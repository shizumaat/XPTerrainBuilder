"""THE RING IS THE DECK'S (#2239 / #2241, spec cyyz-decks-r3 R1; owner sim
read 2026-11-26T15:02Z on 1.0.585: "the end strip is NOT support").

A pack deck with a cut under it is drawn by its object: the airport's
pavement drives onto it at its end edges and the mesh under its ring is the
cut's (the trench, its walls and banks) and the deck's own ground
(``deck_bridge.deck_ground``).  An airside cell reaching INSIDE the ring --
the taxiway's polygon running on under the slab -- is neither: it holds a
strip of pavement at the deck's level over the cut, and its vertices weld
the trench floor up to the deck where the two rings stand nearer than the
arrangement keeps apart (``verify/deck_pinch``).  MEASURED (CYYZ capture
frames/lcyyz): the M deck's pavement tucked 0.46-1.01 m under its ring; 556
of the FA deck's 1,171 m2 ring under taxiway pav134 at the deck's level.

THE RULE: the knife ``generated decks`` take (``deck_generated.
carried_off``) takes, after the corridors are cut, the airside pavement
inside the ring of EVERY pack deck with a cut under it -- its ``cut`` set
(``deck_bridge.with_cuts``), a corridor passing under it
(``Tunnel.deck_bridge``), or an object corridor whose objects are the
deck's own placements.  The rolled-on roles only (``law.tables.
rolled_on_roles``), never the runway family (its rows are senior).  The
pavement then ends ON the end edge, which is a map line, every vertex on it
a station of its end line (``constraints/deck_edge_weld``); what the knife
leaves unowned is the deck's ground (``deck_bridge.deck_ground``, flush).
Nothing here names a pack or an airport.
"""
from __future__ import annotations

import dataclasses as _dc
import typing as _t

from shapely.geometry import Polygon
from shapely.ops import unary_union

from ..model.structures import is_generated

__all__ = ["cut_decks", "ring_cut"]

#: the runway family (``constraints/runway_profile.RUNWAY_FAMILY``; not
#: imported: a planar module may not reach the constraints)
_RUNWAY_FAMILY = ("runway", "runway_crossing")


def cut_decks(decks: _t.Sequence, tunnels: _t.Sequence) -> list:
    """The pack decks with a cut under them (module doc)."""
    under = {t.deck_bridge for t in tunnels if getattr(t, "deck_bridge", "")}
    objs = {o for t in tunnels for o in (getattr(t, "objects", ()) or ())}
    return [d for d in decks if not is_generated(d)
            and (d.cut != "none" or d.object_id in under
                 or objs & ({d.object_id} | set(d.members)))]


def ring_cut(classification, decks, tunnels, law) -> tuple[_t.Any, list[str]]:
    """``(classification, notes)``: the airside pavement inside every cut
    pack deck's ring cut out of its cells (module doc)."""
    from ..law.tables import rolled_on_roles
    from .cell_knife import knife_cells
    from .deck_bridge import deck_polygon
    mine = cut_decks(decks, tunnels)
    if not mine or classification is None:
        return classification, []
    knife = unary_union([deck_polygon(d) for d in mine])
    polys = []
    for c in classification.cells:
        p = Polygon(c.ring, c.holes) if len(c.ring) >= 3 else Polygon()
        polys.append(p if p.is_valid else p.buffer(0.0))
    air = rolled_on_roles(law)
    cells, n = knife_cells(classification.cells, polys, knife, law, _RUNWAY_FAMILY,
                           cut_pads=False, mark="pack_deck_cut", cuts=lambda c: c.role in air)
    if not n:
        return classification, []
    return (_dc.replace(classification, cells=tuple(cells)),
            [f"pack decks: {n} airside cell(s) cut under {len(mine)} deck ring(s) with a cut "
             f"under them, the pavement ending on their end edges (#2239, planar/deck_ring_cut)"])
