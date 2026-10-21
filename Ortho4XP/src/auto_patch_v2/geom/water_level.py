"""THE LEVEL OF THE WATER BESIDE A SHORE POINT (owner RULINGS 2026-10-20k,
issue #1104).

The zones stop at EVERY water body's edge (``planar/zones.shore_region``
with ``sea_only=False``), so the shore decision and the natural-shore pin
need the level of the body a point stands beside — 0 for the sea, the
witness's own level for an inland body (``TileWater.level_of``, read
through ``dem.water_many``).  A shore point stands on the water line and
samples dry or wet by a hair, so the read is a small ring of samples
around it: the first wet one names the level.  With no witness, or no wet
sample, the level is the sea's — the reading before 20k."""
from __future__ import annotations

import numpy as np

__all__ = ["water_level_beside", "SEA_LEVEL_M"]

#: The tile's sea level (``O4_Vector_Map.SEAWALL_SEA_LEVEL_M``).
SEA_LEVEL_M = 0.0

#: The ring the read samples: the point itself and eight around it.
_PROBE_M = 1.5
_ANGLES = np.linspace(0.0, 2.0 * np.pi, 8, endpoint=False)


def water_level_beside(dem, xs, ys, probe_m: float = _PROBE_M) -> np.ndarray:
    """The water level beside each frame point ``(xs[i], ys[i])``."""
    xs = np.atleast_1d(np.asarray(xs, float))
    ys = np.atleast_1d(np.asarray(ys, float))
    out = np.full(xs.shape, SEA_LEVEL_M)
    fn = getattr(dem, "water_many", None)
    if not callable(fn) or not xs.size:
        return out
    dx = np.concatenate([[0.0], probe_m * np.cos(_ANGLES)])
    dy = np.concatenate([[0.0], probe_m * np.sin(_ANGLES)])
    px = (xs[:, None] + dx[None, :]).ravel()
    py = (ys[:, None] + dy[None, :]).ravel()
    try:
        wet, level = fn(px, py)
    except Exception:                                   # pragma: no cover
        return out
    wet = np.asarray(wet, bool).reshape(xs.size, dx.size)
    level = np.asarray(level, float).reshape(xs.size, dx.size)
    ok = wet & np.isfinite(level)
    first = np.argmax(ok, axis=1)
    has = ok.any(axis=1)
    out[has] = level[np.arange(xs.size), first][has]
    return out
