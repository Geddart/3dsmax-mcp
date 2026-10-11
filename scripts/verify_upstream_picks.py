"""Live acceptance for the upstream picks on wl/native (2026-10-12):

* class lookup by UI label / internal / non-localized name, AMBIGUOUS on a
  name shared by two different classes (8a756dc);
* UTF-8 (umlaut) texture paths survive inspect_material_network and
  material_roles (2dd9ed6, 5c960bb, c2530b0);
* material_roles resolves slot -> file and flags a filename mismatch (6e17afe);
* contact_check classifies penetrating / near_gap pairs with fractional
  depth and gap on a de-DE Windows (57bc91d, c2530b0);
* assign_material validates targets and params before assigning (cae21ab
  hunk): BAD_PARAM / NOT_FOUND / AMBIGUOUS leave the target untouched, a key
  that does not stick raises PARTIAL_APPLY with nothing assigned.

Run against a SCRATCH Max with an Untitled scene, never a production instance:
    set MCP_UI_DENY_PIDS=<every protected Max PID>
    uv run python scripts/verify_upstream_picks.py <scratch PID>
"""
import json
import os
import struct
import sys
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from maxmcp.server import client
from maxmcp.max_client import MaxBridgeError
from maxmcp.tool_response import _error_from_exception
from maxmcp.tools.routing import select_max_instance
from maxmcp.tools.objects import create_object
from maxmcp.tools.material_ops import assign_material, set_material_property
from maxmcp.tools.material_network import inspect_material_network
from maxmcp.tools.material_roles import material_roles
from maxmcp.tools.contact_check import contact_check

pid = int(sys.argv[1])
select_max_instance(pid)
ms = lambda e: client.send_command(e).get("result")  # noqa: E731
assert ms("maxFileName") == "", "scratch Max must be Untitled"
assert int(ms('((dotNetClass "System.Diagnostics.Process").GetCurrentProcess()).Id as string')) == pid
ms("resetMaxFile #noPrompt")

fails = []


def check(label, ok, info=""):
    print(("PASS " if ok else "FAIL ") + label + (f": {info}" if info else ""))
    if not ok:
        fails.append(label)


def expect_error(label, code, fn, **kwargs):
    try:
        result = fn(**kwargs)
    except MaxBridgeError as exc:
        error = _error_from_exception(exc)
        check(label, error.get("code") == code, f"code={error.get('code')} msg={str(error.get('message'))[:120]!r}")
        return error
    check(label, False, f"expected {code}, got success {str(result)[:160]!r}")
    return {}


def write_png(path: Path, rgb=(200, 120, 40)) -> None:
    """A real 4x4 RGB PNG, so the bitmap loads and no extension-mismatch issue fires."""
    raw = b"".join(b"\x00" + bytes(rgb) * 4 for _ in range(4))

    def chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)

    png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 4, 4, 8, 2, 0, 0, 0))
    png += chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b"")
    path.write_bytes(png)


def ms_str(path: str) -> str:
    return '"' + path.replace("\\", "\\\\").replace('"', '\\"') + '"'


try:
    # ── 1. class lookup by localized label / internal name, AMBIGUOUS ───────
    labels = json.loads(client.send_command(json.dumps({"superclass": "geometry"}),
                                            cmd_type="native:list_plugin_classes")["result"])
    pairs = []

    def walk(o):
        if isinstance(o, dict):
            if "name" in o and "internalName" in o:
                pairs.append((o["name"], o["internalName"]))
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
    walk(labels)
    box_label = next((n for n, i in pairs if i == "Box"), None)
    # Mutating handlers see ClassName() non-localized, so a German UI label
    # ("Quader") does not resolve there (pre-existing; read-only introspect
    # does see it). Exercise the label route with an English label that
    # differs from the script name instead: "Physical Material".
    print(f"INFO localized Box label {box_label!r}: create_object accepts script/internal names")
    if box_label and box_label != "Box":
        intro = json.loads(client.send_command(json.dumps({"class_name": box_label}),
                                               cmd_type="native:introspect_class")["result"])
        check(f"introspect_class by UI label {box_label!r} -> Box", intro.get("internalName") == "Box",
              str(intro.get("internalName")))
    create_object(type="Box", name="lblTarget", length=5, width=5, height=5)
    r = json.loads(assign_material(names=["lblTarget"], material_class="Physical Material"))
    check("assign_material by class label 'Physical Material'",
          ms("(classOf $lblTarget.material) as string") == "PhysicalMaterial",
          f"{ms('(classOf $lblTarget.material) as string')} requested={r['material'].get('requestedClass')}")
    create_object(type="ChamferBox", name="clsInternal", length=10, width=10, height=10, fillet=1)
    check("create_object by internal name ChamferBox", ms("(classOf $clsInternal) as string") == "ChamferBox")
    create_object(type="box", name="clsLower", length=4, width=4, height=4)
    check("create_object case-insensitive 'box'", ms("(classOf $clsLower) as string") == "Box")
    shared = [i for i in {i for _, i in pairs} if sum(1 for _, x in pairs if x == i) > 1]
    print("internal names shared by several classes:", shared)
    if shared:
        before = ms("objects.count as string")
        expect_error(f"create_object '{shared[0]}' (two classes) -> AMBIGUOUS", "AMBIGUOUS",
                     create_object, type=shared[0], name="clsAmb")
        check("AMBIGUOUS created nothing", ms("objects.count as string") == before)

    # ── 2. umlaut texture paths through the material tools ──────────────────
    tex_dir = Path(os.environ["TEMP"]) / "3dsmax-mcp" / "Prüfung_Ümlaut"
    tex_dir.mkdir(parents=True, exist_ok=True)
    base_png = tex_dir / "Grün_Stoff_basecolor.png"
    rough_png = tex_dir / "Grün_Stoff_roughness.png"
    missing_png = tex_dir / "Grün_fehlt_normal.png"
    write_png(base_png)
    write_png(rough_png, (90, 90, 90))
    if missing_png.exists():
        missing_png.unlink()

    create_object(type="Box", name="texBox", length=20, width=20, height=20)
    r = json.loads(assign_material(names=["texBox"], material_class="PhysicalMaterial",
                                   material_name="Mat_Grün", params="roughness:0.35"))
    check("assign_material PhysicalMaterial with umlaut name", r.get("material", {}).get("name") == "Mat_Grün",
          str(r.get("material")))
    set_material_property(name="texBox", property="base_color_map",
                          value=f"(Bitmaptexture filename:{ms_str(str(base_png))})")
    # A roughness file wired into the base weight slot -> advisory mismatch.
    set_material_property(name="texBox", property="base_weight_map",
                          value=f"(Bitmaptexture filename:{ms_str(str(rough_png))})")
    set_material_property(name="texBox", property="bump_map",
                          value=f"(Bitmaptexture filename:{ms_str(str(missing_png))})")
    readback = ms("$texBox.material.base_color_map.filename")
    check("umlaut filename read back via MAXScript", readback == str(base_png), repr(readback))

    net = json.loads(inspect_material_network(name="texBox"))
    manifest = {f.get("path"): f for f in net.get("fileManifest", [])}
    print("fileManifest:", json.dumps(net.get("fileManifest"), ensure_ascii=False)[:600])
    entry = manifest.get(str(base_png))
    check("inspect_material_network: umlaut path exists=true", bool(entry) and entry.get("exists") is True,
          json.dumps(entry, ensure_ascii=False))
    miss = manifest.get(str(missing_png))
    check("inspect_material_network: missing umlaut path exists=false", bool(miss) and miss.get("exists") is False,
          json.dumps(miss, ensure_ascii=False))
    check("inspect_material_network: complete=true", net.get("complete") is True, str(net.get("complete")))

    # ── 3. material_roles ────────────────────────────────────────────────────
    roles = material_roles(names=["Mat_Grün"])
    print("material_roles:", json.dumps(roles, ensure_ascii=False)[:1500])
    mats = roles.get("materials") or []
    check("material_roles returned the material", len(mats) == 1 and not roles.get("failed"),
          f"returned={roles.get('returned')} failed={roles.get('failed')}")
    if mats:
        m = mats[0]
        rows = m.get("roles") or m.get("sources") or []
        files = json.dumps(m, ensure_ascii=False)
        check("material_roles: base colour file is the umlaut path", str(base_png).replace("\\", "\\\\") in files)
        check("material_roles: missing umlaut file listed", str(missing_png) in (m.get("missing_files") or []),
              str(m.get("missing_files")))
        check("material_roles: roughness file in base weight flagged as mismatch", bool(m.get("mismatches")),
              json.dumps(m.get("mismatches"), ensure_ascii=False)[:300])
    roles_obj = material_roles(names=["texBox"])
    check("material_roles by object name", roles_obj.get("returned") == 1, str(roles_obj.get("failed")))

    # ── 4. contact_check: fractional depth / gap on a decimal-comma Windows ─
    ms('Box name:"ccA" length:10 width:10 height:10 pos:[0,0,0]')
    ms('Box name:"ccB" length:10 width:10 height:10 pos:[7.75,1.5,1.25]')
    ms('Box name:"ccC" length:10 width:10 height:10 pos:[-10.5,0,0]')
    scene_before = ms("objects.count as string") + "|" + ms("selection.count as string")
    report = contact_check(names=["ccA", "ccB", "ccC"], tolerance=0.01, near_gap=1.0)
    print("contact_check:", json.dumps(report)[:900])
    by_pair = {tuple(sorted((p["a"], p["b"]))): p for p in report.get("pairs", [])}
    ab = by_pair.get(("ccA", "ccB"))
    ac = by_pair.get(("ccA", "ccC"))
    check("contact_check A/B penetrating", bool(ab) and ab["status"] == "penetrating", str(ab and ab["status"]))
    check("contact_check A/B depth 1.25", bool(ab) and abs(ab["depth"] - 1.25) < 1e-3, str(ab and ab["depth"]))
    check("contact_check A/C near_gap", bool(ac) and ac["status"] == "near_gap", str(ac and ac["status"]))
    check("contact_check A/C gap 0.5", bool(ac) and ac["gap"] is not None and abs(ac["gap"] - 0.5) < 1e-3,
          str(ac and ac["gap"]))
    check("contact_check tolerance parsed as 0.01", abs(report.get("tolerance", 0) - 0.01) < 1e-9,
          str(report.get("tolerance")))
    # Defaults: 0.1 mm / 10 mm decoded without locale-dependent decimals.
    one_mm = float(ms('(units.decodeValue "1mm") as string'))
    default_report = contact_check(names=["ccA", "ccC"])
    check("contact_check default tolerance = 0.1 mm", abs(default_report["tolerance"] - one_mm / 10) < 1e-9,
          f"{default_report['tolerance']} (1mm={one_mm})")
    check("contact_check default near_gap = 10 mm", abs(default_report["near_gap"] - one_mm * 10) < 1e-9,
          str(default_report["near_gap"]))
    scene_after = ms("objects.count as string") + "|" + ms("selection.count as string")
    check("contact_check left the scene unchanged", scene_after == scene_before, f"{scene_before} -> {scene_after}")

    # ── 5. assign_material validates before assigning ───────────────────────
    ms('b = Box name:"m5" length:5 width:5 height:5; b.material = Standardmaterial name:"orig"')
    orig = lambda: ms("$m5.material.name")  # noqa: E731
    expect_error("assign_material params without colon -> BAD_PARAM", "BAD_PARAM", assign_material,
                 names=["m5"], material_class="PhysicalMaterial", params="roughness 0.5")
    check("BAD_PARAM left m5's material unchanged", orig() == "orig", orig())
    expect_error("assign_material unclosed value -> BAD_PARAM", "BAD_PARAM", assign_material,
                 names=["m5"], material_class="PhysicalMaterial", params="base_color:(color 1 2 3")
    expect_error("assign_material unknown name -> NOT_FOUND", "NOT_FOUND", assign_material,
                 names=["m5", "doesNotExist_xyz"], material_class="PhysicalMaterial", params="roughness:0.5")
    check("NOT_FOUND left m5's material unchanged", orig() == "orig", orig())
    expect_error("assign_material unknown handle -> NOT_FOUND", "NOT_FOUND", assign_material,
                 handles=[987654321], material_class="PhysicalMaterial")
    ms('Box name:"dup" pos:[50,0,0]; Box name:"dup" pos:[60,0,0]')
    expect_error("assign_material duplicate name -> AMBIGUOUS", "AMBIGUOUS", assign_material,
                 names=["m5", "dup"], material_class="PhysicalMaterial")
    check("AMBIGUOUS left m5's material unchanged", orig() == "orig", orig())
    err = expect_error("assign_material bad key -> PARTIAL_APPLY", "PARTIAL_APPLY", assign_material,
                       names=["m5"], material_class="PhysicalMaterial", material_name="halfMat",
                       params="roughness:0.25 bogus_param_xyz:3")
    check("PARTIAL_APPLY assigned nothing (m5 still orig)", orig() == "orig", orig())
    details = err.get("details") or {}
    check("PARTIAL_APPLY details.assigned == []", details.get("assigned") == [], str(details.get("assigned")))
    keys = [k.get("key") for k in details.get("keys", [])]
    check("PARTIAL_APPLY names the failed key", keys == ["bogus_param_xyz"], str(keys))
    h = details.get("handle")
    check("PARTIAL_APPLY reports the unassigned material handle", bool(h), str(h))
    if h:
        check("unassigned material holds the applied roughness",
              ms(f"(getAnimByHandle {int(h)}).roughness as string") == "0.25",
              ms(f"(getAnimByHandle {int(h)}).roughness as string"))
    r = json.loads(assign_material(names=["m5"], material_class="PhysicalMaterial", material_name="goodMat",
                                   params="roughness:0.35 base_color:(color 200 100 50)"))
    check("assign_material success assigns", orig() == "goodMat", orig())
    check("appliedParameters lists both keys", r.get("appliedParameters") == ["roughness", "base_color"],
          str(r.get("appliedParameters")))
    check("roughness read back 0.35", ms("$m5.material.roughness as string") == "0.35")
    r = json.loads(assign_material(names=["m5"], material_class="Standardmaterial", material_name="stdMat",
                                   params="diffuse:(color 48 32 22) glossiness:35"))
    check("Standardmaterial diffuse (MAXScript path before assignment)",
          ms("$m5.material.diffuse as string") == "(color 48 32 22)", ms("$m5.material.diffuse as string"))
    check("Standardmaterial glossiness 35", ms("$m5.material.glossiness as string") == "35.0",
          ms("$m5.material.glossiness as string"))
finally:
    assert ms("maxFileName") == ""
    ms("resetMaxFile #noPrompt")

print("\nRESULT:", "ALL PASS" if not fails else f"{len(fails)} FAIL: {fails}")
sys.exit(1 if fails else 0)
