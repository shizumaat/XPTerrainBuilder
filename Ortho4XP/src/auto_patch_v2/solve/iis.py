"""IRREDUCIBLE INFEASIBLE SUBSYSTEM — the seeded deletion filter (solver
benchmark finding 4; RULINGS 2026-09-03g), run ONLY when the LP reports
infeasible, answering "who minted the contradiction" (plan §2, the R1.3
question) as ``(row, source)`` pairs.

Seeded: the structural rows (pins, flats, bands) are the seed; the
generators' row groups are added one at a time until the system turns
infeasible — the first such group is culpable together with what came
before — then QuickXplain (a divide-and-conquer deletion filter,
``O(k · log n)`` feasibility probes for a conflict of size ``k``) finds
a MINIMAL conflict inside that group, and again inside the context.
Every probe is a HiGHS LP with a zero objective over a subset of rows
(0.01–1 s at these sizes).
"""
from __future__ import annotations

import numpy as np
from scipy.optimize import linprog

from ..model.constraints import ConstraintSet, Row, Source
from ..model.planar import PlanarMap
from .api import Options, Weights
from .assemble import to_sparse

__all__ = ["diagnose", "feasible", "quickxplain"]


def feasible(n: int, rows: list[Row]) -> bool:
    """Is the subsystem ``rows`` feasible over ``n`` variables?"""
    if not rows:
        return True
    S = to_sparse(ConstraintSet.from_rows(rows), n)
    bounds = [(None if not np.isfinite(S.lo[i]) else float(S.lo[i]),
               None if not np.isfinite(S.hi[i]) else float(S.hi[i]))
              for i in range(n)]
    res = linprog(np.zeros(n), A_ub=S.A_ub if S.A_ub.shape[0] else None,
                  b_ub=S.b_ub if S.b_ub.shape[0] else None,
                  A_eq=S.A_eq if S.A_eq.shape[0] else None,
                  b_eq=S.b_eq if S.b_eq.shape[0] else None,
                  bounds=bounds, method="highs")
    return res.status != 2


def quickxplain(n: int, background: list[Row], cand: list[Row]) -> list[Row]:
    """A minimal subset of ``cand`` that is infeasible together with
    ``background`` (Junker 2004), assuming ``background + cand`` is
    infeasible and ``background`` alone is feasible."""

    def qx(bg: list[Row], delta_nonempty: bool, c: list[Row]) -> list[Row]:
        if delta_nonempty and not feasible(n, bg):
            return []
        if len(c) == 1:
            return list(c)
        k = len(c) // 2
        c1, c2 = c[:k], c[k:]
        d2 = qx(bg + c1, bool(c1), c2)
        d1 = qx(bg + d2, bool(d2), c1)
        return d1 + d2

    return qx(list(background), False, list(cand))


def diagnose(planar: PlanarMap, cs: ConstraintSet, weights: Weights,
             options: Options) -> tuple[tuple[Row, Source], ...]:
    """The IIS as ``(row, source)`` pairs."""
    n = len(planar.vertices)
    seed: list[Row] = [*cs.pins, *cs.flats, *cs.bands]
    if not feasible(n, seed):
        core = quickxplain(n, [], seed)
        return tuple((r, r.source) for r in core)
    groups: dict[str, list[Row]] = {}
    for r in (*cs.diffs, *cs.offsets, *cs.linears):
        groups.setdefault(r.source.generator, []).append(r)
    keep = list(seed)
    for name in sorted(groups):
        rows = groups[name]
        if feasible(n, keep + rows):
            keep += rows
            continue
        core = quickxplain(n, keep, rows)
        ctx = quickxplain(n, core, keep) if keep else []
        return tuple((r, r.source) for r in (*ctx, *core))
    return ()
