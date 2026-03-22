# 3dsmax-mcp Extension Project — Session Log

## Session 2026-03-03

### What happened
- Cloned `https://github.com/cl0nazepamm/3dsmax-mcp.git` into `H:\001_ProjectCache\1000_Coding\3dsmax_MCP`
- Updated MCP config in `~/.claude.json` to point to this new location
- Initialized git repo, set identity (Sascha Geddert / sascha@geddart.de)
- Researched Redshift, tyFlow, RPManager, RailClone, Forest Pack Pro MAXScript APIs
- Generated 5 comprehensive implementation plans in `docs/`

### Plans written
| Plan | File | Tools | Key insight |
|------|------|-------|-------------|
| Redshift | `docs/PLAN_redshift.md` (66KB) | 13 tools | Runtime introspection critical — RS class names change between versions |
| tyFlow | `docs/PLAN_tyflow.md` (85KB) | 13 tools | Shape `_tab` arrays are write-only path; known bug with shape type IDs |
| RPManager | `docs/PLAN_rpmanager.md` (56KB) | 15 tools (2 conditional) | Docs site down; pass creation/deletion may not be exposed |
| RailClone | `docs/PLAN_railclone.md` (42KB) | 13 tools | Style graph can't be built via MAXScript — library-first approach |
| Forest Pack | `docs/PLAN_forest_pack.md` (64KB) | 18 tools | Extends existing `scatter_forest_pack`; 200+ properties to discover |

### Known bug
User tested tyFlow and shapes were wrong (said spheres, got triangles). Shape operator `type_3d_ID_tab` integer mapping needs empirical discovery in 3ds Max.

### Next steps (from session 1)
- tyFlow Shape ID investigation (fixes known bug)
- Remaining Redshift plan tools (lights, render settings, AOVs, proxies, camera)
- Other plugin plans still pending Phase 0/1 introspection

---

## Session 2026-03-03 (Part 2) — Redshift Materials Implementation

### What happened
1. Implemented the approved Redshift Materials plan (6 phases):
   - Phase 1: Fixed 4+ bugs in `material_ops.py` (RS class names, RS_Bitmap, RS_Normal_Map, AO skip)
   - Phase 2: Created `src/tools/redshift.py` with 5 tools + 10 presets
   - Phase 3: Registered `redshift` module in `src/server.py`
   - Phase 4: Created `docs/redshift_api_reference.md`
   - Phase 5: Updated `CHANGELOG.md`
   - Phase 6: All 10 verification tests passed against live Max (PID 61960)

2. Built 12 Fab.com tile materials from texture folders in `N:\50_Assets\`:
   - Launched separate dev Max instance (PID 91996) to avoid touching user's working scene
   - Created materials using buildRSMat MAXScript helper with RS_Bitmap, RS_Normal_Map, RS_Displacement
   - Placed in Slate Material Editor in 4x3 grid
   - Created 12 spheres with materials, rsDomeLight, rsPhysicalLight, camera, rendered

3. Major debugging session — ALL textures rendered BLACK:
   - Root cause: `Sphere mapcoords = false` (default) — no UV coordinates generated
   - Fix: set `mapcoords = true` on all primitives receiving textures
   - This was the most critical lesson of the session

4. Applied all fixes back to MCP server code:
   - `render.py`: `vfb:true` → `vfb:false` (prevents VFB popup)
   - `material_ops.py`: RS_Normal_Map uses tex0_filename directly, RS_Displacement wires through node, skip AO for RS
   - `redshift.py`: RS_Displacement auto-creates child RS_Bitmap when file_path provided
   - `SKILL.md`: Added mapcoords pitfall, RS class name lessons
   - `CHANGELOG.md`: All new entries under [Unreleased]

### Files created
- `src/tools/redshift.py` (~400 lines, 5 tools)
- `docs/redshift_api_reference.md` (~200 lines)

### Files modified
- `src/server.py` (added redshift import)
- `src/tools/material_ops.py` (bug fixes)
- `src/tools/render.py` (vfb:false)
- `skills/3dsmax-mcp-dev/SKILL.md` (new pitfalls)
- `CHANGELOG.md` (new entries)

### Saved scene
- `N:\50_Assets\Fab_Tile_Materials.max` — 12 materials, spheres, lights, camera
- User can merge via: `mergeMAXFile "N:/50_Assets/Fab_Tile_Materials.max"`

### Next steps
- MCP server restart needed to pick up all Python code fixes
- Remaining Redshift plan: lights, render settings, AOVs, proxies, camera tools
- tyFlow, RPManager, RailClone, Forest Pack plans still pending

---

## Session 2026-03-04 — RPManager Render Layer Setup

### What happened
1. Set up RPManager render layers for shot 504_53_010:
   - Scene: `N:\30_Shots\504_53_010\3D\504_53_010_v041.max` (272 objects, 13M polys)
   - 3 existing passes: BG (1), MG (2), FG (3) — camera: CAM_504_53_010_blend
   - Used before/after scripts (not vis sets) because RPManager's vis set creation API requires UI

2. Pass configuration:
   - **BG**: Only BG_AI_Projection layer (5 objects) + Lights
   - **MG**: Water_Surface + BG objects with RS_VIS_PRIMARYRAYVISIBLE=False + Lights
   - **FG**: All FG layers + BG objects with RS_VIS_PRIMARYRAYVISIBLE=False, Water hidden

3. Rendered frame 1200 for all 3 passes:
   - `N:\30_Shots\504_53_010\render\BG\504_53_010_BG_1200.exr` (1.4 MB)
   - `N:\30_Shots\504_53_010\render\MG\504_53_010_MG_1200.exr` (7.8 MB)
   - `N:\30_Shots\504_53_010\render\FG\504_53_010_FG_1200.exr` (39 MB)

4. Scene state properly restored after all renders
5. Saved as v042: `N:\30_Shots\504_53_010\3D\504_53_010_v042.max`

### Key technical findings
- Redshift visibility controlled via UserPropBuffer (`RS_VIS_OVERRIDE`, `RS_VIS_PRIMARYRAYVISIBLE`, etc.)
- `setUserProp`/`getUserPropBuffer` for reading/writing RS object properties
- RPManager `SetPassRange` silently fails even with correct args (data may not persist to internal storage)
- RPManager `renderLocally` needs passes checked in UI — no headless API for checking passes
- RPManager `GetPassCamera` returns node reference, not string name

### MCP server issues found
1. `get_rpmanager_capture_sets` returns raw dotNetObject strings instead of state set names
2. `get_rpmanager_passes` doesn't include pass names (only index, output, camera, etc.)
3. `batch_update_rpmanager_passes` range format broken — `SetPassRange` takes 2 args (index, array) but tool sends 4
4. `get_rpmanager_pass_detail` has `visSetName: "undefined"` string instead of null/proper handling
5. No tool for creating/managing RPManager visibility sets programmatically
6. `get_rpmanager_pass_scripts` — script retrieval has JSON control character issues (newlines in script content not escaped)
7. No tool for programmatically rendering RPManager passes (before/after script execution + render)
8. `GetPassCamera` returns node reference — MCP tools should convert to name string

### Next steps
- Fix the 8 MCP server issues listed above
- User needs to verify renders in Nuke for compositing correctness
- Consider adding dedicated RPManager render tool that handles before/after scripts

---

## Session 2026-03-04 (Part 2) — RPManager Visibility Set Assignment Fix

### What happened
1. Continued from context compaction — task was to properly assign visibility sets to all 3 RPManager passes
2. Multiple failed approaches:
   - `renderdataarray[28]` modification — doesn't persist (read-only copy)
   - `writeVisSetData()` — writes layer state data but NOT the pass assignment
   - `SetPassSelection` — doesn't actually control the RMLSetMaker's target
   - `selectionTemp` / `lastLstBoxId` — RPMdata internal state, not the UI selection
   - `CA_redefineVis` — takes 6 args, couldn't determine correct signature
3. **Root cause found**: RPManager's "Apply to Currently Selected Passes" reads the selection from a .NET `System.Windows.Forms.ListView` control — NOT from `selectionTemp` or `lastLstBoxId`
4. **Solution**: Access the ListView via `RPMdata.MouseDownSelection.ListView`, programmatically set `.Selected = true/false` on items, then create the layer set
5. Successfully assigned all 3 visibility sets:
   - Pass 1 (BG): `LS:BG_final_504` — layers: BG_AI_Projection + Lights
   - Pass 2 (MG): `LS:MG_final_504` — layers: 20_MG + BG_AI_Projection + Lights
   - Pass 3 (FG): `LS:FG_final_504` — layers: 10_FG + BG_AI_Projection + Lights
6. Saved as v042: `N:\30_Shots\504_53_010\3D\504_53_010_v042.max`
7. Triggered "Layer Set Set Exists" modal once (reused name from timed-out attempt)

### Key technical discovery
The RPManager pass ListView is accessible via:
```maxscript
local lv = RPMdata.MouseDownSelection.ListView  -- .NET System.Windows.Forms.ListView
lv.Items.Item[index].Selected = true/false       -- controls "currently selected passes"
```
This is the ONLY reliable way to target a specific pass for vis set assignment.

### Files modified
- `skills/3dsmax-mcp-dev/SKILL.md` — Added section 17 (RPManager Visibility Set Assignment)
- `.claude/conversation.md` — This update

### Orphaned items
- 3 extra unchecked items in RPManager ListView (indices 3-5) from failed attempts — harmless but visible in UI

---

## Session 2026-03-04 (Part 3) — RPManager Decryption Attempt + MCP Tool Fixes

### Decryption attempt (blocked)
1. Backed up 4 priority .mse files to `rpmanager_src/originals/`
2. QuickBMS + standard MSE decryption failed — RPManager uses custom encryption, NOT standard Max `encryptScript`
3. Files are valid UTF-8 with CP1252-mapped characters (Unicode codepoints in 0x80-0x9F range)
4. Wrote custom tools: `rpmanager_src/tools/decrypt_mse.py`, `decode_rpm.py`
5. Reverse-engineered `RPMdlx.dlx` binary — found polyalphabetic cipher:
   - CP1252 reverse mapping → counter (mod 37) + PRNG (mod 44) subtraction + even/odd adjustment
   - PRNG array initialized from internal function — blocked without extracting seed values
6. **Conclusion**: Decryption requires further RE of RPMdlx.dlx PRNG initialization. Pivoted to MCP workarounds.

### MCP tool fixes (completed)
All fixes in `src/tools/rpmanager.py`:

1. **`fRefresh()` → `try(RPMdata.rmrefresh())catch()`** — 12 occurrences replaced (prevents crash when lstbox undefined)
2. **Added `RMopenFloater()` guards** to tools 4 (set_rpmanager_pass_property), 14 (set_rpmanager_pass_script), 15 (batch_update_rpmanager_passes) — prevents silent setter failures
3. **Rewrote `restore_rpmanager_pass`** (tool 6b) — opens UI, tries ListView with fallback to state-variable-only restore, reports `lvFound` status
4. **Rewrote `set_rpmanager_visibility`** (tool 8) — replaced broken RMLSetMaker dialog with before/after script approach. Now takes `layers_on` + optional `restore_layers`, generates scripts that save/restore layer state
5. **New tool `configure_rpmanager_pass`** (tool 16) — one-stop setup: layers + output path + frame range via before/after scripts
6. **New tool `render_rpmanager_pass`** (tool 17) — full render cycle: restore pass → before script → render → after script (300s timeout)

### SKILL.md updates
- Expanded section 14 with RPManager v7.8 bug list and workarounds
- Added before/after script pattern for layer visibility
- Updated RMLSetMaker warning (do not use — broken)

### Files modified
- `src/tools/rpmanager.py` — all 6 fixes above
- `skills/3dsmax-mcp-dev/SKILL.md` — RPManager section rewritten

### Files created
- `rpmanager_src/originals/` — backed up .mse files
- `rpmanager_src/tools/decrypt_mse.py`, `decode_rpm.py`, `3dsmax.bms`

### Next steps
- Live test all RPManager tools against 3ds Max
- MCP server restart needed to pick up Python code changes

---

## Session 2026-03-22 — tyFlow 2.0 (Zenith) Support

### What happened
1. Deleted stale `H:\001_ProjectCache\1000_Coding\3dsmax-mcp` directory (older clone)
2. Researched tyFlow 2.0 (Zenith) — GPU smoke/fire via 20 "Inferno" operators
3. Ran Phase 0 introspection in live 3ds Max 2025 (tyFlow v2.003):
   - Discovered 15 Inferno operators (10 from docs + 5 undocumented)
   - Captured all properties via showProperties
   - Confirmed Inferno ops work in regular events
   - Re-verified ALL operators — 39+ previously-failed ops now work in v2.0
   - Confirmed Global operator, MAXScript operator, SDF shape mode, tyMeshBlend
4. Implemented 6 new tools in `src/tools/tyflow.py`:
   - `get_tyflow_volume_data` — sample density/fuel/temp/color/velocity from fluid grid
   - `convert_tyflow_temperature` — celsius/fahrenheit/kelvin conversion
   - `create_tyflow_inferno` — one-call fire/smoke setup with 4 presets
   - `set_tyflow_inferno_display` — configure viewport ray marching
   - `export_tyflow_inferno_vdb` — configure VDB export channels/path
   - `set_tyflow_global_event` — mark events as global (v2.0 feature)
5. Fixed critical `_sa_name()` bug: SubAnim access uses underscores not quotes (`#PhysX_Shape` not `#'PhysX Shape'`)
6. Tested all new tools in live 3ds Max — fire simulation rendered in viewport with AO/shadows/glow

### 15 Confirmed Inferno Operators
Birth Inferno, Inferno Emitter, Inferno Bounds, Inferno Display, Inferno Collider, Inferno Color, Inferno Spawn, Inferno Properties, Inferno Recall, Export Inferno, Inferno Force, Inferno Temperature, Inferno Density, Inferno Vorticity, Inferno Scale

### Key findings
- Export operator is `Export Inferno` (NOT `Inferno Export`)
- SubAnim access: spaces become underscores (`#Inferno_Display`, NOT `#'Inferno Display'`)
- Temperature props use `Celcius` (tyFlow's misspelling)
- Volume API: `updateVolumes()` / `releaseVolumes()` must be paired (GPU memory)
- Inferno operators work in regular events, no special event type

### Files modified
- `src/tools/tyflow.py` — 6 new tools, _sa_name fix, updated docstring (~700 new lines)
- `skills/3dsmax-mcp-dev/SKILL.md` — Inferno pitfalls, SubAnim fix

### Files created
- `docs/research/tyflow2_introspection.md` — complete introspection results

### Next steps
- MCP server restart needed to register new tools
- Consider adding Inferno presets to `create_tyflow_preset`
- Test `modify_tyflow_operator` with Inferno operators after server restart

### Session 2026-03-22 (Part 2) — Live Testing & Explosion Scene

1. Fixed `send_command()` return type bug in tyflow.py (19 calls) and redshift.py (5 calls) — tools must return `.get("result", "")` not the raw dict
2. Built explosion scene: fractured wall (Voronoi 80 pieces) + PhysX debris + Inferno fire
3. Discovered Inferno timeline scrubbing limitation and solved with sim+capture workflow

### Future MCP tool ideas (from Inferno workflow lessons)
- **`capture_tyflow_preview`** — sim + viewport capture in one loop: steps through frames, calls `updateParticles` on specified tyFlows, captures `gw.getViewportDib()` per frame, outputs image sequence. Works for any tyFlow sim, not just Inferno.
- **`create_tyflow_inferno` improvements** — set `updateOnTimeChange = true` by default on Birth Inferno; investigate adding Inferno Recall with uncompressed RAM cache by default
- **Inferno Recall investigation** — compressed mode (VQVDB) may need RTX 2000+ GPU; uncompressed mode (0) suppressed display in our tests; `recallMode` values undocumented. Needs more testing with different GPU/driver combos.
- **`playAnimation()` alternative** — can't use via MCP (blocks TCP listener). The sim+capture loop is the only reliable approach.
- **`createPreview` limitation** — does NOT call `updateParticles`, so Inferno stays static. Document this and warn users.
- **RV integration** — launching RV with `-network -networkPort 45125` works; sequence notation is `filename_####.ext`
