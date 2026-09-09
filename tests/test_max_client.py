import unittest
import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

from maxmcp.max_client import AmbiguousMaxInstanceError, MaxBridgeError, MaxClient


class MaxClientTests(unittest.TestCase):
    def test_explicit_instance_wins_over_environment_default(self):
        with patch.dict('os.environ', {'MCP_MAX_PIPE': 'pipe-env'}):
            self.assertEqual(MaxClient(pipe_name='pipe-selected')._resolve_pipe_name(), 'pipe-selected')
            self.assertEqual(MaxClient()._resolve_pipe_name(), 'pipe-env')

    def test_request_resolves_target_once_and_records_transport_failures(self):
        client = MaxClient()
        with patch.object(client, '_resolve_pipe_name', side_effect=['pipe-A', 'pipe-B']) as resolve, patch.object(client, '_send_via_pipe', side_effect=TimeoutError('pending')) as send:
            with self.assertRaises(TimeoutError): client.send_command('1')
            resolve.assert_called_once()
            self.assertEqual(send.call_args.kwargs['pipe_name'], 'pipe-A')
            self.assertEqual(client.get_last_transport()['error'], 'pending')

    def test_connection_lock_obeys_deadline(self):
        client = MaxClient(pipe_name='pipe-A')
        client._pipe_lock.acquire()
        try:
            with self.assertRaisesRegex(TimeoutError, 'lock'):
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

    def test_resolve_pipe_uses_active_instance_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            config = Path(tmp) / "3dsmax-mcp"
            config.mkdir()
            active = {
                "instance_id": "pid-111",
                "pid": 111,
                "pipe": r"\\.\pipe\3dsmax-mcp-pid-111",
            }
            (config / "active_instance.json").write_text(json.dumps(active), "utf-8")

            with (
                patch.dict("os.environ", {"LOCALAPPDATA": tmp}, clear=False),
                patch.object(MaxClient, "_probe_pipe_available", return_value=True),
            ):
                self.assertEqual(MaxClient()._resolve_pipe_name(), active["pipe"])

    def test_resolve_pipe_requires_claim_when_multiple_instances_are_live(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            instances = Path(tmp) / "3dsmax-mcp" / "instances"
            instances.mkdir(parents=True)
            for pid in (111, 222):
                data = {
                    "instance_id": f"pid-{pid}",
                    "pid": pid,
                    "pipe": fr"\\.\pipe\3dsmax-mcp-pid-{pid}",
                }
                (instances / f"pid-{pid}.json").write_text(json.dumps(data), "utf-8")

            with (
                patch.dict("os.environ", {"LOCALAPPDATA": tmp}, clear=False),
                patch.object(MaxClient, "_probe_pipe_available", return_value=True),
            ):
                with self.assertRaisesRegex(AmbiguousMaxInstanceError, "MCP Claim This Max"):
                    MaxClient()._resolve_pipe_name()


if __name__ == "__main__":
    unittest.main()
