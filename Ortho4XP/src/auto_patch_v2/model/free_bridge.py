"""THE FREE BRIDGE (#2065; spec ``2065-bridge-class-A1.md`` §A4 S1): a pack
deck the positive witness (``airport/bridge_witness`` W1-W7 + W4b) holds as
a free-standing road bridge, with the decks of its group (one zero, 22o)
and each deck's two ROUTE ends — where its mapped way crosses the plate
outline, never the plate's rectangle.

Read once at the pack stage (``planar/free_bridge.attach_free_bridges``)
onto ``Airport.free_bridges``; the planar stage keeps those no earlier
reader takes (``planar/free_bridge.admitted``) on ``PlanarMap.free_bridges``;
the rebake plan publishes each deck's ends on its member
(``pipeline/rebake_inputs``, ``plate_kind == "free"``) and the object stage
seats the bridge at its land ends (``airport/free_bridge_seat``).

Data only: no shapely, no numpy (``tests/auto_patch_v2/test_model.py``).
Coordinates are airport-frame metres; ``top`` an authored height over the
placement's zero.
"""
from __future__ import annotations

import dataclasses as _dc
import math
import typing as _t

from .frame import XY

__all__ = ["FreeEnd", "FreeDeck", "FreeBridge", "FREE_PLATE", "FREE_PREFIX", "published"]

#: the plan member's ``plate_kind`` of a free deck (``pipeline/rebake_inputs``)
FREE_PLATE = "free"
#: ``FreeBridge.id`` is this + its first deck's placement id
FREE_PREFIX = "free:"


@_dc.dataclass(frozen=True)
class FreeEnd:
    """One route end of a free deck: its END LINE (the plate outline within
    half the deck's width of the crossing) as stations, the driven layer's
    top there, the route's outward tangent, and whether it meets LAND (W7:
    the mapped bridge stops within ``free_end_run_on_max_m``) or is a JOINT
    (the structure carries on, or a stub's end abutting its group)."""

    stations: tuple[XY, ...]
    top: float
    out: XY
    land: bool
    run_on: float = 0.0


@_dc.dataclass(frozen=True)
class FreeDeck:
    """One deck of a free bridge: its placement, plan ring, the mapped ways
    it carries between its ends, its two ends; ``stub_of`` the W-deck a
    routeless stub joined (``""`` for a deck with its own route)."""

    object_id: str
    ring: tuple[XY, ...]
    ways: tuple[int, ...]
    ends: tuple[FreeEnd, ...]
    stub_of: str = ""


@_dc.dataclass(frozen=True)
class FreeBridge:
    """One free bridge: the decks of one group (rings touching within
    ``[placement] footprint_touch_m``) and every member of their frame."""

    id: str
    members: tuple[str, ...]
    decks: tuple[FreeDeck, ...]

    def deck_ids(self) -> tuple[str, ...]:
        return tuple(d.object_id for d in self.decks)


def _chord(stations: _t.Sequence[tuple[float, float]]) -> tuple:
    """An end line's two extreme stations (the chord the seat samples)."""
    if len(stations) < 2:
        return (stations[0], stations[0])
    return max(((a, b) for i, a in enumerate(stations) for b in stations[i + 1:]),
               key=lambda ab: math.hypot(ab[0][0] - ab[1][0], ab[0][1] - ab[1][1]))


def published(bridges: _t.Sequence[FreeBridge], to_ll) -> dict[str, dict]:
    """Placement id -> the rebake plan's record of each free deck (S2):
    ``bridge`` its bridge's id, ``ends`` its two route end lines as chords
    ``[[lat, lon], [lat, lon]]``, ``tops`` the driven layer's top at each,
    ``land`` whether each meets land."""
    out: dict[str, dict] = {}
    for fb in bridges:
        for d in fb.decks:
            if len(d.ends) != 2:
                continue
            out[d.object_id] = {
                "bridge": fb.id,
                "ends": [[[round(float(v), 9) for v in to_ll(*p)] for p in _chord(e.stations)]
                         for e in d.ends],
                "tops": [round(float(e.top), 4) for e in d.ends],
                "land": [bool(e.land) for e in d.ends]}
    return out
