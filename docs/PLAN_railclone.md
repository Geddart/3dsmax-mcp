# RailClone Pro MCP Tools - Implementation Plan

## Table of Contents

1. [Overview](#1-overview)
2. [Research Summary: RailClone MAXScript API](#2-research-summary-railclone-maxscript-api)
3. [Phase 0/1: Runtime Introspection (Discovery Scripts)](#3-phase-01-runtime-introspection-discovery-scripts) -- COMPLETED
4. [Phase 2: Tool Architecture](#4-phase-2-tool-architecture)
5. [Phase 3: Proposed Tools](#5-phase-3-proposed-tools)
6. [Phase 4: High-Level Presets](#6-phase-4-high-level-presets)
7. [Phase 5: Style Library Integration](#7-phase-5-style-library-integration)
8. [Implementation Order](#8-implementation-order)
9. [Testing Strategy](#9-testing-strategy)
10. [Known Risks and Mitigations](#10-known-risks-and-mitigations)
11. [Reference: RailClone Concepts](#11-reference-railclone-concepts)
12. [Reference: Confirmed API Surface](#12-reference-confirmed-api-surface)
13. [Reference: Complete Introspected Property List](#13-reference-complete-introspected-property-list)
14. [Sources](#14-sources)

---

## 1. Overview

RailClone Pro by iToo Software is a parametric modeling plugin for 3ds Max that creates complex arrays of objects along splines. It is the sibling product to Forest Pack (same developer), and the existing `scatter_forest_pack` tool in `src/tools/scattering.py` provides the architectural template.

**Goal**: Extend the 3dsmax-mcp server with tools that allow AI agents to create, configure, and manage RailClone objects programmatically. The tools will follow the same pattern as Forest Pack: build MAXScript strings, send via `client.send_command()`, parse JSON responses.

**Key Constraint**: Unlike Forest Pack, RailClone's MAXScript API is significantly more limited. The style editor is primarily GUI-driven, and many operations that seem scriptable are actually locked behind the internal node graph. This plan accounts for that by emphasizing two strategies:
1. **Library-first**: Load pre-built styles from the RailClone library, then modify exposed parameters
2. **Parameter-based**: Create objects and manipulate the subset of properties accessible via MAXScript

**File target**: `src/tools/railclone.py`, imported in `src/server.py` alongside existing tools.

---

## 2. Research Summary: RailClone MAXScript API

### 2.1 Confirmed Class Name

The MAXScript class is `RailClone_Pro`. Creation follows the standard 3ds Max pattern:
```maxscript
rc = RailClone_Pro name:"MyRailClone"
```

### 2.2 Confirmed Scriptable Properties

**Base Object Assignment** (spline paths):
```maxscript
-- Assign a spline to base object slot 1
$.banode[1] = $SplineName

-- Batch assign to selection
for obj in selection do obj.banode[1] = $SplineName
```

The `banode` property is an indexed array of base objects (splines). Index 1 is the primary path spline. For A2S generators, additional indices hold the Y spline.

**Style/Library Loading** (added in RailClone 6):
```maxscript
-- Load a library preset by its path in the library browser
$.railclone.loadLibraryItemByPath "\\RailClone Library\\Architecture\\Exterior\\Railings\\Handrail 1"
-- Returns integer (1 = success, confirmed via introspection)
-- NOTE: path uses backslashes, style name must match library browser exactly

-- Get the currently loaded style path
$.style  -- NOTE: remains empty string after loading; style data is stored internally
```

> **Introspection correction:** Return value is 1 on success (not 0 as originally documented). The `$.style` property does NOT reflect the loaded library path -- it remains empty string. Style data is stored in the internal graph.

**Style Description**:
```maxscript
$.railclone.setStyleDesc("description text")
$.railclone.getStyleDesc()
-- Batch
for obj in selection do (obj.railclone.setStyleDesc("my style"))
```

**Exposed Parameters** (Numeric node system):
Parameters exposed via Numeric nodes in the Style Editor are accessible as parallel arrays:
```maxscript
-- Core identification
$.paid       -- #("id1", "id2")       -- unique identifiers
$.paname     -- #("Distance", "Y Offset") -- display names
$.patype     -- #(3, 3)               -- type enum: 0=int, 1=float, 3=worldUnits (others TBD)
$.padesc     -- #("...", "...")        -- descriptions/tooltips

-- Value arrays (by type)
$.paintval   -- #(0, 0)               -- integer values
$.paintmin   -- integer array          -- min constraint for int params
$.paintmax   -- integer array          -- max constraint for int params
$.pafloatval -- #(0.0, 0.0)           -- float values
$.pafloatmin -- float array            -- min constraint for float params
$.pafloatmax -- float array            -- max constraint for float params
$.paunitval  -- #(10.0, 5.0)          -- worldUnit values
$.paunitmin  -- worldUnits array       -- min constraint for unit params
$.paunitmax  -- worldUnits array       -- max constraint for unit params
$.paboolval  -- boolean array          -- boolean values
$.pastrval   -- string array           -- string values

-- Metadata
$.palimit    -- boolean array          -- whether min/max constraints are active
$.paselector -- string array           -- selector binding (if any)
$.pamodified -- boolean array          -- whether param has been changed from default
$.paretain   -- integer array          -- retain setting

-- Set a parameter by array index
$.paunitval[2] = 10
```

> **Introspection note:** 19 pa* arrays confirmed (vs. 7 originally documented). The additional arrays for min/max constraints and boolean/string value types expand what can be queried and set programmatically.

**Proxy Cache Management** (via `.railclone` interface):
```maxscript
$.railclone.setProxyMode 0 ""                           -- Disabled
$.railclone.setProxyMode 1 ""                           -- Embedded (returns size)
$.railclone.setProxyMode 2 "proxyFileName.rcproxy"      -- External file
```

> **Introspection note:** `setProxyMode` is on the `.railclone` interface, not directly on the object. Also confirmed: `proxymode` (integer) and `proxyfile` (filename) are direct properties for reading proxy state.

**Instantiation** (RailClone Tools):
```maxscript
-- Create instances for selected RailClone objects
RailClone_Pro.global.Instantiate mode layerName autoDelete separatedMeshes forceInstances
-- mode: 0=individual, 1=grouped, 2=layer-based
-- Example:
RailClone_Pro.global.Instantiate 0 "rc_instances" true true false true

-- Delete instances
RailClone_Pro.global.InstantiateDelete()

-- Enable display
RailClone_Pro.global.InstantiateEnable()
```

**Data Export**:
```maxscript
RailClone_Pro.global.exportData "c:\export\test" "" 0
-- or legacy:
RailClone_pro.RailClone.exportData "c:\\tmp\\data.xml" "geomID colorID size"
-- format: 0=Standard, 1=Unity
```

**RailClone Lister**:
```maxscript
RailClone_Pro.openLister()
```

### 2.3 What Is NOT Directly Scriptable

> **Confirmed by introspection (2026-03-03):** The segment arrays (s*) are populated by the internal style graph. While 37 segment arrays exist and are readable, they cannot be used to construct styles programmatically.

Based on research and confirmed by introspection, these operations require the Style Editor GUI and cannot be performed purely via MAXScript:

- **Creating/wiring nodes** in the style graph (generators, segments, operators)
- **Assigning geometry to segment slots** (Default, Start, Corner, End, Evenly) -- these are internal node connections
- **Changing generator type** (L1S vs A2S) after creation -- this is part of the style
- **Adding operators** (Compose, Sequence, Random, Selector, Transform, Mirror, etc.)
- **Modifying segment deform/slice/bend settings** individually
- **Creating conditional rules** for segment selection

This is the critical difference from Forest Pack, where `cobjlist`, `geomlist`, `namelist`, etc. allow full programmatic control. RailClone's style system is an internal node graph that MAXScript can load but not construct.

### 2.4 Implications for Tool Design

> **VALIDATED by introspection (2026-03-03):** Library-first approach confirmed working. `loadLibraryItemByPath` returns 1 on success. `banode[1] = splineObject` confirmed. 19 pa* arrays available for parameter manipulation.

The tool strategy must be **library-centric**:
1. Load pre-built styles from the RailClone library (hundreds of presets available)
2. Assign spline paths via `banode`
3. Tweak exposed parameters via the `pa*` arrays (19 arrays confirmed, including min/max constraints and bool/string types)
4. Use introspection to report what parameters are available

For users who need custom styles, the workflow would be:
1. Create the style manually in the Style Editor (or use a preset as a starting point)
2. Expose desired parameters as Numeric nodes
3. Use MCP tools to assign paths and adjust exposed parameters

---

## 3. Phase 0/1: Runtime Introspection (Discovery Scripts)

> **Phase 0 Status:** COMPLETED 2026-03-03
> **Full results:** `docs/research/railclone_introspection.md`
> **Key findings:**
> - Class confirmed: `RailClone_Pro` (GeometryClass), 166 properties
> - loadLibraryItemByPath WORKS (returned 1) -- library-first approach is viable
> - banode[1] = splineObject WORKS -- spline assignment confirmed
> - Exposed parameter arrays confirmed: pa* (paid, patype, paname, paintval, pafloatval, paunitval, paboolval, pastrval, etc.)
> - Additional classes: RailClone_Color (textureMap), RC_Slice (modifier), RC_Spline (modifier)
> - RailClone_Exporter and RailClone_Importer found -- .rcproxy export/import possible
> - Segment arrays (s*) are extensive but likely read-only from MAXScript

All discovery scripts below have been executed in a live 3ds Max 2025 session (PID 91996) with RailClone Pro installed. Each script includes a result summary.

### 3.1 Class Discovery

> **Result:** Found 7 classes -- RailClone_Pro (GeometryClass), RailClone_Tools (UtilityPlugin), RailClone_Exporter, RailClone_Importer, RailClone_Color (textureMap), RC_Slice (modifier), RC_Spline (modifier).

```maxscript
-- Find the exact class name
showClass "Rail*"
showClass "RC_*"
showClass "railclone*"
showClass "RailClone*"

-- Check if RailClone_Pro is available
try (
    local testClass = RailClone_Pro
    print ("RailClone_Pro is available: " + (testClass as string))
) catch (
    print "RailClone_Pro class not found"
)
```

### 3.2 Property Enumeration

> **Result:** 166 properties found. Organized into: core (spline, seed, style, etc.), base object arrays (ba*), exposed parameter arrays (pa*), segment arrays (s*), display/render, and v1 legacy properties. Full listing in `docs/research/railclone_introspection.md` Section 2.

```maxscript
-- Create a temporary RailClone object and dump all properties
(
    local rc = RailClone_Pro()
    local ss = stringstream ""
    showProperties rc to:ss
    seek ss 0
    local result = ""
    while not (eof ss) do (
        result += (readline ss) + "\n"
    )
    delete rc
    result
)
```

### 3.3 Interface Discovery

> **Result:** Three interfaces found -- `global` (static: RegisterEngine, version, SetEngineFeatures, Instantiate, InstantiateDelete, InstantiateEnable, exportData), `railclone` (instance: segmentsUpdate, getStyleDesc, setStyleDesc, loadLibraryItemByPath, etc.), `scatalog` (browser: openBrowser, closeBrowser, refresh, getMacroCount, evalMacro, etc.).

```maxscript
-- List all interfaces on a RailClone object
(
    local rc = RailClone_Pro()
    local ifaces = getInterfaces rc
    local result = ""
    for iface in ifaces do (
        result += (iface as string) + "\n"
        -- Try to get interface methods
        try (
            local methods = getInterfaceMethods iface
            if methods != undefined do (
                for m in methods do
                    result += "  method: " + (m as string) + "\n"
            )
        ) catch ()
    )
    delete rc
    result
)
```

### 3.4 The `.railclone` Interface

> **Result:** Confirmed. `rc.railclone` exists. Methods: segmentsUpdate(), getStyleDesc(), setStyleDesc(), resetCreatedVersion(), setCreatedVersion(), upgradeFromVersion(), setNodesCache(), setProxyMode(), loadLibraryItemByPath(). `RailClone_Pro.global` also confirmed with Instantiate/InstantiateDelete/InstantiateEnable/exportData/RegisterEngine/version/SetEngineFeatures.

```maxscript
-- Specifically probe the .railclone sub-interface
(
    local rc = RailClone_Pro()
    local result = ""

    -- Check if .railclone exists
    try (
        local rcInterface = rc.railclone
        result += "rc.railclone exists: " + (rcInterface as string) + "\n"

        -- Enumerate methods
        local ss = stringstream ""
        showMethods rcInterface to:ss
        seek ss 0
        while not (eof ss) do (
            result += "  " + (readline ss) + "\n"
        )
    ) catch (
        result += "rc.railclone interface not accessible\n"
    )

    -- Check .global static interface
    try (
        result += "RailClone_Pro.global: " + (RailClone_Pro.global as string) + "\n"
        local ss2 = stringstream ""
        showMethods RailClone_Pro.global to:ss2
        seek ss2 0
        while not (eof ss2) do (
            result += "  global." + (readline ss2) + "\n"
        )
    ) catch (
        result += "RailClone_Pro.global not accessible\n"
    )

    delete rc
    result
)
```

### 3.5 Base Object (`banode`) Exploration

> **Result:** `rc.banode[1] = splineObject` WORKS. banode.count starts at 0, becomes 1 after assignment. Full ba* arrays confirmed: baid, batype, baname, banode, bafull, bastart, balength, badesc (all start empty, populated by library loading).

```maxscript
-- Test base object assignment with a real spline
(
    local sp = SplineShape name:"TestSpline"
    addNewSpline sp
    addKnot sp 1 #smooth #curve [0,0,0]
    addKnot sp 1 #smooth #curve [100,0,0]
    addKnot sp 1 #smooth #curve [200,0,50]
    updateShape sp

    local rc = RailClone_Pro name:"TestRC"

    -- Probe banode
    local result = ""
    result += "banode class: " + ((classOf rc.banode) as string) + "\n"
    result += "banode count: " + (rc.banode.count as string) + "\n"

    -- Try assignment
    rc.banode[1] = sp
    result += "After assignment - banode[1]: " + ((rc.banode[1]) as string) + "\n"

    -- Check for other base object properties
    local propNames = getPropNames rc
    for p in propNames do (
        local pStr = toLower (p as string)
        if (findString pStr "ba" != undefined) or
           (findString pStr "spline" != undefined) or
           (findString pStr "path" != undefined) or
           (findString pStr "base" != undefined) or
           (findString pStr "surf" != undefined) do (
            local val = undefined
            try (val = getProperty rc p) catch ()
            result += "  " + (p as string) + " = " + (val as string) + "\n"
        )
    )

    delete rc
    delete sp
    result
)
```

### 3.6 Full Property Dump with Types

> **Result:** 166 properties enumerated with types and defaults. Includes 37 s* (segment) arrays, 19 pa* (exposed param) arrays, 8 ba* (base object) arrays, 17 display/render properties, and 11 v1 legacy properties. Full listing in `docs/research/railclone_introspection.md` Section 2.

```maxscript
-- Exhaustive property dump with read/write testing
(
    local rc = RailClone_Pro name:"TestRC_Dump"
    local propNames = #()
    try (propNames = makeuniquearray (getPropNames rc)) catch ()

    local result = "Property count: " + (propNames.count as string) + "\n\n"
    for p in propNames do (
        local val = undefined
        local valStr = "???"
        local typeStr = "???"
        local writable = false
        try (
            val = getProperty rc p
            valStr = val as string
            typeStr = (classOf val) as string
            if valStr.count > 100 do valStr = (substring valStr 1 100) + "..."
        ) catch (
            valStr = "<read error>"
        )
        -- Test writability (only for safe-looking values)
        try (
            if typeStr == "Integer" or typeStr == "Float" or typeStr == "BooleanClass" do (
                local original = val
                setProperty rc p val
                writable = true
            )
        ) catch ()

        result += (p as string) + " : " + typeStr + " = " + valStr
        if writable do result += " [RW]"
        result += "\n"
    )
    delete rc
    result
)
```

### 3.7 Library Path Discovery

> **Result:** `loadLibraryItemByPath` returned 1 (success) for `"\\RailClone Library\\Architecture\\Exterior\\Railings\\Handrail 1"`. After loading: paname.count = 0 (this style had no exposed parameters). The `style` property remained empty string (style data is stored internally, not in this field). Path format uses backslashes: `"\\RailClone Library\\Category\\SubCategory\\StyleName"`.

```maxscript
-- Discover available library paths
(
    local rc = RailClone_Pro name:"TestRC_Lib"
    local result = ""

    -- Try to get style info
    try (
        result += "Current style: " + (rc.style as string) + "\n"
    ) catch (
        result += "style property not accessible\n"
    )

    -- Try loading a known library item
    try (
        local loadResult = rc.railclone.loadLibraryItemByPath "\\RailClone Library\\Architecture\\Exterior\\Railings\\Vynil Handrail 1"
        result += "loadLibraryItemByPath result: " + (loadResult as string) + "\n"
        result += "Style after load: " + (rc.style as string) + "\n"

        -- Check what parameters are now exposed
        result += "paname: " + (rc.paname as string) + "\n"
        result += "patype: " + (rc.patype as string) + "\n"
    ) catch (
        result += "Library loading failed\n"
    )

    delete rc
    result
)
```

### 3.8 Segment and Generator Property Discovery

> **Result:** 37 segment arrays (s*) found after loading a style -- sid, sname, sflags, sobjref, sobjoffset, sobjnodetm, sobjnode, sobjmtl, spos, srot, ssca, sxalign/syalign/szalign, spadin/spadout/spadtop/spadbottom, sfixedsize, sinstance, sbend, sslice, snesting, srandtrans/rot/scale/mat, srt1/2, srr1/2, srs1/2, smaterial, smapping, smapreal, smapchans, smapsize/off/rotx/y/z. These are likely read-only from MAXScript (populated by the style graph internally).

```maxscript
-- After loading a style, probe for generator/segment-related properties
(
    local rc = RailClone_Pro name:"TestRC_Seg"

    -- Load a known style first
    try (rc.railclone.loadLibraryItemByPath "\\RailClone Library\\Architecture\\Exterior\\Fences\\Metal Fence 1") catch ()

    local propNames = #()
    try (propNames = makeuniquearray (getPropNames rc)) catch ()

    local result = ""
    -- Filter for potentially interesting properties
    local keywords = #("seg", "gen", "node", "geom", "obj", "slot", "default", "corner", "start", "end", "even", "spacing", "size", "offset", "seed", "icon", "display", "style", "update")
    for p in propNames do (
        local pLower = toLower (p as string)
        local match = false
        for kw in keywords do (
            if findString pLower kw != undefined do match = true
        )
        if match do (
            local val = undefined
            try (val = getProperty rc p) catch ()
            result += (p as string) + " = " + (if val != undefined then (val as string) else "<undefined>") + "\n"
        )
    )
    delete rc
    result
)
```

### 3.9 Installed Script Discovery

> **Result:** Not yet executed. To be run if library XML parsing (Section 7.1 Option A) is pursued.

```maxscript
-- Look for RailClone .ms files in the 3ds Max installation
(
    local maxRoot = getDir #maxroot
    local pluginsDir = getDir #plugins
    local scriptsDir = getDir #scripts
    local userScriptsDir = getDir #userscripts
    local startupDir = getDir #startupScripts

    local result = ""
    result += "maxroot: " + maxRoot + "\n"
    result += "plugins: " + pluginsDir + "\n"
    result += "scripts: " + scriptsDir + "\n"
    result += "userscripts: " + userScriptsDir + "\n"
    result += "startup: " + startupDir + "\n\n"

    -- Search for RailClone related files
    local dirs = #(maxRoot, pluginsDir, scriptsDir, userScriptsDir, startupDir)
    for d in dirs where d != undefined do (
        local files = getFiles (d + "\\*railclone*")
        local files2 = getFiles (d + "\\*RailClone*")
        local files3 = getFiles (d + "\\*iToo*")
        local allFiles = join files files2
        allFiles = join allFiles files3
        for f in allFiles do
            result += "  " + f + "\n"
    )
    result
)
```

---

## 4. Phase 2: Tool Architecture

### 4.1 File Structure

Create `src/tools/railclone.py` following the same pattern as `src/tools/scattering.py`:

```python
"""RailClone Pro tools for parametric modeling along splines in 3ds Max."""

from __future__ import annotations

from ..server import mcp, client


def _safe_name(name: str) -> str:
    return name.replace("\\", "\\\\").replace('"', '\\"')


def _name_array(names: list[str]) -> str:
    return "#(" + ", ".join(f'"{_safe_name(name)}"' for name in names) + ")"
```

### 4.2 Registration

Add `railclone` to the import line in `src/server.py`:

```python
from .tools import execute, scene, objects, materials, render, viewport, identify, transform, hierarchy, modifiers, selection, clone, scene_manage, visibility, inspect, build, grid, floor_plan, scene_query, effects, material_ops, state_sets, data_channel, wire_params, controllers, scattering, railclone  # noqa: E402, F401
```

### 4.3 Error Handling Pattern

Every tool should:
1. Check that `RailClone_Pro` class exists (plugin installed check)
2. Validate referenced objects exist in scene
3. Return JSON with error details on failure
4. Return JSON summary on success

```python
# Standard error check pattern (inside MAXScript):
"""
local rcClass = undefined
try (rcClass = RailClone_Pro) catch ()
if rcClass == undefined then (
    "{\\"error\\":\\"RailClone Pro is not installed (RailClone_Pro unavailable).\\"}"
) else (
    -- ... actual logic ...
)
"""
```

---

## 5. Phase 3: Proposed Tools

### 5.1 `create_railclone` -- Core Creation Tool

**Purpose**: Create a RailClone Pro object and assign path spline(s).

**Parameters**:
| Name | Type | Default | Description |
|------|------|---------|-------------|
| `path_splines` | `list[str]` | required | Scene spline names for path(s). First = primary (X), second = Y (for A2S) |
| `name` | `str` | `"RailClone001"` | Object name |
| `icon_size_cm` | `float` | `30.0` | Icon display size in cm |
| `seed` | `int` | `12345` | Random seed |

**MAXScript logic**:
```maxscript
local rc = RailClone_Pro name:"<name>"
rc.banode[1] = getNodeByName "<spline1>"
-- if second spline provided:
rc.banode[2] = getNodeByName "<spline2>"
-- return JSON summary
```

**Returns**: JSON with name, class, assigned spline count, base position.

### 5.2 `create_railclone_from_style` -- Library Style Creation

**Purpose**: Create a RailClone object pre-loaded with a style from the library browser.

**Parameters**:
| Name | Type | Default | Description |
|------|------|---------|-------------|
| `style_path` | `str` | required | Library path (e.g. `"\RailClone Library\Architecture\Exterior\Fences\Metal Fence 1"`) |
| `path_splines` | `list[str]` | `[]` | Optional spline(s) to assign immediately |
| `name` | `str` | `"RailClone001"` | Object name |

**MAXScript logic**:
```maxscript
local rc = RailClone_Pro name:"<name>"
local loadResult = rc.railclone.loadLibraryItemByPath "<style_path>"
-- NOTE: loadResult == 1 means success (confirmed by introspection)
if loadResult != 1 then (
    delete rc
    "{\\"error\\":\\"Failed to load style: <style_path>\\"}"
) else (
    -- Assign splines if provided
    for i = 1 to splineNames.count do (
        local sp = getNodeByName splineNames[i]
        if sp != undefined do rc.banode[i] = sp
    )
    -- Return JSON with style info + exposed parameters
    -- NOTE: rc.style remains "" after load; use getStyleDesc() for description
    -- NOTE: paname.count may be 0 if style has no exposed Numeric nodes
)
```

**Returns**: JSON with name, loaded style path, exposed parameter names/types, assigned spline count.

### 5.3 `set_railclone_paths` -- Assign/Change Path Splines

**Purpose**: Assign or reassign spline paths to an existing RailClone object.

**Parameters**:
| Name | Type | Default | Description |
|------|------|---------|-------------|
| `name` | `str` | required | RailClone object name |
| `path_splines` | `list[str]` | required | Spline names to assign (index 1, 2, ...) |

**MAXScript logic**:
```maxscript
local rc = getNodeByName "<name>"
for i = 1 to splineNames.count do (
    local sp = getNodeByName splineNames[i]
    if sp != undefined do rc.banode[i] = sp
)
```

### 5.4 `set_railclone_parameters` -- Set Exposed Parameters

**Purpose**: Modify parameters that have been exposed via Numeric nodes in the style.

**Parameters**:
| Name | Type | Default | Description |
|------|------|---------|-------------|
| `name` | `str` | required | RailClone object name |
| `parameters` | `dict[str, float]` | required | Map of parameter name to value |

**MAXScript logic**:
```maxscript
local rc = getNodeByName "<name>"
-- For each parameter name, find its index in paname array
local paramNames = rc.paname
for paramKey in parameterKeys do (
    local idx = findItem paramNames paramKey
    if idx != 0 do (
        local ptype = rc.patype[idx]
        case ptype of (
            0: rc.paintval[idx] = <value> as integer
            1: rc.pafloatval[idx] = <value> as float
            3: rc.paunitval[idx] = <value>
            -- Additional types confirmed by introspection:
            -- paboolval for boolean params, pastrval for string params
            -- palimit[idx] indicates if min/max constraints are active
        )
    )
)
```

**Returns**: JSON with updated parameters and their new values.

### 5.5 `get_railclone_info` -- Inspect RailClone Object

**Purpose**: Get comprehensive information about an existing RailClone object including its style, parameters, base objects, and display state.

**Parameters**:
| Name | Type | Default | Description |
|------|------|---------|-------------|
| `name` | `str` | required | RailClone object name |

**MAXScript logic**:
```maxscript
local rc = getNodeByName "<name>"
-- Collect:
--   rc.style (loaded library path)
--   rc.paname, rc.patype, rc.paunitval, rc.pafloatval, rc.paintval
--   rc.banode (assigned splines)
--   rc.railclone.getStyleDesc()
--   General object properties (position, bounds, face count)
```

**Returns**: Rich JSON with:
- Object name, class, position, bounding box
- Current style path and description
- List of exposed parameters with names, types, and current values
- List of assigned base objects (splines)
- Display/proxy state

### 5.6 `set_railclone_display` -- Control Display and Proxy Settings

**Purpose**: Configure viewport display and proxy cache.

**Parameters**:
| Name | Type | Default | Description |
|------|------|---------|-------------|
| `name` | `str` | required | RailClone object name |
| `proxy_mode` | `int` | `None` | 0=disabled, 1=embedded, 2=external |
| `proxy_file` | `str` | `""` | External proxy filename (for mode 2) |

**MAXScript logic**:
```maxscript
local rc = getNodeByName "<name>"
rc.railclone.setProxyMode <mode> "<proxy_file>"
-- Additional display properties confirmed by introspection:
-- rc.vmesh (integer), rc.adaptfaces (integer), rc.cloudens (integer)
-- rc.rmesh (integer), rc.rendermode (boolean), rc.maxseg (integer)
-- rc.maxfaces (float), rc.proxymode (integer), rc.proxyfile (filename)
-- rc.autoupdate (boolean), rc.disabled (boolean)
```

### 5.7 `railclone_instantiate` -- Convert to Instances

**Purpose**: Convert RailClone objects to real instanced geometry.

**Parameters**:
| Name | Type | Default | Description |
|------|------|---------|-------------|
| `names` | `list[str]` | required | RailClone object names to instantiate |
| `mode` | `int` | `0` | 0=individual, 1=grouped, 2=layer |
| `layer_name` | `str` | `"rc_instances"` | Target layer (for mode 2) |
| `auto_delete` | `bool` | `True` | Remove previous instances |
| `separated_meshes` | `bool` | `True` | Generate distinct meshes for non-instanced segments |
| `force_instances` | `bool` | `False` | Maximize instance generation |

**MAXScript logic**:
```maxscript
select (for n in names collect getNodeByName n)
RailClone_Pro.global.Instantiate <mode> "<layer>" <autoDelete> <separated> <force>
```

---

## 6. Phase 4: High-Level Presets

These tools combine spline creation + RailClone + library loading into single convenient operations. They depend on discovering which library paths exist at runtime.

### 6.1 `create_railclone_fence`

**Purpose**: Create a fence along a path with a single call.

**Strategy**:
1. Take a list of points or existing spline name
2. If points provided, create a SplineShape
3. Create RailClone, load a fence style from library
4. Assign spline, adjust spacing parameter if exposed

**Parameters**:
| Name | Type | Default | Description |
|------|------|---------|-------------|
| `spline_name` | `str` | `None` | Existing spline name (mutually exclusive with `points`) |
| `points` | `list[list[float]]` | `None` | [[x,y,z], ...] to auto-create a spline |
| `fence_style` | `str` | `"Metal Fence 1"` | Short name looked up from known fence style paths |
| `name` | `str` | `"Fence001"` | Output object name |

**Requires**: A curated map of known fence style paths (built during Phase 1 library enumeration).

### 6.2 `create_railclone_railing`

**Purpose**: Create handrails along a path.

**Similar to fence** but uses railing-category library styles.

### 6.3 `create_railclone_wall`

**Purpose**: Create a wall following a path.

**Uses**: Architecture > Walls category from the RailClone library.

### 6.4 `create_railclone_array`

**Purpose**: Create an evenly-spaced array of objects along a path.

**Strategy**: If simple enough (single segment, evenly spaced), this could potentially work without a library style by:
1. Creating a RailClone object
2. Loading a minimal "repeat" style
3. Adjusting the spacing parameter

**Falls back to**: Using a generic "repeat segment" library style if custom node creation is not possible.

---

## 7. Phase 5: Style Library Integration

### 7.1 Library Enumeration Tool

**`list_railclone_styles`**: Browse the RailClone library.

**Challenge**: There is no known MAXScript API to enumerate library contents programmatically. The library is stored as XML files.

**Strategy options** (to be validated during introspection):

**Option A - XML parsing**: Find the library XML index files on disk and parse them:
```maxscript
-- Locate iToo library installation
local rcLibPath = (getDir #maxroot) + "\\..\\RailClone\\Library\\"
-- Parse index.xml to enumerate styles
```

**Option B - Known path catalog**: Maintain a hardcoded catalog of common library paths (populated by running introspection scripts). This is fragile but practical.

**Option C - Filesystem scan**: Look for `.max` scene template files in the RailClone library directories.

### 7.2 Style Application

**`apply_railclone_style`**: Apply a different style to an existing RailClone object.

```maxscript
local rc = getNodeByName "<name>"
local result = rc.railclone.loadLibraryItemByPath "<style_path>"
-- Re-assign splines if needed (style change may reset base objects)
```

**Important note**: Changing styles may reset base object assignments. The tool should optionally re-assign splines after loading.

---

## 8. Implementation Order

### Phase 1: Discovery (Week 1)
**Goal**: Run all introspection scripts from Section 3 in a live 3ds Max session.

Deliverables:
- [ ] Confirmed class name and creation syntax
- [ ] Full property dump with types and read/write status
- [ ] Interface method list (`$.railclone.*`, `RailClone_Pro.global.*`)
- [ ] `banode` behavior confirmed (indexing, assignment, count)
- [ ] Library loading confirmed with real style paths
- [ ] Parameter array access confirmed (`paname`, `patype`, `paunitval`, etc.)
- [ ] Display/proxy control confirmed
- [ ] Any undocumented properties discovered
- [ ] Library file locations identified for potential XML parsing
- [ ] Results documented in `docs/railclone_introspection_results.md`

### Phase 2: Core Tools (Week 2)
**Goal**: Implement the fundamental creation and inspection tools.

Deliverables:
- [ ] `create_railclone` -- basic creation with spline assignment
- [ ] `create_railclone_from_style` -- library-based creation
- [ ] `get_railclone_info` -- inspection/introspection
- [ ] Registration in `server.py`
- [ ] Basic error handling (plugin check, missing objects)

### Phase 3: Configuration Tools (Week 3)
**Goal**: Implement parameter manipulation and path management.

Deliverables:
- [ ] `set_railclone_paths` -- spline assignment/reassignment
- [ ] `set_railclone_parameters` -- exposed parameter modification
- [ ] `set_railclone_display` -- display/proxy control
- [ ] `railclone_instantiate` -- conversion to instances

### Phase 4: High-Level Presets (Week 4)
**Goal**: Implement convenience tools that combine multiple operations.

Deliverables:
- [ ] Curate map of known library style paths (by category)
- [ ] `create_railclone_fence`
- [ ] `create_railclone_railing`
- [ ] `create_railclone_wall`
- [ ] `create_railclone_array`

### Phase 5: Library Integration (Week 5)
**Goal**: Enable browsing and applying library styles.

Deliverables:
- [ ] `list_railclone_styles` (approach depends on Phase 1 findings)
- [ ] `apply_railclone_style`
- [ ] End-to-end integration tests

---

## 9. Testing Strategy

### 9.1 Unit-Level MAXScript Tests

Each tool should be testable by sending its generated MAXScript directly to a 3ds Max session. Create test scenarios:

**Test 1: Basic Creation**
```maxscript
-- Create a spline path
sp = SplineShape name:"TestPath"
addNewSpline sp
addKnot sp 1 #smooth #curve [0,0,0]
addKnot sp 1 #smooth #curve [200,0,0]
addKnot sp 1 #smooth #curve [400,0,50]
updateShape sp

-- Create RailClone and assign
rc = RailClone_Pro name:"TestRC"
rc.banode[1] = sp
-- Verify: rc.banode[1] should reference the spline
```

**Test 2: Library Loading**
```maxscript
rc = RailClone_Pro name:"TestRC_Style"
result = rc.railclone.loadLibraryItemByPath "\\RailClone Library\\Architecture\\Exterior\\Fences\\Metal Fence 1"
-- Verify: result == 1 (success, confirmed by introspection)
-- Verify: rc.paname.count >= 0 (depends on style; some have no exposed params)
```

**Test 3: Parameter Modification**
```maxscript
-- After loading a style with exposed parameters
rc.paunitval[1] = 50.0
-- Verify viewport updates or read back confirms change
```

**Test 4: Spline Path Assignment**
```maxscript
-- Create two splines for A2S testing
spX = SplineShape name:"XPath"
addNewSpline spX
addKnot spX 1 #smooth #curve [0,0,0]
addKnot spX 1 #smooth #curve [500,0,0]
updateShape spX

spY = SplineShape name:"YPath"
addNewSpline spY
addKnot spY 1 #smooth #curve [0,0,0]
addKnot spY 1 #smooth #curve [0,0,300]
updateShape spY

rc = RailClone_Pro name:"TestRC_A2S"
-- Load an A2S style
rc.banode[1] = spX
rc.banode[2] = spY
```

### 9.2 Integration Tests via MCP

Test the full pipeline: Python tool call -> MAXScript generation -> TCP send -> 3ds Max execution -> JSON response.

1. Call `create_railclone` with a known spline in the scene
2. Call `get_railclone_info` on the result
3. Call `create_railclone_from_style` with a known library path
4. Call `set_railclone_parameters` and verify via `get_railclone_info`
5. Call `railclone_instantiate` and verify geometry is created

### 9.3 Real-World Use Cases

| Use Case | Tools Used | Expected Outcome |
|----------|-----------|------------------|
| Fence along property boundary | `create_railclone_fence` | Fence follows spline path |
| Railing on staircase | `create_railclone_from_style` + `set_railclone_paths` | Railing follows stair path with correct angle |
| Building facade | `create_railclone_from_style` (A2S) + 2 splines | 2D array of facade panels |
| Adjust fence spacing | `set_railclone_parameters` | Spacing changes without rebuilding |
| Inspect unknown RC object | `get_railclone_info` | Full parameter dump for understanding |
| Export to instances | `railclone_instantiate` | Real geometry for external use |

---

## 10. Known Risks and Mitigations

### Risk 1: Limited Style Construction API
**Severity**: High
**Description**: RailClone's style editor is GUI-driven. We likely cannot create or wire nodes via MAXScript.
**Mitigation**: Adopt a library-first approach. All tools that need specific arrangements will load pre-built styles, then modify exposed parameters. Document this limitation clearly in tool docstrings.

### Risk 2: `banode` Indexing May Vary by Style
**Severity**: Medium
**Description**: Different generator types (L1S vs A2S) may map `banode` indices differently. The first slot might not always be "path spline."
**Mitigation**: Phase 1 introspection must test `banode` with multiple style types. Build a mapping table if indices are style-dependent. Consider probing `banode.count` and testing each index.

### Risk 3: Library Paths May Vary by Installation
**Severity**: Medium
**Description**: Library paths in `loadLibraryItemByPath` are internal tree paths, not filesystem paths. Different RailClone versions or custom libraries may have different paths.
**Mitigation**:
- `get_railclone_info` should always return the current `$.style` path
- `list_railclone_styles` should enumerate actual available paths
- Preset tools should attempt loading and report failures gracefully

### Risk 4: Parameter Arrays Are Position-Based
**Severity**: Low-Medium
**Description**: Parameters are stored in parallel arrays (`paname`, `patype`, `paunitval`, etc.). If a style exposes parameters in a different order than expected, index-based access would break.
**Mitigation**: Always look up parameters by name using `findItem` on `paname`, never by hardcoded index.

### Risk 5: Style Loading May Reset State
**Severity**: Medium
**Description**: Loading a new style via `loadLibraryItemByPath` may clear base object assignments.
**Mitigation**: In `create_railclone_from_style`, load the style first, then assign splines. In `apply_railclone_style`, save current spline assignments, load new style, re-assign.

### Risk 6: RailClone Version Differences
**Severity**: Low-Medium
**Description**: `loadLibraryItemByPath` was added in RailClone 6. The `$.railclone` interface may not exist in older versions.
**Mitigation**: Version-check at tool invocation. Fall back to basic creation if library loading is unavailable. Document minimum required version (RailClone 6+).

### Risk 7: No Known API for Geometry Segment Assignment
**Severity**: High
**Description**: Unlike Forest Pack's `cobjlist`/`geomlist`, there is no known MAXScript API to assign geometry objects to segment slots (Default, Start, Corner, End). This means we cannot programmatically build a style from scratch.
**Mitigation**: This is a fundamental limitation. The approach must be:
1. Use library styles (which have segments pre-configured)
2. Allow users to create custom styles in the GUI, expose parameters, then control those parameters via MCP tools
3. Clearly document this in tool descriptions so AI agents understand they cannot build arbitrary styles from code

### Risk 8: Large Library Enumeration Performance
**Severity**: Low
**Description**: Enumerating all library styles might be slow or impractical if the library is large.
**Mitigation**: Implement pagination or category filtering in `list_railclone_styles`. Cache results.

---

## 11. Reference: RailClone Concepts

### Generator Types

| Generator | Code | Dimensions | Spline Inputs | Description |
|-----------|------|-----------|---------------|-------------|
| Linear 1S | L1S | 1D | 1 (path) | Distributes segments along a single spline path |
| Array 2S | A2S | 2D | 2 (X path, Y path) | Creates 2D grid arrays, ideal for facades/floors |

### Segment Slots (L1S Generator)

| Slot | Purpose | When Used |
|------|---------|-----------|
| Default | Base mesh for normal segments | Always (when no other rule matches) |
| Start | First segment on path | At path beginning |
| Corner | At vertices between path segments | At intermediate spline knots |
| End | Last segment on path | At path terminus |
| Evenly | Evenly distributed insertions | At calculated intervals |

### Segment Slots (A2S Generator)

| Slot | Purpose |
|------|---------|
| Default | Fill segment |
| Left Side / Right Side | Edge segments along Y / X axes |
| Top Side / Bottom Side | Edge segments along X axis at top/bottom |
| X Corner / Y Corner | Intermediate column/row segments |
| LT / RT / LB / RB | Four corner segments |
| X Evenly / Y Evenly | Evenly distributed columns/rows |

### Segment Properties

| Property | Description |
|----------|-------------|
| Padding (L/R/T/B) | Spacing between adjacent segments |
| Fixed Size (X/Y/Z) | Override segment dimensions |
| Alignment (X/Y/Z) | Automatic, Pivot, Left/Right/Center, Top/Bottom |
| Deform: Bend | Deform along curves |
| Deform: Slice | Cut at boundaries |
| Z-axis Mode | Adaptative, Vertical, Stepped |
| Mapping | Box mapping with real-world size option |
| Transform | Fixed + Random translation/rotation/scale |

### Default Segment Modes

| Mode | Description |
|------|-------------|
| Tile | Replicate with deformation |
| Scale | Stretch single segment to fill |
| Adaptive | Whole segments scaled to fill space |
| Count | Fixed number of segments scaled to fit |

### Key Operators (Style Editor)

| Operator | Purpose |
|----------|---------|
| Compose | Layer multiple segment streams |
| Sequence | Cycle through segments in order |
| Random | Random segment selection |
| Selector | Choose segment based on condition |
| Transform | Apply transformations |
| Mirror | Mirror geometry |
| Conditional | Rule-based segment selection |

---

## 12. Reference: Confirmed API Surface

> Updated 2026-03-03 with live introspection results from 3ds Max 2025.

### Object Creation
```maxscript
rc = RailClone_Pro name:"MyName"
```

### Core Properties
| Property | Type | Description |
|----------|------|-------------|
| `spline` | node | Spline reference |
| `maxtime` | integer | Max time |
| `seed` | integer | Random seed |
| `iconsize` | float | Icon display size |
| `style` | string | Style string (remains empty after library load) |
| `maxpath` | integer | Max path count |
| `gscale` | float | Global scale |
| `curvesteps` | integer | Curve interpolation steps |
| `simpleoffset` | boolean | Simple offset mode |
| `freeobject` | boolean | Free object mode |
| `stylelink` | node | Style link to another RC object |
| `stylelinkmat` | boolean | Link materials from style link |

### Base Object Arrays (ba*)
| Property | Type | Description |
|----------|------|-------------|
| `banode[i]` | node ref array | Base objects (splines). Index 1 = primary path |
| `baid` | string array | Base object unique IDs |
| `batype` | integer array | Base object types |
| `baname` | string array | Base object display names |
| `bafull` | boolean array | Full spline flag |
| `bastart` | float array | Start position on spline |
| `balength` | float array | Length on spline |
| `badesc` | string array | Base object descriptions |

### Exposed Parameter Arrays (pa*) -- 19 arrays
| Property | Type | Description |
|----------|------|-------------|
| `paid` | string array | Parameter unique IDs |
| `paname` | string array | Parameter display names |
| `patype` | integer array | Type enum: 0=int, 1=float, 3=worldUnits |
| `padesc` | string array | Parameter descriptions |
| `palimit` | boolean array | Whether min/max constraints are active |
| `paintval` | integer array | Integer parameter values |
| `paintmin` | integer array | Integer min constraint |
| `paintmax` | integer array | Integer max constraint |
| `pafloatval` | float array | Float parameter values |
| `pafloatmin` | float array | Float min constraint |
| `pafloatmax` | float array | Float max constraint |
| `paunitval` | worldUnits array | World unit parameter values |
| `paunitmin` | worldUnits array | World unit min constraint |
| `paunitmax` | worldUnits array | World unit max constraint |
| `paboolval` | boolean array | Boolean parameter values |
| `pastrval` | string array | String parameter values |
| `paselector` | string array | Selector binding |
| `pamodified` | boolean array | Whether parameter changed from default |
| `paretain` | integer array | Retain setting |

### Display/Render Properties
| Property | Type | Description |
|----------|------|-------------|
| `autoupdate` | boolean | Auto-update on change |
| `disabled` | boolean | Disable the RailClone object |
| `vmesh` | integer | Viewport mesh density |
| `adaptfaces` | integer | Adaptive face count |
| `cloudens` | integer | Cloud density |
| `rmesh` | integer | Render mesh density |
| `rendermode` | boolean | Render mode toggle |
| `maxseg` | integer | Max segments |
| `maxfaces` | float | Max face count |
| `proxymode` | integer | Proxy mode (0=off, 1=embedded, 2=external) |
| `proxyfile` | filename | External proxy file path |

### Methods ($.railclone.*)
| Method | Description |
|--------|-------------|
| `loadLibraryItemByPath(path)` | Load library style; returns 1=success (integer) |
| `setStyleDesc(text)` | Set style description |
| `getStyleDesc()` | Get style description (returns string) |
| `segmentsUpdate(n1, n2)` | Update segments in range |
| `resetCreatedVersion()` | Reset created version flag |
| `setCreatedVersion(version)` | Set created version |
| `upgradeFromVersion(version)` | Upgrade from older version |
| `setNodesCache(state)` | Set nodes cache state |
| `setProxyMode(mode, proxyfile)` | Set proxy cache (0=off, 1=embedded, 2=external) |

### Static Methods (RailClone_Pro.global.*)
| Method | Description |
|--------|-------------|
| `RegisterEngine()` | Register the RailClone engine |
| `version()` | Get RailClone version (returns integer) |
| `SetEngineFeatures(features)` | Set engine feature flags |
| `Instantiate(mode, layerName, autoDelete, separatedMeshes, forceInstances, disableAtEnd)` | Convert to instances |
| `InstantiateDelete()` | Remove instances |
| `InstantiateEnable()` | Enable display for instances |
| `exportData(filename, fieldlist, format)` | Export data channels (format: 0=Standard, 1=Unity) |

### Scatalog Interface ($.scatalog.*)
| Method | Description |
|--------|-------------|
| `openBrowser()` | Open library browser |
| `closeBrowser()` | Close library browser |
| `refresh()` | Refresh library browser |
| `getMacroCount()` | Get macro count |
| `evalMacro()` | Evaluate macro |
| `getMacro()` | Get macro |
| `setMacro()` | Set macro |
| `getSelItemName()` | Get selected item name |
| `getSelItemProp()` | Get selected item property |
| `getSelItemCustomProp()` | Get selected item custom property |

### Additional Classes (discovered via introspection)
| Class | Type | Description |
|-------|------|-------------|
| `RailClone_Pro` | GeometryClass | Main RailClone object (166 properties) |
| `RailClone_Tools` | UtilityPlugin | RailClone Tools utility |
| `RailClone_Exporter` | ExporterPlugin | Export .rcproxy files |
| `RailClone_Importer` | ImporterPlugin | Import .rcproxy files |
| `RailClone_Color` | textureMap | Per-segment color/material randomization (17 properties) |
| `RC_Slice` | modifier | Slice modifier for RailClone geometry (28 properties) |
| `RC_Spline` | modifier | Spline marker modifier (34 properties) |

---

## 13. Reference: Complete Introspected Property List

> **Source:** Live introspection 2026-03-03, 3ds Max 2025, RailClone Pro
> **Full details:** `docs/research/railclone_introspection.md`

### Segment Arrays (s*) -- 37 arrays (read-only, populated by style graph)

These arrays expose the internal segment configuration. While readable, they are populated by the style editor's node graph and cannot be used to construct styles programmatically.

| Property | Type | Description |
|----------|------|-------------|
| `sid` | string array | Segment unique IDs |
| `sname` | string array | Segment display names |
| `sflags` | integer array | Segment flags |
| `sobjref` | maxObject array | Segment geometry references |
| `sobjoffset` | matrix3 array | Segment object offsets |
| `sobjnodetm` | matrix3 array | Segment node transforms |
| `sobjnode` | node array | Segment source nodes |
| `sobjmtl` | material array | Segment materials |
| `spos` | point3 array | Segment positions |
| `srot` | point3 array | Segment rotations |
| `ssca` | point3 array | Segment scales |
| `sxalign` | integer array | X alignment mode |
| `syalign` | integer array | Y alignment mode |
| `szalign` | integer array | Z alignment mode |
| `spadin` | worldUnits array | Padding in (left) |
| `spadout` | worldUnits array | Padding out (right) |
| `spadtop` | worldUnits array | Padding top |
| `spadbottom` | worldUnits array | Padding bottom |
| `sfixedsize` | point3 array | Fixed size override |
| `ssizescale` | boolean array | Size scale flag |
| `sinstance` | boolean array | Instance flag |
| `sbend` | boolean array | Bend deformation |
| `sslice` | boolean array | Slice at boundaries |
| `snesting` | boolean array | Nesting flag |
| `szdeform` | integer array | Z-axis deform mode |
| `ssurfconform` | boolean array | Surface conform flag |
| `ssurfnormal` | boolean array | Surface normal flag |
| `sslopefix` | boolean array | Slope fix flag |
| `sflattop` | worldUnits array | Flat top distance |
| `sflatbottom` | worldUnits array | Flat bottom distance |
| `srandtrans` | boolean array | Random translation enabled |
| `srandrot` | boolean array | Random rotation enabled |
| `srandscale` | boolean array | Random scale enabled |
| `srandmat` | boolean array | Random material enabled |
| `srt1`, `srt2` | point3 array | Random translation range |
| `srr1`, `srr2` | point3 array | Random rotation range |
| `srs1`, `srs2` | point3 array | Random scale range |
| `smaterial` | integer array | Material ID assignment |
| `smatrange` | integer array | Material range |
| `smapping` | boolean array | Mapping enabled |
| `smapreal` | boolean array | Real-world mapping |
| `smapchans` | string array | Mapping channels |
| `smapsize` | point3 array | Map size |
| `smapoff` | point3 array | Map offset |
| `smaprotx` | float array | Map rotation X |
| `smaproty` | float array | Map rotation Y |
| `smaprotz` | float array | Map rotation Z |

### RailClone_Color Properties (textureMap)
| Property | Type | Description |
|----------|------|-------------|
| `mapbase` | texturemap | Base texture map |
| `mapidmode` | integer | Map ID mode |
| `colorbase` | color | Base color |
| `maplist` | texturemap array | Texture map list for randomization |
| `maponlist` | boolean array | Map enable list |
| `colorlist` | color array | Color list for randomization |
| `problist` | float array | Probability weights |
| `tintmixmode` | integer | Tint mixing mode |
| `tintvariation` | float | Tint variation amount |
| `override` | boolean | Override flag |
| `tintcolor1`, `tintcolor2` | color | Tint color range |
| `tintmin`, `tintmax` | integer | Tint value range |
| `tintmode` | integer | Tint mode |
| `tintmap` | texturemap | Tint texture map |
| `tintmapmode` | integer | Tint map mode |

### RC_Slice Properties (modifier, 28 properties)
Slice positioning for start, end, X/Y evenly, X/Y corners, top, bottom. Key properties:
`start`, `stasize`, `end`, `endsize`, `xde`, `xdepos`, `xdesize`, `xev`, `xevpos`, `xevsize`, `xcr`, `xcrpos`, `xcrsize`, `adjusty`, `top`, `topsize`, `bottom`, `botsize`, `yde`, `ydepos`, `ydesize`, `yev`, `yevpos`, `yevsize`, `adjustx`, `output`, `operateon`, `exname`

### RC_Spline Properties (modifier, 34 properties)
Spline marker control for custom insertion points. Key properties:
`mktype`, `mkdesc`, `mkuserid`, `mkspline`, `mkallsplines`, `mkpercent`, `mkdist`, `mkreference`, `mkrefid`, `mkuserdata0-8`, `mkuserlabel0-8`, `mkusertype0-8`, `mkshowgidzmos`, `bkgizmosize`, `bkspline`, `bkpercent`, `bkangle`, `bkshowgidzmos`

### V1 Legacy Properties
Retained for backward compatibility: `v1yoffset`, `v1zoffset`, `v1gscale`, `v1mirror`, `v1flipa`, `v1flipb`, `v1flatstepped`, `v1beveloffset`, `v1filletrad`, `v1distance`, `v1distadjust`

---

## 14. Sources

Research was conducted across the following resources:

- [iToo Software RailClone Product Page](https://www.itoosoft.com/railclone) -- product overview and feature list
- [RailClone Getting Started Documentation](https://docs.itoosoft.com/railclone/getting-started-with-railclone) -- official beginner guide
- [RailClone Interface Reference](https://docs.itoosoft.com/railclone/getting-started-with-railclone/5-the-railclone-interface) -- UI structure and rollouts
- [RailClone Style Editor Overview](https://docs.itoosoft.com/railclone/style-editor) -- node types, wiring, and MAXScript style description methods
- [RailClone Style Rollout](https://docs.itoosoft.com/railclone/styles) -- style loading and management
- [RailClone Parameters Rollout](https://docs.itoosoft.com/railclone/style-editor/parameters/parameters-rollout) -- pa* array documentation with scripting examples
- [RailClone L1S Generator Reference](https://docs.itoosoft.com/railclone/style-editor/1d-arrays-generator-l1s) -- all L1S slots and properties
- [RailClone A2S Generator Reference](https://docs.itoosoft.com/railclone/style-editor/2d-arrays-generator-a2s) -- all A2S slots and properties
- [RailClone Segments Reference](https://docs.itoosoft.com/railclone/style-editor/segments) -- segment properties (padding, alignment, deform, transform)
- [RailClone Display Settings](https://docs.itoosoft.com/railclone/display-settings) -- setProxyMode MAXScript command
- [RailClone Tools Reference](https://docs.itoosoft.com/railclone/railclone-tools) -- Instantiate/export MAXScript functions
- [RailClone Lister Reference](https://docs.itoosoft.com/railclone/railclone-lister) -- openLister() function
- [Customizing the RailClone Library](https://docs.itoosoft.com/railclone/customizing-the-library) -- loadLibraryItemByPath documentation
- [RailClone 6.0.0 Changelog](https://docs.itoosoft.com/changelog/2023/05/25/railclone-6_0_0) -- MAXScript API additions
- [RailClone 7 Announcement](https://www.itoosoft.com/blog/introducing-railclone-7-smarter-modeling-in-3ds-max-starts-here) -- latest features including spline operators
- [iToo Forum: RailClone and MAXScript](https://forum.itoosoft.com/railclone-pro-(*)/railclone-and-maxscript/) -- community scripting discussions
- [iToo Forum: RailClone MAXScript Usage](https://forum.itoosoft.com/railclone-pro-(*)/railclone-and-maxscript-usage/) -- additional scripting patterns
- [iToo Forum: Scripts for RailClone](https://forum.itoosoft.com/railclone-pro-(*)/scripts-for-railclone/) -- community scripts
- [iToo Forum: Utilizing RailClone Tools in MAXScript](https://forum.itoosoft.com/general-off-topic/utilizing-railclone-tools-in-maxscript/) -- tool automation
- [iToo Forum: Library Path via MAXScript](https://forum.itoosoft.com/railclone-pro-(*)/howto-set-railclone-and-forestpack-user-library-path-via-maxscript/) -- library path configuration
- [CG Channel: RailClone 6 Release](https://www.cgchannel.com/2023/05/itoo-software-releases-railclone-6-for-3ds-max/) -- feature overview
- [RailClone Guide PDF (Intercadsys)](https://www.intercadsys.com/uploads/brochure/Railclone_Guide.pdf) -- comprehensive guide
- [Novedge: Top 5 Customization Techniques](https://novedge.com/blogs/design-news/top-5-customization-techniques-for-railclone-to-enhance-your-3ds-max-workflow) -- scripting and customization overview
- [Megarender: Definitive Starting Guide](https://megarender.com/blog/the-definitive-starting-guide-for-railclone/) -- banode assignment pattern
