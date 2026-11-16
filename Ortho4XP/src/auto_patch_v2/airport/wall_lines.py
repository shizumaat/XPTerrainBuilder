"""THE WALL LINES OF A MOUTH'S WALLS (#2099 R3 D1; spec
``docs/specs/2099-R3.md`` §4): a wall placement's WALL LINES are the
connected components of its genuine solids' plan (``airport/mouth_group.
_solids``), each read along its own centre line (``geom/centreline.
ribbon_centreline``) every ``[tunnel.object] wall_sample_m`` from the end
nearest the mouth: the cross-section NORMAL to the line there, its lowest
solid y (never under 0) the FOOT, its highest the TOP.  A section holding
only a coping (its foot within ``plate_bin_m`` of its top) is dropped.
AN END STATION IS NO SECTION (R3b D1b): the first and the last station
take the extent ``(lo, hi)`` and the foot of their nearest interior
station, their top standing -- a section at a line's end cuts the wall's
end cap (measured: 0.17-0.56 m thick against 1.0-1.5 m inside; one end
foot 5.19 over an interior foot 0.00).

Read by the mouth group (a wall lining the mouth's road, R3 E) and the cut
beside it (``planar/wing_cut``, R3 D).  Nothing here names a pack, a
resource or an airport.
"""
from __future__ import annotations

import math

import numpy as np
import shapely
from shapely.geometry import LineString, Point

from ..geom.centreline import ribbon_centreline
from ..geom.parts import polygon_parts_with_area
from . import obj8 as _obj8

__all__ = ["Station", "wall_line_feet"]

XY = tuple[float, float]
#: one station of a wall line: centre ``(x, y)``, unit normal ``(nx, ny)``,
#: the section's extent ``(lo, hi)`` along the normal, its foot and top
Station = tuple[float, float, float, float, float, float, float, float]


def wall_line_feet(o, cache, law, mouth_plan) -> list[tuple[tuple[XY, ...], list[Station]]]:
    """``[(centre line, stations)]`` per WALL LINE of placement ``o`` (module
    doc, R3 D1), the line nearest the mouth's plan first; ``[]`` with no
    solid."""
    from .mouth_group import _solids
    read = _solids(o, cache, law)
    if read is None:
        return []
    ob = law.tables.structures.tunnel.object
    step, coping = float(ob.wall_sample_m), float(ob.plate_bin_m)
    g = cache.geometry(o.resolved)
    tris = np.concatenate([c.tris for c in cache.genuine(o.resolved)])
    a, b, d, e, xo, yo = _obj8.placement_affine(o.xy, o.heading_deg)
    v = g.vertices
    X, Y = a * v[:, 0] + b * v[:, 2] + xo, d * v[:, 0] + e * v[:, 2] + yo
    edges = np.unique(np.sort(np.concatenate([tris[:, [0, 1]], tris[:, [1, 2]],
                                              tris[:, [2, 0]]]), axis=1), axis=0)
    out = []
    for part in sorted(polygon_parts_with_area(read[0]), key=mouth_plan.distance):
        ln = ribbon_centreline(part, min(step, 0.5))
        if ln is None or ln.length <= 1e-6:
            continue
        if mouth_plan.distance(Point(ln.coords[-1])) < mouth_plan.distance(Point(ln.coords[0])):
            ln = LineString(list(ln.coords)[::-1])
        inside = part.buffer(0.05)
        ss = [*np.arange(0.0, ln.length, step), ln.length]
        st = [q for s in ss
              if (q := _section(ln, float(s), X, Y, v[:, 1], edges, inside, coping)) is not None]
        if st:
            out.append((tuple(ln.coords), _ends_from_inside(st)))
    return out


def _ends_from_inside(st: list[Station]) -> list[Station]:
    """R3b D1b: the first / last station takes its nearest interior
    station's extent and foot; its own top stands (3 stations or more)."""
    if len(st) < 3:
        return st
    a, b = st[0], st[-1]
    return [a[:4] + st[1][4:7] + (a[7],), *st[1:-1], b[:4] + st[-2][4:7] + (b[7],)]


def _section(ln: LineString, s: float, X, Y, Yv, edges, inside, coping: float
             ) -> "Station | None":
    """The cross-section of the solids NORMAL to ``ln`` at ``s`` within
    ``inside`` (its own wall line), or ``None`` (no solid, or a coping)."""
    p = ln.interpolate(s)
    p0, p1 = ln.interpolate(max(0.0, s - 0.5)), ln.interpolate(min(ln.length, s + 0.5))
    tx, ty = p1.x - p0.x, p1.y - p0.y
    L = math.hypot(tx, ty)
    if L <= 1e-9:
        return None
    tx, ty = tx / L, ty / L
    nx, ny = -ty, tx
    T = (X - p.x) * tx + (Y - p.y) * ty
    ta, tb = T[edges[:, 0]], T[edges[:, 1]]
    m = (ta * tb <= 0.0) & (ta != tb)
    if not m.any():
        return None
    f = (-ta[m]) / (tb[m] - ta[m])
    i0, i1 = edges[m, 0], edges[m, 1]
    cx, cy = X[i0] + f * (X[i1] - X[i0]), Y[i0] + f * (Y[i1] - Y[i0])
    keep = shapely.contains_xy(inside, cx, cy)
    if not keep.any():
        return None
    ys = (Yv[i0] + f * (Yv[i1] - Yv[i0]))[keep]
    ns = ((cx - p.x) * nx + (cy - p.y) * ny)[keep]
    foot, top = max(float(ys.min()), 0.0), float(ys.max())
    if top - foot <= coping:
        return None
    return (p.x, p.y, nx, ny, float(ns.min()), float(ns.max()), foot, top)
