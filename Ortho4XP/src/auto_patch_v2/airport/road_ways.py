"""THE AT-GRADE ROAD SOURCE — one derivation of the mapped road centrelines
(``planar/terrain_edge.road_lines`` for §19's rim road and §34 (4)'s band
subtraction; ``classify/roles.mint_osm_ribbons`` for the widened road-face
mint, RULINGS 2026-09-30e (1)).  It lives at the ``airport`` layer so
``classify`` may read it (``classify`` never imports ``planar``)."""
from __future__ import annotations

from shapely.geometry import LineString

from .deck_signature import is_bridge_way, is_tunnel_way

__all__ = ["road_ways", "mapped_width_m", "ribbon_half_width_m"]


def mapped_width_m(tags, lane_width_m: float, default_lanes: int) -> float:
    """THE WAY'S MAPPED CARRIAGEWAY WIDTH — the one reading of what the map
    says about a road's width: its ``width`` tag, else ``lanes`` x
    ``lane_width_m`` (``default_lanes`` where neither parses).  The
    structures read it through ``planar/structure_approach.
    carriageway_width_m``; the at-grade ribbon through
    :func:`ribbon_half_width_m`."""
    tags = tags or {}
    w = tags.get("width")
    if w:
        try:
            return max(1.0, float(str(w).replace("m", "").strip()))
        except ValueError:
            pass
    lanes = tags.get("lanes")
    try:
        n = int(lanes) if lanes else int(default_lanes)
    except ValueError:
        n = int(default_lanes)
    return max(1, n) * float(lane_width_m)


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
