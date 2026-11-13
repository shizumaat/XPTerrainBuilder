"""THE GROUND MEETS A TRENCH OBJECT'S TOP EDGE (owner RULINGS 2026-11-06d
(5), #1921: "some places the tunnel roofs, which act as taxiway bridges, are
not flush with the airside pavement they abut.  Like a bridge, the airside
pavement must grade smoothly to the object edge"; #1936, owner sim read of
1.0.476: "in some places terrain is not graded smoothly to the outer edges
of the walls").

A floor object's frame (``airport/object_floor``: the floor, its covers --
the walls and the hard-deck roofs a taxiway drives across -- and every
placement co-placed with them) is written whole at its zero.  The ground
and pavement round it meet it at its OUTLINE: the rim of the cut (the
footprint's void band, ``planar/object_floor_cells``) stands at the
frame's TOP there -- the highest solid of the frame within
``[tunnel.object] wall_face_max_thickness_m`` of the rim in plan (a wall's
crest, a roof's edge), never above the frame's own zero (the author's
ground: a parapet or a railing standing over it is furniture on the
ground, not the ground).  A rim point with no solid of the frame within
that reach (an open ramp's lip) states nothing.

MEASURED EGLL (+51-001, base 79a3a386d): the seven floor frames' tops
along their rims read +0.00 m over the zero (5a +0.94, 9a +0.76: walls
standing over the ground), while the DEM 1 m outside them reads -1.3 ..
-1.7 m under it (p50; p10 -4.5: the survey's own trench beside the
object) -- the rim the solve left there is that DEM, a moat beside the
walls and a step at every roof a taxiway crosses.

Nothing here names a pack, a resource or an airport.
"""
from __future__ import annotations

import typing as _t

import numpy as np

from ..geom import shape_class as _shape
from .below_grade_witness import placed_all as _placed_all

__all__ = ["rim_tops"]


def rim_tops(outline, frame: _t.Sequence[tuple], cache, law, scale, zero: float) -> tuple:
    """``((x, y, dz), ...)``: the frame's top (module doc) every
    ``wall_sample_m`` along ``outline`` (the footprint's rim, a Polygon or
    MultiPolygon), as metres over ``zero`` (``dz <= 0``) so a frame moved
    whole keeps it; ``frame`` is ``(placement, its zero)`` pairs.  ``()``
    when nothing of the frame reaches the outline."""
    ob = law.tables.structures.tunnel.object
    step, reach = float(ob.wall_sample_m), float(ob.wall_face_max_thickness_m)
    pts = []
    for p, z0 in frame:
        g = cache.geometry(p.resolved) if p.resolved else None
        if g is None or not len(g.solid):
            continue
        F = _placed_all(p, g, z0, scale)
        k = len(F)
        V = F.reshape(-1, 3)
        P = _shape.edge_points(V, np.arange(3 * k).reshape(k, 3), 0.5 * step)
        # never above the placement's own zero (module doc)
        P[:, 2] = np.minimum(P[:, 2], z0)
        pts.append(P)
    if not pts:
        return ()
    P = np.vstack(pts)
    be, bn = _samples(outline, step)
    if not len(be):
        return ()
    _lo, hi = _shape.outline_reach(P, be, bn, reach)
    ok = np.isfinite(hi)
    return tuple((float(x), float(y), round(float(z) - zero, 3))
                 for x, y, z in zip(be[ok], bn[ok], hi[ok], strict=True))


def _samples(outline, step: float) -> tuple[np.ndarray, np.ndarray]:
    """Points every ``step`` along every exterior ring of ``outline``."""
    xs, ys = [], []
    for g in getattr(outline, "geoms", [outline]):
        ring = g.exterior
        n = max(4, int(np.ceil(ring.length / step)))
        for k in range(n):
            q = ring.interpolate(k * ring.length / n)
            xs.append(q.x)
            ys.append(q.y)
    return np.asarray(xs, float), np.asarray(ys, float)
