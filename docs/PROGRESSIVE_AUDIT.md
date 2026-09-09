# Progressive profile and implementation audit

## Configuration and discovery

Codex's `mcp_servers.3dsmax-mcp.env.MCP_TOOL_PROFILE` is now `progressive`.
The previous config was backed up beside `C:/Users/sasch/.codex/config.toml`.
The fork deployment script also selects progressive, so rerunning it no longer
silently restores full mode. Existing Claude configurations were not changed.

A fresh stdio connection launched from the actual saved Codex entry advertised
only `list_toolsets`, `describe_toolset`, and `call_tool`. Every one of the 254
operational input schemas matched full mode across all 22 groups; all 188
original tool names remain present. Loading every group did not expand the
public catalog. Legacy plugin tools and the new UI/job tools are included.

Measured serialized initial `tools/list` responses: full 499,995 bytes versus
progressive 4,552 bytes (99.09% smaller, before subsequent tool descriptions).
This measures initial catalog bytes, not total token use or conversation size.
Later description changes can slightly change those numbers.

The already-running Codex task still exposes the previous full catalog. No
supported live MCP reload control is available to this task. Fresh connections
were started, exercised, and closed successfully; that is not proof that Codex's
own existing connection was reloaded. Reload/restart Codex to finish that step.
The user subsequently confirmed that the Codex settings UI displays progressive.

## Fixes in the Python implementation

- Explicit Max selection now takes precedence over the environment default,
  including the private connection used to schedule a job.
- A request resolves its target once, uses that target for the reservation check
  and send, and records transport failures in its response metadata.
- Pipe reads and writes use deadline-aware overlapped I/O; acquiring a busy
  connection lock is bounded too. Cancellation drains the I/O before freeing
  buffers/events. An attempted write is never automatically replayed, including
  failed writes reporting zero or partial bytes.
- Job callbacks release their Max reservation before publishing completion,
  clean up after setup errors, and explicitly report definite scheduling
  rejection. Timeouts and missing acknowledgements remain uncertain.
- Job state is latched at completion, elapsed time stops increasing, file sharing
  races are tolerated, and non-finite progress cannot leak into JSON results.
- UI waits pass their remaining deadline to the helper process. Set-value
  rejects embedded NUL and verifies exact readback. Keyboard input requires the
  exact observed control to gain focus; native password edits and Alt/global
  shortcuts are rejected. Traversal queues are bounded and truncated inspection
  is reported honestly.

These are source changes in the installed editable checkout. A new MCP process
loads them; an existing Python process must be restarted.

## Native C++ fixes: built, not deployed

The audit also found existing native bridge problems:

- Pipe handles opened for overlapped I/O were used with null OVERLAPPED pointers
  for client reads/writes. Idle client I/O did not reliably observe shutdown.
  Connect cancellation also freed its event before cancellation completed.
- A queued main-thread callback could time out, outlive references captured from
  its caller's stack, and execute later. Expired queued work is now skipped.

The source fixes build successfully against the installed Max 2025 SDK at
`native/build-2025/Release/mcp_bridge.gup`. Native regression tests exercise
pending connect/read/write cancellation repeatedly and verify that expired
queued work never executes. These tests do not require Max or modify a scene.

Neither running Max process has been replaced or restarted. The shared bundle
still contains the previous binaries. Deployment/reload of the 2025 binary is
pending, and rebuilding the 2027 binary requires the 2027 SDK (only the 2025 SDK
was found). Do not use a 2025 binary in 2027.

## Verification and limits

- 492 passing Python unittests, including real Windows pipe timeout/backpressure
  tests, registration, progressive dispatch, legacy compatibility, job state,
  UI validation and ownership tests.
- Real full and configured-progressive MCP connections; all schemas compared;
  actual progressive job submission/wait and concurrent full-mode polling.
- Live Max 2025 and 2027: temporary rollout field edit/readback, button invocation,
  capture, a modal message box, detached short jobs, running cooperative
  cancellation, and cross-instance routing. Test dialogs were cleaned up.
- C++ build and SDK-independent native regression executable passed.

No production renders, simulations, or exhaustive third-party plugin dialog
tests were performed. Schema parity is not proof that every plugin workflow
works in every scene.

The additional keyboard-input check found that a Max rollout Edit can reject
UIA SetFocus. A native focus fallback now verifies the exact focused HWND before
sending keys. The final live acceptance run passed in the restarted Max 2025,
including keyboard input, dialog editing/capture, async jobs and cancellation.
The native focus fallback has not yet been live-tested in Max 2027.

Async handles remain owned by one MCP process; restart loses ownership even
though Max may continue the job. Reservations for ordinary commands are local
to that MCP process, so separate clients must coordinate. Cancellation remains
cooperative. An uncertain job is intentionally retained rather than falsely
reported finished. Max's main thread still executes the actual work. Native
in-flight work is not forcibly interrupted, and a client timeout does not prove
that a command did not run.

References: [Microsoft overlapped I/O deadlines](https://learn.microsoft.com/en-us/windows/win32/api/ioapiset/nf-ioapiset-getoverlappedresultex),
[cancellation lifetime rules](https://learn.microsoft.com/en-us/windows/win32/api/ioapiset/nf-ioapiset-cancelioex).
