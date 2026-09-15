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

import numpy as np
import scipy.sparse as sp

# §20c: the projections' solver, imported AT MODULE TOP.  A third-party
# import inside a function is invisible to PyInstaller and to the suite
# (memory ``frozen-engine-lazy-imports``: ``highspy`` 2026-09-10 shipped a
# frozen engine that died on a lazy import nothing had exercised).  It is
# imported here because this module is §20c's site even though the measured
# solver below is the module's own — see the docstring's deviation.
import highspy  # noqa: F401

from .linear import _linear_solve, _objective

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
#: the iteration is CONVERGED when one accepted step buys less than this,
#: relative to the objective (a convex C¹ function at its minimum buys
#: nothing; this is the floor of double precision on that reading)
_REL_TOL = 1.0e-9
#: a ceiling, whose hit is a NAMED failure and never a silent stop (§20a's
#: discipline for every loop in this solve)
_ROUNDS_MAX = 400


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
                    low_rank: str, active_tol: float = 0.0,
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
    """
    t0 = time.perf_counter()
    nc = A0.shape[1]
    bb = b1 - shift
    A0T, A1T = A0.T.tocsr(), A1.T.tocsr()
    UT = None if U is None else U.T.tocsr()
    sw = np.sqrt(w_row)
    eye = sp.identity(nc, format="csr")

    def F(x: np.ndarray) -> float:
        return _objective(A0, b0, A1, b1, w_row, shift, x, U, c)

    def grad(x: np.ndarray) -> np.ndarray:
        g = 2.0 * (A0T @ (A0 @ x - b0))
        if UT is not None and c is not None:
            g += 2.0 * (UT @ (U @ x - c))
        r = np.maximum(A1 @ x - bb, 0.0)
        return g + 2.0 * (A1T @ (w_row * r))

    def step(x: np.ndarray | None, lam: float) -> tuple[np.ndarray, int]:
        """The active set's own subproblem, PROXIMAL at ``x``."""
        sel = (np.flatnonzero(A1 @ x - bb > active_tol) if x is not None
               else np.zeros(0, dtype=np.int64))
        blocks: list = [A0]
        rhs: list = [b0]
        if sel.size:
            blocks.append(sp.diags(sw[sel]) @ A1[sel])
            rhs.append(sw[sel] * bb[sel])
        if x is not None and lam > 0.0:
            root = float(np.sqrt(lam))
            blocks.append(root * eye)
            rhs.append(root * x)
        A = sp.vstack(blocks, format="csr") if len(blocks) > 1 else A0
        b = np.concatenate(rhs) if len(rhs) > 1 else b0
        return (_linear_solve(A, b, x, method, solver_tol, solver_max_iter,
                              U, c, low_rank), int(sel.size))

    solves = 0
    if x0 is None:                       # the cold start: no active set yet
        x, _n = step(None, 0.0)
        solves += 1
    else:
        x = np.asarray(x0, float).copy()
    f = F(x)
    lam = _LAMBDA0
    status = "round_cap"
    rnd = 0
    for rnd in range(1, _ROUNDS_MAX + 1):
        took = False
        for _back in range(_BACKOFF_MAX):
            xt, nact = step(x, lam)
            solves += 1
            ft = F(xt)
            if ft < f:
                took = True
                break
            lam *= _LAMBDA_UP
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
        if gain <= _REL_TOL * max(1.0, abs(f)):
            status = "optimal"
            break
    return QPResult(x=x, status=status, rounds=rnd, solves=solves,
                    objective=float(f), grad_norm=float(np.linalg.norm(grad(x))),
                    wall_s=time.perf_counter() - t0)
