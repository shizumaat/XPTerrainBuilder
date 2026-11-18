"""THE GROUND ROUND A BANKED DECK (#2141; owner sim read 2026-11-18T13:58Z,
ESSA 1.0.558 at 59.657248, 17.952089: "The embankment at the actual
taxiway down to the cut is good, but then we're cutting a strange jagged
edge around the corner of the bridge.  The bridge on the taxi edges should
be graded smoothly to ground the entire width, with the same embankment
the whole way").

A banked deck's cut (``model/deck_bank``) blends out past its ring on the
bank's own face (``constraints/edge_deck._blend_drop``) -- but only over
ground the map HAS.  Round the deck's corners, past the 1 m run-on
(``deck_bridge.deck_ground``) and beyond the zone bands and the corridor's
walls, nothing owned the ground: it was outside the patch, the base mesh at
the DEM beside a cut 5 m deep.  MEASURED ESSA (``v2_solve_replay`` capture
on test-558 fa425778c): every one of the 5 generated decks had four such
holes within 10 m of its ring, 29-259 m2 each, one at each corner
(o4gen_44525b99 at the owner's corner 259 m2), and every jag the walk round
the ring read (``tools/deck_probe.py --bank-perimeter``) stood on the
corridor's wall rim or on such a hole's edge.

So each GENERATED deck mints ``graded_strip`` pieces under
:data:`SKIRT_PREFIX` over the free ground its bank reaches
(:func:`_skirt_region`: the run-on, then the deepest end's depth at the bank's
slope, then a metre more for the daylight line) -- a zone region's family,
no zone class, the form of ``planar/pit_bank``.  Not a pack deck's (RULINGS 2026-11-17p
shares the bank, not this ground): MEASURED KIAH (lkiah capture), round
pack decks whose cut does not yet reach under (``deck_probe --cut-cover``
FAIL in the control, ground 6-7 m over the bank) a skirt carried the bank's
face down beside ground standing at the deck -- obj24614's walk 5 -> 20
jags.  The ground's own datum
holds it on the DEM (``solve/design_ground``: ground reaching the patch's
edge); the deck's blend holds it under the bank's face (a ceiling).  Each
piece welds to the zone bands, the keep-outs and the deck's own corridor
(its ground, walls and floor), stands off every other cell and the airside
pavement by its frontage.  No airport is named
(RULINGS 2026-10-05e)."""
from __future__ import annotations

import typing as _t

import shapely
from shapely.geometry import Polygon

from .bank_cut import knives, pieces
from .stack_ground import _areal

__all__ = ["SKIRT_PREFIX", "deck_skirt_pieces", "is_deck_skirt_ref"]

#: a piece of the ground round a banked deck
SKIRT_PREFIX = "deck_skirt:"
#: the corridor's own roles: the skirt meets them, never stands off
_MET = frozenset({"graded_strip", "retaining_wall", "tunnel_ramp", "tunnel_trench"})
#: past the daylight line, so the bank's face meets the DEM inside the map (m)
_MARGIN_M = 1.0


def is_deck_skirt_ref(ref: object) -> bool:
    """Is this face a piece of the ground round a banked deck?"""
    return str(ref or "").startswith(SKIRT_PREFIX)


def _skirt_region(db, law):
    """The plan the bank under ``db`` reaches (module doc)."""
    from ..model.deck_bank import bank_past_m, deck_bank_slope
    slope = deck_bank_slope(law)
    depth = max(float(db.depth_a or 0.0), float(db.depth_b or 0.0))
    ring = Polygon(db.ring)
    if not ring.is_valid:
        ring = ring.buffer(0.0)
    return ring.buffer(bank_past_m(law), join_style="mitre").buffer(
        depth / slope + _MARGIN_M if slope > 0.0 else _MARGIN_M)


def deck_skirt_pieces(decks: _t.Sequence, regions: _t.Sequence, keepouts: _t.Sequence,
                      cut_m: float, hairline_m: float, vertex_m: float, law,
                      notes: "list | None" = None) -> list[tuple[str, _t.Any]]:
    """``(ref, polygon)`` per skirt piece (module doc): ``regions`` the
    arrangement's regions so far (zone bands and the corridor's own cells
    met, the airside stood off by its frontage, the rest by ``cut_m``),
    ``keepouts`` met, never entered: a corridor's keep-out is its rim's
    outline, and a skirt stood off it left the rim on the wall's face alone,
    3.8 m over the skirt 1 m away (MEASURED ESSA o4gen_44525b99).  The road
    ribbons claim their own footprint at the face claim (``planar/overlay``),
    as round a pit's bank."""
    from ..model.structures import is_generated
    plan = [(db, _skirt_region(db, law)) for db in decks
            if is_generated(db) and len(getattr(db, "ring", ()) or ()) >= 3]
    if not plan:
        return []
    taken = [r.polygon for r in regions if r.source == "zone" or r.role in _MET]
    air = [r.polygon for r in regions
           if r.source != "zone" and r.role not in _MET and r.side == "airside"]
    other = [r.polygon for r in regions
             if r.source != "zone" and r.role not in _MET and r.side != "airside"]
    reach = shapely.union_all([g for _db, g in plan])
    knife, _rib = knives(reach, taken + list(keepouts), other, air, (), cut_m, law)
    out: list[tuple[str, _t.Any]] = []
    claimed = None
    for db, g in sorted(plan, key=lambda t: t[0].object_id):
        piece = g if claimed is None else g.difference(claimed)
        piece = _areal(piece)
        if piece.is_empty:
            continue
        claimed = piece if claimed is None else claimed.union(piece)
        got = pieces(piece, knife, hairline_m, vertex_m)
        out.extend((f"{SKIRT_PREFIX}{db.object_id}#{j}", q) for j, q in enumerate(got))
        if notes is not None and got:
            notes.append(f"{db.object_id}: {len(got)} piece(s) "
                         f"{sum(q.area for q in got):.0f} m2")
    return out
