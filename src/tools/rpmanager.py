"""RPManager tools for 3ds Max.

Provides 15 MCP tools for managing RPManager render passes, visibility sets,
capture/state sets, material overrides, and per-pass scripting.

RPManager API notes (from live introspection of v7.8):
- RPMdata is a flat MAXScript struct (RmanagerDataStruct), NOT nested sub-structs
- Many functions require the RPManager UI to be open (RPMdata.RMopenFloater())
- Pass indices are 1-based
- Headless-safe: version(), GetPassOutputPath, Get/SetPassBeforeScript,
  Get/SetPassAfterScript, Get/SetPassTimeType, Get/SetPassRange,
  GetPassVisSetName, GetPassBGColor, SetPassColor
- UI-required: AddPass(), RMDeleteItem, duplicatePass(), GetPassChecked
"""

from __future__ import annotations

from ..server import mcp, client


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _safe_name(name: str) -> str:
    """Escape a user-provided string for embedding in MAXScript double-quotes."""
    return name.replace("\\", "\\\\").replace('"', '\\"')


def _safe_script(script: str) -> str:
    """Escape a script string for embedding in MAXScript.

    Handles backslashes, double-quotes, and newlines so the string survives
    being placed inside a MAXScript string literal.
    """
    return (
        script
        .replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\n", "\\n")
        .replace("\r", "")
    )


def _rpm_guard(inner: str) -> str:
    """Wrap MAXScript in an RPManager availability check."""
    return (
        "(\n"
        "    if RPMdata == undefined then (\n"
        '        "{\\"error\\": \\"RPManager is not installed or not loaded\\"}"\n'
        "    ) else (\n"
        f"        {inner}\n"
        "    )\n"
        ")"
    )


def _index_guard(inner: str) -> str:
    """Wrap MAXScript in an RPMdata existence check AND a pass-index range check.

    The inner script can reference ``idx`` (the validated 1-based index) and
    ``pc`` (the pass count).  The placeholder ``{IDX}`` in *inner* will be
    replaced by the caller with the actual index value.
    """
    return _rpm_guard(
        "local pc = RPMdata.getpasscount()\n"
        "        local idx = {IDX}\n"
        '        if idx < 1 or idx > pc then (\n'
        '            "{\\"error\\": \\"Pass index " + idx as string '
        '+ " out of range (1-" + pc as string + ")\\"}"\n'
        "        ) else (\n"
        f"            {inner}\n"
        "        )"
    )


# ---------------------------------------------------------------------------
# Tool 1: inspect_rpmanager
# ---------------------------------------------------------------------------

@mcp.tool()
def inspect_rpmanager() -> str:
    """Check if RPManager is available and return version and pass count.

    Use this first to verify RPManager is loaded before calling other
    RPManager tools.

    Returns:
        JSON with available (bool), version, passCount.
    """
    maxscript = (
        '(\n'
        '    if RPMdata == undefined then (\n'
        '        "{\\"available\\": false, \\"error\\": '
        '\\"RPManager is not installed or not loaded\\"}"\n'
        '    ) else (\n'
        '        local ver = try (RPMdata.version()) catch("unknown")\n'
        '        local pc = try (RPMdata.getpasscount()) catch(0)\n'
        '        local json = "{\\"available\\": true"\n'
        '        json += ", \\"version\\": \\"" + ver as string + "\\""\n'
        '        json += ", \\"passCount\\": " + pc as string\n'
        '        json += "}"\n'
        '        json\n'
        '    )\n'
        ')'
    )
    response = client.send_command(maxscript)
    return response.get("result", response)


# ---------------------------------------------------------------------------
# Tool 2: get_rpmanager_passes
# ---------------------------------------------------------------------------

@mcp.tool()
def get_rpmanager_passes() -> str:
    """List all RPManager render passes with name, camera, output path, frame range, and time type.

    Use this to see the full render pass setup before making changes.
    Each pass has a 1-based index -- use that index for get/set operations.

    Returns:
        JSON with passCount and array of passes, each containing:
        index, name, camera, outputPath, timeType, visSetName, bgColor.
    """
    maxscript = _rpm_guard(
        'local pc = RPMdata.getpasscount()\n'
        '        local json = "{\\"passCount\\": " + pc as string + ", \\"passes\\": ["\n'
        '        for i = 1 to pc do (\n'
        '            if i > 1 do json += ","\n'
        '            local pOut = try (RPMdata.GetPassOutputPath i) catch("")\n'
        '            local pTimeType = try (RPMdata.GetPassTimeType i) catch(0)\n'
        '            local pRange = try (RPMdata.GetPassRange i) catch(#(0,100,1))\n'
        '            local pVisSet = try (RPMdata.GetPassVisSetName i) catch("")\n'
        '            local pBG = try (RPMdata.GetPassBGColor i) catch(color 0 0 0)\n'
        '            local pCam = try (RPMdata.getpasscamera i) catch(undefined)\n'
        '            local camName = ""\n'
        '            if pCam != undefined do (\n'
        '                try (camName = pCam.name) catch (try (camName = pCam as string) catch())\n'
        '            )\n'
        '            local safeOut = substituteString (substituteString (pOut as string) "\\\\" "/") "\\"" "\\\\\\""\n'
        '            json += "{\\"index\\": " + i as string\n'
        '            json += ", \\"outputPath\\": \\"" + safeOut + "\\""\n'
        '            if camName != "" then\n'
        '                json += ", \\"camera\\": \\"" + camName + "\\""\n'
        '            else\n'
        '                json += ", \\"camera\\": null"\n'
        '            json += ", \\"timeType\\": " + (pTimeType as integer) as string\n'
        '            local rangeStart = try (pRange[1] as integer) catch(0)\n'
        '            local rangeEnd = try (pRange[2] as integer) catch(100)\n'
        '            local rangeNth = try (pRange[3] as integer) catch(1)\n'
        '            json += ", \\"frameRange\\": {\\"start\\": " + rangeStart as string\n'
        '            json += ", \\"end\\": " + rangeEnd as string\n'
        '            json += ", \\"nthFrame\\": " + rangeNth as string + "}"\n'
        '            json += ", \\"visSetName\\": \\"" + (pVisSet as string) + "\\""\n'
        '            json += "}"\n'
        '        )\n'
        '        json += "]}"\n'
        '        json'
    )
    response = client.send_command(maxscript)
    return response.get("result", response)


# ---------------------------------------------------------------------------
# Tool 3: get_rpmanager_pass_detail
# ---------------------------------------------------------------------------

@mcp.tool()
def get_rpmanager_pass_detail(pass_index: int) -> str:
    """Get detailed information for a specific RPManager pass.

    Returns all available pass properties: output path, camera, time type,
    frame range, before/after scripts, visibility set name, and background color.

    Args:
        pass_index: 1-based index of the pass (from get_rpmanager_passes).

    Returns:
        JSON with full pass details.
    """
    inner = (
        'local pOut = try (RPMdata.GetPassOutputPath idx) catch("")\n'
        '            local pTimeType = try (RPMdata.GetPassTimeType idx) catch(0)\n'
        '            local pRange = try (RPMdata.GetPassRange idx) catch(#(0,100,1))\n'
        '            local pBefore = try (RPMdata.GetPassBeforeScript idx) catch("")\n'
        '            local pAfter = try (RPMdata.GetPassAfterScript idx) catch("")\n'
        '            local pVisSet = try (RPMdata.GetPassVisSetName idx) catch("")\n'
        '            local pBG = try (RPMdata.GetPassBGColor idx) catch(color 0 0 0)\n'
        '            local pCam = try (RPMdata.getpasscamera idx) catch(undefined)\n'
        '            local camName = ""\n'
        '            if pCam != undefined do (\n'
        '                try (camName = pCam.name) catch (try (camName = pCam as string) catch())\n'
        '            )\n'
        '            local safeOut = substituteString (substituteString (pOut as string) "\\\\" "/") "\\"" "\\\\\\""\n'
        '            local safeBefore = substituteString (substituteString (pBefore as string) "\\\\" "\\\\\\\\") "\\"" "\\\\\\""\n'
        '            safeBefore = substituteString safeBefore "\\n" "\\\\n"\n'
        '            local safeAfter = substituteString (substituteString (pAfter as string) "\\\\" "\\\\\\\\") "\\"" "\\\\\\""\n'
        '            safeAfter = substituteString safeAfter "\\n" "\\\\n"\n'
        '            local json = "{\\"index\\": " + idx as string\n'
        '            if camName != "" then\n'
        '                json += ", \\"camera\\": \\"" + camName + "\\""\n'
        '            else\n'
        '                json += ", \\"camera\\": null"\n'
        '            json += ", \\"outputPath\\": \\"" + safeOut + "\\""\n'
        '            local rangeStart = try (pRange[1] as integer) catch(0)\n'
        '            local rangeEnd = try (pRange[2] as integer) catch(100)\n'
        '            local rangeNth = try (pRange[3] as integer) catch(1)\n'
        '            json += ", \\"timeType\\": " + (pTimeType as integer) as string\n'
        '            json += ", \\"frameRange\\": {\\"start\\": " + rangeStart as string\n'
        '            json += ", \\"end\\": " + rangeEnd as string\n'
        '            json += ", \\"nthFrame\\": " + rangeNth as string + "}"\n'
        '            json += ", \\"beforeScript\\": \\"" + safeBefore + "\\""\n'
        '            json += ", \\"afterScript\\": \\"" + safeAfter + "\\""\n'
        '            json += ", \\"visSetName\\": \\"" + (pVisSet as string) + "\\""\n'
        '            local bgR = try ((pBG.r as integer) as string) catch("0")\n'
        '            local bgG = try ((pBG.g as integer) as string) catch("0")\n'
        '            local bgB = try ((pBG.b as integer) as string) catch("0")\n'
        '            json += ", \\"bgColor\\": {\\"r\\": " + bgR + ", \\"g\\": " + bgG + ", \\"b\\": " + bgB + "}"\n'
        '            json += "}"\n'
        '            json'
    )
    ms = _index_guard(inner).replace("{IDX}", str(pass_index))
    response = client.send_command(ms)
    return response.get("result", response)


# ---------------------------------------------------------------------------
# Tool 4: set_rpmanager_pass_property
# ---------------------------------------------------------------------------

@mcp.tool()
def set_rpmanager_pass_property(
    pass_index: int,
    property: str,
    value: str = "",
    frame_start: int = 0,
    frame_end: int = 100,
    nth_frame: int = 1,
) -> str:
    """Set a property on an RPManager render pass.

    Args:
        pass_index: 1-based index of the pass.
        property: Property to set. One of:
            - "name": Pass display name (value = new name string).
            - "output": Render output path (value = file path).
            - "time_type": Time type integer (value = "0", "1", etc.).
            - "range": Frame range (uses frame_start, frame_end, nth_frame params).
            - "color": Background color (value = "R,G,B" 0-255).
        value: The new value as a string.
        frame_start: Start frame (only for property="range").
        frame_end: End frame (only for property="range").
        nth_frame: Nth frame (only for property="range").

    Returns:
        JSON with confirmation and old/new values.
    """
    safe_val = _safe_name(value)
    prop = property.lower().strip()

    if prop == "name":
        inner = (
            f'local oldVal = try (RPMdata.GetPassOutputPath idx; "ok") catch("?")\n'
            f'            RPMdata.SetPassName idx "{safe_val}"\n'
            f'            RPMdata.fRefresh()\n'
            f'            "{{\\\"set\\\":\\\"name\\\", \\\"index\\\":" + idx as string + ", \\\"value\\\":\\\"{safe_val}\\\"}}"'
        )
    elif prop == "output":
        safe_path = value.replace("\\", "/").replace('"', '\\"')
        inner = (
            f'local oldVal = try (RPMdata.GetPassOutputPath idx) catch("")\n'
            f'            local safeOld = substituteString (substituteString (oldVal as string) "\\\\" "/") "\\"" "\\\\\\""\n'
            f'            RPMdata.SetPassOutputPath idx "{safe_path}"\n'
            f'            RPMdata.fRefresh()\n'
            f'            local json = "{{\\\"set\\\":\\\"output\\\", \\\"index\\\":" + idx as string\n'
            f'            json += ", \\\"old\\\":\\\"" + safeOld + "\\\""\n'
            f'            json += ", \\\"new\\\":\\\"{safe_path}\\\"}}"\n'
            f'            json'
        )
    elif prop == "time_type":
        try:
            tt_int = int(value)
        except ValueError:
            tt_int = 0
        inner = (
            f'local oldVal = try (RPMdata.GetPassTimeType idx) catch(0)\n'
            f'            RPMdata.SetPassTimeType idx {tt_int}\n'
            f'            RPMdata.fRefresh()\n'
            f'            "{{\\\"set\\\":\\\"time_type\\\", \\\"index\\\":" + idx as string + ", \\\"old\\\":" + (oldVal as integer) as string + ", \\\"new\\\":{tt_int}}}"'
        )
    elif prop == "range":
        inner = (
            f'local oldRange = try (RPMdata.GetPassRange idx) catch(#(0,100,1))\n'
            f'            RPMdata.SetPassRange idx {frame_start} {frame_end} {nth_frame}\n'
            f'            RPMdata.fRefresh()\n'
            f'            local oldS = try (oldRange[1] as integer) catch(0)\n'
            f'            local oldE = try (oldRange[2] as integer) catch(100)\n'
            f'            local oldN = try (oldRange[3] as integer) catch(1)\n'
            f'            "{{\\\"set\\\":\\\"range\\\", \\\"index\\\":" + idx as string + ", \\\"old\\\":[" + oldS as string + "," + oldE as string + "," + oldN as string + "], \\\"new\\\":[{frame_start},{frame_end},{nth_frame}]}}"'
        )
    elif prop == "color":
        parts = [c.strip() for c in value.split(",")]
        if len(parts) != 3:
            return '{"error": "color value must be R,G,B (e.g. 255,0,0)"}'
        r, g, b = parts[0], parts[1], parts[2]
        inner = (
            f'local oldBG = try (RPMdata.GetPassBGColor idx) catch(color 0 0 0)\n'
            f'            RPMdata.SetPassColor idx (color {r} {g} {b})\n'
            f'            RPMdata.fRefresh()\n'
            f'            "{{\\\"set\\\":\\\"color\\\", \\\"index\\\":" + idx as string + ", \\\"new\\\":{{\\\"r\\\":{r}, \\\"g\\\":{g}, \\\"b\\\":{b}}}}}"'
        )
    else:
        return (
            '{"error": "Unknown property: ' + prop + '. '
            'Use: name, output, time_type, range, color"}'
        )

    ms = _index_guard(inner).replace("{IDX}", str(pass_index))
    response = client.send_command(ms)
    return response.get("result", response)


# ---------------------------------------------------------------------------
# Tool 5: create_rpmanager_pass
# ---------------------------------------------------------------------------

@mcp.tool()
def create_rpmanager_pass(name: str | None = None) -> str:
    """Create a new RPManager render pass.

    NOTE: This opens the RPManager UI temporarily because AddPass()
    requires the floater dialog to be open.  RPManager must have been
    opened manually by the user at least once in the current Max session
    to initialize its internal data structures; otherwise AddPass will
    fail.  If it fails, ask the user to open RPManager once from the
    3ds Max menu (Rendering > RPManager) and try again.

    Args:
        name: Optional name for the new pass.

    Returns:
        JSON with the new pass index and confirmation.
    """
    safe = _safe_name(name) if name else ""

    name_line = ""
    if safe:
        name_line = (
            f'\n        RPMdata.SetPassName newIdx "{safe}"'
        )

    maxscript = _rpm_guard(
        'RPMdata.RMopenFloater()\n'
        '        local oldCount = RPMdata.getpasscount()\n'
        '        RPMdata.AddPass()\n'
        '        RPMdata.fRefresh()\n'
        '        local newIdx = RPMdata.getpasscount()\n'
        '        if newIdx <= oldCount then (\n'
        '            "{\\"error\\": \\"AddPass did not create a new pass. '
        'Ensure RPManager UI is open and responsive.\\"}"\n'
        '        ) else ('
        + name_line +
        '\n'
        '            RPMdata.fRefresh()\n'
        '            local json = "{\\"created\\": true, \\"index\\": " + newIdx as string\n'
        '            json += ", \\"passCount\\": " + newIdx as string\n'
        + (f'            json += ", \\"name\\": \\"{safe}\\""\n' if safe else '')
        +
        '            json += "}"\n'
        '            json\n'
        '        )'
    )
    response = client.send_command(maxscript)
    return response.get("result", response)


# ---------------------------------------------------------------------------
# Tool 6: delete_rpmanager_pass
# ---------------------------------------------------------------------------

@mcp.tool()
def delete_rpmanager_pass(pass_index: int) -> str:
    """Delete an RPManager render pass.

    NOTE: This opens the RPManager UI temporarily because RMDeleteItem
    may require the floater dialog for proper cleanup.

    Args:
        pass_index: 1-based index of the pass to delete.

    Returns:
        JSON with deletion confirmation.
    """
    inner = (
        'RPMdata.RMopenFloater()\n'
        '            local ok = RPMdata.RMDeleteItem idx\n'
        '            RPMdata.fRefresh()\n'
        '            local newCount = RPMdata.getpasscount()\n'
        '            if ok then (\n'
        '                "{\\"deleted\\": true, \\"index\\": " + idx as string '
        '+ ", \\"remainingPasses\\": " + newCount as string + "}"\n'
        '            ) else (\n'
        '                "{\\"error\\": \\"RMDeleteItem returned false for index " '
        '+ idx as string + "\\"}"\n'
        '            )'
    )
    ms = _index_guard(inner).replace("{IDX}", str(pass_index))
    response = client.send_command(ms)
    return response.get("result", response)


# ---------------------------------------------------------------------------
# Tool 7: get_rpmanager_visibility_sets
# ---------------------------------------------------------------------------

@mcp.tool()
def get_rpmanager_visibility_sets(pass_index: int) -> str:
    """Get visibility set information for a specific render pass.

    RPManager visibility sets control which objects are visible in each
    render pass.  This returns the visibility set name assigned to the
    given pass.

    Args:
        pass_index: 1-based index of the pass.

    Returns:
        JSON with the pass index and its assigned visibility set name.
    """
    inner = (
        'local vsName = try (RPMdata.GetPassVisSetName idx) catch("")\n'
        '            "{\\"index\\": " + idx as string + ", \\"visSetName\\": \\"" + (vsName as string) + "\\"}"'
    )
    ms = _index_guard(inner).replace("{IDX}", str(pass_index))
    response = client.send_command(ms)
    return response.get("result", response)


# ---------------------------------------------------------------------------
# Tool 8: set_rpmanager_visibility
# ---------------------------------------------------------------------------

@mcp.tool()
def set_rpmanager_visibility(pass_index: int, vis_set_name: str) -> str:
    """Set the visibility set for a render pass.

    Assigns a named visibility set to control which objects are visible
    when this pass renders.

    Args:
        pass_index: 1-based index of the pass.
        vis_set_name: Name of the visibility set to assign.

    Returns:
        JSON with confirmation.
    """
    safe_vs = _safe_name(vis_set_name)
    inner = (
        f'local oldVS = try (RPMdata.GetPassVisSetName idx) catch("")\n'
        f'            try (RPMdata.writeVisSetData idx "{safe_vs}") catch(\n'
        f'                try (RPMdata.SetPassVisSetName idx "{safe_vs}") catch()\n'
        f'            )\n'
        f'            RPMdata.fRefresh()\n'
        f'            local newVS = try (RPMdata.GetPassVisSetName idx) catch("")\n'
        f'            "{{\\\"index\\\":" + idx as string + ", \\\"old\\\":\\\"" + (oldVS as string) + "\\\", \\\"new\\\":\\\"" + (newVS as string) + "\\\"}}"'
    )
    ms = _index_guard(inner).replace("{IDX}", str(pass_index))
    response = client.send_command(ms)
    return response.get("result", response)


# ---------------------------------------------------------------------------
# Tool 9: get_rpmanager_capture_sets
# ---------------------------------------------------------------------------

@mcp.tool()
def get_rpmanager_capture_sets() -> str:
    """Get state/capture set information from RPManager.

    Retrieves available state sets which store per-pass scene state
    overrides (camera, background, exposure, custom state sets).
    Uses RPMdata.getallstatesets() to enumerate available sets.

    Returns:
        JSON with state set information.
    """
    maxscript = _rpm_guard(
        'local stSets = try (RPMdata.getallstatesets()) catch(#())\n'
        '        local json = "{\\"stateSetCount\\": " + stSets.count as string + ", \\"stateSets\\": ["\n'
        '        for i = 1 to stSets.count do (\n'
        '            if i > 1 do json += ","\n'
        '            local setStr = try (stSets[i] as string) catch("unknown")\n'
        '            local safeSet = substituteString setStr "\\"" "\\\\\\""\n'
        '            json += "{\\"index\\": " + i as string + ", \\"name\\": \\"" + safeSet + "\\"}" \n'
        '        )\n'
        '        json += "]}"\n'
        '        json'
    )
    response = client.send_command(maxscript)
    return response.get("result", response)


# ---------------------------------------------------------------------------
# Tool 10: add_rpmanager_capture_set
# ---------------------------------------------------------------------------

@mcp.tool()
def add_rpmanager_capture_set(pass_index: int, capture_type: str) -> str:
    """Capture current scene state for a render pass.

    Captures the current scene state (camera, background, exposure, or
    custom state set) and stores it as a per-pass override.

    Args:
        pass_index: 1-based index of the pass.
        capture_type: What to capture. One of:
            - "camera": Capture current camera assignment.
            - "background": Capture current background/environment.
            - "exposure": Capture current exposure settings.
            - "state": Capture a scene state set.

    Returns:
        JSON with confirmation.
    """
    ct = capture_type.lower().strip()
    capture_map = {
        "camera": "captureCamera",
        "background": "captureBackground",
        "exposure": "captureExposure",
        "state": "captureStateSet",
    }

    if ct not in capture_map:
        return (
            '{"error": "Unknown capture_type: ' + ct + '. '
            'Use: camera, background, exposure, state"}'
        )

    fn_name = capture_map[ct]
    inner = (
        f'try (\n'
        f'                RPMdata.{fn_name} idx\n'
        f'                "{{\\\"captured\\\": true, \\\"index\\\":" + idx as string + ", \\\"type\\\":\\\"{ct}\\\"}}"\n'
        f'            ) catch (\n'
        f'                "{{\\\"error\\\":\\\"Failed to capture {ct}: " + (getCurrentException()) + "\\\"}}"\n'
        f'            )'
    )
    ms = _index_guard(inner).replace("{IDX}", str(pass_index))
    response = client.send_command(ms)
    return response.get("result", response)


# ---------------------------------------------------------------------------
# Tool 11: remove_rpmanager_capture_set
# ---------------------------------------------------------------------------

@mcp.tool()
def remove_rpmanager_capture_set(pass_index: int, capture_type: str) -> str:
    """Remove/restore a captured state from a render pass.

    Removes the per-pass override so the pass uses the scene default
    for the specified state type.

    Args:
        pass_index: 1-based index of the pass.
        capture_type: What to restore. One of:
            - "state": Restore a captured scene state set.

    Returns:
        JSON with confirmation.
    """
    ct = capture_type.lower().strip()
    restore_map = {
        "state": "restoreStateSet",
    }

    if ct not in restore_map:
        return (
            '{"error": "Unknown capture_type for restore: ' + ct + '. '
            'Currently supported: state"}'
        )

    fn_name = restore_map[ct]
    inner = (
        f'try (\n'
        f'                RPMdata.{fn_name} idx\n'
        f'                "{{\\\"restored\\\": true, \\\"index\\\":" + idx as string + ", \\\"type\\\":\\\"{ct}\\\"}}"\n'
        f'            ) catch (\n'
        f'                "{{\\\"error\\\":\\\"Failed to restore {ct}: " + (getCurrentException()) + "\\\"}}"\n'
        f'            )'
    )
    ms = _index_guard(inner).replace("{IDX}", str(pass_index))
    response = client.send_command(ms)
    return response.get("result", response)


# ---------------------------------------------------------------------------
# Tool 12: set_rpmanager_material_override
# ---------------------------------------------------------------------------

@mcp.tool()
def set_rpmanager_material_override(
    pass_index: int,
    material_name: str | None = None,
) -> str:
    """Set or clear a material override for a render pass.

    When a material override is set, all objects in the pass render with
    the specified material instead of their assigned materials.  Pass
    material_name=None or "" to clear the override.

    Uses RPMdata.setPostMaterial for assignment and RPMdata.getPreMaterial
    to retrieve the current override.

    Args:
        pass_index: 1-based index of the pass.
        material_name: Scene material name to use as override, or None/"" to clear.

    Returns:
        JSON with confirmation.
    """
    if material_name:
        safe_mat = _safe_name(material_name)
        inner = (
            f'local mat = undefined\n'
            f'            for m in sceneMaterials where m.name == "{safe_mat}" do (mat = m; exit)\n'
            f'            if mat == undefined do (\n'
            f'                for m in meditMaterials where m.name == "{safe_mat}" do (mat = m; exit)\n'
            f'            )\n'
            f'            if mat == undefined then (\n'
            f'                "{{\\\"error\\\": \\\"Material \'{safe_mat}\' not found in scene or material editor\\\"}}"\n'
            f'            ) else (\n'
            f'                try (\n'
            f'                    RPMdata.setPostMaterial idx mat\n'
            f'                    RPMdata.fRefresh()\n'
            f'                    "{{\\\"set\\\": true, \\\"index\\\":" + idx as string + ", \\\"material\\\":\\\"{safe_mat}\\\"}}"\n'
            f'                ) catch (\n'
            f'                    "{{\\\"error\\\":\\\"Failed to set material override: " + (getCurrentException()) + "\\\"}}"\n'
            f'                )\n'
            f'            )'
        )
    else:
        inner = (
            'try (\n'
            '                RPMdata.setPostMaterial idx undefined\n'
            '                RPMdata.fRefresh()\n'
            '                "{\\"cleared\\": true, \\"index\\":" + idx as string + "}"\n'
            '            ) catch (\n'
            '                "{\\"error\\":\\"Failed to clear material override: " + (getCurrentException()) + "\\"}" \n'
            '            )'
        )

    ms = _index_guard(inner).replace("{IDX}", str(pass_index))
    response = client.send_command(ms)
    return response.get("result", response)


# ---------------------------------------------------------------------------
# Tool 13: get_rpmanager_pass_scripts
# ---------------------------------------------------------------------------

@mcp.tool()
def get_rpmanager_pass_scripts(pass_index: int) -> str:
    """Get before and after scripts for a render pass.

    RPManager can run MAXScript before and after each pass renders.
    This retrieves both scripts for the given pass.

    Args:
        pass_index: 1-based index of the pass.

    Returns:
        JSON with beforeScript and afterScript strings.
    """
    inner = (
        'local pBefore = try (RPMdata.GetPassBeforeScript idx) catch("")\n'
        '            local pAfter = try (RPMdata.GetPassAfterScript idx) catch("")\n'
        '            local safeBefore = substituteString (substituteString (pBefore as string) "\\\\" "\\\\\\\\") "\\"" "\\\\\\""\n'
        '            safeBefore = substituteString safeBefore "\\n" "\\\\n"\n'
        '            local safeAfter = substituteString (substituteString (pAfter as string) "\\\\" "\\\\\\\\") "\\"" "\\\\\\""\n'
        '            safeAfter = substituteString safeAfter "\\n" "\\\\n"\n'
        '            local json = "{\\"index\\": " + idx as string\n'
        '            json += ", \\"beforeScript\\": \\"" + safeBefore + "\\""\n'
        '            json += ", \\"afterScript\\": \\"" + safeAfter + "\\""\n'
        '            json += "}"\n'
        '            json'
    )
    ms = _index_guard(inner).replace("{IDX}", str(pass_index))
    response = client.send_command(ms)
    return response.get("result", response)


# ---------------------------------------------------------------------------
# Tool 14: set_rpmanager_pass_script
# ---------------------------------------------------------------------------

@mcp.tool()
def set_rpmanager_pass_script(
    pass_index: int,
    script_type: str,
    script: str,
) -> str:
    """Set a before or after script for a render pass.

    RPManager can run MAXScript before rendering starts and after
    rendering completes for each pass.  This sets the script content.

    Args:
        pass_index: 1-based index of the pass.
        script_type: "before" or "after".
        script: The MAXScript code to set (can be multi-line).

    Returns:
        JSON with confirmation.
    """
    st = script_type.lower().strip()
    if st not in ("before", "after"):
        return '{"error": "script_type must be \\"before\\" or \\"after\\""}'

    safe_script = _safe_script(script)

    if st == "before":
        fn_set = "SetPassBeforeScript"
        fn_get = "GetPassBeforeScript"
    else:
        fn_set = "SetPassAfterScript"
        fn_get = "GetPassAfterScript"

    inner = (
        f'local oldScript = try (RPMdata.{fn_get} idx) catch("")\n'
        f'            RPMdata.{fn_set} idx "{safe_script}"\n'
        f'            RPMdata.fRefresh()\n'
        f'            "{{\\\"set\\\":\\\"{st}\\\", \\\"index\\\":" + idx as string + ", \\\"success\\\": true}}"'
    )
    ms = _index_guard(inner).replace("{IDX}", str(pass_index))
    response = client.send_command(ms)
    return response.get("result", response)


# ---------------------------------------------------------------------------
# Tool 15: batch_update_rpmanager_passes
# ---------------------------------------------------------------------------

@mcp.tool()
def batch_update_rpmanager_passes(
    pass_indices: list[int],
    properties: dict,
) -> str:
    """Batch update multiple render passes with the same property values.

    Applies a set of property changes to multiple passes at once.
    Useful for standardizing output paths, frame ranges, or time types
    across several passes.

    Args:
        pass_indices: List of 1-based pass indices to update.
        properties: Dictionary of property name to value. Supported keys:
            - "output": Render output path (str).
            - "time_type": Time type integer as string.
            - "range": Frame range as "start,end,nth" string (e.g. "0,100,1").
            - "color": Background color as "R,G,B" string.
            - "before_script": Before-render script (str).
            - "after_script": After-render script (str).

    Returns:
        JSON with per-pass results.
    """
    if not pass_indices:
        return '{"error": "pass_indices must not be empty"}'
    if not properties:
        return '{"error": "properties must not be empty"}'

    # Build MAXScript for each pass index
    set_lines: list[str] = []
    for prop_name, prop_val in properties.items():
        pn = prop_name.lower().strip()
        if pn == "output":
            safe_path = str(prop_val).replace("\\", "/").replace('"', '\\"')
            set_lines.append(
                f'RPMdata.SetPassOutputPath passIdx "{safe_path}"'
            )
        elif pn == "time_type":
            try:
                tt = int(prop_val)
            except (ValueError, TypeError):
                tt = 0
            set_lines.append(f'RPMdata.SetPassTimeType passIdx {tt}')
        elif pn == "range":
            parts = [p.strip() for p in str(prop_val).split(",")]
            if len(parts) == 3:
                set_lines.append(
                    f'RPMdata.SetPassRange passIdx {parts[0]} {parts[1]} {parts[2]}'
                )
        elif pn == "color":
            parts = [p.strip() for p in str(prop_val).split(",")]
            if len(parts) == 3:
                set_lines.append(
                    f'RPMdata.SetPassColor passIdx (color {parts[0]} {parts[1]} {parts[2]})'
                )
        elif pn == "before_script":
            safe_s = _safe_script(str(prop_val))
            set_lines.append(
                f'RPMdata.SetPassBeforeScript passIdx "{safe_s}"'
            )
        elif pn == "after_script":
            safe_s = _safe_script(str(prop_val))
            set_lines.append(
                f'RPMdata.SetPassAfterScript passIdx "{safe_s}"'
            )

    if not set_lines:
        return '{"error": "No valid properties provided. Use: output, time_type, range, color, before_script, after_script"}'

    # Build the pass index array as MAXScript literal
    idx_arr = "#(" + ", ".join(str(i) for i in pass_indices) + ")"
    set_block = "\n                ".join(set_lines)

    maxscript = _rpm_guard(
        f'local pc = RPMdata.getpasscount()\n'
        f'        local indices = {idx_arr}\n'
        f'        local json = "{{\\\"updated\\\": ["\n'
        f'        local first = true\n'
        f'        for passIdx in indices do (\n'
        f'            if passIdx >= 1 and passIdx <= pc then (\n'
        f'                try (\n'
        f'                    {set_block}\n'
        f'                    if not first do json += ","\n'
        f'                    first = false\n'
        f'                    json += "{{\\\"index\\\":" + passIdx as string + ", \\\"success\\\": true}}"\n'
        f'                ) catch (\n'
        f'                    if not first do json += ","\n'
        f'                    first = false\n'
        f'                    json += "{{\\\"index\\\":" + passIdx as string + ", \\\"error\\\":\\\"" + (getCurrentException()) + "\\\"}}\"\n'
        f'                )\n'
        f'            ) else (\n'
        f'                if not first do json += ","\n'
        f'                first = false\n'
        f'                json += "{{\\\"index\\\":" + passIdx as string + ", \\\"error\\\":\\\"out of range\\\"}}"\n'
        f'            )\n'
        f'        )\n'
        f'        RPMdata.fRefresh()\n'
        f'        json += "]}}" \n'
        f'        json'
    )
    response = client.send_command(maxscript)
    return response.get("result", response)
