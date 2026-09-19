"""THE FEET NEIGHBOUR GRAPH, FAST — the Euclidean MST over one body's
feet, emitted edge-for-edge, order-for-order, length-for-length the way
``model/ground_fit.neighbour_pairs`` emits it, in O(n log n).

WHY THIS MODULE EXISTS (spec ``pack-read-once-fast-spec.md`` row 1;
findings ``pack-read-profile-20260918.md`` §1.3).  The shipped Prim is
pure-Python O(n^2) because ``model`` may import neither ``scipy`` nor
``numpy`` (M0 §1).  On the real maxima that is 444 M ``math.hypot``
calls: 39.6 s of a TNCM pack stage and **646.5 s of TFFG's 652.3 s**,
one call with n = 86,592 feet.  ``model`` keeps its pure reference — it
is still the DEFAULT and it is what the twins compare against — and the
two callers that see the big bodies (``planar/group.derive``,
``constraints/foot_rows``) inject :func:`neighbour_pairs_fast`.

THE LAW IS UNCHANGED.  The contract is not "an MST"; it is the SHIPPED
PRIM'S OWN LIST: start at index 0; the next vertex is the unseen one
with the smallest ``best``, LOWEST INDEX on a tie; ``link[v]`` is the
EARLIEST-ADDED tree vertex achieving ``best[v]`` (strict ``<`` update);
edges come out in pick order as ``(link[u], u, best[u])`` with ``best``
= ``math.hypot``.  ``ground_fit`` reads that ORDER (its ``worst`` is the
FIRST pair reaching the maximum residual), and ties are not a corner
case — a rectangle's four feet tie by construction and the real TFFG
input carries 52,846 repeated lengths in 86,591 edges.

WHY A CANDIDATE GRAPH REPRODUCES IT EXACTLY (spec §B.1).

  (i) Every MST edge ``ab`` has an EMPTY CLOSED DIAMETRAL DISK: a point
  ``c`` inside it satisfies ``|ac|, |bc| < |ab|`` strictly, so ``ab``
  would not survive the cycle property.  An edge with an empty closed
  diametral disk is strictly Gabriel, and a strictly Gabriel edge lies
  in EVERY Delaunay triangulation of the points — cocircular
  degeneracies included.

  (ii) At every Prim step the minimum crossing weight ``m`` is achieved
  only by edges that each lie in SOME MST (cut property), hence by (i)
  every ``(u, v)`` with ``d(u, v) = m`` across the cut is a Delaunay
  edge.

  Therefore, at every step, the set of minimum candidates, the
  lowest-index winner AND the earliest-added ``link`` are the same on
  the Delaunay graph as on the complete graph.  (The candidate graph is
  a SUBGRAPH, so ``best_fast[v] >= best_shipped[v]`` always; (ii) makes
  them equal whenever ``v`` is popped, and the achiever the shipped loop
  recorded is itself a Delaunay neighbour, so the earliest achiever is
  the same vertex.)  A DIFFERENT VALID TRIANGULATION — Qhull on arm64
  against Qhull on x86 — cannot change the output: the guarantee is
  platform-stable BY CONSTRUCTION, not by luck.  Distances are
  ``math.hypot`` on the ORIGINAL coordinates, i.e. CPython's own
  algorithm on the same doubles, never ``np.hypot`` (libm, last-ulp
  platform-varying).

THE TRANSLATION IS LOAD-BEARING.  Qhull is fed the unique points
TRANSLATED TO THEIR MEAN.  Un-centred — airport feet are ~1e6 m apart
from the origin with 0.4 m spacing — Qhull's precision merging discarded
85,538 of TFFG's 86,592 points as "coplanar" (measured, spec §B.1).  The
translation feeds QHULL ONLY; no length is ever computed from it.

DEGENERATE INPUT FALLS BACK, IT DOES NOT IMPROVISE: fewer than 3 unique
points, collinear sets (``QhullError``), a non-empty ``tri.coplanar``, a
short edge list, any non-finite coordinate, or n below
:data:`SMALL_N` — all return the pure reference's own answer.  Fallbacks
are counted (:func:`fallback_count`) and a fallback on a BIG input logs
one line, because that is the 345 s case.
"""
from __future__ import annotations

import collections as _collections
import heapq as _heapq
import logging as _logging
import math as _math
import typing as _t

import numpy as _np
# MODULE-TOP, deliberately: a function-level third-party import is invisible
# to PyInstaller AND to the suite (the highspy precedent, 2026-09-10).  No
# ``Ortho4XP.spec`` hidden import is needed — ``planar/shapes.py:76`` already
# imports ``scipy.spatial`` at module level, which pulls ``scipy.spatial._qhull``
# (``Delaunay``/``QhullError``'s home) into the freeze; this import makes
# THIS module's dependency statically visible too.
from scipy.spatial import Delaunay as _Delaunay, QhullError as _QhullError

from ..model.ground_fit import neighbour_pairs

__all__ = ["neighbour_pairs_fast", "fallback_count", "reset_fallback_count",
           "SMALL_N", "BIG_N"]

_LOG = _logging.getLogger(__name__)

#: Below this, delegate to the reference: Qhull's set-up costs more than
#: the O(n^2) loop saves, and the small case is the twins' anchor.  ONE
#: derivation site for "which feet are neighbours" either way.
SMALL_N = 64

#: A fallback at or above this many points is the pathological case the
#: whole module exists for (TFFG's single n = 86,592 call was 345 s), so
#: it says so once in the log rather than silently costing minutes.
BIG_N = 20_000

_FALLBACKS = 0


def fallback_count() -> int:
    """How many :func:`neighbour_pairs_fast` calls fell back to the pure
    reference for a reason OTHER than ``n < SMALL_N`` (which is the
    designed small path, not a degeneracy).  Reported as
    ``mst_fallback`` in the group report."""
    return _FALLBACKS


def reset_fallback_count() -> None:
    """Zero the counter (the group report reads a per-``derive`` delta;
    tests read an absolute)."""
    global _FALLBACKS
    _FALLBACKS = 0


def _fallback(pts: _t.Sequence[tuple[float, float]], why: str
              ) -> list[tuple[int, int, float]]:
    global _FALLBACKS
    _FALLBACKS += 1
    if len(pts) >= BIG_N:
        _LOG.warning("[feet_graph] fallback to the O(n^2) reference on "
                     "n=%d feet (%s) — this call is minutes, not seconds",
                     len(pts), why)
    return neighbour_pairs(pts)


def neighbour_pairs_fast(pts: _t.Sequence[tuple[float, float]]
                         ) -> list[tuple[int, int, float]]:
    """``model/ground_fit.neighbour_pairs``'s OWN ordered edge list, from
    a Delaunay candidate graph and a heap (module doc).

    The returned list is ``==`` to the reference's, float for float.
    """
    n = len(pts)
    if n < 2:
        return []
    if n < SMALL_N:
        return neighbour_pairs(pts)      # the designed small path

    P = _np.asarray(pts, dtype=float)
    if P.ndim != 2 or P.shape[1] != 2:
        return _fallback(pts, "not a 2-column point array")
    if not bool(_np.isfinite(P).all()):
        return _fallback(pts, "non-finite coordinate")

    uq, inv = _np.unique(P, axis=0, return_inverse=True)
    inv = _np.asarray(inv).reshape(-1)
    if len(uq) < 3:
        return _fallback(pts, "fewer than 3 distinct points")

    try:
        # TRANSLATED TO THE MEAN — Qhull only (module doc).
        tri = _Delaunay(uq - uq.mean(axis=0))
    except _QhullError as error:
        return _fallback(pts, f"QhullError: {error.__class__.__name__}")
    except Exception as error:          # degenerate input of any other shape
        return _fallback(pts, f"Delaunay failed: {error!r}")
    if len(tri.coplanar):
        # Qhull dropped points: the candidate graph is not guaranteed to
        # contain every MST edge any more.
        return _fallback(pts, f"{len(tri.coplanar)} coplanar points dropped")

    # --- the candidate graph -------------------------------------------------
    # Delaunay adjacency over UNIQUE points, expanded over each duplicate
    # class, plus the zero-length edges inside every class.
    cls: dict[int, list[int]] = _collections.defaultdict(list)
    for i, k in enumerate(inv.tolist()):
        cls[k].append(i)
    indptr, indices = tri.vertex_neighbor_vertices
    indptr = indptr.tolist()
    indices = indices.tolist()

    adj: list[list[tuple[int, float]]] = [[] for _ in range(n)]
    hypot = _math.hypot
    for a in range(len(uq)):
        ca = cls[a]
        for b in indices[indptr[a]:indptr[a + 1]]:
            if a >= b:
                continue                 # each unique pair once
            cb = cls[b]
            for i in ca:
                xi, yi = pts[i]
                for j in cb:
                    xj, yj = pts[j]
                    d = hypot(xi - xj, yi - yj)
                    adj[i].append((j, d))
                    adj[j].append((i, d))
    for members in cls.values():
        if len(members) > 1:
            for i in members:
                for j in members:
                    if i != j:
                        adj[i].append((j, 0.0))

    # --- Prim, the shipped selection rule, on a heap -------------------------
    INF = _math.inf
    best = [INF] * n
    link = [-1] * n
    seen = [False] * n
    best[0] = 0.0
    heap: list[tuple[float, int]] = [(0.0, 0)]
    out: list[tuple[int, int, float]] = []
    push, pop = _heapq.heappush, _heapq.heappop
    while heap:
        du, u = pop(heap)
        if seen[u] or du != best[u]:
            continue                     # lazy deletion
        seen[u] = True
        if link[u] >= 0:
            out.append((link[u], u, du))
        for v, d in adj[u]:
            if not seen[v] and d < best[v]:
                # strict ``<``: the EARLIEST-added achiever keeps ``link``
                best[v] = d
                link[v] = u
                push(heap, (d, v))

    if len(out) != n - 1:
        # disconnected candidate graph (Qhull gave something we cannot
        # trust): the reference is the answer, not a partial forest.
        return _fallback(pts, f"{len(out)} edges for {n} points")
    return out
