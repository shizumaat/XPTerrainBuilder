"""A TAXI ROUTE THROUGH AN APRON CARRIES THE TAXIWAY LAW (owner, RULINGS
2026-09-06t) AND THE APRON LAW IS TIERED (owner, RULINGS 2026-09-06w; spec
``docs/specs/auto-patch-v2/apron-route-cap-spec.md`` §3 superseded):

* §2 ``stretches.edge_cap``: a stretch edge bounded by apron faces keeps
  the stretch's cap; bounded by a runway slab it is tightened.
* 06w (1)/(2): every apron row is HARD at 1.5 % and carries the 1 %
  PREFERENCE row beside it (``Diff.soft`` group per row, no ceiling);
  the synthetic apron (200 × 60 m) with one letter-E stretch along its
  middle: a 1.5 m rise pinned over 100 m of route is FEASIBLE with the
  preference slack charged and reported; 1.6 m is INFEASIBLE and the IIS
  names rows at the hard cap; with nothing pinned the surface sits at
  ≤ 1 % (the preference holds when nothing senior needs more).
* The objective ORDER: a runway free to sag beside an apron chain that
  must climb — the runway's fit wins and the apron goes above 1 %; the
  same fixture with the apron preference priced above everything (a
  labelled arm) sags the runway instead.
* Oracle / v2 verify LOCKSTEP: the same rows over 1.5 % (violations);
  the rows over 1 % are a report figure on both readers.
"""
from __future__ import annotations

import dataclasses as _dc
import math
import sys
from pathlib import Path

import pytest

from auto_patch_v2.classify.roles import Cell, Classification, CutLine
from auto_patch_v2.constraints import generate, roads
from auto_patch_v2.constraints.apron import (PREFERENCE_GROUP, PREFERENCE_RULING,
                                             STATS as APRON_STATS, apron_preference_report,
                                             preference_face)
from auto_patch_v2.constraints.precedence import view
from auto_patch_v2.constraints.stretches import edge_cap, stretches
from auto_patch_v2.emit.graded import graded_surface
from auto_patch_v2.emit.osm_adapter import write_patch
from auto_patch_v2.law import Law
from auto_patch_v2.law.tables import role_cap, role_preferred_cap, taxi_half_width_m
from auto_patch_v2.model.airport import Airport, Runway, RunwayEnd, SceneryPack
from auto_patch_v2.model.constraints import ConstraintSet, Diff, Pin, Source
from auto_patch_v2.model.frame import Frame
from auto_patch_v2.pipeline.build import DEFAULT_WEIGHTS
from auto_patch_v2.pipeline.publication import publication
from auto_patch_v2.planar.build import build
from auto_patch_v2.solve import Options, Status
from auto_patch_v2.solve.highs import solve as solve_hard
from auto_patch_v2.solve.stage1 import runway_targets
from auto_patch_v2.verify import census
from auto_patch_v2.verify.frame import Patch
from auto_patch_v2.verify.within import apron_over_preference

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
import check_grade as cg  # noqa: E402

RISE_OK_M = 1.5           # 1.5 % × 100 m between the two route vertices
RISE_BAD_M = 1.6
PREFERRED = 0.010         # common.roles.apron preferred
HARD = 0.015              # common.roles.apron max
LANE_CAP = 0.015          # letter E
LANE_Y = 330.0            # the letter-E stretch along the apron's middle
ROUTE_A = (50.0, LANE_Y)
ROUTE_B = (150.0, LANE_Y)
ABEAM_A = (110.0, 340.0)  # two ring vertices 10 m abeam the route, 10 m apart
ABEAM_B = (120.0, 340.0)
NOTCH_A = (110.0, 360.0)  # the notch's outer corner: 30 m off the axis
BAY_A = (60.0, 290.0)     # the south bay's floor: ring edges 40 m off the
BAY_B = (140.0, 290.0)    # axis, PARALLEL to the route


class _Dem:
    provenance = {"synthetic": "plane 2 % in y"}

    def z(self, x: float, y: float) -> float:
        return 700.0 + 0.02 * max(0.0, y)

    def bounds(self):
        return (-5000.0, -5000.0, 5000.0, 5000.0)


class _Flat:
    provenance = {"synthetic": "flat 700"}

    def z(self, x: float, y: float) -> float:
        return 700.0

    def bounds(self):
        return (-5000.0, -5000.0, 5000.0, 5000.0)


def _rect(x0, y0, x1, y1):
    return ((x0, y0), (x1, y0), (x1, y1), (x0, y1))


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


def _airport(law, dem, threshold=700.0):
    frame = Frame("ZZZZ", origin=(60.5, -135.5), identity_dp=11)
    ends = (RunwayEnd("09", (-600.0, 0.0), (60.5, -135.5), 0.0, 0.0, threshold, "fixture"),
            RunwayEnd("27", (600.0, 0.0), (60.5, -135.5), 0.0, 0.0, threshold, "fixture"))
    rw = Runway("09/27", 45.0, 1, ends, 3, "D")
    pack = SceneryPack("fixture", "apt.dat", "0", (), ())
    return Airport("ZZZZ", "Synthetic", frame, 700.0, (rw,), (), (), {}, (),
                   (), (), (), (), (), (), pack, dem, law.ruleset_key)


@pytest.fixture(scope="module")
def site(law):
    airport = _airport(law, _Dem())
    # the apron: 200 × 60 m with a NOTCH in its north edge whose two inner
    # corners sit 10 m abeam the lane, and a BAY in its south edge whose
    # floor is a ring edge 40 m off the lane, parallel to it
    apron = ((0.0, 300.0), (60.0, 300.0), BAY_A, BAY_B, (140.0, 300.0), (200.0, 300.0),
             (200.0, 360.0), (120.0, 360.0), ABEAM_B, ABEAM_A, NOTCH_A, (0.0, 360.0))
    cells = (
        Cell(0, "runway", "09/27", _rect(-600, -22.5, 600, 22.5), (), 3, "D",
             "airside", "runway", {}),
        Cell(1, "stub", "stubA", _rect(-8, 22.5, 8, 80), (), None, "A",
             "airside", "taxi", {}),
        Cell(2, "primary_parallel", "taxiA", _rect(-400, 80, 400, 103), (), None,
             "D", "airside", "taxi", {}),
        Cell(3, "apron", "apron1", apron, (), None, None, "airside", "apron", {}),
    )
    cuts = (CutLine("taxi_centerline", "stubA", ((0.0, 0.0), (0.0, 91.5)), "A"),
            CutLine("taxi_centerline", "taxiA", ((-400.0, 91.5), (400.0, 91.5)), "D"),
            CutLine("taxi_centerline", "laneE",
                    ((0.0, LANE_Y), ROUTE_A, (100.0, LANE_Y), ROUTE_B, (200.0, LANE_Y)), "E"))
    pm, _stats = build(airport, Classification(cells, cuts, {}, ()), law)
    return airport, pm


def _vid(pm, xy):
    v = min(pm.vertices, key=lambda k: math.dist(pm.vertices[k].xy, xy))
    assert math.dist(pm.vertices[v].xy, xy) < 0.01, (xy, pm.vertices[v].xy)
    return v


def _pair_rows(cs: ConstraintSet, a: int, b: int) -> list[Diff]:
    key = (min(a, b), max(a, b))
    return [r for r in cs.rows() if isinstance(r, Diff) and (min(r.a, r.b), max(r.a, r.b)) == key]


# ── §2: edge_cap ──────────────────────────────────────────────────────────

def test_a_stretch_edge_bounded_by_apron_faces_keeps_the_stretch_cap(site, law):
    airport, pm = site
    vw = view(pm, law)
    st = stretches(pm, law)
    lane = next(s for s in st.items if s.ref == "laneE")
    assert lane.code_letter == "E" and lane.cap_l == pytest.approx(LANE_CAP)
    assert taxi_half_width_m(law, "E") == 11.5      # the width law key (06t), kept
    for eid in lane.edges:
        e = pm.edges[eid]
        roles = {pm.faces[f].role for f in (e.left_face, e.right_face) if f is not None}
        assert roles == {"apron"}, roles          # the lane splits the apron
        assert edge_cap(pm, law, st, eid, vw.caps) == (lane.cap_l, lane.cap_t)


def test_a_stretch_edge_bounded_by_a_runway_slab_is_tightened(site, law):
    airport, pm = site
    vw = view(pm, law)
    st = stretches(pm, law)
    stub = next(s for s in st.items if s.ref == "stubA")
    assert stub.cap_l == pytest.approx(0.03)      # letter A: 3 % / 2 %
    seen_runway = seen_stub = False
    for eid in stub.edges:
        e = pm.edges[eid]
        roles = {pm.faces[f].role for f in (e.left_face, e.right_face) if f is not None}
        cap = edge_cap(pm, law, st, eid, vw.caps)
        if roles == {"runway"}:
            seen_runway = True
            assert cap == (pytest.approx(0.015), pytest.approx(0.015))
        elif roles == {"stub"}:
            seen_stub = True
            assert cap == (stub.cap_l, stub.cap_t)
    assert seen_runway and seen_stub


# ── 06w (1)/(2): the tiered apron rows ────────────────────────────────────

def test_the_law_tables_state_the_two_tiers(law):
    hard, pref = role_cap(law, "apron"), role_preferred_cap(law, "apron")
    assert (hard.longitudinal, hard.transverse) == (HARD, HARD)
    assert (pref.longitudinal, pref.transverse) == (PREFERRED, PREFERRED)
    pad = role_cap(law, "building")
    assert (pad.longitudinal, pad.preferred.longitudinal) == (HARD, PREFERRED)   # pad = apron law
    assert role_preferred_cap(law, "service_road") is None
    assert role_preferred_cap(law, "runway") is None


def test_every_apron_row_is_hard_at_max_with_the_preference_row_beside_it(site, law):
    airport, pm = site
    cs, _c, _w = generate(pm, law, airport, only={"apron_within_shape"})
    rows = [r for r in cs.rows() if isinstance(r, Diff) and r.source.generator == "apron"]
    hard = [r for r in rows if r.soft is None]
    pref = [r for r in rows if r.soft is not None]
    assert hard and len(hard) == len(pref)
    assert {r.cap for r in hard} == {HARD}
    assert {r.cap for r in pref} == {PREFERRED}
    assert all(r.ceiling is None and r.source.ruling == PREFERENCE_RULING for r in pref)
    assert all(r.soft.startswith(PREFERENCE_GROUP + ":") for r in pref)
    assert len({r.soft for r in pref}) == len(pref)          # one group PER ROW
    # the preference row sits on the same pair as its hard twin
    hk = {(min(r.a, r.b), max(r.a, r.b)) for r in hard}
    assert {(min(r.a, r.b), max(r.a, r.b)) for r in pref} == hk
    assert {preference_face(r) for r in pref} <= {f.id for f in pm.faces.values() if f.role == "apron"}
    assert APRON_STATS["apron_within_shape"]["preference_rows"] == len(pref)
    a, c = _vid(pm, ABEAM_A), _vid(pm, NOTCH_A)
    ac = _pair_rows(cs, a, c)                     # a 20 m ring edge: 1.5 % hard, 1 % preferred
    assert sorted(r.cap for r in ac) == [PREFERRED, HARD]


def _solve(site, law, extra=(), diagnose=False, weights=None):
    airport, pm = site
    cs, _c, _w = generate(pm, law, airport)
    if extra:
        cs = ConstraintSet.from_rows([*cs.rows(), *extra])
    size: dict = {}
    sol = solve_hard(pm, cs, weights or DEFAULT_WEIGHTS, Options(diagnose_iis=diagnose),
                     size_out=size)
    return cs, sol, size


def _pins(pm, rise_m):
    src = Source("twin", "the imposed rise between two route vertices (spec §4)", ())
    return (Pin(_vid(pm, ROUTE_A), 700.0, src), Pin(_vid(pm, ROUTE_B), 700.0 + rise_m, src))


def test_the_centreline_rows_through_the_apron_hold_the_taxiway_cap(site, law):
    airport, pm = site
    cs, _c, _w = generate(pm, law, airport, only={"taxi_centerlines"})
    ra, rb = _vid(pm, ROUTE_A), _vid(pm, (100.0, LANE_Y))
    rows = _pair_rows(cs, ra, rb)
    assert len(rows) == 1 and rows[0].cap == pytest.approx(LANE_CAP)
    assert rows[0].bound_m == pytest.approx(0.75)


def test_the_1_5m_rise_is_feasible_and_the_preference_slack_is_charged_and_reported(site, law):
    airport, pm = site
    ra, rb = _vid(pm, ROUTE_A), _vid(pm, ROUTE_B)
    cs, sol, size = _solve(site, law, extra=_pins(pm, RISE_OK_M), diagnose=True)
    assert sol.status in (Status.OPTIMAL, Status.FEASIBLE), (sol.status, sol.message, sol.iis)
    assert sol.z[rb] - sol.z[ra] == pytest.approx(RISE_OK_M, abs=1e-5)
    # the preference YIELDED on apron rows (the escalation the solve charged)
    esc = {g: e for g, e in size["escalation"].items() if g.startswith(PREFERENCE_GROUP + ":")}
    assert esc and max(esc.values()) > 1e-4
    assert all(e <= HARD - PREFERRED + 1e-6 for e in esc.values())   # never past the hard twin
    rep = apron_preference_report(cs, sol.z, law)
    assert rep["preferred"] == PREFERRED and rep["max"] == HARD
    assert rep["rows"] > 0 and rep["over_preference"] > 0
    assert PREFERRED < rep["max_grade"] <= HARD + 1e-6
    fid = next(f.id for f in pm.faces.values() if f.role == "apron")
    assert str(fid) in rep["faces"] or any(v["over_preference"] for v in rep["faces"].values())


def test_a_1_6m_rise_is_infeasible_and_the_iis_names_rows_at_the_hard_cap(site, law):
    airport, pm = site
    ra, rb = _vid(pm, ROUTE_A), _vid(pm, ROUTE_B)
    lane = {v for v in pm.vertices if abs(pm.vertices[v].xy[1] - LANE_Y) < 1e-6}
    cs, sol, _s = _solve(site, law, extra=_pins(pm, RISE_BAD_M), diagnose=True)
    assert sol.status == Status.INFEASIBLE, sol.status
    diffs = [r for r, _s in sol.iis if isinstance(r, Diff)]
    assert diffs
    # every named row is HARD (never a preference row) at the 1.5 % the
    # route and the apron share, along the lane, and their bounds sum to
    # the 1.5 m the law admits
    assert all(r.soft is None for r in diffs), diffs
    assert all(r.cap == pytest.approx(HARD) for r in diffs)
    assert all(r.a in lane and r.b in lane for r in diffs), diffs
    assert sum(r.bound_m for r in diffs) == pytest.approx(RISE_OK_M, abs=1e-6)
    assert {ra, rb} <= {v for r in diffs for v in (r.a, r.b)}


def test_with_nothing_pinned_the_apron_sits_at_the_preference(site, law):
    """The DEM rises 2 % across the apron (1.2 m over its 60 m); the
    preference holds the apron at ≤ 1 % against the DEM fit — nothing
    senior asks for more."""
    airport, pm = site
    cs, sol, size = _solve(site, law)
    assert sol.status in (Status.OPTIMAL, Status.FEASIBLE), sol.message
    rep = apron_preference_report(cs, sol.z, law)
    assert rep["rows"] > 0
    assert rep["over_preference"] == 0, rep
    assert rep["max_grade"] <= PREFERRED + law.tables.emit.materiality.grade + 1e-9
    assert not [g for g, e in size["escalation"].items() if g.startswith(PREFERENCE_GROUP + ":")]


# ── the objective order: the runway's fit outranks the apron preference ──

@pytest.fixture(scope="module")
def drag(law):
    """A runway FREE to sag (no threshold pins), a letter-D stub off its
    north edge, an apron 100 m long hanging off the stub's end; flat DEM
    at 700.  A pin 2.2 m BELOW the DEM at the apron's far corner: the
    chain to the runway climbs 0.86 m on the stub (1.5 % × 57.5 m) and
    1.0 m on the apron at the preference — 0.34 m short.  Either the
    runway sags 0.34 m or the apron goes to ~1.34 %."""
    airport = _airport(law, _Flat(), threshold=None)
    cells = (
        Cell(0, "runway", "09/27", _rect(-600, -22.5, 600, 22.5), (), 3, "D",
             "airside", "runway", {}),
        Cell(1, "stub", "stubD", _rect(-8, 22.5, 8, 80), (), None, "D",
             "airside", "taxi", {}),
        Cell(3, "apron", "apron2", _rect(-25, 80, 25, 180), (), None, None,
             "airside", "apron", {}),
    )
    cuts = (CutLine("taxi_centerline", "stubD", ((0.0, 0.0), (0.0, 80.0)), "D"),)
    pm, _stats = build(airport, Classification(cells, cuts, {}, ()), law)
    return airport, pm


def _drag_solve(drag, law, weights):
    airport, pm = drag
    cs, _c, _w = generate(pm, law, airport)
    far = _vid(pm, (25.0, 180.0))
    pin = Pin(far, 700.0 - 2.2, Source("twin", "the apron's far corner seated 2.2 m below the DEM", ()))
    cs = ConstraintSet.from_rows([*cs.rows(), pin])
    size: dict = {}
    sol = solve_hard(pm, cs, weights, Options(diagnose_iis=True), size_out=size)
    assert sol.status in (Status.OPTIMAL, Status.FEASIBLE), (sol.status, sol.message, sol.iis[:5])
    assert set(runway_targets(pm, law)) >= {v for v in pm.vertices
                                             if any(pm.faces[f].role == "runway"
                                                    for f in pm.vertices[v].incident_faces)}
    # the runway's two readings: its RIDGE (the crown spine, at the DEM) and
    # its north EDGE — which sits the CROWN below the ridge by law (1 % ×
    # 22.5 m = 0.225 m): an edge deeper than that is the runway sagging
    ridge = {v for b in pm.breaklines.values() if b.kind == "runway_profile"
             for v in b.vertices(pm)}
    edge = [v for v in pm.vertices if abs(pm.vertices[v].xy[1] - 22.5) < 1e-6
            and any(pm.faces[f].role == "runway" for f in pm.vertices[v].incident_faces)]
    ridge_sag = max(700.0 - sol.z[v] for v in ridge)
    edge_sag = max(700.0 - sol.z[v] for v in edge)
    return cs, sol, (ridge_sag, edge_sag), apron_preference_report(cs, sol.z, law)


CROWN_M = 0.010 * 22.5   # runway_crown_transverse × the half width


def test_the_runway_fit_outranks_the_apron_preference(drag, law):
    cs, sol, (ridge_sag, edge_sag), rep = _drag_solve(drag, law, DEFAULT_WEIGHTS)
    # the runway stays on its DEM — the ridge at 700, the edge at its
    # crown datum (its fit is senior); the apron pays, to the hard cap
    assert ridge_sag < 0.01, ridge_sag
    assert edge_sag <= CROWN_M + 0.01, edge_sag
    assert rep["over_preference"] > 0 and rep["max_grade"] > PREFERRED + 1e-4, rep
    assert rep["max_grade"] <= HARD + 1e-6


def test_the_labelled_arm_with_the_apron_preference_on_top_sags_the_runway(drag, law):
    """The same fixture with the apron preference charged above every
    other term (an ARM, never the build): the apron holds 1 % and the
    runway's edge sags below its crown datum — the ORDER is the weight's
    doing, not the geometry's."""
    w = _dc.replace(DEFAULT_WEIGHTS, preference={**DEFAULT_WEIGHTS.preference, "apron": 1.0e6})
    cs, sol, (_ridge_sag, edge_sag), rep = _drag_solve(drag, law, w)
    assert edge_sag > CROWN_M + 0.05, edge_sag
    assert rep["over_preference"] == 0, rep


# ── lockstep: the oracle and the v2 verify read the same rows ─────────────

def _readers(site, law, sol, out_dir):
    airport, pm = site
    surf = graded_surface(pm, law, sol, airport.frame.origin, airport.frame.crs)
    pub = publication(pm, law, airport, sol.z)
    assert pub["apron_tier"] == {"preferred": PREFERRED, "max": HARD,
                                 "fan": law.tables.common.apron_fan_ramp_max}
    caps = roads.road_law_caps(pm, law)
    v2 = census(surf, law, pub, caps)
    v2_pref = apron_over_preference(Patch.of(surf, law, pub, caps))
    paths = write_patch(surf, law, out_dir, pub)
    fam: dict = {}
    cg.run_checks_law_true(Path(paths.patch), family_out=fam)
    return v2, v2_pref, fam, dict(fam["_apron_over_preference"])


def _apron_rows(rows):
    return sorted(round(r["distance_m"], 1) for r in rows if r["roles"] == "apron|apron")


def _oracle_apron_rows(fam):
    return sorted(round(v.distance_m, 1) for v in (fam.get("within_shape") or [])
                  if cg.law_role(v.way_a) == "apron")


def test_oracle_and_verify_read_the_hard_cap_in_lockstep_and_the_preference_as_a_figure(
        site, law, tmp_path):
    airport, pm = site
    cs, sol, _s = _solve(site, law, extra=_pins(pm, RISE_OK_M))
    assert sol.status in (Status.OPTIMAL, Status.FEASIBLE), sol.message
    # the solution: rows above 1 % exist (the route's climb), none above
    # 1.5 % — NO violation on either reader; the figure agrees between the
    # generator and the v2 verify (one population)
    v2, v2_pref, fam, or_pref = _readers(site, law, sol, tmp_path / "held")
    assert _apron_rows(v2["within_shape"]) == [] and _oracle_apron_rows(fam) == []
    gen = apron_preference_report(cs, sol.z, law)
    assert gen["over_preference"] > 0
    # one population (the row counts agree); the verify reads the EMITTED
    # (quantised) elevations behind the role's envelope, the generator the
    # exact solve — a row sitting within the emit quantum of 1 % may read
    # either side (measured: 18 vs 19 of 114), never more than that
    assert v2_pref["rows"] == gen["rows"]
    assert abs(v2_pref["over_preference"] - gen["over_preference"]) <= 1, (v2_pref, gen)
    assert or_pref["over_preference"] > 0 and or_pref["max"] == HARD and or_pref["preferred"] == PREFERRED
    assert or_pref["max_grade"] <= HARD + 1e-3
    # a 0.6 m step on ABEAM_A: its 10 m pair along the route (6 %), its
    # 20 m ring edge to the notch corner (3 %) and its 14.1 m chord to the
    # route station (4.2 %) read OVER 1.5 % in BOTH readers (its 22.4 m
    # chord to the notch's far corner crosses the notch: dropped by the
    # 05ae face cover); rows over 1 % only stay a report figure
    z = list(sol.z)
    a = _vid(pm, ABEAM_A)
    z[a] = z[a] + 0.6
    v2s, v2s_pref, fams, or_s = _readers(site, law, _dc.replace(sol, z=tuple(z)), tmp_path / "step")
    v2_d, or_d = _apron_rows(v2s["within_shape"]), _oracle_apron_rows(fams)
    assert or_d == [10.0, 14.1, 20.0, 41.5], or_d
    # PRE-EXISTING population difference, not this law's: v2 prices EVERY
    # spine chord of a ring vertex (08-21c frontage chords), the oracle the
    # NEAREST-spine chord only (families.toml within_shape) — ABEAM_A's
    # 60.7 m chord to ROUTE_A is the one row v2 reads that the oracle does
    # not; on the rows both price the readers agree at the hard cap
    assert v2_d == [*or_d, 60.7], v2_d
    caps = {r["cap_pct"] for r in v2s["within_shape"] if r["roles"] == "apron|apron"}
    assert caps and all(c == pytest.approx(100 * HARD) for c in caps), caps
    or_caps = {v.cap_pct for v in fams["within_shape"] if cg.law_role(v.way_a) == "apron"}
    assert or_caps and all(c == pytest.approx(100 * HARD, abs=1e-6) for c in or_caps), or_caps
    assert v2s_pref["over_preference"] >= v2_pref["over_preference"]
    assert or_s["over_preference"] >= or_pref["over_preference"]
