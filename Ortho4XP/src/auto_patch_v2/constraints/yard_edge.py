"""A PROJECTED VERTEX IS NOT AN UNKNOWN OF THE SOLVE (spec
``2068-fence-grade-spec-A3.md`` R3; makes A2's G7 "the yard is a late
cell, projected after the solve, never a row" true).

A fence yard (``classify/fence_yard``) stands on the fence-foot plane: its
vertices take their height AFTER the whole solve (``solve/project_yard``),
so no row may price them against the airport.  A PROJECTED vertex is a
vertex of a ``fenceyard:`` face that no other face carries, and a FREE
vertex of a yard's road run (R5, :func:`yard_runs`).  At the one
site every generator's rows pass (``constraints.assembly``, beside the
riser's exemption and before the 5 % ceiling and the pavement fallback)
this withdraws

* (i) every row naming a projected vertex and any other vertex — the
  apron-to-groundside ramp across the yard's stand-off and its ceiling
  twin (MEASURED LPPI replay: row 102123, yard v2120 36.67 vs apron v604
  33.50 over 1.80 m, the 66th hard row);
* (ii) every ``road_ramp`` row naming a projected vertex (the
  ``ramp_runout.runout_exempt`` precedent).

A single-vertex row of any other family stays.  The pavement fallback
(``constraints/pavement_cap``) skips a pair holding a projected vertex
through :func:`projected_vertices`.  The yard's edge stays a declared
joint for the census (``pipeline/upper_pad_publication``).

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
from ..model.constraints import Row, row_vertices
from ..model.planar import PlanarMap, face_vertex_set, fence_yard_pad

__all__ = ["YardRun", "lot_vertices", "projected_vertices", "run_grade", "yard_exempt",
           "yard_records", "yard_runs"]


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
    block itself, ``pad`` its own ref)."""
    from ..model.registries import FLOOR_YARD
    reg = getattr(planar, "registries", None)
    out = {lv: rec for lv, rec in (getattr(reg, "landings", None) or {}).items()
           if rec.get("yard_plane")}
    for ref, h in (getattr(reg, "held", None) or {}).items():
        if h.get(FLOOR_YARD):
            out[ref] = dict(h[FLOOR_YARD], pad=ref)
    return out


def yard_runs(planar: PlanarMap, law: Law) -> list[YardRun]:
    """The yard road run of every level whose yard record
    (:func:`yard_records`) carries a ``yard_hull`` (module doc); ``[]``
    with none."""
    hulls = {lv: rec["yard_hull"] for lv, rec in yard_records(planar).items()
             if rec.get("yard_hull")}
    if not hulls:
        return []
    import shapely
    from shapely.geometry import Polygon

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
        gross = shapely.union_all([Polygon(r[0], r[1:]) for r in hulls[lv]]).buffer(snap)
        shapely.prepare(gross)
        level_vs = frozenset(by_ref.get(lv, ()))
        inside = {v for v, vx in planar.vertices.items()
                  if shapely.intersects_xy(gross, *vx.xy)}
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


def projected_vertices(planar: PlanarMap, law: Law) -> frozenset[int]:
    """The vertices of the fence yards no other face carries, and the free
    vertices of their road runs (module doc); empty with no yard."""
    own: set[int] = set()
    other: set[int] = set()
    for f in planar.faces.values():
        (own if fence_yard_pad(f.ref) is not None else other).update(
            face_vertex_set(planar, f))
    if not own:
        return frozenset()
    run = {v for r in yard_runs(planar, law) for v in r.free}
    return frozenset((own - other) | run)


def yard_exempt(rows: list[Row], planar: PlanarMap, law: Law,
                counts: dict[str, _t.Any]) -> list[Row]:
    """``rows`` less every row R3 withdraws (module doc); the count goes
    into ``counts['yard_rows_withdrawn']`` where a yard stands (none is
    written without one, as ``riser.riser_exempt``)."""
    from .road_ramp import GEN as _ROAD_RAMP
    held = projected_vertices(planar, law)
    if not held:
        return rows
    out: list[Row] = []
    for r in rows:
        vs = set(row_vertices(r))
        if vs & held and (len(vs) > 1 or r.source.generator == _ROAD_RAMP):
            continue
        out.append(r)
    counts["yard_rows_withdrawn"] = len(rows) - len(out)
    return out
