"""20g (3): THE TRENCH FLOOR UNDER A PACK SOFFIT IS TIED TO THE SOLVED SEAT
WITNESS (owner RULINGS 2026-11-20g / 20k / 20s; spec ``docs/specs/
elevated-clearance-20g-round3-spec.md`` §B.6).

``planar/soffit_road`` lays each trench out at a PLANNED floor (the planned
seat on the DEM votes).  The clearance is a RELATION, never a number the
plan can know: the object stage seats the crossing group on the SOLVED
surface under its anchor's feet (``crossing_seat.publication`` publishes
``zero = mean(solved(foot) - y) + dz``), so the floor is stated against that
same surface:

* R1 FLOOR: every level-station vertex of both halves of a run
  ``z_v - Σ w_k z_k <= c`` (a hard CEILING: the road goes down where the
  soffit needs it and keeps its ground where it clears -- an equality
  would raise a road the seat already clears), ``Σ w_k z_k`` the witness feet's barycentric
  terms averaged (``crossing_seat.witness_terms``), ``c = dz + soffit_y -
  need - margin - mean(y_feet)`` of the run's GOVERNING crossing (the
  lowest planned floor; ``[elevated] clearance_margin_m``) -- whatever the
  seat solves to, ``zero + soffit_y - floor >= need + margin``;
* R2 CLIMB: each climb station at or under the straight line from that
  floor to the plan's top (``viaduct_floor.half_rows`` with the weighted
  witness, its upper side);
* R3 NEVER TIED: a vertex stage 1 solves, a tile-seam vertex and its
  station, a vertex a RIGID-role (``pads.rigid_roles``) or airside face
  shares -- the pad and the pavement keep their own law.

R4 THE STAGE: the rows name a groundside trench vertex, so stage 1 drops
them (``solve/design_stage.stage_split``: every row touching a foreign
column); where the witness stands on a pad or pavement stage 1 solved it and
stage 2 holds the floor under it fixed, and on graded ground both solve in
stage 2 under the one hard relation.  FALLBACK (no witness foot on the map,
no governing crossing): the planned profile pinned per station, counted
``soffit_floor_absolute`` in :data:`STATS`.

The half prefix is spelled here (the planar module is not imported, so the
constraint stage's code key stays its own; a twin holds them equal).
Nothing names an airport, a pack or a resource.
"""
from __future__ import annotations

import typing as _t

import numpy as np
import shapely
from shapely.geometry import Polygon

from ..airport.crossing_seat import VERDICTS, ground_reader, margin_m, seat_plan, short_crossings
from ..law import Law
from ..law.tables import is_rigid_role, is_structure_role, is_value_role, role_side
from ..model.constraints import Pin, Row, Source
from ..model.planar import PlanarMap, pad_base_ref, platform_ref_of
from ..model.structures import Tunnel, profile_z
from .face_index import FaceIndex
from .viaduct_floor import _level_run, _runs, _stage_one, half_rows, stations_of

__all__ = ["soffit_floor_rows", "is_soffit_half", "publication", "low_ties",
           "HALF_PREFIX", "RULING", "STATS"]

#: a soffit trench half's tunnel id prefix: ``planar/soffit_road.ID_PREFIX`` + ``:``
HALF_PREFIX = "soffit-road:"
_GEN = "structures"
#: the hard head ``[design] hard_rulings`` registers: a datum equality
RULING = ("elevated.clearance_margin_m (20g (3) trench floor under the solved seat witness; "
          "owner RULINGS 2026-11-20g / 20k / 20s)")
#: the last call's counts (``soffit_floor_absolute``: runs pinned at the plan)
STATS: dict[str, int] = {}

Stations = _t.Mapping[str, _t.Sequence[tuple[float, _t.Sequence[int]]]]


def is_soffit_half(tn) -> bool:
    """Whether structure ``tn`` is one half of a 20g soffit trench (its id
    ``soffit-road:<run>/<half>``)."""
    head, sep, _rest = str(getattr(tn, "id", "")).partition(":")
    return bool(sep) and f"{head}:" == HALF_PREFIX


def _untied(planar: PlanarMap, law: Law) -> set[int]:
    """R3: stage 1's vertices and every vertex a rigid face or an airside
    pavement face (a value role, never a structure's own wall) shares."""
    s1, _datum = _stage_one(planar, law)
    out = set(s1)
    for f in planar.faces.values():
        if is_rigid_role(law, f.role) or (role_side(law, f.role) == "airside"
                                          and is_value_role(law, f.role)
                                          and not is_structure_role(law, f.role)):
            out.update(planar.ring_vertices(f.ring))
    return out


def _plans(planar: PlanarMap, law: Law, airport, margin: float):
    """``(face index, entry, [(rec, plan, short crossing)])`` on the map."""
    to_xy = airport.frame.entry()
    ground, near, fx = planar_ground(planar, law, airport.dem)
    out = []
    for rec in getattr(airport, "elevated_crossings", ()) or ():
        if rec["class"]:
            continue
        plan = seat_plan(rec, law, ground, near)
        out += [(rec, plan, c) for c in short_crossings(rec, plan, margin, ground)]
    return fx, to_xy, out


def _governing(comp: _t.Sequence[Tunnel], wanted):
    """The lowest-floor short crossing with a cell under the run's level
    stretch, or ``None``."""
    zone = shapely.union_all([_level_run(tn).buffer(float(tn.half_width_m) + 1.0,
                                                    cap_style="flat") for tn in comp])
    best = None
    for item in wanted:
        cells = np.asarray(item[2]["cells"])
        if shapely.contains_xy(zone, cells[:, 0], cells[:, 1]).any():
            if best is None or item[2]["floor"] < best[2]["floor"]:
                best = item
    return best


def soffit_floor_rows(planar: PlanarMap, law: Law, airport, tunnels: _t.Sequence[Tunnel],
                      stations: Stations) -> list[Row]:
    """The floor and climb rows of every soffit half in ``stations``
    (``tunnel id -> [(s, vertex ids)]``; module doc)."""
    STATS.clear()
    halves = [tn for tn in tunnels if tn.id in stations and is_soffit_half(tn)]
    if not halves:
        return []
    margin = margin_m(law)
    fx, to_xy, wanted = _plans(planar, law, airport, margin)
    seam = frozenset(int(v) for v in getattr(planar, "seam_vertices", ()) or ())
    done = _untied(planar, law)
    rows: list[Row] = []
    for comp in _runs(halves):
        gov = _governing(comp, wanted)
        wt = witness_terms(fx, to_xy, gov[1]["witness"]) if gov is not None else None
        if wt is None:
            rows.extend(_absolute(comp, stations, margin))
            continue
        rec, plan, c = gov
        terms, mean_y = wt
        done.update(v for v, _w in terms)
        depth = -(float(plan["dz"]) + float(c["soffit_y"]) - float(c["need"]) - margin - mean_y)
        src = Source(_GEN, RULING, (*(t.id for t in comp), rec["unit"],
                                    f"crossing:{c['member']}#{c['comp']}", f"osm:{c['way']}"))
        for tn in comp:
            st = [(s_, vs) for s_, vs in stations_of(planar, tn, stations[tn.id])
                  if not seam.intersection(vs)]
            rows.extend(half_rows(tn, st, terms, depth, src, done, ceiling=True))
        STATS["soffit_floor_runs"] = STATS.get("soffit_floor_runs", 0) + 1
    return rows


#: the FALLBACK's margin under the class minimum (spec §B.6 R4), m
ABSOLUTE_MARGIN_M = 0.30


def _absolute(comp, stations: Stations, margin: float) -> list[Row]:
    """The FALLBACK: the planned profile pinned per station, its level
    stretch at :data:`ABSOLUTE_MARGIN_M` under the class minimum (counted)."""
    STATS["soffit_floor_absolute"] = STATS.get("soffit_floor_absolute", 0) + 1
    out: list[Row] = []
    for tn in comp:
        src = Source(_GEN, RULING + " -- the planned profile, no witness on the map", (tn.id,))
        floor = float(tn.profile[0][1]) if tn.profile else None
        for s, vs in stations[tn.id]:
            z = profile_z(tn.profile, min(float(s), float(tn.top_s)))
            if floor is not None and z <= floor + 1e-6:
                z -= ABSOLUTE_MARGIN_M - margin
            out.extend(Pin(int(v), z, src) for v in vs)
    return out


# ── the seat on the planar map and its publication ──────────────────────

def planar_ground(planar, law, dem) -> tuple:
    """``(ground, airside_near, face index)`` on the planar map:
    ``crossing_seat.ground_reader`` over its faces (a pad keyed by the pad
    its pieces were cut from), and the map's face index."""
    fx = FaceIndex(planar, law)
    items = []
    for f in planar.faces.values():
        if len(f.ring) < 3:
            continue
        poly = Polygon([planar.vertices[v].xy for v in planar.ring_vertices(f.ring)])
        items.append((poly if poly.is_valid else poly.buffer(0.0), f.role,
                      pad_base_ref(platform_ref_of(f.ref))))
    ground, near = ground_reader(items, law, dem)
    return ground, near, fx


def witness_terms(fx, to_xy, feet) -> "tuple[tuple[tuple[int, float], ...], float] | None":
    """``(terms, mean y)``: the witness feet's barycentric terms, averaged
    (``Σ w_k z_k`` = the mean surface under the feet), and their mean
    authored ``y``; ``None`` where no foot stands on the map."""
    acc: dict[int, float] = {}
    ys = []
    for la, lo, y in feet:
        t = fx.terms_at(to_xy(lo, la))
        if t is None:
            continue
        ys.append(float(y))
        for v, w in t:
            acc[int(v)] = acc.get(int(v), 0.0) + float(w)
    if not ys:
        return None
    n = float(len(ys))
    return tuple((v, w / n) for v, w in sorted(acc.items())), sum(ys) / n


def _published(rec, c, zero, plan, cls) -> dict:
    """One crossing as the graded surface publishes it."""
    return {"unit": rec["unit"], "member": c["member"], "comp": c["comp"], "way": c["way"],
            "kind": c["kind"], "need": c["need"],
            "zero": None if zero is None else round(zero, 3), "soffit_y": c["soffit_y"],
            "anchor": "#".join(map(str, plan["anchor"])) if plan else "",
            "dz": plan["dz"] if plan else 0.0,
            "lift": bool(plan and plan["lift"] and zero is not None), "class": cls}


def publication(planar, law, airport, z) -> list[dict]:
    """THE SEAT THE PATCH GRADED FOR, as the graded surface publishes it
    (spec §B.4 (4)): every crossing of every seated group with ``zero =
    mean(solved(foot) - y) + dz`` over the witness feet (``z`` the solved
    heights by vertex), the plan's ``anchor``, ``dz`` and ``lift``, and its
    class -- the planner's for a short one (``crossing_seat.VERDICTS``;
    ``structure_refused`` where the structure pass built no trench under it),
    ``clear`` for one the planned seat clears; a listed crossing (``no_seat``
    group, ``low_soffit``) with no zero and no lift."""
    recs = tuple(getattr(airport, "elevated_crossings", ()) or ())
    if not recs or z is None:
        return []
    to_xy = airport.frame.entry()
    ground, near, fx = planar_ground(planar, law, airport.dem)
    built = shapely.union_all([shapely.LineString(t.axis).buffer(float(t.half_width_m),
                                                                 cap_style="flat")
                               for t in getattr(planar, "structures", ()) or ()
                               if is_soffit_half(t)])
    out = []
    for rec in recs:
        plan = None if rec["class"] else seat_plan(rec, law, ground, near)
        wt = witness_terms(fx, to_xy, plan["witness"]) if plan else None
        zero = None if wt is None else \
            sum(w * float(z[v]) for v, w in wt[0]) - wt[1] + plan["dz"]
        short = {(c["member"], c["comp"], c["way"])
                 for c in (short_crossings(rec, plan, margin_m(law), ground) if plan else ())}
        for c in rec["crossings"]:
            key = (rec["unit"], c["member"], c["comp"], c["way"])
            if c["class"] or rec["class"]:
                out.append(_published(rec, c, None, None, c["class"] or rec["class"]))
            elif (c["member"], c["comp"], c["way"]) in short:
                cls = VERDICTS.get(key, "unplanned")
                cells = np.asarray(c["cells"])
                if cls == "trench" and not shapely.contains_xy(built, cells[:, 0],
                                                               cells[:, 1]).any():
                    cls = "structure_refused"      # the structure pass did not build it
                out.append(_published(rec, c, zero, plan, cls))
            else:
                out.append(_published(rec, c, zero, plan, "clear"))
    return out


def low_ties(planar, law, airport) -> dict[tuple[str, int], tuple[tuple, float]]:
    """§B.7 THE GROUND UNDER A LIFTED GROUP'S LOW MEMBERS: ``(member, comp)
    -> (witness terms, offset)`` of every tie member (``seat_plan``'s
    ``ties``) of a lifted group holding a short crossing -- its feet's
    ground ``surface(foot) - Σ w_k z_k = y_foot + offset`` (``offset = dz -
    mean(y_anchor feet)``: the foot stands on the ground the lifted seat
    puts it at).  ``constraints/foot_rows`` states the rows."""
    recs = tuple(getattr(airport, "elevated_crossings", ()) or ())
    if not recs:
        return {}
    to_xy = airport.frame.entry()
    ground, near, fx = planar_ground(planar, law, airport.dem)
    margin = margin_m(law)
    out: dict[tuple[str, int], tuple[tuple, float]] = {}
    for rec in recs:
        if rec["class"]:
            continue
        plan = seat_plan(rec, law, ground, near)
        if not plan["lift"] or not plan["ties"] or not short_crossings(rec, plan, margin, ground):
            continue
        wt = witness_terms(fx, to_xy, plan["witness"])
        if wt is None:
            continue
        for k in plan["ties"]:
            out[(str(k[0]), int(k[1]))] = (wt[0], float(plan["dz"]) - wt[1])
    return out
