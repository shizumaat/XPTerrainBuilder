"""THE VARIANCE PROGRAM's model and backends (RULINGS 2026-09-04t(1);
``solve/relax.py`` module docstring, step 3) — split out of ``relax.py``
(lane v2relaxfull, the 1,000-line law) verbatim:

* :func:`model` — columns ``z`` then one block per relaxed element (a
  Diff / Linear: its slack; a pad: ``zc, u, v`` — one PLANE bounded to the
  ``pad_slope_max`` disc, 05f), the un-relaxed rows as they stand; then
  (RULINGS 2026-09-06h (b)) the RUNWAY family's L1 DEM-fit columns ``t``
  at the preference ladder's runway weight and (06h (c)) the runway
  ridge's L1 second-difference columns ``r`` at its smoothness λ — the
  LINEAR part of the objective beside the slack variance, so the slack
  is placed where it costs the runway nothing before the runway is sunk
  (HECA 05C/23C: stage 1 blind to the runway sank it 2.7 m to spare
  apron pav132's chords);
* :func:`qp` — highspy's exact QP ``min Σ weight · x²``;
* :func:`pieces` / :func:`pwl` — the CONVEX PIECEWISE-LINEAR approximation
  of the square on scipy's HiGHS LP (``max_pieces`` pieces from the
  materiality doubling), the answer past ``qp_max_rows`` / the QP budget.

Imports ``model`` and its siblings only (04q-3).
"""
from __future__ import annotations

import dataclasses as _dc
import math
import time
import typing as _t

import numpy as np
import scipy.sparse as sp
from scipy.optimize import linprog

from ..model.constraints import ConstraintSet, Row
from ..model.planar import PlanarMap
from .assemble import to_sparse

__all__ = ["Model", "SLOPE_DIRECTIONS", "model", "slack_bound", "qp", "pieces", "pwl",
           "qp_available", "without"]


def qp_available() -> bool:
    """Is the ``highspy`` QP backend importable?"""
    try:
        import highspy  # noqa: F401
    except ImportError:
        return False
    return True


class _HasRow(_t.Protocol):
    """What :func:`model` reads of a ``relax.Relaxed``."""

    index: int
    kind: str
    row: Row
    extent_m: float
    offsets: tuple[tuple[int, float, float], ...]


def without(cs: ConstraintSet, relaxed: _t.Sequence[_HasRow]) -> ConstraintSet:
    """``cs`` minus the relaxed elements' own rows (by identity)."""
    drop = {id(x.row) for x in relaxed}
    return ConstraintSet.from_rows(r for r in cs.rows() if id(r) not in drop)


@_dc.dataclass
class Model:
    """Columns: ``z`` (n), then one block per relaxed element — a Diff /
    Linear: ``s``; a pad: ``zc, u, v``.  ``quad`` names the columns the
    square charges (``u`` / ``v`` free, ``s ≥ 0``)."""

    n: int
    ncol: int
    A_ub: sp.csr_matrix
    b_ub: np.ndarray
    A_eq: sp.csr_matrix
    b_eq: np.ndarray
    lo: np.ndarray
    hi: np.ndarray
    quad: list[int]
    col_of: dict[int, tuple[int, ...]]   # relaxed element index -> its columns
    #: the square's weight per quad column (``d`` for a Diff's grade, 1 for
    #: a Linear's metres, ``D`` for a pad's slope components)
    weight: dict[int, float] = _dc.field(default_factory=dict)
    #: quad columns charged in GRADE units (pieces from the grade materiality)
    grade_cols: set[int] = _dc.field(default_factory=set)
    #: the LINEAR objective over every column (the runway fit ``t`` and
    #: smoothness ``r`` columns, 06h b/c; zero elsewhere)
    lin_cost: np.ndarray = _dc.field(default_factory=lambda: np.zeros(0))
    #: how many fit / smoothness columns and rows the linear part added
    linear_cols: int = 0
    linear_rows: int = 0


#: Directions of the polygonal bound on a relaxed pad's gradient
#: (``model``): a regular polygon INSCRIBED in the ``pad_slope_max`` disc,
#: so the true gradient never exceeds the table value in any direction.
SLOPE_DIRECTIONS = 32


def slack_bound(x: _HasRow, max_over_cap_factor: float | None) -> float:
    """THE RELAXATION'S SHAPE (RULINGS 2026-09-05ae(2), ``[relaxation]
    max_over_cap_factor``): the most a relaxed row may take — a Diff's
    GRADE excess at most ``(factor − 1) × cap`` (its metres then
    ``(factor − 1) × cap × d``: a 2.55 m edge at 1 % carries 0.04 m at
    2.0, never 1.33 m); a Linear's metre slack at most ``(factor − 1) ×``
    its own bound magnitude (``cap × d`` plus the reader's envelope, the
    row's statement of the law); an equality row (bound 0) may not open
    at all — a weld or a plane tie relaxed is a STEP, which 04t(1)
    forbids.  ``inf`` with no factor (the pre-05ae program)."""
    if max_over_cap_factor is None or not math.isfinite(max_over_cap_factor):
        return math.inf
    k = max(0.0, max_over_cap_factor - 1.0)
    r = x.row
    if x.kind == "diff":
        return k * float(r.cap)                              # type: ignore[attr-defined]
    if x.kind == "linear":
        mags = [abs(float(b)) for b in (r.hi, r.lo)           # type: ignore[attr-defined]
                if b is not None and math.isfinite(float(b))]
        return k * (max(mags) if mags else 0.0)
    return math.inf


def model(pm: PlanarMap, cs: ConstraintSet, relaxed: _t.Sequence[_HasRow],
           pad_slope_max: float | None = None,
           max_over_cap_factor: float | None = None,
           fit: _t.Mapping[int, tuple[float, float]] | None = None,
           smooth: _t.Sequence[tuple[int, int, int, float, float, float]] = ()
           ) -> Model:
    """``pad_slope_max`` (RULINGS 2026-09-05f, ``[relaxation]``): every
    relaxed pad's plane ``(u, v)`` is bounded to the disc of that radius
    (``SLOPE_DIRECTIONS`` half-planes ``u·cosθ + v·sinθ ≤ s·cos(π/K)``,
    whose polygon lies INSIDE the disc: |u|, |v| ≤ s among them), so the
    variance program spreads the relief a steeper pad would have taken
    over the other populations (04t-1).  ``max_over_cap_factor`` (RULINGS
    2026-09-05ae(2)): every Diff / Linear slack column is bounded above by
    :func:`slack_bound` — a slight over-cap, never a cliff.  ``fit``
    (06h b): vertex -> ``(weight, target)`` — one L1 column ``t ≥ |z −
    target|`` charged ``weight`` (the runway family at the ladder's
    runway weight); ``smooth`` (06h c): ``(a, m, c, dp, dn, λ)`` stations
    (``assemble.roughness_stations``) — one L1 column ``r ≥ |Δgrade| ×
    span`` charged ``λ``."""
    n = len(pm.vertices)
    S = to_sparse(without(cs, relaxed), n)
    ncol = n
    col_of: dict[int, tuple[int, ...]] = {}
    quad: list[int] = []
    weight: dict[int, float] = {}
    grade_cols: set[int] = set()
    for x in relaxed:
        if x.kind == "pad":
            col_of[x.index] = (ncol, ncol + 1, ncol + 2)
            quad += [ncol + 1, ncol + 2]
            weight[ncol + 1] = weight[ncol + 2] = x.extent_m
            grade_cols.update((ncol + 1, ncol + 2))
            ncol += 3
        else:
            col_of[x.index] = (ncol,)
            quad.append(ncol)
            weight[ncol] = x.extent_m if x.kind == "diff" else 1.0
            if x.kind == "diff":
                grade_cols.add(ncol)
            ncol += 1
    ub_r: list[int] = []
    ub_c: list[int] = []
    ub_v: list[float] = []
    ub_b: list[float] = []
    eq_r: list[int] = []
    eq_c: list[int] = []
    eq_v: list[float] = []
    eq_b: list[float] = []

    def ub(terms, b):
        k = len(ub_b)
        for c, v in terms:
            ub_r.append(k); ub_c.append(c); ub_v.append(v)
        ub_b.append(b)

    def eq(terms, b):
        k = len(eq_b)
        for c, v in terms:
            eq_r.append(k); eq_c.append(c); eq_v.append(v)
        eq_b.append(b)

    # THE LINEAR PART (06h b/c): the runway fit and smoothness columns
    lin: dict[int, float] = {}
    n_lin_rows = 0
    for vid, (wt, target) in sorted((fit or {}).items()):
        if wt <= 0.0:
            continue
        tc = ncol; ncol += 1
        lin[tc] = float(wt)
        ub(((vid, 1.0), (tc, -1.0)), float(target))
        ub(((vid, -1.0), (tc, -1.0)), -float(target))
        n_lin_rows += 2
    for a_, m_, c_, dp, dn, lam in smooth:
        if lam <= 0.0:
            continue
        rc = ncol; ncol += 1
        lin[rc] = float(lam)
        scale = 0.5 * (dp + dn)
        terms = ((c_, scale / dn), (m_, -scale * (1.0 / dn + 1.0 / dp)), (a_, scale / dp))
        ub(terms + ((rc, -1.0),), 0.0)
        ub(tuple((v, -k) for v, k in terms) + ((rc, -1.0),), 0.0)
        n_lin_rows += 2
    n_lin_cols = len(lin)
    for x in relaxed:
        cols = col_of[x.index]
        r = x.row
        if x.kind == "diff":
            g = cols[0]                      # grade excess: |Δz| ≤ (cap + g)·d
            ub(((r.a, 1.0), (r.b, -1.0), (g, -r.d)), r.cap * r.d)
            ub(((r.b, 1.0), (r.a, -1.0), (g, -r.d)), r.cap * r.d)
        elif x.kind == "linear":
            s = cols[0]
            if r.hi is not None:
                ub(tuple(r.terms) + ((s, -1.0),), r.hi)
            if r.lo is not None:
                ub(tuple((v, -c) for v, c in r.terms) + ((s, -1.0),), -r.lo)
        else:
            zc, u, v = cols                  # the plane: z = zc + u·dx + v·dy
            for vid, dx, dy in x.offsets:
                eq(((vid, 1.0), (zc, -1.0), (u, -dx), (v, -dy)), 0.0)
            if pad_slope_max is not None and math.isfinite(pad_slope_max):
                K = SLOPE_DIRECTIONS
                b = pad_slope_max * math.cos(math.pi / K)
                for k in range(K):
                    th = 2.0 * math.pi * k / K
                    ub(((u, math.cos(th)), (v, math.sin(th))), b)
    A_ub = sp.vstack([sp.hstack([S.A_ub, sp.csr_matrix((S.A_ub.shape[0], ncol - n))]),
                      sp.csr_matrix((ub_v, (ub_r, ub_c)), shape=(len(ub_b), ncol))],
                     format="csr")
    A_eq = sp.vstack([sp.hstack([S.A_eq, sp.csr_matrix((S.A_eq.shape[0], ncol - n))]),
                      sp.csr_matrix((eq_v, (eq_r, eq_c)), shape=(len(eq_b), ncol))],
                     format="csr")
    lo = np.concatenate([S.lo, np.full(ncol - n, -np.inf)])
    hi = np.concatenate([S.hi, np.full(ncol - n, np.inf)])
    for x in relaxed:
        if x.kind != "pad":
            lo[col_of[x.index][0]] = 0.0
            hi[col_of[x.index][0]] = slack_bound(x, max_over_cap_factor)
    lin_cost = np.zeros(ncol)
    for j, wt in lin.items():
        lin_cost[j] = wt
        lo[j] = 0.0
    return Model(n, ncol, A_ub, np.concatenate([S.b_ub, np.asarray(ub_b, float)]),
                  A_eq, np.concatenate([S.b_eq, np.asarray(eq_b, float)]),
                  lo, hi, quad, col_of, weight, grade_cols, lin_cost, n_lin_cols, n_lin_rows)


def qp(m: Model, time_limit_s: float | None) -> tuple[str, np.ndarray | None, float]:
    """``min Σ_quad x_j²`` through highspy's QP.  Returns (status, x, wall)."""
    import highspy
    t0 = time.perf_counter()
    h = highspy.Highs()
    h.silent()
    if time_limit_s is not None:
        h.setOptionValue("time_limit", float(time_limit_s))
    inf = highspy.kHighsInf
    A = sp.vstack([m.A_ub, m.A_eq], format="csc")
    lp = highspy.HighsLp()
    lp.num_col_ = m.ncol
    lp.num_row_ = A.shape[0]
    lp.col_cost_ = m.lin_cost if len(m.lin_cost) == m.ncol else np.zeros(m.ncol)
    lp.col_lower_ = np.where(np.isfinite(m.lo), m.lo, -inf)
    lp.col_upper_ = np.where(np.isfinite(m.hi), m.hi, inf)
    lp.row_lower_ = np.concatenate([np.full(m.A_ub.shape[0], -inf), m.b_eq])
    lp.row_upper_ = np.concatenate([m.b_ub, m.b_eq])
    lp.a_matrix_.format_ = highspy.MatrixFormat.kColwise
    lp.a_matrix_.start_ = A.indptr
    lp.a_matrix_.index_ = A.indices
    lp.a_matrix_.value_ = A.data
    h.passModel(lp)
    hess = highspy.HighsHessian()
    hess.dim_ = m.ncol
    start = np.zeros(m.ncol + 1, dtype=np.int64)
    qs = sorted(m.quad)
    for j in qs:
        start[j + 1:] += 1
    hess.start_ = start
    hess.index_ = np.asarray(qs, dtype=np.int32)
    hess.value_ = np.asarray([2.0 * m.weight.get(j, 1.0) for j in qs], float)
    h.passHessian(hess)
    h.run()
    st = h.getModelStatus()
    wall = time.perf_counter() - t0
    if st == highspy.HighsModelStatus.kInfeasible:
        return "infeasible", None, wall
    if st == highspy.HighsModelStatus.kTimeLimit:
        return "time_limit", None, wall
    if st not in (highspy.HighsModelStatus.kOptimal,):
        return f"error:{st}", None, wall
    return "optimal", np.asarray(h.getSolution().col_value, float), wall


def pieces(materiality_m: float, k: int) -> list[tuple[float, float]]:
    """``k`` convex pieces of ``x²`` on ``x ≥ 0``: breakpoints ``m·(2^i −
    1)``, each piece ``(width, slope)`` with slope ``b_i + b_{i−1}`` (the
    chord's slope of the square), the last unbounded."""
    out: list[tuple[float, float]] = []
    prev = 0.0
    for i in range(1, k + 1):
        b = materiality_m * (2.0 ** i - 1.0)
        out.append(((np.inf if i == k else b - prev), b + prev))
        prev = b
    return out


def pwl(m: Model, grade_pieces: list[tuple[float, float]],
         metre_pieces: list[tuple[float, float]], time_limit_s: float | None
         ) -> tuple[str, np.ndarray | None, float]:
    """The convex piecewise-linear approximation on scipy's HiGHS LP: each
    quadratic column ``x`` becomes ``x = Σ p_k`` (a free ``x``: ``Σ p⁺_k −
    Σ p⁻_k``), ``0 ≤ p_k ≤ width_k``, cost ``weight · slope_k``."""
    t0 = time.perf_counter()
    K = len(grade_pieces)
    assert len(metre_pieces) == K
    extra = 0
    blocks: list[tuple[int, int, int]] = []   # (column, +block start, -block start or -1)
    for j in m.quad:
        neg = m.lo[j] < 0.0
        blocks.append((j, m.ncol + extra, (m.ncol + extra + K) if neg else -1))
        extra += 2 * K if neg else K
    ncol = m.ncol + extra
    c = np.zeros(ncol)
    if len(m.lin_cost) == m.ncol:
        c[:m.ncol] = m.lin_cost
    lo = np.concatenate([m.lo, np.zeros(extra)])
    hi = np.concatenate([m.hi, np.zeros(extra)])
    r_: list[int] = []
    c_: list[int] = []
    v_: list[float] = []
    for row, (j, pos, neg) in enumerate(blocks):
        r_.append(row); c_.append(j); v_.append(1.0)
        pieces = grade_pieces if j in m.grade_cols else metre_pieces
        wt = m.weight.get(j, 1.0)
        for k, (w, s) in enumerate(pieces):
            c[pos + k] = wt * s
            hi[pos + k] = w
            r_.append(row); c_.append(pos + k); v_.append(-1.0)
            if neg >= 0:
                c[neg + k] = wt * s
                hi[neg + k] = w
                r_.append(row); c_.append(neg + k); v_.append(1.0)
    link = sp.csr_matrix((v_, (r_, c_)), shape=(len(blocks), ncol))
    A_ub = sp.hstack([m.A_ub, sp.csr_matrix((m.A_ub.shape[0], extra))], format="csr")
    A_eq = sp.vstack([sp.hstack([m.A_eq, sp.csr_matrix((m.A_eq.shape[0], extra))]), link],
                     format="csr")
    b_eq = np.concatenate([m.b_eq, np.zeros(len(blocks))])
    bounds = [(None if not np.isfinite(lo[i]) else float(lo[i]),
               None if not np.isfinite(hi[i]) else float(hi[i])) for i in range(ncol)]
    opts = {"disp": False, "presolve": True}
    if time_limit_s is not None:
        opts["time_limit"] = float(time_limit_s)
    res = linprog(c, A_ub=A_ub, b_ub=m.b_ub, A_eq=A_eq, b_eq=b_eq, bounds=bounds,
                  method="highs", options=opts)
    wall = time.perf_counter() - t0
    if res.status == 2:
        return "infeasible", None, wall
    if res.status != 0 or res.x is None:
        return f"error:{res.status}", None, wall
    return "optimal", np.asarray(res.x[:m.ncol], float), wall


