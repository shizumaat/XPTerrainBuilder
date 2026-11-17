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

from shapely.geometry import LineString, Point, Polygon
from shapely.ops import unary_union

from ..geom.parts import nonempty_polygon_parts as _parts
from ..geom.valid_area import valid_area

__all__ = ["cut_runouts", "level_exit_climbs"]

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
    return [(p, d) for p, d, back, _s, _sg in _crossings(L, pads, ways) if back is None]


def _crossings(L, pads, ways) -> _t.Iterator:
    """``(point, (dx, dy), back, s, sgn)`` for every crossing of a way's
    line out of the level ``L`` that runs on outside ``pads`` for
    :data:`CLEAR_M`; ``back`` is ``None`` where it leaves for good, else the
    distance along the line to where it comes back into the level (a
    NOTCH); ``s`` the crossing's station on the line, ``sgn`` the way out
    along it (+1 forward)."""
    from shapely.ops import substring
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
                        else LineString(list(substring(line, 0.0, s - 1.0).coords)[::-1]))
                back = None
                if rest.length > 0.0 and rest.intersects(L):
                    back = 1.0 + min(rest.project(c) for c in _parts_points(rest.intersection(L)))
                d = math.hypot(q.x - p.x, q.y - p.y)
                yield p, ((q.x - p.x) / d, (q.y - p.y) / d), back, s, sgn


def _parts_points(g) -> list:
    """Every vertex of every part of ``g`` (a line's overlap with a level;
    the nearest along the line is where it comes back in)."""
    return [Point(c) for q in (getattr(g, "geoms", None) or [g]) if not q.is_empty
            for c in (q.exterior.coords if q.geom_type == "Polygon" else q.coords)]


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
                roads: bool = False, named: _t.Sequence = ()) -> dict[str, dict[str, _t.Any]]:
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
    clipped at the aerodrome boundary; ``named`` names what takes an end
    (:func:`_road_runouts`)."""
    from ..airport.airside_group_seat import PLANE_BAND_M
    from ..classify.pad_cut_corridor import cutting_corridors
    from ..geom.ramp_profile import runout_profile
    frame, dem = getattr(airport, "frame", None), getattr(airport, "dem", None)
    if frame is None or dem is None or not levels:
        return {}
    tn = law.tables.structures.tunnel
    if roads:
        return _road_runouts(levels, held, airport, law, taken, grid, counts, named)
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


def _road_runouts(levels, held, airport, law, taken, grid: float, counts: dict,
                  named: _t.Sequence = ()) -> dict[str, dict[str, _t.Any]]:
    """:func:`cut_runouts` for a lower region's ROADS (``roads``): the same
    lips, along the at-grade carriageways (``road_yield.road_carriageways``)
    at the road ramp law, descending or CLIMBING to the ground ahead.  An
    end is ONE route's crossing of the level's rim (never grouped across
    :data:`END_M`), its strip that route's own carriageway (its half-width
    either side, clipped to that carriageway alone): grouped, or clipped to
    every carriageway, a strip spanned up to 111 m of parallel roads and
    tilted every cross street it swallowed along its axis (MEASURED KATL
    replay: road_cross_section 53 -> 208 / 225).  ``named``: ``[(ref,
    polygon)]`` of ``taken``, to name the pad or airside that takes an end
    (``level_runout_ends["taken_by"]``)."""
    from ..airport.airside_group_seat import PLANE_BAND_M
    from ..geom.ramp_profile import runout_profile
    frame, dem = getattr(airport, "frame", None), getattr(airport, "dem", None)
    if frame is None or dem is None or not levels:
        return {}
    tn = law.tables.structures.tunnel
    # a road is mapped in many short ways: the run is read along its ROUTE,
    # never per way (``viaduct_road._route``, R6) -- MEASURED LFPG T2: the
    # corridor's west roads, 37-177 m ways, each "ended before it cleared"
    ways = _routes(airport, law, [L for L, _b, _y in levels.values()], grid)
    if not ways:
        return {}
    from ..law.tables import road_terrain_cap
    g, cap = float(tn.ramp_grade), float(tn.ramp_max_grade)
    tcap = float(road_terrain_cap(law))
    step = float(law.tables.emit.chords.station_spacing_m)
    riser = max(float(law.tables.emit.identity.min_distinct_spacing_m), 2.0 * float(grid))
    stat = {"ends": 0, "no_datum": 0, "climbs": 0, "falls": 0, "taken": 0, "to_junction": 0}
    taken_by: list[str] = []
    out: dict[str, dict[str, _t.Any]] = {}
    pads = taken
    for ref, (L, bref, y) in sorted(levels.items()):
        # a crossing clears off the PADS and the airside alone: a run-out
        # minted for another road is no pad (2120-F6: -10619's strip over
        # the junction it shares with -4173 refused -4173's exit); the strip
        # itself is still clipped off every earlier one (``taken``, :func:`_end`)
        for p, (dx, dy), h, corr, z0, fix in _road_exits(
                L, (held.get(bref) or {}).get("datum_pred"), y, ways, pads, grid, riser):
            stat["ends"] += 1
            if z0 is None:
                stat["no_datum"] += 1
                continue
            lx, ly = p.x, p.y

            def ground(s: float, _x=lx, _y=ly, _dx=dx, _dy=dy) -> float:
                return float(dem.z(_x + _dx * s, _y + _dy * s))
            sign = 1.0 if ground(0.0) < z0 else -1.0
            stat["falls" if sign > 0 else "climbs"] += 1
            # the run is laid out off the level the solve may hold FURTHEST
            # from the ground (the datum's miss, one plane band, 23c): the
            # predicted datum is no solved one (MEASURED KIAH: 28.77
            # predicted, 28.08 solved -- the lip read "at grade")
            # the grade the junction needs is read off the level itself; the
            # plane band only lengthens the run (the rows ride the solved level)
            ge, ce, fix_m = _to_fixed(z0, (lx, ly), (dx, dy), fix, dem, g, cap, tcap)
            stat["to_junction"] += ge > g
            prof = runout_profile(z0 + sign * float(PLANE_BAND_M), ground, ge, ce, MAX_RUN_M)
            rec = _end(L, (lx, ly), (dx, dy), [p], prof, ground, h, corr, taken,
                       step, riser, grid, frame)
            if rec is None:
                stat["taken"] += 1
                taken_by.append(_taker(ref, L, (lx, ly), (dx, dy), prof, h, corr, named,
                                       2.0 * riser, frame))
                continue
            rref = _next_ref(out, ref)
            out[rref] = {**rec, "landing": ref, "block": bref, "y": float(y),
                         "sign": sign, "from_level": True,
                         "z0_pred": round(z0, 3), "reach_m": float(PLANE_BAND_M),
                         "g": ge, "cap": ce, "fix_m": fix_m, "kind": "level_end"}
            taken = unary_union([taken, *rec["polys"]])
    # the callers' counts add up (``level_regions.seed_levels`` per seed)
    counts["level_runouts"] = counts.get("level_runouts", 0) + len(out)
    prev = counts.get("level_runout_ends") or {}
    ends = {k: prev.get(k, 0) + v for k, v in stat.items()}
    ends["taken_by"] = [*prev.get("taken_by", []), *taken_by]
    counts["level_runout_ends"] = ends
    lines = [f"{r} lip {v['at'][0]},{v['at'][1]} {'climbs' if v['sign'] < 0 else 'falls'} "
             f"dem {v['dem0']:.2f} from {v['z0_pred']:.2f} run {v['run_m']:.0f} m "
             f"x {v['width_m']:.0f} m at {100.0 * v['g']:.1f} %"
             + (f" to a junction {v['fix_m']:.0f} m" if v['fix_m'] is not None else "")
             for r, v in sorted(out.items())]
    if lines:
        counts["level_runout_list"] = "; ".join(
            [counts["level_runout_list"], *lines] if counts.get("level_runout_list") else lines)
    return out


def _road_exits(L, datum, y: float, ways, taken, grid: float, riser: float) -> _t.Iterator:
    """``(lip, (dx, dy), half-width, corridor, z0, junction)`` for every
    ROAD EXIT of the level ``L`` (:func:`_road_runouts`' reader): each route
    of ``ways`` (``[(route, half-width, junction stations)]``,
    :func:`_routes`) within a grid of the level, where it leaves through
    the level's rim (:func:`_crossings`, off ``taken``) for good, or out to a JUNCTION
    before it comes back in (2120-F6, owner 2026-11-17T18:47Z: the road
    "may climb at 15 % to its junction" -- a notch whose road meets
    another first is an exit to that fixed point; one with no junction
    before it comes back is no end); one lip per crossing (two routes
    within ``riser``: one end); ``z0`` the level's predicted height there
    (``datum + y``), ``None`` without a ``datum``; ``junction`` the next
    junction's point along the road out, or ``None``."""
    lips: list = []                        # two routes over one crossing: one end
    z0 = None if datum is None else float(datum) + float(y)
    for wy, h, js in [w for w in ways if w[0].distance(L) <= max(grid, 0.5)]:
        corr = wy.buffer(h, cap_style="flat")
        for p, d, back, s, sgn in _crossings(L, taken, [wy]):
            # a junction within half the carriageway of the lip stands on the
            # level's edge (its other road meets the level there): no fixed
            # point ahead (MEASURED LOWW, RJTT: junctions 1.0-1.4 m off the lip
            # steepened 5 % run-outs to 20 %)
            ahead = sorted(sgn * (sj - s) for sj in js if sgn * (sj - s) > h)
            fix = ahead[0] if ahead else None
            if back is not None and (fix is None or fix >= back):
                continue                   # a notch: the road comes back first
            if any(p.distance(q) <= riser for q in lips):
                continue
            lips.append(p)
            yield p, d, h, corr, z0, (None if fix is None else wy.interpolate(s + sgn * fix))


def _to_fixed(z0: float, lip, d, fix, dem, g: float, cap: float, tcap: float
              ) -> tuple[float, float, "float | None"]:
    """``(design grade, cap, distance)`` of a road run-out off a level at
    ``z0`` toward the road's next FIXED POINT ``fix`` (a junction, or
    ``None``): where the design grade ``g`` cannot close the level's offset
    to that point's ground in the distance to it, the run steepens to the
    grade that does -- never steeper than needed, never past the road on
    steep ground's cap ``tcap`` (owner RULINGS 2026-11-17e,
    ``tables.road_terrain_cap``); the cap rises with it."""
    if fix is None:
        return g, cap, None
    D = (fix.x - lip[0]) * d[0] + (fix.y - lip[1]) * d[1]
    if D <= 0.0:
        return g, cap, None
    need = abs(float(dem.z(fix.x, fix.y)) - z0) / D
    if need <= g:
        return g, cap, round(D, 1)
    ge = min(need, tcap)
    return ge, max(cap, ge), round(D, 1)


def level_exit_climbs(L, datum, y: float, airport, law, taken, grid: float) -> "list | None":
    """``[DEM at the lip - level]`` of every road exit of the level ``L``
    (:func:`_road_exits`, the run-outs' own reader), or ``None`` where no
    road leaves it or the block has no ``datum``."""
    dem = getattr(airport, "dem", None)
    if dem is None or datum is None:
        return None
    ways = _routes(airport, law, [L], grid)
    riser = max(float(law.tables.emit.identity.min_distinct_spacing_m), 2.0 * float(grid))
    ex = list(_road_exits(L, datum, y, ways, taken, grid, riser)) if ways else []
    if not ex:
        return None
    return [float(dem.z(p.x, p.y)) - z0 for p, _d, _h, _c, z0, _j in ex]


def _taker(ref: str, L, lip, d, prof, side: float, corr, named, reach: float,
           frame) -> str:
    """``"<lat>,<lon> <refs>"``: what takes the level ``ref``'s end at
    ``lip`` -- every other ``named`` ``(ref, polygon)`` within ``reach`` of
    its strip."""
    (lx, ly), (dx, dy) = lip, d
    run, nx, ny = prof[-1][0], -dy, dx
    R = Polygon([(lx + nx * side, ly + ny * side), (lx - nx * side, ly - ny * side),
                 (lx + dx * run - nx * side, ly + dy * run - ny * side),
                 (lx + dx * run + nx * side, ly + dy * run + ny * side)])
    S = valid_area(valid_area(R.intersection(corr)).difference(L))
    refs = sorted({str(r) for r, q in named
                   if str(r) != ref and q is not None and q.distance(S) <= reach})
    lat, lon = frame.transformers()[1](lx, ly)
    return f"{lat:.6f},{lon:.6f} {'+'.join(refs) or '?'}"


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
    """``[(route, half-width, junctions)]``: the ROUTES
    (``viaduct_road._route``: through the junctions, the least turn) of
    every at-grade mapped road way of a ribbon class
    (``road_yield.road_carriageways``) crossing a level's edge, with that
    crossing way's carriageway half-width (``airport/road_ways.
    ribbon_half_width_m``) and the stations along the route of its
    JUNCTIONS (a mapped node three or more road ways' segments meet at)."""
    from ..airport.road_ways import ribbon_half_width_m
    from ..classify.rules import load_rules
    from .structure_approach import is_bridge, is_tunnel
    from .viaduct_road import _graph, _key, _layer, _route
    orr = load_rules().osm_roads
    if not orr.enabled:
        return []
    ribbon = set(orr.ribbon_highways)
    tn = law.tables.structures.tunnel
    roads = [w for w in getattr(airport, "osm_ways", ()) or ()
             if len(w.points) >= 2 and (w.tags or {}).get("highway") and not is_bridge(w)
             and not is_tunnel(w, tn.admitted_values) and _layer(w.tags or {}) <= 0]
    edge = unary_union([L.boundary for L in levels]).buffer(max(grid, 0.5))
    nb = _graph(roads)
    out, seen = [], set()
    for w in roads:
        line = LineString(w.points)
        if (w.tags or {}).get("highway") not in ribbon or not line.intersects(edge):
            continue
        r = _route(w, nb, law)
        # one route is one PATH: two routes between the same two ends by
        # different ways are two (MEASURED KATL: -4174's 2061 m route was
        # dropped as -8145's 2996 m one, 457 m apart, and kept its 1.44 m step)
        ends = tuple(round(c, 1) for xy in (r.coords[0], r.coords[-1]) for c in xy)
        key = (ends, round(r.length))
        if key not in seen and (ends[2:] + ends[:2], key[1]) not in seen:
            seen.add(key)
            js = [r.project(Point(c)) for c in r.coords if len(nb.get(_key(c), ())) >= 3]
            out.append((r, ribbon_half_width_m(w.tags or {}, law), js))
    return out
