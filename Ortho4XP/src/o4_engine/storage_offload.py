"""PROACTIVE OFFLOAD to a storage tier (RULINGS 2026-11-16c, #2103; owner
2026-11-16T03:43Z: "Shouldn't it offload most of the cache since none of
that is needed for x-plane?").

When a storage tier is mounted and has room, the data X-Plane does not
read lives there: after each build run (``RunDone``, once no build is
running) :func:`offload_now` moves every movable cache file -- the
stores of ``storage_tier_data.MOVABLE_KINDS``: orthophotos, the texture
cache, elevation and map data, masks, rebuild data -- to the tier, in
tile priority order (``storage_priority.offload``).  Moving is never
deletion: a tile's next build lays its files back
(``storage_tier_data.recall_tile``).  The internal disk keeps the
flyable files (no cache store holds one, RULINGS 2026-11-14i (3)), any
file written in the last hour or under a held lock, and stops the moment
a build starts (its inputs stay).  The free-space floor
(``storage_floor``) stays the backstop.

The DEV CORPUS (#2093) is never moved: ``storage_floor.corpus_roots``
spares the folders the harness mounts from a data folder holding its
``.harness`` state, and a session the harness or the suite runs
(``storage_floor.ENV_UNGATED``) offloads nothing.

No tile or airport is named here.
"""
from __future__ import annotations

import os
import threading
import time
import typing as _t

from . import storage as STORAGE
from . import storage_floor as FLOOR
from . import storage_priority as PRIORITY

__all__ = ["watch"]

#: An offload with no byte limit: everything movable, until the tier is
#: full (its own size is its budget).
_ALL = 1 << 62
_LOCK = threading.Lock()
_RUNNING = {"on": False}


def _tier_mounted() -> bool:
    from . import storage_tiers as TIERS
    return any(TIERS._mounted(mount) for mount in TIERS._configured())


def offload_now(abort: "_t.Callable[[], bool] | None" = None,
                now: "float | None" = None) -> dict:
    """Move what X-Plane does not read to the mounted tier (module doc);
    the sweep's result plus ``"ran"`` (False: no tier mounted, or a
    harness/suite session)."""
    if os.environ.get(FLOOR.ENV_UNGATED) or not _tier_mounted():
        return {"ran": False, "freed_bytes": 0, "files": 0}
    sweep = STORAGE._Sweep(False, "offload to the storage tier", abort)
    sweep.tier_only, sweep.spare = True, FLOOR.corpus_roots()
    PRIORITY.offload(_ALL, sweep, time.time() if now is None else now)
    return dict(sweep.result(), ran=True)


def _work(busy: _t.Callable[[], bool]) -> None:
    try:
        waited = 0.0
        while busy() and waited < 6 * 3600.0:
            time.sleep(5.0)
            waited += 5.0
        if not busy() and offload_now(busy).get("files"):
            from .storage_shared import refresh
            refresh(busy)
    except Exception as error:          # an offload never fails the app
        print("Moving data to the storage tier failed: %s" % error)
    finally:
        with _LOCK:
            _RUNNING["on"] = False


def watch(session: _t.Any) -> None:
    """After each build run (``RunDone``), :func:`offload_now` in the
    background once no build runs; it stops when one starts.

    Never in a parallel run's WORKER child (incident 2026-11-18, tile
    +53+010's ``.node`` / ``.poly`` moved mid-build): a child's run is one
    tile of its parent's, so its ``RunDone`` and its idle ``_building``
    say nothing of the siblings still building.  The parent's own
    ``RunDone`` -- the whole run's end -- is the one that offloads."""
    import O4_Machine_Memory as MEMORY
    if os.environ.get(MEMORY.ENV_STEP_RESERVED):
        return

    def busy() -> bool:
        return bool(getattr(session, "_building", False))

    def on_event(event) -> None:
        if type(event).__name__ != "RunDone":
            return
        with _LOCK:
            if _RUNNING["on"]:
                return
            _RUNNING["on"] = True
        threading.Thread(target=_work, args=(busy,), daemon=True,
                         name="o4-storage-offload").start()
    session.subscribe(on_event)
