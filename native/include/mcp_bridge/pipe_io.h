#pragma once
#include <windows.h>
#include <cstdio>

// Failure reporting for the transport layer. This header is also compiled into
// the standalone transport tests, which link no Max SDK, so it must stay free of
// SDK logging (Interface::Log). OutputDebugString is visible in DebugView and in
// the VS output window, which is where native-bridge transport issues get read.
inline void LogPipeIOFailure(const char* what, DWORD error) {
    char message[192];
    _snprintf_s(message, sizeof(message), _TRUNCATE,
                "[mcp_bridge] pipe I/O: %s (GetLastError=%lu)\n", what, error);
    OutputDebugStringA(message);
}

// Overlapped buffers/events must remain alive until completion, even on shutdown.
// Return false after cancelling and draining pending I/O; never dispatch fragments.
inline bool CompletePipeIO(HANDLE pipe, OVERLAPPED& operation, BOOL immediate,
                           DWORD error, HANDLE shutdown, DWORD& transferred) {
    if (immediate) return true;
    if (error != ERROR_IO_PENDING) return false;

    // A missing shutdown event is a bug (or a handle already closed), not a
    // shutdown request. Waiting on it would fail anyway; say so out loud, then
    // take the same cancel-and-drain path so the caller's buffers stay valid.
    if (!shutdown) {
        LogPipeIOFailure("CompletePipeIO called with a null shutdown event",
                         ERROR_INVALID_HANDLE);
        CancelIoEx(pipe, &operation);
        GetOverlappedResult(pipe, &operation, &transferred, TRUE);
        return false;
    }

    HANDLE events[] = {shutdown, operation.hEvent};
    const DWORD wait = WaitForMultipleObjects(2, events, FALSE, INFINITE);
    if (wait == WAIT_FAILED) {
        // Distinct from "shutdown was signalled": the wait itself broke (invalid
        // handle, exhausted resources). Silently treating it as shutdown hides a
        // real defect behind a clean-looking disconnect.
        LogPipeIOFailure("WaitForMultipleObjects failed", GetLastError());
    }
    if (wait != WAIT_OBJECT_0 + 1) {
        CancelIoEx(pipe, &operation);
        GetOverlappedResult(pipe, &operation, &transferred, TRUE);
        return false;
    }
    return GetOverlappedResult(pipe, &operation, &transferred, FALSE) != FALSE;
}

class PipeIOEvent {
public:
    OVERLAPPED operation{};
    PipeIOEvent() { operation.hEvent = CreateEvent(nullptr, TRUE, FALSE, nullptr); }
    ~PipeIOEvent() { if (operation.hEvent) CloseHandle(operation.hEvent); }
    PipeIOEvent(const PipeIOEvent&) = delete;
    PipeIOEvent& operator=(const PipeIOEvent&) = delete;

    // Reuse one event across the many chunks of a single request/response
    // instead of a CreateEvent/CloseHandle pair per chunk. Only valid once the
    // previous operation has completed or been cancelled-and-drained: clears the
    // OVERLAPPED (Internal/InternalHigh/Offset are kernel-owned per operation)
    // and resets the manual-reset event that the last completion left signalled.
    void Reset() {
        HANDLE handle = operation.hEvent;
        operation = OVERLAPPED{};
        operation.hEvent = handle;
        if (handle) ResetEvent(handle);
    }
};
