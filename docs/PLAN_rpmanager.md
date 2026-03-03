# RPManager MCP Tools — Implementation Plan

## Overview

RPManager (Render Pass Manager) is a widely-used 3ds Max plugin for managing
render passes, visibility sets, capture property sets, material overrides, and
per-pass scripting. This plan describes adding full RPManager support to the
3dsmax-mcp server so that an AI assistant can query, configure, and automate
render passes via MCP tools.

All tools follow the existing project conventions:
- Python file in `src/tools/` with `@mcp.tool()` decorators
- MAXScript string built in Python, sent via `client.send_command()`
- JSON response built by manual string concatenation inside MAXScript
- Tool module imported in `src/server.py` line 13 for auto-registration

Target file: **`src/tools/rpmanager.py`**

---

## Phase 0 — Runtime Introspection (Research)

> **Phase 0 Status:** COMPLETED 2026-03-03
> **Full results:** `docs/research/rpmanager_introspection.md`
> **Key findings:**
> - RPMdata is a flat MAXScript struct (RmanagerDataStruct), NOT nested sub-structs
> - Version 7.8, detected via `RPMdata.version()`
> - AddPass() EXISTS (0 args) -- pass creation IS possible
> - RMDeleteItem EXISTS (1 arg: index) -- pass deletion IS possible
> - duplicatePass() EXISTS but NEEDS UI OPEN (crashes without listbox)
> - CRITICAL: Many functions require RPManager UI to be open (`RPMdata.RMopenFloater()`)
> - RPMObjProp is UndefinedClass -- object property overrides need different approach
> - 300+ struct members (functions + data)

Before writing any tools, we must confirm the full RPManager MAXScript API by
running introspection scripts inside a live 3ds Max session with RPManager
installed. The official rpmanager.com documentation site is down, so runtime
discovery is the only reliable source.

### 0.1 Core Struct Discovery

Run each of these via `execute_maxscript` and capture the output:

```maxscript
-- 0.1a: Confirm RPMdata exists and get its type
if RPMdata != undefined then
    classof RPMdata as string
else
    "RPMdata is undefined — RPManager not installed"
```
> **Result:** `#Struct:RmanagerDataStruct` -- confirmed as a flat MAXScript struct with 300+ members.

```maxscript
-- 0.1b: Full property dump of RPMdata
if RPMdata != undefined then (
    local ss = StringStream ""
    showProperties RPMdata to:ss
    ss as string
) else "RPMdata undefined"
```
> **Result:** Returns mix of `<fn>` functions and `<data>` members; RPMdata is NOT nested sub-structs.

```maxscript
-- 0.1c: Full method dump of RPMdata
if RPMdata != undefined then (
    local ss = StringStream ""
    showMethods RPMdata to:ss
    ss as string
) else "RPMdata undefined"
```
> **Result:** MAXScript structs do not support `showMethods`; all callable members are `<fn>` entries from `showProperties`.

```maxscript
-- 0.1d: Interface dump
if RPMdata != undefined then (
    local ss = StringStream ""
    showInterfaces RPMdata to:ss
    ss as string
) else "RPMdata undefined"
```
> **Result:** MAXScript structs do not support `showInterfaces`; not applicable.

```maxscript
-- 0.1e: RPMCaptureProps (may be RPMdata.RPMObjProp or a sibling global)
try (
    local ss = StringStream ""
    showProperties RPMdata.RPMObjProp to:ss
    format "RPMObjProp properties:\n%\n" (ss as string)
    ss = StringStream ""
    showMethods RPMdata.RPMObjProp to:ss
    format "RPMObjProp methods:\n%\n" (ss as string)
) catch (
    format "RPMObjProp access failed: %\n" (getCurrentException())
)
```
> **Result:** RPMObjProp is `UndefinedClass` -- may need RPManager UI open or different initialization path.

```maxscript
-- 0.1f: RPMVisSets (visibility set sub-struct)
try (
    local ss = StringStream ""
    showProperties RPMdata.RPMVisSets to:ss
    format "RPMVisSets properties:\n%\n" (ss as string)
    ss = StringStream ""
    showMethods RPMdata.RPMVisSets to:ss
    format "RPMVisSets methods:\n%\n" (ss as string)
) catch (
    format "RPMVisSets access failed: %\n" (getCurrentException())
)
```
> **Result:** RPMVisSets is NOT a sub-struct; visibility is managed via top-level functions: `writeVisSetData`, `getVisUndoState`, `isolateSet`, etc.

### 0.2 Pass Create/Delete Discovery

These are the highest-priority unknowns:

```maxscript
-- 0.2a: Search for add/create/new/delete/remove methods
if RPMdata != undefined then (
    local ss = StringStream ""
    showMethods RPMdata to:ss
    local full = ss as string
    -- Look for keywords
    local keywords = #("add", "create", "new", "delete", "remove", "duplicate", "copy")
    local result = ""
    for kw in keywords do (
        if findString (toLower full) kw != undefined then
            result += kw + ": FOUND\n"
        else
            result += kw + ": not found\n"
    )
    result + "\n---FULL---\n" + full
) else "RPMdata undefined"
```
> **Result:** Used `showProperties` instead (structs lack `showMethods`). Found: add, delete, duplicate, copy keywords all present.

```maxscript
-- 0.2b: Try known creation patterns
try (RPMdata.AddPass "TestPass"; "AddPass exists") catch ("AddPass: " + getCurrentException())
try (RPMdata.CreatePass "TestPass"; "CreatePass exists") catch ("CreatePass: " + getCurrentException())
try (RPMdata.NewPass "TestPass"; "NewPass exists") catch ("NewPass: " + getCurrentException())
try (RPMdata.addNewPass "TestPass"; "addNewPass exists") catch ("addNewPass: " + getCurrentException())
try (RPMdata.duplicatePass 1; "duplicatePass exists") catch ("duplicatePass: " + getCurrentException())
```
> **Result:** `AddPass()` EXISTS (0 args, returns undefined). `duplicatePass()` EXISTS but crashes without UI (needs listbox). CreatePass, NewPass, addNewPass do not exist.

```maxscript
-- 0.2c: Try deletion patterns
try (RPMdata.DeletePass 1; "DeletePass exists") catch ("DeletePass: " + getCurrentException())
try (RPMdata.RemovePass 1; "RemovePass exists") catch ("RemovePass: " + getCurrentException())
try (RPMdata.deleteSelectedPasses(); "deleteSelectedPasses exists") catch ("deleteSelectedPasses: " + getCurrentException())
```
> **Result:** `RMDeleteItem` EXISTS (1 arg: index, returns boolean). DeletePass/RemovePass/deleteSelectedPasses do not exist as named.

### 0.3 Batch Render Discovery

```maxscript
-- 0.3a: Search for render/batch methods
try (RPMdata.RenderPasses; "RenderPasses exists") catch ("RenderPasses: " + getCurrentException())
try (RPMdata.RenderChecked; "RenderChecked exists") catch ("RenderChecked: " + getCurrentException())
try (RPMdata.RenderAll; "RenderAll exists") catch ("RenderAll: " + getCurrentException())
try (RPMdata.batchRender; "batchRender exists") catch ("batchRender: " + getCurrentException())
try (RPMdata.startRender; "startRender exists") catch ("startRender: " + getCurrentException())
```
> **Result:** Found: `renderLocally`, `submitChecked`, `submitSelected`, `previewChecked`, `previewSelected`, `previewLocally`. RenderPasses/RenderAll/batchRender/startRender do not exist.

### 0.4 Visibility Set Deep Dive

```maxscript
-- 0.4a: Explore visibility set API
if RPMdata != undefined then (
    local result = ""
    -- Try common patterns
    try (result += "GetVisSetCount: " + (RPMdata.GetVisSetCount() as string) + "\n") catch (result += "GetVisSetCount: FAIL\n")
    try (result += "RPMVisSets type: " + (classof RPMdata.RPMVisSets) as string + "\n") catch (result += "RPMVisSets: FAIL\n")
    try (
        local ss = StringStream ""
        showProperties RPMdata.RPMVisSets to:ss
        result += "VisSets props:\n" + (ss as string) + "\n"
    ) catch ()
    try (
        local ss = StringStream ""
        showMethods RPMdata.RPMVisSets to:ss
        result += "VisSets methods:\n" + (ss as string) + "\n"
    ) catch ()
    result
) else "RPMdata undefined"
```
> **Result:** RPMVisSets is NOT a sub-struct. Visibility is managed via top-level RPMdata functions: `writeVisSetData`, `getVisUndoState`, `isolateSet`, `deleteVisSetsHolder`, `UpdateLayerArray`, `CA_redefineVis`.

### 0.5 Installed Script File Examination

```maxscript
-- 0.5a: Find RPManager installation directory and list .ms files
local maxDir = getDir #maxroot
local rpDir = maxDir + "scripts\\RPManager\\"
local files = getFiles (rpDir + "*.ms")
local result = "RPManager scripts dir: " + rpDir + "\n"
result += "Files found: " + (files.count as string) + "\n"
for f in files do result += f + "\n"
result
```
> **Result:** Not executed in this introspection session; API was confirmed via live `showProperties` and direct function calls instead.

After identifying the files, read key ones to find undocumented functions:

```maxscript
-- 0.5b: Read the main RPManager script to discover all public functions
-- (adjust filename based on 0.5a results)
local f = openFile (getDir #maxroot + "scripts\\RPManager\\RPManager.ms") mode:"r"
if f != undefined then (
    local content = ""
    while not eof f do content += readLine f + "\n"
    close f
    content
) else "File not found"
```
> **Result:** Not executed; sufficient API coverage obtained from live introspection.

### 0.6 Version Detection

```maxscript
-- 0.6a: Check for version info
try (RPMdata.version as string) catch ("version: " + getCurrentException())
try (RPMdata.getVersion() as string) catch ("getVersion: " + getCurrentException())
try (RPMdata.RPMVersion as string) catch ("RPMVersion: " + getCurrentException())
```
> **Result:** `RPMdata.version()` returns `"7.8"` (it is a function, not a property). `RPMdata.RManVersion` is undefined.

### 0.7 Capture Sets Deep Dive (RPMCaptureProps)

```maxscript
-- 0.7a: Full CaptureProps exploration
if RPMdata != undefined then (
    local cp = undefined
    try (cp = RPMdata.RPMCaptureProps) catch ()
    if cp == undefined do try (cp = RPMdata.RPMObjProp) catch ()
    if cp != undefined then (
        local ss = StringStream ""
        showProperties cp to:ss
        local props = ss as string
        ss = StringStream ""
        showMethods cp to:ss
        local meths = ss as string
        "CaptureProps type: " + (classof cp) as string + "\nProperties:\n" + props + "\nMethods:\n" + meths
    ) else "CaptureProps not found"
) else "RPMdata undefined"
```
> **Result:** `RPMObjProp` is `UndefinedClass`. Object property overrides are managed via top-level RPMdata functions: `getObjPropPrefsData`, `setObjPropPrefsData`, `storePropOverrideData`, `convertRenderPropertyOverrideToNewData`. The nested sub-struct model in the original plan is incorrect.

### Expected Outcomes

After Phase 0, we will have:
1. Confirmed list of all RPMdata methods and properties -- **DONE: 300+ members catalogued**
2. Knowledge of whether pass creation/deletion is scriptable -- **DONE: AddPass() and RMDeleteItem confirmed**
3. Full visibility set API -- **DONE: flat functions, not sub-struct**
4. Full capture set API -- **PARTIAL: RPMObjProp is UndefinedClass, needs further investigation with UI open**
5. Whether batch render is triggerable -- **DONE: renderLocally, submitChecked, submitSelected confirmed**
6. RPManager version detection capability -- **DONE: RPMdata.version() returns "7.8"**
7. Any undocumented functions from installed .ms files -- **SKIPPED: sufficient coverage from live introspection**

---

## UI Dependency Matrix

> **CRITICAL:** Many RPManager functions require the RPManager UI (floater dialog) to be open.
> They interact with .NET listbox controls internally, so calling them headlessly causes crashes
> or silently fails.

### Pattern for UI-Dependent Operations

```maxscript
RPMdata.RMopenFloater()  -- open RPManager UI
-- ... do work that requires UI ...
-- UI remains open; close manually if desired
```

### Functions That Work WITHOUT UI (Headless-Safe)

| Function | Confirmed |
|----------|-----------|
| `version()` | Yes -- returns "7.8" |
| `getpasscount()` | Yes -- returns int (but 0 after headless AddPass) |
| `SetPassName` | Yes -- returns OK |
| `GetPassOutputPath` | Yes -- returns string |
| `GetPassBeforeScript` / `SetPassBeforeScript` | Yes |
| `GetPassAfterScript` / `SetPassAfterScript` | Yes |
| `GetPassTimeType` / `SetPassTimeType` | Yes |
| `GetPassRange` / `SetPassRange` | Yes |
| `GetPassVisSetName` | Yes |
| `GetPassBGColor` / `SetPassColor` | Yes |
| `SetRenderer` / `getrenderer` | Yes (returns undefined with no passes) |

### Functions That NEED UI Open

| Function | Evidence |
|----------|----------|
| `AddPass()` | Runs without error but `getpasscount()` stays 0 -- pass not registered without UI |
| `duplicatePass()` | Crashes: `Unknown property "items" in dotNetControl:lstbox:(null)` |
| `GetPassNameFromID` | Fails in headless mode |
| `GetPassChecked` | Fails in headless mode |
| `getCheckedPasses` | Needs 1 arg; likely UI-dependent |

### Functions Needing Investigation

| Function | Status |
|----------|--------|
| `renderLocally` | Exists, not tested for UI dependency |
| `submitChecked` / `submitSelected` | Exists, not tested |
| `previewChecked` / `previewSelected` | Exists, not tested |
| `captureCamera` | Exists, not tested |
| `captureStateSet` / `restoreStateSet` | Exists, not tested |

---

## Phase 1 — RPManager Detection & Pass Reading (MVP)

**Priority: Highest — enables basic querying immediately.**

### 1.1 Helper: `_rpm_check()` — Installation Guard

Every RPManager tool needs a guard that returns a clear error if RPManager is
not installed. This is a Python-side helper that wraps the MAXScript in a
detection check.

```python
def _rpm_guard(inner_script: str) -> str:
    """Wrap MAXScript in an RPManager installation check."""
    return f"""(
        if RPMdata == undefined then (
            "{{\\\"error\\\": \\\"RPManager is not installed or not loaded\\\"}}"
        ) else (
            {inner_script}
        )
    )"""
```

### 1.2 Tool: `get_rpmanager_passes`

**Purpose:** List all passes with summary info — the primary discovery tool.

```
Tool name:    get_rpmanager_passes
Parameters:   (none)
Returns:      JSON
Prerequisites: RPManager installed, scene may have 0+ passes
```

**Python signature:**
```python
@mcp.tool()
def get_rpmanager_passes() -> str:
    """List all RPManager render passes with name, camera, output path,
    frame range, and checked/enabled state.

    Use this to see the full render pass setup before making changes.
    Each pass has a 1-based index and a unique ID — use the index for
    get/set operations.

    Returns:
        JSON with passCount and array of passes, each containing:
        index, name, camera, outputPath, frameRange, timeType, checked.
    """
```

**MAXScript template:**

> **NOTE (Phase 0 update):** Uses confirmed function names: `getpasscount()`, `GetPassNameFromID`,
> `getpasscamera`, `GetPassOutputPath`, `GetPassRange`, `GetPassTimeType`.
> `GetPassChecked` fails headlessly -- omitted from headless path; use `getCheckedPasses` with UI open.
> **NEEDS_UI** for checked passes -- consider opening floater first.

```maxscript
(
    if RPMdata == undefined then (
        "{\"error\": \"RPManager is not installed or not loaded\"}"
    ) else (
        local pc = RPMdata.getpasscount()
        local result = "{\"passCount\": " + pc as string + ", \"passes\": ["
        for i = 1 to pc do (
            if i > 1 do result += ","
            local pName = RPMdata.GetPassNameFromID i
            local pCam = RPMdata.getpasscamera i
            local pOut = RPMdata.GetPassOutputPath i
            local pRange = RPMdata.GetPassRange i   -- #(start, end, nth)
            local pTimeType = RPMdata.GetPassTimeType i
            local camName = ""
            if pCam != undefined do (
                try (camName = pCam.name) catch (camName = pCam as string)
            )
            local safeName = substituteString pName "\"" "\\\""
            local safeOut = substituteString (substituteString pOut "\\" "/") "\"" "\\\""
            result += "{"
            result += "\"index\": " + i as string
            result += ", \"name\": \"" + safeName + "\""
            if camName != "" then
                result += ", \"camera\": \"" + camName + "\""
            else
                result += ", \"camera\": null"
            result += ", \"outputPath\": \"" + safeOut + "\""
            result += ", \"frameRange\": {\"start\": " + pRange[1] as string
            result += ", \"end\": " + pRange[2] as string
            result += ", \"nthFrame\": " + pRange[3] as string + "}"
            result += ", \"timeType\": " + pTimeType as string
            result += "}"
        )
        result += "]}"
        result
    )
)
```

**Return format:**
```json
{
    "passCount": 3,
    "passes": [
        {
            "index": 1,
            "name": "Beauty",
            "camera": "Camera_Main",
            "outputPath": "C:/renders/beauty/beauty_.exr",
            "frameRange": {"start": 0, "end": 100, "nthFrame": 1},
            "timeType": 0
        }
    ],
    "checkedPasses": [1, 3]
}
```

### 1.3 Tool: `get_rpmanager_pass_detail`

**Purpose:** Detailed info for a single pass including scripts, unique ID, etc.

```
Tool name:    get_rpmanager_pass_detail
Parameters:   pass_index: int (1-based)
Returns:      JSON
Prerequisites: RPManager installed, valid pass index
```

**Python signature:**
```python
@mcp.tool()
def get_rpmanager_pass_detail(pass_index: int) -> str:
    """Get detailed information for a specific RPManager pass.

    Args:
        pass_index: 1-based index of the pass (from get_rpmanager_passes).

    Returns:
        JSON with full pass details: name, camera, outputPath, frameRange,
        timeType, beforeScript, afterScript, scriptsEnabled, uniqueID.
    """
```

**MAXScript template:**

> **NOTE (Phase 0 update):** Uses confirmed function names. See UI Dependency Matrix for headless safety.

```maxscript
(
    if RPMdata == undefined then (
        "{\"error\": \"RPManager is not installed or not loaded\"}"
    ) else (
        local pc = RPMdata.getpasscount()
        local i = <pass_index>
        if i < 1 or i > pc then (
            "{\"error\": \"Pass index " + i as string + " out of range (1-" + pc as string + ")\"}"
        ) else (
            local pName = RPMdata.GetPassNameFromID i
            local pCam = RPMdata.getpasscamera i
            local pOut = RPMdata.GetPassOutputPath i
            local pRange = RPMdata.GetPassRange i
            local pTimeType = RPMdata.GetPassTimeType i
            local pBefore = RPMdata.GetPassBeforeScript i
            local pAfter = RPMdata.GetPassAfterScript i
            local pScriptEnabled = RPMdata.GetBeforeAfterScriptEnabled i
            local camName = ""
            if pCam != undefined do (
                try (camName = pCam.name) catch (camName = pCam as string)
            )
            -- Escape strings for JSON
            local safeName = substituteString pName "\"" "\\\""
            local safeOut = substituteString (substituteString pOut "\\" "/") "\"" "\\\""
            local safeBefore = substituteString (substituteString pBefore "\\" "\\\\") "\"" "\\\""
            safeBefore = substituteString safeBefore "\n" "\\n"
            local safeAfter = substituteString (substituteString pAfter "\\" "\\\\") "\"" "\\\""
            safeAfter = substituteString safeAfter "\n" "\\n"

            local result = "{"
            result += "\"index\": " + i as string
            result += ", \"name\": \"" + safeName + "\""
            if camName != "" then
                result += ", \"camera\": \"" + camName + "\""
            else
                result += ", \"camera\": null"
            result += ", \"outputPath\": \"" + safeOut + "\""
            result += ", \"frameRange\": {\"start\": " + pRange[1] as string
            result += ", \"end\": " + pRange[2] as string
            result += ", \"nthFrame\": " + pRange[3] as string + "}"
            result += ", \"timeType\": " + pTimeType as string
            result += ", \"beforeScript\": \"" + safeBefore + "\""
            result += ", \"afterScript\": \"" + safeAfter + "\""
            result += ", \"scriptsEnabled\": " + (if pScriptEnabled then "true" else "false")
            result += "}"
            result
        )
    )
)
```

---

## Phase 2 — Pass Property Modification

**Priority: High — enables AI-driven pass configuration.**

### 2.1 Tool: `set_rpmanager_pass_property`

**Purpose:** Set any single property on a pass (name, camera, output, range, etc.).

```
Tool name:    set_rpmanager_pass_property
Parameters:
    pass_index: int          — 1-based pass index (required)
    property: str            — one of: "name", "camera", "output_path",
                               "frame_range", "time_type" (required)
    value: str               — the new value (required)
    frame_start: int = 0     — start frame (only for frame_range)
    frame_end: int = 100     — end frame (only for frame_range)
    nth_frame: int = 1       — nth frame (only for frame_range)
Returns:      Confirmation string
Prerequisites: RPManager installed, valid pass index
```

**Python signature:**
```python
@mcp.tool()
def set_rpmanager_pass_property(
    pass_index: int,
    property: str,
    value: str = "",
    frame_start: int = 0,
    frame_end: int = 100,
    nth_frame: int = 1,
) -> str:
    """Set a property on an RPManager render pass.

    Args:
        pass_index: 1-based index of the pass.
        property: Property to set. One of:
            - "name": Pass name (value = new name string)
            - "camera": Camera name (value = scene camera name, or "" to clear)
            - "output_path": Render output path (value = file path)
            - "frame_range": Frame range (uses frame_start, frame_end, nth_frame)
            - "time_type": Time type integer (value = "0", "1", etc.)
        value: The new value (string). Used for name, camera, output_path, time_type.
        frame_start: Start frame (only used when property = "frame_range").
        frame_end: End frame (only used when property = "frame_range").
        nth_frame: Nth frame (only used when property = "frame_range").

    Returns confirmation with old and new values.
    """
```

**MAXScript template (dispatches by property):**

For `property == "name"`:
```maxscript
(
    local i = <pass_index>
    local pc = RPMdata.GetPassCount()
    if i < 1 or i > pc then (
        "Error: pass index " + i as string + " out of range"
    ) else (
        local oldVal = RPMdata.GetPassName i
        RPMdata.SetPassName i "<value>"
        RPMdata.UpdateUI()
        "Pass " + i as string + " name: \"" + oldVal + "\" -> \"<value>\""
    )
)
```

For `property == "camera"`:
```maxscript
(
    local i = <pass_index>
    local cam = getNodeByName "<value>"
    if cam == undefined and "<value>" != "" then (
        "Error: camera \"<value>\" not found in scene"
    ) else (
        local oldCam = RPMdata.GetPassCamera i
        local oldName = if oldCam != undefined then oldCam.name else "none"
        RPMdata.SetPassCamera i cam
        RPMdata.UpdateUI()
        "Pass " + i as string + " camera: \"" + oldName + "\" -> \"<value>\""
    )
)
```

For `property == "output_path"`:
```maxscript
(
    local i = <pass_index>
    local oldVal = RPMdata.GetPassOutputPath i
    RPMdata.SetPassOutputPath i "<value>"
    RPMdata.UpdateUI()
    "Pass " + i as string + " output: \"" + oldVal + "\" -> \"<value>\""
)
```

For `property == "frame_range"`:
```maxscript
(
    local i = <pass_index>
    local oldRange = RPMdata.GetPassRange i
    RPMdata.SetPassRange i <frame_start> <frame_end> <nth_frame>
    RPMdata.UpdateUI()
    "Pass " + i as string + " range: [" + oldRange[1] as string + "," + oldRange[2] as string + "," + oldRange[3] as string + "] -> [<frame_start>,<frame_end>,<nth_frame>]"
)
```

For `property == "time_type"`:
```maxscript
(
    local i = <pass_index>
    local oldVal = RPMdata.GetPassTimeType i
    RPMdata.SetPassTimeType i <value_int>
    RPMdata.UpdateUI()
    "Pass " + i as string + " timeType: " + oldVal as string + " -> <value>"
)
```

### 2.2 Tool: `create_rpmanager_pass`

> **Phase 0 update:** `AddPass()` CONFIRMED (0 args). However, **NEEDS_UI** -- pass creation
> requires the RPManager floater to be open. Without the UI, `AddPass()` runs but
> `getpasscount()` stays 0 (the pass is not registered in the internal data structures).
> The tool MUST open the UI before calling `AddPass()`.

```
Tool name:    create_rpmanager_pass
Parameters:
    name: str = "New Pass"        — pass name
    camera: str = ""              — camera name (optional)
    output_path: str = ""         — output path (optional)
    frame_start: int = 0          — start frame
    frame_end: int = 100          — end frame
Returns:      JSON with new pass index and details
Prerequisites: RPManager installed, UI will be opened automatically
```

**Python signature:**
```python
@mcp.tool()
def create_rpmanager_pass(
    name: str = "New Pass",
    camera: str = "",
    output_path: str = "",
    frame_start: int = 0,
    frame_end: int = 100,
) -> str:
    """Create a new RPManager render pass.

    NOTE: This opens the RPManager UI temporarily because AddPass()
    requires the floater dialog to be open for the pass to register.

    Args:
        name: Name for the new pass.
        camera: Scene camera name to assign (optional).
        output_path: Render output file path (optional).
        frame_start: Start frame of the pass range.
        frame_end: End frame of the pass range.

    Returns:
        JSON with the new pass index and confirmation.
    """
```

**MAXScript template:**
```maxscript
(
    -- MUST open UI for AddPass() to register the pass
    RPMdata.RMopenFloater()
    RPMdata.AddPass()
    local newIdx = RPMdata.getpasscount()  -- now reflects the new pass
    RPMdata.SetPassName newIdx "<name>"
    if "<camera>" != "" do (
        local cam = getNodeByName "<camera>"
        if cam != undefined do RPMdata.captureCamera()
    )
    if "<output_path>" != "" do
        RPMdata.SetPassOutputPath newIdx "<output_path>"
    RPMdata.SetPassRange newIdx <frame_start> <frame_end> 1
    RPMdata.fRefresh()
    "{\"created\": true, \"index\": " + newIdx as string + ", \"name\": \"<name>\"}"
)
```

### 2.3 Tool: `delete_rpmanager_pass`

**Conditional on Phase 0 results.** Same pattern as create.

```
Tool name:    delete_rpmanager_pass
Parameters:
    pass_index: int   — 1-based pass index
Returns:      Confirmation string
Prerequisites: RPManager installed, deletion API confirmed
```

**Fallback:** Same stub approach as create, opening the UI for manual deletion.

---

## Phase 3 — Visibility Sets

**Priority: Medium-High — visibility control is core to multi-pass workflows.**

### 3.1 Tool: `get_rpmanager_visibility_sets`

```
Tool name:    get_rpmanager_visibility_sets
Parameters:   (none)
Returns:      JSON
Prerequisites: RPManager installed
```

**Python signature:**
```python
@mcp.tool()
def get_rpmanager_visibility_sets() -> str:
    """List all RPManager visibility sets and their member objects.

    Visibility sets control which objects are visible in each render pass.
    Returns set names and the objects assigned to each set.

    Returns:
        JSON with visSetCount and array of sets, each with name and members.
    """
```

**MAXScript template (will be refined after Phase 0.4):**
```maxscript
(
    if RPMdata == undefined then (
        "{\"error\": \"RPManager is not installed\"}"
    ) else (
        -- CONFIRMED (Phase 0): Visibility is managed via flat functions, NOT a sub-struct
        -- Functions: writeVisSetData, getVisUndoState, isolateSet, deleteVisSetsHolder
        -- RPMVisSets is NOT a sub-struct — visibility data is managed via functions on RPMdata directly
        local count = vs.getVisSetCount()
        local result = "{\"visSetCount\": " + count as string + ", \"visSets\": ["
        for i = 1 to count do (
            if i > 1 do result += ","
            local setName = vs.getVisSetName i
            local members = vs.getVisSetObjects i  -- expected: array of nodes
            result += "{\"index\": " + i as string
            result += ", \"name\": \"" + (substituteString setName "\"" "\\\"") + "\""
            result += ", \"members\": ["
            for j = 1 to members.count do (
                if j > 1 do result += ","
                result += "\"" + members[j].name + "\""
            )
            result += "]}"
        )
        result += "]}"
        result
    )
)
```

### 3.2 Tool: `set_rpmanager_visibility`

```
Tool name:    set_rpmanager_visibility
Parameters:
    set_index: int             — 1-based visibility set index (required)
    action: str = "add"        — "add" or "remove"
    object_names: list[str]    — list of object names (required)
Returns:      Confirmation string
Prerequisites: RPManager installed, valid set index, objects exist
```

**Python signature:**
```python
@mcp.tool()
def set_rpmanager_visibility(
    set_index: int,
    action: str = "add",
    object_names: list[str] = [],
) -> str:
    """Add or remove objects from an RPManager visibility set.

    Args:
        set_index: 1-based index of the visibility set.
        action: "add" to add objects, "remove" to remove them.
        object_names: List of scene object names.

    Returns confirmation with count of affected objects.
    """
```

**MAXScript template:**
```maxscript
(
    local vs = RPMdata.RPMVisSets
    local objs = #()
    local nameArr = #("<name1>", "<name2>", ...)
    for n in nameArr do (
        local obj = getNodeByName n
        if obj != undefined do append objs obj
    )
    if "<action>" == "add" then
        vs.addObjectsToVisSet objs <set_index>
    else
        vs.removeObjectsFromVisSet objs <set_index>
    RPMdata.UpdateUI()
    "<action>: " + (objs.count as string) + " objects to/from vis set " + <set_index> as string
)
```

---

## Phase 4 — Capture Sets & Material Overrides

**Priority: Medium — important for per-pass look development.**

### 4.1 Tool: `get_rpmanager_capture_sets`

```
Tool name:    get_rpmanager_capture_sets
Parameters:   (none)
Returns:      JSON
Prerequisites: RPManager installed
```

**Python signature:**
```python
@mcp.tool()
def get_rpmanager_capture_sets() -> str:
    """List all RPManager capture property sets with their objects and properties.

    Capture sets store per-pass object property overrides (material, visibility,
    render properties, etc.). Each capture set has a name, list of member
    objects, and the properties being captured.

    Returns:
        JSON with capSetCount and array of sets with name, objects, and properties.
    """
```

**MAXScript template:**
```maxscript
(
    if RPMdata == undefined then (
        "{\"error\": \"RPManager is not installed\"}"
    ) else (
        local cp = RPMdata.RPMCaptureProps  -- or RPMdata.RPMObjProp
        local count = cp.getCapSetCount()
        local result = "{\"capSetCount\": " + count as string + ", \"captureSets\": ["
        for i = 1 to count do (
            if i > 1 do result += ","
            local setName = cp.getCapSetName i
            local objs = cp.getCapSetObjects i
            local props = cp.getCapSetProperties i
            result += "{\"index\": " + i as string
            result += ", \"name\": \"" + (substituteString setName "\"" "\\\"") + "\""
            result += ", \"objects\": ["
            for j = 1 to objs.count do (
                if j > 1 do result += ","
                result += "\"" + objs[j].name + "\""
            )
            result += "], \"properties\": ["
            for j = 1 to props.count do (
                if j > 1 do result += ","
                result += "\"" + (props[j] as string) + "\""
            )
            result += "]}"
        )
        result += "]}"
        result
    )
)
```

### 4.2 Tool: `add_to_rpmanager_capture_set`

```
Tool name:    add_to_rpmanager_capture_set
Parameters:
    set_index: int          — 1-based capture set index (required)
    object_names: list[str] — scene object names to add (required)
Returns:      Confirmation string
Prerequisites: RPManager installed, valid set index
```

**Python signature:**
```python
@mcp.tool()
def add_to_rpmanager_capture_set(
    set_index: int,
    object_names: list[str],
) -> str:
    """Add objects to an RPManager capture property set.

    Args:
        set_index: 1-based index of the capture set.
        object_names: List of scene object names to add.

    Returns confirmation with count of added objects.
    """
```

**MAXScript template:**
```maxscript
(
    local cp = RPMdata.RPMCaptureProps
    local objs = #()
    local nameArr = #("<name1>", "<name2>", ...)
    for n in nameArr do (
        local obj = getNodeByName n
        if obj != undefined do append objs obj
    )
    cp.addObjectsToSet objs <set_index>
    RPMdata.UpdateUI()
    "Added " + (objs.count as string) + " objects to capture set " + <set_index> as string
)
```

### 4.3 Tool: `remove_from_rpmanager_capture_set`

```
Tool name:    remove_from_rpmanager_capture_set
Parameters:
    set_index: int          — 1-based capture set index (required)
    object_names: list[str] — scene object names to remove (required)
Returns:      Confirmation string
Prerequisites: RPManager installed, valid set index
```

Same pattern as 4.2 but calling `cp.removeObjectsFromSet objs <set_index>`.

### 4.4 Tool: `set_rpmanager_material_override`

```
Tool name:    set_rpmanager_material_override
Parameters:
    capture_sets: list[int]      — 1-based capture set indices (required)
    passes: list[int]            — 1-based pass indices (required)
    material_name: str = ""      — scene material name (empty = clear override)
Returns:      Confirmation string
Prerequisites: RPManager installed, material exists in scene (if setting)
```

**Python signature:**
```python
@mcp.tool()
def set_rpmanager_material_override(
    capture_sets: list[int],
    passes: list[int],
    material_name: str = "",
) -> str:
    """Set or clear a material override for capture sets on specific passes.

    This is the core material override mechanism in RPManager: override the
    material for a set of objects (capture set) on specific render passes.
    Pass an empty material_name to clear the override.

    Args:
        capture_sets: List of 1-based capture set indices.
        passes: List of 1-based pass indices to apply the override to.
        material_name: Scene material name to use as override.
                       Empty string clears the override.

    Returns confirmation.
    """
```

**MAXScript template:**
```maxscript
(
    local cp = RPMdata.RPMCaptureProps
    local capSets = #(<cs1>, <cs2>, ...)
    local passArr = #(<p1>, <p2>, ...)
    if "<material_name>" != "" then (
        -- Find material by name in scene materials
        local mat = undefined
        for m in sceneMaterials do (
            if m.name == "<material_name>" do (mat = m; exit)
        )
        if mat == undefined then (
            "Error: material \"<material_name>\" not found in scene"
        ) else (
            cp.captureCapSetMaterial capSets passArr mat
            RPMdata.UpdateUI()
            "Set material override \"<material_name>\" on " + capSets.count as string + " capture sets, " + passArr.count as string + " passes"
        )
    ) else (
        -- Clear override: use rpmdata.RPMObjProp.moAltMat.picked undefined
        -- or cp.captureCapSetMaterial capSets passArr undefined
        cp.captureCapSetMaterial capSets passArr undefined
        RPMdata.UpdateUI()
        "Cleared material override on " + capSets.count as string + " capture sets, " + passArr.count as string + " passes"
    )
)
```

---

## Phase 5 — Pass Scripts

**Priority: Medium — enables per-pass automation hooks.**

### 5.1 Tool: `get_rpmanager_pass_scripts`

```
Tool name:    get_rpmanager_pass_scripts
Parameters:
    pass_index: int   — 1-based pass index (required)
Returns:      JSON with beforeScript, afterScript, enabled
Prerequisites: RPManager installed, valid pass index
```

**Python signature:**
```python
@mcp.tool()
def get_rpmanager_pass_scripts(pass_index: int) -> str:
    """Read the before/after MAXScript hooks for an RPManager pass.

    Each pass can have a "before" script (runs before rendering that pass)
    and an "after" script (runs after). These are commonly used for
    per-pass render settings, object state changes, etc.

    Args:
        pass_index: 1-based index of the pass.

    Returns:
        JSON with beforeScript, afterScript, and scriptsEnabled.
    """
```

**MAXScript template:**

> **NOTE (Phase 0 update):** Uses confirmed function names. GetPassBeforeScript/SetPassBeforeScript
> and GetPassAfterScript/SetPassAfterScript are **headless-safe** (work without UI).

```maxscript
(
    local i = <pass_index>
    local pc = RPMdata.getpasscount()
    if i < 1 or i > pc then (
        "{\"error\": \"Pass index out of range\"}"
    ) else (
        local bScript = RPMdata.GetPassBeforeScript i
        local aScript = RPMdata.GetPassAfterScript i
        local enabled = RPMdata.GetBeforeAfterScriptEnabled i
        -- Escape for JSON
        local safeBefore = substituteString (substituteString bScript "\\" "\\\\") "\"" "\\\""
        safeBefore = substituteString safeBefore "\n" "\\n"
        safeBefore = substituteString safeBefore "\r" ""
        safeBefore = substituteString safeBefore "\t" "\\t"
        local safeAfter = substituteString (substituteString aScript "\\" "\\\\") "\"" "\\\""
        safeAfter = substituteString safeAfter "\n" "\\n"
        safeAfter = substituteString safeAfter "\r" ""
        safeAfter = substituteString safeAfter "\t" "\\t"
        local result = "{"
        result += "\"passIndex\": " + i as string
        result += ", \"passName\": \"" + (RPMdata.GetPassNameFromID i) + "\""
        result += ", \"beforeScript\": \"" + safeBefore + "\""
        result += ", \"afterScript\": \"" + safeAfter + "\""
        result += ", \"scriptsEnabled\": " + (if enabled then "true" else "false")
        result += "}"
        result
    )
)
```

### 5.2 Tool: `set_rpmanager_pass_script`

```
Tool name:    set_rpmanager_pass_script
Parameters:
    pass_index: int               — 1-based pass index (required)
    script_type: str = "before"   — "before" or "after" (required)
    script: str = ""              — MAXScript code to set (empty = clear)
    enabled: bool = True          — enable/disable script execution
Returns:      Confirmation string
Prerequisites: RPManager installed, valid pass index
```

**Python signature:**
```python
@mcp.tool()
def set_rpmanager_pass_script(
    pass_index: int,
    script_type: str = "before",
    script: str = "",
    enabled: bool = True,
) -> str:
    """Set a before or after MAXScript hook on an RPManager pass.

    Use this to automate per-pass actions: change render settings, toggle
    objects, switch materials, etc. The script runs inside 3ds Max's
    MAXScript interpreter before or after the pass renders.

    Args:
        pass_index: 1-based index of the pass.
        script_type: "before" (runs before rendering) or "after" (runs after).
        script: MAXScript code. Empty string clears the script.
        enabled: Whether the script hooks are enabled for this pass.

    Returns confirmation.
    """
```

**MAXScript template:**
```maxscript
(
    local i = <pass_index>
    -- Escape the script string for embedding in MAXScript
    -- (Python side handles escaping into the f-string)
    if "<script_type>" == "before" then
        RPMdata.SetPassBeforeScript i "<escaped_script>"
    else
        RPMdata.SetPassAfterScript i "<escaped_script>"
    RPMdata.SetBeforeAfterScriptEnabled i <enabled_bool>
    RPMdata.fRefresh()
    "Set " + "<script_type>" + " script on pass " + i as string + " (enabled: <enabled>)"
)
```

**Important implementation note:** The `script` parameter will contain arbitrary
MAXScript code with quotes, backslashes, and newlines. The Python side must:
1. Escape backslashes: `\\` -> `\\\\`
2. Escape double quotes: `"` -> `\\\"`
3. Escape newlines: `\n` -> `\\n`
4. The MAXScript `SetPassBeforeScript` stores the raw string, so these escapes
   need to be the MAXScript string escapes, not JSON escapes.

---

## Phase 6 — Batch Operations

**Priority: Medium — pipeline automation power tool.**

### 6.1 Tool: `batch_update_rpmanager_passes`

```
Tool name:    batch_update_rpmanager_passes
Parameters:
    updates: list[dict]   — list of update specs (required)
Returns:      JSON with results per pass
Prerequisites: RPManager installed
```

Each dict in `updates` has:
- `pass_index` (int, required) — 1-based pass index
- `name` (str, optional) — new pass name
- `camera` (str, optional) — camera name
- `output_path` (str, optional) — output file path
- `frame_start` (int, optional) — start frame
- `frame_end` (int, optional) — end frame
- `nth_frame` (int, optional) — nth frame
- `time_type` (int, optional) — time type value

**Python signature:**
```python
@mcp.tool()
def batch_update_rpmanager_passes(updates: list[dict]) -> str:
    """Batch-update properties on multiple RPManager passes at once.

    Use this for pipeline automation — e.g. update all pass output paths
    to a new directory, shift all frame ranges, reassign cameras across
    passes. More efficient than calling set_rpmanager_pass_property
    repeatedly.

    Args:
        updates: List of update dictionaries. Each dict must have:
            - "pass_index" (int): 1-based pass index (required)
            And any combination of optional properties:
            - "name" (str): New pass name
            - "camera" (str): Camera name to assign
            - "output_path" (str): New output file path
            - "frame_start" (int): Start frame
            - "frame_end" (int): End frame
            - "nth_frame" (int): Nth frame
            - "time_type" (int): Time type value

    Returns:
        JSON with results array showing what was updated per pass.
    """
```

**Implementation approach:** Build a single MAXScript block that processes all
updates in sequence, wrapped in `disableSceneRedraw()` / `enableSceneRedraw()`
for performance:

```maxscript
(
    disableSceneRedraw()
    local results = "["
    local pc = RPMdata.getpasscount()

    -- Update 1
    local i = <pass_index_1>
    if i >= 1 and i <= pc then (
        -- apply each provided property (confirmed function names)
        <if name>    RPMdata.SetPassName i "<name>"
        <if output>  RPMdata.SetPassOutputPath i "<output_path>"
        <if range>   RPMdata.SetPassRange i <start> <end> <nth>
        <if timetype> RPMdata.SetPassTimeType i <time_type>
        -- Camera assignment: use captureCamera (exact setter TBD)
        results += "{\"passIndex\": " + i as string + ", \"status\": \"updated\"}"
    ) else (
        results += "{\"passIndex\": " + i as string + ", \"status\": \"out of range\"}"
    )

    -- Update 2 ... N (generated by Python loop)

    results += "]"
    RPMdata.fRefresh()
    enableSceneRedraw()
    redrawViews()
    results
)
```

The Python implementation will loop over the `updates` list and generate the
MAXScript block dynamically, one section per update.

---

## Phase 7 — Utility Tools

### 7.1 Tool: `inspect_rpmanager`

A diagnostic/discovery tool that dumps the raw RPMdata struct for debugging.

```
Tool name:    inspect_rpmanager
Parameters:
    target: str = "passes"   — "passes", "visibility", "capture", "all"
Returns:      JSON diagnostic dump
Prerequisites: RPManager installed
```

This tool is useful for the AI to self-diagnose when something is not working
as expected, similar to the existing `inspect_object` pattern in the codebase.

---

## File Structure

All RPManager tools will live in a single file:

```
src/tools/rpmanager.py
```

### File Layout

```python
"""RPManager (Render Pass Manager) tools for 3ds Max.

Provides read/write access to RPManager render passes, visibility sets,
capture property sets, material overrides, and per-pass scripting hooks.
Requires RPManager plugin to be installed in 3ds Max.
"""

from typing import Optional
from ..server import mcp, client


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _safe(s: str) -> str:
    """Escape a string for safe embedding in MAXScript double-quoted strings."""
    return s.replace("\\", "\\\\").replace('"', '\\"')


def _safe_path(p: str) -> str:
    """Normalize and escape a file path for MAXScript."""
    return _safe(p.replace("\\", "/"))


def _rpm_guard(inner: str) -> str:
    """Wrap MAXScript in an RPManager installation check."""
    return f"""(
        if RPMdata == undefined then (
            "{{\\\"error\\\": \\\"RPManager is not installed or not loaded\\\"}}"
        ) else (
            {inner}
        )
    )"""


# ---------------------------------------------------------------------------
# Phase 1: Pass Reading
# ---------------------------------------------------------------------------

@mcp.tool()
def get_rpmanager_passes() -> str: ...

@mcp.tool()
def get_rpmanager_pass_detail(pass_index: int) -> str: ...


# ---------------------------------------------------------------------------
# Phase 2: Pass Modification
# ---------------------------------------------------------------------------

@mcp.tool()
def set_rpmanager_pass_property(...) -> str: ...

@mcp.tool()
def create_rpmanager_pass(...) -> str: ...      # confirmed: AddPass() + NEEDS_UI

@mcp.tool()
def delete_rpmanager_pass(...) -> str: ...      # confirmed: RMDeleteItem + NEEDS_UI


# ---------------------------------------------------------------------------
# Phase 3: Visibility Sets
# ---------------------------------------------------------------------------

@mcp.tool()
def get_rpmanager_visibility_sets() -> str: ...

@mcp.tool()
def set_rpmanager_visibility(...) -> str: ...


# ---------------------------------------------------------------------------
# Phase 4: Capture Sets & Material Overrides
# ---------------------------------------------------------------------------

@mcp.tool()
def get_rpmanager_capture_sets() -> str: ...

@mcp.tool()
def add_to_rpmanager_capture_set(...) -> str: ...

@mcp.tool()
def remove_from_rpmanager_capture_set(...) -> str: ...

@mcp.tool()
def set_rpmanager_material_override(...) -> str: ...


# ---------------------------------------------------------------------------
# Phase 5: Pass Scripts
# ---------------------------------------------------------------------------

@mcp.tool()
def get_rpmanager_pass_scripts(pass_index: int) -> str: ...

@mcp.tool()
def set_rpmanager_pass_script(...) -> str: ...


# ---------------------------------------------------------------------------
# Phase 6: Batch Operations
# ---------------------------------------------------------------------------

@mcp.tool()
def batch_update_rpmanager_passes(updates: list[dict]) -> str: ...


# ---------------------------------------------------------------------------
# Phase 7: Diagnostics
# ---------------------------------------------------------------------------

@mcp.tool()
def inspect_rpmanager(target: str = "passes") -> str: ...
```

### Registration

Add to `src/server.py` line 13:

```python
from .tools import ..., rpmanager  # noqa: E402, F401
```

---

## Testing Strategy

### Test Prerequisites

1. 3ds Max with RPManager installed and licensed
2. A test scene with:
   - At least 3 render passes configured
   - At least 2 cameras in the scene
   - At least 1 visibility set with members
   - At least 1 capture set with objects
   - At least 1 pass with before/after scripts
   - At least 1 material override set

### Test Matrix

| Test Case | Tool | Validates |
|-----------|------|-----------|
| T1: List passes | `get_rpmanager_passes` | Correct count, all fields populated |
| T2: Pass detail | `get_rpmanager_pass_detail` | All fields, script content, unique ID |
| T3: Set pass name | `set_rpmanager_pass_property(property="name")` | Name changes, round-trip verification |
| T4: Set pass camera | `set_rpmanager_pass_property(property="camera")` | Camera assigned, verified by re-read |
| T5: Set output path | `set_rpmanager_pass_property(property="output_path")` | Path changes, backslash handling |
| T6: Set frame range | `set_rpmanager_pass_property(property="frame_range")` | Range updates, nth frame correct |
| T7: List vis sets | `get_rpmanager_visibility_sets` | Set names and member objects |
| T8: Add to vis set | `set_rpmanager_visibility(action="add")` | Object appears in set members |
| T9: Remove from vis set | `set_rpmanager_visibility(action="remove")` | Object removed from set members |
| T10: List capture sets | `get_rpmanager_capture_sets` | Set names, objects, properties |
| T11: Add to capture set | `add_to_rpmanager_capture_set` | Object appears in set |
| T12: Remove from capture set | `remove_from_rpmanager_capture_set` | Object removed from set |
| T13: Set mat override | `set_rpmanager_material_override` | Material assigned, verified |
| T14: Clear mat override | `set_rpmanager_material_override(material_name="")` | Override cleared |
| T15: Read pass scripts | `get_rpmanager_pass_scripts` | Script content matches what was set |
| T16: Set before script | `set_rpmanager_pass_script(script_type="before")` | Script stored, round-trip OK |
| T17: Set after script | `set_rpmanager_pass_script(script_type="after")` | Script stored, round-trip OK |
| T18: Toggle script enabled | `set_rpmanager_pass_script(enabled=False)` | Enabled flag changes |
| T19: Batch update | `batch_update_rpmanager_passes` | Multiple passes updated in one call |
| T20: No RPManager | Any tool | Returns clean JSON error, no crash |
| T21: Invalid pass index | Any pass tool with bad index | Returns clear error message |
| T22: Invalid camera name | `set_rpmanager_pass_property(property="camera")` | Returns error, does not crash |
| T23: Empty scene | `get_rpmanager_passes` | Returns passCount: 0, empty array |

### Round-Trip Verification Pattern

For every "set" operation, immediately re-read the value to confirm:

```
1. Call get_rpmanager_pass_detail(1) → record original values
2. Call set_rpmanager_pass_property(1, "name", "TestName")
3. Call get_rpmanager_pass_detail(1) → verify name == "TestName"
4. Call set_rpmanager_pass_property(1, "name", <original>) → restore
```

### Edge Cases to Test

- Pass names containing quotes, backslashes, Unicode characters
- Output paths with spaces, network UNC paths (`\\server\share\...`)
- Empty before/after scripts vs scripts with complex MAXScript code
- Camera set to `undefined`/`null` (no camera assigned)
- Capture set with no members
- Visibility set with no members
- Calling tools when RPManager is installed but no passes exist
- Very long script content in before/after scripts

---

## Graceful Degradation

### RPManager Not Installed

Every tool wraps its MAXScript in the `_rpm_guard()` helper which checks
`RPMdata == undefined`. When RPManager is not installed:

```json
{"error": "RPManager is not installed or not loaded"}
```

This is a valid JSON response that the AI can parse and relay to the user
with a helpful message.

### RPManager Installed But Not Initialized

Some RPManager versions require the UI to be opened once before the API is
fully initialized. If `RPMdata` exists but `getpasscount()` fails:

> **Phase 0 update:** Confirmed that many functions need UI open. Use `RPMdata.RMopenFloater()`
> before UI-dependent operations. Note: there is no `RMcloseFloater()` -- the UI stays open.

```maxscript
try (
    RPMdata.getpasscount()
) catch (
    -- Try initializing by opening the UI
    try (RPMdata.RMopenFloater()) catch ()
    -- Retry
    RPMdata.getpasscount()
)
```

### Version Detection

> **Phase 0 update:** Confirmed: `RPMdata.version()` is a function (not a property) returning `"7.8"`.
> `RPMdata.RManVersion` is undefined. Use `RPMdata.version()` only.

Include version info in the `inspect_rpmanager` tool output:

```maxscript
local ver = "unknown"
try (ver = RPMdata.version()) catch ()
```

### Conditional Tool Registration

> **Phase 0 update:** Pass creation (`AddPass()`) and deletion (`RMDeleteItem`) are both
> confirmed to exist. However, both require the RPManager UI to be open for proper operation.
> No stub tools needed -- implement full tools with automatic UI opening via `RMopenFloater()`.
> The `duplicatePass()` function also exists but crashes without UI (needs listbox control).

---

## Implementation Order

### Sprint 1: Foundation (Phase 0 + Phase 1)
1. ~~Run all Phase 0 introspection scripts in a live 3ds Max session~~ **DONE 2026-03-03**
2. ~~Document actual API findings~~ **DONE: `docs/research/rpmanager_introspection.md`**
3. Implement `_safe()`, `_safe_path()`, `_rpm_guard()` helpers
4. Implement `get_rpmanager_passes`
5. Implement `get_rpmanager_pass_detail`
6. Add `rpmanager` import to `src/server.py`
7. Test T1, T2, T20, T21, T23

### Sprint 2: Pass Modification (Phase 2)
1. Implement `set_rpmanager_pass_property` with all property dispatches
2. Implement `create_rpmanager_pass` (API confirmed: `AddPass()` + `RMopenFloater()`)
3. Implement `delete_rpmanager_pass` (API confirmed: `RMDeleteItem` + `RMopenFloater()`)
4. Test T3-T6, T22

### Sprint 3: Visibility & Capture Sets (Phase 3 + Phase 4)
1. Implement `get_rpmanager_visibility_sets`
2. Implement `set_rpmanager_visibility`
3. Implement `get_rpmanager_capture_sets`
4. Implement `add_to_rpmanager_capture_set`
5. Implement `remove_from_rpmanager_capture_set`
6. Implement `set_rpmanager_material_override`
7. Test T7-T14

### Sprint 4: Scripts & Batch (Phase 5 + Phase 6)
1. Implement `get_rpmanager_pass_scripts`
2. Implement `set_rpmanager_pass_script`
3. Implement `batch_update_rpmanager_passes`
4. Test T15-T19

### Sprint 5: Diagnostics & Polish (Phase 7)
1. Implement `inspect_rpmanager`
2. Full integration testing
3. Update `skills/3dsmax-mcp-dev/SKILL.md` with RPManager lessons learned
4. Update tool docstrings with any caveats discovered during testing

---

## Known Risks & Mitigations

### Risk 1: Documentation Site Down
- **Impact:** Cannot verify API beyond what is known from community sources
- **Mitigation:** Phase 0 runtime introspection is comprehensive. Examining
  installed .ms files provides source-level API discovery.
- **Fallback:** If critical APIs are missing, implement read-only tools first
  and expand write tools incrementally as the API is confirmed.

### Risk 2: Pass Creation/Deletion Require UI ~~Not Exposed~~
> **Phase 0 update:** RESOLVED. AddPass() and RMDeleteItem are confirmed.
- **Impact:** Pass creation and deletion work but require RPManager UI to be open
- **Probability:** Confirmed -- headless `AddPass()` runs but pass is not registered
- **Mitigation:** Open RPManager floater automatically via `RPMdata.RMopenFloater()`
  before calling `AddPass()` or `RMDeleteItem`. This adds UI flicker but is reliable.
- **Alternative:** `duplicatePass()` exists but also needs UI (crashes without listbox).

### Risk 3: Version Compatibility
- **Impact:** API may differ between RPManager versions
- **Probability:** Low-Medium
- **Mitigation:** Phase 0 includes version detection. Wrap critical API calls
  in `try/catch` and return version info in error messages. Test on the user's
  specific RPManager version.

### Risk 4: RPMdata Initialization State
> **Phase 0 update:** CONFIRMED. Many functions require UI to be open.
- **Impact:** `RPMdata` exists but many functions silently fail or crash without the UI
- **Probability:** Confirmed -- see UI Dependency Matrix above
- **Mitigation:** Open RPManager floater (`RPMdata.RMopenFloater()`) before UI-dependent
  operations. Property get/set functions (output path, scripts, frame range, etc.) work
  headlessly; pass CRUD and checked-state queries need the UI.

### Risk 5: String Escaping in Pass Scripts
- **Impact:** Complex MAXScript in before/after scripts may contain characters
  that break our JSON serialization or string embedding
- **Probability:** Medium
- **Mitigation:** Multi-layer escaping in Python:
  1. Escape for MAXScript string literal (backslash, quotes)
  2. Escape for JSON output (newlines, tabs)
  3. Test with real-world complex scripts during T15-T18

### Risk 6: Large Scenes Performance
- **Impact:** Scenes with many passes, large visibility sets, or many capture
  set members may produce slow responses
- **Probability:** Low (RPManager typically has < 50 passes)
- **Mitigation:** Wrap batch operations in `disableSceneRedraw()`. Single
  `UpdateUI()` call at the end of batch operations. Use `timeout=120.0` for
  batch tools.

### Risk 7: Capture Set Material Override API Mismatch
> **Phase 0 update:** RPMObjProp is UndefinedClass. The sub-struct model is incorrect.
- **Impact:** Cannot use `RPMCaptureProps` or `RPMObjProp` sub-struct API as originally planned
- **Probability:** Confirmed -- both are UndefinedClass in headless mode
- **Mitigation:** Use top-level RPMdata functions instead: `RPMpreRenderSwapMat`,
  `RPMpostRenderSwapMat`, `setPostMaterial`, `getPreMaterial`, `storePropOverrideData`.
  Further introspection WITH UI OPEN is needed to determine if the sub-structs initialize
  when the floater is active.

---

## Tool Count Summary

| Category | Tools | UI Required | Status |
|----------|-------|-------------|--------|
| Pass Reading | 2 | No (headless-safe) | CONFIRMED |
| Pass Modification | 1 | No (headless-safe) | CONFIRMED |
| Pass Creation | 1 | Yes (NEEDS_UI) | CONFIRMED |
| Pass Deletion | 1 | Yes (NEEDS_UI) | CONFIRMED |
| Visibility Sets | 2 | Needs investigation | API differs from plan |
| Capture Sets | 3 | Needs investigation | RPMObjProp is UndefinedClass |
| Material Overrides | 1 | Needs investigation | RPMObjProp is UndefinedClass |
| Pass Scripts | 2 | No (headless-safe) | CONFIRMED |
| Batch Operations | 1 | Partial | Property sets are headless-safe |
| Diagnostics | 1 | No | CONFIRMED |
| **Total** | **15** | **3+ need UI** | **10 confirmed, 5 need rework** |

---

## Appendix A: RPMdata API Quick Reference (Phase 0 Confirmed)

> Updated 2026-03-03 from live introspection of RPManager 7.8 on 3ds Max 2025.
> See `docs/research/rpmanager_introspection.md` for full details.
> Original pre-research below updated with confirmed signatures.

```
RPMdata (RmanagerDataStruct) — flat struct, 300+ members, NOT nested sub-structs

PASS CRUD (confirmed; NEEDS_UI for create/delete)
├── AddPass()                           — 0 args, NEEDS_UI to register pass
├── RMDeleteItem(index)                 — 1 arg, returns boolean, NEEDS_UI
├── duplicatePass()                     — 0 args, NEEDS_UI (crashes without listbox)
├── SetPassName(index, name)            — headless-safe
├── GetPassNameFromID(index) -> string  — headless-safe (fails without passes)
├── getpasscount() -> int               — headless-safe
├── movePassUpDown(...)                 — exists, not tested
├── invertPasses(...)                   — exists, not tested

PASS PROPERTIES (all headless-safe, confirmed)
├── GetPassOutputPath(index) -> string
├── GetPassBeforeScript(index) -> string
├── SetPassBeforeScript(index, script)
├── GetPassAfterScript(index) -> string
├── SetPassAfterScript(index, script)
├── GetPassTimeType(index) -> int
├── SetPassTimeType(index, type)
├── GetPassRange(index) -> array
├── SetPassRange(index, start, end, nth?)
├── GetPassVisSetName(index) -> string
├── GetPassBGColor(index) -> color
├── SetPassColor(index, color)
├── GetBeforeAfterScriptEnabled(index) -> bool
├── SetBeforeAfterScriptEnabled(index, bool)

PASS SELECTION/CHECK (NEEDS_UI)
├── GetPassSelection(1+)               — fails headlessly
├── GetPassChecked(1)                   — fails headlessly
├── getCheckedPasses(1)                 — needs 1 arg (not 0!)

RENDERING (confirmed exist, UI dependency untested)
├── renderLocally(...)
├── submitChecked(...)
├── submitSelected(...)
├── previewChecked(...)
├── previewSelected(...)
├── previewLocally(...)

RENDERERS
├── SetRenderer(index, renderer)
├── getrenderer(index) -> renderer|undefined
├── copyRenderer(...), pasteRenderer(...), autoBuildRenderers(...)

CAMERAS (confirmed exist)
├── captureCamera(...)
├── GetAllCameras(...)
├── RMfindCamera(...)
├── getpasscamera(index) -> node|undefined

STATE (confirmed exist)
├── captureStateSet(...), restoreStateSet(...), getallstatesets(...)
├── captureBackground(...), captureExposure(...)

VISIBILITY (flat functions, NOT sub-struct — CONFIRMED Phase 0)
├── writeVisSetData(...)
├── getVisUndoState(...)
├── isolateSet(...)
├── deleteVisSetsHolder(...)
├── UpdateLayerArray(...)
├── CA_redefineVis(...)

MATERIALS (flat functions, NOT sub-struct)
├── RPMpreRenderSwapMat(...), RPMpostRenderSwapMat(...)
├── setPostMaterial(...), getPreMaterial(...), putMatToSlate(...)

OBJECT PROPERTIES (flat functions; RPMObjProp is UndefinedClass)
├── getObjPropPrefsData(...), setObjPropPrefsData(...)
├── storePropOverrideData(...), getPerObjectPreviewData(...)

UI
├── RMopenFloater()                     — opens RPManager dialog
├── fRefresh()                          — refreshes UI

MISC
├── version() -> "7.8"                  — headless-safe (function, not property)
├── passthenumb -> int (current pass unique ID)
```

## Appendix B: Naming Conventions

All tool names follow the existing codebase pattern:
- Prefix: `get_rpmanager_`, `set_rpmanager_`, `add_to_rpmanager_`, etc.
- Verb-first where possible
- Snake_case throughout
- Module name: `rpmanager` (matches the import in `server.py`)
- All parameters use snake_case
- 1-based indexing for pass/set indices (matches MAXScript convention)
