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
"""
from __future__ import annotations

import numpy as np

from ..law import Law
from ..model.airport import Airport
from ..model.constraints import Linear, Row, Source
from ..model.planar import PlanarMap

__all__ = ["edge_deck_rows", "GEN", "RULING"]

GEN = "edge_deck"
#: the ruling head (``[design] hard_rulings``)
RULING = "roads.edge bridge deck level with the airside abeam"


def edge_deck_rows(planar: PlanarMap, law: Law, airport: Airport) -> list[Row]:
    """Every terrain-deck vertex over an edge bridge's trench, held equal to
    its nearest airside pavement vertex (module doc)."""
    tunnels = [t for t in getattr(planar, "structures", ()) or ()
               if getattr(t, "edge_back", ()) and any(d.datum != "deck_top" for d in t.decks)]
    if not tunnels:
        return []
    from .roads import stage_one_vertices
    air = sorted(stage_one_vertices(planar, law))
    if not air:
        return []
    axy = np.array([planar.vertices[v].xy for v in air], dtype=float)
    faces_by_ref: dict[str, list] = {}
    for f in planar.faces.values():
        faces_by_ref.setdefault(f.ref, []).append(f)
    rows: list[Row] = []
    for tn in tunnels:
        for d in tn.decks:
            if d.datum == "deck_top":
                continue
            vs = sorted({v for f in faces_by_ref.get(d.ref, ())
                         for v in planar.ring_vertices(f.ring)} - set(air))
            src = Source(GEN, RULING, (tn.id, tn.portal, f"osm:{d.way}"))
            for v in vs:
                x, y = planar.vertices[v].xy
                k = int(np.argmin((axy[:, 0] - x) ** 2 + (axy[:, 1] - y) ** 2))
                rows.append(Linear(((v, 1.0), (air[k], -1.0)), None, 0.0, src))
                rows.append(Linear(((v, -1.0), (air[k], 1.0)), None, 0.0, src))
    return rows
