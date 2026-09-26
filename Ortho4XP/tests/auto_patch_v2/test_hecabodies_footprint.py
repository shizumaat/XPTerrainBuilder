"""§16g (7) (1) THE FOOTPRINT RING IS BOUNDED OUTWARD (lane ``hecabodies``,
issues #6 / #7, HECA-1 / HECA-2).

``contact.plan_hull`` is the ONE derivation of a component's plan footprint
(the rings the footprint unit chains on and the cluster pad is the union
of).  Measured at HECA on the pack's own OBJ8s:

* ``Hangar_Tower/metal_strip_2.obj`` component 117 — a kerb strip, 113 m2
  in plan — read 7,385 m2 (the outward simplification doubled its buffer to
  6.4 m to fit 16 vertices) and carried ``building13``'s pad over the
  service road at 30.1125298, 31.4064909 (#7);
* ``Hangar_Tower/titles_1_yellow.obj`` component 0 — a lettering band with
  NO plan area — took its convex hull, 1,946 m2, pushed the T3_20 cluster
  pad into the concrete slab's footprint pad and minted a second
  ``building20`` face nested inside the first (#6);
* component 69 of the same strip file — 15 m2 of rail around a 59 x 21 m
  rectangle — read 1,235 m2 because a ring carries no holes.

Headless, synthetic geometry only.
"""
from __future__ import annotations

import numpy as np
from shapely.geometry import Point, Polygon
from shapely.ops import unary_union

from auto_patch_v2.airport import contact as C


def _strip(path, width=0.3, y0=0.0, y1=3.0):
    """A THIN solid strip along a plan polyline: a box of ``width`` per
    segment, top and bottom faces (plan area) and walls, in the OBJ8 frame
    (x, y, z) with z the plan north."""
    pts, tris = [], []
    for (x0, z0), (x1, z1) in zip(path, path[1:]):
        dx, dz = x1 - x0, z1 - z0
        n = np.hypot(dx, dz)
        ox, oz = -dz / n * width / 2, dx / n * width / 2
        quad = [(x0 + ox, z0 + oz), (x1 + ox, z1 + oz),
                (x1 - ox, z1 - oz), (x0 - ox, z0 - oz)]
        base = len(pts)
        for y in (y0, y1):
            for qx, qz in quad:
                pts.append((qx, y, qz))
        for a, b, c in ((0, 1, 2), (0, 2, 3), (4, 5, 6), (4, 6, 7),
                        (0, 1, 5), (0, 5, 4), (1, 2, 6), (1, 6, 5),
                        (2, 3, 7), (2, 7, 6), (3, 0, 4), (3, 4, 7)):
            tris.append((base + a, base + b, base + c))
    return np.asarray(pts, dtype=float), np.asarray(tris, dtype=int)


def _wall(path, y0=0.0, y1=3.0):
    """A band with NO plan area: vertical quads along a plan polyline."""
    pts, tris = [], []
    for (x0, z0), (x1, z1) in zip(path, path[1:]):
        b = len(pts)
        pts += [(x0, y0, z0), (x1, y0, z1), (x1, y1, z1), (x0, y1, z0)]
        tris += [(b, b + 1, b + 2), (b, b + 2, b + 3)]
    return np.asarray(pts, dtype=float), np.asarray(tris, dtype=int)


def _true(pts, tris):
    xz = np.column_stack((pts[:, 0], pts[:, 2]))
    return unary_union([Polygon(xz[t]) for t in tris
                        if Polygon(xz[t]).area > 1e-6])


def _rings_union(rings):
    return unary_union([Polygon(r).buffer(0) for r in rings])


# a zig-zag kerb 400 m long: far more than 16 vertices of outline
ZIGZAG = [(0.0, 0.0)] + [(20.0 * k, 12.0 * (k % 2)) for k in range(1, 21)]


def test_a_thin_strip_is_not_inflated_into_a_band():
    pts, tris = _strip(ZIGZAG)
    true = _true(pts, tris)
    rings = C.plan_hull(pts, tris)
    got = _rings_union(rings)
    assert all(len(r) <= C.FOOTPRINT_RING_MAX for r in rings)
    # OUTWARD (owner RULINGS 2026-09-14j): the rings contain the footprint
    assert got.buffer(1e-6).covers(true)
    # ...and grow it by no more than the bounded tolerance all round
    assert got.area <= true.buffer(C.OUTWARD_TOL_MAX_M + 0.05,
                                   join_style=2).area + 1e-6
    # the old reading claimed the ground between the zig-zag's teeth
    assert not got.contains(Point(20.0, 2.0))


def test_a_wall_with_no_plan_area_is_its_line_not_its_hull():
    # an L-shaped lettering band: 60 m then 40 m, vertical only
    pts, tris = _wall([(0.0, 0.0), (60.0, 0.0), (60.0, 40.0)])
    rings = C.plan_hull(pts, tris)
    got = _rings_union(rings)
    assert rings
    # the convex hull would be a 1,200 m2 triangle
    assert got.area < 100.0 * 2 * (C.OUTLINE_SIMPLIFY_M + C.OUTWARD_TOL_MAX_M) + 1.0
    assert not got.contains(Point(40.0, 10.0))
    assert got.buffer(1e-6).covers(Point(30.0, 0.0))


def test_a_frame_keeps_the_ground_it_encloses_out_of_its_footprint():
    # a 59 x 21 m rail frame
    pts, tris = _strip([(0.0, 0.0), (59.0, 0.0), (59.0, 21.0), (0.0, 21.0),
                        (0.0, 0.0)])
    rings = C.plan_hull(pts, tris)
    got = _rings_union(rings)
    assert got.buffer(1e-6).covers(_true(pts, tris))
    assert not got.contains(Point(29.5, 10.5))
    assert got.area < 0.25 * 59.0 * 21.0


def test_a_compact_footprint_is_unchanged_in_kind():
    # a plain 30 x 20 m slab: one ring, the rectangle grown by <= the tolerance
    pts = np.array([(0, 0, 0), (30, 0, 0), (30, 0, 20), (0, 0, 20)], float)
    tris = np.array([(0, 1, 2), (0, 2, 3)])
    rings = C.plan_hull(pts, tris)
    assert len(rings) == 1
    a = Polygon(rings[0]).area
    assert 600.0 <= a <= Polygon([(0, 0), (30, 0), (30, 20), (0, 20)]).buffer(
        C.OUTLINE_SIMPLIFY_M, join_style=2).area + 1e-6
