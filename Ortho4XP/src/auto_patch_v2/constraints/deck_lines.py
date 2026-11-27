"""THE DECKS' END LINES ON A MAP (deck redesign §1; owner RULINGS
2026-10-30a (1), 2026-11-03c): every pack deck of ``PlanarMap.decks``
(``model/structures.DeckBridge``, derived once by ``planar/deck_bridge``),
per object, as its end lines — each piece's A then B, in the map's deck
order — with the seat they hold: the mean of each station's nearest
airside vertex (``constraints/edge_floor``'s set seat).  The anchors
(``constraints/deck_anchor``), the deck rows (``constraints/edge_deck``)
and the object stage's plate (``pipeline/rebake_inputs``) read THIS, never
a tunnel's copy of the deck: a deck no corridor runs under is read like any
other (§0: round 3 keyed every one of them to a ``Tunnel``)."""
from __future__ import annotations

import typing as _t

from ..law import Law
from ..model.planar import PlanarMap
from ..model.structures import DeckBridge

__all__ = ["end_lines", "floor_end_lines", "anchor_of", "cut_faces", "plate_of"]

XY = tuple[float, float]


class EndLine(_t.NamedTuple):
    """One end line of a deck piece: its deck, the deck's stations there
    (frame xy, the line's identity on every map), the seat terms
    ``((vertex, weight), ...)`` and the depth (top less the frame's
    bottom) there."""

    deck: DeckBridge
    line: tuple[XY, ...]
    terms: tuple[tuple[int, float], ...]
    depth: float
    #: #2241: ``((vertex, depth there), ...)`` where the slab's top differs
    #: along the line (``DeckBridge.station_tops``): each seat vertex's own
    #: depth, ``depth`` their weighted mean; ``()`` reads ``depth`` at every one
    tops: tuple[tuple[int, float], ...] = ()


def end_lines(planar: PlanarMap, law: Law) -> dict[str, list[EndLine]]:
    """Object id -> its end lines (module doc), each line once; ``{}`` with
    no deck or no airside vertex to seat on."""
    decks = getattr(planar, "decks", ()) or ()
    if not decks:
        return {}
    from ..model.platform import stage_air_vertices
    from .edge_floor import _mean_terms
    from .geometry import nearest_vertex_fn
    near = nearest_vertex_fn(planar, stage_air_vertices(planar, law))
    if near is None:
        return {}
    rim = _rim_seats(planar, law, decks)
    out: dict[str, list[EndLine]] = {}
    seen: set[tuple] = set()
    for db in decks:
        moved = rim.get(id(db))
        for k, (st, depth) in enumerate(((db.seats_a, db.depth_a), (db.seats_b, db.depth_b))):
            line = tuple(tuple(p) for p in st)
            if not line or (db.object_id, line) in seen:
                continue
            seen.add((db.object_id, line))
            pairs = moved[k] if moved is not None and moved[k] else \
                [(i, near(x, y)) for i, (x, y) in enumerate(line)]
            vs = [v for _i, v in pairs]
            tops = _vertex_depths(db, k, pairs)
            if tops:
                # the seat mean's own depth: every station once (``_mean_terms``)
                tk = db.station_tops[k]
                depth = sum(float(tk[i]) for i, _v in pairs) / len(pairs) - float(db.bottom_y)
            out.setdefault(db.object_id, []).append(EndLine(
                db, line, _mean_terms(vs), float(depth), tops))
    return out


def _vertex_depths(db: DeckBridge, k: int, pairs) -> tuple[tuple[int, float], ...]:
    """#2241: each seat vertex's depth -- the mean of its stations' slab tops
    (``DeckBridge.station_tops[k]``) less the frame's bottom; ``()`` where
    the deck reads one top per end line, or the tops are one level."""
    st = getattr(db, "station_tops", ()) or ()
    if len(st) != 2 or not st[k] or len(st[k]) != len((db.seats_a, db.seats_b)[k]):
        return ()
    acc: dict[int, list[float]] = {}
    for i, v in pairs:
        acc.setdefault(v, []).append(float(st[k][i]) - float(db.bottom_y))
    out = tuple(sorted((v, sum(d) / len(d)) for v, d in acc.items()))
    if max(d for _v, d in out) - min(d for _v, d in out) < 1e-9:
        return ()
    return out


def _rim_seats(planar: PlanarMap, law: Law, decks) -> dict[int, tuple[list, list]]:
    """W3 (walled-multibridge-frames spec): per WALLED deck (``id``), the seat
    vertices of its two end lines read at its stations moved one
    ``abutment_sample_step_m`` outside the larger of its ring and its rim
    (``planar/deck_bridge.rim_end_stations``): each the nearest AIRSIDE
    vertex OFF the cut (no structure face at it) within two steps -- the
    pavement the taxiway drives onto the deck from.  A station with none
    seats nowhere; an end line with none keeps its ring stations' seats
    (:func:`end_lines`).  MEASURED KORD I-190: the ring's own stations
    seated on the rim and the pit edge."""
    from ..geom import exact
    from ..geom.walled_trench import rim_end_stations
    from ..law.tables import is_structure_role
    from ..model.platform import stage_air_vertices
    from .geometry import nearest_vertex_fn
    step = float(law.tables.structures.bridge.abutment_sample_step_m)
    from ..geom.deck_plan import wall_inset
    gap = wall_inset(law)      # #2239 R2: the rim the stations stand past
    got = {id(db): st for db in decks if (st := rim_end_stations(db, step, gap)) is not None}
    if not got:
        return {}
    off = {v for v in stage_air_vertices(planar, law)
           if not any(is_structure_role(law, planar.faces[f].role)
                      for f in planar.vertices[v].incident_faces if f in planar.faces)}
    near = nearest_vertex_fn(planar, off)
    if near is None:
        return {}
    reach2 = exact.sq(2.0 * step)

    def seats(st) -> list[tuple[int, int]]:
        # ``(station index, vertex)``: a station seats nowhere off the cut
        return [(i, v) for i, (x, y) in enumerate(st) if (v := near(x, y)) is not None
                and exact.sq(planar.vertices[v].xy[0] - x)
                + exact.sq(planar.vertices[v].xy[1] - y) <= reach2]
    return {k: (seats(a), seats(b)) for k, (a, b) in got.items()}


def floor_end_lines(planar: PlanarMap, law: Law) -> dict[str, list[EndLine]]:
    """Deck piece id -> its two end lines, for every deck over a pack's cut
    (``ObjectFloor.decks``, ``planar/floor_decks``; #1883 r3 B2): each its
    OWN zero (LGAV ``Trench_00``'s pieces stand 3.1 m apart), the seat the
    mean of each station's nearest map vertex OFF the cut (a vertex of a
    face that is no structure: the pavement or ground the deck ends on)
    within two ``abutment_sample_step_m``, the depth its top (``bottom`` 0)."""
    from ..geom import exact
    from ..law.tables import is_structure_role
    from .edge_floor import _mean_terms
    from .geometry import nearest_vertex_fn
    decks = [d for f in (getattr(planar, "object_floors", ()) or ()) for d in f.decks]
    if not decks:
        return {}
    ids = {v for v, vx in planar.vertices.items()
           if any(not is_structure_role(law, planar.faces[f].role)
                  for f in vx.incident_faces if f in planar.faces)}
    near = nearest_vertex_fn(planar, ids)
    if near is None:
        return {}
    reach = 2.0 * float(law.tables.structures.bridge.abutment_sample_step_m)
    out: dict[str, list[EndLine]] = {}
    for d in decks:
        for st, top in ((d.seats_a, d.top_a), (d.seats_b, d.top_b)):
            vs = [v for x, y in st if (v := near(x, y)) is not None
                  and exact.sq(planar.vertices[v].xy[0] - x)
                  + exact.sq(planar.vertices[v].xy[1] - y) <= reach * reach]
            if vs:
                out.setdefault(d.id, []).append(EndLine(d, tuple(st), _mean_terms(vs), float(top)))
    return {k: v for k, v in out.items() if len(v) == 2}


def plate_of(lines: _t.Sequence[EndLine], law: Law) -> list[int]:
    """The PLATE of each of one object's end lines (#2112; owner
    2026-11-17T14:57Z "(a) split them so they can better follow the
    terrain"): a deck authored as disjoint plates -- its pieces' rings
    further apart than ``[placement] rigid_reach_m`` and banding along one
    axis (``airport/deck_plates.piece_plates``, the object stage's own
    rule) -- has one zero PER PLATE, each flush at its own end lines;
    every other deck has plate 0 at every end line (one zero, 30a (1))."""
    from ..geom.plate_bands import piece_plates
    rings: list[tuple] = []
    for e in lines:
        r = tuple(tuple(q) for q in e.deck.ring)
        if r not in rings:
            rings.append(r)
    got = piece_plates(rings, float(law.tables.structures.placement.rigid_reach_m))
    if got is None:
        return [0] * len(lines)
    return [got[rings.index(tuple(tuple(q) for q in e.deck.ring))] for e in lines]


def anchor_of(planar: PlanarMap, oid: str, line: tuple) -> "_t.Any | None":
    """The deck anchor (``PlanarMap.deck_anchors``) of object ``oid``'s end
    line ``line``, ``None`` for none."""
    for a in getattr(planar, "deck_anchors", ()) or ():
        if a.object_id == oid and tuple(a.line) == tuple(line):
            return a
    return None


#: the faces of a cut: its floor and its void (``planar/structures``)
_CUT_ROLES = frozenset({"tunnel_ramp", "retaining_wall"})


def cut_faces(pm: PlanarMap, cuts) -> list[tuple[tuple[float, float], ...]]:
    """The floor and void faces of the cuts ``cuts`` (``deck_anchor.
    deck_holes``; ``edge_deck``: no span vertex inside one)."""
    if not cuts:
        return []
    from shapely.geometry import LineString, Point, Polygon
    from shapely.ops import unary_union
    from shapely.prepared import prep
    shapes = []
    for tn in cuts:
        rim = tuple(getattr(tn, "wall_path", ()) or ())
        p = Polygon(rim).buffer(0.0) if len(rim) >= 4 else None
        if (p is None or p.is_empty) and len(tn.axis) >= 2:
            p = LineString(tn.axis).buffer(float(tn.half_width_m) + 2.0)
        if p is not None and not p.is_empty:
            shapes.append(p.buffer(1.0))
    if not shapes:
        return []
    within = prep(unary_union(shapes))
    out = []
    for f in pm.faces.values():
        if f.role not in _CUT_ROLES:
            continue
        ring = tuple(tuple(pm.vertices[v].xy) for v in pm.ring_vertices(f.ring))
        if len(ring) < 3:
            continue
        q = Polygon(ring)
        if within.contains(Point(q.representative_point() if q.is_valid else ring[0])):
            out.append(ring)
    return out
