from typing import Optional
import json as _json
from ..max_client import MaxBridgeError
from ..server import mcp, client
from ..coerce import StrList
from maxmcp.helpers.maxscript import safe_string












@mcp.tool()
def batch_modify(
    modifier_class: str,
    property_name: str,
    property_value: str,
    names: Optional[StrList] = None,
    selection_only: bool = False,
) -> str:
    """Batch-set a property on all modifiers of a given class across multiple objects.

    Use this for scene-wide modifier changes — e.g. "set all TurboSmooth
    iterations to 0" or "disable all Bend modifiers". Much faster and safer
    than looping via execute_maxscript. Wraps in disableSceneRedraw and undo.

    Args:
        modifier_class: Class name to match (e.g. "TurboSmooth", "Bend").
        property_name: Property to set (e.g. "iterations", "angle").
        property_value: Value as MAXScript expression (e.g. "3", "45.0", "true").
        names: Optional list of specific object names. If empty, uses all or selection.
        selection_only: If True and names is empty, only process selected objects.

    Returns count of modified modifiers.
    """
    # Upstream 1.5.5 removed this legacy native handler; use the preserved MAXScript path.

    safe_class = safe_string(modifier_class)
    safe_prop = safe_string(property_name)

    if names:
        name_arr = "#(" + ", ".join(f'"{safe_string(n)}"' for n in names) + ")"
        collect_line = f"local objsel = for n in {name_arr} where (getNodeByName n) != undefined collect (getNodeByName n)"
    elif selection_only:
        collect_line = "local objsel = selection as array"
    else:
        collect_line = "local objsel = objects as array"

    maxscript = f"""(
        disableSceneRedraw()
        undo "Batch Modify {safe_class}.{safe_prop}" on (
            {collect_line}
            local modCount = 0
            local targetClass = {safe_class}
            for obj in objsel do (
                for m = 1 to obj.modifiers.count do (
                    if (classof obj.modifiers[m]) == targetClass do (
                        try (
                            obj.modifiers[m].{safe_prop} = {property_value}
                            modCount += 1
                        ) catch ()
                    )
                )
            )
        )
        enableSceneRedraw()
        redrawViews()
        "Modified " + (modCount as string) + " {safe_class} modifiers: {safe_prop} = {property_value}"
    )"""
    response = client.send_command(maxscript)
    return response.get("result", "")
