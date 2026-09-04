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

THE FAST PATH (lane v2relax, RULINGS 2026-09-04t(1) — the IIS is now on
the build path, inside ``emit.relaxation.iis_time_budget_s``): with
``highspy`` present, :func:`ray_candidates` solves the whole set ONCE
with presolve off and reads the DUAL RAY — the Farkas certificate — whose
support (rows, and the bands of the columns it leans on) is an
infeasible set a few dozen rows long; QuickXplain reduces it with tiny
scipy probes.  Measured HECA (1.8 M rows): the seeded filter alone took
73–126 s; the certificate LP 32 s + ~25 probes under a second.  The
seeded filter remains the path without ``highspy``, without a ray, and
``deadline`` (a ``time.perf_counter`` instant) raises
:class:`IISBudgetExceeded` on either path.
"""
from __future__ import annotations

import time
import typing as _t

import numpy as np
import scipy.sparse as sp
from scipy.optimize import linprog

from ..model.constraints import Band, ConstraintSet, Row, Source
from ..model.planar import PlanarMap
from .api import Options, Weights
from .assemble import to_sparse

__all__ = ["IISBudgetExceeded", "ray_candidates", "diagnose", "feasible", "quickxplain"]


class IISBudgetExceeded(RuntimeError):
    """The IIS search passed its wall budget."""


def feasible(n: int, rows: list[Row]) -> bool:
    """Is the subsystem ``rows`` feasible over ``n`` variables?  (A fresh
    scipy LP over the subset; the fast path is :func:`ray_candidates`.)"""
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


def ray_candidates(n: int, cs: ConstraintSet, time_limit_s: float | None = None
                   ) -> list[Row] | None:
    """THE FARKAS CERTIFICATE: the whole set as ONE HiGHS LP with presolve
    OFF (a reduced model carries no ray) and a zero objective; when it is
    infeasible the dual ray ``y`` names the rows in its support and, by
    ``Aᵀy``, the columns whose ``Band`` bounds it leans on — together an
    infeasible set a few dozen rows long (measured HECA: 23 rows + 2
    bands from 1.8 M, 32 s) that QuickXplain reduces with tiny probes.
    ``None`` when ``highspy`` is absent, the LP is feasible, or no ray
    is reported; raises :class:`IISBudgetExceeded` on the time limit."""
    try:
        import highspy
    except ImportError:
        return None
    S = to_sparse(cs, n)
    inf = highspy.kHighsInf
    nub = S.A_ub.shape[0]
    A = sp.vstack([S.A_ub, S.A_eq], format="csc")
    h = highspy.Highs()
    h.silent()
    h.setOptionValue("presolve", "off")
    if time_limit_s is not None:
        h.setOptionValue("time_limit", float(max(1.0, time_limit_s)))
    lp = highspy.HighsLp()
    lp.num_col_ = n
    lp.num_row_ = A.shape[0]
    lp.col_cost_ = np.zeros(n)
    lp.col_lower_ = np.where(np.isfinite(S.lo), S.lo, -inf)
    lp.col_upper_ = np.where(np.isfinite(S.hi), S.hi, inf)
    lp.row_lower_ = np.concatenate([np.full(nub, -inf), S.b_eq])
    lp.row_upper_ = np.concatenate([S.b_ub, S.b_eq])
    lp.a_matrix_.format_ = highspy.MatrixFormat.kColwise
    lp.a_matrix_.start_ = A.indptr
    lp.a_matrix_.index_ = A.indices
    lp.a_matrix_.value_ = A.data
    h.passModel(lp)
    h.run()
    st = h.getModelStatus()
    if st == highspy.HighsModelStatus.kTimeLimit:
        raise IISBudgetExceeded("the certificate LP hit the time limit")
    if st != highspy.HighsModelStatus.kInfeasible:
        return None
    got = h.getDualRay()
    if not (isinstance(got, tuple) and len(got) == 3 and got[1]):
        return None
    y = np.asarray(got[2], float)
    rows_nz = np.nonzero(np.abs(y) > 1e-9)[0]
    cand: dict[int, Row] = {}
    for k in rows_nz:
        r = S.ub_rows[k] if k < nub else S.eq_rows[k - nub]
        cand.setdefault(id(r), r)
    w = np.abs(A.T @ y)
    cols = set(np.nonzero(w > 1e-9)[0].tolist())
    for b in cs.bands:
        if b.v in cols:
            cand.setdefault(id(b), b)
    return list(cand.values())


def quickxplain(n: int, background: list[Row], cand: list[Row],
                probe: _t.Callable[[list[Row]], bool] | None = None) -> list[Row]:
    """A minimal subset of ``cand`` that is infeasible together with
    ``background`` (Junker 2004), assuming ``background + cand`` is
    infeasible and ``background`` alone is feasible.  ``probe(rows)``
    answers feasibility (default: :func:`feasible`)."""
    fz = probe or (lambda rows: feasible(n, rows))

    def qx(bg: list[Row], delta_nonempty: bool, c: list[Row]) -> list[Row]:
        if delta_nonempty and not fz(bg):
            return []
        if len(c) == 1:
            return list(c)
        k = len(c) // 2
        c1, c2 = c[:k], c[k:]
        d2 = qx(bg + c1, bool(c1), c2)
        d1 = qx(bg + d2, bool(d2), c1)
        return d1 + d2

    return qx(list(background), False, list(cand))


def _probe_for(n: int, cs: ConstraintSet, deadline: float | None
               ) -> _t.Callable[[list[Row]], bool]:
    def fz(rows: list[Row]) -> bool:
        if deadline is not None and time.perf_counter() > deadline:
            raise IISBudgetExceeded("scipy probes")
        return feasible(n, rows)

    return fz


def diagnose(planar: PlanarMap, cs: ConstraintSet, weights: Weights,
             options: Options, *, deadline: float | None = None,
             minimal: bool = True) -> tuple[tuple[Row, Source], ...]:
    """The IIS as ``(row, source)`` pairs; ``deadline`` (module docstring).
    ``minimal=False`` returns the Farkas SUPPORT as found — an infeasible
    subsystem, not reduced — which is what the last resort needs: its
    variance program gives a row in no conflict exactly zero slack, so
    the reduction buys nothing there, and a support that IS a 2,500-row
    chain (HECA 23C→05L along junction pav132's apron edge, 2026-09-05)
    costs QuickXplain O(k·log n) probes the IIS budget cannot pay."""
    n = len(planar.vertices)
    remaining = None if deadline is None else deadline - time.perf_counter()
    if remaining is not None and remaining <= 0.0:
        raise IISBudgetExceeded("no budget left before the certificate LP")
    cand = ray_candidates(n, cs, remaining)
    if cand and not feasible(n, cand):
        core = cand if not minimal else quickxplain(n, [], cand)
        return tuple((r, r.source) for r in core)
    fz = _probe_for(n, cs, deadline)
    seed: list[Row] = [*cs.pins, *cs.flats, *cs.bands]
    if not fz(seed):
        core = quickxplain(n, [], seed, fz)
        return tuple((r, r.source) for r in core)
    groups: dict[str, list[Row]] = {}
    for r in (*cs.diffs, *cs.offsets, *cs.linears):
        groups.setdefault(r.source.generator, []).append(r)
    keep = list(seed)
    for name in sorted(groups):
        rows = groups[name]
        if fz(keep + rows):
            keep += rows
            continue
        core = quickxplain(n, keep, rows, fz)
        ctx = quickxplain(n, core, keep, fz) if keep else []
        return tuple((r, r.source) for r in (*ctx, *core))
    return ()
