import json
import unittest
from unittest.mock import MagicMock, patch

from maxmcp.path_policy import PathNotAllowedError
from maxmcp.tools import vray as V


def _client(*results):
    mock = MagicMock()
    mock.send_command.side_effect = [{"result": r if isinstance(r, str) else json.dumps(r)} for r in results]
    return mock


def _scripts(mock):
    return [c.args[0] for c in mock.send_command.call_args_list]


RENDERER_DUMP = {
    "renderer": "V_Ray_7__update_4_hotfix_2_DR2",
    "is_vray": True,
    "vray_version": "7.40.04",
    "scene_dir": "",
    "props": [
        {"name": "progressive_noise_threshold", "type": "Float", "value": 0.01},
        {"name": "GI_on", "type": "BooleanClass", "value": True},
        {"name": "progressive_maxSamples", "type": "Integer", "value": 100},
        {"name": "environment_gi_color", "type": "Color", "value": [215.0, 228.0, 251.0]},
        {"name": "output_rawFileName", "type": "String", "value": ""},
        {"name": "adv_irradmap_loadFileName", "type": "String", "value": ""},
        {"name": "lightcache_preset_subdivs", "type": "ArrayParameter", "value": [1000, 3000]},
        {"name": "filter_Kernel", "type": "VRayLanczosFilter", "value": {"class": "VRayLanczosFilter"}},
    ],
}


class FormattingTests(unittest.TestCase):
    def test_format_value_by_live_type(self):
        self.assertEqual(V.format_value("BooleanClass", True), ("true", True))
        self.assertEqual(V.format_value("BooleanClass", "off"), ("false", False))
        self.assertEqual(V.format_value("Integer", 50), ("50", 50))
        self.assertEqual(V.format_value("Integer", 4.0), ("4", 4))
        self.assertEqual(V.format_value("Float", 3), ("3.0", 3.0))
        self.assertEqual(V.format_value("Float", "0,25"), ("0.25", 0.25))
        self.assertEqual(V.format_value("Color", [10, 20, 30]), ("(color 10.0 20.0 30.0)", [10.0, 20.0, 30.0]))
        self.assertEqual(V.format_value("Point3", [1, 2.5, -3]), ("[1.0,2.5,-3.0]", [1.0, 2.5, -3.0]))
        self.assertEqual(V.format_value("String", 'a"b'), ('"a\\"b"', 'a"b'))
        self.assertEqual(V.format_value("UndefinedClass", "x"), ('"x"', "x"))
        self.assertEqual(V.format_value("Float", None), ("undefined", None))

    def test_format_value_rejects_wrong_types(self):
        with self.assertRaises(TypeError):
            V.format_value("Integer", 2.5)
        with self.assertRaises(TypeError):
            V.format_value("Integer", True)
        with self.assertRaises(TypeError):
            V.format_value("Float", True)
        with self.assertRaises(TypeError):
            V.format_value("BooleanClass", 2)
        with self.assertRaises(TypeError):
            V.format_value("Color", [1, 2])
        with self.assertRaises(TypeError):
            V.format_value("VRayLanczosFilter", 1)
        with self.assertRaises(ValueError):
            V.format_value("String", "two\nlines")
        with self.assertRaises(ValueError):
            V.format_value("Float", float("nan"))

    def test_float_literal_never_uses_exponent_or_comma(self):
        self.assertEqual(V._ms_float(1e-05), "0.00001")
        self.assertEqual(V._ms_float(2.5e-7), "0.00000025")
        self.assertNotIn(",", V._ms_float(1234567.25))

    def test_format_array_uses_existing_element_type(self):
        self.assertEqual(V.format_array([1000, 3000], [500, 1500]), ("#(500,1500)", [500, 1500]))
        self.assertEqual(V.format_array([2.0, 8.0], [1, 2]), ("#(1.0,2.0)", [1.0, 2.0]))
        with self.assertRaises(TypeError):
            V.format_array([1, 2], "nope")

    def test_values_match(self):
        self.assertTrue(V.values_match(0.02, 0.0199999995))
        self.assertFalse(V.values_match(0.02, 0.021))
        self.assertFalse(V.values_match(True, 1))
        self.assertFalse(V.values_match(1, True))
        self.assertTrue(V.values_match([10.0, 20.0, 30.0], [10.0, 20.0, 30.0]))
        self.assertTrue(V.values_match(None, None))

    def test_write_path_properties(self):
        for name in ("output_rawFileName", "output_splitfilename", "system_vrayLog_file",
                     "system_memstats_path", "lightcache_autoSaveFileName", "vrscene_fileName"):
            self.assertTrue(V.is_write_path_property(name), name)
        for name in ("adv_irradmap_loadFileName", "lightcache_loadFileName", "progressive_maxSamples"):
            self.assertFalse(V.is_write_path_property(name), name)

    def test_enums(self):
        self.assertEqual(V.normalize_enum("full", V.LIGHT_SELECT_MODES, "mode", "7.40.04"), 4)
        self.assertEqual(V.normalize_enum("Direct diffuse", V.LIGHT_SELECT_MODES, "mode", "7.40.04"), 2)
        self.assertEqual(V.normalize_enum("lpe", V.LIGHT_SELECT_MODES, "mode", "7.40.04"), 9)
        self.assertEqual(V.normalize_enum(7, V.LIGHT_SELECT_MODES, "mode", "6.0"), 7)
        self.assertEqual(V.normalize_enum("material_name", V.CRYPTOMATTE_ID_TYPES, "id_type", "7.40.04"), 2)
        self.assertEqual(V.normalize_enum("Node name with hierarchy", V.CRYPTOMATTE_ID_TYPES, "id_type", "7.1"), 1)
        with self.assertRaises(ValueError):
            V.normalize_enum(10, V.LIGHT_SELECT_MODES, "mode", "7.40.04")
        with self.assertRaises(ValueError):
            V.normalize_enum("full", V.LIGHT_SELECT_MODES, "mode", "6.20.00")
        with self.assertRaises(ValueError):
            V.normalize_enum("bogus", V.LIGHT_SELECT_MODES, "mode", "7.40.04")
        self.assertEqual(V.enum_label(2, V.CRYPTOMATTE_ID_TYPES, "7.40.04"), "node_material_name")
        self.assertIsNone(V.enum_label(2, V.CRYPTOMATTE_ID_TYPES, "6.2"))

    def test_user_prop_parsing(self):
        buf = "VRay_Matte_Enable = True\r\nVRay_Matte_Alpha = -1,000000\r\n\r\nother=1\r\nVRay_Matte_Alpha = 5\r\n"
        parsed = V.parse_user_prop_buffer(buf)
        self.assertEqual(parsed, {"VRay_Matte_Enable": "True", "VRay_Matte_Alpha": "-1,000000", "other": "1"})
        self.assertEqual(V.parse_typed("-1,000000", "float"), -1.0)
        self.assertEqual(V.parse_typed("-0.5", "float"), -0.5)
        self.assertIs(V.parse_typed("True", "bool"), True)
        self.assertIs(V.parse_typed("false", "bool"), False)
        self.assertIs(V.parse_typed("0", "bool"), False)
        self.assertIsNone(V.parse_typed("abc", "float"))

    def test_user_prop_float_matches_vray_format(self):
        self.assertEqual(V.format_user_prop_float(-1), "-1.000000")
        self.assertEqual(V.format_user_prop_float(0.25), "0.250000")


class RunTests(unittest.TestCase):
    def test_maxscript_error_sentinel_raises(self):
        mock = _client("__MCP_MS_ERR__: -- Unknown property")
        with patch("maxmcp.tools.vray.client", mock):
            with self.assertRaisesRegex(RuntimeError, "Unknown property"):
                V.vray_get_settings()

    def test_error_payload_raises(self):
        mock = _client({"error": "-- Runtime error: boom"})
        with patch("maxmcp.tools.vray.client", mock):
            with self.assertRaisesRegex(RuntimeError, "boom"):
                V.vray_get_settings()


class RendererToolTests(unittest.TestCase):
    def test_set_renderer_validates_mode(self):
        with self.assertRaises(ValueError):
            V.vray_set_renderer("rt")

    def test_set_renderer_gpu_script(self):
        mock = _client({"renderer_class": "V_Ray_GPU_7", "previous_class": "V_Ray_7", "changed": True,
                        "restored_settings": False, "vray_version": "7.40.04", "engine_type": 2})
        with patch("maxmcp.tools.vray.client", mock):
            out = json.loads(V.vray_set_renderer("GPU"))
        script = _scripts(mock)[0]
        self.assertIn("local wantGpu = true", script)
        self.assertIn("mcp_vray_renderer_stash", script)
        self.assertIn("#systemPostReset", script)
        self.assertEqual(out["mode"], "gpu")
        self.assertEqual(out["renderer_class"], "V_Ray_GPU_7")

    def test_get_settings_filters(self):
        mock = _client(RENDERER_DUMP)
        with patch("maxmcp.tools.vray.client", mock):
            out = json.loads(V.vray_get_settings(filter="progressive_*"))
        self.assertEqual(sorted(out["settings"]), ["progressive_maxSamples", "progressive_noise_threshold"])
        self.assertEqual(out["settings"]["progressive_maxSamples"], {"type": "Integer", "value": 100})

    def test_get_settings_unknown_name_lists_close_matches(self):
        mock = _client(RENDERER_DUMP)
        with patch("maxmcp.tools.vray.client", mock):
            with self.assertRaisesRegex(ValueError, "progressive_noise_threshold"):
                V.vray_get_settings(names=["progressive_noise_treshold"])

    def test_get_settings_requires_vray(self):
        mock = _client({"renderer": "Default_Scanline_Renderer", "is_vray": False, "props": []})
        with patch("maxmcp.tools.vray.client", mock):
            with self.assertRaisesRegex(RuntimeError, "vray_set_renderer"):
                V.vray_get_settings()

    def test_set_settings_writes_typed_and_reads_back(self):
        readback = {"readback": {"progressive_noise_threshold": 0.02, "GI_on": False,
                                 "environment_gi_color": [10.0, 20.0, 30.0],
                                 "lightcache_preset_subdivs": [500, 1500]},
                    "errors": {}, "renderer_class": "V_Ray_7"}
        mock = _client(RENDERER_DUMP, readback)
        with patch("maxmcp.tools.vray.client", mock):
            out = json.loads(V.vray_set_settings({"PROGRESSIVE_noise_threshold": 0.02, "gi_on": False,
                                                  "environment_gi_color": [10, 20, 30],
                                                  "lightcache_preset_subdivs": [500, 1500]}))
        script = _scripts(mock)[1]
        self.assertIn("setProperty r #progressive_noise_threshold (0.02)", script)
        self.assertIn("setProperty r #GI_on (false)", script)
        self.assertIn("setProperty r #environment_gi_color ((color 10.0 20.0 30.0))", script)
        self.assertIn("setProperty r #lightcache_preset_subdivs (#(500,1500))", script)
        self.assertIn('undo "MCP vray_set_settings" on', script)
        self.assertEqual(out["set"]["GI_on"], False)

    def test_set_settings_gpu_read_only_mirror_falls_back_to_v_ray_settings(self):
        # Regression (review 2026-10-12): V-Ray GPU's output_* are read-only mirrors of
        # renderers.current.V_Ray_settings; the write and the read-back must use the owner.
        readback = {"readback": {"output_rawFileName": "C:/p/raw.exr"}, "on_sub_object": ["output_rawFileName"],
                    "errors": {}, "renderer_class": "V_Ray_GPU_7"}
        mock = _client(RENDERER_DUMP, readback)
        with patch("maxmcp.tools.vray.client", mock), patch("maxmcp.tools.vray.resolve_write_path"):
            out = json.loads(V.vray_set_settings({"output_rawFileName": "C:/p/raw.exr"}))
        script = _scripts(mock)[1]
        self.assertIn("local sub = if (isProperty r #V_Ray_settings) then r.V_Ray_settings else undefined", script)
        self.assertIn("if sub != undefined and (isProperty sub #output_rawFileName) then", script)
        self.assertIn("try (setProperty sub #output_rawFileName", script)
        self.assertIn("getProperty hosts[1] #output_rawFileName", script)
        self.assertEqual(out["written_to_V_Ray_settings"], ["output_rawFileName"])
        self.assertEqual(out["set"]["output_rawFileName"], "C:/p/raw.exr")

    def test_set_settings_mismatch_raises(self):
        readback = {"readback": {"progressive_maxSamples": 60}, "errors": {}}
        mock = _client(RENDERER_DUMP, readback)
        with patch("maxmcp.tools.vray.client", mock):
            with self.assertRaisesRegex(RuntimeError, "read-back mismatch.*progressive_maxSamples"):
                V.vray_set_settings({"progressive_maxSamples": 50})

    def test_set_settings_write_error_raises(self):
        readback = {"readback": {"progressive_maxSamples": 100}, "errors": {"progressive_maxSamples": "-- out of range"}}
        mock = _client(RENDERER_DUMP, readback)
        with patch("maxmcp.tools.vray.client", mock):
            with self.assertRaisesRegex(RuntimeError, "write failed"):
                V.vray_set_settings({"progressive_maxSamples": 50})

    def test_set_settings_validation_writes_nothing(self):
        for props, pattern in (
            ({"progresive_noise_threshold": 0.1}, "close: progressive_noise_threshold"),
            ({"progressive_maxSamples": 2.5}, "expected an integer"),
            ({"filter_Kernel": 1}, "unsupported property type"),
            ({"output_rawFileName": "relative/out.vrimg"}, "absolute"),
        ):
            mock = _client(RENDERER_DUMP)
            with patch("maxmcp.tools.vray.client", mock):
                with self.assertRaisesRegex(ValueError, pattern):
                    V.vray_set_settings(props)
            self.assertEqual(mock.send_command.call_count, 1, props)

    def test_set_settings_output_path_goes_through_policy(self):
        mock = _client(RENDERER_DUMP)
        with patch("maxmcp.tools.vray.client", mock), patch(
                "maxmcp.tools.vray.resolve_write_path", side_effect=PathNotAllowedError("Refusing to write")) as policy:
            with self.assertRaisesRegex(ValueError, "Refusing to write"):
                V.vray_set_settings({"output_rawFileName": "C:/Windows/out.vrimg"})
        policy.assert_called_once()
        self.assertEqual(mock.send_command.call_count, 1)

    def test_load_paths_are_not_policed(self):
        readback = {"readback": {"adv_irradmap_loadFileName": "C:/maps/a.vrmap"}, "errors": {}}
        mock = _client(RENDERER_DUMP, readback)
        with patch("maxmcp.tools.vray.client", mock), patch("maxmcp.tools.vray.resolve_write_path") as policy:
            V.vray_set_settings({"adv_irradmap_loadFileName": "C:/maps/a.vrmap"})
        policy.assert_not_called()


LS_DESCRIBE = {
    "vray_version": "7.40.04",
    "renderer": "V_Ray_7",
    "vray_classes": ["VRayLightSelect", "VRayCryptomatte", "VRayAlpha"],
    "existing": ["Old"],
    "class": "VRayLightSelect",
    "props": [
        {"name": "enabled", "type": "BooleanClass", "value": True},
        {"name": "elementName", "type": "String", "value": "VRayLightSelect"},
        {"name": "multiplier", "type": "Float", "value": 1.0},
        {"name": "mode", "type": "Integer", "value": 4},
        {"name": "lights", "type": "ArrayParameter", "value": []},
        {"name": "lights_exclude_type", "type": "Integer", "value": 1},
    ],
    "lights": [{"name": "Key", "count": 1, "is_light": True}],
}


class RenderElementToolTests(unittest.TestCase):
    def test_add_light_select(self):
        added = {"index": 1, "class": "VRayLightSelect", "name": "LS_key", "props": [
            {"name": "enabled", "type": "BooleanClass", "value": True},
            {"name": "filterOn", "type": "BooleanClass", "value": True},
            {"name": "multiplier", "type": "Float", "value": 2.5},
            {"name": "mode", "type": "Integer", "value": 2},
            {"name": "lights", "type": "ArrayParameter", "value": [{"node": "Key"}]},
            {"name": "lights_exclude_type", "type": "Integer", "value": 1},
        ]}
        mock = _client(LS_DESCRIBE, added)
        with patch("maxmcp.tools.vray.client", mock):
            out = json.loads(V.vray_add_render_element(
                "VRayLightSelect", "LS_key", props={"multiplier": 2.5}, lights=["Key"], mode="direct_diffuse"))
        script = _scripts(mock)[1]
        self.assertIn('local re = cls elementName:"LS_key"', script)
        self.assertIn("setProperty re #mode (2)", script)
        self.assertIn("setProperty re #multiplier (2.5)", script)
        self.assertIn('re.lights = for h in #("Key") collect (getNodeByName h)', script)
        self.assertIn("mgr.AddRenderElement re", script)
        self.assertEqual(out["added"]["mode_label"], "direct_diffuse")
        self.assertEqual(out["added"]["lights"], ["Key"])
        self.assertEqual(out["added"]["lights_list_type"], "include")

    def test_add_validation_writes_nothing(self):
        cases = (
            (dict(type="VRayLightSelect", name="Old"), "already exists"),
            (dict(type="VRayLightSelect", name="x", mode="bogus"), "unknown label"),
            (dict(type="VRayLightSelect", name="x", id_type=1), "VRayCryptomatte only"),
            (dict(type="VRayLightSelect", name="x", props={"multiplyer": 2}), "close: multiplier"),
            (dict(type="VRayLightSelect", name="x", props={"lights": []}), "own parameter"),
        )
        for kwargs, pattern in cases:
            mock = _client(LS_DESCRIBE)
            with patch("maxmcp.tools.vray.client", mock):
                with self.assertRaisesRegex(ValueError, pattern):
                    V.vray_add_render_element(**kwargs)
            self.assertEqual(mock.send_command.call_count, 1, kwargs)

    def test_add_rejects_bad_lights(self):
        describe = dict(LS_DESCRIBE, lights=[{"name": "Nope", "count": 0, "is_light": False},
                                              {"name": "Teapot", "count": 1, "is_light": False},
                                              {"name": "Twin", "count": 2, "is_light": False}])
        mock = _client(describe)
        with patch("maxmcp.tools.vray.client", mock):
            with self.assertRaisesRegex(ValueError, "not found.*not a light.*ambiguous"):
                V.vray_add_render_element("VRayLightSelect", "x", lights=["Nope", "Teapot", "Twin"])

    def test_add_unknown_type_lists_close_matches(self):
        describe = dict(LS_DESCRIBE, **{"class": None, "props": []})
        mock = _client(describe)
        with patch("maxmcp.tools.vray.client", mock):
            with self.assertRaisesRegex(ValueError, "close: VRayLightSelect"):
                V.vray_add_render_element("VRayLightSelekt", "x")

    def test_add_readback_mismatch_raises(self):
        added = {"index": 1, "class": "VRayLightSelect", "name": "LS", "props": [
            {"name": "mode", "type": "Integer", "value": 4},
            {"name": "lights", "type": "ArrayParameter", "value": []},
        ]}
        mock = _client(LS_DESCRIBE, added)
        with patch("maxmcp.tools.vray.client", mock):
            with self.assertRaisesRegex(RuntimeError, "mode.*lights"):
                V.vray_add_render_element("VRayLightSelect", "LS", lights=["Key"], mode=2)

    def test_list_summarizes(self):
        listing = {"vray_version": "7.40.04", "active": True, "elements": [
            {"index": 0, "class": "VRayCryptomatte", "name": "CM", "props": [
                {"name": "enabled", "type": "BooleanClass", "value": True},
                {"name": "filterOn", "type": "BooleanClass", "value": True},
                {"name": "id_type", "type": "Integer", "value": 2}]}]}
        mock = _client(listing)
        with patch("maxmcp.tools.vray.client", mock):
            out = json.loads(V.vray_list_render_elements())
        self.assertEqual(out["elements"][0]["id_type_label"], "node_material_name")
        self.assertNotIn("properties", out["elements"][0])

    def test_remove_is_case_sensitive_and_verified(self):
        listing = {"vray_version": "7.40.04", "active": True, "elements": [
            {"index": 0, "class": "VRayAlpha", "name": "A", "props": []},
            {"index": 1, "class": "VRayAlpha", "name": "LS", "props": []}]}
        mock = _client(listing)
        with patch("maxmcp.tools.vray.client", mock):
            with self.assertRaisesRegex(ValueError, "close: LS"):
                V.vray_remove_render_element("ls")
        mock = _client(listing, {"removed": 1, "remaining": ["A"]})
        with patch("maxmcp.tools.vray.client", mock):
            out = json.loads(V.vray_remove_render_element("LS"))
        self.assertIn("for i in #(1) do", _scripts(mock)[1])
        self.assertEqual(out, {"removed": 1, "remaining": ["A"]})
        mock = _client(listing, {"removed": 0, "remaining": ["A", "LS"]})
        with patch("maxmcp.tools.vray.client", mock):
            with self.assertRaisesRegex(RuntimeError, "removal incomplete"):
                V.vray_remove_render_element("LS")


def _state(buffer="", cast=True, receive=True, primary=True, name="catcher", count=1):
    return {"name": name, "count": count, "buffer": buffer, "primaryVisibility": primary,
            "castShadows": cast, "receiveShadows": receive}


class ObjectPropertyToolTests(unittest.TestCase):
    def test_get_reports_defaults_and_stored_keys(self):
        mock = _client([_state("VRay_Matte_Enable = True\r\nVRay_Matte_Alpha = -1,000000\r\nfoo = 1\r\n")])
        with patch("maxmcp.tools.vray.client", mock):
            out = json.loads(V.vray_get_object_properties(["catcher"]))
        obj = out["objects"][0]
        self.assertIs(obj["properties"]["matte"], True)
        self.assertEqual(obj["properties"]["alpha_contribution"], -1.0)
        self.assertIs(obj["properties"]["shadow_catcher"], False)
        self.assertEqual(obj["stored_vray_keys"], {"VRay_Matte_Enable": "True", "VRay_Matte_Alpha": "-1,000000"})

    def test_get_missing_and_ambiguous(self):
        mock = _client([_state(), _state(name="nope", count=0), _state(name="dup", count=2)])
        with patch("maxmcp.tools.vray.client", mock):
            with self.assertRaisesRegex(ValueError, "'nope' not found.*'dup' is ambiguous"):
                V.vray_get_object_properties(["catcher", "nope", "dup"])

    def test_set_writes_vray_format_and_reads_back(self):
        after = _state("VRay_Matte_Enable = True\r\nVRay_Matte_Alpha = -0,500000\r\nVRay_Matte_Shadows = True\r\n"
                       "VRay_GI_VisibleToGI = False\r\n", cast=False)
        mock = _client([_state()], {"decimal_separator": ","}, [after])
        with patch("maxmcp.tools.vray.client", mock):
            out = json.loads(V.vray_set_object_properties(
                ["catcher"], matte=True, alpha_contribution=-0.5, shadow_catcher=True,
                gi_visibility=False, cast_shadows=False))
        script = _scripts(mock)[1]
        self.assertIn('setUserProp n "VRay_Matte_Enable" "True"', script)
        self.assertIn('setUserProp n "VRay_Matte_Alpha" (mcpVLocal "-0.500000" dsep)', script)
        self.assertIn('setUserProp n "VRay_Matte_Shadows" "True"', script)
        self.assertIn('setUserProp n "VRay_GI_VisibleToGI" "False"', script)
        self.assertIn("n.castShadows = false", script)
        self.assertIn("n.receiveShadows = true", script)
        self.assertIn('undo "MCP V-Ray object properties" on', script)
        self.assertEqual(out["objects"][0]["properties"]["alpha_contribution"], -0.5)
        self.assertEqual(out["float_decimal_separator"], ",")
        self.assertIn("receive_shadows", out["set"])
        self.assertTrue(out["warnings"])

    def test_set_mismatch_raises(self):
        mock = _client([_state()], {"decimal_separator": "."}, [_state("VRay_Matte_Enable = False\r\n")])
        with patch("maxmcp.tools.vray.client", mock):
            with self.assertRaisesRegex(RuntimeError, "catcher.matte: wrote True, read back False"):
                V.vray_set_object_properties(["catcher"], matte=True)

    def test_set_validation(self):
        with self.assertRaisesRegex(ValueError, "between -1 and 1"):
            V.vray_set_object_properties(["catcher"], alpha_contribution=1.5)
        with self.assertRaisesRegex(ValueError, "at least one property"):
            V.vray_set_object_properties(["catcher"])
        mock = _client([_state(name="nope", count=0)])
        with patch("maxmcp.tools.vray.client", mock):
            with self.assertRaisesRegex(ValueError, "not found"):
                V.vray_set_object_properties(["nope"], matte=True)
        self.assertEqual(mock.send_command.call_count, 1)

    def test_shadow_catcher_with_receive_off_warns(self):
        after = _state("VRay_Matte_Shadows = True\r\n", receive=False)
        mock = _client([_state()], {"decimal_separator": "."}, [after])
        with patch("maxmcp.tools.vray.client", mock):
            out = json.loads(V.vray_set_object_properties(["catcher"], shadow_catcher=True, receive_shadows=False))
        self.assertIn("suppresses", out["warnings"][0])


if __name__ == "__main__":
    unittest.main()
