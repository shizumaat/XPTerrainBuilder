"""CLASS A: AN AIRSIDE HARD DECK SITS FLUSH WITH THE SOLVED AIRSIDE AT ITS
END LINES (owner RULINGS 2026-10-22n; #1214 round 3, R3).

A taxiway or runway carried over a road on a pack hard deck (LFPG's
``H*.obj``): its deck top — the max y of the ``ATTR_hard_deck`` slab at
each end (:func:`end_tops`; a deck authored on a grade rises with it) —
meets the solved airside surface where the taxiway drives onto it, at the
deck's two END LINES (the median of each end's airside stations; one rigid
zero, the mean of the two ends' zeros), and every body of its frame moves with it when the frame IS
the bridge (every other member stands inside the deck's footprint, §16e (3)
``bridge_of``).  The under-span mesh stays as it is (#1138, held).

Round 2 read the ring's median (``deck_datum_z``) — the whole ring, the road
under the deck included — and missed the end lines by up to 1.2 m.  The end
lines are the ring's extreme cross-sections; a deck wider than its span has
its principal axis along the road it crosses, so both axes are read and the
pair whose two lines stand on AIRSIDE faces (``law.tables.role_side``) is
the one (``rebake_plan.ring_ends(cross=...)``).  The ring median stands
only where neither axis has two airside end lines.

THE WITNESS IS THE SOLVE, never a name: the deck's ring stands on an
emitted ``bridge_deck`` face (``planar/structure_deck``), or the design
surface under its ring is airside and the plan carries the solved value
(``Member.deck_datum_z``) — and (owner RULINGS 2026-10-27c, #1471) the
airport's own taxiway or apron pavement runs ACROSS the deck, not just
touching it at one end (:func:`pavement_runs_across`).  Moved out of ``placement_plan`` (round 2's
``_airside_*``) with the reading R3 changes.
"""
from __future__ import annotations

import dataclasses as _dc
import math
import os
import typing as _t

from . import anchor_rule as _ar
from .bridge_approach import _median

__all__ = ["deck_owns_its_datum", "airside_zero", "airside_frame",
           "airside_deck", "airside_role", "airside_end_ground", "slab_points",
           "end_tops", "pavement_runs_across", "facing_contacts", "refused_bridge"]


def deck_owns_its_datum(m: _t.Any) -> bool:
    """A FLAG deck (``ATTR_hard_deck``) or one over an emitted deck face
    (``deck_datum_z``): its seat is §16e's / §49's, never a unit's."""
    return (str(getattr(m, "deck_kind", "") or "") == "flag"
            or getattr(m, "deck_datum_z", None) is not None)


_SIDE: dict[str, bool] = {}


def airside_role(role: "str | None") -> bool:
    """Is this face role AIRSIDE by the law's own register
    (``law.tables.role_side``)?  Memoised per role."""
    if not role:
        return False
    if role not in _SIDE:
        from ..law import Law
        from ..law import tables as _T
        try:
            _SIDE[role] = _T.role_side(Law.load(), role) == "airside"
        except Exception:
            _SIDE[role] = False
    return _SIDE[role]


def _perimeter(ring: _t.Sequence[tuple[float, float]], step_m: float
               ) -> list[tuple[float, float, float, float]]:
    """``(lat, lon, out_lat, out_lon)`` every ``step_m`` along the ring:
    the station ON the ring edge and one ``step_m`` OUTSIDE it (the edge's
    outward normal, read off the ring's own winding)."""
    from .rebake_plan import _mpd
    lat0 = sum(q[0] for q in ring) / len(ring)
    ml, mo = _mpd(lat0)
    pts = [(float(q[0]), float(q[1])) for q in ring]
    if pts[0] == pts[-1]:
        pts = pts[:-1]
    area = sum((pts[i][1] * mo) * (pts[(i + 1) % len(pts)][0] * ml)
               - (pts[(i + 1) % len(pts)][1] * mo) * (pts[i][0] * ml)
               for i in range(len(pts)))
    sign = 1.0 if area > 0.0 else -1.0          # counter-clockwise in (x=lon, y=lat)
    out = []
    for i, a in enumerate(pts):
        b = pts[(i + 1) % len(pts)]
        dx, dy = (b[1] - a[1]) * mo, (b[0] - a[0]) * ml
        ln = math.hypot(dx, dy)
        if ln <= 1e-6:
            continue
        nx, ny = sign * dy / ln, -sign * dx / ln     # outward normal (x, y)
        k = max(1, int(math.ceil(ln / step_m)))
        for j in range(k):
            t = (j + 0.5) / k
            la, lo = a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t
            out.append((la, lo, la + ny * step_m / ml, lo + nx * step_m / mo))
    return out


def _two_ends(pts: _t.Sequence[tuple[float, float, float]], lat0: float
              ) -> "tuple[list, list] | None":
    """Split ``(lat, lon, z)`` stations into the deck's TWO ends: a 2-means
    split seeded by the two stations furthest apart."""
    from .rebake_plan import _mpd
    if len(pts) < 4:
        return None
    ml, mo = _mpd(lat0)
    xy = [(q[1] * mo, q[0] * ml) for q in pts]
    i0, i1, best = 0, 0, -1.0
    for i in range(len(xy)):
        for j in range(i + 1, len(xy)):
            d = (xy[i][0] - xy[j][0]) ** 2 + (xy[i][1] - xy[j][1]) ** 2
            if d > best:
                i0, i1, best = i, j, d
    c = [xy[i0], xy[i1]]
    lab = [0] * len(xy)
    for _it in range(8):
        lab = [0 if (p[0] - c[0][0]) ** 2 + (p[1] - c[0][1]) ** 2
               <= (p[0] - c[1][0]) ** 2 + (p[1] - c[1][1]) ** 2 else 1 for p in xy]
        for k in (0, 1):
            g = [p for p, q in zip(xy, lab, strict=True) if q == k]
            if g:
                c[k] = (sum(p[0] for p in g) / len(g), sum(p[1] for p in g) / len(g))
    e0 = [q for q, k in zip(pts, lab, strict=True) if k == 0]
    e1 = [q for q, k in zip(pts, lab, strict=True) if k == 1]
    if len(e0) < 2 or len(e1) < 2:
        return None
    return e0, e1


def airside_end_ground(ring: _t.Sequence[tuple[float, float]],
                       surface: _ar.Surface, step_m: float,
                       carried: _t.Callable[["str | None"], bool] | None = None,
                       outside: bool = False
                       ) -> "tuple[tuple[float, float], tuple[list, list]] | None":
    """``((ground at end 1, at end 2), (end 1's stations, end 2's))``: THE
    END LINES ARE WHERE THE AIRSIDE DRIVES ONTO THE DECK — the stations of
    the ring's edge whose ground one step OUTSIDE it is an airside face
    (``surface.roles``; the road under the deck and the sheet's edge are
    not), split into the deck's two ends; the median of each end's ground
    ON the edge.  A skewed deck's extreme cross-sections are corners, and a
    deck wider than its span has its principal axis along the road it
    crosses, so the ends are read off the solve, not the ring's axis.
    ``None`` where two such ends are not found (no ``surface.roles``, an
    off-sheet deck).  ``carried`` is the role test of the surface the
    deck carries — :func:`airside_role` by default; a pack deck over the
    pack's own cut also carries a road (``cut_deck_seat``).  ``outside``
    reads the ground at the station one step OUTSIDE the edge, on the
    surface carried, instead of on the edge — a deck over a cut has the
    trench under its edge (``cut_deck_seat``)."""
    carried = carried or airside_role
    roles = getattr(surface, "roles", None)
    if roles is None or step_m <= 0.0 or len(ring) < 3:
        return None
    per = _perimeter(ring, step_m)
    if not per:
        return None
    got = roles.roles_many([q[2] for q in per], [q[3] for q in per])
    kept = []
    for (la, lo, ola, olo), r in zip(per, got, strict=True):
        if not carried(r):
            continue
        z = surface(ola, olo) if outside else surface(la, lo)
        if z is not None:
            kept.append((la, lo, float(z)))
    ends = _two_ends(kept, sum(q[0] for q in ring) / len(ring))
    if ends is None:
        return None
    return (_median([q[2] for q in ends[0]]), _median([q[2] for q in ends[1]])), ends


def _contacts(flags: _t.Sequence[bool]) -> list[list[int]]:
    """The maximal runs of ``True`` along a CLOSED ring of stations (a run
    may wrap past the first station).  A ring all ``True`` has no
    separate runs and gives ``[]``, as one all ``False`` does."""
    n = len(flags)
    if n == 0 or all(flags) or not any(flags):
        return []
    s0 = next(i for i in range(n) if not flags[i])
    runs: list[list[int]] = []
    cur: list[int] = []
    for k in range(1, n + 1):
        i = (s0 + k) % n
        if flags[i]:
            cur.append(i)
        elif cur:
            runs.append(cur)
            cur = []
    if cur:
        runs.append(cur)
    return runs


def pavement_runs_across(ring: _t.Sequence[tuple[float, float]],
                         surface: _ar.Surface, step_m: float) -> bool:
    """:func:`facing_contacts` found a pair (its doc carries the law)."""
    return facing_contacts(ring, surface, step_m) is not None


#: a ``(lat, lon)`` station
LL = tuple[float, float]


def facing_contacts(ring: _t.Sequence[tuple[float, float]],
                    surface: _ar.Surface, step_m: float, every: bool = False
                    ) -> "tuple[list[LL], list[LL]] | list | None":
    """Owner RULINGS 2026-10-27c (Q183, #1471; narrows 10-22n class A): A
    STRUCTURE IS A TAXIWAY BRIDGE ONLY IF THE AIRPORT'S OWN TAXIWAY OR
    APRON PAVEMENT RUNS ACROSS ITS DECK, not just touching it at one end.

    Read on the stations :func:`airside_end_ground` reads — every
    ``step_m`` along the ring's edge, the role one step OUTSIDE it.  A
    PAVEMENT station's role is the airport's own pavement (the rolled-on
    roles, ``airside_group_seat.airside_pavement``: apron, taxiways,
    runway — never the graded strip, a pad or a road).  A CONTACT is a
    maximal run of them along the edge.  The deck's own interior is no
    witness: the pack's deck is the pavement there, and apt.dat and the
    solve leave it a hole.  The pavement runs across when two SEPARATE
    contacts face each other across the deck: their mean outward normals
    oppose, each lies on the inward side of the other, and the midpoint of
    the chord between them stands inside the ring.  One contact (KLAX's
    people-mover rail meets the apron at one end), two on one side, and a
    ring wholly surrounded by pavement (nothing passes under it) are not.
    No number is chosen: the step is the law's, the tests are signs.

    The answer is the first facing pair's two contacts as their ON-EDGE
    stations ``(lat, lon)`` — the deck's END LINES where the taxiway
    drives onto it (``planar/deck_bridge`` seats the deck there) — or
    ``None``; with ``every``, the list of every facing pair in that order
    (``planar/deck_bridge`` picks the one the road under it runs along)."""
    roles = getattr(surface, "roles", None)
    if roles is None or step_m <= 0.0 or len(ring) < 3:
        return [] if every else None
    per = _perimeter(ring, step_m)
    if not per:
        return [] if every else None
    from shapely.geometry import Point, Polygon

    from .airside_group_seat import airside_pavement
    from .rebake_plan import _mpd
    pave = airside_pavement(surface)
    got = roles.roles_many([q[2] for q in per], [q[3] for q in per])
    runs = _contacts([pave(r) for r in got])
    if len(runs) < 2:
        return [] if every else None
    ml, mo = _mpd(sum(float(q[0]) for q in ring) / len(ring))
    xy = [(q[1] * mo, q[0] * ml, (q[3] - q[1]) * mo, (q[2] - q[0]) * ml) for q in per]
    deck = Polygon([(float(q[1]) * mo, float(q[0]) * ml) for q in ring])
    if not deck.is_valid:
        deck = deck.buffer(0)
    ends = []
    for r in runs:
        cx = sum(xy[i][0] for i in r) / len(r)
        cy = sum(xy[i][1] for i in r) / len(r)
        nx = sum(xy[i][2] for i in r)
        ny = sum(xy[i][3] for i in r)
        ends.append((cx, cy, nx, ny))
    pairs = []
    for i, a in enumerate(ends):
        for j in range(i + 1, len(ends)):
            b = ends[j]
            dx, dy = b[0] - a[0], b[1] - a[1]
            if (a[2] * b[2] + a[3] * b[3] < 0.0
                    and dx * a[2] + dy * a[3] < 0.0
                    and -dx * b[2] - dy * b[3] < 0.0
                    and deck.contains(Point(a[0] + 0.5 * dx, a[1] + 0.5 * dy))):
                pair = ([(per[k][0], per[k][1]) for k in runs[i]],
                        [(per[k][0], per[k][1]) for k in runs[j]])
                if not every:
                    return pair
                pairs.append(pair)
    return pairs if every else None


def slab_points(m: _t.Any, origin: "tuple[float, float] | None"
                ) -> list[tuple[float, float, float]]:
    """The AUTHORED hard-deck slab of a member as ``(lat, lon, y)``: its
    ``ATTR_hard_deck`` vertices placed about the placement ``origin`` at
    its heading (``authored_offset``'s map, inverted).  Empty where the
    file or the origin is not to hand."""
    path = getattr(m, "authored_path", "") or ""
    if origin is None or not path or not os.path.isfile(path):
        return []
    from . import obj8 as _obj8
    from .rebake_plan import _mpd
    try:
        g = _obj8.parse_obj8(path)
    except (OSError, ValueError):
        return []
    tri = g.hard_deck
    if not len(tri):
        return []
    ix = sorted({int(i) for t in tri for i in t})
    ml, mo = _mpd(float(origin[0]))
    h = math.radians(float(getattr(m, "heading_deg", 0.0) or 0.0))
    c, sn = math.cos(h), math.sin(h)
    out = []
    for i in ix:
        x, y, z = (float(v) for v in g.vertices[i][:3])
        east, north = x * c - z * sn, -(x * sn + z * c)
        out.append((float(origin[0]) + north / ml, float(origin[1]) + east / mo, y))
    return out


def _top_near(slab: _t.Sequence[tuple[float, float, float]], end: _t.Sequence,
              reach_m: float) -> "float | None":
    """The slab's top ``y`` within ``reach_m`` of an end's stations."""
    from .rebake_plan import _mpd
    if not slab or not end:
        return None
    ml, mo = _mpd(float(end[0][0]))
    near = [y for la, lo, y in slab
            if any(math.hypot((la - q[0]) * ml, (lo - q[1]) * mo) <= reach_m
                   for q in end)]
    return max(near) if near else None


def end_tops(m: _t.Any, ends: tuple[list, list], origin, step_m: float
             ) -> tuple[float, float]:
    """The deck top AT each end: the slab's max ``y`` near the end's
    stations (a deck authored on a grade rises with it), else the slab's
    max (``deck_top_y``)."""
    slab = slab_points(m, origin)
    top = float(m.deck_top_y)
    out = []
    for e in ends:
        t = _top_near(slab, e, max(2.0 * step_m, 3.0))
        out.append(top if t is None else t)
    return out[0], out[1]


def _airside_witness(m: _t.Any, decks: _t.Sequence, surface: _ar.Surface
                     ) -> "tuple[tuple, float, _t.Any, float | None] | None":
    """22n's witness that a pack deck stands over AIRSIDE: ``(ring, top,
    face, z_face)`` — a flag / signature deck whose ring stands on an
    emitted deck face, or over an airside role with the plan's solved
    ``deck_datum_z`` — else ``None``."""
    top = getattr(m, "deck_top_y", None)
    ring = tuple(getattr(m, "deck_ring", None) or ())
    if (top is None or len(ring) < 3
            or str(getattr(m, "deck_kind", "") or "") not in ("flag", "signature")):
        return None
    la = sum(float(q[0]) for q in ring) / len(ring)
    lo = sum(float(q[1]) for q in ring) / len(ring)
    face = _ar.deck_of(decks, la, lo) if decks else None
    z_face = None if face is None else _ar.deck_z_at(face, la, lo)
    if z_face is None:
        roles = getattr(surface, "roles", None)
        if getattr(m, "deck_datum_z", None) is None or roles is None:
            return None
        got = roles.roles_many([float(q[0]) for q in ring], [float(q[1]) for q in ring])
        if not any(airside_role(r) for r in got if r):
            return None
    return ring, float(top), face, z_face


def airside_zero(m: _t.Any, decks: _t.Sequence, surface: _ar.Surface,
                 step_m: float = 0.0, origin: "tuple[float, float] | None" = None,
                 counts: "dict | None" = None) -> "tuple | None":
    """``(zero, where[, seat])`` of an AIRSIDE hard-deck member — the world height
    of its authored ``y = 0`` that puts its deck top on the solved airside
    surface at its end lines — or ``None`` (not class A).  A deck over
    airside that the airport's pavement does not run across (RULINGS
    2026-10-27c, :func:`pavement_runs_across`) is not class A: counted
    ``airside_deck_touch_only``.

    A member carrying a HARD-DECK BRIDGE's plate (``plate_kind == "deck"``,
    ``pipeline/rebake_inputs._deck_plate``; owner RULINGS 2026-10-30a (1))
    is read off it alone: the planar stage found the pavement across it and
    the design solve graded both end lines to one zero, so the zero is the
    solved surface at the plate's stations less the deck top.  A ROAD
    OVERPASS's plate (``"overpass"``, RULINGS 2026-10-30f (5)) is read the
    same way: its stations are the road beneath, its y the zero's own.  A
    plate's reading carries its ``seat`` (:func:`_plate_zero`)."""
    plated = _plate_zero(m, surface)
    if plated is not None:
        return plated
    w = _airside_witness(m, decks, surface)
    if w is None:
        return None
    ring, top, face, z_face = w
    if not pavement_runs_across(ring, surface, step_m):
        if counts is not None:
            counts["airside_deck_touch_only"] = counts.get("airside_deck_touch_only", 0) + 1
        return None
    ends = airside_end_ground(ring, surface, step_m)
    if ends is not None:
        (z1, z2), lines = ends
        t1, t2 = end_tops(m, lines, origin, step_m)
        return (0.5 * ((z1 - t1) + (z2 - t2)),
                f"the solved airside surface at its end lines {z1:.2f} / {z2:.2f} "
                f"(deck top y {t1:+.2f} / {t2:+.2f})")
    if z_face is not None:
        return float(z_face) - top, face.ref
    return float(m.deck_datum_z) - top, "the solved airside surface (ring median)"


#: the plate kinds class A reads the zero off alone: a hard-deck bridge's
#: end lines (``pipeline/rebake_inputs.DECK_PLATE``) and a road overpass's
#: road beneath (``OVERPASS_PLATE``, RULINGS 2026-10-30f (5))
_PLATED = {"deck": "the hard-deck bridge's end lines {lo:.2f}..{hi:.2f} over {n} stations "
                   "(deck top y {y:+.2f}; RULINGS 2026-10-30a)",
           "overpass": "the road beneath the overpass {lo:.2f}..{hi:.2f} over {n} stations "
                       "(its zero on the road, y {y:+.2f}; RULINGS 2026-10-30f (5))"}


def _plate_zero(m: _t.Any, surface: _ar.Surface) -> "tuple[float, str, tuple] | None":
    """``(zero, where, seat)`` off a hard-deck bridge's or a road
    overpass's plate, or ``None``; ``seat`` is the station ``(lat, lon,
    z)`` nearest the stations' middle — where a body of the frame whose own
    anchor reads no surface is anchored (:func:`airside_deck`)."""
    st = tuple(getattr(m, "plate_stations", ()) or ())
    y = getattr(m, "plate_y", None)
    kind = getattr(m, "plate_kind", "")
    if kind not in _PLATED or not st or y is None:
        return None
    read = [(float(q[0]), float(q[1]), surface(float(q[0]), float(q[1]))) for q in st]
    read = [(la, lo, float(z)) for la, lo, z in read if z is not None]
    if not read:
        return None
    zs = [z for _la, _lo, z in read]
    zero = sum(zs) / len(zs) - float(y)
    cla = sum(r[0] for r in read) / len(read)
    clo = sum(r[1] for r in read) / len(read)
    seat = min(read, key=lambda r: (r[0] - cla) ** 2 + (r[1] - clo) ** 2)
    return zero, _PLATED[kind].format(lo=min(zs), hi=max(zs), n=len(zs), y=float(y)), seat


def _maybe_a_building(st: _t.Any, i: int, surface: _ar.Surface) -> bool:
    """Can body ``i`` of ``st`` be a BUILDING — does it stand on an emitted
    object PAD, the class rule's own witness (``placement_plan`` §6:
    ``building`` when a body stands inside an emitted object pad)?  Read at
    its hull box's centre; a body with no box, or a surface with no roles,
    cannot be cleared and counts as one."""
    roles = getattr(surface, "roles", None)
    boxes = list(getattr(st, "boxes", ()) or ())
    if roles is None or i >= len(boxes) or boxes[i] is None:
        return True
    from .placement_read import PAD_FACE_ROLE
    b = boxes[i]
    got = roles.roles_many([0.5 * (b[0] + b[2])], [0.5 * (b[1] + b[3])])
    return got[0] == PAD_FACE_ROLE


def _is_the_bridge(staged: _t.Sequence[_t.Any], deck: _t.Any,
                   surface: "_ar.Surface | None" = None) -> bool:
    """§16e (3)'s ``Staged.bridge``: every OTHER member's every body stands
    inside ``deck``'s model footprint (the rails, the piers, the abutments)
    or, outside it, on no emitted object PAD — the frame IS the bridge.

    22n's exception is "a frame that also holds a BUILDING beside it"
    (KBNA's terminal-satellite floor plate), and a building is what stands
    on a pad (:func:`_maybe_a_building`).  An abutment, a wing wall or an
    approach rail reaching past the deck's ring is still the bridge: KBNA's
    taxiway-L frame (six placements, one flag deck over two roads, its
    approach walls 60-86 m past the ring) was refused as a building frame
    and its every body sat at the strip's median ground, the deck 6 m over
    the taxiway (#1671)."""
    res = str(deck.m.resource)
    for st in staged:
        if st is deck:
            continue
        keys = list(getattr(st, "bridge", ()) or ())
        if not keys and surface is None:    # nothing to clear it by
            return False
        for i, k in enumerate(keys):
            if str(k).split("#", 1)[0] == res:
                continue
            if surface is None or _maybe_a_building(st, i, surface):
                return False
    return True


def refused_bridge(staged: _t.Sequence[_t.Any], decks: _t.Sequence,
                   surface: _ar.Surface) -> _t.Any:
    """A frame :func:`airside_frame` refused because the airport's pavement
    does not run across its deck (RULINGS 2026-10-27c) is still a BRIDGE
    frame when it IS the bridge (:func:`_is_the_bridge`), and a bridge
    moves as one (10-22c/f), its deck first (10-22d: "the priority is the
    road/taxiway deck").  The deck's staged member — the placement stage
    seats every body of the frame at that deck's own zero — or ``None``.
    Asked only of a frame class A refused (ELLX's ``Bridge_2``: four
    placements, one flag deck, its supports inside the deck's footprint)."""
    for st in staged:
        if _airside_witness(st.m, decks, surface) is not None:
            return st if _is_the_bridge(staged, st, surface) else None
    return None


def airside_frame(staged: _t.Sequence[_t.Any], decks: _t.Sequence,
                  surface: _ar.Surface, counts: dict,
                  step_m: float = 0.0, origin: "tuple[float, float] | None" = None
                  ) -> "tuple[float, str] | None":
    """Owner RULINGS 2026-10-22n (#1214): CLASS A — this frame is an
    AIRSIDE hard-deck BRIDGE: ``(zero, where)`` for every body of it, or
    ``None``.  Its deck member reads :func:`airside_zero`, and every other
    member's every body stands inside that deck's model footprint (§16e
    (3)'s ``Staged.bridge``: the rails, the piers, the abutments) — the
    frame IS the bridge, and it moves as one (10-22c).  A frame holding a
    deck and a building beside it (KBNA's terminal satellite floor plate)
    is not a bridge: nothing moves, and the census names it."""
    deck = None
    for st in staged:
        a = airside_zero(st.m, decks, surface, step_m, origin, counts)
        if a is not None:
            deck = (st, a)
            break
    if deck is None:
        return None
    if not _is_the_bridge(staged, deck[0], surface):
        counts["airside_deck_in_a_building_frame"] = \
            counts.get("airside_deck_in_a_building_frame", 0) + 1
        return None
    counts["airside_deck_frames"] = counts.get("airside_deck_frames", 0) + 1
    return deck[1]


def airside_deck(record: _t.Any, m: _t.Any, airside: "tuple[float, str] | None",
                 counts: dict) -> _t.Any:
    """Every body of a CLASS A frame (:func:`airside_frame`) at the airside
    zero — the deck top FLUSH with the solved airside surface, its supports
    attached; the road under it is the underpass cut's.  Each body's file
    is renamed for the offset it now bakes (R1, ``placement_file.
    named_body``)."""
    if airside is None:
        return record
    from .placement_file import authored_offset, named_body
    zero, where, *seat = airside
    out = []
    for b in record.bodies:
        a = b.anchor
        if a.surface_z is None and seat:
            # #1692: a body whose own anchor reads no surface (an abutment
            # off the map) rides the frame: anchored at the plate's seat
            la, lo, sz = seat[0]
            y0 = float(sz) - zero
            a = _dc.replace(a, lat=la, lon=lo, surface_z=float(sz), y_zero=y0,
                            offset=authored_offset(la, lo, y0, record.lat, record.lon,
                                                   record.heading))
        if a.surface_z is None:
            out.append(b)
            continue
        y0 = float(a.surface_z) - zero
        off = tuple(a.offset)
        a2 = _dc.replace(a, y_zero=y0, offset=(off[0], y0, off[2]), datum=True,
                         reason=f"airside deck on {where}: flush at zero {zero:.2f} "
                                f"(RULINGS 2026-10-22n; was: {b.anchor.reason})")
        out.append(named_body(m, b, anchor=a2))
    counts["airside_deck_placements"] = counts.get("airside_deck_placements", 0) + 1
    return _dc.replace(record, bodies=tuple(out))
