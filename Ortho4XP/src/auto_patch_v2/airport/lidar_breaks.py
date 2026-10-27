"""THE DEM'S OWN WITNESS READS (#1359; spec
``docs/specs/multi-source-terrain-spec.md`` §3 Q4 / Q5 / Q6, §7.1):
vectorised profile reads of the airport's DEM, one sampler call per probe
family (``airport/dem.dem_z_many``).

* :func:`slope_breaks` — per line probe, where the smoothed normal profile
  changes slope the most (a graded fill meeting natural ground), and by how
  much (per cent); ``None`` where the change is under the floor.
* :func:`cut_depth` — at a point, the median of a ring minus the minimum of
  a core (an open cut or a portal reads metres deep; kerbs and noise read
  well under the floor).
"""
from __future__ import annotations

import math

import numpy as np
from scipy import ndimage

from .dem import dem_z_many

__all__ = ["slope_breaks", "cut_depth", "profiles"]

_K_ALONG = 5
#: slope is compared between the means of this many metres either side
_SIDE_M = 5.0


def profiles(dem, xy: np.ndarray, normal: np.ndarray, offsets: np.ndarray,
             along_half_m: float) -> np.ndarray:
    """DEM N×M: per station, per normal offset, the median of ``_K_ALONG``
    samples across ``±along_half_m`` along the edge."""
    xy = np.asarray(xy, dtype=float)
    n = np.asarray(normal, dtype=float)
    t = np.stack([-n[:, 1], n[:, 0]], axis=-1)
    ts = np.linspace(-along_half_m, along_half_m, _K_ALONG) if along_half_m > 0 else np.zeros(1)
    pts = (xy[:, None, None, :] + n[:, None, None, :] * offsets[None, :, None, None]
           + t[:, None, None, :] * ts[None, None, :, None])
    z = dem_z_many(dem, pts[..., 0].ravel(), pts[..., 1].ravel()).reshape(pts.shape[:3])
    with np.errstate(all="ignore"):
        return np.nanmedian(z, axis=2)


def slope_breaks(dem, xy: np.ndarray, normal: np.ndarray, offsets: np.ndarray,
                 along_half_m: float, smooth_m: float, min_change_pct: float
                 ) -> tuple[list[float | None], np.ndarray]:
    """``(offset of the break per station or None, slope change per cent)``."""
    offsets = np.asarray(offsets, dtype=float)
    z = profiles(dem, xy, normal, offsets, along_half_m)
    d = float(np.median(np.diff(offsets))) if offsets.size > 1 else 1.0
    side = max(1, int(round(_SIDE_M / d)))
    out: list[float | None] = []
    best = np.zeros(z.shape[0])
    for i, p in enumerate(z):
        ok = np.isfinite(p)
        if ok.sum() < max(8, p.size // 2):
            out.append(None)
            continue
        p = np.interp(offsets, offsets[ok], p[ok])
        p = ndimage.gaussian_filter1d(p, max(1.0, smooth_m / d))
        g = np.gradient(p, d) * 100.0
        c = np.zeros_like(g)
        # the smoothing reads past the band's ends: no break within one
        # smoothing span plus one side of either end
        edge = side + max(1, int(round(smooth_m / d)))
        for j in range(edge, g.size - edge):
            c[j] = abs(g[j:j + side].mean() - g[j - side:j].mean())
        j = int(np.argmax(c))
        best[i] = c[j]
        out.append(float(offsets[j]) if c[j] >= min_change_pct else None)
    return out, best


def cut_depth(dem, xy: tuple[float, float], ring_m: tuple[float, float], core_m: float
              ) -> tuple[float | None, float | None]:
    """``(depth, floor)`` at ``xy``: the median DEM on the ring
    ``ring_m[0]..ring_m[1]`` minus the minimum within ``core_m``."""
    x0, y0 = xy
    rs = np.linspace(ring_m[0], ring_m[1], 5)
    angs = np.linspace(0.0, 2 * math.pi, 48, endpoint=False)
    R, A = np.meshgrid(rs, angs)
    zr = dem_z_many(dem, (x0 + R * np.cos(A)).ravel(), (y0 + R * np.sin(A)).ravel())
    g = np.arange(-core_m, core_m + 1e-9, 1.0)
    gx, gy = np.meshgrid(g, g)
    inside = np.hypot(gx, gy) <= core_m
    zc = dem_z_many(dem, (x0 + gx[inside]).ravel(), (y0 + gy[inside]).ravel())
    zr, zc = zr[np.isfinite(zr)], zc[np.isfinite(zc)]
    if not zr.size or not zc.size:
        return None, None
    floor = float(zc.min())
    return float(np.median(zr) - floor), floor
