"""A PACK PORTAL OBJECT PINS ITS TUNNEL'S MOUTH (owner 2026-10-19, #971:
"Tunnel mouths should always stop at the pavement (or object if one is
provided)"; #1343 KBUF; the RULINGS 2026-10-26d family).

A PORTAL is a ROOFED pack object standing over a mapped bore's END: its
walls stand on the road (it carries no floor plate under its zero — the
road is the terrain) and its ROOF is a near-horizontal plate of a plate's
worth (``[tunnel.object] plate_min_area_m2``) above its zero, which the
ground covers.  The author's geometry states the portal's depth: the road
at the mouth is the object's zero and the ground stands on its roof, so
the mouth's floor is the ground less the ROOF TOP (:attr:`Portal.depth_m`)
— never the bore law's ``mouth_depth_m`` — and the mouth stands AT the
portal (``planar/structure_mouth.mouth_at_pavement(pinned=...)``): it does
not slide out of the pavement, because the object is provided.

A portal is the bore law's own kind of opening, so it states a depth up to
``tunnel.mouth_depth_m`` and no more: a taller roofed object over a bore's
end is a building standing on it (refused by name, the bore law keeps the
mouth); a roof under ``bridge.clearance_minimum_m`` clears no road (a deck
at grade), an object whose walls run below its zero is a cover over a cut
(EGLL's hard-deck covers, #1298), and a roof that is a HARD DECK (LFPG's
taxiway bridges ``H*.obj``: class A, 22n; the trench under them is #1138,
held) is never a portal.  A pack object that is a tunnel shell or a wall corridor is read by
``tunnel_objects`` / ``object_cut`` and never here (``taken``).

MEASURED KBUF: ``Road_Tunnel.obj`` (x4, roof top y 6.64, 219 m2) and
``KBUF_Terminal_Parking_Underpass.obj`` (x2, roof 6.09, 213 m2) stand 0.6-
10 m from five mapped service/tertiary bore ends; both were refused by
every tunnel reader ("roofed along its axis", "the inner faces leave no
station"), so their mouths were cut 7.5 m deep, slid, or refused.
"""
from __future__ import annotations

import dataclasses as _dc
import math
import os
import typing as _t

import numpy as np
from shapely.geometry import Point
from shapely.strtree import STRtree

from ..model.frame import XY
from . import frame_entry as _fe
from . import obj8 as _obj8
from .obj8_clip import _bulk_polys
from .object_cut import _face_normals_y, _plan_area

__all__ = ["Portal", "read_portals", "portal_of", "roof_reading"]


@_dc.dataclass(frozen=True)
class Portal:
    """One pack portal over one mapped bore end, in the airport frame."""

    object_id: str
    resource: str
    end_xy: XY
    way_id: int
    #: the ROOF TOP over the object's zero: the depth of the road under
    #: the ground at the mouth
    depth_m: float
    roof_area_m2: float
    #: the placement's anchor (frame xy): where X-Plane draws its zero
    anchor_xy: XY = (0.0, 0.0)
    #: owner RULINGS 2026-10-26p Q168 / 2026-10-20am-at: a HANGING portal
    #: (``airport/hanging_objects``) — a face or bridge-edge walls hanging
    #: from a top flush with the ground, no floor: ``depth_m`` is its walls'
    #: bottom under that top, the top flush with the ground beside the cover
    #: (``planar/covered_ground.beside_ground``, read by ``planar/
    #: structures``: a bare-earth DEM carries the ROAD under a lid — KATL
    #: 282 m under a 304 m field), and the cut takes in its whole plan
    #: (``plan_xy``): the mouth stands at its back
    hanging: bool = False
    plan_xy: tuple = ()


def _ends(tunnel_ways) -> list[tuple[XY, int]]:
    out = []
    for w in tunnel_ways:
        pts = list(w.points)
        if len(pts) >= 2:
            out.append(((float(pts[0][0]), float(pts[0][1])), int(w.id)))
            out.append(((float(pts[-1][0]), float(pts[-1][1])), int(w.id)))
    return out


def roof_reading(geom: _obj8.ObjGeometry, genuine: _t.Sequence[_obj8.Component],
                 law) -> "tuple[float, float, object] | str":
    """``(roof top y, roof area, roof plan)`` of a resource in its
    authored frame (the plan in ``(x, z)``), or the reason it is no portal
    (a string)."""
    ob = law.tables.structures.tunnel.object
    if not genuine:
        return "no genuine solid component"
    if len(geom.hard_deck):
        # LFPG's ``H*.obj``: a taxiway bridge over a road is a HARD DECK —
        # class A's seat (22n) and the held trench under it (#1138), never a
        # portal read here
        return "a hard deck (a bridge or a cover), not a portal"
    tris = np.concatenate([c.tris for c in genuine])
    v = geom.vertices
    horiz = _face_normals_y(v, tris) >= ob.plate_normal_y_min
    area = _plan_area(v, tris)
    ymax = np.maximum(np.maximum(v[tris[:, 0], 1], v[tris[:, 1], 1]), v[tris[:, 2], 1])
    floor = horiz & (ymax <= -ob.shell_floor_min_m)
    if floor.any() and float(area[floor].sum()) >= ob.plate_min_area_m2:
        return "a floor plate under its zero (a shell, not a portal)"
    if float(v[tris].reshape(-1, 3)[:, 1].min()) < -ob.shell_floor_min_m:
        # EGLL's ``2.obj``: an ATTR_hard_deck cover whose walls run to -5 m —
        # a cover over a cut (#1298), never a portal standing on the road
        return "walls under its zero (a cover over a cut, not a portal standing on the road)"
    up = horiz & (ymax > ob.plate_bin_m)
    if not up.any():
        return "no roof: no near-horizontal solid face above its zero"
    binned = np.floor(ymax[up] / ob.plate_bin_m).astype(int)
    bins: dict[int, float] = {}
    for k, a in zip(binned.tolist(), area[up].tolist(), strict=True):
        bins[k] = bins.get(k, 0.0) + a
    roofs = [k for k, a in bins.items() if a >= ob.plate_min_area_m2]
    if not roofs:
        return (f"no roof: the largest plate above its zero is {max(bins.values()):.0f} m2 "
                f"(< plate_min_area_m2 {ob.plate_min_area_m2:.0f})")
    top = max(roofs)
    sel = binned == top
    plan = _fe.union(_bulk_polys(v, tris[up][sel]), "portal_objects.roof_reading")
    return float(ymax[up][sel].max()), float(bins[top]), plan


def hanging_reading(o: _obj8.PlacedObject, g: _obj8.ObjGeometry, law
                    ) -> "tuple[float, tuple] | None":
    """``(depth, placed plan hull)`` of a HANGING portal — no hard
    deck, its top flush with its zero (``cover_flush_m``), its solids
    hanging to a bottom with no floor there (``hanging_objects.
    hanging_bottom``) — else ``None``."""
    from shapely.geometry import MultiPoint

    from .hanging_objects import hanging_bottom
    ob = law.tables.structures.tunnel.object
    if len(g.hard_deck) or not len(g.solid):
        return None
    v = g.vertices
    top = float(v[np.unique(g.solid), 1].max())
    if abs(top) > ob.cover_flush_m:
        return None
    bottom = hanging_bottom(v, g.solid, law)
    if bottom is None:
        return None
    # A BARE FACE (Q168): no plate of a plate's worth anywhere.  Bridge-edge
    # walls carrying a deck plate (KATL ``tunel_*``, #1138) are not read
    # here: measured on KATL, reading them so dropped the service road on
    # the bridge 3.8 m and cut 23-26 m trenches along I-285 (findings
    # ``docs/findings/1298-1138-lpackcut.md``)
    t = g.solid
    plates = _face_normals_y(v, t) >= law.tables.structures.tunnel.object.plate_normal_y_min
    if plates.any() and float(_plan_area(v, t)[plates].sum()) >= \
            law.tables.structures.tunnel.object.plate_min_area_m2:
        return None
    a, b, d, e, xo, yo = _obj8.placement_affine(o.xy, o.heading_deg)
    pts = [(a * x + b * z + xo, d * x + e * z + yo) for x, _y, z in v[np.unique(g.solid)]]
    hull = MultiPoint(pts).convex_hull
    ring = list(hull.exterior.coords) if hull.geom_type == "Polygon" else list(hull.coords)
    return top - bottom, tuple((float(x), float(y)) for x, y in ring)


def read_portals(objects: _t.Sequence[_obj8.PlacedObject], cache: _obj8.ResourceCache,
                 law, tunnel_ways, taken: _t.AbstractSet[str] = frozenset()
                 ) -> tuple[list[Portal], list[str]]:
    """Every pack portal standing over a mapped bore end, and one refusal
    line per roofed-looking candidate that is not one."""
    tn = law.tables.structures.tunnel
    tol = float(tn.object.bore_end_tolerance_m)
    ends = _ends(tunnel_ways)
    if not ends:
        return [], []
    tree = STRtree([Point(p) for p, _w in ends])
    readings: dict[str, "tuple[float, float] | str"] = {}
    out: list[Portal] = []
    refused: list[str] = []
    for o in objects:
        if (o.resolved is None or o.id in taken or not hasattr(o.plan_bbox, "buffer")
                or _obj8.is_stock_library_resource(o.path)):
            continue
        # (twice the tolerance: a bare face's line may stand it off either side)
        near = [int(j) for j in tree.query(o.plan_bbox.buffer(2.0 * tol),
                                           predicate="intersects")]
        if not near:
            continue
        g = cache.geometry(o.resolved)
        hung = hanging_reading(o, g, law) if g is not None else None
        if hung is not None:
            depth, plan_xy = hung
            from shapely.geometry import LineString as _LS
            from shapely.geometry import Polygon as _Poly
            shape = (_Poly(plan_xy) if len(plan_xy) >= 4 else
                     _LS(plan_xy) if len(plan_xy) >= 2 else None)
            # a bare FACE is a line in plan: the mapped end may stand the
            # tolerance off it on either side (EGGW ``eggw_tex14``: 4.4-9.3 m)
            reach = tol if shape is not None and shape.geom_type == "Polygon" else 2.0 * tol
            for j in [int(i) for i in tree.query(o.plan_bbox.buffer(reach),
                                                 predicate="intersects")]:
                if shape is not None and shape.distance(Point(ends[j][0])) <= reach:
                    xy, wid = ends[j]
                    out.append(Portal(o.id, o.path, xy, wid, depth, 0.0,
                                      (float(o.xy[0]), float(o.xy[1])), True, plan_xy))
            continue
        if o.path not in readings:
            readings[o.path] = (roof_reading(g, cache.genuine(o.resolved), law)
                                if g is not None else "unreadable OBJ8")
        r = readings[o.path]
        name = os.path.basename(o.path)
        if isinstance(r, str):
            continue
        depth, roof_area, plan = r
        # THE ROOF STANDS OVER THE BORE END: a plate's worth somewhere in a
        # large object's plan box is not a portal (EGGW ``eggw_cabins.obj``,
        # 400 m of scattered cabins, boxed both ends of bore -908)
        roof = _fe.enter([plan], _obj8.placement_affine(o.xy, o.heading_deg),
                         _fe.quantum(law))[0]
        near = [j for j in near
                if roof is not None and roof.distance(Point(ends[j][0])) <= tol]
        if not near:
            continue
        if depth < law.tables.structures.bridge.clearance_minimum_m:
            refused.append(f"{o.id} {name}: roofed over a bore end, but its roof top "
                           f"{depth:.2f} m clears no road (bridge.clearance_minimum_m "
                           f"{law.tables.structures.bridge.clearance_minimum_m}): a deck, "
                           f"not a portal")
            continue
        if depth > tn.mouth_depth_m:
            refused.append(f"{o.id} {name}: roofed over a bore end, but its roof top "
                           f"{depth:.2f} m stands over the bore law's mouth_depth_m "
                           f"{tn.mouth_depth_m}: a building on the bore, not a portal")
            continue
        for j in near:
            xy, wid = ends[j]
            out.append(Portal(o.id, o.path, xy, wid, depth, roof_area,
                              (float(o.xy[0]), float(o.xy[1]))))
    out.sort(key=lambda p: (p.end_xy, p.object_id))
    return out, refused


def portal_of(xy: XY, portals: _t.Sequence[Portal], tol_m: float) -> "Portal | None":
    """The portal pinning the mapped mouth at ``xy`` (its bore end within
    ``tol_m``), the nearest one where two stand there."""
    best = None
    for p in portals:
        d = math.hypot(p.end_xy[0] - xy[0], p.end_xy[1] - xy[1])
        if d <= tol_m and (best is None or d < best[0]):
            best = (d, p)
    return None if best is None else best[1]
