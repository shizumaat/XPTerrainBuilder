"""THE FEET NEIGHBOUR GRAPH, REFERENCE — the Euclidean MST over one
body's feet as an ORDERED edge list, pure Python (stdlib only).

MOVED here from ``model/ground_fit`` (#59): ``geom/feet_graph`` (the
fast Delaunay path) falls back to this loop and the twins compare against
it, and ``geom`` is the LEAF — it may import nothing of v2 — so the
reference lives in the leaf and ``model/ground_fit.ground_fit`` takes the
graph as an injected ``pairs`` argument.  One derivation site; never a
copy.
"""
from __future__ import annotations

import math
import typing as _t

__all__ = ["neighbour_pairs"]


def neighbour_pairs(pts: _t.Sequence[tuple[float, float]]
                    ) -> list[tuple[int, int, float]]:
    """THE NEIGHBOUR GRAPH over feet in plan: ``(a, b, distance)`` for
    each edge of the feet's Euclidean MINIMUM SPANNING TREE.

    11x (2) allows "Delaunay or nearest-neighbour"; the EMST is the
    nearest-neighbour graph made CONNECTED — every foot's own nearest
    neighbour is an EMST edge, and the extra edges are exactly the ones
    that join otherwise separate clusters of feet (two columns' corner
    pairs, say), which a bare nearest-neighbour graph leaves untested
    and therefore always feasible.  It is a subgraph of the Delaunay
    triangulation, so no pair it reads is a pair the Delaunay would call
    non-adjacent.

    Pure Python, O(n^2) Prim — the feet of one body, never a corpus; and
    this module imports stdlib only, so ``geom``'s pure
    callers and the twins may read it without scipy.

    THIS FUNCTION IS THE REFERENCE AND THE DEFAULT.  It is also, on the
    real maxima, 646.5 s of a 652.3 s TFFG pack stage (findings
    ``pack-read-profile-20260918.md`` §1.3) — so the callers that see
    the big bodies inject ``pairs=geom.feet_graph.neighbour_pairs_fast``
    (spec ``pack-read-once-fast-spec.md`` row 1), which reproduces THIS
    list exactly, order and float, from a Delaunay candidate graph.  The
    twins compare against this loop; it is never deleted.
    """
    n = len(pts)
    if n < 2:
        return []
    INF = float("inf")
    best = [INF] * n
    link = [-1] * n
    seen = [False] * n
    best[0] = 0.0
    out: list[tuple[int, int, float]] = []
    for _ in range(n):
        u, du = -1, INF
        for i in range(n):
            if not seen[i] and best[i] < du:
                u, du = i, best[i]
        if u < 0:
            break                      # unreachable: distances are finite
        seen[u] = True
        if link[u] >= 0:
            out.append((link[u], u, du))
        ux, uy = pts[u]
        for v in range(n):
            if seen[v]:
                continue
            vx, vy = pts[v]
            d = math.hypot(ux - vx, uy - vy)
            if d < best[v]:
                best[v], link[v] = d, u
    return out
