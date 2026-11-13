"""The colour cast between two photo providers along a tile edge (#2018,
spec ``docs/specs/auto-imagery-provider-spec-20261113.md`` §3), the
measurement ``O4_Imagery_Provider_Blend`` blends with.

* :func:`edge_squares` -- the texture squares (ZL :data:`CAST_ZL`) that
  straddle an edge (``O4_Imagery_Provider_Blend.edge_key``): each shows
  the same ground in both providers, so their colour difference is the
  providers', not the ground's.
* :func:`measure` -- ``mean(b - a)`` per RGB channel over the pixels
  both images show (luminance in [10, 248] in both, the
  ``O4_Color_Harmonization`` gate), clipped to :data:`MAX_CAST`; None
  below :data:`MIN_PIXELS`.  ``image_of(provider, til_x, til_y)`` gives a
  square's RGB array; with ``edge`` only the pixels within
  :data:`BAND_DEG` of the edge line count -- the ground the seam shows.
  The mean of differences is antisymmetric (the tile on the other side
  measures exactly ``-c``) and closes the gap of the mean colours.  Two
  providers differ in contrast as well as level, so the band matters: on
  the BI/USA2 edge at 32 N 110 W (lane l2018) the whole squares read
  +21 red, a 1.7 km band +34, the median of the squares +14.
* :class:`CastBook` -- the casts measured, one JSON file in the data
  folder, so both tiles of an edge read the same value whenever each is
  made.
* :func:`fetch_square` -- the production ``image_of``: the square's
  512 px placeholder JPEG (drop :data:`CAST_DROP`, raised to the
  provider's ``min_source_zl`` by ``download_jpeg_ortho``, #2017), the
  same file the drape of that tile fetches, cached where it looks.

No tile or airport is named here.
"""
from __future__ import annotations

import json
import os
import threading
from typing import Callable, Optional, Sequence, Tuple

import numpy

__all__ = ["CAST_ZL", "CAST_DROP", "MAX_CAST", "MIN_PIXELS", "BAND_DEG",
           "fetch_square", "book"]

#: Texture squares at this zoom (a drape's own) are measured...
CAST_ZL = 16
#: ...at their 512 px tier (``O4_Imagery_Placeholder``).
CAST_DROP = 3
#: Per-channel cap in 0-255 counts (twice ``MAXIMUM_SHIFT_MAGNITUDE``: a
#: blending pair closes up to this much between them).
MAX_CAST = 40.0
#: Pixels both images must show for a cast.
MIN_PIXELS = 2000
#: Only the pixels this close to the edge line (degrees, ~1.7 km) count.
BAND_DEG = 1.0 / 64.0
#: Each square is reduced to this many pixels per side before comparing.
_SAMPLE = 128
_LUMA = numpy.array([0.299, 0.587, 0.114])
_EPS = 1e-9
_BOOK_NAME = "provider_casts.json"


def edge_squares(edge: Tuple[str, int, int], zoomlevel: int = CAST_ZL) -> list:
    """``[(til_x, til_y)]`` of the texture squares straddling ``edge``
    (``("H", lat, lon)``: latitude ``lat`` over ``[lon, lon+1]``;
    ``("V", lat, lon)``: longitude ``lon`` over ``[lat, lat+1]``)."""
    import O4_Geo_Utils as GEO
    kind, lat, lon = edge
    if kind == "H":
        x0, y = GEO.wgs84_to_orthogrid(lat, lon + _EPS, zoomlevel)
        x1, _ = GEO.wgs84_to_orthogrid(lat, lon + 1 - _EPS, zoomlevel)
        return [(x, y) for x in range(x0, x1 + 1, 16)]
    x, y0 = GEO.wgs84_to_orthogrid(lat + 1 - _EPS, lon, zoomlevel)
    _, y1 = GEO.wgs84_to_orthogrid(lat + _EPS, lon, zoomlevel)
    return [(x, y) for y in range(y0, y1 + 1, 16)]


def _valid(rgb: numpy.ndarray) -> numpy.ndarray:
    luma = rgb @ _LUMA
    return (luma >= 10.0) & (luma <= 248.0)


def _near(edge, til_x: int, til_y: int, shape) -> numpy.ndarray:
    """The pixels of a square (an image of ``shape``) within
    :data:`BAND_DEG` of ``edge``'s line."""
    kind, lat, lon = edge
    half = 2.0 ** (CAST_ZL - 1)
    if kind == "H":
        u = (numpy.arange(shape[0]) + 0.5) / shape[0] * 16.0
        lats = 360.0 / numpy.pi * numpy.arctan(numpy.exp(
            numpy.pi * (1.0 - (til_y + u) / half))) - 90.0
        return numpy.broadcast_to((numpy.abs(lats - lat) <= BAND_DEG)[:, None],
                                  shape[:2])
    u = (numpy.arange(shape[1]) + 0.5) / shape[1] * 16.0
    lons = ((til_x + u) / half - 1.0) * 180.0
    return numpy.broadcast_to((numpy.abs(lons - lon) <= BAND_DEG)[None, :],
                              shape[:2])


def measure(squares: Sequence[Tuple[int, int]], a: str, b: str,
            image_of: Callable[[str, int, int], Optional[numpy.ndarray]],
            edge: Optional[Tuple[str, int, int]] = None
            ) -> Optional[Tuple[float, float, float]]:
    """``mean(b - a)`` per channel over ``squares``, near ``edge`` when
    one is given (module docstring)."""
    diffs = []
    for til_x, til_y in squares:
        first, second = image_of(a, til_x, til_y), image_of(b, til_x, til_y)
        if first is None or second is None:
            continue
        first = numpy.asarray(first, dtype=numpy.float64)[..., :3]
        second = numpy.asarray(second, dtype=numpy.float64)[..., :3]
        both = _valid(first) & _valid(second)
        if edge is not None:
            both = both & _near(edge, til_x, til_y, first.shape)
        diffs.append((second - first)[both])
    if not diffs:
        return None
    stacked = numpy.concatenate(diffs)
    if len(stacked) < MIN_PIXELS:
        return None
    cast = numpy.clip(stacked.mean(axis=0), -MAX_CAST, MAX_CAST)
    return tuple(round(float(v), 2) for v in cast)


class CastBook:
    """The casts measured, by edge and provider pair (module docstring).
    ``None`` is remembered too (an edge with no common pixels)."""

    def __init__(self, path: str) -> None:
        self.path = path
        self._lock = threading.Lock()
        self._casts: Optional[dict] = None

    @staticmethod
    def key(edge, a: str, b: str, zoomlevel: int = CAST_ZL) -> str:
        kind, lat, lon = edge
        return f"{kind}{lat:+03d}{lon:+04d}:{a}:{b}:{zoomlevel}"

    def _load(self) -> dict:
        if self._casts is None:
            try:
                with open(self.path, encoding="utf-8") as handle:
                    data = json.load(handle)
                self._casts = data if isinstance(data, dict) else {}
            except (OSError, ValueError):
                self._casts = {}
        return self._casts

    def cast(self, edge, a: str, b: str,
             image_of: Callable[[str, int, int], Optional[numpy.ndarray]]
             ) -> Optional[Tuple[float, float, float]]:
        """The cast of ``edge`` from ``a`` to ``b``: the book's, else
        measured now and written."""
        key = self.key(edge, a, b)
        with self._lock:
            casts = self._load()
            if key in casts:
                value = casts[key]
                return None if value is None else tuple(value)
        value = measure(edge_squares(edge), a, b, image_of, edge)
        with self._lock:
            casts = self._load()
            casts[key] = None if value is None else list(value)
            try:
                os.makedirs(os.path.dirname(self.path), exist_ok=True)
                with open(self.path + ".tmp", "w", encoding="utf-8",
                          newline="\n") as handle:
                    json.dump(casts, handle, sort_keys=True)
                os.replace(self.path + ".tmp", self.path)
            except OSError:
                pass                        # a cache: measured again next time
        return value


_BOOK: dict = {}


def book() -> CastBook:
    """The data folder's book (``World_build/provider_casts.json``)."""
    import O4_File_Names as FNAMES
    path = os.path.join(FNAMES.data_path("World_build"), _BOOK_NAME)
    return _BOOK.setdefault(path, CastBook(path))


def fetch_square(provider_code: str, til_x: int, til_y: int,
                 folder_tile: Tuple[int, int]) -> Optional[numpy.ndarray]:
    """A square's 512 px photo from ``provider_code`` as a
    ``_SAMPLE``-pixel RGB array, from the imagery cache of tile
    ``folder_tile`` (downloaded there when missing); None when it cannot
    be had.  The provider registries must be loaded."""
    import O4_Imagery_Placeholder as PLACEHOLDER
    import O4_Imagery_Utils as IMG
    from PIL import Image
    provider = IMG.providers_dict.get(provider_code)
    if provider is None:
        return None
    lat, lon = folder_tile
    folder = PLACEHOLDER.jpeg_dir(lat, lon, CAST_ZL, provider, CAST_DROP)
    name = PLACEHOLDER.jpeg_name(til_x, til_y, CAST_ZL, provider_code,
                                 CAST_DROP, provider)
    path = os.path.join(folder, name)
    if not os.path.isfile(path):
        try:
            IMG.download_orthophoto_once(folder, name, til_x, til_y, CAST_ZL,
                                         provider_code, drop=CAST_DROP,
                                         require_complete=True)
        except Exception:
            return None
    try:
        with Image.open(path) as image:
            small = image.convert("RGB").resize((_SAMPLE, _SAMPLE), Image.BOX)
    except (OSError, ValueError):
        return None
    return numpy.asarray(small)
