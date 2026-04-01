# 3dsmax-mcp

MCP server for AI agents to control 3ds Max. This file is the single source of truth — `AGENTS.md` (Codex) is auto-generated from it via `scripts/build_skill.py`.

## learn-from-mistakes

When you encounter a bug, unexpected behavior, or discover a MAXScript/3ds Max/MCP pitfall:
1. Fix the issue
2. Append the lesson to the relevant section in `skills/3dsmax-mcp-dev/SKILL.md`
3. One line per lesson — include the pattern or fix
4. Check for duplicates before adding

## Project Structure
- `src/server.py` — FastMCP server entry point
- `src/max_client.py` — TCP socket client + MaxClientManager (multi-instance slot routing)
- `src/tools/` — MCP tool implementations (one file per category)
- `maxscript/mcp_server.ms` — MAXScript listener (runs inside 3ds Max)
- `maxscript/mcp_manager.ms` — Multi-instance slot manager UI
- `maxscript/mcp_toolbar.ms` — Macroscript toolbar buttons for slots
- `maxscript/startup/mcp_autostart.ms` — auto-start loader for 3ds Max
- `native/` — C++ GUP bridge plugin (named pipe, 53 native handlers)

## Skills & Build
- `skills/3dsmax-mcp-dev/SKILL.md` — source of truth (grows via learn-from-mistakes)
- `scripts/build_skill.py` — builds `.skill` archive, copies to local + global `.claude/skills/`, generates `AGENTS.md`
- Both `.claude/skills/` and `AGENTS.md` are gitignored — never edit them directly

## Key Patterns
- Tools registered via `@mcp.tool()` in `src/tools/*.py`
- All tools send MAXScript strings to 3ds Max via `client.send_command()`
- MAXScript results returned as JSON strings via manual concatenation
- Viewport capture: `gw.getViewportDib()` → save to temp → `Read` tool to view
- Do not RENDER unless user explicitly asks — but `capture_multi_view` (quad view) is encouraged after scene changes

## tyFlow Rendering Constraints
- Per-particle vertex color or UVW mapping overrides BREAK GPU instancing — each becomes a unique mesh
- Only particle transforms (pos/rot/scale) are lightweight instance data
- For massive instancing with per-instance color: use OSL shader reading world position (preserves instancing)
- `meshSplitElements_tab = #(true)` on Shape operator splits reference mesh elements into separate particles
- `displayMaterial = true` on Display operator required for materials to render
- Introspection gaps: Color, Material Static, Material Dynamic, Custom Properties operators need `showProperties` dumps

## Plugin Renderer Compatibility
- ForestColor texmap NOT supported by Redshift or other GPU renderers (iToo confirmed)
- Forest Pack tintmap with Redshift: untested, likely breaks instancing
- Redshift RS_Color_User_Data: can read per-instance attributes — whether tyFlow exposes these is unverified
