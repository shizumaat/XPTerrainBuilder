"""A DECK'S END EDGE, CORNER TO CORNER (#2239 / #2241; owner sim read
2026-11-26T15:02Z: "the weld must span the deck's full width including
shoulders").

A pack deck's END LINE (``planar/deck_bridge``: the stations where the
airport's pavement drives onto it, ``airport/airside_deck_seat.
facing_contacts``) covers only the run of its ring with PAVEMENT outside.
A deck wider than the pavement it carries -- a taxiway with its shoulders,
two parallel taxiways side by side -- has the rest of that side facing
ground, and nothing held it: MEASURED CYYZ 1.0.585, the T deck's end
lines 55 of its 68 m sides, the M deck's 39-43 of 68 m, the shoulder
standing 0.58-1.44 m under the deck edge.

THE EDGE is the ring's side the end line lies on: from the line's ring
edges, every consecutive ring edge that still FACES THE SAME WAY -- its
outward normal nearer the line's than square to it (the bisector between
facing the taxiway and facing the road under it; no number is chosen) --
up to the corners where the ring turns toward the road.  Pure plan
geometry; nothing here names a pack or an airport.
"""
from __future__ import annotations

import math
import typing as _t

__all__ = ["end_edge", "on_edge"]

XY = tuple[float, float]

#: cos 45 deg: an edge faces the end line's way when its normal is nearer
#: the line's normal than square to it
_FACING = math.sqrt(0.5)


def _ring(ring: _t.Sequence[XY]) -> list[XY]:
    pts = [(float(p[0]), float(p[1])) for p in ring]
    if len(pts) > 1 and pts[0] == pts[-1]:
        pts = pts[:-1]
    return pts


def _seg_dist(p: XY, a: XY, b: XY) -> float:
    dx, dy = b[0] - a[0], b[1] - a[1]
    L2 = dx * dx + dy * dy
    t = 0.0 if L2 <= 0.0 else max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / L2))
    return math.hypot(p[0] - a[0] - t * dx, p[1] - a[1] - t * dy)


def _normal(a: XY, b: XY, ccw: bool) -> "XY | None":
    """The outward unit normal of ring edge ``a -> b``."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    L = math.hypot(dx, dy)
    if L <= 1e-9:
        return None
    return (dy / L, -dx / L) if ccw else (-dy / L, dx / L)


def _run(hit: list[int], n: int) -> tuple[int, int]:
    """The hit ring edges as ONE run along the ring ``(lo, hi)``, ``hi``
    past ``n`` where it wraps past vertex 0."""
    lo, hi = hit[0], hit[-1]
    if len(hit) > 1 and hi - lo > n // 2:
        _g, k = max((hit[k + 1] - hit[k], k) for k in range(len(hit) - 1))
        lo, hi = hit[k + 1], hit[k] + n
    return lo, hi


def end_edge(ring: _t.Sequence[XY], line: _t.Sequence[XY]) -> list[XY]:
    """The polyline of ``ring``'s side that end line ``line`` (its stations,
    in the ring's frame) lies on, corner to corner (module doc); ``[]``
    where the ring or the line is degenerate."""
    pts = _ring(ring)
    n = len(pts)
    if n < 3 or not line:
        return []
    area = sum(pts[i][0] * pts[(i + 1) % n][1] - pts[(i + 1) % n][0] * pts[i][1]
               for i in range(n))
    ccw = area > 0.0
    hit = sorted({min(range(n), key=lambda i, q=q: _seg_dist(q, pts[i], pts[(i + 1) % n]))
                  for q in line})
    nx = ny = 0.0
    for i in hit:
        a, b = pts[i], pts[(i + 1) % n]
        m = _normal(a, b, ccw)
        if m is not None:
            w = math.hypot(b[0] - a[0], b[1] - a[1])
            nx, ny = nx + m[0] * w, ny + m[1] * w
    L = math.hypot(nx, ny)
    if L <= 1e-9:
        return []
    nx, ny = nx / L, ny / L

    def facing(i: int) -> bool:
        m = _normal(pts[i % n], pts[(i + 1) % n], ccw)
        return m is None or m[0] * nx + m[1] * ny >= _FACING

    lo, hi = _run(hit, n)
    steps = hi - lo
    while steps < n - 1 and facing(lo - 1):
        lo, steps = lo - 1, steps + 1
    while steps < n - 1 and facing(hi + 1):
        hi, steps = hi + 1, steps + 1
    return [pts[i % n] for i in range(lo, hi + 2)]


def on_edge(p: XY, edge: _t.Sequence[XY], tol: float) -> bool:
    """``p`` lies within ``tol`` of polyline ``edge``."""
    return any(_seg_dist(p, edge[i], edge[i + 1]) <= tol for i in range(len(edge) - 1))
