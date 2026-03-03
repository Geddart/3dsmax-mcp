# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Redshift material tools: `create_redshift_material`, `get_redshift_material_info`, `set_redshift_material_properties`, `connect_redshift_texture`, `list_redshift_materials`
- 10 built-in presets (chrome, gold, copper, glass, plastic, rubber, ceramic, skin, sss_wax, emissive)
- Redshift API quick reference (`docs/redshift_api_reference.md`)
- Redshift introspection research files (`docs/research/rs_*.md`)
- Implementation plans for Redshift, tyFlow, RPManager, RailClone, and Forest Pack Pro extensions (`docs/PLAN_*.md`)
- This CHANGELOG file

### Fixed
- `material_ops.py`: RS_BumpMap → RS_Bump_Map (class didn't exist, caused silent failures)
- `material_ops.py`: Use RS_Bitmap instead of Bitmaptexture for Redshift textures (gains native color space control)
- `material_ops.py`: Use RS_Normal_Map with `tex0_filename` directly (not via RS_Bitmap to tex0 which expects a Bitmap)
- `material_ops.py`: Displacement now wires through RS_Displacement node instead of raw bitmap to slot
- `material_ops.py`: Skip AO compositing for Redshift (GI handles it; CompositeTexturemap name: param is bugged)
- `material_ops.py`: Added normal/bump/displacement slots to Redshift renderer config
- `render.py`: Changed `vfb:true` to `vfb:false` — prevents standard Max VFB from popping up during render
- `redshift.py`: RS_Displacement auto-creates child RS_Bitmap when file_path is provided

## [0.2.0] - 2025-03-01

### Added
- Forest Pack scatter tool (`scatter_forest_pack`) with native parameter array wiring
- Safe mode for MAXScript execution — blocks dangerous commands by default
- State Sets and camera sequence tools
- Wire parameters tool for connecting object parameters with expressions
- Data channel modifier operator graph builder
- Animation controllers (script, constraint, noise, expression, list)
- Material ops: `assign_material`, `set_material_property`, `set_material_properties`, `create_material_from_textures`
- OSL shader writing tool
- Multi/Sub-Object sub-material management
- Texture map creation and property configuration
- Material slot discovery (`get_material_slots`)
- Object inspection tools (`inspect_object`, `inspect_properties`, `inspect_modifier_properties`)
- Scene query and filtering (`find_class_instances`, `get_instances`, `get_dependencies`, `find_objects_by_property`)
- Batch modifier operations
- Build tools for procedural structures (houses, towers, castles, bridges, etc.)
- Grid placement and floor plan tools
- Viewport capture, model capture, screen capture
- Render with file save support
- Clone, hierarchy, transform, visibility, selection tools
- Scene management (hold/fetch/reset/save)
- Effects management (atmospheric and render effects)
- Development skill guide (`SKILL.md`)

## [0.1.0] - 2025-02-15

### Added
- Initial MCP server with TCP MAXScript bridge
- Core tools: `execute_maxscript`, `get_scene_info`, `create_object`, `delete_objects`
- Object property get/set
- Material listing
- Basic scene and object manipulation
