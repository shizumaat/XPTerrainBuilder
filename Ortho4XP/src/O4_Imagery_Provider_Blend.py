"""The colour blend across an edge where the photo provider changes
(#2018, spec ``docs/specs/auto-imagery-provider-spec-20261113.md`` §3).

A drape tile beside a tile drawn by another provider has its colour
pulled toward that provider, as ONE continuous field of position over
the tile -- never a per-texture constant (the per-texture shifts minted
the OTHH seams of 2026-09-18):

* each side s whose neighbour's provider differs carries the measured
  cast ``c`` (``O4_Imagery_Provider_Cast``: the mean neighbour-minus-own
  colour on the squares straddling the edge) and a midpoint value
  ``f = c/2`` when the neighbour will blend too, ``c + f_N`` when it has
  blended (its record's value), ``c`` when it never will (a full, kept or
  adopted tile);
* along the edge the value is piecewise linear: ``f`` at the midpoint,
  and at each end the corner value shared with the tile beside it along
  the edge (its record's, else the mean of the two midpoints when it
  blends on the same side, else 0);
* the value falls linearly to 0 at the opposite edge.

Every term vanishes on an edge whose far side does not apply the same
term, so the field never adds a step where there was none; across the
provider edge the two sides meet halfway.  :meth:`Blend.field` evaluates
it at a texture's pixel centres (``O4_Color_Harmonization``'s field
shape, applied by ``apply_color_field``), so two textures agree on their
shared edge.

Pure: numpy only; the facts about neighbours and the casts come in as
callables.  No tile or airport is named here.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Callable, Dict, Optional, Sequence, Tuple

import numpy

__all__ = ["SIDES", "TileFacts", "Blend", "plan", "add_field"]

#: Side -> (dlat, dlon) of the neighbour across it.
SIDES = {"N": (1, 0), "S": (-1, 0), "E": (0, 1), "W": (0, -1)}
#: Side -> the two along-edge directions (start end, finish end) and
#: whether the along-edge parameter is the longitude fraction.
_ALONG = {"N": ("W", "E"), "S": ("W", "E"), "E": ("S", "N"), "W": ("S", "N")}
_OPPOSITE = {"N": "S", "S": "N", "E": "W", "W": "E"}
#: The field's samples per texture edge (``O4_Color_Harmonization.FIELD_SIZE``).
FIELD_SIZE = 256
RGB = Tuple[float, float, float]


@dataclass(frozen=True)
class TileFacts:
    """What draws a tile: its ``provider``; ``built`` when the World pack
    holds a real tile there (else it will be a drape that blends); its
    record's ``blend`` sides (``{side: {"mid", "start", "end"}}``) when
    it blended."""

    provider: str
    built: bool = False
    blend: Dict[str, dict] = field(default_factory=dict)

    @property
    def blends(self) -> bool:
        return not self.built


def edge_key(lat: int, lon: int, side: str) -> Tuple[str, int, int]:
    """The edge on ``side`` of tile (``lat``, ``lon``), named from the
    tile south or west of it: ``("H", lat, lon)`` is the line at latitude
    ``lat`` over ``[lon, lon+1]``; ``("V", lat, lon)`` the line at
    longitude ``lon`` over ``[lat, lat+1]``."""
    dlat, dlon = SIDES[side]
    if dlat:
        return ("H", lat + max(dlat, 0), lon)
    return ("V", lat, lon + max(dlon, 0))


def _add(a, b) -> RGB:
    return tuple(float(x) + float(y) for x, y in zip(a, b, strict=False))


def _scale(a, k: float) -> RGB:
    return tuple(float(x) * k for x in a)


@dataclass
class Blend:
    """One tile's blend: ``terms[side] = (start, mid, end)`` RGB values
    along the edge (``start`` at its west or south end)."""

    lat: int
    lon: int
    terms: Dict[str, Tuple[RGB, RGB, RGB]] = field(default_factory=dict)
    toward: Dict[str, str] = field(default_factory=dict)

    def record(self) -> dict:
        """The sides as the World pack record keeps them."""
        return {side: {"toward": self.toward.get(side, ""),
                       "start": [round(v, 2) for v in start],
                       "mid": [round(v, 2) for v in mid],
                       "end": [round(v, 2) for v in end]}
                for side, (start, mid, end) in sorted(self.terms.items())}

    def at(self, lat, lon) -> numpy.ndarray:
        """The field's RGB offsets at points (numpy arrays of any shape)."""
        fx, fy = numpy.broadcast_arrays(
            numpy.clip(numpy.asarray(lon, dtype=numpy.float64) - self.lon, 0.0, 1.0),
            numpy.clip(numpy.asarray(lat, dtype=numpy.float64) - self.lat, 0.0, 1.0))
        out = numpy.zeros(fx.shape + (3,), dtype=numpy.float64)
        for side, (start, mid, end) in self.terms.items():
            t = fx if side in ("N", "S") else fy
            depth = {"N": fy, "S": 1.0 - fy, "E": fx, "W": 1.0 - fx}[side]
            lo = numpy.minimum(t, 0.5) * 2.0          # 0..1 over the first half
            hi = numpy.maximum(t - 0.5, 0.0) * 2.0    # 0..1 over the second
            first = t <= 0.5
            for ch in range(3):
                value = numpy.where(first, start[ch] + (mid[ch] - start[ch]) * lo,
                                    mid[ch] + (end[ch] - mid[ch]) * hi)
                out[..., ch] += value * depth
        return out

    def field(self, til_x: int, til_y: int, zoomlevel: int,
              size: int = FIELD_SIZE) -> Optional[numpy.ndarray]:
        """The ``(size, size, 3)`` float32 offsets over texture square
        (``til_x``, ``til_y``) at ``zoomlevel`` (16 x 16 map tiles), at its
        pixel centres; None when the tile has no term or it rounds to 0."""
        if not self.terms:
            return None
        u = (numpy.arange(size, dtype=numpy.float64) + 0.5) / size * 16.0
        half = 2.0 ** (zoomlevel - 1)
        lon = ((til_x + u) / half - 1.0) * 180.0
        lat = 360.0 / math.pi * numpy.arctan(numpy.exp(
            math.pi * (1.0 - (til_y + u) / half))) - 90.0
        values = self.at(lat[:, None], lon[None, :]).astype(numpy.float32)
        if not numpy.rint(values).any():
            return None
        return values


def _neighbour(lat: int, lon: int, side: str) -> Tuple[int, int]:
    dlat, dlon = SIDES[side]
    return lat + dlat, lon + dlon


def plan(lat: int, lon: int, provider: str,
         facts: Callable[[int, int], TileFacts],
         cast: Callable[[Tuple[str, int, int], str, str], Optional[Sequence[float]]]
         ) -> Blend:
    """The blend of drape tile (``lat``, ``lon``) drawn by ``provider``.
    ``facts(lat, lon)`` says what draws a neighbour; ``cast(edge, a, b)``
    is ``mean(b - a)`` on an edge (``a`` the provider south or west of
    it), or None when it cannot be measured."""
    me = TileFacts(provider)

    def facts_of(key):
        return me if key == (lat, lon) else facts(*key)

    def midpoint(key, side) -> Optional[RGB]:
        """The midpoint value tile ``key`` applies (or would) on ``side``."""
        own = facts_of(key)
        if own.built:
            rec = own.blend.get(side)
            return tuple(rec["mid"]) if rec else None
        other_key = _neighbour(*key, side)
        other = facts_of(other_key)
        if not own.provider or not other.provider or other.provider == own.provider:
            return None
        south_west = side in ("S", "W")
        a, b = ((other.provider, own.provider) if south_west
                else (own.provider, other.provider))
        measured = cast(edge_key(*key, side), a, b)
        if measured is None:
            return None
        c = _scale(measured, -1.0 if south_west else 1.0)   # toward the other
        if other.blends:
            return _scale(c, 0.5)
        rec = other.blend.get(_OPPOSITE[side])
        return _add(c, rec["mid"]) if rec else c

    def corner(side, end: str, mid: RGB) -> RGB:
        beside = _neighbour(lat, lon, end)
        info = facts_of(beside)
        if info.built:
            rec = info.blend.get(side)
            if not rec:
                return (0.0, 0.0, 0.0)
            # its end facing this tile: its finish end when it lies at our start
            return tuple(rec["end" if end == _ALONG[side][0] else "start"])
        theirs = midpoint(beside, side)
        if theirs is None:
            return (0.0, 0.0, 0.0)
        return _scale(_add(mid, theirs), 0.5)

    out = Blend(lat, lon)
    for side in SIDES:
        mid = midpoint((lat, lon), side)
        if mid is None:
            continue
        start_end, finish_end = _ALONG[side]
        out.terms[side] = (corner(side, start_end, mid), mid,
                           corner(side, finish_end, mid))
        out.toward[side] = facts_of(_neighbour(lat, lon, side)).provider
    return out


def add_field(tile, base: Optional[numpy.ndarray], til_x: int, til_y: int,
              zoomlevel: int) -> Optional[numpy.ndarray]:
    """``base`` (a colour-harmonization field, or None) plus the tile's
    provider blend (``tile.provider_blend``, a :class:`Blend`) over one
    texture: the hook ``O4_Imagery_Utils.convert_texture`` calls."""
    blend = getattr(tile, "provider_blend", None)
    if blend is None:
        return base
    extra = blend.field(til_x, til_y, zoomlevel)
    if extra is None:
        return base
    if base is None:
        return extra
    return (numpy.asarray(base, dtype=numpy.float32) + extra).astype(numpy.float32)
