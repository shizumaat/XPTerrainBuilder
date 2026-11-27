"""A PACK DECK'S APRON: THE GROUND ITS END MEETS (#2239 / #2241, spec
cyyz-decks-r3 R4; owner sim read 2026-11-26T15:02Z on 1.0.585: "the weld
must span the deck's full width including shoulders").

Outside a deck's END EDGE (``geom/deck_end_edge``) the airport's pavement
drives on where it is mapped; where it is not -- a shoulder, the corner past
the taxiway -- nothing owned the ground and the mesh stood on the DEM, 3-5 m
under the slab (MEASURED CYYZ T: 8-10 m of side a's west corner; the wall
stubs' rim vertices DEM-pinned 162.40-163.27 m beside an edge at 167.55).

THE RULE: for every pack deck with a cut under it (``planar/deck_ring_cut.
cut_decks``) the UNOWNED part of the strip outside each end edge
(``geom/deck_plan.DeckPlan.apron``), ``bank_past_m`` wide and then as far
again as the bank needs to reach the ground -- the larger of ``[design]
bank_min_width_m`` and the deck's estimated height over the DEM along the
edge at ``[zones] old_dem_fill_slope`` -- is the deck's apron:
``deck_apron:<object>#k`` (``graded_strip``, ground), in two pieces noded
on the edge and on its run-on line ``bank_past_m`` out.  Its rows are
``constraints/edge_deck``'s (the run-on band flush with the edge,
``constraints/deck_edge_weld``) and ``constraints/fill_bank``'s (its open
toe on the DEM).  Nothing here names a pack or an airport.
"""
from __future__ import annotations

import typing as _t

from ..geom.deck_end_edge import end_edge
from ..geom.deck_plan import plan, safe_band
from ..model.structures import DECK_APRON_REF

__all__ = ["apron_cells"]


def _apron_depth(db, law, dem_z=None) -> float:
    """How far the apron runs out from the end edge (module doc), m."""
    from ..model.deck_bank import bank_past_m
    past = bank_past_m(law)
    run = float(law.tables.emit.design.bank_min_width_m)
    if dem_z is not None:
        zs = [z for z in (dem_z(p) for p in db.ring) if z is not None and z == z]
        if zs:
            gap = float(db.deck_z) - min(zs)
            run = max(run, gap / float(law.tables.zones.adjacent_ground.old_dem_fill_slope))
    return past + run


def apron_cells(decks: _t.Sequence, tunnels: _t.Sequence, law, taken, cell_of,
                dem_z=None) -> list:
    """The apron cells (module doc) of every cut pack deck, each piece the
    part of the strip ``taken`` (the owned plan) does not hold;
    ``cell_of(ref, polygon)`` mints one cell."""
    from shapely.ops import unary_union

    from ..geom.fixed_overlay import canonical_union, fixed_difference, is_hairline
    from ..geom.parts import polygon_parts_with_area
    from ..model.deck_bank import bank_past_m
    from .deck_ring_cut import cut_decks
    spacing = float(law.tables.emit.identity.min_distinct_spacing_m)
    past = bank_past_m(law)
    out: list = []
    for db in cut_decks(decks, tunnels):
        ea, eb = (end_edge(db.ring, st) if len(st) else [] for st in (db.seats_a, db.seats_b))
        dp = plan(db.ring, ea, eb, safe_band(law))
        if dp is None:
            continue
        depth = _apron_depth(db, law, dem_z)
        k = 0
        for side in (0, 1):
            near = dp.apron(side, past)
            far = dp.apron(side, depth).difference(near).buffer(0.0)
            for piece in (near, far):
                if piece.is_empty:
                    continue
                free = [q for q in polygon_parts_with_area(fixed_difference(piece, taken))
                        if not is_hairline(q, spacing)]
                for q in free:
                    out.append(cell_of(f"{DECK_APRON_REF}:{db.object_id}#{k}", q))
                    k += 1
                if free:
                    taken = canonical_union([taken, unary_union(free)])
    return out
