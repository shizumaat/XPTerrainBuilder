"""The patch editor's Slice (issue #1318; owner Q130-Q133): one shape cut
in two between two of its nodes, a 0.5 m gap left, checked with shapely.
The ``slice_shape`` cases of ``tests/fixtures/patch_edit_ops.json`` are the
twin the Mac app runs too (``tests/test_patch_edit.py`` runs them here)."""

import json
import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest  # noqa: E402
from o4_engine import patch_edit as PE  # noqa: E402
from o4_engine import patch_slice as SL  # noqa: E402
from shapely.geometry import Polygon  # noqa: E402

FIXTURE = os.path.join(os.path.dirname(__file__), "fixtures", "patch_edit_ops.json")
with open(FIXTURE, encoding="utf-8") as _f:
    CASES = {c["name"]: c for c in json.load(_f)["cases"]}

M_LAT = 111320.0
M_LON = M_LAT * math.cos(math.radians(30.0))
D = 0.0009765625


def _doc(name):
    c = CASES[name]
    return PE.PatchDoc.from_wire(c["doc"]["nodes"], c["doc"]["ways"]), c["ops"][0]["args"]


def _poly(doc, way_id):
    w = next(x for x in doc.ways if x.id == way_id)
    return Polygon([((doc.nodes[r][2] - 31.0) * M_LON, (doc.nodes[r][1] - 30.0) * M_LAT)
                    for r in w.refs[:-1]])


def _halves(before, after, way_id):
    new = [w.id for w in after.ways if w.id not in {x.id for x in before.ways}]
    assert len(new) == 1
    return _poly(after, way_id), _poly(after, new[0]), new[0]


def _ring(doc, way_id, holes=()):
    shell = _poly(doc, way_id)
    for h in holes:
        shell = shell.difference(_poly(doc, h))
    return shell


def _xy(doc, nid):
    n = doc.nodes[nid]
    return ((n[2] - 31.0) * M_LON, (n[1] - 30.0) * M_LAT)


def _copy_pairs(before, after, args):
    """(kept id, new id) for a and b: the new copy is the added node
    nearest the kept one."""
    added = [i for i in after.nodes if i not in before.nodes]
    out = []
    for nid in (args["a"], args["b"]):
        p = _xy(after, nid)
        out.append((nid, min(added, key=lambda i: math.dist(p, _xy(after, i)))))
    return out


def _check_split(before, after, way_id, args, holes=()):
    keep, other, new_id = _halves(before, after, way_id)
    assert keep.is_valid and other.is_valid
    assert keep.area >= other.area * (1.0 - 1.0e-9)
    assert not keep.intersects(other)
    # Each cut node is now two, the gap apart, keeping its height; the cut
    # line between them is the gap wide all along.
    (a, a2), (b, b2) = _copy_pairs(before, after, args)
    for x, y in ((a, a2), (b, b2)):
        assert math.dist(_xy(after, x), _xy(after, y)) == pytest.approx(SL.GAP_M, abs=1e-3)
        assert after.nodes[x][3] == after.nodes[y][3] == before.nodes[x][3]
    mid_a = [(p + q) / 2 for p, q in zip(_xy(after, a), _xy(after, a2), strict=True)]
    mid_b = [(p + q) / 2 for p, q in zip(_xy(after, b), _xy(after, b2), strict=True)]
    assert mid_a == pytest.approx(list(_xy(before, a)), abs=1e-6)
    assert mid_b == pytest.approx(list(_xy(before, b)), abs=1e-6)
    # Everything the halves cover was the shape (the copies sit half the
    # gap off the cut line, so a corner may stand that far out).
    original = _ring(before, way_id, holes)
    assert keep.union(other).difference(original.buffer(SL.GAP_M / 2 + 1e-3)).area < 1e-6
    tags = {w.id: dict(w.tags) for w in after.ways}
    assert tags[new_id] == tags[way_id] == dict(next(w for w in before.ways if w.id == way_id).tags)
    return keep, other, new_id


def test_convex_square_diagonal():
    before, args = _doc("slice_square_diagonal_keeps_neighbour_welded")
    after = PE.slice_shape(before, **args)
    keep, other, new_id = _check_split(before, after, -101, args)
    diagonal = math.hypot(D * M_LON, D * M_LAT)
    # The strip lost along the cut is at most the diagonal times the gap
    # (the copies at the two corners stand out and win a little back).
    assert 0 < _poly(before, -101).area - keep.area - other.area <= diagonal * SL.GAP_M
    # The node ids stay with the half that keeps the way id; the
    # neighbour still uses -1 (welded), and every copy keeps its height.
    kept = next(w for w in after.ways if w.id == -101).refs
    assert -1 in kept and -3 in kept
    assert next(w for w in after.ways if w.id == -102).refs == (-5, -1)
    assert after.nodes[-1][3] == after.nodes[-6][3] == 100.0
    assert after.nodes[-3][3] == after.nodes[-7][3] == 104.0
    gap = math.hypot((after.nodes[-1][2] - after.nodes[-6][2]) * M_LON,
                     (after.nodes[-1][1] - after.nodes[-6][1]) * M_LAT)
    assert gap == pytest.approx(SL.GAP_M, abs=1e-3)
    assert [w.id for w in after.ways] == [-101, -103, -102]


def test_clockwise_concave_l():
    before, args = _doc("slice_clockwise_concave_l_larger_half_keeps_id")
    after = PE.slice_shape(before, **args)
    keep, other, _new = _check_split(before, after, -201, args)
    assert keep.area > 4 * other.area
    # The rings keep the input's direction (clockwise) and start at a.
    for w in after.ways:
        assert SL.ring_area([(after.nodes[r][2], after.nodes[r][1]) for r in w.refs[:-1]]) < 0
    assert next(w for w in after.ways if w.id == -201).refs[0] == args["a"]


def test_a_crossed_hole_is_sliced_and_dropped():
    before, args = _doc("slice_through_a_hole_adds_nodes_and_drops_the_hole")
    after = PE.slice_shape(before, **args)
    keep, other, _new = _check_split(before, after, -301, args, holes=(-302,))
    ids = {w.id for w in after.ways}
    assert -302 not in ids and -303 in ids          # crossed hole gone, the other kept
    original = _ring(before, -301, holes=(-302,))
    lost = original.area - keep.area - other.area
    assert 0 < lost < 1.5 * math.hypot(D * M_LON, D * M_LAT) * SL.GAP_M
    added = [n for i, n in after.nodes.items() if i not in before.nodes]
    assert len(added) == 6                          # a's and b's copies + 2 per crossing
    # Crossing heights are interpolated along the hole edge; an edge with a
    # node without elevation gives none.
    crossing_alts = sorted((n[3] for n in added if n[3] not in (10.0, 20.0)),
                           key=lambda x: (x is None, x))
    assert crossing_alts[-4:] == [None] * 4


def test_the_way_argument_picks_one_of_two_shapes():
    nodes = [[-1, 30.0, 31.0, 1.0], [-2, 30.0, 31.0 + D, 1.0], [-3, 30.0 + D, 31.0 + D, 1.0],
             [-4, 30.0 + D, 31.0, 1.0], [-5, 30.0 + D / 2, 31.0 + 1.5 * D, 1.0],
             [-6, 30.0 + D / 2, 31.0 - D / 2, 1.0]]
    ways = [{"id": -1, "refs": [-1, -2, -3, -4, -1], "tags": {"role": "apron"}},
            {"id": -2, "refs": [-1, -5, -3, -6, -1], "tags": {"role": "taxiway"}}]
    doc = PE.PatchDoc.from_wire(nodes, ways)
    with pytest.raises(ValueError, match="more than one shape"):
        PE.slice_shape(doc, -1, -3)
    after = PE.slice_shape(doc, -1, -3, way=-2)
    assert next(w for w in after.ways if w.id == -1).refs == (-1, -2, -3, -4, -1)
    assert len(after.ways) == 3
    assert [w.tags["role"] for w in after.ways][1:] == ["taxiway", "taxiway"]


@pytest.mark.parametrize("a,b,match", [
    (-3, -6, "leaves the shape"),       # across the L's notch
    (-1, -2, "not neighbours"),
    (-1, -1, "same shape"),
])
def test_refused_cuts_on_the_l(a, b, match):
    before, _args = _doc("slice_clockwise_concave_l_larger_half_keeps_id")
    with pytest.raises(ValueError, match=match):
        PE.slice_shape(before, a, b)


def test_refused_off_the_shape_and_unknown():
    before, _args = _doc("slice_square_diagonal_keeps_neighbour_welded")
    with pytest.raises(ValueError, match="same shape"):
        PE.slice_shape(before, -5, -3)
    with pytest.raises(KeyError):
        PE.slice_shape(before, -1, -99)


def test_refused_along_an_edge():
    # -1, -2, -3 in a straight line: a cut from -1 to -3 runs along the edge.
    nodes = [[-1, 30.0, 31.0, 1.0], [-2, 30.0, 31.0 + D, 1.0], [-3, 30.0, 31.0 + 2 * D, 1.0],
             [-4, 30.0 + D, 31.0 + 2 * D, 1.0], [-5, 30.0 + D, 31.0, 1.0]]
    doc = PE.PatchDoc.from_wire(nodes, [{"id": -1, "refs": [-1, -2, -3, -4, -5, -1], "tags": {}}])
    with pytest.raises(ValueError, match="along the shape's edge"):
        PE.slice_shape(doc, -1, -3)


def _square_with_hole(hole):
    nodes = [[-1, 30.0, 31.0, 1.0], [-2, 30.0, 31.0 + D, 1.0], [-3, 30.0 + D, 31.0 + D, 1.0],
             [-4, 30.0 + D, 31.0, 1.0]]
    nodes += [[-10 - i, 30.0 + lat * D, 31.0 + lon * D, 1.0] for i, (lat, lon) in enumerate(hole)]
    ways = [{"id": -1, "refs": [-1, -2, -3, -4, -1], "tags": {"role": "apron"}},
            {"id": -2, "refs": [-10 - i for i in range(len(hole))] + [-10],
             "tags": {"o4_feature": "gap_interior_ring"}}]
    return PE.PatchDoc.from_wire(nodes, ways)


def test_refused_through_a_hole_corner():
    doc = _square_with_hole([(0.25, 0.5), (0.5, 0.75), (0.75, 0.5), (0.5, 0.25)])
    # The cut -1 -> -3 is the diagonal; the hole's corners (0.5±.25) are off
    # it, but a diamond centred on it has two corners exactly on it.
    doc2 = _square_with_hole([(0.25, 0.25), (0.5, 0.4), (0.75, 0.75), (0.4, 0.5)])
    PE.slice_shape(doc, -1, -3)
    with pytest.raises(ValueError, match="corner of a hole"):
        PE.slice_shape(doc2, -1, -3)


def test_refused_more_than_two_pieces():
    # A U-shaped hole opening north, crossed through both arms by a cut
    # from west to east: the pocket between the arms below the cut would
    # be a third piece.
    nodes = [[-1, 30.0, 31.0, 1.0], [-2, 30.0, 31.0 + D, 1.0], [-3, 30.0 + D, 31.0 + D, 1.0],
             [-4, 30.0 + D / 2 + D / 64, 31.0 + D, 1.0], [-5, 30.0 + D, 31.0, 1.0],
             [-6, 30.0 + D / 2, 31.0, 1.0]]
    u = [(0.2, 0.2), (0.2, 0.8), (0.8, 0.8), (0.8, 0.7),
         (0.3, 0.7), (0.3, 0.3), (0.8, 0.3), (0.8, 0.2)]
    nodes += [[-10 - i, 30.0 + lat * D, 31.0 + lon * D, 1.0] for i, (lat, lon) in enumerate(u)]
    ways = [{"id": -1, "refs": [-1, -2, -4, -3, -5, -6, -1], "tags": {}},
            {"id": -2, "refs": [-10 - i for i in range(len(u))] + [-10],
             "tags": {"o4_feature": "gap_interior_ring"}}]
    doc = PE.PatchDoc.from_wire(nodes, ways)
    with pytest.raises(ValueError, match="more than two pieces"):
        PE.slice_shape(doc, -6, -4)


def test_slice_is_pure_and_one_op():
    before, args = _doc("slice_through_a_hole_adds_nodes_and_drops_the_hole")
    wire = before.to_wire()
    PE.slice_shape(before, **args)
    assert before.to_wire() == wire
    assert PE.apply_op(before, "slice_shape", args) == PE.slice_shape(before, **args)
