"""Deadline-aware Win32 overlapped I/O for the local Max named pipe."""
import ctypes
from ctypes import wintypes
import math
import time


class Overlapped(ctypes.Structure):
    _fields_ = [('Internal', ctypes.c_size_t), ('InternalHigh', ctypes.c_size_t),
                ('Offset', wintypes.DWORD), ('OffsetHigh', wintypes.DWORD),
                ('hEvent', wintypes.HANDLE)]


kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
kernel32.CreateEventW.argtypes = [wintypes.LPVOID, wintypes.BOOL, wintypes.BOOL, wintypes.LPCWSTR]
kernel32.CreateEventW.restype = wintypes.HANDLE
kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
kernel32.CloseHandle.restype = wintypes.BOOL
kernel32.GetOverlappedResultEx.argtypes = [wintypes.HANDLE, ctypes.POINTER(Overlapped),
                                         ctypes.POINTER(wintypes.DWORD), wintypes.DWORD, wintypes.BOOL]
kernel32.GetOverlappedResultEx.restype = wintypes.BOOL
kernel32.GetOverlappedResult.argtypes = [wintypes.HANDLE, ctypes.POINTER(Overlapped),
                                       ctypes.POINTER(wintypes.DWORD), wintypes.BOOL]
kernel32.GetOverlappedResult.restype = wintypes.BOOL
kernel32.CancelIoEx.argtypes = [wintypes.HANDLE, ctypes.POINTER(Overlapped)]
kernel32.CancelIoEx.restype = wintypes.BOOL


def transfer(function, handle, buffer, count, deadline):
    """Return (success, error, bytes); timeouts never imply safe replay.

    Keep the buffer, OVERLAPPED and event alive until cancellation completes.
    Closing an event immediately after CancelIoEx would allow use-after-free.
    """
    remaining = deadline - time.perf_counter()
    if remaining <= 0:
        raise TimeoutError('Named pipe deadline expired; request outcome may be unknown')
    event = kernel32.CreateEventW(None, True, False, None)
    if not event:
        raise OSError(ctypes.get_last_error(), 'Could not create pipe I/O event')
    overlapped = Overlapped(hEvent=event)
    transferred = wintypes.DWORD()
    pending = False
    try:
        ok = function(handle, buffer, count, ctypes.byref(transferred), ctypes.byref(overlapped))
        error = 0 if ok else ctypes.get_last_error()
        if not ok and error == 997:  # ERROR_IO_PENDING
            pending = True
            milliseconds = max(1, min(0xfffffffe, math.ceil((deadline-time.perf_counter()) * 1000)))
            ok = kernel32.GetOverlappedResultEx(handle, ctypes.byref(overlapped),
                                               ctypes.byref(transferred), milliseconds, False)
            error = 0 if ok else ctypes.get_last_error()
            if error in (258, 996):  # WAIT_TIMEOUT / ERROR_IO_INCOMPLETE
                raise TimeoutError('Named pipe I/O timed out; request outcome may be unknown')
            pending = False
        return bool(ok), error, transferred.value
    finally:
        if pending:
            kernel32.CancelIoEx(handle, ctypes.byref(overlapped))
            kernel32.GetOverlappedResult(handle, ctypes.byref(overlapped), ctypes.byref(transferred), True)
        kernel32.CloseHandle(event)
