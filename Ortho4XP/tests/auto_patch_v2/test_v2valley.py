"""SPEC §61 — THE TAXIWAY EDGE TAKES ITS CENTRELINE'S LEVEL, AND THE SOLVE
IS REPRODUCIBLE (owner RULINGS 2026-10-09e).

The finding: a taxi-family vertex off a SHORT centreline chain carried
bending only, a valley of the objective, so a constraint the surface already
SATISFIED moved hundreds of them (KCLT 506-615 vertices up to 0.81 m).  The
twins here are the stability bar at fixture scale — a NULL CHANGE moves
nothing — and the rows that make it so.
"""
from __future__ import annotations

import dataclasses as dc

import numpy as np
import pytest

from auto_patch_v2.classify.roles import Classification
from auto_patch_v2.constraints import generate
from auto_patch_v2.constraints.runway_chord import with_runway_chord
from auto_patch_v2.constraints.taxi_trend import with_taxi_trend
from auto_patch_v2.law import Law
from auto_patch_v2.model.constraints import Band, Source
from auto_patch_v2.planar.build import build
from auto_patch_v2.solve import Status, solve_design
from auto_patch_v2.solve.design import DesignReport, assemble
from auto_patch_v2.solve.rows import _level_row_columns
from tests.auto_patch_v2 import test_v2taxidatum as T

#: the stability bar (§61 (6) 5): no vertex moves by this under a null change
BAR_M = 0.02


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


@pytest.fixture(scope="module")
def stub_problem(law):
    """The §8.6 stub fixture (an apron, a 1 km parallel and the 101 m link
    stub joining them — ``test_v2taxidatum.apron_and_parallel``) as the
    problem the solve is handed, before any solve."""
    airport, r = T._airport(law, T._RampDem())
    from auto_patch_v2.classify.roles import Cell, CutLine
    from tests.auto_patch_v2.test_crown import HALF_WIDTH, _rect
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
    pm = with_taxi_trend(with_runway_chord(pm, law, airport), law, airport)
    cs, _c, _w = generate(pm, law, airport)
    return pm, cs


def _z(pm, cs, law):
    sol, rep = solve_design(pm, cs, law)
    assert sol.status in (Status.OPTIMAL, Status.FEASIBLE), sol.message
    return np.asarray(sol.z, float), rep


def _satisfied_ceilings(pm, z, n=12, margin=0.05):
    """``n`` ``Band`` ceilings ``margin`` ABOVE the surface's own level on
    apron / taxi-family vertices, by a fixed seed: constraints the surface
    already satisfies — a null change."""
    roles = {"apron", "junction", "primary_parallel", "stub", "cross_connector"}
    vs = sorted({v for f in pm.faces.values() if f.role in roles
                 for v in pm.ring_vertices(f.ring)})
    pick = np.random.default_rng(3).choice(len(vs), size=min(n, len(vs)),
                                           replace=False)
    src = Source("null_probe", "spec §61 null-change ceiling", ())
    return tuple(Band(vs[i], None, float(z[vs[i]]) + margin, src) for i in pick)


def test_the_stub_edge_is_named_by_its_centreline(stub_problem, law):
    """The rows exist where §61 puts them: the stub's side vertices carry a
    ``taxi_xsec`` row and no column of the taxi sheet is left with bending
    alone."""
    pm, cs = stub_problem
    rep = DesignReport()
    bp = assemble(pm, cs, law, rep)
    owners = [o for o in bp.rows.owner if o and o[0] == "taxi_xsec"]
    assert rep.taxi_xsec_rows == len(owners) > 0
    named = {int(bp.red.col[o[1]]) for o in owners}
    assert not ({o[1] for o in owners} & set(pm.taxi_trend_z)), \
        "a vertex with a trend row takes no cross-section row"
    lev = _level_row_columns(bp.rows, bp.body, bp.red.n_cols)
    taxi = set(law.tables.precedence.taxi_family.members)
    membrane = {int(bp.red.col[o[1]]) for o in bp.rows.owner
                if o and o[0] == "free_membrane"}
    for v, vx in pm.vertices.items():
        col = int(bp.red.col[v])
        if col < 0 or not any(pm.faces[f].role in taxi
                              for f in vx.incident_faces):
            continue
        assert lev[col] or col in named or col in membrane, \
            f"taxi-family vertex {pm.vertices[v].key} is held by bending alone"


def test_a_satisfied_ceiling_moves_nothing(stub_problem, law):
    """THE STABILITY BAR (§61 (6) 5): the same problem plus ceilings 0.05 m
    above its own answer is the same surface."""
    pm, cs = stub_problem
    z0, rep0 = _z(pm, cs, law)
    assert rep0.taxi_xsec_rows > 0
    bands = _satisfied_ceilings(pm, z0)
    z1, _rep1 = _z(pm, dc.replace(cs, bands=tuple(cs.bands) + bands), law)
    d = np.abs(z1 - z0)
    assert int((d > BAR_M).sum()) == 0, \
        f"{int((d > BAR_M).sum())} vertices moved under a null change, worst {d.max():.4f} m"
    assert d.max() < 0.005


def test_the_qp_exit_is_a_law_value(law):
    """§61 (4): the exit is ``[design] qp_rel_tol``, in the table."""
    d = law.tables.emit.design
    assert d.qp_rel_tol == 1e-12
    assert d.taxi_xsec == d.free_membrane == d.bend_taxi == 1.0


# ── §61 (5) THE §5a LP's TIE-BREAK AMONG EQUAL OPTIMA ────────────────────

def _cycle_lp():
    """THE DEGENERATE OPTIMUM at fixture scale: ``x0 − x1 ≤ −1`` against
    ``x1 − x0 ≤ 0`` (and a second such pair) — one metre of relaxation is
    owed per pair, and either row of a pair pays it at the same price."""
    import scipy.sparse as sp
    A = sp.csr_matrix(np.array([[1.0, -1.0, 0.0, 0.0],
                                [-1.0, 1.0, 0.0, 0.0],
                                [0.0, 0.0, 1.0, -1.0],
                                [0.0, 0.0, -1.0, 1.0],
                                [0.0, 1.0, -1.0, 0.0]]))
    b = np.array([-1.0, 0.0, 0.0, -2.0, 5.0])
    return A, b


@pytest.mark.parametrize("perm", [(0, 1, 2, 3, 4), (1, 0, 3, 2, 4),
                                  (4, 3, 2, 1, 0), (2, 4, 0, 3, 1)])
def test_the_lp_relaxes_the_canonically_first_of_equal_rows(perm):
    """The rows handed in ANY order relax the SAME rows — the ones earliest
    in canonical order — at the SAME total: the optimum is untouched, only
    the choice among equal answers is made by rank instead of row order."""
    from auto_patch_v2.solve.project import _relax_lp
    A, b = _cycle_lp()
    rank = np.array([2.0, 1.0, 3.0, 4.0, 5.0])     # by identity, not position
    p = np.asarray(perm)
    info: dict = {}
    s, st = _relax_lp(A[p], b[p], np.ones(5, bool), cost=np.ones(5),
                      dual_form=True, tie_rank=rank[p], tie_tol=0.02, info=info)
    assert st == "optimal" and info["tie"] == "canonical"
    by_row = np.empty(5)
    by_row[p] = s
    assert by_row.sum() == pytest.approx(3.0)       # the optimum's value
    # pair (0, 1): row 1 is canonically first; pair (2, 3): row 2
    assert by_row == pytest.approx([0.0, 1.0, 2.0, 0.0, 0.0], abs=1e-7)
    # and WITHOUT the tie-break the total is the same (nothing was bought)
    s0, _st = _relax_lp(A[p], b[p], np.ones(5, bool), cost=np.ones(5),
                        dual_form=True)
    assert s0.sum() == pytest.approx(3.0)


def test_the_tie_break_never_trades_a_dear_row_for_a_cheap_rank():
    """Tiers and weights are untouched: a row ten times dearer is not
    relaxed because its rank is lower."""
    from auto_patch_v2.solve.project import _relax_lp
    A, b = _cycle_lp()
    cost = np.array([10.0, 1.0, 1.0, 10.0, 1.0])
    rank = np.array([1.0, 2.0, 4.0, 3.0, 5.0])     # the dear rows rank first
    info: dict = {}
    s, _st = _relax_lp(A, b, np.ones(5, bool), cost=cost, dual_form=True,
                       tie_rank=rank, tie_tol=0.02, info=info)
    assert s == pytest.approx([0.0, 1.0, 2.0, 0.0, 0.0], abs=1e-7)
    assert info["tie"] == "canonical"


def test_the_canonical_rank_is_a_function_of_the_row_not_its_position(
        stub_problem, law):
    """``feasibility.canonical_rank``: the hard rows of the stub fixture in
    two orders get the same rank row by row."""
    from auto_patch_v2.solve.design_roles import ruling_head
    from auto_patch_v2.solve.feasibility import canonical_rank
    pm, cs = stub_problem
    bp = assemble(pm, cs, law, DesignReport())
    rows = np.asarray(bp.hard, dtype=np.int64)
    assert rows.size > 50
    heads = [ruling_head(bp.one[int(k)][2]) for k in rows]
    r0 = canonical_rank(pm, bp.one, rows, heads)
    p = np.random.default_rng(7).permutation(rows.size)
    r1 = canonical_rank(pm, bp.one, rows[p], [heads[i] for i in p])
    assert np.array_equal(r0[p], r1)
    assert r0.min() == 1 and len(set(r0.tolist())) > 0.9 * rows.size


# ── §61 (4) A CAPPED LOOP IS A NAMED LINE AND A SIDECAR KEY ─────────────

def test_every_stage_call_publishes_how_its_loops_ended(stub_problem, law):
    """The sidecar's ``design`` block is ``DesignReport.as_dict()``: each
    stage call carries ``qp_exits``, ``lag_settled`` and ``hard_settled``."""
    pm, cs = stub_problem
    _z0, rep = _z(pm, cs, law)
    d = rep.as_dict()
    calls = [d] + [d["stages"][k] for k in ("stage1", "stage2")]
    if "stage1a" in d["stages"]:
        calls.append(d["stages"]["stage1a"])
    for rec in calls:
        assert {"qp_exits", "lag_settled", "hard_settled"} <= set(rec)
        assert isinstance(rec["lag_settled"], bool)
        assert isinstance(rec["hard_settled"], bool)
    s1 = d["stages"]["stage1"]["qp_exits"]
    assert s1 and set(s1) <= {"optimal", "no_descent", "round_cap"}
    assert "round_cap" not in s1, "the stub fixture's QP converges"


def test_a_round_cap_is_named_first_and_fails_nothing():
    rep = DesignReport()
    rep.note_qp("optimal", 10, 12, 1.0, 0.1, 0.01)
    rep.note_qp("round_cap", 400, 500, 1.0, 9.0, 1.0)
    rep.note_qp("no_descent", 3, 20, 1.0, 0.2, 0.01)
    rep.one_way_settled = False
    rec = rep.settle_record()
    assert list(rec["qp_exits"]) == ["round_cap", "no_descent", "optimal"]
    assert rec["qp_exits"] == {"round_cap": 1, "no_descent": 1, "optimal": 1}
    assert rec["lag_settled"] is False and rec["hard_settled"] is rep.hard_settled
    assert "HIT THE ROUND CAP" in rep.qp_line()
