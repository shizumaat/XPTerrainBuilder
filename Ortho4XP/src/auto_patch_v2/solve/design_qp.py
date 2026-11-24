"""§20c THE ONE-SIDED PROBLEM SOLVED AS A CONVEX QP (Fable 2026-09-14,
RULINGS 2026-09-14bw) — ``[design] solver = "qp"``.

THE PROBLEM.  The design surface minimises

    F(x) = ‖A₀x − b₀‖² + ‖Ux − c‖² + Σ_i w_i · max(0, a_i·x − b̃_i)²

over the reduced columns — a CONVEX, C¹, piecewise-quadratic function (a
convex QP in ``(x, s)`` with ``s_i ≥ max(0, a_i·x − b̃_i)``).  Its minimum
is what the design surface IS; every consumer downstream reads it.

WHAT SHIPS TODAY (``solver = "fixed_point"``) DOES NOT REACH IT.  The
damped active-set iteration in ``design._solve_stage`` takes the UNDAMPED
minimiser of the current active set's subproblem and line-searches along
the ray from the previous iterate.  MEASURED on the registered CYXY
capture (lane ``v2qp``): that subproblem minimiser sits at ``F = 7.6e8``
against ``F = 1.9e5`` at the iterate it was taken from — the ray is
useless, the backtracking collapses to the floor, and the iteration exits
``line_search_stalled`` / ``objective_stalled`` (RULINGS 14bw: all six
HECA solves, never ``same_set``).  The surface it returns is **1.489 %
above the minimum of its own objective**, and 707 of 4,437 CYXY columns
stand more than 0.02 m off it (worst 0.586 m).  A point that is not the
minimum has no reason to be stable: perturb the problem and the next
not-quite-minimum lands somewhere else, which is exactly 14bw's far field.

THE STEP THAT DOES REACH IT.  Damp the SAME subproblem instead of
line-searching a ray out of it — solve

    min ‖A₀x − b₀‖² + ‖Ux − c‖² + Σ_{i active} w_i (a_i·x − b̃_i)²
        + λ‖x − x_k‖²

(a proximal / Levenberg-Marquardt term, ONE extra diagonal block on the
same stack, through the same :func:`linear._linear_solve`), accept it when
F decreases and divide λ by four, multiply λ by six and retry when it does
not.  λ → 0 near the solution, so the tail is the undamped semismooth
Newton step and converges superlinearly; λ → ∞ is a gradient step, so
descent is always available while ``F`` is above its minimum.

MEASURED (CYXY, the same capture): 52 iterations, 94 linear solves,
**1.2 s** — against the 3.2 s the stalling iteration costs — reaching
``F = 190617.9104`` where the fixed point returns ``193499.2357``.  An
INDEPENDENT accelerated proximal gradient (FISTA with function restart,
20,000 iterations, 9 s) from the same start reaches ``190618.15`` — above
this one and converging to it, which is the cross-check that this is the
minimum and not another stall.

WHY NOT HiGHS (a DEVIATION from §20c's text, reported not decided).  The
spec names ``highspy``'s QP, which §30 (3)/§32 (4)'s projections already
use.  MEASURED, both textbook forms of this QP (epigraph variables for
every residual row; and the normal-equation Hessian with L2 slacks for the
one-sided rows and L1-elastic slacks for the hard rows): HiGHS's QP solver
is a DENSE-NULLSPACE active-set method — ``ERROR: QP solver has exceeded
nullspace limit of 4000``, "Large nullspace", ``Solve error`` — because
the nullspace dimension of this problem is its free-column count (4,437 at
CYXY, ~32,000 at HECA), and the limit's cost is quadratic in that
dimension.  Raised to 200,000 it ran 630 s at CYXY WITHOUT terminating
(objective flat from ~230 s, nullspace dimension still climbing) against
the 3.2 s solve it replaces — 190x on the CHEAPEST airport in the battery.
The projections stay on HiGHS because their QPs are small by construction
(``project_runway``: 993 free columns at CYXY, and nearly every row
active).  The whole-airport design problem is not that shape.  What ships
here is the same convex QP, solved exactly, by the module's own linear
algebra.
"""
from __future__ import annotations

import time
import typing as _t
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import scipy.sparse as sp

# §20c: the projections' solver, imported AT MODULE TOP.  A third-party
# import inside a function is invisible to PyInstaller and to the suite
# (memory ``frozen-engine-lazy-imports``: ``highspy`` 2026-09-10 shipped a
# frozen engine that died on a lazy import nothing had exercised).  It is
# imported here because this module is §20c's site even though the measured
# solver below is the module's own — see the docstring's deviation.
import highspy  # noqa: F401

from .fill_order import ColumnOrder, factor_in_order
from .linear import RowBlocks, _linear_solve, _objective
from .round_normal import Prefix, RoundNormal

__all__ = ["SOLVERS", "DEFAULT_SOLVER", "QPResult", "solve_one_sided"]

#: ``[design] solver``: the damped active-set fixed point this module
#: replaces, and §20c's exact convex QP.  ``qp`` SHIPS (§20c RULED (3),
#: Fable 2026-09-15, RULINGS 2026-09-15b); ``fixed_point`` is kept as the
#: DIAGNOSTIC ARM — the matched pair every §20c number was read against,
#: and the only way to reproduce a pre-flip surface.  ``DEFAULT_SOLVER``
#: NAMES the shipped value: the law table is the authority, and a constant
#: here saying something else would read as a second one.
SOLVERS: tuple[str, ...] = ("fixed_point", "qp")
DEFAULT_SOLVER = "qp"

#: The proximal term's starting weight, its growth on a rejected step and
#: its decay on an accepted one.  Solver constants, not law values (the
#: class of ``_ALPHA_FLOOR`` and ``_LAG_OFF`` in ``solve/design.py``): they
#: decide how the SAME minimum is reached, never which surface is lawful.
_LAMBDA0 = 1.0
_LAMBDA_UP = 6.0
_LAMBDA_DOWN = 4.0
_LAMBDA_FLOOR = 1.0e-9
#: at most this many λ increases before the step is declared unavailable
_BACKOFF_MAX = 12
#: a ceiling, whose hit is a NAMED failure and never a silent stop (§20a's
#: discipline for every loop in this solve)
_ROUNDS_MAX = 400
#: HOW MANY λ OF ONE ROUND ARE FACTORISED AT ONCE (issue #149, lane
#: ``perf149``).  A rejected step is retried at ``λ·6`` from the SAME
#: iterate, so the tries of one round depend on each other only through
#: "was the previous one accepted?".  They are therefore solved
#: CONCURRENTLY (SuperLU's factorisation releases the GIL) and READ IN
#: ORDER exactly as the sequential loop reads them: the first that lowers
#: ``F`` is taken, ``λ`` ends where the sequential loop leaves it, and the
#: ``solves`` count is the tries READ, never the tries computed — so the
#: iterate, the report and the surface are byte for byte the one-at-a-time
#: loop's.  A try computed past the accepted one is discarded unread.
#: Measured HECA stage 1: 842 linear solves over 475 rounds (1.77 per
#: round).  1 is the sequential loop.
_SPECULATE = 2
#: THREADS FOR A ROUND'S NORMAL PRODUCT (#1270, ``solve/round_normal``): the
#: round's ``SᵀS`` is taken once, its row blocks on this many threads, and
#: shared by the round's tries — the same arrays the per-try product made
_NORMAL_WORKERS = 4


class QPResult(_t.NamedTuple):
    """What one §20c solve did: the minimiser, how it ended, and the counts
    the report prints (the brief's item 3 — ``set_exits`` is the fixed
    point's instrument and is not written by this path)."""

    x: np.ndarray
    status: str            # "optimal" | "round_cap" | "no_descent"
    rounds: int
    solves: int
    objective: float
    grad_norm: float
    wall_s: float


def solve_one_sided(A0: sp.csr_matrix, b0: np.ndarray,
                    A1: sp.csr_matrix, b1: np.ndarray,
                    w_row: np.ndarray, shift: np.ndarray,
                    x0: np.ndarray | None,
                    U: sp.csr_matrix | None, c: np.ndarray | None,
                    *, method: str, solver_tol: float, solver_max_iter: int,
                    low_rank: str, rel_tol: float, active_tol: float = 0.0,
                    order: ColumnOrder | None = None,
                    verbose: bool = False) -> QPResult:
    """Minimise ``F`` (module docstring) to its unique optimum.

    ``A0``/``b0`` are the ALWAYS-ON rows (already carrying ``√w``), ``U``/
    ``c`` the per-body datum's low-rank term, ``A1``/``b1`` the one-sided
    rows over the reduced columns with the hard rows already scaled to
    metres, ``w_row`` each row's own weight and ``shift`` the augmented
    Lagrangian's ``μ/ρ`` (and the one-way lag's leader term) — exactly the
    objects ``design._solve_stage`` holds, so this is a drop-in for its
    ``_inner``.

    ``x0`` is the warm start (the previous outer round's iterate, or
    ``None`` for the cold solve, which starts from the unconstrained
    least-squares point).

    ``rel_tol`` is ``[design] qp_rel_tol`` (§61 (4)): the iteration is
    CONVERGED when one accepted step buys less than it, relative to the
    objective — a convex C¹ function at its minimum buys nothing.

    ``order`` is the stage's :class:`~.fill_order.ColumnOrder` (#1270): the
    descent runs in its ordered columns, taken from this QP's first active
    set when the stage holds none (a QP alone orders by its own).
    """
    t0 = time.perf_counter()
    solves = 0
    if x0 is None:                       # the cold start: no active set yet
        x0 = _linear_solve(A0, b0, None, method, solver_tol, solver_max_iter,
                           U, c, low_rank)
        solves = 1
    x0 = np.asarray(x0, float)
    order = ColumnOrder() if order is None else order
    if not order.holds(int(A0.shape[1])):
        order.take(A0, A1, np.flatnonzero(A1 @ x0 - (b1 - shift) > active_tol))
    res = _descend(order.relabel(A0), b0, order.relabel(A1), b1, w_row, shift,
                   x0[order.q], order.relabel(U, sort=True), c, method=method,
                   solver_tol=solver_tol, solver_max_iter=solver_max_iter,
                   low_rank=low_rank, rel_tol=rel_tol, active_tol=active_tol,
                   verbose=verbose)
    return res._replace(x=res.x[order.at], solves=res.solves + solves,
                        wall_s=time.perf_counter() - t0)


def _descend(A0: sp.csr_matrix, b0: np.ndarray, A1: sp.csr_matrix, b1: np.ndarray,
             w_row: np.ndarray, shift: np.ndarray, x0: np.ndarray,
             U: sp.csr_matrix | None, c: np.ndarray | None, *, method: str,
             solver_tol: float, solver_max_iter: int, low_rank: str, rel_tol: float,
             active_tol: float, verbose: bool) -> QPResult:
    """:func:`solve_one_sided`'s descent from ``x0``, in the ordered columns
    (each try's factorisation in the order the columns already have)."""
    t0 = time.perf_counter()
    nc = A0.shape[1]
    bb = b1 - shift
    A0T, A1T = A0.T.tocsr(), A1.T.tocsr()
    UT = None if U is None else U.T.tocsr()
    sw = np.sqrt(w_row)
    eye = sp.identity(nc, format="csr")

    #: ``A1 @ x`` of the iterates ``F`` read, by the iterate's identity
    #: (#1951): the accepted iterate's product is the one the next round's
    #: active set and the final gradient read, so it is taken once.  ``F``
    #: runs on the speculation threads; a dict store is atomic.
    a1x_of: dict[int, tuple[np.ndarray, np.ndarray]] = {}

    A1_rows = RowBlocks(A1)          # ``A1 @ x`` on threads, bit for bit

    def a1x(x: np.ndarray) -> np.ndarray:
        got = a1x_of.get(id(x))
        return got[1] if got is not None and got[0] is x else A1_rows @ x

    def F(x: np.ndarray) -> float:
        r, pen = A1_rows.penalty(x, bb, w_row)
        a1x_of[id(x)] = (x, r)
        return _objective(A0, b0, A1, b1, w_row, shift, x, U, c, pen=pen)

    def grad(x: np.ndarray) -> np.ndarray:
        g = 2.0 * (A0T @ (A0 @ x - b0))
        if UT is not None and c is not None:
            g += 2.0 * (UT @ (U @ x - c))
        r = np.maximum(a1x(x) - bb, 0.0)
        return g + 2.0 * (A1T @ (w_row * r))

    def active(x: np.ndarray) -> np.ndarray:
        sel = A1_rows.above(a1x(x), bb, active_tol)
        a1x_of.clear()       # the next products are the next round's
        return sel

    def stack(sel: np.ndarray) -> tuple[list, list]:
        """The always-on rows over the active rows at their own weights."""
        blocks: list = [A0]
        rhs: list = [b0]
        if sel.size:
            blocks.append(sp.diags(sw[sel]) @ A1[sel])
            rhs.append(sw[sel] * bb[sel])
        return blocks, rhs

    #: #1270: a warm ``normal`` try reads its round's shared ``SᵀS``
    #: (``solve/round_normal``) — ``dense`` stacks ``U`` after the λ rows,
    #: so it keeps the per-try product
    shared = method == "normal" and (U is None or low_rank != "dense")
    Uk = U if U is not None and int(U.shape[0]) else None
    norm_pool = ThreadPoolExecutor(_NORMAL_WORKERS) if shared and _NORMAL_WORKERS > 1 else None
    this_round: dict = {}

    def round_normal(sel: np.ndarray) -> None:
        """The round's normal matrix, before its tries."""
        if not shared:
            return
        if "pre" not in this_round:
            this_round["pre"] = Prefix(A0, b0, A0T, norm_pool, _NORMAL_WORKERS)
        W = (sp.diags(sw[sel]) @ A1[sel]).tocsr() if sel.size else \
            sp.csr_matrix((0, nc))
        this_round["rn"] = RoundNormal(this_round["pre"], W, sw[sel] * bb[sel], Uk,
                                       low_rank, norm_pool, _NORMAL_WORKERS,
                                       factor_in_order)

    def step(x: np.ndarray, lam: float, sel: np.ndarray) -> tuple[np.ndarray, int]:
        """The active set ``sel``'s own subproblem, PROXIMAL at ``x``."""
        rn = this_round.get("rn")
        if rn is not None:
            return rn.solve(x, lam, None if Uk is None else c), int(sel.size)
        blocks, rhs = stack(sel)
        root = float(np.sqrt(lam))
        blocks.append(root * eye)
        rhs.append(root * x)
        A = sp.vstack(blocks, format="csr")
        b = np.concatenate(rhs)
        return (_linear_solve(A, b, x, method, solver_tol, solver_max_iter,
                              U, c, low_rank), int(sel.size))

    solves = 0
    x = np.asarray(x0, float).copy()
    f = F(x)
    lam = _LAMBDA0
    status = "round_cap"
    rnd = 0
    pool = ThreadPoolExecutor(_SPECULATE) if _SPECULATE > 1 else None

    def tried(x_: np.ndarray, lam_: float, sel: np.ndarray
              ) -> tuple[np.ndarray, int, float]:
        xt_, nact_ = step(x_, lam_, sel)
        return xt_, nact_, F(xt_)
    try:
        for rnd in range(1, _ROUNDS_MAX + 1):
            sel = active(x)
            round_normal(sel)
            took, lam, xt, ft, nact, read = _round(x, f, lam, tried, sel, pool)
            solves += read
            if not took:
                # No damped step of the SAME subproblem decreases a convex C¹
                # F: the iterate is its minimiser to the linear solve's own
                # precision.  Named, never silent.
                status = "no_descent"
                break
            gain = f - ft
            x, f = xt, ft
            lam = max(lam / _LAMBDA_DOWN, _LAMBDA_FLOOR)
            if verbose:
                print(f"    [design/qp] round {rnd}: F {f:.10g} (-{gain:.4g}) "
                      f"λ {lam:.3g}, {nact} active")
            if gain <= rel_tol * max(1.0, abs(f)):
                status = "optimal"
                break
    finally:
        if pool is not None:
            pool.shutdown(wait=True)
        if norm_pool is not None:
            norm_pool.shutdown(wait=True)
        this_round.clear()
    try:
        g_end = float(np.linalg.norm(grad(x)))
    finally:
        A1_rows.close()
    return QPResult(x=x, status=status, rounds=rnd, solves=solves,
                    objective=float(f), grad_norm=g_end,
                    wall_s=time.perf_counter() - t0)


def _round(x: np.ndarray, f: float, lam: float, tried: _t.Callable,
           sel: np.ndarray, pool: "ThreadPoolExecutor | None") -> tuple:
    """ONE round's backoff (:data:`_SPECULATE`): ``(took, λ, x_t, F(x_t),
    active count, tries read)`` — the sequential loop's answer.  Up to
    ``_BACKOFF_MAX`` tries at ``λ, λ·6, λ·6², …`` (the λ by the SAME
    repeated multiplication), solved ``_SPECULATE`` at a time and read in
    order until one lowers ``F``."""
    read = 0
    xt, nact, ft = x, 0, f
    while read < _BACKOFF_MAX:
        k = min(_SPECULATE, _BACKOFF_MAX - read) if pool is not None else 1
        lams = [lam]
        for _i in range(k - 1):
            lams.append(lams[-1] * _LAMBDA_UP)
        if k > 1:
            got = [fu.result() for fu in [pool.submit(tried, x, lm, sel) for lm in lams]]
        else:
            got = [tried(x, lam, sel)]
        for (xt, nact, ft), lm in zip(got, lams):
            read += 1
            lam = lm
            if ft < f:
                return True, lam, xt, ft, nact, read
        lam = lam * _LAMBDA_UP
    return False, lam, xt, ft, nact, read

