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
from auto_patch_v2.solve.round_normal import RoundNormal


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


def _stack(seed: int, nx: int = 100, ny: int = 90):
    rng = np.random.default_rng(seed)
    n = nx * ny
    anchor = sp.identity(n, format="csr")[rng.random(n) < 0.05]
    S = sp.vstack([anchor, _grid_rows(rng, nx, ny, 0.9),
                   _grid_rows(rng, nx, ny, 0.3)], format="csr")
    # an empty column (no diagonal in SᵀS) and an explicit zero entry
    S = S.tocsc()
    S.data[S.indptr[n // 3]:S.indptr[n // 3 + 1]] = 0.0
    S = S.tocsr()
    S.eliminate_zeros()
    S.data[0] = 0.0
    b = rng.normal(size=S.shape[0])
    x0 = rng.normal(loc=150.0, scale=20.0, size=n)
    k = 7
    U = sp.random(k, n, density=0.002, random_state=seed + 2, format="csr")
    c = rng.normal(size=k)
    return S, b, x0, U, c


def _per_try(S, b, x0, lam, U, c, low_rank):
    root = float(np.sqrt(lam))
    n = S.shape[1]
    A = sp.vstack([S, root * sp.identity(n, format="csr")], format="csr")
    rhs = np.concatenate([b, root * x0])
    return _linear_solve(A, rhs, x0, "normal", 1e-10, 100, U, c, low_rank)


@pytest.mark.parametrize("low_rank", ["bordered", "woodbury", None])
def test_shared_round_normal_is_the_per_try_solve_byte_for_byte(low_rank):
    pool = ThreadPoolExecutor(4)
    try:
        for seed in (1, 2):
            S, b, x0, U, c = _stack(seed)
            if low_rank is None:
                U = c = None
            mode = low_rank or "bordered"
            for workers, p in ((1, None), (4, pool)):
                rn = RoundNormal(S, b, p, workers)
                for lam in (6.0, 0.25 ** 9, 1e-9):
                    want = _per_try(S, b, x0, lam, U, c, mode)
                    got = rn.solve(x0, lam, U, c, mode)
                    assert got.tobytes() == want.tobytes()
    finally:
        pool.shutdown()


def test_row_blocks_engage_on_a_wide_stack():
    S, _b, _x0, _U, _c = _stack(4)
    assert S.shape[1] // round_normal._BLOCK_MIN_COLS >= 2


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
    """The whole QP with its tries on the shared product returns the bytes,
    status and counts of the per-try path (``RoundNormal`` withheld)."""
    kw = dict(method="normal", solver_tol=1e-10, solver_max_iter=1000,
              low_rank="bordered", rel_tol=1e-12)
    for seed in (1, 2):
        prob = _problem(seed)
        new = design_qp.solve_one_sided(*prob, None, None, None, **kw)
        with monkeypatch.context() as m:
            m.setattr(design_qp, "RoundNormal", lambda *a, **k: None)
            old = design_qp.solve_one_sided(*prob, None, None, None, **kw)
        assert new.x.tobytes() == old.x.tobytes()
        assert (new.status, new.rounds, new.solves, new.objective) == \
            (old.status, old.rounds, old.solves, old.objective)
        assert old.solves > old.rounds        # the fixture does back off
