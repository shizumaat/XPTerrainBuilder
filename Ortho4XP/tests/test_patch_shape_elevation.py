"""Twin of ``Tests/SceneryKitTests/PatchShapeElevationTests.swift`` (issue
#1357): "Set elevation…" on selected shapes sets every node of theirs,
holes too, reports the shared nodes and neighbouring shapes, prefills the
mean, undoes, and converts ft → m exactly to a millimetre; plus the map
cursor rule (#1325).  Pure: no Qt."""

import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import O4_Qt_Patch_Elevation as ELEV  # noqa: E402
import O4_Qt_Patch_ShapePick as PICK  # noqa: E402
from o4_engine import patch_edit as PE  # noqa: E402
from O4_Qt_Pack_Outlines import METRES_PER_DEG_LAT  # noqa: E402


def _doc() -> PE.PatchDoc:
    """A 100 m apron (-101) with a gap-ring hole (-110), a taxiway (-102)
    sharing its nodes -2 and -3, and an open line (-103) from -4."""
    d_lat = 100 / METRES_PER_DEG_LAT
    d_lon = 100 / (METRES_PER_DEG_LAT * math.cos(math.radians(30.0)))

    def n(i, a, b, alt):
        return (i, 30.0 + a * d_lat, 31.0 + b * d_lon, alt)
    nodes = [n(-1, 0, 0, 100.0), n(-2, 0, 1, 102.0), n(-3, 1, 1, 104.0), n(-4, 1, 0, 106.0),
             n(-6, 0, 3, 101.0), n(-7, 1, 3, None), n(-8, 2, 0, 99.0),
             n(-21, 0.4, 0.4, 100.0), n(-22, 0.4, 0.6, None), n(-23, 0.6, 0.5, 100.0)]
    ways = (PE.Way(-101, (-1, -2, -3, -4, -1), {"role": "apron"}),
            PE.Way(-102, (-2, -6, -7, -3, -2), {"role": "taxiway"}),
            PE.Way(-103, (-4, -8), {"o4_feature": "crown_spine"}),
            PE.Way(-110, (-21, -22, -23, -21), {"o4_feature": "gap_interior_ring"}))
    return PE.PatchDoc({row[0]: row for row in nodes}, ways)


def test_one_shape_sets_its_ring_and_hole_and_reports_its_neighbours():
    p = ELEV.plan(_doc(), [-101])
    assert p.ways == {-101, -110}
    assert p.own == {-1, -21, -22, -23}
    assert p.shared == {-2, -3, -4}
    assert p.neighbours == {-102, -103}
    assert math.isclose(p.mean_alt, (100 + 102 + 104 + 106 + 100 + 100) / 6)
    assert ELEV.summary(p) == "3 shared nodes, 2 neighbouring shapes affected."
    assert p.targets(include_shared=False) == [-23, -22, -21, -1]


def test_two_shapes_sharing_two_nodes_set_every_node_and_undo_restores():
    before = _doc()
    p = ELEV.plan(before, [-101, -102])
    assert p.shared == {-4} and p.neighbours == {-103}
    after = ELEV.apply(before, p, 95.5)
    assert all(after.nodes[i][3] == 95.5 for i in p.targets())
    assert after.nodes[-8][3] == 99.0                  # the line's own end stays
    assert before.nodes[-2][3] == 102.0                # immutable: "undo" is the old doc


def test_shared_nodes_stay_when_the_box_is_off():
    doc = _doc()
    p = ELEV.plan(doc, [-101])
    after = ELEV.apply(doc, p, 90.0, include_shared=False)
    assert after.nodes[-1][3] == 90.0 and after.nodes[-22][3] == 90.0
    assert after.nodes[-2][3] == 102.0 and after.nodes[-4][3] == 106.0
    assert ELEV.summary(p, False) == ("3 shared nodes left as they are; "
                                      "no neighbouring shapes affected.")


def test_feet_convert_to_metres_exactly_to_a_millimetre():
    assert abs(ELEV.to_metres(1000, "ft") - 304.8) < 0.001
    assert abs(ELEV.to_metres(328.084, "ft") - 100) < 0.001
    assert ELEV.to_metres(12.5, "m") == 12.5
    assert abs(ELEV.from_metres(304.8, "ft") - 1000) < 0.001


def test_the_pointer_follows_what_a_click_acts_on():
    assert PICK.pointer(None) == "openHand"
    assert PICK.pointer(("empty",)) == "openHand"
    assert PICK.pointer(("node", -1)) == "pointingHand"
    assert PICK.pointer(("handle",)) == "pointingHand"
    assert PICK.pointer(("edge",)) == "pointingHand"
    assert PICK.pointer(("edge",), panning=True) == "closedHand"
    assert set(PICK.POINTERS) == {"openHand", "closedHand", "pointingHand"}
