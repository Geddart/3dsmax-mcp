#include "mcp_bridge/pipe_server.h"
#include "mcp_bridge/bridge_gup.h"
#include "mcp_bridge/command_dispatcher.h"
#include "mcp_bridge/native_handlers.h"
#include "mcp_bridge/pipe_io.h"

PipeServer::PipeServer(MCPBridgeGUP* gup, std::wstring pipe_name)
    : gup_(gup), pipe_name_(std::move(pipe_name)) {
    shutdown_event_ = CreateEvent(nullptr, TRUE, FALSE, nullptr);
}

PipeServer::~PipeServer() {
    Stop();
    if (shutdown_event_) {
        CloseHandle(shutdown_event_);
        shutdown_event_ = nullptr;
    }
}

void PipeServer::Start() {
    if (running_.load()) return;
    running_ = true;
    ResetEvent(shutdown_event_);
    accept_thread_ = std::thread(&PipeServer::AcceptLoop, this);
}

void PipeServer::Stop() {
    if (!running_.load()) return;
    running_ = false;
    SetEvent(shutdown_event_);

    if (accept_thread_.joinable()) {
        accept_thread_.join();
    }

    // Join all client threads
    std::lock_guard<std::mutex> lock(threads_mutex_);
    for (auto& ct : client_threads_) {
        if (ct->thread.joinable()) {
            ct->thread.join();
        }
    }
    client_threads_.clear();
}

void PipeServer::CleanupFinishedThreads() {
    std::lock_guard<std::mutex> lock(threads_mutex_);
    auto it = client_threads_.begin();
    while (it != client_threads_.end()) {
        if ((*it)->done.load()) {
            if ((*it)->thread.joinable()) {
                (*it)->thread.join();
            }
            it = client_threads_.erase(it);
        } else {
            ++it;
        }
    }
}

void PipeServer::AcceptLoop() {
    while (running_.load()) {
        // Cleanup finished client threads periodically
        CleanupFinishedThreads();

        HANDLE pipe = CreateNamedPipeW(
            pipe_name_.c_str(),
            PIPE_ACCESS_DUPLEX | FILE_FLAG_OVERLAPPED,
            PIPE_TYPE_BYTE | PIPE_READMODE_BYTE | PIPE_WAIT,
            PIPE_UNLIMITED_INSTANCES,
            BUFFER_SIZE,
            BUFFER_SIZE,
            0,              // default timeout (use system default, fastest)
            nullptr         // default security (local machine only)
        );

        if (pipe == INVALID_HANDLE_VALUE) {
            Sleep(100);
            continue;
        }

        // Wait for client with overlapped I/O so we can detect shutdown
        PipeIOEvent connection;
        if (!connection.operation.hEvent) {
            CloseHandle(pipe);
            break;
        }
        BOOL connected = ConnectNamedPipe(pipe, &connection.operation);
        const DWORD error = connected ? ERROR_SUCCESS : GetLastError();
        DWORD transferred = 0;
        if (error != ERROR_PIPE_CONNECTED &&
            !CompletePipeIO(pipe, connection.operation, connected, error, shutdown_event_, transferred)) {
            CloseHandle(pipe);
            continue;
        }
        if (!running_.load()) { CloseHandle(pipe); break; }

        // Spawn a thread for this client — accept loop immediately creates
        // the next pipe instance so another client can connect with zero delay
        auto ct = std::make_unique<ClientThread>();
        ClientThread* ctPtr = ct.get();
        ct->thread = std::thread([this, pipe, ctPtr]() {
            HandleClient(pipe);
            DisconnectNamedPipe(pipe);
            CloseHandle(pipe);
            ctPtr->done.store(true);
        });

        std::lock_guard<std::mutex> lock(threads_mutex_);
        client_threads_.push_back(std::move(ct));
    }
}

void PipeServer::HandleClient(HANDLE pipe) {
    static std::atomic<unsigned long long> next_client_id{1};
    const std::string client_id =
        "pipe-" + std::to_string(next_client_id.fetch_add(1));

    while (running_.load()) {
        std::string request = ReadRequest(pipe);
        if (request.empty()) break;

        std::string response;
        try {
            response = CommandDispatcher::Dispatch(request, gup_, client_id);
        } catch (const std::exception& e) {
            response = "{\"success\":false,\"error\":\"Internal bridge error: ";
            std::string msg = e.what();
            for (auto& c : msg) {
                if (c == '"') response += "\\\"";
                else if (c == '\\') response += "\\\\";
                else if (c == '\n') response += "\\n";
                else response += c;
            }
            response += "\",\"meta\":{\"transport\":\"namedpipe\"}}";
        }

        if (!WriteResponse(pipe, response)) {
            break;
        }
    }

    NativeHandlers::ReleaseSceneDeltaSession(client_id);
}

std::string PipeServer::ReadRequest(HANDLE pipe) {
    std::string data;
    char buf[4096];
    while (running_.load()) {
        PipeIOEvent read;
        if (!read.operation.hEvent) return {};
        DWORD bytes_read = 0;
        BOOL ok = ReadFile(pipe, buf, sizeof(buf), &bytes_read, &read.operation);
        const DWORD error = ok ? ERROR_SUCCESS : GetLastError();
        if (!CompletePipeIO(pipe, read.operation, ok, error, shutdown_event_, bytes_read)) return {};
        if (bytes_read == 0) return {};
        if (bytes_read > 0) {
            data.append(buf, bytes_read);
        }
        if (data.find('\n') != std::string::npos) {
            break;
        }
    }
    if (data.find('\n') == std::string::npos) return {};

    while (!data.empty() && (data.back() == '\n' || data.back() == '\r')) {
        data.pop_back();
    }
    return data;
}

bool PipeServer::WriteResponse(HANDLE pipe, const std::string& response) {
    std::string out = response + "\n";
    DWORD written = 0;
    DWORD total = static_cast<DWORD>(out.size());
    const char* ptr = out.c_str();

    while (total > 0) {
        PipeIOEvent write;
        if (!write.operation.hEvent) return false;
        written = 0;
        BOOL ok = WriteFile(pipe, ptr, total, &written, &write.operation);
        const DWORD error = ok ? ERROR_SUCCESS : GetLastError();
        if (!CompletePipeIO(pipe, write.operation, ok, error, shutdown_event_, written) || written == 0) return false;
        ptr += written;
        total -= written;
    }
    return true;
}
