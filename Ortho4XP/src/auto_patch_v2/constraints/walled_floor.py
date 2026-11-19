"""THE GROUND UNDER A WALLED FRAME IS THE OBJECT'S FLOOR (owner RULINGS
2026-11-19m "trust the object"; walled-multibridge-frames spec W5; KORD
I-190 trench, #2157 family).

A pack trench whose walls stand under its own hard decks
(``planar/deck_bridge._walled_trench``: a wall pair on both sides of the
road under the piece) states its depth: the floor under each span is that
span's zero less the frame's own bottom, whatever the lidar trench does.
The road corridors' floors already hang from the deck's seats
(``constraints/structures``' datum rows); the REST of the ground between
the walls -- the deck's own ground (``deck_ground:<object>``), the mapped
roads beside the carriageway, any zone ground -- was the DEM's, or was
pulled flush with the deck (``constraints/edge_deck._span_rows``).
MEASURED KORD obj14271 (lane lkordtr): 7 ground vertices beside the W
span's floor up to 1.01 m under it, following the lidar.

Every map vertex strictly inside the frame's FLOOR -- under each walled
piece between its walls, and along the open stretch between two walled
pieces of one object (``deck_bridge.open_stretch``) -- that is no airside
vertex, no seat, no corridor floor (``tunnel_ramp``, the corridor's own
rows) and no wall, takes the deck-floor pair (``constraints/edge_floor``):
under a piece ``z = seat - depth`` against that piece's two end lines'
mean seat (its zero plus the bottom once the rigid rows hold); along the
stretch the floor runs linearly from one piece's to the next's.  The rows
are ``edge_deck``'s generator (``release_governed``: the vertex sheds its
DEM pin and road ramp) under the deck-floor head.  A frame whose object the
user hides has no pack deck: its generated deck's floor is the lidar's
(19m (2), ``planar/deck_generated``).  Nothing here names an airport.
"""
from __future__ import annotations

import typing as _t

from ..law import Law
from ..model.constraints import Row, Source
from ..model.planar import PlanarMap

__all__ = ["walled_floor_rows"]

#: the floor is read this far inside its edge (its edge is the walls' foot)
_INSET_M = 0.05


def _pieces(es, gap: float) -> list:
    """``(deck, seat, depth)`` of each WALLED pack piece among one object's
    end lines ``es``, its seat the mean of its two end lines' seats."""
    from ..model.structures import is_generated
    from ..planar.deck_bridge import _walled_trench
    from .edge_floor import _mean_terms
    by: dict[int, list] = {}
    for e in es:
        by.setdefault(id(e.deck), [e.deck]).append(e)
    out = []
    for d, *ends in by.values():
        if len(ends) != 2 or is_generated(d) or _walled_trench(d, gap) is None:
            continue
        seat = _mean_terms([], ((ends[0].terms, 0.5), (ends[1].terms, 0.5)))
        out.append((d, seat, 0.5 * (ends[0].depth + ends[1].depth)))
    return out


def walled_floor_rows(planar: PlanarMap, law: Law, lines, skip: _t.Callable[[int], bool],
                      gen: str) -> tuple[list[Row], set[int]]:
    """``(rows, the vertices they hold)`` (module doc) over every object's
    end lines ``lines`` (``deck_lines.end_lines``); ``skip(v)``: a vertex
    the floor never takes (the airside, a seat); ``gen`` the generator."""
    from shapely.geometry import Point
    from shapely.prepared import prep

    from ..geom.wall_lines import inner_faces, project_span
    from ..law.tables import is_structure_role
    from ..planar.deck_bridge import _walled_trench, open_stretch
    from ..planar.deck_walls import wall_strip
    from .edge_floor import DECK_FLOOR, seat_pair, sloped_floor_rows
    gap = float(law.tables.structures.tunnel.wall_gap_m)
    rows: list[Row] = []
    held: set[int] = set()
    free = [v for v, vx in planar.vertices.items()
            if not skip(v) and not any(is_structure_role(law, planar.faces[f].role)
                                       for f in vx.incident_faces if f in planar.faces)]
    for oid, es in sorted(lines.items()):
        pieces = _pieces(es, gap)
        if not pieces:
            continue
        src = Source(gen, DECK_FLOOR, (oid, oid, "walled floor"))
        r = pieces[0][0].walls[0]
        pieces.sort(key=lambda t: project_span(t[0].ring, r)[0])
        # each region: (inside, seats, stretch): under a piece one seat; along
        # the open stretch to the next piece the two seats and ``(r, s0, s1)``
        regions: list = [(prep(_walled_trench(d, gap)[0].buffer(-_INSET_M)),
                          ((seat, depth),), None) for d, seat, depth in pieces]
        for (d, sa, da), (o, sb, db) in zip(pieces, pieces[1:], strict=False):
            rw, n, faces = d.walls[:3]
            u_lo, u_hi = project_span(d.ring, n)
            s_lo, s_hi = project_span(d.ring, rw)
            pair = inner_faces(faces, s_lo, s_hi, 0.5 * (u_lo + u_hi), (u_lo, u_hi),
                               d.walls[3] if len(d.walls) > 3 else ())
            got = open_stretch(d, o, pair)
            if got is not None:
                (va, vb), (g0, g1) = got
                regions.append((prep(wall_strip(rw, n, va, vb, g0, g1).buffer(-_INSET_M)),
                                ((sa, da), (sb, db)), (rw, g0, g1)))
        for v in free:
            if v in held:
                continue
            x, y = planar.vertices[v].xy
            for inside, seats, stretch in regions:
                if not inside.contains(Point(x, y)):
                    continue
                if stretch is None:
                    rows.extend(seat_pair(v, seats[0], src))
                else:
                    r_, g0, g1 = stretch
                    rows.extend(sloped_floor_rows([(x * r_[0] + y * r_[1], [v])], seats,
                                                  (g0, g1), src))
                held.add(v)
                break
    return rows, held
