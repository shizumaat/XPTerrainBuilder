"""THE LAST STAGE, ORCHESTRATED (spec §55 (4); §53 (9), (17) item 6): the gap
pieces cut by their standing neighbours' levels, then solved against them.

ORDER.  The map WITHOUT gap pieces is built and solved exactly as an airport
without a gap sheet is (the BASE).  Then, here: (i) the STATIONS — every
point of a standing ring of the base beside a piece, with its solved level
(:func:`late_stations`); (ii) each piece cut into its parts
(``classify/gap_terrace``) and the classification rewritten with the parts
in the piece's place (:func:`cut_classification`); (iii) the full map
through the caller's own prefix, the followers, the constants, the follow
rows and ``solve.design.solve_late_stage``.  Nothing standing moves: every
base level is a constant of this stage.

THE CAR LOTS come last of all (#2114 round 2, ``pipeline/car_lot_stage``):
a gap piece and a pad road are standing ground to a car lot.

ONE MAP FOR EVERY LAST STAGE (#2206, :func:`run_last_stages`): the three
cuts read the base, the prefix runs once on the full classification, and
the stages solve in order on that map, a later stage's faces withheld.

ONE function, :func:`run_late_stage`, for the build and for the replay tool
(``tools/v2_solve_replay.py --late-from``).  This module derives nothing of
its own: the sets are ``pipeline/stage_one_map``'s, the rows
``constraints/gap_follow``'s, the cut ``classify/gap_terrace``'s."""
from __future__ import annotations

import dataclasses as _dc
import time
import typing as _t

import shapely
from shapely.geometry import Polygon
from shapely.strtree import STRtree

from ..classify.gap_mint import _poly
from ..classify.gap_terrace import APRON, PAD, ROAD, Station, terrace_cut
from ..classify.roles import is_pad_road_cell
from ..constraints.ceiling import RULING as _CEILING_RULING
from ..constraints.gap_follow import GEN as _GAP_GEN
from ..constraints.gap_follow import (BehindStep, PartStations,
                                      gap_follow_rows, reach_m)
from ..constraints.pavement_cap import RULING as _FALLBACK_RULING
from ..emit.graded import FLOOR_ROLES
from ..law import Law
from ..law.tables import is_rigid_role, role_cap, snap_margin_m
from ..model.constraints import ConstraintSet
from ..model.planar import face_edge_ids, is_car_lot_ref, is_gap_ref, is_osm_ribbon_ref
from ..planar.basins import WALL_ROLE
from ..planar.chords import stations as _chord_stations
from .late_view import VIEW_FIELDS, dissolved_levels, withheld_vertices, withheld_view
from .stage_one_map import (late_constraints, late_fixed, late_followers,
                            late_rim_levels, row_vertices)

__all__ = ["late_stations", "cut_classification", "run_late_stage", "run_last_stages",
           "late_cut", "late_derive", "late_solve", "LateCut", "BEHIND_STEP", "with_cells"]

#: THE CELLS BEHIND A DECLARED STEP (spec §60 (9) R1) — a structure's floor
#: and ramp roles and its wall void, read from their two owners: never a
#: follow neighbour of a piece (``constraints/gap_follow``).
BEHIND_STEP = BehindStep(frozenset(FLOOR_ROLES), WALL_ROLE)

#: a mapped-road ribbon whose ring comes this near a piece is welded to it
#: (the mint is flush on a ribbon cell) — a follower, never a station
_WELD_M = 0.3
_RANK = {ROAD: 0, APRON: 1, PAD: 2, "lot": 3, "band": 4, "structure": 5}


def _class_of(law: Law, role: str, ref, own_role: str, roles: dict) -> str:
    if role in roles["road"]:
        return ROAD
    if role == "apron":
        return APRON
    if is_rigid_role(law, role):
        return PAD
    if role in roles["lot"] and role != own_role:
        return "lot"
    return "band" if role in roles["band"] else "structure"


def late_stations(pm_base, z_base, pieces: _t.Sequence[Polygon], law: Law,
                  own_role: str) -> list[list[Station]]:
    """THE STATIONS of each piece (spec §55 (1)): the points of every
    standing ring of the base map that the piece's rim comes within the
    follow reach of, laid along the ring's edges at the chord density, each
    with the base's level interpolated on its edge and the PIECE's cap (a
    ring's own cap binds inside the follow reach only, through the follow
    rows).  No station lies on a road's DROP edge
    (``model/planar.drop_edges``, the fill risers' far kerb).  A mapped-road ribbon welded
    to a piece is a follower (an unknown), never a station; a ribbon
    beside no piece is a standing ring."""
    from ..constraints.groundside import groundside_face_roles
    from ..constraints.roads import road_family_roles
    from ..solve.design_ground import ground_roles
    roles = {"road": frozenset(road_family_roles(law)),
             "lot": frozenset(groundside_face_roles(law)),
             "band": frozenset(ground_roles(law))}
    pc = role_cap(law, own_role)
    cap_p = float(pc.longitudinal) if pc else 0.0
    setback = float(law.tables.structures.building_pad.groundside_cutback_m) \
        + snap_margin_m(law)
    reach, reach_pad = reach_m(law), reach_m(law, pad=True)
    spacing = float(law.tables.emit.chords.station_spacing_m)
    V = pm_base.vertices
    # owner RULINGS 2026-10-20d (round 3 D4 (b)): no station on a road's
    # DROP edge — the piece beyond it keeps its own ground
    from ..model.planar import drop_edges
    drop = drop_edges(pm_base)
    ptree = STRtree(list(pieces)) if pieces else None
    segs, meta = [], []
    for f in sorted(pm_base.faces.values(), key=lambda f: f.id):
        if is_gap_ref(f.ref):
            continue
        es = sorted(face_edge_ids(f))
        if is_osm_ribbon_ref(f.ref) and ptree is not None:
            pts = shapely.points([V[v].xy for e in es
                                  for v in (pm_base.edges[e].a, pm_base.edges[e].b)])
            if len(ptree.query(pts, predicate="dwithin", distance=_WELD_M)[0]):
                continue
        cls = _class_of(law, f.role, f.ref, own_role, roles)
        name = f"{f.role}:{str(f.ref).split('#')[0]}"
        for e in es:
            ed = pm_base.edges[e]
            if drop and frozenset((ed.a, ed.b)) in drop:
                continue
            segs.append([V[ed.a].xy, V[ed.b].xy])
            meta.append((float(z_base[ed.a]), float(z_base[ed.b]), cls, cap_p,
                         setback if cls == PAD else 0.0, name))
    out: list[list[Station]] = [[] for _ in pieces]
    if not segs or not pieces:
        return out
    lines = shapely.linestrings(segs)
    tree = STRtree(lines)
    for k, piece in enumerate(pieces):
        rim = piece.boundary
        best: dict[tuple, Station] = {}
        for i in sorted(tree.query(rim, predicate="dwithin",
                                   distance=max(reach, reach_pad)).tolist()):
            (ax, ay), (bx, by) = segs[i]
            za, zb, cls, cap, knife, name = meta[i]
            # a PAD ring's stations are read at the pad's own reach — the
            # piece's stand-off at that pad (spec §62 (3) R-D rule 1)
            r_i = reach_pad if cls == PAD else reach
            length = float(shapely.length(lines[i]))
            pts = _chord_stations([(ax, ay), (bx, by)], spacing)
            near = shapely.dwithin(shapely.points(pts), rim, r_i)
            for (x, y), ok in zip(pts, near.tolist()):
                if not ok:
                    continue
                t = (((x - ax) ** 2 + (y - ay) ** 2) ** 0.5 / length) if length else 0.0
                s = Station((float(x), float(y)), (1.0 - t) * za + t * zb, cls, cap,
                            knife, name)
                key = (round(s.xy[0], 3), round(s.xy[1], 3))
                old = best.get(key)
                if old is None or (_RANK[s.cls], s.cap, s.ring) < (_RANK[old.cls], old.cap, old.ring):
                    best[key] = s
        out[k] = [best[key] for key in sorted(best)]
    return out


def cut_classification(cl, pm_base, z_base, law: Law, rules) -> tuple[_t.Any, dict]:
    """``cl`` with every gap piece REPLACED by its parts (cells only: the
    mint is unchanged), and the per-piece report — ``part_stations`` the
    cut's stations as each part reads them (``gap_follow.PartStations``)."""
    gap = [c for c in cl.cells if is_gap_ref(c.ref)]
    rep: dict = {"pieces": [], "parts": 0, "knives": 0, "merged": 0, "stations": 0,
                 "part_stations": {}}
    if not gap:
        return cl, rep
    polys = [_poly(c.ring, c.holes) for c in gap]
    own_role = gap[0].role
    pc = role_cap(law, own_role)
    cap_p = float(pc.longitudinal) if pc else 0.0
    stations = late_stations(pm_base, z_base, [p for p in polys if p is not None],
                             law, own_role)
    it = iter(stations)
    kept = [c for c in cl.cells if not is_gap_ref(c.ref)]
    cells = list(kept)
    nid = max((c.id for c in kept), default=-1) + 1
    for c, piece in zip(gap, polys):
        if piece is None:
            continue
        st = next(it)
        cut = terrace_cut(piece, st, law, rules, cap=cap_p)
        by_cls: dict[str, int] = {}
        for s in st:
            by_cls[s.cls] = by_cls.get(s.cls, 0) + 1
        parts = []
        grp = {i: g for g, members in enumerate(cut.groups) for i in members}
        for p in cut.parts:
            rep["part_stations"][f"{c.ref}{p.suffix}"] = PartStations(
                st, frozenset(i for i in p.stations if grp.get(i) == p.group),
                bool(p.stations) and all(st[i].cls in (ROAD, APRON) for i in p.stations))
            ev = {**dict(c.evidence), "area_m2": float(p.poly.area)}
            cells.append(_dc.replace(
                c, id=nid, ref=f"{c.ref}{p.suffix}",
                ring=tuple(p.poly.exterior.coords)[:-1],
                holes=tuple(tuple(h.coords)[:-1] for h in p.poly.interiors),
                evidence=ev))
            nid += 1
            parts.append({"ref": f"{c.ref}{p.suffix}", "kind": p.kind,
                          "m2": round(float(p.poly.area), 1), "group": p.group,
                          "stations": len(p.stations)})
        rep["pieces"].append({
            "ref": c.ref, "m2": round(float(piece.area), 1), "groups": len(cut.groups),
            "knives": cut.knives, "stations": by_cls, "parts": parts,
            "conflicts_merged": [
                {k: (round(v, 3) if isinstance(v, float) else
                     tuple(round(x, 3) for x in v) if isinstance(v, tuple) else v)
                 for k, v in m.items()} for m in cut.merged],
            "knife_dropped_m2": round(cut.dropped_m2, 1)})
        rep["parts"] += len(parts)
        rep["knives"] += cut.knives
        rep["merged"] += len(cut.merged)
        rep["stations"] += len(st)
    return _dc.replace(cl, cells=tuple(cells)), rep


def _pad_levels(pm, z, law: Law) -> dict[str, float]:
    """``{pad ref: the median solved level of its faces' vertices}``."""
    import statistics
    from ..model.planar import face_vertex_set
    acc: dict[str, list[float]] = {}
    for f in pm.faces.values():
        if is_rigid_role(law, f.role):
            acc.setdefault(str(f.ref), []).extend(float(z[v]) for v in face_vertex_set(pm, f))
    return {ref: statistics.median(zs) for ref, zs in acc.items() if zs}


def follower_join_yields(pm, cs: ConstraintSet, fixed: _t.Mapping[int, float],
                         yield_heads: _t.AbstractSet[str],
                         known: _t.AbstractSet[int] = frozenset()) -> list[dict]:
    """A FOLLOWER'S JOIN PIN THE LAST STAGE RELEASES IS A YIELD (owner
    RULINGS 2026-09-27a (10); #1093): ``late_constraints`` drops every
    yielding pin on a follower (spec §53 (17)), so each §37 (9) join among
    them is recorded as a released join (``pin_yield`` shape) — the core
    ribbon then takes the level the follower solves to, as for every
    released join.  Unrecorded, the sidecar kept the ribbon's own altitude
    and the census read a step the mesh never carries (MEASURED, KCLT
    ``small_roads:-8201``: 5.18 m once a run-out bank took the join's
    vertex off the pad's rim).  ``known``: joins already recorded."""
    joins = getattr(pm, "road_coverage_join", None) or {}
    return [{"v": int(p.v), "xy": tuple(float(c) for c in pm.vertices[p.v].xy),
             "pinned_m": round(float(p.z), 4), "z_m": round(float(p.z), 4),
             "excess_m": 0.0, "stage": "late"}
            for p in cs.pins if p.v in joins and p.v not in fixed and p.v not in known
            and str(p.source.ruling).split("(")[0].strip() in yield_heads]


def _carry_pin_yield(base_solution, pm_base, pm_full) -> list[dict]:
    """The base solve's released join pins (``DesignReport.pin_yield``) on
    the FULL map's vertex ids, by the canonical coordinate join."""
    recs = list(base_solution.get("pin_yield") or ())
    if not recs:
        return []
    at = {tuple(v.xy): i for i, v in pm_full.vertices.items()}
    out = []
    for r in recs:
        v = pm_base.vertices.get(int(r["v"]))
        j = at.get(tuple(v.xy)) if v is not None else None
        if j is not None:
            out.append({**r, "v": j})
    return out


@_dc.dataclass
class LateCut:
    """What the cut (steps (i)-(ii)) hands the derive and the solve: the cut
    classification, its published report, the stations each part reads
    (``gap_follow.PartStations``), the pad roads' exits (``roads_only``)
    and the cut's wall seconds."""

    cl: _t.Any
    report: dict
    part_stations: dict
    exits: _t.Any
    wall_s: float


def late_cut(cl, airport, law: Law, base_solution: _t.Mapping[str, _t.Any], *,
             rules=None, out: _t.Callable[[str], None] = print,
             roads_only: bool = False, lots_only: bool = False,
             held: _t.Sequence = ()) -> LateCut:
    """STEPS (i)-(ii) of the module docstring: the stations and the cut —
    ``cl`` with every gap piece replaced by its parts (or, ``roads_only``,
    the pad roads run on to their exits and their ramp-foot run-outs; or,
    ``lots_only``, the car lots cut against the solved map and ``held``,
    the polygons of the late cells cut before them, ``pipeline/car_lot_stage``)."""
    if rules is None:
        from ..classify.rules import load_rules
        rules = load_rules()
    pm_base, z_base = base_solution["pm"], base_solution["z"]
    t0 = time.perf_counter()
    exits = None
    if roads_only:
        # the ramp is INSIDE the patch (13a (1)/(3)): each pad road runs on
        # from its patch exits until a design-grade profile from its pad's
        # solved level meets the terrain
        from ..classify.pad_road_exit import extend_pad_roads
        cl_cut, exits = extend_pad_roads(cl, airport, law, rules,
                                         _pad_levels(pm_base, z_base, law))
        out(f"LAST STAGE pad road exits (13a (1)): {exits}")
        # the ramp foot runs out at road grade to raw DEM (14c (5), #669)
        from ..classify.ramp_runout import mint_ramp_runouts
        cl_cut, runouts = mint_ramp_runouts(cl_cut, airport, law, rules, pm_base, z_base)
        out(f"LAST STAGE ramp-foot run-outs (14c (5)): "
            f"{ {k: v for k, v in runouts.items() if k != 'list'} }")
        for line in runouts["list"]:
            out(f"    run-out: {line}")
        # #1633 round 3: the roads minted here are cut back at a retaining
        # wall like every other road (``classify/wall_cutback``, the one
        # helper ``classify/roles`` runs; a pad road's exit ran through the
        # KATL ``muro_concreto5`` footprint)
        from ..airport.walled_plate import body_plan
        from ..classify.wall_cutback import cut_roads_at_walls
        from ..law.tables import road_family_roles, snap_margin_m
        cells, wcut = cut_roads_at_walls(
            cl_cut.cells, frozenset(road_family_roles(law)),
            tuple(getattr(airport, "retaining_walls", ()) or ()),
            rules.cells.min_area_m2, snap_margin_m(law), body_plan(airport))
        if wcut["wall_cut_cells"] or wcut.get("plate_cut_cells"):
            cl_cut = _dc.replace(cl_cut, cells=tuple(cells))
            out(f"LAST STAGE roads cut back at retaining walls: {wcut}")
        cut = {"pieces": [], "parts": 0, "knives": 0, "merged": 0, "stations": 0,
               "part_stations": {}}
    elif lots_only:
        from .car_lot_stage import car_lot_cut
        cl_cut, cut = car_lot_cut(cl, pm_base, law, rules, held)
    else:
        cl_cut, cut = cut_classification(cl, pm_base, z_base, law, rules)
    # the stations stay the stage's own (the cut report is a published record)
    part_stations = cut.pop("part_stations")
    t_cut = time.perf_counter() - t0
    out(f"LAST STAGE cut (§55 (2)-(3)) {t_cut:.1f} s: {len(cut['pieces'])} pieces -> "
        f"{cut['parts']} parts, {cut['knives']} knives, {cut['stations']} stations, "
        f"{cut['merged']} stations merged by the floors")
    return LateCut(cl_cut, cut, part_stations, exits, t_cut)


def late_derive(derive: _t.Callable[[_t.Any], tuple], cut: LateCut) -> tuple[tuple, float]:
    """STEP (iii)'s first half: the CALLER's own prefix on the cut
    classification — ``((pm, cs, strips, hold), wall seconds)``."""
    t0 = time.perf_counter()
    got = derive(cut.cl)
    return got, time.perf_counter() - t0


def late_solve(cut: LateCut, derived: tuple, t_derive: float, airport, law: Law,
               base_solution: _t.Mapping[str, _t.Any], *, options=None,
               out: _t.Callable[[str], None] = print, roads_only: bool = False,
               lots_only: bool = False, withheld: _t.AbstractSet[int] = frozenset(),
               rim_base: _t.Mapping[str, _t.Any] | None = None,
               **solve_kw) -> tuple[_t.Any, _t.Any, dict]:
    """STEP (iii)'s second half: the followers, the constants, the follow
    rows and ``solve.design.solve_late_stage`` on the derived map —
    ``(full map, solution, report)`` (:func:`run_late_stage`).
    ``lots_only``: the car lots' stage (``pipeline/car_lot_stage``).

    THE LAST STAGES ON ONE MAP (#2206, :func:`run_last_stages`):
    ``withheld`` are the face ids a LATER stage owns on ``derived``'s map
    (:func:`_junior_faces`) — this stage solves on the map without them
    (``stage_one_map.withheld_view``): the vertices only they carry are
    constants at the survey that no face of the view and no row of the
    stage's set names, and the pad roads' own passes run only in the stage
    the pad roads follow in.  ``rim_base`` (the pad
    roads' stage on the one map): the MAIN base, the map the pad roads' rim
    nodes stand off (``pipeline/neck_release`` reads their edges there)."""
    if lots_only:
        from .car_lot_stage import car_lot_solve
        return car_lot_solve(cut, derived, t_derive, airport, law, base_solution,
                             options=options, out=out, **solve_kw)
    from ..law.tables import design as _design_law
    from ..model.planar import pad_road_faces
    from ..solve.design import solve_late_stage
    pm_base, z_base = base_solution["pm"], base_solution["z"]
    cl_cut, part_stations, exits, t_cut = cut.cl, cut.part_stations, cut.exits, cut.wall_s
    pm, cs, strips, _hold = derived
    pm_full = pm
    absent = frozenset(base_solution.get("withheld") or ())
    junior = withheld_vertices(pm, withheld)
    pad_ids = {f.id for f in pad_road_faces(pm)}
    # the map as this stage sees it (``pipeline/late_view``): the later
    # stages' faces are not on it, nor the nodes they minted on its rings
    # (their vertices stay, isolated, so the ids index the full map)
    pm, dissolved = withheld_view(pm, withheld, frozenset(
        tuple(v.xy) for i, v in pm_base.vertices.items() if i not in absent)
        if withheld else frozenset())
    junior = junior | frozenset(dissolved)
    if junior:
        # a later stage's rows are its own (a pin, a law row on its faces)
        cs = ConstraintSet.from_rows([r for r in cs.rows()
                                      if not any(v in junior for v in row_vertices(r))])
    # the pad roads' passes (13a (1)) are THEIR stage's; a map carrying pad
    # roads notches the standing rims they meet, in every stage that sees it
    pad_stage = roads_only or not (pad_ids & set(withheld))
    notch = roads_only or bool(pad_ids)
    free, frep = late_followers(pm, roads_only=roads_only)
    ident = float(law.tables.emit.identity.min_distinct_spacing_m)
    fixed, jrep = late_fixed(pm_base, z_base, pm, free | junior, ident, absent)
    for v in junior:
        fixed.pop(v, None)
    # the pad roads' arrangement notches a standing cell's node off its
    # edge (pass C, three identity cells): that node is still the cell's
    from ..constraints.pad_ramp import stand_off_m
    rigid = frozenset(f.role for f in pm.faces.values()
                      if is_rigid_role(law, f.role)) if notch else frozenset()
    joined, rim_edges = frozenset(fixed), {}
    jrep["rim"] = late_rim_levels(
        pm_base, z_base, pm, fixed, free | junior | absent, ident * 0.02,
        notch_m=stand_off_m(law) if notch else 0.0, rigid=rigid, edge_of=rim_edges)
    if junior:
        jrep["withheld"] = {"faces": len(withheld), "vertices": len(junior) - len(dissolved),
                            "nodes_dissolved": len(dissolved)}
    # #1918 R4-2: a standing road kerb's station abeam a pad road's
    # standing vertex across a step over the bar is RELEASED where its own
    # law lets it (``pipeline/neck_release``) — the pad roads' stage only
    necks: list = []
    if roads_only:
        from .neck_release import late_neck_release
        neck_base, neck_edges, neck_joined = pm_base, rim_edges, joined
        if rim_base is not None and rim_base["pm"] is not pm_base:
            # on the one map the rim nodes were levelled in the gap stage:
            # their edges are read off the main base again
            seen, _j = late_fixed(rim_base["pm"], rim_base["z"], pm, free, ident)
            neck_base, neck_edges, neck_joined = rim_base["pm"], {}, frozenset(seen)
            late_rim_levels(rim_base["pm"], rim_base["z"], pm, seen, free, ident * 0.02,
                            notch_m=stand_off_m(law), rigid=rigid, edge_of=neck_edges)
        jrep["rim"]["necks"], necks = late_neck_release(
            neck_base, pm, fixed, cs, law, neck_edges, neck_joined,
            to_ll=airport.frame.transformers()[1])
    # THE ROAD YIELDS TO THE PAD (issue #609; 13a (1), 13d): a pad road's
    # absolute road rows leave and it carries the ramp from the rim it is
    # welded to — the rim a constant of this stage
    from ..constraints.foot_road import foot_road_rows
    from ..constraints.pad_ramp import pad_ramp_rewrite
    from ..constraints.ramp_runout import runout_rows
    if pad_stage:
        cs, pad_ramp = pad_ramp_rewrite(pm, law, cs, fixed)
        cs, pad_ramp["runout_rows"] = runout_rows(pm, law, cs, fixed,
                                                  dem=getattr(airport, "dem", None))
    else:
        pad_ramp = {"joins": [], "withheld": "the pad roads' own stage"}
    # a mapped road continuing from a ramp foot carries its run-out (14i;
    # #669 / #1093) — from the foot's level, a constant of this stage
    from ..airport.ramp_feet import FOOT_SPAN_M, ramp_feet
    from ..classify.ramp_runout import MAX_RUN_M
    cs, foot_roads = foot_road_rows(pm, law, cs, fixed, airport,
                                    ramp_feet(airport, law, airport.frame.entry()),
                                    back_m=FOOT_SPAN_M, max_run_m=MAX_RUN_M)
    out(f"LAST STAGE foot roads (14i): { {k: v for k, v in foot_roads.items() if k != 'list'} }")
    for line in foot_roads.pop("list"):
        out(f"    foot road: {line}")
    pad_ramp["foot_road_rows"] = foot_roads
    pad_joins = pad_ramp.pop("joins")
    # owner RULINGS 2026-10-15a (2) / 10-20d (round 3 D4): THE WALL IS THE
    # STEP in this stage too — a road-edge drop's lower side is a gap piece
    # (``airport/riser_wall``), and the pair rows across a declared
    # wall's line leave here as they leave between §20b's stages
    from ..constraints.road_ramp import wall_release
    cs, wall_rep = wall_release(pm, law, cs)
    # 13d "road ramps first": where no cap-grade ramp fits between the pad
    # and the road's other standing end — the remainder.  13f: ONLY A
    # FREE-STANDING PAD takes any of it (one rigid pad, inside the cap);
    # 13e: what is still out of reach steepens — one ramp over its whole
    # run, no step — and is published as a lifted cap on those faces
    from ..constraints.pad_road_reach import (free_standing_pads, pad_grade_release,
                                              pad_road_reach, pad_shifts, shift_pads)
    from ..constraints.pad_ramp import PAD_RAMP_RULING
    reach_rep = pad_road_reach(pm, law, fixed) if pad_stage else []
    first = [r for r in reach_rep if r["remainder_m"]]
    free_pads = free_standing_pads(pm, law) if first else frozenset()
    shifts = pad_shifts(reach_rep, free_pads)
    if shifts:
        pad_ramp["shifted"] = shift_pads(pm, law, fixed, shifts)
        reach_rep = pad_road_reach(pm, law, fixed)
    pad_ramp["shifts"] = shifts
    pad_ramp["reach"] = reach_rep
    cs, pad_ramp["released"] = pad_grade_release(pm, cs, reach_rep, PAD_RAMP_RULING)
    if pad_ramp["released"]:
        pm = _dc.replace(pm, pad_road_released={
            int(f): (r["pad"], float(r["run_m"]), float(r["grade"]))
            for r in pad_ramp["released"] for f in r["faces"]})
    if reach_rep:
        to_ll = airport.frame.transformers()[1]
        out(f"LAST STAGE pad roads (13d): {len(reach_rep)} pad|road network(s) between "
            f"two standing levels, {len(first)} with no ramp inside the road cap, "
            f"{len(shifts)} free-standing and shifted (13f), "
            f"{len(pad_ramp['released'])} stretch(es) released above the cap (13e)")
        for r in sorted(first, key=lambda r: -abs(r["remainder_m"])):
            pad = r["pad"]
            lat, lon = to_ll(*pm.vertices[r["far_v"]].xy)
            now = next((q for q in pad_ramp["released"]
                        if q["pad"] == pad and q["road"] == r["road"]), None)
            out(f"    {pad}: {r['rise_m']:+.2f} m over {r['run_m']:.1f} m to {r['far']} "
                f"at {lat:.7f},{lon:.7f} = {100 * r['grade']:.1f} % (cap "
                f"{100 * r['cap']:.0f} %), remainder {r['remainder_m']:+.2f} m; "
                + (f"FREE-STANDING: pad shifted {shifts[pad]:+.2f} m (13f); "
                   if pad in shifts else
                   "free-standing, its roads ask opposite ways: stays (13f); "
                   if pad in free_pads else "welded to other pavement: stays (13f); ")
                + (f"GRADE RELEASED to {100 * now['grade']:.1f} % over "
                   f"{now['run_m']:.1f} m (13e); " if now else "a cap-grade ramp now fits; ")
                + f"road {', '.join(r['road'][:3])}")
    cs_all = cs
    # THE FLOOR, ONE NUMBER AT ONE SITE (spec §55 (5), (15) rule B): the
    # widening reads it here and the sidecar publishes THIS value
    # (``report["stage"]``), so the census follows the stage, never a copy
    floor_m = float(law.tables.emit.terrace.pad_terrace_floor_m)
    yheads = frozenset(getattr(_design_law(law), "yielding_pin_rulings", ()) or ())
    pad_joins.extend(follower_join_yields(pm, cs, fixed, yheads,
                                          {int(r["v"]) for r in pad_joins}))
    cs, dropped = late_constraints(
        cs, fixed, yheads,
        widen_heads=frozenset(r.split("(")[0].strip()
                              for r in (_CEILING_RULING, _FALLBACK_RULING)),
        widen_floor_m=floor_m, no_widen=frozenset(n.s for n in necks))
    out(f"LAST STAGE (§53 (9)): followers {frep}; join {jrep}; "
        f"rows with no unknown dropped {dropped}; wall release {wall_rep}")
    grows, grep = ([], {"rows": 0, "conflicts": [], "declared": []}) if roads_only \
        else gap_follow_rows(pm, law, fixed, part_stations, BEHIND_STEP)
    if not roads_only:
        # #712 (10o (B)): a base slab meets the pack pavement beside it at
        # one level across the stand-off — both are this stage's unknowns
        from ..constraints.slab_weld import slab_weld_rows
        wrows, grep["slab_weld"] = slab_weld_rows(pm, law, cl_cut, fixed)
        grows = [*grows, *wrows]
    cs = ConstraintSet.from_rows([*cs.rows(), *grows])
    cs_full = ConstraintSet.from_rows([*cs_all.rows(), *grows])
    # the lot SITS at its road's level: the one published-target channel
    lot_z = grep.get("lot_targets") or {}
    if lot_z:
        pm = _dc.replace(pm, preferred_z={**dict(pm.preferred_z), **lot_z})
    out(f"LAST STAGE gap_follow (§53 (13)): {grep['rows']} rows; "
        f"{len(grep['conflicts'])} vertices between two disagreeing neighbours; "
        f"{len(grep['declared'])} bounds of another group's ring declared (§55 (2) 5); "
        f"lot rows (§55 (3) 4) {grep.get('lot_rows', 0)}, lot_fit targets {len(lot_z)}")
    t0 = time.perf_counter()
    # THE BASE'S RELAXATIONS STAY PUBLISHED (§55 (4) iv): the last solve
    # publishes its own conflict records over the registry; the earlier
    # stages' (the caller's own solve, or the pickled base's) come first
    base_conf = [dict(r) for r in (base_solution.get("hard_conflict") or ())]
    # a later stage's own vertices are constants here, at the survey: no
    # face of the view carries them and no row of ``cs`` names one
    held_at = {v: float(pm.vertices[v].dem_z) if pm.vertices[v].dem_z is not None else 0.0
               for v in junior}
    sol, design = solve_late_stage(pm, cs, law, {**fixed, **held_at}, options, **solve_kw)
    if dissolved and sol.z:
        # a lifted node stands on the edge it was lifted onto
        sol = _dc.replace(sol, z=tuple(dissolved_levels(sol.z, dissolved)))
    hard_conflict = [*base_conf, *(dict(r) for r in design.hard_conflict)]
    t_solve = time.perf_counter() - t0
    feas = getattr(design, "hard_feasibility", None)
    if feas is not None:
        out(f"LAST STAGE relaxed by head (§55 (5)): {feas.by_head_line()}")
    off = [abs(float(sol.z[v]) - z) for v, z in fixed.items()] if sol.z else []
    out(f"LAST STAGE: fixed vertices off their constant by > 0.02 m: "
        f"{sum(1 for d in off if d > 0.02)} of {len(off)} (worst {max(off, default=0.0):.3f} m)")
    if necks and sol.z:
        from .neck_release import necks_over
        bar = float(law.tables.emit.road_contact.neck_step_m)
        to_ll = airport.frame.transformers()[1]
        over = necks_over(necks, sol.z, bar)
        out(f"LAST STAGE necks (#1918 R4): {len(jrep['rim']['necks']['released'])} "
            f"station(s) released on {jrep['rim']['necks']['released_edges']} edge(s), "
            f"{len(jrep['rim']['necks']['walls'])} wall(s); {len(over)} released neck(s) "
            f"still over {bar} m after the solve")
        for s_, v_, d_ in over:
            out("    neck over the bar: station %.7f,%.7f vs %.7f,%.7f step %.3f m"
                % (*to_ll(*pm.vertices[s_].xy), *to_ll(*pm.vertices[v_].xy), d_))
    for r in pad_joins:                  # published with the level they took
        if sol.z:
            r["z_m"] = round(float(sol.z[r["v"]]), 4)
            r["excess_m"] = round(r["z_m"] - r["pinned_m"], 4)
    report = {"cut": cut.report, "cl": cl_cut, "followers": frep, "join": jrep,
              "pad_ramp": pad_ramp, "pad_exits": exits, "wall_release": wall_rep,
              "stage": {"floor_m": floor_m,
                        "followers": list(frep["follower_ribbon_refs"])},
              "dropped": dropped, "follow": grep, "cs": cs, "cs_full": cs_full,
              "fixed": fixed, "strips": strips, "pin_yield": [*_carry_pin_yield(base_solution, pm_base, pm), *pad_joins],
              "design": design, "hard_conflict": hard_conflict,
              "withheld": sorted(junior - frozenset(dissolved)),
              "wall_s": {"cut": round(t_cut, 2), "derive": round(t_derive, 2),
                         "solve": round(t_solve, 2)}}
    if pm is not pm_full:
        # what this stage published, on the full map (the view's faces go)
        pm = _dc.replace(pm_full, **{f.name: getattr(pm, f.name) for f in _dc.fields(pm)
                                     if f.name not in VIEW_FIELDS})
    return pm, sol, report


def run_late_stage(cl, airport, law: Law, derive: _t.Callable[[_t.Any], tuple],
                   base_solution: _t.Mapping[str, _t.Any], *, rules=None,
                   options=None, out: _t.Callable[[str], None] = print,
                   roads_only: bool = False, lots_only: bool = False,
                   records: _t.Any = None,
                   **solve_kw) -> tuple[_t.Any, _t.Any, dict]:
    """THE LAST STAGE (spec §55 (4)).  ``base_solution`` is the base map and
    its solved levels (``{"pm", "z"}``, and the base's ``hard_conflict``
    records — empty when absent); ``derive(cl) -> (pm, cs, strips,
    hold)`` is the CALLER's own prefix (the build's, the replay's), run here
    on the classification with the pieces cut.  ``(full map, solution,
    report)``; the report carries the stage's own row set (``cs``), its
    constants (``fixed``), the solve's report (``design``) and
    ``hard_conflict``: the base's records merged with the late solve's
    (v2-stage-cache spec §3b — no module global).

    ``roads_only`` is THE PAD ROADS' OWN STAGE (issue #609; 13a (1): junior
    to every pavement they meet — :func:`run_last_stages`): ``cl`` is taken
    as it is (nothing is cut), only the pad roads follow, and no gap-follow
    row is minted.  ``lots_only`` is THE CAR LOTS' OWN STAGE (#2114 round 2,
    ``pipeline/car_lot_stage``): last of all, the car lots alone follow.

    ``records`` (``pipeline/late_records.LateRecords``): the cut and the
    solve through their stage-cache records, the derive through the
    prefix's; ``None`` runs them plainly.  One stage alone; the build runs
    every stage on one map through :func:`run_last_stages`."""
    mode = {"roads_only": roads_only, "lots_only": lots_only}
    stage = "car_lots" if lots_only else "pad_roads" if roads_only else "gap"
    if records is None:
        cut = late_cut(cl, airport, law, base_solution, rules=rules, out=out, **mode)
        derived, t_derive = late_derive(derive, cut)
        return late_solve(cut, derived, t_derive, airport, law, base_solution,
                          options=options, out=out, **mode, **solve_kw)
    # the stage-cache records (``pipeline/late_records``; spec §4b.5)
    cut = records.cut(cl, stage, lambda o: late_cut(
        cl, airport, law, base_solution, rules=rules, out=o, **mode), out)
    derived, t_derive = late_derive(derive, cut)
    return records.solve(cut, derive, derived, t_derive, stage, lambda o: late_solve(
        cut, derived, t_derive, airport, law, base_solution, options=options, out=o,
        **mode, **solve_kw), out)


def with_cells(cl_cut, extra: _t.Sequence[_t.Any]):
    """The next stage's classification: the stage before's cut ``cl_cut``
    with ``extra`` (the pad road cells, the car lots) appended under fresh
    ids."""
    nid = max((c.id for c in cl_cut.cells), default=-1) + 1
    return _dc.replace(cl_cut, cells=tuple(cl_cut.cells) + tuple(
        _dc.replace(c, id=nid + k) for k, c in enumerate(extra)))


def _junior_faces(pm, stage: str) -> frozenset[int]:
    """THE LATER STAGES' FACES ON THE ONE LATE MAP (#2206): what ``stage``
    solves as if absent — every car lot (the gap pieces' and the pad roads'
    stages: the lots come last of all, #2114), and every pad road, run-out
    strip and run-out bank (the gap pieces' stage: a pad road is junior to
    a gap piece, 13a (1))."""
    from ..model.planar import is_collar_ref, pad_road_faces, platform_ref_of
    if stage == "car_lots":
        return frozenset()
    out = {f.id for f in pm.faces.values() if is_car_lot_ref(f.ref)}
    if stage == "gap":
        runs = getattr(pm, "ramp_runouts", None) or {}
        out |= {f.id for f in pad_road_faces(pm)}
        out |= {f.id for f in pm.faces.values()
                if str(f.ref).split("#")[0] in runs
                or (is_collar_ref(f.ref) and platform_ref_of(f.ref) in runs)}
    return frozenset(out)


def run_last_stages(cl, airport, law: Law, derive: _t.Callable[[_t.Any], tuple],
                    base_solution: _t.Mapping[str, _t.Any], *,
                    out: _t.Callable[[str], None] = print, rules=None, options=None,
                    records: _t.Any = None, **solve_kw) -> tuple[_t.Any, _t.Any, dict]:
    """THE LAST STAGES, ON ONE MAP (#2206; owner 2026-11-21: "we shouldn't be
    rerunning that long complex calculation more than once per airport"):
    the gap pieces, then the pad roads (issue #609; 13a (1): junior to every
    pavement they meet, the gap pieces too), then THE CAR LOTS (#2114 round 2,
    ``pipeline/car_lot_stage``: a gap piece and a pad road are standing
    ground to a car lot) — in that order, each solved against every level
    the stages before it gave.

    ALL THREE CUTS READ THE BASE.  The gap pieces are cut by the base's
    levels (§55); the pad roads by their pads' levels and the ramp feet's
    (``pad_road_exit``, ``ramp_runout``) — constants of the gap stage, so
    the cut off the base IS the gap stage's wherever no level it reads
    moved (cold-patch 300 s §3.1 C4b measured it so); the car lots against
    the base map's faces and the cells the two cuts before them minted
    (``car_lot_cut``'s ``held``).  So the full classification is known
    before any late solve, and the caller's prefix runs ONCE on it
    (``derive``).  Each stage then solves on that one map with the later
    stages' faces withheld (:func:`_junior_faces`, ``late_solve``'s
    ``withheld``): they neither follow nor hold, the vertices only they
    carry leave its solve with their rows.  MEASURED before (#2206, the
    app's ledger 2026-11-20): KATL ran this prefix four times in its solve
    (1,955 s of 3,874), HECA 1,754 s, LFPG 2,312 s.

    ``records`` (``pipeline/late_records.LateRecords``): the cuts and the
    solves through their stage-cache records, the derive through the
    prefix's.  The car lots' stage reads the rows standing under its
    constants (the stage before it's ``cs_full``, or ``base_solution
    ["cs"]`` with no stage before it)."""
    from .car_lot_stage import lot_cells
    lots = lot_cells(cl)
    roads = [c for c in cl.cells if is_pad_road_cell(c)]
    plain = _dc.replace(cl, cells=tuple(c for c in cl.cells
                                        if not (is_pad_road_cell(c) or is_car_lot_ref(c.ref))))
    standing = {id(c) for c in plain.cells if not is_gap_ref(c.ref)}

    def _cut(cl_x, stage: str, **mode) -> LateCut:
        def run(o):
            return late_cut(cl_x, airport, law, base_solution, rules=rules, out=o, **mode)
        return run(out) if records is None else records.cut(cl_x, stage, run, out)
    cuts: list[tuple[str, LateCut, dict]] = []
    cl_x = plain
    if any(is_gap_ref(c.ref) for c in plain.cells):
        cuts.append(("gap", _cut(plain, "gap"), {}))
        cl_x = cuts[-1][1].cl
    if roads:
        out(f"LAST STAGE, then the pad roads ({len(roads)} cells), cut off the base (13a (1))")
        mode = {"roads_only": True}
        cuts.append(("pad_roads", _cut(with_cells(cl_x, roads), "pad_roads", **mode), mode))
        cl_x = cuts[-1][1].cl
    if lots:
        out(f"LAST STAGE, then the car lots ({len(lots)} cells) against it (#2114 round 2)")
        held = [_poly(c.ring, c.holes) for c in cl_x.cells if id(c) not in standing]
        cuts.append(("car_lots", _cut(with_cells(cl_x, lots), "car_lots", lots_only=True,
                                      held=held), {"lots_only": True}))
    if not cuts:
        raise ValueError("run_last_stages: no gap piece, pad road or car lot to solve")
    if lots and base_solution.get("cs") is None and len(cuts) == 1:
        raise ValueError("run_last_stages: the car lots' stage needs the standing rows "
                         "(base_solution['cs'])")
    out(f"LAST STAGES ON ONE MAP (#2206): {' -> '.join(s for s, _c, _m in cuts)}, "
        f"one derive")
    derived, t_derive = late_derive(derive, cuts[-1][1])
    base, prev = dict(base_solution), None
    for stage, cut, mode in cuts:
        kw = {**mode, "withheld": _junior_faces(derived[0], stage),
              "rim_base": base_solution if stage == "pad_roads" else None}

        def run(o, cut=cut, base=base, kw=kw):
            return late_solve(cut, derived, t_derive, airport, law, base, options=options,
                              out=o, **kw, **solve_kw)
        pm, sol, rep = (run(out) if records is None else
                        records.solve(cut, derive, derived, t_derive, stage, run, out))
        if prev is not None:
            rep = (_gap_then_roads if stage == "pad_roads" else _then_lots)(prev, rep)
        prev = rep
        base = {"pm": pm, "z": sol.z, "pin_yield": rep["pin_yield"],
                "hard_conflict": rep["hard_conflict"], "cs": rep["cs_full"],
                "withheld": rep.get("withheld") or ()}
    # the one derive, counted once
    prev["wall_s"] = {**prev["wall_s"], "derive": round(t_derive, 2)}
    prev["one_map"] = {"stages": [s for s, _c, _m in cuts], "derives": 1}
    return pm, sol, prev


def _summed(a: dict, b: dict) -> dict:
    """Two stages' ``wall_s`` (cut and solve summed; the derive is one)."""
    return {k: round(a[k] + b[k], 2) if k != "derive" else a[k] for k in a}


def _gap_then_roads(rep_g: dict, rep: dict) -> dict:
    """The pad roads' report over the gap stage's: the gap stage's records
    stand, its follow rows join the final set (the same map), its followers
    and the roads' are the stage's."""
    rep = dict(rep)
    g_rows = [r for r in rep_g["cs_full"].rows() if r.source.generator == _GAP_GEN]
    rep["cs_full"] = ConstraintSet.from_rows([*rep["cs_full"].rows(), *g_rows])
    rep["cut"], rep["follow"] = rep_g["cut"], rep_g["follow"]
    rep["gap_stage"] = {"followers": rep_g["followers"], "join": rep_g["join"],
                        "dropped": rep_g["dropped"], "wall_s": rep_g["wall_s"],
                        "follow_rows_carried": len(g_rows), "follow_rows": len(g_rows)}
    refs = sorted({*rep_g["stage"]["followers"], *rep["stage"]["followers"]})
    rep["stage"] = {**rep_g["stage"], "followers": refs}
    rep["followers"] = {**rep["followers"], "gap_faces": rep_g["followers"]["gap_faces"],
                        "follower_ribbon_refs": refs, "follower_ribbons": len(refs)}
    rep["wall_s"] = _summed(rep_g["wall_s"], rep["wall_s"])
    rep["design"].stages["gap_stage"] = dict(rep_g["design"].stages)
    return rep


def _then_lots(prev: dict, lot: dict) -> dict:
    """The car lots' report over the stages before it (their records stand;
    the final map's sets and the solve's records are the lots')."""
    rep = {**prev, **{k: lot[k] for k in ("cl", "cs", "cs_full", "fixed", "strips",
                                          "pin_yield", "design", "hard_conflict",
                                          "car_lots")}}
    rep["wall_s"] = _summed(prev["wall_s"], lot["wall_s"])
    rep["design"].stages["gap_and_road_stages"] = dict(prev["design"].stages)
    return rep
