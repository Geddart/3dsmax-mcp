"""Bounded, out-of-process Windows UI Automation, restricted to 3dsmax.exe.

The targeted PID is never a free-form argument: it is either the instance this
MCP session is pinned to, or an explicitly passed PID that must still appear in
the live native-bridge instance registry and must not be protected. A wrong PID
would click inside somebody's production Max, so resolution fails closed before
any PowerShell process is spawned.
"""
import ctypes
import json
import os
from pathlib import Path
import subprocess
import tempfile
from uuid import uuid4

DENY_ENV = 'MCP_UI_DENY_PIDS'
PROTECTED_FILE = 'protected_pids.json'
_STILL_ACTIVE = 259
_PROCESS_QUERY_LIMITED_INFORMATION = 0x1000


class UIReadTimeout(TimeoutError):
    """A read-only UI snapshot exceeded its deadline."""


class UITargetError(ValueError):
    """The requested PID is not an addressable, permitted Max instance."""


def config_dir():
    root = os.environ.get('LOCALAPPDATA')
    if root:
        return Path(root) / '3dsmax-mcp'
    return Path.home() / 'AppData' / 'Local' / '3dsmax-mcp'


def _process_is_live(pid):
    """True only for a currently running process; never signals or touches it."""
    if os.name != 'nt':
        return False
    kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
    handle = kernel32.OpenProcess(_PROCESS_QUERY_LIMITED_INFORMATION, False, int(pid))
    if not handle:
        return False
    try:
        code = ctypes.c_ulong()
        if not kernel32.GetExitCodeProcess(handle, ctypes.byref(code)):
            return False
        return code.value == _STILL_ACTIVE
    finally:
        kernel32.CloseHandle(handle)


def registered_pids():
    """Live PIDs advertised by the native bridge as pid-*.json instance records."""
    found = set()
    try:
        paths = sorted((config_dir() / 'instances').glob('pid-*.json'))
    except OSError:
        return found
    for path in paths:
        try:
            data = json.loads(path.read_text('utf-8'))
        except (OSError, ValueError):
            continue
        if not isinstance(data, dict):
            continue
        try:
            pid = int(data.get('pid'))
        except (TypeError, ValueError):
            continue
        if pid > 0 and _process_is_live(pid):
            found.add(pid)
    return found


def denied_pids():
    """PIDs the operator has fenced off: env deny list plus protected_pids.json."""
    denied = set()
    for chunk in (os.environ.get(DENY_ENV) or '').replace(';', ',').split(','):
        chunk = chunk.strip()
        if chunk.isdigit():
            denied.add(int(chunk))
    try:
        data = json.loads((config_dir() / PROTECTED_FILE).read_text('utf-8'))
    except (OSError, ValueError):
        return denied
    if isinstance(data, dict):
        data = data.get('pids', [])
    if isinstance(data, list):
        for item in data:
            try:
                denied.add(int(item))
            except (TypeError, ValueError):
                continue
    return denied


def _session_client():
    from .server import client
    return client


def session_pid():
    """The PID this MCP session is pinned to, or None when routing is automatic."""
    client = _session_client()
    selected = getattr(client, 'selected_pid', None)
    if selected is None:
        raise UITargetError(
            'This build cannot resolve the session Max instance (MaxClient.selected_pid '
            'is unavailable); pass an explicit pid from list_max_instances')
    pid = selected()
    if pid is None:
        return None
    try:
        pid = int(pid)
    except (TypeError, ValueError):
        return None
    return pid if pid > 0 else None


def resolve_pid(pid=None):
    """Resolve and authorise the Max PID a UI action may target."""
    if pid is None:
        pid = session_pid()
        if pid is None:
            raise UITargetError(
                'No 3ds Max instance is bound to this session; run list_max_instances '
                'then set_active_instance, or pass an explicit pid')
    else:
        if type(pid) is not int or pid <= 0:
            raise ValueError('An explicit positive Max PID is required')
        known = registered_pids()
        if pid not in known:
            listed = ', '.join(str(item) for item in sorted(known)) or 'none'
            raise UITargetError(
                f'PID {pid} is not a live registered 3ds Max MCP instance; '
                f'registered PIDs: {listed}')
    if pid in denied_pids():
        raise UITargetError(
            f'PID {pid} is protected against UI automation '
            f'({DENY_ENV} or {PROTECTED_FILE}); refusing before any input is sent')
    return pid


def request(action, pid=None, *, timeout=12, **kwargs):
    if pid is not None and (type(pid) is not int or pid <= 0):
        raise ValueError('An explicit positive Max PID is required')
    if os.name != 'nt':
        raise RuntimeError('Max UI automation requires Windows')
    target = resolve_pid(pid)
    helper = Path(__file__).with_name('helpers') / 'max_ui.ps1'
    executable = Path(os.environ['SystemRoot']) / 'System32/WindowsPowerShell/v1.0/powershell.exe'
    payload = dict(action=action, process_id=target, **kwargs)
    try:
        result = subprocess.run([str(executable), '-NoProfile', '-NonInteractive',
                                 '-ExecutionPolicy', 'Bypass', '-File', str(helper)],
                                input=json.dumps(payload), capture_output=True, text=True, encoding='utf-8',
                                timeout=timeout, creationflags=subprocess.CREATE_NO_WINDOW)
    except subprocess.TimeoutExpired as exc:
        if action in ('windows', 'inspect'):
            raise UIReadTimeout(f'UI snapshot timed out for pid {target}') from exc
        raise RuntimeError(f'UI provider timed out for pid {target}; action outcome is unknown. '
                           'Re-inspect before retrying.') from exc
    if result.returncode:
        raise RuntimeError(result.stderr.strip()[:1500] or 'UI helper failed')
    answer = json.loads(result.stdout.lstrip('\ufeff'))
    if isinstance(answer, dict):
        # Every result names the process that was actually operated on.
        answer['pid'] = target
    return answer


def capture_path():
    directory = Path(tempfile.gettempdir()) / '3dsmax-mcp-ui'
    directory.mkdir(exist_ok=True)
    return str(directory / (uuid4().hex + '.png'))
