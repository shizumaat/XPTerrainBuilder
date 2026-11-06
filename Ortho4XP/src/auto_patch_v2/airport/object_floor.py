"""A TRENCH OBJECT'S OWN FLOOR IS THE CUT (owner 2026-11-06T00:07Z, #1903):
"they have their own ramps so it should be a simple continuous trench
tracing the whole object for each of the tunnels".

THE RULE.  A pack trench, tunnel or underpass object that carries its own
floor and ramps defines the cut: the ground inside the object's footprint
is the object's own floor geometry — its floor plates and ramps, per
triangle, at the object's seat — projected over the whole footprint end to
end, including the ramps beyond its walls to the lips.  It is not a
profile along an axis that stops at the portals.  Mouths seat at that
floor; walls end on it.

THE WITNESS (geometry, never a name).  A FLOOR OBJECT is a placement whose
solid states a floor (``hanging_objects._has_floor``: a plate's worth of
near-horizontal faces ``shell_floor_min_m`` under its zero) and is a floor
rather than a structure — near-horizontal faces carry at least
``floor_object_min_share`` of its solid plan area — standing CO-PLACED
with the tunnel's cover (another placement within ``cover_placement_tol_m``,
same heading, whose solids reach ``shell_floor_min_m`` under its zero and
which is not itself a floor: the walls and roof the floor belongs to; EGLL
``Na.obj`` beside ``N.obj``).  The cover is the evidence that the floor is
a tunnel's, not a sea barrier's or a basement's.

THE SURFACE.  The floor's near-horizontal faces that reach under
``cover_flush_m`` below the object's zero, placed in the airport frame with
absolute z (the placement's zero + authored y); where two faces overlap in
plan the LOWEST is the floor (:func:`floor_z_at`).  The footprint is their
plan union.  ``planar/object_floor_cells`` cuts it into the map and
``constraints/object_floor`` pins every vertex of it to the surface.

Every number is a law-table value; nothing here names a pack or an airport.
"""
from __future__ import annotations

import dataclasses as _dc
import typing as _t

import numpy as np
import shapely
import shapely.affinity
from shapely.ops import unary_union

from . import obj8 as _obj8
from . import terrain_shaped as _ts
from .hanging_objects import _co_placed, _has_floor
from .object_cut import _base, _face_normals_y, _plan_segments, placement_order, valid_polygon

__all__ = ["ObjectFloor", "read_object_floors", "floor_z_at", "seat_records", "floor_portals",
           "FLOOR_REF",
           "FLOOR_WALL_REF", "FLOOR_SEAT"]

#: The planar ref of a floor's cut face (``FLOOR_REF + id``) and of the
#: void band around it (``FLOOR_WALL_REF + id``).
FLOOR_REF = "object_floor:"
FLOOR_WALL_REF = "object_floor_wall:"
#: the seat record's ``seat`` value (``terrain_shaped.row_seats``): the row
#: written whole, ``OBJECT_MSL`` at the zero its floor was cut from
FLOOR_SEAT = _ts.OBJECT_FLOOR_SEAT


@_dc.dataclass(frozen=True)
class ObjectFloor:
    """One trench object's floor in the AIRPORT frame: ``faces`` the
    ``(n, 3, 3)`` placed ``(x, y, z)`` corners of its below-grade floor
    faces (z absolute), ``footprint`` their plan union (Polygon or
    MultiPolygon), ``covers`` the co-placed placement ids it floors."""

    id: str
    object_id: str
    resource: str
    covers: tuple[str, ...]
    zero_z: float
    floor_z: float
    footprint: object
    faces: np.ndarray = _dc.field(repr=False, compare=False)
    notes: tuple[str, ...] = ()
    #: ``(placement id, resource, zero)`` of the floor and each cover: the
    #: rows written WHOLE at their read zero (:func:`seat_records`) — the cut
    #: is that zero's floor, so the authored seat is the one that lands on it
    seats: tuple[tuple[str, str, float], ...] = ()


def floor_z_at(faces: np.ndarray, xs: _t.Sequence[float], ys: _t.Sequence[float],
               edge_m: float = 0.0) -> np.ndarray:
    """The floor's z under each ``(x, y)``: the LOWEST face whose plan
    triangle holds the point (its plane there); ``nan`` where none does.
    ``edge_m`` > 0 also reads a point up to that far outside the nearest
    face, on that face's plane (a ring vertex the map snapped a hair off
    the footprint, or the void band's floor-side ring)."""
    xs = np.asarray(xs, float)
    ys = np.asarray(ys, float)
    out = np.full(xs.shape, np.nan)
    if not len(faces) or not len(xs):
        return out
    x0, x1, x2 = faces[:, 0, 0], faces[:, 1, 0], faces[:, 2, 0]
    y0, y1, y2 = faces[:, 0, 1], faces[:, 1, 1], faces[:, 2, 1]
    z0, z1, z2 = faces[:, 0, 2], faces[:, 1, 2], faces[:, 2, 2]
    den = (y1 - y2) * (x0 - x2) + (x2 - x1) * (y0 - y2)
    ok = np.abs(den) > 1e-9
    lo_x = np.minimum(np.minimum(x0, x1), x2) - edge_m
    hi_x = np.maximum(np.maximum(x0, x1), x2) + edge_m
    lo_y = np.minimum(np.minimum(y0, y1), y2) - edge_m
    hi_y = np.maximum(np.maximum(y0, y1), y2) + edge_m
    for k in range(len(xs)):
        x, y = xs[k], ys[k]
        c = np.flatnonzero(ok & (lo_x <= x) & (x <= hi_x) & (lo_y <= y) & (y <= hi_y))
        if not len(c):
            continue
        w0 = ((y1[c] - y2[c]) * (x - x2[c]) + (x2[c] - x1[c]) * (y - y2[c])) / den[c]
        w1 = ((y2[c] - y0[c]) * (x - x2[c]) + (x0[c] - x2[c]) * (y - y2[c])) / den[c]
        w2 = 1.0 - w0 - w1
        z = w0 * z0[c] + w1 * z1[c] + w2 * z2[c]
        least = np.minimum(np.minimum(w0, w1), w2)
        inside = least >= -1e-9
        if inside.any():
            out[k] = float(z[inside].min())
        elif edge_m > 0.0:
            # how far outside each candidate the point stands, in metres:
            # the least barycentric weight times the face's height there
            h = np.abs(den[c]) / np.maximum(np.hypot(x1[c] - x2[c], y1[c] - y2[c]), 1e-9)
            near = -least * h <= edge_m
            if near.any():
                out[k] = float(z[near].min())
    return out


def _floor_share(g: "_obj8.ObjGeometry | None", law) -> float:
    """The share of the solid's SURFACE (3D area) its near-horizontal faces
    carry — a wall has no plan area, so plan area cannot tell a cover from
    a floor."""
    ob = law.tables.structures.tunnel.object
    if g is None or not len(g.solid):
        return 0.0
    v, t = g.vertices, g.solid
    p0, p1, p2 = v[t[:, 0]], v[t[:, 1]], v[t[:, 2]]
    area = 0.5 * np.linalg.norm(np.cross(p1 - p0, p2 - p0), axis=1)
    tot = float(area.sum())
    if tot <= 0.0:
        return 0.0
    return float(area[_face_normals_y(v, t) >= ob.plate_normal_y_min].sum()) / tot


def _walled_share(foot, p: _obj8.PlacedObject, cache: _obj8.ResourceCache, law) -> float:
    """The share of the floor footprint's ring (frame) within
    ``wall_face_max_thickness_m`` of ``p``'s wall faces reaching
    ``shell_floor_min_m`` under its zero — the cover's walls standing on
    the floor's edges ("walls end on it")."""
    ob = law.tables.structures.tunnel.object
    g = cache.geometry(p.resolved)
    if g is None or not len(g.solid):
        return 0.0
    v, t = g.vertices, g.solid
    w = t[_face_normals_y(v, t) < ob.plate_normal_y_min]
    if len(w):
        w = w[v[w][:, :, 1].min(axis=1) <= -ob.shell_floor_min_m]
    segs = _plan_segments(v, w) if len(w) else []
    if not segs:
        return 0.0
    a, b, d, e, xo, yo = _obj8.placement_affine(p.xy, p.heading_deg)
    walls = shapely.affinity.affine_transform(unary_union(segs), [a, b, d, e, xo, yo])
    ring = foot.boundary
    if ring.length <= 0.0:
        return 0.0
    return float(ring.intersection(walls.buffer(ob.wall_face_max_thickness_m)).length
                 / ring.length)


def _placed_floor(o: _obj8.PlacedObject, g: _obj8.ObjGeometry, zero: float, law):
    """``(faces, footprint)`` of the floor's below-grade faces in the frame,
    or ``None`` when they carry less than a plate's worth."""
    ob = law.tables.structures.tunnel.object
    v, t = g.vertices, g.solid
    hz = t[_face_normals_y(v, t) >= ob.plate_normal_y_min]
    if len(hz):
        hz = hz[v[hz][:, :, 1].min(axis=1) < -ob.cover_flush_m]
    if not len(hz):
        return None
    a, b, d, e, xo, yo = _obj8.placement_affine(o.xy, o.heading_deg)
    F = v[hz]
    px = a * F[:, :, 0] + b * F[:, :, 2] + xo
    py = d * F[:, :, 0] + e * F[:, :, 2] + yo
    faces = np.stack([px, py, zero + F[:, :, 1]], axis=2)
    tris = shapely.polygons(np.stack([px, py], axis=2))
    tris = tris[shapely.area(tris) > 1e-6]
    foot = valid_polygon(unary_union(tris)) if len(tris) else None
    if foot is None or foot.area < ob.plate_min_area_m2:
        return None
    return faces, foot


def _within(faces: np.ndarray, outline, law):
    """``(faces, footprint)`` of the placed floor faces whose plan centroid
    stands inside ``outline``, or ``None`` short of a plate's worth."""
    ob = law.tables.structures.tunnel.object
    if outline is None or outline.is_empty:
        return None
    cx, cy = faces[:, :, 0].mean(axis=1), faces[:, :, 1].mean(axis=1)
    keep = shapely.contains_xy(outline.buffer(1.0), cx, cy)
    if not keep.any():
        return None
    faces = faces[keep]
    tris = shapely.polygons(faces[:, :, :2])
    foot = valid_polygon(unary_union(tris[shapely.area(tris) > 1e-6]))
    if foot is None or foot.area < ob.plate_min_area_m2:
        return None
    return faces, foot


def read_object_floors(objects: _t.Sequence[_obj8.PlacedObject], cache: _obj8.ResourceCache,
                       law, msl: _t.Mapping[str, float],
                       taken: _t.AbstractSet[str] = frozenset(),
                       shells: _t.Mapping[str, str] | None = None
                       ) -> tuple[list[ObjectFloor], list[str]]:
    """Every FLOOR OBJECT (module doc) as an :class:`ObjectFloor`, and one
    note per floor read or refused.  ``taken`` are placement ids another
    reader already cuts by their own floor (an object is read once);
    ``shells`` maps each placement ``object_cut`` admitted as a §33 (6) B
    shell (walls and floor in one object) to ``(its cover's placement id,
    the region between its walls)`` — only those are read as floors
    without being floor objects, only that cover is theirs, and only their
    faces over that region are the floor (a shell's own model can reach far
    past its trench: LGAV ``Trench_06``, 362,036 m2 of plates).  A shared-datum pack co-places everything (LGAV
    ``Trench_0x``, one anchor), so co-placement alone is no tunnel
    evidence: a floor object's cover must also stand its walls ON the
    floor's edges — at least ``floor_walled_min_share`` of the footprint's
    ring within ``wall_face_max_thickness_m`` of the cover's deep wall
    faces (EGLL 82-99 %; LGAV's stack and KBNA ``Metropolitan-part7``
    0-2 %)."""
    ob = law.tables.structures.tunnel.object
    placed = [o for o in placement_order(objects)
              if o.resolved is not None and not _obj8.is_stock_library_resource(o.path)]
    out: list[ObjectFloor] = []
    notes: list[str] = []
    k_by_res: dict[str, int] = {}
    for o in placed:
        if o.id in taken or not _has_floor(cache, o, law):
            continue
        g = cache.geometry(o.resolved)
        share = _floor_share(g, law)
        mates = [p for p in placed
                 if p.id != o.id and _co_placed(o, p, ob.cover_placement_tol_m)]
        shells = shells or {}
        if share >= ob.floor_object_min_share:
            # a FLOOR object: its cover is a co-placed structure hanging
            # under its zero whose walls stand on the floor's edges
            covers = [p for p in mates
                      if cache.y_range(p.resolved)[0] <= -ob.shell_floor_min_m
                      and _floor_share(cache.geometry(p.resolved), law)
                      < ob.floor_object_min_share]
            placed_floor = _placed_floor(o, g, 0.0, law)
            covers = [p for p in covers if placed_floor is not None
                      and _walled_share(placed_floor[1], p, cache, law)
                      >= ob.floor_walled_min_share]
        elif o.id in shells:
            # a SHELL (its own walls and floor, §33 (6) B): its cover is the
            # one object_cut paired it with
            covers = [p for p in mates if p.id == shells[o.id][0]]
        else:
            continue
        if not covers:
            notes.append(f"{o.id} {_base(o.path)}: a floor ({share:.0%} near-horizontal) with "
                         f"no co-placed cover (walls under its zero, or a flush hard deck "
                         f"over its own walls): not a tunnel's floor")
            continue
        zero = _zero(o, msl)
        got = _placed_floor(o, g, zero, law)
        if got is None:
            notes.append(f"{o.id} {_base(o.path)}: no below-grade floor face of a plate's worth")
            continue
        faces, foot = got
        if o.id in shells and share < ob.floor_object_min_share:
            got = _within(faces, shells[o.id][1], law)
            if got is None:
                notes.append(f"{o.id} {_base(o.path)}: no floor face over its trench outline")
                continue
            faces, foot = got
        k = k_by_res.get(o.path, 0)
        k_by_res[o.path] = k + 1
        fz = float(faces[:, :, 2].min())
        note = (f"object floor {_base(o.path)}@{k}: {len(faces)} faces over {foot.area:.0f} m2, "
                f"floor {fz:.2f} (zero {zero:.2f}), the floor of "
                + ", ".join(_base(p.path) for p in covers))
        notes.append(note)
        seats = tuple((p.id, p.path, _zero(p, msl)) for p in (o, *covers))
        out.append(ObjectFloor(f"{FLOOR_REF}{_base(o.path)}@{k}", o.id, o.path,
                               tuple(p.id for p in covers), zero, fz, foot, faces, (note,),
                               seats))
    return out, notes


def _zero(o: _obj8.PlacedObject, msl: _t.Mapping[str, float]) -> float:
    """The placement's zero as read: its MSL elevation, or the ground under
    its anchor plus its AGL."""
    return float(msl[o.id]) if o.kind == "OBJECT_MSL" else float(o.anchor_z + o.agl_m)


def seat_records(floors: _t.Iterable[ObjectFloor]) -> list[dict[str, _t.Any]]:
    """One seat record per placement of every object floor (the floor and
    its covers): written WHOLE as ``OBJECT_MSL`` at the zero the cut was
    read from ("mouths seat at that floor; walls end on it") — never split
    and re-seated on feet that stand in its own cut."""
    return [{"id": pid, "resource": res, "datum": "object_floor", "seat": FLOOR_SEAT,
             "elevation": round(float(z), 3)}
            for f in floors for pid, res, z in f.seats]


def floor_portals(portals: _t.Sequence, floors: _t.Sequence[ObjectFloor]) -> tuple:
    """The pack portals with every pin a trench object's floor states read
    off THAT floor (#1903, owner 2026-11-06 "mouths seat at that floor"): a
    portal on the floor object or one of its covers takes the floor's own
    height at the footprint point nearest its bore end — never the floor's
    deepest level, nor a face bottom the object stage would re-seat (EGLL
    11 west mouth: the portal pinned 16.14, 11b's lowest plate, where the
    floor stands 17.16 at that end).  A portal off every floor is unchanged."""
    by_id = {pid: f for f in floors for pid, _r, _z in f.seats}
    if not by_id:
        return tuple(portals)
    out = []
    for p in portals:
        f = by_id.get(p.object_id)
        if f is None:
            out.append(p)
            continue
        from shapely.geometry import Point
        from shapely.ops import nearest_points
        q = nearest_points(f.footprint, Point(p.end_xy))[0]
        z = floor_z_at(f.faces, [q.x], [q.y], edge_m=0.5)[0]
        if z != z:
            out.append(p)
            continue
        out.append(_dc.replace(p, floor_z=float(z), bottom_y=None))
    return tuple(out)
