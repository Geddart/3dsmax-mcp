"""tyFlow particle system tools for 3ds Max.

Provides MCP tools for creating, inspecting, and controlling tyFlow
particle systems and Inferno (Zenith) smoke/fire simulations.

Based on live introspection of tyFlow v2.003 in 3ds Max 2025 (2026-03-22).

Key constraints:
- Shape ``_tab`` arrays are the ONLY writable path; single-item props are READ-ONLY.
- ``addOperator`` requires two args: name + position index.
- Operator variable names MUST use ``_Op`` suffix to avoid MAXScript global name collisions.
- ``quickType_submit`` CRASHES -- never use it.
- Operators with spaces in their name need ``#'PhysX Shape'`` quoting in SubAnim paths.
- Inferno operators require tyFlow 2.0+ (Zenith). Tools fail gracefully on older versions.
- Volume API: always pair ``updateVolumes()`` / ``releaseVolumes()`` to avoid GPU memory leaks.
- Export operator is ``Export Inferno`` (not ``Inferno Export``).
- tyCache export: call ``opRef.exportTyCache()`` on an Export Particles operator.
  Also available: ``exportPRT()``, ``exportAlembic_Mesh()``, ``exportAlembic_PC()``.
"""

from __future__ import annotations

from ..server import mcp, client


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _safe_name(name: str) -> str:
    """Escape a user-provided name for embedding in MAXScript strings."""
    return name.replace("\\", "\\\\").replace('"', '\\"')


def _name_array(names: list[str]) -> str:
    """Build a MAXScript ``#("a","b",...)`` string array literal."""
    return "#(" + ", ".join(f'"{_safe_name(n)}"' for n in names) + ")"


def _int_array(values: list[int]) -> str:
    """Build a MAXScript ``#(1, 2, ...)`` integer array literal."""
    return "#(" + ", ".join(str(int(v)) for v in values) + ")"


def _float_array(values: list[float]) -> str:
    """Build a MAXScript ``#(1.0, 2.0, ...)`` float array literal."""
    return "#(" + ", ".join(f"{float(v):.4f}" for v in values) + ")"


def _bool_array(values: list[bool]) -> str:
    """Build a MAXScript ``#(true, false, ...)`` boolean array literal."""
    return "#(" + ", ".join("true" if v else "false" for v in values) + ")"


def _ms_value(val) -> str:
    """Convert a Python value to its MAXScript literal representation."""
    if isinstance(val, bool):
        return "true" if val else "false"
    if isinstance(val, float):
        return f"{val:.6f}"
    if isinstance(val, int):
        return str(val)
    if isinstance(val, str):
        return f'"{_safe_name(val)}"'
    if isinstance(val, list):
        # Detect element type from first element
        if val and isinstance(val[0], bool):
            return _bool_array(val)
        if val and isinstance(val[0], float):
            return _float_array(val)
        if val and isinstance(val[0], int):
            return _int_array(val)
        if val and isinstance(val[0], str):
            return _name_array(val)
        return "#()"
    return str(val)


def _sa_name(name: str) -> str:
    """Format a name for SubAnim access -- replace spaces with underscores."""
    safe = _safe_name(name).replace(" ", "_")
    return f"#{safe}"


# ---------------------------------------------------------------------------
# Shape ID mapping (VERIFIED 2026-03-03 via live introspection)
# ---------------------------------------------------------------------------

SHAPE_3D_IDS: dict[str, int] = {
    "triangle": 0,
    "cone": 1,
    "quad": 2,
    "plane": 2,          # alias
    "cylinder": 3,
    "sphere": 4,          # 289 verts, 512 faces
    "pyramid": 5,         # DEFAULT -- 5 verts, 6 faces
    "box": 6,
    "cube": 6,            # alias
    "octahedron": 7,
    "geosphere_low": 8,
    "geosphere": 9,       # medium (default geosphere)
    "geosphere_med": 9,   # alias
    "geosphere_high": 10,
    "icosahedron": 11,
}


# ---------------------------------------------------------------------------
# Tool 1: create_tyflow
# ---------------------------------------------------------------------------

@mcp.tool()
def create_tyflow(
    name: str = "tyFlow001",
    events: list[dict] | None = None,
    position: list[float] | None = None,
    physx_gravity: bool = False,
    physx_gravity_value: float = -980.0,
    physx_ground_collider: bool = False,
    physx_substeps: int = 4,
    reset_simulation: bool = True,
    open_editor: bool = False,
) -> str:
    """Create a new tyFlow particle system with events and operators.

    Each event dict should have:
      - name (str): Event name.
      - operators (list[dict]): Each operator dict has:
        - type (str): Operator type name (e.g. "Birth", "Speed", "Shape").
        - properties (dict, optional): Property name-value pairs to set.

    Args:
        name: tyFlow object name.
        events: List of event definitions. If None a bare tyFlow is created.
        position: World position [x, y, z]. Defaults to [0, 0, 0].
        physx_gravity: Enable PhysX gravity on the tyFlow.
        physx_gravity_value: Gravity strength (negative = down). Default -980.
        physx_ground_collider: Enable built-in ground plane collider.
        physx_substeps: PhysX substeps (default 4).
        reset_simulation: Reset simulation after creation.
        open_editor: Open the tyFlow editor UI.
    """
    pos = position or [0.0, 0.0, 0.0]
    safe = _safe_name(name)
    events = events or []

    lines: list[str] = [
        f'local tfObj = tyflow()',
        f'tfObj.name = "{safe}"',
        f'tfObj.pos = [{pos[0]}, {pos[1]}, {pos[2]}]',
    ]

    # PhysX object-level settings
    if physx_gravity:
        lines.append("tfObj.physXGravityEnabled = true")
        lines.append(f"tfObj.physXGravityValue = {physx_gravity_value:.6f}")
    if physx_ground_collider:
        lines.append("tfObj.physXGroundCollider = true")
    if physx_substeps != 4:
        lines.append(f"tfObj.physXSubsteps = {physx_substeps}")

    # Build events
    event_json_parts: list[str] = []
    for evt_idx, evt in enumerate(events):
        evt_name = _safe_name(evt.get("name", f"Event{evt_idx + 1}"))
        lines.append(f'local ev{evt_idx} = tfObj.addEvent()')
        lines.append(f'ev{evt_idx}.setName "{evt_name}"')

        operators = evt.get("operators", [])
        op_names: list[str] = []
        for op_idx, op in enumerate(operators):
            op_type = _safe_name(op.get("type", ""))
            var = f"op_{evt_idx}_{op_idx}_Op"
            lines.append(f'local {var} = ev{evt_idx}.addOperator "{op_type}" {op_idx + 1}')
            props = op.get("properties", {})
            for prop_name, prop_val in props.items():
                lines.append(f'{var}.{prop_name} = {_ms_value(prop_val)}')
            op_names.append(op_type)

        # Build per-event JSON fragment
        ops_json = ", ".join(f'\\"{o}\\"' for o in op_names)
        event_json_parts.append(
            f'"{{\\\"name\\\":\\\"{evt_name}\\\",\\\"operatorCount\\\":{len(op_names)},'
            f'\\\"operators\\\":[{ops_json}]}}"'
        )

    if reset_simulation:
        lines.append("tfObj.reset_simulation()")
    if open_editor:
        lines.append("tfObj.editor_open()")

    # Build JSON response
    events_json_str = " + \",\" + ".join(event_json_parts) if event_json_parts else '""'
    lines.append(f'local evJson = ""')
    if event_json_parts:
        for i, part in enumerate(event_json_parts):
            if i == 0:
                lines.append(f'evJson += {part}')
            else:
                lines.append(f'evJson += "," + {part}')

    lines.append(f'local json = "{{\\\"name\\\":\\\"" + tfObj.name + "\\\""')
    lines.append(f'json += ",\\\"eventCount\\\":{len(events)}"')
    lines.append(f'json += ",\\\"events\\\":[" + evJson + "]"')
    lines.append(f'json += "}}"')
    lines.append('json')

    ms = "(\n    " + "\n    ".join(lines) + "\n)"
    return client.send_command(ms).get("result", "")


# ---------------------------------------------------------------------------
# Tool 2: get_tyflow_info
# ---------------------------------------------------------------------------

@mcp.tool()
def get_tyflow_info(
    name: str,
    include_properties: bool = False,
) -> str:
    """Get comprehensive info about a tyFlow object.

    Returns events, operators, particle count, PhysX settings, and
    simulation state.  Set include_properties=True for a full property
    dump per operator (verbose).

    Args:
        name: tyFlow object name.
        include_properties: Include full property list per operator.
    """
    safe = _safe_name(name)

    # The MAXScript enumerates events via baseobject SubAnims.
    # Fixed SubAnims are indices 1..20; events start at index 21+.
    prop_block = ""
    if include_properties:
        prop_block = r"""
                local ss = StringStream ""
                showProperties (getSubAnim evSA j) to:ss
                local propStr = substituteString (ss as string) "\"" "'"
                propStr = substituteString propStr "\n" " | "
                opJson += ",\"properties\":\"" + propStr + "\""
"""
    else:
        prop_block = ""

    maxscript = f"""(
    local tfObj = getNodeByName "{safe}"
    if tfObj == undefined then (
        "{{\\\"error\\\":\\\"tyFlow not found: {safe}\\\"}}"
    ) else if (classOf tfObj.baseobject) != tyFlow then (
        "{{\\\"error\\\":\\\"Object is not a tyFlow: {safe}\\\"}}"
    ) else (
        local tf = tfObj.baseobject
        tfObj.updateParticles currentTime
        local pCount = tfObj.numParticles()
        local p = tfObj.pos

        local json = "{{\\\"name\\\":\\\"" + tfObj.name + "\\\""
        json += ",\\\"class\\\":\\\"tyFlow\\\""
        json += ",\\\"position\\\":[" + (p.x as string) + "," + (p.y as string) + "," + (p.z as string) + "]"
        json += ",\\\"particleCount\\\":" + (pCount as string)

        -- PhysX info
        json += ",\\\"physx\\\":{{\\\"gravityEnabled\\\":" + (tf.physXGravityEnabled as string)
        json += ",\\\"gravityValue\\\":" + (tf.physXGravityValue as string)
        json += ",\\\"groundCollider\\\":" + (tf.physXGroundCollider as string)
        json += ",\\\"substeps\\\":" + (tf.physXSubsteps as string)
        json += "}}"

        -- Enumerate events (SubAnims after the 20 fixed ones)
        local numSA = tf.numsubs
        json += ",\\\"events\\\":["
        local firstEvt = true
        for i = 1 to numSA do (
            local sa = getSubAnim tf i
            -- Events are SubAnims that themselves have SubAnims (operators)
            -- Fixed params have 0 subs; events have 1+ subs (their operators)
            if sa.numsubs > 0 then (
                local evName = getSubAnimName tf i
                if not firstEvt do json += ","
                firstEvt = false
                json += "{{\\\"name\\\":\\\"" + (evName as string) + "\\\""

                -- Enumerate operators in this event
                local evSA = sa
                local opCount = evSA.numsubs
                json += ",\\\"operatorCount\\\":" + (opCount as string)
                json += ",\\\"operators\\\":["
                for j = 1 to opCount do (
                    if j > 1 do json += ","
                    local opName = getSubAnimName evSA j
                    local opJson = "{{\\\"name\\\":\\\"" + (opName as string) + "\\\""
                    {prop_block.replace(chr(10), chr(10) + '                    ') if include_properties else ''}
                    opJson += "}}"
                    json += opJson
                )
                json += "]}}"
            )
        )
        json += "]}}"
        json
    )
)"""
    return client.send_command(maxscript).get("result", "")


# ---------------------------------------------------------------------------
# Tool 3: modify_tyflow_operator
# ---------------------------------------------------------------------------

@mcp.tool()
def modify_tyflow_operator(
    tyflow_name: str,
    event_name: str,
    operator_name: str,
    properties: dict,
) -> str:
    """Modify properties on an existing tyFlow operator.

    Access operators via baseobject SubAnim path.  Operators with spaces
    in their name (e.g. "PhysX Shape") are handled automatically.

    Args:
        tyflow_name: tyFlow object name.
        event_name: Event name containing the operator.
        operator_name: Operator name to modify.
        properties: Property name to value pairs to set.
    """
    safe_tf = _safe_name(tyflow_name)
    sa_evt = _sa_name(event_name)
    sa_op = _sa_name(operator_name)
    safe_op = _safe_name(operator_name)

    lines: list[str] = [
        f'local tfObj = getNodeByName "{safe_tf}"',
        f'if tfObj == undefined then (',
        f'    "{{\\\"error\\\":\\\"tyFlow not found: {safe_tf}\\\"}}"',
        ') else (',
        f'    local opRef = undefined',
        f'    try (opRef = tfObj.baseobject[{sa_evt}][{sa_op}]) catch ()',
        f'    if opRef == undefined then (',
        f'        "{{\\\"error\\\":\\\"Operator not found: {safe_op} in event {_safe_name(event_name)}\\\"}}"',
        '    ) else (',
    ]

    # Build property assignment lines
    prop_names: list[str] = []
    for prop_name, prop_val in properties.items():
        lines.append(f'        try (opRef.{prop_name} = {_ms_value(prop_val)}) catch ()')
        prop_names.append(prop_name)

    props_json = ", ".join(f'\\"{p}\\"' for p in prop_names)
    lines.append(f'        "{{\\\"success\\\":true,\\\"operator\\\":\\\"{safe_op}\\\",'
                 f'\\\"propertiesSet\\\":[{props_json}]}}"')
    lines.append('    )')
    lines.append(')')

    ms = "(\n    " + "\n    ".join(lines) + "\n)"
    return client.send_command(ms).get("result", "")


# ---------------------------------------------------------------------------
# Tool 4: add_tyflow_event
# ---------------------------------------------------------------------------

@mcp.tool()
def add_tyflow_event(
    tyflow_name: str,
    event_name: str,
    operators: list[dict] | None = None,
) -> str:
    """Add a new event with operators to an existing tyFlow.

    Each operator dict should have:
      - type (str): Operator type name (e.g. "Birth", "Speed").
      - properties (dict, optional): Property name-value pairs.

    Args:
        tyflow_name: tyFlow object name.
        event_name: Name for the new event.
        operators: List of operator definitions to add.
    """
    safe_tf = _safe_name(tyflow_name)
    safe_evt = _safe_name(event_name)
    operators = operators or []

    lines: list[str] = [
        f'local tfObj = getNodeByName "{safe_tf}"',
        f'if tfObj == undefined then (',
        f'    "{{\\\"error\\\":\\\"tyFlow not found: {safe_tf}\\\"}}"',
        ') else (',
        f'    local newEv = tfObj.addEvent()',
        f'    newEv.setName "{safe_evt}"',
    ]

    op_names: list[str] = []
    for op_idx, op in enumerate(operators):
        op_type = _safe_name(op.get("type", ""))
        var = f"op_{op_idx}_Op"
        lines.append(f'    local {var} = newEv.addOperator "{op_type}" {op_idx + 1}')
        props = op.get("properties", {})
        for prop_name, prop_val in props.items():
            lines.append(f'    {var}.{prop_name} = {_ms_value(prop_val)}')
        op_names.append(op_type)

    ops_json = ", ".join(f'\\"{o}\\"' for o in op_names)
    lines.append(f'    "{{\\\"success\\\":true,\\\"event\\\":\\\"{safe_evt}\\\",'
                 f'\\\"operatorCount\\\":{len(op_names)},\\\"operators\\\":[{ops_json}]}}"')
    lines.append(')')

    ms = "(\n    " + "\n    ".join(lines) + "\n)"
    return client.send_command(ms).get("result", "")


# ---------------------------------------------------------------------------
# Tool 5: connect_tyflow_events
# ---------------------------------------------------------------------------

@mcp.tool()
def connect_tyflow_events(
    tyflow_name: str,
    source_event: str,
    target_event: str,
    operator_name: str = "Event",
) -> str:
    """Connect two tyFlow events via an Event/Send Out operator.

    Wires an Event (or Send Out) operator in the source event to point
    at the target event.  If the operator does not exist it will be
    created automatically.

    Args:
        tyflow_name: tyFlow object name.
        source_event: Source event name.
        target_event: Target event name.
        operator_name: Name of the routing operator (default "Event").
                       Common values: "Event", "Send Out", "Spawn".
    """
    safe_tf = _safe_name(tyflow_name)
    sa_src = _sa_name(source_event)
    sa_op = _sa_name(operator_name)
    sa_tgt = _sa_name(target_event)
    safe_src = _safe_name(source_event)
    safe_tgt = _safe_name(target_event)
    safe_op = _safe_name(operator_name)

    maxscript = f"""(
    local tfObj = getNodeByName "{safe_tf}"
    if tfObj == undefined then (
        "{{\\\"error\\\":\\\"tyFlow not found: {safe_tf}\\\"}}"
    ) else (
        local opRef = undefined
        try (opRef = tfObj.baseobject[{sa_src}][{sa_op}]) catch ()
        if opRef == undefined then (
            "{{\\\"error\\\":\\\"Operator '{safe_op}' not found in event '{safe_src}'\\\"}}"
        ) else (
            local targetEv = undefined
            try (targetEv = tfObj.baseobject[{sa_tgt}]) catch ()
            if targetEv == undefined then (
                "{{\\\"error\\\":\\\"Target event not found: {safe_tgt}\\\"}}"
            ) else (
                try (opRef.connect targetEv) catch ()
                "{{\\\"success\\\":true,\\\"from\\\":\\\"{safe_src}\\\",\\\"operator\\\":\\\"{safe_op}\\\",\\\"to\\\":\\\"{safe_tgt}\\\"}}"
            )
        )
    )
)"""
    return client.send_command(maxscript).get("result", "")


# ---------------------------------------------------------------------------
# Tool 6: remove_tyflow_element
# ---------------------------------------------------------------------------

@mcp.tool()
def remove_tyflow_element(
    tyflow_name: str,
    event_name: str,
    operator_name: str | None = None,
) -> str:
    """Remove an event or operator from a tyFlow.

    If operator_name is provided, only that operator is removed.
    If operator_name is None, the entire event is removed.

    Args:
        tyflow_name: tyFlow object name.
        event_name: Event name.
        operator_name: Operator to remove (None = remove entire event).
    """
    safe_tf = _safe_name(tyflow_name)
    sa_evt = _sa_name(event_name)
    safe_evt = _safe_name(event_name)

    if operator_name is not None:
        sa_op = _sa_name(operator_name)
        safe_op = _safe_name(operator_name)
        maxscript = f"""(
    local tfObj = getNodeByName "{safe_tf}"
    if tfObj == undefined then (
        "{{\\\"error\\\":\\\"tyFlow not found: {safe_tf}\\\"}}"
    ) else (
        local opRef = undefined
        try (opRef = tfObj.baseobject[{sa_evt}][{sa_op}]) catch ()
        if opRef == undefined then (
            "{{\\\"error\\\":\\\"Operator not found: {safe_op}\\\"}}"
        ) else (
            opRef.remove()
            "{{\\\"success\\\":true,\\\"removed\\\":\\\"operator\\\",\\\"name\\\":\\\"{safe_op}\\\",\\\"event\\\":\\\"{safe_evt}\\\"}}"
        )
    )
)"""
    else:
        maxscript = f"""(
    local tfObj = getNodeByName "{safe_tf}"
    if tfObj == undefined then (
        "{{\\\"error\\\":\\\"tyFlow not found: {safe_tf}\\\"}}"
    ) else (
        local evRef = undefined
        try (evRef = tfObj.baseobject[{sa_evt}]) catch ()
        if evRef == undefined then (
            "{{\\\"error\\\":\\\"Event not found: {safe_evt}\\\"}}"
        ) else (
            evRef.remove()
            "{{\\\"success\\\":true,\\\"removed\\\":\\\"event\\\",\\\"name\\\":\\\"{safe_evt}\\\"}}"
        )
    )
)"""
    return client.send_command(maxscript).get("result", "")


# ---------------------------------------------------------------------------
# Tool 7: set_tyflow_shape
# ---------------------------------------------------------------------------

@mcp.tool()
def set_tyflow_shape(
    tyflow_name: str,
    event_name: str,
    shape_type: str = "sphere",
    operator_name: str = "Shape",
    scale: float = 100.0,
    scale_variation: float = 0.0,
    frequency: float = 100.0,
) -> str:
    """Configure a Shape operator on a tyFlow event.

    Uses the verified shape ID mapping and writes via _tab arrays
    (the ONLY writable path -- single-item props are READ-ONLY).

    Available 3D shapes: triangle, cone, quad/plane, cylinder, sphere,
    pyramid, box/cube, octahedron, geosphere_low, geosphere/geosphere_med,
    geosphere_high, icosahedron.

    Args:
        tyflow_name: tyFlow object name.
        event_name: Event containing the Shape operator.
        shape_type: Shape name (e.g. "sphere", "box", "cylinder").
        operator_name: Shape operator name (default "Shape").
        scale: Shape scale percentage (default 100).
        scale_variation: Scale variation percentage (default 0).
        frequency: Distribution frequency (default 100).
    """
    safe_tf = _safe_name(tyflow_name)
    sa_evt = _sa_name(event_name)
    sa_op = _sa_name(operator_name)

    shape_id = SHAPE_3D_IDS.get(shape_type.lower(), SHAPE_3D_IDS.get("sphere", 4))
    safe_shape = _safe_name(shape_type)

    maxscript = f"""(
    local tfObj = getNodeByName "{safe_tf}"
    if tfObj == undefined then (
        "{{\\\"error\\\":\\\"tyFlow not found: {safe_tf}\\\"}}"
    ) else (
        local shapeOp = undefined
        try (shapeOp = tfObj.baseobject[{sa_evt}][{sa_op}]) catch ()
        if shapeOp == undefined then (
            "{{\\\"error\\\":\\\"Shape operator not found\\\"}}"
        ) else (
            shapeOp.shape_type_tab = #(1)  -- sets shapeMode to 3D automatically
            shapeOp.type_3d_ID_tab = #({shape_id})
            shapeOp.frequency_tab = #({frequency:.4f})
            shapeOp.scaleVal_tab = #({scale:.4f})
            shapeOp.scaleVariation_tab = #({scale_variation:.4f})
            "{{\\\"success\\\":true,\\\"shape\\\":\\\"{safe_shape}\\\",\\\"shapeId\\\":{shape_id},\\\"scale\\\":{scale:.1f}}}"
        )
    )
)"""
    return client.send_command(maxscript).get("result", "")


# ---------------------------------------------------------------------------
# Tool 8: set_tyflow_physx
# ---------------------------------------------------------------------------

@mcp.tool()
def set_tyflow_physx(
    tyflow_name: str,
    gravity_enabled: bool | None = None,
    gravity_value: float | None = None,
    ground_collider: bool | None = None,
    ground_collider_height: float | None = None,
    ground_collider_restitution: float | None = None,
    ground_collider_static_friction: float | None = None,
    ground_collider_dynamic_friction: float | None = None,
    substeps: int | None = None,
    pos_iterations: int | None = None,
    vel_iterations: int | None = None,
    ccd: bool | None = None,
    enhanced_determinism: bool | None = None,
) -> str:
    """Configure PhysX solver settings on a tyFlow object.

    Only provided (non-None) parameters are changed -- omitted settings
    are left at their current values.

    Args:
        tyflow_name: tyFlow object name.
        gravity_enabled: Enable/disable PhysX gravity.
        gravity_value: Gravity strength (negative = down, e.g. -980).
        ground_collider: Enable built-in ground collider plane.
        ground_collider_height: Ground plane Z height.
        ground_collider_restitution: Ground bounce coefficient.
        ground_collider_static_friction: Ground static friction.
        ground_collider_dynamic_friction: Ground dynamic friction.
        substeps: PhysX substeps per frame.
        pos_iterations: Position solver iterations.
        vel_iterations: Velocity solver iterations.
        ccd: Enable continuous collision detection.
        enhanced_determinism: Enable enhanced determinism mode.
    """
    safe_tf = _safe_name(tyflow_name)

    # Map Python param -> MAXScript property
    _prop_map: list[tuple[str, str, object]] = [
        ("physXGravityEnabled", "bool", gravity_enabled),
        ("physXGravityValue", "float", gravity_value),
        ("physXGroundCollider", "bool", ground_collider),
        ("physXGroundColliderHeight", "float", ground_collider_height),
        ("physXGroundColliderRestitution", "float", ground_collider_restitution),
        ("physXGroundColliderSFriction", "float", ground_collider_static_friction),
        ("physXGroundColliderDFriction", "float", ground_collider_dynamic_friction),
        ("physXSubsteps", "int", substeps),
        ("physXPosIterations", "int", pos_iterations),
        ("physXVelIterations", "int", vel_iterations),
        ("physXCCD", "bool", ccd),
        ("physXEnhancedDeterminism", "bool", enhanced_determinism),
    ]

    prop_lines: list[str] = []
    set_names: list[str] = []
    for ms_prop, _typ, val in _prop_map:
        if val is None:
            continue
        prop_lines.append(f"        tf.{ms_prop} = {_ms_value(val)}")
        set_names.append(ms_prop)

    if not prop_lines:
        prop_lines.append("        -- no properties to set")

    props_json = ", ".join(f'\\"{p}\\"' for p in set_names)

    maxscript = f"""(
    local tfObj = getNodeByName "{safe_tf}"
    if tfObj == undefined then (
        "{{\\\"error\\\":\\\"tyFlow not found: {safe_tf}\\\"}}"
    ) else (
        local tf = tfObj.baseobject
{chr(10).join(prop_lines)}
        "{{\\\"success\\\":true,\\\"name\\\":\\\"" + tfObj.name + "\\\",\\\"propertiesSet\\\":[{props_json}]}}"
    )
)"""
    return client.send_command(maxscript).get("result", "")


# ---------------------------------------------------------------------------
# Tool 9: add_tyflow_collision
# ---------------------------------------------------------------------------

@mcp.tool()
def add_tyflow_collision(
    tyflow_name: str,
    event_name: str,
    collision_objects: list[str],
    operator_name: str = "PhysX Collision",
    hull_mode: int = 3,
    restitution: float = 0.3,
    static_friction: float = 0.5,
    dynamic_friction: float = 0.3,
) -> str:
    """Add collision objects to a PhysX Collision operator on a tyFlow event.

    If the operator does not exist it will report an error -- add a
    "PhysX Collision" operator first via create_tyflow or add_tyflow_event.

    Hull modes: 0=Sphere, 1=Box, 2=Convex Hull, 3=Mesh (default).

    Args:
        tyflow_name: tyFlow object name.
        event_name: Event containing the PhysX Collision operator.
        collision_objects: List of scene object names to use as colliders.
        operator_name: Operator name (default "PhysX Collision").
        hull_mode: Collision hull mode (0-3).
        restitution: Bounce coefficient.
        static_friction: Static friction.
        dynamic_friction: Dynamic friction.
    """
    safe_tf = _safe_name(tyflow_name)
    sa_evt = _sa_name(event_name)
    sa_op = _sa_name(operator_name)
    names_arr = _name_array(collision_objects)

    maxscript = f"""(
    local tfObj = getNodeByName "{safe_tf}"
    if tfObj == undefined then (
        "{{\\\"error\\\":\\\"tyFlow not found: {safe_tf}\\\"}}"
    ) else (
        local collOp = undefined
        try (collOp = tfObj.baseobject[{sa_evt}][{sa_op}]) catch ()
        if collOp == undefined then (
            "{{\\\"error\\\":\\\"PhysX Collision operator not found in event\\\"}}"
        ) else (
            local colliderNames = {names_arr}
            local colliderNodes = #()
            local missingNames = #()
            for cName in colliderNames do (
                local cNode = getNodeByName cName
                if cNode != undefined then append colliderNodes cNode
                else append missingNames cName
            )
            if missingNames.count > 0 then (
                local missStr = ""
                for i = 1 to missingNames.count do (
                    if i > 1 do missStr += ","
                    missStr += "\\\"" + missingNames[i] + "\\\""
                )
                "{{\\\"error\\\":\\\"Objects not found\\\",\\\"missing\\\":[" + missStr + "]}}"
            ) else (
                collOp.objectlist = colliderNodes
                try (collOp.hullMode = {hull_mode}) catch ()
                try (collOp.restitution = {restitution:.6f}) catch ()
                try (collOp.staticFriction = {static_friction:.6f}) catch ()
                try (collOp.dynamicFriction = {dynamic_friction:.6f}) catch ()
                "{{\\\"success\\\":true,\\\"colliderCount\\\":" + (colliderNodes.count as string) + "}}"
            )
        )
    )
)"""
    return client.send_command(maxscript).get("result", "")


# ---------------------------------------------------------------------------
# Tool 10: get_tyflow_particles
# ---------------------------------------------------------------------------

@mcp.tool()
def get_tyflow_particles(
    tyflow_name: str,
    properties: list[str] | None = None,
    max_particles: int = 100,
    frame: int | None = None,
) -> str:
    """Get particle data from a tyFlow system.

    Reads particle positions, velocities, ages, etc.  Limited to
    max_particles entries to avoid huge JSON payloads.

    Available properties: positions, velocities, ages, ids, scales, masses.

    Args:
        tyflow_name: tyFlow object name.
        properties: List of data types to read (default: ["positions"]).
        max_particles: Maximum particles to return (default 100, 0=all).
        frame: Frame to sample (None = current time).
    """
    safe_tf = _safe_name(tyflow_name)
    props = properties or ["positions"]

    frame_line = ""
    if frame is not None:
        frame_line = f"sliderTime = {frame}f"

    # Build data extraction blocks
    data_blocks: list[str] = []
    for prop in props:
        p = prop.lower()
        if p == "positions":
            data_blocks.append("""
            local allPos = tfObj.getAllParticlePositions()
            json += ",\\\"positions\\\":["
            for i = 1 to (amin limit allPos.count) do (
                if i > 1 do json += ","
                local pp = allPos[i]
                json += "[" + (pp.x as string) + "," + (pp.y as string) + "," + (pp.z as string) + "]"
            )
            json += "]"
""")
        elif p == "velocities":
            data_blocks.append("""
            local allVel = tfObj.getAllParticleVelocities()
            json += ",\\\"velocities\\\":["
            for i = 1 to (amin limit allVel.count) do (
                if i > 1 do json += ","
                local vv = allVel[i]
                json += "[" + (vv.x as string) + "," + (vv.y as string) + "," + (vv.z as string) + "]"
            )
            json += "]"
""")
        elif p == "ages":
            data_blocks.append("""
            local allAge = tfObj.getAllParticleAges()
            json += ",\\\"ages\\\":["
            for i = 1 to (amin limit allAge.count) do (
                if i > 1 do json += ","
                json += (allAge[i] as string)
            )
            json += "]"
""")
        elif p == "ids":
            data_blocks.append("""
            local allID = tfObj.getAllParticleIDs()
            json += ",\\\"ids\\\":["
            for i = 1 to (amin limit allID.count) do (
                if i > 1 do json += ","
                json += (allID[i] as string)
            )
            json += "]"
""")
        elif p == "scales":
            data_blocks.append("""
            local allScl = tfObj.getAllParticleScales()
            json += ",\\\"scales\\\":["
            for i = 1 to (amin limit allScl.count) do (
                if i > 1 do json += ","
                local ss = allScl[i]
                json += "[" + (ss.x as string) + "," + (ss.y as string) + "," + (ss.z as string) + "]"
            )
            json += "]"
""")
        elif p == "masses":
            data_blocks.append("""
            local allMass = tfObj.getAllParticleMasses()
            json += ",\\\"masses\\\":["
            for i = 1 to (amin limit allMass.count) do (
                if i > 1 do json += ","
                json += (allMass[i] as string)
            )
            json += "]"
""")

    data_code = "".join(data_blocks)

    maxscript = f"""(
    local tfObj = getNodeByName "{safe_tf}"
    if tfObj == undefined then (
        "{{\\\"error\\\":\\\"tyFlow not found: {safe_tf}\\\"}}"
    ) else (
        {frame_line}
        tfObj.updateParticles currentTime
        local n = tfObj.numParticles()
        local limit = if {max_particles} > 0 then {max_particles} else n

        local json = "{{\\\"name\\\":\\\"" + tfObj.name + "\\\""
        json += ",\\\"frame\\\":" + ((currentTime.frame as integer) as string)
        json += ",\\\"particleCount\\\":" + (n as string)
        json += ",\\\"returnedCount\\\":" + ((amin limit n) as string)
{data_code}
        json += "}}"
        json
    )
)"""
    return client.send_command(maxscript).get("result", "")


# ---------------------------------------------------------------------------
# Tool 11: get_tyflow_particle_count
# ---------------------------------------------------------------------------

@mcp.tool()
def get_tyflow_particle_count(
    tyflow_name: str,
    frame: int | None = None,
) -> str:
    """Quick particle count check on a tyFlow (no data serialization).

    Args:
        tyflow_name: tyFlow object name.
        frame: Frame to sample (None = current time).
    """
    safe_tf = _safe_name(tyflow_name)

    frame_line = ""
    if frame is not None:
        frame_line = f"sliderTime = {frame}f"

    maxscript = f"""(
    local tfObj = getNodeByName "{safe_tf}"
    if tfObj == undefined then (
        "{{\\\"error\\\":\\\"tyFlow not found: {safe_tf}\\\"}}"
    ) else (
        {frame_line}
        tfObj.updateParticles currentTime
        local n = tfObj.numParticles()
        "{{\\\"name\\\":\\\"" + tfObj.name + "\\\",\\\"particleCount\\\":" + (n as string) + ",\\\"frame\\\":" + ((currentTime.frame as integer) as string) + "}}"
    )
)"""
    return client.send_command(maxscript).get("result", "")


# ---------------------------------------------------------------------------
# Tool 12: reset_tyflow_simulation
# ---------------------------------------------------------------------------

@mcp.tool()
def reset_tyflow_simulation(
    tyflow_name: str,
) -> str:
    """Reset the simulation cache on a tyFlow object.

    This clears all cached particle data and resets the simulation
    back to the start frame.

    Args:
        tyflow_name: tyFlow object name.
    """
    safe_tf = _safe_name(tyflow_name)

    maxscript = f"""(
    local tfObj = getNodeByName "{safe_tf}"
    if tfObj == undefined then (
        "{{\\\"error\\\":\\\"tyFlow not found: {safe_tf}\\\"}}"
    ) else (
        tfObj.reset_simulation()
        "{{\\\"success\\\":true,\\\"name\\\":\\\"" + tfObj.name + "\\\"}}"
    )
)"""
    return client.send_command(maxscript).get("result", "")


# ---------------------------------------------------------------------------
# Tool 13: create_tyflow_preset
# ---------------------------------------------------------------------------

@mcp.tool()
def create_tyflow_preset(
    name: str,
    preset: str,
    position: list[float] | None = None,
    particle_count: int | None = None,
    shape: str | None = None,
    scale: float = 100.0,
    speed: float | None = None,
    lifetime_frames: int | None = None,
) -> str:
    """Create a tyFlow with a preset particle effect configuration.

    Presets: fountain, rain, explosion, snow, debris, confetti, sparks, smoke.

    Each preset builds appropriate events, operators, and settings for the
    named effect.  Override individual parameters to customize.

    Args:
        name: tyFlow object name.
        preset: Preset name (fountain, rain, explosion, snow, debris,
                confetti, sparks, smoke).
        position: World position [x, y, z].
        particle_count: Override default particle count.
        shape: Override shape type (e.g. "sphere", "box").
        scale: Shape scale percentage (default 100).
        speed: Override speed magnitude.
        lifetime_frames: Override particle lifetime in frames.
    """
    pos = position or [0.0, 0.0, 0.0]
    safe = _safe_name(name)
    p = preset.lower()

    # Preset defaults
    _defaults: dict[str, dict] = {
        "fountain": {
            "count": 1000, "birth_mode": 1, "birth_per_frame": 30.0,
            "speed_mag": 500.0, "speed_var": 20.0, "speed_dir": 0, "speed_reverse": False,
            "gravity": -1.0, "shape_id": SHAPE_3D_IDS.get("sphere", 4),
            "shape_name": "sphere", "shape_scale": 20.0, "shape_scale_var": 10.0,
            "has_spin": False, "has_kill_age": False, "kill_age": 100,
        },
        "rain": {
            "count": 2000, "birth_mode": 1, "birth_per_frame": 50.0,
            "speed_mag": 500.0, "speed_var": 10.0, "speed_dir": 0, "speed_reverse": True,
            "gravity": -0.5, "shape_id": SHAPE_3D_IDS.get("quad", 2),
            "shape_name": "quad", "shape_scale": 5.0, "shape_scale_var": 10.0,
            "has_spin": False, "has_kill_age": True, "kill_age": 60,
        },
        "explosion": {
            "count": 500, "birth_mode": 0, "birth_per_frame": 0.0,
            "speed_mag": 800.0, "speed_var": 40.0, "speed_dir": 3, "speed_reverse": False,
            "gravity": -1.0, "shape_id": SHAPE_3D_IDS.get("geosphere_low", 8),
            "shape_name": "geosphere_low", "shape_scale": 30.0, "shape_scale_var": 50.0,
            "has_spin": True, "has_kill_age": False, "kill_age": 100,
        },
        "snow": {
            "count": 1000, "birth_mode": 1, "birth_per_frame": 20.0,
            "speed_mag": 100.0, "speed_var": 30.0, "speed_dir": 0, "speed_reverse": True,
            "gravity": -0.2, "shape_id": SHAPE_3D_IDS.get("quad", 2),
            "shape_name": "quad", "shape_scale": 10.0, "shape_scale_var": 20.0,
            "has_spin": True, "has_kill_age": True, "kill_age": 200,
        },
        "debris": {
            "count": 200, "birth_mode": 0, "birth_per_frame": 0.0,
            "speed_mag": 400.0, "speed_var": 50.0, "speed_dir": 3, "speed_reverse": False,
            "gravity": -1.0, "shape_id": SHAPE_3D_IDS.get("cube", 6),
            "shape_name": "cube", "shape_scale": 50.0, "shape_scale_var": 60.0,
            "has_spin": True, "has_kill_age": False, "kill_age": 100,
        },
        "confetti": {
            "count": 300, "birth_mode": 1, "birth_per_frame": 10.0,
            "speed_mag": 100.0, "speed_var": 50.0, "speed_dir": 3, "speed_reverse": False,
            "gravity": -0.3, "shape_id": SHAPE_3D_IDS.get("quad", 2),
            "shape_name": "quad", "shape_scale": 15.0, "shape_scale_var": 30.0,
            "has_spin": True, "has_kill_age": True, "kill_age": 150,
        },
        "sparks": {
            "count": 500, "birth_mode": 0, "birth_per_frame": 0.0,
            "speed_mag": 1200.0, "speed_var": 40.0, "speed_dir": 3, "speed_reverse": False,
            "gravity": -1.5, "shape_id": SHAPE_3D_IDS.get("sphere", 4),
            "shape_name": "sphere", "shape_scale": 3.0, "shape_scale_var": 20.0,
            "has_spin": False, "has_kill_age": True, "kill_age": 30,
        },
        "smoke": {
            "count": 200, "birth_mode": 1, "birth_per_frame": 5.0,
            "speed_mag": 50.0, "speed_var": 30.0, "speed_dir": 0, "speed_reverse": False,
            "gravity": 0.0, "shape_id": SHAPE_3D_IDS.get("sphere", 4),
            "shape_name": "sphere", "shape_scale": 80.0, "shape_scale_var": 30.0,
            "has_spin": True, "has_kill_age": True, "kill_age": 120,
        },
    }

    if p not in _defaults:
        available = ", ".join(sorted(_defaults.keys()))
        return f'{{"error": "Unknown preset: {preset}. Available: {available}"}}'

    d = _defaults[p]

    # Apply user overrides
    count = particle_count if particle_count is not None else d["count"]
    spd = speed if speed is not None else d["speed_mag"]
    lifetime = lifetime_frames if lifetime_frames is not None else d["kill_age"]

    if shape:
        shape_lower = shape.lower()
        shape_id = SHAPE_3D_IDS.get(shape_lower, d["shape_id"])
        shape_name = shape_lower
    else:
        shape_id = d["shape_id"]
        shape_name = d["shape_name"]

    shape_scale = scale if scale != 100.0 else d["shape_scale"]
    shape_scale_var = d["shape_scale_var"]

    # Build MAXScript
    lines: list[str] = [
        f'local tfObj = tyflow()',
        f'tfObj.name = "{safe}"',
        f'tfObj.pos = [{pos[0]}, {pos[1]}, {pos[2]}]',
        '',
        f'local ev1 = tfObj.addEvent()',
        f'ev1.setName "{safe}_Event"',
        '',
    ]

    op_idx = 1

    # Birth operator
    lines.append(f'local birth_Op = ev1.addOperator "Birth" {op_idx}')
    op_idx += 1
    if d["birth_mode"] == 0:
        # Total mode (burst)
        lines.append(f'birth_Op.birthMode = 0')
        lines.append(f'birth_Op.birthTotal = {count}')
        lines.append(f'birth_Op.birthStart = 0')
        lines.append(f'birth_Op.birthEndEnable = true')
        lines.append(f'birth_Op.birthEnd = 2')
    else:
        # Per-frame mode
        per_frame = d["birth_per_frame"]
        lines.append(f'birth_Op.birthMode = 1')
        lines.append(f'birth_Op.birthPerFrame = {per_frame:.1f}')
        lines.append(f'birth_Op.birthStart = 0')

    # Speed operator
    lines.append('')
    lines.append(f'local speed_Op = ev1.addOperator "Speed" {op_idx}')
    op_idx += 1
    lines.append(f'speed_Op.magnitude = {spd:.1f}')
    lines.append(f'speed_Op.magnitudeVariation = {d["speed_var"]:.1f}')
    lines.append(f'speed_Op.directionMode = {d["speed_dir"]}')
    if d.get("speed_reverse"):
        lines.append('try (speed_Op.directionReverse = true) catch ()')

    # Force operator (if gravity or noise)
    if d["gravity"] != 0.0:
        lines.append('')
        lines.append(f'local force_Op = ev1.addOperator "Force" {op_idx}')
        op_idx += 1
        lines.append(f'force_Op.gravityStrength = {d["gravity"]:.2f}')
        if p == "snow" or p == "confetti":
            # Add some wind noise for snow and confetti
            lines.append('try (force_Op.windStrength = 30.0) catch ()')
        if p == "smoke":
            lines.append('try (force_Op.windStrength = 20.0) catch ()')

    # Spin operator (optional)
    if d.get("has_spin"):
        lines.append('')
        lines.append(f'local spin_Op = ev1.addOperator "Spin" {op_idx}')
        op_idx += 1
        if p in ("confetti", "snow"):
            lines.append('spin_Op.spinX = 50.0')
            lines.append('spin_Op.spinY = 50.0')
            lines.append('spin_Op.spinZ = 50.0')

    # Kill Age operator (optional)
    if d.get("has_kill_age"):
        lines.append('')
        lines.append(f'local killAge_Op = ev1.addOperator "Kill Age" {op_idx}')
        op_idx += 1
        lines.append(f'try (killAge_Op.age = {lifetime}) catch ()')
        lines.append(f'try (killAge_Op.ageVariation = 20) catch ()')

    # Shape operator
    lines.append('')
    lines.append(f'local shape_Op = ev1.addOperator "Shape" {op_idx}')
    op_idx += 1
    lines.append(f'shape_Op.shape_type_tab = #(1)')  # sets shapeMode to 3D automatically
    lines.append(f'shape_Op.type_3d_ID_tab = #({shape_id})')
    lines.append(f'shape_Op.frequency_tab = #(100.0)')
    lines.append(f'shape_Op.scaleVal_tab = #({shape_scale:.1f})')
    lines.append(f'shape_Op.scaleVariation_tab = #({shape_scale_var:.1f})')

    # Display operator
    lines.append('')
    lines.append(f'local display_Op = ev1.addOperator "Display" {op_idx}')
    op_idx += 1
    lines.append('display_Op.displayMode = 2')

    # PhysX for debris preset
    if p == "debris":
        lines.append('')
        lines.append('tfObj.physXGravityEnabled = true')
        lines.append('tfObj.physXGravityValue = -980.0')
        lines.append('tfObj.physXGroundCollider = true')
        lines.append('tfObj.physXGroundColliderHeight = 0.0')
        lines.append('tfObj.physXSubsteps = 8')
        lines.append('')
        lines.append(f'local physxShape_Op = ev1.addOperator "PhysX Shape" {op_idx}')
        op_idx += 1
        lines.append('try (physxShape_Op.hullMode = 0) catch ()')
        lines.append('try (physxShape_Op.restitution = 0.4) catch ()')

    # Reset simulation
    lines.append('')
    lines.append('tfObj.reset_simulation()')

    # JSON response
    lines.append('')
    lines.append(f'"{{\\\"name\\\":\\\"" + tfObj.name + "\\\",\\\"preset\\\":\\\"{p}\\\",'
                 f'\\\"shape\\\":\\\"{shape_name}\\\",\\\"shapeId\\\":{shape_id}}}"')

    ms = "(\n    " + "\n    ".join(lines) + "\n)"
    return client.send_command(ms).get("result", "")


# ---------------------------------------------------------------------------
# Inferno operator list (VERIFIED 2026-03-22 via live introspection, tyFlow v2.003)
# ---------------------------------------------------------------------------

INFERNO_OPERATORS: list[str] = [
    "Birth Inferno",
    "Inferno Emitter",
    "Inferno Bounds",
    "Inferno Display",
    "Inferno Collider",
    "Inferno Color",
    "Inferno Spawn",
    "Inferno Properties",
    "Inferno Recall",
    "Export Inferno",
    "Inferno Force",
    "Inferno Temperature",
    "Inferno Density",
    "Inferno Vorticity",
    "Inferno Scale",
]


# ---------------------------------------------------------------------------
# Tool 14: get_tyflow_volume_data
# ---------------------------------------------------------------------------

@mcp.tool()
def get_tyflow_volume_data(
    tyflow_name: str,
    positions: list[list[float]],
    scalar_types: list[str] | None = None,
    vector_types: list[str] | None = None,
    temperature_units: str = "kelvin",
) -> str:
    """Sample scalar/vector data from a tyFlow Inferno fluid grid at world-space positions.

    Requires tyFlow 2.0+ with an active Inferno simulation. Calls
    updateVolumes() / releaseVolumes() to safely access GPU volume data.

    Args:
        tyflow_name: Name of the tyFlow object with Inferno simulation.
        positions: List of [x, y, z] world-space sample points.
        scalar_types: Scalars to sample -- any of "density", "fuel", "temperature".
        vector_types: Vectors to sample -- any of "color", "velocity".
        temperature_units: Unit for temperature values -- "celsius", "fahrenheit", or "kelvin".
    """
    safe = _safe_name(tyflow_name)
    scalar_map = {"density": 0, "fuel": 1, "temperature": 2}
    vector_map = {"color": 0, "velocity": 1}
    temp_unit_map = {"celsius": 1, "fahrenheit": 2, "kelvin": 3}

    scalars = scalar_types or []
    vectors = vector_types or []
    temp_unit = temp_unit_map.get(temperature_units, 3)

    lines: list[str] = []
    lines.append(f'local tfObj = getNodeByName "{safe}"')
    lines.append('if tfObj == undefined then (')
    lines.append(f'  "{{\\"error\\":\\"tyFlow \\\\\\"{safe}\\\\\\" not found\\"}}"')
    lines.append(') else (')
    lines.append('  tfObj.updateVolumes()')
    lines.append('  local json = "{\\"samples\\":["')

    for i, pos in enumerate(positions):
        x, y, z = float(pos[0]), float(pos[1]), float(pos[2])
        lines.append(f'  local p{i} = [{x:.4f},{y:.4f},{z:.4f}]')
        if i > 0:
            lines.append('  json += ","')
        lines.append(f'  json += "{{\\"pos\\":[{x:.4f},{y:.4f},{z:.4f}]"')

        for stype in scalars:
            sid = scalar_map.get(stype)
            if sid is None:
                continue
            lines.append(f'  local s{i}_{stype} = try (tfObj.getVolumeScalar p{i} {sid}) catch (0.0)')
            if stype == "temperature":
                lines.append(f'  s{i}_{stype} = try (tfObj.convertVolumeTemperature s{i}_{stype} {temp_unit}) catch (s{i}_{stype})')
            lines.append(f'  json += ",\\"{stype}\\":" + (s{i}_{stype} as string)')

        for vtype in vectors:
            vid = vector_map.get(vtype)
            if vid is None:
                continue
            lines.append(f'  local v{i}_{vtype} = try (tfObj.getVolumeVector p{i} {vid}) catch ([0,0,0])')
            lines.append(f'  json += ",\\"{vtype}\\":[" + (v{i}_{vtype}.x as string) + "," + (v{i}_{vtype}.y as string) + "," + (v{i}_{vtype}.z as string) + "]"')

        lines.append('  json += "}"')

    lines.append('  json += "]}"')
    lines.append('  tfObj.releaseVolumes()')
    lines.append('  json')
    lines.append(')')

    ms = "(\n    " + "\n    ".join(lines) + "\n)"
    return client.send_command(ms).get("result", "")


# ---------------------------------------------------------------------------
# Tool 15: convert_tyflow_temperature
# ---------------------------------------------------------------------------

@mcp.tool()
def convert_tyflow_temperature(
    tyflow_name: str,
    temperature: float,
    from_units: str,
    to_units: str,
) -> str:
    """Convert a temperature value between units using tyFlow's built-in converter.

    Uses the tyFlow volume API's convertVolumeTemperature function to ensure
    consistency with Inferno simulation temperature values.

    Args:
        tyflow_name: Name of any tyFlow object (needed to access the API).
        temperature: The temperature value to convert.
        from_units: Source units -- "celsius", "fahrenheit", or "kelvin".
        to_units: Target units -- "celsius", "fahrenheit", or "kelvin".
    """
    safe = _safe_name(tyflow_name)
    unit_map = {"celsius": 1, "fahrenheit": 2, "kelvin": 3}
    from_id = unit_map.get(from_units)
    to_id = unit_map.get(to_units)
    if from_id is None or to_id is None:
        return '{"error":"Invalid units. Use celsius, fahrenheit, or kelvin."}'

    ms = f"""(
    local tfObj = getNodeByName "{safe}"
    if tfObj == undefined then (
        "{{\\"error\\":\\"tyFlow \\\\\\"{safe}\\\\\\" not found\\"}}"
    ) else (
        local normalized = try (tfObj.convertVolumeTemperature {temperature:.6f} {from_id}) catch (undefined)
        if normalized == undefined then (
            "{{\\"error\\":\\"convertVolumeTemperature failed -- is tyFlow 2.0+ installed?\\"}}"
        ) else (
            local result = try (tfObj.convertVolumeTemperature normalized {to_id}) catch (undefined)
            if result == undefined then (
                "{{\\"error\\":\\"Temperature conversion failed\\"}}"
            ) else (
                "{{\\"from_value\\":" + ({temperature:.6f} as string) + ",\\"from_units\\":\\"{from_units}\\",\\"to_value\\":" + (result as string) + ",\\"to_units\\":\\"{to_units}\\"}}"
            )
        )
    )
)"""
    return client.send_command(ms).get("result", "")


# ---------------------------------------------------------------------------
# Tool 16: create_tyflow_inferno
# ---------------------------------------------------------------------------

# Inferno preset defaults
_INFERNO_PRESETS: dict[str, dict] = {
    "fire": {
        "voxelSize": 2.0,
        "temperatureKelvin": 1500.0,
        "temperatureBuoyancy": 1.0,
        "temperatureCooling": 0.5,
        "dissipation": 0.02,
        "vorticity": 0.5,
        "fuelEnabled": True,
        "fuel": 1.0,
        "fuelBurnTemperatureKelvin": 800.0,
        "fuelIgnitionTemperatureKelvin": 400.0,
        "densityEnabled": True,
        "density": 0.5,
        "emissionThickness": 1.0,
    },
    "smoke": {
        "voxelSize": 3.0,
        "temperatureKelvin": 400.0,
        "temperatureBuoyancy": 0.5,
        "temperatureCooling": 0.8,
        "dissipation": 0.01,
        "vorticity": 0.3,
        "fuelEnabled": False,
        "fuel": 0.0,
        "densityEnabled": True,
        "density": 1.0,
        "emissionThickness": 2.0,
    },
    "explosion_smoke": {
        "voxelSize": 2.5,
        "temperatureKelvin": 2500.0,
        "temperatureBuoyancy": 2.0,
        "temperatureCooling": 0.3,
        "dissipation": 0.05,
        "vorticity": 0.8,
        "fuelEnabled": True,
        "fuel": 2.0,
        "fuelBurnTemperatureKelvin": 1200.0,
        "fuelIgnitionTemperatureKelvin": 600.0,
        "densityEnabled": True,
        "density": 1.5,
        "emissionThickness": 3.0,
    },
    "campfire": {
        "voxelSize": 1.5,
        "temperatureKelvin": 1000.0,
        "temperatureBuoyancy": 0.8,
        "temperatureCooling": 0.6,
        "dissipation": 0.03,
        "vorticity": 0.4,
        "fuelEnabled": True,
        "fuel": 0.8,
        "fuelBurnTemperatureKelvin": 700.0,
        "fuelIgnitionTemperatureKelvin": 350.0,
        "densityEnabled": True,
        "density": 0.3,
        "emissionThickness": 0.5,
    },
}


@mcp.tool()
def create_tyflow_inferno(
    name: str = "tyInferno001",
    preset: str | None = None,
    position: list[float] | None = None,
    emitter_objects: list[str] | None = None,
    voxel_size: float = 2.0,
    temperature: float = 1500.0,
    buoyancy: float = 1.0,
    cooling: float = 0.5,
    dissipation: float = 0.02,
    vorticity: float = 0.5,
    enable_collision: bool = False,
    collision_objects: list[str] | None = None,
    enable_ground: bool = False,
    ground_height: float = 0.0,
    enable_export: bool = False,
    export_path: str | None = None,
    reset_simulation: bool = True,
    open_editor: bool = False,
) -> str:
    """Create a tyFlow Inferno (Zenith) smoke/fire simulation.

    Builds a complete Inferno event with Birth Inferno, Emitter, Bounds,
    Display, and optional Collider/Export operators. Requires tyFlow 2.0+.

    Args:
        name: Name for the new tyFlow object.
        preset: Optional preset -- "fire", "smoke", "explosion_smoke", or "campfire".
            Overrides voxel_size/temperature/buoyancy/cooling/dissipation/vorticity defaults.
        position: World position [x, y, z] for the tyFlow icon.
        emitter_objects: Scene object names to use as emission sources.
        voxel_size: Simulation voxel size (smaller = more detail, more VRAM).
        temperature: Emission temperature in kelvin.
        buoyancy: Temperature buoyancy strength.
        cooling: Temperature cooling rate.
        dissipation: Density dissipation rate.
        vorticity: Vorticity confinement strength.
        enable_collision: Add an Inferno Collider operator.
        collision_objects: Scene objects for collision.
        enable_ground: Add built-in ground plane collider.
        ground_height: Ground plane height.
        enable_export: Add an Export Inferno operator.
        export_path: VDB export output path.
        reset_simulation: Reset simulation after creation.
        open_editor: Open the tyFlow editor window.
    """
    safe = _safe_name(name)

    # Apply preset defaults
    if preset and preset in _INFERNO_PRESETS:
        p = _INFERNO_PRESETS[preset]
        voxel_size = p.get("voxelSize", voxel_size)
        temperature = p.get("temperatureKelvin", temperature)
        buoyancy = p.get("temperatureBuoyancy", buoyancy)
        cooling = p.get("temperatureCooling", cooling)
        dissipation = p.get("dissipation", dissipation)
        vorticity = p.get("vorticity", vorticity)

    lines: list[str] = []
    lines.append(f'local tfObj = tyflow()')
    lines.append(f'tfObj.name = "{safe}"')

    if position:
        x, y, z = float(position[0]), float(position[1]), float(position[2])
        lines.append(f'tfObj.pos = [{x:.4f},{y:.4f},{z:.4f}]')

    # Create Inferno event
    lines.append('local ev1 = tfObj.addEvent()')
    lines.append('ev1.setName "Inferno"')
    lines.append('local opIdx = 1')

    # Birth Inferno -- version check
    lines.append('local birthOp = undefined')
    lines.append('try (birthOp = ev1.addOperator "Birth Inferno" opIdx) catch ()')
    lines.append('if birthOp == undefined then (')
    lines.append('  delete tfObj')
    lines.append('  "{\\"error\\":\\"Inferno operators require tyFlow 2.0 (Zenith). Your version does not support them.\\"}"')
    lines.append(') else (')
    lines.append('  opIdx += 1')

    # Configure Birth Inferno solver
    lines.append(f'  try (birthOp.voxelSize = {voxel_size:.4f}) catch ()')
    lines.append(f'  try (birthOp.temperatureBuoyancy = {buoyancy:.6f}) catch ()')
    lines.append(f'  try (birthOp.temperatureCooling = {cooling:.6f}) catch ()')
    lines.append(f'  try (birthOp.dissipation = {dissipation:.6f}) catch ()')
    lines.append(f'  try (birthOp.vorticity = {vorticity:.6f}) catch ()')

    # Fuel settings from preset
    if preset and preset in _INFERNO_PRESETS:
        p = _INFERNO_PRESETS[preset]
        if p.get("fuelBurnTemperatureKelvin"):
            lines.append(f'  try (birthOp.fuelBurnTemperatureKelvin = {p["fuelBurnTemperatureKelvin"]:.4f}) catch ()')
        if p.get("fuelIgnitionTemperatureKelvin"):
            lines.append(f'  try (birthOp.fuelIgnitionTemperatureKelvin = {p["fuelIgnitionTemperatureKelvin"]:.4f}) catch ()')

    # Inferno Emitter
    lines.append('  local emitterOp = ev1.addOperator "Inferno Emitter" opIdx')
    lines.append('  opIdx += 1')
    lines.append('  try (emitterOp.densityEnabled = true) catch ()')

    if preset and preset in _INFERNO_PRESETS:
        p = _INFERNO_PRESETS[preset]
        lines.append(f'  try (emitterOp.density = {p.get("density", 1.0):.4f}) catch ()')
        lines.append(f'  try (emitterOp.emissionThickness = {p.get("emissionThickness", 1.0):.4f}) catch ()')
        if p.get("fuelEnabled"):
            lines.append('  try (emitterOp.fuelEnabled = true) catch ()')
            lines.append(f'  try (emitterOp.fuel = {p.get("fuel", 1.0):.4f}) catch ()')

    lines.append('  try (emitterOp.temperatureEnabled = true) catch ()')
    lines.append(f'  try (emitterOp.temperatureKelvin = {temperature:.4f}) catch ()')

    # Assign emitter objects
    if emitter_objects:
        obj_refs = " ".join(f'(getNodeByName "{_safe_name(o)}")' for o in emitter_objects)
        lines.append(f'  try (emitterOp.objectList = #({obj_refs})) catch ()')

    # Inferno Bounds
    lines.append('  local boundsOp = ev1.addOperator "Inferno Bounds" opIdx')
    lines.append('  opIdx += 1')

    # Inferno Display
    lines.append('  local displayOp = ev1.addOperator "Inferno Display" opIdx')
    lines.append('  opIdx += 1')
    lines.append('  try (displayOp.showSmoke = true) catch ()')
    lines.append('  try (displayOp.showFire = true) catch ()')

    # Inferno Collider (optional)
    if enable_collision or collision_objects or enable_ground:
        lines.append('  local colliderOp = ev1.addOperator "Inferno Collider" opIdx')
        lines.append('  opIdx += 1')
        if collision_objects:
            obj_refs = " ".join(f'(getNodeByName "{_safe_name(o)}")' for o in collision_objects)
            lines.append(f'  try (colliderOp.objectList = #({obj_refs})) catch ()')
        if enable_ground:
            lines.append('  try (colliderOp.builtinGround = true) catch ()')
            lines.append(f'  try (colliderOp.builtinGroundHeight = {ground_height:.4f}) catch ()')

    # Export Inferno (optional)
    if enable_export:
        lines.append('  local exportOp = ev1.addOperator "Export Inferno" opIdx')
        lines.append('  opIdx += 1')
        if export_path:
            safe_path = _safe_name(export_path)
            lines.append(f'  try (exportOp.filenameSolver = "{safe_path}") catch ()')
        lines.append('  try (exportOp.gridDensity = true) catch ()')
        lines.append('  try (exportOp.gridTemperature = true) catch ()')
        lines.append('  try (exportOp.gridVelocity = true) catch ()')

    # Reset simulation
    if reset_simulation:
        lines.append('  tfObj.reset_simulation()')

    # Open editor
    if open_editor:
        lines.append('  tfObj.openEditor()')

    # JSON response
    lines.append('  local json = "{\\"name\\":\\"" + tfObj.name + "\\",\\"preset\\":\\"' + (preset or "custom") + '\\""')
    lines.append(f'  json += ",\\"voxelSize\\":{voxel_size:.4f}"')
    lines.append(f'  json += ",\\"temperatureKelvin\\":{temperature:.4f}"')
    lines.append('  local evCount = tfObj.baseobject.numsubs')
    lines.append('  json += ",\\"eventCount\\":" + (evCount as string)')
    lines.append('  json += ",\\"operatorCount\\":" + ((opIdx - 1) as string)')
    lines.append('  json += "}"')
    lines.append('  json')
    lines.append(')')

    ms = "(\n    " + "\n    ".join(lines) + "\n)"
    return client.send_command(ms).get("result", "")


# ---------------------------------------------------------------------------
# Tool 17: set_tyflow_inferno_display
# ---------------------------------------------------------------------------

@mcp.tool()
def set_tyflow_inferno_display(
    tyflow_name: str,
    event_name: str,
    operator_name: str = "Inferno Display",
    show_smoke: bool | None = None,
    show_fire: bool | None = None,
    smoke_opacity: float | None = None,
    fire_color_intensity: float | None = None,
    fire_opacity_intensity: float | None = None,
    overall_opacity: float | None = None,
    temperature_blur: float | None = None,
    ao_strength: float | None = None,
    ao_distance: float | None = None,
    shadow_strength: float | None = None,
    light_intensity: float | None = None,
    ambient_strength: float | None = None,
    glow_enable: bool | None = None,
    glow_intensity: float | None = None,
    glow_scale: float | None = None,
    motion_blur: bool | None = None,
    camera_step_size: float | None = None,
) -> str:
    """Configure an Inferno Display operator's viewport ray marching settings.

    Only specified (non-None) parameters are applied. Requires tyFlow 2.0+.

    Args:
        tyflow_name: Name of the tyFlow object.
        event_name: Name of the event containing the display operator.
        operator_name: Name of the display operator (default "Inferno Display").
        show_smoke: Show smoke volume.
        show_fire: Show fire volume.
        smoke_opacity: Smoke opacity multiplier.
        fire_color_intensity: Fire color intensity.
        fire_opacity_intensity: Fire opacity intensity.
        overall_opacity: Overall opacity multiplier.
        temperature_blur: Temperature blur amount.
        ao_strength: Ambient occlusion strength.
        ao_distance: Ambient occlusion distance.
        shadow_strength: Shadow strength.
        light_intensity: Light intensity.
        ambient_strength: Ambient light strength.
        glow_enable: Enable heat glow effect.
        glow_intensity: Glow intensity.
        glow_scale: Glow scale.
        motion_blur: Enable motion blur.
        camera_step_size: Ray march step size.
    """
    safe = _safe_name(tyflow_name)
    sa_evt = _sa_name(event_name)
    sa_op = _sa_name(operator_name)

    prop_lines: list[str] = []
    props = {
        "showSmoke": show_smoke,
        "showFire": show_fire,
        "smokeOpacity": smoke_opacity,
        "fireColorIntensity": fire_color_intensity,
        "fireOpacityIntensity": fire_opacity_intensity,
        "overallOpacity": overall_opacity,
        "temperatureBlur": temperature_blur,
        "aoStrength": ao_strength,
        "aoDistance": ao_distance,
        "shadowStrength": shadow_strength,
        "lightIntensity": light_intensity,
        "ambientStrength": ambient_strength,
        "glowEnable": glow_enable,
        "glowIntensity": glow_intensity,
        "glowScale": glow_scale,
        "motionBlurMode": motion_blur,
        "cameraStepSize": camera_step_size,
    }
    set_props = {k: v for k, v in props.items() if v is not None}
    if not set_props:
        return '{"error":"No properties specified to change."}'

    for prop_name, prop_val in set_props.items():
        prop_lines.append(f'  try (opRef.{prop_name} = {_ms_value(prop_val)}) catch ()')

    modified_json = ", ".join(f'\\"{k}\\"' for k in set_props)

    ms = f"""(
    local tfObj = getNodeByName "{safe}"
    if tfObj == undefined then (
        "{{\\"error\\":\\"tyFlow \\\\\\"{safe}\\\\\\" not found\\"}}"
    ) else (
        local opRef = undefined
        try (opRef = tfObj.baseobject[{sa_evt}][{sa_op}]) catch ()
        if opRef == undefined then (
            "{{\\"error\\":\\"Operator \\\\\\"{operator_name}\\\\\\" not found in event \\\\\\"{event_name}\\\\\\"\\"}}"
        ) else (
{chr(10).join(prop_lines)}
            "{{\\"success\\":true,\\"modified\\":[{modified_json}]}}"
        )
    )
)"""
    return client.send_command(ms).get("result", "")


# ---------------------------------------------------------------------------
# Tool 18: export_tyflow_inferno_vdb
# ---------------------------------------------------------------------------

@mcp.tool()
def export_tyflow_inferno_vdb(
    tyflow_name: str,
    event_name: str,
    output_path: str,
    operator_name: str = "Export Inferno",
    export_density: bool = True,
    export_temperature: bool = True,
    export_velocity: bool = True,
    export_color: bool = False,
    export_fuel: bool = False,
    velocity_mask_with_density: bool = True,
    temperature_units_enabled: bool = True,
    temperature_units: int = 3,
    frame_start: int | None = None,
    frame_end: int | None = None,
) -> str:
    """Configure an Export Inferno operator for VDB output.

    Sets the export path, channel selection, and frame range on an existing
    Export Inferno operator. Does NOT trigger the export -- use the tyFlow
    editor or simulate to generate output.

    Args:
        tyflow_name: Name of the tyFlow object.
        event_name: Name of the event containing the export operator.
        output_path: VDB output file path (use .vdb extension).
        operator_name: Name of the export operator (default "Export Inferno").
        export_density: Export density channel.
        export_temperature: Export temperature channel.
        export_velocity: Export velocity channel.
        export_color: Export color channel.
        export_fuel: Export fuel channel.
        velocity_mask_with_density: Mask velocity with density (reduces file size).
        temperature_units_enabled: Write temperature in real units.
        temperature_units: Temperature unit -- 1=Celsius, 2=Fahrenheit, 3=Kelvin.
        frame_start: Export start frame (None = don't change).
        frame_end: Export end frame (None = don't change).
    """
    safe = _safe_name(tyflow_name)
    safe_path = _safe_name(output_path)
    sa_evt = _sa_name(event_name)
    sa_op = _sa_name(operator_name)

    lines: list[str] = []
    lines.append(f'local tfObj = getNodeByName "{safe}"')
    lines.append('if tfObj == undefined then (')
    lines.append(f'  "{{\\"error\\":\\"tyFlow \\\\\\"{safe}\\\\\\" not found\\"}}"')
    lines.append(') else (')
    lines.append(f'  local opRef = undefined')
    lines.append(f'  try (opRef = tfObj.baseobject[{sa_evt}][{sa_op}]) catch ()')
    lines.append('  if opRef == undefined then (')
    lines.append(f'    "{{\\"error\\":\\"Operator \\\\\\"{operator_name}\\\\\\" not found in event \\\\\\"{event_name}\\\\\\"\\"}}"')
    lines.append('  ) else (')
    lines.append(f'    try (opRef.filenameSolver = "{safe_path}") catch ()')
    lines.append(f'    try (opRef.gridDensity = {_ms_value(export_density)}) catch ()')
    lines.append(f'    try (opRef.gridTemperature = {_ms_value(export_temperature)}) catch ()')
    lines.append(f'    try (opRef.gridVelocity = {_ms_value(export_velocity)}) catch ()')
    lines.append(f'    try (opRef.gridColor = {_ms_value(export_color)}) catch ()')
    lines.append(f'    try (opRef.gridFuel = {_ms_value(export_fuel)}) catch ()')
    lines.append(f'    try (opRef.gridVelocityMaskWithDensity = {_ms_value(velocity_mask_with_density)}) catch ()')
    lines.append(f'    try (opRef.gridTemperatureUnitsEnabled = {_ms_value(temperature_units_enabled)}) catch ()')
    lines.append(f'    try (opRef.gridTemperatureUnits = {temperature_units}) catch ()')
    if frame_start is not None:
        lines.append(f'    try (opRef.frameStart = {int(frame_start)}) catch ()')
    if frame_end is not None:
        lines.append(f'    try (opRef.frameEnd = {int(frame_end)}) catch ()')
    lines.append(f'    "{{\\"success\\":true,\\"path\\":\\"{safe_path}\\",\\"channels\\":[\\"density\\",\\"temperature\\",\\"velocity\\"]}}"')
    lines.append('  )')
    lines.append(')')

    ms = "(\n    " + "\n    ".join(lines) + "\n)"
    return client.send_command(ms).get("result", "")


# ---------------------------------------------------------------------------
# Tool 19: set_tyflow_global_event
# ---------------------------------------------------------------------------

@mcp.tool()
def set_tyflow_global_event(
    tyflow_name: str,
    event_name: str,
    enabled: bool = True,
    affect_mode: int = 0,
    include_events: str | None = None,
    exclude_events: str | None = None,
) -> str:
    """Mark a tyFlow event as global so its operators are auto-inserted into other events.

    Adds or configures a Global operator in the specified event. Requires tyFlow 2.0+.

    Args:
        tyflow_name: Name of the tyFlow object.
        event_name: Name of the event to make global.
        enabled: Enable/disable the Global operator.
        affect_mode: 0 = affect all events, 1 = include list, 2 = exclude list.
        include_events: Comma-separated event names to include (when affect_mode=1).
        exclude_events: Comma-separated event names to exclude (when affect_mode=2).
    """
    safe = _safe_name(tyflow_name)
    sa_evt = _sa_name(event_name)

    lines: list[str] = []
    lines.append(f'local tfObj = getNodeByName "{safe}"')
    lines.append('if tfObj == undefined then (')
    lines.append(f'  "{{\\"error\\":\\"tyFlow \\\\\\"{safe}\\\\\\" not found\\"}}"')
    lines.append(') else (')
    lines.append(f'  local evRef = undefined')
    lines.append(f'  try (evRef = tfObj.baseobject[{sa_evt}]) catch ()')
    lines.append('  if evRef == undefined then (')
    lines.append(f'    "{{\\"error\\":\\"Event \\\\\\"{event_name}\\\\\\" not found\\"}}"')
    lines.append('  ) else (')
    # Check if Global operator already exists
    lines.append(f'    local globalOp = undefined')
    lines.append(f'    try (globalOp = evRef[#Global]) catch ()')
    lines.append(f'    if globalOp == undefined do (')
    lines.append(f'      try (globalOp = evRef.addOperator "Global" -1) catch ()')
    lines.append(f'    )')
    lines.append(f'    if globalOp == undefined then (')
    lines.append(f'      "{{\\"error\\":\\"Could not add Global operator. Requires tyFlow 2.0+.\\"}}"')
    lines.append(f'    ) else (')
    lines.append(f'      try (globalOp.setEnabled {_ms_value(enabled)}) catch ()')
    lines.append(f'      try (globalOp.affectEvents = {affect_mode}) catch ()')
    if include_events is not None:
        lines.append(f'      try (globalOp.includeEventNames = "{_safe_name(include_events)}") catch ()')
    if exclude_events is not None:
        lines.append(f'      try (globalOp.excludeEventNames = "{_safe_name(exclude_events)}") catch ()')
    lines.append(f'      "{{\\"success\\":true,\\"event\\":\\"{event_name}\\",\\"global\\":{_ms_value(enabled)}}}"')
    lines.append(f'    )')
    lines.append('  )')
    lines.append(')')

    ms = "(\n    " + "\n    ".join(lines) + "\n)"
    return client.send_command(ms).get("result", "")


# ---------------------------------------------------------------------------
# Tool 20: export_tyflow_cache
# ---------------------------------------------------------------------------

@mcp.tool()
def export_tyflow_cache(
    tyflow_name: str,
    event_name: str = "Event_001",
    operator_name: str = "Export Particles",
    output_path: str | None = None,
    create_tycache_object: bool = True,
    only_if_not_created: bool = True,
    frame_start: int | None = None,
    frame_end: int | None = None,
) -> str:
    """Export a tyFlow particle system to tyCache files.

    Calls ``exportTyCache()`` on an Export Particles operator, which is
    equivalent to clicking the "Generate tyCache files" button in the UI.
    Optionally configures the output path, frame range, and whether a
    tyCache scene object is created automatically.

    The export runs synchronously and may take a long time for large
    particle counts.

    Args:
        tyflow_name: Name of the tyFlow object.
        event_name: Name of the event containing the Export Particles operator.
        operator_name: Name of the export operator (default "Export Particles").
        output_path: tyCache output path (without extension). None = keep current.
        create_tycache_object: Create a tyCache object in the scene after export.
        only_if_not_created: Only create tyCache object if one doesn't already exist.
        frame_start: Export start frame (None = don't change).
        frame_end: Export end frame (None = don't change).
    """
    safe = _safe_name(tyflow_name)
    sa_evt = _sa_name(event_name)
    sa_op = _sa_name(operator_name)

    lines: list[str] = []
    lines.append(f'local tfObj = getNodeByName "{safe}"')
    lines.append('if tfObj == undefined then (')
    lines.append(f'  "{{\\"error\\":\\"tyFlow \\\\\\"{safe}\\\\\\" not found\\"}}"')
    lines.append(') else (')
    lines.append(f'  local opRef = undefined')
    lines.append(f'  try (opRef = tfObj.baseobject[{sa_evt}][{sa_op}]) catch ()')
    lines.append('  if opRef == undefined then (')
    lines.append(f'    "{{\\"error\\":\\"Operator \\\\\\"{operator_name}\\\\\\" not found in event \\\\\\"{event_name}\\\\\\"\\"}}"')
    lines.append('  ) else (')
    # Configure export settings
    lines.append(f'    try (opRef.exportMode = 2) catch ()  -- tyCache mode')
    if output_path is not None:
        safe_path = _safe_name(output_path)
        lines.append(f'    try (opRef.tyCacheFilename = "{safe_path}") catch ()')
    lines.append(f'    try (opRef.tycacheCreateObject = {_ms_value(create_tycache_object)}) catch ()')
    lines.append(f'    try (opRef.tycacheCreateObjectIfNotCreated = {_ms_value(only_if_not_created)}) catch ()')
    if frame_start is not None:
        lines.append(f'    try (opRef.frameStart = {int(frame_start)}) catch ()')
    if frame_end is not None:
        lines.append(f'    try (opRef.frameEnd = {int(frame_end)}) catch ()')
    # Trigger the export
    lines.append(f'    local exportResult = opRef.exportTyCache()')
    lines.append(f'    local cachePath = try (opRef.tyCacheFilename) catch ("")')
    lines.append(f'    "{{\\"success\\":true,\\"tyflow\\":\\"{safe}\\",\\"cachePath\\":\\"" + (substituteString cachePath "\\\\" "/") + "\\"}}"')
    lines.append('  )')
    lines.append(')')

    ms = "(\n    " + "\n    ".join(lines) + "\n)"
    return client.send_command(ms).get("result", "")
