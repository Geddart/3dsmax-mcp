# Dialog automation, async jobs, and native instances

Implemented on the merged **1.5.5+fork** checkout. The custom Redshift, RPManager,
Forest Pack, RailClone and other retained tool modules remain enabled.

Max Ultra MCP's public README inspired the two capabilities; no source from that
repository was copied, installed, or merged. This implementation uses Python,
Windows UI Automation/Win32, and a short deferred MAXScript callback.

## Native instances replace slots

Use `list_max_instances`, then `select_max_instance(pid=12345)`.
`get_selected_max_instance()` reports the current target, and
`release_max_instance()` drops the pin and returns to claim/single routing.
A selection is local to the current MCP server process. There is no
three-instance cap. Multiple unclaimed instances require selection rather than
arbitrary routing. These four names and their `target_pid` / `target_pipe` /
`target_source` fields match upstream 1.6.7, so merges do not collide.

There is **no shared-pipe fallback**. Every request routes to a per-process pipe
(`\\.\pipe\3dsmax-mcp-pid-<pid>`); when nothing is selected, claimed, or singly
live, the call fails with "No live 3ds Max instance with the native bridge
found" instead of reaching whatever listens on the old `\\.\pipe\3dsmax-mcp`
name — which may be a production Max running the old fork bridge.

Routing is reported on every response: `target_pid`, `target_pipe` and
`target_source` (`selected` | `claimed` | `single` | `explicit`) appear in the
transport metadata, and `MaxClient.selected_pid()` resolves the bound PID
without sending anything to Max.

Instance records for dead PIDs are ignored and their files deleted while
enumerating `%LOCALAPPDATA%\3dsmax-mcp\instances`, so a crashed Max cannot
linger in `list_max_instances` or be routed to.

In Max, **MCP → MCP Instances** opens the replacement panel. It lists version,
PID and window/scene title. **Use selected instance** sets the shared default;
**MCP Claim This Max** remains available. Explicit session pins take precedence
over that default. Jobs and observed UI tokens keep their submitted target.

The Python TCP transport, slot manager, numbered slot macros, TCP startup macros
and MAXScript listener are removed. `execute_maxscript` no longer accepts `slot`;
instance-id string routing (`set_active_instance`) is replaced by the PID-based
API above. The old checkout/backups remain historical rollback material and are
not the configured server.

`MCP_Server.escapeJsonString` remains as a helper object: retained plugin tools
depend on it even though they communicate over native pipes.

## Real dialog tools

`max_ui_windows()` finds only visible windows in one Max process.
Pass a returned **token** to `max_ui_inspect(window=token)`, then use an
element token with `max_ui_invoke`, `max_ui_set_value`, or `max_ui_send_keys`.
Re-inspect after an action. `max_ui_wait` waits for a window title;
`max_ui_capture` saves a window-only PNG (no rendering).

**`pid` is optional and should normally be omitted.** It then resolves to the
instance this session is pinned to (`set_active_instance`, via the client's
`selected_pid()`); an unpinned session refuses rather than guessing. A pid that
*is* passed must appear in the live native-bridge instance registry
(`%LOCALAPPDATA%\3dsmax-mcp\instances\pid-*.json`, process still running), so a
typo cannot drive an unrelated Max. PIDs listed in `MCP_UI_DENY_PIDS`
(comma-separated) or in `%LOCALAPPDATA%\3dsmax-mcp\protected_pids.json` are
refused outright — that is how a production Max is fenced off. Both checks run
before the helper process is spawned, and every result reports the `pid` it
actually targeted.

`max_ui_wait` compares titles after normalisation: surrounding whitespace and
the trailing `*` Max appends to a modified scene are ignored. `match="contains"`
opts into a case-insensitive substring match. `timeout_seconds=0` still probes
once, and a short timeout still allows the helper its startup cost instead of
guaranteeing a miss.

`max_ui_set_value` returns `value_written`, `readback` and `matches`. Controls
legitimately normalise text (a spinner turns `1` into `1.0`), so a differing
readback is reported rather than raised; only a failed write raises. The native
Edit fallback uses `WM_SETTEXT`, which does **not** fire a MAXScript rollout
`on entered` handler — pass `commit=true` to send `{ENTER}` through the focused
control afterwards (Max must be foreground; a failed commit comes back as
`committed=false` with `commit_error`, the written value stands either way).

UI operations run in a bounded hidden helper process, not on the MCP or Max
request thread. Its Win32 shim is compiled once into
`%LOCALAPPDATA%\3dsmax-mcp\max_ui_helper_<source-hash>.dll` and reused, so a
call no longer pays the C# compile on every invocation. Tokens check PID,
process start time, window/runtime identity and element ownership.
Password/disabled controls are rejected. UIA patterns are preferred; Max's
standard Edit and CustButton controls have narrow Win32 fallbacks. Actions
report dispatch, not proof that a dialog completed its work.

A hung provider may time out, and GPU/custom windows may capture blank. Input
focus can race user input: prefer value/invoke patterns over SendKeys. A timeout
is an unknown outcome; inspect before retrying. The helper does not automate
other processes or bypass Windows elevation restrictions.

## Async job tools

`max_job_submit(code, label)` returns a handle immediately. A short native request
installs a one-shot WinForms timer on Max's main thread. The timer releases that
request before executing the operation, writing progress/results to local files.
No MAXScript or SDK scene operations run on a background Python thread.

Use `max_job_status`, `max_job_result`, `max_job_list`, `max_job_wait`,
`max_job_cancel` and `max_job_forget`. Result text is paginated. `max_job_render`
uses the current renderer with `vfb:false`, only when a render is requested.

Scripts can call:

```maxscript
for frame = 1 to 100 do (
    mcpJobCheckCancel()
    -- One bounded simulation step here.
    mcpJobProgress frame
)
"finished"
```

Cancellation is cooperative, not a process kill. Cancelling before execution
skips the body; running scripts must check the flag. A blocking renderer/plugin
may ignore cancellation until it returns. The existing `render_automations`
abort path remains available; it uses the bridge's native render-abort handler.

One active/uncertain job per target is allowed in this MCP server. Normal bridge
calls to that target fail fast while reserved; job status/results and UI tools
remain available. Another Max instance can still be used. Other MCP server
processes are not governed by this in-process reservation; coordinate clients
when doing long scene operations.

Scheduling uncertainty is **unknown**, not failed/cancelled, because a request
may execute after a timeout. Accepted scheduling is idempotent; written native
requests are not automatically replayed or retried over TCP. The safe-mode
restricted-function list also applies to submitted scripts.

Handles/history belong to the current MCP server process (maximum 64 retained
jobs). Do not restart MCP during a job: the job can continue in Max but the new
MCP process will not own its handle. Max remains busy during blocking operations;
async handles do not make rendering or simulation itself multithreaded.

## Verification

The subsequent [progressive implementation audit](PROGRESSIVE_AUDIT.md) records
additional fixes, complete schema parity checks, and pending native deployment.

480 automated tests passed, including the progressive async-dispatch regression.
A real MCP handshake confirmed 254 tools, all 188 original tool names,
full-profile async wait/status concurrency, and progressive async dispatch.

Automated tests cover registration/progressive profiles, ownership, input bounds,
nonblocking waits, result pagination, cancellation semantics, safe mode, busy
target reservations, native routing and no replay after a written request.

`scripts/verify_ui_jobs.py PID` explicitly creates a temporary rollout and a real
modal message box, edits/reads a field, invokes buttons, captures a window, runs
a short sleeping job, cancels a cooperative job, and checks target isolation.
It cleans up its dialogs; it does not render or change scene geometry.
`scripts/verify_instance_panel.py PID` verifies the new instance UI and helper.

Live checks passed in Max 2025 and 2027 for the initial dialog/job workflow and
cross-instance job isolation. The modal and running-cancellation checks passed
in Max 2025. Production renders, simulations and every third-party plugin dialog
were not exercised; those remain workload-specific acceptance checks.

Deployment on 2026-09-09 updated the shared bundle script and removed exact old
slot/TCP macro files for both versions, with backups in
`.deployment-backup/native-ui-20260909-224155`. The new panel is loaded in both
running versions. Restart MCP clients to load Python/tool changes; restart Max
to clear cached old macro definitions. Custom toolbar layouts are not rewritten.

Design references: [Max Ultra MCP public README](https://github.com/maxpkg-dev/max-ultra-mcp),
[Autodesk WinForms timer guidance](https://help.autodesk.com/cloudhelp/2021/ENU/3DSMax-MAXScript/files/GUID-DB82F222-B77F-4F85-865F-A4D54B53107D.htm),
[Microsoft InvokePattern blocking behavior](https://learn.microsoft.com/en-us/dotnet/api/system.windows.automation.invokepattern.invoke).
