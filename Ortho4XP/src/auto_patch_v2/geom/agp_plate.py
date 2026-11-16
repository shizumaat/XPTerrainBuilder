"""WHERE AN AGP PLATE STANDS (#2090 C3; spec ``2090-agp-group-groundside-
spec.md`` amendment C): the ONE selection of the vertices inside a built
plate and of those near it, read by the plate's rows (``constraints/
agp_plate``) and by the road ramp's seeds (``airport/deck_ends``).

Pure shape, duck-typed on the records (``model/agp_group.AgpGroup`` /
``AgpPlate``, ``model/deck_stack.DeckStack``): ``geom`` imports nothing of
v2 (test_model.test_dependency_direction).  Nothing here names an airport.
"""
from __future__ import annotations

import typing as _t

import numpy as np
import shapely

__all__ = ["built_plates", "inside_plates", "near_plates", "under_rings"]


def built_plates(groups) -> list[tuple[str, _t.Any, _t.Any]]:
    """``[(group id, plate, polygon)]`` of every BUILT plate of a governed group."""
    out = []
    for g in groups or ():
        if getattr(g, "governor", None) is None:
            continue
        for p in getattr(g, "plates", ()) or ():
            if p.built and len(p.ring) >= 3:
                out.append((str(g.id), p, shapely.Polygon(p.ring, p.holes)))
    return out


def _xy(items: _t.Sequence[tuple[int, tuple[float, float]]]) -> np.ndarray:
    return np.asarray([xy for _v, xy in items], float).reshape(-1, 2)


def inside_plates(items: _t.Sequence[tuple[int, tuple[float, float]]], plates,
                  grid: float = 0.0) -> dict[int, tuple[str, _t.Any]]:
    """``{v: (group id, plate)}`` of every ``(v, xy)`` inside a plate (grown
    by ``grid``); the first plate wins."""
    out: dict[int, tuple[str, _t.Any]] = {}
    if not items or not plates:
        return out
    pts = _xy(items)
    for gid, p, poly in plates:
        hit = shapely.contains_xy(poly.buffer(grid) if grid else poly, pts[:, 0], pts[:, 1])
        for k in np.flatnonzero(hit).tolist():
            out.setdefault(items[k][0], (gid, p))
    return out


def near_plates(items: _t.Sequence[tuple[int, tuple[float, float]]], plates,
                reach: _t.Callable[[_t.Any], float]) -> dict[int, tuple[str, _t.Any, float]]:
    """``{v: (group id, plate, d)}`` of every ``(v, xy)`` OUTSIDE every plate
    and within ``reach(plate)`` of one (the nearest)."""
    out: dict[int, tuple[str, _t.Any, float]] = {}
    if not items or not plates:
        return out
    pts = _xy(items)
    geoms = shapely.points(pts)
    inside = np.zeros(len(items), bool)
    for _gid, _p, poly in plates:
        inside |= shapely.contains_xy(poly, pts[:, 0], pts[:, 1])
    for gid, p, poly in plates:
        r = float(reach(p))
        d = shapely.distance(poly, geoms)
        for k in np.flatnonzero((~inside) & (d <= r)).tolist():
            v = items[k][0]
            if v not in out or d[k] < out[v][2]:
                out[v] = (gid, p, float(d[k]))
    return out


def under_rings(items: _t.Sequence[tuple[int, tuple[float, float]]], rings) -> set[int]:
    """The ``v`` of ``(v, xy)`` standing under one of the plan ``rings``
    (C3c: a joined or riding deck's)."""
    polys = [shapely.Polygon(r) for r in rings if len(r) >= 3]
    if not items or not polys:
        return set()
    u = shapely.union_all(polys)
    pts = _xy(items)
    return {items[k][0] for k in np.flatnonzero(shapely.contains_xy(u, pts[:, 0],
                                                                    pts[:, 1])).tolist()}
