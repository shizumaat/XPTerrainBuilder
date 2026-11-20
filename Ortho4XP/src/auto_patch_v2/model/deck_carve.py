"""THE CUT A GENERATED DECK OWNS, AS A RECORD (owner 2026-11-19T23:07Z:
"When we insert a bridge, we know the size and shape of the cut needed to
provide the clearance under it, whether there's OSM or not ... we have to
add the cut to the patch"; 23:09Z: "the cut needs to grade smoothly away
from the bridge back to the natural terrain"; RULINGS 2026-11-19s (2)-(4)).

``planar/deck_carve`` derives one :class:`DeckCarve` per generated deck on
the full map (``DeckBridge.carve``) and mints its cells; stage 2
(``constraints/deck_carve``) levels them from the deck's solved top.  The
model holds no geometry library: paths are plain coordinate tuples.
Nothing here names an airport.
"""
from __future__ import annotations

import dataclasses as _dc

__all__ = ["CarvePath", "DeckCarve", "CARVE_REF", "floor_band"]

#: the ref prefix of every cell a deck's cut mints (``planar/deck_carve``)
CARVE_REF = "deck_carve"

XY = tuple[float, float]


@_dc.dataclass(frozen=True)
class CarvePath:
    """The line a deck's ONE cut runs along: its most senior covered road or
    rail (its OSM way, chained on past the deck along its own path) or, with
    none mapped, the cut's own axis; the cut spans the deck between its end
    lines (``span``), wherever the line runs across it."""

    #: the OSM way id, or ``""`` for the cut's own axis
    way: str
    #: ``road``, ``rail`` or ``axis``
    kind: str
    #: the least half width of the floor: every road under the deck with its
    #: shoulders (m)
    half_m: float
    #: the clearance the road needs under the deck's underside (m)
    clearance_m: float
    #: the grade cap its ramps climb at (road law; rail 1.25 %)
    cap: float
    #: the vertical curve's grade change per metre
    rate: float
    #: the path (frame metres), from its far end before the deck to its far
    #: end past it
    coords: tuple[XY, ...]
    #: ``(s0, s1, deck id)``: the stretch of the path under each generated
    #: deck it passes (its ring grown by the bank's run-on)
    stretches: tuple[tuple[float, float, str], ...]
    #: ``(s, z)``: the surveyed ground (lidar) along the path
    terrain: tuple[tuple[float, float], ...]
    #: ``(lo, hi)``: the deck's span across the path between its end lines,
    #: as signed offsets (left positive): the trench is the deck's full width
    #: less each abutment's embankment (``constraints/deck_carve``)
    span: tuple[float, float] = ()
    #: ``(lo, hi)``: what the floor must at least carry -- every road under
    #: the deck with its shoulders, as signed offsets
    need: tuple[float, float] = ()


@_dc.dataclass(frozen=True)
class DeckCarve:
    """A generated deck's cut (module doc)."""

    #: what put the deck there: ``OSM road <id> highway=...``, ``OSM rail
    #: <id>``, ``hidden pack frame``, ``OSM bridge tag``, ``lidar trench``
    evidence: tuple[str, ...]
    #: which way its ramps run: ``along OSM road <id>`` / ``along the cut's
    #: own axis``
    direction: str
    paths: tuple[CarvePath, ...]


def floor_band(p: CarvePath, depth: "float | None", law) -> tuple[float, float]:
    """``(lo, hi)``: the cut's floor across its path (signed offsets) -- the
    deck's full span between its end lines less each abutment's embankment
    (``depth`` from the end lines' top to the floor at the deck bank's
    slope, ``model/deck_bank``), never narrower than its roads need
    (``CarvePath.need``: there the bank is a wall, RULINGS 2026-11-19s (4)
    (a)).  A path with no span read keeps ``half_m`` either side."""
    from .deck_bank import deck_bank_slope
    need = tuple(getattr(p, "need", ()) or ()) or (-float(p.half_m), float(p.half_m))
    span = tuple(getattr(p, "span", ()) or ())
    if len(span) != 2 or depth is None:
        return float(need[0]), float(need[1])
    run = max(0.0, float(depth)) / deck_bank_slope(law)
    return min(float(need[0]), span[0] + run), max(float(need[1]), span[1] - run)

