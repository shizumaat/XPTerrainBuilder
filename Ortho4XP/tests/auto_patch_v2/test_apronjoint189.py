"""Twins for owner RULINGS 2026-10-02v (2) — APRONS ALWAYS GRADE (issue
#189, lane ``apronjoint189``): "an apron face never carries a terrace — a
contour joint inside one apron face does not withdraw the 29ac pavement
fallback; terraces stay lawful groundside only (KCLT 35.2068281,
-80.9422880 becomes a ramp)".

MEASURED defect (#189, KCLT capture at main 52e2e2ae): v11221 (212.26 m)
and v11222 (214.85 m) are CONSECUTIVE RING VERTICES of one apron face,
``apron#445`` (``dsf:pol43``), with no road within reach; the 08k shape
stage declared a contour joint between shapes 1 and 6 inside it and
``pipeline/shapes.apply_joints`` dropped every row across it — including
the only family left on a bare apron ring edge, the 29ac
``rulesets.common.road_max_grade pavement fallback``.  The pair carried NO
row, and the census priced the built 2.59 m over 4.47 m (57.9 %) against
the 8 % road cap.

The fix is at the joint's DERIVATION (``planar/shape_airside.py``): the
labels on an airside apron face weld, so no contour is cut inside it, no
row is withdrawn and no sidecar record is written.  The twins here read
the derivation site directly (which roles weld, and the 08r-2 road
exception) and then the whole build: no joint, the fallback rows present,
the solved step inside the pavement cap, the sidecar clean — against a
GROUNDSIDE face carrying the same step, which keeps its joint."""
from __future__ import annotations

import dataclasses as _dc
import math
import sys
from pathlib import Path

import pytest

from auto_patch_v2.classify.roles import Cell
from auto_patch_v2.constraints.pavement_cap import GEN as PAVCAP_GEN
from auto_patch_v2.law import Law
from auto_patch_v2.law.tables import pavement_fallback_cap
from auto_patch_v2.model.constraints import Diff
from auto_patch_v2.pipeline.publication import publication
from auto_patch_v2.pipeline.shapes import shape_constraints, shape_stage
from auto_patch_v2.planar import shapes as S
from auto_patch_v2.planar.shape_airside import airside_apron_roles, weld_airside_faces
from auto_patch_v2.solve import Status, solve_design

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_v2shapes import (RUNWAY, Y0, Y1, _Bench, _airport,  # noqa: E402
                           _dumbbell, _rect, _vid)

@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


#: the DEM drop the mouth stands over — well past ``materiality.step_m``,
#: the drop 29k's earned-joint admission reads
MOUTH_DROP_M = 5.0


# ── 1. the derivation site: which face welds its labels ─────────────────

class _FacePM:
    """The two things :func:`weld_airside_faces` reads off a map: the faces
    (role, ring, holes) and ``ring_vertices``.  Face 10 is the face under
    test, carrying labels on vertices 0..3; ``road_ring`` optionally adds a
    service-road face 11 ringing the vertices named (the 08r-2 case: the
    second label reaches the apron only through the road weld)."""

    def __init__(self, role: str, road_ring: tuple[int, ...] | None = None):
        F = _dc.make_dataclass("F", ["role", "ring", "holes"])
        self.faces = {10: F(role, "r10", ())}
        self._rings = {"r10": (0, 1, 2, 3)}
        if road_ring is not None:
            self.faces[11] = F("service_road", "r11", ())
            self._rings["r11"] = road_ring

    def ring_vertices(self, cyc):
        return self._rings[cyc]


def _weld(law, role: str, road_ring: tuple[int, ...] | None = None):
    pm = _FacePM(role, road_ring)
    label = {0: 0, 1: 0, 2: 1, 3: 1}
    st, uf = S.ShapeStats(), S._Union()
    weld_airside_faces(pm, law, label, uf, st)
    return label[0] == label[3], st.welded_airside_faces


def test_an_apron_face_welds_its_labels_and_a_groundside_face_does_not(law):
    """The scope is the AIRSIDE APRON BODY roles, from the law tables: the
    apron and the junction body.  A GROUNDSIDE face (a lot, a road) keeps
    08k's joint — "terraces stay lawful groundside only" — and so does a
    rigid pad (its 28b pad|apron terrace is its own ruling)."""
    assert sorted(airside_apron_roles(law)) == ["apron", "junction"]
    for role in ("apron", "junction"):
        assert _weld(law, role) == (True, 1), role
    for role in ("parking_lot", "service_road", "groundside_pavement", "building"):
        assert _weld(law, role) == (False, 0), role


def test_the_08r2_step_at_a_road_far_edge_is_not_the_aprons_terrace(law):
    """Owner RULINGS 2026-09-08r-2, KEPT: a road running ALONG a boundary
    takes the level of the shape it is welded to and "the step stands at
    the road's FAR edge ... B's faces along it carry two labels and the
    contour hugs their edge inside B".  That second label reaches the
    apron face only through the road weld and the ROAD is the separator, so
    those vertices are not read here.  #189's pair has "no road within
    reach", so the weld reaches it."""
    assert _weld(law, "apron", road_ring=(2, 3)) == (False, 0)   # the minority is the road's
    assert _weld(law, "apron", road_ring=(3,)) == (True, 1)      # ... only partly: label 1 is on v2 too


# ── 2. the whole build: an apron face with a DEM step inside it ──────────

def test_an_apron_face_with_a_dem_step_inside_it_carries_no_terrace(law):
    """THE RULING, end to end.  One apron face (the dumbbell) whose mouth
    stands over a 5 m DEM drop: no joint is declared, the 29ac fallback row
    across the mouth's ring edge survives the filter, the solved step is
    inside the pavement cap, and the sidecar declares no terrace."""
    airport, pm, st, cl = _airport(law, _dumbbell(10.0), [], dem=_Bench(0.0, rise=MOUTH_DROP_M))
    # ONE shape, no contour, no gap midline, nothing for the sidecar
    assert st.shapes.shapes == 1 and not pm.shape_joints
    assert st.shapes.contours == 0 and st.shapes.gap_joints == 0
    assert st.shapes.orphans_earned == 0
    # the mouth's ring edge: two CONSECUTIVE ring vertices of the one apron
    # face, the shape of #189's pair
    a, b = _vid(pm, (-15.0, 165.0)), _vid(pm, (15.0, 165.0))
    assert not S.straddles(pm, (a, b))
    stage = shape_stage(pm, law, airport, cl, out=lambda _m: None)
    cs, _counts, _w = shape_constraints(pm, law, airport, stage)
    # THE ROWS ARE PRESENT (the rows #189 found missing) and the filter
    # withdrew none of them.  The 29ac fallback itself mints nothing on
    # this pair — it is "one hard row family over every pavement pair NOT
    # ALREADY CAPPED LOWER", and the apron's own 1.5 % row caps it — so
    # what the twin reads is the population the ruling restores: a hard
    # ``Diff`` at or under the fallback cap.  At #189's KCLT pair the apron
    # row was absent too and the fallback was the only family left, which is
    # why the issue names it.
    assert stage.dropped == {}, stage.dropped
    cap = pavement_fallback_cap(law)
    hard = [r for r in cs.rows() if isinstance(r, Diff) and r.soft is None
            and {r.a, r.b} == {a, b} and r.cap <= cap]
    assert hard, "no hard pavement row across the mouth's ring edge"
    assert {r.source.generator for r in hard} == {"apron", "pavement_ceiling"}
    assert stage.dropped.get(PAVCAP_GEN, 0) == 0
    # ... and the solve keeps the built step inside the pavement cap
    sol, rep = solve_design(pm, cs, law)
    assert sol.status in (Status.OPTIMAL, Status.FEASIBLE), rep.line()
    dist = math.dist(pm.vertices[a].xy, pm.vertices[b].xy)
    step = abs(float(sol.z[a]) - float(sol.z[b]))
    assert step <= cap * dist + 1e-6, (step, cap * dist)
    # the sidecar: no declared terrace anywhere on the apron
    pub = publication(pm, law, airport, sol.z)
    assert pub["terrace_joints"] == [], pub["terrace_joints"]


def test_the_189_mechanism_on_the_same_fixture_with_the_welds_withheld(law):
    """THE CONTROL — #189's mechanism, on the fixture above, with the apron
    body roles withheld from the law so neither weld fires (what main built
    before this ruling): the mouth earns 29k's in-face contour, the stage
    declares it, ``apply_joints`` withdraws EVERY row across it
    (``{'apron': 30, 'pavement_ceiling': 2, 'no_step': 4}``), the pair is
    left carrying NO ROW AT ALL, and the solve builds 4.85 m over 30.0 m =
    16.2 % against the 8 % road cap — #189's shape exactly (2.59 m over
    4.47 m = 57.9 %), declared lawful in the sidecar.

    This twin is the measurement the fix is read against; it is NOT a
    claim that the law may be configured this way."""
    emit = _dc.replace(law.tables.emit,
                       terrace=_dc.replace(law.tables.emit.terrace, one_shape_roles=()))
    off = Law(tables=_dc.replace(law.tables, emit=emit), ruleset_key=law.ruleset_key)
    airport, pm, st, cl = _airport(off, _dumbbell(10.0), [], dem=_Bench(0.0, rise=MOUTH_DROP_M))
    assert st.shapes.shapes == 2 and st.shapes.contours == 1
    assert st.shapes.welded_airside_faces == 0 and st.shapes.welded_same_role_mouths == 0
    a, b = _vid(pm, (-15.0, 165.0)), _vid(pm, (15.0, 165.0))
    assert S.straddles(pm, (a, b))
    stage = shape_stage(pm, off, airport, cl, out=lambda _m: None)
    cs, _counts, _w = shape_constraints(pm, off, airport, stage)
    assert stage.dropped.get("apron", 0) > 0 and stage.dropped.get("pavement_ceiling", 0) > 0
    assert not [r for r in cs.rows() if hasattr(r, "a") and {r.a, r.b} == {a, b}], \
        "the pair should carry no row at all — that is the defect"
    sol, rep = solve_design(pm, cs, off)
    assert sol.status in (Status.OPTIMAL, Status.FEASIBLE), rep.line()
    dist = math.dist(pm.vertices[a].xy, pm.vertices[b].xy)
    step = abs(float(sol.z[a]) - float(sol.z[b]))
    assert step / dist > pavement_fallback_cap(off), (step, dist)
    assert len(publication(pm, off, airport, sol.z)["terrace_joints"]) == 1


# ── 3. a GROUNDSIDE face with the same step keeps its joint ──────────────

def _lot_between_two_aprons():
    """Two apron rects 1.6 m apart (two shapes: ``test_pavement_apart_is_
    two_shapes``) bridged by a groundside ``parking_lot`` whose face is the
    strip between them (the apron wins the overlap by precedence), so the
    LOT's vertices carry both labels."""
    return [RUNWAY,
            Cell(1, "apron", "apronA", _rect(-200, Y0, -0.8, Y1), (), None, None, "airside", "apron", {}),
            Cell(2, "apron", "apronB", _rect(0.8, Y0, 200, Y1), (), None, None, "airside", "apron", {}),
            Cell(3, "parking_lot", "lot", _rect(-60, Y0, 60, Y1), (), None, None, "groundside", "apron", {})]


def test_a_groundside_face_with_the_same_step_keeps_its_joint(law):
    """"Terraces stay lawful groundside only": the contour through the LOT
    face between the two apron shapes is declared exactly as before, the
    airside weld never fires, and the sidecar carries the record."""
    airport, pm, st, cl = _airport(law, _lot_between_two_aprons(), [],
                                   dem=_Bench(0.0, rise=MOUTH_DROP_M))
    assert st.shapes.shapes == 2 and st.shapes.welded_airside_faces == 0
    (j,) = pm.shape_joints
    assert not j.gap and "parking_lot" in j.roles and len(set(j.shapes)) == 2
    stage = shape_stage(pm, law, airport, cl, out=lambda _m: None)
    cs, _c, _w = shape_constraints(pm, law, airport, stage)
    sol, rep = solve_design(pm, cs, law)
    assert sol.status in (Status.OPTIMAL, Status.FEASIBLE), rep.line()
    pub = publication(pm, law, airport, sol.z)
    recs = [r for r in pub["terrace_joints"] if r["kind"] == "apron_terrace"]
    assert len(recs) == 1 and recs[0]["shapes"] == list(j.shapes)
