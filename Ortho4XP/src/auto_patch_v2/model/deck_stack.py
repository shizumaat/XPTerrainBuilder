"""THE DECK STACK (#1971; spec ``docs/specs/interchange-levels-20261113.md``
§3.1): several pack objects standing over one another on ONE floor — a
trench whose walls rise from that floor (level 0) and the hard decks that
span it (levels 1..N, in the order of their authored height).  Every member
stands on the level-0 floor, so the stack has ONE zero, read off the decks'
end lines as a bridge's is (RULINGS 2026-10-30a).

Derived once at the pack stage (``airport/deck_stack``), read by the planar
floor (``airport/deck_stack.stack_floors``), the rows
(``constraints/deck_stack``) and the sidecar (``pipeline/publication``).
Data only: no shapely, no numpy (``tests/auto_patch_v2/test_model.py``).
Coordinates are airport-frame metres; ``y`` / ``top`` are authored heights
over a placement's zero.
"""
from __future__ import annotations

import dataclasses as _dc

from .frame import XY

__all__ = ["StackDeck", "DeckStack", "XY3", "STACK_PREFIX", "FLOOR_FACE_PREFIX",
           "FLOOR_WALL_PREFIX", "floor_level"]

XY3 = tuple[float, float, float]

#: ``DeckStack.id`` is this + the walls' placement id
STACK_PREFIX = "stack:"
#: the planar refs of a stack's floor face and its void band: the object
#: floor's own (``airport/object_floor.FLOOR_REF`` / ``FLOOR_WALL_REF``, held
#: equal by ``tests/auto_patch_v2/test_deck_stack1971.py``) + the stack id —
#: the stack floor IS an object floor
FLOOR_FACE_PREFIX = "object_floor:"
FLOOR_WALL_PREFIX = "object_floor_wall:"


def floor_level(zero_z: float, feet_y: float) -> float:
    """THE FLOOR RULE, in one place (§3.7 (1); owner RULINGS 2026-11-13g,
    question O1 answered (a)): the decks stand at the real road level and
    the level-0 floor at the walls' feet at the stack's zero — the depth
    ladder's first rung, an object that states its own bottom."""
    return float(zero_z) + float(feet_y)


@_dc.dataclass(frozen=True)
class StackDeck:
    """One hard-deck PIECE of a stack member (§3.4): its plan ``ring``, its
    ``level`` (1..N), the way ids of the route it CARRIES and of those
    crossing UNDER it, its two END LINES' stations (``()`` if none) and the
    plate's own height ON each (``top_a`` / ``top_b``), and the plate's
    triangles ``(frame x, frame y, authored y)``."""

    object_id: str
    resource: str
    piece: int
    ring: tuple[XY, ...]
    level: int
    carried: tuple[int, ...]
    under: tuple[int, ...]
    end_a: tuple[XY, ...]
    end_b: tuple[XY, ...]
    top_a: float
    top_b: float
    plate: tuple[tuple[XY3, XY3, XY3], ...] = _dc.field(repr=False, default=())


@_dc.dataclass(frozen=True)
class DeckStack:
    """One stack (§3.1).  ``floor`` is the corridor between the walls as a
    ring of station points ``[left_0 .. left_n, right_n .. right_0]`` (the
    ``i``-th left and right points stand on one station across the
    under-way); ``rim`` the wall lines (where a wall face stands);
    ``runouts`` each run-out strip as ``(ring, z at the walls, z at the
    lip)``, its ring ordered as ``floor``'s with station 0 at the walls and
    the level linear along the strip.  ``end_zeros`` is
    ``(deck object id, piece, "a"|"b", ground, top)`` per end line read
    into the zero."""

    id: str
    walls_id: str
    walls_resource: str
    members: tuple[tuple[str, str], ...]
    zero_z: float
    zero_spread_m: float
    end_zeros: tuple[tuple[str, int, str, float, float], ...]
    feet_y: float
    crest_y: float
    floor: tuple[XY, ...]
    rim: tuple[tuple[XY, ...], ...]
    runouts: tuple[tuple[tuple[XY, ...], float, float], ...]
    under_ways: tuple[int, ...]
    decks: tuple[StackDeck, ...]
    notes: tuple[str, ...] = ()

    @property
    def floor_z(self) -> float:
        """The floor's level (:func:`floor_level`)."""
        return floor_level(self.zero_z, self.feet_y)

    @property
    def levels(self) -> int:
        """How many deck levels stand over the floor."""
        return max((d.level for d in self.decks), default=0)

    @property
    def floor_ref(self) -> str:
        """The planar ref of the stack floor's cut face (and its object
        floor's id)."""
        return FLOOR_FACE_PREFIX + self.id

    @property
    def wall_ref(self) -> str:
        """The planar ref of the void band around the floor."""
        return FLOOR_WALL_PREFIX + self.id

    def sidecar(self, to_ll) -> dict:
        """The ``"stack"`` sub-record of the floor's sidecar row
        (``pipeline/publication.object_floors``; ``tools/drawn_check``
        reads it): the zero, the walls' feet and crest, the floor's
        centreline and wall lines, and per deck its ring, level, carried
        ways, plate floor and end lines (stations and the plate's top on
        each), all as lat/lon."""
        def ll(pts) -> list:
            return [[round(la, 8), round(lo, 8)] for la, lo in (to_ll(x, y) for x, y in pts)]
        n = len(self.floor) // 2
        mid = [((a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0)
               for a, b in zip(self.floor[:n], reversed(self.floor[n:]), strict=True)]
        return {"id": self.id, "zero_m": round(self.zero_z, 3),
                "spread_m": round(self.zero_spread_m, 3), "levels": self.levels,
                "feet_y": round(self.feet_y, 3), "crest_y": round(self.crest_y, 3),
                "members": [pid for pid, _r in self.members],
                "floor_line": ll(mid), "rim": [ll(r) for r in self.rim],
                "decks": [{"object": d.object_id, "resource": d.resource, "piece": d.piece,
                           "level": d.level, "carried": list(d.carried), "ring": ll(d.ring),
                           "plate_min_y": round(min((p[2] for t in d.plate for p in t),
                                                    default=min(d.top_a, d.top_b)), 3),
                           "ends": [{"end": e, "top": round(top, 3), "stations": ll(line)}
                                    for e, line, top in (("a", d.end_a, d.top_a),
                                                         ("b", d.end_b, d.top_b)) if line]}
                          for d in self.decks]}
