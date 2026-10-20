"""THE LANDING'S RUN-OUT — a viaduct ramp that lands on a 10-03e LANDING
comes down to the ground at road grade, not down the 1:3 bank (issue #711;
owner RULINGS 2026-10-14c (5) applied at the 10-03e landings).

The owner, at HECA's T3 viaduct (30.1113555, 31.392245, app 1.0.394): "The
elevated ramps that are landing around here should have ground graded down
at road grade, it's too steep right now."  MEASURED (sw33): the landing
``building4/landing4`` held at 101.63 m over a raw DEM of 95.5 m; along the
ramp's direction of travel the collar fell to the lot ``dsf:pol10`` at
95.36 m within 5-10 m of the foot (a 6.3 m drop, steeper than the 1:3 bank
the collar was minted for).

THE RUN-OUT, minted where the landing is (``planar/landing``, after every
landing platform and BEFORE any collar): for each object ramp foot
(``airport/ramp_feet``) standing on a landing, a strip of the foot's width
leaves the foot along its direction of travel, as long as the shared ramp law
(``geom/ramp_profile.runout_profile``: design ``[road_contact] ramp_grade``
off the landing's level, never steeper than the road's own cap) needs to
meet the raw DEM from the highest level the solve may hold the landing at
(the block's PREDICTED datum ``held[block]["datum_pred"]`` + its widest
reach band + the deck's ``y``: MEASURED at HECA's T3 the prediction stood
1.7-1.9 m under the solved datum).  The rows
(``constraints/ramp_runout.landing_runout_rows``) read the SOLVED datum:
never above the landing, never steeper than the design profile or the
road cap off it, and the ground objective lays the strip on its DEM once
the profile has met it.  The strip is a ROAD (``service_road``, ref
``runout:<landing ref>``), a base region: the LOT it crosses is cut back
from it (``planar/landing.landing_cut``), roads and every other standing
region keep their ground (the strip yields to them).  Its SIDES are banked
by the landing's own 1:3 collar (14c (5): "the 1:3 bank of 10-03e stays
for the ramp's sides"), its END meets what lies ahead at the DEM's level.

A foot whose landing has no predicted datum, whose ground ahead is held
(another pad, the airside) within the run, or that already stands within
``[cockpit] visual_m`` of its ground asks nothing; each is counted.
"""
from __future__ import annotations

import math
import typing as _t

from shapely.geometry import LineString, Point, Polygon
from shapely.ops import unary_union

from ..geom.parts import nonempty_polygon_parts as _parts

__all__ = ["RUNOUT_REF_PREFIX", "runout_ref", "landing_runouts"]

#: the strip's ref: ``runout:<landing ref>`` (the last stage's object-ramp
#: run-outs are ``runout:<k>``, ``classify/ramp_runout``)
RUNOUT_REF_PREFIX = "runout:"

#: the run's bound (``classify/ramp_runout.MAX_RUN_M``'s value)
MAX_RUN_M = 400.0


def runout_ref(landing_ref: str) -> str:
    return f"{RUNOUT_REF_PREFIX}{landing_ref}"


def landing_runouts(plats: _t.Sequence[tuple], held: _t.Mapping[str, dict], airport, law,
                    taken, near_m: float, grid: float, counts: dict
                    ) -> dict[str, dict[str, _t.Any]]:
    """``{run-out ref: record}`` for every ramp foot standing on a landing of
    ``plats`` (``planar/landing``'s PASS 1 tuples ``(ref, Ls, Lu, y_land,
    key, bref, ...)``).  ``taken`` is what no run-out may take (the
    platforms, every pad, the airside and its bank); ``near_m`` how near a
    foot's lip stands to its landing.  The record carries the strip
    polygons (``polys``), the lip, the direction, the landing / block / y,
    and the long section relative to the landing's level (``profile``:
    ``[(s, dz)]``)."""
    from ..airport.ramp_feet import ramp_feet
    from ..geom.ramp_profile import runout_profile
    from ..law.tables import role_cap
    frame, dem = getattr(airport, "frame", None), getattr(airport, "dem", None)
    if frame is None or dem is None or not plats:
        return {}
    feet = ramp_feet(airport, law, frame.entry())
    if not feet:
        return {}
    g = float(law.tables.emit.road_contact.ramp_grade)
    rc = role_cap(law, "service_road")
    cap = float(rc.longitudinal) if rc is not None else g
    band = float(law.tables.emit.cockpit.visual_m)
    step = float(law.tables.emit.chords.station_spacing_m)
    out: dict[str, dict[str, _t.Any]] = {}
    held_ground = taken
    stat = {"feet": 0, "no_datum": 0, "at_grade": 0, "held_ahead": 0, "taken": 0}
    for f in feet:
        (lx, ly), (dx, dy), h = f.lip, f.direction, 0.5 * f.width_m
        lip = Point(lx, ly)
        land = min(plats, key=lambda p: p[2].distance(lip))
        ref, _Ls, Lu, y_land, _key, bref = land[:6]
        if Lu.distance(lip) > near_m:
            continue
        stat["feet"] += 1
        hb = held.get(bref) or {}
        datum = hb.get("datum_pred")
        if datum is None:
            stat["no_datum"] += 1
            continue
        z0 = float(datum) + float(y_land)
        # THE RUN'S LENGTH: the profile off the HIGHEST level the solve may
        # hold the block at — its predicted datum plus the widest REACH band
        # the datum pin clips it into (``planar/pad_blocks``).  The strip's
        # rows read the SOLVED datum (``constraints/ramp_runout``), so a
        # strip longer than its descent lies on its own ground beyond it.
        reach_hi = max((float(r) for r in (hb.get("samples_reach") if hb.get(
            "samples_reach") is not None else ())), default=0.0)
        def ground(s: float) -> float:
            return float(dem.z(lx + dx * s, ly + dy * s))
        prof = runout_profile(z0 + reach_hi, ground, g, cap, MAX_RUN_M)
        run = prof[-1][0]
        if abs(z0 + reach_hi - ground(0.0)) <= band or run <= grid:
            stat["at_grade"] += 1
            continue
        nx, ny = -dy, dx
        # the strip's two sides carry PAIRED stations (``[chords]
        # station_spacing_m``): the road's cross-section rows pair a side's
        # vertex with the other side's at the same station — unpaired, the
        # 2 % cross-fall and the long section contest (MEASURED, HECA:
        # stations 35.9 / 47.7 m apart across the strip, 0.41 m relaxed)
        ss = [min(run, k * step) for k in range(int(math.ceil(run / step)) + 1)]
        R = Polygon([(lx + dx * s + nx * -h, ly + dy * s + ny * -h) for s in ss]
                    + [(lx + dx * s + nx * h, ly + dy * s + ny * h) for s in reversed(ss)])
        # a pad or the airside standing in the run: the ground between is
        # graded between the two, never run out to the DEM short of it.  A
        # SIBLING foot's strip is not such a stand: two ramps landing side by
        # side run out together, the later strip on the ground the earlier
        # left (MEASURED, HECA T3, #711: the 14 % main ramp's strip crossed
        # the run of the gentle ramp beside it, which then ran out nowhere)
        hit = R.intersection(held_ground).difference(Lu.buffer(near_m))
        if hit.area > max(grid * grid, 1.0):
            stat["held_ahead"] += 1
            continue
        got = [q for q in _parts(R.difference(Lu).difference(taken))
               if q.area >= max(grid * grid, 1.0) and q.distance(Lu) <= near_m]
        if not got:
            stat["taken"] += 1
            continue
        k = sum(1 for r in out if r.startswith(runout_ref(ref)))
        rref = runout_ref(ref) if not k else f"{runout_ref(ref)}#{k}"
        lat, lon = frame.transformers()[1](lx, ly)
        out[rref] = {"landing": ref, "block": bref, "y": float(y_land),
                     "lip": (float(lx), float(ly)), "dir": (float(dx), float(dy)),
                     "width_m": float(f.width_m), "z0_pred": round(z0, 3),
                     "reach_m": round(reach_hi, 3), "g": g, "cap": cap,
                     "dem0": round(ground(0.0), 4),
                     # the raw ground along the run, relative to the lip's
                     "ground": [(float(s_), round(ground(s_) - ground(0.0), 4))
                                for s_, _z in prof[::2] + prof[-1:]],
                     "run_m": round(run, 1), "polys": got,
                     "axis": LineString([(lx, ly), (lx + dx * run, ly + dy * run)]),
                     "at": (round(lat, 7), round(lon, 7))}
        taken = unary_union([taken, *got])
    counts["landing_runouts"] = len(out)
    counts["landing_runout_feet"] = stat
    if out:
        counts["landing_runout_list"] = "; ".join(
            f"{r} lip {v['at'][0]},{v['at'][1]} z0 {v['z0_pred']:.2f} run {v['run_m']:.0f} m "
            f"x {v['width_m']:.0f} m" for r, v in sorted(out.items()))
    return out
