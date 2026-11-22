"""THE CAR LOTS' OWN STAGE (#2114 round 2 P1; owner RULINGS 2026-11-16p) —
the last of the last stages (``pipeline/late_stage.run_last_stages``).

A car lot (``classify/car_lot``) is in neither the base map nor the base
solve (``pipeline/stage_one_map.gap_free``).  It is cut, mapped and solved
AFTER every other stage — the gap pieces and the pad roads included — with
every level they gave a CONSTANT, through the same machinery a gap piece
is: the caller's own prefix on the full classification
(``late_stage.late_derive``), the followers (``late_followers``
``lots_only``), the constants by the canonical join (``late_fixed``,
``late_rim_levels``) and ``solve.design.solve_late_stage``.  What is the
car lots' own:

- THE CUT (P4/P5, ``classify/car_lot.cut_car_lots``): each lot cut against
  every face of the solved map grown by the §52 stand-off, the adjacent-
  ground bands included — a lot never takes a band's ground;
- ALONE (``late_constraints`` ``alone``): no row couples a lot to a
  constant but the stage's own follow row (P3,
  ``constraints/car_lot_follow``): §28's frontage, the apron-edge ramp and
  the road-end contact read a car lot nowhere;
- THE ROWS THAT STAND (``cs_full``): the earlier stages' set carried to the
  final map by the canonical join, plus the lots' own rows — never the
  full map's re-derivation, which is not the set those levels were solved
  under.

Nothing standing moves BY CONSTRUCTION: every vertex of the earlier map is
a constant here.  MEASURED (round 1, the lot in the one map and the one
solve, KBNA): 229 standing nodes moved > 0.1 m — a pad 0.33 m, a zone band
0.40 m, road ends 4.6 m — and 48 standing nodes were new."""
from __future__ import annotations

import dataclasses as _dc
import time
import typing as _t

from ..classify.car_lot import car_anchors, cut_car_lots
from ..constraints.car_lot_follow import car_lot_follow_rows
from ..law import Law
from ..model.constraints import ConstraintSet
from ..model.planar import is_car_lot_ref
from .stage_one_map import (
    late_constraints,
    late_fixed,
    late_followers,
    late_rim_levels,
    remap_row,
    row_vertices,
)

__all__ = ["car_lot_cut", "car_lot_solve", "lot_cells"]


def lot_cells(cl) -> list:
    """The car-lot cells of ``cl``."""
    return [c for c in cl.cells if is_car_lot_ref(c.ref)]


def car_lot_cut(cl, pm_base, law: Law, rules, extra: _t.Sequence = ()) -> tuple[_t.Any, dict]:
    """``cl`` with every car lot cut against the solved map ``pm_base``
    (P4/P5) and ``extra`` (#2206: the polygons of the late cells cut
    before it, which the one late map will carry) — the late cut's report
    shape, ``car_lots`` the lots' own."""
    lots = lot_cells(cl)
    rest = _dc.replace(cl, cells=tuple(c for c in cl.cells if not is_car_lot_ref(c.ref)))
    from .late_stage import with_cells
    parts, rep = cut_car_lots(lots, pm_base, law, rules, extra)
    return with_cells(rest, parts), {"pieces": [], "parts": 0, "knives": 0, "merged": 0,
                                     "stations": 0, "part_stations": {}, "car_lots": rep}


def _carry_rows(cs: ConstraintSet, pm_from, pm_to) -> tuple[list, int]:
    """Every row of ``cs`` (on ``pm_from``) read onto ``pm_to`` by the
    canonical join (vertex coordinate); ``(rows, lost)``."""
    at = {tuple(v.xy): i for i, v in pm_to.vertices.items()}
    vmap = {i: at[tuple(v.xy)] for i, v in pm_from.vertices.items() if tuple(v.xy) in at}
    out, lost = [], 0
    for r in cs.rows():
        q = remap_row(r, vmap) if all(v in vmap for v in row_vertices(r)) else None
        if q is None:
            lost += 1
        else:
            out.append(q)
    return out, lost


def _carry_published(pm_from, pm_to):
    """``pm_to`` with what the stages before PUBLISHED on their map and no
    derive re-mints — the pad roads' released grades (13e,
    ``pad_road_released``, by face: same ref, same ring) and the published
    targets (``preferred_z``, the gap lots' road level, by the canonical
    join).  MEASURED (KBNA replay, before this): the fresh map dropped
    ``small_roads:-2919#1``'s released grade and the census judged 19 rows
    on it at the road cap."""
    from ..model.planar import face_cycles
    at = {tuple(v.xy): i for i, v in pm_to.vertices.items()}
    pref = {**dict(pm_to.preferred_z),
            **{at[tuple(pm_from.vertices[v].xy)]: z for v, z in pm_from.preferred_z.items()
               if tuple(pm_from.vertices[v].xy) in at}}

    def key(pm, f):
        return (str(f.ref), frozenset(tuple(pm.vertices[v].xy)
                                      for cyc in face_cycles(pm, f) for v in cyc))
    released = dict(getattr(pm_from, "pad_road_released", None) or {})
    if released:
        by_key = {key(pm_to, f): f.id for f in pm_to.faces.values()}
        released = {by_key[k]: rec for fid, rec in released.items()
                    if (k := key(pm_from, pm_from.faces[fid])) in by_key}
    return _dc.replace(pm_to, preferred_z=pref, pad_road_released=released)


def car_lot_solve(cut, derived: tuple, t_derive: float, airport, law: Law,
                  base_solution: _t.Mapping[str, _t.Any], *, options=None,
                  out: _t.Callable[[str], None] = print, **solve_kw
                  ) -> tuple[_t.Any, _t.Any, dict]:
    """The car lots solved alone against the constants (module docstring):
    ``(full map, solution, report)`` in ``late_stage.late_solve``'s shape,
    the stage's own records under ``car_lots``."""
    from ..law.tables import design as _design_law
    from ..solve.design import solve_late_stage
    from .late_stage import BEHIND_STEP, _carry_pin_yield
    pm_base, z_base = base_solution["pm"], base_solution["z"]
    pm, cs, strips, _hold = derived
    pm = _carry_published(pm_base, pm)
    free, frep = late_followers(pm, lots_only=True)
    ident = float(law.tables.emit.identity.min_distinct_spacing_m)
    # the stages before withheld the lots (#2206): no level of theirs
    absent = frozenset(base_solution.get("withheld") or ())
    fixed, jrep = late_fixed(pm_base, z_base, pm, free, ident, absent)
    jrep["rim"] = late_rim_levels(pm_base, z_base, pm, fixed, free | absent, ident * 0.02)
    yheads = frozenset(getattr(_design_law(law), "yielding_pin_rulings", ()) or ())
    own, dropped = late_constraints(cs, fixed, yheads, alone=True)
    anchors = {c.ref: car_anchors(c) for c in lot_cells(cut.cl)}
    rows, follow = car_lot_follow_rows(pm, law, fixed, anchors,
                                       getattr(airport, "dem", None), BEHIND_STEP)
    cs_stage = ConstraintSet.from_rows([*own.rows(), *rows])
    carried, lost = _carry_rows(base_solution["cs"], pm_base, pm)
    cs_full = ConstraintSet.from_rows([*carried, *cs_stage.rows()])
    out(f"LAST STAGE car lots (#2114 round 2): cut {cut.report['car_lots']}; "
        f"followers {frep['vertices']} vertices on {frep['gap_faces']} faces "
        f"({frep['held_on_a_leader']} held on a standing ring); join {jrep}; "
        f"rows dropped {dropped}; standing rows carried {len(carried)} (lost {lost})")
    out(f"LAST STAGE car lots follow (P3): {follow['rows']} rows, "
        f"{follow['welded_lots']} lot(s) welded, {follow['terraced_lots']} with a declared "
        f"terrace ({len(follow['terraces'])} lot|ring pairs), "
        f"{len(follow['conflicts'])} vertices between two disagreeing neighbours")
    t0 = time.perf_counter()
    sol, design = solve_late_stage(pm, cs_stage, law, fixed, options, **solve_kw)
    t_solve = time.perf_counter() - t0
    off = [abs(float(sol.z[v]) - z) for v, z in fixed.items()] if sol.z else []
    out(f"LAST STAGE car lots: fixed vertices off their constant by > 0.02 m: "
        f"{sum(1 for d in off if d > 0.02)} of {len(off)} (worst {max(off, default=0.0):.3f} m)")
    base_conf = [dict(r) for r in (base_solution.get("hard_conflict") or ())]
    report = {"cut": cut.report, "cl": cut.cl, "followers": frep, "join": jrep,
              "pad_ramp": {}, "pad_exits": None, "wall_release": {},
              "stage": {"floor_m": float(law.tables.emit.terrace.pad_terrace_floor_m),
                        "followers": []},
              "dropped": dropped, "follow": {"rows": 0, "conflicts": [], "declared": []},
              "car_lots": {"cut": cut.report["car_lots"], "follow": follow,
                           "carried_lost": lost},
              "cs": cs_stage, "cs_full": cs_full, "fixed": fixed, "strips": strips,
              "pin_yield": _carry_pin_yield(base_solution, pm_base, pm),
              "design": design,
              "hard_conflict": [*base_conf, *(dict(r) for r in design.hard_conflict)],
              "wall_s": {"cut": round(cut.wall_s, 2), "derive": round(t_derive, 2),
                         "solve": round(t_solve, 2)}}
    return pm, sol, report
