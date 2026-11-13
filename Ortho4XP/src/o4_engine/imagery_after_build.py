"""After a build in on-demand mode: the tile in the index and its airport
cores sharp at once (#1992 local-imagery-cache spec §6.1; owner bug
2026-11-10: a freshly built airport stayed low-res).

A tile built with imagery on demand has low-res placeholders under every
texture name.  The follow job only sharpens squares near X-Plane's camera
and only knows the tiles its index holds, so a tile built after the job
started was in no index and its airport stayed coarse.  A tile's own build lands them as the end of its imagery step
(:func:`land_in_build`; owner 2026-11-13, RULINGS 13p: a tile is not
done until its airports have the imagery the settings asked for); a
World publish, an adopt and a flight's kept endpoints hand theirs over
on a worker (:func:`start`):

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
  starts while a build runs (``busy``) outside a build's own step.

Each landing is a line of ``logs/imagery_on_demand.log``, and each tile
of a batch a row of the Build view's Activity list
(``imagery_core_rows``, #2039), whoever started it.  No airport is
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

from . import imagery_core_rows as ROWS
from . import imagery_follow as FOLLOW

__all__ = ["CORE_WORKERS", "register_built", "core_wants", "fetch_cores",
           "sharpen", "core_seconds", "start", "watch", "land_in_build",
           "StepCores"]

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
                extra: Optional[Dict[tuple, Sequence[tuple]]] = None,
                rows_for: Callable = ROWS.CoreRows
                ) -> Dict[str, int]:
    """Land every core square of ``tiles`` (``(build_dir, lat, lon)``) at
    its tier.  ``lander(row, tier)`` returns the index facts (default
    ``TierLander``); none starts while ``busy()``; ``extra``: more
    airports per ``(lat, lon)`` (:func:`core_wants`); ``rows_for(totals)``
    reports the progress (default: the Build view's core rows; a build's
    own imagery step passes :class:`StepCores`).

    :returns: ``{"wanted", "landed", "failed", "network", "skipped"}``
    """
    if lander is None:
        from .imagery_follow_land import TierLander
        lander = TierLander()
    counts = {"wanted": 0, "landed": 0, "failed": 0, "network": 0,
              "skipped": 0}
    conn = INDEX.open_index(index)
    rows = None
    try:
        # finest tier first across every tile (the squares nearest the
        # airports), so a landing stopped for room keeps those
        wants = sorted((((int(lat), int(lon)), row, tier)
                        for (build_dir, lat, lon) in tiles
                        for row, tier in core_wants(
                           conn, build_dir, lat, lon,
                           (extra or {}).get((int(lat), int(lon)), ()))),
                       key=lambda want: -want[2])
        counts["wanted"] = len(wants)
        totals: Dict[tuple, int] = {}
        for tile, _row, _tier in wants:
            totals[tile] = totals.get(tile, 0) + 1
        rows = rows_for(totals)    # the Build view's rows (#2039)
        with _futures.ThreadPoolExecutor(
                max_workers=max(1, int(workers)),
                thread_name_prefix="o4-imagery-cores") as pool:
            futures = {}
            for tile, row, tier in wants:
                if busy() or ROWS.stopped(*tile):
                    counts["skipped"] += 1
                    rows.skipped(tile)
                    continue
                INDEX.set_state(conn, row["tile"], row["name"], "upgrading")
                futures[pool.submit(_land, lander, tile, dict(row), tier)] = (
                    tile, row, tier)
            for future in _futures.as_completed(futures):
                tile, row, tier = futures[future]
                outcome = _record(conn, row, tier, future, counts, log)
                if outcome == "skipped":
                    rows.skipped(tile)
                else:
                    rows.landed(tile, outcome == "landed")
    finally:
        conn.close()
        if rows is not None:
            rows.finish()
    FOLLOW.write_log(log, {"cores_done": len(tiles), **counts})
    return counts


class _Stopped(Exception):
    """The user stopped the square's tile (``imagery_core_rows.stop``)."""


def _land(lander: Callable, tile: tuple, row: dict, tier: int) -> dict:
    """``lander(row, tier)``, unless the tile was stopped meanwhile."""
    if ROWS.stopped(*tile):
        raise _Stopped()
    return lander(row, tier)


def _record(conn, row: dict, tier: int, future, counts: dict,
            log: Optional[str]) -> str:
    """The index row of one finished core landing, and its log line:
    ``landed``, ``failed`` or ``skipped`` (stopped before it started)."""
    square = f"{row['tile']}/{row['name']}"
    try:
        facts = future.result()
    except Exception as error:          # counted; the follow job retries it
        stopped = isinstance(error, _Stopped)
        counts["skipped" if stopped else "failed"] += 1
        INDEX.set_state(conn, row["tile"], row["name"],
                        "upgraded" if PLAN.tier_of_width(row["tier_px"]) > 0
                        else "low")
        if stopped:
            return "skipped"
        FOLLOW.write_log(log, {"core": square, "tier": tier,
                        "error": repr(error)[:200]})
        return "failed"
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
    return "landed"


def sharpen(tiles: Sequence[Sequence[Any]],
            busy: Callable[[], bool] = lambda: False,
            index: Optional[str] = None,
            lander: Optional[Callable] = None,
            log: Optional[str] = None,
            extra: Optional[Dict[tuple, Sequence[tuple]]] = None,
            rows_for: Callable = ROWS.CoreRows
            ) -> Optional[Dict[str, int]]:
    """:func:`register_built` then :func:`fetch_cores` for ``tiles``, one
    pass at a time (a build and a World publish may hand over the same
    tile); ``None`` when none was built on demand."""
    log = log or FOLLOW.log_path()
    with _GUARD:
        chosen = register_built(tiles, index)
        if not chosen:
            return None
        FOLLOW.write_log(log, {"registered": ",".join(
            FNAMES.short_latlon(la, lo) for _d, la, lo in chosen)})
        return fetch_cores(chosen, index=index, lander=lander, busy=busy,
                           log=log, extra=extra, rows_for=rows_for)


class StepCores:
    """A build's own core landing reported on its tile's row (#2052, owner
    2026-11-13 RULINGS 13p): ``progress(done, total)`` after each square,
    no core row of its own."""

    def __init__(self, progress: Callable[[int, int], None]):
        self._progress = progress
        self._done = 0
        self._total = 0

    def __call__(self, totals: Dict[tuple, int]) -> "StepCores":
        self._total = sum(int(n) for n in totals.values())
        self._report()
        return self

    def landed(self, _tile, _ok: bool) -> None:
        self._done += 1
        self._report()

    def skipped(self, _tile) -> None:
        self._done += 1
        self._report()

    def finish(self) -> None:
        pass

    def _report(self) -> None:
        try:
            self._progress(self._done, self._total)
        except Exception:               # a label is never worth the tile
            pass


def land_in_build(build_dir: str, lat: int, lon: int,
                  stopped: Callable[[], bool],
                  progress: Callable[[int, int], None] = lambda d, t: None,
                  index: Optional[str] = None,
                  lander: Optional[Callable] = None
                  ) -> Optional[Dict[str, int]]:
    """THE TILE'S IMAGERY STEP ENDS HERE (owner 2026-11-13, RULINGS 13p):
    a tile built on demand is not done until its airport cores are landed
    at the tier the user's settings ask for, so it flies with no X-Plane
    reload; imagery away from the airports stays on demand (the follow
    job).  Registers the tile and lands its cores now, in the build;
    ``stopped()`` (the build's Stop) leaves the squares not yet started.
    ``None`` for a tile not built on demand."""
    return sharpen([(build_dir, int(lat), int(lon))], busy=stopped,
                   index=index, lander=lander, rows_for=StepCores(progress))


def _work(tiles, busy, index, lander, log, extra=None) -> None:
    try:
        sharpen(tiles, busy=busy, index=index, lander=lander, log=log,
                extra=extra)
    except Exception as error:          # logged; the build itself is done
        FOLLOW.write_log(log, {"after_build_error": repr(error)[:300]})


def start(tiles: Sequence[Sequence[Any]],
          busy: Callable[[], bool] = lambda: False,
          index: Optional[str] = None,
          lander: Optional[Callable] = None,
          log: Optional[str] = None,
          extra: Optional[Dict[tuple, Sequence[tuple]]] = None
          ) -> Optional[threading.Thread]:
    """Register and sharpen the cores of ``tiles`` on a worker thread (the
    session calls it when a run ends; a flight for its kept departure and
    destination); ``None`` when there is nothing.  ``extra``: more
    airports per tile (:func:`core_wants`)."""
    tiles = [tuple(t) for t in tiles or ()]
    if not tiles:
        return None
    thread = threading.Thread(
        target=_work,
        args=(tiles, busy, index, lander, log or FOLLOW.log_path(), extra),
        daemon=True, name="o4-imagery-after-build")
    thread.start()
    return thread


def watch(session) -> None:
    """Send the background core rows (#2039) of ``session`` (an
    ``EngineSession``) to its event stream.  A build's own tiles are not
    handed over at the run's end any more: their cores land inside the
    tile's imagery step (:func:`land_in_build`, RULINGS 13p), so the rows
    are only for sharpening outside a build (a World publish, an adopt, a
    flight's kept endpoints)."""
    ROWS.set_sink(getattr(session, "_emit", None))
