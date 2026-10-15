"""The patch editor's edit operations against the shared twin fixture
(spec patch-editor-20261015 §3; ``tests/fixtures/patch_edit_ops.json`` is
run by ``swift test`` too — the two implementations cannot drift)."""

import json
import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest  # noqa: E402

from auto_patch_v2.emit import osm_adapter  # noqa: E402
from o4_engine import patch_edit as PE  # noqa: E402

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "patch_edit_ops.json")
with open(FIXTURE, encoding="utf-8") as _f:
    DATA = json.load(_f)
TOL_DEG = DATA["tolerance"]["deg"]
TOL_M = DATA["tolerance"]["m"]


def test_fixture_states_the_law_it_was_written_under():
    """The fixture's identity frame IS the law table's, and the local
    plane it describes is the emitter's own."""
    spacing, dp = PE.law_identity()
    assert DATA["min_distinct_spacing_m"] == spacing
    assert DATA["identity_dp"] == dp
    m_lat, m_lon = osm_adapter._local_metres((30.0, 31.0))
    assert m_lat == 111320.0
    assert m_lon == pytest.approx(111320.0 * math.cos(math.radians(30.0)), rel=1e-15)
    assert len(DATA["cases"]) >= 12


@pytest.mark.parametrize("case", DATA["cases"], ids=[c["name"] for c in DATA["cases"]])
def test_fixture_case(case):
    doc = PE.PatchDoc.from_wire(case["doc"]["nodes"], case["doc"]["ways"],
                                DATA["min_distinct_spacing_m"], DATA["identity_dp"])
    assert list(doc.origin) == pytest.approx(case["origin"], abs=TOL_DEG)
    for op in case["ops"]:
        doc = PE.apply_op(doc, op["op"], op["args"])
    got = doc.to_wire()
    want = case["expect"]
    assert [n[0] for n in got["nodes"]] == [n[0] for n in want["nodes"]]
    for g, w in zip(got["nodes"], want["nodes"]):
        assert abs(g[1] - w[1]) <= TOL_DEG and abs(g[2] - w[2]) <= TOL_DEG, (g, w)
        assert (g[3] is None) == (w[3] is None), (g, w)
        if w[3] is not None:
            assert abs(g[3] - w[3]) <= TOL_M, (g, w)
    assert got["ways"] == want["ways"]


def _doc(case_name):
    case = next(c for c in DATA["cases"] if c["name"] == case_name)
    return PE.PatchDoc.from_wire(case["doc"]["nodes"], case["doc"]["ways"],
                                 DATA["min_distinct_spacing_m"], DATA["identity_dp"])


def test_operations_are_pure():
    doc = _doc("move_single_no_neighbour")
    before = doc.to_wire()
    PE.move(doc, [-3], 0.001, 0.0)
    PE.delete_nodes(doc, [-1])
    PE.insert_on_edge(doc, -1, -2)
    assert doc.to_wire() == before


def test_insert_on_a_non_edge_is_refused():
    doc = _doc("move_single_no_neighbour")
    with pytest.raises(ValueError):
        PE.insert_on_edge(doc, -1, -3)
    with pytest.raises(KeyError):
        PE.move(doc, [-99], 0.0, 0.0)
