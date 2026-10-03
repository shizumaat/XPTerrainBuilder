"""Twins for issue #284 (owner sim read 1.0.371, SPJC: "apron shapeID 126
sits inside apron shapeID 32 ... complex jagged shapes although the whole
area is apron"): ONE APRON AREA, ONE PLATEAU.

``planar/pad_cut.plateau_cut`` cut the stand zone of a held block out of
its apron as the union of the rider rectangles and a 30 m disc per stand,
clipped to a span made of one band per frontage segment.  Three artefacts
followed, each an apron face of its own:

1. a stand standing beyond the stand radius of the pad cut a flat ISLAND
   inside the apron (SPJC 126 / 127, ``pav49#plateau:building5/b2``,
   2.8 m off the pad, holes of face 32);
2. the per-segment span left a V notch at every turn of the frontage —
   a hair slit of apron along the plateau's outer edge;
3. neighbouring discs / rectangles ringed small patches of apron — HOLES
   in the plateau, each an apron face (SPJC building5/b0: 19 holes).

The stand zone is now swept to the pad (a plateau TO THE STAND LINE,
RULINGS 2026-09-30y addendum), closed by half the stand radius, hole-
filled, built on one band per held RUN, and only its parts touching the
block stand.
"""
from __future__ import annotations

import pytest
from shapely.geometry import LineString, Point, Polygon

from auto_patch_v2.classify.roles import Classification
from auto_patch_v2.law import Law
from auto_patch_v2.model.airport import Startup
from auto_patch_v2.model.planar import PLATEAU_MARK
from auto_patch_v2.planar.build import build
from auto_patch_v2.planar.pad_cut import _held_span, _stand_zone

from test_flatpad128v3 import _airport, _cells  # noqa: E402

#: the pad edge is y = 180; a 30 m disc round this gate reaches y = 158,
#: so before #284 the stand cut an island 22 m off the pad
FAR_GATE_XY = (0.0, 128.0)


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


@pytest.fixture(scope="module")
def far(law):
    gate = Startup("G1", FAR_GATE_XY, 180.0, "gate")
    pm, _s = build(_airport(law, startups=(gate,)),
                   Classification(tuple(_cells()), (), {}, ()), law)
    from auto_patch_v2.model.platform import PLATEAUS
    return pm, dict(PLATEAUS)


def _keys(pm, f) -> set:
    return {pm.vertices[v].key for r in (f.ring, *f.holes)
            for v in pm.ring_vertices(r)}


def test_a_far_stand_cuts_one_plateau_that_meets_the_pad(far):
    pm, plateaus = far
    assert "padA" in plateaus
    faces = [f for f in pm.faces.values() if PLATEAU_MARK in str(f.ref)]
    assert len(faces) == 1, [(f.id, f.ref) for f in faces]
    collar = set().union(*(_keys(pm, f) for f in pm.faces.values()
                           if str(f.ref).startswith("padA")))
    assert _keys(pm, faces[0]) & collar, "the plateau stands apart from its pad"


def test_no_apron_face_carries_a_plateau_hole_or_sits_in_one(far):
    pm, _p = far
    for f in pm.faces.values():
        if f.role == "apron":
            assert not f.holes, (f.id, f.ref, len(f.holes))


def test_the_span_has_no_notch_at_a_turn_of_the_frontage():
    pts = [(float(x), 0.0) for x in range(0, 101, 10)] + \
          [(100.0, float(y)) for y in range(10, 101, 10)]
    span = _held_span(pts, [False] * len(pts), 30.0)
    assert span.covers(Point(115.0, -15.0)), "the convex turn leaves a V notch"
    # a ramp sample still breaks the span: the ramp is covered by neither
    ramp = [False] * len(pts)
    ramp[5] = True
    cut = _held_span(pts, ramp, 30.0)
    assert not cut.covers(Point(50.0, 10.0))


def test_the_stand_zone_is_closed_hole_free_and_touches_its_block():
    outline = Polygon([(0, 0), (200, 0), (200, 20), (0, 20)])
    # four rectangles ringing a ~20 x 20 patch of apron (a hole)
    parts = [Polygon([(0, 20), (100, 20), (100, 40), (0, 40)]),
             Polygon([(0, 60), (100, 60), (100, 80), (0, 80)]),
             Polygon([(0, 40), (39.5, 40), (39.5, 60), (0, 60)]),
             Polygon([(60, 40), (100, 40), (100, 60), (60, 60)]),
             Point(150.0, 150.0).buffer(10.0)]          # apart from the block
    span = Polygon([(-50, -50), (300, -50), (300, 300), (-50, 300)])
    zone = _stand_zone(parts, 15.0, span, outline, 0.5)
    assert zone is not None
    polys = list(getattr(zone, "geoms", [zone]))
    assert len(polys) == 1, "the part apart from the block was kept"
    assert not polys[0].interiors, "the ringed patch stayed a hole"
    assert zone.covers(Point(50.0, 50.0))
    assert not zone.intersects(Point(150.0, 150.0))
    assert LineString([(20, 20), (80, 20)]).within(zone.buffer(1e-6))
