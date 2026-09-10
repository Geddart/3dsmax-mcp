# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.5.5+fork] - Unreleased

Integration of upstream **1.5.5** (`32af329`) on top of fork `72b454f` (0.5.3.1+fork), plus the
review round on PR #2.

> **Native binaries in this round:** Max 2025 and Max 2027 now carry the source fixes.
> The 2027 binary was rebuilt with its matching SDK and has not yet been live-tested.
> `mcp_bridge_2023/2024/2026.gup` are unchanged and predate both the `vfb:false` render
> fix and the overlapped-I/O transport; rebuild each against its matching SDK before shipping.

### Added
- **Progressive tool discovery** — the `progressive` profile advertises only `list_toolsets`,
  `describe_toolset` and `call_tool`; operational tools are described on demand. Schemas are
  byte-identical to the full profile (see `docs/PROGRESSIVE_AUDIT.md` for the measurements).
- **Async job handles** — `max_job_submit` / `max_job_status` / `max_job_result` / `max_job_list` /
  `max_job_wait` / `max_job_cancel` / `max_job_forget` schedule one-shot main-thread callbacks and
  return immediately. Job scripts can call `mcpJobProgress` and `mcpJobCheckCancel()`;
  cancellation is cooperative and an unknown outcome is never reported as completion.
- **Process-scoped UI automation** — `max_ui_windows`, `max_ui_inspect`, `max_ui_invoke`,
  `max_ui_set_value`, `max_ui_send_keys`, `max_ui_wait`, `max_ui_capture`, each bound to a
  specific Max PID, with native fallbacks for rollout controls that expose no UIA patterns.
- Upstream 1.5.5 structured results, atomic scene edits and OpenPBR material defaults.

### Changed
- **TCP transport and numbered slots removed** in favour of upstream's per-process native
  instance routing (deliberate, approved decision). Instances are now selected by native
  PID via `list_max_instances` / `select_max_instance(pid)` / `get_selected_max_instance` /
  `release_max_instance` (module `maxmcp/tools/routing.py`); the old
  slot/port macros, toolbar scripts and the instance-id string API are retired. Named pipes are the only transport.
- 187 of the 188 previously advertised tool names are retained (`set_active_instance` became `select_max_instance(pid)` in the review round); removed upstream native operations fall
  back to their preserved MAXScript paths.
- `skills/3dsmax-mcp-dev/` split into `SKILL.md` (served to agents) plus `fork-reference.md`
  (long-tail plugin lessons).
- `scripts/verify_feature_catalog.py` is parametrized (argparse + environment variables) and
  compares against a **git ref** (default `master`) instead of a hardcoded sibling checkout.

### Fixed
- **Plain-pipe fallback removed** — the unauthenticated/unframed fallback path could talk to a
  half-initialized bridge; discovery now probes named pipes without opening throwaway
  connections.
- **Job-registry wedge** — a terminal job state is published only after the Max reservation is
  released, completed state is latched, elapsed time freezes, transient sharing violations are
  tolerated and non-finite progress values are discarded.
- **UI tools bound to the wrong process** — every UI call now resolves and verifies its target
  PID, waits pass their remaining deadline to the provider process, and keyboard input requires
  the exact observed control to hold focus.
- **`safe_value()` regression in `set_texture_map_properties`** — `maxmcp/tools/material_ops.py`
  emitted the raw property value into MAXScript, so a Windows path (`"C:\tex\normal.png"`) had
  its backslash escapes eaten (`\t` became a tab) and the texture silently failed to load. The value is
  wrapped with `safe_value()` again, matching every other assignment site; covered by
  `tests/test_material_ops.py`.
- **SKILL.md restored** — the must-know Redshift / RPManager / tyFlow / Forest Pack / RailClone
  rules are back in `SKILL.md` (what `resource://3dsmax-mcp/skill` and the `max_assistant` prompt
  actually serve) instead of living only in `fork-reference.md`, which now carries the long tail
  and is pointed at loudly from the top of `SKILL.md`.
- **Native shutdown fixes** — overlapped I/O with proper `OVERLAPPED` pointers, idle client I/O
  observing shutdown, connect cancellation completing before its event is freed, and expired
  queued main-thread work being skipped rather than executed against a dead caller stack.
- **Native binary rebuilt for Max 2025** — `native/bin/mcp_bridge_2025.gup` is a true Release
  build carrying the transport/executor fixes above and the `vfb:false` render fix
  (4 593 664 -> 2 135 552 bytes). A repeat build has matching size, imports and fix strings;
  the committed binary was retained. The 2023/2024/2026 binaries still require rebuilding.
- mcp_bridge_2027.gup rebuilt from source with the 2027 SDK; not yet live-tested
- **`render_scene` native handler double-pass with Redshift** — `native/src/handlers/render_handlers.cpp` was issuing `render … vfb:true …`, which on a Redshift renderer caused two full render passes per call: one into the VFB display buffer, then a second to satisfy the `outputFile:` save. Doubled render cost per tool call and doubled the window in which `RSScene is locked` / Scene.cpp:402 crashes could fire. Changed to `vfb:false` to match the Python fallback in `src/tools/render.py` (which was already correct). Reproduced in 822 HeissluftBallon envelope work 2026-04-20. Rebuild `mcp_bridge.gup` from `native/` (see README "Building from source") to pick up the fix.

#### PR #2 review round

- **The instance fence covered only the `max_ui_*` tools** — `protected_pids.json` /
  `MCP_UI_DENY_PIDS` were read exclusively by `maxmcp/max_ui.py`, so every MAXScript tool routed
  around them. Fencing the production Max and then closing the dev Max made the production one
  "the single live instance", and the next `execute_maxscript` / `scene_patch` / `max_job_render`
  ran inside it with `target_source='single'` and no refusal. The fence now lives in
  `maxmcp/pid_fence.py` and is enforced in `MaxClient._default_target()` (claimed *and* single
  branches) and `select_max_instance()`, raising the new `ProtectedMaxInstanceError`.
- **A fence entry lapsing across a Max restart was at least made visible** — a bare PID is
  recycled by Windows, so the protection can quietly protect nothing (and can start refusing an
  unrelated dev Max that inherited the number). `list_max_instances` now reports `protected` per
  instance plus a `protected_fence` block whose `lapsed_pids` names entries that match nothing
  live, so the lapse is seen rather than assumed away. The fence itself stays per-PID and must be
  renewed after a restart.
- **Routing metadata was stripped from every response in the default tripback mode** — the docs
  promised `target_pid` / `target_pipe` / `target_source` on every response that reaches Max, but minimal mode
  attached transport only on errors and `_slim_transport` copied just `transport` and the dead
  `fallback_error`. Slim transport now carries the three routing keys and is attached on the
  minimal-mode success path too; the `fallback_error` branch (whose only producer this round
  deleted) is gone.
- **`scripts/verify_ui_jobs.py` auto-drove a second Max** — the acceptance script picked
  `others[0]` from the live instance list and executed MAXScript in it, which on this workstation
  is the production Max, possibly mid-render. The isolation check is now opt-in via
  `--other-pid N` and refuses a protected PID.
- **A racing foreground could swallow `SendKeys` input and still be reported as committed** —
  `SendWait` injects into the input desktop, not into a PID-scoped window, so a dialog that stole
  focus after `Set-ControlFocus` received the keystroke. `max_ui_set_value(commit=True)` and
  `max_ui_send_keys` now re-read the foreground PID after the injection and report
  `foreground_changed` (with `committed=false` / `completed=false`) instead of claiming success.
- **A SKILL.md lesson contained raw `0x03` bytes** — the `\3` in `\3dsmax-mcp` was interpreted as
  an octal escape and written into the file, erasing both the trigger and the symptom of the very
  pitfall the line documents. `SKILL.md` is served verbatim as an MCP resource, so every agent
  loading the skill received the control character. Rewritten, and the file is control-byte clean.

#### PR #2 review round 2

- **`max_versions` fencing removed entirely** — the key compared against the bridge's
  `max_version`, which is the compile-time `MAX_SDK_VERSION` written by
  `native/src/bridge_gup.cpp`, identical for every Max of a release. `{"max_versions": [27000]}`
  therefore fenced the production *and* the dev Max 2025 and wedged routing completely.
  `denied_max_versions()`, its checks in `_default_target` / `select_max_instance` /
  `resolve_pid`, and the `protected_fence.max_versions` field are gone. The fence is per-PID,
  lapses on restart, and `protected_fence.lapsed_pids` makes that visible; a restart-proof fence
  needs the bridge to publish a stable identity (scene path / operator label) and is future work.
- **`max_ui_wait` authorised its target differently from the other six UI tools** — it resolved
  `pid` to an int once and then fed that int back into `request()`, which re-authorised it
  through the explicit-pid branch (registry membership required). A session-resolved PID that is
  not in the registry worked everywhere except in `max_ui_wait`. The original `pid` argument is
  now passed on every probe; the resolved target is used only for the reported `pid`.
- **Two process-liveness policies disagreed** — `maxmcp/max_ui._process_is_live` treated any
  `OpenProcess` failure as death (an access-denied Max looked dead), while
  `maxmcp/max_client._process_alive` counts only `ERROR_INVALID_PARAMETER` as proof. `max_ui`
  now delegates to `max_client`, so there is a single policy.
- **`max_ui_set_value` could silently write an empty string** — `value` had defaulted to `''`
  once `pid` became optional and moved ahead of it, so an omitted value was a valid empty write.
  It is now `None` by default and raises `ValueError('value is required')`.
- **"Did this request reach Max?" was decided by string matching** — `is_provably_unsent` parsed
  message text, where `'timed out waiting for named pipe'` is a prefix of the ambiguous
  read-timeout message and only marker ordering kept the two apart. `maxmcp/max_client` now
  raises the new `PipeNotConnectedError(ConnectionError)` at every raise site that fires before
  the first `WriteFile` (pipe not found, open failed, wait timed out, pipe vanished, connection
  lock timeout), and classification is by type; the markers remain as a fallback only.
- **`select_max_instance` could pin a PID with no instance record** — it synthesised
  `\.\pipe\3dsmax-mcp-pid-<pid>` and pinned whenever the process was alive and something
  answered that name. Selection now refuses outright with `NoMaxInstanceError` naming
  `list_max_instances`.
- **Docs overpromised routing metadata** — "reported on every response" is now "every response
  that reached Max"; `list_max_instances`, `max_job_*` and `max_ui_*` never call
  `send_command` and emit no transport block (the `max_ui_*` results carry their own `pid`).
- **Every tool call resolved the routing target twice** — `MaxClient.native_available` ran a full
  `_default_target()` (glob the instances dir, `OpenProcess` per record, `WaitNamedPipeW` per
  record) and `send_command` immediately repeated it, across ~70 `if client.native_available:`
  sites. The resolved target is now memoised on the client for `MaxClient._TARGET_CACHE_TTL`
  (1.5 s, monotonic clock) and shared by both paths. Only successes are cached: `Ambiguous`/`No`/
  `ProtectedMaxInstanceError` propagate untouched, so a Max that appears or a fence that lifts is
  seen on the next call. The cache is dropped by `select_max_instance`, `release_max_instance` and
  any `ConnectionError`/`TimeoutError` out of a send, so a vanished Max is re-resolved at once.

<!-- native -->
### Fixed (native bridge)
- **Max hung on exit for up to 120 s per in-flight request** — `MCPBridgeGUP::Stop()` joined the pipe client threads (`StopPipe()`) *before* shutting the executor down. A client thread inside `CommandDispatcher::Dispatch` -> `MainThreadExecutor::ExecuteSync` was waiting for a `WM_MCP_EXECUTE` that the main thread could no longer pump, because it was blocked in `std::thread::join()` on that same thread. New `MainThreadExecutor::BeginShutdown()` is now the first thing `Stop()` calls: it closes a submission gate (later `ExecuteSync` calls from background threads throw immediately instead of posting) and completes every queued/deferred work item with an error, so the joins below it return at once.
- **Leaked work items on shutdown** — `MainThreadExecutor::Shutdown()` called `DestroyWindow()` while `WM_MCP_EXECUTE` messages were still queued. Windows discards those messages, leaking the heap `shared_ptr<WorkItem>` each one owns and leaving its waiter to sleep out the full timeout. `DrainPendingWork()` now `PeekMessage`-drains the queue first, deletes the raw pointers and wakes each waiter with an error.
- **`CompletePipeIO` swallowed real wait failures** — `WAIT_FAILED` (and a null shutdown event) were indistinguishable from "shutdown was signalled". Both are now reported via `OutputDebugString` (`LogPipeIOFailure`); the cancel-and-drain behaviour is unchanged.

### Changed (native bridge)
- `PipeIOEvent::Reset()` lets one event be reused across the chunks of a request/response. `PipeServer::ReadRequest`/`WriteResponse` no longer create and close a kernel event every 4 KB.
- `native/CMakeLists.txt` gained `option(MCP_BUILD_TESTS OFF)`, which pulls `native/tests` in via `add_subdirectory` and registers it with CTest. `native/tests` still configures standalone.
- `native/tests/transport_tests.cpp`: new coverage for shutdown waking a queued waiter promptly, `ExecuteSync` failing fast once shutting down, `Initialize()` reopening the gate, and the null-shutdown / event-reuse paths in `pipe_io.h`.
- `native/bin/mcp_bridge_2025.gup` rebuilt from source as a true Release build (4 593 664 -> 2 135 552 bytes; the committed binary was an unoptimized link — 2x `.text`, 6x `.pdata`, extra `.idata`/`.tls`/`.00cfg` sections — and predated the overlapped-I/O transport entirely). Binaries for 2023/2024/2026/2027 were **not** rebuilt: only the Max 2025 SDK is installed on this machine.
<!-- /native -->

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
