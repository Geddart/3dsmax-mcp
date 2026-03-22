# tyFlow 2.0 (Zenith) Introspection Results

**Date:** 2026-03-22
**tyFlow version:** 200300 (v2.003)
**3ds Max:** 2025

## 1. Confirmed Inferno Operators (15 total)

All 15 operators confirmed via `addOperator` + `remove()` cycle.

| # | Operator Name | Notes |
|---|---|---|
| 1 | Birth Inferno | Main fluid sim birth — has solver settings, fuel, buoyancy, etc. |
| 2 | Inferno Emitter | Emission from mesh objects — density, temperature, fuel, color |
| 3 | Inferno Bounds | Simulation domain bounds — include/exclude lists, static bounds |
| 4 | Inferno Display | Viewport ray marching — smoke/fire opacity, AO, lighting, glow |
| 5 | Inferno Collider | Volume collision with objects — ground plane option |
| 6 | Inferno Color | Color control — relative to density/temperature/velocity |
| 7 | Inferno Spawn | Spawn particles from fluid grid — rate, max, relative curves |
| 8 | Inferno Properties | Read fluid data into particle channels — density, color, temp, velocity |
| 9 | Inferno Recall | RAM cache recall — compression, upres ML, sharpen, retiming |
| 10 | Export Inferno | VDB/TYV export — NOT "Inferno Export" |
| 11 | Inferno Force | Forces — gravity, wind, drag, noise (2 noise slots) |
| 12 | Inferno Temperature | Temperature modification — cooling, noise |
| 13 | Inferno Density | Density modification — dissipation, emission by temperature, noise |
| 14 | Inferno Vorticity | Vorticity control — adaptive, constraint, conservation bias |
| 15 | Inferno Scale | Scale override — mode, scale value, reference node |

**Note:** The article "20 Infernos" may count sub-features or internal operators not exposed via `addOperator`.

## 2. Event Compatibility

- Inferno operators work in **regular events** (standard `addEvent()`)
- No special `addInfernoEvent()` method exists
- Inferno and particle operators **can coexist** in the same event

## 3. New Non-Inferno Operators

| Operator | Status | Properties |
|---|---|---|
| Global | OK | `.affectEvents` (int), `.includeEventNames` (str), `.excludeEventNames` (str) |
| MAXScript | OK | `.mode` (int), `.filename` (str), `.script` (str) |
| Script | OK | (already existed in v1.x) |

## 4. SDF Shape Mode (PhysX Shape)

New properties on PhysX Shape operator:
- `.sdfCellRatio` : float
- `.sdfMinCellSize` : float
- `.hullMode` : integer (SDF is a new hull mode value)
- `.compoundHullMode` : integer

## 5. tyMeshBlend Modifier

```
tyMeshBlend() -- creates modifier instance
  .blendNormals : boolean
  .blendNormalsDistance : float
  .blendNormalsSmooth : integer
  .blendNormalsShow : boolean
  .blendNormalsShowLength : float
  .blendNormalsPhase : integer
  .blendNormalsNodes : maxObject array
  .transformMonitor : maxObject array
```

**Must be instanced** across all objects to blend.

## 6. Previously-Failed Operators Now Working in v2.0

ALL of these now return OK:
- Birth Burst, Birth Flow, Birth Fluid, Birth PRT, Birth Paint, Birth Skeleton, Birth Voxels, Birth VDB, Birth Terrain, Birth Intersections, Birth ForestPack
- Stop, Spread, Limiter, Integrate, Mass, Temporal Smooth
- Cluster Force, Flock, Fluid Force, Particle Force, Point Force, Surface Force, VDB Force
- Display Data, PhysX Break, PhysX Modify, PhysX Fluid, PhysX Switch
- Edge Fracture, Export VDB, Material ID, Object Bind, Particle Bind
- Boundary, Push In/Out, Time Test

**Still failing in v2.003:** Cache, Position, Look At, Attract, Collision Test

## 7. Inferno Operator Properties (Complete)

### Birth Inferno
```
.birthFrame : integer
.resetWithFlow : boolean
.gridSource : integer
.gridVDBFilename : string
.gridVDBDensity : boolean
.gridVDBDensityName : string
.gridVDBTemperature : boolean
.gridVDBTemperatureName : string
.gridVDBTemperatureUnitsEnabled : boolean
.gridVDBTemperatureUnits : integer
.gridVDBColor : boolean
.gridVDBColorName : string
.gridVDBFuel : boolean
.gridVDBFuelName : string
.gridVDBVelocity : boolean
.gridVDBVelocityMode : integer
.gridVDBVelocityNameXYZ : string
.gridVDBVelocityNameX : string
.gridVDBVelocityNameY : string
.gridVDBVelocityNameZ : string
.gridVDBVelocityScale : float
.voxelSize : float
.halfPrecision : boolean
.advectionMode : integer
.traceVelocity : float
.conservation : float
.vorticity : float
.vorticityConstraintEnable : boolean
.vorticityConstraint : float
.vorticityConservationBias : float
.adaptiveVorticity : boolean
.temperatureUnits : integer
.temperatureBuoyancy : float
.temperatureBuoyancyRelativity : float
.temperatureCooling : float
.temperatureCoolingShrinkage : float
.temperatureFlux : float
.fuelBuoyancy : float
.color : color
.dissipation : float
.timeScale : float
.advectionCorrectionScalar : float
.advectionCorrectionVector : float
.dynamicTimeStep : boolean
.dynamicTimeStepMode : integer
.dynamicTimeStepThreshold : float
.dynamicTimeStepMaxSteps : integer
.dynamicTimeStepSteps : integer
.fuelIgnitionTemperatureNormalized : float
.fuelIgnitionTemperatureCelcius : float
.fuelIgnitionTemperatureFahrenheit : float
.fuelIgnitionTemperatureKelvin : float
.fuelBurnTemperatureNormalized : float
.fuelBurnTemperatureCelcius : float
.fuelBurnTemperatureFahrenheit : float
.fuelBurnTemperatureKelvin : float
.fuelPropagation : float
.fuelPressure : float
.fuelSmother : float
.fuelDissipation : float
.fuelSmokeDensity : float
.fuelSmokeColorEnable : boolean
.fuelSmokeColor : color
.adaptiveVelocity : boolean
.adaptiveVelocityThreshold : float
.adaptiveDensity : boolean
.adaptiveDensityThreshold : float
.adaptiveTemperature : boolean
.adaptiveTemperatureThresholdNormalized : float
.adaptiveTemperatureThresholdCelcius : float
.adaptiveTemperatureThresholdFahrenheit : float
.adaptiveTemperatureThresholdKelvin : float
.adaptiveFuel : boolean
.adaptiveFuelThreshold : float
.evaluationOrder : integer
.simulationScale : float
.maxVRAMEnabled : boolean
.maxVRAM : float
.sourceInitBuffer : integer
.continuousEmission : boolean
.multiGridConservation : boolean
.pcgConservation : boolean
.perceptualColorMixing : boolean
.advectionQuality : integer
.updateOnTimeChange : boolean
```

### Inferno Emitter
```
.timingInterval : integer
.timingIntervalStart : integer
.timingIntervalEnd : integer
[...timing props shared by most operators...]
.filtersEnable : boolean
.filtersOperation : integer
[...filter props shared by most operators...]
.includeThisFlow : boolean
.objectList : node array
.emitFrom : integer
.emissionQuality : integer
.emissionCondition : integer
.emissionThickness : float
.emissionThicknessMultiplier : float
.emissionThicknessRegion : integer
.emissionSoften : boolean
.emissionSoftenCurve : matrix3 array
.densityEnabled : boolean
.density : float
.densityEmitMode : integer
.temperatureEnabled : boolean
.temperatureNormalized : float
.temperatureCelcius : float
.temperatureFahrenheit : float
.temperatureKelvin : float
.temperatureEmitMode : integer
.temperatureRelativeToDensity : boolean
.fuelEnabled : boolean
.fuel : float
.fuelEmitMode : integer
.colorEnabled : boolean
.color : color
.colorEmitMode : integer
.pressureEnabled : boolean
.pressure : float
.motionEnabled : boolean
.motion : float
.normalsEnabled : boolean
.normals : float
.vectorEnabled : boolean
.vectorMode : integer
.vectorNode : node
.vectorMultiplier : float
.vectorX : float
.vectorY : float
.vectorZ : float
.velocityEmitMode : integer
.simulateSubsteps : boolean
.smoothNormals : boolean
.splitMeshElements : boolean
.splitParticles : boolean
.normalsPerturb : boolean
[...noise props...]
.meshConvexHull : boolean
.meshPush : boolean
.meshPushAmount : float
.meshWeld : boolean
.meshWeldThreshold : float
.matIDFilter : boolean
.matIDFilterList : string
.matIDFilterInvert : boolean
.vertexVelocityChannelEnable : boolean
.vertexVelocityChannel : integer
[...simulation/export group booleans...]
.particlePointEmission : boolean
.particlePointEmissionSurfaceAreaThreshold : float
.particlePointEmissionRadiusMultiplier : float
.particleMeshlessRadiusFromScale : boolean
.particleMeshlessRadiusMultiplier : float
```

### Inferno Bounds
```
.mode : integer
.includeList : node array
.excludeList : node array
.affectMode : integer
.frustumExpand : float
.includeStatic : boolean
.includeStaticXMin/XMax/YMin/YMax/ZMin/ZMax : float
.includeStaticShow : boolean
.includeStaticShowPreview : boolean
.includeOperation : integer
.excludeStatic : boolean
.excludeStaticXMin/XMax/YMin/YMax/ZMin/ZMax : float
.excludeStaticShow : boolean
.excludeStaticShowPreview : boolean
```

### Inferno Display
```
.colorUI : integer
.showVolume : boolean
.volumeDisplayMode : integer
.temperatureDisplayMinNormalized/Celcius/Fahrenheit/Kelvin : float
.temperatureDisplayMaxNormalized/Celcius/Fahrenheit/Kelvin : float
.volumeMode : integer
.cameraStepSize : float
.precision16 : boolean
.raymarch : boolean
.randomRayOffset : boolean
.adaptiveDegradation : boolean
.volumeToneMapping : integer
.volumeGammaCorrection : boolean
.motionBlurMode : boolean
.motionBlurShutterSpeed : float
.motionBlurMaxSamples : integer
.densitySamplingMode : integer
.smokeFormat : integer
.smokeOpacity : float
.smokePhaseAlgorithm : integer
.smokePhaseMode : integer
.smokePhase : float
.smokePhaseIntensity : float
.smokeRelativeToTemperature : boolean
.smokeRelativeToTemperatureMin/MaxNormalized/Celcius/Fahrenheit/Kelvin : float
.smokeRelativeToTemperatureCurve : matrix3 array
.smokeOverrideColor : boolean
.smokeOverrideColorColor : color
.smokeAbsorption : boolean
.smokeAbsorptionGradient : matrix3 array
.smokeAbsorptionIntensity : float
.showSmoke : boolean
.showFire : boolean
.temperatureSamplingMode : integer
.fireTemperatureMinNormalized/Celcius/Fahrenheit/Kelvin : float
.fireTemperatureMaxNormalized/Celcius/Fahrenheit/Kelvin : float
.fireColorGradient : matrix3 array
.fireColorShifting : boolean
.fireColorShiftingHue : float
.fireColorShiftingHueCurve : matrix3 array
.fireColorShiftingHueCurveScale : float
.fireColorNoiseStrength : float
.fireColorNoiseScale : float
.fireColorIntensity : float
.fireOpacityCurve : matrix3 array
.fireOpacityNoiseStrength : float
.fireOpacityNoiseScale : float
.fireOpacityIntensity : float
.fireOpacityExponent : float
.fireCreaseMasking : boolean
.fireCreaseMaskingDepth : float
.fireCreaseMaskingWidth : float
.fireLuminanceMasking : boolean
.fireLuminanceMaskingMin : float
.fireLuminanceMaskingMax : float
.fireLuminanceMaskingCurve : matrix3 array
.fireOcclusionMasking : boolean
.fireOcclusionMaskingMin : float
.fireOcclusionMaskingMax : float
.fireOcclusionMaskingCurve : matrix3 array
.showFuel : boolean
.fuelOpacity : float
.fuelColor : color
.showIntersection : boolean
.intersectionNode : node
.sceneScale : float
.overallOpacity : float
.temperatureBlur : float
.aoFormat : integer
.aoStrength : float
.aoDistance : float
.aoSamples : integer
.aoSteps : integer
.lightMode : integer
.lightNode : node
.lightColor : color
.lightIntensity : float
.ambientStrength : float
.ambientColor : color
.shadowMode : integer
.shadowStrength : float
.shadowStepSize : float
.shadowStepSizeAdaptive : boolean
.showVelocityStreamlines : boolean
.velocityStreamlineSpacing : integer
.velocityStreamlineLengthMultiplier : float
.showSparseCubes : boolean
.deallocateRender : boolean
.glowEnable : boolean
.glowScale : float
.glowIntensity : float
.glowTint : color
.glowClampEnable : boolean
.glowClamp : float
.glowThreshold : float
.glowThresholdFalloff : float
.showSampler : boolean
.samplerNode : node
```

### Inferno Collider
```
.includeThisFlow : boolean
.objectList : node array
.emitFrom : integer
.emissionThickness : float
.motion : float
.eraseDensityEnabled : boolean
.eraseTemperatureEnabled : boolean
.eraseFuelEnabled : boolean
.eraseColorEnabled : boolean
.builtinGround : boolean
.builtinGroundHeight : float
.builtinGroundShow : boolean
.builtinGroundShowPreview : boolean
.simulateSubsteps : boolean
.splitMeshElements : boolean
.splitParticles : boolean
.meshConvexHull : boolean
.meshWeld : boolean
.meshWeldThreshold : float
[...matID filter, vertex velocity, simulation/export groups...]
```

### Inferno Color
```
.relativeToDensity : boolean
.relativeToDensityMin/Max : float
.relativeToDensityCurve : matrix3 array
.relativeToTemperature : boolean
.relativeToTemperatureMin/MaxNormalized/Celcius/Fahrenheit/Kelvin : float
.relativeToTemperatureCurve : matrix3 array
.relativeToVelocity : boolean
.relativeToVelocityMin/Max : float
.relativeToVelocityCurve : matrix3 array
.colorMode : integer
.color : color
.gradient : matrix3 array
.colorRelativeToDensity/Temperature/Velocity : boolean (+ min/max/curve)
.interpolationFullOnEmission : boolean
.interpolation : float
```

### Inferno Spawn
```
.gridSource : integer
.flowNode : node
.rate : float
.rateCubeSize : float
.spawnMax : integer
.relativeToDensity : boolean (+ min/max/curve)
.relativeToTemperature : boolean (+ min/max/curve in all unit variants)
.relativeToVelocity : boolean (+ min/max/curve)
.seed : integer
.seedByTime : boolean
```

### Inferno Properties
```
[...filters...]
[...timing...]
.testActionMode : integer
.testActionSaveAll : boolean
.testActionSaveAllFloatChannel : string
.testActionSaveTrue : boolean
.testActionSaveTrueFloatChannel : string
.testActionSaveAge : boolean
.testActionSaveAgeMode : integer
.gridSource : integer
.flowNode : node
.densityFloat : boolean
.densityFloatChannel : string
.colorMapChannel : boolean
.colorMapChannelChannel : integer
.colorVector : boolean
.colorVectorChannel : string
.colorFire : boolean
.colorFireIntensity : float
.temperatureFloat : boolean
.temperatureFloatChannel : string
.velocityVector : boolean
.velocityVectorChannel : string
.velocityInherit : boolean
.velocityInheritValue : float
.velocityTimeScale : boolean
.velocityInheritVariation : float
.velocityInheritMode : integer
.velocityInheritOperation : integer
.velocityInheritInfluenceX/Y/Z : boolean
.velocityInheritSimulateSubsteps : boolean
.relativeToPropertyMode : integer
.relativeToPropertyFloatChannel : string
.relativeToPropertyThreshold/Min/Max/Exponent : float
.relativeToPropertyInvert : boolean
.insideMode : integer
.seed : integer
```

### Inferno Recall
```
.recallMode : integer
.filenameMode : integer
.filename : string
.multiFrameBuffering : boolean
.ramCacheLocation : integer
.ramCacheSubframes : boolean
.conserveVRAM : boolean
.ramCacheCompressModePerChannel : boolean
.ramCacheCompressModeAll/Density/Temperature/Fuel/Color/Velocity : integer
.ramCacheVQVDBScalarModel : string
.ramCacheVQVDBVectorModel : string
.ramCacheMaxRAM : float
.ramCacheAutoClear : boolean
.gridDensity/Color/Fuel/Temperature : boolean (+ Name strings)
.gridTemperatureUnitsEnabled : boolean
.gridTemperatureUnits : integer
.gridVelocity : boolean
.gridVelocityMode : integer
.gridVelocityNameXYZ/X/Y/Z : string
.gridVelocityScale : float
.gridEmitterVelocity : boolean (+ mode/names)
.gridFlags : boolean
.gridFlagsName : string
.maskingEnable : boolean
.maskingClearDensity/Temperature : boolean (+ Amount)
.retimingAffectVelocity : boolean
.retimingInterpolation : boolean
.retimingOverrideVelDT : boolean (+ Value)
.retimingVelocityInterpolation : boolean
.retimingConserveVRAM : boolean
.upresEnable : boolean
.upresDensity/Temperature/Fuel : boolean
.upresModel : string
.upresAdaptive : boolean
.upresBatching : boolean
.upresFP16 : boolean
.upresConserveVRAM : boolean
.upresOverlapBlending : boolean
.upresPadding : integer
.upresCameraDistanceFallback : boolean
.upresCameraDistanceFallbackCamera : node
.upresCameraDistanceFallbackDensity/Temperature/Fuel : boolean (+ Distance)
.sharpenEnable : boolean
.sharpenDensity/Temperature : boolean (+ Sigma/Strength)
.reverseAdvectionDensity/Temperature : boolean (+ Strength)
```

### Export Inferno
```
.mode : integer
.filenameSolver : string
.filenameCache : string
.filenameCacheTYV : string
.tyvExportSubframes : boolean
.gridSource : integer
.gridFormat : integer
.coordinates : integer
.gridDensity/Color/Fuel/Temperature : boolean (+ Name)
.gridTemperatureUnitsEnabled : boolean
.gridTemperatureUnits : integer
.gridTemperatureBakeBlur : boolean
.gridVelocity : boolean
.gridVelocityName : string
.gridVelocityMaskWithDensity : boolean
.gridEmitterVelocity : boolean
.gridEmitterVelocityName : string
.bakePostProcessing : boolean
.updateDisplay : boolean
.frameStart : integer
.frameEnd : integer
.denseFilename : string
.denseFrames : string
.flipbookFilename : string
.flipbookCamera : node
.flipbookFrameStart/End : integer
.flipbookCellAspectRatio : float
.flipbookResolutionX/Y : integer
.flipbookGlow : integer
.flipbookProgressive : integer
.flipbookProgressiveIterations : integer
```

### Inferno Force
```
.affectMagnitude : float
.conservationBias : float
.relativeToDensity/Temperature/Velocity : boolean (+ min/max/curve)
.forceList : node array
.gravityStrength : float
.windX/Y/Z : float
.windStrength : float
.constrainDrag : boolean
.dragX/Y/Z : float
.noisePressure : boolean
[...noise slot 1 props (noiseMode, noiseStrength, etc.)...]
[...noise slot 2 props (noise2Mode, noise2Strength, etc.)...]
.noiseSpeed : float
.noise2Speed : float
```

### Inferno Temperature
```
.relativeToDensity/Temperature/Velocity : boolean (+ min/max/curve)
.temperatureCooling : float
[...noise props...]
.noiseSpeed : float
```

### Inferno Density
```
.relativeToDensity/Temperature/Velocity : boolean (+ min/max/curve)
.densityDissipation : float
.emissionByTemperature : boolean
.emissionByTemperatureDensity : float
.emissionByTemperatureColorEnabled : boolean
.emissionByTemperatureColor : color
.emissionByTemperatureMin/MaxNormalized/Celcius/Fahrenheit/Kelvin : float
.emissionByTemperatureCurve : matrix3 array
[...noise props...]
.noiseSpeed : float
```

### Inferno Vorticity
```
.relativeToDensity/Temperature/Velocity : boolean (+ min/max/curve)
.vorticityMode : integer
.vorticity : float
.vorticityConstraintEnable : boolean
.vorticityConstraint : float
.vorticityConservationBias : float
.adaptiveVorticity : boolean
.adaptiveVorticityOverride : boolean
.adaptiveVorticityFrontPlumeBlend : float
.adaptiveVorticityFrontPlumeMult : float
.adaptiveVorticityFrontPlumeLimit : float
.adaptiveVorticityBackPlumeMult : float
.adaptiveVorticityBackPlumeLimit : float
[...noise props...]
.noiseSpeed : float
```

### Inferno Scale
```
.mode : integer
.scale : float
.node : node
```

## 8. Volume MAXScript API (Documented)

```maxscript
[obj].updateVolumes()                           -- prepare volume data for sampling
[obj].getVolumeScalar [pos] type                -- type: 0=density, 1=fuel, 2=temperature
[obj].getVolumeVector [pos] type                -- type: 0=color, 1=velocity
[obj].convertVolumeTemperature temp units        -- units: 1=celsius, 2=fahrenheit, 3=kelvin
[obj].releaseVolumes()                          -- free cached volume data
```

## 9. Common Property Patterns

Most Inferno operators share these property groups:
- **Timing:** `.timingInterval`, `.timingIntervalStart/End`, `.timingPostStepNew/PhysX`, etc.
- **Filters:** `.filtersEnable`, `.filterPropertyType`, `.filterTestCondition`, simulation/export groups
- **Relative curves:** `.relativeToDensity/Temperature/Velocity` + min/max/curve variants
- **Temperature units:** Properties come in 4 variants: `Normalized`, `Celcius`, `Fahrenheit`, `Kelvin`
- **Noise:** Full noise configuration with mode, fractal, cellular, octaves, seed, etc.
