"""Twins for lane ``perf149`` (issue #149): two build-time changes that must
leave the surface BYTE-identical.

1. ``solve/design_qp``'s backoff tries are factorised ``_SPECULATE`` at a
   time and read in order: the result — iterate, status, rounds, solves —
   is exactly the one-at-a-time loop's.
2. ``constraints/geometry.chains_within`` answers exactly what the walk of
   every segment of every chain answers (``project_to_chain <= r``).
"""
from __future__ import annotations

import random

import numpy as np
import scipy.sparse as sp

from auto_patch_v2.constraints.geometry import chains_within, project_to_chain
from auto_patch_v2.solve import design_qp


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


def _solve(prob, speculate: int, monkeypatch):
    monkeypatch.setattr(design_qp, "_SPECULATE", speculate)
    A0, b0, A1, b1, w, shift = prob
    return design_qp.solve_one_sided(A0, b0, A1, b1, w, shift, None, None, None,
                                     method="normal", solver_tol=1e-10,
                                     solver_max_iter=1000, low_rank="bordered",
                                     rel_tol=1e-12)


def test_concurrent_backoff_is_the_sequential_loop_byte_for_byte(monkeypatch):
    for seed in (1, 2, 3):
        prob = _problem(seed)
        one = _solve(prob, 1, monkeypatch)
        for k in (2, 3):
            got = _solve(prob, k, monkeypatch)
            assert got.x.tobytes() == one.x.tobytes()
            assert (got.status, got.rounds, got.solves) == (one.status, one.rounds, one.solves)
            assert got.objective == one.objective
        assert one.solves > one.rounds        # the fixture does back off


def test_chains_within_is_the_segment_walk():
    rnd = random.Random(149)
    chains = []
    for _ in range(25):
        x, y = rnd.uniform(-2000, 2000), rnd.uniform(-2000, 2000)
        ch = [(x, y)]
        for _ in range(rnd.randint(1, 15)):
            x += rnd.uniform(-250, 250)
            y += rnd.uniform(-250, 250)
            ch.append((x, y))
        if rnd.random() < 0.3:
            ch.append(ch[-1])                 # a degenerate segment
        chains.append(ch)
    for r in (0.5, 4.0, 60.0):
        near = chains_within(chains, r)
        hits = 0
        for _ in range(20000):
            ch = rnd.choice(chains)
            k = rnd.randrange(len(ch) - 1)
            t = rnd.random()
            (ax, ay), (bx, by) = ch[k], ch[k + 1]
            p = (ax + t * (bx - ax) + rnd.uniform(-2 * r, 2 * r),
                 ay + t * (by - ay) + rnd.uniform(-2 * r, 2 * r))
            want = any(project_to_chain(p, c)[0] <= r for c in chains)
            hits += want
            assert near(p) == want
        assert hits > 0
