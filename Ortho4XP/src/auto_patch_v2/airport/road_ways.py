"""THE AT-GRADE ROAD SOURCE — one derivation of the mapped road centrelines
(``planar/terrain_edge.road_lines`` for §19's rim road and §34 (4)'s band
subtraction; ``classify/roles.mint_osm_ribbons`` for the widened road-face
mint, RULINGS 2026-09-30e (1)).  It lives at the ``airport`` layer so
``classify`` may read it (``classify`` never imports ``planar``)."""
from __future__ import annotations

from shapely.geometry import LineString

from .deck_signature import is_bridge_way, is_tunnel_way

__all__ = ["road_ways"]


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
