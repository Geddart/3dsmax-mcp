"""Detached Max main-thread operations with session-owned handles."""
import time
from ..server import mcp, client
from ..max_client import MaxClient
from ..async_jobs import jobs, ms_string
from ..tool_response import run_in_thread


@mcp.tool()
@run_in_thread
def max_job_submit(code: str, label: str = 'MAXScript') -> dict:
    """Schedule MAXScript and return immediately with a job handle.

    Runs on Max's main thread after releasing the bridge request. Status/result
    polling needs no Max socket. Native pipe required. No automatic retries.
    Scripts may call mcpJobProgress(percentage), mcpJobCheckCancel(), or
    mcpJobCancelRequested(). Render/simulation still occupies Max's main thread.
    Handles live for this MCP server session; restarting MCP loses ownership.
    """
    selected = client
    # Safe mode is enforced inside JobStore.submit so every path shares one check.
    pipe = selected._resolve_pipe_name()
    if not selected._probe_pipe_available(pipe):
        raise ValueError('Selected native Max bridge is not available')
    def schedule(script):
        connection = MaxClient(transport='pipe', pipe_name=pipe)
        connection._async_scheduler = True
        try:
            return connection.send_command(script, timeout=30)
        finally:
            connection._close_pipe_handle()
    return jobs.submit(code, pipe, schedule, label, config_dir=selected._config_dir())


@mcp.tool()
@run_in_thread
def max_job_render(width: int = 1920, height: int = 1080, output_path: str = '') -> dict:
    """Start a render only when the user requests one, returning a job handle.

    Uses current renderer/view, vfb:false, and the common job result API.
    Cancellation is not a forced renderer interrupt; use the renderer's Cancel UI.
    """
    if not 1 <= width <= 32768 or not 1 <= height <= 32768:
        raise ValueError('Render dimensions must be 1–32768')
    output = ' outputFile:' + ms_string(output_path.replace('\\', '/')) if output_path else ''
    return max_job_submit(f'local bmp = render outputWidth:{width} outputHeight:{height}{output} vfb:false; '
                          'if bmp == undefined do throw "Render returned no bitmap"; close bmp; "Render completed"', 'Render')


@mcp.tool()
@run_in_thread
def max_job_status(job_id: str) -> dict:
    """Read job state/progress without sending anything to busy Max."""
    return jobs.status(job_id)


@mcp.tool()
@run_in_thread
def max_job_result(job_id: str, offset: int = 0, limit: int = 16000) -> dict:
    """Read a completed job's output/error, paginated in characters."""
    return jobs.result(job_id, offset, limit)


@mcp.tool()
@run_in_thread
def max_job_list() -> dict:
    """List jobs owned by this MCP server session without contacting Max."""
    with jobs.lock:
        return {'jobs': [jobs.status(jid) for jid in jobs.jobs]}


@mcp.tool()
@run_in_thread
def max_job_cancel(job_id: str) -> dict:
    """Request cooperative cancellation; never kill Max or claim a running job stopped.

    Before execution the job skips its body; during execution the script must
    check mcpJobCheckCancel(). Blocking third-party render/sim calls may ignore it.
    """
    return jobs.cancel(job_id)


@mcp.tool()
@run_in_thread
def max_job_wait(job_id: str, timeout_seconds: float = 5) -> dict:
    """Wait at most 30 seconds for completion; does not occupy the Max socket."""
    if not 0 <= timeout_seconds <= 30:
        raise ValueError('timeout_seconds must be 0–30')
    deadline = time.monotonic() + timeout_seconds
    while True:
        result = jobs.status(job_id)
        if result['state'] in jobs.TERMINAL or time.monotonic() >= deadline:
            return result
        time.sleep(min(.1, max(0, deadline-time.monotonic())))


@mcp.tool()
@run_in_thread
def max_job_forget(job_id: str, force: bool = False) -> dict:
    """Delete this session's completed job output and release its history slot.

    force=True also releases a job stuck in the 'unknown' state (scheduling result
    ambiguous), freeing the Max instance for normal commands again. Use it ONLY if
    you verified in Max that nothing is running; otherwise a live job keeps writing.
    """
    return jobs.forget(job_id, force)
