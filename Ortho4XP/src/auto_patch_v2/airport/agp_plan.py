"""A GOVERNED GROUP'S FOLLOWERS' PLANS: WHERE A FOLLOWER STANDS, NO PAD
(#2116 R2 G1; owner RULINGS 2026-11-16r/s/t).

A FOLLOWER of a governed AGP group (``AgpGroup.followers``) is seated by
X-Plane at its ``GROUND_PT`` on the group's datum — never by a pad.  A
building footprint (any admitted source) lying mostly inside a follower's
PLAN would mint a pad on the per-body DEM datum that fronts nothing and
pulls every neighbour to it (KDEN building22).  The plan here is the plan
of the follower's placed pieces' up-facing floors (``agp_plates.
_floor_plan``: every floor at any height, roofs included — the floor
cache's one read, no second OBJ8 walk), sampled on a grid: a footprint's COVER is the
share of its grid points standing on a floor triangle.

The predicate is used at the ONE pad derivation site
(``classify/evidence._pads``).  Nothing here names a pack, a resource or
an airport.
"""
from __future__ import annotations

import dataclasses as _dc
import math
import typing as _t

import numpy as np

__all__ = ["FollowerPlan", "follower_plans", "follower_cover"]

#: floor triangles smaller than this (m²) are left out of the plan (the
#: roofs and slabs carry the plan; trims and railings only cost the read)
_MIN_TRI_M2 = 1.0
#: the cover's sampling grid (m)
_GRID_M = 2.0


@_dc.dataclass(frozen=True)
class FollowerPlan:
    """One follower's plan: ``group`` / ``row``, its floor triangles in the
    frame (``(k, 3, 2)``) and their tree, and the plan's bounds."""

    group: str
    row: str
    tris: np.ndarray
    tree: _t.Any
    bounds: tuple[float, float, float, float]


def follower_plans(airport, law) -> list[FollowerPlan]:
    """Every governed group's followers' plans (module doc); ``[]`` with
    no governed group."""
    groups = [g for g in getattr(airport, "agp_groups", ()) or () if g.governor is not None]
    if not groups or law is None:
        return []
    import shapely

    from .agp_group import members_of
    from .agp_plates import _floor_plan
    agp = law.tables.structures.agp
    lat0, lon0 = airport.frame.transformers()[1](0.0, 0.0)
    by_row = {m.row: m for m in members_of(airport)}
    memo: dict = {}
    out = []
    for g in groups:
        for fm in g.followers():
            m = by_row.get(fm.row)
            if m is None:
                continue
            tris = _floor_plan(m, lat0, lon0, memo, agp, airport)()
            if not tris.shape[0]:
                continue
            polys = shapely.polygons(tris)
            keep = shapely.area(polys) >= _MIN_TRI_M2
            if not keep.any():
                continue
            tris, polys = tris[keep], polys[keep]
            lo, hi = tris.reshape(-1, 2).min(axis=0), tris.reshape(-1, 2).max(axis=0)
            out.append(FollowerPlan(g.id, fm.row, tris, shapely.STRtree(polys),
                                    (float(lo[0]), float(lo[1]), float(hi[0]), float(hi[1]))))
    return out


def follower_cover(plans: _t.Sequence[FollowerPlan], poly) -> tuple[FollowerPlan, float] | None:
    """``(plan, share)`` of the follower plan covering most of ``poly``
    (frame metres), or ``None`` when none touches it."""
    import shapely
    if not plans or poly is None or poly.is_empty:
        return None
    x0, y0, x1, y1 = poly.bounds
    best = None
    pts = None
    for p in plans:
        bx0, by0, bx1, by1 = p.bounds
        if bx1 < x0 or bx0 > x1 or by1 < y0 or by0 > y1:
            continue
        if pts is None:
            step = min(_GRID_M, max(0.25, math.sqrt(poly.area) / 20.0))
            gx, gy = np.meshgrid(np.arange(x0 + step / 2, x1, step),
                                 np.arange(y0 + step / 2, y1, step))
            gx, gy = gx.ravel(), gy.ravel()
            inside = shapely.contains_xy(poly, gx, gy)
            pts = shapely.points(gx[inside], gy[inside])
            if not len(pts):
                return None
        hit = p.tree.query(pts, predicate="intersects")
        share = float(np.unique(hit[0]).size) / float(len(pts))
        if best is None or share > best[1]:
            best = (p, share)
    return best
