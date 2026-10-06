"""The ONE oriented-envelope guard (owner 2026-09-04, 2026-10-04).

A leaf: no v2 import and no geometry library (numpy only), so ``geom``,
``model`` and every layer above may read it.
"""
from __future__ import annotations

import numpy as np

__all__ = ["rotated_rectangle"]


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
