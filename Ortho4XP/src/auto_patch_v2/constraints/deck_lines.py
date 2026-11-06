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

__all__ = ["end_lines", "floor_end_lines", "anchor_of", "cut_faces"]

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
    out: dict[str, list[EndLine]] = {}
    seen: set[tuple] = set()
    for db in decks:
        for st, depth in ((db.seats_a, db.depth_a), (db.seats_b, db.depth_b)):
            line = tuple(tuple(p) for p in st)
            if not line or (db.object_id, line) in seen:
                continue
            seen.add((db.object_id, line))
            out.setdefault(db.object_id, []).append(EndLine(
                db, line, _mean_terms([near(x, y) for x, y in line]), float(depth)))
    return out


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
