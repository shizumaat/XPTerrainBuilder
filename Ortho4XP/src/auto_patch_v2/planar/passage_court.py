"""THE OPEN COURT OF A PASSAGE LEVEL (owner RULINGS 2026-11-10h, KMCI
garden).

Owner, 1.0.480 sim read: "I think the garden level stays part of the group,
shouldn't change relative to the terminal, it's just the terrain should be
graded flat at the lot level under it so it's exposed".  A unit whose main
floor and passage coexist (``planar/level_regions._upper_floors``) may set
parts down OUTSIDE its pads -- a garden, a forecourt's planters -- on ground
no region holds, where the DEM buries them.  Where such a cluster meets a
parking lot (``planar/landing.LOT_ROLES``: the lot at the walls' foot, at
the passage's floor), the ground under and around it is that floor: its
COURT.

THE COURT (:func:`courts`).  The unit's parts with feet standing at or
under its main floor (authored base within one ``PLANE_BAND_M`` of the main
floor's plane, or lower), whose plan centre lies on no pad, lot or airside
region, clustered within two ``pad_frontage_m`` of one another; a cluster
within two ``pad_frontage_m`` plus a riser of a lot is a court: the convex
hull of its parts and the lot's edge within that reach (the ground between
them), grown by ``pad_frontage_m`` (the "around"), less the pads and a
riser, the lots, the mapped carriageways and the airside with
``pad_frontage_m``.  ``level_regions.seed_levels``
mints each as a piece of the passage level (step (b)'s ``_pieces``): at the
passage floor, a riser along the pads and its open edges, none into a lot.
The parts keep their unit's seat; only the ground moves.  A cluster beside
no lot (a structure on the high ground) is no court.

MEASURED KMCI ``building26`` (unit 20): the garden's planters, paths and
rails at y -8.0 .. -8.3 (302.6 m at the terminal's 310.70 zero) on DEM
302.5-303.8 outside the patch, between ``dsf:objpav405`` / ``objpav660``
(300.10-300.16) and the hall's facade.

Nothing here names a pack, a resource or an airport.
"""
from __future__ import annotations

import shapely
from shapely.geometry import Polygon
from shapely.ops import unary_union

from ..geom.parts import nonempty_polygon_parts
from ..geom.valid_area import valid_area

__all__ = ["courts"]


def courts(unit, floor_y: float, pads, lots, air, roads, to_xy, near: float, w: float,
           pmin: float) -> "list[Polygon]":
    """The courts (module docstring) of the partition ``unit`` whose main
    floor stands at authored ``floor_y``: ``pads``, ``lots`` and ``air``
    the regions' unions (frame xy), ``roads(g)`` the mapped carriageways
    over ``g`` (or ``None``),
    ``near`` = ``pad_frontage_m``, ``w`` the riser width, ``pmin`` the
    least piece."""
    from ..airport.airside_group_seat import PLANE_BAND_M
    if unit is None or lots is None or lots.is_empty:
        return []
    taken = valid_area(unary_union([g for g in (pads, lots, air) if g is not None]))
    rings = []
    for m in unit.members:
        for p in m.parts:
            if getattr(p, "line", False) or not (getattr(p, "feet", ()) or ()) \
                    or float(p.base_y) > floor_y + float(PLANE_BAND_M):
                continue
            x, y = to_xy(p.lon, p.lat)
            if shapely.contains_xy(taken, x, y):
                continue
            for rg in p.rings:
                if len(rg) >= 3:
                    g = Polygon([to_xy(lon, lat) for lat, lon in rg])
                    g = g if g.is_valid else g.buffer(0.0)
                    if not g.is_empty:
                        rings.append(g)
    if not rings:
        return []
    keep_off = valid_area(unary_union([pads.buffer(w, join_style=2), lots,
                                       air.buffer(near, join_style=2)]))
    reach = 2.0 * near + w
    out: list[Polygon] = []
    for c in nonempty_polygon_parts(valid_area(unary_union(
            [g.buffer(near) for g in rings]))):
        mine = valid_area(unary_union([g for g in rings if g.intersects(c)]))
        if mine.distance(lots) > reach:
            continue
        # the ground between the parts and the lot is the court's too
        lot_near = valid_area(lots.intersection(mine.buffer(reach, join_style=2)))
        hull = unary_union([mine, lot_near]).convex_hull.buffer(near, join_style=2)
        road = roads(hull) if roads is not None else None
        q0 = valid_area(hull.difference(keep_off))
        if road is not None and not road.is_empty:
            q0 = valid_area(q0.difference(road))
        out.extend(q for q in nonempty_polygon_parts(q0)
                   if q.area >= pmin)
    return out
