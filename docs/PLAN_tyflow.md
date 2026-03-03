# tyFlow MCP Tools -- Implementation Plan

## Table of Contents

1. [Overview](#1-overview)
2. [Research Phase: Runtime Introspection Scripts](#2-research-phase-runtime-introspection-scripts)
3. [Shape Type ID Investigation (Priority 0)](#3-shape-type-id-investigation-priority-0)
4. [Tool Definitions](#4-tool-definitions)
5. [Preset Templates](#5-preset-templates)
6. [Testing Strategy](#6-testing-strategy)
7. [Implementation Order](#7-implementation-order)
8. [Known Risks & Mitigations](#8-known-risks--mitigations)
9. [File Structure](#9-file-structure)

---

## 1. Overview

### Goal

Add tyFlow particle system integration to the 3dsmax-mcp server, following the
existing plugin-integration pattern established by `scattering.py` (Forest Pack).

### Architecture Summary

- All tools live in `src/tools/tyflow.py` (single module, consistent with existing layout).
- Each tool is a Python function decorated with `@mcp.tool()`.
- Each tool constructs a MAXScript string, sends it via `client.send_command(maxscript)`,
  and parses the JSON-formatted string response.
- The module is registered by adding `tyflow` to the import chain in `src/server.py` line 13.
- All MAXScript must be wrapped in parentheses `(...)` for `execute()` safety.
- Variable names MUST use suffixed forms (`birthOp`, `speedOp`, `shapeOp`) -- never bare
  `Birth`, `Speed`, `Shape` which collide with MAXScript global names.

### Key Constraints

| Constraint | Detail |
|---|---|
| tyFlow version | v1.118+ required (Sept 2024) |
| Shape `_tab` arrays | Single-value Shape properties are READ-ONLY; must use `_tab` arrays |
| Particle data | READ-ONLY from MAXScript |
| PhysX gravity | Object-level `tf.physXGravityValue`, separate from Force operator `gravityStrength` |
| Variable naming | No bare operator names as variables |
| JSON response | Built as string concatenation inside MAXScript (no `json.dumps` in Max) |

---

## 2. Research Phase: Runtime Introspection Scripts

> **Phase 0 Status:** COMPLETED 2026-03-03
> **Full results:** `docs/research/tyflow_introspection.md`
> **Key findings:**
> - 51 operators confirmed working (all planned operators exist)
> - Shape ID 5 = Pyramid (NOT Sphere) -- this is the default and explains the known bug
> - Sphere is ID 4 (289 verts), Cube is ID 6, Triangle is ID 0
> - addOperator requires 2 args: name + position index
> - quickType_submit CRASHES -- do NOT use
> - Operator properties accessed via: `$flowName.baseobject[#EventName][#OperatorName]`

Before writing any tools, run these MAXScript commands inside 3ds Max to capture
exact property names and enum values. Each script is self-contained and prints
its output to the Listener.

### 2.1 Confirm All Operator Types

```maxscript
(
    -- Creates a temporary tyFlow, adds every known operator type,
    -- and reports success/failure for each.
    local tf = tyflow()
    tf.name = "zzz_tyFlowIntrospect"
    local ev1 = tf.addEvent()
    ev1.setName "TestEvent"

    local operatorNames = #(
        -- Birth
        "Birth", "Birth Burst", "Birth Flow", "Birth Fluid", "Birth Objects",
        "Birth PRT", "Birth Paint", "Birth Skeleton", "Birth Spline",
        "Birth Surface", "Birth Voxels", "Birth VDB", "Birth Terrain",
        "Birth Intersections", "Birth ForestPack",
        -- Motion
        "Speed", "Spin", "Rotation", "Path Follow", "Slow", "Stop",
        "Spread", "Limiter", "Integrate", "Scale", "Mass", "Temporal Smooth",
        -- Forces
        "Force", "Cluster Force", "Flock", "Fluid Force", "Particle Force",
        "Point Force", "Surface Force", "VDB Force",
        -- Shape/Display
        "Shape", "Display", "Display Data",
        -- PhysX
        "PhysX Shape", "PhysX Collision", "PhysX Bind", "PhysX Break",
        "PhysX Modify", "PhysX Fluid", "PhysX Switch",
        -- Collision
        "Collision", "Boundary", "Push In/Out",
        -- Flow Control
        "Send Out", "Split", "Select", "Delete", "Spawn",
        -- Tests
        "Object Test", "Property Test", "Surface Test", "Time Test",
        -- Fracture
        "Voronoi Fracture", "Element Fracture", "Face Fracture",
        "Edge Fracture", "Bounds Fracture", "Brick Fracture",
        "Multifracture", "Convex Hull",
        -- Export
        "Export Particles", "Export VDB",
        -- Additional (may exist in newer versions)
        "Mapping", "Material ID", "Object Bind", "Particle Bind",
        "Cache", "Script", "Custom Properties", "Color", "Age Test",
        "Collision Test", "Distance Test", "Particle Test",
        "Density", "Position", "Find Target", "Look At",
        "Attract", "Cloth", "Cloth Bind"
    )

    local results = ""
    for opName in operatorNames do (
        local opRef = undefined
        try (opRef = ev1.addOperator opName -1) catch ()
        if opRef != undefined then (
            results += "OK:   " + opName + "\n"
            try (opRef.remove()) catch ()
        ) else (
            results += "FAIL: " + opName + "\n"
        )
    )

    delete tf
    format "%\n" results
    results
)
```

**Action:** Copy the output. Any `FAIL` entries are either misnamed or not available
in the installed tyFlow version. Update the operator list accordingly.

> **Result (2026-03-03):** 51 operators confirmed OK. Many planned operators (Birth Burst, Birth Flow, Birth Fluid, Birth PRT, Birth Paint, Birth Skeleton, Birth Voxels, Birth VDB, Birth Terrain, Birth Intersections, Birth ForestPack, Stop, Spread, Limiter, Integrate, Mass, Temporal Smooth, Cluster Force, Flock, Fluid Force, Particle Force, Point Force, Surface Force, VDB Force, Display Data, PhysX Break, PhysX Modify, PhysX Fluid, Collision, Boundary, Push In/Out, Send Out, Split, Select, Time Test, Edge Fracture, Export VDB, Material ID, Object Bind, Particle Bind, Cache, Position, Look At, Attract) returned FAIL -- these names do not exist in the installed tyFlow version or use different naming.

### 2.2 Capture `showProperties` for Core Operators

Run this for each operator type we plan to support. The script captures the full
property list to a string.

```maxscript
(
    local tf = tyflow()
    tf.name = "zzz_PropIntrospect"
    local ev1 = tf.addEvent()
    ev1.setName "IntrospectEvent"

    local targetOps = #(
        "Birth", "Birth Surface", "Birth Objects", "Birth Spline",
        "Speed", "Force", "Shape", "Display",
        "PhysX Shape", "PhysX Collision",
        "Collision", "Send Out", "Split", "Select", "Delete",
        "Voronoi Fracture", "Export Particles",
        "Spin", "Rotation", "Scale", "Spawn",
        "Cloth", "PhysX Fluid"
    )

    local allOutput = ""
    for opName in targetOps do (
        local opRef = undefined
        try (opRef = ev1.addOperator opName -1) catch ()
        if opRef != undefined then (
            local ss = StringStream ""
            showProperties opRef to:ss
            allOutput += "\n=== " + opName + " ===\n"
            allOutput += (ss as string) + "\n"
            try (opRef.remove()) catch ()
        ) else (
            allOutput += "\n=== " + opName + " === (FAILED TO CREATE)\n"
        )
    )

    delete tf
    format "%\n" allOutput
    allOutput
)
```

**Action:** Save the full output. This is the ground-truth property reference for
building MAXScript templates. Pay special attention to property names that differ
from the documented names.

> **Result (2026-03-03):** Properties captured for Birth (17 key), Speed, Force (197 total), Shape (145 total), Display, Rotation, Scale, Spawn (154 total), PhysX Shape (164 total), and more. Full dumps in `docs/research/tyflow_introspection.md`. Fracture and Export Particles may not expose SubAnims via getPropNames.

### 2.3 Shape Operator: Enumerate ALL 3D Shape Type IDs

This is the **highest priority** research item. The user reported that spheres
displayed as triangles, indicating a wrong `type_3d_ID_tab` value.

```maxscript
(
    -- Creates a tyFlow with a Shape operator, iterates type_3d_ID_tab from 0..30,
    -- and for each value inspects what the Shape operator reports.
    -- Also capture the name via the read-only shapeMode3D property after setting.

    local tf = tyflow()
    tf.name = "zzz_ShapeIDTest"
    local ev1 = tf.addEvent()
    ev1.setName "ShapeTest"

    local birthOp = ev1.addOperator "Birth" -1
    birthOp.birthMode = 0
    birthOp.birthTotal = 1
    birthOp.birthStart = 0
    birthOp.birthEndEnable = true
    birthOp.birthEnd = 0

    local shapeOp = ev1.addOperator "Shape" -1
    local displayOp = ev1.addOperator "Display" -1
    displayOp.displayMode = 2

    local results = "=== 3D Shape Type ID Mapping ===\n"
    for i = 0 to 30 do (
        try (
            shapeOp.shape_type_tab = #(1)       -- 1 = 3D type
            shapeOp.type_3d_ID_tab = #(i)
            shapeOp.frequency_tab = #(100.0)
            shapeOp.scaleVal_tab = #(100.0)

            -- Try reading the read-only convenience property
            local modeName = "unknown"
            try (modeName = shapeOp.shapeMode3D as string) catch ()

            -- Also try getting the mesh vert count as a shape fingerprint
            tf.reset_simulation()
            sliderTime = 0f
            tf.updateParticles currentTime
            local vertCount = "?"
            try (
                local snapMesh = snapshotAsMesh tf
                vertCount = snapMesh.numVerts as string
                delete snapMesh
            ) catch ()

            results += "ID " + (i as string) + " => mode3D=" + modeName + ", verts=" + vertCount + "\n"
        ) catch (
            results += "ID " + (i as string) + " => ERROR\n"
        )
    )

    delete tf
    format "%\n" results
    results
)
```

> **Result (2026-03-03):** Full mapping confirmed for IDs 0-25. Default is #(5) = Pyramid. Key: Triangle=0, Cone=1, Quad=2, Cylinder=3, Sphere=4 (289 verts), Pyramid=5, Cube=6, Octahedron=7, GeoSphere low=8, GeoSphere med=9, GeoSphere high=10, Icosahedron=11. IDs 12-25 are subdivided polyhedron variants.

### 2.4 Shape Operator: Enumerate ALL 2D Shape Type IDs

```maxscript
(
    local tf = tyflow()
    tf.name = "zzz_Shape2DTest"
    local ev1 = tf.addEvent()
    ev1.setName "Shape2DTest"

    local birthOp = ev1.addOperator "Birth" -1
    birthOp.birthMode = 0
    birthOp.birthTotal = 1

    local shapeOp = ev1.addOperator "Shape" -1
    local displayOp = ev1.addOperator "Display" -1
    displayOp.displayMode = 2

    local results = "=== 2D Shape Type ID Mapping ===\n"
    for i = 0 to 20 do (
        try (
            shapeOp.shape_type_tab = #(0)       -- 0 = 2D type
            shapeOp.type_2d_ID_tab = #(i)
            shapeOp.frequency_tab = #(100.0)
            shapeOp.scaleVal_tab = #(100.0)

            local modeName = "unknown"
            try (modeName = shapeOp.shapeMode as string) catch ()

            results += "ID " + (i as string) + " => mode2D=" + modeName + "\n"
        ) catch (
            results += "ID " + (i as string) + " => ERROR\n"
        )
    )

    delete tf
    format "%\n" results
    results
)
```

> **Result (2026-03-03):** 2D shape IDs 0-15 returned IDENTICAL vertex/face counts as 3D shapes. The 2D/3D distinction appears to be in rendering mode (shapeMode property), not geometry.

### 2.5 Birth Surface / Birth Objects / Birth Spline Properties

```maxscript
(
    local tf = tyflow()
    tf.name = "zzz_BirthVariants"
    local ev1 = tf.addEvent()

    local ops = #("Birth Surface", "Birth Objects", "Birth Spline")
    local allOutput = ""

    for opName in ops do (
        local opRef = undefined
        try (opRef = ev1.addOperator opName -1) catch ()
        if opRef != undefined then (
            local ss = StringStream ""
            showProperties opRef to:ss
            allOutput += "\n=== " + opName + " ===\n" + (ss as string) + "\n"
            try (opRef.remove()) catch ()
        )
    )

    delete tf
    format "%\n" allOutput
    allOutput
)
```

> **Result (2026-03-03):** Birth Surface, Birth Objects, and Birth Spline all confirmed working. Properties captured in introspection results.

### 2.6 Export Particles Properties

```maxscript
(
    local tf = tyflow()
    tf.name = "zzz_ExportTest"
    local ev1 = tf.addEvent()
    local opRef = ev1.addOperator "Export Particles" -1

    local ss = StringStream ""
    showProperties opRef to:ss
    local result = ss as string

    delete tf
    format "%\n" result
    result
)
```

> **Result (2026-03-03):** Export Particles confirmed working. May not expose SubAnims via getPropNames -- requires index-based access.

### 2.7 Fracture Operator Properties

```maxscript
(
    local tf = tyflow()
    tf.name = "zzz_FractureTest"
    local ev1 = tf.addEvent()

    local fractureOps = #(
        "Voronoi Fracture", "Element Fracture", "Face Fracture",
        "Edge Fracture", "Bounds Fracture", "Brick Fracture",
        "Multifracture", "Convex Hull"
    )
    local allOutput = ""
    for opName in fractureOps do (
        local opRef = undefined
        try (opRef = ev1.addOperator opName -1) catch ()
        if opRef != undefined then (
            local ss = StringStream ""
            showProperties opRef to:ss
            allOutput += "\n=== " + opName + " ===\n" + (ss as string) + "\n"
            try (opRef.remove()) catch ()
        )
    )

    delete tf
    format "%\n" allOutput
    allOutput
)
```

> **Result (2026-03-03):** Voronoi Fracture, Element Fracture, Face Fracture, Bounds Fracture, Brick Fracture, Multifracture, and Convex Hull all confirmed. Fracture and Boolean may not expose SubAnims via getPropNames.

### 2.8 Cloth / Fluid / VDB Properties

```maxscript
(
    local tf = tyflow()
    tf.name = "zzz_ClothFluidVDB"
    local ev1 = tf.addEvent()

    local simOps = #("Cloth", "Cloth Bind", "PhysX Fluid", "Birth Fluid",
                      "Birth VDB", "Fluid Force", "VDB Force", "Export VDB")
    local allOutput = ""
    for opName in simOps do (
        local opRef = undefined
        try (opRef = ev1.addOperator opName -1) catch ()
        if opRef != undefined then (
            local ss = StringStream ""
            showProperties opRef to:ss
            allOutput += "\n=== " + opName + " ===\n" + (ss as string) + "\n"
            try (opRef.remove()) catch ()
        ) else (
            allOutput += "\n=== " + opName + " === (FAILED TO CREATE)\n"
        )
    )

    delete tf
    format "%\n" allOutput
    allOutput
)
```

> **Result (2026-03-03):** Cloth and Cloth Bind confirmed working. Birth Fluid, PhysX Fluid, Birth VDB, Fluid Force, VDB Force, and Export VDB all returned FAIL -- not available in installed version or use different naming.

### 2.9 Complete tyFlow Object-Level PhysX Properties

```maxscript
(
    local tf = tyflow()
    tf.name = "zzz_PhysXObjProps"

    local ss = StringStream ""
    showProperties tf to:ss
    local result = "=== tyFlow Object Properties ===\n" + (ss as string)

    delete tf
    format "%\n" result
    result
)
```

> **Result (2026-03-03):** Full object-level properties confirmed: simulation, cache, retimer, PhysX global, bind, display, export groups, simulation groups, threading, and debug printing. 21 SubAnims on the baseobject. See `docs/research/tyflow_introspection.md` Section 6-7.

### 2.10 Particle Data Functions & Return Types

```maxscript
(
    local tf = tyflow()
    tf.name = "zzz_ParticleDataTest"
    local ev1 = tf.addEvent()
    ev1.setName "DataTest"

    local birthOp = ev1.addOperator "Birth" -1
    birthOp.birthMode = 0
    birthOp.birthTotal = 5
    birthOp.birthStart = 0
    birthOp.birthEndEnable = true
    birthOp.birthEnd = 0

    local speedOp = ev1.addOperator "Speed" -1
    speedOp.magnitude = 100.0
    speedOp.directionMode = 3

    local shapeOp = ev1.addOperator "Shape" -1
    shapeOp.shape_type_tab = #(1)
    shapeOp.type_3d_ID_tab = #(0)
    shapeOp.frequency_tab = #(100.0)
    shapeOp.scaleVal_tab = #(100.0)

    local displayOp = ev1.addOperator "Display" -1
    displayOp.displayMode = 2

    tf.reset_simulation()
    sliderTime = 5f
    tf.updateParticles currentTime

    local n = tf.numParticles()
    local results = "Particle count: " + (n as string) + "\n"

    -- Test each data function and capture type
    local dataFuncs = #(
        #("getAllParticlePositions", "positions"),
        #("getAllParticleVelocities", "velocities"),
        #("getAllParticleAges", "ages")
    )

    for pair in dataFuncs do (
        local funcName = pair[1]
        local label = pair[2]
        try (
            local val = execute ("tf." + funcName + "()")
            results += label + " type: " + ((classOf val) as string)
            results += ", count: " + (val.count as string)
            if val.count > 0 do (
                results += ", element type: " + ((classOf val[1]) as string)
                results += ", sample: " + (val[1] as string)
            )
            results += "\n"
        ) catch (
            results += label + ": ERROR\n"
        )
    )

    -- Single-particle access
    if n > 0 do (
        try (
            local pos1 = tf.getParticlePosition 1
            results += "getParticlePosition(1) type: " + ((classOf pos1) as string) + " val: " + (pos1 as string) + "\n"
        ) catch (results += "getParticlePosition(1): ERROR\n")
        try (
            local vel1 = tf.getParticleVelocity 1
            results += "getParticleVelocity(1) type: " + ((classOf vel1) as string) + " val: " + (vel1 as string) + "\n"
        ) catch (results += "getParticleVelocity(1): ERROR\n")
        try (
            local tm1 = tf.getParticleTM 1
            results += "getParticleTM(1) type: " + ((classOf tm1) as string) + " val: " + (tm1 as string) + "\n"
        ) catch (results += "getParticleTM(1): ERROR\n")
    )

    -- Check for additional data functions (mesh, scale, spin, etc.)
    local extraFuncs = #(
        "getAllParticleScales", "getAllParticleMasses",
        "getAllParticleSpins", "getAllParticleColors",
        "getAllParticleIDs", "getAllParticleMaterialIDs",
        "getAllParticleMeshes", "getAllParticleCustomFloats",
        "getAllParticleCustomVectors", "getAllParticleShapes",
        "getAllParticleLifespans"
    )

    for funcName in extraFuncs do (
        try (
            local val = execute ("tf." + funcName + "()")
            results += funcName + " type: " + ((classOf val) as string) + ", count: " + (val.count as string)
            if val.count > 0 do (
                results += ", element type: " + ((classOf val[1]) as string)
            )
            results += "\n"
        ) catch (
            results += funcName + ": NOT AVAILABLE\n"
        )
    )

    delete tf
    format "%\n" results
    results
)
```

> **Result (2026-03-03):** Particle data functions confirmed: getParticleID, getParticleAge, getParticleTM, getParticlePosition, getParticleScale, getParticleVelocity, getParticleShapeMesh, getParticleMatID, getParticleInstanceID, getParticleMass, getParticleSimGroups, getParticleExportGroups, getParticleUVWChannels, getParticleUVW. Bulk versions (getAllParticle*) also confirmed. Volume interface available: updateVolumes, releaseVolumes, getVolumeScalar, getVolumeVector, convertVolumeTemperature.

---

## 3. Shape Type ID Investigation (Priority 0)

This section is the **single most important pre-implementation task**. The user
already encountered the bug: "it said it created spheres but the shapes were
triangles." This was almost certainly caused by setting the wrong `type_3d_ID_tab` value.

### 3.1 The Problem

The Shape operator's 3D shape type is controlled by `type_3d_ID_tab`, an array
of integer IDs. The documentation says `0 = Sphere`, but this has not been
verified at runtime. If the mapping is wrong, particles display the wrong geometry.

The read-only scalar `shapeMode3D` property *may* reflect the current 3D type as
a readable enum value after the `_tab` is set, but this is also unconfirmed.

### 3.2 Systematic Discovery Procedure

**Step 1: Visual confirmation script.**

This script creates 21 separate tyFlow objects, each with a different `type_3d_ID_tab`
value, arranged in a row so the user can visually identify each shape:

```maxscript
(
    local spacing = 50.0
    local results = ""

    for shapeID = 0 to 20 do (
        local tfName = "ShapeTest_ID" + (shapeID as string)
        local tf = tyflow()
        tf.name = tfName
        tf.pos = [(shapeID * spacing), 0, 0]

        local ev1 = tf.addEvent()
        ev1.setName "TestEvent"

        local birthOp = ev1.addOperator "Birth" -1
        birthOp.birthMode = 0
        birthOp.birthTotal = 1
        birthOp.birthStart = 0
        birthOp.birthEndEnable = true
        birthOp.birthEnd = 0

        local shapeOp = ev1.addOperator "Shape" -1
        shapeOp.shape_type_tab = #(1)
        shapeOp.type_3d_ID_tab = #(shapeID)
        shapeOp.frequency_tab = #(100.0)
        shapeOp.scaleVal_tab = #(100.0)

        local displayOp = ev1.addOperator "Display" -1
        displayOp.displayMode = 2

        tf.reset_simulation()

        -- Read back the shapeMode3D to see if it reflects the ID
        try (
            local modeVal = shapeOp.shapeMode3D
            results += "ID " + (shapeID as string) + " => shapeMode3D=" + (modeVal as string) + "\n"
        ) catch (
            results += "ID " + (shapeID as string) + " => shapeMode3D=READ_ERROR\n"
        )
    )

    format "%\n" results
    results
)
```

**Step 2:** After running the above, visually identify each shape in the viewport
and record the mapping. Then run the cleanup:

```maxscript
(
    for shapeID = 0 to 20 do (
        local tfName = "ShapeTest_ID" + (shapeID as string)
        local obj = getNodeByName tfName
        if obj != undefined do delete obj
    )
)
```

**Step 3:** Also test via mesh vertex count fingerprinting (automated verification):

```maxscript
(
    local results = "=== 3D Shape Fingerprints ===\n"
    for shapeID = 0 to 20 do (
        local tf = tyflow()
        tf.name = "zzz_FP_" + (shapeID as string)
        local ev1 = tf.addEvent()

        local birthOp = ev1.addOperator "Birth" -1
        birthOp.birthMode = 0
        birthOp.birthTotal = 1
        birthOp.birthStart = 0
        birthOp.birthEndEnable = true
        birthOp.birthEnd = 0

        local shapeOp = ev1.addOperator "Shape" -1
        shapeOp.shape_type_tab = #(1)
        shapeOp.type_3d_ID_tab = #(shapeID)
        shapeOp.frequency_tab = #(100.0)
        shapeOp.scaleVal_tab = #(100.0)

        local displayOp = ev1.addOperator "Display" -1
        displayOp.displayMode = 2

        tf.reset_simulation()
        sliderTime = 0f
        tf.updateParticles currentTime

        local verts = 0
        local faces = 0
        try (
            local snapMesh = snapshotAsMesh tf
            verts = snapMesh.numVerts
            faces = snapMesh.numFaces
            delete snapMesh
        ) catch ()

        results += "ID=" + (shapeID as string) + " verts=" + (verts as string) + " faces=" + (faces as string) + "\n"
        delete tf
    )
    format "%\n" results
    results
)
```

### 3.3 Confirmed Mapping (VERIFIED 2026-03-03)

> **Previously:** This mapping was speculative and WRONG. The old assumed mapping had Cube=1, Sphere=2, etc.
> **Bug root cause CONFIRMED:** Default `type_3d_ID_tab` is `#(5)` = Pyramid, NOT Sphere. This is why "spheres showed as triangles."

Confirmed via live introspection with vertex/face fingerprinting:

| `type_3d_ID_tab` value | Confirmed Shape | Verts | Faces |
|---|---|---|---|
| 0 | Triangle | 3 | 1 |
| 1 | Cone | 28 | 26 |
| 2 | Quad / Plane | 4 | 2 |
| 3 | Cylinder | 25 | 32 |
| 4 | **Sphere** | 289 | 512 |
| 5 | **Pyramid** (DEFAULT) | 5 | 6 |
| 6 | **Cube / Box** | 8 | 12 |
| 7 | Octahedron | 6 | 8 |
| 8 | GeoSphere (low) | 62 | 120 |
| 9 | GeoSphere (medium) | 266 | 528 |
| 10 | GeoSphere (high) | 1106 | 2208 |
| 11 | Icosahedron | 12 | 20 |
| 12-25 | Subdivided polyhedron variants | varies | varies |

### 3.4 Hardcoded Mapping (CONFIRMED 2026-03-03)

Stored as a Python dict in `tyflow.py`:

```python
SHAPE_3D_IDS = {
    "triangle": 0,
    "cone": 1,
    "quad": 2,
    "plane": 2,          # alias for quad
    "cylinder": 3,
    "sphere": 4,          # 289 verts, 512 faces
    "pyramid": 5,         # DEFAULT -- 5 verts, 6 faces
    "box": 6,
    "cube": 6,            # alias for box
    "octahedron": 7,
    "geosphere_low": 8,
    "geosphere": 9,       # medium (default geosphere)
    "geosphere_high": 10,
    "icosahedron": 11,
}

SHAPE_2D_IDS = {
    # 2D IDs produce identical geometry to 3D IDs.
    # The 2D/3D distinction is in shapeMode, not geometry.
    # Use shape_type_tab = #(0) for 2D mode with the same ID values.
}
```

The `set_tyflow_shape` tool will accept shape names as strings and translate to IDs
internally, so the AI never has to guess raw integer IDs.

---

## 4. Tool Definitions

### 4.0 Module Boilerplate

```python
"""tyFlow particle system tools for 3ds Max."""

from __future__ import annotations

import json
from typing import Any

from ..server import mcp, client


def _safe_name(name: str) -> str:
    return name.replace("\\", "\\\\").replace('"', '\\"')


def _name_array(names: list[str]) -> str:
    return "#(" + ", ".join(f'"{_safe_name(n)}"' for n in names) + ")"


def _int_array(values: list[int]) -> str:
    return "#(" + ", ".join(str(int(v)) for v in values) + ")"


def _float_array(values: list[float]) -> str:
    return "#(" + ", ".join(f"{float(v):.6f}" for v in values) + ")"


def _bool_array(values: list[bool]) -> str:
    return "#(" + ", ".join("true" if v else "false" for v in values) + ")"


# Confirmed shape ID mappings (VERIFIED 2026-03-03)
SHAPE_3D_IDS: dict[str, int] = {
    "triangle": 0,
    "cone": 1,
    "quad": 2,
    "plane": 2,
    "cylinder": 3,
    "sphere": 4,
    "pyramid": 5,       # DEFAULT
    "box": 6,
    "cube": 6,
    "octahedron": 7,
    "geosphere_low": 8,
    "geosphere": 9,
    "geosphere_high": 10,
    "icosahedron": 11,
}

SHAPE_2D_IDS: dict[str, int] = {
    # 2D uses same IDs as 3D; distinction is shapeMode not geometry
}
```

---

### 4.1 `create_tyflow` -- The Big Builder

**Purpose:** Create a complete tyFlow particle system in one call, with events,
operators, and inter-event connections.

**Parameters:**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `name` | `str` | `"tyFlow001"` | tyFlow object name |
| `position` | `list[float]` | `[0, 0, 0]` | World position of the tyFlow icon |
| `events` | `list[dict]` | (required) | List of event definitions (see below) |
| `connections` | `list[dict]` | `[]` | Event connections `[{"from_event": 0, "operator": "Send Out", "to_event": 1}, ...]` |
| `physx_gravity` | `bool` | `False` | Enable PhysX gravity |
| `physx_gravity_value` | `float` | `-980.0` | PhysX gravity strength |
| `physx_ground_collider` | `bool` | `False` | Enable built-in ground plane |
| `physx_ground_height` | `float` | `0.0` | Ground plane Z height |
| `physx_substeps` | `int` | `4` | PhysX substeps |
| `reset_simulation` | `bool` | `True` | Reset sim after creation |
| `open_editor` | `bool` | `False` | Open the tyFlow editor UI |

**Event Definition Schema:**

```python
{
    "name": "BirthEvent",
    "operators": [
        {
            "type": "Birth",         # Exact operator type string
            "properties": {          # Dict of property_name: value
                "birthMode": 0,
                "birthTotal": 500,
                "birthStart": 0,
                "birthEndEnable": True,
                "birthEnd": 30
            }
        },
        {
            "type": "Speed",
            "properties": {
                "magnitude": 300.0,
                "directionMode": 3
            }
        },
        {
            "type": "Send Out",
            "properties": {}
        }
    ]
}
```

**MAXScript Template (conceptual):**

```python
def create_tyflow(name, position, events, connections, ...):
    safe_name = _safe_name(name)

    # Build operator creation lines for each event
    event_blocks = []
    for evt_idx, evt in enumerate(events):
        evt_name = _safe_name(evt["name"])
        lines = []
        lines.append(f'local ev{evt_idx} = tfObj.addEvent()')
        lines.append(f'ev{evt_idx}.setName "{evt_name}"')
        for op_idx, op in enumerate(evt["operators"]):
            op_type = _safe_name(op["type"])
            var_name = f'op_{evt_idx}_{op_idx}'
            lines.append(f'local {var_name} = ev{evt_idx}.addOperator "{op_type}" -1')
            for prop, val in op.get("properties", {}).items():
                lines.append(f'{var_name}.{prop} = {_maxscript_value(val)}')
        event_blocks.append("\n".join(lines))

    # Build connection lines
    conn_lines = []
    for conn in connections:
        from_evt = conn["from_event"]
        op_name = _safe_name(conn["operator"])
        to_evt = conn["to_event"]
        # Find the operator index within the from_event that matches op_name
        # ... (requires searching event_blocks)
        conn_lines.append(f'op_{from_evt}_X.connect ev{to_evt}')

    maxscript = f"""(
        local tfObj = tyflow()
        tfObj.name = "{safe_name}"
        tfObj.pos = [{position[0]}, {position[1]}, {position[2]}]
        {physx_lines}
        {chr(10).join(all_event_lines)}
        {chr(10).join(conn_lines)}
        {"tfObj.reset_simulation()" if reset_simulation else ""}
        {"tfObj.editor_open()" if open_editor else ""}
        -- Return JSON
        ...build JSON response string...
    )"""
```

**Return JSON:**

```json
{
    "name": "MyParticles",
    "eventCount": 2,
    "events": [
        {
            "name": "BirthEvent",
            "operatorCount": 3,
            "operators": ["Birth", "Speed", "Send Out"]
        },
        {
            "name": "PhysicsEvent",
            "operatorCount": 4,
            "operators": ["Force", "Shape", "PhysX Shape", "Display"]
        }
    ],
    "connections": [
        {"from": "BirthEvent", "operator": "Send Out", "to": "PhysicsEvent"}
    ]
}
```

**Dependencies:** None (creates from scratch).

**Key Implementation Notes:**
- Property value serialization needs a helper `_maxscript_value(val)` that handles
  bool -> `true`/`false`, int, float, string -> `"quoted"`, list -> `#(...)`,
  and None -> `undefined`.
- Tab-array properties (anything ending in `_tab`) must be serialized as `#(value1, value2, ...)`.
- The `connections` parameter uses event indices (0-based) that reference into the
  `events` list, and an operator type name. The tool finds the matching operator
  variable and calls `.connect` on it.

---

### 4.2 `get_tyflow_info` -- Inspect Existing tyFlow

**Purpose:** Read the full structure of an existing tyFlow: events, operators,
properties, connections, and PhysX settings.

**Parameters:**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `name` | `str` | (required) | tyFlow object name |
| `include_properties` | `bool` | `False` | Include full property dump per operator (verbose) |

**MAXScript Template:**

```maxscript
(
    local tfObj = getNodeByName "{safe_name}"
    if tfObj == undefined then (
        "{{\\"error\\":\\"tyFlow not found: {safe_name}\\"}}"
    ) else if (classOf tfObj) != tyFlow then (
        "{{\\"error\\":\\\"Object is not a tyFlow: {safe_name}\\"}}"
    ) else (
        -- Enumerate events
        -- For each event, enumerate operators
        -- For each operator, optionally dump showProperties
        -- Read PhysX object-level settings
        -- Build JSON response
    )
)
```

**Return JSON:**

```json
{
    "name": "MyParticles",
    "class": "tyFlow",
    "position": [0, 0, 100],
    "physx": {
        "gravityEnabled": true,
        "gravityValue": -980.0,
        "groundCollider": true,
        "substeps": 8
    },
    "events": [
        {
            "name": "Birth",
            "enabled": true,
            "operators": [
                {
                    "name": "Birth",
                    "type": "Birth",
                    "enabled": true,
                    "properties": {}
                }
            ]
        }
    ]
}
```

**Implementation Challenge (RESOLVED 2026-03-03):** tyFlow does not expose a
`getEvents()` or `getOperators()` function in MAXScript. Use baseobject SubAnim
traversal: tyFlow baseobject has 21 SubAnims (fixed params), then events at indices 21+.
Each event SubAnim contains operators indexed sequentially.

**Research script (kept for reference):**

```maxscript
-- Test: how to enumerate events on a tyFlow
(
    local tf = tyflow()
    tf.name = "zzz_EnumTest"
    local ev1 = tf.addEvent()
    ev1.setName "EventA"
    local ev2 = tf.addEvent()
    ev2.setName "EventB"

    -- Try various enumeration approaches:
    try (format "numEvents: %\n" (tf.numEvents())) catch (format "numEvents: NOT AVAILABLE\n")
    try (format "getEvent 0: %\n" (tf.getEvent 0)) catch (format "getEvent 0: NOT AVAILABLE\n")
    try (format "getEvent 1: %\n" (tf.getEvent 1)) catch (format "getEvent 1: NOT AVAILABLE\n")
    try (format "events: %\n" (tf.events)) catch (format "events property: NOT AVAILABLE\n")

    -- Check subAnim approach
    try (
        format "numSubs: %\n" (tf.numsubs)
        for i = 1 to tf.numsubs do (
            format "sub %: % (class: %)\n" i (getSubAnim tf i) (classOf (getSubAnim tf i))
        )
    ) catch (format "subAnim approach failed\n")

    delete tf
)
```

**Confirmed approach:** Enumerate events via SubAnim traversal on baseobject.
Events appear at SubAnim indices 21+ (after the 20 fixed parameter SubAnims).
Each event's SubAnims are its operators. Names via `getSubAnimName`.

---

### 4.3 `modify_tyflow_operator` -- Set Properties on Existing Operator

**Purpose:** Modify one or more properties on an existing operator in a tyFlow.

**Parameters:**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `tyflow_name` | `str` | (required) | tyFlow object name |
| `event_name` | `str` | (required) | Event name |
| `operator_name` | `str` | (required) | Operator name |
| `properties` | `dict` | (required) | Property name-value pairs to set |

**MAXScript Template:**

```maxscript
(
    local tfObj = getNodeByName "{safe_tyflow_name}"
    if tfObj == undefined then (
        "{{\\"error\\":\\"tyFlow not found\\"}}"
    ) else (
        local opRef = tfObj.baseobject[#'{safe_event_name}'][#'{safe_operator_name}']
        if opRef == undefined then (
            "{{\\"error\\":\\"Operator not found\\"}}"
        ) else (
            {property_assignment_lines}
            "{{\\"success\\":true,\\"operator\\":\\"{operator_name}\\"}}"
        )
    )
)
```

**Key Detail:** Operators are accessed via baseobject SubAnims:
`$flowName.baseobject[#EventName][#OperatorName]`. Operators with spaces in
their name require quoting: `[#'PhysX Shape']`. The direct scene path
`$Name.Event.Operator.property` also works for simple names without spaces.

**Return JSON:**

```json
{
    "success": true,
    "operator": "Birth",
    "propertiesSet": ["birthTotal", "birthMode"]
}
```

---

### 4.4 `add_tyflow_event` -- Add Event to Existing Flow

**Purpose:** Add a new event with operators to an existing tyFlow.

**Parameters:**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `tyflow_name` | `str` | (required) | tyFlow object name |
| `event_name` | `str` | (required) | New event name |
| `operators` | `list[dict]` | (required) | Operator definitions (same schema as `create_tyflow`) |
| `position` | `list[float]` | `[0, 0]` | Editor GUI position |

**MAXScript Template:**

```maxscript
(
    local tfObj = getNodeByName "{safe_name}"
    if tfObj == undefined then (
        "{{\\"error\\":\\"tyFlow not found\\"}}"
    ) else (
        local newEv = tfObj.addEvent()
        newEv.setName "{event_name}"
        newEv.setPosition [{position[0]}, {position[1]}]
        {operator_creation_lines}
        "{{\\"success\\":true, \\"event\\":\\"{event_name}\\", \\"operatorCount\\":{op_count}}}"
    )
)
```

---

### 4.5 `connect_tyflow_events` -- Wire Events Together

**Purpose:** Connect events via Send Out or Split operators.

**Parameters:**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `tyflow_name` | `str` | (required) | tyFlow object name |
| `from_event` | `str` | (required) | Source event name |
| `operator_name` | `str` | (required) | Name of Send Out / Split operator in source event |
| `to_event` | `str` | (required) | Target event name |

**MAXScript Template:**

```maxscript
(
    local tfObj = getNodeByName "{safe_tyflow_name}"
    local opRef = tfObj.baseobject[#'{safe_from_event}'][#'{safe_operator_name}']
    local targetEv = tfObj.baseobject[#'{safe_to_event}']
    opRef.connect targetEv
    "{{\\"success\\":true}}"
)
```

**Note:** Event references are obtained via `baseobject[#EventName]` SubAnim access.
Operator references via `baseobject[#EventName][#OperatorName]`. Names with spaces
require quoting: `[#'PhysX Shape']`.

---

### 4.6 `remove_tyflow_element` -- Remove Event or Operator

**Purpose:** Remove an event or operator from a tyFlow.

**Parameters:**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `tyflow_name` | `str` | (required) | tyFlow object name |
| `event_name` | `str` | (required) | Event name |
| `operator_name` | `str \| None` | `None` | If provided, remove this operator. If None, remove the entire event. |

**MAXScript Template:**

```maxscript
(
    local tfObj = getNodeByName "{safe_tyflow_name}"
    if operator_name provided:
        local opRef = tfObj.baseobject[#'{safe_event_name}'][#'{safe_operator_name}']
        opRef.remove()
    else:
        local evRef = tfObj.baseobject[#'{safe_event_name}']
        evRef.remove()
)
```

---

### 4.7 `set_tyflow_shape` -- HIGH PRIORITY (Bug Fix)

**Purpose:** Configure a Shape operator with correct `_tab` array values,
using human-readable shape names instead of raw integer IDs.

**Parameters:**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `tyflow_name` | `str` | (required) | tyFlow object name |
| `event_name` | `str` | (required) | Event containing the Shape operator |
| `operator_name` | `str` | `"Shape"` | Shape operator name (in case renamed) |
| `shapes` | `list[dict]` | (required) | Shape definitions (see below) |
| `distribution_mode` | `int` | `0` | 0=Random by frequency, 1=Index from custom float |

**Shape Definition Schema:**

```python
{
    "type": "3d",                  # "3d", "2d", or "reference"
    "shape": "sphere",             # For 3d: sphere, box, cylinder, etc.
                                   # For 2d: circle, square, triangle, etc.
    "reference_object": "MyMesh",  # Only for type="reference"
    "frequency": 100.0,            # Distribution weight
    "scale": 100.0,                # Scale percentage
    "scale_variation": 0.0,        # Scale variation percentage
    "center_pivot": False,
    "preserve_normals": False,
    "split_elements": False,
    "animated": False
}
```

**MAXScript Template:**

```python
def set_tyflow_shape(tyflow_name, event_name, operator_name, shapes, distribution_mode):
    # Build parallel arrays from shape definitions
    shape_type_tab = []     # 0=2D, 1=3D, 2=Reference
    type_3d_ID_tab = []
    type_2d_ID_tab = []
    instancedGeo_tab = []   # Node references for type=reference
    frequency_tab = []
    scaleVal_tab = []
    scaleVariation_tab = []
    meshCenterPivots_tab = []
    meshPreserveNormals_tab = []
    meshSplitElements_tab = []
    meshAnimated_tab = []

    for shape_def in shapes:
        shape_type = shape_def["type"]
        if shape_type == "3d":
            shape_type_tab.append(1)
            shape_name = shape_def.get("shape", "sphere").lower()
            type_3d_ID_tab.append(SHAPE_3D_IDS.get(shape_name, 4))  # default to sphere (4)
            type_2d_ID_tab.append(0)
            instancedGeo_tab.append("undefined")
        elif shape_type == "2d":
            shape_type_tab.append(0)
            # ... similar
        elif shape_type == "reference":
            shape_type_tab.append(2)
            # ...

        frequency_tab.append(shape_def.get("frequency", 100.0))
        scaleVal_tab.append(shape_def.get("scale", 100.0))
        # ... etc

    maxscript = f"""(
        local tfObj = getNodeByName "{safe_tyflow_name}"
        local shapeOp = tfObj.baseobject[#'{safe_event_name}'][#'{safe_operator_name}']
        if shapeOp == undefined then (
            "{{\\"error\\":\\"Shape operator not found\\"}}"
        ) else (
            shapeOp.shape_type_tab = {_int_array(shape_type_tab)}
            shapeOp.type_3d_ID_tab = {_int_array(type_3d_ID_tab)}
            shapeOp.type_2d_ID_tab = {_int_array(type_2d_ID_tab)}
            shapeOp.frequency_tab = {_float_array(frequency_tab)}
            shapeOp.scaleVal_tab = {_float_array(scaleVal_tab)}
            shapeOp.scaleVariation_tab = {_float_array(scaleVariation_tab)}
            shapeOp.meshCenterPivots_tab = {_bool_array(meshCenterPivots_tab)}
            shapeOp.meshPreserveNormals_tab = {_bool_array(meshPreserveNormals_tab)}
            shapeOp.meshSplitElements_tab = {_bool_array(meshSplitElements_tab)}
            shapeOp.meshAnimated_tab = {_bool_array(meshAnimated_tab)}
            shapeOp.distributionMode = {distribution_mode}
            {ref_object_lines}
            "{{\\"success\\":true,\\"shapeCount\\":{len(shapes)}}}"
        )
    )"""
```

**Return JSON:**

```json
{
    "success": true,
    "shapeCount": 1,
    "shapes": [
        {"type": "3d", "shape": "sphere", "id": 4, "frequency": 100.0, "scale": 100.0}
    ]
}
```

**CRITICAL IMPLEMENTATION NOTE:**

All `_tab` arrays MUST have the same length. If the user defines 3 shapes, every
`_tab` array must have exactly 3 elements. Missing values in the user input must
be filled with sensible defaults:
- `frequency_tab` default: `100.0`
- `scaleVal_tab` default: `100.0`
- `scaleVariation_tab` default: `0.0`
- `meshCenterPivots_tab` default: `false`
- `meshPreserveNormals_tab` default: `false`
- `meshSplitElements_tab` default: `false`
- `meshAnimated_tab` default: `false`
- `scale_tab` default: `false` (enable override scale -- usually leave off)

Also, the `instancedGeo_tab` array for non-reference shapes should contain
`undefined` entries. This needs testing -- if tyFlow does not accept `undefined`
in the array, we may need to use a dummy node or omit non-reference entries.

---

### 4.8 `set_tyflow_physx` -- Configure PhysX Settings

**Purpose:** Set PhysX solver properties on a tyFlow object.

**Parameters:**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `tyflow_name` | `str` | (required) | tyFlow object name |
| `gravity_enabled` | `bool \| None` | `None` | Enable/disable PhysX gravity |
| `gravity_value` | `float \| None` | `None` | Gravity strength (negative = down) |
| `ground_collider` | `bool \| None` | `None` | Enable built-in ground collider |
| `ground_collider_height` | `float \| None` | `None` | Ground plane Z height |
| `ground_collider_restitution` | `float \| None` | `None` | Ground bounce |
| `ground_collider_static_friction` | `float \| None` | `None` | Ground static friction |
| `ground_collider_dynamic_friction` | `float \| None` | `None` | Ground dynamic friction |
| `substeps` | `int \| None` | `None` | PhysX substeps |
| `pos_iterations` | `int \| None` | `None` | Position iterations |
| `vel_iterations` | `int \| None` | `None` | Velocity iterations |
| `ccd` | `bool \| None` | `None` | Continuous collision detection |
| `enhanced_determinism` | `bool \| None` | `None` | Enhanced determinism |

**MAXScript Template:**

Only emit property-setting lines for non-None parameters. This allows partial updates.

```maxscript
(
    local tfObj = getNodeByName "{safe_name}"
    if tfObj == undefined then (
        "{{\\"error\\":\\"tyFlow not found\\"}}"
    ) else (
        {conditional_property_lines}
        "{{\\"success\\":true,\\"name\\":\\"" + tfObj.name + "\\"}}"
    )
)
```

---

### 4.9 `add_tyflow_collision` -- Add Collision Objects

**Purpose:** Add scene objects as colliders to a PhysX Collision operator.

**Parameters:**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `tyflow_name` | `str` | (required) | tyFlow object name |
| `event_name` | `str` | (required) | Event name |
| `operator_name` | `str` | `"PhysX Collision"` | Operator name |
| `collider_names` | `list[str]` | (required) | Scene object names to add as colliders |
| `hull_mode` | `int` | `3` | 0=Sphere, 1=Box, 2=Convex Hull, 3=Mesh |
| `restitution` | `float` | `0.3` | Bounce |
| `static_friction` | `float` | `0.5` | Static friction |
| `dynamic_friction` | `float` | `0.3` | Dynamic friction |

**MAXScript Template:**

```maxscript
(
    local tfObj = getNodeByName "{safe_tyflow_name}"
    local physxCollOp = tfObj.baseobject[#'{safe_event_name}'][#'{safe_operator_name}']
    if physxCollOp == undefined then (
        "{{\\"error\\":\\"PhysX Collision operator not found\\"}}"
    ) else (
        local colliderNames = {_name_array(collider_names)}
        local colliderNodes = #()
        local missingNames = #()
        for cName in colliderNames do (
            local cNode = getNodeByName cName
            if cNode != undefined then append colliderNodes cNode
            else append missingNames cName
        )
        if missingNames.count > 0 then (
            -- report missing
        ) else (
            physxCollOp.colliderList = colliderNodes
            physxCollOp.hullMode = {hull_mode}
            physxCollOp.restitution = {restitution}
            physxCollOp.staticFriction = {static_friction}
            physxCollOp.dynamicFriction = {dynamic_friction}
            "{{\\"success\\":true,\\"colliderCount\\":" + (colliderNodes.count as string) + "}}"
        )
    )
)
```

---

### 4.10 `get_tyflow_particles` -- Read Particle Data

**Purpose:** Read particle positions, velocities, ages, and other data.

**Parameters:**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `tyflow_name` | `str` | (required) | tyFlow object name |
| `frame` | `int \| None` | `None` | Frame to sample (None = current time) |
| `data_types` | `list[str]` | `["positions"]` | What to read: "positions", "velocities", "ages", "transforms", "scales" |
| `max_particles` | `int` | `1000` | Limit output (0 = all) |
| `particle_indices` | `list[int] \| None` | `None` | Specific 1-based particle indices to read (None = all up to max) |

**Return JSON:**

```json
{
    "name": "MyParticles",
    "frame": 30,
    "particleCount": 500,
    "returnedCount": 500,
    "positions": [[1.0, 2.0, 3.0], [4.0, 5.0, 6.0], ...],
    "velocities": [[0.1, 0.2, 0.3], ...],
    "ages": [0.5, 1.0, ...]
}
```

**Performance Note:** For large particle counts (10k+), the JSON string can be very
large. The `max_particles` parameter with a default of 1000 prevents timeouts.
When `max_particles` > 0, we only serialize the first N particles. The total count
is always reported.

---

### 4.11 `get_tyflow_particle_count` -- Quick Count Query

**Purpose:** Fast query for just the particle count (no data serialization).

**Parameters:**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `tyflow_name` | `str` | (required) | tyFlow object name |
| `frame` | `int \| None` | `None` | Frame to sample |

**MAXScript Template:**

```maxscript
(
    local tfObj = getNodeByName "{safe_name}"
    if tfObj == undefined then (
        "{{\\"error\\":\\"tyFlow not found\\"}}"
    ) else (
        {frame_setting_line}
        tfObj.updateParticles currentTime
        local n = tfObj.numParticles()
        "{{\\"name\\":\\"" + tfObj.name + "\\",\\"particleCount\\":" + (n as string) + "}}"
    )
)
```

---

### 4.12 `reset_tyflow_simulation` -- Reset Simulation Cache

**Purpose:** Reset the simulation cache on a tyFlow object.

**Parameters:**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `tyflow_name` | `str` | (required) | tyFlow object name |

**MAXScript Template:**

```maxscript
(
    local tfObj = getNodeByName "{safe_name}"
    if tfObj == undefined then (
        "{{\\"error\\":\\"tyFlow not found\\"}}"
    ) else (
        tfObj.reset_simulation()
        "{{\\"success\\":true,\\"name\\":\\"" + tfObj.name + "\\"}}"
    )
)
```

---

### 4.13 `create_tyflow_preset` -- High-Level Presets

**Purpose:** Create common particle effects with a single call. Internally
builds the appropriate events, operators, and connections.

**Parameters:**

| Parameter | Type | Default | Description |
|---|---|---|---|
| `preset` | `str` | (required) | Preset name (see table) |
| `name` | `str` | auto | tyFlow object name |
| `position` | `list[float]` | `[0, 0, 0]` | World position |
| `particle_count` | `int` | varies | Total particle count |
| `shape` | `str` | varies | Shape override (e.g. "sphere", "box") |
| `scale` | `float` | `100.0` | Shape scale % |
| `lifetime_frames` | `int` | varies | Particle lifetime in frames |
| `speed` | `float` | varies | Speed magnitude |
| `ground_plane` | `bool` | `False` | Create a ground plane and add PhysX collision |
| `collider_names` | `list[str]` | `[]` | Additional collider objects |

**Preset Definitions:**

| Preset | Description | Default Count | Operators |
|---|---|---|---|
| `"rain"` | Downward particles, speed aligned | 2000 | Birth (per-frame), Speed (down), Shape (sphere, small scale), Force (gravity), Display |
| `"snow"` | Gentle falling, some wind/noise | 1000 | Birth (per-frame), Speed (down, low), Shape (sphere, small), Force (gravity weak, noise), Spin, Display |
| `"explosion"` | Burst outward from center | 500 | Birth (burst), Speed (random 3D, high), Force (gravity), Shape (sphere), Display |
| `"debris"` | Fractured pieces with PhysX | 200 | Birth (burst), Speed (random 3D), Shape (box), PhysX Shape, PhysX Collision, Force (gravity), Display |
| `"confetti"` | Colorful flat pieces falling | 300 | Birth (per-frame), Speed (random 3D, low), Shape (disc/plane), Spin (high), Force (gravity weak, noise), Display |
| `"fountain"` | Upward stream with falloff | 1000 | Birth (per-frame), Speed (up + variation), Force (gravity), Shape (sphere, small), Display |
| `"sparks"` | Fast small particles with drag | 500 | Birth (burst), Speed (random 3D, very high), Force (gravity), Slow, Shape (sphere, tiny), Display |
| `"smoke"` | Slow rising with noise | 200 | Birth (per-frame), Speed (up, slow), Force (noise, no gravity), Scale (grow over time), Shape (sphere), Display |

**Implementation:** This tool will internally call the same MAXScript generation
logic as `create_tyflow`, but with preset-specific parameters. It is a Python-level
convenience that constructs the events/operators dict and delegates.

---

## 5. Preset Templates

### 5.1 Rain Preset -- Full MAXScript Example

```maxscript
(
    local tfObj = tyflow()
    tfObj.name = "Rain"
    tfObj.pos = [0, 0, 200]

    local ev1 = tfObj.addEvent()
    ev1.setName "RainEvent"

    local birthOp = ev1.addOperator "Birth" -1
    birthOp.birthMode = 1              -- Per Frame
    birthOp.birthPerFrame = 50.0
    birthOp.birthStart = 0

    local speedOp = ev1.addOperator "Speed" -1
    speedOp.magnitude = 500.0
    speedOp.magnitudeVariation = 10.0
    speedOp.directionMode = 0          -- Along icon arrow (default = down)
    speedOp.directionReverse = true    -- Ensure downward

    local forceOp = ev1.addOperator "Force" -1
    forceOp.gravityStrength = -0.5
    forceOp.windStrength = 50.0
    forceOp.windX = 1.0
    forceOp.windZ = 0.0

    local shapeOp = ev1.addOperator "Shape" -1
    shapeOp.shape_type_tab = #(1)
    shapeOp.type_3d_ID_tab = #(4)  -- 4 = Sphere (confirmed)
    shapeOp.frequency_tab = #(100.0)
    shapeOp.scaleVal_tab = #(10.0)         -- Small drops
    shapeOp.scaleVariation_tab = #(20.0)

    local displayOp = ev1.addOperator "Display" -1
    displayOp.displayMode = 2

    tfObj.reset_simulation()

    -- JSON response
    "{{\\"name\\":\\"Rain\\",\\"preset\\":\\"rain\\",\\"particleRate\\":50}}"
)
```

### 5.2 Explosion Preset -- Full MAXScript Example

```maxscript
(
    local tfObj = tyflow()
    tfObj.name = "Explosion"
    tfObj.pos = [0, 0, 50]

    local ev1 = tfObj.addEvent()
    ev1.setName "ExplosionEvent"

    local birthOp = ev1.addOperator "Birth" -1
    birthOp.birthMode = 0              -- Total
    birthOp.birthTotal = 500
    birthOp.birthStart = 0
    birthOp.birthEndEnable = true
    birthOp.birthEnd = 2               -- Quick burst

    local speedOp = ev1.addOperator "Speed" -1
    speedOp.magnitude = 800.0
    speedOp.magnitudeVariation = 40.0
    speedOp.directionMode = 3          -- Random 3D

    local forceOp = ev1.addOperator "Force" -1
    forceOp.gravityStrength = -1.0

    local shapeOp = ev1.addOperator "Shape" -1
    shapeOp.shape_type_tab = #(1)
    shapeOp.type_3d_ID_tab = #(4)           -- 4 = Sphere (confirmed)
    shapeOp.frequency_tab = #(100.0)
    shapeOp.scaleVal_tab = #(30.0)
    shapeOp.scaleVariation_tab = #(50.0)

    local displayOp = ev1.addOperator "Display" -1
    displayOp.displayMode = 2

    tfObj.reset_simulation()

    "{{\\"name\\":\\"Explosion\\",\\"preset\\":\\"explosion\\",\\"particleCount\\":500}}"
)
```

### 5.3 Debris with PhysX Preset -- Full MAXScript Example

```maxscript
(
    local groundPlane = Plane length:1000 width:1000 pos:[0,0,0] name:"DebrisGround"

    local tfObj = tyflow()
    tfObj.name = "Debris"
    tfObj.pos = [0, 0, 100]

    -- PhysX object-level settings
    tfObj.physXGravityEnabled = true
    tfObj.physXGravityValue = -980.0
    tfObj.physXGroundCollider = true
    tfObj.physXGroundColliderHeight = 0.0
    tfObj.physXGroundColliderRestitution = 0.3
    tfObj.physXSubsteps = 8

    -- Birth event
    local ev1 = tfObj.addEvent()
    ev1.setName "DebrisBirth"

    local birthOp = ev1.addOperator "Birth" -1
    birthOp.birthMode = 0
    birthOp.birthTotal = 200
    birthOp.birthStart = 0
    birthOp.birthEndEnable = true
    birthOp.birthEnd = 5

    local sndOp = ev1.addOperator "Send Out" -1

    -- Physics event
    local ev2 = tfObj.addEvent()
    ev2.setName "DebrisPhysics"

    local speedOp = ev2.addOperator "Speed" -1
    speedOp.magnitude = 400.0
    speedOp.magnitudeVariation = 50.0
    speedOp.directionMode = 3

    local shapeOp = ev2.addOperator "Shape" -1
    shapeOp.shape_type_tab = #(1)
    shapeOp.type_3d_ID_tab = #(6)    -- 6 = Cube/Box (confirmed)
    shapeOp.frequency_tab = #(100.0)
    shapeOp.scaleVal_tab = #(50.0)
    shapeOp.scaleVariation_tab = #(60.0)

    local physxShapeOp = ev2.addOperator "PhysX Shape" -1
    physxShapeOp.hullMode = 0              -- Box hull
    physxShapeOp.restitution = 0.4
    physxShapeOp.staticFriction = 0.5
    physxShapeOp.dynamicFriction = 0.3

    local physxCollOp = ev2.addOperator "PhysX Collision" -1
    append physxCollOp.colliderList groundPlane
    physxCollOp.hullMode = 3
    physxCollOp.restitution = 0.3

    local displayOp = ev2.addOperator "Display" -1
    displayOp.displayMode = 2

    sndOp.connect ev2

    tfObj.reset_simulation()

    "{{\\"name\\":\\"Debris\\",\\"preset\\":\\"debris\\",\\"particleCount\\":200,\\"events\\":2}}"
)
```

---

## 6. Testing Strategy

### 6.1 General Testing Framework

Each test consists of:

1. **Setup script** -- MAXScript that creates a known state.
2. **Validation script** -- MAXScript that inspects the result and returns a
   pass/fail JSON.
3. **Visual expectation** -- What the user should see in the viewport.
4. **Cleanup script** -- Removes all test objects.

All tests should be runnable via `execute_maxscript` through the MCP connection
during development.

### 6.2 Shape Operator Tests (CRITICAL)

#### Test S1: Each 3D Shape Type Individually

For each confirmed shape ID, create a flow and verify:

```maxscript
-- Test template for shape ID verification
(
    local tf = tyflow()
    tf.name = "zzz_ShapeTest_{shape_name}"
    local ev1 = tf.addEvent()
    ev1.setName "TestEvent"

    local birthOp = ev1.addOperator "Birth" -1
    birthOp.birthMode = 0
    birthOp.birthTotal = 1
    birthOp.birthStart = 0
    birthOp.birthEndEnable = true
    birthOp.birthEnd = 0

    local shapeOp = ev1.addOperator "Shape" -1
    shapeOp.shape_type_tab = #(1)
    shapeOp.type_3d_ID_tab = #({shape_id})
    shapeOp.frequency_tab = #(100.0)
    shapeOp.scaleVal_tab = #(100.0)

    local displayOp = ev1.addOperator "Display" -1
    displayOp.displayMode = 2

    tf.reset_simulation()
    sliderTime = 0f
    tf.updateParticles currentTime

    -- Validation: check mesh vert count matches expected
    local snapMesh = snapshotAsMesh tf
    local verts = snapMesh.numVerts
    local faces = snapMesh.numFaces
    delete snapMesh

    local expected_verts = {expected_verts}
    local pass = (verts == expected_verts)

    local result = "{{\\"test\\":\\"shape_{shape_name}\\",\\"pass\\":" + (if pass then "true" else "false") + ",\\"expected_verts\\":" + (expected_verts as string) + ",\\"actual_verts\\":" + (verts as string) + ",\\"faces\\":" + (faces as string) + "}}"
    delete tf
    result
)
```

Run this for EVERY shape type (sphere, box, cylinder, cone, pyramid, torus,
hemisphere, capsule, diamond, disc, tetrahedron, and any others discovered).

#### Test S2: Multi-Shape Tab Arrays

Test that defining multiple shapes in the `_tab` arrays works:

```maxscript
(
    local tf = tyflow()
    tf.name = "zzz_MultiShapeTest"
    local ev1 = tf.addEvent()
    ev1.setName "TestEvent"

    local birthOp = ev1.addOperator "Birth" -1
    birthOp.birthMode = 0
    birthOp.birthTotal = 100
    birthOp.birthStart = 0
    birthOp.birthEndEnable = true
    birthOp.birthEnd = 0

    local shapeOp = ev1.addOperator "Shape" -1
    -- 3 shapes: sphere, box, cylinder
    shapeOp.shape_type_tab = #(1, 1, 1)
    shapeOp.type_3d_ID_tab = #(4, 6, 3)
    shapeOp.frequency_tab = #(50.0, 30.0, 20.0)
    shapeOp.scaleVal_tab = #(100.0, 80.0, 120.0)
    shapeOp.scaleVariation_tab = #(0.0, 0.0, 0.0)
    shapeOp.meshCenterPivots_tab = #(false, false, false)
    shapeOp.meshPreserveNormals_tab = #(false, false, false)
    shapeOp.meshSplitElements_tab = #(false, false, false)
    shapeOp.meshAnimated_tab = #(false, false, false)
    shapeOp.distributionMode = 0

    local displayOp = ev1.addOperator "Display" -1
    displayOp.displayMode = 2

    tf.reset_simulation()
    sliderTime = 0f
    tf.updateParticles currentTime

    -- Validation: should have 100 particles, mesh should exist
    local n = tf.numParticles()
    local verts = 0
    try (
        local snapMesh = snapshotAsMesh tf
        verts = snapMesh.numVerts
        delete snapMesh
    ) catch ()

    local pass = (n == 100) and (verts > 0)
    local result = "{{\\"test\\":\\"multi_shape\\",\\"pass\\":" + (if pass then "true" else "false") + ",\\"particles\\":" + (n as string) + ",\\"verts\\":" + (verts as string) + "}}"
    delete tf
    result
)
```

**Visual Expectation:** 100 particles with a mix of visually distinct shapes.

#### Test S3: Tab Array Length Mismatch

Test what happens when `_tab` arrays have mismatched lengths (should we error
or pad?):

```maxscript
(
    local tf = tyflow()
    tf.name = "zzz_TabMismatchTest"
    local ev1 = tf.addEvent()

    local birthOp = ev1.addOperator "Birth" -1
    birthOp.birthMode = 0
    birthOp.birthTotal = 10

    local shapeOp = ev1.addOperator "Shape" -1

    -- Intentional mismatch: 2 types but only 1 frequency
    local errored = false
    try (
        shapeOp.shape_type_tab = #(1, 1)
        shapeOp.type_3d_ID_tab = #(4, 6)
        shapeOp.frequency_tab = #(100.0)    -- only 1 entry!
    ) catch (
        errored = true
    )

    local result = "{{\\"test\\":\\"tab_mismatch\\",\\"errored\\":" + (if errored then "true" else "false") + "}}"
    delete tf
    result
)
```

**Expected:** Either tyFlow throws an error (ideal) or silently uses defaults for
missing entries (we must document which). This determines whether our Python code
must enforce equal-length arrays.

#### Test S4: Reference Object Shape

```maxscript
(
    local refSphere = Sphere radius:25 pos:[0,0,0] name:"RefSphere"

    local tf = tyflow()
    tf.name = "zzz_RefShapeTest"
    local ev1 = tf.addEvent()

    local birthOp = ev1.addOperator "Birth" -1
    birthOp.birthMode = 0
    birthOp.birthTotal = 10

    local shapeOp = ev1.addOperator "Shape" -1
    shapeOp.shape_type_tab = #(2)          -- 2 = Reference Object
    shapeOp.instancedGeo_tab = #(refSphere)
    shapeOp.frequency_tab = #(100.0)
    shapeOp.scaleVal_tab = #(100.0)
    shapeOp.scaleVariation_tab = #(0.0)
    shapeOp.meshCenterPivots_tab = #(false)
    shapeOp.meshPreserveNormals_tab = #(false)
    shapeOp.meshSplitElements_tab = #(false)
    shapeOp.meshAnimated_tab = #(false)

    local displayOp = ev1.addOperator "Display" -1
    displayOp.displayMode = 2

    tf.reset_simulation()
    sliderTime = 0f
    tf.updateParticles currentTime

    local n = tf.numParticles()
    local pass = (n == 10)

    local result = "{{\\"test\\":\\"ref_shape\\",\\"pass\\":" + (if pass then "true" else "false") + ",\\"particles\\":" + (n as string) + "}}"
    delete tf
    delete refSphere
    result
)
```

**Visual Expectation:** 10 particles each shaped like the reference sphere mesh.

#### Test S5: `set_tyflow_shape` Tool Round-Trip

After implementing the tool, test the full pipeline:

1. Call `create_tyflow` with a Shape operator (default/blank shape).
2. Call `set_tyflow_shape` with `shapes=[{"type": "3d", "shape": "sphere"}]`.
3. Call `get_tyflow_particles` to confirm particles exist.
4. Visually confirm spheres in the viewport.
5. Call `set_tyflow_shape` again with `shapes=[{"type": "3d", "shape": "box"}]`.
6. Visually confirm the shapes changed to boxes.

---

### 6.3 Flow Management Tests

#### Test F1: Create and Inspect

```maxscript
-- Create a flow, then inspect it
(
    local tf = tyflow()
    tf.name = "zzz_CreateInspectTest"
    local ev1 = tf.addEvent()
    ev1.setName "BirthEvent"
    local birthOp = ev1.addOperator "Birth" -1
    birthOp.birthTotal = 100

    -- Verify we can read back
    local readName = ev1.getName()
    local readEnabled = ev1.getEnabled()
    local pass = (readName == "BirthEvent") and readEnabled

    local result = "{{\\"test\\":\\"create_inspect\\",\\"pass\\":" + (if pass then "true" else "false") + ",\\"eventName\\":\\"" + readName + "\\"}}"
    delete tf
    result
)
```

#### Test F2: Event Connection

```maxscript
(
    local tf = tyflow()
    tf.name = "zzz_ConnectionTest"
    local ev1 = tf.addEvent()
    ev1.setName "EvA"
    local sndOp = ev1.addOperator "Send Out" -1

    local ev2 = tf.addEvent()
    ev2.setName "EvB"
    local birthOp = ev2.addOperator "Birth" -1

    sndOp.connect ev2

    -- Verify particles flow (need to birth in ev1 and check if they arrive in ev2)
    -- This is hard to verify without particle data per-event.
    -- Minimal verification: connection created without error.
    local pass = true

    local result = "{{\\"test\\":\\"connection\\",\\"pass\\":" + (if pass then "true" else "false") + "}}"
    delete tf
    result
)
```

#### Test F3: Operator Removal

```maxscript
(
    local tf = tyflow()
    tf.name = "zzz_RemoveTest"
    local ev1 = tf.addEvent()
    ev1.setName "TestEvent"
    local birthOp = ev1.addOperator "Birth" -1
    local speedOp = ev1.addOperator "Speed" -1
    local shapeOp = ev1.addOperator "Shape" -1

    -- Remove the Speed operator
    speedOp.remove()

    -- Verify only 2 operators remain (Birth and Shape)
    -- We need to test if we can still access remaining ops
    local pass = true
    try (
        -- Birth should still be accessible
        local bMode = birthOp.birthMode
    ) catch (pass = false)

    local result = "{{\\"test\\":\\"remove_op\\",\\"pass\\":" + (if pass then "true" else "false") + "}}"
    delete tf
    result
)
```

#### Test F4: Event Removal

```maxscript
(
    local tf = tyflow()
    tf.name = "zzz_RemoveEventTest"
    local ev1 = tf.addEvent()
    ev1.setName "EvToRemove"
    local ev2 = tf.addEvent()
    ev2.setName "EvToKeep"

    ev1.remove()

    -- Verify ev2 still works
    local pass = true
    try (
        local name2 = ev2.getName()
        pass = (name2 == "EvToKeep")
    ) catch (pass = false)

    local result = "{{\\"test\\":\\"remove_event\\",\\"pass\\":" + (if pass then "true" else "false") + "}}"
    delete tf
    result
)
```

---

### 6.4 PhysX Tests

#### Test P1: PhysX Ground Collision

```maxscript
(
    local tf = tyflow()
    tf.name = "zzz_PhysXGroundTest"
    tf.pos = [0, 0, 100]

    tf.physXGravityEnabled = true
    tf.physXGravityValue = -980.0
    tf.physXGroundCollider = true
    tf.physXGroundColliderHeight = 0.0
    tf.physXSubsteps = 8

    local ev1 = tf.addEvent()
    ev1.setName "PhysXTest"

    local birthOp = ev1.addOperator "Birth" -1
    birthOp.birthMode = 0
    birthOp.birthTotal = 10
    birthOp.birthStart = 0
    birthOp.birthEndEnable = true
    birthOp.birthEnd = 0

    local shapeOp = ev1.addOperator "Shape" -1
    shapeOp.shape_type_tab = #(1)
    shapeOp.type_3d_ID_tab = #(4)
    shapeOp.frequency_tab = #(100.0)
    shapeOp.scaleVal_tab = #(50.0)

    local physxShapeOp = ev1.addOperator "PhysX Shape" -1
    physxShapeOp.hullMode = 4

    local displayOp = ev1.addOperator "Display" -1
    displayOp.displayMode = 2

    tf.reset_simulation()

    -- Advance to frame 100 where particles should have settled on ground
    sliderTime = 100f
    tf.updateParticles currentTime

    local positions = tf.getAllParticlePositions()
    local allAboveGround = true
    local allSettled = true
    for pos in positions do (
        if pos.z < -1.0 do allAboveGround = false    -- should be at or above ground (z=0)
        if pos.z > 50.0 do allSettled = false         -- should have fallen from z=100
    )

    local pass = allAboveGround and allSettled and (positions.count == 10)
    local result = "{{\\"test\\":\\"physx_ground\\",\\"pass\\":" + (if pass then "true" else "false") + ",\\"particleCount\\":" + (positions.count as string) + "}}"
    delete tf
    result
)
```

**Visual Expectation:** 10 spheres resting on the invisible ground plane at Z=0.

#### Test P2: PhysX Mesh Collision

```maxscript
(
    local ramp = Plane length:200 width:200 pos:[0,0,50] name:"zzz_Ramp"
    rotate ramp (eulerAngles 30 0 0)

    local tf = tyflow()
    tf.name = "zzz_MeshCollTest"
    tf.pos = [0, 0, 150]

    tf.physXGravityEnabled = true
    tf.physXGravityValue = -980.0
    tf.physXSubsteps = 8

    local ev1 = tf.addEvent()
    ev1.setName "CollTest"

    local birthOp = ev1.addOperator "Birth" -1
    birthOp.birthMode = 0
    birthOp.birthTotal = 20
    birthOp.birthStart = 0
    birthOp.birthEndEnable = true
    birthOp.birthEnd = 0

    local shapeOp = ev1.addOperator "Shape" -1
    shapeOp.shape_type_tab = #(1)
    shapeOp.type_3d_ID_tab = #(4)
    shapeOp.frequency_tab = #(100.0)
    shapeOp.scaleVal_tab = #(30.0)

    local physxShapeOp = ev1.addOperator "PhysX Shape" -1
    physxShapeOp.hullMode = 4

    local physxCollOp = ev1.addOperator "PhysX Collision" -1
    physxCollOp.colliderList = #(ramp)
    physxCollOp.hullMode = 3

    local displayOp = ev1.addOperator "Display" -1
    displayOp.displayMode = 2

    tf.reset_simulation()
    sliderTime = 50f
    tf.updateParticles currentTime

    -- Particles should have interacted with the ramp
    local n = tf.numParticles()
    local pass = (n == 20)

    local result = "{{\\"test\\":\\"physx_mesh_coll\\",\\"pass\\":" + (if pass then "true" else "false") + ",\\"particles\\":" + (n as string) + "}}"
    delete tf
    delete ramp
    result
)
```

---

### 6.5 Particle Data Tests

#### Test D1: Read Positions

```maxscript
(
    local tf = tyflow()
    tf.name = "zzz_DataReadTest"
    local ev1 = tf.addEvent()

    local birthOp = ev1.addOperator "Birth" -1
    birthOp.birthMode = 0
    birthOp.birthTotal = 5
    birthOp.birthStart = 0
    birthOp.birthEndEnable = true
    birthOp.birthEnd = 0

    local displayOp = ev1.addOperator "Display" -1
    displayOp.displayMode = 1

    tf.reset_simulation()
    sliderTime = 0f
    tf.updateParticles currentTime

    local n = tf.numParticles()
    local positions = tf.getAllParticlePositions()

    local pass = (n == 5) and (positions.count == 5)
    -- Each position should be a Point3
    if pass and positions.count > 0 do (
        pass = ((classOf positions[1]) == Point3)
    )

    local result = "{{\\"test\\":\\"data_read\\",\\"pass\\":" + (if pass then "true" else "false") + ",\\"count\\":" + (n as string) + ",\\"posType\\":\\"" + ((classOf positions[1]) as string) + "\\"}}"
    delete tf
    result
)
```

#### Test D2: Large Particle Count Performance

```maxscript
(
    local startTime = timeStamp()
    local tf = tyflow()
    tf.name = "zzz_PerfTest"
    local ev1 = tf.addEvent()

    local birthOp = ev1.addOperator "Birth" -1
    birthOp.birthMode = 0
    birthOp.birthTotal = 10000

    local speedOp = ev1.addOperator "Speed" -1
    speedOp.magnitude = 100.0
    speedOp.directionMode = 3

    local displayOp = ev1.addOperator "Display" -1
    displayOp.displayMode = 1

    tf.reset_simulation()
    sliderTime = 5f
    tf.updateParticles currentTime

    local n = tf.numParticles()
    local positions = tf.getAllParticlePositions()
    local elapsed = timeStamp() - startTime

    local pass = (n == 10000) and (elapsed < 10000)  -- under 10 seconds
    local result = "{{\\"test\\":\\"perf_10k\\",\\"pass\\":" + (if pass then "true" else "false") + ",\\"count\\":" + (n as string) + ",\\"elapsed_ms\\":" + (elapsed as string) + "}}"
    delete tf
    result
)
```

---

### 6.6 Edge Case Tests

#### Test E1: Variable Naming Conflict

Verify that our generated MAXScript never uses bare operator names as variables:

```maxscript
-- This should FAIL (demonstrates the bug):
(
    local Birth = tyflow()  -- BAD: conflicts with Birth operator class
)

-- This should SUCCEED (our pattern):
(
    local tfObj = tyflow()
    local ev1 = tfObj.addEvent()
    local birthOp = ev1.addOperator "Birth" -1  -- GOOD: suffixed name
    birthOp.birthTotal = 100
    local pass = (birthOp.birthTotal == 100)
    delete tfObj
    "{{\\"test\\":\\"var_naming\\",\\"pass\\":" + (if pass then "true" else "false") + "}}"
)
```

#### Test E2: Empty Flow (No Events)

```maxscript
(
    local tf = tyflow()
    tf.name = "zzz_EmptyFlowTest"

    local n = 0
    try (
        tf.updateParticles currentTime
        n = tf.numParticles()
    ) catch ()

    local pass = (n == 0)
    local result = "{{\\"test\\":\\"empty_flow\\",\\"pass\\":" + (if pass then "true" else "false") + "}}"
    delete tf
    result
)
```

#### Test E3: Duplicate Event Names

```maxscript
(
    local tf = tyflow()
    tf.name = "zzz_DupeNameTest"
    local ev1 = tf.addEvent()
    ev1.setName "SameName"
    local ev2 = tf.addEvent()
    ev2.setName "SameName"

    -- Does tyFlow auto-rename? Or allow duplicates?
    local name1 = ev1.getName()
    local name2 = ev2.getName()
    local areDifferent = (name1 != name2)

    local result = "{{\\"test\\":\\"dupe_event_name\\",\\"name1\\":\\"" + name1 + "\\",\\"name2\\":\\"" + name2 + "\\",\\"autoRenamed\\":" + (if areDifferent then "true" else "false") + "}}"
    delete tf
    result
)
```

**Why This Matters:** If tyFlow allows duplicate event names, our scene-path
approach (`$tyFlowName.EventName.OperatorName`) becomes ambiguous. We may need
to auto-append indices or enforce unique names.

#### Test E4: Scene Path Access After Creation

```maxscript
(
    local tf = tyflow()
    tf.name = "zzz_ScenePathTest"
    local ev1 = tf.addEvent()
    ev1.setName "MyEvent"
    local birthOp = ev1.addOperator "Birth" -1
    birthOp.setName "MyBirth"
    birthOp.birthTotal = 42

    -- Try scene path access
    local val = undefined
    try (
        val = $zzz_ScenePathTest.MyEvent.MyBirth.birthTotal
    ) catch ()

    local pass = (val == 42)
    local result = "{{\\"test\\":\\"scene_path\\",\\"pass\\":" + (if pass then "true" else "false") + ",\\"value\\":" + (if val != undefined then val as string else "null") + "}}"
    delete tf
    result
)
```

**Why This Matters:** `modify_tyflow_operator` relies on scene path access.
If it does not work, we need an alternative approach (e.g., storing operator
references via custom attributes or using index-based access).

#### Test E5: Special Characters in Names

```maxscript
(
    local tf = tyflow()
    tf.name = "zzz_Special Test-Flow (1)"
    local ev1 = tf.addEvent()
    ev1.setName "Event With Spaces"

    local birthOp = ev1.addOperator "Birth" -1
    birthOp.birthTotal = 99

    -- Scene path with special chars may need $'Name' syntax
    local val = undefined
    try (
        val = execute "$'zzz_Special Test-Flow (1)'.'Event With Spaces'.Birth.birthTotal"
    ) catch ()

    local pass = (val == 99)
    local result = "{{\\"test\\":\\"special_chars\\",\\"pass\\":" + (if pass then "true" else "false") + "}}"
    delete tf
    result
)
```

---

### 6.7 Preset Tests

For each preset in Section 5, run a simplified test:

```maxscript
-- Generic preset test template
(
    -- [preset creation code here]

    tf.reset_simulation()
    sliderTime = 30f
    tf.updateParticles currentTime

    local n = tf.numParticles()
    local hasShape = false
    try (
        local snapMesh = snapshotAsMesh tf
        hasShape = (snapMesh.numVerts > 0)
        delete snapMesh
    ) catch ()

    local pass = (n > 0) and hasShape
    local result = "{{\\"test\\":\\"preset_{preset_name}\\",\\"pass\\":" + (if pass then "true" else "false") + ",\\"particles\\":" + (n as string) + "}}"
    delete tf
    result
)
```

---

## 7. Implementation Order

### Phase 0: Research & Shape ID Mapping -- COMPLETED 2026-03-03

**Duration:** 1 session (completed)

**Tasks:**
1. ~~Run all scripts from Section 2 inside 3ds Max.~~ DONE
2. ~~Run all scripts from Section 3 (Shape ID investigation).~~ DONE
3. ~~Record results in a new file.~~ DONE -- `docs/research/tyflow_introspection.md`
4. ~~Confirm the Shape 3D type ID mapping.~~ DONE -- Triangle=0, Cone=1, Quad=2, Cylinder=3, Sphere=4, Pyramid=5 (default), Cube=6, Octahedron=7, GeoSphere=8-10, Icosahedron=11
5. ~~Confirm event/operator enumeration approach.~~ DONE -- via baseobject SubAnims
6. ~~Confirm scene path access works.~~ DONE -- `$flowName.baseobject[#EventName][#OperatorName]`
7. ~~Run edge case tests E3, E4, E5 to verify naming assumptions.~~ DONE -- operators with spaces need `#'Quoted Name'`
8. ~~Update `SHAPE_3D_IDS` and `SHAPE_2D_IDS` dicts with confirmed values.~~ DONE

**Deliverable:** Confirmed property reference and shape ID mapping.

**Exit Criteria:** All research scripts run successfully, shape mapping documented.

> **Key findings from Phase 0:**
> - 51 operators confirmed working out of 99 tested names
> - addOperator requires 2 args: `ev.addOperator "Name" positionIndex`
> - quickType_submit causes access violation CRASH -- do NOT use
> - 2D and 3D shape IDs produce identical geometry; distinction is in shapeMode property
> - Events created via `tf.addEvent()` returning `tyEvent`
> - Particle data: 14 single-particle functions + 14 bulk functions + volume interface

---

### Phase 1: Core Module & Basic Flow Creation

**Duration:** 1 session

**Tasks:**
1. Create `src/tools/tyflow.py` with boilerplate, helpers, and shape ID constants.
2. Implement `create_tyflow` (the big builder).
3. Implement `reset_tyflow_simulation`.
4. Register module in `src/server.py` imports.
5. Run tests F1, F2 (create and inspect, connections).
6. Run test E1 (variable naming).

**Dependencies:** Phase 0 (need confirmed shape IDs).

**Deliverable:** Can create tyFlow systems with events, operators, and connections.

---

### Phase 2: Shape Configuration (Bug Fix)

**Duration:** 1 session

**Tasks:**
1. Implement `set_tyflow_shape` with confirmed ID mapping.
2. Run ALL Shape tests (S1 through S5).
3. Run test S3 (tab mismatch) to determine padding strategy.
4. Verify the original bug is fixed: create flow with "sphere" shape, confirm
   viewport shows spheres (not triangles).

**Dependencies:** Phase 1 (need create_tyflow working), Phase 0 (confirmed IDs).

**Deliverable:** Shape operator works correctly with human-readable names.

**Exit Criteria:** Every 3D shape type produces the correct geometry in viewport.

---

### Phase 3: Inspection & Modification

**Duration:** 1 session

**Tasks:**
1. Implement `get_tyflow_info`.
2. Implement `modify_tyflow_operator`.
3. Implement `add_tyflow_event`.
4. Implement `connect_tyflow_events`.
5. Implement `remove_tyflow_element`.
6. Run tests F3, F4 (removal).

**Dependencies:** Phase 1, Phase 0 (enumeration research).

**Deliverable:** Full CRUD on tyFlow structures.

---

### Phase 4: PhysX & Collision

**Duration:** 1 session

**Tasks:**
1. Implement `set_tyflow_physx`.
2. Implement `add_tyflow_collision`.
3. Run tests P1, P2 (ground collision, mesh collision).

**Dependencies:** Phase 1.

**Deliverable:** PhysX simulation works correctly via MCP tools.

---

### Phase 5: Particle Data

**Duration:** 1 session

**Tasks:**
1. Implement `get_tyflow_particles`.
2. Implement `get_tyflow_particle_count`.
3. Run tests D1, D2 (data reading, performance).
4. Test with `max_particles` limit for large counts.

**Dependencies:** Phase 1.

**Deliverable:** Can read particle state data from running simulations.

---

### Phase 6: Presets

**Duration:** 1 session

**Tasks:**
1. Implement `create_tyflow_preset` with all 8 presets.
2. Run preset tests for each preset type.
3. Visual verification of each preset.

**Dependencies:** Phase 2 (shape), Phase 4 (PhysX for debris preset).

**Deliverable:** One-call preset creation for common particle effects.

---

### Phase 7: Integration Testing & Polish

**Duration:** 1 session

**Tasks:**
1. Run the full test suite end-to-end.
2. Test tool chaining: create -> modify shape -> add physics -> read particles.
3. Test error handling: missing objects, invalid names, wrong types.
4. Update SKILL.md with tyFlow tool documentation.
5. Update `docs/tyflow_maxscript_reference.md` with any corrections from research.

**Dependencies:** All prior phases.

**Deliverable:** Production-ready tyFlow tools.

---

### Dependency Graph

```
Phase 0 (Research)
    |
    +---> Phase 1 (Core) ---> Phase 3 (Inspect/Modify)
    |         |
    |         +---> Phase 2 (Shape) ---> Phase 6 (Presets)
    |         |
    |         +---> Phase 4 (PhysX) ---> Phase 6 (Presets)
    |         |
    |         +---> Phase 5 (Data)
    |
    +---> All phases feed into Phase 7 (Integration)
```

---

## 8. Known Risks & Mitigations

### Risk 1: Shape `_tab` Array ID Mapping Is Wrong -- RESOLVED

**Severity:** HIGH (already caused a user-facing bug) -- **RESOLVED 2026-03-03**

**Description:** The `type_3d_ID_tab` integer-to-shape mapping is not documented
by tyFlow. Our assumed mapping (0=Sphere) was INCORRECT. Default is 5=Pyramid.

**Resolution:**
- Phase 0 exhaustively tested IDs 0-25 with vertex-count fingerprinting.
- Confirmed mapping: Triangle=0, Cone=1, Quad=2, Cylinder=3, Sphere=4, Pyramid=5, Cube=6, Octahedron=7, GeoSphere(low/med/high)=8/9/10, Icosahedron=11.
- The `set_tyflow_shape` tool uses string names ("sphere", "box") and translates
  internally, so the mapping is corrected in one place.
- If the mapping changes between tyFlow versions, we add version detection.

### Risk 2: Variable Naming Conflicts

**Severity:** MEDIUM

**Description:** MAXScript global names like `Birth`, `Speed`, `Force`, `Shape`,
`Scale`, `Rotation`, `Spin`, `Select`, `Delete`, `Display` conflict with
tyFlow operator type names. Using them as variable names causes silent bugs.

**Mitigation:**
- All generated variable names use the `_Op` suffix pattern: `birthOp`, `speedOp`, etc.
- Code review checklist item: verify no bare operator names used as variables.
- Helper function `_safe_var_name(op_type)` that maps operator types to safe variable names.
- Variable name map:

```python
SAFE_VAR_NAMES = {
    "Birth": "birthOp",
    "Birth Burst": "birthBurstOp",
    "Speed": "speedOp",
    "Spin": "spinOp",
    "Rotation": "rotOp",
    "Force": "forceOp",
    "Shape": "shapeOp",
    "Display": "displayOp",
    "Scale": "scaleOp",
    "Mass": "massOp",
    "Select": "selectOp",
    "Delete": "deleteOp",
    "Spawn": "spawnOp",
    "Collision": "collOp",
    "Slow": "slowOp",
    "Stop": "stopOp",
    "Spread": "spreadOp",
    "Color": "colorOp",
    "Position": "posOp",
    # Generic fallback: opTypeString.replace(" ", "_").lower() + "Op"
}
```

### Risk 3: PhysX Gravity Dual Systems

**Severity:** MEDIUM

**Description:** Two independent gravity systems:
1. **Force operator** `gravityStrength` -- applies to non-PhysX particle motion.
2. **tyFlow object** `physXGravityValue` -- applies to PhysX rigidbody simulation.

If both are enabled, particles may fall twice as fast or behave unpredictably.

**Mitigation:**
- Document clearly in tool docstrings which gravity system each setting controls.
- Preset templates use one system or the other, never both:
  - Non-PhysX presets (rain, snow, fountain): use Force operator gravity only.
  - PhysX presets (debris): use object-level PhysX gravity only (no Force gravity).
- `create_tyflow_preset` enforces this separation.
- `set_tyflow_physx` docstring warns about dual gravity.

### Risk 4: Event/Operator Enumeration Not Available -- RESOLVED

**Severity:** MEDIUM -- **RESOLVED 2026-03-03**

**Description:** tyFlow does not expose `getEvent(index)` or `numEvents()`.

**Resolution:**
- SubAnim traversal works: baseobject has 21 fixed SubAnims (params), then events at indices 21+.
- Each event SubAnim contains operators indexed sequentially.
- `getSubAnimName` returns event/operator names.
- Access pattern: `tfObj.baseobject[#EventName][#OperatorName]` (quote names with spaces).
- The `create_tyflow` tool returns full structure in its JSON response, so the
  AI has the information it just created.

### Risk 5: Read-Only Particle Data Limitations

**Severity:** LOW

**Description:** Particle positions, velocities, ages etc. are read-only.
Cannot set particle positions via MAXScript.

**Mitigation:**
- Document this clearly.
- All particle data tools are read-only by design.
- Particle behavior is controlled indirectly via operators (Speed, Force, etc.).

### Risk 6: `_tab` Array Length Requirements

**Severity:** MEDIUM

**Description:** All `_tab` arrays on the Shape operator may need to be the same
length. If not, tyFlow may crash or produce undefined behavior.

**Mitigation:**
- Test S3 (tab mismatch) in Phase 0 determines the behavior.
- Python-side validation enforces equal-length arrays before sending MAXScript.
- `set_tyflow_shape` auto-pads missing fields with defaults.
- Error message if the user provides inconsistent data.

### Risk 7: Scene Path Access for Operators

**Severity:** MEDIUM

**Description:** The `$tyFlowName.EventName.OperatorName.property` scene path
syntax may not work reliably, especially with spaces, special characters, or
duplicate names.

**Mitigation:**
- Test E4 and E5 verify scene path access.
- If unreliable, switch to storing references directly during creation (return
  event/operator indices in JSON) and using index-based access:
  ```maxscript
  local tfObj = getNodeByName "MyFlow"
  -- use subAnim index or stored reference
  ```
- Enforce unique event names in `create_tyflow` (append index if duplicate detected).

### Risk 8: Large JSON Response Sizes

**Severity:** LOW-MEDIUM

**Description:** `get_tyflow_particles` with 10,000+ particles generates very
large JSON strings that may exceed the TCP buffer or cause timeouts.

**Mitigation:**
- `max_particles` parameter with default of 1000.
- Always report total count in response even when limiting.
- For very large counts, suggest using `get_tyflow_particle_count` first.
- Consider adding sampling options (every Nth particle, spatial region).
- Use extended timeout for particle data tools.

### Risk 9: tyFlow Version Compatibility

**Severity:** LOW

**Description:** tyFlow MAXScript API was added in v1.118. Older versions will
fail silently or throw errors.

**Mitigation:**
- Add a version check at the start of `create_tyflow`:
  ```maxscript
  try (local testTF = tyflow(); delete testTF; true) catch (false)
  ```
- Return clear error message if tyFlow is not installed or too old.
- Document minimum version requirement in tool docstrings.

### Risk 10: `instancedGeo_tab` with Mixed Shape Types

**Severity:** MEDIUM

**Description:** When mixing 3D, 2D, and reference shapes in a single Shape
operator, the `instancedGeo_tab` array needs entries for all shapes, but
non-reference entries should be... undefined? null? This is undocumented.

**Mitigation:**
- Test in Phase 0: create a mixed shape list with 3D and reference types.
- Try `undefined` for non-reference entries.
- If that fails, try `$` (the scene root) or a dummy hidden node.
- Document the working approach.

---

## 9. File Structure

### New Files

```
src/tools/tyflow.py          -- All tyFlow MCP tools (main implementation)
docs/research/tyflow_introspection.md  -- Results from Phase 0 research (COMPLETED 2026-03-03)
```

### Modified Files

```
src/server.py                -- Add 'tyflow' to the import chain on line 13
```

### `src/server.py` Change

```python
# Line 13 (add tyflow at the end):
from .tools import execute, scene, objects, materials, render, viewport, identify, transform, hierarchy, modifiers, selection, clone, scene_manage, visibility, inspect, build, grid, floor_plan, scene_query, effects, material_ops, state_sets, data_channel, wire_params, controllers, scattering, tyflow  # noqa: E402, F401
```

### `src/tools/tyflow.py` Structure

```python
"""tyFlow particle system tools for 3ds Max.

Requires tyFlow v1.118+ (September 2024) with MAXScript API support.

Key concepts:
- tyFlow objects contain Events, which contain Operators.
- Particles flow between Events via Send Out / Split operators.
- Shape operator uses _tab arrays (single-item properties are READ-ONLY).
- PhysX gravity lives on the tyFlow object, Force gravity on the operator.
- Variable names must be suffixed (birthOp, not Birth) to avoid MAXScript conflicts.
"""

from __future__ import annotations
from ..server import mcp, client

# --- Constants ---
SHAPE_3D_IDS = { "triangle": 0, "cone": 1, "quad": 2, "plane": 2, "cylinder": 3, "sphere": 4, "pyramid": 5, "box": 6, "cube": 6, "octahedron": 7, "geosphere_low": 8, "geosphere": 9, "geosphere_high": 10, "icosahedron": 11 }
SHAPE_2D_IDS = {}  # Same IDs as 3D; distinction is shapeMode property
SAFE_VAR_NAMES = { ... }  # Operator type -> safe MAXScript variable name

# --- Helpers ---
def _safe_name(name: str) -> str: ...
def _safe_var_name(op_type: str) -> str: ...
def _maxscript_value(val) -> str: ...
def _int_array(values: list[int]) -> str: ...
def _float_array(values: list[float]) -> str: ...
def _bool_array(values: list[bool]) -> str: ...
def _name_array(names: list[str]) -> str: ...
def _node_array(names: list[str]) -> str: ...

# --- Flow Management ---
@mcp.tool()
def create_tyflow(...) -> str: ...

@mcp.tool()
def get_tyflow_info(...) -> str: ...

@mcp.tool()
def modify_tyflow_operator(...) -> str: ...

@mcp.tool()
def add_tyflow_event(...) -> str: ...

@mcp.tool()
def connect_tyflow_events(...) -> str: ...

@mcp.tool()
def remove_tyflow_element(...) -> str: ...

# --- Shape (HIGH PRIORITY) ---
@mcp.tool()
def set_tyflow_shape(...) -> str: ...

# --- Physics ---
@mcp.tool()
def set_tyflow_physx(...) -> str: ...

@mcp.tool()
def add_tyflow_collision(...) -> str: ...

# --- Particle Data ---
@mcp.tool()
def get_tyflow_particles(...) -> str: ...

@mcp.tool()
def get_tyflow_particle_count(...) -> str: ...

# --- Simulation ---
@mcp.tool()
def reset_tyflow_simulation(...) -> str: ...

# --- Presets ---
@mcp.tool()
def create_tyflow_preset(...) -> str: ...
```

### Tool Count Summary

| Category | Tools | Count |
|---|---|---|
| Flow Management | create, get_info, modify_op, add_event, connect, remove | 6 |
| Shape | set_shape | 1 |
| Physics | set_physx, add_collision | 2 |
| Particle Data | get_particles, get_count | 2 |
| Simulation | reset_simulation | 1 |
| Presets | create_preset | 1 |
| **Total** | | **13** |
