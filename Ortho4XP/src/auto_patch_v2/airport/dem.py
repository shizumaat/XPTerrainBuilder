"""The DEM + insets sampler (``model.airport.DemSample``; M0 §4 step 1:
"``DemSample`` over the .hgt with the inset applied (bilinear)").

Reads the SAME files the v1 harness frame resolves (``build_airport.py``
``dem_cache_state``): the tile ``Elevation_data/<block>/N60W136.hgt``
and the airport inset ``N60W136_airport_insets/<ICAO>_<provider>.tif``
(+ ``.json`` provenance) from the shared data repo — read-only, never a
download, never a private cache (RULINGS ``e9daef5``).  The composite is
``base + w * (inset - base)`` with ``w`` ramping 0 -> 1 over
``feather_m`` from the inset's edge (the ``airport_elevation_inset_
feather_m`` convention, taken as an argument, never from a cfg).

NOT carried from v1's production frame (reported in the M1 report):
the working-grid densification, the tile-overlay bake and
``smooth_raster_over_airports`` — v2 samples the authored rasters.
"""
from __future__ import annotations

import dataclasses as _dc
import json
import math
import os
import typing as _t

import numpy as np

from ..model.frame import Frame

__all__ = ["HgtRaster", "GeoTiffRaster", "DemSampler", "resolve_dem_files",
           "hgt_name", "load_dem"]

_LAT_SCALE = 111320.0


def hgt_name(lat: int, lon: int) -> str:
    """``N60W136`` for tile (60, -136)."""
    return (f"{'S' if lat < 0 else 'N'}{abs(lat):02d}"
            f"{'W' if lon < 0 else 'E'}{abs(lon):03d}")


def _block_dir(lat: int, lon: int) -> str:
    return f"{(lat // 10) * 10:+03d}{(lon // 10) * 10:+04d}"


@_dc.dataclass
class HgtRaster:
    """One SRTM-style ``.hgt``: big-endian int16, ``n x n``, row 0 at the
    tile's NORTH edge, column 0 at its WEST edge; -32768 = void."""

    path: str
    lat0: int
    lon0: int
    n: int
    data: np.ndarray

    @classmethod
    def read(cls, path: str, lat0: int, lon0: int) -> "HgtRaster":
        raw = np.fromfile(path, dtype=">i2")
        n = int(round(math.sqrt(raw.size)))
        if n * n != raw.size:
            raise ValueError(f"{path}: not a square raster ({raw.size})")
        data = raw.astype(np.float32).reshape((n, n))
        data[data <= -32768] = np.nan
        return cls(path, lat0, lon0, n, data)

    def sample(self, lat: np.ndarray, lon: np.ndarray) -> np.ndarray:
        """Bilinear; NaN outside the tile or over a void."""
        r = (self.lat0 + 1.0 - lat) * (self.n - 1)
        c = (lon - self.lon0) * (self.n - 1)
        return _bilinear(self.data, r, c)


@_dc.dataclass
class GeoTiffRaster:
    """A WGS84 GeoTIFF inset (``ModelPixelScale`` + ``ModelTiepoint``);
    ``lon0``/``lat0`` = the outer corner of pixel (0, 0) (PixelIsArea) —
    a PixelIsPoint file is shifted by half a pixel on read."""

    path: str
    lon0: float
    lat0: float
    dlon: float
    dlat: float
    data: np.ndarray
    nodata: float | None

    @classmethod
    def read(cls, path: str) -> "GeoTiffRaster":
        import tifffile  # local: the only raster-format import
        with tifffile.TiffFile(path) as tf:
            page = tf.pages[0]
            scale = page.tags["ModelPixelScaleTag"].value
            tie = page.tags["ModelTiepointTag"].value
            data = page.asarray().astype(np.float32, copy=False)
            nodata = None
            tag = page.tags.get("GDAL_NODATA")
            if tag is not None:
                try:
                    nodata = float(str(tag.value))
                except ValueError:
                    nodata = None
            keys = page.tags.get("GeoKeyDirectoryTag")
            point = False
            if keys is not None:
                k = list(keys.value)
                for i in range(4, len(k) - 3, 4):
                    if k[i] == 1025 and k[i + 3] == 2:
                        point = True
        dlon, dlat = float(scale[0]), float(scale[1])
        lon0 = float(tie[3]) - float(tie[0]) * dlon
        lat0 = float(tie[4]) + float(tie[1]) * dlat
        if point:
            lon0 -= dlon / 2
            lat0 += dlat / 2
        if nodata is not None:
            data = data.copy()
            data[data == nodata] = np.nan
        return cls(path, lon0, lat0, dlon, dlat, data, nodata)

    @property
    def bounds(self) -> tuple[float, float, float, float]:
        """``(lon_min, lat_min, lon_max, lat_max)`` of the raster edge."""
        h, w = self.data.shape
        return (self.lon0, self.lat0 - h * self.dlat, self.lon0 + w * self.dlon,
                self.lat0)

    def sample(self, lat: np.ndarray, lon: np.ndarray) -> np.ndarray:
        """Bilinear on pixel centres; NaN outside or over nodata."""
        r = (self.lat0 - lat) / self.dlat - 0.5
        c = (lon - self.lon0) / self.dlon - 0.5
        return _bilinear(self.data, r, c)

    def edge_distance_m(self, lat: np.ndarray, lon: np.ndarray) -> np.ndarray:
        """Distance (m) from each point to the nearest raster edge,
        negative outside."""
        w, s, e, n = self.bounds
        lon_scale = _LAT_SCALE * math.cos(math.radians((s + n) / 2))
        dx = np.minimum(lon - w, e - lon) * lon_scale
        dy = np.minimum(lat - s, n - lat) * _LAT_SCALE
        return np.minimum(dx, dy)


def _bilinear(data: np.ndarray, r: np.ndarray, c: np.ndarray) -> np.ndarray:
    h, w = data.shape
    out = np.full(r.shape, np.nan, dtype=np.float64)
    ok = (r >= 0) & (c >= 0) & (r <= h - 1) & (c <= w - 1)
    if not ok.any():
        return out
    rr, cc = r[ok], c[ok]
    r0 = np.clip(np.floor(rr).astype(int), 0, h - 2)
    c0 = np.clip(np.floor(cc).astype(int), 0, w - 2)
    fr = np.clip(rr - r0, 0.0, 1.0)
    fc = np.clip(cc - c0, 0.0, 1.0)
    z00 = data[r0, c0].astype(np.float64)
    z01 = data[r0, c0 + 1].astype(np.float64)
    z10 = data[r0 + 1, c0].astype(np.float64)
    z11 = data[r0 + 1, c0 + 1].astype(np.float64)
    out[ok] = ((1 - fr) * ((1 - fc) * z00 + fc * z01)
               + fr * ((1 - fc) * z10 + fc * z11))
    return out


class DemSampler:
    """``DemSample`` over the base tiles + one feathered inset, in the
    airport frame.  Base tiles are loaded lazily per 1° cell touched."""

    def __init__(self, frame: Frame, elevation_root: str,
                 inset: GeoTiffRaster | None, feather_m: float,
                 provenance: _t.Mapping[str, str]) -> None:
        self.frame = frame
        self.elevation_root = elevation_root
        self.inset = inset
        self.feather_m = float(feather_m)
        self.provenance = dict(provenance)
        self._tiles: dict[tuple[int, int], HgtRaster | None] = {}
        from pyproj import Transformer  # local: geodesy stays in the loaders
        self._inv = Transformer.from_crs(frame.crs, "EPSG:4326",
                                         always_xy=True)

    # ── DemSample protocol ──────────────────────────────────────────
    def z(self, x: float, y: float) -> float:
        return float(self.z_many(np.array([x]), np.array([y]))[0])

    def bounds(self) -> tuple[float, float, float, float]:
        """The frame box of the tile that holds the origin."""
        lat, lon = self.frame.origin
        t0, t1 = math.floor(lat), math.floor(lon)
        from pyproj import Transformer
        fwd = Transformer.from_crs("EPSG:4326", self.frame.crs, always_xy=True)
        xs, ys = fwd.transform([t1, t1 + 1, t1, t1 + 1],
                               [t0, t0, t0 + 1, t0 + 1])
        return (min(xs), min(ys), max(xs), max(ys))

    # ── vectorised entry ────────────────────────────────────────────
    def z_many(self, xs: np.ndarray, ys: np.ndarray) -> np.ndarray:
        """Composite elevation at frame points (NaN where no raster)."""
        lon, lat = self._inv.transform(np.asarray(xs, dtype=np.float64),
                                       np.asarray(ys, dtype=np.float64))
        lon, lat = np.asarray(lon), np.asarray(lat)
        base = self._sample_base(lat, lon)
        if self.inset is None:
            return base
        ins = self.inset.sample(lat, lon)
        d = self.inset.edge_distance_m(lat, lon)
        w = np.clip(d / self.feather_m, 0.0, 1.0) if self.feather_m > 0 \
            else (d >= 0).astype(np.float64)
        have = np.isfinite(ins)
        out = base.copy()
        both = have & np.isfinite(base)
        out[both] = base[both] + w[both] * (ins[both] - base[both])
        only = have & ~np.isfinite(base)
        out[only] = ins[only]
        return out

    def _sample_base(self, lat: np.ndarray, lon: np.ndarray) -> np.ndarray:
        out = np.full(lat.shape, np.nan)
        tl = np.floor(lat).astype(int)
        tn = np.floor(lon).astype(int)
        for key in set(zip(tl.tolist(), tn.tolist())):
            tile = self._tile(*key)
            if tile is None:
                continue
            m = (tl == key[0]) & (tn == key[1])
            out[m] = tile.sample(lat[m], lon[m])
        return out

    def _tile(self, lat: int, lon: int) -> HgtRaster | None:
        key = (lat, lon)
        if key not in self._tiles:
            path = os.path.join(self.elevation_root, _block_dir(lat, lon),
                                hgt_name(lat, lon) + ".hgt")
            self._tiles[key] = HgtRaster.read(path, lat, lon) \
                if os.path.isfile(path) else None
            self.provenance[f"hgt:{hgt_name(lat, lon)}"] = path
        return self._tiles[key]


def resolve_dem_files(elevation_root: str, lat: float, lon: float,
                      icao: str) -> tuple[str, str | None, str | None]:
    """``(hgt_path, inset_tif | None, inset_json | None)`` for the tile
    holding ``(lat, lon)``: the first ``<ICAO>_*.tif`` in the tile's
    ``_airport_insets`` directory (the harness's own resolution)."""
    tl, tn = int(math.floor(lat)), int(math.floor(lon))
    stem = hgt_name(tl, tn)
    d = os.path.join(elevation_root, _block_dir(tl, tn))
    hgt = os.path.join(d, stem + ".hgt")
    ins_dir = os.path.join(d, stem + "_airport_insets")
    tif = js = None
    if os.path.isdir(ins_dir):
        for name in sorted(os.listdir(ins_dir)):
            if name.upper().startswith(icao.upper() + "_") and name.endswith(".tif"):
                tif = os.path.join(ins_dir, name)
                cand = tif[:-4] + ".json"
                js = cand if os.path.isfile(cand) else None
                break
    return hgt, tif, js


def load_dem(frame: Frame, elevation_root: str, icao: str,
             feather_m: float = 60.0) -> DemSampler:
    """The sampler for ``icao`` at the frame origin's tile."""
    lat, lon = frame.origin
    hgt, tif, js = resolve_dem_files(elevation_root, lat, lon, icao)
    if not os.path.isfile(hgt):
        raise FileNotFoundError(f"base DEM missing: {hgt} (warm it with "
                                "build_airport.py --refresh-data dem)")
    prov: dict[str, str] = {"base": hgt, "feather_m": str(feather_m)}
    inset = None
    if tif is not None:
        inset = GeoTiffRaster.read(tif)
        prov["inset"] = tif
        if js is not None:
            try:
                with open(js) as fh:
                    meta = json.load(fh)
                prov["inset_provider"] = str(meta.get("provider", ""))
                prov["inset_source_ids"] = ",".join(meta.get("source_ids", []))
                prov["inset_vertical_datum"] = str(meta.get("vertical_datum", ""))
            except (OSError, ValueError):
                pass
    return DemSampler(frame, elevation_root, inset, feather_m, prov)
