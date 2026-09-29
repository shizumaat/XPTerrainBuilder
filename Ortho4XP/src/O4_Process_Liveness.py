"""Is a process id alive?  One answer for POSIX and Windows (#83).

``os.kill(pid, 0)`` is the POSIX idiom and it is NOT portable.  On
Windows ``signal.CTRL_C_EVENT == 0``, so CPython routes ``os.kill(pid, 0)``
to ``GenerateConsoleCtrlEvent(CTRL_C_EVENT, pid)``: for a pid that is not a
console process-group leader it raises ``OSError`` (WinError 87) whether
the process is alive or dead, and for one that IS a group leader it
delivers a Ctrl-C to it.  Never a liveness probe.

Measured consequence (Windows CI, #83): the band-fetch lock's stale test
wrote a DEAD child's pid, the probe raised ``OSError`` instead of
``ProcessLookupError``, the owner was read as "undeterminable", and the
waiter polled the 1,800 s mtime fallback until pytest-timeout killed the
xdist worker at 600 s — the ``node down: Not properly terminated`` that
then INTERNALERRORed the loadgroup scheduler.

:func:`pid_is_alive` returns ``True``/``False`` when it can tell and
``None`` when it cannot (permission, platform API absent).  Top-level
imports only (PyInstaller sees them).
"""

import ctypes
import os
import sys

_WINDOWS = sys.platform == "win32"

# Win32 constants.
_PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
_STILL_ACTIVE = 259
_ERROR_ACCESS_DENIED = 5
_ERROR_INVALID_PARAMETER = 87


def _windows_pid_is_alive(pid: int):
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.OpenProcess.restype = ctypes.c_void_p
    kernel32.OpenProcess.argtypes = (
        ctypes.c_uint32, ctypes.c_int, ctypes.c_uint32)
    kernel32.GetExitCodeProcess.argtypes = (
        ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint32))
    kernel32.CloseHandle.argtypes = (ctypes.c_void_p,)
    handle = kernel32.OpenProcess(
        _PROCESS_QUERY_LIMITED_INFORMATION, 0, int(pid))
    if not handle:
        error = ctypes.get_last_error()
        if error == _ERROR_INVALID_PARAMETER:
            return False            # no such process
        if error == _ERROR_ACCESS_DENIED:
            return True             # exists, owned by someone else
        return None
    try:
        exit_code = ctypes.c_uint32()
        if not kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
            return None
        # A process object outlives its process while any handle to it is
        # open (e.g. a Popen that was waited on); it is dead once it has
        # an exit code.  (A process that EXITED with 259 reads as alive —
        # the documented GetExitCodeProcess caveat.)
        return exit_code.value == _STILL_ACTIVE
    finally:
        kernel32.CloseHandle(handle)


def pid_is_alive(pid: int):
    """``True`` alive, ``False`` gone, ``None`` undeterminable."""
    try:
        pid = int(pid)
    except (TypeError, ValueError):
        return None
    if pid <= 0:
        return None
    if _WINDOWS:
        try:
            return _windows_pid_is_alive(pid)
        except (OSError, AttributeError):
            return None
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True                 # exists, another user's
    except OSError:
        return None
    return True
