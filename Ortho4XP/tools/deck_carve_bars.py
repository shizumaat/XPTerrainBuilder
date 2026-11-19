"""LIBRARY of ``tools/deck_probe.py --carve`` (owner RULINGS 2026-11-19s
(2)-(4); owner 2026-11-19T23:07Z / 23:09Z: the cut is the deck's and
grades smoothly back to the terrain): THE CUT UNDER EVERY GENERATED DECK,
read off a ``--solved-out`` pickle, per deck and per path of its cut
(``DeckBridge.carve``, ``planar/deck_carve``):

* EVIDENCE and DIRECTION: what put the deck there and which way its ramps
  run (the record's);
* CLEARANCE: at every station of the path under the ring (every
  :data:`STEP_M`) and every mapped road node there, the deck's underside
  (its top -- the Coons patch of the solved airside on its ring,
  ``constraints/deck_floor_follow._patch`` -- less ``[deck_gen]
  thickness_m``) over the solved surface; bar ``>= `` the road's clearance;
* FLOOR: the solved floor under the deck against the rule
  ``min(lidar road floor, underside - clearance)`` (the lidar road its
  lowest survey within ``[deck_gen] level_probe_m`` of the stretch; the
  deck's one floor is the deepest any of its roads asks);
* RAMPS: from each outermost stretch outward, the solved surface along the
  path until it stands within :data:`MEET_M` of the surveyed ground -- the
  ramp's length (``None``: it never met it, the shortfall) and its steepest
  grade over :data:`GRADE_WINDOW_M`; bar ``<= `` the path's cap;
* EMBANKMENT: across the deck along its route through the path's
  crossing, the steepest solved slope over :data:`GRADE_WINDOW_M` between
  the end lines and the floor (the abutment's bank, 1V:1.5H by law).

The surface is read over each map face within :data:`NEAR_M` of the path,
triangulated on its own ring (``tools/deck_bank_perimeter._interp``: the
way the mesh takes the patch's faces).  Pure: reads
the pickle's map and ``z``; writes nothing.
"""
from __future__ import annotations

import math

__all__ = ["STEP_M", "MEET_M", "EDGE_STEP_M", "GRADE_WINDOW_M", "NEAR_M", "carve_bars"]

#: a path is read this often (m)
STEP_M = 1.0
#: the ramp has met the terrain within this (m): the floor's vertical
#: curves ride a smoothed survey, a lidar road's noise is a few decimetres
MEET_M = 0.30
#: the patch's edge meets the base mesh within this (m)
EDGE_STEP_M = 0.25
#: grades are read over this run (m)
GRADE_WINDOW_M = 4.0
#: the surface is triangulated from the vertices this near the path (m)
NEAR_M = 60.0


def _tin(pm, z, xs, ys):
    """``surf(x, y)``: the solved surface over the path's reach, each map
    face triangulated on its own ring (``deck_bank_perimeter._interp``,
    the way the mesh takes the patch); ``nan`` off every face."""
    from deck_bank_perimeter import _interp
    from shapely.geometry import LineString
    f = _interp(pm, z, LineString(list(zip(xs, ys, strict=True))).buffer(NEAR_M))
    return lambda x, y: float(f([x], [y])[0])


def _top(pm, z, db, law):
    from auto_patch_v2.constraints.deck_floor_follow import _patch
    from auto_patch_v2.model.platform import stage_air_vertices
    air = stage_air_vertices(pm, law)
    patch, _n = _patch(db, None, pm, {v: float(z[v]) for v in air})
    return patch


def _grade(ss, zs) -> float:
    best = 0.0
    j = 0
    for i in range(len(ss)):
        while j < len(ss) and ss[j] - ss[i] < GRADE_WINDOW_M:
            j += 1
        if j < len(ss):
            best = max(best, abs(zs[j] - zs[i]) / max(ss[j] - ss[i], 1e-9))
    return best


def _ramp(frame, surf, terrain, start: float, sign: float) -> tuple:
    """``(length or None, steepest grade)`` from ``start`` outward."""
    import numpy as np
    ts = np.array([t[0] for t in terrain])
    tz = np.array([t[1] for t in terrain])
    ss, zs = [], []
    s = start
    while 0.0 <= s <= frame.length:
        (x, y), _u = frame.at(s)
        q = surf(x, y)
        if q != q:
            # off the patch: the base mesh at the DEM -- met there, with the
            # step the patch's edge stands off the ground
            if zs:
                step = abs(zs[-1] - float(np.interp(s, ts, tz)))
                return (round(abs(s - start), 1) if step <= EDGE_STEP_M else None,
                        round(_grade(ss, zs), 4) if len(ss) > 1 else 0.0)
            break
        ss.append(abs(s - start))
        zs.append(q)
        if abs(s - start) > 2.0 and q >= float(np.interp(s, ts, tz)) - MEET_M:
            return round(abs(s - start), 1), round(_grade(ss, zs), 4)
        s += sign * STEP_M
    return None, round(_grade(ss, zs), 4) if len(ss) > 1 else 0.0


def _bank(pm, surf, db, top, frame, s_mid: float) -> "float | None":
    """The steepest slope across the deck along its route through the
    path's point ``s_mid``, between the end lines (the abutments' banks)."""
    (x, y), (ux, uy) = frame.at(s_mid)
    if top is None:
        return None
    u = top.u
    lu = math.sqrt(u[0] * u[0] + u[1] * u[1])
    if lu < 1e-6:
        return None
    ex, ey = u[0] / lu, u[1] / lu
    ss, zs = [], []
    k = -lu
    while k <= lu:
        q = surf(x + ex * k, y + ey * k)
        if q == q:
            st, _t = top.st(x + ex * k, y + ey * k)
            if 0.0 <= st <= 1.0:
                ss.append(k)
                zs.append(q)
        k += 0.5
    return round(_grade(ss, zs), 3) if len(ss) > 2 else None


def carve_bars(pm, z, law) -> list[dict]:
    """One row per path of every generated deck's cut (module doc)."""
    from auto_patch_v2.geom.carve_profile import PathFrame, smoothed
    from auto_patch_v2.planar.deck_bridge import deck_polygon
    from shapely.geometry import Point
    slab = float(law.tables.structures.deck_gen.thickness_m)
    probe = float(law.tables.structures.deck_gen.level_probe_m)
    decks = {d.object_id: d for d in getattr(pm, "decks", ()) or ()
             if getattr(d, "carve", None) is not None}
    tops = {oid: _top(pm, z, d, law) for oid, d in decks.items()}
    out = []
    for oid, d in sorted(decks.items()):
        dc = d.carve
        top = tops[oid]
        ring = deck_polygon(d)
        for p in dc.paths:
            frame = PathFrame(p.coords)
            xs = [c[0] for c in p.coords]
            ys = [c[1] for c in p.coords]
            surf = _tin(pm, z, xs, ys)
            r = smoothed([t[1] for t in p.terrain])
            terrain = [(t[0], float(q)) for t, q in zip(p.terrain, r, strict=True)]
            row = {"deck": oid, "evidence": list(dc.evidence), "direction": dc.direction,
                   "way": p.way, "kind": p.kind, "need_m": p.clearance_m, "cap": p.cap}
            own = [(a, b) for a, b, o in p.stretches if o == oid]
            clear, floors, unders, lidar = [], [], [], []
            for a, b in own:
                s = a
                while s <= b:
                    (x, y), _u = frame.at(s)
                    if ring.contains(Point(x, y)) and top is not None:
                        q = surf(x, y)
                        if q == q:
                            under = top.z(x, y) - slab
                            clear.append(under - q)
                            floors.append(q)
                            unders.append(under)
                    s += STEP_M
                lidar += [zz for ss, zz in terrain if a - probe <= ss <= b + probe]
            for c in p.coords:
                if ring.contains(Point(c)) and top is not None:
                    q = surf(*c)
                    if q == q:
                        clear.append(top.z(*c) - slab - q)
            row["clearance_min_m"] = round(min(clear), 3) if clear else None
            row["floor_m"] = [round(min(floors), 3), round(max(floors), 3)] if floors else None
            row["floor_rule_m"] = round(min([min(unders) - p.clearance_m] + lidar), 3) \
                if unders else None
            lo = min((a for a, _b, _o in p.stretches), default=None)
            hi = max((b for _a, b, _o in p.stretches), default=None)
            if lo is not None:
                row["ramp_before"] = _ramp(frame, surf, terrain, lo, -1.0)
                row["ramp_after"] = _ramp(frame, surf, terrain, hi, 1.0)
            if own:
                row["bank_slope_max"] = _bank(pm, surf, d, top, frame,
                                              0.5 * (own[0][0] + own[0][1]))
            g = [x for k in ("ramp_before", "ramp_after") if row.get(k) for x in [row[k][1]]]
            row["pass_clearance"] = row["clearance_min_m"] is not None and \
                row["clearance_min_m"] >= p.clearance_m - 0.05
            row["pass_grade"] = all(x <= p.cap + 0.005 for x in g)
            row["pass_meets"] = all(row.get(k) and row[k][0] is not None
                                    for k in ("ramp_before", "ramp_after"))
            out.append(row)
    return out
