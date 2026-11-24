"""Twin for #1270 (``solve/round_normal``): a QP round's shared ``SᵀS``
gives each try EXACTLY the solve the per-try stack ``[S; √λ I]`` gave
through :func:`~auto_patch_v2.solve.linear._linear_solve` — byte for byte,
with and without the per-body low-rank term, its row blocks on threads or
not — and :func:`~auto_patch_v2.solve.design_qp.solve_one_sided` returns the
same surface whichever path its tries take."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pytest
import scipy.sparse as sp
from auto_patch_v2.solve import design_qp, round_normal
from auto_patch_v2.solve.linear import _linear_solve
from auto_patch_v2.solve.round_normal import Prefix, RoundNormal


def _grid_rows(rng, nx: int, ny: int, frac: float) -> sp.csr_matrix:
    """Difference rows between grid neighbours (a mesh's bending stencil):
    sparse factors, unlike a random matrix's dense fill."""
    idx = np.arange(nx * ny).reshape(ny, nx)
    pairs = np.concatenate([np.column_stack([idx[:, :-1].ravel(), idx[:, 1:].ravel()]),
                            np.column_stack([idx[:-1].ravel(), idx[1:].ravel()])])
    pairs = pairs[rng.random(len(pairs)) < frac]
    m = len(pairs)
    w = rng.uniform(0.1, 1e3, size=m)
    return sp.csr_matrix((np.column_stack([w, -w * rng.uniform(0.5, 1.5, m)]).ravel(),
                          pairs.ravel(), np.arange(0, 2 * m + 1, 2)),
                         shape=(m, nx * ny))


def _stack(seed: int, nx: int = 100, ny: int = 90, empty_col: bool = True):
    rng = np.random.default_rng(seed)
    n = nx * ny
    anchor = sp.identity(n, format="csr")[rng.random(n) < 0.05]
    A0 = sp.vstack([anchor, _grid_rows(rng, nx, ny, 0.9)], format="csr")
    # an empty column (no diagonal in the product) and an explicit zero
    A0 = A0.tocsc()
    if empty_col:
        A0.data[A0.indptr[n // 3]:A0.indptr[n // 3 + 1]] = 0.0
    A0 = A0.tocsr()
    A0.eliminate_zeros()
    A0.data[0] = 0.0
    W = _grid_rows(rng, nx, ny, 0.3)
    if empty_col:
        W = W.tocsc()
        W.data[W.indptr[n // 3]:W.indptr[n // 3 + 1]] = 0.0
        W = W.tocsr()
        W.eliminate_zeros()
    W.data[1] = 0.0
    b0 = rng.normal(size=A0.shape[0])
    bW = rng.normal(size=W.shape[0])
    x0 = rng.normal(loc=150.0, scale=20.0, size=n)
    k = 7
    U = sp.random(k, n, density=0.002, random_state=seed + 2, format="csr")
    c = rng.normal(size=k)
    return A0, b0, W, bW, x0, U, c


def _per_try(S, b, x0, lam, U, c, low_rank):
    root = float(np.sqrt(lam))
    n = S.shape[1]
    A = sp.vstack([S, root * sp.identity(n, format="csr")], format="csr")
    rhs = np.concatenate([b, root * x0])
    return _linear_solve(A, rhs, x0, "normal", 1e-10, 100, U, c, low_rank)


@pytest.mark.parametrize("empty_col", [False, True])
@pytest.mark.parametrize("low_rank", ["bordered", "woodbury", None])
def test_shared_round_normal_is_the_per_try_solve_byte_for_byte(low_rank, empty_col):
    """``empty_col``: a column no row reaches (no diagonal in the product,
    the rare layout); else every try rewrites the diagonal in place."""
    pool = ThreadPoolExecutor(4)
    fast = 0
    try:
        for seed in (1, 2):
            A0, b0, W, bW, x0, U, c = _stack(seed, empty_col=empty_col)
            if low_rank is None:
                U = c = None
            mode = low_rank or "bordered"
            S = sp.vstack([A0, W], format="csr")
            b = np.concatenate([b0, bW])
            for workers, p in ((1, None), (4, pool)):
                pre = Prefix(A0, b0, A0.T.tocsr(), p, workers)
                for W_, bW_, S_, b_ in ((W, bW, S, b),
                                        (sp.csr_matrix((0, A0.shape[1])), np.zeros(0),
                                         A0, b0)):
                    rn = RoundNormal(pre, W_, bW_, U, mode, p, workers)
                    assert rn.dpos is None or not empty_col
                    fast += rn.dpos is not None
                    for lam in (6.0, 0.25 ** 9, 1e-9):
                        want = _per_try(S_, b_, x0, lam, U, c, mode)
                        got = rn.solve(x0, lam, c)
                        assert got.tobytes() == want.tobytes()
    finally:
        pool.shutdown()
    assert (fast > 0) != empty_col


def test_row_blocks_engage_on_a_wide_stack():
    A0, *_rest = _stack(4)
    assert A0.shape[1] // round_normal._BLOCK_MIN_ROWS >= 2


def _problem(seed: int, n: int = 300, m0: int = 600, m1: int = 900):
    rng = np.random.default_rng(seed)
    A0 = sp.vstack([sp.identity(n, format="csr"),
                    sp.random(m0 - n, n, density=0.01, random_state=seed)],
                   format="csr")
    b0 = rng.normal(size=m0)
    A1 = sp.random(m1, n, density=0.02, random_state=seed + 1, format="csr")
    b1 = rng.normal(scale=0.1, size=m1)
    w = rng.uniform(1.0, 300.0, size=m1)
    return A0, b0, A1, b1, w, np.zeros(m1)


def test_qp_surface_is_the_per_try_path(monkeypatch):
    """The whole QP with its tries on the shared product returns the
    status and counts of the per-try path (``RoundNormal`` withheld) and its
    surface to rounding: the shared tries factorise in the stage's column
    order (``solve/fill_order``, lane ``lsplu``), the per-try path lets
    SuperLU order each matrix."""
    kw = dict(method="normal", solver_tol=1e-10, solver_max_iter=1000,
              low_rank="bordered", rel_tol=1e-12)
    for seed in (1, 2):
        prob = _problem(seed)
        new = design_qp.solve_one_sided(*prob, None, None, None, **kw)
        with monkeypatch.context() as m:
            m.setattr(design_qp, "RoundNormal", lambda *a, **k: None)
            old = design_qp.solve_one_sided(*prob, None, None, None, **kw)
        assert np.allclose(new.x, old.x, rtol=0.0, atol=1e-9)
        assert (new.status, new.rounds, new.solves) == (old.status, old.rounds, old.solves)
        assert new.objective == pytest.approx(old.objective, rel=1e-12)
        assert old.solves > old.rounds        # the fixture does back off


def test_bordered_is_bmat_array_for_array():
    """``linear._bordered`` writes ``bmat``'s canonical CSC directly."""
    from auto_patch_v2.solve.linear import _bordered
    rng = np.random.default_rng(1270)
    for t in range(12):
        n, k = int(rng.integers(5, 300)), int(rng.integers(1, 25))
        M = (sp.random(n, n, density=0.05, random_state=t, format="csc")
             + sp.identity(n, format="csc")).tocsc()
        U = sp.random(k, n, density=0.1, random_state=t + 100, format="csr")
        if t % 3 == 0:
            U.data[:3] = 0.0                       # explicit zeros are kept
        want = sp.bmat([[M, U.T], [U, -sp.identity(k, format="csc")]], format="csc")
        got = _bordered(M, U)
        assert np.array_equal(got.indptr, want.indptr)
        assert np.array_equal(got.indices, want.indices)
        assert got.data.tobytes() == want.data.tobytes()
