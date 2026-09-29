"""Portable exclusive file lock for the harness ledgers (#92).

``fcntl`` does not exist on Windows; importing it at module top made every
harness tool (artifact ledger, shared-repo guard, run ledger) unimportable
there — and with them the suite's shared-repo and X-Plane guards, which
tests/conftest.py then reported "unavailable".  One lock, two backends:

* POSIX: ``fcntl.flock(LOCK_EX)`` — exactly what the three callers did.
* Windows: ``msvcrt.locking`` on byte 0, retried until granted (``LK_LOCK``
  gives up after ~10 s; a blocked writer must wait, not raise).  Callers
  open their files in append mode, so writes still land at EOF.

Callers are themselves loaded by file path, so each loads this module by
path too (``_load_flock``), cached in ``sys.modules`` under one name.
"""
from __future__ import annotations

import os

try:
    import fcntl as _fcntl
except ImportError:          # Windows
    _fcntl = None
    import msvcrt as _msvcrt


def _fd(fh):
    return fh if isinstance(fh, int) else fh.fileno()


def lock(fh) -> None:
    """Block until an exclusive lock on ``fh`` (file object or fd) is held."""
    if _fcntl is not None:
        _fcntl.flock(_fd(fh), _fcntl.LOCK_EX)
        return
    fd = _fd(fh)
    while True:
        os.lseek(fd, 0, os.SEEK_SET)
        try:
            _msvcrt.locking(fd, _msvcrt.LK_LOCK, 1)
            return
        except OSError:
            continue


def unlock(fh) -> None:
    """Release the lock taken by :func:`lock` (flushes a file object first)."""
    if not isinstance(fh, int):
        fh.flush()
    if _fcntl is not None:
        _fcntl.flock(_fd(fh), _fcntl.LOCK_UN)
        return
    fd = _fd(fh)
    os.lseek(fd, 0, os.SEEK_SET)
    _msvcrt.locking(fd, _msvcrt.LK_UNLCK, 1)

