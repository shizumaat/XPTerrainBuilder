"""ONE WRITER PER PACK (#1884 round 2, spec ``1884-round2-spec.md`` §3 B3).

Since #1884 a tile's build writes the DSF of a NEIGHBOUR tile of the same
pack (its guest rows), and every write of a pack DSF reads, composes and
writes back the record beside it and the body files in the pack's shared
``objects/``.  Two tiles in different 10° folders have different records
but one ``objects/``; a forest, drape, optimise or art rewrite of one DSF
re-applies every airport's rows, guests included.  So the unit a writer
locks is the PACK, never one DSF or one record.

The lock is taken ONCE, at the outermost entry of every writer
(``placement_write.apply_routed`` / ``apply_plan``,
``unpatched_pack.restore_airport``, the engine's art-only write,
``pack_rewrite``, the UI restore, the stopped-build replay).  It is NOT
re-entrant: a writer entry reached while this thread already holds the
pack's lock raises ``RuntimeError`` — a nested entry is a structure
defect (an inner step must call the unlocked half), never a second lock
to wait on.  A lock that cannot be had in :data:`WAIT_SECONDS` REFUSES the
write with ``TimeoutError``: nothing of the pack is touched.  (Both are
the builtin classes: a new exception class would need a user message in
``O4_Tile_Failures``, which keys every step and patch build.)

THE LOCK FILE lives in the pack's ``Earth nav data`` (the pack root when
there is none): ``o4_pack_write.lock``, made and removed by
``O4_File_Lock.hold_file_lock``.  It is a write of the pack, so it obeys
the pack-copy write guard: a pack inside a live X-Plane install is refused
before the file is made unless the caller passes the app's
``allow_live_install`` (``pack_copy.write_guard``), exactly as every pack
writer refuses one (§3.5).
"""
from __future__ import annotations

import contextlib
import os
import threading
import typing as _t

__all__ = ["WAIT_SECONDS", "LOCK_NAME", "hold", "live_install_roots"]

#: how long a writer waits for another writer of the same pack (s)
WAIT_SECONDS = 900.0
#: the lock file's name, without the ``.lock`` ``hold_file_lock`` appends
LOCK_NAME = "o4_pack_write"

_local = threading.local()

#: A pack under one of these is the user's LIVE scenery: never a lane's.
_LIVE_HINTS = ("/X-Plane 12/", "/X-Plane 11/", "/X-Plane 12 Demo/")


def live_install_roots(path: str) -> bool:
    """Whether ``path`` lies inside a live X-Plane installation (every pack
    writer's §3.5 refusal; ``dsf_write`` re-exports it)."""
    p = os.path.abspath(path).replace(os.sep, "/") + "/"
    return any(h in p for h in _LIVE_HINTS)


def _key(pack_root: str) -> str:
    return os.path.normcase(os.path.realpath(pack_root))


def _held() -> set:
    got = getattr(_local, "held", None)
    if got is None:
        got = _local.held = set()
    return got


def _lock_path(pack_root: str) -> str:
    """The lock file of ``pack_root`` (module doc)."""
    nav = os.path.join(pack_root, "Earth nav data")
    return os.path.join(nav if os.path.isdir(nav) else pack_root,
                        LOCK_NAME + ".lock")


@contextlib.contextmanager
def hold(pack_root: str, *, allow_live_install: bool = False
         ) -> _t.Iterator[None]:
    """Hold ``pack_root``'s write lock for the block (module doc).
    Raises ``RuntimeError`` when this thread holds it already,
    ``TimeoutError`` when it cannot be had, ``PermissionError`` for a
    live install without ``allow_live_install``."""
    key = _key(pack_root)
    if key in _held():
        raise RuntimeError(
            f"the pack write lock of {pack_root!r} is already held by this "
            f"writer (a nested writer entry)")
    if live_install_roots(pack_root) and not allow_live_install:
        raise PermissionError(
            f"REFUSING to lock a pack inside a live X-Plane installation: "
            f"{pack_root!r} (spec §3.5 — a lane writes a COPY of the pack)")
    if not os.path.isdir(pack_root):
        # a pack that is not there holds nothing to write: the writer's
        # own refusal names it
        _held().add(key)
        try:
            yield
        finally:
            _held().discard(key)
        return
    import O4_File_Lock as _lock
    target = _lock_path(pack_root)[: -len(".lock")]
    with _lock.hold_file_lock(target, timeout_seconds=WAIT_SECONDS) as got:
        if not got:
            name = os.path.basename(os.path.normpath(pack_root))
            raise TimeoutError(f"another write of the pack {name!r} held its "
                           f"lock for {WAIT_SECONDS:.0f} s; nothing was "
                           f"written")
        _held().add(key)
        try:
            yield
        finally:
            _held().discard(key)
