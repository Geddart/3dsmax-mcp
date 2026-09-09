import ctypes
import ctypes.wintypes as wintypes
import json
import math
import os
import threading
import time
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4
from .pipe_io import transfer

DEFAULT_TIMEOUT = 120.0
DEFAULT_PIPE_NAME = r"\\.\pipe\3dsmax-mcp"
MCP_PIPE_ENV = "MCP_MAX_PIPE"

# Win32 constants for named pipe
_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
_GENERIC_READ = 0x80000000
_GENERIC_WRITE = 0x40000000
_OPEN_EXISTING = 3
_ERROR_FILE_NOT_FOUND = 2
_ERROR_PATH_NOT_FOUND = 3
_ERROR_ACCESS_DENIED = 5
_ERROR_BROKEN_PIPE = 109
_ERROR_SEM_TIMEOUT = 121
_ERROR_PIPE_BUSY = 231

# CreateFileW returns HANDLE; set proper return type for correct comparison
_kernel32.CreateFileW.restype = wintypes.HANDLE
_kernel32.CreateFileW.argtypes = [
    wintypes.LPCWSTR,
    wintypes.DWORD,
    wintypes.DWORD,
    wintypes.LPVOID,
    wintypes.DWORD,
    wintypes.DWORD,
    wintypes.HANDLE,
]
_kernel32.WaitNamedPipeW.restype = wintypes.BOOL
_kernel32.WaitNamedPipeW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD]
_kernel32.WriteFile.restype = wintypes.BOOL
_kernel32.WriteFile.argtypes = [
    wintypes.HANDLE,
    wintypes.LPCVOID,
    wintypes.DWORD,
    ctypes.POINTER(wintypes.DWORD),
    wintypes.LPVOID,
]
_kernel32.ReadFile.restype = wintypes.BOOL
_kernel32.ReadFile.argtypes = [
    wintypes.HANDLE,
    wintypes.LPVOID,
    wintypes.DWORD,
    ctypes.POINTER(wintypes.DWORD),
    wintypes.LPVOID,
]
_kernel32.PeekNamedPipe.restype = wintypes.BOOL
_kernel32.PeekNamedPipe.argtypes = [
    wintypes.HANDLE,
    wintypes.LPVOID,
    wintypes.DWORD,
    ctypes.POINTER(wintypes.DWORD),
    ctypes.POINTER(wintypes.DWORD),
    ctypes.POINTER(wintypes.DWORD),
]
_kernel32.CloseHandle.restype = wintypes.BOOL
_kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
_INVALID_HANDLE = wintypes.HANDLE(-1).value


class AmbiguousMaxInstanceError(ConnectionError):
    """Raised when multiple live Max native bridges exist and none is claimed."""


class MaxBridgeError(Exception):
    """Raised when the native bridge returns a structured error response."""

    def __init__(self, message: str, response: dict[str, Any]) -> None:
        self.bridge_message = message
        self.bridge_response = response
        super().__init__(f"MAXScript error: {message}")


class MaxClient:
    """Client that sends commands to a native 3ds Max named pipe."""

    def __init__(
        self,
        timeout: float = DEFAULT_TIMEOUT,
        transport: str = "auto",
        pipe_name: str = DEFAULT_PIPE_NAME,
    ):
        if transport not in ('auto', 'pipe'):
            raise ValueError('Only native named pipes are supported; TCP/slots were removed')
        self.timeout = timeout
        self.transport = transport
        self.pipe_name = pipe_name
        self._pipe_handle: Optional[int] = None
        self._selected_pipe_name: Optional[str] = None
        self._pipe_lock = threading.Lock()
        self._local = threading.local()

    def clear_last_response(self) -> None:
        """Clear thread-local metadata from the previous command."""
        self._local.last_response = None
        self._local.last_error = None

    def get_last_transport(self) -> dict[str, Any] | None:
        """Return compact transport metadata from the last command on this thread."""
        response = getattr(self._local, "last_response", None)
        if isinstance(response, dict):
            meta = response.get("meta") if isinstance(response.get("meta"), dict) else {}
            return {
                "transport": meta.get("transport"),
                "requested_transport": meta.get("requestedTransport"),
                "request_id": response.get("requestId"),
                "protocol_version": meta.get("protocolVersion"),
                "client_round_trip_ms": meta.get("clientRoundTripMs"),
                "fallback_error": meta.get("fallbackError"),
            }
        error = getattr(self._local, "last_error", None)
        if isinstance(error, dict):
            return error
        return None

    @property
    def native_available(self) -> bool:
        """Check whether the native C++ bridge is currently available."""
        try:
            return self._probe_pipe_available(self._resolve_pipe_name())
        except (ConnectionError, TimeoutError):
            return False

    def _config_dir(self) -> Path:
        root = os.environ.get("LOCALAPPDATA")
        if root:
            return Path(root) / "3dsmax-mcp"
        return Path.home() / "AppData" / "Local" / "3dsmax-mcp"

    def _load_instance(self, path: Path) -> dict[str, Any] | None:
        try:
            data = json.loads(path.read_text("utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        if not isinstance(data, dict) or not isinstance(data.get("pipe"), str):
            return None
        return data

    def _active_instance(self) -> dict[str, Any] | None:
        return self._load_instance(self._config_dir() / "active_instance.json")

    def _live_instances(self) -> list[dict[str, Any]]:
        instances_dir = self._config_dir() / "instances"
        try:
            paths = sorted(instances_dir.glob("*.json"))
        except OSError:
            return []

        live: list[dict[str, Any]] = []
        for path in paths:
            data = self._load_instance(path)
            if data and self._probe_pipe_available(data["pipe"]):
                live.append(data)
        return live

    def _resolve_pipe_name(self) -> str:
        # An explicit session/job target always wins over an environment default.
        if self.pipe_name != DEFAULT_PIPE_NAME:
            return self.pipe_name
        env_pipe = os.environ.get(MCP_PIPE_ENV)
        if env_pipe:
            return env_pipe

        active = self._active_instance()
        if active and self._probe_pipe_available(active["pipe"]):
            return active["pipe"]

        live = self._live_instances()
        if len(live) == 1:
            return live[0]["pipe"]
        if len(live) > 1:
            labels = ", ".join(
                f"{item.get('instance_id', 'unknown')} pid={item.get('pid', '?')}"
                for item in live
            )
            raise AmbiguousMaxInstanceError(
                "Multiple 3ds Max MCP instances are running. "
                "In the target 3ds Max window, run MCP > MCP Claim This Max. "
                f"Available instances: {labels}"
            )

        return DEFAULT_PIPE_NAME

    def _probe_pipe_available(self, pipe_name: str | None = None) -> bool:
        """Best-effort probe that treats a busy pipe as available."""
        pipe_name = pipe_name or self.pipe_name
        if _kernel32.WaitNamedPipeW(pipe_name, 0):
            return True
        wait_err = ctypes.get_last_error()
        if wait_err in (_ERROR_SEM_TIMEOUT, _ERROR_PIPE_BUSY, _ERROR_ACCESS_DENIED):
            return True
        return False

    def _close_pipe_handle(self) -> None:
        handle = self._pipe_handle
        if handle not in (None, 0, _INVALID_HANDLE):
            _kernel32.CloseHandle(handle)
        self._pipe_handle = None

    def _ensure_pipe_handle(self, deadline: float, pipe_name: str) -> int:
        handle = self._pipe_handle
        if handle not in (None, 0, _INVALID_HANDLE):
            return handle

        connect_grace = min(deadline, time.perf_counter() + .5)
        while True:
            handle = _kernel32.CreateFileW(
                pipe_name,
                _GENERIC_READ | _GENERIC_WRITE,
                0,
                None,
                _OPEN_EXISTING,
                0x40000000,  # FILE_FLAG_OVERLAPPED: enforce read AND write deadlines
                None,
            )
            if handle != _INVALID_HANDLE:
                self._pipe_handle = handle
                return handle

            err = ctypes.get_last_error()
            if err in (_ERROR_FILE_NOT_FOUND, _ERROR_PATH_NOT_FOUND):
                if time.perf_counter() < connect_grace:
                    time.sleep(.01)
                    continue
                raise ConnectionError(
                    f"Named pipe {pipe_name} not found. "
                    "Is the MCP Bridge plugin loaded in 3ds Max?"
                )
            if err != _ERROR_PIPE_BUSY:
                raise ConnectionError(f"Failed to open pipe: Win32 error {err}")

            remaining_ms = int((deadline - time.perf_counter()) * 1000)
            if remaining_ms <= 0:
                raise TimeoutError(
                    f"Timed out waiting for named pipe {pipe_name} after "
                    f"{self.timeout}s."
                )

            wait_ms = min(remaining_ms, 250)
            if _kernel32.WaitNamedPipeW(pipe_name, wait_ms):
                continue
            wait_err = ctypes.get_last_error()
            if wait_err in (_ERROR_FILE_NOT_FOUND, _ERROR_PATH_NOT_FOUND):
                if time.perf_counter() < connect_grace:
                    time.sleep(.01)
                    continue
                raise ConnectionError(
                    f"Named pipe {pipe_name} disappeared while waiting."
                )
            if wait_err in (_ERROR_SEM_TIMEOUT, _ERROR_PIPE_BUSY):
                continue
            raise ConnectionError(
                f"Failed waiting for named pipe {self.pipe_name}: "
                f"Win32 error {wait_err}"
            )

    def send_command(
        self,
        command: str,
        cmd_type: str = "maxscript",
        timeout: Optional[float] = None,
    ) -> dict[str, Any]:
        """Send a command to 3ds Max and return the parsed JSON response."""
        pipe_name = self._resolve_pipe_name()
        if not getattr(self, '_async_scheduler', False) and cmd_type != 'native:render_cancel':
            from .async_jobs import busy_job
            active = busy_job(pipe_name)
            if active:
                raise RuntimeError(f'Max is reserved by async job {active}; use max_job_status/result or max_ui_*')
        effective_timeout = self.timeout if timeout is None else timeout
        if not math.isfinite(effective_timeout) or effective_timeout <= 0:
            raise ValueError('timeout must be finite and positive')
        request_id = uuid4().hex
        started_at = time.perf_counter()
        transport_used = self.transport
        fallback_error: str | None = None
        self.clear_last_response()

        request = json.dumps({
            "command": command,
            "type": cmd_type,
            "requestId": request_id,
            "protocolVersion": 2,
        }, ensure_ascii=True)

        transport_used = "namedpipe"
        try:
            response_data = self._send_via_pipe(request, effective_timeout, pipe_name=pipe_name)
            response = self._parse_response(response_data, request_id, started_at)
        except Exception as exc:
            self._local.last_error = {
                "transport": transport_used,
                "requested_transport": self.transport,
                "request_id": request_id,
                "error": str(exc),
                "fallback_error": fallback_error,
            }
            raise

        meta = response.setdefault("meta", {})
        meta.setdefault("transport", transport_used)
        meta.setdefault("requestedTransport", self.transport)
        if fallback_error:
            meta.setdefault("fallbackError", fallback_error)
        self._local.last_response = response
        return response

    # ── Named Pipe transport ─────────────────────────────────────
    def _send_via_pipe(self, request: str, timeout: float, *, pipe_name: str | None = None) -> bytes:
        deadline = time.perf_counter() + timeout
        data = (request + "\n").encode("utf-8")
        pipe_name = pipe_name or self._resolve_pipe_name()

        if not self._pipe_lock.acquire(timeout=max(0, deadline-time.perf_counter())):
            raise TimeoutError('Timed out waiting for the MCP connection lock; request not sent')
        try:
            if self._selected_pipe_name != pipe_name:
                self._close_pipe_handle()
                self._selected_pipe_name = pipe_name

            handle = self._ensure_pipe_handle(deadline, pipe_name)
            try:
                total_written = 0
                while total_written < len(data):
                    ok, err, written = transfer(_kernel32.WriteFile, handle,
                                                data[total_written:], len(data)-total_written, deadline)
                    total_written += written
                    if not ok:
                        if err == _ERROR_BROKEN_PIPE:
                            raise BrokenPipeError("Pipe closed while writing request.")
                        raise ConnectionError(
                            f"Failed writing to pipe: Win32 error {err}"
                        )
                    if written == 0:
                        raise ConnectionError(
                            "Pipe write returned 0 bytes written."
                        )

                response_data = bytearray()
                buf = ctypes.create_string_buffer(65536)
                while True:
                    if time.perf_counter() >= deadline:
                        self._close_pipe_handle()
                        raise TimeoutError(
                            f"Timed out waiting for named pipe response after "
                            f"{timeout}s."
                        )

                    ok, err, bytes_read = transfer(_kernel32.ReadFile, handle, buf, len(buf), deadline)
                    if bytes_read > 0:
                        response_data.extend(buf.raw[:bytes_read])
                        if b"\n" in response_data:
                            return bytes(response_data)

                    if not ok:
                        if err == _ERROR_BROKEN_PIPE:
                            raise BrokenPipeError(
                                "Pipe closed while reading response."
                            )
                        raise ConnectionError(
                            f"Failed reading from pipe: Win32 error {err}"
                        )

                    if bytes_read == 0:
                        raise BrokenPipeError(
                            "Pipe closed before response terminator."
                        )
            except BaseException:
                # Once WriteFile is attempted its outcome may be uncertain, even
                # if Win32 reports zero transferred bytes. Never replay it.
                self._close_pipe_handle()
                raise
        finally:
            self._pipe_lock.release()

    # ── Response parsing (shared) ────────────────────────────────
    def _parse_response(
        self, response_data: bytes, request_id: str, started_at: float
    ) -> dict[str, Any]:
        # Strip UTF-8 BOM if present
        if response_data.startswith(b'\xef\xbb\xbf'):
            response_data = response_data[3:]
        response_str = response_data.decode("utf-8", errors="replace").strip()

        if not response_str:
            raise RuntimeError("Empty response from 3ds Max")

        response = json.loads(response_str)
        response_request_id = response.get("requestId")
        if response_request_id not in (None, "", request_id):
            raise RuntimeError(
                f"Mismatched response requestId: expected {request_id}, got {response_request_id}"
            )

        response["requestId"] = request_id
        meta = response.get("meta")
        if not isinstance(meta, dict):
            meta = {}
            response["meta"] = meta
        meta.setdefault(
            "clientRoundTripMs",
            round((time.perf_counter() - started_at) * 1000.0, 3),
        )

        if not response.get("success", False):
            error_msg = response.get("error", "Unknown error")
            raise MaxBridgeError(str(error_msg), response)

        return response


class MaxClientManager(MaxClient):
    """Session-local native target selection; no numbered slots or TCP fallback."""

    def list_instances(self):
        live = sorted(self._live_instances(), key=lambda item: int(item.get('pid', 0)))
        try:
            active = self._resolve_pipe_name()
        except AmbiguousMaxInstanceError:
            active = None
        return [dict(item, active=item['pipe'] == active) for item in live]

    def select_instance(self, instance_id=''):
        if not instance_id:
            with self._pipe_lock:
                self._close_pipe_handle()
                self.pipe_name = DEFAULT_PIPE_NAME
            return {'selection': 'automatic'}
        matches = [item for item in self._live_instances() if item.get('instance_id') == instance_id]
        if len(matches) != 1:
            raise ValueError('Instance is absent or ambiguous; call list_max_instances first')
        with self._pipe_lock:
            self._close_pipe_handle()
            self.pipe_name = matches[0]['pipe']
        return dict(matches[0], active=True)
