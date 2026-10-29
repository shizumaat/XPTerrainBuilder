"""THE BORES, MOUTHS AND APPROACHES of the OSM tunnel ways (M4; split out
of ``planar/structures.py`` for lane v2tunnelobj2 so that file stays
under its line budget — no behaviour moved with it): the way predicates,
the carriageway width, bore chains, the approach centreline outward
from a mouth, the mouths themselves and 31h's dual-carriageway merge.
Law ``structures.toml [tunnel]``; see ``planar/structures.py``'s module
doc for the model.
"""
from __future__ import annotations

import dataclasses as _dc
import math
import typing as _t

import shapely
from shapely.geometry import LineString, Point, Polygon
from shapely.ops import unary_union
from shapely.strtree import STRtree

from ..law import Law
from ..law.approach_corridor import ApproachCorridor, RunwayViewBand
from ..law.tables import role_family
from ..model.airport import Airport, OsmWay
from ..model.frame import XY
from ..model.planar import is_gap_ref, is_road_reach
from ..airport.deck_signature import (DEFAULT_TUNNEL_VALUES, is_bridge_way,
                                      is_tunnel_way)
from ..classify.roles import Cell
from ..geom.union_find import find_root
from ..airport.dem import dem_z_at
from ..airport.road_ways import mapped_width_m
from ..airport.wall_mouth import WallField
from ..geom.vector import unit_vector

_MITRE = dict(join_style="mitre", mitre_limit=2.0)


__all__ = ["carriageway_width_m", "pavement_half_widths", "Bore", "Mouth", "chains", "approach",
           "resample",
           "mouths", "FieldRegion", "cover_polygons", "standing_cover", "cut_gap_cells", "wall_field", "ApproachCorridor", "RunwayViewBand", "approach_corridor_of", "runway_band_of", "field_region_for", "mouth_reports", "under_cover", "merge_duals", "unit", "is_tunnel", "is_bridge",
           "PARALLEL_COS", "NODE_TOL", "apply_plates", "ramp_top", "approach_ground",
           "road_index", "road_end_m", "crossing_roads"]

#: Two OSM node coordinates closer than this (frame metres) are one node.
NODE_TOL = 0.05
#: Two directions within 30° are parallel (31h's dual test; the approach kink test).
PARALLEL_COS = math.cos(math.radians(30))


# ── tags ─────────────────────────────────────────────────────────────────

def is_tunnel(w: OsmWay,
              admitted: _t.Sequence[str] = DEFAULT_TUNNEL_VALUES) -> bool:
    """One predicate with ``airport/deck_signature.is_tunnel_way`` (§26:
    ``admitted`` is ``law.tables.structures.tunnel.admitted_values``)."""
    return is_tunnel_way(w.tags, admitted)


def is_bridge(w: OsmWay) -> bool:
    """One predicate with the deck signature's (``airport/deck_signature``)."""
    return is_bridge_way(w.tags)


def carriageway_width_m(tags: _t.Mapping[str, str], law: Law) -> float:
    """The way's stated ``width``, else ``lanes × lane_width_m`` (a
    railway counts as ``default_lanes``) — ``airport/road_ways.
    mapped_width_m`` at the ``[tunnel]`` lane law."""
    tn = law.tables.structures.tunnel
    return mapped_width_m(tags, tn.lane_width_m, tn.default_lanes)


def pavement_half_widths(axis_fn, ss: _t.Sequence[float], cells, polys, law: Law,
                         half_default: float) -> "tuple[dict[float, tuple[float, float]], list[str]]":
    """THE RAMP WIDTH FROM THE PAVEMENT (RULINGS 2026-09-06b (2); ``tunnel.
    ramp_width_source``): per station ``s`` the ramp's half widths ``(left,
    right)`` read from the pavement cell that TRACES the road there — a
    value cell (never the runway family, never a pad) containing the
    station whose across-axis centre lies within
    ``ramp_pavement_max_offset_m`` of the axis and which runs ALONG the
    axis (it contains the neighbouring stations too).  Stations no
    pavement traces are absent (the caller's lanes width stands).
    Returns the map and the cells' refs used."""
    from ..law.tables import is_value_role
    tn = law.tables.structures.tunnel
    if not tn.ramp_width_source or tn.ramp_width_source[0] != "pavement":
        return {}, []
    max_off = tn.ramp_pavement_max_offset_m
    cand = [(p, c) for p, c in zip(polys, cells)
            if is_value_role(law, c.role) and c.role not in ("runway", "runway_crossing",
                                                              "building")]
    if not cand:
        return {}, []
    # a station ON the pavement's edge (the mouth where the traced road
    # ends at the bore) counts: containment within one identity-grid step
    grid = law.tables.emit.identity.min_distinct_spacing_m
    hulls = [p.buffer(grid) for p, _c in cand]
    tree = STRtree(hulls)
    out: dict[float, tuple[float, float]] = {}
    refs: list[str] = []
    n = len(ss)
    reach = 10.0 * max(half_default, 1.0)
    for i, s in enumerate(ss):
        p = axis_fn(s)
        a, b = axis_fn(max(0.0, s - 1.0)), axis_fn(s + 1.0)
        u = unit(a, b)
        nv = (-u[1], u[0])
        prev_pt = axis_fn(ss[i - 1]) if i > 0 else None
        next_pt = axis_fn(ss[i + 1]) if i + 1 < n else None
        best = None
        for j in tree.query(Point(p), predicate="within"):
            poly, c = cand[int(j)]
            hull = hulls[int(j)]
            along = all(hull.contains(Point(q)) for q in (prev_pt, next_pt) if q is not None)
            if not along:
                continue
            ray_l = LineString([p, (p[0] + nv[0] * reach, p[1] + nv[1] * reach)])
            ray_r = LineString([p, (p[0] - nv[0] * reach, p[1] - nv[1] * reach)])
            hl = _ray_hit(ray_l, poly, p)
            hr = _ray_hit(ray_r, poly, p)
            if hl is None or hr is None:
                continue
            off = abs(hl - hr) / 2.0
            if off > max_off:
                continue
            if best is None or off < best[0]:
                best = (off, hl, hr, c.ref)
        if best is not None:
            out[s] = (best[1], best[2])
            if best[3] not in refs:
                refs.append(best[3])
    return out, refs


def _ray_hit(ray: LineString, poly, p: XY) -> float | None:
    """The distance from ``p`` along ``ray`` to the polygon's boundary."""
    x = ray.intersection(poly.boundary)
    if x.is_empty:
        return None
    pts = [g for g in shapely.get_parts(x) if g.geom_type == "Point"]
    if not pts:
        return None
    return min(math.hypot(g.x - p[0], g.y - p[1]) for g in pts)


# ── bores (chains of tunnel ways) ────────────────────────────────────────

def _key(p: XY) -> tuple[int, int]:
    return (int(round(p[0] / NODE_TOL)), int(round(p[1] / NODE_TOL)))


@_dc.dataclass
class Bore:
    ways: list[OsmWay]
    points: list[XY]          # the chain, in order

    @property
    def line(self) -> LineString:
        return LineString(self.points)


def _copies(ways: _t.Sequence[OsmWay]) -> dict[int, list[OsmWay]]:
    """THE SECOND FEED'S COPY IS THE SAME WAY (issue #1028, spec
    ``eddf-tunnel-mouths-spec.md`` E1): ``{index of the first way: [its
    coincident copies]}`` — a way whose nodes are another's node for node
    (``NODE_TOL``), in either direction.  Two OSM feeds (the big-roads and
    the airport-roads extracts) carry the same tunnel; chained, the copy
    ran the bore out and back, so both its "ends" stood at ONE portal and
    the real far portal was lost in the chain's middle (MEASURED EDDF: 118
    of 282 tunnel ways are such copies; ``-9780`` / ``-17626`` built two
    mouths at 50.034989, 8.520647 whose corridors overlapped each other)."""
    first: dict[tuple, int] = {}
    out: dict[int, list[OsmWay]] = {}
    for i, w in enumerate(ways):
        k = tuple(_key(p) for p in w.points)
        j = first.get(k, first.get(tuple(reversed(k))))
        if j is None:
            first[k] = i
        else:
            out.setdefault(j, []).append(w)
    return out


def chains(ways: list[OsmWay]) -> list[Bore]:
    """Join tunnel ways end to end where exactly two of them meet.  A
    second feed's coincident copy (:func:`_copies`) is no way of its own:
    it rides in its original's ``Bore.ways`` and never joins a chain."""
    copies = _copies(ways)
    copy_ids = {id(c) for cs in copies.values() for c in cs}
    ends: dict[tuple[int, int], list[int]] = {}
    for i, w in enumerate(ways):
        if id(w) in copy_ids:
            continue
        ends.setdefault(_key(w.points[0]), []).append(i)
        ends.setdefault(_key(w.points[-1]), []).append(i)
    used = [id(w) in copy_ids for w in ways]
    out: list[Bore] = []
    for i, w in enumerate(ways):
        if used[i]:
            continue
        used[i] = True
        pts = list(w.points)
        members = [w] + copies.get(i, [])
        for direction in (1, -1):
            while True:
                end = pts[-1] if direction == 1 else pts[0]
                cands = [j for j in ends.get(_key(end), ()) if not used[j]]
                if len(cands) != 1 or len(ends.get(_key(end), ())) != 2:
                    break
                j = cands[0]
                used[j] = True
                nxt = list(ways[j].points)
                if _key(nxt[-1]) == _key(end):
                    nxt.reverse()
                if direction == 1:
                    pts.extend(nxt[1:])
                else:
                    pts = list(reversed(nxt[1:])) + pts
                members.extend([ways[j]] + copies.get(j, []))
        out.append(Bore(members, pts))
    return out


# ── the approach ─────────────────────────────────────────────────────────

def approach(mouth: XY, inward: XY, ways: list[OsmWay], reach_m: float,
             admitted: _t.Sequence[str] = DEFAULT_TUNNEL_VALUES,
             turn_max_deg: float = 180.0) -> list[XY]:
    """The centreline OUTWARD from the mouth: non-tunnel ways joined at
    the mouth node, followed up to ``reach_m``; a straight extension of
    the bore's own end direction where no way continues.

    THE APPROACH WALK KEEPS ITS HEADING (spec §34 (2); Fable
    2026-09-13i, RULINGS 2026-09-13i item 7a).  At every node the walk
    takes the continuation with the SMALLEST TURN from the heading it
    arrived on, and refuses a turn over ``turn_max_deg``
    (``[tunnel] approach_turn_max_deg``, 60°) — an unrelated road
    meeting the approach at a junction is not the road the ramp is on.
    The route stays on the way it entered until that way ENDS (a way is
    walked whole, so a hairpin's own nodes — which turn gradually — are
    never a hop and are never refused).  Before this the walk tested
    direction on the FIRST hop only and then took the first candidate in
    load order at each node: LEMD −5980's ramp left its hairpin onto
    −15331 (33.3°) with −15328 (2.3°) beside it.

    THE ARRIVAL HEADING IS THE WAY'S, NOT ITS FLARE (issue #948).  Where
    the arrival hop refuses EVERY continuation, the turn is read again
    from the CHORD of the way the walk arrived on (its first node as
    walked to the junction): a carriageway that flares into a merge node
    — a dual carriageway rejoining its single way — arrives on a short
    hop tens of degrees off the road's own line, and the hop alone
    refused the road straight ahead (KBUR −22530's last 4.3 m hop stood
    62° off the 7-lane way north, so the walk ended there and its
    extension ran 59° off the road).  The fallback only admits: a walk
    the hop reading continues is unchanged.

    The walk is bounded by ``reach_m`` and by never walking a way twice,
    not by a count of ways: a road mapped as many short pieces is still
    one route (the retired six-hop cap ended KBUR's west carriageway's
    walk 239 m out, short of its 360 m ramp)."""
    idx: dict[tuple[int, int], list[tuple[int, bool]]] = {}
    for i, w in enumerate(ways):
        if is_tunnel(w, admitted) or ("highway" not in w.tags
                                      and "railway" not in w.tags):
            continue
        idx.setdefault(_key(w.points[0]), []).append((i, True))
        idx.setdefault(_key(w.points[-1]), []).append((i, False))
    path: list[XY] = [mouth]
    cur = mouth
    length = 0.0
    seen: set[int] = set()
    heading: XY = (-inward[0], -inward[1])     # OUTWARD from the bore
    cos_max = math.cos(math.radians(max(0.0, min(180.0, turn_max_deg))))
    chord: XY | None = None                    # the arriving way's own line
    for _hop in range(len(ways) + 1):
        best = _next_way(ways, idx.get(_key(cur), ()), seen, cur, heading, cos_max)
        if best is None and chord is not None:
            best = _next_way(ways, idx.get(_key(cur), ()), seen, cur, chord, cos_max)
        if best is None:
            break
        i, pts = best
        seen.add(i)
        chord = unit(cur, pts[-1]) if pts[-1] != cur else None
        for p in pts[1:]:
            length += math.hypot(p[0] - cur[0], p[1] - cur[1])
            path.append(p)
            if p != cur:
                heading = unit(cur, p)
            cur = p
            if length >= reach_m:
                return path
    if length < reach_m:
        # straight on, along the last direction (or away from the bore)
        if len(path) >= 2:
            ax, ay = path[-1][0] - path[-2][0], path[-1][1] - path[-2][1]
        else:
            ax, ay = -inward[0], -inward[1]
        L = math.hypot(ax, ay) or 1.0
        path.append((cur[0] + ax / L * (reach_m - length + 1.0),
                     cur[1] + ay / L * (reach_m - length + 1.0)))
    return path


def road_index(ways: _t.Sequence[OsmWay],
               admitted: _t.Sequence[str] = DEFAULT_TUNNEL_VALUES
               ) -> "tuple[list[LineString], STRtree | None]":
    """The mapped roads a ramp may follow — every non-tunnel ``highway`` /
    ``railway`` way the approach walk reads (:func:`approach`) — as
    ``(lines, tree, ways)``, built once per pass for :func:`road_end_m` and
    :func:`crossing_roads`."""
    kept = [w for w in ways if len(w.points) >= 2 and not is_tunnel(w, admitted)
            and ("highway" in w.tags or "railway" in w.tags)]
    lines = [LineString(w.points) for w in kept]
    return lines, (STRtree(lines) if lines else None), kept


#: A way the corridor axis stays within ``_ALONG_TOL_M`` of for longer than
#: ``_ALONG_MIN_M`` is a road the ramp runs ALONG (its own, or its other
#: feed's copy); a road crossing it meets the axis for ~twice the tolerance.
_ALONG_TOL_M = 0.5
_ALONG_MIN_M = 3.0


def crossing_roads(axis: LineString, index, law: Law,
                   routes: _t.Sequence[_t.Sequence[XY]] = ()) -> list[tuple[Polygon, str]]:
    """THE RAMP NEVER GOES THROUGH ANOTHER ROAD (owner, #1028 Q32): every
    mapped road of ``index`` (:func:`road_index`) that passes THROUGH the
    corridor axis, as its carriageway polygon (the way buffered by half its
    mapped width, ``carriageway_width_m``) and ``osm:<id>`` — a stop the
    ramp's top is trimmed at like any other (``structures.
    build_structures``'s truncation loop).  Not a road through it: a road
    the axis or one of ``routes`` (the members' own approaches) runs ALONG
    (the ramp's own road, or its other feed's copy), a road that only ENDS
    on the axis (a junction with the ramp's road), and a road on a bridge
    over it (its deck, §34 (12) (4)).  Roads the classification carries as
    cells already stop it (``structure_mouth`` clause 4); this reads the
    mapped way, so a road beyond the classified cover stops it too."""
    lines, tree, ways = index
    if tree is None:
        return []
    own = [axis] + [LineString(r) for r in routes if len(r) >= 2]
    out = []
    for j in tree.query(axis, predicate="intersects"):
        ln, w = lines[int(j)], ways[int(j)]
        if is_bridge(w):
            continue
        band = ln.buffer(_ALONG_TOL_M)
        if any(r.intersection(band).length > _ALONG_MIN_M for r in own):
            continue                                   # the road the ramp runs along
        ends = (Point(ln.coords[0]), Point(ln.coords[-1]))
        hits = [g for g in shapely.get_parts(axis.intersection(ln)) if g.geom_type == "Point"]
        if not any(min(g.distance(e) for e in ends) > _ALONG_MIN_M for g in hits):
            continue                                   # it ends on the axis: a junction
        out.append((ln.buffer(carriageway_width_m(w.tags, law) / 2.0, cap_style="flat"),
                    f"osm:{w.id}"))
    return out


#: A corridor whose mouth stands off the road it then joins (a plate's end,
#: §33 (2)) is on that road if it reaches it within this many half widths.
_JOIN_LEAD = 4.0


def road_end_m(axis: LineString, index, reach: float, step: float) -> float | None:
    """THE RAMP FOLLOWS THE ROAD (#1028): the station along a mapped bore's
    corridor axis where it LEAVES the mapped road — the first station
    farther than ``reach`` (the corridor's half width) from every road of
    ``index`` (:func:`road_index`).  :func:`approach` continues a walk
    that found no way on — a road that ends, turns past the cap or runs
    into another tunnel — as a straight line; that line is no road, and a
    ramp run along it crosses whatever lies there (measured EDDF bore
    −20307: 125 m of ramp diagonally across an apron past the service
    road's junction with the next bore).  ``None`` where the axis never
    leaves the road, and where it reaches none within ``_JOIN_LEAD`` half
    widths of its mouth (a bore end no way continues: its own line is the
    only reading, and the crossing roads and pavement stop it,
    :func:`crossing_roads`)."""
    lines, tree = index[0], index[1]
    if tree is None or axis.length <= 0.0:
        return None

    def on_road(s: float) -> bool:
        p = axis.interpolate(s)
        return any(lines[int(j)].distance(p) <= reach
                   for j in tree.query(p, predicate="dwithin", distance=reach))
    s = 0.0
    while not on_road(s):
        s += step
        if s > _JOIN_LEAD * reach:
            return None     # no mapped road to follow: the bore's own line, stops trim it
    s += step
    while s < axis.length:
        if not on_road(s):
            return s - step
        s += step
    return None


def _next_way(ways, at, seen: set[int], cur: XY, heading: XY, cos_max: float):
    """The unwalked way at node ``cur`` whose first hop turns least from
    ``heading``, inside the cap: ``(index, points as walked)`` or None."""
    best = None
    best_cos = cos_max - 1e-12
    for i, forward in at:
        if i in seen:
            continue
        pts = list(ways[i].points) if forward else list(reversed(ways[i].points))
        d = unit(cur, pts[min(1, len(pts) - 1)])
        c = d[0] * heading[0] + d[1] * heading[1]
        if c > best_cos:                       # the smallest turn, inside the cap
            best_cos, best = c, (i, pts)
    return best


def resample(path: _t.Sequence[XY], ss: _t.Sequence[float]) -> list[XY]:
    ln = LineString(path)
    out = []
    for s in ss:
        p = ln.interpolate(min(s, ln.length))
        out.append((p.x, p.y))
    return out


# ── the mouths ───────────────────────────────────────────────────────────

@_dc.dataclass
class Mouth:
    bore: Bore
    xy: XY
    inward: XY               # unit vector INTO the bore
    width_m: float
    approach: list[XY]
    ways: tuple[int, ...]


#: The unit vector from ``a`` towards ``b`` — ``geom.vector.unit_vector``,
#: under the name the planar structure modules import it by.
unit = unit_vector


def under_cover(line: LineString, polys: _t.Sequence[Polygon], tree) -> bool:
    """The RETIRED admission test (spec §29 (2)) — >= 1 m of the bore under
    the classified cover — kept only to count the bores the mouth-based
    admission and it disagree on (``bores_mouth_only``).  Reads the cell
    tree rather than a union of every cell (same answer, no union to
    build).  Lives here, beside the gate it is compared against, so
    ``structures.py`` stays under its 1,000-line budget."""
    if tree is None:
        return False
    parts = [line.intersection(polys[int(j)])
             for j in tree.query(line, predicate="intersects")]
    parts = [g for g in parts if not g.is_empty]
    return bool(parts) and unary_union(parts).length >= 1.0


def field_region_for(airport, law: Law, polys: _t.Sequence[Polygon],
                     corridors: _t.Sequence = ()) -> "FieldRegion":
    """THE REGION A MOUTH MAY STAND IN, assembled in ONE place: the
    classified cover (with the roofed corridors' footprints, which the
    caller passes in ``polys``) ⊕ ``[tunnel] mouth_standoff_m``, union
    the approach corridor of §31 (2), union THE RUNWAY LATERAL BAND of
    §29 (7).  ``corridors`` are the pack's roofed TUNNEL corridors
    (``airport.tunnel_objects.Corridor``) whose footprints ``polys``
    carries — §34 (12) (5) (a)'s pack-building reading never takes their
    objects for buildings nor refuses a mouth inside one (owner RULINGS
    2026-09-27a (3))."""
    region = FieldRegion(list(polys),
                         law.tables.structures.tunnel.mouth_standoff_m,
                         approach_corridor_of(airport, law),
                         runway_band_of(airport, law),
                         airport)
    region.corridor_prints = [c.footprint for c in corridors]
    region.corridor_objects = {i for c in corridors for i in c.objects}
    return region


def mouth_reports(on_field: "FieldRegion", mouth_list: _t.Sequence["Mouth"],
                  dropped: _t.Sequence[tuple]) -> tuple[list[str], int, list[str]]:
    """``(off-field lines, on-approach count, on-approach lines)`` for the
    structures line — the nearest drops and every mouth THE CORRIDOR
    kept, each with its true distance off the field, so both findings are
    visible without a rebuild and neither is read as the other.

    §34 (12) (5)'s refusals (``on_field.not_terrain``) ride the SAME list
    with their own wording and their own evidence — a bore the terrain
    witness withheld is never reported as a mouth that stood off the
    field, and the two counts are never added.  ``stats.mouths_off_field``
    is ``len(dropped)`` at the caller and so stays §29 (1)'s alone."""
    not_terrain = list(getattr(on_field, "not_terrain", ()) or ())
    off = [f"bore NOT A TERRAIN TUNNEL (§34 (12) (5)): {w}" for w in not_terrain]
    if not_terrain:
        off.insert(0, f"§34 (12) (5): {len(not_terrain)} bore(s) with an on-field mouth "
                      f"pass under nothing at grade and are NOT built")
    off += [f"mouth off-field {ids} at {xy[0]:.0f},{xy[1]:.0f} — {d:.0f} m off "
           f"the field, outside every approach corridor and outside the "
           f"runway lateral band"
           for ids, xy, d in sorted(dropped, key=lambda t: t[2])[:8]]
    on_approach = [m for m in mouth_list if not on_field.on_cover(Point(m.xy))]
    named = [f"mouth on approach {'+'.join(str(i) for i in m.ways)} at "
             f"{m.xy[0]:.0f},{m.xy[1]:.0f} — "
             f"{on_field.cover_distance_m(Point(m.xy)):.0f} m off the field, "
             f"in view ({_view_reason(on_field, m)})"
             for m in on_approach[:12]]
    return off, len(on_approach), named


def _view_reason(on_field: "FieldRegion", m: "Mouth") -> str:
    """WHICH TERM ADMITTED THIS MOUTH — §31 (2)'s approach corridor, §29
    (7)'s runway lateral band, or the ramp reach reaching one of them.
    The report states its own attribution: "in view" alone let 12al's
    corridor and 13bm's band be read as one region."""
    pt = Point(m.xy)
    reach = LineString(m.approach) if len(m.approach) >= 2 else pt
    for name, geom in (("approach corridor", pt), ("approach corridor", reach)):
        if on_field.in_corridor(geom):
            return name if geom is pt else name + ", by its ramp reach"
    for geom in (pt, reach):
        if on_field.in_band(geom):
            return ("runway lateral band" if geom is pt
                    else "runway lateral band, by its ramp reach")
    return "cover, by its ramp reach"


def approach_corridor_of(airport, law: Law) -> ApproachCorridor:
    """THE APPROACH CORRIDOR of §31 (2) for one airport, from the model's
    OWN runway ends (apt.dat row 100 thresholds) and the two ``[cockpit]``
    numbers — never a second idea of either.

    The harness reaches the same class from the emitted patch (the
    principal axis of each runway's ring cloud): one derivation, two
    sources for the axis it is derived FROM, which is why
    ``tests/auto_patch_v2/test_v2approachcorridor.py`` pins them against
    one fixture."""
    return ApproachCorridor(_runway_axes(airport),
                            float(law.tables.emit.cockpit.approach_km) * 1000.0,
                            float(law.tables.emit.cockpit.approach_half_width_m))


def _runway_axes(airport) -> list[tuple]:
    """The model's OWN runway axes (apt.dat row 100 thresholds) — the ONE
    source both §31 (2)'s corridor and §29 (7)'s band are built from."""
    return [(r.ends[0].xy, r.ends[1].xy, r.id)
            for r in getattr(airport, "runways", ()) or ()]


def runway_band_of(airport, law: Law) -> RunwayViewBand:
    """§29 (7) THE RUNWAY LATERAL BAND (Fable 2026-09-13; owner RULINGS
    2026-09-13bm (ii)) for one airport: each runway's axis ⊕ ``[cockpit]
    runway_view_half_width_m``, from the SAME axes and the SAME
    ``law/approach_corridor`` derivation as the corridor."""
    return RunwayViewBand(
        _runway_axes(airport),
        float(law.tables.emit.cockpit.runway_view_half_width_m))


def cover_polygons(classification) -> list[Polygon]:
    """THE CLASSIFIED COVER as polygons: one per STANDING cell, ring and
    holes — the ONE derivation the mapped-tunnel field
    (``build_structures``' :class:`FieldRegion`) and the kerb corridors'
    FIELD clause (:func:`wall_field`, spec §12h (1)) both read.  A late gap
    piece (spec §53 (18), ``model.planar.is_gap_ref``) is never cover: it
    follows the structures and may not admit, move or re-shape one.  Nor is
    a ribbon of the aerodrome's ROAD REACH (owner RULINGS 2026-10-22g,
    ``model.planar.is_road_reach``): a road graded because it lies inside
    the boundary admits, moves or refuses no structure.  MEASURED KPHX
    (#1246), with the reach ribbons standing: bore -2553's end on primary
    road -22826 by Terminal 4 was admitted on one and sank the road 5.2 m
    into a 12 m ramp (33.43602, -111.99307); bore -7353+-10192's portal
    was refused at another (#971) and bore -13436+-23951's ramp was
    clipped at a third and moved 110 m.  A PAD ROAD of the reach stands
    (:func:`standing_cover`: it stops a mouth and clips a ramp, as every
    pad road does) but is no field either — MEASURED KPHX: pad road
    ``small_roads:-9405``, 259 m from bore -26323+-41006's end, admitted
    the bore within its 603 m ramp reach."""
    return [Polygon(c.ring, c.holes) for c in classification.cells
            if not is_gap_ref(c.ref) and not is_road_reach(c)]


def _late(c) -> bool:
    """A cell that FOLLOWS the structures: a gap piece, or a road-reach
    ribbon that is not a pad road."""
    return is_gap_ref(c.ref) or (is_road_reach(c) and not c.evidence.get("pad_road"))


def standing_cover(classification) -> tuple[list, list, list[Polygon]]:
    """``(standing cells, gap pieces, standing polygons)`` — A GAP PIECE
    NEVER LEADS (spec §53 (18)): the structures are derived over the
    STANDING cells only — a ramp's climb, a wall band's stops and a deck's
    intervals read them, and a piece beside a tunnel would re-shape it
    (MEASURED at HECA: 15 wall / ramp vertices the base map does not
    carry).  The pieces are set aside and cut by the finished footprints
    last (:func:`cut_gap_cells`); a ROAD-REACH ribbon (RULINGS 2026-10-22g)
    is set aside with them and cut flush there.  The polygons are
    index-aligned with the standing cells; the FIELD is
    :func:`cover_polygons`."""
    cells = [c for c in classification.cells if not _late(c)]
    gap = [c for c in classification.cells if _late(c)]
    return cells, gap, [Polygon(c.ring, c.holes) for c in cells]


def cut_gap_cells(gap_cells, knife, law: Law, cut) -> None:
    """A gap piece STANDS OFF a structure as it stands off every standing
    cell (spec §53 (13)): each piece goes through ``build_structures``' own
    ``cut(cell, polygon, blade)`` with the structure footprints grown by the
    mint's stand-off as the blade.  LAST, so every standing and structure
    cell keeps the base map's place.  A ROAD-REACH ribbon (RULINGS
    2026-10-22g) is cut by the footprints themselves, as every standing
    ribbon is (30e (3): no ribbon inside a structure face, no stand-off)."""
    if not gap_cells:
        return
    from ..classify.gap_mint import standoff_m
    blade = None if knife.is_empty else knife.buffer(
        standoff_m(law), join_style="mitre", mitre_limit=2.0)
    for c in gap_cells:
        cut(c, Polygon(c.ring, c.holes), knife if is_road_reach(c) else blade)


def wall_field(classification, law: Law) -> WallField:
    """THE FIELD OF THE WALL CORRIDORS (spec §12h (1), (4); owner RULINGS
    2026-10-05h (3)): the classified cover ALONE — never the approach
    corridor or the runway band — with ``[tunnel] mouth_standoff_m``, as
    the record a reader (and a pool worker) is handed."""
    return WallField(tuple(cover_polygons(classification)),
                     float(law.tables.structures.tunnel.mouth_standoff_m))


class FieldRegion:
    """THE REGION A MOUTH MAY STAND IN (spec §29 (1) as amended by owner
    RULINGS 2026-09-12al): the classified cover ⊕ ``[tunnel]
    mouth_standoff_m`` **∪ THE APPROACH CORRIDOR of §31 (2)**.

    The cover carries the ROOFED CORRIDORS' footprints — the object /
    kerb-wall corridors are the owner's EGLL exception (Laws B/C, keyed on
    the pack's geometry, never on OSM) and are the field authority where
    they stand, so a bore mouth an object corridor takes is never gated
    away before the precedence runs.  Held as polygons in an STRtree with
    a ``dwithin`` query rather than a buffered union — the same region,
    exactly, without buffering a thousand-part union.

    THE CORRIDOR IS NOT THIS MODULE'S IDEA of a corridor: it is
    ``law/approach_corridor.ApproachCorridor``, the ONE derivation the
    harness's cockpit block reads too (owner 12al: "if it would be visible
    from an arriving or departing aircraft it should be cut, if not we can
    leave it raw DEM").  A portal 208 m off the classified surfaces but on
    the extended centreline of runway 14R is in plain view; one 4 km west
    of everything may be too, and the answer is the corridor's, not a
    standoff's.  ``corridor`` may be ``None`` (a caller with no runway
    geometry): the cover then decides alone."""

    def __init__(self, polys: _t.Sequence[Polygon], standoff_m: float,
                 corridor=None, band=None, airport=None) -> None:
        self.standoff_m = float(standoff_m)
        self._polys = list(polys)
        self._tree = STRtree(list(polys)) if len(polys) else None
        #: THE AIRPORT THE REGION WAS BUILT FROM (§34 (12) (5), lane
        #: `v2vmmcbore`) — carried here so ``mouths()`` can reach the DEM
        #: and the cover without a new argument at ``planar/structures.
        #: build_structures``'s call site, which is another lane's file
        #: this round.  ``None`` for every caller that passes none; the
        #: (5) witness then claims nothing.
        self.airport = airport
        #: §34 (12) (5)'s own report — one line per bore refused as NOT A
        #: TERRAIN TUNNEL, kept apart from §29 (1)'s off-field drops
        #: (two reports are never one region: the r1 discipline).
        self.not_terrain: list[str] = []
        #: the pack's roofed TUNNEL corridors' footprints among ``polys``
        #: and their placement ids (``field_region_for``'s ``corridors``):
        #: §34 (12) (5) (a)'s pack-building reading never refuses a mouth
        #: standing in one, nor takes their objects for buildings
        self.corridor_prints: list = []
        self.corridor_objects: set = set()
        self.corridor = corridor
        rings = list(corridor.rings()) if corridor is not None else []
        self._corridor_tree = (STRtree([Polygon(r) for r in rings])
                               if rings else None)
        self.band = band
        brings = list(band.rings()) if band is not None else []
        self._band_tree = (STRtree([Polygon(r) for r in brings])
                           if brings else None)

    def holds(self, geom) -> bool:
        """``geom`` (a mouth point or its ramp reach) stands where a pilot
        would see it: on the field, in an approach corridor, or BESIDE a
        runway inside §29 (7)'s lateral band."""
        return self.on_cover(geom) or self.in_corridor(geom) or \
            self.in_band(geom)

    def in_band(self, geom) -> bool:
        """§29 (7) THE RUNWAY LATERAL BAND alone (Fable 2026-09-13; owner
        RULINGS 2026-09-13bm (ii)) — quoted separately in the report, like
        the corridor, so "beside the runway" is never read as "on the
        field".  The corridor runs BEYOND each threshold and never beside
        the runway; SPJC's trunk-tunnel south mouths stood 191 m off the
        cover, 5 km from every corridor and 192 m from runway 16R/34L at
        mid-length."""
        if self._band_tree is None:
            return False
        return len(self._band_tree.query(geom,
                                         predicate="intersects")) > 0

    def on_cover(self, geom) -> bool:
        """The cover ⊕ ``mouth_standoff_m`` half alone."""
        if self._tree is None:
            return False
        return len(self._tree.query(geom, predicate="dwithin",
                                    distance=self.standoff_m)) > 0

    def in_corridor(self, geom) -> bool:
        """The §31 (2) half alone — quoted separately in the report, so a
        mouth built ON APPROACH is never read as a mouth on the field."""
        if self._corridor_tree is None:
            return False
        return len(self._corridor_tree.query(geom,
                                             predicate="intersects")) > 0

    def cover_run_m(self, line) -> float:
        """§34 (12) (5) (c): metres of ``line`` running UNDER the
        classified cover — the SAME polygons §29 (1)'s standoff is grown
        from and the same reading ``under_cover`` takes, without a second
        union to build."""
        if self._tree is None:
            return 0.0
        parts = [line.intersection(self._polys[int(j)])
                 for j in self._tree.query(line, predicate="intersects")]
        parts = [g for g in parts if not g.is_empty]
        return float(unary_union(parts).length) if parts else 0.0

    def cover_distance_m(self, geom) -> float:
        """Distance to the CLASSIFIED COVER alone — how far off the field
        a mouth the corridor admitted actually stands."""
        if self._tree is None:
            return float("inf")
        j = self._tree.nearest(geom)
        if j is None:
            return float("inf")
        return float(self._tree.geometries[int(j)].distance(geom))

    def distance_m(self, geom) -> float:
        """How far off the REGION ``geom`` stands (the dropped-mouth
        report): the lesser of its distance to the cover and to the
        nearest corridor edge; ``inf`` when there is neither."""
        d = self.cover_distance_m(geom)
        for tree in (self._corridor_tree, self._band_tree):
            if tree is None:
                continue
            j = tree.nearest(geom)
            if j is not None:
                d = min(d, float(tree.geometries[int(j)].distance(geom)))
        return d


def mouths(bores: list[Bore], osm: list[OsmWay], law: Law, reach_m: float,
           on_field=None) -> tuple[list[Mouth], int]:
    """The mapped ends of every bore, as mouths — GATED BY THE FIELD (spec
    §29 (1), owner RULINGS 2026-09-12r; Fable 2026-09-12t): "a tunnel
    emits only its mouths and ramps", and a mouth is built only where it
    STANDS ON THE FIELD.  ``on_field`` is the airport's governed region —
    the classified cover with the roofed corridors ⊕ ``[tunnel]
    mouth_standoff_m`` — prepared by the caller.  THE TEST IS THE MOUTH
    POINT *AND ITS RAMP REACH* (§29 (1)): a mapped end whose point stands
    outside the region AND whose approach corridor — the reach the ramp
    would be built along — never enters it is DROPPED here and counted in
    the returned tally, which the structures line names (``mouths
    off-field N``).  A mouth just off the cover whose ramp climbs onto the
    field is what that clause protects; the rail mouths 4.0 km out are
    neither.  ``on_field = None`` gates nothing (a caller with no
    classification).  The second member of the return is the dropped
    mouths — ``(way ids, xy, distance off the field)`` — for the report.

    LEMD's two rail bores are why: 4.9 km ways admitted by 125–162 m of
    cover under the ``building12`` pad whose SOUTH-WEST ends stand 4.0 km
    west of every other feature and 95 m up a hillside — ramps, rims and
    banks (149 vertices) that set the patch's whole western bbox edge and
    carry zero grade rows.
    """
    # §34 (12) (5) A TERRAIN TUNNEL PASSES UNDER SOMETHING AT GRADE (owner
    # RULINGS 2026-09-16d): the SECOND, independent admission condition,
    # after §29 (1)'s.  It is applied HERE because this is where admission
    # has stood since owner 12ab — a bore that fails it yields no mouths,
    # so nothing downstream can tell it from one that never had an
    # on-field mouth, and no other file needs a line.  Its refusals are
    # NAMED on ``on_field.not_terrain``, never folded into ``dropped``
    # (§29 (1)'s own population): the two reports stay apart.
    terrain = None
    if on_field is not None and getattr(on_field, "airport", None) is not None:
        from .structure_service import terrain_tunnel_witness
        terrain = terrain_tunnel_witness(on_field.airport, law, on_field, osm)
        on_field.not_terrain = []
    out: list[Mouth] = []
    dropped: list[tuple[str, XY, float]] = []
    from .bore_continuation import continues_underground, tunnel_ends
    t_ends = tunnel_ends(osm, law.tables.structures.tunnel.admitted_values)
    no_portal: list[str] = []
    if on_field is not None:
        on_field.no_portal = no_portal     # #1028: named by the structures line
    for b in bores:
        width = max(carriageway_width_m(w.tags, law) for w in b.ways)
        wids = tuple(w.id for w in b.ways)
        cand: list[tuple[Mouth, bool, float]] = []
        for end, nxt in ((b.points[0], b.points[1]), (b.points[-1], b.points[-2])):
            inward = unit(end, nxt)
            path = approach(end, inward, osm, reach_m,
                            law.tables.structures.tunnel.admitted_values,
                            law.tables.structures.tunnel.approach_turn_max_deg)
            m = Mouth(b, end, inward, width, path, wids)
            why = continues_underground(b, inward, path, t_ends, law, reach_m)
            if why is not None:
                no_portal.append(why)
                continue
            if on_field is None:
                cand.append((m, True, 0.0))
                continue
            pt = Point(end)
            reach = LineString(path) if len(path) >= 2 else pt
            held = on_field.holds(pt) or on_field.holds(reach)
            cand.append((m, held, min(on_field.distance_m(pt),
                                      on_field.distance_m(reach))))
        # §29 (7) THE SIBLING MOUTH — RULED (Fable 2026-09-13; owner
        # RULINGS 2026-09-13bm (ii): "a bore with one mouth built has its
        # sibling admitted under the same test; a tunnel with one mouth is
        # never right") and MEASURED REFUTED at LEMD by lane ``v2spjc``,
        # so it is NOT armed and the clause is deleted rather than gated.
        #
        # THE MEASUREMENT (dry ``--stage structures`` arms on main
        # 0c86fe2c, three-way base / band-only / band+sibling):
        #   * SPJC needs it for NOTHING.  The bar — the −641/−2525 trunk
        #     tunnel's south mouth at −12.0202431, −77.129278 — is built
        #     by §29 (7)'s RUNWAY LATERAL BAND alone (191 m off the
        #     cover, inside the 250 m band of runway 16R/34L); the
        #     band-only arm and the band+sibling arm are identical at
        #     SPJC (mouths 14, tunnels 8, off-field 6).
        #   * LEMD it REGRESSES.  Armed, it rebuilt three mouths the
        #     150 m standoff of RULINGS 2026-09-12r exists to drop —
        #     ``tunnel:-4928@1`` 2,309 m off the field and
        #     ``tunnel:-26708+-22223@0`` / ``tunnel:-26709+-8677@0`` at
        #     40.48100, −3.63953 and 40.48053, −3.63947, ~6.7 km west of
        #     the frame origin: the rail-bore class whose far mouths set
        #     the patch's whole western bbox edge (LEMD tunnels 51 -> 54,
        #     mouths 90 -> 93, off-field 45 -> 42).  A 4.9 km bore
        #     admitted by 125–162 m of cover under ONE pad is exactly the
        #     case where the sibling is nowhere a pilot looks.
        #
        # A narrowing that separates the two needs a law number this lane
        # may not author (a bore length, or a distance from the built
        # mouth).  Routed to the spec's author with the measurement.
        # §34 (12) (5) RUNS AFTER §29 (1), ON A BORE THAT SURVIVED IT.
        # The order is the reports': a bore with no on-field mouth was
        # never going to be built and is not a (5) finding (at VMMC 65 of
        # 77 bores are in that class), so (5) names only the bores it
        # ITSELF withholds.
        if terrain is not None and any(held for _m, held, _d in cand):
            built, why = terrain(b)
            if not built:
                on_field.not_terrain.append(why)
                continue
        for m, held, d in cand:
            if held:
                out.append(m)
            else:
                dropped.append(("+".join(str(i) for i in wids), m.xy, d))
    return out, dropped


def _parallel(a: Mouth, b: Mouth, sep_max: float) -> bool:
    """31h's test: mouths within the dual separation, approaches parallel
    and holding that separation 50 m out."""
    if b.bore is a.bore:
        return False
    d0 = math.hypot(a.xy[0] - b.xy[0], a.xy[1] - b.xy[1])
    if d0 > sep_max:
        return False
    if a.inward[0] * b.inward[0] + a.inward[1] * b.inward[1] < PARALLEL_COS:
        return False
    pa, pb = resample(a.approach, [50.0])[0], resample(b.approach, [50.0])[0]
    d1 = math.hypot(pa[0] - pb[0], pa[1] - pb[1])
    return abs(d1 - d0) <= 0.5 * d0 + 2.0


def merge_duals(mouths: list[Mouth], law: Law, stats, same=None
                 ) -> list[tuple[list[Mouth], XY, XY, float, list[XY]]]:
    """Cluster mouths of DIFFERENT bores that stand within the dual
    separation with parallel approaches (31h — transitively, so a 2+2
    with service lanes is ONE ramp): returns ``(members, mouth_xy,
    inward, full_width, axis_path)`` per ramp.  The mouth line stands at
    the OUTER of the mapped ends (a mapped bore is never cut open, 08-07
    ruling 2); the width spans every carriageway.  ``same`` (a mouth ->
    key or ``None``): mouths sharing a key are ONE ramp whatever their
    separation — the carriageways one edge bridge's back stops are one cut
    across both and the median (owner RULINGS 2026-10-28d Q214)."""
    sep_max = law.tables.structures.tunnel.dual_carriageway_max_separation_m
    n = len(mouths)
    parent = list(range(n))


    keys = [None if same is None else same(m) for m in mouths]
    for i in range(n):
        for j in range(i + 1, n):
            if (keys[i] is not None and keys[i] == keys[j]) or \
                    _parallel(mouths[i], mouths[j], sep_max):
                parent[find_root(parent, i)] = find_root(parent, j)
    groups: dict[int, list[Mouth]] = {}
    for i in range(n):
        groups.setdefault(find_root(parent, i), []).append(mouths[i])
    out = []
    for members in groups.values():
        if len(members) == 1:
            a = members[0]
            out.append(([a], a.xy, a.inward, a.width_m, list(a.approach)))
            continue
        stats.duals_merged += 1
        sx = sum(m.inward[0] for m in members)
        sy = sum(m.inward[1] for m in members)
        inward = unit((0.0, 0.0), (sx, sy))
        nx, ny = -inward[1], inward[0]
        # along: outward is -inward; the mouth line at the outermost end
        along = [-(m.xy[0] * inward[0] + m.xy[1] * inward[1]) for m in members]
        s_out = max(along)
        lat = [m.xy[0] * nx + m.xy[1] * ny for m in members]
        lo = min(l - m.width_m / 2 for l, m in zip(lat, members))
        hi = max(l + m.width_m / 2 for l, m in zip(lat, members))
        centre_lat = (lo + hi) / 2
        width = hi - lo
        # the axis: the mean of the approaches, re-based on the centre line
        length = max(LineString(m.approach).length for m in members)
        ss = [5.0 * k for k in range(int(length // 5.0) + 2)]
        rs = [resample(m.approach, ss) for m in members]
        axis = [(sum(r[k][0] for r in rs) / len(rs), sum(r[k][1] for r in rs) / len(rs))
                for k in range(len(ss))]
        a0 = axis[0]
        along0 = -(a0[0] * inward[0] + a0[1] * inward[1])
        lat0 = a0[0] * nx + a0[1] * ny
        dx = (centre_lat - lat0) * nx - (s_out - along0) * inward[0]
        dy = (centre_lat - lat0) * ny - (s_out - along0) * inward[1]
        axis = [(p[0] + dx, p[1] + dy) for p in axis]
        span, s_part = _dual_span_m(axis, members, law)
        width = max(width, span)
        if s_part is not None:
            axis = _straight_past(axis, ss, s_part)
        out.append((members, axis[0], inward, width, axis))
    return out


def _dual_span_m(axis: list[XY], members: list[Mouth], law: Law
                 ) -> tuple[float, float | None]:
    """THE DUAL RAMP SPANS ITS CARRIAGEWAYS ALONG THE RAMP, not at the mouth
    alone (issue #807): ``(the full width across every member's approach
    over the NOMINAL ramp length — mouth_depth_m / ramp_grade, the stations
    the ramp is built over at its design grade — the station where the
    carriageways PART, or None)``.

    They part where they stand further apart than half the dual separation
    (``dual_carriageway_max_separation_m``): there they stop being one road
    (KCLT's south ramp: both run into a roundabout), and the MEAN of two
    routes going different ways is no route at all.  KCLT's tertiary
    carriageways stand 11 m apart at the taxiway U mouths and ~18 m apart
    80 m out; the mouth's 17.5 m left each carriageway's outer edge on the
    ramp wall."""
    tn = law.tables.structures.tunnel
    ax = LineString(axis)
    s_max = min(tn.mouth_depth_m / max(tn.ramp_grade, 1e-6), ax.length)
    routes = [(LineString(m.approach), m.width_m / 2.0) for m in members
              if len(m.approach) >= 2]
    if not routes:
        return 0.0, None
    part_m = tn.dual_carriageway_max_separation_m / 2.0
    half = 0.0
    for k in range(int(ax.length) + 1):
        p = ax.interpolate(float(k))
        offs = [(r.distance(p), h) for r, h in routes]
        if 2.0 * max(d for d, _h in offs) > part_m:
            return 2.0 * half, float(k)         # the carriageways part here
        if k <= s_max:
            half = max([half] + [d + h for d, h in offs])
    return 2.0 * half, None


#: The chord the straight run past a parting takes its direction from: the
#: axis's own line over this run before the parting, not its last 5 m hop
#: (already bending toward one of the parting roads).
_PART_CHORD_M = 20.0


def _straight_past(axis: list[XY], ss: list[float], s_part: float) -> list[XY]:
    """The dual's axis up to where its carriageways part, then STRAIGHT on
    along its line over the last ``_PART_CHORD_M`` to its full length (issue
    #807): past the
    parting the mean axis kinks between two roads and the corridor folds
    ("the approach bends tighter than the corridor")."""
    keep = [p for p, s in zip(axis, ss, strict=False) if s <= s_part]
    if len(keep) < 2:
        keep = list(axis[:2])
    kl = LineString(keep)
    back = kl.interpolate(max(0.0, kl.length - _PART_CHORD_M))
    a = unit((back.x, back.y), keep[-1])
    rest = LineString(axis).length - kl.length
    if rest <= 0.0:
        return keep
    return keep + [(keep[-1][0] + a[0] * rest, keep[-1][1] + a[1] * rest)]

# ── the ramp's top (moved VERBATIM from planar/structures.py, lane
#    v2wallplate: that file stands at its 1,000-line budget and §33 grows
#    it; no behaviour moved with it) ─────────────────────────────────────
def ramp_top(airport: Airport, law: Law, axis_fn, mouth_z: float, climb_from: float,
              spacing: float, s_min: float = 0.0, grade: float | None = None,
              max_len: float | None = None) -> tuple[float | None, list[float]]:
    """``(s_top, station s values)`` — the first station at or beyond
    ``s_min`` where the climb from ``mouth_z`` at ``grade`` (a caller's
    own; ``ramp_max_grade`` where none is given)
    (starting at ``climb_from``) reaches the DEM ALONG THE ROUTE, plus
    one station of slack; ``None`` when the DEM is not reached within
    ``max_ramp_length_m``.

    A RAMP IS PRICED ALONG ITS ROUTE (spec §34 (1); Fable 2026-09-13i,
    RULINGS 2026-09-13i item 7a).  The reach is the AXIS LENGTH WALKED
    — ``s − climb_from`` — never the straight chord from the mouth
    line.  The retired chord term (``chord × grade ≥ rise``, an
    allowance for the within-shape law pricing ring pairs over the
    chord) made a ramp whose DEM condition was met at 271 m of route
    run 420 m of axis whenever the mapped road curved: 12 of LEMD's 59
    ramps carried axis/chord > 1.3, the worst 3.85, and −15327's ramp
    overran its road by 156 m.  A curved road is still a road; the
    grade a driver feels is the one along it.

    ``s_min`` is an object corridor's wall length: INSIDE the walls the
    DEM is not the ground (2026-09-06f: LEMD's Bridge4 stands in a
    cutting the SPAIN5M DEM carries, its axis sample 8 m under the
    walls' ground) — the ramp there is the design.  ``grade`` /
    ``max_len`` are a group's own law (a door ramp: 09-08b/c
    ``cutout.door``), else the tunnel's."""
    tn = law.tables.structures.tunnel
    g = tn.ramp_max_grade if grade is None else grade
    bound = tn.max_ramp_length_m if max_len is None else max_len
    ss = [0.0]
    s = 0.0
    while s < bound:
        s += spacing
        ss.append(s)
        if s <= climb_from or s < s_min - 1e-9:
            continue
        # the ramp meets the DEM where the DEM enters the ±ramp_max_grade
        # CONE from the datum, measured along the route: rising ground is
        # climbed, ground that has fallen below the bore floor (a mouth on
        # a ridge of the smoothed DEM — measured LEMD -15327+-5980: the
        # DEM 8.4 m under the datum 24 m out) is descended to, never
        # stepped down to
        reach = g * (s - climb_from)
        d = dem_z_at(airport, axis_fn(s))
        if math.isnan(d):
            return None, ss
        if abs(d - mouth_z) <= reach:
            ss.append(s + spacing)
            return s + spacing, ss
    return None, ss


def approach_ground(airport: Airport, axis_fn, band_m: float, spacing: float) -> float:
    """THE APPROACH'S GROUND (spec §33 (3)): the MEDIAN DEM along the
    approach's first stations beyond the mouth's own band — the stations
    at ``spacing`` from ``band_m`` out to four times it, which is the
    road the ramp has to meet.  ``nan`` when the DEM carries none of
    them."""
    zs = []
    s = band_m
    while s <= 4.0 * band_m + 1e-9:
        z = dem_z_at(airport, axis_fn(s))
        if not math.isnan(z):
            zs.append(z)
        s += max(spacing, 1.0)
    if not zs:
        return float("nan")
    zs.sort()
    return zs[len(zs) // 2]


# ── the thin-plate wall objects govern the mouth (spec §33 (2)) ──────────

def apply_plates(mouth_list: list[Mouth], plates: _t.Sequence, osm: list[OsmWay],
                 law: Law, reach_m: float) -> tuple[list[Mouth], list[str]]:
    """THE PACK'S WALL OBJECTS GOVERN THE MOUTH (spec §33 (2); owner
    RULINGS 2026-09-13d item 5; Fable 2026-09-13i).  A mouth standing
    INSIDE a thin-plate wall object that spans its bore is the OBJECT's
    (``tunnel.object.source_precedence = ["object", "osm"]``, per mouth as
    05n-3 already applies it): it MOVES to the plate's own end — the plan
    rectangle's short-side midpoint, so the corridor's axis is the
    object's centre — takes the plate's WIDTH, and keeps the mapped road
    beyond as its approach (the leading stretch that ran under the plate
    is dropped; the mouth is the portal, and the bore behind it emits
    nothing, §29).

    Measured LEMD: ``Bridge3.obj`` is 354.2 x 25.1 m and covers all
    223.7 m of bore ``-5931``; its mouths were built 7.0 m wide
    (``lanes x lane_width_m``), 1.08 m off the object's centre and 83 m
    INSIDE its north end.  Returns the mouths and one report line per
    mouth moved."""
    if not plates or not mouth_list:
        return mouth_list, []
    admitted = law.tables.structures.tunnel.admitted_values
    out: list[Mouth] = []
    notes: list[str] = []
    for m in mouth_list:
        p = _plate_for(m, plates)
        if p is None:
            out.append(m)
            continue
        # §33 (6) C1' THE PAIR MARKS A MOUTH RAMP (owner RULINGS
        # 2026-09-15e items 3/4; Fable / RULINGS 2026-09-15x).  Where the
        # object carries a PARALLEL PAIR of thin surface walls near this
        # mouth, THAT is the author's mouth ramp: the ramp lies between
        # the pair's inner faces, runs the pair's length, its mouth at
        # the end nearer the bore's COVERED stretch and its top at the
        # outer end.  The §33 (2) reading (the object's BOX end, clamped
        # to the bore) is superseded there — measured LEMD `Bridge3.obj`:
        # the box is 354.2 x 25.1 m but the solids are two 73 m pairs
        # 14.02 m apart at its two ends with 224 m of nothing between, so
        # the box's end is 83.9 m from any wall and its width 11 m too
        # wide.  Without a pair the §33 (2) (a) clamp stands exactly as
        # it is (the 14bl item 7/8 runaway it fixed).
        from .structure_pair import pair_mouth
        moved = pair_mouth(m, p, osm, law, reach_m, admitted)
        if moved is not None:
            out.append(moved[0])
            notes.append(moved[1])
            continue
        # the plate END this mouth belongs to, and the direction INTO the plate
        ax = LineString(p.ends)
        s_m = ax.project(Point(m.xy))
        k = 0 if s_m < ax.length / 2.0 else 1
        far = p.ends[1 - k]
        # §33 (2) (a) THE PLATE MOUTH IS CLAMPED TO THE COVERED EXTENT
        # (Fable 2026-09-14; RULINGS 2026-09-14bp items 7/8).  The move was
        # UNCONDITIONAL — to the plate's short-side midpoint, wherever that
        # stands.  A pack's wall object is a VIADUCT, not a portal marker:
        # LEMD's ``Bridge3.obj`` is a 354.2 x 25.1 m plan rectangle whose
        # ends run 83.9 m north and 46.6 m south of the 222.8 m bore way
        # −5931 it covers, so both mouths were built past the road's own
        # ends — the owner's three points at 40.4988 are that way's own two
        # nodes to 1.4 / 5.5 m.  The plate governs WIDTH and AXIS (§33 (2)
        # stands); the PORTAL cannot stand where the bore does not go, so
        # the move is clamped along the axis to the nearer of the plate's
        # end and the bore way's own end.
        s_p = float(ax.project(Point(p.ends[k])))
        s_end, clamped_to = _covered_end(ax, s_m, s_p, m, osm)
        q = ax.interpolate(s_end)
        end = (float(q.x), float(q.y))
        inward = unit(end, far)
        # THE APPROACH WALK IS UNCHANGED (§33 (2) (a)) where the mouth
        # keeps its own station: the mapped road out of the portal is what
        # it always was.  Only a mouth taken to the PLATE's end needs the
        # stretch that runs under the plate dropped.
        # ALONG the axis: a mouth projected sideways onto the object's own
        # centreline has not left its portal, and §33 (2)'s axis takeover is
        # exactly that projection.
        near = abs(s_end - s_m) <= law.tables.emit.identity.min_distinct_spacing_m
        path = list(m.approach) if (clamped_to is not None and near) else (
            approach(end, inward, osm, reach_m, admitted,
                     law.tables.structures.tunnel.approach_turn_max_deg)
            if clamped_to is not None else
            _approach_beyond(end, inward, m.approach, p.plan, osm, law, reach_m, admitted))
        moved = math.hypot(end[0] - m.xy[0], end[1] - m.xy[1])
        notes.append(f"mouth of bore {'+'.join(str(i) for i in m.ways)} taken by {p.id} "
                     f"(§33 (2)): moved {moved:.1f} m to "
                     + (f"the object's end" if clamped_to is None else
                        f"the bore way {clamped_to}'s own end — CLAMPED to the covered extent, "
                        f"{abs(s_p - s_end):.1f} m inside the object's end (§33 (2) (a))")
                     + f", width {m.width_m:.1f} -> {p.width_m:.1f} m")
        out.append(Mouth(m.bore, end, inward, p.width_m, path, m.ways))
    return out, notes


def _covered_end(ax: LineString, s_m: float, s_p: float, m: Mouth, osm: list[OsmWay]
                 ) -> tuple[float, int | None]:
    """THE COVERED EXTENT'S END ALONG THE PLATE'S AXIS (spec §33 (2) (a)):
    ``(station, the bore way whose end clamped it or None)`` — the plate's
    end ``s_p`` or the BORE CHAIN's own end on THE SAME SIDE of the mapped
    mouth, whichever is nearer ``s_m`` along the axis.  The portal is the
    bore's end; past it the object is a viaduct over ordinary ground and
    there is nothing bored to let out of.  The chain's ends, never an
    interior way's: a dual carriageway chain's joints are mid-bore."""
    d = 1.0 if s_p >= s_m else -1.0
    pts = list(getattr(m.bore, "points", ()) or ())
    best = None
    for q, wid in ((pts[0], m.ways[0] if m.ways else None),
                   (pts[-1], m.ways[-1] if m.ways else None)) if len(pts) >= 2 else ():
        s = float(ax.project(Point(q)))
        if (s - s_m) * d < -1e-6:
            continue                          # behind the mouth, not beyond it
        if best is None or abs(s - s_m) < abs(best[0] - s_m):
            best = (s, wid)
    if best is None or abs(best[0] - s_m) >= abs(s_p - s_m):
        return s_p, None
    return max(0.0, min(ax.length, best[0])), best[1]


def _plate_for(m: Mouth, plates: _t.Sequence):
    """The thin plate that governs this mouth: it spans one of the bore's
    own ways and holds the mapped end inside its plan."""
    pt = Point(m.xy)
    for p in plates:
        if not p.bore_ways or not p.plan.contains(pt):
            continue
        if any(wid in m.ways for wid, _L in p.bore_ways):
            return p
    return None


def _approach_beyond(end: XY, inward: XY, path: _t.Sequence[XY], plan: Polygon,
                     osm: list[OsmWay], law: Law, reach_m: float, admitted) -> list[XY]:
    """The approach from the plate's END outward: the mapped approach the
    OSM mouth already walked, with the stretch that runs UNDER the plate
    dropped and the plate's end midpoint prepended, so the ramp follows
    the real road rather than a straight extension (a plate's end stands
    off the mapped node, so ``approach`` alone would find no way there)."""
    keep: list[XY] = []
    if len(path) >= 2:
        rest = LineString(path).difference(plan)
        parts = [g for g in shapely.get_parts(rest) if g.geom_type == "LineString"]
        if parts:
            # the piece that starts nearest the plate's end, in path order
            best = min(parts, key=lambda g: Point(end).distance(g))
            if Point(end).distance(best) <= reach_m:
                cs = list(best.coords)
                if math.hypot(cs[0][0] - path[0][0], cs[0][1] - path[0][1]) \
                        > math.hypot(cs[-1][0] - path[0][0], cs[-1][1] - path[0][1]):
                    cs.reverse()
                keep = [q for q in cs
                        if math.hypot(q[0] - end[0], q[1] - end[1]) > NODE_TOL]
    if not keep:
        return approach(end, inward, osm, reach_m, admitted,
                        law.tables.structures.tunnel.approach_turn_max_deg)
    out = [end] + keep
    ln = LineString(out)
    if ln.length < reach_m:
        a = unit(out[-2], out[-1])
        out.append((out[-1][0] + a[0] * (reach_m - ln.length + 1.0),
                    out[-1][1] + a[1] * (reach_m - ln.length + 1.0)))
    return out
