"""Issue #1179: a flat pad never fills a mapped cutting."""
from types import SimpleNamespace as NS

from auto_patch_v2.classify.pad_cut_corridor import CUT_TRIMMED, trim_cut_corridors
from shapely.geometry import box


def _law():
    tn = NS(admitted_values=["yes"], lane_width_m=3.5, default_lanes=2)
    return NS(tables=NS(structures=NS(tunnel=tn)))


def _way(tags):
    return NS(points=[(0.0, -100.0), (0.0, 100.0)], tags=tags)


def _trim(tags):
    ap = NS(osm_ways=[_way(tags)])
    return trim_cut_corridors([box(-50, -50, 50, 50)], ap, _law())


def test_a_cutting_rail_splits_the_pad_along_its_corridor():
    out = _trim({"railway": "rail", "cutting": "yes"})
    assert len(out) == 1 and out[0].geom_type == "MultiPolygon"
    assert abs(out[0].area - (100 * 100 - 7.0 * 100)) < 1e-6
    assert CUT_TRIMMED["parts"] == 1


def test_bridge_bore_and_plain_ways_leave_the_pad_whole():
    for tags in ({"railway": "rail"},
                 {"railway": "rail", "cutting": "no"},
                 {"railway": "rail", "cutting": "yes", "bridge": "yes"},
                 {"highway": "primary", "cutting": "yes", "tunnel": "yes"},
                 {"waterway": "ditch", "cutting": "yes"}):
        out = _trim(tags)
        assert len(out) == 1 and abs(out[0].area - 10000.0) < 1e-6, tags


def test_a_building_passage_in_a_cutting_stays_in_the_pad_for_the_planar_stage():
    """#1333: the cut UNDER a building is the building's lower level
    (``planar/covered_cut``), or trimmed there where none is minted."""
    out = _trim({"railway": "rail", "cutting": "yes",
                 "tunnel": "building_passage"})
    assert abs(out[0].area - 10000.0) < 1e-6
