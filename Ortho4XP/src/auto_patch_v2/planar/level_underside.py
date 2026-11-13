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
    tris: list = []
    for m in members:
        path = getattr(m, "authored_path", None) or getattr(m, "live_path", None)
        g = cache.geometry(path) if cache is not None and path else None
        if g is None or not g.solid.shape[0]:
            continue
        o = to_xy(float(m.origin[1]), float(m.origin[0]))
        tris.extend(_overhead(g, o, float(getattr(m, "heading_deg", 0.0) or 0.0),
                              floor_y + OVER_FLOOR_M, region))
    if not tris:
        return None
    return _cells_over(tris, region, floor_y + OVER_FLOOR_M, step)


def _cells_over(tris: list, region, above_y: float, step: float) -> "dict | None":
    """The grid read of :func:`underside_over` over ``tris`` in one array
    pass: the cells of ``step`` metres whose centre ``region`` contains, in
    the x-major order the scalar walk took, each cell's lowest flat and
    lowest overhead triangle over ``above_y``.  ``any_xy`` is the FIRST cell
    reaching the lowest overhead level, as the walk's strict ``<`` kept."""
    import numpy as np
    import shapely
    from shapely import STRtree

    x0, y0, x1, y1 = region.bounds
    xs = np.arange(x0, x1, step) + 0.5 * step
    ys = np.arange(y0, y1, step) + 0.5 * step
    px, py = np.repeat(xs, len(ys)), np.tile(ys, len(xs))
    inside = shapely.contains_xy(region, px, py)
    px, py = px[inside], py[inside]
    cells = int(px.size)
    if not cells:
        return None
    lo = np.array([t[1] for t in tris], dtype=np.float64)
    hi = np.array([t[2] for t in tris], dtype=np.float64)
    cell, tri = STRtree([p for p, _a, _b in tris]).query(shapely.points(px, py),
                                                          predicate="intersects")
    up = lo[tri] > above_y
    flat = up & (hi[tri] - lo[tri] <= FLAT_DY_M)
    soff = np.full(cells, np.inf)
    np.minimum.at(soff, cell[flat], lo[tri][flat])
    low = np.full(cells, np.inf)
    np.minimum.at(low, cell[up], lo[tri][up])
    covered = int(np.isfinite(soff).sum())
    if not covered and not np.isfinite(low).any():
        return None
    any_y = any_xy = None
    if np.isfinite(low).any():
        k = int(np.argmin(low))
        any_y, any_xy = float(low[k]), (float(px[k]), float(py[k]))
    return {"soffit_y": round(float(soff.min()), 3) if covered else None,
            "any_y": None if any_y is None else round(any_y, 3), "any_xy": any_xy,
            "cells": cells, "covered": covered}


def _overhead(g, o, heading_deg: float, above_y: float, region) -> list:
    """``[(plan polygon, y min, y max), ...]``: the static solid triangles of
    one member's geometry ``g`` (placed at frame xy ``o``, ``heading_deg``)
    rising over ``above_y`` whose plan meets ``region``, in triangle order.
    Array arithmetic in the order ``obj8._to_frame`` writes it, in float64,
    so every plan coordinate is the scalar reading's to the bit (#1951: the
    per-triangle loop was ~30 s per planar pass at KMCI)."""
    import math

    import numpy as np
    import shapely

    T = np.asarray(g.solid)
    V = np.asarray(g.vertices, dtype=np.float64)
    ys = V[T][:, :, 1]
    keep = ys.max(axis=1) > above_y
    if g.animated.shape[0]:
        keep &= ~np.asarray(g.animated, dtype=bool)
    idx = np.nonzero(keep)[0]
    if not idx.size:
        return []
    h = math.radians(heading_deg)
    s, c = math.sin(h), math.cos(h)
    x, z = V[T[idx]][:, :, 0], V[T[idx]][:, :, 2]
    px = (o[0] + x * c) - z * s
    py = o[1] - (x * s + z * c)
    polys = shapely.polygons(np.stack([px, py], axis=-1))
    ok = (shapely.area(polys) > 1e-6) & shapely.intersects(polys, region)
    lo, hi = ys.min(axis=1), ys.max(axis=1)
    return [(polys[k], float(lo[i]), float(hi[i]))
            for k, i in enumerate(idx.tolist()) if ok[k]]
