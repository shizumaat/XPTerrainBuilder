"""Stack the constraint rows into ONE sparse LP (plan §2; the
``ConstraintSet.to_sparse`` contract in ``model/constraints.py``).

Variables (column blocks):
  ``z``  one per planar-map vertex, ``0..n-1`` in id order;
  ``t``  one per vertex with a DEM sample: ``|z − dem| ≤ t`` (the L1
         fit, weighted by role — airside high, groundside 1);
  ``r``  one per interior breakline station: the L1 second difference
         (grade change per station) — the roughness term, weight λ.

Objective ``min Σ w_i t_i + λ Σ r_k`` — the L1 form the solver benchmark
measured (solver-benchmark-20260903.md finding 3a): a pure LP, solved
with the REAL objective (a zero-objective phase 1 wanders, finding 1).

Rows: ``Pin`` and ``Flat`` are equalities; ``Diff`` two inequalities;
``Offset`` one; ``Linear`` one per finite side; ``Band`` per-variable
bounds (tightest wins).  Row order within kind is preserved and
:func:`row_index` maps every inequality / equality row back to its
``Row`` for the IIS.
"""
from __future__ import annotations

import dataclasses as _dc
import math
import typing as _t

import numpy as np
import scipy.sparse as sp

from ..model.constraints import (Band, ConstraintSet, Diff, Flat, Linear,
                                 Offset, Pin, Row)  # noqa: F401 (Offset: row kinds)
from ..model.planar import PlanarMap
from .api import Weights

__all__ = ["Sparse", "to_sparse", "Problem", "assemble", "PREFERENCE_WEIGHT"]

#: Default charge of one unit of preference escalation, per metre of
#: relief, relative to the largest DEM-fit weight, for a group prefix
#: ``Weights.preference`` does not name: large enough that no DEM-fit gain
#: can buy an escalation the hard rows do not force (owner 2026-07-08
#: "only by the minimum").
PREFERENCE_WEIGHT = 1.0e4


@_dc.dataclass(frozen=True)
class Sparse:
    """The ``to_sparse`` product: constraint rows over ``n`` z-variables
    and the row -> ``Row`` maps."""

    A_eq: sp.csr_matrix
    b_eq: np.ndarray
    A_ub: sp.csr_matrix
    b_ub: np.ndarray
    lo: np.ndarray
    hi: np.ndarray
    eq_rows: tuple[Row, ...]        # one entry per A_eq row
    ub_rows: tuple[Row, ...]        # one entry per A_ub row
    soft: tuple[Row, ...] = ()      # the preference rows left to ``assemble``


def to_sparse(cs: ConstraintSet, n: int, soft: str = "ceiling") -> Sparse:
    """See ``ConstraintSet.to_sparse``'s contract.  ``soft``: how a
    preference ``Diff`` (``Diff.soft``) is stacked — ``"ceiling"`` (a
    hard row at its ceiling: IIS probes) or ``"defer"`` (left in
    ``Sparse.soft`` for :func:`assemble` to give a slack column)."""
    soft_rows: list[Row] = []
    eq_r: list[int] = []
    eq_c: list[int] = []
    eq_v: list[float] = []
    eq_b: list[float] = []
    eq_rows: list[Row] = []
    ub_r: list[int] = []
    ub_c: list[int] = []
    ub_v: list[float] = []
    ub_b: list[float] = []
    ub_rows: list[Row] = []
    lo = np.full(n, -np.inf)
    hi = np.full(n, np.inf)

    def eq(terms: _t.Sequence[tuple[int, float]], b: float, row: Row) -> None:
        k = len(eq_b)
        for v, c in terms:
            eq_r.append(k)
            eq_c.append(v)
            eq_v.append(c)
        eq_b.append(b)
        eq_rows.append(row)

    def ub(terms: _t.Sequence[tuple[int, float]], b: float, row: Row) -> None:
        k = len(ub_b)
        for v, c in terms:
            ub_r.append(k)
            ub_c.append(v)
            ub_v.append(c)
        ub_b.append(b)
        ub_rows.append(row)

    for p in cs.pins:
        eq(((p.v, 1.0),), p.z, p)
    for f in cs.flats:
        g0 = f.group[0]
        for gi in f.group[1:]:
            eq(((g0, 1.0), (gi, -1.0)), 0.0, f)
    for d in cs.diffs:
        if d.soft is not None and d.ceiling is not None:
            if soft == "defer":
                soft_rows.append(d)
                continue
            bound = max(d.cap, d.ceiling) * d.d
        else:
            bound = d.cap * d.d
        ub(((d.a, 1.0), (d.b, -1.0)), bound, d)
        ub(((d.b, 1.0), (d.a, -1.0)), bound, d)
    for o in cs.offsets:
        ub(((o.b, 1.0), (o.a, -1.0)), -o.min_delta, o)
    for ln in cs.linears:
        relax = 0.0
        if ln.soft is not None:
            if soft == "defer":
                soft_rows.append(ln)
                continue
            if ln.ceiling is None:
                continue              # fully relaxable: constrains nothing
            relax = max(0.0, ln.ceiling)
        if ln.lo is not None and ln.hi is not None and ln.lo == ln.hi and relax == 0.0:
            eq(ln.terms, ln.hi, ln)
            continue
        if ln.hi is not None:
            ub(ln.terms, ln.hi + relax, ln)
        if ln.lo is not None:
            ub(tuple((v, -c) for v, c in ln.terms), -(ln.lo - relax), ln)
    for b in cs.bands:
        if b.lo is not None:
            lo[b.v] = max(lo[b.v], b.lo)
        if b.hi is not None:
            hi[b.v] = min(hi[b.v], b.hi)
    A_eq = sp.csr_matrix((eq_v, (eq_r, eq_c)), shape=(len(eq_b), n))
    A_ub = sp.csr_matrix((ub_v, (ub_r, ub_c)), shape=(len(ub_b), n))
    return Sparse(A_eq, np.asarray(eq_b, float), A_ub, np.asarray(ub_b, float),
                  lo, hi, tuple(eq_rows), tuple(ub_rows), tuple(soft_rows))


@_dc.dataclass(frozen=True)
class Problem:
    """The LP ``linprog`` takes: ``c``, ``A_ub x ≤ b_ub``, ``A_eq x = b_eq``,
    bounds; ``n`` z-columns first.  ``row_map`` names the constraint
    ``Row`` of every A_ub / A_eq row that came from the set (``None`` for
    an objective-slack row)."""

    n: int
    c: np.ndarray
    A_ub: sp.csr_matrix
    b_ub: np.ndarray
    A_eq: sp.csr_matrix
    b_eq: np.ndarray
    bounds: list[tuple[float | None, float | None]]
    ub_rows: tuple[Row | None, ...]
    eq_rows: tuple[Row | None, ...]
    sparse: Sparse
    #: Preference slack columns: group name -> column index (the escalation
    #: of that group's cap, a grade fraction in ``[0, ceiling - cap]``).
    soft_cols: dict[str, int] = _dc.field(default_factory=dict)


def vertex_weights(planar: PlanarMap, weights: Weights) -> np.ndarray:
    """DEM-fit weight per vertex: the LARGEST weight of any incident
    face's role (airside pulls hardest), ``default`` where no face has
    a weight, ``zone3`` never (v2 emits no zone-3 vertex)."""
    n = len(planar.vertices)
    w = np.full(n, float(weights.default))
    role_w = dict(weights.by_role)
    for vid, v in planar.vertices.items():
        best: float | None = None
        for fid in v.incident_faces:
            rw = role_w.get(planar.faces[fid].role)
            if rw is not None:
                best = rw if best is None else max(best, rw)
        if best is not None:
            w[vid] = best
    return w


def assemble(planar: PlanarMap, cs: ConstraintSet, weights: Weights) -> Problem:
    """The whole LP."""
    n = len(planar.vertices)
    S = to_sparse(cs, n, soft="defer")
    dem = np.array([planar.vertices[i].dem_z if planar.vertices[i].dem_z is not None
                    else math.nan for i in range(n)], float)
    has_dem = ~np.isnan(dem)
    wv = vertex_weights(planar, weights)
    # roughness stations along breaklines (interior vertices of each chain)
    stations: list[tuple[int, int, int, float, float]] = []
    lam = float(weights.smoothness)
    if lam > 0.0:
        for b in planar.breaklines.values():
            ch = b.vertices(planar)
            for k in range(1, len(ch) - 1):
                a, m, c = ch[k - 1], ch[k], ch[k + 1]
                if len({a, m, c}) < 3:
                    continue
                (ax, ay), (mx, my), (cx, cy) = (planar.vertices[i].xy for i in (a, m, c))
                dp, dn = math.hypot(mx - ax, my - ay), math.hypot(cx - mx, cy - my)
                if dp > 1e-6 and dn > 1e-6:
                    stations.append((a, m, c, dp, dn))
    n_t = int(has_dem.sum())
    n_r = len(stations)
    # preference slacks (owner 2026-07-08): one column per escalation group,
    # bounded by the group's ceiling, charged far above any DEM-fit gain
    # (PREFERENCE_WEIGHT × the group's chord metres per unit of escalation)
    groups: dict[str, list[Row]] = {}
    for d in S.soft:
        groups.setdefault(d.soft, []).append(d)
    soft_cols = {g: n + n_t + n_r + j for j, g in enumerate(sorted(groups))}
    n_e = len(soft_cols)
    ncol = n + n_t + n_r + n_e
    c = np.zeros(ncol)
    soft_hi: dict[str, float | None] = {}
    for g, rows_g in groups.items():
        # a Diff group's slack is a GRADE (metres per metre of chord); a
        # Linear group's slack is METRES — both charged per metre of relief
        scale = sum(d.d for d in rows_g if isinstance(d, Diff)) + \
            sum(1.0 for d in rows_g if isinstance(d, Linear))
        tier = weights.preference.get(g.split(":", 1)[0], PREFERENCE_WEIGHT)
        c[soft_cols[g]] = tier * max(wv.max(), 1.0) * scale
        lims = [(d.ceiling - d.cap) if isinstance(d, Diff) else d.ceiling
                for d in rows_g]
        soft_hi[g] = None if any(l is None for l in lims) else max(0.0, min(lims))
    t_col = {}
    k = n
    for i in range(n):
        if has_dem[i]:
            t_col[i] = k
            c[k] = wv[i]
            k += 1
    for j in range(n_r):
        c[n + n_t + j] = lam
    # extra inequality rows: |z - dem| <= t ; |second diff| <= r
    r_: list[int] = []
    c_: list[int] = []
    v_: list[float] = []
    b_: list[float] = []
    row = 0
    for i, tc in t_col.items():
        r_ += [row, row, row + 1, row + 1]
        c_ += [i, tc, i, tc]
        v_ += [1.0, -1.0, -1.0, -1.0]
        b_ += [dem[i], -dem[i]]
        row += 2
    for j, (a, m, cc, dp, dn) in enumerate(stations):
        rc = n + n_t + j
        terms = ((cc, 1.0 / dn), (m, -(1.0 / dn + 1.0 / dp)), (a, 1.0 / dp))
        scale = 0.5 * (dp + dn)          # metres of Δgrade·span: comparable to t
        for sgn in (1.0, -1.0):
            for v, coef in terms:
                r_.append(row)
                c_.append(v)
                v_.append(sgn * coef * scale)
            r_.append(row)
            c_.append(rc)
            v_.append(-1.0)
            b_.append(0.0)
            row += 1
    soft_rows: list[Row] = []
    for d in S.soft:
        col = soft_cols[d.soft]
        if isinstance(d, Diff):
            for sa, sb in ((d.a, d.b), (d.b, d.a)):
                r_ += [row, row, row]
                c_ += [sa, sb, col]
                v_ += [1.0, -1.0, -d.d]
                b_.append(d.cap * d.d)
                soft_rows.append(d)
                row += 1
            continue
        for sgn, bound in ((1.0, d.hi), (-1.0, None if d.lo is None else -d.lo)):
            if bound is None:
                continue
            for v, coef in d.terms:
                r_.append(row)
                c_.append(v)
                v_.append(sgn * coef)
            r_.append(row)
            c_.append(col)
            v_.append(-1.0)
            b_.append(bound)
            soft_rows.append(d)
            row += 1
    A_obj = sp.csr_matrix((v_, (r_, c_)), shape=(row, ncol))
    A_ub_cs = sp.hstack([S.A_ub, sp.csr_matrix((S.A_ub.shape[0], ncol - n))],
                        format="csr")
    A_eq = sp.hstack([S.A_eq, sp.csr_matrix((S.A_eq.shape[0], ncol - n))],
                     format="csr")
    A_ub = sp.vstack([A_ub_cs, A_obj], format="csr")
    b_ub = np.concatenate([S.b_ub, np.asarray(b_, float)])
    bounds: list[tuple[float | None, float | None]] = []
    for i in range(n):
        lo = None if not np.isfinite(S.lo[i]) else float(S.lo[i])
        hi = None if not np.isfinite(S.hi[i]) else float(S.hi[i])
        bounds.append((lo, hi))
    bounds += [(0.0, None)] * (n_t + n_r)
    bounds += [(0.0, soft_hi[g]) for g in sorted(groups)]
    ub_rows = tuple(S.ub_rows) + (None,) * (row - len(soft_rows)) + tuple(soft_rows)
    return Problem(n, c, A_ub, b_ub, A_eq, S.b_eq, bounds, ub_rows,
                   tuple(S.eq_rows), S, soft_cols)
