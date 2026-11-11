"""The Fly map's layers as data (spec flight-manager-and-world-20261110
§4.3 (4, 6), §14; #2001; lane U2): the aircraft's track and the route's
corridor tiles by legend.  Pure: no Qt, no I/O.

The Qt layer (``O4_Qt_Fly_Layer``) draws it; the Mac app's
``Sources/SceneryKit/FlyLayers.swift`` holds the same rules, and
``tests/test_fly_pane.py`` holds the two equal through
``tests/fixtures/fly_pane_cases.json``.
"""

from __future__ import annotations

import math
from typing import Dict, List, Optional, Sequence, Tuple

import O4_Flight_Plan as FP
import O4_Fly_Text as TEXT

__all__ = ["TRACK_MAX_POINTS", "TRACK_MIN_STEP_M", "TRACK_BREAK_KM",
           "AircraftTrack", "corridor_cells", "map_jobs"]

#: One hour at one position a second.
TRACK_MAX_POINTS = 3600
#: A position closer than this to the last one is not added (parked).
TRACK_MIN_STEP_M = 20.0
#: A step longer than this starts a new piece (a jump or a flight load).
TRACK_BREAK_KM = 30.0

LatLon = Tuple[float, float]


def _step_m(a: LatLon, b: LatLon) -> float:
    mid = math.radians((a[0] + b[0]) / 2.0)
    dlon = (b[1] - a[1] + 540.0) % 360.0 - 180.0
    return math.hypot(dlon * 111_320.0 * math.cos(mid),
                      (b[0] - a[0]) * 111_320.0)


class AircraftTrack:
    """The aircraft's track as polylines: :meth:`add` each
    ``AircraftPosition``; :meth:`parts` is what the map draws.  A jump
    (more than :data:`TRACK_BREAK_KM` in one step) or the antimeridian
    starts a new piece; the oldest points go past
    :data:`TRACK_MAX_POINTS`."""

    def __init__(self) -> None:
        self._parts: List[List[LatLon]] = []
        self.last: Optional[Tuple[float, float, float]] = None   # lat, lon, track

    def add(self, lat: float, lon: float, track_deg: float = 0.0) -> bool:
        """One position; True when the drawing changed."""
        point = (float(lat), float(lon))
        self.last = (point[0], point[1], float(track_deg))
        if self._parts and self._parts[-1]:
            prev = self._parts[-1][-1]
            step = _step_m(prev, point)
            if step < TRACK_MIN_STEP_M:
                return False
            if step > TRACK_BREAK_KM * 1000.0 or abs(point[1] - prev[1]) > 180.0:
                self._parts.append([])
        else:
            self._parts.append([])
        self._parts[-1].append(point)
        self._trim()
        return True

    def _trim(self) -> None:
        extra = sum(len(p) for p in self._parts) - TRACK_MAX_POINTS
        while extra > 0 and self._parts:
            head = self._parts[0]
            cut = min(extra, len(head))
            del head[:cut]
            extra -= cut
            if not head:
                self._parts.pop(0)

    def parts(self) -> List[List[LatLon]]:
        return [list(p) for p in self._parts if len(p) > 1]

    def clear(self) -> None:
        self._parts = []
        self.last = None


def map_jobs(flight: Sequence = (), planned: bool = False,
             ahead: Sequence = ()) -> Sequence:
    """The jobs the Fly map draws: the flight's once it reports any; with
    no flight and no plan, build-ahead's tiles (``WorldStatus.jobs``, the
    same rows) so free flight shows its drapes; else none (the plan's
    corridor).  Swift: ``FlyLayers.mapJobs``."""
    if flight:
        return flight
    return () if planned else (ahead or ())


def corridor_cells(plan: Optional[Dict], corridor_km: float,
                   jobs: Sequence = ()) -> List[Tuple[int, int, str]]:
    """The corridor's tiles with their legend key, sorted: the tiles of
    ``FlightStatus.jobs`` (rows ``[tile, role, kind, state, ...]``) by
    their job, and before the engine reports any, the tiles the route
    crosses plus those within ``corridor_km`` (``route_tiles``) as
    X-Plane's own scenery."""
    cells: Dict[Tuple[int, int], str] = {}
    if jobs:
        for row in jobs:
            tile, kind, state = row[0], row[2], row[3]
            cells[(int(tile[0]), int(tile[1]))] = TEXT.legend_key(kind, state)
    elif plan and plan.get("waypoints"):
        points = [(w["lat"], w["lon"]) for w in plan["waypoints"]]
        for tile in FP.route_tiles(points, float(corridor_km)):
            cells[(int(tile[0]), int(tile[1]))] = "own"
    return sorted((lat, lon, key) for (lat, lon), key in cells.items())
