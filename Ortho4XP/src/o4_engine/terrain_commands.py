"""``terrain_sample`` — the DEM grid under the patch editor's 3D preview
(protocol 1.12, ``docs/specs/patch-editor-20261015.md`` §2 and §5).

The grid is sampled from the terrain the mesh drapes on when the last
build's raster is on disk, else from the airport solve's authored DEM
(``terrain_source.choose_source``; ``sources.frame`` says which) —
never a second reader.  It reads the data
repo's caches only: a missing base DEM is an error naming the tile and
the refresh it needs, never a download (data-repo law, RULINGS
``e9daef5``).

The extent is the CLIENT's choice (A9: patch bbox + 500 m at 5 m); the
engine serves the bbox and spacing it is given and refuses a grid over
:data:`MAX_SAMPLES`.  Grid layout: ``rows`` × ``cols`` points, row-major,
row 0 at the SOUTH edge, column 0 at the WEST edge; the corner points
sit exactly on the bbox corners, so the step (``dlat``, ``dlon``) is the
largest that divides the bbox and does not exceed ``spacing_m``.
Elevations are metres MSL, float32 little-endian, base64; a point no
raster covers is NaN.
"""
from __future__ import annotations

import base64
import math
import os
from typing import Any, Dict, Sequence

import numpy as np

import O4_File_Names as FNAMES

__all__ = ["MAX_SAMPLES", "terrain_sample"]

#: The largest grid one reply carries (§2 cap): 4,000,000 points is 16 MB
#: of float32 before base64.
MAX_SAMPLES = 4_000_000

#: Metres per degree of latitude — the emit's local plane
#: (``emit/osm_adapter._local_metres``), which the client draws in.
_M_PER_DEG_LAT = 111320.0

def _tile_of(key: Any) -> tuple[int, int]:
    """``(lat, lon)`` of a ``+45-123`` tile key, or a refusal sentence."""
    tile = FNAMES.parse_tile_key(key)
    if tile is None:
        raise ValueError(f"terrain_sample: {key!r} is not a tile key like +45-123.")
    return tile


def _box(bbox: Any) -> tuple[float, float, float, float]:
    try:
        s, w, n, e = (float(v) for v in bbox)
    except (TypeError, ValueError):
        raise ValueError("terrain_sample: bbox must be [min_lat, min_lon, max_lat, "
                         "max_lon] in degrees.") from None
    if not (all(math.isfinite(v) for v in (s, w, n, e)) and s < n and w < e
            and -90 <= s and n <= 90 and -180 <= w and e <= 180):
        raise ValueError(f"terrain_sample: bbox {[s, w, n, e]} is empty or off the globe.")
    return s, w, n, e


def grid_shape(bbox: Sequence[float], spacing_m: float) -> tuple[int, int, float, float]:
    """``(rows, cols, dlat, dlon)`` of the grid whose corners are the
    bbox corners and whose step is at most ``spacing_m``."""
    s, w, n, e = bbox
    mid = math.radians((s + n) / 2)
    m_per_deg_lon = _M_PER_DEG_LAT * max(math.cos(mid), 1e-6)
    rows = int(math.ceil((n - s) * _M_PER_DEG_LAT / spacing_m - 1e-9)) + 1
    cols = int(math.ceil((e - w) * m_per_deg_lon / spacing_m - 1e-9)) + 1
    rows, cols = max(rows, 2), max(cols, 2)
    return rows, cols, (n - s) / (rows - 1), (e - w) / (cols - 1)


def terrain_sample(tile: str, icao: str, bbox: Sequence[float],
                   spacing_m: float, build_dir: str | None = None) -> Dict[str, Any]:
    """The §2 reply: the DEM over ``bbox`` at ``spacing_m``; the built DEM
    is looked up in ``build_dir`` (the app's tile folder) or ``Tiles/``."""
    from auto_patch_v2.airport import dem as _dem      # local: engine start stays light

    from . import terrain_source as _src

    lat0, lon0 = _tile_of(tile)
    box = _box(bbox)
    try:
        spacing = float(spacing_m)
    except (TypeError, ValueError):
        spacing = float("nan")
    if not (math.isfinite(spacing) and spacing > 0):
        raise ValueError(f"terrain_sample: spacing_m must be a positive number of metres, "
                         f"not {spacing_m!r}.")
    rows, cols, dlat, dlon = grid_shape(box, spacing)
    if rows * cols > MAX_SAMPLES:
        raise ValueError(
            f"terrain_sample: {rows} × {cols} = {rows * cols:,} samples is over the "
            f"{MAX_SAMPLES:,} limit — ask for a smaller box or a coarser spacing.")

    root = FNAMES.Elevation_dir
    hgt, _tif, _js = _dem.resolve_dem_files(root, lat0 + 0.5, lon0 + 0.5, str(icao))
    have_hgt = bool(root) and os.path.isfile(hgt)
    lats = box[0] + np.arange(rows, dtype=np.float64) * dlat
    lons = box[1] + np.arange(cols, dtype=np.float64) * dlon
    lat_grid, lon_grid = np.meshgrid(lats, lons, indexing="ij")
    la, lo = lat_grid.ravel(), lon_grid.ravel()
    try:
        cfg = _src.tile_config(lat0, lon0, build_dir)
    except Exception:              # a cfg the core cannot read: defaults
        cfg = None
    source = _src.production_source(lat0, lon0, cfg) if cfg is not None else None
    if source is None and not have_hgt:
        raise ValueError(
            f"No elevation data for tile {tile} ({_dem.hgt_name(lat0, lon0)}.hgt is not in "
            "the data folder). Build the tile or refresh its elevation data first; the 3D "
            "preview never downloads.")
    if source is None:
        source = _src.authored_source(lat0, lon0, str(icao), root, cfg)
    z = source.z(la, lo)
    gaps = ~np.isfinite(z)
    if source.sources["frame"] == "production" and gaps.any() and have_hgt:
        # the built raster covers its own tile only: the box's overhang
        # into a neighbour reads the authored DEM
        z[gaps] = _src.authored_source(lat0, lon0, str(icao), root, cfg).z(la[gaps], lo[gaps])
    payload = np.asarray(z, dtype="<f4").tobytes()
    return {
        "bbox": list(box), "rows": rows, "cols": cols, "spacing_m": spacing,
        "dlat": dlat, "dlon": dlon,
        "elev_f32_b64": base64.b64encode(payload).decode("ascii"),
        "sources": dict(source.sources),
    }

