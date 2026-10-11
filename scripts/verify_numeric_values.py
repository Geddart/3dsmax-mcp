"""Live acceptance: fractional values, Point3 and colours survive a non-English
Windows locale (regression for the de-DE decimal-comma bug, 2026-10-12).

Run against a SCRATCH Max with an Untitled scene, never a production instance:
    set MCP_UI_DENY_PIDS=<every protected Max PID>
    uv run python scripts/verify_numeric_values.py <scratch PID>
Every case writes through a real MCP tool and reads back via MAXScript.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import json

from maxmcp.server import client
from maxmcp.tools.routing import select_max_instance, release_max_instance
from maxmcp.tools.objects import create_object, set_object_property
from maxmcp.tools.modifiers import add_modifier, set_modifier_property
from maxmcp.tools.material_ops import assign_material
from maxmcp.tools.execute import execute_maxscript

pid = int(sys.argv[1])
select_max_instance(pid)
ms = lambda e: client.send_command(e).get("result")  # noqa: E731
assert ms("maxFileName") == "", "scratch Max must be Untitled"
assert int(ms('((dotNetClass "System.Diagnostics.Process").GetCurrentProcess()).Id as string')) == pid
ms("resetMaxFile #noPrompt")

fails = []


def check(label, got, want):
    ok = got == want
    print(("PASS " if ok else "FAIL ") + f"{label}: got {got!r} want {want!r}")
    if not ok:
        fails.append(label)


def tail(r):
    return str(r)[-160:].replace("\n", " ")


try:
    # 1. create_object with fractional radius, params and pos
    create_object(type="Cylinder", name="cA", radius=4.5)
    check("create_object radius=4.5", ms("$cA.radius as string"), "4.5")
    create_object(type="Cylinder", name="cB", params="radius:6.5 height:10.25", pos=[-276.8, -3.5, -3], pos_mode="pivot")
    check("create_object params radius:6.5", ms("$cB.radius as string"), "6.5")
    check("create_object params height:10.25", ms("$cB.height as string"), "10.25")
    check("create_object pos", ms("$cB.pos as string"), "[-276.8,-3.5,-3]")

    # 2. set_object_property
    set_object_property(name="cA", property="radius", value="4.75")
    check("set_object_property radius", ms("$cA.radius as string"), "4.75")
    set_object_property(name="cA", property="pos", value="[-276.8,-3.5,-3]")
    check("set_object_property pos", ms("$cA.pos as string"), "[-276.8,-3.5,-3]")

    # 3. Extrude (PB1) via add_modifier + set_modifier_property
    ms('Rectangle name:"rA" length:10 width:10')
    r = add_modifier(name="rA", modifier="Extrude", params="amount:6.5")
    check("add_modifier Extrude amount:6.5", ms("$rA.modifiers[1].amount as string"), "6.5")
    set_modifier_property(property_name="amount", property_value="7.25", name="rA", modifier_class="Extrude")
    check("set_modifier_property amount 7.25", ms("$rA.modifiers[1].amount as string"), "7.25")
    ms('Rectangle name:"rB" length:10 width:10')
    add_modifier(name="rB", modifier="Bend", params="angle:12.5")
    check("add_modifier Bend angle:12.5 (PB2)", ms("$rB.modifiers[1].angle as string"), "12.5")

    # 4. Materials: colour scaling + fractional values
    assign_material(names=["cA"], material_class="PhysicalMaterial", params="base_color:(color 48 32 22) roughness:0.7")
    check("Physical base_color", ms("$cA.material.base_color as string"), "(color 48 32 22)")
    check("Physical roughness 0.7", ms("$cA.material.roughness as string"), "0.7")
    assign_material(names=["cB"], material_class="Standardmaterial", params="diffuse:(color 48 32 22) glossiness:35")
    check("Standard diffuse", ms("$cB.material.diffuse as string"), "(color 48 32 22)")
    if ms("(VRayMtl != undefined) as string") == "true":
        r = assign_material(names=["cB"], material_class="VRayMtl", params="diffuse:(color 48 32 22) reflection_glossiness:0.7")
        check("VRayMtl diffuse", ms("$cB.material.diffuse as string"), "(color 48 32 22)")
        check("VRayMtl reflection_glossiness 0.7", ms("$cB.material.reflection_glossiness as string"), "0.7")
    else:
        print("SKIP VRayMtl: V-Ray not loaded")

    # 5. Freecamera
    r = create_object(type="Freecamera", name="camA")
    check("create_object Freecamera", ms('(isValidNode $camA) as string'), "true")

    # 6. Float results come back with '.' (execute_maxscript result path)
    raw = execute_maxscript(code="4.5 * 1.0")
    try:
        parsed = json.loads(raw)
        val = parsed.get("result") if isinstance(parsed, dict) else parsed
    except ValueError:
        val = raw
    check("execute_maxscript float result", str(val), "4.5")
finally:
    ms("delete objects")
    release_max_instance()

print("\nRESULT:", "ALL PASS" if not fails else f"{len(fails)} FAIL: {fails}")
sys.exit(1 if fails else 0)
