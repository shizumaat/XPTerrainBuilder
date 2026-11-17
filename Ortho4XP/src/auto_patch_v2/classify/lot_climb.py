"""THE CLIMB ARM OF A LOT IS A ROAD (owner 2026-11-17T00:13Z, #2116 (c);
RULINGS 2026-11-16g (3): "a mapped road from a ramp road into a lot at
another level is minted as a road (10 % cap) through the lot and carries
the climb, the lot staying within its own cap").

A pack lot page is drawn flat by its author; where part of it runs UP the
ground toward a mapped road that stands at another level, that part is the
drive between the two levels, not parking.  Graded as a lot (5 %) the
whole page is held to one tilted plane: the climb lifts the flat part and
everything welded to it (MEASURED KDEN ``dsf:pol32``: the 3,700 m² south
part runs 9-13.5 % up the berm to the ridge-road junction 11 m away; at
5 % it stood 2-3.6 m under its ground and lifted the taxiway F zone it
welds to by up to 0.85 m).

THE WITNESS (both, never the DEM alone — RULINGS 2026-11-16s):

1. the MAP: a mapped road comes within ``[lot] climb_reach_m`` of the lot
   page without entering it (a road that ENTERS the page is the lot's own
   road, ``lot_roads``) — the level the climb runs to;
2. the GROUND: the connected part of the page whose ground runs steeper
   than the lot's own cap (``[lot] climb_min_grade``) over at least
   ``[lot] climb_min_area_m2``, rising at least ``[lot] climb_min_rise_m``
   toward that road (the road stands on its high side).

The arm is cut out of the page as its own source piece
(``<page>#climb<k>``, class ``strip``: a service road, 10 %), so the page's
remaining lot keeps its 5 % and the cells are cut at the arm's boundary
like any strip/lot mouth (``roles._cut_lines``).
"""
from __future__ import annotations

import typing as _t

import numpy as np
from shapely.geometry import LineString, Polygon, box
from shapely.ops import unary_union
from shapely.strtree import STRtree

from ..airport.dem import dem_z_many
from .evidence import polygon_parts

__all__ = ["climb_arms"]


def _steep(poly: Polygon, dem, grid: float, grade: float):
    """The part of ``poly`` whose ground runs steeper than ``grade``: the
    DEM sampled on a ``grid`` lattice over its bounds, the slope by central
    differences (a ``2 grid`` baseline), one square per steep sample."""
    x0, y0, x1, y1 = poly.bounds
    xs = np.arange(x0 - grid, x1 + 2 * grid, grid)
    ys = np.arange(y0 - grid, y1 + 2 * grid, grid)
    gx, gy = np.meshgrid(xs, ys)
    z = dem_z_many(dem, gx.ravel(), gy.ravel()).reshape(gx.shape)
    dzy, dzx = np.gradient(z, grid)
    slope = np.hypot(dzx, dzy)
    h = grid / 2.0
    cells = [box(x - h, y - h, x + h, y + h)
             for x, y, s in zip(gx.ravel(), gy.ravel(), slope.ravel(), strict=True)
             if np.isfinite(s) and s > grade]
    if not cells:
        return Polygon(), z, xs, ys
    return unary_union(cells).intersection(poly), z, xs, ys


def _dem_at(dem, pts: _t.Sequence[tuple[float, float]]) -> np.ndarray:
    a = np.asarray(pts, dtype=float).reshape(-1, 2)
    return dem_z_many(dem, a[:, 0], a[:, 1])


def climb_arms(poly: Polygon, roads: _t.Sequence[LineString],
               road_tree: STRtree | None, dem, lot) -> list[tuple[Polygon, dict]]:
    """The climb arms of the lot page ``poly`` (module doc): ``(arm,
    record)`` per arm, the record naming its area, mean grade, rise and
    the road gap (to the page).  ``lot`` is the ``[lot]`` rules table."""
    if dem is None or road_tree is None or poly.is_empty:
        return []
    reach = float(lot.climb_reach_m)
    near = [roads[int(j)] for j in road_tree.query(poly.buffer(reach), predicate="intersects")]
    near = [ln for ln in near if not ln.intersects(poly)
            and ln.distance(poly) <= reach]
    if not near:
        return []
    grid = float(lot.climb_grid_m)
    steep, _z, _xs, _ys = _steep(poly, dem, grid, float(lot.climb_min_grade))
    if steep.is_empty:
        return []
    # one sample's noise is no climb: open by a grid, close the gaps a grid leaves
    steep = steep.buffer(-grid).buffer(2.0 * grid).buffer(-grid).intersection(poly)
    out: list[tuple[Polygon, dict]] = []
    for part in polygon_parts(steep):
        if part.area < float(lot.climb_min_area_m2):
            continue
        # the part reaches toward the road: it comes within the reach of the
        # page's own point nearest that road
        from shapely.ops import nearest_points
        roads_here = [ln for ln in near
                      if part.distance(nearest_points(poly, ln)[0]) <= reach]
        if not roads_here:
            continue
        ring = list(part.exterior.coords)
        zr = _dem_at(dem, ring)
        lo, hi = float(np.min(zr)), float(np.max(zr))
        if hi - lo < float(lot.climb_min_rise_m):
            continue
        # the road stands on the arm's HIGH side: its nearest point to the
        # page is at least the arm's mid level
        best = None
        for ln in roads_here:
            p_road, _p = nearest_points(ln, poly)
            zr_ = float(_dem_at(dem, [(p_road.x, p_road.y)])[0])
            if best is None or zr_ > best[0]:
                best = (zr_, float(ln.distance(poly)))
        if best is None or best[0] < (lo + hi) / 2.0:
            continue
        out.append((part, {"area_m2": round(part.area, 1), "rise_m": round(hi - lo, 2),
                           "road_z": round(best[0], 2), "road_gap_m": round(best[1], 2)}))
    return out
