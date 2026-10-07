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
from ..constraints.ceiling import RULING as _CEILING_RULING
from ..constraints.gap_follow import gap_follow_rows, reach_m
from ..constraints.pavement_cap import RULING as _FALLBACK_RULING
from ..law import Law
from ..law.tables import is_rigid_role, role_cap, snap_margin_m
from ..model.constraints import ConstraintSet
from ..model.planar import face_edge_ids, is_gap_ref, is_osm_ribbon_ref
from ..planar.chords import stations as _chord_stations
from .stage_one_map import (late_constraints, late_fixed, late_followers,
                            late_rim_levels)

__all__ = ["late_stations", "cut_classification", "run_late_stage"]

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
    rows).  A mapped-road ribbon welded to a piece is a follower (an
    unknown), never a station; a ribbon beside no piece is a standing ring."""
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
    reach = reach_m(law)
    spacing = float(law.tables.emit.chords.station_spacing_m)
    V = pm_base.vertices
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
        for i in sorted(tree.query(rim, predicate="dwithin", distance=reach).tolist()):
            (ax, ay), (bx, by) = segs[i]
            za, zb, cls, cap, knife, name = meta[i]
            length = float(shapely.length(lines[i]))
            pts = _chord_stations([(ax, ay), (bx, by)], spacing)
            near = shapely.dwithin(shapely.points(pts), rim, reach)
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
    mint is unchanged), and the per-piece report."""
    gap = [c for c in cl.cells if is_gap_ref(c.ref)]
    rep: dict = {"pieces": [], "parts": 0, "knives": 0, "merged": 0, "stations": 0}
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
        for p in cut.parts:
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


def run_late_stage(cl, airport, law: Law, derive: _t.Callable[[_t.Any], tuple],
                   base_solution: _t.Mapping[str, _t.Any], *, rules=None,
                   options=None, out: _t.Callable[[str], None] = print,
                   **solve_kw) -> tuple[_t.Any, _t.Any, dict]:
    """THE LAST STAGE (spec §55 (4)).  ``base_solution`` is the base map and
    its solved levels (``{"pm", "z"}``); ``derive(cl) -> (pm, cs, strips,
    hold)`` is the CALLER's own prefix (the build's, the replay's), run here
    on the classification with the pieces cut.  ``(full map, solution,
    report)``; the report carries the stage's own row set (``cs``), its
    constants (``fixed``) and the solve's report (``design``)."""
    from ..law.tables import design as _design_law
    from ..solve import feasibility as _feas
    from ..solve.design import solve_late_stage
    if rules is None:
        from ..classify.rules import load_rules
        rules = load_rules()
    pm_base, z_base = base_solution["pm"], base_solution["z"]
    t0 = time.perf_counter()
    cl_cut, cut = cut_classification(cl, pm_base, z_base, law, rules)
    t_cut = time.perf_counter() - t0
    out(f"LAST STAGE cut (§55 (2)-(3)) {t_cut:.1f} s: {len(cut['pieces'])} pieces -> "
        f"{cut['parts']} parts, {cut['knives']} knives, {cut['stations']} stations, "
        f"{cut['merged']} stations merged by the floors")
    t0 = time.perf_counter()
    pm, cs, strips, _hold = derive(cl_cut)
    t_derive = time.perf_counter() - t0
    free, frep = late_followers(pm)
    ident = float(law.tables.emit.identity.min_distinct_spacing_m)
    fixed, jrep = late_fixed(pm_base, z_base, pm, free, ident)
    jrep["rim"] = late_rim_levels(pm_base, z_base, pm, fixed, free, ident * 0.02)
    cs_all = cs
    cs, dropped = late_constraints(
        cs, fixed, frozenset(getattr(_design_law(law), "yielding_pin_rulings", ()) or ()),
        retier_heads=frozenset(r.split("(")[0].strip()
                               for r in (_CEILING_RULING, _FALLBACK_RULING)))
    out(f"LAST STAGE (§53 (9)): followers {frep}; join {jrep}; "
        f"rows with no unknown dropped {dropped}")
    grows, grep = gap_follow_rows(pm, law, fixed)
    cs = ConstraintSet.from_rows([*cs.rows(), *grows])
    cs_full = ConstraintSet.from_rows([*cs_all.rows(), *grows])
    # the lot SITS at its road's level: the one published-target channel
    lot_z = grep.get("lot_targets") or {}
    if lot_z:
        pm = _dc.replace(pm, preferred_z={**dict(pm.preferred_z), **lot_z})
    out(f"LAST STAGE gap_follow (§53 (13)): {grep['rows']} rows; "
        f"{len(grep['conflicts'])} vertices between two disagreeing neighbours; "
        f"lot rows (§55 (3) 4) {grep.get('lot_rows', 0)}, lot_fit targets {len(lot_z)}")
    t0 = time.perf_counter()
    # THE BASE'S RELAXATIONS STAY PUBLISHED (§55 (4) iv): the last solve
    # publishes its own conflict records over the registry; the earlier
    # stages' (the caller's own solve, or the pickled base's) come first
    base_conf = [dict(r) for r in (base_solution.get("hard_conflict")
                                   if "hard_conflict" in base_solution
                                   else _feas.HARD_CONFLICT)]
    sol, design = solve_late_stage(pm, cs, law, fixed, options, **solve_kw)
    _feas.publish([*base_conf, *_feas.HARD_CONFLICT])
    t_solve = time.perf_counter() - t0
    feas = getattr(design, "hard_feasibility", None)
    if feas is not None:
        out(f"LAST STAGE relaxed by head (§55 (5)): {feas.by_head_line()}")
    off = [abs(float(sol.z[v]) - z) for v, z in fixed.items()] if sol.z else []
    out(f"LAST STAGE: fixed vertices off their constant by > 0.02 m: "
        f"{sum(1 for d in off if d > 0.02)} of {len(off)} (worst {max(off, default=0.0):.3f} m)")
    report = {"cut": cut, "cl": cl_cut, "followers": frep, "join": jrep,
              "dropped": dropped, "follow": grep, "cs": cs, "cs_full": cs_full,
              "fixed": fixed, "strips": strips, "pin_yield": _carry_pin_yield(base_solution, pm_base, pm),
              "design": design,
              "wall_s": {"cut": round(t_cut, 2), "derive": round(t_derive, 2),
                         "solve": round(t_solve, 2)}}
    return pm, sol, report
