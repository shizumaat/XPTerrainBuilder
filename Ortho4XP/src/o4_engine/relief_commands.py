"""``terrain_relief`` — the patch view's terrain picture (protocol 1.15,
issue #1320, owner Q134: hillshade plus contours).

The client names a tile, a box and a picture size; the reply is a PNG
(base64) of the hillshade with contour lines (``o4_engine.relief``) and
its legend.  Elevations come from the sources ``cursor_elevation`` reads
(``elevation_commands``: the BUILT mesh, else the tile's DEM) — never a
second reader, and never a download.

Pixels are centred on an even grid in longitude and in web-mercator Y, so
the picture lies on the map's own projection: the client draws it into
the box's corners as they are.  The box is clipped to the tile.

The command is called on the transport's read loop, so it never renders
there: a source not yet loaded, or a picture not yet drawn, is loaded or
drawn on a daemon thread and the reply says ``pending: true``; the client
asks again.  Pictures are kept per (mesh stamp, tile, box, size, step),
the last :data:`MAX_CACHED` of them.
"""
from __future__ import annotations

import base64
import math
import threading
from collections import OrderedDict
from typing import Any, Dict, Optional

import numpy as np
import O4_File_Names as FNAMES

from . import elevation_commands as _elev
from . import relief as _relief
from .terrain_commands import _box, _tile_of

__all__ = ["MAX_CACHED", "MAX_PX", "terrain_relief"]

#: The largest picture side the engine draws, in pixels.
MAX_PX = 1024
#: Pictures kept in memory (a few map views' worth).
MAX_CACHED = 12
_M_PER_DEG_LAT = 111320.0

_LOCK = threading.Lock()
_RELIEF: "OrderedDict[tuple, Any]" = OrderedDict()   # key -> reply | Exception


def _merc(lat: float) -> float:
    return math.log(math.tan(math.pi / 4 + math.radians(lat) / 2))


def pixel_centres(box, width: int, height: int) -> tuple[np.ndarray, np.ndarray]:
    """``(lats, lons)`` of the pixel centres, rows north to south, even in
    mercator Y; columns west to east."""
    s, w, n, e = box
    lons = w + (np.arange(width) + 0.5) * ((e - w) / width)
    y0, y1 = _merc(n), _merc(s)
    ys = y0 + (np.arange(height) + 0.5) * ((y1 - y0) / height)
    lats = np.degrees(2 * np.arctan(np.exp(ys)) - math.pi / 2)
    return lats, lons


def _sample(sampler, z_many, lats, lons) -> tuple[np.ndarray, str]:
    """The elevation grid and which source answered (``mesh`` / ``dem``
    / ``mixed``)."""
    lat_grid, lon_grid = np.meshgrid(lats, lons, indexing="ij")
    la, lo = lat_grid.ravel(), lon_grid.ravel()
    z = np.full(la.shape, np.nan)
    if sampler is not None:
        hits = sampler.sample_many(la, lo)
        z = np.array([np.nan if h is None else h.elevation_metres for h in hits], dtype=np.float64)
    from_mesh = np.isfinite(z)
    if z_many is not None and not from_mesh.all():
        miss = ~from_mesh
        z[miss] = np.asarray(z_many(la[miss], lo[miss]), dtype=np.float64)
    source = "mesh" if from_mesh.all() else ("dem" if not from_mesh.any() else "mixed")
    return z.reshape(lat_grid.shape), source


def _render(sampler, z_many, box, width, height, contour_m) -> Dict[str, Any]:
    lats, lons = pixel_centres(box, width, height)
    z, source = _sample(sampler, z_many, lats, lons)
    s, w, n, e = box
    dx = (e - w) / width * _M_PER_DEG_LAT * max(math.cos(math.radians((s + n) / 2)), 1e-6)
    dy = (n - s) / height * _M_PER_DEG_LAT
    finite = z[np.isfinite(z)]
    lo, hi = (float(finite.min()), float(finite.max())) if finite.size else (None, None)
    step = float(contour_m) if contour_m else _relief.contour_step(max(dx, dy), lo, hi)
    picture = _relief.relief_rgba(z, dx, dy, step)
    return {
        "pending": False,
        "png_b64": base64.b64encode(_relief.png_bytes(picture.rgba)).decode("ascii"),
        "width": width, "height": height, "bbox": list(box),
        "source": source if finite.size else None,
        "legend": {"min_m": picture.min_m, "max_m": picture.max_m, "contour_m": step},
    }


def _size(value: Any, name: str) -> int:
    try:
        px = int(value)
    except (TypeError, ValueError):
        raise ValueError(f"terrain_relief: {name} must be a whole number of pixels.") from None
    if not 1 <= px <= MAX_PX:
        raise ValueError(f"terrain_relief: {name} {px} is outside 1-{MAX_PX} pixels.")
    return px


def terrain_relief(tile: str, bbox, px_w, px_h, contour_m: Optional[float] = None,
                   build_dir: Optional[str] = None) -> Dict[str, Any]:
    """The terrain picture over ``bbox`` (``[min_lat, min_lon, max_lat,
    max_lon]``, clipped to ``tile``) at ``px_w`` × ``px_h``; ``contour_m``
    the contour interval (default: by pixel size, module ``relief``)."""
    lat0, lon0 = _tile_of(tile, "terrain_relief")
    s, w, n, e = _box(bbox, "terrain_relief")
    box = (max(s, lat0), max(w, lon0), min(n, lat0 + 1), min(e, lon0 + 1))
    if not (box[0] < box[2] and box[1] < box[3]):
        raise ValueError(f"terrain_relief: bbox {[s, w, n, e]} is outside tile {tile}.")
    width, height = _size(px_w, "px_w"), _size(px_h, "px_h")
    if contour_m is not None:
        try:
            contour_m = float(contour_m)
        except (TypeError, ValueError):
            contour_m = float("nan")
        if not (math.isfinite(contour_m) and contour_m > 0):
            raise ValueError("terrain_relief: contour_m must be a positive number of metres.")
    folder = build_dir or FNAMES.build_dir(lat0, lon0, "")
    mesh_path = FNAMES.mesh_file(folder, lat0, lon0)
    sampler, mesh_pending = _elev._mesh_sampler(mesh_path, lat0, lon0)
    z_many, dem_pending = _elev._dem_source(lat0, lon0, build_dir)
    waiting = {"pending": True, "png_b64": None, "width": width, "height": height,
               "bbox": list(box), "source": None, "legend": None}
    if mesh_pending or dem_pending:
        return waiting
    if sampler is None and z_many is None:
        raise ValueError(f"No elevation data for tile {tile}: build the tile or refresh its "
                         "elevation data first.")
    key = (_elev._stamp(mesh_path), mesh_path, lat0, lon0, box, width, height, contour_m)
    with _LOCK:
        cached = _RELIEF.get(key)
        if cached is not None:
            _RELIEF.move_to_end(key)
            if isinstance(cached, Exception):
                del _RELIEF[key]            # asked again: draw again
    if isinstance(cached, Exception):
        raise ValueError(f"terrain_relief: the picture could not be drawn ({cached}).")
    if cached is not None:
        return cached

    def draw():
        try:
            return _render(sampler, z_many, box, width, height, contour_m)
        except Exception as error:      # answered on the next ask
            return error

    def store(reply) -> None:           # called under the elevation lock
        with _LOCK:
            _RELIEF[key] = reply if reply is not None else RuntimeError("no picture")
            while len(_RELIEF) > MAX_CACHED:
                _RELIEF.popitem(last=False)

    _elev._load_in_background(("relief", key), draw, store)
    return waiting
