"""Explicit live acceptance check: temporary dialog and short sleep job, no render.

Run from the checkout with Max already running: python scripts/verify_ui_jobs.py PID

The cross-instance isolation check drives a SECOND Max, so it never picks one on
its own: pass `--other-pid N` to opt in, and only for a Max you are willing to
have MAXScript executed in. A protected PID is refused outright.
"""
import json
import os
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from maxmcp.max_client import MaxClient
from maxmcp.pid_fence import fence_reason
from maxmcp.server import client
from maxmcp.tools import jobs, max_ui
from maxmcp.tools.routing import get_selected_max_instance, list_max_instances, release_max_instance, select_max_instance


def selected_instance_pid():
    """The PID this process is currently pinned to, for later restoration."""
    current = get_selected_max_instance()
    return current['target_pid'] if current.get('pinned') else None


def restore_selection(previous):
    """Re-pin the PID we started on, or drop the pin if there was none."""
    if previous:
        select_max_instance(previous)
    else:
        release_max_instance()


def wait_until_gone(pid, title, seconds=10):
    """A queued click is dispatched, not completed: give the dialog time to close."""
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if not any(w['title'] == title for w in max_ui.max_ui_windows(pid)['windows']):
            return True
        time.sleep(.2)
    return False


def main(pid, other_pid=None):
    # Resolve using the installed discovery record rather than guessing pipe names.
    record = Path(os.environ['LOCALAPPDATA'])/'3dsmax-mcp/instances'/f'pid-{pid}.json'
    pipe = json.loads(record.read_text())['pipe']
    available = list_max_instances()['instances']
    previous = selected_instance_pid()
    select_max_instance(pid)
    assert client._resolve_pipe_name() == pipe
    c = MaxClient(transport='pipe', pipe_name=pipe)
    title = 'MCP UI Job Acceptance'
    c.send_command('(global mcpAcceptance; try(destroyDialog mcpAcceptance)catch(); rollout mcpAcceptance "MCP UI Job Acceptance" (edittext field "Value:" text:"before"; button finish "Finish"; on finish pressed do destroyDialog mcpAcceptance); createDialog mcpAcceptance 260 110; "ready")')
    try:
        windows = max_ui.max_ui_windows(pid)['windows']
        window = next(w['token'] for w in windows if w['title'] == title)
        controls = max_ui.max_ui_inspect(pid, window)['elements']
        print('UI_CONTROLS', [(e['name'],e['class_name'],e['control_type'],e['patterns']) for e in controls], flush=True)
        edit = next(e['token'] for e in controls if e['native_set_value'])
        changed = max_ui.max_ui_set_value(pid, edit, 'verified')
        # A control may legitimately normalise text; the readback is reported, not thrown.
        assert changed['readback'] == 'verified' and changed['matches'], changed
        assert changed['pid'] == pid, changed
        max_ui.max_ui_send_keys(pid, edit, '{END}')
        capture = max_ui.max_ui_capture(pid, window)
        print('UI_CAPTURE', capture, flush=True)
        start = time.monotonic()
        job = jobs.max_job_submit('mcpJobProgress 25; sleep 8; mcpJobCheckCancel(); "job result verified"', 'Live acceptance')
        jid = job['job_id']
        assert time.monotonic()-start < 1, 'submit blocked'
        deadline = time.monotonic()+15
        while jobs.max_job_status(jid)['state'] not in ('running','unknown') and time.monotonic()<deadline:
            time.sleep(.05)
        state = jobs.max_job_status(jid)
        assert state['state']=='running', state
        # Opt-in only: this block executes MAXScript in a second Max. Auto-picking
        # one would run it in whichever other Max happens to be open, which on a
        # workstation is the production instance.
        if other_pid is None:
            print('SKIP isolation check: pass --other-pid N to run it in a second Max', flush=True)
        else:
            other = next((item for item in available if item.get('pid') == other_pid), None)
            assert other is not None and other['pipe'] != pipe, (
                f'--other-pid {other_pid} is not a second live instance; '
                f'live: {[item.get("pid") for item in available]}')
            reason = fence_reason(other_pid, other)
            assert reason is None, f'--other-pid {other_pid} is protected ({reason}); refusing to drive it'
            # Never leave the session pinned to a foreign instance, even on failure.
            try:
                select_max_instance(other_pid)
                reported = client.send_command('((dotNetClass "System.Diagnostics.Process").GetCurrentProcess()).Id as string')['result']
                assert int(reported) == other_pid
                assert jobs.max_job_status(jid)['target'] == pipe, 'Job was redirected by target switch'
            finally:
                select_max_instance(pid)
        start = time.monotonic()
        assert jobs.max_job_status(jid)['state']=='running'
        assert time.monotonic()-start < .2, 'poll blocked'
        # UI remains addressable without submitting to the occupied Max main thread.
        during = max_ui.max_ui_windows(pid)
        assert any(w['title']==title for w in during['windows']), during
        done = jobs.max_job_wait(jid, 20)
        assert done['state']=='succeeded', jobs.max_job_result(jid)
        assert jobs.max_job_result(jid)['output']=='job result verified'
        # Cooperative cancellation path; do not forcefully interrupt Max.
        cancelled = jobs.max_job_submit('for i=1 to 30 do (sleep .1; mcpJobCheckCancel()); "unexpected"', 'Cancel acceptance')
        deadline=time.monotonic()+5
        while jobs.max_job_status(cancelled['job_id'])['state'] != 'running' and time.monotonic()<deadline:
            time.sleep(.05)
        assert jobs.max_job_status(cancelled['job_id'])['state']=='running'
        jobs.max_job_cancel(cancelled['job_id'])
        assert jobs.max_job_wait(cancelled['job_id'],10)['state']=='cancelled'
        modal = jobs.max_job_submit('messageBox "Temporary acceptance check" title:"MCP Modal Acceptance"; "modal dismissed"', 'Modal acceptance')
        modal_window=max_ui.max_ui_wait(pid,'MCP Modal Acceptance',10)['windows'][0]['token']
        modal_controls=max_ui.max_ui_inspect(pid,modal_window)['elements']
        accept=next(e['token'] for e in modal_controls if e['name']=='OK')
        max_ui.max_ui_invoke(pid,accept)
        assert jobs.max_job_wait(modal['job_id'],10)['state']=='succeeded'
        controls = max_ui.max_ui_inspect(pid, window)['elements']
        button = next(e['token'] for e in controls if e['name']=='Finish' and e['native_invoke'])
        max_ui.max_ui_invoke(pid, button)
        assert wait_until_gone(pid, title), 'Finish click did not close the acceptance dialog'
        print('PASS: UI read/write/invoke/capture, detached job, responsive status, cooperative cancel', flush=True)
    finally:
        # Destroy only our test dialog; no scene reset or object changes.
        for pending in jobs.max_job_list()['jobs']:
            if pending['state'] not in jobs.jobs.TERMINAL:
                jobs.max_job_cancel(pending['job_id'])
                jobs.max_job_wait(pending['job_id'],20)
        c.send_command('try(destroyDialog mcpAcceptance)catch(); "cleaned"')
        restore_selection(previous)


def parse_args(argv):
    """PID, then an optional opt-in `--other-pid N` for the isolation check."""
    if not argv:
        raise SystemExit('usage: verify_ui_jobs.py PID [--other-pid N]')
    other = None
    if '--other-pid' in argv:
        index = argv.index('--other-pid')
        if index + 1 >= len(argv):
            raise SystemExit('--other-pid needs a PID')
        other = int(argv[index + 1])
        argv = argv[:index] + argv[index + 2:]
    return int(argv[0]), other


if __name__=='__main__': main(*parse_args(sys.argv[1:]))
