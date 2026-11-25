"""MAKE ROOM BEFORE A RUN (owner 2026-11-18T13:32Z: "When XPTerrainBuilder
starts a build, it probably needs to use the estimated space needed for
the tiles, if there's any new ones, and the storage manager would need to
check the budget and make room if needed before the build begins.").

No storage pass touches a tile a live build holds (``storage_hold``), and
offload no longer runs in a worker child, so room is made BEFORE the run's
first tile starts (``parallel.ParallelBuildRun.start``, the in-process run
in ``session._start_run``):

1. :func:`_need_bytes` -- what the run adds on disk: each tile's
   ``plan_estimate.tile_estimate`` (its tile files and the caches its
   downloads fill, the upper end of the range).  A tile whose outputs
   exist counts only what it is missing (the estimate's own delta).
2. :func:`_make_room` -- what must go: the larger of the shortfall under
   the free-space floor (``storage_floor``) once the run's bytes are
   written, and, with a budget the user SET, how far the run would take
   the stored bytes over it (``storage_budget``; the last shared scan).
   The floor's own passes free it: offload to a mounted tier first, then
   trim (``storage_priority.offload`` / ``clear``), the run's own tiles
   skipped (and their inputs, and every held tile's: ``storage_hold``).
3. One line on the console: "making room: needs X GB, freed Y GB (budget
   B GB)"; when it cannot free enough, one more line says so and the run
   starts anyway -- the per-step disk waits still keep the floor.

A session the harness or the suite runs (``storage_floor.ENV_UNGATED``)
and a parallel run's worker child make no room.

No tile or airport is named here.
"""
from __future__ import annotations

import os
import time
import typing as _t

from . import storage as STORAGE
from . import storage_floor as FLOOR
from . import storage_priority as PRIORITY

__all__ = ["before_run"]

_GB = 1e9


def _need_bytes(tiles, provider, zoomlevel, custom_build_dir,
               step_flags=(True, True, False)) -> int:
    """The bytes the run of ``tiles`` adds on disk (module doc, 1)."""
    from .plan_estimate import tile_estimate
    do_vector, do_imagery, do_overlays = step_flags
    total = 0
    for tile in tiles:
        try:
            row = tile_estimate(int(tile[0]), int(tile[1]), provider,
                                zoomlevel, custom_build_dir, do_vector,
                                do_imagery, do_overlays)
        except Exception:               # an estimate never stops a build
            continue
        total += int(row["tile_bytes"][1]) + int(row["cache_bytes"][1])
    return total


def _budget(scan: "dict | None") -> "tuple[int, int]":
    """``(budget, used)`` bytes from a ``storage_scan`` result (default:
    the last shared one); budget 0 when none is SET (the default clears
    nothing unasked, RULINGS 2026-11-11h (1))."""
    if scan is None:
        from .storage_shared import storage_scan_cached
        scan = storage_scan_cached().get("scan")
    figures = (scan or {}).get("budget") or {}
    if not figures.get("budget_set"):
        return 0, 0
    return (int(figures.get("budget_bytes") or 0),
            int(figures.get("used_bytes") or 0))


def _passes(to_free: int, skip: set, abort, now: float) -> int:
    """Offload, then trim, until ``to_free`` bytes are freed; the bytes
    freed."""
    freed = 0
    spare = FLOOR.corpus_roots()
    for tier_only in (True, False):
        if freed >= to_free:
            break
        sweep = STORAGE._Sweep(False, "making room for a build, %s"
                               % ("offload" if tier_only else "trim"), abort)
        sweep.tier_only, sweep.spare = tier_only, spare
        if tier_only:
            PRIORITY.offload(to_free - freed, sweep, now,
                             PRIORITY.session_tiles(), skip_tiles=skip)
        else:
            PRIORITY.clear(to_free - freed, sweep, now, skip_tiles=skip)
        freed += int(sweep.result().get("freed_bytes") or 0)
    return freed


def _make_room(need: int, run_tiles, raw: "dict | None" = None,
              scan: "dict | None" = None,
              abort: "_t.Callable[[], bool] | None" = None,
              now: "float | None" = None) -> dict:
    """Free what a run adding ``need`` bytes needs (module doc, 2-3);
    ``{"need", "to_free", "freed", "budget", "short"}`` bytes."""
    free = FLOOR.free_bytes()
    floor = FLOOR.floor_bytes(raw)
    budget, used = _budget(scan)
    to_free = max(0, need + floor - free)
    if budget:
        to_free = max(to_free, used + need - budget)
    out = {"need": need, "to_free": to_free, "freed": 0, "budget": budget,
           "short": 0}
    if to_free <= 0:
        return out
    # #2207: why the pass runs, before its first deletion
    STORAGE.write_log("making room for a build: needs %d bytes; free space "
                      "%d bytes, floor %d; budget %s, used %d; clearing %d "
                      "bytes" % (need, free, floor, budget or "not set", used,
                                 to_free))
    skip = {(int(t[0]), int(t[1])) for t in run_tiles}
    now = time.time() if now is None else now
    out["freed"] = _passes(to_free, skip, abort, now)
    out["short"] = max(0, to_free - out["freed"])
    print("making room: needs %.1f GB, freed %.1f GB (budget %s)"
          % (need / _GB, out["freed"] / _GB,
             "%.0f GB" % (budget / _GB) if budget else "not set"))
    if out["short"]:
        print("Could not free %.1f GB more before the build; starting "
              "anyway (each step still waits for the free-space floor)."
              % (out["short"] / _GB))
    STORAGE.write_log("making room: needs %d bytes, %d to free, freed %d"
                      % (need, to_free, out["freed"]))
    return out


def before_run(tiles, provider, zoomlevel, custom_build_dir,
               step_flags=(True, True, False)) -> "dict | None":
    """:func:`_make_room` for a run about to start; ``None`` in an ungated
    session or a worker child.  Never raises: a build always starts."""
    import O4_Machine_Memory as MEMORY
    if os.environ.get(FLOOR.ENV_UNGATED) or os.environ.get(
            MEMORY.ENV_STEP_RESERVED):
        return None
    try:
        need = _need_bytes(tiles, provider, zoomlevel, custom_build_dir,
                          step_flags)
        return _make_room(need, tiles)
    except Exception as error:          # making room never stops a build
        print("Making room before the build failed: %s" % error)
        return None
