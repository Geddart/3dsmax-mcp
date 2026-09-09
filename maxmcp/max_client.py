import ctypes
import ctypes.wintypes as wintypes
import json
import math
import os
import re
import threading
import time
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4
from .pipe_io import transfer
from .pid_fence import denied_pids, fence_reason, unmatched_pids

DEFAULT_TIMEOUT = 120.0
MCP_PIPE_ENV = "MCP_MAX_PIPE"
# Per-process pipe published by the native bridge; the old shared
# \\.\pipe\3dsmax-mcp name is never used, so a stale bridge in a production
# Max can no longer catch commands meant for a selected instance.
PIPE_PREFIX = r"\\.\pipe\3dsmax-mcp-pid-"

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
_kernel32.CloseHandle.restype = wintypes.BOOL
_kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
_kernel32.OpenProcess.restype = wintypes.HANDLE
_kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
_kernel32.GetExitCodeProcess.restype = wintypes.BOOL
_kernel32.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
_INVALID_HANDLE = wintypes.HANDLE(-1).value
_PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
_STILL_ACTIVE = 259
_ERROR_INVALID_PARAMETER = 87


def _process_alive(pid: int) -> bool:
    """Report whether a PID still exists; unknown/denied processes count as alive."""
    if not isinstance(pid, int) or isinstance(pid, bool) or pid <= 0:
        return False
    handle = _kernel32.OpenProcess(_PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not handle:
        # Only "no such process" is proof of death; access denied is not.
        return ctypes.get_last_error() != _ERROR_INVALID_PARAMETER
    try:
        code = wintypes.DWORD()
        if not _kernel32.GetExitCodeProcess(handle, ctypes.byref(code)):
            return True
        return code.value == _STILL_ACTIVE
    finally:
        _kernel32.CloseHandle(handle)


class PipeNotConnectedError(ConnectionError):
    """Raised before a single byte of the request was written to the pipe.

    Every raise site below the first `WriteFile` uses a different exception, so
    callers such as `maxmcp.async_jobs.is_provably_unsent` can classify on type
    instead of parsing message text.
    """


class AmbiguousMaxInstanceError(ConnectionError):
    """Raised when multiple live Max native bridges exist and none is claimed."""


class NoMaxInstanceError(ConnectionError):
    """Raised when no live Max instance publishes a native bridge pipe."""


class ProtectedMaxInstanceError(ConnectionError):
    """Raised when the resolvable Max is fenced off by the operator.

    The fence covers every tool, not just ``max_ui_*``: routing a scene
    command into a production Max is exactly what protected_pids.json exists
    to prevent, so resolution fails closed rather than picking that Max up as
    the last instance standing.
    """


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
        pipe_name: str = "",
    ):
        if transport not in ('auto', 'pipe'):
            raise ValueError('Only native named pipes are supported; TCP/slots were removed')
        self.timeout = timeout
        self.transport = transport
        self.pipe_name = pipe_name
        self._pipe_handle: Optional[int] = None
        self._selected_pipe_name: Optional[str] = None
        self._bound_target: dict[str, Any] | None = None
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
            target = meta.get("target") if isinstance(meta.get("target"), dict) else {}
            return {
                "transport": meta.get("transport"),
                "requested_transport": meta.get("requestedTransport"),
                "request_id": response.get("requestId"),
                "protocol_version": meta.get("protocolVersion"),
                "client_round_trip_ms": meta.get("clientRoundTripMs"),
                **target,
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

    @staticmethod
    def _target(pipe: str, source: str, pid: Any = None) -> dict[str, Any]:
        """Build the routing metadata carried on every response and error."""
        if not isinstance(pid, int) or isinstance(pid, bool) or pid <= 0:
            match = re.search(r"-pid-(\d+)$", pipe)
            pid = int(match[1]) if match else None
        return {"target_pid": pid, "target_pipe": pipe, "target_source": source}

    @staticmethod
    def _instance_pid(*sources: str | dict[str, Any] | None) -> int | None:
        """Read the PID from an instance record, its pipe name, or its filename."""
        for source in sources:
            if isinstance(source, dict):
                pid = source.get("pid")
                if isinstance(pid, int) and not isinstance(pid, bool) and pid > 0:
                    return pid
                source = source.get("pipe")
            if isinstance(source, str):
                match = re.search(r"pid-(\d+)", source)
                if match:
                    return int(match[1])
        return None

    def _live_instances(self) -> list[dict[str, Any]]:
        """List instances whose process is alive and whose pipe answers.

        Records left behind by a crashed or closed Max are deleted while
        enumerating, so a dead PID can never be routed to or reported.
        """
        instances_dir = self._config_dir() / "instances"
        try:
            paths = sorted(instances_dir.glob("*.json"))
        except OSError:
            return []

        live: list[dict[str, Any]] = []
        for path in paths:
            data = self._load_instance(path)
            pid = self._instance_pid(data, path.name)
            if pid is None:
                # Not attributable to a process: leave it alone rather than
                # deleting a record that may just be mid-write.
                continue
            if not _process_alive(pid):
                try:
                    path.unlink()
                except OSError:
                    pass
                continue
            if data is None:
                continue
            data = {**data, "pid": pid}
            if not self._probe_pipe_available(data["pipe"]):
                # Process is alive but the bridge is not listening (yet); keep
                # the file, it is not stale.
                continue
            try:
                data = {**data, "started": path.stat().st_mtime}
            except OSError:
                pass
            live.append(data)
        return sorted(live, key=lambda item: int(item.get("pid") or 0))

    def _default_target(self) -> dict[str, Any]:
        """Resolve the routing target from claim file / live instances only.

        A protected instance is never routed to, including when it is the last
        one running: closing the dev Max must not silently promote the
        operator's production Max to "the single live instance".
        """
        active = self._active_instance()
        active_pid = self._instance_pid(active)
        if active and active_pid and _process_alive(active_pid) and self._probe_pipe_available(active["pipe"]):
            reason = fence_reason(active_pid, active)
            if reason:
                raise ProtectedMaxInstanceError(
                    f"The claimed 3ds Max instance is protected: {reason}. "
                    "Nothing was routed to it. Claim another Max, or remove the "
                    "fence entry if this instance is no longer production."
                )
            return self._target(active["pipe"], "claimed", active_pid)

        all_live = self._live_instances()
        live = [item for item in all_live if fence_reason(item.get("pid"), item) is None]
        if len(live) == 1:
            return self._target(live[0]["pipe"], "single", live[0].get("pid"))
        if len(live) > 1:
            labels = ", ".join(
                f"pid={item.get('pid', '?')}"
                for item in live
            )
            raise AmbiguousMaxInstanceError(
                "Multiple 3ds Max MCP instances are running. "
                "Call select_max_instance(pid), or in the target 3ds Max window "
                "run MCP > MCP Claim This Max. "
                f"Available instances: {labels}"
            )

        protected = [item for item in all_live if fence_reason(item.get("pid"), item)]
        if protected:
            labels = ", ".join(
                f"pid={item.get('pid', '?')} ({fence_reason(item.get('pid'), item)})"
                for item in protected
            )
            raise ProtectedMaxInstanceError(
                "The only live 3ds Max instances are protected and will not be "
                f"routed to ({labels}). Start an unprotected Max, or remove the "
                "entry from protected_pids.json / MCP_UI_DENY_PIDS."
            )

        raise NoMaxInstanceError(
            "No live 3ds Max instance with the native bridge found. "
            "Start 3ds Max with the MCP Bridge plugin loaded, then call "
            "list_max_instances to confirm it registered."
        )

    def _resolve_target(self) -> dict[str, Any]:
        """Pick the target for this request; never falls back to a shared pipe."""
        if self._bound_target is not None:
            return dict(self._bound_target)
        # An explicit session/job target always wins over an environment default.
        if self.pipe_name:
            return self._target(self.pipe_name, "explicit")
        env_pipe = os.environ.get(MCP_PIPE_ENV)
        if env_pipe:
            return self._target(env_pipe, "explicit")
        return self._default_target()

    def _resolve_pipe_name(self) -> str:
        return self._resolve_target()["target_pipe"]

    def selected_pid(self) -> int | None:
        """PID this client currently routes to, or None if nothing is resolvable.

        Resolution only; nothing is sent to 3ds Max.
        """
        try:
            return self._resolve_target()["target_pid"]
        except (ConnectionError, TimeoutError):
            return None

    # ── Instance selection API ───────────────────────────────────
    def list_max_instances(self) -> dict[str, Any]:
        """List live instances, flagging the claimed and the selected one."""
        active = self._active_instance()
        claimed_pipe = active["pipe"] if active else None
        selected_pipe = self._bound_target["target_pipe"] if self._bound_target else None
        instances = self._live_instances()
        return {
            "instances": [
                {
                    **item,
                    "claimed": item["pipe"] == claimed_pipe,
                    "selected": item["pipe"] == selected_pipe,
                    "protected": fence_reason(item.get("pid"), item) is not None,
                }
                for item in instances
            ],
            # The fence is per-PID and lapses when the protected Max restarts
            # (Windows recycles the number). `lapsed_pids` surfaces entries that
            # match nothing live, so the lapse is visible rather than silent.
            "protected_fence": {
                "pids": sorted(denied_pids()),
                "lapsed_pids": unmatched_pids(item.get("pid") for item in instances),
            },
        }

    def get_selected_max_instance(self) -> dict[str, Any]:
        """Report the current target without switching or sending anything."""
        try:
            target = self._resolve_target()
        except (ConnectionError, TimeoutError) as exc:
            return {
                "target_pid": None,
                "target_pipe": None,
                "target_source": None,
                "pinned": False,
                "available": False,
                "reason": str(exc),
            }
        return {
            **target,
            "pinned": self._bound_target is not None,
            "available": self._probe_pipe_available(target["target_pipe"]),
            # An explicit pipe/env target bypasses fence-aware resolution on
            # purpose; report the fence state so that override stays visible.
            "protected": fence_reason(target.get("target_pid")) is not None,
        }

    def select_max_instance(self, pid: int) -> dict[str, Any]:
        """Bind this MCP process to a live Max PID until changed or released."""
        if isinstance(pid, bool) or not isinstance(pid, int) or pid <= 0:
            raise ValueError("pid must be a positive process ID")
        record = next(
            (item for item in self._live_instances() if self._instance_pid(item) == pid),
            None,
        )
        if record is None:
            raise NoMaxInstanceError(
                f"3ds Max PID {pid} is not a live registered MCP instance; "
                "selection was not changed. Call list_max_instances for live PIDs."
            )
        pipe = record["pipe"]
        reason = fence_reason(pid, record)
        if reason:
            raise ProtectedMaxInstanceError(
                f"3ds Max PID {pid} is protected: {reason}. Selection was not "
                "changed and nothing was sent to it."
            )
        if not _process_alive(pid) or not self._probe_pipe_available(pipe):
            raise ConnectionError(
                f"3ds Max PID {pid} is unavailable; selection was not changed. "
                "Call list_max_instances for live PIDs."
            )
        with self._pipe_lock:
            self._close_pipe_handle()
            self._selected_pipe_name = None
            self._bound_target = self._target(pipe, "selected", pid)
            return {**self._bound_target, "pinned": True, "available": True}

    def release_max_instance(self) -> dict[str, Any]:
        """Drop the pinned target; routing returns to claim/single resolution."""
        with self._pipe_lock:
            self._close_pipe_handle()
            self._selected_pipe_name = None
            self._bound_target = None
        return {"target_pid": None, "target_pipe": None, "target_source": None, "pinned": False}

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
                raise PipeNotConnectedError(
                    f"Named pipe {pipe_name} not found. "
                    "Is the MCP Bridge plugin loaded in 3ds Max?"
                )
            if err != _ERROR_PIPE_BUSY:
                raise PipeNotConnectedError(f"Failed to open pipe: Win32 error {err}")

            remaining_ms = int((deadline - time.perf_counter()) * 1000)
            if remaining_ms <= 0:
                raise PipeNotConnectedError(
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
                raise PipeNotConnectedError(
                    f"Named pipe {pipe_name} disappeared while waiting."
                )
            if wait_err in (_ERROR_SEM_TIMEOUT, _ERROR_PIPE_BUSY):
                continue
            raise PipeNotConnectedError(
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
        target = self._resolve_target()
        pipe_name = target["target_pipe"]
        if not getattr(self, '_async_scheduler', False) and cmd_type != 'native:render_cancel':
            from .async_jobs import busy_job
            active = busy_job(pipe_name)
            if active:
                raise RuntimeError(
                    f'Max is reserved by async job {active}; use max_job_status/result or max_ui_*. '
                    f'If that job is stuck in an unknown state and you verified in Max that nothing '
                    f"is running, release it with max_job_forget('{active}', force=True).")
        effective_timeout = self.timeout if timeout is None else timeout
        if not math.isfinite(effective_timeout) or effective_timeout <= 0:
            raise ValueError('timeout must be finite and positive')
        request_id = uuid4().hex
        started_at = time.perf_counter()
        transport_used = "namedpipe"
        self.clear_last_response()

        request = json.dumps({
            "command": command,
            "type": cmd_type,
            "requestId": request_id,
            "protocolVersion": 2,
        }, ensure_ascii=True)

        try:
            response_data = self._send_via_pipe(request, effective_timeout, pipe_name=pipe_name)
            response = self._parse_response(response_data, request_id, started_at)
        except Exception as exc:
            self._local.last_error = {
                "transport": transport_used,
                "requested_transport": self.transport,
                "request_id": request_id,
                "error": str(exc),
                **target,
            }
            raise

        meta = response.setdefault("meta", {})
        meta.setdefault("transport", transport_used)
        meta.setdefault("requestedTransport", self.transport)
        meta.setdefault("target", dict(target))
        self._local.last_response = response
        return response

    # ── Named Pipe transport ─────────────────────────────────────
    def _send_via_pipe(self, request: str, timeout: float, *, pipe_name: str | None = None) -> bytes:
        deadline = time.perf_counter() + timeout
        data = (request + "\n").encode("utf-8")
        pipe_name = pipe_name or self._resolve_pipe_name()

        if not self._pipe_lock.acquire(timeout=max(0, deadline-time.perf_counter())):
            raise PipeNotConnectedError(
                'Timed out waiting for the MCP connection lock; request not sent')
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
    """Process-local native target selection; no numbered slots or TCP fallback.

    Selection lives on MaxClient itself (list/select/get_selected/release_max_instance);
    this subclass only names the process-wide instance created by the server.
    """
