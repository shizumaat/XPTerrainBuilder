"""THE DESIGN REPORT — what the design surface's one solve says it did.

Split out of ``solve/design.py`` under the 1,000-line law (the same move
``airport/obj8_clip.py`` made for ``obj8.py``): the report is a pure
record and its rendering, with no algebra, so it reads and reviews on its
own.  ``solve.design`` re-exports :class:`DesignReport`, which is the name
every caller uses.
"""
from __future__ import annotations

import dataclasses as _dc
import typing as _t

import numpy as np

from ..model.constraints import ConstraintSet
from .api import Residual
from .project import ProjectionReport, ZoneClampReport
from .linear import DEFAULT_METHOD

__all__ = ["DesignReport", "residual", "settled_flip", "hard_exceeds",
           "hard_metres", "row_metre_scale", "HARD_READ_EPS"]

#: THE SETTLE TEST'S NUMERICAL FLOOR (lane ``v2settle``, spec §20a).  The
#: runway projection is a QP that solves its own rows TO ``hard_tol_m``, so
#: it lands them AT the bar — and a strict ``> tol`` on a solver residual
#: 2e-14 to 6e-13 m above its own target reports a HELD row as a violation.
#: MEASURED at HECA (staged, capture off b1b7704c): 6 of stage 1's 33
#: "unsettled" rows were ``runway_profile`` rows at 0.020000000000023 ..
#: 0.020000000000583 m — the projection's certificate read as its own
#: failure.  RULINGS 2026-09-13ac named this class cosmetic and left the two
#: readers rounding opposite ways; ONE derivation ends that.  Absolute, not
#: relative to the row: it is the solver's floor, not the surface's.
HARD_READ_EPS = 1e-9


def row_metre_scale(terms: _t.Iterable[tuple[int, float]]) -> float:
    """THE METRE SCALE OF ONE LAW ROW: ``2 / Σ|c|`` over the row's OWN
    terms — every vertex it names, pinned or free (1 for a two-vertex Δz
    row, ``≈ d/2`` for a vertical-curve row).  The ONE derivation the
    design report, its infeasibility certificate and ``v2_solve_replay
    --why-hard`` read a hard row's violation in (lane ``surfacesettle``,
    issues #21/#22): scaled by the REDUCED sum instead, a row with a pinned
    side read double and one whose free term was a 0.097 interpolation
    weight read 20x (GEML 3.5369 m reported, 0.1719 m on the surface)."""
    s = sum(abs(float(c)) for _v, c in terms)
    return 2.0 / s if s > 0.0 else 1.0


def hard_metres(one: list, hard_i: np.ndarray, raw: np.ndarray) -> np.ndarray:
    """``raw`` (each hard row's ``Σ c·z − bound`` in the row's own units,
    positionally over ``hard_i``) in METRES of surface — :func:`row_metre_scale`
    per row."""
    sc = np.fromiter((row_metre_scale(one[int(k)][0]) for k in hard_i),
                     dtype=float, count=len(hard_i))
    return np.asarray(raw, dtype=float) * sc


def _infeasible_set(hard_i: np.ndarray, bad: np.ndarray, one: list,
                    red: _t.Any, z: np.ndarray, limit: int = 12,
                    max_rows: int = 4000) -> dict[str, _t.Any]:
    """IS THE LAW SATISFIABLE WHERE THE HARD SET DID NOT SETTLE? (lane
    ``v2settle``, spec §20a.)

    Around the surviving rows, flood over the hard rows that SHARE A COLUMN
    with them (``limit`` hops, capped at ``max_rows`` rows so a pathological
    component cannot turn a report into a second solve).  Every column the
    component does not contain is held at its shipped value and folded into
    the right-hand side; then

        min Σ s   s.t.   A x - s <= b,   s >= 0

    over the component's own columns.  ``Σ s`` is the SMALLEST total
    shortfall any surface can leave on those rows.  Zero means they can all
    hold and the residual belongs to the solve (a multiplier that did not
    close, an active set that did not settle); positive is a PROOF of
    infeasibility, and the rows carrying slack at the optimum are the
    infeasible set — the rows the law makes impossible together, named
    instead of silently traded.

    Returns ``{}`` when the certificate could not be taken (no solver, no
    free column, the cap hit), which the line reports as neither.
    """
    # 1. the rows, by column adjacency
    cols_of: list[frozenset[int]] = []
    for k in hard_i:
        terms = one[int(k)][0]
        acc: dict[int, float] = {}
        for v, c in terms:
            col = int(red.col[v])
            if col >= 0:
                acc[col] = acc.get(col, 0.0) + c
        cols_of.append(frozenset(c for c, w in acc.items() if w != 0.0))
    by_col: dict[int, list[int]] = {}
    for i, cs_ in enumerate(cols_of):
        for c in cs_:
            by_col.setdefault(c, []).append(i)
    seen = set(int(i) for i in bad)
    frontier = set(seen)
    for _hop in range(max(1, int(limit))):
        nxt: set[int] = set()
        for i in frontier:
            for c in cols_of[i]:
                nxt.update(by_col.get(c, ()))
        nxt -= seen
        if not nxt or len(seen) + len(nxt) > max_rows:
            break
        seen |= nxt
        frontier = nxt
    idx = sorted(seen)
    comp_cols = sorted({c for i in idx for c in cols_of[i]})
    if not comp_cols or not idx:
        return {}
    pos = {c: j for j, c in enumerate(comp_cols)}

    # 2. the rows, reduced onto the component's columns; everything else at z
    import numpy as _np
    rowsA: list[list[tuple[int, float]]] = []
    rhs: list[float] = []
    for i in idx:
        terms, hi, _r = one[int(hard_i[i])]
        acc: dict[int, float] = {}
        b = float(hi)
        for v, c in terms:
            col = int(red.col[v])
            if col < 0:
                b -= c * float(red.value[v])
            elif col in pos:
                acc[pos[col]] = acc.get(pos[col], 0.0) + c
            else:                       # outside the component: held at z
                b -= c * float(z[v])
        acc = {j: w for j, w in acc.items() if w != 0.0}
        if not acc:
            continue
        # the row's OWN metres (:func:`row_metre_scale`) — never the sum
        # over the component's columns, which read a pinned-side row double
        sc = row_metre_scale(terms)
        rowsA.append([(j, w * sc) for j, w in acc.items()])
        rhs.append(b * sc)
    if not rowsA:
        return {}

    # 3. min Sum s  s.t.  A x - s <= b,  s >= 0
    try:
        import highspy
    except Exception:
        return {}
    inf = highspy.kHighsInf
    nx, ns = len(comp_cols), len(rowsA)
    h = highspy.Highs()
    h.setOptionValue("output_flag", False)
    h.addVars(nx, _np.full(nx, -inf), _np.full(nx, inf))
    h.addVars(ns, _np.zeros(ns), _np.full(ns, inf))
    h.changeColsCost(ns, _np.arange(nx, nx + ns, dtype=_np.int32),
                     _np.ones(ns))
    starts, index, value = [], [], []
    for r, terms in enumerate(rowsA):
        starts.append(len(index))
        for j, w in terms:
            index.append(j); value.append(w)
        index.append(nx + r); value.append(-1.0)
    h.addRows(ns, _np.full(ns, -inf), _np.asarray(rhs, float),
              len(index), _np.asarray(starts, _np.int32),
              _np.asarray(index, _np.int32), _np.asarray(value, float))
    h.run()
    if h.getModelStatus() != highspy.HighsModelStatus.kOptimal:
        return {}
    sol = _np.asarray(h.getSolution().col_value, float)
    slack = sol[nx:]
    total = float(slack.sum())
    tight = int(_np.count_nonzero(slack > 1e-7))
    return {"rows_considered": len(rowsA), "columns": nx,
            "total_slack_m": round(total, 6),
            "rows_in_set": tight,
            "infeasible": bool(total > 1e-6),
            "feasible": bool(total <= 1e-6)}


def hard_exceeds(viol, tol: float):
    """Is this hard-row residual a VIOLATION, or the solver's own floor at
    the bar?  ``viol`` is metres of surface over the row's bound (positive
    is a violation), ``tol`` is ``hard_tol_m``.  Works on a scalar or an
    array."""
    return viol > tol + HARD_READ_EPS


def settled_flip(viol: np.ndarray, tol: float,
                 active: _t.AbstractSet[int]) -> tuple[bool, int, float]:
    """THE SETTLED CONDITION of the design solve's active set (owner
    RULINGS 2026-09-12u, spec §30 (3c)), stated ONCE: given the current
    one-sided violations, the tolerance and the set that was active,
    return ``(settled, rows that flipped label, the worst violation
    among them)``.

    The set is SETTLED when no row changes label, or when every row that
    does sits inside ONE tolerance band of the threshold (violation
    ``<= 2 * tol``) — a row hovering at its own bound flips without
    moving the surface, and that is the only flip settlement forgives.
    Until 12u ``converged`` was asserted on TWO weaker exits — the
    objective stalling within 1e-6, and the line search buying nothing —
    either of which fires while thousands of rows are still crossing
    their bounds by metres.  Both are still exits (there is nothing
    better to return), but they no longer claim settlement, and the flip
    they exit on is REPORTED (``set_flips`` / ``set_flip_max_m``)."""
    nxt = set(np.flatnonzero(viol > tol).tolist())
    flip = np.asarray(sorted(nxt ^ set(active)), dtype=np.int64)
    if not flip.size:
        return True, 0, 0.0
    worst = float(np.max(np.abs(viol[flip])))
    return worst <= 2.0 * tol, int(flip.size), worst


# ── the report ──────────────────────────────────────────────────────────

@_dc.dataclass
class DesignReport:
    """The residual per family and per objective term — what ``law_tiers``
    used to be, read the design surface's way: a law is a TARGET, so a
    missed target is a residual, never a demotion."""

    rounds: int = 0
    #: THE ACTIVE SET SETTLED (owner RULINGS 2026-09-12u, spec §30 (3c)):
    #: asserted ONLY where no row changed label, or where every row that did
    #: hovers within one tolerance band of its own bound
    #: (``solve.design._settled``).  The objective stalling and the line
    #: search buying nothing are EXITS, not settlement.
    converged: bool = False
    #: the rows that changed label at the exit, and the worst violation
    #: among them — the flip an unsettled exit is reported by
    set_flips: int = 0
    set_flip_max_m: float = 0.0
    method: str = DEFAULT_METHOD
    unknowns: int = 0
    fixed: int = 0
    rows: int = 0
    triangles: int = 0
    components: int = 0
    detached: int = 0
    #: THE PER-BODY DATUM (RULINGS 2026-09-09p (3); the AFFINE fit of
    #: 2026-09-10t (1) / 10v (2)): THREE rows per APRON BODY — its mean and
    #: its two first moments against the same moments of the DEM under its
    #: own vertices, i.e. its plane follows the ground's plane
    body_datum_rows: int = 0
    #: how many BODIES those rows cover (three rows each where the geometry
    #: carries all three; a collinear body fewer)
    body_datum_bodies: int = 0
    #: one record per datum BODY — ``kind``, the body's ``ll`` identity, how
    #: many vertices its plane is fitted over, the MEAN DEM under it, and
    #: the solved PLANE RESIDUAL: ``residual_m`` (its mean against the DEM
    #: mean) and ``tilt_m`` (the worst of the two moment rows, read as
    #: metres of rise over the body's own RMS half-extent)
    body_datums: list[dict[str, _t.Any]] = _dc.field(default_factory=list)
    #: THE TAXI CHAIN TREND (owner RULINGS 2026-09-10v (1); spec §8.6):
    #: per chain the built surface against its published target profile
    #: (RMS and max) and its mean z − DEM — filled by the pipeline after
    #: the projection (``constraints/taxi_trend.taxi_trend_block``)
    taxi_trend: dict[str, _t.Any] = _dc.field(default_factory=dict)
    #: how many vertices carry a trend target row
    taxi_trend_rows: int = 0
    #: THE APRON BODY'S 2-D TREND (owner RULINGS 2026-09-10ar; spec §8.7):
    #: per body carrying a 2-D trend, the built surface against its
    #: published target (RMS and max) and its mean z − DEM — filled by the
    #: pipeline after the projection
    #: (``constraints/apron_trend.apron_trend_block``)
    apron_trend: dict[str, _t.Any] = _dc.field(default_factory=dict)
    #: how many apron vertices carry a 2-D trend row (such a body carries
    #: NO affine ``body_datum`` rows)
    apron_trend_rows: int = 0
    #: THE GROUND'S OWN DATUM (owner RULINGS 2026-09-10av; spec §23): how
    #: many ADJACENT-GROUND vertices carry the weak ``z = DEM`` row — the
    #: ``graded_strip`` family minus the pavement vertices and minus the
    #: interior pockets enclosed by pavement (09g (1))
    ground_datum_rows: int = 0
    #: THE LEVEL BELT (RULINGS 2026-09-13, lane ``v2zerocrater``; spec §23.4):
    #: how many vertices reached the solve in a piece with NO LEVEL AT ALL —
    #: bending and relative rows only, whose least-squares minimiser is the
    #: sentinel 0.0 m — and took their own terrain plane instead.  A non-zero
    #: count is worth reading: it names geometry no law levels.
    level_belt_rows: int = 0
    #: §20a's tie-break rows (lane ``v2settle`` r2): one per free column
    #: §20a: HOW each damped active-set solve ENDED, in order (lane
    #: ``v2settle`` r2).  ``SET NOT SETTLED`` said only that it did not; the
    #: three exits are different failures with different cures, and a local
    #: perturbation at ONE HECA vertex flipped the whole field's surface by
    #: changing WHICH one fires (959 vertices > 0.02 m, 953 of them beyond
    #: 500 m, max 0.52 m — RULINGS 2026-09-14br's field-wide shift,
    #: reproduced offline with no pads involved).
    set_exits: list[tuple[str, int, int]] = _dc.field(default_factory=list)
    #: §20c (3) THE QP's OWN RECORD (``[design] solver = "qp"``, RULINGS
    #: 2026-09-14bw): one entry per exact solve — its status, its rounds,
    #: the linear solves it paid, the objective it reached, the gradient
    #: norm there and its wall.  ``set_exits`` is the fixed point's
    #: instrument and stays EMPTY on this arm; these are what replaces it.
    qp_solves: list[tuple[str, int, int, float, float, float]] = _dc.field(
        default_factory=list)
    #: THE FOOT ROWS (owner RULINGS 2026-09-11q, repriced 11ab; spec
    #: §11b (2)): the per-foot placement targets of every bare-ground
    #: body, priced at ``pad_flat`` (``constraints/foot_rows.py``)
    foot_rows: int = 0
    #: WHY a foot row is missed (round 8's attribution surface): the
    #: per-FOOT residual distribution, how many feet stand on a triangle
    #: with no free column at all, and how many share one triangle with
    #: another foot asking for a different level — a sheet is LINEAR over
    #: a triangle, so two feet in one face cannot both be carried
    foot_row_diag: dict[str, _t.Any] = _dc.field(default_factory=dict)
    #: law rows whose one foot is the terrain beyond the zone's outer ring:
    #: the BANK (08t answers 2/3) — reported, never a design target
    bank_rows: int = 0
    #: THE HARD ROWS (RULINGS 2026-09-08v): the runway family's law rows as
    #: constraints — how many exist, how many the settled active set holds,
    #: how many polish rounds it took and the worst violation left (a
    #: constraint held exactly reads 0 to the solver's tolerance)
    hard_rows: int = 0
    #: THE VIOLATED ROWS OF THE SHIPPED SURFACE (owner RULINGS 2026-09-12u,
    #: spec §30 (3b)).  Until 12u this was phase C's MULTIPLIER count — how
    #: many rows the augmented Lagrangian had ever charged, read before the
    #: final projection — which at LEMD read 1,457 where the surface that
    #: shipped violated 725.  A count nobody can act on is not an
    #: instrument; the number reported is now the rows over ``hard_tol_m``
    #: on the surface the build emits, re-read after the projection like
    #: the worst violation beside it.
    hard_active: int = 0
    hard_rounds: int = 0
    hard_max_violation_m: float = 0.0
    hard_settled: bool = True
    #: the ruling of the worst-held hard row (empty where every row is held)
    hard_worst: str = ""
    #: THE FINAL PROJECTION (owner RULINGS 2026-09-09y): the runway family's
    #: hard rows held EXACTLY by a QP after the solve (``solve/project.py``)
    runway_projection: ProjectionReport = _dc.field(default_factory=ProjectionReport)
    #: THE ZONE PROJECTION (RULINGS 2026-09-12ag; spec §32): every
    #: adjacent-ground zone vertex clamped into its own corridor band
    #: after the runway projection (``solve/project.project_zone_bands``)
    zone_projection: ZoneClampReport = _dc.field(default_factory=ZoneClampReport)
    #: THE ONE-WAY ROWS (RULINGS 2026-09-09b (2)/(3)): the adjacent-ground
    #: corridor and strip-tie rows whose pavement feet are LAGGED — how
    #: many, how many lag rounds the outer loop paid, whether the lag
    #: settled and how far the worst leader foot moved in the last round
    one_way_rows: int = 0
    one_way_rounds: int = 0
    one_way_settled: bool = True
    one_way_move_m: float = 0.0
    #: §20a THE LAG IS A CONVERGENCE CONDITION (Fable 2026-09-13; owner
    #: RULINGS 2026-09-13ac).  When the lag exhausts ``one_way_max_rounds``
    #: without reaching ``one_way_tol_m`` the report NAMES the failure —
    #: how many rows still move, the worst row's generator and ruling, its
    #: LEADER vertex (id and lat/lon) and that leader's last move.  Until
    #: 13ac the cap was a silent stop at three rounds and the polish ran
    #: inside a lag that had not converged.
    one_way_failure: dict[str, _t.Any] = _dc.field(default_factory=dict)
    #: §20a's named HARD failure and its feasibility certificate (lane
    #: ``v2settle``): which rows are left over ``hard_tol_m``, where, and
    #: whether the law is satisfiable there at all
    hard_failure: dict[str, _t.Any] = _dc.field(default_factory=dict)
    #: §20b THE STAGED SOLVE (owner RULINGS 2026-09-13dh, ordered
    #: 2026-09-14an).  ``staged`` says the two-stage form ran; ``stages``
    #: carries stage 1's own counters (rows, columns, hard set, lag,
    #: projections, wall) beside stage 2's, which are this report's own
    #: fields; ``stage_dropped_rows`` is how many law rows this assembly
    #: refused as foreign to its stage; ``stage1_fixed`` how many airside
    #: vertices stage 2 substituted as constants and ``stage1_unlevelled``
    #: how many airside columns stage 1 left with NO always-on row (§20b
    #: (4)) and therefore did NOT fix.
    staged: bool = False
    stages: dict[str, _t.Any] = _dc.field(default_factory=dict)
    stage_dropped_rows: int = 0
    stage1_fixed: int = 0
    stage1_unlevelled: int = 0
    stage1_wall_s: float = 0.0
    stage2_wall_s: float = 0.0
    bend_rows_by_class: dict[str, int] = _dc.field(default_factory=dict)
    #: THE MISSED TARGETS (sidecar ``design_target``, RULINGS 2026-09-08t/v):
    #: one record per law row the design surface did not reach — its family,
    #: the metres it is out by and the lat/lon identities of its vertices, so
    #: the census can report the rows it counts under one heading
    targets: list[dict[str, _t.Any]] = _dc.field(default_factory=list)
    solver_wall_s: float = 0.0
    #: THE RUNWAY PROFILE (spec §21.2 (4)): per runway the target kind and
    #: window, the built ridge's residual against its target, its mean
    #: |z - DEM| and the law row that holds it — filled by the pipeline
    #: after the projection (``pipeline/runway_report.runway_profile_block``), and
    #: carried into the sidecar's ``design`` block so the census and the
    #: owner read WHICH target the runway was designed to.
    runway_profile: dict[str, _t.Any] = _dc.field(default_factory=dict)
    families: dict[str, dict[str, _t.Any]] = _dc.field(default_factory=dict)
    terms: dict[str, float] = _dc.field(default_factory=dict)

    def record_flip(self, res: tuple[bool, int, float]) -> bool:
        """Record one active-set EXIT's flip (§30 (3c), ``settled_flip``) and
        return whether that exit SETTLED."""
        ok, n, worst = res
        self.set_flips = max(self.set_flips, int(n))
        self.set_flip_max_m = max(self.set_flip_max_m, round(float(worst), 4))
        return bool(ok)

    def note_set_exit(self, why: str, rounds: int, size: int) -> None:
        """One damped active-set solve ended: ``same_set`` is the fixed
        point (the only real convergence), ``objective_stalled`` and
        ``line_search_stalled`` are the two early exits, ``round_cap`` the
        ceiling."""
        self.set_exits.append((why, int(rounds), int(size)))

    def note_qp(self, status: str, rounds: int, solves: int, objective: float,
                grad_norm: float, wall_s: float) -> None:
        """One §20c exact solve ended (``solve/design_qp.solve_one_sided``).
        ``optimal`` is the objective's own convergence floor, ``no_descent``
        the linear solve's precision floor — both are the minimum;
        ``round_cap`` is a NAMED failure."""
        self.qp_solves.append((str(status), int(rounds), int(solves),
                               float(objective), float(grad_norm),
                               round(float(wall_s), 3)))

    def qp_line(self) -> str:
        """The QP arm's own line: how each solve ended, what it paid, and
        the worst gradient norm left (empty on the fixed-point arm)."""
        if not self.qp_solves:
            return ""
        by: dict[str, int] = {}
        for st, *_ in self.qp_solves:
            by[st] = by.get(st, 0) + 1
        rounds = sum(r for _s, r, *_ in self.qp_solves)
        solves = sum(s for _s, _r, s, *_ in self.qp_solves)
        wall = sum(w for *_r, w in self.qp_solves)
        worst_g = max(g for *_r, g, _w in self.qp_solves)
        cap = sum(1 for st, *_ in self.qp_solves if st == "round_cap")
        return (f"QP (§20c): {len(self.qp_solves)} exact solve(s), "
                + ", ".join(f"{k} x{v}" for k, v in sorted(by.items()))
                + f", {rounds} round(s) / {solves} linear solves, {wall:.2f} s, "
                f"worst |grad| {worst_g:.4g}"
                + (f" — {cap} HIT THE ROUND CAP" if cap else ""))

    def set_exit_line(self) -> str:
        """The exits by kind, worst first — empty when every solve reached
        its fixed point."""
        if not self.set_exits:
            return ""
        by: dict[str, list[int]] = {}
        for why, rnd, _n in self.set_exits:
            by.setdefault(why, []).append(rnd)
        if set(by) == {"same_set"}:
            return ""
        order = ("round_cap", "line_search_stalled", "objective_stalled",
                 "same_set")
        return "active-set exits: " + ", ".join(
            f"{k} x{len(by[k])}" for k in order if k in by)

    def read_hard_set(self, viol: np.ndarray, tol: float,
                      ruling: _t.Callable[[int], str]) -> float:
        """THE HARD SET READ OFF THE SHIPPED SURFACE (owner RULINGS
        2026-09-12u, spec §30 (3b)): the worst violation, whether the set is
        settled, HOW MANY ROWS ARE VIOLATED and the worst row's ruling.

        ``hard_active`` used to be phase C's MULTIPLIER count, taken before
        the final projection — at LEMD it read 1,457 where the surface that
        shipped violated 725.  A count nobody can act on is not an
        instrument.  Returns the worst violation."""
        worst = float(np.max(viol)) if viol.size else 0.0
        self.hard_max_violation_m = worst
        self.hard_settled = not hard_exceeds(worst, tol)
        self.hard_active = int(np.count_nonzero(hard_exceeds(viol, tol)))
        self.hard_worst = "" if self.hard_settled else ruling(int(np.argmax(viol)))
        return worst

    def read_hard_failure(self, hard_i: np.ndarray, viol: np.ndarray,
                          one: list, planar: _t.Any, red: _t.Any,
                          tol: float, z: np.ndarray,
                          limit: int = 12) -> dict[str, _t.Any]:
        """§20a: NAME THE HARD SET'S FAILURE, AND SAY WHETHER THE LAW IS
        INFEASIBLE THERE (lane ``v2settle``; the first-ranked standing debt,
        RULINGS 13y (B) / 13ab / 14as; the brief's (b) "name the pair as a
        CRITICAL and do NOT trade them silently").

        ``HARD SET NOT SETTLED`` named ONE row, by a 70-character slice of
        its ruling.  That is the same instrument §20a already replaced for
        the lag: it cannot say WHICH rows are left, WHERE they are, or —
        the question that decides what to do about them — whether they are a
        residual the solve could still close or a set of rows NO SURFACE
        SATISFIES.  A residual is the solve's problem; an infeasible set is
        the LAW's, and trading one of its rows silently against another is
        exactly what the owner ruled out.

        THE CERTIFICATE.  Around the surviving rows the hard rows that share
        their columns are collected (a bounded flood, ``limit`` hops of
        rows), every column outside that component is held at its shipped
        value, and the small LP ``min Σ s  s.t.  A x - s <= b,  s >= 0`` is
        solved over what is left.  ``Σ s > 0`` at the optimum is a PROOF
        that those rows cannot all hold — the rows carrying slack are the
        infeasible set, named — and ``Σ s = 0`` is a proof that they can,
        which makes the residual the solve's and not the law's.  HiGHS, the
        same solver the projections use.
        """
        bad = np.flatnonzero(hard_exceeds(viol, tol))
        if not bad.size:
            self.hard_failure = {}
            return self.hard_failure

        def _row(i: int) -> dict[str, _t.Any]:
            terms, hi, r = one[int(hard_i[i])]
            val = sum(c * float(z[v]) for v, c in terms)
            return {"row": int(hard_i[i]), "violation_m": round(float(viol[i]), 6),
                    "generator": r.source.generator,
                    "ruling": r.source.ruling[:120],
                    "demanded": round(val, 6), "allowed": round(float(hi), 6),
                    "vertices": [{"v": int(v), "c": float(c),
                                  "lat": planar.vertices[v].key[0],
                                  "lon": planar.vertices[v].key[1]}
                                 for v, c in terms]}

        order = bad[np.argsort(-viol[bad])]
        rows = [_row(int(i)) for i in order[:limit]]
        cert = _infeasible_set(hard_i, bad, one, red, z, limit)
        self.hard_failure = {
            "rows_violated": int(bad.size), "rows": int(hard_i.size),
            "tol_m": tol, "worst_m": round(float(viol[bad].max()), 6),
            "rows_named": rows, "certificate": cert}
        return self.hard_failure

    def hard_failure_line(self) -> str:
        """The named failure, one line (empty where the hard set settled)."""
        f = self.hard_failure
        if not f:
            return ""
        cert = f.get("certificate") or {}
        head = (f"HARD SET NOT SETTLED: {f['rows_violated']} of {f['rows']} hard "
                f"rows over {f['tol_m']} m, worst {f['worst_m']:.4f} m")
        if cert.get("infeasible"):
            head += (f"; CRITICAL — {cert['rows_in_set']} of them are an "
                     f"INFEASIBLE SET: no surface satisfies them together "
                     f"(min total shortfall {cert['total_slack_m']:.4f} m over "
                     f"{cert['columns']} free column(s))")
        elif cert.get("feasible"):
            head += ("; the law IS satisfiable there (min total shortfall "
                     "0.0000 m) — the residual is the solve's, not the law's")
        for r in f["rows_named"][:4]:
            vs = ", ".join(f"v{t['v']} at {t['lat']:.11f},{t['lon']:.11f}"
                           for t in r["vertices"][:3])
            head += (f"; {r['violation_m']:.4f} m on row {r['row']} "
                     f"({r['generator']}: {r['ruling']}) at {vs}")
        return head

    def read_lag_failure(self, ow_i: np.ndarray, move: np.ndarray, tol: float,
                         cap: int, one: list, one_way: dict, planar: _t.Any
                         ) -> dict[str, _t.Any]:
        """§20a: NAME the lag's failure (owner RULINGS 2026-09-13ac).

        ``one_way_max_rounds`` is a SAFETY CEILING, not a schedule: hitting
        it means the leader/follower fixed point did not contract, and the
        augmented-Lagrangian polish that follows is then iterating inside a
        problem that is still moving under it — which is how LEMD's 2-3 cm
        pad-ceiling shortfall crossed ``hard_tol_m`` while the report said
        only ``LAG NOT SETTLED``.

        ``move`` is the last round's per-row leader motion, positionally
        over ``ow_i``.  Records the rows still moving, the worst row's
        generator / ruling, its LEADER vertices (the terms that are not the
        row's ``one_way`` followers) with their canonical lat/lon, and that
        leader's move."""
        if not move.size:
            return self.one_way_failure
        k = int(np.argmax(move))
        row_i = int(ow_i[k])
        _terms, _b, row = one[row_i]
        followers = set(one_way.get(row_i) or ())
        leaders = [v for v, _c in _terms if v not in followers]
        self.one_way_failure = {
            "rounds": self.one_way_rounds, "cap": cap, "tol_m": tol,
            "rows_moving": int(np.count_nonzero(move > tol)),
            "rows": int(move.size),
            "worst_move_m": round(float(move[k]), 6),
            "worst_row": row_i,
            "generator": row.source.generator,
            "ruling": row.source.ruling[:120],
            "leaders": [{"v": v,
                         "lat": planar.vertices[v].key[0],
                         "lon": planar.vertices[v].key[1]} for v in leaders[:4]],
            "followers": sorted(followers)[:4]}
        return self.one_way_failure

    def lag_failure_line(self) -> str:
        """The named failure, one line (empty where the lag settled)."""
        f = self.one_way_failure
        if not f:
            return ""
        led = ", ".join(f"v{r['v']} at {r['lat']:.11f},{r['lon']:.11f}"
                        for r in f["leaders"]) or "(no leader column)"
        return (f"LAG NOT SETTLED after {f['rounds']} of {f['cap']} round(s): "
                f"{f['rows_moving']} of {f['rows']} one-way rows still move "
                f"more than {f['tol_m']} m; worst {f['worst_move_m']:.4f} m on "
                f"row {f['worst_row']} ({f['generator']}: {f['ruling']}), "
                f"leader {led}")

    def as_dict(self) -> dict[str, _t.Any]:
        return {"rounds": self.rounds, "converged": self.converged,
                "set_flips": self.set_flips,
                "set_flip_max_m": round(self.set_flip_max_m, 4),
                "method": self.method, "unknowns": self.unknowns,
                "fixed": self.fixed, "rows": self.rows,
                "triangles": self.triangles, "components": self.components,
                "detached": self.detached,
                "level_belt_rows": self.level_belt_rows,
                "set_exits": [list(e) for e in self.set_exits],
                "qp_solves": [list(e) for e in self.qp_solves],
                "body_datum_rows": self.body_datum_rows,
                "body_datum_bodies": self.body_datum_bodies,
                "body_datums": self.body_datums,
                "taxi_trend": self.taxi_trend,
                "taxi_trend_rows": self.taxi_trend_rows,
                "apron_trend": self.apron_trend,
                "apron_trend_rows": self.apron_trend_rows,
                "bank_rows": self.bank_rows,
                "hard_rows": self.hard_rows, "hard_active": self.hard_active,
                "hard_rounds": self.hard_rounds, "hard_settled": self.hard_settled,
                "hard_max_violation_m": round(self.hard_max_violation_m, 6),
                "hard_worst": self.hard_worst,
                "runway_projection": self.runway_projection.as_dict(),
                "zone_projection": self.zone_projection.as_dict(),
                "one_way_rows": self.one_way_rows,
                "one_way_rounds": self.one_way_rounds,
                "one_way_settled": self.one_way_settled,
                "one_way_move_m": round(self.one_way_move_m, 6),
                "one_way_failure": self.one_way_failure,
                "hard_failure": self.hard_failure,
                "staged": self.staged, "stages": self.stages,
                "stage_dropped_rows": self.stage_dropped_rows,
                "stage1_fixed": self.stage1_fixed,
                "stage1_unlevelled": self.stage1_unlevelled,
                "stage1_wall_s": round(self.stage1_wall_s, 3),
                "stage2_wall_s": round(self.stage2_wall_s, 3),
                "bend_rows_by_class": self.bend_rows_by_class,
                "targets": len(self.targets),
                "solver_wall_s": round(self.solver_wall_s, 3),
                "runway_profile": self.runway_profile,
                "families": self.families, "terms": self.terms,
                "foot_row_diag": self.foot_row_diag}

    def _taxi_trend_line(self) -> str:
        """THE TAXI CHAINS' TREND RESIDUALS (owner RULINGS 2026-09-10v) —
        the worst three chains by |residual|, each with its length."""
        by = self.taxi_trend.get("by_chain") or []
        if not by:
            return ""
        return (" (worst taxi trends " + ", ".join(
            f"{r['max_m']:.2f} m over {r['length_m']:.0f} m" for r in by[:3])
            + ")")

    def _apron_trend_line(self) -> str:
        """THE APRON BODIES' 2-D TREND RESIDUALS (spec §8.7) — the worst
        three bodies by |residual|, each with its plan diameter."""
        by = self.apron_trend.get("by_body") or []
        if not by:
            return ""
        return (" (worst apron trends " + ", ".join(
            f"{r['max_m']:.2f} m over {r['diameter_m']:.0f} m" for r in by[:3])
            + ")")

    def _body_plane_line(self) -> str:
        """THE APRON BODIES' PLANE RESIDUALS — the worst three by the larger
        of |level| and |tilt| (metres of rise over the body's own radius)."""
        bs = sorted(self.body_datums,
                    key=lambda r: -max(abs(r["residual_m"]),
                                       abs(r.get("tilt_m") or 0.0)))[:3]
        if not bs:
            return ""
        return (" (worst body planes " + ", ".join(
            f"level {r['residual_m']:+.2f} / tilt {(r.get('tilt_m') or 0.0):+.2f} m"
            for r in bs) + ")")

    def staged_line(self) -> str:
        """§20b: what the two stages were, in one clause — stage 1's airside
        problem and its hard set, stage 2's size, the substitution, both
        clocks.  Empty when the single solve ran (the DISARM arm)."""
        if not self.staged:
            return ""
        s1 = self.stages.get("stage1") or {}
        return (f"staged (20b): stage 1 AIRSIDE {s1.get('unknowns', 0)} unknowns / "
                f"{s1.get('rows', 0)} rows, {s1.get('hard_active', 0)}/"
                f"{s1.get('hard_rows', 0)} hard violated (max "
                f"{float(s1.get('hard_max_violation_m') or 0.0):.4f} m"
                + (', SETTLED' if s1.get('hard_settled')
                   else ', ' + (s1.get('hard_line') or 'NOT SETTLED')) + "), "
                f"{s1.get('rounds', 0)} round(s), {self.stage1_wall_s:.2f} s, "
                f"{s1.get('one_way_rows', 0)} one-way rows in "
                f"{s1.get('one_way_rounds', 0)} lag round(s) (worst leader move "
                f"{float(s1.get('one_way_move_m') or 0.0):.3f} m"
                + ('' if s1.get('one_way_settled')
                   else ', ' + (s1.get('lag_line') or 'LAG NOT SETTLED')) + "), "
                + (s1.get("projection_line") or "") + "; "
                + f"{self.stage1_fixed} airside vertices SUBSTITUTED into stage 2 "
                f"({self.stage1_unlevelled} unlevelled columns left free, "
                f"{self.stage_dropped_rows} rows foreign to stage 1), stage 2 "
                f"{self.unknowns} unknowns / {self.rows} rows, "
                f"{self.stage2_wall_s:.2f} s; ")

    def line(self) -> str:
        worst = sorted(self.families.items(), key=lambda kv: -kv[1]["max_m"])[:6]
        return (self.staged_line()
                + f"design (08t): {self.rounds} active-set round(s)"
                f"{'' if self.converged else f' (SET NOT SETTLED: {self.set_flips} rows flipped, worst {self.set_flip_max_m:.3f} m)'}, {self.method}, "
                f"{self.unknowns} unknowns / {self.fixed} fixed, {self.rows} rows, "
                f"{self.triangles} triangles in {self.components} complexes "
                f"({self.detached} detached"
                + (f", {self.level_belt_rows} LEVEL-BELT vertices"
                   if self.level_belt_rows else "")
                + (f", {self.set_exit_line()}" if self.set_exit_line() else "")
                + (f", {self.qp_line()}" if self.qp_line() else "")
                + f"), {self.body_datum_bodies} apron bodies on "
                f"their own DEM PLANE ({self.body_datum_rows} rows)"
                + self._body_plane_line()
                + f", {self.taxi_trend_rows} taxi trend rows"
                + self._taxi_trend_line()
                + f", {self.apron_trend_rows} apron trend rows"
                + self._apron_trend_line()
                + f", {self.bank_rows} bank rows off the "
                f"terrain edge, {self.hard_active}/{self.hard_rows} hard rows violated "
                f"(max violation {self.hard_max_violation_m:.4f} m in "
                f"{self.hard_rounds} polish round(s)"
                + (', HARD SET SETTLED' if self.hard_settled
                   else ', ' + (self.hard_failure_line() or 'HARD SET NOT SETTLED'))
                + "), "
                f"{self.one_way_rows} one-way rows in {self.one_way_rounds} lag "
                f"round(s) (worst leader move {self.one_way_move_m:.3f} m"
                + ('' if self.one_way_settled
                   else ', ' + (self.lag_failure_line() or 'LAG NOT SETTLED'))
                + "), "
                f"{self.solver_wall_s:.2f} s solver; "
                + self.runway_projection.line() + "; "
                + self.zone_projection.line() + "; "
                "worst targets " + ", ".join(
                    f"{k} {v['missed']}/{v['rows']} max {v['max_m']:.3f} m"
                    for k, v in worst if v["missed"]))




def residual(cs: ConstraintSet, z: np.ndarray, objective: float) -> Residual:
    """The certificate: the worst residual of each row kind at ``z`` — the
    same reading the LP's certificate carried, now of TARGETS."""
    mp = md = mf = mb = mo = 0.0
    for p in cs.pins:
        mp = max(mp, abs(float(z[p.v]) - p.z))
    for d in cs.diffs:
        # 11j: the row's relief target shifts its zero (``Diff.rel``)
        md = max(md, abs(float(z[d.a]) - float(z[d.b]) - float(getattr(d, "rel", 0.0)))
                 - d.cap * d.d)
    for f in cs.flats:
        g = z[list(f.group)]
        mf = max(mf, float(g.max() - g.min()))
    for bd in cs.bands:
        if bd.lo is not None:
            mb = max(mb, bd.lo - float(z[bd.v]))
        if bd.hi is not None:
            mb = max(mb, float(z[bd.v]) - bd.hi)
    for o in cs.offsets:
        mo = max(mo, o.min_delta - (float(z[o.a]) - float(z[o.b])))
    ml = 0.0
    for ln in cs.linears:
        s = sum(c * float(z[v]) for v, c in ln.terms)
        if ln.hi is not None:
            ml = max(ml, s - ln.hi)
        if ln.lo is not None:
            ml = max(ml, ln.lo - s)
    return Residual(max_pin_m=mp, max_diff_m=max(md, ml), max_flat_m=mf,
                    max_band_m=mb, max_offset_m=mo, objective=objective)


def foot_row_diagnostic(one: _t.Sequence[_t.Any], viol: _t.Sequence[float],
                        idx: _t.Sequence[int],
                        col: _t.Sequence[int]) -> dict[str, _t.Any]:
    """ROUND 8's attribution (owner RULINGS 2026-09-11ab): the foot rows
    were repriced from ``ground_datum`` (3) to ``pad_flat`` (3000) and
    LEMD's missed count barely moved — so the price is not what binds.
    This reads WHAT does, per FOOT (a foot is TWO one-sided rows sharing
    one target), without costing a second solve:

    * the residual distribution — how many feet land inside 0.01 / 0.1 /
      0.3 / 1.0 m of their target;
    * ``feet_no_free_column`` — the foot's triangle is entirely FIXED, so
      no price can move it;
    * ``feet_sharing_a_triangle`` and ``worst_triangle_spread_m`` — two
      feet inside ONE face asking for different levels.  The sheet is
      LINEAR over a triangle: their difference is unpayable at any price.
    """
    feet: dict[tuple, dict[str, _t.Any]] = {}
    for i in idx:
        terms, hi, row = one[i]
        key = (row.source.inputs, tuple(sorted((v, round(abs(c), 9))
                                               for v, c in terms)))
        f = feet.setdefault(key, {"r": 0.0, "z": 0.0, "vs": tuple(
            sorted(v for v, _c in terms))})
        f["r"] = max(f["r"], float(viol[i]))
        if hi >= 0.0:
            f["z"] = float(hi)
    res = sorted(max(0.0, f["r"]) for f in feet.values())
    n = len(res) or 1
    by_tri: dict[tuple, list[float]] = {}
    fixed = 0
    for f in feet.values():
        by_tri.setdefault(f["vs"], []).append(f["z"])
        if all(col[v] < 0 for v in f["vs"]):
            fixed += 1
    shared = sum(len(zs) for zs in by_tri.values() if len(zs) > 1)
    spread = max((max(zs) - min(zs) for zs in by_tri.values() if len(zs) > 1),
                 default=0.0)
    def _q(p: float) -> float:
        return round(res[min(n - 1, int(p * n))], 4) if res else 0.0
    return {"feet": len(feet),
            "within_0.01_m": sum(1 for r in res if r <= 0.01),
            "within_0.1_m": sum(1 for r in res if r <= 0.1),
            "within_0.3_m": sum(1 for r in res if r <= 0.3),
            "within_1.0_m": sum(1 for r in res if r <= 1.0),
            "p50_m": _q(0.5), "p90_m": _q(0.9),
            "max_m": round(res[-1], 4) if res else 0.0,
            "feet_no_free_column": fixed,
            "triangles": len(by_tri),
            "feet_sharing_a_triangle": shared,
            "worst_triangle_spread_m": round(spread, 4)}
