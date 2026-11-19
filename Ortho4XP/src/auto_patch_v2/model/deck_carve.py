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

__all__ = ["CarvePath", "DeckCarve", "CARVE_REF"]

#: the ref prefix of every cell a deck's cut mints (``planar/deck_carve``)
CARVE_REF = "deck_carve"

XY = tuple[float, float]


@_dc.dataclass(frozen=True)
class CarvePath:
    """One line the cut runs along: a mapped road or rail (its OSM way,
    chained on past the deck along its own path) or, with none mapped, the
    cut's own axis across the deck."""

    #: the OSM way id, or ``""`` for the cut's own axis
    way: str
    #: ``road``, ``rail`` or ``axis``
    kind: str
    #: the floor's half width: the carriageway's half plus the shoulder (m)
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
