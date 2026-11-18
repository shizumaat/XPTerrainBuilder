"""NEVER MID-BUILD (owner 2026-11-18T13:06Z: "we want to cleanup unneeded
files, but not mid-build").

Incident 2026-11-18 (app 1.0.558, tile +53+010): a parallel run's worker
child ran the after-run offload (``storage_offload``) when ITS tile was
done, while its siblings built.  The pass listed the tile's ``.node`` /
``.poly`` -- laid back from the storage tier at the vector step's start,
so carrying the tier copy's old times -- as more than an hour old; the
vector step then rewrote them, and 22 s later the pass moved the new files
to the tier on that stale reading.  The mesh step's Triangle input was
gone.

Every storage pass deletes or moves through ``storage._Sweep.delete``,
which asks :func:`untouchable` first.  A file is left alone when

* it changed since the pass read it (size or mtime): it is being written,
  and the pass's age test was made on an older file; or
* it belongs to a tile a live build holds, in ANY session on the machine
  (the machine ledger's tile holds, ``O4_Machine_Memory.hold_tile``,
  dropped by the OS when the holder exits however it exits).

No tile or airport is named here.
"""
from __future__ import annotations

import os
import threading
import time

__all__ = ["untouchable", "held_tiles"]

#: how long one reading of the ledger's holds serves a pass
_FRESH_S = 2.0
_CACHE: list = []                  # [(monotonic, frozenset)]
_LOCK = threading.Lock()


def held_tiles() -> frozenset:
    """The tiles live builds hold now (read at most every ``_FRESH_S``)."""
    with _LOCK:
        if _CACHE and time.monotonic() - _CACHE[0][0] < _FRESH_S:
            return _CACHE[0][1]
    import O4_Machine_Memory as MEMORY
    try:
        held = frozenset(MEMORY.held_tiles())
    except Exception:                  # a ledger that cannot be read
        held = frozenset()
    with _LOCK:
        _CACHE[:] = [(time.monotonic(), held)]
    return held


def _forget() -> None:
    with _LOCK:
        _CACHE.clear()


def _changed(path: str, st: os.stat_result) -> bool:
    try:
        now = os.lstat(path)
    except OSError:
        return True                    # gone: nothing to do
    return (now.st_size, now.st_mtime_ns) != (st.st_size, st.st_mtime_ns)


def untouchable(store, path: str, st: os.stat_result) -> bool:
    """Whether a pass must leave ``path`` (a file of ``store`` it read as
    ``st``) alone (module doc)."""
    if _changed(path, st):
        return True
    held = held_tiles()
    if not held:
        return False
    from .storage_priority import _tile_of
    try:
        return _tile_of(store, path) in held
    except Exception:
        return False
