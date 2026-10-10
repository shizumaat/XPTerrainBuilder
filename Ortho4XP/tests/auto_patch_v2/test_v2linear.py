"""THE NORMAL SOLVE'S FLOOR IS CENTRED ON THE WARM START (lane ``pass2``,
``docs/briefs/pass2-notes.md`` step 4; spec §61 (0)'s class).

``solve/linear._linear_solve`` keeps its factorisation non-singular with
``eps · I``, ``eps = 1e-12 · max diag(AᵀA)``.  Solved for ``x`` itself that
is a spring to z = 0 on every column, sized by the STIFFEST row: beside
hard rows at 3e5 it held a column priced at 1.0 to sea level nearly as
hard as to its neighbours, the QP stopped where the spring balanced the
descent, and a constraint the surface already satisfied moved the weak
blocks (HECA pass 2: 164 vertices, KCLT pass 1b: 47).  The twins: a weak
chain between two hard anchors, 200 m up.
"""
from __future__ import annotations

import numpy as np
import pytest
import scipy.sparse as sp
from scipy.sparse.linalg import splu

from auto_patch_v2.solve.linear import LOW_RANK_MODES, _linear_solve

#: the hard rows' weight in the solve (``[design] hard_weight`` 3e5), as √w
HARD = float(np.sqrt(3.0e5))
N_CHAIN = 120


def _chain() -> tuple[sp.csr_matrix, np.ndarray, np.ndarray]:
    """``(A, b, the exact minimiser)``: 120 columns tied to their
    neighbours by first-difference rows at 1.0 (the membrane's price), the
    two ends held at 200 m and 203 m by hard rows."""
    rows, b = [], []
    for i in range(N_CHAIN - 1):
        r = np.zeros(N_CHAIN)
        r[i], r[i + 1] = 1.0, -1.0
        rows.append(r)
        b.append(0.0)
    for i, z in ((0, 200.0), (N_CHAIN - 1, 203.0)):
        r = np.zeros(N_CHAIN)
        r[i] = HARD
        rows.append(r)
        b.append(HARD * z)
    A = np.array(rows)
    bb = np.array(b)
    return sp.csr_matrix(A), bb, np.linalg.lstsq(A, bb, rcond=None)[0]


def _solve(A, b, x0, U=None, c=None, low_rank="bordered"):
    return _linear_solve(A, b, x0, "normal", 1e-8, 20000, U, c, low_rank)


def test_the_floor_alone_is_a_spring_to_sea_level():
    """WHAT THE TWINS BELOW PROTECT AGAINST, stated once: the floored
    normal equations solved for ``x`` itself put the middle of the chain
    centimetres under the line between its anchors."""
    A, b, ref = _chain()
    N = (A.T @ A).tocsc()
    eps = 1e-12 * float(abs(N.diagonal()).max())
    x = splu((N + eps * sp.identity(N_CHAIN, format="csc")).tocsc()).solve(A.T @ b)
    assert np.max(ref - x) > 0.05, "the fixture no longer shows the spring"


def test_an_optimum_handed_back_as_the_warm_start_stays_put():
    A, b, ref = _chain()
    assert np.max(np.abs(_solve(A, b, ref) - ref)) < 1e-9


def test_a_warm_start_beside_the_optimum_lands_on_it():
    A, b, ref = _chain()
    x0 = ref + 0.05 * np.sin(np.arange(N_CHAIN))
    assert np.max(np.abs(_solve(A, b, x0) - ref)) < 1e-4


def test_the_cold_solve_is_refined_once():
    A, b, ref = _chain()
    assert np.max(np.abs(_solve(A, b, None) - ref)) < 1e-3


@pytest.mark.parametrize("mode", LOW_RANK_MODES)
def test_every_low_rank_mode_is_the_same_algebra(mode):
    """A per-body datum row (the chain's mean at 201 m, weight 0.5) held
    out of the factorisation: each mode meets the stacked dense problem's
    minimiser, cold and from a warm start."""
    A, b, _ref = _chain()
    U = sp.csr_matrix(np.full((1, N_CHAIN), 0.5 / N_CHAIN))
    c = np.array([0.5 * 201.0])
    ref = np.linalg.lstsq(np.vstack([A.toarray(), U.toarray()]),
                          np.concatenate([b, c]), rcond=None)[0]
    assert np.max(np.abs(_solve(A, b, None, U, c, mode) - ref)) < 1e-3
    assert np.max(np.abs(_solve(A, b, ref, U, c, mode) - ref)) < 1e-9
