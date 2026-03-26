from typing import Optional

from ..server import mcp, client


@mcp.tool()
def execute_maxscript(code: str, slot: Optional[int] = None) -> str:
    """Execute arbitrary MAXScript code in 3ds Max and return the result.

    The code is run via MAXScript's execute() function. The return value
    is the string representation of whatever the last expression evaluates to.

    Args:
        code: MAXScript code to execute.
        slot: Target instance slot (1-3). If omitted, uses the active instance.
              Use this for parallel control of multiple 3ds Max instances.

    Examples:
        execute_maxscript("objects.count")
        execute_maxscript("sphere radius:25 pos:[0,0,0]")
        execute_maxscript("for o in selection collect o.name", slot=2)
    """
    response = client.send_command(code, cmd_type="maxscript", slot=slot)
    return response.get("result", "")
