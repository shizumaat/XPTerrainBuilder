"""#2206 step 4: THE §5a LP MEMO ACROSS STAGE-1 PASSES (``solve/
feasibility.LpMemo``; spec ``one-map-solve-spec-20261123.md``).

Synthetic twins on ``test_apronhard``'s problems: a pass on the SAME hard
set takes the earlier pass's LP answer without solving, and the demoted
rows and the report are the ones a fresh read gives (clocks and the memo
flag left out) — on a tie the canonical order breaks, on two relaxed
rows, and with the hard rows at other positions of ``one``.  A changed
bound, price or vertex table reads the LP again."""
from __future__ import annotations

import types

import numpy as np
import pytest
import scipy.sparse as sp

from auto_patch_v2.solve import feasibility as F
from auto_patch_v2.solve import project as PRJ
from tests.auto_patch_v2.test_apronhard import APRON, PAD, TAXI, _problem, law  # noqa: F401

#: the report's clocks and the memo's own flag
_CLOCKS = ("lp_wall_s", "tie_wall_s", "lp_memo", "over_budget")

#: either pad row alone could give the 3.5 m: the canonical tie-break picks
CONFLICT = [(APRON, {1: 1.0, 0: -1.0}, 1.5), (PAD, {0: 1.0}, 0.0), (PAD, {1: -1.0}, -5.0)]
#: a taxi cap against two apron chords: both chords give
TWO = [(TAXI, {0: 1.0, 1: -1.0}, -4.0), (APRON, {1: 1.0, 0: -1.0}, 1.5),
       (APRON, {1: 1.0, 0: -1.0}, 1.5)]


@pytest.fixture
def lp_calls(monkeypatch):
    calls = []
    real = PRJ._relax_lp

    def counted(*a, **k):
        calls.append(1)
        return real(*a, **k)
    monkeypatch.setattr(PRJ, "_relax_lp", counted)
    return calls


def _read(rep) -> dict:
    return {k: v for k, v in rep.as_dict().items() if k not in _CLOCKS}


@pytest.mark.parametrize("rows", [CONFLICT, TWO], ids=["tie", "two-relaxed"])
def test_a_second_pass_on_the_same_hard_set_is_the_lp_answer(law, lp_calls, rows):  # noqa: F811
    one, A, b, pl = _problem(rows)
    hard = np.arange(len(rows))
    fresh_d, fresh = F.check_hard_set(pl, law, one, hard, A, b, stage="1")
    memo = F.LpMemo()
    d1, r1 = F.check_hard_set(pl, law, one, hard, A, b, stage="1", memo=memo)
    n = len(lp_calls)
    d2, r2 = F.check_hard_set(pl, law, one, hard, A, b, stage="1", memo=memo)
    assert len(lp_calls) == n and memo.hits == 1          # the LP was not read
    assert not r1.lp_memo and r2.lp_memo and "memo" in r2.line()
    assert fresh.relaxed >= 1 and fresh.tie_break == "canonical"
    for d, r in ((d1, r1), (d2, r2)):
        assert d.tolist() == fresh_d.tolist()
        assert _read(r) == _read(fresh)
        assert r.conflicts == fresh.conflicts


def test_the_hard_rows_at_other_positions_of_one_still_hit(law, lp_calls):  # noqa: F811
    # a retarget pass's ``one`` may carry other priced rows before the hard
    # ones: the answer is keyed on the rows, the demoted indices re-read
    one, A, b, pl = _problem(CONFLICT)
    memo = F.LpMemo()
    d1, r1 = F.check_hard_set(pl, law, one, np.arange(3), A, b, memo=memo)
    pad_one = [(((0, 1.0),), 9.0, one[0][2])] + list(one)
    A2 = sp.vstack([sp.csr_matrix(([1.0], ([0], [0])), shape=(1, A.shape[1])), A]).tocsr()
    b2 = np.concatenate(([9.0], b))
    d2, r2 = F.check_hard_set(pl, law, pad_one, np.arange(1, 4), A2, b2, memo=memo)
    assert r2.lp_memo and memo.hits == 1
    assert (d2 - 1).tolist() == d1.tolist() and _read(r2) == _read(r1)


def test_a_changed_bound_price_or_vertex_table_reads_the_lp_again(law, lp_calls):  # noqa: F811
    one, A, b, pl = _problem(CONFLICT)
    memo = F.LpMemo()
    F.check_hard_set(pl, law, one, np.arange(3), A, b, memo=memo)
    b2 = b.copy()
    b2[2] = -6.0
    one2 = [*one[:2], (one[2][0], -6.0, one[2][2])]
    _d, r = F.check_hard_set(pl, law, one2, np.arange(3), A, b2, memo=memo)
    assert not r.lp_memo
    # another head: another tier, another price
    one3, A3, b3, _pl = _problem([CONFLICT[0], CONFLICT[1], (TAXI, {1: -1.0}, -5.0)])
    _d, r = F.check_hard_set(pl, law, one3, np.arange(3), A3, b3, memo=memo)
    assert not r.lp_memo
    # the same rows over another vertex table: the canonical rank may differ
    pl2 = types.SimpleNamespace(vertices=dict(pl.vertices))
    _d, r = F.check_hard_set(pl2, law, one, np.arange(3), A, b, memo=memo)
    assert not r.lp_memo and memo.hits == 0


def test_a_retargeted_stage_one_solve_is_byte_identical(law, monkeypatch):  # noqa: F811
    """The twin through ``solve_design``: the trend retarget's second
    stage-1 pass reads the same hard set (a target is never a hard row), so
    its LP is the first pass's; the surface is the one solved with the memo
    off, to the byte."""
    from auto_patch_v2.constraints import taxi_trend as tt
    from auto_patch_v2.solve import solve_design
    from tests.auto_patch_v2.test_v2trendcap import apron_problem  # noqa: F401
    from tests.auto_patch_v2.test_v2trendcap import _apron_vertices
    pm, cs, airport = apron_problem.__wrapped__(law)
    low = {v: float(pm.vertices[v].dem_z) - 2.0 for v in _apron_vertices(pm, law)}

    def rewrite(pm_x, _lv):                   # always a second pass
        return tt.stage_one_retarget(pm_x, law, airport, low)

    def arm() -> tuple:
        sol, rep = solve_design(pm, cs, law, trend_rewrite=rewrite)
        return np.asarray(sol.z, float).tobytes(), sol.status, rep.hard_conflict
    hits: list = []
    real_get = F.LpMemo.get

    def get(self, key, vertices):
        got = real_get(self, key, vertices)
        hits.append(got is not None)
        return got
    monkeypatch.setattr(F.LpMemo, "get", get)
    on = arm()
    assert any(hits), hits
    monkeypatch.setattr(F.LpMemo, "get", lambda self, key, vertices: None)
    off = arm()
    assert on == off
