"""THE UNDERSIDE OF AN OBJECT OVER A LOWER LEVEL (owner 2026-11-04T18:42Z on
KIAH #1852: "It has to be low enough vehicles can pass under it, so 5m
minimum below the station"; round 4 of the two-level model).

A lower level that runs under a pack object -- the roads through a station
or terminal -- must leave ``[tunnel] clearance_m`` (the road's vertical
clearance under the roof) to the object's lowest OVERHEAD geometry.  That
geometry is read off the object itself, never off its wall feet: on a grid
of ``step`` metres over the level, the lowest HORIZONTAL static solid
triangle (a soffit, a slab underside) covering each cell above the floor;
and, apart, the lowest static solid of any slope over it (a stair, a
bracket), reported but not taken as the roof.

MEASURED KIAH ``KIAH_Trainstation2.obj`` over its roads: soffits at y
+1.36 (87 cells), +3.46 and +7.88 over the -3.93 wall feet -- 5.29 m clear;
a 0.7 m sloped element at 29.98723, -95.33285 reaches -1.75.

Nothing here names a pack, a resource or an airport.
"""
from __future__ import annotations

__all__ = ["underside_over"]

#: a triangle this flat (its y span) is a horizontal surface
FLAT_DY_M = 0.05
#: overhead geometry stands at least this far over the floor (a kerb, a
#: drawn road surface on the floor itself is no roof)
OVER_FLOOR_M = 0.5


def underside_over(members, cache, to_xy, region, floor_y: float, step: float = 2.0
                   ) -> "dict | None":
    """``{"soffit_y", "any_y", "any_xy", "cells"}`` -- the lowest horizontal
    and the lowest overhead geometry (authored y, the members' common frame)
    over ``region`` (frame xy) of the pack ``members`` above ``floor_y``
    (module docstring), or ``None`` where no geometry covers it."""
    import numpy as np
    from shapely import STRtree
    from shapely.geometry import Point, Polygon

    from ..airport.obj8 import _to_frame
    tris: list = []
    for m in members:
        path = getattr(m, "authored_path", None) or getattr(m, "live_path", None)
        g = cache.geometry(path) if cache is not None and path else None
        if g is None or not g.solid.shape[0]:
            continue
        o = to_xy(float(m.origin[1]), float(m.origin[0]))
        h = float(getattr(m, "heading_deg", 0.0) or 0.0)
        anim = g.animated if g.animated.shape[0] else np.zeros(len(g.solid), dtype=bool)
        V = g.vertices
        for i, t in enumerate(g.solid):
            if anim[i]:
                continue
            ys = V[t][:, 1]
            if float(ys.max()) <= floor_y + OVER_FLOOR_M:
                continue
            poly = Polygon([_to_frame(o, h, float(V[k, 0]), float(V[k, 2])) for k in t])
            if poly.area <= 1e-6 or not poly.intersects(region):
                continue
            tris.append((poly, float(ys.min()), float(ys.max())))
    if not tris:
        return None
    tree = STRtree([p for p, _a, _b in tris])
    x0, y0, x1, y1 = region.bounds
    soffit, cells = [], 0
    any_y, any_xy = None, None
    for x in np.arange(x0, x1, step):
        for y in np.arange(y0, y1, step):
            c = Point(x + 0.5 * step, y + 0.5 * step)
            if not region.contains(c):
                continue
            cells += 1
            hit = [tris[int(j)] for j in tree.query(c, predicate="intersects")]
            flat = [lo for _p, lo, hi in hit
                    if hi - lo <= FLAT_DY_M and lo > floor_y + OVER_FLOOR_M]
            if flat:
                soffit.append(min(flat))
            low = [lo for _p, lo, _hi in hit if lo > floor_y + OVER_FLOOR_M]
            if low and (any_y is None or min(low) < any_y):
                any_y, any_xy = min(low), (float(c.x), float(c.y))
    if not soffit and any_y is None:
        return None
    return {"soffit_y": round(min(soffit), 3) if soffit else None,
            "any_y": None if any_y is None else round(any_y, 3), "any_xy": any_xy,
            "cells": cells, "covered": len(soffit)}
