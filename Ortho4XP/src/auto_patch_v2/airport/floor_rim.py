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

__all__ = ["rim_tops", "open_edge_tops"]


def rim_tops(outline, frame: _t.Sequence[tuple], cache, law, scale, zero: float,
             ceiling: "float | None" = None) -> tuple:
    """``((x, y, dz), ...)``: the frame's top (module doc) every
    ``wall_sample_m`` along ``outline`` (the footprint's rim, a Polygon or
    MultiPolygon), as metres over ``zero`` (``dz <= 0``) so a frame moved
    whole keeps it; ``frame`` is ``(placement, its zero)`` pairs.  ``()``
    when nothing of the frame reaches the outline.  ``ceiling`` (absolute)
    replaces each placement's own zero as the top's cap: a walled pit's
    zero stands under its rim (#1949 R2), the rim is its author's ground."""
    be, bn, hi, _ring = _tops(outline, frame, cache, law, scale, ceiling)
    ok = np.isfinite(hi)
    return tuple((float(x), float(y), round(float(z) - zero, 3))
                 for x, y, z in zip(be[ok], bn[ok], hi[ok], strict=True))


def open_edge_tops(outline, frame: _t.Sequence[tuple], cache, law, scale, zero: float,
                   ceiling: float, lift: float, ground, floor) -> tuple:
    """#1949 R2 (owner RULINGS 2026-11-16l): a walled pit's ``rim_tops`` --
    only where its wall is LOWER than the ground behind it.  Along
    ``outline`` (every ``wall_sample_m``), an OPEN EDGE is a sample where
    ``ground(xs, ys)`` stands more than ``[tunnel.object]
    shell_rim_ground_m`` over the frame's top as seated (its authored top,
    capped at ``ceiling``, plus ``lift``) and that top is a WALL's -- it
    stands ``hollow_m`` or more over ``floor(xs, ys)``, the pit's floor
    beside it.  There the rim is held at the top less
    ``retaining_parapet_m`` (a wall rises that far over the high side's
    ground), never under the cut beside it (the floor less
    ``floor_clearance_m``) and never over the ground, eased along the rim
    from the ground where the run's wall comes to meet it (a flush or proud
    wall; a lip is no such end) at ``[design] bank_slope``.
    Elsewhere -- a wall standing flush or proud, a LIP (no solid of the
    frame in reach, or only the floor's own edge: a ramp running out of the
    frame) -- nothing is stated and the rim stays as accepted.  ``dz`` is
    metres over ``zero + lift``."""
    ob = law.tables.structures.tunnel.object
    be, bn, hi, ring = _tops(outline, frame, cache, law, scale, ceiling)
    if not len(be):
        return ()
    top = hi + lift
    g = np.asarray(ground(be, bn), float)
    fl = np.asarray(floor(be, bn), float)
    with np.errstate(invalid="ignore"):
        wall = np.isfinite(top) & np.isfinite(g) & (top - fl >= float(ob.hollow_m))
        op = wall & (g - top > float(ob.shell_rim_ground_m))
    if not op.any():
        return ()
    level = np.maximum(top - float(ob.retaining_parapet_m), fl - float(ob.floor_clearance_m))
    # a run eases from where its wall meets the ground (a flush or proud
    # wall), never from a lip: no wall stands there to meet
    ease = _eased(be, bn, ring, np.where(wall & ~op, g, -np.inf),
                  float(law.tables.emit.design.bank_slope))
    level = np.minimum(np.maximum(level, ease), g)
    z0 = zero + lift
    return tuple((float(x), float(y), round(float(z) - z0, 3))
                 for x, y, z in zip(be[op], bn[op], level[op], strict=True))


def _eased(be, bn, ring, src, slope: float) -> np.ndarray:
    """Per sample, the highest ``src[j] - slope * d(i, j)`` over the samples
    ``j`` of its ring, ``d`` the distance along the (closed) ring: the
    ground at a run's ends falling into it at ``slope``."""
    out = np.full(len(be), -np.inf)
    for r in np.unique(ring):
        k = np.flatnonzero(ring == r)
        e = src[k].copy()
        xy = np.column_stack([be[k], bn[k]])
        ds = np.hypot(*(np.roll(xy, -1, axis=0) - xy).T)    # i -> i+1, closing
        for _lap in range(2):
            for i in range(len(k)):
                e[(i + 1) % len(k)] = max(e[(i + 1) % len(k)], e[i] - slope * ds[i])
            for i in range(len(k) - 1, -1, -1):
                e[i - 1] = max(e[i - 1], e[i] - slope * ds[i - 1])
        out[k] = e
    return out


def _tops(outline, frame, cache, law, scale, ceiling) -> tuple:
    """``(xs, ys, top, ring)`` per :func:`_samples` point of ``outline``:
    the frame's top there (absolute; ``nan`` with no solid in reach)."""
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
        # never above the placement's own zero (module doc), or the ceiling
        P[:, 2] = np.minimum(P[:, 2], z0 if ceiling is None else ceiling)
        pts.append(P)
    be, bn, ring = _samples(outline, step)
    if not pts or not len(be):
        e = np.zeros(0)
        return e, e, e, e.astype(int)
    _lo, hi = _shape.outline_reach(np.vstack(pts), be, bn, reach)
    return be, bn, hi, ring


def _samples(outline, step: float) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Points every ``step`` along every exterior ring of ``outline``, and
    the index of the ring each lies on."""
    xs, ys, rs = [], [], []
    for r, g in enumerate(getattr(outline, "geoms", [outline])):
        ring = g.exterior
        n = max(4, int(np.ceil(ring.length / step)))
        for k in range(n):
            q = ring.interpolate(k * ring.length / n)
            xs.append(q.x)
            ys.append(q.y)
            rs.append(r)
    return np.asarray(xs, float), np.asarray(ys, float), np.asarray(rs, int)
