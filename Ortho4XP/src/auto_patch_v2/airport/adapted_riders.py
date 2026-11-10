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
member cannot move and 22o's group moves together.

THE ZERO THE TERRAIN WAS ADAPTED FOR (owner sim read KMCI 1.0.480,
2026-11-10T15:47Z: "the art is at the right spot, and the terminal is too
low").  The planar stage cuts the ground round a terrain-adapted placement
for its RENDERED zero -- the DEM at its anchor plus its lift
(``obj8.PlacedObject.base_z``).  An ``OBJECT_AGL`` row left as authored
(RULINGS 2026-10-14g (1)) stands its ``y = 0`` on OUR mesh at its origin
plus the lift instead, so wherever the design surface redrew the ground at
the origin the member -- and, through #1726, every re-seated piece of its
frame -- moved with that one point: KMCI's terminal frame (origin inside the
pad's lower level, drawn at the lot 2.2 m under the author's ground) stood
308.76 against the 310.73 its wall corridors and sunken road were cut for.
:func:`seat_records` (patch half) writes each such row's zero as an
:data:`~.terrain_shaped.ADAPTED_SEAT` record; the object stage writes the
row as ``OBJECT_MSL`` there (14g (2): only where that changes something)
and :func:`frame_zero` / :func:`member_zeros` read the frame's zero from it.
A footless own-ground piece of a placement authored at the same origin with
another lift (KMCI's ``CEILING-DECO`` at +8.40 in the terminal's +8.50
frame, no carrier) is drawn in that frame and hangs in it at its own lift's
difference."""
from __future__ import annotations

import typing as _t

__all__ = ["riders_of_adapted", "touching_adapted", "ADAPTED_SRC", "ADAPTED_ZERO_REASON",
           "frame_zero",
           "member_zeros", "seat_records", "authored_zeros", "family_seats"]

#: the datum source of a unit seated on a terrain-adapted member's zero
#: (``footprint_unit.plan_unit_datums``); ``open_frame_seat.root_zeros``
#: never moves such a share off it
ADAPTED_SRC = "adapted_frame"
#: the reason ``open_frame_seat.group_zero`` gives a loose piece it hangs on
#: an adapted frame's zero: an absolute zero, so its row keeps no authored
#: lift over it (``authored_landing.body_lift``)
ADAPTED_ZERO_REASON = "one connected group on its terrain-adapted member's zero"


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


#: the ``MslSeat.why`` of a row :func:`family_seats` writes
FAMILY_WHY = "adapted_family"
#: an origin within this of a record's is the same authored origin (a DSF
#: row's coordinates at 1e-9 deg; a re-written row keeps them within mm)
SAME_ORIGIN_M = 0.5
#: lifts within this are one anchor family's
SAME_LIFT_M = 0.01


def seat_records(objects: _t.Iterable[_t.Any], excluded: _t.AbstractSet[str],
                 to_ll: _t.Callable) -> list[dict[str, _t.Any]]:
    """PATCH HALF: one ``RebakePlan.authored_seats`` record per lifted
    (``OBJECT_AGL``, not read ground-seated) placement in ``excluded`` (the
    terrain adapted to it, ``pipeline/rebake_inputs``): ``elevation`` its
    rendered zero (``base_z``: the DEM at its anchor plus its lift -- the
    zero its cut was read for), ``lat`` / ``lon`` its origin, ``agl_m`` its
    lift.  ``to_ll(x, y) -> (lat, lon)`` is the frame's exit."""
    from .terrain_shaped import ADAPTED_SEAT
    out = []
    for o in objects:
        if (o.id not in excluded or getattr(o, "kind", "") != "OBJECT_AGL"
                or getattr(o, "ground_seated", False)):
            continue
        lat, lon = to_ll(float(o.xy[0]), float(o.xy[1]))
        out.append({"id": str(o.id), "resource": str(o.path), "datum": "terrain_adapted",
                    "seat": ADAPTED_SEAT, "elevation": round(float(o.base_z), 3),
                    "lat": float(lat), "lon": float(lon), "agl_m": float(o.agl_m)})
    return out


def authored_zeros(records: _t.Iterable[_t.Mapping[str, _t.Any]]
                   ) -> tuple[tuple[float, float, float, float], ...]:
    """``(lat, lon, lift, zero)`` of every :func:`seat_records` record."""
    from .terrain_shaped import ADAPTED_SEAT
    return tuple((float(r["lat"]), float(r["lon"]), float(r.get("agl_m") or 0.0),
                  float(r["elevation"]))
                 for r in records or () if hasattr(r, "get") and r.get("seat") == ADAPTED_SEAT
                 and r.get("lat") is not None and r.get("elevation") is not None)


def _authored_at(anchor: _t.Sequence[float], authored: _t.Sequence[tuple]
                 ) -> "tuple[float, float] | None":
    """``(lift, zero)`` of the :func:`authored_zeros` record at ``anchor``'s
    origin (the lowest lift's where several frames share it)."""
    import math
    la, lo = float(anchor[0]), float(anchor[1])
    ml = 111_320.0
    mo = ml * math.cos(math.radians(la))
    hit = [(lift, z) for a, b, lift, z in authored
           if math.hypot((a - la) * ml, (b - lo) * mo) <= SAME_ORIGIN_M]
    return min(hit) if hit else None


def frame_zero(surface: _t.Callable, anchor: _t.Sequence[float],
               lift: float, authored: _t.Sequence[tuple] = ()) -> "float | None":
    """The zero an adapted member's authored row stands its ``y = 0`` at:
    the zero its terrain was adapted for where a :func:`seat_records`
    record of this origin and lift says it (the row is written there), else
    the surface at the frame's origin plus the row's lift (X-Plane drapes
    an unmoved row there); ``None`` where the surface reads nothing."""
    for a, b, rl, z in authored:
        if (abs(rl - float(lift or 0.0)) <= SAME_LIFT_M
                and _authored_at(anchor, ((a, b, rl, z),)) is not None):
            return z
    z = surface(float(anchor[0]), float(anchor[1]))
    return None if z is None else float(z) + float(lift or 0.0)


def member_zeros(plan: _t.Any, surface: _t.Callable) -> dict[str, float]:
    """``member id -> frame_zero`` for every plan member with a part in
    ``plan.adapted_frame_pids``: its footless own-ground pieces hang in the
    adapted member's frame, never on the ground under them
    (``open_frame_seat.group_zero``).  A member of a frame authored at the
    origin of an adapted record with another lift hangs in that record's
    frame: its zero plus the lifts' difference (``group_zero`` moves only
    its footless own-ground pieces there)."""
    touch = frozenset(getattr(plan, "adapted_frame_pids", ()) or ())
    authored = authored_zeros(getattr(plan, "authored_seats", ()) or ())
    out: dict[str, float] = {}
    if not touch and not authored:
        return out
    for u in plan.units:
        z: "float | None" = None
        lift = float(getattr(u, "agl_m", 0.0) or 0.0)
        for m in u.members:
            if any(p.pid in touch for p in m.parts):
                if z is None:
                    z = frame_zero(surface, u.anchor, lift, authored)
                if z is not None:
                    out[m.id] = z
        at = _authored_at(u.anchor, authored) if authored else None
        if at is None:
            continue
        for m in u.members:
            if m.id not in out:
                out[m.id] = at[1] + lift - at[0]
    return out


def family_seats(dump: _t.Any, authored: _t.Sequence[tuple], taken: _t.AbstractSet[int],
                 surface: _t.Callable, tol_m: float = 0.05) -> tuple:
    """OBJECT STAGE: the ``MslSeat`` of every lifted row of an adapted
    record's ANCHOR FAMILY (its origin, its lift) that no other rule wrote
    (``taken``): the frame those rows were drawn in stands at the record's
    zero, so they are written there too -- where their drape at the origin
    plus the lift is more than ``tol_m`` off it (14g (2))."""
    from ..model.placement import MslSeat
    if not authored:
        return ()
    out = []
    for i, row in enumerate(getattr(dump, "placements", ()) or ()):
        if i in taken or getattr(row, "kind", "OBJECT") != "OBJECT_AGL":
            continue
        lift = float(getattr(row, "elevation", 0.0) or 0.0)
        anchor = (float(row.lat), float(row.lon))
        z = frame_zero(lambda _la, _lo: None, anchor, lift, authored)
        if z is None:
            continue
        g = surface(anchor[0], anchor[1])
        if g is not None and abs(float(g) + lift - z) <= tol_m:
            continue
        out.append(MslSeat(i, str(row.def_path), anchor[1], anchor[0],
                           float(getattr(row, "heading_deg", 0.0)), z, FAMILY_WHY))
    return tuple(out)
