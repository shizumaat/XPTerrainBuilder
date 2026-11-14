"""The LOWEST plan face under a point: the z of the lowest of a set of
3D triangles whose plan triangle holds each ``(x, y)`` (``airport/object_floor``
reads a trench object's floor with it; ``constraints/object_floor`` pins to it).
"""
from __future__ import annotations

import typing as _t

import numpy as np

__all__ = ["floor_z_at", "every_z_at"]


def floor_z_at(faces: np.ndarray, xs: _t.Sequence[float], ys: _t.Sequence[float],
               edge_m: float = 0.0) -> np.ndarray:
    """The floor's z under each ``(x, y)``: the LOWEST face whose plan
    triangle holds the point (its plane there); ``nan`` where none does.
    ``edge_m`` > 0 also reads a point up to that far outside the nearest
    face, on that face's plane (a ring vertex the map snapped a hair off
    the footprint, or the void band's floor-side ring)."""
    xs = np.asarray(xs, float)
    out = np.full(xs.shape, np.nan)
    for k, z in enumerate(_z_over(faces, xs, ys, edge_m)):
        if z.size:
            out[k] = float(z.min())
    return out


def every_z_at(faces: np.ndarray, xs: _t.Sequence[float], ys: _t.Sequence[float],
               edge_m: float = 0.0) -> list[np.ndarray]:
    """EVERY face's z under each ``(x, y)`` (:func:`floor_z_at`'s reading
    without taking the lowest; #2065 ``airport/bridge_witness`` W3/W4 read
    the layers of a plate): one array per point, empty where no face is."""
    return list(_z_over(faces, xs, ys, edge_m))


def _z_over(faces: np.ndarray, xs: _t.Sequence[float], ys: _t.Sequence[float],
            edge_m: float) -> _t.Iterator[np.ndarray]:
    """Per point, the z of the faces whose plan triangle holds it — or,
    with none and ``edge_m`` > 0, of the faces it stands within ``edge_m``
    outside of (:func:`floor_z_at`)."""
    xs = np.asarray(xs, float)
    ys = np.asarray(ys, float)
    none = np.zeros(0)
    if not len(faces) or not len(xs):
        for _k in range(len(xs)):
            yield none
        return
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
            yield none
            continue
        w0 = ((y1[c] - y2[c]) * (x - x2[c]) + (x2[c] - x1[c]) * (y - y2[c])) / den[c]
        w1 = ((y2[c] - y0[c]) * (x - x2[c]) + (x0[c] - x2[c]) * (y - y2[c])) / den[c]
        w2 = 1.0 - w0 - w1
        z = w0 * z0[c] + w1 * z1[c] + w2 * z2[c]
        least = np.minimum(np.minimum(w0, w1), w2)
        inside = least >= -1e-9
        if inside.any():
            yield z[inside]
        elif edge_m > 0.0:
            # how far outside each candidate the point stands, in metres:
            # the least barycentric weight times the face's height OVER THE
            # EDGE THAT WEIGHT IS MEASURED FROM (#1936: the height over edge
            # 1-2 alone read a ring vertex 0.16-0.33 m off a long sliver face
            # as metres out, and EGLL 11b left 81 ring vertices unpinned,
            # the mesh standing up to 5 m over its floor between them)
            w = np.stack([w0, w1, w2])
            edge = np.stack([np.hypot(x1[c] - x2[c], y1[c] - y2[c]),
                             np.hypot(x2[c] - x0[c], y2[c] - y0[c]),
                             np.hypot(x0[c] - x1[c], y0[c] - y1[c])])
            i = np.argmin(w, axis=0)
            h = np.abs(den[c]) / np.maximum(edge[i, np.arange(len(c))], 1e-9)
            near = -least * h <= edge_m
            yield z[near]
        else:
            yield none
