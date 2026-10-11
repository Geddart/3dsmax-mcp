"""Live acceptance for the V-Ray tools (maxmcp/tools/vray.py).

Run against a SCRATCH Max with an Untitled scene and V-Ray installed, never a
production instance:
    set MCP_UI_DENY_PIDS=<every protected Max PID>
    uv run python scripts/verify_vray.py <scratch PID> [--quit]
Every write goes through the MCP tool and is checked again with raw MAXScript.
Nothing is rendered. --quit closes the scratch Max afterwards (after asserting
the scene is still Untitled).
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from maxmcp.server import client  # noqa: E402
from maxmcp.tools.routing import select_max_instance  # noqa: E402
from maxmcp.tools import vray as V  # noqa: E402

pid = int(sys.argv[1])
select_max_instance(pid)
ms = lambda e: client.send_command(e).get("result")  # noqa: E731
assert ms("maxFileName") == "", "scratch Max must be Untitled"
assert int(ms('((dotNetClass "System.Diagnostics.Process").GetCurrentProcess()).Id as string')) == pid
ms("renderSceneDialog.close()")
ms("resetMaxFile #noPrompt")
assert ms("maxFileName") == ""

fails = []


def check(label, got, want):
    ok = got == want
    print(("PASS " if ok else "FAIL ") + f"{label}: got {got!r} want {want!r}")
    if not ok:
        fails.append(label)


def expect_error(label, fn, *args, contains="", **kwargs):
    try:
        fn(*args, **kwargs)
    except Exception as exc:  # noqa: BLE001
        ok = contains in str(exc)
        print(("PASS " if ok else "FAIL ") + f"{label}: {type(exc).__name__}: {str(exc)[:160]}")
        if not ok:
            fails.append(label)
        return
    print(f"FAIL {label}: no error raised")
    fails.append(label)


try:
    # 1. CPU <-> GPU, with GPU settings surviving a round trip via the stash
    cpu = json.loads(V.vray_set_renderer("cpu"))
    check("cpu class is V-Ray CPU", cpu["renderer_class"].startswith("V_Ray_") and "GPU" not in cpu["renderer_class"], True)
    check("cpu class live", ms("(classOf renderers.current) as string"), cpu["renderer_class"])
    gpu = json.loads(V.vray_set_renderer("gpu"))
    check("gpu class is V-Ray GPU", gpu["renderer_class"].startswith("V_Ray_GPU"), True)
    check("gpu class live", ms("(classOf renderers.current) as string"), gpu["renderer_class"])
    V.vray_set_settings({"max_render_time": 1.5})
    back = json.loads(V.vray_set_renderer("cpu"))
    check("cpu again", ms("(classOf renderers.current) as string"), cpu["renderer_class"])
    check("cpu again changed", back["changed"], True)
    again = json.loads(V.vray_set_renderer("gpu"))
    check("gpu settings restored flag", again["restored_settings"], True)
    check("gpu max_render_time survived round trip", ms("renderers.current.max_render_time as string"), "1.5")
    check("no-op switch", json.loads(V.vray_set_renderer("gpu"))["changed"], False)
    V.vray_set_renderer("cpu")

    # 2. three typed settings, read back by the tool and by raw MAXScript
    out = json.loads(V.vray_set_settings({
        "progressive_noise_threshold": 0.02, "GI_on": False, "progressive_maxSamples": 50}))
    check("tool readback noise", out["set"]["progressive_noise_threshold"], 0.02)
    check("raw noise", ms("renderers.current.progressive_noise_threshold as string"), "0.02")
    check("raw GI_on", ms("renderers.current.GI_on as string"), "false")
    check("raw maxSamples", ms("renderers.current.progressive_maxSamples as string"), "50")
    got = json.loads(V.vray_get_settings(names=["progressive_noise_threshold", "gi_on", "progressive_maxSamples"]))
    check("get_settings typed", {k: v["value"] for k, v in got["settings"].items()},
          {"progressive_noise_threshold": 0.02, "GI_on": False, "progressive_maxSamples": 50})
    expect_error("unknown setting lists close match", V.vray_set_settings,
                 {"progressive_noise_treshold": 0.1}, contains="progressive_noise_threshold")
    expect_error("int setting rejects 2.5", V.vray_set_settings, {"progressive_maxSamples": 2.5},
                 contains="expected an integer")
    check("rejected write left value", ms("renderers.current.progressive_maxSamples as string"), "50")

    # 3. render elements: LightSelect with one light + Cryptomatte
    light_cls = "VRayLight" if ms("(VRayLight != undefined) as string") == "true" else "Omnilight"
    ms(f'{light_cls} name:"KeyLight" pos:[0,0,100]; Box name:"catcher" width:100 length:100 height:1; "ok"')
    ls = json.loads(V.vray_add_render_element("VRayLightSelect", "LS_key", lights=["KeyLight"], mode="full"))["added"]
    check("LS lights", ls["lights"], ["KeyLight"])
    check("LS mode", (ls["mode"], ls["mode_label"]), (4, "full"))
    cm = json.loads(V.vray_add_render_element("VRayCryptomatte", "CM_mtl", id_type="node_material_name"))["added"]
    check("CM id_type", (cm["id_type"], cm["id_type_label"]), (2, "node_material_name"))
    raw = ms('(local m = maxOps.GetCurRenderElementMgr(); local s = ""; '
             'for i = 0 to m.NumRenderElements()-1 do (local r = m.GetRenderElement i; '
             's += r.elementName + ":" + ((classOf r) as string) + ";"); s)')
    check("raw element list", raw, "LS_key:VRayLightSelect;CM_mtl:VRayCryptomatte;")
    check("raw LS lights", ms('((maxOps.GetCurRenderElementMgr()).GetRenderElement 0).lights[1].name'), "KeyLight")
    check("raw CM id_type", ms('((maxOps.GetCurRenderElementMgr()).GetRenderElement 1).id_type as string'), "2")
    listed = json.loads(V.vray_list_render_elements())
    check("list names", [e["name"] for e in listed["elements"]], ["LS_key", "CM_mtl"])
    expect_error("duplicate element name", V.vray_add_render_element, "VRayAlpha", "LS_key", contains="already exists")
    expect_error("non-light rejected", V.vray_add_render_element, "VRayLightSelect", "LS_bad",
                 lights=["catcher"], contains="not a light")
    V.vray_add_render_element("VRayAlpha", "tmp_alpha")
    check("remove", json.loads(V.vray_remove_render_element("tmp_alpha"))["remaining"], ["LS_key", "CM_mtl"])

    # 4. object properties: matte / shadow catcher / castShadows on a box
    obj = json.loads(V.vray_set_object_properties(
        ["catcher"], matte=True, alpha_contribution=-1.0, shadow_catcher=True, affect_alpha=True,
        cast_shadows=False))["objects"][0]
    props = obj["properties"]
    check("matte", props["matte"], True)
    check("alpha_contribution", props["alpha_contribution"], -1.0)
    check("shadow_catcher", props["shadow_catcher"], True)
    check("affect_alpha", props["affect_alpha"], True)
    check("cast_shadows", props["cast_shadows"], False)
    check("receive_shadows forced on", props["receive_shadows"], True)
    check("raw castShadows", ms("$catcher.castShadows as string"), "false")
    check("raw receiveShadows", ms("$catcher.receiveShadows as string"), "true")
    buffer = V.parse_user_prop_buffer(ms("getUserPropBuffer $catcher"))
    check("raw VRay_Matte_Enable", buffer.get("VRay_Matte_Enable"), "True")
    check("raw VRay_Matte_Shadows", buffer.get("VRay_Matte_Shadows"), "True")
    check("raw VRay_Matte_ShadowAlpha", buffer.get("VRay_Matte_ShadowAlpha"), "True")
    sep = ms('((dotNetClass "System.Globalization.CultureInfo").CurrentCulture.NumberFormat.NumberDecimalSeparator) as string')
    want_alpha = "-1,000000" if sep == "," else "-1.000000"
    check("raw VRay_Matte_Alpha in V-Ray's own format", buffer.get("VRay_Matte_Alpha"), want_alpha)
    V.vray_set_object_properties(["catcher"], alpha_contribution=-0.5)
    check("fractional alpha read back", json.loads(V.vray_get_object_properties(["catcher"]))["objects"][0]
          ["properties"]["alpha_contribution"], -0.5)
    expect_error("missing object", V.vray_get_object_properties, ["no_such_node"], contains="not found")
finally:
    print("\n%d failure(s)" % len(fails) + (": " + ", ".join(fails) if fails else ""))
    if "--quit" in sys.argv:
        if ms("maxFileName") == "":
            ms("resetMaxFile #noPrompt")
            try:
                client.send_command("quitMax #noPrompt", timeout=10)
            except Exception as exc:  # noqa: BLE001 - Max may drop the pipe while exiting
                print(f"quitMax: {type(exc).__name__} (expected while Max exits)")
        else:
            print("NOT quitting: a scene file is open")

sys.exit(1 if fails else 0)
