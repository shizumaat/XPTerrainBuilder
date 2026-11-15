"""THE SLOPE BOUNDS OF A SET OF SOURCES INSIDE A REGION: how high and how
low a point may stand when it climbs at most ``grade`` from every source
along the shortest path INSIDE the region (spec 2068 A3 R5:
``hi = min_f z_f + g d(f, v)``, ``lo = max_f z_f - g d(f, v)``, ``d`` the
shortest path inside the union of a road's faces).

The shortest path between two points of a polygon bends only at its
vertices, so ``d`` is read on the VISIBILITY GRAPH of the points given (the
region's own vertices among them): two points see each other when the
segment between them stays inside the region.  ``geom`` imports nothing
of v2."""
from __future__ import annotations

import heapq

import numpy as np
import shapely

__all__ = ["slope_bounds"]


def slope_bounds(xy: np.ndarray, region, sources: "dict[int, float]", grade: float,
                 tol: float = 0.01) -> "tuple[np.ndarray, np.ndarray]":
    """``(lo, hi)`` over the points ``xy`` ``(n, 2)``: ``hi[v] = min over
    the sources f of z_f + grade * d(f, v)`` and ``lo[v] = max of z_f -
    grade * d(f, v)``, ``d`` the shortest path inside ``region`` (grown by
    ``tol``) through the points.  ``sources`` maps a point's index to its
    height.  A point no source reaches reads ``+inf`` / ``-inf``."""
    pts = np.asarray(xy, dtype=float).reshape(-1, 2)
    n = len(pts)
    lo = np.full(n, -np.inf)
    hi = np.full(n, np.inf)
    if n == 0 or not sources:
        return lo, hi
    adj = _visibility(pts, region.buffer(tol))
    hi[:] = _relax(adj, {i: z for i, z in sources.items()}, grade, n)
    lo[:] = -_relax(adj, {i: -z for i, z in sources.items()}, grade, n)
    return lo, hi


def _visibility(pts: np.ndarray, region) -> "list[list[tuple[int, float]]]":
    """Every pair of points whose segment stays inside ``region``, with its
    length."""
    n = len(pts)
    shapely.prepare(region)
    i, j = np.triu_indices(n, 1)
    adj: list[list[tuple[int, float]]] = [[] for _ in range(n)]
    if len(i) == 0:
        return adj
    segs = shapely.linestrings(np.stack([pts[i], pts[j]], axis=1))
    ok = shapely.covers(region, segs)
    d = np.hypot(*(pts[i] - pts[j]).T)
    for a, b, w in zip(i[ok].tolist(), j[ok].tolist(), d[ok].tolist(), strict=True):
        adj[a].append((b, w))
        adj[b].append((a, w))
    return adj


def _relax(adj, start: "dict[int, float]", grade: float, n: int) -> np.ndarray:
    """``min over the starts s of start[s] + grade * d(s, v)`` (Dijkstra
    from every start at once)."""
    best = np.full(n, np.inf)
    heap = [(float(z), int(i)) for i, z in start.items()]
    for z, i in heap:
        best[i] = min(best[i], z)
    heapq.heapify(heap)
    while heap:
        z, i = heapq.heappop(heap)
        if z > best[i]:
            continue
        for j, w in adj[i]:
            c = z + grade * w
            if c < best[j]:
                best[j] = c
                heapq.heappush(heap, (c, j))
    return best
