"""THE ROAD LEG OF A NECK BEYOND THE TAXI ROUTES (owner sim read
2026-11-19T22:50Z, ELLX fuel farm 49.634280, 6.221846: "no taxiway here,
and no connection wide enough for aircraft back to airside, and no taxi
route to it ... we should recognize [the road] on width alone").

§43 (1) kinds a NECK — the pavement joining two apron lobes — ``junction``
on the taxi family's evidence-free rung, WHOLE: a 671 m neck (ELLX
``pav47``) whose one end the taxi routes cross carried the junction role
round its 11 m loop road to the fuel farm, where §27 then read the farm's
lot (``dsf:pol51``) as running 78 m along AIRSIDE pavement and flipped it
to a junction too.  The apron the same ladder scores is bounded by the
ROUTE TERRITORY (RULINGS 2026-09-05x, ``roles._route_territory``); the
neck was not.

THE READING: of a neck piece the ladder kinded junction, the part inside
its taxi routes' territory stays the junction; each remainder part — no
taxi centreline within ``junction.route_territory_half_width_m`` of it —
that is ROAD-WIDE THROUGHOUT (``open_default.narrow_road``, the one
width-alone road reading: no point reaches ``corridor.max_width_m`` of
local width, mean width at most ``service.free_max_width_m``) and holds
no 1300 stand is a ``service_road``.  Every other remainder part stays
with the junction.  No new number.
"""
from __future__ import annotations

import typing as _t

import shapely
from shapely.geometry import Polygon
from shapely.ops import unary_union

from .evidence import polygon_parts
from .open_default import narrow_road
from .rules import Rules

__all__ = ["road_beyond_routes"]


def road_beyond_routes(face: Polygon, territory, rules: Rules,
                       holds_stand: _t.Callable[[Polygon], bool]
                       ) -> tuple[Polygon | None, list[tuple[Polygon, float]]]:
    """``(junction_rest, [(road_part, mean_width_m), ...])`` for a neck
    piece ``face`` whose taxi routes' territory is ``territory`` (module
    docstring); ``(None, [])`` when no remainder part is a road."""
    if territory is None or territory.is_empty:
        return None, []
    grid = rules.cells.snap_grid_m
    roads: list[tuple[Polygon, float]] = []
    rest = shapely.set_precision(face.difference(territory), grid)
    for part in polygon_parts(rest):
        if part.area < rules.cells.min_area_m2 or holds_stand(part):
            continue
        w = narrow_road(part, rules)
        if w is not None:
            roads.append((part, w))
    if not roads:
        return None, []
    keep = shapely.set_precision(
        face.difference(unary_union([p for p, _w in roads])), grid)
    return keep, roads
