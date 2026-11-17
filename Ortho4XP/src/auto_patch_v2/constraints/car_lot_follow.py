"""A CAR LOT MEETS A STANDING NEIGHBOUR ONLY WHERE ITS OWN GROUND DOES
(#2114 round 2 P3; owner RULINGS 2026-11-16p "welded to any pad or road it
touches", read with 16t) — the car-lot stage's own generator.

A car lot (``classify/car_lot``) is a LAST-STAGE cell: every standing level
is a constant when it is solved, and it stands off every standing ring by
the §52 stand-off, so no generator that reads a shared rim ties it to the
pad, road, apron, band or lot beside it.  Its body takes its own ground
(each vertex's DEM, under the lot law's cap).  At its rim, for a lot vertex
``v`` within the follow reach of a standing ring (``gap_follow.reach_m``,
the pad's covering its set-back), at the ring's nearest point ``S`` with
solved level ``z_S`` and plan distance ``d``:

- CONSISTENT when ``|z_S - g_v| <= cap x d + step``, ``g_v`` the lot's OWN
  GROUND at ``v`` — the DEM where its nearest counted car stands (the
  pack's own statement of where the lot surface is) — and ``step`` the
  ``[terrace] car_lot_weld_step_m`` law key;
- consistent: ONE one-way follow row ``|z_v - z_S| <= cap x d`` (the gap
  piece's form, ``gap_follow.bound_row``; from the set-back for a pad):
  the lot meets the neighbour with no step;
- not consistent: NO row.  The stand-off is a DECLARED TERRACE — the pad's
  edge the kerb or bank (§28 (6), RULINGS 2026-11-10a (5)) — published
  with both levels (``report["terraces"]``).

This one test, at this one site, stands in for a car lot where §28's
frontage row (``constraints/pad_frontage_gs``), the apron-edge ramp
(``constraints/groundside.groundside_ramps``) and the §37 (10) road-end
contact (``constraints/road_ramp``) bind any other groundside face: the
stage keeps no row between a car lot and a constant but this one
(``pipeline/stage_one_map.late_constraints`` ``alone``).  MEASURED (round 1,
the lot in the one solve): §28 bound KBNA's lots 231/232 to pad
``building40`` (62 rows), lifting them 1.9 / 2.9 m over the lidar."""
from __future__ import annotations

import typing as _t

import numpy as np
import shapely
from scipy.spatial import cKDTree
from shapely.strtree import STRtree

from ..law import Law
from ..law.tables import role_cap
from ..model.constraints import Linear
from ..model.planar import PlanarMap, face_vertex_set, is_car_lot_ref
from .gap_follow import BehindStep, bound_row, reach_m, standing_rings

__all__ = ["GEN", "RULING", "car_lot_follow_rows"]

GEN = "car_lot_follow"
RULING = "car lot meets its standing neighbour where its own ground does (owner 2026-11-16p)"


def _weld_step_m(law: Law) -> float:
    """THE STEP UNDER WHICH A CAR LOT WELDS (``[terrace]
    car_lot_weld_step_m``)."""
    return float(law.tables.emit.terrace.car_lot_weld_step_m)


def _own_ground(planar: PlanarMap, lots, anchors: _t.Mapping[str, np.ndarray],
                dem) -> dict[int, float]:
    """``{lot vertex: g_v}``, the DEM at the nearest counted car of the
    vertex's own lot (a lot with no anchor, or no DEM: absent)."""
    out: dict[int, float] = {}
    if dem is None:
        return out
    for f in lots:
        cars = anchors.get(str(f.ref).split("#")[0])
        if cars is None or not len(cars):
            continue
        vs = sorted(face_vertex_set(planar, f))
        _d, k = cKDTree(cars).query([planar.vertices[v].xy for v in vs])
        for v, i in zip(vs, np.atleast_1d(k).tolist()):
            out.setdefault(v, float(dem.z(*cars[i])))
    return out


def car_lot_follow_rows(planar: PlanarMap, law: Law, fixed: _t.Mapping[int, float],
                        anchors: _t.Mapping[str, np.ndarray], dem,
                        behind_step: BehindStep | None = None
                        ) -> tuple[list[Linear], dict]:
    """The follow rows of every car-lot vertex that is an UNKNOWN (module
    docstring) and the report: ``rows``; ``terraces`` — one record per
    (lot, ring) held apart, at the vertex where the ring's level and the
    lot's own ground differ most; ``welded_lots`` / ``terraced_lots`` — the
    lots that took a row / declared a terrace; ``conflicts`` as
    ``gap_follow``'s.  ``anchors``: ``{lot ref: car anchors}``
    (``classify/car_lot.car_anchors``)."""
    rep: dict = {"rows": 0, "terraces": [], "welded_lots": 0, "terraced_lots": 0,
                 "conflicts": []}
    lots = [f for f in planar.faces.values() if is_car_lot_ref(f.ref)]
    if not lots:
        return [], rep
    pc = role_cap(law, lots[0].role)
    cap_p = float(pc.longitudinal) if pc else 0.0
    rings = standing_rings(planar, law, fixed, cap_p, lambda f: is_car_lot_ref(f.ref),
                           behind_step)
    if rings is None:
        return [], rep
    tree = STRtree(rings.lines)
    drop_tree = STRtree(rings.drops) if rings.drops is not None else None
    reach, reach_pad = reach_m(law), reach_m(law, pad=True)
    step = _weld_step_m(law)
    ground = _own_ground(planar, lots, anchors, dem)
    lot_of = {v: str(f.ref).split("#")[0] for f in lots for v in face_vertex_set(planar, f)}
    V = planar.vertices
    rows: list[Linear] = []
    held: dict[tuple[str, str], dict] = {}
    welded: set[str] = set()
    for v in sorted(set(lot_of) - set(fixed)):
        best = rings.bounds(shapely.points(V[v].xy), reach, reach_pad, tree, drop_tree)
        g = ground.get(v)
        for name in sorted(best):
            _d, z, allow, _at = best[name]
            off = abs(z - g) if g is not None else 0.0
            if off > allow + step:
                best.pop(name)
                key = (lot_of[v], name)
                if key not in held or off > held[key]["off_m"]:
                    held[key] = {"lot": lot_of[v], "ring": name, "xy": tuple(V[v].xy),
                                 "ring_m": round(z, 3), "ground_m": round(g, 3),
                                 "off_m": round(off, 3)}
        if best:
            welded.add(lot_of[v])
            rows.append(bound_row(v, V[v].xy, best, rep["conflicts"], GEN, RULING))
    rep["rows"] = len(rows)
    rep["terraces"] = [held[k] for k in sorted(held)]
    rep["welded_lots"] = len(welded)
    rep["terraced_lots"] = len({k[0] for k in held})
    return rows, rep
