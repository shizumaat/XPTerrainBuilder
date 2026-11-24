"""Twin for #1270 lane ``lsplu`` (``solve/fill_order``): a stage's QPs run in
ONE fill-reducing column order.  Relabelling the columns keeps every row's
entries in their stored order, so each product and each round's normal
matrix holds the same values, only relabelled; the factorisation in that
order is the same algebra (the surface moves at rounding level) and the
order is taken once per stage."""
from __future__ import annotations

import numpy as np
import pytest
import scipy.sparse as sp
from auto_patch_v2.solve import design_qp, fill_order
from auto_patch_v2.solve.fill_order import ColumnOrder, relabelled
from auto_patch_v2.solve.round_normal import Prefix, RoundNormal


def _problem(seed: int, n: int = 400, m0: int = 900, m1: int = 1500):
    rng = np.random.default_rng(seed)
    A0 = sp.vstack([sp.identity(n, format="csr") * 0.3,
                    sp.random(m0 - n, n, density=0.01, random_state=seed)], format="csr")
    A1 = sp.random(m1, n, density=0.01, random_state=seed + 1, format="csr")
    U = sp.random(5, n, density=0.05, random_state=seed + 2, format="csr")
    return (A0, rng.normal(size=m0), A1, rng.normal(scale=0.1, size=m1),
            rng.uniform(1.0, 300.0, size=m1), np.zeros(m1), U, rng.normal(size=5))


def test_relabelled_products_are_the_same_terms():
    A0, _b0, A1, *_r = _problem(1)
    order = ColumnOrder()
    order.take(A0, A1, np.arange(0, A1.shape[0], 3))
    n = A0.shape[1]
    assert order.holds(n) and np.array_equal(np.sort(order.q), np.arange(n))
    x = np.random.default_rng(2).normal(loc=100.0, size=n)
    for A in (A0, A1):
        assert (relabelled(A, order.at) @ x[order.q]).tobytes() == (A @ x).tobytes()


def test_round_normal_in_order_is_the_relabelled_matrix():
    """The round's normal matrix built in the ordered columns IS the
    original one with rows and columns relabelled, value for value."""
    A0, b0, A1, *_r = _problem(3)
    W = A1[::2].tocsr()
    order = ColumnOrder()
    order.take(A0, A1, np.arange(0, A1.shape[0], 2))
    at, q = order.at, order.q
    base = RoundNormal(Prefix(A0, b0, A0.T.tocsr()), W, np.ones(W.shape[0]), None, "bordered")
    A0r, Wr = relabelled(A0, at), relabelled(W, at)
    ordered = RoundNormal(Prefix(A0r, b0, A0r.T.tocsr()), Wr, np.ones(W.shape[0]), None,
                          "bordered")
    want = base.N.tocsc()[q][:, q].tocsc()
    want.sort_indices()
    got = ordered.N.tocsc()
    got.sort_indices()
    assert np.array_equal(got.indptr, want.indptr) and np.array_equal(got.indices, want.indices)
    assert got.data.tobytes() == want.data.tobytes()


def test_stage_takes_one_order_and_the_surface_is_the_unordered_one(monkeypatch):
    """One order per stage (column count): later QPs reuse it; the surface
    equals the per-try path's (every matrix ordered by SuperLU) to rounding."""
    kw = dict(method="normal", solver_tol=1e-10, solver_max_iter=1000,
              low_rank="bordered", rel_tol=1e-12)
    taken = []
    real = ColumnOrder.take
    monkeypatch.setattr(ColumnOrder, "take",
                        lambda self, *a: (taken.append(1), real(self, *a))[1])
    for seed in (5, 6):
        A0, b0, A1, b1, w, shift, U, c = _problem(seed)
        order = ColumnOrder()
        first = design_qp.solve_one_sided(A0, b0, A1, b1, w, shift, None, U, c,
                                          order=order, **kw)
        again = design_qp.solve_one_sided(A0, b0, A1, b1, w, shift + 0.01, first.x, U, c,
                                          order=order, **kw)
        with monkeypatch.context() as m:
            m.setattr(design_qp, "RoundNormal", lambda *a, **k: None)
            ref = design_qp.solve_one_sided(A0, b0, A1, b1, w, shift, None, U, c, **kw)
        assert first.status == ref.status == "optimal" and again.status == "optimal"
        assert np.allclose(first.x, ref.x, rtol=0.0, atol=1e-8)
        assert first.objective == pytest.approx(ref.objective, rel=1e-10)
    assert len(taken) == 2 + 2           # one per stage (+ the reference's own)


def test_factor_in_order_keeps_the_given_order():
    """``factor_in_order`` factorises the ordered matrix as it stands
    (SuperLU's ``NATURAL`` order) and solves it."""
    A0, _b0, A1, *_r = _problem(7)
    order = ColumnOrder()
    order.take(A0, A1, np.arange(A1.shape[0]))
    S = sp.vstack([relabelled(A0, order.at), relabelled(A1, order.at)], format="csr")
    N = (S.T @ S + sp.identity(S.shape[1])).tocsc()
    lu = fill_order.factor_in_order(N)
    r = np.random.default_rng(8).normal(size=N.shape[0])
    assert np.allclose(N @ lu.solve(r), r, atol=1e-9)
