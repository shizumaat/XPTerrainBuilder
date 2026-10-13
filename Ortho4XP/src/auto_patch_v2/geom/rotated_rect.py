"""The ONE oriented-envelope guard (owner 2026-09-04, 2026-10-04).

A leaf: no v2 import and no geometry library (numpy only), so ``geom``,
``model`` and every layer above may read it.
"""
from __future__ import annotations

import numpy as np

__all__ = ["rotated_rectangle", "long_axis"]


def rotated_rectangle(poly):
    """``poly.minimum_rotated_rectangle`` with the numeric noise silenced.

    shapely 2.1's ``oriented_envelope`` (the numpy path, GEOS < 3.12)
    divides by every hull edge's components and lets numpy emit
    ``divide by zero`` / ``invalid value`` RuntimeWarnings on an
    axis-aligned or zero-length edge before masking the result — the
    rectangle it returns is correct (OTHH: every warned face read a sane
    width, 0.4–426 m).  The app shows engine stderr, so the noise looked
    like a defect (owner, 2026-09-04).  ONE spelling of the guard for
    every caller; degenerate input still returns whatever shapely returns
    (a Point / LineString), which each caller already handles.  This module imports
    no geometry library (``model`` re-exports it; test_model): the polygon
    is duck-typed.

    The guard is ``np.errstate`` — numpy's floating-point error state,
    held for this one call and restored on exit, the same spelling as
    ``airport/obj8_grade._eroded`` and ``airport/frame_entry.union``
    (#418).  ``warnings.catch_warnings()`` was process-global filter
    state, not thread-safe; errstate stops the warning at its source
    (numpy's FP-flag check after the ``oriented_envelope`` ufunc) and the
    rectangle is the same bytes.
    """
    with np.errstate(divide="ignore", invalid="ignore"):
        return poly.minimum_rotated_rectangle


def long_axis(rect):
    """``(a, b)`` — the mid-points of the two SHORT sides of a rotated
    rectangle, i.e. its long axis from one end to the other (``planar/
    strip_keepout`` and ``planar/zones`` read a runway's axis off its
    cells' rectangle this way).  ``None`` for a degenerate rectangle."""
    pts = list(rect.exterior.coords)[:4] if hasattr(rect, "exterior") else []
    if len(pts) < 4:
        return None
    sides = [(float(np.hypot(pts[(k + 1) % 4][0] - pts[k][0],
                             pts[(k + 1) % 4][1] - pts[k][1])), k)
             for k in range(4)]
    _l, k = max(sides)
    p, q = pts[k], pts[(k + 1) % 4]
    r, s = pts[(k + 3) % 4], pts[(k + 2) % 4]
    a = ((p[0] + r[0]) / 2.0, (p[1] + r[1]) / 2.0)
    b = ((q[0] + s[0]) / 2.0, (q[1] + s[1]) / 2.0)
    if np.hypot(b[0] - a[0], b[1] - a[1]) <= 0.0:
        return None
    return a, b
