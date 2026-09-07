"""THE LEXICOGRAPHIC BASE SOLVE (RULINGS 2026-09-06x; the law:
``law/emit.toml [objective]``, bound to ``Weights.lexicographic`` by
``pipeline.build.weights_under_law``).

The owner's order (04i: the runway first, terrain never blocks; 06w (2):
the apron preference junior to the runway family's own objective and
senior to the DEM fit) cannot be held by ONE weighted stage: at HECA the
apron preference (18 per metre × hundreds of parallel rows across apron
#364) outweighs the runway fit (20 per metre × a few dozen vertices) and
holds the runway's binding chain at 1.445 % under the allowed 1.5 %
(round 3 of ``apron-route-cap-spec.md``: fully spent, the tier lifts the
chain +0.72 m).  So the order is held LEXICOGRAPHICALLY, the shape of
``stage1.py``'s last resort applied to the hard solve — the SAME rows and
columns ``assemble`` stacks, three objectives in turn on one HiGHS model
(``highspy``; stages B and C start from the previous stage's basis):

* **stage A** — the runway family's terms: the DEM fit of every vertex on
  a ``runway_roles`` face, the smoothness of every ``runway_kinds``
  breakline station (the ridge), and every preference group whose
  prefix is not ``stage_b_prefix`` (crown, end zone, seam, the law
  ladder, the flat-site datum — the groups the single stage already
  ranked ABOVE the runway fit; demoting them would let the runway buy an
  end-zone or seam escalation, which no ruling asked for);
* **stage B** — the ``stage_b_prefix`` preference (the apron's 1 %) alone,
  with every runway-family vertex bounded to its stage-A value ±
  ``hold_m`` (the elevation materiality) and every column stage A charged
  bounded at its stage-A value + ``hold_m`` in its own unit (a fit or
  curvature column in metres, a preference slack in metres over its
  chord) — BOUNDS, never a row: a single dense objective-hold row over
  thousands of columns spanning 20 … 1e5 in coefficient was measured at
  HECA to end stage C in ``kUnknown`` / ``kSolveError`` (696k rows);
* **stage C** — the whole objective (the DEM fit of every other role, its
  smoothness), stage B's columns held likewise.  Holding each column
  rather than the stage's sum is stricter than the lexicographic minimum
  by the tie-break only (a later stage may not redistribute a senior
  stage's relief between rows at equal total) — a per-row hold, which is
  also what the elevation materiality means.

A stage with no charged column is skipped (no aprons: two LPs; no runway:
one).  Stage A infeasible is the hard set's infeasibility (the IIS runs as
before).  A later stage that does not solve — a knife edge like
``highs.RESTATEMENT_MARGIN_M``'s — keeps the previous stage's point and
says so.  ``why`` reads STAGE A's duals: the chain that holds the runway
at its best is stage A's question.

Imports ``model`` and its siblings only (04q-3).
"""
from __future__ import annotations

import dataclasses as _dc
import time
import typing as _t

import numpy as np
import scipy.sparse as sp

from ..model.planar import PlanarMap
from .api import Lexicographic, Options, Weights
from .assemble import Problem, preference_weight

__all__ = ["Stage", "Staged", "partition", "runway_vertices", "solve_stages"]

#: A row's prefix before the first ``:`` (the preference group's).
_SEP = ":"


@_dc.dataclass
class Stage:
    """One stage's record: the objective it minimised at its optimum
    (its OWN cost vector), its wall, HiGHS's status and iterations, the
    number of charged columns and the hold it ran under."""

    name: str
    status: str
    objective: float
    wall_s: float
    iterations: int
    charged: int
    held_vertices: int = 0
    #: the previous stages' columns bounded at their solved values (+ hold)
    held_columns: int = 0


@_dc.dataclass
class Staged:
    """The stages' product: ``x`` the final point (the last stage that
    solved), ``fun`` the whole objective there, ``status`` (``optimal`` /
    ``infeasible`` / ``error`` / ``time_limit``), stage A's point and row
    duals (``why``'s reading), the hold stage B ran under."""

    x: np.ndarray | None
    status: str
    fun: float
    stages: list[Stage]
    x_a: np.ndarray | None = None
    row_dual_a: np.ndarray | None = None
    hold: dict[int, float] = _dc.field(default_factory=dict)
    message: str = ""
    wall_s: float = 0.0

    @property
    def iterations(self) -> int:
        return sum(s.iterations for s in self.stages)


def runway_vertices(planar: PlanarMap, lex: Lexicographic) -> list[int]:
    """Every vertex on a runway-family face (``lex.runway_roles``) — the
    hold set (a vertex with no DEM sample is held too)."""
    return sorted(v for v, vert in planar.vertices.items()
                  if any(planar.faces[f].role in lex.runway_roles for f in vert.incident_faces))


def partition(planar: PlanarMap, prob: Problem, weights: Weights
              ) -> tuple[np.ndarray, np.ndarray, list[int]]:
    """Stage A's and stage B's cost vectors (module docstring), cut from
    ``prob.c``, and the runway vertices stage B/C hold."""
    lex = weights.lexicographic
    assert lex is not None
    rv = runway_vertices(planar, lex)
    c_a = np.zeros_like(prob.c)
    c_b = np.zeros_like(prob.c)
    for v in rv:
        tc = prob.t_col.get(v)
        if tc is not None:
            c_a[tc] = prob.c[tc]
    r0 = prob.n + len(prob.t_col)
    for j, kind in enumerate(prob.station_kinds):
        if kind in lex.runway_kinds:
            c_a[r0 + j] = prob.c[r0 + j]
    for g, col in prob.soft_cols.items():
        if g.partition(_SEP)[0] == lex.stage_b_prefix:
            c_b[col] = prob.c[col]
        else:
            c_a[col] = prob.c[col]
    return c_a, c_b, rv


def _status(highspy, st) -> str:
    S = highspy.HighsModelStatus
    if st == S.kOptimal:
        return "optimal"
    if st in (S.kInfeasible, S.kUnboundedOrInfeasible):
        return "infeasible"
    if st == S.kTimeLimit:
        return "time_limit"
    return f"error:{st}"


def _model(highspy, prob: Problem):
    inf = highspy.kHighsInf
    A = sp.vstack([prob.A_ub, prob.A_eq], format="csc")
    lp = highspy.HighsLp()
    lp.num_col_ = int(A.shape[1])
    lp.num_row_ = int(A.shape[0])
    lp.col_cost_ = np.zeros(A.shape[1])
    lp.col_lower_ = np.array([-inf if lo is None else lo for lo, _ in prob.bounds], float)
    lp.col_upper_ = np.array([inf if hi is None else hi for _, hi in prob.bounds], float)
    lp.row_lower_ = np.concatenate([np.full(prob.A_ub.shape[0], -inf), prob.b_eq])
    lp.row_upper_ = np.concatenate([prob.b_ub, prob.b_eq])
    lp.a_matrix_.format_ = highspy.MatrixFormat.kColwise
    lp.a_matrix_.start_ = A.indptr.astype(np.int32)
    lp.a_matrix_.index_ = A.indices.astype(np.int32)
    lp.a_matrix_.value_ = A.data.astype(float)
    return lp


def solve_stages(planar: PlanarMap, prob: Problem, weights: Weights,
                 options: Options | None = None) -> Staged:
    """The three stages on one HiGHS model (module docstring)."""
    import highspy
    opt = options or Options()
    lex = weights.lexicographic
    assert lex is not None
    t0 = time.perf_counter()
    c_a, c_b, rv = partition(planar, prob, weights)
    plan: list[tuple[str, np.ndarray]] = []
    if np.any(c_a != 0.0):
        plan.append(("A", c_a))
    if np.any(c_b != 0.0):
        plan.append(("B", c_b))
    plan.append(("C", prob.c))
    h = highspy.Highs()
    h.silent()
    if opt.time_limit_s is not None:
        h.setOptionValue("time_limit", float(opt.time_limit_s))
    h.passModel(_model(highspy, prob))
    ncol = int(prob.c.shape[0])
    all_cols = np.arange(ncol, dtype=np.int32)
    lo = np.array([-highspy.kHighsInf if b[0] is None else b[0] for b in prob.bounds], float)
    hi = np.array([highspy.kHighsInf if b[1] is None else b[1] for b in prob.bounds], float)
    # the hold of a charged column in ITS unit: a fit / curvature column is
    # metres; a preference slack is a grade over its chord metres (its
    # charge is weight × chord metres), so ``hold_m`` of relief is
    # ``hold_m / chord`` of grade
    unit = np.ones(ncol)
    for g, col in prob.soft_cols.items():
        per_m = preference_weight(g, weights) * (1.0 if g.startswith("law:") else prob.fit_scale)
        chord = prob.c[col] / per_m if per_m > 0.0 else 0.0
        unit[col] = 1.0 / chord if chord > 0.0 else 1.0
    out = Staged(None, "error", float("nan"), [])
    prev_cost: np.ndarray | None = None
    prev_x: np.ndarray | None = None
    for name, cost in plan:
        st = Stage(name, "", float("nan"), 0.0, 0, int(np.count_nonzero(cost)))
        changed = False
        if prev_cost is not None and prev_x is not None:
            # hold every column the previous stage charged at its value
            nz = np.flatnonzero(prev_cost)
            hi[nz] = np.minimum(hi[nz], prev_x[nz] + lex.hold_m * unit[nz])
            st.held_columns = int(len(nz))
            changed = True
        if name == "B" and out.x_a is not None:
            for v in rv:
                lo[v] = max(lo[v], out.x_a[v] - lex.hold_m)
                hi[v] = min(hi[v], out.x_a[v] + lex.hold_m)
            st.held_vertices = len(rv)
            changed = True
        if changed:
            h.changeColsBounds(ncol, all_cols, lo.astype(float), hi.astype(float))
        h.changeColsCost(ncol, all_cols, cost.astype(float))
        if not lex.warm_start:
            h.clearSolver()
        t = time.perf_counter()
        h.run()
        st.wall_s = time.perf_counter() - t
        st.status = _status(highspy, h.getModelStatus())
        st.iterations = int(h.getInfo().simplex_iteration_count)
        out.stages.append(st)
        if st.status not in ("optimal",):
            if out.x is None:
                out.status = st.status
                out.message = f"stage {name} ended {st.status}"
                break
            out.status = "feasible"
            out.message += f"; stage {name} ended {st.status} — stage {plan[len(out.stages) - 2][0]}'s point kept"
            break
        sol = h.getSolution()
        x = np.asarray(sol.col_value, float)
        st.objective = float(cost @ x)
        out.x, out.status, out.fun = x, "optimal", float(prob.c @ x)
        if name == "A":
            out.x_a = x.copy()
            out.row_dual_a = np.asarray(sol.row_dual, float)
            out.hold = {v: float(x[v]) for v in rv}
        prev_cost, prev_x = cost, x
    if out.x_a is None and out.x is not None and out.status == "optimal":
        # no stage A ran (no runway family): the single stage's duals are the reading
        out.x_a = out.x
        out.row_dual_a = np.asarray(h.getSolution().row_dual, float)
    out.wall_s = time.perf_counter() - t0
    if not out.message:
        out.message = "lexicographic " + " ".join(
            f"{s.name}:{s.status}[{s.wall_s:.1f}s,{s.iterations}it]" for s in out.stages)
    return out
