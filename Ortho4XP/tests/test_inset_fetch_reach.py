"""Twin of the inset fetch box (owner RULINGS 2026-10-26t, #1330): the box
is the aerodrome boundary plus the GRADED REACH, and that reach is at or
above what the law tables let any runway grade beyond its pavement."""
import types

import O4_Airport_Elevation_Insets as INSETS
from auto_patch_v2.law import Law
from auto_patch_v2.law.model import load_tables
from auto_patch_v2.law.tables import (
    DEFAULT_LAW_DIR,
    runway_safety_area_length_m,
)


def test_the_graded_reach_covers_every_safety_area_the_law_states():
    tables = load_tables(DEFAULT_LAW_DIR)
    reach = 0.0
    for ruleset in ("icao", "faa"):
        law = Law(tables=tables, ruleset_key=ruleset)
        for code in (1, 2, 3, 4):
            for letter in "ABCDEF":
                for status in (0, 1, 2):
                    reach = max(reach, runway_safety_area_length_m(
                        law, code, letter, status))
    assert reach >= 300.0  # the tables were read, not defaulted
    assert INSETS.INSET_GRADED_REACH_M >= reach


def test_the_fetch_margin_is_the_reach_capped_by_the_setting():
    tile = types.SimpleNamespace(airport_elevation_inset_margin_m=2000.0,
                                 airport_elevation_inset_feather_m=60.0)
    expected = (INSETS.INSET_GRADED_REACH_M + 60.0
                + INSETS.INSET_FETCH_PAD_M)
    assert INSETS.inset_fetch_margin_m(tile) == expected < 2000.0
    tile.airport_elevation_inset_margin_m = 250.0
    assert INSETS.inset_fetch_margin_m(tile) == 250.0
    # the WARN rule judges what the box is now cut to
    assert INSETS.INSET_FUNCTIONAL_MARGIN_M <= expected


def test_the_box_every_inset_reader_shares_is_the_trimmed_one():
    from shapely.geometry import box as _box

    tile = types.SimpleNamespace(lat=55, lon=-4,
                                 airport_elevation_inset_margin_m=2000.0,
                                 airport_elevation_inset_feather_m=60.0)
    dico = {"TEST": {"boundary": _box(0.6, 0.9, 0.65, 0.93)}}
    trimmed = INSETS._airport_bounding_boxes(tile, dico)["TEST"]
    wide = INSETS._airport_bounding_boxes(tile, dico, margin_m=2000.0)["TEST"]
    margin_deg = INSETS.inset_fetch_margin_m(tile) / INSETS.GEO.lat_to_m
    assert abs((0.9 + 55) - trimmed[1] - margin_deg) < 1e-9
    assert wide[1] < trimmed[1] and wide[3] > trimmed[3]
