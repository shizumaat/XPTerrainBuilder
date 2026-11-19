"""A PAD STANDS ONLY WHERE THE BUILDING TOUCHES THE GROUND (owner RULINGS
2026-11-19l; KPHX Terminal 3, 33.435031, -112.008786).

Owner 2026-11-19T04:56Z: "we should not draw the building pad over the
roads, the pad should only be where the buildings actually touch the
ground, so roads and rails can pass underneath at their grade ... The pads
should be under the 'feet' ground touching walls and floors of the
building."  MEASURED at KPHX (1.0.561): the Terminal 3 pad (``building22``,
37,868 m2) is the OSM ``aeroway=terminal`` outline, which takes in the sky
bridges over the curbside roads -- the pack draws those as terminal-kit
``levels`` facades whose walls stop 3.83 m over the ground -- and the
roads under them (``tunnel=building_passage`` and plain at-grade ways) were
held off the pad or lifted onto it.

THE RULE, at the pad's ONE derivation site (``classify/evidence._pads``,
before the jetways join and the refs are minted, so every pad consumer
inherits it), read from geometry and tags only, never names:

* THE GROUND PLAN -- what of the pack stands on the ground: every plan part
  carrying ground FEET (``model.rebake.Part.feet``: its lowest solid within
  the ground band of its seat), every footless part under a storey
  (``[placement] chain_min_height_m``, 2.5 m -- 18h's own storey -- over
  its unit's ground floor; MEASURED KPHX: the garages' 80,815 m2 deck
  slabs stand 2.0 m over their columns' feet, no road passes under 2 m and
  the pad keeps the ground from rising into them) and every roofed facade
  whose walls reach lower (``FacadeRead.base_m``), closed at
  ``[placement] footprint_touch_m`` with its courts filled.
* THE LIFTED FACADES -- every roofed facade whose walls stop a storey or
  more over the ground (a terminal kit's ``levels`` / ``bridge`` facade,
  read off its file): open ground under its whole plan.
* THE PASSAGES -- every mapped at-grade road of a ribbon class
  (``osm_roads.ribbon_highways``) but a parking aisle (``service=
  parking_aisle``: a garage's own floor) and every at-grade railway
  (``osm_roads.railways``; never a bridge, an admitted bore or a cutting,
  ``pad_cut_corridor``'s), as its ribbon (``airport/road_ways``) grown by
  the groundside cut-back every road receives -- where it runs UNDER a
  building: all of it for a way mapped through one (``tunnel=
  building_passage``, ``covered=yes``), else the stretch under a lifted
  piece (a lifted facade, or a footless OBJ part a storey up) or under a
  mapped building outline of a higher ``layer`` (KPHX's ``Terminal 3`` is
  ``layer=4`` over its curbside roads).  A road merely drawn across a
  footprint at the same layer is not read as passing under it (MEASURED:
  read so, OTHH lost 125,000 m2 of pad, OMDB's 54 pads broke into 107).

Every pad part loses (lifted facades | passages) less the ground plan.  So
a lifted facade adds no pad; a road under a lifted piece -- or through a
footprint the pack does not stand on -- keeps its own ground and is
ribboned through unbroken (14m (1) "a road passing under a bridge stays on
the ground", 18j (2) "a mapped at-grade road through the footprint keeps
its own ground", now for every pad); a building on its feet keeps its pad.

A footless OBJ part a storey up is NOT read as open ground on its own: the
plan's part rings carry no vertical wall (a wall's triangles stand on edge
and project to no area), so a roof cannot be told from a bridge by them --
MEASURED KBNA, read so: a hangar roof (``part1`` +18.6 m) stood on its walls
(``part2``, 21.1 m tall) along 0.24 of its edge, and 126,000 of the airport's
390,470 m2 of pad left.  Such parts give the passages under them their
clearance and nothing else; the passages themselves carry the rule.

Reads with 18h (a connector between two seats is warped, its feet are the
seats'), 19f (an interior deck rides its building: it is never lifted
ground) and 19j (the terrain absorbs within 0.5 m): none of them derives a
pad.  The clearance under each lifted piece over a passage is reported
(``[building_pad] passage_clearance_road_m`` / ``_rail_m``).
"""
from __future__ import annotations

import typing as _t

from shapely.geometry import LineString, Polygon
from shapely.ops import unary_union

__all__ = ["GROUND_TRIMMED", "PASSAGE_NOTES", "ground_plan", "passages",
           "trim_to_ground"]

#: the last run's counts: pad parts trimmed, m2, lifted pieces, passages
GROUND_TRIMMED: dict[str, float] = {}
#: one line per passage under a lifted piece, with its clearance
PASSAGE_NOTES: list[str] = []


def _ring(ring, to_xy) -> Polygon | None:
    if len(ring) < 3:
        return None
    g = Polygon([to_xy(lo, la) for la, lo in ring])
    if not g.is_valid:
        g = g.buffer(0.0)
    return None if g.is_empty else g


def _facade_polys(airport, storey_m: float):
    """``(ground, lifted)``: each roofed facade's outline and, for a lifted
    one, ``(polygon, its base over its ground)``."""
    from ..airport.facade import PARKING_STRUCTURE, ROOFED
    ground, lifted = [], []
    for b in getattr(airport, "buildings", ()) or ():
        fr = getattr(b, "facade", None)
        if fr is None or fr.cls not in (ROOFED, PARKING_STRUCTURE):
            continue
        try:
            g = Polygon(b.outer, b.holes)
        except (ValueError, TypeError):
            continue
        if not g.is_valid:
            g = g.buffer(0.0)
        if g.is_empty:
            continue
        base = getattr(fr, "base_m", None)
        if base is not None and float(base) >= storey_m:
            lifted.append((g, float(base)))
        else:
            ground.append(g)
    return ground, lifted


def ground_plan(airport, law):
    """``(ground, facades, over)`` (module doc): the ground plan as one
    closed, court-filled geometry (or ``None``), the lifted facades and the
    footless OBJ parts a storey up, each as ``[(polygon, lift, m)]``."""
    st = law.tables.structures
    storey_m = float(st.placement.chain_min_height_m)
    touch = float(st.placement.footprint_touch_m)
    ground, facades = _facade_polys(airport, storey_m)
    over = []
    part = getattr(airport, "partition", None)
    to_xy = airport.frame.entry()
    for u in (getattr(part, "units", ()) or ()) if part is not None else ():
        live = [q for m in u.members for q in m.parts
                if not q.line and not getattr(q, "scatter", False) and q.rings]
        # the unit's ground floor: its lowest footed part, never under its
        # zero (a pier's buried foot is not the floor -- MEASURED KPHX:
        # garage piers founded at -8 m under decks at +2 m)
        floor = max(0.0, min((float(q.base_y) for q in live if q.feet), default=0.0))
        for q in live:
            gs = [g for g in (_ring(r, to_xy) for r in q.rings) if g is not None]
            lift = float(q.base_y) - floor
            if q.feet or lift < storey_m:
                ground.extend(gs)
            else:
                over.extend((g, lift) for g in gs)
    g = unary_union(ground) if ground else None
    if g is not None and touch > 0.0:
        g = g.buffer(touch, join_style=2).buffer(-touch, join_style=2)
    if g is not None:
        g = unary_union([Polygon(p.exterior) for p in getattr(g, "geoms", [g])
                         if p.geom_type == "Polygon" and not p.is_empty])
        if g.is_empty:
            g = None
    return g, facades, over


def passages(airport, law, rules) -> list[tuple[_t.Any, Polygon, str]]:
    """``[(way, corridor, "road" | "rail")]`` (module doc)."""
    from ..airport.deck_signature import is_bridge_way, is_tunnel_way
    from ..airport.road_ways import mapped_width_m, ribbon_half_width_m, road_ways
    from .pad_cut_corridor import _is_cutting
    tn = law.tables.structures.tunnel
    admitted = tuple(tn.admitted_values)
    cut = float(law.tables.zones.adjacent_ground.groundside_cutback_m)
    orr = getattr(rules, "osm_roads", None)       # a rules stub reads none
    ways = getattr(airport, "osm_ways", ()) or ()
    out = []
    classes = set(getattr(orr, "ribbon_highways", ()) or ())
    for w, ln in road_ways(ways):
        tags = w.tags or {}
        if (tags.get("highway") in classes and tags.get("service") != "parking_aisle"
                and not _is_cutting(tags, admitted)):
            half = ribbon_half_width_m(tags, law) + cut
            out.append((w, ln.buffer(half, cap_style="flat"), "road"))
    rails = set(getattr(orr, "railways", ()) or ())
    for w in ways:
        tags = getattr(w, "tags", None) or {}
        if (tags.get("railway") not in rails or len(w.points) < 2
                or is_bridge_way(tags) or is_tunnel_way(tags, admitted)
                or _is_cutting(tags, admitted)):
            continue
        half = 0.5 * mapped_width_m(tags, tn.lane_width_m, tn.default_lanes) + cut
        out.append((w, LineString(w.points).buffer(half, cap_style="flat"), "rail"))
    return out


def _layer(tags) -> int:
    try:
        return int(str((tags or {}).get("layer", "0")).strip() or 0)
    except ValueError:
        return 0


def _layered_buildings(airport) -> list[tuple[Polygon, int]]:
    """Every mapped building outline (``building=*`` or ``aeroway=terminal``)
    with its ``layer``: a way of a lower layer crossing it passes under it."""
    out = []
    for w in getattr(airport, "osm_ways", ()) or ():
        tags = getattr(w, "tags", None) or {}
        b = str(tags.get("building", "")).strip().lower()
        if not ((b and b != "no") or tags.get("aeroway") == "terminal"):
            continue
        if not getattr(w, "closed", False) or len(w.points) < 4:
            continue
        g = Polygon(w.points)
        if not g.is_valid:
            g = g.buffer(0.0)
        if not g.is_empty:
            out.append((g, _layer(tags)))
    return out


def _under(w, corridor, lifted, above):
    """The stretch of ``corridor`` the way runs UNDER a building on (module
    doc): all of it for a way mapped through one (``tunnel=
    building_passage``, ``covered=yes``), else what lies under a lifted
    piece or under a mapped building of a higher ``layer``; ``None``."""
    from .pad_cut_corridor import _is_covered
    tags = getattr(w, "tags", None) or {}
    if _is_covered(tags):
        return corridor
    lw = _layer(tags)
    over = [g for g, lb in above if lb > lw and g.intersects(corridor)]
    if lifted is not None and not lifted.is_empty and lifted.intersects(corridor):
        over.append(lifted)
    if not over:
        return None
    u = corridor.intersection(unary_union(over))
    return None if u.is_empty or u.area <= 0.0 else u


def _clearance_notes(ways, over, open_, bp) -> list[str]:
    """One line per passage that left a pad under a lifted piece: the
    lowest lift over the stretch it left, flagged under the law's
    clearance."""
    lim = {"road": float(getattr(bp, "passage_clearance_road_m", 0.0) or 0.0),
           "rail": float(getattr(bp, "passage_clearance_rail_m", 0.0) or 0.0)}
    out = []
    for w, corr, kind in ways:
        cut = corr.intersection(open_)
        if cut.is_empty:
            continue
        lo = min((lift for g, lift in over if g.intersects(cut)), default=None)
        if lo is None:
            continue
        tags = getattr(w, "tags", None) or {}
        flag = " LOW" if lim[kind] > 0.0 and lo < lim[kind] else ""
        out.append(f"pad passage: {kind} {getattr(w, 'id', '?')} "
                   f"({tags.get('highway') or tags.get('railway')}) passes under a "
                   f"lifted building piece at its own grade, clearance {lo:.2f} m{flag}")
    return out


def trim_to_ground(parts: list, airport, law, rules) -> list:
    """Every pad part less (lifted facades | passages) less the ground plan
    (module doc; geometry only, the caller splits and mints)."""
    GROUND_TRIMMED.clear()
    PASSAGE_NOTES.clear()
    if law is None or not parts or airport is None:
        return parts
    pads = unary_union(parts)
    ground, facades, over = ground_plan(airport, law)
    facades = [(g, z) for g, z in facades if g.intersects(pads)]
    ways = [(w, c, k) for w, c, k in passages(airport, law, rules) if c.intersects(pads)]
    if not facades and not ways:
        return parts
    lifted = unary_union([g for g, _z in over + facades if g.intersects(pads)])
    above = _layered_buildings(airport)
    under = [_under(w, c, lifted, above) for w, c, _k in ways]
    ways = [(w, c, k) for (w, c, k), u in zip(ways, under) if u is not None]
    open_ = unary_union([g for g, _z in facades] + [u for u in under if u is not None])
    if open_.is_empty:
        return parts
    if ground is not None:
        open_ = open_.difference(ground)
    if open_.is_empty:
        return parts
    out, n, area = [], 0, 0.0
    for p in parts:
        if p.intersects(open_):
            q = p.difference(open_)
            if not q.is_valid:
                q = q.buffer(0.0)
            # polygonal only: a sliver line the difference leaves is no pad
            q = unary_union([g for g in getattr(q, "geoms", [q])
                             if g.geom_type in ("Polygon", "MultiPolygon") and not g.is_empty])
            if q.area < p.area:
                n += 1
                area += p.area - q.area
            if q.is_empty:
                continue
            p = q
        out.append(p)
    GROUND_TRIMMED.update(parts=n, area_m2=round(area, 1),
                          facades=len(facades), passages=len(ways))
    over = [(g, z) for g, z in over + facades if g.intersects(open_)]
    PASSAGE_NOTES.extend(_clearance_notes(ways, over, open_.intersection(pads),
                                          law.tables.structures.building_pad))
    return out
