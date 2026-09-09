"""Session-owned jobs; only scheduling uses the bridge, polling uses local files.

Original implementation. MAXScript always runs on Max's UI thread, never a Python
worker. A timer releases the request before running the operation.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
import tempfile
import threading
import time
from uuid import uuid4


def ms_string(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def bootstrap(job_id: str, directory: Path) -> str:
    base = directory.as_posix()
    def path(name):
        return ms_string(base + '/' + name)
    # Functions contain literal paths: MAXScript callbacks cannot close over
    # stack-local variables. Stop timer before user code pumps nested messages.
    return f'''(
global mcpAsyncActiveJob
if (dotNetClass "System.IO.File").Exists {path('accepted')} do return "scheduled:{job_id}"
if mcpAsyncActiveJob != undefined do return "rejected:{job_id}:Another async job owns this Max instance"
global mcpAsyncTimer_{job_id}
fn mcpAsyncRun_{job_id} sender args = (
 sender.Stop()
 local io = dotNetClass "System.IO.File"
 local finalState = "cancelled"
 try (
  if not (io.Exists {path('cancel')}) do (
   io.WriteAllText {path('state')} "running"
   local answer = execute (io.ReadAllText {path('operation.ms')})
   io.WriteAllText {path('result')} (answer as string)
   finalState = "succeeded"
  )
 ) catch (
  local message = getCurrentException() as string
  finalState = (if matchPattern message pattern:"*MCP_JOB_CANCELLED*" then "cancelled" else "failed")
  try (io.WriteAllText {path('error')} message) catch ()
 )
 try (sender.Dispose()) catch ()
 mcpAsyncActiveJob = undefined
 mcpAsyncTimer_{job_id} = undefined
 -- Publish completion only AFTER releasing the Max reservation.
 io.WriteAllText {path('state')} finalState
)
try (
 mcpAsyncTimer_{job_id} = dotNetObject "System.Windows.Forms.Timer"
 dotNet.addEventHandler mcpAsyncTimer_{job_id} "Tick" mcpAsyncRun_{job_id}
 mcpAsyncTimer_{job_id}.Interval = 250
 mcpAsyncActiveJob = "{job_id}"
 mcpAsyncTimer_{job_id}.Start()
 (dotNetClass "System.IO.File").WriteAllText {path('accepted')} "accepted"
) catch (
 local message = getCurrentException() as string
 try (mcpAsyncTimer_{job_id}.Stop(); mcpAsyncTimer_{job_id}.Dispose()) catch ()
 mcpAsyncTimer_{job_id} = undefined
 mcpAsyncActiveJob = undefined
 return ("rejected:{job_id}:" + message)
)
"scheduled:{job_id}"
)'''


def operation(code: str, directory: Path) -> str:
    def path(name):
        return ms_string((directory / name).as_posix())
    return f'''(
fn mcpJobCancelRequested = ((dotNetClass "System.IO.File").Exists {path('cancel')})
fn mcpJobCheckCancel = (if mcpJobCancelRequested() do throw "MCP_JOB_CANCELLED")
fn mcpJobProgress percent = ((dotNetClass "System.IO.File").WriteAllText {path('progress')} (percent as string))
{code}
)'''


class JobStore:
    TERMINAL = {'succeeded', 'failed', 'cancelled'}

    def __init__(self, root=None, capacity=64):
        self.root = Path(root) if root else Path(tempfile.gettempdir()) / '3dsmax-mcp-jobs' / uuid4().hex
        self.capacity = capacity
        self.jobs = {}
        self.lock = threading.RLock()

    def submit(self, code, target, schedule, label='MAXScript'):
        if not code.strip() or len(code) > 1_000_000:
            raise ValueError('Provide 1–1,000,000 characters of MAXScript')
        with self.lock:
            if len(self.jobs) >= self.capacity:
                raise ValueError('Job history full; forget completed jobs first')
            for jid, item in self.jobs.items():
                if item['target'] == target and self.status(jid)['state'] not in self.TERMINAL:
                    raise ValueError('This Max instance already has an active or uncertain job')
            jid = uuid4().hex
            folder = self.root / jid
            folder.mkdir(parents=True)
            (folder / 'operation.ms').write_text(operation(code, folder), encoding='utf-8')
            self.jobs[jid] = dict(job_id=jid, target=target, label=label[:120], created_at=time.time(),
                                  state='submitting', cancel_requested=False)
            threading.Thread(target=self._schedule, args=(jid, schedule), daemon=True).start()
            return self.status(jid)

    def _schedule(self, jid, schedule):
        try:
            response = schedule(bootstrap(jid, self.root / jid))
            reply = response.get('result')
            if isinstance(reply, str) and reply.startswith('rejected:' + jid + ':'):
                with self.lock:
                    if jid in self.jobs:
                        (self.root / jid / 'error').write_text(reply, encoding='utf-8')
                        self.jobs[jid].update(state='failed', finished_at=time.time())
                return
            if response.get('result') != 'scheduled:' + jid:
                raise RuntimeError('Scheduling was not acknowledged: ' + str(response)[:500])
            with self.lock:
                if jid in self.jobs and self.jobs[jid]['state'] not in self.TERMINAL:
                    self.jobs[jid]['state'] = 'scheduled'
        except Exception as exc:
            # A timeout is not proof of failure: Max may execute the request later.
            with self.lock:
                if jid in self.jobs and self.jobs[jid]['state'] not in self.TERMINAL:
                    self.jobs[jid].update(state='unknown', scheduling_error=str(exc)[:1000])

    def status(self, jid):
        with self.lock:
            if jid not in self.jobs:
                raise ValueError('Unknown job handle in this MCP server session')
            result = dict(self.jobs[jid])
            folder = self.root / jid
            try:
                state = (folder / 'state').read_text(encoding='utf-8-sig').strip()
                if result['state'] not in self.TERMINAL and state in self.TERMINAL | {'running'}:
                    result['state'] = state
                    self.jobs[jid]['state'] = state
                if state in self.TERMINAL:
                    result['finished_at'] = self.jobs[jid].setdefault('finished_at', time.time())
            except (FileNotFoundError, PermissionError):
                # .NET may briefly hold an exclusive handle while publishing.
                pass
            try:
                progress = float((folder / 'progress').read_text(encoding='utf-8-sig'))
                if math.isfinite(progress):
                    result['progress_percent'] = min(100, max(0, progress))
            except (FileNotFoundError, PermissionError, ValueError):
                pass
            result['elapsed_seconds'] = round(result.get('finished_at', time.time()) - result['created_at'], 2)
            result['cancellation'] = 'cooperative; script must call mcpJobCheckCancel()'
            return result

    def result(self, jid, offset=0, limit=16000):
        if offset < 0 or not 1 <= limit <= 64000:
            raise ValueError('offset must be nonnegative; limit must be 1–64000')
        result = self.status(jid)
        if result['state'] not in self.TERMINAL:
            return result
        file = self.root / jid / ('result' if result['state'] == 'succeeded' else 'error')
        if file.exists():
            with file.open(encoding='utf-8-sig') as stream:
                # Text offsets are characters; bounded output avoids huge MCP results.
                remaining = offset
                while remaining:
                    chunk = stream.read(min(remaining, 64000))
                    if not chunk:
                        break
                    remaining -= len(chunk)
                text = stream.read(limit)
                more = bool(stream.read(1))
            result.update(output=text, next_offset=offset + len(text) if more else None)
        return result

    def cancel(self, jid):
        with self.lock:
            result = self.status(jid)
            if result['state'] not in self.TERMINAL:
                (self.root / jid / 'cancel').touch()
                self.jobs[jid]['cancel_requested'] = True
            return self.status(jid)

    def forget(self, jid):
        import shutil
        with self.lock:
            if self.status(jid)['state'] not in self.TERMINAL:
                raise ValueError('Cannot forget an active or uncertain job; cancellation is not completion')
            shutil.rmtree(self.root / jid)
            del self.jobs[jid]
        return {'forgotten': jid}


jobs = JobStore()


def busy_job(target):
    with jobs.lock:
        for jid, item in jobs.jobs.items():
            if item['target'] == target and jobs.status(jid)['state'] not in jobs.TERMINAL:
                return jid
    return None
