"""Twins for lane ``rwyband128`` (issue #128, RULINGS 2026-09-30bq STOP (1)):
THE RUNWAY BANDS ARE CENTRED ON PASS 1a AS TODAY'S STAGE 1 SHIPS IT — ITS
ISSUE #87 PIN YIELD INCLUDED.

Measured (HECA, capture ``frames/hardhold128/HECA.pkl``, branch
``claude/apronhard`` 8fe97a07): 05L/23R moved 3.47 m vs sw1002 at
30.13103, 31.39586 while its flex record used 0.45 of 0.81 m.  The vertex
WAS a Band column (a runway face's vertex, shared with cross_connector
``dsf:objpav115``) and pass 1b held it 0.09 m from its centre — but the
centre was pass 1a read BEFORE the stage-1 pin yield (64.55 m); the
hold-less stage 1 releases seven yielding pins (one 5.62 m under its
value) and ships the runway at 61.33 m (sw1002 61.17).

1. ``flex.stage_one`` derives pass 1b off pass 1a's POST-yield answer and
   problem, and returns both passes' releases.
2. A vertex shared between a runway face and an apron face IS a runway
   column and carries the pulled runway's Band (the role-membership
   hypothesis of 30bq, refuted by the read above, kept as a guard).
"""
from __future__ import annotations

import types

import numpy as np

from auto_patch_v2.constraints.no_step import FLEX_RULING, hold_pass
from auto_patch_v2.solve import flex, solve_design

from test_flatpad128v3 import _arm, built, law  # noqa: F401  (fixtures)


def test_pass_1b_is_derived_off_the_yielded_pass_1a(monkeypatch):
    seen: dict = {}
    got_raw = (types.SimpleNamespace(z=[1.0]), "rep_raw", set(), {}, {7: 64.55}, {})
    got_y = (types.SimpleNamespace(z=[1.0]), "rep_y", set(), {}, {7: 61.33}, {})

    class Hold:
        result = None

        def strip(self, cs):
            return "cs1a"

        def derive(self, cs1a, z1a, rw_cols):
            seen["derive"] = (cs1a, dict(z1a))
            return None

    def fake_yield(planar, cs, law_, got, solve1):
        assert (cs, got) == ("cs1a", got_raw)
        return "cs1a_released", got_y, [{"v": 3, "stage": 1}]

    monkeypatch.setattr(flex, "yield_stage_one", fake_yield)
    monkeypatch.setattr(flex, "runway_columns", lambda pm, cs, lw: {7: 0})
    rep_ns = types.SimpleNamespace(unknowns=1, rows=1, hard_rows=1,
                                   hard_max_violation_m=0.0, hard_settled=True)
    got_y = (got_y[0], rep_ns, *got_y[2:])
    pm, cs, got, rec, yl = flex.stage_one("pm", "cs", None, Hold(),
                                          lambda p, c: got_raw)
    assert seen["derive"] == ("cs1a_released", {7: 61.33})
    assert cs == "cs1a_released" and got is got_y
    assert yl == [{"v": 3, "stage": 1}] and rec["pins_yielded"] == 1


def test_a_vertex_shared_with_an_apron_face_carries_the_band(law, built):  # noqa: F811
    pm, cs = built
    lw = _arm(law, staged_solve=True)
    rw = {v for f in pm.faces.values() if f.role == "runway"
          for ring in (f.ring, *f.holes) for v in pm.ring_vertices(ring)}
    ap = {v for f in pm.faces.values() if f.role == "apron"
          for ring in (f.ring, *f.holes) for v in pm.ring_vertices(ring)}
    shared = rw & ap
    assert shared, "the fixture's apron shares runway ring vertices"
    cols = flex.runway_columns(pm, cs, lw)
    free = {v for v in shared if v in cols}
    assert free, "a shared vertex is a free runway column"
    hp = hold_pass(pm, lw)
    sol, rep = solve_design(pm, cs, lw, hold=hp)
    banded = {r.v for r in hp.result.rows
              if type(r).__name__ == "Band" and r.source.ruling.startswith(FLEX_RULING)}
    by_col: dict[int, set[int]] = {}
    for v, c in cols.items():
        by_col.setdefault(c, set()).add(v)
    for v in free:   # one Band per column: some member of v's column carries it
        assert by_col[cols[v]] & banded, v
    # owner RULINGS 2026-10-02ag (1): a pad never pulls a runway — the
    # budget is 0 (``rep.runway_flex`` carries no pulled runway) and every
    # shared column sits at its pass-1a value
    assert not rep.runway_flex
    beta = 0.0
    tol = float(lw.tables.emit.design.hard_tol_m)
    z = np.asarray(sol.z, float)
    ref = {v: z0 for cm in hp.result.columns.values() for v, z0 in cm.items()}
    for v in free:
        u = next(iter(by_col[cols[v]] & set(ref)))
        assert abs(z[v] - ref[u]) <= beta + tol, (v, z[v], ref[u], beta)
