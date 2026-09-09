#include "mcp_bridge/pipe_io.h"
#include "mcp_bridge/main_thread_executor.h"
#include <atomic>
#include <chrono>
#include <iostream>
#include <stdexcept>
#include <string>
#include <thread>

using Clock = std::chrono::steady_clock;

long long ms_since(Clock::time_point start) {
    return std::chrono::duration_cast<std::chrono::milliseconds>(Clock::now() - start).count();
}

// Mirrors MainThreadExecutor::WM_MCP_EXECUTE (private). Filtering on it keeps
// these assertions about OUR work items and not about whatever else Windows
// leaves in a thread queue.
constexpr UINT kExecuteMessage = WM_USER + 0x4D43;

bool execute_message_queued() {
    MSG message;
    return PeekMessage(&message, nullptr, kExecuteMessage, kExecuteMessage, PM_NOREMOVE) != FALSE;
}

// Spin (bounded) until a worker's ExecuteSync has really queued its work item.
bool wait_for_queued_message(int timeout_ms) {
    const auto start = Clock::now();
    while (ms_since(start) < timeout_ms) {
        if (execute_message_queued()) return true;
        Sleep(1);
    }
    return false;
}

void ShowChat() {}
void ClaimNativeInstance() {}
void RunToolSmokeMacro() {}
void require(bool ok, const char* message) { if (!ok) throw std::runtime_error(message); }

void cancelled_pipe_operations() {
    std::wstring name = L"\\\\.\\pipe\\mcp-native-test-" + std::to_wstring(GetCurrentProcessId());
    HANDLE shutdown = CreateEvent(nullptr, TRUE, FALSE, nullptr);
    HANDLE pipe = CreateNamedPipeW(name.c_str(), PIPE_ACCESS_DUPLEX | FILE_FLAG_OVERLAPPED,
                                  PIPE_TYPE_BYTE | PIPE_WAIT, 1, 1024, 1024, 0, nullptr);
    require(pipe != INVALID_HANDLE_VALUE, "create pipe");
    {
        PipeIOEvent connect;
        BOOL ok = ConnectNamedPipe(pipe, &connect.operation);
        DWORD error = ok ? 0 : GetLastError(), bytes = 0;
        require(error == ERROR_IO_PENDING, "connect pending");
        SetEvent(shutdown);
        require(!CompletePipeIO(pipe, connect.operation, ok, error, shutdown, bytes), "cancel connect");
    }
    ResetEvent(shutdown);
    {
        PipeIOEvent connect;
        BOOL ok = ConnectNamedPipe(pipe, &connect.operation);
        DWORD error = ok ? 0 : GetLastError(), bytes = 0;
        HANDLE client = CreateFileW(name.c_str(), GENERIC_READ|GENERIC_WRITE, 0, nullptr, OPEN_EXISTING, 0, nullptr);
        require(client != INVALID_HANDLE_VALUE, "connect client");
        require(CompletePipeIO(pipe, connect.operation, ok, error, shutdown, bytes), "complete connect");
        {
            char buffer[16]; PipeIOEvent read;
            ok = ReadFile(pipe, buffer, sizeof(buffer), &bytes, &read.operation);
            error = ok ? 0 : GetLastError();
            require(error == ERROR_IO_PENDING, "read pending");
            SetEvent(shutdown);
            require(!CompletePipeIO(pipe, read.operation, ok, error, shutdown, bytes), "cancel read");
        }
        ResetEvent(shutdown);
        {
            std::string buffer(100000, 'x'); PipeIOEvent write;
            ok = WriteFile(pipe, buffer.data(), static_cast<DWORD>(buffer.size()), &bytes, &write.operation);
            error = ok ? 0 : GetLastError();
            require(error == ERROR_IO_PENDING, "write pending");
            SetEvent(shutdown);
            require(!CompletePipeIO(pipe, write.operation, ok, error, shutdown, bytes), "cancel write");
        }
        CloseHandle(client);
    }
    DisconnectNamedPipe(pipe); CloseHandle(pipe); CloseHandle(shutdown);
}

// A null shutdown event is a defect, not a shutdown: CompletePipeIO must still
// cancel and drain (so the caller's OVERLAPPED stays valid) and report failure.
// One PipeIOEvent is reused across both operations via Reset(), which is how the
// pipe server now runs multi-chunk reads and writes.
void null_shutdown_and_event_reuse() {
    std::wstring name = L"\\\\.\\pipe\\mcp-native-reuse-" + std::to_wstring(GetCurrentProcessId());
    HANDLE pipe = CreateNamedPipeW(name.c_str(), PIPE_ACCESS_DUPLEX | FILE_FLAG_OVERLAPPED,
                                   PIPE_TYPE_BYTE | PIPE_WAIT, 1, 1024, 1024, 0, nullptr);
    require(pipe != INVALID_HANDLE_VALUE, "create reuse pipe");
    PipeIOEvent connect;
    require(connect.operation.hEvent != nullptr, "create reuse event");

    BOOL ok = ConnectNamedPipe(pipe, &connect.operation);
    DWORD error = ok ? 0 : GetLastError(), bytes = 0;
    require(error == ERROR_IO_PENDING, "reuse connect pending");
    require(!CompletePipeIO(pipe, connect.operation, ok, error, nullptr, bytes), "null shutdown fails");

    // Same event, second operation — Reset() must clear the signalled state and
    // the kernel-owned OVERLAPPED fields, or the wait below returns instantly.
    HANDLE shutdown = CreateEvent(nullptr, TRUE, FALSE, nullptr);
    connect.Reset();
    require(WaitForSingleObject(connect.operation.hEvent, 0) == WAIT_TIMEOUT, "reset clears event");
    ok = ConnectNamedPipe(pipe, &connect.operation);
    error = ok ? 0 : GetLastError();
    require(error == ERROR_IO_PENDING || error == ERROR_PIPE_CONNECTED, "re-issued connect pending");
    HANDLE client = CreateFileW(name.c_str(), GENERIC_READ|GENERIC_WRITE, 0, nullptr, OPEN_EXISTING, 0, nullptr);
    require(client != INVALID_HANDLE_VALUE, "reuse client connects");
    if (error == ERROR_IO_PENDING) {
        require(CompletePipeIO(pipe, connect.operation, ok, error, shutdown, bytes), "reused event completes");
    }

    CloseHandle(client);
    DisconnectNamedPipe(pipe); CloseHandle(pipe); CloseHandle(shutdown);
}

void expired_work_does_not_execute() {
    MainThreadExecutor executor;
    executor.Initialize();
    std::atomic<bool> ran{false}, expired{false};
    std::thread worker([&] {
        try { executor.ExecuteSync([&] { ran=true; return "late"; }, 10); }
        catch (const std::runtime_error&) { expired=true; }
    });
    worker.join(); // deliberately do not pump the queued callback before timeout
    MSG message;
    while (PeekMessage(&message, nullptr, 0, 0, PM_REMOVE)) DispatchMessage(&message);
    require(expired && !ran, "expired callback executed");
    executor.Shutdown();
}

// Regression: Max used to hang on exit. A client thread inside ExecuteSync waits
// for a WM_MCP_EXECUTE the main thread can no longer pump (it is blocked joining
// that very thread), so the waiter slept out its whole timeout. BeginShutdown
// must complete queued items with an error immediately.
void shutdown_wakes_queued_waiter() {
    MainThreadExecutor executor;
    executor.Initialize();
    std::atomic<bool> ran{false}, errored{false};
    std::thread worker([&] {
        try { executor.ExecuteSync([&] { ran = true; return std::string("late"); }, 20000); }
        catch (const std::runtime_error&) { errored = true; }
    });
    require(wait_for_queued_message(5000), "work item never reached the queue");

    const auto start = Clock::now();
    executor.BeginShutdown();   // deliberately never pump the message
    worker.join();
    const long long elapsed = ms_since(start);

    require(errored, "queued waiter did not fail on shutdown");
    require(!ran, "work executed during shutdown");
    require(elapsed < 2000, "queued waiter woke only after its timeout expired");

    // The drain must have consumed the message, not left it for DestroyWindow
    // to discard (which is what leaked the heap shared_ptr).
    require(!execute_message_queued(), "shutdown left work queued");
    executor.Shutdown();
}

// Once shutting down, a background ExecuteSync must throw at once instead of
// posting work nobody will ever pump.
void execute_after_shutdown_fails_fast() {
    MainThreadExecutor executor;
    executor.Initialize();
    executor.BeginShutdown();
    require(MainThreadExecutor::IsShuttingDown(), "shutdown flag not set");

    std::atomic<bool> ran{false}, errored{false};
    const auto start = Clock::now();
    std::thread worker([&] {
        try { executor.ExecuteSync([&] { ran = true; return std::string("nope"); }, 20000); }
        catch (const std::runtime_error&) { errored = true; }
    });
    worker.join();
    const long long elapsed = ms_since(start);

    require(errored, "ExecuteSync after shutdown did not fail");
    require(!ran, "work executed after shutdown");
    require(elapsed < 2000, "ExecuteSync after shutdown blocked instead of failing fast");
    require(!execute_message_queued(), "failed submission still posted work");
    executor.Shutdown();
}

// The shutdown gate is process-wide, so a fresh Initialize() has to reopen it —
// otherwise one Stop/Start cycle would leave the bridge permanently dead.
void initialize_reopens_after_shutdown() {
    MainThreadExecutor executor;
    executor.Initialize();
    require(!MainThreadExecutor::IsShuttingDown(), "initialize left the gate closed");

    std::atomic<bool> done{false};
    std::string result;
    std::thread worker([&] {
        result = executor.ExecuteSync([] { return std::string("ok"); }, 20000);
        done = true;
    });
    const auto start = Clock::now();
    MSG message;
    while (!done.load() && ms_since(start) < 5000) {
        while (PeekMessage(&message, nullptr, 0, 0, PM_REMOVE)) DispatchMessage(&message);
        Sleep(1);
    }
    worker.join();
    require(done && result == "ok", "executor did not run work after re-initialize");
    executor.Shutdown();
}

int main() {
    try {
        for (int i=0; i<20; ++i) cancelled_pipe_operations();
        null_shutdown_and_event_reuse();
        expired_work_does_not_execute();
        shutdown_wakes_queued_waiter();
        execute_after_shutdown_fails_fast();
        initialize_reopens_after_shutdown();
        std::cout << "PASS: pending connect/read/write cancellation; null-shutdown + event reuse; "
                     "expired work skipped; shutdown wakes queued waiter; execute-after-shutdown fails fast; "
                     "initialize reopens the gate\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n'; return 1;
    }
}
