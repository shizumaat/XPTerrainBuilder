"""A DECK AUTHORED ON A GRADE IS ONE PLATE (#2086 / #2065 R3).

``deck_signature`` reads a member's PLATE as its faces in the family's deck
plane: the largest-area bin (``[bridge] deck_plane_bin_m``) of near-
horizontal faces.  A deck authored on a grade crosses several bins, and a
quad of it is split along its diagonal into two triangles whose mean
heights fall in different bins: the plate then keeps ONE triangle of the
quad.  LEMG's motorway viaduct (a 247 m deck falling 2.8 m end to end, three
quads) read as a wedge tapering to a point 25 m short of its real NE edge:
its end lines, its ring and the route end the bridge witness reads on it
(W7: "run-on 63 m") all sat on the wedge.

THE RULE.  The plate is grown over the near-horizontal faces of its own
components that share an edge with it, transitively — the deck's connected
driven surface — when that whole surface stands over the family's lowest
feet by at least ``[bridge] deck_min_elevation_m`` (the plane's own
elevation law).  A surface that runs down to the feet anywhere is a deck
with its RAMP in the same component (OTHH: "a ramp runs down from the plane
to the ground within one component"), and its plate stays the plane's
faces, as the R12 seats the owner accepted read it.  A flat deck's
connected surface is its plane already: nothing grows.

Nothing here names a pack, a resource or an airport.
"""
from __future__ import annotations

import numpy as np

__all__ = ["grown_plate"]

#: corners are joined by their authored position at this quantum (m): an
#: exporter's per-seam duplicate vertices share an edge (``obj8``'s weld)
_WELD_M = 1e-3


def _edges(corners: np.ndarray) -> np.ndarray:
    """``(n, 3)`` edge keys of ``(n, 3, 3)`` face corners: each edge's two
    welded corner ids, ordered, packed into one integer."""
    q = np.round(corners.reshape(-1, 3) / _WELD_M).astype(np.int64)
    _u, ids = np.unique(q, axis=0, return_inverse=True)
    ids = ids.reshape(-1, 3).astype(np.int64)
    big = np.int64(ids.max() + 1 if ids.size else 1)
    out = np.empty((ids.shape[0], 3), dtype=np.int64)
    for k, (i, j) in enumerate(((0, 1), (1, 2), (2, 0))):
        a, b = ids[:, i], ids[:, j]
        out[:, k] = np.minimum(a, b) * big + np.maximum(a, b)
    return out


def grown_plate(corners: np.ndarray, near: np.ndarray, plane: np.ndarray,
                high: np.ndarray) -> np.ndarray:
    """The plate's faces (module doc): ``plane`` (the in-plane faces) grown
    over the ``near`` faces (near-horizontal, of the plate's own components)
    that share an edge with it, transitively — when every face so reached is
    ``high`` (over the family's feet by the deck elevation); else ``plane``.
    ``corners`` are every face's authored ``(x, y, z)``, ``(n, 3, 3)``."""
    plane = np.asarray(plane, bool)
    cand = np.asarray(near, bool) | plane
    if not plane.any() or int(cand.sum()) == int(plane.sum()):
        return plane
    idx = np.nonzero(cand)[0]
    keys = _edges(np.asarray(corners, float)[idx])
    by_edge: dict[int, list[int]] = {}
    for r, row in enumerate(keys.tolist()):
        for e in row:
            by_edge.setdefault(e, []).append(r)
    seen = plane[idx].copy()
    todo = np.nonzero(seen)[0].tolist()
    while todo:
        r = todo.pop()
        for e in keys[r].tolist():
            for s in by_edge[e]:
                if not seen[s]:
                    seen[s] = True
                    todo.append(s)
    got = np.zeros_like(plane)
    got[idx[seen]] = True
    if not np.asarray(high, bool)[got].all():
        return plane
    return got
