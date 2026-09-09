"""Bounded, out-of-process Windows UI Automation, restricted to 3dsmax.exe."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import time
from uuid import uuid4


class UIReadTimeout(TimeoutError):
    """A read-only UI snapshot exceeded its deadline."""


def request(action, pid, *, timeout=12, **kwargs):
    if type(pid) is not int or pid <= 0:
        raise ValueError('An explicit positive Max PID is required')
    if os.name != 'nt':
        raise RuntimeError('Max UI automation requires Windows')
    helper = Path(__file__).with_name('helpers') / 'max_ui.ps1'
    executable = Path(os.environ['SystemRoot']) / 'System32/WindowsPowerShell/v1.0/powershell.exe'
    payload = dict(action=action, process_id=pid, **kwargs)
    try:
        result = subprocess.run([str(executable), '-NoProfile', '-NonInteractive', '-File', str(helper)],
                                input=json.dumps(payload), capture_output=True, text=True, encoding='utf-8',
                                timeout=timeout, creationflags=subprocess.CREATE_NO_WINDOW)
    except subprocess.TimeoutExpired as exc:
        if action in ('windows', 'inspect'):
            raise UIReadTimeout('UI snapshot timed out') from exc
        raise RuntimeError('UI provider timed out; action outcome is unknown. Re-inspect before retrying.') from exc
    if result.returncode:
        raise RuntimeError(result.stderr.strip()[:1500] or 'UI helper failed')
    return json.loads(result.stdout.lstrip('\ufeff'))


def capture_path():
    directory = Path(tempfile.gettempdir()) / '3dsmax-mcp-ui'
    directory.mkdir(exist_ok=True)
    return str(directory / (uuid4().hex + '.png'))
