#include "mcp_bridge/native_handlers.h"
#include "mcp_bridge/handler_helpers.h"
#include "mcp_bridge/spatial_snapshot.h"
#include "mcp_bridge/bridge_gup.h"

#include <modstack.h>
#include <iparamb2.h>
#include <algorithm>
#include <vector>

using json = nlohmann::json;
using namespace HandlerHelpers;

static json ModifierStackJson(INode* node) {
    json stack = json::array();
    if (!node) return stack;
    Object* objRef = node->GetObjectRef();
    if (!objRef || objRef->SuperClassID() != GEN_DERIVOB_CLASS_ID) return stack;
    IDerivedObject* dobj = (IDerivedObject*)objRef;
    for (int i = 0; i < dobj->NumModifiers(); i++) {
        Modifier* mod = dobj->GetModifier(i);
        if (!mod) continue;
        stack.push_back({
            {"index", i + 1},
            {"name", WideToUtf8(mod->GetName(false).data())},
            {"class", WideToUtf8(mod->ClassName().data())},
            {"enabled", mod->IsEnabled() != 0},
            {"enabledInViews", mod->IsEnabledInViews() != 0},
            {"enabledInRenders", mod->IsEnabledInRender() != 0},
        });
    }
    return stack;
}

// ── Helper: get IDerivedObject, creating one if needed ────────
static IDerivedObject* GetOrCreateDerivedObject(INode* node) {
    Object* objRef = node->GetObjectRef();
    if (objRef && objRef->SuperClassID() == GEN_DERIVOB_CLASS_ID) {
        return (IDerivedObject*)objRef;
    }
    // Create a derived object wrapper
    IDerivedObject* dobj = CreateDerivedObject(objRef);
    node->SetObjectRef(dobj);
    return dobj;
}

// ── Helper: find modifier by name on a node ──────────────────
static int FindModifierIndex(INode* node, const std::string& modName) {
    Object* objRef = node->GetObjectRef();
    if (!objRef || objRef->SuperClassID() != GEN_DERIVOB_CLASS_ID) return -1;
    IDerivedObject* dobj = (IDerivedObject*)objRef;
    std::wstring wname = Utf8ToWide(modName);
    for (int i = 0; i < dobj->NumModifiers(); i++) {
        Modifier* mod = dobj->GetModifier(i);
        if (mod && _wcsicmp(mod->GetName(false).data(), wname.c_str()) == 0) {
            return i;
        }
    }
    return -1;
}

// ── native:add_modifier (Pure SDK) ──────────────────────────
// A modifier matches a requested class by SDK class name ("ExtrudeMod"),
// by ClassDesc internal/MAXScript name ("Extrude"), or by its stack name.
static bool ModifierMatchesClass(Modifier* mod, const std::wstring& wanted) {
    if (!mod || wanted.empty()) return false;
    if (_wcsicmp(mod->ClassName().data(), wanted.c_str()) == 0) return true;
    if (_wcsicmp(mod->GetName(false).data(), wanted.c_str()) == 0) return true;
    ClassDesc* cd = GetCOREInterface()->GetDllDir().ClassDir().FindClass(mod->SuperClassID(), mod->ClassID());
    if (cd) {
        if (cd->InternalName() && _wcsicmp(cd->InternalName(), wanted.c_str()) == 0) return true;
        if (cd->ClassName() && _wcsicmp(cd->ClassName(), wanted.c_str()) == 0) return true;
    }
    return false;
}

std::string NativeHandlers::AddModifier(const std::string& params, MCPBridgeGUP* gup) {
    return gup->GetExecutor().ExecuteSync([&params]() -> std::string {
        json p = json::parse(params, nullptr, false);
        std::string name = p.value("name", "");
        std::string modClass = p.value("modifier", "");
        std::string modParams = p.value("params", "");

        if (modClass.empty()) throw std::runtime_error("modifier is required");

        INode* node = ResolveNodeFromPayload(p);

        Interface* ip = GetCOREInterface();
        TimeValue t = ip->GetTime();

        // Find the modifier ClassDesc
        ClassDesc* cd = FindClassDescByName(modClass, OSM_CLASS_ID);
        if (!cd) cd = FindClassDescByName(modClass, WSM_CLASS_ID);
        if (!cd) cd = FindClassDescByName(modClass);
        if (!cd) throw std::runtime_error("Unknown modifier class: " + modClass);

        // Create modifier instance
        Modifier* mod = (Modifier*)ip->CreateInstance(cd->SuperClassID(), cd->ClassID());
        if (!mod) throw std::runtime_error("Failed to create modifier: " + modClass);

        // Set params via IParamBlock2 if provided. Params the PB2 path cannot set
        // (PB1 modifiers such as Extrude, unit/expression values) are applied
        // through MAXScript once the modifier is on the stack.
        std::vector<std::pair<std::string, std::string>> pendingParams;
        json failedKeys = json::array();
        json applied = json::object();
        if (!modParams.empty()) {
            // Reuse ParseParamString pattern from object_handlers
            // Simple key:value parsing
            size_t i = 0;
            while (i < modParams.size()) {
                while (i < modParams.size() && modParams[i] == ' ') i++;
                if (i >= modParams.size()) break;
                size_t keyStart = i;
                while (i < modParams.size() && modParams[i] != ':') i++;
                if (i >= modParams.size()) break;
                std::string key = modParams.substr(keyStart, i - keyStart);
                i++; // skip ':'
                size_t valStart = i;
                if (i < modParams.size() && (modParams[i] == '[' || modParams[i] == '(')) {
                    const char open = modParams[i], close = (open == '[') ? ']' : ')';
                    int depth = 1; i++;
                    while (i < modParams.size() && depth > 0) {
                        if (modParams[i] == open) depth++;
                        else if (modParams[i] == close) depth--;
                        i++;
                    }
                } else if (i < modParams.size() && modParams[i] == '"') {
                    i++;
                    while (i < modParams.size() && modParams[i] != '"') {
                        if (modParams[i] == '\\') i++;
                        i++;
                    }
                    if (i < modParams.size()) i++;
                } else {
                    while (i < modParams.size() && modParams[i] != ' ') i++;
                }
                std::string val = modParams.substr(valStart, i - valStart);
                const SetOutcome outcome = SetParamByName(mod, key, val, t);
                if (outcome.ok()) {
                    applied[key] = outcome.applied;
                } else if (outcome.status == SetStatus::Mismatch) {
                    failedKeys.push_back(PartialKey(key, val, outcome.applied, outcome.hasApplied, outcome.reason));
                } else {
                    pendingParams.emplace_back(key, val);
                }
            }
        }

        // Add modifier to node
        GetOrCreateDerivedObject(node);
        Object* objRef = node->GetObjectRef();
        if (objRef && objRef->SuperClassID() == GEN_DERIVOB_CLASS_ID) {
            IDerivedObject* dobj = (IDerivedObject*)objRef;
            dobj->AddModifier(mod);
        }

        int stackIdx = -1;
        {
            Object* ref = node->GetObjectRef();
            if (ref && ref->SuperClassID() == GEN_DERIVOB_CLASS_ID) {
                IDerivedObject* d = (IDerivedObject*)ref;
                for (int m = 0; m < d->NumModifiers(); ++m) {
                    if (d->GetModifier(m) == mod) { stackIdx = m; break; }
                }
            }
        }
        if (!pendingParams.empty()) {
            // SDK index 0 is the top of the stack == MAXScript modifiers[1].
            const std::string target = "(getAnimByHandle " + std::to_string(NodeHandle(node)) +
                                       ").modifiers[" + std::to_string(stackIdx + 1) + "]";
            for (auto& [key, val] : pendingParams) {
                const SetOutcome outcome = (stackIdx < 0)
                    ? NotHandled("modifier is not on the stack")
                    : TrySetViaMaxScript(target, key, val);
                if (outcome.ok()) {
                    applied[key] = outcome.applied;
                } else {
                    failedKeys.push_back(PartialKey(key, val, outcome.applied, outcome.hasApplied, outcome.reason));
                }
            }
            mod->NotifyDependents(FOREVER, PART_ALL, REFMSG_CHANGE);
        }

        ip->RedrawViews(t);
        const json addedModifier = {
            {"name", WideToUtf8(mod->GetName(false).data())},
            {"class", WideToUtf8(mod->ClassName().data())},
            {"index", stackIdx + 1},
        };
        if (!failedKeys.empty()) {
            // The modifier stays on the stack (PARTIAL_APPLY is committed):
            // fix the listed keys on it, never add it again.
            json details = NodeIdentityJson(node);
            details["addedModifier"] = addedModifier;
            details["keys"] = failedKeys;
            details["applied"] = applied;
            ThrowPartialApply("add_modifier: added " + WideToUtf8(mod->ClassName().data()) + " to " +
                              WideToUtf8(node->GetName()) + " but " + std::to_string(failedKeys.size()) +
                              " parameter(s) did not apply: " + failedKeys.dump(), details);
        }
        json result = NodeIdentityJson(node);
        result["message"] = "Added " + WideToUtf8(mod->ClassName().data()) + " to " + WideToUtf8(node->GetName());
        result["addedModifier"] = addedModifier;
        result["applied"] = applied;
        result["stack"] = ModifierStackJson(node);
        return result.dump();
    });
}

// ── native:remove_modifier (Pure SDK) ───────────────────────
std::string NativeHandlers::RemoveModifier(const std::string& params, MCPBridgeGUP* gup) {
    return gup->GetExecutor().ExecuteSync([&params]() -> std::string {
        json p = json::parse(params, nullptr, false);
        std::string name = p.value("name", "");
        std::string modName = p.value("modifier", "");

        if (modName.empty()) throw std::runtime_error("modifier name is required");

        INode* node = ResolveNodeFromPayload(p);

        Object* objRef = node->GetObjectRef();
        if (!objRef || objRef->SuperClassID() != GEN_DERIVOB_CLASS_ID) {
            throw std::runtime_error("No modifiers on " + name);
        }

        IDerivedObject* dobj = (IDerivedObject*)objRef;
        int idx = FindModifierIndex(node, modName);
        if (idx < 0) {
            throw std::runtime_error("Modifier \"" + modName + "\" not found on " + name);
        }

        dobj->DeleteModifier(idx);
        GetCOREInterface()->RedrawViews(GetCOREInterface()->GetTime());
        json result = NodeIdentityJson(node);
        result["message"] = "Removed modifier \"" + modName + "\" from " + WideToUtf8(node->GetName());
        result["removedModifier"] = modName;
        result["stack"] = ModifierStackJson(node);
        return result.dump();
    });
}

// ── native:set_modifier_state (Pure SDK) ────────────────────
std::string NativeHandlers::SetModifierState(const std::string& params, MCPBridgeGUP* gup) {
    return gup->GetExecutor().ExecuteSync([&params]() -> std::string {
        json p = json::parse(params, nullptr, false);
        std::string name = p.value("name", "");
        std::string modName = p.value("modifier_name", "");
        int modIndex = p.value("modifier_index", 0);

        INode* node = ResolveNodeFromPayload(p);

        Object* objRef = node->GetObjectRef();
        if (!objRef || objRef->SuperClassID() != GEN_DERIVOB_CLASS_ID) {
            throw std::runtime_error("No modifiers on " + name);
        }

        IDerivedObject* dobj = (IDerivedObject*)objRef;
        int idx = -1;

        if (modIndex > 0) {
            // 1-based index from user → 0-based SDK index
            idx = modIndex - 1;
            if (idx >= dobj->NumModifiers()) {
                throw std::runtime_error("Modifier index " + std::to_string(modIndex) +
                    " out of range (has " + std::to_string(dobj->NumModifiers()) + ")");
            }
        } else if (!modName.empty()) {
            idx = FindModifierIndex(node, modName);
            if (idx < 0) {
                throw std::runtime_error("Modifier \"" + modName + "\" not found on " + name);
            }
        } else {
            throw std::runtime_error("Either modifier_name or modifier_index is required");
        }

        Modifier* mod = dobj->GetModifier(idx);
        if (!mod) throw std::runtime_error("Could not get modifier at index");

        bool changed = false;

        if (p.contains("enabled") && !p["enabled"].is_null()) {
            bool val = p["enabled"].get<bool>();
            if (val) mod->EnableMod();
            else mod->DisableMod();
            changed = true;
        }

        if (p.contains("enabled_in_views") && !p["enabled_in_views"].is_null()) {
            bool val = p["enabled_in_views"].get<bool>();
            if (val) mod->EnableModInViews();
            else mod->DisableModInViews();
            changed = true;
        }

        if (p.contains("enabled_in_renders") && !p["enabled_in_renders"].is_null()) {
            bool val = p["enabled_in_renders"].get<bool>();
            if (val) mod->EnableModInRender();
            else mod->DisableModInRender();
            changed = true;
        }

        if (!changed) return "No state changes specified.";

        GetCOREInterface()->RedrawViews(GetCOREInterface()->GetTime());

        std::string modDisplayName = WideToUtf8(mod->GetName(false).data());
        json result = NodeIdentityJson(node);
        result["message"] = "Set state on " + modDisplayName + " (" + WideToUtf8(node->GetName()) + ")";
        result["modifier"] = {
            {"name", modDisplayName},
            {"index", idx + 1},
            {"class", WideToUtf8(mod->ClassName().data())},
            {"enabled", mod->IsEnabled() != 0},
            {"enabledInViews", mod->IsEnabledInViews() != 0},
            {"enabledInRenders", mod->IsEnabledInRender() != 0},
        };
        result["stack"] = ModifierStackJson(node);
        return result.dump();
    });
}

// ── native:collapse_modifier_stack (Pure SDK) ───────────────
std::string NativeHandlers::CollapseModifierStack(const std::string& params, MCPBridgeGUP* gup) {
    return gup->GetExecutor().ExecuteSync([&params]() -> std::string {
        json p = json::parse(params, nullptr, false);
        std::string name = p.value("name", "");
        int toIndex = p.value("to_index", 0);
        bool dryRun = p.value("dry_run", false);

        INode* node = ResolveNodeFromPayload(p);
        name = WideToUtf8(node->GetName());

        Interface* ip = GetCOREInterface();
        TimeValue t = ip->GetTime();

        Object* objRef = node->GetObjectRef();
        if (!objRef || objRef->SuperClassID() != GEN_DERIVOB_CLASS_ID) {
            json result = NodeIdentityJson(node);
            result["status"] = "no_stack";
            result["message"] = "No modifier stack to collapse on " + name;
            result["stack"] = json::array();
            return result.dump();
        }

        IDerivedObject* dobj = (IDerivedObject*)objRef;
        int numMods = dobj->NumModifiers();
        json beforeStack = ModifierStackJson(node);

        if (dryRun) {
            json result = NodeIdentityJson(node);
            result["dry_run"] = true;
            result["to_index"] = toIndex;
            result["stack"] = beforeStack;
            result["message"] = toIndex > 0
                ? "Would collapse " + name + " to modifier index " + std::to_string(toIndex)
                : "Would collapse entire stack on " + name;
            return result.dump();
        }

        if (toIndex > 0) {
            // Collapse to specific index (1-based)
            if (toIndex > numMods) {
                throw std::runtime_error("Index " + std::to_string(toIndex) +
                    " out of range (stack has " + std::to_string(numMods) + " modifiers)");
            }
            // Evaluate pipeline at that modifier and replace
            // SDK approach: delete modifiers above the target index
            // In Max SDK, modifier 0 is the top of stack
            // toIndex=1 means keep only the topmost, collapse rest
            // Actually, CollapseNodeTo in MAXScript does: evaluate pipeline down to that modifier
            // Pure SDK: we evaluate the world state, convert to mesh, replace object ref
            // For partial collapse, use RunMAXScript as it maps to maxOps.CollapseNodeTo
            std::string script = "maxOps.CollapseNodeTo (getNodeByName \"" +
                JsonEscape(name) + "\") " + std::to_string(toIndex) + " off";
            RunMAXScript(script);
            ip->RedrawViews(t);
            json result = NodeIdentityJson(node);
            result["message"] = "Collapsed " + WideToUtf8(node->GetName()) + " to modifier index " + std::to_string(toIndex);
            result["to_index"] = toIndex;
            result["beforeStack"] = beforeStack;
            result["stack"] = ModifierStackJson(node);
            return result.dump();
        }

        // Full collapse: evaluate pipeline, get final object, replace
        ObjectState os = node->EvalWorldState(t);
        if (!os.obj) throw std::runtime_error("Failed to evaluate object");

        // Convert to editable mesh
        if (os.obj->CanConvertToType(triObjectClassID)) {
            TriObject* tri = (TriObject*)os.obj->ConvertToType(t, triObjectClassID);
            if (tri && tri != os.obj) {
                node->SetObjectRef(tri);
            } else if (tri == os.obj) {
                // Already a tri, but need to strip the derived object wrapper
                // Use the simple approach
                std::string script = "maxOps.CollapseNode (getNodeByName \"" +
                    JsonEscape(name) + "\") off";
                RunMAXScript(script);
            }
        } else {
            // Fallback for non-mesh objects
            std::string script = "maxOps.CollapseNode (getNodeByName \"" +
                JsonEscape(name) + "\") off";
            RunMAXScript(script);
        }

        ip->RedrawViews(t);

        // Get resulting class
        ObjectState finalOs = node->EvalWorldState(t);
        std::string resultClass = finalOs.obj ? WideToUtf8(finalOs.obj->ClassName().data()) : "Unknown";
        json result = NodeIdentityJson(node);
        result["message"] = "Collapsed entire stack on " + WideToUtf8(node->GetName());
        result["resultClass"] = resultClass;
        result["beforeStack"] = beforeStack;
        result["stack"] = ModifierStackJson(node);
        result["spatial"] = SpatialSnapshot::BuildSpatialSnapshot(node, t);
        return result.dump();
    });
}

// ── native:make_modifier_unique (Pure SDK) ──────────────────
std::string NativeHandlers::MakeModifierUnique(const std::string& params, MCPBridgeGUP* gup) {
    return gup->GetExecutor().ExecuteSync([&params]() -> std::string {
        json p = json::parse(params, nullptr, false);
        std::string name = p.value("name", "");
        int modIndex = p.value("modifier_index", 0);

        if (modIndex <= 0) throw std::runtime_error("modifier_index (1-based) is required");

        INode* node = ResolveNodeFromPayload(p);

        Object* objRef = node->GetObjectRef();
        if (!objRef || objRef->SuperClassID() != GEN_DERIVOB_CLASS_ID) {
            throw std::runtime_error("No modifiers on " + name);
        }

        IDerivedObject* dobj = (IDerivedObject*)objRef;
        int idx = modIndex - 1; // 0-based
        if (idx >= dobj->NumModifiers()) {
            throw std::runtime_error("Index " + std::to_string(modIndex) + " out of range");
        }

        Modifier* mod = dobj->GetModifier(idx);
        if (!mod) throw std::runtime_error("Could not get modifier at index");

        std::string modDisplayName = WideToUtf8(mod->GetName(false).data());

        // Clone the modifier and replace
        RemapDir* remap = NewRemapDir();
        Modifier* cloned = (Modifier*)mod->Clone(*remap);
        remap->DeleteThis();

        if (!cloned) throw std::runtime_error("Failed to clone modifier");

        // Replace: delete old, add cloned at same position
        dobj->DeleteModifier(idx);
        dobj->AddModifier(cloned, nullptr, idx);

        GetCOREInterface()->RedrawViews(GetCOREInterface()->GetTime());
        json result = NodeIdentityJson(node);
        result["message"] = "Made modifier " + modDisplayName + " unique on " + WideToUtf8(node->GetName());
        result["modifier"] = {
            {"name", modDisplayName},
            {"index", modIndex},
        };
        result["stack"] = ModifierStackJson(node);
        return result.dump();
    });
}

// ── native:set_modifier_property (Pure SDK) ─────────────────
std::string NativeHandlers::SetModifierProperty(const std::string& params, MCPBridgeGUP* gup) {
    return gup->GetExecutor().ExecuteSync([&params]() -> std::string {
        json p = json::parse(params, nullptr, false);
        std::string propName = p.value("property_name", "");
        std::string modClassName = p.value("modifier_class", "");
        std::string modName = p.value("modifier_name", "");
        int modIndex = p.value("modifier_index", 0);
        auto names = p.value("names", std::vector<std::string>{});
        bool selectionOnly = p.value("selection_only", false);
        std::string singleName = p.value("name", "");

        if (propName.empty()) throw std::runtime_error("property_name is required");
        if (p.find("property_value") == p.end()) {
            throw std::runtime_error("property_value is required");
        }
        std::string propValue;
        if (p["property_value"].type() == json::value_t::string) {
            propValue = p["property_value"].get<std::string>();
        } else {
            propValue = p["property_value"].dump();
        }

        if (modIndex <= 0 && modName.empty() && modClassName.empty()) {
            throw std::runtime_error(
                "Specify modifier_index, modifier_name, or modifier_class to choose a modifier");
        }

        if (!singleName.empty()) {
            names.insert(names.begin(), singleName);
        }

        Interface* ip = GetCOREInterface();
        TimeValue t = ip->GetTime();

        std::vector<INode*> targets;
        if (PayloadHandleValue(p) != 0ULL) {
            targets.push_back(ResolveNodeFromPayload(p));
        } else if (!names.empty()) {
            for (const auto& n : names) {
                INode* node = FindNodeByName(n);
                if (node) targets.push_back(node);
            }
        } else if (selectionOnly) {
            int selCount = ip->GetSelNodeCount();
            for (int i = 0; i < selCount; i++) {
                targets.push_back(ip->GetSelNode(i));
            }
        } else if (modIndex > 0 || !modName.empty()) {
            throw std::runtime_error("Specify name, names, or selection_only to choose objects");
        } else {
            INode* root = ip->GetRootNode();
            CollectNodes(root, targets);
        }

        if (targets.empty()) throw std::runtime_error("No target objects found");

        std::wstring wModClass = modClassName.empty() ? L"" : Utf8ToWide(modClassName);
        json hits = json::array();
        json failedTargets = json::array();
        std::vector<unsigned long long> failedHandles;
        int modCount = 0;

        ip->DisableSceneRedraw();

        for (INode* node : targets) {
            Object* objRef = node->GetObjectRef();
            if (!objRef || objRef->SuperClassID() != GEN_DERIVOB_CLASS_ID) continue;

            IDerivedObject* dobj = (IDerivedObject*)objRef;
            const std::string nodeName = WideToUtf8(node->GetName());

            auto tryModifier = [&](Modifier* mod, int idx) {
                if (!mod) return;
                if (!modClassName.empty() && !ModifierMatchesClass(mod, wModClass)) return;
                const std::string target = "(getAnimByHandle " + std::to_string(NodeHandle(node)) +
                                           ").modifiers[" + std::to_string(idx + 1) + "]";
                const SetOutcome outcome = SetParamWithFallback(mod, target, propName, propValue, t);
                if (outcome.hasApplied) mod->NotifyDependents(FOREVER, PART_ALL, REFMSG_CHANGE);
                json entry = {
                    {"object", nodeName},
                    {"handle", NodeHandle(node)},
                    {"modifier", WideToUtf8(mod->GetName(false).data())},
                    {"index", idx + 1},
                    {"class", WideToUtf8(mod->ClassName().data())},
                };
                if (!outcome.ok()) {
                    // A matched target that did not take the value: never skip it silently.
                    json key = PartialKey(propName, propValue, outcome.applied, outcome.hasApplied, outcome.reason);
                    key.update(entry);
                    failedTargets.push_back(key);
                    if (std::find(failedHandles.begin(), failedHandles.end(), NodeHandle(node)) == failedHandles.end()) {
                        failedHandles.push_back(NodeHandle(node));
                    }
                    return;
                }
                modCount++;
                entry["applied"] = outcome.applied;
                hits.push_back(entry);
            };

            if (modIndex > 0) {
                int idx = modIndex - 1;
                if (idx < dobj->NumModifiers()) {
                    tryModifier(dobj->GetModifier(idx), idx);
                }
            } else if (!modName.empty()) {
                int idx = FindModifierIndex(node, modName);
                if (idx >= 0) {
                    tryModifier(dobj->GetModifier(idx), idx);
                }
            } else {
                for (int m = 0; m < dobj->NumModifiers(); m++) {
                    tryModifier(dobj->GetModifier(m), m);
                }
            }
        }

        ip->EnableSceneRedraw();
        ip->RedrawViews(t);

        if (!failedTargets.empty()) {
            json details;
            details["handles"] = failedHandles;
            details["keys"] = failedTargets;
            details["modified"] = hits;
            ThrowPartialApply("set_modifier_property: " + propName + " did not apply on " +
                              std::to_string(failedTargets.size()) + " of " +
                              std::to_string(failedTargets.size() + hits.size()) + " matched modifier(s)",
                              details);
        }

        if (modCount == 0) {
            throw std::runtime_error(
                "No modifiers updated — check object names, modifier target, and property name");
        }

        json out = {
            {"modified", modCount},
            {"property", propName},
            {"value", propValue},
            {"hits", hits},
        };
        return out.dump();
    });
}
