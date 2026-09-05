# Redshift API Quick Reference

**3ds Max 2025 / Redshift 2026.3.1** — Consolidated from live introspection.

---

## RS_Standard_Material — Properties by Layer

### Base
| Property | Type | Default |
|----------|------|---------|
| `base_color` | color | white |
| `base_color_weight` | float | 1.0 |
| `diffuse_roughness` | float | 0.0 |
| `metalness` | float | 0.0 |

### Reflection
| Property | Type | Default |
|----------|------|---------|
| `refl_color` | color | white |
| `refl_weight` | float | 1.0 |
| `refl_roughness` | float | 0.5 |
| `refl_ior` | float | 1.5 |
| `refl_aniso` | float | 0.0 |
| `refl_aniso_rotation` | float | 0.0 |

### Refraction
| Property | Type | Default |
|----------|------|---------|
| `refr_color` | color | white |
| `refr_weight` | float | 0.0 |
| `refr_roughness` | float | 0.0 |
| `refr_abbe` | float | 0.0 |
| `ss_depth` | float | 0.0 |
| `ss_scatter_color` | color | white |

### SSS (Subsurface Scattering)
| Property | Type | Default |
|----------|------|---------|
| `ms_amount` | float | 0.0 |
| `ms_color` | color | white |
| `ms_radius` | color | white |
| `ms_radius_scale` | float | 1.0 |
| `ms_phase` | float | 0.0 |
| `ms_mode` | int | 0 (0=point, 1=ray, 2=random walk) |

### Sheen
| Property | Type | Default |
|----------|------|---------|
| `sheen_color` | color | white |
| `sheen_weight` | float | 0.0 |
| `sheen_roughness` | float | 0.3 |

### Coat
| Property | Type | Default |
|----------|------|---------|
| `coat_color` | color | white |
| `coat_weight` | float | 0.0 |
| `coat_roughness` | float | 0.0 |
| `coat_ior` | float | 1.5 |
| `coat_aniso` | float | 0.0 |
| `coat_aniso_rotation` | float | 0.0 |

### Emission
| Property | Type | Default |
|----------|------|---------|
| `emission_color` | color | white |
| `emission_weight` | float | 0.0 |

### Opacity
| Property | Type | Default |
|----------|------|---------|
| `opacity_color` | color | white |
| `thin_walled` | bool | false |

### Geometry (special slots)
| Property | Type | Notes |
|----------|------|-------|
| `bump_input` | texturemap | Connect RS_Normal_Map or RS_Bump_Map |
| `displacement_input` | texturemap | Connect RS_Displacement |
| `coat_bump_input` | texturemap | Separate coat normal |
| `overall_color` | texturemap | Post-shader tint |

---

## Map Slots

Every `_map` slot has companion `_mapenable` (bool) and `_mapamount` (percent).

| Slot | Layer |
|------|-------|
| `base_color_map` | Base |
| `metalness_map` | Base |
| `refl_roughness_map` | Reflection |
| `refl_color_map` | Reflection |
| `refl_ior_map` | Reflection |
| `refl_aniso_map` | Reflection |
| `refr_color_map` | Refraction |
| `refr_roughness_map` | Refraction |
| `ss_depth_map` | Refraction |
| `ss_scatter_color_map` | Refraction |
| `ms_color_map` | SSS |
| `ms_amount_map` | SSS |
| `ms_radius_map` | SSS |
| `sheen_color_map` | Sheen |
| `sheen_weight_map` | Sheen |
| `sheen_roughness_map` | Sheen |
| `coat_color_map` | Coat |
| `coat_weight_map` | Coat |
| `coat_roughness_map` | Coat |
| `coat_ior_map` | Coat |
| `emission_color_map` | Emission |
| `opacity_color_map` | Opacity |
| `overall_color_map` | Geometry |
| `bump_input` | Geometry (no _mapenable) |
| `displacement_input` | Geometry (no _mapenable) |
| `coat_bump_input` | Geometry (no _mapenable) |

---

## Top 20 Texture Map Classes

| Class | Key Properties | Use Case |
|-------|---------------|----------|
| `RS_Bitmap` | tex0_filename, tex0_colorSpace, tilingmode | File textures |
| `RS_Normal_Map` | tex0_filename, flipY, scale, unbiasedNormalMap | Normal maps → bump_input |
| `RS_Bump_Map` | input_map, inputType (0=bump,1=normal), scale | Bump → bump_input |
| `RS_Displacement` | texMap_map, scale, map_encoding | Displacement → displacement_input |
| `RS_Maxon_Noise` | noise_type, octaves, color1, color2, coord_scale | Procedural noise |
| `RS_Tiles` | inPattern, inGroutColor, inTilesColor1 | Tile patterns |
| `RS_Triplanar` | imageX_map, imageY_map, imageZ_map, blendAmount, scale | Triplanar projection |
| `RS_AO` | maxDistance, numSamples, bright, dark, spread | Ambient occlusion |
| `RS_Curvature` | mode, radius, numSamples | Edge wear/dirt |
| `RS_Color_Correct` | input_map, gamma, contrast, hue, saturation | Color correction |
| `RS_Mix` | input1_map, input2_map, mixAmount_map | Blend two maps |
| `RS_Color_Mix` | input1_map, input2_map, mixAmount_map | Blend two colors |
| `RS_Change_Range` | input_map, old_min, old_max, new_min, new_max | Remap values |
| `RS_Fresnel` | ior, facing_color, perp_color | Facing ratio |
| `RS_Round_Corners` | radius, numSamples | Edge smoothing |
| `RS_Color_Layer` | Does NOT exist | — |
| `RS_Ramp` | Does NOT exist | — |
| `RS_State` | state_var, texN_map (N=0..63) | Conditional switching |
| `RS_Math_Abs` | input, input_map | Absolute value |
| `RS_Math_Mix_Color` | input1, input2, mixAmount | Color blend |

---

## All RS Material Classes

`RS_Standard_Material`, `RS_Material`, `RS_Car_Paint`, `RS_Hair`,
`RS_Principled_Hair`, `RS_Skin`, `RS_Incandescent`, `RS_Architectural`,
`RS_Toon_Material`, `RS_Contour`, `RS_SSS`, `RS_Surface`, `RS_Volume`,
`RS_Standard_Volume`, `RS_Matte_Shadow_Catcher`, `RS_Sprite`,
`RS_Material_Blender`, `RS_Material_Switch`, `RS_Random_Material_Switch`,
`RS_Ray_Switch_Material`, `RS_Material_Output`, `RS_Store_Color_To_AOV`,
`RS_OpenPBR_Material`, `RS_OSL_Material`

---

## RS_Bitmap Quick Reference

| Property | Type | Notes |
|----------|------|-------|
| `tex0_filename` | string | File path |
| `tex0_colorSpace` | string | "sRGB", "Raw", "ACEScg", "scene-linear Rec.709-sRGB" |
| `tilingmode` | int | 0=wrap, 1=mirror, 2=clamp, 3=decal |
| `tex0_gammaoverride` | float | Manual gamma value |
| `scale` | point2 | UV scale |
| `offset` | point2 | UV offset |
| `rotate` | float | UV rotation (degrees) |

---

## Non-Existent Classes (Common Misconceptions)

These do NOT exist in Redshift 2026.3.1:
`RS_Noise`, `RS_Ramp`, `RS_Gradient_Ramp`, `RS_Stencil`, `RS_Color_Layer`,
`RS_UDIM_Texture`, `RS_UVProject`, `RS_UV_Remap`
