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
import typing as _t

from .frame import XY

__all__ = ["FreeEnd", "FreeDeck", "FreeBridge", "FREE_PLATE", "FREE_PREFIX", "published"]

#: the plan member's ``plate_kind`` of a free deck (``pipeline/rebake_inputs``)
FREE_PLATE = "free"
#: ``FreeBridge.id`` is this + its first deck's placement id
FREE_PREFIX = "free:"


@_dc.dataclass(frozen=True)
class FreeEnd:
    """One route end of a free deck: its END LINE (A2: across the deck's
    width, the plate outline outermost along the route's outward tangent) as
    stations, the driven layer's
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


def _end_ground(e: FreeEnd, out_m: float) -> tuple[XY, XY]:
    """A2 END GROUND (S3): the chord the seat reads at end ``e`` — the first
    and last stations of its END LINE, moved ``out_m`` along its outward
    tangent (``[bridge] free_end_ground_out_m``: outside the plate, on the
    ground the deck meets, never the carried road under it)."""
    a, b = e.stations[0], e.stations[-1]
    dx, dy = out_m * e.out[0], out_m * e.out[1]
    return ((a[0] + dx, a[1] + dy), (b[0] + dx, b[1] + dy))


def published(bridges: _t.Sequence[FreeBridge], to_ll, out_m: float) -> dict[str, dict]:
    """Placement id -> the rebake plan's record of each free deck (S2):
    ``bridge`` its bridge's id, ``ends`` its two END GROUND chords
    (:func:`_end_ground`) ``[[lat, lon], [lat, lon]]``, ``tops`` the driven
    layer's top at each, ``land`` whether each meets land."""
    out: dict[str, dict] = {}
    for fb in bridges:
        for d in fb.decks:
            if len(d.ends) != 2:
                continue
            out[d.object_id] = {
                "bridge": fb.id,
                "ends": [[[round(float(v), 9) for v in to_ll(*p)] for p in _end_ground(e, out_m)]
                         for e in d.ends],
                "tops": [round(float(e.top), 4) for e in d.ends],
                "land": [bool(e.land) for e in d.ends]}
    return out
