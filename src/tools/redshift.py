"""Redshift material tools for 3ds Max.

Dedicated tools for creating, inspecting, modifying Redshift materials and
connecting texture maps.  Based on live introspection of RS_Standard_Material
in 3ds Max 2025 / Redshift 2026.3.1.
"""

from __future__ import annotations

from ..server import mcp, client


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _safe_name(name: str) -> str:
    return name.replace("\\", "\\\\").replace('"', '\\"')


def _ms_path(path: str) -> str:
    """Convert a file path to MAXScript-safe forward-slash string."""
    return path.replace("\\", "/")


def _color_arg(color_str: str) -> str:
    """Convert ``"R,G,B"`` string to MAXScript ``(color R G B)``."""
    r, g, b = (c.strip() for c in color_str.split(","))
    return f"(color {r} {g} {b})"


# ---------------------------------------------------------------------------
# Presets for create_redshift_material
# ---------------------------------------------------------------------------

_PRESETS: dict[str, dict] = {
    "chrome":   {"metalness": 1.0, "refl_roughness": 0.05, "base_color": "200,200,200"},
    "gold":     {"metalness": 1.0, "refl_roughness": 0.1,  "base_color": "255,200,50"},
    "copper":   {"metalness": 1.0, "refl_roughness": 0.15, "base_color": "220,130,80"},
    "glass":    {"refr_weight": 1.0, "refl_roughness": 0.0, "refl_ior": 1.52, "thin_walled": False},
    "plastic":  {"metalness": 0.0, "refl_roughness": 0.3, "refl_ior": 1.45},
    "rubber":   {"metalness": 0.0, "refl_roughness": 0.8, "refl_weight": 0.3},
    "ceramic":  {"metalness": 0.0, "refl_roughness": 0.15, "coat_weight": 1.0, "coat_ior": 1.5},
    "skin":     {"ms_amount": 1.0, "ms_mode": 2, "ms_color": "200,100,80"},
    "sss_wax":  {"ms_amount": 1.0, "ms_mode": 0, "refr_weight": 0.1},
    "emissive": {"emission_weight": 1.0, "emission_color": "255,255,255"},
}

# Properties that take a MAXScript `color` value
_COLOR_PROPS = {"base_color", "refl_color", "refr_color", "coat_color",
                "sheen_color", "emission_color", "opacity_color",
                "ms_color", "ss_scatter_color"}

# Layer → property groups for get_redshift_material_info
_LAYER_PROPS: dict[str, list[str]] = {
    "base":       ["base_color", "base_color_weight", "diffuse_roughness", "metalness"],
    "reflection": ["refl_color", "refl_weight", "refl_roughness", "refl_ior",
                   "refl_aniso", "refl_aniso_rotation"],
    "refraction": ["refr_color", "refr_weight", "refr_roughness", "refr_abbe",
                   "ss_depth", "ss_scatter_color"],
    "sss":        ["ms_amount", "ms_color", "ms_radius", "ms_radius_scale",
                   "ms_phase", "ms_mode"],
    "sheen":      ["sheen_color", "sheen_weight", "sheen_roughness"],
    "coat":       ["coat_color", "coat_weight", "coat_roughness", "coat_ior",
                   "coat_aniso", "coat_aniso_rotation"],
    "emission":   ["emission_color", "emission_weight"],
    "opacity":    ["opacity_color", "thin_walled"],
    "geometry":   ["bump_input", "displacement_input", "overall_color"],
}


def _ms_value(prop: str, value) -> str:
    """Format a Python value as MAXScript literal for the given property."""
    if prop in _COLOR_PROPS and isinstance(value, str) and "," in value:
        return _color_arg(value)
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        return f"{value:.6f}"
    return str(value)


def _find_mat_ms(material_name: str | None, object_name: str | None) -> str:
    """Return MAXScript lines that resolve a material into local ``mat``.

    Populates ``mat`` or sets it to ``undefined`` on failure.
    """
    lines: list[str] = []
    if object_name:
        safe = _safe_name(object_name)
        lines.append(f'local obj = getNodeByName "{safe}"')
        lines.append('local mat = if obj != undefined then obj.material else undefined')
    elif material_name:
        safe = _safe_name(material_name)
        lines.append('local mat = undefined')
        lines.append(f'for m in sceneMaterials where m.name == "{safe}" do (mat = m; exit)')
        lines.append(f'if mat == undefined do (for m in meditMaterials where m.name == "{safe}" do (mat = m; exit))')
    else:
        lines.append('local mat = undefined')
    return "\n    ".join(lines)


# ---------------------------------------------------------------------------
# Tool 1: create_redshift_material
# ---------------------------------------------------------------------------

@mcp.tool()
def create_redshift_material(
    name: str,
    preset: str | None = None,
    objects: list[str] | None = None,
    base_color: str | None = None,
    metalness: float = 0.0,
    refl_roughness: float = 0.5,
    refl_weight: float = 1.0,
    refl_ior: float = 1.5,
    refl_aniso: float = 0.0,
    refr_weight: float = 0.0,
    refr_color: str | None = None,
    coat_weight: float = 0.0,
    coat_roughness: float = 0.0,
    coat_ior: float = 1.5,
    sheen_weight: float = 0.0,
    emission_weight: float = 0.0,
    emission_color: str | None = None,
    opacity_color: str | None = None,
    thin_walled: bool = False,
    ms_amount: float = 0.0,
    ms_color: str | None = None,
    ms_mode: int = 0,
) -> str:
    """Create an RS_Standard_Material with optional preset and assign to objects.

    Use presets for common looks: chrome, gold, copper, glass, plastic, rubber,
    ceramic, skin, sss_wax, emissive.  Explicit parameters override preset values.

    Args:
        name: Material name.
        preset: Named preset (chrome, gold, copper, glass, plastic, rubber,
                ceramic, skin, sss_wax, emissive).
        objects: Objects to assign the material to.
        base_color: "R,G,B" (0-255).
        metalness: 0.0-1.0.
        refl_roughness: Reflection roughness 0.0-1.0.
        refl_weight: Reflection weight 0.0-1.0.
        refl_ior: Reflection IOR.
        refl_aniso: Anisotropy 0.0-1.0.
        refr_weight: Refraction weight (0=opaque, 1=fully refractive).
        refr_color: Refraction color "R,G,B".
        coat_weight: Clearcoat weight 0.0-1.0.
        coat_roughness: Clearcoat roughness 0.0-1.0.
        coat_ior: Clearcoat IOR.
        sheen_weight: Sheen weight 0.0-1.0.
        emission_weight: Emission weight 0.0-1.0.
        emission_color: Emission color "R,G,B".
        opacity_color: Opacity color "R,G,B" (white=opaque).
        thin_walled: Thin-walled mode for refraction.
        ms_amount: SSS amount (0=off, 1=full).
        ms_color: SSS scatter color "R,G,B".
        ms_mode: SSS mode (0=point, 1=ray, 2=random walk).
    """
    # Merge preset defaults, then overlay explicit args
    effective: dict = {}
    if preset and preset.lower() in _PRESETS:
        effective.update(_PRESETS[preset.lower()])

    # Map parameter names to locals — only override preset if caller explicitly set a value
    local_args = {
        "base_color": base_color, "metalness": metalness,
        "refl_roughness": refl_roughness, "refl_weight": refl_weight,
        "refl_ior": refl_ior, "refl_aniso": refl_aniso,
        "refr_weight": refr_weight, "refr_color": refr_color,
        "coat_weight": coat_weight, "coat_roughness": coat_roughness,
        "coat_ior": coat_ior, "sheen_weight": sheen_weight,
        "emission_weight": emission_weight, "emission_color": emission_color,
        "opacity_color": opacity_color, "thin_walled": thin_walled,
        "ms_amount": ms_amount, "ms_color": ms_color, "ms_mode": ms_mode,
    }

    # Defaults that match MAXScript constructor defaults
    _DEFAULTS = {
        "metalness": 0.0, "refl_roughness": 0.5, "refl_weight": 1.0,
        "refl_ior": 1.5, "refl_aniso": 0.0, "refr_weight": 0.0,
        "coat_weight": 0.0, "coat_roughness": 0.0, "coat_ior": 1.5,
        "sheen_weight": 0.0, "emission_weight": 0.0, "thin_walled": False,
        "ms_amount": 0.0, "ms_mode": 0,
    }

    # For non-None scalar args: if the value differs from Python default it's explicit
    for prop, val in local_args.items():
        if val is None:
            continue
        default = _DEFAULTS.get(prop)
        if default is not None and val == default and prop not in effective:
            continue  # user didn't set it and no preset set it
        effective[prop] = val

    safe = _safe_name(name)
    lines: list[str] = [f'local mat = RS_Standard_Material name:"{safe}"']
    props_set: list[str] = []

    for prop, val in effective.items():
        ms_val = _ms_value(prop, val)
        lines.append(f'mat.{prop} = {ms_val}')
        props_set.append(prop)

    # Build JSON result
    lines.append(f'local json = "{{\\\"name\\\":\\\"" + mat.name + "\\\""')
    lines.append('json += ",\\\"class\\\":\\\"RS_Standard_Material\\\""')
    if preset:
        lines.append(f'json += ",\\\"preset\\\":\\\"{preset.lower()}\\\""')
    props_json = ",".join(f'\\\\\\"{p}\\\\\\"' for p in props_set)
    lines.append('json += ",\\\"properties_set\\\":[' + props_json + ']"')

    if objects:
        names_arr = "#(" + ", ".join(f'"{_safe_name(n)}"' for n in objects) + ")"
        lines.append(f'local nameList = {names_arr}')
        lines.append('local assigned = #()')
        lines.append('for n in nameList do (local obj = getNodeByName n; if obj != undefined do (obj.material = mat; append assigned n))')
        lines.append('local assignedStr = ""')
        lines.append('for i = 1 to assigned.count do (if i > 1 do assignedStr += ","; assignedStr += "\\\"" + assigned[i] + "\\\"")')
        lines.append('json += ",\\\"assigned_to\\\":[" + assignedStr + "]"')
    else:
        lines.append('json += ",\\\"assigned_to\\\":[]"')

    lines.append('json += "}"')
    lines.append('json')

    ms = "(\n    " + "\n    ".join(lines) + "\n)"
    return client.send_command(ms)


# ---------------------------------------------------------------------------
# Tool 2: get_redshift_material_info
# ---------------------------------------------------------------------------

@mcp.tool()
def get_redshift_material_info(
    material_name: str | None = None,
    object_name: str | None = None,
    layer: str | None = None,
) -> str:
    """Inspect a Redshift material's properties organized by layer.

    Returns property values and connected texture maps for any RS material.
    Use layer filter to focus on specific sections.

    Args:
        material_name: Material name to look up in scene or material editor.
        object_name: Get material from this object instead.
        layer: Filter to one layer: base, reflection, refraction, sss, sheen,
               coat, emission, opacity, geometry.
    """
    find_ms = _find_mat_ms(material_name, object_name)

    # Determine which layers to report
    if layer and layer.lower() in _LAYER_PROPS:
        layers = {layer.lower(): _LAYER_PROPS[layer.lower()]}
    else:
        layers = _LAYER_PROPS

    lines: list[str] = [find_ms]
    lines.append('if mat == undefined do "{\\"error\\":\\"Material not found\\"}"')
    lines.append('if mat != undefined do (')
    lines.append('local cls = classOf mat as string')
    lines.append('local json = "{\\"name\\":\\"" + mat.name + "\\",\\"class\\":\\"" + cls + "\\""')

    for lname, props in layers.items():
        lines.append(f'json += ",\\"{lname}\\":{{"')
        for i, prop in enumerate(props):
            pfx = "" if i == 0 else ","
            # Get value
            lines.append(f'local v_{prop} = try (getProperty mat #{prop}) catch("N/A")')
            lines.append(f'local vs_{prop} = v_{prop} as string')
            # Check for connected map
            map_prop = f"{prop}_map" if not prop.endswith("_input") else prop
            lines.append(f'local mp_{prop} = try (getProperty mat #{map_prop}) catch(undefined)')
            lines.append(f'local mps_{prop} = if mp_{prop} != undefined then ("\\"" + (classOf mp_{prop}) as string + ": " + mp_{prop}.name + "\\"") else "null"')
            lines.append(f'json += "{pfx}\\"{prop}\\":{{\\"value\\":\\"" + vs_{prop} + "\\",\\"map\\":" + mps_{prop} + "}}"')
        lines.append('json += "}"')

    lines.append('json += "}"')
    lines.append('json')
    lines.append(')')

    ms = "(\n    " + "\n    ".join(lines) + "\n)"
    return client.send_command(ms)


# ---------------------------------------------------------------------------
# Tool 3: set_redshift_material_properties
# ---------------------------------------------------------------------------

@mcp.tool()
def set_redshift_material_properties(
    material_name: str,
    properties: dict,
) -> str:
    """Batch-set properties on an existing Redshift material.

    Supports float, int, bool, and color ("R,G,B") values.
    Returns before/after values for each property.

    Args:
        material_name: Name of the material to modify.
        properties: Property name → value pairs.
                    Colors as "R,G,B" strings, bools as true/false.
    """
    find_ms = _find_mat_ms(material_name, None)
    lines: list[str] = [find_ms]
    lines.append('if mat == undefined do "{\\"error\\":\\"Material not found\\"}"')
    lines.append('if mat != undefined do (')
    lines.append('local json = "{\\"material\\":\\"" + mat.name + "\\",\\"changes\\\":["')

    prop_items = list(properties.items())
    for i, (prop, val) in enumerate(prop_items):
        pfx = "" if i == 0 else ","
        ms_val = _ms_value(prop, val)
        lines.append(f'local old_{i} = try ((getProperty mat #{prop}) as string) catch("N/A")')
        lines.append(f'try (setProperty mat #{prop} {ms_val}) catch()')
        lines.append(f'local new_{i} = try ((getProperty mat #{prop}) as string) catch("N/A")')
        lines.append(f'json += "{pfx}{{\\"prop\\":\\"{prop}\\",\\"old\\":\\"" + old_{i} + "\\",\\"new\\":\\"" + new_{i} + "\\"}}"')

    lines.append('json += "]}"')
    lines.append('json')
    lines.append(')')

    ms = "(\n    " + "\n    ".join(lines) + "\n)"
    return client.send_command(ms)


# ---------------------------------------------------------------------------
# Tool 4: connect_redshift_texture
# ---------------------------------------------------------------------------

@mcp.tool()
def connect_redshift_texture(
    material_name: str,
    slot: str,
    texture_class: str = "RS_Bitmap",
    texture_name: str | None = None,
    file_path: str | None = None,
    color_space: str | None = None,
    properties: dict | None = None,
) -> str:
    """Create a Redshift texture map and wire it into a material slot.

    Common slots: base_color_map, metalness_map, refl_roughness_map,
    bump_input, displacement_input, coat_bump_input, emission_color_map,
    opacity_color_map, and many more (any *_map or *_input slot).

    Common texture classes: RS_Bitmap, RS_Normal_Map, RS_Bump_Map,
    RS_Displacement, RS_Maxon_Noise, RS_Tiles, RS_Triplanar, RS_AO,
    RS_Curvature, RS_Color_Correct, RS_Mix, RS_Fresnel, RS_Round_Corners.

    Args:
        material_name: Target material name.
        slot: Material slot name (e.g. "base_color_map", "bump_input").
        texture_class: Redshift texture class to create.
        texture_name: Name for the texture node (auto-generated if omitted).
        file_path: File path for bitmap-based textures (RS_Bitmap, RS_Normal_Map).
        color_space: Color space for RS_Bitmap ("sRGB", "Raw", "ACEScg", etc.).
        properties: Additional properties to set on the texture node.
    """
    find_ms = _find_mat_ms(material_name, None)
    auto_name = texture_name or f"{texture_class}_{slot}"
    safe_tex_name = _safe_name(auto_name)

    lines: list[str] = [find_ms]
    lines.append('if mat == undefined do "{\\"error\\":\\"Material not found\\"}"')
    lines.append('if mat != undefined do (')
    lines.append(f'local tex = {texture_class} name:"{safe_tex_name}"')

    # File path handling for bitmap-based classes
    if file_path:
        fp = _ms_path(file_path)
        if texture_class == "RS_Bitmap":
            lines.append(f'tex.tex0_filename = "{fp}"')
            if color_space:
                lines.append(f'tex.tex0_colorSpace = "{color_space}"')
        elif texture_class == "RS_Normal_Map":
            # RS_Normal_Map has tex0_filename directly (no child bitmap needed)
            lines.append(f'tex.tex0_filename = "{fp}"')
        elif texture_class == "RS_Displacement":
            # RS_Displacement needs a child RS_Bitmap wired to texMap_map
            cs = color_space or "Raw"
            lines.append(f'local dispBmp = RS_Bitmap name:"{safe_tex_name}_Bmp"')
            lines.append(f'dispBmp.tex0_filename = "{fp}"')
            lines.append(f'dispBmp.tex0_colorSpace = "{cs}"')
            lines.append('tex.texMap_map = dispBmp')
        else:
            # Generic: try tex0_filename first, fall back to texMap_map with RS_Bitmap
            lines.append(f'try (tex.tex0_filename = "{fp}") catch (try (tex.texMap_filename = "{fp}") catch())')

    # Set additional properties
    if properties:
        for prop, val in properties.items():
            ms_val = _ms_value(prop, val)
            lines.append(f'try (setProperty tex #{prop} {ms_val}) catch()')

    # Wire texture to material slot
    safe_slot = _safe_name(slot)
    lines.append(f'setProperty mat #{safe_slot} tex')

    # Auto-enable companion _mapenable if the slot ends with _map
    if slot.endswith("_map"):
        enable_prop = slot.replace("_map", "_mapenable")
        lines.append(f'try (setProperty mat #{enable_prop} true) catch()')

    # Build JSON result
    lines.append(f'local json = "{{\\\"texture_name\\\":\\\"" + tex.name + "\\\""')
    lines.append(f'json += ",\\\"texture_class\\\":\\\"" + (classOf tex as string) + "\\\""')
    lines.append(f'json += ",\\\"slot\\\":\\\"{safe_slot}\\\""')
    lines.append('json += ",\\\"material\\\":\\"" + mat.name + "\\""')
    lines.append('json += "}"')
    lines.append('json')
    lines.append(')')

    ms = "(\n    " + "\n    ".join(lines) + "\n)"
    return client.send_command(ms)


# ---------------------------------------------------------------------------
# Tool 5: list_redshift_materials
# ---------------------------------------------------------------------------

# Known RS material superclasses for filtering
_RS_MATERIAL_CLASSES = {
    "RS_Standard_Material", "RS_Material", "RS_Car_Paint", "RS_Hair",
    "RS_Principled_Hair", "RS_Skin", "RS_Incandescent", "RS_Architectural",
    "RS_Toon_Material", "RS_Contour", "RS_SSS", "RS_Surface", "RS_Volume",
    "RS_Standard_Volume", "RS_Matte_Shadow_Catcher", "RS_Sprite",
    "RS_Material_Blender", "RS_Material_Switch", "RS_Random_Material_Switch",
    "RS_Ray_Switch_Material", "RS_Material_Output", "RS_Store_Color_To_AOV",
    "RS_OpenPBR_Material", "RS_OSL_Material",
}


@mcp.tool()
def list_redshift_materials(
    filter_class: str | None = None,
) -> str:
    """List all Redshift materials in the scene.

    Args:
        filter_class: Optional class name to filter by (e.g. "RS_Standard_Material").
    """
    # Build a class filter pattern: either specific class or all RS_ prefixed
    if filter_class:
        safe_cls = _safe_name(filter_class)
        filter_line = f'local isRS = (cls == "{safe_cls}")'
    else:
        filter_line = 'local isRS = (matchPattern cls pattern:"RS_*")'

    lines: list[str] = [
        'local json = "["',
        'local first = true',
        'for m in sceneMaterials do (',
        '    local cls = classOf m as string',
        f'    {filter_line}',
        '    if isRS do (',
        '        if not first do json += ","',
        '        first = false',
        '        local summary = ""',
        '        if cls == "RS_Standard_Material" do (',
        '            local mtl = try (getProperty m #metalness) catch(0)',
        '            local rgh = try (getProperty m #refl_roughness) catch(0)',
        '            summary = "metal=" + (mtl as string) + " rough=" + (rgh as string)',
        '        )',
        '        json += "{\\"name\\":\\"" + m.name + "\\",\\"class\\":\\"" + cls + "\\",\\"summary\\":\\"" + summary + "\\"}"',
        '    )',
        ')',
        'json += "]"',
        'json',
    ]

    ms = "(\n    " + "\n    ".join(lines) + "\n)"
    return client.send_command(ms)
