"""A MAPPED ROAD CONTINUING FROM AN OBJECT RAMP'S FOOT CARRIES ITS RUN-OUT
(issues #669 / #1093; owner RULINGS 2026-10-14i, 14c (5); the rule R1 + R2
of ``docs/findings/kclt-ramp-lramp2.md``).

The foot leads what lies ahead of it: the ground there starts at the FOOT's
level — its unit's seat + the deck's authored ``y`` (:func:`foot_levels`) —
never at whatever the patch solved under the lip, and a mapped road leaving
the foot comes down from that level at road grade until it meets the DEM
(:func:`foot_road_rows`).  The strip beside it, where no road runs, is
``classify/ramp_runout`` / ``constraints/ramp_runout``'s.

Called by the last stages (``pipeline/late_stage``), where the foot's level
is a constant; not a generator (its row needs that constant)."""
from __future__ import annotations

import typing as _t

from ..law import Law
from ..model.constraints import ConstraintSet, Linear, Source
from ..model.planar import PlanarMap, face_vertex_set
from .ramp_runout import GEN, _dz_at, _row_vs

__all__ = ["FOOT_ROAD_RULING", "foot_levels", "foot_road_rows"]


#: The ruling head of a MAPPED ROAD's run-out off a ramp foot (#669 / #1093).
FOOT_ROAD_RULING = ("roads.ramp_runout ramp foot to raw DEM, carried by the mapped road "
                    "(owner 2026-10-14i; issues #669, #1093)")


def foot_levels(planar: PlanarMap, law: Law, airport, feet, levels: _t.Mapping[int, float]
                ) -> list["float | None"]:
    """R1 of ``docs/findings/kclt-ramp-lramp2.md``: each foot's LEVEL — its
    unit's seat + the deck's authored ``y`` at the foot.  The object stage
    seats a unit with its origin on the surface at its ANCHOR; where that is
    a held pad flat at its datum (``constraints/platform.flat_held_refs``),
    the seat is the pad's datum column, a constant of the stage (``levels``).
    Any other anchor: ``None`` (the foot's level is not a constant here)."""
    from shapely.geometry import Point, Polygon

    from ..model.platform import datum_vertices
    from .platform import flat_held_refs
    units = {str(getattr(u, "id", "")): u for u in
             (getattr(getattr(airport, "partition", None), "units", None) or ())}
    flat = flat_held_refs(planar, law)
    held = datum_vertices(planar, law)
    pads = [(str(f.ref), Polygon([planar.vertices[v].xy for v in planar.ring_vertices(f.ring)]))
            for f in planar.faces.values() if str(f.ref) in flat and str(f.ref) in held]
    enter = airport.frame.entry()
    out: list[float | None] = []
    for foot in feet:
        u = units.get(foot.unit)
        anchor = getattr(u, "anchor", None)
        if anchor is None:
            out.append(None)
            continue
        p = Point(*enter(float(anchor[1]), float(anchor[0])))
        ref = next((r for r, q in pads if q.is_valid and q.contains(p)), None)
        d = held.get(ref) if ref is not None else None
        out.append(float(levels[d]) + float(foot.y_foot) if d in levels else None)
    return out


def _on_landing(planar: PlanarMap, lip: tuple[float, float], reach: float) -> bool:
    """Does a 10-03e landing (``planar/landing``) stand within ``reach`` of
    the lip?  Its foot runs out in the planar stage (``planar/landing_runout``)."""
    from shapely.geometry import Point, Polygon

    from ..model.platform import LANDING_SEP
    p = Point(*lip)
    return any(LANDING_SEP in str(f.ref) and Polygon(
        [planar.vertices[v].xy for v in planar.ring_vertices(f.ring)]).distance(p) <= reach
        for f in planar.faces.values())


def foot_road_rows(planar: PlanarMap, law: Law, cs: ConstraintSet,
                   levels: _t.Mapping[int, float], airport
                   ) -> tuple[ConstraintSet, dict[str, _t.Any]]:
    """R2 of ``docs/findings/kclt-ramp-lramp2.md``: A MAPPED ROAD CONTINUING
    FROM AN OBJECT RAMP'S FOOT CARRIES ITS RUN-OUT (owner RULINGS 2026-10-14i:
    "where a mapped road continues from a ramp landing or foot, that road
    descends from the landing's level along its own course at road grade
    ... until it meets raw DEM"; 14c (5) for the strip beside it).

    Run in a LAST STAGE (``pipeline/late_stage``), where the foot's level is
    a constant (:func:`foot_levels`).  Every UNKNOWN vertex of a mapped-road
    ribbon (not a pad road, not a run-out strip, on no rigid face) inside
    the foot's corridor — its width, from ``FOOT_SPAN_M`` behind the lip
    (under the ramp's last metres: AT the foot's level) to where the run-out
    profile meets the ground — takes ONE design row at the profile
    ``geom/ramp_profile.runout_profile`` lays off the foot along its axis
    ground (design ``[road_contact] ramp_grade``, never steeper than the
    road's cap), the strip's own law; the road's §37 ramp rows on those
    vertices are withdrawn, as on a strip (``constraints/ramp_runout.runout_exempt``).
    MEASURED (KCLT, main 2cc289364): the departures roadway's mapped way
    ``big_roads:-6300`` and its slivers under the ramp, followers of the
    gap stage, held the ground at the lip 2.5 m under the deck's foot.
    ``(cs, report)``."""
    from ..airport.ramp_feet import FOOT_SPAN_M, ramp_feet
    from ..classify.ramp_runout import MAX_RUN_M
    from ..geom.ramp_profile import runout_profile
    from ..law.tables import is_rigid_role, role_cap
    from ..model.planar import is_osm_ribbon_ref, pad_road_faces
    from .road_ramp import GEN as _ROAD_RAMP
    rep: dict[str, _t.Any] = {"feet": 0, "no_level": 0, "landing": 0, "at_grade": 0,
                              "roads": 0, "rows": 0, "withdrawn": 0, "list": []}
    dem, frame = getattr(airport, "dem", None), getattr(airport, "frame", None)
    if dem is None or frame is None:
        return cs, rep
    feet = ramp_feet(airport, law, frame.entry())
    rep["feet"] = len(feet)
    if not feet:
        return cs, rep
    F = planar.faces
    skip = {f.id for f in pad_road_faces(planar)}
    runs = set(getattr(planar, "ramp_runouts", None) or ())
    road_v = sorted({v for f in F.values()
                     if f.role in ("service_road", "service_junction")
                     and is_osm_ribbon_ref(f.ref) and f.id not in skip and str(f.ref) not in runs
                     for v in face_vertex_set(planar, f)
                     if v not in levels and not any(
                         q in F and is_rigid_role(law, F[q].role)
                         for q in planar.vertices[v].incident_faces)})
    if not road_v:
        return cs, rep
    g = float(law.tables.emit.road_contact.ramp_grade)
    rc = role_cap(law, "service_road")
    cap = float(rc.longitudinal) if rc is not None else g
    band = float(law.tables.emit.cockpit.visual_m)
    to_ll = frame.transformers()[1]
    rows: list = []
    held: set[int] = set()
    for foot, zf in zip(feet, foot_levels(planar, law, airport, feet, levels), strict=True):
        (lx, ly), (dx, dy), h = foot.lip, foot.direction, 0.5 * foot.width_m
        if zf is None:
            rep["no_level"] += 1
            continue
        if _on_landing(planar, foot.lip, FOOT_SPAN_M):
            rep["landing"] += 1
            continue
        if abs(zf - float(dem.z(lx, ly))) <= band:
            rep["at_grade"] += 1
            continue
        prof = runout_profile(
            zf, lambda s, lx=lx, ly=ly, dx=dx, dy=dy: float(dem.z(lx + dx * s, ly + dy * s)),
            g, cap, MAX_RUN_M)
        run = prof[-1][0]
        n0 = len(rows)
        for v in road_v:
            if v in held:
                continue
            x, y = planar.vertices[v].xy
            s = (x - lx) * dx + (y - ly) * dy
            t = -(x - lx) * dy + (y - ly) * dx
            if abs(t) > h or s < -FOOT_SPAN_M or s > run:
                continue
            zt = zf if s <= 0.0 else _dz_at(prof, s)
            held.add(v)
            rows.append(Linear(((v, 1.0),), zt, zt,
                               Source(GEN, FOOT_ROAD_RULING, (f"vertex:{v}", foot.member))))
        if len(rows) > n0:
            rep["roads"] += 1
            lat, lon = to_ll(lx, ly)
            rep["list"].append(f"{foot.member} foot {lat:.7f},{lon:.7f} level {zf:.2f} "
                               f"run {run:.0f} m: {len(rows) - n0} road vertices")
    rep["rows"] = len(rows)
    if not rows:
        return cs, rep
    kept = [r for r in cs.rows() if not (r.source.generator == _ROAD_RAMP
                                         and all(v in held for v in _row_vs(r)))]
    rep["withdrawn"] = len(list(cs.rows())) - len(kept)
    return ConstraintSet.from_rows([*kept, *rows]), rep
