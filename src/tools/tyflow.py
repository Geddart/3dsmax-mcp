from __future__ import annotations

import json
from typing import Any

from src.helpers.maxscript import safe_string

from ..server import client, mcp
from ..coerce import StrList, FloatList, IntList, DictList


SHAPE_3D_IDS: dict[str, int] = {
    "triangle": 0,
    "cone": 1,
    "quad": 2,
    "plane": 2,
    "cylinder": 3,
    "sphere": 4,
    "pyramid": 5,
    "box": 6,
    "cube": 6,
    "octahedron": 7,
    "geosphere_low": 8,
    "geosphere": 9,
    "geosphere_high": 10,
    "icosahedron": 11,
}


KNOWN_OPERATORS: tuple[str, ...] = (
    "Birth",
    "Birth Surface",
    "Birth Objects",
    "Birth Spline",
    "Speed",
    "Spin",
    "Rotation",
    "Scale",
    "Mass",
    "Force",
    "Shape",
    "Display",
    "PhysX Shape",
    "PhysX Collision",
    "Collision",
    "Delete",
    "Spawn",
    "Select",
    "Send Out",
    "Split",
    "Time Test",
    "Object Test",
    "Surface Test",
    "Property Test",
    "Voronoi Fracture",
    "Element Fracture",
    "Face Fracture",
    "Bounds Fracture",
    "Brick Fracture",
    "Multifracture",
    "Convex Hull",
    "Export Particles",
    "Display Data",
    "Position Object",
)


HELPERS = """
local esc = MCP_Server.escapeJsonString

fn jsonStringArray arr =
(
    local s = "["
    for i = 1 to arr.count do (
        if i > 1 do s += ","
        s += "\\"" + (esc arr[i]) + "\\""
    )
    s += "]"
    s
)

fn findEventSubAnim flowNode eventName =
(
    if flowNode == undefined then return undefined
    local bo = flowNode.baseobject
    if bo == undefined then return undefined
    local evSym = undefined
    try (evSym = execute ("#'" + eventName + "'")) catch ()
    if evSym == undefined then return undefined
    local ev = undefined
    try (ev = bo[evSym]) catch ()
    ev
)

fn findOperatorSubAnim eventSub operatorName =
(
    if eventSub == undefined then return undefined
    local opSym = undefined
    try (opSym = execute ("#'" + operatorName + "'")) catch ()
    if opSym == undefined then return undefined
    local op = undefined
    try (op = eventSub[opSym]) catch ()
    op
)
"""


def _load_json(raw: str, fallback: Any) -> Any:
    try:
        return json.loads(raw)
    except Exception:
        return fallback


def _send_json(maxscript: str, fallback: Any) -> Any:
    try:
        response = client.send_command(maxscript)
    except Exception as exc:
        return {"error": str(exc)}
    return _load_json(response.get("result", ""), fallback)


def _mxs_string_array(items: list[str]) -> str:
    return "#(" + ", ".join(f'"{safe_string(item)}"' for item in items) + ")"


def _mxs_value(value: Any, raw_strings: bool = False) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int) and not isinstance(value, bool):
        return str(value)
    if isinstance(value, float):
        return str(float(value))
    if isinstance(value, str):
        return value if raw_strings else f'"{safe_string(value)}"'
    if isinstance(value, list):
        if not value:
            return "#()"
        if all(isinstance(v, str) for v in value):
            return _mxs_string_array(value)
        if all(isinstance(v, bool) for v in value):
            return "#(" + ", ".join("true" if v else "false" for v in value) + ")"
        if all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in value):
            return "#(" + ", ".join(str(float(v)) if isinstance(v, float) else str(int(v)) for v in value) + ")"
    raise ValueError(f"Unsupported value type: {type(value).__name__}")


def _assignment_lines(values: dict[str, Any], var_name: str, raw_strings: bool = False) -> tuple[str, list[str]]:
    lines: list[str] = []
    names: list[str] = []
    for prop_name, prop_value in values.items():
        prop = safe_string(prop_name)
        expr = _mxs_value(prop_value, raw_strings=raw_strings)
        lines.append(
            f'try ({var_name}.{prop} = {expr}; append applied "{prop}") '
            f'catch (append errors "Could not set {prop}")'
        )
        names.append(prop_name)
    return "\n".join(lines), names


def _sa_name(name: str) -> str:
    """Format a name for SubAnim access -- replace spaces with underscores."""
    safe = safe_string(name).replace(" ", "_")
    return f"#{safe}"


@mcp.tool()
def list_tyflow_operator_types() -> str:
    """Return available and unavailable tyFlow operator names for this installation."""
    candidates = _mxs_string_array(list(KNOWN_OPERATORS))
    maxscript = f"""(
{HELPERS}
if tyFlow == undefined then (
    "{{\\"error\\":\\"tyFlow plugin is not available\\"}}"
) else (
    local opNames = {candidates}
    local flow = tyFlow name:"zzz_tyflow_op_probe"
    local eventHandle = flow.tyFlow.addEvent()
    local ev = eventHandle.Event
    ev.setName "Probe"
    local ok = #()
    local fail = #()
    for n in opNames do (
        local op = undefined
        try (op = ev.addOperator n -1) catch ()
        if op == undefined then append fail n else (
            append ok n
            try (op.remove()) catch ()
        )
    )
    delete flow
    "{{\\"available\\":" + (jsonStringArray ok) + ",\\"unavailable\\":" + (jsonStringArray fail) + "}}"
)
)"""
    return json.dumps(_send_json(maxscript, {"error": "Could not parse operator probe response."}))


@mcp.tool()
def create_tyflow(
    name: str = "",
    position: FloatList | None = None,
    event_name: str = "Emit",
    event_position: IntList | None = None,
    operators: DictList | None = None,
    select_created: bool = True,
) -> str:
    """Create tyFlow with one event and a configurable operator list."""
    from .selection import select_objects

    pos = position or [0.0, 0.0, 0.0]
    ev_pos = event_position or [0, 0]
    if len(pos) != 3:
        raise ValueError("position must be [x, y, z]")
    if len(ev_pos) != 2:
        raise ValueError("event_position must be [x, y]")

    op_defs = operators or [
        {"type": "Birth", "name": "Birth", "position": 0, "properties": {"birthMode": 0, "birthTotal": 100}},
        {
            "type": "Shape",
            "name": "Shape",
            "position": 1,
            "properties": {
                "shape_type_tab": [1],
                "type_3d_ID_tab": [SHAPE_3D_IDS["sphere"]],
                "frequency_tab": [100.0],
                "scaleVal_tab": [100.0],
            },
        },
        {"type": "Display", "name": "Display", "position": 2, "properties": {"displayMode": 2}},
    ]

    op_blocks: list[str] = []
    for idx, op in enumerate(op_defs, start=1):
        op_type = safe_string(str(op.get("type", "Birth")))
        op_name = safe_string(str(op.get("name", op.get("type", f"Operator{idx}"))))
        op_pos = int(op.get("position", idx - 1))
        var = f"op{idx}"
        props = op.get("properties", {})
        if not isinstance(props, dict):
            props = {}
        assign_lines: list[str] = []
        for prop_name, prop_value in props.items():
            prop = safe_string(prop_name)
            expr = _mxs_value(prop_value)
            assign_lines.append(f'try ({var}.{prop} = {expr}) catch (totalErrors += 1)')
        assign_script = "\n".join(assign_lines)
        op_blocks.append(
            f"""
local {var} = ev.addOperator "{op_type}" {op_pos}
try ({var}.Operator.setName "{op_name}") catch ()
{assign_script}
operatorCount += 1
"""
        )

    maxscript = f"""(
{HELPERS}
if tyFlow == undefined then (
    "{{\\"error\\":\\"tyFlow plugin is not available\\"}}"
) else (
    if "{safe_string(name)}" != "" and (getNodeByName "{safe_string(name)}") != undefined then (
        "{{\\"error\\":\\"Object already exists: {safe_string(name)}\\"}}"
    ) else (
        local flow = if "{safe_string(name)}" == "" then tyFlow pos:[{float(pos[0])},{float(pos[1])},{float(pos[2])}] else tyFlow name:"{safe_string(name)}" pos:[{float(pos[0])},{float(pos[1])},{float(pos[2])}]
        local eventHandle = flow.tyFlow.addEvent()
        local ev = eventHandle.Event
        ev.setName "{safe_string(event_name)}"
        ev.setPosition [{int(ev_pos[0])},{int(ev_pos[1])}]
        local operatorCount = 0
        local totalErrors = 0
        {"".join(op_blocks)}
        "{{\\"name\\":\\"" + flow.name + "\\",\\"event\\":\\"" + ev.getName() + "\\",\\"operatorCount\\":" + (operatorCount as string) + ",\\"errorCount\\":" + (totalErrors as string) + "}}"
    )
)
)"""
    payload = _send_json(maxscript, {"error": "Could not parse create_tyflow response."})
    if select_created and isinstance(payload, dict) and "name" in payload and "error" not in payload:
        payload["selectResult"] = select_objects(names=[str(payload["name"])])
    return json.dumps(payload)


@mcp.tool()
def get_tyflow_info(
    name: str,
    include_events: bool = True,
    include_operator_properties: bool = False,
    max_operators_per_event: int = 200,
    include_flow_properties: bool = False,
    include_event_properties: bool = False,
    max_properties_per_operator: int = 200,
    max_properties_per_event: int = 200,
    max_properties_on_flow: int = 200,
) -> str:
    """Inspect a tyFlow object with deep flow/event/operator/property readback."""
    max_ops = max(1, int(max_operators_per_event))
    max_op_props = max(1, int(max_properties_per_operator))
    max_ev_props = max(1, int(max_properties_per_event))
    max_flow_props = max(1, int(max_properties_on_flow))
    maxscript = f"""(
{HELPERS}
fn parseSubAnimNamesByShowProps targetObj =
(
    local names = #()
    local ss = stringstream ""
    try (showProperties targetObj to:ss) catch ()
    seek ss 0
    while not eof ss do (
        local line = trimRight (trimLeft (readline ss))
        if line.count > 1 and (substring line 1 1) == "." then (
            local rawName = trimRight (trimLeft (substring line 2 (line.count - 1)))
            if (findString rawName ":") == undefined and rawName != "" do append names rawName
        )
    )
    names
)

fn clean s =
(
    local t = s as string
    t = substituteString t "|" "<pipe>"
    t = substituteString t "\\n" " "
    t = substituteString t "\\r" ""
    t
)

fn propLinesFor targetObj lineTag maxProps maxChars =
(
    local out = ""
    local pNames = #()
    try (pNames = getPropNames targetObj) catch ()
    local total = pNames.count
    local take = total
    if take > maxProps do take = maxProps
    for i = 1 to take do (
        local p = pNames[i]
        local pName = p as string
        local pVal = ""
        try (pVal = (getProperty targetObj p) as string) catch (pVal = "<unreadable>")
        if pVal.count > maxChars do pVal = (substring pVal 1 maxChars) + "..."
        out += lineTag + "|" + (clean pName) + "|" + (clean pVal) + "\\n"
    )
    if total > take do out += "WARN|" + lineTag + "_TRUNCATED|" + (total as string) + "|" + (take as string) + "\\n"
    out
)

local flow = getNodeByName "{safe_string(name)}"
if flow == undefined then (
    "__ERROR__|Object not found: {safe_string(name)}"
) else (
    local bo = flow.baseobject
    local particleCount = 0
    try (particleCount = flow.numParticles()) catch ()

    local out = "FLOW|" + (clean flow.name) + "|" + (clean ((classof bo) as string)) + "|" + (particleCount as string) + "\\n"
    if {str(bool(include_flow_properties)).lower()} then (
        local fpLines = propLinesFor bo "FP" {max_flow_props} 300
        out += fpLines
    )
    if {str(bool(include_events)).lower()} then (
        local eventNames = parseSubAnimNamesByShowProps bo
        out += "META|eventSubAnimCount|" + (eventNames.count as string) + "\\n"
        for eventName in eventNames do (
            out += "EV|" + (clean eventName) + "\\n"
            local evSym = undefined
            local ev = undefined
            try (evSym = execute ("#'" + eventName + "'")) catch ()
            if evSym != undefined then (
                try (ev = bo[evSym]) catch ()
            )
            if ev != undefined then (
                if {str(bool(include_event_properties)).lower()} then (
                    local epNames = #()
                    try (epNames = getPropNames ev) catch ()
                    local epTotal = epNames.count
                    local epTake = epTotal
                    if epTake > {max_ev_props} do epTake = {max_ev_props}
                    for epi = 1 to epTake do (
                        local ep = epNames[epi]
                        local epName = ep as string
                        local epVal = ""
                        try (epVal = (getProperty ev ep) as string) catch (epVal = "<unreadable>")
                        if epVal.count > 300 do epVal = (substring epVal 1 300) + "..."
                        out += "EP|" + (clean eventName) + "|" + (clean epName) + "|" + (clean epVal) + "\\n"
                    )
                    if epTotal > epTake do out += "WARN|EP_TRUNCATED|" + (clean eventName) + "|" + (epTotal as string) + "|" + (epTake as string) + "\\n"
                )
                local opNames = parseSubAnimNamesByShowProps ev
                local opCount = opNames.count
                if opCount > {max_ops} then (
                    out += "WARN|OP_TRUNCATED|" + (clean eventName) + "|" + (opNames.count as string) + "|" + ({max_ops} as string) + "\\n"
                    opCount = {max_ops}
                )
                for oi = 1 to opCount do (
                    local opName = opNames[oi]
                    local opSym = undefined
                    local op = undefined
                    try (opSym = execute ("#'" + opName + "'")) catch ()
                    if opSym != undefined then (
                        try (op = ev[opSym]) catch ()
                    )
                    local opClass = "<unknown>"
                    local propCount = 0
                    if op != undefined then (
                        try (opClass = (classof op.Operator) as string) catch (try (opClass = (classof op) as string) catch ())
                        local pNames = #()
                        try (pNames = getPropNames op) catch ()
                        propCount = pNames.count
                        out += "OP|" + (clean eventName) + "|" + (clean opName) + "|" + (clean opClass) + "|" + (propCount as string) + "\\n"
                        if {str(bool(include_operator_properties)).lower()} then (
                            local pTake = pNames.count
                            if pTake > {max_op_props} do pTake = {max_op_props}
                            for pi = 1 to pTake do (
                                local p = pNames[pi]
                                local pName = p as string
                                local pVal = ""
                                try (pVal = (getProperty op p) as string) catch (pVal = "<unreadable>")
                                if pVal.count > 300 do pVal = (substring pVal 1 300) + "..."
                                out += "PR|" + (clean eventName) + "|" + (clean opName) + "|" + (clean pName) + "|" + (clean pVal) + "\\n"
                            )
                            if pNames.count > pTake do out += "WARN|PR_TRUNCATED|" + (clean eventName) + "|" + (clean opName) + "|" + (pNames.count as string) + "|" + (pTake as string) + "\\n"
                        )
                    )
                    if op == undefined then out += "OP|" + (clean eventName) + "|" + (clean opName) + "|<unresolved>|0\\n"
                )
            )
        )
    )
    out
)
)"""
    try:
        response = client.send_command(maxscript)
    except Exception as exc:
        return json.dumps({"error": str(exc)})
    raw = str(response.get("result", ""))
    if raw.startswith("__ERROR__|"):
        return json.dumps({"error": raw.split("|", 1)[1]})

    def _decode_token(value: str) -> str:
        return value.replace("<pipe>", "|")

    result: dict[str, Any] = {
        "name": name,
        "class": "",
        "particleCount": 0,
        "flowPropertyCount": 0,
        "flowProperties": [],
        "eventSubAnimCount": 0,
        "eventCount": 0,
        "events": [],
        "warnings": [],
    }
    events: dict[str, dict[str, Any]] = {}

    for line in raw.splitlines():
        parts = line.split("|")
        if not parts:
            continue
        tag = parts[0]
        if tag == "FLOW" and len(parts) >= 4:
            result["name"] = _decode_token(parts[1])
            result["class"] = _decode_token(parts[2])
            try:
                result["particleCount"] = int(parts[3])
            except Exception:
                result["particleCount"] = 0
        elif tag == "META" and len(parts) >= 3:
            if parts[1] == "eventSubAnimCount":
                try:
                    result["eventSubAnimCount"] = int(parts[2])
                except Exception:
                    result["eventSubAnimCount"] = 0
        elif tag == "FP" and len(parts) >= 3:
            result["flowProperties"].append({"name": _decode_token(parts[1]), "value": _decode_token(parts[2])})
        elif tag == "EV" and len(parts) >= 2:
            ev_name = _decode_token(parts[1])
            if ev_name not in events:
                events[ev_name] = {
                    "name": ev_name,
                    "propertyCount": 0,
                    "properties": [],
                    "operatorCount": 0,
                    "operators": [],
                }
        elif tag == "EP" and len(parts) >= 4:
            ev_name = _decode_token(parts[1])
            p_name = _decode_token(parts[2])
            p_val = _decode_token(parts[3])
            if ev_name not in events:
                events[ev_name] = {
                    "name": ev_name,
                    "propertyCount": 0,
                    "properties": [],
                    "operatorCount": 0,
                    "operators": [],
                }
            events[ev_name]["properties"].append({"name": p_name, "value": p_val})
        elif tag == "OP" and len(parts) >= 5:
            ev_name = _decode_token(parts[1])
            op_name = _decode_token(parts[2])
            op_class = _decode_token(parts[3])
            try:
                prop_count = int(parts[4])
            except Exception:
                prop_count = 0
            if ev_name not in events:
                events[ev_name] = {
                    "name": ev_name,
                    "propertyCount": 0,
                    "properties": [],
                    "operatorCount": 0,
                    "operators": [],
                }
            events[ev_name]["operators"].append({
                "name": op_name,
                "class": op_class,
                "propertyCount": prop_count,
                "properties": [],
            })
        elif tag == "PR" and len(parts) >= 5:
            ev_name = _decode_token(parts[1])
            op_name = _decode_token(parts[2])
            prop_name = _decode_token(parts[3])
            prop_value = _decode_token(parts[4])
            ev = events.get(ev_name)
            if not ev:
                continue
            op = next((item for item in ev["operators"] if item["name"] == op_name), None)
            if op is None:
                continue
            op["properties"].append({"name": prop_name, "value": prop_value})
        elif tag == "WARN":
            decoded = [_decode_token(p) for p in parts[1:]]
            if decoded:
                result["warnings"].append(decoded)

    event_list = list(events.values())
    for ev in event_list:
        ev["propertyCount"] = len(ev["properties"])
        ev["operatorCount"] = len(ev["operators"])
    result["flowPropertyCount"] = len(result["flowProperties"])
    result["eventCount"] = len(event_list)
    result["events"] = event_list
    return json.dumps(result)


@mcp.tool()
def add_tyflow_event(name: str, event_name: str, event_position: IntList | None = None) -> str:
    """Add one event to an existing tyFlow object."""
    pos = event_position or [0, 0]
    if len(pos) != 2:
        raise ValueError("event_position must be [x, y]")

    maxscript = f"""(
{HELPERS}
local flow = getNodeByName "{safe_string(name)}"
if flow == undefined then (
    "{{\\"error\\":\\"Object not found: {safe_string(name)}\\"}}"
) else (
    local evRef = flow.tyFlow.addEvent()
    local ev = evRef.Event
    ev.setName "{safe_string(event_name)}"
    ev.setPosition [{int(pos[0])},{int(pos[1])}]
    "{{\\"name\\":\\"" + (esc flow.name) + "\\",\\"event\\":\\"" + (esc ev.getName()) + "\\"}}"
)
)"""
    return json.dumps(_send_json(maxscript, {"error": "Could not parse add_tyflow_event response."}))


@mcp.tool()
def modify_tyflow_operator(
    name: str,
    event_name: str,
    operator_name: str,
    properties: dict[str, Any],
    raw_values: bool = False,
) -> str:
    """Set operator properties on an existing tyFlow event/operator pair."""
    if not properties:
        return json.dumps({"error": "properties cannot be empty"})

    assignments, names = _assignment_lines(properties, "op", raw_strings=raw_values)
    req = _mxs_string_array(names)
    maxscript = f"""(
{HELPERS}
local flow = getNodeByName "{safe_string(name)}"
if flow == undefined then (
    "{{\\"error\\":\\"Object not found: {safe_string(name)}\\"}}"
) else (
    local ev = findEventSubAnim flow "{safe_string(event_name)}"
    if ev == undefined then (
        "{{\\"error\\":\\"Event not found: {safe_string(event_name)}\\"}}"
    ) else (
        local op = findOperatorSubAnim ev "{safe_string(operator_name)}"
        if op == undefined then (
            "{{\\"error\\":\\"Operator not found: {safe_string(operator_name)}\\"}}"
        ) else (
            local applied = #()
            local errors = #()
            {assignments}
            "{{\\"name\\":\\"" + (esc flow.name) + "\\",\\"event\\":\\"" + (esc "{safe_string(event_name)}") + "\\",\\"operator\\":\\"" + (esc "{safe_string(operator_name)}") + "\\",\\"requested\\":" + (jsonStringArray {req}) + ",\\"applied\\":" + (jsonStringArray applied) + ",\\"errors\\":" + (jsonStringArray errors) + "}}"
        )
    )
)
)"""
    return json.dumps(_send_json(maxscript, {"error": "Could not parse modify_tyflow_operator response."}))


@mcp.tool()
def set_tyflow_shape(
    name: str,
    event_name: str = "Emit",
    operator_name: str = "Shape",
    shape: str = "sphere",
    scale: float = 100.0,
    frequency: float = 100.0,
    create_if_missing: bool = True,
) -> str:
    """Set Shape operator with validated 3D shape IDs."""
    key = shape.strip().lower()
    if key not in SHAPE_3D_IDS:
        return json.dumps({"error": f"Unknown shape '{shape}'"})

    shape_id = SHAPE_3D_IDS[key]
    maxscript = f"""(
{HELPERS}
local flow = getNodeByName "{safe_string(name)}"
if flow == undefined then (
    "{{\\"error\\":\\"Object not found: {safe_string(name)}\\"}}"
) else (
    local ev = findEventSubAnim flow "{safe_string(event_name)}"
    if ev == undefined then (
        "{{\\"error\\":\\"Event not found: {safe_string(event_name)}\\"}}"
    ) else (
        local shapeOp = findOperatorSubAnim ev "{safe_string(operator_name)}"
        if shapeOp == undefined and {str(bool(create_if_missing)).lower()} then (
            local evI = undefined
            try (evI = ev.Event) catch ()
            if evI != undefined then (
                shapeOp = evI.addOperator "Shape" -1
                try (shapeOp.Operator.setName "{safe_string(operator_name)}") catch ()
            )
        )
        if shapeOp == undefined then (
            "{{\\"error\\":\\"Shape operator not found\\"}}"
        ) else (
            local applied = #()
            local errors = #()
            try (shapeOp.shape_type_tab = #(1); append applied "shape_type_tab") catch (append errors "shape_type_tab")
            try (shapeOp.type_3d_ID_tab = #({shape_id}); append applied "type_3d_ID_tab") catch (append errors "type_3d_ID_tab")
            try (shapeOp.frequency_tab = #({float(frequency)}); append applied "frequency_tab") catch (append errors "frequency_tab")
            try (shapeOp.scaleVal_tab = #({float(scale)}); append applied "scaleVal_tab") catch (append errors "scaleVal_tab")
            "{{\\"name\\":\\"" + (esc flow.name) + "\\",\\"shape\\":\\"{safe_string(key)}\\",\\"shapeId\\":{shape_id},\\"applied\\":" + (jsonStringArray applied) + ",\\"errors\\":" + (jsonStringArray errors) + "}}"
        )
    )
)
)"""
    return json.dumps(_send_json(maxscript, {"error": "Could not parse set_tyflow_shape response."}))


@mcp.tool()
def connect_tyflow_events(
    name: str,
    from_event: str,
    to_event: str,
    send_out_operator_name: str = "Send Out",
    create_if_missing: bool = True,
) -> str:
    """Connect events with Send Out by applying common destination property candidates."""
    maxscript = f"""(
{HELPERS}
local flow = getNodeByName "{safe_string(name)}"
if flow == undefined then (
    "{{\\"error\\":\\"Object not found: {safe_string(name)}\\"}}"
) else (
    local src = findEventSubAnim flow "{safe_string(from_event)}"
    local dst = findEventSubAnim flow "{safe_string(to_event)}"
    if src == undefined then (
        "{{\\"error\\":\\"Source event not found: {safe_string(from_event)}\\"}}"
    ) else if dst == undefined then (
        "{{\\"error\\":\\"Destination event not found: {safe_string(to_event)}\\"}}"
    ) else (
        local sendOp = findOperatorSubAnim src "{safe_string(send_out_operator_name)}"
        if sendOp == undefined and {str(bool(create_if_missing)).lower()} then (
            local srcI = undefined
            try (srcI = src.Event) catch ()
            if srcI != undefined then (
                sendOp = srcI.addOperator "Send Out" -1
                try (sendOp.Operator.setName "{safe_string(send_out_operator_name)}") catch ()
            )
        )
        if sendOp == undefined then (
            "{{\\"error\\":\\"Send Out operator not found\\"}}"
        ) else (
            local applied = #()
            local errors = #()
            local props = #("eventName", "targetEvent", "nextEvent", "destinationEvent")
            for pName in props do (
                local pSym = execute ("#" + pName)
                if isProperty sendOp pSym then (
                    try (setProperty sendOp pSym "{safe_string(to_event)}"; append applied pName) catch (append errors ("Could not set " + pName))
                )
            )
            "{{\\"name\\":\\"" + (esc flow.name) + "\\",\\"fromEvent\\":\\"{safe_string(from_event)}\\",\\"toEvent\\":\\"{safe_string(to_event)}\\",\\"operator\\":\\"{safe_string(send_out_operator_name)}\\",\\"applied\\":" + (jsonStringArray applied) + ",\\"errors\\":" + (jsonStringArray errors) + "}}"
        )
    )
)
)"""
    return json.dumps(_send_json(maxscript, {"error": "Could not parse connect_tyflow_events response."}))


@mcp.tool()
def add_tyflow_collision(
    name: str,
    event_name: str,
    collider_names: StrList,
    operator_name: str = "Collision",
    create_if_missing: bool = True,
) -> str:
    """Add/configure Collision operator and wire collider node list."""
    requested = _mxs_string_array(collider_names)
    maxscript = f"""(
{HELPERS}
local flow = getNodeByName "{safe_string(name)}"
local names = {requested}
if flow == undefined then (
    "{{\\"error\\":\\"Object not found: {safe_string(name)}\\"}}"
) else (
    local ev = findEventSubAnim flow "{safe_string(event_name)}"
    if ev == undefined then (
        "{{\\"error\\":\\"Event not found: {safe_string(event_name)}\\"}}"
    ) else (
        local collOp = findOperatorSubAnim ev "{safe_string(operator_name)}"
        if collOp == undefined and {str(bool(create_if_missing)).lower()} then (
            local evI = undefined
            try (evI = ev.Event) catch ()
            if evI != undefined then (
                collOp = evI.addOperator "Collision" -1
                try (collOp.Operator.setName "{safe_string(operator_name)}") catch ()
            )
        )
        if collOp == undefined then (
            "{{\\"error\\":\\"Collision operator not found\\"}}"
        ) else (
            local nodes = #()
            local missing = #()
            for n in names do (
                local node = getNodeByName n
                if node == undefined then append missing n else append nodes node
            )
            local applied = #()
            local errors = #()
            local props = #("colliderList", "objectList", "objects", "nodes")
            for pName in props do (
                local pSym = execute ("#" + pName)
                if isProperty collOp pSym then (
                    try (setProperty collOp pSym nodes; append applied pName) catch (append errors ("Could not set " + pName))
                )
            )
            "{{\\"name\\":\\"" + (esc flow.name) + "\\",\\"operator\\":\\"{safe_string(operator_name)}\\",\\"requested\\":" + (jsonStringArray names) + ",\\"missing\\":" + (jsonStringArray missing) + ",\\"applied\\":" + (jsonStringArray applied) + ",\\"errors\\":" + (jsonStringArray errors) + "}}"
        )
    )
)
    )"""
    return json.dumps(_send_json(maxscript, {"error": "Could not parse add_tyflow_collision response."}))


@mcp.tool()
def set_tyflow_physx(
    name: str,
    enabled: bool = True,
    gravity: float = -980.0,
    substeps: int = 8,
    pos_iterations: int = 4,
    vel_iterations: int = 1,
) -> str:
    """Set object-level PhysX settings from tyFlow object properties."""
    maxscript = f"""(
{HELPERS}
local flow = getNodeByName "{safe_string(name)}"
if flow == undefined then (
    "{{\\"error\\":\\"Object not found: {safe_string(name)}\\"}}"
) else (
    local bo = flow.baseobject
    local applied = #()
    local errors = #()
    fn setIf propName propValue = (
        local pSym = execute ("#" + propName)
        if isProperty bo pSym then (
            try (setProperty bo pSym propValue; append applied propName) catch (append errors ("Could not set " + propName))
        )
    )
    setIf "physXGravityEnabled" {str(bool(enabled)).lower()}
    setIf "physXGravityValue" {float(gravity)}
    setIf "physXSubsteps" {int(substeps)}
    setIf "physXPosIterations" {int(pos_iterations)}
    setIf "physXVelIterations" {int(vel_iterations)}
    "{{\\"name\\":\\"" + (esc flow.name) + "\\",\\"applied\\":" + (jsonStringArray applied) + ",\\"errors\\":" + (jsonStringArray errors) + "}}"
)
)"""
    return json.dumps(_send_json(maxscript, {"error": "Could not parse set_tyflow_physx response."}))


@mcp.tool()
def remove_tyflow_element(name: str, event_name: str, operator_name: str = "") -> str:
    """Remove operator from an event, or remove event when operator_name is empty."""
    maxscript = f"""(
{HELPERS}
local flow = getNodeByName "{safe_string(name)}"
if flow == undefined then (
    "{{\\"error\\":\\"Object not found: {safe_string(name)}\\"}}"
) else (
    local ev = findEventSubAnim flow "{safe_string(event_name)}"
    if ev == undefined then (
        "{{\\"error\\":\\"Event not found: {safe_string(event_name)}\\"}}"
    ) else (
        if "{safe_string(operator_name)}" != "" then (
            local op = findOperatorSubAnim ev "{safe_string(operator_name)}"
            if op == undefined then (
                "{{\\"error\\":\\"Operator not found: {safe_string(operator_name)}\\"}}"
            ) else (
                local ok = false
                try (op.remove(); ok = true) catch ()
                if ok then "{{\\"removed\\":\\"operator\\",\\"event\\":\\"{safe_string(event_name)}\\",\\"operator\\":\\"{safe_string(operator_name)}\\"}}" else "{{\\"error\\":\\"Could not remove operator\\"}}"
            )
        ) else (
            local ok = false
            try (ev.remove(); ok = true) catch ()
            if ok then "{{\\"removed\\":\\"event\\",\\"event\\":\\"{safe_string(event_name)}\\"}}" else "{{\\"error\\":\\"Could not remove event\\"}}"
        )
    )
)
)"""
    return json.dumps(_send_json(maxscript, {"error": "Could not parse remove_tyflow_element response."}))


@mcp.tool()
def get_tyflow_particle_count(name: str, frame: int | None = None, update: bool = True) -> str:
    """Return tyFlow particle count at current frame or supplied frame."""
    frame_expr = "currentTime" if frame is None else f"{int(frame)}f"
    maxscript = f"""(
{HELPERS}
local flow = getNodeByName "{safe_string(name)}"
if flow == undefined then (
    "{{\\"error\\":\\"Object not found: {safe_string(name)}\\"}}"
) else (
    if {str(bool(update)).lower()} then (
        sliderTime = {frame_expr}
        try (flow.updateParticles {frame_expr}) catch ()
    )
    local n = 0
    try (n = flow.numParticles()) catch ()
    "{{\\"name\\":\\"" + (esc flow.name) + "\\",\\"particleCount\\":" + (n as string) + "}}"
)
)"""
    return json.dumps(_send_json(maxscript, {"error": "Could not parse get_tyflow_particle_count response."}))


@mcp.tool()
def get_tyflow_particles(
    name: str,
    frame: int | None = None,
    max_particles: int = 1000,
    include_position: bool = True,
    include_velocity: bool = True,
    include_age: bool = True,
) -> str:
    """Return particle data rows from tyFlow read-only APIs."""
    if max_particles <= 0:
        raise ValueError("max_particles must be > 0")
    frame_expr = "currentTime" if frame is None else f"{int(frame)}f"
    maxscript = f"""(
{HELPERS}
local flow = getNodeByName "{safe_string(name)}"
if flow == undefined then (
    "{{\\"error\\":\\"Object not found: {safe_string(name)}\\"}}"
) else (
    sliderTime = {frame_expr}
    try (flow.updateParticles {frame_expr}) catch ()
    local total = 0
    try (total = flow.numParticles()) catch ()
    local takeCount = total
    if takeCount > {int(max_particles)} do takeCount = {int(max_particles)}
    local pos = #()
    local vel = #()
    local age = #()
    if {str(bool(include_position)).lower()} then (try (pos = flow.getAllParticlePositions()) catch ())
    if {str(bool(include_velocity)).lower()} then (try (vel = flow.getAllParticleVelocities()) catch ())
    if {str(bool(include_age)).lower()} then (try (age = flow.getAllParticleAges()) catch ())

    local rows = #()
    for i = 1 to takeCount do (
        local row = "{{\\"id\\":" + (i as string)
        if {str(bool(include_position)).lower()} and pos.count >= i then (
            local p = pos[i]
            row += ",\\"position\\":[" + ((p.x) as string) + "," + ((p.y) as string) + "," + ((p.z) as string) + "]"
        )
        if {str(bool(include_velocity)).lower()} and vel.count >= i then (
            local v = vel[i]
            row += ",\\"velocity\\":[" + ((v.x) as string) + "," + ((v.y) as string) + "," + ((v.z) as string) + "]"
        )
        if {str(bool(include_age)).lower()} and age.count >= i then row += ",\\"age\\":" + ((age[i]) as string)
        row += "}}"
        append rows row
    )
    local payload = "["
    for i = 1 to rows.count do (
        if i > 1 do payload += ","
        payload += rows[i]
    )
    payload += "]"
    "{{\\"name\\":\\"" + (esc flow.name) + "\\",\\"total\\":" + (total as string) + ",\\"returned\\":" + (takeCount as string) + ",\\"particles\\":" + payload + "}}"
)
)"""
    return json.dumps(_send_json(maxscript, {"error": "Could not parse get_tyflow_particles response."}))


@mcp.tool()
def reset_tyflow_simulation(name: str = "") -> str:
    """Reset simulation for one tyFlow object or for all tyFlow objects."""
    maxscript = f"""(
{HELPERS}
local targets = #()
if "{safe_string(name)}" != "" then (
    local node = getNodeByName "{safe_string(name)}"
    if node != undefined then append targets node
) else (
    for o in objects where ((classof o.baseobject as string) == "tyFlow" or (classof o as string) == "tyFlow") do append targets o
)
if targets.count == 0 then (
    "{{\\"error\\":\\"No tyFlow objects found\\"}}"
) else (
    local resetNames = #()
    for n in targets do (
        try (n.reset_simulation(); append resetNames n.name) catch ()
    )
    "{{\\"count\\":" + (resetNames.count as string) + ",\\"names\\":" + (jsonStringArray resetNames) + "}}"
)
)"""
    return json.dumps(_send_json(maxscript, {"error": "Could not parse reset_tyflow_simulation response."}))


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
    """
    sa_evt = _sa_name(event_name)

    lines: list[str] = []
    lines.append(f'local tfObj = getNodeByName "{safe_string(tyflow_name)}"')
    lines.append('if tfObj == undefined then (')
    lines.append(f'  "{{\\"error\\":\\"tyFlow \\\\\\"{safe_string(tyflow_name)}\\\\\\" not found\\"}}"')
    lines.append(') else (')
    lines.append('  local evRef = undefined')
    lines.append(f'  try (evRef = tfObj.baseobject[{sa_evt}]) catch ()')
    lines.append('  if evRef == undefined then (')
    lines.append(f'    "{{\\"error\\":\\"Event \\\\\\"{safe_string(event_name)}\\\\\\" not found\\"}}"')
    lines.append('  ) else (')
    lines.append('    local globalOp = undefined')
    lines.append('    try (globalOp = evRef[#Global]) catch ()')
    lines.append('    if globalOp == undefined do (')
    lines.append('      try (globalOp = evRef.addOperator "Global" -1) catch ()')
    lines.append('    )')
    lines.append('    if globalOp == undefined then (')
    lines.append('      "{\\"error\\":\\"Could not add Global operator. Requires tyFlow 2.0+.\\"}"')
    lines.append('    ) else (')
    lines.append(f'      try (globalOp.setEnabled {_mxs_value(enabled)}) catch ()')
    lines.append(f'      try (globalOp.affectEvents = {affect_mode}) catch ()')
    if include_events is not None:
        lines.append(f'      try (globalOp.includeEventNames = "{safe_string(include_events)}") catch ()')
    if exclude_events is not None:
        lines.append(f'      try (globalOp.excludeEventNames = "{safe_string(exclude_events)}") catch ()')
    lines.append(f'      "{{\\"success\\":true,\\"event\\":\\"{safe_string(event_name)}\\",\\"global\\":{_mxs_value(enabled)}}}"')
    lines.append('    )')
    lines.append('  )')
    lines.append(')')

    ms = "(\n    " + "\n    ".join(lines) + "\n)"
    return json.dumps(_send_json(ms, {"error": "Could not parse set_tyflow_global_event response."}))


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

    Calls ``exportTyCache()`` on an Export Particles operator. Optionally
    configures the output path, frame range, and whether a tyCache scene
    object is created automatically. The export runs synchronously.
    """
    sa_evt = _sa_name(event_name)
    sa_op = _sa_name(operator_name)

    lines: list[str] = []
    lines.append(f'local tfObj = getNodeByName "{safe_string(tyflow_name)}"')
    lines.append('if tfObj == undefined then (')
    lines.append(f'  "{{\\"error\\":\\"tyFlow \\\\\\"{safe_string(tyflow_name)}\\\\\\" not found\\"}}"')
    lines.append(') else (')
    lines.append('  local opRef = undefined')
    lines.append(f'  try (opRef = tfObj.baseobject[{sa_evt}][{sa_op}]) catch ()')
    lines.append('  if opRef == undefined then (')
    lines.append(f'    "{{\\"error\\":\\"Operator \\\\\\"{safe_string(operator_name)}\\\\\\" not found in event \\\\\\"{safe_string(event_name)}\\\\\\"\\"}}"')
    lines.append('  ) else (')
    lines.append('    try (opRef.exportMode = 2) catch ()  -- tyCache mode')
    if output_path is not None:
        lines.append(f'    try (opRef.tyCacheFilename = "{safe_string(output_path)}") catch ()')
    lines.append(f'    try (opRef.tycacheCreateObject = {_mxs_value(create_tycache_object)}) catch ()')
    lines.append(f'    try (opRef.tycacheCreateObjectIfNotCreated = {_mxs_value(only_if_not_created)}) catch ()')
    if frame_start is not None:
        lines.append(f'    try (opRef.frameStart = {int(frame_start)}) catch ()')
    if frame_end is not None:
        lines.append(f'    try (opRef.frameEnd = {int(frame_end)}) catch ()')
    lines.append('    local exportResult = opRef.exportTyCache()')
    lines.append('    local cachePath = try (opRef.tyCacheFilename) catch ("")')
    lines.append(f'    "{{\\"success\\":true,\\"tyflow\\":\\"{safe_string(tyflow_name)}\\",\\"cachePath\\":\\"" + (substituteString cachePath "\\\\" "/") + "\\"}}"')
    lines.append('  )')
    lines.append(')')

    ms = "(\n    " + "\n    ".join(lines) + "\n)"
    return json.dumps(_send_json(ms, {"error": "Could not parse export_tyflow_cache response."}))


# ---------------------------------------------------------------------------
# Inferno / preset tools (ported from local branch)
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
def create_tyflow_preset(
    preset: str,
    name: str = "",
    position: FloatList | None = None,
    particle_count: int | None = None,
    shape: str | None = None,
    scale: float = 100.0,
    speed: float | None = None,
    lifetime_frames: int | None = None,
) -> str:
    """Create a tyFlow with a preset particle effect configuration.

    Presets: fountain, rain, explosion, snow, debris, confetti, sparks, smoke.
    Each preset builds appropriate events, operators, and settings for the
    named effect. Override individual parameters to customize.
    """
    pos = position or [0.0, 0.0, 0.0]
    actual_name = name or f"ty_{preset.lower()}"
    safe = safe_string(actual_name)
    p = preset.lower()

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
        return json.dumps({"error": f"Unknown preset: {preset}. Available: {available}"})

    d = _defaults[p]
    count = particle_count if particle_count is not None else d["count"]
    spd = speed if speed is not None else d["speed_mag"]
    lifetime = lifetime_frames if lifetime_frames is not None else d["kill_age"]

    if shape:
        shape_lower = shape.lower()
        shape_id = SHAPE_3D_IDS.get(shape_lower, d["shape_id"])
    else:
        shape_id = d["shape_id"]

    shape_scale = scale if scale != 100.0 else d["shape_scale"]
    shape_scale_var = d["shape_scale_var"]

    # Build operator list and delegate to create_tyflow
    ops: list[dict] = []
    op_pos = 0

    # Birth
    birth_props: dict[str, object] = {"birthStart": 0}
    if d["birth_mode"] == 0:
        birth_props.update({"birthMode": 0, "birthTotal": count, "birthEndEnable": True, "birthEnd": 2})
    else:
        birth_props.update({"birthMode": 1, "birthPerFrame": d["birth_per_frame"]})
    ops.append({"type": "Birth", "name": "Birth", "position": op_pos, "properties": birth_props})
    op_pos += 1

    # Speed
    speed_props: dict[str, object] = {
        "magnitude": spd, "magnitudeVariation": d["speed_var"], "directionMode": d["speed_dir"],
    }
    if d.get("speed_reverse"):
        speed_props["directionReverse"] = True
    ops.append({"type": "Speed", "name": "Speed", "position": op_pos, "properties": speed_props})
    op_pos += 1

    # Force (optional)
    if d["gravity"] != 0.0:
        force_props: dict[str, object] = {"gravityStrength": d["gravity"]}
        if p in ("snow", "confetti"):
            force_props["windStrength"] = 30.0
        if p == "smoke":
            force_props["windStrength"] = 20.0
        ops.append({"type": "Force", "name": "Force", "position": op_pos, "properties": force_props})
        op_pos += 1

    # Spin (optional)
    if d.get("has_spin"):
        spin_props: dict[str, object] = {}
        if p in ("confetti", "snow"):
            spin_props = {"spinX": 50.0, "spinY": 50.0, "spinZ": 50.0}
        ops.append({"type": "Spin", "name": "Spin", "position": op_pos, "properties": spin_props})
        op_pos += 1

    # Kill Age (optional)
    if d.get("has_kill_age"):
        ops.append({"type": "Kill Age", "name": "Kill Age", "position": op_pos, "properties": {"age": lifetime, "ageVariation": 20}})
        op_pos += 1

    # Shape
    ops.append({
        "type": "Shape", "name": "Shape", "position": op_pos,
        "properties": {
            "shape_type_tab": [1], "type_3d_ID_tab": [shape_id],
            "frequency_tab": [100.0], "scaleVal_tab": [shape_scale], "scaleVariation_tab": [shape_scale_var],
        },
    })
    op_pos += 1

    # Display
    ops.append({"type": "Display", "name": "Display", "position": op_pos, "properties": {"displayMode": 2}})
    op_pos += 1

    return create_tyflow(name=actual_name, position=pos, operators=ops)


@mcp.tool()
def create_tyflow_inferno(
    name: str = "tyInferno001",
    preset: str | None = None,
    position: FloatList | None = None,
    emitter_objects: StrList | None = None,
    voxel_size: float = 2.0,
    temperature: float = 1500.0,
    buoyancy: float = 1.0,
    cooling: float = 0.5,
    dissipation: float = 0.02,
    vorticity: float = 0.5,
    enable_collision: bool = False,
    collision_objects: StrList | None = None,
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
    """
    safe = safe_string(name)

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
    lines.append('local tfObj = tyflow()')
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
        obj_refs = " ".join(f'(getNodeByName "{safe_string(o)}")' for o in emitter_objects)
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
            obj_refs = " ".join(f'(getNodeByName "{safe_string(o)}")' for o in collision_objects)
            lines.append(f'  try (colliderOp.objectList = #({obj_refs})) catch ()')
        if enable_ground:
            lines.append('  try (colliderOp.builtinGround = true) catch ()')
            lines.append(f'  try (colliderOp.builtinGroundHeight = {ground_height:.4f}) catch ()')

    # Export Inferno (optional)
    if enable_export:
        lines.append('  local exportOp = ev1.addOperator "Export Inferno" opIdx')
        lines.append('  opIdx += 1')
        if export_path:
            lines.append(f'  try (exportOp.filenameSolver = "{safe_string(export_path)}") catch ()')
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
    return json.dumps(_send_json(ms, {"error": "Could not parse create_tyflow_inferno response."}))


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
    """
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
        return json.dumps({"error": "No properties specified to change."})

    for prop_name, prop_val in set_props.items():
        prop_lines.append(f'  try (opRef.{prop_name} = {_mxs_value(prop_val)}) catch ()')

    modified_json = ", ".join(f'\\"{k}\\"' for k in set_props)

    ms = f"""(
    local tfObj = getNodeByName "{safe_string(tyflow_name)}"
    if tfObj == undefined then (
        "{{\\"error\\":\\"tyFlow \\\\\\"{safe_string(tyflow_name)}\\\\\\" not found\\"}}"
    ) else (
        local opRef = undefined
        try (opRef = tfObj.baseobject[{sa_evt}][{sa_op}]) catch ()
        if opRef == undefined then (
            "{{\\"error\\":\\"Operator \\\\\\"{safe_string(operator_name)}\\\\\\" not found in event \\\\\\"{safe_string(event_name)}\\\\\\"\\"}}"
        ) else (
{chr(10).join(prop_lines)}
            "{{\\"success\\":true,\\"modified\\":[{modified_json}]}}"
        )
    )
)"""
    return json.dumps(_send_json(ms, {"error": "Could not parse set_tyflow_inferno_display response."}))


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
    """
    sa_evt = _sa_name(event_name)
    sa_op = _sa_name(operator_name)

    lines: list[str] = []
    lines.append(f'local tfObj = getNodeByName "{safe_string(tyflow_name)}"')
    lines.append('if tfObj == undefined then (')
    lines.append(f'  "{{\\"error\\":\\"tyFlow \\\\\\"{safe_string(tyflow_name)}\\\\\\" not found\\"}}"')
    lines.append(') else (')
    lines.append('  local opRef = undefined')
    lines.append(f'  try (opRef = tfObj.baseobject[{sa_evt}][{sa_op}]) catch ()')
    lines.append('  if opRef == undefined then (')
    lines.append(f'    "{{\\"error\\":\\"Operator \\\\\\"{safe_string(operator_name)}\\\\\\" not found in event \\\\\\"{safe_string(event_name)}\\\\\\"\\"}}"')
    lines.append('  ) else (')
    lines.append(f'    try (opRef.filenameSolver = "{safe_string(output_path)}") catch ()')
    lines.append(f'    try (opRef.gridDensity = {_mxs_value(export_density)}) catch ()')
    lines.append(f'    try (opRef.gridTemperature = {_mxs_value(export_temperature)}) catch ()')
    lines.append(f'    try (opRef.gridVelocity = {_mxs_value(export_velocity)}) catch ()')
    lines.append(f'    try (opRef.gridColor = {_mxs_value(export_color)}) catch ()')
    lines.append(f'    try (opRef.gridFuel = {_mxs_value(export_fuel)}) catch ()')
    lines.append(f'    try (opRef.gridVelocityMaskWithDensity = {_mxs_value(velocity_mask_with_density)}) catch ()')
    lines.append(f'    try (opRef.gridTemperatureUnitsEnabled = {_mxs_value(temperature_units_enabled)}) catch ()')
    lines.append(f'    try (opRef.gridTemperatureUnits = {temperature_units}) catch ()')
    if frame_start is not None:
        lines.append(f'    try (opRef.frameStart = {int(frame_start)}) catch ()')
    if frame_end is not None:
        lines.append(f'    try (opRef.frameEnd = {int(frame_end)}) catch ()')
    lines.append(f'    "{{\\"success\\":true,\\"path\\":\\"{safe_string(output_path)}\\",\\"channels\\":[\\"density\\",\\"temperature\\",\\"velocity\\"]}}"')
    lines.append('  )')
    lines.append(')')

    ms = "(\n    " + "\n    ".join(lines) + "\n)"
    return json.dumps(_send_json(ms, {"error": "Could not parse export_tyflow_inferno_vdb response."}))


@mcp.tool()
def get_tyflow_volume_data(
    tyflow_name: str,
    positions: list[list[float]],
    scalar_types: StrList | None = None,
    vector_types: StrList | None = None,
    temperature_units: str = "kelvin",
) -> str:
    """Sample scalar/vector data from a tyFlow Inferno fluid grid at world-space positions.

    Requires tyFlow 2.0+ with an active Inferno simulation. Calls
    updateVolumes() / releaseVolumes() to safely access GPU volume data.
    """
    scalar_map = {"density": 0, "fuel": 1, "temperature": 2}
    vector_map = {"color": 0, "velocity": 1}
    temp_unit_map = {"celsius": 1, "fahrenheit": 2, "kelvin": 3}

    scalars = scalar_types or []
    vectors = vector_types or []
    temp_unit = temp_unit_map.get(temperature_units, 3)

    lines: list[str] = []
    lines.append(f'local tfObj = getNodeByName "{safe_string(tyflow_name)}"')
    lines.append('if tfObj == undefined then (')
    lines.append(f'  "{{\\"error\\":\\"tyFlow \\\\\\"{safe_string(tyflow_name)}\\\\\\" not found\\"}}"')
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
    return json.dumps(_send_json(ms, {"error": "Could not parse get_tyflow_volume_data response."}))


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
    """
    unit_map = {"celsius": 1, "fahrenheit": 2, "kelvin": 3}
    from_id = unit_map.get(from_units)
    to_id = unit_map.get(to_units)
    if from_id is None or to_id is None:
        return json.dumps({"error": "Invalid units. Use celsius, fahrenheit, or kelvin."})

    ms = f"""(
    local tfObj = getNodeByName "{safe_string(tyflow_name)}"
    if tfObj == undefined then (
        "{{\\"error\\":\\"tyFlow \\\\\\"{safe_string(tyflow_name)}\\\\\\" not found\\"}}"
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
    return json.dumps(_send_json(ms, {"error": "Could not parse convert_tyflow_temperature response."}))
