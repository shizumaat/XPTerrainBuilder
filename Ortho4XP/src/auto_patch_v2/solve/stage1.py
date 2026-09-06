"""STAGE 1 OF THE LAST RESORT — the ruled order (RULINGS 2026-09-06l; the
program itself: ``solve/variance.py``; the whole last resort and its
report: ``solve/relax.py``, whose module docstring step 3 states the law).
Split out of ``relax.py`` (lane v2bow3, the 1,000-line law) verbatim:

* :func:`stage1a` — the RUNWAY family's L1 departure from its DEM fit,
  minimised over the un-relaxed rows and every candidate inside
  ``max_over_cap_factor`` (``variance.lp``): the senior family's hard-
  feasible best;
* :func:`stage1b` — the variance program with the runway family HELD
  within ``[relaxation] runway_hold_tolerance_m`` of stage 1a
  (``variance.held``); with no hold, 04t(1) alone (a twin's control);
* :func:`stage1` — the dispatch: lexicographic by default, the 06h
  weighted single stage at a positive ``runway_fit_weight``.

Imports ``law``, ``model`` and its siblings only (04q-3).
"""
from __future__ import annotations

import dataclasses as _dc
import math
import typing as _t

import numpy as np

from ..law import Law
from ..model.constraints import ConstraintSet
from ..model.planar import PlanarMap
from .api import Options, Weights
from .assemble import roughness_stations, vertex_weights
from .variance import held, lp, model, pieces, pwl, qp, qp_available

if _t.TYPE_CHECKING:
    from .relax import Relaxed

__all__ = ["ORDER_LEXICOGRAPHIC", "ORDER_WEIGHTED", "ORDER_VARIANCE", "STAGE1A_FIT_WEIGHT",
           "Stage1", "runway_fit", "runway_targets", "runway_departure", "stage1a", "stage1b",
           "stage1"]


# ── stage 1: the variance program (``solve/variance.py``) ───────────────

#: THE ORDER stage 1 answered in (``Stage1.order`` / ``RelaxReport.order``).
ORDER_LEXICOGRAPHIC = "lexicographic"   # 06l: 1a the runway's DEM fit, 1b the variance at that runway
ORDER_WEIGHTED = "weighted"             # 06h (b)/(c) at a positive [relaxation] runway_fit_weight
ORDER_VARIANCE = "variance"             # 04t(1) alone (the 06e program): a twin's control, never the default
#: The stage-1a fit weight: the runway family's L1 departure is a SINGLE
#: objective in 1a, so the ladder's runway weight is only a scale — every
#: runway vertex counts its metres once.
STAGE1A_FIT_WEIGHT = 1.0


@_dc.dataclass
class Stage1:
    status: str
    backend: str                       # "qp" | "pwl" (stage 1b's / the single stage's)
    wall_s: float                      # every stage-1 solve together
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
    #: the LINEAR part's size (06h b/c; 06l's stage 1a): fit + smoothness columns, rows
    linear_cols: int = 0
    linear_rows: int = 0
    #: RULINGS 2026-09-06l: which order answered, and each stage's wall
    order: str = ORDER_VARIANCE
    stage1a_wall_s: float = 0.0
    stage1b_wall_s: float = 0.0
    #: Σ|z − fit target| over the runway family: ``stage1a`` at its optimum
    #: (the runway's hard-feasible best inside the factor), ``stage1b`` at
    #: the variance program's point (inside ``runway_hold_tolerance_m`` × n)
    runway_departure_m: dict[str, float] = _dc.field(default_factory=dict)
    #: the runway family's stage-1a values (the hold stage 1b ran under)
    hold: dict[int, float] = _dc.field(default_factory=dict, repr=False)


def _runway_roles(law: Law) -> frozenset[str]:
    from ..law.tables import role_family
    return frozenset(r for r in law.tables.precedence.roles if role_family(law, r) == "runway")


def runway_fit(pm: PlanarMap, law: Law, weights: Weights
               ) -> dict[int, tuple[float, float]]:
    """THE RUNWAY FAMILY's DEM-fit term (RULINGS 2026-09-06h (b)): vertex
    -> ``(weight, target)`` for every vertex on a runway-family face
    with a DEM sample — the preference ladder's runway weight
    (``Weights.by_role``, the largest over its runway-family faces) and
    the fit target the solve itself uses (``planar.preferred_z`` else the
    DEM sample, as ``assemble`` reads it)."""
    wv = vertex_weights(pm, weights, _runway_roles(law))
    pref = pm.preferred_z
    out: dict[int, tuple[float, float]] = {}
    for vid in np.flatnonzero(wv > 0.0):
        v = pm.vertices[int(vid)]
        if v.dem_z is None:
            continue
        out[int(vid)] = (float(wv[vid]), float(pref.get(int(vid), v.dem_z)))
    return out


def runway_targets(pm: PlanarMap, law: Law) -> dict[int, float]:
    """The runway family's fit targets (RULINGS 2026-09-06l, stage 1a):
    vertex -> target for every vertex on a runway-family face with a DEM
    sample — the same population as :func:`runway_fit`, weightless (the
    departure is a single objective; the ladder's weight is a scale)."""
    roles = _runway_roles(law)
    pref = pm.preferred_z
    out: dict[int, float] = {}
    for vid, v in pm.vertices.items():
        if v.dem_z is None:
            continue
        if any(pm.faces[f].role in roles for f in v.incident_faces):
            out[int(vid)] = float(pref.get(int(vid), v.dem_z))
    return out


def runway_departure(z: _t.Sequence[float], targets: _t.Mapping[int, float]) -> float:
    """Σ|z − target| over the runway family (metres)."""
    return float(sum(abs(float(z[v]) - t) for v, t in targets.items()))


def _run_variance(m, law: Law, opt: Options, backend: str | None,
                  qp_time_limit_s: float | None) -> tuple[str, np.ndarray | None, float, str, str]:
    """The square's backends (module docstring, step 3): the QP under its
    size gate and budget, else the piecewise-linear approximation.
    Returns ``(status, x, wall, backend, note)``."""
    rl = law.tables.emit.relaxation
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
        st, x, wall = qp(m, lim)
        if st in ("time_limit",) or st.startswith("error"):
            if backend == "qp":
                return st, None, wall, be, "forced QP did not finish"
            note = f"QP {st} after {wall:.1f} s; the piecewise-linear approximation answers"
            be = "pwl"
    if be == "pwl":
        st2, x, wall2 = pwl(m, pieces(law.tables.emit.materiality.grade, rl.max_pieces),
                            pieces(rl.materiality_m, rl.max_pieces), opt.time_limit_s)
        st, wall = st2, wall + wall2
    return st, x, wall, be, note


def _read_relief(m, x: np.ndarray, relaxed: _t.Sequence[Relaxed]
                 ) -> tuple[dict[int, float], dict[int, float], dict[int, tuple[float, float, float]]]:
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
    return excess, slack, planes


def stage1a(pm: PlanarMap, cs: ConstraintSet, relaxed: _t.Sequence[Relaxed], law: Law,
            options: Options | None = None):
    """STAGE 1a (RULINGS 2026-09-06l): the RUNWAY family's L1 departure from
    its fit target, minimised over the un-relaxed rows and every relaxable
    row inside ``max_over_cap_factor`` (``slack_bound``) — the senior
    family's hard-feasible best, the apron's whole allowance at its
    service.  Returns ``(status, x, wall, model, targets)``; ``x`` is
    ``None`` when the set is infeasible even at the factor (the same
    feasible region the variance program has: the rounds / the ladder
    answer as before)."""
    opt = options or Options()
    rl = law.tables.emit.relaxation
    targets = runway_targets(pm, law)
    fit = {v: (STAGE1A_FIT_WEIGHT, t) for v, t in targets.items()}
    m = model(pm, cs, relaxed, rl.pad_slope_max, rl.max_over_cap_factor, fit, ())
    st, x, wall = lp(m, opt.time_limit_s)
    return st, x, wall, m, targets


def stage1b(pm: PlanarMap, cs: ConstraintSet, relaxed: _t.Sequence[Relaxed], law: Law,
            options: Options | None = None, backend: str | None = None,
            qp_time_limit_s: float | None = None, *, m=None,
            hold: _t.Mapping[int, float] | None = None,
            targets: _t.Mapping[int, float] | None = None) -> Stage1:
    """STAGE 1b (RULINGS 2026-09-06l): the variance program (module
    docstring, step 3) with every vertex of ``hold`` bounded to its value
    ± ``[relaxation] runway_hold_tolerance_m`` (bounds, no new row).  With
    no ``hold`` it is 04t(1)'s pure-variance program alone (``ORDER_
    VARIANCE``, the 06e relaxation — a twin's control).  ``m`` reuses a
    built model (stage 1a's, its fit columns uncharged)."""
    opt = options or Options()
    rl = law.tables.emit.relaxation
    if m is None:
        m = model(pm, cs, relaxed, rl.pad_slope_max, rl.max_over_cap_factor, None, ())
    mb = held(m, hold or {}, rl.runway_hold_tolerance_m)
    st, x, wall, be, note = _run_variance(mb, law, opt, backend, qp_time_limit_s)
    order = ORDER_LEXICOGRAPHIC if hold else ORDER_VARIANCE
    if x is None:
        return Stage1(st, be, wall, {}, {}, {}, note, 0, 0, order, 0.0, wall)
    excess, slack, planes = _read_relief(mb, x, relaxed)
    dep = {"stage1b": round(runway_departure(x, targets), 4)} if targets else {}
    return Stage1(st, be, wall, excess, slack, planes, note, 0, 0, order, 0.0, wall, dep,
                  dict(hold or {}))


def stage1(pm: PlanarMap, cs: ConstraintSet, relaxed: _t.Sequence[Relaxed], law: Law,
           options: Options | None = None, backend: str | None = None,
           qp_time_limit_s: float | None = None,
           weights: Weights | None = None, order: str | None = None) -> Stage1:
    """Stage 1 in the RULED ORDER (RULINGS 2026-09-06l, 04i applied to the
    last resort): LEXICOGRAPHIC — :func:`stage1a` places the runway family
    at its hard-feasible best inside the factor, :func:`stage1b` spreads
    the slack variance holding that runway within ``runway_hold_
    tolerance_m``; the runway sags only as far as the apron's allowance
    cannot cover.  ``backend`` forces stage 1b's ``"qp"`` / ``"pwl"``; by
    default the QP runs under ``qp_time_limit_s`` and the approximation
    takes over past it.  ``order`` overrides: ``ORDER_WEIGHTED`` is the
    single-stage alternative (06h b/c at the ladder's runway weight ×
    ``[relaxation] runway_fit_weight``; chosen by itself when that key is
    positive and ``weights`` are given), ``ORDER_VARIANCE`` 04t(1) alone
    (a twin's control: measured at HECA it priced sinking the runway at
    zero and relaxed pav132's chords to 1.18-1.45 % of an allowed 2.5 %,
    an 11.04 m bow — 06l)."""
    opt = options or Options()
    rl = law.tables.emit.relaxation
    if order is None:
        # 06m: the table's ``[relaxation] order`` answers; a positive
        # runway_fit_weight with weights selects the weighted alternative
        order = (ORDER_WEIGHTED if weights is not None and rl.runway_fit_weight > 0.0
                 else rl.order)
    if order == ORDER_VARIANCE:
        return stage1b(pm, cs, relaxed, law, opt, backend, qp_time_limit_s)
    if order == ORDER_WEIGHTED:
        if weights is None:
            raise ValueError("the weighted order needs the solve's weights")
        fit = {v: (w * rl.runway_fit_weight, tgt)
               for v, (w, tgt) in runway_fit(pm, law, weights).items()}
        smooth = [(a, m_, c, dp, dn, lam * rl.runway_fit_weight)
                  for a, m_, c, dp, dn, lam in roughness_stations(pm, weights)]
        m = model(pm, cs, relaxed, rl.pad_slope_max, rl.max_over_cap_factor, fit, smooth)
        st, x, wall, be, note = _run_variance(m, law, opt, backend, qp_time_limit_s)
        if x is None:
            return Stage1(st, be, wall, {}, {}, {}, note, m.linear_cols, m.linear_rows, order)
        excess, slack, planes = _read_relief(m, x, relaxed)
        return Stage1(st, be, wall, excess, slack, planes, note, m.linear_cols, m.linear_rows,
                      order)
    if order != ORDER_LEXICOGRAPHIC:
        raise ValueError(f"unknown stage-1 order {order!r}")
    st, x, wall_a, m, targets = stage1a(pm, cs, relaxed, law, opt)
    if x is None:
        return Stage1(st, "lp", wall_a, {}, {}, {}, "stage 1a (the runway's DEM fit) "
                      f"ended {st}", m.linear_cols, m.linear_rows, order, wall_a, 0.0)
    dep_a = runway_departure(x, targets)
    hold = {v: float(x[v]) for v in targets}
    s1 = stage1b(pm, cs, relaxed, law, opt, backend, qp_time_limit_s, m=m, hold=hold,
                 targets=targets)
    s1.wall_s += wall_a
    s1.stage1a_wall_s = wall_a
    s1.linear_cols, s1.linear_rows = m.linear_cols, m.linear_rows
    s1.runway_departure_m = {"stage1a": round(dep_a, 4), **s1.runway_departure_m}
    return s1
