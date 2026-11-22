"""THE WALLED TRENCH UNDER A HARD DECK, in plan (owner RULINGS 2026-10-30f
(3)): the floor between a walled deck's inner wall faces and the rim behind
them, and the open stretch toward the next deck over the same road.  A leaf
over ``geom/wall_lines``: it reads a deck only by its ``ring`` and ``walls``
(``model/structures.DeckBridge``), so the planar cut
(``planar/deck_bridge``) and the floor rows (``constraints/walled_floor``,
which may not import ``planar``) answer with ONE derivation.  Moved here
from ``planar/deck_bridge`` / ``planar/deck_walls`` unchanged.  Nothing
here names a pack or an airport.
"""
from __future__ import annotations

import functools
import typing as _t

from shapely.geometry import Polygon
from shapely.ops import unary_union

from .wall_lines import inner_faces, project_span, stretch_pair

__all__ = ["ring_polygon", "deck_polygon", "wall_strip", "open_stretch", "rim_end_stations"]

XY = tuple[float, float]


def ring_polygon(ring) -> Polygon:
    """``ring`` as a valid polygon (cached on its points)."""
    return _ring_polygon(tuple(tuple(p) for p in ring))


def deck_polygon(db) -> Polygon:
    """The deck piece's outline as a valid polygon (the model holds no
    shapely: ``model/structures.DeckBridge``)."""
    return ring_polygon(db.ring)


@functools.lru_cache(maxsize=4096)
def _ring_polygon(ring: tuple) -> Polygon:
    p = Polygon(ring)
    return p if p.is_valid else p.buffer(0.0)


def wall_strip(r: tuple[float, float], n: tuple[float, float], u0: float, u1: float,
               s0: float, s1: float) -> Polygon:
    """The plan rectangle ``u0 <= u <= u1``, ``s0 <= s <= s1``."""
    def at(s: float, u: float) -> tuple[float, float]:
        return (r[0] * s + n[0] * u, r[1] * s + n[1] * u)
    return Polygon([at(s0, u0), at(s1, u0), at(s1, u1), at(s0, u1)])


def _walled_trench(db, inset: float, other: "_t.Any" = None
                  ) -> "tuple[Polygon, Polygon] | None":
    """``(floor, rim)`` of a WALLED deck (``planar/deck_walls``; RULINGS
    2026-10-30f (3)): the floor is the strip between the walls' inner faces
    under the deck — and, toward ``other`` deck over the same road, along
    the open stretch to it, between that stretch's own inner faces — and
    the rim the same strip ``inset`` wider (behind the walls), inside the
    deck's ring under it.  ``None`` where either side of the deck has no
    wall: the 30b bank stands there.

    #2157 R2: a wall line outside the ring's own reach across the road is
    not this deck's wall (a frame's wall under another span of the same
    object), and the floor never leaves the ring's reach across the road
    but along the open stretch to ``other`` (MEASURED KRDU obj140: the W
    span took the E span's wall 436 m away and floored the at-grade
    taxiway between them)."""
    if not db.walls:
        return None
    r, n, faces = db.walls[:3]
    floor = db.walls[3] if len(db.walls) > 3 else ()   # K2: the frame's floor
    u_lo, u_hi = project_span(db.ring, n)
    s_lo, s_hi = project_span(db.ring, r)
    ua, ub = inner_faces(faces, s_lo, s_hi, 0.5 * (u_lo + u_hi), (u_lo, u_hi), floor)
    if ua is None or ub is None:
        return None
    floors = [wall_strip(r, n, max(ua, u_lo), min(ub, u_hi), s_lo, s_hi)]
    rims = [wall_strip(r, n, ua - inset, ub + inset, s_lo, s_hi).intersection(ring_polygon(db.ring))]
    for (va, vb), (g0, g1) in getattr(db, "beyond", ()) or ():
        floors.append(wall_strip(r, n, va, vb, g0, g1))     # W7b: past its ends
        rims.append(wall_strip(r, n, va - inset, vb + inset, g0, g1))
    got = open_stretch(db, other, (ua, ub)) if other is not None else None
    if got is not None:
        (va, vb), (g0, g1) = got
        floors.append(wall_strip(r, n, va, vb, g0, g1))
        rims.append(wall_strip(r, n, va - inset, vb + inset, g0, g1))
    return unary_union(floors), unary_union(rims)


def open_stretch(db, other, pair: tuple[float, float]
                 ) -> "tuple[tuple[float, float], tuple[float, float]] | None":
    """``((u_a, u_b), (s0, s1))``: the wall pair across the road and the
    stretch along it of the OPEN STRETCH between walled ``db`` (its own
    pair ``pair``) and ``other`` deck over the same road
    (:func:`_walled_trench`), or ``None`` where they do not stand apart or
    the stretch has no wall pair.  A side no single line covers reads the
    two spans' own lines (``geom/wall_lines.stretch_pair``: a skewed wall,
    or the frame's floor running on between them)."""
    r, n, faces = db.walls[:3]
    floor = db.walls[3] if len(db.walls) > 3 else ()
    u_lo, u_hi = project_span(db.ring, n)
    s_lo, s_hi = project_span(db.ring, r)
    o_lo, o_hi = project_span(other.ring, r)
    g0, g1 = (s_hi, o_lo) if o_lo >= s_hi else (o_hi, s_lo)
    if g1 <= g0:
        return None
    va, vb = inner_faces(faces, g0, g1, 0.5 * (u_lo + u_hi), (u_lo, u_hi), floor)
    if (va is None or vb is None) and other.walls:
        ou_lo, ou_hi = project_span(other.ring, n)
        os_lo, os_hi = project_span(other.ring, r)
        oa, ob = inner_faces(faces, os_lo, os_hi, 0.5 * (ou_lo + ou_hi), (ou_lo, ou_hi),
                             floor)
        if oa is not None and ob is not None:
            sa, sb = stretch_pair(faces, g0, g1, pair, (oa, ob), floor)
            va, vb = (sa if va is None else va), (sb if vb is None else vb)
    if va is None or vb is None or va >= vb:
        return None
    return (va, vb), (g0, g1)


def rim_end_stations(db, step: float, gap: float
                     ) -> "tuple[tuple[XY, ...], tuple[XY, ...]] | None":
    """W3 (walled-multibridge-frames spec): the end-line stations ``(A, B)``
    of a WALLED piece moved across the road to one ``step`` past the larger
    of its ring and its rim (the K2 wall pair less / plus ``gap``) -- the
    pavement the taxiway drives onto the deck from, never the rim or the pit
    -- or ``None`` for a piece with no wall pair.  The pre-solve zero
    (:func:`_walled_zero`) and the planar seats (``constraints/deck_lines.
    end_lines``) read the same stations."""
    if _walled_trench(db, gap) is None:
        return None
    r, n, faces = db.walls[:3]
    floor = db.walls[3] if len(db.walls) > 3 else ()
    u_lo, u_hi = project_span(db.ring, n)
    s_lo, s_hi = project_span(db.ring, r)
    mid = 0.5 * (u_lo + u_hi)
    ua, ub = inner_faces(faces, s_lo, s_hi, mid, (u_lo, u_hi), floor)
    lo, hi = min(u_lo, ua - gap) - step, max(u_hi, ub + gap) + step

    def moved(st) -> tuple[XY, ...]:
        out = []
        for x, y in st:
            u = x * n[0] + y * n[1]
            du = (lo if u < mid else hi) - u
            out.append((x + du * n[0], y + du * n[1]))
        return tuple(out)
    return moved(db.seats_a), moved(db.seats_b)
