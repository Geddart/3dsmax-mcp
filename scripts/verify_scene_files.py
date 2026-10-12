"""Live acceptance for maxmcp/tools/scene_files.py against a SCRATCH 3ds Max.

Usage (from the repo root, with the production Max fenced):

    set MCP_UI_DENY_PIDS=<production pid>
    uv run --frozen --no-sync python scripts/verify_scene_files.py --pid <scratch pid> [--quit]

The scratch Max must have an untitled, disposable scene: the script asserts
maxFileName == "" before it resets the scene. It exports two boxes to OBJ and
JSON under %TEMP%\\3dsmax-mcp, checks a refused path, saves
%TEMP%\\3dsmax-mcp\\vtest\\test_V001.max then two versioned saves (V002, V003)
with render outputs following, round-trips scene_setup, and removes every file
it created. It ends by resetting the scratch scene (guarded) and, with --quit,
quitting that Max.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from maxmcp.path_policy import PathNotAllowedError, temp_root  # noqa: E402
from maxmcp.server import client  # noqa: E402
from maxmcp.tools import scene_files  # noqa: E402
from maxmcp.tools.routing import select_max_instance  # noqa: E402

FAILURES: list[str] = []


def check(cond: bool, label: str, detail: object = "") -> None:
    print(("PASS " if cond else "FAIL ") + label + (f" -- {detail}" if detail != "" else ""))
    if not cond:
        FAILURES.append(label)


def ms(code: str, timeout: float = 120.0) -> str:
    return str(client.send_command(code, timeout=timeout).get("result", ""))


def ms_json(code: str) -> dict:
    return json.loads(ms(code))


def denied_pids() -> set[int]:
    out: set[int] = set()
    for part in os.environ.get("MCP_UI_DENY_PIDS", "").replace(";", ",").split(","):
        if part.strip().isdigit():
            out.add(int(part.strip()))
    return out


def read_obj(path: Path) -> dict:
    verts: list[list[float]] = []
    faces = 0
    vt = vn = 0
    objects = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.startswith("v "):
            verts.append([float(x) for x in line.split()[1:4]])
        elif line.startswith("vt "):
            vt += 1
        elif line.startswith("vn "):
            vn += 1
        elif line.startswith("f "):
            faces += 1
        elif line.startswith("o "):
            objects += 1
    return {"verts": verts, "faces": faces, "vt": vt, "vn": vn, "objects": objects}


def close(a: list[float], b: list[float], tol: float = 1e-3) -> bool:
    return all(math.isclose(x, y, abs_tol=tol) for x, y in zip(a, b))


REF_VERTS = r'''(
    local o = getNodeByName "@NAME@" exact:true
    local m = snapshotAsMesh o
    local itm = inverse o.objectTransform
    local s = stringStream ""
    format "{\"world\":[" to:s
    for i in #(1, 4, m.numVerts) do (
        local p = getVert m i
        if i != 1 do format "," to:s
        format "[%,%,%]" (formattedPrint p.x format:".9g") (formattedPrint p.y format:".9g") (formattedPrint p.z format:".9g") to:s
    )
    format "],\"local\":[" to:s
    for i in #(1, 4, m.numVerts) do (
        local p = (getVert m i) * itm
        if i != 1 do format "," to:s
        format "[%,%,%]" (formattedPrint p.x format:".9g") (formattedPrint p.y format:".9g") (formattedPrint p.z format:".9g") to:s
    )
    format "],\"nv\":%,\"nf\":%}" m.numVerts m.numFaces to:s
    delete m
    s as string
)'''


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pid", type=int, required=True)
    parser.add_argument("--quit", action="store_true", help="quit the scratch Max at the end")
    args = parser.parse_args()
    if args.pid in denied_pids():
        print(f"Refusing: PID {args.pid} is fenced by MCP_UI_DENY_PIDS")
        return 2

    select_max_instance(args.pid)
    pid_seen = ms('((dotNetClass "System.Diagnostics.Process").GetCurrentProcess()).Id as string')
    if pid_seen != str(args.pid):
        print(f"Refusing: routed to PID {pid_seen}, expected {args.pid}")
        return 2
    name = ms("maxFileName")
    if name != "":
        print(f"Refusing: scratch Max has a named scene open ({name!r})")
        return 2
    ms("resetMaxFile #noPrompt; true")

    tmp = temp_root()
    exp_dir = tmp / "verify_scene_files"
    vtest = tmp / "vtest"
    for folder in (exp_dir, vtest):
        if folder.exists():
            leftovers = [p for p in folder.rglob("*") if p.is_file()]
            if any(p.suffix.lower() not in (".obj", ".json", ".max", ".exr") for p in leftovers):
                print(f"Refusing: {folder} holds files this script did not create")
                return 2
            shutil.rmtree(folder)
    exp_dir.mkdir(parents=True)

    try:
        # ---- scene: two boxes, one rotated with map coords, fractional positions
        ms('(local a = Box name:"vsfA" length:10.25 width:20.5 height:5.125 pos:[100.33,-7.5,2.25] mapcoords:true; '
           'rotate a (eulerangles 15 0 90); '
           'local b = Box name:"vsfB" length:4 width:4 height:4 pos:[-3.125,1000.5,0]; true)')
        ref_a = ms_json(REF_VERTS.replace("@NAME@", "vsfA"))
        ref_b = ms_json(REF_VERTS.replace("@NAME@", "vsfB"))

        # ---- ITEM 8: OBJ (world) + JSON (local)
        obj_path = exp_dir / "two_boxes.obj"
        res = scene_files.export_geometry(path=str(obj_path), names=["vsfA", "vsfB"], format="obj")
        check(res["object_count"] == 2, "obj object_count == 2", res["object_count"])
        check(res["vertex_count"] == ref_a["nv"] + ref_b["nv"], "obj vertex_count", res["vertex_count"])
        check(res["face_count"] == ref_a["nf"] + ref_b["nf"], "obj face_count", res["face_count"])
        check(res["file_size"] == obj_path.stat().st_size, "obj file_size matches disk", res["file_size"])
        check(any("vsfB" in w and "UV" in w for w in res.get("warnings", [])), "obj warns: vsfB has no UVs",
              res.get("warnings"))
        parsed = read_obj(obj_path)
        text = obj_path.read_text(encoding="utf-8")
        check(parsed["objects"] == 2 and len(parsed["verts"]) == res["vertex_count"]
              and parsed["faces"] == res["face_count"], "obj re-read counts", parsed["faces"])
        check(parsed["vn"] == res["vertex_count"], "obj normals written per vertex", parsed["vn"])
        check(parsed["vt"] > 0, "obj UVs written for vsfA", parsed["vt"])
        check("," not in "".join(l for l in text.splitlines() if l.startswith("v ")), "obj has no comma decimals")
        va = parsed["verts"][: ref_a["nv"]]
        vb = parsed["verts"][ref_a["nv"]:]
        check(close(va[0], ref_a["world"][0]) and close(va[3], ref_a["world"][1]) and close(va[-1], ref_a["world"][2]),
              "obj vsfA world vertices match MAXScript", (va[0], ref_a["world"][0]))
        check(close(vb[0], ref_b["world"][0]) and close(vb[-1], ref_b["world"][2]),
              "obj vsfB world vertices match MAXScript", (vb[0], ref_b["world"][0]))

        handle_b = int(ms('(getNodeByName "vsfB" exact:true).inode.handle as string'))
        json_path = exp_dir / "two_boxes.json"
        res_j = scene_files.export_geometry(path=str(json_path), names=["vsfA"], handles=[handle_b],
                                            format="json", space="local")
        doc = json.loads(json_path.read_text(encoding="utf-8"))
        check(doc["space"] == "local" and len(doc["objects"]) == 2, "json parses, 2 objects, local space")
        oa = next(o for o in doc["objects"] if o["name"] == "vsfA")
        ob = next(o for o in doc["objects"] if o["handle"] == handle_b)
        check(len(oa["vertices"]) == ref_a["nv"] and len(oa["faces"]) == ref_a["nf"], "json vsfA counts")
        check(close(oa["vertices"][0], ref_a["local"][0]) and close(oa["vertices"][3], ref_a["local"][1]),
              "json vsfA local vertices match MAXScript", (oa["vertices"][0], ref_a["local"][0]))
        check(close(ob["vertices"][-1], ref_b["local"][2]), "json vsfB (by handle) local vertices match")
        check("uvs" in oa and "uvs" not in ob, "json uvs only where map channel 1 exists")
        check(min(min(f) for f in oa["faces"]) == 0, "json faces are 0-based")
        check(res_j["file_size"] == json_path.stat().st_size, "json file_size matches disk")

        try:
            scene_files.export_geometry(path=str(obj_path), names=["vsfA"])
            check(False, "existing export file refused without overwrite")
        except FileExistsError:
            check(True, "existing export file refused without overwrite")

        # Review 2026-10-12: Max writes a temp file that replaces the target only on success.
        before_bytes = obj_path.read_bytes()
        res_o = scene_files.export_geometry(path=str(obj_path), names=["vsfB"], overwrite=True)
        check(res_o["object_count"] == 1 and obj_path.read_bytes() != before_bytes,
              "overwrite=True replaces the target", res_o["object_count"])
        check(not list(exp_dir.glob("*.mcptmp")), "no temp file left after a successful export")
        kept = obj_path.read_bytes()
        staging = exp_dir / "two_boxes.obj.injected.mcptmp"
        script = scene_files.build_export_script(
            out_path=str(staging), expected_scene="", names=["vsfA"], handles=[], fmt="obj", space="world",
            include_normals=True, include_uvs=True, precision=9)
        marker = 'format "[" to:summary'
        check(script.count(marker) == 1, "failure injection point found once")
        script = script.replace(marker, marker + '\n            throw "mcp injected failure"', 1)
        failed = json.loads(ms(script))
        check("mcp injected failure" in str(failed.get("error", "")), "mid-export throw reported as an error", failed)
        check(not staging.exists(), "mid-export throw: temp file closed and deleted")
        check(obj_path.read_bytes() == kept, "mid-export throw: target untouched")

        outside = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "mcp_scene_files_refuse.obj"
        try:
            scene_files.export_geometry(path=str(outside), names=["vsfA"])
            check(False, "path outside allowed roots refused")
        except PathNotAllowedError as exc:
            check(not outside.exists(), "path outside allowed roots refused", str(exc)[:90])

        try:
            scene_files.export_geometry(path=str(exp_dir / "missing.obj"), names=["vsf_nope"])
            check(False, "missing object name refused")
        except RuntimeError as exc:
            check("vsf_nope" in str(exc) and not (exp_dir / "missing.obj").exists(), "missing object name refused")

        # ---- ITEM 9: versioned saves with render output following
        v1 = vtest / "test_V001.max"
        render_v1 = str(vtest / "renders" / "test_V001" / "test_V001_beauty.exr")
        ms(f"rendOutputFilename = {scene_files._ms_str(render_v1)}; true")
        ms('(local re = maxOps.GetCurRenderElementMgr(); re.RemoveAllRenderElements(); '
           're.AddRenderElement (Z_Depth elementname:"vsfZ"); '
           f're.SetRenderElementFilename 0 {scene_files._ms_str(str(vtest / "renders" / "test_V001" / "test_V001_z.exr"))}; true)')
        s1 = scene_files.save_scene_versioned(path=str(v1))
        check(v1.is_file() and s1["new_path"].lower() == str(v1).lower() and s1["old_path"] is None,
              "first save to test_V001.max", s1["new_path"])
        check(s1["render_output"]["new"] == render_v1, "V001 render output unchanged", s1["render_output"])

        s2 = scene_files.save_scene_versioned()
        v2 = vtest / "test_V002.max"
        check(v2.is_file() and s2["new_path"].lower() == str(v2).lower(), "versioned save -> V002", s2["new_path"])
        want2 = str(vtest / "renders" / "test_V002" / "test_V002_beauty.exr")
        check(s2["render_output"]["new"] == want2 and ms("rendOutputFilename") == want2,
              "render output follows to V002", s2["render_output"]["new"])
        check(s2.get("render_elements", [{}])[0].get("new", "").endswith(r"test_V002\test_V002_z.exr"),
              "render element path follows to V002", s2.get("render_elements"))

        # V-Ray branch: make V-Ray current (no render) with raw/VFB output names on V002.
        ms('(local vc = undefined; for c in RendererClass.classes where matchPattern (c as string) '
           'pattern:"V_Ray*" and not (matchPattern (c as string) pattern:"*GPU*") do vc = c; if vc != undefined do renderers.current = vc(); true)')
        is_vray = ms("matchPattern ((classof renderers.current) as string) pattern:\"V_Ray*\"") == "true"
        raw_v2 = str(vtest / "renders" / "test_V002" / "test_V002_raw.exr")
        if is_vray:
            ms(f"renderers.current.output_rawFileName = {scene_files._ms_str(raw_v2)}; "
               f"renderers.current.output_splitfilename = {scene_files._ms_str(raw_v2.replace('_raw', '_split'))}; true")

        s3 = scene_files.save_scene_versioned()
        v3 = vtest / "test_V003.max"
        check(v3.is_file() and s3["new_path"].lower() == str(v3).lower(), "versioned save -> V003", s3["new_path"])
        want3 = str(vtest / "renders" / "test_V003" / "test_V003_beauty.exr")
        check(s3["render_output"]["new"] == want3, "render output follows to V003", s3["render_output"]["new"])
        if is_vray:
            raw3 = s3.get("vray_output", {}).get("output_rawFileName", {}).get("new", "")
            check(raw3 == raw_v2.replace("V002", "V003") and ms("renderers.current.output_rawFileName") == raw3,
                  "V-Ray raw output follows to V003", raw3)
            split3 = s3.get("vray_output", {}).get("output_splitfilename", {}).get("new", "")
            check("test_V003_split" in split3, "V-Ray split output follows to V003", split3)
        else:
            check(False, "V-Ray renderer available for the V-Ray branch")
        check(ms("maxFileName") == "test_V003.max", "scene is now test_V003.max")

        # The saved V003 file carries the new render path: verify from disk without loading it.
        # (getMAXFileObjectNames/props would need a load; re-read rendOutputFilename via the open scene instead.)
        stub = vtest / "test_V004.max"
        stub.write_bytes(b"")
        try:
            scene_files.save_scene_versioned()
            check(False, "existing next version refused")
        except FileExistsError as exc:
            check(ms("maxFileName") == "test_V003.max" and stub.stat().st_size == 0,
                  "existing next version refused, nothing overwritten", str(exc)[:90])
        stub.unlink()

        try:
            scene_files.save_scene_versioned(path=str(Path(os.environ.get("SystemRoot", r"C:\Windows")) / "x_V001.max"))
            check(False, "versioned save outside allowed roots refused")
        except PathNotAllowedError:
            check(True, "versioned save outside allowed roots refused")

        # Review 2026-10-12: V-Ray GPU keeps output_* on V_Ray_settings (the renderer's own
        # are read-only mirrors); the versioned save must retarget them there.
        ms('(local vc = undefined; for c in RendererClass.classes where matchPattern (c as string) '
           'pattern:"V_Ray_GPU*" do vc = c; if vc != undefined do renderers.current = vc(); true)')
        if ms('matchPattern ((classof renderers.current) as string) pattern:"V_Ray_GPU*"') == "true":
            host = ("renderers.current.V_Ray_settings"
                    if ms("(isProperty renderers.current #V_Ray_settings) as string") == "true" else "renderers.current")
            raw_v3 = str(vtest / "renders" / "test_V003" / "test_V003_raw.exr")
            ms(f"{host}.output_rawFileName = {scene_files._ms_str(raw_v3)}; true")
            ms("renderSceneDialog.open(); true")
            s4 = scene_files.save_scene_versioned()
            raw4 = s4.get("vray_output", {}).get("output_rawFileName", {}).get("new", "")
            want4 = raw_v3.replace("V003", "V004")
            check(raw4 == want4 and ms(f"{host}.output_rawFileName") == want4,
                  "V-Ray GPU raw output follows to V004 on its owner", raw4)
            check(ms("maxFileName") == "test_V004.max", "scene is now test_V004.max")
            check(ms("renderSceneDialog.isOpen() as string") == "true", "Render Setup reopened after the save")
            ms("renderSceneDialog.close(); true")
        else:
            check(False, "V-Ray GPU renderer available for the GPU save branch")

        # ---- scene_setup round trip
        prev_lock = ms("rendLockImageAspectRatio") == "true"
        first =scene_files.scene_setup(units="mm", display_units="cm", fps=25, frame_range=[10, 250],
                                        render_size=[1921, 1081], pixel_aspect=1.25)
        cur = first["current"]
        check(cur["units"] == "millimeters" and cur["metric_type"] == "centimeters" and cur["fps"] == 25
              and cur["frame_start"] == 10 and cur["frame_end"] == 250 and cur["render_width"] == 1921
              and cur["render_height"] == 1081 and abs(cur["pixel_aspect"] - 1.25) < 1e-6,
              "scene_setup applied and read back", cur)
        live = ms_json('("{\\"u\\":\\"" + (units.SystemType as string) + "\\",\\"w\\":" + (renderWidth as string) '
                       '+ ",\\"fps\\":" + (frameRate as string) + ",\\"s\\":" + (animationRange.start.frame as string) + "}")')
        check(live == {"u": "millimeters", "w": 1921, "fps": 25, "s": 10.0}, "scene_setup independent MAXScript readback", live)
        prev = first["previous"]
        disp = prev["display_type"] if prev["display_type"] == "generic" else (
            prev["metric_type"] if prev["display_type"] == "metric" else prev["us_type"])
        back = scene_files.scene_setup(units=prev["units"], display_units=disp, fps=prev["fps"],
                                       frame_range=[prev["frame_start"], prev["frame_end"]],
                                       render_size=[prev["render_width"], prev["render_height"]],
                                       pixel_aspect=prev["pixel_aspect"])
        restored = {k: back["current"][k] for k in prev}
        check(restored == prev, "scene_setup restores previous values", back["current"])
        # Render Setup open + image-aspect lock on: values must stick, dialog and lock come back.
        ms("rendLockImageAspectRatio = true; renderSceneDialog.open(); true")
        locked = scene_files.scene_setup(render_size=[1001, 333])
        state = ms_json('("{\\"open\\":" + (renderSceneDialog.isOpen() as string) + ",\\"lock\\":" + '
                        '(rendLockImageAspectRatio as string) + ",\\"w\\":" + (renderWidth as string) + '
                        '",\\"h\\":" + (renderHeight as string) + "}")')
        check(state == {"open": True, "lock": True, "w": 1001, "h": 333}
              and locked["current"]["render_width"] == 1001,
              "scene_setup with Render Setup open and aspect lock on", state)
        ms("renderSceneDialog.close(); true")
        scene_files.scene_setup(render_size=[prev["render_width"], prev["render_height"]])
        ms(f"rendLockImageAspectRatio = {'true' if prev_lock else 'false'}; true")
        try:
            scene_files.scene_setup(frame_range=[5, 5])
            check(False, "scene_setup rejects empty range")
        except ValueError:
            check(True, "scene_setup rejects empty range")
    finally:
        # Guarded reset: only our own vtest scene (or an untitled one) may be discarded.
        cur_path = ms("maxFilePath")
        cur_name = ms("maxFileName")
        own = cur_name == "" or (os.path.normcase(os.path.normpath(cur_path)) == os.path.normcase(str(vtest))
                                 and cur_name.lower().startswith("test_v"))
        if own and ms('((dotNetClass "System.Diagnostics.Process").GetCurrentProcess()).Id as string') == str(args.pid):
            ms("resetMaxFile #noPrompt; true")
            check(ms("maxFileName") == "", "scratch scene reset after the run")
        else:
            check(False, "guarded reset", f"{cur_path}{cur_name} is not this script's scene; left alone")
        for folder in (exp_dir, vtest):
            shutil.rmtree(folder, ignore_errors=True)
        check(not exp_dir.exists() and not vtest.exists(), "temp files removed")

    if args.quit:
        if ms("maxFileName") == "":
            try:
                client.send_command("quitMax #noPrompt", timeout=10.0)
            except Exception as exc:  # the pipe may close before a reply
                print(f"quitMax sent ({type(exc).__name__})")
    print(f"\n{'ALL PASS' if not FAILURES else 'FAILURES: ' + ', '.join(FAILURES)}")
    return 0 if not FAILURES else 1


if __name__ == "__main__":
    raise SystemExit(main())
