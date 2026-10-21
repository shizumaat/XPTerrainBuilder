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

__all__ = ["water_level_beside", "water_line_level", "shore_edge_records", "SEA_LEVEL_M"]

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


def water_line_level(dem, xs, ys, ground_z, probe_m: float = _PROBE_M) -> np.ndarray:
    """THE LEVEL THE LAND MEETS THE WATER AT, at shore points ``(xs, ys)``
    whose own terrain is ``ground_z`` (issue #1177; owner 2026-10-21: "leave
    enough buffer to grade smoothly into the water just like the natural
    terrain does").

    The SEA's water line is the sea level: ``sea_smoothing_mode=zero`` levels
    every vertex of a sea triangle, its coastline vertices included, so the
    natural terrain meets the sea at 0.  An INLAND body is never levelled to
    its median: the mesh's ``water_smoothing`` averages its triangles WITH
    their bank vertices, so its surface rides up the bank to the terrain at
    the water line.  There the land meets the water at its own terrain,
    never below the body's level — pinned to the median instead, the ground
    stood under a water surface the mesh lifted 1–2 m up the bank (KOTH's
    runway ends on Coos Bay)."""
    xs = np.atleast_1d(np.asarray(xs, float))
    ys = np.atleast_1d(np.asarray(ys, float))
    ground = np.atleast_1d(np.asarray(ground_z, float))
    level = water_level_beside(dem, xs, ys, probe_m)
    if not xs.size:
        return level
    sea_fn = getattr(dem, "sea_geometry", None)
    sea = None
    if callable(sea_fn):
        pad = 2.0 * probe_m
        try:
            sea = sea_fn((float(xs.min()) - pad, float(ys.min()) - pad,
                          float(xs.max()) + pad, float(ys.max()) + pad))
        except Exception:                               # pragma: no cover
            sea = None
    if sea is None or sea.is_empty:
        on_sea = np.zeros(xs.shape, bool)
    else:
        import shapely
        on_sea = np.asarray(shapely.distance(sea, shapely.points(xs, ys))) <= probe_m
    bank = np.where(np.isfinite(ground), np.maximum(level, ground), level)
    return np.where(on_sea, level, bank)


def shore_edge_records(dem, shore) -> list[list[float]]:
    """The sidecar's ``shore_edges``: ``[lat_a, lon_a, lat_b, lon_b, level]``
    per shore edge (lat/lon pairs), ``level`` the water line at its midpoint
    (:func:`water_line_level` over the DEM there) — the level the census's
    ``sea_wall`` family reads the drop to the water from (#1177).  The level
    is left out (four fields) when the DEM cannot be read."""
    out = [[a[0], a[1], b[0], b[1]] for a, b in shore]
    frame = getattr(dem, "frame", None)
    if not out or frame is None:
        return out
    try:
        to_xy, _ = frame.transformers()
        mid = [to_xy((e[1] + e[3]) / 2.0, (e[0] + e[2]) / 2.0) for e in out]
        xs = np.array([m[0] for m in mid])
        ys = np.array([m[1] for m in mid])
        lv = water_line_level(dem, xs, ys, np.asarray(dem.z_many(xs, ys), float))
    except Exception:                                   # pragma: no cover
        return out
    for e, z in zip(out, lv, strict=True):
        if np.isfinite(z):
            e.append(round(float(z), 3))
    return out
