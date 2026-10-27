"""THE SEEDED FIRST QP (owner RULINGS 2026-10-19am (a); #1270 / #803,
``docs/findings/solve-speed-lsolve.md``).

The passes after a stage's first — stage 1's retarget pass (2026-10-15i (3)
(b)), pass 1b and its weld re-widen (§57 (3) (ii-c)), stage 2's pin-yield
trials (#778) — each open with a QP at zero multipliers and the one-way rows
off, exactly as the pass before them did, on a problem that differs from it
by a few rows.  Started cold (the unconstrained least-squares point) that QP
pays as many rounds as the first pass's (HECA: 92–301); started from the
previous pass's FIRST QP answer it pays 29–39 and ends at the same convex
minimum within the QP's own convergence spread (≈1e-5 m).

The previous pass's FINAL surface is not the seed: it solves the shifted
problem (converged multipliers, lagged leaders), and from there the same QP
still takes 189 rounds (the warm start #1063 measured as noise).

One :class:`WarmSeed` per stage, shared by the ``_solve_stage`` calls of that
stage.  The seed is held PER VERTEX, so a pass whose reduction differs (a pin
released, a weld widened) still reads it: a column takes the value of its
vertices (a column is a class of vertices that share one value).
"""
from __future__ import annotations

import numpy as np

__all__ = ["WarmSeed"]


class WarmSeed:
    """The per-vertex surface of the last first QP a stage solved."""

    def __init__(self) -> None:
        self.z: np.ndarray | None = None

    def x0(self, red) -> np.ndarray | None:
        """The seed in ``red``'s columns, or ``None`` (cold) when there is no
        seed for this map."""
        if self.z is None or self.z.shape[0] != red.col.shape[0]:
            return None
        cols = np.asarray(red.col)
        free = cols >= 0
        x = np.zeros(int(red.n_cols))
        x[cols[free]] = self.z[free]
        return x

    def record(self, red, x: np.ndarray) -> None:
        """Keep this first QP's answer, per vertex."""
        cols = np.asarray(red.col)
        free = cols >= 0
        z = np.asarray(red.value, float).copy()
        z[free] = np.asarray(x, float)[cols[free]]
        self.z = z
