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
