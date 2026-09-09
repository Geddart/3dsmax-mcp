#pragma once
#include <windows.h>

// Overlapped buffers/events must remain alive until completion, even on shutdown.
// Return false after cancelling and draining pending I/O; never dispatch fragments.
inline bool CompletePipeIO(HANDLE pipe, OVERLAPPED& operation, BOOL immediate,
                           DWORD error, HANDLE shutdown, DWORD& transferred) {
    if (immediate) return true;
    if (error != ERROR_IO_PENDING) return false;
    HANDLE events[] = {shutdown, operation.hEvent};
    const DWORD wait = WaitForMultipleObjects(2, events, FALSE, INFINITE);
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
};
