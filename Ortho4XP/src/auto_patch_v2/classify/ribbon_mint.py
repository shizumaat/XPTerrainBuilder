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
from ..law.reference_code import ref_status, status_by_ref
from ..law.tables import (role_cap, runway_safety_area_length_m, snap_margin_m,
                          zone2_half_width_m, zone_edge_offset_m)
from ..model.airport import Airport
from ..model.planar import OSM_RIBBON_FEEDS, ROAD_REACH_KEY
from .evidence import Evidence, polygon_parts
from .roles import TAXI_FAMILY, is_runway_shoulder
from .lot_roads import lot_cells, split_lot_ribbon
from .pad_touch import touch_limit_m
from .rules import Rules
from ..geom.parts import areal_part, line_parts
from ..airport.road_ways import ribbon_half_width_m

__all__ = ["mint_osm_ribbons", "mint_reach_ribbons", "mint_pad_roads", "ribbon_extent",
           "road_extent",
           "bridge_gaps", "network_spans", "exit_reach"]




def _rsa_rect(poly, law: Law, cn, cl, hw: float, ends=None, status: int = 0):
    """The RSA rectangle beyond a runway's ends (owner RULINGS 2026-10-15c
    (2)): the band ``planar/zones`` grades runs the RSA length past the
    runway END (``ends``: the apt.dat ends, ``planar/zones._runway_band``'s
    own reading), and the patch a road is ribboned in covers it.  Without
    the ends, the cell's own rectangle (the slab ends)."""
    from shapely.geometry import LineString
    from ..geom.rotated_rect import long_axis, rotated_rectangle
    ab = ends if ends is not None else (
        long_axis(rotated_rectangle(poly)) if not poly.is_empty else None)
    if ab is None:
        return Polygon()
    (ax, ay), (bx, by) = ab
    L = ((bx - ax) ** 2 + (by - ay) ** 2) ** 0.5
    if L <= 0.0:
        return Polygon()
    ux, uy = (bx - ax) / L, (by - ay) / L
    r = runway_safety_area_length_m(law, cn, cl, status)
    return LineString([(ax - ux * r, ay - uy * r), (bx + ux * r, by + uy * r)]
                      ).buffer(hw, cap_style="flat")


def ribbon_extent(cells, law: Law, pavement_union, runways=()):
    """THE PATCH a mapped road is ribboned inside (30e (2)): the pavement
    and every airside band's zone-2 envelope — the regions
    ``planar/zones.zone_regions`` draws, read at their un-trimmed extent
    (the half-widths ARE the zone table's)."""
    RUNWAY_FAMILY_ROLES = ("runway", "runway_crossing")   # planar/zones.RUNWAY_FAMILY
    parts = [pavement_union] if not pavement_union.is_empty else []
    status_of = status_by_ref(runways)
    for c in cells:
        if c.role in RUNWAY_FAMILY_ROLES and not is_runway_shoulder(c):
            hw = zone2_half_width_m(law, "runway", c.code_number, c.code_letter,
                                    ref_status(status_of, c.ref))
        elif c.role in TAXI_FAMILY:
            hw = zone_edge_offset_m(law, "junction", c.code_number, c.code_letter)
        else:
            continue
        if hw:
            parts.append(Polygon(c.ring, c.holes).buffer(hw, join_style="mitre",
                                                         mitre_limit=2.0))
        if hw and c.role in RUNWAY_FAMILY_ROLES:
            rw = next((r for r in runways if r.id == c.ref), None)
            ends = (rw.ends[0].xy, rw.ends[1].xy) if rw is not None else None
            parts.append(_rsa_rect(Polygon(c.ring), law, c.code_number, c.code_letter, hw,
                                   ends, status_of.get(c.ref, 0)))
    return unary_union(parts) if parts else Polygon()


def road_extent(cells, law: Law, ev: Evidence, rules: Rules, runways=()):
    """THE REACH a mapped road is ribboned inside (owner RULINGS 2026-10-22g,
    superseding 30e (2)'s extent; issue #1246): the AERODROME BOUNDARY
    (apt.dat 130, ``Evidence.boundary``) buffered ``osm_roads.
    boundary_reach_m`` outward, with :func:`ribbon_extent`'s envelope —
    the pavement and the airside bands' zone-2 ground, which a road crossing
    it grades with whatever the boundary says.  An airport with no boundary
    keeps that envelope alone (30e (2)).  ``(reach, envelope)``: the
    envelope is where a road's exit still reads the airside's level
    (:func:`exit_reach`'s ``near``)."""
    zone = ribbon_extent(cells, law, ev.pavement_union, runways)
    boundary = getattr(ev, "boundary", None)
    reach_m = float(rules.osm_roads.boundary_reach_m)
    if boundary is None or boundary.is_empty or reach_m < 0.0:
        return zone, zone
    grown = boundary.buffer(reach_m, join_style="mitre", mitre_limit=2.0) \
        if reach_m > 0.0 else boundary
    return (unary_union([zone, grown]) if not zone.is_empty else grown), zone


def _way_intervals(line: LineString, inside) -> list[tuple[float, float]]:
    """The arclength intervals of ``line`` inside ``inside``.

    A way that does not meet ``inside`` has none, and is answered by the
    prepared predicate instead of a full overlay (issue #803: the pad-road
    exit walk asked this of every tile way against the whole airport's
    union — 30 s of HECA's last stage, nearly all of it for ways nowhere
    near the field).  ``inside`` is prepared in place, once; the answer is
    the overlay's own, because an empty intersection is exactly a false
    ``intersects``."""
    if not shapely.is_prepared(inside):
        shapely.prepare(inside)
    if not inside.intersects(line):
        return []
    out = []
    for part in line_parts(line.intersection(inside)):
        a = line.project(Point(part.coords[0]))
        b = line.project(Point(part.coords[-1]))
        if b < a:
            a, b = b, a
        if b - a > 0.0:
            out.append((a, b))
    out.sort()
    return out


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


def _arc_cuts(line: LineString, intervals: list[tuple[float, float]]
              ) -> list[float]:
    """The arclengths that cut ``line`` into pieces each wholly in or out
    of the extent: its own vertices and every interval end."""
    cuts = {0.0, float(line.length)}
    s = 0.0
    pts = list(line.coords)
    for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
        s += ((x1 - x0) ** 2 + (y1 - y0) ** 2) ** 0.5
        cuts.add(s)
    for a, b in intervals:
        cuts.update((a, b))
    return sorted(cuts)


def network_spans(ways: list[tuple[object, LineString]], extent, gap_m: float,
                  serve=None) -> list[list[tuple[float, float]]]:
    """30e (2)'s GAP BRIDGE READ ON THE ROAD, NOT THE OSM WAY (issue #609):
    per way, the arclength intervals ribboned — its in-extent stretches,
    plus every out-of-extent stretch on a path of at most ``gap_m`` along
    the ROAD NETWORK (ways sharing a node) between two in-extent mouths.
    OSM splits a road at every junction, so the forecourt between two
    garage entries is a path of several short ways; the one-way bridge
    (:func:`bridge_gaps`) is this read's special case of the path along
    a single way.  A road that leaves the patch toward nothing in-patch
    within ``gap_m`` is not bridged (never the way's whole span).  With
    ``serve`` (a region — the building pads) a path is bridged only when
    one of its two mouths stands on it: the road between serves a pad."""
    import heapq
    ivs = [_way_intervals(ln, extent) for _, ln in ways]
    # sub-edges: (way, s0, s1, inside); nodes keyed by their coordinate
    # (shared OSM nodes are identical doubles after the entry quantum)
    edges: list[tuple[int, float, float, bool]] = []
    adj: dict[tuple[float, float], list[tuple[int, tuple[float, float]]]] = {}
    inside_at: dict[tuple[float, float], bool] = {}
    outside_at: dict[tuple[float, float], bool] = {}

    def key(p) -> tuple[float, float]:
        return (round(float(p.x), 3), round(float(p.y), 3))

    for i, (_w, ln) in enumerate(ways):
        cuts = _arc_cuts(ln, ivs[i])
        for s0, s1 in zip(cuts, cuts[1:]):
            if s1 - s0 <= 1e-9:
                continue
            mid = 0.5 * (s0 + s1)
            inside = any(a - 1e-9 <= mid <= b + 1e-9 for a, b in ivs[i])
            na, nb = key(ln.interpolate(s0)), key(ln.interpolate(s1))
            e = len(edges)
            edges.append((i, s0, s1, inside))
            for n in (na, nb):
                (inside_at if inside else outside_at)[n] = True
            if not inside:
                adj.setdefault(na, []).append((e, nb))
                adj.setdefault(nb, []).append((e, na))
    mouths = [n for n in inside_at if n in outside_at]
    serving = None if serve is None else {
        n for n in mouths if serve.covers(Point(n)) or serve.distance(Point(n)) <= 2e-3}
    bridged: set[int] = set()
    for m in mouths:
        dist = {m: 0.0}
        pred: dict[tuple[float, float], tuple[int, tuple[float, float]]] = {}
        heap = [(0.0, m)]
        while heap:
            d, n = heapq.heappop(heap)
            if d > dist.get(n, float("inf")):
                continue
            if n != m and n in inside_at:
                q = n
                while q in pred and (serving is None or m in serving or n in serving):
                    e, q = pred[q]               # mark the path back to m
                    bridged.add(e)
                continue                          # a mouth ends the walk
            for e, nn in adj.get(n, ()):
                i, s0, s1, _ = edges[e]
                nd = d + (s1 - s0)
                if nd <= gap_m and nd < dist.get(nn, float("inf")):
                    dist[nn] = nd
                    pred[nn] = (e, n)
                    heapq.heappush(heap, (nd, nn))
    out = [list(iv) for iv in ivs]
    for e in bridged:
        i, s0, s1, _ = edges[e]
        out[i].append((s0, s1))
    return [bridge_gaps(sorted(iv), 1e-6) for iv in out]


def _stations(d0: float, d1: float, step: float) -> list[float]:
    out, d = [], d0
    while d <= d1 + 1e-9:
        out.append(d)
        d += step
    return out


def exit_reach(line: LineString, a: float, b: float, dem, airside,
               cap: float, station_m: float, hold_m: float = 0.0,
               max_reach_m: float = 1000.0, near=None) -> tuple[float, float]:
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
    one lane past the mouth is the mouth's).  With ``near`` (the airside
    bands' envelope, :func:`road_extent`) the airside's level is read only
    at a mouth within one station of it: a road leaving the aerodrome's
    reach far from any airside leaves at its own ground (RULINGS
    2026-10-22g).  Without a DEM, a cap or an airside the span is what it
    was."""
    if dem is None or cap <= 0.0 or line.length <= 0.0:
        return a, b

    def z_at(s: float) -> float:
        p = line.interpolate(s)
        return float(dem.z(p.x, p.y))

    def level(s: float) -> float:
        p = line.interpolate(s)
        z0 = z_at(s)
        if airside is not None and not airside.is_empty and (
                near is None or near.distance(p) <= station_m):
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


def _interval_minus(spans: list[tuple[float, float]],
                    cut: list[tuple[float, float]]) -> list[tuple[float, float]]:
    """``spans`` without ``cut`` (both sorted arclength intervals)."""
    out = []
    for a, b in spans:
        for c, d in cut:
            if d <= a or c >= b:
                continue
            if c > a:
                out.append((a, c))
            a = max(a, d)
            if a >= b:
                break
        if b - a > 1e-9:
            out.append((a, b))
    return out


def _ribbon_ways(airport: Airport, rules: Rules) -> list[tuple[object, LineString]]:
    """The mapped at-grade roads of a ribbon class, in the mint's order."""
    from ..airport.road_ways import road_ways
    orr = rules.osm_roads
    if not orr.enabled or not orr.ribbon_highways:
        return []
    ways = [(w, ln) for w, ln in road_ways(getattr(airport, "osm_ways", ()))
            if (w.tags or {}).get("highway") in orr.ribbon_highways
            and getattr(w, "kind", "") in OSM_RIBBON_FEEDS]
    ways.sort(key=lambda wl: (wl[0].kind, wl[0].id))
    return ways


def _mint_spans(w, line: LineString, spans, occupied, serial: dict[str, int],
                cover, law: Law, rules: Rules, add, extra: dict,
                min_len: float | None = None, lots=None):
    """One way's ribbon over ``spans`` less ``occupied``, added part by
    part (refs numbered on from ``serial``): ``(parts, m2, ribbon)`` — the
    ribbon ``None`` when no part was minted.  ``min_len`` (default
    ``osm_roads.min_len_m``, the floor under a stray stub) is the shortest
    axis ribboned: a pad road's piece between two standing roads is road
    however short (the cell floor ``cells.min_area_m2`` still stands).
    ``lots`` (``lot_roads.lot_cells``): a stretch running ALONG a lot is
    minted as that lot (RULINGS 2026-10-14a (2), ``classify/lot_roads``);
    the returned ribbon still covers it (it is occupied)."""
    from shapely.ops import substring
    orr = rules.osm_roads
    hw = ribbon_half_width_m(w.tags, law)
    axes = []
    for a, b in spans:
        seg = substring(line, a, b)
        if not cover.is_empty:
            axes.extend(line_parts(seg.difference(cover)))
        else:
            axes.append(seg)
    axes = [ax for ax in axes
            if ax.length >= (orr.min_len_m if min_len is None else min_len)]
    if not axes:
        return 0, 0.0, None
    rib = _ribbon_over(axes, hw, occupied, float(law.tables.emit.road_profile.lane_width_m),
                       rules.cells.snap_grid_m)
    road, lot_parts = rib, []
    if lots:
        road, lot_parts = split_lot_ribbon(
            rib, line, lots, hw, touch_limit_m(law), rules.cells.snap_grid_m,
            rules.cells.min_area_m2)
    for lot, part in lot_parts:
        k = serial.get(f"{lot.ref}#road", 0)
        serial[f"{lot.ref}#road"] = k + 1
        add(lot.role, f"{lot.ref}#road{k}", part, lot.kind, None, None,
            {"lot_road": 1.0, "lot_of": lot.ref, **({"lot_road_pad": 1.0} if extra.get("pad_road") else {}),
             "highway": str(w.tags.get("highway")),
             "lot_road_way": f"{OSM_RIBBON_FEEDS[w.kind]}:{w.id}"})
    ref = f"{OSM_RIBBON_FEEDS[w.kind]}:{w.id}"
    k0 = k = serial.get(ref, 0)
    area = 0.0
    for part in polygon_parts(road):
        if part.area < rules.cells.min_area_m2:
            continue
        add("service_road", ref if k == 0 else f"{ref}#{k}", part,
            "service_road", None, None,
            {"osm_ribbon": 1.0, "highway": str(w.tags.get("highway")),
             "road_len_m": float(sum(ax.length for ax in axes)), **extra})
        k += 1
        area += part.area
    serial[ref] = k
    return k - k0, area, (rib if k > k0 or lot_parts else None)


def _ribbon_over(axes, hw: float, occupied: "_Occupied", core_hw: float, grid: float):
    """The ribbon of ``axes`` at half-width ``hw`` less ``occupied``,
    widened only AROUND the core-width ribbon (``core_hw``) the same axes
    mint (issue #949): the map's width widens a road the core ribbons, and
    never mints road where the core's ribbon is covered — a road the
    pavement already traces, whose wider buffer would only lay a strip
    along that pavement's edge (KBUR way −18822, ``lanes=3``: a 0.5 m strip
    87 m along ``dsf:pol122``'s edge beside a pad, 2.5 m off it)."""
    def _rib(h: float):
        g = unary_union([ax.buffer(h, cap_style="flat", join_style="mitre",
                                   mitre_limit=2.0) for ax in axes])
        return shapely.set_precision(areal_part(occupied.cut(g)), grid)
    # a ribbon is an AREA (``geom/parts.areal_part``): the collapsed edges
    # an overlay hands back with it would ride into ``_Occupied`` and the
    # next way's cut would refuse them (#1147, KCLT)
    core = _rib(core_hw)
    if hw <= core_hw or core.is_empty:
        return core
    reach = core.buffer(hw - core_hw, join_style="mitre", mitre_limit=2.0)
    return shapely.set_precision(areal_part(_rib(hw).intersection(reach)), grid)


class _Occupied:
    """What a ribbon may not overlap: the cells standing when the mint
    began, and every ribbon minted since — held APART (issue #1083:
    re-unioning the whole map after every way was ~60 s of HECA's
    classify).  :meth:`cut` takes the standing cells off a ribbon, then
    the union of only the minted ribbons whose bounds meet it."""

    def __init__(self, base):
        self.base = base
        self.ribs: list = []
        self.bounds: list[tuple[float, float, float, float]] = []

    def add(self, rib) -> None:
        self.ribs.append(rib)
        self.bounds.append(rib.bounds)

    def cut(self, g):
        out = g.difference(self.base)
        x0, y0, x1, y1 = g.bounds
        near = [r for r, b in zip(self.ribs, self.bounds, strict=True)
                if b[0] <= x1 and b[2] >= x0 and b[1] <= y1 and b[3] >= y0]
        return out.difference(unary_union(near)) if near else out


def _cover(ev: Evidence, rules: Rules):
    return unary_union([c.line for c in ev.truck_chains]).buffer(rules.osm_roads.dedup_m) \
        if ev.truck_chains else Polygon()


def mint_osm_ribbons(airport: Airport, ev: Evidence, cells: list, law: Law,
                     rules: Rules, add, first_out: dict | None = None
                     ) -> tuple[int, float]:
    """30e (1)-(3), (6): the RIBBON FACE of every mapped at-grade road
    (``planar/terrain_edge.road_ways`` — the one at-grade road source) of
    an ``osm_roads.ribbon_highways`` class, over its parts inside the
    airside bands' envelope (the reach beyond it is
    :func:`mint_reach_ribbons`', RULINGS 2026-10-22g) plus the same-way
    gaps up to ``osm_roads.road_gap_bridge_m``; parts
    within ``osm_roads.dedup_m`` of a 1206 route dropped (the network is
    senior); half-width = the way's own (``airport/road_ways.
    ribbon_half_width_m``: its mapped carriageway, never under the core's
    ``road_profile.lane_width_m``; issue #949).  Nothing already
    standing is overlapped — pavement, runway, shoulder, pad, a 1206
    corridor, an earlier ribbon — and every pad's set-back is kept
    (roadweld100: "the ribbon takes the same set-back itself"), so no
    ribbon lies inside a pad face; structure faces (tunnel / bridge) cut
    the ribbons at the structure pass like every other cell.
    ``first_out`` receives what :func:`mint_pad_roads` reads: each way's
    ribboned spans and the serial of its refs.  Returns (faces minted, m2)."""
    cx = _context(airport, ev, cells, law, rules)
    if cx is None:
        return 0, 0.0
    # THE BANDS' ENVELOPE (30e (2)) here; THE REACH beyond it (RULINGS
    # 2026-10-22g) in :func:`mint_reach_ribbons`, after the gap pieces
    n, area = _mint_pass(cx, cx.zone, None, {}, add)
    if first_out is not None:
        first_out.update(spans=cx.spans_of, serial=cx.serial, extent=cx.zone,
                         reach=cx.extent)
    return n, area


def mint_reach_ribbons(airport: Airport, ev: Evidence, cells: list, law: Law,
                       rules: Rules, add, first: dict) -> tuple[int, float]:
    """THE ROAD REACH (owner RULINGS 2026-10-22g): what remains of each
    mapped road inside the aerodrome boundary ⊕ ``boundary_reach_m`` once
    the envelope's ribbons (:func:`mint_osm_ribbons`) AND THE GAP PIECES
    stand.  Minted after the gap pieces so it re-cuts none of them — a
    gap-apron part is stage-1 airside (MEASURED LGAV: with the reach minted
    first, ``gapapron:0/1/2/4`` were re-cut and 81 airside nodes moved, worst
    0.26 m).  Marked ``ROAD_REACH_KEY``: a reach ribbon never leads a
    structure (``planar/structure_approach``).  A PAD ROAD inside the reach
    stays a pad road (:func:`mint_pad_roads`' own spans, read on the
    envelope, 13a): at the pad's FOOTPRINT, welded by the touch witness,
    standing for the structures but no field (MEASURED KPHX, way -21842 by
    Terminal 3: as a plain reach ribbon it was held off the terminal's pad
    and fell 2.9 m below it).  ``first`` is :func:`mint_osm_ribbons`'
    ``first_out``, updated with the reach as :func:`mint_pad_roads`' extent.
    Returns (faces minted, m2)."""
    reach = first.get("reach") if first else None
    if reach is None or reach is first.get("extent"):
        return 0, 0.0
    cx = _context(airport, ev, cells, law, rules)
    if cx is None:
        return 0, 0.0
    cx.serial, cx.spans_of = first["serial"], first["spans"]
    cx.at_pads = _Occupied(unary_union([Polygon(c.ring, c.holes) for c in cells]))
    cx.at_pads.ribs, cx.at_pads.bounds = cx.occupied.ribs, cx.occupied.bounds
    cx.lots = lot_cells(cells)
    mine = {key: list(v) for key, v in cx.spans_of.items()}
    held = _pad_road_spans(cx.ways, cells, cx.zone, rules.osm_roads.road_gap_bridge_m, mine)
    n, area = _mint_pass(cx, cx.extent, mine, {ROAD_REACH_KEY: 1.0}, add, held)
    first.update(spans=cx.spans_of, serial=cx.serial, extent=cx.extent)
    return n, area


def _context(airport: Airport, ev: Evidence, cells: list, law: Law, rules: Rules):
    """The mint's reading of the airport and the cells standing now."""
    import types
    ways = _ribbon_ways(airport, rules)
    if not ways:
        return None
    extent, zone = road_extent(cells, law, ev, rules, getattr(airport, "runways", ()))
    if extent.is_empty:
        return None
    # every cell standing, and every pad's set-back (``_cut_back_groundside``'s
    # own knife: ``groundside_cutback_m`` + the snap margin, mitred)
    knife_m = float(law.tables.structures.building_pad.groundside_cutback_m) \
        + snap_margin_m(law)
    occupied = _Occupied(unary_union([Polygon(c.ring, c.holes) for c in cells]
                           + ([Polygon(c.ring, c.holes).buffer(
                               knife_m, join_style="mitre", mitre_limit=2.0)
                               for c in cells if c.role == "building"]
                              if knife_m > 0.0 else [])))
    cap = role_cap(law, "service_road")
    return types.SimpleNamespace(
        ways=ways, extent=extent, zone=zone, cover=_cover(ev, rules),
        hw=float(law.tables.emit.road_profile.lane_width_m), occupied=occupied,
        at_pads=occupied, lots=None, cap_l=float(cap.longitudinal) if cap else 0.0,
        dem=getattr(airport, "dem", None), law=law, rules=rules,
        airside=unary_union([Polygon(c.ring, c.holes) for c in cells
                             if c.side == "airside"]) if cells else Polygon(),
        serial={}, spans_of={})


def _mint_pass(cx, inside, minus: dict | None, extra: dict, add,
               pads: dict | None = None) -> tuple[int, float]:
    """One pass of the mint over ``inside``: each way's spans there (the gap
    bridge, the exit reach) less ``minus``; ``pads``' spans minted as pad
    roads instead."""
    orr = cx.rules.osm_roads
    n, area = 0, 0.0
    for w, line in cx.ways:
        key = (w.kind, w.id)
        spans = sorted(exit_reach(line, a, b, cx.dem, cx.airside, cx.cap_l, cx.hw,
                                  2.0 * cx.hw, near=cx.zone)
                       for a, b in bridge_gaps(_way_intervals(line, inside),
                                               orr.road_gap_bridge_m))
        if minus is not None:
            spans = _interval_minus(spans, bridge_gaps(minus.get(key, []), 1e-6))
        held = sorted((pads or {}).get(key, []))
        if held:
            spans = _interval_minus(spans, bridge_gaps(held, 1e-6))
        for sp, ex, occ, kw in ((spans, extra, cx.occupied, {}),
                                (held, {"pad_road": 1.0, ROAD_REACH_KEY: 1.0}, cx.at_pads,
                                 {"min_len": 0.0, "lots": cx.lots})):
            if not sp:
                continue
            cx.spans_of[key] = sorted(cx.spans_of.get(key, []) + sp)
            k, m2, rib = _mint_spans(w, line, sp, occ, cx.serial, cx.cover, cx.law,
                                     cx.rules, add, ex, **kw)
            n += k
            area += m2
            if rib is not None:
                cx.occupied.add(rib)
    return n, area


def _pad_road_spans(ways, cells, extent, gap_m: float, mine: dict) -> dict:
    """Per way, the spans :func:`mint_pad_roads` reads from ``extent`` and
    the pads: the network bridge a pad serves, less the ribbons' own."""
    pads = [Polygon(c.ring, c.holes) for c in cells if c.role == "building"]
    if not pads:
        return {}
    pad_union = unary_union(pads)
    served = network_spans(ways, unary_union([extent, pad_union]), gap_m, serve=pad_union)
    out = {}
    for (w, _line), spans in zip(ways, served, strict=True):
        rest = _interval_minus(spans, bridge_gaps(mine.get((w.kind, w.id), []), 1e-6))
        if rest:
            out[(w.kind, w.id)] = rest
    return out


def mint_pad_roads(airport: Airport, ev: Evidence, cells: list, law: Law,
                   rules: Rules, add, first: dict) -> tuple[int, float]:
    """THE PAD ROADS (issue #609; owner RULINGS 2026-10-13a (1)-(3), 13d)
    — what remains of each mapped road once a BUILDING PAD is patch too
    and the gap bridge is read along the road NETWORK
    (:func:`network_spans`), a path bridged only when one of its mouths
    stands on a pad: the stretches that reach a pad and the paths from a
    pad to the patch or to another pad.  Minted AFTER every other cell —
    the patch's own ribbons (``first``, :func:`mint_osm_ribbons`'s
    ``first_out``) and the §53 gap pieces — so nothing standing is
    overlapped or re-cut: the map without the pad roads is the airport's
    as it was.  Evidence ``pad_road`` (published as
    ``PlanarMap.pad_roads``): junior to every pavement they meet, solved
    in the last stage.  A pad is subtracted at its FOOTPRINT, never with
    the set-back knife (09j (2): a road touching a pad in source is
    welded; the engine's own knife is no witness) — the caller reads these
    cells through the one touch witness (``roles._cut_back_groundside``).
    Returns (faces minted, m2)."""
    pads = [Polygon(c.ring, c.holes) for c in cells if c.role == "building"]
    ways = _ribbon_ways(airport, rules)
    if not pads or not ways or not first:
        return 0, 0.0
    pad_union = unary_union(pads)
    served = network_spans(ways, unary_union([first["extent"], pad_union]),
                           rules.osm_roads.road_gap_bridge_m, serve=pad_union)
    occupied = _Occupied(unary_union([Polygon(c.ring, c.holes) for c in cells]))
    cover = _cover(ev, rules)
    # 14a (2): a pad road's stretch along a lot is the lot.  The patch's own
    # ribbons (``mint_osm_ribbons``) are NOT read: their lot strips re-solve
    # stage 1, and MEASURED (lane lotroads) that moves airside — HECA apron
    # ``dsf:objpav402`` 0.62 m and 30 pads up to 0.87 m, KCLT pads 0.54 m
    # and runway 18L/36R 0.05 m — the pad roads' strips (SPJC building24)
    # move none.  Owner question, not ruled.
    lots = lot_cells(cells)
    n, area = 0, 0.0
    for (w, line), spans in zip(ways, served):
        mine = bridge_gaps(first["spans"].get((w.kind, w.id), []), 1e-6)
        spans = _interval_minus(spans, mine)
        if not spans:
            continue
        k, m2, rib = _mint_spans(w, line, spans, occupied, first["serial"], cover,
                                 law, rules, add, {"pad_road": 1.0}, min_len=0.0,
                                 lots=lots)
        n += k
        area += m2
        if rib is not None:
            occupied.add(rib)
    return n, area
