"""Twins for THE SEEDED FIRST QP (``solve/warm_seed``; RULINGS 2026-10-19am
(a); #1270 / #803, ``docs/findings/solve-speed-lsolve.md``).

1. the seed is held per vertex and read through ANY reduction of the same
   map: a column takes its vertices' value, a vertex the last pass pinned
   seeds the column its release opens, another map gets no seed;
2. a re-solve seeded with the previous first QP ends at the SAME convex
   minimum as the cold solve, in fewer rounds.
"""
from __future__ import annotations

import types

import numpy as np
import scipy.sparse as sp
from auto_patch_v2.solve.design_qp import solve_one_sided
from auto_patch_v2.solve.warm_seed import WarmSeed


def _red(col, value, n_cols):
    return types.SimpleNamespace(col=np.asarray(col, dtype=np.int64),
                                 value=np.asarray(value, float), n_cols=n_cols)


def test_seed_maps_through_another_reduction():
    seed = WarmSeed()
    assert seed.x0(_red([0, 1, -1], [0, 0, 5.0], 2)) is None      # nothing yet
    # vertices 0,1 share column 0 (a Flat), 2 is column 1, 3 is pinned at 9
    seed.record(_red([0, 0, 1, -1], [0, 0, 0, 9.0], 2), np.array([2.0, 3.0]))
    assert np.array_equal(seed.z, [2.0, 2.0, 3.0, 9.0])
    # the next pass: the pin released (vertex 3 its own column), the Flat split
    x0 = seed.x0(_red([1, 0, 2, 3], [0, 0, 0, 0], 4))
    assert np.array_equal(x0, [2.0, 2.0, 3.0, 9.0])
    # another map (a different vertex count) is never seeded
    assert seed.x0(_red([0, 1, 2], [0, 0, 0], 3)) is None


def _problem(rng, n=300, m1=1200):
    # a chain of bending rows (the always-on base) and one-sided caps
    rows, cols, vals = [], [], []
    for i in range(n - 1):
        rows += [i, i]
        cols += [i, i + 1]
        vals += [1.0, -1.0]
    A0 = sp.csr_matrix((vals, (rows, cols)), shape=(n - 1, n))
    A0 = sp.vstack([A0, 0.1 * sp.identity(n, format="csr")], format="csr")
    b0 = np.concatenate([np.zeros(n - 1), 0.1 * rng.normal(0.0, 5.0, n)])
    A1 = sp.random(m1, n, density=3.0 / n, random_state=7, format="csr")
    b1 = rng.normal(0.0, 1.0, m1)
    return A0, b0, A1, b1, np.full(m1, 30.0)


def _solve(A0, b0, A1, b1, w, x0):
    return solve_one_sided(A0, b0, A1, b1, w, np.zeros(A1.shape[0]), x0, None, None,
                           method="normal", solver_tol=1e-10, solver_max_iter=500,
                           low_rank="bordered", rel_tol=1e-12)


def test_seeded_resolve_reaches_the_cold_minimum():
    rng = np.random.default_rng(3)
    A0, b0, A1, b1, w = _problem(rng)
    red = _red(np.arange(A0.shape[1]), np.zeros(A0.shape[1]), A0.shape[1])
    seed = WarmSeed()
    seed.record(red, _solve(A0, b0, A1, b1, w, None).x)
    # the next pass moves a few rows' targets (the retarget / re-widen class)
    b1b = b1.copy()
    b1b[:20] -= 0.5
    cold = _solve(A0, b0, A1, b1b, w, None)
    warm = _solve(A0, b0, A1, b1b, w, seed.x0(red))
    assert cold.status == warm.status == "optimal"
    assert abs(warm.objective - cold.objective) <= 1e-9 * cold.objective
    assert float(np.max(np.abs(warm.x - cold.x))) < 1e-4
    assert warm.rounds <= cold.rounds
