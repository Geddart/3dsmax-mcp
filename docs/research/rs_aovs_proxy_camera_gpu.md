# Redshift Introspection: AOVs, Proxy, Camera, GPU, Lights, Mesh Parameters

**Date:** 2026-03-03
**Redshift Version:** 2026.3.1 (version array: `#(2026, 3, 1)`)
**Source:** Live introspection via `execute_maxscript` MCP tool in 3ds Max

---

## Table of Contents

1. [Render Elements (AOVs)](#1-render-elements-aovs)
2. [Proxy Objects](#2-proxy-objects)
3. [Camera Overrides](#3-camera-overrides)
4. [GPU API](#4-gpu-api)
5. [Redshift Interface Namespace](#5-redshift-interface-namespace)
6. [Light Types](#6-light-types)
7. [Redshift Mesh Parameters Modifier](#7-redshift-mesh-parameters-modifier)
8. [Redshift Renderer Properties](#8-redshift-renderer-properties)
9. [All Redshift Classes (showClass)](#9-all-redshift-classes)

---

## 1. Render Elements (AOVs)

### Common Properties Shared by Most AOVs

Most RS render elements share these base properties:
- `.enabled` : boolean
- `.filterOn` : boolean
- `.elementName` : string
- `.bitmap` : bitmap

### 1.1 RS_Beauty

```
.enabled : boolean
.filterOn : boolean
.elementName : string
.bitmap : bitmap
.applyColorProcessing : boolean
.denoiseOn : boolean
.globalAOV : integer
.allLightGroups : boolean
.lightGroupList : string array
```

### 1.2 RS_Diffuse_Lighting

```
.enabled : boolean
.filterOn : boolean
.elementName : string
.bitmap : bitmap
.applyColorProcessing : boolean
.denoiseOn : boolean
.secondaryRayVisibility : integer
.globalAOV : integer
.allLightGroups : boolean
.lightGroupList : string array
```

### 1.3 RS_Specular_Lighting

```
.enabled : boolean
.filterOn : boolean
.elementName : string
.bitmap : bitmap
.applyColorProcessing : boolean
.denoiseOn : boolean
.secondaryRayVisibility : integer
.globalAOV : integer
.allLightGroups : boolean
.lightGroupList : string array
```

### 1.4 RS_Reflections

```
.enabled : boolean
.filterOn : boolean
.elementName : string
.bitmap : bitmap
.applyColorProcessing : boolean
.denoiseOn : boolean
.secondaryRayVisibility : integer
.globalAOV : integer
.allLightGroups : boolean
.lightGroupList : string array
```

### 1.5 RS_Refractions

```
.enabled : boolean
.filterOn : boolean
.elementName : string
.bitmap : bitmap
.applyColorProcessing : boolean
.denoiseOn : boolean
.globalAOV : integer
.allLightGroups : boolean
.lightGroupList : string array
```

Note: RS_Refractions does NOT have `.secondaryRayVisibility`.

### 1.6 RS_Global_Illumination

```
.enabled : boolean
.filterOn : boolean
.elementName : string
.bitmap : bitmap
.applyColorProcessing : boolean
.denoiseOn : boolean
.secondaryRayVisibility : integer
.globalAOV : integer
.allLightGroups : boolean
.lightGroupList : string array
```

### 1.7 RS_Sub_Surface_Scatter

```
.enabled : boolean
.filterOn : boolean
.elementName : string
.bitmap : bitmap
.applyColorProcessing : boolean
.denoiseOn : boolean
.secondaryRayVisibility : integer
.globalAOV : integer
.allLightGroups : boolean
.lightGroupList : string array
```

### 1.8 RS_Emission

```
.enabled : boolean
.filterOn : boolean
.elementName : string
.bitmap : bitmap
.applyColorProcessing : boolean
.denoiseOn : boolean
.secondaryRayVisibility : integer
.globalAOV : integer
.allLightGroups : boolean
.lightGroupList : string array
```

### 1.9 RS_Caustics

```
.enabled : boolean
.filterOn : boolean
.elementName : string
.bitmap : bitmap
.applyColorProcessing : boolean
.denoiseOn : boolean
```

Minimal -- no light groups, no secondaryRayVisibility.

### 1.10 RS_Depth

```
.enabled : boolean
.filterOn : boolean
.elementName : string
.bitmap : bitmap
.filterMode : integer
.depthMode : integer
.useCameraNearFar : boolean
.depthMin : worldUnits
.depthMax : worldUnits
.setEnvironmentRaysToBlack : boolean
```

### 1.11 RS_Normals

```
.enabled : boolean
.filterOn : boolean
.elementName : string
.bitmap : bitmap
```

Minimal -- base properties only.

### 1.12 RS_World_Position

```
.enabled : boolean
.filterOn : boolean
.elementName : string
.bitmap : bitmap
.filterMode : integer
.scaleX : float
.scaleY : float
.scaleZ : float
.setEnvironmentRaysToBlack : boolean
```

### 1.13 RS_Motion_Vectors

```
.enabled : boolean
.filterOn : boolean
.elementName : string
.bitmap : bitmap
.outputRawVectors : boolean
.noClamp : boolean
.maxMotion : integer
.imageOutputMin : float
.imageOutputMax : float
.filtering : boolean
```

### 1.14 RS_Puzzle_Matte

```
.enabled : boolean
.filterOn : boolean
.elementName : string
.bitmap : bitmap
.puzzleMatteMode : integer
.redID : integer
.greenID : integer
.blueID : integer
.reflectRefractIDs : boolean
```

### 1.15 RS_Cryptomatte

```
.filterOn : boolean
.elementName : string
.bitmap : bitmap
.enabled : boolean
.cryptomatteIDType : integer
.cryptomatteUserAttribute : string
.cryptomatteDepth : integer
```

Note: `.enabled` appears after `.bitmap` (non-standard ordering).

### 1.16 RS_Custom

```
.enabled : boolean
.filterOn : boolean
.elementName : string
.bitmap : bitmap
.defaultShaderMap : texturemap
.applyColorProcessing : boolean
.denoiseOn : boolean
.secondaryRayVisibility : integer
```

Note: Has `.defaultShaderMap` for custom shader assignment. No light group support.

### 1.17 RS_Object_ID

```
.enabled : boolean
.filterOn : boolean
.elementName : string
.bitmap : bitmap
```

Minimal -- base properties only.

### 1.18 RS_Matte

```
.enabled : boolean
.filterOn : boolean
.elementName : string
.bitmap : bitmap
.denoiseOn : boolean
```

### 1.19 RS_Ambient_Occlusion

```
.enabled : boolean
.filterOn : boolean
.elementName : string
.bitmap : bitmap
.numSamples : integer
.bright : color
.bright_map : texturemap
.bright_mapenable : boolean
.dark : color
.dark_map : texturemap
.dark_mapenable : boolean
.spread : float
.spread_map : texturemap
.spread_mapenable : boolean
.fallOff : float
.fallOff_map : texturemap
.fallOff_mapenable : boolean
.maxDistance : worldUnits
.maxDistance_map : texturemap
.maxDistance_mapenable : boolean
.applyColorProcessing : boolean
.denoiseOn : boolean
.secondaryRayVisibility : integer
```

Most complex AOV -- has its own sampling, color, and distance parameters with per-parameter map slots.

### 1.20 RS_Background

```
.enabled : boolean
.filterOn : boolean
.elementName : string
.bitmap : bitmap
.applyColorProcessing : boolean
.denoiseOn : boolean
```

### 1.21 RS_Shadows

```
.enabled : boolean
.filterOn : boolean
.elementName : string
.bitmap : bitmap
.applyColorProcessing : boolean
.denoiseOn : boolean
```

### 1.22 RS_Volume_Lighting

```
.enabled : boolean
.filterOn : boolean
.elementName : string
.bitmap : bitmap
.applyColorProcessing : boolean
.denoiseOn : boolean
.secondaryRayVisibility : integer
.globalAOV : integer
.allLightGroups : boolean
.lightGroupList : string array
```

### Additional Render Elements (Discovered via showClass)

#### RS_Diffuse_Filter

```
.enabled : boolean
.filterOn : boolean
.elementName : string
.bitmap : bitmap
```

#### RS_Reflections_Filter

```
.enabled : boolean
.filterOn : boolean
.elementName : string
.bitmap : bitmap
```

#### RS_Reflections_Raw

```
.enabled : boolean
.filterOn : boolean
.elementName : string
.bitmap : bitmap
.applyColorProcessing : boolean
.denoiseOn : boolean
```

#### RS_Refractions_Filter

```
.enabled : boolean
.filterOn : boolean
.elementName : string
.bitmap : bitmap
```

#### RS_Refractions_Raw

```
.enabled : boolean
.filterOn : boolean
.elementName : string
.bitmap : bitmap
.applyColorProcessing : boolean
.denoiseOn : boolean
```

#### RS_Diffuse_Lighting_Raw

```
.enabled : boolean
.filterOn : boolean
.elementName : string
.bitmap : bitmap
.applyColorProcessing : boolean
.denoiseOn : boolean
```

#### RS_Global_Illumination_Raw

```
.enabled : boolean
.filterOn : boolean
.elementName : string
.bitmap : bitmap
.applyColorProcessing : boolean
.denoiseOn : boolean
```

#### RS_Sub_Surface_Scatter_Raw

```
.enabled : boolean
.filterOn : boolean
.elementName : string
.bitmap : bitmap
.applyColorProcessing : boolean
.denoiseOn : boolean
```

#### RS_Caustics_Raw

```
.enabled : boolean
.filterOn : boolean
.elementName : string
.bitmap : bitmap
.applyColorProcessing : boolean
.denoiseOn : boolean
```

#### RS_Translucency_Filter

```
.enabled : boolean
.filterOn : boolean
.elementName : string
.bitmap : bitmap
```

#### RS_Translucency_Lighting_Raw

```
.enabled : boolean
.filterOn : boolean
.elementName : string
.bitmap : bitmap
.applyColorProcessing : boolean
.denoiseOn : boolean
```

#### RS_Translucency_GI_Raw

```
.enabled : boolean
.filterOn : boolean
.elementName : string
.bitmap : bitmap
.applyColorProcessing : boolean
.denoiseOn : boolean
```

#### RS_Total_Diffuse_Lighting_Raw

```
.enabled : boolean
.filterOn : boolean
.elementName : string
.bitmap : bitmap
.applyColorProcessing : boolean
.denoiseOn : boolean
```

#### RS_Total_Translucency_Lighting_Raw

```
.enabled : boolean
.filterOn : boolean
.elementName : string
.bitmap : bitmap
.applyColorProcessing : boolean
.denoiseOn : boolean
```

#### RS_Volume_Fog_Emission

```
.enabled : boolean
.filterOn : boolean
.elementName : string
.bitmap : bitmap
.denoiseOn : boolean
```

#### RS_Volume_Fog_Tint

```
.enabled : boolean
.filterOn : boolean
.elementName : string
.bitmap : bitmap
```

#### RS_Volume_Depth

```
.enabled : boolean
.filterOn : boolean
.elementName : string
.bitmap : bitmap
.filterMode : integer
.depthMode : integer
.useCameraNearFar : boolean
.depthMin : worldUnits
.depthMax : worldUnits
.setEnvironmentRaysToBlack : boolean
```

Same structure as RS_Depth.

#### RS_Object_Space_Positions

```
.enabled : boolean
.filterOn : boolean
.elementName : string
.bitmap : bitmap
.setEnvironmentRaysToBlack : boolean
```

#### RS_Object_Space_Bump_Normals

```
.enabled : boolean
.filterOn : boolean
.elementName : string
.bitmap : bitmap
```

#### RS_Bump_Normals

```
.enabled : boolean
.filterOn : boolean
.elementName : string
.bitmap : bitmap
```

#### RS_Ambient_Occlusion__Legacy

```
.enabled : boolean
.filterOn : boolean
.elementName : string
.bitmap : bitmap
```

Minimal -- the legacy version has no configurable parameters (unlike the current RS_Ambient_Occlusion).

### AOV Property Pattern Summary

| Property Group | AOVs that have it |
|---|---|
| Base only (enabled, filterOn, elementName, bitmap) | RS_Normals, RS_Object_ID, RS_Diffuse_Filter, RS_Reflections_Filter, RS_Refractions_Filter, RS_Translucency_Filter, RS_Volume_Fog_Tint, RS_Object_Space_Bump_Normals, RS_Bump_Normals, RS_Ambient_Occlusion__Legacy |
| + denoiseOn | RS_Matte, RS_Volume_Fog_Emission |
| + applyColorProcessing + denoiseOn | RS_Caustics, RS_Background, RS_Shadows, RS_Reflections_Raw, RS_Refractions_Raw, RS_Diffuse_Lighting_Raw, RS_Global_Illumination_Raw, RS_Sub_Surface_Scatter_Raw, RS_Caustics_Raw, RS_Translucency_Lighting_Raw, RS_Translucency_GI_Raw, RS_Total_Diffuse_Lighting_Raw, RS_Total_Translucency_Lighting_Raw |
| + applyColorProcessing + denoiseOn + globalAOV + lightGroups | RS_Beauty (no secondaryRayVisibility) |
| + applyColorProcessing + denoiseOn + secondaryRayVisibility + globalAOV + lightGroups | RS_Diffuse_Lighting, RS_Specular_Lighting, RS_Reflections, RS_Global_Illumination, RS_Sub_Surface_Scatter, RS_Emission, RS_Volume_Lighting |
| + applyColorProcessing + denoiseOn + globalAOV + lightGroups (no secondaryRayVisibility) | RS_Refractions |
| Specialized | RS_Depth, RS_World_Position, RS_Motion_Vectors, RS_Puzzle_Matte, RS_Cryptomatte, RS_Custom, RS_Ambient_Occlusion |

---

## 2. Proxy Objects

### RedshiftProxy (confirmed working class name)

- **Class:** `RedshiftProxy`
- **SuperClass:** `GeometryClass`
- **Internal classOf:** `proxy` (the 3ds Max generic proxy class)

```
.gizmoscale : float
.file : filename
.displaymode : integer
.linkedmesh : node
.displaypct : percent
.issequence : boolean
.startframe : integer
.endframe : integer
.pattern : string
.frameoffset : integer
.outofrangemode : integer
.materialmode : integer
.namematchprefix : string
.overrideobjectid : boolean
.overridevisibility : boolean
.overridetessdisp : boolean
.overridetracesets : boolean
.overrideuserdata : boolean
.overrideunits : boolean
.customUnitScale : float
.customUnit : integer
```

### Other proxy class names tested

| Name | Result |
|---|---|
| `rsProxy` | Exists as a `Primitive` (function), requires 9 arguments -- NOT a geometry class |
| `RS_Proxy` | undefined |
| `Redshift_Proxy` | undefined |
| `RedshiftProxyMesh` | undefined |

### showClass "*proxy*" results

```
Forest_Proxy(Forest Proxy) : GeometryClass
BitmapProxy_Config_Dialog(BitmapProxy Config Dialog) : UserDataTypeClass
Input_Proxy(Input Proxy) : ReferenceTarget
BitmapProxyManagerImp_Latch(BitmapProxyManagerImp Latch) : UserDataTypeClass
proxy : GeometryClass
VRayProxy : GeometryClass
```

Note: `RedshiftProxy` does not appear in `showClass "*proxy*"` because its MAXScript class name is just `proxy` internally. Creating via `RedshiftProxy()` is the correct approach.

### showClass "*Redshift*Mesh*" results

```
Redshift_Mesh_Parameters(Redshift Mesh Parameters) : modifier
```

---

## 3. Camera Overrides

### 3.1 Redshift_Camera_Attributes (modifier)

Main camera modifier applied to cameras for RS-specific controls.

```
.cameraType : integer
.fisheyeScaleH : float
.fisheyeScaleV : float
.fisheyeFov : float
.cylindricalOrthographic : boolean
.cylindricalFovH : float
.cylindricalFovV : float
.cylindricalOrthoHeight : float
.stereoSphericalMode : integer
.stereoSphericalSeparation : worldUnits
.stereoSphericalFocusEnable : boolean
.stereoSphericalFocusDeriveFromCamera : boolean
.stereoSphericalFocusDistance : worldUnits
.stereoSphericalHorizontalFov : float
.stereoSphericalVerticalFov : float
.optical : maxObject        --> RS_Optical_Params
.background : maxObject     --> RS_Backplate_Params
.lut : maxObject             --> RS_LUT_Params
.colorControl : maxObject    --> RS_Color_Control_Params
.bloom : maxObject           --> RS_Bloom_Params
.flare : maxObject           --> RS_Flare_Params
.streak : maxObject          --> RS_Streak_Params
```

#### RS_Optical_Params (sub-object of Redshift_Camera_Attributes.optical)

```
.exposureType : integer
.exposure : float
.iso : float
.whitepoint : color
.vignetting : float
.toneMapEnabled : boolean
.highlights : float
.desaturateHighlights : boolean
.blacks : float
.blacksThreshold : float
.saturation : float
.focusDeriveFromCamera : boolean
.focusDistance : worldUnits
.focusObject : node
.focusObjectOffset : worldUnits
.fStop : float
.bokeh : boolean
.bokehShape : integer
.sphericalAberration : float
.bokehBlades : integer
.bokehAngle : float
.bokehImage : bitmap
.bokehImage_filename : filename
.bokehNormalization : integer
.motionBlur : integer
.cameraMotion : boolean
.shutterType : integer
.shutterTime : float
.shutterAngle : angle
.shutterTimeOffset : float
.shutterAngleOffset : angle
.shutterEfficiency : float
.distortion : boolean
.distortionImage : bitmap
.distortionImage_filename : filename
```

#### RS_Backplate_Params (sub-object of Redshift_Camera_Attributes.background)

```
.enableMode : integer
.enabled : boolean
.renderMode : integer
.affectedByBentRays : boolean
.color : color
.image : bitmap
.image_filename : filename
.image_colorSpace : string
.imageAlpha : boolean
.frame : integer
.offsetX : float
.offsetY : float
.gamma : float
.exposure : float
.hue : float
.saturation : float
.exposureCompensation : boolean
```

#### RS_LUT_Params (sub-object of Redshift_Camera_Attributes.lut)

```
.overrideGlobal : boolean
.enabled : boolean
.filename : filename
.apply_before_color_management : integer
.log_input : integer
.strength : float
```

#### RS_Color_Control_Params (sub-object of Redshift_Camera_Attributes.colorControl)

```
.overrideGlobal : boolean
.enabled : boolean
.exposure : float
.contrast : float
.curve_red : point3 array
.curve_green : point3 array
.curve_blue : point3 array
.curve_rgb : point3 array
```

#### RS_Bloom_Params (sub-object of Redshift_Camera_Attributes.bloom)

```
.overrideGlobal : boolean
.enabled : boolean
.threshold : float
.softness : float
.intensity : float
.tint0 : color
.tint1 : color
.tint2 : color
.tint3 : color
.tint4 : color
```

#### RS_Flare_Params (sub-object of Redshift_Camera_Attributes.flare)

```
.overrideGlobal : boolean
.enabled : boolean
.threshold : float
.softness : float
.chromatic : float
.size : float
.halo : float
.intensity : float
.tint0 : color
.tint1 : color
.tint2 : color
.tint3 : color
.tint4 : color
.tint5 : color
```

#### RS_Streak_Params (sub-object of Redshift_Camera_Attributes.streak)

```
.overrideGlobal : boolean
.enabled : boolean
.threshold : float
.softness : float
.tail : float
.number : integer
.angle : integer
.intensity : float
```

### 3.2 Redshift_Camera_Effects (modifier)

Override modifier -- enables per-camera post-effect overrides.

```
.bokeh : maxObject                         --> undefined until assigned (Redshift_Bokeh render effect)
.lens_distortion : maxObject               --> undefined until assigned (Redshift_Lens_Distortion)
.lut : maxObject                           --> RS_LUT_Params
.color_control : maxObject                 --> RS_Color_Control_Params
.photographic_exposure : maxObject         --> undefined until assigned
.bloom : maxObject                         --> RS_Bloom_Params
.flare : maxObject                         --> RS_Flare_Params
.streak : maxObject                        --> RS_Streak_Params
.override_bokeh : boolean
.override_lens_distortion : boolean
.override_bloom : boolean
.override_flare : boolean
.override_streak : boolean
.override_photographic_exposure : boolean
.override_lut : boolean
.override_color_control : boolean
```

### 3.3 Redshift_Camera_Type (CustAttrib)

```
.on : integer
```

Minimal -- just an enable toggle (as integer, not boolean).

### 3.4 Redshift_Bokeh (renderEffect)

```
.enabled : boolean
.deriveFocusDistanceFromCamera : boolean
.focusDistance : worldUnits
.CoCRadius : float
.power : float
.aspect : float
.bladeCount : integer
.angle : float
.useImage : boolean
.imageNormalizationMode : integer
.image : bitmap
.image_filename : filename
```

### 3.5 Redshift_Volume_Scattering (atmospheric)

```
.tint : color
.scatteringAmount : float
.phase : float
.fogEmission : color
.fogApplyCameraExposureCompensation : boolean
.fogHeight : worldUnits
.fogHorizonBlur : float
.fogGroundPointX : float
.fogGroundPointY : float
.fogGroundPointZ : float
.fogGroundNormalX : float
.fogGroundNormalY : float
.fogGroundNormalZ : float
.environmentRayContributionScale : float
.cameraRayContributionScale : float
.reflectionRayContributionScale : float
.GIRayContributionScale : float
.TintMap : texturemap
.TintMapEnable : boolean
.environmentAlphaReplace : boolean
.viewingDistance : float
```

### 3.6 Redshift_Lens_Distortion (renderEffect)

```
.image : bitmap
.image_filename : filename
```

### 3.7 Redshift_Texture_Options (CustAttrib)

```
.mipBias : float
```

### 3.8 Redshift_Trace_Sets (CustAttrib)

No exposed properties (empty).

### 3.9 Non-creatable classes

The following are `ReferenceTarget` sub-objects that cannot be instantiated directly -- they must be accessed via their parent object:

- `RS_Physical_Camera_Params` -- "Not creatable"
- `RS_Post_Effects` -- "Not creatable"
- `RS_Bloom_Params` -- "Not creatable" (access via camera modifier sub-objects)
- `RS_Flare_Params` -- "Not creatable"
- `RS_Streak_Params` -- "Not creatable"
- `RS_Optical_Params` -- "Not creatable"
- `RS_LUT_Params` -- "Not creatable"
- `RS_Color_Control_Params` -- "Not creatable"
- `RS_Backplate_Params` -- "Not creatable"
- `RS_Color_Management_Params` -- "Not creatable"
- `RS_Curve_Params` -- "Not creatable"
- `Redshift_Photographic_Exposure` -- "Not creatable" (ToneOperator)

---

## 4. GPU API

### Direct GPU Functions

All three standard Redshift GPU functions are **undefined** in this version:

| Function | Result |
|---|---|
| `rsGetNumCudaDevices()` | undefined |
| `rsGetCudaDevices()` | undefined |
| `rsGetCudaDeviceName 0` | undefined |

These functions may have been removed or renamed in Redshift 2026.x. GPU selection is likely now handled through the renderer properties or the Redshift GUP.

### Renderer GPU-related properties

The `Redshift_Renderer` has the following GPU/memory-related properties:

```
.PercentageOfGPUMemoryToUse : integer
.GPUMemoryInactivityTimeout : integer
.IrradiancePointCloudGPUWorkingMemory : integer
.IrradianceCacheGPUWorkingMemory : integer
.PercentageOfFreeMemoryUsedForTextureCache : integer
.TextureCacheGPUWorkingMemory : integer
.RayReservedMemory : integer
.TextureCacheCPUWorkingMemory : integer
.AutomaticMemoryManagement : boolean
.NVLinkModeForVolumeGrids : enum
.NVLinkModeForGeometry : enum
.EnableOptiXRTOnSupportedGPUs : boolean
```

### Redshift_GUP

- Type: `GlobalUtilityPlugin`
- No exposed properties via `showProperties`
- No exposed interfaces via `showInterfaces`
- This is the background plugin that manages the Redshift connection to 3ds Max

---

## 5. Redshift Interface Namespace

### `redshift` (FPInterface)

Type: `Interface` (FPInterface / Value)

#### Properties

```
.version : integer array : Read       --> #(2026, 3, 1)
.versionString : string : Read        --> "2026.3.1"
.renderView : Interface : Read        --> rsRenderView interface
```

#### Methods

```
<boolean>checkVersion <integer>major <integer>minor <integer>build
<void>openRenderLog()
<void>openOnlineDocumentation()
<void>setNextPhysicalLightType <integer>type    -- range: 0 to 3
```

### `redshift.renderView` (rsRenderView interface)

#### Properties

```
.hwnd : HWND : Read
.visible : boolean : Read
.extended : boolean : Read
.freezeTessellation : boolean : Read|Write
.autoFreezeTessellation : boolean : Read|Write
.bucketIPR : boolean : Read|Write
.iprUndersampling : integer : Read|Write
.enable : boolean : Read|Write
```

#### Methods

```
<boolean>open()
<void>close()
<void>startIPR()
<void>stopIPR()
<void>refreshIPR()
<value>getBeauty()
```

---

## 6. Light Types

### 6.1 rsPhysicalLight

The main Redshift area/point light.

```
.excludeList : node array
.includeList : node array
.inclExclType : integer
.on : boolean
.width : worldUnits
.length : worldUnits
.type : integer
.targeted : boolean
.targetDistance : worldUnits
.unitsType : integer
.lumensperwatt : float
.opacity : float
.opacity_map : texturemap
.useAlpha : boolean
.intensity : float
.intensity_map : texturemap
.exposure : float
.decayType : integer
.falloffStart : worldUnits
.falloffStop : worldUnits
.colorMode : integer
.color : color
.color_map : texturemap
.temperature : float
.temperature_map : texturemap
.areashape : integer
.areavisible : boolean
.areabidirectional : boolean
.areanormalize : boolean
.areaspread : float
.areamesh : node
.spotconeangle : float
.spotConeFalloffAngle : float
.spotConeFalloffAngle_map : texturemap
.spotConeFalloffCurve : float
.spotConeShow : boolean
.aovLightGroup : string
.affectedbyrefraction : integer
.matteshadowilluminator : boolean
.indirectmaxtracedepth : integer
.areasamples : integer
.volumesamples : integer
.diffusescale : float
.reflectionscale : float
.transmissionscale : float
.singlescatteringscale : float
.multiplescatteringscale : float
.volumecontributionscale : float
.indirectscale : float
.toondiffusescale : float
.toonreflectionscale : float
.toonrimscale : float
.shadow : boolean
.shadowTransparency : float
.shadowTransparency_map : texturemap
.SAMPLINGOVERRIDES_shadowSamplesScale : float
.SAMPLINGOVERRIDES_numShadowSamples : integer
.softnessAffectsGobo : boolean
.vpshadowradius : worldUnits
.castCaustics : integer
.causticsOverrideRefractionShadows : boolean
.causticphotonmultiplier : float
.causticsNumPhotonsMultiplier : float
.legacyNonAreaLightIntensity : boolean
.legacySoftShadowTechnique : boolean
.legacySpreadIntensity : boolean
.legacyUVComputation : boolean
.cameraRayContributionScale : float
```

### 6.2 rsDomeLight

The HDR environment/dome light.

```
.excludeList : node array
.includeList : node array
.inclExclType : integer
.on : boolean
.multiplier : float
.tex0_exposure : float
.color : color
.tex0 : bitmap
.tex0_filename : filename
.tex0_colorSpace : string
.envType : integer
.horizontalflipenabled : boolean
.tex0_hue : float
.tex0_saturation : float
.tex0_gamma : float
.alphaReplaceEnable : boolean
.alphaReplaceValue : float
.aovLightGroup : string
.startTime : time
.playBackRate : float
.endCondition : integer
.preview_visibility : integer
.preview_resolution : integer
.preview_exposure : float
.imageseq_enable : boolean
.backPlateLegacyMode : boolean
.backPlateEnabled : boolean
.tex1 : bitmap
.tex1_filename : filename
.tex1_colorSpace : string
.backPlateAspect : integer
.applyExposureCompensation : boolean
.tex1_exposure : float
.tex1_hue : float
.tex1_saturation : float
.tex1_gamma : float
.affectedbyrefraction : integer
.indirectmaxtracedepth : integer
.areasamples : integer
.volumesamples : integer
.diffusescale : float
.reflectionscale : float
.transmissionscale : float
.singlescatteringscale : float
.multiplescatteringscale : float
.indirectscale : float
.volumecontributionscale : float
.toondiffusescale : float
.toonreflectionscale : float
.shadow : boolean
.shadowTransparency : float
.shadowTransparency_map : texturemap
.castCaustics : integer
.causticsOverrideRefractionShadows : boolean
.causticphotonmultiplier : float
.causticsNumPhotonsMultiplier : float
.cameraRayContributionScale : float
```

### 6.3 rsSunLight

Standalone sun (without sky).

```
.excludeList : node array
.includeList : node array
.inclExclType : integer
.on : boolean
.targeted : boolean
.targetDistance : worldUnits
.model : integer
.showGuide : boolean
.intensity : float
.intensity_map : texturemap
.useNonPhysicalIntensity : boolean
.sun_disk_scale : float
.redblueshift : float
.saturation : float
.tint : color
.saturation_affects_color_adjustments : boolean
.haze : float
.ozone : float
.horizon_height : float
.aovLightGroup : string
.diffusescale : float
.reflectionscale : float
.transmissionscale : float
.singlescatteringscale : float
.multiplescatteringscale : float
.indirectscale : float
.indirectmaxtracedepth : integer
.volumecontributionscale : float
.volumesamples : integer
.toondiffusescale : float
.toonreflectionscale : float
.toonrimscale : float
.SAMPLINGOVERRIDES_shadowSamplesScale : float
.SAMPLINGOVERRIDES_numShadowSamples : integer
.shadowTransparency : float
.vpshadowradius : worldUnits
.castCaustics : integer
.causticsOverrideRefractionShadows : boolean
.causticphotonmultiplier : float
.causticsNumPhotonsMultiplier : float
.legacySoftShadowTechnique : boolean
```

### 6.4 rsSunSkyLight

Combined sun + physical sky.

```
.excludeList : node array
.includeList : node array
.inclExclType : integer
.on : boolean
.targeted : boolean
.targetDistance : worldUnits
.intensity : float
.useNonPhysicalIntensity : boolean
.model : integer
.haze : float
.ozone : float
.horizon_height : float
.horizon_blur : float
.ground_color : color
.night_color : color
.redblueshift : float
.saturation : float
.saturation_affects_color_adjustments : boolean
.sun_disk_intensity : float
.sun_disk_scale : float
.sun_glow_intensity : float
.sun_tint : color
.alphaReplaceEnable : boolean
.alphaReplaceValue : float
.aovLightGroup : string
.affectedbyrefraction : integer
.indirectmaxtracedepth : integer
.areasamples : integer
.volumesamples : integer
.cameraRayContributionScale : float
.diffusescale : float
.reflectionscale : float
.transmissionscale : float
.singlescatteringscale : float
.multiplescatteringscale : float
.indirectscale : float
.volumecontributionscale : float
.toondiffusescale : float
.toonreflectionscale : float
.shadow : boolean
.shadowTransparency : float
.shadowTransparency_map : texturemap
.castCaustics : integer
.causticsOverrideRefractionShadows : boolean
.causticphotonmultiplier : float
.causticsNumPhotonsMultiplier : float
```

### 6.5 rsIESLight

IES profile-based light.

```
.excludeList : node array
.includeList : node array
.inclExclType : integer
.on : boolean
.profile : filename
.targeted : boolean
.targetDistance : worldUnits
.viewportScale : float
.multiplier : float
.multiplier_map : texturemap
.exposure : float
.colorMode : integer
.color : color
.color_map : texturemap
.temperature : float
.temperature_map : texturemap
.aovLightGroup : string
.matteshadowilluminator : boolean
.indirectmaxtracedepth : integer
.volumesamples : integer
.diffusescale : float
.reflectionscale : float
.transmissionscale : float
.singlescatteringscale : float
.multiplescatteringscale : float
.indirectscale : float
.volumecontributionscale : float
.toondiffusescale : float
.toonreflectionscale : float
.toonrimscale : float
.shadow : boolean
.shadowTransparency : float
.shadowTransparency_map : texturemap
.SAMPLINGOVERRIDES_shadowSamplesScale : float
.SAMPLINGOVERRIDES_numShadowSamples : integer
.softnessAffectsGobo : boolean
.castCaustics : integer
.causticsOverrideRefractionShadows : boolean
.causticphotonmultiplier : float
.causticsNumPhotonsMultiplier : float
.legacySoftShadowTechnique : boolean
.intensityMode : integer
.overrideValue : float
.overrideUnit : integer
.luminousPower : float
.maxCandela : float
```

### 6.6 rsPortalLight

Portal light for indoor scenes.

```
.excludeList : node array
.includeList : node array
.inclExclType : integer
.on : boolean
.width : worldUnits
.height : worldUnits
.areaspread : float
.targeted : boolean
.targetDistance : worldUnits
.multiplier : float
.multiplier_map : texturemap
.exposure : float
.tint_color : color
.tint_color_map : texturemap
.transparency : color
.transparency_map : texturemap
.environment_map : texturemap
.aovLightGroup : string
.affectedbyrefraction : integer
.indirectmaxtracedepth : integer
.volumesamples : integer
.diffusescale : float
.reflectionscale : float
.transmissionscale : float
.singlescatteringscale : float
.multiplescatteringscale : float
.indirectscale : float
.areasamples : integer
.volumecontributionscale : float
.toondiffusescale : float
.toonreflectionscale : float
.shadows : boolean
.shadowTransparency : float
.castCaustics : integer
.causticsOverrideRefractionShadows : boolean
.causticphotonmultiplier : float
.causticsNumPhotonsMultiplier : float
```

Note: rsPortalLight uses `.shadows` (plural) while other lights use `.shadow` (singular).

### Light Type Summary

| MAXScript Class | Display Name | Light Class | Key Features |
|---|---|---|---|
| `rsPhysicalLight` | Physical | light | Area shapes, spot cone, decay, most versatile |
| `rsDomeLight` | Dome | light | HDR environment, backplate, preview controls |
| `rsSunLight` | RS Sun | light | Standalone sun, atmosphere haze/ozone |
| `rsSunSkyLight` | RS Sun and Sky | light | Combined sun+sky, ground color, horizon |
| `rsIESLight` | IES | light | IES profiles, luminous power |
| `rsPortalLight` | Portal | light | Window portals, tint, transparency |

---

## 7. Redshift Mesh Parameters Modifier

Class: `Redshift_Mesh_Parameters` (modifier)

```
.enableSubdivision : boolean
.screenSpaceAdaptive : boolean
.doSmoothSubdivision : boolean
.doSmoothUVBoundaries : boolean
.minTessellationLength : float
.maxTessellationSubdivs : integer
.outOfFrustumTessellationFactor : float
.limitOutOfFrustumTessellation : boolean
.maxOutOfFrustumTessellationSubdivs : integer
.subdivisionRule : integer
.maxDisplacement : worldUnits
.displacementScale : float
.autoBumpMap : boolean
.triplanarUseFrame : boolean
.triplanarFrame : time
.triplanarNode : node
.displacementMode : integer
.displacementType : integer
.autoMaxDisplacement : boolean
.bakingResolution : integer
.smartBakingResolution : boolean
.displacementNormalInterpolation : integer
```

---

## 8. Redshift Renderer Properties

Full property list for `Redshift_Renderer` (RendererClass):

### Output Settings

```
.RedshiftFileOutput : boolean
.SeparateAovFiles : boolean
.SeparateLightGroupAovFiles : boolean
.OutputExrBitDepth : enum
.OutputExrCompression : enum
.OutputExrTiled : boolean
.OutputExrMultipart : boolean
.OutputExrAutocrop : boolean
```

### General

```
.ShowAdvancedSettings : boolean
.RenderHiddenLights : boolean
.RenderDefaultLights : boolean
.VerboseFileLog : boolean
.RenderViewEnable : boolean
.RenderViewLockToCamera : boolean
.FastPreprocessingMode : enum
```

### Rendering Engine

```
.RenderingEngine : enum
.OverscanMode : enum
.OverscanX : integer
.OverscanY : integer
.BlockRenderingOrder : enum
.BlockSize : enum
.ProgressiveRenderingEnabled : boolean
.ProgressiveRenderingNumPasses : integer
```

### Unified Sampling

```
.UnifiedMinSamples : integer
.UnifiedMaxSamples : integer
.UnifiedAdaptiveErrorThreshold : float
.UnifiedFilterType : enum
.UnifiedFilterSize : float
.UnifiedMaxSubsampleIntensity : float
.UnifiedMaxSecondaryRayIntensity : float
.UnifiedDebugDrawSamples : boolean
.UnifiedDisableDivision : boolean
.UnifiedRandomizePattern : boolean
```

### Motion Blur

```
.MotionBlurEnabled : boolean
.MotionBlurDeformationEnabled : boolean
.MotionBlurNumTransformationSteps : integer
.MotionBlurNumDeformationSteps : integer
.MotionBlurFrameDuration : float
.MotionBlurShutterStart : float
.MotionBlurShutterEnd : float
.MotionBlurShutterPosition : enum
.MotionBlurShutterEfficiencyType : enum
.MotionBlurShutterEfficiencyForTrapezoidal : float
.MotionBlurShutterType : enum
.MotionBlurShutterTime : float
.MotionBlurShutterTimeOffset : float
.MotionBlurShutterAngle : float
.MotionBlurShutterAngleOffset : float
```

### Denoising

```
.DenoiseEngine : enum
.DenoiseAovs : boolean
.DenoiseAutoCreateAovs : boolean
.DenoiseShowBuffersInRenderView : boolean
.DenoiseSaveBuffers : boolean
.DenoiseOverheadProgressive : float
.DenoiseOverheadBucket : float
.DenoiseAltusKC1 : float
.DenoiseAltusKC2 : float
.DenoiseAltusKC4 : float
.DenoiseAltusKF : float
.DenoiseOIDNQuality : enum
.Do8BitQuantizationAndDithering : boolean
```

### Trace Depth

```
.MaxTraceDepthReflection : integer
.MaxTraceDepthRefraction : integer
.MaxTraceDepthVolume : integer
.MaxTraceDepthCombined : integer
.MaxTraceDepthTransparency : integer
```

### Displacement / Tessellation

```
.GlobalDisplacementEnable : boolean
.DisplacementType : enum
.BakingResolution : enum
.AutoBumpEnabled : boolean
.DisplacementNormalInterpolation : enum
.TessellationEnable : boolean
.DisplacementEnable : boolean
```

### Hair

```
.MPWHairEnabled : boolean
.MPWHairAutoThreshold : boolean
.MPWHairThreshold : float
.MPWHairTraceDepth : integer
.HairTessellationMode : enum
```

### Russian Roulette / Cut-offs

```
.RussianRouletteImportanceThreshold : float
.RussianRouletteFalloff : float
.DiffuseSamplingCutOffThreshold : float
.ReflectionSamplingCutOffThreshold : float
.RefractionSamplingCutOffThreshold : float
.DirectLightingCutOffThreshold : float
.DirectLightingShadowCutOffThreshold : float
```

### Feature Toggles

```
.ReflectionsEnable : boolean
.RefractionsEnable : boolean
.SubsurfaceScatteringEnable : boolean
.EmissionEnable : boolean
.EnableMaterialsMaxCombinedOverrides : boolean
.DomeLightsAffectedByRefractionEnable : boolean
.AreaLightsAffectedByRefractionEnable : boolean
```

### Sample Overrides

```
.OverrideReflectionSamplesEnabled : boolean
.OverrideReflectionSamplesMode : enum
.OverrideReflectionSamplesCount : integer
.OverrideReflectionSamplesScale : float
.OverrideRefractionSamplesEnabled : boolean
.OverrideRefractionSamplesMode : enum
.OverrideRefractionSamplesCount : integer
.OverrideRefractionSamplesScale : float
.OverrideAOSamplesEnabled : boolean
.OverrideAOSamplesMode : enum
.OverrideAOSamplesCount : integer
.OverrideAOSamplesScale : float
.OverrideLightSamplesEnabled : boolean
.OverrideLightSamplesMode : enum
.OverrideLightSamplesCount : integer
.OverrideLightSamplesScale : float
.OverrideVolumeSamplesEnabled : boolean
.OverrideVolumeSamplesMode : enum
.OverrideVolumeSamplesCount : integer
.OverrideVolumeSamplesScale : float
.OverrideSingleScatteringSamplesEnabled : boolean
.OverrideSingleScatteringSamplesMode : enum
.OverrideSingleScatteringSamplesCount : integer
.OverrideSingleScatteringSamplesScale : float
.OverrideMultipleScatteringSamplesEnabled : boolean
.OverrideMultipleScatteringSamplesMode : enum
.OverrideMultipleScatteringSamplesCount : integer
.OverrideMultipleScatteringSamplesScale : float
```

### Global Illumination

```
.GIEnabled : boolean
.PrimaryGIEngine : enum
.SecondaryGIEngine : enum
.NumGIBounces : integer
.ConserveGIReflectionEnergy : boolean
```

### Caustics

```
.CausticsEnabled : boolean
.CausticsGIEngine : enum
.CausticsOverridesEnabled : boolean
.CausticsOverridesReflectionsEnabled : boolean
.CausticsOverridesRefractionsEnabled : boolean
.CausticsOverridesLightCastingEnabled : boolean
.CausticsOverridesNoIntensityClampsEnabled : boolean
.CausticsIndirectBruteForceSamplingEnabled : boolean
```

### Photon Mapping

```
.PhotonMode : enum
.PhotonFilename : string
.PhotonMaxTraceDepthReflection : integer
.PhotonMaxTraceDepthRefraction : integer
.PhotonMaxTraceDepthCombined : integer
.PhotonCausticsSearchRadius : float
.PhotonCausticsNumPhotons : integer
.PhotonCausticsMaxNumToGather : integer
```

### Brute Force GI

```
.BruteForceGINumRays : integer
```

### Irradiance Point Cloud

```
.IrradiancePointCloudMode : enum
.IrradiancePointCloudFilename : string
.IrradiancePointCloudNumFramesToBlend : integer
.ShowIrradiancePointCloudCalculation : boolean
.IrradiancePointCloudScreenRadius : integer
.IrradiancePointCloudNumSamplesPerPixel : integer
.IrradiancePointCloudFilterSize : float
.IrradiancePointCloudRetraceThreshold : float
```

### Irradiance Cache

```
.IrradianceCacheMode : enum
.IrradianceCacheFilename : string
.IrradianceCacheNumFramesToBlend : integer
.IrradianceCacheFlythroughMode : boolean
.ShowIrradianceCacheCalculation : boolean
.IrradianceCacheUseSeparatePointsForSecondaryRays : boolean
.IrradianceCacheMinRate : integer
.IrradianceCacheMaxRate : integer
.IrradianceCacheColorThreshold : float
.IrradianceCacheDistanceThreshold : float
.IrradianceCacheNormalThreshold : float
.IrradianceCacheMinDetail : float
.IrradianceCacheRadiusFactor : float
.IrradianceCacheNumRays : integer
.IrradianceCacheAdaptiveAmount : float
.IrradianceCacheAdaptiveErrorThreshold : float
.IrradianceCacheNumSmoothingPasses : integer
.IrradianceCacheDebugDrawPoints : boolean
```

### Subsurface Scattering

```
.SubsurfaceScatteringMode : enum
.SubsurfaceScatteringFilename : string
.SubsurfaceScatteringRate : integer
.SubsurfaceScatteringInterpolationQuality : enum
.SubsurfaceScatteringNumGIRays : integer
.SubsurfaceScatteringOverrideMode : enum
```

### Texture

```
.TextureSamplingTechnique : enum
.CopyPreConvertedTexturesToTextureCache : boolean
.BumpMapBias : float
.SuppressTiledTextureWarnings : boolean
.SuppressTextureConversionMessage : boolean
.EnableAutomaticReprocessingOfPreConvertedTextures : boolean
.EnableDetailedTextureProcessingReporting : boolean
```

### Units

```
.EnableDistanceUnits : boolean
.ImageUnitsScale : float
.PhotometricUnitsToMeterScale : float
.PhotometricCandelaMetersSquaredFactor : float
```

### Advanced

```
.DisableShadowRayBiasing : boolean
.DoCompleteRTHConstruction : boolean
.RTHMaxNumLeafPrimitives : integer
.AbortOnLicenseFail : boolean
.AbortOnMissingResource : boolean
.RenderInCameraSpace : boolean
.FreezeTessellation : boolean
.ContourScale : float
.GlobalContourShader : material
.EnableGlobalContour : boolean
.DisableBumpSmoothingOnLightingSilhouettes : boolean
.EnableSecondaryRayClampingOnFirstBounce : boolean
.DisableSamplingOptimizations : boolean
.ShadingNormalAdaptionTechnique : enum
.EnableOptiXRTOnSupportedGPUs : boolean
.EnableAutomaticSampling : boolean
.DisableMotionBlurBandingCompensation : boolean
.EnableLegacySceneConversion : boolean
```

### Memory

```
.PercentageOfGPUMemoryToUse : integer
.GPUMemoryInactivityTimeout : integer
.IrradiancePointCloudGPUWorkingMemory : integer
.IrradianceCacheGPUWorkingMemory : integer
.PercentageOfFreeMemoryUsedForTextureCache : integer
.TextureCacheGPUWorkingMemory : integer
.RayReservedMemory : integer
.TextureCacheCPUWorkingMemory : integer
.AutomaticMemoryManagement : boolean
.NVLinkModeForVolumeGrids : enum
.NVLinkModeForGeometry : enum
```

### Debug

```
.EnableDebugCapture : boolean
.EnableDebugCaptureShaderIntegrityCheck : boolean
.EnableDetailedTextureSamplingStats : boolean
```

### AOV Settings

```
.AOVDeepOutputEnabled : boolean
.AOVDeepMergeMode : enum
.AOVDeepMergeZThreshold : float
.AOVDeepMergeAlphaThreshold : float
.AOVMaxOverbright : float
.AOVMaxOverbrightEnable : boolean
.AOVDisableImportanceOptimizations : boolean
.AOVFixRawHaloArtifacts : boolean
```

### Material Override

```
.MaterialOverrideEnabled : boolean
.MaterialOverrideColor : color
```

### OCIO Color Management

```
.OCIOFilename : string
.OCIORenderingColorSpace : string
.OCIODisplayName : string
.OCIOViewName : string
.UseOCIOFileRules : boolean
.SrgbLinearColorSpace : string
.SrgbNonLinearColorSpace : string
.RawColorSpace : string
```

### Real-Time (RT) Preview Settings

```
.MaxTraceDepthCombinedRT : integer
.NumGIBouncesRT : integer
.MaxTraceDepthReflectionRT : integer
.MaxTraceDepthRefractionRT : integer
.MaxTraceDepthTransparencyRT : integer
.DenoiseEngineRT : enum
.DenoiseAggressivenessRT : float
.LightImportanceSamplingRT : boolean
.UpsamplingRT : boolean
.UpsamplingEngineRT : enum
.UpsamplingModeRT : enum
.RussianRouletteImportanceThresholdRT : float
.RussianRouletteFalloffThresholdRT : float
.PreviewOverlayRT : boolean
.PreviewRenderingRT : boolean
.TextureCompressionLevelRT : enum
```

### Legacy Compatibility Flags

```
.EnableLegacyVolumeGridEmission : boolean
.EnableLegacyCutOffsRules : boolean
.EnableLegacyNonInverseSquareLightDecay : boolean
.EnableLegacyBumpSamplingTechnique : boolean
.EnableLegacyNoGIFromVolumeScattering : boolean
.EnableLegacyNonScalingOfPointClouds : boolean
.EnableLegacyRefractionAffectsAlphaChannel : boolean
.EnableLegacyBlackBodyAndDispersionTechnique : boolean
.EnableLegacySSSGI : boolean
.EnableLegacyVolumePhase : boolean
.EnableLegacyDispersionNestedDielectricsTechnique : boolean
.EnableLegacyTimeBehavior : boolean
.EnableLegacyMaxColorCorrectionSaturationBehavior : boolean
.EnableLegacyGIConserveReflectionEnergyForCaustics : boolean
.EnableLegacyAreaLightVisibility : boolean
```

---

## 9. All Redshift Classes

Complete list from `showClass "Redshift*"` and `showClass "rs*"`:

### Modifiers

| Class | Display Name | SuperClass |
|---|---|---|
| `Redshift_Mesh_Parameters` | Redshift Mesh Parameters | modifier |
| `Redshift_Camera_Effects` | Redshift Camera Effects | modifier |
| `Redshift_Camera_Attributes` | Redshift Camera Attributes | modifier |

### Renderer

| Class | Display Name | SuperClass |
|---|---|---|
| `Redshift_Renderer` | Redshift Renderer | RendererClass |

### Render Effects / Atmospheric

| Class | Display Name | SuperClass |
|---|---|---|
| `Redshift_Bokeh` | Redshift Bokeh | renderEffect |
| `Redshift_Lens_Distortion` | Redshift Lens Distortion | renderEffect |
| `Redshift_Volume_Scattering` | Redshift Volume Scattering | atmospheric |

### Tone Operator

| Class | Display Name | SuperClass |
|---|---|---|
| `Redshift_Photographic_Exposure` | Redshift Photographic Exposure | ToneOperator |

### Custom Attributes

| Class | Display Name | SuperClass |
|---|---|---|
| `Redshift_Texture_Options` | Redshift Texture Options | CustAttrib |
| `Redshift_Trace_Sets` | Redshift Trace Sets | CustAttrib |
| `Redshift_Camera_Type` | Redshift Camera Type | CustAttrib |
| `RS_Post_Effects` | RS Post Effects | CustAttrib |

### Utility

| Class | Display Name | SuperClass |
|---|---|---|
| `Redshift_GUP` | Redshift GUP | GlobalUtilityPlugin |
| `Redshift_Color_Picker` | Redshift Color Picker | colorPicker |

### Lights

| Class | Display Name | SuperClass |
|---|---|---|
| `rsPhysicalLight` | Physical | light |
| `rsDomeLight` | Dome | light |
| `rsSunLight` | RS Sun | light |
| `rsSunSkyLight` | RS Sun and Sky | light |
| `rsIESLight` | IES | light |
| `rsPortalLight` | Portal | light |

### Materials

| Class | Display Name | SuperClass |
|---|---|---|
| `RS_Standard_Material` | RS Standard Material | material |
| `RS_Material` | RS Material | material |
| `RS_Surface` | RS Surface | material |
| `RS_Architectural` | RS Architectural | material |
| `RS_Car_Paint` | RS Car Paint | material |
| `RS_Hair` | RS Hair | material |
| `RS_Principled_Hair` | RS Principled Hair | material |
| `RS_Skin` | RS Skin | material |
| `RS_SSS` | RS SSS | material |
| `RS_Incandescent` | RS Incandescent | material |
| `RS_Sprite` | RS Sprite | material |
| `RS_Toon_Material` | RS Toon Material | material |
| `RS_Volume` | RS Volume | material |
| `RS_Standard_Volume` | RS Standard Volume | material |
| `RS_Matte_Shadow_Catcher` | RS Matte-Shadow Catcher | material |
| `RS_Contour` | RS Contour | material |
| `RS_OpenPBR_Material` | RS OpenPBR Material | material |
| `RS_Material_Blender` | RS Material Blender | material |
| `RS_Material_Switch` | RS Material Switch | material |
| `RS_Random_Material_Switch` | RS Random Material Switch | material |
| `RS_Material_Output` | RS Material Output | material |
| `RS_Ray_Switch_Material` | RS Ray Switch Material | material |
| `RS_Store_Color_To_AOV` | RS Store Color To AOV | material |
| `RS_OSL_Material` | RS OSL Material | material |

### Render Elements

| Class | Display Name | SuperClass |
|---|---|---|
| `RS_Beauty` | RS Beauty | RenderElement |
| `RS_Diffuse_Lighting` | RS Diffuse Lighting | RenderElement |
| `RS_Diffuse_Lighting_Raw` | RS Diffuse Lighting Raw | RenderElement |
| `RS_Diffuse_Filter` | RS Diffuse Filter | RenderElement |
| `RS_Specular_Lighting` | RS Specular Lighting | RenderElement |
| `RS_Reflections` | RS Reflections | RenderElement |
| `RS_Reflections_Filter` | RS Reflections Filter | RenderElement |
| `RS_Reflections_Raw` | RS Reflections Raw | RenderElement |
| `RS_Refractions` | RS Refractions | RenderElement |
| `RS_Refractions_Filter` | RS Refractions Filter | RenderElement |
| `RS_Refractions_Raw` | RS Refractions Raw | RenderElement |
| `RS_Global_Illumination` | RS Global Illumination | RenderElement |
| `RS_Global_Illumination_Raw` | RS Global Illumination Raw | RenderElement |
| `RS_Sub_Surface_Scatter` | RS Sub Surface Scatter | RenderElement |
| `RS_Sub_Surface_Scatter_Raw` | RS Sub Surface Scatter Raw | RenderElement |
| `RS_Emission` | RS Emission | RenderElement |
| `RS_Caustics` | RS Caustics | RenderElement |
| `RS_Caustics_Raw` | RS Caustics Raw | RenderElement |
| `RS_Shadows` | RS Shadows | RenderElement |
| `RS_Background` | RS Background | RenderElement |
| `RS_Matte` | RS Matte | RenderElement |
| `RS_Ambient_Occlusion` | RS Ambient Occlusion | RenderElement |
| `RS_Ambient_Occlusion__Legacy` | RS Ambient Occlusion (Legacy) | RenderElement |
| `RS_Depth` | RS Depth | RenderElement |
| `RS_Normals` | RS Normals | RenderElement |
| `RS_Bump_Normals` | RS Bump Normals | RenderElement |
| `RS_Object_Space_Bump_Normals` | RS Object Space Bump Normals | RenderElement |
| `RS_World_Position` | RS World Position | RenderElement |
| `RS_Object_Space_Positions` | RS Object Space Positions | RenderElement |
| `RS_Motion_Vectors` | RS Motion Vectors | RenderElement |
| `RS_Puzzle_Matte` | RS Puzzle Matte | RenderElement |
| `RS_Cryptomatte` | RS Cryptomatte | RenderElement |
| `RS_Custom` | RS Custom | RenderElement |
| `RS_Object_ID` | RS Object ID | RenderElement |
| `RS_Volume_Lighting` | RS Volume Lighting | RenderElement |
| `RS_Volume_Fog_Emission` | RS Volume Fog Emission | RenderElement |
| `RS_Volume_Fog_Tint` | RS Volume Fog Tint | RenderElement |
| `RS_Volume_Depth` | RS Volume Depth | RenderElement |
| `RS_Translucency_Filter` | RS Translucency Filter | RenderElement |
| `RS_Translucency_Lighting_Raw` | RS Translucency Lighting Raw | RenderElement |
| `RS_Translucency_GI_Raw` | RS Translucency GI Raw | RenderElement |
| `RS_Total_Diffuse_Lighting_Raw` | RS Total Diffuse Lighting Raw | RenderElement |
| `RS_Total_Translucency_Lighting_Raw` | RS Total Translucency Lighting Raw | RenderElement |

### Bake Elements

| Class | Display Name | SuperClass |
|---|---|---|
| `RsBeautyBake` | | BakeElement |
| `RsAmbientOcclusionBake` | | BakeElement |
| `RsBackgroundBake` | | BakeElement |
| `RsBumpNormalsBake` | | BakeElement |
| `RsCausticsBake` | | BakeElement |
| `RsCausticsRawBake` | | BakeElement |
| `RsDiffuseFilterBake` | | BakeElement |
| `RsDiffuseLightingBake` | | BakeElement |
| `RsDiffuseLightingRawBake` | | BakeElement |
| `RsEmissionBake` | | BakeElement |
| `RsGlobalIlluminationBake` | | BakeElement |
| `RsGlobalIlluminationRawBake` | | BakeElement |
| `RsMatteBake` | | BakeElement |
| `RsNormalsBake` | | BakeElement |
| `RsObjectSpaceBumpNormalsBake` | | BakeElement |
| `RsObjectIDBake` | | BakeElement |
| `RsObjectSpacePositionsBake` | | BakeElement |
| `RsReflectionsBake` | | BakeElement |
| `RsReflectionsFilterBake` | | BakeElement |
| `RsReflectionsRawBake` | | BakeElement |
| `RsRefractionsBake` | | BakeElement |
| `RsRefractionsFilterBake` | | BakeElement |
| `RsRefractionsRawBake` | | BakeElement |
| `RsShadowsBake` | | BakeElement |
| `RsSpecularLightingBake` | | BakeElement |
| `RsSubSurfaceScatterBake` | | BakeElement |
| `RsSubSurfaceScatterRawBake` | | BakeElement |
| `RsTotalDiffuseLightingRawBake` | | BakeElement |
| `RsTotalTranslucencyLightingRawBake` | | BakeElement |
| `RsTranslucencyFilterBake` | | BakeElement |
| `RsTranslucencyGIRawBake` | | BakeElement |
| `RsTranslucencyLightingRawBake` | | BakeElement |
| `RsVolumeFogEmissionBake` | | BakeElement |
| `RsVolumeFogTintBake` | | BakeElement |
| `RsVolumeLightingBake` | | BakeElement |

### ReferenceTarget Sub-objects (not directly creatable)

| Class | Display Name | SuperClass |
|---|---|---|
| `RS_Bloom_Params` | RS Bloom Params | ReferenceTarget |
| `RS_Flare_Params` | RS Flare Params | ReferenceTarget |
| `RS_Streak_Params` | RS Streak Params | ReferenceTarget |
| `RS_Optical_Params` | RS Optical Params | ReferenceTarget |
| `RS_LUT_Params` | RS LUT Params | ReferenceTarget |
| `RS_Color_Control_Params` | RS Color Control Params | ReferenceTarget |
| `RS_Physical_Camera_Params` | RS Physical Camera Params | ReferenceTarget |
| `RS_Backplate_Params` | RS Backplate Params | ReferenceTarget |
| `RS_Color_Management_Params` | RS Color Management Params | ReferenceTarget |
| `RS_Curve_Params` | RS Curve Params | ReferenceTarget |
| `RS_Light_List` | RS Light List | ReferenceTarget |
| `rsTraceSet` | RS Trace Set | ReferenceTarget |

### Texture Maps (partial list -- 100+ classes)

Key utility maps:

| Class | Display Name |
|---|---|
| `RS_Bitmap` | RS Bitmap |
| `RS_Normal_Map` | RS Normal Map |
| `RS_Bump_Map` | RS Bump Map |
| `RS_Bump_Blender` | RS Bump Blender |
| `RS_Displacement` | RS Displacement |
| `RS_Displacement_Blender` | RS Displacement Blender |
| `RS_TriPlanar` | RS TriPlanar |
| `RS_Environment` | RS Environment |
| `RS_Physical_Sky` | RS Physical Sky |
| `RS_Noise` (as RS_Maxon_Noise) | RS Maxon Noise |
| `RS_AO` | RS AO |
| `RS_Curvature` | RS Curvature |
| `RS_Fresnel` | RS Fresnel |
| `RS_Round_Corners` | RS Round Corners |
| `RS_Camera_Map` | RS Camera Map |
| `RS_UV_Projection` | RS UV Projection |
| `RS_Color_Correct` | RS Color Correct |
| `RS_Color_Change_Range` | RS Color Change Range |
| `RS_Color_Mix` | RS Color Mix |
| `RS_Multi_Map` | RS Multi-Map |
| `RS_Shader_Switch` | RS Shader Switch |
| `RS_Random_Color_Switch` | RS Random Color Switch |
| `RS_Ray_Switch` | RS Ray Switch |
| `RS_State` | RS State |
| `RS_WireFrame` | RS WireFrame |
| `RS_OSL_Map` | RS OSL Map |
| `RS_Flakes` | RS Flakes |
| `RS_Texture` | RS Texture |
| `RS_Color_User_Data` | RS Color User Data |
| `RS_Scalar_User_Data` | RS Scalar User Data |
| `RS_Integer_User_Data` | RS Integer User Data |
| `RS_Vector_User_Data` | RS Vector User Data |
| `RS_Tonemap_Pattern` | RS Tonemap Pattern |
