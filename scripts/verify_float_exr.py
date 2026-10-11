"""Live acceptance: render_float_exr writes an UNCLAMPED, full-frame float EXR.

Kaschmir (2026-10): render() outputFile .exr with V-Ray GPU came out clamped at
1.0 and region renders left dataWindow != displayWindow. This renders a
self-illuminated plane (VRayLightMtl multiplier 5) through render_float_exr
with V-Ray GPU and V-Ray CPU and checks the PIXELS, not just the file:
  * a pixel value > 1.0 (~5, scene-linear),
  * dataWindow == displayWindow == the full 160x90 frame,
  * 32-bit float channels (half=False) and 16-bit half channels (half=True),
  * the file lands at exactly the requested path,
  * the renderer's raw-output properties are restored afterwards,
  * a path outside the allowed folders is refused before rendering.
It also renders the old way (render() outputFile:.exr) to show the clamp, and
checks the non-V-Ray fallback (Scanline into an HDR bitmap) for a full-frame
float file.

Run against a SCRATCH Max with an Untitled scene, never a production instance:
    set MCP_UI_DENY_PIDS=<every protected Max PID>
    uv run python scripts/verify_float_exr.py <scratch PID>
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from maxmcp.server import client
from maxmcp.helpers.exr import read_pixels
from maxmcp.path_policy import temp_root
from maxmcp.tools.routing import select_max_instance, release_max_instance
from maxmcp.tools.render_exr import render_float_exr

pid = int(sys.argv[1])
select_max_instance(pid)
ms = lambda e: client.send_command(e, timeout=600).get("result")  # noqa: E731
assert ms("maxFileName") == "", "scratch Max must be Untitled"
assert int(ms('((dotNetClass "System.Diagnostics.Process").GetCurrentProcess()).Id as string')) == pid
ms("resetMaxFile #noPrompt")

fails = []
W, H = 160, 90
out_dir = temp_root() / "exr_verify"


def check(label, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + label + (f": {detail}" if detail else ""))
    if not ok:
        fails.append(label)


def centre(rows):
    red = rows.get("R") or []
    return red[H // 2][W // 2] if red else None


def vray_case(tag, renderer):
    ms(f"renderers.current = {renderer}()")
    print(f"\n== {tag}: {ms('(classOf renderers.current) as string')}")
    for half in (False, True):
        target = out_dir / f"{tag}_{'half' if half else 'full'}.exr"
        r = json.loads(render_float_exr(output_path=str(target), width=W, height=H,
                                        camera="mcpExrCam", half=half, timeout=600))
        label = f"{tag} half={half}"
        if "output" not in r:
            check(f"{label}: render_float_exr succeeded", False, json.dumps(r)[:400])
            continue
        print("   properties:", r.get("propertiesSet"))
        header, rows = read_pixels(r["output"])
        types = {c.name: c.pixel_type for c in header.channels}
        want_type = "half" if half else "float"
        value = centre(rows)
        check(f"{label}: file at the requested path", Path(r["output"]) == target, r["output"])
        check(f"{label}: dataWindow == displayWindow == full frame",
              header.data_window == header.display_window == (0, 0, W - 1, H - 1),
              f"{header.data_window} / {header.display_window}")
        check(f"{label}: RGB are {want_type}", all(types.get(c) == want_type for c in "RGB"), str(types))
        check(f"{label}: centre pixel > 1.0 (unclamped)", value is not None and value > 1.0, f"R={value}")
        check(f"{label}: centre pixel ~ 5 (scene-linear)", value is not None and abs(value - 5.0) < 0.25, f"R={value}")
        check(f"{label}: tool reports fullFrame", (r.get("exr") or {}).get("fullFrame") is True)
    host = "renderers.current.V_Ray_settings" if ms("(isProperty renderers.current #V_Ray_settings) as string") == "true" \
        else "renderers.current"
    restored = ms(f'({host}.output_saveRawFile as string) + "|" + {host}.output_rawFileName + "|" + '
                  f'({host}.colorMapping_adaptationOnly as string)')
    check(f"{tag}: raw-output properties restored", restored == "false||2", repr(restored))


try:
    names = ms("(for c in RendererClass.classes collect (c as string)) as string").strip("#()").replace('"', "").split(", ")
    gpu = next((c for c in names if c.startswith("V_Ray_GPU")), "")
    cpu = next((c for c in names if c.startswith("V_Ray_") and not c.startswith("V_Ray_GPU")), "")
    assert gpu or cpu, f"no V-Ray renderer installed: {names}"

    # A plane filling the view, self-illuminated at 5x white, seen by a camera.
    ms('(local p = Plane name:"mcpExrPlane" length:4000 width:4000 lengthsegs:1 widthsegs:1; '
       'p.material = VRayLightMtl color:white multiplier:5.0; '
       'Freecamera name:"mcpExrCam" pos:[0,0,200])')

    # Baseline (informational): the old render() outputFile path.
    if gpu:
        ms(f"renderers.current = {gpu}()")
        old = out_dir / "baseline_render_outputfile.exr"
        out_dir.mkdir(parents=True, exist_ok=True)
        old.unlink(missing_ok=True)
        ms(f'(render camera:$mcpExrCam outputwidth:{W} outputheight:{H} vfb:false '
           f'outputFile:"{old.as_posix()}"; "ok")')
        try:
            _, rows = read_pixels(old)
            print(f"INFO baseline render() outputFile:.exr centre R = {centre(rows)} (clamped if 1.0)")
        except Exception as exc:  # noqa: BLE001 - informational only
            print(f"INFO baseline render() outputFile not readable: {exc}")

    if gpu:
        vray_case("vray_gpu", gpu)
    if cpu:
        vray_case("vray_cpu", cpu)

    # Non-V-Ray fallback: Scanline into an HDR bitmap, saved by Max's EXR writer.
    ms("renderers.current = Default_Scanline_Renderer()")
    ms('(local p = $mcpExrPlane; p.material = Standardmaterial diffuse:white selfIllumAmount:100)')
    target = out_dir / "scanline_fallback.exr"
    r = json.loads(render_float_exr(output_path=str(target), width=W, height=H, camera="mcpExrCam"))
    print("\n== scanline fallback:", json.dumps(r)[:400])
    if "output" in r:
        header, rows = read_pixels(r["output"])
        types = {c.name: c.pixel_type for c in header.channels}
        check("fallback: method is max_hdr_bitmap", r.get("method") == "max_hdr_bitmap", r.get("method"))
        check("fallback: dataWindow == displayWindow == full frame",
              header.data_window == header.display_window == (0, 0, W - 1, H - 1),
              f"{header.data_window} / {header.display_window}")
        check("fallback: float or half channels", all(types.get(c) in ("float", "half") for c in "RGB"), str(types))
        value = centre(rows)
        check("fallback: self-illuminated white reads ~1.0", value is not None and abs(value - 1.0) < 0.05, f"R={value}")
    else:
        check("fallback render succeeded", False, json.dumps(r)[:400])

    # Path policy: refused before anything renders.
    r = json.loads(render_float_exr(output_path="C:/Windows/mcp_not_allowed.exr", width=W, height=H))
    check("path outside allowed folders refused (SAFE_MODE)", r.get("code") == "SAFE_MODE", json.dumps(r)[:200])
    check("refused path not written", not Path("C:/Windows/mcp_not_allowed.exr").exists())
finally:
    ms("delete objects")
    ms("renderers.current = Default_Scanline_Renderer()")
    release_max_instance()

print("\nRESULT:", "ALL PASS" if not fails else f"{len(fails)} FAIL: {fails}")
sys.exit(1 if fails else 0)
