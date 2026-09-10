"""Native Max instance discovery and process-local targeting; no numbered slots."""
from ..server import mcp, client

@mcp.tool()
def list_max_instances() -> dict:
    """List live native instances with PID, pipe, start time, claim and selection flags.

    Instances whose process is gone are dropped and their stale records deleted.
    Sends nothing to 3ds Max.
    """
    return client.list_max_instances()

@mcp.tool()
def select_max_instance(pid: int) -> dict:
    """Bind this MCP process to a live Max PID until explicitly changed or released.

    Does not change other clients. Submitted jobs and observed UI tokens retain
    their original target.
    """
    return client.select_max_instance(pid)

@mcp.tool()
def get_selected_max_instance() -> dict:
    """Read this MCP process's target, its source and availability without switching it."""
    return client.get_selected_max_instance()

@mcp.tool()
def release_max_instance() -> dict:
    """Release the pinned target; routing returns to the claimed or single live instance."""
    return client.release_max_instance()
