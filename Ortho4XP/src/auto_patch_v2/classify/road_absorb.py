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
over a structure footprint (the caller's ``keep_out``), a ``route`` piece
the §47 retaining-wall extension lengthened (``wall_extended``); a ramp
role is not a road-family role and is never a candidate.
"""
from __future__ import annotations

import dataclasses as _dc
import typing as _t

from shapely.geometry import LineString, Polygon
from shapely.ops import unary_union
from shapely.strtree import STRtree

from ..airport.deck_signature import is_tunnel_way
from ..geom.cluster_outline import simplified_outline
from ..law import Law
from ..law.tables import PadOutline, family

__all__ = ["ABSORB_MIN_FRACTION", "ROADS_ABSORBED", "ROADS_KEPT",
           "absorb_near_roads", "structure_keep_out"]

#: §56 (2) 2: "EVERY point within" read as this share of the cell's area
#: inside the buffer — the 2 % is the kerb noise of the cut.
ABSORB_MIN_FRACTION = 0.98

#: pad ref -> the road refs it absorbed this pass, in mint order (the
#: sidecar's ``cluster_pads[].roads_absorbed``).
ROADS_ABSORBED: dict[str, list[str]] = {}
#: ``(road ref, pad ref, reason)`` per near road a §56 (2) 4 rule kept.
ROADS_KEPT: list[tuple[str, str, str]] = []

KEPT_STRUCTURE = "structure_footprint"
KEPT_WALL = "wall_extended_route"
KEPT_PIECES = "pad_not_one_polygon"


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


def absorb_near_roads(cells: list, law: Law, outline: PadOutline, *,
                      keep_out=None, wall_extended=None
                      ) -> tuple[list, dict[str, list[str]]]:
    """The cells with every near road folded into its pad, and ``pad ref
    -> [road refs]``.  A pad that absorbs nothing keeps its cell object
    (and every other cell keeps its ring), so the cells pass is identical
    there by construction; ids stay positional."""
    ROADS_ABSORBED.clear()
    ROADS_KEPT.clear()
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
            why = ""
            if keep_out is not None and rp.intersects(keep_out):
                why = KEPT_STRUCTURE
            elif wall_extended is not None and rp.intersects(wall_extended) \
                    and rp.intersection(wall_extended).area > 0.0:
                why = KEPT_WALL
            if why:
                ROADS_KEPT.append((cells[roads[k]].ref, cells[i].ref, why))
                continue
            take.append(k)
        if not take:
            continue
        g = simplified_outline(unary_union([ppolys[i]] + [rpolys[k] for k in take]),
                               outline.close_m, outline.chord_m,
                               outline.hole_min_m2)
        # the close never takes another pad's ground
        near = [ppolys[j] if j not in grown else grown[j] for j in pads
                if j != i and ppolys[j].distance(g) <= 0.0]
        if near:
            g = g.difference(unary_union(near))
        if g.geom_type != "Polygon" or g.is_empty or not g.is_valid:
            ROADS_KEPT.extend((cells[roads[k]].ref, cells[i].ref, KEPT_PIECES)
                              for k in take)
            continue
        grown[i] = g
        gone.update(roads[k] for k in take)
        ROADS_ABSORBED[cells[i].ref] = [cells[roads[k]].ref for k in take]
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
