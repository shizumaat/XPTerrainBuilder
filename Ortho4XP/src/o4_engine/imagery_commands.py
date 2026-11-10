"""Imagery commands: the launch-time liveness check (protocol 1.17, #1345)
and the tile info's imagery check (protocol 1.27, #1666).

``imagery_source_status`` replies ``{"started": true, "count": N}`` at
once; one ``ImagerySourceStatus`` event per source follows from worker
threads (``O4_Imagery_Sources.check_status``).

``imagery_freshness`` replies ``{"status": "started"}``; a worker thread
completes it with ``ImageryFreshnessReady`` carrying the command's id and
``O4_Imagery_Freshness.tile_freshness``'s answer.  ``imagery_freshness_
discard`` ("Update Imagery") removes the tile's cached orthophotos and
base textures so the rebuild the app starts next downloads them again;
synchronous file work.

``imagery_follow_start`` (#1992 P3b) starts the follow job
(``o4_engine.imagery_follow``) and replies ``{"status": "started"}`` (or
``"running"``); ``ImageryFollowStatus`` events report it until
``imagery_follow_stop`` ends it and replies its counts.  One job per
engine.  After a spawn or jump whose imagery missed X-Plane's flight-start
window the job asks X-Plane to reload its scenery (#1992 P5, capability
``imagery_spawn_reload``); ``reload: false`` starts a job that never does.

On-demand imagery (#1992, capability ``imagery_ondemand``):
``imagery_ondemand_scan`` (the index rebuilt from the on-demand tiles),
``imagery_pin`` (a tile's "always full resolution"),
``imagery_ondemand_sweep`` (hold the storage cap now) and
``imagery_ondemand_downgrade_all`` ("Make all low-res again"), synchronous
file work in :mod:`o4_engine.imagery_ondemand`; those that change
textures are refused while a build runs (:func:`ondemand_handlers`).

A command module, not a session method, so the imagery menus stay out of
the session's import closure (the patch and step code keys,
``tests/test_patch_code_closure.py``).
"""
from __future__ import annotations

import os
import threading
from typing import Any, Callable, Dict, Optional, Sequence

import O4_Imagery_Sources as SOURCES

from .events import ImageryFreshnessReady, ImagerySourceStatus

_FOLLOW: Dict[str, Any] = {"job": None}
_FOLLOW_GUARD = threading.Lock()


def start_imagery_follow(emit: Callable[[Any], None],
                         busy: Callable[[], bool] = lambda: False,
                         port: Optional[int] = None,
                         lead_s: Optional[float] = None,
                         tiles: Optional[Sequence[Sequence[Any]]] = None,
                         index_path: Optional[str] = None,
                         reload: Optional[bool] = None) -> Dict[str, Any]:
    """The command: start following X-Plane's camera on ``port`` (default
    8086); ``tiles`` (``[build_dir, lat, lon]`` each) are rescanned into
    the index first; ``busy()`` is true while a build runs; ``reload``
    false: never ask X-Plane to reload its scenery after a spawn or jump
    (default: ask, through its Web API command)."""
    import O4_File_Names as FNAMES
    import O4_Imagery_Tier_Plan as PLAN
    import O4_XPlane_WebAPI as WEBAPI

    from .imagery_follow import FollowJob
    from .imagery_follow_land import TierLander
    with _FOLLOW_GUARD:
        job = _FOLLOW["job"]
        if job is not None and job.running:
            return {"status": "running"}
        base = WEBAPI.base_url(int(port or WEBAPI.DEFAULT_PORT))
        log = os.path.join(FNAMES.data_path("logs"), "imagery_on_demand.log")
        job = FollowJob(emit, reader=WEBAPI.PositionReader(base),
                        lander=TierLander(),
                        index_path=index_path, busy=busy,
                        lead_s=float(lead_s or PLAN.DEFAULT_LEAD_S),
                        log_path=log, rebuild_tiles=tiles or (),
                        reloader=None if reload is False else (
                            lambda: WEBAPI.reload_scenery(base)))
        _FOLLOW["job"] = job.start()
    return {"status": "started"}


def stop_imagery_follow() -> Dict[str, Any]:
    """The command: stop the job (fetches in flight finish first); its
    counts, or ``{"status": "idle"}`` when none runs."""
    with _FOLLOW_GUARD:
        job, _FOLLOW["job"] = _FOLLOW["job"], None
    if job is None:
        return {"status": "idle"}
    return {"status": "stopped", **job.stop()}


def start_imagery_source_status(emit: Callable[[Any], None],
                                codes: Optional[Sequence[str]] = None) -> Dict[str, Any]:
    """Start the check; ``emit`` receives each ImagerySourceStatus."""
    return SOURCES.check_status(
        lambda code, status, reason: emit(ImagerySourceStatus(
            code=code, status=status, reason=reason)), codes=codes)


def _tile_imagery(info):
    """``(build_dir, provider, zl)`` the built tile was made with, or None."""
    import O4_Tile_Info as TINFO
    imagery = TINFO.effective_imagery(info) if info is not None else None
    if imagery is None:
        return None
    return info.build_dir, imagery[0], imagery[1]


def freshness_for_info(info, force: bool = False, **options) -> Dict[str, Any]:
    """The imagery check of one scanned tile (``O4_Tile_Info.TileInfo``);
    the Qt pane's worker calls it with the tile it already has."""
    import O4_Imagery_Freshness as FRESH
    tile = _tile_imagery(info)
    if tile is None:
        return {"status": FRESH.UNKNOWN, "label": FRESH.LABELS[FRESH.UNKNOWN],
                "detail": "This tile is not built."}
    return FRESH.tile_freshness(info.lat, info.lon, *tile, force=bool(force), **options)


def _imagery_freshness(lat: int, lon: int, working_dir: str,
                      force: bool = False, **options) -> Dict[str, Any]:
    """The tile's imagery check, the tile found under ``working_dir``."""
    import O4_Tile_Info as TINFO
    return freshness_for_info(TINFO.tile_info(int(lat), int(lon), working_dir),
                              force=force, **options)


def discard_for_info(info) -> Dict[str, Any]:
    """"Update Imagery" for one scanned tile: what was removed."""
    import O4_Imagery_Freshness as FRESH
    tile = _tile_imagery(info)
    if tile is None:
        raise ValueError("imagery_freshness_discard: this tile is not built.")
    return FRESH.discard_tile_imagery(info.lat, info.lon, *tile)


def start_imagery_freshness(emit: Callable[[Any], None], lat: int, lon: int,
                            working_dir: str, force: bool = False,
                            request: Any = None) -> Dict[str, Any]:
    """The command: ``{"status": "started"}``; ImageryFreshnessReady follows."""
    def work():
        try:
            event = ImageryFreshnessReady(request=request, result=_imagery_freshness(
                lat, lon, working_dir, force=force))
        except Exception as error:      # the event carries it; the session lives on
            event = ImageryFreshnessReady(request=request, error=str(error))
        emit(event)

    threading.Thread(target=work, daemon=True, name="o4-imagery-freshness").start()
    return {"status": "started"}


def imagery_freshness_discard(lat: int, lon: int, working_dir: str) -> Dict[str, Any]:
    """"Update Imagery": what was removed (``jpegs``, ``textures``)."""
    import O4_Tile_Info as TINFO
    return discard_for_info(TINFO.tile_info(int(lat), int(lon), working_dir))


#: The on-demand commands that land textures: refused while a build runs
#: (a build may be converting the same tile's textures).
ONDEMAND_REFUSED_WHILE_BUILDING = {"imagery_pin": "pinning a tile",
                                   "imagery_ondemand_sweep":
                                   "holding the imagery storage limit",
                                   "imagery_ondemand_downgrade_all":
                                   "making imagery low-res again"}


def ondemand_handlers(building: Callable[[], bool]) -> Dict[str, Callable]:
    """The on-demand commands for the transport; ``building`` says a
    build runs."""
    from . import imagery_ondemand as ONDEMAND

    def guarded(name, function):
        def run(**kwargs):
            if building():
                raise ValueError("%s: not while a build runs (%s)."
                                 % (name, ONDEMAND_REFUSED_WHILE_BUILDING[name]))
            return function(**kwargs)
        return run
    return {
        "imagery_ondemand_scan": ONDEMAND.imagery_ondemand_scan,
        "imagery_pin": guarded("imagery_pin", ONDEMAND.imagery_pin),
        "imagery_ondemand_sweep": guarded("imagery_ondemand_sweep",
                                          ONDEMAND.imagery_ondemand_sweep),
        "imagery_ondemand_downgrade_all": guarded(
            "imagery_ondemand_downgrade_all",
            ONDEMAND.imagery_ondemand_downgrade_all),
    }
