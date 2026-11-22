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
from .below_grade_witness import zero_of
from .hanging_objects import edge_wall_reading, flush_hanging
from .obj8_clip import _bulk_polys
from .object_cut import _face_normals_y, _plan_area

__all__ = ["Portal", "across_bore", "read_portals", "portal_of", "roof_of",
           "roof_reading"]


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
    #: bottom under its top, and the cut takes in its whole plan
    #: (``plan_xy``): the mouth stands at its back
    hanging: bool = False
    plan_xy: tuple = ()
    #: owner RULINGS 2026-10-27l: an EDGE-WALL BRIDGE's pin
    #: (``planar/bridge_span.bridge_pin``) — its back line; the mouth stands
    #: at it (``planar/structure_mouth.edge_wall_mouth``).  Empty for every
    #: portal this module reads.
    edge_walls: tuple = ()
    #: #1747 (owner ruling 2026-11-03 "yes", LOWS): the ABSOLUTE floor an
    #: ENTRANCE object states at the bore end — its solids' bottom where it
    #: stands (``trench_objects.mouth_portals``); the mouth's floor is this,
    #: never the ground less :attr:`depth_m`.  A TALL roofed portal (over
    #: ``mouth_depth_m``, owner 2026-11-04 ENTC) states it too: the surveyed
    #: ground on its roof less its roof top.  ``None`` for any other portal.
    floor_z: "float | None" = None
    #: a portal's OPENING across the bore at the end — a ROOFED portal's
    #: roof width (owner 2026-11-04 ENTC: "tunnel ramps not matching tunnel
    #: mouth width"), an ENTRANCE face's gap between its walls
    #: (``trench_objects.mouth_portals``, owner 2026-11-05 LOWS "shouldn't
    #: its size be set by the tunnel mouth object?") — the ramp's width at
    #: the mouth; ``0.0`` for any other pin
    opening_m: float = 0.0
    #: #1917: the opening's two EDGE points across the bore at the end
    #: (frame metres, :attr:`opening_m` apart) -- WHERE the ramp stands, not
    #: only how wide: the mapped road need not run down the opening's middle
    #: (MEASURED LOWS west mouth: the carriageways' midline 1.5 m off it, the
    #: cut wall over 1.5 m of the opening).  Empty with no opening.
    opening_xy: tuple = ()
    #: #2062 R3b C: an ENTRANCE face's FRONT WALL ends across the bore
    #: (``airport/entrance_front``; ``opening_xy`` inside it) and its width;
    #: ``()`` / ``0.0`` with none wider than the opening
    front_xy: tuple = ()
    front_m: float = 0.0
    #: owner RULINGS 2026-11-16a: the entrance reader's own opening read
    #: under one road lane (``[tunnel] lane_width_m``) -- a misread; the
    #: opening above is the face's jamb-to-jamb read
    #: (``entrance_front.jamb_to_jamb``), and the object's walls are the cut's
    #: witness (``airport/walled_trench``)
    opening_misread: bool = False
    #: #2099 F2 P0: a misread face its OWN read did not wall, walled and
    #: seated by the re-read (zero = :attr:`floor_z` - :attr:`bottom_y` on the
    #: ground its walls retain): the one witness for the retaining-wall law's
    #: re-seat (``airport/wall_reseat``) and for the face's plan being its
    #: wall (``trench_objects._wall_plan``)
    wall_reseat: bool = False
    #: #1747 (Q-A 2026-11-05): an ENTRANCE object's face bottom under its
    #: zero at this end (``trench_objects.mouth_portals``) — the object stage
    #: seats that face with its bottom on :attr:`floor_z`
    #: (``Tunnel.portal_seat``); ``None`` for any other pin
    bottom_y: "float | None" = None
    #: RULINGS 2026-11-06c (3): an ENTRANCE face's TOP — its plan (frame
    #: metres, ``trench_objects._face_at``) and its level once seated (the
    #: ground over it): the ramp ends at its front and the ground round it
    #: is graded up to it (``planar/entrance_skirt``); a TALL roofed portal's
    #: roof and its WINGS standing at its top (``_wing_plan``, #1689 R4) and
    #: the cover on it (#1689 R2 A3, no :attr:`bottom_y`); ``None`` otherwise
    face_plan: object = None
    face_top_z: "float | None" = None
    #: #1737: the top plan the face's cover was read over (``trench_objects.
    #: _face_at``) -- a lid's as well as a headwall's: where AIRSIDE pavement
    #: abuts it, the face's top is that pavement's level
    #: (``constraints/airside_top``); a ROOFED portal's roof plan (#1689 R2
    #: A2: the reach its seat leads its frame within); ``None`` otherwise
    top_plan: object = None
    #: #1689 R3: a ROOFED portal's OWN FOOTPRINT -- the plan of its genuine
    #: solids, roof, walls and wings (frame metres): the frame its seat
    #: leads stands in it (``terrain_shaped.portal_frame_records``) and a
    #: tall portal's host pads are cut to it (``planar/entrance_skirt.
    #: host_blade``); ``None`` otherwise
    footprint: object = None
    #: #1938 (RULINGS 2026-11-13h, round 2 S2/S3): an ENTRANCE object's
    #: WALL REACH -- how far its solids hanging ``shell_floor_min_m`` or more
    #: under its zero run along the approach from the end (metres; inside it
    #: the trench is senior to a pad) -- and its WALL-FOOT GRADE, the slope of
    #: the lowest solid along that reach (the ramp's design grade there,
    #: ``trench_objects.wall_feet``); ``0.0`` for any other pin
    wall_reach_m: float = 0.0
    foot_grade: float = 0.0
    #: #1949: a ROOFED portal's zero as its row reads (``below_grade_witness
    #: .zero_of``): off the road its roof states at the bore end, its own
    #: floor is the cut there (``airport/portal_floor``); ``None`` with no
    #: ground read
    zero_z: "float | None" = None
    #: #2069: a portal standing on its walls' FEET under its zero
    #: (``airport/footed_portal``): the mouth stands at the back of its roof
    #: (``planar/structure_mouth.roof_back_mouth``), its floor is
    #: :attr:`floor_z`, and its body is seated by its ENTRANCE record at
    #: :attr:`anchor_xy` (zero = floor - :attr:`bottom_y`)
    footed: bool = False
    #: #1689 R5 R2 / R3: a TALL roofed portal's COVER -- the plan (frame
    #: metres) of the highest plate of its FRAME (:func:`_frame`) standing a
    #: road's clearance over its zero at this end (:func:`_covers`), and its
    #: top once seated (the floor plus its top y): the cut ends under it and
    #: the ground behind welds to its back at that top; ``None`` otherwise
    cover_plan: object = None
    cover_top_z: "float | None" = None
    #: #1689 R5 R3: the plan of the frame's solids standing over the cover
    #: (a parapet, a headwall): the ground in front of them is never its
    #: skirt (``planar/entrance_skirt``); ``None`` with none or no cover
    parapet_plan: object = None
    #: owner RULINGS 2026-11-21d (#2221): a roofed portal standing ON the
    #: author's ground that is still its tunnel's mouth (:func:`_tunnel_mouth`):
    #: its row reads the uncut ground, never its road -- it states no floor of
    #: its own (``airport/portal_floor`` reads none) and is seated on its
    #: mouth's floor (``planar/portal_level``)
    at_grade: bool = False


def _ends(tunnel_ways) -> list[tuple[XY, int]]:
    out = []
    for w in tunnel_ways:
        pts = list(w.points)
        if len(pts) >= 2:
            out.append(((float(pts[0][0]), float(pts[0][1])), int(w.id)))
            out.append(((float(pts[-1][0]), float(pts[-1][1])), int(w.id)))
    return out


def _bore_dirs(tunnel_ways) -> dict[tuple[XY, int], XY]:
    """The unit direction INTO each bore from each of its ends."""
    out: dict[tuple[XY, int], XY] = {}
    for w in tunnel_ways:
        pts = [(float(x), float(y)) for x, y in w.points]
        if len(pts) < 2:
            continue
        for a, b in ((pts[0], pts[1]), (pts[-1], pts[-2])):
            d = math.hypot(b[0] - a[0], b[1] - a[1])
            if d > 0.0:
                out[(a, int(w.id))] = ((b[0] - a[0]) / d, (b[1] - a[1]) / d)
    return out


def across_bore(pts, end_xy: XY, into: XY) -> list[float]:
    """Each plan point's offset ACROSS the bore (direction ``into``) from
    its end ``end_xy``: the one axis every portal's opening is read on."""
    nx, ny = -into[1], into[0]
    return [(float(x) - end_xy[0]) * nx + (float(y) - end_xy[1]) * ny for x, y in pts]


def opening_span(lo: float, hi: float, end_xy: XY, into: "XY | None") -> tuple[float, tuple]:
    """``(width, (edge, edge))`` of an opening spanning ``lo``..``hi``
    across the bore (:func:`across_bore`) from its end, the edges in frame
    metres; ``(0.0, ())`` for no span."""
    if into is None or not hi > lo:
        return 0.0, ()
    nx, ny = -into[1], into[0]
    return float(hi - lo), tuple((end_xy[0] + q * nx, end_xy[1] + q * ny) for q in (lo, hi))


def _roof_opening(roof, end_xy: XY, into: "XY | None", tol: float) -> tuple[float, tuple]:
    """A roofed portal's OPENING: the extent across the bore's direction
    ``into`` (:func:`opening_span`) of the roof PARTS standing over this
    bore end (within ``tol``, the test that admitted the portal).

    #1910: a roof plan is the object's every roof, and a large object's
    are scattered — LOWS ``Terminal_LOWS_61.obj`` read 183.71 m across a
    7 m service bore from its whole roof, 16.22 m from the two parts over
    the end.  A part standing clear of the end roofs something else."""
    if roof is None or roof.is_empty or into is None:
        return 0.0, ()
    end = Point(end_xy)
    parts = [g for g in getattr(roof, "geoms", [roof]) if g.distance(end) <= tol]
    s = across_bore([c for g in parts for c in g.exterior.coords], end_xy, into)
    return opening_span(min(s), max(s), end_xy, into) if s else (0.0, ())


#: :func:`roof_reading`'s verdict on walls hanging under the zero: read again
#: as a FOOTED portal (``airport/footed_portal``, #2069)
_WALLS_UNDER = "walls under its zero"


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
        return _WALLS_UNDER + " (a cover over a cut, not a portal standing on the road)"
    return roof_of(v, tris, horiz, area, ymax, ob)


def roof_of(v: np.ndarray, tris: np.ndarray, horiz: np.ndarray, area: np.ndarray,
            ymax: np.ndarray, ob) -> "tuple[float, float, object] | str":
    """``(roof top y, roof area, roof plan)`` of the near-horizontal faces
    ``horiz`` of ``tris`` standing above the zero: the HIGHEST
    ``plate_bin_m`` bin of a plate's worth, or why there is none (a
    string).  ``area`` / ``ymax`` are the faces' plan areas and tops."""
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
    plan = _fe.union(_bulk_polys(v, tris[up][sel]), "portal_objects.roof_of")
    return float(ymax[up][sel].max()), float(bins[top]), plan


def hanging_reading(o: _obj8.PlacedObject, g: _obj8.ObjGeometry, law
                    ) -> "tuple[float, tuple] | None":
    """``(depth, placed plan hull)`` of a HANGING portal — a BARE FACE (Q168):
    ``hanging_objects.flush_hanging`` and no plate of a plate's worth
    anywhere — else ``None``.  Bridge-edge walls carrying a deck plate (KATL
    ``tunel_*``, #1138) are an edge-wall bridge (``hanging_objects.
    edge_wall_reading``, owner RULINGS 2026-10-27l), not this: read as a
    bare face, their hull's back sent KATL's mouths 68-135 m into the span."""
    from shapely.geometry import MultiPoint
    hung = flush_hanging(g, law)
    if hung is None:
        return None
    top, bottom = hung
    v, t = g.vertices, g.solid
    plates = _face_normals_y(v, t) >= law.tables.structures.tunnel.object.plate_normal_y_min
    if plates.any() and float(_plan_area(v, t)[plates].sum()) >= \
            law.tables.structures.tunnel.object.plate_min_area_m2:
        return None
    a, b, d, e, xo, yo = _obj8.placement_affine(o.xy, o.heading_deg)
    pts = [(a * x + b * z + xo, d * x + e * z + yo) for x, _y, z in v[np.unique(t)]]
    hull = MultiPoint(pts).convex_hull
    ring = list(hull.exterior.coords) if hull.geom_type == "Polygon" else list(hull.coords)
    return top - bottom, tuple((float(x), float(y)) for x, y in ring)


def _solids_plan(o: _obj8.PlacedObject, g: _obj8.ObjGeometry,
                genuine: _t.Sequence[_obj8.Component], law):
    """The placed plan (frame metres) of ``o``'s genuine solids -- every
    plan-bearing triangle's plan, unioned (``frame_entry``) -- or ``None``.
    A wall stands edge-on in plan: a reader grows the plan by its own
    reach to take it in."""
    if not genuine:
        return None
    tris = np.concatenate([c.tris for c in genuine])
    plan = _fe.union(_bulk_polys(g.vertices, tris), "portal_objects._solids_plan")
    return _fe.enter([plan], _obj8.placement_affine(o.xy, o.heading_deg), _fe.quantum(law))[0]


#: a wall's half thickness in plan: it stands edge-on, so its outline is
#: read as a line grown by this much (#1689 R4 W1)
_WALL_HALF_M = 0.1


def _station(c, end_xy: XY, into: XY) -> float:
    """``c``'s station along ``into`` from ``end_xy`` (into the bore)."""
    return (c[0] - end_xy[0]) * into[0] + (c[1] - end_xy[1]) * into[1]


def _wing_plan(o: _obj8.PlacedObject, g: _obj8.ObjGeometry, roof, local, top_y: float,
               end_xy: XY, into: "XY | None", law):
    """The plan (frame metres) of a TALL portal's WINGS at one bore end, or
    ``None``: the solids of its OWN object standing AT its stated top
    ``top_y`` (highest vertex within ``[tunnel.object] cover_flush_m`` of
    it; every still solid read, a thin cap included -- at the top it is no
    ground decal), taken in plan (plates as polygons, every outline as a
    line grown by :data:`_WALL_HALF_M`), less the whole ``roof`` grown by
    twice that; a part is a wing where it stands within ``plate_bin_m`` of
    ``local`` (the roof over this end) and runs at least
    ``entrance_skirt_m`` OUT of the bore beyond that roof's front.

    #1689 R4: the wings are part of the top the portal states, so the
    level piece of its skirt runs along them.  MEASURED KBNA Murfreesboro
    east: two wing walls run 15.2 and 15.6 m out of the bore at the
    headwall's level (to 8.8 over the zero); held at the stub roof alone,
    the ground behind them fell to the DEM."""
    if into is None or local is None or local.is_empty:
        return None
    import shapely
    ob = law.tables.structures.tunnel.object
    v, t = g.vertices, g.solid
    if len(t) and g.animated.shape[0]:
        t = t[~g.animated]
    t = t[v[t][:, :, 1].max(axis=1) >= float(top_y) - float(ob.cover_flush_m)] \
        if len(t) else t
    if not len(t):
        return None
    pts = v[t][:, :, [0, 2]]
    lines = shapely.linestrings(np.concatenate([pts, pts[:, :1]], axis=1))
    plan = _fe.union([*_bulk_polys(v, t), *shapely.buffer(lines, _WALL_HALF_M).tolist()],
                     "portal_objects._wing_plan")
    plan = _fe.enter([plan], _obj8.placement_affine(o.xy, o.heading_deg), _fe.quantum(law))[0]
    if plan is None or plan.is_empty:
        return None
    rings = [c for q in getattr(local, "geoms", [local]) if q.geom_type == "Polygon"
             for c in q.exterior.coords]
    if not rings:
        return None
    front = min(_station(c, end_xy, into) for c in rings)
    beyond = plan.difference(roof.buffer(2.0 * _WALL_HALF_M))
    parts = [q for q in getattr(beyond, "geoms", [beyond])
             if q.geom_type == "Polygon" and not q.is_empty
             and q.distance(local) <= float(ob.plate_bin_m)
             and front - min(_station(c, end_xy, into) for c in q.exterior.coords)
             >= float(ob.entrance_skirt_m)]
    return _fe.union(parts, "portal_objects._wing_plan") if parts else None


def _in_frame(v: np.ndarray, q: _obj8.PlacedObject, o: _obj8.PlacedObject) -> np.ndarray:
    """``q``'s authored vertices ``v`` in ``o``'s authored frame (``(x, z)``
    through the airport frame; ``y`` kept): a placement affine is its own
    inverse (a reflection), so ``o``'s takes the frame point home."""
    a, b, d, e, xo, yo = _obj8.placement_affine(q.xy, q.heading_deg)
    A, B, D, E, XO, YO = _obj8.placement_affine(o.xy, o.heading_deg)
    px, py = a * v[:, 0] + b * v[:, 2] + xo - XO, d * v[:, 0] + e * v[:, 2] + yo - YO
    out = v.copy()
    out[:, 0], out[:, 2] = A * px + B * py, D * px + E * py
    return out


def _frame(o: _obj8.PlacedObject, objects: _t.Sequence[_obj8.PlacedObject],
           cache: _obj8.ResourceCache, foot, law) -> "tuple[np.ndarray, np.ndarray] | None":
    """THE FRAME IS THE OBJECT (#1689 R5 R1): ``(vertices, tris)`` of the
    still solids (``solid`` less ``animated``, every component) of the
    portal ``o`` and of every placement its seat leads -- the test
    ``terrain_shaped.portal_frame_records`` reads with the tol and reach
    ``pipeline/rebake_inputs`` hands it: co-placed (``hanging_objects.
    _co_placed``, ``cover_placement_tol_m``) and standing in the portal's
    footprint ``foot`` (``walled_pit._in_pit``, ``bore_end_tolerance_m``)
    -- in ``o``'s authored frame; ``None`` with no solid.  No genuine
    filter: a deck sheet one side thick is the cover (R4 W1's reason)."""
    from .hanging_objects import _co_placed
    from .walled_pit import _in_pit
    ob = law.tables.structures.tunnel.object
    group = [o]
    if foot is not None and not foot.is_empty:
        tol, reach = float(ob.cover_placement_tol_m), float(ob.bore_end_tolerance_m)
        group += [q for q in objects if q.resolved and _co_placed(o, q, tol)
                  and _in_pit(q, foot, cache, reach)]
    vs, ts, k = [], [], 0
    for q in group:
        g = cache.geometry(q.resolved) if q.resolved else None
        if g is None or not len(g.solid):
            continue
        t = g.solid[~g.animated] if g.animated.shape[0] else g.solid
        if not len(t):
            continue
        vs.append(g.vertices if q is o else _in_frame(g.vertices, q, o))
        ts.append(t + k)
        k += len(g.vertices)
    return (np.concatenate(vs), np.concatenate(ts)) if ts else None


def _placed_plan(o: _obj8.PlacedObject, v: np.ndarray, t: np.ndarray, law, site: str):
    """The placed plan (frame metres) of the triangles ``t``: plates as
    polygons, every outline as a line grown by :data:`_WALL_HALF_M` (a wall
    stands edge-on); ``None`` when nothing is left."""
    import shapely
    pts = v[t][:, :, [0, 2]]
    lines = shapely.linestrings(np.concatenate([pts, pts[:, :1]], axis=1))
    plan = _fe.union([*_bulk_polys(v, t), *shapely.buffer(lines, _WALL_HALF_M).tolist()], site)
    plan = _fe.enter([plan], _obj8.placement_affine(o.xy, o.heading_deg), _fe.quantum(law))[0]
    return None if plan is None or plan.is_empty else plan


def _covers(frame, end_xy: XY, o: _obj8.PlacedObject, law) -> "tuple[float, object, object] | None":
    """``(cover top y, cover plan, soffit plan)`` of a portal's ``frame``
    (:func:`_frame`) at the bore end ``end_xy``, the plans placed (#1689 R5
    R2), or ``None``.  The frame's near-horizontal faces whose top stands
    ``bridge.clearance_minimum_m`` over the zero, binned by
    ``plate_bin_m``: a COVER BIN is one whose plan union (one side, never
    the triangle sum) is a plate's worth, a PLATE and not a wall top (it
    survives ``wall_face_max_thickness_m / 2`` inward: #2099 W1's witness)
    and within ``bore_end_tolerance_m`` of the end once placed.  The cover
    is the HIGHEST cover bin, the soffit the LOWEST (``None`` with one bin:
    no ceiling under the cover, R5 T2); ``None`` where the bins are not
    :func:`_one_roof` (R5b: floors of a building, read as R4).

    MEASURED KBNA Murfreesboro west: the parapet's 0.9 m top at 8.89 read
    as the roof by its two-sided triangle area (#1689 R4); the deck at
    7.43 is the cover and the ceiling at 5.95 the soffit."""
    ob = law.tables.structures.tunnel.object
    v, t = frame
    horiz = _face_normals_y(v, t) >= ob.plate_normal_y_min
    ymax = v[t][:, :, 1].max(axis=1)
    up = horiz & (ymax >= float(law.tables.structures.bridge.clearance_minimum_m))
    if not up.any():
        return None
    tu, yu = t[up], ymax[up]
    bins = np.floor(yu / ob.plate_bin_m).astype(int)
    mat, end, found = _obj8.placement_affine(o.xy, o.heading_deg), Point(end_xy), {}
    for k in sorted(set(bins.tolist())):
        plan = _fe.union(_bulk_polys(v, tu[bins == k]), "portal_objects._covers")
        if plan is None or plan.is_empty or plan.area < ob.plate_min_area_m2 \
                or plan.buffer(-0.5 * float(ob.wall_face_max_thickness_m)).is_empty:
            continue
        placed = _fe.enter([plan], mat, _fe.quantum(law))[0]
        if placed is not None and not placed.is_empty \
                and placed.distance(end) <= float(ob.bore_end_tolerance_m):
            found[k] = (float(yu[bins == k].max()), placed)
    if not found or not _one_roof([top for top, _p in found.values()], law):
        return None
    # one cover bin: no soffit under the cover, the opening is read as R4's
    return (found[max(found)][0], found[max(found)][1],
            found[min(found)][1] if len(found) > 1 else None)


def _one_roof(plate_tops: _t.Sequence[float], law) -> bool:
    """A frame's cover plates (their tops over the zero) state ONE ROOF
    over its road (#1689 R5b R2, the scope witness): the highest stands at
    most ``tunnel.roof_m + tunnel.cover_m`` over the lowest -- a roof slab
    and its cover, the deck and its ceiling.  More is FLOORS of a building
    (its storeys' plates), never a mouth's cover; a hard-deck box passes.

    MEASURED: ENGM's terminal frames span 4.07 / 19.17 / 6.77 m; the
    tunnel mouths ENTC 1.08 / 0.50 and KBNA 1.48 / 1.67 against 2.2."""
    tn = law.tables.structures.tunnel
    return not plate_tops or \
        max(plate_tops) - min(plate_tops) <= float(tn.roof_m) + float(tn.cover_m)


def _parapet(o: _obj8.PlacedObject, frame, top_y: float, law):
    """The placed plan of the ``frame``'s solids whose highest vertex
    stands more than ``plate_bin_m`` over the cover top ``top_y`` -- the
    walls standing over the cover (#1689 R5 R3) -- or ``None``."""
    v, t = frame
    hi = t[v[t][:, :, 1].max(axis=1) > float(top_y) + float(
        law.tables.structures.tunnel.object.plate_bin_m)]
    return _placed_plan(o, v, hi, law, "portal_objects._parapet") if len(hi) else None


def _front_wall_top(o: _obj8.PlacedObject, g: _obj8.ObjGeometry,
                   genuine: _t.Sequence[_obj8.Component], at, law) -> "float | None":
    """The TOP y (over the object's zero) of a tall portal's FRONT WALL at
    a bore end: the highest of its genuine solids' WALL faces (``|normal
    y|`` under ``plate_normal_y_min``) standing in ``at`` -- the roof
    within that end's reach, frame metres -- grown by
    ``bore_end_tolerance_m``: the headwall over the mouth, read at its full
    height.  ``None`` where no wall stands there.

    #1689 R3 (master ruling 2026-11-15): the top a tall portal states is
    its headwall's own top, not the cover the survey read on its roof.
    MEASURED KBNA Murfreesboro east portal: a hollow stub roof at 7.78
    over the zero, the headwall in front of it to 9.17 (the survey's cover
    176.50, the headwall top 177.88 with the zero on the 168.71 floor);
    the west portal's headwall top is its roof top, 8.89."""
    if not genuine or at is None or at.is_empty:
        return None
    import shapely
    ob = law.tables.structures.tunnel.object
    v = g.vertices
    tris = np.concatenate([c.tris for c in genuine])
    walls = tris[_face_normals_y(v, tris) < ob.plate_normal_y_min]
    if not len(walls):
        return None
    a, b, d, e, xo, yo = _obj8.placement_affine(o.xy, o.heading_deg)
    p = v[walls]
    px, py = a * p[:, :, 0] + b * p[:, :, 2] + xo, d * p[:, :, 0] + e * p[:, :, 2] + yo
    ring = np.stack([px, py], axis=2)
    lines = shapely.linestrings(np.concatenate([ring, ring[:, :1]], axis=1))
    hit = shapely.intersects(lines, at.buffer(float(ob.bore_end_tolerance_m)))
    return float(p[hit][:, :, 1].max()) if hit.any() else None


def _ground_covers_roof(roof, end_xy: XY, dem_z, law, into: "XY | None" = None
                       ) -> "float | None":
    """The surveyed ground over a portal's ROOF (the highest DEM sample
    over the roof plan, its vertices and an inner point) when it stands at
    least ``[channel] object_min_depth_m`` — the survey's own reading of a
    cut (RULINGS 2026-10-28k (232 a)) — over the ground at its bore end,
    else ``None``: no cover stands on the roof.

    #1689: the ground a portal holds back stands BEHIND its roof, over the
    bore (``into``: the unit direction into it from the end).  With
    ``into``, the bore is sampled inward every ``abutment_sample_step_m`` as
    far as the roof reaches along it plus ``bore_end_tolerance_m``, and the
    ground at the end is the lowest of the end and the road
    ``bore_end_tolerance_m`` out of it (a survey cell straddling a mouth
    blends the cut's two sides).  MEASURED KBNA Murfreesboro east portal (a
    headwall over a primary road into a 307 m bore under a runway): the DEM
    over its roof plan reads 175.4, 1.6 m over the end's 173.8; 5 m into
    the bore 176.3, 5 m out along the road 170.5 -- a 5.8 m cut."""
    if dem_z is None or roof is None or roof.is_empty:
        return None
    end = float(dem_z(end_xy[0], end_xy[1]))
    pts = [roof.representative_point().coords[0]]
    for g in getattr(roof, "geoms", [roof]):
        pts.extend(g.exterior.coords)
    if into is not None:
        tol = float(law.tables.structures.tunnel.object.bore_end_tolerance_m)
        out = float(dem_z(end_xy[0] - into[0] * tol, end_xy[1] - into[1] * tol))
        end = end if math.isnan(out) else min(end, out)
        reach = max(0.0, max((x - end_xy[0]) * into[0] + (y - end_xy[1]) * into[1]
                             for x, y in pts)) + tol
        step = float(law.tables.structures.bridge.abutment_sample_step_m)
        n = max(1, int(math.ceil(reach / step)))
        pts.extend((end_xy[0] + into[0] * reach * k / n, end_xy[1] + into[1] * reach * k / n)
                   for k in range(1, n + 1))
    zs = [float(dem_z(x, y)) for x, y in pts]
    zs = [z for z in zs if not math.isnan(z)]
    if math.isnan(end) or not zs:
        return None
    cover = max(zs)
    return cover if cover - end >= float(law.tables.structures.channel.object_min_depth_m) \
        else None


class _GradeEnd(_t.NamedTuple):
    """A mapped bore END a roofed pack object stands over AT GRADE — a
    building on the road (a toll booth, a canopy), refused as a portal by
    :func:`_at_grade`: the bore enters that building, it is no terrain
    tunnel (``planar/structure_service``'s (a), #1972)."""

    end_xy: XY
    way_id: int
    object_id: str
    resource: str
    why: str


def _roof_over(roof, points: _t.Sequence[XY], tol: float):
    """The parts of ``roof`` standing within ``tol`` of a bore end in
    ``points``: the roof the ground must stand on for a portal there (#2086
    LEMG ``LEMGterminalMagenta-LEMG62.obj``: 17 roofs over 400 m of
    terminal front: the author's ground round all of them read the
    terminal's plates 5.16 m over its bottom, round the one over the bore
    end 0.31 m — a building over the road at grade)."""
    parts = list(getattr(roof, "geoms", [roof]))
    near = [q for q in parts if any(q.distance(Point(p)) <= tol for p in points)]
    if not near or len(near) == len(parts):
        return roof
    from shapely.ops import unary_union
    return unary_union(near)


def _at_grade(o: _obj8.PlacedObject, cache: _obj8.ResourceCache, roof, law,
              ground) -> str:
    """Why a roofed portal candidate ``o`` stands ON the author's ground —
    its lowest genuine solid under the author's ground around its roof
    over the bore end (:func:`_roof_over`) by
    less than ``floor_sunken_min_m`` (``airport/below_grade_witness``, owner RULINGS
    2026-11-07b (1)) — or ``""``.  A portal says the road at its zero runs
    under the ground that stands on its roof; where the ground around it
    stands at its zero it is a building over the road at grade (KDEN's toll
    booths, #1972), and its roof top states no depth."""
    if ground is None or roof is None or roof.is_empty:
        return ""
    from .below_grade_witness import row_depth_under
    low = min((c.min_y for c in cache.genuine(o.resolved)), default=0.0)
    b = row_depth_under(o, low, roof, {o.id}, ground, law)
    floor = law.tables.structures.tunnel.object.floor_sunken_min_m
    if not b.depth < floor:
        return ""
    return (f"roofed over a bore end, but it stands on the author's ground — {b.why} < "
            f"floor_sunken_min_m {floor:g}: a building over the road at grade, not a "
            f"portal (RULINGS 2026-11-07b (1), #1972)")


def _bore_runs(tunnel_ways) -> dict[int, float]:
    """Each tunnel way's BORE RUN: the summed length of the mapped tunnel
    ways joined to it end to end (one bore drawn as several ways)."""
    lens, nodes = {}, {}
    for w in tunnel_ways:
        pts = [(float(x), float(y)) for x, y in w.points]
        if len(pts) >= 2:
            lens[int(w.id)] = sum(math.dist(a, b) for a, b in zip(pts, pts[1:]))
            for q in (pts[0], pts[-1]):
                nodes.setdefault((round(q[0], 2), round(q[1], 2)), set()).add(int(w.id))
    parent = {w: w for w in lens}

    def root(w):
        while parent[w] != w:
            parent[w] = parent[parent[w]]
            w = parent[w]
        return w
    for ws in nodes.values():
        first, *rest = sorted(ws)
        for w in rest:
            parent[root(w)] = root(first)
    run: dict[int, float] = {}
    for w, n in lens.items():
        run[root(w)] = run.get(root(w), 0.0) + n
    return {w: run[root(w)] for w in lens}


def _plan_size(plan, end_xy: XY, into: "XY | None") -> float:
    """``plan``'s larger extent, along the bore (``into``) or across it."""
    pts = [c for q in getattr(plan, "geoms", [plan]) for c in q.exterior.coords]
    if into is None:
        x0, y0, x1, y1 = plan.bounds
        return math.hypot(x1 - x0, y1 - y0)
    along = [_station(c, end_xy, into) for c in pts]
    across = across_bore(pts, end_xy, into)
    return max(max(along) - min(along), max(across) - min(across))


def _tunnel_mouth(plan, end_xy: XY, into: "XY | None", run_m: float, law
                  ) -> tuple[bool, str]:
    """Whether the roofed object over a bore end is that tunnel's MOUTH
    though it stands on the author's ground, and the reading: the mapped
    bore runs at least ``mouth_bore_min_ratio`` times the object's own size
    — a mouth object at grade on the uncut ground (KBUF ``Road_Tunnel.obj``,
    bores 231 m / 243 m), never a booth on a stub its own length (KDEN) nor
    a building over a bore (owner RULINGS 2026-11-21d, #2221)."""
    if plan is None or plan.is_empty:
        return False, ""
    size = _plan_size(plan, end_xy, into)
    ratio = float(law.tables.structures.tunnel.object.mouth_bore_min_ratio)
    if run_m < ratio * size:
        return False, (f"its bore runs {run_m:.1f} m, under mouth_bore_min_ratio {ratio:g} x "
                       f"its size {size:.1f} m (RULINGS 2026-11-21d)")
    return True, (f"its bore runs {run_m:.1f} m, at least mouth_bore_min_ratio {ratio:g} x "
                  f"its size {size:.1f} m: a tunnel mouth (RULINGS 2026-11-21d)")


def read_portals(objects: _t.Sequence[_obj8.PlacedObject], cache: _obj8.ResourceCache,
                 law, tunnel_ways, taken: _t.AbstractSet[str] = frozenset(), dem_z=None,
                 ground=None, at_grade: "list[_GradeEnd] | None" = None,
                 roads: _t.Sequence = ()) -> tuple[list[Portal], list[str]]:
    """Every pack portal standing over a mapped bore end, and one refusal
    line per roofed-looking candidate that is not one.  ``dem_z`` (the
    airport's DEM) reads a TALL portal: a roof over ``mouth_depth_m`` is a
    portal only where the surveyed ground stands on it
    (:func:`_ground_covers_roof`; owner 2026-11-04 ENTC "seating at the
    bottom of a ramp sized to the object"), a building on the bore where
    it does not.  ``ground`` (``airport/below_grade_witness.ground_of``) reads every
    other roofed one: a portal only where it stands under the author's
    ground (:func:`_at_grade`); the bore ends one stands over at grade are
    appended to ``at_grade``.  An object whose walls hang under its zero
    is read by ``airport/footed_portal`` (``roads``: the mapped non-tunnel
    roads a bore end runs on into it)."""
    from .footed_portal import _road_under, footed_parts, read_footed_portals
    tn = law.tables.structures.tunnel
    tol = float(tn.object.bore_end_tolerance_m)
    ends = _ends(tunnel_ways)
    if not ends:
        return [], []
    tree = STRtree([Point(p) for p, _w in ends])
    into = _bore_dirs(tunnel_ways)
    readings: dict[str, "tuple[float, float] | str"] = {}
    runs: "dict[int, float] | None" = None
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
        if g is not None and edge_wall_reading(o, g, law) is not None:
            # an EDGE-WALL BRIDGE pins by its back's CROSSING, never by an
            # end's distance (``planar/bridge_span``, owner RULINGS 2026-10-28d)
            continue
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
        if isinstance(r, str) and r.startswith(_WALLS_UNDER) and dem_z is not None:
            parts = footed_parts(g, cache.genuine(o.resolved), law)
            if isinstance(parts, str):
                refused.append(f"{o.id} {name}: {parts}")
                continue
            got = read_footed_portals(o, parts, ends, roads, law, dem_z,
                                      zero_of(o, ground.msl) if ground is not None
                                      else float(o.anchor_z + o.agl_m), into)
            if not got:
                refused.append(f"{o.id} {name}: roofed on walls under its zero, but no part "
                               f"pins a mapped bore end (#2069)")
            out.extend(got)
            continue
        if isinstance(r, str):
            continue
        depth, roof_area, plan = r
        # THE ROOF STANDS OVER THE BORE END: a plate's worth somewhere in a
        # large object's plan box is not a portal (EGGW ``eggw_cabins.obj``,
        # 400 m of scattered cabins, boxed both ends of bore -908)
        roof = _fe.enter([plan], _obj8.placement_affine(o.xy, o.heading_deg),
                         _fe.quantum(law))[0]
        # #1689: a TALL portal (its roof over ``mouth_depth_m``, held to the
        # survey's cover below) pins the end too where the mapped road
        # leaving it runs under its roof within the shortest lawful ramp --
        # the ``footed_portal`` argument: no ramp comes up to grade and goes
        # down again in that run (KBNA Murfreesboro west portal: roof 6.8 m
        # up the primary road from its bore's mapped end)
        tall = depth > tn.mouth_depth_m
        run = float(tn.mouth_depth_m) / float(tn.ramp_max_grade)
        near = [j for j in near
                if roof is not None and (roof.distance(Point(ends[j][0])) <= tol or (
                    tall and _road_under(ends[j][0], roof, roads, run)))]
        if not near:
            continue
        if depth < law.tables.structures.bridge.clearance_minimum_m:
            refused.append(f"{o.id} {name}: roofed over a bore end, but its roof top "
                           f"{depth:.2f} m clears no road (bridge.clearance_minimum_m "
                           f"{law.tables.structures.bridge.clearance_minimum_m}): a deck, "
                           f"not a portal")
            continue
        cover: dict[int, float] = {}
        grade = "" if depth > tn.mouth_depth_m else _at_grade(
            o, cache, _roof_over(roof, [ends[j][0] for j in near], tol), law, ground)
        foot = _solids_plan(o, g, cache.genuine(o.resolved), law)
        if grade:
            # 2026-11-21d: an end whose bore runs far past the object is its
            # tunnel's mouth; the others stay ends at grade
            runs = runs if runs is not None else _bore_runs(tunnel_ways)
            read = {j: _tunnel_mouth(roof if foot is None else foot, ends[j][0],
                                     into.get(ends[j]), runs.get(ends[j][1], 0.0), law)
                    for j in near}
            mouth = {j: why for j, (ok, why) in read.items() if ok}
            low = [j for j in near if j not in mouth]
            if low:
                refused.append(f"{o.id} {name}: {grade}; {read[low[0]][1]}")
            if at_grade is not None:
                at_grade.extend(_GradeEnd(ends[j][0], ends[j][1], o.id, o.path, grade)
                                for j in low)
            refused.extend(f"{o.id} {name}: at grade, but {mouth[j]}" for j in sorted(mouth))
            near = sorted(mouth)
            if not near:
                continue
        if depth > tn.mouth_depth_m:
            cover = {j: z for j in near
                     if (z := _ground_covers_roof(roof, ends[j][0], dem_z, law,
                                                  into.get(ends[j]))) is not None}
            near = sorted(cover)
            if not near:
                refused.append(f"{o.id} {name}: roofed over a bore end, but its roof top "
                               f"{depth:.2f} m stands over the bore law's mouth_depth_m "
                               f"{tn.mouth_depth_m} and no surveyed ground stands on its "
                               f"roof: a building on the bore, not a portal")
                continue
        framed: list = []            # #1689 R5 R1: the frame, read once
        for j in near:
            xy, wid = ends[j]
            # an end the road pins up the open road (#1689) opens over the
            # roof within its own reach of the end, never the whole wall top
            # the roof is (KBNA west: an 86 m diagonal parapet, 19 m within
            # the reach)
            off = roof.distance(Point(xy))
            local = roof if off <= tol else roof.intersection(Point(xy).buffer(off + tol))
            # a tall portal's floor is the ground ON ITS ROOF less its roof
            # top: the ground at the cap stands inside the surveyed cut
            floor = (cover[j] - depth) if j in cover else None
            # #1689 R5 R2: a tall portal's COVER and SOFFIT, read off its frame
            if floor is not None and not framed:
                framed.append(_frame(o, objects, cache, foot, law))
            cov = None if floor is None or framed[0] is None else _covers(framed[0], xy, o, law)
            # #1689 R5 R4: up the open road the opening is the soffit's
            width, edges = (_roof_opening(cov[2], xy, into.get((xy, wid)), tol)
                            if off > tol and cov is not None and cov[2] is not None else
                            _roof_opening(local, xy, into.get((xy, wid)),
                                          tol if off <= tol else off + tol))
            # #1689 R2 A3 / R3: a TALL portal STATES ITS TOP -- its roof plan
            # at its zero (the floor) plus its FRONT WALL's top (the cover
            # the survey read on the roof where no wall stands at the end):
            # the ground round it is graded to it (``planar/entrance_skirt``;
            # no bottom: the mouth rule is a roofed portal's)
            front = None if floor is None else _front_wall_top(
                o, g, cache.genuine(o.resolved), local, law)
            # #1689 R4: its WINGS standing at that top are part of the top
            wing = None if front is None else _wing_plan(
                o, g, roof, local, front, xy, into.get((xy, wid)), law)
            # #1689 R5 R3: the cover, not the object's own roof, is the top
            top = roof if cov is None else cov[1]
            out.append(Portal(o.id, o.path, xy, wid, depth, roof_area,
                              (float(o.xy[0]), float(o.xy[1])),
                              floor_z=floor, opening_m=width, opening_xy=edges,
                              face_plan=(top if wing is None else top.union(wing))
                              if j in cover else None,
                              face_top_z=None if floor is None else float(
                                  cover[j] if front is None else floor + front),
                              top_plan=roof, footprint=foot,
                              zero_z=None if ground is None else zero_of(o, ground.msl),
                              cover_plan=None if cov is None else cov[1],
                              cover_top_z=None if cov is None else float(floor + cov[0]),
                              parapet_plan=None if cov is None else _parapet(
                                  o, framed[0], cov[0], law),
                              at_grade=bool(grade)))
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
