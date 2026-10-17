#include "mcp_bridge/native_handlers.h"
#include "mcp_bridge/handler_helpers.h"
#include "mcp_bridge/spatial_snapshot.h"
#include "mcp_bridge/bridge_gup.h"

#include <iparamb2.h>
#include <istdplug.h>
#include <decomp.h>
#include <algorithm>
#include <cmath>
#include <set>
#include <unordered_map>

using json = nlohmann::json;
using namespace HandlerHelpers;

// ── native:get_object_properties ────────────────────────────────
std::string NativeHandlers::GetObjectProperties(const std::string& params, MCPBridgeGUP* gup) {
    return gup->GetExecutor().ExecuteSync([&params]() -> std::string {
        json p = json::parse(params, nullptr, false);
        INode* node = ResolveNodeFromPayload(p);

        Interface* ip = GetCOREInterface();
        TimeValue t = ip->GetTime();

        json result;
        result["name"] = WideToUtf8(node->GetName());
        result["handle"] = NodeHandle(node);

        // Class info
        ObjectState os = node->EvalWorldState(t);
        result["class"] = os.obj ? WideToUtf8(os.obj->ClassName().data()) : "Unknown";
        // Get superclass name via MAXScript — no direct SDK method
        if (os.obj) {
            SClass_ID scid = os.obj->SuperClassID();
            if (scid == GEOMOBJECT_CLASS_ID) result["superclass"] = "GeometryClass";
            else if (scid == CAMERA_CLASS_ID) result["superclass"] = "camera";
            else if (scid == LIGHT_CLASS_ID) result["superclass"] = "light";
            else if (scid == SHAPE_CLASS_ID) result["superclass"] = "shape";
            else if (scid == HELPER_CLASS_ID) result["superclass"] = "helper";
            else if (scid == SYSTEM_CLASS_ID) result["superclass"] = "system";
            else result["superclass"] = "Unknown";
        } else {
            result["superclass"] = "Unknown";
        }

        // Transform
        Matrix3 tm = node->GetNodeTM(t);
        Point3 pos = tm.GetTrans();
        result["position"] = json::array({pos.x, pos.y, pos.z});

        // Rotation (as Euler angles)
        AffineParts ap;
        decomp_affine(tm, &ap);
        float euler[3];
        QuatToEuler(ap.q, euler, EULERTYPE_XYZ);
        result["rotation"] = json::array({RadToDeg(euler[0]), RadToDeg(euler[1]), RadToDeg(euler[2])});

        // Scale
        result["scale"] = json::array({ap.k.x, ap.k.y, ap.k.z});

        // Hierarchy
        INode* parent = node->GetParentNode();
        result["parent"] = (parent && !parent->IsRootNode()) ?
            json(WideToUtf8(parent->GetName())) : json(nullptr);

        json children = json::array();
        for (int i = 0; i < node->NumberOfChildren(); i++) {
            children.push_back(WideToUtf8(node->GetChildNode(i)->GetName()));
        }
        result["children"] = children;

        // Layer
        result["layer"] = NodeLayerName(node);

        // Wire color
        result["wirecolor"] = NodeWireColor(node);

        // Material
        Mtl* mtl = node->GetMtl();
        result["material"] = mtl ? WideToUtf8(mtl->GetName().data()) : "none";

        // Modifiers
        json mods = json::array();
        Object* objRef = node->GetObjectRef();
        if (objRef && objRef->SuperClassID() == GEN_DERIVOB_CLASS_ID) {
            IDerivedObject* dobj = (IDerivedObject*)objRef;
            for (int m = 0; m < dobj->NumModifiers(); m++) {
                Modifier* mod = dobj->GetModifier(m);
                if (mod) mods.push_back(WideToUtf8(mod->ClassName().data()));
            }
        }
        result["modifiers"] = mods;

        // Mesh stats via snapshot
        result["numVerts"] = nullptr;
        result["numFaces"] = nullptr;
        if (os.obj && os.obj->CanConvertToType(triObjectClassID)) {
            BOOL needDel = FALSE;
            TriObject* tri = (TriObject*)os.obj->ConvertToType(t, triObjectClassID);
            if (tri) {
                Mesh& mesh = tri->GetMesh();
                result["numVerts"] = mesh.getNumVerts();
                result["numFaces"] = mesh.getNumFaces();
                if (tri != os.obj) tri->MaybeAutoDelete();
            }
        }

        // Bounding box dimensions
        if (os.obj) {
            Box3 bbox;
            os.obj->GetDeformBBox(t, bbox);
            Matrix3 nodeTM = node->GetNodeTM(t);
            Point3 corners[8];
            corners[0] = Point3(bbox.Min().x, bbox.Min().y, bbox.Min().z) * nodeTM;
            corners[1] = Point3(bbox.Max().x, bbox.Min().y, bbox.Min().z) * nodeTM;
            corners[2] = Point3(bbox.Min().x, bbox.Max().y, bbox.Min().z) * nodeTM;
            corners[3] = Point3(bbox.Max().x, bbox.Max().y, bbox.Min().z) * nodeTM;
            corners[4] = Point3(bbox.Min().x, bbox.Min().y, bbox.Max().z) * nodeTM;
            corners[5] = Point3(bbox.Max().x, bbox.Min().y, bbox.Max().z) * nodeTM;
            corners[6] = Point3(bbox.Min().x, bbox.Max().y, bbox.Max().z) * nodeTM;
            corners[7] = Point3(bbox.Max().x, bbox.Max().y, bbox.Max().z) * nodeTM;
            Point3 wMin = corners[0], wMax = corners[0];
            for (int c = 1; c < 8; c++) {
                if (corners[c].x < wMin.x) wMin.x = corners[c].x;
                if (corners[c].y < wMin.y) wMin.y = corners[c].y;
                if (corners[c].z < wMin.z) wMin.z = corners[c].z;
                if (corners[c].x > wMax.x) wMax.x = corners[c].x;
                if (corners[c].y > wMax.y) wMax.y = corners[c].y;
                if (corners[c].z > wMax.z) wMax.z = corners[c].z;
            }
            Point3 dims = wMax - wMin;
            result["dimensions"] = json::array({dims.x, dims.y, dims.z});
        }

        return result.dump();
    });
}

// ── Parse a Point3 from string "[x,y,z]" or "x,y,z" ────────────
static bool ParsePoint3(const std::string& s, Point3& out) {
    double v[3] = {0, 0, 0};
    if (!mcp_bridge::number_text::ParseDoubleList(s, v, 3)) return false;  // locale-independent
    out = Point3(static_cast<float>(v[0]), static_cast<float>(v[1]), static_cast<float>(v[2]));
    return true;
}

// ── Parse a Color from string "(color r g b)" or "r,g,b" or named ──
static bool ParseColor(const std::string& s, DWORD& out) {
    // Named colors
    std::string lower = s;
    std::transform(lower.begin(), lower.end(), lower.begin(), ::tolower);
    if (lower == "red")     { out = RGB(255,0,0); return true; }
    if (lower == "green")   { out = RGB(0,255,0); return true; }
    if (lower == "blue")    { out = RGB(0,0,255); return true; }
    if (lower == "white")   { out = RGB(255,255,255); return true; }
    if (lower == "black")   { out = RGB(0,0,0); return true; }
    if (lower == "yellow")  { out = RGB(255,255,0); return true; }
    if (lower == "orange")  { out = RGB(255,165,0); return true; }
    if (lower == "gray" || lower == "grey") { out = RGB(128,128,128); return true; }

    // "(color r g b)" (0-255) or "[r,g,b]" / "r,g,b", parsed locale-independently.
    double v[4] = {0, 0, 0, 0};
    int n = 0;
    if (!mcp_bridge::number_text::ParseMaxColor(s, v, n) &&
        !mcp_bridge::number_text::ParseDoubleList(s, v, 3)) {
        return false;
    }
    auto clamp255 = [](double c) { return int(c < 0 ? 0 : (c > 255 ? 255 : c + 0.5)); };
    out = RGB(clamp255(v[0]), clamp255(v[1]), clamp255(v[2]));
    return true;
}

// ── native:set_object_property (Pure SDK) ───────────────────────
std::string NativeHandlers::SetObjectProperty(const std::string& params, MCPBridgeGUP* gup) {
    return gup->GetExecutor().ExecuteSync([&params]() -> std::string {
        json p = json::parse(params, nullptr, false);
        std::string prop = p.value("property", "");
        std::string value = p.value("value", "");

        if (prop.empty()) throw std::runtime_error("property is required");

        INode* node = ResolveNodeFromPayload(p);

        Interface* ip = GetCOREInterface();
        TimeValue t = ip->GetTime();

        // Convert prop to lowercase for comparison
        std::string lprop = prop;
        std::transform(lprop.begin(), lprop.end(), lprop.begin(), ::tolower);

        auto propertyResult = [&](const std::string& message, const std::string& applied) -> std::string {
            json result = NodeIdentityJson(node);
            result["message"] = message;
            result["property"] = prop;
            result["value"] = value;
            result["applied"] = applied;  // read back after the write
            if (lprop == "pos" || lprop == "position") {
                result["spatial"] = SpatialSnapshot::BuildSpatialSnapshot(node, t);
            }
            return result.dump();
        };
        // Fail loud: the property was requested and did not end up as asked.
        auto partial = [&](const std::string& applied, bool hasApplied, const std::string& reason) {
            json details = NodeIdentityJson(node);
            details["keys"] = json::array({PartialKey(prop, value, applied, hasApplied, reason)});
            ThrowPartialApply("set_object_property: " + prop + " not applied on " +
                              WideToUtf8(node->GetName()) + " (" + reason + ")", details);
        };
        auto parseBool = [&](bool& out) -> bool {
            std::string lv = value;
            std::transform(lv.begin(), lv.end(), lv.begin(), ::tolower);
            if (lv == "true" || lv == "1" || lv == "on") { out = true; return true; }
            if (lv == "false" || lv == "0" || lv == "off") { out = false; return true; }
            return false;
        };
        auto boolText = [](bool b) { return std::string(b ? "true" : "false"); };

        // ── Node-level properties (direct SDK, read back) ───────
        if (lprop == "pos" || lprop == "position") {
            Point3 pt;
            if (!ParsePoint3(value, pt)) partial("", false, "cannot parse Point3 from the value");
            Matrix3 tm = node->GetNodeTM(t);
            tm.SetTrans(pt);
            node->SetNodeTM(t, tm);
            ip->RedrawViews(t);
            const Point3 got = node->GetNodeTM(t).GetTrans();
            const float gl[3] = {got.x, got.y, got.z};
            const std::string applied = mcp_bridge::number_text::FormatList(gl, 3);
            const double w[3] = {pt.x, pt.y, pt.z};
            const double g[3] = {got.x, got.y, got.z};
            if (!mcp_bridge::param_units::ComponentsMatch(w, g, 3, 1e-4)) {
                partial(applied, true, "node position differs after the write (locked or constrained controller?)");
            }
            return propertyResult("Set pos on " + WideToUtf8(node->GetName()), applied);
        }

        if (lprop == "wirecolor") {
            DWORD col;
            if (!ParseColor(value, col)) partial("", false, "cannot parse a colour from the value");
            node->SetWireColor(col);
            ip->RedrawViews(t);
            const DWORD got = node->GetWireColor();
            const std::string applied = "(color " + std::to_string(GetRValue(got)) + " " +
                                        std::to_string(GetGValue(got)) + " " + std::to_string(GetBValue(got)) + ")";
            if ((got & 0xFFFFFF) != (col & 0xFFFFFF)) partial(applied, true, "wirecolor differs after the write");
            return propertyResult("Set wirecolor on " + WideToUtf8(node->GetName()), applied);
        }

        if (lprop == "name") {
            std::wstring wval = Utf8ToWide(value);
            // Strip quotes
            if (wval.size() >= 2 && wval.front() == L'"' && wval.back() == L'"')
                wval = wval.substr(1, wval.size() - 2);
            node->SetName(wval.c_str());
            const std::string applied = WideToUtf8(node->GetName());
            if (Utf8ToWide(applied) != wval) partial(applied, true, "name differs after the write");
            return propertyResult("Set name on " + applied, applied);
        }

        if (lprop == "ishidden" || lprop == "hidden" || lprop == "isfrozen" || lprop == "frozen" ||
            lprop == "renderable") {
            bool v = false;
            if (!parseBool(v)) partial("", false, "expected true/false");
            bool got = false;
            std::string label;
            if (lprop == "ishidden" || lprop == "hidden") {
                node->Hide(v ? TRUE : FALSE);
                got = node->IsHidden() != 0;
                label = "isHidden";
            } else if (lprop == "isfrozen" || lprop == "frozen") {
                node->Freeze(v ? TRUE : FALSE);
                got = node->IsFrozen() != 0;
                label = "isFrozen";
            } else {
                node->SetRenderable(v ? TRUE : FALSE);
                got = node->Renderable() != 0;
                label = "renderable";
            }
            ip->RedrawViews(t);
            if (got != v) partial(boolText(got), true, label + " differs after the write");
            return propertyResult("Set " + label + " on " + WideToUtf8(node->GetName()), boolText(got));
        }

        // ── Base object IParamBlock2 properties, then MAXScript ──
        Object* baseObj = node->GetObjectRef();
        // Walk past derived objects to get the base
        while (baseObj && baseObj->SuperClassID() == GEN_DERIVOB_CLASS_ID) {
            baseObj = ((IDerivedObject*)baseObj)->GetObjRef();
        }

        // Whatever IParamBlock2 cannot write (legacy PB1 object, unit/expression
        // value, non-PB property) MAXScript evaluates exactly, by anim handle.
        const SetOutcome outcome = SetParamWithFallback(
            baseObj, "(getAnimByHandle " + std::to_string(NodeHandle(node)) + ")", prop, value, t);
        if (baseObj) baseObj->NotifyDependents(FOREVER, PART_ALL, REFMSG_CHANGE);
        ip->RedrawViews(t);
        if (!outcome.ok()) partial(outcome.applied, outcome.hasApplied, outcome.reason);
        return propertyResult("Set " + prop + " on " + WideToUtf8(node->GetName()), outcome.applied);
    });
}

// ── Parse MAXScript-style "key:value" param pairs ──────────────
// Input: "radius:25 pos:[0,0,50] name:\"Foo\""
// Returns vector of {key, value} pairs
static std::vector<std::pair<std::string, std::string>> ParseParamString(const std::string& s) {
    std::vector<std::pair<std::string, std::string>> result;
    size_t i = 0;
    while (i < s.size()) {
        // Skip whitespace
        while (i < s.size() && s[i] == ' ') i++;
        if (i >= s.size()) break;

        // Find key (up to ':')
        size_t keyStart = i;
        while (i < s.size() && s[i] != ':') i++;
        if (i >= s.size()) break;
        std::string key = s.substr(keyStart, i - keyStart);
        i++; // skip ':'

        // Parse value — handle brackets and quotes
        size_t valStart = i;
        if (i < s.size() && (s[i] == '[' || s[i] == '(')) {
            // Scan to the matching ']' / ')' so "(2 * 3.25)" stays one value
            const char open = s[i], close = (open == '[') ? ']' : ')';
            int depth = 1;
            i++;
            while (i < s.size() && depth > 0) {
                if (s[i] == open) depth++;
                else if (s[i] == close) depth--;
                i++;
            }
        } else if (i < s.size() && s[i] == '"') {
            // Scan to matching '"'
            i++;
            while (i < s.size() && s[i] != '"') {
                if (s[i] == '\\') i++; // skip escaped char
                i++;
            }
            if (i < s.size()) i++; // skip closing quote
        } else {
            // Scan to next space
            while (i < s.size() && s[i] != ' ') i++;
        }
        std::string val = s.substr(valStart, i - valStart);
        result.push_back({key, val});
    }
    return result;
}

static std::string ToLowerCopy(std::string s) {
    std::transform(s.begin(), s.end(), s.begin(), ::tolower);
    return s;
}

static bool HasParam(const std::vector<std::pair<std::string, std::string>>& params,
                     const std::string& key) {
    std::string lkey = ToLowerCopy(key);
    for (const auto& [paramKey, _] : params) {
        if (ToLowerCopy(paramKey) == lkey) {
            return true;
        }
    }
    return false;
}

static void UpsertParam(std::vector<std::pair<std::string, std::string>>& params,
                        const std::string& key,
                        const std::string& value) {
    std::string lkey = ToLowerCopy(key);
    for (auto& [paramKey, paramValue] : params) {
        if (ToLowerCopy(paramKey) == lkey) {
            paramValue = value;
            return;
        }
    }
    params.push_back({key, value});
}

static std::string DefaultCreateObjectParams(const std::string& type) {
    static const std::unordered_map<std::string, std::string> kDefaults = {
        {"box", "length:25 width:25 height:25"},
        {"sphere", "radius:25"},
        {"cylinder", "radius:10 height:25"},
        {"cone", "radius1:15 radius2:0 height:25"},
        {"torus", "radius:20 radius2:5"},
        {"plane", "length:50 width:50"},
        {"teapot", "radius:15"},
        {"tube", "radius1:15 radius2:10 height:25"},
        {"pyramid", "width:25 depth:25 height:25"},
        {"geosphere", "radius:25"},
        {"hedra", "radius:15"},
        {"torusknot", "radius:20 radius2:4"},
        {"chamferbox", "length:25 width:25 height:25 fillet:2"},
        {"chamfercyl", "radius:10 height:25 fillet:2"},
        {"oiltank", "radius:15 height:25 capheight:5"},
        {"spindle", "radius:15 height:25 capheight:5"},
        {"capsule", "radius:10 height:25"},
    };
    auto it = kDefaults.find(ToLowerCopy(type));
    return it != kDefaults.end() ? it->second : "";
}

static std::string JsonValueToParamString(const json& value, bool rawString = false) {
    switch (value.type()) {
    case json::value_t::null:
    case json::value_t::discarded:
        return {};
    case json::value_t::string:
        return rawString ? value.get<std::string>() : value.dump();
    case json::value_t::object:
        return {};
    default:
        return value.dump();
    }
}

static void MergeJsonParams(const json& source,
                            std::vector<std::pair<std::string, std::string>>& out) {
    if (source.type() != json::value_t::object) {
        return;
    }

    for (auto it = source.begin(); it != source.end(); ++it) {
        std::string key = it.key();
        std::string lkey = ToLowerCopy(key);
        if (lkey == "position") {
            key = "pos";
            lkey = "pos";
        }
        std::string value = JsonValueToParamString(it.value(), lkey == "pos");
        if (value.empty()) {
            continue;
        }
        UpsertParam(out, key, value);
    }
}

// `defaultKeys` receives the (lower-case) keys the bridge added itself, which
// the caller did not request.
static std::vector<std::pair<std::string, std::string>> BuildCreateObjectParams(
    const json& payload,
    const std::string& type,
    std::set<std::string>* defaultKeys = nullptr) {

    std::vector<std::pair<std::string, std::string>> kvPairs;

    auto paramsIt = payload.find("params");
    if (paramsIt != payload.end()) {
        if (paramsIt->type() == json::value_t::string) {
            kvPairs = ParseParamString(paramsIt->get<std::string>());
        } else if (paramsIt->type() == json::value_t::object) {
            MergeJsonParams(*paramsIt, kvPairs);
        }
    }

    if (payload.type() == json::value_t::object) {
        for (auto it = payload.begin(); it != payload.end(); ++it) {
            std::string lkey = ToLowerCopy(it.key());
            if (lkey == "type" || lkey == "name" || lkey == "params" || lkey == "pos_mode") {
                continue;
            }
            json wrapper = json::object();
            wrapper[it.key()] = it.value();
            MergeJsonParams(wrapper, kvPairs);
        }
    }

    for (const auto& [key, value] : ParseParamString(DefaultCreateObjectParams(type))) {
        if (!HasParam(kvPairs, key)) {
            kvPairs.push_back({key, value});
            if (defaultKeys) defaultKeys->insert(ToLowerCopy(key));
        }
    }

    return kvPairs;
}

// ── native:create_object (Pure SDK) ─────────────────────────────
std::string NativeHandlers::CreateObject(const std::string& params, MCPBridgeGUP* gup) {
    return gup->GetExecutor().ExecuteSync([&params]() -> std::string {
        json p = json::parse(params, nullptr, false);
        std::string type = p.value("type", "");
        std::string name = p.value("name", "");
        const SpatialSnapshot::PosMode posMode = SpatialSnapshot::ParsePosMode(p.value("pos_mode", "ground"));

        if (type.empty()) throw std::runtime_error("type is required");

        Interface* ip = GetCOREInterface();
        TimeValue t = ip->GetTime();

        // Find ClassDesc for this type — try geometry first, then all
        ClassDesc* cd = FindClassDescByName(type, GEOMOBJECT_CLASS_ID);
        if (!cd) cd = FindClassDescByName(type, SHAPE_CLASS_ID);
        if (!cd) cd = FindClassDescByName(type, LIGHT_CLASS_ID);
        if (!cd) cd = FindClassDescByName(type, CAMERA_CLASS_ID);
        if (!cd) cd = FindClassDescByName(type, HELPER_CLASS_ID);
        if (!cd) cd = FindClassDescByName(type, SYSTEM_CLASS_ID);
        if (!cd) cd = FindClassDescByName(type); // any superclass
        if (!cd) throw std::runtime_error("Unknown object class: " + type);

        // Create the object instance
        Object* obj = (Object*)ip->CreateInstance(cd->SuperClassID(), cd->ClassID());
        if (!obj) throw std::runtime_error("Failed to create instance of: " + type);

        // Create node in scene
        INode* node = ip->CreateObjectNode(obj);
        if (!node) throw std::runtime_error("Failed to create node for: " + type);

        // Set name
        if (!name.empty()) {
            std::wstring wname = Utf8ToWide(name);
            node->SetName(wname.c_str());
        }

        // Apply params: IParamBlock2 first, MAXScript by anim handle for the
        // rest (PB1/legacy objects like Capsule, Hedra; unit or expression
        // values). Every key is read back.
        Point3 posOverride(0, 0, 0);
        bool hasPos = false;
        std::set<std::string> defaultKeys;
        json failedKeys = json::array();        // requested keys that did not stick
        json failedDefaults = json::array();    // bridge defaults that did not stick (warn only)
        json applied = json::object();
        auto kvPairs = BuildCreateObjectParams(p, type, &defaultKeys);
        const std::string target = "(getAnimByHandle " + std::to_string(NodeHandle(node)) + ")";

        for (auto& [key, val] : kvPairs) {
            const std::string lkey = ToLowerCopy(key);

            // pos is a node-level placement, applied (and reported) by pos_mode below.
            if (lkey == "pos") {
                if (ParsePoint3(val, posOverride)) {
                    hasPos = true;
                } else {
                    failedKeys.push_back(PartialKey(key, val, "", false, "cannot parse Point3 from the value"));
                }
                continue;
            }

            const SetOutcome outcome = SetParamWithFallback(obj, target, key, val, t);
            if (outcome.ok()) {
                applied[key] = outcome.applied;
                continue;
            }
            json entry = PartialKey(key, val, outcome.applied, outcome.hasApplied, outcome.reason);
            if (defaultKeys.count(lkey)) failedDefaults.push_back(entry);
            else failedKeys.push_back(entry);
        }

        // Apply placement using shared spatial semantics.
        SpatialSnapshot::ApplyPosMode(node, t, posOverride, hasPos, posMode);

        // Notify and redraw
        obj->NotifyDependents(FOREVER, PART_ALL, REFMSG_CHANGE);
        ip->RedrawViews(t);

        if (!failedKeys.empty()) {
            // The node stays (the dispatcher commits PARTIAL_APPLY): report its
            // handle so the caller fixes keys on it instead of re-creating it.
            json details = NodeIdentityJson(node);
            details["created"] = true;
            details["keys"] = failedKeys;
            details["applied"] = applied;
            if (!failedDefaults.empty()) details["defaultsNotApplied"] = failedDefaults;
            ThrowPartialApply("create_object: created " + WideToUtf8(node->GetName()) + " but " +
                              std::to_string(failedKeys.size()) + " requested parameter(s) did not apply: " +
                              failedKeys.dump(), details);
        }

        json created = SpatialSnapshot::BuildCreateObjectResult(
            node, t, type, posOverride, hasPos, posMode);
        if (created.is_object()) {
            created["applied"] = applied;
            if (!failedDefaults.empty()) {
                created["failedParams"] = failedDefaults;
                created["warnings"] = json::array({"Default parameters not applied: " + failedDefaults.dump()});
            }
        }
        return created.dump();
    });
}

// ── native:delete_objects ───────────────────────────────────────
std::string NativeHandlers::DeleteObjects(const std::string& params, MCPBridgeGUP* gup) {
    return gup->GetExecutor().ExecuteSync([&params]() -> std::string {
        json p = json::parse(params, nullptr, false);
        auto names = p.value("names", std::vector<std::string>{});
        auto handles = p.value("handles", std::vector<unsigned long long>{});
        bool dryRun = p.value("dry_run", false);
        if (names.empty() && handles.empty()) throw std::runtime_error("names or handles is required");

        Interface* ip = GetCOREInterface();
        json deleted = json::array();
        json notFound = json::array();
        std::set<INode*> seen;
        std::vector<INode*> targets;

        for (unsigned long long handle : handles) {
            INode* node = FindNodeByHandle(handle);
            if (node && seen.insert(node).second) {
                targets.push_back(node);
            } else if (!node) {
                notFound.push_back({{"handle", handle}});
            }
        }
        for (const auto& name : names) {
            std::vector<INode*> matches = CollectNodesByExactName(name);
            if (matches.empty()) {
                notFound.push_back(name);
                continue;
            }
            if (matches.size() > 1) {
                json candidates = json::array();
                for (INode* candidate : matches) {
                    candidates.push_back(NodeIdentityJson(candidate));
                }
                json hint = {
                    {"message", "Pass handles to disambiguate these object names."},
                    {"candidates", candidates},
                };
                throw std::runtime_error(StructuredErrorPayload(
                    "AMBIGUOUS",
                    "Ambiguous object name: " + name,
                    hint));
            }
            INode* node = matches[0];
            if (node && seen.insert(node).second) {
                targets.push_back(node);
            }
        }

        // Resolve and validate every selector before the first mutation. This
        // both deduplicates matching handle/name selectors and prevents an
        // ambiguous later name from leaving a partially deleted scene.
        for (INode* node : targets) {
            deleted.push_back(NodeIdentityJson(node));
            if (!dryRun) ip->DeleteNode(node);
        }

        json result;
        result[dryRun ? "wouldDelete" : "deleted"] = deleted;
        result["notFound"] = notFound;
        result["dry_run"] = dryRun;
        result["message"] = std::string(dryRun ? "Would delete " : "Deleted ") +
            std::to_string(deleted.size()) + " objects";
        if (!notFound.empty()) {
            result["message"] = result["message"].get<std::string>() +
                " | Not found: " + std::to_string(notFound.size());
        }
        return result.dump();
    });
}

// ── native:transform_object ────────────────────────────────────
std::string NativeHandlers::TransformObject(const std::string& params, MCPBridgeGUP* gup) {
    return gup->GetExecutor().ExecuteSync([&params]() -> std::string {
        json p = json::parse(params, nullptr, false);
        INode* node = ResolveNodeFromPayload(p);

        Interface* ip = GetCOREInterface();
        TimeValue t = ip->GetTime();
        std::string coordSys = p.value("coordinate_system", "world");

        bool didSomething = false;
        namespace pu = mcp_bridge::param_units;
        namespace ntx = mcp_bridge::number_text;
        json failedKeys = json::array();
        json applied = json::object();
        auto listText = [](const json& arr) {
            std::string out = "[";
            for (size_t i = 0; i < arr.size(); ++i) {
                if (i) out += ",";
                out += arr[i].is_number() ? ntx::FormatDouble(arr[i].get<double>()) : arr[i].dump();
            }
            return out + "]";
        };
        auto quatOf = [](const Matrix3& tm, double out[4]) {
            AffineParts parts;
            decomp_affine(tm, &parts);
            out[0] = parts.q.x; out[1] = parts.q.y; out[2] = parts.q.z; out[3] = parts.q.w;
        };
        auto basis3 = [](const Matrix3& m, double out[9]) {
            for (int r = 0; r < 3; ++r) {
                const Point3 row = m.GetRow(r);
                out[r * 3] = row.x; out[r * 3 + 1] = row.y; out[r * 3 + 2] = row.z;
            }
        };

        // Move — read back: the world translation must change by the offset.
        if (p.contains("move") && p["move"].type() == json::value_t::array && p["move"].size() == 3) {
            Point3 offset(p["move"][0].get<float>(), p["move"][1].get<float>(), p["move"][2].get<float>());
            const Point3 before = node->GetNodeTM(t).GetTrans();
            Matrix3 tmAxis;  // identity by default in Max 2026
            node->Move(t, tmAxis, offset, TRUE, TRUE, PIV_NONE, TRUE);
            didSomething = true;
            const Point3 delta = node->GetNodeTM(t).GetTrans() - before;
            const float dl[3] = {delta.x, delta.y, delta.z};
            const std::string got = ntx::FormatList(dl, 3);
            applied["move"] = got;
            bool ok = true;
            for (int i = 0; i < 3; ++i) {
                const double tol = 1e-4 * std::max({1.0, std::fabs(static_cast<double>(before[i])),
                                                    std::fabs(static_cast<double>(offset[i]))});
                if (std::fabs(static_cast<double>(delta[i]) - offset[i]) > tol) ok = false;
            }
            if (!ok) {
                failedKeys.push_back(PartialKey("move", listText(p["move"]), got, true,
                    "world position changed by a different offset (locked axis or position constraint/controller?)"));
            }
        }

        // Rotate
        if (p.contains("rotate") && p["rotate"].type() == json::value_t::array && p["rotate"].size() == 3) {
            float rx = DegToRad(p["rotate"][0].get<float>());
            float ry = DegToRad(p["rotate"][1].get<float>());
            float rz = DegToRad(p["rotate"][2].get<float>());

            Matrix3 tmAxis;
            if (coordSys == "local") {
                tmAxis = node->GetNodeTM(t);
                tmAxis.NoTrans();
            }

            AngAxis aax(Point3(1, 0, 0), rx);
            AngAxis aay(Point3(0, 1, 0), ry);
            AngAxis aaz(Point3(0, 0, 1), rz);

            Quat qx(aax), qy(aay), qz(aaz);
            Quat combined = qx * qy * qz;
            AngAxis finalAA(combined);

            double qBefore[4], qAfter[4];
            quatOf(node->GetNodeTM(t), qBefore);
            node->Rotate(t, tmAxis, finalAA, TRUE, TRUE, PIV_NONE, TRUE);
            didSomething = true;
            // Read back: the orientation must have turned by the requested
            // angle (axis-order independent; q and -q are the same pose).
            quatOf(node->GetNodeTM(t), qAfter);
            const double want = pu::CanonicalRotationAngle(finalAA.angle);
            const double got = pu::QuatRelativeAngle(qBefore, qAfter);
            const std::string gotText = ntx::FormatDouble(pu::StorageToUser(pu::UnitKind::Degrees, got));
            applied["rotate"] = "rotated by " + gotText + " deg";
            if (std::fabs(got - want) > 1e-3) {
                failedKeys.push_back(PartialKey("rotate", listText(p["rotate"]),
                    "rotated by " + gotText + " deg (requested " +
                    ntx::FormatDouble(pu::StorageToUser(pu::UnitKind::Degrees, want)) + " deg)", true,
                    "orientation changed by a different angle (locked axis or rotation constraint/controller?)"));
            }
        }

        // Scale
        if (p.contains("scale") && p["scale"].type() == json::value_t::array) {
            auto& sv = p["scale"];
            Point3 scaleVal;
            if (sv.size() == 1) {
                float s = sv[0].get<float>();
                scaleVal = Point3(s, s, s);
            } else if (sv.size() == 3) {
                scaleVal = Point3(sv[0].get<float>(), sv[1].get<float>(), sv[2].get<float>());
            } else {
                throw std::runtime_error("scale must be [s] or [x,y,z]");
            }
            double before3[9], after3[9];
            basis3(node->GetNodeTM(t), before3);
            Matrix3 tmAxis;
            node->Scale(t, tmAxis, scaleVal, TRUE, TRUE, PIV_NONE, TRUE);
            didSomething = true;
            // Read back the FULL basis: it must equal the old one scaled by
            // (sx,sy,sz) along world or local axes. A determinant ratio alone
            // accepted a refused [2,0.5,1] (ratio 1) and ignored sign flips.
            basis3(node->GetNodeTM(t), after3);
            const double s3[3] = {scaleVal.x, scaleVal.y, scaleVal.z};
            const pu::ScaleFrame frame = pu::AppliedScaleFrame(before3, after3, s3);
            const double detBefore = pu::Det3(before3);
            const double got = (std::fabs(detBefore) > 1e-20) ? pu::Det3(after3) / detBefore : 0.0;
            const std::string gotText = "volume x" + ntx::FormatDouble(got);
            if (frame == pu::ScaleFrame::None) {
                applied["scale"] = gotText;
                failedKeys.push_back(PartialKey("scale", listText(sv), gotText + ", axes not scaled as requested", true,
                    "node axes did not change by the requested factors (locked scale, scale controller, or a flat node?)"));
            } else {
                applied["scale"] = listText(sv) + (frame == pu::ScaleFrame::World ? " along world axes" : " along local axes");
            }
        }

        if (!failedKeys.empty()) {
            ip->RedrawViews(t);
            json details = NodeIdentityJson(node);
            details["keys"] = failedKeys;
            details["applied"] = applied;
            details["spatial"] = SpatialSnapshot::BuildSpatialSnapshot(node, t);
            ThrowPartialApply("transform_object: " + std::to_string(failedKeys.size()) +
                              " transform(s) did not apply as requested on " + WideToUtf8(node->GetName()), details);
        }

        if (!didSomething) {
            json result = NodeIdentityJson(node);
            result["status"] = "noop";
            result["message"] = "No transform parameters provided.";
            return result.dump();
        }

        ip->RedrawViews(t);

        json result = SpatialSnapshot::BuildSpatialSnapshot(node, t);
        result["message"] = "Transformed " + WideToUtf8(node->GetName());
        result["coordinateSystem"] = coordSys;
        result["applied"] = applied;
        return result.dump();
    });
}

// ── native:select_objects ──────────────────────────────────────
std::string NativeHandlers::SelectObjects(const std::string& params, MCPBridgeGUP* gup) {
    return gup->GetExecutor().ExecuteSync([&params]() -> std::string {
        json p = json::parse(params, nullptr, false);

        Interface* ip = GetCOREInterface();
        bool selectAll = p.value("all", false);
        auto names = p.value("names", std::vector<std::string>{});
        std::string pattern = p.value("pattern", "");
        std::string className = p.value("class_name", "");

        if (selectAll) {
            // Select all objects
            INode* root = ip->GetRootNode();
            std::vector<INode*> nodes;
            CollectNodes(root, nodes);
            ip->ClearNodeSelection(FALSE);
            for (INode* n : nodes) {
                ip->SelectNode(n, FALSE);
            }
            ip->RedrawViews(ip->GetTime());
            return "Selected " + std::to_string(nodes.size()) + " objects";
        }

        if (!names.empty()) {
            ip->ClearNodeSelection(FALSE);
            int found = 0;
            for (const auto& name : names) {
                INode* node = FindNodeByName(name);
                if (node) {
                    ip->SelectNode(node, FALSE);
                    found++;
                }
            }
            ip->RedrawViews(ip->GetTime());
            return "Selected " + std::to_string(found) + " of " +
                   std::to_string(names.size()) + " objects";
        }

        if (!pattern.empty() || !className.empty()) {
            INode* root = ip->GetRootNode();
            std::vector<INode*> allNodes;
            CollectNodes(root, allNodes);

            ip->ClearNodeSelection(FALSE);
            int found = 0;
            for (INode* n : allNodes) {
                bool match = false;
                if (!pattern.empty()) {
                    match = WildcardMatch(WideToUtf8(n->GetName()), pattern);
                } else {
                    match = (NodeClassName(n) == className);
                }
                if (match) {
                    ip->SelectNode(n, FALSE);
                    found++;
                }
            }
            ip->RedrawViews(ip->GetTime());

            std::string desc = !pattern.empty()
                ? ("matching \"" + pattern + "\"")
                : ("of class " + className);
            return "Selected " + std::to_string(found) + " objects " + desc;
        }

        return "At least one parameter (names, pattern, class_name, or all) must be provided.";
    });
}

// ── native:set_visibility ──────────────────────────────────────
std::string NativeHandlers::SetVisibility(const std::string& params, MCPBridgeGUP* gup) {
    return gup->GetExecutor().ExecuteSync([&params]() -> std::string {
        json p = json::parse(params, nullptr, false);
        auto names = p.value("names", std::vector<std::string>{});
        std::string pattern = p.value("pattern", "");
        std::string action = p.value("action", "hide");

        if (names.empty() && pattern.empty()) {
            throw std::runtime_error("At least one of names or pattern must be provided.");
        }

        // Collect target nodes
        std::vector<INode*> targets;
        if (!names.empty()) {
            for (const auto& name : names) {
                INode* node = FindNodeByName(name);
                if (node) targets.push_back(node);
            }
        } else {
            targets = CollectNodesByPattern(pattern);
        }

        int count = 0;
        for (INode* node : targets) {
            if (action == "hide") {
                node->Hide(TRUE);
            } else if (action == "show") {
                node->Hide(FALSE);
            } else if (action == "toggle") {
                node->Hide(!node->IsHidden());
            } else if (action == "freeze") {
                node->Freeze(TRUE);
            } else if (action == "unfreeze") {
                node->Freeze(FALSE);
            } else {
                throw std::runtime_error("Unknown action: " + action);
            }
            count++;
        }

        GetCOREInterface()->RedrawViews(GetCOREInterface()->GetTime());

        json result;
        result["action"] = action;
        result["count"] = count;
        result["message"] = action + ": " + std::to_string(count) + " objects";
        return result.dump();
    });
}

// ── native:clone_objects (Pure SDK) ─────────────────────────────
std::string NativeHandlers::CloneObjects(const std::string& params, MCPBridgeGUP* gup) {
    return gup->GetExecutor().ExecuteSync([&params]() -> std::string {
        json p = json::parse(params, nullptr, false);
        auto names = p.value("names", std::vector<std::string>{});
        std::string mode = p.value("mode", "copy");
        auto offsetVec = p.value("offset", std::vector<float>{0.0f, 0.0f, 0.0f});

        if (names.empty()) throw std::runtime_error("names is required");

        Interface* ip = GetCOREInterface();

        // Build INodeTab of source nodes
        INodeTab srcNodes;
        json notFound = json::array();
        for (const auto& name : names) {
            INode* node = FindNodeByName(name);
            if (node) {
                srcNodes.AppendNode(node);
            } else {
                notFound.push_back(name);
            }
        }

        if (srcNodes.Count() == 0) {
            throw std::runtime_error("No valid objects found to clone");
        }

        // Determine clone type
        CloneType ct = NODE_COPY;
        if (mode == "instance") ct = NODE_INSTANCE;
        else if (mode == "reference") ct = NODE_REFERENCE;

        // Clone
        Point3 offset(
            offsetVec.size() > 0 ? offsetVec[0] : 0.0f,
            offsetVec.size() > 1 ? offsetVec[1] : 0.0f,
            offsetVec.size() > 2 ? offsetVec[2] : 0.0f
        );
        INodeTab resultSource, resultTarget;
        bool ok = ip->CloneNodes(srcNodes, offset, true, ct, &resultSource, &resultTarget);

        if (!ok) {
            throw std::runtime_error("CloneNodes failed");
        }

        // Build result
        json cloneNames = json::array();
        for (int i = 0; i < resultTarget.Count(); i++) {
            cloneNames.push_back(WideToUtf8(resultTarget[i]->GetName()));
        }

        ip->RedrawViews(ip->GetTime());

        json nodes = json::array();
        const TimeValue t = ip->GetTime();
        for (int i = 0; i < resultTarget.Count(); i++) {
            nodes.push_back(SpatialSnapshot::BuildSpatialSnapshot(resultTarget[i], t));
        }

        json result;
        result["cloned"] = cloneNames;
        result["notFound"] = notFound;
        result["nodes"] = nodes;
        result["space"] = SpatialSnapshot::SpaceJson();
        return result.dump();
    });
}
