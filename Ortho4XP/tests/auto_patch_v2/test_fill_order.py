"""Twin for #1270 lane ``lsplu`` (``solve/fill_order``): a QP orders its
factorisations ONCE.  The order is the one SuperLU chose for the QP's first
round, offered by that round and committed only between rounds; each later
round lays its matrix out in it (the same values, both indices permuted,
every column's rows sorted) and each try's factorisation in that order
solves the same system."""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import numpy as np
import scipy.sparse as sp
from auto_patch_v2.solve.fill_order import FillOrder
from auto_patch_v2.solve.linear import _bordered


def _bordered_system(seed: int, n: int = 600, k: int = 6) -> sp.csc_matrix:
    rng = np.random.default_rng(seed)
    S = sp.random(3 * n, n, density=0.004, random_state=seed, format="csr")
    N = (S.T @ S + sp.diags(rng.uniform(1.0, 2.0, n))).tocsc()
    U = sp.random(k, n, density=0.05, random_state=seed + 1, format="csr")
    return _bordered(N, U)


def test_the_first_order_offered_is_committed_between_rounds_only():
    M = _bordered_system(1)
    order = FillOrder()
    pool = ThreadPoolExecutor(2)
    try:
        lus = list(pool.map(order.factor, [M, M]))      # round 1's two tries
    finally:
        pool.shutdown()
    assert order.q is None                               # never inside a round
    order.commit()
    assert np.array_equal(order.q, np.argsort(lus[0].perm_c))
    assert np.array_equal(np.sort(order.q), np.arange(M.shape[0]))


def test_layout_is_the_symmetric_permutation_value_for_value():
    M = _bordered_system(2)
    order = FillOrder()
    order.factor(M)
    order.commit()
    q = order.q
    idx, ptr, src = order.layout(M)
    want = M[q][:, q].tocsc()
    want.sort_indices()
    assert np.array_equal(ptr, want.indptr) and np.array_equal(idx, want.indices)
    assert M.data[src].tobytes() == want.data.tobytes()
    assert order.layout(M[:-1, :-1].tocsc()) is None     # another size: no layout


def test_a_try_in_the_order_solves_the_same_system():
    M = _bordered_system(3)
    order = FillOrder()
    base = order.factor(M)
    order.commit()
    lay = order.layout(M)
    M2 = M.copy()
    M2.data = M2.data * 1.0
    M2.setdiag(M2.diagonal() + 0.25)                     # a later try's λ
    M2 = M2.tocsc()
    got = order.factor(M2, lay if M2.nnz == M.nnz else None)
    r = np.random.default_rng(4).normal(size=(M.shape[0], 3))
    assert np.allclose(M2 @ got.solve(r), r, atol=1e-9)
    assert np.allclose(M @ base.solve(r[:, 0]), r[:, 0], atol=1e-9)
