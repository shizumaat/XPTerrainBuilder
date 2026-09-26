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


# ── #6 THE FALLBACK PAD NEVER STANDS UNDER A CLUSTER PAD ────────────────

def _pads_of(clusters, footprints):
    from shapely.geometry import Polygon as _P

    from auto_patch_v2.classify.evidence import _pads
    from auto_patch_v2.law import Law
    from test_v2padcluster import _AP, _armed

    class _R:
        class buildings:
            sources = ("osm",)

    class _B:
        def __init__(self, outer):
            self.source, self.outer, self.holes = "osm", outer, ()

    law = _armed(Law.for_airport("ZZZZ"))
    ap = _AP(clusters, buildings=tuple(_B(r) for r in footprints))
    gate = _P([(-500.0, -500.0), (-500.0, 500.0), (500.0, 500.0),
               (500.0, -500.0)])
    none = _P()
    pads, _d, _s = _pads(ap, _R, 50.0, gate, none, none, law=law)
    return [(r, g) for r, g in pads]


def _overlaps(pads):
    out = 0.0
    for i, (_ri, a) in enumerate(pads):
        for _rj, b in pads[i + 1:]:
            out += a.intersection(b).area
    return out


def test_a_fallback_footprint_never_stands_under_a_cluster_pad():
    """HECA-1 (#6): the concrete slab's footprint-cache pad (9,605 m2) was
    admitted WHOLE under the 50 % bar while 2,281 m2 of it lay under the
    T3_20 cluster pad — two pads on one ground, read by the owner as a
    building20 inside a building20.  The cluster pad owns its ground."""
    from test_v2padcluster import _Cl, _sq
    cl = _Cl("unit:0#0", [_sq(0.0, 0.0, 100.0, 100.0)], area=10000.0)
    # a footprint 40 % under the cluster pad, the rest beside it
    slab = ((20.0, 60.0), (80.0, 60.0), (80.0, 160.0), (20.0, 160.0))
    pads = _pads_of([cl], [slab])
    assert len(pads) == 2, pads
    assert _overlaps(pads) < 1e-6
    fb = [g for r, g in pads if g.area < 9000.0][0]
    assert abs(fb.area - 60.0 * 60.0) < 1.0      # only the ground no cluster covers


def test_a_fallback_remnant_enclosed_by_a_cluster_pad_is_absorbed():
    """...and where what is left of the fallback lies inside the cluster
    pad's own outline (a courtyard it half-fills), it is not a second
    building nested in the first: it joins the pad that encloses it."""
    from test_v2padcluster import _Cl, _sq
    # a U-shaped cluster: 100 x 100 with a 40 x 60 notch open to the north
    # (the notch closed below by the cluster's rings: three blocks)
    rings = [_sq(0.0, 0.0, 30.0, 100.0), _sq(70.0, 0.0, 100.0, 100.0),
             _sq(30.0, 0.0, 70.0, 40.0)]
    cl = _Cl("unit:0#0", rings, area=7600.0)
    # a courtyard slab whose footprint also covers part of the U's arms
    slab = ((20.0, 30.0), (80.0, 30.0), (80.0, 90.0), (20.0, 90.0))
    pads = _pads_of([cl], [slab])
    assert _overlaps(pads) < 1e-6
    # the courtyard remnant is NOT enclosed by the U's EXTERIOR (the notch
    # is open to the north), so it stands as its own pad beside it
    assert len(pads) == 2, [(r, round(g.area)) for r, g in pads]
    # now close the U: a ring of four blocks with a 40 x 40 hole
    rings = [_sq(0.0, 0.0, 30.0, 100.0), _sq(70.0, 0.0, 100.0, 100.0),
             _sq(30.0, 0.0, 70.0, 30.0), _sq(30.0, 70.0, 70.0, 100.0)]
    cl = _Cl("unit:0#0", rings, area=8400.0)
    # a slab over the courtyard and a 5 m margin of the ring (36 % under it)
    slab = ((25.0, 25.0), (75.0, 25.0), (75.0, 75.0), (25.0, 75.0))
    pads = _pads_of([cl], [slab])
    assert len(pads) == 1, [(r, round(g.area)) for r, g in pads]
    assert abs(pads[0][1].area - 10000.0) < 1.0   # the hole is filled
    assert not pads[0][1].interiors
