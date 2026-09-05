# Redshift Math & Utility Texture Map Nodes -- MAXScript Property Reference

> **Environment:** 3ds Max 2025, Redshift 2026.3.1
> **Introspected:** 2026-03-03
> **Method:** `showProperties` on instantiated objects via MAXScript `execute()`
> **Superclass:** All nodes listed below are `textureMap` (superclass `material`)

---

## Table of Contents

1. [Arithmetic](#1-arithmetic)
2. [Mix / Blend](#2-mix--blend)
3. [Range Mapping](#3-range-mapping)
4. [Inversion](#4-inversion)
5. [Color Utilities](#5-color-utilities)
6. [Unary Math](#6-unary-math)
7. [Vector Operations](#7-vector-operations)
8. [Switching / Multi-Map](#8-switching--multi-map)
9. [Bias / Gain](#9-bias--gain)
10. [State / Ray Switch](#10-state--ray-switch)
11. [Blending (Bump & Displacement)](#11-blending-bump--displacement)
12. [Texture Utilities](#12-texture-utilities)
13. [Property Pattern Summary](#13-property-pattern-summary)

---

## 1. Arithmetic

All six arithmetic nodes share an identical property signature -- two scalar float inputs, each with an optional texture map override and enable toggle.

### RS_Add

Adds two scalar values: `output = input1 + input2`

| Property | Type | Default |
|----------|------|---------|
| `input1` | float | 0.0 |
| `input1_map` | texturemap | undefined |
| `input1_mapenable` | boolean | -- |
| `input2` | float | 0.0 |
| `input2_map` | texturemap | undefined |
| `input2_mapenable` | boolean | -- |

### RS_Sub

Subtracts two scalar values: `output = input1 - input2`

| Property | Type | Default |
|----------|------|---------|
| `input1` | float | 0.0 |
| `input1_map` | texturemap | undefined |
| `input1_mapenable` | boolean | -- |
| `input2` | float | 0.0 |
| `input2_map` | texturemap | undefined |
| `input2_mapenable` | boolean | -- |

### RS_Mul

Multiplies two scalar values: `output = input1 * input2`

| Property | Type | Default |
|----------|------|---------|
| `input1` | float | 0.0 |
| `input1_map` | texturemap | undefined |
| `input1_mapenable` | boolean | -- |
| `input2` | float | 0.0 |
| `input2_map` | texturemap | undefined |
| `input2_mapenable` | boolean | -- |

### RS_Div

Divides two scalar values: `output = input1 / input2`

| Property | Type | Default |
|----------|------|---------|
| `input1` | float | 0.0 |
| `input1_map` | texturemap | undefined |
| `input1_mapenable` | boolean | -- |
| `input2` | float | **1.0** |
| `input2_map` | texturemap | undefined |
| `input2_mapenable` | boolean | -- |

> **Note:** `input2` defaults to 1.0 (not 0.0) to avoid division by zero.

### RS_Min

Returns the minimum of two scalar values: `output = min(input1, input2)`

| Property | Type | Default |
|----------|------|---------|
| `input1` | float | 0.0 |
| `input1_map` | texturemap | undefined |
| `input1_mapenable` | boolean | -- |
| `input2` | float | 0.0 |
| `input2_map` | texturemap | undefined |
| `input2_mapenable` | boolean | -- |

### RS_Max

Returns the maximum of two scalar values: `output = max(input1, input2)`

| Property | Type | Default |
|----------|------|---------|
| `input1` | float | 0.0 |
| `input1_map` | texturemap | undefined |
| `input1_mapenable` | boolean | -- |
| `input2` | float | 0.0 |
| `input2_map` | texturemap | undefined |
| `input2_mapenable` | boolean | -- |

---

## 2. Mix / Blend

### RS_Mix

Linearly interpolates between two **scalar** values based on a mix amount: `output = lerp(input1, input2, mixAmount)`

| Property | Type | Default |
|----------|------|---------|
| `input1` | float | 1.0 |
| `input1_map` | texturemap | undefined |
| `input1_mapenable` | boolean | -- |
| `input2` | float | 1.0 |
| `input2_map` | texturemap | undefined |
| `input2_mapenable` | boolean | -- |
| `mixAmount` | float | 0.0 |
| `mixAmount_map` | texturemap | undefined |
| `mixAmount_mapenable` | boolean | -- |

### RS_Color_Mix

Linearly interpolates between two **color** values based on a mix amount: `output = lerp(input1, input2, mixAmount)`

| Property | Type | Default |
|----------|------|---------|
| `input1` | color | (color 255 255 255) |
| `input1_map` | texturemap | undefined |
| `input1_mapenable` | boolean | -- |
| `input2` | color | (color 255 255 255) |
| `input2_map` | texturemap | undefined |
| `input2_mapenable` | boolean | -- |
| `mixAmount` | float | 0.0 |
| `mixAmount_map` | texturemap | undefined |
| `mixAmount_mapenable` | boolean | -- |

---

## 3. Range Mapping

### RS_Change_Range

Remaps a **scalar** value from one range to another (with optional clamp).

| Property | Type | Default |
|----------|------|---------|
| `input` | float | 0.0 |
| `input_map` | texturemap | undefined |
| `input_mapenable` | boolean | -- |
| `old_min` | float | 0.0 |
| `old_min_map` | texturemap | undefined |
| `old_min_mapenable` | boolean | -- |
| `old_max` | float | 1.0 |
| `old_max_map` | texturemap | undefined |
| `old_max_mapenable` | boolean | -- |
| `new_min` | float | 0.0 |
| `new_min_map` | texturemap | undefined |
| `new_min_mapenable` | boolean | -- |
| `new_max` | float | 1.0 |
| `new_max_map` | texturemap | undefined |
| `new_max_mapenable` | boolean | -- |
| `clamp` | boolean | true |

### RS_Color_Change_Range

Remaps a **color** value from one range to another (with optional clamp). Has an additional `applyToAlpha` toggle.

| Property | Type | Default |
|----------|------|---------|
| `input` | color | (color 0 0 0) |
| `input_map` | texturemap | undefined |
| `input_mapenable` | boolean | -- |
| `old_min` | color | (color 0 0 0) |
| `old_min_map` | texturemap | undefined |
| `old_min_mapenable` | boolean | -- |
| `old_max` | color | (color 255 255 255) |
| `old_max_map` | texturemap | undefined |
| `old_max_mapenable` | boolean | -- |
| `new_min` | color | (color 0 0 0) |
| `new_min_map` | texturemap | undefined |
| `new_min_mapenable` | boolean | -- |
| `new_max` | color | (color 255 255 255) |
| `new_max_map` | texturemap | undefined |
| `new_max_mapenable` | boolean | -- |
| `applyToAlpha` | boolean | false |
| `clamp` | boolean | true |

---

## 4. Inversion

### RS_Invert

Inverts a scalar value: `output = 1.0 - input`

| Property | Type | Default |
|----------|------|---------|
| `input` | float | 0.0 |
| `input_map` | texturemap | undefined |
| `input_mapenable` | boolean | -- |

### RS_Color_Invert

Inverts a color value per-channel. Has an `applyToAlpha` toggle.

| Property | Type | Default |
|----------|------|---------|
| `input` | color | -- |
| `input_map` | texturemap | undefined |
| `input_mapenable` | boolean | -- |
| `applyToAlpha` | boolean | false |

---

## 5. Color Utilities

### RS_Color_Correct

Applies gamma, contrast, hue shift, saturation, and level adjustments to a color input.

| Property | Type | Default | Notes |
|----------|------|---------|-------|
| `input` | color | -- | Base color input |
| `input_map` | texturemap | undefined | |
| `input_mapenable` | boolean | -- | |
| `gamma` | float | 1.0 | 1.0 = no change |
| `gamma_map` | texturemap | undefined | |
| `gamma_mapenable` | boolean | -- | |
| `contrast` | float | 0.5 | 0.5 = no change |
| `contrast_map` | texturemap | undefined | |
| `contrast_mapenable` | boolean | -- | |
| `hue` | float | 0.0 | 0.0 = no shift |
| `hue_map` | texturemap | undefined | |
| `hue_mapenable` | boolean | -- | |
| `saturation` | float | 1.0 | 1.0 = no change |
| `saturation_map` | texturemap | undefined | |
| `saturation_mapenable` | boolean | -- | |
| `level` | float | 1.0 | Brightness multiplier |
| `level_map` | texturemap | undefined | |
| `level_mapenable` | boolean | -- | |
| `updatedMode` | boolean | true | Use updated calculation mode |
| `xsiMode` | boolean | false | XSI compatibility mode |

### RS_Color_Maker

Constructs a color from individual R, G, B, A scalar channels.

| Property | Type | Default |
|----------|------|---------|
| `red` | float | 0.0 |
| `red_map` | texturemap | undefined |
| `red_mapenable` | boolean | -- |
| `green` | float | 0.0 |
| `green_map` | texturemap | undefined |
| `green_mapenable` | boolean | -- |
| `blue` | float | 0.0 |
| `blue_map` | texturemap | undefined |
| `blue_mapenable` | boolean | -- |
| `alpha` | float | 1.0 |
| `alpha_map` | texturemap | undefined |
| `alpha_mapenable` | boolean | -- |

### RS_Color_Splitter

Splits a color into individual scalar channels. The `output` property selects which channel to output.

| Property | Type | Default | Notes |
|----------|------|---------|-------|
| `output` | integer | 0 | Channel selector (0=R, 1=G, 2=B, 3=A) |
| `input` | color | -- | |
| `input_map` | texturemap | undefined | |
| `input_mapenable` | boolean | -- | |

### RS_Color_Constant

A simple constant color value (no map inputs).

| Property | Type | Default |
|----------|------|---------|
| `color` | color | (color 255 255 255) |

### RS_HSV_To_Color

Converts HSV values to RGB color.

| Property | Type | Default |
|----------|------|---------|
| `input` | color | -- |
| `input_map` | texturemap | undefined |
| `input_mapenable` | boolean | -- |

### RS_Color_To_HSV

Converts RGB color to HSV values.

| Property | Type | Default |
|----------|------|---------|
| `input` | color | -- |
| `input_map` | texturemap | undefined |
| `input_mapenable` | boolean | -- |

---

## 6. Unary Math

### RS_Abs

Absolute value: `output = |input|`

| Property | Type | Default |
|----------|------|---------|
| `input` | float | 0.0 |
| `input_map` | texturemap | undefined |
| `input_mapenable` | boolean | -- |

### RS_Neg

Negation: `output = -input`

| Property | Type | Default |
|----------|------|---------|
| `input` | float | 1.0 |
| `input_map` | texturemap | undefined |
| `input_mapenable` | boolean | -- |

### RS_Pow

Power function: `output = base ^ exponent`

| Property | Type | Default |
|----------|------|---------|
| `base` | float | 0.0 |
| `base_map` | texturemap | undefined |
| `base_mapenable` | boolean | -- |
| `exponent` | float | 1.0 |
| `exponent_map` | texturemap | undefined |
| `exponent_mapenable` | boolean | -- |

### RS_Sqrt

Square root: `output = sqrt(input)`

| Property | Type | Default |
|----------|------|---------|
| `input` | float | 1.0 |
| `input_map` | texturemap | undefined |
| `input_mapenable` | boolean | -- |

### RS_Exp

Exponential function: `output = e ^ input`

| Property | Type | Default |
|----------|------|---------|
| `input` | float | 1.0 |
| `input_map` | texturemap | undefined |
| `input_mapenable` | boolean | -- |

### RS_Log

Logarithm: `output = log_base(input)`

| Property | Type | Default |
|----------|------|---------|
| `input` | float | 1.0 |
| `input_map` | texturemap | undefined |
| `input_mapenable` | boolean | -- |
| `base` | float | 1.0 |
| `base_map` | texturemap | undefined |
| `base_mapenable` | boolean | -- |

> **Note:** Default `base=1.0` produces `log_1(x)` which is undefined for most inputs. Set `base` to `2.718281828` for natural log or `10.0` for common log.

---

## 7. Vector Operations

### RS_Dot_Product

Computes the dot product of two vectors: `output = input1 . input2` (scalar result)

| Property | Type | Default |
|----------|------|---------|
| `input1` | point3 | -- |
| `input1_map` | texturemap | undefined |
| `input1_mapenable` | boolean | -- |
| `input2` | point3 | -- |
| `input2_map` | texturemap | undefined |
| `input2_mapenable` | boolean | -- |

### RS_Cross_Product

Computes the cross product of two vectors: `output = input1 x input2` (vector result)

| Property | Type | Default |
|----------|------|---------|
| `input1` | point3 | -- |
| `input1_map` | texturemap | undefined |
| `input1_mapenable` | boolean | -- |
| `input2` | point3 | -- |
| `input2_map` | texturemap | undefined |
| `input2_mapenable` | boolean | -- |

### RS_Normalize

Normalizes a vector to unit length: `output = input / |input|`

| Property | Type | Default |
|----------|------|---------|
| `input` | point3 | -- |
| `input_map` | texturemap | undefined |
| `input_mapenable` | boolean | -- |

### RS_Vector_Maker

Constructs a vector (point3) from individual X, Y, Z scalar components.

| Property | Type | Default |
|----------|------|---------|
| `x` | float | 0.0 |
| `x_map` | texturemap | undefined |
| `x_mapenable` | boolean | -- |
| `y` | float | 0.0 |
| `y_map` | texturemap | undefined |
| `y_mapenable` | boolean | -- |
| `z` | float | 0.0 |
| `z_map` | texturemap | undefined |
| `z_mapenable` | boolean | -- |

### RS_Vector_To_Scalars

Splits a vector into individual scalar components. The `output` property selects which component.

| Property | Type | Default | Notes |
|----------|------|---------|-------|
| `output` | integer | 0 | Component selector (0=X, 1=Y, 2=Z) |
| `input` | point3 | -- | |
| `input_map` | texturemap | undefined | |
| `input_mapenable` | boolean | -- | |

---

## 8. Switching / Multi-Map

### RS_Shader_Switch

Selects one of up to 10 color inputs (shader0..shader9) based on an integer selector, with a default fallback.

| Property | Type | Default | Notes |
|----------|------|---------|-------|
| `selector` | integer | 0 | Which shader slot to use |
| `selector_map` | texturemap | undefined | |
| `selector_mapenable` | boolean | -- | |
| `selector_offset` | integer | 0 | Offset added to selector |
| `shader0` | color | -- | Slot 0 |
| `shader0_map` | texturemap | undefined | |
| `shader0_mapenable` | boolean | -- | |
| `shader1` | color | -- | Slot 1 |
| `shader1_map` | texturemap | undefined | |
| `shader1_mapenable` | boolean | -- | |
| `shader2` | color | -- | Slot 2 |
| `shader2_map` | texturemap | undefined | |
| `shader2_mapenable` | boolean | -- | |
| `shader3` | color | -- | Slot 3 |
| `shader3_map` | texturemap | undefined | |
| `shader3_mapenable` | boolean | -- | |
| `shader4` | color | -- | Slot 4 |
| `shader4_map` | texturemap | undefined | |
| `shader4_mapenable` | boolean | -- | |
| `shader5` | color | -- | Slot 5 |
| `shader5_map` | texturemap | undefined | |
| `shader5_mapenable` | boolean | -- | |
| `shader6` | color | -- | Slot 6 |
| `shader6_map` | texturemap | undefined | |
| `shader6_mapenable` | boolean | -- | |
| `shader7` | color | -- | Slot 7 |
| `shader7_map` | texturemap | undefined | |
| `shader7_mapenable` | boolean | -- | |
| `shader8` | color | -- | Slot 8 |
| `shader8_map` | texturemap | undefined | |
| `shader8_mapenable` | boolean | -- | |
| `shader9` | color | -- | Slot 9 |
| `shader9_map` | texturemap | undefined | |
| `shader9_mapenable` | boolean | -- | |
| `default_shader` | color | -- | Fallback if selector is out of range |
| `default_shader_map` | texturemap | undefined | |
| `default_shader_mapenable` | boolean | -- | |

### RS_Random_Color_Switch

Randomly assigns colors to objects based on object ID or user data, with optional HSV jitter.

| Property | Type | Default | Notes |
|----------|------|---------|-------|
| `inInputID` | integer | 2 | ID source selector |
| `inUserData` | integer | -- | User data attribute |
| `inUserData_map` | texturemap | undefined | |
| `inUserData_mapenable` | boolean | -- | |
| `inFloatSeed` | integer | 123 | Random seed |
| `shader_input` | color array | -- | Array of color inputs |
| `shader_input_map` | texturemap array | -- | Array of map overrides |
| `shader_input_mapenable` | boolean array | -- | Array of enable flags |
| `shader_weight` | float array | -- | Weight per shader input |
| `inColJitterEnabled` | boolean | false | Enable HSV color jitter |
| `inHueVarMin` | float | 0.0 | Hue jitter minimum |
| `inHueVarMax` | float | 1.0 | Hue jitter maximum |
| `inHueSeed` | integer | 123 | Hue randomization seed |
| `inSaturationVarMin` | float | 0.0 | Saturation jitter minimum |
| `inSaturationVarMax` | float | 1.0 | Saturation jitter maximum |
| `inSaturationSeed` | integer | 123 | Saturation randomization seed |
| `inValueVarMin` | float | 0.0 | Value jitter minimum |
| `inValueVarMax` | float | 1.0 | Value jitter maximum |
| `inValueSeed` | integer | 123 | Value randomization seed |

### RS_Multi_Map

Maps different colors/textures to different material IDs or object IDs. Uses dynamic arrays for the map list.

| Property | Type | Default | Notes |
|----------|------|---------|-------|
| `default_color` | color | (color 255 255 255) | Fallback color |
| `default_map` | texturemap | undefined | |
| `default_mapenable` | boolean | -- | |
| `source` | integer | 0 | ID source (0=Material ID, etc.) |
| `on` | boolean array | -- | Enable per slot |
| `id` | integer array | -- | ID value per slot |
| `color` | color array | -- | Color per slot |
| `map` | texturemap array | -- | Map per slot |
| `mapenable` | boolean array | -- | Map enable per slot |

---

## 9. Bias / Gain

### RS_Bias

Applies bias curve to a scalar value: shifts midtones without affecting 0 or 1.

| Property | Type | Default | Notes |
|----------|------|---------|-------|
| `input` | float | 0.0 | Input value |
| `input_map` | texturemap | undefined | |
| `input_mapenable` | boolean | -- | |
| `bias` | float | 0.5 | 0.5 = no change |
| `bias_map` | texturemap | undefined | |
| `bias_mapenable` | boolean | -- | |

### RS_Gain

Applies gain curve to a scalar value: adjusts contrast around 0.5.

| Property | Type | Default | Notes |
|----------|------|---------|-------|
| `input` | float | 0.0 | Input value |
| `input_map` | texturemap | undefined | |
| `input_mapenable` | boolean | -- | |
| `gain` | float | 0.5 | 0.5 = no change |
| `gain_map` | texturemap | undefined | |
| `gain_mapenable` | boolean | -- | |

---

## 10. State / Ray Switch

### RS_State

Outputs various shading state information (position, normal, UVs, ray depth, etc.). The `output` property selects which state value to return.

| Property | Type | Default | Notes |
|----------|------|---------|-------|
| `output` | integer | 0 | State output selector |
| `tspace_id` | integer | 1 | Texture space ID |
| `tangents` | integer | 1 | Tangent mode |
| `trans_space` | integer | 0 | Transform space |
| `showRayFacingNormals` | boolean | true | Show ray-facing normals |
| `bounceLevelType` | integer | 0 | Bounce level type |

### RS_Ray_Switch

Returns different colors depending on ray type (camera, reflection, refraction, GI), with optional front/back face differentiation.

| Property | Type | Default | Notes |
|----------|------|---------|-------|
| `cameraSwitchFrontBack` | boolean | false | Enable front/back for camera rays |
| `cameraColor` | color | -- | Camera ray color (front) |
| `cameraColor_map` | texturemap | undefined | |
| `cameraColor_mapenable` | boolean | -- | |
| `cameraColorBack` | color | -- | Camera ray color (back face) |
| `cameraColorBack_map` | texturemap | undefined | |
| `cameraColorBack_mapenable` | boolean | -- | |
| `reflectionSwitch` | boolean | false | Enable reflection ray override |
| `reflectionSwitchFrontBack` | boolean | false | Enable front/back for reflection |
| `reflectionColor` | color | -- | Reflection ray color (front) |
| `reflectionColor_map` | texturemap | undefined | |
| `reflectionColor_mapenable` | boolean | -- | |
| `reflectionColorBack` | color | -- | Reflection ray color (back face) |
| `reflectionColorBack_map` | texturemap | undefined | |
| `reflectionColorBack_mapenable` | boolean | -- | |
| `refractionSwitch` | boolean | false | Enable refraction ray override |
| `refractionSwitchFrontBack` | boolean | false | Enable front/back for refraction |
| `refractionColor` | color | -- | Refraction ray color (front) |
| `refractionColor_map` | texturemap | undefined | |
| `refractionColor_mapenable` | boolean | -- | |
| `refractionColorBack` | color | -- | Refraction ray color (back face) |
| `refractionColorBack_map` | texturemap | undefined | |
| `refractionColorBack_mapenable` | boolean | -- | |
| `giSwitch` | boolean | false | Enable GI ray override |
| `giSwitchFrontBack` | boolean | false | Enable front/back for GI |
| `giColor` | color | -- | GI ray color (front) |
| `giColor_map` | texturemap | undefined | |
| `giColor_mapenable` | boolean | -- | |
| `giColorBack` | color | -- | GI ray color (back face) |
| `giColorBack_map` | texturemap | undefined | |
| `giColorBack_mapenable` | boolean | -- | |

---

## 11. Blending (Bump & Displacement)

### RS_Bump_Blender

Blends up to 3 bump map inputs on top of a base bump input, each with a weight.

| Property | Type | Default | Notes |
|----------|------|---------|-------|
| `baseInput` | point3 | -- | Base bump normal |
| `baseInput_map` | texturemap | undefined | |
| `baseInput_mapenable` | boolean | -- | |
| `bumpInput0` | point3 | -- | Bump layer 0 |
| `bumpInput0_map` | texturemap | undefined | |
| `bumpInput0_mapenable` | boolean | -- | |
| `bumpWeight0` | float | 0.0 | Weight for layer 0 |
| `bumpWeight0_map` | texturemap | undefined | |
| `bumpWeight0_mapenable` | boolean | -- | |
| `bumpInput1` | point3 | -- | Bump layer 1 |
| `bumpInput1_map` | texturemap | undefined | |
| `bumpInput1_mapenable` | boolean | -- | |
| `bumpWeight1` | float | 0.0 | Weight for layer 1 |
| `bumpWeight1_map` | texturemap | undefined | |
| `bumpWeight1_mapenable` | boolean | -- | |
| `bumpInput2` | point3 | -- | Bump layer 2 |
| `bumpInput2_map` | texturemap | undefined | |
| `bumpInput2_mapenable` | boolean | -- | |
| `bumpWeight2` | float | 0.0 | Weight for layer 2 |
| `bumpWeight2_map` | texturemap | undefined | |
| `bumpWeight2_mapenable` | boolean | -- | |
| `additive` | boolean | false | Additive blending mode |

### RS_Displacement_Blender

Blends up to 3 displacement inputs on top of a base displacement, each with a weight.

| Property | Type | Default | Notes |
|----------|------|---------|-------|
| `baseInput` | float | 0.0 | Base displacement value |
| `baseInput_map` | texturemap | undefined | |
| `baseInput_mapenable` | boolean | -- | |
| `displaceInput0` | float | -- | Displacement layer 0 |
| `displaceInput0_map` | texturemap | undefined | |
| `displaceInput0_mapenable` | boolean | -- | |
| `displaceWeight0` | float | 0.0 | Weight for layer 0 |
| `displaceWeight0_map` | texturemap | undefined | |
| `displaceWeight0_mapenable` | boolean | -- | |
| `displaceInput1` | float | -- | Displacement layer 1 |
| `displaceInput1_map` | texturemap | undefined | |
| `displaceInput1_mapenable` | boolean | -- | |
| `displaceWeight1` | float | 0.0 | Weight for layer 1 |
| `displaceWeight1_map` | texturemap | undefined | |
| `displaceWeight1_mapenable` | boolean | -- | |
| `displaceInput2` | float | -- | Displacement layer 2 |
| `displaceInput2_map` | texturemap | undefined | |
| `displaceInput2_mapenable` | boolean | -- | |
| `displaceWeight2` | float | 0.0 | Weight for layer 2 |
| `displaceWeight2_map` | texturemap | undefined | |
| `displaceWeight2_mapenable` | boolean | -- | |
| `additive` | boolean | false | Additive blending mode |

---

## 12. Texture Utilities

### RS_Jitter

Randomizes color, float, or integer values per object based on object ID or user data, with HSV jitter controls.

| Property | Type | Default | Notes |
|----------|------|---------|-------|
| `inInputID` | integer | 2 | ID source selector |
| `inUserData` | integer | -- | User data attribute |
| `inUserData_map` | texturemap | undefined | |
| `inUserData_mapenable` | boolean | -- | |
| `inColor` | color | -- | Base color to jitter |
| `inColor_map` | texturemap | undefined | |
| `inColor_mapenable` | boolean | -- | |
| `inHueVarMin` | float | 0.0 | Hue variation minimum |
| `inHueVarMax` | float | 1.0 | Hue variation maximum |
| `inHueSeed` | integer | 123 | Hue random seed |
| `inSaturationVarMin` | float | 0.0 | Saturation variation minimum |
| `inSaturationVarMax` | float | 1.0 | Saturation variation maximum |
| `inSaturationSeed` | integer | 123 | Saturation random seed |
| `inValueVarMin` | float | 0.0 | Value variation minimum |
| `inValueVarMax` | float | 1.0 | Value variation maximum |
| `inValueSeed` | integer | 123 | Value random seed |
| `inFloatMin` | float | 0.0 | Float output minimum |
| `inFloatMax` | float | 0.0 | Float output maximum |
| `inFloatSeed` | integer | 123 | Float random seed |
| `inIntegerMin` | integer | 0 | Integer output minimum |
| `inIntegerMax` | integer | 0 | Integer output maximum |
| `inIntegerSeed` | integer | 123 | Integer random seed |
| `numIMultipleOutputChannels` | integer | -- | Number of output channels |

### RS_Distorter

Distorts UV coordinates of a texture input using a distortion map.

| Property | Type | Default | Notes |
|----------|------|---------|-------|
| `distorter` | color | -- | Distortion source |
| `distorter_map` | texturemap | undefined | |
| `distorter_mapenable` | boolean | -- | |
| `texture` | color | -- | Texture to distort |
| `texture_map` | texturemap | undefined | |
| `texture_mapenable` | boolean | -- | |
| `inType` | integer | 0 | Distortion type |
| `inWrap` | integer | 1 | Wrap mode |
| `inAmount` | float | 1.0 | Distortion amount |
| `inX` | float | 0.1 | X distortion scale |
| `inY` | float | 0.1 | Y distortion scale |
| `inZ` | float | 0.1 | Z distortion scale |
| `inDelta` | float | 1.0 | Delta parameter |
| `inStep` | float | 1.0 | Step size |

### RS_Texture

The primary Redshift texture/bitmap node. Loads image files with full UV control, filtering, color management, and animation support.

| Property | Type | Default | Notes |
|----------|------|---------|-------|
| `startTime` | time | -- | Animation start time |
| `playBackRate` | float | -- | Animation playback rate |
| `endCondition` | integer | -- | Animation end behavior |
| `tex0` | bitmap | -- | The bitmap texture data |
| `tex0_filename` | filename | -- | File path to image |
| `tilingmode` | integer | 0 | Tiling mode |
| `tex0_gamma` | float | 1.0 | Input gamma |
| `map_channel` | integer | 1 | UV map channel |
| `mapping` | radiobtnIndex | 0 | Mapping projection type |
| `mirrorU` | boolean | false | Mirror in U direction |
| `mirrorV` | boolean | false | Mirror in V direction |
| `wrapU` | boolean | true | Wrap in U direction |
| `wrapV` | boolean | true | Wrap in V direction |
| `scale_x` | float | 1.0 | UV scale X |
| `scale_y` | float | 1.0 | UV scale Y |
| `scale_map` | texturemap | undefined | Map for scale |
| `scale_mapenable` | boolean | -- | |
| `offset_x` | float | 0.0 | UV offset X |
| `offset_y` | float | 0.0 | UV offset Y |
| `offset_map` | texturemap | undefined | Map for offset |
| `offset_mapenable` | boolean | -- | |
| `rotate` | float | 0.0 | UV rotation (degrees) |
| `rotate_map` | texturemap | undefined | Map for rotation |
| `rotate_mapenable` | boolean | -- | |
| `color_multiplier` | color | -- | Post-load color multiply |
| `color_multiplier_map` | texturemap | undefined | |
| `color_multiplier_mapenable` | boolean | -- | |
| `color_offset` | color | -- | Post-load color offset |
| `color_offset_map` | texturemap | undefined | |
| `color_offset_mapenable` | boolean | -- | |
| `alpha_multiplier` | float | -- | Alpha channel multiplier |
| `alpha_multiplier_map` | texturemap | undefined | |
| `alpha_multiplier_mapenable` | boolean | -- | |
| `alpha_offset` | float | -- | Alpha channel offset |
| `alpha_offset_map` | texturemap | undefined | |
| `alpha_offset_mapenable` | boolean | -- | |
| `alpha_is_luminance` | boolean | false | Derive alpha from luminance |
| `invalid_color` | color | -- | Color for missing textures |
| `invalid_color_map` | texturemap | undefined | |
| `invalid_color_mapenable` | boolean | -- | |
| `filter_enable_type` | integer | 2 | Filter mode |
| `filter_bicubic` | boolean | false | Use bicubic filtering |
| `prefer_sharp` | boolean | true | Prefer sharp filtering |
| `mip_bias` | float | 0.0 | Mipmap bias |
| `uv_context` | texturemap | -- | Custom UV context input |
| `uv_context_enable` | boolean | -- | Enable custom UV context |
| `tex0_colorSpace` | string | -- | OCIO color space |
| `tone_map_enable` | boolean | false | Enable tone mapping |

### RS_OSL_Map

Executes an Open Shading Language (OSL) shader as a texture map.

| Property | Type | Default | Notes |
|----------|------|---------|-------|
| `oslFilename` | filename | -- | Path to .osl file |
| `oslCode` | string | -- | Inline OSL source code |
| `oslSource` | integer | 0 | Source mode (0=file, etc.) |
| `numIMultipleOutputChannels` | integer | 0 | Number of output channels |

---

## 13. Property Pattern Summary

### Common Patterns

Almost every mappable property in Redshift follows the **triplet pattern**:

```
.propertyName          -- The scalar/color/vector value
.propertyName_map      -- Optional texturemap override
.propertyName_mapenable -- Boolean to enable/disable the map
```

When `_mapenable` is `true` and `_map` is assigned, the map output overrides the scalar value.

### Type Categories

| Input Type | MAXScript Type | Used By |
|------------|---------------|---------|
| Scalar | `float` | Arithmetic, Unary Math, Mix, Bias/Gain, Change Range |
| Color | `color` | Color Mix, Color Change Range, Color Correct, Shader Switch, Ray Switch |
| Vector | `point3` | Dot/Cross Product, Normalize, Bump Blender |
| Integer | `integer` | State output, Color Splitter output, Shader Switch selector |
| Array | `type array` | Multi Map, Random Color Switch (dynamic slot lists) |

### Node Complexity Tiers

| Tier | Properties | Nodes |
|------|-----------|-------|
| Minimal (1-3 props) | Single input + optional map | RS_Abs, RS_Neg, RS_Sqrt, RS_Exp, RS_Invert, RS_Normalize, RS_Color_Constant |
| Simple (6 props) | Two inputs + maps | RS_Add, RS_Sub, RS_Mul, RS_Div, RS_Min, RS_Max, RS_Bias, RS_Gain, RS_Pow, RS_Log, RS_Dot_Product, RS_Cross_Product |
| Medium (9 props) | Two inputs + mix + maps | RS_Mix, RS_Color_Mix |
| Complex (15+ props) | Multiple inputs/controls | RS_Change_Range, RS_Color_Change_Range, RS_Color_Correct, RS_Bump_Blender, RS_Displacement_Blender |
| Heavy (30+ props) | Dynamic arrays, many slots | RS_Shader_Switch, RS_Ray_Switch, RS_Random_Color_Switch, RS_Multi_Map, RS_Texture, RS_Jitter |

### MAXScript Creation Examples

```maxscript
-- Simple arithmetic
local addNode = RS_Add()
addNode.input1 = 0.5
addNode.input2 = 0.3

-- Map-driven mix
local mixNode = RS_Color_Mix()
mixNode.input1 = color 255 0 0      -- Red
mixNode.input2 = color 0 0 255      -- Blue
mixNode.mixAmount_map = RS_Texture()  -- Driven by texture
mixNode.mixAmount_mapenable = true

-- Range remapping
local remap = RS_Change_Range()
remap.old_min = 0.0
remap.old_max = 1.0
remap.new_min = 0.2
remap.new_max = 0.8
remap.clamp = true

-- Vector construction
local vec = RS_Vector_Maker()
vec.x = 1.0
vec.y = 0.0
vec.z = 0.0

-- Color correction chain
local cc = RS_Color_Correct()
cc.input_map = RS_Texture()
cc.input_mapenable = true
cc.gamma = 2.2
cc.saturation = 0.8
cc.level = 1.2
```
