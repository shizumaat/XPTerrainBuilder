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
from the block's predicted datum + the level's ``y`` + one plane band
(``PLANE_BAND_M``, 23c: the datum's miss; the block's contact reach is the
datum pin's, not a rigid level's lip -- MEASURED LFLL: ``building8``'s
10.97 m reach ran both strips to the 400 m cap).

The record is a LANDING RUN-OUT (``Registries.landing_runouts``, #711): the
strip becomes a base region in ``planar/landing.landing_cut`` and its rows
are ``constraints/ramp_runout.landing_runout_rows`` -- never above the
level, never below the design ramp off it, onto its ground by its end --
read against the block's SOLVED datum.  One mechanism, one row family: a
viaduct's landing runs out at road grade, a cut's level at rail grade.

The strip keeps two risers off every pad but its level and off the airside
(the census pairs pavement within one riser, ``PAVCAP_WELD_M``).  An end whose
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
                law, taken, grid: float, counts: dict, rail: bool = False,
                roads: bool = False) -> dict[str, dict[str, _t.Any]]:
    """``{run-out ref: record}`` for the ENDS of every covered-cut level
    (module docstring).  ``levels``: ``{level ref: (polygon, block ref,
    y)}``; ``taken``: every pad and the airside, which no strip takes.
    ``rail``: a station level stands among them (RULINGS 2026-11-03b (6),
    #1739), so the open RAILWAY ways leaving it are ends too
    (``covered_cut.station_corridors``).  ``roads``: the levels are LOWER
    REGIONS (``planar/level_regions``, two-level round 4 step 8): the
    at-grade mapped ROADS leaving them are the ends, each run along its
    carriageway at the road ramp law (``[tunnel] ramp_grade``, never above
    ``ramp_max_grade``), and an end whose ground ahead stands ABOVE the
    level CLIMBS to it (the record's ``sign`` -1; ``constraints/
    ramp_runout.landing_runout_rows`` mirrors its rows) -- the run is never
    clipped at the aerodrome boundary."""
    from ..airport.airside_group_seat import PLANE_BAND_M
    from ..classify.pad_cut_corridor import cutting_corridors
    from ..geom.ramp_profile import runout_profile
    frame, dem = getattr(airport, "frame", None), getattr(airport, "dem", None)
    if frame is None or dem is None or not levels:
        return {}
    tn = law.tables.structures.tunnel
    if roads:
        return _road_runouts(levels, held, airport, law, taken, grid, counts)
    corr = cutting_corridors(airport, law, widen=0.5)
    if rail:
        from .covered_cut import station_corridors
        st = station_corridors(airport, law, open_only=True)
        corr = st if corr is None else (corr if st is None else unary_union([corr, st]))
    if corr is None:
        return {}
    from ..airport.road_ways import mapped_width_m
    from ..classify.pad_cut_corridor import _is_cutting
    admitted = tuple(tn.admitted_values)
    ways, width = [], 0.0
    for w in getattr(airport, "osm_ways", ()) or ():
        tags = getattr(w, "tags", None) or {}
        if len(w.points) >= 2 and (_is_cutting(tags, admitted) or (
                rail and "railway" in tags and tags.get("tunnel", "no") in ("", "no"))):
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
            z0 = float(datum) + float(y) + float(PLANE_BAND_M)

            def ground(s: float, _x=lx, _y=ly, _dx=dx, _dy=dy) -> float:
                return float(dem.z(_x + _dx * s, _y + _dy * s))
            if ground(0.0) >= z0 - band:
                stat["climbs" if ground(0.0) > z0 + band else "at_grade"] += 1
                continue
            prof = runout_profile(z0, ground, g, cap, MAX_RUN_M)
            rec = _end(L, (lx, ly), (dx, dy), pts, prof, ground, width, corr, taken, step,
                       riser, grid, frame)
            if rec is None:
                stat["taken"] += 1
                continue
            rref = _next_ref(out, ref)
            out[rref] = {**rec, "landing": ref, "block": bref, "y": float(y),
                         "z0_pred": round(z0 - float(PLANE_BAND_M), 3),
                         "reach_m": float(PLANE_BAND_M), "g": g, "cap": cap, "kind": "cut_end"}
            taken = unary_union([taken, *rec["polys"]])
    counts["cut_runouts"] = len(out)
    counts["cut_runout_ends"] = stat
    if out:
        counts["cut_runout_list"] = "; ".join(
            f"{r} lip {v['at'][0]},{v['at'][1]} dem {v['dem0']:.2f} run {v['run_m']:.0f} m "
            f"x {v['width_m']:.0f} m" for r, v in sorted(out.items()))
    return out


def _road_runouts(levels, held, airport, law, taken, grid: float, counts: dict
                  ) -> dict[str, dict[str, _t.Any]]:
    """:func:`cut_runouts` for a lower region's ROADS (``roads``): the same
    ends, lips and strips, along the at-grade carriageways
    (``road_yield.road_carriageways``) at the road ramp law, descending or
    CLIMBING to the ground ahead."""
    from ..airport.airside_group_seat import PLANE_BAND_M
    from ..geom.ramp_profile import runout_profile
    from .road_yield import road_carriageways
    frame, dem = getattr(airport, "frame", None), getattr(airport, "dem", None)
    if frame is None or dem is None or not levels:
        return {}
    tn = law.tables.structures.tunnel
    cw = list(road_carriageways(getattr(airport, "osm_ways", ()) or (), law))
    if not cw:
        return {}
    # a road is mapped in many short ways: the run is read along its ROUTE,
    # never per way (``viaduct_road._route``, R6) -- MEASURED LFPG T2: the
    # corridor's west roads, 37-177 m ways, each "ended before it cleared"
    ways = _routes(airport, law, [L for L, _b, _y in levels.values()], grid)
    corr = unary_union([line.buffer(h, cap_style="flat") for line, h in cw])
    width = max(2.0 * h for _l, h in cw)
    g, cap = float(tn.ramp_grade), float(tn.ramp_max_grade)
    step = float(law.tables.emit.chords.station_spacing_m)
    riser = max(float(law.tables.emit.identity.min_distinct_spacing_m), 2.0 * float(grid))
    stat = {"ends": 0, "no_datum": 0, "climbs": 0, "falls": 0, "taken": 0}
    out: dict[str, dict[str, _t.Any]] = {}
    for ref, (L, bref, y) in sorted(levels.items()):
        datum = (held.get(bref) or {}).get("datum_pred")
        near_ways = [w for w in ways if w.distance(L) <= max(grid, 0.5)]
        # ONE END PER ROAD: crossings are grouped along their own route only
        # -- grouped across routes (a cut's tracks, :data:`END_M`) the strip
        # spanned up to 111 m of parallel roads and tilted every one across
        # (MEASURED KATL replay: road_cross_section 53 -> 208)
        ends = [e for wy in near_ways for e in _ends(_exits(L, taken, [wy]))]
        for (lx, ly), (dx, dy), pts in ends:
            stat["ends"] += 1
            if datum is None:
                stat["no_datum"] += 1
                continue
            z0 = float(datum) + float(y)

            def ground(s: float, _x=lx, _y=ly, _dx=dx, _dy=dy) -> float:
                return float(dem.z(_x + _dx * s, _y + _dy * s))
            g0 = ground(0.0)
            sign = 1.0 if g0 < z0 else -1.0
            stat["falls" if sign > 0 else "climbs"] += 1
            # the run is laid out off the level the solve may hold FURTHEST
            # from the ground (the datum's miss, one plane band, 23c): the
            # predicted datum is no solved one (MEASURED KIAH: 28.77
            # predicted, 28.08 solved -- the lip read "at grade")
            prof = runout_profile(z0 + sign * float(PLANE_BAND_M), ground, g, cap, MAX_RUN_M)
            rec = _end(L, (lx, ly), (dx, dy), pts, prof, ground, 0.5 * width, corr, taken,
                       step, riser, grid, frame)
            if rec is None:
                stat["taken"] += 1
                continue
            rref = _next_ref(out, ref)
            out[rref] = {**rec, "landing": ref, "block": bref, "y": float(y), "sign": sign,
                         "from_level": True,
                         "z0_pred": round(z0, 3), "reach_m": float(PLANE_BAND_M), "g": g,
                         "cap": cap, "kind": "level_end"}
            taken = unary_union([taken, *rec["polys"]])
    # the callers' counts add up (``level_regions.seed_levels`` per seed)
    counts["level_runouts"] = counts.get("level_runouts", 0) + len(out)
    prev = counts.get("level_runout_ends") or {}
    counts["level_runout_ends"] = {k: prev.get(k, 0) + v for k, v in stat.items()}
    lines = [f"{r} lip {v['at'][0]},{v['at'][1]} {'climbs' if v['sign'] < 0 else 'falls'} "
             f"dem {v['dem0']:.2f} from {v['z0_pred']:.2f} run {v['run_m']:.0f} m "
             f"x {v['width_m']:.0f} m" for r, v in sorted(out.items())]
    if lines:
        counts["level_runout_list"] = "; ".join(
            [counts["level_runout_list"], *lines] if counts.get("level_runout_list") else lines)
    return out


def _next_ref(out: dict, ref: str) -> str:
    """The next free run-out ref of the level ``ref``."""
    from .landing_runout import runout_ref
    k = sum(1 for r in out if r.startswith(runout_ref(ref)))
    return runout_ref(ref) if not k else f"{runout_ref(ref)}#{k}"


def _end(L, lip, d, pts, prof, ground, side: float, corr, taken, step: float,
         riser: float, grid: float, frame) -> "dict | None":
    """One END's run-out strip and its geometry fields, or ``None`` where
    the pads or the airside take it: off the ``lip`` along ``d`` as far as
    the profile ``prof`` runs, ``side`` beyond the outermost crossing
    ``pts`` either way, inside the corridors ``corr``, two risers off every
    pad but the level ``L`` (the strip never shares a vertex with, nor pairs
    against, a pad at another level)."""
    (lx, ly), (dx, dy) = lip, d
    run = prof[-1][0]
    nx, ny = -dy, dx
    ts = [(p.x - lx) * nx + (p.y - ly) * ny for p in pts]
    lo, hi = min(ts) - side, max(ts) + side
    ss = [min(run, k * step) for k in range(int(math.ceil(run / step)) + 1)]
    R = Polygon([(lx + dx * s + nx * lo, ly + dy * s + ny * lo) for s in ss]
                + [(lx + dx * s + nx * hi, ly + dy * s + ny * hi) for s in reversed(ss)])
    S = valid_area(valid_area(R.intersection(corr)).difference(L).difference(
        valid_area(taken.difference(L)).buffer(2.0 * riser, join_style=2)))
    got = [q for q in _parts(S) if q.area >= max(grid * grid, 1.0)
           and q.distance(L) <= max(grid, 0.5)]
    if not got:
        return None
    lat, lon = frame.transformers()[1](lx, ly)
    g0 = ground(0.0)
    return {"lip": (float(lx), float(ly)), "dir": (float(dx), float(dy)),
            "width_m": float(hi - lo), "dem0": round(g0, 4),
            "ground": [(float(s_), round(ground(s_) - g0, 4)) for s_, _z in prof[::2] + prof[-1:]],
            "run_m": round(run, 1), "polys": got,
            "axis": LineString([(lx, ly), (lx + dx * run, ly + dy * run)]),
            "at": (round(lat, 7), round(lon, 7))}


def _routes(airport, law, levels, grid: float) -> list:
    """The ROUTES (``viaduct_road._route``: through the junctions, the least
    turn) of every at-grade mapped road way crossing a level's edge."""
    from .structure_approach import is_bridge, is_tunnel
    from .viaduct_road import _graph, _layer, _route
    tn = law.tables.structures.tunnel
    roads = [w for w in getattr(airport, "osm_ways", ()) or ()
             if len(w.points) >= 2 and (w.tags or {}).get("highway") and not is_bridge(w)
             and not is_tunnel(w, tn.admitted_values) and _layer(w.tags or {}) <= 0]
    edge = unary_union([L.boundary for L in levels]).buffer(max(grid, 0.5))
    nb = _graph(roads)
    out, seen = [], set()
    for w in roads:
        line = LineString(w.points)
        if not line.intersects(edge):
            continue
        r = _route(w, nb, law)
        key = tuple(round(c, 1) for xy in (r.coords[0], r.coords[-1]) for c in xy)
        if key not in seen and key[2:] + key[:2] not in seen:
            seen.add(key)
            out.append(r)
    return out
