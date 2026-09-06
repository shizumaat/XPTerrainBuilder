"""Twins for RULINGS 2026-09-06h (lane v2bow — "the runway should not
need to sag that much"):

* (a) a 1202 centreline entering a runway slab diagonally and ENDING
  at a node on the runway's own 1202 line 2 m off the ridge joins the
  ridge through the crossing — the entry reaches the ridge ALONG it, not
  by a perpendicular hop (``constraints.routes._runway_crossings``);
* (b) the relaxation program's objective carries the RUNWAY family's
  DEM-fit term: where slack on an apron row costs less than sinking a
  runway vertex, the runway stays (``solve/variance.model`` ``fit``);
* (c) a ridge with two holds runs STRAIGHT between them under the
  smoothness preference (``rulesets.toml [common]
  runway_profile_smoothness``) with the vertical-curve rows satisfied.
"""
from __future__ import annotations

import dataclasses as _dc
import math

import numpy as np
import pytest

from auto_patch_v2.classify.roles import Cell, Classification, CutLine
from auto_patch_v2.constraints import generate
from auto_patch_v2.constraints.routes import (CROSSING, LATERAL, RIDGE_KIND, reach,
                                              route_path, routes)
from auto_patch_v2.constraints.runway_profile import (curve_stations, ridge_chains,
                                                      threshold_pins)
from auto_patch_v2.constraints.precedence import view
from auto_patch_v2.law import Law
from auto_patch_v2.law.tables import role_cap, runway_transverse_max, runway_vertical_curve_bound
from auto_patch_v2.model.airport import Airport, Runway, RunwayEnd, SceneryPack, TaxiEdge, TaxiNode
from auto_patch_v2.model.constraints import Band, ConstraintSet, Source
from auto_patch_v2.model.frame import Frame
from auto_patch_v2.pipeline.build import DEFAULT_WEIGHTS, weights_under_law
from auto_patch_v2.planar.build import build
from auto_patch_v2.solve import Options, Status, relax
from auto_patch_v2.solve.assemble import roughness_stations
from auto_patch_v2.solve.highs import solve as solve_hard

from test_routes import _rect, _verts_of_role


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


def _vid_at(pm, x, y, tol=0.05):
    """The one vertex within ``tol`` of ``(x, y)`` (the planar build snaps
    a cut end to its identity grid, so the entry lies within the weld
    spacing of the 1202 line's clip point, never on it)."""
    hits = [v for v, p in pm.vertices.items() if math.hypot(p.xy[0] - x, p.xy[1] - y) <= tol]
    assert len(hits) == 1, (x, y, hits)
    return hits[0]


# ── (a) the diagonal crossing that ends 2 m off the ridge ────────────────

class _FlatDem:
    provenance = {"synthetic": "flat 700"}

    def z(self, x: float, y: float) -> float:
        return 700.0

    def bounds(self):
        return (-5000.0, -5000.0, 5000.0, 5000.0)


#: The 1202 route: an outside node, the runway edge, and the END node on
#: the runway's own 1202 line 2 m off the ridge (HECA T4 → node 257).
OUT = (-400.0, 190.0)
END = (0.0, 2.0)
HALF = 22.5
ENTRY_X = OUT[0] + (END[0] - OUT[0]) * (OUT[1] - HALF) / (OUT[1] - END[1])


@pytest.fixture(scope="module")
def diagonal_end(law):
    """A runway 09/27 (pins 700/700) with ONE stub whose 1202 centreline
    enters the slab diagonally and ends at node 3 = (0, 2) — a node of
    the runway's 1202 line, 2 m off the ridge, > the weld spacing — so no
    clipped part crosses the ridge (the HECA T4 geometry)."""
    frame = Frame("ZZZZ", origin=(60.5, -135.5), identity_dp=11)
    ends = (RunwayEnd("09", (-600.0, 0.0), (60.5, -135.5), 0.0, 0.0, 700.0, "fixture"),
            RunwayEnd("27", (600.0, 0.0), (60.5, -135.5), 0.0, 0.0, 700.0, "fixture"))
    rw = Runway("09/27", 2 * HALF, 1, ends, 3, "D")
    pack = SceneryPack("fixture", "apt.dat", "0", (), ())
    nodes = {1: TaxiNode(1, OUT, "both"), 3: TaxiNode(3, END, "both"),
             4: TaxiNode(4, (-600.0, 0.0), "both"), 5: TaxiNode(5, (600.0, 0.0), "both")}
    edges = (TaxiEdge(1, 3, "T4", False, False, "D"),
             TaxiEdge(4, 3, "09/27", False, True, None), TaxiEdge(3, 5, "09/27", False, True, None))
    airport = Airport("ZZZZ", "Synthetic", frame, 700.0, (rw,), (), (), nodes, edges,
                      (), (), (), (), (), (), pack, _FlatDem(), law.ruleset_key)
    cells = (
        Cell(0, "runway", "09/27", _rect(-600, -HALF, 600, HALF), (), 3, "D",
             "airside", "runway", {}),
        Cell(1, "stub", "stubT4", _rect(-420, HALF, 10, 190), (), None, "D",
             "airside", "taxi", {}),
    )
    cuts = (CutLine("taxi_centerline", "stubT4", ((ENTRY_X, HALF), OUT)),)
    pm, _stats = build(airport, Classification(cells, cuts, {}, ()), law)
    return airport, pm


def test_diagonal_end_joins_the_ridge_through_the_crossing(diagonal_end, law):
    """06h (a): the entry reaches the ridge ALONG the crossing (its
    diagonal to the end node + the end node's lateral hop at the
    transverse cap), never by a perpendicular hop of its own."""
    airport, pm = diagonal_end
    g = routes(pm, law, airport)
    assert g.stats["crossing_unmatched"] == 0
    assert g.stats["crossing_ridge_entries"] == 1
    entry = _vid_at(pm, ENTRY_X, HALF, law.tables.emit.identity.weld_spacing_m)
    kinds = {(int(a), int(b)): (int(k), float(ln), float(c))
             for a, b, k, ln, c in zip(g.a, g.b, g.kind, g.length, g.cap)}
    mine = {key: val for key, val in kinds.items() if entry in key}
    ridge = {v for bl in pm.breaklines.values() if bl.kind == RIDGE_KIND for v in bl.vertices(pm)}
    # no perpendicular hop of the entry's own onto the ridge (the stub's
    # ring vertices still hop TO the entry: it is their stretch's station)
    assert mine and not any(val[0] == LATERAL and (a in ridge or b in ridge)
                            for (a, b), val in mine.items()), mine
    xing = {key: val for key, val in mine.items() if val[0] == CROSSING}
    assert xing, mine
    cap = role_cap(law, "runway", 3, "D").longitudinal
    tcap = runway_transverse_max(law, "D", 3)
    diag = math.hypot(END[0] - ENTRY_X, END[1] - HALF)
    for (a, b), (_k, ln, c) in xing.items():
        s = b if a == entry else a
        assert s in ridge and abs(pm.vertices[s].xy[1]) < 1e-6
        along = abs(pm.vertices[s].xy[0] - END[0])
        # the crossing's length is the diagonal plus the end node's hop
        assert ln == pytest.approx(diag + END[1] + along, abs=1e-6)
        assert c * ln == pytest.approx(cap * (diag + along) + tcap * END[1], abs=1e-6)
    # and the reach at the entry is the ridge's value carried ALONG the
    # crossing — larger than the perpendicular hop would have read
    pins = threshold_pins(pm, law, airport)
    band = reach(g, pins)
    near = min(ridge, key=lambda v: abs(pm.vertices[v].xy[0] - END[0]))
    best = min(band[s][1] + c * ln for (a, b), (_k, ln, c) in xing.items()
               for s in [b if a == entry else a])
    assert band[entry][1] == pytest.approx(best, abs=1e-6)
    # the perpendicular hop from the entry's own foot would have read the
    # ridge there plus the transverse allowance — the shortcut withdrawn
    foot = min(ridge, key=lambda v: abs(pm.vertices[v].xy[0] - ENTRY_X))
    hop = band[foot][1] + tcap * HALF
    assert band[entry][1] > hop + cap * diag * 0.5, (band[entry][1], hop)
    d, bud, path = route_path(g, entry, near)
    assert path[1] in ridge and d == pytest.approx(min(ln for _k, ln, _c in xing.values()), abs=1e-6)


# ── (b) the relaxation keeps the runway on the DEM ───────────────────────

class _RampDem:
    """1 % along the runway; 10 % across the hangar row."""

    provenance = {"synthetic": "1 % in x, 10 % in y beyond the apron"}

    def z(self, x: float, y: float) -> float:
        return 700.0 + 0.01 * (x + 600.0) + 0.10 * max(0.0, y - 60.0)

    def bounds(self):
        return (-5000.0, -5000.0, 5000.0, 5000.0)


@pytest.fixture(scope="module")
def hangar_slack(law):
    """The hangar row of ``test_relax`` with the runway at 1 % (pins
    700 / 712), short stubs (17.5 m: ±0.26 m each) and a 20 m apron strip
    (0.2 m across) whose rim three flat pads consume (0.2 m along): between
    the stubs the DEM rises 3 m against ~1.1 m of budget, so the hard set
    has TWO ways out — the apron takes slack, or the runway sinks between
    the stubs (a lawful profile: the pins leave 1.5 m of room)."""
    frame = Frame("ZZZZ", origin=(60.5, -135.5), identity_dp=11)
    ends = (RunwayEnd("09", (-600.0, 0.0), (60.5, -135.5), 0.0, 0.0, 700.0, "fixture"),
            RunwayEnd("27", (600.0, 0.0), (60.5, -135.5), 0.0, 0.0, 712.0, "fixture"))
    rw = Runway("09/27", 45.0, 1, ends, 3, "D")
    cells = [
        Cell(0, "runway", "09/27", _rect(-600, -22.5, 600, 22.5), (), 3, "D",
             "airside", "runway", {}),
        Cell(1, "stub", "stubW", _rect(-161.5, 22.5, -138.5, 40), (), None, "D",
             "airside", "taxi", {}),
        Cell(2, "stub", "stubE", _rect(138.5, 22.5, 161.5, 40), (), None, "D",
             "airside", "taxi", {}),
        Cell(3, "apron", "hangar_apron", _rect(-200, 40, 200, 60), (), None, None,
             "airside", "apron", {}),
        Cell(4, "building", "hangar1", _rect(-190, 60, -70, 110), (), None, None,
             "airside", "pad", {}),
        Cell(5, "building", "hangar2", _rect(-60, 60, 60, 110), (), None, None,
             "airside", "pad", {}),
        Cell(6, "building", "hangar3", _rect(70, 60, 190, 110), (), None, None,
             "airside", "pad", {}),
    ]
    cuts = [CutLine("taxi_centerline", "stubW", ((-150.0, 0.0), (-150.0, 50.0))),
            CutLine("taxi_centerline", "stubE", ((150.0, 0.0), (150.0, 50.0)))]
    pack = SceneryPack("fixture", "apt.dat", "0", (), ())
    airport = Airport("ZZZZ", "Synthetic", frame, 700.0, (rw,), (), (), {},
                      (), (), (), (), (), (), (), pack, _RampDem(), law.ruleset_key)
    pm, _stats = build(airport, Classification(tuple(cells), tuple(cuts), {}, ()), law)
    cs, _counts, _w = generate(pm, law, airport)
    return airport, pm, cs


def _runway_off_dem(pm, z) -> float:
    ridge = {v for bl in pm.breaklines.values() if bl.kind == RIDGE_KIND for v in bl.vertices(pm)}
    return max(abs(z[v] - pm.vertices[v].dem_z) for v in ridge
               if -150.0 <= pm.vertices[v].xy[0] <= 150.0)


def test_relaxation_objective_keeps_the_runway_on_the_dem(hangar_slack, law):
    """06h (b): the pure variance program (04t(1) alone) gives the apron
    no slack and lets the runway sink between the stubs; with the RUNWAY
    family's DEM-fit term the apron takes the slack and the runway stays
    within materiality of the DEM."""
    airport, pm, cs = hangar_slack
    w = weights_under_law(DEFAULT_WEIGHTS, law)
    cand = relax.full_scope(pm, law, cs)
    assert any(x.kind == "diff" for x in cand) and any(x.kind == "pad" for x in cand)
    tol = law.tables.emit.materiality.elevation_m
    control = relax.stage1(pm, cs, cand, law, backend="pwl")
    assert control.status == "optimal" and control.linear_cols == 0
    # RULINGS 2026-09-06k (1): the term enters only at a positive
    # [relaxation] runway_fit_weight (OFF by default; test_v2bow2 twins the default)
    rl = _dc.replace(law.tables.emit.relaxation, runway_fit_weight=1.0)
    law_on = Law(tables=_dc.replace(law.tables, emit=_dc.replace(law.tables.emit, relaxation=rl)),
                 ruleset_key=law.ruleset_key)
    ruled = relax.stage1(pm, cs, cand, law_on, backend="pwl", weights=w)
    assert ruled.status == "optimal"
    assert ruled.linear_cols > 0 and ruled.linear_rows == 2 * ruled.linear_cols
    apron = [x for x in cand if x.kind == "diff" and relax.stated_role(x.row, law.tables.precedence.roles) == "apron"
             or (x.kind == "diff" and x.row.source.generator == "apron")]
    slack_c = sum(control.slack.get(x.index, 0.0) for x in cand)
    slack_r = sum(ruled.slack.get(x.index, 0.0) for x in cand)
    assert slack_r > slack_c + tol, (slack_c, slack_r)
    # stage 2 on each relaxed set: the runway between the stubs
    for s1, expect_on_dem in ((control, False), (ruled, True)):
        cs2, _repl = relax.relaxed_hard_set(cs, cand, s1)
        sol = solve_hard(pm, cs2, w, Options(diagnose_iis=False))
        assert sol.status in (Status.OPTIMAL, Status.FEASIBLE), sol.message
        off = _runway_off_dem(pm, sol.z)
        if expect_on_dem:
            assert off <= tol, off
        else:
            assert off > 10 * tol, off
    # the relief stays inside the ruled shape
    rl = law.tables.emit.relaxation
    assert max(ruled.excess.get(x.index, 0.0) / x.row.cap for x in cand if x.kind == "diff") \
        <= rl.max_over_cap_factor - 1.0 + 1e-6


# ── (c) straight between the holds ──────────────────────────────────────

class _HumpDem:
    """A 3 m hump on a flat 700 between x = −250 and 250."""

    provenance = {"synthetic": "flat 700 + 3 m hump"}

    def z(self, x: float, y: float) -> float:
        return 700.0 + 3.0 * max(0.0, math.cos(math.pi * x / 500.0)) if abs(x) < 250.0 else 700.0

    def bounds(self):
        return (-5000.0, -5000.0, 5000.0, 5000.0)


@pytest.fixture(scope="module")
def humped(law):
    frame = Frame("ZZZZ", origin=(60.5, -135.5), identity_dp=11)
    ends = (RunwayEnd("09", (-600.0, 0.0), (60.5, -135.5), 0.0, 0.0, 700.0, "fixture"),
            RunwayEnd("27", (600.0, 0.0), (60.5, -135.5), 0.0, 0.0, 700.0, "fixture"))
    rw = Runway("09/27", 45.0, 1, ends, 3, "D")
    pack = SceneryPack("fixture", "apt.dat", "0", (), ())
    airport = Airport("ZZZZ", "Synthetic", frame, 700.0, (rw,), (), (), {}, (),
                      (), (), (), (), (), (), pack, _HumpDem(), law.ruleset_key)
    cells = (Cell(0, "runway", "09/27", _rect(-600, -22.5, 600, 22.5), (), 3, "D",
                  "airside", "runway", {}),)
    pm, _stats = build(airport, Classification(cells, (), {}, ()), law)
    cs, _counts, _w = generate(pm, law, airport)
    return airport, pm, cs


def _holds(pm, at=(-300.0, 300.0), z=697.0):
    ridge = {v for bl in pm.breaklines.values() if bl.kind == RIDGE_KIND for v in bl.vertices(pm)}
    src = Source("twin", "hold", ())
    rows = []
    for x in at:
        v = min(ridge, key=lambda v: abs(pm.vertices[v].xy[0] - x))
        rows.append(Band(v, None, z, src))
    return rows


def test_smoothness_runs_straight_between_holds(humped, law):
    """06h (c): two ceilings 3 m under the DEM 600 m apart; at the
    default λ the fit humps the profile toward the DEM between them; at
    the table's ``runway_profile_smoothness`` it runs straight (every
    station between the holds within materiality of their chord) and the
    hard vertical-curve rows hold."""
    airport, pm, cs = humped
    cs2 = ConstraintSet.from_rows(list(cs.rows()) + _holds(pm))
    vw = view(pm, law)
    chains = ridge_chains(vw)[airport.runways[0].id]
    st = curve_stations(vw.xy, chains, lambda v: vw.xy[v][0], law.tables.emit.identity.min_distinct_spacing_m)
    between = [v for v in st if -300.0 <= vw.xy[v][0] <= 300.0]
    assert len(between) > 10
    tol = law.tables.emit.materiality.elevation_m
    w_law = weights_under_law(DEFAULT_WEIGHTS, law)
    lam = law.tables.common.runway_profile_smoothness
    assert w_law.smoothness_by_kind[RIDGE_KIND] == lam
    assert lam > max(DEFAULT_WEIGHTS.by_role[r] for r in ("runway", "runway_crossing"))
    assert any(s[5] == lam for s in roughness_stations(pm, w_law))
    flat = _dc.replace(w_law, smoothness_by_kind={})
    control = solve_hard(pm, cs2, flat, Options(diagnose_iis=False))
    ruled = solve_hard(pm, cs2, w_law, Options(diagnose_iis=False))
    for sol in (control, ruled):
        assert sol.status in (Status.OPTIMAL, Status.FEASIBLE), sol.message
    hump_c = max(control.z[v] - 697.0 for v in between)
    hump_r = max(ruled.z[v] - 697.0 for v in between)
    assert hump_c > 0.5, hump_c                      # the fit humps toward the DEM
    assert hump_r <= tol, hump_r                     # straight between the holds
    # the vertical-curve law holds at K's own rate (hard rows)
    xs = [vw.xy[v][0] for v in st]
    zs = [ruled.z[v] for v in st]
    for p, c, n in zip(range(len(st)), range(1, len(st)), range(2, len(st))):
        d1, d2 = xs[c] - xs[p], xs[n] - xs[c]
        b = runway_vertical_curve_bound(law, 0.5 * (d1 + d2), 3, "D")
        assert abs((zs[n] - zs[c]) / d2 - (zs[c] - zs[p]) / d1) <= b + 1e-9
