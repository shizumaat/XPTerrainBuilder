"""The colour blend across an edge where the photo provider changes
(#2018, spec ``docs/specs/auto-imagery-provider-spec-20261113.md`` §3).

A drape tile beside a tile drawn by another provider has its colour
pulled toward that provider, as ONE continuous field of position over
the tile -- never a per-texture constant (the per-texture shifts minted
the OTHH seams of 2026-09-18):

* each side s whose neighbour's provider differs carries an AFFINE term
  ``x -> k*x + b`` per channel, from the edge's statistics
  (``O4_Imagery_Provider_Cast.CastBook``: each provider's mean and
  standard deviation near the line, square by square along the edge).
  At each knot it maps the own band's mean and spread onto a target:
  halfway to the neighbour's (the mean of the two means, the geometric
  mean of the two spreads) when the neighbour will blend too, onto the
  neighbour's as its record left it when it has blended, onto the
  neighbour's own when it never will (a full, kept or adopted tile).  The
  gain ``1 + k`` matches the contrast an offset cannot (#2018 follow-up);
  a cast given as a bare RGB offset is a term with ``k = 0``;
* along the edge the value is piecewise linear through the knots (one
  per straddling texture square, at its centre), and at each end the
  corner value shared with the tile beside it along the edge (its
  record's, else the mean of the two end knots when it blends on the
  same side, else 0);
* the value falls linearly to 0 at the opposite edge.

Every term vanishes on an edge whose far side does not apply the same
term, so the field never adds a step where there was none; across the
provider edge the two sides meet halfway.  :meth:`Blend.fields`
evaluates it at a texture's pixel centres (``O4_Color_Harmonization``'s
field shape, applied by ``apply_color_field`` with its ``gain``), so two
textures agree on their shared edge.  :func:`from_record` rebuilds a
drape's blend from its World pack record, so a finer tier of it landed
later is shifted as its first tier was.

Pure: numpy only; the facts about neighbours and the casts come in as
callables.  No tile or airport is named here.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Callable, Dict, Optional, Sequence, Tuple

import numpy

__all__ = ["SIDES", "TileFacts", "Blend", "plan", "add_field", "gain_field",
           "from_record"]

#: Side -> (dlat, dlon) of the neighbour across it.
SIDES = {"N": (1, 0), "S": (-1, 0), "E": (0, 1), "W": (0, -1)}
#: Side -> the two along-edge directions (start end, finish end) and
#: whether the along-edge parameter is the longitude fraction.
_ALONG = {"N": ("W", "E"), "S": ("W", "E"), "E": ("S", "N"), "W": ("S", "N")}
_OPPOSITE = {"N": "S", "S": "N", "E": "W", "W": "E"}
#: The field's samples per texture edge (``O4_Color_Harmonization.FIELD_SIZE``).
FIELD_SIZE = 256
RGB = Tuple[float, float, float]
#: A side's value at a point: ``(b_r, b_g, b_b, k_r, k_g, k_b)``, the
#: term ``k*x + b`` per channel.
Term = Tuple[float, ...]
_ZERO: Term = (0.0,) * 6
_EPS = 1e-6


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


def _add(a, b) -> Term:
    return tuple(float(x) + float(y) for x, y in zip(a, b, strict=True))


def _scale(a, k: float) -> Term:
    return tuple(float(x) * k for x in a)


def _rec_knots(rec: dict) -> Tuple["Knot", ...]:
    """A record side's knots (:meth:`Blend.record`); a first-round record
    (``start``/``mid``/``end`` offsets, no gains) reads as three knots
    with ``k = 0``."""
    if rec.get("knots"):
        return tuple((float(row[0]), tuple(float(v) for v in row[1:4])
                      + tuple(float(g) - 1.0 for g in row[4:7]))
                     for row in rec["knots"])
    return tuple((t, tuple(float(v) for v in rec[which]) + (0.0,) * 3)
                 for t, which in ((0.0, "start"), (0.5, "mid"), (1.0, "end")))


def _stats(value, own_is_b: bool):
    """``(mean_own, mean_other, std_own, std_other)`` of a cast: an
    ``EdgeStats``, or a bare ``mean(b - a)`` RGB offset."""
    import O4_Imagery_Provider_Cast as CAST
    if isinstance(value, CAST.EdgeStats):
        if own_is_b:
            return value.mean_b, value.mean_a, value.std_b, value.std_a
        return value.mean_a, value.mean_b, value.std_a, value.std_b
    toward = _scale(value, -1.0 if own_is_b else 1.0)
    return (0.0,) * 3, toward, (1.0,) * 3, (1.0,) * 3


def _term(mean_own, std_own, mean_to, std_to, weight: float) -> Term:
    """The term taking the own band (``mean_own``, ``std_own``) ``weight``
    of the way to (``mean_to``, ``std_to``): the mean linearly (the shift
    clipped to ``MAX_CAST``), the spread geometrically (the ratio clipped
    to ``MAX_GAIN``)."""
    import O4_Imagery_Provider_Cast as CAST
    offsets, slopes = [], []
    for m, s, mt, st in zip(mean_own, std_own, mean_to, std_to, strict=True):
        shift = float(numpy.clip(mt - m, -CAST.MAX_CAST, CAST.MAX_CAST))
        ratio = st / s if s > _EPS and st > _EPS else 1.0
        gain = float(numpy.clip(ratio, 1.0 / CAST.MAX_GAIN, CAST.MAX_GAIN)) ** weight
        offsets.append(m + weight * shift - gain * m)
        slopes.append(gain - 1.0)
    return tuple(offsets) + tuple(slopes)


Knot = Tuple[float, Term]


def _profile_at(knots: Sequence[Knot], t) -> numpy.ndarray:
    """A piecewise-linear profile (``knots``: ``(t, Term)`` sorted by
    ``t``) at ``t`` (any shape): ``t.shape + (6,)``."""
    ts = numpy.array([k[0] for k in knots], dtype=numpy.float64)
    values = numpy.array([k[1] for k in knots], dtype=numpy.float64)
    t = numpy.asarray(t, dtype=numpy.float64)
    return numpy.stack([numpy.interp(t, ts, values[:, ch])
                        for ch in range(values.shape[1])], axis=-1)


def _value_at(knots: Sequence[Knot], t: float) -> Term:
    return tuple(float(v) for v in _profile_at(knots, numpy.array(t)))


@dataclass
class Blend:
    """One tile's blend: ``terms[side]`` the ``(t, Term)`` knots along
    the edge (``t`` 0 at its west or south end, 1 at the other; the first
    and last are the corners)."""

    lat: int
    lon: int
    terms: Dict[str, Tuple[Knot, ...]] = field(default_factory=dict)
    toward: Dict[str, str] = field(default_factory=dict)

    def record(self) -> dict:
        """The sides as the World pack record keeps them:
        ``knots: [[t, b_r, b_g, b_b, gain_r, gain_g, gain_b], ...]``."""
        out = {}
        for side, knots in sorted(self.terms.items()):
            out[side] = {"toward": self.toward.get(side, ""), "knots": [
                [round(t, 4)] + [round(v, 2) for v in value[:3]]
                + [round(1.0 + v, 4) for v in value[3:]]
                for t, value in knots]}
        return out

    def at(self, lat, lon) -> numpy.ndarray:
        """The field's :data:`Term` values at points (numpy arrays of any
        shape): ``(..., 6)``, offsets then slopes."""
        fx, fy = numpy.broadcast_arrays(
            numpy.clip(numpy.asarray(lon, dtype=numpy.float64) - self.lon, 0.0, 1.0),
            numpy.clip(numpy.asarray(lat, dtype=numpy.float64) - self.lat, 0.0, 1.0))
        out = numpy.zeros(fx.shape + (6,), dtype=numpy.float64)
        for side, knots in self.terms.items():
            t = fx if side in ("N", "S") else fy
            depth = {"N": fy, "S": 1.0 - fy, "E": fx, "W": 1.0 - fx}[side]
            out += _profile_at(knots, t) * depth[..., None]
        return out

    def fields(self, til_x: int, til_y: int, zoomlevel: int,
               size: int = FIELD_SIZE
               ) -> Optional[Tuple[numpy.ndarray, Optional[numpy.ndarray]]]:
        """``(offset, slope)``: ``(size, size, 3)`` float32 fields over
        texture square (``til_x``, ``til_y``) at ``zoomlevel`` (16 x 16
        map tiles), at its pixel centres -- a pixel ``x`` becomes
        ``x * (1 + slope) + offset``; ``slope`` None when it moves no
        pixel by half a count.  None when the tile has no term or it
        changes nothing."""
        if not self.terms:
            return None
        u = (numpy.arange(size, dtype=numpy.float64) + 0.5) / size * 16.0
        half = 2.0 ** (zoomlevel - 1)
        lon = ((til_x + u) / half - 1.0) * 180.0
        lat = 360.0 / math.pi * numpy.arctan(numpy.exp(
            math.pi * (1.0 - (til_y + u) / half))) - 90.0
        values = self.at(lat[:, None], lon[None, :]).astype(numpy.float32)
        offset, slope = values[..., :3], values[..., 3:]
        if not (numpy.abs(slope) * 255.0 >= 0.5).any():
            slope = None
        if slope is None and not numpy.rint(offset).any():
            return None
        return numpy.ascontiguousarray(offset), (
            None if slope is None else numpy.ascontiguousarray(slope))

    def field(self, til_x: int, til_y: int, zoomlevel: int,
              size: int = FIELD_SIZE) -> Optional[numpy.ndarray]:
        """The offset part of :meth:`fields`."""
        both = self.fields(til_x, til_y, zoomlevel, size)
        return None if both is None else both[0]


def _neighbour(lat: int, lon: int, side: str) -> Tuple[int, int]:
    dlat, dlon = SIDES[side]
    return lat + dlat, lon + dlon


def _cast_knots(measured) -> Sequence[Tuple[float, object]]:
    """A cast as ``[(t, value)]`` along its edge: a list of knots as
    ``O4_Imagery_Provider_Cast.CastBook.cast`` gives it, or one value (an
    ``EdgeStats`` or a bare RGB offset) for the whole edge, at its
    middle."""
    if isinstance(measured, list):
        return measured
    return [(0.5, measured)]


def plan(lat: int, lon: int, provider: str,
         facts: Callable[[int, int], TileFacts],
         cast: Callable[[Tuple[str, int, int], str, str], Optional[object]]
         ) -> Blend:
    """The blend of drape tile (``lat``, ``lon``) drawn by ``provider``.
    ``facts(lat, lon)`` says what draws a neighbour; ``cast(edge, a, b)``
    is the edge's ``[(t, EdgeStats)]`` knots (``a`` the provider south or
    west of it; ``t`` the fraction along the edge), one ``EdgeStats`` or
    a bare ``mean(b - a)`` RGB offset for the whole edge, or None when it
    cannot be measured."""
    me = TileFacts(provider)

    def facts_of(key):
        return me if key == (lat, lon) else facts(*key)

    def profile(key, side) -> Optional[Tuple[Knot, ...]]:
        """The knots tile ``key`` applies (or would) on ``side``, without
        its corners when it is a drape still to be made."""
        own = facts_of(key)
        if own.built:
            rec = own.blend.get(side)
            return _rec_knots(rec) if rec else None
        other = facts_of(_neighbour(*key, side))
        if not own.provider or not other.provider or other.provider == own.provider:
            return None
        south_west = side in ("S", "W")
        a, b = ((other.provider, own.provider) if south_west
                else (own.provider, other.provider))
        measured = cast(edge_key(*key, side), a, b)
        if not measured:
            return None
        theirs = None if other.blends else other.blend.get(_OPPOSITE[side])
        theirs = _rec_knots(theirs) if theirs else None
        knots = []
        for t, value in _cast_knots(measured):
            mean_own, mean_to, std_own, std_to = _stats(value, south_west)
            if other.blends:
                knots.append((float(t), _term(mean_own, std_own, mean_to, std_to, 0.5)))
                continue
            if theirs:              # the neighbour as its blend left it
                there = _value_at(theirs, t)
                mean_to = tuple(m * (1.0 + k) + b for m, b, k in zip(
                    mean_to, there[:3], there[3:], strict=True))
                std_to = tuple(s * (1.0 + k) for s, k in zip(
                    std_to, there[3:], strict=True))
            knots.append((float(t), _term(mean_own, std_own, mean_to, std_to, 1.0)))
        return tuple(sorted(knots)) or None

    def corner(side, end: str, mine: Tuple[Knot, ...]) -> Term:
        """The value at the ``end`` corner of ``side``: shared with the
        tile beside it along the edge."""
        at_start = end == _ALONG[side][0]
        beside = _neighbour(lat, lon, end)
        info = facts_of(beside)
        theirs = profile(beside, side)
        if theirs is None:
            return _ZERO
        # their end facing this tile: their finish when they lie at our start
        facing = _value_at(theirs, 1.0) if at_start else _value_at(theirs, 0.0)
        if info.built:
            return facing
        own = mine[0][1] if at_start else mine[-1][1]
        return _scale(_add(own, facing), 0.5)

    out = Blend(lat, lon)
    for side in SIDES:
        mine = profile((lat, lon), side)
        if mine is None:
            continue
        start_end, finish_end = _ALONG[side]
        inner = tuple(k for k in mine if 0.0 < k[0] < 1.0) or mine
        out.terms[side] = ((0.0, corner(side, start_end, mine)),) + inner + (
            (1.0, corner(side, finish_end, mine)),)
        out.toward[side] = facts_of(_neighbour(lat, lon, side)).provider
    return out


def from_record(lat: int, lon: int, sides: dict) -> Optional[Blend]:
    """The blend a drape was made with, from its World pack record's
    ``blend`` sides (:meth:`Blend.record`); None when it has none."""
    out = Blend(int(lat), int(lon))
    for side, rec in (sides or {}).items():
        if side not in SIDES or not isinstance(rec, dict):
            continue
        try:
            out.terms[side] = _rec_knots(rec)
        except (KeyError, TypeError, ValueError, IndexError):
            continue
        out.toward[side] = str(rec.get("toward") or "")
    return out if out.terms else None


def add_field(tile, base: Optional[numpy.ndarray], til_x: int, til_y: int,
              zoomlevel: int) -> Optional[numpy.ndarray]:
    """``base`` (a colour-harmonization field, or None) plus the tile's
    provider blend's offset (``tile.provider_blend``, a :class:`Blend`)
    over one texture: the hook ``O4_Imagery_Utils.convert_texture``
    calls (with :func:`gain_field`)."""
    blend = getattr(tile, "provider_blend", None)
    if blend is None:
        return base
    both = blend.fields(til_x, til_y, zoomlevel)
    if both is None:
        return base
    if base is None:
        return both[0]
    return (numpy.asarray(base, dtype=numpy.float32) + both[0]).astype(numpy.float32)


def gain_field(tile, til_x: int, til_y: int, zoomlevel: int
               ) -> Optional[numpy.ndarray]:
    """The slope part of the tile's provider blend over one texture
    (``apply_color_field``'s ``gain``); None when it has none there."""
    blend = getattr(tile, "provider_blend", None)
    both = None if blend is None else blend.fields(til_x, til_y, zoomlevel)
    return None if both is None else both[1]
