"""Native Max instance discovery and session-local targeting; no numbered slots."""
from ..server import mcp, client

@mcp.tool()
def list_max_instances() -> dict:
    """List live native instances with PID, version, pipe and active target; no Max scene request."""
    return {'instances': client.list_instances()}

@mcp.tool()
def set_active_instance(instance_id: str = '') -> dict:
    """Pin this MCP session to a discovered instance_id such as pid-12345.

    Empty string resumes automatic/Claim This Max routing. Does not change other
    clients. Submitted jobs and observed UI tokens retain their original target.
    """
    return client.select_instance(instance_id)
