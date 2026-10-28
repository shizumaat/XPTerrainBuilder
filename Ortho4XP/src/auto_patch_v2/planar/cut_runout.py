"""THE CUT'S END RAMPS — beyond each end of a covered cut's lower level the
ground grades to the open cut at the RAIL grade, never steps (#1333; owner
RULINGS 2026-10-28r (3), with 2026-10-28k Q233 a).

Owner, 2026-10-28T05:47:49Z (259): "A, and then grade terrain to meet either
end of the object rails smoothly".  The level of ``planar/covered_cut``
stands where the objects put it (28r (3)); the open cut beyond it is the
lidar's.  MEASURED LFLL (capture replay at b8c456c9): ``building8/p1`` at
230.38 m against the base mesh's 228.9 m just north of the station and
229.5 m south of it -- a 0.9-1.4 m step at both ends.

THE END: where a mapped cutting way crosses the level's ring for good (it
never comes back into the level) and runs on outside every pad for at least
:data:`CLEAR_M`.  The crossings within
:data:`END_M` of each other are ONE end (the tracks of one cut), its LIP
their centre, its direction their mean outward tangent.  Off the lip a
strip as wide as those tracks' corridors (``classify/pad_cut_corridor.
cutting_corridors``, half a carriageway either side) runs along the
direction as far as the shared ramp law needs to meet the raw ground
(``geom/ramp_profile.runout_profile``: designed at ``[tunnel]
rail_ramp_grade`` off the level, never steeper than ``rail_ramp_max_grade``)
from the highest level the solve may hold it at (the block's predicted
datum + its widest reach band + the level's ``y``).

The record is a LANDING RUN-OUT (``Registries.landing_runouts``, #711): the
strip becomes a base region in ``planar/landing.landing_cut`` and its rows
are ``constraints/ramp_runout.landing_runout_rows`` -- never above the
level, never below the design ramp off it, onto its ground by its end --
read against the block's SOLVED datum.  One mechanism, one row family: a
viaduct's landing runs out at road grade, a cut's level at rail grade.

The strip keeps a riser's width off every pad but its level.  An end whose
ground ahead stands within ``[cockpit] visual_m`` of the
level, or ABOVE it (the level would climb to it, which a run-out never
does), or whose strip a pad or the airside takes asks nothing; each is
counted.
"""
from __future__ import annotations

import math
import typing as _t

from shapely.geometry import LineString, Polygon
from shapely.ops import unary_union

from ..geom.parts import nonempty_polygon_parts as _parts
from ..geom.valid_area import valid_area

__all__ = ["cut_runouts"]

#: a crossing is an END only where its way runs on outside every pad this far
CLEAR_M = 20.0
#: crossings this close are one end (the tracks of one cut)
END_M = 60.0
#: the run's bound (``planar/landing_runout.MAX_RUN_M``)
MAX_RUN_M = 400.0


def _exits(L, pads, ways) -> list:
    """``[(point, (dx, dy))]``: where a cutting way's line leaves the level
    ``L`` for good -- it never comes back into the level (a notch the level
    keeps off a ramp or a pad is no end) -- and runs on outside ``pads`` for
    :data:`CLEAR_M`."""
    from shapely.ops import substring
    out = []
    ring = L.boundary
    for line in ways:
        hit = line.intersection(ring)
        pts = [hit] if hit.geom_type == "Point" else [
            g for g in getattr(hit, "geoms", ()) if g.geom_type == "Point"]
        for p in pts:
            s = line.project(p)
            for sgn in (1.0, -1.0):
                q = line.interpolate(s + sgn * CLEAR_M)
                if q.distance(p) < 0.5 * CLEAR_M:
                    continue                       # the way ends before it clears
                seg = LineString([line.interpolate(s + sgn * 1.0), q])
                if seg.intersects(pads):
                    continue
                rest = (substring(line, s + 1.0, line.length) if sgn > 0
                        else substring(line, 0.0, s - 1.0))
                if rest.length > 0.0 and rest.intersects(L):
                    continue
                d = math.hypot(q.x - p.x, q.y - p.y)
                out.append((p, ((q.x - p.x) / d, (q.y - p.y) / d)))
    return out


def _ends(exits) -> list:
    """The exits grouped into ENDS (:data:`END_M`): ``[(lip, dir, points)]``."""
    groups: list[list] = []
    for p, d in exits:
        for g in groups:
            if any(p.distance(q) <= END_M and d[0] * e[0] + d[1] * e[1] > 0.0
                   for q, e in g):
                g.append((p, d))
                break
        else:
            groups.append([(p, d)])
    out = []
    for g in groups:
        x = sum(p.x for p, _d in g) / len(g)
        y = sum(p.y for p, _d in g) / len(g)
        dx = sum(d[0] for _p, d in g)
        dy = sum(d[1] for _p, d in g)
        n = math.hypot(dx, dy) or 1.0
        out.append(((x, y), (dx / n, dy / n), [p for p, _d in g]))
    return out


def cut_runouts(levels: _t.Mapping[str, tuple], held: _t.Mapping[str, dict], airport,
                law, taken, grid: float, counts: dict) -> dict[str, dict[str, _t.Any]]:
    """``{run-out ref: record}`` for the ENDS of every covered-cut level
    (module docstring).  ``levels``: ``{level ref: (polygon, block ref,
    y)}``; ``taken``: every pad and the airside, which no strip takes."""
    from ..classify.pad_cut_corridor import cutting_corridors
    from ..geom.ramp_profile import runout_profile
    from ..model.platform import widest_reach
    from .landing_runout import runout_ref
    frame, dem = getattr(airport, "frame", None), getattr(airport, "dem", None)
    if frame is None or dem is None or not levels:
        return {}
    tn = law.tables.structures.tunnel
    corr = cutting_corridors(airport, law, widen=0.5)
    if corr is None:
        return {}
    from ..airport.road_ways import mapped_width_m
    from ..classify.pad_cut_corridor import _is_cutting
    admitted = tuple(tn.admitted_values)
    ways, width = [], 0.0
    for w in getattr(airport, "osm_ways", ()) or ():
        tags = getattr(w, "tags", None) or {}
        if len(w.points) >= 2 and _is_cutting(tags, admitted):
            ways.append(LineString(w.points))
            width = max(width, mapped_width_m(tags, tn.lane_width_m, tn.default_lanes))
    g, cap = float(tn.rail_ramp_grade), float(tn.rail_ramp_max_grade)
    band = float(law.tables.emit.cockpit.visual_m)
    step = float(law.tables.emit.chords.station_spacing_m)
    riser = max(float(law.tables.emit.identity.min_distinct_spacing_m), 2.0 * float(grid))
    stat = {"ends": 0, "no_datum": 0, "at_grade": 0, "climbs": 0, "taken": 0}
    out: dict[str, dict[str, _t.Any]] = {}
    for ref, (L, bref, y) in sorted(levels.items()):
        hb = held.get(bref) or {}
        datum = hb.get("datum_pred")
        for (lx, ly), (dx, dy), pts in _ends(_exits(L, taken, ways)):
            stat["ends"] += 1
            if datum is None:
                stat["no_datum"] += 1
                continue
            z0 = float(datum) + float(y) + widest_reach(hb)

            def ground(s: float, _x=lx, _y=ly, _dx=dx, _dy=dy) -> float:
                return float(dem.z(_x + _dx * s, _y + _dy * s))
            if ground(0.0) >= z0 - band:
                stat["climbs" if ground(0.0) > z0 + band else "at_grade"] += 1
                continue
            prof = runout_profile(z0, ground, g, cap, MAX_RUN_M)
            run = prof[-1][0]
            nx, ny = -dy, dx
            ts = [(p.x - lx) * nx + (p.y - ly) * ny for p in pts]
            lo, hi = min(ts) - width, max(ts) + width
            ss = [min(run, k * step) for k in range(int(math.ceil(run / step)) + 1)]
            R = Polygon([(lx + dx * s + nx * lo, ly + dy * s + ny * lo) for s in ss]
                        + [(lx + dx * s + nx * hi, ly + dy * s + ny * hi) for s in reversed(ss)])
            # a riser's width off every pad but the level: the strip never
            # shares a vertex with a pad standing at another level
            S = valid_area(valid_area(R.intersection(corr)).difference(L)
                           .difference(valid_area(taken.difference(L)).buffer(riser, join_style=2)))
            got = [q for q in _parts(S) if q.area >= max(grid * grid, 1.0)
                   and q.distance(L) <= max(grid, 0.5)]
            if not got:
                stat["taken"] += 1
                continue
            k = sum(1 for r in out if r.startswith(runout_ref(ref)))
            rref = runout_ref(ref) if not k else f"{runout_ref(ref)}#{k}"
            lat, lon = frame.transformers()[1](lx, ly)
            out[rref] = {"landing": ref, "block": bref, "y": float(y),
                         "lip": (float(lx), float(ly)), "dir": (float(dx), float(dy)),
                         "width_m": float(hi - lo), "z0_pred": round(z0 - widest_reach(hb), 3),
                         "reach_m": round(widest_reach(hb), 3), "g": g, "cap": cap,
                         "dem0": round(ground(0.0), 4),
                         "ground": [(float(s_), round(ground(s_) - ground(0.0), 4))
                                    for s_, _z in prof[::2] + prof[-1:]],
                         "run_m": round(run, 1), "polys": got,
                         "axis": LineString([(lx, ly), (lx + dx * run, ly + dy * run)]),
                         "at": (round(lat, 7), round(lon, 7)), "kind": "cut_end"}
            taken = unary_union([taken, *got])
    counts["cut_runouts"] = len(out)
    counts["cut_runout_ends"] = stat
    if out:
        counts["cut_runout_list"] = "; ".join(
            f"{r} lip {v['at'][0]},{v['at'][1]} dem {v['dem0']:.2f} run {v['run_m']:.0f} m "
            f"x {v['width_m']:.0f} m" for r, v in sorted(out.items()))
    return out
