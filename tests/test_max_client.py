import unittest
import json
import tempfile
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import MagicMock, patch

from maxmcp.max_client import (
    AmbiguousMaxInstanceError,
    MaxBridgeError,
    MaxClient,
    NoMaxInstanceError,
    PipeNotConnectedError,
    ProtectedMaxInstanceError,
    _process_alive,
)


@contextmanager
def _instance_dir(*pids):
    """Temporary LOCALAPPDATA root holding one instance record per PID."""
    with tempfile.TemporaryDirectory() as tmp:
        instances = Path(tmp) / "3dsmax-mcp" / "instances"
        instances.mkdir(parents=True)
        for pid in pids:
            (instances / f"pid-{pid}.json").write_text(json.dumps(_instance(pid)), "utf-8")
        yield tmp


def _instance(pid, **extra):
    return {
        'instance_id': f'pid-{pid}',
        'pid': pid,
        'pipe': fr'\\.\pipe\3dsmax-mcp-pid-{pid}',
        **extra,
    }


class MaxClientTests(unittest.TestCase):
    def test_explicit_instance_wins_over_environment_default(self):
        with patch.dict('os.environ', {'MCP_MAX_PIPE': 'pipe-env'}):
            self.assertEqual(MaxClient(pipe_name='pipe-selected')._resolve_pipe_name(), 'pipe-selected')
            self.assertEqual(MaxClient()._resolve_pipe_name(), 'pipe-env')

    def test_request_resolves_target_once_and_records_transport_failures(self):
        client = MaxClient()
        targets = [MaxClient._target('pipe-A', 'explicit'), MaxClient._target('pipe-B', 'explicit')]
        with patch.object(client, '_resolve_target', side_effect=targets) as resolve, patch.object(client, '_send_via_pipe', side_effect=TimeoutError('pending')) as send:
            with self.assertRaises(TimeoutError): client.send_command('1')
            resolve.assert_called_once()
            self.assertEqual(send.call_args.kwargs['pipe_name'], 'pipe-A')
            transport = client.get_last_transport()
            self.assertEqual(transport['error'], 'pending')
            self.assertEqual(transport['target_pipe'], 'pipe-A')

    def test_connection_lock_obeys_deadline(self):
        client = MaxClient(pipe_name='pipe-A')
        client._pipe_lock.acquire()
        try:
            with self.assertRaisesRegex(PipeNotConnectedError, 'lock'):
                client._send_via_pipe('{}', .01)
        finally:
            client._pipe_lock.release()

    def test_partial_failed_write_is_never_replayed(self):
        client = MaxClient(pipe_name='pipe-A')
        with patch.object(client, '_ensure_pipe_handle', return_value=123), patch.object(client, '_close_pipe_handle'), patch('maxmcp.max_client.transfer', return_value=(False, 109, 1)) as write:
            with self.assertRaises(ConnectionError): client._send_via_pipe('{}', 1)
            self.assertEqual(write.call_count, 1)

    def test_discovery_probe_does_not_consume_connections(self):
        with patch('maxmcp.max_client._kernel32.WaitNamedPipeW',return_value=True), patch('maxmcp.max_client._kernel32.CreateFileW') as create:
            self.assertTrue(MaxClient()._probe_pipe_available('test-pipe'))
            create.assert_not_called()

    def test_disconnect_after_write_is_not_replayed(self):
        import time
        client=MaxClient(transport='pipe',pipe_name='test-pipe')
        def written(handle,data,count,out,unused):
            out._obj.value=count
            return True
        with patch.object(client,'_ensure_pipe_handle',return_value=123), patch.object(client,'_close_pipe_handle'), patch('maxmcp.max_client._kernel32.WriteFile',side_effect=written) as write, patch('maxmcp.max_client._kernel32.ReadFile',return_value=False), patch('maxmcp.max_client.ctypes.get_last_error',return_value=109):
            with self.assertRaises(ConnectionError): client._send_via_pipe('{}',1)
            self.assertEqual(write.call_count,1)

    def test_send_command_uses_ascii_escaped_json_and_decodes_bom_response(self) -> None:
        fake_socket = MagicMock()
        fake_socket.side_effect = [
            b'\xef\xbb\xbf{"success":true,"result":"ok","error":""}\n',
        ]

        with patch.object(MaxClient, "_send_via_pipe", fake_socket):
            client = MaxClient(timeout=1.0, transport="pipe", pipe_name="test-pipe")
            response = client.send_command('print("Merhaba ğüş")')

        self.assertEqual(response["result"], "ok")
        self.assertIn("requestId", response)
        self.assertIn("meta", response)
        self.assertIn("clientRoundTripMs", response["meta"])
        self.assertEqual(response["meta"]["transport"], "namedpipe")
        self.assertEqual(response["meta"]["requestedTransport"], "pipe")
        self.assertEqual(client.get_last_transport()["transport"], "namedpipe")
        sent = fake_socket.call_args.args[0].encode("utf-8")
        self.assertIn(b'"protocolVersion": 2', sent)
        self.assertIn(b'"requestId": "', sent)
        self.assertIn(b"\\u011f", sent)
        self.assertIn(b"\\u00fc", sent)



    def test_send_command_replaces_invalid_utf8_bytes(self) -> None:
        fake_socket = MagicMock()
        fake_socket.side_effect = [
            b'{"success":true,"result":"bad\xff","error":""}\n',
        ]

        with patch.object(MaxClient, "_send_via_pipe", fake_socket):
            client = MaxClient(timeout=1.0, transport="pipe", pipe_name="test-pipe")
            response = client.send_command("x")

        self.assertEqual(response["result"], "bad\ufffd")

    def test_send_command_rejects_mismatched_request_id(self) -> None:
        fake_socket = MagicMock()
        fake_socket.side_effect = [
            b'{"success":true,"requestId":"wrong","result":"ok","error":"","meta":{}}\n',
        ]

        with patch.object(MaxClient, "_send_via_pipe", fake_socket):
            client = MaxClient(timeout=1.0, transport="pipe", pipe_name="test-pipe")
            with self.assertRaisesRegex(RuntimeError, "Mismatched response requestId"):
                client.send_command("x")

    def test_bridge_error_is_not_runtime_error_fallback_signal(self) -> None:
        client = MaxClient(timeout=1.0, transport="pipe")
        payload = {
            "success": False,
            "requestId": "req",
            "error": '{"type":"NativeError","message":"Ambiguous","code":"AMBIGUOUS","retryable":false}',
            "meta": {},
        }

        with self.assertRaises(MaxBridgeError) as raised:
            client._parse_response(json.dumps(payload).encode("utf-8"), "req", 0.0)

        self.assertNotIsInstance(raised.exception, RuntimeError)
        self.assertEqual(raised.exception.bridge_response["error"], payload["error"])

    def test_send_command_reports_the_routed_target(self) -> None:
        client = MaxClient(timeout=1.0, transport="pipe")
        target = MaxClient._target(r"\\.\pipe\3dsmax-mcp-pid-111", "claimed")
        with (
            patch.object(client, "_resolve_target", return_value=target),
            patch.object(MaxClient, "_send_via_pipe", return_value=b'{"success":true,"result":"ok"}\n'),
        ):
            response = client.send_command("x")

        self.assertEqual(response["meta"]["target"], target)
        transport = client.get_last_transport()
        self.assertEqual(transport["target_pid"], 111)
        self.assertEqual(transport["target_pipe"], target["target_pipe"])
        self.assertEqual(transport["target_source"], "claimed")

    def test_resolve_pipe_uses_active_instance_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config = Path(tmp) / "3dsmax-mcp"
            config.mkdir()
            active = _instance(111)
            (config / "active_instance.json").write_text(json.dumps(active), "utf-8")

            with (
                patch.dict("os.environ", {"LOCALAPPDATA": tmp}, clear=False),
                patch("maxmcp.max_client._process_alive", return_value=True),
                patch.object(MaxClient, "_probe_pipe_available", return_value=True),
            ):
                client = MaxClient()
                self.assertEqual(client._resolve_pipe_name(), active["pipe"])
                self.assertEqual(client._resolve_target()["target_source"], "claimed")
                self.assertEqual(client.selected_pid(), 111)

    def test_resolve_pipe_requires_claim_when_multiple_instances_are_live(self) -> None:
        with _instance_dir(111, 222) as tmp:
            with (
                patch.dict("os.environ", {"LOCALAPPDATA": tmp}, clear=False),
                patch("maxmcp.max_client._process_alive", return_value=True),
                patch.object(MaxClient, "_probe_pipe_available", return_value=True),
            ):
                client = MaxClient()
                with self.assertRaisesRegex(AmbiguousMaxInstanceError, "select_max_instance"):
                    client._resolve_pipe_name()
                self.assertIsNone(client.selected_pid())

    def test_single_live_instance_is_routed_without_a_claim(self) -> None:
        with _instance_dir(111) as tmp:
            with (
                patch.dict("os.environ", {"LOCALAPPDATA": tmp}, clear=False),
                patch("maxmcp.max_client._process_alive", return_value=True),
                patch.object(MaxClient, "_probe_pipe_available", return_value=True),
            ):
                client = MaxClient()
                self.assertEqual(client._resolve_target()["target_source"], "single")
                self.assertEqual(client.selected_pid(), 111)

    def test_missing_instance_never_falls_back_to_the_shared_pipe(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with (
                patch.dict("os.environ", {"LOCALAPPDATA": tmp}, clear=False),
                patch.object(MaxClient, "_probe_pipe_available", return_value=True),
            ):
                client = MaxClient()
                with self.assertRaisesRegex(NoMaxInstanceError, "No live 3ds Max instance"):
                    client._resolve_pipe_name()
                self.assertIsNone(client.selected_pid())
                self.assertFalse(client.native_available)
                with self.assertRaises(NoMaxInstanceError):
                    client.send_command("x")

    def test_stale_instance_files_are_ignored_and_removed(self) -> None:
        with _instance_dir(111, 222) as tmp:
            stale = Path(tmp) / "3dsmax-mcp" / "instances" / "pid-222.json"
            with (
                patch.dict("os.environ", {"LOCALAPPDATA": tmp}, clear=False),
                patch("maxmcp.max_client._process_alive", side_effect=lambda pid: pid == 111),
                patch.object(MaxClient, "_probe_pipe_available", return_value=True),
            ):
                client = MaxClient()
                listed = client.list_max_instances()["instances"]
                self.assertEqual([item["pid"] for item in listed], [111])
                self.assertEqual(client._resolve_target()["target_source"], "single")
            self.assertFalse(stale.exists())

    def test_select_and_release_pin_the_target(self) -> None:
        with _instance_dir(111, 222) as tmp:
            with (
                patch.dict("os.environ", {"LOCALAPPDATA": tmp}, clear=False),
                patch("maxmcp.max_client._process_alive", return_value=True),
                patch.object(MaxClient, "_probe_pipe_available", return_value=True),
            ):
                client = MaxClient()
                selected = client.select_max_instance(222)
                self.assertEqual(selected["target_pid"], 222)
                self.assertEqual(selected["target_source"], "selected")
                self.assertEqual(client.selected_pid(), 222)
                self.assertEqual(client.get_selected_max_instance()["target_source"], "selected")
                self.assertEqual(
                    [item["selected"] for item in client.list_max_instances()["instances"]],
                    [False, True],
                )

                self.assertIsNone(client.release_max_instance()["target_pid"])
                with self.assertRaises(AmbiguousMaxInstanceError):
                    client._resolve_target()

    def test_protected_instance_is_never_the_single_live_target(self) -> None:
        """The fence must cover routing, not only the max_ui_* tools."""
        with _instance_dir(111) as tmp:
            fence = Path(tmp) / "3dsmax-mcp" / "protected_pids.json"
            fence.write_text(json.dumps({"pids": [111]}), "utf-8")
            with (
                patch.dict("os.environ", {"LOCALAPPDATA": tmp}, clear=False),
                patch("maxmcp.max_client._process_alive", return_value=True),
                patch.object(MaxClient, "_probe_pipe_available", return_value=True),
            ):
                client = MaxClient()
                with self.assertRaisesRegex(ProtectedMaxInstanceError, "protected"):
                    client._resolve_target()
                with self.assertRaises(ProtectedMaxInstanceError):
                    client.select_max_instance(111)
                listed = client.list_max_instances()
                self.assertEqual([item["protected"] for item in listed["instances"]], [True])
                self.assertEqual(listed["protected_fence"]["pids"], [111])
                self.assertEqual(listed["protected_fence"]["lapsed_pids"], [])

    def test_protected_claim_is_refused_and_lapsed_entries_are_reported(self) -> None:
        with _instance_dir(111) as tmp:
            config = Path(tmp) / "3dsmax-mcp"
            (config / "active_instance.json").write_text(json.dumps(_instance(111)), "utf-8")
            (config / "protected_pids.json").write_text(
                json.dumps({"pids": [111, 999]}), "utf-8")
            with (
                patch.dict("os.environ", {"LOCALAPPDATA": tmp}, clear=False),
                patch("maxmcp.max_client._process_alive", return_value=True),
                patch.object(MaxClient, "_probe_pipe_available", return_value=True),
            ):
                client = MaxClient()
                with self.assertRaisesRegex(ProtectedMaxInstanceError, "claimed"):
                    client._resolve_target()
                listed = client.list_max_instances()
                # PID 999 was fenced before a restart recycled it: say so.
                self.assertEqual(listed["protected_fence"]["lapsed_pids"], [999])
                self.assertNotIn("max_versions", listed["protected_fence"])

    def test_same_max_version_does_not_fence_the_second_instance(self) -> None:
        """Only the listed PID is fenced: max_version is shared by every Max of a release."""
        with tempfile.TemporaryDirectory() as tmp:
            instances = Path(tmp) / "3dsmax-mcp" / "instances"
            instances.mkdir(parents=True)
            for pid in (111, 222):
                (instances / f"pid-{pid}.json").write_text(
                    json.dumps(_instance(pid, max_version=27000)), "utf-8")
            (Path(tmp) / "3dsmax-mcp" / "protected_pids.json").write_text(
                json.dumps({"pids": [111]}), "utf-8")
            with (
                patch.dict("os.environ", {"LOCALAPPDATA": tmp}, clear=False),
                patch("maxmcp.max_client._process_alive", return_value=True),
                patch.object(MaxClient, "_probe_pipe_available", return_value=True),
            ):
                client = MaxClient()
                target = client._resolve_target()
                self.assertEqual(target["target_pid"], 222)
                self.assertEqual(
                    [item["protected"] for item in client.list_max_instances()["instances"]],
                    [True, False],
                )
                self.assertEqual(client.select_max_instance(222)["target_pid"], 222)

    def test_unprotected_instance_still_routes_beside_a_protected_one(self) -> None:
        with _instance_dir(111, 222) as tmp:
            (Path(tmp) / "3dsmax-mcp" / "protected_pids.json").write_text(
                json.dumps([222]), "utf-8")
            with (
                patch.dict("os.environ", {"LOCALAPPDATA": tmp}, clear=False),
                patch("maxmcp.max_client._process_alive", return_value=True),
                patch.object(MaxClient, "_probe_pipe_available", return_value=True),
            ):
                client = MaxClient()
                target = client._resolve_target()
                self.assertEqual(target["target_pid"], 111)
                self.assertEqual(target["target_source"], "single")

    def test_process_liveness_is_measured_against_real_win32(self) -> None:
        import os
        import subprocess
        import sys

        self.assertTrue(_process_alive(os.getpid()))
        self.assertFalse(_process_alive(0))
        finished = subprocess.Popen([sys.executable, "-c", "pass"])
        finished.wait(timeout=30)
        self.assertFalse(_process_alive(finished.pid))

    def test_select_refuses_a_pid_with_no_live_instance_record(self) -> None:
        """No synthesised pipe: without a record there is nothing to pin to."""
        with _instance_dir(111) as tmp:
            with (
                patch.dict("os.environ", {"LOCALAPPDATA": tmp}, clear=False),
                patch("maxmcp.max_client._process_alive", return_value=True),
                patch.object(MaxClient, "_probe_pipe_available", return_value=True),
            ):
                client = MaxClient()
                with self.assertRaisesRegex(NoMaxInstanceError, "list_max_instances"):
                    client.select_max_instance(222)
                self.assertIsNone(client._bound_target)

    def test_select_rejects_dead_or_invalid_pids(self) -> None:
        client = MaxClient()
        with patch("maxmcp.max_client._process_alive", return_value=False):
            with self.assertRaises(ConnectionError):
                client.select_max_instance(4242)
        for bad in (0, -1, True, "111"):
            with self.assertRaises(ValueError):
                client.select_max_instance(bad)  # type: ignore[arg-type]
        self.assertIsNone(client._bound_target)


class TargetCacheTests(unittest.TestCase):
    """The resolved default target is memoised for a short TTL."""

    def _client(self, ttl=1.5):
        client = MaxClient(timeout=1.0, transport="pipe")
        client._TARGET_CACHE_TTL = ttl
        return client

    @contextmanager
    def _counted_resolution(self, client, *, target=None, side_effect=None):
        """Patch _default_target on the instance and expose the call counter."""
        resolved = target or MaxClient._target('pipe-cached', 'single', 111)
        mock = MagicMock(return_value=resolved, side_effect=side_effect)
        with patch.dict("os.environ", {"MCP_MAX_PIPE": ""}, clear=False):
            with patch.object(client, "_default_target", mock):
                yield mock

    def test_two_calls_within_the_ttl_resolve_once(self) -> None:
        client = self._client()
        with self._counted_resolution(client) as resolve:
            with patch.object(MaxClient, "_probe_pipe_available", return_value=True):
                self.assertTrue(client.native_available)
                first = client._resolve_target()
                self.assertTrue(client.native_available)
                second = client._resolve_target()
        self.assertEqual(resolve.call_count, 1)
        self.assertEqual(first, second)
        self.assertEqual(first["target_pid"], 111)

    def test_cached_target_is_a_copy_callers_cannot_poison(self) -> None:
        client = self._client()
        with self._counted_resolution(client):
            first = client._resolve_target()
            first["target_pid"] = 999
            self.assertEqual(client._resolve_target()["target_pid"], 111)

    def test_ttl_zero_disables_caching(self) -> None:
        client = self._client(ttl=0)
        with self._counted_resolution(client) as resolve:
            client._resolve_target()
            client._resolve_target()
            client._resolve_target()
        self.assertEqual(resolve.call_count, 3)
        self.assertIsNone(client._target_cache)

    def test_failures_are_never_cached(self) -> None:
        client = self._client()
        with self._counted_resolution(
            client, side_effect=NoMaxInstanceError("nothing live")
        ) as resolve:
            for _ in range(3):
                with self.assertRaises(NoMaxInstanceError):
                    client._resolve_target()
        self.assertEqual(resolve.call_count, 3)
        self.assertIsNone(client._target_cache)

    def test_ambiguous_and_protected_semantics_survive_the_cache(self) -> None:
        client = self._client()
        for error in (AmbiguousMaxInstanceError("two"), ProtectedMaxInstanceError("fenced")):
            with self._counted_resolution(client, side_effect=error):
                with self.assertRaises(type(error)):
                    client._resolve_target()
                self.assertFalse(client.native_available)

    def test_select_and_release_invalidate_the_cache(self) -> None:
        with _instance_dir(111) as tmp:
            with (
                patch.dict("os.environ", {"LOCALAPPDATA": tmp, "MCP_MAX_PIPE": ""}, clear=False),
                patch("maxmcp.max_client._process_alive", return_value=True),
                patch.object(MaxClient, "_probe_pipe_available", return_value=True),
            ):
                client = self._client()
                client._resolve_target()
                self.assertIsNotNone(client._target_cache)

                client.select_max_instance(111)
                self.assertIsNone(client._target_cache)

                client.release_max_instance()
                self.assertIsNone(client._target_cache)

                client._resolve_target()
                self.assertIsNotNone(client._target_cache)
                client.release_max_instance()
                self.assertIsNone(client._target_cache)

    def test_send_failure_invalidates_the_cache(self) -> None:
        client = self._client()
        with self._counted_resolution(client) as resolve:
            with patch.object(
                MaxClient, "_send_via_pipe", side_effect=PipeNotConnectedError("gone")
            ):
                with self.assertRaises(PipeNotConnectedError):
                    client.send_command("x")
            self.assertIsNone(client._target_cache)
            with patch.object(
                MaxClient,
                "_send_via_pipe",
                return_value=b'{"success":true,"result":"ok","error":"","meta":{}}\n',
            ):
                client.send_command("x")
        self.assertEqual(resolve.call_count, 2)

    def test_a_non_connection_failure_keeps_the_cache(self) -> None:
        client = self._client()
        with self._counted_resolution(client) as resolve:
            with patch.object(MaxClient, "_send_via_pipe", side_effect=ValueError("boom")):
                with self.assertRaises(ValueError):
                    client.send_command("x")
            self.assertIsNotNone(client._target_cache)
        self.assertEqual(resolve.call_count, 1)


if __name__ == "__main__":
    unittest.main()
