# 1.5.5 fork update

Merged upstream `32af329` (1.5.5) with fork `72b454f` (0.5.3.1+fork).
The prepared updated checkout is `.updates/1.5.5`, branch `codex/update-1.5.5`.
The original checkout, environment, untracked files and local edits remain available for rollback.

## Preserved and updated

- All 188 previously advertised tool names remain available; the full merged profile has 239 tools.
- Custom Redshift, RPManager, Forest Pack and RailClone modules are retained.
- Removed upstream native operations used by legacy tools use their preserved MAXScript paths.
- Default connection routing uses upstream's per-process native discovery. As of 2026-09-09, numbered slots and TCP are removed; instance tools select native discovery IDs directly.
- Use **MCP Claim This Max** or **MCP Instances** in Max for default native routing. Old slot/TCP macros and toolbar scripts have been retired from the installation.
- Upstream structured results, atomic operations and progressive discovery are retained. The installed full profile exposes all custom tools directly; progressive discovery also indexes the extensions.
- The Redshift `vfb:false` fix is preserved in the rendering tool and native source.
- The Max 2025 and Max 2027 native bridges were rebuilt from source with their matching SDKs. Both contain the pipe-cancellation, executor-shutdown-gate and `vfb:false` fixes. The 2027 binary passed the same live acceptance set as 2025 (instance panel, UI automation, async jobs, MCP stdio catalog) in Max 2027 on 2026-09-10.
- A repeat Max 2025 Release build matches the committed binary's size (2,135,552 bytes), imports and fix strings. Only two compiler-generated RTTI names differ among extracted strings; the committed binary was retained. The 2027 Release binary is 2,066,944 bytes. See [native build matrix and commands](../native/README.md).
- `mcp_bridge_2023/2024/2026.gup` still predate the transport/executor and native `vfb:false` fixes; rebuild each against its matching SDK before shipping to those Max versions.
- Compatible dependencies were refreshed in the isolated environment, including MCP 1.29.1. MCP remains pinned below 2 as required by the upstream API.
- Upstream skill guidance and the fork reference are bundled for both Claude and Codex.

## Verification

551 Python tests pass in the native rebuild worktree with `uv run --frozen --no-sync python -m unittest discover -s tests`.
Progressive discovery of fork extension schemas also passed a real stdio MCP handshake.
The full tool catalog contains every prior tool name. Import dependencies in the restored workflows resolve.
The native Max 2025 and Max 2027 Release builds succeed with MSVC 19.43 and no reported compiler/linker warnings. Native transport regression tests pass. No render or scene edit was performed for this rebuild.
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

## Current installation status

Deployment completed on 2026-09-07 with Windows administrator approval.
The shared ApplicationPlugins bundle is enabled for Max 2023–2027, including the installed Max 2025 on C: and Max 2027 on F:.
The old Max 2025 bridge and startup scripts were renamed to rollback copies. Claude and Codex now point to the merged checkout with the full tool profile.
Deployment backups are under `.deployment-backup/20260907-104413`.
The installer discovers custom Max installation paths through the Windows registry and activates the bundle manifest after updating the client configurations.
The September 7 verification confirmed 239 tools and the saved robot scene in Max 2025. The September 9 integration now exposes 254 tools with all 188 original names retained, adds dialog automation and async jobs, and removes slot/TCP routing. Live checks passed in both Max 2025 and 2027; see [UI, jobs and native instances](UI_JOBS_NATIVE_INSTANCES.md) for verification scope and limitations.
