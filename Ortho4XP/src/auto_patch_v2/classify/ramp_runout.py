"""THE RAMP FOOT RUNS OUT AT ROAD GRADE (issue #669; owner RULINGS
2026-10-14c (5), amending 2026-10-03e in the direction of travel).

The owner, at a terminal's departures ramp: "If we grade terrain up to meet
an object ramp bottom, we should continue road grade until we get back to
raw dem so we don't have a sharp cliff even if there is no road evidence."
RULED: where the ground is graded to an object ramp's foot, it continues
beyond the foot along the ramp's direction of travel at road grade (design
5 %, cap 10 %) until it meets raw DEM, whether or not a mapped road
continues there; 10-03e's 1:3 bank stays for the ramp's sides.

MEASURED (KCLT, sw27): the departures ramp (``techos_1_charlotte.obj``)
comes down northward to its zero at 35.2223739, -80.9423249; the pack
pavement under it (``gap:0``) stood at 222.2 m to the patch edge 8 m on,
and the raw DEM beyond stood at 218.1 m — a 4 m cliff.

THE RUN-OUT, minted in the LAST STAGE beside the pad-road exits
(``classify/pad_road_exit``), where the level of the ground at the foot is
a solved constant: for each foot (``airport/ramp_feet``) the patch must
hold the ground under the ramp's last ``FOOT_SPAN_M`` (else nothing graded
the ground to it); a strip of the ramp's width leaves the lip along the
direction of travel over the ground no cell holds.  It starts where the
patch ends, at the level the map solved there (``z0``), and runs for the
foot's OFFSET at the design grade, ``|z0 - DEM| / ramp_grade`` (the ramp
closes the offset; the terrain's own slope beyond is the terrain's —
``pad_road_exit``'s round 5), or until a standing face stops it (then the
road's own cap steepens it).  The strip is a
ROAD (``service_road``, the road law's caps) and a PAD ROAD (a follower of
the last stage, junior to every pavement it meets); its profile rows are
``constraints/ramp_runout``'s.  A foot whose ground already stands within
``[cockpit] visual_m`` of the DEM where the patch ends asks nothing.

A 10-03e LANDING's foot (counted ``landing`` here) runs out in the PLANAR
stage instead (``planar/landing_runout``, issue #711): the lot it crosses is
cut back from the strip there and the strip is held against the landing's
block datum in stage 2, so the lot meets it rather than the strip meeting a
lot already solved.  (RULINGS 2026-10-14i's "road carries the run-out" was
tried here and withdrawn: the lot ``dsf:pol10`` welded to HECA's landing
level, +5.7 m, and the mapped road ``-3963`` ended 6 m over the raw DEM.)
"""
from __future__ import annotations

import dataclasses as _dc
import math as _math
import typing as _t

import numpy as np
import shapely
from shapely.geometry import LineString, Polygon
from shapely.ops import unary_union

from ..airport.ramp_feet import FOOT_SPAN_M
from ..law import Law
from .rules import Rules

__all__ = ["mint_ramp_runouts", "runout_of", "RUNOUT_PREFIX", "MAX_RUN_M"]

#: the run-out cell's ref: ``runout:<k>``
RUNOUT_PREFIX = "runout"

#: the run's bound (``pad_road_exit.MAX_REACH_M``'s order: a ramp the DEM
#: never meets inside it is not a ramp foot's)
MAX_RUN_M = 400.0

#: the stations of the strip's sides (``mint_ramp_runouts``): a vertex on
#: each side every this many metres along the run
STATION_M = 10.0

_KEYS = ("runout_x0", "runout_y0", "runout_dx", "runout_dy", "runout_z0",
         "runout_dem0")


def runout_of(cell) -> "tuple | None":
    """``(x0, y0, dx, dy, z0, dem0)`` of a run-out cell, else None."""
    ev = getattr(cell, "evidence", None) or {}
    if not ev.get("ramp_runout"):
        return None
    return tuple(float(ev[k]) for k in _KEYS)


def _stations(s0: float, s1: float, step: float) -> list[float]:
    """``s0``, every ``step`` after it and ``s1`` (``step`` 0: the ends)."""
    n = int(_math.ceil((s1 - s0) / step - 1.0e-9)) if step > 0.0 and s1 > s0 else 1
    return [s0 + (s1 - s0) * k / max(1, n) for k in range(max(1, n) + 1)]


def _level_at(seg: LineString, xy: np.ndarray, z: np.ndarray,
              reach: float) -> "float | None":
    """The median solved level of the base map's vertices within ``reach``
    of ``seg`` (the line where the strip leaves the patch)."""
    d = shapely.distance(seg, shapely.points(xy))
    near = d <= reach
    if not near.any():
        k = int(np.argmin(d))
        return float(z[k]) if d[k] <= 3.0 * reach else None
    return float(np.median(z[near]))


def _landing_faces(pm):
    """The 10-03e landings and their collars on the solved map: planar pad
    regions (``planar/landing``), never classification cells."""
    from ..model.platform import LANDING_SEP
    faces = getattr(pm, "faces", None) or {}
    return unary_union([
        q for f in faces.values() if LANDING_SEP in str(f.ref)
        for q in [Polygon([pm.vertices[v].xy for v in pm.ring_vertices(f.ring)])]
        if q.is_valid and not q.is_empty])


def mint_ramp_runouts(cl, airport, law: Law, rules: Rules, pm_base, z_base
                      ) -> tuple[_t.Any, dict]:
    """``cl`` with a run-out strip minted off every object ramp's graded
    foot (module docstring); ``(cl, report)``."""
    from ..airport.ramp_feet import ramp_feet
    from ..law.tables import role_side
    from .evidence import polygon_parts
    from .roles import Cell
    rep: dict[str, _t.Any] = {"feet": 0, "ungraded": 0, "landing": 0, "at_grade": 0, "blocked": 0,
                              "runouts": 0, "run_m": 0.0, "list": []}
    dem = getattr(airport, "dem", None)
    frame = getattr(airport, "frame", None)
    if dem is None or frame is None or pm_base is None or z_base is None:
        return cl, rep
    feet = ramp_feet(airport, law, frame.entry())
    rep["feet"] = len(feet)
    if not feet:
        return cl, rep
    g = float(law.tables.emit.road_contact.ramp_grade)
    band = float(law.tables.emit.cockpit.visual_m)
    snap = float(rules.cells.snap_grid_m)
    touch = float(law.tables.structures.placement.sunken_ramp_grid_m) or 2.0
    ids = sorted(pm_base.vertices)
    xy = np.array([pm_base.vertices[v].xy for v in ids], dtype=float)
    zz = np.array([float(z_base[v]) for v in ids], dtype=float)
    landings = _landing_faces(pm_base)
    occupied = unary_union([Polygon(c.ring, c.holes) for c in cl.cells] + [landings])
    cells = list(cl.cells)
    to_ll = frame.transformers()[1]
    for f in feet:
        (lx, ly), (dx, dy), w = f.lip, f.direction, f.width_m
        nx, ny = -dy, dx

        def rect(s0: float, s1: float, step: float = 0.0) -> Polygon:
            h = 0.5 * w
            ss = _stations(s0, s1, step)
            return Polygon([(lx + dx * s + nx * t, ly + dy * s + ny * t)
                            for s, t in [*((s, -h) for s in ss),
                                         *((s, h) for s in reversed(ss))]])
        # the patch holds the ground under the ramp's last metres: else
        # nothing graded the ground to the foot and nothing runs out
        back = rect(-FOOT_SPAN_M, 0.0)
        if back.intersection(occupied).area < 0.5 * back.area:
            rep["ungraded"] += 1
            continue
        if back.intersects(landings):
            rep["landing"] += 1           # 10-03e: not yet (module NOT YET)
            continue
        free = [q for q in polygon_parts(rect(0.0, MAX_RUN_M).difference(occupied))
                if q.distance(occupied) <= touch]
        if not free:
            rep["blocked"] += 1
            continue

        def s_of(q):
            c = np.asarray(q.exterior.coords)
            return float(((c[:, 0] - lx) * dx + (c[:, 1] - ly) * dy).min())
        first = min(free, key=s_of)
        s0 = max(0.0, s_of(first))
        x0, y0 = lx + dx * s0, ly + dy * s0
        h = 0.5 * w
        seg = LineString([(x0 - nx * h, y0 - ny * h), (x0 + nx * h, y0 + ny * h)])
        z0 = _level_at(seg, xy, zz, touch)
        if z0 is None:
            rep["ungraded"] += 1
            continue
        dem0 = float(dem.z(x0, y0))
        if abs(z0 - dem0) <= band:
            rep["at_grade"] += 1
            continue
        # THE RUN IS THE FOOT'S OFFSET (``pad_road_exit``'s round 5): the
        # ramp closes the ground's offset at the foot, the terrain's own
        # slope beyond is the terrain's
        run = min(MAX_RUN_M, abs(z0 - dem0) / g)
        # both SIDES carry a vertex every ``STATION_M`` at the same stations:
        # the profile and its cross-fall are only what the ring's vertices
        # can hold (MEASURED, KCLT #1093: a 61 m strip with one mid vertex on
        # one side only, 13.4 % across the chord to the other side)
        strip = rect(s0 - snap, s0 + run, STATION_M).difference(occupied)
        strip = shapely.set_precision(strip, snap)
        parts = [q for q in polygon_parts(strip)
                 if q.area >= touch * touch and q.distance(seg) <= touch]
        if not parts:
            rep["blocked"] += 1
            continue
        lat, lon = to_ll(x0, y0)
        for q in parts:
            k = rep["runouts"]
            ev = {"pad_road": 1.0, "ramp_runout": 1.0, "runout_x0": x0, "runout_y0": y0,
                  "runout_dx": dx, "runout_dy": dy, "runout_z0": z0, "runout_dem0": dem0,
                  "runout_run_m": run, "runout_width_m": w}
            cells.append(Cell(len(cells), "service_road", f"{RUNOUT_PREFIX}:{k}",
                              tuple(q.exterior.coords)[:-1],
                              tuple(tuple(r.coords)[:-1] for r in q.interiors),
                              None, None, role_side(law, "service_road"),
                              "service_road", ev))
            occupied = unary_union([occupied, q])
            rep["runouts"] += 1
        rep["run_m"] = round(rep["run_m"] + run, 1)
        rep["list"].append(f"{f.member} foot {lat:.7f},{lon:.7f} z0 {z0:.2f} dem "
                           f"{dem0:.2f} run {run:.0f} m x {w:.0f} m")
    if not rep["runouts"]:
        return cl, rep
    return _dc.replace(cl, cells=tuple(cells)), rep
