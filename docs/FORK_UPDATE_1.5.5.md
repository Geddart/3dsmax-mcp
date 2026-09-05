# 1.5.5 fork update

Merged upstream `32af329` (1.5.5) with fork `72b454f` (0.5.3.1+fork).
The active updated checkout is `.updates/1.5.5`, branch `codex/update-1.5.5`.
The original checkout, environment, untracked files and local edits remain available for rollback.

## Preserved and updated

- All 188 previously advertised tool names remain available; the full merged profile has 239 tools.
- Custom Redshift, RPManager, Forest Pack and RailClone modules are retained.
- Removed upstream native operations used by legacy tools use their preserved MAXScript paths.
- Default connection routing uses upstream's per-process native discovery. Explicit legacy slots use their selected TCP endpoint rather than an unrelated native pipe; discovered native instances can be selected with the existing instance tools.
- Use **MCP Claim This Max** in Max for default native routing. Historical TCP toolbar scripts are retained as source; they are not installed by the new bundle.
- Upstream structured results, atomic operations and progressive discovery are retained. The installed full profile exposes all custom tools directly; progressive discovery also indexes the extensions.
- The Redshift `vfb:false` fix is preserved in the rendering tool and native source.
- The Max 2025 native bridge was rebuilt with the installed SDK. Other Max-year binaries are the upstream builds; the Python render path keeps the fix across versions.
- Compatible dependencies were refreshed in the isolated environment, including MCP 1.29.1. MCP remains pinned below 2 as required by the upstream API.
- Upstream skill guidance and the fork reference are bundled for both Claude and Codex.

## Verification

465 Python tests pass (430 upstream, 30 preserved fork tests and 5 new compatibility checks).
The full tool catalog contains every prior tool name. Import dependencies in the restored workflows resolve.
The native Max 2025 build succeeds. No render or scene edit is part of deployment verification.
Live scene behavior still requires a running Max instance and cannot be established by mocked tests alone.

## Deployment and rollback

`scripts/deploy_merged_update.py` stages the new ApplicationPlugins bundle, verifies hashes,
backs up previous plugin/config/skill files and disables old loadable plugin/startup files by renaming them.
Backups are private, ignored files under `.deployment-backup/<timestamp>/manifest.json`.
The original pre-update client configuration backup is under `20260905-073600`.
Do not publish backups: client settings may contain credentials.

Both client registrations should point to this checkout's `.venv/Scripts/3dsmax-mcp.exe` with
`MCP_TOOL_PROFILE=full`. Restart the clients to reload their tool catalogs after deployment.
A rollback requires restoring both the prior native bridge/startup files and the corresponding client configurations.
