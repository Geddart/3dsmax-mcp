"""material_roles: role resolution from a captured graphVersion-2 payload (no Max)."""
import copy
import json
import unittest
from pathlib import Path
from unittest.mock import patch

from maxmcp.helpers import material_roles as impl
from maxmcp.tools.material_roles import material_roles

# Captured live from 3ds Max 2025: PhysicalMaterial "RolesMat" with
#   base_color_map <- Bitmap Wood_basecolor.png
#   roughness_map  <- Color Correction <- Bitmap Wood_normal.png  (wrong slot)
#   bump_map       <- Bitmap Missing_bump.png
# None of the C:\tex files exist on the capture machine.
FIXTURE = Path(__file__).parent / "fixtures" / "material_roles_graph_v2.json"


def _batch() -> dict:
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


class RolesFromPayloadTests(unittest.TestCase):
    def setUp(self) -> None:
        self.graph = _batch()["graphs"][0]

    def test_roles_follow_wiring_through_wrappers(self) -> None:
        result = impl.roles_from_payload(self.graph)
        by_slot = {row["slot"]: row for row in result["roles"]}
        self.assertEqual(by_slot["base_color_map"]["role"], "dif")
        self.assertEqual(by_slot["base_color_map"]["file"], "C:\\tex\\Wood_basecolor.png")
        rough = by_slot["roughness_map"]
        self.assertEqual(rough["role"], "rough")
        self.assertEqual(rough["node_chain"], ["Color Correction", "Bitmap"])
        self.assertEqual(rough["file"], "C:\\tex\\Wood_normal.png")

    def test_filename_disagreement_is_advisory_mismatch(self) -> None:
        result = impl.roles_from_payload(self.graph)
        mismatched = {row["slot"] for row in result["mismatches"]}
        self.assertEqual(mismatched, {"roughness_map"})
        by_slot = {row["slot"]: row for row in result["roles"]}
        self.assertFalse(by_slot["base_color_map"]["mismatch"])

    def test_missing_files_listed(self) -> None:
        result = impl.roles_from_payload(self.graph)
        self.assertIn("C:\\tex\\Missing_bump.png", result["missing_files"])

    def test_refuses_graph_without_connections(self) -> None:
        legacy = copy.deepcopy(self.graph)
        legacy.pop("graphVersion")
        with self.assertRaises(ValueError):
            impl.roles_from_payload(legacy)

    def test_truncated_graph_is_incomplete(self) -> None:
        truncated = copy.deepcopy(self.graph)
        truncated["truncated"] = {"nodesOmitted": 3}
        self.assertFalse(impl.roles_from_payload(truncated)["complete"])


class MaterialRolesToolTests(unittest.TestCase):
    def test_argument_validation(self) -> None:
        with self.assertRaises(ValueError):
            material_roles()
        with self.assertRaises(ValueError):
            material_roles(names=["a"], scan_scene=True)
        with self.assertRaises(ValueError):
            material_roles(names=["a"], depth=0)
        with self.assertRaises(ValueError):
            material_roles(names=[""])

    def test_tool_uses_native_roles_action(self) -> None:
        sent = {}

        def fake_send(command, cmd_type="maxscript", timeout=None):
            sent["payload"] = json.loads(command)
            sent["cmd_type"] = cmd_type
            return {"result": json.dumps(_batch())}

        with patch("maxmcp.tools.material_roles.client.send_command", side_effect=fake_send):
            result = material_roles(names=["RolesMat", "RolesMat"], only_problems=True)
        self.assertEqual(sent["cmd_type"], "native:inspect_material_network")
        self.assertEqual(sent["payload"]["action"], "roles")
        self.assertEqual(sent["payload"]["names"], ["RolesMat"])
        self.assertEqual(result["returned"], 1)
        self.assertEqual(result["with_mismatch"], 1)
        self.assertEqual(result["with_missing_files"], 1)

    def test_old_bridge_is_reported(self) -> None:
        with patch("maxmcp.tools.material_roles.client.send_command",
                   return_value={"result": json.dumps({"ok": True})}):
            with self.assertRaisesRegex(RuntimeError, "graphVersion 2"):
                material_roles(names=["RolesMat"])


if __name__ == "__main__":
    unittest.main()
