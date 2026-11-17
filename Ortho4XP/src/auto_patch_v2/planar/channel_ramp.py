"""A ROAD LEAVING A CHANNEL THROUGH ITS WALL CLIMBS ON A RAMP PART OF THE
FLOOR (#2127 round 3, spec ``sim-review/2127-R3.md`` §3 Part A).

THE EXIT (A1): a mapped at-grade road route of a ribbon class
(``planar/cut_runout.road_routes``, the crest ring as the level) whose
crossing way runs on the channel's floor for at least ``[channel]
corridor_min_length_m`` and that leaves the corridor for good
(``cut_runout.exits``, read within the run-out reach) through a LATERAL wall —
an end line is ``planar/channel_depth.rejoin``'s.  Exits within
``cut_runout.END_M`` of each other are ONE end (``cut_runout.exit_ends``):
parallel carriageways climb one ramp.

THE PROFILE (A2), the pack first (owner 16s): where one visible member's
feet flank the route within its carriageway half-width plus ``[tunnel]
lane_width_m`` and that run ends in LEDGE feet, the ramp's long section IS
that foot line — from the last foot standing within ``[cockpit] visual_m``
of the shell's floor level through every later foot — and beyond its last
foot it runs on at that last interval's grade (never under ``ramp_grade``
nor over ``ramp_max_grade``) to its ground (``geom/ramp_profile.
runout_profile``).  Those feet are RAMP feet (``channel_depth.RAMP``): no
floor foot.  Without such feet the ramp is the road ramp law from the floor
edge outward.

THE CELL (A3): the ramp's plan is the exit routes' carriageways from its
first station to its top, widened to the foot line where feet state it;
``ChannelRamp.outline`` (the ramp ⊕ the channel's wall band, flat at the
top line) is what the main floor stands back from and the corridor's knife
covers (``channel_claims.channel_cells``).  Its floor is read by
``geom/channel_declared``.  Nothing here names an airport or a pack.
"""
from __future__ import annotations

import math
import typing as _t

import numpy as np
from shapely.geometry import LineString, Point, Polygon
from shapely.ops import substring, unary_union

from ..airport.dem import dem_z_at
from ..geom.ramp_profile import runout_profile
from ..model.structures import ChannelRamp, profile_z
from .channel_depth import LEDGE
from .channel_geometry import _poly
from .cut_runout import MAX_RUN_M, exit_ends, exits, road_routes

__all__ = ["exit_ramps", "crest_with_ramps"]

#: the ramp's long section is stated every this many metres
STEP_M = 2.0


class _Exit(_t.NamedTuple):
    point: Point
    out: tuple[float, float]   # the outward direction at the crossing
    route: LineString          # oriented outward: ``t`` grows away from the floor
    half: float
    way: object
    in_floor: float


def exit_ramps(airport, law, cid: str, axis_ln: LineString, ends: tuple[float, float],
               profile, region, crest_ring, band: float, vis=None
               ) -> tuple[tuple[ChannelRamp, ...], frozenset, list[str]]:
    """``(ramps, the (station, row) feet of their pack runs, notes)`` of one
    channel (module doc); ``vis`` its ``channel_depth.VisibleFloor`` or
    ``None``."""
    floor, crest = _poly(region), _poly(crest_ring)
    if floor is None or crest is None or getattr(airport, "dem", None) is None:
        return (), frozenset(), []
    notes: list[str] = []
    found = _exits(airport, law, cid, axis_ln, ends, floor, crest, band, notes)
    ramps: list[ChannelRamp] = []
    rows: set[tuple[int, int]] = set()
    by_pt = {id(e.point): e for e in found}
    for _lip, _d, pts in exit_ends([(e.point, e.out) for e in found]):
        group = sorted((by_pt[id(p)] for p in pts), key=lambda e: -e.in_floor)
        got = _ramp(airport, law, cid, len(ramps), group, profile, axis_ln, floor, band,
                    vis, notes)
        if got is not None:
            ramps.append(got[0])
            rows |= got[1]
    return tuple(ramps), frozenset(rows), notes


def crest_with_ramps(crest_ring, ramps) -> tuple:
    """The crest ring taking in every ramp's outline (A3: the knife, the
    keep-out and every reader of the corridor cover the ramp's run past the
    crest), or ``crest_ring`` unchanged without ramps."""
    if not ramps:
        return crest_ring
    got = unary_union([g for g in (_poly(crest_ring), *(_poly(r.outline) for r in ramps))
                       if g is not None])
    if got.geom_type != "Polygon":
        got = max(got.geoms, key=lambda g: g.area)
    return tuple(got.exterior.coords)[:-1]


def _exits(airport, law, cid, axis_ln, ends, floor, crest, band, notes) -> list[_Exit]:
    """Every lateral exit of the corridor (A1), one per crossing way."""
    ch = law.tables.structures.channel
    grid = float(law.tables.emit.identity.min_distinct_spacing_m)
    out: list[_Exit] = []
    for route, half, ways in road_routes(airport, law, [crest], grid, with_ways=True):
        for p, d in exits(crest, Polygon(), [route], reach=MAX_RUN_M):
            w = min(ways, key=lambda w: LineString(w.points).distance(p))
            if LineString(w.points).distance(p) > half:
                continue
            s = axis_ln.project(p)
            if not ends[0] + band < s < ends[1] - band:
                continue                         # through an end line: rejoin's
            inf = LineString(w.points).intersection(floor).length
            if inf < ch.corridor_min_length_m:
                if inf > 0.0:
                        notes.append(f"{cid}: way {w.id} leaves through the wall at "
                                 f"{_ll(airport, p)} with {inf:.0f} m on the floor (< [channel] "
                                 f"corridor_min_length_m {ch.corridor_min_length_m:.0f}) — "
                                 f"no exit ramp (#2127 R3 A1)")
                continue
            t = route.project(p)
            ahead = route.interpolate(min(route.length, t + 1.0))
            if (ahead.x - p.x) * d[0] + (ahead.y - p.y) * d[1] < 0.0:
                route = LineString(list(route.coords)[::-1])
            out.append(_Exit(p, d, route, half, w, inf))
    return out


def _ramp(airport, law, cid, n, group, profile, axis_ln, floor, band, vis, notes):
    """One end's ``(ChannelRamp, pack feet)`` or ``None``."""
    tn = law.tables.structures.tunnel
    visual = float(law.tables.emit.cockpit.visual_m)
    lead, run = group[0], None
    for e in group:
        run = _pack_run(vis, e, tn.lane_width_m, visual)
        if run is not None:
            lead = e
            break
    route = lead.route
    t_x = route.project(lead.point)

    def ground(u: float) -> float:
        return _ground(airport, route, u)
    if run is not None:
        prof, source = _pack_profile(run, ground, tn), "pack"
    else:
        lips = [route.project(q) for q in _points(route.intersection(floor.boundary))]
        lips = [t for t in lips if t <= t_x]
        if not lips:
            return None
        t0 = max(lips)
        z0 = profile_z(profile, axis_ln.project(route.interpolate(t0)))
        if ground(t0) <= z0 + visual:
            notes.append(f"{cid}: way {lead.way.id} leaves through the wall at "
                         f"{_ll(airport, lead.point)} onto ground within {visual} m of the "
                         f"floor — no exit ramp (#2127 R3 A2)")
            return None
        rise = runout_profile(z0, lambda u: ground(t0 + u), tn.ramp_grade, tn.ramp_max_grade,
                              MAX_RUN_M)
        prof, source = [(t0 + u, z) for u, z in rise], "law"
    t0, t_top = prof[0][0], min(prof[-1][0], route.length)
    if t_top - t0 < 2.0 * STEP_M:
        return None
    ts = sorted({*np.arange(t0, t_top, STEP_M).tolist(), t_top})
    zs = np.interp(ts, [t for t, _z in prof], [z for _t, z in prof])
    stations = tuple((float(route.interpolate(t).x), float(route.interpolate(t).y), float(z))
                     for t, z in zip(ts, zs, strict=True))
    ring = _plan(group, lead, t0, t_top, run)
    if ring is None:
        return None
    outline = _outline(ring, route, t_top, band)
    ref = f"channel_floor:{cid.split(':')[-1]}#r{n}"
    from .channel import way_key
    notes.append(f"{cid}: exit ramp {ref} ({source}) for way(s) "
                 f"{'+'.join(str(e.way.id) for e in group)} leaving the wall at "
                 f"{_ll(airport, lead.point)}: {zs[0]:.2f} -> {zs[-1]:.2f} m over "
                 f"{t_top - t0:.0f} m, steepest {_steepest(ts, zs):.1%} (#2127 R3 A1-A3)")
    rec = ChannelRamp(ref, tuple(ring.exterior.coords)[:-1], tuple(outline.exterior.coords)[:-1],
                      stations, source, tuple(way_key(e.way) for e in group))
    return rec, frozenset((r[0], r[1]) for r in (run or ()))


def _pack_run(vis, e: _Exit, lane: float, visual: float):
    """The run ``[(station, row, t, z, (x, y))]`` of one member's feet flanking the
    route ``e`` and ending in LEDGE feet (A2), or ``None``."""
    if vis is None or vis.feet is None or vis.level is None:
        return None
    route, reach = e.route, e.half + lane
    t_x = route.project(e.point)
    by: dict[int, list] = {}
    for i, (f, k) in enumerate(zip(vis.feet, vis.kinds, strict=True)):
        for j, r in enumerate(f):
            q = Point(float(r[4]), float(r[5]))
            if route.distance(q) > reach:
                continue
            t = route.project(q)
            if t_x - MAX_RUN_M <= t <= t_x + reach:
                by.setdefault(int(r[3]), []).append((i, j, t, float(r[2]), k[j],
                                                     (float(r[4]), float(r[5]))))
    best = None
    for feet in by.values():
        feet.sort(key=lambda r: r[2])
        if feet[-1][4] != LEDGE:
            continue
        low = [m for m, (i, _j, _t, z, _k, _xy) in enumerate(feet)
               if np.isfinite(vis.level[i]) and abs(z - float(vis.level[i])) <= visual]
        if not low:
            continue
        run = [(i, j, t, z, xy) for i, j, t, z, _k, xy in feet[low[-1]:]]
        if len(run) >= 2 and (best is None or len(run) > len(best)):
            best = run
    return best


def _pack_profile(run, ground, tn) -> list[tuple[float, float]]:
    """The foot line (never falling) and, past its last foot, the run-out at
    the last interval's grade to the ground (A2)."""
    prof, top = [], -math.inf
    for _i, _j, t, z, _xy in run:
        top = max(top, z)
        if not prof or t > prof[-1][0] + 1e-6:
            prof.append((t, top))
    (ta, za), (tb, zb) = prof[-2], prof[-1]
    g = min(max((zb - za) / max(tb - ta, 1e-6), tn.ramp_grade), tn.ramp_max_grade)
    rise = runout_profile(zb, lambda u: ground(tb + u), g, tn.ramp_max_grade, MAX_RUN_M)
    return prof + [(tb + u, z) for u, z in rise[1:]]


def _plan(group, lead: _Exit, t0: float, t_top: float, run) -> "Polygon | None":
    """The ramp's plan: every exit route's carriageway over the lead's span,
    the lead's widened to its foot line (A3); one polygon."""
    a, b = lead.route.interpolate(t0), lead.route.interpolate(t_top)
    parts = []
    for e in group:
        r = e.route
        u0, u1 = (t0, t_top) if e is lead else sorted((r.project(a), r.project(b)))
        if u1 - u0 > 1.0:
            parts.append(substring(r, u0, u1).buffer(e.half, cap_style="flat",
                                                      join_style="mitre"))
    for side in (1.0, -1.0):
        feet = [r for r in (run or ()) if _side(lead.route, r) == side]
        if len(feet) >= 2:
            pts = [lead.route.interpolate(r[2]) for r in feet]
            foot = [_foot_xy(lead.route, r) for r in feet]
            strip = Polygon([(p.x, p.y) for p in pts] + foot[::-1]).buffer(0)
            if not strip.is_empty:
                parts.append(strip)
    plan = unary_union(parts) if parts else None
    if plan is None or plan.is_empty:
        return None
    if plan.geom_type != "Polygon":
        plan = max(plan.geoms, key=lambda g: g.area)
    return Polygon(plan.exterior)


def _outline(ring: Polygon, route: LineString, t_top: float, band: float) -> Polygon:
    """``ring`` ⊕ ``band``, cut off flat at the top line (A3: the road the
    ramp hands over to is never knifed back from it)."""
    p = route.interpolate(t_top)
    q = route.interpolate(max(0.0, t_top - 1.0))
    ux, uy = p.x - q.x, p.y - q.y
    n = math.hypot(ux, uy) or 1.0
    ux, uy = ux / n, uy / n
    big = 10.0 * (band + math.sqrt(ring.area) + 1.0)
    beyond = Polygon([(p.x - uy * big, p.y + ux * big), (p.x - uy * big + ux * big,
                                                         p.y + ux * big + uy * big),
                      (p.x + uy * big + ux * big, p.y - ux * big + uy * big),
                      (p.x + uy * big, p.y - ux * big)])
    out = ring.buffer(band, join_style="mitre").difference(beyond)
    if out.geom_type != "Polygon":
        out = max(out.geoms, key=lambda g: g.area)
    return out


def _side(route: LineString, r) -> float:
    i_xy = _foot_xy(route, r)
    p = route.interpolate(r[2])
    q = route.interpolate(min(route.length, r[2] + 1.0))
    return 1.0 if (q.x - p.x) * (i_xy[1] - p.y) - (q.y - p.y) * (i_xy[0] - p.x) >= 0 else -1.0


def _foot_xy(_route, r) -> tuple[float, float]:
    return r[4] if len(r) > 4 else (np.nan, np.nan)


def _ground(airport, route: LineString, u: float) -> float:
    """The DEM on the route ``u`` metres along it (its end tangent beyond)."""
    if u <= route.length:
        p = route.interpolate(u)
        return dem_z_at(airport, (p.x, p.y))
    a, b = route.coords[-2], route.coords[-1]
    n = math.hypot(b[0] - a[0], b[1] - a[1]) or 1.0
    k = u - route.length
    return dem_z_at(airport, (b[0] + (b[0] - a[0]) / n * k, b[1] + (b[1] - a[1]) / n * k))


def _steepest(ts, zs) -> float:
    return max((abs(zs[k + 1] - zs[k]) / max(ts[k + 1] - ts[k], 1e-6)
                for k in range(len(ts) - 1)), default=0.0)


def _points(g) -> list[Point]:
    if g.is_empty:
        return []
    if g.geom_type == "Point":
        return [g]
    return [q for q in getattr(g, "geoms", ()) if q.geom_type == "Point"]


def _ll(airport, p) -> str:
    la, lo = airport.frame.transformers()[1](p.x, p.y)
    return f"{la:.6f},{lo:.6f}"
