"""WHAT SHAPE A SOLID IS, FROM ITS GEOMETRY ALONE (#1914, #1883 round 3).

ONE classification, two readers: the engine's object-floor reader
(``airport/object_floor``: a CONCAVE CUT SHELL is a stated ground) and the
drawn instrument (``tools/drawn_site_check.shape_witness``).  Both raster
the solid's plan (:func:`rasterise`: per grid cell its TOP and its LOWEST
surface), read the solid's OWN RIM — the 90th percentile of the highest
geometry on its outline band (:func:`outline_band`, :func:`outline_reach`)
— and ask :func:`shape_class`:

* ``flat`` — its surfaces span less height than ``flat_m`` (a deck, a pad);
* ``concave`` — an OPEN-TOP HOLLOW: over at least ``min_share`` of its
  inner plan the top surface stands ``hollow_m`` or more under the rim,
  with one surface per plan point (nothing over it);
* ``covered`` — a deck or roof stands over a floor over ``min_share``;
* ``convex`` — anything else (its top is its highest part);
* ``thin`` — no inner plan (a wall, a rail).

Nothing here names a pack, an object or an airport.
"""
from __future__ import annotations

import dataclasses as _dc
import math

import numpy as np

__all__ = ["Raster", "rasterise", "outline_band", "outline_reach", "shape_class", "shape_of",
           "CONCAVE", "COVERED", "CONVEX", "FLAT", "THIN"]

CONCAVE, COVERED, CONVEX, FLAT, THIN = "concave", "covered", "convex", "flat", "thin"


@_dc.dataclass
class Raster:
    """The plan on a grid: per cell its top and lowest surface z (``nan``
    where uncovered); cell ``(i, j)``'s centre is ``(e0 + (j + .5) step,
    n0 + (i + .5) step)``."""

    e0: float
    n0: float
    step: float
    top: np.ndarray
    low: np.ndarray

    def centres(self, ij: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        return self.e0 + (ij[:, 1] + 0.5) * self.step, self.n0 + (ij[:, 0] + 0.5) * self.step


def rasterise(p: np.ndarray, max_cells: int = 160000, min_step: float = 0.5) -> "Raster | None":
    """Top and lowest surface of the 3D triangles ``p`` ``(n, 3, 3)`` per
    grid cell, the step sized so the grid holds about ``max_cells``."""
    if not p.shape[0]:
        return None
    lo, hi = p[:, :, :2].reshape(-1, 2).min(0), p[:, :, :2].reshape(-1, 2).max(0)
    span = hi - lo
    step = max(min_step, math.sqrt(max(span[0] * span[1], 1.0) / max_cells))
    ncol, nrow = int(span[0] // step) + 1, int(span[1] // step) + 1
    top = np.full(nrow * ncol, -np.inf)
    low = np.full(nrow * ncol, np.inf)
    for t in p:
        (x1, y1, z1), (x2, y2, z2), (x3, y3, z3) = t
        d = (y2 - y3) * (x1 - x3) + (x3 - x2) * (y1 - y3)
        if abs(d) < 1e-12:
            continue
        c0, c1 = int((min(x1, x2, x3) - lo[0]) // step), int((max(x1, x2, x3) - lo[0]) // step)
        r0, r1 = int((min(y1, y2, y3) - lo[1]) // step), int((max(y1, y2, y3) - lo[1]) // step)
        cc, rr = np.meshgrid(np.arange(c0, c1 + 1), np.arange(r0, r1 + 1))
        cc, rr = cc.ravel(), rr.ravel()
        cx, cy = lo[0] + (cc + 0.5) * step, lo[1] + (rr + 0.5) * step
        w1 = ((y2 - y3) * (cx - x3) + (x3 - x2) * (cy - y3)) / d
        w2 = ((y3 - y1) * (cx - x3) + (x1 - x3) * (cy - y3)) / d
        w3 = 1.0 - w1 - w2
        m = (w1 >= -1e-6) & (w2 >= -1e-6) & (w3 >= -1e-6)
        if m.any():
            zz = w1[m] * z1 + w2[m] * z2 + w3[m] * z3
            k = rr[m] * ncol + cc[m]
            np.maximum.at(top, k, zz)
            np.minimum.at(low, k, zz)
    top[~np.isfinite(top)] = np.nan
    low[~np.isfinite(low)] = np.nan
    return Raster(float(lo[0]), float(lo[1]), step,
                  top.reshape(nrow, ncol), low.reshape(nrow, ncol))


def outline_band(r: Raster, band_m: float) -> tuple[np.ndarray, np.ndarray]:
    """``(band, inner)``: the covered cells within ``band_m`` of an
    uncovered one, and the rest."""
    cov = ~np.isnan(r.top)
    k = max(1, int(round(band_m / r.step)))
    pad = np.pad(cov, k, constant_values=False)
    inner = cov.copy()
    for di in range(-k, k + 1):
        for dj in range(-k, k + 1):
            inner &= pad[k + di:k + di + cov.shape[0], k + dj:k + dj + cov.shape[1]]
    return cov & ~inner, inner


def outline_reach(P: np.ndarray, be, bn, reach_m: float) -> tuple[np.ndarray, np.ndarray]:
    """Per outline point ``(be, bn)``, the lowest and highest geometry of
    the points ``P`` ``(m, 3)`` within ``reach_m`` in plan (``nan`` where
    none): a wall's foot and its crest."""
    from scipy.spatial import cKDTree
    lo, hi = np.full(len(be), np.nan), np.full(len(be), np.nan)
    if not len(P):
        return lo, hi
    tree = cKDTree(P[:, :2])
    for k, nb in enumerate(tree.query_ball_point(np.column_stack([be, bn]), reach_m)):
        if nb:
            lo[k], hi[k] = P[nb, 2].min(), P[nb, 2].max()
    return lo, hi


def shape_class(top_in: np.ndarray, low_in: np.ndarray, rim: float, *, hollow_m: float,
                stacked_m: float, min_share: float = 0.5) -> tuple[str, float, float]:
    """``(class, hollow share, covered share)`` of a solid whose inner plan
    has tops ``top_in`` and lowest surfaces ``low_in`` under its own rim
    ``rim`` (module doc): a point is HOLLOW where its top stands
    ``hollow_m`` or more under the rim with one surface there (top - low
    within ``stacked_m``), COVERED where two surfaces stand apart."""
    if not len(top_in):
        return THIN, 0.0, 0.0
    single = (top_in - low_in) <= stacked_m
    hollow = float(((top_in < rim - hollow_m) & single).mean())
    covered = float((~single).mean())
    cls = CONCAVE if hollow >= min_share else COVERED if covered >= min_share else CONVEX
    return cls, hollow, covered


def shape_of(r: "Raster | None", P: np.ndarray, *, band_m: float, reach_m: float,
             hollow_m: float, stacked_m: float, flat_m: float,
             min_share: float = 0.5) -> dict:
    """The whole reading of one solid: ``class``, ``hollow``, ``covered``
    (shares), ``rim`` (its own rim z) and ``inner_top_p50``.  ``P`` are
    points along its edges (the crest a wall's outline reaches)."""
    if r is None or not np.isfinite(r.top).any():
        return {"class": THIN, "hollow": None, "covered": None, "rim": None,
                "inner_top_p50": None}
    relief = float(np.nanmax(r.top) - np.nanmin(r.low))
    if relief < flat_m:
        return {"class": FLAT, "hollow": 0.0, "covered": 0.0, "rim": float(np.nanmax(r.top)),
                "inner_top_p50": float(np.nanmedian(r.top))}
    band, inner = outline_band(r, band_m)
    if not band.any() or not inner.any():
        return {"class": THIN, "hollow": None, "covered": None, "rim": None,
                "inner_top_p50": None}
    _foot, crest = outline_reach(P, *r.centres(np.argwhere(band)), reach_m + r.step / 2)
    rim = float(np.percentile(np.fmax(r.top[band], crest), 90))
    top_in = r.top[inner]
    cls, hollow, covered = shape_class(top_in, r.low[inner], rim, hollow_m=hollow_m,
                                       stacked_m=stacked_m, min_share=min_share)
    return {"class": cls, "hollow": hollow, "covered": covered, "rim": rim,
            "inner_top_p50": float(np.median(top_in))}
