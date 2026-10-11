"""Scene file tools: geometry export to disk, versioned save-as, scene setup.

Every tool here that writes a file asks :mod:`maxmcp.path_policy` first, with
``scene_dir`` set to the folder of the scene open in the targeted Max. The
heavy lifting (geometry writing) happens inside 3ds Max so large meshes never
travel through the pipe.
"""
from __future__ import annotations

import json as _json
import math
import os
import re
from dataclasses import dataclass
from typing import Any, Optional

from ..coerce import FloatList, IntList, StrList
from ..path_policy import resolve_write_path
from ..server import client, mcp

# ---------------------------------------------------------------------------
# MAXScript helpers
# ---------------------------------------------------------------------------

# JSON string quoting inside MAXScript (names, paths). Defined as a local
# function at the top of every script block that needs it.
_MS_JSTR = r'''
    fn mcpSfJ s = (
        s = s as string
        s = substituteString s "\\" "\\\\"
        s = substituteString s "\"" "\\\""
        s = substituteString s "\n" "\\n"
        s = substituteString s "\r" "\\r"
        s = substituteString s "\t" "\\t"
        "\"" + s + "\""
    )
'''


def _ms_str(value: str) -> str:
    """Quote *value* as a MAXScript string literal (backslash/quote/control escaped)."""
    out = (
        str(value)
        .replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", "\\n")
        .replace("\r", "\\r")
        .replace("\t", "\\t")
    )
    return f'"{out}"'


def _ms_float(value: float) -> str:
    """Locale-free float literal for MAXScript ('.' decimal, never a comma)."""
    if not math.isfinite(value):
        raise ValueError(f"non-finite number: {value!r}")
    return repr(float(value))


def _run(script: str, *, timeout: Optional[float] = None) -> dict[str, Any]:
    """Send *script*, parse its JSON result and raise on a script-reported error."""
    response = client.send_command(script, timeout=timeout) if timeout else client.send_command(script)
    raw = response.get("result", "")
    try:
        data = _json.loads(raw) if isinstance(raw, str) else raw
    except ValueError as exc:
        raise RuntimeError(f"3ds Max returned non-JSON output: {str(raw)[:400]}") from exc
    if not isinstance(data, dict):
        raise RuntimeError(f"3ds Max returned an unexpected result: {str(raw)[:400]}")
    if data.get("error"):
        raise RuntimeError(str(data["error"]))
    return data


_SCENE_STATE_SCRIPT = "(" + _MS_JSTR + r'''
    "{\"path\":" + (mcpSfJ maxFilePath) + ",\"name\":" + (mcpSfJ maxFileName) + "}"
)'''


def _scene_state() -> tuple[str, str]:
    """Return (maxFilePath, maxFileName) of the targeted Max ('' when untitled)."""
    data = _run(_SCENE_STATE_SCRIPT)
    return str(data.get("path") or ""), str(data.get("name") or "")


def _same_path(a: str, b: str) -> bool:
    return os.path.normcase(os.path.normpath(a)) == os.path.normcase(os.path.normpath(b))


# ---------------------------------------------------------------------------
# export_geometry
# ---------------------------------------------------------------------------

_EXPORT_TEMPLATE = "(" + _MS_JSTR + r'''
    local errs = #()
    local warns = #()
    local nodes = #()
    local skipped = #()
    local summary = stringStream ""
    if (maxFilePath + maxFileName) != @EXPECTED_SCENE@ then (
        append errs ("The open scene changed while preparing the export; now " + (maxFilePath + maxFileName))
    )
    -- formattedPrint must write '.' decimals; refuse rather than write commas.
    if (formattedPrint 0.5 format:".1f") != "0.5" do (
        append errs ("formattedPrint is locale-dependent in this Max (0.5 -> " + (formattedPrint 0.5 format:".1f") + ")")
    )
    for n in @NAMES@ do (
        local found = getNodeByName n exact:true all:true
        if found == undefined or found.count == 0 then append errs ("No object named " + n)
        else (
            if found.count > 1 do append warns ((found.count as string) + " objects are named " + n + "; all were exported")
            for o in found do appendIfUnique nodes o
        )
    )
    for h in @HANDLES@ do (
        local o = maxOps.getNodeByHandle h
        if o == undefined then append errs ("No object with handle " + (h as string))
        else appendIfUnique nodes o
    )
    local exportable = #()
    for o in nodes do (
        if canConvertTo o TriMeshGeometry then append exportable o
        else append skipped o.name
    )
    if errs.count == 0 and exportable.count == 0 do append errs "None of the requested objects has mesh geometry"
    if errs.count > 0 then (
        local es = stringStream ""
        for i = 1 to errs.count do (if i > 1 do format "; " to:es; format "%" errs[i] to:es)
        "{\"error\":" + (mcpSfJ (es as string)) + "}"
    ) else (
        local fmt = @NUMFMT@
        local isLocal = @IS_LOCAL@
        local doN = @NORMALS@
        local doUV = @UVS@
        local isObj = @IS_OBJ@
        local outPath = @PATH@
        makeDir (getFilenamePath outPath) all:true
        local f = openFile outPath mode:"wt"
        if f == undefined then (
            "{\"error\":" + (mcpSfJ ("Could not open " + outPath + " for writing")) + "}"
        ) else (
            local unitName = units.SystemType as string
            local vOff = 0
            local tOff = 0
            if isObj then (
                format "# 3dsmax-mcp export_geometry\n# space=% system_units=% scale=% objects=%\n" (if isLocal then "local" else "world") unitName (formattedPrint units.SystemScale format:fmt) exportable.count to:f
            ) else (
                format "{\"format\":\"3dsmax-mcp-geometry\",\"version\":1,\"space\":\"%\",\"system_units\":\"%\",\"system_scale\":%,\"objects\":[\n" (if isLocal then "local" else "world") unitName (formattedPrint units.SystemScale format:fmt) to:f
            )
            format "[" to:summary
            with undo off (
                for oi = 1 to exportable.count do (
                    local o = exportable[oi]
                    local m = snapshotAsMesh o
                    local tm = o.objectTransform
                    local itm = inverse tm
                    local nv = m.numVerts
                    local nf = m.numFaces
                    local hasUV = doUV and (meshop.getMapSupport m 1)
                    local ntv = if hasUV then (meshop.getNumMapVerts m 1) else 0
                    if doUV and not hasUV do append warns (o.name + " has no map channel 1; UVs omitted")
                    local clean = substituteString (substituteString o.name "\n" " ") "\r" " "
                    if isObj then (
                        format "o %\ng %\n" clean clean to:f
                        for i = 1 to nv do (
                            local p = getVert m i
                            if isLocal do p = p * itm
                            format "v % % %\n" (formattedPrint p.x format:fmt) (formattedPrint p.y format:fmt) (formattedPrint p.z format:fmt) to:f
                        )
                        for i = 1 to ntv do (
                            local t = meshop.getMapVert m 1 i
                            format "vt % %\n" (formattedPrint t.x format:fmt) (formattedPrint t.y format:fmt) to:f
                        )
                        if doN do for i = 1 to nv do (
                            local nn = getNormal m i
                            if isLocal do nn = normalize [dot nn tm.row1, dot nn tm.row2, dot nn tm.row3]
                            format "vn % % %\n" (formattedPrint nn.x format:fmt) (formattedPrint nn.y format:fmt) (formattedPrint nn.z format:fmt) to:f
                        )
                        for i = 1 to nf do (
                            local fc = getFace m i
                            local a = (fc.x as integer) + vOff
                            local b = (fc.y as integer) + vOff
                            local c = (fc.z as integer) + vOff
                            if hasUV then (
                                local tf = meshop.getMapFace m 1 i
                                local ta = (tf.x as integer) + tOff
                                local tb = (tf.y as integer) + tOff
                                local tc = (tf.z as integer) + tOff
                                if doN then format "f %/%/% %/%/% %/%/%\n" a ta a b tb b c tc c to:f
                                else format "f %/% %/% %/%\n" a ta b tb c tc to:f
                            ) else (
                                if doN then format "f %//% %//% %//%\n" a a b b c c to:f
                                else format "f % % %\n" a b c to:f
                            )
                        )
                    ) else (
                        if oi > 1 do format ",\n" to:f
                        format "{\"name\":%,\"handle\":%,\"vertex_count\":%,\"face_count\":%,\"vertices\":[" (mcpSfJ o.name) o.inode.handle nv nf to:f
                        for i = 1 to nv do (
                            local p = getVert m i
                            if isLocal do p = p * itm
                            if i > 1 do format "," to:f
                            format "[%,%,%]" (formattedPrint p.x format:fmt) (formattedPrint p.y format:fmt) (formattedPrint p.z format:fmt) to:f
                        )
                        format "],\n\"faces\":[" to:f
                        for i = 1 to nf do (
                            local fc = getFace m i
                            if i > 1 do format "," to:f
                            format "[%,%,%]" ((fc.x as integer) - 1) ((fc.y as integer) - 1) ((fc.z as integer) - 1) to:f
                        )
                        format "]" to:f
                        if doN do (
                            format ",\n\"normals\":[" to:f
                            for i = 1 to nv do (
                                local nn = getNormal m i
                                if isLocal do nn = normalize [dot nn tm.row1, dot nn tm.row2, dot nn tm.row3]
                                if i > 1 do format "," to:f
                                format "[%,%,%]" (formattedPrint nn.x format:fmt) (formattedPrint nn.y format:fmt) (formattedPrint nn.z format:fmt) to:f
                            )
                            format "]" to:f
                        )
                        if hasUV do (
                            format ",\n\"uvs\":[" to:f
                            for i = 1 to ntv do (
                                local t = meshop.getMapVert m 1 i
                                if i > 1 do format "," to:f
                                format "[%,%]" (formattedPrint t.x format:fmt) (formattedPrint t.y format:fmt) to:f
                            )
                            format "],\n\"uv_faces\":[" to:f
                            for i = 1 to nf do (
                                local tf = meshop.getMapFace m 1 i
                                if i > 1 do format "," to:f
                                format "[%,%,%]" ((tf.x as integer) - 1) ((tf.y as integer) - 1) ((tf.z as integer) - 1) to:f
                            )
                            format "]" to:f
                        )
                        format "}" to:f
                    )
                    if oi > 1 do format "," to:summary
                    format "{\"name\":%,\"handle\":%,\"vertices\":%,\"faces\":%,\"uv_vertices\":%,\"normals\":%}" (mcpSfJ o.name) o.inode.handle nv nf ntv doN to:summary
                    vOff += nv
                    tOff += ntv
                    delete m
                )
            )
            if not isObj do format "\n]}\n" to:f
            close f
            format "]" to:summary
            local ws = stringStream ""
            format "[" to:ws
            for i = 1 to warns.count do (if i > 1 do format "," to:ws; format "%" (mcpSfJ warns[i]) to:ws)
            format "]" to:ws
            local ks = stringStream ""
            format "[" to:ks
            for i = 1 to skipped.count do (if i > 1 do format "," to:ks; format "%" (mcpSfJ skipped[i]) to:ks)
            format "]" to:ks
            "{\"objects\":" + (summary as string) + ",\"skipped\":" + (ks as string) + ",\"warnings\":" + (ws as string) + ",\"system_units\":" + (mcpSfJ unitName) + "}"
        )
    )
)'''


def _ms_array_str(values: list[str]) -> str:
    return "#(" + ", ".join(_ms_str(v) for v in values) + ")"


def _ms_array_int(values: list[int]) -> str:
    return "#(" + ", ".join(str(int(v)) for v in values) + ")"


def _ms_bool(value: bool) -> str:
    return "true" if value else "false"


def build_export_script(
    *,
    out_path: str,
    expected_scene: str,
    names: list[str],
    handles: list[int],
    fmt: str,
    space: str,
    include_normals: bool,
    include_uvs: bool,
    precision: int,
) -> str:
    replacements = {
        "@EXPECTED_SCENE@": _ms_str(expected_scene),
        "@NAMES@": _ms_array_str(names),
        "@HANDLES@": _ms_array_int(handles),
        "@NUMFMT@": _ms_str(f".{int(precision)}g"),
        "@IS_LOCAL@": _ms_bool(space == "local"),
        "@NORMALS@": _ms_bool(include_normals),
        "@UVS@": _ms_bool(include_uvs),
        "@IS_OBJ@": _ms_bool(fmt == "obj"),
        "@PATH@": _ms_str(out_path),
    }
    script = _EXPORT_TEMPLATE
    for key, value in replacements.items():
        script = script.replace(key, value)
    return script


@mcp.tool()
def export_geometry(
    path: str,
    names: StrList | None = None,
    handles: IntList | None = None,
    format: str = "obj",
    space: str = "world",
    include_normals: bool = True,
    include_uvs: bool = True,
    precision: int = 9,
    overwrite: bool = False,
    timeout_s: float = 600.0,
) -> dict:
    """Write objects' evaluated geometry to a file inside 3ds Max (nothing big crosses the pipe).

    Pick objects by exact ``names`` and/or node ``handles``. ``format``: ``obj`` (Wavefront,
    1-based indices, one ``o``/``g`` block per object) or ``json`` (``{"objects":[{name, handle,
    vertices, faces (0-based), normals?, uvs?, uv_faces?}]}``). ``space``: ``world`` or ``local``
    (object space = world multiplied by the inverse of ``objectTransform``). Geometry is the
    triangulated world-state mesh (``snapshotAsMesh``), so face counts are triangles. Normals are
    per-vertex; UVs come from map channel 1 and are omitted (with a warning) when absent.
    Numbers are written with '.' decimals and ``precision`` significant digits (9 = float32
    round-trip). Written by a MAXScript writer, not the Max OBJ exporter: that exporter's
    settings live in a shared per-user ini (presets, Y/Z flip, .mtl side files) a tool cannot
    set per call without changing every other Max session.

    ``path`` must be inside an allowed folder (``[safe_mode] allowed_dirs``, the open scene's
    folder, or %TEMP%\\3dsmax-mcp); an existing file is refused unless ``overwrite=True``.
    Returns the path, object/vertex/face totals, file size and per-object counts.
    """
    fmt = (format or "").strip().lower()
    if fmt not in ("obj", "json"):
        raise ValueError("format must be 'obj' or 'json'")
    space_n = (space or "").strip().lower()
    if space_n not in ("world", "local"):
        raise ValueError("space must be 'world' or 'local'")
    names_l = [str(n) for n in (names or []) if str(n)]
    handles_l = [int(h) for h in (handles or [])]
    if not names_l and not handles_l:
        raise ValueError("Pass at least one object in names or handles")
    precision = int(precision)
    if not 1 <= precision <= 17:
        raise ValueError("precision must be between 1 and 17 significant digits")
    if not math.isfinite(timeout_s) or timeout_s <= 0:
        raise ValueError("timeout_s must be a positive number")

    scene_path, scene_name = _scene_state()
    target = resolve_write_path(path, scene_dir=scene_path or None)
    if target.exists() and not overwrite:
        raise FileExistsError(f"{target} already exists; pass overwrite=True to replace it")
    if target.exists() and target.is_dir():
        raise IsADirectoryError(f"{target} is a folder; pass a file path")

    script = build_export_script(
        out_path=str(target),
        expected_scene=scene_path + scene_name,
        names=names_l,
        handles=handles_l,
        fmt=fmt,
        space=space_n,
        include_normals=bool(include_normals),
        include_uvs=bool(include_uvs),
        precision=precision,
    )
    data = _run(script, timeout=float(timeout_s))
    objects = list(data.get("objects") or [])
    if not target.is_file():
        raise RuntimeError(f"3ds Max reported success but {target} does not exist")
    warnings = [str(w) for w in data.get("warnings") or []]
    skipped = [str(s) for s in data.get("skipped") or []]
    if skipped:
        warnings.append(f"Skipped objects without mesh geometry: {', '.join(skipped)}")
    result: dict[str, Any] = {
        "path": str(target),
        "format": fmt,
        "space": space_n,
        "object_count": len(objects),
        "vertex_count": sum(int(o.get("vertices", 0)) for o in objects),
        "face_count": sum(int(o.get("faces", 0)) for o in objects),
        "face_type": "triangles",
        "file_size": target.stat().st_size,
        "system_units": data.get("system_units"),
        "objects": objects[:200],
        "skipped": skipped,
    }
    if len(objects) > 200:
        result["objects_truncated"] = len(objects)
    if warnings:
        result["warnings"] = warnings
    return result


# ---------------------------------------------------------------------------
# save_scene_versioned
# ---------------------------------------------------------------------------

_VERSION_RE = re.compile(r"^(?P<base>.*?)(?P<sep>_?)(?P<v>[Vv])(?P<num>\d+)$")
_TOKEN_RE = re.compile(r"(?<![A-Za-z0-9])(?P<v>[Vv])(?P<num>\d+)(?![0-9])")


@dataclass(frozen=True)
class VersionedName:
    base: str
    sep: str = "_"
    v: str = "V"
    num: int = 0
    pad: int = 3

    def stem(self, num: Optional[int] = None) -> str:
        n = self.num if num is None else num
        return f"{self.base}{self.sep}{self.v}{n:0{self.pad}d}"


def parse_versioned_stem(stem: str) -> Optional[VersionedName]:
    """Parse ``<base>_V###`` / ``<base>_v###`` / ``<base>V###``; None when there is no token."""
    match = _VERSION_RE.match(stem)
    if not match:
        return None
    digits = match.group("num")
    return VersionedName(
        base=match.group("base"),
        sep=match.group("sep"),
        v=match.group("v"),
        num=int(digits),
        pad=len(digits),
    )


def highest_existing_version(folder: str, base: str) -> int:
    """Highest version number of ``<base>[_][Vv]###.max`` files in *folder* (0 when none)."""
    pattern = re.compile(r"^" + re.escape(base) + r"_?[Vv](\d+)\.max$", re.IGNORECASE)
    best = 0
    try:
        entries = os.listdir(folder)
    except OSError:
        return 0
    for entry in entries:
        match = pattern.match(entry)
        if match:
            best = max(best, int(match.group(1)))
    return best


def retarget_version_tokens(
    text: str,
    *,
    old_stem: Optional[str],
    new_stem: str,
    old_num: Optional[int],
    new_num: int,
) -> tuple[str, str]:
    """Rewrite the version tokens of a render output path for a new scene version.

    Order: replace the old scene stem verbatim; else replace delimited ``V###`` tokens whose
    number equals the old scene version (each keeps its own padding); else replace the last
    token of the file name (``already`` when it carries the new number). Returns
    ``(new_text, how)`` with how in ``stem|token|basename_token|already|none|empty``.
    """
    if not text:
        return text, "empty"
    out = text
    how = "none"
    if old_stem and old_stem != new_stem and old_stem in out:
        out = out.replace(old_stem, new_stem)
        how = "stem"
    if old_num is not None:
        def swap(match: re.Match[str]) -> str:
            digits = match.group("num")
            if int(digits) != old_num:
                return match.group(0)
            return f"{match.group('v')}{new_num:0{len(digits)}d}"

        swapped = _TOKEN_RE.sub(swap, out)
        if swapped != out:
            out = swapped
            if how == "none":
                how = "token"
    if how == "none":
        cut = max(out.rfind("\\"), out.rfind("/")) + 1
        head, tail = out[:cut], out[cut:]
        tokens = list(_TOKEN_RE.finditer(tail))
        if tokens:
            last = tokens[-1]
            digits = last.group("num")
            if int(digits) == new_num:
                return out, "already"
            tail = f"{tail[:last.start()]}{last.group('v')}{new_num:0{len(digits)}d}{tail[last.end():]}"
            out = head + tail
            how = "basename_token"
    return out, how


_SAVE_READ_SCRIPT = "(" + _MS_JSTR + r'''
    local r = renderers.current
    local vs = stringStream ""
    format "{" to:vs
    local firstV = true
    for p in #(#output_fileName, #output_rawFileName, #output_splitfilename) do (
        if r != undefined and (isProperty r p) do (
            if not firstV do format "," to:vs
            format "%:%" (mcpSfJ (p as string)) (mcpSfJ ((getProperty r p) as string)) to:vs
            firstV = false
        )
    )
    format "}" to:vs
    local re = maxOps.GetCurRenderElementMgr()
    local es = stringStream ""
    format "[" to:es
    for i = 0 to (re.NumRenderElements() - 1) do (
        if i > 0 do format "," to:es
        local efn = re.GetRenderElementFilename i
        format "%" (mcpSfJ (if efn == undefined then "" else efn)) to:es
    )
    format "]" to:es
    local isVray = r != undefined and (matchPattern ((classof r) as string) pattern:"V_Ray*")
    "{\"path\":" + (mcpSfJ maxFilePath) + ",\"name\":" + (mcpSfJ maxFileName) + ",\"render_output\":" + (mcpSfJ rendOutputFilename) + ",\"renderer\":" + (mcpSfJ ((classof r) as string)) + ",\"is_vray\":" + (isVray as string) + ",\"vray\":" + (vs as string) + ",\"elements\":" + (es as string) + "}"
)'''


_SAVE_APPLY_TEMPLATE = "(" + _MS_JSTR + r'''
    local newPath = @NEW_PATH@
    local result = undefined
    if (maxFilePath + maxFileName) != @EXPECTED_SCENE@ then (
        result = "{\"error\":" + (mcpSfJ ("The open scene changed since it was read; now " + (maxFilePath + maxFileName))) + "}"
    ) else if doesFileExist newPath then (
        result = "{\"error\":" + (mcpSfJ ("Refusing to overwrite existing file " + newPath)) + "}"
    ) else (
        local dir = getFilenamePath newPath
        if not (doesDirectoryExist dir) do makeDir dir all:true
        if not (doesDirectoryExist dir) then (
            result = "{\"error\":" + (mcpSfJ ("Could not create folder " + dir)) + "}"
        ) else (
            local dlgOpen = renderSceneDialog.isOpen()
            if dlgOpen do renderSceneDialog.close()
            local r = renderers.current
            local oldOut = rendOutputFilename
            local oldV = #()
            local vProps = @VRAY_PROPS@
            local vVals = @VRAY_VALUES@
            local re = maxOps.GetCurRenderElementMgr()
            local eVals = @ELEMENT_VALUES@
            local oldE = for i = 0 to (re.NumRenderElements() - 1) collect (re.GetRenderElementFilename i)
            if @SET_OUTPUT@ do rendOutputFilename = @NEW_OUTPUT@
            for i = 1 to vProps.count do (
                append oldV (getProperty r vProps[i])
                setProperty r vProps[i] vVals[i]
            )
            if eVals.count == oldE.count do (
                for i = 1 to eVals.count do re.SetRenderElementFilename (i - 1) eVals[i]
            )
            local ok = false
            try (ok = saveMaxFile newPath quiet:true) catch (ok = false)
            if not ok or not (doesFileExist newPath) then (
                rendOutputFilename = oldOut
                for i = 1 to vProps.count do setProperty r vProps[i] oldV[i]
                for i = 1 to oldE.count do (if oldE[i] != undefined do re.SetRenderElementFilename (i - 1) oldE[i])
                result = "{\"error\":" + (mcpSfJ ("saveMaxFile failed for " + newPath + "; render paths restored")) + "}"
            ) else (
                local vs = stringStream ""
                format "{" to:vs
                for i = 1 to vProps.count do (
                    if i > 1 do format "," to:vs
                    format "%:%" (mcpSfJ (vProps[i] as string)) (mcpSfJ ((getProperty r vProps[i]) as string)) to:vs
                )
                format "}" to:vs
                local es = stringStream ""
                format "[" to:es
                for i = 0 to (re.NumRenderElements() - 1) do (
                    if i > 0 do format "," to:es
                    local efn = re.GetRenderElementFilename i
                    format "%" (mcpSfJ (if efn == undefined then "" else efn)) to:es
                )
                format "]" to:es
                result = "{\"path\":" + (mcpSfJ maxFilePath) + ",\"name\":" + (mcpSfJ maxFileName) + ",\"render_output\":" + (mcpSfJ rendOutputFilename) + ",\"vray\":" + (vs as string) + ",\"elements\":" + (es as string) + "}"
            )
            if dlgOpen do renderSceneDialog.open()
        )
    )
    result
)'''


def _plan_versioned_target(
    *,
    scene_path: str,
    scene_name: str,
    path: Optional[str],
    base_name: Optional[str],
) -> tuple[str, Optional[VersionedName]]:
    """Return (absolute target .max path, parsed new version or None)."""
    current_stem = os.path.splitext(scene_name)[0] if scene_name else ""
    current = parse_versioned_stem(current_stem) if current_stem else None

    if path and str(path).strip().lower().endswith(".max"):
        target = os.path.abspath(os.path.expandvars(str(path).strip()))
        return target, parse_versioned_stem(os.path.splitext(os.path.basename(target))[0])

    if path and str(path).strip():
        folder = os.path.abspath(os.path.expandvars(str(path).strip()))
    elif scene_path:
        folder = os.path.abspath(scene_path)
    else:
        raise ValueError("The scene has never been saved: pass path (a folder or a .max file)")

    if base_name is not None and str(base_name).strip():
        base = str(base_name).strip()
        if base.lower().endswith(".max"):
            base = base[:-4]
        if any(ch in base for ch in '\\/:*?"<>|'):
            raise ValueError("base_name must be a plain file name without folders")
    elif current is not None:
        base = current.base
    elif current_stem:
        base = current_stem
    else:
        raise ValueError("The scene has never been saved: pass base_name or a .max path")

    same_base = current is not None and current.base.lower() == base.lower()
    if same_base:
        style = VersionedName(base=base, sep=current.sep, v=current.v, num=current.num, pad=current.pad)
        next_num = current.num + 1
    else:
        style = VersionedName(base=base)
        next_num = highest_existing_version(folder, base) + 1
    new = VersionedName(base=style.base, sep=style.sep, v=style.v, num=next_num, pad=style.pad)
    return os.path.join(folder, new.stem() + ".max"), new


@mcp.tool()
def save_scene_versioned(path: Optional[str] = None, base_name: Optional[str] = None) -> dict:
    """Save the open scene as its next version and point render outputs at that version.

    Naming: ``<base>_V###`` (``_v###`` and ``V###`` without underscore are recognised; the
    existing separator, letter case and zero padding are kept, ``V999`` grows to ``V1000``).
    * no arguments: next version of the open scene in its own folder (``shot_V004`` -> ``shot_V005``).
    * ``path`` = folder: next version saved into that folder (created if needed).
    * ``path`` = ``.max`` file: saved exactly there (e.g. the first ``shot_V001.max`` of an
      untitled scene).
    * ``base_name``: start/continue a different base; its number is one past the highest
      ``<base>_V###.max`` already in the target folder.
    An existing target is never overwritten: the call fails and names the file. The target must
    be inside an allowed folder (path policy). Before saving, the version token in
    ``rendOutputFilename``, render element paths and (when V-Ray is current) the V-Ray
    ``output_fileName`` / ``output_rawFileName`` / ``output_splitfilename`` are rewritten to the
    new version, so the saved file already carries them; on a failed save they are restored.
    Returns old/new scene paths and old/new render output paths.
    """
    state = _run(_SAVE_READ_SCRIPT)
    scene_path = str(state.get("path") or "")
    scene_name = str(state.get("name") or "")
    old_full = os.path.join(scene_path, scene_name) if scene_name else ""

    target, new_version = _plan_versioned_target(
        scene_path=scene_path, scene_name=scene_name, path=path, base_name=base_name)
    resolved = resolve_write_path(target, scene_dir=scene_path or None)
    target = str(resolved)
    if old_full and _same_path(old_full, target):
        raise FileExistsError(f"{target} is the open scene; refusing to overwrite it")
    if os.path.exists(target):
        folder, fname = os.path.split(target)
        stem = os.path.splitext(fname)[0]
        parsed = parse_versioned_stem(stem)
        highest = highest_existing_version(folder, parsed.base) if parsed else 0
        hint = f" (highest existing version: {highest})" if highest else ""
        raise FileExistsError(f"Refusing to overwrite existing file {target}{hint}")

    warnings: list[str] = []
    current = parse_versioned_stem(os.path.splitext(scene_name)[0]) if scene_name else None
    old_stem = os.path.splitext(scene_name)[0] if scene_name else None
    new_stem = os.path.splitext(os.path.basename(target))[0]

    def retarget(label: str, value: str) -> str:
        if new_version is None:
            if value:
                warnings.append(f"{label}: new scene name has no version token; left unchanged")
            return value
        out, how = retarget_version_tokens(
            value, old_stem=old_stem, new_stem=new_stem,
            old_num=current.num if current else None, new_num=new_version.num)
        if how == "none":
            warnings.append(f"{label} has no version token; left unchanged: {value}")
        elif how == "basename_token":
            warnings.append(
                f"{label} version token did not match the scene version; set to {new_version.num}: {out}")
        return out

    old_output = str(state.get("render_output") or "")
    new_output = retarget("rendOutputFilename", old_output)

    vray_old: dict[str, str] = {}
    vray_new: dict[str, str] = {}
    if state.get("is_vray"):
        for prop, value in dict(state.get("vray") or {}).items():
            value = str(value or "")
            if value:
                vray_old[prop] = value
                vray_new[prop] = retarget(f"V-Ray {prop}", value)

    elements_old = [str(e or "") for e in state.get("elements") or []]
    elements_new = [retarget(f"render element {i + 1}", e) if e else e for i, e in enumerate(elements_old)]

    vray_props = [p for p in vray_new if vray_new[p] != vray_old[p]]
    script = _SAVE_APPLY_TEMPLATE
    script = script.replace("@NEW_PATH@", _ms_str(target))
    script = script.replace("@EXPECTED_SCENE@", _ms_str(scene_path + scene_name))
    script = script.replace("@SET_OUTPUT@", _ms_bool(new_output != old_output))
    script = script.replace("@NEW_OUTPUT@", _ms_str(new_output))
    script = script.replace("@VRAY_PROPS@", "#(" + ", ".join(f"#{p}" for p in vray_props) + ")")
    script = script.replace("@VRAY_VALUES@", _ms_array_str([vray_new[p] for p in vray_props]))
    script = script.replace(
        "@ELEMENT_VALUES@", _ms_array_str(elements_new) if elements_new != elements_old else "#()")
    after = _run(script, timeout=600.0)

    saved = os.path.join(str(after.get("path") or ""), str(after.get("name") or ""))
    if not _same_path(saved, target):
        raise RuntimeError(f"Saved scene reads back as {saved!r}, expected {target!r}")
    if not os.path.isfile(target):
        raise RuntimeError(f"3ds Max reported a save but {target} does not exist")
    read_output = str(after.get("render_output") or "")
    if read_output != new_output:
        raise RuntimeError(f"rendOutputFilename reads back as {read_output!r}, expected {new_output!r}")
    read_vray = {k: str(v) for k, v in dict(after.get("vray") or {}).items()}
    for prop in vray_props:
        if read_vray.get(prop) != vray_new[prop]:
            raise RuntimeError(f"V-Ray {prop} reads back as {read_vray.get(prop)!r}, expected {vray_new[prop]!r}")

    result: dict[str, Any] = {
        "old_path": old_full or None,
        "new_path": target,
        "version": new_version.num if new_version else None,
        "version_label": new_version.stem()[len(new_version.base):].lstrip("_") if new_version else None,
        "render_output": {"old": old_output, "new": read_output},
        "file_size": os.path.getsize(target),
    }
    if vray_old:
        result["vray_output"] = {p: {"old": vray_old[p], "new": read_vray.get(p, vray_old[p])} for p in vray_old}
    if elements_old:
        result["render_elements"] = [
            {"old": o, "new": n} for o, n in zip(elements_old, [str(e) for e in after.get("elements") or []])
        ]
    if warnings:
        result["warnings"] = warnings
    return result


# ---------------------------------------------------------------------------
# scene_setup
# ---------------------------------------------------------------------------

_SYSTEM_UNITS = {
    "mm": "millimeters", "millimeter": "millimeters", "millimeters": "millimeters",
    "cm": "centimeters", "centimeter": "centimeters", "centimeters": "centimeters",
    "m": "meters", "meter": "meters", "meters": "meters",
    "km": "kilometers", "kilometer": "kilometers", "kilometers": "kilometers",
    "in": "inches", "inch": "inches", "inches": "inches",
    "ft": "feet", "foot": "feet", "feet": "feet",
    "mi": "miles", "mile": "miles", "miles": "miles",
}

# display unit -> (DisplayType, MetricType or USType or None)
_DISPLAY_UNITS = {
    "generic": ("generic", None),
    "mm": ("metric", "millimeters"), "millimeters": ("metric", "millimeters"),
    "cm": ("metric", "centimeters"), "centimeters": ("metric", "centimeters"),
    "m": ("metric", "meters"), "meters": ("metric", "meters"),
    "km": ("metric", "kilometers"), "kilometers": ("metric", "kilometers"),
    "in": ("us", "dec_in"), "inches": ("us", "dec_in"), "dec_in": ("us", "dec_in"),
    "frac_in": ("us", "frac_in"),
    "ft": ("us", "dec_ft"), "feet": ("us", "dec_ft"), "dec_ft": ("us", "dec_ft"),
    "frac_ft": ("us", "frac_ft"), "ft_frac_in": ("us", "ft_frac_in"), "ft_dec_in": ("us", "ft_dec_in"),
}

_SETUP_TEMPLATE = "(" + r'''
    fn mcpSfState = (
        local s = stringStream ""
        format "{\"units\":\"%\",\"system_scale\":%,\"display_type\":\"%\",\"metric_type\":\"%\",\"us_type\":\"%\",\"frame_start\":%,\"frame_end\":%,\"fps\":%,\"render_width\":%,\"render_height\":%,\"pixel_aspect\":%}" (units.SystemType as string) (formattedPrint units.SystemScale format:".9g") (units.DisplayType as string) (units.MetricType as string) (units.USType as string) (formattedPrint animationRange.start.frame format:".9g") (formattedPrint animationRange.end.frame format:".9g") frameRate renderWidth renderHeight (formattedPrint renderPixelAspect format:".9g") to:s
        s as string
    )
    local before = mcpSfState()
    local err = ""
    try (
@BODY@
    ) catch (err = getCurrentException())
    local after = mcpSfState()
    if err != "" then (
        local e = substituteString (substituteString err "\\" "/") "\"" "'"
        e = substituteString (substituteString e "\n" " ") "\r" " "
        "{\"error\":\"" + e + "\",\"previous\":" + before + ",\"current\":" + after + "}"
    ) else "{\"previous\":" + before + ",\"current\":" + after + "}"
)'''


def build_setup_body(
    *,
    system_units: Optional[str],
    display: Optional[tuple[str, Optional[str]]],
    fps: Optional[int],
    frame_range: Optional[tuple[int, int]],
    render_size: Optional[tuple[int, int]],
    pixel_aspect: Optional[float],
) -> str:
    lines: list[str] = []
    if system_units:
        lines.append(f"units.SystemType = #{system_units}")
    if display:
        dtype, sub = display
        lines.append(f"units.DisplayType = #{dtype}")
        if dtype == "metric" and sub:
            lines.append(f"units.MetricType = #{sub}")
        elif dtype == "us" and sub:
            lines.append(f"units.USType = #{sub}")
    if fps is not None:
        # Frame rate first: changing it re-expresses the existing range in new frames.
        lines.append(f"frameRate = {int(fps)}")
    if frame_range is not None:
        # Plain integers: an `Nf` literal is converted to ticks at parse time with the OLD frame
        # rate, so after a frameRate change it would land on the wrong frame.
        lines.append(f"animationRange = interval {int(frame_range[0])} {int(frame_range[1])}")
    if render_size is not None or pixel_aspect is not None:
        lines.append("local dlgOpen = renderSceneDialog.isOpen()")
        lines.append("if dlgOpen do renderSceneDialog.close()")
        lines.append("local lockImg = rendLockImageAspectRatio")
        lines.append("rendLockImageAspectRatio = false")
        if render_size is not None:
            lines.append(f"renderWidth = {int(render_size[0])}")
            lines.append(f"renderHeight = {int(render_size[1])}")
        if pixel_aspect is not None:
            lines.append(f"renderPixelAspect = {_ms_float(pixel_aspect)}")
        lines.append("rendLockImageAspectRatio = lockImg")
        lines.append("if dlgOpen do renderSceneDialog.open()")
    return "\n".join("        " + line for line in lines)


def _two_ints(value: Any, label: str) -> tuple[int, int]:
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise ValueError(f"{label} must be [a, b]")
    out: list[int] = []
    for item in value:
        number = float(item)
        if not math.isfinite(number) or number != int(number):
            raise ValueError(f"{label} values must be whole numbers, got {item!r}")
        out.append(int(number))
    return out[0], out[1]


@mcp.tool()
def scene_setup(
    units: Optional[str] = None,
    display_units: Optional[str] = None,
    frame_range: Optional[FloatList] = None,
    fps: Optional[float] = None,
    render_size: Optional[FloatList] = None,
    pixel_aspect: Optional[float] = None,
) -> dict:
    """Set scene units, timeline and render size; read every value back and fail on mismatch.

    * ``units``: system unit (mm|cm|m|km|in|ft|mi). Changing system units on an existing scene
      does NOT rescale objects: a 100-unit box stays 100 units, it is just measured in the new
      unit (100 cm becomes 100 mm). Rescale geometry separately if that is what you want.
    * ``display_units``: generic | mm|cm|m|km (metric) | in|ft|frac_in|frac_ft|ft_frac_in|ft_dec_in (US).
    * ``frame_range``: [start, end] in whole frames (end > start), applied after ``fps``.
    * ``fps``: whole frames per second (``frameRate``). Changing fps alone re-expresses the
      existing range in the new frame count (time is kept, frames change) - pass
      ``frame_range`` too to pin it.
    * ``render_size``: [width, height] in pixels; ``pixel_aspect``: renderPixelAspect. The
      image-aspect lock is released while setting and restored afterwards; an open Render
      Setup dialog is closed and reopened so it cannot overwrite the values.
    Omitted arguments are left unchanged. Returns ``previous`` and ``current`` values; raises
    when any requested value does not read back.
    """
    sys_unit = None
    if units is not None:
        sys_unit = _SYSTEM_UNITS.get(str(units).strip().lower())
        if not sys_unit:
            raise ValueError(f"Unknown system unit {units!r}; use one of mm, cm, m, km, in, ft, mi")
    display = None
    if display_units is not None:
        display = _DISPLAY_UNITS.get(str(display_units).strip().lower())
        if not display:
            raise ValueError(f"Unknown display unit {display_units!r}; use generic, mm, cm, m, km, in, ft, "
                             "frac_in, frac_ft, ft_frac_in or ft_dec_in")
    fps_i = None
    if fps is not None:
        f = float(fps)
        if not math.isfinite(f) or f != int(f) or not 1 <= f <= 1000:
            raise ValueError("fps must be a whole number between 1 and 1000 (frameRate is an integer)")
        fps_i = int(f)
    rng = None
    if frame_range is not None:
        rng = _two_ints(frame_range, "frame_range")
        if rng[1] <= rng[0]:
            raise ValueError("frame_range end must be greater than start")
    size = None
    if render_size is not None:
        size = _two_ints(render_size, "render_size")
        if size[0] < 1 or size[1] < 1 or size[0] > 32768 or size[1] > 32768:
            raise ValueError("render_size must be between 1 and 32768 pixels")
    aspect = None
    if pixel_aspect is not None:
        aspect = float(pixel_aspect)
        if not math.isfinite(aspect) or aspect <= 0:
            raise ValueError("pixel_aspect must be a positive number")
    if all(v is None for v in (sys_unit, display, fps_i, rng, size, aspect)):
        raise ValueError("Nothing to set: pass at least one of units, display_units, frame_range, "
                         "fps, render_size, pixel_aspect")

    body = build_setup_body(system_units=sys_unit, display=display, fps=fps_i, frame_range=rng,
                            render_size=size, pixel_aspect=aspect)
    script = _SETUP_TEMPLATE.replace("@BODY@", body)
    response = client.send_command(script)
    raw = response.get("result", "")
    try:
        data = _json.loads(raw)
    except ValueError as exc:
        raise RuntimeError(f"3ds Max returned non-JSON output: {str(raw)[:400]}") from exc
    previous = data.get("previous") or {}
    current = data.get("current") or {}
    if data.get("error"):
        raise RuntimeError(f"scene_setup failed in 3ds Max: {data['error']}; previous={_json.dumps(previous)} "
                           f"current={_json.dumps(current)}")

    mismatches: list[str] = []

    def expect(key: str, wanted: Any) -> None:
        got = current.get(key)
        if isinstance(wanted, float) or isinstance(got, float):
            ok = got is not None and abs(float(got) - float(wanted)) <= 1e-4 * max(1.0, abs(float(wanted)))
        else:
            ok = str(got).lower() == str(wanted).lower()
        if not ok:
            mismatches.append(f"{key}: wanted {wanted!r}, reads back {got!r}")

    if sys_unit:
        expect("units", sys_unit)
    if display:
        expect("display_type", display[0])
        if display[0] == "metric" and display[1]:
            expect("metric_type", display[1])
        elif display[0] == "us" and display[1]:
            expect("us_type", display[1])
    if fps_i is not None:
        expect("fps", fps_i)
    if rng is not None:
        expect("frame_start", float(rng[0]))
        expect("frame_end", float(rng[1]))
    if size is not None:
        expect("render_width", size[0])
        expect("render_height", size[1])
    if aspect is not None:
        expect("pixel_aspect", aspect)
    if mismatches:
        raise RuntimeError("scene_setup read-back mismatch: " + "; ".join(mismatches)
                           + f"; previous={_json.dumps(previous)}")

    changed = sorted(k for k in current if current.get(k) != previous.get(k))
    result: dict[str, Any] = {"previous": previous, "current": current, "changed": changed}
    if sys_unit and previous.get("units") != current.get("units"):
        result["warnings"] = [
            "System units changed without rescaling objects: existing geometry keeps its numeric size"
        ]
    return result
