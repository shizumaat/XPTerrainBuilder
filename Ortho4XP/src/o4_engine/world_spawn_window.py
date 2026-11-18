"""Pre-drape the spawn window of a built airport tile (#2142 part 1;
owner rulings 2026-11-17, Q1 and Q4).

X-Plane reads a tile's DSF once, when the tile enters its window; a tile
that entered as a 0-tri placeholder shows nothing until it leaves and
comes back or the scenery reloads.  So every tile X-Plane loads at a
spawn on a built tile's airports is draped BEFORE the pilot loads there:

* :func:`spawn_set` -- the tiles of every window the hysteresis allows at
  one point (``O4_World_Window.plausible_columns`` / ``plausible_rows``:
  12 tiles, up to 20 near a column or row line);
  :func:`_tile_spawn_set` -- the union over a tile's airports
  (``O4_Imagery_OnDemand_Cores.airport_points``), the tile itself left
  out, at most 24 others.
* :func:`_plan` -- of those, the pack's placeholders the World job may
  build, nearest an airport first, each with the airport it is nearest:
  a neighbour within :data:`CORE_REACH_DEG` of one is draped with that
  airport as its core (``world_job_run.drape_tile(core=...)``: the
  squares within its full-resolution ring fetched at full width), so the
  photo a parked pilot sees across the boundary is the airport's.
* :func:`_run` -- drapes the plan at :data:`QUICK_PX` (Q1: Quick for
  every speculative tile; the follow job sharpens it live), :data:`AT_ONCE`
  at a time, each taken through ``build_share.SHARE`` as
  :data:`OWNER` (lowest priority: track mode or a flight adopts it, never
  builds it twice), and swaps it in through the World job's publisher
  (``world_job_run._PackPublisher``: a placeholder X-Plane holds goes in,
  #2032; the follow job owns its rows from then on).  Nothing starts
  while the disk is under its free-space floor (``storage_floor``).
* :func:`start` -- after a ``full`` tile publishes (``world_publish``);
  :func:`backfill` -- at app start, the ``full`` tiles of the pack whose
  spawn set still holds a placeholder (Q4).  Both run on a background
  thread, one tile at a time; a tile already in work is not queued again.
* ONLY the airports the user cares about (owner 2026-11-17T23:45Z (a),
  RULINGS 2026-11-17v): a favourite tile's, or one flown from in the last
  30 days (``world_spawn_recent``); every other airport's start area is
  draped on demand when the aircraft is there (``world_job``).
* The work PAUSES while the app builds tiles or X-Plane runs (owner (b),
  ``world_yield``) and resumes after; its lines are the World job's
  (``O4_UI_Utils.set_thread_job``, #2148), never a tile's.

Every drape logs a line (``world_pack.log``: ``spawn_window``), and one
when the set is done.  No airport is named here: the points are the
tile's own airports.
"""
from __future__ import annotations

import math
import queue
import threading
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, Iterable, Optional

import O4_World_Pack as WP
import O4_World_Window as WINDOW

from . import world_job as JOB

__all__ = ["QUICK_PX", "AT_ONCE", "OWNER", "CORE_REACH_DEG", "spawn_set", "start", "backfill"]

#: The photo width of every spawn-set drape (owner Q1, 2026-11-17).
QUICK_PX = JOB.QUICK_PX
#: Drapes at once (spec §3.1: two beside the session's builds).
AT_ONCE = 2
#: The ``build_share`` owner name (not ranked: below track and flight).
OWNER = "spawn"
#: A neighbour this close to an airport (degrees, to its nearest edge)
#: gets the airport's core: the full-resolution ring
#: (``world_job_run.CORE_FULL_S``) of a ZL16-18 square is under this.
CORE_REACH_DEG = 0.15

Tile = tuple[int, int]
Point = tuple[str, float, float]


def spawn_set(lat: float, lon: float) -> set:
    """Every tile X-Plane may load at a flight load at ``(lat, lon)``."""
    return WINDOW.window_tiles(WINDOW.plausible_columns(lon),
                               WINDOW.plausible_rows(lat))


def _tile_spawn_set(tile: Tile, points: Iterable[Point]) -> set:
    """The union of :func:`spawn_set` over ``points`` ``(icao, lat,
    lon)``, ``tile`` itself left out."""
    out: set = set()
    for _icao, lat, lon in points:
        out |= spawn_set(float(lat), float(lon))
    out.discard(tuple(tile))
    return out


def _edge_deg(tile: Tile, lat: float, lon: float) -> float:
    """Degrees (longitude scaled by latitude) from a point to a tile."""
    dlat = max(tile[0] - lat, 0.0, lat - tile[0] - 1)
    dlon = max(tile[1] - lon, 0.0, lon - tile[1] - 1)
    return math.hypot(dlat, dlon * math.cos(math.radians(lat)))


def _plan(tile: Tile, points: list, kind_of: Callable[[Tile], Optional[str]]
         ) -> list:
    """``[(tile, core)]``: the placeholders of the spawn set, nearest an
    airport first; ``core`` ``(lat, lon)`` of that airport when within
    :data:`CORE_REACH_DEG`, else None."""
    out = []
    for other in _tile_spawn_set(tile, points):
        if kind_of(other) != "placeholder":
            continue
        near = min(points, key=lambda p: _edge_deg(other, p[1], p[2]))
        gap = _edge_deg(other, near[1], near[2])
        core = (float(near[1]), float(near[2])) if gap <= CORE_REACH_DEG else None
        out.append((gap, other, core))
    return [(other, core) for _gap, other, core in sorted(out)]


def _run(tile: Tile, points: list, *, kind_of, drape, publish, share=None,
        floor_ok: Callable[[], bool] = lambda: True,
        hold: Callable[[], object] = lambda: None,
        log: Callable[[dict], None] = lambda r: None) -> dict:
    """Drape ``tile``'s spawn set (see the module): ``drape(tile, core)``
    writes a staged drape and says whether it verifies, ``publish(tile)``
    swaps it in and returns its state; ``hold()`` returns when the work
    may go on (``world_yield.wait``).  Returns the counts."""
    name = WP.tile_name(*tile)
    todo = _plan(tile, points, kind_of)
    counts = {"spawn_window": name, "wanted": len(todo), "draped": 0,
              "failed": 0, "skipped": 0}

    def one(item) -> str:
        other, core = item
        hold()
        if not floor_ok():
            return "skipped"
        if share is not None and share.take(OWNER, other, "drape") != "start":
            return "skipped"
        ok = False
        try:
            ok = bool(drape(other, core))
            state = publish(other) if ok else "failed"
        except Exception as error:          # logged; the next start retries
            state = "failed"
            log({"spawn_window": name, "error": repr(error)[:300],
                 "tile": WP.tile_name(*other)})
        if share is not None:
            share.finish(other, ok)
            share.poll(OWNER)
        log({"spawn_window": name, "drape": WP.tile_name(*other),
             "core": core is not None, "state": state})
        return "draped" if state in ("swapped", "staged") else "failed"

    import O4_UI_Utils as UI
    with ThreadPoolExecutor(AT_ONCE, thread_name_prefix="o4-spawn",
                            initializer=UI.set_thread_job,
                            initargs=(UI.thread_job(),)) as pool:
        for verdict in pool.map(one, todo):
            counts[verdict] += 1
    log(dict(counts, done=True))
    return counts


_LOCK = threading.Lock()
_QUEUE: "queue.Queue[tuple]" = queue.Queue()
_IN_WORK: set = set()
_WORKER: list = []


def _work_one(tile: Tile, scenery_dir: str) -> None:
    import O4_Imagery_OnDemand_Cores as CORES

    from . import storage_floor as FLOOR
    from . import world_commands as WORLD
    from . import world_job_run as RUN
    from . import world_spawn_recent as RECENT
    from . import world_yield as YIELD
    from .build_share import SHARE
    YIELD.wait(WORLD.write_log)
    points = CORES.airport_points(tile[0], tile[1], scenery_dir=scenery_dir)
    if not points or not WORLD.managed(scenery_dir):
        return
    points = RECENT.allowed(tile, points, favourites=RECENT.favourite_tiles(),
                            recent=RECENT.places())
    if not points:                          # draped on demand (owner (a))
        return
    wanted = RUN._Wanted(scenery_dir)
    publisher = RUN._PackPublisher(scenery_dir, lambda la, lo: "")
    _run(tile, points, kind_of=wanted.kind,
        drape=lambda t, core: RUN.drape_tile(t, *RUN.photo_source(t),
                                             core=core, px=QUICK_PX),
        publish=lambda t: publisher.settle(t, "drape", True),
        share=SHARE, floor_ok=lambda: FLOOR.admits()[0],
        hold=lambda: YIELD.wait(WORLD.write_log), log=WORLD.write_log)


def _worker() -> None:
    import O4_UI_Utils as UI

    from . import world_commands as WORLD
    UI.set_thread_job(WORLD.JOB_NAME)       # #2148: no tile's lines
    while True:
        tile, scenery_dir = _QUEUE.get()
        try:
            _work_one(tile, scenery_dir)
        except Exception as error:          # logged; the next start retries
            from . import world_commands as WORLD
            WORLD.write_log({"spawn_window_error": repr(error)[:300],
                             "tile": WP.tile_name(*tile)})
        finally:
            with _LOCK:
                _IN_WORK.discard(tile)


def start(lat: int, lon: int, scenery_dir: str) -> bool:
    """Queue tile ``(lat, lon)``'s spawn set (see the module); False when
    it is already queued or in work."""
    tile = (int(lat), int(lon))
    with _LOCK:
        if tile in _IN_WORK:
            return False
        _IN_WORK.add(tile)
        if not _WORKER:
            _WORKER.append(threading.Thread(target=_worker, daemon=True,
                                            name="o4-spawn-window"))
            _WORKER[0].start()
    _QUEUE.put((tile, scenery_dir))
    return True


def backfill(scenery_dir: str, *, favourites: Optional[set] = None,
             recent: Optional[list] = None) -> list:
    """Queue every ``full`` tile of the pack holding a favourite or recent
    airport (``world_spawn_recent``; owner 2026-11-17T23:45Z (a), amending
    Q4) whose spawn set (its own 3 x 3 neighbourhood and one more column
    each side, read cheaply as the 5 x 5 around it) still holds a
    placeholder; the tiles queued.  Never raises."""
    from . import world_commands as WORLD
    from . import world_spawn_recent as RECENT
    queued = []
    try:
        if not WORLD.managed(scenery_dir):
            return queued
        favourites = (RECENT.favourite_tiles() if favourites is None
                      else favourites)
        recent = RECENT.places() if recent is None else recent
        cared = RECENT.tiles(favourites=favourites, recent=recent)
        kinds = WP.world_tiles(WORLD.pack_dir(scenery_dir))
        for tile, kind in sorted(kinds.items()):
            if kind != "full" or tuple(tile) not in cared:
                continue
            near = {(tile[0] + a, tile[1] + b)
                    for a in range(-2, 3) for b in range(-2, 3)}
            if any(kinds.get(t) == "placeholder" for t in near):
                if start(tile[0], tile[1], scenery_dir):
                    queued.append(WP.tile_name(*tile))
    except Exception as error:              # logged; the app starts
        WORLD.write_log({"spawn_window_backfill": repr(error)[:300]})
    if queued:
        WORLD.write_log({"spawn_window_backfill": queued})
    return queued
