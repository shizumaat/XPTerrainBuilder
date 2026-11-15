"""A FENCE YARD'S RECORDS AND ITS ROAD RUN, read off the planar map (spec
``2068-fence-grade-spec-A3.md`` R5).  Read by BOTH the constraints
(``constraints/yard_edge``: the run's free vertices are no unknown of the
solve) and the solve (``solve/project_yard``: the projection that stands
them on the yard's ground) -- which may not import each other (M0 §1), so
the reading lives in the model.  Shapely-free: the hull test is
``geom/containment.points_near_polygons``.

THE YARD'S ROAD RUN (R5: "a road inside the yard stands on the yard's
ground").  The gross yard (``classify/fence_yard``, the landing record's
``yard_hull``) holds the roads the yard encloses.  The RUN is every
groundside road-family face (the yard's own faces aside) with a vertex
within the identity snap
(``law.tables.snap_margin_m``) of it; a run vertex is FREE when only
groundside road-family faces carry it and it lies in the gross yard, and
FIXED otherwise (an airside-side face, any other standing face or the level
carries it, or it lies outside).  ``solve/project_yard`` stands the free
vertices on the plane within the road grade of the fixed ones.

A LOT IN THE RUN BLENDS GENTLER (owner 2026-11-14T21:42Z, "Lots 5%"):
:func:`run_grade` — a road face climbs at ``[road_contact]
upper_pad_road_grade`` (RULINGS 2026-11-14b), a lot face (a run role whose
own longitudinal cap stands under the road cross-section's: the parking
lot's 5 %, owner 2026-09-04j) at its own cap, so its blend spreads wider.
A free vertex only lot faces carry is a LOT vertex (:func:`lot_vertices`);
it is graded second, off every other vertex of the lot faces."""
from __future__ import annotations

import dataclasses as _dc
import typing as _t

from ..law import Law
from .planar import PlanarMap, face_vertex_set, fence_yard_pad

__all__ = ["YardRun", "lot_vertices", "run_grade", "yard_records", "yard_runs"]


@_dc.dataclass(frozen=True)
class YardRun:
    """One upper level's yard road run (module doc): its landing record's
    key, the run's faces, its FREE vertices, its SOURCES (the fixed
    vertices less the level's own) and the level's vertices."""

    level: str
    faces: tuple[int, ...]
    free: frozenset[int]
    sources: frozenset[int]
    level_vertices: frozenset[int]


def yard_records(planar: PlanarMap) -> dict[str, dict[str, _t.Any]]:
    """``{level ref: its yard record}``: an upper level's landing record
    carrying a ``yard_plane`` (spec 2068 A2 F3), and a floor pad's held
    block record's floor yard (``classify/floor_yard``; the level is the
    block itself, ``pad`` its own ref) -- only while a yard face of its pad
    stands in the map (spec 2068 A4 F1' b: no face, no record, no run)."""
    from .registries import FLOOR_YARD
    reg = getattr(planar, "registries", None)
    out = {lv: rec for lv, rec in (getattr(reg, "landings", None) or {}).items()
           if rec.get("yard_plane")}
    for ref, h in (getattr(reg, "held", None) or {}).items():
        if h.get(FLOOR_YARD):
            out[ref] = dict(h[FLOOR_YARD], pad=ref)
    faced = {str(fence_yard_pad(f.ref)) for f in (getattr(planar, "faces", None) or {}).values()
             if fence_yard_pad(f.ref) is not None}
    return {lv: rec for lv, rec in out.items() if str(rec.get("pad")) in faced}


def yard_runs(planar: PlanarMap, law: Law) -> list[YardRun]:
    """The yard road run of every level whose yard record
    (:func:`yard_records`) carries a ``yard_hull`` (module doc); ``[]``
    with none."""
    hulls = {lv: rec["yard_hull"] for lv, rec in yard_records(planar).items()
             if rec.get("yard_hull")}
    if not hulls:
        return []
    from ..geom.containment import points_near_polygons
    from ..law.tables import road_family_roles, role_side, snap_margin_m
    roads = set(road_family_roles(law))
    snap = snap_margin_m(law)

    def is_road(fid: int) -> bool:
        f = planar.faces[fid]       # the yard itself is no road of its run
        return (f.role in roads and role_side(law, f.role) == "groundside"
                and fence_yard_pad(f.ref) is None)
    by_ref: dict[str, set[int]] = {}
    for f in planar.faces.values():
        by_ref.setdefault(str(f.ref), set()).update(face_vertex_set(planar, f))
    out: list[YardRun] = []
    for lv in sorted(hulls):
        level_vs = frozenset(by_ref.get(lv, ()))
        vids = list(planar.vertices)
        near = points_near_polygons(hulls[lv], [planar.vertices[v].xy for v in vids], snap)
        inside = {v for v, hit in zip(vids, near, strict=True) if hit}
        faces = sorted(fid for fid, f in planar.faces.items()
                       if is_road(fid) and face_vertex_set(planar, f) & inside)
        if not faces:
            continue
        vs = set().union(*(face_vertex_set(planar, planar.faces[fid]) for fid in faces))
        free = frozenset(v for v in vs if v in inside and v not in level_vs
                         and all(is_road(fid) for fid in planar.vertices[v].incident_faces))
        out.append(YardRun(lv, tuple(faces), free, frozenset(vs - free - level_vs), level_vs))
    return out


def run_grade(law: Law, role: str) -> float:
    """The grade a yard run face of ``role`` blends at (module doc): the
    upper-pad road grade, or a lot's own longitudinal cap where that stands
    under the road cross-section family's."""
    from ..law.tables import family, role_cap
    road = float(law.tables.emit.road_contact.upper_pad_road_grade)
    caps = [c.longitudinal for r in family(law, "road_cross_section").roles
            if (c := role_cap(law, r)) is not None]
    own = role_cap(law, role)
    if own is None or not caps or own.longitudinal >= max(caps):
        return road
    return float(own.longitudinal)


def lot_vertices(planar: PlanarMap, law: Law, run: YardRun) -> frozenset[int]:
    """The free vertices of ``run`` that only lot faces (:func:`run_grade`
    under the road grade) carry."""
    road = float(law.tables.emit.road_contact.upper_pad_road_grade)
    return frozenset(v for v in run.free
                     if all(run_grade(law, planar.faces[f].role) < road
                            for f in planar.vertices[v].incident_faces))
