#include "mcp_bridge/pipe_io.h"
#include "mcp_bridge/main_thread_executor.h"
#include <atomic>
#include <iostream>
#include <stdexcept>
#include <thread>

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

int main() {
    try {
        for (int i=0; i<20; ++i) cancelled_pipe_operations();
        expired_work_does_not_execute();
        std::cout << "PASS: pending connect/read/write cancellation; expired work skipped\n";
        return 0;
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n'; return 1;
    }
}
