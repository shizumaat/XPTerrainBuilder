"""THE AT-GRADE ROAD SOURCE — one derivation of the mapped road centrelines
(``planar/terrain_edge.road_lines`` for §19's rim road and §34 (4)'s band
subtraction; ``classify/roles.mint_osm_ribbons`` for the widened road-face
mint, RULINGS 2026-09-30e (1)).  It lives at the ``airport`` layer so
``classify`` may read it (``classify`` never imports ``planar``)."""
from __future__ import annotations

import typing as _t

from shapely.geometry import LineString

from ..geom.valid_area import valid_area
from ..model.road_clearance import mapped_width_m
from .deck_signature import is_bridge_way, is_tunnel_way

__all__ = ["road_corridors", "road_ways", "mapped_width_m", "ribbon_half_width_m"]


def ribbon_half_width_m(tags, law) -> float:
    """THE AT-GRADE RIBBON'S HALF-WIDTH FROM THE MAP (issue #949): half the
    way's mapped carriageway (:func:`mapped_width_m` at the structures'
    ``[tunnel] lane_width_m`` / ``default_lanes``, the reading every bore,
    deck and channel already makes), never less than the core's levelled
    half-width ``road_profile.lane_width_m``.  A 7-lane way (KBUR's
    Hollywood Way, ``lanes=7``) is 24.5 m, where the core's half-width
    alone ribboned 8 m of it; an untagged or two-lane way keeps the core's
    ribbon unchanged."""
    tn = law.tables.structures.tunnel
    core = float(law.tables.emit.road_profile.lane_width_m)
    return max(core, 0.5 * mapped_width_m(tags, tn.lane_width_m, tn.default_lanes))


def road_ways(osm_ways=()) -> tuple[tuple[object, LineString], ...]:
    """``road_lines`` WITH the way each centreline came from — the one
    at-grade road source, for the consumer that needs the way's class and
    feed (the road-face mint, RULINGS 2026-09-30e (1): a ribbon's ref
    carries its feed, and its class passes ``osm_roads.ribbon_highways``)."""
    out: list[tuple[object, LineString]] = []
    for w in osm_ways or ():
        tags = getattr(w, "tags", None) or {}
        if not tags.get("highway"):
            continue
        if is_tunnel_way(tags) or is_bridge_way(tags):
            continue
        pts = [(float(p[0]), float(p[1])) for p in getattr(w, "points", ())]
        if len(pts) >= 2:
            out.append((w, LineString(pts)))
    return tuple(out)


def road_corridors(P, airport, law) -> list[tuple[_t.Any, float]]:
    """``[(corridor, width)]``: every mapped road's carriageway meeting
    ``P`` -- the way buffered by half its mapped width
    (``airport/road_ways.mapped_width_m`` at the ``[tunnel]`` lane law); a
    bridge's corridor counts (the ground under a bridge is the ground the
    road beneath runs on), a bore never (it runs under the pad)."""
    tn = law.tables.structures.tunnel
    admitted = tuple(tn.admitted_values)
    out = []
    for w in getattr(airport, "osm_ways", ()) or ():
        tags = getattr(w, "tags", None) or {}
        if not tags.get("highway") or len(w.points) < 2 or is_tunnel_way(tags, admitted):
            continue
        width = mapped_width_m(tags, tn.lane_width_m, tn.default_lanes)
        c = LineString(w.points).buffer(0.5 * width, cap_style="flat")
        if c.intersects(P):
            out.append((valid_area(c), float(width)))
    return out
