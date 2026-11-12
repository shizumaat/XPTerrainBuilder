"""The X-Plane overlays of ADOPTED full tiles (#2021, RULINGS 2026-11-12e).

A tile Convert existing tiles adopts into the World pack is a full tile
the app did not build, so it never ran the build's overlay step: its
overlay is made here instead (``O4_Overlay_Utils.background_overlay``),
one tile after another on ONE worker thread, so a Convert run of many
tiles does not wait for them.  Whether a tile needs one is decided at the
request; the worker starts with the first tile that does.

``background_overlay`` uses no build-step state, so it runs beside a
build.  It waits while Convert (or a revert, Free space, a rechoose)
runs: the overlay pack's ``scenery_packs.ini`` row is written only when
that run no longer edits the ini.  Each outcome is a line of the World
pack's log (``world_commands.write_log``).  A request still queued when
the engine quits is not kept: that tile has no overlay until it is
built again.
"""
from __future__ import annotations

import queue
import threading
import time

import O4_World_Pack as WP

__all__ = ["WAIT_S", "request"]

#: Seconds between looks while a Convert run is editing the ini.
WAIT_S = 5.0
_JOBS: "queue.Queue[tuple]" = queue.Queue()
_WORKER: list = []
_LOCK = threading.Lock()


def _log(lat: int, lon: int, state: str) -> None:
    from . import world_commands as WORLD
    WORLD.write_log({"overlay": WP.tile_name(lat, lon), "state": state})


def _work() -> None:
    import O4_Overlay_Utils as OVL

    from . import world_migrate as MIGRATE
    while True:
        lat, lon, scenery_dir = _JOBS.get()
        while MIGRATE.active():
            time.sleep(WAIT_S)
        try:
            state = OVL.background_overlay(lat, lon, scenery_dir)
        except Exception as error:          # logged; the next tile goes on
            state = f"failed: {error!r}"[:300]
        _log(lat, lon, state)


def request(lat: int, lon: int, scenery_dir: str) -> str:
    """Make the overlay of the adopted full tile ``(lat, lon)`` in Custom
    Scenery folder ``scenery_dir`` soon.  Decided at once
    (``O4_Overlay_Utils.overlay_decision``): a tile another pack covers,
    or with nothing to copy, is logged and not queued.  Returns the
    decision's state (``build``: queued)."""
    import O4_Overlay_Utils as OVL
    lat, lon, scenery_dir = int(lat), int(lon), str(scenery_dir or "")
    state = OVL.overlay_decision(lat, lon, scenery_dir)["state"]
    if state != "build":
        _log(lat, lon, state)
        return state
    _JOBS.put((lat, lon, scenery_dir))
    with _LOCK:
        if not _WORKER:
            _WORKER.append(threading.Thread(target=_work, daemon=True,
                                            name="o4-overlay-adopted"))
            _WORKER[0].start()
    return state
