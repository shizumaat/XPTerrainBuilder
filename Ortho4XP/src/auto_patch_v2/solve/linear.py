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

__all__ = ["METHODS", "DEFAULT_METHOD", "LOW_RANK_MODES", "DEFAULT_LOW_RANK", "RowBlocks"]


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


def _factor(M: sp.csc_matrix):
    """THE ONE SPARSE FACTORISATION of every design solve (owner RULINGS
    2026-10-20, #803/#412).  Every matrix factorised here is SYMMETRIC — the
    floored normal matrix (positive definite) and its bordered form (quasi-
    definite: ``M`` over ``−I``) — so SuperLU runs in its symmetric mode: a
    minimum-degree ordering of ``Mᵀ + M`` and diagonal pivots preferred.
    Measured on HECA's stage-1 bordered systems (n 19,685): 0.074 s → 0.042 s
    per factorisation, the solution moving at 1e-13 relative (5,539
    factorisations per HECA solve).  The answer changes at rounding level
    only, which the owner accepted at the visibility bars."""
    return splu(M, permc_spec="MMD_AT_PLUS_A", diag_pivot_thresh=0.1,
                options={"SymmetricMode": True})


def _bordered(M: sp.csc_matrix, U: sp.csr_matrix) -> sp.csc_matrix:
    """``bmat([[M, Uᵀ], [U, −I]], format="csc")`` written straight into its
    canonical arrays (#1270: the ``bmat`` cost 4.5 ms of each 75 ms KATL
    try).  ``bmat`` goes through COO and sorts each column, so column ``j``
    is ``M``'s column over ``U``'s (rows shifted by ``n``) and column
    ``n + i`` is ``U``'s row ``i`` over the ``−1`` — every value a copy.  A
    matrix not in canonical form (unsorted or duplicate entries, which
    ``bmat`` would re-order or sum) takes ``bmat`` itself."""
    k = int(U.shape[0])
    if not (M.format == "csc" and M.has_canonical_format
            and U.format == "csr" and U.has_canonical_format):
        return sp.bmat([[M, U.T], [U, -sp.identity(k, format="csc")]], format="csc")
    n = int(M.shape[0])
    Uc = U.tocsc()
    mp, up = M.indptr.astype(np.int64), Uc.indptr.astype(np.int64)
    rp = U.indptr.astype(np.int64)
    nm, nu = int(mp[-1]), int(up[-1])
    indptr = np.concatenate([mp + up, nm + nu + rp[1:] + np.arange(1, k + 1)])
    nnz = int(indptr[-1])
    idx_t = np.int32 if n + k < np.iinfo(np.int32).max and nnz < np.iinfo(np.int32).max \
        else np.int64
    indices = np.empty(nnz, dtype=idx_t)
    data = np.empty(nnz)
    # column j < n: M's entries, then U's column j
    col_m = np.repeat(np.arange(n), np.diff(mp))
    pos_m = np.arange(nm) + up[col_m]
    indices[pos_m] = M.indices
    data[pos_m] = M.data
    col_u = np.repeat(np.arange(n), np.diff(up))
    pos_u = np.arange(nu) - up[col_u] + mp[col_u + 1] + up[col_u]
    indices[pos_u] = n + Uc.indices
    data[pos_u] = Uc.data
    # column n + i: U's row i, then −1 on the border's diagonal
    row_u = np.repeat(np.arange(k), np.diff(rp))
    pos_r = indptr[n + row_u] + (np.arange(int(rp[-1])) - rp[row_u])
    indices[pos_r] = U.indices
    data[pos_r] = U.data
    pos_d = indptr[n + 1:] - 1
    indices[pos_d] = n + np.arange(k)
    data[pos_d] = -1.0
    return sp.csc_matrix((data, indices, indptr.astype(idx_t)), shape=(n + k, n + k))


def _normal_back(M: sp.csc_matrix, U: sp.csr_matrix | None, low_rank: str):
    """``back(r, rc) -> (M + UᵀU)⁻¹ (r + Uᵀ rc)`` on ONE factorisation of the
    (floored) normal matrix ``M``: the low-rank datum term by ``low_rank``
    (:data:`LOW_RANK_MODES`; ``U is None``: no such term)."""
    n = M.shape[0]
    if U is None:
        lu = _factor(M)
        return lambda r, rc=None: np.asarray(lu.solve(r), float)
    k = int(U.shape[0])
    if low_rank == "bordered":
        # the border carries ``rc`` itself: eliminating y = U x − rc gives
        # (M + UᵀU) x = r + Uᵀ rc.  ONE sparse solve of the augmented system
        # whose Schur complement onto the border is Woodbury's k × k system
        lu = _factor(_bordered(M, U))
        return lambda r, rc: np.asarray(
            lu.solve(np.concatenate([r, rc]))[:n], float)
    # the identity applied explicitly: k back-solves against LU(M)
    lu = _factor(M)
    Y = lu.solve(np.asarray(U.T.toarray(), float))              # M⁻¹ Uᵀ
    S = np.eye(k) + np.asarray(U @ Y, float)                    # I + U M⁻¹ Uᵀ

    def back(r: np.ndarray, rc: np.ndarray) -> np.ndarray:
        y = lu.solve(r + np.asarray(U.T @ rc).ravel())
        return np.asarray(y - Y @ np.linalg.solve(S, U @ y), float)
    return back


def _floored(N: sp.csc_matrix) -> sp.csc_matrix:
    """The normal matrix with its tiny Tikhonov floor: it keeps the
    factorisation non-singular on a column the active set left with only a
    bending row (``solve/round_normal`` builds the same ``N`` by rounds)."""
    eps = 1e-12 * max(1.0, float(abs(N.diagonal()).max()))
    return (N + eps * sp.identity(N.shape[0], format="csc")).tocsc()


def _linear_solve(A: sp.csr_matrix, b: np.ndarray, x0: np.ndarray | None,
                  method: str, tol: float, maxiter: int,
                  U: sp.csr_matrix | None = None, c: np.ndarray | None = None,
                  low_rank: str = DEFAULT_LOW_RANK) -> np.ndarray:
    """min ‖A x − b‖² + ‖U x − c‖² by ``method`` (:data:`METHODS`).

    ``U`` carries the PER-BODY DATUM rows (one per body, already weighted):
    each is dense in the normal equations, so it is applied as a LOW-RANK
    correction by ``low_rank`` (:data:`LOW_RANK_MODES`) instead of being
    factorised.  Every mode is the SAME algebra and returns the same ``x``.

    The ``normal`` result DEPENDS ON ``x0``: it is an increment from the
    warm start, so a column no row prices (the null space) is returned at
    its ``x0`` value (0 on a cold start) — never pulled to zero.
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
        back = _normal_back(_floored(N), U if k else None, low_rank)
        cc = None if not k else np.asarray(c, float)

        def toward(x: np.ndarray) -> np.ndarray:
            """The step from ``x`` to the minimiser, its residual taken on
            ``A`` itself — the floor then pulls the STEP to zero, never
            the answer."""
            return back(At @ (b - A @ x), None if cc is None else cc - U @ x)
        # THE FLOOR IS CENTRED ON THE WARM START (lane ``pass2``,
        # ``docs/briefs/pass2-notes.md`` step 4): ``(N + eps I) x = Aᵀb`` minimises ``‖Ax − b‖² + eps‖x‖²``
        # — a spring to z = 0 on every column, and ``eps`` follows the
        # STIFFEST row (KCLT: max diag 1.1e8, eps 1.1e-4), so a column
        # priced at 1.0 or less was held to sea level nearly as hard as to
        # its neighbours and the QP stopped where that spring balanced the
        # descent (|g| = 2·eps·‖z‖).  Solved as an increment from ``x0`` the
        # same floor damps the step and leaves the optimum alone.
        if x0 is not None:
            x0 = np.asarray(x0, float)
            return x0 + toward(x0)
        x = back(rhs, cc)                # the cold start: no iterate yet —
        return x + toward(x)             # one refinement lifts the spring
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


class RowBlocks:
    """``A @ x`` for a TALL sparse matrix, its rows cut into blocks and the
    blocks multiplied on threads (#1951).  Every row is multiplied by the
    same SciPy kernel over the same entries in the same order, so the product
    is the plain ``A @ x`` bit for bit; SciPy's kernel releases the GIL, so
    the blocks run at once.  KMCI's one-sided stack is 18 M rows, read three
    times per QP round over 2,773 rounds; a matrix under ``min_rows`` is
    multiplied whole."""

    def __init__(self, A: sp.csr_matrix, workers: int = 4,
                 min_rows: int = 1_000_000) -> None:
        self.A = A
        n = int(A.shape[0])
        k = max(1, min(int(workers), n // max(1, int(min_rows)) or 1))
        if n < min_rows:
            k = 1
        cuts = np.linspace(0, n, k + 1).astype(np.int64)
        self.blocks = [A[int(a):int(b)] for a, b in zip(cuts[:-1], cuts[1:], strict=True)]
        self._pool = None
        self._spans = self._cuts()
        if k > 1:
            from concurrent.futures import ThreadPoolExecutor
            self._pool = ThreadPoolExecutor(k)

    def __matmul__(self, x: np.ndarray) -> np.ndarray:
        if self._pool is None:
            return self.A @ x
        return np.concatenate(list(self._pool.map(lambda B: B @ x, self.blocks)))

    def _cuts(self) -> list[tuple[int, int]]:
        out, a = [], 0
        for B in self.blocks:
            out.append((a, a + int(B.shape[0])))
            a += int(B.shape[0])
        return out

    def penalty(self, x: np.ndarray, bb: np.ndarray, w: np.ndarray
                ) -> tuple[np.ndarray, np.ndarray]:
        """``(A @ x, w · max(A @ x − bb, 0)²)`` — the one-sided rows'
        product and their penalty terms, each element by the expression
        :func:`_objective` writes, block by block on the threads."""
        if self._pool is None:
            r = self.A @ x
            return r, w * np.maximum(r - bb, 0.0) ** 2
        r = np.empty(self.A.shape[0])
        pen = np.empty(self.A.shape[0])

        def one(k: int) -> None:
            a, b = self._spans[k]
            r[a:b] = self.blocks[k] @ x
            pen[a:b] = w[a:b] * np.maximum(r[a:b] - bb[a:b], 0.0) ** 2
        list(self._pool.map(one, range(len(self.blocks))))
        return r, pen

    def above(self, r: np.ndarray, bb: np.ndarray, tol: float) -> np.ndarray:
        """``np.flatnonzero(r − bb > tol)``, block by block."""
        if self._pool is None:
            return np.flatnonzero(r - bb > tol)
        parts = list(self._pool.map(
            lambda ab: np.flatnonzero(r[ab[0]:ab[1]] - bb[ab[0]:ab[1]] > tol) + ab[0],
            self._spans))
        return np.concatenate(parts).astype(np.int64, copy=False)

    def close(self) -> None:
        if self._pool is not None:
            self._pool.shutdown(wait=True)
            self._pool = None


def _objective(A0: sp.csr_matrix, b0: np.ndarray, A1: sp.csr_matrix,
               b1: np.ndarray, w_row: np.ndarray, shift: np.ndarray,
               x: np.ndarray, U: sp.csr_matrix | None = None,
               c: np.ndarray | None = None, *, bb: np.ndarray | None = None,
               a1x: np.ndarray | None = None, pen: np.ndarray | None = None) -> float:
    """The TRUE objective at ``x``: the always-on rows' squared residual plus
    the PER-BODY DATUM's (the low-rank term ``U`` — held out of the
    factorisation, never out of the objective the line search descends) plus
    every one-sided row's ``w · max(0, violation)²`` at ITS OWN weight (the
    law's for a target, ``hard_weight`` for a runway constraint) against its
    shifted target (the augmented Lagrangian's ``b − μ/ρ``).

    ``bb`` is ``b1 − shift`` and ``a1x`` is ``A1 @ x`` when the caller holds
    them already (#1951: ``A1`` carries a row per one-sided side — 18 M at
    KMCI — and the QP reads ``F`` and the active set at every iterate); the
    value is the same array either way; ``pen`` is :meth:`RowBlocks.penalty`'s
    ``w · viol²``, the same elements."""
    if pen is None:
        viol = np.maximum((A1 @ x if a1x is None else a1x)
                          - ((b1 - shift) if bb is None else bb), 0.0)
        pen = w_row * viol ** 2
    f = float(np.sum((A0 @ x - b0) ** 2) + float(np.sum(pen)))
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
