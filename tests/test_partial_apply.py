"""PARTIAL_APPLY: the native bridge reads every write back and fails loud.

A write that created something (object, modifier, material) but left a
requested key unapplied raises PARTIAL_APPLY with the created handle in
``details``. The envelope must carry code and details unchanged, never mark it
retryable, and create_object must never replay the call (it would duplicate
the node).
"""
import json
import unittest
from unittest.mock import PropertyMock, patch

from maxmcp.max_client import MaxBridgeError
from maxmcp.tool_response import (
    ErrorCode,
    _error_from_exception,
    _normalize_error,
    envelope_exception,
)
from maxmcp.tools.objects import _is_unresolved_class_error, create_object


def _partial_apply_payload() -> dict:
    return {
        "type": "NativeError",
        "message": "create_object: created Cylinder001 but 1 requested parameter(s) did not apply",
        "code": "PARTIAL_APPLY",
        "retryable": False,
        "hint": {"message": "Do NOT re-run the call."},
        "details": {
            "name": "Cylinder001",
            "handle": 4242,
            "created": True,
            "retry": False,
            "keys": [
                {"key": "bogusprop", "requested": "3", "applied": None,
                 "reason": "MAXScript: Unknown property: \"bogusprop\""},
            ],
            "applied": {"radius": "5"},
        },
    }


def _bridge_error(payload: dict) -> MaxBridgeError:
    message = json.dumps(payload)
    return MaxBridgeError(message, {"success": False, "error": message})


class PartialApplyEnvelopeTests(unittest.TestCase):
    def test_error_code_exists_and_is_not_retryable(self) -> None:
        self.assertEqual(ErrorCode.PARTIAL_APPLY.value, "PARTIAL_APPLY")
        error = _normalize_error(message="x", code="PARTIAL_APPLY")
        self.assertEqual(error["code"], "PARTIAL_APPLY")
        self.assertFalse(error["retryable"])

    def test_normalize_error_passes_code_and_details_through(self) -> None:
        details = _partial_apply_payload()["details"]
        error = _normalize_error(message="partial", code="PARTIAL_APPLY", retryable=False, details=details)
        self.assertEqual(error["code"], "PARTIAL_APPLY")
        self.assertEqual(error["details"], details)

    def test_bridge_exception_keeps_code_handle_and_keys(self) -> None:
        error = _error_from_exception(_bridge_error(_partial_apply_payload()))
        self.assertEqual(error["code"], "PARTIAL_APPLY")
        self.assertFalse(error["retryable"])
        self.assertEqual(error["details"]["handle"], 4242)
        self.assertEqual(error["details"]["keys"][0]["key"], "bogusprop")
        self.assertIsNone(error["details"]["keys"][0]["applied"])

    def test_envelope_carries_details_and_promotes_hint(self) -> None:
        envelope = envelope_exception(
            _bridge_error(_partial_apply_payload()), elapsed_ms=1.0, tool_name="create_object"
        )
        self.assertFalse(envelope["ok"])
        self.assertEqual(envelope["error"]["code"], "PARTIAL_APPLY")
        self.assertFalse(envelope["error"]["retryable"])
        self.assertEqual(envelope["error"]["details"]["handle"], 4242)
        self.assertIn("hint", envelope)

    def test_retryable_true_in_payload_cannot_be_inferred_for_unknown_codes(self) -> None:
        # The code alone (no explicit retryable) must still resolve to not retryable.
        payload = _partial_apply_payload()
        del payload["retryable"]
        error = _error_from_exception(_bridge_error(payload))
        self.assertFalse(error["retryable"])


class CreateObjectNoReplayTests(unittest.TestCase):
    def test_partial_apply_is_not_an_unresolved_class(self) -> None:
        self.assertFalse(_is_unresolved_class_error(_bridge_error(_partial_apply_payload())))

    def test_unknown_class_still_counts_as_unresolved(self) -> None:
        structured = {"type": "NativeError", "message": "Unknown object class: Freecamera",
                      "code": "PLUGIN_MISSING", "retryable": False}
        self.assertTrue(_is_unresolved_class_error(_bridge_error(structured)))
        self.assertTrue(_is_unresolved_class_error(
            MaxBridgeError("Unknown object class: Freecamera", {"success": False})))

    def test_partial_apply_message_mentioning_unknown_class_is_not_replayed(self) -> None:
        payload = _partial_apply_payload()
        payload["message"] = "Unknown object class: Cylinder (but the node exists)"
        self.assertFalse(_is_unresolved_class_error(_bridge_error(payload)))

    def test_create_object_raises_partial_apply_without_second_send(self) -> None:
        with (
            patch("maxmcp.max_client.MaxClient.native_available", new_callable=PropertyMock, return_value=True),
            patch(
                "maxmcp.tools.objects.client.send_command",
                side_effect=_bridge_error(_partial_apply_payload()),
            ) as mocked_send,
        ):
            with self.assertRaises(MaxBridgeError) as raised:
                create_object("Cylinder", params="radius:5 bogusprop:3")

        self.assertEqual(mocked_send.call_count, 1)
        self.assertEqual(_error_from_exception(raised.exception)["code"], "PARTIAL_APPLY")

    def test_create_object_unknown_class_falls_back_to_maxscript_once(self) -> None:
        unknown = {"type": "NativeError", "message": "Unknown object class: Freecamera",
                   "code": "PLUGIN_MISSING", "retryable": False}
        with (
            patch("maxmcp.max_client.MaxClient.native_available", new_callable=PropertyMock, return_value=True),
            patch(
                "maxmcp.tools.objects.client.send_command",
                side_effect=[_bridge_error(unknown), {"result": json.dumps({"name": "Camera001"})}],
            ) as mocked_send,
        ):
            create_object("Freecamera")

        self.assertEqual(mocked_send.call_count, 2)


if __name__ == "__main__":
    unittest.main()
