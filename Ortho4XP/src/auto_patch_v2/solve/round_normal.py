"""ONE QP ROUND'S NORMAL MATRIX, BUILT ONCE AND SHARED BY ITS TRIES (#1270).

A round of :func:`~.design_qp.solve_one_sided` tries the SAME active set at
``λ, 6λ, 36λ, …`` from the SAME iterate.  Each try's least-squares stack is

    A(λ) = [ A0 ; W ; √λ·I ]        W = diag(√w_sel)·A1_sel

and :func:`~.linear._linear_solve` rebuilt ``A(λ)``, transposed it and
multiplied ``A(λ)ᵀA(λ)`` in every try.  SciPy's ``csr_matmat`` takes each
entry of that product as ONE FOLD over the stack's rows in order (the
compiled ``sums += v·b``, fused into an FMA on the shipped wheel —
measured), so the product is

    the fold over A0's rows        — the same in every round of the QP
    continued over W's rows        — the same in every try of the round
    continued over the λ rows      — one term √λ·√λ, on the diagonal only

This module takes the first part ONCE per QP (:class:`Prefix`), continues
it over ``W`` once per round, and finishes each try with its one term —
every continuation by ``csr_matmat`` itself, reading a row whose first
entry is ``1·(the partial sum)`` (an exact copy) before the terms that
follow it, so no fold is ever re-derived in NumPy.  The right-hand side
``A(λ)ᵀ(b − A(λ)x)`` is continued the same way, and the λ rows' residual
``√λ·x − √λ·x`` is an exact zero.  The floored matrix and its bordered
form (``linear._floored``, ``linear._bordered``) are then written into a
structure laid out once per round.

The matrix factorised and the vectors solved are the old path's, array for
array (twin ``tests/auto_patch_v2/test_round_normal.py``): the surface is
byte-identical and the round is shorter.
"""
from __future__ import annotations

import typing as _t

import numpy as np
import scipy.sparse as sp

from .linear import _bordered, _factor, _floored, _normal_back

if _t.TYPE_CHECKING:
    from .fill_order import FillOrder

__all__ = ["Prefix", "RoundNormal"]

#: a product is cut into row blocks of at least this many rows on threads
_BLOCK_MIN_ROWS = 4000


def _product(L: sp.csr_matrix, R: sp.csr_matrix, pool: _t.Any, workers: int
             ) -> sp.csr_matrix:
    """``L @ R``, row blocks of ``L`` on threads: ``csr_matmat`` computes
    each output row from that row alone, so the blocks ARE the product."""
    n = int(L.shape[0])
    k = max(1, min(int(workers), n // _BLOCK_MIN_ROWS))
    if pool is None or k == 1:
        return L @ R
    cuts = np.linspace(0, n, k + 1).astype(np.int64)
    return sp.vstack(list(pool.map(lambda ab: L[int(ab[0]):int(ab[1])] @ R,
                                   zip(cuts[:-1], cuts[1:], strict=True))),
                     format="csr")


def _lead_one(T: sp.csr_matrix, lead: int) -> sp.csr_matrix:
    """``T`` (``n`` rows) with ``1`` at column ``i`` put FIRST in each row
    ``i`` and ``T``'s own columns shifted by ``lead``: the row that reads a
    partial sum, then continues it over ``T``'s terms."""
    n = int(T.shape[0])
    at = T.indptr[:-1]
    idx = np.insert(T.indices.astype(np.int64) + lead, at, np.arange(n))
    dat = np.insert(np.asarray(T.data, float), at, 1.0)
    return sp.csr_matrix((dat, idx, T.indptr.astype(np.int64) + np.arange(n + 1)),
                         shape=(n, lead + int(T.shape[1])))


class Prefix:
    """The always-on rows' share of every round's product: ``A0ᵀA0``, taken
    once per QP."""

    def __init__(self, A0: sp.csr_matrix, b0: np.ndarray, A0T: sp.csr_matrix,
                 pool: _t.Any = None, workers: int = 1) -> None:
        self.A0, self.b0, self.A0T = A0, b0, A0T
        self.P = _product(A0T, A0, pool, workers)


class RoundNormal:
    """One round's normal matrix (the always-on rows over the active rows
    ``W``, right-hand side ``bW``) and each try's warm-started proximal solve
    on it (:meth:`solve`)."""

    def __init__(self, pre: Prefix, W: sp.csr_matrix, bW: np.ndarray,
                 U: sp.csr_matrix | None, low_rank: str,
                 pool: _t.Any = None, workers: int = 1,
                 order: "FillOrder | None" = None) -> None:
        self.pre, self.W, self.bW = pre, W, bW
        #: the QP's one fill-reducing ordering (``solve/fill_order``)
        self.order = order
        self.n = n = int(pre.A0.shape[1])
        self.U, self.low_rank = U, low_rank
        #: row i: ``1`` at the partial sum's column i, then W's column i
        self.L = L = _lead_one(W.T.tocsr(), n)
        N = _product(L, sp.vstack([pre.P, W], format="csr"), pool, workers).tocsc()
        col = np.repeat(np.arange(n, dtype=np.int32), np.diff(N.indptr))
        dpos = np.flatnonzero(N.indices == col)
        #: the fold's diagonal (0 where the product has none)
        self.diag = np.zeros(n)
        self.diag[col[dpos]] = N.data[dpos]
        self.N = N
        # THE TRY'S MATRIX IN PLACE: with every column's diagonal already in
        # the product (the common case), a try only rewrites those entries —
        # the floored matrix's off-diagonal entries are the product's own
        # (the binop's ``a + 0``) — and, bordered, the same slots of the
        # bordered form laid out once here
        self.dpos = dpos if dpos.size == n else None
        self.border = None
        if self.dpos is not None and U is not None and low_rank == "bordered":
            B = _bordered(N, U)
            up = U.tocsc().indptr.astype(np.int64)
            self.border = (B.data, B.indices, B.indptr, dpos + up[:-1], int(B.shape[0]))
        #: the try's matrix (bordered, or the product's own) laid out in the
        #: QP's order, once per round (``None`` before the order is taken)
        self.lay = None
        if order is not None and self.dpos is not None:
            self.lay = order.layout(B if self.border is not None else N)
        # the λ term's kernel input (``_diagonal``)
        self._l_idx = np.column_stack([np.arange(n), n + np.arange(n)]).ravel()
        self._l_ptr = np.arange(0, 2 * n + 1, 2, dtype=np.int64)
        nz = self.diag != 0.0
        self._r_ptr = np.concatenate([[0], np.cumsum(nz), int(nz.sum()) + np.arange(1, n + 1)])
        self._r_idx = np.concatenate([np.flatnonzero(nz), np.arange(n)])
        self._r_base = self.diag[nz]

    def _diagonal(self, root: float) -> np.ndarray:
        """The fold's diagonal continued by ``√λ·√λ``, by ``csr_matmat``:
        row ``i`` of ``L`` reads ``1·s_i`` then ``√λ·√λ``."""
        n = self.n
        L = sp.csr_matrix((np.column_stack([np.ones(n), np.full(n, root)]).ravel(),
                           self._l_idx, self._l_ptr), shape=(n, 2 * n))
        R = sp.csr_matrix((np.concatenate([self._r_base, np.full(n, root)]),
                           self._r_idx, self._r_ptr), shape=(2 * n, n))
        return np.asarray((L @ R).diagonal(), float)

    def solve(self, x0: np.ndarray, lam: float, c: np.ndarray | None) -> np.ndarray:
        """:func:`~.linear._linear_solve` (``normal``, warm start and
        proximal centre ``x0``) of ``[A0; W; √λ I] x ≈ [b0; bW; √λ x0]``."""
        n = self.n
        root = float(np.sqrt(lam))
        dg = self._diagonal(root)
        U = self.U
        if self.dpos is None:            # a column with no diagonal yet
            back = _normal_back(_floored(self._off() + sp.diags(dg, format="csc")),
                                U, self.low_rank,
                                _factor if self.order is None else self.order.factor)
        else:
            # ``linear._floored``: its ε from this diagonal, added by the
            # binop's own ``a + b``
            md = dg + 1e-12 * max(1.0, float(abs(dg).max()))
            if self.border is not None:
                data, indices, indptr, dslot, nb = self.border
                data = data.copy()
                data[dslot] = md
                lu = self._lu(sp.csc_matrix((data, indices, indptr), shape=(nb, nb)))

                def back(r: np.ndarray, rc: np.ndarray) -> np.ndarray:
                    return np.asarray(lu.solve(np.concatenate([r, rc]))[:n], float)
            else:
                data = self.N.data.copy()
                data[self.dpos] = md
                back = _normal_back(sp.csc_matrix((data, self.N.indices, self.N.indptr),
                                                  shape=(n, n)), U, self.low_rank,
                                    self._lu)
        x0 = np.asarray(x0, float)
        pre = self.pre
        r_lam = root * x0 - (root * sp.identity(n, format="csr")) @ x0   # ±0
        head = pre.A0T @ (pre.b0 - pre.A0 @ x0)
        rhs = self.L @ np.concatenate([head, self.bW - self.W @ x0]) + root * r_lam
        rc = None if U is None else np.asarray(c, float) - U @ x0
        return x0 + back(rhs, rc)

    def _lu(self, M: sp.csc_matrix):
        """A try's factorisation of the round's laid-out matrix."""
        return _factor(M) if self.order is None else self.order.factor(M, self.lay)

    def _off(self) -> sp.csc_matrix:
        """The product without its diagonal (the rare column with none)."""
        N = self.N
        col = np.repeat(np.arange(self.n), np.diff(N.indptr))
        off = N.indices != col
        ptr = np.concatenate([[0], np.cumsum(np.bincount(col[off], minlength=self.n))])
        return sp.csc_matrix((N.data[off], N.indices[off], ptr), shape=N.shape)
