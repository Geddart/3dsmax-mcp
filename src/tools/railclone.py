"""RailClone Pro tools for parametric modeling along splines in 3ds Max.

Provides 11 MCP tools for creating, inspecting, and configuring RailClone Pro
objects.  Style graphs cannot be built via MAXScript -- all tools follow a
library-first approach: load pre-built styles, assign spline paths, and tweak
exposed parameters.

Based on live introspection of RailClone_Pro in 3ds Max 2025 (see
docs/research/railclone_introspection.md).
"""

from __future__ import annotations

from ..server import mcp, client


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _safe_name(name: str) -> str:
    """Escape a user-provided name for embedding in MAXScript strings."""
    return name.replace("\\", "\\\\").replace('"', '\\"')


def _ms_path(path: str) -> str:
    """Convert a file/library path to MAXScript-safe forward-slash string."""
    return path.replace("\\", "/")


def _name_array(names: list[str]) -> str:
    """Build a MAXScript ``#(...)`` literal from a list of Python names."""
    return "#(" + ", ".join(f'"{_safe_name(n)}"' for n in names) + ")"


# Display mode string -> integer mapping
# Introspection confirms the property is `vmesh` (integer) on RailClone_Pro.
_DISPLAY_MODES: dict[str, int] = {
    "mesh": 0,
    "point_cloud": 1,
    "bbox": 2,
    "proxy": 3,
    "none": 4,
}

# Preset library paths for high-level convenience tools.
# These use the backslash-separated internal library path format that
# loadLibraryItemByPath expects.  Paths confirmed by introspection session.
_FENCE_STYLES: dict[str, str] = {
    "default": "\\\\RailClone Library\\\\Architecture\\\\Exterior\\\\Fences\\\\Metal Fence 1",
    "metal_fence_1": "\\\\RailClone Library\\\\Architecture\\\\Exterior\\\\Fences\\\\Metal Fence 1",
    "metal_fence_2": "\\\\RailClone Library\\\\Architecture\\\\Exterior\\\\Fences\\\\Metal Fence 2",
    "wood_fence": "\\\\RailClone Library\\\\Architecture\\\\Exterior\\\\Fences\\\\Wood Fence 1",
    "chain_link": "\\\\RailClone Library\\\\Architecture\\\\Exterior\\\\Fences\\\\Chain Link 1",
}

_RAILING_STYLES: dict[str, str] = {
    "default": "\\\\RailClone Library\\\\Architecture\\\\Exterior\\\\Railings\\\\Handrail 1",
    "handrail_1": "\\\\RailClone Library\\\\Architecture\\\\Exterior\\\\Railings\\\\Handrail 1",
    "handrail_2": "\\\\RailClone Library\\\\Architecture\\\\Exterior\\\\Railings\\\\Handrail 2",
    "glass_railing": "\\\\RailClone Library\\\\Architecture\\\\Exterior\\\\Railings\\\\Glass Railing 1",
    "balustrade": "\\\\RailClone Library\\\\Architecture\\\\Exterior\\\\Railings\\\\Balustrade 1",
}

_WALL_STYLES: dict[str, str] = {
    "default": "\\\\RailClone Library\\\\Architecture\\\\Exterior\\\\Walls\\\\Brick Wall 1",
    "brick_wall": "\\\\RailClone Library\\\\Architecture\\\\Exterior\\\\Walls\\\\Brick Wall 1",
    "stone_wall": "\\\\RailClone Library\\\\Architecture\\\\Exterior\\\\Walls\\\\Stone Wall 1",
    "concrete_wall": "\\\\RailClone Library\\\\Architecture\\\\Exterior\\\\Walls\\\\Concrete Wall 1",
}


def _rc_plugin_check() -> str:
    """Return MAXScript lines that verify RailClone Pro is installed.

    Sets local ``rcOK`` to ``true`` if available, or returns an error JSON
    string and halts execution.
    """
    return (
        'local rcOK = true\n'
        '    local rcTestClass = undefined\n'
        '    try (rcTestClass = RailClone_Pro) catch ()\n'
        '    if rcTestClass == undefined do (\n'
        '        rcOK = false\n'
        '    )\n'
        '    if not rcOK then (\n'
        '        "{\\"error\\":\\"RailClone Pro plugin is not installed or not loaded.\\"}" \n'
        '    ) else'
    )


# ---------------------------------------------------------------------------
# Tool 1: create_railclone
# ---------------------------------------------------------------------------

@mcp.tool()
def create_railclone(
    name: str = "RailClone001",
    splines: list[str] | None = None,
    icon_size: float = 30.0,
    seed: int = 12345,
) -> str:
    """Create a new RailClone Pro object and optionally assign spline paths.

    Creates an empty RailClone Pro object.  Use create_railclone_from_style
    to load a library style at creation time.  Spline paths are assigned to
    banode slots 1-8 (up to 8 base paths).

    Args:
        name: Name for the new RailClone object.
        splines: Optional list of scene spline names to assign as base paths
                 (index 1 = primary X path, index 2 = Y path for A2S styles).
        icon_size: Icon display size in scene units (default 30).
        seed: Random seed for the RailClone object.
    """
    safe = _safe_name(name)
    lines: list[str] = [
        _rc_plugin_check(),
        '(',
        'local rc = RailClone_Pro()',
        f'rc.name = "{safe}"',
        f'rc.iconsize = {icon_size:.4f}',
        f'rc.seed = {seed}',
    ]

    # Assign splines
    lines.append('local assignedSplines = #()')
    if splines:
        names_arr = _name_array(splines)
        lines.append(f'local splineNames = {names_arr}')
        lines.append('for i = 1 to splineNames.count do (')
        lines.append('    local sp = getNodeByName splineNames[i]')
        lines.append('    if sp != undefined do (')
        lines.append('        rc.banode[i] = sp')
        lines.append('        append assignedSplines splineNames[i]')
        lines.append('    )')
        lines.append(')')

    # Build JSON result
    lines.append('local json = "{\\"name\\":\\"" + rc.name + "\\""')
    lines.append('json += ",\\"class\\":\\"RailClone_Pro\\""')
    lines.append('json += ",\\"seed\\":" + (rc.seed as string)')
    lines.append('json += ",\\"icon_size\\":" + (rc.iconsize as string)')
    lines.append('json += ",\\"position\\":\\"" + (rc.pos as string) + "\\""')

    # Assigned splines list
    lines.append('local spJson = ""')
    lines.append('for i = 1 to assignedSplines.count do (')
    lines.append('    if i > 1 do spJson += ","')
    lines.append('    spJson += "\\"" + assignedSplines[i] + "\\""')
    lines.append(')')
    lines.append('json += ",\\"assigned_splines\\":[" + spJson + "]"')
    lines.append('json += "}"')
    lines.append('json')
    lines.append(')')

    ms = "(\n    " + "\n    ".join(lines) + "\n)"
    response = client.send_command(ms)
    return response.get("result", "")


# ---------------------------------------------------------------------------
# Tool 2: create_railclone_from_style
# ---------------------------------------------------------------------------

@mcp.tool()
def create_railclone_from_style(
    name: str = "RailClone001",
    library_path: str = "",
    splines: list[str] | None = None,
) -> str:
    """Create a RailClone Pro object and load a style from the RailClone library.

    The library_path uses the internal RailClone browser path format with
    backslash separators, for example:
    ``\\RailClone Library\\Architecture\\Exterior\\Fences\\Metal Fence 1``

    Returns 1 on successful load.  After loading, exposed parameters can be
    read with get_railclone_info and modified with set_railclone_parameters.

    Args:
        name: Name for the new RailClone object.
        library_path: Full library path to load (backslash-separated).
        splines: Optional spline names to assign as base paths after style load.
    """
    safe = _safe_name(name)
    safe_path = _safe_name(library_path)
    lines: list[str] = [
        _rc_plugin_check(),
        '(',
        f'local rc = RailClone_Pro(); rc.name = "{safe}"',
        f'local loadResult = rc.railclone.loadLibraryItemByPath "{safe_path}"',
        'if loadResult != 1 then (',
        '    delete rc',
        f'    "{{\\"error\\":\\"Failed to load style: {safe_path}. loadLibraryItemByPath returned \\" + (loadResult as string) + \\". Check the library path is correct.\\"}}"',
        ') else (',
    ]

    # Assign splines after style load
    lines.append('    local assignedSplines = #()')
    if splines:
        names_arr = _name_array(splines)
        lines.append(f'    local splineNames = {names_arr}')
        lines.append('    for i = 1 to splineNames.count do (')
        lines.append('        local sp = getNodeByName splineNames[i]')
        lines.append('        if sp != undefined do (')
        lines.append('            rc.banode[i] = sp')
        lines.append('            append assignedSplines splineNames[i]')
        lines.append('        )')
        lines.append('    )')

    # Gather exposed parameters
    lines.append('    local paramJson = ""')
    lines.append('    local pCount = rc.paname.count')
    lines.append('    for i = 1 to pCount do (')
    lines.append('        if i > 1 do paramJson += ","')
    lines.append('        local pName = rc.paname[i]')
    lines.append('        local pType = rc.patype[i]')
    lines.append('        local pTypeStr = case pType of (')
    lines.append('            0: "int"')
    lines.append('            1: "float"')
    lines.append('            3: "worldUnits"')
    lines.append('            default: ("type_" + (pType as string))')
    lines.append('        )')
    lines.append('        local pVal = case pType of (')
    lines.append('            0: (rc.paintval[i] as string)')
    lines.append('            1: (rc.pafloatval[i] as string)')
    lines.append('            3: (rc.paunitval[i] as string)')
    lines.append('            default: "N/A"')
    lines.append('        )')
    lines.append('        paramJson += "{\\"name\\":\\"" + pName + "\\",\\"type\\":\\"" + pTypeStr + "\\",\\"value\\":" + pVal + "}"')
    lines.append('    )')

    # Build JSON result
    lines.append('    local json = "{\\"name\\":\\"" + rc.name + "\\""')
    lines.append(f'    json += ",\\"library_path\\":\\"{safe_path}\\""')
    lines.append('    json += ",\\"load_result\\":1"')
    lines.append('    json += ",\\"exposed_params\\":[" + paramJson + "]"')

    # Style description
    lines.append('    local styleDesc = ""')
    lines.append('    try (styleDesc = rc.railclone.getStyleDesc()) catch ()')
    lines.append('    json += ",\\"style_description\\":\\"" + styleDesc + "\\""')

    # Assigned splines
    lines.append('    local spJson = ""')
    lines.append('    for i = 1 to assignedSplines.count do (')
    lines.append('        if i > 1 do spJson += ","')
    lines.append('        spJson += "\\"" + assignedSplines[i] + "\\""')
    lines.append('    )')
    lines.append('    json += ",\\"assigned_splines\\":[" + spJson + "]"')
    lines.append('    json += "}"')
    lines.append('    json')
    lines.append(')')
    lines.append(')')

    ms = "(\n    " + "\n    ".join(lines) + "\n)"
    response = client.send_command(ms)
    return response.get("result", "")


# ---------------------------------------------------------------------------
# Tool 3: get_railclone_info
# ---------------------------------------------------------------------------

@mcp.tool()
def get_railclone_info(
    name: str,
) -> str:
    """Get comprehensive information about an existing RailClone Pro object.

    Returns the object's style description, exposed parameters (names, types,
    current values), assigned base splines, segment count, and display state.
    Use this to discover what parameters are available before calling
    set_railclone_parameters.

    Args:
        name: Name of the RailClone object to inspect.
    """
    safe = _safe_name(name)
    lines: list[str] = [
        _rc_plugin_check(),
        '(',
        f'local rc = getNodeByName "{safe}"',
        'if rc == undefined then (',
        f'    "{{\\"error\\":\\"Object not found: {safe}\\"}}"',
        ') else if (classOf rc.baseObject) != RailClone_Pro then (',
        f'    "{{\\"error\\":\\"Object {safe} is not a RailClone Pro object (class: \\" + ((classOf rc.baseObject) as string) + \\")\\"}}"',
        ') else (',
    ]

    # Basic info
    lines.append('    local json = "{\\"name\\":\\"" + rc.name + "\\""')
    lines.append('    json += ",\\"class\\":\\"RailClone_Pro\\""')
    lines.append('    json += ",\\"position\\":\\"" + (rc.pos as string) + "\\""')

    # Style description
    lines.append('    local styleDesc = ""')
    lines.append('    try (styleDesc = rc.railclone.getStyleDesc()) catch ()')
    lines.append('    json += ",\\"style_description\\":\\"" + styleDesc + "\\""')

    # Display state
    lines.append('    local vmeshVal = try (rc.vmesh as string) catch("N/A")')
    lines.append('    local autoUpd = try (rc.autoupdate as string) catch("N/A")')
    lines.append('    local disabledVal = try (rc.disabled as string) catch("N/A")')
    lines.append('    local maxSegVal = try (rc.maxseg as string) catch("N/A")')
    lines.append('    json += ",\\"display\\":{\\"vmesh\\":" + vmeshVal + ",\\"autoupdate\\":" + autoUpd + ",\\"disabled\\":" + disabledVal + ",\\"maxseg\\":" + maxSegVal + "}"')

    # Seed and scale
    lines.append('    json += ",\\"seed\\":" + (rc.seed as string)')
    lines.append('    json += ",\\"gscale\\":" + (rc.gscale as string)')

    # Base splines (banode array)
    lines.append('    local baJson = ""')
    lines.append('    local baCount = rc.banode.count')
    lines.append('    for i = 1 to baCount do (')
    lines.append('        if i > 1 do baJson += ","')
    lines.append('        local baNode = rc.banode[i]')
    lines.append('        local baNodeName = if baNode != undefined then baNode.name else "null"')
    lines.append('        local baNameVal = if i <= rc.baname.count then rc.baname[i] else ""')
    lines.append('        local baTypeVal = if i <= rc.batype.count then (rc.batype[i] as string) else "N/A"')
    lines.append('        baJson += "{\\"index\\":" + (i as string) + ",\\"node\\":\\"" + baNodeName + "\\",\\"label\\":\\"" + baNameVal + "\\",\\"type\\":" + baTypeVal + "}"')
    lines.append('    )')
    lines.append('    json += ",\\"base_objects\\":[" + baJson + "]"')
    lines.append('    json += ",\\"base_object_count\\":" + (baCount as string)')

    # Exposed parameters
    lines.append('    local paramJson = ""')
    lines.append('    local pCount = rc.paname.count')
    lines.append('    for i = 1 to pCount do (')
    lines.append('        if i > 1 do paramJson += ","')
    lines.append('        local pName = rc.paname[i]')
    lines.append('        local pType = rc.patype[i]')
    lines.append('        local pTypeStr = case pType of (')
    lines.append('            0: "int"')
    lines.append('            1: "float"')
    lines.append('            3: "worldUnits"')
    lines.append('            default: ("type_" + (pType as string))')
    lines.append('        )')
    lines.append('        local pVal = case pType of (')
    lines.append('            0: (rc.paintval[i] as string)')
    lines.append('            1: (rc.pafloatval[i] as string)')
    lines.append('            3: (rc.paunitval[i] as string)')
    lines.append('            default: "0"')
    lines.append('        )')
    lines.append('        local hasLimits = if i <= rc.palimit.count then rc.palimit[i] else false')
    lines.append('        local limitsStr = ""')
    lines.append('        if hasLimits do (')
    lines.append('            local minVal = case pType of (')
    lines.append('                0: (rc.paintmin[i] as string)')
    lines.append('                1: (rc.pafloatmin[i] as string)')
    lines.append('                3: (rc.paunitmin[i] as string)')
    lines.append('                default: "0"')
    lines.append('            )')
    lines.append('            local maxVal = case pType of (')
    lines.append('                0: (rc.paintmax[i] as string)')
    lines.append('                1: (rc.pafloatmax[i] as string)')
    lines.append('                3: (rc.paunitmax[i] as string)')
    lines.append('                default: "0"')
    lines.append('            )')
    lines.append('            limitsStr = ",\\"min\\":" + minVal + ",\\"max\\":" + maxVal')
    lines.append('        )')
    lines.append('        paramJson += "{\\"name\\":\\"" + pName + "\\",\\"type\\":\\"" + pTypeStr + "\\",\\"value\\":" + pVal + limitsStr + "}"')
    lines.append('    )')
    lines.append('    json += ",\\"exposed_params\\":[" + paramJson + "]"')
    lines.append('    json += ",\\"exposed_param_count\\":" + (pCount as string)')

    # Segment count (read-only, from loaded style)
    lines.append('    local segCount = rc.sname.count')
    lines.append('    json += ",\\"segment_count\\":" + (segCount as string)')

    lines.append('    json += "}"')
    lines.append('    json')
    lines.append(')')
    lines.append(')')

    ms = "(\n    " + "\n    ".join(lines) + "\n)"
    response = client.send_command(ms)
    return response.get("result", "")


# ---------------------------------------------------------------------------
# Tool 4: set_railclone_paths
# ---------------------------------------------------------------------------

@mcp.tool()
def set_railclone_paths(
    name: str,
    splines: list[str],
) -> str:
    """Assign or reassign spline paths to an existing RailClone Pro object.

    Splines are assigned to banode slots starting at index 1 (primary X path).
    Up to 8 base paths can be assigned.  Splines that are not found in the
    scene are skipped with a warning in the result.

    Args:
        name: Name of the RailClone object.
        splines: List of scene spline names to assign as base paths.
    """
    safe = _safe_name(name)
    names_arr = _name_array(splines)
    lines: list[str] = [
        _rc_plugin_check(),
        '(',
        f'local rc = getNodeByName "{safe}"',
        'if rc == undefined then (',
        f'    "{{\\"error\\":\\"Object not found: {safe}\\"}}"',
        ') else if (classOf rc.baseObject) != RailClone_Pro then (',
        f'    "{{\\"error\\":\\"Object {safe} is not a RailClone Pro object.\\"}}"',
        ') else (',
        f'    local splineNames = {names_arr}',
        '    local assigned = #()',
        '    local notFound = #()',
        '    for i = 1 to splineNames.count do (',
        '        local sp = getNodeByName splineNames[i]',
        '        if sp != undefined then (',
        '            rc.banode[i] = sp',
        '            append assigned splineNames[i]',
        '        ) else (',
        '            append notFound splineNames[i]',
        '        )',
        '    )',
    ]

    # Build JSON result
    lines.append('    local json = "{\\"object\\":\\"" + rc.name + "\\""')
    lines.append('    local aJson = ""')
    lines.append('    for i = 1 to assigned.count do (')
    lines.append('        if i > 1 do aJson += ","')
    lines.append('        aJson += "\\"" + assigned[i] + "\\""')
    lines.append('    )')
    lines.append('    json += ",\\"assigned\\":[" + aJson + "]"')
    lines.append('    local nfJson = ""')
    lines.append('    for i = 1 to notFound.count do (')
    lines.append('        if i > 1 do nfJson += ","')
    lines.append('        nfJson += "\\"" + notFound[i] + "\\""')
    lines.append('    )')
    lines.append('    json += ",\\"not_found\\":[" + nfJson + "]"')
    lines.append('    json += ",\\"total_assigned\\":" + (assigned.count as string)')
    lines.append('    json += "}"')
    lines.append('    json')
    lines.append(')')
    lines.append(')')

    ms = "(\n    " + "\n    ".join(lines) + "\n)"
    response = client.send_command(ms)
    return response.get("result", "")


# ---------------------------------------------------------------------------
# Tool 5: set_railclone_parameters
# ---------------------------------------------------------------------------

@mcp.tool()
def set_railclone_parameters(
    name: str,
    parameters: dict,
) -> str:
    """Set exposed parameters on a RailClone Pro object by name.

    Only parameters exposed via Numeric nodes in the style graph can be set.
    Use get_railclone_info first to discover available parameter names and
    their types.

    Parameter types (from rc.patype):
      0 = int (written to rc.paintval)
      1 = float (written to rc.pafloatval)
      3 = worldUnits (written to rc.paunitval)

    Args:
        name: Name of the RailClone object.
        parameters: Dict of parameter_name -> value to set.
    """
    safe = _safe_name(name)
    lines: list[str] = [
        _rc_plugin_check(),
        '(',
        f'local rc = getNodeByName "{safe}"',
        'if rc == undefined then (',
        f'    "{{\\"error\\":\\"Object not found: {safe}\\"}}"',
        ') else if (classOf rc.baseObject) != RailClone_Pro then (',
        f'    "{{\\"error\\":\\"Object {safe} is not a RailClone Pro object.\\"}}"',
        ') else (',
        '    local results = #()',
        '    local notFoundParams = #()',
    ]

    # For each parameter, find by name in paname array and set
    for param_name, value in parameters.items():
        safe_param = _safe_name(param_name)
        # Convert Python value to MAXScript literal
        if isinstance(value, bool):
            ms_val = "true" if value else "false"
        elif isinstance(value, float):
            ms_val = f"{value:.6f}"
        elif isinstance(value, int):
            ms_val = str(value)
        else:
            ms_val = str(value)

        lines.append(f'    local found_{safe_param.replace(" ", "_")} = false')
        lines.append('    for i = 1 to rc.paname.count do (')
        lines.append(f'        if rc.paname[i] == "{safe_param}" do (')
        lines.append(f'            found_{safe_param.replace(" ", "_")} = true')
        lines.append('            local pType = rc.patype[i]')
        lines.append('            local oldVal = case pType of (')
        lines.append('                0: (rc.paintval[i] as string)')
        lines.append('                1: (rc.pafloatval[i] as string)')
        lines.append('                3: (rc.paunitval[i] as string)')
        lines.append('                default: "N/A"')
        lines.append('            )')
        lines.append('            case pType of (')
        lines.append(f'                0: rc.paintval[i] = {ms_val} as integer')
        lines.append(f'                1: rc.pafloatval[i] = {ms_val} as float')
        lines.append(f'                3: rc.paunitval[i] = {ms_val}')
        lines.append('            )')
        lines.append('            local newVal = case pType of (')
        lines.append('                0: (rc.paintval[i] as string)')
        lines.append('                1: (rc.pafloatval[i] as string)')
        lines.append('                3: (rc.paunitval[i] as string)')
        lines.append('                default: "N/A"')
        lines.append('            )')
        lines.append('            local pTypeStr = case pType of (')
        lines.append('                0: "int"')
        lines.append('                1: "float"')
        lines.append('                3: "worldUnits"')
        lines.append('                default: ("type_" + (pType as string))')
        lines.append('            )')
        lines.append(f'            append results ("\\"{safe_param}\\":{{\\"type\\":\\"" + pTypeStr + "\\",\\"old\\":" + oldVal + ",\\"new\\":" + newVal + "}}")')
        lines.append('        )')
        lines.append('    )')
        lines.append(f'    if not found_{safe_param.replace(" ", "_")} do (')
        lines.append(f'        append notFoundParams "{safe_param}"')
        lines.append('    )')

    # Build JSON result
    lines.append('    local json = "{\\"object\\":\\"" + rc.name + "\\""')
    lines.append('    local rJson = ""')
    lines.append('    for i = 1 to results.count do (')
    lines.append('        if i > 1 do rJson += ","')
    lines.append('        rJson += results[i]')
    lines.append('    )')
    lines.append('    json += ",\\"changes\\":{" + rJson + "}"')
    lines.append('    local nfJson = ""')
    lines.append('    for i = 1 to notFoundParams.count do (')
    lines.append('        if i > 1 do nfJson += ","')
    lines.append('        nfJson += "\\"" + notFoundParams[i] + "\\""')
    lines.append('    )')
    lines.append('    json += ",\\"not_found\\":[" + nfJson + "]"')
    lines.append('    json += "}"')
    lines.append('    json')
    lines.append(')')
    lines.append(')')

    ms = "(\n    " + "\n    ".join(lines) + "\n)"
    response = client.send_command(ms)
    return response.get("result", "")


# ---------------------------------------------------------------------------
# Tool 6: set_railclone_display
# ---------------------------------------------------------------------------

@mcp.tool()
def set_railclone_display(
    name: str,
    mode: str = "mesh",
) -> str:
    """Set the viewport display mode for a RailClone Pro object.

    Controls how the RailClone object is displayed in the viewport.

    Available modes:
      - "mesh"        (0) -- full mesh display
      - "point_cloud" (1) -- point cloud representation
      - "bbox"        (2) -- bounding box only
      - "proxy"       (3) -- proxy display
      - "none"        (4) -- no display

    Args:
        name: Name of the RailClone object.
        mode: Display mode string (mesh, point_cloud, bbox, proxy, none).
    """
    safe = _safe_name(name)
    mode_int = _DISPLAY_MODES.get(mode.lower(), 0)
    lines: list[str] = [
        _rc_plugin_check(),
        '(',
        f'local rc = getNodeByName "{safe}"',
        'if rc == undefined then (',
        f'    "{{\\"error\\":\\"Object not found: {safe}\\"}}"',
        ') else if (classOf rc.baseObject) != RailClone_Pro then (',
        f'    "{{\\"error\\":\\"Object {safe} is not a RailClone Pro object.\\"}}"',
        ') else (',
        f'    local oldMode = try (rc.vmesh) catch(-1)',
        f'    rc.vmesh = {mode_int}',
        f'    local newMode = rc.vmesh',
        '    local json = "{\\"object\\":\\"" + rc.name + "\\""',
        f'    json += ",\\"mode\\":\\"{mode.lower()}\\""',
        '    json += ",\\"vmesh_old\\":" + (oldMode as string)',
        '    json += ",\\"vmesh_new\\":" + (newMode as string)',
        '    json += "}"',
        '    json',
        ')',
        ')',
    ]

    ms = "(\n    " + "\n    ".join(lines) + "\n)"
    response = client.send_command(ms)
    return response.get("result", "")


# ---------------------------------------------------------------------------
# Tool 7: railclone_instantiate
# ---------------------------------------------------------------------------

@mcp.tool()
def railclone_instantiate(
    name: str,
    mode: int = 0,
    layer_name: str = "rc_instances",
    auto_delete: bool = True,
    separated_meshes: bool = True,
    force_instances: bool = False,
) -> str:
    """Convert a RailClone Pro object to real instanced geometry.

    Uses the global Instantiate interface to convert RailClone parametric
    geometry into real 3ds Max objects.  The original RailClone object is
    disabled after instantiation.

    Modes:
      - 0 = individual objects
      - 1 = grouped objects
      - 2 = placed on a named layer

    Args:
        name: Name of the RailClone object to instantiate.
        mode: Instantiation mode (0=individual, 1=grouped, 2=layer).
        layer_name: Target layer name (used when mode=2).
        auto_delete: Remove previous instances before creating new ones.
        separated_meshes: Generate distinct meshes for non-instanced segments.
        force_instances: Maximize instance generation.
    """
    safe = _safe_name(name)
    safe_layer = _safe_name(layer_name)
    ms_auto_del = "true" if auto_delete else "false"
    ms_sep = "true" if separated_meshes else "false"
    ms_force = "true" if force_instances else "false"
    # Instantiate also needs a disableAtEnd param (last bool)
    lines: list[str] = [
        _rc_plugin_check(),
        '(',
        f'local rc = getNodeByName "{safe}"',
        'if rc == undefined then (',
        f'    "{{\\"error\\":\\"Object not found: {safe}\\"}}"',
        ') else if (classOf rc.baseObject) != RailClone_Pro then (',
        f'    "{{\\"error\\":\\"Object {safe} is not a RailClone Pro object.\\"}}"',
        ') else (',
        '    select rc',
        f'    RailClone_Pro.global.Instantiate {mode} "{safe_layer}" {ms_auto_del} {ms_sep} {ms_force} true',
        '    local json = "{\\"object\\":\\"" + rc.name + "\\""',
        f'    json += ",\\"mode\\":{mode}"',
        f'    json += ",\\"layer\\":\\"{safe_layer}\\""',
        '    json += ",\\"instantiated\\":true"',
        '    json += "}"',
        '    json',
        ')',
        ')',
    ]

    ms = "(\n    " + "\n    ".join(lines) + "\n)"
    response = client.send_command(ms)
    return response.get("result", "")


# ---------------------------------------------------------------------------
# Tool 8: create_railclone_fence
# ---------------------------------------------------------------------------

@mcp.tool()
def create_railclone_fence(
    name: str = "Fence001",
    spline: str = "",
    style: str = "default",
) -> str:
    """Create a fence along a spline path using a RailClone library preset.

    Convenience tool that creates a RailClone object, loads a fence style
    from the library, and assigns the spline path in a single call.

    Available styles: default, metal_fence_1, metal_fence_2, wood_fence,
    chain_link.  Or provide a full library path starting with backslash.

    Args:
        name: Name for the fence RailClone object.
        spline: Name of the scene spline to use as the fence path.
        style: Preset style name or full library path.
    """
    safe = _safe_name(name)

    # Resolve style path
    if style.startswith("\\") or style.startswith("/"):
        style_path = _safe_name(style)
    else:
        style_path = _FENCE_STYLES.get(style.lower(), _FENCE_STYLES["default"])

    safe_spline = _safe_name(spline)
    lines: list[str] = [
        _rc_plugin_check(),
        '(',
        f'local rc = RailClone_Pro(); rc.name = "{safe}"',
        f'local loadResult = rc.railclone.loadLibraryItemByPath "{style_path}"',
        'if loadResult != 1 then (',
        '    delete rc',
        f'    "{{\\"error\\":\\"Failed to load fence style: {style_path}\\"}}"',
        ') else (',
    ]

    # Assign spline if provided
    if spline:
        lines.append(f'    local sp = getNodeByName "{safe_spline}"')
        lines.append('    local splineAssigned = false')
        lines.append('    if sp != undefined do (')
        lines.append('        rc.banode[1] = sp')
        lines.append('        splineAssigned = true')
        lines.append('    )')
    else:
        lines.append('    local splineAssigned = false')

    # Gather exposed parameters
    lines.append('    local paramJson = ""')
    lines.append('    for i = 1 to rc.paname.count do (')
    lines.append('        if i > 1 do paramJson += ","')
    lines.append('        local pName = rc.paname[i]')
    lines.append('        local pType = rc.patype[i]')
    lines.append('        local pVal = case pType of (')
    lines.append('            0: (rc.paintval[i] as string)')
    lines.append('            1: (rc.pafloatval[i] as string)')
    lines.append('            3: (rc.paunitval[i] as string)')
    lines.append('            default: "0"')
    lines.append('        )')
    lines.append('        paramJson += "{\\"name\\":\\"" + pName + "\\",\\"value\\":" + pVal + "}"')
    lines.append('    )')

    # Build JSON result
    lines.append('    local json = "{\\"name\\":\\"" + rc.name + "\\""')
    lines.append('    json += ",\\"type\\":\\"fence\\""')
    lines.append(f'    json += ",\\"style\\":\\"{style}\\""')
    lines.append(f'    json += ",\\"library_path\\":\\"{style_path}\\""')
    lines.append('    json += ",\\"spline_assigned\\":" + (splineAssigned as string)')
    lines.append('    json += ",\\"exposed_params\\":[" + paramJson + "]"')
    lines.append('    json += "}"')
    lines.append('    json')
    lines.append(')')
    lines.append(')')

    ms = "(\n    " + "\n    ".join(lines) + "\n)"
    response = client.send_command(ms)
    return response.get("result", "")


# ---------------------------------------------------------------------------
# Tool 9: create_railclone_railing
# ---------------------------------------------------------------------------

@mcp.tool()
def create_railclone_railing(
    name: str = "Railing001",
    spline: str = "",
    style: str = "default",
) -> str:
    """Create a railing along a spline path using a RailClone library preset.

    Convenience tool that creates a RailClone object, loads a railing style
    from the library, and assigns the spline path in a single call.

    Available styles: default, handrail_1, handrail_2, glass_railing,
    balustrade.  Or provide a full library path starting with backslash.

    Args:
        name: Name for the railing RailClone object.
        spline: Name of the scene spline to use as the railing path.
        style: Preset style name or full library path.
    """
    safe = _safe_name(name)

    if style.startswith("\\") or style.startswith("/"):
        style_path = _safe_name(style)
    else:
        style_path = _RAILING_STYLES.get(style.lower(), _RAILING_STYLES["default"])

    safe_spline = _safe_name(spline)
    lines: list[str] = [
        _rc_plugin_check(),
        '(',
        f'local rc = RailClone_Pro(); rc.name = "{safe}"',
        f'local loadResult = rc.railclone.loadLibraryItemByPath "{style_path}"',
        'if loadResult != 1 then (',
        '    delete rc',
        f'    "{{\\"error\\":\\"Failed to load railing style: {style_path}\\"}}"',
        ') else (',
    ]

    if spline:
        lines.append(f'    local sp = getNodeByName "{safe_spline}"')
        lines.append('    local splineAssigned = false')
        lines.append('    if sp != undefined do (')
        lines.append('        rc.banode[1] = sp')
        lines.append('        splineAssigned = true')
        lines.append('    )')
    else:
        lines.append('    local splineAssigned = false')

    lines.append('    local paramJson = ""')
    lines.append('    for i = 1 to rc.paname.count do (')
    lines.append('        if i > 1 do paramJson += ","')
    lines.append('        local pName = rc.paname[i]')
    lines.append('        local pType = rc.patype[i]')
    lines.append('        local pVal = case pType of (')
    lines.append('            0: (rc.paintval[i] as string)')
    lines.append('            1: (rc.pafloatval[i] as string)')
    lines.append('            3: (rc.paunitval[i] as string)')
    lines.append('            default: "0"')
    lines.append('        )')
    lines.append('        paramJson += "{\\"name\\":\\"" + pName + "\\",\\"value\\":" + pVal + "}"')
    lines.append('    )')

    lines.append('    local json = "{\\"name\\":\\"" + rc.name + "\\""')
    lines.append('    json += ",\\"type\\":\\"railing\\""')
    lines.append(f'    json += ",\\"style\\":\\"{style}\\""')
    lines.append(f'    json += ",\\"library_path\\":\\"{style_path}\\""')
    lines.append('    json += ",\\"spline_assigned\\":" + (splineAssigned as string)')
    lines.append('    json += ",\\"exposed_params\\":[" + paramJson + "]"')
    lines.append('    json += "}"')
    lines.append('    json')
    lines.append(')')
    lines.append(')')

    ms = "(\n    " + "\n    ".join(lines) + "\n)"
    response = client.send_command(ms)
    return response.get("result", "")


# ---------------------------------------------------------------------------
# Tool 10: create_railclone_wall
# ---------------------------------------------------------------------------

@mcp.tool()
def create_railclone_wall(
    name: str = "Wall001",
    spline: str = "",
    style: str = "default",
) -> str:
    """Create a wall along a spline path using a RailClone library preset.

    Convenience tool that creates a RailClone object, loads a wall style
    from the library, and assigns the spline path in a single call.

    Available styles: default, brick_wall, stone_wall, concrete_wall.
    Or provide a full library path starting with backslash.

    Args:
        name: Name for the wall RailClone object.
        spline: Name of the scene spline to use as the wall path.
        style: Preset style name or full library path.
    """
    safe = _safe_name(name)

    if style.startswith("\\") or style.startswith("/"):
        style_path = _safe_name(style)
    else:
        style_path = _WALL_STYLES.get(style.lower(), _WALL_STYLES["default"])

    safe_spline = _safe_name(spline)
    lines: list[str] = [
        _rc_plugin_check(),
        '(',
        f'local rc = RailClone_Pro(); rc.name = "{safe}"',
        f'local loadResult = rc.railclone.loadLibraryItemByPath "{style_path}"',
        'if loadResult != 1 then (',
        '    delete rc',
        f'    "{{\\"error\\":\\"Failed to load wall style: {style_path}\\"}}"',
        ') else (',
    ]

    if spline:
        lines.append(f'    local sp = getNodeByName "{safe_spline}"')
        lines.append('    local splineAssigned = false')
        lines.append('    if sp != undefined do (')
        lines.append('        rc.banode[1] = sp')
        lines.append('        splineAssigned = true')
        lines.append('    )')
    else:
        lines.append('    local splineAssigned = false')

    lines.append('    local paramJson = ""')
    lines.append('    for i = 1 to rc.paname.count do (')
    lines.append('        if i > 1 do paramJson += ","')
    lines.append('        local pName = rc.paname[i]')
    lines.append('        local pType = rc.patype[i]')
    lines.append('        local pVal = case pType of (')
    lines.append('            0: (rc.paintval[i] as string)')
    lines.append('            1: (rc.pafloatval[i] as string)')
    lines.append('            3: (rc.paunitval[i] as string)')
    lines.append('            default: "0"')
    lines.append('        )')
    lines.append('        paramJson += "{\\"name\\":\\"" + pName + "\\",\\"value\\":" + pVal + "}"')
    lines.append('    )')

    lines.append('    local json = "{\\"name\\":\\"" + rc.name + "\\""')
    lines.append('    json += ",\\"type\\":\\"wall\\""')
    lines.append(f'    json += ",\\"style\\":\\"{style}\\""')
    lines.append(f'    json += ",\\"library_path\\":\\"{style_path}\\""')
    lines.append('    json += ",\\"spline_assigned\\":" + (splineAssigned as string)')
    lines.append('    json += ",\\"exposed_params\\":[" + paramJson + "]"')
    lines.append('    json += "}"')
    lines.append('    json')
    lines.append(')')
    lines.append(')')

    ms = "(\n    " + "\n    ".join(lines) + "\n)"
    response = client.send_command(ms)
    return response.get("result", "")


# ---------------------------------------------------------------------------
# Tool 11: create_railclone_array
# ---------------------------------------------------------------------------

@mcp.tool()
def create_railclone_array(
    name: str = "RCArray001",
    spline: str = "",
    x_spacing: float = 100.0,
    y_spacing: float = 100.0,
) -> str:
    """Create a 2D array pattern using RailClone along a spline.

    Creates a RailClone object configured for evenly-spaced repetition.
    The spacing is set via the v1distance (X segment length) and gscale
    (global scale) properties.  For full 2D array control, load an A2S
    style via create_railclone_from_style and assign both X and Y splines.

    Note: Spacing properties depend on the loaded style's exposed parameters.
    This tool sets the v1distance legacy property and gscale as a baseline.
    For precise control, use set_railclone_parameters with the style's
    specific exposed parameter names.

    Args:
        name: Name for the RailClone array object.
        spline: Name of the scene spline to use as the base path.
        x_spacing: Spacing along the X/spline direction in scene units.
        y_spacing: Spacing for the Y direction (perpendicular) in scene units.
    """
    safe = _safe_name(name)
    safe_spline = _safe_name(spline)
    lines: list[str] = [
        _rc_plugin_check(),
        '(',
        f'local rc = RailClone_Pro(); rc.name = "{safe}"',
    ]

    # Assign spline
    if spline:
        lines.append(f'local sp = getNodeByName "{safe_spline}"')
        lines.append('local splineAssigned = false')
        lines.append('if sp != undefined do (')
        lines.append('    rc.banode[1] = sp')
        lines.append('    splineAssigned = true')
        lines.append(')')
    else:
        lines.append('local splineAssigned = false')

    # Set spacing properties (v1distance for legacy segment distance, gscale for global scale)
    # These are baseline properties; actual spacing depends on loaded style.
    lines.append(f'try (rc.v1distance = {x_spacing:.4f}) catch ()')
    lines.append(f'rc.gscale = 1.0')

    # Try to set Y/Z spacing if properties exist (style-dependent)
    lines.append(f'try (rc.v1yoffset = {y_spacing:.4f}) catch ()')

    # Also attempt to set any exposed parameters named "Spacing", "Distance", etc.
    lines.append('local spacingSet = #()')
    lines.append('for i = 1 to rc.paname.count do (')
    lines.append('    local pNameLower = toLower rc.paname[i]')
    lines.append('    if (findString pNameLower "spacing" != undefined) or (findString pNameLower "distance" != undefined) or (findString pNameLower "length" != undefined) do (')
    lines.append('        local pType = rc.patype[i]')
    lines.append('        case pType of (')
    lines.append(f'            0: rc.paintval[i] = {x_spacing:.0f} as integer')
    lines.append(f'            1: rc.pafloatval[i] = {x_spacing:.4f}')
    lines.append(f'            3: rc.paunitval[i] = {x_spacing:.4f}')
    lines.append('        )')
    lines.append('        append spacingSet rc.paname[i]')
    lines.append('    )')
    lines.append(')')

    # Build JSON result
    lines.append('local json = "{\\"name\\":\\"" + rc.name + "\\""')
    lines.append('json += ",\\"type\\":\\"array\\""')
    lines.append(f'json += ",\\"x_spacing\\":{x_spacing:.4f}"')
    lines.append(f'json += ",\\"y_spacing\\":{y_spacing:.4f}"')
    lines.append('json += ",\\"spline_assigned\\":" + (splineAssigned as string)')

    lines.append('local spJson = ""')
    lines.append('for i = 1 to spacingSet.count do (')
    lines.append('    if i > 1 do spJson += ","')
    lines.append('    spJson += "\\"" + spacingSet[i] + "\\""')
    lines.append(')')
    lines.append('json += ",\\"spacing_params_set\\":[" + spJson + "]"')

    lines.append('json += "}"')
    lines.append('json')
    lines.append(')')

    ms = "(\n    " + "\n    ".join(lines) + "\n)"
    response = client.send_command(ms)
    return response.get("result", "")
