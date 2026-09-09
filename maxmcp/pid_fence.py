"""Operator fence naming 3ds Max instances that no MCP path may drive.

`MCP_UI_DENY_PIDS` and `%LOCALAPPDATA%\3dsmax-mcp\protected_pids.json` are read
here rather than inside one tool family, because a fence that only covers the
`max_ui_*` tools is not a fence: every other tool reaches the same Max through
the native transport router. Both `maxmcp.max_ui` (before any input is sent) and
`maxmcp.max_client` (before any command is routed) consult this module.

A bare PID is recycled by Windows, so an entry naming only a PID lapses the
moment the protected Max restarts. The file therefore also accepts
``max_versions``: the value compared is the ``max_version`` field the native
bridge writes into each instance record, which survives a restart.

    {"pids": [9876], "max_versions": [27000]}

`unmatched_pids()` reports fence entries that match no live instance, so a
lapsed entry is visible in `list_max_instances` instead of failing silently.
"""
import json
import os
from pathlib import Path

DENY_ENV = 'MCP_UI_DENY_PIDS'
PROTECTED_FILE = 'protected_pids.json'


def config_dir() -> Path:
    root = os.environ.get('LOCALAPPDATA')
    if root:
        return Path(root) / '3dsmax-mcp'
    return Path.home() / 'AppData' / 'Local' / '3dsmax-mcp'


def _fence_document() -> dict:
    """The protected_pids.json body, as a dict; a bare list means bare PIDs."""
    try:
        data = json.loads((config_dir() / PROTECTED_FILE).read_text('utf-8'))
    except (OSError, ValueError):
        return {}
    if isinstance(data, list):
        return {'pids': data}
    return data if isinstance(data, dict) else {}


def _coerce_pid(value) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        pid = int(value)
    except (TypeError, ValueError):
        return None
    return pid if pid > 0 else None


def denied_pids() -> set[int]:
    """PIDs the operator fenced off: env deny list plus protected_pids.json."""
    denied = set()
    for chunk in (os.environ.get(DENY_ENV) or '').replace(';', ',').split(','):
        chunk = chunk.strip()
        if chunk.isdigit():
            denied.add(int(chunk))
    entries = _fence_document().get('pids')
    if isinstance(entries, list):
        for item in entries:
            pid = _coerce_pid(item)
            if pid is not None:
                denied.add(pid)
    return denied


def denied_max_versions() -> set[str]:
    """Bridge `max_version` values fenced off; unlike a PID these survive a restart."""
    entries = _fence_document().get('max_versions')
    if not isinstance(entries, list):
        return set()
    return {str(item).strip() for item in entries if str(item).strip()}


def fence_reason(pid=None, record=None) -> str | None:
    """Why this instance must not be targeted, or None when it may be."""
    if pid is None and isinstance(record, dict):
        pid = record.get('pid')
    pid = _coerce_pid(pid)
    if pid is not None and pid in denied_pids():
        return f'PID {pid} is listed in {DENY_ENV} or {PROTECTED_FILE}'
    if isinstance(record, dict):
        version = record.get('max_version')
        if version is not None and str(version).strip() in denied_max_versions():
            return f'max_version {version} is listed in {PROTECTED_FILE}'
    return None


def unmatched_pids(live_pids) -> list[int]:
    """Fenced PIDs carried by no live instance: entries that have lapsed."""
    live = {pid for pid in (_coerce_pid(item) for item in live_pids) if pid}
    return sorted(denied_pids() - live)
