"""Twin for #1917 (owner RULINGS 2026-11-06c (5): "the ramp depth and width
should be set based on the mouth object"; ``planar/mouth_opening``,
``planar/entrance_skirt.face_front_mouth``): a mouth object's ramp spans its
opening EDGE TO EDGE wherever the mapped road runs in it, and runs in to
where the face stands DEEPEST across it, so no cut ground stands in front of
any part of the opening.  MEASURED LOWS west mouth (1.0.474): the
carriageways' midline 1.5 m off the opening's middle, the face skewed 1.8 m
across it.  Synthetic bore and DEM; law values read from the tables."""
from __future__ import annotations

import dataclasses as _dc

import pytest
from auto_patch_v2.airport.portal_objects import Portal, opening_span
from auto_patch_v2.classify.roles import Classification
from auto_patch_v2.law import Law
from auto_patch_v2.planar.entrance_skirt import face_front_mouth
from auto_patch_v2.planar.mouth_opening import opening_halves
from auto_patch_v2.planar.structures import build_structures
from shapely.geometry import LineString, Polygon, box
from shapely.ops import unary_union
from test_mouth_at_pavement971 import _airport as _bore_airport
from test_mouth_at_pavement971 import _base_cells, _FlatDem

#: the east mouth's axis (mapped end x = 60, ramp running out to +x)
_AXIS = LineString([(60.0, 0.0), (300.0, 0.0)])
#: its opening: 20 m between its walls, the road 6 m off its middle
_EDGES = ((60.0, 16.0), (60.0, -4.0))
#: a face top skewed across the bore: its front 2 m nearer the end at y = -4
_SKEWED = Polygon([(58.0, -6.0), (56.0, 18.0), (50.0, 18.0), (50.0, -6.0)])


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


def test_the_ramp_spans_the_opening_about_its_axis():
    """The halves are the edges' offsets from the axis (left = +y for an
    axis running +x); an axis outside the opening keeps the symmetric width."""
    assert opening_halves(_AXIS, _EDGES) == pytest.approx((16.0, 4.0))
    assert opening_halves(_AXIS, ((60.0, 4.0), (60.0, 24.0))) is None
    assert opening_halves(_AXIS, ()) is None


def test_the_opening_span_is_read_across_the_bore():
    width, edges = opening_span(-4.8, 15.7, (0.0, 0.0), (1.0, 0.0))
    assert width == pytest.approx(20.5)
    assert [tuple(e) for e in edges] == [pytest.approx((0.0, -4.8)), pytest.approx((0.0, 15.7))]
    assert opening_span(3.0, 3.0, (0.0, 0.0), (1.0, 0.0)) == (0.0, ())


def test_the_mouth_runs_in_to_the_deepest_front_of_a_skewed_face():
    """Its nearest corner (x = 57.8 at y = -4) left 1.8 m of cut ground in
    front of the far side; the mouth now stands at the far side's front (its
    last line 0.25 m inside the edge: x = 58 - 21.75 / 12)."""
    ln, moved = face_front_mouth(_AXIS, (-1.0, 0.0), _SKEWED, (16.0, 4.0))
    assert moved == pytest.approx(60.0 - (58.0 - 21.75 / 12.0))
    assert ln.coords[0][0] == pytest.approx(60.0 - moved)
    # a face square to the bore keeps its one front, whatever the span
    ln, moved = face_front_mouth(_AXIS, (-1.0, 0.0), box(50.0, -14.0, 56.0, 14.0), 6.0)
    assert moved == pytest.approx(4.0) and ln.coords[0] == pytest.approx((56.0, 0.0))


def _pins():
    """Both mouths' entrance faces; the east one off-centre and skewed."""
    west = Portal("dsf:obj1", "objects/entrance.obj", (-60.0, 0.0), -101, 6.0, 0.0,
                  (-60.0, 0.0), floor_z=694.5, opening_m=12.0, bottom_y=-5.0,
                  face_plan=box(-66.0, -14.0, -60.0, 14.0), face_top_z=700.0)
    east = Portal("dsf:obj2", "objects/entrance.obj", (60.0, 0.0), -101, 6.0, 0.0,
                  (60.0, 0.0), floor_z=694.5, opening_m=20.0, opening_xy=_EDGES,
                  bottom_y=-5.0, face_plan=_SKEWED, face_top_z=700.0)
    return [west, east]


def test_the_built_ramp_covers_the_opening_up_to_the_face(law):
    airport = _dc.replace(_bore_airport(law), dem=_FlatDem())
    cl, tunnels, st = build_structures(airport, Classification(tuple(_base_cells()), (), {}, ()),
                                       law, portals=_pins())
    assert len(tunnels) == 2, st.refused
    ramp = unary_union([Polygon(c.ring, c.holes) for c in cl.cells
                        if c.role == "tunnel_ramp" and min(p[0] for p in c.ring) > 0.0])
    x0, y0, _x1, y1 = ramp.bounds
    # edge to edge across the opening (the edges snap outward)
    assert y0 <= -4.0 + 1e-6 and y1 >= 16.0 - 1e-6 and y1 - y0 <= 20.0 + 2.0
    # in to the face's deepest front (x = 56.2 at y = +15.75), not its nearest corner
    assert x0 == pytest.approx(56.0, abs=0.6)
