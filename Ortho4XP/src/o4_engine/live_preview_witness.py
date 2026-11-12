"""What X-Plane holds, for the map's "Live flight preview" (owner
2026-11-12T19:28Z: the map "show[s] exactly what's showing in X-Plane
when in the Fly view").  ``O4_Live_Preview.squares`` draws the imagery
installed on disk; this says where X-Plane shows something else.

* A 1° tile with no tile of ours -- no DSF in the World pack nor a
  ``zOrtho4XP_<tile>`` pack, or only a World-pack placeholder (an
  overlay: X-Plane falls through to its default mesh) -- is ``own``:
  X-Plane draws its own scenery there, so the map shows its base
  imagery, marked.
* While X-Plane runs, ``Log.txt`` (``O4_XPlane_Log``) says when it
  loaded each tile this session: a tile whose DSF was written or swapped
  in since (its change time is later: a placeholder X-Plane loaded that
  is a tile now, a drape replaced by the full tile) is ``reload``; a
  square whose texture file changed after the load is stale
  (``O4_Live_Preview.squares``: X-Plane still shows the earlier imagery
  until the user reloads).  A tile X-Plane has not loaded yet will be
  read as installed: nothing to mark.
* When the log cannot be read, the follow job's ``late`` landings stand
  in (a tier that landed after X-Plane crossed into its square), while
  their reload offer (``reload_offer``) is pending.

The log is tailed once per path (``LogTail``: only new lines are read)
and X-Plane's process is looked for at most every
:data:`RUNNING_EVERY_S`.
"""
from __future__ import annotations

import os
import threading
import time
from typing import Callable, Optional

__all__ = ["RUNNING_EVERY_S", "late_keys", "tile_state", "xplane_log"]

#: Seconds between looks for X-Plane's process.
RUNNING_EVERY_S = 5.0

_LOCK = threading.Lock()
_LOGS: dict = {}                        # log path -> _Log
_RUNNING = {"at": -1e9, "value": False}


class _Log:
    """One ``Log.txt`` tailed: the latest load of each (pack, tile)."""

    def __init__(self, path: str) -> None:
        import O4_XPlane_Log as XLOG
        self.tail = XLOG.LogTail(path)
        self.restarts = 0
        self.loads: dict = {}

    def read(self) -> "tuple[Optional[float], dict]":
        """``(started, loads)``: X-Plane's start (epoch seconds, ``None``
        when the log does not say) and ``{(pack, lat, lon): DsfLoad}``."""
        records = self.tail.read()
        if self.tail.restarts != self.restarts:
            self.restarts, self.loads = self.tail.restarts, {}
        for rec in records:
            self.loads[(rec.pack, rec.lat, rec.lon)] = rec
        return _epoch(self.tail.started), self.loads


def _epoch(started: Optional[str]) -> Optional[float]:
    """``Thu Nov 12 11:18:45 2026`` (local time) as epoch seconds."""
    if not started:
        return None
    try:
        return time.mktime(time.strptime(started.strip(), "%a %b %d %H:%M:%S %Y"))
    except (ValueError, OverflowError):
        return None


def xplane_log(xplane_dir: str) -> "tuple[Optional[float], dict]":
    """``_Log.read`` of ``<xplane_dir>/Log.txt``, tailed across calls."""
    import O4_XPlane_Log as XLOG
    path = XLOG.log_path(xplane_dir)
    with _LOCK:
        log = _LOGS.get(path)
        if log is None:
            log = _LOGS[path] = _Log(path)
        return log.read()


def _xplane_running(now: Optional[float] = None) -> bool:
    now = time.monotonic() if now is None else now
    if now - _RUNNING["at"] >= RUNNING_EVERY_S:
        from .xplane_root import xplane_running
        _RUNNING.update(at=now, value=bool(xplane_running()))
    return _RUNNING["value"]


def _changed(path: str) -> float:
    """When ``path`` was last written or renamed into place (a rename
    keeps the modification time and moves the change time)."""
    try:
        st = os.stat(path)
    except OSError:
        return 0.0
    return max(st.st_mtime, st.st_ctime)


def tile_state(scenery_dir: str, running: Optional[bool] = None,
               log=None) -> Callable[[int, int], tuple]:
    """``(lat, lon) -> (state, loaded_at)`` for ``O4_Live_Preview.
    squares`` (the module docstring): ``state`` ``"ours"``, ``"own"`` or
    ``"reload"``; ``loaded_at`` when X-Plane loaded the tile (epoch
    seconds) or ``None``.  ``running`` / ``log`` (``(started, loads)``)
    are read here when not given.  With no Custom Scenery folder nothing
    is known and every tile is ``ours``."""
    import O4_World_Pack as WP

    from .storage_installed import PREFIX
    if not scenery_dir:
        return lambda lat, lon: ("ours", None)
    running = _xplane_running() if running is None else running
    if log is None:
        log = (xplane_log(os.path.dirname(os.path.normpath(scenery_dir)))
               if running else (None, {}))
    started, loads = log
    world = os.path.join(scenery_dir, WP.PACK_NAME)

    def state(lat: int, lon: int) -> tuple:
        tile, rel = WP.tile_name(lat, lon), WP.dsf_relpath(lat, lon)
        world_dsf = os.path.join(world, rel)
        pack_dsf = os.path.join(scenery_dir, PREFIX + tile, rel)
        in_world = os.path.isfile(world_dsf) and not WP.is_placeholder(world_dsf)
        dsf = world_dsf if in_world else (pack_dsf if os.path.isfile(pack_dsf)
                                          else None)
        if dsf is None:
            return "own", None
        if not running or started is None:
            return "ours", None
        held = [loads[k] for k in ((WP.PACK_NAME, lat, lon),
                                   (PREFIX + tile, lat, lon)) if k in loads]
        if not held:
            return "ours", None          # read as installed when it loads
        load = max(held, key=lambda r: r.t_s)
        loaded_at = started + load.t_s
        if _changed(dsf) > loaded_at:
            return "reload", loaded_at
        return "ours", loaded_at
    return state


def late_keys(scenery_dir: str, running: Optional[bool] = None,
              log=None) -> frozenset:
    """``{"<tile>/<texture>"}`` of the follow job's late landings, the
    stand-in witness: only while X-Plane runs, its ``Log.txt`` cannot be
    read (no start stamp) and the landings' reload offer is pending."""
    from . import reload_offer as RELOAD
    from .imagery_commands import follow_late_landings
    running = _xplane_running() if running is None else running
    if not running or not scenery_dir or not RELOAD.current():
        return frozenset()
    if log is None:
        log = xplane_log(os.path.dirname(os.path.normpath(scenery_dir)))
    if log[0] is not None:
        return frozenset()
    return frozenset(follow_late_landings())
