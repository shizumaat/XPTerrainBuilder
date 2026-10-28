"""A ROAD DECK OVER AN EDGE BRIDGE'S TRENCH IS LEVEL WITH THE AIRSIDE ABEAM
(owner RULINGS 2026-10-28d Q211 a; 2026-10-27r "the top of the objects
flush with the airside surface"; #1138).

Where a pack models a bridge by its edges (``planar/bridge_span``), the
road the bridge carries beside the airside pavement — a mapped bridge way
over the trench, a terrain deck (spec §33 (4), ``Tunnel.decks``) — is the
bridge's own slab: it stands at the level of the airside pavement edge
abeam it and follows whatever that pavement does over the bridge.  It is
RELATIONAL, never a pre-solve deck height: each deck vertex takes an
EQUALITY to the nearest airside pavement vertex — stated as a two-sided
PAIR of one-sided rows under a head ``[design] hard_rulings`` names, so it
is a CONSTRAINT of the active set (the ``tunnel.mouth_depth_m`` idiom,
``constraints/structures``): MEASURED on the KATL capture, the one-way
equality at the law weight left the deck 1.8-7.8 m under the taxiway, the
road's DEM fit over the bare-earth trench winning the contest.  The road
deck has no other hard row there (its end ties stand down over an edge
trench, ``constraints/structures``), so the taxiway is never pulled.

THE SPAN TOO (RULINGS 28d Q212 "lifted to deck level"; owner sim read
2026-10-28T14:26Z points 4 / 5: "Runway edge should be flat and paved to
the edge of the tunnel object, no gap between them"): every vertex inside
an edge bridge's COVER (``Tunnel.edge_covers``), off the back by the rim
stand-off and on no trench face, takes the same pair to its nearest airside
vertex — measured on the KATL capture, ``tunel_A`` south's span (a pack
parking lot) stood 2.9 m under to 1.8 m over the runway edge abeam.
"""
from __future__ import annotations

from ..law import Law
from ..model.airport import Airport
from ..model.constraints import Linear, Row, Source
from ..model.planar import PlanarMap

__all__ = ["edge_deck_rows", "airside_nearest", "GEN", "RULING"]

GEN = "edge_deck"
#: the ruling head (``[design] hard_rulings``)
RULING = "roads.edge bridge deck level with the airside abeam"


def airside_nearest(planar: PlanarMap, law: Law):
    """``nearest(x, y) -> vertex id``: the airside pavement vertex nearest
    a point (``roads.stage_one_vertices``), or ``None`` with no airside."""
    from .geometry import nearest_vertex_fn
    from .roads import stage_one_vertices
    return nearest_vertex_fn(planar, stage_one_vertices(planar, law))


def edge_deck_rows(planar: PlanarMap, law: Law, airport: Airport) -> list[Row]:
    """Every terrain-deck vertex over an edge bridge's trench, held equal to
    its nearest airside pavement vertex (module doc)."""
    tunnels = [t for t in getattr(planar, "structures", ()) or ()
               if getattr(t, "edge_back", ()) and (
                   getattr(t, "edge_covers", ()) or any(d.datum != "deck_top" for d in t.decks))]
    if not tunnels:
        return []
    nearest = airside_nearest(planar, law)
    if nearest is None:
        return []
    rows: list[Row] = []
    for tn in tunnels:
        src = Source(GEN, RULING, (tn.id, tn.portal, "span"))
        for v in _span_vertices(planar, law, tn) - nearest.air:
            a = nearest(*planar.vertices[v].xy)
            rows.append(Linear(((v, 1.0), (a, -1.0)), None, 0.0, src))
            rows.append(Linear(((v, -1.0), (a, 1.0)), None, 0.0, src))
    faces_by_ref: dict[str, list] = {}
    for f in planar.faces.values():
        faces_by_ref.setdefault(f.ref, []).append(f)
    for tn in tunnels:
        for d in tn.decks:
            if d.datum == "deck_top":
                continue
            vs = sorted({v for f in faces_by_ref.get(d.ref, ())
                         for v in planar.ring_vertices(f.ring)} - nearest.air)
            src = Source(GEN, RULING, (tn.id, tn.portal, f"osm:{d.way}"))
            for v in vs:
                a = nearest(*planar.vertices[v].xy)
                rows.append(Linear(((v, 1.0), (a, -1.0)), None, 0.0, src))
                rows.append(Linear(((v, -1.0), (a, 1.0)), None, 0.0, src))
    return rows


#: the roles of an edge trench's own faces: never part of its span
_TRENCH_ROLES = frozenset({"tunnel_ramp", "retaining_wall"})


def _span_vertices(planar: PlanarMap, law: Law, tn) -> set[int]:
    """The vertices inside ``tn``'s edge covers, at least the rim stand-off
    (``wall_gap_m + wall_band_width_m``) inside each, on no trench face
    (module doc)."""
    covers = getattr(tn, "edge_covers", ()) or ()
    if not covers:
        return set()
    from shapely.geometry import Point, Polygon
    from shapely.prepared import prep
    t = law.tables.structures.tunnel
    inner = [prep(q) for q in (Polygon(c).buffer(-(t.wall_gap_m + t.wall_band_width_m))
                               for c in covers if len(c) >= 4) if not q.is_empty]
    if not inner:
        return set()
    out: set[int] = set()
    for v, vx in planar.vertices.items():
        if any(c.contains(Point(vx.xy)) for c in inner) and \
                not _TRENCH_ROLES & set(planar.roles_at(v)):
            out.add(v)
    return out
