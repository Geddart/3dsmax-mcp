"""Real Max dialog automation without a MaxScript/socket dependency."""
import time
import re
from ..server import mcp
from ..max_ui import request, capture_path, UIReadTimeout


@mcp.tool()
def max_ui_windows(pid: int) -> dict:
    """Find visible top-level dialogs/windows belonging only to this 3dsmax.exe PID.

    Works independently of the Max bridge, including when a job or modal is open.
    Returns observed window tokens; never guess handles or use another app's PID.
    """
    return request('windows', pid)


@mcp.tool()
def max_ui_inspect(pid: int, window: dict, max_elements: int = 200, max_depth: int = 8) -> dict:
    """Inspect a previously observed Max window's UIA controls and supported patterns.

    Element tokens are tied to this process lifetime and window. Re-inspect after
    each mutation. Custom-drawn controls may not expose accessibility patterns.
    """
    if not 1 <= max_elements <= 500 or not 0 <= max_depth <= 15:
        raise ValueError('max_elements must be 1–500; max_depth must be 0–15')
    return request('inspect', pid, window=window, max_elements=max_elements, max_depth=max_depth)


@mcp.tool()
def max_ui_invoke(pid: int, element: dict) -> dict:
    """Invoke an observed Max control with UIA InvokePattern (e.g. a dialog button).

    This can open a modal. A timeout means unknown outcome, not safe-to-retry.
    Inspect the resulting dialogs before issuing another action.
    """
    return request('invoke', pid, element=element)


@mcp.tool()
def max_ui_set_value(pid: int, element: dict, value: str) -> dict:
    """Set an observed editable Max control through ValuePattern, then read it back.

    Rejects password, disabled, and read-only controls. No clipboard or shell use.
    """
    if len(value) > 16000 or '\x00' in value:
        raise ValueError('value must be at most 16000 characters without NUL')
    return request('set_value', pid, element=element, value=value)


@mcp.tool()
def max_ui_send_keys(pid: int, element: dict, keys: str) -> dict:
    """Focus an observed Max control and send a short Windows Forms SendKeys sequence.

    Verify the resulting state. Prefer invoke/set_value. Foreground process is
    checked immediately before input, but the user can still race global input.
    Alt/global shortcuts and password controls are rejected. Prefer set_value for text.
    """
    if not keys or len(keys) > 128:
        raise ValueError('keys must contain 1–128 characters')
    if '%' in keys or re.search(r'\{(?:LWIN|RWIN|APPS|PRTSC|BREAK)', keys, re.I) or ('^' in keys and re.search(r'\{ESC', keys, re.I)):
        raise ValueError('Alt and desktop/global shortcuts are not supported')
    return request('send_keys', pid, element=element, keys=keys)


@mcp.tool()
def max_ui_wait(pid: int, title: str, timeout_seconds: float = 5) -> dict:
    """Wait for a Max window with an exact title; bounded to 30 seconds, no Max socket."""
    if not 0 <= timeout_seconds <= 30:
        raise ValueError('timeout_seconds must be 0–30')
    deadline = time.monotonic() + timeout_seconds
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return {'windows': [], 'timed_out': True}
        try:
            result = request('windows', pid, timeout=min(12, remaining))
        except UIReadTimeout:
            return {'windows': [], 'timed_out': True}
        matches = [w for w in result['windows'] if w['title'] == title]
        if matches or time.monotonic() >= deadline:
            return {'windows': matches, 'timed_out': not bool(matches)}
        time.sleep(min(.2, max(0, deadline-time.monotonic())))


@mcp.tool()
def max_ui_capture(pid: int, window: dict) -> dict:
    """Capture an observed Max window using PrintWindow and return a local PNG path.

    No render and no whole-desktop capture. Some GPU/custom windows return blank
    captures; the result is visual evidence only after the image is inspected.
    """
    return request('capture', pid, window=window, output_path=capture_path())
