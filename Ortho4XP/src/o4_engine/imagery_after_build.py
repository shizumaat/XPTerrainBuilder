"""After a build in on-demand mode: the tile in the index and its airport
cores sharp at once (#1992 local-imagery-cache spec §6.1; owner bug
2026-11-10: a freshly built airport stayed low-res).

A tile built with imagery on demand has low-res placeholders under every
texture name.  The follow job only sharpens squares near X-Plane's camera
and only knows the tiles its index holds, so a tile built after the job
started was in no index and its airport stayed coarse.  When a run ends
the session's watcher (:func:`watch`, subscribed by both apps) hands
every tile the run built here (:func:`start`):

* :func:`register_built` -- each tile whose imagery record says on demand
  (or pinned) gets its index rows and core marks
  (``imagery_ondemand.register_tiles``); a running follow job reads them
  at its next row reload;
* :func:`fetch_cores` -- every core square below the tier a camera at its
  airport wants, and every cover texture (finer than the tile's own zoom
  level: the airport cover and approach corridors) below full
  (``O4_Imagery_OnDemand_Cores.core_tier``), is landed at
  that tier by the follow job's own lander
  (``imagery_follow_land.TierLander``: the build's cached source JPEGs
  first, a download only when they are gone), without X-Plane.  No fetch
  starts while a build runs (``busy``); the next run's end resumes.

Each landing is a line of ``logs/imagery_on_demand.log``.  No airport is
named here: the cores are the airports the tile's patches graded.
"""
from __future__ import annotations

import concurrent.futures as _futures
import math
import os
import threading
import time
from typing import Any, Callable, Dict, Optional, Sequence

import O4_File_Names as FNAMES
import O4_Imagery_OnDemand_Cores as CORES
import O4_Imagery_OnDemand_Index as INDEX
import O4_Imagery_Tier_Plan as PLAN

from . import imagery_follow as FOLLOW

__all__ = ["CORE_WORKERS", "register_built", "core_wants", "fetch_cores",
           "sharpen", "core_seconds", "start", "watch"]

#: Core landings at once (each is a JPEG read or download and a convert).
CORE_WORKERS = 4

#: Bytes per second a core landing is reckoned at, ``(fast, slow)``: a
#: conservative CONSTANT (the on-demand log records no bytes per second
#: to measure one from), for a flight's countdown only.
CORE_RATE_BPS = (8_000_000.0, 2_000_000.0)

_GUARD = threading.Lock()


def core_seconds(airports: int = 1) -> "tuple[float, float]":
    """``(low, high)`` seconds to land the cores of ``airports`` airports:
    each core tier's ring (``O4_Imagery_Tier_Plan.CROSSING_S``, in square
    sides; about pi r^2 squares) at that tier's bytes
    (``TIER_BYTES``), ~183 MB an airport, at :data:`CORE_RATE_BPS`.
    Cover textures finer than the tile's zoom are not counted."""
    total = inner = 0.0
    for tier in range(len(PLAN.TIER_BYTES) - 1, 0, -1):    # full .. 1024
        area = math.pi * PLAN.CROSSING_S[tier] ** 2
        total += (area - inner) * PLAN.TIER_BYTES[tier]
        inner = area
    total *= max(0, int(airports))
    fast, slow = CORE_RATE_BPS
    return total / fast, total / slow


def _on_demand(build_dir: str, lat: int, lon: int) -> bool:
    import O4_Tile_Info as TINFO
    try:
        record = TINFO.read_imagery_record(build_dir, int(lat), int(lon))
    except Exception:                   # no record: not an on-demand build
        return False
    return bool(record.get("on_demand") or record.get("pinned"))


def register_built(tiles: Sequence[Sequence[Any]],
                   index: Optional[str] = None) -> list:
    """The ``(build_dir, lat, lon)`` of ``tiles`` built on demand, their
    index rows written; the others are left alone."""
    from . import imagery_ondemand as ONDEMAND
    chosen = [(str(d), int(la), int(lo)) for d, la, lo in tiles
              if os.path.isdir(str(d)) and _on_demand(d, la, lo)]
    if chosen:
        ONDEMAND.register_tiles(chosen, index)
    return chosen


def core_wants(conn, build_dir: str, lat: int, lon: int,
               extra: Sequence[tuple] = ()) -> "list[tuple[dict, int]]":
    """``(row, tier)`` of every core square of tile ``(lat, lon)`` below
    the tier its airport wants (a cover texture: full), finest first.
    ``extra``: more ``(icao, lat, lon)`` airports (a flight's departure
    when its tile graded none), each one the graded and custom points do
    not already name."""
    points = CORES.airport_points(lat, lon)
    named = {p[0] for p in points}
    points += [tuple(p) for p in extra if p[0] not in named]
    base_zl = CORES.base_zoom(build_dir, lat, lon)
    wants = []
    for row in INDEX.rows(conn, tile=FNAMES.short_latlon(lat, lon)):
        tier = CORES.core_tier(row, points, base_zl)
        if (tier is not None and row.get("state") != "failed"
                and PLAN.tier_of_width(row["tier_px"]) < tier):
            wants.append((row, tier))
    return sorted(wants, key=lambda want: -want[1])


def fetch_cores(tiles: Sequence[Sequence[Any]], index: Optional[str] = None,
                lander: Optional[Callable] = None,
                busy: Callable[[], bool] = lambda: False,
                log: Optional[str] = None,
                workers: int = CORE_WORKERS,
                extra: Optional[Dict[tuple, Sequence[tuple]]] = None
                ) -> Dict[str, int]:
    """Land every core square of ``tiles`` (``(build_dir, lat, lon)``) at
    its tier.  ``lander(row, tier)`` returns the index facts (default
    ``TierLander``); none starts while ``busy()``; ``extra``: more
    airports per ``(lat, lon)`` (:func:`core_wants`).

    :returns: ``{"wanted", "landed", "failed", "network", "skipped"}``
    """
    if lander is None:
        from .imagery_follow_land import TierLander
        lander = TierLander()
    counts = {"wanted": 0, "landed": 0, "failed": 0, "network": 0,
              "skipped": 0}
    conn = INDEX.open_index(index)
    try:
        # finest tier first across every tile (the squares nearest the
        # airports), so a landing stopped for room keeps those
        wants = sorted((w for (build_dir, lat, lon) in tiles
                        for w in core_wants(
                           conn, build_dir, lat, lon,
                           (extra or {}).get((int(lat), int(lon)), ()))),
                       key=lambda want: -want[1])
        counts["wanted"] = len(wants)
        with _futures.ThreadPoolExecutor(
                max_workers=max(1, int(workers)),
                thread_name_prefix="o4-imagery-cores") as pool:
            futures = {}
            for row, tier in wants:
                if busy():
                    counts["skipped"] += 1
                    continue
                INDEX.set_state(conn, row["tile"], row["name"], "upgrading")
                futures[pool.submit(lander, dict(row), tier)] = (row, tier)
            for future in _futures.as_completed(futures):
                row, tier = futures[future]
                _record(conn, row, tier, future, counts, log)
    finally:
        conn.close()
    FOLLOW.write_log(log, {"cores_done": len(tiles), **counts})
    return counts


def _record(conn, row: dict, tier: int, future, counts: dict,
            log: Optional[str]) -> None:
    """The index row of one finished core landing, and its log line."""
    square = f"{row['tile']}/{row['name']}"
    try:
        facts = future.result()
    except Exception as error:          # counted; the follow job retries it
        counts["failed"] += 1
        INDEX.set_state(conn, row["tile"], row["name"],
                        "upgraded" if PLAN.tier_of_width(row["tier_px"]) > 0
                        else "low")
        FOLLOW.write_log(log, {"core": square, "tier": tier,
                        "error": repr(error)[:200]})
        return
    INDEX.set_state(conn, row["tile"], row["name"], "upgraded",
                    tier_px=facts["tier_px"],
                    full_bytes=facts.get("full_bytes", 0),
                    jpeg_path=facts.get("jpeg_path"),
                    dds_cache_key=facts.get("dds_cache_key"),
                    fetched_at=time.time())
    counts["landed"] += 1
    counts["network"] += int(bool(facts.get("network", True)))
    FOLLOW.write_log(log, {"core": square, "tier": tier,
                    "network": bool(facts.get("network", True))})


def sharpen(tiles: Sequence[Sequence[Any]],
            busy: Callable[[], bool] = lambda: False,
            index: Optional[str] = None,
            lander: Optional[Callable] = None,
            log: Optional[str] = None,
            extra: Optional[Dict[tuple, Sequence[tuple]]] = None
            ) -> Optional[Dict[str, int]]:
    """:func:`register_built` then :func:`fetch_cores` for ``tiles``, one
    pass at a time (the run's end and a World publish may hand over the
    same tile); ``None`` when none was built on demand."""
    log = log or FOLLOW.log_path()
    with _GUARD:
        chosen = register_built(tiles, index)
        if not chosen:
            return None
        FOLLOW.write_log(log, {"registered": ",".join(
            FNAMES.short_latlon(la, lo) for _d, la, lo in chosen)})
        return fetch_cores(chosen, index=index, lander=lander, busy=busy,
                           log=log, extra=extra)


def _work(tiles, busy, index, lander, log) -> None:
    try:
        sharpen(tiles, busy=busy, index=index, lander=lander, log=log)
    except Exception as error:          # logged; the build itself is done
        FOLLOW.write_log(log, {"after_build_error": repr(error)[:300]})


def start(tiles: Sequence[Sequence[Any]],
          busy: Callable[[], bool] = lambda: False,
          index: Optional[str] = None,
          lander: Optional[Callable] = None,
          log: Optional[str] = None) -> Optional[threading.Thread]:
    """Register and sharpen the cores of ``tiles`` on a worker thread (the
    session calls it when a run ends); ``None`` when there is nothing."""
    tiles = [tuple(t) for t in tiles or ()]
    if not tiles:
        return None
    thread = threading.Thread(
        target=_work, args=(tiles, busy, index, lander, log or FOLLOW.log_path()),
        daemon=True, name="o4-imagery-after-build")
    thread.start()
    return thread


def watch(session) -> None:
    """Subscribe to ``session`` (an ``EngineSession``): each tile its run
    built (``BuildDone`` ok) goes to :func:`start` when the run ends
    (``RunDone``), in its build folder (``session.tile_build_dir``).  A
    per-step worker child's runs are its parent's to hand over."""
    built: list = []
    guard = threading.Lock()

    def on_event(event) -> None:
        name = type(event).__name__
        if name == "BuildDone" and event.ok:
            with guard:
                built.append((int(event.lat), int(event.lon)))
        elif name == "RunDone":
            with guard:
                tiles, built[:] = list(built), []
            if tiles and not getattr(session, "_stepwise_run", False):
                # The follow job holds only the tiles a build has queued
                # or is building (World spec §8.7).
                start([(session.tile_build_dir(*t), *t) for t in tiles],
                      busy=getattr(session, "building_tiles",
                                   lambda: bool(session._building)))
    session.subscribe(on_event)
