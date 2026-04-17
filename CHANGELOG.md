# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.5.3.1-fork] - 2026-04-17

Bugfix release on top of v0.5.3+fork after a full trace of the server start/stop and MCP slot logic.

### Fixed
- **`pyproject.toml` PEP 440 compliance** (`9a571c7`) — version was `0.5.3-fork` which `uv` refused to parse (`-` is not a valid PEP 440 separator). Changed to `0.5.3.1+fork` (PEP 440 local-version segment uses `+`). Symptom was the Claude Code MCP entry showing "X failed" with no obvious error surface.
- **`introspect_osl` backslash paths in verbatim strings** (`054f0ed`) — `safe_string()` was being applied to OSL paths before injection into MAXScript verbatim strings (`@"..."`), doubling backslashes. Windows paths like `C:\OSL\foo.osl` became `C:\\OSL\\foo.osl` and `OSLPath` would not resolve. Fix uses raw path with stray-quote stripping for the verbatim branch.
- **`install.py` non-atomic file writes** — `copy_elevated()` now writes to a `.tmp` sibling then `os.replace()`s atomically, both for the local and the elevated path. Prevents Max from reading a half-written `mcp_autostart.ms` during install (the historical cause of the `global fn M` startup parse error).
- **`server.py` plugin loading silently swallowed all `ImportError`** — now distinguishes a genuinely missing plugin module (silent skip, expected) from a missing transitive dependency or syntax error (warning logged). Prevents the silent feature-loss class of bug.
- **TCP transport had no retry on `ConnectionRefusedError`** — `_send_via_tcp` now retries once after 500ms before raising. Handles the narrow race where Max is mid-restart (listener stopped but not yet rebound).

## [0.5.3-fork] - 2026-04-17

Selective integration of upstream `cl0nazepamm/3dsmax-mcp` v0.5.3 (`abb87e5`) and v0.5.4 (`0dc3d65`). The fork is not a linear descendant of upstream — the cascade of deletions in upstream's v0.5.2 dropped modules this fork actively ships, so six upstream commits were skipped.

### Added
- `list_wireable_params`: bounded walk with new optional params `max_visits` (20000), `max_results` (500), `max_ms` (5000), `max_fanout` (200). Iterative visited-set walk replaces naive recursive DFS. Returns `__truncated__` synthetic terminal entry on cap trip. Prevents multi-minute main-thread hangs on rigs (Skin/biped/CAT), Multi/Sub materials, and particle systems. (Upstream `0dc3d65` / v0.5.4, cherry-picked)
- `introspect_osl` tool — lightweight MAXScript reflection for materials/texmaps/OSLMaps with bounded output. `introspect_class` now redirects OSL classes. (Upstream `49dd51c`, manually applied)
- `safe_value()` helper in `src/helpers/maxscript.py` — auto-protects backslash paths in MAXScript value expressions via verbatim-string coercion. Applied to all property-assignment sites in `material_ops.py` (including local Redshift additions). (Upstream `55aa5da`, manually applied)
- `install.py`: per-Max-version `.gup` deployment via new `gup_src_for()` helper + `GUP_SRC_DEFAULT`/`GUP_SRCS` globals; elevated-mkdir fallback (PowerShell RunAs) for `scripts/mcp` directory when Max is installed under Program Files. (Upstream `36c90c3` + `e2cd040`, cherry-picked — applied cleanly)
- `native/bin/mcp_bridge_2027.gup` — pre-built C++ plugin binary for Max 2027 (dormant on current 2024/2025 installs).

### Changed
- `native/bin/mcp_bridge.gup` updated to upstream's v0.5.4 compiled state (1072128 → 1079296 bytes). The running binary also contains upstream code from `c597ec0` (learning_handlers.cpp +96 lines, inspect_handlers.cpp +2 lines) that was NOT cherry-picked into source. Rebuilding from source will produce a binary missing those features. Accept for now; revisit if we diverge native code.

### Fixed
- `native/src/handlers/controller_handlers.cpp`: `ListWireableParams` replaced with iterative bounded walk, visited set (skip shared sub-anim subtrees), try/catch on every `NumSubs`/`SubAnim`/`SubAnimName` call to contain third-party plugin exceptions.

### Skipped (incompatible with fork surface)
- Upstream `ef33eca` — removed `verification.py`. Fork keeps all `*_verified` tools (`create_object_verified`, `transform_object_verified`, `assign_material_verified`, `set_material_verified`, `set_modifier_state_verified`, `set_object_property_verified`, `add_modifier_verified`, `create_tyflow_basic_verified`, `create_tyflow_scatter_from_objects_verified`).
- Upstream `f969ebb` — removed `grid.py` (`place_circle`, `place_grid_array`, `place_on_grid`), `build.py` (`build_floor_plan`, `build_structure`), `plugin_workflows.py` (`discover_plugin_classes`, `discover_plugin_surface`), `workflows.py`, `capture_model` alias. Fork keeps all.
- Upstream `1603a85` + `abb87e5` — README tool-count rewrite to 110 and "v0.5.2 Notice" block. Fork ships ~140+ tools.
- Upstream `c597ec0` + `b8643b4` — Max 2027 SDK support and VS 2022 build docs. Not applicable to 2024/2025 targets.

## [0.5.2] - 2026-04-01

### Added
- **Native C++ bridge** — 76 pure SDK handlers via named pipe (`\\.\pipe\3dsmax-mcp`), bypassing MAXScript for scene reads, object CRUD, modifiers, materials, controllers, viewport capture, and more
- **Protocol v2** — request IDs, response metadata (transport, timing, safe mode), ping command
- **Verified workflow tools** — 9 tools that combine action + delta tracking + readback in one call (`create_object_verified`, `assign_material_verified`, `set_material_verified`, `add_modifier_verified`, `transform_object_verified`, etc.)
- **Scene snapshots & delta tracking** — `get_scene_snapshot`, `get_selection_snapshot`, `get_scene_delta` with per-client session scoping
- **Session context** — `get_session_context` combines bridge status + capabilities + snapshot in one call
- **Plugin discovery system** — `discover_plugin_surface`, `get_plugin_manifest`, `inspect_plugin_class`, `inspect_plugin_instance` with MCP resources for manifests/guides/recipes/gotchas
- **File access tools** — `inspect_max_file`, `merge_from_file`, `batch_file_info`, `search_max_files` (inspect .max files without opening)
- **Scene organization** — `manage_layers`, `manage_groups`, `manage_selection_sets` via pure C++ SDK
- **SDK learning tools** — `walk_references`, `map_class_relationships`, `learn_scene_patterns`, `watch_scene`
- **Material replacement** — `replace_material`, `batch_replace_materials`
- **RailClone style graph introspection** — `get_railclone_style_graph` reads exposed bases/segments/parameters
- **Multi-view capture** — `capture_multi_view` stitches 4 viewport angles into one image
- **Coercion types** — `StrList`, `IntList`, `FloatList`, `DictList` auto-coerce single values into lists
- **Shared helpers** — `safe_string`, `safe_name`, `normalize_subanim_path` in `src/helpers/maxscript.py`
- **Installer/uninstaller** — `install.py` and `uninstall.py` for one-step C++ plugin deployment and agent registration
- **Safe mode config** — `mcp_config.ini` shared between C++ bridge and MAXScript listener
- **14 test modules** — full test suite with mocked bridge (65 tests)
- **Enhanced MAXScript listener** — full JSON spec escaping (`\uXXXX`, control chars), `hexToInt`, `ping` command, inline safe mode blocklist

### Changed
- `MaxClientManager` now uses `transport="auto"` — tries native pipe first, falls back to TCP for port-based slot routing
- `MaxClientManager` exposes `native_available` property for upstream tool compatibility
- MAXScript listener upgraded to protocol v2 with `requestId` echo and `meta` block
- `buildResponse` now includes timing, command type, and safe mode status
- `execute_maxscript` gains `command` alias parameter (LLMs sometimes send wrong kwarg name)
- Plugin tool loading expanded: `plugins` and `plugin_workflows` added to `plugins.toml`

### Fixed
- `safeExecute` was undefined in our MAXScript listener — replaced with upstream's inline blocklist
- Enhanced `escapeJsonString` handles all control characters, backspace, form feed, `\uXXXX`
- Protocol v2 client strips UTF-8 BOM, validates request IDs, adds client round-trip timing

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
