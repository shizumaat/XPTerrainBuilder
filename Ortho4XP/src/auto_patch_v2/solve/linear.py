"""THE DESIGN SURFACE'S LINEAR ALGEBRA — the one linear solve an
active-set round pays, the objective the line search descends, and the
per-term energies the report prints (split from ``solve/design.py`` by
the 1,000-line file law; owner RULINGS 2026-09-09r (1) is what made the
module worth its own file).

Nothing here knows about law, roles or geometry: it is given a matrix, a
right-hand side and the PER-BODY DATUM's low-rank term, and returns ``x``.
"""
from __future__ import annotations

import numpy as np
import scipy.sparse as sp
from scipy.sparse.linalg import LinearOperator, cg, lsqr, splu

from .rows import _Rows

__all__ = ["METHODS", "DEFAULT_METHOD", "LOW_RANK_MODES", "DEFAULT_LOW_RANK"]


#: The linear solvers the round may use.  ``normal`` factorises the normal
#: equations Aᵀ A once per active set (sparse LU); ``cg`` runs conjugate
#: gradients on them (Jacobi-preconditioned); ``lsqr`` runs on A itself.
#: The lane measured all three on CYXY and HECA captures (spec §5).
METHODS: tuple[str, ...] = ("normal", "cg", "lsqr")
DEFAULT_METHOD = "normal"

#: HOW THE PER-BODY DATUM ROWS REACH THE LINEAR SOLVE (owner RULINGS
#: 2026-09-09r (1)).  A body's datum is ONE row with ``N`` non-zeros, so in
#: the normal equations ``AᵀA`` it is a rank-1 DENSE ``N × N`` block: the
#: factorisation cost is ``O(Σ N_body²)`` and at HECA (342 bodies) it cost
#: the solve +76 s (spec §14.5).  The rows are therefore held OUT of the
#: factorised matrix as a LOW-RANK term ``U ᵀU`` (one row of ``U`` per
#: body) and applied by the WOODBURY identity:
#:
#:     (M + Uᵀ U)⁻¹ = M⁻¹ − M⁻¹ Uᵀ (I + U M⁻¹ Uᵀ)⁻¹ U M⁻¹
#:
#: ``bordered`` realises exactly that identity as ONE sparse solve of the
#: augmented (quasi-definite) system, whose Schur complement onto the
#: border IS the ``k × k`` dense system the identity names:
#:
#:     [ M   Uᵀ ] [x]   [Aᵀb]        y = U x − c
#:     [ U   −I ] [y] = [ c  ]   ⇒   (M + Uᵀ U) x = Aᵀb + Uᵀ c
#:
#: ``woodbury`` applies the identity EXPLICITLY (``k`` triangular
#: back-solves against the sparse LU of ``M``) — the same algebra, kept as
#: the twin's reference and measured against ``bordered``; ``dense`` stacks
#: the rows into ``A`` as ordinary rows (round 1's behaviour, the ``O(Σ
#: N²)`` block) and is the parity arm every path is checked against.
LOW_RANK_MODES: tuple[str, ...] = ("bordered", "woodbury", "dense")
DEFAULT_LOW_RANK = "bordered"


def _linear_solve(A: sp.csr_matrix, b: np.ndarray, x0: np.ndarray | None,
                  method: str, tol: float, maxiter: int,
                  U: sp.csr_matrix | None = None, c: np.ndarray | None = None,
                  low_rank: str = DEFAULT_LOW_RANK) -> np.ndarray:
    """min ‖A x − b‖² + ‖U x − c‖² by ``method`` (:data:`METHODS`).

    ``U`` carries the PER-BODY DATUM rows (one per body, already weighted):
    each is dense in the normal equations, so it is applied as a LOW-RANK
    correction by ``low_rank`` (:data:`LOW_RANK_MODES`) instead of being
    factorised.  Every mode is the SAME algebra and returns the same ``x``.
    """
    k = 0 if U is None else int(U.shape[0])
    if k and low_rank == "dense":
        A = sp.vstack([A, U], format="csr")
        b = np.concatenate([b, np.asarray(c, float)])
        k = 0
    if method == "lsqr":
        if k:
            A = sp.vstack([A, U], format="csr")
            b = np.concatenate([b, np.asarray(c, float)])
        out = lsqr(A, b, atol=tol, btol=tol, iter_lim=maxiter, x0=x0)
        return np.asarray(out[0], float)
    At = A.T.tocsr()
    N = (At @ A).tocsc()
    rhs = At @ b
    if method == "normal":
        # a tiny Tikhonov floor keeps the factorisation non-singular on a
        # column the active set left with only a bending row
        eps = 1e-12 * max(1.0, float(abs(N.diagonal()).max()))
        M = (N + eps * sp.identity(N.shape[0], format="csc")).tocsc()
        if not k:
            return np.asarray(splu(M).solve(rhs), float)
        if low_rank == "bordered":
            # the border carries ``c`` itself: eliminating y = U x − c gives
            # (M + UᵀU) x = Aᵀb + Uᵀc, so ``rhs`` stays Aᵀb here
            # ONE sparse solve of the augmented system whose Schur
            # complement onto the border is Woodbury's k × k dense system
            K = sp.bmat([[M, U.T], [U, -sp.identity(k, format="csc")]],
                        format="csc")
            sol = splu(K).solve(np.concatenate([rhs, np.asarray(c, float)]))
            return np.asarray(sol[:N.shape[0]], float)
        # the identity applied explicitly: k back-solves against LU(M)
        lu = splu(M)
        x0_ = lu.solve(rhs + np.asarray(U.T @ np.asarray(c, float)).ravel())
        Y = lu.solve(np.asarray(U.T.toarray(), float))          # M⁻¹ Uᵀ
        S = np.eye(k) + np.asarray(U @ Y, float)                # I + U M⁻¹ Uᵀ
        return np.asarray(x0_ - Y @ np.linalg.solve(S, U @ x0_), float)
    if k:
        rhs = rhs + np.asarray(U.T @ np.asarray(c, float)).ravel()
    diag = N.diagonal().copy()
    if k:
        diag = diag + np.asarray(U.multiply(U).sum(axis=0), float).ravel()
    diag[diag <= 0.0] = 1.0
    Mj = sp.diags(1.0 / diag)
    Nc = N.tocsr()
    Uc = None if not k else U.tocsr()
    op = (Nc if not k else
          LinearOperator(Nc.shape, matvec=lambda v: Nc @ v + Uc.T @ (Uc @ v)))
    x, _info = cg(op, rhs, x0=x0, rtol=tol, maxiter=maxiter, M=Mj)
    return np.asarray(x, float)


def _objective(A0: sp.csr_matrix, b0: np.ndarray, A1: sp.csr_matrix,
               b1: np.ndarray, w_row: np.ndarray, shift: np.ndarray,
               x: np.ndarray, U: sp.csr_matrix | None = None,
               c: np.ndarray | None = None) -> float:
    """The TRUE objective at ``x``: the always-on rows' squared residual plus
    the PER-BODY DATUM's (the low-rank term ``U`` — held out of the
    factorisation, never out of the objective the line search descends) plus
    every one-sided row's ``w · max(0, violation)²`` at ITS OWN weight (the
    law's for a target, ``hard_weight`` for a runway constraint) against its
    shifted target (the augmented Lagrangian's ``b − μ/ρ``)."""
    viol = np.maximum(A1 @ x - (b1 - shift), 0.0)
    f = float(np.sum((A0 @ x - b0) ** 2) + float(np.sum(w_row * viol ** 2)))
    if U is not None and c is not None:
        f += float(np.sum((U @ x - c) ** 2))
    return f


def _term_energies(rows: _Rows, A: sp.csr_matrix, b: np.ndarray,
                   x: np.ndarray | None) -> dict[str, float]:
    """Σ of each objective term's squared weighted residual."""
    if x is None:
        return {}
    r = A @ x - b
    acc: dict[str, float] = {}
    for k, own in enumerate(rows.owner):
        key = own[0] if own else "other"
        acc[key] = acc.get(key, 0.0) + float(r[k]) ** 2
    return {k: round(v, 3) for k, v in sorted(acc.items())}
