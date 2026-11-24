"""ONE FILL-REDUCING ORDERING PER QP (#1270, lane ``lsplu``).

Every try of :func:`~.design_qp.solve_one_sided` factorises a matrix of the
same size and NEARLY the same pattern — the always-on rows' normal matrix,
the round's active one-sided rows, ``λ`` on the diagonal, the per-body
border of ``linear._bordered`` — and ``linear._factor`` let SuperLU order
every one of them afresh (``MMD_AT_PLUS_A``).  That minimum-degree ordering
is most of each factorisation: HECA stage 2 (n 42,662 bordered, 2.0 M
entries) 159 ms per try, 89 ms in a held order; KBUF 6.5 → 3.9 ms at
n 4,601.  The active set moves a few hundred entries of the pattern from
round to round, and an order taken on one round costs the QP's other
rounds about 1 % more fill (KBUF).

:class:`FillOrder` therefore orders ONCE per QP: its first round factorises
as before and OFFERS SuperLU's column order; the QP COMMITS it between
rounds (never inside one, so a round's concurrent tries read the same
state); every later round lays its matrix out in that order once
(:meth:`FillOrder.layout`, both index permutations by two O(nnz)
transposes) and each try gathers its values into it and factorises in the
order it has (``NATURAL``; ``panel_size`` 1, a further 25 % off these
matrices).  The order is the QP's OWN: a stage's later QPs carry other
active sets (HECA stage 2: an order held from the stage's first QP cost
the second 64 % more fill), and the border's rows stay where SuperLU put
them (placed last: +28 % fill at HECA).

Products, residuals and normal matrices are untouched; only the
factorisation's summation order changes, so a solve moves at rounding level
(replays of KBUF, KRDU, KDEN, KATL, KDFW and HECA: every patch body, graded
surface and seat file byte-identical; HECA's sidecar moves one diagnostic,
five platforms' ``reach_lo_binding`` hop count by one).  NOT exact by
construction: RULINGS 2026-11-23e/24e are the bar this is measured against.
"""
from __future__ import annotations

import threading

import numpy as np
import scipy.sparse as sp
from scipy.sparse.linalg import splu

from .linear import _factor

__all__ = ["FillOrder"]


class _Permuted:
    """``M⁻¹ r`` by the factorisation of ``M[q][:, q]``."""

    def __init__(self, lu, q: np.ndarray) -> None:
        self.lu, self.q = lu, q

    def solve(self, r: np.ndarray) -> np.ndarray:
        y = self.lu.solve(np.asarray(r)[self.q])
        out = np.empty_like(y)
        out[self.q] = y
        return out


class FillOrder:
    """One QP's column order (module docstring): ``q[i]`` is the original
    column at position ``i``."""

    def __init__(self) -> None:
        self.q: np.ndarray | None = None
        self._offer: np.ndarray | None = None
        self._lock = threading.Lock()

    def commit(self) -> None:
        """Between rounds: the first order offered becomes THE order."""
        if self.q is None and self._offer is not None:
            self.q = self._offer

    def layout(self, M: sp.csc_matrix) -> tuple | None:
        """``M[q][:, q]``'s CSC structure and, per entry, where its value
        sits in ``M.data`` (``None`` while no order is committed or ``M`` is
        another size): the columns gathered in order, the rows renamed, and
        two transposes (counting sorts) leave every column's rows sorted."""
        q = self.q
        n = int(M.shape[0])
        if q is None or q.size != n:
            return None
        at = np.empty(n, dtype=np.int64)
        at[q] = np.arange(n)
        lens = np.diff(M.indptr)[q]
        ptr = np.zeros(n + 1, dtype=np.int64)
        np.cumsum(lens, out=ptr[1:])
        nnz = int(ptr[-1])
        src = np.repeat(M.indptr[q].astype(np.int64) - ptr[:-1], lens) + np.arange(nnz)
        idx_t = np.int64 if max(n, nnz) >= np.iinfo(np.int32).max else np.int32
        C = sp.csc_matrix((src.astype(np.float64) + 1.0, at[M.indices[src]].astype(idx_t),
                           ptr.astype(idx_t)), shape=M.shape)
        P = C.tocsr().tocsc()
        return P.indices, P.indptr, P.data.astype(np.int64) - 1

    def factor(self, M: sp.csc_matrix, layout: tuple | None = None):
        """``linear._factor(M)`` while no order is committed (offering its
        order); after, the factorisation of ``M`` in the order
        (``layout``: :meth:`layout` of ``M``'s structure when held)."""
        q = self.q
        if q is None or q.size != M.shape[0]:
            lu = _factor(M)
            with self._lock:
                if self._offer is None:
                    self._offer = np.argsort(lu.perm_c)
            return lu
        idx, ptr, src = self.layout(M) if layout is None else layout
        Mp = sp.csc_matrix((M.data[src], idx, ptr), shape=M.shape)
        return _Permuted(splu(Mp, permc_spec="NATURAL", diag_pivot_thresh=0.1, panel_size=1,
                              options={"SymmetricMode": True}), q)
