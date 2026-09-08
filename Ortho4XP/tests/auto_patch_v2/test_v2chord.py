"""v1's PRIORITY MODEL in v2 (owner RULINGS 2026-09-08d; spec
``docs/specs/auto-patch-v2/heca-v1-parity-spec.md``; lane ``v2chord``):

1. the runway fits the THRESHOLD CHORD (``constraints/runway_chord.py``,
   ``[common] runway_chord_fit``): a two-pin ridge over a valley DEM sits
   on the chord; an edge vertex's target is the chord less its crown drop;
2. the surface families beyond the route graph YIELD (``constraints/
   yielding.py``, ``emit.toml [yield]``): the selected hard rows become
   preferences with escalation ceilings; the chain / runway rows stay
   hard; a 2 % apron rise pinned over a ring edge is FEASIBLE (was
   infeasible at the 1.5 % hard cap) and reported as yielded; 3.5 % is
   refused at the ceiling;
3. a joint carries ≤ ``terrace.max_step_m`` HARD (``planar/territories``
   predicate, ``pipeline/territory.weld_built_steps`` on the BUILT surface);
4. the owner's site: same-region slivers merged (``overlay.merge_slivers``),
   the apron edge ramps to the groundside (``yielding.groundside_ramps``).
"""
from __future__ import annotations

import dataclasses as _dc
import math

import pytest
from shapely.geometry import Polygon

from auto_patch_v2.classify.roles import Cell, Classification, CutLine
from auto_patch_v2.constraints import generate
from auto_patch_v2.constraints.runway_chord import runway_chord_targets, with_runway_chord
from auto_patch_v2.constraints.runway_profile import crown_drops
from auto_patch_v2.constraints.yielding import (GROUP, RAMP_FAMILY, YieldStats,
                                                groundside_ramps, yield_family,
                                                yield_rows, yielded_rows)
from auto_patch_v2.law import Law, LawError
from auto_patch_v2.law.tables import runway_chord_fit_weight, yield_ceiling
from auto_patch_v2.law.yield_schema import Yield, YIELD_FAMILIES, check_yield
from auto_patch_v2.model.airport import Airport, Runway, RunwayEnd, SceneryPack
from auto_patch_v2.model.constraints import ConstraintSet, Diff, Flat, Linear, Pin, Source
from auto_patch_v2.model.frame import Frame
from auto_patch_v2.model.planar import LabelJoint, TerraceJoint
from auto_patch_v2.pipeline import territory as T
from auto_patch_v2.pipeline.build import DEFAULT_WEIGHTS, weights_under_law
from auto_patch_v2.planar import territories as PT
from auto_patch_v2.planar.build import build
from auto_patch_v2.planar.overlay import Region, merge_slivers
from auto_patch_v2.solve import Options, Status
from auto_patch_v2.solve.highs import solve as solve_hard
from auto_patch_v2.solve.tiers import solve_law_ordered


def _rect(x0, y0, x1, y1):
    return ((x0, y0), (x1, y0), (x1, y1), (x0, y1))


class _Valley:
    """A valley 6 m deep under the runway's middle, flat elsewhere."""

    provenance = {"synthetic": "valley"}

    def z(self, x: float, y: float) -> float:
        return 700.0 - 6.0 * max(0.0, 1.0 - abs(x) / 400.0)

    def bounds(self):
        return (-5000.0, -5000.0, 5000.0, 5000.0)


class _Flat:
    provenance = {"synthetic": "flat 700"}

    def z(self, x: float, y: float) -> float:
        return 700.0

    def bounds(self):
        return (-5000.0, -5000.0, 5000.0, 5000.0)


class _LotStep:
    """The apron's ground at 703, the lot's at 700: a 3 m step at x = 0."""

    provenance = {"synthetic": "703 west of x=0, 700 east"}

    def z(self, x: float, y: float) -> float:
        return 700.0 if x > 0.0 else 703.0

    def bounds(self):
        return (-5000.0, -5000.0, 5000.0, 5000.0)


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


def _airport(law, cells, cuts, dem, thresholds=(700.0, 700.0)):
    frame = Frame("ZZZZ", origin=(60.5, -135.5), identity_dp=11)
    ends = (RunwayEnd("09", (-600.0, 0.0), (60.5, -135.5), 0.0, 0.0, thresholds[0], "fixture"),
            RunwayEnd("27", (600.0, 0.0), (60.5, -135.5), 0.0, 0.0, thresholds[1], "fixture"))
    rw = Runway("09/27", 45.0, 1, ends, 3, "D")
    pack = SceneryPack("fixture", "apt.dat", "0", (), ())
    airport = Airport("ZZZZ", "Synthetic", frame, 700.0, (rw,), (), (), {},
                      (), (), (), (), (), (), (), pack, dem, law.ruleset_key)
    pm, stats = build(airport, Classification(tuple(cells), tuple(cuts), {}, ()), law)
    return airport, pm, stats


def _vid(pm, xy):
    v = min(pm.vertices, key=lambda k: math.dist(pm.vertices[k].xy, xy))
    assert math.dist(pm.vertices[v].xy, xy) < 0.01, (xy, pm.vertices[v].xy)
    return v


RUNWAY = Cell(0, "runway", "09/27", _rect(-600, -22.5, 600, 22.5), (), 3, "D", "airside", "runway", {})


# ── the law tables ────────────────────────────────────────────────────

def test_the_law_tables_state_the_priority_model_keys(law):
    assert runway_chord_fit_weight(law) > max(w for r, w in DEFAULT_WEIGHTS.by_role.items()
                                              if r not in ("runway", "runway_crossing"))
    y = law.tables.emit.yielding
    assert set(y.families) <= set(YIELD_FAMILIES)
    for fam in ("junction_mesh", "taxi_box", "no_step_pairs", "apron", "apron_edge_portion", "roads"):
        assert yield_ceiling(law, fam) is not None
    assert yield_ceiling(law, "zones") is None
    assert 0.0 < y.groundside_ramp_max < 1.0 and y.sliver_area_factor > 0.0
    w = weights_under_law(DEFAULT_WEIGHTS, law)
    assert w.by_role["runway"] == runway_chord_fit_weight(law)
    assert "yield" in w.preference and w.preference["yield"] < 1.0   # junior to the chord fit


def test_the_yield_schema_refuses_an_unknown_family_and_a_bad_ceiling():
    good = Yield(0.03, 0.03, 0.08, 8.0, 0.05, {"apron": "apron"})
    check_yield(good, LawError)
    with pytest.raises(LawError):
        check_yield(_dc.replace(good, families={"zones": "taxi"}), LawError)
    with pytest.raises(LawError):
        check_yield(_dc.replace(good, families={"apron": "runway"}), LawError)
    with pytest.raises(LawError):
        check_yield(_dc.replace(good, taxi_yield_max=1.5), LawError)


# ── change 1: the chord ──────────────────────────────────────────────

@pytest.fixture(scope="module")
def valley(law):
    return _airport(law, [RUNWAY], [], _Valley())


def test_a_two_pin_ridge_over_a_valley_sits_on_the_chord(valley, law):
    airport, pm, _st = valley
    targets = runway_chord_targets(pm, law, airport)
    ridge = [v for v in targets if abs(pm.vertices[v].xy[1]) < 0.01]
    assert len(ridge) >= 20
    assert all(abs(targets[v] - 700.0) < 1e-6 for v in ridge)          # the chord, not the DEM
    edge = next(v for v in targets if abs(abs(pm.vertices[v].xy[1]) - 22.5) < 0.01)
    drop = crown_drops(pm, law, airport)[edge]
    assert targets[edge] == pytest.approx(700.0 - drop)               # chord less the crown
    pm_c = with_runway_chord(pm, law, airport)
    cs, _c, _w = generate(pm_c, law, airport)
    w = weights_under_law(DEFAULT_WEIGHTS, law)
    sol = solve_hard(pm_c, cs, w, Options(diagnose_iis=False))
    assert sol.status in (Status.OPTIMAL, Status.FEASIBLE)
    mid = _vid(pm, (0.0, 0.0))
    assert pm.vertices[mid].dem_z == pytest.approx(694.0)
    assert abs(sol.z[mid] - 700.0) < 0.05                               # on the chord: 6 m of fill
    # the DEM-fit control: the same set without the chord sags into the valley
    cs0, _c, _w = generate(pm, law, airport)
    sol0 = solve_hard(pm, cs0, w, Options(diagnose_iis=False))
    assert sol0.z[mid] < 697.0


def test_a_runway_without_two_pins_keeps_the_dem(law):
    airport, pm, _st = _airport(law, [RUNWAY], [], _Valley(), thresholds=(700.0, None))
    rep: dict = {}
    assert runway_chord_targets(pm, law, airport, rep) == {}
    assert rep["runways_without"] == 1 and rep["runways"] == 0


# ── change 2: the yielding families ─────────────────────────────────

LANE_Y = 330.0
BAY_A, BAY_B = (60.0, 290.0), (140.0, 290.0)          # an apron ring edge, 80 m, off the lane


@pytest.fixture(scope="module")
def apron_site(law):
    apron = ((0.0, 300.0), (60.0, 300.0), BAY_A, BAY_B, (140.0, 300.0), (200.0, 300.0),
             (200.0, 360.0), (0.0, 360.0))
    cells = [RUNWAY,
             Cell(1, "stub", "stubA", _rect(-8, 22.5, 8, 80), (), None, "A", "airside", "taxi", {}),
             Cell(2, "primary_parallel", "taxiA", _rect(-400, 80, 400, 103), (), None, "D",
                  "airside", "taxi", {}),
             Cell(3, "apron", "apron1", apron, (), None, None, "airside", "apron", {})]
    cuts = [CutLine("taxi_centerline", "stubA", ((0.0, 0.0), (0.0, 91.5)), "A"),
            CutLine("taxi_centerline", "taxiA", ((-400.0, 91.5), (400.0, 91.5)), "D"),
            CutLine("taxi_centerline", "laneE", ((0.0, LANE_Y), (100.0, LANE_Y), (200.0, LANE_Y)), "E")]
    return _airport(law, cells, cuts, _Flat())


def _yielded_set(pm, law, airport):
    cs, _c, _w = generate(pm, law, airport)
    st = YieldStats()
    return cs, yield_rows(cs, pm, law, st), st


def test_the_transform_makes_the_selected_hard_rows_preferences_with_ceilings(apron_site, law):
    airport, pm, _st = apron_site
    cs, ys, st = _yielded_set(pm, law, airport)
    assert st.by_family["apron"] > 0 and st.by_family["no_step_pairs"] > 0
    hard_before = [r for r in cs.rows() if isinstance(r, Diff) and r.source.generator == "apron"
                   and r.soft is None]
    after = [r for r in ys.rows() if isinstance(r, Diff) and r.source.generator == "apron"
             and r.soft is not None and r.soft.startswith(GROUP + ":")]
    assert len(after) == len(hard_before) > 0
    for r in after:
        assert yield_family(r) == "apron"
        assert r.ceiling == pytest.approx(yield_ceiling(law, "apron")) and r.cap < r.ceiling
    # the apron 1 % preference rows keep their own prefix; the taxi CHAIN,
    # the runway family, the pins and the bands are untouched
    assert sum(1 for r in ys.rows() if getattr(r, "soft", "") and r.soft.startswith("apron:")) == \
        sum(1 for r in cs.rows() if getattr(r, "soft", "") and r.soft.startswith("apron:"))
    for r in ys.rows():
        if r.source.generator in ("runway_profile", "reach", "zones", "strips", "pads"):
            assert getattr(r, "soft", None) is None or not r.soft.startswith(GROUP + ":")
        if r.source.generator == "taxi" and "box" not in r.source.ruling:
            assert r.soft is None
    assert len(ys.rows()) == len(cs.rows())


def _pinned(cs: ConstraintSet, pm, rise: float) -> ConstraintSet:
    a, b = _vid(pm, BAY_A), _vid(pm, BAY_B)
    src = Source("fixture", "pin")
    return cs.merged(ConstraintSet.from_rows([Pin(a, 700.0, src), Pin(b, 700.0 + rise, src)]))


def test_a_two_percent_apron_rise_is_feasible_by_yielding_and_reported(apron_site, law):
    airport, pm, _st = apron_site
    cs, ys, _s = _yielded_set(pm, law, airport)
    w = weights_under_law(DEFAULT_WEIGHTS, law)
    hard = solve_hard(pm, _pinned(cs, pm, 1.6), w, Options(diagnose_iis=False))
    assert hard.status is Status.INFEASIBLE                       # 06w: 2 % over 80 m at 1.5 % hard
    sol, rep = solve_law_ordered(pm, _pinned(ys, pm, 1.6), law, w, Options(diagnose_iis=False))
    assert sol.status in (Status.OPTIMAL, Status.FEASIBLE) and rep.mode == "hard"
    yr = yielded_rows(_pinned(ys, pm, 1.6), sol.z, law, pm)
    assert yr["families"]["apron"]["yielded"] >= 1
    assert yr["families"]["apron"]["max_grade"] >= 0.02 - 1e-6
    assert yr["families"]["apron"]["max_grade"] <= yield_ceiling(law, "apron") + 1e-6
    assert all(rec["kind"] in ("diff", "linear") and rec["family"] and len(rec["ll"]) >= 2
               for rec in yr["published"])
    # the ceiling is law: 3.5 % is refused
    over = solve_hard(pm, _pinned(ys, pm, 2.8), w, Options(diagnose_iis=False))
    assert over.status is Status.INFEASIBLE


# ── change 3: the joint step law ─────────────────────────────────────

def test_the_territory_predicate_holds_a_joint_only_under_max_step():
    import numpy as np
    bands = {10: (690.0, 700.0), 20: (690.0, 701.0), 30: (690.0, 706.0)}
    terr = PT.Territories({}, {}, frozenset({10, 20, 30}), PT.TerritoryStats(), _bands=bands,
                          _cap=0.015, _min_step=0.5, _max_step=2.0,
                          _where={10: (0, 0), 20: (0, 1), 30: (0, 2)},
                          _dcc=[np.zeros((3, 3))])
    assert terr.joint(10, 20)                # 1 m over 0 m of path: a joint (0.5 < 1 <= 2)
    assert not terr.joint(10, 30)            # 6 m: NOT a joint — the cell grades through
    assert not terr.joint(10, 10)


def test_a_06n_joint_built_over_max_step_is_welded_and_undeclared(law):
    pm_cells = [RUNWAY,
                Cell(1, "stub", "stubA", _rect(-111.5, 22.5, -88.5, 120), (), None, "D", "airside", "taxi", {}),
                Cell(2, "apron", "apronA", _rect(-200, 120, 0, 170), (), None, None, "airside", "apron", {}),
                Cell(3, "apron", "apronB", _rect(0, 120, 200, 170), (), None, None, "airside", "apron", {})]
    cuts = [CutLine("taxi_centerline", "stubA", ((-100.0, 0.0), (-100.0, 145.0)), "D")]
    airport, pm, _st = _airport(law, pm_cells, cuts, _Flat())
    assert pm.terrace_joints, "the 06n joint between the aprons"
    j = pm.terrace_joints[0]
    terr = PT.Territories({}, {}, frozenset(), PT.TerritoryStats())
    stage = T.TerritoryStage(pm, terr, [], (), {})
    z = [700.0] * len(pm.vertices)
    for _a, b in j.pairs:
        z[b] = 705.0                                  # apron B's copies 5 m above A's
    new, n_label, n_terrace = T.weld_built_steps(stage, law, airport, None, z)
    assert (n_label, n_terrace) == (0, 1)
    assert j not in new.pm.terrace_joints and new.welded_terraces == (j,)
    assert new.welded_steps[0] == pytest.approx(5.0)
    welds = T.terrace_welds(new)
    assert len(welds) == len(j.pairs) and all(isinstance(r, Flat) and r.source.generator == T.WELD_GEN
                                              for r in welds)
    # under 2 m the joint stays declared (v1 APRON_TERRACE_MAX_STEP_M)
    for _a, b in j.pairs:
        z[b] = 701.0
    same, n_label, n_terrace = T.weld_built_steps(stage, law, airport, None, z)
    assert (n_label, n_terrace) == (0, 0) and same is stage and j in pm.terrace_joints


def test_the_built_step_pass_unjoints_a_contour_over_max_step(law):
    cells = [RUNWAY, Cell(1, "apron", "apronA", _rect(-200, 120, 200, 170), (), None, None,
                          "airside", "apron", {})]
    airport, pm, _st = _airport(law, cells, [], _Flat())
    a, b = _vid(pm, (-200.0, 120.0)), _vid(pm, (200.0, 120.0))
    terr = PT.Territories({a: 10, b: 20}, {}, frozenset({10, 20}), PT.TerritoryStats(),
                          verdict={(10, 20): True})
    contour = LabelJoint(0, ((0.0, 120.0), (0.0, 170.0)), ((60.5, -135.5), (60.5, -135.5)),
                         ((a, b),), 50.0, ("apron",))
    stage = T.TerritoryStage(pm, terr, [(a, b, "apron", "apron")], (contour,), {})
    z = [700.0] * len(pm.vertices)
    z[b] = 703.0
    new, n_label, n_terrace = T.weld_built_steps(stage, law, airport, None, z)
    assert (n_label, n_terrace) == (1, 0)
    assert not terr.joint(10, 20)                    # welded: one terrace from now on
    assert new.joints == () and new.edges == []
    z[b] = 701.0
    same, n_label, n_terrace = T.weld_built_steps(stage, law, airport, None, z)
    assert (n_label, n_terrace) == (0, 0) and same is stage


# ── change 4: the owner's site ───────────────────────────────────────

def test_a_same_region_sliver_is_merged_into_its_neighbour():
    big = Region("apron", "pav1", Polygon(_rect(0, 0, 100, 50)), None, None, "airside", "cell")
    other = Region("apron", "pav2", Polygon(_rect(0, 0, 100, 50)), None, None, "airside", "cell")
    faces = [(Polygon(_rect(0, 0, 100, 50)), big),
             (Polygon(((100, 0), (102, 0), (100, 50))), big),        # a 50 m² sliver of the same cell
             (Polygon(((0, 50), (100, 50), (50, 50.2))), other)]     # a sliver of ANOTHER pavement
    out, n = merge_slivers(faces, 16.0 ** 2)
    assert n == 1 and len(out) == 2
    merged = next(p for p, r in out if r is big)
    assert merged.area == pytest.approx(5050.0)
    assert any(r is other for _p, r in out)
    assert merge_slivers(faces, 1.0)[1] == 0                         # under the area gate: kept


@pytest.fixture(scope="module")
def lot_site(law):
    cells = [RUNWAY,
             Cell(1, "stub", "stubA", _rect(-8, 22.5, 8, 120), (), None, "D", "airside", "taxi", {}),
             Cell(2, "apron", "apron1", _rect(-120, 120, 0, 180), (), None, None, "airside", "apron", {}),
             Cell(3, "groundside_pavement", "lot1", _rect(1.0, 120, 61, 180), (), None, None,
                  "groundside", "groundside", {})]
    cuts = [CutLine("taxi_centerline", "stubA", ((0.0, 0.0), (0.0, 150.0)), "D")]
    return _airport(law, cells, cuts, _LotStep())


def test_the_apron_edge_ramps_to_the_groundside_as_a_preference(lot_site, law):
    airport, pm, _st = lot_site
    rows = groundside_ramps(pm, law, airport)
    assert rows, "the stand-off pairs across the 1 m gap"
    y = law.tables.emit.yielding
    for r in rows:
        assert isinstance(r, Diff) and r.cap == y.groundside_ramp_max and r.ceiling is None
        assert yield_family(r) == RAMP_FAMILY and r.d <= 2.0
        roles = {pm.faces[f].role for f in pm.vertices[r.a].incident_faces} | \
            {pm.faces[f].role for f in pm.vertices[r.b].incident_faces}
        assert "apron" in roles and "groundside_pavement" in roles
    cs, _c, _w = generate(pm, law, airport)
    assert any(r.source.generator == RAMP_FAMILY for r in cs.rows())
    w = weights_under_law(DEFAULT_WEIGHTS, law)
    sol = solve_hard(pm, cs, w, Options(diagnose_iis=False))
    assert sol.status in (Status.OPTIMAL, Status.FEASIBLE)
    # the apron sits on its 703 ground (the route holds it); the lot's near
    # edge came up to meet it — a ramp, no step — and its far edge grades
    # down toward its own 700 at the lot's cap
    a, g_near, g_far = _vid(pm, (0.0, 120.0)), _vid(pm, (1.0, 120.0)), _vid(pm, (61.0, 120.0))
    assert sol.z[a] == pytest.approx(703.0, abs=0.5)      # the apron gives a little to the ramp
    assert abs(sol.z[a] - sol.z[g_near]) <= y.groundside_ramp_max * 1.0 + 0.02
    assert sol.z[g_far] < sol.z[g_near] - 1.0
    yr = yielded_rows(cs, sol.z, law, pm)
    assert yr["families"][RAMP_FAMILY]["yielded"] == 0            # no step charged
