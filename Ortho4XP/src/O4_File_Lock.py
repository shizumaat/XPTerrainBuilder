"""Cross-process advisory file locks for shared caches.

When several tiles build concurrently in separate worker processes
(``docs/specs/parallel-tile-builds.md``), adjacent tiles fetch an
overlapping three-by-three neighbourhood of base-elevation files and
therefore race to download the very same ``.hgt`` / ``.tif`` into one
shared cache directory.  :func:`hold_file_lock` serialises that critical
section across processes using a sibling lock file created with an
exclusive ``open`` -- the classic ``O_CREAT | O_EXCL`` mutual-exclusion
primitive, which works across every process on a machine and across an
ordinary networked file system, with no dependency beyond the standard
library.

Design priorities, in order:

  * A build must NEVER stall on a lock.  Contention polls until the lock
    is free or a generous timeout elapses; on timeout the caller proceeds
    WITHOUT the lock.  The worst case is then a duplicated download -- the
    exact pre-lock status quo -- never a hung build.
  * A crashed holder must not wedge the cache forever.  The lock file names
    its holder (process id and host); a holder on THIS host that is no
    longer running is reaped at once (#1236: a killed tile used to block
    the next one for up to an hour).  A lock file whose modification time
    is older than one hour is treated as stale whoever holds it.  Either
    way it is broken loudly and re-acquired.
  * The lock file is always removed on exit, including when the guarded
    block raises, and a concurrent removal by another process is
    tolerated.

No graphical-user-interface imports live here: the module depends only on
the standard library and :mod:`O4_UI_Utils` for its warning channel, so
core pipeline modules may import it freely.
"""

from __future__ import annotations

import contextlib
import datetime
import os
import socket
import sys
import threading
import time
from typing import Iterator

import O4_UI_Utils as UI

# A lock file whose modification time is older than this many seconds is
# assumed to belong to a crashed holder: it is broken and re-acquired.
STALE_LOCK_AGE_SECONDS: float = 3600.0

# How long to sleep between acquisition attempts while another process
# holds the lock.
ACQUISITION_POLL_INTERVAL_SECONDS: float = 0.2


def _write_holder_identity(lock_file_descriptor: int) -> None:
    """Record this process's identity inside the freshly created lock file.

    The contents are advisory only -- nothing reads them programmatically
    -- but they make a lingering lock file self-describing for a human
    diagnosing a stuck cache.
    """
    identity = "{process_id} {timestamp} {host}\n".format(
        process_id=os.getpid(),
        timestamp=datetime.datetime.now().isoformat(),
        host=_host(),
    )
    try:
        os.write(lock_file_descriptor, identity.encode("utf-8"))
    finally:
        os.close(lock_file_descriptor)


def _host() -> str:
    """This machine's name, without spaces (the identity line is split on
    them)."""
    return (socket.gethostname() or "unknown").replace(" ", "_")


def _process_is_running(process_id: int) -> bool:
    """True unless ``process_id`` is certainly gone from this machine (an
    unanswerable probe reads as running: the hour rule still reaps it)."""
    if process_id <= 0:
        return True
    if sys.platform == "win32":
        import ctypes
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.OpenProcess(0x1000, False, process_id)  # QUERY_LIMITED
        if not handle:
            return kernel32.GetLastError() != 87     # INVALID_PARAMETER: no such id
        try:
            code = ctypes.c_ulong()
            if not kernel32.GetExitCodeProcess(handle, ctypes.byref(code)):
                return True
            return code.value == 259                 # STILL_ACTIVE
        finally:
            kernel32.CloseHandle(handle)
    try:
        os.kill(process_id, 0)
    except ProcessLookupError:
        return False
    except OSError:
        return True                                  # alive, someone else's
    return True


def _read_identity(lock_path: str):
    """The lock file's identity line, or ``None`` when it cannot be read."""
    try:
        with open(lock_path, "r", encoding="utf-8") as handle:
            return handle.read(256)
    except (OSError, ValueError):
        return None


def _holder_is_dead(identity) -> bool:
    """True when the identity line names a holder on this host that is no
    longer running.  A lock written by an older build (no host), by
    another machine sharing the cache, or not yet written names no holder
    this process can judge."""
    fields = (identity or "").split()
    if len(fields) < 3 or fields[2] != _host():
        return False
    try:
        process_id = int(fields[0])
    except ValueError:
        return False
    if process_id == os.getpid():
        return False
    try:
        return not _process_is_running(process_id)
    except Exception:
        return False


def _lock_file_is_stale(lock_path: str, identity=None) -> bool:
    """True when the lock file is presumed abandoned: its holder on this
    host is gone, or it is older than :data:`STALE_LOCK_AGE_SECONDS`.

    A lock file that has vanished between the failed acquisition and this
    check is reported as not stale, so the caller simply retries the
    exclusive create rather than announcing a spurious stale break.
    """
    try:
        age_seconds = time.time() - os.path.getmtime(lock_path)
    except OSError:
        return False
    return age_seconds > STALE_LOCK_AGE_SECONDS or _holder_is_dead(identity)


def _break_stale_lock(lock_path: str, identity) -> None:
    """Remove the stale lock whose identity line was ``identity``.

    The lock is first RENAMED aside, which exactly one breaker can do; if
    what was moved is not the lock judged stale (another waiter broke it
    and a live holder created a fresh one in between), it is put back, so
    two waiters reaping one dead holder never take a live holder's lock.
    """
    if identity is None:
        with contextlib.suppress(OSError):
            os.remove(lock_path)     # unreadable: the hour rule alone judged it
        return
    aside = "%s.reap-%d-%d" % (lock_path, os.getpid(), threading.get_ident())
    try:
        os.rename(lock_path, aside)
    except OSError:
        return                       # another breaker moved it first
    if _read_identity(aside) == identity:
        with contextlib.suppress(OSError):
            os.remove(aside)
        return
    try:
        if not os.path.exists(lock_path):
            os.rename(aside, lock_path)
            return
    except OSError:
        pass
    with contextlib.suppress(OSError):
        os.remove(aside)


@contextlib.contextmanager
def hold_file_lock(
    target_path: str, timeout_seconds: float = 900.0
) -> Iterator[bool]:
    """Hold a cross-process advisory lock guarding ``target_path``.

    The lock is a sibling file named ``<target_path>.lock`` created with
    ``os.open(..., os.O_CREAT | os.O_EXCL | os.O_WRONLY)`` -- an atomic
    create-if-absent that exactly one process can win.  On contention the
    call polls every
    :data:`ACQUISITION_POLL_INTERVAL_SECONDS` seconds until the lock is
    free or ``timeout_seconds`` elapses.

    The context manager yields ``True`` when the lock was acquired and
    ``False`` when it proceeded without it (a timeout waiting for a holder
    that never released).  Callers may ignore the value: a
    double-checked cache re-read inside the guarded block makes both
    outcomes correct, the ``False`` outcome merely risking a duplicated
    fetch.

    A lock file whose holder on this host is no longer running, or older
    than :data:`STALE_LOCK_AGE_SECONDS`, is presumed to belong to a
    crashed holder; it is removed with one warning and the
    acquisition is retried.  The lock file is always removed on exit when
    (and only when) this call created it, tolerating a concurrent removal
    by another process.

    The caller is responsible for ensuring the parent directory of
    ``target_path`` exists before entering the context.
    """
    lock_path = target_path + ".lock"
    deadline = time.monotonic() + timeout_seconds
    acquired = False
    announced_stale_break = False
    while True:
        try:
            lock_file_descriptor = os.open(
                lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY
            )
        except FileExistsError:
            # Someone else holds it (or crashed holding it).
            identity = _read_identity(lock_path)
            if _lock_file_is_stale(lock_path, identity):
                if not announced_stale_break:
                    UI.vprint(
                        0,
                        "   WARNING: breaking a stale cache lock (its holder "
                        "is gone, or it is older than one hour):",
                        lock_path,
                    )
                    announced_stale_break = True
                _break_stale_lock(lock_path, identity)
                if time.monotonic() < deadline:
                    continue
            if time.monotonic() >= deadline:
                UI.vprint(
                    0,
                    "   WARNING: timed out waiting for the cache lock",
                    lock_path,
                    "- proceeding without it (a duplicated download is the "
                    "only risk).",
                )
                break
            time.sleep(ACQUISITION_POLL_INTERVAL_SECONDS)
            continue
        except OSError as error:
            if os.path.exists(lock_path) and time.monotonic() < deadline:
                # Windows: a lock being removed refuses opens until it is.
                time.sleep(ACQUISITION_POLL_INTERVAL_SECONDS)
                continue
            # The lock cannot be created at all (a read-only or denied
            # folder): locking is advisory, so the block runs unlocked and
            # meets the same folder error itself.
            UI.vprint(
                1,
                "   WARNING: could not create the cache lock",
                lock_path,
                "(%s) - proceeding without it." % error,
            )
            break
        else:
            _write_holder_identity(lock_file_descriptor)
            acquired = True
            break
    try:
        yield acquired
    finally:
        if acquired:
            try:
                os.remove(lock_path)
            except OSError:
                # A stale-break by another process, or a manual cleanup,
                # already removed our lock file -- nothing more to do.
                pass
