"""A ROOFED PORTAL'S OWN FLOOR IS THE CUT WHERE ITS ROW STANDS OFF ITS ROAD
(#1949; the portal law of ``airport/portal_objects`` and the floor law of
``airport/object_floor``, owner 2026-11-06 "mouths seat at that floor").

A roofed portal over a bore end states its road: the road at the mouth is
the object's zero and the ground stands on its roof, so the road runs
``depth_m`` (its roof top) under the ground at the bore end
(``Portal.depth_m``; a TALL portal's ``floor_z`` states it absolutely and
the structure pass seats it there already).  A portal whose row reads its
zero there (within ``cover_flush_m``) stands on its road as authored, and
one with no floor plate under its roof (the road is the terrain) keeps its
bore's mouth ramp as the cut: nothing here applies to either.  One whose row reads its
zero OFF that road (OMDB ``tunner_5_1``: ``OBJECT_AGL`` -4.8 off a DEM
bump at its anchor, zero 3.63 where its roof puts the road at -2.11 — the
box stood 5.7 m proud with no cut under it) is moved onto it, and the
ground under it is ITS OWN FLOOR: the lowest near-horizontal faces of the
object, per triangle, at that zero — its road and the ramp up to its open
end — one ``object_floor.ObjectFloor`` that every consumer of an object
floor reads unchanged (cells, pins, the bore mouth seated on it, seats).
The rows co-placed with it (its walls, its lights:
``hanging_objects._co_placed``) are its frame and move with it.

Every number is a law-table value; nothing here names a pack or an airport.
"""
from __future__ import annotations

import types as _types
import typing as _t

import numpy as np
import shapely
from shapely.ops import unary_union

from ..geom.lowest_face import floor_z_at
from .below_grade_witness import placed_all
from .hanging_objects import _co_placed
from .object_cut import _base, _face_normals_y, valid_polygon

__all__ = ["read_portal_floors"]


def _lowest(F: np.ndarray, tol: float) -> np.ndarray:
    """The faces of ``F`` (``(n, 3, 3)``: plan x, y and z) that are the
    lowest surface at their own centroid (within ``tol``): the floor under
    a roof, never the roof over it."""
    c = F.mean(axis=1)
    low = floor_z_at(F, c[:, 0], c[:, 1])
    return F[~(c[:, 2] > low + tol)]


def _road_zero(p, ground) -> float:
    """The zero the portal ``p``'s roof states: the ground at its bore end
    less its roof top."""
    end = np.asarray(ground([p.end_xy[0]], [p.end_xy[1]]), float).ravel()
    return float(end[0]) - float(p.depth_m)


def read_portal_floors(portals: _t.Sequence, objects: _t.Sequence, cache, law, ground,
                       scale=(1.0, 1.0), taken: _t.AbstractSet[str] = frozenset()
                       ) -> tuple[list, list[str]]:
    """``(floors, notes)``: an ``object_floor.ObjectFloor`` for every
    roofed portal (no tall floor, no entrance face, no hanging walls) with a
    floor plate under its roof whose row reads its zero more than ``cover_flush_m`` off
    the road its roof states (module doc).  ``ground(xs, ys)`` is the design
    ground at the bore end; ``taken`` the placements another floor reads."""
    from .object_floor import FLOOR_REF, ObjectFloor
    ob = law.tables.structures.tunnel.object
    tol = float(ob.cover_flush_m)
    by_id = {o.id: o for o in objects}
    out: list = []
    notes: list[str] = []
    seen: set[str] = set(taken)
    for p in portals:
        if (p.hanging or p.bottom_y is not None or p.floor_z is not None or p.opening_m <= 0.0
                or p.zero_z is None or p.object_id in seen):
            continue
        o = by_id.get(p.object_id)
        g = cache.geometry(o.resolved) if o is not None and o.resolved else None
        zero = _road_zero(p, ground)
        if g is None or not len(g.solid) or zero != zero or abs(float(p.zero_z) - zero) <= tol:
            continue
        seen.add(p.object_id)
        hz = g.solid[_face_normals_y(g.vertices, g.solid) >= ob.plate_normal_y_min]
        if not len(hz):
            continue
        F = placed_all(o, _types.SimpleNamespace(vertices=g.vertices, solid=hz), zero, scale)
        # its FLOOR: the lowest faces standing under its roof top by more
        # than cover_flush_m — a portal with no floor plate (the road is
        # the terrain) states none, and its bore's mouth ramp stays the cut
        faces = _lowest(F, tol)
        faces = faces[faces[:, :, 2].mean(axis=1) < zero + float(p.depth_m) - tol]
        tris = shapely.polygons(faces[:, :, :2]) if len(faces) else np.zeros(0, object)
        foot = valid_polygon(unary_union(tris[shapely.area(tris) > 1e-6])) if len(tris) \
            else None
        if foot is None or foot.area < ob.plate_min_area_m2:
            notes.append(f"{o.id} {_base(o.path)}: a portal off the road its roof states "
                         f"({float(p.zero_z):.2f} vs {zero:.2f}), but no floor of a plate's "
                         f"worth under its roof: its bore's mouth ramp stays the cut")
            continue
        frame = [q for q in objects if q.id not in seen
                 and _co_placed(o, q, float(ob.cover_placement_tol_m))]
        seen.update(q.id for q in frame)
        fz = float(faces[:, :, 2].min())
        note = (f"object floor portal {_base(o.path)}: its row reads its zero "
                f"{float(p.zero_z):.2f}, its roof top {float(p.depth_m):.2f} puts the road at "
                f"{zero:.2f} at bore {p.way_id}'s end -> its frame ({1 + len(frame)} "
                f"placements) seated there, its floor ({len(faces)} faces over "
                f"{foot.area:.0f} m2, lowest {fz:.2f}) is the cut")
        notes.append(note)
        seats = tuple((q.id, q.path, zero) for q in (o, *frame))
        out.append(ObjectFloor(f"{FLOOR_REF}{_base(o.path)}@portal{len(out)}", o.id, o.path,
                               (), zero, fz, foot, faces, (note,), seats))
    return out, notes
