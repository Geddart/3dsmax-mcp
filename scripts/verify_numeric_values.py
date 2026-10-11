"""Live acceptance: fractional values, Point3 and colours survive a non-English
Windows locale (regression for the de-DE decimal-comma bug, 2026-10-12), and
every native write is read back (angles in degrees, percentages 0-100,
MAXScript-fallback expressions) with PARTIAL_APPLY on anything that did not
stick.

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
from maxmcp.max_client import MaxBridgeError
from maxmcp.tool_response import _error_from_exception
from maxmcp.tools.routing import select_max_instance, release_max_instance
from maxmcp.tools.objects import create_object, set_object_property
from maxmcp.tools.modifiers import add_modifier, set_modifier_property
from maxmcp.tools.material_ops import (
    assign_material,
    get_material_slots,
    set_material_properties,
    set_material_property,
)
from maxmcp.tools.material_network import inspect_material_network
from maxmcp.tools.transform import transform_object
from maxmcp.tools.inspect import inspect_properties
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


def check_num(label, got, want, tol=1e-3):
    try:
        ok = abs(float(got) - want) <= tol
    except (TypeError, ValueError):
        ok = False
    print(("PASS " if ok else "FAIL ") + f"{label}: got {got!r} want {want!r}")
    if not ok:
        fails.append(label)


def expect_partial(label, fn, **kwargs):
    """Call a tool that must fail with PARTIAL_APPLY; return the error dict (or {})."""
    try:
        result = fn(**kwargs)
    except MaxBridgeError as exc:
        error = _error_from_exception(exc)
        ok = error.get("code") == "PARTIAL_APPLY" and error.get("retryable") is False
        print(("PASS " if ok else "FAIL ") + f"{label}: code={error.get('code')} retryable={error.get('retryable')}")
        if not ok:
            fails.append(label)
        return error
    print(f"FAIL {label}: expected PARTIAL_APPLY, got success {str(result)[:160]!r}")
    fails.append(label)
    return {}


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

    # ── Read-back by default (2026-10-12) ─────────────────────────────
    # 7. TYPE_ANGLE: user text is degrees (was written raw into radians -> 1718.87).
    create_object(type="Cylinder", name="cS", radius=5)
    r = json.loads(set_object_property(name="cS", property="sliceFrom", value="30"))
    check_num("angle sliceFrom 30 -> MAXScript reads 30", ms("$cS.sliceFrom"), 30.0)
    check_num("angle sliceFrom applied (native read-back, degrees)", r.get("applied"), 30.0)
    create_object(type="Cylinder", name="cS2", params="radius:5 slice:true sliceTo:45.5")
    check_num("angle create_object sliceTo:45.5", ms("$cS2.sliceTo"), 45.5)
    check("bool create_object slice:true", ms("$cS2.slice as string"), "true")
    # Cylinder.sliceOn is a MAXScript alias that silently ignores writes (reads
    # back false): read-back turns that former silent no-op into PARTIAL_APPLY.
    expect_partial("silently ignored alias sliceOn:true -> PARTIAL_APPLY", set_object_property,
                   name="cS2", property="sliceOn", value="false")
    insp = json.loads(inspect_properties(name="cS", target="baseobject"))
    props = {p.get("name", "").lower(): p for p in insp.get("properties", [])}
    slice_prop = props.get("slicefrom", {})
    check_num("inspect_properties reports sliceFrom in degrees", slice_prop.get("value"), 30.0)
    check("inspect_properties labels sliceFrom unit", slice_prop.get("unit"), "degrees")

    # 8. TYPE_PCNT_FRAC: user text is 0-100 (was written raw as a fraction -> 5000).
    assign_material(names=["cS"], material_class="Standardmaterial")
    r = json.loads(set_material_property(name="cS", property="opacity", value="50"))
    check_num("pcnt Standard opacity 50 -> MAXScript reads 50", ms("$cS.material.opacity"), 50.0)
    check_num("pcnt opacity applied (native read-back, percent)", r.get("applied"), 50.0)
    set_material_properties(name="cS", properties={"opacity": "75", "glossiness": "20"})
    check_num("pcnt set_material_properties opacity 75", ms("$cS.material.opacity"), 75.0)
    # The material formatters report the same units, labelled.
    net = json.loads(inspect_material_network(name="cS"))
    root = (net.get("nodes") or [{}])[0]
    check_num("inspect_material_network opacity in percent", (root.get("values") or {}).get("opacity"), 75.0)
    check("inspect_material_network labels opacity", (root.get("valueUnits") or {}).get("opacity"), "percent")
    slots = json.loads(get_material_slots(name="cS", include_values=True, slot_scope="all", max_slots=200))
    opacity_slot = next((s for s in slots.get("numericSlots", []) if s.get("name") == "opacity"), {})
    check_num("get_material_slots opacity in percent", opacity_slot.get("value"), 75.0)
    check("get_material_slots labels opacity", opacity_slot.get("unit"), "percent")

    # 9. MAXScript-fallback expression value, read back inside the same script.
    create_object(type="Cylinder", name="cE", params="radius:(2*3.25)")
    check_num("expression radius:(2*3.25) -> 6.5", ms("$cE.radius"), 6.5)
    r = json.loads(set_object_property(name="cE", property="height", value="(10 * 1.5)"))
    check_num("expression set_object_property height (10 * 1.5)", ms("$cE.height"), 15.0)

    # 10. Deliberate mismatch: an integer param given 12.5 is truncated -> PARTIAL_APPLY.
    err = expect_partial("mismatch heightsegs 12.5 -> PARTIAL_APPLY", set_object_property,
                         name="cE", property="heightsegs", value="12.5")
    keys = (err.get("details") or {}).get("keys") or [{}]
    check("mismatch reports the applied value", str(keys[0].get("applied")), "12")

    # 11. Unsettable key on create_object: node is KEPT, handle reported, no duplicate.
    err = expect_partial("create_object bogusprop -> PARTIAL_APPLY", create_object,
                         type="Cylinder", name="cP", params="radius:5 bogusprop:3")
    details = err.get("details") or {}
    handle = details.get("handle")
    check("PARTIAL_APPLY details carry the created handle", isinstance(handle, int) and handle > 0, True)
    check("created node survives PARTIAL_APPLY (undo hold committed)",
          ms(f"(isValidNode (getAnimByHandle {handle})) as string") if handle else "no handle", "true")
    check("no duplicate created by a retry", ms('((for o in objects where o.name == "cP" collect o).count) as string'), "1")
    check_num("valid key applied despite PARTIAL_APPLY", ms("$cP.radius"), 5.0)
    check("failing key named", [k.get("key") for k in details.get("keys", [])], ["bogusprop"])

    # 12. add_modifier with an unknown key keeps the modifier.
    err = expect_partial("add_modifier bogus key -> PARTIAL_APPLY", add_modifier,
                         name="cP", modifier="Bend", params="angle:20 notAParam:1")
    check("modifier kept after PARTIAL_APPLY", ms("$cP.modifiers.count as string"), "1")
    check_num("modifier angle applied", ms("$cP.modifiers[1].angle"), 20.0)

    # 13. set_material_properties: one bad key fails loud, the good one applies.
    err = expect_partial("set_material_properties bad key -> PARTIAL_APPLY", set_material_properties,
                         name="cS", properties={"opacity": "40", "noSuchProp": "1"})
    check_num("good key applied alongside the failure", ms("$cS.material.opacity"), 40.0)

    # 14. transform_object on a constrained node: the move does not stick.
    ms('Box name:"bC" length:5 width:5 height:5; $bC.position.controller = Position_Constraint()')
    err = expect_partial("transform_object move on Position_Constraint -> PARTIAL_APPLY", transform_object,
                         name="bC", move=[10, 0, 0])
    check("transform failure names the move key",
          [k.get("key") for k in (err.get("details") or {}).get("keys", [])], ["move"])
    ms('Box name:"bF" length:5 width:5 height:5')
    r = json.loads(transform_object(name="bF", move=[10.5, 0, 0], rotate=[0, 0, 30], scale=[2]))
    check_num("transform_object move read-back", ms("$bF.pos.x"), 10.5)
    check("transform_object reports applied", sorted((r.get("applied") or {}).keys()), ["move", "rotate", "scale"])
    # No false PARTIAL_APPLY on a parented, rotated, non-uniformly scaled node.
    ms('(local p = Point name:"tP" pos:[5,5,0]; p.rotation = eulerAngles 10 20 30; '
       'local b = Box name:"tB" length:5 width:5 height:5 pos:[10,0,0]; b.parent = p; '
       'rotate b (eulerAngles 15 0 40); scale b [1,2,0.5]; "ok")')
    for coord in ("world", "local"):
        try:
            r = json.loads(transform_object(name="tB", move=[1, 2, 3], rotate=[10, 20, 30],
                                            scale=[1.5, 1, 2], coordinate_system=coord))
            check(f"transform_object {coord} on parented/rotated/non-uniform node succeeds",
                  sorted((r.get("applied") or {}).keys()), ["move", "rotate", "scale"])
        except MaxBridgeError as exc:
            err = _error_from_exception(exc)
            check(f"transform_object {coord} on parented/rotated/non-uniform node succeeds",
                  err.get("code"), "no error")
            print("   details:", json.dumps(err.get("details"))[:600])
finally:
    ms("delete objects")
    release_max_instance()

print("\nRESULT:", "ALL PASS" if not fails else f"{len(fails)} FAIL: {fails}")
sys.exit(1 if fails else 0)
