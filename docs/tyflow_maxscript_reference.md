# tyFlow MAXScript Reference

Full scripting API reference for controlling tyFlow particle systems via MAXScript.
MAXScript control was added in **tyFlow v1.118** (September 2024).

---

## 1. Creating a tyFlow Object

```maxscript
tf = tyflow()
tf.name = "MyParticleSystem"
tf.pos = [0, 0, 100]
```

> **Note:** The icon position is cosmetic for the viewport. tyFlow simulations operate in world-space. However, the default Birth operator uses the tyFlow object's transform as the particle birth origin.

---

## 2. Object-Level PhysX Settings

These properties live on the tyFlow object itself and control the PhysX solver:

```maxscript
-- Gravity
tf.physXGravityEnabled = true
tf.physXGravityValue = -980.0         -- Strength (negative = downward)

-- Built-in ground collider (infinite plane)
tf.physXGroundCollider = true
tf.physXGroundColliderHeight = 0.0    -- World-space Z height
tf.physXGroundColliderRestitution = 0.3
tf.physXGroundColliderSFriction = 0.5
tf.physXGroundColliderDFriction = 0.3

-- Simulation quality
tf.physXSubsteps = 8
tf.physXPosIterations = 4
tf.physXVelIterations = 1
tf.physXInertiaMult = 1.0
tf.physXCCD = false                   -- Continuous collision detection
tf.physXCCDSteps = 1
tf.physXEnhancedDeterminism = false
tf.physXFrictionEverySubstep = false
tf.physXSimulationGroupCollisionFiltering = false
```

---

## 3. Events

Events are containers for operators. Particles flow between events.

```maxscript
ev = tf.addEvent()
ev.setName "MyEvent"
ev.setPosition [100, 200]    -- Editor GUI position (cosmetic)

-- Other event functions
ev.getEnabled()               -- Returns boolean
ev.setEnabled true
ev.getName()                  -- Returns string
ev.getPosition()              -- Returns point2
ev.getWidth()                 -- Returns integer
ev.setWidth 200
ev.remove()                   -- Deletes the event
```

---

## 4. Operators

### Adding Operators

```maxscript
opRef = ev.addOperator "OperatorName" position
-- position: 0-based index, or -1 to append at end
-- Returns: operator reference
```

### Operator Functions

```maxscript
opRef.getEnabled()
opRef.setEnabled true
opRef.getName()
opRef.setName "MyOp"
opRef.connect targetEvent     -- Connect to another event (Send Out, Split, etc.)
opRef.disconnect()
opRef.remove()
```

### Discovering Properties

```maxscript
showProperties opRef
-- or capture to string:
ss = StringStream ""
showProperties opRef to:ss
print (ss as string)
```

### Scene Path Access

After creation, operators can be accessed via scene path:

```maxscript
$MyParticles.EventName.OperatorName.propertyName
```

---

## 5. Available Operator Types

These are the exact strings to pass to `addOperator`:

| Category | Operator Names |
|----------|---------------|
| **Birth** | `"Birth"`, `"Birth Burst"`, `"Birth Flow"`, `"Birth Fluid"`, `"Birth Objects"`, `"Birth PRT"`, `"Birth Paint"`, `"Birth Skeleton"`, `"Birth Spline"`, `"Birth Surface"`, `"Birth Voxels"`, `"Birth VDB"`, `"Birth Terrain"`, `"Birth Intersections"`, `"Birth ForestPack"` |
| **Motion** | `"Speed"`, `"Spin"`, `"Rotation"`, `"Path Follow"`, `"Slow"`, `"Stop"`, `"Spread"`, `"Limiter"`, `"Integrate"`, `"Scale"`, `"Mass"`, `"Temporal Smooth"` |
| **Forces** | `"Force"`, `"Cluster Force"`, `"Flock"`, `"Fluid Force"`, `"Particle Force"`, `"Point Force"`, `"Surface Force"`, `"VDB Force"` |
| **Shape/Display** | `"Shape"`, `"Display"`, `"Display Data"` |
| **PhysX** | `"PhysX Shape"`, `"PhysX Collision"`, `"PhysX Bind"`, `"PhysX Break"`, `"PhysX Modify"`, `"PhysX Fluid"`, `"PhysX Switch"` |
| **Collision** | `"Collision"`, `"Boundary"`, `"Push In/Out"` |
| **Flow Control** | `"Send Out"`, `"Split"`, `"Select"`, `"Delete"`, `"Spawn"` |
| **Tests** | `"Object Test"`, `"Property Test"`, `"Surface Test"`, `"Time Test"` |
| **Fracture** | `"Voronoi Fracture"`, `"Element Fracture"`, `"Face Fracture"`, `"Edge Fracture"`, `"Bounds Fracture"`, `"Brick Fracture"`, `"Multifracture"`, `"Convex Hull"` |
| **Export** | `"Export Particles"`, `"Export VDB"` |

---

## 6. Operator Property Reference

### Birth

```maxscript
birthOp = ev.addOperator "Birth" -1

birthOp.birthStart = 0
birthOp.birthEndEnable = true
birthOp.birthEnd = 100
birthOp.birthMode = 0             -- 0=Total, 1=Per Frame, 2=Per Step, 3=Repeater
birthOp.birthTotal = 500          -- Total count (birthMode=0)
birthOp.birthPerFrame = 60.0      -- Per frame (birthMode=1)
birthOp.birthPerStep = 10.0       -- Per step (birthMode=2)
birthOp.birthPerFrameVariation = 0.0
birthOp.everyNthEnabled = false
birthOp.everyNth = 1
birthOp.seed = 12345

-- Repeater mode (birthMode=3)
birthOp.repeaterCount = 10
birthOp.repeaterCountVariation = 0.0
birthOp.repeaterDurationFrames = 5
birthOp.repeaterDurationFramesVariation = 0
birthOp.repeaterIntervalFrames = 10
birthOp.repeaterIntervalFramesVariation = 0
```

### Speed

```maxscript
speedOp = ev.addOperator "Speed" -1

speedOp.speedMode = 0
speedOp.magnitudeMode = 0
speedOp.magnitude = 300.0
speedOp.magnitudeMultiplier = 1.0
speedOp.magnitudeVariation = 50.0     -- % variation
speedOp.directionMode = 3
    -- 0 = Along Icon Arrow
    -- 1 = Icon Center Out
    -- 2 = Icon Axis Out
    -- 3 = Random 3D
    -- 4 = Random Horizontal
    -- 5 = Inherit Previous
speedOp.directionReverse = false
speedOp.simulateSubsteps = false
speedOp.seed = 12345
speedOp.objectList = #()              -- Node array for icon-based directions
```

### Force

```maxscript
forceOp = ev.addOperator "Force" -1

-- Gravity
forceOp.gravityStrength = -1.0

-- Wind
forceOp.windX = 0.0
forceOp.windY = 0.0
forceOp.windZ = 1.0
forceOp.windStrength = 0.0

-- Noise
forceOp.noiseStrength = 0.0
forceOp.noiseFrequency = 0.5
forceOp.noiseScale = 1.0

-- Velocity affect
forceOp.velocityAffectMode = 0       -- 0=Both, 1=Magnitude, 2=Direction
forceOp.velocityX = 100.0
forceOp.velocityY = 100.0
forceOp.velocityZ = 100.0
forceOp.velocityMultiplier = 100.0

-- External force objects (spacewarps)
forceOp.objectList = #()
```

### Shape

> **Important:** Single-item properties (`shapeMode`, `shapeMode3D`, `referenceNode`, `scale`, etc.) are **read-only**. Use the `_tab` array properties to configure shapes.

```maxscript
shapeOp = ev.addOperator "Shape" -1

-- Use _tab arrays to define the shape list
shapeOp.shape_type_tab = #(1)            -- 0=2D, 1=3D, 2=Reference Object
shapeOp.type_3d_ID_tab = #(0)            -- 3D shape ID (0=Sphere, etc.)
shapeOp.type_2d_ID_tab = #(0)            -- 2D shape ID
shapeOp.instancedGeo_tab = #(myMesh)     -- Reference node objects
shapeOp.frequency_tab = #(100.0)         -- Distribution weight
shapeOp.scaleVal_tab = #(100.0)          -- Scale %
shapeOp.scaleVariation_tab = #(0.0)
shapeOp.scale_tab = #(false)             -- Enable override scale
shapeOp.meshCenterPivots_tab = #(false)
shapeOp.meshPreserveNormals_tab = #(false)
shapeOp.meshSplitElements_tab = #(false)
shapeOp.meshSplitGroup_tab = #(false)
shapeOp.meshAnimated_tab = #(false)

-- Writable non-tab property
shapeOp.distributionMode = 0             -- 0=Random by frequency, 1=Index from custom float
```

### Display

```maxscript
displayOp = ev.addOperator "Display" -1

displayOp.displayMode = 2        -- 0=None, 1=Ticks, 2=Geometry, 3=Bounding Box
displayOp.sizeMultiplier = 1.0
displayOp.filterPercent = 100.0
displayOp.colorMode = 0
displayOp.displayMaterial = false
```

### PhysX Shape

Defines the rigidbody shape for each particle.

```maxscript
physxShapeOp = ev.addOperator "PhysX Shape" -1

-- Hull type
physxShapeOp.hullMode = 4            -- 0=Box, 1=Compound, 2=Convex Hull, 3=Mesh, 4=Sphere

-- Bounce and friction
physxShapeOp.restitution = 0.5
physxShapeOp.staticFriction = 0.4
physxShapeOp.dynamicFriction = 0.3

-- Damping
physxShapeOp.angularDamping = 0.1
physxShapeOp.linearDamping = 0.05

-- Mass
physxShapeOp.massOverride = false
physxShapeOp.mass = 1.0

-- Velocity limits
physxShapeOp.limitImpulse = 0.0      -- 0 = no limit
physxShapeOp.limitAngular = 0.0
physxShapeOp.limitExit = 0.0

-- Position/Rotation locks
physxShapeOp.lockPosX = false
physxShapeOp.lockPosY = false
physxShapeOp.lockPosZ = false
physxShapeOp.lockRotX = false
physxShapeOp.lockRotY = false
physxShapeOp.lockRotZ = false

-- Display
physxShapeOp.displayHull = false

-- Collision tolerance
physxShapeOp.penetrationOffset = 0.0
physxShapeOp.contactSensitivity = 0.0

-- Convex hull settings
physxShapeOp.convexMaxVerts = 255
physxShapeOp.fitBounds = false
physxShapeOp.dimensionsMultiplier = 1.0
```

### PhysX Collision

Defines external mesh objects as colliders for PhysX particles.

```maxscript
physxCollOp = ev.addOperator "PhysX Collision" -1

-- Add collider mesh objects
append physxCollOp.colliderList $MyGroundPlane
-- or set directly:
physxCollOp.colliderList = #($Obj1, $Obj2)

-- Hull type for colliders
physxCollOp.hullMode = 3              -- 0=Sphere, 1=Box, 2=Convex Hull, 3=Mesh

-- Collider physics
physxCollOp.restitution = 0.3
physxCollOp.staticFriction = 0.5
physxCollOp.dynamicFriction = 0.3
physxCollOp.displayHull = false
physxCollOp.fitBoundingBox = false

-- Contact generation
physxCollOp.testGeometryFuture = false
physxCollOp.testGeometryFutureInflate = 0.0

-- Test conditions
physxCollOp.testInterparticle = false
physxCollOp.testGeometry = false
physxCollOp.testGround = false

-- Extra conditions
physxCollOp.conditionCount = false
physxCollOp.conditionCountValue = 1
physxCollOp.conditionImpulseMin = false
physxCollOp.conditionImpulseMinValue = 0.0
```

### Collision (non-PhysX)

Simpler collision without full PhysX rigidbody simulation.

```maxscript
collOp = ev.addOperator "Collision" -1

-- Collider objects
append collOp.colliderList $MyObject

-- Ground collider
collOp.groundCollider = false
collOp.groundColliderOffset = 0.0

-- Radius
collOp.radiusMode = 0
collOp.radius = 1.0
collOp.radiusMultiplier = 1.0

-- Bounce/Friction
collOp.bounce = 1.0
collOp.bounceVariation = 0.0
collOp.bounceDivergence = 0.0
collOp.bounceThreshold = 0.0
collOp.friction = 0.0
collOp.frictionVariation = 0.0
collOp.passThrough = 0.0
collOp.inherit = 0.0
collOp.offset = 0.0
```

---

## 7. Connecting Events

Use `Send Out` or `Split` operators to route particles between events:

```maxscript
sndOp = ev1.addOperator "Send Out" -1
sndOp.connect ev2       -- Particles flow from ev1 to ev2
sndOp.disconnect()      -- Remove the connection
```

---

## 8. Simulation Control & Particle Data

```maxscript
tf.reset_simulation()

-- Reading particle data (read-only, must call updateParticles first)
tf.updateParticles currentTime
n = tf.numParticles()
positions = tf.getAllParticlePositions()
velocities = tf.getAllParticleVelocities()
ages = tf.getAllParticleAges()

-- Single particle access (1-based index)
pos = tf.getParticlePosition 1
vel = tf.getParticleVelocity 1
tm = tf.getParticleTM 1
```

---

## 9. Complete Example: Particles with PhysX Collision

```maxscript
(
    local groundPlane = Plane length:500 width:500 pos:[0,0,0] name:"Ground"

    local tf = tyflow()
    tf.name = "MyParticles"
    tf.pos = [0, 0, 100]

    tf.physXGravityEnabled = true
    tf.physXGravityValue = -980.0
    tf.physXSubsteps = 8

    -- Birth event
    local ev1 = tf.addEvent()
    ev1.setName "Birth"

    local birthOp = ev1.addOperator "Birth" -1
    birthOp.birthMode = 0
    birthOp.birthTotal = 200
    birthOp.birthStart = 0
    birthOp.birthEndEnable = true
    birthOp.birthEnd = 30

    local sndOp = ev1.addOperator "Send Out" -1

    -- Physics event
    local ev2 = tf.addEvent()
    ev2.setName "Physics"

    local speedOp = ev2.addOperator "Speed" -1
    speedOp.magnitude = 300.0
    speedOp.magnitudeVariation = 50.0
    speedOp.directionMode = 3

    local forceOp = ev2.addOperator "Force" -1
    forceOp.gravityStrength = -1.0

    local shapeOp = ev2.addOperator "Shape" -1

    local physxShapeOp = ev2.addOperator "PhysX Shape" -1
    physxShapeOp.hullMode = 4
    physxShapeOp.restitution = 0.5
    physxShapeOp.staticFriction = 0.4
    physxShapeOp.dynamicFriction = 0.3

    local physxCollOp = ev2.addOperator "PhysX Collision" -1
    append physxCollOp.colliderList groundPlane
    physxCollOp.hullMode = 3
    physxCollOp.restitution = 0.3
    physxCollOp.staticFriction = 0.5
    physxCollOp.dynamicFriction = 0.3

    local displayOp = ev2.addOperator "Display" -1
    displayOp.displayMode = 2

    sndOp.connect ev2

    tf.reset_simulation()
    tf.editor_open()
)
```

---

## 10. Key Caveats

1. **Variable naming**: Do NOT use `Birth`, `Speed`, `Force` etc. as variable names - they conflict with MAXScript reserved names. Use suffixed names like `birthOp`, `speedOp`.
2. **Shape _tab arrays**: Single-item Shape properties are read-only. Always use the `_tab` array properties to configure shapes.
3. **Force vs PhysX gravity**: `forceOp.gravityStrength` is operator-level gravity for non-PhysX motion. `tf.physXGravityValue` is the PhysX solver gravity for rigidbodies. For PhysX simulations, the object-level setting is what matters.
4. **Collider lists**: Use `append` to add nodes, or set directly: `physxCollOp.colliderList = #($Obj1, $Obj2)`.
5. **MAXScript wrapping**: All code must be wrapped in parentheses `(...)` when executing via `execute()`.

---

## Sources

- [tyFlow MAXScript Documentation](https://docs.tyflow.com/tyflow_maxscript/)
- [tyFlow Operators List](https://docs.tyflow.com/tyflow_particles/operators/)
- [PhysX Collision Operator](https://docs.tyflow.com/tyflow_particles/operators/physx_collision/)
- [PhysX Shape Operator](https://docs.tyflow.com/tyflow_particles/operators/physx_shape/)
- [PhysX Object-Level Settings](https://docs.tyflow.com/tyflow_particles/object/physx/)
- [Force Operator](https://docs.tyflow.com/tyflow_particles/operators/force/)
- [Birth Operator](https://docs.tyflow.com/tyflow_particles/operators/birth/)
- [Speed Operator](https://docs.tyflow.com/tyflow_particles/operators/speed/)
- [Shape Operator](https://docs.tyflow.com/tyflow_particles/operators/shape/)
- [tyFlow Forum: MAXScript Events/Operators](https://forum.tyflow.com/thread-1145.html)
