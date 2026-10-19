"""THE SLOPE PAD WITNESS (owner RULINGS 2026-10-19w, extends 2026-10-14n).

Owner, answering "RULINGS 14n: pad any building that floats more than
0.5 m?": "4. Yes".  A walled cluster under ``[placement]
cluster_pad_min_m2`` mints no pad (§16g (9)), and its bodies seat on
§16g (2)'s MEDIAN ground under their contacts — so on a slope its low side
floats by the median less the lowest ground under it.  This module is the
ONE reading of that float, asked by both halves that must agree on the pad
population (``classify/evidence._cluster_pads``, the mint, and
``constraints/cluster_pad.cluster_polys``, the census) and by the shelf
(``planar/apron_shelf``), which leaves a slope-padded cluster to its pad.

The float is read on the GROUND (the airport's DEM, the frame the pad mint
works in), at the closed outline's vertices and on a grid inside it: what
the building would stand on before any grading.  A pad on airside ground
is still never minted — ``geom.cluster_outlines`` rule 4 clips it first.
"""
from __future__ import annotations

import typing as _t

from shapely.geometry import Point, Polygon

__all__ = ["seat_float_m", "slope_witness"]

#: grid samples per side inside the outline (plus its vertices)
GRID_N = 8


def seat_float_m(outline: Polygon, dem_z: _t.Callable[[float, float], float]) -> float:
    """How far a building seated at the MEDIAN ground under ``outline``
    stands above the LOWEST ground under it (metres, >= 0)."""
    if outline is None or outline.is_empty:
        return 0.0
    polys = list(getattr(outline, "geoms", [outline]))
    pts = [c for p in polys for c in list(p.exterior.coords)[:-1]]
    x0, y0, x1, y1 = outline.bounds
    for i in range(GRID_N):
        for j in range(GRID_N):
            x = x0 + (i + 0.5) * (x1 - x0) / GRID_N
            y = y0 + (j + 0.5) * (y1 - y0) / GRID_N
            if outline.contains(Point(x, y)):
                pts.append((x, y))
    zs = sorted(float(z) for z in (dem_z(float(x), float(y)) for x, y in pts)
                if z is not None and z == z)
    if not zs:
        return 0.0
    n = len(zs)
    med = zs[n // 2] if n % 2 else 0.5 * (zs[n // 2 - 1] + zs[n // 2])
    return max(0.0, med - zs[0])


def slope_witness(airport: _t.Any, law: _t.Any):
    """``(outline -> float m, threshold m)`` for ``geom.cluster_outlines``'
    slope gate, or ``None`` where it is disarmed (``[placement]
    slope_pad_float_m`` 0) or the airport carries no DEM."""
    st = law.tables.structures.placement if law is not None else None
    t = float(getattr(st, "slope_pad_float_m", 0.0) or 0.0) if st is not None else 0.0
    dem = getattr(airport, "dem", None)
    if t <= 0.0 or dem is None or not hasattr(dem, "z"):
        return None
    return (lambda u: seat_float_m(u, dem.z)), t
