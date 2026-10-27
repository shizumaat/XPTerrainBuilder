"""THE BUILD'S AIRPORT IMAGERY, READ (#1359; spec
``docs/specs/multi-source-terrain-spec.md`` §2, §7.1, §7.4).

The imagery voter reads the orthophotos THIS build textures the airport
with — never a second download.  A :class:`TextureSet` is the list of
those textures (``{til_y}_{til_x}_{provider}{zl}`` JPEGs of the imagery
cache, or the ``.dds`` of a built tile), each covering one 16×16 block of
web-mercator tiles at its zoom (4,096 px).  :meth:`TextureSet.patch`
resamples them north-up into the airport frame as an
:class:`~.image_provider.ImagePatch`, decoding a texture only when a
window touches it (a small LRU keeps the last few decoded).  Where two
zooms cover a point the finer one answers.

Pixels only: nothing here is written, and nothing knows the airport.
"""
from __future__ import annotations

import collections
import dataclasses as _dc
import math
import os
import typing as _t

import numpy as np
import O4_Custom_Scenery as _cs
from PIL import Image
from pyproj import Transformer
from scipy import ndimage

from .image_provider import ImagePatch

__all__ = ["TextureRef", "TextureSet", "texture_of_file", "global_pixel",
           "built_tile_paths"]

_EXTS = (".dds", ".jpg", ".jpeg", ".png")
#: a texture whose block centre lies further than this from the airport is
#: another tile's (a provider code ending in digits mis-split)
_NEAR_DEG = 1.5
#: decoded textures kept (each 4096² RGB is 48 MB)
_LRU = 4
_TEX_PX = 4096


@_dc.dataclass(frozen=True)
class TextureRef:
    """One texture: the top-left web-mercator tile of its 16×16 block, its
    zoom, provider code, and the file holding its pixels."""

    til_x: int
    til_y: int
    zoom: int
    provider: str
    path: str

    @property
    def source(self) -> str:
        """``provider@zoom`` (the evidence's ``source``)."""
        return f"{self.provider}@{self.zoom}"


def global_pixel(lat: np.ndarray, lon: np.ndarray, zoom: int) -> tuple[np.ndarray, np.ndarray]:
    """Web-mercator global pixel ``(x, y)`` of ``(lat, lon)`` at ``zoom``
    (256 px per tile; ``O4_Geo_Utils.wgs84_to_pix`` without the rounding)."""
    lat = np.asarray(lat, dtype=float)
    lon = np.asarray(lon, dtype=float)
    scale = 2.0 ** (zoom + 7)
    px = (lon / 180.0 + 1.0) * scale
    py = (1.0 - np.log(np.tan((90.0 + lat) * math.pi / 360.0)) / math.pi) * scale
    return px, py


def texture_of_file(path: str, lat: float, lon: float) -> TextureRef | None:
    """The texture a file named ``{til_y}_{til_x}_{provider}{zl}[_suffix].ext``
    holds, if its block lies near ``(lat, lon)``; else None."""
    name = os.path.basename(path)
    stem, ext = os.path.splitext(name)
    if ext.lower() not in _EXTS:
        return None
    parsed = _cs.parse_texture_stem(stem)
    if parsed is None:
        return None
    provider, zoom = parsed
    parts = stem.split("_", 2)
    til_y, til_x = int(parts[0]), int(parts[1])
    scale = 2.0 ** (zoom - 1)
    c_lon = ((til_x + 8) / scale - 1.0) * 180.0
    c_lat = 360.0 / math.pi * math.atan(math.exp(math.pi * (1.0 - (til_y + 8) / scale))) - 90.0
    if abs(c_lat - lat) > _NEAR_DEG or abs(c_lon - lon) > _NEAR_DEG:
        return None
    return TextureRef(til_x, til_y, zoom, provider, path)


class TextureSet:
    """The textures one build reads the airport from (see the module)."""

    def __init__(self, refs: _t.Iterable[TextureRef]):
        self.refs: tuple[TextureRef, ...] = tuple(sorted(
            refs, key=lambda r: (-r.zoom, r.provider, r.til_y, r.til_x)))
        self._by_key = {(r.zoom, r.til_x, r.til_y): r for r in self.refs}
        self._zooms = sorted({r.zoom for r in self.refs}, reverse=True)
        self._decoded: "collections.OrderedDict[str, np.ndarray]" = collections.OrderedDict()
        self.decodes = 0

    def __len__(self) -> int:
        return len(self.refs)

    @classmethod
    def from_files(cls, paths: _t.Iterable[str], lat: float, lon: float) -> "TextureSet":
        """The textures among ``paths`` that lie near ``(lat, lon)``."""
        refs = [r for p in paths if (r := texture_of_file(p, lat, lon)) is not None]
        return cls(refs)

    @classmethod
    def from_built_tile(cls, tile_dir: str, lat: float, lon: float) -> "TextureSet":
        """A built tile's LIVE textures: those its ``terrain/*.ter`` files
        name (a ``textures/`` folder can hold stale textures of an earlier
        build with another provider), read from ``textures/*.dds``."""
        tex_dir = os.path.join(tile_dir, "textures")
        try:
            ters = os.listdir(os.path.join(tile_dir, "terrain"))
        except OSError:
            ters = []
        live = set()
        for t in ters:
            if not t.endswith(".ter"):
                continue
            stem = t[:-4]
            for suffix in ("_overlay", "_water", "_sea"):
                if stem.endswith(suffix):
                    stem = stem[: -len(suffix)]
            live.add(stem)
        paths = [os.path.join(tex_dir, f"{s}.dds") for s in sorted(live)]
        return cls.from_files([p for p in paths if os.path.isfile(p)], lat, lon)

    def identity(self) -> list[tuple[str, int]]:
        """``(file name, byte size)`` of every texture (a freshness input)."""
        out = []
        for r in self.refs:
            try:
                out.append((os.path.basename(r.path), os.path.getsize(r.path)))
            except OSError:
                out.append((os.path.basename(r.path), -1))
        return out

    def _pixels(self, ref: TextureRef) -> np.ndarray:
        arr = self._decoded.get(ref.path)
        if arr is not None:
            self._decoded.move_to_end(ref.path)
            return arr
        with Image.open(ref.path) as im:
            arr = np.asarray(im.convert("RGB"))
        self.decodes += 1
        self._decoded[ref.path] = arr
        while len(self._decoded) > _LRU:
            self._decoded.popitem(last=False)
        return arr

    def sample(self, lat: np.ndarray, lon: np.ndarray) -> tuple[np.ndarray, np.ndarray, str]:
        """Bilinear RGB (N×3 float32) at the points, a validity mask, and the
        ``source`` that answered most of them; the finest zoom wins."""
        lat = np.asarray(lat, dtype=float).ravel()
        lon = np.asarray(lon, dtype=float).ravel()
        n = lat.size
        rgb = np.zeros((n, 3), dtype=np.float32)
        ok = np.zeros(n, dtype=bool)
        used: collections.Counter = collections.Counter()
        for zoom in self._zooms:
            todo = ~ok
            if not todo.any():
                break
            px, py = global_pixel(lat[todo], lon[todo], zoom)
            idx = np.flatnonzero(todo)
            bx = (np.floor(px / 256.0 / 16.0) * 16).astype(np.int64)
            by = (np.floor(py / 256.0 / 16.0) * 16).astype(np.int64)
            for kx, ky in set(zip(bx.tolist(), by.tolist(), strict=True)):
                ref = self._by_key.get((zoom, kx, ky))
                if ref is None:
                    continue
                sel = (bx == kx) & (by == ky)
                col = px[sel] - kx * 256.0 - 0.5
                row = py[sel] - ky * 256.0 - 0.5
                arr = self._pixels(ref)
                coords = np.vstack([np.clip(row, 0, _TEX_PX - 1), np.clip(col, 0, _TEX_PX - 1)])
                for c in range(3):
                    rgb[idx[sel], c] = ndimage.map_coordinates(
                        arr[..., c], coords, order=1, mode="nearest")
                ok[idx[sel]] = True
                used[ref.source] += int(sel.sum())
        source = used.most_common(1)[0][0] if used else ""
        return rgb, ok, source

    def patch(self, crs: str, x0: float, y0: float, x1: float, y1: float,
              m_per_px: float, corridor: tuple | None = None) -> ImagePatch | None:
        """The textures resampled north-up over the airport-frame box
        ``[x0, x1] × [y0, y1]`` at ``m_per_px``; None when nothing covers it.
        ``corridor = (a_xy, b_xy, half_width_m)`` samples only the pixels
        within that distance of segment a–b (the rest read not ``valid``),
        so a long diagonal probe pays for its strip, not its bounding box."""
        if not self.refs:
            return None
        w = max(1, int(math.ceil((x1 - x0) / m_per_px)))
        h = max(1, int(math.ceil((y1 - y0) / m_per_px)))
        lat, lon = _grid_ll(crs, x0 + 0.5 * m_per_px, y1 - 0.5 * m_per_px, m_per_px, w, h)
        keep = np.ones((h, w), dtype=bool)
        if corridor is not None:
            keep = _within(corridor, x0 + 0.5 * m_per_px, y1 - 0.5 * m_per_px, m_per_px, w, h)
        rgb = np.zeros((h * w, 3), dtype=np.float32)
        ok = np.zeros(h * w, dtype=bool)
        sel = keep.ravel()
        got, got_ok, source = self.sample(lat.ravel()[sel], lon.ravel()[sel])
        rgb[sel], ok[sel] = got, got_ok
        if not ok.any():
            return None
        return ImagePatch(np.clip(rgb, 0, 255).astype(np.uint8).reshape(h, w, 3),
                          float(m_per_px), (float(x0), float(y1)), source,
                          ok.reshape(h, w))


def _within(corridor: tuple, xa: float, ya: float, step: float, w: int, h: int) -> np.ndarray:
    """h×w: whether each pixel centre lies within the corridor's half width
    of its segment."""
    (ax, ay), (bx, by), hw = corridor
    gx, gy = np.meshgrid(xa + np.arange(w) * step, ya - np.arange(h) * step)
    dx, dy = bx - ax, by - ay
    L2 = dx * dx + dy * dy
    t = np.clip(((gx - ax) * dx + (gy - ay) * dy) / L2, 0.0, 1.0) if L2 > 0 else 0.0
    return np.hypot(gx - (ax + t * dx), gy - (ay + t * dy)) <= hw


def built_tile_paths(scenery_dir: str, lat: float, lon: float,
                     margin_deg: float = 0.05) -> tuple[str, ...]:
    """The LIVE textures of the built ortho tiles (``zOrtho4XP_+LL+LLL``
    under ``scenery_dir``) touching ``±margin_deg`` of ``(lat, lon)`` —
    the imagery an installed build textures the airport with (read-only;
    the patch is built standalone, without an imagery step of its own)."""
    out: list[str] = []
    tiles = sorted({(math.floor(lat + a), math.floor(lon + b))
                    for a in (-margin_deg, margin_deg) for b in (-margin_deg, margin_deg)})
    for la, lo in tiles:
        d = os.path.join(scenery_dir, f"zOrtho4XP_{la:+03d}{lo:+04d}")
        if os.path.isdir(d):
            out.extend(r.path for r in TextureSet.from_built_tile(d, lat, lon).refs)
    return tuple(sorted(out))


_INV: dict[str, Transformer] = {}
#: the exact projection is evaluated on a coarse lattice this many metres
#: apart and interpolated between (a transverse Mercator frame is affine to
#: well under a millimetre over that span)
_LATTICE_M = 50.0


def _grid_ll(crs: str, xa: float, ya: float, step: float, w: int, h: int
             ) -> tuple[np.ndarray, np.ndarray]:
    """``(lat, lon)`` h×w of the pixel centres ``x = xa + c·step``,
    ``y = ya − r·step``: exact on a lattice, bilinear between."""
    nc = max(2, int(math.ceil(w * step / _LATTICE_M)) + 1)
    nr = max(2, int(math.ceil(h * step / _LATTICE_M)) + 1)
    lc = np.linspace(0.0, max(w - 1, 1), nc)
    lr = np.linspace(0.0, max(h - 1, 1), nr)
    gx, gy = np.meshgrid(xa + lc * step, ya - lr * step)
    lon, lat = _inverse(crs).transform(gx.ravel(), gy.ravel())
    lat = np.asarray(lat).reshape(nr, nc)
    lon = np.asarray(lon).reshape(nr, nc)
    rr = np.interp(np.arange(h), lr, np.arange(nr))
    cc = np.interp(np.arange(w), lc, np.arange(nc))
    R, C = np.meshgrid(rr, cc, indexing="ij")
    return (ndimage.map_coordinates(lat, [R, C], order=1),
            ndimage.map_coordinates(lon, [R, C], order=1))


def _inverse(crs: str) -> Transformer:
    """Frame metres -> lon/lat, cached per CRS string."""
    t = _INV.get(crs)
    if t is None:
        t = _INV[crs] = Transformer.from_crs(crs, "EPSG:4326", always_xy=True)
    return t
