"""Twins for spec §55 (15) rule A+C — A GAP PART IS ONE SHAPE BY KIND, AND
ITS KNIVES ARE ITS ONLY JOINTS (``planar/shape_parts``,
``model.planar.shares_gap_part``).  Each is red on the 08k body reading
the rule replaces: two parts across a knife welded to one apron carried
ONE label (no joint along the knife), a neck inside one part minted a
contour whose rows were withdrawn, and a part welded beside a standing
neck changed the standing pavement's own labels."""
from __future__ import annotations

import dataclasses as _dc
import math
import sys
from pathlib import Path

import pytest
from shapely.geometry import LineString, Point
from shapely.ops import unary_union

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_v2shapes import (MOUTH_BENCH, RUNWAY, Y0, Y1, _airport, _dumbbell,  # noqa: E402,F401
                           _face, _rect, _vid, law)

from auto_patch_v2.classify.roles import Cell  # noqa: E402
from auto_patch_v2.law import Law  # noqa: E402
from auto_patch_v2.model.planar import (NO_SHAPE, gap_step_part,  # noqa: E402
                                        shares_gap_part)
from auto_patch_v2.planar import shapes as S  # noqa: E402

#: the knife of the twins (m): wider than the pre-snap weld (1.0 m) that
#: would share the two rims' vertices in a stage-1 fixture — the parts of
#: a real cut are late cells — and inside the widened readers' horizon
KNIFE = 1.2
YW = 160.0          # the welded rim: the apron's far edge, the parts' near edge


def _wide(law):
    emit = _dc.replace(law.tables.emit,
                       instrument=_dc.replace(law.tables.emit.instrument, step_contact_tol_m=2.0))
    return Law(tables=_dc.replace(law.tables, emit=emit), ruleset_key=law.ruleset_key)


def _part(i, ref, ring):
    return Cell(i, "groundside_pavement", ref, tuple(ring), (), None, None,
                "groundside", "gap_piece", {})


def _apron(ring=None):
    return Cell(1, "apron", "apronA", ring or _rect(-100, Y0, 100, YW), (), None, None,
                "airside", "apron", {})


def _two_parts_on_one_apron():
    h = KNIFE / 2.0
    return [RUNWAY, _apron(),
            _part(2, "gap:0/s0", _rect(-100, YW, -h, 200)),
            _part(3, "gap:0/s1/lot", _rect(h, YW, 100, 185)),
            _part(4, "gap:0/s1/ramp0", _rect(h, 185, 100, 200))]


def test_the_step_part_of_a_ref():
    assert gap_step_part("gap:7") == "gap:7" and gap_step_part("gap:7/lot1") == "gap:7"
    assert gap_step_part("gap:0/s4/lot#3") == "gap:0/s4" == gap_step_part("gap:0/s4/ramp2")
    assert gap_step_part("gap:0/s4") == "gap:0/s4" != gap_step_part("gap:0/s14")
    assert gap_step_part("pav37") is None and gap_step_part(None) is None


def test_two_parts_across_a_knife_are_two_shapes_and_the_knife_is_a_joint_along_its_length(law):
    _ap, pm, st, _cl = _airport(_wide(law), _two_parts_on_one_apron(), [])
    a, b, apron = (pm.shape_of_vertex[_vid(pm, xy)]
                   for xy in ((-100.0, 200.0), (100.0, 200.0), (-100.0, Y0)))
    assert len({a, b, apron}) == 3
    # a lot and its ramp are ONE step part: one label, no joint on the breakline
    assert pm.shape_of_vertex[_vid(pm, (100.0, 185.0))] == b
    # by kind: each part face is its own step part's shape, never the apron's
    assert pm.shape_of_face[_face(pm, "gap:0/s0").id] == a
    assert pm.shape_of_face[_face(pm, "gap:0/s1/lot").id] == b \
        == pm.shape_of_face[_face(pm, "gap:0/s1/ramp0").id]
    assert pm.shape_of_face[_face(pm, "apronA").id] == apron
    # the knife is declared along its whole facing rim
    gaps = [j for j in pm.shape_joints if j.gap and set(j.shapes) == {a, b}]
    assert gaps and st.shapes.contours == 0
    line = unary_union([LineString(j.points) for j in gaps])
    for k in range(0, 41):
        for x in (-KNIFE / 2.0, KNIFE / 2.0):
            assert line.distance(Point(x, YW + k)) <= 1.0, (x, YW + k)
    assert all(S.straddles(pm, p) for j in gaps for p in j.pairs)


def test_a_welded_rim_vertex_keeps_the_standing_label_and_the_pair_inside_the_part_is_one_shape(law):
    _ap, pm, st, _cl = _airport(_wide(law), _two_parts_on_one_apron(), [])
    rim, inner = _vid(pm, (-100.0, YW)), _vid(pm, (-100.0, 200.0))
    across = _vid(pm, (100.0, 200.0))
    assert pm.shape_of_vertex[rim] == pm.shape_of_vertex[_vid(pm, (-100.0, Y0))]
    assert pm.shape_of_vertex[rim] != pm.shape_of_vertex[inner]
    assert shares_gap_part(pm, (rim, inner)) and not S.straddles(pm, (rim, inner))
    assert not shares_gap_part(pm, (inner, across)) and S.straddles(pm, (inner, across))
    assert not shares_gap_part(pm, (rim, _vid(pm, (-100.0, Y0))))      # the apron's own pair
    # the two-label part faces declare no contour and count as the part's
    assert st.shapes.part_contours_undeclared >= 2 and st.shapes.apron_contours_undeclared == 0
    assert not any(not j.gap for j in pm.shape_joints)


def test_a_neck_inside_one_part_earns_no_contour(law):
    """A dumbbell PART with a 6 m neck over a 4 m bench: 08k's body reading
    split it at the neck (two bodies, an earned contour, every row across
    withdrawn).  One part is one shape: one label, no joint."""
    ring = _dumbbell(6.0)[1].ring
    _ap, pm, st, _cl = _airport(law, [RUNWAY, _part(1, "gap:2", ring)], [], dem=MOUTH_BENCH)
    f = _face(pm, "gap:2")
    labs = {pm.shape_of_vertex.get(v, NO_SHAPE) for v in pm.ring_vertices(f.ring)}
    assert len(labs) == 1 and NO_SHAPE not in labs
    assert not pm.shape_joints and st.shapes.contours == 0 and st.shapes.orphans_earned == 0
    assert not S.straddles(pm, (_vid(pm, (-150.0, Y0)), _vid(pm, (150.0, Y0))))


def test_a_part_welded_beside_a_standing_neck_leaves_the_standing_labels_alone(law):
    """Rule 1: the part is OUT of the pavement union.  A standing dumbbell
    (two bodies across its 10 m neck, an earned joint) keeps its two shapes
    when a gap part fills the notch under the neck — in the union the part
    made the neck 55 m wide and the standing pavement ONE body."""
    cells = _dumbbell(10.0, "stub")
    _ap, base, _st, _cl = _airport(law, cells, [], dem=MOUTH_BENCH)
    _ap, pm, st, _cl = _airport(law, cells + [_part(2, "gap:1", _rect(-15, Y0, 15, 165))], [],
                                dem=MOUTH_BENCH)
    corners = [(-150.0, Y0), (-150.0, Y1), (150.0, Y0), (150.0, Y1), (-15.0, Y1), (15.0, Y1)]

    def partition(m):
        labs = [m.shape_of_vertex[_vid(m, xy)] for xy in corners]
        return [[i == j for j in labs] for i in labs]
    assert partition(pm) == partition(base)
    left, right = (pm.shape_of_vertex[_vid(pm, xy)] for xy in ((-150.0, Y0), (150.0, Y0)))
    assert left != right and st.shapes.bodies == 2
    # the standing neck's own joint still stands between the two standing shapes
    assert len(base.shape_joints) == 1
    assert any(not j.gap and set(j.shapes) == {left, right} for j in pm.shape_joints)


def test_a_map_with_no_gap_part_is_labelled_exactly_as_before(law, monkeypatch):
    """Sheet-free: no branch taken — the labels with the part rule equal the
    labels with the rule's two entry points stubbed out."""
    cells = _dumbbell(10.0, "stub")
    _ap, pm, _st, _cl = _airport(law, cells, [], dem=MOUTH_BENCH)
    monkeypatch.setattr(S, "label_gap_parts", lambda *a, **k: {})
    monkeypatch.setattr(S, "shares_gap_part", lambda *a, **k: False)
    _ap, ref, _st, _cl = _airport(law, cells, [], dem=MOUTH_BENCH)
    assert dict(pm.shape_of_vertex) == dict(ref.shape_of_vertex)
    assert dict(pm.shape_of_face) == dict(ref.shape_of_face)
    assert pm.shape_joints == ref.shape_joints


FRAME = Path("/Users/noah/XPTerrainBuilderData/.harness/frames/gaps7/ARM2/solved.pkl")


@pytest.mark.skipif(not FRAME.exists(), reason="frame gaps7/ARM2 (a cut map) not mounted")
def test_the_rule_read_on_a_real_cut_map_declares_every_knife_and_no_contour_in_a_part():
    """THE FRAME TWIN (spec §55 (15)): the labels re-derived on one recorded
    cut map.  COVERAGE, never a count (``linemerge`` splits a knife's
    midline where a ribbon crosses it): the declared joints between two
    step parts of one piece run the knife's facing rim — one stub excepted
    on this map (9 m of rim, 3 m declared: the knife's end at a pad's foot,
    §55 (15) residual 6)."""
    import collections
    import pickle

    from auto_patch_v2.model.planar import gap_parts_across_knife
    from auto_patch_v2.pipeline import capture_state as cs_
    with open(FRAME, "rb") as fh:
        a = pickle.load(fh)
    if a.get(cs_.CAPTURE_STATE_KEY):
        cs_.install(a[cs_.CAPTURE_STATE_KEY])
    pm, st = S.build_shapes(a["pm"], Law.for_airport(a["icao"]), a["airport"])
    contours = [j for j in pm.shape_joints if not j.gap]
    assert len(contours) <= 16 and st.part_contours_undeclared > 0
    assert not any(shares_gap_part(pm, p) for j in contours for p in j.pairs)
    polys, shape = collections.defaultdict(list), {}
    for fid, f in pm.faces.items():
        key = gap_step_part(f.ref)
        if key is not None and (p := S._face_polygon(pm, fid)) is not None:
            polys[key].append(p)
            shape[key] = pm.shape_of_face[fid]
    part = {k: unary_union(v) for k, v in polys.items()}
    assert len(set(shape.values())) == len(shape)            # one shape per step part
    declared = collections.Counter()
    for j in pm.shape_joints:
        if j.gap:
            declared[tuple(sorted(j.shapes))] += j.length_m
    keys = sorted(part)
    knives, short = 0, []
    for i, k in enumerate(keys):
        for k2 in keys[i + 1:]:
            if not gap_parts_across_knife(k, k2) or part[k].distance(part[k2]) > 1.0:
                continue
            knives += 1
            facing = part[k].boundary.intersection(part[k2].buffer(1.0)).length
            if declared[tuple(sorted((shape[k], shape[k2])))] < 0.9 * facing:
                short.append((k, k2, round(facing, 1)))
    assert knives >= 40
    assert len(short) <= 1 and all(f <= 10.0 for _k, _k2, f in short), short
