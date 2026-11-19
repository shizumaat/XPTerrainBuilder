"""GENERATED DECKS AND THEIR NEIGHBOURS (issue #2181; owner sim read
2026-11-19T14:03Z / 14:33Z, KPHX and KIAH; KORD I-190 and KRDU north with
the pack's frame hidden, RULINGS 2026-11-19m (2)).

Two rules, both read after ``planar/deck_generated`` has its pieces:

1. SIDE BY SIDE, ONE CUT (:func:`one_cut`).  Two generated decks over one
   mapped road whose rings stand closer than their two banks' runs (each
   deck's floor depth over the bank slope under a bridge,
   ``model/deck_bank.deck_bank_slope``: the ground between them cannot
   climb out of one cut and back into the other, let alone carry pavement
   at grade) are ONE cut: the ground between them, over the roads' cut, is
   the decks' approach -- the airside pavement there leaves with their
   rings (``carried_off``, the object stage's page clip), so the structure
   pass pairs the two decks (``structure_overlap.deck_partner``: no
   airside pavement between) and the floor runs level from one to the
   other.  Farther apart, pavement between them is the taxiway's own and
   each deck is its own cut (RULINGS 2026-10-29 Q271 b, kiahdeck).
   MEASURED KPHX (33.4354, -112.0047): the pack's page ``dsf:pol91`` over
   the 8 m between the two taxiway bridges' rings held the ground at
   taxiway level there ("raised terrain between").
2. A ROAD BESIDE A TAXIWAY DECK RIDES IT, OR GETS ITS OWN
   (:func:`riders`; owner 14:33Z "If the service road is very close like
   at KPHX, it rides the same bridge, if the gap is larger like at KIAH,
   it gets its own bridge").  A generated road bridge over a road the deck
   covers whose carriageway stands within ``2 x [deck_gen] edge_margin_m``
   of the deck's carried pavement rides the deck: each ring stands
   ``edge_margin_m`` outside its own pavement, so at that gap the two
   rings meet and no ground stands between them -- the deck widens to
   carry the road and the road bridge is not built on its own.  Farther
   off it is its own narrow deck (``pipeline/road_deck``).

3. ONE MAPPED BRIDGE, ONE DECK (:func:`one_bridge`).  The pieces of the
   ring over the roads under ONE mapped aeroway bridge
   (``structure_underpass.aeroway_decks``: OSM states one structure) are
   one deck: the ground between two roads under it is the deck's floor,
   never a bank standing up to the taxiway between two cuts.  MEASURED
   KPHX: the east bridge ``-206`` read three pieces (over ``-3935``,
   ``-5346``, ``-4247`` / ``-2223``) with the ground at taxiway level
   between them.

Nothing here names an airport.  Build-time impact: a pairwise ring test
over the generated decks (a handful) and one buffer per road.
"""
from __future__ import annotations

import dataclasses as _dc
import math
import typing as _t

from shapely.geometry import LineString, Polygon
from shapely.ops import unary_union

__all__ = ["one_cut", "one_bridge", "riders", "rider_gap_m", "pair_gap_m"]


def pair_gap_m(a, b, law) -> float:
    """The widest gap two decks are one cut across (rule 1): their banks'
    runs, each floor's depth over the bank slope under a bridge."""
    from ..model.deck_bank import deck_bank_slope
    return (float(a.floor_min_m) + float(b.floor_min_m)) / deck_bank_slope(law)


def rider_gap_m(law) -> float:
    """The widest gap a road bridge rides a deck across: two rings each
    ``[deck_gen] edge_margin_m`` outside their pavement meet (rule 2)."""
    return 2.0 * float(law.tables.structures.deck_gen.edge_margin_m)


def _poly(ring) -> Polygon:
    p = Polygon(ring)
    return p if p.is_valid else p.buffer(0.0)


def _dir(ln: LineString) -> tuple[float, float]:
    (x0, y0), (x1, y1) = ln.coords[0], ln.coords[-1]
    n = math.hypot(x1 - x0, y1 - y0) or 1.0
    return (x1 - x0) / n, (y1 - y0) / n


def _carries(ln: LineString, d) -> bool:
    """``ln`` runs ON one of the roads deck ``d`` covers: it meets that
    road's line and runs along it (``structure_approach.PARALLEL_COS``) --
    never a road running beside the taxiway past both decks."""
    from .structure_approach import PARALLEL_COS
    u = _dir(ln)
    for _id, _tags, coords in getattr(d, "covered", ()) or ():
        if len(coords) < 2:
            continue
        c = LineString(coords)
        v = _dir(c)
        if ln.distance(c) < 0.5 and abs(u[0] * v[0] + u[1] * v[1]) >= PARALLEL_COS:
            return True
    return False


def one_cut(decks: _t.Sequence, roads: _t.Sequence, law,
            reach_of: _t.Callable[[_t.Mapping], float]) -> tuple[list, list[str]]:
    """``(decks, notes)``: ``decks`` (generated) with the ground between
    every pair standing side by side over one mapped road (rule 1) added to
    both decks' ``approach``.  ``roads``: the mapped road ways;
    ``reach_of(tags)``: a road's cut reach either side of its axis (the
    carriageway, the floor's shoulder and the bank's run,
    ``deck_generated._cut_reach``)."""
    if len(decks) < 2:
        return list(decks), []
    rings = [_poly(d.ring) for d in decks]
    lines = [(LineString(w.points), w) for w in roads if len(w.points) >= 2]
    extra: dict[int, list] = {}
    notes: list[str] = []
    for i in range(len(decks)):
        for j in range(i + 1, len(decks)):
            a, b = rings[i], rings[j]
            gap, gap_max = a.distance(b), pair_gap_m(decks[i], decks[j], law)
            if gap <= 0.0 or gap > gap_max:
                continue
            both = [(ln, w) for ln, w in lines if ln.intersects(a) and ln.intersects(b)
                    and _carries(ln, decks[i]) and _carries(ln, decks[j])]
            if not both:
                continue
            band = unary_union([ln.buffer(reach_of(w.tags or {}), cap_style="flat")
                                for ln, w in both])
            between = unary_union([a, b]).convex_hull.difference(a.union(b)).intersection(band)
            parts = [q for q in getattr(between, "geoms", [between])
                     if q.geom_type == "Polygon" and q.area > 1.0]
            if not parts:
                continue
            for k in (i, j):
                extra.setdefault(k, []).extend(parts)
            notes.append(f"generated decks {decks[i].object_id} and {decks[j].object_id} "
                         f"stand {gap:.1f} m apart over "
                         + ", ".join(sorted({str(w.id) for _ln, w in both})[:6])
                         + f" (within their banks' runs {gap_max:.0f} m): ONE cut, "
                           f"{sum(q.area for q in parts):,.0f} m2 between them leave the "
                           f"pavement with their rings (#2181 item 1)")
    out = []
    for k, d in enumerate(decks):
        add = tuple(tuple(q.exterior.coords[:-1]) for q in extra.get(k, ()))
        out.append(_dc.replace(d, approach=tuple(d.approach) + add) if add else d)
    return out, notes


def riders(piece: Polygon, carried, covered_ids: _t.AbstractSet[str],
           bridges: _t.Sequence[_t.Mapping], law) -> tuple[Polygon, tuple[str, ...], list[str]]:
    """``(piece widened, the riding road bridges' ids, notes)`` (rule 2):
    ``carried`` the taxi / runway pavement the deck piece carries;
    ``covered_ids`` the ids of the roads it covers; ``bridges`` the
    generated road bridge records (``Airport.road_bridges``)."""
    g = law.tables.structures.deck_gen
    lim = rider_gap_m(law)
    ids: list[str] = []
    notes: list[str] = []
    grown = [piece]
    for b in bridges:
        if not set(map(str, b.get("over") or ())) & covered_ids:
            continue
        axis = b.get("axis_xy") or ()
        if len(axis) < 2:
            continue
        road = LineString(axis).buffer(float(b.get("half_m") or 0.0) or 0.01, cap_style="flat")
        gap = road.distance(carried) if carried is not None and not carried.is_empty \
            else road.distance(piece)
        if gap > lim:
            notes.append(f"road bridge {b['id']} stands {gap:.1f} m off the deck's pavement "
                         f"(over {lim:g} m, 2 x edge_margin_m): its own deck (#2183 item 5)")
            continue
        ids.append(str(b["id"]))
        grown.append(road.buffer(float(g.edge_margin_m), join_style="mitre"))
        notes.append(f"road bridge {b['id']} stands {gap:.1f} m off the deck's pavement "
                     f"(within {lim:g} m, 2 x edge_margin_m): it rides the deck (#2181 item 1)")
    if len(grown) == 1:
        return piece, (), notes
    u = unary_union(grown)
    u = u if u.geom_type == "Polygon" else u.convex_hull
    return Polygon(u.exterior), tuple(ids), notes


def one_bridge(R, aero: _t.Sequence[LineString]):
    """``R`` (the generated ring, one polygon per deck piece) with the
    pieces each mapped aeroway bridge line ``aero`` runs over joined into
    their hull (rule 3); ``R`` unchanged where no bridge holds two."""
    pieces = [q for q in getattr(R, "geoms", [R]) if q.geom_type == "Polygon"]
    if len(pieces) < 2 or not aero:
        return R
    parent = list(range(len(pieces)))

    def root(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i
    for a in aero:
        hit = [k for k, q in enumerate(pieces) if q.intersects(a)]
        for k in hit[1:]:
            parent[root(k)] = root(hit[0])
    groups: dict[int, list] = {}
    for k, q in enumerate(pieces):
        groups.setdefault(root(k), []).append(q)
    if len(groups) == len(pieces):
        return R
    return unary_union([unary_union(g).convex_hull if len(g) > 1 else g[0]
                        for g in groups.values()])
