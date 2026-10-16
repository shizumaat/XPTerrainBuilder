"""THE TAXI TREND HELD TO THE TAXI LAW (owner decision 2026-10-15g, "fix
slope cap"; ``constraints/taxi_trend_cap``; issue #742).

Found at KCLT: a loop taxiway crosses a real drainage valley, its ground
trend runs at 2.5-3.6 % under a 1.5 % cap, and the WEAK trend row pulling
against the law rows left ``airside_no_step`` / ``taxi_box`` rows that a
zero trend weight does not.  The twins, synthetic:

* a valley under a parallel: the raw trend is steeper than the cap, the
  published targets are not, and the solved parallel holds its no-step
  rows;
* the targets agree ACROSS the network: no target asks more than the route
  budget from any other or from a runway contact;
* where the ground already holds the cap the targets are the trend,
  exactly (the clamp is the identity).
"""
from __future__ import annotations

import pytest

from auto_patch_v2.constraints import taxi_trend as tt
from auto_patch_v2.constraints.routes import reach, routes
from auto_patch_v2.constraints.trend import shift_through, trend_of
from auto_patch_v2.law import Law
from tests.auto_patch_v2 import test_v2taxidatum as T

VALLEY_X = 250.0         # the valley's floor, along the parallel
VALLEY_HALF = 150.0      # its half-width: 9 m over 150 m is a 6 % bank
VALLEY_DEPTH = 9.0
#: the projection's own settling bar (``taxi_trend_cap._SETTLED_M``) and
#: a margin, far under the 0.01 m materiality floor
SETTLED_M = 0.002


class _ValleyDem:
    """A drainage valley under the parallel only (the runway's ground is
    flat): the KCLT loop's shape at fixture scale."""

    provenance = {"synthetic": "a 9 m valley under the parallel"}

    def z(self, x: float, y: float) -> float:
        across = min(1.0, max(0.0, (y - 120.0) / 60.0))
        along = max(0.0, 1.0 - abs(x - VALLEY_X) / VALLEY_HALF)
        return 700.0 - VALLEY_DEPTH * along * across

    def bounds(self):
        return (-9000.0, -9000.0, 9000.0, 9000.0)


class _GentleDem(_ValleyDem):
    """The same field at a third of the depth: a 1 % bank the cap allows."""

    def z(self, x: float, y: float) -> float:
        return 700.0 + (super().z(x, y) - 700.0) / 9.0


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


@pytest.fixture(scope="module")
def valley(law):
    return T._runway_touching(law, _ValleyDem())


def _parallel(pm, law):
    return next(c for c in tt.taxi_chains(pm, law)
                if pm.breaklines[c.bl].ref == "pavT")


def _raw(pm, law, c):
    tr = trend_of([(s, float(pm.vertices[v].dem_z))
                   for v, s in zip(c.vertices, c.stations)],
                  float(law.tables.emit.design.runway_profile_window_m))
    return shift_through(tr, [])


def test_the_valley_trend_is_steeper_than_the_cap(valley, law):
    """The fixture's own claim: the RAW trend along the parallel asks more
    than the taxi cap — what the hold exists for."""
    pm, _z, _rep, _ap = valley
    c = _parallel(pm, law)
    at = _raw(pm, law, c)
    g = max(abs(at(b) - at(a)) / (b - a)
            for a, b in zip(c.stations, c.stations[1:]) if b - a > 1.0)
    assert g > 0.02, f"the raw trend runs at {100 * g:.2f} % only"


def test_the_targets_hold_the_cap_along_the_chain(valley, law):
    pm, _z, _rep, _ap = valley
    c = _parallel(pm, law)
    tz = pm.taxi_trend_z
    pts = [(s, tz[v]) for v, s in zip(c.vertices, c.stations) if v in tz]
    assert len(pts) > 4
    worst = max(abs(zb - za) - 0.015 * (sb - sa)
                for (sa, za), (sb, zb) in zip(pts, pts[1:]) if sb - sa > 1.0)
    assert worst <= SETTLED_M, f"a target asks {worst:.4f} m over the cap"


def test_no_target_asks_more_than_the_route_budget(valley, law):
    """ACROSS THE NETWORK: every target lies inside the route reach of
    every other target and of every runway contact — the no-step law's own
    metric at its own path caps."""
    pm, _z, _rep, airport = valley
    g = routes(pm, law, airport)
    tz = {v: t for v, t in pm.taxi_trend_z.items() if v in g.nodes}
    band = reach(g, tz)
    worst = max(max(b[0] - tz[v], tz[v] - b[1]) for v, b in band.items()
                if v in tz)
    assert worst <= SETTLED_M, f"a target stands {worst:.4f} m outside its reach"
    rwy = set(law.tables.precedence.runway_family.members)
    contacts = {v for c in tt.taxi_chains(pm, law) for v in c.pins}
    assert contacts, "the stub must touch the runway"
    pins = {v: pm.preferred_z.get(v, pm.vertices[v].dem_z) for v in contacts}
    cb = reach(g, pins)
    out = max(max(cb[v][0] - t, t - cb[v][1]) for v, t in tz.items()
              if v in cb)
    assert out <= SETTLED_M, f"a target stands {out:.4f} m outside a contact's reach"
    assert not (contacts & set(pm.taxi_trend_z)) and rwy


def test_the_solved_parallel_holds_its_no_step_rows(valley, law):
    """The rows the KCLT loop minted: on the solved surface the parallel's
    own centreline runs inside the cap (the materiality floor 0.01 m over a
    chord), where the raw trend asked 2 % and more."""
    pm, z, _rep, _ap = valley
    c = _parallel(pm, law)
    over = []
    for i in range(len(c.vertices)):
        for j in range(i + 1, len(c.vertices)):
            ds = c.stations[j] - c.stations[i]
            if ds > 150.0:
                break
            dz = abs(float(z[c.vertices[j]]) - float(z[c.vertices[i]]))
            if dz - 0.015 * ds > 0.01:
                over.append((round(dz - 0.015 * ds, 3), i, j))
    assert not over, f"the parallel exceeds its cap: {sorted(over)[-3:]}"


def _lone_parallel(law, dem):
    """The runway and the parallel alone (no stub): one chain, no contact."""
    from auto_patch_v2.classify.roles import Cell, CutLine
    from tests.auto_patch_v2.test_crown import HALF_WIDTH, _rect
    airport, r = T._airport(law, dem)
    cells = (
        Cell(0, "runway", "09/27", _rect(r, -T.RUN_LEN / 2, -HALF_WIDTH,
                                         T.RUN_LEN / 2, HALF_WIDTH), (), 3,
             "D", "airside", "runway", {}),
        Cell(1, "primary_parallel", "pavT",
             _rect(r, -T.TAXI_LEN / 2, 200.0, T.TAXI_LEN / 2, 223.0), (),
             None, "D", "airside", "taxi", {}),
    )
    cuts = (CutLine("taxi_centerline", "pavT",
                    (r((-T.TAXI_LEN / 2, 211.5)), r((T.TAXI_LEN / 2, 211.5)))),)
    pm, _z, _rep = T._solve(law, airport, cells, cuts)
    return pm, airport


def test_a_lawful_ground_keeps_its_trend_exactly(law):
    """The identity: where the trend already holds the cap, the published
    targets ARE the trend — no clamp and no network hold moves one."""
    pm, airport = _lone_parallel(law, _GentleDem())
    rep: dict = {}
    tt.taxi_trend_targets(pm, law, airport, rep)
    assert rep["capped_chains"] == 0
    assert rep["agreed"] == 0 and rep["held"] == 0, rep


def test_two_chains_meeting_out_of_reach_are_made_to_agree(law):
    """At a junction the stub's trend (shifted through its runway contact)
    and the parallel's (unpinned) disagree by more than the route budget
    between their vertices; the hold moves those targets, and only by the
    minimum (half the excess), never the ones already in reach."""
    pm, _z, _rep, airport = T._runway_touching(law, _GentleDem())
    rep: dict = {}
    tt.taxi_trend_targets(pm, law, airport, rep)
    assert rep["capped_chains"] == 0
    assert 0 < rep["agreed"] < 0.2 * rep["vertices"], rep
    assert rep["held_worst_m"] < 0.25, rep


# ── THE SECOND PASS: stage 1's apron levels as contacts (RULINGS 15i (3)) ──

@pytest.fixture(scope="module")
def apron_problem(law):
    """An apron, the 1 km parallel and the 101 m link stub between them
    (``test_v2valley.stub_problem``'s geometry), before any solve."""
    from auto_patch_v2.classify.roles import Cell, Classification, CutLine
    from auto_patch_v2.constraints import generate
    from auto_patch_v2.constraints.runway_chord import with_runway_chord
    from auto_patch_v2.planar.build import build
    from tests.auto_patch_v2.test_crown import HALF_WIDTH, _rect
    airport, r = T._airport(law, T._RampDem())
    cells = (
        Cell(0, "runway", "09/27", _rect(r, -T.RUN_LEN / 2, -HALF_WIDTH,
                                         T.RUN_LEN / 2, HALF_WIDTH), (), 3,
             "D", "airside", "runway", {}),
        Cell(1, "apron", "apronW", _rect(r, -520.0, 60.0, -320.0, 110.0), (),
             None, "D", "airside", "apron", {}),
        Cell(2, "primary_parallel", "pavT",
             _rect(r, -T.TAXI_LEN / 2, 200.0, T.TAXI_LEN / 2, 223.0), (),
             None, "D", "airside", "taxi", {}),
        Cell(3, "stub", "linkW", _rect(r, -431.5, 110.0, -408.5, 200.0), (),
             None, "D", "airside", "taxi", {}),
    )
    cuts = (CutLine("taxi_centerline", "pavT",
                    (r((-T.TAXI_LEN / 2, 211.5)), r((T.TAXI_LEN / 2, 211.5)))),
            CutLine("taxi_centerline", "linkW",
                    (r((-420.0, 110.0)), r((-420.0, 211.5)))))
    pm, _st = build(airport, Classification(cells, cuts, {}, ()), law)
    pm = tt.with_taxi_trend(with_runway_chord(pm, law, airport), law, airport)
    cs, _c, _w = generate(pm, law, airport)
    return pm, cs, airport


def _apron_vertices(pm, law):
    from auto_patch_v2.law.tables import apron_roles
    roles = apron_roles(law)
    return [v for v, vx in pm.vertices.items()
            if any(pm.faces[f].role in roles for f in vx.incident_faces)]


HELD_LOW_M = 2.0     # the apron stage 1 solved this far under its ground


def test_a_held_low_apron_pulls_the_trend_within_the_cap(apron_problem, law):
    """Option (b): the apron's stage-1 levels are contacts, so every target
    the no-step law pairs with an apron vertex stands inside that pair's
    route budget of the apron's level — the taxiway starts its descent
    early enough to meet it."""
    from auto_patch_v2.constraints.routes import route_neighbours, routes
    pm, _cs, airport = apron_problem
    levels = {v: float(pm.vertices[v].dem_z) - HELD_LOW_M
              for v in _apron_vertices(pm, law)}
    rep: dict = {}
    new = tt.stage_one_retarget(pm, law, airport, levels, rep)
    assert new is not None and rep["retarget_moved"] > 0, rep
    assert set(new) == set(pm.taxi_trend_z)
    g = routes(pm, law, airport)
    ns = law.tables.emit.no_step
    worst = 0.0
    for a, b, _d, bud in route_neighbours(g, levels, float(ns.window_m),
                                          4 * int(ns.k), targets=set(new)):
        u, v = (a, b) if a in levels else (b, a)
        if u in levels and v in new:
            worst = max(worst, abs(new[v] - levels[u]) - bud)
    assert worst <= SETTLED_M + 1e-6, f"a target stands {worst:.4f} m off its apron"


def test_an_apron_at_its_first_pass_level_moves_nothing(apron_problem, law):
    """The identity: levels the first-pass targets already reach within
    budget change nothing, and nothing is re-solved."""
    pm, _cs, airport = apron_problem
    # an apron exactly on the ground the trend follows (the ramp's own DEM)
    levels = {v: float(pm.vertices[v].dem_z) for v in _apron_vertices(pm, law)}
    rep: dict = {}
    got = tt.stage_one_retarget(pm, law, airport, levels, rep)
    assert got is None or rep["retarget_worst_m"] <= 0.05, rep


def test_the_second_pass_is_one_extra_stage_one_solve(apron_problem, law):
    """``solve_design(trend_rewrite=...)`` reads stage 1's levels ONCE: the
    rewrite is called once, never in a loop."""
    from auto_patch_v2.solve import solve_design
    pm, cs, airport = apron_problem
    calls = []

    def rewrite(pm_x, lv):
        calls.append(len(lv))
        return tt.stage_one_retarget(pm_x, law, airport, lv)
    sol, _rep = solve_design(pm, cs, law, trend_rewrite=rewrite)
    assert sol.z and len(calls) == 1, calls
