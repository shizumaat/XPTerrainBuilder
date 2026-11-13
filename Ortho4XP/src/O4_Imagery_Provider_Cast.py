"""The colour cast between two photo providers along a tile edge (#2018,
spec ``docs/specs/auto-imagery-provider-spec-20261113.md`` §3), the
measurement ``O4_Imagery_Provider_Blend`` blends with.

* :func:`edge_squares` -- the texture squares (ZL :data:`CAST_ZL`) that
  straddle an edge (``O4_Imagery_Provider_Blend.edge_key``): each shows
  the same ground in both providers, so their colour difference is the
  providers', not the ground's.
* :class:`EdgeStats` -- the per-channel mean and standard deviation of
  each provider over the pixels of some squares both images show
  (luminance in [10, 248] in both, the ``O4_Color_Harmonization`` gate)
  within :data:`BAND_DEG` of the edge line -- the ground the seam shows.
  Its ``offset`` (``mean(b - a)`` clipped to :data:`MAX_CAST`) is
  antisymmetric: the tile on the other side measures exactly ``-c``.
  The spreads carry the contrast an offset cannot close (#2018
  follow-up: BI/USA2 at 32 N 110 W reads L* std 8 against 15 within
  0.5 km of the line).
* :func:`_measure` -- ``[(t, EdgeStats)]``: each straddling square on
  its own (``image_of(provider, til_x, til_y)`` gives a square's RGB
  array), at the fraction ``t`` of the edge its centre lies at: the cast
  varies ALONG an edge as much as across it (BI/USA2 at 32 N 110 W: the
  150 m strips of the twelve squares read dE76 7 to 31, one BI scene
  ending ~0.7 km south of the line on part of it), which one value for
  the whole edge cannot follow.  None below :data:`MIN_PIXELS`.
* :class:`CastBook` -- the knots measured, one JSON file in the data
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
from dataclasses import dataclass
from typing import Callable, Optional, Sequence, Tuple

import numpy

__all__ = ["CAST_ZL", "CAST_DROP", "MAX_CAST", "MAX_GAIN", "MIN_PIXELS",
           "MIN_KNOT_PIXELS", "BAND_DEG", "EdgeStats",
           "fetch_square", "book"]

#: Texture squares at this zoom (a drape's own) are measured...
CAST_ZL = 16
#: ...at their 512 px tier (``O4_Imagery_Placeholder``).
CAST_DROP = 3
#: Per-channel cap in 0-255 counts: a blending pair closes up to this
#: much between them, each drape moving half.  Real provider casts reach
#: it (#2018 follow-up: BI/USA2 squares at 32 N 110 W read +50 to +71
#: red; the first round's 40 left dE76 7.1 where 80 leaves 3.4).
MAX_CAST = 80.0
#: The contrast ratio of two providers is clipped to [1/MAX_GAIN, MAX_GAIN].
MAX_GAIN = 2.0
#: Pixels both images must show for a cast...
MIN_PIXELS = 2000
#: ...and for one square's knot.
MIN_KNOT_PIXELS = 400
#: Only the pixels this close to the edge line (degrees, ~0.87 km) count:
#: the ground the seam shows (#2018 follow-up: 1/64 deg read the BI scene
#: beyond the line's own at 32 N 110 W, dE76 5.6 against 2.7 at 1/128;
#: 4.9 -> 4.4 at 33 N).
BAND_DEG = 1.0 / 128.0
#: Each square is reduced to this many pixels per side before comparing.
_SAMPLE = 128
_LUMA = numpy.array([0.299, 0.587, 0.114])
_EPS = 1e-9
_BOOK_NAME = "provider_casts.json"
RGB = Tuple[float, float, float]


@dataclass(frozen=True)
class EdgeStats:
    """Each provider's per-channel mean and standard deviation over the
    pixels of an edge both show (``a`` the provider south or west)."""

    mean_a: RGB
    mean_b: RGB
    std_a: RGB
    std_b: RGB

    @property
    def offset(self) -> RGB:
        """``mean(b - a)``, clipped to :data:`MAX_CAST`."""
        return tuple(float(numpy.clip(y - x, -MAX_CAST, MAX_CAST))
                     for x, y in zip(self.mean_a, self.mean_b, strict=True))

    def swapped(self) -> "EdgeStats":
        """The same edge seen from ``b``."""
        return EdgeStats(self.mean_b, self.mean_a, self.std_b, self.std_a)

    def as_list(self) -> list:
        return [list(self.mean_a), list(self.mean_b), list(self.std_a),
                list(self.std_b)]

    @classmethod
    def from_list(cls, value) -> "EdgeStats":
        return cls(*(tuple(float(v) for v in part) for part in value))


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


def _along(edge: Tuple[str, int, int], til_x: int, til_y: int,
           zoomlevel: int = CAST_ZL) -> float:
    """The fraction along ``edge`` (0 at its west or south end) of the
    centre of square (``til_x``, ``til_y``)."""
    kind, lat, lon = edge
    half = 2.0 ** (zoomlevel - 1)
    if kind == "H":
        return ((til_x + 8) / half - 1.0) * 180.0 - lon
    centre = 360.0 / numpy.pi * numpy.arctan(numpy.exp(
        numpy.pi * (1.0 - (til_y + 8) / half))) - 90.0
    return float(centre) - lat


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


def _pixels(squares, a: str, b: str, image_of, edge):
    """The pixels of ``squares`` both providers show (near ``edge`` when
    one is given): two ``(n, 3)`` arrays, or None."""
    pairs = []
    for til_x, til_y in squares:
        first, second = image_of(a, til_x, til_y), image_of(b, til_x, til_y)
        if first is None or second is None:
            continue
        first = numpy.asarray(first, dtype=numpy.float64)[..., :3]
        second = numpy.asarray(second, dtype=numpy.float64)[..., :3]
        both = _valid(first) & _valid(second)
        if edge is not None:
            both = both & _near(edge, til_x, til_y, first.shape)
        pairs.append((first[both], second[both]))
    if not pairs:
        return None
    return (numpy.concatenate([p[0] for p in pairs]),
            numpy.concatenate([p[1] for p in pairs]))


def _stats_of(first: numpy.ndarray, second: numpy.ndarray) -> EdgeStats:
    def rounded(values):
        return tuple(round(float(v), 2) for v in values)
    return EdgeStats(rounded(first.mean(axis=0)), rounded(second.mean(axis=0)),
                     rounded(first.std(axis=0)), rounded(second.std(axis=0)))


def _measure_squares(squares: Sequence[Tuple[int, int]], a: str, b: str,
            image_of: Callable[[str, int, int], Optional[numpy.ndarray]],
            edge: Optional[Tuple[str, int, int]] = None
            ) -> Optional[EdgeStats]:
    """The :class:`EdgeStats` of ``squares`` together, near ``edge`` when
    one is given (module docstring)."""
    pixels = _pixels(squares, a, b, image_of, edge)
    if pixels is None or len(pixels[0]) < MIN_PIXELS:
        return None
    return _stats_of(*pixels)


def _measure(edge: Tuple[str, int, int], a: str, b: str,
                  image_of: Callable[[str, int, int], Optional[numpy.ndarray]]
                  ) -> Optional[list]:
    """``[(t, EdgeStats)]``: each straddling square measured on its own
    near ``edge`` (at least :data:`MIN_KNOT_PIXELS`), at the fraction
    ``t`` of the edge its centre lies at (a square centred beyond the
    edge's ends is the next edge's); None when the knots hold fewer than
    :data:`MIN_PIXELS` together."""
    knots, total = [], 0
    for til_x, til_y in edge_squares(edge):
        t = _along(edge, til_x, til_y)
        if not 0.0 < t < 1.0:
            continue
        pixels = _pixels([(til_x, til_y)], a, b, image_of, edge)
        if pixels is None or len(pixels[0]) < MIN_KNOT_PIXELS:
            continue
        knots.append((round(t, 4), _stats_of(*pixels)))
        total += len(pixels[0])
    return knots if total >= MIN_PIXELS else None


class CastBook:
    """The casts measured, by edge and provider pair (module docstring).
    ``None`` is remembered too (an edge with no common pixels)."""

    def __init__(self, path: str) -> None:
        self.path = path
        self._lock = threading.Lock()
        self._casts: Optional[dict] = None

    @staticmethod
    def key(edge, a: str, b: str, zoomlevel: int = CAST_ZL) -> str:
        # ":knots": the first round's one offset per edge is measured again
        kind, lat, lon = edge
        return f"{kind}{lat:+03d}{lon:+04d}:{a}:{b}:{zoomlevel}:knots"

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
             ) -> Optional[list]:
        """The knots of ``edge`` from ``a`` to ``b`` (:func:`_measure`):
        the book's, else measured now and written."""
        key = self.key(edge, a, b)
        with self._lock:
            casts = self._load()
            if key in casts:
                value = casts[key]
                try:
                    return None if value is None else [
                        (float(t), EdgeStats.from_list(stats)) for t, stats in value]
                except (TypeError, ValueError):
                    pass                    # unreadable: measured again
        value = _measure(edge, a, b, image_of)
        with self._lock:
            casts = self._load()
            casts[key] = None if value is None else [
                [t, stats.as_list()] for t, stats in value]
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
