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
3. **STAGE 1 — LEXICOGRAPHIC by law order (RULINGS 2026-09-06l, 04i
   applied to the last resort).**  Measured at HECA (lane v2bow2, the
   identical LP): the pure-variance program priced the apron's over-cap
   and priced sinking the runway at ZERO, so pav132's apron rows relaxed
   to 1.18–1.45 % of an allowed 2.5 % and runway 05C/23C bowed 11.04 m
   under the CIFP line.  So: **stage 1a** (:func:`stage1a`) minimises
   the RUNWAY family's L1 departure from its DEM fit (``variance.model``
   ``fit`` columns at weight 1 — the runway being senior, the ladder's
   weight is only a scale) subject to every un-relaxed row and every
   candidate inside ``max_over_cap_factor`` (``variance.slack_bound``);
   **stage 1b** (:func:`stage1b`) is the variance program below with
   every runway-family vertex HELD within ``[relaxation]
   runway_hold_tolerance_m`` of its stage-1a value (bounds, no new row).
   The runway sags only as far as the apron's allowance cannot cover.
   A positive ``[relaxation] runway_fit_weight`` is the WEIGHTED single-
   stage alternative instead (06h b/c at the ladder's runway weight ×
   that scale; 0 by default); ``ORDER_VARIANCE`` runs 04t(1) alone (a
   twin's control).  **The variance program.**  Every candidate ``Diff`` gets a
   GRADE excess ``g ≥ 0`` (``|z_a − z_b| ≤ (cap + g)·d``); a ``Linear`` a
   metre slack ``s`` on each finite side; a pad becomes ONE PLANE ``z_i =
   z_c + u·dx_i + v·dy_i`` over its vertices (``(u, v)`` its slope: its
   contact may slope, its interior stays one plane, no step can form —
   its rim vertices ARE the apron's own).  Objective ``min Σ d·g² + Σ s²
   + Σ D·(u² + v²)`` — the squared excess over the law INTEGRATED along
   the pavement (``d`` the chord, ``D`` the pad's extent): its optimum is
   the UNIFORM over-cap along the whole site, the spread the ruling asks
   for (a plain ``Σ g²`` would load the long chords, ``Σ metres²`` the
   short edges).  (The weighted alternative adds the 06h (b)/(c) RUNWAY
   family's L1 DEM-fit term at the ladder's runway weight and the ridge's
   smoothness λ — ``variance.model`` ``fit`` / ``smooth`` — measured at
   HECA (v2bow 7aeb747e) 11.04 → 10.12 m at 2.8× the relief, Σ 3,804 →
   10,680 m, and a ``pad_flat`` row: the owner keeps it off.)
   Backend: ``highspy``'s QP under
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
widens the site), up to ``max_rounds``.

NO CERTIFICATE IS NOT A REASON TO DEMOTE (RULINGS 2026-09-05u; spec
``relaxation-without-certificate-spec.md``; ``[relaxation]
scope_without_certificate`` / ``tier_ladder_last``).  The order of
answers on an infeasible hard set is (i) the IIS-scoped program above
when the certificate arrives inside ``iis_time_budget_s``; (ii) with no
certificate — the budget spent, the rounds spent, a stage that would not
solve — the SAME variance program over the WHOLE relaxable population
(:func:`full_scope`: every row ``relaxable_from_role``'s tier or a junior
one owns, every rigid pad as a plane ≤ ``pad_slope_max``), whose support
is the rows a certificate would have named; (iii) only when that is
still infeasible the tier ladder (``tiers.py``), which names the
governed family it demotes as a FAILURE.  A certificate that names NO
relaxable row (runway / taxi rows and pins alone) refutes (ii) without
running it.  ``RelaxReport.scope`` states which answered.  Measured
HECA 2026-09-05: the ladder demoted the taxi tier (3,037 rows, 5 m)
after 120 / 300 s certificate searches that never returned.  This
module imports ``law``, ``model`` and its siblings only (04q-3).
"""
from __future__ import annotations

import dataclasses as _dc
import math
import time
import typing as _t

import numpy as np

from ..law import Law
from ..law.tables import is_rigid_role, role_tier, tiers
from ..model.constraints import (REACH_GENERATOR, Band, ConstraintSet, Diff, Flat, Linear, Pin, Row,
                                 Source)
from ..model.planar import PlanarMap
from .api import Options, Solution, Status, Weights
from .assemble import roughness_stations, vertex_weights
from .highs import RESTATEMENT_MARGIN_M, solve as solve_hard
from .iis import (Certificate, IISBudgetExceeded, RowIndex, diagnose, neighbourhood_certificate,
                  row_vertices)
from .tiers import row_tier
from .variance import held, lp, model, pieces, pwl, qp, qp_available, without as _without

__all__ = ["RULING", "SCOPE_CERTIFICATE", "SCOPE_RELAXABLE", "SCOPE_LADDER", "Relaxed",
           "ORDER_LEXICOGRAPHIC", "ORDER_WEIGHTED", "ORDER_VARIANCE",
           "RelaxReport", "relaxable", "site_candidates", "full_scope", "stage1",
           "stage1a", "stage1b", "runway_targets", "runway_departure",
           "relaxed_hard_set", "certificate", "solve_relaxed", "qp_available"]

#: The ruling every relaxed row cites (the census heading).
RULING = "relaxed by 04t(1)"
#: Generator name of a relaxed pad's plane rows.
PLANE_GENERATOR = "pads"


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


#: The citation prefix of a row that states a ROLE's law (``Source.ruling``
#: ``common.roles.<role> …``): the law a row states is read from its own
#: citation, never from the face it sits on nor its generator's name.
LAW_CITATION = "common.roles."


def stated_role(r: Row, roles: _t.Container[str]) -> str | None:
    """The registered role whose law ``r`` cites (``common.roles.apron on
    the shared edge portion (04t-2)`` → ``apron``), or ``None``."""
    cite = r.source.ruling.split(" ", 1)[0]
    if not cite.startswith(LAW_CITATION):
        return None
    role = cite[len(LAW_CITATION):].split(".", 1)[0]
    return role if role in roles else None


def _law_tier(pm: PlanarMap, r: Row, tier_of: _t.Mapping[str, int], lowest: int) -> int:
    """The tier of the LAW a row states, never only of the face it sits
    on: a row the APRON law mints on a junction face (04t-2, the apron
    cap on the portion along the apron; ``apron.apron_edge_portions``) is
    an apron row — "a slightly over-cap apron" is exactly what 04t(1)
    admits — and reads the apron's tier.  Measured HECA 2026-09-05: the
    23C→05L reach floor rose 3.3 m under 04t-2's 1 % on 2.5 km of junction
    pav132's apron edge, the hard set went infeasible against the 05L pin,
    and the portion rows (taxi-tier by face) were refused as relaxable.
    The law is read from the row's CITATION (:func:`stated_role`): the
    first fix keyed on the generator's NAME, and ``apron_edge_portion`` is
    not a role — measured on the HECA replay (lane v2relaxfull, 2026-09-05)
    18,672 of 22,547 portion rows were still refused."""
    k = row_tier(pm, r, tier_of, lowest)
    role = stated_role(r, tier_of)
    law_k = tier_of.get(r.source.generator) if role is None else tier_of[role]
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
        order = (ORDER_WEIGHTED if weights is not None and rl.runway_fit_weight > 0.0
                 else ORDER_LEXICOGRAPHIC)
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


# ── stage 2: the relaxed HARD set ────────────────────────────────────────

def relaxed_hard_set(cs: ConstraintSet, relaxed: _t.Sequence[Relaxed], s1: Stage1,
                     tol: float = 1e-9, margin: float = RESTATEMENT_MARGIN_M
                     ) -> tuple[ConstraintSet, dict[int, Row | tuple[Row, ...]]]:
    """Every relaxed row at its solved relief: a ``Diff`` at ``cap + (s +
    margin)/d``, a ``Linear`` at ``hi + s + margin`` / ``lo − s − margin``,
    a pad as plane equalities at the solved gradient (a pad whose rise is
    below ``tol`` stays a ``Flat``); returns the set and ``index ->
    replacement``.  ``margin`` (``highs.RESTATEMENT_MARGIN_M``): the
    stage-1 point satisfies its rows only to the LP's feasibility
    tolerance, so a row re-stated at the slack EXACTLY is a knife edge
    the stage-2 solve may call infeasible (measured at HECA, lane v2bow2:
    the same set optimal in one process, infeasible in another)."""
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
            nr: Row = _dc.replace(r, cap=r.cap + s1.excess[x.index] + margin / max(r.d, tol),
                                  source=src)
            out.append(nr)
            repl[x.index] = nr
        elif x.kind == "linear":
            nr = _dc.replace(r, hi=None if r.hi is None else r.hi + s + margin,
                             lo=None if r.lo is None else r.lo - s - margin, source=src)
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
                pad_slope_max: float | None = None, grade_tol: float = 0.0,
                max_over_cap_factor: float | None = None
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
    worst_factor = 1.0
    for x in relaxed:
        if x.kind == "diff":
            r = x.row
            over.append(abs(z[r.a] - z[r.b]) - r.cap * r.d)
            if r.cap > 0.0 and r.d > 0.0:
                worst_factor = max(worst_factor, abs(z[r.a] - z[r.b]) / (r.cap * r.d))
    ok = worst_plane <= materiality_m and slope_ok and all(
        o <= s1.slack.get(x.index, 0.0) + materiality_m
        for o, x in zip(over, [x for x in relaxed if x.kind == "diff"]))
    factor_ok = (max_over_cap_factor is None
                 or worst_factor <= max_over_cap_factor * (1.0 + grade_tol)
                 + materiality_m)
    return {"plane_residual_max_m": round(worst_plane, 6),
            "pad_slope_max_seen": round(worst_slope, 7), "pad_slope_max": pad_slope_max,
            "shared_vertex_step_m": 0.0, "materiality_m": materiality_m,
            # THE SHAPE (05ae-2): the worst relaxed chord's |Δz| / (cap × d)
            "over_cap_factor_max_seen": round(worst_factor, 5),
            "max_over_cap_factor": max_over_cap_factor,
            "ok": bool(ok and factor_ok)}


# ── the whole last resort ────────────────────────────────────────────────

#: Which scope answered (``RelaxReport.scope``; RULINGS 2026-09-05u).
SCOPE_CERTIFICATE = "certificate"   # (i) the IIS-scoped program, the certificate in budget
SCOPE_RELAXABLE = "relaxable"       # (ii) the whole relaxable population, no certificate
SCOPE_LADDER = "ladder"             # (iii) the tier ladder answers (tiers.py) — a FAILURE when a governed family yields


@_dc.dataclass
class RelaxReport:
    """What the last resort did (``TierReport.relaxation``)."""

    applied: bool
    reason: str = ""
    #: which scope answered — ``certificate`` | ``relaxable`` | ``ladder``
    scope: str = ""
    backend: str = ""
    approximation: bool = False
    rounds: int = 0
    iis_rows: int = 0
    iis_wall_s: float = 0.0
    stage1_wall_s: float = 0.0
    stage2_wall_s: float = 0.0
    #: the candidate rows — the site's (certificate) or the whole relaxable population
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
    #: the certificate path's own exit when the relaxable scope answered
    certificate_reason: str = ""
    #: the stage-1 objective's LINEAR part (06h b/c): runway fit + ridge
    #: smoothness columns and their rows beside the slack variance
    linear_cols: int = 0
    linear_rows: int = 0
    #: RULINGS 2026-09-06l: the order stage 1 answered in (``lexicographic``
    #: | ``weighted`` | ``variance``), each stage's wall, and the runway
    #: family's departure Σ|z − fit| in metres — ``stage1a`` (its hard-
    #: feasible best inside the factor), ``stage1b`` (held), ``final``
    #: (stage 2's surface)
    order: str = ""
    stage1a_wall_s: float = 0.0
    stage1b_wall_s: float = 0.0
    runway_departure_m: dict[str, float] = _dc.field(default_factory=dict)
    runway_vertices: int = 0

    def as_dict(self) -> dict[str, _t.Any]:
        d = _dc.asdict(self)
        d["ruling"] = RULING
        return d

    def line(self) -> str:
        if not self.applied:
            return f"relaxation (04t-1) not applied: {self.reason}"
        s, sm = self.stats, self.stats_m
        how = (f"over the {self.scope.upper()} scope" if self.scope == SCOPE_RELAXABLE
               else "IIS-scoped")
        cert = (f"IIS {self.iis_rows} rows in {self.iis_wall_s:.1f} s" if self.scope == SCOPE_CERTIFICATE
                else f"no certificate ({self.certificate_reason or 'search skipped'})")
        return (f"relaxation (04t-1) applied {how}: {cert}, "
                f"{self.candidates} candidates, {len(self.rows)} relaxed "
                f"({self.backend}{' approx' if self.approximation else ''}, {self.rounds} round(s)"
                f"{'; ' + self.note if self.note else ''}); excess grade mean {s.get('mean', 0):.5f} "
                f"max {s.get('max', 0):.5f} sd {s.get('sd', 0):.5f} max/mean {s.get('max_over_mean', 0):.2f}; "
                f"relief Σ {sm.get('sum', 0):.3f} m max {sm.get('max', 0):.3f} m; "
                f"worst over-cap factor {self.certificate.get('over_cap_factor_max_seen', 0):.3f} "
                f"(bound {self.certificate.get('max_over_cap_factor')}); "
                f"order {self.order or '?'} (06l): stage1a {self.stage1a_wall_s:.1f} s "
                f"stage1b {self.stage1b_wall_s:.1f} s stage2 {self.stage2_wall_s:.1f} s; "
                f"runway departure Σ|z−dem| over {self.runway_vertices} vertices: "
                + ", ".join(f"{k} {v:.2f} m" for k, v in self.runway_departure_m.items())
                + f"; linear part {self.linear_cols} columns, {self.linear_rows} rows; "
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


def full_scope(pm: PlanarMap, law: Law, cs: ConstraintSet) -> list[Relaxed]:
    """THE WHOLE RELAXABLE POPULATION (RULINGS 2026-09-05u, ``[relaxation]
    scope_without_certificate = "relaxable"``): every hard ``Diff`` /
    ``Linear`` owned (``_law_tier``) by ``relaxable_from_role``'s tier or a
    junior one, and every rigid face's ``Flat`` group (a pad, as a plane
    ≤ ``pad_slope_max``) — the same admission as :func:`relaxable`, over
    the set instead of a site.  The variance program gives a row in no
    contradiction exactly zero slack, so its support is still "the rows
    an IIS would name" — without waiting for one."""
    return relaxable(pm, law, [*cs.flats, *cs.diffs, *cs.linears])


def _note_stage1(rep: RelaxReport, s1: Stage1) -> None:
    """Stage 1's account on the report (both scopes, applied or not)."""
    rep.backend = s1.backend
    rep.approximation = s1.backend == "pwl"
    rep.note = s1.note
    rep.linear_cols, rep.linear_rows = s1.linear_cols, s1.linear_rows
    rep.order = s1.order
    rep.stage1a_wall_s += s1.stage1a_wall_s
    rep.stage1b_wall_s += s1.stage1b_wall_s
    rep.runway_departure_m = dict(s1.runway_departure_m)
    rep.runway_vertices = len(s1.hold)


def _finish(rep: RelaxReport, pm: PlanarMap, law: Law, relaxed: _t.Sequence[Relaxed],
            s1: Stage1, sol: Solution, unrelaxed: _t.Sequence[Row]) -> None:
    """The report of an applied relaxation: the support, the spread, the
    certificate (module docstring, step 5); the runway family's departure
    at stage 1b's point and on the final surface (06l)."""
    rl = law.tables.emit.relaxation
    tol_g = law.tables.emit.materiality.grade
    rep.applied = True
    targets = runway_targets(pm, law)
    rep.runway_vertices = len(targets)
    rep.runway_departure_m["final"] = round(runway_departure(sol.z, targets), 4)
    # the SUPPORT: an excess below the materiality floor is a residual,
    # never a relaxed row (owner 2026-08-02 convergence guards)
    support = [x for x in relaxed
               if s1.excess.get(x.index, 0.0) >= (tol_g if x.kind != "linear" else rl.materiality_m)]
    rep.rows = [_row_record(pm, x, s1) for x in support]
    rep.unrelaxed = [{"kind": type(r).__name__, "family": r.source.generator,
                      "ruling": r.source.ruling, "inputs": list(r.source.inputs)}
                     for r in unrelaxed]
    rep.stats = _stats([s1.excess[x.index] for x in support if x.kind != "linear"])
    rep.stats_m = _stats([s1.slack[x.index] for x in support])
    rep.certificate = certificate(pm, support, s1, sol.z, rl.materiality_m,
                                  rl.pad_slope_max, tol_g, rl.max_over_cap_factor)


def _certificate_rounds(pm: PlanarMap, cs: ConstraintSet, law: Law, weights: Weights,
                        opt: Options, rep: RelaxReport, *, size_out: dict | None,
                        backend: str | None
                        ) -> tuple[Solution | None, ConstraintSet | None, bool]:
    """(i) THE IIS-SCOPED PROGRAM, inside ``iis_time_budget_s`` (module
    docstring, steps 1–5; ``cs`` WITH its reach envelope — the cached
    certificate is built on it, the rows are then freed of it).  Returns
    ``(solution, relaxed set, proven)`` — ``proven`` when a certificate
    NAMED NO RELAXABLE ROW: an infeasible subsystem of runway / taxi rows
    and pins stays infeasible under any relaxation of the junior rows, so
    the relaxable scope is refuted without running (the ladder answers)."""
    rl = law.tables.emit.relaxation
    deadline = time.perf_counter() + rl.iis_time_budget_s
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
                          f"(round {rnd}: {e})")
            return None, None, False
        rep.iis_wall_s += time.perf_counter() - t
        rep.iis_rows += len(rows)
        if not rows:
            rep.reason = (f"round {rnd}: no IIS found on the set with the relaxed rows "
                          f"dropped, yet the relaxed program is infeasible (a pad's plane "
                          f"cannot absorb its contradiction)")
            return None, None, False
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
            return None, None, True
        relaxed_all = cand
        rep.candidates = len(relaxed_all)
        t = time.perf_counter()
        s1 = stage1(pm, cs, relaxed_all, law, opt, backend,
                    qp_time_limit_s=min(rl.qp_time_budget_s,
                                        max(1.0, deadline - time.perf_counter())),
                    weights=weights)
        rep.stage1_wall_s += time.perf_counter() - t
        _note_stage1(rep, s1)
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
            rep.reason = f"stage 1 ({s1.backend}) ended {s1.status}"
            return None, None, False
        cs2, _repl = relaxed_hard_set(cs, relaxed_all, s1)
        t = time.perf_counter()
        sol = solve_hard(pm, cs2, weights, quiet, size_out=size_out)
        rep.stage2_wall_s += time.perf_counter() - t
        if sol.status not in (Status.OPTIMAL, Status.FEASIBLE):
            rep.reason = (f"stage 2 ended {sol.status.value} on the relaxed set "
                          f"({sol.message[:120]})")
            return None, None, False
        _finish(rep, pm, law, relaxed_all, s1, sol, unrelaxed)
        return sol, cs2, False
    rep.reason = f"{rl.max_rounds} rounds spent without a feasible relaxed set"
    return None, None, False


def _relaxable_scope(pm: PlanarMap, cs: ConstraintSet, law: Law, weights: Weights,
                     opt: Options, rep: RelaxReport, *, size_out: dict | None,
                     backend: str | None) -> tuple[Solution | None, ConstraintSet | None]:
    """(ii) 04t(1) OVER THE WHOLE RELAXABLE SCOPE (RULINGS 2026-09-05u):
    the same variance program with every relaxable row a candidate, then
    the normal solve on the relaxed hard set.  Infeasible here means the
    contradiction lies among the runway / taxi rows and the pins — the
    ladder answers, and its demotion is a FAILURE (``tiers.py``)."""
    rl = law.tables.emit.relaxation
    quiet = _dc.replace(opt, diagnose_iis=False)
    cand = full_scope(pm, law, cs)
    rep.candidates = len(cand)
    rep.rounds += 1
    if not cand:
        rep.reason += "; the set holds no relaxable row"
        return None, None
    t = time.perf_counter()
    s1 = stage1(pm, cs, cand, law, opt, backend, qp_time_limit_s=rl.qp_time_budget_s,
                weights=weights)
    rep.stage1_wall_s += time.perf_counter() - t
    _note_stage1(rep, s1)
    if s1.status == "infeasible":
        rep.reason += (f"; the {SCOPE_RELAXABLE} scope ({len(cand)} candidates) is STILL "
                       f"infeasible — the contradiction lies among the runway / taxi rows "
                       f"and the pins")
        _name_unrelaxable(pm, cs, cand, rl.qp_time_budget_s, rep)
        return None, None
    if s1.status != "optimal":
        rep.reason += f"; stage 1 ({s1.backend}) over the {SCOPE_RELAXABLE} scope ended {s1.status}"
        return None, None
    cs2, _repl = relaxed_hard_set(cs, cand, s1)
    t = time.perf_counter()
    sol = solve_hard(pm, cs2, weights, quiet, size_out=size_out)
    rep.stage2_wall_s += time.perf_counter() - t
    if sol.status not in (Status.OPTIMAL, Status.FEASIBLE):
        rep.reason += (f"; stage 2 ended {sol.status.value} on the {SCOPE_RELAXABLE}-scope "
                       f"relaxed set ({sol.message[:120]})")
        return None, None
    _finish(rep, pm, law, cand, s1, sol, ())
    return sol, cs2


def _name_unrelaxable(pm: PlanarMap, cs: ConstraintSet, cand: _t.Sequence[Relaxed],
                      time_limit_s: float, rep: RelaxReport) -> None:
    """THE NAMING the owner rules on: the certificate of the set with EVERY
    relaxable row dropped — rows the ruling may not relax, contradicting
    each other (HECA replay 2026-09-05: 65 rows in 0.9 s — runway 05C/23C's
    transverse and profile rows, taxi rows on stub pav91 / parallel pav112,
    their no-step pairs, no pin, no apron).  Published as ``unrelaxed`` and
    summarised in the reason; bounded by ``qp_time_budget_s`` (a budget the
    table already carries), and silent past it."""
    try:
        t = time.perf_counter()
        sup = Certificate(len(pm.vertices), _without(cs, cand).rows()).ray(time_limit_s)
        rep.iis_wall_s += time.perf_counter() - t
    except (ImportError, IISBudgetExceeded):
        return
    if not sup:
        return
    rep.unrelaxed = [{"kind": type(r).__name__, "family": r.source.generator,
                      "ruling": r.source.ruling, "inputs": list(r.source.inputs)}
                     for r in sup]
    hist: dict[str, int] = {}
    for r in sup:
        k = f"{type(r).__name__}:{r.source.generator}"
        hist[k] = hist.get(k, 0) + 1
    faces: dict[str, int] = {}
    for r in sup:
        for inp in r.source.inputs:
            if inp.startswith("face:"):
                try:
                    f = pm.faces[int(inp[5:])]
                except (KeyError, ValueError):
                    continue
                key = f"{f.role}/{f.ref}"
                faces[key] = faces.get(key, 0) + 1
    top = ", ".join(f"{k}={v}" for k, v in sorted(faces.items(), key=lambda kv: -kv[1])[:6])
    rep.reason += (f" — the unrelaxable contradiction ({len(sup)} rows): "
                   + ", ".join(f"{k}={v}" for k, v in sorted(hist.items()))
                   + (f"; faces {top}" if top else ""))


def solve_relaxed(pm: PlanarMap, cs: ConstraintSet, law: Law, weights: Weights,
                  options: Options | None = None, *, size_out: dict | None = None,
                  backend: str | None = None
                  ) -> tuple[Solution | None, RelaxReport, ConstraintSet | None]:
    """The last resort on an INFEASIBLE hard set, in the ruled order
    (RULINGS 2026-09-05u): (i) the IIS-scoped program when a certificate
    arrives inside ``iis_time_budget_s``; (ii) with none, 04t(1) over the
    whole relaxable scope (``scope_without_certificate``); (iii) only then
    the tier ladder (``tier_ladder_last``) — ``solution`` is ``None`` and
    ``report.scope == "ladder"`` when it must answer (``report.reason``).
    A certificate naming NO relaxable row refutes (ii) without running it.
    Returns ``(solution, report, the relaxed hard set)``."""
    opt = options or Options()
    rl = law.tables.emit.relaxation
    rep = RelaxReport(False)
    proven = False
    if rl.iis_time_budget_s > 0.0:
        sol, cs2, proven = _certificate_rounds(pm, cs, law, weights, opt, rep,
                                               size_out=size_out, backend=backend)
        if sol is not None:
            rep.scope = SCOPE_CERTIFICATE
            return sol, rep, cs2
    else:
        rep.reason = f"iis_time_budget_s {rl.iis_time_budget_s:g}: no certificate search"
    if not proven and rl.scope_without_certificate == SCOPE_RELAXABLE and rl.tier_ladder_last:
        rep.certificate_reason = rep.reason
        # the rows, never their reach envelope (module docstring, step 2)
        sol, cs2 = _relaxable_scope(pm, envelope_free(cs), law, weights, opt, rep,
                                    size_out=size_out, backend=backend)
        if sol is not None:
            rep.scope = SCOPE_RELAXABLE
            return sol, rep, cs2
    rep.scope = SCOPE_LADDER
    rep.reason += "; the tier machinery (04i) answers"
    return None, rep, None
