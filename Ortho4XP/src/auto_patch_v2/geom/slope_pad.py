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

__all__ = ["seat_float_m", "slope_witness", "SlopeWitness"]

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


class SlopeWitness:
    """The slope gate ``geom.cluster_outlines`` asks (owner RULINGS
    2026-10-19w; 2026-10-19ak for a building on airside pavement).

    ``threshold`` is ``[placement] slope_pad_float_m``.  A cluster is read
    on its own closed outline, UNLESS it is a piece of a MULTI-FILE
    BUILDING: clusters that hold one resource file and whose outlines come
    within ``[placement] piece_reach_m`` chain into one building (19u's
    rule, at the cluster), and where that building holds a walled cluster,
    spans under ``connector_span_m`` and floats more than the threshold
    over the ground under its WHOLE footprint, its pad is that footprint:
    the union of its clusters' outlines, minted ONCE (:meth:`group_of`).
    MEASURED (KASE tower, 39.22574, -106.86832): its walled cluster floats
    0.40 m on its own 152 m2 outline, the tower's four clusters 1.13 m
    over 1,757 m2, and the shared datum left its low end 0.63 m up."""

    def __init__(self, dem_z, threshold: float,
                 groups: _t.Mapping[str, tuple[str, Polygon]] | None = None):
        self.dem_z = dem_z
        self.threshold = float(threshold)
        self._groups = dict(groups or {})

    def floats(self, u: Polygon) -> bool:
        return seat_float_m(u, self.dem_z) > self.threshold

    def group_of(self, cid: str) -> "tuple[str, Polygon] | None":
        """``(the group's representative cluster id, its footprint union)``
        for a cluster of a FLOATING multi-file building, else ``None``."""
        return self._groups.get(str(cid))

    def __getitem__(self, k):          # the ``(fn, threshold)`` spelling
        return ((lambda u: seat_float_m(u, self.dem_z)), self.threshold)[k]


_MEMO: list[tuple[int, _t.Any, SlopeWitness]] = []


def _groups(airport: _t.Any, st: _t.Any, dem_z, threshold: float
            ) -> dict[str, tuple[str, Polygon]]:
    from shapely.ops import unary_union
    from shapely.strtree import STRtree
    reach = float(getattr(st, "piece_reach_m", 0.0) or 0.0)
    span_max = float(getattr(st, "connector_span_m", 0.0) or 0.0)
    to_xy = airport.frame.entry()
    cl, polys = [], []
    for c in getattr(airport, "clusters", None) or ():
        ps = []
        for r in getattr(c, "rings", ()) or ():
            if len(r) >= 3:
                g = Polygon([to_xy(lo, la) for la, lo in r])
                ps.append(g if g.is_valid else g.buffer(0.0))
        if ps:
            cl.append(c)
            polys.append(unary_union(ps))
    if len(cl) < 2:
        return {}
    par = list(range(len(cl)))

    def find(i: int) -> int:
        while par[i] != i:
            par[i] = par[par[i]]
            i = par[i]
        return i
    tree = STRtree(polys)
    for i, g in enumerate(polys):
        mi = set(cl[i].members)
        for j in tree.query(g, predicate="dwithin", distance=reach):
            j = int(j)
            if j > i and mi & set(cl[j].members) and find(i) != find(j):
                par[find(i)] = find(j)
    by: dict[int, list[int]] = {}
    for i in range(len(cl)):
        by.setdefault(find(i), []).append(i)
    out: dict[str, tuple[str, Polygon]] = {}
    for idx in by.values():
        if len(idx) < 2:
            continue
        walled = [i for i in idx if int(getattr(cl[i], "walled", 0) or 0)]
        files = {m for i in idx for m in cl[i].members}
        if not walled or len(files) < 2:
            continue
        u = unary_union([polys[i] for i in idx])
        x0, y0, x1, y1 = u.bounds
        if span_max > 0.0 and ((x1 - x0) ** 2 + (y1 - y0) ** 2) ** 0.5 >= span_max:
            continue
        if seat_float_m(u, dem_z) <= threshold:
            continue
        rep = str(cl[max(walled, key=lambda i: polys[i].area)].id)
        for i in idx:
            out[str(cl[i].id)] = (rep, u)
    return out


def slope_witness(airport: _t.Any, law: _t.Any) -> "SlopeWitness | None":
    """The witness for ``geom.cluster_outlines``' slope gate, or ``None``
    where it is disarmed (``[placement] slope_pad_float_m`` 0) or the
    airport carries no DEM.  Memoised per airport: the mint and the census
    read one object."""
    st = law.tables.structures.placement if law is not None else None
    t = float(getattr(st, "slope_pad_float_m", 0.0) or 0.0) if st is not None else 0.0
    dem = getattr(airport, "dem", None)
    if t <= 0.0 or dem is None or not hasattr(dem, "z"):
        return None
    for k, ap, w in _MEMO:
        if k == id(airport) and ap is airport and w.threshold == t:
            return w
    groups = (_groups(airport, st, dem.z, t)
              if getattr(airport, "frame", None) is not None else {})
    w = SlopeWitness(dem.z, t, groups)
    _MEMO.append((id(airport), airport, w))
    del _MEMO[:-2]
    return w
