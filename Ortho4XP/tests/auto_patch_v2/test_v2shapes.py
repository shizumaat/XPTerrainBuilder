"""Twins for owner RULINGS 2026-09-08k (lane ``v2shapes``; spec §8): a SHAPE
is a connected component of touching / overlapping pavement — pavement
under ``terrace.separation_m`` apart is one shape; a connection through a
NARROW MOUTH (``narrow_mouth_max_m``) or a SERVICE ROAD does not join two
bodies; a JOINT exists only between two shapes and is declared so both
censuses read its step as lawful; inside a shape no joint exists and the
apron rows yield WITHOUT a ceiling (a shape with two route contacts far
apart by ceiling grades through at > 3 %, the rows reported); the taxi
chain yields where it meets a runway-family vertex (08i-1), with NO ceiling
(08r-1); a road between two shapes belongs to neither — along a boundary
it takes its shape's level and the step stands at its far edge, crossing
it ramps at the road cap with no joint (08r-2); ONE solve pass.

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
from auto_patch_v2.constraints.yielding import (GROUP, NETWORK_HARD_CLASSES, NETWORK_YIELDS, runway_vertices,
                                                yield_family, yielded_rows)
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
    assert sh.shapes == 1                                   # the aprons; the runway is NETWORK (08p)
    assert sh.network_faces >= 1 and sh.network_by_role.get("runway", 0) >= 1


# ── 2. pavement apart is TWO shapes ──────────────────────────────────────

def test_pavement_apart_is_two_shapes(law):
    """DEVIATION reported (lane v2shapes): the 04u weld (``identity.weld_spacing_m``
    1.0 m, pre-snap) shares the vertices of any gap under ≈ 1 m, so the
    brief's 0.6 m gap is welded into ONE shape; ``separation_m`` (0.5)
    governs only unwelded pavement.  The twin stands at 1.6 m (1.5 m
    after the 0.5 m identity snap)."""
    _ap, pm, st, _cl = _airport(law, _apron_pair(1.6), [])
    assert _shape_of(pm, (-200.0, Y0)) != _shape_of(pm, (200.0, Y0))
    assert st.shapes.shapes == 2
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
    assert st.shapes.bodies == 2 and st.shapes.contours == 1   # the runway is no body (08p)
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
    assert not pm.shape_joints and st.shapes.shapes == 1


# ── 4. a service road between two aprons separates them ─────────────────

def _road_between(y_b0: float, y_b1: float):
    """apronA the full height west of a 8 m road, its road edge drawn every
    20 m; apronB east of it between ``y_b0``..``y_b1`` (shorter: A shares
    MORE of the road's vertices — the weld side, 08r-2)."""
    ring_a = ((-200, Y0), (-4, Y0)) + tuple((-4, y) for y in range(int(Y0) + 20, int(Y1), 20)) + ((-4, Y1), (-200, Y1))
    return [RUNWAY,
            Cell(1, "apron", "apronA", ring_a, (), None, None, "airside", "apron", {}),
            Cell(2, "service_road", "road", _rect(-4, Y0, 4, Y1), (), None, None, "airside", "strip", {}),
            Cell(3, "apron", "apronB", _rect(4, y_b0, 200, y_b1), (), None, None, "airside", "apron", {})]


def test_a_road_along_a_boundary_takes_its_shapes_level_and_the_step_stands_at_its_far_edge(law, tmp_path):
    """Owner RULINGS 2026-09-08r-2: the road is welded to apronA (more shared
    vertices) and takes ITS level; the step stands at the road's far edge —
    inside apronB, whose vertices on the road carry A's label."""
    airport, pm, st, cl = _airport(law, _road_between(Y0 + 30.0, Y1 - 30.0), [])
    road = _face(pm, "road")
    A, B = _shape_of(pm, (-200.0, Y0)), _shape_of(pm, (200.0, Y1 - 30.0))
    assert A != B and st.shapes.roads_along >= 1 and st.shapes.roads_crossing == 0
    assert not pm.road_ramps
    for v in S._face_vertices(pm, road.id):                  # the whole road: A's level
        assert pm.shape_of_vertex.get(v, S.NO_SHAPE) == A, (v, pm.vertices[v].xy)
    assert pm.shape_of_face[road.id] == A
    (j,) = pm.shape_joints
    assert not j.gap and set(j.shapes) == {A, B}
    assert min(x for x, _y in j.points) >= 4.0 - 0.01, "the contour stands inside apronB, never on the road"
    for a, b, ra, rb in st.shapes and S.joint_planar_edges(pm):
        assert "service_road" not in (ra, rb) or "apron" in (ra, rb)
    stage = shape_stage(pm, law, airport, cl, out=lambda _m: None)
    cs, counts, _w = shape_constraints(pm, law, airport, stage)
    assert stage.dropped.get("roads", 0) == 0, stage.dropped   # the road's rows are intact
    assert stage.dropped.get("apron", 0) > 0                   # apronB's rows from its road edge inward
    a, b = _vid(pm, (-200.0, Y0)), _vid(pm, (200.0, Y1 - 30.0))
    src = Source("fixture", "pin")
    pinned = cs.merged(ConstraintSet.from_rows([Pin(a, 700.0, src), Pin(b, 704.0, src)]))
    w = weights_under_law(DEFAULT_WEIGHTS, law)
    sol, rep = solve_law_ordered(pm, pinned, law, w, Options(diagnose_iis=False))
    assert sol.status in (Status.OPTIMAL, Status.FEASIBLE), rep.line()
    zr = [sol.z[v] for v in S._face_vertices(pm, road.id)]
    assert max(zr) - min(zr) < 0.5, "the road at one level (A's)"
    js = joint_steps(pm, law, stage, sol.z)
    assert not js["roads"] and not js["ramps"]
    assert js["contours"][0]["step_m"] > 2.0
    # both censuses: the road reads lawful; apronB's step reads as its joint
    surf = graded_surface(pm, law, sol, airport.frame.origin, airport.frame.crs)
    pub = publication(pm, law, airport, sol.z)
    from auto_patch_v2.constraints.roads import road_law_caps
    p = Patch.of(surf, law, pub, road_law_caps(pm, law, airport))
    rows = census_patch(p)
    for fam in ("within_shape", "road_cross_section", "airside_no_step", "vertex_to_edge_step"):
        assert not [r for r in rows[fam] if "service_road" in r["roles"]], (fam, rows[fam][:2])
    assert not [r for r in rows["within_shape"] if r["roles"] == "apron|apron"], rows["within_shape"][:2]
    paths = write_patch(surf, law, tmp_path, pub, face_tags=face_tags(pm, law))
    sys.path.insert(0, str(ROOT / "tools" / "harness"))
    sys.path.insert(0, str(ROOT / "tools"))
    cg = pytest.importorskip("check_grade")
    fam: dict = {}
    cg.run_checks_law_true(paths.patch, family_out=fam, quiet=True, top_n=0)
    for key in ("within_shape", "road_cross_section", "terrace_joint_route", "vertex_to_edge_step"):
        assert not [r for r in (fam.get(key) or []) if "service_road" in str(r)], (key, fam.get(key)[:2])


def _crossing_road():
    """apronA west, apronB east, 200 m apart; a 6 m road crossing between them."""
    return [RUNWAY,
            Cell(1, "apron", "apronA", _rect(-300, Y0, -100, Y1), (), None, None, "airside", "apron", {}),
            Cell(2, "service_road", "road", _rect(-100, 160, 100, 166), (), None, None, "airside", "strip", {}),
            Cell(3, "apron", "apronB", _rect(100, Y0, 300, Y1), (), None, None, "airside", "apron", {})]


def test_a_road_crossing_between_two_shapes_ramps_at_its_cap_with_no_joint(law):
    """Owner RULINGS 2026-09-08r-2: a crossing road belongs to NEITHER shape —
    unlabelled, every row kept, it ramps along its length at the road cap
    (8 %); no contour touches it; a road too short to ramp the difference
    is named."""
    airport, pm, st, cl = _airport(law, _crossing_road(), [])
    road = _face(pm, "road")
    A, B = _shape_of(pm, (-300.0, Y0)), _shape_of(pm, (300.0, Y0))
    assert A != B and st.shapes.roads_crossing == 1 and st.shapes.road_ramps == 1
    (ramp,) = pm.road_ramps
    assert ramp.face == road.id and set(ramp.shapes) == {A, B} and ramp.length_m == pytest.approx(200.0, abs=1.0)
    for v in S._face_vertices(pm, road.id):
        assert pm.shape_of_vertex.get(v, S.NO_SHAPE) == S.NO_SHAPE
    assert road.id not in pm.shape_of_face
    assert not pm.shape_joints and st.shapes.joint_edges == 0
    stage = shape_stage(pm, law, airport, cl, out=lambda _m: None)
    cs, counts, _w = shape_constraints(pm, law, airport, stage)
    assert stage.dropped == {}, stage.dropped
    assert yield_ceiling(law, "roads") == pytest.approx(0.08)
    # the two shapes 8 m apart AT THE ROAD's contacts: the road carries the
    # difference over its 200 m (4 %, past the 1.5 % it inherits from the
    # aprons by contiguity, under its own 8 % cap)
    a, b = ramp.contacts_a[0], ramp.contacts_b[0]
    src = Source("fixture", "pin")
    pinned = cs.merged(ConstraintSet.from_rows([Pin(a, 700.0, src), Pin(b, 708.0, src)]))
    w = weights_under_law(DEFAULT_WEIGHTS, law)
    sol, rep = solve_law_ordered(pm, pinned, law, w, Options(diagnose_iis=False))
    assert sol.status in (Status.OPTIMAL, Status.FEASIBLE) and rep.mode == "hard", rep.line()
    js = joint_steps(pm, law, stage, sol.z)
    (rr,) = js["ramps"]
    assert rr["face"] == road.id and rr["cap"] == pytest.approx(0.08)
    assert 0.03 < rr["grade"] <= 0.08 + 1e-6 and not rr["too_short"], rr
    # no step anywhere on the road: a grade along its length under the cap
    for e in pm.edges.values():
        if road.id in (e.left_face, e.right_face):
            d = math.dist(pm.vertices[e.a].xy, pm.vertices[e.b].xy)
            assert abs(sol.z[e.a] - sol.z[e.b]) <= 0.08 * d + 0.02, (e.a, e.b)
    # too short: the shapes 30 m apart over 200 m of road — the road at its cap
    z = [700.0 if pm.vertices[v].xy[0] < 0.0 else 730.0 for v in range(len(pm.vertices))]
    (rr2,) = joint_steps(pm, law, stage, z)["ramps"]
    assert rr2["too_short"] and rr2["ref"] == "road"


def test_two_road_pieces_along_different_shapes_become_one_ramp(law):
    """A road in two edge-adjacent pieces, each welded to a different shape,
    would carry the step on their shared edge — a wall across the road
    (HECA route8): the pair is a crossing."""
    cells = [RUNWAY,
             Cell(1, "apron", "apronA", _rect(-300, Y0, -100, Y1), (), None, None, "airside", "apron", {}),
             Cell(2, "service_road", "roadW", _rect(-100, 160, 0, 166), (), None, None, "airside", "strip", {}),
             Cell(3, "service_road", "roadE", _rect(0, 160, 100, 166), (), None, None, "airside", "strip", {}),
             Cell(4, "apron", "apronB", _rect(100, Y0, 300, Y1), (), None, None, "airside", "apron", {})]
    _ap, pm, st, _cl = _airport(law, cells, [])
    assert st.shapes.roads_crossing == 2 and st.shapes.road_ramps == 1
    assert not pm.shape_joints and st.shapes.joint_edges == 0
    for ref in ("roadW", "roadE"):
        for v in S._face_vertices(pm, _face(pm, ref).id):
            assert pm.shape_of_vertex.get(v, S.NO_SHAPE) == S.NO_SHAPE


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
    assert _shape_of(pm, (-150.0, 180.0)) == _shape_of(pm, (150.0, Y0))
    for xy in ((-150.0, Y0), (150.0, 180.0)):                # the stub contacts: N (08p)
        assert pm.shape_of_vertex.get(_vid(pm, xy), S.NO_SHAPE) == S.NO_SHAPE
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

def test_the_taxi_chain_at_the_runway_has_no_ceiling_and_what_holds_the_contact(law):
    """Owner RULINGS 2026-09-08i-1 / 08r-1: at a runway contact the chain
    yields with NO ceiling; the ceiling stays everywhere else.  MEASURED
    (lane v2shapes round 3): the contact still cannot grade past 1.5 % —
    a 3 % first hop is INFEASIBLE in the hard set, the IIS naming the
    short-pair BOX (the taxi class, hard on the network — 08p) and, behind
    it, the ``no_step`` §1.2 RATE law (not a yield family).
    The twin pins that attribution: when it fails, the contact has been
    freed and the 05L/23R hump (spec §12) is worth re-measuring."""
    cells = [RUNWAY,
             Cell(1, "stub", "stubA", _rect(-111.5, 22.5, -88.5, Y0), (), None, "D", "airside", "taxi", {}),
             Cell(2, "apron", "apronA", _rect(-200, Y0, 0, Y1), (), None, None, "airside", "apron", {})]
    cuts = [CutLine("taxi_centerline", "stubA", ((-100.0, 0.0), (-100.0, Y0 + 25.0)), "D")]
    airport, pm, st, cl = _airport(law, cells, cuts)
    stage = shape_stage(pm, law, airport, cl, out=lambda _m: None)
    cs, counts, _w = shape_constraints(pm, law, airport, stage)
    assert counts["yield.taxi_chain_at_runway"] > 0
    assert yield_ceiling(law, "taxi_chain_at_runway") is None      # 08r-1: no ceiling
    assert yield_ceiling(law, "taxi_box") == pytest.approx(0.03)   # kept elsewhere
    rw = runway_vertices(pm, law)
    at_rw = [r for r in cs.rows() if yield_family(r) == "taxi_chain_at_runway"]
    assert at_rw and any(isinstance(r, Diff) for r in at_rw)
    for r in at_rw:
        assert r.ceiling is None, r
        assert r.source.generator == "taxi" and "crossing" not in r.source.ruling
        assert any(v in rw for v in S.row_vertices(r))
    for r in cs.rows():                                   # every other chain row stays hard
        if r.source.generator == "taxi" and "box" not in r.source.ruling and yield_family(r) is None:
            assert getattr(r, "soft", None) is None
            if isinstance(r, Diff) and "chain" in r.source.ruling:
                assert not (r.a in rw or r.b in rw) or "crossing" in r.source.ruling
    # the runway demands 3 % over the first hop (the runway-edge station to
    # the next): the contact chain would yield, the rate law does not
    stations = sorted({v for b in pm.breaklines.values() if b.kind == S.STATION_KIND
                       for v in b.vertices(pm)}, key=lambda v: pm.vertices[v].xy[1])
    a = [v for v in stations if v in rw][-1]
    b = stations[stations.index(a) + 1]
    d = math.dist(pm.vertices[a].xy, pm.vertices[b].xy)
    src = Source("fixture", "pin")
    pinned = cs.merged(ConstraintSet.from_rows([Pin(a, 700.0, src), Pin(b, 700.0 + 0.03 * d, src)]))
    w = weights_under_law(DEFAULT_WEIGHTS, law)
    sol, rep = solve_law_ordered(pm, pinned, law, w, Options(diagnose_iis=True))
    assert rep.mode != "hard", rep.line()
    named = {(u["family"], u["ruling"].split(" (")[0].split(" |")[0]) for u in rep.relaxation["unrelaxed"]}
    holders = {("taxi", "short-pair box"), ("no_step", "airside_no_step §1.2 rate"),
               ("no_step", "airside_no_step §1.1 route pairs")}
    assert named & holders, named                       # the network-hard taxi class / the rate law
    assert not any("chain" in r or "centreline" in r for _f, r in named), named   # never the (soft) chain
    # the report reads the contact: a synthetic 5 % hop is the contact's max
    z = list(sol.z)
    z[b] = z[a] + 0.05 * d
    rc = yielded_rows(pinned, z, law, pm)["runway_contacts"]
    assert rc and rc[0]["vertex"] == a and rc[0]["max_grade"] == pytest.approx(0.05, abs=1e-3)


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
    # 08r-1: the runway contact states no ceiling; the round-2 knob is gone
    y = law.tables.emit.yielding
    assert y.families["taxi_chain_at_runway"] == "runway_contact" and y.ceiling("runway_contact") is None
    assert not hasattr(y, "network_hard_classes")
    from auto_patch_v2.law.yield_schema import check_yield
    with pytest.raises(LawError):
        check_yield(_dc.replace(y, runway_contact_yield_max=0.05), LawError)
    check_yield(y, LawError)


# ── 10. SHAPES ARE APRON BODIES; THE NETWORK CONNECTS THEM BY ROUTE (08p) ──

def _stub(k, ref, x, y0, y1):
    return Cell(k, "stub", ref, _rect(x - 11.5, y0, x + 11.5, y1), (), None, "D", "airside", "taxi", {})


def _cut(ref, pts):
    """A centreline that CROSSES its pavement end to end (a line ending
    inside a face splits nothing: polygonize needs both crossings — the
    real 1202 network's dangling ends are the arrangement's own affair)."""
    return CutLine("taxi_centerline", ref, tuple(pts), "D")


@pytest.fixture(scope="module")
def through_taxiway(law):
    """Two aprons touching only through a runway-connected taxiway: the
    west apron hangs off the taxiway's west edge, the east apron off its
    east edge; the taxiway runs from the runway up between them."""
    cells = [RUNWAY,
             _stub(1, "taxi", 0.0, 22.5, Y1),
             Cell(2, "apron", "apronW", _rect(-200, Y0, -11.5, Y1), (), None, None, "airside", "apron", {}),
             Cell(3, "apron", "apronE", _rect(11.5, Y0, 200, Y1), (), None, None, "airside", "apron", {})]
    return _airport(law, cells, [_cut("taxi", [(0.0, 0.0), (0.0, Y1 + 5.0)])])


def test_two_aprons_touching_only_through_a_taxiway_are_two_shapes_with_no_joint(through_taxiway, law):
    airport, pm, st, cl = through_taxiway
    sh = st.shapes
    taxi = _face(pm, "taxi")
    assert taxi.id not in pm.shape_of_face                  # the network has no shape
    assert sh.network_by_role.get("stub") == 2 and sh.connected_stations >= 2   # the centreline splits the stub
    assert _shape_of(pm, (-200.0, Y0)) != _shape_of(pm, (200.0, Y0))
    assert sh.shapes == 2 and not pm.shape_joints and sh.joint_edges == 0
    # every vertex of the taxiway — the aprons' edges on it included — is N
    for v in (_vid(pm, (-11.5, Y0)), _vid(pm, (11.5, Y1)), _vid(pm, (0.0, 22.5))):
        assert pm.shape_of_vertex.get(v, S.NO_SHAPE) == S.NO_SHAPE
    stage = shape_stage(pm, law, airport, cl, out=lambda _m: None)
    cs, counts, _w = shape_constraints(pm, law, airport, stage)
    # the taxiway's own rows are never dropped: it couples the two shapes
    # by ROUTE (its chain, its transverse law) — only rows joining the two
    # bodies directly across it are
    assert stage.dropped.get("taxi", 0) == 0, stage.dropped
    N = S.network_vertices(pm, law)
    assert sum(1 for r in cs.rows() if r.source.generator == "taxi"
               and all(v in N for v in S.row_vertices(r)) and getattr(r, "soft", None) is None) > 0
    assert counts["yield.taxi_box.network_hard"] > 0 and counts["yield.no_step_pairs.network_hard"] > 0
    # THE NETWORK IS HARD (08p (2)): no yielded TAXI-class row lies wholly
    # on the taxiway (an apron ring edge along it is the body's own law)
    for r in cs.rows():
        fam = yield_family(r)
        if fam is not None and fam not in NETWORK_YIELDS and law.tables.emit.yielding.families.get(fam) == "taxi":
            assert not all(v in N for v in S.row_vertices(r)), (fam, r)
    assert "taxi" in NETWORK_HARD_CLASSES and yield_ceiling(law, "taxi_box") is not None
    # the two shapes are coupled through the taxiway: pin the west apron
    # and the east one 6 m apart — the solve grades the taxiway between
    a, b = _vid(pm, (-200.0, Y0)), _vid(pm, (200.0, Y0))
    src = Source("fixture", "pin")
    pinned = cs.merged(ConstraintSet.from_rows([Pin(a, 700.0, src), Pin(b, 706.0, src)]))
    w = weights_under_law(DEFAULT_WEIGHTS, law)
    sol, rep = solve_law_ordered(pm, pinned, law, w, Options(diagnose_iis=False))
    assert sol.status in (Status.OPTIMAL, Status.FEASIBLE), rep.line()
    steps = [abs(sol.z[e.a] - sol.z[e.b]) / max(math.dist(pm.vertices[e.a].xy, pm.vertices[e.b].xy), 1e-9)
             for e in pm.edges.values()
             if any(f is not None and pm.faces[f].role in ("apron", "stub") for f in (e.left_face, e.right_face))]
    assert max(steps) < 0.10, max(steps)                    # a grade, never a step (welded)


def test_an_apron_against_a_taxiway_is_welded_with_no_joint(law):
    cells = [RUNWAY, _stub(1, "taxi", -100.0, 22.5, Y0),
             Cell(2, "apron", "apronA", _rect(-200, Y0, 0, Y1), (), None, None, "airside", "apron", {})]
    airport, pm, st, cl = _airport(law, cells, [_cut("taxi", [(-100.0, 0.0), (-100.0, Y0 + 5.0)])])
    sh = st.shapes
    assert sh.shapes == 1 and not pm.shape_joints and sh.joint_edges == 0 and sh.gap_joints == 0
    assert _face(pm, "taxi").id not in pm.shape_of_face
    assert pm.shape_of_face[_face(pm, "apronA").id] == 0
    # the shared vertices are the network's; the apron interior is labelled
    assert pm.shape_of_vertex.get(_vid(pm, (-111.5, Y0)), S.NO_SHAPE) == S.NO_SHAPE
    assert pm.shape_of_vertex[_vid(pm, (-200.0, Y1))] == 0
    stage = shape_stage(pm, law, airport, cl, out=lambda _m: None)
    cs, counts, _w = shape_constraints(pm, law, airport, stage)
    assert stage.dropped == {}, stage.dropped                # welded: no row dropped
    assert counts["yield.apron"] > 0                        # the body yields
    assert counts.get("yield.taxi_chain_at_runway", 0) > 0  # the chain still yields at the runway (08i-1)


def test_a_hangar_junction_no_route_crosses_is_part_of_the_body(law):
    """The 05w 'junction' hangar apron: a junction-role face beside the
    apron with no centreline through it is an apron body, one shape with
    the apron it touches; the runway-connected taxiway beside them is not."""
    cells = [RUNWAY, _stub(1, "taxi", -150.0, 22.5, Y0),
             Cell(2, "apron", "apronA", _rect(-161.5, Y0, 0, Y1), (), None, None, "airside", "apron", {}),
             Cell(3, "junction", "hangar", _rect(0, Y0, 120, Y1), (), None, "E", "airside", "taxi", {})]
    airport, pm, st, cl = _airport(law, cells, [_cut("taxi", [(-150.0, 0.0), (-150.0, Y0 + 5.0)])])
    sh = st.shapes
    assert sh.network_by_role.get("stub") == 2 and "junction" not in sh.network_by_role
    assert pm.shape_of_face[_face(pm, "hangar").id] == pm.shape_of_face[_face(pm, "apronA").id]
    assert sh.shapes == 1 and not pm.shape_joints
    stage = shape_stage(pm, law, airport, cl, out=lambda _m: None)
    cs, counts, _w = shape_constraints(pm, law, airport, stage)
    # the hangar's mesh rows yield (a body), the taxiway's stay hard
    assert counts.get("yield.junction_mesh", 0) > 0


def test_a_centreline_no_runway_reaches_is_part_of_the_body(law):
    """An apron taxilane (a centreline breakline not connected to the
    runway) does not make its face network: the stub is a body, one shape
    with the apron; a connected one is network."""
    cells = [RUNWAY,
             Cell(1, "apron", "apronA", _rect(-200, Y0, 200, Y1), (), None, None, "airside", "apron", {}),
             _stub(2, "lane", 0.0, Y1, Y1 + 80.0)]
    airport, pm, st, cl = _airport(law, cells, [_cut("lane", [(0.0, Y1 - 5.0), (0.0, Y1 + 85.0)])])
    sh = st.shapes
    assert sh.network_by_role == {"runway": sh.network_by_role.get("runway", 0)}
    assert sh.unconnected_station_edges >= 1 and sh.connected_stations == 0
    assert pm.shape_of_face[_face(pm, "lane").id] == pm.shape_of_face[_face(pm, "apronA").id]
    assert sh.shapes == 1 and not pm.shape_joints
    # the same lane joined to the runway by a connector through the apron
    # is NETWORK — the apron faces the route runs through are not (08p (2):
    # the network is the taxi family; the route's chain is hard through them)
    cells2 = cells + [_stub(3, "conn", 0.0, 22.5, Y0)]
    _ap2, pm2, st2, _cl2 = _airport(law, cells2, [_cut("conn", [(0.0, 0.0), (0.0, Y1 + 85.0)])])
    assert st2.shapes.network_by_role.get("stub") == 4 and "apron" not in st2.shapes.network_by_role
    assert st2.shapes.unconnected_station_edges == 0
    assert st2.shapes.shapes == 1                            # the apron the route runs through stays a body
    for ref in ("lane", "conn"):
        assert all(f.id not in pm2.shape_of_face for f in pm2.faces.values() if f.ref == ref)


def test_two_bodies_across_a_gap_beyond_the_separation_take_a_joint_never_the_network(law):
    """Two apron bodies 1.2 m apart (a gap over the separation; the 04u weld
    shares vertices under ≈ 1 m — the deviation of twin 2 stands) under a
    2 m reader horizon: ONE gap joint between the two shapes; the taxiway
    each touches takes none."""
    emit = _dc.replace(law.tables.emit,
                       instrument=_dc.replace(law.tables.emit.instrument, step_contact_tol_m=2.0))
    wide = Law(tables=_dc.replace(law.tables, emit=emit), ruleset_key=law.ruleset_key)
    cells = _apron_pair(1.2) + [_stub(3, "taxiW", -150.0, 22.5, Y0), _stub(4, "taxiE", 150.0, 22.5, Y0)]
    cuts = [_cut("taxiW", [(-150.0, 0.0), (-150.0, Y0 + 5.0)]), _cut("taxiE", [(150.0, 0.0), (150.0, Y0 + 5.0)])]
    _ap, pm, st, _cl = _airport(wide, cells, cuts)
    assert st.shapes.shapes == 2 and st.shapes.gap_joints == 1 and st.shapes.contours == 0
    (j,) = pm.shape_joints
    assert j.gap and set(j.roles) == {"apron"} and "stub" not in j.roles
    assert max(abs(x) for x, _y in j.points) < 0.7
