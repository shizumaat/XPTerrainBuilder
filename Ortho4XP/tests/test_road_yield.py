"""The steep-ground yield of the core's levelled road ribbons (LPPD
2026-11-18): a span whose bench would stand more than ROAD_BENCH_MAX_M off
its own ground within one lane leaves the banked network."""
import math

import numpy
import O4_Road_Yield as RY
import O4_Vector_Utils as VECT
import pytest
from shapely import geometry

LANE = 4.0
M = 1.0 / 111195.0           # one metre of latitude, in degrees
EDGE_Y = 0.5                 # the cliff edge runs east-west at this y


@pytest.fixture(autouse=True)
def _scalx(monkeypatch):
    monkeypatch.setattr(VECT, "scalx", math.cos(math.radians(37.5)))


def _alt_vec(pts):
    """A 20 m bluff: 20 m south of EDGE_Y, 40 m north, over ~2 m."""
    y = numpy.asarray(pts, float)[:, 1]
    return 20.0 + 20.0 / (1.0 + numpy.exp(-(y - EDGE_Y) / M))


def _east(y, x0=0.40, x1=0.402):
    return geometry.LineString([(x0, y), (x1, y)])


def test_a_road_on_the_bluff_edge_yields_and_one_inland_does_not():
    edge, inland = _east(EDGE_Y), _east(EDGE_Y + 100 * M)
    net = geometry.MultiLineString([edge, inland])
    kept, classes, ids, report = RY.yield_steep_spans(
        net, _alt_vec, LANE, way_classes=["unclassified", "residential"],
        way_ids=[-1, -2])
    assert report["ways"] == 1 and report["spans"] == 1
    assert report["worst_relief_m"] > 9.0
    assert list(kept.geoms) == [inland]
    assert classes == ["residential"] and ids == [-2]


def test_a_road_crossing_the_bluff_keeps_its_two_ends_with_its_class():
    road = geometry.LineString([(0.4, EDGE_Y - 150 * M),
                                (0.4, EDGE_Y + 150 * M)])
    kept, classes, ids, report = RY.yield_steep_spans(
        geometry.MultiLineString([road]), _alt_vec, LANE,
        way_classes=["service"], way_ids=[-7])
    assert report["ways"] == 1 and len(kept.geoms) == 2
    assert classes == ["service", "service"] and ids == [-7, -7]
    for piece in kept.geoms:      # no kept piece reaches the face
        ys = numpy.array(piece.coords)[:, 1]
        assert numpy.abs(ys - EDGE_Y).min() > LANE * M
    assert report["yielded_m"] == pytest.approx(
        300.0 - sum(VECT.length_in_meters(g) for g in kept.geoms), abs=1.0)


def test_the_band_the_clamp_owns_is_never_yielded():
    edge = _east(EDGE_Y)
    band = edge.buffer(10 * M)
    kept, _c, _i, report = RY.yield_steep_spans(
        geometry.MultiLineString([edge]), _alt_vec, LANE, exempt=band)
    assert report["ways"] == 0 and list(kept.geoms) == [edge]


def test_a_low_bench_stays_levelled():
    def gentle(pts):        # 50 % cross-fall: 2 m over a lane
        return 30.0 + 0.5 * (numpy.asarray(pts, float)[:, 1] / M)
    road = _east(EDGE_Y)
    kept, _c, _i, report = RY.yield_steep_spans(
        geometry.MultiLineString([road]), gentle, LANE)
    assert report["ways"] == 0 and kept.geoms[0].equals(road)
