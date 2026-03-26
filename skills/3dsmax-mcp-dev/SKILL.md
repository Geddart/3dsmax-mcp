---
name: 3dsmax-mcp-dev
description: Practical rules, tool choices, and common failure modes when developing 3dsmax-mcp tools (Python MCP + MAXScript bridge). Use this when adding new tools, writing bridge MAXScript, or debugging TCP/JSON issues.
---

# 3dsmax-mcp Development Guide (Clean Version)

This guide is the **single source of truth** for building and debugging 3dsmax-mcp tools.

---

## 1) Hard Rules

### Materials
- **Never use `execute_maxscript` for material work.**
- Always use:
  - `assign_material`
  - `set_material_property`
  - `set_material_properties`
  - `set_sub_material` (Multi/Sub slot management)

Only use `execute_maxscript` for material-adjacent tasks that have **no dedicated tool**, such as:
- file I/O
- creating texture map objects (e.g. `OSLMap`, `Bitmaptexture`, `ai_bump2d`)
- assigning sub-materials inside a Multi/Sub when no tool covers it

### Rendering and viewport
- **Do not render unless user explicitly asks for it.**
- **Avoid screenshots by default.** Only capture when:
  - The user explicitly asks to see the scene
  - Visual verification is truly necessary (e.g. debugging a visual issue you can't diagnose otherwise)
- When capturing: prefer `capture_viewport` or `capture_model`. Only use `capture_screen enabled:true` for full UI/fullscreen needs.

---

## 2) Always Inspect Before You Change Anything

Never guess:
- property names
- class names
- enum values
- parameter types

Use these first:
- `inspect_object` → quick overview (class, transform, modifiers, material, mesh stats)
- `inspect_properties target="baseobject"|"material"|"modifier"` → full typed properties
- `inspect_modifier_properties` → modifier params specifically
- `get_object_properties` → detailed object state (transform/material/modifiers)

Fallback inspection commands (MAXScript) when needed:
- `showInterfaces obj`
- `showMethods obj`
- `getPropNames obj`
- `classOf obj`, `superClassOf obj`
- `showProperties obj.modifiers[i]`
- `showProperties obj.material`

---

## 3) Tool Selection Cheat Sheet

### Understand an object
- Overview → `inspect_object`
- Typed properties → `inspect_properties`
- Modifier params → `inspect_modifier_properties`
- Full object details → `get_object_properties`

### Find things in the scene
- List/filter objects → `get_scene_info`
- List assigned materials → `get_materials`
- Enumerate scene-wide class instances → `find_class_instances` (use `superclass`)
- Instancing status → `get_instances`
- Find objects by property → `find_objects_by_property`
- Dependencies graph → `get_dependencies`
- Fog/volume/lens effects → `get_effects`
- State Sets / cameras → `get_state_sets`, `get_camera_sequence`

### Materials
- Create + assign → `assign_material`
- Set one property → `set_material_property`
- Set many properties → `set_material_properties`
- Fast slot discovery (low-token, default map-only + bitmap class hints) → `get_material_slots`
- Multi/Sub slots → `set_sub_material`
- Inspect material → `inspect_properties target="material"`

### Texture maps
- Auto PBR from folder → `create_material_from_textures`
- Create map → `create_texture_map` (stored as global var)
- Set map params → `set_texture_map_properties`
- Write OSL + create map → `write_osl_shader`
- Wire map into material slot → `set_material_property value="{global_var_name}"`

### Modify scene objects
- Set object prop → `set_object_property`
- Add/remove modifier → `add_modifier` / `remove_modifier`
- Enable/disable modifier → `set_modifier_state`
- Scene-wide modifier edits → `batch_modify`
- Collapse stack → `collapse_modifier_stack`
- De-instance modifier → `make_modifier_unique`
- Transform → `transform_object`
- Effects → `toggle_effect` / `delete_effect`

### Organize
- Parent/unparent → `set_parent`
- Show/hide/freeze → `set_visibility`
- Select → `select_objects`
- Clone/instance → `clone_objects`
- Batch rename → `batch_rename_objects`

### Build geometry
- Primitives → `create_object`
- Structures → `build_structure`
- Grid placement → `place_grid_array` / `place_on_grid`
- Circular placement → `place_circle`
- Floor plans → `build_floor_plan`

### See the scene
- Viewport only (safe default) → `capture_viewport` or `capture_model`
- Full UI panels / fullscreen → `capture_screen enabled:true`
- Render → `render_scene`
- Identify visually → `isolate_and_capture_selected`

---

### Animation controllers
- Assign controller → `assign_controller`
- Inspect controller → `inspect_controller`
- Add target/variable → `add_controller_target`
- Update script/props → `set_controller_props`

---

## 4) When `execute_maxscript` Is Allowed

Use it only when no dedicated tool exists, such as:
- animation keyframing
- custom scripted operations
- render settings / environment setup
- specialized Max features not covered by tools

---

## 5) Architecture (Bridge + Protocol)

- MCP server: **Python (FastMCP)**
- 3ds Max side: **MAXScript TCP listener**
- Address: `127.0.0.1:8765`
- Protocol: **JSON + newline delimiter**, one request/response per connection
- Listener design: `.NET TcpListener` + timer polling (50ms) to stay non-blocking

---

## 6) Adding a New Tool (Python)

1. Create: `src/tools/<name>.py`
2. Import: `from ..server import mcp, client`
3. Decorate: `@mcp.tool()`
4. Build MAXScript string
5. Send it: `client.send_command(maxscript)`
6. Return: `response.get("result", "")` (or sensible default)

If the operation can run long (e.g., render), set timeout:
- `client.send_command(maxscript, timeout=300)`

After editing tool files, **restart the MCP server** to load changes.

---

## 7) MAXScript Pitfalls (High-Frequency Errors)

### Constructors
- **Do not use parentheses** after class name when passing keyword params:
  - ✅ `ai_standard_surface name:"Mat1" metalness:1.0`
  - ❌ `ai_standard_surface() name:"Mat1" metalness:1.0`

### Case-insensitivity
- MAXScript is case-insensitive. `R` and `r` are the same variable.
- Use descriptive unique names (`ringRadius`, `tubeRadius`, etc.).

### Scope
- `execute()` runs in global scope.
- **No `local` at top level**; use locals only inside functions/blocks.

### View types
- Use `#view_persp_user` (not `#view_persp`)
- Examples: `#view_left`, `#view_front`, `#view_top`, `#view_iso_user`, `#view_persp_user`

### No built-in join
MAXScript has no `stringJoin`. Use manual concatenation loops.

### Reserved names / keywords
- Avoid global identifiers like: `output`, `result`, `bmp`, `foliage`, `floor`, `osl`, `OSLMap`
- `by` is a reserved keyword (cannot be a var or parameter name)

### Noise modifier naming
- `Noise` is the **texture map**, not the modifier.
- Modifier class is `Noisemodifier`.

### Temp path mismatch
- `(getDir #temp)` is Max’s temp, not OS temp.
- Use `.NET Path.GetTempPath()` to match Python temp.

### String escaping + JSON
- Always escape user strings before embedding in MAXScript (use your project’s safe-name helper).
- Build JSON manually; always escape strings using `escapeJsonString()` from `mcp_server.ms`.

### Python f-strings + braces
- Double MAXScript braces in Python f-strings: `{{` and `}}`, or use raw strings.

### Sphere/primitive UV mapping
- `Sphere()` creates with `mapcoords = false` by default — textures render BLACK with no error.
- Always set `s.mapcoords = true` on any primitive that will receive texture maps.
- This applies to all Standard Primitives (Box, Sphere, Cylinder, etc.).

### Redshift class names
- `RS_Material` is the correct class for Redshift standard materials — NOT `Redshift_Material` (undefined).
- `rsPhysicalLight` color property is `.color` (plain), NOT `.LightColor` — the latter throws "Unknown property". Use `.colorMode = 1` to enable custom color.
- `RS_Bump_Map` (with underscores), NOT `RS_BumpMap` — the latter silently fails.
- `RS_Normal_Map` — dedicated normal map node; use `.tex0_filename` directly (no separate RS_Bitmap needed). Has NO `.input` property.
- `RS_Bitmap` — Redshift native bitmap; set `.tex0_filename` and `.tex0_colorSpace` ("sRGB"/"Raw").
- `RS_Displacement` — displacement node; wire child bitmap via `setProperty dispNode #texMap_map bmpNode`.
- `Redshift_Mesh_Parameters` — modifier for per-object tessellation/displacement settings. Class name uses full `Redshift_` prefix, NOT `RS_`.
- `CompositeTexturemap name:"X"` — the `name:` param collides with an array property; use `CompositeTexturemap(); .name = "X"` instead, or avoid for Redshift (use RS_Mix).

### Redshift texture map wiring
- **Cannot use direct property assignment** for RS material texture map slots: `mat.base_color_map = RS_Bitmap()` fails with "Unable to convert RS_Bitmap to Point4".
- **Must use `setProperty` with symbol access**: `setProperty mat #base_color_map texNode`.
- After wiring a `_map` slot, enable the companion property: `try (setProperty mat #base_color_mapenable true) catch()`.
- RS material slot names: `base_color_map` (sRGB), `refl_roughness_map` (Raw), `metalness_map` (Raw), `bump_input` (RS_Normal_Map or RS_Bump_Map), `displacement_input` (RS_Displacement).
- For displacement: create RS_Bitmap → wire to RS_Displacement via `setProperty dispNode #texMap_map bmpNode` → wire RS_Displacement to `setProperty mat #displacement_input dispNode`.
- RS texture displacement (displacementMode=2) is more efficient than normal maps for surface detail — set globally in RS render settings or per-object via `Redshift_Mesh_Parameters` modifier.

### Redshift rendering
- Use `redshift.renderView` interface for IPR, or standard `render()` for production frames.
- `render_scene` tool uses the standard render pipeline which works with Redshift.

### Redshift MCP tool bugs (as of 2026-03-03)
- `create_redshift_material`, `connect_redshift_texture`, `get_redshift_material_info` all return a dict instead of a string from the MAXScript side — causes pydantic validation error on output. The MAXScript may or may not execute.
- **Workaround**: Use `execute_maxscript` with `setProperty mat #slot_name tex` pattern directly until the tools are fixed.

### .NET strings
- Convert .NET string to MAXScript string with `str as string` before using `.count` etc.

### SubAnim keys
- `numKeys` isn’t available on SubAnim; access controller keys via the actual controller object.

### RailClone_Pro constructor
- `RailClone_Pro name:"X"` — `name:` collides with an internal array property. Use `RailClone_Pro(); rc.name = "X"` instead.

### tyFlow Shape operator
- Single-item properties like `shapeMode` are READ-ONLY from MAXScript.
- Only `_tab` arrays (`shape_type_tab`, `type_3d_ID_tab`, etc.) are writable.
- Setting `shape_type_tab = #(1)` automatically flips `shapeMode` to 3D mode.
- Shape IDs: Triangle=0, Cone=1, Quad=2, Cylinder=3, Sphere=4, Pyramid=5, Cube=6, Octahedron=7.
- Operator variables: use `_Op` suffix to avoid MAXScript name conflicts.

### tyFlow SubAnim access
- SubAnim names replace spaces with underscores: `#PhysX_Shape` NOT `#'PhysX Shape'`.
- `baseobject[#EventName][#Operator_Name]` is the correct access pattern.
- `#'quoted names'` do NOT work for SubAnim access on tyFlow operators.

### tyFlow Inferno (Zenith) — tyFlow 2.0+
- Export operator name is `Export Inferno` (NOT `Inferno Export`).
- Volume API: always pair `updateVolumes()` / `releaseVolumes()` to avoid GPU memory leaks.
- Temperature properties come in 4 variants: `Normalized`, `Celcius`, `Fahrenheit`, `Kelvin`.
- Note: tyFlow uses `Celcius` (misspelled), NOT `Celsius`.
- 15 confirmed Inferno operators: Birth Inferno, Inferno Emitter, Inferno Bounds, Inferno Display, Inferno Collider, Inferno Color, Inferno Spawn, Inferno Properties, Inferno Recall, Export Inferno, Inferno Force, Inferno Temperature, Inferno Density, Inferno Vorticity, Inferno Scale.
- Inferno operators work in regular events (`addEvent()`), no special event type needed.
- PhysX SDF mode: new `sdfCellRatio` and `sdfMinCellSize` properties on PhysX Shape.
- Inferno is a forward-only GPU sim — timeline scrubbing does NOT update the volume display.
- To preview Inferno animations: sim each frame with `updateParticles` + capture with `gw.getViewportDib()`.
- `playAnimation()` blocks the TCP listener — avoid calling it via MAXScript.
- `createPreview` does NOT trigger `updateParticles` — Inferno won't animate in previews.
- Inferno Recall operator with RAM cache: compression mode 0 may suppress display. Needs further testing.

### Physical_Material emission properties
- `emission_weight` does NOT exist — use `emission` (float, default 1.0) for emission strength.
- `emission_color` does NOT exist — use `emit_color` (color) for emission color.
- Other emit properties: `emit_luminance`, `emit_kelvin`, `emit_color_map`, `emit_color_map_on`.

### Forest Pack + Redshift rendering
- Materials on the Forest Pack object itself are VIEWPORT-ONLY — Redshift ignores them at render time.
- Assign RS materials to the **source geometry** nodes, or populate `fp.matlist` (per-source override array).
- `fp.rmesh = 0` (Automatic mode) is the correct setting for Redshift — enables native instancing.
- Do NOT wrap FP source geometry in RedshiftProxy; Forest Pack handles the instancing bridge internally.
- Correct FP scale properties: `scalexmin`, `scalexmax` (NOT `scalemin`/`scalemax`).
- `divers` NOT `diversity`, `clusize` NOT `clustsize`, `animation` NOT `animmode`.
- `at` is a MAXScript reserved word — never use as a variable name (use `atype` etc.).

### RPManager UI dependency
- `RPMdata.AddPass()` requires the RPManager UI to have been opened at least once in the current session.
- Headless-safe functions: `version()`, `getpasscount()`, `GetPassOutputPath`, `GetPassBeforeScript`, `SetPassBeforeScript`, `GetPassAfterScript`, `SetPassAfterScript`, `GetPassTimeType`, `SetPassTimeType`, `GetPassRange`, `SetPassRange`, `GetPassVisSetName`, `GetPassBGColor`, `SetPassColor`.

---

## 8) Viewport Capture Rules

- OSL maps show correctly in viewport only in **High Quality** mode.
  - Switch via: `actionMan.executeAction -844228238 "40"`
- Use `completeredraw()` before capturing.
- **Always frame before capture**:
  - select target → `max zoomext sel` → capture
- Avoid `viewport.setTM` for camera placement; it’s unreliable.

---

## 9) Scattering Policy

- If user says “scatter”, default to procedural tools (not manual loop placement).
- Prefer **tyFlow** over Particle Flow.
- Built-in Scatter limitations:
  - Max 2025+ `ScatterGeometry` exists but some arrays are UI-only and not settable via MAXScript.
  - Legacy Scatter compound object not creatable via MAXScript in Max 2026.

Fallback when tools fail:
- Convert distribution surface to mesh (`snapshotAsMesh`)
- Sample faces, use `meshOp.getFaceCenter`
- Orient using global `getFaceNormal mesh faceIdx`
- Instance placement as last resort

---

## 10) Scene Organization Rules

- Prefer **Dummy-based hierarchies** for clean outliner.
- Don’t create a Dummy on first build of a single object; organize only when you’ll reuse/group.

Dummy workflow order:
1. Create all objects
2. Compute combined bounding box
3. Create Dummy
4. Set Dummy box size to bbox
5. Position Dummy at bbox center XY
6. Set pivot to minimum Z
7. Parent objects into Dummy

---

## 11) Instancing & Cloning Notes

- `instance` doesn’t work reliably on group heads.
- Use `maxOps.cloneNodes ... cloneType:#instance newNodes:&cloneArr`
- Instancing a Dummy alone does **not** bring children. To instance hierarchies:
  - clone full descendant list, or
  - group/attach depending on the situation

---

## 12) Splines (Key Properties)

Renderable spline params:
- `render_displayRenderMesh`
- `render_displayRenderSettings`
- `render_thickness`

Not a thing:
- `render_viewport` (doesn’t exist on SplineShape)

---

## 13) Booleans

- Use **`BooleanMod`** (modern), not ProBoolean.
- Add operands via `bm.BooleanModifier.AppendOperand ...`
- Make cutters thick enough: operand B must fully intersect operand A.

---

## 14) RPManager Script & Visibility Tools

### Key bugs & workarounds (RPManager v7.8)
- **`fRefresh()` crashes** when `lstbox` is undefined (UI not open) — always use `try(RPMdata.rmrefresh())catch()` instead
- **`MouseDownSelection.ListView`** returns undefined until user has clicked the pass list — wrap in try/catch, fall back to state-variable-only restore
- **Setter functions** (`SetPassOutputPath`, `SetPassBeforeScript`, etc.) silently fail without UI — always call `RPMdata.RMopenFloater()` first
- **Vis set creation via `RMLSetMaker.oker.pressed()`** assigns name but does NOT store layer data — BROKEN, cannot fix without decrypting RPManager source
- **`RMrestore()` does NOT apply vis set layer states** — it restores render settings but not layer visibility
- **RPManager .mse encryption** is custom (polyalphabetic cipher in RPMdlx.dlx), NOT standard Max `encryptScript` — cannot be decrypted with QuickBMS

### Recommended tools
- **`set_rpmanager_visibility`** — uses before/after scripts for layer control (bypasses broken vis set API). Pass `layers_on` list.
- **`configure_rpmanager_pass`** — one-stop setup: layers + output path + frame range via before/after scripts
- **`render_rpmanager_pass`** — full cycle: restore pass → before script → render → after script
- **`set_rpmanager_pass_script`** — auto-wraps scripts in `( ... )` for safe `execute()` (RPManager uses `execute()` internally)
- **`restore_rpmanager_pass`** — switches active pass with fallback (tries ListView, falls back to state vars + RMrestore)

### Before/after script pattern for layer visibility
Before/after scripts are the ONLY reliable way to control per-pass layer visibility:
```maxscript
-- Before: save state, set layers
global _rpm_layer_state = #()
for li = 0 to LayerManager.count-1 do (
  local l = LayerManager.getLayer li
  append _rpm_layer_state #(l.name, l.on)
)
local onLayers = #("LayerA", "LayerB")
for li = 0 to LayerManager.count-1 do (
  local l = LayerManager.getLayer li
  l.on = (findItem onLayers l.name) > 0
)

-- After: restore
for entry in _rpm_layer_state do (
  local l = LayerManager.getLayerFromName entry[1]
  if l != undefined do l.on = entry[2]
)
```

---

## 15) Modal Dialogs Lock You Out

**CRITICAL:** Any MAXScript that triggers a modal dialog (confirmation, file browser, error popup) will block the TCP listener indefinitely. Max stops responding to MCP commands until the user manually dismisses the dialog.

- **Never trigger "overwrite?" confirmations** — check `doesFileExist` before saving, use unique names for RPManager vis sets, etc.
- **Never call functions that open file browsers** (`getOpenFileName`, `getSaveFileName`) — pass paths directly
- **RPManager `RMLSetMaker` dialog:** Do NOT use — `oker.pressed()` doesn't store layer data, and duplicate names cause a blocking modal. Use before/after scripts instead.
- **Avoid `messageBox`**, `queryBox`, `yesNoCancelBox` in any script you execute
- **If locked out:** user must click through the dialog in Max, then retry the MCP command
- **`quiet:true`** flags exist on many Max functions — always use them (e.g. `loadMaxFile ... quiet:true`, `resetMaxFile #noPrompt`)

---

## 16) Safety for Destructive Operations

- Prefer **Hold/Fetch** for critical operations:
  - `holdMaxFile()`
  - revert with: `fetchMaxFile quiet:true`

For batch ops:
- wrap with `disableSceneRedraw()` / `enableSceneRedraw()` / `redrawViews()`
- preserve selection
- allow abort via `keyboard.escPressed`

---

## 17) Data Channel Modifier (DC)

Use tools:
- Build full graph → `add_data_channel`
- Inspect → `inspect_data_channel`
- Change one operator → `set_data_channel_operator`
- Add script operator → `add_dc_script_operator`
- Presets → `list_dc_presets` / `load_dc_preset`

Common DC pitfalls:
- Must be Editable Mesh/Poly → convert first
- `operator_order` is **0-based**
- Operators not in order do not execute
- GeoQuantize before element-level ops to avoid tearing
- Node references must be actual nodes, not strings
- **Always include `vertex_output` (output=0, Position)** at the end of TransformElements/ColorElements pipelines — composite operators need it to write results to the mesh
- **TransformElements.transformType actual values**: 0=Position, 1=Rotation, 2=Scale%, 3=ScaleUniform (sequential, NOT the gapped 0,2,3,4 from Autodesk docs)
- Use `"blend"` key in operator dicts to set `operator_ops` blend mode: 0=Replace, 1=Add, 2=Subtract, 3=Multiply, 4=Divide, 5=Dot, 6=Cross

---

## 18) Wire Parameters

Use tools:
- Discover params → `list_wireable_params`
- Create wire → `wire_params`
- Inspect wires → `get_wired_params`
- Remove wire → `unwire_params`

Wire tips:
- You do NOT need to `unwire_params` before re-wiring — `paramWire.connect` overwrites existing wire controllers automatically
- **Rotation wire expressions use RADIANS**, not degrees — use `distance / radius` not `distance * 360 / (2*pi*r)`
- Sub-anim paths from `list_wireable_params` start with `[#` — no dot separator needed before brackets
- MAXScript `pi` constant is available in wire expressions

---

## 17) Animation Controllers

Use tools:
- Assign controller → `assign_controller`
- Inspect controller → `inspect_controller`
- Add target/variable → `add_controller_target`
- Update script/props → `set_controller_props`

Supported controller types:
- **Script**: `float_script`, `position_script`, `rotation_script`, `scale_script`, `point3_script`
- **Constraints**: `position_constraint`, `orientation_constraint`, `lookat_constraint`, `path_constraint`, `surface_constraint`, `link_constraint`, `attachment_constraint`
- **Noise**: `noise_float`, `noise_position`, `noise_rotation`, `noise_scale`
- **List**: `float_list`, `position_list`, `rotation_list`, `scale_list`
- **Expression**: `float_expression`, `position_expression`
- **Other**: `spring`

Controller tips:
- `dependsOn` in script controllers = self-reference to the owning node (critical for dependency tracking)
- Script controller `addNode` creates name-independent references (survive object renames)
- Expression controllers require `ctrl.update()` after `setExpression` — `assign_controller` and `set_controller_props` handle this automatically
- Link constraint uses `addTarget node frame` (not `appendTarget`)
- Attachment constraint uses `appendTarget node face`
- Use `list_wireable_params` to find the correct sub-anim path before assigning controllers
- Sub-anim paths starting with `[` need no dot separator (same pattern as wire_params)
- **Use `layer=True`** to add a controller on top of existing (wraps in list controller, preserves current value)

List controller pitfalls:
- **Cannot assign sub-controllers via local variable** — `listCtrl[2].controller = X()` fails with "Cannot set controller"
- **Must use `execute("$'name'.pos.controller.Available.controller = ...")`** — the `$` path is required for list sub-anim assignment
- Position_List sub-anim structure: [1]=default Bezier, [2]=Available (dummy), [numsubs]=Weights — after adding, new ctrl is at numsubs-2
- `assign_controller` with `layer=True` handles all of this automatically

Noise controller property names:
- `Noise_Position`: `noise_strength` (Point3, e.g. `[0.3, 0.3, 0.15]`) — NOT `X_Strength`/`Y_Strength`/`Z_Strength`
- `Noise_Float`: `strength` (float)
- `Noise_Rotation`: `noise_strength` (Point3, XYZ in degrees)
- Common props: `seed`, `frequency`, `fractal`, `roughness`, `rampin`, `rampout`, `x_positive`/`y_positive`/`z_positive`

---

## 18) Debug / Test Loop

- Use `execute_maxscript` as an “escape hatch” for quick experiments.
- If you get `ConnectionRefusedError`, the MAXScript listener isn’t running.
- Confirm comms/temp directory exists to validate bridge readiness.
- Restart MCP server after Python tool edits.

---

## 19) tyFlow + tyCache Rendering Pitfalls

- **Material modifier ignored by tyFlow**: tyFlow reads base mesh face matIDs, NOT Material modifier. Must `collapseStack` or set face matIDs directly via `polyop.setFaceMatID`.
- **tyCache matID ordering**: tyCache exports with its own Multi/Sub ordering (from `OLED_Instances_Mat` or auto-generated). This may NOT match the tyFlow object's material. Always verify slot ordering and create a matching Multi/Sub for the tyCache.
- **RS_OSL_Map corruption**: `oslCode` assignment can crash with access violation if the map is in a bad state. Create a fresh `RS_OSL_Map` instead of modifying the corrupted one.
- **RS_OSL_Map multi-output**: Shaders with multiple outputs (e.g. `output color Out` + `output float Weight`) need `MultiOutputChannelTexmapToTexmap` wrapper. Single-output shaders can be assigned directly to material slots.
- **RefractionsEnable**: Redshift global refraction toggle (`renderers.current.RefractionsEnable`) can silently be `false`. Always verify when transparency doesn't render.
- **MCP listener access violation**: `dotNet.setLifetimeControl listener #dotnet` prevents .NET GC from invalidating the TCP listener during heavy operations.
- **Always backup before destructive mesh ops**: `polyop.attach`, `collapseStack`, `convertTo` are irreversible. Clone + hide originals first.
- **tyCache renderable flag**: resets to `false` after Max restart. Must set `tc.renderable = true` explicitly.
- **tyCache renderMode**: 0=Triangle mesh (combined, slow), 1=Render instances (fast, GPU instancing). Use 1 for production.
- **tyCache export trigger**: `objectsAutoRenderExport = true` + render a frame to trigger. `reset_simulation()` alone does NOT export.
