"""THE FINAL PROJECTION — the runway family's hard rows enforced EXACTLY
(owner RULINGS 2026-09-09y, closing 09v (3); spec
``docs/specs/auto-patch-v2/design-surface-spec.md`` §14).

The design solve prices the runway family's laws as an AUGMENTED
LAGRANGIAN: a constraint weight plus a multiplier loop.  Measured on real
airports at every weight (09r (3) / 09v), the multiplier sequence does not
converge — it oscillates while the one-sided active set re-forms under it —
so the solve ships a residual it cannot certify, and at HECA on 09y that
residual landed on RUNWAY rows: ``runway_transverse`` 1 (0.50 m) and
``runway_vertical_curve`` 4 (0.24-0.33 m), which the app's DEFECT gate
refuses.

So the runway family is settled by a SECOND, TINY problem after the design
solve, not by a better penalty:

    minimise  Σ_v (z_v − z_design_v)²        over the RUNWAY-FAMILY vertices
    subject to  every runway-family HARD row as a TRUE constraint
                (threshold pins are already fixed vertices, so they hold
                 exactly; transverse/crown, the vertical curve K, the
                 runway's max grade and the 5 % pavement ceiling are
                 inequalities)

with EVERY OTHER VERTEX FIXED at the value the design solve gave it.  A row
that couples a runway vertex to a fixed non-runway vertex keeps the fixed
value on its own side (it moves into the right-hand side); a hard row with
no free column at all constrains nothing here and is dropped — it is not
this projection's business, and it is not a runway DEFECT family either.

THE SET (stated, because everything else is fixed against it): the ring and
hole vertices of every face whose role is in
``law.tables.precedence.runway_family.members`` (``runway`` and
``runway_crossing``), plus the vertices of every ``runway_profile``
breakline — the RIDGE, which the vertical-curve and transverse readers both
read.  A reduced COLUMN is free only when EVERY vertex mapped to it lies in
that set: a ``Flat`` group straddling the boundary is one rigid unknown and
moving it would move pavement outside the family.

The DEFECT readers (``verify/runway.runway_transverse`` /
``runway_vertical_curve``) then read 0 BY CONSTRUCTION: the generator's hard
rows and those readers are twins of one law.  The surrounding sheet's rows
on runway vertices (strip ties, contact chains) are re-evaluated as report
figures only — the design report's family table is read AFTER the
projection.

TWO DEVIATIONS FROM THE RULING'S LETTER, both measured, both REPORTED for
the owner rather than decided here:

1. THE BAR IS THE LAW'S OWN "HELD", NOT ZERO.  The constraint is
   ``row ≤ bound + [design] hard_tol_m`` (0.02 m of surface), which is the
   law's own definition of a held row — under the census's per-node
   rounding envelope (``instrument.rounding_noise_m`` 0.03) and far under
   the rate readers' quantum (``coarse_noise_m`` 0.1), so a row held there
   can mint no DEFECT row.  Projecting to EXACT zero buys no reading and
   costs surface: measured at CYXY, where the design solve leaves 0.027 m
   and the DEFECT readers already read 0, the exact projection pulled the
   runway 2.16 m and took the census from 428 rows to 464.  At the held bar
   the same airport moves 0.038 m.
2. A COUPLED ROW THE PROJECTION'S OWN FIXING MADE INFEASIBLE IS WITHDRAWN.
   A row tying a runway vertex to a NON-runway vertex is solvable in the
   design solve, where both feet move, and can be unsolvable here.  The
   conflicting rows are found by an LP (:func:`_relax_lp`) and withdrawn by
   name-count in the report; every row whose feet are all inside the family
   stays a TRUE constraint, so the DEFECT families still read 0.  At CYXY
   and HECA under deviation 1 this arm does not run at all.
"""
from __future__ import annotations

import dataclasses as _dc
import time
import typing as _t

import numpy as np
import scipy.sparse as sp

from ..law import Law
from ..law.tables import design as design_law
from ..model.planar import PlanarMap
from .rows import _law_sides, _one_matrix, _Reduction, _Side, _violation

__all__ = ["ProjectionReport", "runway_family_vertices", "free_columns",
           "project_runway", "runway_profile_block"]

#: The ridge: the breakline kind the runway profile (and the census's own
#: ``crown_spine``) is carried on.
RIDGE_KIND = "runway_profile"


@_dc.dataclass
class ProjectionReport:
    """What the final projection did — the report's ``runway_projection``
    block (owner RULINGS 2026-09-09y: "the report gains
    ``runway_projection`` (rows, max move, wall)")."""

    #: ``false`` only on the diagnostic arm (``[design] runway_projection``)
    ran: bool = False
    #: the runway-family vertices and the free columns they reduce to
    vertices: int = 0
    columns: int = 0
    #: the hard rows the projection constrains, and how many of those couple
    #: a free runway vertex to a FIXED foot outside the family
    rows: int = 0
    coupled_rows: int = 0
    #: hard rows the law states as EQUALITIES (``lo == hi``) — none today
    equalities: int = 0
    #: the worst hard-row violation BEFORE and AFTER (metres of surface)
    before_m: float = 0.0
    after_m: float = 0.0
    #: the worst left on a row whose feet are ALL inside the runway family —
    #: the DEFECT families' own population, 0 by construction
    after_family_m: float = 0.0
    #: THE ACTIVE NEIGHBOURHOOD: the rows the QP was actually solved over
    #: and how many cutting-plane rounds it took to close on the full set
    cut_rows: int = 0
    cut_rounds: int = 0
    #: the ELASTIC ARM (a coupled row the projection's own fixing made
    #: infeasible): how many rows were given slack, and the worst slack taken
    elastic_rows: int = 0
    elastic_slack_m: float = 0.0
    #: the largest |z − z_design| the projection paid for it
    max_move_m: float = 0.0
    wall_s: float = 0.0
    #: ``optimal`` / ``skipped`` (nothing to do) / the solver's own status
    #: word when it is neither — a NAMED failure, never a silent pass
    status: str = "skipped"

    def as_dict(self) -> dict[str, _t.Any]:
        return {"ran": self.ran, "vertices": self.vertices,
                "columns": self.columns, "rows": self.rows,
                "coupled_rows": self.coupled_rows,
                "equalities": self.equalities,
                "before_m": round(self.before_m, 6),
                "after_m": round(self.after_m, 6),
                "after_family_m": round(self.after_family_m, 6),
                "cut_rows": self.cut_rows, "cut_rounds": self.cut_rounds,
                "elastic_rows": self.elastic_rows,
                "elastic_slack_m": round(self.elastic_slack_m, 6),
                "max_move_m": round(self.max_move_m, 6),
                "wall_s": round(self.wall_s, 3), "status": self.status}

    def line(self) -> str:
        if not self.ran:
            return f"runway projection (09y): {self.status}"
        return (f"runway projection (09y): {self.rows} hard rows "
                f"({self.coupled_rows} coupled to fixed feet; {self.cut_rows} "
                f"solved in {self.cut_rounds} cut round(s)) over "
                f"{self.columns} free columns / {self.vertices} runway "
                f"vertices, worst hard row {self.before_m:.4f} -> "
                f"{self.after_m:.6f} m (family rows {self.after_family_m:.6f}"
                + (f", {self.elastic_rows} elastic, worst slack "
                   f"{self.elastic_slack_m:.4f} m" if self.elastic_rows else "")
                + f"), max move {self.max_move_m:.3f} m, "
                f"{self.wall_s:.2f} s ({self.status})")


def runway_family_vertices(planar: PlanarMap, law: Law) -> set[int]:
    """THE SET (module docstring): every ring and hole vertex of a
    runway-family face, plus every ``runway_profile`` breakline vertex."""
    members = set(law.tables.precedence.runway_family.members)
    out: set[int] = set()
    for f in planar.faces.values():
        if f.role not in members:
            continue
        for ring in (f.ring, *f.holes):
            out.update(planar.ring_vertices(ring))
    for b in planar.breaklines.values():
        if b.kind == RIDGE_KIND:
            out.update(b.vertices(planar))
    return out


def free_columns(red: _Reduction, vertices: _t.AbstractSet[int]) -> np.ndarray:
    """The reduced columns the projection may move: a column is free only
    when EVERY vertex mapped to it lies in ``vertices`` (a ``Flat`` group
    straddling the family's boundary is one rigid unknown, and moving it
    would move pavement the projection has fixed)."""
    free = np.zeros(red.n_cols, dtype=bool)
    seen = np.zeros(red.n_cols, dtype=bool)
    for v in range(len(red.col)):
        c = int(red.col[v])
        if c < 0:
            continue
        if v in vertices:
            if not seen[c]:
                seen[c] = True
                free[c] = True
        else:
            free[c] = False
    return free


def _scaled(A: sp.csr_matrix, b: np.ndarray, sel: np.ndarray
            ) -> tuple[sp.csr_matrix, np.ndarray]:
    """The selected rows in METRES of surface: a law row is stated in its
    own units (a Δz row in metres, a vertical-curve row in grade change, a
    rate row in curvature), so each row and its target are divided by
    ``Σ|c| / 2`` — the same normalisation the design solve's hard rows
    carry, so "0.02 m" means one thing in both places."""
    As = A[sel]
    rowsum = np.asarray(abs(As).sum(axis=1)).ravel()
    sc = np.ones(As.shape[0])
    good = rowsum > 0.0
    sc[good] = 2.0 / rowsum[good]
    return (sp.diags(sc) @ As).tocsr(), sc * b[sel]


#: THE ACTIVE NEIGHBOURHOOD: a row further inside its bound than this
#: cannot bind a minimum-change projection, so the first QP is solved
#: without it and the loop adds back anything the answer actually violates
#: (exact on termination — a relaxation whose optimum is feasible for the
#: full problem IS its optimum).  Measured at HECA: 1.00 m keeps 12,641 of
#: 17,062 rows and closes in one round.  Solver constants, not law values.
_NEAR_M = 0.25
_CUT_ROUNDS_MAX = 8
#: a row the answer violates by more than this is ADDED to the neighbourhood
_FEAS_M = 1.0e-6
#: ...and the projection has CLOSED when no row is out by more than this —
#: HiGHS's own primal feasibility is asked for at ``_PRIMAL_TOL`` and lands
#: a little above it on a real airport (measured CYXY: a few times 1e-6),
#: so the closure test carries two decades of headroom and still sits 100x
#: under the elevation materiality (0.01 m) and 300x under the census's
#: rounding envelope (0.03 m).  A row held here can mint no defect row.
_CLOSED_M = 1.0e-4
_PRIMAL_TOL = 1.0e-9

#: The right-hand side a WITHDRAWN row takes (the elastic arm): unreachable,
#: so the row constrains nothing while its columns keep every other row they
#: carry.  A solver constant, not a law value.
_DROPPED_BOUND = 1.0e6


def _qp(A: sp.csr_matrix, rhs: np.ndarray, x0: np.ndarray, w: np.ndarray,
        verbose: bool = False) -> tuple[np.ndarray, str]:
    """``min Σ w (x − x0)²  s.t.  A x ≤ rhs`` through HiGHS's QP.  Returns
    ``(x, "optimal")`` or ``(x0, status word)``."""
    import highspy
    inf = highspy.kHighsInf
    h = highspy.Highs()
    h.setOptionValue("output_flag", bool(verbose))
    h.setOptionValue("primal_feasibility_tolerance", _PRIMAL_TOL)
    m, n = A.shape
    h.addVars(n, np.full(n, -inf), np.full(n, inf))
    h.changeColsCost(n, np.arange(n, dtype=np.int32), -2.0 * w * x0)
    h.addRows(m, np.full(m, -inf), rhs, int(A.nnz),
              A.indptr[:-1].astype(np.int32), A.indices.astype(np.int32), A.data)
    # ``0.5 xᵀQx + cᵀx`` with a DIAGONAL ``Q = 2w`` is ``Σ w (x−x0)²`` up to
    # a constant
    h.passHessian(n, n, highspy.MatrixFormat.kColwise,
                  np.arange(n + 1, dtype=np.int32),
                  np.arange(n, dtype=np.int32), 2.0 * w)
    rc = h.run()
    st = h.getModelStatus()
    if st != highspy.HighsModelStatus.kOptimal:
        return x0, f"{h.modelStatusToString(st)} [rc {rc}, {m} rows x {n} columns]"
    return np.asarray(h.getSolution().col_value, float)[:n], "optimal"


def _relax_lp(A: sp.csr_matrix, rhs: np.ndarray, elastic: np.ndarray,
              verbose: bool = False) -> tuple[np.ndarray, str]:
    """The LEAST TOTAL RELAXATION of the ``elastic`` rows' bounds that makes
    ``A x ≤ rhs`` solvable: an LP in ``(x, s)`` minimising ``Σ s`` with
    ``A x − s ≤ rhs`` and ``s ≥ 0`` on those rows only.  Returns the
    per-row relaxation (0 everywhere else).

    Why an LP and not slack columns inside the QP: HiGHS's active-set QP
    ERRORS on the elastic model (measured at CYXY — "Non-convex" with a
    semi-definite Hessian, "Unbounded" with a tiny one, an internal error
    with a unit one), while its LP solves the same feasibility question
    without complaint.  The QP then runs on the shape it does handle: the
    original rows with the relaxed right-hand side and no extra columns."""
    import highspy
    inf = highspy.kHighsInf
    m, n = A.shape
    ns = int(elastic.sum())
    if not ns:
        return np.zeros(m), "optimal"
    S = sp.csr_matrix((-np.ones(ns), (np.flatnonzero(elastic), np.arange(ns))),
                      shape=(m, ns))
    M = sp.hstack([A, S], format="csr")
    h = highspy.Highs()
    h.setOptionValue("output_flag", bool(verbose))
    h.addVars(n + ns, np.concatenate([np.full(n, -inf), np.zeros(ns)]),
              np.full(n + ns, inf))
    h.changeColsCost(n + ns, np.arange(n + ns, dtype=np.int32),
                     np.concatenate([np.zeros(n), np.ones(ns)]))
    h.addRows(m, np.full(m, -inf), rhs, int(M.nnz),
              M.indptr[:-1].astype(np.int32), M.indices.astype(np.int32), M.data)
    h.run()
    st = h.getModelStatus()
    if st != highspy.HighsModelStatus.kOptimal:
        return np.zeros(m), str(h.modelStatusToString(st))
    sv = np.asarray(h.getSolution().col_value, float)[n:]
    out = np.zeros(m)
    out[elastic] = np.maximum(sv, 0.0)
    return out, "optimal"


def project_runway(planar: PlanarMap, law: Law, base: _t.Any, x: np.ndarray,
                   *, stacked: tuple[sp.csr_matrix, np.ndarray] | None = None,
                   verbose: bool = False) -> tuple[np.ndarray, ProjectionReport]:
    """Project the design solve's ``x`` onto the runway family's hard rows
    (module docstring).  Returns the projected column vector and the report;
    on anything but an optimal QP the DESIGN vector is returned unchanged
    with the solver's status named — never a silently worse surface.

    ``stacked`` is the design solve's OWN ``(A1, b1)`` — the one-sided rows
    over the reduced columns, hard rows already divided into metres of
    surface.  Re-assembling it here costs 4.5 s at HECA (234,850 rows) for a
    matrix the caller is holding, so the pipeline hands it over; a caller
    with none (a twin, a replay) passes nothing and it is rebuilt.  The
    one-way SPLIT the design solve applies to that matrix never touches a
    hard row (no hard ruling head is a one-way head), so the two readings
    are the same matrix on this population."""
    rep = ProjectionReport()
    t0 = time.perf_counter()
    if not bool(design_law(law).runway_projection):
        rep.status = "off (law [design] runway_projection = false)"
        return x, rep
    red: _Reduction = base.red
    one: list[_Side] = base.one
    hard = np.asarray(base.hard, dtype=np.int64)
    if not hard.size or red.n_cols == 0:
        return x, rep
    S = runway_family_vertices(planar, law)
    rep.vertices = len(S)
    free = free_columns(red, S)
    rep.columns = int(free.sum())
    if not rep.columns:
        return x, rep

    # THE LAW'S OWN EQUALITIES (``lo == hi``) whose ruling head is hard: the
    # generator states none today (the runway family's rows are all
    # two-sided bands, and the threshold pins are FIXED vertices, not rows),
    # but a future one would be a hard row this projection must hold, so it
    # is stated here rather than assumed away.  ``rep.equalities`` names how
    # many were found.
    heads = frozenset(design_law(law).hard_rulings)
    eq_sides = [s for s in base.eqs
                if s[2].source.ruling.split(" (")[0].strip() in heads]
    one_all = list(one)
    eq_i: list[int] = []
    for terms, hi, row in eq_sides:
        eq_i.append(len(one_all))
        one_all.append((terms, hi, row))
        one_all.append((tuple((v, -c) for v, c in terms), -float(hi), row))
    rep.equalities = len(eq_sides)
    if eq_i:
        hard = np.concatenate([hard, np.asarray(
            [k for i in eq_i for k in (i, i + 1)], dtype=np.int64)])
        one = one_all

    if stacked is not None and not eq_i:
        A1, b1 = stacked
        Ah, bh = A1[hard], b1[hard]
    else:
        A1, b1 = _one_matrix(one, red)
        Ah, bh = _scaled(A1, b1, hard)
    # the rows this projection OWNS: those carrying at least one free column
    touch = np.asarray((abs(Ah)[:, free] > 0).sum(axis=1)).ravel()
    sel = np.flatnonzero(touch > 0)
    if not sel.size:
        return x, rep
    Ah, bh = Ah[sel], bh[sel]
    fixed = ~free
    n_free = np.asarray((abs(Ah)[:, free] > 0).sum(axis=1)).ravel()
    n_all = np.asarray((abs(Ah) > 0).sum(axis=1)).ravel()
    rep.rows = int(Ah.shape[0])
    rep.coupled_rows = int(np.count_nonzero(n_free < n_all))
    # a row's FIXED feet keep the design solve's value: they move to the
    # right-hand side, exactly as a pinned vertex already does
    # THE BAR IS THE READER'S, NOT ZERO (deviation, reported — see the
    # module docstring's last paragraph): the constraint is the law's own
    # definition of HELD, ``row ≤ bound + [design] hard_tol_m`` (0.02 m of
    # surface, under the census's per-node rounding envelope of 0.03 and far
    # under the rate readers' 0.1 quantum), so a held row can mint no DEFECT
    # row.  Projecting to EXACT zero instead buys no reading and costs
    # surface: measured at CYXY, a 0.027 m residual — already inside the
    # envelope, already DEFECT-free — pulled the runway 2.16 m and took the
    # census from 428 rows to 464.
    held = float(design_law(law).hard_tol_m)
    rhs = bh + held - np.asarray(Ah[:, fixed] @ x[fixed]).ravel()
    Ar = Ah[:, free].tocsr()
    x0 = x[free]
    # reported against the LAW's own bound, never the held bar
    rep.before_m = float(np.max(np.maximum(Ar @ x0 - rhs + held, 0.0)))

    # NOTHING TO SETTLE: the design solve already holds every row of this
    # family at the law's HELD bar, so the projection IS the identity and the
    # QP is not built at all (measured at OTHH, where the hard set settles on
    # its own: 4.45 s of solver for a max move of 0.000 m).
    if float(np.max(Ar @ x0 - rhs)) <= 0.0:
        rep.after_m = rep.before_m
        rep.ran = True
        rep.status = "held by the solve (nothing to settle)"
        rep.wall_s = time.perf_counter() - t0
        if verbose:
            print("    " + rep.line())
        return x, rep

    # the WEIGHT of a column is how many vertices it carries: the objective
    # is Σ over VERTICES of (z − z_design)², and a Flat group is one column
    # standing for many vertices
    cnt = np.zeros(red.n_cols)
    cols = red.col[red.col >= 0]
    np.add.at(cnt, cols.astype(np.int64), 1.0)
    w = np.maximum(cnt[free], 1.0)

    coupled = n_free < n_all
    # THE ACTIVE NEIGHBOURHOOD (a cutting plane, exact on termination).  Of
    # the 17,062 rows HECA's runway family carries, all but a few hundred sit
    # metres inside their bound and no minimum-change projection can bring
    # them to it.  The QP is solved over the rows within ``_NEAR_M`` of their
    # bound, then EVERY row is re-read: any row the answer violates is added
    # and the QP re-solved.  The loop ends when the full population is
    # satisfied, so the result is the same point the all-rows QP gives —
    # measured at HECA, in a fraction of the time.
    near = (Ar @ x0 - rhs) > -_NEAR_M
    xf, st = np.asarray(x0), "optimal"
    for _round in range(_CUT_ROUNDS_MAX):
        rep.cut_rounds += 1
        xf, st = _qp(Ar[near], rhs[near], x0, w, verbose)
        if st != "optimal":
            break
        add = ((Ar @ xf - rhs) > _FEAS_M) & ~near
        if not add.any():
            break
        near |= add
    rep.cut_rows = int(near.sum())
    if st == "optimal" and (np.max(Ar @ xf - rhs) > _CLOSED_M):
        st = "cutting plane did not close"           # fall through to the full QP
    if st != "optimal":
        xf, st = _qp(Ar, rhs, x0, w, verbose)
    if st != "optimal":
        # THE COUPLED ROWS CAN BE INFEASIBLE, AND THAT IS THE PROJECTION'S
        # OWN DOING (measured on the ``ridge`` fixture with a 4 m ridge
        # kink): a row that ties a runway vertex to a NON-runway vertex is
        # solvable in the design solve, where both feet move, and can be
        # unsolvable here, where this projection has just fixed one of them.
        # A refusal would ship the runway DEFECTs the projection exists to
        # remove, so the second arm gives those rows — and ONLY those — an
        # elastic slack at a large LINEAR penalty (exact-penalty: the slack
        # is 0 wherever the hard problem is feasible).  Every row whose feet
        # are all inside the family stays a TRUE constraint, so the DEFECT
        # families still read 0 by construction; the report names the arm
        # and the worst slack.  A second failure returns the design surface
        # unchanged with the solver's own word.
        slack, st_lp = _relax_lp(Ar, rhs, coupled, verbose)
        if st_lp != "optimal":
            st = f"{st} / the relaxation LP: {st_lp}"
        else:
            # THE CONFLICT IS A SET OF ROWS, NOT A BUDGET.  Relaxing every
            # coupled row's bound BY the LP's own slack vector solves a
            # different problem — the LP minimises total slack with no regard
            # for distance, and the QP under its corner moved CYXY 2.29 m.
            # The rows the LP has to give slack to are the conflict itself
            # (CYXY: 18 of 826), so those rows — and only those — are
            # WITHDRAWN from this projection and reported by count and by the
            # size of the conflict; every other row stays a true constraint
            # and the QP is again the minimum change.
            drop = slack > _FEAS_M
            rep.elastic_rows = int(drop.sum())
            rep.elastic_slack_m = float(slack.max())
            r2 = rhs.copy()
            r2[drop] = _DROPPED_BOUND
            xf, st = _qp(Ar, r2, x0, w, verbose)
            if st == "optimal":
                st = "optimal (elastic on the coupled rows)"
    rep.wall_s = time.perf_counter() - t0
    if not st.startswith("optimal"):
        rep.status = st
        rep.after_m = rep.before_m
        if verbose:
            print(f"    [design/project] NOT OPTIMAL: {rep.status}")
        return x, rep
    out = x.copy()
    out[free] = xf
    v = Ar @ xf - rhs + held
    rep.after_m = float(np.max(np.maximum(v, 0.0)))
    inner = ~coupled
    rep.after_family_m = (float(np.max(np.maximum(v[inner], 0.0)))
                          if inner.any() else 0.0)
    rep.max_move_m = float(np.max(np.abs(xf - x0))) if xf.size else 0.0
    rep.status = st
    rep.ran = True
    rep.wall_s = time.perf_counter() - t0
    if verbose:
        print("    " + rep.line())
    return out, rep


# ── THE RUNWAY PROFILE BLOCK (spec §21.2 (4)) ───────────────────────────

def runway_profile_block(planar: PlanarMap, law: Law, airport,
                         cs, z: _t.Sequence[float]) -> dict[str, _t.Any]:
    """THE REPORT NAMES THE RESIDUAL PER RUNWAY (spec §21.2 (4)).

    "The final projection (§16) still settles the family exactly; a target
    the laws refuse is simply not reached, and the report names the
    residual per runway."  Per runway with a target profile:

    * ``kind`` — ``trend`` or the ``chord`` fallback, and the window;
    * ``target_rms_m`` / ``target_max_m`` — the BUILT ridge against the
      target it was given, the §21.4 twin's own bar;
    * ``dem_mean_abs_m`` — mean |z − DEM| along the ridge, the SPJC bar
      (2.14 m on the straight chord);
    * ``chord_bow_m`` — the built ridge's worst fall under the STRAIGHT
      threshold chord, kept for continuity with every earlier round's bow;
    * ``binding`` / ``binding_slack_m`` — the law row with the least slack
      among the rows whose feet ALL lie on this runway's ridge: what the
      surface is held by where it does not reach its target.

    Reads only what the pipeline already has (the constraint set and the
    solved z); mints nothing.
    """
    from ..constraints.runway_chord import _chords, _with_knots, runway_crossings
    from ..constraints.runway_profile import ridge_chains
    from ..constraints.precedence import view
    vw = view(planar, law)
    chains = ridge_chains(vw)
    straight, n_without = _chords(planar, law, airport)
    chords = _with_knots(straight, runway_crossings(planar, law, airport, straight))
    # the least-slack law row per runway ridge (the binding law)
    one, eq = _law_sides(cs)
    zz = np.asarray(z, dtype=float)
    ridge_of: dict[int, str] = {}
    for r, chs in chains.items():
        for ch in chs:
            for v in ch:
                ridge_of[v] = r
    worst: dict[str, tuple[float, str]] = {}
    for side in one:
        terms, _hi, row = side
        rs = {ridge_of.get(v) for v, _c in terms}
        if len(rs) != 1 or None in rs:
            continue
        r = rs.pop()
        slack = -_violation(side, zz)
        if r not in worst or slack < worst[r][0]:
            worst[r] = (slack, row.source.ruling)
    out: list[dict[str, _t.Any]] = []
    for r, c in sorted(chords.items()):
        ridge = sorted({v for ch in chains.get(r, []) for v in ch},
                       key=lambda q: c.station(*vw.xy[q]))
        if not ridge:
            continue
        d2 = t_max = 0.0
        dem_abs: list[float] = []
        bow = 0.0
        for v in ridge:
            s = c.station(*vw.xy[v])
            d = float(zz[v]) - c.z(s)
            d2 += d * d
            t_max = max(t_max, abs(d))
            bow = min(bow, float(zz[v]) - c.straight_z(s))
            dem = planar.vertices[v].dem_z
            if dem is not None:
                dem_abs.append(abs(float(zz[v]) - float(dem)))
        wr = worst.get(r)
        out.append({
            "runway": r, "kind": c.kind,
            "window_m": round(float(law.tables.emit.design.runway_profile_window_m), 1),
            "stations": len(ridge),
            "target_rms_m": round((d2 / len(ridge)) ** 0.5, 4),
            "target_max_m": round(t_max, 4),
            "dem_mean_abs_m": round(sum(dem_abs) / len(dem_abs), 4) if dem_abs else None,
            "chord_bow_m": round(bow, 3),
            "binding": wr[1] if wr else "",
            "binding_slack_m": round(wr[0], 4) if wr else None,
        })
    return {"runways": out, "runways_without_pins": n_without,
            "window_m": round(float(law.tables.emit.design.runway_profile_window_m), 1)}
