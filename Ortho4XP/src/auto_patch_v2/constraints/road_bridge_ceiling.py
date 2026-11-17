"""THE LOWER ROAD HOLDS ITS CLEARANCE UNDER A GENERATED ROAD BRIDGE (owner
2026-11-17 18:30Z: "Be sure the cut goes all the way under anywhere we add
a bridge"; 19:08Z: 4.2 m over a small road).

``planar/road_bridge_clear`` cuts the survey under the span where it is
short (a ground the road profile and every ``preferred_z`` reader read),
but a ground is a TARGET: the solve may still lift the lower road under the
span -- MEASURED ESSA road bridge ``-260`` over ``-3078``: the road ramped
2.8 m over its survey (22.37) from the generated deck's mouth beside the
bridge, 1.47 m into the 5.0 m clearance, its ramp ceiling at 25.70 and no
row binding (the objective held it).  So every map vertex on a lower
road's carriageway under the span takes ONE hard ceiling ``Band``: the deck
line there (``model/road_clearance.deck_at`` between the ends' levels, at the
vertex's projection on the axis) less the road's clearance
(``structure_approach.design_clearance_m``).  Groundside law (the
``groundside`` tier): the lower road moves, the bridge's ends never do.
Nothing here names an airport; no generated road bridge, no row.
"""
from __future__ import annotations

from shapely.geometry import LineString, Point, Polygon
from shapely.prepared import prep

from ..model.constraints import Band, Row, Source

__all__ = ["road_bridge_ceiling_rows", "GEN", "RULING"]

GEN = "road_bridge_ceiling"
#: the ruling HEAD ``[design] hard_rulings`` names
RULING = "structures.road_bridge clearance under the span (owner 2026-11-17 18:30Z)"


def road_bridge_ceiling_rows(planar, law, airport) -> list[Row]:
    """One hard ceiling per lower-road vertex under each generated road
    bridge's span (module doc)."""
    from ..model.road_clearance import carriageway_width_m, deck_at, design_clearance_m
    bridges = [b for b in getattr(airport, "road_bridges", ()) or ()
               if b.get("levels") and len(b.get("axis_xy") or ()) >= 2
               and len(b.get("span_xy") or ()) >= 3]
    if not bridges:
        return []
    ways = {str(w.id): w for w in getattr(airport, "osm_ways", ()) or ()}
    hi: dict[int, tuple[float, Source]] = {}
    for b in bridges:
        axis = LineString(b["axis_xy"])
        lv = (float(b["levels"][0]), float(b["levels"][1]))
        span = Polygon(b["span_xy"])
        for wid in b.get("over") or ():
            w = ways.get(str(wid))
            if w is None or len(w.points) < 2:
                continue
            region = LineString(w.points).buffer(carriageway_width_m(w.tags, law) / 2.0,
                                                 cap_style="flat").intersection(span)
            if region.is_empty:
                continue
            clear = design_clearance_m(w.tags, law)
            src = Source(GEN, RULING, (f"road_bridge:{b['id']}", f"osm:{wid}"))
            pr, (x0, y0, x1, y1) = prep(region), region.bounds
            for v, vx in planar.vertices.items():
                x, y = vx.xy
                if not (x0 <= x <= x1 and y0 <= y <= y1) or not pr.covers(Point(x, y)):
                    continue
                z = deck_at(lv, axis.length, axis.project(Point(x, y))) - clear
                if v not in hi or z < hi[v][0]:
                    hi[v] = (z, src)
    return [Band(v, None, z, src) for v, (z, src) in sorted(hi.items())]
