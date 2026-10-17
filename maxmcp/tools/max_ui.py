"""Real Max dialog automation without a MaxScript/socket dependency."""
import time
import re
from ..server import mcp
from ..tool_response import run_in_thread
from ..max_ui import request, resolve_pid, capture_path, UIReadTimeout

# A cold PowerShell provider needs about a second before it can answer at all,
# so short waits still give it a usable floor instead of guaranteeing a miss.
_PROVIDER_FLOOR_SECONDS = 4.0
MATCH_MODES = ('exact', 'contains')


def _normalise_title(text: str) -> str:
    """Trim whitespace and the trailing '*' Max appends to modified scenes."""
    return (text or '').strip().rstrip('*').strip()


def _title_matches(observed: str, wanted: str, mode: str) -> bool:
    if mode == 'exact':
        return _normalise_title(observed) == _normalise_title(wanted)
    return _normalise_title(wanted).casefold() in _normalise_title(observed).casefold()


@mcp.tool()
@run_in_thread
def max_ui_windows(pid: int | None = None) -> dict:
    """Find visible top-level dialogs/windows belonging only to one 3dsmax.exe PID.

    Omit pid to use the instance this session routes to (list_max_instances /
    select_max_instance). An explicit pid must be a live registered Max instance
    and must not be protected. Works independently of the Max bridge, including
    when a job or modal is open. Returns observed window tokens plus the pid used.
    """
    return request('windows', pid)


@mcp.tool()
@run_in_thread
def max_ui_inspect(pid: int | None = None, window: dict | None = None,
                   max_elements: int = 200, max_depth: int = 8) -> dict:
    """Inspect a previously observed Max window's UIA controls and supported patterns.

    Omit pid to use this session's pinned instance. Element tokens are tied to
    that process lifetime and window. Re-inspect after each mutation. Custom-drawn
    controls may not expose accessibility patterns.
    """
    if window is None:
        raise ValueError('window must be a token from max_ui_windows')
    if not 1 <= max_elements <= 500 or not 0 <= max_depth <= 15:
        raise ValueError('max_elements must be 1–500; max_depth must be 0–15')
    return request('inspect', pid, window=window, max_elements=max_elements, max_depth=max_depth)


@mcp.tool()
@run_in_thread
def max_ui_invoke(pid: int | None = None, element: dict | None = None) -> dict:
    """Invoke an observed Max control with UIA InvokePattern (e.g. a dialog button).

    Omit pid to use this session's pinned instance. This can open a modal. A
    timeout means unknown outcome, not safe-to-retry. Inspect the resulting
    dialogs before issuing another action.
    """
    if element is None:
        raise ValueError('element must be a token from max_ui_inspect')
    return request('invoke', pid, element=element)


@mcp.tool()
@run_in_thread
def max_ui_set_value(pid: int | None = None, element: dict | None = None,
                     value: str | None = None, commit: bool = False) -> dict:
    """Set an observed editable Max control, then read it back without asserting equality.

    Omit pid to use this session's pinned instance. Returns value_written,
    readback and matches: controls legitimately normalise text ("1" becomes
    "1.0"), so a differing readback is reported, not raised; only a failed write
    raises. A native Edit fallback uses WM_SETTEXT, which does NOT fire a
    MAXScript rollout 'on entered' handler — pass commit=True to send {ENTER}
    through the focused control afterwards. That {ENTER} goes through SendKeys,
    which is desktop-global: the foreground process is checked before and again
    after the injection, and a window that stole focus in between comes back as
    committed=false with foreground_changed and commit_error, meaning the
    keystroke may have landed elsewhere. The written value stands either way.
    Rejects password, disabled, and read-only controls. No clipboard or shell use.
    """
    if element is None:
        raise ValueError('element must be a token from max_ui_inspect')
    if value is None:
        # pid is optional and comes first, so an omitted value must not be
        # silently written as an empty string.
        raise ValueError('value is required')
    if len(value) > 16000 or '\x00' in value:
        raise ValueError('value must be at most 16000 characters without NUL')
    return request('set_value', pid, element=element, value=value, commit=bool(commit))


@mcp.tool()
@run_in_thread
def max_ui_send_keys(pid: int | None = None, element: dict | None = None, keys: str = '') -> dict:
    """Focus an observed Max control and send a short Windows Forms SendKeys sequence.

    Omit pid to use this session's pinned instance. Verify the resulting state.
    Prefer invoke/set_value. The foreground process is checked immediately before
    input and re-read afterwards, but SendKeys is desktop-global: a window that
    stole focus in between comes back as completed=false with foreground_changed,
    an unknown outcome, not a failure. Alt/global shortcuts and
    password controls are rejected. Prefer set_value for text.
    """
    if element is None:
        raise ValueError('element must be a token from max_ui_inspect')
    if not keys or len(keys) > 128:
        raise ValueError('keys must contain 1–128 characters')
    if '%' in keys or re.search(r'\{(?:LWIN|RWIN|APPS|PRTSC|BREAK)', keys, re.I) or ('^' in keys and re.search(r'\{ESC', keys, re.I)):
        raise ValueError('Alt and desktop/global shortcuts are not supported')
    return request('send_keys', pid, element=element, keys=keys)


@mcp.tool()
@run_in_thread
def max_ui_wait(pid: int | None = None, title: str = '', timeout_seconds: float = 5,
                match: str = 'exact') -> dict:
    """Wait for a Max window by title; bounded to 30 seconds, no Max socket.

    Omit pid to use this session's pinned instance. match='exact' (default)
    compares after normalisation — surrounding whitespace and a trailing '*' are
    ignored; match='contains' accepts any window whose normalised title contains
    the requested text, case-insensitively. timeout_seconds=0 still probes once.
    """
    if not 0 <= timeout_seconds <= 30:
        raise ValueError('timeout_seconds must be 0–30')
    if match not in MATCH_MODES:
        raise ValueError(f"match must be one of {', '.join(MATCH_MODES)}")
    target = resolve_pid(pid)
    deadline = time.monotonic() + timeout_seconds
    probed = False
    while True:
        remaining = deadline - time.monotonic()
        if probed and remaining <= 0:
            return {'windows': [], 'timed_out': True, 'pid': target}
        try:
            # The ORIGINAL pid argument is passed on every probe: handing the
            # resolved int back to request() would re-authorise it through the
            # explicit-pid branch, which demands registry membership that a
            # session-resolved pid need not have.
            # A short deadline must not starve the provider of its startup cost.
            result = request('windows', pid, timeout=min(12, max(remaining, _PROVIDER_FLOOR_SECONDS)))
        except UIReadTimeout:
            return {'windows': [], 'timed_out': True, 'pid': target}
        probed = True
        matches = [w for w in result['windows'] if _title_matches(w.get('title', ''), title, match)]
        if matches or time.monotonic() >= deadline:
            return {'windows': matches, 'timed_out': not bool(matches), 'pid': target}
        time.sleep(min(.2, max(0, deadline - time.monotonic())))


@mcp.tool()
@run_in_thread
def max_ui_capture(pid: int | None = None, window: dict | None = None) -> dict:
    """Capture an observed Max window using PrintWindow and return a local PNG path.

    Omit pid to use this session's pinned instance. No render and no whole-desktop
    capture. Some GPU/custom windows return blank captures; the result is visual
    evidence only after the image is inspected.
    """
    if window is None:
        raise ValueError('window must be a token from max_ui_windows')
    return request('capture', pid, window=window, output_path=capture_path())
