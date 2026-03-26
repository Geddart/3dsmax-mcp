"""MCP tools for managing multiple 3ds Max instances."""

import json

from ..server import mcp, client


@mcp.tool()
def list_max_instances() -> str:
    """List all available 3ds Max MCP instances (slots 1-3).

    Pings each slot port to check if a 3ds Max instance is listening.
    Shows which slot is currently active for command routing.

    Returns JSON array with slot, port, status (running/offline), pid, and active flag.
    """
    instances = client.list_instances()
    return json.dumps(instances, indent=2)


@mcp.tool()
def set_active_instance(slot: int) -> str:
    """Switch which 3ds Max instance receives commands.

    Args:
        slot: Instance slot number (1, 2, or 3).
              Slot 1 = port 8765, Slot 2 = port 8766, Slot 3 = port 8767.

    All subsequent tool calls will be routed to this instance until
    changed again. The instance must be running (use list_max_instances
    to check).
    """
    if not 1 <= slot <= client.max_slots:
        return json.dumps({
            "success": False,
            "error": f"Slot must be 1-{client.max_slots}, got {slot}",
        })

    status = client.ping_slot(slot)
    if status["status"] == "offline":
        return json.dumps({
            "success": False,
            "error": f"Slot {slot} (port {status['port']}) is not responding. "
                     f"Start the MCP server in that 3ds Max instance first.",
        })

    client.active_slot = slot
    return json.dumps({
        "success": True,
        "message": f"Switched to slot {slot} (port {status['port']}, PID {status['pid']})",
        "slot": slot,
        "port": status["port"],
        "pid": status["pid"],
    })
