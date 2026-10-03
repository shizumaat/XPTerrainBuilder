"""THE ROAD-FACE MINT, WIDENED TO THE MAPPED OSM ROADS (owner RULINGS
2026-09-30b Q-100b, spec-author 30e (1)-(3), (6); the road-exit law 29y /
30z (1) / 10-02v (1); issue #100) — split out of ``classify/roles.py`` for
its line budget (lane roadmint100b).  ``roles.classify`` imports
:func:`mint_osm_ribbons` at call time; this module reads ``roles``' own
helpers at import, so the cycle never closes at import time."""
from __future__ import annotations

import shapely
import shapely.ops
from shapely.geometry import LineString, Point, Polygon
from shapely.ops import unary_union

from ..law import Law
from ..law.tables import role_cap, snap_margin_m, zone2_half_width_m
from ..model.airport import Airport
from ..model.planar import OSM_RIBBON_FEEDS
from .evidence import Evidence, polygon_parts
from .roles import TAXI_FAMILY, is_runway_shoulder
from .rules import Rules

__all__ = ["mint_osm_ribbons", "ribbon_extent", "bridge_gaps", "exit_reach"]




def ribbon_extent(cells, law: Law, pavement_union):
    """THE PATCH a mapped road is ribboned inside (30e (2)): the pavement
    and every airside band's zone-2 envelope — the regions
    ``planar/zones.zone_regions`` draws, read at their un-trimmed extent
    (the half-widths ARE the zone table's)."""
    RUNWAY_FAMILY_ROLES = ("runway", "runway_crossing")   # planar/zones.RUNWAY_FAMILY
    parts = [pavement_union] if not pavement_union.is_empty else []
    for c in cells:
        if c.role in RUNWAY_FAMILY_ROLES and not is_runway_shoulder(c):
            hw = zone2_half_width_m(law, "runway", c.code_number, c.code_letter)
        elif c.role in TAXI_FAMILY:
            hw = zone2_half_width_m(law, "junction", c.code_number, c.code_letter)
        else:
            continue
        if hw:
            parts.append(Polygon(c.ring, c.holes).buffer(hw, join_style="mitre",
                                                         mitre_limit=2.0))
    return unary_union(parts) if parts else Polygon()


def _way_intervals(line: LineString, inside) -> list[tuple[float, float]]:
    """The arclength intervals of ``line`` inside ``inside``."""
    out = []
    for part in _line_parts_of(line.intersection(inside)):
        a = line.project(Point(part.coords[0]))
        b = line.project(Point(part.coords[-1]))
        if b < a:
            a, b = b, a
        if b - a > 0.0:
            out.append((a, b))
    out.sort()
    return out


def _line_parts_of(g) -> list[LineString]:
    if g is None or g.is_empty:
        return []
    if g.geom_type == "LineString":
        return [g]
    return [q for q in getattr(g, "geoms", ()) if q.geom_type == "LineString"
            and q.length > 0]


def bridge_gaps(intervals: list[tuple[float, float]], gap_m: float
                ) -> list[tuple[float, float]]:
    """30e (2): consecutive in-patch stretches of ONE way joined across an
    out-of-patch gap of at most ``gap_m`` — never the way's whole span."""
    out: list[list[float]] = []
    for a, b in intervals:
        if out and a - out[-1][1] <= gap_m:
            out[-1][1] = max(out[-1][1], b)
        else:
            out.append([a, b])
    return [(a, b) for a, b in out]


def _stations(d0: float, d1: float, step: float) -> list[float]:
    out, d = [], d0
    while d <= d1 + 1e-9:
        out.append(d)
        d += step
    return out


def exit_reach(line: LineString, a: float, b: float, dem, airside,
               cap: float, station_m: float, hold_m: float = 0.0,
               max_reach_m: float = 1000.0) -> tuple[float, float]:
    """THE ROAD-EXIT LAW (owner RULINGS 2026-09-29y, 2026-09-30z (1),
    2026-10-02v (1); spec-author 29r / 30aa rules 5-7): where a mapped
    road LEAVES the patch (an in-patch span ``[a, b]`` of its way whose
    way continues beyond) the ribbon runs on until a profile climbing
    from the patch's level at exactly the road cap meets the terrain —
    "the TERRAIN IS CUT to support that grade" — so the road never steps
    up the patch edge.  The patch's level at the mouth is estimated before
    the solve as the LOWER of the DEM at the mouth and the DEM at the
    nearest airside pavement point (an adjacent-ground band is mandatory-
    down from its pavement, never above it); the reach is the first
    station ``d`` outward (stations one lane-width apart, the ribbon's
    own scale) with ``|DEM(s) - z0| <= cap * d``, plus one
    station so the last ring vertex stands ON the terrain — "met" meaning
    met over the next ``hold_m`` as well (the ribbon's own width: a step
    one lane past the mouth is the mouth's).  Without a DEM, a cap or an
    airside the span is what it was."""
    if dem is None or cap <= 0.0 or line.length <= 0.0:
        return a, b

    def z_at(s: float) -> float:
        p = line.interpolate(s)
        return float(dem.z(p.x, p.y))

    def level(s: float) -> float:
        p = line.interpolate(s)
        z0 = z_at(s)
        if airside is not None and not airside.is_empty:
            q = shapely.ops.nearest_points(airside, p)[0]
            z0 = min(z0, float(dem.z(q.x, q.y)))
        return z0

    def meets(s_exit: float, sign: float, d: float, z0: float) -> bool:
        return abs(z_at(s_exit + sign * d) - z0) <= cap * d

    def reach(s_exit: float, sign: float) -> float:
        z0 = level(s_exit)
        d = station_m
        limit = min(max_reach_m, (line.length - s_exit) if sign > 0 else s_exit)
        while d <= limit:
            # the profile has MET the terrain when it stays on it over the
            # ribbon's own width ahead (a shelf a lane-width past the
            # mouth is still the mouth's step, not open terrain)
            if all(meets(s_exit, sign, e, z0)
                   for e in _stations(d, min(limit, d + hold_m), station_m)):
                return min(limit, d + station_m)
            d += station_m
        return limit

    eps = 1e-6
    if b < line.length - eps:
        b = min(line.length, b + reach(b, +1.0))
    if a > eps:
        a = max(0.0, a - reach(a, -1.0))
    return a, b


def mint_osm_ribbons(airport: Airport, ev: Evidence, cells: list, law: Law,
                     rules: Rules, add) -> tuple[int, float]:
    """30e (1)-(3), (6): the RIBBON FACE of every mapped at-grade road
    (``planar/terrain_edge.road_ways`` — the one at-grade road source) of
    an ``osm_roads.ribbon_highways`` class, over its parts inside the patch
    plus the same-way gaps up to ``osm_roads.road_gap_bridge_m``; parts
    within ``osm_roads.dedup_m`` of a 1206 route dropped (the network is
    senior); half-width = ``road_profile.lane_width_m`` (the ribbon
    half-width ``terrain_edge.road_half_width_m`` reads).  Nothing already
    standing is overlapped — pavement, runway, shoulder, pad, a 1206
    corridor, an earlier ribbon — so no ribbon lies inside a pad face;
    structure faces (tunnel / bridge) cut the ribbons at the structure
    pass like every other cell.  Returns (faces minted, m2)."""
    from ..airport.road_ways import road_ways
    orr = rules.osm_roads
    if not orr.enabled or not orr.ribbon_highways:
        return 0, 0.0
    ways = [(w, ln) for w, ln in road_ways(getattr(airport, "osm_ways", ()))
            if (w.tags or {}).get("highway") in orr.ribbon_highways
            and getattr(w, "kind", "") in OSM_RIBBON_FEEDS]
    if not ways:
        return 0, 0.0
    extent = ribbon_extent(cells, law, ev.pavement_union)
    if extent.is_empty:
        return 0, 0.0
    cover = unary_union([c.line for c in ev.truck_chains]).buffer(orr.dedup_m) \
        if ev.truck_chains else Polygon()
    hw = float(law.tables.emit.road_profile.lane_width_m)
    # every cell standing, and every pad's set-back (``_cut_back_groundside``'s
    # own knife: ``groundside_cutback_m`` + the snap margin, mitred)
    knife_m = float(law.tables.structures.building_pad.groundside_cutback_m) \
        + snap_margin_m(law)
    occupied = unary_union([Polygon(c.ring, c.holes) for c in cells]
                           + ([Polygon(c.ring, c.holes).buffer(
                               knife_m, join_style="mitre", mitre_limit=2.0)
                               for c in cells if c.role == "building"]
                              if knife_m > 0.0 else []))
    grid = rules.cells.snap_grid_m
    from shapely.ops import substring
    n, area = 0, 0.0
    cap = role_cap(law, "service_road")
    cap_l = float(cap.longitudinal) if cap else 0.0
    dem = getattr(airport, "dem", None)
    airside = unary_union([Polygon(c.ring, c.holes) for c in cells
                           if c.side == "airside"]) if cells else Polygon()
    for w, line in sorted(ways, key=lambda wl: (wl[0].kind, wl[0].id)):
        spans = bridge_gaps(_way_intervals(line, extent), orr.road_gap_bridge_m)
        spans = [exit_reach(line, a, b, dem, airside, cap_l, hw, 2.0 * hw)
                 for a, b in spans]
        axes = []
        for a, b in spans:
            seg = substring(line, a, b)
            if not cover.is_empty:
                axes.extend(_line_parts_of(seg.difference(cover)))
            else:
                axes.append(seg)
        axes = [ax for ax in axes if ax.length >= orr.min_len_m]
        if not axes:
            continue
        rib = unary_union([ax.buffer(hw, cap_style="flat", join_style="mitre",
                                     mitre_limit=2.0) for ax in axes])
        rib = shapely.set_precision(rib.difference(occupied), grid)
        ref = f"{OSM_RIBBON_FEEDS[w.kind]}:{w.id}"
        k = 0
        for part in polygon_parts(rib):
            if part.area < rules.cells.min_area_m2:
                continue
            add("service_road", ref if k == 0 else f"{ref}#{k}", part,
                "service_road", None, None,
                {"osm_ribbon": 1.0, "highway": str(w.tags.get("highway")),
                 "road_len_m": float(sum(ax.length for ax in axes))})
            k += 1
            n += 1
            area += part.area
        if k:
            occupied = unary_union([occupied, rib])
    return n, area


