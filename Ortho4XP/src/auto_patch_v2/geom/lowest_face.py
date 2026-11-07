"""The LOWEST plan face under a point: the z of the lowest of a set of
3D triangles whose plan triangle holds each ``(x, y)`` (``airport/object_floor``
reads a trench object's floor with it; ``constraints/object_floor`` pins to it).
"""
from __future__ import annotations

import typing as _t

import numpy as np

__all__ = ["floor_z_at"]


def floor_z_at(faces: np.ndarray, xs: _t.Sequence[float], ys: _t.Sequence[float],
               edge_m: float = 0.0) -> np.ndarray:
    """The floor's z under each ``(x, y)``: the LOWEST face whose plan
    triangle holds the point (its plane there); ``nan`` where none does.
    ``edge_m`` > 0 also reads a point up to that far outside the nearest
    face, on that face's plane (a ring vertex the map snapped a hair off
    the footprint, or the void band's floor-side ring)."""
    xs = np.asarray(xs, float)
    ys = np.asarray(ys, float)
    out = np.full(xs.shape, np.nan)
    if not len(faces) or not len(xs):
        return out
    x0, x1, x2 = faces[:, 0, 0], faces[:, 1, 0], faces[:, 2, 0]
    y0, y1, y2 = faces[:, 0, 1], faces[:, 1, 1], faces[:, 2, 1]
    z0, z1, z2 = faces[:, 0, 2], faces[:, 1, 2], faces[:, 2, 2]
    den = (y1 - y2) * (x0 - x2) + (x2 - x1) * (y0 - y2)
    ok = np.abs(den) > 1e-9
    lo_x = np.minimum(np.minimum(x0, x1), x2) - edge_m
    hi_x = np.maximum(np.maximum(x0, x1), x2) + edge_m
    lo_y = np.minimum(np.minimum(y0, y1), y2) - edge_m
    hi_y = np.maximum(np.maximum(y0, y1), y2) + edge_m
    for k in range(len(xs)):
        x, y = xs[k], ys[k]
        c = np.flatnonzero(ok & (lo_x <= x) & (x <= hi_x) & (lo_y <= y) & (y <= hi_y))
        if not len(c):
            continue
        w0 = ((y1[c] - y2[c]) * (x - x2[c]) + (x2[c] - x1[c]) * (y - y2[c])) / den[c]
        w1 = ((y2[c] - y0[c]) * (x - x2[c]) + (x0[c] - x2[c]) * (y - y2[c])) / den[c]
        w2 = 1.0 - w0 - w1
        z = w0 * z0[c] + w1 * z1[c] + w2 * z2[c]
        least = np.minimum(np.minimum(w0, w1), w2)
        inside = least >= -1e-9
        if inside.any():
            out[k] = float(z[inside].min())
        elif edge_m > 0.0:
            # how far outside each candidate the point stands, in metres:
            # the least barycentric weight times the face's height there
            h = np.abs(den[c]) / np.maximum(np.hypot(x1[c] - x2[c], y1[c] - y2[c]), 1e-9)
            near = -least * h <= edge_m
            if near.any():
                out[k] = float(z[near].min())
    return out
