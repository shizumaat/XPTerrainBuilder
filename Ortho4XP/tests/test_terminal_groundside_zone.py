"""Terminal groundside-zone classification — the UNKNOWN-edge contract.

Owner report 2026-07-27 (SPJC building81 / HECA): the zone classifier's
"any-airside promotion" turned every UNKNOWN edge of a partly mapped
terminal into a 100 m groundside stamp — at SPJC's new east terminal 78
UNKNOWN edges carved ~190 k m² of REAL apron (the terminal sits between
the runways; both faces are airside).  The docstring's contract — an
edge with NO indicator defaults to airside, never subtracted — is now
enforced by these tests, together with the positive-evidence path that
replaces the promotion: road-class ways from the airport-region ROAD
FEED join the groundside catalog.

Hermetic: hand-built geometry, identity projection, no fixtures, no DEM,
no network.
"""
from shapely.geometry import Point, Polygon

from auto_patch.terminals import _terminal_groundside_zone


def _to_m(lon, lat):
    """Identity 'projection': tests author coordinates in meters and
    store them as (lat, lon) = (y, x) in the node dict."""
    return (lon, lat)


# One 100 x 100 m terminal at the origin.
_BLDG = Polygon([(0.0, 0.0), (100.0, 0.0), (100.0, 100.0), (0.0, 100.0)])

# An aeroway=taxiway line 10 m west of the building (airside indicator
# for the WEST edge), and a highway=service road 10 m east of it
# (groundside indicator for the EAST edge).  North/south stay unmapped.
_NODES = {
    "a1": (-10.0, -110.0), "a2": (110.0, -110.0),     # (lat=y, lon=x)
    "r1": (-10.0, 110.0), "r2": (110.0, 110.0),
}
_TAXIWAY = ("w_air", ["a1", "a2"], {"aeroway": "taxiway"})
_ROAD = ("w_road", ["r1", "r2"], {"highway": "service"})


def _zone(ways, **kw):
    return _terminal_groundside_zone(
        [_BLDG], dict(_NODES), list(ways), _to_m, **kw)


def test_road_backed_edge_subtracts_and_unknown_does_not():
    """Only the EAST edge (positive road evidence) grows a zone; the
    unmapped north/south edges stay airside even though the building has
    airside evidence on the west — the SPJC/HECA regression class."""
    zone = _zone([_TAXIWAY, _ROAD])
    assert zone is not None and not zone.is_empty
    assert zone.covers(Point(150.0, 50.0)), "east curbside must subtract"
    assert not zone.intersects(Point(-50.0, 50.0)), "west is airside"
    assert not zone.intersects(Point(50.0, 160.0)), \
        "north is UNKNOWN — never subtracted"
    assert not zone.intersects(Point(50.0, -60.0)), \
        "south is UNKNOWN — never subtracted"


def test_unknown_edges_alone_produce_no_zone():
    """Airside-only mapping (the sparse-OSM airport): nothing subtracts,
    no matter how many edges are un-taggable."""
    assert _zone([_TAXIWAY]) is None


def test_no_evidence_at_all_is_conservative():
    assert _zone([]) is None


def test_road_feed_ways_are_groundside_evidence():
    """The airport-region road feed replaces the deleted promotion: a
    feed way with a road-class highway tag fires the groundside
    indicator exactly like an extract way."""
    feed_nodes = {"f1": (-10.0, 110.0), "f2": (110.0, 110.0)}
    feed_ways = [("f_road", ["f1", "f2"], {"highway": "unclassified"})]
    zone = _zone([_TAXIWAY], road_ways=feed_ways, road_nodes=feed_nodes)
    assert zone is not None and zone.covers(Point(150.0, 50.0))
    assert not zone.intersects(Point(50.0, 160.0))


def test_feed_ways_without_road_class_are_ignored():
    feed_nodes = {"f1": (-10.0, 110.0), "f2": (110.0, 110.0)}
    feed_ways = [("f_path", ["f1", "f2"], {"highway": "footway"})]
    assert _zone([_TAXIWAY], road_ways=feed_ways,
                 road_nodes=feed_nodes) is None


def test_airside_evidence_beats_a_road_on_the_same_edge():
    """An edge with BOTH indicators stays airside (a service road ON the
    apron along the terminal face — the R-VETO philosophy)."""
    both = [
        _TAXIWAY, _ROAD,
        ("w_air_e", ["r1", "r2"], {"aeroway": "apron"}),
    ]
    zone = _zone(both)
    assert zone is None or not zone.intersects(Point(150.0, 50.0))
