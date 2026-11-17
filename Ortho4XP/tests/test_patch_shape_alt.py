"""A patch shape's own elevation tags (issue #2137) against the shared
twin fixture ``tests/fixtures/patch_shape_alt.json`` (``swift test`` runs
it too), and the round trip: an edit written by the editor's save path is
read back by Ortho4XP's own patch reader with the value the edit set."""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import O4_OSM_Utils as OSM  # noqa: E402
import pytest  # noqa: E402
from o4_engine import patch_edit as PE  # noqa: E402
from o4_engine import patch_file as PF  # noqa: E402
from o4_engine import patch_shape_alt as A  # noqa: E402

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "patch_shape_alt.json")
with open(FIXTURE, encoding="utf-8") as _f:
    DATA = json.load(_f)
TOL = DATA["tolerance"]["deg"]


@pytest.mark.parametrize("case", DATA["recognize"], ids=[c["name"] for c in DATA["recognize"]])
def test_recognize(case):
    assert A.shape_alt(case["tags"], case["refs"]) == case["expect"]


@pytest.mark.parametrize("case", DATA["level"], ids=[c["name"] for c in DATA["level"]])
def test_level_tags(case):
    assert A.level_tags(case["tags"], case["value"]) == case["expect"]


@pytest.mark.parametrize("case", DATA["slope"], ids=[c["name"] for c in DATA["slope"]])
def test_slope_tags(case):
    assert A.slope_tags(case["tags"], case["high"], case["low"]) == case["expect"]


def test_labels():
    for case in DATA["labels"]:
        assert A.slope_label(case["side"], case["value"]) == case["expect"]


def _flat(points):
    return list(points) if isinstance(points[0], (int, float)) else [x for p in points for x in p]


@pytest.mark.parametrize("case", DATA["marks"], ids=[c["name"] for c in DATA["marks"]])
def test_marks(case):
    got, want = A.slope_marks(case["corners"]), case["expect"]
    if want is None:
        assert got is None
        return
    assert set(got) == set(want)
    for key, points in want.items():
        assert _flat(got[key]) == pytest.approx(_flat(points), abs=TOL), key


def test_arrow_points_from_the_high_side_to_the_low_side():
    corners = DATA["marks"][0]["corners"]   # north-up: refs [3]-[0] is the south edge
    m = A.slope_marks(corners)
    assert m["arrow"][3][0] > m["arrow"][0][0]     # the tip is north of the tail
    assert m["high_label"][0] < m["low_label"][0]


def _ortho4xp_reads(tmp_path, doc):
    """Write ``doc`` the way ``patch_save`` does and parse it with the
    reader the tile build uses; returns its way tags by id and the file as
    the editor reads it back."""
    wire = doc.to_wire()
    text = PF.render([("generator", "'", "test")], wire["nodes"], wire["ways"],
                     identity_dp=11, z_dp=2)
    path = tmp_path / "TEST.patch.osm"
    path.write_text(text, encoding="utf-8")
    layer = OSM.OSM_layer()
    layer.update_dicosm(str(path), input_tags=None, target_tags=None)
    return layer.dicosmtags["w"], PF.read_patch(str(path))


@pytest.mark.parametrize("tags", [{"cst_alt_abs": "80"}, {"altitude": "55"}, {"role": "apron"}])
def test_level_edit_round_trips_through_the_reader(tmp_path, tags):
    nodes = [[-1, 30.0, 31.0, None], [-2, 30.0, 31.001, None], [-3, 30.001, 31.001, None]]
    doc = PE.PatchDoc.from_wire(nodes, [{"id": -9, "refs": [-1, -2, -3, -1], "tags": tags}])
    new = A.level_tags(tags, 172.4)
    doc = PE.set_way_tags(doc, -9, put=new)
    read, again = _ortho4xp_reads(tmp_path, doc)
    (wtags,) = read.values()
    key = A.shape_alt(new)["key"]
    assert float(wtags[key]) == pytest.approx(172.4)
    w = again.ways[0]
    assert A.shape_alt(w["tags"], w["refs"])["value"] == pytest.approx(172.4)


def test_slope_edit_round_trips_through_the_reader(tmp_path):
    nodes = [[-1, 30.0, 31.0, 1.0], [-2, 30.0007, 31.0, 1.0], [-3, 30.0007, 31.0001, 1.0],
             [-4, 30.0, 31.0001, 1.0]]
    tags = {"altitude_high": "172.40", "altitude_low": "170.90", "profile": "spline",
            "role": "tunnel_ramp"}
    doc = PE.PatchDoc.from_wire(nodes, [{"id": -9, "refs": [-1, -2, -3, -4, -1], "tags": tags}])
    doc = PE.set_way_tags(doc, -9, put=A.slope_tags(tags, high=175.0, low=169.25))
    read, again = _ortho4xp_reads(tmp_path, doc)
    (wtags,) = read.values()
    assert float(wtags["altitude_high"]) == 175.0
    assert float(wtags["altitude_low"]) == 169.25
    assert wtags["profile"] == "spline"
    w = again.ways[0]
    assert A.shape_alt(w["tags"], w["refs"]) == {"form": "slope", "high": 175.0, "low": 169.25,
                                                 "valid": True}


def test_set_way_tags_refuses_an_unknown_way():
    doc = PE.PatchDoc.from_wire([], [])
    with pytest.raises(KeyError):
        PE.set_way_tags(doc, -1, put={"a": "b"})
