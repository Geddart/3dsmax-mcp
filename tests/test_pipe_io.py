"""Real Windows pipe regressions: silent peers and write backpressure."""
import ctypes
from ctypes import wintypes
import threading
import time
import unittest
from uuid import uuid4

from maxmcp.max_client import MaxClient


class PipeDeadlineTests(unittest.TestCase):
    def stalled_peer(self, payload):
        win = ctypes.WinDLL('kernel32', use_last_error=True)
        win.CreateNamedPipeW.argtypes = [wintypes.LPCWSTR] + [wintypes.DWORD]*6 + [wintypes.LPVOID]
        win.CreateNamedPipeW.restype = wintypes.HANDLE
        win.ConnectNamedPipe.argtypes = [wintypes.HANDLE, wintypes.LPVOID]
        win.ConnectNamedPipe.restype = wintypes.BOOL
        win.DisconnectNamedPipe.argtypes = [wintypes.HANDLE]
        win.CloseHandle.argtypes = [wintypes.HANDLE]
        pipe = r'\\.\pipe\mcp-test-' + uuid4().hex
        handle = win.CreateNamedPipeW(pipe, 3, 0, 1, 1024, 1024, 0, None)
        self.assertNotEqual(handle, wintypes.HANDLE(-1).value)
        release = threading.Event()
        def peer():
            win.ConnectNamedPipe(handle, None)
            release.wait(5)
            win.DisconnectNamedPipe(handle)
            win.CloseHandle(handle)
        thread = threading.Thread(target=peer, daemon=True)
        thread.start()
        client = MaxClient(pipe_name=pipe)
        start = time.perf_counter()
        try:
            with self.assertRaises(TimeoutError):
                client._send_via_pipe(payload, .1)
            self.assertLess(time.perf_counter()-start, 1.5)
            self.assertIsNone(client._pipe_handle)
        finally:
            client._close_pipe_handle()
            release.set()
            thread.join(2)
        self.assertFalse(thread.is_alive())

    def test_silent_peer_read_times_out(self):
        self.stalled_peer('{}')

    def test_full_pipe_write_times_out(self):
        self.stalled_peer('x'*2_000_000)
