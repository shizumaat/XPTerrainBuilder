"""Twins for issue #253 (RULINGS 2026-10-02y) — THE APRON WELD KEEPS
GROUNDSIDE TERRACE JOINTS.

Owner RULINGS 2026-10-02v (2) rules both halves at once: "an apron face
never carries a terrace ... terraces stay lawful GROUNDSIDE only".  Round
one (#189, ``planar/shape_airside.weld_airside_faces``) delivered the
first half by welding the LABELS of an apron face, and a ``uf.union`` is
GLOBAL: a label pair welded through one apron face loses its joint on
EVERY edge between those labels.  MEASURED at KCLT (sw1007, main
b10b2014): shapes 31 -> 28, joints 5 -> 0, road ramps 7 -> 4, sidecar
``terrace_joints`` 5 -> 0 — although the edge census before the weld was
``apron|apron`` 8, ``apron|parking_lot`` 1, ``parking_lot|parking_lot`` 1
(joint 4, shapes [3, 15], 0.82 m, near 35.20906, -80.93114).  The
groundside terrace died with the airside one.

THE RULE these twins hold: only an edge BOTH of whose sides are airside
pavement loses its joint; a joint edge with a GROUNDSIDE side (a lot,
groundside pavement, a service road, a terrain face) keeps its joint, its
row withdrawal and its sidecar record.  The joint is therefore carried per
EDGE (``planar/shape_airside.inside_apron_body``, read by the one label
reader ``planar.shapes.straddles`` and by the contour derivation), and the
weld that remains consolidates IDENTITY only — never across a label pair a
surviving joint edge separates.

PR #236's five twins stand unchanged beside these.
"""
from __future__ import annotations

import math
import sys
from pathlib import Path

import pytest

from auto_patch_v2.classify.roles import Cell
from auto_patch_v2.law import Law
from auto_patch_v2.law.tables import pavement_fallback_cap
from auto_patch_v2.model.constraints import Diff
from auto_patch_v2.pipeline.publication import publication
from auto_patch_v2.pipeline.shapes import shape_constraints, shape_stage
from auto_patch_v2.planar import shapes as S
from auto_patch_v2.planar.shape_airside import (inside_apron_body,
                                                separated_label_pairs,
                                                weld_airside_faces)
from auto_patch_v2.solve import Status, solve_design

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_apronjoint189 import MOUTH_DROP_M, _FacePM  # noqa: E402
from test_v2shapes import RUNWAY, Y0, Y1, _airport, _Bench, _dumbbell, _vid  # noqa: E402


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


#: the dumbbell's neck: the ring steps in to ``170 - h`` and out at
#: ``170 + h`` (``test_v2shapes._dumbbell``), so with a 10 m neck the two
#: cross-neck ring edges stand at y = 165 (the SOUTH one) and y = 175
NECK_W = 10.0
NECK_S, NECK_N = 170.0 - NECK_W / 2.0, 170.0 + NECK_W / 2.0


def _apron_and_lot():
    """#253's shape, synthetically: ONE apron face (the dumbbell, whose two
    lobes are two shapes over a DEM step at x = 0) and a ``parking_lot``
    filling the dumbbell's SOUTH notch, so the lot's own vertices carry
    BOTH labels.  That gives all three edge classes of the KCLT census on
    one fixture:

    * ``apron|apron``  — the neck's NORTH ring edge (y = 175), the apron
      face on one side and the open boundary on the other: inside the
      apron body, no joint (#189);
    * ``apron|parking_lot`` — the neck's SOUTH ring edge (y = 165), shared
      with the lot: a groundside side, so the joint stands;
    * ``parking_lot|parking_lot`` — the lot's SOUTH edge (y = 120): the lot
      face on one side, nothing airside anywhere on it, joint stands.
    """
    return _dumbbell(NECK_W) + [
        Cell(3, "parking_lot", "lot", ((-15.0, Y0), (15.0, Y0), (15.0, NECK_S), (-15.0, NECK_S)),
             (), None, None, "groundside", "apron", {})]


@pytest.fixture(scope="module")
def built(law):
    return _airport(law, _apron_and_lot(), [], dem=_Bench(0.0, rise=MOUTH_DROP_M))


# ── 1. THE DEFECT: the weld no longer unions the labels globally ─────────

def test_a_label_pair_a_groundside_joint_edge_separates_is_never_welded(law):
    """#253's MECHANISM, at the derivation site.  ``weld_airside_faces``
    merges the labels an apron face carries only when NO surviving joint
    edge separates them; a pair that one does (KCLT's [3, 15], carried by
    an ``apron|parking_lot`` and a ``parking_lot|parking_lot`` edge) is
    kept apart, so its groundside joints stand.  Without ``separated`` the
    merge is round one's and still fires — that is PR #236's twin."""
    pm = _FacePM("apron")
    label = {0: 0, 1: 0, 2: 1, 3: 1}
    st, uf = S.ShapeStats(), S._Union()
    weld_airside_faces(pm, law, label, uf, st, frozenset({(0, 1)}))
    assert label[0] != label[3]
    assert (st.welded_airside_faces, st.airside_faces_kept) == (0, 1)


def test_the_separated_pair_is_not_merged_transitively(law):
    """A|B welded through one apron face and B|C through another must not
    put A and C in one shape when a joint edge separates A|C
    (``_merges_separated``): a union is transitive, and that is exactly how
    one apron face reached every edge of a label pair at KCLT."""
    pm = _FacePM("apron")
    uf, st = S._Union(), S.ShapeStats()
    weld_airside_faces(pm, law, {0: 0, 1: 0, 2: 1, 3: 1}, uf, st, frozenset({(0, 2)}))
    assert uf.find(0) == uf.find(1)                      # A|B: nothing separates it
    weld_airside_faces(pm, law, {0: 1, 1: 1, 2: 2, 3: 2}, uf, st, frozenset({(0, 2)}))
    assert uf.find(0) != uf.find(2), "A and C merged through B"


def test_the_separated_pairs_are_read_off_the_surviving_joint_edges(built, law):
    """``separated_label_pairs`` is the edge census the rule turns on: the
    two labels of the fixture are separated, because the lot's edges carry
    them with a GROUNDSIDE side."""
    _ap, pm, _st, _cl = built
    pairs = separated_label_pairs(pm, dict(pm.shape_of_vertex),
                                  pm.no_terrace_faces, pm.airside_pavement_faces)
    labs = sorted({s for s in pm.shape_of_vertex.values() if s != S.NO_SHAPE})
    assert len(labs) == 2 and pairs == frozenset({(labs[0], labs[1])})


# ── 2. THE RULE, end to end, on one contour crossing both faces ─────────

def test_the_apron_portion_ramps_and_the_groundside_edges_keep_the_joint(built, law):
    """ONE contour step crossing an apron face AND the adjacent parking
    lot.  The apron's own cross-neck edge is inside the apron body: it is
    no joint edge and its rows are PRESENT (it ramps, #189).  The lot|lot
    and apron|lot edges keep the joint (#253), and the sidecar lists
    them."""
    _ap, pm, st, cl = built
    # the labels were NOT merged: two shapes, nothing welded, one pair kept
    assert st.shapes.shapes == 2
    assert (st.shapes.welded_airside_faces, st.shapes.airside_faces_kept) == (0, 1)

    apron_n = (_vid(pm, (-15.0, NECK_N)), _vid(pm, (15.0, NECK_N)))
    apron_lot = (_vid(pm, (-15.0, NECK_S)), _vid(pm, (15.0, NECK_S)))
    lot_lot = (_vid(pm, (-15.0, Y0)), _vid(pm, (15.0, Y0)))
    assert pm.shape_of_vertex[apron_n[0]] != pm.shape_of_vertex[apron_n[1]]

    # THE AIRSIDE EDGE: inside the apron body, so not a joint edge
    assert inside_apron_body(pm, apron_n) and not S.straddles(pm, apron_n)
    # THE GROUNDSIDE EDGES: a lot side vetoes, so both stand as 08k cut them
    for pair in (apron_lot, lot_lot):
        assert not inside_apron_body(pm, pair) and S.straddles(pm, pair), pair
    # the JOINT-EDGE CENSUS, in KCLT's own vocabulary: the groundside edges
    # and only those — no ``apron|apron`` row survives (#189), and the two
    # the issue names do (#253).  ``joint_planar_edges`` pads a one-sided
    # edge's roles, so the lot's open edge reads ``parking_lot|parking_lot``.
    roles: dict[str, int] = {}
    for _x, _y, a, b in S.joint_planar_edges(pm):
        roles[f"{a}|{b}"] = roles.get(f"{a}|{b}", 0) + 1
    assert roles == {"apron|parking_lot": 1, "parking_lot|parking_lot": 1}, roles

    # the sidecar LISTS the groundside joints (5 -> 0 at KCLT is the defect)
    stage = shape_stage(pm, law, _ap, cl, out=lambda _m: None)
    cs, _counts, _w = shape_constraints(pm, law, _ap, stage)
    sol, rep = solve_design(pm, cs, law)
    assert sol.status in (Status.OPTIMAL, Status.FEASIBLE), rep.line()
    recs = [r for r in publication(pm, law, _ap, sol.z)["terrace_joints"]
            if r["kind"] == "apron_terrace"]
    assert recs, "the groundside terrace was not declared"
    assert {r for rec in recs for r in rec["roles"]} >= {"parking_lot"}

    # ... and the APRON's edge carries a hard pavement row at or under the
    # 29ac fallback cap — #189's pair carried none at all — and the solved
    # step across it is inside that cap: the apron RAMPS
    cap = pavement_fallback_cap(law)
    hard = [r for r in cs.rows() if isinstance(r, Diff) and r.soft is None
            and {r.a, r.b} == set(apron_n) and r.cap <= cap]
    assert hard, "no hard pavement row across the apron's own neck edge"
    dist = math.dist(pm.vertices[apron_n[0]].xy, pm.vertices[apron_n[1]].xy)
    step = abs(float(sol.z[apron_n[0]]) - float(sol.z[apron_n[1]]))
    assert step <= cap * dist + 1e-6, (step, cap * dist)
