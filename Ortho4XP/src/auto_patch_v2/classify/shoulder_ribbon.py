"""THE SHOULDER IS A RIBBON AT ITS OWN DEPTH (§40 (1)/(5); issue #1100).

§40 admits a pavement cell as the runway's SHOULDER when it runs along the
runway ring (shared edge and MEAN depth, ``roles._runway_shoulder``) and
§40 (5) keeps only its part inside the runway's graded strip.  A cell that
is a shoulder ribbon AND carries the taxiways leaving the runway is cut by
neither: LPHRx paints its runway, its shoulders, both apron taxiways and
the apron in ONE draped object (``lphr_solowiz_fs9-lphr_asphalt.obj``), so
the north shoulder cell (857 m along 10/28, mean depth 13.9 m) carries the
two taxiways up to the apron 55 m off the runway edge — inside the 75 m
strip, so §40 (5) left both taxiways ``runway``.

The ribbon's own depth is read off the cell: the MEDIAN, over stations
along the runway slab's two long sides, of how far the cell runs out
perpendicular to the edge.  A taxiway leaving the ribbon occupies a few
stations, so the median is the ribbon's; the part of the cell further out
than ``corridor.runway_shoulder_ribbon_factor`` x that depth is not the
shoulder and goes back on the §40 (5) worklist as its remainder, scored on
its own evidence.
"""
from __future__ import annotations

import math
import statistics as _st

from shapely.geometry import LineString, Point, Polygon

__all__ = ["ribbon_depth_m", "ribbon_half_width_m"]

#: the station spacing along the slab's long sides (m)
_STEP_M = 5.0


def _long_sides(slab: Polygon) -> list[tuple[tuple[float, float], tuple[float, float]]]:
    """The slab rectangle's two longest sides, each ``(a, b)``."""
    pts = list(slab.exterior.coords)[:-1]
    sides = [(pts[i], pts[(i + 1) % len(pts)]) for i in range(len(pts))]
    sides.sort(key=lambda s: -math.dist(s[0], s[1]))
    return sides[:2]


def _station_depth(face: Polygon, px: float, py: float, nx: float, ny: float,
                   tol: float, reach: float) -> float | None:
    """How far ``face`` runs out from ``(px, py)`` along the outward normal,
    or ``None`` where it does not touch the station within ``tol``."""
    ray = LineString([(px - nx * tol, py - ny * tol),
                      (px + nx * reach, py + ny * reach)])
    got = face.intersection(ray)
    if got.is_empty:
        return None
    p0 = Point(px, py)
    for g in getattr(got, "geoms", (got,)):
        if g.geom_type == "LineString" and g.distance(p0) <= tol:
            far = max(math.dist((px, py), c) for c in g.coords)
            return far if far > tol else None
    return None


def ribbon_depth_m(face: Polygon, slab: Polygon, tol: float,
                   reach: float) -> float | None:
    """The MEDIAN depth the cell ``face`` runs out from the runway slab's
    long sides (module docstring), over the stations where it touches the
    side within ``tol``; rays stop at ``reach``.  ``None`` where no station
    touches."""
    centre = slab.centroid
    depths: list[float] = []
    for a, b in _long_sides(slab):
        L = math.dist(a, b)
        if L <= 0.0:
            continue
        ux, uy = (b[0] - a[0]) / L, (b[1] - a[1]) / L
        nx, ny = -uy, ux
        if ((a[0] + b[0]) / 2 - centre.x) * nx + ((a[1] + b[1]) / 2 - centre.y) * ny < 0.0:
            nx, ny = -nx, -ny                  # outward, away from the slab
        n = max(1, int(L // _STEP_M))
        for i in range(n):
            s = (i + 0.5) * L / n
            d = _station_depth(face, a[0] + ux * s, a[1] + uy * s, nx, ny, tol, reach)
            if d is not None:
                depths.append(d)
    return _st.median(depths) if depths else None


def ribbon_half_width_m(face: Polygon, rw, slab: Polygon, tol: float,
                        reach: float, factor: float) -> float | None:
    """The half width about the runway centreline beyond which the cell is
    not the shoulder ribbon: the runway's own half width plus ``factor`` x
    the ribbon depth; ``None`` where ``factor`` disarms the cut or the cell
    has no ribbon station."""
    if factor <= 0.0:
        return None
    d = ribbon_depth_m(face, slab, tol, reach)
    if d is None:
        return None
    return 0.5 * float(rw.width_m) + factor * d
