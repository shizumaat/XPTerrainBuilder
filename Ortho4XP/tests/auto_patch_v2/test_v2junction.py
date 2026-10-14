"""Issue #517's twins: the taxi design profile continues THROUGH a junction
where two centreline breaklines meet and run straight on, and does not
across a T (``solve/design_junction``; ``[design]
taxi_profile_through_max_deg``).

The fixture is ``test_v2ground``'s runway over a V-valley with a parallel
taxiway — its centreline SPLIT at the valley floor into two breaklines,
and a stub's centreline meeting the split vertex square-on.
"""
from __future__ import annotations

import numpy as np
import pytest

from auto_patch_v2.classify.roles import Cell, CutLine
from auto_patch_v2.solve import design_assemble
from auto_patch_v2.solve.design import DesignReport, assemble
from auto_patch_v2.solve.design_junction import (deflection_deg,
                                                 through_junction_pairs)
from tests.auto_patch_v2.test_crown import HALF_WIDTH, _rect
from tests.auto_patch_v2.test_v2smooth import (RUN_LEN, _airport, law,  # noqa: F401
                                               _ValleyDem)

Y = 71.5            # the parallel's centreline offset from the runway axis


def _cells_and_cuts(r):
    cells = (
        Cell(0, "runway", "09/27", _rect(r, -RUN_LEN / 2, -HALF_WIDTH, RUN_LEN / 2,
                                         HALF_WIDTH), (), 3, "D", "airside", "runway", {}),
        Cell(1, "primary_parallel", "taxiA", _rect(r, -400.0, 60.0, 400.0, 83.0), (),
             None, "D", "airside", "taxi", {}),
        Cell(2, "stub", "stubB", _rect(r, -11.5, HALF_WIDTH, 11.5, 60.0), (), None, "D",
             "airside", "taxi", {}),
    )
    west = tuple(r((x, Y)) for x in np.arange(-400.0, 0.1, 20.0))
    east = tuple(r((x, Y)) for x in np.arange(0.0, 400.1, 20.0))
    stub = (r((0.0, Y)), r((0.0, 50.0)), r((0.0, 30.0)))
    cuts = (CutLine("taxi_centerline", "taxiA", west, "D"),
            CutLine("taxi_centerline", "taxiA", east, "D"),
            CutLine("taxi_centerline", "stubB", stub, "D"))
    return cells, cuts


@pytest.fixture(scope="module")
def junction_map(law):                                      # noqa: F811
    airport, r = _airport(law, _ValleyDem(), ())
    cells, cuts = _cells_and_cuts(r)
    pm, cs, sol, rep = _taxi_solve(law, airport, cells, cuts, trend=True)
    return pm, cs, sol, rep, airport, r


def _taxi_solve(law, airport, cells, cut, trend):              # noqa: F811
    """``test_v2ground._taxi_solve`` in PIPELINE ORDER: each half of the
    split centreline takes its own §8.6 trend, which is what turns the
    grade at the valley floor (each half's one-sided fit ends descending)."""
    from auto_patch_v2.classify.roles import Classification
    from auto_patch_v2.constraints import generate
    from auto_patch_v2.constraints.runway_chord import with_runway_chord
    from auto_patch_v2.constraints.taxi_trend import with_taxi_trend
    from auto_patch_v2.planar.build import build
    from auto_patch_v2.solve import solve_design
    pm, _st = build(airport, Classification(tuple(cells), tuple(cut), {}, ()), law)
    pm = with_runway_chord(pm, law, airport)
    if trend:
        pm = with_taxi_trend(pm, law, airport)
    cs, _c, _w = generate(pm, law, airport)
    sol, rep = solve_design(pm, cs, law)
    return pm, cs, sol, rep


def _junction_vertex(pm, r):
    target = r((0.0, Y))
    return min(pm.vertices, key=lambda v: np.hypot(pm.vertices[v].xy[0] - target[0],
                                                   pm.vertices[v].xy[1] - target[1]))


def test_straight_on_pairs_get_a_row_and_the_t_does_not(junction_map, law):  # noqa: F811
    """At the split vertex three centrelines END: west and east run on
    (0 deg), the stub meets them square-on (90 deg).  Exactly the one
    straight pair is a through-junction, and ``assemble`` writes it."""
    pm, cs, _sol, _rep, _ap, r = junction_map
    m = _junction_vertex(pm, r)
    max_deg = law.tables.emit.design.taxi_profile_through_max_deg
    pairs = [p for p in through_junction_pairs(pm, max_deg) if p[1] == m]
    assert len(pairs) == 1
    a, _m, c = pairs[0]
    assert deflection_deg(pm, a, m, c) < 1.0
    ends = [bl for bl in pm.breaklines.values() if bl.kind == "taxi_centerline"
            and m in (bl.vertices(pm)[0], bl.vertices(pm)[-1])]
    assert len(ends) == 3, "the fixture must END three centrelines at the junction"
    rep = DesignReport()
    base = assemble(pm, cs, law, rep)
    rows = [own for own in base.rows.owner if own == ("taxi_profile_junction", m)]
    assert len(rows) == 1
    assert rep.taxi_junction_rows >= 1


def test_a_t_alone_takes_no_row(junction_map):
    """With only the stub and one half of the parallel meeting (a 90 deg
    turn), no threshold under 90 deg makes it a through-junction."""
    pm, _cs, _sol, _rep, _ap, r = junction_map
    m = _junction_vertex(pm, r)
    for a, mm, c in through_junction_pairs(pm, 89.0):
        if mm == m:
            assert deflection_deg(pm, a, m, c) < 1.0


def _second_diff_at(pm, z, a, m, c):
    (ax, ay), (mx, my), (cx, cy) = (pm.vertices[i].xy for i in (a, m, c))
    dp, dn = np.hypot(mx - ax, my - ay), np.hypot(cx - mx, cy - my)
    return abs((z[c] - z[m]) / dn - (z[m] - z[a]) / dp)


def test_the_junction_row_smooths_the_v(junction_map, law, monkeypatch):  # noqa: F811
    """Over the valley floor the taxiway's grade turns at the split vertex.
    Without the through-junction row the turn there is unpriced; with it,
    the grade change at that one vertex falls."""
    from auto_patch_v2.solve import solve_design
    pm, cs, sol, _rep, _ap, r = junction_map
    m = _junction_vertex(pm, r)
    (a, _m, c), = [p for p in through_junction_pairs(
        pm, law.tables.emit.design.taxi_profile_through_max_deg) if p[1] == m]
    on = _second_diff_at(pm, np.asarray(sol.z, float), a, m, c)
    monkeypatch.setattr(design_assemble, "through_junction_rows",
                        lambda *args, **kw: 0)
    off_sol, _ = solve_design(pm, cs, law)
    off = _second_diff_at(pm, np.asarray(off_sol.z, float), a, m, c)
    # measured: 3.25 % off -> 2.64 % on (the valley itself is a real V,
    # so the row softens the kink and does not erase it)
    assert off > 0.02, "the fixture's valley must turn the grade at the junction"
    assert on < 0.9 * off
