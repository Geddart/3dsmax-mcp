import json
import os
import re
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from maxmcp import path_policy
from maxmcp.path_policy import PathNotAllowedError
from maxmcp.tools import scene_files
from maxmcp.tools.scene_files import (
    VersionedName,
    parse_versioned_stem,
    retarget_version_tokens,
)


class FakeClient:
    native_available = True

    def __init__(self, responses: list) -> None:
        self.responses = list(responses)
        self.calls: list[str] = []

    def send_command(self, command, *args, **kwargs):
        self.calls.append(command)
        if not self.responses:
            raise AssertionError("unexpected extra send_command")
        item = self.responses.pop(0)
        if callable(item):
            item = item(command)
        return {"result": item if isinstance(item, str) else json.dumps(item)}


class _PolicySandbox(unittest.TestCase):
    """Isolate the path policy from the developer's real config."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        local = self.root / "local"
        (local / "3dsmax-mcp").mkdir(parents=True)
        env = patch.dict(os.environ, {"LOCALAPPDATA": str(local), path_policy.ALLOWED_ENV: ""}, clear=False)
        env.start()
        self.addCleanup(env.stop)
        self.scene_dir = self.root / "proj" / "max"
        self.scene_dir.mkdir(parents=True)

    def use(self, responses: list) -> FakeClient:
        fake = FakeClient(responses)
        patcher = patch.object(scene_files, "client", fake)
        patcher.start()
        self.addCleanup(patcher.stop)
        return fake

    def scene_state(self, name: str = "shot_V004.max") -> dict:
        return {"path": str(self.scene_dir) + "\\", "name": name}


class VersionParsingTests(unittest.TestCase):
    def test_parses_underscore_lowercase_and_bare_tokens(self) -> None:
        self.assertEqual(parse_versioned_stem("test_V001"), VersionedName("test", "_", "V", 1, 3))
        self.assertEqual(parse_versioned_stem("shot_v12"), VersionedName("shot", "_", "v", 12, 2))
        self.assertEqual(parse_versioned_stem("R02_SetV005"), VersionedName("R02_Set", "", "V", 5, 3))
        self.assertIsNone(parse_versioned_stem("no_version"))
        self.assertIsNone(parse_versioned_stem("shot_V001_final"))

    def test_padding_kept_and_grows_on_overflow(self) -> None:
        self.assertEqual(VersionedName("a", "_", "V", 5, 3).stem(6), "a_V006")
        self.assertEqual(VersionedName("a", "_", "V", 999, 3).stem(1000), "a_V1000")
        self.assertEqual(VersionedName("a", "", "v", 9, 1).stem(10), "av10")


class RetargetTokenTests(unittest.TestCase):
    def test_old_stem_replaced_everywhere(self) -> None:
        out, how = retarget_version_tokens(
            r"N:\proj\renders\shot_V004\shot_V004_beauty.exr",
            old_stem="shot_V004", new_stem="shot_V005", old_num=4, new_num=5)
        self.assertEqual(out, r"N:\proj\renders\shot_V005\shot_V005_beauty.exr")
        self.assertEqual(how, "stem")

    def test_delimited_tokens_matching_old_number_keep_their_padding(self) -> None:
        out, how = retarget_version_tokens(
            r"N:\out\v04\beauty_V0004.exr", old_stem="shot_V004", new_stem="shot_V005", old_num=4, new_num=5)
        self.assertEqual(out, r"N:\out\v05\beauty_V0005.exr")
        self.assertEqual(how, "token")

    def test_letter_prefixed_and_other_numbers_untouched(self) -> None:
        out, _ = retarget_version_tokens(
            r"N:\Rev004\plate_V002\shot_V004.exr", old_stem=None, new_stem="x_V005", old_num=4, new_num=5)
        self.assertEqual(out, r"N:\Rev004\plate_V002\shot_V005.exr")

    def test_out_of_sync_basename_token_is_forced(self) -> None:
        out, how = retarget_version_tokens(
            r"N:\r\V002\shot_V002.exr", old_stem="shot_V004", new_stem="shot_V005", old_num=4, new_num=5)
        self.assertEqual(out, r"N:\r\V002\shot_V005.exr")
        self.assertEqual(how, "basename_token")

    def test_none_already_and_empty(self) -> None:
        self.assertEqual(retarget_version_tokens(r"N:\r\beauty.exr", old_stem="a_V1", new_stem="a_V2",
                                                 old_num=1, new_num=2), (r"N:\r\beauty.exr", "none"))
        self.assertEqual(retarget_version_tokens(r"N:\r\a_V001.exr", old_stem=None, new_stem="a_V001",
                                                 old_num=None, new_num=1), (r"N:\r\a_V001.exr", "already"))
        self.assertEqual(retarget_version_tokens("", old_stem=None, new_stem="a", old_num=None, new_num=1),
                         ("", "empty"))


class PlanTargetTests(_PolicySandbox):
    def test_next_version_in_scene_folder(self) -> None:
        target, ver = scene_files._plan_versioned_target(
            scene_path=str(self.scene_dir) + "\\", scene_name="shot_v009.max", path=None, base_name=None)
        self.assertEqual(target, str(self.scene_dir / "shot_v010.max"))
        self.assertEqual(ver.num, 10)

    def test_untitled_scene_needs_a_path(self) -> None:
        with self.assertRaises(ValueError):
            scene_files._plan_versioned_target(scene_path="", scene_name="", path=None, base_name=None)
        target, ver = scene_files._plan_versioned_target(
            scene_path="", scene_name="", path=str(self.root / "x" / "t_V001.max"), base_name=None)
        self.assertEqual(target, str(self.root / "x" / "t_V001.max"))
        self.assertEqual(ver.num, 1)

    def test_new_base_continues_after_highest_existing(self) -> None:
        folder = self.root / "out"
        folder.mkdir()
        for name in ("lay_V002.max", "lay_v007.max", "layout_V020.max", "lay_V003.max.bak"):
            (folder / name).write_bytes(b"")
        target, ver = scene_files._plan_versioned_target(
            scene_path=str(self.scene_dir) + "\\", scene_name="shot_V004.max", path=str(folder), base_name="lay")
        self.assertEqual(target, str(folder / "lay_V008.max"))

    def test_base_name_rejects_folders(self) -> None:
        with self.assertRaises(ValueError):
            scene_files._plan_versioned_target(
                scene_path=str(self.scene_dir) + "\\", scene_name="a_V001.max", path=None, base_name=r"..\evil")


def staging_path(script: str) -> Path:
    match = re.search(r'local outPath = "((?:[^"\\]|\\.)*)"', script)
    assert match, "no outPath in the export script"
    return Path(match.group(1).replace("\\\\", "\\"))


class ExportGeometryTests(_PolicySandbox):
    def test_path_outside_allowed_roots_is_refused_before_export(self) -> None:
        fake = self.use([self.scene_state()])
        with self.assertRaises(PathNotAllowedError):
            scene_files.export_geometry(path=str(self.root / "elsewhere" / "geo.obj"), names=["Box001"])
        self.assertEqual(len(fake.calls), 1)  # only the scene-state read

    def test_existing_file_refused_without_overwrite(self) -> None:
        out = self.scene_dir / "geo.obj"
        out.write_text("old")
        self.use([self.scene_state()])
        with self.assertRaises(FileExistsError):
            scene_files.export_geometry(path=str(out), names=["Box001"])

    def test_export_script_and_totals(self) -> None:
        out = self.scene_dir / "exports" / "geo.json"

        def max_writes(command: str) -> dict:
            staged = staging_path(command)
            staged.parent.mkdir(parents=True, exist_ok=True)
            staged.write_text('{"objects":[]}')
            return {
                "objects": [
                    {"name": 'Box "A"', "handle": 7, "vertices": 8, "faces": 12, "uv_vertices": 0, "normals": True},
                    {"name": "B", "handle": 9, "vertices": 4, "faces": 2, "uv_vertices": 4, "normals": True},
                ],
                "skipped": ["Camera01"],
                "warnings": ['Box "A" has no map channel 1; UVs omitted'],
                "system_units": "centimeters",
            }

        fake = self.use([self.scene_state("shot_V004.max"), max_writes])
        res = scene_files.export_geometry(path=str(out), names=['Box "A"'], handles=[9], format="JSON",
                                          space="local", precision=7)
        script = fake.calls[1]
        staged = staging_path(script)
        self.assertEqual(staged.parent, out.parent)
        self.assertTrue(staged.name.startswith("geo.json.") and staged.name.endswith(".mcptmp"))
        self.assertFalse(staged.exists())  # renamed onto the target
        self.assertIn(r'#("Box \"A\"")', script)
        self.assertIn("#(9)", script)
        self.assertIn('local fmt = ".7g"', script)
        self.assertIn("local isLocal = true", script)
        self.assertIn("local isObj = false", script)
        self.assertIn('mode:"wt"', script)
        # Safe mode refuses any command containing these names (live 2026-10-12).
        for blocked in ("doscommand", "shelllaunch", "deletefile", "python.execute", "createfile"):
            self.assertNotIn(blocked, script.lower())
        self.assertIn("catch (writeErr = getCurrentException())", script)
        self.assertEqual((res["object_count"], res["vertex_count"], res["face_count"]), (2, 12, 14))
        self.assertEqual(res["file_size"], out.stat().st_size)
        self.assertTrue(any("Camera01" in w for w in res["warnings"]))

    def test_failed_export_keeps_the_previous_file_and_cleans_the_temp(self) -> None:
        # Regression (review 2026-10-12): an exception mid-export used to leave a partial
        # file at the target (an overwrite destroyed the old one) and leak the stream/mesh.
        out = self.scene_dir / "geo.obj"
        out.write_text("previous export")

        def max_fails(command: str) -> dict:
            staging_path(command).write_text("partial")
            return {"error": "Export failed; the target was not touched: -- disk full"}

        fake = self.use([self.scene_state(), max_fails])
        with self.assertRaisesRegex(RuntimeError, "disk full"):
            scene_files.export_geometry(path=str(out), names=["Box001"], overwrite=True)
        script = fake.calls[1]
        self.assertIn("if m != undefined do try (delete m) catch ()", script)
        self.assertIn("if f != undefined do try (close f) catch ()", script)
        self.assertEqual(out.read_text(), "previous export")
        self.assertEqual([p.name for p in self.scene_dir.iterdir()], ["geo.obj"])

    def test_argument_validation(self) -> None:
        for kwargs in ({"names": []}, {"names": ["a"], "format": "fbx"}, {"names": ["a"], "space": "pivot"},
                       {"names": ["a"], "precision": 0}):
            with self.assertRaises(ValueError):
                scene_files.export_geometry(path=str(self.scene_dir / "g.obj"), **kwargs)


class SaveVersionedTests(_PolicySandbox):
    def read_state(self, name="shot_V004.max", output="", vray=None, elements=None) -> dict:
        return {"path": str(self.scene_dir) + "\\", "name": name, "render_output": output,
                "renderer": "V_Ray_7", "is_vray": vray is not None, "vray": vray or {},
                "elements": elements or []}

    def test_existing_next_version_is_refused_loudly(self) -> None:
        (self.scene_dir / "shot_V005.max").write_bytes(b"")
        (self.scene_dir / "shot_V006.max").write_bytes(b"")
        fake = self.use([self.read_state()])
        with self.assertRaises(FileExistsError) as ctx:
            scene_files.save_scene_versioned()
        self.assertIn("shot_V005.max", str(ctx.exception))
        self.assertIn("highest existing version: 6", str(ctx.exception))
        self.assertEqual(len(fake.calls), 1)

    def test_target_outside_allowed_roots_refused(self) -> None:
        fake = self.use([self.read_state()])
        with self.assertRaises(PathNotAllowedError):
            scene_files.save_scene_versioned(path=str(self.root / "other"))
        self.assertEqual(len(fake.calls), 1)

    def test_happy_path_sets_render_paths_before_saving(self) -> None:
        out_old = str(self.root / "renders" / "shot_V004" / "shot_V004_.exr")
        raw_old = str(self.root / "renders" / "shot_V004" / "raw_V004.vrimg")
        target = self.scene_dir / "shot_V005.max"
        out_new = out_old.replace("V004", "V005")
        raw_new = raw_old.replace("V004", "V005")

        def apply(command: str) -> dict:
            target.write_bytes(b"max")
            return {"path": str(self.scene_dir) + "\\", "name": "shot_V005.max", "render_output": out_new,
                    "vray": {"output_rawFileName": raw_new, "output_splitfilename": ""}, "elements": []}

        fake = self.use([
            self.read_state(output=out_old, vray={"output_rawFileName": raw_old, "output_splitfilename": ""}),
            apply,
        ])
        res = scene_files.save_scene_versioned()
        script = fake.calls[1]
        self.assertIn(scene_files._ms_str(str(target)), script)
        self.assertIn(f"if true do rendOutputFilename = {scene_files._ms_str(out_new)}", script)
        self.assertIn("#(#output_rawFileName)", script)
        self.assertLess(script.index("rendOutputFilename = "), script.index("saveMaxFile newPath"))
        self.assertEqual(res["new_path"], str(target))
        self.assertEqual(res["version"], 5)
        self.assertEqual(res["version_label"], "V005")
        self.assertEqual(res["render_output"], {"old": out_old, "new": out_new})
        self.assertEqual(res["vray_output"]["output_rawFileName"]["new"], raw_new)
        # Regression (review 2026-10-12): every path write sits inside the guard that
        # restores them, GPU read-only mirrors fall back to V_Ray_settings, and Render
        # Setup is reopened on every exit.
        guard = script.index("try (\n                if true do rendOutputFilename")
        self.assertLess(guard, script.index("append vHosts (mcpSfVSet r vProps[i] vVals[i])"))
        self.assertLess(script.index("ok = saveMaxFile newPath quiet:true"), script.index("failMsg = getCurrentException()"))
        self.assertIn("if sub != undefined and (isProperty sub p) then (setProperty sub p v; sub) else throw()", script)
        self.assertIn("for i = 1 to vHosts.count do try (setProperty vHosts[i] vProps[i] oldV[i]) catch ()", script)
        self.assertGreater(script.index("if dlgOpen do renderSceneDialog.open()"),
                           script.index("render paths restored"))
        for blocked in ("doscommand", "shelllaunch", "deletefile", "python.execute", "createfile"):
            self.assertNotIn(blocked, script.lower())

    def test_readback_mismatch_raises(self) -> None:
        target = self.scene_dir / "shot_V005.max"

        def apply(command: str) -> dict:
            target.write_bytes(b"max")
            return {"path": str(self.scene_dir) + "\\", "name": "shot_V005.max",
                    "render_output": "something else", "vray": {}, "elements": []}

        self.use([self.read_state(output=r"N:\r\shot_V004.exr"), apply])
        with self.assertRaises(RuntimeError):
            scene_files.save_scene_versioned()


class SceneSetupTests(unittest.TestCase):
    STATE = {"units": "centimeters", "system_scale": 1, "display_type": "metric", "metric_type": "meters",
             "us_type": "ft_Frac_In", "frame_start": 0, "frame_end": 100, "fps": 30, "render_width": 1280,
             "render_height": 720, "pixel_aspect": 1}

    def use(self, current: dict) -> FakeClient:
        fake = FakeClient([{"previous": self.STATE, "current": current}])
        patcher = patch.object(scene_files, "client", fake)
        patcher.start()
        self.addCleanup(patcher.stop)
        return fake

    def test_body_order_and_readback(self) -> None:
        current = dict(self.STATE, units="millimeters", fps=25, frame_start=10, frame_end=250,
                       render_width=1920, render_height=1080, pixel_aspect=1.25)
        fake = self.use(current)
        res = scene_files.scene_setup(units="mm", fps=25, frame_range=[10, 250], render_size=[1920, 1080],
                                      pixel_aspect=1.25)
        script = fake.calls[0]
        self.assertIn("units.SystemType = #millimeters", script)
        self.assertLess(script.index("frameRate = 25"), script.index("animationRange = interval 10 250"))
        self.assertNotIn("interval 10f", script)
        self.assertIn("rendLockImageAspectRatio = false", script)
        self.assertIn("local touchRender = true", script)
        self.assertLess(script.index("rendLockImageAspectRatio = false"), script.index("renderWidth = 1920"))
        self.assertLess(script.index("renderPixelAspect = 1.25"), script.index("rendLockImageAspectRatio = lockImg"))
        self.assertIn("renderPixelAspect = 1.25", script)
        self.assertEqual(res["previous"]["units"], "centimeters")
        self.assertIn("units", res["changed"])
        self.assertTrue(res["warnings"])

    def test_mismatch_fails_loudly(self) -> None:
        self.use(dict(self.STATE, render_width=1280))
        with self.assertRaises(RuntimeError) as ctx:
            scene_files.scene_setup(render_size=[1920, 720])
        self.assertIn("render_width", str(ctx.exception))

    def test_validation(self) -> None:
        for kwargs in ({}, {"units": "parsec"}, {"display_units": "furlong"}, {"fps": 23.976},
                       {"frame_range": [5, 5]}, {"render_size": [0, 10]}, {"pixel_aspect": -1}):
            with self.assertRaises(ValueError):
                scene_files.scene_setup(**kwargs)

    def test_display_units_mapping(self) -> None:
        fake = self.use(dict(self.STATE, display_type="us", us_type="Dec_Ft"))
        scene_files.scene_setup(display_units="ft")
        self.assertIn("units.DisplayType = #us", fake.calls[0])
        self.assertIn("units.USType = #dec_ft", fake.calls[0])
        self.assertIn("local touchRender = false", fake.calls[0])


if __name__ == "__main__":
    unittest.main()
