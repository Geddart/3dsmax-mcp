# Redshift Renderer Tools -- Implementation Plan

> **Status:** Draft
> **Date:** 2026-03-03
> **Target file:** `src/tools/redshift.py` (new module)
> **Server registration:** Add `redshift` to the import line in `src/server.py` line 13

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Research Phase -- Runtime Introspection Scripts](#2-research-phase----runtime-introspection-scripts)
3. [Tool Definitions](#3-tool-definitions)
4. [Testing Strategy](#4-testing-strategy)
5. [Implementation Order](#5-implementation-order)
6. [Known Risks and Mitigations](#6-known-risks-and-mitigations)

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

### What already exists for Redshift

In `src/tools/material_ops.py`:
- `_RENDERER_CONFIGS["redshift"]` maps PBR channels to `RS_Standard_Material` slot names.
- `_build_redshift_maxscript()` generates MAXScript for auto-wiring PBR textures.
- `_material_slot_hints()` returns `RS_BumpMap` as the normal/bump helper class.
- `create_material_from_textures` auto-detects Redshift renderer and creates RS materials.

### What does NOT exist yet

- Render settings (resolution, samples, GI, output format, GPU selection)
- Lights (dome, area, sun, IES, portal)
- AOVs / render elements
- Advanced material creation with layer control
- Proxy objects
- Camera overrides (RS exposure, DOF, motion blur, lens distortion)

### New file location

All new Redshift tools go in a single file: **`src/tools/redshift.py`**

This keeps the Redshift integration self-contained and follows the pattern of `scattering.py` (Forest Pack plugin integration in one file). If the file grows beyond ~1200 lines, split into `redshift_lights.py`, `redshift_render.py`, etc.

---

## 2. Research Phase -- Runtime Introspection Scripts

**CRITICAL:** Redshift property names, class names, and parameter types vary between versions. The official documentation is incomplete. Before writing any tool, the following MAXScript introspection commands MUST be run inside 3ds Max with Redshift active to discover the exact API surface.

Run each script below via the existing `execute_maxscript` tool or the MAXScript Listener.

### 2.1 Discover all Redshift classes

```maxscript
-- Find all classes matching "rs*" or "RS*" or "Redshift*"
(
    local ss = stringstream ""
    showClass "rs*" to:ss
    seek ss 0
    local lines = #()
    while not (eof ss) do (
        local ln = readline ss
        if ln.count > 0 do append lines ln
    )
    result = "Found " + (lines.count as string) + " RS classes:\n"
    for ln in lines do result += ln + "\n"
    result
)
```

### 2.2 Discover all RS light classes

```maxscript
-- List all Redshift light classes and their superclass
(
    local lightClasses = #()
    local ss = stringstream ""
    showClass "rs*Light*" to:ss
    seek ss 0
    while not (eof ss) do (
        local ln = readline ss
        if ln.count > 0 do append lightClasses ln
    )
    -- Also check for dome, sun, portal, IES patterns
    local extras = #("rsDomeLight", "rsSunLight", "rsPhysicalLight",
                     "rsIESLight", "rsPortalLight", "rsPhotometricLight")
    for cls in extras do (
        try (
            local testCls = execute cls
            if testCls != undefined do
                append lightClasses (cls + " : " + (superClassOf testCls) as string)
        ) catch ()
    )
    result = ""
    for ln in lightClasses do result += ln + "\n"
    result
)
```

### 2.3 Dump all RS light properties (per class)

Run this for EACH discovered light class. Replace `rsDomeLight` with each class name:

```maxscript
-- Dump all properties of a Redshift light class
(
    try (
        local lightObj = rsDomeLight()
        local ss = stringstream ""
        showProperties lightObj to:ss
        seek ss 0
        local result = "rsDomeLight properties:\n"
        while not (eof ss) do (
            local ln = readline ss
            if ln.count > 0 do result += ln + "\n"
        )
        delete lightObj
        result
    ) catch (
        "Error: " + (getCurrentException())
    )
)
```

### 2.4 Full Redshift_Renderer() property dump

```maxscript
-- Dump ALL properties of Redshift_Renderer
(
    local rr = Redshift_Renderer()
    local ss = stringstream ""
    showProperties rr to:ss
    seek ss 0
    local result = ""
    while not (eof ss) do (
        local ln = readline ss
        if ln.count > 0 do result += ln + "\n"
    )
    -- Also try filtered dumps for key categories
    local cats = #("*Sample*", "*GI*", "*Output*", "*Exr*", "*AOV*",
                    "*Resolution*", "*Bucket*", "*GPU*", "*CUDA*",
                    "*Motion*", "*DOF*", "*Exposure*")
    for cat in cats do (
        local ss2 = stringstream ""
        showProperties rr cat to:ss2
        seek ss2 0
        while not (eof ss2) do (
            local ln = readline ss2
            if ln.count > 0 do result += "[" + cat + "] " + ln + "\n"
        )
    )
    result
)
```

### 2.5 Discover all RS render element (AOV) classes

```maxscript
-- Find all Redshift render element classes
(
    local ss = stringstream ""
    showClass "RS*:RenderElement" to:ss
    seek ss 0
    local result = "RS Render Elements:\n"
    while not (eof ss) do (
        local ln = readline ss
        if ln.count > 0 do result += ln + "\n"
    )
    -- Also try the direct enumeration pattern
    local reClasses = #()
    try (
        local allRE = RenderElement.classes
        for c in allRE where (matchPattern ((c as string)) pattern:"RS*" ignoreCase:true) do
            append reClasses (c as string)
    ) catch ()
    result += "\nFrom RenderElement.classes:\n"
    for c in reClasses do result += c + "\n"
    result
)
```

### 2.6 Dump RS render element properties (per class)

Run for each discovered AOV class. Replace `RS_Aov_Diffuse` with each:

```maxscript
-- Dump properties of a specific RS render element
(
    try (
        local re = RS_Aov_Diffuse()
        local ss = stringstream ""
        showProperties re to:ss
        seek ss 0
        local result = "RS_Aov_Diffuse properties:\n"
        while not (eof ss) do (
            local ln = readline ss
            if ln.count > 0 do result += ln + "\n"
        )
        result
    ) catch (
        "Error: " + (getCurrentException())
    )
)
```

### 2.7 RS material classes and properties

```maxscript
-- Find all RS material classes
(
    local ss = stringstream ""
    showClass "RS*:material" to:ss
    seek ss 0
    local result = "RS Material classes:\n"
    while not (eof ss) do (
        local ln = readline ss
        if ln.count > 0 do result += ln + "\n"
    )
    result
)
```

```maxscript
-- Full property dump of RS_Standard_Material (the uber-shader)
(
    local mat = RS_Standard_Material()
    local ss = stringstream ""
    showProperties mat to:ss
    seek ss 0
    local result = "RS_Standard_Material properties:\n"
    while not (eof ss) do (
        local ln = readline ss
        if ln.count > 0 do result += ln + "\n"
    )
    result
)
```

### 2.8 RS texture/map classes

```maxscript
-- Find all RS texture map classes
(
    local ss = stringstream ""
    showClass "rs*:textureMap" to:ss
    seek ss 0
    local result = "RS TextureMap classes:\n"
    while not (eof ss) do (
        local ln = readline ss
        if ln.count > 0 do result += ln + "\n"
    )
    result
)
```

### 2.9 RS proxy object properties

```maxscript
-- Discover RS proxy class and properties
(
    local proxyClasses = #("RedshiftProxy", "rsProxy", "RS_Proxy",
                           "Redshift_Proxy", "RedshiftProxyMesh")
    local result = ""
    for cls in proxyClasses do (
        try (
            local proxyObj = execute (cls + "()")
            local ss = stringstream ""
            showProperties proxyObj to:ss
            seek ss 0
            result += cls + " properties:\n"
            while not (eof ss) do (
                local ln = readline ss
                if ln.count > 0 do result += ln + "\n"
            )
            delete proxyObj
        ) catch (
            result += cls + ": NOT FOUND\n"
        )
    )
    result
)
```

### 2.10 GPU selection API

```maxscript
-- Discover GPU selection API
(
    local result = ""
    -- Check if rsSetCudaDevices exists
    try (
        local devCount = rsGetNumCudaDevices()
        result += "rsGetNumCudaDevices() = " + (devCount as string) + "\n"
    ) catch (
        result += "rsGetNumCudaDevices: " + (getCurrentException()) + "\n"
    )
    -- Try to list device names
    try (
        local devCount = rsGetNumCudaDevices()
        for i = 0 to devCount - 1 do (
            local devName = rsGetCudaDeviceName i
            result += "GPU " + (i as string) + ": " + devName + "\n"
        )
    ) catch (
        result += "rsGetCudaDeviceName: " + (getCurrentException()) + "\n"
    )
    -- Check current device selection
    try (
        local devs = rsGetCudaDevices()
        result += "Current devices: " + (devs as string) + "\n"
    ) catch (
        result += "rsGetCudaDevices: " + (getCurrentException()) + "\n"
    )
    result
)
```

### 2.11 RS camera override properties

```maxscript
-- Discover Redshift camera override properties on a standard camera
(
    local cam = FreeCamera()
    cam.name = "__rs_introspect_cam"
    -- Redshift attaches properties via a CustAttributes plugin or modifier
    local ss = stringstream ""
    showProperties cam to:ss
    seek ss 0
    local result = "FreeCamera base properties:\n"
    while not (eof ss) do (
        local ln = readline ss
        if ln.count > 0 do result += ln + "\n"
    )
    -- Check for RS-specific attributes / modifiers
    result += "\nModifiers:\n"
    for m in cam.modifiers do
        result += "  " + m.name + " (" + (classOf m) as string + ")\n"
    -- Check custom attributes
    result += "\nCustom attributes:\n"
    local cas = custAttributes.get cam
    if cas != undefined do (
        for ca in cas do
            result += "  CA: " + (classOf ca) as string + "\n"
    )
    -- Try the Redshift camera tag class directly
    try (
        local rsCam = rsPhysicalCamera()  -- or rsCameraTag, RS_Camera
        local ss2 = stringstream ""
        showProperties rsCam to:ss2
        seek ss2 0
        result += "\nrsPhysicalCamera properties:\n"
        while not (eof ss2) do (
            local ln = readline ss2
            if ln.count > 0 do result += ln + "\n"
        )
    ) catch ()
    delete cam
    result
)
```

### 2.12 Redshift MAXScript interface namespace

```maxscript
-- Check if the 'redshift' interface exists and what methods it exposes
(
    local result = ""
    try (
        local iface = redshift
        local ss = stringstream ""
        showMethods iface to:ss
        seek ss 0
        result += "redshift interface methods:\n"
        while not (eof ss) do (
            local ln = readline ss
            if ln.count > 0 do result += ln + "\n"
        )
        local ss2 = stringstream ""
        showProperties iface to:ss2
        seek ss2 0
        result += "\nredshift interface properties:\n"
        while not (eof ss2) do (
            local ln = readline ss2
            if ln.count > 0 do result += ln + "\n"
        )
    ) catch (
        result += "redshift interface: " + (getCurrentException()) + "\n"
    )
    result
)
```

---

## 3. Tool Definitions

### File Header

```python
"""Redshift renderer tools for 3ds Max.

Provides tools for Redshift render settings, lights, AOVs (render elements),
advanced material creation, proxy objects, GPU selection, and camera overrides.

IMPORTANT: Redshift class and property names can change between versions.
All tools use runtime introspection (try/catch) and NEVER hardcode class names
without a fallback. Discovery scripts in docs/PLAN_redshift.md Section 2 must
be run first to confirm exact property names for the installed RS version.
"""

from __future__ import annotations

import json
from typing import Optional
from ..server import mcp, client


def _safe_name(name: str) -> str:
    return name.replace("\\", "\\\\").replace('"', '\\"')


def _safe_path(path: str) -> str:
    return path.replace("\\", "/")
```

---

### 3.1 `get_redshift_settings`

**Purpose:** Dump the current Redshift render configuration as structured JSON.

**Parameters:**

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `filter` | `str` | `""` | Optional wildcard filter for property names (e.g. `"*Sample*"`, `"*GI*"`). Empty = dump all. |
| `max_properties` | `int` | `100` | Maximum number of properties to return. |

**MAXScript template:**

```maxscript
(
    local rr = renderers.current
    if (matchPattern ((classof rr) as string) pattern:"*Redshift*" ignoreCase:true) == false then (
        "{\"error\": \"Active renderer is not Redshift. Current: " + ((classof rr) as string) + "\"}"
    ) else (
        local ss = stringstream ""
        local filterPat = "{filter}"
        if filterPat == "" then
            showProperties rr to:ss
        else
            showProperties rr filterPat to:ss
        seek ss 0

        local propNames = #()
        local propTypes = #()
        while not (eof ss) do (
            local ln = readline ss
            local parts = filterString ln ":"
            if parts.count >= 2 do (
                local lhsParts = filterString (trimRight parts[1]) ". "
                if lhsParts.count >= 1 do (
                    append propNames lhsParts[lhsParts.count]
                    append propTypes (trimLeft parts[2])
                )
            )
        )

        local result = "{\"renderer\": \"" + ((classof rr) as string) + "\", \"propertyCount\": " + (propNames.count as string) + ", \"properties\": ["
        local maxProps = amin #(propNames.count, {max_properties})
        for i = 1 to maxProps do (
            if i > 1 do result += ","
            local pName = propNames[i]
            local pType = propTypes[i]
            local pVal = "null"
            try (
                local v = getProperty rr pName
                pVal = "\"" + (substituteString (substituteString (v as string) "\"" "'") "\n" " ") + "\""
            ) catch ()
            result += "{\"name\": \"" + pName + "\", \"type\": \"" + pType + "\", \"value\": " + pVal + "}"
        )
        result += "]}"
        result
    )
)
```

**Return format:**
```json
{
  "renderer": "Redshift_Renderer",
  "propertyCount": 150,
  "properties": [
    {"name": "UnifiedMaxSamples", "type": "integer", "value": "256"},
    {"name": "UnifiedMinSamples", "type": "integer", "value": "16"}
  ]
}
```

**Dependencies:** Redshift must be the active renderer.

---

### 3.2 `set_redshift_settings`

**Purpose:** Set one or more Redshift render settings properties.

**Parameters:**

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `properties` | `dict[str, str]` | required | Dict of property names to MAXScript values. |

**MAXScript template:**

```maxscript
(
    local rr = renderers.current
    if (matchPattern ((classof rr) as string) pattern:"*Redshift*" ignoreCase:true) == false then (
        "{\"error\": \"Active renderer is not Redshift. Current: " + ((classof rr) as string) + "\"}"
    ) else (
        local okList = #()
        local errList = #()
        {set_block}
        local msg = "{\"set\": " + (okList.count as string) + ", \"errors\": " + (errList.count as string)
        if okList.count > 0 do (
            msg += ", \"ok\": ["
            for i = 1 to okList.count do (
                if i > 1 do msg += ","
                msg += "\"" + okList[i] + "\""
            )
            msg += "]"
        )
        if errList.count > 0 do (
            msg += ", \"errDetails\": ["
            for i = 1 to errList.count do (
                if i > 1 do msg += ","
                msg += "\"" + (substituteString errList[i] "\"" "'") + "\""
            )
            msg += "]"
        )
        msg += "}"
        msg
    )
)
```

Where `{set_block}` is dynamically generated:
```python
set_lines = []
for prop, val in properties.items():
    safe_prop = _safe_name(prop)
    set_lines.append(
        f'try (rr.{safe_prop} = {val}; append okList "{safe_prop}") '
        f'catch (append errList ("{safe_prop}: " + (getCurrentException())))'
    )
set_block = "\n        ".join(set_lines)
```

**Return format:**
```json
{
  "set": 3,
  "errors": 0,
  "ok": ["UnifiedMaxSamples", "UnifiedMinSamples", "GIEnabled"]
}
```

**Dependencies:** Redshift must be the active renderer.

**Common property names (to be confirmed by introspection):**

| Property | Type | Example | Description |
|----------|------|---------|-------------|
| `UnifiedMinSamples` | integer | `16` | Min adaptive samples |
| `UnifiedMaxSamples` | integer | `256` | Max adaptive samples |
| `UnifiedAdaptiveErrorThreshold` | float | `0.01` | Noise threshold |
| `GIEnabled` | boolean | `true` | Enable global illumination |
| `GIEngine_Primary` | integer | `0` | Primary GI engine (0=BruteForce, 2=IrradiancePointCloud) |
| `GIEngine_Secondary` | integer | `0` | Secondary GI engine |
| `BucketSizeX` | integer | `128` | Bucket width |
| `BucketSizeY` | integer | `128` | Bucket height |
| `OutputExrEnabled` | boolean | `true` | EXR output |
| `OutputExrFileName` | string | `"C:/..."` | Output file path |

---

### 3.3 `set_redshift_gpu`

**Purpose:** Select which GPUs to use for Redshift rendering.

**Parameters:**

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `device_indices` | `list[int]` | `[0]` | List of 0-based GPU indices to enable. |

**MAXScript template:**

```maxscript
(
    local devArr = {device_array}
    local result = ""
    try (
        local totalDevs = rsGetNumCudaDevices()
        result += "{\"totalGPUs\": " + (totalDevs as string)
        -- Validate indices
        local validDevs = #()
        local invalidDevs = #()
        for idx in devArr do (
            if idx >= 0 and idx < totalDevs then
                append validDevs idx
            else
                append invalidDevs idx
        )
        if invalidDevs.count > 0 then (
            result += ", \"error\": \"Invalid GPU indices\", \"invalid\": " + (invalidDevs as string)
            result += ", \"validRange\": \"0-" + ((totalDevs - 1) as string) + "\"}"
        ) else (
            rsSetCudaDevices devArr
            local activeDevs = rsGetCudaDevices()
            result += ", \"activeGPUs\": " + (activeDevs as string)
            result += ", \"deviceNames\": ["
            for i = 1 to activeDevs.count do (
                if i > 1 do result += ","
                local devName = rsGetCudaDeviceName activeDevs[i]
                result += "\"" + devName + "\""
            )
            result += "]}"
        )
    ) catch (
        result = "{\"error\": \"" + (substituteString (getCurrentException()) "\"" "'") + "\"}"
    )
    result
)
```

Where `{device_array}` is built as:
```python
device_array = "#(" + ", ".join(str(int(d)) for d in device_indices) + ")"
```

**Return format:**
```json
{
  "totalGPUs": 2,
  "activeGPUs": [0, 1],
  "deviceNames": ["NVIDIA GeForce RTX 4090", "NVIDIA GeForce RTX 4090"]
}
```

**Dependencies:** Redshift global functions (`rsSetCudaDevices`, `rsGetNumCudaDevices`, `rsGetCudaDeviceName`) must be available.

---

### 3.4 `create_redshift_light`

**Purpose:** Create a Redshift light with specified parameters.

**Parameters:**

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `light_type` | `str` | required | One of: `"dome"`, `"area"`, `"sun"`, `"ies"`, `"portal"`, `"physical"`. |
| `name` | `str` | `""` | Optional light name. |
| `position` | `list[float]` | `[0, 0, 0]` | World position `[x, y, z]`. |
| `rotation` | `list[float]` | `[0, 0, 0]` | Euler rotation `[x, y, z]` in degrees. |
| `intensity` | `float` | `1.0` | Light intensity/multiplier. |
| `color` | `list[int]` | `[255, 255, 255]` | RGB color `[r, g, b]`. |
| `enabled` | `bool` | `True` | Whether the light is on. |
| `properties` | `dict[str, str]` | `None` | Additional MAXScript properties to set after creation. |

**Light type to class mapping (to be confirmed by introspection):**

| `light_type` | Expected MAXScript class | Fallback candidates |
|--------------|--------------------------|---------------------|
| `"dome"` | `rsDomeLight` | `rsEnvironmentLight`, `RS_DomeLight` |
| `"area"` | `rsPhysicalLight` | `rsAreaLight`, `RS_AreaLight` |
| `"sun"` | `rsSunLight` | `rsDirectionalLight`, `RS_SunLight` |
| `"ies"` | `rsIESLight` | `RS_IES_Light` |
| `"portal"` | `rsPortalLight` | `RS_PortalLight` |
| `"physical"` | `rsPhysicalLight` | `RS_PhysicalLight` |

**MAXScript template:**

```maxscript
(
    -- Class lookup table with fallbacks
    local classMap = #(
        #("dome",     #("rsDomeLight", "rsEnvironmentLight", "RS_DomeLight")),
        #("area",     #("rsPhysicalLight", "rsAreaLight", "RS_AreaLight")),
        #("sun",      #("rsSunLight", "rsDirectionalLight", "RS_SunLight")),
        #("ies",      #("rsIESLight", "RS_IES_Light")),
        #("portal",   #("rsPortalLight", "RS_PortalLight")),
        #("physical", #("rsPhysicalLight", "RS_PhysicalLight"))
    )

    local lightType = "{light_type}"
    local candidates = undefined
    for entry in classMap where entry[1] == lightType do candidates = entry[2]
    if candidates == undefined then (
        "{\"error\": \"Unknown light_type: {light_type}. Valid: dome, area, sun, ies, portal, physical\"}"
    ) else (
        local lightObj = undefined
        local usedClass = ""
        for cls in candidates while lightObj == undefined do (
            try (
                lightObj = execute (cls + "()")
                usedClass = cls
            ) catch ()
        )
        if lightObj == undefined then (
            "{\"error\": \"Could not create RS light. Tried: " + (candidates as string) + "\"}"
        ) else (
            -- Set name
            local safeName = "{safe_name}"
            if safeName != "" do lightObj.name = safeName
            -- Set transform
            lightObj.pos = [{pos_x}, {pos_y}, {pos_z}]
            try (lightObj.rotation = eulerAngles {rot_x} {rot_y} {rot_z}) catch ()
            -- Set common properties
            try (lightObj.intensity = {intensity}) catch (
                try (lightObj.multiplier = {intensity}) catch ()
            )
            try (lightObj.color = color {color_r} {color_g} {color_b}) catch (
                try (lightObj.LightColor = color {color_r} {color_g} {color_b}) catch ()
            )
            try (lightObj.on = {enabled_ms}) catch (
                try (lightObj.enabled = {enabled_ms}) catch ()
            )
            -- Set additional properties
            local okList = #()
            local errList = #()
            {extra_props_block}
            -- Build result
            local result = "{\"name\": \"" + lightObj.name + "\""
            result += ", \"class\": \"" + (classOf lightObj) as string + "\""
            result += ", \"rsClass\": \"" + usedClass + "\""
            result += ", \"position\": [" + (lightObj.pos.x as string) + "," + (lightObj.pos.y as string) + "," + (lightObj.pos.z as string) + "]"
            if okList.count > 0 do (
                result += ", \"extraPropsSet\": " + (okList.count as string)
            )
            if errList.count > 0 do (
                result += ", \"extraPropsErrors\": " + (errList.count as string)
            )
            result += "}"
            result
        )
    )
)
```

**Return format:**
```json
{
  "name": "RS_DomeLight001",
  "class": "rsDomeLight",
  "rsClass": "rsDomeLight",
  "position": [0, 0, 300],
  "extraPropsSet": 2
}
```

**Dependencies:** Redshift plugin must be installed.

---

### 3.5 `get_redshift_lights`

**Purpose:** List all Redshift lights in the scene with their key properties.

**Parameters:**

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `max_lights` | `int` | `50` | Maximum number of lights to return. |

**MAXScript template:**

```maxscript
(
    local rsLights = #()
    for obj in lights where (matchPattern ((classOf obj) as string) pattern:"rs*" ignoreCase:true) do
        append rsLights obj
    -- Also check for Redshift pattern
    for obj in lights where (matchPattern ((classOf obj) as string) pattern:"Redshift*" ignoreCase:true) do
        if (findItem rsLights obj) == 0 do append rsLights obj

    local maxLights = {max_lights}
    local result = "{\"count\": " + (rsLights.count as string) + ", \"lights\": ["
    local showCount = amin #(rsLights.count, maxLights)
    for i = 1 to showCount do (
        if i > 1 do result += ","
        local lt = rsLights[i]
        result += "{\"name\": \"" + lt.name + "\""
        result += ", \"class\": \"" + (classOf lt) as string + "\""
        result += ", \"position\": [" + (lt.pos.x as string) + "," + (lt.pos.y as string) + "," + (lt.pos.z as string) + "]"
        try (result += ", \"intensity\": " + (lt.intensity as string)) catch (
            try (result += ", \"multiplier\": " + (lt.multiplier as string)) catch ()
        )
        try (
            local c = lt.color
            result += ", \"color\": [" + (c.r as string) + "," + (c.g as string) + "," + (c.b as string) + "]"
        ) catch ()
        try (result += ", \"on\": " + (if lt.on then "true" else "false")) catch (
            try (result += ", \"enabled\": " + (if lt.enabled then "true" else "false")) catch ()
        )
        result += "}"
    )
    result += "]}"
    result
)
```

**Return format:**
```json
{
  "count": 3,
  "lights": [
    {
      "name": "rsDomeLight001",
      "class": "rsDomeLight",
      "position": [0, 0, 0],
      "intensity": 1.0,
      "color": [255, 255, 255],
      "on": true
    }
  ]
}
```

---

### 3.6 `add_redshift_aov`

**Purpose:** Add a Redshift AOV (render element) to the scene.

**Parameters:**

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `aov_type` | `str` | required | AOV type name. Supported: `"diffuse"`, `"specular"`, `"reflection"`, `"refraction"`, `"emission"`, `"gi"`, `"sss"`, `"caustics"`, `"depth"`, `"normals"`, `"world_position"`, `"motion_vectors"`, `"object_id"`, `"material_id"`, `"puzzle_matte"`, `"shadow"`, `"ambient_occlusion"`, `"custom"`. |
| `class_override` | `str` | `""` | Explicit MAXScript class name override. Use when `aov_type` mapping is wrong for your RS version. |
| `name` | `str` | `""` | Optional display name for the AOV. |
| `enabled` | `bool` | `True` | Whether the AOV is enabled. |
| `properties` | `dict[str, str]` | `None` | Additional properties to set on the render element. |

**AOV type to class mapping (to be confirmed by introspection):**

| `aov_type` | Expected class | Notes |
|------------|----------------|-------|
| `"diffuse"` | `RS_Aov_DiffuseLighting` | Diffuse lighting pass |
| `"specular"` | `RS_Aov_SpecularLighting` | Specular/reflection lighting |
| `"reflection"` | `RS_Aov_Reflections` | Mirror reflections |
| `"refraction"` | `RS_Aov_Refractions` | Refraction pass |
| `"emission"` | `RS_Aov_Emission` | Emission pass |
| `"gi"` | `RS_Aov_GI` | Global illumination |
| `"sss"` | `RS_Aov_SSS` | Subsurface scattering |
| `"caustics"` | `RS_Aov_Caustics` | Caustics |
| `"depth"` | `RS_Aov_Depth` | Z-depth |
| `"normals"` | `RS_Aov_Normals` | Surface normals |
| `"world_position"` | `RS_Aov_WorldPosition` | World space position |
| `"motion_vectors"` | `RS_Aov_MotionVectors` | Motion vector pass |
| `"object_id"` | `RS_Aov_ObjectID` | Object ID |
| `"material_id"` | `RS_Aov_MaterialID` | Material ID |
| `"puzzle_matte"` | `RS_Aov_PuzzleMatte` | Cryptomatte/puzzle matte |
| `"shadow"` | `RS_Aov_Shadows` | Shadow pass |
| `"ambient_occlusion"` | `RS_Aov_AO` | Ambient occlusion |
| `"custom"` | (use `class_override`) | For unlisted AOV types |

**MAXScript template:**

```maxscript
(
    -- AOV type to class name map
    local typeMap = #(
        #("diffuse", "RS_Aov_DiffuseLighting"),
        #("specular", "RS_Aov_SpecularLighting"),
        #("reflection", "RS_Aov_Reflections"),
        #("refraction", "RS_Aov_Refractions"),
        #("emission", "RS_Aov_Emission"),
        #("gi", "RS_Aov_GI"),
        #("sss", "RS_Aov_SSS"),
        #("caustics", "RS_Aov_Caustics"),
        #("depth", "RS_Aov_Depth"),
        #("normals", "RS_Aov_Normals"),
        #("world_position", "RS_Aov_WorldPosition"),
        #("motion_vectors", "RS_Aov_MotionVectors"),
        #("object_id", "RS_Aov_ObjectID"),
        #("material_id", "RS_Aov_MaterialID"),
        #("puzzle_matte", "RS_Aov_PuzzleMatte"),
        #("shadow", "RS_Aov_Shadows"),
        #("ambient_occlusion", "RS_Aov_AO")
    )

    local aovType = "{aov_type}"
    local classOverride = "{class_override}"
    local className = ""

    if classOverride != "" then (
        className = classOverride
    ) else (
        for entry in typeMap where entry[1] == aovType do className = entry[2]
    )

    if className == "" then (
        "{\"error\": \"Unknown aov_type: " + aovType + ". Use class_override for custom types.\"}"
    ) else (
        local re = undefined
        try (re = execute (className + "()")) catch ()
        if re == undefined then (
            "{\"error\": \"Could not create render element class: " + className + "\"}"
        ) else (
            local safeName = "{safe_name}"
            if safeName != "" do try (re.elementName = safeName) catch ()
            try (re.enabled = {enabled_ms}) catch ()

            -- Set additional properties
            local okList = #()
            local errList = #()
            {extra_props_block}

            -- Add to the render elements manager
            local rem = maxOps.GetCurRenderElementMgr()
            rem.AddRenderElement re

            local result = "{\"name\": \""
            try (result += re.elementName) catch (result += (classOf re) as string)
            result += "\", \"class\": \"" + (classOf re) as string + "\""
            result += ", \"enabled\": " + (if re.enabled then "true" else "false")
            result += ", \"totalAOVs\": " + (rem.NumRenderElements() as string)
            result += "}"
            result
        )
    )
)
```

**Return format:**
```json
{
  "name": "RS_Depth",
  "class": "RS_Aov_Depth",
  "enabled": true,
  "totalAOVs": 5
}
```

---

### 3.7 `get_redshift_aovs`

**Purpose:** List all render elements (AOVs) currently in the scene.

**Parameters:**

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `redshift_only` | `bool` | `True` | If true, only return AOVs whose class matches `RS*`. |

**MAXScript template:**

```maxscript
(
    local rem = maxOps.GetCurRenderElementMgr()
    local total = rem.NumRenderElements()
    local rsOnly = {redshift_only_ms}
    local result = "{\"total\": " + (total as string) + ", \"aovs\": ["
    local first = true
    for i = 0 to total - 1 do (
        local re = rem.GetRenderElement i
        local cls = (classOf re) as string
        if rsOnly and not (matchPattern cls pattern:"RS*" ignoreCase:true) then continue
        if not first do result += ","
        first = false
        result += "{\"index\": " + (i as string)
        result += ", \"class\": \"" + cls + "\""
        try (result += ", \"name\": \"" + re.elementName + "\"") catch ()
        try (result += ", \"enabled\": " + (if re.enabled then "true" else "false")) catch ()
        result += "}"
    )
    result += "]}"
    result
)
```

**Return format:**
```json
{
  "total": 8,
  "aovs": [
    {"index": 0, "class": "RS_Aov_DiffuseLighting", "name": "Diffuse", "enabled": true},
    {"index": 1, "class": "RS_Aov_Depth", "name": "Depth", "enabled": true}
  ]
}
```

---

### 3.8 `remove_redshift_aov`

**Purpose:** Remove a render element by index or by class name.

**Parameters:**

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `index` | `int` | `-1` | 0-based index of the AOV to remove. Use -1 to match by class. |
| `class_name` | `str` | `""` | Class name pattern to match (e.g. `"RS_Aov_Depth"`). Removes first match. |
| `remove_all` | `bool` | `False` | If true with `class_name`, removes ALL matching AOVs. |

**MAXScript template:**

```maxscript
(
    local rem = maxOps.GetCurRenderElementMgr()
    local total = rem.NumRenderElements()
    local idx = {index}
    local classMatch = "{class_name}"
    local removeAll = {remove_all_ms}

    if idx >= 0 then (
        if idx >= total then (
            "{\"error\": \"Index " + (idx as string) + " out of range. Total: " + (total as string) + "\"}"
        ) else (
            local re = rem.GetRenderElement idx
            local cls = (classOf re) as string
            local eName = ""
            try (eName = re.elementName) catch ()
            rem.RemoveRenderElement re
            "{\"removed\": \"" + cls + "\", \"name\": \"" + eName + "\", \"index\": " + (idx as string) + ", \"remaining\": " + (rem.NumRenderElements() as string) + "}"
        )
    ) else if classMatch != "" then (
        -- Find and remove by class pattern
        local removed = #()
        -- Iterate backwards to avoid index shifting
        for i = (total - 1) to 0 by -1 do (
            local re = rem.GetRenderElement i
            local cls = (classOf re) as string
            if (matchPattern cls pattern:("*" + classMatch + "*") ignoreCase:true) do (
                local eName = ""
                try (eName = re.elementName) catch ()
                append removed (cls + ":" + eName)
                rem.RemoveRenderElement re
                if not removeAll do exit
            )
        )
        if removed.count == 0 then (
            "{\"error\": \"No AOV matching '" + classMatch + "' found.\"}"
        ) else (
            local result = "{\"removedCount\": " + (removed.count as string) + ", \"removed\": ["
            for i = 1 to removed.count do (
                if i > 1 do result += ","
                result += "\"" + removed[i] + "\""
            )
            result += "], \"remaining\": " + (rem.NumRenderElements() as string) + "}"
            result
        )
    ) else (
        "{\"error\": \"Provide either index or class_name.\"}"
    )
)
```

**Return format:**
```json
{
  "removedCount": 1,
  "removed": ["RS_Aov_Depth:Depth"],
  "remaining": 4
}
```

---

### 3.9 `create_redshift_material`

**Purpose:** Create an RS Standard Material with fine-grained control over all layers (base, reflection, transmission, SSS, coat, sheen, emission).

**Parameters:**

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `name` | `str` | `""` | Material name. |
| `preset` | `str` | `""` | Optional preset: `"chrome"`, `"glass"`, `"skin"`, `"plastic"`, `"emissive"`. Sets sensible defaults. Empty = no preset. |
| `assign_to` | `list[str]` | `None` | Optional list of object names to assign the material to. |
| `properties` | `dict[str, str]` | `None` | Dict of property names to MAXScript values for direct property setting. |

**Preset definitions (built in Python, not MAXScript):**

```python
_RS_PRESETS = {
    "chrome": {
        "base_color": "color 220 220 225",
        "metalness": "1.0",
        "refl_roughness": "0.05",
        "refl_weight": "1.0",
    },
    "glass": {
        "refr_weight": "1.0",
        "refr_color": "color 255 255 255",
        "refl_roughness": "0.0",
        "refl_IOR": "1.5",
        "refr_IOR": "1.5",
        "thin_walled": "false",
    },
    "skin": {
        "base_color": "color 200 150 120",
        "ss_weight": "0.5",
        "ss_color1": "color 200 100 80",
        "ss_radius1": "1.0",
        "refl_roughness": "0.4",
    },
    "plastic": {
        "base_color": "color 200 50 50",
        "metalness": "0.0",
        "refl_roughness": "0.3",
        "refl_weight": "1.0",
        "coat_weight": "0.5",
        "coat_roughness": "0.1",
    },
    "emissive": {
        "emission_weight": "1.0",
        "emission_color": "color 255 200 150",
    },
}
```

**MAXScript template:**

```maxscript
(
    try (
        local mat = RS_Standard_Material name:"{safe_name}"
        local okList = #()
        local errList = #()
        {props_block}
        {assign_block}
        local result = "{\"name\": \"" + mat.name + "\", \"class\": \"RS_Standard_Material\""
        result += ", \"propertiesSet\": " + (okList.count as string)
        if errList.count > 0 do (
            result += ", \"errors\": " + (errList.count as string)
        )
        {assign_result_block}
        result += "}"
        result
    ) catch (
        "{\"error\": \"" + (substituteString (getCurrentException()) "\"" "'") + "\"}"
    )
)
```

**Return format:**
```json
{
  "name": "Chrome_Material",
  "class": "RS_Standard_Material",
  "propertiesSet": 4,
  "assignedTo": 2
}
```

**Dependencies:** Redshift plugin must be installed (`RS_Standard_Material` class available).

---

### 3.10 `get_redshift_material_properties`

**Purpose:** Introspect an RS material's properties, organized by layer/category.

**Parameters:**

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `name` | `str` | required | Object name whose material to inspect, OR a material name from the material library. |
| `sub_material_index` | `int` | `0` | For Multi/Sub materials, 1-based index. 0 = top-level. |
| `layer_filter` | `str` | `""` | Filter to a specific layer: `"base"`, `"reflection"`, `"refraction"`, `"sss"`, `"coat"`, `"sheen"`, `"emission"`, `"bump"`, `"opacity"`. Empty = all. |

**Implementation note:** This builds on top of the pattern in `get_material_slots` but organizes properties by Redshift layer grouping. The layer groupings are based on property name prefixes:

- `base_*` or `diffuse_*` => Base layer
- `refl_*` or `reflection_*` => Reflection layer
- `refr_*` or `refraction_*` or `trans_*` => Transmission/Refraction layer
- `ss_*` or `sss_*` or `subsurface_*` => Subsurface scattering layer
- `coat_*` => Coat layer
- `sheen_*` => Sheen layer
- `emission_*` or `emit_*` => Emission layer
- `bump_*` or `normal_*` or `displacement_*` => Bump/Normal/Displacement
- `opacity_*` or `cutout_*` => Opacity

**MAXScript template:**

```maxscript
(
    local obj = getNodeByName "{safe}"
    if obj == undefined then (
        "{\"error\": \"Object not found: {safe}\"}"
    ) else if obj.material == undefined then (
        "{\"error\": \"No material assigned to {safe}\"}"
    ) else (
        local mat = {mat_expr}
        if mat == undefined then (
            "{\"error\": \"Material/sub-material not found\"}"
        ) else if not (matchPattern ((classOf mat) as string) pattern:"*RS*" ignoreCase:true) and
                  not (matchPattern ((classOf mat) as string) pattern:"*Redshift*" ignoreCase:true) then (
            "{\"error\": \"Material is not Redshift type: " + ((classOf mat) as string) + "\"}"
        ) else (
            local props = #()
            try (props = makeUniqueArray (getPropNames mat)) catch ()
            local layerFilter = "{layer_filter}"
            -- Categorize by layer based on prefix
            -- (Implementation follows same pattern as get_material_slots)
            -- ... (full categorization logic) ...
        )
    )
)
```

**Return format:**
```json
{
  "name": "RS_Material001",
  "class": "RS_Standard_Material",
  "layers": {
    "base": [
      {"name": "base_color", "value": "(color 200 200 200)", "type": "color"}
    ],
    "reflection": [
      {"name": "refl_roughness", "value": "0.3", "type": "float"}
    ]
  }
}
```

---

### 3.11 `create_redshift_proxy`

**Purpose:** Create a Redshift proxy object from a `.rs` proxy file.

**Parameters:**

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `file_path` | `str` | required | Path to the `.rs` proxy file. |
| `name` | `str` | `""` | Optional object name. |
| `position` | `list[float]` | `[0, 0, 0]` | World position. |
| `display_mode` | `int` | `2` | Viewport display mode (0=bounding box, 1=preview mesh, 2=full mesh -- to be confirmed). |

**MAXScript template:**

```maxscript
(
    -- Try known proxy class names
    local proxyClasses = #("RedshiftProxy", "rsProxy", "RS_Proxy",
                           "Redshift_Proxy", "RedshiftProxyMesh")
    local proxyObj = undefined
    local usedClass = ""
    for cls in proxyClasses while proxyObj == undefined do (
        try (
            proxyObj = execute (cls + "()")
            usedClass = cls
        ) catch ()
    )
    if proxyObj == undefined then (
        "{\"error\": \"Redshift Proxy class not found. Tried: " + (proxyClasses as string) + "\"}"
    ) else (
        local safePath = "{safe_file_path}"
        local safeName = "{safe_name}"
        -- Set the proxy file
        try (proxyObj.fileName = safePath) catch (
            try (proxyObj.file = safePath) catch (
                try (proxyObj.proxyFile = safePath) catch ()
            )
        )
        if safeName != "" do proxyObj.name = safeName
        proxyObj.pos = [{pos_x}, {pos_y}, {pos_z}]
        try (proxyObj.displayMode = {display_mode}) catch (
            try (proxyObj.viewport_mode = {display_mode}) catch ()
        )
        local result = "{\"name\": \"" + proxyObj.name + "\""
        result += ", \"class\": \"" + usedClass + "\""
        result += ", \"file\": \"" + (substituteString safePath "\\" "/") + "\""
        result += ", \"position\": [" + (proxyObj.pos.x as string) + "," + (proxyObj.pos.y as string) + "," + (proxyObj.pos.z as string) + "]"
        result += "}"
        result
    )
)
```

**Return format:**
```json
{
  "name": "RS_Proxy001",
  "class": "RedshiftProxy",
  "file": "C:/assets/tree.rs",
  "position": [100, 0, 0]
}
```

---

### 3.12 `get_redshift_proxy_info`

**Purpose:** Inspect a Redshift proxy object's properties.

**Parameters:**

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `name` | `str` | required | The proxy object name. |

**MAXScript template:**

```maxscript
(
    local obj = getNodeByName "{safe}"
    if obj == undefined then (
        "{\"error\": \"Object not found: {safe}\"}"
    ) else (
        local cls = (classOf obj) as string
        local baseCls = (classOf obj.baseobject) as string
        if not (matchPattern cls pattern:"*Redshift*Prox*" ignoreCase:true) and
           not (matchPattern baseCls pattern:"*Redshift*Prox*" ignoreCase:true) and
           not (matchPattern cls pattern:"*rsProx*" ignoreCase:true) and
           not (matchPattern baseCls pattern:"*rsProx*" ignoreCase:true) then (
            "{\"error\": \"Object is not a Redshift proxy: " + cls + " / " + baseCls + "\"}"
        ) else (
            local tgt = obj.baseobject
            local props = #()
            try (props = makeUniqueArray (getPropNames tgt)) catch ()

            local result = "{\"name\": \"" + obj.name + "\", \"class\": \"" + cls + "\""
            result += ", \"position\": [" + (obj.pos.x as string) + "," + (obj.pos.y as string) + "," + (obj.pos.z as string) + "]"
            result += ", \"properties\": {"
            local first = true
            for p in props do (
                try (
                    local val = getProperty tgt p
                    local valStr = substituteString (substituteString (val as string) "\"" "'") "\n" " "
                    if valStr.count > 200 do valStr = (substring valStr 1 200) + "..."
                    if not first do result += ","
                    first = false
                    result += "\"" + (p as string) + "\": \"" + valStr + "\""
                ) catch ()
            )
            result += "}}"
            result
        )
    )
)
```

**Return format:**
```json
{
  "name": "RS_Proxy001",
  "class": "RedshiftProxy",
  "position": [100, 0, 0],
  "properties": {
    "fileName": "C:/assets/tree.rs",
    "displayMode": "2",
    "displayPercent": "100.0"
  }
}
```

---

### 3.13 `set_redshift_camera_overrides`

**Purpose:** Set Redshift camera overrides on a camera object (exposure, DOF, motion blur, lens distortion).

**Parameters:**

| Name | Type | Default | Description |
|------|------|---------|-------------|
| `camera_name` | `str` | required | Name of the camera object. |
| `properties` | `dict[str, str]` | required | Dict of RS camera property names to MAXScript values. |

**Implementation note:** Redshift camera overrides may be exposed as:
1. Direct properties on the camera node (injected by Redshift plugin).
2. A custom attribute definition attached to the camera.
3. A modifier added to the camera stack.

The introspection scripts in Section 2.11 will reveal which method applies.

**MAXScript template:**

```maxscript
(
    local cam = getNodeByName "{safe_camera}"
    if cam == undefined then (
        "{\"error\": \"Camera not found: {safe_camera}\"}"
    ) else if not (isKindOf cam camera) then (
        "{\"error\": \"Object is not a camera: " + ((classOf cam) as string) + "\"}"
    ) else (
        -- Try direct property access first (RS injects properties)
        local okList = #()
        local errList = #()
        {props_block}
        -- If no properties were set directly, try via custom attributes
        if okList.count == 0 and errList.count > 0 do (
            -- Reset and try CustAttributes path
            okList = #()
            errList = #()
            local cas = custAttributes.get cam
            if cas != undefined do (
                for ca in cas do (
                    {ca_props_block}
                )
            )
        )
        local result = "{\"camera\": \"" + cam.name + "\""
        result += ", \"set\": " + (okList.count as string)
        if errList.count > 0 do (
            result += ", \"errors\": ["
            for i = 1 to errList.count do (
                if i > 1 do result += ","
                result += "\"" + (substituteString errList[i] "\"" "'") + "\""
            )
            result += "]"
        )
        result += "}"
        result
    )
)
```

**Common camera override properties (to be confirmed):**

| Property | Type | Description |
|----------|------|-------------|
| `rs_exposure` or `exposure` | float | EV exposure compensation |
| `rs_whiteBalance` | color | White balance color |
| `rs_dofEnabled` | bool | Enable depth of field |
| `rs_fStop` | float | Aperture f-stop |
| `rs_focusDistance` | float | Focus distance |
| `rs_bokehBlades` | int | Number of aperture blades |
| `rs_motionBlurEnabled` | bool | Enable motion blur |
| `rs_motionBlurDeformationEnabled` | bool | Deformation motion blur |
| `rs_shutterStart` | float | Shutter open time |
| `rs_shutterEnd` | float | Shutter close time |
| `rs_lensDistortionEnabled` | bool | Lens distortion |
| `rs_lensDistortionType` | int | Distortion type |

**Return format:**
```json
{
  "camera": "Camera001",
  "set": 3
}
```

---

## 4. Testing Strategy

### 4.1 Prerequisites

Before running any tests:
1. Open 3ds Max with Redshift installed and activated as the current renderer.
2. Start the MCP TCP listener (`maxscript/mcp_server.ms`).
3. Connect the MCP server.

### 4.2 Test Categories

#### Test A: Renderer Validation

```
Test A1: get_redshift_settings with no filter
  Expected: JSON with "renderer" containing "Redshift", "propertyCount" > 0
  Verify: properties array is not empty

Test A2: get_redshift_settings with filter "*Sample*"
  Expected: Only properties containing "Sample" in the name
  Verify: All returned property names match the pattern

Test A3: get_redshift_settings when renderer is NOT Redshift
  Setup: Set renderer to Default Scanline
  Expected: JSON with "error" key mentioning "not Redshift"

Test A4: set_redshift_settings with valid properties
  Input: {"UnifiedMaxSamples": "512", "UnifiedMinSamples": "32"}
  Expected: {"set": 2, "errors": 0}
  Verify: get_redshift_settings confirms new values

Test A5: set_redshift_settings with invalid property
  Input: {"NonExistentProperty123": "42"}
  Expected: {"set": 0, "errors": 1, "errDetails": [...]}

Test A6: set_redshift_gpu with valid GPU index
  Input: device_indices=[0]
  Expected: JSON with "totalGPUs" >= 1, "activeGPUs" containing 0
  Verify: deviceNames array has valid GPU name strings

Test A7: set_redshift_gpu with invalid GPU index
  Input: device_indices=[99]
  Expected: JSON with "error" mentioning "Invalid GPU indices"
```

#### Test B: Lights

```
Test B1: create_redshift_light with type "dome"
  Expected: JSON with "class" containing a dome light class name
  Verify: Light exists in scene (get_redshift_lights returns it)

Test B2: create_redshift_light with type "area", custom name and position
  Input: light_type="area", name="KeyLight", position=[100, -200, 300], intensity=2.0
  Expected: JSON with "name"="KeyLight", position matches
  Verify: inspect_object confirms the light

Test B3: create_redshift_light with type "sun"
  Expected: JSON with class matching a sun/directional light
  Verify: Light exists in scene

Test B4: create_redshift_light with invalid type
  Input: light_type="nonexistent"
  Expected: JSON with "error"

Test B5: get_redshift_lights after creating 3 lights
  Setup: Create dome + area + sun lights
  Expected: JSON with "count"=3, all three listed

Test B6: create_redshift_light with extra properties
  Input: light_type="dome", properties={"texture": '"C:/hdri/studio.exr"'}
  Expected: Success with extraPropsSet > 0
```

#### Test C: AOVs

```
Test C1: add_redshift_aov with type "diffuse"
  Expected: JSON with "class" containing "Diffuse", "enabled"=true
  Verify: get_redshift_aovs lists it

Test C2: Add multiple AOVs (depth, normals, motion_vectors)
  Expected: All three created successfully
  Verify: get_redshift_aovs shows all three

Test C3: add_redshift_aov with invalid type
  Input: aov_type="nonexistent"
  Expected: JSON with "error"

Test C4: add_redshift_aov with class_override
  Input: aov_type="custom", class_override="RS_Aov_ObjectBumpNormal"
  Expected: Success if class exists, clear error if not

Test C5: remove_redshift_aov by index
  Setup: Create 3 AOVs, note indices
  Input: index=1
  Expected: Correct AOV removed, remaining count decremented

Test C6: remove_redshift_aov by class_name
  Input: class_name="Depth"
  Expected: Depth AOV removed

Test C7: remove_redshift_aov with remove_all=true
  Setup: Add 3 diffuse AOVs
  Input: class_name="Diffuse", remove_all=true
  Expected: All 3 removed

Test C8: get_redshift_aovs with redshift_only=false
  Expected: Lists ALL render elements, not just RS ones
```

#### Test D: Materials

```
Test D1: create_redshift_material with no preset
  Input: name="TestMat"
  Expected: JSON with "class"="RS_Standard_Material"

Test D2: create_redshift_material with "chrome" preset
  Input: preset="chrome", assign_to=["Box001"]
  Setup: Create a Box named Box001 first
  Expected: Material created, assigned to 1 object
  Verify: inspect_properties target="material" shows metalness=1.0

Test D3: create_redshift_material with "glass" preset
  Expected: Material with refraction properties set

Test D4: create_redshift_material with custom properties
  Input: properties={"base_color": "color 100 200 50", "metalness": "0.8"}
  Expected: Both properties set

Test D5: get_redshift_material_properties with layer_filter
  Setup: Assign RS material to an object
  Input: name="Box001", layer_filter="reflection"
  Expected: Only reflection-layer properties returned

Test D6: get_redshift_material_properties on non-RS material
  Setup: Assign PhysicalMaterial to an object
  Expected: JSON with "error" mentioning "not Redshift type"
```

#### Test E: Proxies

```
Test E1: create_redshift_proxy with valid .rs file
  Setup: Need a valid .rs proxy file on disk
  Input: file_path="C:/assets/test.rs", name="TreeProxy"
  Expected: JSON with proxy object created

Test E2: create_redshift_proxy with non-existent file
  Input: file_path="C:/nonexistent/fake.rs"
  Expected: Object created but file may not load (implementation should note this)

Test E3: get_redshift_proxy_info
  Setup: Create a proxy object
  Expected: JSON with file path and display properties

Test E4: get_redshift_proxy_info on non-proxy object
  Input: name="Box001"
  Expected: JSON with "error" mentioning "not a Redshift proxy"
```

#### Test F: Camera Overrides

```
Test F1: set_redshift_camera_overrides on a free camera
  Setup: Create FreeCamera named "RenderCam"
  Input: camera_name="RenderCam", properties={"rs_dofEnabled": "true", "rs_fStop": "2.8"}
  Expected: At least some properties set (depends on RS camera attribute injection)

Test F2: set_redshift_camera_overrides on non-camera
  Input: camera_name="Box001"
  Expected: JSON with "error" mentioning "not a camera"

Test F3: set_redshift_camera_overrides on missing camera
  Input: camera_name="NonExistentCam"
  Expected: JSON with "error" mentioning "not found"
```

### 4.3 Integration Test

Full workflow test:

```
1. set_redshift_settings: Set resolution to 1280x720, samples to 64/256
2. set_redshift_gpu: Select GPU 0
3. create_redshift_light: Create dome light with HDRI
4. create_redshift_light: Create area key light
5. create_redshift_material: Create chrome material, assign to a sphere
6. create_redshift_material: Create glass material, assign to another sphere
7. add_redshift_aov: Add diffuse, specular, depth, normals
8. get_redshift_aovs: Verify 4 AOVs exist
9. get_redshift_settings filter="*Sample*": Verify sample settings
10. render_scene: Render the scene (existing tool)
11. Verify output includes AOV passes
```

---

## 5. Implementation Order

### Phase 1: Foundation and Introspection (Day 1)

**Priority: CRITICAL -- must happen first**

1. Run ALL introspection scripts from Section 2 inside 3ds Max.
2. Document the exact class names and property names in a local reference file.
3. Confirm or update the AOV type-to-class mapping.
4. Confirm or update the light type-to-class mapping.
5. Confirm GPU API function names.
6. Confirm camera override property injection method.

**Output:** Populated lookup tables. No code written yet.

### Phase 2: Render Settings + GPU (Day 1-2)

**Priority: HIGH -- most requested, foundation for everything else**

1. Create `src/tools/redshift.py` with file header and `_safe_name`.
2. Implement `get_redshift_settings`.
3. Implement `set_redshift_settings`.
4. Implement `set_redshift_gpu`.
5. Add `redshift` to the import line in `src/server.py`.
6. Run Tests A1-A7.

**Dependencies:** None (only needs Redshift as active renderer).

### Phase 3: Lights (Day 2)

**Priority: HIGH -- needed for any scene setup**

1. Implement `create_redshift_light`.
2. Implement `get_redshift_lights`.
3. Run Tests B1-B6.

**Dependencies:** Phase 1 (confirmed light class names).

### Phase 4: AOVs (Day 2-3)

**Priority: HIGH -- essential for production rendering**

1. Implement `add_redshift_aov`.
2. Implement `get_redshift_aovs`.
3. Implement `remove_redshift_aov`.
4. Run Tests C1-C8.

**Dependencies:** Phase 1 (confirmed AOV class names).

### Phase 5: Materials (Day 3)

**Priority: MEDIUM -- existing tools partially cover this, but layer control is needed**

1. Implement `create_redshift_material` with preset system.
2. Implement `get_redshift_material_properties` with layer categorization.
3. Run Tests D1-D6.

**Dependencies:** Phase 1 (confirmed RS_Standard_Material property names and layer prefixes).

### Phase 6: Proxies (Day 3-4)

**Priority: MEDIUM -- important for large scenes**

1. Implement `create_redshift_proxy`.
2. Implement `get_redshift_proxy_info`.
3. Run Tests E1-E4.

**Dependencies:** Phase 1 (confirmed proxy class name and file property name).

### Phase 7: Camera Overrides (Day 4)

**Priority: MEDIUM -- frequently needed but can be done via execute_maxscript in the interim**

1. Implement `set_redshift_camera_overrides`.
2. Run Tests F1-F3.

**Dependencies:** Phase 1 (confirmed camera override injection method). This is the highest-risk tool because the camera override mechanism varies significantly between RS versions.

### Phase 8: Integration Testing and Polish (Day 4-5)

1. Run the full integration test (Section 4.3).
2. Update `skills/3dsmax-mcp-dev/SKILL.md` with Redshift tool documentation.
3. Update `TODO.md` to mark render settings and lights as done.
4. Add Redshift-specific entries to the Tool Selection Cheat Sheet.

---

## 6. Known Risks and Mitigations

### Risk 1: Class Name Instability

**Problem:** Redshift class names change between versions. For example, `rsDomeLight` might be `RS_DomeLight` or `rsEnvironment` in different versions.

**Mitigation:**
- Every tool that creates an object uses a **fallback candidate list** (try multiple class names).
- Every tool that detects RS objects uses **pattern matching** (`matchPattern ... pattern:"rs*"`) instead of exact class comparison.
- The introspection scripts in Section 2 MUST be run before implementation to populate the correct lookup tables for the installed version.

### Risk 2: Property Name Changes

**Problem:** Render setting property names may differ between RS versions. For example, `UnifiedMaxSamples` vs `MaxSamples` vs `SamplesMax`.

**Mitigation:**
- `get_redshift_settings` and `set_redshift_settings` operate on **user-provided property names** discovered via introspection. They do not hardcode property names except for presets.
- Preset dictionaries are documented and version-specific. They are defined as Python constants that can be easily updated.
- The `filter` parameter on `get_redshift_settings` lets users discover property names themselves.

### Risk 3: AOV Class Names

**Problem:** AOV render element class names are the most version-volatile. `RS_Aov_Diffuse` vs `RS_Aov_DiffuseLighting` vs `Redshift_Aov_DiffuseFilter`.

**Mitigation:**
- The `class_override` parameter on `add_redshift_aov` lets users bypass the lookup table entirely.
- The lookup table is built from introspection, not documentation.
- `get_redshift_aovs` discovers all AOVs by pattern matching, not by a fixed list.

### Risk 4: Camera Override Method

**Problem:** Redshift camera overrides may be injected as direct node properties, custom attributes, or modifiers depending on the RS version and 3ds Max integration method.

**Mitigation:**
- `set_redshift_camera_overrides` tries three access paths in order: direct property, custom attribute, modifier.
- The introspection script (Section 2.11) will reveal the correct path before implementation.
- If all paths fail, the error message is descriptive enough for the user to fall back to `execute_maxscript`.

### Risk 5: GPU API Availability

**Problem:** `rsSetCudaDevices`, `rsGetNumCudaDevices`, `rsGetCudaDeviceName` may not exist in all RS builds (e.g., CPU-only fallback, or renamed functions).

**Mitigation:**
- Wrap all GPU API calls in `try/catch`.
- Return descriptive errors including the exception message.
- The introspection script (Section 2.10) will confirm availability.

### Risk 6: Proxy Class Discovery

**Problem:** The Redshift proxy class name is not standardized across platforms and versions.

**Mitigation:**
- Try 5 candidate class names in order.
- File path property name is also tried with 3 variants (`fileName`, `file`, `proxyFile`).
- `get_redshift_proxy_info` uses pattern matching to identify proxy objects.

### Risk 7: Large Property Dumps

**Problem:** `Redshift_Renderer()` can have 200+ properties. Dumping all at once may exceed response size limits or be too noisy.

**Mitigation:**
- `get_redshift_settings` has a `filter` parameter for wildcards.
- `get_redshift_settings` has a `max_properties` cap.
- `get_redshift_material_properties` has a `layer_filter` to scope to one material layer.

### Risk 8: TCP Timeout on Complex Operations

**Problem:** Some operations (especially render element enumeration on large scenes) may be slow.

**Mitigation:**
- Use `client.send_command(maxscript, timeout=30.0)` for tools that may be slow.
- The default 120s timeout in `MaxClient` is adequate for most operations.
- Render-related tools (`set_redshift_settings`, `add_redshift_aov`) should not trigger actual rendering.

### Risk 9: Concurrent Modifications

**Problem:** If the user changes the active renderer between `get_redshift_settings` and `set_redshift_settings` calls, the set operation will fail.

**Mitigation:**
- Every mutating tool re-checks that the active renderer is Redshift before proceeding.
- Error messages clearly state the current renderer when validation fails.

---

## Appendix A: Server Registration

After creating `src/tools/redshift.py`, add `redshift` to the import line in `src/server.py`:

```python
# Before:
from .tools import execute, scene, objects, materials, render, viewport, identify, transform, hierarchy, modifiers, selection, clone, scene_manage, visibility, inspect, build, grid, floor_plan, scene_query, effects, material_ops, state_sets, data_channel, wire_params, controllers, scattering  # noqa: E402, F401

# After:
from .tools import execute, scene, objects, materials, render, viewport, identify, transform, hierarchy, modifiers, selection, clone, scene_manage, visibility, inspect, build, grid, floor_plan, scene_query, effects, material_ops, state_sets, data_channel, wire_params, controllers, scattering, redshift  # noqa: E402, F401
```

## Appendix B: SKILL.md Updates

Add to `skills/3dsmax-mcp-dev/SKILL.md` under the Tool Selection Cheat Sheet:

```markdown
### Redshift Renderer
- Read render settings -> `get_redshift_settings` (supports wildcard filter)
- Set render settings -> `set_redshift_settings` (dict of property:value)
- GPU selection -> `set_redshift_gpu` (list of GPU indices)
- Create RS light -> `create_redshift_light` (dome, area, sun, ies, portal)
- List RS lights -> `get_redshift_lights`
- Add AOV/render element -> `add_redshift_aov` (diffuse, depth, normals, etc.)
- List AOVs -> `get_redshift_aovs`
- Remove AOV -> `remove_redshift_aov` (by index or class pattern)
- Create RS material -> `create_redshift_material` (presets: chrome, glass, skin, plastic, emissive)
- Inspect RS material -> `get_redshift_material_properties` (layer filter support)
- Create RS proxy -> `create_redshift_proxy` (from .rs file)
- Inspect RS proxy -> `get_redshift_proxy_info`
- Camera overrides -> `set_redshift_camera_overrides` (exposure, DOF, motion blur)
```

## Appendix C: File Structure Summary

```
src/tools/redshift.py          <-- NEW: All Redshift tools (~800-1200 lines)
src/server.py                  <-- MODIFIED: Add 'redshift' to import line
skills/3dsmax-mcp-dev/SKILL.md <-- MODIFIED: Add Redshift tool cheat sheet
TODO.md                        <-- MODIFIED: Mark render settings as done
```

## Appendix D: Tool Count Summary

| Category | Tool | Priority |
|----------|------|----------|
| Render Settings | `get_redshift_settings` | Phase 2 |
| Render Settings | `set_redshift_settings` | Phase 2 |
| GPU | `set_redshift_gpu` | Phase 2 |
| Lights | `create_redshift_light` | Phase 3 |
| Lights | `get_redshift_lights` | Phase 3 |
| AOVs | `add_redshift_aov` | Phase 4 |
| AOVs | `get_redshift_aovs` | Phase 4 |
| AOVs | `remove_redshift_aov` | Phase 4 |
| Materials | `create_redshift_material` | Phase 5 |
| Materials | `get_redshift_material_properties` | Phase 5 |
| Proxies | `create_redshift_proxy` | Phase 6 |
| Proxies | `get_redshift_proxy_info` | Phase 6 |
| Camera | `set_redshift_camera_overrides` | Phase 7 |

**Total: 13 new tools across 7 phases.**
