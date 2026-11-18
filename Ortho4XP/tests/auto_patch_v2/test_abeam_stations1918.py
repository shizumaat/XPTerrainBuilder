"""#1918 R3 (LGAV 37.927345, 23.934221): a road kerb vertex has its
opposite (``planar/chords.abeam_stations``).  MEASURED: building24's pad
tip stood 0.4-1.3 m from ONE 31 m chord of ``small_roads:-886`` with no
vertex opposite it, so ``road_within_shape`` (vertex pairs only) never
priced the 0.7-1.0 m step across the road.  The twin is that notch."""
from __future__ import annotations

from auto_patch_v2.planar.chords import abeam_stations
from shapely.geometry import Point, Polygon


def _road(notch):
    """A 30 m road, 7 m wide (its kerbs farther apart than one ribbon),
    whose north kerb carries ``notch`` (pad-tip vertices); the south kerb
    is ONE chord (0,0)-(30,0)."""
    return [(0.0, 0.0), (30.0, 0.0), (30.0, 7.0), *notch, (0.0, 7.0), (0.0, 0.0)]


def _new(ring, out):
    return [p for p in out if p not in ring]


def test_a_pad_corner_by_a_long_chord_gains_one_station():
    ring = _road([(16.0, 7.0), (15.0, 1.3), (14.0, 7.0)])
    out = abeam_stations(ring, 6.0, 0.5)
    assert _new(ring, out) == [(15.0, 0.0)]
    assert out.index((15.0, 0.0)) == 1                     # on the chord it splits


def test_two_feet_closer_than_the_gap_give_one():
    ring = _road([(16.0, 7.0), (15.2, 1.3), (14.9, 1.5), (14.0, 7.0)])
    new = _new(ring, abeam_stations(ring, 6.0, 0.5))
    assert len(new) == 1                                   # the nearer vertex wins
    assert abs(new[0][0] - 15.2) < 1e-9 and new[0][1] == 0.0


def test_a_foot_outside_the_polygon_gives_none():
    # a U: the inner vertex (8,6) of the west arm faces the east arm's
    # inner chord (12,2)-(12,10) 4 m away ACROSS the gap between the arms
    ring = [(0.0, -1.0), (20.0, -1.0), (20.0, 10.0), (12.0, 10.0), (12.0, 2.0),
            (8.0, 2.0), (8.0, 6.0), (8.0, 10.0), (0.0, 10.0), (0.0, -1.0)]
    out = abeam_stations(ring, 6.0, 0.5)
    assert (12.0, 6.0) not in out
    assert (8.0, -1.0) in out and (12.0, -1.0) in out     # across the face: minted


def test_a_foot_on_a_contact_rim_gives_none():
    ring = _road([(16.0, 7.0), (15.0, 1.3), (14.0, 7.0)])
    apron = Polygon([(12.0, -10.0), (18.0, -10.0), (18.0, 0.0), (12.0, 0.0)])
    out = abeam_stations(ring, 6.0, 0.5,
                         keep_off=lambda p: apron.distance(Point(p)) <= 0.36)
    assert out == ring


def test_a_ring_with_opposite_vertices_gains_nothing():
    ring = [(0.0, 0.0), (10.0, 0.0), (20.0, 0.0), (20.0, 5.0), (10.0, 5.0),
            (0.0, 5.0), (0.0, 0.0)]
    assert abeam_stations(ring, 6.0, 0.5) == ring


def test_a_vertex_beyond_one_ribbon_gains_nothing():
    ring = [(0.0, 0.0), (30.0, 0.0), (30.0, 9.0), (15.0, 7.0), (0.0, 9.0), (0.0, 0.0)]
    assert abeam_stations(ring, 6.0, 0.5) == ring
