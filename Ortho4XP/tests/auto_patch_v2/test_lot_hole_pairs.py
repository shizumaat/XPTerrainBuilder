"""OWNER RULINGS 2026-10-04p (C, issue #360): A LOT'S OWN GRADE CAP BINDS
ACROSS ITS HOLES.

``roads.road_within_shape`` paired every cycle of a lot with itself only,
so a hole ring stood coupled to the page it is cut from by no row — HECA
lot ``pav57``'s hole ring round pads ``building19`` / ``building23``
peaked 105.29 m at 30.1156466, 31.4091106, +8.3 m over the lot's outer
ring 4.3 m away.  Each hole-ring vertex now carries the lot's own
longitudinal cap to the nearest outer-ring vertex."""
from __future__ import annotations

import math

import pytest

from auto_patch_v2.classify.roles import Cell, Classification
from auto_patch_v2.constraints.roads import hole_pairs, road_within_shape
from auto_patch_v2.law import Law
from auto_patch_v2.law.tables import role_cap
from auto_patch_v2.model.constraints import Diff
from auto_patch_v2.planar.build import build

from test_roadrows143 import HALF_W, RUN_LEN, _airport, _rect

LOT = (300.0, 100.0, 400.0, 200.0)
HOLE = (340.0, 140.0, 360.0, 160.0)


def test_hole_pairs_takes_the_nearest_outer_vertex():
    xy = {0: (0.0, 0.0), 1: (10.0, 0.0), 2: (10.0, 10.0), 3: (0.0, 10.0),
          4: (2.0, 2.0), 5: (8.0, 8.0)}
    got = hole_pairs(xy, [0, 1, 2, 3], [[4, 5]], 0.01)
    assert [(a, b) for a, b, _d in got] == [(4, 0), (5, 2)]
    assert got[0][2] == pytest.approx(math.hypot(2.0, 2.0))


def test_hole_pairs_skips_a_shared_or_coincident_vertex():
    xy = {0: (0.0, 0.0), 1: (10.0, 0.0), 2: (10.0, 10.0), 3: (0.0, 10.0),
          4: (0.0, 0.001), 5: (5.0, 5.0)}
    got = hole_pairs(xy, [0, 1, 2, 3], [[0, 4, 5]], 0.01)
    assert [(a, b) for a, b, _d in got] == [(5, 0)]
    assert hole_pairs(xy, [], [[4, 5]], 0.01) == []


@pytest.fixture(scope="module")
def built():
    law = Law.for_airport("ZZZZ")
    cells = [
        Cell(0, "runway", "09/27",
             _rect(-RUN_LEN / 2, -HALF_W, RUN_LEN / 2, HALF_W),
             (), 3, "C", "airside", "runway", {}),
        Cell(1, "parking_lot", "lotA", _rect(*LOT), (_rect(*HOLE),),
             None, None, "groundside", "lot", {}),
    ]
    airport = _airport(law)
    pm, _st = build(airport, Classification(tuple(cells), (), {}, ()), law)
    return law, airport, pm


def test_every_hole_vertex_of_a_lot_is_capped_to_its_outer_ring(built):
    law, airport, pm = built
    lot = next(f for f in pm.faces.values() if f.role == "parking_lot")
    assert lot.holes, "the fixture lot lost its hole"
    outer = set(pm.ring_vertices(lot.ring))
    hole = {v for h in lot.holes for v in pm.ring_vertices(h)} - outer
    assert hole
    cap = role_cap(law, "parking_lot").longitudinal
    rows = [r for r in road_within_shape(pm, law, airport)
            if isinstance(r, Diff) and "hole" in r.source.inputs]
    bound = {}
    for r in rows:
        a, b = (r.a, r.b) if r.a in hole else (r.b, r.a)
        assert a in hole and b in outer
        assert r.cap == pytest.approx(cap) and r.follows is None
        assert r.d == pytest.approx(math.dist(pm.vertices[a].xy,
                                              pm.vertices[b].xy))
        bound[a] = b
    assert set(bound) == hole
    for v, u in bound.items():
        dmin = min(math.dist(pm.vertices[v].xy, pm.vertices[q].xy)
                   for q in outer)
        assert math.dist(pm.vertices[v].xy, pm.vertices[u].xy) \
            == pytest.approx(dmin)
