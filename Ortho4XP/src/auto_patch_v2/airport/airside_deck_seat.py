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
(``Member.deck_datum_z``).  Moved out of ``placement_plan`` (round 2's
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
           "end_tops"]


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


def airside_zero(m: _t.Any, decks: _t.Sequence, surface: _ar.Surface,
                 step_m: float = 0.0, origin: "tuple[float, float] | None" = None
                 ) -> "tuple[float, str] | None":
    """``(zero, where)`` of an AIRSIDE hard-deck member — the world height
    of its authored ``y = 0`` that puts its deck top on the solved airside
    surface at its end lines — or ``None`` (not class A)."""
    top = getattr(m, "deck_top_y", None)
    ring = tuple(getattr(m, "deck_ring", None) or ())
    if (top is None or len(ring) < 3
            or str(getattr(m, "deck_kind", "") or "") not in ("flag", "signature")):
        return None
    la = sum(float(q[0]) for q in ring) / len(ring)
    lo = sum(float(q[1]) for q in ring) / len(ring)
    face = _ar.deck_of(decks, la, lo) if decks else None
    z_face = None if face is None else _ar.deck_z_at(face, la, lo)
    dz = getattr(m, "deck_datum_z", None)
    if z_face is None:
        roles = getattr(surface, "roles", None)
        if dz is None or roles is None:
            return None
        got = roles.roles_many([float(q[0]) for q in ring], [float(q[1]) for q in ring])
        if not any(airside_role(r) for r in got if r):
            return None
    ends = airside_end_ground(ring, surface, step_m)
    if ends is not None:
        (z1, z2), lines = ends
        t1, t2 = end_tops(m, lines, origin, step_m)
        return (0.5 * ((z1 - t1) + (z2 - t2)),
                f"the solved airside surface at its end lines {z1:.2f} / {z2:.2f} "
                f"(deck top y {t1:+.2f} / {t2:+.2f})")
    if z_face is not None:
        return float(z_face) - float(top), face.ref
    return float(dz) - float(top), "the solved airside surface (ring median)"


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
        a = airside_zero(st.m, decks, surface, step_m, origin)
        if a is not None:
            deck = (st, a)
            break
    if deck is None:
        return None
    res = str(deck[0].m.resource)
    for st in staged:
        if st is deck[0]:
            continue
        keys = list(getattr(st, "bridge", ()) or ())
        if not keys or not all(str(k).split("#", 1)[0] == res for k in keys):
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
    from .placement_file import named_body
    zero, where = airside
    out = []
    for b in record.bodies:
        a = b.anchor
        if a.surface_z is None:
            out.append(b)
            continue
        y0 = float(a.surface_z) - zero
        off = tuple(a.offset)
        a2 = _dc.replace(a, y_zero=y0, offset=(off[0], y0, off[2]), datum=True,
                         reason=f"airside deck on {where}: flush at zero {zero:.2f} "
                                f"(RULINGS 2026-10-22n; was: {a.reason})")
        out.append(named_body(m, b, anchor=a2))
    counts["airside_deck_placements"] = counts.get("airside_deck_placements", 0) + 1
    return _dc.replace(record, bodies=tuple(out))
