"""Free-road scoping of the service slice set — owner ruling 2026-07-27.

"Any road inside, or sharing an edge with an apron must be graded the
same as the apron, so essentially just becomes part of the apron and
never needs to be carved in the first place.  We only want completely
free roads, with no pavement on either side of road-width pavement, to
be graded as roads."

``groundside.free_road_subsegments`` implements the slice-side half of
the ruling; ``carve_narrow_service_strips`` keys the strip carve on the
SAME per-station measurement (``_svc_contiguous_width``), so the two
cannot drift.

Hermetic: hand-built geometry, no fixtures, no DEM, no network.
"""
from shapely.geometry import LineString, Polygon

from auto_patch.groundside import (
    _svc_contiguous_width, free_road_subsegments)


# A 400 m x 200 m apron and, east of it, a free-standing 10 m road
# ribbon crossing open terrain.
_APRON = Polygon([(0, -100), (400, -100), (400, 100), (0, 100)])
_RIBBON = Polygon([(500, -5), (900, -5), (900, 5), (500, 5)])
_PAV = _APRON.union(_RIBBON)


def test_a_road_through_the_apron_is_not_free():
    """The through-apron span (cross-section 200 m) never reaches the
    slice — it IS the apron."""
    road = LineString([(50, 0), (350, 0)])
    assert free_road_subsegments([road], _PAV) == []


def test_a_road_hugging_the_apron_edge_is_not_free():
    """Edge-sharing: a road just inside the apron's south edge still
    measures the apron's full cross-section — part of the apron."""
    road = LineString([(50, -95), (350, -95)])
    assert free_road_subsegments([road], _PAV) == []


def test_a_road_width_ribbon_is_free():
    """Pavement that is nothing but the road grades as a road."""
    road = LineString([(510, 0), (890, 0)])
    segs = free_road_subsegments([road], _PAV)
    assert len(segs) == 1
    assert segs[0].length > 350.0


def test_a_mixed_route_keeps_only_its_free_span():
    """One 1206 route running apron → open ribbon: only the ribbon span
    survives; the apron span is dropped whole."""
    road = LineString([(50, 0), (890, 0)])
    segs = free_road_subsegments([road], _PAV)
    assert len(segs) == 1
    (x0, _y0) = segs[0].coords[0]
    (x1, _y1) = segs[0].coords[-1]
    assert min(x0, x1) >= 395.0, "the apron span must not be carved"
    assert max(x0, x1) > 850.0


def test_off_pavement_roads_pass_through_unfiltered():
    road = LineString([(0, 500), (400, 500)])
    segs = free_road_subsegments([road], _PAV)
    assert len(segs) == 1


def test_the_carve_and_the_filter_share_one_measurement():
    """Lockstep: the width the filter keys on IS the carve's width."""
    road = LineString([(510, 0), (890, 0)])
    w = _svc_contiguous_width(road, road.length / 2.0, _PAV)
    assert w is not None and 8.0 <= w <= 12.0
    w_apron = _svc_contiguous_width(
        LineString([(50, 0), (350, 0)]), 150.0, _PAV)
    assert w_apron is not None and w_apron > 100.0
