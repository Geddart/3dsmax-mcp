"""Regression tests for MAXScript value escaping in material_ops."""

import unittest
from unittest.mock import patch

from maxmcp.tools.material_ops import set_texture_map_properties


class SetTextureMapPropertiesEscapingTests(unittest.TestCase):
    """A Windows path must reach MAXScript as a verbatim string.

    Without safe_value() the literal "C:\tex\normal.png" is emitted raw,
    and MAXScript interprets \t / \n as escape sequences, silently
    corrupting the filename.
    """

    def _generated_script(self, properties: dict[str, str]) -> str:
        with patch("maxmcp.tools.material_ops.client") as client:
            client.native_available = False
            client.send_command.return_value = {"result": "ok"}
            set_texture_map_properties("tmpTex", properties)
        return client.send_command.call_args.args[0]

    def test_windows_path_is_emitted_as_verbatim_string(self) -> None:
        script = self._generated_script({"filename": r'"C:\tex\normal.png"'})

        self.assertIn(r'tmpTex.filename = @"C:\tex\normal.png"', script)
        # The raw (non-verbatim) form must not survive.
        self.assertNotIn(r'tmpTex.filename = "C:\tex\normal.png"', script)

    def test_already_verbatim_path_is_not_double_prefixed(self) -> None:
        script = self._generated_script({"filename": r'@"C:\tex\normal.png"'})

        self.assertIn(r'tmpTex.filename = @"C:\tex\normal.png"', script)
        self.assertNotIn('@@"', script)

    def test_non_path_values_pass_through_unchanged(self) -> None:
        script = self._generated_script({"coords": "1", "uvwSource": "#explicit"})

        self.assertIn("tmpTex.coords = 1", script)
        self.assertIn("tmpTex.uvwSource = #explicit", script)

    def test_native_path_bypasses_maxscript_generation(self) -> None:
        with patch("maxmcp.tools.material_ops.client") as client:
            client.native_available = True
            client.send_command.return_value = {"result": "ok"}
            set_texture_map_properties("tmpTex", {"filename": r'"C:\tex\normal.png"'})

        self.assertEqual(
            client.send_command.call_args.kwargs["cmd_type"],
            "native:set_texture_map_properties",
        )


if __name__ == "__main__":
    unittest.main()
