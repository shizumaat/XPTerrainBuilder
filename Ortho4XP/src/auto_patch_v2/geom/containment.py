"""Which point sets stand whole inside one of a set of rings (leaf geometry;
issue #84).  Shared so ``model/islands`` (the courtyard derivation) stays
free of shapely — the model layer carries no geometry library
(``tests/auto_patch_v2/test_model.py``)."""
from __future__ import annotations

import typing as _t

__all__ = ["sets_inside_one_ring"]

XY = tuple[float, float]


def sets_inside_one_ring(rings: _t.Sequence[_t.Sequence[XY]],
                         point_sets: _t.Sequence[_t.Sequence[XY]],
                         tol_m: float) -> list[bool]:
    """For each point set, True when EVERY point lies inside ONE ring
    buffered by ``tol_m`` (the ring found by the set's first point).  Rings
    with fewer than three points, or empty after repair, are skipped."""
    from shapely.geometry import Point, Polygon
    from shapely.strtree import STRtree

    polys: list = []
    for r in rings:
        if len(r) < 3:
            continue
        poly = Polygon(r)
        if not poly.is_valid:
            poly = poly.buffer(0.0)
        if poly.is_empty:
            continue
        polys.append(poly.buffer(tol_m))
    out = [False] * len(point_sets)
    if not polys:
        return out
    tree = STRtree(polys)
    for i, ps in enumerate(point_sets):
        if not ps:
            continue
        pts = [Point(*p) for p in ps]
        for hi in tree.query(pts[0]):
            hp = polys[int(hi)]
            if all(hp.contains(p) for p in pts):
                out[i] = True
                break
    return out
