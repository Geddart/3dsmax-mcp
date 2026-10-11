#pragma once
#include <string>
#include <vector>
#include <algorithm>
#include <stdexcept>
#include <nlohmann/json.hpp>
#include <max.h>
#include <maxapi.h>
#include <inode.h>
#include <object.h>
#include <modstack.h>
#include <ilayer.h>
#include <ILayerProperties.h>
#include <INodeLayerProperties.h>
#include <iparamb2.h>
#include <plugapi.h>
#include <ISceneEventManager.h>

#include <maxscript/maxscript.h>
#include <maxscript/foundation/strings.h>
#include <maxscript/maxwrapper/mxsobjects.h>
#include <CoreFunctions.h>
#include "mcp_bridge/number_text.h"
#include "mcp_bridge/param_units.h"

class MCPBridgeGUP;

namespace HandlerHelpers {

namespace nt = mcp_bridge::number_text;

using json = nlohmann::json;

// ── UTF-8 <-> Wide conversion ───────────────────────────────────
inline std::string WideToUtf8(const wchar_t* w) {
    if (!w || !*w) return {};
    int len = WideCharToMultiByte(CP_UTF8, 0, w, -1, nullptr, 0, nullptr, nullptr);
    std::string s(len - 1, 0);
    WideCharToMultiByte(CP_UTF8, 0, w, -1, &s[0], len, nullptr, nullptr);
    return s;
}

inline std::wstring Utf8ToWide(const std::string& s) {
    if (s.empty()) return {};
    int len = MultiByteToWideChar(CP_UTF8, 0, s.c_str(), (int)s.size(), nullptr, 0);
    std::wstring w(len, 0);
    MultiByteToWideChar(CP_UTF8, 0, s.c_str(), (int)s.size(), &w[0], len);
    return w;
}

// MAXScript's `(classOf value) as string` exposes the script-facing class
// token, not the localized UI label returned by Animatable::ClassName().
inline std::string ScriptClassName(ClassDesc* descriptor) {
    if (!descriptor) return {};

    const MCHAR* internalName = descriptor->InternalName();
    if (internalName && *internalName) {
        return WideToUtf8(internalName);
    }

    const MCHAR* nonLocalizedName = descriptor->NonLocalizedClassName();
    if (nonLocalizedName && *nonLocalizedName) {
        return WideToUtf8(nonLocalizedName);
    }

    const MCHAR* className = descriptor->ClassName();
    return className ? WideToUtf8(className) : std::string();
}

inline std::string ScriptClassName(Animatable* value) {
    if (!value) return {};

    ClassDesc* descriptor = DllDir::GetInstance().ClassDir().FindClass(
        value->SuperClassID(), value->ClassID());
    const std::string scriptName = ScriptClassName(descriptor);
    if (!scriptName.empty()) {
        return scriptName;
    }
    return WideToUtf8(value->ClassName().data());
}

// The script-visible MAXClass name can differ from ClassDesc::InternalName()
// (OpenPBR_Material vs OpenPBR, for example). This is still native C++ metadata:
// it does not evaluate MAXScript. Call only from handlers marshalled to Max's
// main thread because the MAXScript class registry is not thread-safe.
inline std::string MaxScriptVisibleClassName(
    SClass_ID superClassId,
    const Class_ID& classId) {
    ScopedMaxScriptEvaluationContext evaluationContext;
    Class_ID lookupId = classId;
    MAXClass* maxClass = MAXClass::lookup_class(
        &lookupId,
        superClassId,
        true);
    if (maxClass && maxClass->name) {
        const MCHAR* value = maxClass->name->to_string();
        if (value && *value) {
            return WideToUtf8(value);
        }
    }
    ClassDesc* descriptor = DllDir::GetInstance().ClassDir().FindClass(
        superClassId,
        classId);
    return ScriptClassName(descriptor);
}

inline std::string MaxScriptVisibleClassName(Animatable* value) {
    if (!value) return {};
    return MaxScriptVisibleClassName(
        value->SuperClassID(),
        value->ClassID());
}

// ── Node property helpers ───────────────────────────────────────
inline std::string NodeClassName(INode* node) {
    ObjectState os = node->EvalWorldState(GetCOREInterface()->GetTime());
    if (os.obj) {
        return WideToUtf8(os.obj->ClassName().data());
    }
    return "Unknown";
}

inline std::string NodeLayerName(INode* node) {
    INodeLayerProperties* nlp = static_cast<INodeLayerProperties*>(
        node->GetInterface(NODELAYERPROPERTIES_INTERFACE));
    if (nlp) {
        ILayerProperties* lp = nlp->getLayer();
        if (lp) {
            const MCHAR* name = lp->getName();
            if (name) return WideToUtf8(name);
        }
    }
    return "0";
}

inline unsigned long long NodeHandle(INode* node) {
    if (!node) return 0ULL;
    return static_cast<unsigned long long>(Animatable::GetHandleByAnim(node));
}

inline json NodeIdentityJson(INode* node) {
    json out;
    if (!node) return out;
    out["name"] = WideToUtf8(node->GetName());
    out["handle"] = NodeHandle(node);
    out["class"] = NodeClassName(node);
    out["layer"] = NodeLayerName(node);
    return out;
}

inline json NodePosition(INode* node, TimeValue t) {
    Matrix3 tm = node->GetNodeTM(t);
    Point3 pos = tm.GetTrans();
    return json::array({pos.x, pos.y, pos.z});
}

inline json NodeWireColor(INode* node) {
    DWORD c = node->GetWireColor();
    return json::array({GetRValue(c), GetGValue(c), GetBValue(c)});
}

// ── Scene traversal ─────────────────────────────────────────────
inline void CollectNodes(INode* node, std::vector<INode*>& out) {
    for (int i = 0; i < node->NumberOfChildren(); i++) {
        INode* child = node->GetChildNode(i);
        out.push_back(child);
        CollectNodes(child, out);
    }
}

inline std::vector<INode*> CollectNodesByExactName(const std::string& name) {
    Interface* ip = GetCOREInterface();
    INode* root = ip->GetRootNode();
    std::vector<INode*> all, matched;
    CollectNodes(root, all);
    for (INode* n : all) {
        if (WideToUtf8(n->GetName()) == name) {
            matched.push_back(n);
        }
    }
    return matched;
}

// ── Node lookup by name ─────────────────────────────────────────
inline INode* FindNodeByName(const std::string& name) {
    Interface* ip = GetCOREInterface();
    std::wstring wname = Utf8ToWide(name);
    return ip->GetINodeByName(wname.c_str());
}

inline unsigned long long PayloadHandleValue(const json& payload, const std::string& key = "handle") {
    auto it = payload.find(key);
    if (it == payload.end() || it->is_null()) return 0ULL;
    try {
        if (it->is_number_unsigned()) return it->get<unsigned long long>();
        if (it->is_number_integer()) {
            long long value = it->get<long long>();
            return value > 0 ? static_cast<unsigned long long>(value) : 0ULL;
        }
        // type() check instead of is_string(): MAXScript's value.h defines a
        // function-like is_string macro that breaks the method call when this
        // header lands after maxscript includes.
        if (it->type() == json::value_t::string) {
            std::string value = it->get<std::string>();
            if (!value.empty()) return std::stoull(value);
        }
    } catch (...) {
        return 0ULL;
    }
    return 0ULL;
}

inline INode* FindNodeByHandle(unsigned long long handle) {
    if (handle == 0ULL) return nullptr;
    return NodeEventNamespace::GetNodeByKey(static_cast<NodeEventNamespace::NodeKey>(handle));
}

inline std::string StructuredErrorPayload(
    const std::string& code,
    const std::string& message,
    const json& hint = json(),
    const json& details = json()) {
    json payload;
    payload["type"] = "NativeError";
    payload["message"] = message;
    payload["code"] = code;
    payload["retryable"] = (
        code == "BRIDGE_DOWN" || code == "RENDER_BUSY" ||
        code == "SCENE_CONFLICT" || code == "TRANSACTION_BUSY");
    if (!hint.is_null() && !hint.empty()) {
        payload["hint"] = hint;
    }
    if (!details.is_null() && !details.empty()) {
        payload["details"] = details;
    }
    return payload.dump();
}

// ── PARTIAL_APPLY: fail loud when a requested key did not stick ──
// The dispatcher ACCEPTS the undo transaction for this code (instead of
// cancelling it), so whatever was created stays in the scene and its handle in
// `details` is valid. Callers must never retry: re-running a create would
// duplicate the object.
inline const char* PartialApplyCode() { return "PARTIAL_APPLY"; }

inline bool IsPartialApplyError(const std::string& message) {
    json payload = json::parse(message, nullptr, false);
    return !payload.is_discarded() && payload.is_object() &&
           payload.value("code", "") == PartialApplyCode();
}

// One entry of details.keys. `applied` is the read-back value in user units,
// or JSON null when nothing was written.
inline json PartialKey(const std::string& key, const std::string& requested,
                       const std::string& applied, bool hasApplied, const std::string& reason) {
    json k;
    k["key"] = key;
    k["requested"] = requested;
    k["applied"] = hasApplied ? json(applied) : json(nullptr);
    k["reason"] = reason;
    return k;
}

[[noreturn]] inline void ThrowPartialApply(const std::string& message, json details) {
    if (!details.is_object()) details = json::object();
    details["retry"] = false;
    json hint = {
        {"message", "Some requested values did not apply. Do NOT re-run the call: anything it created "
                    "already exists (see details.handle). Fix only the listed keys on that handle."},
    };
    throw std::runtime_error(StructuredErrorPayload(PartialApplyCode(), message, hint, details));
}

inline INode* ResolveNodeFromPayload(
    const json& payload,
    const std::string& nameKey = "name",
    const std::string& handleKey = "handle") {

    const unsigned long long handle = PayloadHandleValue(payload, handleKey);
    if (handle != 0ULL) {
        INode* byHandle = FindNodeByHandle(handle);
        if (!byHandle) {
            throw std::runtime_error("Object handle not found: " + std::to_string(handle));
        }
        return byHandle;
    }

    const std::string name = payload.value(nameKey, "");
    if (name.empty()) {
        throw std::runtime_error(nameKey + " or " + handleKey + " is required");
    }

    std::vector<INode*> matches = CollectNodesByExactName(name);
    if (matches.empty()) {
        throw std::runtime_error("Object not found: " + name);
    }
    if (matches.size() > 1) {
        json candidates = json::array();
        for (INode* node : matches) {
            candidates.push_back(NodeIdentityJson(node));
        }
        json hint = {
            {"message", "Pass handle to disambiguate this object name."},
            {"candidates", candidates},
        };
        throw std::runtime_error(StructuredErrorPayload(
            "AMBIGUOUS",
            "Ambiguous object name: " + name,
            hint));
    }
    return matches[0];
}

// MAXScript-level wrap that captures runtime exceptions (parse errors still
// surface via ExecuteMAXScriptScript returning FALSE). The wrapped script
// returns either the user's value, or a string with this sentinel prefix.
inline const char* MaxScriptErrorSentinel() { return "__MCP_MS_ERR__:"; }

inline std::wstring WrapForErrorCapture(const std::wstring& wcmd) {
    return std::wstring(
        L"(\n"
        L"  local __mcp_err = undefined\n"
        L"  local __mcp_res = try (\n"
    ) + wcmd + std::wstring(
        L"\n  ) catch (__mcp_err = getCurrentException(); undefined)\n"
        L"  if __mcp_err != undefined then (\"__MCP_MS_ERR__:\" + __mcp_err) else __mcp_res\n"
        L")\n"
    );
}

// ── MAXScript execution (for hybrid handlers) ───────────────────
inline std::string RunMAXScript(const std::string& script) {
    std::wstring wcmd = WrapForErrorCapture(Utf8ToWide(script));
    FPValue fpv;
    BOOL ok = FALSE;

    try {
        ok = ExecuteMAXScriptScript(
            wcmd.c_str(),
            MAXScript::ScriptSource::NonEmbedded,
            FALSE,   // quietErrors
            &fpv,    // result
            TRUE     // logQuietErrors
        );
    } catch (...) {
        throw std::runtime_error("MAXScript execution exception");
    }

    if (!ok) {
        throw std::runtime_error("MAXScript execution failed");
    }

    // Convert FPValue to string
    if (fpv.type == TYPE_STRING || fpv.type == TYPE_FILENAME) {
        return WideToUtf8(fpv.s);
    }
    if (fpv.type == TYPE_TSTR) {
        return WideToUtf8(fpv.tstr->data());
    }
    if (fpv.type == TYPE_VALUE && fpv.v != nullptr) {
        try {
            const MCHAR* str = fpv.v->to_string();
            return WideToUtf8(str);
        } catch (...) {}
    }
    if (fpv.type == TYPE_INT) {
        return std::to_string(fpv.i);
    }
    if (fpv.type == TYPE_FLOAT) {
        return nt::FormatFloat(fpv.f);  // never std::to_string: locale decimal comma
    }
    if (fpv.type == TYPE_BOOL) {
        return fpv.i ? "true" : "false";
    }

    // Never re-evaluate the script to stringify the result: scripts with side
    // effects (e.g. "max undo") would run twice.
    return "OK";
}

// A bare MAXScript identifier (property name) — the only shape we splice into
// fallback scripts, so a caller-supplied name can never inject code.
inline bool IsPlainIdentifier(const std::string& s) {
    if (s.empty() || s.size() > 128) return false;
    const unsigned char c0 = static_cast<unsigned char>(s[0]);
    if (!(std::isalpha(c0) || c0 == '_')) return false;
    for (unsigned char c : s) {
        if (!(std::isalnum(c) || c == '_')) return false;
    }
    return true;
}

// A dotted property path of plain identifiers with optional [n] indices
// ("diffuseMap.coords.U_Tiling", "materialList[2].diffuse"). Still never
// code: no spaces, operators, quotes or calls.
inline bool IsPropertyPath(const std::string& s) {
    if (s.empty() || s.size() > 256) return false;
    size_t i = 0;
    while (true) {
        size_t start = i;
        while (i < s.size() && s[i] != '.' && s[i] != '[') ++i;
        if (!IsPlainIdentifier(s.substr(start, i - start))) return false;
        while (i < s.size() && s[i] == '[') {
            size_t close = s.find(']', i);
            if (close == std::string::npos || close == i + 1) return false;
            for (size_t k = i + 1; k < close; ++k) {
                if (!std::isdigit(static_cast<unsigned char>(s[k]))) return false;
            }
            i = close + 1;
        }
        if (i >= s.size()) return true;
        if (s[i] != '.') return false;
        ++i;
    }
}

// ── Outcome of one property write, verified by reading it back ──
enum class SetStatus {
    NotHandled,  // this path could not write it (unknown name, unparseable text) — try the next path
    Applied,     // written and the read-back matches the request
    Mismatch,    // written, but the read-back differs (clamped, truncated, ignored) — do NOT retry elsewhere
};

struct SetOutcome {
    SetStatus status = SetStatus::NotHandled;
    std::string applied;      // read-back value in user units (degrees, 0-100, (color 0-255))
    bool hasApplied = false;  // false: nothing was written, or the value could not be read back
    std::string reason;       // why it is NotHandled / Mismatch
    bool ok() const { return status == SetStatus::Applied; }
};

inline SetOutcome NotHandled(const std::string& reason) {
    SetOutcome o;
    o.status = SetStatus::NotHandled;
    o.reason = reason;
    return o;
}

// Assign `target.prop = (value)` through MAXScript, for parameters the
// IParamBlock2 path cannot reach (PB1 modifiers such as Extrude, shader
// sub-blocks, values with units or expressions). `targetExpr` must be built by
// the bridge itself (handles/indices), never from caller text; `prop` must be
// a plain identifier or, with allowPath, a dotted identifier path.
//
// The value is evaluated once, assigned, and read back in the SAME script:
// numbers compare with a 1e-5 relative tolerance, Point3/Point4/Color per
// component, numbers vs booleans by truthiness, strings vs names by text,
// everything else with ==. MAXScript speaks user units (degrees, 0-100), so
// the comparison needs no conversion.
inline SetOutcome TrySetViaMaxScript(const std::string& targetExpr, const std::string& prop,
                                     const std::string& value, bool allowPath = false) {
    if (allowPath ? !IsPropertyPath(prop) : !IsPlainIdentifier(prop)) {
        return NotHandled("invalid property name");
    }
    if (value.empty()) return NotHandled("empty value");
    static const char* kOk = "__MCP_SET_OK__:";
    static const char* kMismatch = "__MCP_SET_MISMATCH__:";
    static const char* kUnreadable = "__MCP_SET_UNREADABLE__";
    const std::string ms =
        "(\n"
        "local __mcp_t = " + targetExpr + "\n"
        "local __mcp_w = (" + value + ")\n"
        "__mcp_t." + prop + " = __mcp_w\n"
        "local __mcp_r = true\n"
        "local __mcp_g = try (__mcp_t." + prop + ") catch (__mcp_r = false; undefined)\n"
        "if not __mcp_r then \"" + std::string(kUnreadable) + "\" else (\n"
        // Numbers never go through ==: MAXScript's Integer == Float converts the
        // float to an integer, so `12 == 12.5` is true (a truncation looks applied).
        "local __mcp_num = (isKindOf __mcp_w Number) and (isKindOf __mcp_g Number)\n"
        "local __mcp_ok = if __mcp_num then "
        "(abs ((__mcp_g as float) - (__mcp_w as float))) <= 1e-5 * (amax 1.0 (abs (__mcp_w as float))) "
        "else (__mcp_w == __mcp_g)\n"
        "local __mcp_vec = #(Point3, Point4, Color)\n"
        "if not __mcp_ok and not __mcp_num then (\n"
        "  if (isKindOf __mcp_w Number) and (isKindOf __mcp_g BooleanClass) then\n"
        "    __mcp_ok = ((__mcp_w != 0) == __mcp_g)\n"
        "  else if (isKindOf __mcp_w BooleanClass) and (isKindOf __mcp_g Number) then\n"
        "    __mcp_ok = ((__mcp_g != 0) == __mcp_w)\n"
        "  else if (findItem __mcp_vec (classOf __mcp_w)) > 0 and (findItem __mcp_vec (classOf __mcp_g)) > 0 then (\n"
        // if/else, not `case classOf v of (Color: ... Point4: ...)`: that form
        // failed to parse here (Max 2025) while the equivalent chain is fine.
        "    local __mcp_c = for __mcp_v in #(__mcp_w, __mcp_g) collect (\n"
        "      if (classOf __mcp_v) == Color then #(__mcp_v.r, __mcp_v.g, __mcp_v.b)\n"
        "      else if (classOf __mcp_v) == Point4 then #(__mcp_v.x, __mcp_v.y, __mcp_v.z, __mcp_v.w)\n"
        "      else #(__mcp_v.x, __mcp_v.y, __mcp_v.z))\n"
        "    local __mcp_n = amin __mcp_c[1].count __mcp_c[2].count\n"
        "    __mcp_ok = true\n"
        "    for __mcp_i = 1 to __mcp_n do (\n"
        "      local __mcp_a = __mcp_c[1][__mcp_i]\n"
        "      if (abs (__mcp_c[2][__mcp_i] - __mcp_a)) > 1e-5 * (amax 1.0 (abs __mcp_a)) do __mcp_ok = false)\n"
        "  )\n"
        "  else if ((isKindOf __mcp_w String) or (isKindOf __mcp_w Name)) and "
        "((isKindOf __mcp_g String) or (isKindOf __mcp_g Name)) then\n"
        "    __mcp_ok = ((__mcp_w as string) == (__mcp_g as string))\n"
        ")\n"
        "(if __mcp_ok then \"" + std::string(kOk) + "\" else \"" + std::string(kMismatch) +
        "\") + (__mcp_g as string)\n"
        "))";
    std::string out;
    try {
        out = RunMAXScript(ms);
    } catch (const std::exception& e) {
        return NotHandled(std::string("MAXScript: ") + e.what());
    }
    SetOutcome o;
    const std::string okPrefix(kOk);
    if (out.rfind(okPrefix, 0) == 0) {
        o.status = SetStatus::Applied;
        o.applied = out.substr(okPrefix.size());
        o.hasApplied = true;
        return o;
    }
    const std::string mismatch(kMismatch);
    if (out.rfind(mismatch, 0) == 0) {
        o.status = SetStatus::Mismatch;
        o.applied = out.substr(mismatch.size());
        o.hasApplied = true;
        o.reason = "read-back differs from the requested value";
        return o;
    }
    if (out == kUnreadable) {
        // The assignment ran but cannot be confirmed: report it, never claim success.
        o.status = SetStatus::Mismatch;
        o.reason = "assigned, but the property cannot be read back to verify it";
        return o;
    }
    const std::string err(MaxScriptErrorSentinel());
    if (out.rfind(err, 0) == 0) {
        std::string msg = out.substr(err.size());
        while (!msg.empty() && (msg.back() == '\n' || msg.back() == '\r' || msg.back() == ' ')) msg.pop_back();
        return NotHandled("MAXScript: " + msg);
    }
    return NotHandled("MAXScript returned " + out);
}

// ── JSON escape utility ─────────────────────────────────────────
inline std::string JsonEscape(const std::string& s) {
    std::string out;
    out.reserve(s.size() + 8);
    for (char c : s) {
        switch (c) {
            case '"':  out += "\\\""; break;
            case '\\': out += "\\\\"; break;
            case '\n': out += "\\n";  break;
            case '\r': out += "\\r";  break;
            case '\t': out += "\\t";  break;
            default:   out += c;      break;
        }
    }
    return out;
}

// ── Wildcard pattern matching (case-insensitive) ────────────────
// Supports: * at start, end, both, or standalone. Exact match otherwise.
inline bool WildcardMatch(const std::string& name, const std::string& pattern) {
    if (pattern == "*") return true;
    // Case-insensitive copies
    std::string lname = name, lpat = pattern;
    std::transform(lname.begin(), lname.end(), lname.begin(), ::tolower);
    std::transform(lpat.begin(), lpat.end(), lpat.begin(), ::tolower);

    bool startsWild = !lpat.empty() && lpat.front() == '*';
    bool endsWild = !lpat.empty() && lpat.back() == '*';

    if (startsWild && endsWild) {
        std::string sub = lpat.substr(1, lpat.size() - 2);
        return lname.find(sub) != std::string::npos;
    }
    if (startsWild) {
        std::string suffix = lpat.substr(1);
        return lname.size() >= suffix.size() &&
               lname.compare(lname.size() - suffix.size(), suffix.size(), suffix) == 0;
    }
    if (endsWild) {
        std::string prefix = lpat.substr(0, lpat.size() - 1);
        return lname.compare(0, prefix.size(), prefix) == 0;
    }
    return lname == lpat;
}

// ── Collect nodes matching a wildcard pattern ───────────────────
inline std::vector<INode*> CollectNodesByPattern(const std::string& pattern) {
    Interface* ip = GetCOREInterface();
    INode* root = ip->GetRootNode();
    std::vector<INode*> all, matched;
    CollectNodes(root, all);
    for (INode* n : all) {
        if (WildcardMatch(WideToUtf8(n->GetName()), pattern))
            matched.push_back(n);
    }
    return matched;
}

// ── Normalize sub-anim path for execute() ───────────────────────
// Replaces [#Object (ClassName)] with .baseObject — parentheses in
// class names break MAXScript's execute() parser.
inline std::string NormalizeSubAnimPath(const std::string& path) {
    std::string result = path;

    // Ensure [name] tokens have # prefix → [#name] (needed by MAXScript execute())
    // Handles paths from get_wired_params which may omit the # prefix
    std::string fixed;
    for (size_t i = 0; i < result.size(); i++) {
        if (result[i] == '[' && (i + 1 < result.size()) && result[i + 1] != '#') {
            fixed += "[#";
        } else {
            fixed += result[i];
        }
    }
    result = fixed;

    // Replace [#Object (anything)] with .baseObject — parentheses break execute()
    auto pos = result.find("[#Object (");
    if (pos != std::string::npos) {
        auto end = result.find(")]", pos);
        if (end != std::string::npos) {
            result = result.substr(0, pos) + ".baseObject" + result.substr(end + 2);
        }
    }
    // Also handle without # (legacy): [Object (anything)]
    pos = result.find("[Object (");
    if (pos != std::string::npos) {
        auto end = result.find(")]", pos);
        if (end != std::string::npos) {
            result = result.substr(0, pos) + ".baseObject" + result.substr(end + 2);
        }
    }

    // Strip [#Parameters] — track view grouping node, not addressable in MAXScript
    std::string paramToken = "[#Parameters]";
    pos = result.find(paramToken);
    while (pos != std::string::npos) {
        result.erase(pos, paramToken.length());
        pos = result.find(paramToken);
    }
    return result;
}

// ── Walk sub-anim path to resolve a track from a node ───────────
// Path format: "[#Transform][#Position][#Z Position]" or "[#transform][#position][#z_position]"
// Returns the Animatable* at that path, or nullptr if not found.
inline Animatable* ResolveSubAnimPath(INode* node, const std::string& path) {
    if (!node) return nullptr;
    Animatable* current = node;

    // Parse [#name] tokens from the path
    std::vector<std::string> tokens;
    size_t i = 0;
    while (i < path.size()) {
        auto open = path.find("[#", i);
        if (open == std::string::npos) {
            // Also try [  without #
            open = path.find('[', i);
            if (open == std::string::npos) break;
            auto close = path.find(']', open);
            if (close == std::string::npos) break;
            std::string tok = path.substr(open + 1, close - open - 1);
            if (!tok.empty() && tok != "Parameters") tokens.push_back(tok);
            i = close + 1;
        } else {
            auto close = path.find(']', open);
            if (close == std::string::npos) break;
            std::string tok = path.substr(open + 2, close - open - 2);
            if (!tok.empty() && tok != "Parameters") tokens.push_back(tok);
            i = close + 1;
        }
    }

    // Walk sub-anims matching by name (case-insensitive)
    for (const auto& tok : tokens) {
        bool found = false;
        int numSubs = current->NumSubs();
        for (int s = 0; s < numSubs; s++) {
            Animatable* sub = current->SubAnim(s);
            if (!sub) continue;
            MSTR subName = current->SubAnimName(s, false);
            std::string sname = WideToUtf8(subName.data());
            // Case-insensitive compare, also handle underscore vs space
            std::string lTok = tok, lName = sname;
            std::transform(lTok.begin(), lTok.end(), lTok.begin(), ::tolower);
            std::transform(lName.begin(), lName.end(), lName.begin(), ::tolower);
            // Replace spaces with underscores for comparison
            std::replace(lTok.begin(), lTok.end(), ' ', '_');
            std::replace(lName.begin(), lName.end(), ' ', '_');
            if (lTok == lName) {
                current = sub;
                found = true;
                break;
            }
        }
        if (!found) return nullptr;
    }
    return current;
}

// ── Find ClassDesc by class name (iterates all loaded plugins) ──
inline ClassDesc* FindClassDescByName(const std::string& className, SClass_ID superID = 0) {
    std::wstring wname = Utf8ToWide(className);
    auto& dir = DllDir::GetInstance();
    int numDlls = dir.Count();
    for (int d = 0; d < numDlls; d++) {
        const DllDesc& dll = dir[d];
        int numClasses = dll.NumberOfClasses();
        for (int c = 0; c < numClasses; c++) {
            ClassDesc* cd = dll[c];
            if (!cd) continue;
            if (superID != 0 && cd->SuperClassID() != superID) continue;
            const MCHAR* cn = cd->ClassName();
            if (cn && _wcsicmp(cn, wname.c_str()) == 0)
                return cd;
            // Also try internal name (some plugins differ)
            const MCHAR* intName = cd->InternalName();
            if (intName && _wcsicmp(intName, wname.c_str()) == 0)
                return cd;
        }
    }
    return nullptr;
}

// ── ParamBlock2 user units ──────────────────────────────────────
// MAXScript (and every bridge caller) speaks degrees for TYPE_ANGLE and 0-100
// for TYPE_PCNT_FRAC; the block stores radians and 0-1. Writers convert user
// text to storage, every reader converts back, so the bridge and MAXScript
// agree on every value.
inline mcp_bridge::param_units::UnitKind PB2UnitKind(int baseType) {
    using mcp_bridge::param_units::UnitKind;
    if (baseType == TYPE_ANGLE) return UnitKind::Degrees;
    if (baseType == TYPE_PCNT_FRAC) return UnitKind::Percent;
    return UnitKind::None;
}

// "degrees" / "percent", or "" for every other parameter type.
inline const char* PB2UnitLabel(ParamType2 ptype) {
    return mcp_bridge::param_units::UnitLabel(PB2UnitKind(ptype & ~TYPE_TAB));
}

// A stored float as user-unit text ('.' decimal point, never the locale's).
inline std::string FormatPB2Float(ParamType2 ptype, float stored) {
    const auto kind = PB2UnitKind(ptype & ~TYPE_TAB);
    if (kind == mcp_bridge::param_units::UnitKind::None) return nt::FormatFloat(stored);
    return nt::FormatFloat(static_cast<float>(mcp_bridge::param_units::StorageToUser(kind, stored)));
}

inline std::string FormatPoint4List(const Point4& p) {
    const float v[4] = {p.x, p.y, p.z, p.w};
    return nt::FormatList(v, 4);
}

inline std::string FormatMaxColor4(const Point4& p) {
    return "(color " + nt::FormatFloat(p.x * 255.0f) + " " + nt::FormatFloat(p.y * 255.0f) + " " +
           nt::FormatFloat(p.z * 255.0f) + " " + nt::FormatFloat(p.w * 255.0f) + ")";
}

// ── Parse a MAXScript-style value string into a typed PB2 value ─
// Writes the value, reads the same parameter back and compares in storage
// units (ints/bools/strings exactly, floats with a 1e-5 relative tolerance,
// Point3/Point4/colours per component).
//   NotHandled — the text is not a plain literal for this type (units,
//                expressions, "4,5", texmap references) or SetValue refused it:
//                the caller falls back to MAXScript, which evaluates it exactly.
//   Mismatch   — the block holds something else after the write: report it,
//                never fall back (a second writer would only hide the problem).
inline SetOutcome SetPB2ParamFromString(IParamBlock2* pb, ParamID pid, ParamType2 ptype,
                                        const std::string& valStr, TimeValue t) {
    namespace pu = mcp_bridge::param_units;
    // Every numeric parse is locale-independent and must consume the whole
    // string. Never store a partially parsed value: Max's CRT locale follows
    // the Windows region, and a German locale turns std::stof("4.5") into 4.
    const int baseType = ptype & ~TYPE_TAB;
    SetOutcome o;
    auto finish = [&o](bool match, const std::string& applied) -> SetOutcome {
        o.status = match ? SetStatus::Applied : SetStatus::Mismatch;
        o.applied = applied;
        o.hasApplied = true;
        if (!match) o.reason = "read-back differs from the requested value";
        return o;
    };
    static const char* kRefused = "ParamBlock2 SetValue refused the value";

    switch (baseType) {
    case TYPE_FLOAT:
    case TYPE_ANGLE:
    case TYPE_PCNT_FRAC:
    case TYPE_WORLD:
    case TYPE_COLOR_CHANNEL: {
        double user = 0.0;
        if (!nt::ParseDouble(valStr, user)) return NotHandled("not a plain number");
        const float want = static_cast<float>(pu::UserToStorage(PB2UnitKind(baseType), user));
        if (!pb->SetValue(pid, t, want)) return NotHandled(kRefused);
        float got = 0.0f;
        pb->GetValue(pid, t, got, FOREVER);
        return finish(pu::FloatsMatch(want, got), FormatPB2Float(ptype, got));
    }
    case TYPE_INT:
    case TYPE_BOOL:
    case TYPE_TIMEVALUE:
    case TYPE_RADIOBTN_INDEX:
    case TYPE_INDEX: {
        int want = 0;
        if (valStr == "true" || valStr == "on") want = 1;
        else if (valStr == "false" || valStr == "off") want = 0;
        else if (!nt::ParseInt(valStr, want)) return NotHandled("not a plain integer");
        if (!pb->SetValue(pid, t, want)) return NotHandled(kRefused);
        int got = 0;
        pb->GetValue(pid, t, got, FOREVER);
        if (baseType == TYPE_BOOL) {
            return finish((want != 0) == (got != 0), got ? "true" : "false");
        }
        return finish(want == got, std::to_string(got));
    }
    case TYPE_POINT3:
    case TYPE_RGBA: {
        // "(color r g b)" is MAXScript colour syntax with 0-255 components;
        // TYPE_RGBA stores a Color with 0-1 components, so scale it down.
        // "[x,y,z]" is passed through unchanged (already in storage units).
        double v[4] = {0, 0, 0, 0};
        int n = 0;
        bool colorSyntax = false;
        if (nt::ParseMaxColor(valStr, v, n)) {
            colorSyntax = true;
            if (baseType == TYPE_RGBA) {
                for (int i = 0; i < 3; ++i) v[i] /= 255.0;
            }
        } else if (!nt::ParseDoubleList(valStr, v, 3)) {
            return NotHandled("not a plain [x,y,z] or (color r g b)");
        }
        const Point3 want(static_cast<float>(v[0]), static_cast<float>(v[1]), static_cast<float>(v[2]));
        if (!pb->SetValue(pid, t, want)) return NotHandled(kRefused);
        Point3 got(0.0f, 0.0f, 0.0f);
        pb->GetValue(pid, t, got, FOREVER);
        const double w[3] = {want.x, want.y, want.z};
        const double g[3] = {got.x, got.y, got.z};
        const float gl[3] = {got.x, got.y, got.z};
        const std::string applied = (baseType == TYPE_RGBA && colorSyntax)
            ? nt::FormatMaxColor(got.x, got.y, got.z, true)
            : nt::FormatList(gl, 3);
        return finish(pu::ComponentsMatch(w, g, 3), applied);
    }
    case TYPE_POINT4:
    case TYPE_FRGBA: {
        double v[4] = {0, 0, 0, 1};
        int n = 0;
        bool colorSyntax = false;
        if (nt::ParseMaxColor(valStr, v, n)) {
            colorSyntax = true;
            const double k = (baseType == TYPE_FRGBA) ? (1.0 / 255.0) : 1.0;
            for (int i = 0; i < 3; ++i) v[i] *= k;
            v[3] = (n == 4) ? v[3] * k : 1.0;
        } else if (!nt::ParseDoubleList(valStr, v, 4)) {
            v[3] = 1.0;
            if (!nt::ParseDoubleList(valStr, v, 3)) return NotHandled("not a plain [x,y,z,w] or (color r g b a)");
        }
        const Point4 want(static_cast<float>(v[0]), static_cast<float>(v[1]), static_cast<float>(v[2]), static_cast<float>(v[3]));
        if (!pb->SetValue(pid, t, want)) return NotHandled(kRefused);
        Point4 got(0.0f, 0.0f, 0.0f, 0.0f);
        pb->GetValue(pid, t, got, FOREVER);
        const double w[4] = {want.x, want.y, want.z, want.w};
        const double g[4] = {got.x, got.y, got.z, got.w};
        const std::string applied = (baseType == TYPE_FRGBA && colorSyntax) ? FormatMaxColor4(got) : FormatPoint4List(got);
        return finish(pu::ComponentsMatch(w, g, 4), applied);
    }
    case TYPE_TEXMAP: {
        // "undefined" / "null" / "none" clears the slot; a map reference is a
        // MAXScript expression and is evaluated by the fallback.
        std::string lower = valStr;
        std::transform(lower.begin(), lower.end(), lower.begin(), ::tolower);
        if (lower != "undefined" && lower != "null" && lower != "none") return NotHandled("texture map reference");
        if (!pb->SetValue(pid, t, (Texmap*)nullptr)) return NotHandled(kRefused);
        Texmap* got = nullptr;
        pb->GetValue(pid, t, got, FOREVER);
        return finish(got == nullptr, got ? WideToUtf8(got->GetName().data()) : "undefined");
    }
    case TYPE_MTL: {
        std::string lower = valStr;
        std::transform(lower.begin(), lower.end(), lower.begin(), ::tolower);
        if (lower != "undefined" && lower != "null" && lower != "none") return NotHandled("material reference");
        if (!pb->SetValue(pid, t, (Mtl*)nullptr)) return NotHandled(kRefused);
        Mtl* got = nullptr;
        pb->GetValue(pid, t, got, FOREVER);
        return finish(got == nullptr, got ? WideToUtf8(got->GetName().data()) : "undefined");
    }
    case TYPE_STRING:
    case TYPE_FILENAME: {
        // A quoted MAXScript literal with escapes ("C:\\x", "a\"b") must be
        // unescaped exactly as MAXScript does: leave it to the fallback.
        std::string s = valStr;
        if (s.size() >= 2 && s.front() == '"' && s.back() == '"') {
            s = s.substr(1, s.size() - 2);
            if (s.find('\\') != std::string::npos || s.find('"') != std::string::npos) {
                return NotHandled("string literal with escapes");
            }
        }
        const std::wstring want = Utf8ToWide(s);
        if (!pb->SetValue(pid, t, want.c_str())) return NotHandled(kRefused);
        const MCHAR* got = nullptr;
        pb->GetValue(pid, t, got, FOREVER);
        const std::wstring gotW = got ? std::wstring(got) : std::wstring();
        bool match = gotW == want;
        if (!match && baseType == TYPE_FILENAME) {
            // Asset paths come back with the separator/case Max normalised them to.
            auto norm = [](std::wstring p) {
                std::replace(p.begin(), p.end(), L'/', L'\\');
                std::transform(p.begin(), p.end(), p.begin(), ::towlower);
                return p;
            };
            match = norm(gotW) == norm(want);
        }
        return finish(match, WideToUtf8(gotW.c_str()));
    }
    default:
        return NotHandled("parameter type is not settable from text natively");
    }
}

// ── Find and set a parameter by name on an object's IParamBlock2s ──
// NotHandled with reason "unknown parameter" when no block declares the name.
inline SetOutcome SetParamByName(Animatable* anim, const std::string& paramName,
                                 const std::string& value, TimeValue t) {
    if (!anim) return NotHandled("no target");
    std::wstring wparam = Utf8ToWide(paramName);

    // Iterate all param blocks on the object
    int numPB = anim->NumParamBlocks();
    for (int pb_idx = 0; pb_idx < numPB; pb_idx++) {
        IParamBlock2* pb = anim->GetParamBlock(pb_idx);
        if (!pb) continue;

        ParamBlockDesc2* desc = pb->GetDesc();
        if (!desc) continue;

        for (int p = 0; p < desc->count; p++) {
            const ParamDef& pd = desc->GetParamDef(desc->IndextoID(p));
            if (pd.int_name && _wcsicmp(pd.int_name, wparam.c_str()) == 0) {
                return SetPB2ParamFromString(pb, pd.ID, pd.type, value, t);
            }
        }
    }
    return NotHandled("unknown parameter");
}

// Native ParamBlock2 first; whatever that path cannot write (PB1 classes such
// as Extrude/Capsule, units, expressions, map references) goes through
// MAXScript on `targetExpr`. A native Mismatch is final — it is reported, not
// retried. The returned reason names both attempts when both fail.
inline SetOutcome SetParamWithFallback(Animatable* anim, const std::string& targetExpr,
                                       const std::string& key, const std::string& value,
                                       TimeValue t, bool allowPath = false) {
    SetOutcome native = anim ? SetParamByName(anim, key, value, t) : NotHandled("no native target");
    if (native.status != SetStatus::NotHandled) return native;
    if (targetExpr.empty()) return native;
    SetOutcome viaScript = TrySetViaMaxScript(targetExpr, key, value, allowPath);
    if (viaScript.status == SetStatus::NotHandled && !native.reason.empty() &&
        native.reason != "unknown parameter") {
        viaScript.reason = native.reason + "; " + viaScript.reason;
    }
    return viaScript;
}

} // namespace HandlerHelpers
