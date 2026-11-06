"""A DECK OVER THE PACK'S CUT ENDS ON ITS TAXIWAY (#1883 round 3 B2; owner
RULINGS 2026-11-04a (16), 2026-11-03e (4)/(6), 2026-10-26d).

A pack that states its own cut as a concave cut shell (``airport/object_
floor``; a floor object's covers are its own tunnel, walls and roof as one,
and stay whole with it) may carry the airport's pavement across it on a HARD
DECK of the same frame (LGAV ``Trench_00``: two pieces 1.6 km apart over
the motorway shell, their zeros 3.1 m apart).  The cut is the floor's — its
footprint owns the ground under the deck (``planar/object_floor_cells``) —
and the deck is seated by its END LINES:

* THE WITNESS is the airport's pavement running ACROSS a deck piece of the
  frame (``airport/airside_deck_seat.facing_contacts``, read as
  ``planar/deck_bridge`` reads it) — never a name; each piece is its own
  deck with its own zero (:class:`airport.object_floor.FloorDeck`);
* THE STATIONS: each end line's stations seat on the map's nearest
  vertices off the cut (``constraints/deck_lines.floor_end_lines``);
* THE ROWS (``constraints/edge_deck``): every station flush with one zero
  of the piece, both end lines held to it by the deck-top difference, the
  pavement under the piece never through it — the taxiway flattens to the
  deck end, the deck never tilts;
* THE SEAT: the object stage seats each piece flush with what it carries
  at its end lines (``airport/cut_deck_seat``, the floor's footprint ring
  its cut).

Nothing here names a pack, a resource or an airport.
"""
from __future__ import annotations

import dataclasses as _dc
import typing as _t

import shapely
from shapely.ops import unary_union

from ..airport.object_floor import SHELL, FloorDeck, ObjectFloor, owns_ground
from ..geom.parts import polygon_parts_with_area
from ..model.planar import ROAD_ROLES

__all__ = ["floor_decks"]


def floor_decks(floors: _t.Sequence[ObjectFloor], objects, cache, classification, airport,
                law) -> tuple[list[ObjectFloor], list[str]]:
    """``(floors, notes)``: each floor owning ground with the hard-deck
    pieces of its frame the pavement drives across (``ObjectFloor.decks``),
    those placements out of its whole-row seats (they are seated by their
    end lines, module doc)."""
    if not floors or classification is None or not classification.cells:
        return list(floors), []
    import types

    from ..airport.airside_deck_seat import facing_contacts
    from .deck_bridge import CellRoles, _end_pair, _plate, _routes_across, _top_at
    step = float(law.tables.structures.bridge.abutment_sample_step_m)
    on = float(law.tables.structures.deck.on_fraction)
    roles = CellRoles(classification, airport)
    surface = types.SimpleNamespace(roles=roles)
    to_xy, to_ll = airport.frame.transformers()
    by_id = {str(o.id): o for o in objects or ()}
    floor_ids = {f.object_id for f in floors}
    out: list[ObjectFloor] = []
    notes: list[str] = []
    for f in floors:
        if f.kind != SHELL or not owns_ground(f):
            # a floor OBJECT's covers are its tunnel (walls and roof as one,
            # EGLL ``2.obj``): written whole with it at its zero
            out.append(f)
            continue
        got: list[FloorDeck] = []
        for pid, _res, zero in f.seats:
            d = by_id.get(pid)
            if (d is None or pid in floor_ids
                    or str(getattr(d, "deck_kind", "") or "") not in ("flag", "signature")
                    or getattr(d, "hard_deck", None) is None or d.hard_deck.is_empty):
                continue
            plate = _plate(cache, [d])
            top = max((y for _x, _y, y in plate), default=0.0)
            for k, piece in enumerate(_pieces(d.hard_deck)):
                if piece.intersection(f.footprint).area < on * piece.area \
                        or not _spans(f, piece, zero + top, law):
                    continue
                ring_ll = [to_ll(x, y) for x, y in piece.exterior.coords[:-1]]
                # the airport's pavement across it, else a road (the deck
                # carries what drives onto it: ``cut_deck_seat.end_ground``)
                pairs = (facing_contacts(ring_ll, surface, step, every=True)
                         or facing_contacts(ring_ll, surface, step, every=True,
                                            carried=lambda r: r in ROAD_ROLES))
                pair = _end_pair(pairs, None, to_xy,
                                 _routes_across(airport, piece) if pairs and len(pairs) > 1
                                 else ())
                if pair is None:
                    continue
                sa, sb = (tuple(to_xy(lo, la) for la, lo in e) for e in pair)
                reach = max(2.0 * step, 3.0)
                got.append(FloorDeck(f"{pid}#{k}", pid, d.path,
                                     tuple(piece.exterior.coords[:-1]), sa, sb,
                                     _top_at(plate, sa, reach, top),
                                     _top_at(plate, sb, reach, top)))
                notes.append(f"{f.id}: deck piece {pid}#{k} {d.path.rsplit('/', 1)[-1]} "
                             f"{piece.area:.0f} m2 over its cut, the pavement across it: seated "
                             f"by its end lines (#1883 r3 B2)")
        if got:
            decked = {g.object_id for g in got}
            f = _dc.replace(f, decks=tuple(got),
                            seats=tuple(s for s in f.seats if s[0] not in decked))
        out.append(f)
    return out, notes


def _pieces(deck) -> list:
    """The deck's pieces, those touching within half a metre ONE piece (B2:
    LGAV ``Trench_00``'s ramp plate beside its road deck rides that deck)."""
    grown = unary_union([p.buffer(0.5, join_style="mitre")
                         for p in polygon_parts_with_area(deck, 1.0)])
    return [q for g in polygon_parts_with_area(grown, 1.0)
            for q in polygon_parts_with_area(g.buffer(-0.5, join_style="mitre"), 1.0)]


def _spans(f: ObjectFloor, piece, top_z: float, law) -> bool:
    """Does the deck piece SPAN the cut — its top ``shell_floor_min_m`` or
    more over the floor under its plan (median)?  A hard surface lying ON
    the floor (the carriageway in the trench, LGAV ``Trench_07`` /
    ``Trench_08``) is the floor's, written at the frame's zero."""
    import numpy as np

    from ..geom.lowest_face import floor_z_at
    q = piece.intersection(f.footprint)
    if q.is_empty:
        return False
    x0, y0, x1, y1 = q.bounds
    step = max(1.0, ((x1 - x0) * (y1 - y0) / 400.0) ** 0.5)
    xs, ys = np.meshgrid(np.arange(x0, x1, step), np.arange(y0, y1, step))
    xs, ys = xs.ravel(), ys.ravel()
    inside = shapely.contains_xy(q, xs, ys)
    if not inside.any():
        return False
    z = floor_z_at(f.faces, xs[inside], ys[inside], edge_m=0.5)
    span = float(law.tables.structures.tunnel.object.shell_floor_min_m)
    return bool(np.isfinite(z).any()) and top_z - float(np.nanmedian(z)) >= span
