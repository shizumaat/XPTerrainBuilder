"""THE AUTHOR'S GROUND: the surface a scenery author laid as the ground —
the near-horizontal faces of the pack's own plate objects (pavement, grass,
road plates), seated where the pack puts them — read at a point as the
LOWEST of those faces there (a roof stands over the ground plate, never
under it).

Owner 2026-11-07 (lane kmcifloor): "we would probably need to be measuring
against the ground the author was using to tell if something is intended as
a tunnel or not ... our graded terrain can be quite different".  Whether a
candidate stands BELOW GRADE is read against this ground, never against a
placement's zero (a shared-datum pack hangs every object off one datum), and
against the design ground (the DEM) only where the author laid no plates.

Pure geometry: the faces come placed (frame x, y, absolute z) with the id of
the placement each belongs to; ``airport/object_floor`` gathers them.
"""
from __future__ import annotations

import typing as _t

import numpy as np
import shapely
from shapely import STRtree

__all__ = ["AuthorGround"]


class _Reading(_t.NamedTuple):
    """The author's ground around a footprint: ``z`` the median ground
    height over the ring, ``source`` ``"plates"``, ``"dem"`` (no plates
    there) or ``"none"``, ``share`` the share of ring samples a plate
    covered."""

    z: float
    source: str
    share: float


class AuthorGround:
    """Lowest-plate-face queries over placed plate faces ``faces``
    (``(n, 3, 3)``) whose placements are ``owners`` (one id per face)."""

    def __init__(self, faces: np.ndarray, owners: _t.Sequence[str]):
        faces = np.asarray(faces, float).reshape(-1, 3, 3)
        owners = np.asarray(list(owners), object)
        tris = shapely.polygons(faces[:, :, :2]) if len(faces) else np.array([], object)
        keep = shapely.area(tris) > 1e-6 if len(faces) else np.zeros(0, bool)
        self.faces, self.owners = faces[keep], owners[keep] if len(owners) else owners
        self._tree = STRtree(tris[keep]) if keep.any() else None

    def at(self, xs, ys, exclude: _t.AbstractSet[str] = frozenset()) -> np.ndarray:
        """The lowest plate face's z under each point; NaN where none (or
        only an ``exclude``-d placement's) stands."""
        xs = np.asarray(xs, float).ravel()
        ys = np.asarray(ys, float).ravel()
        out = np.full(xs.shape, np.nan)
        if self._tree is None or not len(xs):
            return out
        pi, fi = self._tree.query(shapely.points(xs, ys), predicate="intersects")
        if exclude and len(fi):
            ok = ~np.isin(self.owners[fi], list(exclude))
            pi, fi = pi[ok], fi[ok]
        if not len(fi):
            return out
        F = self.faces[fi]
        x, y = xs[pi], ys[pi]
        x0, y0, x1, y1, x2, y2 = (F[:, 0, 0], F[:, 0, 1], F[:, 1, 0], F[:, 1, 1],
                                  F[:, 2, 0], F[:, 2, 1])
        den = (y1 - y2) * (x0 - x2) + (x2 - x1) * (y0 - y2)
        w0 = ((y1 - y2) * (x - x2) + (x2 - x1) * (y - y2)) / den
        w1 = ((y2 - y0) * (x - x2) + (x0 - x2) * (y - y2)) / den
        z = w0 * F[:, 0, 2] + w1 * F[:, 1, 2] + (1.0 - w0 - w1) * F[:, 2, 2]
        np.fmin.at(out, pi, z)
        return out

    def around(self, foot, ring: tuple[float, float], step_m: float, min_share: float,
               exclude: _t.AbstractSet[str] = frozenset(),
               dem: "_t.Callable | None" = None, max_samples: int = 20000) -> "_Reading":
        """The author's ground over the ring ``ring = (inner, outer)`` metres
        outside ``foot``: the median plate height where plates cover at
        least ``min_share`` of the ring's samples (a grid ``step_m`` apart,
        coarsened to at most ``max_samples``), else the median of ``dem``
        there."""
        band = foot.buffer(ring[1]).difference(foot.buffer(ring[0]))
        if band.is_empty:
            return _Reading(float("nan"), "none", 0.0)
        x0, y0, x1, y1 = band.bounds
        step = max(step_m, float(np.sqrt(band.area / max_samples)))
        gx, gy = np.meshgrid(np.arange(x0 + step / 2, x1, step),
                             np.arange(y0 + step / 2, y1, step))
        gx, gy = gx.ravel(), gy.ravel()
        inside = shapely.contains_xy(band, gx, gy)
        gx, gy = gx[inside], gy[inside]
        if not len(gx):
            return _Reading(float("nan"), "none", 0.0)
        z = self.at(gx, gy, exclude)
        hit = np.isfinite(z)
        share = float(hit.mean())
        if hit.any() and share >= min_share:
            return _Reading(float(np.median(z[hit])), "plates", share)
        if dem is not None:
            d = np.asarray(dem(gx, gy), float)
            d = d[np.isfinite(d)]
            if len(d):
                return _Reading(float(np.median(d)), "dem", share)
        return _Reading(float("nan"), "none", share)
