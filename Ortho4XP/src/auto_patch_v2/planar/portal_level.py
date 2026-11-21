"""AN AT-GRADE MOUTH OFF ITS ROAD IS SEATED ON ITS MOUTH'S FLOOR, AND THE
FLOOR STAYS LEVEL UNDER IT (#2221, owner RULINGS 2026-11-21d; the edge
bridge's rule, ``bridge_span.edge_flat_s``, 27r).

A roofed portal states its road: the road at its zero runs ``depth_m``
(its roof top) under the ground at the bore end, so the mouth's floor is
``mouth_z``.  An AT-GRADE MOUTH (``Portal.at_grade``: standing on the
author's ground, a tunnel's mouth by the bore's run past it) states no
floor of its own (the road is the terrain: walls on the road, a roof over
it -- KBUF
``Road_Tunnel.obj``, rows at AGL 0 on the uncut DEM, 6.6-9.7 m over the
road its roof states) is seated here: its zero on the mouth's floor, its
roof flush with the ground over the bore.  Its walls stand on that floor
over the whole object, so the floor stays level out to the object's
furthest point along the ramp and climbs from there -- never a ramp
rising under its walls (the drawn gate's objects layer: the KBUF rows
2.7-5.2 m under a floor that climbed from the bore end).

Every number is a law-table value; nothing here names a pack or an airport.
"""
from __future__ import annotations

from shapely.geometry import LineString, Point

__all__ = ["off_road", "level_to_s"]


def off_road(pin, mouth_z: float, law) -> bool:
    """Whether the roofed portal ``pin`` (no stated floor, an opening) is an
    AT-GRADE MOUTH (``Portal.at_grade``, 2026-11-21d) whose row stands off
    the road its roof states -- its zero more than ``[tunnel.object]
    cover_flush_m`` from ``mouth_z``.  Other floorless portals off their
    road (RJTT ``tunnel6.obj``, LFPG ``2A_22.obj``: measured, lane
    ltunnel2) keep today's seat: the ruling covers the at-grade mouth."""
    return (pin is not None and getattr(pin, "at_grade", False) and pin.floor_z is None
            and float(getattr(pin, "opening_m", 0.0) or 0.0) > 0.0
            and getattr(pin, "zero_z", None) is not None
            and abs(float(pin.zero_z) - float(mouth_z))
            > float(law.tables.structures.tunnel.object.cover_flush_m))


def level_to_s(pin, axis: LineString) -> float:
    """The station along ``axis`` (from the mouth) the floor stays level
    to under the seated portal ``pin``: its footprint's furthest point out
    along the ramp (``0`` without one)."""
    foot = getattr(pin, "footprint", None)
    if foot is None or foot.is_empty:
        return 0.0
    return float(max((axis.project(Point(q)) for g in getattr(foot, "geoms", [foot])
                      for q in g.exterior.coords), default=0.0))
