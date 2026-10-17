"""Scene-linear float EXR renders that are NOT clamped and cover the full frame.

``render_scene`` saves Max's frame buffer through ``render outputFile:``. With
V-Ray (CPU or GPU) that buffer is not 32-bit by default (``use_32bit_buffer`` /
``output_force32bit_3dsmax_vfb`` are off), so an ``.exr`` written that way is
clamped at 1.0 (Kaschmir, 2026-10). This tool instead lets the renderer write
its own float image:

* V-Ray: the V-Ray raw image file (``output_saveRawFile`` +
  ``output_rawFileName``), half or full float (``output_rawExrUseHalf``),
  ``colorMapping_clampOutput`` off, colour mapping not baked
  (``colorMapping_adaptationOnly`` = 1 "None") unless asked, VFB colour
  corrections not baked. On V-Ray GPU the colour-mapping / raw-EXR settings
  live on the renderer's ``V_Ray_settings`` sub-object.
* Any other renderer: render into an HDR (float) bitmap and save it through
  Max's OpenEXR writer with ``fopenexr.setSaveRegion false``.

Every renderer property it touches is restored afterwards. Max renders the
full view (``renderType:#view``), but an active V-Ray VFB region still
crops the raw file (dataWindow = region) and its on/off state cannot be
queried from MAXScript (``vfbControl`` answers OK to any flag), so the tool
does not toggle it: it reads the header back and pads a cropped file to
``dataWindow == displayWindow`` in place (zeros outside, ``paddedFrom``). The
output path must pass :func:`maxmcp.path_policy.resolve_write_path` with the
open scene's folder as ``scene_dir``.
"""
from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path

from ..helpers.exr import ExrError, pad_to_display_window, read_header
from ..path_policy import PathNotAllowedError, resolve_write_path
from ..server import client, mcp
from ..tool_response import run_in_thread

_RESULT_PREFIX = "MCPEXR|"


def _ms_string(value: str) -> str:
    """A MAXScript string literal (forward slashes keep paths escape-free)."""
    return '"' + value.replace("\\", "/").replace('"', '\\"') + '"'


def _error(message: str, code: str = "BAD_PARAM", **extra: object) -> str:
    payload: dict[str, object] = {"error": message, "code": code}
    payload.update(extra)
    return json.dumps(payload)


def build_render_float_exr_maxscript(
    path: str,
    *,
    width: int = 0,
    height: int = 0,
    camera: str = "",
    half: bool = False,
    apply_color_mapping: bool = False,
    frame: int | None = None,
) -> str:
    """MAXScript that renders one full frame into ``path`` as a float EXR.

    Returns ``MCPEXR|OK|<renderer>|<method>|<prop=value;...>`` or
    ``MCPEXR|ERR|<message>``; every renderer property it sets is restored.
    """
    width_expr = str(int(width)) if width and width > 0 else "renderWidth"
    height_expr = str(int(height)) if height and height > 0 else "renderHeight"
    cam_clause = ""
    cam_check = ""
    if camera:
        cam_check = (
            f"local cam = getNodeByName {_ms_string(camera)}\n"
            f"if cam == undefined do throw (\"Camera not found: \" + {_ms_string(camera)})\n"
        )
        cam_clause = " camera:cam"
    frame_clause = f" frame:{int(frame)}" if frame is not None else ""
    half_value = "true" if half else "false"
    no_cm = "false" if apply_color_mapping else "true"
    out_path = _ms_string(path)
    render_args = (
        f"outputwidth:({width_expr}) outputheight:({height_expr}){cam_clause}{frame_clause} "
        "renderType:#view vfb:false"
    )
    return f"""(
local mcpSaved = #()
local mcpUsed = #()
fn mcpSetProp obj prop val saved used = (
  if obj != undefined and (isProperty obj prop) then (
    local before = getProperty obj prop
    -- Some flags are read-only when already on (V-Ray GPU output_enable): only write a change.
    if before != val do (
      append saved #(obj, prop, before)
      setProperty obj prop val
    )
    append used ((prop as string) + "=" + (val as string))
    true
  ) else false
)
local r = renderers.current
local rName = (classOf r) as string
local cmHost = if (isProperty r #V_Ray_settings) then r.V_Ray_settings else r
local isVRay = (isProperty cmHost #output_saveRawFile) and (isProperty cmHost #output_rawFileName)
local method = if isVRay then "vray_raw" else "max_hdr_bitmap"
local mcpErr = undefined
local bm = undefined
local exrRegion = undefined
try (
  {cam_check}if isVRay then (
    -- V-Ray GPU exposes output_* on the renderer as READ-ONLY mirrors of its
    -- V_Ray_settings sub-object; CPU V-Ray holds them itself (cmHost == r).
    mcpSetProp cmHost #output_on true mcpSaved mcpUsed
    mcpSetProp cmHost #output_saveRawFile true mcpSaved mcpUsed
    mcpSetProp cmHost #output_rawFileName {out_path} mcpSaved mcpUsed
    mcpSetProp cmHost #output_rawExrUseHalf {half_value} mcpSaved mcpUsed
    mcpSetProp cmHost #output_rawExrDeep false mcpSaved mcpUsed
    mcpSetProp cmHost #output_rawSaveColorCorrections false mcpSaved mcpUsed
    -- "Save separate render channels" would write output_splitfilename, a path
    -- the path policy never saw: off for this render (restored below).
    mcpSetProp cmHost #output_splitgbuffer false mcpSaved mcpUsed
    mcpSetProp cmHost #colorMapping_clampOutput false mcpSaved mcpUsed
    if {no_cm} do mcpSetProp cmHost #colorMapping_adaptationOnly 1 mcpSaved mcpUsed
    bm = render {render_args}
  ) else (
    bm = bitmap ({width_expr}) ({height_expr}) hdr:true
    render {render_args} to:bm
    exrRegion = fopenexr.getSaveRegion()
    fopenexr.setSaveRegion false
    append mcpUsed "fopenexr.saveRegion=false"
    bm.filename = {out_path}
    save bm
  )
) catch (mcpErr = getCurrentException())
for e in mcpSaved do try (setProperty e[1] e[2] e[3]) catch ()
if exrRegion != undefined do try (fopenexr.setSaveRegion exrRegion) catch ()
if bm != undefined do try (close bm) catch ()
if mcpErr != undefined then
  "{_RESULT_PREFIX}ERR|" + mcpErr
else (
  local s = "{_RESULT_PREFIX}OK|" + rName + "|" + method + "|"
  for i = 1 to mcpUsed.count do s += (if i > 1 then ";" else "") + mcpUsed[i]
  s
)
)"""


def _find_written(path: Path, started: float) -> Path | None:
    """The file the renderer wrote: ``path`` itself, or its frame-numbered sibling.

    Only ``<stem>.<digits><suffix>`` / ``<stem><digits><suffix>`` (V-Ray appends the
    frame, ``name.0000.exr``) qualify; ``shot_backup.exr`` next to ``shot.exr`` never does,
    so an unrelated recent file is neither reported as the render nor moved onto it.
    """
    if path.exists() and path.stat().st_mtime >= started - 1:
        return path
    frame_name = re.compile(re.escape(path.stem) + r"\.?\d+" + re.escape(path.suffix), re.IGNORECASE)
    candidates = [
        p for p in path.parent.iterdir()
        if frame_name.fullmatch(p.name) and p.is_file() and p.stat().st_mtime >= started - 1
    ]
    return max(candidates, key=lambda p: p.stat().st_mtime) if candidates else None


@mcp.tool()
@run_in_thread
def render_float_exr(
    output_path: str,
    width: int = 0,
    height: int = 0,
    camera: str = "",
    half: bool = False,
    apply_color_mapping: bool = False,
    frame: int | None = None,
    timeout: float = 600.0,
) -> str:
    """Render one full frame to a scene-linear, unclamped float OpenEXR.

    Use when: an EXR must keep values above 1.0 (comp, grading, lighting
    checks) — `render_scene`'s `outputFile` path clamps with V-Ray.
    V-Ray (CPU/GPU) writes its raw image file; other renderers save an HDR
    bitmap. The header is read back; a region-cropped file (V-Ray VFB region
    render) is padded to the full frame (zeros outside, `paddedFrom`), so
    `exr.fullFrame` (dataWindow == displayWindow) holds.
    width/height 0 = current render size. half=True writes 16-bit half
    float, else 32-bit float. apply_color_mapping=False keeps V-Ray colour
    mapping out of the file. output_path must be inside an allowed folder
    (scene folder, [safe_mode] allowed_dirs, %TEMP%/3dsmax-mcp).
    """
    if not str(output_path).lower().endswith(".exr"):
        return _error("output_path must end in .exr")
    scene_dir = client.send_command("maxFilePath").get("result", "") or None
    try:
        target = resolve_write_path(output_path, scene_dir=scene_dir)
    except PathNotAllowedError as exc:
        return _error(str(exc), code="SAFE_MODE")

    target.parent.mkdir(parents=True, exist_ok=True)
    # A previous file at the target is left alone until this render succeeds;
    # _find_written only accepts files written after `started`.
    started = time.time()
    script = build_render_float_exr_maxscript(
        str(target),
        width=width,
        height=height,
        camera=camera,
        half=half,
        apply_color_mapping=apply_color_mapping,
        frame=frame,
    )
    raw = str(client.send_command(script, timeout=timeout).get("result", ""))
    if not raw.startswith(_RESULT_PREFIX):
        return _error(f"Unexpected render result: {raw[:300]}")
    parts = raw[len(_RESULT_PREFIX):].split("|")
    if parts[0] != "OK":
        return _error("Render failed: " + "|".join(parts[1:]), code="BAD_PARAM")
    renderer, method = parts[1], parts[2]
    properties = [p for p in (parts[3] if len(parts) > 3 else "").split(";") if p]

    written = _find_written(target, started)
    result: dict[str, object] = {
        "renderer": renderer,
        "method": method,
        "requestedPath": str(target),
        "propertiesSet": properties,
        "half": half,
        "colorMappingApplied": apply_color_mapping,
    }
    warnings: list[str] = []
    if written is None:
        return _error(
            f"The render finished but no EXR was written at {target}",
            code="BAD_PARAM",
            renderer=renderer,
            method=method,
            propertiesSet=properties,
        )
    if written != target:
        # V-Ray appends the frame number to the raw file (name.0000.exr);
        # deliver exactly the path the caller asked for.
        os.replace(written, target)
        result["renamedFrom"] = str(written)
        written = target
    result["output"] = str(written)
    result["bytes"] = os.path.getsize(written)
    try:
        header = read_header(written)
        if not header.full_frame and not (header.tiled or header.multipart):
            # A V-Ray VFB region (or any crop) leaves dataWindow smaller than the
            # frame; comp expects the full frame, so pad with zeros in place.
            padded_from = pad_to_display_window(written)
            if padded_from is not None:
                result["paddedFrom"] = list(padded_from)
                warnings.append(
                    f"Only the region {list(padded_from)} was rendered (V-Ray VFB region render is on?); "
                    "the EXR was padded to the full frame with zeros outside it"
                )
                header = read_header(written)
                result["bytes"] = os.path.getsize(written)
    except (ExrError, OSError) as exc:
        warnings.append(f"Could not read the EXR header back: {exc}")
    else:
        result["exr"] = header.summary()
        if not header.full_frame:
            warnings.append(
                f"dataWindow {list(header.data_window)} != displayWindow {list(header.display_window)}"
            )
        integer_channels = [c.name for c in header.channels if c.pixel_type == "uint"]
        if integer_channels:
            warnings.append(f"Integer (not float) channels in the EXR: {integer_channels}")
        want = "half" if half else "float"
        other = sorted({c.pixel_type for c in header.channels if c.pixel_type not in (want, "uint")})
        if other:
            warnings.append(
                f"Requested {want} channels but the file holds {other} "
                "(Max's own EXR writer uses its configured main-layer format)"
            )
    if warnings:
        result["warnings"] = warnings
    return json.dumps(result)
