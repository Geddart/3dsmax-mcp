# Forest Pack Pro Extended Tools -- Implementation Plan

> **Status:** Phase 0 Complete (introspection done, property names verified)
> **Date:** 2026-03-03
> **Target file:** `src/tools/scattering.py` (extend existing module)
> **Server registration:** Already registered via `scattering` import in `src/server.py` line 13

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Research Phase -- Runtime Introspection Scripts](#2-research-phase----runtime-introspection-scripts)
3. [Tool Definitions](#3-tool-definitions)
4. [MAXScript Implementation Details](#4-maxscript-implementation-details)
5. [Testing Strategy](#5-testing-strategy)
6. [Implementation Order](#6-implementation-order)
7. [Known Risks and Mitigations](#7-known-risks-and-mitigations)

---

## 1. Architecture Overview

### How existing tools work

Every tool in this codebase follows the same pattern:

1. A Python function decorated with `@mcp.tool()` in a file under `src/tools/`.
2. The function builds a MAXScript string using f-strings.
3. It calls `client.send_command(maxscript)` which sends the script over TCP to 3ds Max.
4. 3ds Max evaluates the MAXScript and returns a JSON string.
5. The Python function extracts the result with `response.get("result", "")`.

**Key conventions:**
- Tool names are `lowercase_with_underscores`.
- String escaping uses `_safe_name()` (escapes backslashes and double quotes).
- MAXScript builds JSON via manual string concatenation (no `json` library in MAXScript).
- Errors are returned as JSON objects with an `"error"` key.
- The `from ..server import mcp, client` import pattern is used in every tool file.
- Complex tools use `try/catch` blocks in MAXScript for resilience.
- Array helpers `_name_array()` and `_float_array()` already exist in `scattering.py`.

### What already exists for Forest Pack

In `src/tools/scattering.py`:
- `scatter_forest_pack` -- a "create and configure" one-shot tool that:
  - Creates a `Forest_Pro` object
  - Sets surfaces via `fp.surflist`
  - Initializes all 7 area-list arrays together (`arnodelist`, `arnamelist`, `artypelist`, `arincexclist`, `arprojectlist`, `pf_aractivelist`, `aridlist`)
  - Sets source geometry via `fp.cobjlist`, `fp.namelist`, `fp.problist`, `fp.geomlist`
  - Configures density (`maxdensity`, `units_x`, `units_y`), scale, rotation, icon size
  - Handles unit conversion with `units.decodeValue`
  - Returns JSON summary

In `docs/forest_pack_scatter_notes.md`:
- Production learnings documenting array interdependencies, density pitfalls, facing modes

### What does NOT exist yet

- **Inspection:** No way to query an existing Forest Pack object's configuration
- **Listing:** No way to find all Forest Pack objects in a scene
- **Modification:** No way to update properties on an existing Forest Pack object
- **Areas:** No spline-based include/exclude areas, no paint areas, no object-based exclusion
- **Distribution:** No bitmap/texture density maps, no path-mode distribution, no cluster settings
- **Transform maps:** No map-based control of scale/rotation/translation variation
- **Material/Color:** No tint variation, no color correction, no Forest Color integration
- **Camera:** No camera clipping, no density/scale falloff by distance, no look-at
- **Animation:** No animation offset modes (follow geometry, random samples, frame from map)
- **Effects:** No effects expression support
- **LOD:** No Forest LOD object integration
- **Library:** No preset loading from the Forest Pack library
- **Edge mode:** No boundary checking configuration

### File organization

All new Forest Pack tools go in the existing file: **`src/tools/scattering.py`**

This keeps all Forest Pack integration in one place. The existing file is ~220 lines. With the additions below it will grow to approximately 1500-2000 lines. If it exceeds ~2500 lines, split into:
- `scattering.py` -- creation and core modification
- `scattering_areas.py` -- area management
- `scattering_advanced.py` -- camera, animation, effects, LOD

No changes to `src/server.py` are needed if we keep everything in `scattering.py`.

---

## 2. Research Phase -- Runtime Introspection Scripts

> **Phase 0 Status:** COMPLETED 2026-03-03
> **Full results:** `docs/research/forest_pack_introspection.md`
> **Key findings:**
> - 341 properties confirmed (plan estimated "200+")
> - Distribution map: `distmap` (texturemap) -- confirmed
> - Diversity: `divers` (integer), NOT `diversity`
> - Cluster: `clusize`, `clurough`, `clunoise`, `cluedge` -- NOT `clustsize`, `clustrough`
> - 27 area arrays (ar*) confirmed -- more than the 7 documented in existing tool
> - trees interface confirmed with full CRUD (create, delete, edit, move, setPosition, setRotation, etc.)
> - ForestLOD (19 props), ForestSet (7 props), ForestColor (18 props) -- ALL exist
> - Forest_Lite does NOT exist in this installation
> - 4 interfaces: trees, ForestPack, ui, scatalog/catalog

**CRITICAL:** Forest Pack is a closed-source plugin with no published MAXScript API reference. Property names discovered online are incomplete and may vary between versions. The following introspection scripts MUST be run inside 3ds Max with Forest Pack installed before implementing any new tool.

Run each script via the existing `execute_maxscript` tool or the MAXScript Listener.

### 2.1 Complete property dump

> **Result:** 341 properties found via getPropNames. Full dump in `docs/research/forest_pack_introspection.md` Section 1.

This is the single most important research step. Forest Pack objects have 341 properties (confirmed).

```maxscript
-- Dump ALL Forest_Pro properties with types and current values
(
    local fp = undefined
    try (fp = Forest_Pro()) catch ()
    if fp == undefined then (
        "Forest_Pro class not available -- Forest Pack not installed"
    ) else (
        local ss = stringstream ""
        showProperties fp to:ss
        seek ss 0
        local result = "=== showProperties Forest_Pro ===\n"
        while not (eof ss) do (
            local ln = readline ss
            if ln.count > 0 do result += ln + "\n"
        )

        -- Also dump via getPropNames for programmatic names
        result += "\n=== getPropNames Forest_Pro ===\n"
        local propNames = getPropNames fp
        for p in propNames do (
            local val = undefined
            local valStr = "???"
            try (
                val = getProperty fp p
                valStr = val as string
                if valStr.count > 150 do valStr = (substring valStr 1 150) + "..."
            ) catch (valStr = "<error reading>")
            result += (p as string) + " = " + valStr + "  [" + ((classOf val) as string) + "]\n"
        )

        delete fp
        result
    )
)
```

### 2.2 Show interfaces (methods and functions)

> **Result:** 4 interfaces found: trees (full CRUD), ForestPack (engine/export), ui (rollup), scatalog/catalog (browser). See introspection doc Section 2.

```maxscript
-- Dump all interfaces available on a Forest_Pro object
(
    local fp = undefined
    try (fp = Forest_Pro()) catch ()
    if fp == undefined then (
        "Forest_Pro not available"
    ) else (
        local ss = stringstream ""
        showInterfaces fp to:ss
        seek ss 0
        local result = "=== showInterfaces Forest_Pro ===\n"
        while not (eof ss) do (
            local ln = readline ss
            if ln.count > 0 do result += ln + "\n"
        )
        delete fp
        result
    )
)
```

### 2.3 Categorized property discovery

Run these targeted queries to map Forest Pack's property namespace. Each focuses on a known UI rollout.

#### Distribution properties

> **Result:** Confirmed: `distmap`, `distmapchan`, `densityMap`, `distmode`, `divers` (NOT `diversity`), `clusize`/`clurough`/`clunoise`/`cluedge` (NOT `clustsize`/`clustrough`/`clustblur`/`clustnoise`), `collision`, `radius`, `collheight`, `threshold`, `maxdensity`.
```maxscript
-- Find distribution-related properties
(
    local fp = Forest_Pro()
    local propNames = getPropNames fp
    local result = "=== Distribution Properties ===\n"
    local keywords = #("dist", "dens", "map", "noise", "cluster", "collis", "thresh",
                        "divers", "pixel", "offset", "gizmo", "units_x", "units_y",
                        "maxdensity", "maptype", "mapsizex", "mapsizey", "mapchannel")
    for p in propNames do (
        local pStr = toLower (p as string)
        for k in keywords do (
            if findString pStr k != undefined do (
                local val = undefined
                try (val = getProperty fp p) catch ()
                result += (p as string) + " = " + (val as string) + "\n"
                exit
            )
        )
    )
    delete fp
    result
)
```

#### Area properties

> **Result:** 27 area arrays with `ar*` prefix confirmed (plus `pf_aractivelist`). Includes falloff arrays `arflafdenslist`, `arflafscalist`, `arflinvlist` not previously documented. Per-area scale overrides via `arscalemin`, `arscalemax`, `arzoffset`.

```maxscript
-- Find area-related properties
(
    local fp = Forest_Pro()
    local propNames = getPropNames fp
    local result = "=== Area Properties ===\n"
    local keywords = #("ar", "area", "spline", "incexc", "include", "exclude",
                        "paint", "falloff", "boundary", "matid", "thick")
    for p in propNames do (
        local pStr = toLower (p as string)
        for k in keywords do (
            if findString pStr k != undefined do (
                local val = undefined
                try (val = getProperty fp p) catch ()
                result += (p as string) + " = " + (val as string) + "\n"
                exit
            )
        )
    )
    delete fp
    result
)
```

#### Transform properties

> **Result:** Confirmed: `applytranslation`, `transxmin`-`transzmax`, `transmapx/y/z`, `transmap`, `applyrotation`, `xrotmin`-`zrotmax`, `rotmapx/y/z`, `rotmap`, `applyscale`, `scalexmin`-`scalezmax`, `scamapx/y/z`, `scamap`, `scalelock`, `mirror`. All with texture map support via `transmapchan`, `rotmapchan`, `scamapchan`.

```maxscript
-- Find transform-related properties
(
    local fp = Forest_Pro()
    local propNames = getPropNames fp
    local result = "=== Transform Properties ===\n"
    local keywords = #("scale", "rot", "trans", "mirror", "flip", "lock",
                        "apply", "prob", "xmin", "xmax", "ymin", "ymax",
                        "zmin", "zmax", "colormap", "probmap")
    for p in propNames do (
        local pStr = toLower (p as string)
        for k in keywords do (
            if findString pStr k != undefined do (
                local val = undefined
                try (val = getProperty fp p) catch ()
                result += (p as string) + " = " + (val as string) + "\n"
                exit
            )
        )
    )
    delete fp
    result
)
```

#### Camera/LOD properties

> **Result:** Confirmed: `camera`, `lookattarget`, `camlimit`, `uselookat`, `camlookat`, `camlod`, `camloddist`, `camlodlookat`, `camwidth`, `camnear`, `camfar`, `cambho`, `camdenscurve`, `camdensact`, `camscacurve`, `camscaact`, `camdensear`, `camdensfar`. No `limitvisibility` or `expand` -- use `camlimit` and `camwidth` instead.

```maxscript
-- Find camera and LOD-related properties
(
    local fp = Forest_Pro()
    local propNames = getPropNames fp
    local result = "=== Camera/LOD Properties ===\n"
    local keywords = #("cam", "clip", "lod", "visibility", "expand", "far",
                        "limit", "lookat", "facing", "distance", "back",
                        "falloff", "curve", "override", "screen")
    for p in propNames do (
        local pStr = toLower (p as string)
        for k in keywords do (
            if findString pStr k != undefined do (
                local val = undefined
                try (val = getProperty fp p) catch ()
                result += (p as string) + " = " + (val as string) + "\n"
                exit
            )
        )
    )
    delete fp
    result
)
```

#### Material/Color properties

> **Result:** Confirmed: `tintmixmode`, `tintcolor1`, `tintcolor2`, `tintmin`, `tintmax`, `tintmode`, `tintmap`, `tintmapmode`, `tintmapchan`. Color correction: `mathue`, `matsaturation`, `matbrightness`, `matapply`, `matapplycolor`, `matrangewidth`. Opacity: `fastopac`, `tracedepth`, `opaclevel`, `selfillum`, `irradiance`. No `usetint` -- use `tintmode` instead.

```maxscript
-- Find material and color-related properties
(
    local fp = Forest_Pro()
    local propNames = getPropNames fp
    local result = "=== Material/Color Properties ===\n"
    local keywords = #("tint", "color", "hue", "sat", "bright", "material",
                        "gradient", "strength", "correction", "optimize",
                        "consolidate", "forestcolor")
    for p in propNames do (
        local pStr = toLower (p as string)
        for k in keywords do (
            if findString pStr k != undefined do (
                local val = undefined
                try (val = getProperty fp p) catch ()
                result += (p as string) + " = " + (val as string) + "\n"
                exit
            )
        )
    )
    delete fp
    result
)
```

#### Animation properties

> **Result:** Confirmed: `animation` (integer, NOT `animmode`), `animsoffset` (time), `animsamples` (integer), `animonlyrend` (boolean), `animap` (texturemap, NOT `animmap`), `animapchan` (integer), `animstart` (time), `animend` (time). No `animoffset` -- use `animsoffset` instead.

```maxscript
-- Find animation-related properties
(
    local fp = Forest_Pro()
    local propNames = getPropNames fp
    local result = "=== Animation Properties ===\n"
    local keywords = #("anim", "frame", "sample", "time", "offset", "playback",
                        "follow", "geometry", "randmap")
    for p in propNames do (
        local pStr = toLower (p as string)
        for k in keywords do (
            if findString pStr k != undefined do (
                local val = undefined
                try (val = getProperty fp p) catch ()
                result += (p as string) + " = " + (val as string) + "\n"
                exit
            )
        )
    )
    delete fp
    result
)
```

#### Display properties

> **Result:** Confirmed: `vmesh` (integer), `geomtexid`, `vtype`, `adaptfaces`, `cloudcolorid`, `cloudens`, `vmaxitems`, `rmesh` (integer), `rskip`, `opacity`, `wireframe`, `rtype`, `rendermode`, `rmaxitems`, `maxfaces`, `hidecustom`, `manualupdate`, `disabled`, `dispflags`, `iconsize`.

```maxscript
-- Find display-related properties
(
    local fp = Forest_Pro()
    local propNames = getPropNames fp
    local result = "=== Display Properties ===\n"
    local keywords = #("vmesh", "rmesh", "display", "icon", "wire", "opacity",
                        "proxy", "cloud", "points", "adaptive", "maxitems",
                        "simplif", "mesh", "disable", "freeze", "render",
                        "hide", "faces")
    for p in propNames do (
        local pStr = toLower (p as string)
        for k in keywords do (
            if findString pStr k != undefined do (
                local val = undefined
                try (val = getProperty fp p) catch ()
                result += (p as string) + " = " + (val as string) + "\n"
                exit
            )
        )
    )
    delete fp
    result
)
```

#### Surface properties

> **Result:** Confirmed: `surflist`, `surflink`, `altlimited`, `altmax`, `altmin` (NOT `alttop`/`altbottom`), `surfaltdens`, `surfaltscal`, `slopelimited`, `slopemax`, `slopemin`, `surfslodens`, `surfsloscal`, `surfanim`, `linkeditsurf`, `direction`, `scalelope`, `surfmode`, `uvalign`, `uvscalex`, `uvscaley`, `uvmultscalex`, `uvmultscaley`.

```maxscript
-- Find surface-related properties
(
    local fp = Forest_Pro()
    local propNames = getPropNames fp
    local result = "=== Surface Properties ===\n"
    local keywords = #("surf", "altitude", "slope", "direction", "uv",
                        "link", "place", "custom", "edit", "fit")
    for p in propNames do (
        local pStr = toLower (p as string)
        for k in keywords do (
            if findString pStr k != undefined do (
                local val = undefined
                try (val = getProperty fp p) catch ()
                result += (p as string) + " = " + (val as string) + "\n"
                exit
            )
        )
    )
    delete fp
    result
)
```

### 2.4 Discover the "trees" interface

> **Result:** Full CRUD confirmed -- create, delete, edit, count, move, setPosition/getPosition, setRotation/getRotation, setWidth/getWidth, setHeight/getHeight, setSize/getSize, setGeomID/getGeomID, setSeed/getSeed, getFullTransform, getSelected, update, update_ui, plus render helpers.

Forest Pack exposes a programmatic interface for per-item manipulation:

```maxscript
-- Discover the trees interface methods
(
    local fp = Forest_Pro()
    local result = ""
    try (
        local iface = fp.trees
        local ss = stringstream ""
        showMethods iface to:ss
        seek ss 0
        result += "=== trees interface methods ===\n"
        while not (eof ss) do (
            local ln = readline ss
            if ln.count > 0 do result += ln + "\n"
        )
    ) catch (
        result += "trees interface not available or error: " + (getCurrentException()) + "\n"
    )
    delete fp
    result
)
```

### 2.5 Discover Forest LOD class

> **Result:** ForestLOD EXISTS with 19 properties including cobjlist, matlist, namelist, geomlist, distlist, screensizelist, iconsize, mode, distance, variation, update.

```maxscript
-- Check if ForestLOD class exists and dump its properties
(
    local result = ""
    local lodClass = undefined
    try (lodClass = ForestLOD) catch ()
    if lodClass == undefined then (
        try (lodClass = Forest_LOD) catch ()
    )
    if lodClass == undefined then (
        result = "ForestLOD / Forest_LOD class not found. Check: showClass \"Forest*\"\n"
        local ss = stringstream ""
        showClass "Forest*" to:ss
        seek ss 0
        while not (eof ss) do (
            local ln = readline ss
            if ln.count > 0 do result += ln + "\n"
        )
    ) else (
        local obj = lodClass()
        local ss = stringstream ""
        showProperties obj to:ss
        seek ss 0
        result = "=== ForestLOD properties ===\n"
        while not (eof ss) do (
            local ln = readline ss
            if ln.count > 0 do result += ln + "\n"
        )
        delete obj
    )
    result
)
```

### 2.6 Discover Forest Set and Forest Color classes

> **Result:** ForestSet EXISTS (7 props: nodelist, iconsize, layerimport, layerchilds, layernames, wirecolor, disabled). ForestColor EXISTS (18 props: mapbase, mapidmode, colorbase, maplist, maponlist, colorlist, problist, tintmixmode, tintvariation, override, tintcolor1, tintcolor2, tintmin, tintmax, tintmode, tintmap, tintmapmode, applycor). Forest_Lite NOT FOUND.

```maxscript
-- Check for Forest Set and Forest Color map classes
(
    local result = ""

    -- Forest Set
    local setClass = undefined
    for name in #("ForestSet", "Forest_Set", "FP_Set") do (
        try (setClass = execute name) catch ()
        if setClass != undefined do exit
    )
    if setClass != undefined then (
        result += "Forest Set class: " + (setClass as string) + "\n"
    ) else (
        result += "Forest Set class not found\n"
    )

    -- Forest Color map
    local colorClass = undefined
    for name in #("ForestColor", "Forest_Color", "FP_Color") do (
        try (colorClass = execute name) catch ()
        if colorClass != undefined do exit
    )
    if colorClass != undefined then (
        result += "Forest Color class: " + (colorClass as string) + "\n"
        local obj = colorClass()
        local ss = stringstream ""
        showProperties obj to:ss
        seek ss 0
        result += "=== Forest Color properties ===\n"
        while not (eof ss) do (
            local ln = readline ss
            if ln.count > 0 do result += ln + "\n"
        )
    ) else (
        result += "Forest Color class not found\n"
    )

    result
)
```

---

## 3. Tool Definitions

### 3.0 Helper functions to add to `scattering.py`

Before new tools, add shared helpers:

```python
def _get_forest_pack_node_expr(name: str) -> str:
    """Return MAXScript expression that resolves a Forest_Pro node by name."""
    safe = _safe_name(name)
    return f"""(
        local fp = getNodeByName "{safe}"
        if fp == undefined then (
            "{{\\"error\\":\\"Object not found: {safe}\\"}}"
        ) else if (classOf fp.baseObject) != Forest_Pro then (
            "{{\\"error\\":\\"Object '{safe}' is not a Forest Pack object (class: " + ((classOf fp.baseObject) as string) + ")\\"}}"
        ) else (
            -- fp is valid Forest_Pro node
"""

def _int_array(values: list[int]) -> str:
    """Build a MAXScript #(...) integer array literal."""
    return "#(" + ", ".join(str(int(v)) for v in values) + ")"

def _bool_array(values: list[bool]) -> str:
    """Build a MAXScript #(...) boolean array literal."""
    return "#(" + ", ".join("true" if v else "false" for v in values) + ")"
```

---

### 3.1 `list_forest_pack_objects` -- Find all Forest Pack objects in scene

**Purpose:** Scene discovery. Before modifying a Forest Pack object the user needs to know what exists.

**Python signature:**
```python
@mcp.tool()
def list_forest_pack_objects() -> str:
    """List all Forest Pack objects in the current 3ds Max scene.

    Returns JSON array of objects with name, surface count, geometry count,
    density, seed, and enabled status.
    """
```

**MAXScript approach:**
```maxscript
(
    local forestClass = undefined
    try (forestClass = Forest_Pro) catch ()
    if forestClass == undefined then (
        "{\"error\":\"Forest Pack not installed\"}"
    ) else (
        local insts = getClassInstances Forest_Pro
        -- For each instance, find its scene node via refs.dependentNodes
        -- Collect: name, surflist.count, cobjlist.count, maxdensity, seed
        -- Return JSON array
    )
)
```

**JSON output:**
```json
[
    {
        "name": "ForestScatter001",
        "surfaceCount": 2,
        "geometryCount": 5,
        "density": 500,
        "seed": 12345,
        "areaCount": 3,
        "distributionMode": "image"
    }
]
```

---

### 3.2 `get_forest_pack_info` -- Inspect a specific Forest Pack object

**Purpose:** Deep inspection of an existing Forest Pack object. Returns all key configuration in one call. This is the Forest Pack equivalent of `inspect_object`.

**Python signature:**
```python
@mcp.tool()
def get_forest_pack_info(name: str) -> str:
    """Get comprehensive configuration of a Forest Pack object.

    Returns surfaces, source geometry, areas, distribution settings,
    transform settings, camera settings, animation mode, and display modes.

    Args:
        name: The Forest Pack object name.
    """
```

**MAXScript approach:**
- Resolve node, verify `classOf fp.baseObject == Forest_Pro`
- Read and return:
  - **Surfaces:** `fp.surflist` -- names of surface nodes
  - **Geometry:** `fp.cobjlist`, `fp.namelist`, `fp.problist`, `fp.geomlist` -- source objects with probabilities and types
  - **Areas:** `fp.arnodelist`, `fp.arnamelist`, `fp.artypelist`, `fp.arincexclist`, `fp.pf_aractivelist` -- full area configuration
  - **Distribution:** `fp.maxdensity`, `fp.units_x`, `fp.units_y`, distribution mode (needs property discovery), `fp.distmap` (if texture assigned)
  - **Transform:** `fp.applyscale`, `fp.scalelock`, `fp.scalexmin/max`, `fp.scaleymin/max`, `fp.scalezmin/max`, `fp.applyrotation`, `fp.xrotmin/max`, `fp.yrotmin/max`, `fp.zrotmin/max`, `fp.applytranslation`, `fp.mirror`
  - **Surface:** `fp.direction`, `fp.altlimited`, `fp.altmin`, `fp.altmax`, `fp.slopelimited`, `fp.slopemin`, `fp.slopemax`, `fp.surfaltdens`, `fp.surfaltscal`, `fp.surfslodens`, `fp.surfsloscal`
  - **Camera:** `fp.camera`, `fp.camlimit`, `fp.camnear`, `fp.camfar`, `fp.cambho`, `fp.uselookat`, `fp.lookattarget`, `fp.camlod`, `fp.camloddist`
  - **Animation:** `fp.animation`, `fp.animsamples`, `fp.animsoffset`, `fp.animstart`, `fp.animend`, `fp.animonlyrend`, `fp.animap`
  - **Display:** `fp.vmesh`, `fp.rmesh`, `fp.iconsize`
  - **General:** `fp.seed`, `fp.name`

**JSON output (example):**
```json
{
    "name": "ForestScatter001",
    "surfaces": ["Ground_Plane", "Terrain_01"],
    "geometry": [
        {"name": "Oak_Tree", "probability": 0.6, "type": 2},
        {"name": "Birch_Tree", "probability": 0.4, "type": 2}
    ],
    "areas": [
        {"name": "Surface Area", "type": 3, "includeExclude": 0, "active": true, "node": null},
        {"name": "Exclude_Path", "type": 0, "includeExclude": 1, "active": true, "node": "Spline001"}
    ],
    "distribution": {
        "density": 500,
        "unitsX": 300.0,
        "unitsY": 300.0,
        "hasDistributionMap": false
    },
    "transform": {
        "scaleEnabled": true,
        "scaleLocked": true,
        "scaleMin": [85, 85, 85],
        "scaleMax": [115, 115, 115],
        "rotationEnabled": true,
        "zRotMin": -180,
        "zRotMax": 180
    },
    "surface": {
        "direction": 1
    },
    "display": {
        "viewportMode": 2,
        "renderMode": 0,
        "iconSize": 30.0
    },
    "general": {
        "seed": 12345
    }
}
```

---

### 3.3 `modify_forest_pack` -- Update properties on an existing Forest Pack object

**Purpose:** General-purpose modification of any scalar Forest Pack property. Analogous to `set_object_property` but Forest-Pack-aware with validation.

**Python signature:**
```python
@mcp.tool()
def modify_forest_pack(
    name: str,
    density: int | None = None,
    seed: int | None = None,
    scale_min: float | None = None,
    scale_max: float | None = None,
    scale_lock: bool | None = None,
    z_rotation_min: float | None = None,
    z_rotation_max: float | None = None,
    x_rotation_min: float | None = None,
    x_rotation_max: float | None = None,
    y_rotation_min: float | None = None,
    y_rotation_max: float | None = None,
    facing_mode: int | None = None,
    density_units_x_cm: float | None = None,
    density_units_y_cm: float | None = None,
    icon_size_cm: float | None = None,
    viewport_mode: int | None = None,
    render_mode: int | None = None,
) -> str:
    """Modify properties on an existing Forest Pack object.

    Only provided (non-None) parameters are changed. Other properties remain untouched.

    Args:
        name: The Forest Pack object name.
        density: Maximum density value.
        seed: Random seed.
        scale_min: Uniform minimum scale percent (applied to X/Y/Z if scale_lock is true).
        scale_max: Uniform maximum scale percent.
        scale_lock: Lock X/Y/Z scale together.
        z_rotation_min: Minimum Z rotation in degrees.
        z_rotation_max: Maximum Z rotation in degrees.
        x_rotation_min: Minimum X rotation in degrees.
        x_rotation_max: Maximum X rotation in degrees.
        y_rotation_min: Minimum Y rotation in degrees.
        y_rotation_max: Maximum Y rotation in degrees.
        facing_mode: 0 = surface normal, 1 = world up.
        density_units_x_cm: Density tile X size in cm.
        density_units_y_cm: Density tile Y size in cm.
        icon_size_cm: Icon display size in cm.
        viewport_mode: Viewport display mode integer.
        render_mode: Render display mode integer.
    """
```

**MAXScript approach:**
- Build conditional assignment lines only for non-None params
- Use `units.decodeValue` for cm-based params
- Return JSON summary of what was changed

---

### 3.4 `set_forest_pack_surfaces` -- Change surface objects

**Purpose:** Replace or add surface objects on an existing Forest Pack.

**Python signature:**
```python
@mcp.tool()
def set_forest_pack_surfaces(
    name: str,
    surfaces: list[str],
) -> str:
    """Set the surface objects for an existing Forest Pack object.

    Replaces the current surface list entirely.

    Args:
        name: The Forest Pack object name.
        surfaces: List of surface object names.
    """
```

**MAXScript approach:**
- Resolve each surface name to a node
- Set `fp.surflist = surfaceNodes`
- Return JSON with new surface count

---

### 3.5 `set_forest_pack_sources` -- Change source geometry

**Purpose:** Replace or modify source geometry and probabilities on an existing Forest Pack.

**Python signature:**
```python
@mcp.tool()
def set_forest_pack_sources(
    name: str,
    geometry: list[str],
    probabilities: list[float] | None = None,
    source_width_cm: float = 5.0,
    source_height_cm: float = 5.0,
) -> str:
    """Set the source geometry for an existing Forest Pack object.

    Replaces the current geometry list entirely.

    Args:
        name: The Forest Pack object name.
        geometry: List of source object names.
        probabilities: Optional per-source weights. Defaults to equal weights.
        source_width_cm: Source width in centimeters.
        source_height_cm: Source height in centimeters.
    """
```

**MAXScript approach:**
- Resolve geometry nodes
- Set `fp.cobjlist`, `fp.namelist`, `fp.problist`, `fp.geomlist`, `fp.widthlist`, `fp.heightlist`
- All arrays must be set together to maintain consistency

---

### 3.6 `add_forest_pack_area` -- Add an include/exclude area

**Purpose:** Add a spline-based or surface-based area to an existing Forest Pack. This is the most commonly requested missing feature.

**Python signature:**
```python
@mcp.tool()
def add_forest_pack_area(
    name: str,
    area_name: str = "New Area",
    area_type: int = 0,
    include_exclude: int = 0,
    spline_node: str | None = None,
    projection: int = 2,
    active: bool = True,
) -> str:
    """Add an area to an existing Forest Pack object.

    Areas control where items are scattered. They can be include (additive)
    or exclude (subtractive) regions defined by splines, objects, or other
    Forest Pack objects.

    Args:
        name: The Forest Pack object name.
        area_name: Display name for the area.
        area_type: Area type integer:
            0 = Spline area (use spline_node to assign a spline)
            1 = Object area (exclusion by geometry)
            2 = Forest area (exclusion by another Forest object)
            3 = Surface area (existing default type)
            4 = Paint area
        include_exclude: 0 = include, 1 = exclude.
        spline_node: Object name of the spline/object to use (required for type 0, 1, 2).
        projection: Projection mode: 0 = none, 1 = XY, 2 = surface (default).
        active: Whether this area is active.

    Returns:
        JSON summary with area count after addition.
    """
```

**MAXScript approach -- CRITICAL:**
Area lists are interdependent. The core 7 arrays must be read, appended to, and written back together. Phase 0 confirmed 27+ area arrays total (see Section 4.2), but the core 7 are sufficient for basic area creation -- Forest Pack initializes additional per-area arrays with defaults:

```maxscript
-- Read current arrays
local nodes = fp.arnodelist
local names = fp.arnamelist
local types = fp.artypelist
local incexc = fp.arincexclist
local proj = fp.arprojectlist
local active = fp.pf_aractivelist
local ids = fp.aridlist

-- Compute next ID
local nextId = 1
for id in ids do (if id >= nextId do nextId = id + 1)

-- Append new area
append nodes splineObj    -- or undefined for paint/surface areas
append names "New Area"
append types areaTypeVal
append incexc incExcVal
append proj projVal
append active true
append ids nextId

-- Write all back together
fp.arnodelist = nodes
fp.arnamelist = names
fp.artypelist = types
fp.arincexclist = incexc
fp.arprojectlist = proj
fp.pf_aractivelist = active
fp.aridlist = ids
```

---

### 3.7 `remove_forest_pack_area` -- Remove an area by index

**Purpose:** Remove an area from a Forest Pack object.

**Python signature:**
```python
@mcp.tool()
def remove_forest_pack_area(
    name: str,
    area_index: int,
) -> str:
    """Remove an area from a Forest Pack object by index (1-based).

    Args:
        name: The Forest Pack object name.
        area_index: 1-based index of the area to remove.

    Returns:
        JSON summary with remaining area count.
    """
```

**MAXScript approach:**
- Read all core 7 area arrays (plus any populated additional arrays from the 27+ confirmed)
- Validate index bounds
- Delete item at index from all populated arrays
- Write all arrays back
- See Section 4.2 for the complete list of area arrays

---

### 3.8 `set_forest_pack_distribution_map` -- Assign a density/distribution texture

**Purpose:** Control scatter density via a bitmap or procedural texture map.

**Python signature:**
```python
@mcp.tool()
def set_forest_pack_distribution_map(
    name: str,
    map_file: str | None = None,
    map_variable: str | None = None,
    density_units_x_cm: float | None = None,
    density_units_y_cm: float | None = None,
    threshold: float = 0.5,
    use_map_channel: bool = False,
    map_channel: int = 1,
) -> str:
    """Assign a distribution/density map to a Forest Pack object.

    White pixels scatter items, black pixels do not. Grayscale controls density.
    Either provide a bitmap file path or a MAXScript variable name referencing
    an existing texture map.

    Args:
        name: The Forest Pack object name.
        map_file: Path to a bitmap image file. Creates a Bitmaptexture.
        map_variable: Name of an existing MAXScript global variable holding a texture map.
            Use this for procedural maps created via create_texture_map.
        density_units_x_cm: Distribution map X size in cm (controls density tile size).
        density_units_y_cm: Distribution map Y size in cm.
        threshold: Black/white threshold for distribution (0.0-1.0).
        use_map_channel: If true, use surface UV coordinates via map_channel.
        map_channel: UV map channel to use (default 1). Only applies if use_map_channel is true.
    """
```

**MAXScript approach (confirmed property names):**
- Distribution map: `fp.distmap` (texturemap) -- CONFIRMED
- Distribution map channel: `fp.distmapchan` (integer) -- CONFIRMED
- Distribution mode: `fp.distmode` (integer) -- CONFIRMED
- Density map enabled: `fp.densityMap` (boolean) -- CONFIRMED
- Threshold: `fp.threshold` (integer) -- CONFIRMED
- If `map_file` provided: `fp.distmap = Bitmaptexture filename:"<path>"`
- If `map_variable` provided: `fp.distmap = <variable>`
- Optionally set density units via `fp.units_x`, `fp.units_y`

---

### 3.9 `set_forest_pack_cluster_settings` -- Configure clustering

**Purpose:** Group scattered items into natural-looking clusters.

**Python signature:**
```python
@mcp.tool()
def set_forest_pack_cluster_settings(
    name: str,
    enabled: bool = True,
    cluster_size_cm: float = 100.0,
    roughness: float = 50.0,
    noise: float = 0.0,
    edge: float = 0.0,
) -> str:
    """Configure cluster distribution on a Forest Pack object.

    Clusters group similar geometry items together, creating natural-looking
    patches (e.g. groups of same tree species). Requires multiple items in
    the geometry list.

    Args:
        name: The Forest Pack object name.
        enabled: Enable cluster mode.
        cluster_size_cm: Cluster size in centimeters (property: clusize).
        roughness: Cluster boundary roughness (property: clurough, float).
        noise: Random noise to break up clusters (property: clunoise, float).
        edge: Cluster edge softness (property: cluedge, float).
    """
```

**MAXScript approach (confirmed property names):**
- Diversity mode: `fp.divers` (integer) -- NOT `fp.diversity`
- Diversity map: `fp.divtmap` (texturemap), `fp.divmapchan` (integer), `fp.divmapnoise` (float)
- Cluster size: `fp.clusize` (worldUnits) -- NOT `fp.clustsize`
- Cluster roughness: `fp.clurough` (float) -- NOT `fp.clustrough`
- Cluster noise: `fp.clunoise` (float) -- NOT `fp.clustnoise`
- Cluster edge: `fp.cluedge` (float) -- no `clustblur` exists
- All names confirmed via Phase 0 introspection

---

### 3.10 `set_forest_pack_edge_settings` -- Configure boundary checking

**Purpose:** Control how items are handled at area boundaries.

**Python signature:**
```python
@mcp.tool()
def set_forest_pack_edge_settings(
    name: str,
    boundary_mode: int = 0,
    falloff_density: float = 0.0,
    falloff_scale: float = 0.0,
) -> str:
    """Configure edge/boundary behavior for a Forest Pack object.

    Controls how items near the edge of an area boundary are handled --
    point-based, size-based, or edge-based checking, plus falloff curves
    for density and scale near boundaries.

    Args:
        name: The Forest Pack object name.
        boundary_mode: 0 = Point (default), 1 = Size, 2 = Edge (V-Ray only).
        falloff_density: Density falloff at boundaries (0 = none).
        falloff_scale: Scale falloff at boundaries (0 = none).
    """
```

**MAXScript approach (confirmed property names):**
- Edge/boundary checking mode is per-area via `fp.arboundchecklist` (integer array) -- NOT a single `fp.edgemode`
- Falloff density per-area: `fp.arflafdenslist` (float array) -- NOT `fp.falldensity`
- Falloff scale per-area: `fp.arflafscalist` (float array) -- NOT `fp.fallscale`
- Falloff invert per-area: `fp.arflinvlist` (boolean array)
- NOTE: edge settings are per-area, not global. Tool signature may need revision to accept `area_index`.

---

### 3.11 `set_forest_pack_transform` -- Configure full transform variation

**Purpose:** Set detailed per-axis scale, rotation, and translation variation with optional map control.

**Python signature:**
```python
@mcp.tool()
def set_forest_pack_transform(
    name: str,
    scale_enabled: bool | None = None,
    scale_lock: bool | None = None,
    scale_x_min: float | None = None,
    scale_x_max: float | None = None,
    scale_y_min: float | None = None,
    scale_y_max: float | None = None,
    scale_z_min: float | None = None,
    scale_z_max: float | None = None,
    rotation_enabled: bool | None = None,
    rotation_x_min: float | None = None,
    rotation_x_max: float | None = None,
    rotation_y_min: float | None = None,
    rotation_y_max: float | None = None,
    rotation_z_min: float | None = None,
    rotation_z_max: float | None = None,
    translation_enabled: bool | None = None,
    translation_x: float | None = None,
    translation_y: float | None = None,
    translation_z: float | None = None,
    mirror_x: bool | None = None,
) -> str:
    """Configure full transform variation on a Forest Pack object.

    Controls per-axis scale, rotation, and translation randomization.
    Only provided (non-None) parameters are changed.

    Scale values are percentages of original size (100 = 1:1).
    Rotation values are in degrees.
    Translation values are percentages of tree width (X/Y) or height (Z).

    Args:
        name: The Forest Pack object name.
        scale_enabled: Enable/disable scale variation.
        scale_lock: Lock all axes to same scale.
        scale_x_min/max: X-axis scale range (percent).
        scale_y_min/max: Y-axis scale range (percent).
        scale_z_min/max: Z-axis scale range (percent).
        rotation_enabled: Enable/disable rotation variation.
        rotation_x_min/max: X-axis rotation range (degrees).
        rotation_y_min/max: Y-axis rotation range (degrees).
        rotation_z_min/max: Z-axis rotation range (degrees).
        translation_enabled: Enable/disable translation variation.
        translation_x: X translation (% of width).
        translation_y: Y translation (% of width).
        translation_z: Z translation (% of height).
        mirror_x: Enable horizontal mirroring.
    """
```

**MAXScript approach (confirmed property names):**
- Scale: `fp.applyscale`, `fp.scalelock` (integer), `fp.scalexmin`, `fp.scalexmax`, `fp.scaleymin`, `fp.scaleymax`, `fp.scalezmin`, `fp.scalezmax` (all integer)
- Scale maps: `fp.scamapx`, `fp.scamapy`, `fp.scamapz` (boolean), `fp.scamap` (texturemap), `fp.scamapchan` (integer), `fp.scacolormap`, `fp.scaprobmap` (boolean), `fp.usescaprobcurve` (boolean), `fp.scaprobcurve` (maxObject)
- Rotation: `fp.applyrotation`, `fp.xrotmin`, `fp.xrotmax`, `fp.yrotmin`, `fp.yrotmax`, `fp.zrotmin`, `fp.zrotmax` (all integer)
- Rotation maps: `fp.rotmapx`, `fp.rotmapy`, `fp.rotmapz` (boolean), `fp.rotmap` (texturemap), `fp.rotmapchan` (integer), `fp.rotcolormap`, `fp.rotprobmap` (boolean), `fp.userotprobcurve` (boolean), `fp.rotprobcurve` (maxObject)
- Translation: `fp.applytranslation` (boolean), `fp.transxmin`, `fp.transymin`, `fp.transzmin`, `fp.transxmax`, `fp.transymax`, `fp.transzmax` (all integer)
- Translation maps: `fp.transmapx`, `fp.transmapy`, `fp.transmapz` (boolean), `fp.transmap` (texturemap), `fp.transmapchan` (integer), `fp.transcolormap`, `fp.transprobmap` (boolean)
- Mirror: `fp.mirror` (boolean) -- NOT `fp.mirrorX` / `fp.useMirrorCustom`

---

### 3.12 `set_forest_pack_color_variation` -- Configure tint/color variation

**Purpose:** Add per-item color tinting for natural variation.

**Python signature:**
```python
@mcp.tool()
def set_forest_pack_color_variation(
    name: str,
    tint_enabled: bool = True,
    tint_color_1: list[int] | None = None,
    tint_color_2: list[int] | None = None,
    tint_strength_min: float = 0.0,
    tint_strength_max: float = 30.0,
    variation_mode: int = 0,
    hue_shift: float = 0.0,
    saturation: float = 0.0,
    brightness: float = 0.0,
) -> str:
    """Configure color tint and variation on a Forest Pack object.

    Adds random color tinting to scattered items for natural variation.
    Works with gradient mode (two colors) or map-based mode.

    Args:
        name: The Forest Pack object name.
        tint_enabled: Enable color tinting.
        tint_color_1: First gradient color as [R, G, B] (0-255).
        tint_color_2: Second gradient color as [R, G, B] (0-255).
        tint_strength_min: Minimum tint opacity (0-100%).
        tint_strength_max: Maximum tint opacity (0-100%).
        variation_mode: 0 = per-object, 1 = per-element.
        hue_shift: Color correction hue shift (degrees).
        saturation: Saturation adjustment (-100 to 100).
        brightness: Brightness adjustment (-100 to 100).
    """
```

**MAXScript approach (confirmed property names):**
- Tint mode: `fp.tintmode` (integer) -- NOT ~~`fp.usetint`~~
- Tint mix mode: `fp.tintmixmode` (integer)
- Tint color 1: `fp.tintcolor1` (color) -- CONFIRMED
- Tint color 2: `fp.tintcolor2` (color) -- CONFIRMED
- Tint strength min: `fp.tintmin` (integer) -- CONFIRMED
- Tint strength max: `fp.tintmax` (integer) -- CONFIRMED
- Tint texture: `fp.tintmap` (texturemap), `fp.tintmapmode` (integer), `fp.tintmapchan` (integer)
- Hue shift: `fp.mathue` (float) -- NOT ~~`fp.hueshift`~~
- Saturation: `fp.matsaturation` (float) -- NOT ~~`fp.saturation`~~
- Brightness: `fp.matbrightness` (float) -- NOT ~~`fp.brightness`~~
- Color correction enable: `fp.matapply` (boolean), `fp.matapplycolor` (color), `fp.matrangewidth` (float)
- Color values converted to MAXScript `color R G B` format

---

### 3.13 `set_forest_pack_camera_clipping` -- Camera-based optimization

**Purpose:** Limit scatter to visible area for render performance.

**Python signature:**
```python
@mcp.tool()
def set_forest_pack_camera_clipping(
    name: str,
    limit_to_visibility: bool = True,
    expand_percent: float = 15.0,
    far_clip_enabled: bool = False,
    far_clip_distance_cm: float = 10000.0,
    back_offset_cm: float = 0.0,
    camera_node: str | None = None,
) -> str:
    """Configure camera-based clipping and optimization on a Forest Pack object.

    Limits item creation to the camera's visible area to improve render
    performance. Essential for large-scale environments.

    Args:
        name: The Forest Pack object name.
        limit_to_visibility: Only scatter within camera's field of view.
        expand_percent: Expand FOV by this percentage to prevent edge popping.
        far_clip_enabled: Enable far clipping plane.
        far_clip_distance_cm: Maximum distance from camera in cm.
        back_offset_cm: Extend creation behind camera position in cm.
        camera_node: Specific camera object name. If None, uses active viewport camera.
    """
```

**MAXScript approach (confirmed property names):**
- Camera node: `fp.camera` (node) -- NOT ~~`fp.camobj`~~
- Limit to camera: `fp.camlimit` (boolean) -- NOT ~~`fp.limitvisibility`~~
- Camera width (expand FOV): `fp.camwidth` (integer) -- NOT ~~`fp.expand`~~
- Near clip: `fp.camnear` (worldUnits)
- Far clip: `fp.camfar` (worldUnits) -- NOT ~~`fp.farclipDist`~~
- Back offset: `fp.cambho` (worldUnits) -- NOT ~~`fp.backoffset`~~
- Look-at target: `fp.lookattarget` (node), `fp.uselookat` (boolean), `fp.camlookat` (boolean)
- LOD by distance: `fp.camlod` (boolean), `fp.camloddist` (worldUnits), `fp.camlodlookat` (boolean)
- Density curve: `fp.camdenscurve` (maxObject), `fp.camdensact` (boolean), `fp.camdensear`/`fp.camdensfar` (worldUnits)
- Scale curve: `fp.camscacurve` (maxObject), `fp.camscaact` (boolean)

---

### 3.14 `set_forest_pack_animation` -- Animation offset control

**Purpose:** Control how animated source objects play back across scattered instances.

**Python signature:**
```python
@mcp.tool()
def set_forest_pack_animation(
    name: str,
    animation_mode: int = 0,
    sample_count: int = 10,
    time_offset: int = 5,
    start_frame: int = 0,
    end_frame: int = 100,
    map_variable: str | None = None,
) -> str:
    """Configure animation playback for scattered instances.

    Controls how animated source geometry is played back across the
    scattered population, creating natural variation in wind sway, etc.

    Args:
        name: The Forest Pack object name.
        animation_mode: Animation method:
            0 = Disabled (static)
            1 = Follow Geometry (all instances sync)
            2 = Random Samples (random start frames)
            3 = Random from Map (map-driven sample selection)
            4 = Frame from Map (absolute frame from grayscale map)
        sample_count: Number of animation samples (modes 2, 3).
        time_offset: Time offset between samples in frames (mode 2).
        start_frame: Start frame for frame range (mode 4).
        end_frame: End frame for frame range (mode 4).
        map_variable: MAXScript global variable for animation map (modes 3, 4).
    """
```

**MAXScript approach (confirmed property names):**
- Animation mode: `fp.animation` (integer) -- NOT ~~`fp.animmode`~~
- Animation samples: `fp.animsamples` (integer) -- CONFIRMED
- Time offset: `fp.animsoffset` (time) -- NOT ~~`fp.animoffset`~~
- Start/end frame: `fp.animstart` (time), `fp.animend` (time) -- CONFIRMED
- Animation map: `fp.animap` (texturemap) -- NOT ~~`fp.animmap`~~
- Animation map channel: `fp.animapchan` (integer)
- Render only: `fp.animonlyrend` (boolean)

---

### 3.15 `set_forest_pack_lod` -- Level of Detail configuration

**Purpose:** Configure LOD switching for large-scale scenes.

**Python signature:**
```python
@mcp.tool()
def set_forest_pack_lod(
    name: str,
    override_max_distance_cm: float = 0.0,
    use_environment_range: bool = False,
) -> str:
    """Configure Level of Detail settings on a Forest Pack object.

    LOD switches geometry between high and low detail versions based on
    camera distance. Requires ForestLOD objects in the geometry list.

    Args:
        name: The Forest Pack object name.
        override_max_distance_cm: Override the LOD max distance in cm (0 = use per-item values).
        use_environment_range: Derive max distance from active camera's environment range.
    """
```

**MAXScript approach (confirmed property names):**
- Camera LOD enabled: `fp.camlod` (boolean) -- NOT ~~`fp.lodoverridedist`~~
- LOD distance: `fp.camloddist` (worldUnits)
- LOD look-at: `fp.camlodlookat` (boolean) -- NOT ~~`fp.lodusenvrange`~~
- Camera density/scale curves: `fp.camdenscurve` (maxObject), `fp.camdensact` (boolean), `fp.camscacurve` (maxObject), `fp.camscaact` (boolean), `fp.camdensear` (worldUnits), `fp.camdensfar` (worldUnits)
- NOTE: LOD is configured via ForestLOD helper objects (19 props including mode, distance, variation, distlist, screensizelist) used in the geometry list, combined with camera-level LOD toggles on the Forest_Pro object

---

### 3.16 `set_forest_pack_surface_settings` -- Surface altitude/slope limits

**Purpose:** Control scatter based on terrain altitude and slope.

**Python signature:**
```python
@mcp.tool()
def set_forest_pack_surface_settings(
    name: str,
    direction: int | None = None,
    altitude_limited: bool | None = None,
    altitude_top_cm: float | None = None,
    altitude_bottom_cm: float | None = None,
    slope_limited: bool | None = None,
    slope_min_deg: float | None = None,
    slope_max_deg: float | None = None,
    uv_mode: bool | None = None,
    scale_to_slope: bool | None = None,
) -> str:
    """Configure surface constraints for a Forest Pack object.

    Controls altitude range, slope limits, UV mode, and direction alignment
    for terrain-based scattering.

    Args:
        name: The Forest Pack object name.
        direction: -100 (down) to 0 (normal) to 100 (up). Use 0 for normal-aligned, 100 for world-up.
        altitude_limited: Enable altitude range restriction.
        altitude_top_cm: Maximum altitude in cm (property: altmax).
        altitude_bottom_cm: Minimum altitude in cm (property: altmin).
        slope_limited: Enable slope angle restriction.
        slope_min_deg: Minimum slope angle (0 = horizontal).
        slope_max_deg: Maximum slope angle (90 = vertical).
        uv_mode: Use UV mapping coordinates instead of XY plane (property: uvalign).
        scale_to_slope: Scale items proportionally to terrain slope (property: scalelope).
    """
```

**MAXScript approach (confirmed property names):**
- Direction: `fp.direction` (integer) -- CONFIRMED
- Altitude limited: `fp.altlimited` (boolean) -- CONFIRMED
- Altitude max: `fp.altmax` (worldUnits) -- NOT ~~`fp.alttop`~~
- Altitude min: `fp.altmin` (worldUnits) -- NOT ~~`fp.altbottom`~~
- Altitude affects density: `fp.surfaltdens` (boolean), scale: `fp.surfaltscal` (boolean)
- Slope limited: `fp.slopelimited` (boolean) -- CONFIRMED
- Slope min: `fp.slopemin` (float) -- CONFIRMED
- Slope max: `fp.slopemax` (float) -- CONFIRMED
- Slope affects density: `fp.surfslodens` (boolean), scale: `fp.surfsloscal` (boolean)
- UV mode: `fp.uvalign` (boolean), `fp.uvscalex` (boolean), `fp.uvscaley` (boolean), `fp.uvmultscalex` (float), `fp.uvmultscaley` (float)
- Scale to slope: `fp.scalelope` (boolean)
- Surface mode: `fp.surfmode` (integer), `fp.surfanim` (boolean), `fp.linkeditsurf` (boolean)

---

### 3.17 `set_forest_pack_path_distribution` -- Path/spline distribution mode

**Purpose:** Distribute items along spline paths instead of over surfaces.

**Python signature:**
```python
@mcp.tool()
def set_forest_pack_path_distribution(
    name: str,
    splines: list[str],
    spacing_cm: float = 100.0,
    use_vertex_positions: bool = False,
    follow_path_x: bool = True,
    follow_path_z: bool = False,
    offset_cm: float = 0.0,
    randomize_position: float = 0.0,
    geometry_order: int = 0,
) -> str:
    """Set a Forest Pack object to path distribution mode.

    Distributes items at regular intervals along spline paths.
    Useful for fences, hedges, street lights, and similar linear distributions.

    Args:
        name: The Forest Pack object name.
        splines: List of spline object names to distribute along.
        spacing_cm: Distance between items in cm.
        use_vertex_positions: Place items only at spline vertices.
        follow_path_x: Rotate items to follow spline direction on X axis.
        follow_path_z: Rotate items to follow spline direction on Z axis.
        offset_cm: Perpendicular offset from spline in cm.
        randomize_position: Random position variation (0.0-1.0).
        geometry_order: 0 = Sequence, 1 = Random geometry assignment along path.
    """
```

**MAXScript approach (confirmed property names):**
- Switch distribution mode: `fp.distmode` (integer) -- set to path mode value
- Path nodes: `fp.distpathnodes` (node array)
- Path mode: `fp.distpathmode` (integer)
- Path geometry ID: `fp.distpathgeomid` (integer)
- Spacing: `fp.distpathspacing` (worldUnits) -- NOT ~~`fp.pathspacing`~~
- Offset: `fp.distpathoffset` (worldUnits) -- NOT ~~`fp.pathoffset`~~
- Random position: `fp.distpathrandpos` (worldUnits)
- Follow X: `fp.distpathxfollow` (boolean) -- NOT ~~`fp.pathfollow`~~
- Follow Z: `fp.distpathzfollow` (boolean)
- Also available: Reference distribution (`fp.distrefnodes`, `fp.distrefmode`, `fp.distrefgetrot`, `fp.distrefgetscale`, `fp.distrefnumitems`, `fp.distrefrandpos`, `fp.distrefmatid`, `fp.distrefmatchname`, `fp.distrefmatchregex`) and PFlow distribution (`fp.distpflownodes`, `fp.distpflowgetrot`, `fp.distpflowgetscale`, `fp.distpflowallevents`, `fp.distpfloweventslist`)

---

### 3.18 `load_forest_pack_preset` -- Load from library

**Purpose:** Load a complete preset from the Forest Pack library.

**Python signature:**
```python
@mcp.tool()
def load_forest_pack_preset(
    preset_file: str,
    name: str = "ForestPreset",
    surfaces: list[str] | None = None,
) -> str:
    """Load a Forest Pack preset from a .fpe file or library path.

    Forest Pack presets contain pre-configured geometry, distribution,
    and material settings for common vegetation scenarios.

    Args:
        preset_file: Path to a .fpe preset file, or a library preset name.
        name: Name for the created Forest Pack object.
        surfaces: Optional surface objects. If None, creates without surfaces.
    """
```

**MAXScript approach:**
- This may require using the Forest Pack library browser interface
- Alternatively, presets may be loadable via `fp.loadPreset "<path>"` (needs interface discovery)
- Fallback: read preset file properties and apply them programmatically

---

## 4. MAXScript Implementation Details

### 4.1 Common patterns

All Forest Pack tools share these patterns:

**Node resolution with class validation:**
```maxscript
local fp = getNodeByName "<name>"
if fp == undefined then (
    "{\"error\":\"Object not found: <name>\"}"
) else if (classOf fp.baseObject) != Forest_Pro then (
    "{\"error\":\"Not a Forest Pack object\"}"
) else (
    -- tool logic here
)
```

**Unit conversion (always use for cm-based params):**
```maxscript
local valueWU = units.decodeValue "<value>cm"
```

**Reading array properties safely:**
```maxscript
local arr = #()
try (arr = fp.<arrayProp>) catch ()
```

**JSON string building (project convention):**
```maxscript
local result = "{"
result += "\"key\": \"value\""
result += "}"
```

### 4.2 Area list synchronization protocol

This is the most error-prone aspect of Forest Pack scripting. Phase 0 introspection confirmed **27 area arrays** (plus `pf_aractivelist`) with the `ar*` prefix. All synchronized arrays MUST always be kept in sync.

**Core 7 arrays** (minimum required, used by existing `scatter_forest_pack`):

| Array | Purpose | Per-element type |
|-------|---------|-----------------|
| `arnodelist` | Scene node reference | node or undefined |
| `arnamelist` | Display name | string |
| `artypelist` | Area type (0=spline, 1=object, 2=forest, 3=surface, 4=paint) | integer |
| `arincexclist` | Include(0) or Exclude(1) | integer |
| `arprojectlist` | Projection mode | integer |
| `pf_aractivelist` | Active state | boolean |
| `aridlist` | Unique integer ID | integer |

**Additional area arrays** (confirmed via Phase 0 introspection -- all synchronized per-area):

| Array | Purpose | Per-element type |
|-------|---------|-----------------|
| `arnodenamelist` | Node name cache | string |
| `arresollist` | Resolution | integer |
| `arslicelist` | Slice enabled | boolean |
| `arslicetoplist` | Slice top height | worldUnits |
| `arwidthlist` | Width | worldUnits |
| `arforceopenlist` | Force open spline | boolean |
| `armaplist` | Per-area density map | texturemap |
| `arscalelist` | Per-area scale | float |
| `arthresholdlist` | Per-area threshold | float |
| `arsurfidlist` | Surface ID filter | string |
| `arflafdenslist` | Falloff density | float |
| `arflafscalist` | Falloff scale | float |
| `arflinvlist` | Falloff invert | boolean |
| `arselspeclist` | Species selection enabled | boolean |
| `arspeclist` | Species selection list | string |
| `arpaintlist` | Paint data | maxObject |
| `arboundchecklist` | Boundary check mode | integer |
| `arshapelist` | Shape mode | integer |
| `arobscalelist` | Object scale | float |
| `arlinkidlist` | Link ID | integer |
| `arscalemin` | Per-area scale minimum | float |
| `arscalemax` | Per-area scale maximum | float |
| `arzoffset` | Per-area Z offset | worldUnits |

**Rules:**
1. All synchronized arrays must have the same count at all times
2. When adding: append to ALL arrays (core 7 + any additional arrays that are populated), then set ALL back
3. When removing: delete from ALL arrays at same index, then set ALL back
4. `pf_aractivelist` must be `true` for each area that should produce results
5. `aridlist` values must be unique integers (use max+1 for new entries)
6. For new tools that only need basic areas, the core 7 arrays are sufficient -- Forest Pack initializes additional arrays with defaults

### 4.3 Geometry list synchronization protocol

Source geometry arrays must also stay in sync. Phase 0 introspection confirmed **20 source geometry arrays**:

**Core 6 arrays** (used by existing `scatter_forest_pack`):

| Array | Purpose | Per-element type |
|-------|---------|-----------------|
| `cobjlist` | Scene node reference | node |
| `namelist` | Display name | string |
| `problist` | Probability weight | float |
| `geomlist` | Geometry type (2 = custom object) | integer |
| `widthlist` | Source width | worldUnits |
| `heightlist` | Source height | worldUnits |

**Additional source geometry arrays** (confirmed via Phase 0 introspection):

| Array | Purpose | Per-element type |
|-------|---------|-----------------|
| `matlist` | Material override | material |
| `coloridlist` | Color ID | point3 |
| `tempidlist` | Template ID | integer |
| `tempnamelist` | Template name | string |
| `scalelist` | Source scale | float |
| `zoffsetlist` | Z offset | worldUnits |
| `centerlist` | Center mode | integer |
| `radiuslist` | Radius | integer |
| `specidlist` | Species ID | integer |
| `usemeshdimlist` | Use mesh dimensions | boolean |
| `conamelist` | Custom object name | string |
| `includechildlist` | Include children | boolean |
| `keepgrouplist` | Keep group | boolean |
| `nongeomlist` | Non-geometry flag | boolean |

**Rules:**
1. All arrays must have same count
2. `geomlist` should be `2` for every custom object
3. `problist` values are relative weights (Forest Pack normalizes them)
4. `old_problist` (integer array) exists for legacy compatibility but `problist` (float array) should be used

### 4.4 Property name verification

> **Phase 0 introspection COMPLETED 2026-03-03.** All 341 property names are now confirmed. See `docs/research/forest_pack_introspection.md` for the full dump.

**All verified property names** (confirmed via live introspection):

*From existing `scatter_forest_pack` tool (unchanged):*
- `fp.surflist`, `fp.cobjlist`, `fp.namelist`, `fp.problist`, `fp.geomlist`
- `fp.arnodelist`, `fp.arnamelist`, `fp.artypelist`, `fp.arincexclist`, `fp.arprojectlist`, `fp.pf_aractivelist`, `fp.aridlist`
- `fp.widthlist`, `fp.heightlist`
- `fp.maxdensity`, `fp.units_x`, `fp.units_y`
- `fp.seed`, `fp.iconsize`, `fp.vmesh`, `fp.rmesh`, `fp.direction`
- `fp.applyscale`, `fp.scalelock`, `fp.scalexmin`, `fp.scalexmax`, `fp.scaleymin`, `fp.scaleymax`, `fp.scalezmin`, `fp.scalezmax`
- `fp.applyrotation`, `fp.zrotmin`, `fp.zrotmax`

*Newly confirmed -- corrections from original guesses are marked with ~~strikethrough~~:*
- Distribution map: `fp.distmap` (texturemap) -- confirmed
- Distribution mode: `fp.distmode` (integer) -- NOT ~~`fp.maptype`~~
- Density map toggle: `fp.densityMap` (boolean)
- Diversity: `fp.divers` (integer) -- NOT ~~`fp.diversity`~~
- Diversity map: `fp.divtmap` (texturemap), `fp.divmapchan`, `fp.divmapnoise`
- Cluster size: `fp.clusize` (worldUnits) -- NOT ~~`fp.clustsize`~~
- Cluster roughness: `fp.clurough` (float) -- NOT ~~`fp.clustrough`~~
- Cluster noise: `fp.clunoise` (float) -- NOT ~~`fp.clustnoise`~~
- Cluster edge: `fp.cluedge` (float) -- ~~`fp.clustblur`~~ does NOT exist
- Collision: `fp.collision` (boolean), `fp.radius` (integer), `fp.collheight` (integer) -- NOT ~~`fp.collradius`~~
- Camera: `fp.camera` (node), `fp.camlimit` (boolean), `fp.camwidth` (integer), `fp.camnear` (worldUnits), `fp.camfar` (worldUnits), `fp.cambho` (worldUnits) -- NOT ~~`fp.limitvisibility`~~, ~~`fp.expand`~~, ~~`fp.farclip`~~, ~~`fp.farclipDist`~~, ~~`fp.backoffset`~~, ~~`fp.camobj`~~
- Look-at: `fp.lookattarget` (node), `fp.uselookat` (boolean), `fp.camlookat` (boolean)
- Camera LOD: `fp.camlod` (boolean), `fp.camloddist` (worldUnits), `fp.camlodlookat` (boolean)
- Camera density/scale curves: `fp.camdenscurve`, `fp.camdensact`, `fp.camscacurve`, `fp.camscaact`, `fp.camdensear`, `fp.camdensfar`
- Tint mode: `fp.tintmode` (integer) -- NOT ~~`fp.usetint`~~
- Tint mix: `fp.tintmixmode` (integer)
- Tint colors: `fp.tintcolor1` (color), `fp.tintcolor2` (color) -- confirmed
- Tint range: `fp.tintmin` (integer), `fp.tintmax` (integer) -- confirmed
- Tint map: `fp.tintmap` (texturemap), `fp.tintmapmode`, `fp.tintmapchan`
- Color correction: `fp.mathue` (float), `fp.matsaturation` (float), `fp.matbrightness` (float) -- NOT ~~`fp.hueshift`~~, ~~`fp.saturation`~~, ~~`fp.brightness`~~
- Color correction enable: `fp.matapply` (boolean), `fp.matapplycolor` (color), `fp.matrangewidth` (float)
- Animation mode: `fp.animation` (integer) -- NOT ~~`fp.animmode`~~
- Animation samples: `fp.animsamples` (integer) -- confirmed
- Animation offset: `fp.animsoffset` (time) -- NOT ~~`fp.animoffset`~~
- Animation map: `fp.animap` (texturemap) -- NOT ~~`fp.animmap`~~
- Animation range: `fp.animstart` (time), `fp.animend` (time), `fp.animapchan` (integer), `fp.animonlyrend` (boolean)
- Surface altitude: `fp.altlimited` (boolean), `fp.altmax` (worldUnits), `fp.altmin` (worldUnits) -- NOT ~~`fp.alttop`~~, ~~`fp.altbottom`~~
- Surface slope: `fp.slopelimited` (boolean), `fp.slopemin` (float), `fp.slopemax` (float) -- confirmed
- Surface extras: `fp.surfaltdens`, `fp.surfaltscal`, `fp.surfslodens`, `fp.surfsloscal`, `fp.surfanim`, `fp.surfmode`, `fp.scalelope`
- Translation: `fp.applytranslation` (boolean), `fp.transxmin`-`fp.transzmax` (integer) -- confirmed (NOT ~~`fp.applyTranslation`~~ with capital T)
- Translation maps: `fp.transmapx/y/z` (boolean), `fp.transmap` (texturemap), `fp.transmapchan`, `fp.transcolormap`, `fp.transprobmap`
- Mirror: `fp.mirror` (boolean) -- NOT ~~`fp.mirrorX`~~, ~~`fp.useMirrorCustom`~~
- Path distribution: `fp.distpathnodes` (node array), `fp.distpathmode`, `fp.distpathspacing` (worldUnits), `fp.distpathoffset` (worldUnits), `fp.distpathrandpos` (worldUnits), `fp.distpathxfollow`, `fp.distpathzfollow` -- NOT ~~`fp.pathspacing`~~, ~~`fp.pathfollow`~~, ~~`fp.pathoffset`~~
- Edge/falloff: per-area arrays `fp.arboundchecklist`, `fp.arflafdenslist`, `fp.arflafscalist`, `fp.arflinvlist` -- NOT ~~`fp.edgemode`~~, ~~`fp.falldensity`~~, ~~`fp.fallscale`~~
- LOD: `fp.camlod`, `fp.camloddist`, `fp.camlodlookat` -- NOT ~~`fp.lodoverridedist`~~, ~~`fp.lodusenvrange`~~
- Threads: `fp.threads` (integer), `fp.autothreads` (boolean) -- NOT ~~`fp.cputhreads`~~
- Global: `fp.globsize` (boolean), `fp.width` (worldUnits), `fp.height` (worldUnits), `fp.globscale` (float), `fp.consmat` (boolean), `fp.mode` (integer), `fp.consgeom` (boolean)

### 4.5 trees Interface (per-item manipulation)

The `trees` interface provides full CRUD operations on individual scattered items. Confirmed via Phase 0 introspection.

**Access:** `fp.trees` where `fp` is a Forest_Pro node.

**Methods (confirmed):**

| Method | Signature | Description |
|--------|-----------|-------------|
| `create` | `(point3 p, float width, float height, integer geomid)` | Create a new tree at position |
| `delete` | `(integer n)` | Delete tree by index |
| `edit` | `(integer n, float width, float height, integer geomid, integer seed)` | Edit tree properties |
| `count` | `() -> integer` | Get total tree count |
| `move` | `(integer n, point3 p)` | Move tree to new position |
| `setPosition` | `(integer n, point3 p)` | Set absolute position |
| `getPosition` | `(integer n) -> point3` | Get position |
| `setRotation` | `(integer n, point3 angle)` | Set rotation (Euler) |
| `getRotation` | `(integer n) -> point3` | Get rotation |
| `setWidth` | `(integer n, float width)` | Set width |
| `getWidth` | `(integer n) -> float` | Get width |
| `setHeight` | `(integer n, float height)` | Set height |
| `getHeight` | `(integer n) -> float` | Get height |
| `setSize` | `(integer n, point3 size)` | Set size (width, height, scale) |
| `getSize` | `(integer n) -> point3` | Get size |
| `setGeomID` | `(integer n, integer geomid)` | Set geometry ID (which source) |
| `getGeomID` | `(integer n) -> integer` | Get geometry ID |
| `setSeed` | `(integer n, integer seed)` | Set random seed |
| `getSeed` | `(integer n) -> integer` | Get random seed |
| `getFullTransform` | `(integer n) -> matrix3` | Get full 4x4 transform |
| `getSelected` | `() -> integer` | Get selected tree index |
| `update` | `()` | Refresh scatter (recompute) |
| `update_ui` | `()` | Refresh UI display |

**Render helpers:** `getRenderID`, `getRenderNode`, `getRenderNodes`, `clearRenderNodes`, `getRenderData`, `resetCreatedVersion`, `setCreatedVersion`

**Usage example (MAXScript):**
```maxscript
-- Place 10 custom trees in a grid
local fp = $MyForest
local iface = fp.trees
for i = 0 to 9 do (
    local pos = [i * 100.0, 0, 0]
    iface.create pos 10.0 50.0 1  -- position, width, height, geomid
)
iface.update()
```

### 4.6 Helper classes (confirmed)

**ForestLOD** (19 properties):
- Source arrays: `cobjlist`, `matlist`, `namelist`, `geomlist`, `tempidlist`, `tempnamelist`, `widthlist`, `heightlist`, `scalelist`, `zoffsetlist`, `centerlist`, `specidlist`
- LOD: `distlist`, `screensizelist`, `iconsize`, `mode`, `distance`, `variation`, `update`

**ForestSet** (7 properties):
- `nodelist`, `iconsize`, `layerimport`, `layerchilds`, `layernames`, `wirecolor`, `disabled`

**ForestColor** (18 properties):
- `mapbase`, `mapidmode`, `colorbase`, `maplist`, `maponlist`, `colorlist`, `problist`
- `tintmixmode`, `tintvariation`, `override`, `tintcolor1`, `tintcolor2`, `tintmin`, `tintmax`, `tintmode`, `tintmap`, `tintmapmode`, `applycor`

**Forest_Lite:** NOT FOUND in this installation (3ds Max 2025 with Forest Pack Pro).

### 4.7 Additional interfaces (confirmed)

**ForestPack interface** (`fp.ForestPack`):
- `registerEngine()`, `exportData(string filename, string fieldlist) -> integer`, `setEngineFeatures(integerPtr features)`, `openLister()`, `getRenderDataRaw() -> integerPtr`, `clearRenderDataRaw()`, `version() -> integer`

**ui interface** (`fp.ui`):
- `setRollup(integer64 state)` -- control UI rollup state

**scatalog / catalog interface** (`fp.scatalog` or `fp.catalog`):
- Browser control: `openBrowser()`, `closeBrowser()`, `refresh()`, `getMacroCount()`, `evalMacro()`, `getMacro()`, `setMacro()`, `setOverlay()`, `getSelItemName()`, `getSelItemProp()`, `getSelItemCustomProp()`

---

### 4.8 Confirmed Property Categories (all 341 properties)

Complete reference organized by category. See `docs/research/forest_pack_introspection.md` for full details with types.

**Source Geometry** (20 arrays):
cobjlist, matlist, namelist, coloridlist, geomlist, tempidlist, tempnamelist, widthlist, heightlist, scalelist, zoffsetlist, centerlist, radiuslist, specidlist, usemeshdimlist, conamelist, includechildlist, keepgrouplist, nongeomlist, problist (+ old_problist legacy)

**Area** (27 arrays + pf_aractivelist):
aridlist, pf_aractivelist, arnamelist, arnodelist, arnodenamelist, artypelist, arincexclist, arresollist, arslicelist, arslicetoplist, arwidthlist, arforceopenlist, armaplist, arscalelist, arthresholdlist, arsurfidlist, arflafdenslist, arflafscalist, arflinvlist, arselspeclist, arspeclist, arpaintlist, arboundchecklist, arprojectlist, arshapelist, arobscalelist, arlinkidlist, arscalemin, arscalemax, arzoffset

**Distribution**:
distmap, distmapchan, densityMap, distmode, pixels_x, pixels_y, units_x, units_y, lock_ratio, collision, radius, collheight, collpreview, offset_x, offset_y, drotation, threshold, maxdensity, sdgizmo, divers, divtmap, divmapchan, divmapnoise, clusize, clurough, clunoise, cluedge

**Distribution Modes**:
distpathnodes, distpathmode, distpathgeomid, distpathspacing, distpathoffset, distpathrandpos, distpathxfollow, distpathzfollow, distrefnodes, distrefmode, distrefgetrot, distrefgetscale, distrefnumitems, distrefrandpos, distrefmatid, distrefmatchname, distrefmatchregex, distpflownodes, distpflowgetrot, distpflowgetscale, distpflowallevents, distpfloweventslist

**Surface**:
surflist, surflink, altlimited, altmax, altmin, surfaltdens, surfaltscal, slopelimited, slopemax, slopemin, surfslodens, surfsloscal, surfanim, linkeditsurf, direction, scalelope, surfmode, uvalign, uvscalex, uvscaley, uvmultscalex, uvmultscaley

**Transform**:
applytranslation, transxmin, transymin, transzmin, transxmax, transymax, transzmax, transmapx, transmapy, transmapz, transmap, transmapchan, transcolormap, transprobmap, applyrotation, xrotmin, xrotmax, yrotmin, yrotmax, zrotmin, zrotmax, rotmapx, rotmapy, rotmapz, userotprobcurve, rotprobcurve, rotmap, rotmapchan, rotcolormap, rotprobmap, applyscale, scalexmax, scalexmin, scaleymax, scaleymin, scalezmax, scalezmin, scamapx, scamapy, scamapz, usescaprobcurve, scaprobcurve, scamap, scamapchan, scacolormap, scaprobmap, scalelock, mirror

**Camera/LOD**:
camera, lookattarget, camlimit, uselookat, camlookat, camlod, camloddist, camlodlookat, camwidth, camnear, camfar, cambho, camdenscurve, camdensact, camscacurve, camscaact, camdensear, camdensfar

**Tint/Color**:
tintmixmode, tintcolor1, tintcolor2, tintmin, tintmax, tintmode, tintmap, tintmapmode, tintmapchan, fastopac, tracedepth, opaclevel, selfillum, irradiance, mathue, matsaturation, matbrightness, matapply, matapplycolor, matrangewidth

**Animation**:
animation, animsoffset, animsamples, animonlyrend, animap, animapchan, animstart, animend

**Shadow**:
usefakeshadows, light, hshadow, vshadow, hsplanes, custshadow, hsoffset, hsscale, selfshadow, ssitself

**Display/Render**:
vmesh, geomtexid, vtype, adaptfaces, cloudcolorid, cloudens, vmaxitems, rmesh, rskip, opacity, wireframe, rtype, rendermode, rmaxitems, maxfaces, hidecustom, manualupdate, disabled, dispflags, iconsize

**Effects**:
efidlist, efnamelist, efxmllist, efenablelist, efselspeclist, efspeclist, pf_efonlyrender, efpaid, efpaeffid, efpatype, efpaname, efpalimit, efpadesc, efpanumtype, efpaintval, efpaintmin, efpaintmax, efpaintdef, efpafloatval, efpafloatmin, efpafloatmax, efpafloatdef, efpaunitval, efpaunitmin, efpaunitmax, efpaunitdef, efpainode, efpaspline, efpacontref, efpacontanim, efpacontype, efpatexmap, efpacurve

**Global**:
seed, seedtype, threads, autothreads, geomtex, savedversion, renderid, globsize, width, height, globscale, consmat, mode, consgeom

**Spline Density/Scale Curves**:
spdenscurve, spdensact, spdensinc, spdensexc, spscalcurve, spscalact, spscalz, spscalinc, spscalexc

**Reserved/Internal** (not for use):
reserved1, reserved2, reserved3, reserved7, reserved10, reserved11, reserved12, reserved13, reserved14, reserved15, reserved17, reserved18, reserved19, reserved23, reserved40, randstacked, sepsubsplines

---

## 5. Testing Strategy

### 5.1 Test file organization

Add tests to `tests/test_scattering_tools.py` (existing file). Follow the same pattern: mock `client.send_command`, verify the generated MAXScript string contains expected property assignments.

### 5.2 Per-tool test matrix

Each tool needs at minimum:

| Test | Description |
|------|-------------|
| **Happy path** | All required params, verify MAXScript contains expected assignments |
| **Missing object** | Verify error JSON returned when object not found |
| **Not Forest Pack** | Verify error when target is not Forest_Pro |
| **Optional params** | Verify only provided params appear in MAXScript |
| **Validation** | Verify Python-side validation (empty lists, invalid ranges) |

### 5.3 Integration test scripts

These are MAXScript scripts to run manually in 3ds Max for end-to-end verification:

#### Test scene setup
```maxscript
-- Create test scene for Forest Pack testing
(
    -- Ground plane
    local ground = Plane name:"TestGround" length:1000 width:1000 pos:[0,0,0]

    -- Simple box as scatter source
    local box1 = Box name:"TestTree" length:10 width:10 height:50 pos:[500,500,0]
    box1.isHidden = true

    -- Spline for area testing
    local sp = SplineShape name:"TestSpline" pos:[0,0,0]
    addNewSpline sp
    addKnot sp 1 #corner #line [-200,-200,0]
    addKnot sp 1 #corner #line [200,-200,0]
    addKnot sp 1 #corner #line [200,200,0]
    addKnot sp 1 #corner #line [-200,200,0]
    close sp 1
    updateShape sp

    -- Second spline for exclusion
    local sp2 = SplineShape name:"ExcludeSpline" pos:[0,0,0]
    addNewSpline sp2
    addKnot sp2 1 #corner #line [-50,-50,0]
    addKnot sp2 1 #corner #line [50,-50,0]
    addKnot sp2 1 #corner #line [50,50,0]
    addKnot sp2 1 #corner #line [-50,50,0]
    close sp2 1
    updateShape sp2

    "Test scene created: TestGround, TestTree, TestSpline, ExcludeSpline"
)
```

#### Verify list_forest_pack_objects
```maxscript
-- After creating a Forest Pack via scatter_forest_pack, verify listing works
-- Expected: returns array with the created object
```

#### Verify add/remove area
```maxscript
-- After scatter_forest_pack, test adding a spline exclude area
-- Then verify get_forest_pack_info shows the new area
-- Then remove it and verify count decreases
```

#### Verify distribution map
```maxscript
-- Create a Noise texture map, assign it as distribution map
-- Verify scatter pattern changes (visual check in viewport)
```

### 5.4 Unit test examples

```python
class ListForestPackObjectsTests(unittest.TestCase):
    def test_returns_empty_when_no_forest_objects(self) -> None:
        with patch.object(
            scattering.client,
            "send_command",
            return_value={"result": "[]"},
        ):
            result = scattering.list_forest_pack_objects()
        self.assertEqual(result, "[]")


class GetForestPackInfoTests(unittest.TestCase):
    def test_returns_error_for_missing_object(self) -> None:
        with patch.object(
            scattering.client,
            "send_command",
            return_value={"result": '{"error":"Object not found: Missing"}'},
        ):
            result = scattering.get_forest_pack_info("Missing")
        self.assertIn("error", result)

    def test_generates_correct_maxscript(self) -> None:
        with patch.object(
            scattering.client,
            "send_command",
            return_value={"result": "{}"},
        ) as mocked:
            scattering.get_forest_pack_info("ForestScatter001")
        maxscript = mocked.call_args.args[0]
        self.assertIn('getNodeByName "ForestScatter001"', maxscript)
        self.assertIn("Forest_Pro", maxscript)


class AddForestPackAreaTests(unittest.TestCase):
    def test_generates_area_append_maxscript(self) -> None:
        with patch.object(
            scattering.client,
            "send_command",
            return_value={"result": '{"areaCount":2}'},
        ) as mocked:
            scattering.add_forest_pack_area(
                name="ForestScatter001",
                area_name="Exclude Zone",
                area_type=0,
                include_exclude=1,
                spline_node="ExcludeSpline",
            )
        maxscript = mocked.call_args.args[0]
        self.assertIn("fp.arnodelist", maxscript)
        self.assertIn("fp.arnamelist", maxscript)
        self.assertIn("fp.artypelist", maxscript)
        self.assertIn("fp.arincexclist", maxscript)
        self.assertIn("fp.pf_aractivelist", maxscript)
        self.assertIn("fp.aridlist", maxscript)
        self.assertIn("ExcludeSpline", maxscript)


class ModifyForestPackTests(unittest.TestCase):
    def test_only_sets_provided_params(self) -> None:
        with patch.object(
            scattering.client,
            "send_command",
            return_value={"result": '{"modified":true}'},
        ) as mocked:
            scattering.modify_forest_pack(
                name="ForestScatter001",
                density=1000,
                seed=42,
            )
        maxscript = mocked.call_args.args[0]
        self.assertIn("fp.maxdensity = 1000", maxscript)
        self.assertIn("fp.seed = 42", maxscript)
        # These should NOT appear since they weren't provided
        self.assertNotIn("fp.scalexmin", maxscript)
        self.assertNotIn("fp.zrotmin", maxscript)
```

---

## 6. Implementation Order

### Phase 0/1: Introspection -- COMPLETED 2026-03-03

**Goal:** Discover the complete Forest_Pro property namespace.

1. ~~Run ALL scripts from Section 2 inside 3ds Max~~ -- DONE
2. ~~Document every discovered property with its type and default value~~ -- DONE (341 properties in `docs/research/forest_pack_introspection.md`)
3. ~~Map properties to UI rollout sections~~ -- DONE (Section 4.8)
4. ~~Verify/correct the guessed property names in Section 4.4~~ -- DONE (many corrections applied)
5. ~~Update this plan with correct property names~~ -- DONE
6. Full dump in `docs/research/forest_pack_introspection.md` (replaces `docs/forest_pack_property_reference.md`)

**Deliverable:** Verified property name mapping -- COMPLETE.

### Phase 2: Inspection Tools (Week 2)

**Goal:** Read-only tools for understanding existing Forest Pack objects.

1. `list_forest_pack_objects` -- find all FP objects in scene
2. `get_forest_pack_info` -- deep inspect a single FP object
3. Add tests for both tools
4. Manual integration test: create a Forest Pack, verify inspection output

**Dependencies:** Phase 1 (need verified property names)
**Deliverable:** 2 new tools, tests passing.

### Phase 3: Core Modification Tools (Week 3)

**Goal:** Modify existing Forest Pack objects.

1. `modify_forest_pack` -- update scalar properties
2. `set_forest_pack_surfaces` -- swap surface objects
3. `set_forest_pack_sources` -- swap source geometry
4. Add tests for all three
5. Manual integration test: create, inspect, modify, inspect again

**Dependencies:** Phase 2 (need inspection to verify changes)
**Deliverable:** 3 new tools, tests passing.

### Phase 4: Area Management (Week 4)

**Goal:** Add and remove spline/object areas.

1. `add_forest_pack_area` -- add include/exclude areas
2. `remove_forest_pack_area` -- remove areas by index
3. Add tests focused on array synchronization
4. Manual integration test: create FP, add spline exclude, verify scatter excludes region, remove area

**Dependencies:** Phase 3 (need modify to set up test state)
**Deliverable:** 2 new tools, tests passing.

### Phase 5: Distribution Controls (Week 5)

**Goal:** Texture-based density control and clustering.

1. `set_forest_pack_distribution_map` -- bitmap/procedural density map
2. `set_forest_pack_cluster_settings` -- clustering mode
3. `set_forest_pack_edge_settings` -- boundary behavior
4. Add tests
5. Manual integration test: assign Noise map as distribution, verify pattern change

**Dependencies:** Phase 1 (need verified property names for distmap, cluster, edge)
**Deliverable:** 3 new tools, tests passing.

### Phase 6: Transform and Color (Week 6)

**Goal:** Detailed variation control.

1. `set_forest_pack_transform` -- full per-axis transform control
2. `set_forest_pack_color_variation` -- tint and color correction
3. Add tests
4. Manual integration test: apply extreme rotation/scale, verify viewport

**Dependencies:** Phase 1
**Deliverable:** 2 new tools, tests passing.

### Phase 7: Surface, Path, and Camera (Week 7)

**Goal:** Advanced distribution modes and render optimization.

1. `set_forest_pack_surface_settings` -- altitude/slope limits
2. `set_forest_pack_path_distribution` -- spline path mode
3. `set_forest_pack_camera_clipping` -- camera optimization
4. Add tests
5. Manual integration test: set altitude limit on terrain, verify scatter constrained

**Dependencies:** Phase 1
**Deliverable:** 3 new tools, tests passing.

### Phase 8: Animation, LOD, and Library (Week 8)

**Goal:** Advanced features.

1. `set_forest_pack_animation` -- animation offset modes
2. `set_forest_pack_lod` -- LOD configuration
3. `load_forest_pack_preset` -- library preset loading (if feasible)
4. Add tests
5. Manual integration test: assign animated geometry, verify offset works

**Dependencies:** Phase 1, Phase 5 (need interface discovery)
**Deliverable:** 2-3 new tools, tests passing.

### Phase 9: Documentation and SKILL.md Update

**Goal:** Update the development guide.

1. Add Forest Pack section to `skills/3dsmax-mcp-dev/SKILL.md`
2. Update `docs/forest_pack_scatter_notes.md` with new learnings
3. Create `docs/forest_pack_property_reference.md` (from Phase 1)
4. Add Forest Pack workflow examples to skill guide

---

## 7. Known Risks and Mitigations

### Risk 1: Property names are wrong -- MITIGATED

**Impact:** High -- tools will silently fail or crash
**Likelihood:** ~~High for unverified properties~~ LOW -- Phase 0 introspection completed 2026-03-03, all 341 properties confirmed
**Mitigation:**
- ~~Phase 1 introspection is mandatory before any implementation~~ DONE
- Every property access wrapped in `try/catch` in MAXScript
- Return meaningful error messages when property access fails
- ~~Keep a verified vs. unverified property list in this plan~~ All properties now verified (Section 4.4)

### Risk 2: Array synchronization failures

**Impact:** High -- Forest Pack can enter broken state
**Likelihood:** Medium
**Mitigation:**
- All array operations read-all, modify, write-all in a single MAXScript block
- Validate array lengths before writing back
- Add rollback pattern: save old arrays, restore on error
- Test with edge cases: empty arrays, single element, remove last element

### Risk 3: Forest Pack version differences

**Impact:** Medium -- properties may be renamed or removed between FP versions
**Likelihood:** Medium
**Mitigation:**
- Test against the installed Forest Pack version (discovered in Phase 1)
- Use `try/catch` around every property access
- Return `"unsupported"` rather than crashing for missing features
- Document which FP version was tested against

### Risk 4: Distribution map assignment complexity

**Impact:** Medium -- maps may require specific setup sequences
**Likelihood:** Medium (observed in forum posts about `fp.distmap` issues)
**Mitigation:**
- Research forum threads about `distmap` scripting issues
- Test with both Bitmaptexture and procedural maps
- May need to set map type/mode before assigning the map itself
- Consider adding a `fp.update()` or refresh call after map assignment

### Risk 5: Library preset loading

**Impact:** Low -- feature may not be feasible via MAXScript
**Likelihood:** Medium
**Mitigation:**
- Mark `load_forest_pack_preset` as "experimental" / "if feasible"
- If no MAXScript API for presets exists, document manual workflow instead
- Consider alternative: export/import presets via property serialization

### Risk 6: Performance with large property dumps

**Impact:** Low -- `get_forest_pack_info` may be slow with 200+ properties
**Likelihood:** Low
**Mitigation:**
- Only read key properties, not the full dump
- Use `timeout=30.0` for inspection calls (same as `inspect_properties`)
- Consider a "verbose" flag for full vs. summary inspection

### Risk 7: Paint area data format

**Impact:** Low -- paint areas store bitmap data that may not be scriptable
**Likelihood:** High
**Mitigation:**
- Paint area creation may only be possible via the UI paint tool
- The `add_forest_pack_area` tool supports `area_type=4` (paint) for creating the area entry, but filling in paint data may not be possible via script
- Document this limitation clearly

### Risk 8: Forest Pack not installed

**Impact:** Low -- all tools should gracefully handle this
**Likelihood:** Low (user chose to use FP tools)
**Mitigation:**
- Every tool checks `Forest_Pro` class availability first
- Return clear error: `"Forest Pack is not installed (Forest_Pro unavailable)"`
- Same pattern already used in `scatter_forest_pack`

---

## References

- [iToo Software Forest Pack Documentation](https://docs.itoosoft.com/forestpack/)
- [Forest Pack Areas Rollout](https://docs.itoosoft.com/forestpack/forest-plugin/areas)
- [Forest Pack Camera Rollout](https://docs.itoosoft.com/forestpack/forest-plugin/camera)
- [Forest Pack Transform Rollout](https://docs.itoosoft.com/forestpack/forest-plugin/transform)
- [Forest Pack Material Rollout](https://docs.itoosoft.com/forestpack/forest-plugin/material)
- [Forest Pack Animation Rollout](https://docs.itoosoft.com/forestpack/forest-plugin/animation)
- [Forest Pack Display Rollout](https://docs.itoosoft.com/forestpack/forest-plugin/display)
- [Forest Pack Geometry Rollout](https://docs.itoosoft.com/forestpack/forest-plugin/add-geometry)
- [Forest Pack Surface Rollout](https://docs.itoosoft.com/forestpack/forest-plugin/surfaces)
- [Forest Pack Image Mode Distribution](https://docs.itoosoft.com/forestpack/forest-plugin/distribution/image-mode)
- [Forest Pack Path Mode Distribution](https://docs.itoosoft.com/forestpack/forest-plugin/distribution/path-mode)
- [Forest Pack Effects](https://docs.itoosoft.com/forestpack/forest-plugin/effects)
- [Forest Pack UI Overview](https://docs.itoosoft.com/forestpack/forest-plugin/ui)
- [Forest Pack General Rollout](https://docs.itoosoft.com/forestpack/forest-plugin/general)
- [iToo Forum - MAXScript Questions](https://forum.itoosoft.com/forest-pro-(*)/maxscript-questions/)
- [iToo Forum - Scripts for Forest Pack](https://forum.itoosoft.com/forest-pro-(*)/scripts-for-forest-pack/15/)
- [iToo Forum - Adding Source Objects via MAXScript](https://forum.itoosoft.com/forest-pro-(*)/adding-source-objects-surfaces-via-maxscript/)
- [iToo Forum - Distribution Map by Script](https://forum.itoosoft.com/forest-pro-(*)/problem-setting-distmap-by-script-5104/)
- [iToo Forum - Surface MAXScript](https://forum.itoosoft.com/forest-pro-(*)/surface-maxscript/)
- [Existing implementation: `src/tools/scattering.py`](../src/tools/scattering.py)
- [Existing notes: `docs/forest_pack_scatter_notes.md`](./forest_pack_scatter_notes.md)
