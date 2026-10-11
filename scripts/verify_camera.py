"""Live acceptance for maxmcp/tools/camera.py: set/export/import camera,
project_points accuracy against Max's own renders, and capture_camera framing.

Run against a SCRATCH Max with an Untitled scene, never a production instance:
    set MCP_UI_DENY_PIDS=<every protected Max PID>
    uv run python scripts/verify_camera.py <scratch PID>

Ground truth for project_points is a Scanline render of small self-illuminated
marker spheres (Scanline only; no V-Ray). Each marker is located by its
intensity-weighted centroid and compared with project_points. A MAXScript
projection through the inverse camera matrix and Max's integer viewport
projection (gw.wTransPoint) are reported as secondary cross-checks.
"""
from __future__ import annotations

import json
import math
import os
import struct
import sys
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from maxmcp import path_policy  # noqa: E402
from maxmcp.server import client  # noqa: E402
from maxmcp.tools import camera as cm  # noqa: E402
from maxmcp.tools.routing import release_max_instance, select_max_instance  # noqa: E402

PROJECTION_TARGET_PX = 0.5
COLORS = ("R", "G", "B", "RG", "GB", "RB")
COLOR_VALUES = {"R": (255, 0, 0), "G": (0, 255, 0), "B": (0, 0, 255),
                "RG": (255, 255, 0), "GB": (0, 255, 255), "RB": (255, 0, 255)}

pid = int(sys.argv[1])
select_max_instance(pid)


def ms(expr: str, timeout: float = 300.0) -> str:
    return client.send_command(expr, timeout=timeout).get("result")


assert ms("maxFileName") == "", "scratch Max must be Untitled"
assert int(ms('((dotNetClass "System.Diagnostics.Process").GetCurrentProcess()).Id as string')) == pid
ms("resetMaxFile #noPrompt")

fails: list[str] = []
report: dict[str, object] = {}


def check(label: str, ok: bool, detail: str = "") -> None:
    print(("PASS " if ok else "FAIL ") + label + (f": {detail}" if detail else ""))
    if not ok:
        fails.append(label)


# MAXScript measuring helper: hue-class centroids and alpha bbox of an image file.
MEASURE_FN = r"""
fn mcpVerifyMeasure bmp binary = (
  local names = #("R","G","B","RG","GB","RB")
  local sx = #(0.0,0.0,0.0,0.0,0.0,0.0)
  local sy = #(0.0,0.0,0.0,0.0,0.0,0.0)
  local sw = #(0.0,0.0,0.0,0.0,0.0,0.0)
  local ax0 = 100000; local ay0 = 100000; local ax1 = -1; local ay1 = -1
  local asx = 0.0; local asy = 0.0; local asw = 0.0
  for y = 0 to bmp.height - 1 do (
    local row = getPixels bmp [0, y] bmp.width
    for i = 1 to row.count do (
      local p = row[i]
      local x = i - 1
      if p.alpha >= 128 do (
        if x < ax0 do ax0 = x; if x > ax1 do ax1 = x
        if y < ay0 do ay0 = y; if y > ay1 do ay1 = y
      )
      if p.alpha > 0 do (asx += p.alpha * (x + 0.5); asy += p.alpha * (y + 0.5); asw += p.alpha)
      local mx = amax #(p.r, p.g, p.b)
      local mn = amin #(p.r, p.g, p.b)
      local w = mx - mn
      if mx > 20 and w > 20 do (
        local h = mx * 0.5
        local r = p.r > h; local g = p.g > h; local b = p.b > h
        local k = 0
        if r and not g and not b then k = 1
        else if g and not r and not b then k = 2
        else if b and not r and not g then k = 3
        else if r and g and not b then k = 4
        else if g and b and not r then k = 5
        else if r and b and not g then k = 6
        if binary do w = 1.0
        if k > 0 do (sx[k] += w * (x + 0.5); sy[k] += w * (y + 0.5); sw[k] += w)
      )
    )
  )
  local s = "W=" + (bmp.width as string) + ";H=" + (bmp.height as string)
  for k = 1 to 6 where sw[k] > 0 do s += ";" + names[k] + "=" + ((bit.floatAsInt (sx[k]/sw[k])) as string) + "," + ((bit.floatAsInt (sy[k]/sw[k])) as string) + "," + ((sw[k] as integer) as string)
  if ax1 >= 0 do s += ";abox=" + (ax0 as string) + "," + (ay0 as string) + "," + ((ax1 + 1) as string) + "," + ((ay1 + 1) as string)
  if asw > 0 do s += ";acen=" + ((bit.floatAsInt (asx/asw)) as string) + "," + ((bit.floatAsInt (asy/asw)) as string)
  s
)
"""


def parse_measure(raw: str) -> dict[str, object]:
    out: dict[str, object] = {}
    for part in raw.strip('"').split(";"):
        key, _, value = part.partition("=")
        vals = value.split(",")
        if key in ("W", "H"):
            out[key] = int(value)
        elif key in COLORS:
            out[key] = (cm._from_bits(vals[0]), cm._from_bits(vals[1]), int(vals[2]))
        elif key == "abox":
            out[key] = tuple(int(v) for v in vals)
        elif key == "acen":
            out[key] = (cm._from_bits(vals[0]), cm._from_bits(vals[1]))
    return out


def measure_file(path: str) -> dict[str, object]:
    p = str(path).replace("\\", "/")
    return parse_measure(ms(f'({MEASURE_FN}\nlocal b = openBitmap "{p}"\nlocal s = mcpVerifyMeasure b true\nclose b\ns\n)'))


def unproject(cam: dict, px: float, py: float, depth: float) -> list[float]:
    w = float(cam["render_width"])
    pa = float(cam.get("pixel_aspect", 1.0))
    fpx = cm.f_px_from_fov(float(cam["fov_deg"]), w)
    cx, cy = cm.principal_point(cam)
    xc = (px - cx) / fpx * depth
    yc = -(py - cy) / (fpx * pa) * depth
    return [cam["position"][i] - cam["back"][i] * depth + cam["right"][i] * xc + cam["up"][i] * yc for i in range(3)]


def marker_case(label: str, cam_name: str, targets: list[tuple[float, float, float]], gate: bool = True) -> float:
    """Render self-illuminated spheres at world points chosen to land on `targets`
    (px, py, depth) and compare their rendered centroids with project_points."""
    cam = cm.export_camera(cam_name)["camera"]
    world = [unproject(cam, px, py, d) for px, py, d in targets]
    fpx = cm.f_px_from_fov(cam["fov_deg"], cam["render_width"])
    lines = ["(", "local mk = #()"]
    for (px, py, d), p, col in zip(targets, world, COLORS):
        radius = 2.5 * d / fpx
        r, g, b = COLOR_VALUES[col]
        lines.append(
            f"(local s = Sphere radius:{cm._msf(radius)} segs:24 pos:{cm._msp3(p)}; "
            f"s.material = Standardmaterial diffuse:(color {r} {g} {b}) selfIllumAmount:100; append mk s)")
    lines += [
        f'local c = getNodeByName "{cam_name}" exact:true',
        "local bmp = render camera:c outputwidth:renderWidth outputheight:renderHeight vfb:false",
        MEASURE_FN,
        "local s = mcpVerifyMeasure bmp false",
        "close bmp",
        "delete mk",
        "s",
        ")",
    ]
    meas = parse_measure(ms("\n".join(lines), timeout=600.0))
    proj = cm.project_points(cam_name, world)["points"]
    worst = 0.0
    for col, pt in zip(COLORS, proj):
        if col not in meas:
            check(f"{label} marker {col} rendered", False, "not found in render")
            worst = float("inf")
            continue
        mx, my, _ = meas[col]  # type: ignore[misc]
        err = math.hypot(mx - pt["x"], my - pt["y"])
        worst = max(worst, err)
    if gate:
        check(f"{label}: project_points vs Scanline render (max error {worst:.3f} px)", worst < PROJECTION_TARGET_PX)
    else:
        print(f"INFO {label}: project_points vs Scanline render (max error {worst:.3f} px)")
    report[f"projection_max_px_{label}"] = round(worst, 4)
    return worst


try:
    ms("renderers.current = Default_Scanline_Renderer()")
    ms("renderWidth = 640; renderHeight = 360; renderPixelAspect = 1.0")

    # 1. Basis validation (pure Python, but exercised through the tool too).
    yaw, pitch, roll = math.radians(30), math.radians(-12), math.radians(7)

    def rot(yaw: float, pitch: float, roll: float):
        # camera looking along +Y rotated by yaw about Z then pitch about X, then roll about view axis
        back0 = (0.0, -1.0, 0.0)  # looks along +Y
        right0 = (1.0, 0.0, 0.0)
        up0 = (0.0, 0.0, 1.0)

        def rz(v, a):
            return (v[0] * math.cos(a) - v[1] * math.sin(a), v[0] * math.sin(a) + v[1] * math.cos(a), v[2])

        def raxis(v, k, a):
            c, s = math.cos(a), math.sin(a)
            d = sum(v[i] * k[i] for i in range(3))
            cr = (k[1] * v[2] - k[2] * v[1], k[2] * v[0] - k[0] * v[2], k[0] * v[1] - k[1] * v[0])
            return tuple(v[i] * c + cr[i] * s + k[i] * d * (1 - c) for i in range(3))

        r, u, b = (rz(v, yaw) for v in (right0, up0, back0))
        r, u, b = (raxis(v, r, pitch) for v in (r, u, b))
        r, u = (raxis(v, b, roll) for v in (r, u))
        return r, u, b

    r, u, b = rot(yaw, pitch, roll)
    res = cm.set_camera(name="vcA", position=[120.0, -450.0, 160.0], right=list(r), up=list(u), back=list(b),
                        fov_deg=52.5, shift_x=0.07, shift_y=-0.04, near=1.0, far=100000.0)
    check("set_camera Physical basis+fov+shift+clip read back", res["camera"]["class"] == "Physical",
          json.dumps({k: res["camera"][k] for k in ("fov_deg", "shift_x", "shift_y", "near", "far")}))
    noisy = [c + 0.003 for c in r]
    res2 = cm.set_camera(name="vcA", position=[120.0, -450.0, 160.0], right=noisy, up=list(u), back=list(b))
    check("near-orthonormal basis re-orthonormalised with a warning",
          any("re-orthonormalised" in w for w in res2["warnings"]), str(res2["warnings"]))
    for label, kwargs in (
        ("degenerate basis rejected", dict(right=[1, 0, 0], up=[1, 0, 0], back=[0, 0, 1])),
        ("left-handed basis rejected", dict(right=[-1, 0, 0], up=[0, 1, 0], back=[0, 0, 1])),
        ("non-orthonormal basis rejected", dict(right=[1, 0.3, 0], up=[0, 1, 0], back=[0, 0, 1])),
    ):
        try:
            cm.set_camera(name="vcA", position=[0, 0, 0], **kwargs)
            check(label, False, "accepted")
        except ValueError as exc:
            check(label, True, str(exc)[:80])
    cm.set_camera(name="vcA", position=[120.0, -450.0, 160.0], right=list(r), up=list(u), back=list(b))

    # 2. Projection accuracy against Scanline renders.
    targets = [(320.0, 180.0, 400.0), (40.5, 30.25, 250.0), (600.0, 330.0, 900.0),
               (500.3, 60.7, 150.0), (90.0, 300.0, 600.0), (333.3, 111.1, 2500.0)]
    marker_case("A_physical_shift_640x360", "vcA", targets)

    ms("renderWidth = 300; renderHeight = 500")
    cm.set_camera(name="vcB", position=[-300.0, -200.0, 80.0], target=[0.0, 0.0, 40.0], fov_deg=35.0,
                  shift_x=-0.05, shift_y=0.1)
    marker_case("B_physical_portrait_300x500",
                "vcB", [(150.0, 250.0, 300.0), (20.0, 30.0, 400.0), (280.0, 470.0, 350.0),
                        (100.0, 400.0, 200.0), (250.0, 80.0, 800.0), (60.0, 220.0, 500.0)])

    ms("renderWidth = 640; renderHeight = 360")
    cm.set_camera(name="vcC", position=[250.0, 300.0, 120.0], target=[0.0, 0.0, 0.0], fov_deg=63.0,
                  camera_class="Freecamera")
    marker_case("C_freecamera", "vcC", targets)

    # A Physical camera built outside the tool: lens breathing + finite focus changes the effective FOV.
    ms('(local c = Physical name:"vcD" targeted:false; c.focal_length_mm = 50.0; c.film_width_mm = 36.0; '
       'c.lens_breathing_amount = 1.0; c.specify_focus = 1; c.focus_distance = 300.0; '
       'c.transform = matrix3 [1,0,0] [0,0,1] [0,-1,0] [0,-500,50]; c.fov)')
    marker_case("D_physical_lens_breathing", "vcD", targets)

    # 3. Secondary cross-checks for camera A: MAXScript matrix projection and integer viewport projection.
    camA = cm.export_camera("vcA")["camera"]
    ms("renderWidth = 640; renderHeight = 360")
    world = [unproject(camA, px, py, d) for px, py, d in targets]
    py_proj = cm.project_points("vcA", world)["points"]
    pts_ms = "#(" + ", ".join(cm._msp3(p) for p in world) + ")"
    raw = ms(f"""(
local c = getNodeByName "vcA" exact:true
local m = inverse c.transform
local W = renderWidth as float
local H = renderHeight as float
local f = (W / 2.0) / tan (c.fov / 2.0)
local s = ""
for p in {pts_ms} do (
  local q = p * m
  local x = W / 2.0 + c.horizontal_shift / 100.0 * W + f * q.x / (-q.z)
  local y = H / 2.0 - c.vertical_shift / 100.0 * W - f * q.y / (-q.z)
  s += ((bit.floatAsInt x) as string) + "," + ((bit.floatAsInt y) as string) + ";"
)
s
)""")
    ms_pts = [tuple(cm._from_bits(v) for v in item.split(",")) for item in raw.strip('";').split(";") if item]
    d_ms = max(math.hypot(a[0] - b["x"], a[1] - b["y"]) for a, b in zip(ms_pts, py_proj))
    check(f"MAXScript inverse-matrix projection agrees (max {d_ms:.5f} px)", d_ms < 0.01)
    report["maxscript_matrix_max_px"] = round(d_ms, 6)
    raw = ms(f"""(
local c = getNodeByName "vcA" exact:true
local vt = viewport.getType()
local vtm = viewport.getTM()
local vsafe = displaySafeFrames
viewport.setCamera c
displaySafeFrames = true
completeRedraw()
gw.setTransform (matrix3 1)
local s = (gw.getWinSizeX() as string) + "," + (gw.getWinSizeY() as string) + ";"
for p in {pts_ms} do (local q = gw.wTransPoint p; s += (q.x as string) + "," + (q.y as string) + ";")
displaySafeFrames = vsafe
viewport.setType vt
viewport.setTM vtm
completeRedraw()
s
)""")
    parts = [p for p in raw.strip('";').split(";") if p]
    vw, vh = (int(float(v)) for v in parts[0].split(","))
    fx, fy, fw, fh = cm.frame_rect_in_viewport(vw, vh, 640, 360)
    scale = fw / 640.0
    d_vp = 0.0
    for item, pt in zip(parts[1:], py_proj):
        wx, wy = (float(v) for v in item.split(","))
        d_vp = max(d_vp, math.hypot((wx + 0.5 - fx) / scale - pt["x"], (wy + 0.5 - fy) / scale - pt["y"]))
    tol = 1.0 / scale + 0.25
    check(f"viewport gw.wTransPoint agrees within integer quantisation (max {d_vp:.3f} px, tol {tol:.2f})", d_vp < tol)
    report["viewport_wtrans_max_px"] = round(d_vp, 4)

    # Behind / outside flags.
    flags = cm.project_points("vcA", [unproject(camA, 320, 180, -100.0), unproject(camA, -50, 180, 300.0),
                                      unproject(camA, 320, 180, 300.0)])["points"]
    check("behind / outside-frame flags",
          flags[0]["behind"] and not flags[0]["in_frame"] and not flags[1]["behind"] and not flags[1]["in_frame"]
          and flags[2]["in_frame"], json.dumps(flags))

    # 4. Export -> import -> export round trip, JSON file through path_policy.
    out_json = path_policy.temp_root() / "verify_camera_vcA.json"
    exp1 = cm.export_camera("vcA", path=str(out_json))
    check("export_camera wrote JSON under %TEMP%/3dsmax-mcp", Path(exp1["file"]).is_file(), exp1["file"])
    cm.import_camera(path=str(out_json), name="vcA_rt")
    exp2 = cm.export_camera("vcA_rt")["camera"]
    cm.import_camera(data=exp2, name="vcA_rt2")
    exp3 = cm.export_camera("vcA_rt2")["camera"]
    worst_rt = 0.0
    for key, value in exp1["camera"].items():
        if key == "name":
            continue
        for other in (exp2, exp3):
            ov = other[key]
            if isinstance(value, list):
                worst_rt = max(worst_rt, max(abs(a - b) for a, b in zip(value, ov)))
            elif isinstance(value, float):
                worst_rt = max(worst_rt, abs(value - ov) / max(1.0, abs(value)))
            elif value != ov:
                worst_rt = float("inf")
                print("  round-trip mismatch", key, value, ov)
    check(f"export->import->export round trip identical within 1e-5 (max {worst_rt:.2e})", worst_rt < 1e-5)
    report["round_trip_max_diff"] = worst_rt
    try:
        cm.export_camera("vcA", path="C:/Windows/verify_camera_forbidden.json")
        check("export to a non-allowed folder is refused", False)
    except path_policy.PathNotAllowedError:
        check("export to a non-allowed folder is refused", True)

    # 5. capture_camera framing: plate marker vs projected scene object.
    ms("renderWidth = 640; renderHeight = 360")
    sphere_px = (400.0, 150.0, 300.0)
    sphere_world = unproject(camA, *sphere_px)
    fpxA = cm.f_px_from_fov(camA["fov_deg"], 640)
    ms(f'(local s = Sphere name:"vsRed" radius:{cm._msf(14.0 * 300.0 / fpxA)} segs:48 pos:{cm._msp3(sphere_world)}; '
       's.wirecolor = (color 255 0 0); s.material = Standardmaterial diffuse:(color 255 0 0) selfIllumAmount:100; "OK")')
    expected = cm.project_points("vcA", [sphere_world])["points"][0]
    marker_dx = 60
    plate = path_policy.temp_root() / "verify_camera_plate.png"
    mx0 = int(round(expected["x"] + marker_dx - 0.5))
    my0 = int(round(expected["y"] - 0.5))

    def write_png(path: Path, w: int, h: int) -> None:
        rows = []
        for y in range(h):
            row = bytearray([0])
            for x in range(w):
                if abs(x - mx0) <= 3 and abs(y - my0) <= 3:
                    row += bytes((0, 255, 0))
                else:
                    row += bytes((40, 40, 40))
            rows.append(bytes(row))

        def chunk(tag: bytes, data: bytes) -> bytes:
            return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

        ihdr = struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)
        path.write_bytes(b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(b"".join(rows)))
                         + chunk(b"IEND", b""))

    os.makedirs(plate.parent, exist_ok=True)
    write_png(plate, 640, 360)
    plate_center = (mx0 + 0.5, my0 + 0.5)
    state_q = ('(viewport.getType() as string) + "|" + (viewport.GetRenderLevel() as string) + "|" + '
               '(displaySafeFrames as string) + "|" + (viewport.IsSolidBackgroundColorMode() as string) + "|" + '
               '(hideByCategory.geometry as string) + "|" + (ViewportButtonMgr.EnableButtons as string)')
    before = ms(state_q)
    for label, size, scale_f in (("shaded_full", None, 1.0), ("shaded_half", [320, 180], 0.5)):
        cap = cm.capture_camera("vcA", plate_path=str(plate), size=size, mode="shaded", opacity=0.5)
        meas = measure_file(cap["file"])
        ok_size = meas["W"] == int(640 * scale_f) and meas["H"] == int(360 * scale_f)
        check(f"capture {label} size {meas['W']}x{meas['H']}", ok_size)
        if "R" in meas and "G" in meas:
            rx, ry, _ = meas["R"]  # type: ignore[misc]
            gx, gy, _ = meas["G"]  # type: ignore[misc]
            # Offsets in OUTPUT pixels; the plate marker shrinks to 3.5 px at half size.
            obj_err = math.hypot(rx - expected["x"] * scale_f, ry - expected["y"] * scale_f)
            plate_err = math.hypot(gx - plate_center[0] * scale_f, gy - plate_center[1] * scale_f)
            rel = math.hypot((rx - gx) - (expected["x"] - plate_center[0]) * scale_f,
                             (ry - gy) - (expected["y"] - plate_center[1]) * scale_f)
            check(f"capture {label}: object lands on its projected pixel (offset {obj_err:.3f} output px)", obj_err < 0.5)
            check(f"capture {label}: plate marker unshifted (offset {plate_err:.3f} output px)", plate_err < 0.5)
            check(f"capture {label}: object vs plate marker registration (offset {rel:.3f} output px)", rel < 0.75)
            report[f"capture_{label}_object_offset_px"] = round(obj_err, 4)
            report[f"capture_{label}_plate_offset_px"] = round(plate_err, 4)
            report[f"capture_{label}_object_vs_plate_px"] = round(rel, 4)
        else:
            check(f"capture {label}: object and plate marker found", False, json.dumps(meas))
    # Same check through a non-native plate format (TGA is converted through Max first).
    tga = path_policy.temp_root() / "verify_camera_plate.tga"
    header = struct.pack("<BBBHHBHHHHBB", 0, 0, 2, 0, 0, 0, 0, 0, 640, 360, 24, 0)
    body = bytearray()
    for y in range(359, -1, -1):  # bottom-up rows, BGR
        for x in range(640):
            body += bytes((0, 255, 0)) if abs(x - mx0) <= 3 and abs(y - my0) <= 3 else bytes((40, 40, 40))
    tga.write_bytes(header + bytes(body))
    cap = cm.capture_camera("vcA", plate_path=str(tga), mode="shaded", opacity=0.5)
    meas = measure_file(cap["file"])
    if "G" in meas:
        gx, gy, _ = meas["G"]  # type: ignore[misc]
        err = math.hypot(gx - plate_center[0], gy - plate_center[1])
        check(f"capture with TGA plate: marker unshifted (offset {err:.3f} px)", err < 0.5, str(cap["warnings"]))
    else:
        check("capture with TGA plate: marker found", False, json.dumps(meas))

    # Plane facing the camera: matte bbox vs projected corners (shaded and wire), for a
    # height-fit (640x360) and a width-fit (1000x400, wider than the viewport) frame.
    ms('delete $vsRed')

    def plane_case(label: str, rw: int, rh: int, box_px: tuple[float, float, float, float]) -> None:
        ms(f"renderWidth = {rw}; renderHeight = {rh}")
        cam = cm.export_camera("vcA")["camera"]
        x0, y0, x1, y1 = box_px
        depth = 350.0
        corners = [unproject(cam, x, y, depth) for x, y in ((x0, y0), (x1, y0), (x1, y1), (x0, y1))]
        cx_w = [sum(c[i] for c in corners) / 4.0 for i in range(3)]
        tm = f"matrix3 {cm._msp3(cam['right'])} {cm._msp3(cam['up'])} {cm._msp3(cam['back'])} {cm._msp3(cx_w)}"
        ms(f'(local p = Plane name:"vsPlane" length:{cm._msf(math.dist(corners[1], corners[2]))} '
           f'width:{cm._msf(math.dist(corners[0], corners[1]))} lengthsegs:1 widthsegs:1; '
           f'p.transform = {tm}; p.wirecolor = (color 255 255 255); "OK")')
        try:
            for mode in ("shaded", "wire"):
                cap = cm.capture_camera("vcA", mode=mode, opacity=1.0)
                box = measure_file(cap["matte_file"]).get("abox")
                if not box:
                    check(f"capture {label} {mode}: plane found in matte", False)
                    continue
                err = max(abs(a - b) for a, b in zip(box, box_px))  # type: ignore[arg-type]
                centre = math.hypot((box[0] + box[2]) / 2 - (x0 + x1) / 2, (box[1] + box[3]) / 2 - (y0 + y1) / 2)  # type: ignore[index]
                limit = 1.0 if mode == "shaded" else 2.0
                check(f"capture {label} {mode}: plane matte bbox {box} vs projected {box_px} "
                      f"(max edge error {err:.2f} px, centre offset {centre:.2f} px)", err <= limit and centre <= 0.75)
                report[f"capture_{label}_{mode}_plane_bbox_err_px"] = err
                report[f"capture_{label}_{mode}_plane_centre_err_px"] = round(centre, 3)
                report[f"capture_{label}_{mode}_source"] = cap["source"] + " " + str(cap["source_frame_px"])
        finally:
            ms("delete $vsPlane")

    plane_case("640x360", 640, 360, (150.0, 90.0, 490.0, 270.0))
    plane_case("1000x400", 1000, 400, (200.0, 60.0, 800.0, 340.0))
    ms("renderWidth = 640; renderHeight = 360")
    after = ms(state_q)
    check("viewport state restored after captures", before == after, f"{before} -> {after}")
    try:
        cm.capture_camera("vcA", output_path="C:/Windows/forbidden_capture.png")
        check("capture to a non-allowed folder is refused", False)
    except path_policy.PathNotAllowedError:
        check("capture to a non-allowed folder is refused", True)

    # 6. Non-square pixels (shifted camera A, pixel aspect 1.5).
    ms("renderWidth = 640; renderHeight = 360; renderPixelAspect = 1.5")
    try:
        worst_pa = marker_case("E_pixel_aspect_1.5", "vcA", targets)
        report["pixel_aspect_1.5_max_px"] = round(worst_pa, 4)
    finally:
        ms("renderPixelAspect = 1.0")
finally:
    try:
        if ms("maxFileName") == "":
            ms("resetMaxFile #noPrompt")
    finally:
        release_max_instance()

print("\nREPORT:", json.dumps(report, indent=1))
print("\nRESULT:", "ALL PASS" if not fails else f"{len(fails)} FAIL: {fails}")
sys.exit(1 if fails else 0)
