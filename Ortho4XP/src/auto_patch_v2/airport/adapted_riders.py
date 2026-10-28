"""FOOTLESS MEMBERS RESTING ON A TERRAIN-ADAPTED MEMBER STAY WITH IT (#1599).

A member the terrain adapted to (a basin, a door ramp, a wall corridor —
``Screen.excluded``, RULINGS 2026-09-09q (1)) is never re-seated: it keeps
its authored row.  A member with NO ground foot that touches it — the
roofs an author drew as their own object over his walls (KATL
``techo1.obj`` on ``pared1.obj``, 89 contacts, 0 feet) — has no ground of
its own: re-seated, it leaves the walls it rests on (1.0.441: every roof
3.45 m into its hall, the owner's "coming apart, not seated as a group").
Owner 22o: "connected objects stay as one group"; so such a member is
excluded with the member it rests on and keeps its authored row too.

Only a member whose every part is footless follows; a member with one
foot on the ground stands on its own ground as before (09q (1): never the
anchor family)."""
from __future__ import annotations

import typing as _t

__all__ = ["riders_of_adapted"]


def riders_of_adapted(units: _t.Sequence[_t.Any],
                      member_object: _t.Mapping[tuple[int, int], tuple[str, str]],
                      contacts: _t.Iterable[tuple[int, int]],
                      excluded: _t.AbstractSet[str]) -> frozenset[str]:
    """The object ids of the FOOTLESS members whose parts touch (a
    ``contacts`` pair) a part of a member in ``excluded``."""
    held: set[int] = set()
    footless: dict[int, str] = {}
    for ui, u in enumerate(units):
        for mi, m in enumerate(u.members):
            oid = member_object.get((ui, mi), (m.id, m.resource))[0]
            if oid in excluded:
                held.update(p.pid for p in m.parts)
            elif m.parts and not any(p.feet for p in m.parts):
                footless.update((p.pid, oid) for p in m.parts)
    if not held or not footless:
        return frozenset()
    out = set()
    for a, b in contacts:
        if a in held and b in footless:
            out.add(footless[b])
        elif b in held and a in footless:
            out.add(footless[a])
    return frozenset(out)
