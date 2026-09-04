"""THE LAST RESORT — the IIS-scoped, LEAST-TOTAL-VARIANCE relaxation
(RULINGS 2026-09-04t(1), answering 04s: HECA's hangar row).

    "Where the hard set is infeasible at a site, the solver may relax ALL
    THREE populations together — a slightly over-cap apron, a slightly
    sloping pad contact, a slightly over-cap slope between buildings
    (never a cliff/terrace) — choosing the combination that minimises the
    TOTAL variance from law (a quadratic spread across the IIS rows, not
    L1's concentration on one row), and only for the rows an IIS names.
    No terrace minting."

The hard solve comes first (``tiers.solve_law_ordered``).  Only on
infeasibility, and inside ``emit.relaxation.iis_time_budget_s``:

1. **THE IIS** (``iis.diagnose``) names the contradiction's rows and
   thereby THE SITE: the junior faces (``relaxable_from_role``'s tier or
   below, and the rigid pads) its vertices touch.
2. **THE CANDIDATES** are the site's rows the ruling admits: every hard
   ``Diff`` / ``Linear`` OWNED (``tiers.row_tier``) by a junior tier with
   a vertex on the site — an apron chord, a frontage row, a no-step pair
   whose junior endpoint is the apron's — and every rigid face's ``Flat``
   group on it (a pad).  The IIS's own rows are always among them.  A
   row is owned by the tier of the LAW it states (``_law_tier``): an
   apron-cap row on a junction's edge along the apron (04t-2) is an
   apron row.  A pin, a runway or taxi-family row is never relaxed: an
   IIS naming only those falls back to the tier machinery (04i), and the
   report says so.  The route-REACH bands are set aside for the whole
   last resort (``envelope_free``): they are the envelope the hard path
   rows imply (tiers.py withdraws them on demotion for the same reason),
   and an IIS naming the envelope names nothing the ruling can relax —
   the diagnosis, the spread and the re-solve all run on the rows.
   Why the SITE and not the one IIS: an apron is a
   membrane — the parallel chords beside an IIS path are IISs of their
   own (measured on the hangar-row twin: three rounds of one-IIS-at-a-
   time never closed), and the variance program below gives a row that
   is in NO IIS exactly zero slack (relaxing it buys nothing, costs
   something), so its support IS "the rows an IIS names".
3. **STAGE 1 — the variance program.**  Every candidate ``Diff`` gets a
   GRADE excess ``g ≥ 0`` (``|z_a − z_b| ≤ (cap + g)·d``); a ``Linear`` a
   metre slack ``s`` on each finite side; a pad becomes ONE PLANE ``z_i =
   z_c + u·dx_i + v·dy_i`` over its vertices (``(u, v)`` its slope: its
   contact may slope, its interior stays one plane, no step can form —
   its rim vertices ARE the apron's own).  Objective ``min Σ d·g² + Σ s²
   + Σ D·(u² + v²)`` — the squared excess over the law INTEGRATED along
   the pavement (``d`` the chord, ``D`` the pad's extent): its optimum is
   the UNIFORM over-cap along the whole site, the spread the ruling asks
   for (a plain ``Σ g²`` would load the long chords, ``Σ metres²`` the
   short edges).  Pure variance, no DEM term: the combination is a
   property of the law rows alone.  Backend: ``highspy``'s QP under
   ``Options.time_limit_s`` when the wheel is present — measured: exact
   at twin scale, and at HECA's 1.8 M rows it did not finish in five
   minutes — else, and past the limit, a CONVEX PIECEWISE-LINEAR
   approximation of the square (``max_pieces`` pieces from the grade /
   elevation materiality doubling; stated as an approximation in the
   report) on scipy's HiGHS LP, presolve on (HECA: ~30 s).
4. **STAGE 2 — the normal solve with the relief FIXED.**  The optimal
   excesses become the rows' new bounds (``cap + g``; a pad's plane as
   equalities at the solved slope) and ``highs.solve`` runs the usual L1
   DEM preference over the whole map — so ``why`` can read the relaxed
   set's duals like any feasible airport's.  A WARM START of this LP is
   REFUTED (m5j, HECA 1.35 M rows, single runs): from stage 1's own point
   364 s (cold 62 s); from the optimum of the set with the relaxed rows
   dropped 54 s after that solve's own 57 s; the plain feasible LP at this
   size is the cost, not the relaxation.
5. **THE CERTIFICATE**: every relaxed pad's plane residual and every
   step between adjacent relaxed elements ≤ ``materiality_m``.

A second contradiction outside the site is a second ROUND (its IIS
widens the site), up to ``max_rounds``; past the budget or the rounds
the tier machinery answers.  This module imports ``law``, ``model`` and
its siblings only (04q-3).
"""
from __future__ import annotations

import dataclasses as _dc
import math
import time
import typing as _t

import numpy as np
import scipy.sparse as sp
from scipy.optimize import linprog

from ..law import Law
from ..law.tables import is_rigid_role, role_tier, tiers
from ..model.constraints import (REACH_GENERATOR, Band, ConstraintSet, Diff, Flat, Linear, Pin, Row,
                                 Source)
from ..model.planar import PlanarMap
from .api import Options, Solution, Status, Weights
from .assemble import to_sparse
from .highs import solve as solve_hard
from .iis import (Certificate, IISBudgetExceeded, RowIndex, diagnose, neighbourhood_certificate,
                  row_vertices)
from .tiers import row_tier

__all__ = ["RULING", "Relaxed", "RelaxReport", "relaxable", "site_candidates", "stage1",
           "relaxed_hard_set", "certificate", "solve_relaxed", "qp_available"]

#: The ruling every relaxed row cites (the census heading).
RULING = "relaxed by 04t(1)"
#: Generator name of a relaxed pad's plane rows.
PLANE_GENERATOR = "pads"


def qp_available() -> bool:
    """Is the ``highspy`` QP backend importable?"""
    try:
        import highspy  # noqa: F401
    except ImportError:
        return False
    return True


@_dc.dataclass(frozen=True)
class Relaxed:
    """One IIS row admitted to the relaxation."""

    index: int
    row: Row
    kind: str                 # "diff" | "linear" | "pad"
    tier: int
    face: int | None = None   # the pad's face id
    extent_m: float = 0.0     # a pad's D; a Diff's d
    #: a pad's vertex offsets from its centroid, ``(v, dx, dy)``
    offsets: tuple[tuple[int, float, float], ...] = ()


def _face_of(row: Row) -> int | None:
    for inp in row.source.inputs:
        if inp.startswith("face:"):
            try:
                return int(inp[5:])
            except ValueError:
                return None
    return None


def relaxable(pm: PlanarMap, law: Law, iis: _t.Sequence[Row]) -> list[Relaxed]:
    """The IIS rows the ruling admits (module docstring, step 2)."""
    tt = tiers(law)
    tier_of = {r: k for k, t in enumerate(tt) for r in t}
    lowest = len(tt) - 1
    k_from = role_tier(law, law.tables.emit.relaxation.relaxable_from_role)
    out: list[Relaxed] = []
    for r in iis:
        if isinstance(r, Flat):
            fid = _face_of(r)
            role = pm.faces[fid].role if fid is not None and fid in pm.faces else None
            if role is None or not is_rigid_role(law, role):
                continue
            xs = np.array([pm.vertices[v].xy for v in r.group], float)
            c = xs.mean(axis=0)
            off = xs - c
            radius = float(np.hypot(off[:, 0], off[:, 1]).max())
            if radius <= 0.0:
                continue
            out.append(Relaxed(len(out), r, "pad", tier_of.get(role, lowest), fid,
                               2.0 * radius,
                               tuple((int(v), float(dx), float(dy))
                                     for v, (dx, dy) in zip(r.group, off))))
            continue
        if isinstance(r, Diff) and r.soft is None:
            k = _law_tier(pm, r, tier_of, lowest)
            if k >= k_from:
                out.append(Relaxed(len(out), r, "diff", k, _face_of(r), r.d))
        elif isinstance(r, Linear) and r.soft is None and not (
                r.lo is not None and r.hi is not None and r.lo == r.hi
                and len(r.terms) == 1):
            k = row_tier(pm, r, tier_of, lowest)
            if k >= k_from:
                out.append(Relaxed(len(out), r, "linear", k, _face_of(r), 1.0))
    return out


def _law_tier(pm: PlanarMap, r: Row, tier_of: _t.Mapping[str, int], lowest: int) -> int:
    """The tier of the LAW a row states, never only of the face it sits
    on: a row the APRON law mints on a junction face (04t-2, the apron
    cap on the portion along the apron; ``apron.apron_edge_portions``) is
    an apron row — "a slightly over-cap apron" is exactly what 04t(1)
    admits — and reads the apron's tier.  Measured HECA 2026-09-05: the
    23C→05L reach floor rose 3.3 m under 04t-2's 1 % on 2.5 km of junction
    pav132's apron edge, the hard set went infeasible against the 05L pin,
    and the portion rows (taxi-tier by face) were refused as relaxable."""
    k = row_tier(pm, r, tier_of, lowest)
    law_k = tier_of.get(r.source.generator)
    return k if law_k is None else max(k, law_k)


def envelope_free(cs: ConstraintSet) -> ConstraintSet:
    """``cs`` without the route-reach bands (``REACH_GENERATOR``): the
    thresholds' envelope the hard path rows already imply (tiers.py, the
    demotion withdraws them for the same reason).  The last resort
    diagnoses, spreads and re-solves on the ROWS — an IIS naming the
    envelope instead of the path rows it summarises names nothing the
    ruling can relax (HECA 2026-09-05: 'Band:reach' x3 + one runway
    crown row, relaxation refused, the tier machinery demoted the apron
    tier: +8 airside rows)."""
    return ConstraintSet.from_rows(
        r for r in cs.rows()
        if not (isinstance(r, Band) and r.source.generator == REACH_GENERATOR))


def site_candidates(pm: PlanarMap, law: Law, cs: ConstraintSet, iis: _t.Sequence[Row],
                    prior: _t.Sequence[Relaxed] = ()) -> list[Relaxed]:
    """The site's candidate rows (module docstring, steps 1–2): the
    junior faces the IIS's vertices touch, every junior ``Diff`` /
    ``Linear`` with a vertex on them, every rigid pad on them; the IIS's
    own relaxable rows always; ``prior`` candidates kept (indices
    continue)."""
    tt = tiers(law)
    tier_of = {r: k for k, t in enumerate(tt) for r in t}
    lowest = len(tt) - 1
    k_from = role_tier(law, law.tables.emit.relaxation.relaxable_from_role)

    def verts(r: Row) -> tuple[int, ...]:
        if isinstance(r, Pin):
            return (r.v,)
        if isinstance(r, Diff):
            return (r.a, r.b)
        if isinstance(r, Flat):
            return r.group
        if isinstance(r, Linear):
            return tuple(v for v, _c in r.terms)
        return (r.v,)

    faces: set[int] = set()
    for r in iis:
        for v in verts(r):
            for fid in pm.vertices[v].incident_faces:
                role = pm.faces[fid].role
                if is_rigid_role(law, role) or tier_of.get(role, lowest) >= k_from:
                    faces.add(fid)
        fid = _face_of(r)
        if fid is not None and fid in pm.faces:
            faces.add(fid)
    site: set[int] = set()
    for fid in faces:
        f = pm.faces[fid]
        site.update(pm.ring_vertices(f.ring))
        for h in f.holes:
            site.update(pm.ring_vertices(h))
    seen = {id(x.row) for x in prior}
    rows: list[Row] = []
    for r in iis:
        if id(r) not in seen:
            seen.add(id(r))
            rows.append(r)
    for r in (*cs.flats, *cs.diffs, *cs.linears):
        if id(r) in seen:
            continue
        if isinstance(r, Flat):
            if _face_of(r) in faces:
                seen.add(id(r))
                rows.append(r)
            continue
        if any(v in site for v in verts(r)):
            seen.add(id(r))
            rows.append(r)
    new = relaxable(pm, law, rows)
    base = len(prior)
    return list(prior) + [_dc.replace(x, index=base + i) for i, x in enumerate(new)]


def _without(cs: ConstraintSet, relaxed: _t.Sequence[Relaxed]) -> ConstraintSet:
    drop = {id(x.row) for x in relaxed}
    return ConstraintSet.from_rows(r for r in cs.rows() if id(r) not in drop)


# ── stage 1: the variance program ────────────────────────────────────────

@_dc.dataclass
class _Model:
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
    col_of: dict[int, tuple[int, ...]]   # Relaxed.index -> its columns
    #: the square's weight per quad column (``d`` for a Diff's grade, 1 for
    #: a Linear's metres, ``D`` for a pad's slope components)
    weight: dict[int, float] = _dc.field(default_factory=dict)
    #: quad columns charged in GRADE units (pieces from the grade materiality)
    grade_cols: set[int] = _dc.field(default_factory=set)


#: Directions of the polygonal bound on a relaxed pad's gradient
#: (``_model``): a regular polygon INSCRIBED in the ``pad_slope_max`` disc,
#: so the true gradient never exceeds the table value in any direction.
SLOPE_DIRECTIONS = 32


def _model(pm: PlanarMap, cs: ConstraintSet, relaxed: _t.Sequence[Relaxed],
           pad_slope_max: float | None = None) -> _Model:
    """``pad_slope_max`` (RULINGS 2026-09-05f, ``[relaxation]``): every
    relaxed pad's plane ``(u, v)`` is bounded to the disc of that radius
    (``SLOPE_DIRECTIONS`` half-planes ``u·cosθ + v·sinθ ≤ s·cos(π/K)``,
    whose polygon lies INSIDE the disc: |u|, |v| ≤ s among them), so the
    variance program spreads the relief a steeper pad would have taken
    over the other populations (04t-1)."""
    n = len(pm.vertices)
    S = to_sparse(_without(cs, relaxed), n)
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
    return _Model(n, ncol, A_ub, np.concatenate([S.b_ub, np.asarray(ub_b, float)]),
                  A_eq, np.concatenate([S.b_eq, np.asarray(eq_b, float)]),
                  lo, hi, quad, col_of, weight, grade_cols)


def _qp(m: _Model, time_limit_s: float | None) -> tuple[str, np.ndarray | None, float]:
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
    lp.col_cost_ = np.zeros(m.ncol)
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


def _pieces(materiality_m: float, k: int) -> list[tuple[float, float]]:
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


def _pwl(m: _Model, grade_pieces: list[tuple[float, float]],
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


@_dc.dataclass
class Stage1:
    status: str
    backend: str                       # "qp" | "pwl"
    wall_s: float
    #: Relaxed.index -> the EXCESS the square charged: a Diff's grade
    #: excess ``g``, a pad's slope ``√(u²+v²)``, a Linear's metres
    excess: dict[int, float]
    #: Relaxed.index -> metres of relief (``g·d``, a pad's rise over its
    #: extent, a Linear's metres)
    slack: dict[int, float]
    #: a pad's solved plane ``(zc, u, v)``
    planes: dict[int, tuple[float, float, float]]
    #: how the backend was chosen (a QP that hit its limit says so)
    note: str = ""


def stage1(pm: PlanarMap, cs: ConstraintSet, relaxed: _t.Sequence[Relaxed], law: Law,
           options: Options | None = None, backend: str | None = None,
           qp_time_limit_s: float | None = None) -> Stage1:
    """The variance program (module docstring, step 3).  ``backend``
    forces ``"qp"`` / ``"pwl"``; by default the QP runs under
    ``qp_time_limit_s`` and the approximation takes over past it."""
    opt = options or Options()
    rl = law.tables.emit.relaxation
    m = _model(pm, cs, relaxed, rl.pad_slope_max)
    be = backend or ("qp" if qp_available() else "pwl")
    note = ""
    st, x, wall = "", None, 0.0
    nrows = m.A_ub.shape[0] + m.A_eq.shape[0]
    if be == "qp" and backend is None and nrows > rl.qp_max_rows:
        # THE SIZE GATE (RULINGS 2026-09-04x(1)): past ``qp_max_rows`` the
        # QP budget is pure waste — straight to the approximation
        note = (f"QP skipped: {nrows} rows > [relaxation] qp_max_rows {rl.qp_max_rows}; "
                f"the piecewise-linear approximation answers")
        be = "pwl"
    if be == "qp":
        lim = opt.time_limit_s if backend == "qp" else qp_time_limit_s
        st, x, wall = _qp(m, lim)
        if st in ("time_limit",) or st.startswith("error"):
            if backend == "qp":
                return Stage1(st, be, wall, {}, {}, {}, "forced QP did not finish")
            note = f"QP {st} after {wall:.1f} s; the piecewise-linear approximation answers"
            be = "pwl"
    if be == "pwl":
        st2, x, wall2 = _pwl(m, _pieces(law.tables.emit.materiality.grade, rl.max_pieces),
                             _pieces(rl.materiality_m, rl.max_pieces), opt.time_limit_s)
        st, wall = st2, wall + wall2
    if x is None:
        return Stage1(st, be, wall, {}, {}, {}, note)
    excess: dict[int, float] = {}
    slack: dict[int, float] = {}
    planes: dict[int, tuple[float, float, float]] = {}
    for r in relaxed:
        cols = m.col_of[r.index]
        if r.kind == "pad":
            zc, u, v = (float(x[c]) for c in cols)
            planes[r.index] = (zc, u, v)
            excess[r.index] = math.hypot(u, v)
            slack[r.index] = excess[r.index] * r.extent_m
        elif r.kind == "diff":
            excess[r.index] = max(0.0, float(x[cols[0]]))
            slack[r.index] = excess[r.index] * r.row.d
        else:
            excess[r.index] = slack[r.index] = max(0.0, float(x[cols[0]]))
    return Stage1(st, be, wall, excess, slack, planes, note)


# ── stage 2: the relaxed HARD set ────────────────────────────────────────

def relaxed_hard_set(cs: ConstraintSet, relaxed: _t.Sequence[Relaxed], s1: Stage1,
                     tol: float = 1e-9) -> tuple[ConstraintSet, dict[int, Row | tuple[Row, ...]]]:
    """Every relaxed row at its solved relief: a ``Diff`` at ``cap + s/d``,
    a ``Linear`` at ``hi + s`` / ``lo − s``, a pad as plane equalities at
    the solved gradient (a pad whose rise is below ``tol`` stays a
    ``Flat``); returns the set and ``index -> replacement``."""
    repl: dict[int, Row | tuple[Row, ...]] = {}
    by_id: dict[int, Relaxed] = {id(x.row): x for x in relaxed}
    out: list[Row] = []
    for r in cs.rows():
        x = by_id.get(id(r))
        if x is None:
            out.append(r)
            continue
        s = s1.slack.get(x.index, 0.0)
        src = Source(r.source.generator, f"{r.source.ruling}; {RULING}", r.source.inputs)
        if s <= tol:
            out.append(r)
            repl[x.index] = r
            continue
        if x.kind == "diff":
            nr: Row = _dc.replace(r, cap=r.cap + s1.excess[x.index], source=src)
            out.append(nr)
            repl[x.index] = nr
        elif x.kind == "linear":
            nr = _dc.replace(r, hi=None if r.hi is None else r.hi + s,
                             lo=None if r.lo is None else r.lo - s, source=src)
            out.append(nr)
            repl[x.index] = nr
        else:
            _zc, gx, gy = s1.planes[x.index]
            v0, dx0, dy0 = x.offsets[0]
            rows: list[Row] = []
            for vid, dx, dy in x.offsets[1:]:
                rise = gx * (dx - dx0) + gy * (dy - dy0)
                rows.append(Linear(((vid, 1.0), (v0, -1.0)), rise, rise, src))
            out.extend(rows)
            repl[x.index] = tuple(rows)
    return ConstraintSet.from_rows(out), repl


# ── the certificate ──────────────────────────────────────────────────────

def certificate(pm: PlanarMap, relaxed: _t.Sequence[Relaxed], s1: Stage1,
                z: _t.Sequence[float], materiality_m: float,
                pad_slope_max: float | None = None, grade_tol: float = 0.0
                ) -> dict[str, _t.Any]:
    """Every relaxed pad is ONE plane at ``z`` (residual ≤ materiality)
    no steeper than ``pad_slope_max`` (05f, within the grade materiality);
    adjacent relaxed elements share vertices, so their step is zero by
    identity — reported as the largest |Δz| between a relaxed pad's rim
    vertex and the same vertex read through any relaxed chord (always
    0.0: one variable) and the worst plane residual."""
    worst_plane = 0.0
    worst_slope = 0.0
    for x in relaxed:
        if x.kind != "pad" or x.index not in s1.planes:
            continue
        _zc, gx, gy = s1.planes[x.index]
        vals = [z[vid] - gx * dx - gy * dy for vid, dx, dy in x.offsets]
        worst_plane = max(worst_plane, max(vals) - min(vals))
        worst_slope = max(worst_slope, math.hypot(gx, gy))
    slope_ok = pad_slope_max is None or worst_slope <= pad_slope_max + grade_tol
    over: list[float] = []
    for x in relaxed:
        if x.kind == "diff":
            r = x.row
            over.append(abs(z[r.a] - z[r.b]) - r.cap * r.d)
    ok = worst_plane <= materiality_m and slope_ok and all(
        o <= s1.slack.get(x.index, 0.0) + materiality_m
        for o, x in zip(over, [x for x in relaxed if x.kind == "diff"]))
    return {"plane_residual_max_m": round(worst_plane, 6),
            "pad_slope_max_seen": round(worst_slope, 7), "pad_slope_max": pad_slope_max,
            "shared_vertex_step_m": 0.0, "materiality_m": materiality_m, "ok": bool(ok)}


# ── the whole last resort ────────────────────────────────────────────────

@_dc.dataclass
class RelaxReport:
    """What the last resort did (``TierReport.relaxation``)."""

    applied: bool
    reason: str = ""
    backend: str = ""
    approximation: bool = False
    rounds: int = 0
    iis_rows: int = 0
    iis_wall_s: float = 0.0
    stage1_wall_s: float = 0.0
    stage2_wall_s: float = 0.0
    #: the site's candidate rows (every junior row on the IIS's faces)
    candidates: int = 0
    note: str = ""
    #: how each round's certificate was found: the cached with-envelope
    #: ray's wall and support, the neighbourhood LPs (hops / rows / wall),
    #: or ``whole_model`` (the fallback)
    certificates: list[dict[str, _t.Any]] = _dc.field(default_factory=list)
    #: the SUPPORT: candidates that took an excess (the rows relaxed)
    rows: list[dict[str, _t.Any]] = _dc.field(default_factory=list)
    unrelaxed: list[dict[str, _t.Any]] = _dc.field(default_factory=list)
    #: spread of the EXCESS (grade for chords / pads) over the support
    stats: dict[str, float] = _dc.field(default_factory=dict)
    #: spread of the relief in metres over the support
    stats_m: dict[str, float] = _dc.field(default_factory=dict)
    certificate: dict[str, _t.Any] = _dc.field(default_factory=dict)

    def as_dict(self) -> dict[str, _t.Any]:
        d = _dc.asdict(self)
        d["ruling"] = RULING
        return d

    def line(self) -> str:
        if not self.applied:
            return f"relaxation (04t-1) not applied: {self.reason}"
        s, sm = self.stats, self.stats_m
        return (f"relaxation (04t-1) applied: IIS {self.iis_rows} rows in {self.iis_wall_s:.1f} s, "
                f"site {self.candidates} candidates, {len(self.rows)} relaxed "
                f"({self.backend}{' approx' if self.approximation else ''}, {self.rounds} round(s)"
                f"{'; ' + self.note if self.note else ''}); excess grade mean {s.get('mean', 0):.5f} "
                f"max {s.get('max', 0):.5f} sd {s.get('sd', 0):.5f} max/mean {s.get('max_over_mean', 0):.2f}; "
                f"relief Σ {sm.get('sum', 0):.3f} m max {sm.get('max', 0):.3f} m; "
                f"stage1 {self.stage1_wall_s:.1f} s stage2 {self.stage2_wall_s:.1f} s; "
                f"certificate {'OK' if self.certificate.get('ok') else 'FAILED'}")


def _row_record(pm: PlanarMap, x: Relaxed, s1: Stage1) -> dict[str, _t.Any]:
    r = x.row
    slack = s1.slack.get(x.index, 0.0)
    excess = s1.excess.get(x.index, 0.0)
    if x.kind == "pad":
        verts = [vid for vid, _dx, _dy in x.offsets]
        return {"index": x.index, "kind": "pad", "family": r.source.generator,
                "ruling": r.source.ruling, "inputs": list(r.source.inputs), "face": x.face,
                "tier": x.tier, "slack_m": round(slack, 6), "excess": round(excess, 7),
                "slope": round(excess, 7), "extent_m": round(x.extent_m, 3),
                "vertices": verts, "ll": [list(pm.vertices[v].key) for v in verts]}
    if x.kind == "diff":
        verts = [r.a, r.b]
        rec = {"cap": r.cap, "distance_m": round(r.d, 3), "cap_after": round(r.cap + excess, 7)}
    else:
        verts = [v for v, _c in r.terms]
        rec = {"lo": r.lo, "hi": r.hi}
    rec.update({"index": x.index, "kind": x.kind, "family": r.source.generator,
                "ruling": r.source.ruling, "inputs": list(r.source.inputs), "face": x.face,
                "tier": x.tier, "slack_m": round(slack, 6), "excess": round(excess, 7),
                "vertices": verts, "ll": [list(pm.vertices[v].key) for v in verts]})
    return rec


def _stats(slacks: _t.Sequence[float]) -> dict[str, float]:
    a = np.asarray(slacks, float)
    if a.size == 0:
        return {}
    mean = float(a.mean())
    return {"n": int(a.size), "sum": round(float(a.sum()), 7), "mean": round(mean, 7),
            "max": round(float(a.max()), 7), "min": round(float(a.min()), 7),
            "sd": round(float(a.std()), 7), "variance": round(float(a.var()), 10),
            "sum_sq": round(float((a * a).sum()), 10),
            "max_over_mean": round(float(a.max() / mean), 4) if mean > 0 else 0.0}


def solve_relaxed(pm: PlanarMap, cs: ConstraintSet, law: Law, weights: Weights,
                  options: Options | None = None, *, size_out: dict | None = None,
                  backend: str | None = None
                  ) -> tuple[Solution | None, RelaxReport, ConstraintSet | None]:
    """The last resort on an INFEASIBLE hard set: (solution, report, the
    relaxed hard set) — ``solution`` is ``None`` when the tier machinery
    must answer instead (``report.reason``)."""
    opt = options or Options()
    rl = law.tables.emit.relaxation
    t_start = time.perf_counter()
    deadline = t_start + rl.iis_time_budget_s
    rep = RelaxReport(False)
    quiet = _dc.replace(opt, diagnose_iis=False)
    relaxed_all: list[Relaxed] = []
    unrelaxed: list[Row] = []
    n = len(pm.vertices)
    # THE CACHED CERTIFICATE (iis.py module docstring): the WITH-envelope
    # model, built once, names the site in seconds; each round frees the
    # rows it relaxed and hot-starts the next ray
    cached: Certificate | None = None
    seed: set[int] = set()
    try:
        t = time.perf_counter()
        cached = Certificate(n, cs.rows())
        sup = cached.ray(max(1.0, deadline - time.perf_counter()))
        rep.iis_wall_s += time.perf_counter() - t
        seed = {v for r in (sup or ()) for v in row_vertices(r)}
        rep.certificates.append({"round": 0, "kind": "cached_envelope", "support": len(sup or ()),
                                 "seed_vertices": len(seed), "rows": cached.rows,
                                 "wall_s": round(time.perf_counter() - t, 3)})
    except ImportError:
        cached = None
    except IISBudgetExceeded:
        cached = None                   # the whole-model path answers below
    cs = envelope_free(cs)          # the rows, never their reach envelope
    index = RowIndex(cs.rows())
    excluded: set[int] = set()
    probe = cs
    for rnd in range(1, rl.max_rounds + 1):
        rep.rounds = rnd
        t = time.perf_counter()
        rows: list[Row] = []
        try:
            trace: dict = {}
            if seed:
                sup = neighbourhood_certificate(n, index, seed, deadline=deadline,
                                                exclude=excluded, trace=trace)
                if sup:
                    rows = list(sup)
                    rep.certificates.append({"round": rnd, "kind": "neighbourhood", **trace,
                                             "support": len(rows)})
            if not rows:
                rows = [r for r, _s in diagnose(pm, probe, weights, opt, deadline=deadline,
                                                minimal=False)]
                rep.certificates.append({"round": rnd, "kind": "whole_model", **trace,
                                         "support": len(rows)})
        except IISBudgetExceeded as e:
            rep.iis_wall_s += time.perf_counter() - t
            rep.reason = (f"IIS not found inside the {rl.iis_time_budget_s:.0f} s budget "
                          f"(round {rnd}: {e}); the tier machinery (04i) answers")
            return None, rep, None
        rep.iis_wall_s += time.perf_counter() - t
        rep.iis_rows += len(rows)
        if not rows:
            rep.reason = (f"round {rnd}: no IIS found on the set with the relaxed rows "
                          f"dropped, yet the relaxed program is infeasible (a pad's plane "
                          f"cannot absorb its contradiction); the tier machinery answers")
            return None, rep, None
        cand = site_candidates(pm, law, cs, rows, relaxed_all)
        new = cand[len(relaxed_all):]
        unrelaxed += [r for r in rows if id(r) not in {id(x.row) for x in cand}]
        if not new:
            rep.unrelaxed = [{"kind": type(r).__name__, "family": r.source.generator,
                              "ruling": r.source.ruling, "inputs": list(r.source.inputs)}
                             for r in rows]
            rep.reason = (f"the IIS ({len(rows)} rows) names no relaxable row — "
                          f"{sorted({type(r).__name__ + ':' + r.source.generator for r in rows})}; "
                          f"the tier machinery (04i) answers")
            return None, rep, None
        relaxed_all = cand
        rep.candidates = len(relaxed_all)
        t = time.perf_counter()
        s1 = stage1(pm, cs, relaxed_all, law, opt, backend,
                    qp_time_limit_s=min(rl.qp_time_budget_s,
                                        max(1.0, deadline - time.perf_counter())))
        rep.stage1_wall_s += time.perf_counter() - t
        rep.backend = s1.backend
        rep.approximation = s1.backend == "pwl"
        rep.note = s1.note
        if s1.status == "infeasible":
            # another site: the next certificate on the rest — the cached
            # model freed of this round's rows (hot start) re-seeds it
            probe = _without(cs, relaxed_all)
            excluded |= {id(x.row) for x in new}
            seed |= {v for x in new for v in row_vertices(x.row)}
            if cached is not None:
                t = time.perf_counter()
                cached.free(x.row for x in new)
                try:
                    sup = cached.ray(max(1.0, deadline - time.perf_counter()))
                except IISBudgetExceeded:
                    sup = None
                rep.iis_wall_s += time.perf_counter() - t
                seed |= {v for r in (sup or ()) for v in row_vertices(r)}
                rep.certificates.append({"round": rnd, "kind": "cached_envelope_reseed",
                                         "support": len(sup or ()), "seed_vertices": len(seed),
                                         "wall_s": round(time.perf_counter() - t, 3)})
            continue
        if s1.status != "optimal":
            rep.reason = f"stage 1 ({s1.backend}) ended {s1.status}; the tier machinery answers"
            return None, rep, None
        cs2, _repl = relaxed_hard_set(cs, relaxed_all, s1)
        t = time.perf_counter()
        sol = solve_hard(pm, cs2, weights, quiet, size_out=size_out)
        rep.stage2_wall_s += time.perf_counter() - t
        if sol.status not in (Status.OPTIMAL, Status.FEASIBLE):
            rep.reason = (f"stage 2 ended {sol.status.value} on the relaxed set "
                          f"({sol.message[:120]}); the tier machinery answers")
            return None, rep, None
        rep.applied = True
        tol_g = law.tables.emit.materiality.grade
        # the SUPPORT: an excess below the materiality floor is a residual,
        # never a relaxed row (owner 2026-08-02 convergence guards)
        support = [x for x in relaxed_all
                   if s1.excess.get(x.index, 0.0) >= (tol_g if x.kind != "linear" else rl.materiality_m)]
        rep.rows = [_row_record(pm, x, s1) for x in support]
        rep.unrelaxed = [{"kind": type(r).__name__, "family": r.source.generator,
                          "ruling": r.source.ruling, "inputs": list(r.source.inputs)}
                         for r in unrelaxed]
        rep.stats = _stats([s1.excess[x.index] for x in support if x.kind != "linear"])
        rep.stats_m = _stats([s1.slack[x.index] for x in support])
        rep.certificate = certificate(pm, support, s1, sol.z, rl.materiality_m,
                                      rl.pad_slope_max, tol_g)
        return sol, rep, cs2
    rep.reason = f"{rl.max_rounds} rounds spent without a feasible relaxed set; the tier machinery answers"
    return None, rep, None
