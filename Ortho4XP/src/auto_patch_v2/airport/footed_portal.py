"""A ROOFED PORTAL STANDING ON ITS WALLS' FEET UNDER ITS ZERO (#2069; owner
RULINGS 2026-10-26p Q167 "where a pack tunnel has no floor object, its depth
comes from the bottoms of its walls"; #971 "or object if one is provided").

``portal_objects`` reads a roofed portal whose walls stand ON its zero: the
road at the mouth is the zero.  A pack may instead sink the portal: its walls
hang ``[tunnel.object] shell_floor_min_m`` or more under its zero, it carries
no floor plate (the road is the terrain) and no hard deck (never a cover over
a cut, #1298), and its roof stands over the road.  Its road is the walls'
foot: the mouth's floor is the pack's zero plus that foot, the object stays
at the zero its author placed it at, and the depth is never the bore law's.

One OBJ8 may carry several such portals -- one per genuine component, each
its own roof and its own foot (MEASURED NZWN ``Tunnel.obj``: both ends of
bore -199 in one object, roofs +7.05 / +8.00, feet -3.95 / -3.00).  A part
pins a mapped bore end where its roof stands within
``bore_end_tolerance_m`` of the end, or where the mapped road leaving the
end runs under its roof within the shortest lawful ramp
(``mouth_depth_m / ramp_max_grade``): no ramp can come up to grade and go
down again in that run, so the road goes on underground to the portal
(the argument of ``planar/bore_continuation``).  NZWN's west portal stands
65 m up the open road from the mapped end, its east one over the end.

Nothing here names a pack, a resource or an airport.
"""
from __future__ import annotations

import math
import typing as _t

from shapely.geometry import LineString, Point
from shapely.ops import substring

from ..model.frame import XY
from . import frame_entry as _fe
from . import obj8 as _obj8
from .object_cut import _face_normals_y, _plan_area
from .portal_objects import Portal, roof_of

__all__ = ["footed_parts", "read_footed_portals", "roads_of"]


class _Part(_t.NamedTuple):
    """One sunk roofed portal of an OBJ8, in its authored frame."""

    roof_y: float
    foot_y: float
    roof_area_m2: float
    #: the roof's plan, authored ``(x, z)``
    roof_plan: object


def footed_parts(g: _obj8.ObjGeometry, genuine: _t.Sequence[_obj8.Component], law
                 ) -> "list[_Part] | str":
    """Every genuine component of ``g`` that is a portal on its walls' feet
    (module doc), or why the object is none (a string)."""
    ob = law.tables.structures.tunnel.object
    if len(g.hard_deck):
        return "a hard deck (a bridge or a cover), not a portal"
    v = g.vertices
    out: list[_Part] = []
    for c in genuine:
        tris = c.tris
        horiz = _face_normals_y(v, tris) >= ob.plate_normal_y_min
        area = _plan_area(v, tris)
        ymax = v[tris, 1].max(axis=1)
        floor = horiz & (ymax <= -ob.shell_floor_min_m)
        if floor.any() and float(area[floor].sum()) >= ob.plate_min_area_m2:
            return "a floor plate under its zero (a shell, not a portal)"
        foot = float(v[tris, 1].min())
        if foot > -ob.shell_floor_min_m:
            continue
        roof = roof_of(v, tris, horiz, area, ymax, ob)
        if isinstance(roof, str):
            continue
        top, roof_area, plan = roof
        if top - foot < law.tables.structures.bridge.clearance_minimum_m:
            continue
        out.append(_Part(top, foot, roof_area, plan))
    return out or "no roofed part standing on walls under its zero"


def _road_under(end: XY, roof, roads, reach: float) -> bool:
    """A mapped road leaving the bore end ``end`` (a way with that end as one
    of its own) runs under ``roof`` within ``reach`` metres of it."""
    for w in roads:
        pts = list(w.points)
        if len(pts) < 2:
            continue
        if math.dist(pts[-1], end) <= 1e-6:
            pts.reverse()
        elif math.dist(pts[0], end) > 1e-6:
            continue
        ln = LineString(pts)
        if substring(ln, 0.0, min(reach, ln.length)).intersects(roof):
            return True
    return False


def read_footed_portals(o: _obj8.PlacedObject, parts: _t.Sequence[_Part], ends,
                        roads, law, dem_z, zero: float) -> list:
    """One ``portal_objects.Portal`` per bore end (``ends``: ``(xy, way id)``)
    a part of placement ``o`` pins (module doc).  ``roads`` are the mapped
    non-tunnel roads, ``dem_z`` the airport's DEM, ``zero`` the placement's
    zero as its row reads (``below_grade_witness.zero_of``)."""
    tn = law.tables.structures.tunnel
    tol = float(tn.object.bore_end_tolerance_m)
    reach = float(tn.mouth_depth_m) / float(tn.ramp_max_grade)
    mat = _obj8.placement_affine(o.xy, o.heading_deg)
    out = []
    for part in parts:
        roof = _fe.enter([part.roof_plan], mat, _fe.quantum(law))[0]
        if roof is None or roof.is_empty:
            continue
        floor = zero + part.foot_y
        for xy, wid in ends:
            if roof.distance(Point(xy)) > tol and not _road_under(xy, roof, roads, reach):
                continue
            ground = float(dem_z(xy[0], xy[1])) if dem_z is not None else math.nan
            if math.isnan(ground) or not 0.0 < ground - floor <= tn.mouth_depth_m:
                continue
            c = roof.representative_point()
            out.append(Portal(o.id, o.path, (float(xy[0]), float(xy[1])), int(wid),
                              ground - floor, part.roof_area_m2, (float(c.x), float(c.y)),
                              floor_z=float(floor), bottom_y=float(part.foot_y),
                              face_plan=roof, zero_z=float(zero), footed=True))
    return out


def roads_of(osm_ways, admitted) -> list:
    """The mapped roads a bore end may run on into a footed portal: every
    non-tunnel highway way."""
    from .deck_signature import is_tunnel_way
    return [w for w in osm_ways
            if "highway" in (w.tags or {}) and len(w.points) >= 2
            and not is_tunnel_way(w.tags, admitted)]
