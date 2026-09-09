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
- The Max 2025 native bridge was rebuilt with the installed SDK. Other Max-year binaries are the upstream builds; the Python render path keeps the fix across versions.
- The transport/executor fixes from the PR #2 review round are present only in the binaries rebuilt in that round (2025, plus any further version the native build reports - TODO for the integrator to confirm before release). Any other shipped `.gup` still predates them; rebuild it against the matching SDK before use.
- Compatible dependencies were refreshed in the isolated environment, including MCP 1.29.1. MCP remains pinned below 2 as required by the upstream API.
- Upstream skill guidance and the fork reference are bundled for both Claude and Codex.

## Verification

465 Python tests pass (430 upstream, 30 preserved fork tests and 5 new compatibility checks).
Progressive discovery of fork extension schemas also passed a real stdio MCP handshake.
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

## Current installation status

Deployment completed on 2026-09-07 with Windows administrator approval.
The shared ApplicationPlugins bundle is enabled for Max 2023–2027, including the installed Max 2025 on C: and Max 2027 on F:.
The old Max 2025 bridge and startup scripts were renamed to rollback copies. Claude and Codex now point to the merged checkout with the full tool profile.
Deployment backups are under `.deployment-backup/20260907-104413`.
The installer discovers custom Max installation paths through the Windows registry and activates the bundle manifest after updating the client configurations.
The September 7 verification confirmed 239 tools and the saved robot scene in Max 2025. The September 9 integration now exposes 254 tools with all 188 original names retained, adds dialog automation and async jobs, and removes slot/TCP routing. Live checks passed in both Max 2025 and 2027; see [UI, jobs and native instances](UI_JOBS_NATIVE_INSTANCES.md) for verification scope and limitations.
