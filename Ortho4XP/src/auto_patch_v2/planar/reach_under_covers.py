"""THE COVERS STAND IN THE AIRCRAFT'S WAY (#1717 S1; owner RULINGS 2026-11-03b
Q340 a, 2026-10-19ag; spec ``docs/specs/two-level-regions-20261103.md`` §2.2
step 2 and §15).

19ag: pavement aircraft cannot reach is groundside.  ``reach_after_pads``
reads it per connected PIECE of an apron page once the pads stand, and the
road bridges over the pavement do not stand at all.  MEASURED LFPG (capture
lfpg6): one 191,899 m2 piece of ``dsf:pol459`` runs from the stands round
2A-2D through the gaps between the terminal blocks into the T2 central
corridor, under the layer-1 loops and layer-2 viaducts; its room reaches
the taxiways, so the whole corridor stayed apron at level A.

HERE the read is made again with the COVERS as obstacles: every mapped road
or rail bridge (``deck_signature.is_bridge_way``: an aeroway bridge carries
aircraft and is no cover) of ``layer >= [tunnel] cover_min_layer`` inside
the aerodrome boundary, at its carriageway width.  The room is the airside
pavement less the covers, eroded by the law's default taxiway half-width
(``taxi_half_width_m(law, None)``); a room piece REACHES when its sweep
meets a taxi-family face or a runway (``classify/reachability``'s read).
The unit judged is the pavement the reachable sweep leaves, not the page
piece: on every apron face the covers touch, each connected part outside
that sweep (less its fringe that leads out to the reachable sweep: a slot
between two buildings opening onto the stands stays with the stands) is
BEYOND -- ``<ref>#beyond<k>``, the role
``open_default.unclassified_groundside_role`` names -- when it holds
unreachable room, carries no apt.dat startup, and at least ``[tunnel]
cover_min_share`` of it lies under the covers (a covered lot).

The read runs only where the airport's objects state a level B
(``planar/level_depth.airport_level_b``, handed down by ``planar/build``):
the covered pavement is the lower level's to take, at that depth.  A
covered lot at an airport with no object-stated level B waits for the
region round's depth ladder (spec §3) -- MEASURED: EGLL (2 parts, 13,813 m2)
and KPHX (1 part, 2,653 m2) read covered parts and state no level B.

Nothing downstream is new: ``low_extent.extend_levels`` takes every beyond
piece that meets a group's lower footprint into that group's lower level,
at the objects' bottom (27h), tied to the group's zero.

Nothing here names a pack, a resource or an airport.
"""
from __future__ import annotations

import dataclasses as _dc

from shapely.geometry import LineString, Point
from shapely.ops import unary_union
from shapely.strtree import STRtree

from ..airport.deck_signature import is_bridge_way
from ..geom.parts import nonempty_polygon_parts
from ..law.tables import role_side, taxi_half_width_m
from .structure_approach import carriageway_width_m

__all__ = ["bridge_covers", "covered_beyond"]

#: the faces an aircraft taxis on (``classify/reachability``'s, with the runways)
_TAXI_ROLES = frozenset(("primary_parallel", "secondary_parallel", "stub",
                         "cross_connector", "junction", "runway", "runway_crossing"))


def bridge_covers(airport, law):
    """The plan cover of every mapped road or rail bridge at ``layer >=
    [tunnel] cover_min_layer`` inside the aerodrome boundary, each at its
    carriageway width; ``None`` where there is none."""
    from .viaduct_road import _boundary, _layer
    lo = int(law.tables.structures.tunnel.cover_min_layer)
    gs = [LineString(w.points).buffer(carriageway_width_m(w.tags or {}, law) / 2.0)
          for w in getattr(airport, "osm_ways", ()) or ()
          if len(w.points) >= 2 and is_bridge_way(w.tags or {})
          and _layer(w.tags or {}) >= lo]
    inside = _boundary(airport) if gs else None
    if inside is None:
        return None
    cov = unary_union(gs).intersection(inside)
    return None if cov.is_empty else cov


def covered_beyond(regions: list, law, airport) -> "tuple[list, dict]":
    """``(regions, counts)``: ``regions`` with every covered apron part aircraft
    cannot reach once the covers stand made groundside (module docstring)."""
    cov = bridge_covers(airport, law)
    if cov is None:
        return regions, {}
    aprons = [i for i, r in enumerate(regions) if r.role == "apron" and r.source == "cell"
              and r.polygon is not None and r.polygon.intersects(cov)]
    r0 = taxi_half_width_m(law, None)
    if not aprons or not r0 or r0 <= 0.0:
        return regions, {}
    reach, unreach = _room(regions, cov, float(r0), law)
    if not unreach:
        return regions, {"covered_beyond": 0}
    swept = unary_union([p.buffer(float(r0)) for p in reach])
    inside = unary_union([p.buffer(float(r0)) for p in unreach])
    utree = STRtree(unreach)
    stands = [Point(s.xy) for s in getattr(airport, "startups", ()) or ()]
    share = float(law.tables.structures.tunnel.cover_min_share)
    pmin = float(law.tables.structures.building_pad.min_area_m2)
    lost: dict[int, list] = {}
    for i in aprons:
        for q in nonempty_polygon_parts(regions[i].polygon.difference(swept)):
            if q.area < pmin or any(q.contains(s) for s in stands):
                continue
            if not any(unreach[int(j)].intersection(q).area > 0.0
                       for j in utree.query(q, predicate="intersects")):
                continue
            if q.intersection(cov).area < share * q.area:
                continue
            q = _core(q, inside, swept, cov, share)
            lost.setdefault(i, []).extend(g for g in nonempty_polygon_parts(q)
                                          if g.area >= pmin)
    return _split(regions, lost, law) if lost else (regions, {"covered_beyond": 0})


def _core(q, inside, swept, cov, share: float):
    """The part ``q`` less its open fringe: the pavement the unreachable room
    sweeps (``inside``), with every other piece of ``q`` that is covered or
    does not touch the reachable sweep (a strip along a wall too narrow for
    the room, the road under the viaduct).  An open slot between two
    buildings leading out onto the stands is the stands' fringe and stays
    with them."""
    core = q.intersection(inside)
    keep = [g for g in nonempty_polygon_parts(q.difference(core))
            if g.distance(swept) > 1e-6 or g.intersection(cov).area >= share * g.area]
    return unary_union([core, *keep]) if keep else core


def _room(regions: list, cov, r0: float, law) -> "tuple[list, list]":
    """``(reaching, unreaching)`` room pieces: the airside pavement less the
    covers, eroded by ``r0``; a piece reaches when its sweep meets a
    taxi-family face or a runway."""
    cells = [r for r in regions if r.source == "cell" and r.polygon is not None
             and not r.polygon.is_empty]
    air = unary_union([r.polygon for r in cells if role_side(law, r.role) == "airside"])
    taxi = unary_union([r.polygon for r in cells if r.role in _TAXI_ROLES])
    weld = float(law.tables.emit.identity.weld_spacing_m)
    pieces = nonempty_polygon_parts(air.buffer(weld).difference(cov).buffer(-(r0 + weld)))
    reach = [p for p in pieces if p.buffer(r0).intersects(taxi)]
    return reach, [p for p in pieces if not p.buffer(r0).intersects(taxi)]


def _split(regions: list, lost: dict, law) -> "tuple[list, dict]":
    """The regions with each face's ``lost`` parts cut out of it and minted
    beside it as groundside ``<ref>#beyond<k>``, numbered after the beyond
    pieces already minted."""
    from ..classify.open_default import unclassified_groundside_role
    from ..classify.rules import load_rules
    from .reach_after_pads import BEYOND
    rules = load_rules()
    taken = {str(r.ref) for r in regions}
    out: list = []
    n, m2 = 0, 0.0
    for i, r in enumerate(regions):
        if i not in lost:
            out.append(r)
            continue
        # one region per part, as the pad cut leaves a page (a consumer
        # reads ``polygon.exterior``)
        out.extend(_dc.replace(r, polygon=q) for q in
                   nonempty_polygon_parts(r.polygon.difference(unary_union(lost[i]))))
        k = 1
        for q in lost[i]:
            while f"{r.ref}{BEYOND}{k}" in taken:
                k += 1
            ref = f"{r.ref}{BEYOND}{k}"
            taken.add(ref)
            role, _evid = unclassified_groundside_role(q, rules, road_reached=False)
            out.append(_dc.replace(r, role=role, ref=ref, polygon=q, side=role_side(law, role)))
            n += 1
            m2 += float(q.area)
    return out, {"covered_beyond": n, "covered_beyond_m2": round(m2, 1)}
