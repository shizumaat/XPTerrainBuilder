"""A DECK'S END LINE in plan (#1971; spec ``interchange-levels-v2-20261113.md``
§3.3 R1, §3.4): which points stand at it.  ONE predicate, read by the end-line
rows (``constraints/deck_stack``) and the road ramp's deck-end seeds
(``airport/deck_stack.deck_end_seeds``), so the two select the same
vertices."""
from __future__ import annotations

import typing as _t

import numpy as np

__all__ = ["near_stations", "polyline_distance"]


def near_stations(xy: np.ndarray, stations: _t.Sequence, reach: float) -> np.ndarray:
    """``(n,)`` bool: each of the ``(n, 2)`` points within ``reach`` of one of
    the end line's ``stations``."""
    xy = np.asarray(xy, float).reshape(-1, 2)
    pts = np.asarray(stations, float).reshape(-1, 2)
    if not len(xy) or not len(pts):
        return np.zeros(len(xy), bool)
    d = np.hypot(xy[:, None, 0] - pts[None, :, 0], xy[:, None, 1] - pts[None, :, 1])
    return d.min(axis=1) <= reach


def polyline_distance(xy: np.ndarray, line: _t.Sequence) -> np.ndarray:
    """``(n,)`` each point's plan distance to the polyline ``line``."""
    p = np.asarray(xy, float).reshape(-1, 2)
    pts = np.asarray(line, float).reshape(-1, 2)
    best = np.full(len(p), np.inf)
    for a, b in zip(pts[:-1], pts[1:], strict=True):
        e = b - a
        L2 = float(e @ e) or 1e-12
        t = np.clip(((p - a) @ e) / L2, 0.0, 1.0)
        best = np.minimum(best, np.hypot(*(p - (a + t[:, None] * e)).T))
    return best
