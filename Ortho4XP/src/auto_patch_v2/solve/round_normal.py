"""ONE QP ROUND'S NORMAL MATRIX, BUILT ONCE AND SHARED BY ITS TRIES (#1270).

A round of :func:`~.design_qp.solve_one_sided` tries the SAME active set at
``λ, 6λ, 36λ, …`` from the SAME iterate.  Each try's least-squares stack is

    A(λ) = [ S ; √λ·I ]        S = [ A0 ; diag(√w_sel)·A1_sel ]

and :func:`~.linear._linear_solve` rebuilt ``A(λ)``, transposed it and
multiplied ``A(λ)ᵀA(λ)`` in every try.  Only the last ``n`` rows depend on
``λ`` and they come LAST in the stack, so every entry of the product is the
fold of ``SᵀS``'s own terms followed — on the diagonal only — by one term
``√λ·√λ``.  This module takes ``SᵀS`` once per round (its row blocks on
threads: SciPy's ``csr_matmat`` computes each output row from that row
alone, so the blocks ARE the product, bit for bit) and finishes each try's
matrix with that one diagonal term computed BY THE SAME KERNEL: the
compiled ``sums += v·b`` is fused into an FMA on the shipped wheel
(measured), so the term is never re-derived in NumPy.  The right-hand side
``A(λ)ᵀ(b − A(λ)x)`` is ``Sᵀ(b_S − Sx)`` plus the λ rows' terms, whose
residual ``√λ·x − √λ·x`` is an exact zero.

The matrix factorised and the vectors solved are the old path's, array for
array (twin ``tests/auto_patch_v2/test_round_normal.py``): the surface is
byte-identical and the round is shorter.
"""
from __future__ import annotations

import typing as _t

import numpy as np
import scipy.sparse as sp

from .linear import _floored, _normal_back

__all__ = ["RoundNormal"]

#: a row block of ``Sᵀ`` holds at least this many columns of ``S``: below
#: it the product is taken whole
_BLOCK_MIN_COLS = 4000


class RoundNormal:
    """``SᵀS`` of one round's active stack ``S`` (right-hand side ``b``), and
    each try's warm-started proximal solve on it (:meth:`solve`)."""

    def __init__(self, S: sp.csr_matrix, b: np.ndarray,
                 pool: _t.Any = None, workers: int = 1) -> None:
        self.S, self.b = S, b
        self.n = n = int(S.shape[1])
        self.St = St = S.T.tocsr()
        k = max(1, min(int(workers), n // _BLOCK_MIN_COLS))
        if pool is None or k == 1:
            N = St @ S
        else:
            cuts = np.linspace(0, n, k + 1).astype(np.int64)
            N = sp.vstack(list(pool.map(lambda ab: St[int(ab[0]):int(ab[1])] @ S,
                                        zip(cuts[:-1], cuts[1:], strict=True))),
                          format="csr")
        coo = N.tocoo()
        on = coo.row == coo.col
        #: ``SᵀS``'s diagonal (0 where the product has none) and the rest
        self.diag = np.zeros(n)
        self.diag[coo.row[on]] = coo.data[on]
        self.off = sp.csc_matrix((coo.data[~on], (coo.row[~on], coo.col[~on])),
                                 shape=(n, n))
        self._eye = sp.identity(n, format="csr")
        self._fold_ptr = np.arange(0, 2 * n + 1, 2, dtype=np.int64)
        self._fold_idx = np.column_stack([np.arange(n), n + np.arange(n)]).ravel()

    def _diagonal(self, root: float) -> np.ndarray:
        """Each column's ``SᵀS`` diagonal followed by ``√λ·√λ`` — taken by
        ``csr_matmat`` itself, the kernel and the order of the full
        product's fold: row ``i`` of ``L`` reads ``(1, √λ)`` against ``R``'s
        ``s_i`` over ``√λ``."""
        n = self.n
        L = sp.csr_matrix((np.column_stack([np.ones(n), np.full(n, root)]).ravel(),
                           self._fold_idx, self._fold_ptr), shape=(n, 2 * n))
        R = sp.vstack([sp.diags(self.diag, format="csr"),
                       sp.diags(np.full(n, root), format="csr")], format="csr")
        return np.asarray((L @ R).diagonal(), float)

    def solve(self, x0: np.ndarray, lam: float, U: sp.csr_matrix | None,
              c: np.ndarray | None, low_rank: str) -> np.ndarray:
        """:func:`~.linear._linear_solve` (``normal``, warm start and
        proximal centre ``x0``) of ``[S; √λ I] x ≈ [b; √λ x0]``."""
        root = float(np.sqrt(lam))
        N = self.off + sp.diags(self._diagonal(root), format="csc")
        back = _normal_back(_floored(N), U, low_rank)
        x0 = np.asarray(x0, float)
        r_lam = root * x0 - (root * self._eye) @ x0     # exactly ±0 per row
        rhs = self.St @ (self.b - self.S @ x0) + root * r_lam
        rc = None if U is None else np.asarray(c, float) - U @ x0
        return x0 + back(rhs, rc)
