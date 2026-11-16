"""The BASE elevation under a point (issue #2119): the terrain a build
reads before any patch or grade shape — what someone hand-editing a
patch matches — and the words that name where it comes from.

Readers only; ``elevation_commands`` caches them and loads them off the
transport's read loop.

* :class:`AltPoints` — the built tile's production DEM (``Data<tile>.alt``,
  the composed, densified, smoothed and inset-baked raster the mesh drapes
  on), read FOUR POSTS AT A TIME from disk with the mesh's own bilinear
  (``dem_production.baked_cell``): no 0.5 GB load per tile, nothing held.
* :func:`inset_footprints` — the tile's cached airport insets
  (``O4_Airport_Elevation_Insets.list_cached_inset_dems``) with their
  sidecar extent, pixel and source class (the law's
  ``flat_source_class``, or the class the provider declares, #1929).
* :func:`source_label` — ``lidar 1 m`` inside an inset of that class,
  else the tile DEM's posting (``DEM 90 m`` for a 3-arc-second ``.hgt``,
  the cfg's convention: 30 m = 1 arc-second).
"""
from __future__ import annotations

import math
import os
import typing as _t

import numpy as np
import O4_File_Names as FNAMES

__all__ = ["AltPoints", "alt_path", "covering_inset",
           "inset_footprints", "source_label"]


def alt_path(folder: str, lat0: int, lon0: int) -> str:
    """The built tile's ``Data<tile>.alt`` (read where the mesh is read)."""
    return FNAMES.rebuild_path(folder, lat0, lon0,
                               "Data" + FNAMES.short_latlon(lat0, lon0) + ".alt")


class AltPoints:
    """Point reads of a built ``.alt`` (float32, row 0 north) in its frame
    (``O4_DEM_Utils.resolve_alt_frame``); raises when the frame cannot be
    established."""

    def __init__(self, path: str, lat0: int, lon0: int) -> None:
        import O4_DEM_Utils as DEM_UTILS
        side = int(round(math.sqrt(os.path.getsize(path) // 4)))
        if side < 2 or side * side * 4 != os.path.getsize(path):
            raise ValueError(f"{path}: not a square float32 raster")
        frame = DEM_UTILS.resolve_alt_frame(path, side, lat0, lon0)
        self.path, self.lat0, self.lon0, self.side = path, lat0, lon0, side
        self.frame = (frame["x0"], frame["x1"], frame["y0"], frame["y1"])

    def z(self, lat: float, lon: float) -> float | None:
        """The mesh's bilinear at ``(lat, lon)``; None outside the frame."""
        from auto_patch_v2.airport.dem_production import baked_cell
        x0, x1, y0, y1 = self.frame
        if not (x0 <= lon - self.lon0 <= x1 and y0 <= lat - self.lat0 <= y1):
            return None
        iy, ix, iyp, ixp, ry, rx = (np.asarray(v).item() for v in baked_cell(
            np.array([lat]), np.array([lon]), self.lat0, self.lon0, self.frame,
            self.side, self.side))
        with open(self.path, "rb") as fh:
            z0, z1 = (self._row(fh, row, ix, ixp) for row in (iy, iyp))
        value = ((1 - ry) * ((1 - rx) * z0[0] + rx * z0[1])
                 + ry * ((1 - rx) * z1[0] + rx * z1[1]))
        return float(value) if math.isfinite(value) else None

    def _row(self, fh, row: int, ix: int, ixp: int) -> tuple[float, float]:
        fh.seek((row * self.side + ix) * 4)
        posts = np.frombuffer(fh.read(4 * (ixp - ix + 1)), dtype="<f4")
        return float(posts[0]), float(posts[-1])


class _InsetFootprint(_t.NamedTuple):
    """One cached inset: its airport, raster, WGS84 box
    ``(lon_min, lat_min, lon_max, lat_max)``, pixel and source class."""

    icao: str
    path: str
    bbox: tuple[float, float, float, float]
    pixel_m: float | None
    source_class: str | None


def _pixel(meta: dict) -> float | None:
    for key in ("native_resolution_m", "resolution_m"):
        try:
            value = float(meta.get(key))
        except (TypeError, ValueError):
            continue
        if value > 0:
            return value
    return None


def inset_footprints(lat0: int, lon0: int, law=None) -> list[_InsetFootprint]:
    """The tile's cached insets that carry a sidecar extent (an inset
    without one cannot be placed, so it is not listed)."""
    from auto_patch_v2.law.tables import flat_source_class
    from O4_Airport_Elevation_Insets import list_cached_inset_dems
    out = []
    for path in list_cached_inset_dems(lat0, lon0):
        meta = FNAMES.read_json_dict(path[:-4] + ".json")
        box = meta.get("delivered_bounding_box_wgs84") or meta.get("bounding_box_wgs84")
        try:
            bbox = tuple(float(v) for v in box)
        except (TypeError, ValueError):
            continue
        if len(bbox) != 4:
            continue
        pixel = _pixel(meta)
        klass = meta.get("dem_class") or (
            flat_source_class(law, pixel) if law is not None else None)
        out.append(_InsetFootprint(os.path.basename(path).split("_", 1)[0].upper(),
                                   path, bbox, pixel, klass))
    return out


def covering_inset(footprints: _t.Iterable[_InsetFootprint], lat: float,
                   lon: float) -> _InsetFootprint | None:
    """The finest inset whose box holds the point, or None."""
    inside = [f for f in footprints
              if f.bbox[0] <= lon <= f.bbox[2] and f.bbox[1] <= lat <= f.bbox[3]]
    return min(inside, key=lambda f: f.pixel_m or math.inf, default=None)


def _tile_dem_label(lat0: int, lon0: int) -> str | None:
    """``DEM 90 m`` / ``DEM 30 m`` from the tile ``.hgt``'s posting, or
    None when the tile has none."""
    path = os.path.join(FNAMES.Elevation_dir, FNAMES.round_latlon(lat0, lon0),
                        FNAMES.hem_latlon(lat0, lon0) + ".hgt")
    try:
        side = int(round(math.sqrt(os.path.getsize(path) // 2)))
    except OSError:
        return None
    if side < 2:
        return None
    return "DEM %d m" % round(30 * 3600 / (side - 1))


def _metres(value: float) -> str:
    return "%g m" % (round(value, 1) if value < 10 else round(value))


def source_label(inset: _InsetFootprint | None, lat0: int, lon0: int) -> str | None:
    """The words that name the base value's source at a point."""
    if inset is not None and inset.pixel_m is not None:
        word = "lidar" if inset.source_class == "lidar" else "DEM"
        return f"{word} {_metres(inset.pixel_m)}"
    return _tile_dem_label(lat0, lon0)
