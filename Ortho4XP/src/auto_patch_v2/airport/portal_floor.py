"""A ROOFED PORTAL'S OWN FLOOR IS THE CUT WHERE ITS ROW STANDS OFF ITS ROAD
(#1949; the portal law of ``airport/portal_objects`` and the floor law of
``airport/object_floor``, owner 2026-11-06 "mouths seat at that floor").

A roofed portal over a bore end states its road: the road at the mouth is
the object's zero and the ground stands on its roof, so the road runs
``depth_m`` (its roof top) under the ground at the bore end
(``Portal.depth_m``; a TALL portal's ``floor_z`` states it absolutely and
the structure pass seats it there already).  A portal whose row reads its
zero there (within ``cover_flush_m``) stands on its road as authored, and
one with no floor plate under its roof (the road is the terrain; an arch's
soffit is no floor, #2225) keeps its bore's mouth ramp as the cut and is
seated on it by ``planar/portal_level``: nothing here applies to either.  One whose row reads its
zero OFF that road (OMDB ``tunner_5_1``: ``OBJECT_AGL`` -4.8 off a DEM
bump at its anchor, zero 3.63 where its roof puts the road at -2.11 — the
box stood 5.7 m proud with no cut under it) is moved onto it, and the
ground under it is ITS OWN FLOOR: the lowest near-horizontal faces of the
object, per triangle, at that zero — its road and the ramp up to its open
end — one ``object_floor.ObjectFloor`` that every consumer of an object
floor reads unchanged (cells, pins, the bore mouth seated on it, seats).
The rows co-placed with it (its walls, its lights:
``hanging_objects._co_placed``) AND standing in the structure it belongs to
are its frame and move with it (:func:`_frame`).  Co-placement alone is no frame: a
shared-datum pack hangs a whole airport off one origin (#2266 MMUN: a road
bridge's portal led all 115 rows of the pack, terminals and hangars, 4.59 m
under the plateau they stood on).

Every number is a law-table value; nothing here names a pack or an airport.
"""
from __future__ import annotations

import types as _types
import typing as _t

import numpy as np
import shapely
from shapely.ops import unary_union

from ..geom.lowest_face import every_z_at, floor_z_at
from .below_grade_witness import placed_all
from .hanging_objects import _co_placed
from .object_cut import _base, _face_normals_y, valid_polygon
from .walled_pit import _in_pit, hard_deck_share

__all__ = ["read_portal_floors"]


def _lowest(F: np.ndarray, tol: float) -> np.ndarray:
    """The faces of ``F`` (``(n, 3, 3)``: plan x, y and z) that are the
    lowest surface at their own centroid (within ``tol``): the floor under
    a roof, never the roof over it."""
    c = F.mean(axis=1)
    low = floor_z_at(F, c[:, 0], c[:, 1])
    return F[~(c[:, 2] > low + tol)]


def _carries_passage(faces: np.ndarray, F: np.ndarray, headroom: float, roof_z: float,
                     tol: float) -> np.ndarray:
    """Per face of ``faces``, whether it is a FLOOR rather than a SOFFIT
    (#2225).  A soffit is the underside of the material that carries the
    roof: the object (``F``) stands over it up to its roof top (``roof_z``,
    within ``tol``) and every gap between the levels over it (deduplicated
    to the millimetre -- a two-sided face is one level) is that material's
    thickness, none the road's ``headroom`` (RJTT ``tunnel6.obj``: the
    soffit at y 5, its lintel's top the roof at 6, no floor plate).  A face
    with nothing over it (the ramp out to the open end), a floor plate's
    own underside (its road's headroom over its top) and a kerb or ramp
    slab's underside under open air (LFPG ``2A_21.obj``: its top 2.0-2.3
    under a roof at 6.1) stay floors: ``faces`` keep today's lowest
    reading and never gain one."""
    c = faces.mean(axis=1)
    keep = np.ones(len(faces), bool)
    for k, zs in enumerate(every_z_at(F, c[:, 0], c[:, 1])):
        lv = np.unique(np.round(zs[zs > c[k, 2] + 1e-3], 3))
        if len(lv) and lv[-1] >= roof_z - tol:
            keep[k] = bool((np.diff(np.concatenate(([c[k, 2]], lv))) >= headroom).any())
    return keep


def _road_zero(p, ground) -> float:
    """The zero the portal ``p``'s roof states: the ground at its bore end
    less its roof top."""
    end = np.asarray(ground([p.end_xy[0]], [p.end_xy[1]]), float).ravel()
    return float(end[0]) - float(p.depth_m)


def _plan(q, cache, scale) -> np.ndarray:
    """``q``'s solid triangles in plan (frame metres; empty with none)."""
    g = cache.geometry(q.resolved) if q.resolved else None
    if g is None or not len(g.solid):
        return np.zeros(0, object)
    t = shapely.polygons(placed_all(q, g, 0.0, scale)[:, :, :2])
    return t[shapely.area(t) > 1e-6]


def _frame(o, foot, objects: _t.Sequence, seen: _t.AbstractSet[str], cache, law,
           scale) -> list:
    """The placements portal ``o``'s seat leads (#2266): co-placed with it
    (``hanging_objects._co_placed``, ``cover_placement_tol_m``) AND standing
    in the structure it belongs to -- half a placement's solid plan within
    the plan already led (the portal's solids and its floor ``foot``, then
    every placement led, each grown by ``bore_end_tolerance_m``), the half
    of ``walled_pit._in_pit``, read on the solids rather than the authored
    plan box (a bridge laid diagonally across its own box fills a sixth of
    it); a row with no solid (its lights) where half its lights' box
    stands in that plan.  The lead grows piece by piece, so the deck, walls and parapets
    of one bridge move as one; the frame's placements elsewhere (a shared
    datum hangs a whole airport off one origin) keep their own seats."""
    ob = law.tables.structures.tunnel.object
    tol, reach = float(ob.cover_placement_tol_m), float(ob.bore_end_tolerance_m)
    mates = {q.id: (q, _plan(q, cache, scale)) for q in objects
             if q.id not in seen and q.resolved and _co_placed(o, q, tol)}
    own = _plan(o, cache, scale)
    plan = unary_union([foot, *own]).buffer(reach)
    led: list = []
    grew = True
    while grew:
        grew = False
        shapely.prepare(plan)
        for k, (q, t) in list(mates.items()):
            if not len(t):
                # no solid (a lights-only row): where its lights stand
                if _in_pit(q, plan, cache, 0.0):
                    led.append(q)
                    del mates[k]
                continue
            if not shapely.intersects(t, plan).any():
                continue
            if shapely.area(shapely.intersection(t, plan)).sum() >= 0.5 * shapely.area(t).sum():
                led.append(q)
                del mates[k]
                plan = unary_union([plan, shapely.union_all(t).buffer(reach)])
                grew = True
    return led


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
                or p.zero_z is None or p.object_id in seen or p.at_grade):
            # (an at-grade mouth, 2026-11-21d, states no floor: its row reads
            # the uncut ground, and its faces under its roof are its arch's
            # soffit -- KBUF ``Road_Tunnel.obj``, #2221)
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
        # ...and never an arch's soffit (#2225): a floor carries its road's
        # headroom (``[cutout.wall_corridor] min_headroom_m``) under the roof
        faces = faces[_carries_passage(
            faces, F, float(law.tables.structures.cutout.wall_corridor.min_headroom_m),
            zero + float(p.depth_m), tol)]
        tris = shapely.polygons(faces[:, :, :2]) if len(faces) else np.zeros(0, object)
        foot = valid_polygon(unary_union(tris[shapely.area(tris) > 1e-6])) if len(tris) \
            else None
        if foot is None or foot.area < ob.plate_min_area_m2:
            notes.append(f"{o.id} {_base(o.path)}: a portal off the road its roof states "
                         f"({float(p.zero_z):.2f} vs {zero:.2f}), but no floor of a plate's "
                         f"worth under its roof: its bore's mouth ramp stays the cut")
            continue
        frame = _frame(o, foot, objects, seen, cache, law, scale)
        decked = hard_deck_share(foot, (o, *frame), cache, law, lambda _q, _z=zero: _z,
                                 float(faces[:, :, 2].min()), scale)
        if decked >= law.tables.structures.deck.on_fraction:
            # the road under a HARD-DECK bridge of its frame (``planar/
            # deck_bridge``, class A, 22n) is that bridge's: its seat is the
            # deck's, never a second zero off this roof (KBNA taxiway L; the
            # frame placed at the road zero this roof states)
            notes.append(f"{o.id} {_base(o.path)}: a portal off the road its roof states, but "
                         f"{100 * decked:.0f} % of its floor lies under a hard deck of its "
                         f"frame: a hard-deck bridge's road, read by the deck")
            continue
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
