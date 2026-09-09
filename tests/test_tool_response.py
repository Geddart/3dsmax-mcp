import asyncio
import inspect
import os
import unittest
from pathlib import Path
from unittest.mock import patch

from mcp.server.fastmcp.utilities.types import Image

from maxmcp.tool_response import (
    ToolEnvelope,
    envelope_result,
    envelope_exception,
    make_structured_tool,
    run_in_thread,
)


class ToolResponseTests(unittest.TestCase):
    def test_minimal_success_reports_routing_and_omits_diagnostics(self) -> None:
        """With several Max instances live, "which Max got this?" must be answerable."""
        with patch.dict(os.environ, {"MCP_TRIPBACK_MODE": "minimal"}, clear=False):
            payload = envelope_result(
                '{"value": 3, "warnings": ["low"]}',
                elapsed_ms=1.234,
                transport={
                    "transport": "namedpipe",
                    "request_id": "abc",
                    "client_round_trip_ms": 1.2,
                    "target_pid": 1234,
                    "target_pipe": r"\\.\pipe\3dsmax-mcp-pid-1234",
                    "target_source": "claimed",
                },
            )

        self.assertEqual(payload["ok"], True)
        self.assertEqual(payload["result"]["value"], 3)
        self.assertEqual(payload["warnings"], ["low"])
        self.assertNotIn("error", payload)
        self.assertEqual(payload["transport"], {
            "transport": "namedpipe",
            "target_pid": 1234,
            "target_pipe": r"\\.\pipe\3dsmax-mcp-pid-1234",
            "target_source": "claimed",
        })
        self.assertNotIn("elapsed_ms", payload)

    def test_full_success_includes_transport_and_elapsed(self) -> None:
        with patch.dict(os.environ, {"MCP_TRIPBACK_MODE": "full"}, clear=False):
            payload = envelope_result(
                '{"value": 3}',
                elapsed_ms=1.234,
                transport={"transport": "namedpipe"},
            )

        self.assertEqual(payload["ok"], True)
        self.assertEqual(payload["elapsed_ms"], 1.234)
        self.assertEqual(payload["transport"]["transport"], "namedpipe")

    def test_minimal_error_includes_slim_transport(self) -> None:
        with patch.dict(os.environ, {"MCP_TRIPBACK_MODE": "minimal"}, clear=False):
            payload = envelope_result(
                "Error: boom",
                elapsed_ms=2.0,
                transport={
                    "transport": "namedpipe",
                    "request_id": "abc",
                    "client_round_trip_ms": 1.2,
                },
            )

        self.assertEqual(payload["ok"], False)
        self.assertEqual(payload["error"]["message"], "Error: boom")
        self.assertEqual(payload["transport"], {"transport": "namedpipe"})
        self.assertNotIn("elapsed_ms", payload)
        self.assertNotIn("result", payload)
        self.assertEqual(payload["error"]["code"], "BAD_PARAM")
        self.assertEqual(payload["error"]["retryable"], False)

    def test_structured_native_error_preserves_code_retryable_and_hint(self) -> None:
        raw = (
            '{"type":"NativeError","message":"Ambiguous object name: Box",'
            '"code":"AMBIGUOUS","retryable":false,'
            '"hint":{"candidates":[{"name":"Box","handle":10,"class":"Box","layer":"0"}]}}'
        )
        with patch.dict(os.environ, {"MCP_TRIPBACK_MODE": "minimal"}, clear=False):
            payload = envelope_result(raw, elapsed_ms=0.1)

        self.assertEqual(payload["ok"], False)
        self.assertEqual(payload["error"]["code"], "AMBIGUOUS")
        self.assertEqual(payload["error"]["retryable"], False)
        self.assertEqual(payload["hint"]["candidates"][0]["handle"], 10)

    def test_json_success_payload_with_message_is_not_error(self) -> None:
        raw = '{"message":"Transformed Box001","handle":10,"position":[1,2,3]}'
        with patch.dict(os.environ, {"MCP_TRIPBACK_MODE": "minimal"}, clear=False):
            payload = envelope_result(raw, elapsed_ms=0.1)

        self.assertEqual(payload["ok"], True)
        self.assertEqual(payload["result"]["message"], "Transformed Box001")
        self.assertNotIn("error", payload)

    def test_envelope_surfaces_hint_from_error_result(self) -> None:
        raw = {
            "status": "error",
            "error_type": "MAXScriptError",
            "error": "-- Unknown property: foo",
            "hint": {"message": "fallback", "suggested_tools": ["introspect_osl"]},
        }
        with patch.dict(os.environ, {"MCP_TRIPBACK_MODE": "minimal"}, clear=False):
            payload = envelope_result(raw, elapsed_ms=0.1)

        self.assertEqual(payload["ok"], False)
        self.assertEqual(payload["error"]["type"], "MAXScriptError")
        self.assertEqual(payload["hint"]["suggested_tools"], ["introspect_osl"])

    def test_envelope_preserves_structured_error_details(self) -> None:
        raw = {
            "status": "error",
            "error_type": "MCGCompileError",
            "error": "compile failed",
            "details": {
                "graph_id": "graph_123",
                "diagnostics": "Unknown operator",
                "rolled_back": True,
            },
        }
        with patch.dict(os.environ, {"MCP_TRIPBACK_MODE": "minimal"}, clear=False):
            payload = envelope_result(raw, elapsed_ms=0.1)

        self.assertEqual(payload["ok"], False)
        self.assertEqual(payload["error"]["details"]["graph_id"], "graph_123")
        self.assertEqual(payload["error"]["details"]["rolled_back"], True)

    def test_envelope_normalizes_string_hint(self) -> None:
        raw = {"status": "error", "error": "nope", "hint": "try scope=refs"}
        with patch.dict(os.environ, {"MCP_TRIPBACK_MODE": "minimal"}, clear=False):
            payload = envelope_result(raw, elapsed_ms=0.1)

        self.assertEqual(payload["ok"], False)
        self.assertEqual(payload["hint"]["message"], "try scope=refs")

    def test_envelope_promotes_plural_hints(self) -> None:
        raw = {"status": "error", "error": "nope", "hints": "use query_scene"}
        with patch.dict(os.environ, {"MCP_TRIPBACK_MODE": "minimal"}, clear=False):
            payload = envelope_result(raw, elapsed_ms=0.1)

        self.assertEqual(payload["hint"]["message"], "use query_scene")

    def test_envelope_auto_hints_not_found(self) -> None:
        with patch.dict(os.environ, {"MCP_TRIPBACK_MODE": "minimal"}, clear=False):
            payload = envelope_result("Object not found: __missing__", elapsed_ms=0.1)

        self.assertEqual(payload["ok"], False)
        self.assertIn("query_scene", payload["hint"]["suggested_tools"])

    def test_envelope_auto_hints_safe_mode(self) -> None:
        with patch.dict(os.environ, {"MCP_TRIPBACK_MODE": "minimal"}, clear=False):
            payload = envelope_result(
                "Blocked by safe mode: command contains a restricted function.",
                elapsed_ms=0.1,
            )

        self.assertEqual(payload["ok"], False)
        self.assertIn("safe mode", payload["hint"]["message"].lower())
        self.assertNotIn("suggested_tools", payload["hint"])

    def test_envelope_catches_not_found_and_failed_messages(self) -> None:
        for raw in (
            "Object not found: __missing__",
            "Material not found: foo",
            "Failed: could not assign controller",
            "Blocked by safe mode: command contains a restricted function.",
        ):
            with self.subTest(raw=raw):
                payload = envelope_result(raw, elapsed_ms=0.1)
                self.assertEqual(payload["ok"], False, raw)
                self.assertEqual(payload["error"]["message"], raw)

    def test_envelope_spills_mcp_images_to_files(self) -> None:
        payload = envelope_result(Image(data=b"abc", format="png"), elapsed_ms=0.0)

        self.assertEqual(payload["ok"], True)
        self.assertEqual(payload["result"]["type"], "image_file")
        self.assertEqual(payload["result"]["mime_type"], "image/png")
        self.assertNotIn("data", payload["result"])
        spilled = Path(payload["result"]["file"])
        self.addCleanup(lambda: spilled.exists() and spilled.unlink())
        self.assertEqual(spilled.suffix, ".png")
        self.assertEqual(spilled.read_bytes(), b"abc")

    def test_envelope_inlines_small_bytes(self) -> None:
        payload = envelope_result(b"abc", elapsed_ms=0.0)

        self.assertEqual(payload["result"]["type"], "bytes")
        self.assertEqual(payload["result"]["size"], 3)

    def test_envelope_spills_large_bytes_to_files(self) -> None:
        blob = b"x" * 100_000
        payload = envelope_result(blob, elapsed_ms=0.0)

        self.assertEqual(payload["result"]["type"], "bytes_file")
        self.assertEqual(payload["result"]["size"], len(blob))
        self.assertNotIn("data", payload["result"])
        spilled = Path(payload["result"]["file"])
        self.addCleanup(lambda: spilled.exists() and spilled.unlink())
        self.assertEqual(spilled.read_bytes(), blob)

    def test_minimal_exception_omits_elapsed(self) -> None:
        with patch.dict(os.environ, {"MCP_TRIPBACK_MODE": "minimal"}, clear=False):
            payload = envelope_exception(
                RuntimeError("down"),
                elapsed_ms=9.0,
                transport={"transport": "tcp"},
            )

        self.assertEqual(payload["ok"], False)
        self.assertEqual(payload["error"]["message"], "down")
        self.assertEqual(payload["transport"]["transport"], "tcp")
        self.assertNotIn("elapsed_ms", payload)

    def test_exception_auto_hints_bridge_errors(self) -> None:
        with patch.dict(os.environ, {"MCP_TRIPBACK_MODE": "minimal"}, clear=False):
            payload = envelope_exception(
                RuntimeError("named pipe connection failed"),
                elapsed_ms=1.0,
            )

        self.assertEqual(payload["ok"], False)
        self.assertIn("get_bridge_status", payload["hint"]["suggested_tools"])

    def test_exception_passes_maxscript_script_for_intent_hints(self) -> None:
        with patch.dict(os.environ, {"MCP_TRIPBACK_MODE": "minimal"}, clear=False):
            payload = envelope_exception(
                RuntimeError("MAXScript error: MAXScript execution failed (parse error)"),
                elapsed_ms=1.0,
                tool_name="execute_maxscript",
                script="Box() width:10 length:10 height:10",
            )

        self.assertEqual(payload["ok"], False)
        self.assertIn("create_object", payload["hint"]["suggested_tools"])

    def test_structured_tool_preserves_signature_and_catches_exceptions(self) -> None:
        def raw_tool(name: str, count: int = 1) -> str:
            if count < 0:
                raise ValueError("bad count")
            return name * count

        with patch.dict(os.environ, {"MCP_TRIPBACK_MODE": "full"}, clear=False):
            wrapped = make_structured_tool(raw_tool, transport_provider=lambda: {"transport": "tcp"})

            self.assertTrue(str(wrapped.__signature__).endswith("-> ToolEnvelope") or
                            str(wrapped.__signature__).endswith("-> maxmcp.tool_response.ToolEnvelope"))
            self.assertIs(wrapped.__annotations__["return"], ToolEnvelope)

            ok_payload = wrapped("x", count=2)
            self.assertIsInstance(ok_payload, dict)
            self.assertEqual(ok_payload["result"], "xx")
            self.assertEqual(ok_payload["transport"]["transport"], "tcp")

            error_payload = wrapped("x", count=-1)
            self.assertEqual(error_payload["ok"], False)
            self.assertEqual(error_payload["error"]["type"], "ValueError")


class RunInThreadTests(unittest.TestCase):
    """Async dispatch is chosen by an explicit marker, not by module name."""

    def test_undecorated_tool_stays_synchronous(self) -> None:
        def plain() -> dict:
            return {"value": 1}

        plain.__module__ = "maxmcp.tools.jobs"
        wrapped = make_structured_tool(plain)
        self.assertFalse(inspect.iscoroutinefunction(wrapped))
        self.assertTrue(wrapped()["ok"])

    def test_decorated_tool_is_dispatched_to_a_thread(self) -> None:
        import threading

        @run_in_thread
        def marked() -> dict:
            return {"thread": threading.current_thread().name}

        wrapped = make_structured_tool(marked)
        self.assertTrue(inspect.iscoroutinefunction(wrapped))

        async def check() -> None:
            payload = await wrapped()
            self.assertTrue(payload["ok"])
            self.assertNotEqual(payload["result"]["thread"], threading.current_thread().name)

        asyncio.run(check())

    def test_module_name_alone_no_longer_forces_a_thread(self) -> None:
        """The temporary '.tools.max_ui' suffix fallback is gone; only the marker counts."""
        def provider() -> dict:
            return {"value": 1}

        provider.__module__ = "maxmcp.tools.max_ui"
        self.assertFalse(inspect.iscoroutinefunction(make_structured_tool(provider)))

    def test_every_ui_tool_is_marked(self) -> None:
        from maxmcp.tool_response import RUN_IN_THREAD_ATTR
        from maxmcp.tools import max_ui as ui_tools

        names = [name for name in dir(ui_tools) if name.startswith("max_ui_")]
        self.assertTrue(names)
        for name in names:
            self.assertTrue(getattr(getattr(ui_tools, name), RUN_IN_THREAD_ATTR, False), name)

    def test_every_job_tool_is_marked(self) -> None:
        from maxmcp.tool_response import RUN_IN_THREAD_ATTR
        from maxmcp.tools import jobs as job_tools

        names = [name for name in dir(job_tools) if name.startswith("max_job_")]
        self.assertTrue(names)
        for name in names:
            self.assertTrue(getattr(getattr(job_tools, name), RUN_IN_THREAD_ATTR, False), name)



if __name__ == "__main__":
    unittest.main()
