"""Twin for ``tools/inset_coverage_census.py``.

The census is how a staleness RULE gets chosen, and a rule that re-cuts
insets moves the terrain every airport is graded against.  So the two
things that must never drift are pinned here: that the tool's box
arithmetic IS the engine's (``_airport_bounding_boxes``), and that its
verdicts key on the right box with the right tolerance.  Everything runs
on a synthetic corpus; the tool never writes, and the empty-corpus run
proves it touches nothing it was pointed at.
"""

import os
import sys

import pytest

sys.path.insert(
    0,
    os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                 "tools"),
)

import O4_Airport_Elevation_Insets as INSETS          # noqa: E402
import O4_Geo_Utils as GEO                            # noqa: E402
import inset_coverage_census as CENSUS                # noqa: E402


class _Tile:
    def __init__(self, lat, lon, margin_m=2000.0):
        self.lat = lat
        self.lon = lon
        self.airport_elevation_inset_margin_m = margin_m


def _record(**overrides):
    """A synthetic census record: a 0.01 deg boundary at tile +35-087."""
    boundary = (-86.95, 35.45, -86.94, 35.46)
    record = {
        "tile_stem": "N35W087", "lat": 35, "lon": -87, "mid_latitude": 35.5,
        "name": "KTST_usgs3dep.tif", "path": "/nowhere/KTST_usgs3dep.tif",
        "airport": "KTST", "provider": "usgs3dep",
        "boundary_box": boundary,
        "requested_box": CENSUS.expand_box(boundary, 2000.0, 35.5),
        "delivered_box": CENSUS.expand_box(boundary, 2000.0, 35.5),
        "pixel_lon": 1e-5, "pixel_lat": 1e-5,
        "configured_margin_m": 2000.0,
    }
    record.update(overrides)
    return record


# =====================================================================
# The arithmetic IS the engine's
# =====================================================================
def test_expand_box_reproduces_the_engines_required_box():
    """THE ANTI-DRIFT ASSERTION.  If ``_airport_bounding_boxes`` ever
    changes its margin conversion, this fails rather than the census
    quietly reporting against a box the engine does not use."""
    from shapely import geometry as shapely_geometry

    tile = _Tile(35, -87, margin_m=2000.0)
    # dico geometry is TILE-RELATIVE degrees; the census works in
    # absolute degrees, so the boundary below is the same polygon.
    dico = {"KTST": {"boundary": shapely_geometry.box(0.05, 0.45,
                                                      0.06, 0.46)}}
    engine = INSETS._airport_bounding_boxes(tile, dico)["KTST"]
    mine = CENSUS.expand_box((-86.95, 35.45, -86.94, 35.46), 2000.0, 35.5)
    for (theirs, ours) in zip(engine, mine):
        assert theirs == pytest.approx(ours, abs=1e-12)


def test_expand_box_is_true_metres_on_both_axes():
    box = CENSUS.expand_box((0.0, 45.0, 0.0, 45.0), 1000.0, 45.0)
    assert (box[3] - 45.0) * GEO.lat_to_m == pytest.approx(1000.0, abs=1e-6)
    assert (box[2] - 0.0) * GEO.lon_to_m(45.0) == pytest.approx(1000.0,
                                                               abs=1e-6)


def test_edge_shortfalls_are_positive_only_when_ground_is_uncovered():
    required = (-1.0, -1.0, 1.0, 1.0)
    # A covering box inset by ~1 km on the east edge only.
    short = CENSUS.edge_shortfalls_m(
        required, (-1.0, -1.0, 1.0 - 1000.0 / GEO.lon_to_m(0.0), 1.0), 0.0)
    assert short["east"] == pytest.approx(1000.0, abs=1e-3)
    assert short["west"] <= 0.0 and short["north"] <= 0.0
    # A SUPERSET is never a defect: every edge reads negative.
    generous = CENSUS.edge_shortfalls_m(required, (-2.0, -2.0, 2.0, 2.0), 0.0)
    assert all(value < 0 for value in generous.values())


def test_containment_tolerance_is_per_axis():
    required = (-1.0, -1.0, 1.0, 1.0)
    covering = (-1.0, -1.0, 1.0 - 5e-6, 1.0)      # 5e-6 deg short in LON
    assert CENSUS.fails_to_contain(required, covering, 1e-6, 1e-2) is True
    assert CENSUS.fails_to_contain(required, covering, 1e-5, 1e-6) is False
    # A latitude pixel must not excuse a longitude shortfall, which a
    # single scalar tolerance would do on a non-square pixel.
    assert CENSUS.fails_to_contain(required, covering, 1e-6, 1.0) is True


def test_tile_stem_parsing_covers_all_four_hemispheres():
    assert CENSUS.tile_of_stem("N35W087") == (35, -87)
    assert CENSUS.tile_of_stem("S13W078") == (-13, -78)
    assert CENSUS.tile_of_stem("N51E001") == (51, 1)
    assert CENSUS.tile_of_stem("S46E168") == (-46, 168)


# =====================================================================
# The verdicts
# =====================================================================
def test_sweep_judges_the_delivered_box_not_the_request():
    """A raster whose REQUEST was generous but whose delivery is 300 m
    short is stale at m_min 500 and fine at m_min 250 -- the whole point
    of a functional margin."""
    boundary = (-86.95, 35.45, -86.94, 35.46)
    delivered = CENSUS.expand_box(boundary, 300.0, 35.5)
    record = _record(delivered_box=delivered,
                     requested_box=CENSUS.expand_box(boundary, 2000.0, 35.5))
    assert CENSUS._stale_at(record, 250.0)[0] is False
    assert CENSUS._stale_at(record, 500.0)[0] is True
    shortfalls = CENSUS._stale_at(record, 500.0)[1]
    assert shortfalls["north"] == pytest.approx(200.0, abs=1.0)
    # An unreadable raster is never judged, never guessed.
    assert CENSUS._stale_at(_record(delivered_box=None), 500.0) == (None, None)


def test_sweep_tolerance_is_one_delivered_pixel():
    boundary = (-86.95, 35.45, -86.94, 35.46)
    # Exactly one 30 m pixel short of boundary + 500 m.
    pixel_lat = 30.0 / GEO.lat_to_m
    pixel_lon = 30.0 / GEO.lon_to_m(35.5)
    required = CENSUS.expand_box(boundary, 500.0, 35.5)
    delivered = (required[0] + pixel_lon * 0.9, required[1] + pixel_lat * 0.9,
                 required[2] - pixel_lon * 0.9, required[3] - pixel_lat * 0.9)
    record = _record(delivered_box=delivered, pixel_lon=pixel_lon,
                     pixel_lat=pixel_lat)
    assert CENSUS._stale_at(record, 500.0)[0] is False
    # Two pixels short is not rounding any more.
    record["delivered_box"] = (
        required[0] + pixel_lon * 2.1, required[1] + pixel_lat * 2.1,
        required[2] - pixel_lon * 2.1, required[3] - pixel_lat * 2.1)
    assert CENSUS._stale_at(record, 500.0)[0] is True


def test_cause_classification_separates_a_margin_change_from_a_boundary_move():
    boundary = (-86.95, 35.45, -86.94, 35.46)
    # Cut under a 1000 m margin while 2000 m is configured: all four
    # edges are short by the same 1000 m.
    margin_change = _record(
        requested_box=CENSUS.expand_box(boundary, 1000.0, 35.5))
    (cause, deficits) = CENSUS.classify_cause(margin_change)
    assert cause == "margin setting"
    assert all(value == pytest.approx(1000.0, abs=0.01)
               for value in deficits.values())
    # The boundary grew 50 m eastward since the cut: ONE edge moved.
    grown = (-86.95, 35.45, -86.94 + 50.0 / GEO.lon_to_m(35.5), 35.46)
    boundary_move = _record(
        boundary_box=grown,
        requested_box=CENSUS.expand_box(boundary, 2000.0, 35.5))
    (cause, deficits) = CENSUS.classify_cause(boundary_move)
    assert cause == "boundary moved >= 10 m"
    assert deficits["east"] == pytest.approx(50.0, abs=0.1)
    assert deficits["west"] == pytest.approx(0.0, abs=0.01)
    # Sub-metre movement is still a real input change, bucketed as such.
    nudged = (-86.95, 35.45, -86.94 + 0.4 / GEO.lon_to_m(35.5), 35.46)
    (cause, _deficits) = CENSUS.classify_cause(_record(
        boundary_box=nudged,
        requested_box=CENSUS.expand_box(boundary, 2000.0, 35.5)))
    assert cause == "boundary moved < 1 m"


def test_sections_run_over_synthetic_records_and_write_nothing(tmp_path):
    boundary = (-86.95, 35.45, -86.94, 35.46)
    records = [
        _record(),
        _record(name="KSHY_copernicusglo30.tif", airport="KSHY",
                provider="copernicusglo30",
                delivered_box=CENSUS.expand_box(boundary, 300.0, 35.5),
                pixel_lon=30.0 / GEO.lon_to_m(35.5),
                pixel_lat=30.0 / GEO.lat_to_m),
    ]
    lines = []
    CENSUS.section_sweep(records, [0, 500, 2000], 500, out=lines.append)
    CENSUS.section_battery(records, ["KSHY"], out=lines.append)
    CENSUS.section_delivery(records, out=lines.append)
    CENSUS.section_shipped(records, 500.0, out=lines.append)
    text = "\n".join(lines)
    assert "KSHY_copernicusglo30.tif" in text
    assert "SWEEP" in text and "BATTERY" in text and "SHIPPED" in text
    assert os.listdir(tmp_path) == []


def test_an_empty_corpus_yields_no_records_and_no_writes(tmp_path):
    elevation = tmp_path / "Elevation_data"
    elevation.mkdir()
    lines = []
    (records, skipped) = CENSUS.collect_records(str(elevation),
                                                out=lines.append)
    assert records == []
    assert skipped["no_airports_layer"] == []
    assert list(elevation.iterdir()) == []
