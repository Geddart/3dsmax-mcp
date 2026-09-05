"""Advanced scene query tools using MAXScript reflection APIs.

Uses getclassinstances, refs.dependentnodes, refs.dependents, and
InstanceMgr for deep scene introspection that goes far beyond simple
object iteration.
"""

from typing import Optional
import json as _json
from ..max_client import MaxBridgeError
from ..server import mcp, client
from maxmcp.helpers.maxscript import safe_string


@mcp.tool()
def find_class_instances(
    class_name: str,
    superclass: str = "",
) -> str:
    """Find all instances of a class in the entire scene using getclassinstances.

    This searches EVERYWHERE — modifiers, materials, controllers, textures,
    atmospherics — not just top-level objects. Use this when you need to:
    - Audit the scene ("what materials/textures/modifiers are in use?")
    - Find all Bitmaptextures to check file paths
    - Count how many TurboSmooth or Bend modifiers exist scene-wide
    - Enumerate all material types with superclass="material"
    Prefer this over get_materials when you need to find non-assigned materials
    or non-material classes (textures, modifiers, controllers).

    Args:
        class_name: The class to search for (e.g. "Bitmaptexture", "Bend",
                    "VRayMtl", "Noise", "BezierFloat").
        superclass: Optional superclass to enumerate all concrete classes under it.
                    E.g. "material", "textureMap", "modifier", "Shadow",
                    "Atmospheric", "renderEffect", "FloatController".
                    When provided, class_name is ignored and ALL classes
                    under the superclass are enumerated with counts.

    Returns:
        JSON with found instances, counts, and which scene nodes reference them.
    """
    if superclass:
        safe_sc = safe_string(superclass)
        maxscript = f"""(
            local result = "{{\\\"superclass\\\": \\\"" + "{safe_sc}" + "\\\", \\\"classes\\\": ["
            local scls = execute "{safe_sc}"
            if scls == undefined then (
                "{{\\\"error\\\": \\\"Unknown superclass: {safe_sc}\\\"}}"
            ) else (
                local allClasses = scls.classes
                local entries = #()
                for c in allClasses do (
                    local insts = getclassinstances c
                    if insts.count > 0 do (
                        local entry = "{{\\\"class\\\": \\\"" + (c as string) + "\\\", \\\"count\\\": " + (insts.count as string)
                        -- Find which nodes reference first few instances
                        local nodeNames = #()
                        local maxCheck = amin #(insts.count, 5)
                        for i = 1 to maxCheck do (
                            local depNodes = refs.dependentnodes insts[i]
                            for n in depNodes do (
                                if (finditem nodeNames n.name) == 0 do append nodeNames n.name
                            )
                        )
                        entry += ", \\\"sampleNodes\\\": ["
                        local maxNames = amin #(nodeNames.count, 10)
                        for i = 1 to maxNames do (
                            if i > 1 do entry += ","
                            entry += "\\\"" + nodeNames[i] + "\\\""
                        )
                        entry += "]}}"
                        append entries entry
                    )
                )
                for i = 1 to entries.count do (
                    if i > 1 do result += ","
                    result += entries[i]
                )
                result += "]}}"
                result
            )
        )"""
    else:
        safe_cls = safe_string(class_name)
        maxscript = f"""(
            local cls = execute "{safe_cls}"
            if cls == undefined then (
                "{{\\\"error\\\": \\\"Unknown class: {safe_cls}\\\"}}"
            ) else (
                local insts = getclassinstances cls
                local result = "{{\\\"class\\\": \\\"" + (cls as string) + "\\\", \\\"count\\\": " + (insts.count as string) + ", \\\"instances\\\": ["
                local maxShow = amin #(insts.count, 50)
                for i = 1 to maxShow do (
                    if i > 1 do result += ","
                    local inst = insts[i]
                    local instName = ""
                    try (instName = inst.name) catch (try (instName = (exprForMAXObject inst)) catch (instName = (classof inst) as string))
                    local depNodes = refs.dependentnodes inst
                    local nodeArr = "["
                    local maxNodes = amin #(depNodes.count, 5)
                    for j = 1 to maxNodes do (
                        if j > 1 do nodeArr += ","
                        nodeArr += "\\\"" + depNodes[j].name + "\\\""
                    )
                    nodeArr += "]"
                    result += "{{\\\"name\\\": \\\"" + instName + "\\\", \\\"usedByNodes\\\": " + nodeArr + "}}"
                )
                result += "]}}"
                result
            )
        )"""
    response = client.send_command(maxscript)
    return response.get("result", "")






@mcp.tool()
def find_objects_by_property(
    property_name: str,
    property_value: str = "",
    class_filter: str = "",
) -> str:
    """Find scene objects that have a specific property, optionally matching a value.

    Use this for scene-wide queries like "which objects are non-renderable?",
    "which objects have shadows disabled?", "which lights have multiplier > 1?".
    Much faster than iterating objects manually via execute_maxscript.

    Args:
        property_name: Property to check (e.g. "renderable", "castshadows",
                       "primaryVisibility", "material").
        property_value: Optional value to match (e.g. "false", "true").
                        If empty, just checks if the property exists and is readable.
        class_filter: Optional class name filter (e.g. "Box", "Light").

    Returns:
        JSON list of matching objects.
    """
    # Upstream 1.5.5 removed this legacy native handler; use the preserved MAXScript path.

    safe_prop = safe_string(property_name)
    safe_val = safe_string(property_value)
    class_cond = ""
    if class_filter:
        safe_class = safe_string(class_filter)
        class_cond = f'and (matchPattern ((classof obj) as string) pattern:"*{safe_class}*")'

    if property_value:
        maxscript = f"""(
            local matched = #()
            for obj in objects {class_cond} do (
                try (
                    local val = getproperty obj #{safe_prop}
                    if (val as string) == "{safe_val}" or (toLower (val as string)) == (toLower "{safe_val}") do
                        append matched obj
                ) catch ()
            )
            local result = "["
            for i = 1 to matched.count do (
                if i > 1 do result += ","
                result += "\\\"" + matched[i].name + "\\\""
            )
            result += "]"
            result
        )"""
    else:
        maxscript = f"""(
            local matched = #()
            for obj in objects {class_cond} do (
                try (
                    local val = getproperty obj #{safe_prop}
                    append matched #(obj.name, val as string)
                ) catch ()
            )
            local result = "["
            for i = 1 to matched.count do (
                if i > 1 do result += ","
                result += "{{\\\"name\\\": \\\"" + matched[i][1] + "\\\", \\\"value\\\": \\\"" + matched[i][2] + "\\\"}}"
            )
            result += "]"
            result
        )"""
    response = client.send_command(maxscript)
    return response.get("result", "[]")
