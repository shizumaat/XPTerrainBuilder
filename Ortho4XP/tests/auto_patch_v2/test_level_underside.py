"""The underside read over a lower level (``planar/level_underside``) in
array form is the scalar walk's answer to the bit (#1951: the walk was ~30 s
of every planar pass at KMCI).  The reference below is the walk as it stood
before #1951, kept here as the oracle."""
from __future__ import annotations

import math
import types

import numpy as np
from auto_patch_v2.planar.level_underside import FLAT_DY_M, OVER_FLOOR_M, underside_over
from shapely import STRtree
from shapely.geometry import Point, Polygon, box


def _to_frame(xy, heading_deg, x, z):
    h = math.radians(heading_deg)
    s, c = math.sin(h), math.cos(h)
    return (xy[0] + x * c - z * s, xy[1] - (x * s + z * c))


def _reference(members, cache, to_xy, region, floor_y, step=2.0):
    tris = []
    for m in members:
        g = cache.geometry(m.authored_path)
        o = to_xy(float(m.origin[1]), float(m.origin[0]))
        h = float(m.heading_deg)
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
    soffit, cells, any_y, any_xy = [], 0, None, None
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


def _quad(x0, z0, x1, z1, y0, y1=None):
    """Two triangles of a quad from (x0, z0) to (x1, z1); ``y1`` tilts it."""
    y1 = y0 if y1 is None else y1
    v = [(x0, y0, z0), (x1, y0, z0), (x1, y1, z1), (x0, y1, z1)]
    return v, [(0, 1, 2), (0, 2, 3)]


def _member(path, origin, heading, quads, animated=()):
    verts, tris = [], []
    for q in quads:
        v, t = _quad(*q)
        base = len(verts)
        verts.extend(v)
        tris.extend(tuple(base + k for k in tri) for tri in t)
    anim = np.zeros(len(tris), dtype=bool)
    for i in animated:
        anim[i] = True
    g = types.SimpleNamespace(vertices=np.asarray(verts, dtype=np.float32),
                              solid=np.asarray(tris, dtype=np.int64), animated=anim)
    m = types.SimpleNamespace(authored_path=path, origin=origin, heading_deg=heading)
    return m, g


def test_array_read_is_the_walks_answer():
    members, geoms = [], {}
    for path, origin, heading, quads, anim in (
            # a soffit at 4.10 over the floor, a lower one at 3.25, a ramp
            ("a.obj", (10.0, 20.0), 33.7, [(-9, -7, 9, 7, 4.1), (-3, -2, 3, 2, 3.25),
                                           (-6, 2, 6, 5, 2.0, 5.5)], ()),
            # a beam BELOW the floor's clearance and an animated door
            ("b.obj", (12.5, 18.0), 201.3, [(-5, -5, 5, 5, -0.2), (-1, -1, 1, 1, 1.0)], (2, 3)),
            # a slab the region misses entirely
            ("c.obj", (400.0, 400.0), 0.0, [(-2, -2, 2, 2, 5.0)], ())):
        m, g = _member(path, origin, heading, quads, anim)
        members.append(m)
        geoms[path] = g
    cache = types.SimpleNamespace(geometry=lambda p: geoms.get(p))

    def to_xy(lon, lat):
        return (lon * 0.5, lat * 0.25)
    for region in (box(-4.0, -3.0, 9.5, 11.0),
                   Polygon([(-6, -2), (8, -5), (11, 9), (0, 12)]),
                   box(300.0, 300.0, 310.0, 310.0)):
        for floor in (-1.0, 0.0, 3.0):
            got = underside_over(members, cache, to_xy, region, floor)
            want = _reference(members, cache, to_xy, region, floor)
            assert got == want, (region.wkt, floor, got, want)
    assert underside_over(members, cache, to_xy, box(-4.0, -3.0, 9.5, 11.0), -1.0)["covered"] > 0
