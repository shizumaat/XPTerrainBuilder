"""THE CAPPED LEAST-SQUARES PLANE: ``z0 + gx (x - x0) + gy (y - y0)``
through a set of points, its tilt bounded by a ceiling (a steeper fit
keeps its direction at the ceiling and re-centres).  The construction of
Q-32a (d) (spec-author ruling 2026-09-25, ``solve/project_strip``'s pad
plane), shared with the fence-foot plane of spec 2068 A2 F2
(``classify/fence_yard``).  ``geom`` imports nothing of v2."""
from __future__ import annotations

import numpy as np

__all__ = ["capped_plane", "plane_at"]


def capped_plane(P: np.ndarray, z: np.ndarray, tilt_max: float
                 ) -> tuple[float, float, float, float, float]:
    """``(z0, gx, gy, x0, y0)``: the least-squares plane through ``P``
    ``(n, 2)`` at ``z`` ``(n,)``, centred on their mean; fewer than three
    non-collinear points give the median, level.  A tilt over
    ``tilt_max`` (when it is positive) keeps its direction at
    ``tilt_max`` and re-centres ``z0``."""
    P = np.asarray(P, dtype=float).reshape(-1, 2)
    z = np.asarray(z, dtype=float).reshape(-1)
    x0, y0 = float(P[:, 0].mean()), float(P[:, 1].mean())
    A = np.column_stack([np.ones(len(P)), P[:, 0] - x0, P[:, 1] - y0])
    if len(P) >= 3 and np.linalg.matrix_rank(A) == 3:
        c, *_ = np.linalg.lstsq(A, z, rcond=None)
        z0, gx, gy = float(c[0]), float(c[1]), float(c[2])
    else:
        z0, gx, gy = float(np.median(z)), 0.0, 0.0
    g = float(np.hypot(gx, gy))
    if g > tilt_max > 0.0:
        gx, gy = gx * tilt_max / g, gy * tilt_max / g
        z0 = float(np.mean(z - gx * (P[:, 0] - x0) - gy * (P[:, 1] - y0)))
    return (z0, gx, gy, x0, y0)


def plane_at(pl: tuple[float, float, float, float, float], x, y):
    """The plane ``pl`` (:func:`capped_plane`) at ``(x, y)`` (scalars or
    arrays)."""
    z0, gx, gy, x0, y0 = pl
    return z0 + gx * (x - x0) + gy * (y - y0)
