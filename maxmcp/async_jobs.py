"""Session-owned jobs; only scheduling uses the bridge, polling uses local files.

Original implementation. MAXScript always runs on Max's UI thread, never a Python
worker. A timer releases the request before running the operation.
"""
from __future__ import annotations

import atexit
import configparser
import json
import math
import os
from pathlib import Path
import shutil
import tempfile
import threading
import time
from uuid import uuid4


# Mirrors the `blocked[]` array in native/src/command_dispatcher.cpp. Submitted
# job code is written to a file and run via execute(readAllText) inside Max, so
# the native filter never sees it; this list is the only guard on that path.
BLOCKED_COMMANDS = (
    'doscommand',
    'shelllaunch',
    'deletefile',
    'python.execute',
    'createfile',
    'hiddendoscommand',
)


class JobNotSentError(Exception):
    """Raised by a scheduler that can prove its request never reached Max."""


# Failures that prove nothing was written to the bridge. These mirror the raise
# sites in maxmcp/max_client.py: both the connection lock and _ensure_pipe_handle
# fail before the first WriteFile, so such a job is terminal, not uncertain.
_UNSENT_MARKERS = (
    'request not sent',                    # connection lock timeout
    'is the mcp bridge plugin loaded',     # CreateFileW: pipe does not exist
    'disappeared while waiting',           # pipe vanished before connect
    'failed to open pipe: win32 error',    # connect failed outright
    'timed out waiting for named pipe',    # pipe busy, never connected
    'failed waiting for named pipe',
    'native max bridge is not available',  # probe failed before scheduling
)
# Once the request may have been written, the outcome is genuinely ambiguous.
_AMBIGUOUS_MARKERS = (
    'response after',
    'while writing',
    'while reading',
    'pipe write returned',
    'before response terminator',
)


def is_provably_unsent(exc: BaseException) -> bool:
    """True only when the scheduling request demonstrably never left this process."""
    if isinstance(exc, JobNotSentError):
        return True
    text = str(exc).lower()
    if any(marker in text for marker in _AMBIGUOUS_MARKERS):
        return False
    return any(marker in text for marker in _UNSENT_MARKERS)


def default_config_dir() -> Path:
    root = os.environ.get('LOCALAPPDATA')
    return (Path(root) if root else Path.home() / 'AppData' / 'Local') / '3dsmax-mcp'


def safe_mode_enabled(config_dir=None) -> bool:
    config = configparser.ConfigParser()
    try:
        config.read(Path(config_dir or default_config_dir()) / 'mcp_config.ini', encoding='utf-8-sig')
        return config.getboolean('mcp', 'safe_mode', fallback=True)
    except (OSError, configparser.Error, ValueError):
        return True


def check_safe_mode(code: str, config_dir=None) -> None:
    """Single enforcement point for the native blocklist on job code."""
    if not safe_mode_enabled(config_dir):
        return
    lowered = code.lower()
    if any(token in lowered for token in BLOCKED_COMMANDS):
        raise ValueError('Blocked by safe mode: job contains a restricted function. '
                         r'Set safe_mode=false in %LOCALAPPDATA%\3dsmax-mcp\mcp_config.ini to disable.')


# State transitions are monotonic: a job never moves backwards, so a slow
# scheduler thread cannot overwrite a state the job files already published.
_STATE_RANK = {'submitting': 0, 'scheduled': 1, 'unknown': 1, 'running': 2,
               'succeeded': 3, 'failed': 3, 'cancelled': 3}


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
        owned = root is None
        self.root = Path(root) if root else Path(tempfile.gettempdir()) / '3dsmax-mcp-jobs' / uuid4().hex
        self.capacity = capacity
        self.jobs = {}
        self.lock = threading.RLock()
        if owned:
            # The per-process scratch dir is ours; drop it again when it is empty.
            atexit.register(self._remove_root_if_empty)

    def _remove_root_if_empty(self):
        try:
            self.root.rmdir()
        except OSError:
            pass

    def _advance(self, jid, state, **extra):
        """Move a job forward only; refuse regressions and terminal overwrites."""
        item = self.jobs.get(jid)
        if item is None:
            return None
        if _STATE_RANK.get(state, -1) > _STATE_RANK.get(item['state'], -1):
            item['state'] = state
            item.update(extra)
        return item['state']

    def submit(self, code, target, schedule, label='MAXScript', config_dir=None):
        if not code.strip() or len(code) > 1_000_000:
            raise ValueError('Provide 1–1,000,000 characters of MAXScript')
        # Every submission path funnels through here, so the blocklist is checked once.
        check_safe_mode(code, config_dir)
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
                        self._write_scheduling_error(jid, reply)
                        self._advance(jid, 'failed', finished_at=time.time())
                return
            if response.get('result') != 'scheduled:' + jid:
                raise RuntimeError('Scheduling was not acknowledged: ' + str(response)[:500])
            with self.lock:
                self._advance(jid, 'scheduled')
        except Exception as exc:
            message = str(exc)[:1000]
            with self.lock:
                if jid not in self.jobs:
                    return
                if is_provably_unsent(exc):
                    # Nothing reached Max, so the job is terminal and releases the target.
                    self._write_scheduling_error(jid, message)
                    self._advance(jid, 'failed', finished_at=time.time(), scheduling_error=message)
                else:
                    # A timeout is not proof of failure: Max may execute the request later.
                    self._advance(jid, 'unknown', scheduling_error=message)

    def _write_scheduling_error(self, jid, message):
        try:
            (self.root / jid / 'error').write_text(message, encoding='utf-8')
        except OSError:
            pass

    def status(self, jid):
        with self.lock:
            if jid not in self.jobs:
                raise ValueError('Unknown job handle in this MCP server session')
            result = dict(self.jobs[jid])
            folder = self.root / jid
            try:
                state = (folder / 'state').read_text(encoding='utf-8-sig').strip()
                if state in self.TERMINAL | {'running'}:
                    result['state'] = self._advance(jid, state)
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

    def forget(self, jid, force=False):
        with self.lock:
            state = self.status(jid)['state']
            forced = False
            if state not in self.TERMINAL:
                if not (force and state == 'unknown'):
                    raise ValueError(
                        'Cannot forget an active job; cancellation is not completion'
                        + (". Pass force=True to release this 'unknown' job, but only if you "
                           'verified in Max that nothing is running.' if state == 'unknown' else ''))
                forced = True
            shutil.rmtree(self.root / jid, ignore_errors=True)
            del self.jobs[jid]
        return {'forgotten': jid, 'forced': forced, 'state_when_forgotten': state}


jobs = JobStore()


def busy_job(target):
    with jobs.lock:
        for jid, item in jobs.jobs.items():
            if item['target'] == target and jobs.status(jid)['state'] not in jobs.TERMINAL:
                return jid
    return None
