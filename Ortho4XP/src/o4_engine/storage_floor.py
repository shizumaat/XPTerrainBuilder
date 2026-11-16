"""The FREE-SPACE FLOOR of the disk that holds the data folder (#2103,
owner 2026-11-16T03:34Z: "shouldn't XPTerrainBuilder be managing this
automatically as it's building tiles and trimming cache, old tiles, and
offloading imagery to the allocated external drive since it's mounted?").

The disk budget (``storage_budget``) holds what XPTerrainBuilder stores;
the disk is shared with X-Plane and everything else, so a budget well
under the disk can still leave it nearly full.  This module watches the
disk itself:

* :data:`SETTING` -- ``storage_free_floor_gb`` (Settings ▸ Storage, both
  apps), default :data:`DEFAULT_FLOOR_GB`; 0 is off.
* :func:`admits` -- the build scheduler's question before a step starts
  (``parallel.ParallelBuildRun._disk_admits_locked``): is the free space
  at or above the floor?  When it is not, :func:`relieve_async` starts a
  relief in the background and the step WAITS, its row showing
  :func:`wait_message` (a ``MemoryWait`` event with reason
  :data:`REASON_DISK`); the scheduler's ticker dispatches again, so the
  step starts as soon as the floor is met.
* :func:`relieve` -- frees space until :data:`MARGIN_BYTES` above the
  floor, in two passes, each in tile priority order
  (``storage_priority.clear``, RULINGS 2026-11-14i): first OFFLOAD only
  (a movable file goes to a mounted storage tier, ``storage_tier_data``;
  nothing is deleted, made low-res or packaged) -- the unprotected tiles
  first, then, still short, the PROTECTED ones too (used in the last
  week, then this session's; ``storage_priority.offload``):
  moving keeps their data, so "never cleared" holds; the inputs of this
  session's builds stay.  Then TRIM (the budget's own clearing: moved
  when a tier has room, else deleted), which never reaches a protected
  tile.  Nothing X-Plane loads is in a cache store, and a tier never
  takes a flyable file (``storage_tier_data._movable``).
* The DEV CORPUS is never touched (#2093): a data folder holding the
  harness's ``.harness`` state is the shared measurement corpus, and the
  folders the harness mounts from it (:data:`CORPUS_DIRS`, the twin of
  ``tools/harness/shared_repo_guard.SHARED_DATA_DIRS``) are spared by
  both passes (:func:`corpus_roots`).

No tile or airport is named here.
"""
from __future__ import annotations

import os
import shutil
import threading
import time
import typing as _t

import O4_File_Names as FNAMES

from . import storage as STORAGE
from . import storage_priority as PRIORITY

__all__ = ["SETTING", "DEFAULT_FLOOR_GB", "MARGIN_BYTES", "REASON_DISK",
           "ENV_UNGATED", "CORPUS_MARKER", "CORPUS_DIRS", "floor_bytes", "free_bytes",
           "admits", "corpus_roots", "relieve", "relieve_async",
           "wait_message"]

SETTING = "storage_free_floor_gb"
DEFAULT_FLOOR_GB = 60.0
#: A relief frees this much above the floor, so the next step's writes do
#: not trip it again at once.
MARGIN_BYTES = 10 * 10**9
#: ``MemoryWait.reason`` of a step held for the disk floor.
REASON_DISK = "disk"
#: Set by a session that is not the app's (the test suite, the harness's
#: builds, which keep their own floor: ``build_airport.disk_floor_gate``):
#: the scheduler's gate always admits.  The app never sets it.
ENV_UNGATED = "O4_DISK_FLOOR_UNGATED"
#: The harness's state folder at the root of the shared dev corpus.
CORPUS_MARKER = ".harness"
#: The folders the harness mounts from the corpus (twinned with
#: ``shared_repo_guard.SHARED_DATA_DIRS``).
CORPUS_DIRS = ("OSM_data", "Elevation_data", "Airport_mod_cache",
               "Geotiffs", "Masks", "Default_DSF_cache", "Orthophotos")
#: A relief that freed nothing is not retried for this long (the disk
#: does not change by waiting on the same files).
RETRY_SECONDS = 300.0
_GB = 1e9
_LOCK = threading.Lock()
_STATE = {"running": False, "last_at": 0.0, "last_freed": -1}


def floor_bytes(raw: "dict | None" = None) -> int:
    """The floor in bytes; 0 when it is off."""
    if raw is None:
        import O4_Settings_Model as SM
        raw = SM.read_global_raw()
    value = raw.get(SETTING, "")
    try:
        gigabytes = DEFAULT_FLOOR_GB if value in ("", None) else float(value)
    except (TypeError, ValueError):
        gigabytes = DEFAULT_FLOOR_GB
    return int(gigabytes * _GB) if gigabytes > 0 else 0


def free_bytes(root: "str | None" = None) -> int:
    """Free bytes on the disk holding ``root`` (the data folder)."""
    try:
        return int(shutil.disk_usage(root or FNAMES.current_data_root()).free)
    except OSError:
        return 0


def admits(raw: "dict | None" = None) -> "tuple[bool, int, int]":
    """``(ok, free, floor)``: ``ok`` when the floor is off or met, or the
    session is :data:`ENV_UNGATED`."""
    if os.environ.get(ENV_UNGATED):
        return True, 0, 0
    floor = floor_bytes(raw)
    if not floor:
        return True, 0, 0
    free = free_bytes()
    return free >= floor, free, floor


def _in_corpus(folder: str) -> bool:
    parent = os.path.dirname(os.path.realpath(folder))
    return os.path.isdir(os.path.join(parent, CORPUS_MARKER))


def corpus_roots(root: "str | None" = None) -> tuple:
    """The dev corpus folders under ``root`` (#2093): each of
    :data:`CORPUS_DIRS` that is (or links into) a folder whose data root
    holds :data:`CORPUS_MARKER`; ``()`` for an ordinary data folder."""
    root = root or FNAMES.current_data_root()
    out = []
    for name in CORPUS_DIRS:
        folder = os.path.join(root, name)
        if _in_corpus(folder):
            out += [folder, os.path.realpath(folder)]
    return tuple(dict.fromkeys(out))


def _pass(need: int, tier_only: bool, spare: tuple, abort, now: float) -> dict:
    reason = "free-space floor, %s" % ("offload" if tier_only else "trim")
    sweep = STORAGE._Sweep(False, reason, abort)
    sweep.tier_only, sweep.spare = tier_only, spare
    if tier_only:
        # Moving keeps the data: the protected tiles' too; the inputs of
        # this session's builds stay.
        PRIORITY.offload(need, sweep, now, PRIORITY.session_tiles())
    else:
        PRIORITY.clear(need, sweep, now)
    return sweep.result()


def relieve(abort: "_t.Callable[[], bool] | None" = None,
            raw: "dict | None" = None, now: "float | None" = None) -> dict:
    """Offload, then trim, until the free space is :data:`MARGIN_BYTES`
    above the floor (module doc); ``{"ran", "free_before", "free_after",
    "floor", "passes"}`` (``passes``: each sweep's result)."""
    floor = floor_bytes(raw)
    free = before = free_bytes()
    out = {"ran": False, "free_before": before, "free_after": before,
           "floor": floor, "passes": []}
    if not floor or free >= floor:
        return out
    STORAGE.write_log("free space %d bytes is under the floor %d bytes: "
                      "offloading, then trimming" % (free, floor))
    spare = corpus_roots()
    now = time.time() if now is None else now
    out["ran"] = True
    for tier_only in (True, False):
        need = floor + MARGIN_BYTES - free
        if need <= 0:
            break
        out["passes"].append(_pass(need, tier_only, spare, abort, now))
        free = free_bytes()
    out["free_after"] = free
    if free < floor:
        STORAGE.write_log("free space %d bytes is still under the floor %d "
                          "bytes: what is left is kept" % (free, floor))
    return out


def relieve_async(abort: "_t.Callable[[], bool] | None" = None) -> bool:
    """Start :func:`relieve` on a background thread unless one runs or
    the last one freed nothing within :data:`RETRY_SECONDS`; whether one
    started."""
    with _LOCK:
        if _STATE["running"]:
            return False
        if (_STATE["last_freed"] == 0
                and time.time() - _STATE["last_at"] < RETRY_SECONDS):
            return False
        _STATE["running"] = True

    def run():
        freed = 0
        try:
            result = relieve(abort)
            freed = sum(int(p.get("freed_bytes") or 0)
                        for p in result["passes"])
        except Exception as error:      # a relief must never stop a build
            print("Freeing disk space failed: %s" % error)
        finally:
            with _LOCK:
                _STATE.update(running=False, last_at=time.time(),
                              last_freed=freed)

    threading.Thread(target=run, name="storage-floor", daemon=True).start()
    return True


def wait_message(free_gb: float, floor_gb: float) -> str:
    """The sentence a tile's row shows while its step waits for disk
    (``free_gb``, ``floor_gb`` in gigabytes)."""
    return ("Waiting for disk space: %.0f GB free, keeping at least %.0f GB "
            "(Settings > Storage). Older data is being moved to the storage "
            "tier or cleared; freeing space on the disk also lets it start."
            % (max(0.0, free_gb), floor_gb))
