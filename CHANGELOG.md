# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.4.0] - 2026-03-26

### Added
- **Multi-instance MCP support** — control up to 3 simultaneous 3ds Max instances
  - 3 slot system (ports 8765, 8766, 8767) with automatic slot assignment
  - `list_max_instances` tool — discover running 3ds Max instances
  - `set_active_instance` tool — switch which instance receives commands
  - `execute_maxscript` now accepts optional `slot` parameter for parallel agent control
  - `MaxClientManager` proxy class — routes commands transparently, zero changes to existing tools
- **MAXScript Manager UI** — `mcp_manager.ms` rollout dialog showing PID, slot, port, status
- **Toolbar buttons** — MCP1/MCP2/MCP3 toggle buttons replace old Start/Stop
- **Smart autostart** — tries slots 1-3 in order, picks first free port
- `export_tyflow_cache` tool — export tyFlow particles to tyCache files

### Fixed
- Chained .NET method calls crash MAXScript parser (two-step PID capture)
- Removed `dotNet.setLifetimeControl #dotnet` which caused .NET GC to collect TcpListener
- Orphaned timer guard in onTick prevents stale timers from killing active server
- Defensive cleanup in `stop()` — sets timer/listener to undefined after stopping

## [0.3.0] - 2026-03-22

### Added
- **tyFlow 2.0 (Zenith) Inferno tools** — 6 new tools for GPU smoke/fire simulation:
  - `create_tyflow_inferno` — one-call fire/smoke setup with 4 presets (fire, smoke, explosion_smoke, campfire)
  - `get_tyflow_volume_data` — sample density/fuel/temperature/color/velocity from Inferno fluid grids
  - `convert_tyflow_temperature` — celsius/fahrenheit/kelvin conversion via tyFlow API
  - `set_tyflow_inferno_display` — configure viewport ray marching, AO, shadows, glow
  - `export_tyflow_inferno_vdb` — configure VDB export channels, paths, and frame ranges
  - `set_tyflow_global_event` — mark events as global (tyFlow 2.0 feature)
- **57 plugin tools** for tyFlow, RPManager, RailClone, and Forest Pack with plugin config system (`plugins.toml`)
- 13 core tyFlow particle tools (create, inspect, modify, fracture, PhysX, presets)
- 15 RPManager tools (pass management, visibility, capture sets, scripts, rendering)
- 13 RailClone tools (library styles, fences, walls, railings, arrays, parameters)
- 16 Forest Pack tools (scatter, surfaces, sources, transforms, LOD, clustering, animation)
- Redshift material tools with 10 built-in presets
- Redshift API quick reference (`docs/redshift_api_reference.md`)
- Implementation plans for all 5 plugins (`docs/PLAN_*.md`)
- tyFlow 2.0 introspection results: 15 confirmed Inferno operators, full property maps (`docs/research/tyflow2_introspection.md`)
- Plugin enable/disable via `plugins.toml` or `3DSMAX_MCP_PLUGINS` env var

### Fixed
- `_sa_name()`: SubAnim access now uses underscores (`#PhysX_Shape`) instead of broken quoting (`#'PhysX Shape'`)
- All tyflow and redshift tools: extract `.get("result", "")` from `send_command()` dict (was returning raw dict, causing pydantic validation errors)
- `material_ops.py`: RS_BumpMap → RS_Bump_Map, RS_Bitmap for textures, RS_Normal_Map direct filename
- `render.py`: `vfb:false` prevents VFB popup during render
- RPManager: `fRefresh()` crash fix, `RMopenFloater()` guards, before/after script approach for layer visibility
- E2E bugs: reserved word collisions, JSON escaping, constructor conflicts, read-only property handling

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
