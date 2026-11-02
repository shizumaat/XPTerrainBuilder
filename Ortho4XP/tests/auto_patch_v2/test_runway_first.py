"""THE RUNWAY IS SOLVED FIRST (owner RULINGS 2026-11-02a (4), Q311, issue
#1742; ``solve/runway_first``).

The shared-edge fixture of ``test_runway_transverse`` (a stub's
centreline ending AT the runway edge).  A non-runway vertex of the stub
is pulled by a hard pin:

* a pull the taxiway can carry inside its own HARD laws leaves every
  runway column within ``[design] runway_first_slack_m`` of its stage-0
  value — the neighbour fits to the runway, its priced caps take the rest;
* a pull the airside's hard set cannot meet with the runway held (a hard
  5 % pavement ceiling from the pinned vertex to the edge) bends the
  runway: §5a demotes the hold rows the conflict needs, the runway's own
  laws still hold, and the bend is reported.
"""
from __future__ import annotations

import math

import pytest
from auto_patch_v2.constraints import generate, runway_profile
from auto_patch_v2.constraints.precedence import view
from auto_patch_v2.law import Law
from auto_patch_v2.law import tables as T
from auto_patch_v2.model.constraints import ConstraintSet, Linear, Pin, Source
from auto_patch_v2.solve import Status, solve_design
from auto_patch_v2.solve.runway_first import HOLD_RULING, _runway_vertices
from tests.auto_patch_v2.test_runway_transverse import _shared_edge_vertex, build_shared_edge

PIN_SRC = Source("fixture_pin", "twin: a hard pin on a stub vertex", ("fixture:pin",))
#: a HARD row of the taxi tier (its head is in ``[design] hard_rulings``)
CEILING_SRC = Source("fixture_ceiling", "rulesets.common.pavement_max_grade ceiling "
                     "(twin: the stub vertex to the runway edge)", ("fixture:ceiling",))


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


@pytest.fixture(scope="module")
def shared_edge(law):
    return build_shared_edge(law)


@pytest.fixture(scope="module")
def base(shared_edge, law):
    airport, pm, _ = shared_edge
    cs, _c, _w = generate(pm, law, airport)
    sol, rep = solve_design(pm, cs, law)
    assert sol.status in (Status.OPTIMAL, Status.FEASIBLE), sol.message
    return cs, sol, rep


def _stub_vertex(pm, law, edge_v, near_m):
    """The stub's own (non-runway) vertex nearest ``near_m`` from the
    shared edge vertex."""
    vw = view(pm, law)
    rw = _runway_vertices(pm, law)
    stub = {u for f in vw.faces_of_role(("stub",)) for u in vw.face_vertices(f.id)} - set(rw)
    ex, ey = vw.xy[edge_v]
    return min(stub, key=lambda u: abs(math.hypot(vw.xy[u][0] - ex, vw.xy[u][1] - ey) - near_m))


def _pulled(shared_edge, law, base, near_m, lift_m, ceiling=False):
    airport, pm, _ = shared_edge
    cs, sol0, _r = base
    _rw, v, vw = _shared_edge_vertex(pm, law)
    u = _stub_vertex(pm, law, v, near_m)
    extra = [Pin(u, float(sol0.z[u]) + lift_m, PIN_SRC)]
    if ceiling:
        d = math.hypot(vw.xy[u][0] - vw.xy[v][0], vw.xy[u][1] - vw.xy[v][1])
        cap = law.tables.common.pavement_max_grade
        extra.append(Linear(((u, 1.0), (v, -1.0)), None, cap * d, CEILING_SRC))
    cs2 = ConstraintSet.from_rows(list(cs.rows()) + extra)
    sol, rep = solve_design(pm, cs2, law)
    return pm, sol, rep, u, v


def test_the_runway_family_is_stage_zero_and_reported(shared_edge, law, base):
    _airport, pm, _ = shared_edge
    _cs, _sol, rep = base
    s0 = rep.stages["stage0"]
    rw = _runway_vertices(pm, law)
    assert 0 < s0["vertices"] <= len(rw)
    assert s0["slack_m"] == law.tables.emit.design.runway_first_slack_m
    assert HOLD_RULING in law.tables.emit.design.hard_rulings
    # the LAST conflict tier: the hold yields to every airside hard law
    assert HOLD_RULING in law.tables.emit.design.hard_conflict_ranks[-1]


def test_a_pull_the_taxiway_carries_leaves_the_runway_on_its_profile(shared_edge, law, base):
    pm, sol, rep, _u, _v = _pulled(shared_edge, law, base, 40.0, 1.0)
    assert sol.status in (Status.OPTIMAL, Status.FEASIBLE), sol.message
    d = law.tables.emit.design
    for ref, r in rep.stages["stage0"]["runways"].items():
        assert abs(r["worst_m"]) <= d.runway_first_slack_m + d.hard_tol_m + 1e-9, (ref, r)
        assert r["over_slack"] == 0, (ref, r)


def test_a_pull_the_hard_set_cannot_meet_bends_the_runway(shared_edge, law, base):
    pm, sol, rep, u, v = _pulled(shared_edge, law, base, 12.0, 3.0, ceiling=True)
    assert sol.status in (Status.OPTIMAL, Status.FEASIBLE), sol.message
    d = law.tables.emit.design
    bent = rep.stages["stage0"]["runways"]["09/27"]
    assert bent["over_slack"] > 0 and abs(bent["worst_m"]) > d.runway_first_slack_m, bent
    hf = rep.stages["stage1"]["hard_feasibility"]
    assert hf["runway_conflict"] == 0 and set(hf["by_head"]) == {HOLD_RULING}, hf
    # the runway's own laws still hold where it bent: the edge keeps its
    # crown band to the ridge
    vw = view(pm, law)
    rw = next(f for f in vw.faces_of_role(("runway",)) if v in vw.face_vertices(f.id))
    dist, a, b, t = runway_profile._foot(vw, v, runway_profile.ridge_chains(vw)[rw.ref])
    fall = (1.0 - t) * sol.z[a] + t * sol.z[b] - sol.z[v]
    floor = T.runway_crown_floor(law, dist, 22.5, rw.code_letter, rw.code_number)
    assert fall >= floor - d.hard_tol_m - 1e-9, (fall, floor)
