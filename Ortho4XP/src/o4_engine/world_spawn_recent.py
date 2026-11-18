"""Which airports' spawn windows the World job pre-drapes (owner
2026-11-17T23:45Z (a), RULINGS 2026-11-17v; amends #2142's Q4 backfill,
which queued every built airport: 702 spawn windows, ~6,000 placeholders
pulled while the owner built six unrelated tiles).

Only the airports the user CARES ABOUT now are pre-draped
(``world_spawn_window``); every other airport's start area is draped on
demand when the aircraft is there (the World job's spawn tile and held
placeholders, ``world_job``):

* FAVOURITE -- every airport of a tile the user starred (``pinned`` in the
  on-demand index, #2033: ``storage_packages._favorites``);
* RECENT -- an airport within :data:`REACH_DEG` of a place the aircraft
  stood on the ground in the last :data:`RECENT_DAYS` days (:func:`note`,
  written by the World job's runner: a spawn, a taxi, a landing), or the
  origin of a flight record (``Flights/``, ``flight_record``) created or
  departed in that time, and its destination once it arrived (matched by
  ident, else by place).

:func:`allowed` filters one tile's airport points; :func:`tiles` names
the tiles that may hold a favourite or recent airport (the backfill's
candidates).  No airport is named here.
"""
from __future__ import annotations

import contextlib
import json
import math
import os
import threading
import time
from datetime import datetime, timezone
from typing import Iterable, Optional

__all__ = ["RECENT_DAYS", "REACH_DEG", "HISTORY_NAME", "ENV_PATH", "note",
           "places",
           "favourite_tiles", "allowed", "tiles"]

#: "Recent" (owner (a): proposed 30 days).
RECENT_DAYS = 30
#: An airport this close to a recent place (degrees, longitude scaled) is
#: the one flown from: a large airport's far stands are under ~5 km from
#: its reference point.
REACH_DEG = 0.05
#: The ground places (``<data folder>/world_spawns.json``; the file
#: ``$O4_WORLD_SPAWNS`` names instead, read at call time: the tests').
HISTORY_NAME = "world_spawns.json"
ENV_PATH = "O4_WORLD_SPAWNS"
#: Kept places, newest first; one per 0.01 degree cell (:data:`_ROUND`).
_KEEP = 200
_ROUND = 2
#: A place already written this recently is not written again.
_WRITE_EVERY_S = 600.0

_LOCK = threading.Lock()
_WRITTEN: dict = {}              # (path, cell) -> monotonic time written

Point = tuple  # (icao, lat, lon)


def _history_path(path: Optional[str] = None) -> str:
    if path:
        return path
    if os.environ.get(ENV_PATH):
        return os.environ[ENV_PATH]
    import O4_File_Names as FNAMES
    return FNAMES.data_path(HISTORY_NAME)


def _read(path: str) -> list:
    try:
        with open(path, encoding="utf-8") as handle:
            rows = json.load(handle)
    except (OSError, ValueError):
        return []
    if not isinstance(rows, list):
        return []
    return [r for r in rows if isinstance(r, dict)]


def note(lat: float, lon: float, now: Optional[float] = None,
         path: Optional[str] = None) -> bool:
    """The aircraft stands on the ground at ``(lat, lon)`` (wall-clock
    ``now``): kept as a recent place.  True when written; never raises."""
    now = time.time() if now is None else float(now)
    cell = (round(float(lat), _ROUND), round(float(lon), _ROUND))
    clock = time.monotonic()
    with _LOCK:
        if clock - _WRITTEN.get((path, cell), -math.inf) < _WRITE_EVERY_S:
            return False
        _WRITTEN[(path, cell)] = clock
        target = _history_path(path)
        rows = [r for r in _read(target)
                if (r.get("lat"), r.get("lon")) != cell
                and now - float(r.get("at") or 0) <= 2 * RECENT_DAYS * 86400]
        rows.insert(0, {"lat": cell[0], "lon": cell[1], "at": round(now)})
        try:
            from .patch_file import write_atomic
            os.makedirs(os.path.dirname(target) or ".", exist_ok=True)
            write_atomic(target, json.dumps(rows[:_KEEP]))
        except OSError:
            return False
    return True


def _stamp(text) -> float:
    with contextlib.suppress(TypeError, ValueError):
        return datetime.strptime(str(text), "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=timezone.utc).timestamp()
    return 0.0


def _flight_places(folder: str, since: float) -> list:
    from . import flight_record as RECORD
    out = []
    for record in RECORD.list_flights(folder):
        if max(_stamp(record.created_at), _stamp(record.departed_at)) < since:
            continue
        ends = [record.origin]
        if record.arrived_at:
            ends.append(record.destination)
        for end in ends:
            if isinstance(end, dict) and end.get("lat") is not None:
                out.append((str(end.get("ident") or ""), float(end["lat"]),
                            float(end["lon"])))
    return out


def places(now: Optional[float] = None, *, history: Optional[str] = None,
           flights: Optional[str] = None) -> list:
    """``[(ident, lat, lon)]`` of the recent places (see the module):
    ground places (ident "") and flight ends."""
    now = time.time() if now is None else float(now)
    since = now - RECENT_DAYS * 86400
    out = [("", float(r["lat"]), float(r["lon"]))
           for r in _read(_history_path(history))
           if float(r.get("at") or 0) >= since and r.get("lat") is not None]
    with contextlib.suppress(Exception):    # an unreadable folder: none
        if flights is None:
            from . import flight_record as RECORD
            flights = RECORD.flights_dir()
        out += _flight_places(flights, since)
    return out


def favourite_tiles() -> set:
    """``{(lat, lon)}`` of the starred tiles (#2033); empty when the
    on-demand index cannot be read."""
    import O4_File_Names as FNAMES

    from .storage_packages import _favorites
    out = set()
    with contextlib.suppress(Exception):
        for key in _favorites():
            pair = FNAMES.parse_tile_key(key)
            if pair is not None:
                out.add(tuple(pair))
    return out


def _near(point: Point, place: tuple) -> bool:
    ident, lat, lon = place
    if ident and ident.upper() == str(point[0]).upper():
        return True
    dlon = (float(point[2]) - lon) * math.cos(math.radians(lat))
    return math.hypot(float(point[1]) - lat, dlon) <= REACH_DEG


def allowed(tile, points: Iterable[Point], *, favourites: set,
            recent: list) -> list:
    """The points of ``tile`` whose spawn window is pre-draped: all of a
    favourite tile's, else those near a recent place."""
    points = list(points)
    if tuple(tile) in favourites:
        return points
    return [p for p in points if any(_near(p, place) for place in recent)]


def tiles(*, favourites: set, recent: list) -> set:
    """``{(lat, lon)}`` that may hold a favourite or recent airport: the
    favourites and every tile a recent place reaches."""
    out = set(favourites)
    for _ident, lat, lon in recent:
        for dlat in (-REACH_DEG, 0.0, REACH_DEG):
            for dlon in (-REACH_DEG, 0.0, REACH_DEG):
                out.add((math.floor(lat + dlat), math.floor(lon + dlon)))
    return out
