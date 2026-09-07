"""THE LEXICOGRAPHIC BASE SOLVE (RULINGS 2026-09-06x; ``solve/lexi.py``;
the law ``emit.toml [objective]``): the runway family's objective FIRST,
the apron preference (06w (2)) SECOND, the DEM fit and the rest LAST.

The round-3 runway-vs-apron fixture DENSIFIED — the configuration that
defeated the weights at HECA (hundreds of parallel apron preference rows
at 18 per metre against a runway priced at 20 per metre per vertex): a
300 × 50 m apron abutting the runway's north edge, ring vertices every
5 m along both long edges (≈ 4,000 parallel apron rows), its far edge
pinned so the apron must run 1.44 % between the crown datum and the
pins.  Under the WEIGHTED single stage the runway sags ~0.1 m to spare
the apron's parallel rows; under the LEXICOGRAPHIC order the runway
holds its fit (the ridge on the DEM, the edge at its crown datum) and
the apron is spent to 1.5 %.  Also: the hold tolerance (stage B / C move
no runway vertex more than ``runway_hold_tolerance_m``), and the DEM fit
still acting at stage C (a free apron off a second stub lands on its
DEM), the law table and its binding, ``why`` reading stage A.
"""
from __future__ import annotations

import dataclasses as _dc

import numpy as np
import pytest

from auto_patch_v2.classify.roles import Cell, Classification, CutLine
from auto_patch_v2.constraints import generate
from auto_patch_v2.constraints.apron import PREFERENCE_GROUP, apron_preference_report
from auto_patch_v2.constraints.routes import RIDGE_KIND
from auto_patch_v2.law import Law, LawError
from auto_patch_v2.law.objective_schema import OBJECTIVE_ORDERS, Objective, check_objective
from auto_patch_v2.model.airport import Airport, Runway, RunwayEnd, SceneryPack
from auto_patch_v2.model.constraints import ConstraintSet, Pin, Source
from auto_patch_v2.model.frame import Frame
from auto_patch_v2.pipeline.build import DEFAULT_WEIGHTS, weights_under_law
from auto_patch_v2.planar.build import build
from auto_patch_v2.solve import Options, Status
from auto_patch_v2.solve.assemble import assemble
from auto_patch_v2.solve.highs import solve as solve_hard
from auto_patch_v2.solve.lexi import partition, runway_vertices, solve_stages
from auto_patch_v2.solve import why as solve_why

HARD = 0.015
PREFERRED = 0.010
HALF_W = 22.5                  # the runway's half width
CROWN_M = 0.010 * HALF_W       # runway_crown_transverse × the half width
APRON_W = 50.0
APRON_HALF_LEN = 150.0
RING_STEP_M = 5.0
DROP_M = CROWN_M + 0.72        # the far edge: 1.44 % across the apron from the crown datum
FREE_X = 500.0                 # the second stub and its free apron


class _Flat:
    provenance = {"synthetic": "flat 700"}

    def z(self, x: float, y: float) -> float:
        return 700.0

    def bounds(self):
        return (-5000.0, -5000.0, 5000.0, 5000.0)


def _rect(x0, y0, x1, y1):
    return ((x0, y0), (x1, y0), (x1, y1), (x0, y1))


def _dense_rect(x0, y0, x1, y1, step):
    """A rectangle whose two long edges carry a ring vertex every ``step``."""
    n = int(round((x1 - x0) / step))
    pts = [(x0 + (x1 - x0) * i / n, y0) for i in range(n + 1)]
    pts += [(x1 - (x1 - x0) * i / n, y1) for i in range(1, n + 1)]
    return tuple(pts)


def _airport(law, dem):
    frame = Frame("ZZZZ", origin=(60.5, -135.5), identity_dp=11)
    ends = (RunwayEnd("09", (-600.0, 0.0), (60.5, -135.5), 0.0, 0.0, None, "fixture"),
            RunwayEnd("27", (600.0, 0.0), (60.5, -135.5), 0.0, 0.0, None, "fixture"))
    rw = Runway("09/27", 45.0, 1, ends, 3, "D")
    pack = SceneryPack("fixture", "apt.dat", "0", (), ())
    return Airport("ZZZZ", "Synthetic", frame, 700.0, (rw,), (), (), {}, (),
                   (), (), (), (), (), (), pack, dem, law.ruleset_key)


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


@pytest.fixture(scope="module")
def dense(law):
    """The densified fixture (module docstring) plus a FREE apron off a
    second stub far along the runway — nothing pins it, so only the DEM
    fit (stage C) places it."""
    airport = _airport(law, _Flat())
    cells = (
        Cell(0, "runway", "09/27", _rect(-600, -HALF_W, 600, HALF_W), (), 3, "D",
             "airside", "runway", {}),
        Cell(1, "apron", "apronD",
             _dense_rect(-APRON_HALF_LEN, HALF_W, APRON_HALF_LEN, HALF_W + APRON_W, RING_STEP_M),
             (), None, None, "airside", "apron", {}),
        Cell(2, "stub", "stubF", _rect(FREE_X - 8, HALF_W, FREE_X + 8, 80), (), None, "D",
             "airside", "taxi", {}),
        Cell(3, "apron", "apronF", _rect(FREE_X - 30, 80, FREE_X + 30, 140), (), None, None,
             "airside", "apron", {}),
    )
    cuts = (CutLine("taxi_centerline", "stubF", ((FREE_X, 0.0), (FREE_X, 80.0)), "D"),)
    pm, _stats = build(airport, Classification(cells, cuts, {}, ()), law)
    cs, _c, _w = generate(pm, law, airport)
    src = Source("twin", "the apron's far edge seated below the crown datum", ())
    far = [v for v in pm.vertices if abs(pm.vertices[v].xy[1] - (HALF_W + APRON_W)) < 1e-6
           and abs(pm.vertices[v].xy[0]) <= APRON_HALF_LEN + 1e-6]
    assert len(far) >= 2 * APRON_HALF_LEN / RING_STEP_M
    cs = ConstraintSet.from_rows([*cs.rows(), *[Pin(v, 700.0 - DROP_M, src) for v in far]])
    return airport, pm, cs


def _ridge(pm):
    return sorted({v for b in pm.breaklines.values() if b.kind == RIDGE_KIND
                   for v in b.vertices(pm)})


def _free_apron(pm):
    return [v for v in pm.vertices if pm.vertices[v].xy[0] > FREE_X - 40
            and pm.vertices[v].xy[1] >= 80.0
            and any(pm.faces[f].role == "apron" for f in pm.vertices[v].incident_faces)]


def _north_edge(pm):
    return [v for v in pm.vertices if abs(pm.vertices[v].xy[1] - HALF_W) < 1e-6
            and abs(pm.vertices[v].xy[0]) <= APRON_HALF_LEN + 1e-6]


# ── the law table ─────────────────────────────────────────────────────────

def test_the_law_states_the_order_and_binds_it_to_the_weights(law):
    ob = law.tables.emit.objective
    assert ob.order == "lexicographic" and ob.order in OBJECTIVE_ORDERS
    assert ob.stage_b_prefix == PREFERENCE_GROUP
    w = weights_under_law(DEFAULT_WEIGHTS, law)
    lex = w.lexicographic
    assert lex is not None
    assert "runway" in lex.runway_roles and "apron" not in lex.runway_roles
    assert lex.runway_kinds == frozenset((RIDGE_KIND,))
    assert lex.hold_m == law.tables.emit.relaxation.runway_hold_tolerance_m == 0.01
    assert lex.warm_start is ob.warm_start
    # the OFF arm: "weighted" binds nothing
    off = _dc.replace(law.tables.emit.objective, order="weighted")
    law_off = Law(tables=_dc.replace(law.tables, emit=_dc.replace(law.tables.emit, objective=off)),
                  ruleset_key=law.ruleset_key)
    assert weights_under_law(DEFAULT_WEIGHTS, law_off).lexicographic is None
    with pytest.raises(LawError):
        check_objective(Objective("variance", "apron", True), LawError)
    with pytest.raises(LawError):
        check_objective(Objective("lexicographic", "apron:1", True), LawError)


def test_the_partition_puts_the_runway_first_the_apron_second(dense, law):
    _airport_, pm, cs = dense
    w = weights_under_law(DEFAULT_WEIGHTS, law)
    prob = assemble(pm, cs, w)
    c_a, c_b, rv = partition(pm, prob, w)
    assert rv == runway_vertices(pm, w.lexicographic)
    # stage A: the runway vertices' fit columns and the ridge's stations, no apron group
    for v in rv:
        if v in prob.t_col:
            assert c_a[prob.t_col[v]] == prob.c[prob.t_col[v]] > 0
    r0 = prob.n + len(prob.t_col)
    assert any(k == RIDGE_KIND for k in prob.station_kinds)
    for j, kind in enumerate(prob.station_kinds):
        assert (c_a[r0 + j] > 0) == (kind == RIDGE_KIND)
    apron_cols = [c for g, c in prob.soft_cols.items() if g.startswith(PREFERENCE_GROUP + ":")]
    assert len(apron_cols) > 1000
    assert all(c_a[c] == 0 and c_b[c] == prob.c[c] > 0 for c in apron_cols)
    other = [c for g, c in prob.soft_cols.items() if not g.startswith(PREFERENCE_GROUP + ":")]
    assert other and all(c_a[c] == prob.c[c] > 0 and c_b[c] == 0 for c in other)
    # nothing else is charged in A or B: the other roles' fit is stage C's
    free = [prob.t_col[v] for v in _free_apron(pm) if v in prob.t_col]
    assert free and all(c_a[c] == 0 and c_b[c] == 0 and prob.c[c] > 0 for c in free)


# ── the densified fixture ─────────────────────────────────────────────────

def _solve(dense, law, w):
    _airport_, pm, cs = dense
    size: dict = {}
    sol = solve_hard(pm, cs, w, Options(diagnose_iis=True), size_out=size)
    assert sol.status in (Status.OPTIMAL, Status.FEASIBLE), (sol.status, sol.message, sol.iis[:5])
    z = np.asarray(sol.z, float)
    ridge_sag = max(700.0 - z[v] for v in _ridge(pm))
    edge_sag = max(700.0 - z[v] for v in _north_edge(pm))
    return sol, z, ridge_sag, edge_sag, apron_preference_report(cs, z, law), size


def test_weighted_sags_the_runway_to_spare_the_parallel_apron_rows(dense, law):
    """The OFF arm — the configuration that defeated the weights: the
    runway ridge sags ~0.1 m rather than spend hundreds of apron rows."""
    w = _dc.replace(weights_under_law(DEFAULT_WEIGHTS, law), lexicographic=None)
    _sol, _z, ridge_sag, _edge, rep, size = _solve(dense, law, w)
    assert "stages" not in size
    assert rep["rows"] > 1000, rep["rows"]
    assert ridge_sag > 0.05, ridge_sag
    assert rep["max_grade"] < HARD - 1e-4 or rep["over_preference"] < 100, rep


def test_lexicographic_holds_the_runway_and_spends_the_apron_to_the_cap(dense, law):
    """RULINGS 2026-09-06x: the runway family's fit first — ridge on the
    DEM, edge at its crown datum — and the apron spent to 1.5 %."""
    w = weights_under_law(DEFAULT_WEIGHTS, law)
    tol = law.tables.emit.materiality.elevation_m
    sol, _z, ridge_sag, edge_sag, rep, size = _solve(dense, law, w)
    assert abs(ridge_sag) <= tol, ridge_sag
    assert edge_sag <= CROWN_M + tol, edge_sag
    assert rep["over_preference"] > 100 and rep["max_grade"] >= HARD - 1e-4, rep
    assert rep["max_grade"] <= HARD + 1e-6
    stages = size["stages"]
    assert [s["stage"] for s in stages] == ["A", "B", "C"]
    assert all(s["status"] == "optimal" for s in stages)
    assert stages[1]["held_vertices"] == len(runway_vertices(dense[1], w.lexicographic))
    assert stages[1]["held_columns"] == stages[0]["charged"]
    assert stages[2]["held_columns"] == stages[1]["charged"]
    assert "lexicographic A:optimal" in sol.message


def test_the_hold_tolerance_is_respected_and_the_dem_fit_acts_at_stage_c(dense, law):
    """Stage B / C move no runway vertex more than ``runway_hold_
    tolerance_m`` from stage A; the free apron (nothing pins it) lands on
    its DEM at stage C — it is unpriced in A and B."""
    _airport_, pm, cs = dense
    w = weights_under_law(DEFAULT_WEIGHTS, law)
    lex = w.lexicographic
    prob = assemble(pm, cs, w)
    stg = solve_stages(pm, prob, w)
    assert stg.status == "optimal" and stg.x_a is not None and stg.x is not None
    rv = runway_vertices(pm, lex)
    assert set(stg.hold) == set(rv)
    moved = max(abs(stg.x[v] - stg.x_a[v]) for v in rv)
    assert moved <= lex.hold_m + 1e-9, moved
    # stage A's and B's objectives held at the final point: each charged
    # column within hold_m (in its unit) of its solved value
    c_a, c_b, _rv = partition(pm, prob, w)
    assert float(c_a @ stg.x) <= stg.stages[0].objective + lex.hold_m * float(c_a.sum()) + 1e-6
    assert float(c_b @ stg.x) <= stg.stages[1].objective + lex.hold_m * 18.0 * prob.fit_scale * len(
        [g for g in prob.soft_cols if g.startswith(PREFERENCE_GROUP + ":")]) + 1e-6
    free = _free_apron(pm)
    assert len(free) >= 4
    tol = law.tables.emit.materiality.elevation_m
    assert max(abs(stg.x[v] - 700.0) for v in free) <= tol
    # stage C did the placing: its objective (the whole c) is the DEM fit's
    assert stg.stages[2].charged > stg.stages[0].charged + stg.stages[1].charged
    # the cold arm agrees within the materiality (the basis is a speed-up, never a value)
    cold = solve_stages(pm, prob, _dc.replace(w, lexicographic=_dc.replace(lex, warm_start=False)))
    assert cold.status == "optimal"
    assert max(abs(cold.x[v] - stg.x[v]) for v in rv) <= 2 * lex.hold_m + 1e-9


def test_why_reads_stage_a(dense, law):
    """``why`` reads STAGE A's point and duals (the chain that holds the
    runway); the final point rides along for the figures."""
    _airport_, pm, cs = dense
    w = weights_under_law(DEFAULT_WEIGHTS, law)
    prob, res = solve_why.solve_with_duals(pm, cs, w)
    assert res.status == 0
    assert res.ineqlin.marginals is not None and len(res.ineqlin.marginals) == prob.A_ub.shape[0]
    assert res.final_x is not None and res.x is not None
    assert np.allclose(res.x[:prob.n], res.staged.x_a[:prob.n])
    assert np.allclose(res.final_x[:prob.n], res.staged.x[:prob.n])
    # a binding apron hard row at the cap carries a dual in stage A
    assert np.any(res.ineqlin.marginals < -1e-6)
