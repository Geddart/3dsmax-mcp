# tyFlow Introspection Results

**Date:** 2026-03-03
**3ds Max Version:** 2025 (PID 91996)
**Source:** Live introspection via `execute_maxscript` MCP tool

---

## 1. Core Architecture

### Object Creation
- `tyflow()` creates a tyFlow object (GeometryClass)
- Events are added via `tf.addEvent()` which returns a `tyEvent` object
- Operators are added to events via `ev.addOperator "OperatorName" positionIndex`

### tyEvent Interface
```
getEnabled() -> boolean
setEnabled(boolean enabled)
getName() -> string
setName(string name)
getPosition() -> point2
setPosition(point2 position)
getWidth() -> integer
setWidth(integer width)
addOperator(string type, integer where) -> object
remove()
```

### tyFlow Interface (on the object)
```
exportPRT(integer opID, integer partitionFrom, integer partitionTo) -> integer
exportTyCache(integer opID) -> integer
quickType_submit(integer type, integer posX, integer posY, string name) -> integer  -- CRASHES, avoid
activate_license() / deactivate_license() / switch_license_type(integer type) / license_activated() -> integer
editor_open() / editor_close()
reset_simulation()
reseed()
addEvent() -> object
updateParticles(integer frame)
numParticles() -> integer
sortParticlesByID()
```

### Particle Data Access
```
getParticleID(integer index) -> integer
getParticleAge(integer index) -> float
getParticleTM(integer index) -> matrix3
getParticlePosition(integer index) -> point3
getParticleScale(integer index) -> point3
getParticleVelocity(integer index) -> point3
getParticleShapeMesh(integer index) -> mesh
getParticleMatID(integer index) -> integer
getParticleInstanceID(integer index) -> integer
getParticleMass(integer index) -> float
getParticleSimGroups(integer index) -> integer
getParticleExportGroups(integer index) -> integer
getParticleUVWChannels(integer index) -> integer array
getParticleUVW(integer index, integer channel) -> point3
```

### Bulk Particle Access
```
getAllParticleIDs() -> integer array
getAllParticleAges() -> float array
getAllParticleTMs() -> value array
getAllParticlePositions() -> value array
getAllParticleScales() -> value array
getAllParticleVelocities() -> value array
getAllParticleShapeMeshes() -> value array
getAllParticleMatIDs() -> integer array
getAllParticleInstanceIDs() -> integer array
getAllParticleMasses() -> float array
getAllParticleSimGroups() -> integer array
getAllParticleExportGroups() -> integer array
getAllParticleUVWChannels() -> value array
getAllParticleUVWs(integer channel) -> value array
```

### Volume Interface
```
updateVolumes() / releaseVolumes()
getVolumeScalar(point3 position, integer type) -> float
getVolumeVector(point3 position, integer type) -> point3
convertVolumeTemperature(float temperature, integer units) -> float
```

---

## 2. Operator Discovery

### All 51 Confirmed Operators
Birth, Speed, Shape, Display, Delete, Force, Spin, Kill Age, Rotation, Scale, Event, Spawn, Export Particles, PhysX Shape, PhysX Collision, Cloth, Cloth Bind, Fracture, Voronoi Fracture, Boolean, Noise, Mapping, Material Static, Material Dynamic, Color, Custom Properties, Script, Face Fracture, Editor, Position Object, Particle Object, Collision Spawn, Slow, PhysX Switch, PhysX Bind, PhysX Glue, Skin Wrap, Birth Objects, Birth Surface, Birth Spline, UVW Map, Find Target, Property Test, Age Test, Collision Test, Particle Test, Custom Properties Test, Distance Test, Surface Test, Density, Icon Settings, Path Follow, Brick Fracture, Extrude, Bind, Spring, Object Test, Element Fracture, Bounds Fracture, Multifracture, Convex Hull

### Operator Access Pattern
Operators are accessed as SubAnims via the scene path:
```maxscript
$tyFlowName.EventName.OperatorName.propertyName
-- OR via baseobject SubAnims:
$tyFlowName.baseobject[#EventName][#OperatorName]
```

**Note:** Operators with spaces in their name (e.g., "PhysX Shape") require quoting:
```maxscript
$tyFlowName.baseobject[#EventName][#'PhysX Shape']
```

Some operators (Fracture, Export Particles) may not expose SubAnims via getPropNames — requires further investigation.

---

## 3. Shape Type ID Mapping (CRITICAL)

### 3D Shape IDs (type_3d_ID_tab)

Default value: `#(5)` (Pyramid)

| ID | Verts | Faces | Likely Shape |
|----|-------|-------|-------------|
| 0 | 3 | 1 | Triangle |
| 1 | 28 | 26 | Cone |
| 2 | 4 | 2 | Quad/Plane |
| 3 | 25 | 32 | Cylinder |
| 4 | 289 | 512 | Sphere (high-res, ~16 segs) |
| 5 | 5 | 6 | Pyramid (tetrahedron) |
| 6 | 8 | 12 | Cube/Box |
| 7 | 6 | 8 | Octahedron |
| 8 | 62 | 120 | GeoSphere (low) |
| 9 | 266 | 528 | GeoSphere (medium) |
| 10 | 1106 | 2208 | GeoSphere (high) |
| 11 | 12 | 20 | Icosahedron |
| 12 | 22 | 40 | Subdivided Icosahedron (1) |
| 13 | 26 | 48 | Unknown polyhedron |
| 14 | 50 | 96 | Subdivided polyhedron |
| 15 | 98 | 192 | Subdivided polyhedron |
| 16 | 60 | 120 | Similar to GeoSphere variant |
| 17 | 240 | 480 | High-res variant |
| 18 | 960 | 1920 | Very high-res variant |
| 19 | 42 | 80 | Icosphere (level 2) |
| 20 | 162 | 320 | Icosphere (level 3) |
| 21 | 642 | 1280 | Icosphere (level 4) |
| 22 | 34 | 64 | Unknown |
| 23 | 38 | 72 | Unknown |
| 24 | 386 | 768 | High-res polyhedron |
| 25 | 92 | 180 | Unknown |

### Key Mappings for Common Shapes
- **Triangle:** ID 0
- **Quad/Plane:** ID 2
- **Pyramid:** ID 5 (DEFAULT)
- **Cube/Box:** ID 6
- **Octahedron:** ID 7
- **Icosahedron:** ID 11
- **Sphere:** ID 4 (standard), ID 8-10 (GeoSphere variants)
- **Cone:** ID 1
- **Cylinder:** ID 3

### 2D Shape IDs (type_2d_ID_tab)
Tested IDs 0-15 — returned IDENTICAL vertex/face counts as 3D shapes. This suggests 2D mode may use the same geometry or the mode is set elsewhere (shapeMode property).

### Shape Mode Properties
```
shapeMode : integer     -- 0=2D, 1=3D, 2=Reference
shapeMode2D : integer   -- sub-mode for 2D
shapeMode3D : integer   -- sub-mode for 3D
shape_type_tab : integer array  -- per-item shape type (0=2D, 1=3D, 2=Reference)
```

---

## 4. Shape Operator Properties (145 total)

### Key Properties (excluding filter/timing/groups)
```
distributionMode, distributionFloatChannel
saveIndex, saveIndexFloatChannel
saveCurrentFrame, saveCurrentFrameFloatChannel
seed, frequency, scale, scaleValue, scaleVariation
shapeMode, shapeMode2D, shapeMode3D
referenceNode : node
vrmeshFilename : string
vrmeshPreview : boolean
meshSplitGroup, meshSplitGroupKeepPivot, meshSplitElements
meshCenterPivots, meshPreserveNormals
meshMaterialID, meshMaterialIDMin, meshMaterialIDMax
materialMode : integer
material : material
materialFilename : string
meshAnimated, meshAnimatedRenderOnly, meshAnimatedTimingMode
meshAnimatedTimingFloatChannel, meshAnimatedDefault
meshAnimatedStart, meshAnimatedEnd, meshAnimatedOffset
meshAnimatedSpeed, meshAnimatedSpeedVariation
meshAnimatedLoop, meshAnimatedInterpolation
```

### Per-Item Tab Arrays (ALL writable)
```
frequency_tab : float array
scale_tab : boolean array
scaleVal_tab : float array
scaleVariation_tab : float array
shape_type_tab : integer array        -- 0=2D, 1=3D, 2=Reference
type_2d_ID_tab : integer array
type_3d_ID_tab : integer array        -- THE critical shape mapping
instancedGeo_tab : node array         -- for Reference mode
materialMode_tab : integer array
material_tab : material array
matFile_tab : string array
vrmeshFilename_tab : string array
vrmeshPreview_tab : boolean array
meshSplitGroup_tab, meshSplitGroupKeepPivot_tab, meshSplitElements_tab
meshCenterPivots_tab, meshPreserveNormals_tab
meshMatID_tab, meshMatIDMin_tab, meshMatIDMax_tab
meshAnimated_tab, meshAnimatedRender_tab, meshAnimatedTiming_tab
meshAnimatedTimingCustomFloatChannel_tab
meshAnimatedDefault_tab, meshAnimatedStart_tab, meshAnimatedEnd_tab
meshAnimatedLoop_tab, meshAnimatedInterp_tab
meshAnimatedSpeed_tab, meshAnimatedSpeedVariation_tab, meshAnimatedOffset_tab
```

---

## 5. Core Operator Properties

### Birth (17 key properties)
```
birthStart, birthEndEnable, birthEnd
everyNthEnabled, everyNth
birthMode, birthTotal, birthPerFrame, birthPerStep, birthPerFrameVariation
repeaterCount, repeaterCountVariation
repeaterDurationFrames, repeaterDurationFramesVariation
repeaterIntervalFrames, repeaterIntervalFramesVariation
seed
```

### Speed (key properties)
```
speedMode, magnitudeMode, magnitude, magnitudeMultiplier, magnitudeVariation
directionMode, directionVectorChannel, directionDivergence
velocityAffectMode, velocityX, velocityY, velocityZ
interpolationMode, interpolationDuration, interpolationValue
noise*: mode, fractalMode, strength, frequency, scale, roughness, iterations, octaves, phase, seed, offset*
objectlist (node array), seed, seedByTime
```

### Rotation (key properties)
```
mode, affectShape
rotationX, rotationY, rotationZ, rotationDivergence
restrictDivergence, divergenceX, divergenceY, divergenceZ
rotationLimit, rotationLimitDegrees, rotationLimitDegreesVariation
interpolationMode, interpolationDuration
forwardMode, forwardX, forwardY, forwardZ
upMode, bankingMultiplier, bankingSmooth
objectlist, sample, splineAccuracy
```

### Display (key properties)
```
displayMode, colorUI, colorGammaCorrected, sizeMultiplier
markNoGeometry, displayMaterial
mappingMode, mappingSingleChannel
colorMode, colorMappingTexmapSource, colorMappingTexmap, colorMappingChannel
colorFloatVectorChannel, colorMultiplier
gradientEnable, gradientMin, gradientMax, gradientGradient
spriteMode, spriteTexmap, spriteVariation
```

### Force (key properties, 197 total)
```
gravityStrength, windX, windY, windZ, windStrength
noise*: mode, fractalMode, strength, frequency, scale, roughness, octaves, phase, seed
noise2*: second noise layer (same structure)
velocityAffectMode, velocityX/Y/Z, velocityMultiplier, velocityVariation
spinX/Y/Z, spinMultiplier, spinVariation
relativeToMass, relativeToMassPercent
clothAerodynamics, clothAerodynamicsStrength
objectlist, seed
```

### Spawn (key properties, 154 total)
```
spawnMode, deleteParent, rememberParent, resetAge
rate, rateVariation, stepsize, stepVariation
spawnPercent, offspringCount, offspringCountVariation
positionMode, positionMatIDFilter, positionOffset, positionOffsetVariation
velocityInherited, velocityVariation, velocityDivergence
inheritCustomProperties, inheritMapping, inheritMaterialID, inheritShape
spinInherited, spinVariation, scaleInherited, scaleVariation
limitPerParticle, limitPerStep, avoidOverlap
seed
```

### PhysX Shape (93 key / 164 total)
Accessed via `baseobject[#EventName][#'PhysX Shape']`

### Scale (92 key / 163 total)
Accessed via baseobject SubAnims

### Script (64 key / 65 total)
Accessed via baseobject SubAnims

---

## 6. tyFlow Object-Level Properties

### Simulation
simResetMode, enabled, simulationMode, timeStep, timeScale, interpolateTicks, networkVersionAbort, networkingCaching

### Cache
cacheEnable, cacheSubframes, terrainCacheEnable, terrainCacheMode, clearUnusedMeshes, cacheAge, cachePosition, cacheRotation, cacheScale, cacheVelocity, cacheSpin, cacheShape, cacheMaterialID, cachePhysX, cacheMass, cacheMapping, cacheGroups, cacheCustFloat, cacheCustVector, cacheCustTM, meshCacheInclude

### Retimer
retimerEnabled, retimerMode, retimerFrame, retimerSpeed, retimerSpeedFrame

### PhysX Global
physXSolver, physXGravityEnabled, physXGravityValue, physXGroundCollider, physXGroundColliderHeight, physXGroundColliderRestitution, physXGroundColliderSFriction, physXGroundColliderDFriction, physXSubsteps, physXPosIterations, physXVelIterations, physXInertiaMult, physXSimulationGroupCollisionFiltering, physXEnhancedDeterminism, physXFrictionEverySubstep, physXKinematicPairs, physXCCD, physXCCDSteps, physXCUDA, physXCUDAMemory

### Bind (collision system)
bindCollisionRepulseSteps, bindCollisionRepulseMult, bindCollisionImpulseSteps, bindCollisionImpulseMult, bindCollisionIZSteps, bindCollisionIZThresh, bindCollisionCGThresh, bindCollisionMaxIZSize, bindCollisionIZJitter, bindCollisionIZLimit, bindSteps, bindMassMult, bindSleepVelocityThresh, bindSleepMinDuration, bindWakeThresh, bindWakeTransfer

### Display
showIcon, iconSize, showName, displayMeshWireframes, displayMeshFaceNormals/Size, displayMeshVertexNormals/Size, displayMeshVelocities, displayMeshVertices/Positions, displayMeshFaces, displayBoundsInflate, displayTerrainProgress

### Export Groups
exportGroups1_A through exportGroups1_P, exportGroups1_matchType

### Simulation Groups
simulationGroups1_1 through simulationGroups1_16

### Threading
autoThreads, threads, physXThreads, autoPhysXThreads

### Printing/Debug
printSimSummary, printCacheSummary, printDetails, printGPUMeshDetails, printGPUParticleDetails

---

## 7. SubAnim Structure

tyFlow baseobject has 21 SubAnims:
```
SA[1]: iconSize
SA[2]: timeScale
SA[3]: retimerFrame
SA[4]: retimerSpeed
SA[5-14]: bindCollision* params
SA[15]: bindSteps
SA[16-19]: bindSleep/Wake params
SA[20]: physXGravityValue
SA[21]: EventName (event SubAnim containing operators)
```

Event SubAnims contain operators indexed sequentially.

---

## 8. Key Corrections to Plan

- **addOperator needs 2 args:** `ev.addOperator "Name" positionIndex` — NOT just the name
- **quickType_submit CRASHES:** Access violation — do NOT use
- **Shape default is ID 5 (Pyramid)**, NOT Sphere — this explains the reported "spheres showed as triangles" bug
- **Sphere is ID 4** (289 verts, 512 faces = standard sphere ~16 segs)
- **Cube is ID 6** (8 verts, 12 faces)
- **2D/3D shape IDs appear identical** — the distinction may be in rendering mode, not geometry
- **Operator property access via SubAnims** works: `$flowName.baseobject[#EventName][#OperatorName]`
- **Operators with spaces need quoting:** `#'PhysX Shape'`
- **Not all operators expose getPropNames via SubAnims** — Fracture, Noise, Color may need different access paths
