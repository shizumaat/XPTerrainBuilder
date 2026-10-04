"""The ONE oriented-envelope guard (owner 2026-09-04, 2026-10-04).

A leaf: no v2 import and no geometry library, so ``geom``, ``model`` and
every layer above may read it.
"""
from __future__ import annotations

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
    """
    import warnings
    with warnings.catch_warnings():          # numpy routes errstate here
        warnings.simplefilter("ignore", RuntimeWarning)
        return poly.minimum_rotated_rectangle
