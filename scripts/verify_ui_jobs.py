"""Explicit live acceptance check: temporary dialog and short sleep job, no render.

Run from the checkout with Max already running: python scripts/verify_ui_jobs.py PID
"""
import json
from pathlib import Path
import sys
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from maxmcp.max_client import MaxClient
from maxmcp.server import client
from maxmcp.tools import jobs, max_ui


def main(pid):
    pipe = rf'\\.\pipe\3dsmax-mcp-{pid}'
    # Resolve using the installed discovery record rather than guessing pipe names.
    import os
    record = Path(os.environ['LOCALAPPDATA'])/'3dsmax-mcp/instances'/f'pid-{pid}.json'
    pipe = json.loads(record.read_text())['pipe']
    from maxmcp.tools.instances import list_max_instances, set_active_instance
    available = list_max_instances()['instances']
    set_active_instance(f'pid-{pid}')
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
        assert changed['value'] == 'verified', changed
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
        others = [item for item in available if item['pipe'] != pipe]
        if others:
            set_active_instance(others[0]['instance_id'])
            other_pid = client.send_command('((dotNetClass "System.Diagnostics.Process").GetCurrentProcess()).Id as string')['result']
            assert int(other_pid) == others[0]['pid']
            assert jobs.max_job_status(jid)['target'] == pipe, 'Job was redirected by target switch'
            set_active_instance(f'pid-{pid}')
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
        assert not any(w['title']==title for w in max_ui.max_ui_windows(pid)['windows'])
        print('PASS: UI read/write/invoke/capture, detached job, responsive status, cooperative cancel', flush=True)
    finally:
        # Destroy only our test dialog; no scene reset or object changes.
        for pending in jobs.max_job_list()['jobs']:
            if pending['state'] not in jobs.jobs.TERMINAL:
                jobs.max_job_cancel(pending['job_id'])
                jobs.max_job_wait(pending['job_id'],20)
        c.send_command('try(destroyDialog mcpAcceptance)catch(); "cleaned"')


if __name__=='__main__': main(int(sys.argv[1]))
