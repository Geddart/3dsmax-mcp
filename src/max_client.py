import json
import os
import socket
import time
from typing import Any, Optional

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765
DEFAULT_TIMEOUT = 120.0
BASE_PORT = 8765
MAX_SLOTS = 3


class MaxClient:
    """TCP socket client that sends commands to 3ds Max."""

    def __init__(
        self,
        host: str = DEFAULT_HOST,
        port: int = DEFAULT_PORT,
        timeout: float = DEFAULT_TIMEOUT,
    ):
        self.host = host
        self.port = port
        self.timeout = timeout

    def send_command(
        self,
        command: str,
        cmd_type: str = "maxscript",
        timeout: Optional[float] = None,
    ) -> dict[str, Any]:
        """Send a command to 3ds Max via TCP and return the parsed JSON response."""
        effective_timeout = timeout or self.timeout

        request = json.dumps({
            "command": command,
            "type": cmd_type,
        })

        # Create socket and connect
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(effective_timeout)

        try:
            sock.connect((self.host, self.port))

            # Send request with newline delimiter
            sock.sendall((request + "\n").encode("utf-8"))

            # Receive response (read until newline)
            response_data = b""
            while True:
                chunk = sock.recv(4096)
                if not chunk:
                    break
                response_data += chunk
                if b"\n" in response_data:
                    break

            response_str = response_data.decode("utf-8").strip()

            if not response_str:
                raise RuntimeError("Empty response from 3ds Max")

            response = json.loads(response_str)

            if not response.get("success", False):
                error_msg = response.get("error", "Unknown error")
                raise RuntimeError(f"MAXScript error: {error_msg}")

            return response

        except socket.timeout:
            raise TimeoutError(
                f"3ds Max did not respond within {effective_timeout}s. "
                "Is the MCP TCP listener running in 3ds Max?"
            )
        except ConnectionRefusedError:
            raise ConnectionError(
                f"Could not connect to 3ds Max on {self.host}:{self.port}. "
                "Is the MCP TCP listener running in 3ds Max?"
            )
        finally:
            sock.close()


class MaxClientManager:
    """Proxy that routes send_command() to the active MaxClient slot.

    Presents the same send_command() interface as MaxClient so all
    existing tool code works without changes.
    """

    def __init__(
        self,
        host: str = DEFAULT_HOST,
        base_port: int = BASE_PORT,
        max_slots: int = MAX_SLOTS,
        timeout: float = DEFAULT_TIMEOUT,
    ):
        self.host = os.environ.get("MCP_3DSMAX_HOST", host)
        self.base_port = int(os.environ.get("MCP_3DSMAX_PORT", str(base_port)))
        self.max_slots = max_slots
        self.timeout = timeout
        self._active_slot: int = int(os.environ.get("MCP_3DSMAX_SLOT", "1"))
        self._clients: dict[int, MaxClient] = {}

    def _get_client(self, slot: int) -> MaxClient:
        """Get or create a MaxClient for the given slot."""
        if slot not in self._clients:
            port = self.base_port + slot - 1
            self._clients[slot] = MaxClient(
                host=self.host, port=port, timeout=self.timeout
            )
        return self._clients[slot]

    @property
    def active_slot(self) -> int:
        return self._active_slot

    @active_slot.setter
    def active_slot(self, slot: int) -> None:
        if not 1 <= slot <= self.max_slots:
            raise ValueError(f"Slot must be 1-{self.max_slots}, got {slot}")
        self._active_slot = slot

    @property
    def port(self) -> int:
        """Port of the active instance (for backward compat)."""
        return self.base_port + self._active_slot - 1

    def send_command(
        self,
        command: str,
        cmd_type: str = "maxscript",
        timeout: Optional[float] = None,
    ) -> dict[str, Any]:
        """Route to the active slot's MaxClient."""
        return self._get_client(self._active_slot).send_command(
            command, cmd_type=cmd_type, timeout=timeout
        )

    def ping_slot(self, slot: int, timeout: float = 2.0) -> dict:
        """Check if a specific slot is reachable. Returns status dict."""
        port = self.base_port + slot - 1
        try:
            c = MaxClient(host=self.host, port=port, timeout=timeout)
            resp = c.send_command(
                '(local p = (dotNetClass "System.Diagnostics.Process").GetCurrentProcess(); p.Id as string)',
                timeout=timeout,
            )
            pid = resp.get("result", "unknown")
            return {"slot": slot, "port": port, "status": "running", "pid": pid}
        except (ConnectionError, TimeoutError, OSError, RuntimeError):
            return {"slot": slot, "port": port, "status": "offline", "pid": None}

    def list_instances(self) -> list[dict]:
        """Ping all slots and return their status."""
        results = []
        for slot in range(1, self.max_slots + 1):
            info = self.ping_slot(slot)
            info["active"] = slot == self._active_slot
            results.append(info)
        return results
