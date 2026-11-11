"""THE COLLAPSED SPIKE: a ring vertex whose two edges fold back onto each
other with no width between them -- the floating-point residue of an edge
two shapes shared, left when one is subtracted from the other.

GEOS calls such a ring VALID (the fold's vertex stands a hair off the edge
it folds back along), but any op that moves a coordinate on either edge
-- a densify, a snap -- can carry it across, and the next overlay refuses
the shape (``TopologyException: side location conflict``).  MEASURED EGKK
(2026-11-10): a page minus its ``#beyond`` lot kept an 82 m spike 8.8e-14 m
wide along the lot's edge; the plateau cut's densify crossed it and the
whole airport lost its patch.

:func:`without_collapsed_spikes` drops every such vertex (repeatedly: one
removal can expose the next).  A spike narrower than ``width_m`` carries
no area to speak of, so nothing a reader can see moves; every other vertex
stays exactly where it is.  ``geom`` imports nothing of v2.
"""
from __future__ import annotations

import math

from shapely.geometry import Polygon

__all__ = ["without_collapsed_spikes"]

# a fold narrower than this is floating-point residue, never geometry
_FP_SPIKE_WIDTH_M = 1e-6


def _fold_free(cs: list, width_m: float) -> list:
    """The ring ``cs`` (open: no repeated closing point) with every
    collapsed-spike vertex removed."""
    cs = [c for k, c in enumerate(cs) if c != cs[k - 1]] if len(cs) > 1 else list(cs)
    changed = True
    while changed and len(cs) >= 3:
        changed = False
        for k in range(len(cs)):
            a, v, b = cs[k - 1], cs[k], cs[(k + 1) % len(cs)]
            ux, uy = v[0] - a[0], v[1] - a[1]
            wx, wy = b[0] - v[0], b[1] - v[1]
            longest = max(math.hypot(ux, uy), math.hypot(wx, wy))
            if longest <= 0.0:
                continue
            width = abs(ux * wy - uy * wx) / longest
            if width <= width_m and ux * wx + uy * wy < 0.0:
                del cs[k]
                cs = [c for j, c in enumerate(cs) if c != cs[j - 1]]
                changed = True
                break
    return cs


def without_collapsed_spikes(poly: Polygon, width_m: float = _FP_SPIKE_WIDTH_M):
    """``poly`` with every collapsed spike removed from each of its rings:
    the same object when it has none, an empty Polygon when its exterior
    collapses, a hole dropped when it does."""
    if poly is None or poly.is_empty:
        return poly
    rings = [[(float(x), float(y)) for x, y in list(r.coords)[:-1]]
             for r in (poly.exterior, *poly.interiors)]
    clean = [_fold_free(cs, width_m) for cs in rings]
    if all(len(c) == len(r) for c, r in zip(clean, rings, strict=True)):
        return poly
    if len(clean[0]) < 3:
        return Polygon()
    return Polygon(clean[0], [h for h in clean[1:] if len(h) >= 3])
