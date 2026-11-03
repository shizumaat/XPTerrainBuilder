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
anchor family).

THE RE-SEATED PARTS THAT TOUCH IT (issue #1726, owner sim read KBWI
2026-11-03: the interior and skylights stood 0.41 m over the shell).  A
re-seated part of the SAME FRAME (one anchor family: origin and lift) that
ε-touches an adapted member or one of its riders is named by
:func:`touching_adapted`; its connected unit then takes the adapted
member's zero (``footprint_unit.plan_unit_datums``), because the adapted
member cannot move and 22o's group moves together."""
from __future__ import annotations

import typing as _t

__all__ = ["riders_of_adapted", "touching_adapted", "ADAPTED_SRC", "frame_zero",
           "member_zeros"]

#: the datum source of a unit seated on a terrain-adapted member's zero
#: (``footprint_unit.plan_unit_datums``); ``open_frame_seat.root_zeros``
#: never moves such a share off it
ADAPTED_SRC = "adapted_frame"


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


def touching_adapted(units: _t.Sequence[_t.Any],
                     member_object: _t.Mapping[tuple[int, int], tuple[str, str]],
                     contacts: _t.Iterable[tuple[int, int]],
                     held: _t.AbstractSet[str]) -> frozenset[int]:
    """The part ids of members NOT in ``held`` (the adapted members and
    their riders) that ε-touch (a ``contacts`` pair) a part of a ``held``
    member of the SAME unit — one anchor family, so one authored frame."""
    frame: dict[int, int] = {}
    mine: set[int] = set()
    for ui, u in enumerate(units):
        for mi, m in enumerate(u.members):
            oid = member_object.get((ui, mi), (m.id, m.resource))[0]
            for p in m.parts:
                frame[p.pid] = ui
                if oid in held:
                    mine.add(p.pid)
    out = set()
    for a, b in contacts:
        for x, y in ((a, b), (b, a)):
            if x in mine and y not in mine and y in frame and frame[y] == frame.get(x):
                out.add(y)
    return frozenset(out)


def frame_zero(surface: _t.Callable, anchor: _t.Sequence[float],
               lift: float) -> "float | None":
    """The zero an adapted member's authored row stands its ``y = 0`` at:
    the surface at the frame's origin plus the row's lift (X-Plane drapes
    an unmoved row there); ``None`` where the surface reads nothing."""
    z = surface(float(anchor[0]), float(anchor[1]))
    return None if z is None else float(z) + float(lift or 0.0)


def member_zeros(plan: _t.Any, surface: _t.Callable) -> dict[str, float]:
    """``member id -> frame_zero`` for every plan member with a part in
    ``plan.adapted_frame_pids``: its footless own-ground pieces hang in the
    adapted member's frame, never on the ground under them
    (``open_frame_seat.group_zero``)."""
    touch = frozenset(getattr(plan, "adapted_frame_pids", ()) or ())
    out: dict[str, float] = {}
    if not touch:
        return out
    for u in plan.units:
        z: "float | None" = None
        for m in u.members:
            if any(p.pid in touch for p in m.parts):
                if z is None:
                    z = frame_zero(surface, u.anchor, getattr(u, "agl_m", 0.0))
                if z is not None:
                    out[m.id] = z
    return out
