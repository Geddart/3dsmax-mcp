import json
import math
import os
import struct
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from maxmcp import path_policy
from maxmcp.tools import camera as cm


def bits(v: float) -> str:
    return str(struct.unpack("<i", struct.pack("<f", float(v)))[0])


def p3(v) -> str:
    return ",".join(bits(c) for c in v)


def state_string(*, cls="Physical", right=(1, 0, 0), up=(0, 1, 0), back=(0, 0, 1), pos=(0, 0, 0),
                 fov=53.130102, w=400, h=200, pa=1.0, hs=0.0, vs=0.0, has_target=False,
                 extra: dict | None = None) -> str:
    s = (f"cls={cls}|r={p3(right)}|u={p3(up)}|b={p3(back)}|p={p3(pos)}|fov={bits(fov)}"
         f"|W={w}|H={h}|pa={bits(pa)}|frame={bits(0.0)}|units=centimeters"
         f"|hastarget={'true' if has_target else 'false'}|animated=false")
    if cls == "Physical":
        s += (f"|horizontal_shift=f{bits(hs)}|vertical_shift=f{bits(vs)}|film_width_mm=f{bits(36.0)}"
              f"|focal_length_mm=f{bits(36.0)}|lens_breathing_amount=f{bits(0.0)}|distortion_type=i0"
              f"|clip_on=bfalse|clip_near=f{bits(0.0)}|clip_far=f{bits(1000.0)}")
    for key, value in (extra or {}).items():
        s += f"|{key}={value}"
    return s


class QueueClient:
    native_available = True

    def __init__(self, responses):
        self.responses = list(responses)
        self.sent: list[str] = []

    def send_command(self, command, *args, **kwargs):
        self.sent.append(command)
        if not self.responses:
            raise AssertionError(f"unexpected command: {command[:120]}")
        return {"result": self.responses.pop(0)}


class BasisTests(unittest.TestCase):
    def test_orthonormal_basis_is_accepted_unchanged(self):
        r, u, b, dev, corrected = cm.orthonormalize_basis([1, 0, 0], [0, 0, 1], [0, -1, 0])
        self.assertFalse(corrected)
        self.assertAlmostEqual(dev, 0.0)
        for got, want in zip((r, u, b), ((1, 0, 0), (0, 0, 1), (0, -1, 0))):
            for g, x in zip(got, want):
                self.assertAlmostEqual(g, x)

    def test_small_error_is_reorthonormalised_keeping_view_direction(self):
        r, u, b, dev, corrected = cm.orthonormalize_basis([1.0, 0.004, 0.0], [0.0, 0.002, 1.0], [0.0, -1.0, 0.0])
        self.assertTrue(corrected)
        self.assertGreater(dev, cm.ORTHO_TOLERANCE)
        self.assertLess(cm.basis_deviation(r, u, b), 1e-12)
        self.assertEqual(b, (0.0, -1.0, 0.0))

    def test_degenerate_left_handed_and_skewed_bases_are_rejected(self):
        with self.assertRaises(ValueError):
            cm.orthonormalize_basis([0, 0, 0], [0, 1, 0], [0, 0, 1])
        with self.assertRaises(ValueError):
            cm.orthonormalize_basis([1, 0, 0], [1, 0, 0], [0, 0, 1])
        with self.assertRaisesRegex(ValueError, "left-handed"):
            cm.orthonormalize_basis([-1, 0, 0], [0, 1, 0], [0, 0, 1])
        with self.assertRaisesRegex(ValueError, "not orthonormal"):
            cm.orthonormalize_basis([1, 0.3, 0], [0, 1, 0], [0, 0, 1])
        with self.assertRaises(ValueError):
            cm.orthonormalize_basis([1, 0, float("nan")], [0, 1, 0], [0, 0, 1])

    def test_look_at_has_no_roll_and_handles_straight_down(self):
        r, u, b, warnings = cm.look_at_basis([0, -10, 0], [0, 0, 0])
        self.assertEqual(warnings, [])
        self.assertAlmostEqual(r[2], 0.0)
        self.assertAlmostEqual(u[2], 1.0)
        self.assertAlmostEqual(b[1], -1.0)
        r, u, b, warnings = cm.look_at_basis([0, 0, 10], [0, 0, 0])
        self.assertTrue(warnings)
        self.assertLess(cm.basis_deviation(r, u, b), 1e-12)
        self.assertGreater(cm._dot(cm._cross(r, u), b), 0.99)
        with self.assertRaises(ValueError):
            cm.look_at_basis([1, 2, 3], [1, 2, 3])


class LensAndProjectionTests(unittest.TestCase):
    def test_lens_conversions_round_trip(self):
        self.assertAlmostEqual(cm.f_px_from_fov(cm.fov_from_f_px(1234.5, 1920), 1920), 1234.5)
        self.assertAlmostEqual(cm.fov_from_focal_mm(36.0, 36.0), 53.13010235415598)
        self.assertAlmostEqual(cm.focal_mm_from_fov(cm.fov_from_focal_mm(50.0, 36.0), 36.0), 50.0)
        with self.assertRaises(ValueError):
            cm.f_px_from_fov(180.0, 100)

    def cam(self, **kw):
        cam = {"position": [0, 0, 0], "right": [1, 0, 0], "up": [0, 1, 0], "back": [0, 0, 1],
               "fov_deg": cm.fov_from_focal_mm(36.0, 36.0), "render_width": 400, "render_height": 200,
               "pixel_aspect": 1.0, "shift_x": 0.0, "shift_y": 0.0}
        cam.update(kw)
        return cam

    def test_projection_matches_measured_scanline_markers(self):
        # Values measured live: f_px 400 at 400x200, markers at these pixels (exp 2026-10-12).
        pts = cm.project_camera_points(self.cam(), [[0, 0, -100], [20, 10, -100], [-30, -12, -80]])
        for got, want in zip(pts, [(200, 100), (280, 60), (50, 160)]):
            self.assertAlmostEqual(got["x"], want[0], places=6)
            self.assertAlmostEqual(got["y"], want[1], places=6)
            self.assertTrue(got["in_frame"])

    def test_shift_is_a_fraction_of_render_width_on_both_axes(self):
        pts = cm.project_camera_points(self.cam(shift_x=0.1), [[0, 0, -100]])
        self.assertAlmostEqual(pts[0]["x"], 240.0)
        pts = cm.project_camera_points(self.cam(render_height=300, shift_y=0.1), [[0, 0, -100]])
        self.assertAlmostEqual(pts[0]["y"], 150.0 - 40.0)
        self.assertEqual(cm.principal_point(self.cam(shift_x=0.05, shift_y=-0.02)), (220.0, 108.0))

    def test_pixel_aspect_scales_vertical_axis(self):
        pts = cm.project_camera_points(self.cam(pixel_aspect=1.5), [[20, 10, -100]])
        self.assertAlmostEqual(pts[0]["x"], 280.0)
        self.assertAlmostEqual(pts[0]["y"], 100.0 - 60.0)

    def test_behind_outside_and_clipped_flags(self):
        pts = cm.project_camera_points(self.cam(near=10.0, far=500.0),
                                       [[0, 0, 50], [1000, 0, -100], [0, 0, -5], [0, 0, -100]])
        self.assertTrue(pts[0]["behind"])
        self.assertIsNone(pts[0]["x"])
        self.assertFalse(pts[0]["in_frame"])
        self.assertFalse(pts[1]["behind"])
        self.assertFalse(pts[1]["in_frame"])
        self.assertTrue(pts[2]["clipped"])
        self.assertFalse(pts[3]["clipped"])
        self.assertNotIn("clipped", cm.project_camera_points(self.cam(), [[0, 0, -1]])[0])

    def test_project_points_tool_accepts_camera_json(self):
        result = cm.project_points(self.cam(name="j"), [[0, 0, -100]])
        self.assertEqual(result["points"][0]["x"], 200.0)
        self.assertAlmostEqual(result["f_px"], 400.0)


class FramingTests(unittest.TestCase):
    def test_frame_rect_height_fit_matches_live_viewport(self):
        # Live: 1388x601 viewport, 400x200 render -> frame x 93..1295, full height.
        self.assertEqual(cm.frame_rect_in_viewport(1388, 601, 400, 200), (93.0, 0.0, 1202.0, 601.0))

    def test_frame_rect_width_fit(self):
        x, y, w, h = cm.frame_rect_in_viewport(1388, 601, 1000, 400)
        self.assertEqual((x, w), (0.0, 1388.0))
        self.assertAlmostEqual(h, 555.2)
        self.assertAlmostEqual(y, (601 - 555.2) / 2)

    def test_capture_size_resolution(self):
        self.assertEqual(cm.resolve_capture_size(None, 1920, 1080), (1920, 1080))
        self.assertEqual(cm.resolve_capture_size(960, 1920, 1080), (960, 540))
        self.assertEqual(cm.resolve_capture_size([960, 540], 1920, 1080), (960, 540))
        self.assertEqual(cm.resolve_capture_size("960x540", 1920, 1080), (960, 540))
        with self.assertRaisesRegex(ValueError, "render aspect"):
            cm.resolve_capture_size([960, 600], 1920, 1080)
        with self.assertRaises(ValueError):
            cm.resolve_capture_size([4], 1920, 1080)


class TransportTests(unittest.TestCase):
    def test_maxscript_floats_are_locale_free_fixed_point(self):
        self.assertEqual(cm._msf(4.5), "4.5")
        self.assertEqual(cm._msf(-0.0), "0.0")
        self.assertEqual(cm._msf(1e-12), "0.0")
        self.assertEqual(cm._msf(2.0), "2.0")
        self.assertEqual(cm._msf(-1234.5678), "-1234.5678")
        self.assertNotIn("e", cm._msf(1e20))
        self.assertEqual(cm._msp3([1.5, -2.25, 3]), "[1.5,-2.25,3.0]")
        with self.assertRaises(ValueError):
            cm._msf(float("inf"))

    def test_float_bits_round_trip_including_negative(self):
        for v in (0.0, 1.0, -1.0, 53.1301, -276.8, 1e-7):
            self.assertAlmostEqual(cm._from_bits(bits(v)), struct.unpack("<f", struct.pack("<f", v))[0])
        self.assertEqual(cm._from_bits(str(0xBF800000)), -1.0)  # unsigned form of -1.0

    def test_state_parse_and_export_dict(self):
        state = cm._parse_state(state_string(hs=10.0, vs=-5.0, pos=(1.5, -2.5, 3.0)), "c")
        self.assertEqual(state["class"], "Physical")
        self.assertEqual(state["render_width"], 400)
        cam, warnings = cm.camera_dict_from_state("c", state)
        self.assertEqual(warnings, [])
        self.assertEqual(cam["position"], [1.5, -2.5, 3.0])
        self.assertAlmostEqual(cam["shift_x"], 0.1)
        self.assertAlmostEqual(cam["shift_y"], -0.05)
        self.assertAlmostEqual(cam["f_px"], 400.0, places=3)
        self.assertEqual(cam["principal_point"], [240.0, 120.0])
        self.assertIsNone(cam["near"])
        self.assertEqual(cam["schema"], cm.SCHEMA)

    def test_state_parse_errors(self):
        with self.assertRaisesRegex(ValueError, "not found"):
            cm._parse_state("ERR=not_found", "x")
        with self.assertRaisesRegex(ValueError, "not a camera"):
            cm._parse_state("ERR=not_camera:Box", "x")

    def test_non_pinhole_settings_warn(self):
        raw = state_string(extra={"vertical_tilt_correction": "f" + bits(0.2)})
        raw = raw.replace("distortion_type=i0", "distortion_type=i1")
        _, warnings = cm.camera_dict_from_state("c", cm._parse_state(raw, "c"))
        self.assertTrue(any("vertical_tilt_correction" in w for w in warnings))
        self.assertTrue(any("distortion_type" in w for w in warnings))

    def test_read_script_lists_properties_comma_separated(self):
        script = cm._read_script('we"ird')
        self.assertIn('getNodeByName "we\\"ird" exact:true', script)
        self.assertIn("#horizontal_shift, #vertical_shift", script)
        self.assertIn("bit.floatAsInt", script)


class SetCameraTests(unittest.TestCase):
    def run_set(self, responses, **kwargs):
        fake = QueueClient(responses)
        with patch.object(cm, "client", fake):
            return cm.apply_camera(**kwargs), fake

    def test_create_physical_writes_transform_lens_shift_and_reads_back(self):
        fov = 50.0
        after = state_string(right=(1, 0, 0), up=(0, 0, 1), back=(0, -1, 0), pos=(10, -200, 50),
                             fov=fov, w=640, h=360, hs=5.0, vs=-2.0)
        result, fake = self.run_set(["ERR=not_found", "640", "360", "OK", after],
                                    name="cam", position=[10, -200, 50], right=[1, 0, 0], up=[0, 0, 1],
                                    back=[0, -1, 0], fov_deg=fov, shift_x=0.05, shift_y=-0.02)
        script = fake.sent[3]
        self.assertIn('Physical name:"cam" targeted:false', script)
        self.assertIn("c.transform = matrix3 [1.0,0.0,0.0] [0.0,0.0,1.0] [0.0,-1.0,0.0] [10.0,-200.0,50.0]", script)
        self.assertIn("c.horizontal_shift = 5.0", script)
        self.assertIn("c.vertical_shift = -2.0", script)
        self.assertIn("c.lens_breathing_amount = 0.0", script)
        self.assertIn("c.film_width_mm = 36.0", script)
        self.assertIn('undo "MCP set camera" on', script)
        self.assertTrue(result["created"])
        self.assertAlmostEqual(result["camera"]["fov_deg"], fov, places=5)

    def test_readback_mismatch_raises(self):
        after = state_string(fov=40.0, w=640, h=360)
        with self.assertRaisesRegex(cm.CameraReadbackError, "fov_deg"):
            self.run_set(["ERR=not_found", "640", "360", "OK", after],
                         name="cam", position=[0, 0, 0], right=[1, 0, 0], up=[0, 1, 0], back=[0, 0, 1],
                         fov_deg=50.0)

    def test_position_mismatch_raises(self):
        after = state_string(pos=(0, 0, 1), w=640, h=360)
        with self.assertRaisesRegex(cm.CameraReadbackError, "position.z"):
            self.run_set(["ERR=not_found", "640", "360", "OK", after],
                         name="cam", position=[0, 0, 0], right=[1, 0, 0], up=[0, 1, 0], back=[0, 0, 1])

    def test_f_px_uses_render_width_and_shift_px_converts(self):
        f_px = 1000.0
        fov = cm.fov_from_f_px(f_px, 1920)
        after = state_string(fov=fov, w=1920, h=1080, hs=100 * 19.2 / 1920, vs=-100 * 10.8 / 1920)
        result, fake = self.run_set(["ERR=not_found", "1920", "1080", bits(1.0), "OK", after],
                                    name="cam", position=[0, 0, 0], right=[1, 0, 0], up=[0, 1, 0],
                                    back=[0, 0, 1], f_px=f_px, shift_x_px=19.2, shift_y_px=10.8)
        self.assertIn("renderPixelAspect", fake.sent[3])
        self.assertAlmostEqual(result["camera"]["f_px"], f_px, places=2)
        self.assertAlmostEqual(result["camera"]["principal_point"][0], 960 + 19.2, places=3)
        self.assertAlmostEqual(result["camera"]["principal_point"][1], 540 + 10.8, places=3)

    def test_new_camera_pixel_shift_uses_scene_pixel_aspect(self):
        # Regression (review 2026-10-12): a new camera assumed square pixels, so
        # shift_y_px=10 at renderPixelAspect 1.5 became a 15 px shift.
        after = state_string(w=400, h=200, pa=1.5, vs=-100 * 10 / (400 * 1.5))
        result, fake = self.run_set(["ERR=not_found", "400", "200", bits(1.5), "OK", after],
                                    name="cam", position=[0, 0, 0], right=[1, 0, 0], up=[0, 1, 0],
                                    back=[0, 0, 1], shift_y_px=10.0)
        expected = -100.0 * 10.0 / (400 * 1.5)
        line = next(x for x in fake.sent[4].splitlines() if x.startswith("c.vertical_shift = "))
        self.assertAlmostEqual(float(line.split("=")[1]), expected, places=8)
        self.assertAlmostEqual(result["camera"]["principal_point"][1], 110.0, places=3)

    def test_render_size_is_written_guarded_and_verified(self):
        # Regression (review 2026-10-12): render size was written without releasing the
        # aspect lock / closing Render Setup and never compared after the write.
        existing = state_string(w=400, h=200)
        good = state_string(w=800, h=600)
        result, fake = self.run_set([existing, "OK", good], name="cam", render_width=800, render_height=600,
                                    set_render_size=True)
        script = fake.sent[1]
        self.assertIn("rendLockImageAspectRatio = false", script)
        self.assertIn("if mcpDlg do renderSceneDialog.close()", script)
        self.assertIn("try (renderWidth = 800; renderHeight = 600) catch (mcpErr = getCurrentException())", script)
        self.assertLess(script.index("rendLockImageAspectRatio = mcpLock"), script.index("if mcpErr != undefined do throw"))
        self.assertEqual(result["camera"]["render_width"], 800)
        stale = state_string(w=800, h=400)
        with self.assertRaisesRegex(cm.CameraReadbackError, "render size"):
            self.run_set([existing, "OK", stale], name="cam", render_width=800, render_height=600,
                         set_render_size=True)

    def test_clip_false_turns_clipping_off_and_is_verified(self):
        on = {"clip_on": "btrue"}
        existing = state_string(extra=on)
        off = state_string(extra={"clip_on": "bfalse"})
        result, fake = self.run_set([existing, "OK", off], name="cam", clip=False)
        self.assertIn("c.clip_on = false", fake.sent[1])
        with self.assertRaisesRegex(cm.CameraReadbackError, "clip_on"):
            self.run_set([existing, "OK", state_string(extra=on)], name="cam", clip=False)
        with self.assertRaisesRegex(ValueError, "clip=False"):
            self.run_set([existing], name="cam", clip=False, near=1.0)

    def test_argument_validation(self):
        with self.assertRaisesRegex(ValueError, "only one"):
            self.run_set(["ERR=not_found", "640", "360"], name="c", position=[0, 0, 0], target=[0, 1, 0],
                         fov_deg=40, f_px=500)
        with self.assertRaisesRegex(ValueError, "orientation"):
            self.run_set(["ERR=not_found", "640", "360"], name="c", position=[0, 0, 0])
        with self.assertRaisesRegex(ValueError, "not both"):
            self.run_set(["ERR=not_found", "640", "360"], name="c", position=[0, 0, 0], target=[0, 1, 0],
                         right=[1, 0, 0], up=[0, 1, 0], back=[0, 0, 1])
        with self.assertRaisesRegex(ValueError, "far must be greater"):
            self.run_set(["ERR=not_found", "640", "360"], name="c", position=[0, 0, 0], target=[0, 1, 0],
                         near=10, far=5)
        with self.assertRaisesRegex(ValueError, "not found and create=False"):
            self.run_set(["ERR=not_found"], name="c", create=False)

    def test_shift_on_standard_camera_is_rejected(self):
        existing = state_string(cls="Freecamera", w=640, h=360)
        with self.assertRaisesRegex(ValueError, "no lens shift"):
            self.run_set([existing], name="c", shift_x=0.1)

    def test_targeted_roll_mismatch_raises(self):
        before = state_string(cls="Targetcamera", w=640, h=360, has_target=True,
                              right=(1, 0, 0), up=(0, 0, 1), back=(0, -1, 0))
        a = math.radians(20)
        right = [math.cos(a), 0, math.sin(a)]
        up = [-math.sin(a), 0, math.cos(a)]
        after = state_string(cls="Targetcamera", w=640, h=360, has_target=True,
                             right=(1, 0, 0), up=(0, 0, 1), back=(0, -1, 0))
        with self.assertRaisesRegex(cm.CameraReadbackError, "untarget"):
            self.run_set([before, "OK", after], name="c", position=[0, 0, 0], right=right, up=up, back=[0, -1, 0])


class ImportExportTests(unittest.TestCase):
    def test_export_writes_json_through_path_policy(self):
        raw = state_string(w=640, h=360)
        out = path_policy.temp_root() / "test_camera_export.json"
        self.addCleanup(lambda: out.exists() and out.unlink())
        fake = QueueClient([raw, ""])
        with patch.object(cm, "client", fake):
            result = cm.export_camera("c", path=str(out))
        self.assertEqual(Path(result["file"]), out)
        data = json.loads(out.read_text(encoding="utf-8"))
        self.assertEqual(data["render_width"], 640)
        self.assertEqual(data["right"], [1.0, 0.0, 0.0])

    def test_export_outside_allowed_dirs_is_refused(self):
        fake = QueueClient([state_string(), ""])
        with patch.object(cm, "client", fake), patch.dict(os.environ, {path_policy.ALLOWED_ENV: ""}):
            with patch.object(path_policy, "configured_dirs", return_value=[]):
                with self.assertRaises(path_policy.PathNotAllowedError):
                    cm.export_camera("c", path=str(Path(tempfile.gettempdir()).parent / "nope" / "c.json"))

    def test_import_uses_json_fields(self):
        cam = {"name": "src", "class": "Physical", "position": [1, 2, 3], "right": [1, 0, 0], "up": [0, 0, 1],
               "back": [0, -1, 0], "fov_deg": 45.0, "render_width": 640, "render_height": 360,
               "shift_x": 0.02, "shift_y": 0.01, "near": None, "far": None, "film_width_mm": 24.0}
        captured = {}

        def fake_apply(**kwargs):
            captured.update(kwargs)
            return {"camera": {}}

        with patch.object(cm, "apply_camera", fake_apply):
            cm.import_camera(data=json.dumps(cam), name="dst")
        self.assertEqual(captured["name"], "dst")
        self.assertEqual(captured["fov_deg"], 45.0)
        self.assertEqual(captured["shift_x"], 0.02)
        self.assertEqual(captured["film_width_mm"], 24.0)
        self.assertEqual(captured["camera_class"], "Physical")
        # near/far null at export = clipping off (review 2026-10-12)
        self.assertIs(captured["clip"], False)
        self.assertIsNone(captured["pixel_aspect"])

    def test_import_carries_pixel_aspect_and_keeps_clipping_when_keys_absent(self):
        cam = {"position": [0, 0, 0], "right": [1, 0, 0], "up": [0, 1, 0], "back": [0, 0, 1],
               "fov_deg": 40.0, "render_width": 400, "render_height": 200, "pixel_aspect": 1.5}
        captured = {}
        with patch.object(cm, "apply_camera", lambda **kw: captured.update(kw) or {}):
            cm.import_camera(data=cam, name="x", set_render_size=True)
        self.assertEqual(captured["pixel_aspect"], 1.5)
        self.assertIsNone(captured["clip"])
        self.assertTrue(captured["set_render_size"])

    def test_pixel_aspect_mismatch_warns_without_set_render_size(self):
        existing = state_string(w=400, h=200, pa=1.0)
        fake = QueueClient([existing, "OK", existing])
        with patch.object(cm, "client", fake):
            result = cm.apply_camera(name="cam", pixel_aspect=1.5)
        self.assertTrue(any("pixel_aspect 1.5" in w for w in result["warnings"]))
        self.assertNotIn("renderPixelAspect", fake.sent[1])
        written = state_string(w=400, h=200, pa=1.5)
        fake = QueueClient([existing, "OK", written])
        with patch.object(cm, "client", fake):
            result = cm.apply_camera(name="cam", pixel_aspect=1.5, render_width=400, render_height=200,
                                     set_render_size=True)
        self.assertIn("renderPixelAspect = 1.5", fake.sent[1])
        self.assertFalse(any("pixel_aspect" in w for w in result["warnings"]))

    def test_import_f_px_only_and_validation(self):
        cam = {"position": [0, 0, 0], "right": [1, 0, 0], "up": [0, 1, 0], "back": [0, 0, 1],
               "f_px": 400.0, "render_width": 400, "render_height": 200}
        captured = {}
        with patch.object(cm, "apply_camera", lambda **kw: captured.update(kw) or {}):
            cm.import_camera(data=cam, name="x")
        self.assertAlmostEqual(captured["fov_deg"], cm.fov_from_focal_mm(36.0, 36.0))
        with self.assertRaisesRegex(ValueError, "missing"):
            cm.import_camera(data={"position": [0, 0, 0]})
        with self.assertRaisesRegex(ValueError, "not supported"):
            cm.import_camera(data=dict(cam, **{"class": "VRayPhysicalCamera"}))


class CaptureTests(unittest.TestCase):
    def test_capture_rejects_bad_arguments_before_touching_max(self):
        fake = QueueClient([])
        with patch.object(cm, "client", fake):
            with self.assertRaisesRegex(ValueError, "mode"):
                cm.capture_camera("c", mode="clay")
            with self.assertRaisesRegex(ValueError, "opacity"):
                cm.capture_camera("c", opacity=1.5)
        self.assertEqual(fake.sent, [])

    def test_capture_output_path_outside_allowed_dirs_is_refused(self):
        fake = QueueClient([state_string(w=640, h=360), ""])
        with patch.object(cm, "client", fake), patch.object(path_policy, "configured_dirs", return_value=[]):
            with self.assertRaises(path_policy.PathNotAllowedError):
                cm.capture_camera("c", output_path=str(Path(tempfile.gettempdir()).parent / "nope" / "x.png"))
        self.assertEqual(len(fake.sent), 2)  # camera read + maxFilePath only

    def test_compositor_source_is_safe_mode_clean(self):
        lowered = cm._COMPOSITOR_CS.lower()
        for token in ("doscommand", "shelllaunch", "deletefile", "python.execute", "createfile"):
            self.assertNotIn(token, lowered)
        self.assertNotIn("\\", cm._COMPOSITOR_CS)


if __name__ == "__main__":
    unittest.main()
