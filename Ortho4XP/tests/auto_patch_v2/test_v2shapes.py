"""Twins for owner RULINGS 2026-09-08k (lane ``v2shapes``; spec §8): a SHAPE
is a connected component of touching / overlapping pavement — pavement
under ``terrace.separation_m`` apart is one shape; a connection through a
NARROW MOUTH (``narrow_mouth_max_m``) or a SERVICE ROAD does not join two
bodies; a JOINT exists only between two shapes and is declared so both
censuses read its step as lawful; inside a shape no joint exists and the
apron rows yield WITHOUT a ceiling (a shape with two route contacts far
apart by ceiling grades through at > 3 %, the rows reported); the taxi
chain yields where it meets a runway-family vertex (08i-1); ONE solve pass.

Retired with the withdrawn mechanisms: ``test_v2terrace.py`` (06n: the
station-joined partition, split copies, islands, the pad-on-island
frontage, the strip keep-out of a split), ``test_v2terrace3.py`` (07g:
serving contacts, the pairwise predicate, dead-end lanes, the fallback
links, the notch fallback) and the three 08d (3) step-law twins of
``test_v2chord.py``.  The strip keep-out survives as a weld of two bodies
(``test_a_boundary_inside_the_runway_strip_welds_the_bodies``)."""
from __future__ import annotations

import dataclasses as _dc
import math
import sys
from pathlib import Path

import pytest

from auto_patch_v2.classify.roles import Cell, Classification, CutLine
from auto_patch_v2.constraints.yielding import (GROUP, runway_vertices, yield_family,
                                                yielded_rows)
from auto_patch_v2.emit.graded import graded_surface
from auto_patch_v2.emit.osm_adapter import write_patch
from auto_patch_v2.law import Law, LawError
from auto_patch_v2.law.tables import yield_ceiling
from auto_patch_v2.law.terrace_schema import Terrace, check_terrace
from auto_patch_v2.model.airport import Airport, Runway, RunwayEnd, SceneryPack
from auto_patch_v2.model.constraints import ConstraintSet, Diff, Pin, Source
from auto_patch_v2.model.frame import Frame
from auto_patch_v2.pipeline.build import DEFAULT_WEIGHTS, weights_under_law
from auto_patch_v2.pipeline.publication import face_tags, publication
from auto_patch_v2.pipeline.shapes import joint_steps, shape_constraints, shape_stage
from auto_patch_v2.planar import shapes as S
from auto_patch_v2.planar.build import build
from auto_patch_v2.solve import Options, Status
from auto_patch_v2.solve.tiers import solve_law_ordered
from auto_patch_v2.verify.census import census_patch
from auto_patch_v2.verify.frame import Patch

ROOT = Path(__file__).resolve().parents[2]


def _rect(x0, y0, x1, y1):
    return ((x0, y0), (x1, y0), (x1, y1), (x0, y1))


class _Flat:
    provenance = {"synthetic": "flat 700"}

    def z(self, x: float, y: float) -> float:
        return 700.0

    def bounds(self):
        return (-5000.0, -5000.0, 5000.0, 5000.0)


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


def _airport(law, cells, cuts, dem=None):
    frame = Frame("ZZZZ", origin=(60.5, -135.5), identity_dp=11)
    ends = (RunwayEnd("09", (-600.0, 0.0), (60.5, -135.5), 0.0, 0.0, 700.0, "fixture"),
            RunwayEnd("27", (600.0, 0.0), (60.5, -135.5), 0.0, 0.0, 700.0, "fixture"))
    rw = Runway("09/27", 45.0, 1, ends, 3, "D")
    pack = SceneryPack("fixture", "apt.dat", "0", (), ())
    airport = Airport("ZZZZ", "Synthetic", frame, 700.0, (rw,), (), (), {},
                      (), (), (), (), (), (), (), pack, dem or _Flat(), law.ruleset_key)
    cl = Classification(tuple(cells), tuple(cuts), {}, ())
    pm, stats = build(airport, cl, law)
    return airport, pm, stats, cl


RUNWAY = Cell(0, "runway", "09/27", _rect(-600, -22.5, 600, 22.5), (), 3, "D", "airside", "runway", {})
#: the aprons stand beyond the code-3 strip (75 m) so the keep-out never touches them
Y0, Y1 = 120.0, 220.0


def _face(pm, ref):
    return next(f for f in pm.faces.values() if f.ref == ref)


def _vid(pm, xy):
    v = min(pm.vertices, key=lambda k: math.dist(pm.vertices[k].xy, xy))
    assert math.dist(pm.vertices[v].xy, xy) < 0.05, (xy, pm.vertices[v].xy)
    return v


def _shape_of(pm, xy):
    return pm.shape_of_vertex[_vid(pm, xy)]


def _apron_pair(gap: float):
    return [RUNWAY,
            Cell(1, "apron", "apronA", _rect(-200, Y0, -gap / 2.0, Y1), (), None, None, "airside", "apron", {}),
            Cell(2, "apron", "apronB", _rect(gap / 2.0, Y0, 200, Y1), (), None, None, "airside", "apron", {})]


# ── 1. touching / near pavement is ONE shape ─────────────────────────────

def test_pavement_under_the_separation_is_one_shape_with_no_joint(law):
    _ap, pm, st, _cl = _airport(law, _apron_pair(0.3), [])
    sh = st.shapes
    assert _shape_of(pm, (-200.0, Y0)) == _shape_of(pm, (200.0, Y0))
    assert pm.shape_of_face[_face(pm, "apronA").id] == pm.shape_of_face[_face(pm, "apronB").id]
    assert not pm.shape_joints and sh.joint_edges == 0
    assert sh.shapes == 2                                   # the aprons, and the runway


# ── 2. pavement apart is TWO shapes ──────────────────────────────────────

def test_pavement_apart_is_two_shapes(law):
    """DEVIATION reported (lane v2shapes): the 04u weld (``identity.weld_spacing_m``
    1.0 m, pre-snap) shares the vertices of any gap under ≈ 1 m, so the
    brief's 0.6 m gap is welded into ONE shape; ``separation_m`` (0.5)
    governs only unwelded pavement.  The twin stands at 1.6 m (1.5 m
    after the 0.5 m identity snap)."""
    _ap, pm, st, _cl = _airport(law, _apron_pair(1.6), [])
    assert _shape_of(pm, (-200.0, Y0)) != _shape_of(pm, (200.0, Y0))
    assert st.shapes.shapes == 3
    # wider than the step readers' contact horizon (1 m): no reader prices
    # the gap, no joint is declared
    assert not pm.shape_joints


def test_a_gap_inside_the_readers_horizon_declares_a_midline_joint(law):
    """The gap joint: with the readers' horizon widened past the gap the
    midline between the two shapes is declared, its pairs across it."""
    emit = _dc.replace(law.tables.emit,
                       instrument=_dc.replace(law.tables.emit.instrument, step_contact_tol_m=2.0))
    wide = Law(tables=_dc.replace(law.tables, emit=emit), ruleset_key=law.ruleset_key)
    _ap, pm, st, _cl = _airport(wide, _apron_pair(1.2), [])
    assert st.shapes.gap_joints >= 1 and st.shapes.contours == 0
    gaps = [j for j in pm.shape_joints if j.gap]
    xs = [x for j in gaps for x, _y in j.points]
    assert max(abs(x) for x in xs) < 0.7, xs                 # the midline of the 1.2 m gap
    assert all(j.pairs and all(S.straddles(pm, p) for p in j.pairs) for j in gaps)
    ys = [y for j in gaps for _x, y in j.points]
    assert min(ys) < Y0 + 1.0 and max(ys) > Y1 - 1.0        # the whole facing run
    assert sum(j.length_m for j in gaps) > 0.9 * (Y1 - Y0)  # ... as one line, not scraps


# ── 3. narrow mouth: two bodies; a wide neck: one ────────────────────────

def _dumbbell(neck_w: float):
    h = neck_w / 2.0
    ring = ((-150, Y0), (-15, Y0), (-15, 170 - h), (15, 170 - h), (15, Y0), (150, Y0),
            (150, Y1), (15, Y1), (15, 170 + h), (-15, 170 + h), (-15, Y1), (-150, Y1))
    return [RUNWAY, Cell(1, "apron", "dumbbell", ring, (), None, None, "airside", "apron", {})]


def test_a_narrow_mouth_separates_two_bodies_with_a_joint_across_it(law):
    _ap, pm, st, _cl = _airport(law, _dumbbell(10.0), [])
    assert _shape_of(pm, (-150.0, Y0)) != _shape_of(pm, (150.0, Y0))
    assert st.shapes.bodies >= 3 and st.shapes.contours == 1
    (j,) = pm.shape_joints
    assert not j.gap and "apron" in j.roles
    xs = [x for x, _y in j.points]
    ys = [y for _x, y in j.points]
    assert max(abs(x) for x in xs) <= 15.0 + 1.0, xs         # across the neck
    assert min(ys) <= 165.0 + 1.0 and max(ys) >= 175.0 - 1.0
    assert j.pairs and all(S.straddles(pm, p) for p in j.pairs)


def test_a_wide_neck_joins_the_bodies(law):
    _ap, pm, st, _cl = _airport(law, _dumbbell(20.0), [])
    assert _shape_of(pm, (-150.0, Y0)) == _shape_of(pm, (150.0, Y0))
    assert not pm.shape_joints and st.shapes.shapes == 2


# ── 4. a service road between two aprons separates them ─────────────────

def test_a_service_road_between_two_aprons_separates_them(law):
    cells = [RUNWAY,
             Cell(1, "apron", "apronA", _rect(-200, Y0, -4, Y1), (), None, None, "airside", "apron", {}),
             Cell(2, "service_road", "road", _rect(-4, Y0, 4, Y1), (), None, None, "airside", "strip", {}),
             Cell(3, "apron", "apronB", _rect(4, Y0, 200, Y1), (), None, None, "airside", "apron", {})]
    airport, pm, st, cl = _airport(law, cells, [])
    assert _shape_of(pm, (-200.0, Y0)) != _shape_of(pm, (200.0, Y0))
    assert st.shapes.contours == 1 and st.shapes.road_vertices_labelled >= 0
    (j,) = pm.shape_joints
    assert "service_road" in j.roles and not j.gap
    assert max(abs(x) for x, _y in j.points) <= 4.0 + 1.0
    stage = shape_stage(pm, law, airport, cl, out=lambda _m: None)
    cs, counts, _w = shape_constraints(pm, law, airport, stage)
    assert stage.dropped.get("roads", 0) >= 1, stage.dropped   # the road's rows stop at the joint
    for r in cs.rows():
        ids = S.row_vertices(r)
        assert not (len(ids) >= 2 and S.straddles(pm, ids)) or r.source.generator in ("pads", "flat_site"), r
    z = [700.0 if pm.vertices[v].xy[0] < 0.0 else 703.0 for v in range(len(pm.vertices))]
    js = joint_steps(pm, law, stage, z)
    assert js["roads"] and js["roads"][0]["role"] == "service_road"
    assert js["contours"][0]["step_m"] == pytest.approx(3.0)


# ── 5. inside a shape: no joint, the apron grades through at > 3 % ───────

@pytest.fixture(scope="module")
def two_contacts(law):
    """One apron with two runway-connected contacts: a short west stub and a
    long east L-taxiway (their ceilings ≈ 23 m apart)."""
    apron = Cell(1, "apron", "apron", _rect(-150, Y0, 150, 180), (), None, None, "airside", "apron", {})
    stub_w = Cell(2, "stub", "stubW", _rect(-161.5, 22.5, -138.5, Y0), (), None, "D", "airside", "taxi", {})
    top = 900.0
    ring = ((588.5, 22.5), (611.5, 22.5), (611.5, top + 11.5), (138.5, top + 11.5),
            (138.5, 180), (161.5, 180), (161.5, top - 11.5), (588.5, top - 11.5))
    stub_e = Cell(3, "stub", "stubE", ring, (), None, "D", "airside", "taxi", {})
    cuts = [CutLine("taxi_centerline", "stubW", ((-150.0, 0.0), (-150.0, Y0 + 25.0)), "D"),
            CutLine("taxi_centerline", "stubE", ((600.0, 0.0), (600.0, top), (150.0, top), (150.0, 180 - 25.0)), "D")]
    return _airport(law, [RUNWAY, apron, stub_w, stub_e], cuts)


def test_two_route_contacts_in_one_shape_make_no_joint_and_the_apron_grades_through(two_contacts, law):
    airport, pm, st, cl = two_contacts
    assert _shape_of(pm, (-150.0, Y0)) == _shape_of(pm, (150.0, 180.0))
    assert not pm.shape_joints, "no joint inside a shape (08k (2))"
    stage = shape_stage(pm, law, airport, cl, out=lambda _m: None)
    cs, counts, _w = shape_constraints(pm, law, airport, stage)
    assert stage.dropped == {} and counts["yield.apron"] > 0
    assert stage.bands_withdrawn > 0                     # the in-shape band is not a row (07g (2))
    # the two contacts 12 m apart over ~300 m of apron: 4 %
    a, b = _vid(pm, (-150.0, Y0 + 25.0)), _vid(pm, (150.0, 180.0 - 25.0))
    src = Source("fixture", "pin")
    pinned = cs.merged(ConstraintSet.from_rows([Pin(a, 700.0, src), Pin(b, 712.0, src)]))
    w = weights_under_law(DEFAULT_WEIGHTS, law)
    sol, rep = solve_law_ordered(pm, pinned, law, w, Options(diagnose_iis=False))
    assert sol.status in (Status.OPTIMAL, Status.FEASIBLE) and rep.mode == "hard", rep.line()
    yr = yielded_rows(pinned, sol.z, law, pm)
    assert yr["families"]["apron"]["max_grade"] > 0.03, yr["families"]["apron"]
    assert yr["families"]["apron"]["yielded"] >= 1
    sid = pm.shape_of_vertex[a]
    assert yr["by_shape"][sid]["max_grade"] > 0.03 and yr["by_shape"][sid]["yielded"] >= 1
    # no step: every apron ring edge holds a grade, none a cliff
    steps = [abs(sol.z[e.a] - sol.z[e.b]) / math.dist(pm.vertices[e.a].xy, pm.vertices[e.b].xy)
             for e in pm.edges.values() if pm.faces[e.left_face or e.right_face].role == "apron"]
    assert max(steps) < 0.10, max(steps)


# ── 6. the joint's step reads lawful in both censuses ────────────────────

def test_the_step_across_a_shape_joint_is_lawful_in_both_censuses(law, tmp_path):
    airport, pm, st, cl = _airport(law, _dumbbell(10.0), [])
    stage = shape_stage(pm, law, airport, cl, out=lambda _m: None)
    cs, _c, _w = shape_constraints(pm, law, airport, stage)
    a, b = _vid(pm, (-150.0, Y0)), _vid(pm, (150.0, Y0))
    src = Source("fixture", "pin")
    pinned = cs.merged(ConstraintSet.from_rows([Pin(a, 700.0, src), Pin(b, 705.0, src)]))
    w = weights_under_law(DEFAULT_WEIGHTS, law)
    sol, rep = solve_law_ordered(pm, pinned, law, w, Options(diagnose_iis=False))
    assert sol.status in (Status.OPTIMAL, Status.FEASIBLE), rep.line()
    steps = [abs(sol.z[p] - sol.z[q]) for p, q, _r, _s in stage.edges]
    # the two bodies at their own levels: a step across the neck well over
    # the 0.5 m step materiality (the apron preference ramps each body
    # toward the neck, so the built step is under the 5 m pinned)
    assert max(steps) > 2.0, steps
    surf = graded_surface(pm, law, sol, airport.frame.origin, airport.frame.crs)
    pub = publication(pm, law, airport, sol.z)
    recs = pub["terrace_joints"]
    assert len(recs) == 1 and recs[0]["kind"] == "apron_terrace" and recs[0]["faced"] is False
    assert recs[0]["step_m"] >= max(steps) - 0.011 and recs[0]["shapes"] == list(pm.shape_joints[0].shapes)
    for key in ("airside_no_step_edges", "pad_pavement_no_step_edges"):
        for e in pub[key]:
            ids = [_vid(pm, pm.vertices[v].xy) for v in ()]
            del ids
    p = Patch.of(surf, law, pub)
    rows = census_patch(p)
    for fam in ("vertex_to_edge_step", "mid_edge_step", "cross_shape", "stacked_nodes",
                "within_shape", "airside_no_step"):
        assert not rows[fam], (fam, rows[fam][:2])
    p0 = Patch.of(surf, law, {k: v for k, v in pub.items() if k != "terrace_joints"})
    rows0 = census_patch(p0)
    assert rows0["within_shape"], "the ring edge across the neck is a step the cap cannot hold"
    paths = write_patch(surf, law, tmp_path, pub, face_tags=face_tags(pm, law))
    sys.path.insert(0, str(ROOT / "tools" / "harness"))
    sys.path.insert(0, str(ROOT / "tools"))
    cg = pytest.importorskip("check_grade")
    ctx = cg.law_context_from_sidecar(paths.patch)
    assert ctx["terrace_joints_ll"] and len(ctx["terrace_joints_ll"]) == 1
    fam: dict = {}
    cg.run_checks_law_true(paths.patch, family_out=fam, quiet=True, top_n=0)
    for key in ("terrace_joint_route", "terrace_joint_strip", "vertex_to_edge_step",
                "mid_edge_step", "cross_shape", "stacked_nodes", "within_shape"):
        assert not fam.get(key), (key, fam.get(key)[:2])
    fam0: dict = {}
    cg.run_checks_law_true(paths.patch, family_out=fam0, quiet=True, top_n=0,
                           terrace_joints_ll=None)
    assert fam0.get("within_shape")


# ── 7. the strip keep-out welds two bodies ───────────────────────────────

def test_a_boundary_inside_the_runway_strip_welds_the_bodies(law):
    """A 10 m neck beside the runway (inside the code-3 strip, the bodies
    7.5 m off the runway edge so the runway itself joins nothing): the two
    bodies weld — walls at runway edges are never lawful."""
    h = 5.0
    ring = ((-150, 30), (-15, 30), (-15, 60 - h), (15, 60 - h), (15, 30), (150, 30),
            (150, 100), (15, 100), (15, 60 + h), (-15, 60 + h), (-15, 100), (-150, 100))
    cells = [RUNWAY, Cell(1, "apron", "dumbbell", ring, (), None, None, "airside", "apron", {})]
    _ap, pm, st, _cl = _airport(law, cells, [])
    assert st.shapes.welded_strip_pairs >= 1
    assert _shape_of(pm, (-150.0, 100.0)) == _shape_of(pm, (150.0, 100.0))
    assert not pm.shape_joints


# ── 8. the chain yields at the runway (08i-1) ────────────────────────────

def test_the_taxi_chain_yields_where_it_meets_a_runway_vertex(law):
    cells = [RUNWAY,
             Cell(1, "stub", "stubA", _rect(-111.5, 22.5, -88.5, Y0), (), None, "D", "airside", "taxi", {}),
             Cell(2, "apron", "apronA", _rect(-200, Y0, 0, Y1), (), None, None, "airside", "apron", {})]
    cuts = [CutLine("taxi_centerline", "stubA", ((-100.0, 0.0), (-100.0, Y0 + 25.0)), "D")]
    airport, pm, st, cl = _airport(law, cells, cuts)
    stage = shape_stage(pm, law, airport, cl, out=lambda _m: None)
    cs, counts, _w = shape_constraints(pm, law, airport, stage)
    assert counts["yield.taxi_chain_at_runway"] > 0
    rw = runway_vertices(pm, law)
    at_rw = [r for r in cs.rows() if yield_family(r) == "taxi_chain_at_runway"]
    assert at_rw and any(isinstance(r, Diff) for r in at_rw)
    for r in at_rw:
        if isinstance(r, Diff):                       # a hop / chord: the ceiling is the grade
            assert r.ceiling == pytest.approx(yield_ceiling(law, "taxi_chain_at_runway"))
        else:                                         # a foot row: the metres its bound may rise
            assert r.ceiling is not None and r.ceiling > 0.0
        assert r.source.generator == "taxi" and "crossing" not in r.source.ruling
        assert any(v in rw for v in S.row_vertices(r))
    # every other chain row stays hard
    for r in cs.rows():
        if r.source.generator == "taxi" and "box" not in r.source.ruling and yield_family(r) is None:
            assert getattr(r, "soft", None) is None
            if isinstance(r, Diff) and "chain" in r.source.ruling:
                assert not (r.a in rw or r.b in rw) or "crossing" in r.source.ruling


# ── 9. the law tables ────────────────────────────────────────────────────

def test_the_law_table_carries_the_shape_keys(law):
    tt = law.tables.emit.terrace
    assert tt.separation_m > 0.0 and tt.narrow_mouth_max_m > tt.separation_m
    assert {"apron", "runway", "stub"} <= set(tt.shape_roles)
    assert "service_road" not in tt.shape_roles                 # a road separates
    assert "apron" in tt.band_roles
    assert yield_ceiling(law, "apron") is None                  # 08k (3): no ceiling inside a shape
    assert "taxi_chain_at_runway" in law.tables.emit.yielding.families
    good = Terrace(0.5, 12.0, ("apron",), ("apron",))
    check_terrace(good, {"apron"}, LawError)
    with pytest.raises(LawError):
        check_terrace(_dc.replace(good, narrow_mouth_max_m=0.4), {"apron"}, LawError)
    with pytest.raises(LawError):
        check_terrace(_dc.replace(good, shape_roles=("zzz",)), {"apron"}, LawError)
    for r in ("junction_mesh", "taxi_box", "no_step_pairs", "roads"):
        assert yield_ceiling(law, r) is not None
