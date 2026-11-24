"""ONE FILL-REDUCING COLUMN ORDER PER SOLVE STAGE (#1270, lane ``lsplu``).

Every try of :func:`~.design_qp.solve_one_sided` factorises a matrix of the
same size and NEARLY the same pattern — the always-on rows' normal matrix,
the round's active one-sided rows, ``λ`` on the diagonal, the per-body
border of ``linear._bordered`` — and ``linear._factor`` let SuperLU order
every one of them afresh (``MMD_AT_PLUS_A``).  That ordering was about
40 % of each factorisation (KBUF: 6.5 → 3.9 ms at n 4,601, 14.1 → 8.4 ms at
n 14,145), and an order taken on one round's pattern costs every other
round of the stage about 1-3 % more fill (the active set moves a few
hundred entries of the pattern; the border placed last, +3 %).

So the stage orders ONCE (:class:`ColumnOrder`, from the pattern of its
first QP's first active set) and every QP of the stage runs in the ORDERED
COLUMNS: ``A0``, ``A1`` and ``U`` have their column indices relabelled
(:func:`relabelled` — each row keeps its entries in their stored order, so
every product, residual and normal matrix holds the SAME values in the same
summation order, only relabelled), and each try factorises its matrix as
it stands (:func:`factor_in_order`: ``NATURAL`` order, ``panel_size`` 1,
another 25 % off these matrices).  The border's rows come last, where the
relabelling leaves them.

NOT byte-identical: the factors are the same algebra in another summation
order, so a solve moves at rounding level (KBUF's 19 QP calls: 11 return
the identical iterate, the rest move ≤ 1e-10 m) and a QP may take another
path by a try.  RULINGS 2026-11-23e/24e are the bar this was measured
against.
"""
from __future__ import annotations

import numpy as np
import scipy.sparse as sp
from scipy.sparse.linalg import splu

__all__ = ["ColumnOrder", "relabelled", "factor_in_order"]


class ColumnOrder:
    """A stage's column order: ``q[i]`` is the original column at position
    ``i``; ``at[j]`` the position of original column ``j``."""

    def __init__(self) -> None:
        self.q: np.ndarray | None = None
        self.at: np.ndarray | None = None
        #: the relabelled matrices by their source's identity (the source
        #: held, so an identity is never reused): a stage hands every QP the
        #: same ``A0``/``A1``/``U`` until it rescales one
        self._held: dict[int, tuple] = {}

    def holds(self, n: int) -> bool:
        """An order over ``n`` columns is taken."""
        return self.q is not None and self.q.size == n

    def take(self, A0: sp.csr_matrix, A1: sp.csr_matrix, sel: np.ndarray) -> None:
        """Order by the pattern of ``[A0; A1[sel]]ᵀ[A0; A1[sel]]`` (a minimum
        degree order of it, SuperLU's own)."""
        n = int(A0.shape[1])
        self._held.clear()
        S = sp.vstack([A0, A1[sel]], format="csr")
        S = sp.csr_matrix((np.ones(S.nnz), S.indices, S.indptr), shape=S.shape)
        # the pattern, made diagonally dominant so the ordering pass's own
        # factorisation pivots on the diagonal
        N = (S.T @ S).tocsc()
        N = (N + float(N.shape[0] * (1 + S.shape[0])) * sp.identity(n, format="csc")).tocsc()
        lu = splu(N, permc_spec="MMD_AT_PLUS_A", diag_pivot_thresh=0.1,
                  options={"SymmetricMode": True})
        self.q = np.argsort(lu.perm_c)
        self.at = np.empty(n, dtype=np.int64)
        self.at[self.q] = np.arange(n)

    def relabel(self, A: sp.csr_matrix | None, sort: bool = False) -> sp.csr_matrix | None:
        """:func:`relabelled` by this order, once per source matrix."""
        if A is None:
            return None
        got = self._held.get(id(A))
        if got is None or got[0] is not A:
            got = (A, relabelled(A, self.at, sort))
            self._held = {k: v for k, v in self._held.items() if v[0] is not A}
            self._held[id(A)] = got
        return got[1]


def relabelled(A: sp.csr_matrix | None, at: np.ndarray, sort: bool = False
               ) -> sp.csr_matrix | None:
    """``A`` with column ``j`` renamed ``at[j]``: each row's entries stay in
    their stored order (so ``A @ x[q]`` is ``A @ x`` term for term) unless
    ``sort`` (the per-body rows: ``linear._bordered`` lays out a canonical
    matrix directly, so its row sums move at rounding level)."""
    if A is None:
        return None
    A = A.tocsr()
    out = sp.csr_matrix((A.data.copy() if sort else A.data,
                         at[A.indices].astype(A.indices.dtype), A.indptr), shape=A.shape)
    if sort:
        out.sort_indices()
    return out


def factor_in_order(M: sp.csc_matrix):
    """The ordered columns' factorisation: SuperLU in the order the matrix
    already has (``linear._factor``'s symmetric mode and pivot threshold)."""
    return splu(M, permc_spec="NATURAL", diag_pivot_thresh=0.1, panel_size=1,
                options={"SymmetricMode": True})
