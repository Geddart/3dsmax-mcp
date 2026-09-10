"""Bridge/transport status tools for the live 3ds Max connection."""

from __future__ import annotations

import json

from ..server import mcp, client


@mcp.tool()
def get_bridge_status() -> str:
    """Ping the MCP bridge for protocol/transport metadata.

    Use when: a tool failed with a connection/transport/claim error and you need to diagnose.
    Not when: starting a session or before every task — prefer query_scene for scene work.
    """
    response = client.send_command("", cmd_type="ping", timeout=5.0)

    payload = json.loads(response.get("result", "{}"))
    payload["requestId"] = response.get("requestId")
    payload["meta"] = response.get("meta", {})
    payload["connected"] = True
    payload["legacyTransport"] = False
    return json.dumps(payload)
