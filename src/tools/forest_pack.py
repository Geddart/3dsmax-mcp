"""Forest Pack Pro tools for 3ds Max.

Dedicated tools for listing, inspecting, modifying, and configuring Forest Pack
scatter objects.  Based on live introspection of Forest_Pro in 3ds Max 2025
(341 properties confirmed).

Property name corrections (verified via introspection -- do NOT guess):
  - divers         NOT diversity
  - clusize        NOT clustsize
  - clurough       NOT clustrough
  - clunoise       NOT clustnoise
  - cluedge        NOT clustblur
  - animation      NOT animmode
  - animap         NOT animmap
  - animsoffset    NOT animoffset
  - iconsize       NOT iconSize  (lowercase)
  - applyscale     NOT applyScale (lowercase)
  - camlimit       NOT limitvisibility
  - cambho         NOT backoffset
  - camfar         NOT farclipDist
  - altmin/altmax  NOT altbottom/alttop
  - mathue         NOT hueshift
  - tintmode       NOT usetint
"""

from __future__ import annotations

from ..server import mcp, client


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _safe_name(name: str) -> str:
    return name.replace("\\", "\\\\").replace('"', '\\"')


def _name_array(names: list[str]) -> str:
    return "#(" + ", ".join(f'"{_safe_name(n)}"' for n in names) + ")"


def _float_array(values: list[float]) -> str:
    return "#(" + ", ".join(f"{float(v):.6f}" for v in values) + ")"


def _fp_resolve(name: str) -> str:
    """Return MAXScript lines that resolve a Forest_Pro node into ``fp`` and ``fpb``."""
    safe = _safe_name(name)
    return (
        f'local fp = getNodeByName "{safe}"\n'
        '    if fp == undefined then (\n'
        f'        "{{\\\"error\\\":\\\"Object not found: {safe}\\\"}}"\n'
        '    ) else if (classOf fp.baseObject) != Forest_Pro then (\n'
        f'        "{{\\\"error\\\":\\\"Object \'{safe}\' is not a Forest Pack object (class: " + ((classOf fp.baseObject) as string) + ")\\\"}}"\n'
        '    ) else (\n'
        '    local fpb = fp.baseObject'
    )


_FP_RESOLVE_END = "\n    )"


# ---------------------------------------------------------------------------
# Tool 1: list_forest_pack_objects
# ---------------------------------------------------------------------------

@mcp.tool()
def list_forest_pack_objects() -> str:
    """List all Forest Pack objects in the current 3ds Max scene.

    Returns JSON array with each object's name, surface count, geometry count,
    density, seed, area count, distribution mode, and enabled status.
    """
    maxscript = """(
    local forestClass = undefined
    try (forestClass = Forest_Pro) catch ()
    if forestClass == undefined then (
        "{\\"error\\":\\"Forest Pack is not installed (Forest_Pro unavailable).\\"}"
    ) else (
        local json = "["
        local first = true
        for obj in objects where (try ((classOf obj.baseObject) == Forest_Pro) catch false) do (
            if not first do json += ","
            first = false
            local fpb = obj.baseObject
            local surfCount = try (fpb.surflist.count as string) catch "0"
            local geomCount = try (fpb.cobjlist.count as string) catch "0"
            local dens = try (fpb.maxdensity as string) catch "0"
            local sd = try (fpb.seed as string) catch "0"
            local areaCount = try (fpb.arnamelist.count as string) catch "0"
            local dmode = try (fpb.distmode as string) catch "0"
            local dis = try (fpb.disabled as string) catch "false"
            json += "{\\"name\\":\\"" + obj.name + "\\""
            json += ",\\"surfaceCount\\":" + surfCount
            json += ",\\"geometryCount\\":" + geomCount
            json += ",\\"density\\":" + dens
            json += ",\\"seed\\":" + sd
            json += ",\\"areaCount\\":" + areaCount
            json += ",\\"distributionMode\\":" + dmode
            json += ",\\"disabled\\":" + dis
            json += "}"
        )
        json += "]"
        json
    )
)"""
    response = client.send_command(maxscript)
    return response.get("result", '{"error":"No response from 3ds Max"}')


# ---------------------------------------------------------------------------
# Tool 2: get_forest_pack_info
# ---------------------------------------------------------------------------

@mcp.tool()
def get_forest_pack_info(name: str) -> str:
    """Get comprehensive configuration of a Forest Pack object.

    Returns surfaces, source geometry with probabilities, areas, distribution
    settings, transform settings, surface constraints, camera/LOD, animation,
    and display modes in a single call.

    Args:
        name: The Forest Pack object name.
    """
    safe = _safe_name(name)
    maxscript = f"""(
    local fp = getNodeByName "{safe}"
    if fp == undefined then (
        "{{\\"error\\":\\"Object not found: {safe}\\"}}"
    ) else if (classOf fp.baseObject) != Forest_Pro then (
        "{{\\"error\\":\\"Object '{safe}' is not a Forest Pack object\\"}}"
    ) else (
        local fpb = fp.baseObject
        local json = "{{\\"name\\":\\"" + fp.name + "\\""

        -- Surfaces
        json += ",\\"surfaces\\":["
        local surfs = try (fpb.surflist) catch #()
        for i = 1 to surfs.count do (
            if i > 1 do json += ","
            local sn = if surfs[i] != undefined then surfs[i].name else "null"
            json += "\\"" + sn + "\\""
        )
        json += "]"

        -- Geometry sources
        json += ",\\"geometry\\":["
        local geomNodes = try (fpb.cobjlist) catch #()
        local geomNames = try (fpb.namelist) catch #()
        local geomProbs = try (fpb.problist) catch #()
        local geomTypes = try (fpb.geomlist) catch #()
        for i = 1 to geomNodes.count do (
            if i > 1 do json += ","
            local gn = if geomNodes[i] != undefined then geomNodes[i].name else "null"
            local gname = if i <= geomNames.count then geomNames[i] else gn
            local gprob = if i <= geomProbs.count then (geomProbs[i] as string) else "1.0"
            local gtype = if i <= geomTypes.count then (geomTypes[i] as string) else "2"
            json += "{{\\"node\\":\\"" + gn + "\\",\\"name\\":\\"" + gname + "\\",\\"probability\\":" + gprob + ",\\"type\\":" + gtype + "}}"
        )
        json += "]"

        -- Areas
        json += ",\\"areas\\":["
        local arNames = try (fpb.arnamelist) catch #()
        local arTypes = try (fpb.artypelist) catch #()
        local arIncExc = try (fpb.arincexclist) catch #()
        local arActive = try (fpb.pf_aractivelist) catch #()
        local arNodes = try (fpb.arnodelist) catch #()
        for i = 1 to arNames.count do (
            if i > 1 do json += ","
            local an = arNames[i]
            local atype = if i <= arTypes.count then (arTypes[i] as string) else "0"
            local ai = if i <= arIncExc.count then (arIncExc[i] as string) else "0"
            local aa = if i <= arActive.count then (arActive[i] as string) else "true"
            local anode = if i <= arNodes.count and arNodes[i] != undefined then arNodes[i].name else "null"
            json += "{{\\"name\\":\\"" + an + "\\",\\"type\\":" + atype + ",\\"includeExclude\\":" + ai + ",\\"active\\":" + aa + ",\\"node\\":\\"" + anode + "\\"}}"
        )
        json += "]"

        -- Distribution
        local hasDistMap = try (fpb.distmap != undefined) catch false
        json += ",\\"distribution\\":{{"
        json += "\\"density\\":" + (try (fpb.maxdensity as string) catch "0")
        json += ",\\"unitsX\\":" + (try (fpb.units_x as string) catch "0")
        json += ",\\"unitsY\\":" + (try (fpb.units_y as string) catch "0")
        json += ",\\"distMode\\":" + (try (fpb.distmode as string) catch "0")
        json += ",\\"hasDistributionMap\\":" + (hasDistMap as string)
        json += ",\\"divers\\":" + (try (fpb.divers as string) catch "0")
        json += ",\\"clusize\\":" + (try (fpb.clusize as string) catch "0")
        json += "}}"

        -- Transform
        json += ",\\"transform\\":{{"
        json += "\\"scaleEnabled\\":" + (try (fpb.applyscale as string) catch "false")
        json += ",\\"scaleLocked\\":" + (try (fpb.scalelock as string) catch "0")
        json += ",\\"scaleXMin\\":" + (try (fpb.scalexmin as string) catch "100")
        json += ",\\"scaleXMax\\":" + (try (fpb.scalexmax as string) catch "100")
        json += ",\\"scaleYMin\\":" + (try (fpb.scaleymin as string) catch "100")
        json += ",\\"scaleYMax\\":" + (try (fpb.scaleymax as string) catch "100")
        json += ",\\"scaleZMin\\":" + (try (fpb.scalezmin as string) catch "100")
        json += ",\\"scaleZMax\\":" + (try (fpb.scalezmax as string) catch "100")
        json += ",\\"rotationEnabled\\":" + (try (fpb.applyrotation as string) catch "false")
        json += ",\\"xRotMin\\":" + (try (fpb.xrotmin as string) catch "0")
        json += ",\\"xRotMax\\":" + (try (fpb.xrotmax as string) catch "0")
        json += ",\\"yRotMin\\":" + (try (fpb.yrotmin as string) catch "0")
        json += ",\\"yRotMax\\":" + (try (fpb.yrotmax as string) catch "0")
        json += ",\\"zRotMin\\":" + (try (fpb.zrotmin as string) catch "0")
        json += ",\\"zRotMax\\":" + (try (fpb.zrotmax as string) catch "0")
        json += ",\\"translationEnabled\\":" + (try (fpb.applytranslation as string) catch "false")
        json += ",\\"mirror\\":" + (try (fpb.mirror as string) catch "false")
        json += "}}"

        -- Surface settings
        json += ",\\"surface\\":{{"
        json += "\\"direction\\":" + (try (fpb.direction as string) catch "0")
        json += ",\\"altLimited\\":" + (try (fpb.altlimited as string) catch "false")
        json += ",\\"altMin\\":" + (try (fpb.altmin as string) catch "0")
        json += ",\\"altMax\\":" + (try (fpb.altmax as string) catch "0")
        json += ",\\"slopeLimited\\":" + (try (fpb.slopelimited as string) catch "false")
        json += ",\\"slopeMin\\":" + (try (fpb.slopemin as string) catch "0")
        json += ",\\"slopeMax\\":" + (try (fpb.slopemax as string) catch "90")
        json += "}}"

        -- Camera/LOD
        local camName = try (if fpb.camera != undefined then fpb.camera.name else "null") catch "null"
        json += ",\\"camera\\":{{"
        json += "\\"node\\":\\"" + camName + "\\""
        json += ",\\"camLimit\\":" + (try (fpb.camlimit as string) catch "false")
        json += ",\\"camNear\\":" + (try (fpb.camnear as string) catch "0")
        json += ",\\"camFar\\":" + (try (fpb.camfar as string) catch "0")
        json += ",\\"camLod\\":" + (try (fpb.camlod as string) catch "false")
        json += ",\\"camLodDist\\":" + (try (fpb.camloddist as string) catch "0")
        json += "}}"

        -- Animation
        json += ",\\"animation\\":{{"
        json += "\\"mode\\":" + (try (fpb.animation as string) catch "0")
        json += ",\\"samples\\":" + (try (fpb.animsamples as string) catch "1")
        json += ",\\"offset\\":\\"" + (try (fpb.animsoffset as string) catch "0f") + "\\""
        json += "}}"

        -- Display
        json += ",\\"display\\":{{"
        json += "\\"viewportMode\\":" + (try (fpb.vmesh as string) catch "0")
        json += ",\\"renderMode\\":" + (try (fpb.rmesh as string) catch "0")
        json += ",\\"iconSize\\":" + (try (fpb.iconsize as string) catch "0")
        json += "}}"

        -- General
        json += ",\\"general\\":{{"
        json += "\\"seed\\":" + (try (fpb.seed as string) catch "0")
        json += ",\\"disabled\\":" + (try (fpb.disabled as string) catch "false")
        json += "}}"

        json += "}}"
        json
    )
)"""
    response = client.send_command(maxscript)
    return response.get("result", '{"error":"No response from 3ds Max"}')


# ---------------------------------------------------------------------------
# Tool 3: modify_forest_pack
# ---------------------------------------------------------------------------

@mcp.tool()
def modify_forest_pack(
    name: str,
    properties: dict,
) -> str:
    """Set arbitrary properties on an existing Forest Pack object.

    Directly sets properties on the Forest_Pro baseObject.  Returns before/after
    values for each property changed.

    Common properties: maxdensity, seed, direction, iconsize, vmesh, rmesh,
    divers, clusize, collision, threshold, disabled.

    Args:
        name: The Forest Pack object name.
        properties: Property name to value mapping.  Values can be int, float,
                    bool, or string.
    """
    safe = _safe_name(name)
    lines: list[str] = [
        f'local fp = getNodeByName "{safe}"',
        'if fp == undefined then (',
        f'    "{{\\\"error\\\":\\\"Object not found: {safe}\\\"}}"\n',
        ') else if (classOf fp.baseObject) != Forest_Pro then (',
        f'    "{{\\\"error\\\":\\\"Object \'{safe}\' is not a Forest Pack object\\\"}}"\n',
        ') else (',
        '    local fpb = fp.baseObject',
        '    local json = "{\\"object\\":\\"" + fp.name + "\\",\\"changes\\":["',
    ]

    prop_items = list(properties.items())
    for i, (prop, val) in enumerate(prop_items):
        pfx = "" if i == 0 else ","
        # Format value for MAXScript
        if isinstance(val, bool):
            ms_val = "true" if val else "false"
        elif isinstance(val, float):
            ms_val = f"{val:.6f}"
        elif isinstance(val, int):
            ms_val = str(val)
        elif isinstance(val, str):
            ms_val = f'"{_safe_name(val)}"'
        else:
            ms_val = str(val)

        safe_prop = _safe_name(str(prop))
        lines.append(f'    local old_{i} = try ((getProperty fpb #{safe_prop}) as string) catch("N/A")')
        lines.append(f'    try (setProperty fpb #{safe_prop} {ms_val}) catch()')
        lines.append(f'    local new_{i} = try ((getProperty fpb #{safe_prop}) as string) catch("N/A")')
        lines.append(f'    json += "{pfx}{{\\"prop\\":\\"{safe_prop}\\",\\"old\\":\\"" + old_{i} + "\\",\\"new\\":\\"" + new_{i} + "\\"}}"')

    lines.append('    json += "]}"')
    lines.append('    json')
    lines.append(')')

    ms = "(\n    " + "\n    ".join(lines) + "\n)"
    response = client.send_command(ms)
    return response.get("result", '{"error":"No response from 3ds Max"}')


# ---------------------------------------------------------------------------
# Tool 4: set_forest_pack_surfaces
# ---------------------------------------------------------------------------

@mcp.tool()
def set_forest_pack_surfaces(
    name: str,
    surfaces: list[str],
) -> str:
    """Set surface objects for scattering on an existing Forest Pack object.

    Replaces the current surface list entirely.

    Args:
        name: The Forest Pack object name.
        surfaces: List of surface object names to scatter onto.
    """
    safe = _safe_name(name)
    surf_arr = _name_array(surfaces)
    maxscript = f"""(
    local fp = getNodeByName "{safe}"
    if fp == undefined then (
        "{{\\"error\\":\\"Object not found: {safe}\\"}}"
    ) else if (classOf fp.baseObject) != Forest_Pro then (
        "{{\\"error\\":\\"Object '{safe}' is not a Forest Pack object\\"}}"
    ) else (
        local fpb = fp.baseObject
        local surfNames = {surf_arr}
        local surfNodes = #()
        local missing = #()
        for n in surfNames do (
            local node = getNodeByName n
            if node != undefined then append surfNodes node
            else append missing n
        )
        if missing.count > 0 then (
            local ms = ""
            for i = 1 to missing.count do (
                if i > 1 do ms += ","
                ms += "\\"" + missing[i] + "\\""
            )
            "{{\\"error\\":\\"Missing surface objects\\",\\"missing\\":[" + ms + "]}}"
        ) else (
            fpb.surflist = surfNodes
            local count = fpb.surflist.count
            "{{\\"object\\":\\"" + fp.name + "\\",\\"surfaceCount\\":" + (count as string) + "}}"
        )
    )
)"""
    response = client.send_command(maxscript)
    return response.get("result", '{"error":"No response from 3ds Max"}')


# ---------------------------------------------------------------------------
# Tool 5: set_forest_pack_sources
# ---------------------------------------------------------------------------

@mcp.tool()
def set_forest_pack_sources(
    name: str,
    sources: list[str],
    probabilities: list[float] | None = None,
    source_width_cm: float = 5.0,
    source_height_cm: float = 5.0,
) -> str:
    """Set source geometry nodes for an existing Forest Pack object.

    Replaces the current source geometry list entirely.  All geometry arrays
    (cobjlist, namelist, problist, geomlist, widthlist, heightlist) are set
    together atomically.

    Args:
        name: The Forest Pack object name.
        sources: List of source geometry object names.
        probabilities: Optional per-source weights (must match sources length).
                       Defaults to equal weights.
        source_width_cm: Source width in centimeters.
        source_height_cm: Source height in centimeters.
    """
    if not sources:
        return '{"error":"sources must contain at least one object name"}'

    if probabilities is None:
        weights = [1.0] * len(sources)
    else:
        if len(probabilities) != len(sources):
            return f'{{"error":"probabilities length ({len(probabilities)}) must match sources length ({len(sources)})"}}'
        weights = [float(p) for p in probabilities]

    safe = _safe_name(name)
    src_arr = _name_array(sources)
    weight_arr = _float_array(weights)
    sw = max(0.001, float(source_width_cm))
    sh = max(0.001, float(source_height_cm))

    maxscript = f"""(
    local fp = getNodeByName "{safe}"
    if fp == undefined then (
        "{{\\"error\\":\\"Object not found: {safe}\\"}}"
    ) else if (classOf fp.baseObject) != Forest_Pro then (
        "{{\\"error\\":\\"Object '{safe}' is not a Forest Pack object\\"}}"
    ) else (
        local fpb = fp.baseObject
        local srcNames = {src_arr}
        local probValues = {weight_arr}
        local srcNodes = #()
        local missing = #()
        for n in srcNames do (
            local node = getNodeByName n
            if node != undefined then append srcNodes node
            else append missing n
        )
        if missing.count > 0 then (
            local ms = ""
            for i = 1 to missing.count do (
                if i > 1 do ms += ","
                ms += "\\"" + missing[i] + "\\""
            )
            "{{\\"error\\":\\"Missing source objects\\",\\"missing\\":[" + ms + "]}}"
        ) else (
            local geomTypes = for i = 1 to srcNodes.count collect 2
            local sourceWidthWU = units.decodeValue "{sw}cm"
            local sourceHeightWU = units.decodeValue "{sh}cm"
            local widths = for i = 1 to srcNodes.count collect sourceWidthWU
            local heights = for i = 1 to srcNodes.count collect sourceHeightWU

            fpb.cobjlist = srcNodes
            fpb.namelist = srcNames
            fpb.problist = probValues
            fpb.geomlist = geomTypes
            fpb.widthlist = widths
            fpb.heightlist = heights

            local count = fpb.cobjlist.count
            "{{\\"object\\":\\"" + fp.name + "\\",\\"geometryCount\\":" + (count as string) + "}}"
        )
    )
)"""
    response = client.send_command(maxscript)
    return response.get("result", '{"error":"No response from 3ds Max"}')


# ---------------------------------------------------------------------------
# Tool 6: add_forest_pack_area
# ---------------------------------------------------------------------------

@mcp.tool()
def add_forest_pack_area(
    name: str,
    spline_name: str | None = None,
    area_name: str = "New Area",
    area_type: int = 0,
    include_exclude: int = 0,
    projection: int = 2,
    active: bool = True,
) -> str:
    """Add an include/exclude area to a Forest Pack object.

    CRITICAL: All 7 core area arrays are read, appended to, and written back
    atomically to maintain synchronization.

    Args:
        name: The Forest Pack object name.
        spline_name: Object name of the spline/shape to use (required for type 0/1/2).
        area_name: Display name for the area.
        area_type: Area type: 0=Spline, 1=Object, 2=Forest, 3=Surface, 4=Paint.
        include_exclude: 0=include, 1=exclude.
        projection: Projection mode: 0=none, 1=XY, 2=surface.
        active: Whether this area is active.
    """
    safe = _safe_name(name)
    safe_area = _safe_name(area_name)
    atype = int(area_type)
    aincexc = int(include_exclude)
    aproj = int(projection)
    aactive = "true" if active else "false"

    spline_resolve = ""
    spline_append = "append nodes undefined"
    if spline_name:
        safe_spline = _safe_name(spline_name)
        spline_resolve = f"""
        local splineObj = getNodeByName "{safe_spline}"
        if splineObj == undefined then (
            "{{\\"error\\":\\"Spline object not found: {safe_spline}\\"}}"
        ) else ("""
        spline_append = "append nodes splineObj"

    maxscript = f"""(
    local fp = getNodeByName "{safe}"
    if fp == undefined then (
        "{{\\"error\\":\\"Object not found: {safe}\\"}}"
    ) else if (classOf fp.baseObject) != Forest_Pro then (
        "{{\\"error\\":\\"Object '{safe}' is not a Forest Pack object\\"}}"
    ) else (
        local fpb = fp.baseObject
        {spline_resolve}
        -- Read all 7 core area arrays
        local nodes = try (fpb.arnodelist) catch #()
        local names = try (fpb.arnamelist) catch #()
        local types = try (fpb.artypelist) catch #()
        local incexc = try (fpb.arincexclist) catch #()
        local proj = try (fpb.arprojectlist) catch #()
        local active = try (fpb.pf_aractivelist) catch #()
        local ids = try (fpb.aridlist) catch #()

        -- Compute next unique ID
        local nextId = 1
        for id in ids do (if id >= nextId do nextId = id + 1)

        -- Append new area to all arrays
        {spline_append}
        append names "{safe_area}"
        append types {atype}
        append incexc {aincexc}
        append proj {aproj}
        append active {aactive}
        append ids nextId

        -- Write all back atomically
        fpb.arnodelist = nodes
        fpb.arnamelist = names
        fpb.artypelist = types
        fpb.arincexclist = incexc
        fpb.arprojectlist = proj
        fpb.pf_aractivelist = active
        fpb.aridlist = ids

        local count = fpb.arnamelist.count
        "{{\\"object\\":\\"" + fp.name + "\\",\\"areaCount\\":" + (count as string) + ",\\"addedIndex\\":" + (count as string) + ",\\"areaName\\":\\"{safe_area}\\"}}"
        {')' if spline_name else ''}
    )
)"""
    response = client.send_command(maxscript)
    return response.get("result", '{"error":"No response from 3ds Max"}')


# ---------------------------------------------------------------------------
# Tool 7: remove_forest_pack_area
# ---------------------------------------------------------------------------

@mcp.tool()
def remove_forest_pack_area(
    name: str,
    area_index: int,
) -> str:
    """Remove an area from a Forest Pack object by 1-based index.

    CRITICAL: All 7 core area arrays are read, the item at area_index is
    deleted from each, and all are written back atomically.

    Args:
        name: The Forest Pack object name.
        area_index: 1-based index of the area to remove.
    """
    safe = _safe_name(name)
    idx = int(area_index)

    maxscript = f"""(
    local fp = getNodeByName "{safe}"
    if fp == undefined then (
        "{{\\"error\\":\\"Object not found: {safe}\\"}}"
    ) else if (classOf fp.baseObject) != Forest_Pro then (
        "{{\\"error\\":\\"Object '{safe}' is not a Forest Pack object\\"}}"
    ) else (
        local fpb = fp.baseObject
        local idx = {idx}

        -- Read all 7 core area arrays
        local nodes = try (fpb.arnodelist) catch #()
        local names = try (fpb.arnamelist) catch #()
        local types = try (fpb.artypelist) catch #()
        local incexc = try (fpb.arincexclist) catch #()
        local proj = try (fpb.arprojectlist) catch #()
        local active = try (fpb.pf_aractivelist) catch #()
        local ids = try (fpb.aridlist) catch #()

        if idx < 1 or idx > names.count then (
            "{{\\"error\\":\\"Area index " + (idx as string) + " out of range (1-" + (names.count as string) + ")\\"}}"
        ) else (
            local removedName = names[idx]

            -- Delete from all arrays at same index
            deleteItem nodes idx
            deleteItem names idx
            deleteItem types idx
            deleteItem incexc idx
            deleteItem proj idx
            deleteItem active idx
            deleteItem ids idx

            -- Write all back atomically
            fpb.arnodelist = nodes
            fpb.arnamelist = names
            fpb.artypelist = types
            fpb.arincexclist = incexc
            fpb.arprojectlist = proj
            fpb.pf_aractivelist = active
            fpb.aridlist = ids

            local count = fpb.arnamelist.count
            "{{\\"object\\":\\"" + fp.name + "\\",\\"removedArea\\":\\"" + removedName + "\\",\\"remainingCount\\":" + (count as string) + "}}"
        )
    )
)"""
    response = client.send_command(maxscript)
    return response.get("result", '{"error":"No response from 3ds Max"}')


# ---------------------------------------------------------------------------
# Tool 8: set_forest_pack_distribution_map
# ---------------------------------------------------------------------------

@mcp.tool()
def set_forest_pack_distribution_map(
    name: str,
    map_file: str | None = None,
    map_channel: int = 1,
    threshold: int = 50,
    density_units_x_cm: float | None = None,
    density_units_y_cm: float | None = None,
) -> str:
    """Set or clear the distribution/density map on a Forest Pack object.

    White areas scatter items, black areas do not.  Grayscale controls density.
    Provide map_file to assign a bitmap, or omit to clear the distribution map.

    Args:
        name: The Forest Pack object name.
        map_file: Path to a bitmap file.  If omitted, clears the distribution map.
        map_channel: UV map channel (default 1).
        threshold: Density threshold 0-100 (property: threshold).
        density_units_x_cm: Optional density tile X size in cm.
        density_units_y_cm: Optional density tile Y size in cm.
    """
    safe = _safe_name(name)

    map_lines = ""
    if map_file:
        safe_path = map_file.replace("\\", "/")
        map_lines = f"""
        fpb.distmap = Bitmaptexture filename:"{safe_path}"
        fpb.densityMap = true"""
    else:
        map_lines = """
        fpb.distmap = undefined
        fpb.densityMap = false"""

    unit_lines = ""
    if density_units_x_cm is not None:
        unit_lines += f'\n        fpb.units_x = units.decodeValue "{float(density_units_x_cm)}cm"'
    if density_units_y_cm is not None:
        unit_lines += f'\n        fpb.units_y = units.decodeValue "{float(density_units_y_cm)}cm"'

    maxscript = f"""(
    local fp = getNodeByName "{safe}"
    if fp == undefined then (
        "{{\\"error\\":\\"Object not found: {safe}\\"}}"
    ) else if (classOf fp.baseObject) != Forest_Pro then (
        "{{\\"error\\":\\"Object '{safe}' is not a Forest Pack object\\"}}"
    ) else (
        local fpb = fp.baseObject
        {map_lines}
        fpb.distmapchan = {int(map_channel)}
        fpb.threshold = {int(threshold)}
        {unit_lines}
        local hasMap = fpb.distmap != undefined
        "{{\\"object\\":\\"" + fp.name + "\\",\\"hasDistributionMap\\":" + (hasMap as string) + ",\\"threshold\\":" + (fpb.threshold as string) + ",\\"mapChannel\\":" + (fpb.distmapchan as string) + "}}"
    )
)"""
    response = client.send_command(maxscript)
    return response.get("result", '{"error":"No response from 3ds Max"}')


# ---------------------------------------------------------------------------
# Tool 9: set_forest_pack_cluster_settings
# ---------------------------------------------------------------------------

@mcp.tool()
def set_forest_pack_cluster_settings(
    name: str,
    enabled: bool = True,
    cluster_size_cm: float = 100.0,
    roughness: float = 50.0,
    noise: float = 0.0,
    edge: float = 0.0,
) -> str:
    """Configure cluster distribution on a Forest Pack object.

    Clusters group similar geometry items together, creating natural-looking
    patches (e.g. groups of same tree species).

    Args:
        name: The Forest Pack object name.
        enabled: Enable cluster mode (sets divers > 0).
        cluster_size_cm: Cluster size in centimeters (property: clusize).
        roughness: Cluster boundary roughness (property: clurough).
        noise: Random noise to break up clusters (property: clunoise).
        edge: Cluster edge softness (property: cluedge).
    """
    safe = _safe_name(name)
    divers_val = 50 if enabled else 0
    clu_cm = max(0.001, float(cluster_size_cm))

    maxscript = f"""(
    local fp = getNodeByName "{safe}"
    if fp == undefined then (
        "{{\\"error\\":\\"Object not found: {safe}\\"}}"
    ) else if (classOf fp.baseObject) != Forest_Pro then (
        "{{\\"error\\":\\"Object '{safe}' is not a Forest Pack object\\"}}"
    ) else (
        local fpb = fp.baseObject
        fpb.divers = {divers_val}
        fpb.clusize = units.decodeValue "{clu_cm}cm"
        fpb.clurough = {float(roughness):.6f}
        fpb.clunoise = {float(noise):.6f}
        fpb.cluedge = {float(edge):.6f}
        "{{\\"object\\":\\"" + fp.name + "\\",\\"divers\\":" + (fpb.divers as string) + ",\\"clusize\\":" + (fpb.clusize as string) + ",\\"clurough\\":" + (fpb.clurough as string) + ",\\"clunoise\\":" + (fpb.clunoise as string) + ",\\"cluedge\\":" + (fpb.cluedge as string) + "}}"
    )
)"""
    response = client.send_command(maxscript)
    return response.get("result", '{"error":"No response from 3ds Max"}')


# ---------------------------------------------------------------------------
# Tool 10: set_forest_pack_edge_settings
# ---------------------------------------------------------------------------

@mcp.tool()
def set_forest_pack_edge_settings(
    name: str,
    area_index: int | None = None,
    boundary_mode: int = 0,
    falloff_density: float = 0.0,
    falloff_scale: float = 0.0,
    falloff_invert: bool = False,
) -> str:
    """Configure edge/boundary behavior for areas on a Forest Pack object.

    Edge settings are per-area (stored in arboundchecklist, arflafdenslist,
    arflafscalist, arflinvlist arrays).  If area_index is given, only that
    area is updated; otherwise ALL areas are updated.

    Args:
        name: The Forest Pack object name.
        area_index: 1-based area index to update (None = update all areas).
        boundary_mode: 0=Point, 1=Size, 2=Edge.
        falloff_density: Density falloff at boundaries (0=none).
        falloff_scale: Scale falloff at boundaries (0=none).
        falloff_invert: Invert falloff direction.
    """
    safe = _safe_name(name)
    bmode = int(boundary_mode)
    fdensity = float(falloff_density)
    fscale = float(falloff_scale)
    finvert = "true" if falloff_invert else "false"

    if area_index is not None:
        idx = int(area_index)
        idx_check = f"""
        local idx = {idx}
        local bounds = try (fpb.arboundchecklist) catch #()
        if idx < 1 or idx > bounds.count then (
            "{{\\"error\\":\\"Area index " + (idx as string) + " out of range (1-" + (bounds.count as string) + ")\\"}}"
        ) else (
            local fdens = try (fpb.arflafdenslist) catch #()
            local fscal = try (fpb.arflafscalist) catch #()
            local finv = try (fpb.arflinvlist) catch #()
            bounds[idx] = {bmode}
            if idx <= fdens.count do fdens[idx] = {fdensity:.6f}
            if idx <= fscal.count do fscal[idx] = {fscale:.6f}
            if idx <= finv.count do finv[idx] = {finvert}
            fpb.arboundchecklist = bounds
            fpb.arflafdenslist = fdens
            fpb.arflafscalist = fscal
            fpb.arflinvlist = finv
            "{{\\"object\\":\\"" + fp.name + "\\",\\"updatedArea\\":" + (idx as string) + ",\\"boundaryMode\\":" + (bounds[idx] as string) + "}}"
        )"""
    else:
        idx_check = f"""
        local bounds = try (fpb.arboundchecklist) catch #()
        local fdens = try (fpb.arflafdenslist) catch #()
        local fscal = try (fpb.arflafscalist) catch #()
        local finv = try (fpb.arflinvlist) catch #()
        for i = 1 to bounds.count do (
            bounds[i] = {bmode}
            if i <= fdens.count do fdens[i] = {fdensity:.6f}
            if i <= fscal.count do fscal[i] = {fscale:.6f}
            if i <= finv.count do finv[i] = {finvert}
        )
        fpb.arboundchecklist = bounds
        fpb.arflafdenslist = fdens
        fpb.arflafscalist = fscal
        fpb.arflinvlist = finv
        "{{\\"object\\":\\"" + fp.name + "\\",\\"updatedAreas\\":" + (bounds.count as string) + ",\\"boundaryMode\\":{bmode}}}"
        """

    maxscript = f"""(
    local fp = getNodeByName "{safe}"
    if fp == undefined then (
        "{{\\"error\\":\\"Object not found: {safe}\\"}}"
    ) else if (classOf fp.baseObject) != Forest_Pro then (
        "{{\\"error\\":\\"Object '{safe}' is not a Forest Pack object\\"}}"
    ) else (
        local fpb = fp.baseObject
        {idx_check}
    )
)"""
    response = client.send_command(maxscript)
    return response.get("result", '{"error":"No response from 3ds Max"}')


# ---------------------------------------------------------------------------
# Tool 11: set_forest_pack_transform
# ---------------------------------------------------------------------------

@mcp.tool()
def set_forest_pack_transform(
    name: str,
    scale_enabled: bool | None = None,
    scale_lock: bool | None = None,
    scale_x_min: float | None = None,
    scale_x_max: float | None = None,
    scale_y_min: float | None = None,
    scale_y_max: float | None = None,
    scale_z_min: float | None = None,
    scale_z_max: float | None = None,
    rotation_enabled: bool | None = None,
    rotation_x_min: float | None = None,
    rotation_x_max: float | None = None,
    rotation_y_min: float | None = None,
    rotation_y_max: float | None = None,
    rotation_z_min: float | None = None,
    rotation_z_max: float | None = None,
    translation_enabled: bool | None = None,
    translation_x_min: float | None = None,
    translation_x_max: float | None = None,
    translation_y_min: float | None = None,
    translation_y_max: float | None = None,
    translation_z_min: float | None = None,
    translation_z_max: float | None = None,
    mirror: bool | None = None,
) -> str:
    """Configure transform randomization (scale, rotation, translation).

    Only provided (non-None) parameters are changed.  Scale values are
    percentages (100 = original size).  Rotation values are degrees.
    Translation values are percentages of item width (X/Y) or height (Z).

    Args:
        name: The Forest Pack object name.
        scale_enabled: Enable/disable scale variation.
        scale_lock: Lock all axes to same scale.
        scale_x_min: X-axis minimum scale percent.
        scale_x_max: X-axis maximum scale percent.
        scale_y_min: Y-axis minimum scale percent.
        scale_y_max: Y-axis maximum scale percent.
        scale_z_min: Z-axis minimum scale percent.
        scale_z_max: Z-axis maximum scale percent.
        rotation_enabled: Enable/disable rotation variation.
        rotation_x_min: X-axis minimum rotation degrees.
        rotation_x_max: X-axis maximum rotation degrees.
        rotation_y_min: Y-axis minimum rotation degrees.
        rotation_y_max: Y-axis maximum rotation degrees.
        rotation_z_min: Z-axis minimum rotation degrees.
        rotation_z_max: Z-axis maximum rotation degrees.
        translation_enabled: Enable/disable translation variation.
        translation_x_min: X translation min (percent of width).
        translation_x_max: X translation max (percent of width).
        translation_y_min: Y translation min (percent of width).
        translation_y_max: Y translation max (percent of width).
        translation_z_min: Z translation min (percent of height).
        translation_z_max: Z translation max (percent of height).
        mirror: Enable horizontal mirroring.
    """
    safe = _safe_name(name)

    # Build conditional property assignments
    prop_map: list[tuple[str, str]] = []

    def _add(fp_prop: str, val, as_bool: bool = False) -> None:
        if val is not None:
            if as_bool:
                ms_val = "true" if val else "false"
            elif isinstance(val, float):
                ms_val = f"{val:.6f}"
            else:
                ms_val = str(int(val))
            prop_map.append((fp_prop, ms_val))

    _add("applyscale", scale_enabled, as_bool=True)
    _add("scalelock", scale_lock, as_bool=True)
    _add("scalexmin", scale_x_min)
    _add("scalexmax", scale_x_max)
    _add("scaleymin", scale_y_min)
    _add("scaleymax", scale_y_max)
    _add("scalezmin", scale_z_min)
    _add("scalezmax", scale_z_max)
    _add("applyrotation", rotation_enabled, as_bool=True)
    _add("xrotmin", rotation_x_min)
    _add("xrotmax", rotation_x_max)
    _add("yrotmin", rotation_y_min)
    _add("yrotmax", rotation_y_max)
    _add("zrotmin", rotation_z_min)
    _add("zrotmax", rotation_z_max)
    _add("applytranslation", translation_enabled, as_bool=True)
    _add("transxmin", translation_x_min)
    _add("transxmax", translation_x_max)
    _add("transymin", translation_y_min)
    _add("transymax", translation_y_max)
    _add("transzmin", translation_z_min)
    _add("transzmax", translation_z_max)
    _add("mirror", mirror, as_bool=True)

    if not prop_map:
        return '{"error":"No transform properties provided"}'

    set_lines = "\n        ".join(f"fpb.{p} = {v}" for p, v in prop_map)
    changed_json = ",".join(f'\\"{p}\\"' for p, _ in prop_map)

    maxscript = f"""(
    local fp = getNodeByName "{safe}"
    if fp == undefined then (
        "{{\\"error\\":\\"Object not found: {safe}\\"}}"
    ) else if (classOf fp.baseObject) != Forest_Pro then (
        "{{\\"error\\":\\"Object '{safe}' is not a Forest Pack object\\"}}"
    ) else (
        local fpb = fp.baseObject
        {set_lines}
        "{{\\"object\\":\\"" + fp.name + "\\",\\"changed\\":[{changed_json}]}}"
    )
)"""
    response = client.send_command(maxscript)
    return response.get("result", '{"error":"No response from 3ds Max"}')


# ---------------------------------------------------------------------------
# Tool 12: set_forest_pack_color_variation
# ---------------------------------------------------------------------------

@mcp.tool()
def set_forest_pack_color_variation(
    name: str,
    tint_enabled: bool = True,
    tint_color_1: list[int] | None = None,
    tint_color_2: list[int] | None = None,
    tint_strength_min: int = 0,
    tint_strength_max: int = 30,
    tint_mode: int = 0,
    hue_shift: float = 0.0,
    saturation: float = 0.0,
    brightness: float = 0.0,
) -> str:
    """Configure color tint and variation on a Forest Pack object.

    Adds random per-item color tinting for natural variation.  Works with
    gradient mode (two colors blended randomly per item).

    Args:
        name: The Forest Pack object name.
        tint_enabled: Enable color tinting (tintmode > 0).
        tint_color_1: First gradient color as [R, G, B] (0-255).
        tint_color_2: Second gradient color as [R, G, B] (0-255).
        tint_strength_min: Minimum tint strength 0-100 (property: tintmin).
        tint_strength_max: Maximum tint strength 0-100 (property: tintmax).
        tint_mode: Tint variation mode integer (property: tintmixmode).
        hue_shift: Color correction hue shift (property: mathue).
        saturation: Saturation adjustment (property: matsaturation).
        brightness: Brightness adjustment (property: matbrightness).
    """
    safe = _safe_name(name)

    # tintmode: 0=off in most cases; we set to 1 to enable gradient
    tmode = 1 if tint_enabled else 0

    color1_line = ""
    if tint_color_1 and len(tint_color_1) >= 3:
        r, g, b = int(tint_color_1[0]), int(tint_color_1[1]), int(tint_color_1[2])
        color1_line = f"fpb.tintcolor1 = color {r} {g} {b}"

    color2_line = ""
    if tint_color_2 and len(tint_color_2) >= 3:
        r, g, b = int(tint_color_2[0]), int(tint_color_2[1]), int(tint_color_2[2])
        color2_line = f"fpb.tintcolor2 = color {r} {g} {b}"

    maxscript = f"""(
    local fp = getNodeByName "{safe}"
    if fp == undefined then (
        "{{\\"error\\":\\"Object not found: {safe}\\"}}"
    ) else if (classOf fp.baseObject) != Forest_Pro then (
        "{{\\"error\\":\\"Object '{safe}' is not a Forest Pack object\\"}}"
    ) else (
        local fpb = fp.baseObject
        fpb.tintmode = {tmode}
        fpb.tintmixmode = {int(tint_mode)}
        fpb.tintmin = {int(tint_strength_min)}
        fpb.tintmax = {int(tint_strength_max)}
        {color1_line}
        {color2_line}
        fpb.mathue = {float(hue_shift):.6f}
        fpb.matsaturation = {float(saturation):.6f}
        fpb.matbrightness = {float(brightness):.6f}
        "{{\\"object\\":\\"" + fp.name + "\\",\\"tintmode\\":" + (fpb.tintmode as string) + ",\\"tintmin\\":" + (fpb.tintmin as string) + ",\\"tintmax\\":" + (fpb.tintmax as string) + "}}"
    )
)"""
    response = client.send_command(maxscript)
    return response.get("result", '{"error":"No response from 3ds Max"}')


# ---------------------------------------------------------------------------
# Tool 13: set_forest_pack_surface_settings
# ---------------------------------------------------------------------------

@mcp.tool()
def set_forest_pack_surface_settings(
    name: str,
    direction: int | None = None,
    altitude_limited: bool | None = None,
    altitude_min_cm: float | None = None,
    altitude_max_cm: float | None = None,
    slope_limited: bool | None = None,
    slope_min_deg: float | None = None,
    slope_max_deg: float | None = None,
    uv_mode: bool | None = None,
    scale_to_slope: bool | None = None,
) -> str:
    """Configure surface alignment, altitude, and slope constraints.

    Controls how items align to the surface and restricts scatter to
    altitude/slope ranges on the terrain.

    Args:
        name: The Forest Pack object name.
        direction: Alignment: 0=follow surface normal, 1=follow world up.
                   Range roughly -100 to 100.
        altitude_limited: Enable altitude range restriction.
        altitude_min_cm: Minimum altitude in cm (property: altmin).
        altitude_max_cm: Maximum altitude in cm (property: altmax).
        slope_limited: Enable slope angle restriction.
        slope_min_deg: Minimum slope angle in degrees (0=horizontal).
        slope_max_deg: Maximum slope angle in degrees (90=vertical).
        uv_mode: Use UV coordinates for distribution (property: uvalign).
        scale_to_slope: Scale items proportionally to slope (property: scalelope).
    """
    safe = _safe_name(name)

    prop_lines: list[str] = []
    if direction is not None:
        prop_lines.append(f"fpb.direction = {int(direction)}")
    if altitude_limited is not None:
        prop_lines.append(f"fpb.altlimited = {'true' if altitude_limited else 'false'}")
    if altitude_min_cm is not None:
        prop_lines.append(f'fpb.altmin = units.decodeValue "{float(altitude_min_cm)}cm"')
    if altitude_max_cm is not None:
        prop_lines.append(f'fpb.altmax = units.decodeValue "{float(altitude_max_cm)}cm"')
    if slope_limited is not None:
        prop_lines.append(f"fpb.slopelimited = {'true' if slope_limited else 'false'}")
    if slope_min_deg is not None:
        prop_lines.append(f"fpb.slopemin = {float(slope_min_deg):.6f}")
    if slope_max_deg is not None:
        prop_lines.append(f"fpb.slopemax = {float(slope_max_deg):.6f}")
    if uv_mode is not None:
        prop_lines.append(f"fpb.uvalign = {'true' if uv_mode else 'false'}")
    if scale_to_slope is not None:
        prop_lines.append(f"fpb.scalelope = {'true' if scale_to_slope else 'false'}")

    if not prop_lines:
        return '{"error":"No surface settings provided"}'

    set_block = "\n        ".join(prop_lines)
    changed = ",".join(f'\\"{line.split("=")[0].strip().replace("fpb.", "")}\\"' for line in prop_lines)

    maxscript = f"""(
    local fp = getNodeByName "{safe}"
    if fp == undefined then (
        "{{\\"error\\":\\"Object not found: {safe}\\"}}"
    ) else if (classOf fp.baseObject) != Forest_Pro then (
        "{{\\"error\\":\\"Object '{safe}' is not a Forest Pack object\\"}}"
    ) else (
        local fpb = fp.baseObject
        {set_block}
        "{{\\"object\\":\\"" + fp.name + "\\",\\"changed\\":[{changed}]}}"
    )
)"""
    response = client.send_command(maxscript)
    return response.get("result", '{"error":"No response from 3ds Max"}')


# ---------------------------------------------------------------------------
# Tool 14: set_forest_pack_path_distribution
# ---------------------------------------------------------------------------

@mcp.tool()
def set_forest_pack_path_distribution(
    name: str,
    splines: list[str],
    spacing_cm: float = 100.0,
    follow_path_x: bool = True,
    follow_path_z: bool = False,
    offset_cm: float = 0.0,
    randomize_position_cm: float = 0.0,
    path_mode: int = 0,
) -> str:
    """Set a Forest Pack object to path/spline distribution mode.

    Distributes items at regular intervals along spline paths.  Useful for
    fences, hedges, street lights, and similar linear arrangements.

    Args:
        name: The Forest Pack object name.
        splines: List of spline object names to distribute along.
        spacing_cm: Distance between items in centimeters.
        follow_path_x: Rotate items to follow spline direction.
        follow_path_z: Align items vertically to spline.
        offset_cm: Perpendicular offset from spline in cm.
        randomize_position_cm: Random position variation in cm.
        path_mode: Path distribution sub-mode (0=spacing, 1=vertex).
    """
    safe = _safe_name(name)
    spline_arr = _name_array(splines)
    sp_cm = max(0.001, float(spacing_cm))
    off_cm = float(offset_cm)
    rand_cm = max(0.0, float(randomize_position_cm))

    maxscript = f"""(
    local fp = getNodeByName "{safe}"
    if fp == undefined then (
        "{{\\"error\\":\\"Object not found: {safe}\\"}}"
    ) else if (classOf fp.baseObject) != Forest_Pro then (
        "{{\\"error\\":\\"Object '{safe}' is not a Forest Pack object\\"}}"
    ) else (
        local fpb = fp.baseObject
        local splineNames = {spline_arr}
        local splineNodes = #()
        local missing = #()
        for n in splineNames do (
            local node = getNodeByName n
            if node != undefined then append splineNodes node
            else append missing n
        )
        if missing.count > 0 then (
            local ms = ""
            for i = 1 to missing.count do (
                if i > 1 do ms += ","
                ms += "\\"" + missing[i] + "\\""
            )
            "{{\\"error\\":\\"Missing spline objects\\",\\"missing\\":[" + ms + "]}}"
        ) else (
            fpb.distmode = 1
            fpb.distpathnodes = splineNodes
            fpb.distpathmode = {int(path_mode)}
            fpb.distpathspacing = units.decodeValue "{sp_cm}cm"
            fpb.distpathoffset = units.decodeValue "{off_cm}cm"
            fpb.distpathrandpos = units.decodeValue "{rand_cm}cm"
            fpb.distpathxfollow = {'true' if follow_path_x else 'false'}
            fpb.distpathzfollow = {'true' if follow_path_z else 'false'}
            "{{\\"object\\":\\"" + fp.name + "\\",\\"distMode\\":1,\\"pathNodes\\":" + (splineNodes.count as string) + ",\\"spacing\\":" + (fpb.distpathspacing as string) + "}}"
        )
    )
)"""
    response = client.send_command(maxscript)
    return response.get("result", '{"error":"No response from 3ds Max"}')


# ---------------------------------------------------------------------------
# Tool 15: set_forest_pack_camera_clipping
# ---------------------------------------------------------------------------

@mcp.tool()
def set_forest_pack_camera_clipping(
    name: str,
    camera_name: str | None = None,
    enabled: bool = True,
    expand_percent: int = 15,
    near_cm: float = 0.0,
    far_cm: float = 10000.0,
    back_offset_cm: float = 0.0,
) -> str:
    """Configure camera-based clipping and optimization.

    Limits item creation to the camera's visible area to improve render
    performance.  Essential for large-scale environments.

    Args:
        name: The Forest Pack object name.
        camera_name: Camera object name.  If None, uses scene active camera.
        enabled: Enable camera visibility limiting (property: camlimit).
        expand_percent: Expand FOV percentage to prevent edge popping (property: camwidth).
        near_cm: Near clipping distance in cm (property: camnear).
        far_cm: Far clipping distance in cm (property: camfar).
        back_offset_cm: Extend creation behind camera in cm (property: cambho).
    """
    safe = _safe_name(name)

    cam_line = ""
    if camera_name:
        safe_cam = _safe_name(camera_name)
        cam_line = f"""
        local camObj = getNodeByName "{safe_cam}"
        if camObj != undefined do fpb.camera = camObj"""

    maxscript = f"""(
    local fp = getNodeByName "{safe}"
    if fp == undefined then (
        "{{\\"error\\":\\"Object not found: {safe}\\"}}"
    ) else if (classOf fp.baseObject) != Forest_Pro then (
        "{{\\"error\\":\\"Object '{safe}' is not a Forest Pack object\\"}}"
    ) else (
        local fpb = fp.baseObject
        {cam_line}
        fpb.camlimit = {'true' if enabled else 'false'}
        fpb.camwidth = {int(expand_percent)}
        fpb.camnear = units.decodeValue "{float(near_cm)}cm"
        fpb.camfar = units.decodeValue "{float(far_cm)}cm"
        fpb.cambho = units.decodeValue "{float(back_offset_cm)}cm"
        local camName = try (if fpb.camera != undefined then fpb.camera.name else "none") catch "none"
        "{{\\"object\\":\\"" + fp.name + "\\",\\"camera\\":\\"" + camName + "\\",\\"camLimit\\":" + (fpb.camlimit as string) + ",\\"camWidth\\":" + (fpb.camwidth as string) + ",\\"camNear\\":" + (fpb.camnear as string) + ",\\"camFar\\":" + (fpb.camfar as string) + "}}"
    )
)"""
    response = client.send_command(maxscript)
    return response.get("result", '{"error":"No response from 3ds Max"}')


# ---------------------------------------------------------------------------
# Tool 16: set_forest_pack_animation
# ---------------------------------------------------------------------------

@mcp.tool()
def set_forest_pack_animation(
    name: str,
    mode: int = 0,
    samples: int = 10,
    offset: int = 5,
    start_frame: int = 0,
    end_frame: int = 100,
) -> str:
    """Configure animation playback for scattered instances.

    Controls how animated source geometry is played back across the
    scattered population, creating natural variation in wind sway, etc.

    Args:
        name: The Forest Pack object name.
        mode: Animation method:
            0=Disabled, 1=Follow Geometry, 2=Random Samples,
            3=Random from Map, 4=Frame from Map.
        samples: Number of animation samples (modes 2, 3).
        offset: Time offset between samples in ticks (property: animsoffset).
        start_frame: Start frame for animation range (property: animstart).
        end_frame: End frame for animation range (property: animend).
    """
    safe = _safe_name(name)

    maxscript = f"""(
    local fp = getNodeByName "{safe}"
    if fp == undefined then (
        "{{\\"error\\":\\"Object not found: {safe}\\"}}"
    ) else if (classOf fp.baseObject) != Forest_Pro then (
        "{{\\"error\\":\\"Object '{safe}' is not a Forest Pack object\\"}}"
    ) else (
        local fpb = fp.baseObject
        fpb.animation = {int(mode)}
        fpb.animsamples = {int(samples)}
        fpb.animsoffset = {int(offset)}
        fpb.animstart = {int(start_frame)}
        fpb.animend = {int(end_frame)}
        "{{\\"object\\":\\"" + fp.name + "\\",\\"animation\\":" + (fpb.animation as string) + ",\\"animsamples\\":" + (fpb.animsamples as string) + ",\\"animsoffset\\":\\"" + (fpb.animsoffset as string) + "\\"}}"
    )
)"""
    response = client.send_command(maxscript)
    return response.get("result", '{"error":"No response from 3ds Max"}')


# ---------------------------------------------------------------------------
# Tool 17: set_forest_pack_lod
# ---------------------------------------------------------------------------

@mcp.tool()
def set_forest_pack_lod(
    name: str,
    enabled: bool = True,
    lod_distance_cm: float = 5000.0,
    use_lookat: bool = False,
) -> str:
    """Configure Level of Detail (LOD) settings on a Forest Pack object.

    LOD switches geometry between high and low detail versions based on
    camera distance.  Requires ForestLOD objects in the geometry list for
    per-item LOD switching.

    Args:
        name: The Forest Pack object name.
        enabled: Enable camera-based LOD (property: camlod).
        lod_distance_cm: LOD transition distance in cm (property: camloddist).
        use_lookat: Enable LOD look-at camera (property: camlodlookat).
    """
    safe = _safe_name(name)
    dist_cm = max(0.0, float(lod_distance_cm))

    maxscript = f"""(
    local fp = getNodeByName "{safe}"
    if fp == undefined then (
        "{{\\"error\\":\\"Object not found: {safe}\\"}}"
    ) else if (classOf fp.baseObject) != Forest_Pro then (
        "{{\\"error\\":\\"Object '{safe}' is not a Forest Pack object\\"}}"
    ) else (
        local fpb = fp.baseObject
        fpb.camlod = {'true' if enabled else 'false'}
        fpb.camloddist = units.decodeValue "{dist_cm}cm"
        fpb.camlodlookat = {'true' if use_lookat else 'false'}
        "{{\\"object\\":\\"" + fp.name + "\\",\\"camLod\\":" + (fpb.camlod as string) + ",\\"camLodDist\\":" + (fpb.camloddist as string) + ",\\"camLodLookat\\":" + (fpb.camlodlookat as string) + "}}"
    )
)"""
    response = client.send_command(maxscript)
    return response.get("result", '{"error":"No response from 3ds Max"}')


# ---------------------------------------------------------------------------
# Tool 18: load_forest_pack_preset
# ---------------------------------------------------------------------------

@mcp.tool()
def load_forest_pack_preset(
    preset_path: str,
    name: str = "ForestPreset",
    surfaces: list[str] | None = None,
) -> str:
    """Load a Forest Pack preset from a .fpe file or library path.

    Forest Pack presets contain pre-configured geometry, distribution,
    and material settings.  The preset is loaded via the catalog/scatalog
    interface evalMacro mechanism.

    If surfaces are provided, they are assigned after loading the preset.

    Args:
        preset_path: Full path to a .fpe preset file.
        name: Name for the created Forest Pack object.
        surfaces: Optional surface object names to assign after loading.
    """
    safe = _safe_name(name)
    safe_path = preset_path.replace("\\", "/")

    surf_block = ""
    if surfaces:
        surf_arr = _name_array(surfaces)
        surf_block = f"""
            local surfNames = {surf_arr}
            local surfNodes = #()
            for n in surfNames do (
                local node = getNodeByName n
                if node != undefined do append surfNodes node
            )
            if surfNodes.count > 0 do fpb.surflist = surfNodes"""

    maxscript = f"""(
    local forestClass = undefined
    try (forestClass = Forest_Pro) catch ()
    if forestClass == undefined then (
        "{{\\"error\\":\\"Forest Pack is not installed (Forest_Pro unavailable).\\"}}"
    ) else (
        -- Check if preset file exists
        local presetPath = "{safe_path}"
        if not (doesFileExist presetPath) then (
            "{{\\"error\\":\\"Preset file not found: {safe_path}\\"}}"
        ) else (
            -- Create Forest Pack object
            local fpObj = Forest_Pro()
            fpObj.name = "{safe}"
            if fpObj == undefined then (
                "{{\\"error\\":\\"Failed to create Forest_Pro object.\\"}}"
            ) else (
                local fpb = fpObj.baseObject
                -- Attempt to load preset via maxscript file execution
                local loadSuccess = false
                try (
                    -- Forest Pack presets are XML-based .fpe files
                    -- Try loading via the catalog interface
                    local iface = fpb.catalog
                    if iface != undefined do (
                        iface.evalMacro presetPath
                        loadSuccess = true
                    )
                ) catch ()

                if not loadSuccess do (
                    -- Fallback: try direct file-based macro
                    try (
                        local iface = fpb.scatalog
                        if iface != undefined do (
                            iface.evalMacro presetPath
                            loadSuccess = true
                        )
                    ) catch ()
                )
                {surf_block}
                local geomCount = try (fpb.cobjlist.count as string) catch "0"
                local surfCount = try (fpb.surflist.count as string) catch "0"
                "{{\\"name\\":\\"" + fpObj.name + "\\",\\"presetLoaded\\":" + (loadSuccess as string) + ",\\"presetPath\\":\\"{safe_path}\\",\\"geometryCount\\":" + geomCount + ",\\"surfaceCount\\":" + surfCount + "}}"
            )
        )
    )
)"""
    response = client.send_command(maxscript)
    return response.get("result", '{"error":"No response from 3ds Max"}')
