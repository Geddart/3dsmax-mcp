# Redshift Texture Map Classes -- Complete Property Reference

> **3ds Max 2025 | Redshift 2026.3.1 | Introspected 2026-03-03**
>
> Generated via MAXScript `showProperties` on live instances of each class.
> Classes that do not exist in this build are noted at the end.

---

## Table of Contents

1. [Image / File Maps](#1-image--file-maps)
2. [Normal / Bump / Displacement](#2-normal--bump--displacement)
3. [Procedural Patterns](#3-procedural-patterns)
4. [Lookup / Environment](#4-lookup--environment)
5. [UV / Coordinate](#5-uv--coordinate)
6. [Math -- Scalar](#6-math--scalar)
7. [Math -- Vector](#7-math--vector)
8. [Math -- Color](#8-math--color)
9. [Utility / Switching / Blending](#9-utility--switching--blending)
10. [User Data / Attributes](#10-user-data--attributes)
11. [Hair / Volume / Special](#11-hair--volume--special)
12. [OSL](#12-osl)
13. [Classes That Do Not Exist](#13-classes-that-do-not-exist-in-this-build)

---

## 1. Image / File Maps

### RS_Bitmap

```
  .startTime            : time
  .playBackRate         : float
  .endCondition         : integer
  .tex0                 : bitmap
  .tex0_gamma           : float
  .tilingmode           : integer
  .apply                : boolean
  .preMultAlpha         : boolean
  .clipu                : float
  .clipv                : float
  .clipw                : float
  .cliph                : float
  .monoOutput           : integer
  .rgbOutput            : integer
  .alphaSource          : integer
  .cropPlace            : integer
  .filter_enable_type   : integer
  .filter_bicubic       : boolean
  .prefer_sharp         : boolean
  .mip_bias             : float
  .tex0_filename        : filename
  .tex0_colorSpace      : string
  .tone_map_enable      : boolean
  .Coordinates          (sub-rollout)
  .Output               (sub-rollout)
```

### RS_Texture

```
  .startTime                : time
  .playBackRate             : float
  .endCondition             : integer
  .tex0                     : bitmap
  .tex0_filename            : filename
  .tilingmode               : integer
  .tex0_gamma               : float
  .map_channel              : integer
  .mapping                  : radiobtnIndex
  .mirrorU                  : boolean
  .mirrorV                  : boolean
  .wrapU                    : boolean
  .wrapV                    : boolean
  .scale_x                  : float
  .scale_y                  : float
  .scale_map                : texturemap
  .scale_mapenable          : boolean
  .offset_x                 : float
  .offset_y                 : float
  .offset_map               : texturemap
  .offset_mapenable         : boolean
  .rotate                   : float
  .rotate_map               : texturemap
  .rotate_mapenable         : boolean
  .color_multiplier         : color
  .color_multiplier_map     : texturemap
  .color_multiplier_mapenable : boolean
  .color_offset             : color
  .color_offset_map         : texturemap
  .color_offset_mapenable   : boolean
  .alpha_multiplier         : float
  .alpha_multiplier_map     : texturemap
  .alpha_multiplier_mapenable : boolean
  .alpha_offset             : float
  .alpha_offset_map         : texturemap
  .alpha_offset_mapenable   : boolean
  .alpha_is_luminance       : boolean
  .invalid_color            : color
  .invalid_color_map        : texturemap
  .invalid_color_mapenable  : boolean
  .filter_enable_type       : integer
  .filter_bicubic           : boolean
  .prefer_sharp             : boolean
  .mip_bias                 : float
  .uv_context               : texturemap
  .uv_context_enable        : boolean
  .tex0_colorSpace          : string
  .tone_map_enable          : boolean
```

### RS_Sprite

```
  .input_map                    : material
  .tex0                         : bitmap
  .tspace_id                    : integer
  .mode                         : integer
  .threshold                    : float
  .repeats_x                    : float
  .repeats_y                    : float
  .bake_shader_input_map        : texturemap
  .bake_shader_input_mapenable  : boolean
  .bake_width                   : integer
  .startTime                    : time
  .playBackRate                 : float
  .endCondition                 : integer
  .tex0_filename                : filename
  .tex0_colorSpace              : string
  .tex0_gamma                   : float
```

---

## 2. Normal / Bump / Displacement

### RS_Normal_Map

```
  .tex0             : bitmap
  .tspace_id        : integer
  .unbiasedNormalMap : boolean
  .flipY            : boolean
  .scale            : float
  .eccmax           : float
  .alt_x            : boolean
  .alt_y            : boolean
  .repeats_x        : float
  .repeats_y        : float
  .wrapU            : boolean
  .wrapV            : boolean
  .min_uv_x         : float
  .min_uv_y         : float
  .max_uv_x         : float
  .max_uv_y         : float
  .legacyNormalMap   : boolean
  .tex0_filename    : filename
```

### RS_Bump_Map

```
  .inuse            : boolean
  .inputType        : integer
  .input            : color
  .input_map        : texturemap
  .input_mapenable  : boolean
  .scale            : float
  .scale_map        : texturemap
  .scale_mapenable  : boolean
  .factorInObjScale : boolean
  .oldrange_min     : float
  .oldrange_max     : float
  .newrange_min     : float
  .newrange_max     : float
  .unbiasedNormalMap : boolean
  .flipY            : boolean
  .legacyNormalMap   : boolean
```

### RS_Displacement

```
  .texMap_map        : texturemap
  .texMap_mapenable  : boolean
  .scale             : float
  .scale_map         : texturemap
  .scale_mapenable   : boolean
  .map_encoding      : integer
  .space_type        : integer
  .tangents          : integer
  .oldrange_min      : float
  .oldrange_max      : float
  .newrange_min      : float
  .newrange_max      : float
  .uv_context        : texturemap
  .uv_context_enable : boolean
```

### RS_Round_Corners

```
  .radius           : worldUnits
  .radius_map       : texturemap
  .radius_mapenable : boolean
  .numSamples       : integer
  .sameObjectOnly   : boolean
```

### RS_Bump_Blender

```
  .baseInput            : point3
  .baseInput_map        : texturemap
  .baseInput_mapenable  : boolean
  .bumpInput0           : point3
  .bumpInput0_map       : texturemap
  .bumpInput0_mapenable : boolean
  .bumpWeight0          : float
  .bumpWeight0_map      : texturemap
  .bumpWeight0_mapenable : boolean
  .bumpInput1           : point3
  .bumpInput1_map       : texturemap
  .bumpInput1_mapenable : boolean
  .bumpWeight1          : float
  .bumpWeight1_map      : texturemap
  .bumpWeight1_mapenable : boolean
  .bumpInput2           : point3
  .bumpInput2_map       : texturemap
  .bumpInput2_mapenable : boolean
  .bumpWeight2          : float
  .bumpWeight2_map      : texturemap
  .bumpWeight2_mapenable : boolean
  .additive             : boolean
```

### RS_Displacement_Blender

```
  .baseInput              : float
  .baseInput_map          : texturemap
  .baseInput_mapenable    : boolean
  .displaceInput0         : float
  .displaceInput0_map     : texturemap
  .displaceInput0_mapenable : boolean
  .displaceWeight0        : float
  .displaceWeight0_map    : texturemap
  .displaceWeight0_mapenable : boolean
  .displaceInput1         : float
  .displaceInput1_map     : texturemap
  .displaceInput1_mapenable : boolean
  .displaceWeight1        : float
  .displaceWeight1_map    : texturemap
  .displaceWeight1_mapenable : boolean
  .displaceInput2         : float
  .displaceInput2_map     : texturemap
  .displaceInput2_mapenable : boolean
  .displaceWeight2        : float
  .displaceWeight2_map    : texturemap
  .displaceWeight2_mapenable : boolean
  .additive               : boolean
```

---

## 3. Procedural Patterns

### RS_Maxon_Noise

```
  .color1                       : color
  .color1_map                   : texturemap
  .color1_mapenable             : boolean
  .color2                       : color
  .color2_map                   : texturemap
  .color2_mapenable             : boolean
  .seed                         : integer
  .noise_type                   : integer
  .octaves                      : float
  .lacunarity                   : float
  .lacunarity_map               : texturemap
  .lacunarity_mapenable         : boolean
  .gain                         : float
  .gain_map                     : texturemap
  .gain_mapenable               : boolean
  .exponent                     : float
  .exponent_map                 : texturemap
  .exponent_mapenable           : boolean
  .absolute                     : boolean
  .animation_speed              : float
  .animation_loop_period        : float
  .animation_source             : integer
  .animation_time               : float
  .animation_time_map           : texturemap
  .animation_time_mapenable     : boolean
  .coord_source                 : integer
  .coord_attribute              : integer
  .coord_scale_global           : float
  .coord_scale_global_map       : texturemap
  .coord_scale_global_mapenable : boolean
  .coord_scale                  : point3
  .coord_scale_map              : texturemap
  .coord_scale_mapenable        : boolean
  .coord_offset                 : point3
  .coord_offset_map             : texturemap
  .coord_offset_mapenable       : boolean
  .cycles                       : float
  .low_clip                     : float
  .high_clip                    : float
  .brightness                   : float
  .contrast                     : float
  .coord_rotation               : point3
  .coord_rotation_map           : texturemap
  .coord_rotation_mapenable     : boolean
  .uv_context                   : texturemap
  .uv_context_enable            : boolean
```

### RS_Tiles

```
  .inGroutColor              : color
  .inGroutColor_map          : texturemap
  .inGroutColor_mapenable    : boolean
  .inTilesColor1             : color
  .inTilesColor1_map         : texturemap
  .inTilesColor1_mapenable   : boolean
  .inTilesColor2             : color
  .inTilesColor2_map         : texturemap
  .inTilesColor2_mapenable   : boolean
  .inTilesColor3             : color
  .inTilesColor3_map         : texturemap
  .inTilesColor3_mapenable   : boolean
  .inRandomizeColor          : boolean
  .inPattern                 : integer
  .inGroutWidth              : float
  .inGroutWidth_map          : texturemap
  .inGroutWidth_mapenable    : boolean
  .inBevelWidth              : float
  .inBevelWidth_map          : texturemap
  .inBevelWidth_mapenable    : boolean
  .inBevel                   : boolean
  .inOrientation             : integer
  .inOrientation_map         : texturemap
  .inOrientation_mapenable   : boolean
  .inGlobalScale             : float
  .inGlobalScale_map         : texturemap
  .inGlobalScale_mapenable   : boolean
  .inUScale                  : float
  .inUScale_map              : texturemap
  .inUScale_mapenable        : boolean
  .inVScale                  : float
  .inVScale_map              : texturemap
  .inVScale_mapenable        : boolean
  .inRadialScale             : float
  .inRadialScale_map         : texturemap
  .inRadialScale_mapenable   : boolean
  .inRotate                  : float
  .inRotate_map              : texturemap
  .inRotate_mapenable        : boolean
  .inNoiseSeed               : integer
  .uv_context                : texturemap
  .uv_context_enable         : boolean
  .uvCoord                   : maxObject
```

### RS_Brick

```
  .brickScaleInput                  : float
  .brickWidthInput                  : float
  .brickHeightInput                 : float
  .brickShift                       : float
  .brickShiftReset                  : integer
  .brickHalfWidthFrequency          : integer
  .brickHalfWidthShift              : float
  .balanceColHPeriod                : boolean
  .uv_context                       : texturemap
  .uv_context_enable                : boolean
  .brickDisplacementRandomHeight    : float
  .brickDisplacementSlopeIntensity  : float
  .brickDisplacementMode            : integer
  .brickDisplacementVariation       : integer
  .brickColorInput                  : maxObject
  .brickTexture                     : color
  .brickTexture_map                 : texturemap
  .brickTexture_mapenable           : boolean
  .brickTextureOffset               : float
  .brickTextureRandom               : boolean
  .brickTextureScale                : float
  .brickTextureFlip                 : boolean
  .brickTextureOpacity              : float
  .brickTextureBlendmode            : integer
  .brickAltColorInput               : maxObject
  .brickAltTexture                  : color
  .brickAltTexture_map              : texturemap
  .brickAltTexture_mapenable        : boolean
  .brickAltTextureOffset            : float
  .brickAltTextureRandom            : boolean
  .brickAltTextureScale             : float
  .brickAltTextureFlip              : boolean
  .brickAltTextureOpacity           : float
  .brickAltTextureBlendmode         : integer
  .altColorVPeriod                  : integer
  .altColorHPeriod                  : integer
  .brickColorNoiseScaleInput        : float
  .detailInput                      : float
  .detailScaleInput                 : float
  .gapColorInput                    : maxObject
  .gapTexture                       : color
  .gapTexture_map                   : texturemap
  .gapTexture_mapenable             : boolean
  .gapTextureScale                  : float
  .gapTextureFlip                   : boolean
  .gapTextureOpacity                : float
  .gapTextureBlendmode              : integer
  .gapColorNoiseScaleInput          : float
  .gapDepthInput                    : float
  .gapSizeInput                     : float
  .gapGrooveInput                   : float
  .gapNoiseIntensity                : float
  .gapNoiseScale                    : float
  .dirtEnable                       : boolean
  .dirtEnableBrick                  : boolean
  .dirtEnableGap                    : boolean
  .dirtOpacityInput                 : float
  .dirtBlendingGapInput             : float
  .dirtBlendingBrickInput           : float
  .dirtColorInput                   : maxObject
  .dirtAlphaInput                   : maxObject
  .dirtColorScaleInput              : float
  .dirtAlphaShift                   : point2
  .dirtAlphaScale                   : float
  .dirtAlphaOct                     : float
  .dirtTexture                      : color
  .dirtTexture_map                  : texturemap
  .dirtTexture_mapenable            : boolean
  .dirtColorTexture                 : color
  .dirtColorTexture_map             : texturemap
  .dirtColorTexture_mapenable       : boolean
  .dirtTextureShift                 : point2
  .dirtTextureScale                 : float
  .dirtTextureFlip                  : boolean
  .dirtTextureMultiplyWithGradient  : boolean
  .dirtTextureAlphaInvert           : boolean
  .dirtTextureAlphaContrast         : float
  .dirtTextureAlphaBias             : float
  .dirtTextureRain                  : float
  .dirtTextureRain_map              : texturemap
  .dirtTextureRain_mapenable        : boolean
  .dirtTextureRainBlurColorTexture  : boolean
  .uvCoord                          : maxObject
  .numIMultipleOutputChannels       : integer
```

### RS_Pavement

```
  .scaleInput                    : float
  .scaleInput_map                : texturemap
  .scaleInput_mapenable          : boolean
  .seedInput                     : integer
  .uv_context                    : texturemap
  .uv_context_enable             : boolean
  .widthInput                    : float
  .widthInput_map                : texturemap
  .widthInput_mapenable          : boolean
  .softInput                     : float
  .softInput_map                 : texturemap
  .softInput_mapenable           : boolean
  .crookednessInput              : float
  .crookednessInput_map          : texturemap
  .crookednessInput_mapenable    : boolean
  .crookednessScaleInput         : float
  .crookednessScaleInput_map     : texturemap
  .crookednessScaleInput_mapenable : boolean
  .stoneColorInput               : maxObject
  .roughStructureInput           : float
  .roughStructureInput_map       : texturemap
  .roughStructureInput_mapenable : boolean
  .fineStructureInput            : float
  .fineStructureInput_map        : texturemap
  .fineStructureInput_mapenable  : boolean
  .gapColorInput                 : maxObject
  .grainyGapsInput               : float
  .grainyGapsInput_map           : texturemap
  .grainyGapsInput_mapenable     : boolean
  .contrastGrainInput            : boolean
  .smudgyColorInput              : maxObject
  .smudgyEdgesInput              : float
  .smudgyEdgesInput_map          : texturemap
  .smudgyEdgesInput_mapenable    : boolean
  .smudgyEdgesSizeInput          : float
  .smudgyEdgesSizeInput_map      : texturemap
  .smudgyEdgesSizeInput_mapenable : boolean
  .uvCoord                       : maxObject
  .numIMultipleOutputChannels    : integer
```

### RS_Flakes

```
  .inScale               : float
  .inDensity             : float
  .inDensity_map         : texturemap
  .inDensity_mapenable   : boolean
  .inRandomize           : float
  .inRandomize_map       : texturemap
  .inRandomize_mapenable : boolean
  .inSeed                : integer
  .inPattern             : integer
  .inFlakeSize           : float
  .inVariance            : float
  .inCoordinateSpace     : integer
  .tspace_id             : integer
  .uv_context            : texturemap
  .uv_context_enable     : boolean
  .inDepth               : float
  .inStepSize            : float
  .inIOR                 : float
  .inFlakesMinimum       : float
  .inFlakesMaximum       : float
  .numIMultipleOutputChannels : integer
```

### RS_Tonemap_Pattern

```
  .pattern                  : integer
  .color1                   : color
  .color1_map               : texturemap
  .color1_mapenable         : boolean
  .color2                   : color
  .color2_map               : texturemap
  .color2_mapenable         : boolean
  .scale                    : float
  .scale_map                : texturemap
  .scale_mapenable          : boolean
  .scaleWidth               : float
  .scaleWidth_map           : texturemap
  .scaleWidth_mapenable     : boolean
  .scaleHeight              : float
  .scaleHeight_map          : texturemap
  .scaleHeight_mapenable    : boolean
  .rotation                 : float
  .rotation_map             : texturemap
  .rotation_mapenable       : boolean
  .offsetX                  : float
  .offsetX_map              : texturemap
  .offsetX_mapenable        : boolean
  .offsetY                  : float
  .offsetY_map              : texturemap
  .offsetY_mapenable        : boolean
  .intensityOverride        : texturemap
  .intensityOverride_enable : boolean
  .tileScaleBias            : float
  .randomSeed               : integer
  .randomScale              : float
  .randomRotation           : float
  .randomOffset             : float
  .randomHueMin             : float
  .randomHueMax             : float
  .randomSaturationMin      : float
  .randomSaturationMax      : float
  .randomValueMin           : float
  .randomValueMax           : float
```

### RS_WireFrame

```
  .polyColor       : color
  .wireColor       : color
  .thickness       : float
  .showHiddenEdges : boolean
```

---

## 4. Lookup / Environment

### RS_Fresnel

```
  .fresnel_useior          : boolean
  .user_curve              : float
  .user_curve_map          : texturemap
  .user_curve_mapenable    : boolean
  .facing_color            : color
  .facing_color_map        : texturemap
  .facing_color_mapenable  : boolean
  .perp_color              : color
  .perp_color_map          : texturemap
  .perp_color_mapenable    : boolean
  .ior                     : float
  .ior_map                 : texturemap
  .ior_mapenable           : boolean
  .correct_intensity       : boolean
  .fresnel_type            : integer
  .extinction_coeff        : float
  .extinction_coeff_map    : texturemap
  .extinction_coeff_mapenable : boolean
  .bump_input              : point3
  .bump_input_map          : texturemap
  .bump_input_mapenable    : boolean
```

### RS_Camera_Map

```
  .tex0                       : bitmap
  .per_pixel_match            : boolean
  .backPlateAspect            : integer
  .applyExposureCompensation  : boolean
  .alphaReplaceEnable         : boolean
  .alphaReplaceValue          : float
  .reflection_is_environment  : boolean
  .offscreen_is_environment   : boolean
  .offscreen_color            : color
  .offscreen_color_map        : texturemap
  .offscreen_color_mapenable  : boolean
  .cameraPicker               : node
  .tex0_filename              : filename
  .tex0_colorSpace            : string
  .tex0_gamma                 : float
  .startTime                  : time
  .playBackRate               : float
  .endCondition               : integer
```

### RS_Environment

```
  .texMode                    : integer
  .tex0                       : bitmap
  .mode                       : integer
  .rotation_x                 : float
  .rotation_y                 : float
  .rotation_z                 : float
  .background_intensity       : float
  .reflection_intensity       : float
  .fg_intensity               : float
  .giAffectsMatteShadow       : boolean
  .alphaReplaceEnable         : boolean
  .alphaReplaceValue          : float
  .backPlateEnabled           : boolean
  .tex1                       : bitmap
  .backPlateAspect            : integer
  .applyExposureCompensation  : boolean
  .tex2                       : bitmap
  .modeRefract                : integer
  .tex3                       : bitmap
  .modeReflect                : integer
  .tex4                       : bitmap
  .modeGI                     : integer
  .tex0_gamma                 : float
  .tex0_exp                   : float
  .tex0_hue                   : float
  .tex0_sat                   : float
  .tex1_gamma                 : float
  .tex1_exp                   : float
  .tex1_hue                   : float
  .tex1_sat                   : float
  .tex2_gamma                 : float
  .tex2_exp                   : float
  .tex2_hue                   : float
  .tex2_sat                   : float
  .tex3_gamma                 : float
  .tex3_exp                   : float
  .tex3_hue                   : float
  .tex3_sat                   : float
  .tex4_gamma                 : float
  .tex4_exp                   : float
  .tex4_hue                   : float
  .tex4_sat                   : float
  .tex0_filename              : filename
  .tex1_filename              : filename
  .tex2_filename              : filename
  .tex3_filename              : filename
  .tex4_filename              : filename
  .tex0_colorSpace            : string
  .tex1_colorSpace            : string
  .tex2_colorSpace            : string
  .tex3_colorSpace            : string
  .tex4_colorSpace            : string
```

### RS_Physical_Sky

```
  .on                                   : boolean
  .deriveFromSun                        : boolean
  .intensity                            : float
  .intensity_map                        : texturemap
  .intensity_mapenable                  : boolean
  .useNonPhysicalIntensity              : boolean
  .model                                : integer
  .haze                                 : float
  .haze_map                             : texturemap
  .haze_mapenable                       : boolean
  .ozone                                : float
  .horizon_height                       : float
  .horizon_height_map                   : texturemap
  .horizon_height_mapenable             : boolean
  .horizon_blur                         : float
  .horizon_blur_map                     : texturemap
  .horizon_blur_mapenable               : boolean
  .ground_color                         : color
  .ground_color_map                     : texturemap
  .ground_color_mapenable               : boolean
  .night_color                          : color
  .night_color_map                      : texturemap
  .night_color_mapenable                : boolean
  .redblueshift                         : float
  .redblueshift_map                     : texturemap
  .redblueshift_mapenable               : boolean
  .saturation                           : float
  .saturation_map                       : texturemap
  .saturation_mapenable                 : boolean
  .saturation_affects_color_adjustments : boolean
  .sun_direction                        : point3
  .sun_disk_intensity                   : float
  .sun_disk_scale                       : float
  .sun_glow_intensity                   : float
  .forceAlphaToZero                     : boolean
  .background_enable                    : boolean
  .reflection_enable                    : boolean
  .reflection_intensity                 : float
  .refraction_enable                    : boolean
  .refraction_intensity                 : float
  .gi_enable                            : boolean
  .gi_intensity                         : float
  .sun_node                             : node
  .sun_tint                             : color
  .sun_tint_map                         : texturemap
  .sun_tint_mapenable                   : boolean
```

### RS_Curvature

```
  .mode                 : integer
  .radius               : worldUnits
  .radius_map           : texturemap
  .radius_mapenable     : boolean
  .numSamples           : integer
  .inputMin             : float
  .inputMin_map         : texturemap
  .inputMin_mapenable   : boolean
  .inputMax             : float
  .inputMax_map         : texturemap
  .inputMax_mapenable   : boolean
  .contrastVal          : float
  .contrastVal_map      : texturemap
  .contrastVal_mapenable : boolean
  .contrastPivot        : float
  .contrastPivot_map    : texturemap
  .contrastPivot_mapenable : boolean
  .bias                 : float
  .bias_map             : texturemap
  .bias_mapenable       : boolean
  .gain                 : float
  .gain_map             : texturemap
  .gain_mapenable       : boolean
  .outputMin            : float
  .outputMin_map        : texturemap
  .outputMin_mapenable  : boolean
  .outputMax            : float
  .outputMax_map        : texturemap
  .outputMax_mapenable  : boolean
  .clampEnable          : boolean
  .clampExpand          : boolean
  .clampMin             : float
  .clampMin_map         : texturemap
  .clampMin_mapenable   : boolean
  .clampMax             : float
  .clampMax_map         : texturemap
  .clampMax_mapenable   : boolean
  .sameObjectOnly       : boolean
```

### RS_AO

```
  .numSamples          : integer
  .bright              : color
  .bright_map          : texturemap
  .bright_mapenable    : boolean
  .dark                : color
  .dark_map            : texturemap
  .dark_mapenable      : boolean
  .spread              : float
  .spread_map          : texturemap
  .spread_mapenable    : boolean
  .fallOff             : float
  .fallOff_map         : texturemap
  .fallOff_mapenable   : boolean
  .maxDistance          : worldUnits
  .maxDistance_map      : texturemap
  .maxDistance_mapenable : boolean
  .reflective          : boolean
  .invert              : boolean
  .outputMode          : integer
  .biasMode            : integer
  .bias                : point3
  .bias_map            : texturemap
  .bias_mapenable      : boolean
  .occlusionInAlpha    : boolean
  .sameObjectOnly      : boolean
```

### RS_Triplanar

*(Also registered as `RS_TriPlanar` -- both names resolve to the same class.)*

```
  .sameImageOnEachAxis   : boolean
  .imageX                : color
  .imageX_map            : texturemap
  .imageX_mapenable      : boolean
  .imageY                : color
  .imageY_map            : texturemap
  .imageY_mapenable      : boolean
  .imageZ                : color
  .imageZ_map            : texturemap
  .imageZ_mapenable      : boolean
  .blendAmount           : float
  .blendAmount_map       : texturemap
  .blendAmount_mapenable : boolean
  .blendCurve            : float
  .scale                 : point3
  .scale_map             : texturemap
  .scale_mapenable       : boolean
  .offset                : point3
  .offset_map            : texturemap
  .offset_mapenable      : boolean
  .rotation              : point3
  .rotation_map          : texturemap
  .rotation_mapenable    : boolean
  .projSpaceType         : integer
  .worldSpaceUnit        : integer
```

### RS_MatCap

```
  .color           : color
  .color_map       : texturemap
  .color_mapenable : boolean
  .space           : integer
  .scaling         : float
  .scalingU        : float
  .scalingV        : float
  .rotation        : float
```

### RS_Distance

```
  .numSamples                : integer
  .distanceNear              : float
  .distanceNear_map          : texturemap
  .distanceNear_mapenable    : boolean
  .distanceFar               : float
  .distanceFar_map           : texturemap
  .distanceFar_mapenable     : boolean
  .normalizeToRange          : boolean
  .colorNear                 : color
  .colorNear_map             : texturemap
  .colorNear_mapenable       : boolean
  .colorFar                  : color
  .colorFar_map              : texturemap
  .colorFar_mapenable        : boolean
  .includeBackside           : boolean
  .includeMode               : integer
  .traceset                  : maxObject
  .enableInterior            : boolean
  .colorInteriorNear         : color
  .colorInteriorNear_map     : texturemap
  .colorInteriorNear_mapenable : boolean
  .colorInteriorFar          : color
  .colorInteriorFar_map      : texturemap
  .colorInteriorFar_mapenable : boolean
  .solidInterior             : integer
  .numIMultipleOutputChannels : integer
```

### RS_Ray_Switch

```
  .cameraSwitchFrontBack       : boolean
  .cameraColor                 : color
  .cameraColor_map             : texturemap
  .cameraColor_mapenable       : boolean
  .cameraColorBack             : color
  .cameraColorBack_map         : texturemap
  .cameraColorBack_mapenable   : boolean
  .reflectionSwitch            : boolean
  .reflectionSwitchFrontBack   : boolean
  .reflectionColor             : color
  .reflectionColor_map         : texturemap
  .reflectionColor_mapenable   : boolean
  .reflectionColorBack         : color
  .reflectionColorBack_map     : texturemap
  .reflectionColorBack_mapenable : boolean
  .refractionSwitch            : boolean
  .refractionSwitchFrontBack   : boolean
  .refractionColor             : color
  .refractionColor_map         : texturemap
  .refractionColor_mapenable   : boolean
  .refractionColorBack         : color
  .refractionColorBack_map     : texturemap
  .refractionColorBack_mapenable : boolean
  .giSwitch                    : boolean
  .giSwitchFrontBack           : boolean
  .giColor                     : color
  .giColor_map                 : texturemap
  .giColor_mapenable           : boolean
  .giColorBack                 : color
  .giColorBack_map             : texturemap
  .giColorBack_mapenable       : boolean
```

### RS_State

```
  .output              : integer
  .tspace_id           : integer
  .tangents            : integer
  .trans_space         : integer
  .showRayFacingNormals : boolean
  .bounceLevelType     : integer
```

### RS_Surface_Tangent

```
  .source              : integer
  .tspace_id           : integer
  .userTangent         : point3
  .userTangent_map     : texturemap
  .userTangent_mapenable : boolean
  .rotation            : float
  .rotation_map        : texturemap
  .rotation_mapenable  : boolean
```

---

## 5. UV / Coordinate

### RS_UV_Projection

```
  .color               : color
  .color_map           : texturemap
  .color_mapenable     : boolean
  .proj_type           : integer
  .coord_space         : integer
  .angle_u             : float
  .angle_v             : float
  .coord_scale         : point3
  .coord_scale_map     : texturemap
  .coord_scale_mapenable : boolean
  .coord_rotate        : point3
  .coord_rotate_map    : texturemap
  .coord_rotate_mapenable : boolean
  .coord_offset        : point3
  .coord_offset_map    : texturemap
  .coord_offset_mapenable : boolean
  .uv_scale_x          : float
  .uv_scale_y          : float
  .uv_scale_map        : texturemap
  .uv_scale_mapenable  : boolean
  .uv_offset_x         : float
  .uv_offset_y         : float
  .uv_offset_map       : texturemap
  .uv_offset_mapenable : boolean
  .uv_rotate           : float
  .uv_rotate_map       : texturemap
  .uv_rotate_mapenable : boolean
  .world_space_unit    : integer
```

### RS_UV_Context_Projection

```
  .proj_type           : integer
  .proj_space          : integer
  .tspace_id           : integer
  .coord_source        : integer
  .coord_object_id     : node
  .coord_physical_size : boolean
  .coord_uniform_size  : boolean
  .coord_size_x        : float
  .coord_size_y        : float
  .coord_size_z        : float
  .coord_offset        : point3
  .coord_rotate        : point3
  .camera_film_aspect  : float
  .camera_pixel_aspect : float
  .tp_axis_rotate      : point3
  .tp_blend_amount     : float
  .tp_blend_curve      : float
  .tp_blend_noise      : float
  .tp_noise_scale      : float
  .uv_uniform_tiles    : boolean
  .uv_tiles_u          : float
  .uv_tiles_v          : float
  .uv_offset           : point2
  .uv_rotate           : float
  .uv_pivot            : point2
  .wrap_u              : integer
  .wrap_v              : integer
  .flip_u              : boolean
  .flip_v              : boolean
  .isLeftHanded        : boolean
  .yIsUp               : boolean
```

---

## 6. Math -- Scalar

### RS_Add

```
  .input1           : float
  .input1_map       : texturemap
  .input1_mapenable : boolean
  .input2           : float
  .input2_map       : texturemap
  .input2_mapenable : boolean
```

### RS_Sub

```
  .input1           : float
  .input1_map       : texturemap
  .input1_mapenable : boolean
  .input2           : float
  .input2_map       : texturemap
  .input2_mapenable : boolean
```

### RS_Mul

```
  .input1           : float
  .input1_map       : texturemap
  .input1_mapenable : boolean
  .input2           : float
  .input2_map       : texturemap
  .input2_mapenable : boolean
```

### RS_Div

```
  .input1           : float
  .input1_map       : texturemap
  .input1_mapenable : boolean
  .input2           : float
  .input2_map       : texturemap
  .input2_mapenable : boolean
```

### RS_Mod

```
  .input            : float
  .input_map        : texturemap
  .input_mapenable  : boolean
  .divisor          : float
  .divisor_map      : texturemap
  .divisor_mapenable : boolean
```

### RS_Pow

```
  .base             : float
  .base_map         : texturemap
  .base_mapenable   : boolean
  .exponent         : float
  .exponent_map     : texturemap
  .exponent_mapenable : boolean
```

### RS_Exp

```
  .input           : float
  .input_map       : texturemap
  .input_mapenable : boolean
```

### RS_Log

```
  .input           : float
  .input_map       : texturemap
  .input_mapenable : boolean
  .base            : float
  .base_map        : texturemap
  .base_mapenable  : boolean
```

### RS_Ln

```
  .input           : float
  .input_map       : texturemap
  .input_mapenable : boolean
```

### RS_Sqrt

```
  .input           : float
  .input_map       : texturemap
  .input_mapenable : boolean
```

### RS_Abs

```
  .input           : float
  .input_map       : texturemap
  .input_mapenable : boolean
```

### RS_Sign

```
  .input           : float
  .input_map       : texturemap
  .input_mapenable : boolean
```

### RS_Neg

```
  .input           : float
  .input_map       : texturemap
  .input_mapenable : boolean
```

### RS_Rcp

```
  .input           : float
  .input_map       : texturemap
  .input_mapenable : boolean
```

### RS_Invert

```
  .input           : float
  .input_map       : texturemap
  .input_mapenable : boolean
```

### RS_Floor

```
  .input           : float
  .input_map       : texturemap
  .input_mapenable : boolean
```

### RS_Frac

```
  .input           : float
  .input_map       : texturemap
  .input_mapenable : boolean
```

### RS_Saturate

```
  .input           : float
  .input_map       : texturemap
  .input_mapenable : boolean
```

### RS_Min

```
  .input1           : float
  .input1_map       : texturemap
  .input1_mapenable : boolean
  .input2           : float
  .input2_map       : texturemap
  .input2_mapenable : boolean
```

### RS_Max

```
  .input1           : float
  .input1_map       : texturemap
  .input1_mapenable : boolean
  .input2           : float
  .input2_map       : texturemap
  .input2_mapenable : boolean
```

### RS_Mix

```
  .input1           : float
  .input1_map       : texturemap
  .input1_mapenable : boolean
  .input2           : float
  .input2_map       : texturemap
  .input2_mapenable : boolean
  .mixAmount        : float
  .mixAmount_map    : texturemap
  .mixAmount_mapenable : boolean
```

### RS_Bias

```
  .input           : float
  .input_map       : texturemap
  .input_mapenable : boolean
  .bias            : float
  .bias_map        : texturemap
  .bias_mapenable  : boolean
```

### RS_Gain

```
  .input           : float
  .input_map       : texturemap
  .input_mapenable : boolean
  .gain            : float
  .gain_map        : texturemap
  .gain_mapenable  : boolean
```

### RS_Change_Range

```
  .input           : float
  .input_map       : texturemap
  .input_mapenable : boolean
  .old_min         : float
  .old_min_map     : texturemap
  .old_min_mapenable : boolean
  .old_max         : float
  .old_max_map     : texturemap
  .old_max_mapenable : boolean
  .new_min         : float
  .new_min_map     : texturemap
  .new_min_mapenable : boolean
  .new_max         : float
  .new_max_map     : texturemap
  .new_max_mapenable : boolean
  .clamp           : boolean
```

### RS_Sine

```
  .input           : float
  .input_map       : texturemap
  .input_mapenable : boolean
  .isRadians       : boolean
```

### RS_Cosine

```
  .input           : float
  .input_map       : texturemap
  .input_mapenable : boolean
  .isRadians       : boolean
```

### RS_Tangent

```
  .input           : float
  .input_map       : texturemap
  .input_mapenable : boolean
  .isRadians       : boolean
```

### RS_Arcsine

```
  .input           : float
  .input_map       : texturemap
  .input_mapenable : boolean
  .isRadians       : boolean
```

### RS_Arccosine

```
  .input           : float
  .input_map       : texturemap
  .input_mapenable : boolean
  .isRadians       : boolean
```

### RS_Arctangent

```
  .input           : float
  .input_map       : texturemap
  .input_mapenable : boolean
  .isRadians       : boolean
```

### RS_ArcTan2

```
  .x               : float
  .x_map           : texturemap
  .x_mapenable     : boolean
  .y               : float
  .y_map           : texturemap
  .y_mapenable     : boolean
```

---

## 7. Math -- Vector

### RS_Vector_Add

```
  .input1           : point3
  .input1_map       : texturemap
  .input1_mapenable : boolean
  .input2           : point3
  .input2_map       : texturemap
  .input2_mapenable : boolean
```

### RS_Vector_Sub

```
  .input1           : point3
  .input1_map       : texturemap
  .input1_mapenable : boolean
  .input2           : point3
  .input2_map       : texturemap
  .input2_mapenable : boolean
```

### RS_Vector_Mul

```
  .input1           : point3
  .input1_map       : texturemap
  .input1_mapenable : boolean
  .input2           : point3
  .input2_map       : texturemap
  .input2_mapenable : boolean
```

### RS_Vector_Div

```
  .input1           : point3
  .input1_map       : texturemap
  .input1_mapenable : boolean
  .input2           : point3
  .input2_map       : texturemap
  .input2_mapenable : boolean
```

### RS_Vector_Mod

```
  .input           : point3
  .input_map       : texturemap
  .input_mapenable : boolean
  .divisor         : point3
  .divisor_map     : texturemap
  .divisor_mapenable : boolean
```

### RS_Vector_Pow

```
  .base             : point3
  .base_map         : texturemap
  .base_mapenable   : boolean
  .exponent         : point3
  .exponent_map     : texturemap
  .exponent_mapenable : boolean
```

### RS_Vector_Exp

```
  .input           : point3
  .input_map       : texturemap
  .input_mapenable : boolean
```

### RS_Vector_Log

```
  .input           : point3
  .input_map       : texturemap
  .input_mapenable : boolean
  .base            : point3
  .base_map        : texturemap
  .base_mapenable  : boolean
```

### RS_Vector_Ln

```
  .input           : point3
  .input_map       : texturemap
  .input_mapenable : boolean
```

### RS_Vector_Sqrt

```
  .input           : point3
  .input_map       : texturemap
  .input_mapenable : boolean
```

### RS_Vector_Abs

```
  .input           : point3
  .input_map       : texturemap
  .input_mapenable : boolean
```

### RS_Vector_Sign

```
  .input           : point3
  .input_map       : texturemap
  .input_mapenable : boolean
```

### RS_Vector_Neg

```
  .input           : point3
  .input_map       : texturemap
  .input_mapenable : boolean
```

### RS_Vector_Rcp

```
  .input           : point3
  .input_map       : texturemap
  .input_mapenable : boolean
```

### RS_Vector_Invert

```
  .input           : point3
  .input_map       : texturemap
  .input_mapenable : boolean
```

### RS_Vector_Floor

```
  .input           : point3
  .input_map       : texturemap
  .input_mapenable : boolean
```

### RS_Vector_Frac

```
  .input           : point3
  .input_map       : texturemap
  .input_mapenable : boolean
```

### RS_Vector_Saturate

```
  .input           : point3
  .input_map       : texturemap
  .input_mapenable : boolean
```

### RS_Vector_Min

```
  .input1           : point3
  .input1_map       : texturemap
  .input1_mapenable : boolean
  .input2           : point3
  .input2_map       : texturemap
  .input2_mapenable : boolean
```

### RS_Vector_Max

```
  .input1           : point3
  .input1_map       : texturemap
  .input1_mapenable : boolean
  .input2           : point3
  .input2_map       : texturemap
  .input2_mapenable : boolean
```

### RS_Vector_Mix

```
  .input1           : point3
  .input1_map       : texturemap
  .input1_mapenable : boolean
  .input2           : point3
  .input2_map       : texturemap
  .input2_mapenable : boolean
  .mixAmount        : point3
  .mixAmount_map    : texturemap
  .mixAmount_mapenable : boolean
```

### RS_Vector_Bias

```
  .input           : point3
  .input_map       : texturemap
  .input_mapenable : boolean
  .bias            : point3
  .bias_map        : texturemap
  .bias_mapenable  : boolean
```

### RS_Vector_Gain

```
  .input           : point3
  .input_map       : texturemap
  .input_mapenable : boolean
  .gain            : point3
  .gain_map        : texturemap
  .gain_mapenable  : boolean
```

### RS_Vector_Change_Range

```
  .input           : point3
  .input_map       : texturemap
  .input_mapenable : boolean
  .old_min         : point3
  .old_min_map     : texturemap
  .old_min_mapenable : boolean
  .old_max         : point3
  .old_max_map     : texturemap
  .old_max_mapenable : boolean
  .new_min         : point3
  .new_min_map     : texturemap
  .new_min_mapenable : boolean
  .new_max         : point3
  .new_max_map     : texturemap
  .new_max_mapenable : boolean
  .clamp           : boolean
```

### RS_Normalize

```
  .input           : point3
  .input_map       : texturemap
  .input_mapenable : boolean
```

### RS_Vector_Length

```
  .input           : point3
  .input_map       : texturemap
  .input_mapenable : boolean
```

### RS_Dot_Product

```
  .input1           : point3
  .input1_map       : texturemap
  .input1_mapenable : boolean
  .input2           : point3
  .input2_map       : texturemap
  .input2_mapenable : boolean
```

### RS_Cross_Product

```
  .input1           : point3
  .input1_map       : texturemap
  .input1_mapenable : boolean
  .input2           : point3
  .input2_map       : texturemap
  .input2_mapenable : boolean
```

### RS_Vector_Maker

```
  .x               : float
  .x_map           : texturemap
  .x_mapenable     : boolean
  .y               : float
  .y_map           : texturemap
  .y_mapenable     : boolean
  .z               : float
  .z_map           : texturemap
  .z_mapenable     : boolean
```

### RS_Vector_To_Scalars

```
  .output          : integer
  .input           : point3
  .input_map       : texturemap
  .input_mapenable : boolean
```

---

## 8. Math -- Color

### RS_Color_Mix

```
  .input1              : color
  .input1_map          : texturemap
  .input1_mapenable    : boolean
  .input2              : color
  .input2_map          : texturemap
  .input2_mapenable    : boolean
  .mixAmount           : float
  .mixAmount_map       : texturemap
  .mixAmount_mapenable : boolean
```

### RS_Color_Sub

```
  .input1           : color
  .input1_map       : texturemap
  .input1_mapenable : boolean
  .input2           : color
  .input2_map       : texturemap
  .input2_mapenable : boolean
  .applyToAlpha     : boolean
```

### RS_Color_Invert

```
  .input           : color
  .input_map       : texturemap
  .input_mapenable : boolean
  .applyToAlpha    : boolean
```

### RS_Color_Abs

```
  .input           : color
  .input_map       : texturemap
  .input_mapenable : boolean
  .applyToAlpha    : boolean
```

### RS_Color_Exp

```
  .input           : color
  .input_map       : texturemap
  .input_mapenable : boolean
  .applyToAlpha    : boolean
```

### RS_Color_Saturate

```
  .input           : color
  .input_map       : texturemap
  .input_mapenable : boolean
  .applyToAlpha    : boolean
```

### RS_Color_Bias

```
  .input           : color
  .input_map       : texturemap
  .input_mapenable : boolean
  .bias            : color
  .bias_map        : texturemap
  .bias_mapenable  : boolean
  .applyToAlpha    : boolean
```

### RS_Color_Gain

```
  .input           : color
  .input_map       : texturemap
  .input_mapenable : boolean
  .gain            : color
  .gain_map        : texturemap
  .gain_mapenable  : boolean
  .applyToAlpha    : boolean
```

### RS_Color_Change_Range

```
  .input           : color
  .input_map       : texturemap
  .input_mapenable : boolean
  .old_min         : color
  .old_min_map     : texturemap
  .old_min_mapenable : boolean
  .old_max         : color
  .old_max_map     : texturemap
  .old_max_mapenable : boolean
  .new_min         : color
  .new_min_map     : texturemap
  .new_min_mapenable : boolean
  .new_max         : color
  .new_max_map     : texturemap
  .new_max_mapenable : boolean
  .applyToAlpha    : boolean
  .clamp           : boolean
```

### RS_Color_Correct

```
  .input              : color
  .input_map          : texturemap
  .input_mapenable    : boolean
  .gamma              : float
  .gamma_map          : texturemap
  .gamma_mapenable    : boolean
  .contrast           : float
  .contrast_map       : texturemap
  .contrast_mapenable : boolean
  .hue                : float
  .hue_map            : texturemap
  .hue_mapenable      : boolean
  .saturation         : float
  .saturation_map     : texturemap
  .saturation_mapenable : boolean
  .level              : float
  .level_map          : texturemap
  .level_mapenable    : boolean
  .updatedMode        : boolean
  .xsiMode            : boolean
```

### RS_Color_Constant

```
  .color : color
```

### RS_Color_Maker

```
  .red             : float
  .red_map         : texturemap
  .red_mapenable   : boolean
  .green           : float
  .green_map       : texturemap
  .green_mapenable : boolean
  .blue            : float
  .blue_map        : texturemap
  .blue_mapenable  : boolean
  .alpha           : float
  .alpha_map       : texturemap
  .alpha_mapenable : boolean
```

### RS_Color_Splitter

```
  .output          : integer
  .input           : color
  .input_map       : texturemap
  .input_mapenable : boolean
```

### RS_Color_To_HSV

```
  .input           : color
  .input_map       : texturemap
  .input_mapenable : boolean
```

### RS_HSV_To_Color

```
  .input           : color
  .input_map       : texturemap
  .input_mapenable : boolean
```

### RS_IOR_To_Metal_Tints

```
  .ior                        : point3
  .ior_map                    : texturemap
  .ior_mapenable              : boolean
  .k                          : point3
  .k_map                      : texturemap
  .k_mapenable                : boolean
  .numIMultipleOutputChannels : integer
```

---

## 9. Utility / Switching / Blending

### RS_Shader_Switch

```
  .selector              : integer
  .selector_map          : texturemap
  .selector_mapenable    : boolean
  .selector_offset       : integer
  .shader0               : color
  .shader0_map           : texturemap
  .shader0_mapenable     : boolean
  .shader1               : color
  .shader1_map           : texturemap
  .shader1_mapenable     : boolean
  .shader2               : color
  .shader2_map           : texturemap
  .shader2_mapenable     : boolean
  .shader3               : color
  .shader3_map           : texturemap
  .shader3_mapenable     : boolean
  .shader4               : color
  .shader4_map           : texturemap
  .shader4_mapenable     : boolean
  .shader5               : color
  .shader5_map           : texturemap
  .shader5_mapenable     : boolean
  .shader6               : color
  .shader6_map           : texturemap
  .shader6_mapenable     : boolean
  .shader7               : color
  .shader7_map           : texturemap
  .shader7_mapenable     : boolean
  .shader8               : color
  .shader8_map           : texturemap
  .shader8_mapenable     : boolean
  .shader9               : color
  .shader9_map           : texturemap
  .shader9_mapenable     : boolean
  .default_shader        : color
  .default_shader_map    : texturemap
  .default_shader_mapenable : boolean
```

### RS_Multi_Map

```
  .default_color    : color
  .default_map      : texturemap
  .default_mapenable : boolean
  .source           : integer
  .on               : boolean array
  .id               : integer array
  .color            : color array
  .map              : texturemap array
  .mapenable        : boolean array
```

### RS_Random_Color_Switch

```
  .inInputID              : integer
  .inUserData             : integer
  .inUserData_map         : texturemap
  .inUserData_mapenable   : boolean
  .inFloatSeed            : integer
  .shader_input           : color array
  .shader_input_map       : texturemap array
  .shader_input_mapenable : boolean array
  .shader_weight          : float array
  .inColJitterEnabled     : boolean
  .inHueVarMin            : float
  .inHueVarMax            : float
  .inHueSeed              : integer
  .inSaturationVarMin     : float
  .inSaturationVarMax     : float
  .inSaturationSeed       : integer
  .inValueVarMin          : float
  .inValueVarMax          : float
  .inValueSeed            : integer
```

### RS_Jitter

```
  .inInputID              : integer
  .inUserData             : integer
  .inUserData_map         : texturemap
  .inUserData_mapenable   : boolean
  .inColor                : color
  .inColor_map            : texturemap
  .inColor_mapenable      : boolean
  .inHueVarMin            : float
  .inHueVarMax            : float
  .inHueSeed              : integer
  .inSaturationVarMin     : float
  .inSaturationVarMax     : float
  .inSaturationSeed       : integer
  .inValueVarMin          : float
  .inValueVarMax          : float
  .inValueSeed            : integer
  .inFloatMin             : float
  .inFloatMax             : float
  .inFloatSeed            : integer
  .inIntegerMin           : integer
  .inIntegerMax           : integer
  .inIntegerSeed          : integer
  .numIMultipleOutputChannels : integer
```

### RS_Distorter

```
  .distorter           : color
  .distorter_map       : texturemap
  .distorter_mapenable : boolean
  .texture             : color
  .texture_map         : texturemap
  .texture_mapenable   : boolean
  .inType              : integer
  .inWrap              : integer
  .inAmount            : float
  .inX                 : float
  .inY                 : float
  .inZ                 : float
  .inDelta             : float
  .inStep              : float
```

### RS_Unit_Conversion

```
  .mode                       : integer
  .unit                       : integer
  .fixedUnitLength            : float
  .dynamicUnitLength          : float
  .scalarValue                : float
  .scalarValue_map            : texturemap
  .scalarValue_mapenable      : boolean
  .vectorValue                : point3
  .vectorValue_map            : texturemap
  .vectorValue_mapenable      : boolean
  .numIMultipleOutputChannels : integer
```

---

## 10. User Data / Attributes

### RS_Color_User_Data

```
  .attribute : string
  .default   : color
```

### RS_Scalar_User_Data

```
  .attribute : string
  .default   : float
```

### RS_Integer_User_Data

```
  .attribute : string
  .default   : integer
```

### RS_Vector_User_Data

```
  .attribute : string
  .default   : point3
```

---

## 11. Hair / Volume / Special

### RS_Shave

```
  .out_attribute : integer
```

### RS_Hair_Random_Color

```
  .color           : color
  .color_map       : texturemap
  .color_mapenable : boolean
  .hueAmount       : float
  .satAmount       : float
  .valAmount       : float
```

### RS_Hair_Position

```
  (no properties)
```

### RS_Volume_Color_Attribute

```
  .channel_name        : string
  .default_color       : color
  .pos_offset          : point3
  .pos_offset_map      : texturemap
  .pos_offset_mapenable : boolean
```

### RS_Volume_Scalar_Attribute

```
  .channel_name  : string
  .default_scalar : float
  .pos_offset    : point3
  .pos_offset_map : texturemap
  .pos_offset_mapenable : boolean
  .old_min       : float
  .old_max       : float
  .new_min       : float
  .new_max       : float
```

---

## 12. OSL

### RS_OSL_Map

```
  .oslFilename                : filename
  .oslCode                    : string
  .oslSource                  : integer
  .numIMultipleOutputChannels : integer
```

---

## 13. Classes That Do Not Exist in This Build

The following class names were tested but do **not** exist as instantiable TextureMap classes in this version of Redshift for 3ds Max 2025:

| Requested Name      | Status |
|---------------------|--------|
| `RS_UDIM_Texture`   | Not found (undefined) |
| `RS_Noise`          | Not found -- use `RS_Maxon_Noise` instead |
| `RS_Ramp`           | Not found |
| `RS_Gradient_Ramp`  | Not found |
| `RS_Stencil`        | Not found |
| `RS_Color_Layer`    | Not found |
| `RS_UVProject`      | Not found -- use `RS_UV_Projection` instead |
| `RS_UV_Remap`       | Not found |

---

## Complete Class Index (alphabetical)

Total: **109 RS_ TextureMap classes** discovered.

| # | Class Name | Category |
|---|-----------|----------|
| 1 | RS_Abs | Math - Scalar |
| 2 | RS_Add | Math - Scalar |
| 3 | RS_AO | Lookup / Environment |
| 4 | RS_ArcTan2 | Math - Scalar |
| 5 | RS_Arccosine | Math - Scalar |
| 6 | RS_Arcsine | Math - Scalar |
| 7 | RS_Arctangent | Math - Scalar |
| 8 | RS_Bias | Math - Scalar |
| 9 | RS_Bitmap | Image / File |
| 10 | RS_Brick | Procedural Pattern |
| 11 | RS_Bump_Blender | Normal / Bump / Displacement |
| 12 | RS_Bump_Map | Normal / Bump / Displacement |
| 13 | RS_Camera_Map | Lookup / Environment |
| 14 | RS_Change_Range | Math - Scalar |
| 15 | RS_Color_Abs | Math - Color |
| 16 | RS_Color_Bias | Math - Color |
| 17 | RS_Color_Change_Range | Math - Color |
| 18 | RS_Color_Constant | Math - Color |
| 19 | RS_Color_Correct | Math - Color |
| 20 | RS_Color_Exp | Math - Color |
| 21 | RS_Color_Gain | Math - Color |
| 22 | RS_Color_Invert | Math - Color |
| 23 | RS_Color_Maker | Math - Color |
| 24 | RS_Color_Mix | Math - Color |
| 25 | RS_Color_Saturate | Math - Color |
| 26 | RS_Color_Splitter | Math - Color |
| 27 | RS_Color_Sub | Math - Color |
| 28 | RS_Color_To_HSV | Math - Color |
| 29 | RS_Color_User_Data | User Data |
| 30 | RS_Cosine | Math - Scalar |
| 31 | RS_Cross_Product | Math - Vector |
| 32 | RS_Curvature | Lookup / Environment |
| 33 | RS_Displacement | Normal / Bump / Displacement |
| 34 | RS_Displacement_Blender | Normal / Bump / Displacement |
| 35 | RS_Distance | Lookup / Environment |
| 36 | RS_Distorter | Utility |
| 37 | RS_Div | Math - Scalar |
| 38 | RS_Dot_Product | Math - Vector |
| 39 | RS_Environment | Lookup / Environment |
| 40 | RS_Exp | Math - Scalar |
| 41 | RS_Flakes | Procedural Pattern |
| 42 | RS_Floor | Math - Scalar |
| 43 | RS_Frac | Math - Scalar |
| 44 | RS_Fresnel | Lookup / Environment |
| 45 | RS_Gain | Math - Scalar |
| 46 | RS_HSV_To_Color | Math - Color |
| 47 | RS_Hair_Position | Hair / Special |
| 48 | RS_Hair_Random_Color | Hair / Special |
| 49 | RS_IOR_To_Metal_Tints | Math - Color |
| 50 | RS_Integer_User_Data | User Data |
| 51 | RS_Invert | Math - Scalar |
| 52 | RS_Jitter | Utility |
| 53 | RS_Ln | Math - Scalar |
| 54 | RS_Log | Math - Scalar |
| 55 | RS_MatCap | Lookup / Environment |
| 56 | RS_Max | Math - Scalar |
| 57 | RS_Maxon_Noise | Procedural Pattern |
| 58 | RS_Min | Math - Scalar |
| 59 | RS_Mix | Math - Scalar |
| 60 | RS_Mod | Math - Scalar |
| 61 | RS_Mul | Math - Scalar |
| 62 | RS_Multi_Map | Utility |
| 63 | RS_Neg | Math - Scalar |
| 64 | RS_Normal_Map | Normal / Bump / Displacement |
| 65 | RS_Normalize | Math - Vector |
| 66 | RS_OSL_Map | OSL |
| 67 | RS_Pavement | Procedural Pattern |
| 68 | RS_Physical_Sky | Lookup / Environment |
| 69 | RS_Pow | Math - Scalar |
| 70 | RS_Random_Color_Switch | Utility |
| 71 | RS_Ray_Switch | Lookup / Environment |
| 72 | RS_Rcp | Math - Scalar |
| 73 | RS_Round_Corners | Normal / Bump / Displacement |
| 74 | RS_Saturate | Math - Scalar |
| 75 | RS_Scalar_User_Data | User Data |
| 76 | RS_Shader_Switch | Utility |
| 77 | RS_Shave | Hair / Special |
| 78 | RS_Sign | Math - Scalar |
| 79 | RS_Sine | Math - Scalar |
| 80 | RS_Sprite | Image / File |
| 81 | RS_Sqrt | Math - Scalar |
| 82 | RS_State | Lookup / Environment |
| 83 | RS_Sub | Math - Scalar |
| 84 | RS_Surface_Tangent | Lookup / Environment |
| 85 | RS_Tangent | Math - Scalar |
| 86 | RS_Texture | Image / File |
| 87 | RS_Tiles | Procedural Pattern |
| 88 | RS_Tonemap_Pattern | Procedural Pattern |
| 89 | RS_TriPlanar | Lookup / Environment (alias) |
| 90 | RS_Triplanar | Lookup / Environment |
| 91 | RS_UV_Context_Projection | UV / Coordinate |
| 92 | RS_UV_Projection | UV / Coordinate |
| 93 | RS_Unit_Conversion | Utility |
| 94 | RS_Vector_Abs | Math - Vector |
| 95 | RS_Vector_Add | Math - Vector |
| 96 | RS_Vector_Bias | Math - Vector |
| 97 | RS_Vector_Change_Range | Math - Vector |
| 98 | RS_Vector_Div | Math - Vector |
| 99 | RS_Vector_Exp | Math - Vector |
| 100 | RS_Vector_Floor | Math - Vector |
| 101 | RS_Vector_Frac | Math - Vector |
| 102 | RS_Vector_Gain | Math - Vector |
| 103 | RS_Vector_Invert | Math - Vector |
| 104 | RS_Vector_Length | Math - Vector |
| 105 | RS_Vector_Ln | Math - Vector |
| 106 | RS_Vector_Log | Math - Vector |
| 107 | RS_Vector_Maker | Math - Vector |
| 108 | RS_Vector_Max | Math - Vector |
| 109 | RS_Vector_Min | Math - Vector |
| 110 | RS_Vector_Mix | Math - Vector |
| 111 | RS_Vector_Mod | Math - Vector |
| 112 | RS_Vector_Mul | Math - Vector |
| 113 | RS_Vector_Neg | Math - Vector |
| 114 | RS_Vector_Pow | Math - Vector |
| 115 | RS_Vector_Rcp | Math - Vector |
| 116 | RS_Vector_Saturate | Math - Vector |
| 117 | RS_Vector_Sign | Math - Vector |
| 118 | RS_Vector_Sqrt | Math - Vector |
| 119 | RS_Vector_Sub | Math - Vector |
| 120 | RS_Vector_To_Scalars | Math - Vector |
| 121 | RS_Vector_User_Data | User Data |
| 122 | RS_Volume_Color_Attribute | Volume / Special |
| 123 | RS_Volume_Scalar_Attribute | Volume / Special |
| 124 | RS_WireFrame | Procedural Pattern |
