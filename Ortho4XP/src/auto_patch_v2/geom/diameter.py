"""THE PLAN DIAMETER of a point set: the largest distance between two of its
points.

Moved down from ``constraints/apron_trend`` (an apron body's diameter
against the trend window) so ``airport/isolated_seat`` can read the same
number for a cluster's feet (#2063 round 3 amendment A1, the WALLED-BASE
witness).  One implementation, two readers.
"""
from __future__ import annotations

import numpy as np

__all__ = ["plan_diameter"]


def plan_diameter(xy: np.ndarray) -> float:
    """The largest distance between two rows of ``xy`` (``(n, 2)`` plan
    metres).  Taken over the CONVEX HULL where scipy can build one (the
    diameter is always a hull pair), else over the points themselves; a set
    of thousands of points then costs a hull, not N squared."""
    if xy.shape[0] < 2:
        return 0.0
    pts = xy
    if xy.shape[0] > 3:
        try:
            from scipy.spatial import ConvexHull
            pts = xy[ConvexHull(xy).vertices]
        except Exception:                     # degenerate (collinear) input
            pts = xy
    if pts.shape[0] > 4096:                   # never quadratic in N
        pts = pts[:: 1 + pts.shape[0] // 4096]
    d = pts[:, None, :] - pts[None, :, :]
    return float(np.sqrt(np.einsum("ijk,ijk->ij", d, d)).max())
