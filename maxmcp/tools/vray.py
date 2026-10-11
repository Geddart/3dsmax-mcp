"""V-Ray renderer settings, render elements and object properties.

Everything is introspected at runtime: renderer classes are found by pattern in
``RendererClass.classes`` (their names carry the build, e.g.
``V_Ray_7__update_4_hotfix_2_DR2`` / ``V_Ray_GPU_7__update_4_hotfix_2_DR2``),
property types come from ``classOf`` of the live value, and every write is read
back and compared.

Verified against V-Ray 7.40.04 (3ds Max 2025) on a de-DE Windows region:

* Object properties are node user properties. Key names are V-Ray's own
  (``include/objectprops.h``). V-Ray's Object Properties dialog writes
  ``VRay_Matte_Enable = True`` and floats as ``%f`` in the C runtime locale
  (``VRay_Matte_Alpha = -1,000000`` on de-DE), and it parses them the same way:
  a '.'-written ``-0.5`` displays as 0,0 there. This module therefore writes
  ``True`` / ``False`` and ``%f`` floats with the session's decimal separator
  (.NET CurrentCulture, which matched the CRT output here), and parses either
  separator on read.
* The VRayLightSelect ``mode`` and VRayCryptomatte ``id_type`` integer values
  match the order of their Render Setup dropdowns (read live; ``id_type=2``
  displays "Node material name").
"""
from __future__ import annotations

import difflib
import json
import math
import os
import re
from typing import Any, Optional

from ..coerce import DictValue, StrList
from ..helpers.maxscript import safe_string
from ..path_policy import resolve_write_path
from ..server import client, mcp

_MS_ERROR_SENTINEL = "__MCP_MS_ERR__:"
_PROP_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")

# Dropdown order read from the live Render Setup UI of V-Ray 7.40.04. Index == value.
LIGHT_SELECT_MODES = (
    "direct_illumination",
    "direct_raw",
    "direct_diffuse",
    "direct_specular",
    "full",
    "indirect",
    "indirect_diffuse",
    "indirect_specular",
    "subsurface",
    "light_path_expression",
)
CRYPTOMATTE_ID_TYPES = (
    "node_name",
    "node_name_with_hierarchy",
    "node_material_name",
    "node_user_property",
    "layer_name",
)
# lights_exclude_type: the rollout heading reads "Include lights:" at 1 and
# "Exclude lights:" at 0 (V-Ray 7.40.04 Render Setup).
LIGHT_SELECT_LIST_TYPES = ("exclude", "include")
_ENUM_ALIASES = {
    "lpe": "light_path_expression",
    "material_name": "node_material_name",
    "material": "node_material_name",
    "node_path": "node_name_with_hierarchy",
    "hierarchy": "node_name_with_hierarchy",
    "user_property": "node_user_property",
    "layer": "layer_name",
}
_ENUM_VERIFIED_MAJOR = "7"

# friendly name -> (storage, key, type, V-Ray default when the key is absent)
# storage "user" = node user property (key from V-Ray's objectprops.h),
# storage "node" = 3ds Max node property.
OBJECT_PROPERTIES: dict[str, tuple[str, str, str, Any]] = {
    "matte": ("user", "VRay_Matte_Enable", "bool", False),
    "matte_for_reflections": ("user", "VRay_Secondary_Matte_Enable", "bool", False),
    "alpha_contribution": ("user", "VRay_Matte_Alpha", "float", 1.0),
    "shadow_catcher": ("user", "VRay_Matte_Shadows", "bool", False),
    "affect_alpha": ("user", "VRay_Matte_ShadowAlpha", "bool", False),
    "shadow_brightness": ("user", "VRay_Matte_ShadowBrightness", "float", 1.0),
    "reflection_amount": ("user", "VRay_Matte_ReflectionAmount", "float", 1.0),
    "refraction_amount": ("user", "VRay_Matte_RefractionAmount", "float", 1.0),
    "gi_amount": ("user", "VRay_Matte_GIAmount", "float", 1.0),
    "generate_gi": ("user", "VRay_GI_Generate", "bool", True),
    "receive_gi": ("user", "VRay_GI_Receive", "bool", True),
    "gi_visibility": ("user", "VRay_GI_VisibleToGI", "bool", True),
    "visible_in_reflections": ("user", "VRay_GI_VisibleToReflections", "bool", True),
    "visible_in_refractions": ("user", "VRay_GI_VisibleToRefractions", "bool", True),
    "camera_visibility": ("node", "primaryVisibility", "bool", True),
    "cast_shadows": ("node", "castShadows", "bool", True),
    "receive_shadows": ("node", "receiveShadows", "bool", True),
}
_NODE_FLAGS = tuple(spec[1] for spec in OBJECT_PROPERTIES.values() if spec[0] == "node")

# MAXScript value -> JSON. Floats print with '.' regardless of the Windows region.
_MS_HELPERS = r'''
fn mcpVJs v = (
    if v == undefined then "null" else (
        local c = classOf v
        if c == BooleanClass then (if v then "true" else "false")
        else if c == Integer or c == Integer64 or c == IntegerPtr then (v as string)
        else if c == Float or c == Double then (if v != v or (abs v) > 3.0e38 then "null" else (v as string))
        else if c == Color then ("[" + (v.r as string) + "," + (v.g as string) + "," + (v.b as string) + "]")
        else if c == Point3 then ("[" + (v.x as string) + "," + (v.y as string) + "," + (v.z as string) + "]")
        else if c == Point2 then ("[" + (v.x as string) + "," + (v.y as string) + "]")
        else if c == String then ("\"" + (MCP_Server.escapeJsonString v) + "\"")
        else if c == Name then ("\"" + (MCP_Server.escapeJsonString (v as string)) + "\"")
        else if isValidNode v then ("{\"node\":\"" + (MCP_Server.escapeJsonString v.name) + "\"}")
        else ("{\"class\":\"" + (MCP_Server.escapeJsonString (c as string)) + "\",\"repr\":\"" + (MCP_Server.escapeJsonString (v as string)) + "\"}")
    )
)
fn mcpVJ v = (
    local c = classOf v
    if c == Array or c == ArrayParameter then (
        local s = "["
        for i = 1 to v.count do (if i > 1 do s += ","; s += mcpVJs v[i])
        s + "]"
    ) else mcpVJs v
)
fn mcpVT v = (if v == undefined then "UndefinedClass" else ((classOf v) as string))
fn mcpVProps obj = (
    local s = "["
    local pn = getPropNames obj
    for i = 1 to pn.count do (
        local p = pn[i]
        local v = undefined
        local ok = true
        try (v = getProperty obj p) catch (ok = false)
        if i > 1 do s += ","
        s += "{\"name\":\"" + (MCP_Server.escapeJsonString (p as string)) + "\",\"type\":\"" + (if ok then (mcpVT v) else "error") + "\",\"value\":" + (if ok then (mcpVJ v) else "null") + "}"
    )
    s + "]"
)
fn mcpVErr = ("{\"error\":\"" + (MCP_Server.escapeJsonString (getCurrentException())) + "\"}")
fn mcpVVer = (try ((vrayVersion())[1] as string) catch (""))
'''


def _wrap(body: str) -> str:
    """Wrap a MAXScript body (which must evaluate to a JSON string) with helpers + try/catch."""
    return "(\n" + _MS_HELPERS + "\ntry (\n" + body + "\n) catch (mcpVErr())\n)"


def _run(body: str) -> Any:
    response = client.send_command(_wrap(body), timeout=120.0)
    result = response.get("result", "")
    if not isinstance(result, str):
        raise RuntimeError(f"Unexpected MAXScript result: {result!r}")
    if result.startswith(_MS_ERROR_SENTINEL):
        raise RuntimeError("MAXScript error: " + result[len(_MS_ERROR_SENTINEL):].strip())
    try:
        data = json.loads(result)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Malformed JSON from 3ds Max: {result[:400]!r}") from exc
    if isinstance(data, dict) and data.get("error"):
        raise RuntimeError(f"3ds Max: {data['error']}")
    return data


def _ms_str(text: str) -> str:
    if any(ord(ch) < 32 for ch in text):
        raise ValueError(f"Control characters are not allowed in string values: {text!r}")
    return '"' + safe_string(text) + '"'


def _ms_float(value: Any) -> str:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"expected a number, got {value!r}")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"non-finite number {value!r}")
    text = repr(number)
    if "e" in text or "E" in text:
        text = format(number, ".12f").rstrip("0")
        if text.endswith("."):
            text += "0"
    return text


def _close(name: str, candidates: list[str]) -> list[str]:
    lowered = {c.lower(): c for c in candidates}
    hits = difflib.get_close_matches(name.lower(), list(lowered), n=6, cutoff=0.5)
    sub = [c for c in candidates if name.lower() in c.lower() and c.lower() not in hits]
    return [lowered[h] for h in hits] + sub[: max(0, 6 - len(hits))]


def _coerce_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str) and value.strip().lower() in {"true", "false", "on", "off"}:
        return value.strip().lower() in {"true", "on"}
    if isinstance(value, int) and value in (0, 1):
        return bool(value)
    raise TypeError(f"expected a boolean, got {value!r}")


def _coerce_int(value: Any) -> int:
    if isinstance(value, bool):
        raise TypeError(f"expected an integer, got boolean {value!r}")
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, str) and re.fullmatch(r"\s*-?\d+\s*", value):
        return int(value)
    raise TypeError(f"expected an integer, got {value!r}")


def _coerce_float(value: Any) -> float:
    if isinstance(value, str):
        try:
            value = float(value.strip().replace(",", "."))
        except ValueError as exc:
            raise TypeError(f"expected a number, got {value!r}") from exc
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"expected a number, got {value!r}")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"non-finite number {value!r}")
    return number


def _vector(value: Any, sizes: tuple[int, ...], what: str) -> list[float]:
    if not isinstance(value, (list, tuple)) or len(value) not in sizes:
        raise TypeError(f"expected {what} as a list of {' or '.join(map(str, sizes))} numbers, got {value!r}")
    return [_coerce_float(v) for v in value]


def format_value(type_name: str, value: Any) -> tuple[str, Any]:
    """Return (MAXScript literal, normalised expected value) for a live property type.

    The type is the ``classOf`` of the property's current value, never the input.
    Colors use MAXScript's 0-255 convention: ``[r, g, b]`` -> ``(color r g b)``.
    """
    if value is None:
        return "undefined", None
    t = type_name
    if t == "BooleanClass":
        b = _coerce_bool(value)
        return ("true" if b else "false"), b
    if t in {"Integer", "Integer64", "IntegerPtr"}:
        i = _coerce_int(value)
        return str(i), i
    if t in {"Float", "Double"}:
        f = _coerce_float(value)
        return _ms_float(f), f
    if t == "Color":
        v = _vector(value, (3, 4), "a color (0-255)")
        return "(color " + " ".join(_ms_float(c) for c in v) + ")", v[:3]
    if t == "Point3":
        v = _vector(value, (3,), "a point3")
        return "[" + ",".join(_ms_float(c) for c in v) + "]", v
    if t == "Point2":
        v = _vector(value, (2,), "a point2")
        return "[" + ",".join(_ms_float(c) for c in v) + "]", v
    if t in {"String", "Name"}:
        if not isinstance(value, str):
            raise TypeError(f"expected a string, got {value!r}")
        return _ms_str(value), value
    if t == "UndefinedClass":
        if isinstance(value, bool):
            return format_value("BooleanClass", value)
        if isinstance(value, int):
            return format_value("Integer", value)
        if isinstance(value, float):
            return format_value("Float", value)
        if isinstance(value, str):
            return format_value("String", value)
        raise TypeError(f"property is currently undefined; pass a bool, number or string, got {value!r}")
    raise TypeError(f"unsupported property type {t}; set it with execute_maxscript")


def format_array(current: Any, value: Any) -> tuple[str, list]:
    """Format a list for an ArrayParameter/Array property of scalars."""
    if not isinstance(value, (list, tuple)):
        raise TypeError(f"expected a list, got {value!r}")
    sample = current[0] if isinstance(current, list) and current else None
    items: list[str] = []
    expected: list = []
    for item in value:
        if isinstance(sample, bool) or (sample is None and isinstance(item, bool)):
            lit, exp = format_value("BooleanClass", item)
        elif isinstance(sample, int) or (sample is None and isinstance(item, int)):
            lit, exp = format_value("Integer", item)
        elif isinstance(sample, float) or (sample is None and isinstance(item, float)):
            lit, exp = format_value("Float", item)
        elif isinstance(sample, str) or (sample is None and isinstance(item, str)):
            lit, exp = format_value("String", item)
        else:
            raise TypeError(f"only arrays of booleans, numbers or strings are supported, got {item!r}")
        items.append(lit)
        expected.append(exp)
    return "#(" + ",".join(items) + ")", expected


def values_match(expected: Any, got: Any) -> bool:
    if expected is None:
        return got is None
    if isinstance(expected, bool):
        return isinstance(got, bool) and got == expected
    if isinstance(expected, int):
        return isinstance(got, int) and not isinstance(got, bool) and got == expected
    if isinstance(expected, float):
        return isinstance(got, (int, float)) and not isinstance(got, bool) and math.isclose(
            float(got), expected, rel_tol=1e-5, abs_tol=1e-6)
    if isinstance(expected, str):
        return got == expected
    if isinstance(expected, list):
        return isinstance(got, list) and len(got) == len(expected) and all(
            values_match(e, g) for e, g in zip(expected, got))
    return expected == got


def is_write_path_property(name: str) -> bool:
    """Renderer string properties that name a file V-Ray will write at render time."""
    low = name.lower()
    if "load" in low:
        return False
    return "filename" in low or low.endswith("_file") or low.endswith("_path") or "savefile" in low


def _check_write_path(prop: str, value: str, scene_dir: str) -> None:
    if not value.strip():
        return
    expanded = os.path.expandvars(os.path.expanduser(value))
    if not os.path.isabs(expanded):
        raise ValueError(f"{prop}: output paths must be absolute, got {value!r}")
    resolve_write_path(expanded, scene_dir=scene_dir or None)


def normalize_enum(value: Any, labels: tuple[str, ...], what: str, vray_version: str) -> int:
    """Accept an int or a dropdown label (verified for V-Ray 7) and return the int value."""
    if isinstance(value, bool):
        raise TypeError(f"{what}: expected an integer or a label, got {value!r}")
    if isinstance(value, int) or (isinstance(value, str) and re.fullmatch(r"\s*\d+\s*", value)):
        index = int(value)
        if not 0 <= index < len(labels):
            raise ValueError(f"{what}: {index} is outside 0..{len(labels) - 1} ({', '.join(labels)})")
        return index
    if not isinstance(value, str):
        raise TypeError(f"{what}: expected an integer or a label, got {value!r}")
    if not vray_version.split(".")[0] == _ENUM_VERIFIED_MAJOR:
        raise ValueError(
            f"{what}: labels were verified for V-Ray {_ENUM_VERIFIED_MAJOR}.x only; this is V-Ray "
            f"{vray_version or 'unknown'} - pass the integer value instead")
    key = re.sub(r"[^a-z0-9]+", "_", value.strip().lower()).strip("_")
    key = _ENUM_ALIASES.get(key, key)
    if key in labels:
        return labels.index(key)
    raise ValueError(f"{what}: unknown label {value!r}; use one of {', '.join(labels)} or 0..{len(labels) - 1}")


def enum_label(index: Any, labels: tuple[str, ...], vray_version: str) -> Optional[str]:
    if vray_version.split(".")[0] != _ENUM_VERIFIED_MAJOR:
        return None
    if isinstance(index, int) and not isinstance(index, bool) and 0 <= index < len(labels):
        return labels[index]
    return None


# --------------------------------------------------------------------------- renderer

def _renderer_dump() -> dict:
    body = r'''
local r = renderers.current
local rc = (classOf r) as string
local isV = matchPattern rc pattern:"V_Ray*"
local s = "{\"renderer\":\"" + (MCP_Server.escapeJsonString rc) + "\",\"is_vray\":" + (if isV then "true" else "false")
s += ",\"vray_version\":\"" + (MCP_Server.escapeJsonString (mcpVVer())) + "\",\"scene_dir\":\"" + (MCP_Server.escapeJsonString maxFilePath) + "\""
s += ",\"props\":" + (if isV then (mcpVProps r) else "[]") + "}"
s
'''
    return _run(body)


def _require_vray(dump: dict) -> None:
    if not dump.get("is_vray"):
        raise RuntimeError(
            f"renderers.current is {dump.get('renderer')!r}, not V-Ray; call vray_set_renderer first")


@mcp.tool()
def vray_set_renderer(mode: str = "cpu") -> str:
    """Make the installed V-Ray CPU or GPU renderer the production renderer.

    mode: "cpu" | "gpu". The class is discovered at runtime (names carry the
    build, e.g. V_Ray_7__update_4_hotfix_2_DR2). Switching away stashes the
    outgoing V-Ray instance for this scene session and switching back restores
    it, so GPU settings survive a CPU->GPU->CPU round trip (a fresh GPU instance
    would reset them). The stash clears on reset/new/open. No-op when already set.
    Returns renderer_class, previous_class, changed, restored_settings.
    """
    want_gpu = {"cpu": "false", "gpu": "true"}.get(str(mode).strip().lower())
    if want_gpu is None:
        raise ValueError(f"mode must be 'cpu' or 'gpu', got {mode!r}")
    body = r'''
if (mcpVVer()) == "" do throw "V-Ray is not loaded in this 3ds Max"
local wantGpu = %WANTGPU%
local cands = #()
local all = #()
for c in RendererClass.classes do (
    local n = c as string
    if matchPattern n pattern:"V_Ray*" do (
        append all n
        if (matchPattern n pattern:"*GPU*") == wantGpu do append cands c
    )
)
if cands.count == 0 do throw ("No V-Ray " + (if wantGpu then "GPU" else "CPU") + " renderer class among: " + (all as string))
if cands.count > 1 do throw ("Ambiguous V-Ray renderer classes: " + (cands as string))
local want = cands[1]
global mcp_vray_renderer_stash
if mcp_vray_renderer_stash == undefined do mcp_vray_renderer_stash = #()
callbacks.removeScripts id:#mcpVRayStash
callbacks.addScript #systemPostReset "global mcp_vray_renderer_stash = undefined" id:#mcpVRayStash
callbacks.addScript #systemPostNew "global mcp_vray_renderer_stash = undefined" id:#mcpVRayStash
callbacks.addScript #filePostOpen "global mcp_vray_renderer_stash = undefined" id:#mcpVRayStash
local prev = renderers.current
local prevCls = classOf prev
local changed = prevCls != want
local restored = false
if changed do (
    if matchPattern (prevCls as string) pattern:"V_Ray*" do (
        mcp_vray_renderer_stash = for r in mcp_vray_renderer_stash where (classOf r) != prevCls collect r
        append mcp_vray_renderer_stash prev
    )
    local held = for r in mcp_vray_renderer_stash where (classOf r) == want collect r
    if held.count > 0 then (renderers.current = held[1]; restored = true) else renderers.current = want()
)
local now = classOf renderers.current
if now != want do throw ("renderers.current is " + (now as string) + " after the switch, expected " + (want as string))
local extra = ""
if wantGpu do extra = ",\"engine_type\":" + (mcpVJ (try (renderers.current.engine_type) catch (undefined)))
"{\"renderer_class\":\"" + (MCP_Server.escapeJsonString (now as string)) + "\",\"previous_class\":\"" + (MCP_Server.escapeJsonString (prevCls as string)) + "\",\"changed\":" + (if changed then "true" else "false") + ",\"restored_settings\":" + (if restored then "true" else "false") + ",\"vray_version\":\"" + (MCP_Server.escapeJsonString (mcpVVer())) + "\"" + extra + "}"
'''.replace("%WANTGPU%", want_gpu)
    data = _run(body)
    data["mode"] = str(mode).strip().lower()
    return json.dumps(data)


@mcp.tool()
def vray_get_settings(filter: str = "", names: Optional[StrList] = None, limit: int = 500) -> str:
    """Read typed properties of the current V-Ray renderer (CPU or GPU).

    filter: case-insensitive substring or glob (* ?) on property names, e.g.
    "progressive_*" or "gi_". names: exact property names (case-insensitive).
    Values are typed: bool/int/float/string, colors [r,g,b] in 0-255,
    point3 [x,y,z], arrays as lists. Unknown names raise with close matches.
    """
    dump = _renderer_dump()
    _require_vray(dump)
    props = dump.get("props", [])
    by_lower = {p["name"].lower(): p for p in props}
    selected: list[dict] = []
    if names:
        missing = [n for n in names if n.lower() not in by_lower]
        if missing:
            raise ValueError("; ".join(
                f"unknown V-Ray property {m!r} (close: {', '.join(_close(m, [p['name'] for p in props])) or 'none'})"
                for m in missing))
        selected = [by_lower[n.lower()] for n in names]
    else:
        pattern = filter.strip().lower()
        if pattern and any(ch in pattern for ch in "*?"):
            import fnmatch
            selected = [p for p in props if fnmatch.fnmatch(p["name"].lower(), pattern)]
        else:
            selected = [p for p in props if pattern in p["name"].lower()]
    total = len(selected)
    limit = max(1, min(int(limit), 1000))
    settings = {p["name"]: {"type": p["type"], "value": p["value"]} for p in selected[:limit]}
    return json.dumps({
        "renderer_class": dump["renderer"],
        "vray_version": dump.get("vray_version", ""),
        "count": total,
        "truncated": total > limit,
        "settings": settings,
    })


@mcp.tool()
def vray_set_settings(props: DictValue) -> str:
    """Write properties on the current V-Ray renderer, then read each one back.

    props: {"property_name": value}. The literal is formatted from the type of
    the property's CURRENT value (classOf), not from the JSON type: booleans,
    integers (non-integral floats rejected), floats, colors [r,g,b] (0-255),
    point3 [x,y,z], strings, and arrays of scalars. Unknown names fail before any
    write, listing close matches. Every value is read back; a mismatch raises.
    Output-path string props (*FileName, *_file, *_path) must be inside the
    allowed folders (path policy). Mirror pairs are independent: setting
    imageSampler_type does not change imageSampler_type_new (the UI one).
    """
    if not isinstance(props, dict) or not props:
        raise ValueError("props must be a non-empty object of property -> value")
    dump = _renderer_dump()
    _require_vray(dump)
    live = {p["name"].lower(): p for p in dump.get("props", [])}
    all_names = [p["name"] for p in dump.get("props", [])]
    problems: list[str] = []
    plan: list[tuple[str, str, Any]] = []
    for raw_name, value in props.items():
        name = str(raw_name)
        entry = live.get(name.lower())
        if entry is None or not _PROP_NAME_RE.match(entry["name"]):
            problems.append(f"unknown V-Ray property {name!r} (close: {', '.join(_close(name, all_names)) or 'none'})")
            continue
        canonical = entry["name"]
        try:
            if entry["type"] in {"ArrayParameter", "Array"}:
                literal, expected = format_array(entry["value"], value)
            else:
                literal, expected = format_value(entry["type"], value)
            if isinstance(expected, str) and is_write_path_property(canonical):
                _check_write_path(canonical, expected, dump.get("scene_dir", ""))
        except (TypeError, ValueError) as exc:
            problems.append(f"{canonical} ({entry['type']}): {exc}")
            continue
        plan.append((canonical, literal, expected))
    if problems:
        raise ValueError("No settings were written. " + "; ".join(problems))

    lines = ["local r = renderers.current",
             'if not (matchPattern ((classOf r) as string) pattern:"V_Ray*") do throw "renderers.current is not V-Ray"',
             'local errs = ""',
             'undo "MCP vray_set_settings" on (']
    for name, literal, _ in plan:
        lines.append(
            f'    try (setProperty r #{name} ({literal})) catch '
            f'(errs += (if errs == "" then "" else ",") + "\\"{name}\\":\\"" + (MCP_Server.escapeJsonString (getCurrentException())) + "\\"")')
    lines.append(")")
    lines.append('local s = "{\\"readback\\":{"')
    for i, (name, _, _) in enumerate(plan):
        sep = "," if i else ""
        lines.append(f's += "{sep}\\"{name}\\":" + (try (mcpVJ (getProperty r #{name})) catch ("null"))')
    lines.append('s += "},\\"errors\\":{" + errs + "},\\"renderer_class\\":\\"" + (MCP_Server.escapeJsonString ((classOf r) as string)) + "\\"}"')
    lines.append("s")
    data = _run("\n".join(lines))
    readback = data.get("readback", {})
    errors = data.get("errors", {})
    applied = {}
    mismatches = []
    for name, _, expected in plan:
        got = readback.get(name)
        applied[name] = got
        if name in errors:
            mismatches.append(f"{name}: write failed: {errors[name]}")
        elif not values_match(expected, got):
            mismatches.append(f"{name}: wrote {expected!r}, read back {got!r}")
    if mismatches:
        raise RuntimeError("V-Ray settings read-back mismatch: " + "; ".join(mismatches)
                           + f". Stored now: {json.dumps(applied)}")
    return json.dumps({"renderer_class": data.get("renderer_class"), "set": applied})


# --------------------------------------------------------------------------- render elements

def _element_list() -> dict:
    body = r'''
local mgr = maxOps.GetCurRenderElementMgr()
local s = "{\"vray_version\":\"" + (MCP_Server.escapeJsonString (mcpVVer())) + "\",\"active\":" + (if mgr.GetElementsActive() then "true" else "false") + ",\"elements\":["
local n = mgr.NumRenderElements()
for i = 0 to n - 1 do (
    local re = mgr.GetRenderElement i
    if i > 0 do s += ","
    s += "{\"index\":" + (i as string) + ",\"class\":\"" + (MCP_Server.escapeJsonString ((classOf re) as string)) + "\",\"name\":" + (mcpVJ (try (re.elementName) catch (undefined))) + ",\"props\":" + (mcpVProps re) + "}"
)
s + "]}"
'''
    return _run(body)


def _summarize_element(element: dict, vray_version: str, include_properties: bool) -> dict:
    props = {p["name"]: p["value"] for p in element.get("props", [])}
    lower = {k.lower(): v for k, v in props.items()}
    out: dict[str, Any] = {
        "index": element["index"],
        "name": element.get("name"),
        "class": element["class"],
        "enabled": lower.get("enabled"),
        "filter_on": lower.get("filteron"),
    }
    if "mode" in lower and element["class"] == "VRayLightSelect":
        out["mode"] = lower["mode"]
        out["mode_label"] = enum_label(lower["mode"], LIGHT_SELECT_MODES, vray_version)
    if "lights" in lower:
        out["lights"] = [v.get("node") if isinstance(v, dict) else v for v in (lower["lights"] or [])]
    if "lights_exclude_type" in lower:
        out["lights_list_type"] = enum_label(lower["lights_exclude_type"], LIGHT_SELECT_LIST_TYPES, vray_version)
    if "id_type" in lower and element["class"] == "VRayCryptomatte":
        out["id_type"] = lower["id_type"]
        out["id_type_label"] = enum_label(lower["id_type"], CRYPTOMATTE_ID_TYPES, vray_version)
    if include_properties:
        out["properties"] = {p["name"]: {"type": p["type"], "value": p["value"]} for p in element.get("props", [])}
    return out


@mcp.tool()
def vray_list_render_elements(include_properties: bool = False) -> str:
    """List render elements of the current render element manager.

    Each entry: index, name, class, enabled (the element's .enabled param),
    filter_on; VRayLightSelect adds mode/mode_label, lights, lights_list_type;
    VRayCryptomatte adds id_type/id_type_label. include_properties adds every
    property typed. Note: on V-Ray 7.40 the Render Setup list column "Enabled"
    shows Off for scripted elements regardless of .enabled.
    """
    data = _element_list()
    version = data.get("vray_version", "")
    elements = [_summarize_element(e, version, include_properties) for e in data.get("elements", [])]
    return json.dumps({"elements_active": data.get("active"), "count": len(elements), "elements": elements})


@mcp.tool()
def vray_add_render_element(
    type: str,
    name: str,
    props: Optional[DictValue] = None,
    lights: Optional[StrList] = None,
    lights_list_type: str = "",
    mode: Optional[int | str] = None,
    id_type: Optional[int | str] = None,
) -> str:
    """Add a V-Ray render element and read it back.

    type: a V-Ray render element class present at runtime (VRayLightSelect,
    VRayCryptomatte, VRayAlpha, ...); name: unique element name.
    props: other element properties, typed from the live default values (as
    vray_set_settings). VRayLightSelect: lights = scene light names (each must
    resolve to exactly one light), lights_list_type = "include" | "exclude",
    mode = int or label (direct_illumination, direct_raw, direct_diffuse,
    direct_specular, full, indirect, indirect_diffuse, indirect_specular,
    subsurface, light_path_expression). VRayCryptomatte: id_type = int or label
    (node_name, node_name_with_hierarchy, node_material_name,
    node_user_property, layer_name). Nothing is added if any value is invalid.
    """
    if not name or any(ord(ch) < 32 for ch in name):
        raise ValueError("name must be a non-empty single-line string")
    if not _PROP_NAME_RE.match(type or ""):
        raise ValueError(f"type must be a class name, got {type!r}")
    light_names = list(lights or [])
    lights_literal = "#(" + ",".join(_ms_str(n) for n in light_names) + ")"
    body = r'''
local want = %TYPE%
local cls = undefined
local vre = #()
for c in RenderElement.classes do (
    local n = c as string
    if matchPattern n pattern:"VRay*" do append vre n
    if (stricmp n want) == 0 do cls = c
)
local mgr = maxOps.GetCurRenderElementMgr()
local existing = for i = 0 to mgr.NumRenderElements() - 1 collect (mgr.GetRenderElement i).elementName
local s = "{\"vray_version\":\"" + (MCP_Server.escapeJsonString (mcpVVer())) + "\",\"renderer\":\"" + (MCP_Server.escapeJsonString ((classOf renderers.current) as string)) + "\""
s += ",\"vray_classes\":" + (mcpVJ vre) + ",\"existing\":" + (mcpVJ existing)
s += ",\"class\":" + (if cls == undefined then "null" else ("\"" + (MCP_Server.escapeJsonString (cls as string)) + "\""))
s += ",\"props\":" + (if cls == undefined then "[]" else (mcpVProps (cls())))
s += ",\"lights\":["
local req = %LIGHTS%
for i = 1 to req.count do (
    local hits = getNodeByName req[i] all:true
    local isL = hits.count == 1 and (superClassOf hits[1]) == Light
    if i > 1 do s += ","
    s += "{\"name\":\"" + (MCP_Server.escapeJsonString req[i]) + "\",\"count\":" + (hits.count as string) + ",\"is_light\":" + (if isL then "true" else "false") + "}"
)
s + "]}"
'''.replace("%TYPE%", _ms_str(type)).replace("%LIGHTS%", lights_literal)
    info = _run(body)
    version = info.get("vray_version", "")
    if not version:
        raise RuntimeError("V-Ray is not loaded in this 3ds Max")
    cls = info.get("class")
    if not cls or not cls.startswith("VRay"):
        raise ValueError(f"unknown V-Ray render element type {type!r} (close: "
                         f"{', '.join(_close(type, info.get('vray_classes', []))) or 'none'})")
    if name in (info.get("existing") or []):
        raise ValueError(f"a render element named {name!r} already exists")
    live = {p["name"].lower(): p for p in info.get("props", [])}
    all_names = [p["name"] for p in info.get("props", [])]
    problems: list[str] = []
    plan: list[tuple[str, str, Any]] = []
    requested: dict[str, Any] = dict(props or {})
    if mode is not None:
        if cls != "VRayLightSelect":
            problems.append("mode applies to VRayLightSelect only")
        else:
            try:
                requested["mode"] = normalize_enum(mode, LIGHT_SELECT_MODES, "mode", version)
            except (TypeError, ValueError) as exc:
                problems.append(str(exc))
    if id_type is not None:
        if cls != "VRayCryptomatte":
            problems.append("id_type applies to VRayCryptomatte only")
        else:
            try:
                requested["id_type"] = normalize_enum(id_type, CRYPTOMATTE_ID_TYPES, "id_type", version)
            except (TypeError, ValueError) as exc:
                problems.append(str(exc))
    if lights_list_type:
        if "lights_exclude_type" not in live:
            problems.append(f"{cls} has no lights_exclude_type")
        else:
            try:
                requested["lights_exclude_type"] = normalize_enum(
                    lights_list_type, LIGHT_SELECT_LIST_TYPES, "lights_list_type", version)
            except (TypeError, ValueError) as exc:
                problems.append(str(exc))
    for key in requested:
        if key.lower() in {"lights", "elementname"}:
            problems.append(f"pass {key} through its own parameter, not props")
    if light_names:
        if "lights" not in live:
            problems.append(f"{cls} has no lights list")
        for entry in info.get("lights", []):
            if entry["count"] == 0:
                problems.append(f"light {entry['name']!r} not found")
            elif entry["count"] > 1:
                problems.append(f"light name {entry['name']!r} is ambiguous ({entry['count']} nodes)")
            elif not entry["is_light"]:
                problems.append(f"{entry['name']!r} is not a light")
    for key, value in requested.items():
        if key.lower() in {"lights", "elementname"}:
            continue
        entry = live.get(str(key).lower())
        if entry is None or not _PROP_NAME_RE.match(entry["name"]):
            problems.append(f"unknown {cls} property {key!r} (close: {', '.join(_close(str(key), all_names)) or 'none'})")
            continue
        try:
            if entry["type"] in {"ArrayParameter", "Array"}:
                literal, expected = format_array(entry["value"], value)
            else:
                literal, expected = format_value(entry["type"], value)
        except (TypeError, ValueError) as exc:
            problems.append(f"{entry['name']} ({entry['type']}): {exc}")
            continue
        plan.append((entry["name"], literal, expected))
    if problems:
        raise ValueError("No render element was added. " + "; ".join(problems))

    lines = [
        "local cls = undefined",
        f"for c in RenderElement.classes where (c as string) == {_ms_str(cls)} do cls = c",
        f'if cls == undefined do throw "class {cls} disappeared"',
        f"local re = cls elementName:{_ms_str(name)}",
        'local errs = ""',
    ]
    for prop, literal, _ in plan:
        lines.append(
            f'try (setProperty re #{prop} ({literal})) catch '
            f'(errs += (if errs == "" then "" else "; ") + "{prop}: " + (getCurrentException()))')
    if light_names:
        lines.append(f"re.lights = for h in {lights_literal} collect (getNodeByName h)")
    lines += [
        'if errs != "" do throw ("property writes failed, element not added: " + errs)',
        "local mgr = maxOps.GetCurRenderElementMgr()",
        "local ok = mgr.AddRenderElement re",
        'if ok != true do throw ("AddRenderElement refused " + (cls as string) + " for renderer " + ((classOf renderers.current) as string))',
        'local idx = -1',
        "for i = 0 to mgr.NumRenderElements() - 1 where (mgr.GetRenderElement i) == re do idx = i",
        '"{\\"index\\":" + (idx as string) + ",\\"class\\":\\"" + ((classOf re) as string) + "\\",\\"name\\":" + (mcpVJ re.elementName) + ",\\"props\\":" + (mcpVProps re) + "}"',
    ]
    added = _run("\n".join(lines))
    readback = {p["name"]: p["value"] for p in added.get("props", [])}
    mismatches = []
    if added.get("name") != name:
        mismatches.append(f"elementName: wrote {name!r}, read back {added.get('name')!r}")
    for prop, _, expected in plan:
        if not values_match(expected, readback.get(prop)):
            mismatches.append(f"{prop}: wrote {expected!r}, read back {readback.get(prop)!r}")
    if light_names:
        got = [v.get("node") if isinstance(v, dict) else v for v in (readback.get("lights") or [])]
        if got != light_names:
            mismatches.append(f"lights: wrote {light_names!r}, read back {got!r}")
    summary = _summarize_element(added, version, include_properties=False)
    if mismatches:
        raise RuntimeError("Render element added but read-back differs: " + "; ".join(mismatches)
                           + f". Element now: {json.dumps(summary)}")
    return json.dumps({"added": summary})


@mcp.tool()
def vray_remove_render_element(name: str) -> str:
    """Remove every render element whose name equals `name` exactly (case-sensitive)."""
    listing = _element_list()
    elements = listing.get("elements", [])
    hits = [e for e in elements if e.get("name") == name]
    if not hits:
        names = [e.get("name") or "" for e in elements]
        raise ValueError(f"no render element named {name!r} (close: {', '.join(_close(name, names)) or 'none'}; "
                         f"existing: {', '.join(names) or 'none'})")
    indices = sorted((e["index"] for e in hits), reverse=True)
    body = "\n".join([
        "local mgr = maxOps.GetCurRenderElementMgr()",
        "local removed = 0",
        f"for i in #({','.join(str(i) for i in indices)}) do (",
        "    local re = mgr.GetRenderElement i",
        f"    if re != undefined and re.elementName == {_ms_str(name)} do (if mgr.RemoveRenderElement re do removed += 1)",
        ")",
        "local left = for i = 0 to mgr.NumRenderElements() - 1 collect (mgr.GetRenderElement i).elementName",
        '"{\\"removed\\":" + (removed as string) + ",\\"remaining\\":" + (mcpVJ left) + "}"',
    ])
    data = _run(body)
    remaining = data.get("remaining") or []
    if name in remaining or data.get("removed") != len(hits):
        raise RuntimeError(f"removal incomplete: removed {data.get('removed')} of {len(hits)}; remaining {remaining}")
    return json.dumps({"removed": data["removed"], "remaining": remaining})


# --------------------------------------------------------------------------- object properties

def format_user_prop_float(value: float) -> str:
    """V-Ray's own user-prop float format ("%f"); MAXScript swaps '.' for the session separator.

    V-Ray's Object Properties dialog parses these keys with the C runtime locale,
    so on a decimal-comma region "-0.5" displays as 0,0 while "-0,500000" (what
    the dialog itself writes) round-trips. objectprops.h's getNodeUserPropFloat
    localises either separator before atof.
    """
    number = _coerce_float(value)
    return "%f" % number


def parse_user_prop_buffer(buffer: str) -> dict[str, str]:
    """Parse a node user-property buffer into {key: raw value}; the first occurrence wins."""
    out: dict[str, str] = {}
    seen: set[str] = set()
    for line in buffer.replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        if key and key.lower() not in seen:
            seen.add(key.lower())
            out[key] = value.strip()
    return out


def parse_typed(raw: str, kind: str) -> Any:
    """Typed value of a stored user prop. Accepts V-Ray's locale floats ("-1,000000")."""
    text = raw.strip()
    if kind == "bool":
        low = text.lower()
        if low in {"true", "on", "yes", "1"}:
            return True
        if low in {"false", "off", "no", "0"}:
            return False
        try:
            return float(text.replace(",", ".")) != 0.0
        except ValueError:
            return None
    if kind == "float":
        try:
            return float(text.replace(",", "."))
        except ValueError:
            return None
    return text


def _object_state(names: list[str]) -> list[dict]:
    body = r'''
local req = %NAMES%
local s = "["
for i = 1 to req.count do (
    local hits = getNodeByName req[i] all:true
    if i > 1 do s += ","
    s += "{\"name\":\"" + (MCP_Server.escapeJsonString req[i]) + "\",\"count\":" + (hits.count as string)
    if hits.count == 1 do (
        local n = hits[1]
        s += ",\"buffer\":\"" + (MCP_Server.escapeJsonString (getUserPropBuffer n)) + "\""
        s += ",\"primaryVisibility\":" + (mcpVJ n.primaryVisibility) + ",\"castShadows\":" + (mcpVJ n.castShadows) + ",\"receiveShadows\":" + (mcpVJ n.receiveShadows)
    )
    s += "}"
)
s + "]"
'''.replace("%NAMES%", "#(" + ",".join(_ms_str(n) for n in names) + ")")
    return _run(body)


def _describe_object(state: dict) -> dict:
    stored = parse_user_prop_buffer(state.get("buffer", ""))
    stored_lower = {k.lower(): (k, v) for k, v in stored.items()}
    props: dict[str, Any] = {}
    vray_keys: dict[str, str] = {}
    for friendly, (storage, key, kind, default) in OBJECT_PROPERTIES.items():
        if storage == "node":
            props[friendly] = state.get(key)
            continue
        hit = stored_lower.get(key.lower())
        if hit is None:
            props[friendly] = default
        else:
            vray_keys[hit[0]] = hit[1]
            parsed = parse_typed(hit[1], kind)
            props[friendly] = parsed
    other = {k: v for k, v in stored.items() if k.lower().startswith("vray_") and k not in vray_keys}
    vray_keys.update(other)
    return {"name": state["name"], "properties": props, "stored_vray_keys": vray_keys}


def _validate_nodes(names: list[str], states: list[dict]) -> None:
    problems = []
    for state in states:
        if state.get("count") == 0:
            problems.append(f"object {state['name']!r} not found")
        elif state.get("count", 0) > 1:
            problems.append(f"object name {state['name']!r} is ambiguous ({state['count']} nodes)")
    if problems:
        raise ValueError("; ".join(problems))


@mcp.tool()
def vray_get_object_properties(names: StrList) -> str:
    """Read V-Ray object properties (node user props) and node render flags.

    Returns per object the typed properties (matte, alpha_contribution,
    shadow_catcher, affect_alpha, gi_visibility, camera_visibility, cast_shadows,
    receive_shadows, ...) - V-Ray defaults when a key is not stored - and the raw
    stored VRay_* keys exactly as found in the user-property buffer.
    """
    names = [n for n in (names or []) if n]
    if not names:
        raise ValueError("names must list at least one object")
    states = _object_state(names)
    _validate_nodes(names, states)
    return json.dumps({"objects": [_describe_object(s) for s in states]})


@mcp.tool()
def vray_set_object_properties(
    names: StrList,
    matte: Optional[bool] = None,
    matte_for_reflections: Optional[bool] = None,
    alpha_contribution: Optional[float] = None,
    shadow_catcher: Optional[bool] = None,
    affect_alpha: Optional[bool] = None,
    shadow_brightness: Optional[float] = None,
    reflection_amount: Optional[float] = None,
    refraction_amount: Optional[float] = None,
    gi_amount: Optional[float] = None,
    generate_gi: Optional[bool] = None,
    receive_gi: Optional[bool] = None,
    gi_visibility: Optional[bool] = None,
    visible_in_reflections: Optional[bool] = None,
    visible_in_refractions: Optional[bool] = None,
    camera_visibility: Optional[bool] = None,
    cast_shadows: Optional[bool] = None,
    receive_shadows: Optional[bool] = None,
) -> str:
    """Set V-Ray object properties on objects and read them back from the scene.

    V-Ray keys (node user props, names from V-Ray's objectprops.h): matte ->
    VRay_Matte_Enable, matte_for_reflections -> VRay_Secondary_Matte_Enable,
    alpha_contribution (-1..1) -> VRay_Matte_Alpha, shadow_catcher ->
    VRay_Matte_Shadows ("Shadows" in Matte properties), affect_alpha ->
    VRay_Matte_ShadowAlpha, shadow_brightness / reflection_amount /
    refraction_amount / gi_amount -> VRay_Matte_*, generate_gi / receive_gi ->
    VRay_GI_Generate / VRay_GI_Receive, gi_visibility -> VRay_GI_VisibleToGI,
    visible_in_reflections / visible_in_refractions -> VRay_GI_VisibleTo*.
    Node flags: camera_visibility -> primaryVisibility, cast_shadows ->
    castShadows, receive_shadows -> receiveShadows. shadow_catcher=true also
    sets receiveShadows=true unless receive_shadows is given (receiveShadows off
    suppresses matte shadows). Booleans are stored as True/False and floats in
    V-Ray's own "%f" format with the session decimal separator, so V-Ray's
    Object Properties dialog shows them correctly on decimal-comma regions.
    One undo step; every value is read back and a mismatch raises. Matte
    shadow colour is not supported (V-Ray parses it with a locale-dependent scanf).
    """
    names = [n for n in (names or []) if n]
    if not names:
        raise ValueError("names must list at least one object")
    requested = {
        "matte": matte, "matte_for_reflections": matte_for_reflections,
        "alpha_contribution": alpha_contribution, "shadow_catcher": shadow_catcher,
        "affect_alpha": affect_alpha, "shadow_brightness": shadow_brightness,
        "reflection_amount": reflection_amount, "refraction_amount": refraction_amount,
        "gi_amount": gi_amount, "generate_gi": generate_gi, "receive_gi": receive_gi,
        "gi_visibility": gi_visibility, "visible_in_reflections": visible_in_reflections,
        "visible_in_refractions": visible_in_refractions, "camera_visibility": camera_visibility,
        "cast_shadows": cast_shadows, "receive_shadows": receive_shadows,
    }
    requested = {k: v for k, v in requested.items() if v is not None}
    warnings: list[str] = []
    if requested.get("shadow_catcher") is True and "receive_shadows" not in requested:
        requested["receive_shadows"] = True
        warnings.append("shadow_catcher=true also set receive_shadows=true")
    elif requested.get("shadow_catcher") is True and requested.get("receive_shadows") is False:
        warnings.append("receive_shadows=false suppresses V-Ray matte shadows; shadow_catcher will show nothing")
    if not requested:
        raise ValueError("pass at least one property to set")
    expected: dict[str, Any] = {}
    writes: list[str] = []
    for friendly, value in requested.items():
        storage, key, kind, _ = OBJECT_PROPERTIES[friendly]
        if kind == "bool":
            b = _coerce_bool(value)
            expected[friendly] = b
            if storage == "node":
                writes.append(f"n.{key} = {'true' if b else 'false'}")
            else:
                writes.append(f'setUserProp n "{key}" "{"True" if b else "False"}"')
        else:
            f = _coerce_float(value)
            if friendly == "alpha_contribution" and not -1.0 <= f <= 1.0:
                raise ValueError("alpha_contribution must be between -1 and 1")
            expected[friendly] = f
            writes.append(f'setUserProp n "{key}" (mcpVLocal "{format_user_prop_float(f)}" dsep)')

    states = _object_state(names)
    _validate_nodes(names, states)
    body = r'''
local req = %NAMES%
local dsep = try ((dotNetClass "System.Globalization.CultureInfo").CurrentCulture.NumberFormat.NumberDecimalSeparator as string) catch (".")
if dsep != "," do dsep = "."
fn mcpVLocal txt sep = (substituteString txt "." sep)
undo "MCP V-Ray object properties" on (
    for nm in req do (
        local n = (getNodeByName nm all:true)[1]
%WRITES%
    )
)
"{\"decimal_separator\":\"" + dsep + "\"}"
'''.replace("%NAMES%", "#(" + ",".join(_ms_str(n) for n in names) + ")").replace(
        "%WRITES%", "\n".join("        " + w for w in writes))
    written = _run(body)
    after = [_describe_object(s) for s in _object_state(names)]
    mismatches = []
    for obj in after:
        for friendly, want in expected.items():
            got = obj["properties"].get(friendly)
            if not values_match(want, got):
                mismatches.append(f"{obj['name']}.{friendly}: wrote {want!r}, read back {got!r}")
    if mismatches:
        raise RuntimeError("V-Ray object property read-back mismatch: " + "; ".join(mismatches)
                           + f". Stored now: {json.dumps(after)}")
    result: dict[str, Any] = {"objects": after, "set": sorted(expected),
                              "float_decimal_separator": written.get("decimal_separator")}
    if warnings:
        result["warnings"] = warnings
    return json.dumps(result)
