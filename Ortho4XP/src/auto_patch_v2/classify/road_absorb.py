"""Spec §56 (2) THE NEAR ROAD IS THE PAD (owner RULINGS 2026-10-07a (6):
"service roads right next to the building don't need their own shape
because they have to be graded like the pad anyway"; issue #452).

ONE function, called ONCE at the end of ``roles.classify`` — after
``mint_osm_ribbons`` (so both road populations exist: the 1206 ``route*``
corridor faces and the ``small_roads:*`` ribbons) and before
``mint_gap_pieces`` (so the gap sheet differences the final standing
union).  It reads the cells list only, by ROLE, never by a ref's spelling.

A groundside road cell with at least :data:`ABSORB_MIN_FRACTION` of its
area inside a pad's ``pad_road_absorb_m`` round buffer is unioned into
that pad and the pad is re-closed and re-straightened with the SAME
``geom.simplified_outline`` the cluster outline was drawn with, so the
stand-off the set-back had opened between the two fills.  A road that
passes by keeps its shape and its law.  NEVER absorbed (§56 (2) 4): a road
over a mapped bore (the caller's ``keep_out``); a ramp role is not a
road-family role and is never a candidate.  A route the §47 wall extension
lengthened IS absorbed (the terminal's own base walls retain it: it is the
road next to the building).

§56 (2) 8: the re-close takes NO AIRSIDE and NO DECK SHADE — what the
closing added over an airside cell or a welded deck's shade is clipped
back off, so the grown rim differs from the old one only over the absorbed
roads and the bare ground between them.  :data:`ABSORB_GROWTH` names where
the added area went.
"""
from __future__ import annotations

import dataclasses as _dc
import typing as _t

from shapely.geometry import LineString, Polygon
from shapely.ops import unary_union
from shapely.strtree import STRtree

from ..airport.deck_signature import is_tunnel_way
from ..geom.cluster_outline import simplified_outline
from ..geom.parts import nonempty_polygon_parts as polygon_parts
from ..law import Law
from ..law.tables import PadOutline, family

__all__ = ["ABSORB_GROWTH", "ABSORB_MIN_FRACTION", "ROADS_ABSORBED",
           "ROADS_KEPT", "absorb_near_roads", "structure_keep_out"]

#: §56 (2) 2: "EVERY point within" read as this share of the cell's area
#: inside the buffer — the 2 % is the kerb noise of the cut.
ABSORB_MIN_FRACTION = 0.98

#: pad ref -> the road refs it absorbed this pass, in mint order (the
#: sidecar's ``cluster_pads[].roads_absorbed``).
ROADS_ABSORBED: dict[str, list[str]] = {}
#: ``(road ref, pad ref, reason)`` per near road a §56 (2) 4 rule kept.
ROADS_KEPT: list[tuple[str, str, str]] = []

#: pad ref -> the m² the re-close added, by what it lies on (§56 (2) 8,
#: the sidecar's ``absorb_growth_m2``): ``road`` + ``fill`` is the pad's
#: growth, ``shade_clipped`` + ``airside_clipped`` what the clip took back.
ABSORB_GROWTH: dict[str, dict[str, float]] = {}

KEPT_STRUCTURE = "structure_footprint"
KEPT_PIECES = "pad_not_one_polygon"
KEPT_CLIPPED = "over_airside_or_deck_shade"


def structure_keep_out(airport, law: Law):
    """§56 (2) 4 (a): the ground a mapped BORE takes — every OSM way the
    structure pass admits as a tunnel (``deck_signature.is_tunnel_way``
    with ``tunnel.admitted_values``, the predicate ``planar/structures``
    reads), buffered by its default carriageway half width plus the rim
    (``wall_gap_m + wall_band_width_m``).  ``None`` when there is none."""
    tn = law.tables.structures.tunnel
    half = 0.5 * float(tn.default_lanes) * float(tn.lane_width_m) \
        + float(tn.wall_gap_m) + float(tn.wall_band_width_m)
    lines = [LineString(w.points)
             for w in (getattr(airport, "osm_ways", ()) or ())
             if len(w.points) >= 2 and is_tunnel_way(w.tags, tn.admitted_values)]
    return unary_union([ln.buffer(half) for ln in lines]) if lines else None


def _poly(c) -> Polygon:
    return Polygon(c.ring, c.holes)


def _growth(pad: Polygon, closed: Polygon, roads, shades, airside
            ) -> tuple[Polygon, dict[str, float], Polygon]:
    """§56 (2) 8: ``closed`` (the re-closed pad) with what it ADDED over a
    deck shade or an airside cell clipped back, and the added area split
    into ``road / shade_clipped / airside_clipped / fill`` (they sum to
    the added area).  Only the growth is cut, never the pad it grew from.
    A scrap of closing fill the clip left DETACHED from the pad is bare
    ground again (never a second pad piece, never counted); a detached
    ROAD is the caller's to keep (the result is then not one polygon).
    Third: the clip itself (what was taken back)."""
    added = closed.difference(pad)
    on_shade = added.intersection(shades) if shades is not None else Polygon()
    rest = added.difference(shades) if shades is not None else added
    on_air = rest.intersection(airside) if airside is not None else Polygon()
    clip = unary_union([g for g in (on_shade, on_air) if not g.is_empty])
    out = closed.difference(clip) if not clip.is_empty else closed
    parts = polygon_parts(out)
    if len(parts) > 1:
        main = max(parts, key=lambda q: q.intersection(pad).area)
        stray = [q for q in parts if q is not main
                 and q.intersection(roads).area <= (1.0 - ABSORB_MIN_FRACTION) * q.area]
        if stray:
            out = unary_union([q for q in parts if not any(q is t for t in stray)])
    kept = out.difference(pad)
    road = kept.intersection(roads).area
    return out, {"road": road, "shade_clipped": on_shade.area,
                 "airside_clipped": on_air.area, "fill": kept.area - road}, clip


def _absorb(pad: Polygon, rpolys: list, take: list[int], outline: PadOutline,
            other_pads, shades, air, air_tree
            ) -> "tuple[Polygon | None, dict[str, float], list[int], dict[int, str]]":
    """``(grown pad, growth, the roads taken, {road: why kept})`` for one pad and its
    candidate roads — re-closed, the neighbouring pads differenced, rule
    8's clip applied.  A road the clip leaves OFF the pad (across an apron
    tongue with no ground joining it) is dropped from the take and the
    close re-run without it; ``None`` when nothing is left to take or the
    result is still not ONE valid polygon."""
    take = list(take)
    kept: dict[int, str] = {}
    while take:
        taken = unary_union([rpolys[k] for k in take])
        g = simplified_outline(unary_union([pad, taken]), outline.close_m,
                               outline.chord_m, outline.hole_min_m2)
        near = [q for q in other_pads if q.distance(g) <= 0.0]
        if near:                     # the close never takes another pad's ground
            g = g.difference(unary_union(near))
        if g.geom_type != "Polygon" or g.is_empty or not g.is_valid:
            return None, {}, [], {**kept, **dict.fromkeys(take, KEPT_PIECES)}
        hit = ([air[int(k)] for k in air_tree.query(g, predicate="intersects")]
               if air_tree is not None else [])
        g, growth, clip = _growth(pad, g, taken, shades,
                                  unary_union(hit) if hit else None)
        one = g.geom_type == "Polygon" and not g.is_empty and g.is_valid
        slack = 1.0 - ABSORB_MIN_FRACTION
        # a road the clip CUT (it runs over airside or under a deck's shade:
        # folding it in would leave that stretch with no cell) …
        off = {k: KEPT_CLIPPED for k in take
               if rpolys[k].intersection(clip).area > slack * rpolys[k].area}
        if not one:
            # … or left across the clip from the pad, is not this pad's
            main = max(polygon_parts(g), key=lambda q: q.intersection(pad).area)
            off.update((k, KEPT_PIECES) for k in take if k not in off
                       and rpolys[k].intersection(main).area
                       < ABSORB_MIN_FRACTION * rpolys[k].area)
        if not off:
            if one:
                return g, growth, take, kept
            return None, {}, [], {**kept, **dict.fromkeys(take, KEPT_PIECES)}
        kept.update(off)
        take = [k for k in take if k not in off]
    return None, {}, [], kept


def absorb_near_roads(cells: list, law: Law, outline: PadOutline, *,
                      keep_out=None, shades=None
                      ) -> tuple[list, dict[str, list[str]]]:
    """The cells with every near road folded into its pad, and ``pad ref
    -> [road refs]``.  ``shades`` is the SAME ``geom.deck_shades`` union the
    mint subtracted (rule 8).  A pad that absorbs nothing keeps its cell
    object (and every other cell keeps its ring), so the cells pass is
    identical there by construction; ids stay positional."""
    ROADS_ABSORBED.clear()
    ROADS_KEPT.clear()
    ABSORB_GROWTH.clear()
    reach = float(outline.road_absorb_m)
    if reach <= 0.0:
        return cells, {}
    road_roles = set(family(law, "road_cross_section").roles)
    roads = [i for i, c in enumerate(cells)
             if c.role in road_roles and c.side == "groundside"]
    pads = [i for i, c in enumerate(cells) if c.role == "building"]
    if not roads or not pads:
        return cells, {}
    rpolys = [_poly(cells[i]) for i in roads]
    tree = STRtree(rpolys)
    ppolys = {i: _poly(cells[i]) for i in pads}
    air = [_poly(c) for c in cells if c.side == "airside" and c.role != "building"]
    air_tree = STRtree(air) if air else None
    if shades is not None and shades.is_empty:
        shades = None
    grown: dict[int, Polygon] = {}
    gone: set[int] = set()
    for i in pads:
        band = ppolys[i].buffer(reach)
        take: list[int] = []
        for k in sorted(int(k) for k in tree.query(band, predicate="intersects")):
            rp = rpolys[k]
            if roads[k] in gone or rp.area <= 0.0 or \
                    rp.intersection(band).area < ABSORB_MIN_FRACTION * rp.area:
                continue
            if keep_out is not None and rp.intersects(keep_out):
                ROADS_KEPT.append((cells[roads[k]].ref, cells[i].ref, KEPT_STRUCTURE))
                continue
            take.append(k)
        if not take:
            continue
        g, growth, take, kept = _absorb(
            ppolys[i], rpolys, take, outline,
            [grown.get(j, ppolys[j]) for j in pads if j != i],
            shades, air, air_tree)
        ROADS_KEPT.extend((cells[roads[k]].ref, cells[i].ref, why)
                          for k, why in sorted(kept.items()))
        if g is None:
            continue
        grown[i] = g
        gone.update(roads[k] for k in take)
        ROADS_ABSORBED[cells[i].ref] = [cells[roads[k]].ref for k in take]
        ABSORB_GROWTH[cells[i].ref] = growth
    if not grown:
        return cells, {}
    out = []
    for i, c in enumerate(cells):
        if i in gone:
            continue
        if i in grown:
            g = grown[i]
            c = _dc.replace(c, ring=tuple(g.exterior.coords)[:-1],
                            holes=tuple(tuple(h.coords)[:-1] for h in g.interiors),
                            evidence=dict(c.evidence, roads_absorbed=float(
                                len(ROADS_ABSORBED[c.ref]))))
        out.append(c)
    return [c if c.id == n else _dc.replace(c, id=n) for n, c in enumerate(out)], \
        {k: list(v) for k, v in ROADS_ABSORBED.items()}
