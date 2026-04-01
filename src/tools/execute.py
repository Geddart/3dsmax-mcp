from typing import Optional

from ..server import mcp, client


@mcp.tool()
def execute_maxscript(code: str = "", command: str = "", slot: Optional[int] = None) -> str:
    """Execute arbitrary MAXScript code in 3ds Max and return the result.

    The code is run via MAXScript's execute() function. The return value
    is the string representation of whatever the last expression evaluates to.

    This is NOT a shell — do not send PowerShell/bash commands here.

    Examples:
        execute_maxscript("objects.count")
        execute_maxscript("sphere radius:25 pos:[0,0,0]")
        execute_maxscript("for o in selection collect o.name", slot=2)

    Args:
        code: MAXScript code to execute.
        command: Alias for code (use either one).
        slot: Target instance slot (1-3). If omitted, uses the active instance.
              Use this for parallel control of multiple 3ds Max instances.
    """
    script = code or command
    if not script:
        return "Error: provide MAXScript code in the 'code' parameter"
    response = client.send_command(script, cmd_type="maxscript", slot=slot)
    return response.get("result", "")
