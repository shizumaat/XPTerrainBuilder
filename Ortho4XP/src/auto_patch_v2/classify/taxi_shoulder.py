"""THE TAXIWAY SHOULDER (owner RULINGS 2026-11-10m, #1900 HECA objpav447):
"if there's a narrow strip of pavement next to a taxiway, running parallel
to the taxi route centerline, then its a shoulder that just become part of
the taxiway as one shape.  Like runways, it stops at every junction."

The runway's §40 (1) rule (``roles._runway_shoulder``) read against a
TAXI-FAMILY cell instead of a runway ring, with the runway's own numbers:

* the strip's boundary runs along the taxi cell, PARALLEL to that cell's
  taxi centreline, for at least ``corridor.runway_shoulder_shared_m`` —
  the shared edge's run measured as STATIONS along the centreline, so an
  edge that crosses the taxiway (a perpendicular road, a stand lead-in)
  runs nowhere along it;
* it is NARROW: its mean depth off that edge (area / run) is at most
  ``apron.arm_road_max_width_m`` — narrower than the narrowest parking
  module (one stall row and its aisle, ``lot.min_lot_width_m`` + 1), so
  nothing a vehicle parks across and no stand bay is ever a shoulder
  (#1900: "no apron on a shape narrower than a stand/apron minimum
  width").  The runway's own ribbon bound (50 m) is a corridor's width
  and admitted whole pages at HECA (36.8-49.6 m deep, measured on the
  dry classify arm; CYXY pav9 33.1 m).

THE SHOULDER STOPS AT EVERY JUNCTION: only the part of the strip opposite
the parallel shared edge — the edge's flat-capped band, as deep as the
runway shoulder's (``corridor.runway_shoulder_max_depth_m``) — joins
the taxiway; where the taxi cell ends (a junction, a crossing) the edge
ends and so does the shoulder.  The rest keeps the verdict it had.

The joined part takes the taxi cell's role, ref and code letter, so it is
one shape with the taxiway: one surface, one law, no zone between them
(zones are drawn round the taxi family's union).  What is never a shoulder:
a ROAD on mapped evidence (a road strip source, a 1206 route corridor) and
pavement holding a 1300 startup (a stand is apron).

#1900 (owner 2026-11-10T23:12Z, HECA taxiway G at 30.12699,31.41024: "there
is only a single taxiway running perpendicular to the runways here ... a
service road crossing from one apron, over the taxiway, to the other apron,
no horizontal taxiway shapes anywhere in this area"):

* a §43 / 10l ARM ROAD is a road only BESIDE its road: the HECA
  ``dsf:objpav99`` neck is an L — 200 m along the crossing road (road) and
  600 m along taxiway G with no road near (G's shoulder).  Its depth is read
  on the leg away from the road;
* the join repeats until a round joins nothing, so a strip beside a joined
  shoulder joins too (``dsf:objpav447`` beside that neck).
"""
from __future__ import annotations

import typing as _t

from shapely.geometry import LineString, Point, Polygon
from shapely.ops import unary_union
from shapely.strtree import STRtree

from ..geom.parts import line_parts
from .evidence import polygon_parts

__all__ = ["join_taxi_shoulders", "SHOULDER_HOSTS"]

#: The verdicts a strip may carry and still be read as a taxiway's shoulder:
#: pavement no taxi evidence claimed (the ladder's apron / open-default /
#: groundside verdicts, §110's road-by-proportions included).
SHOULDER_HOSTS = ("apron", "parking_lot", "service_road", "groundside_pavement",
                  "service_junction")


def _mapped_road(ref: str, evid: _t.Mapping) -> bool:
    """A road on MAPPED evidence, never a shoulder: a road strip source
    (owner 2026-09-04j), a 1206 route corridor outside pavement.  A §43 /
    RULINGS 2026-11-10l ARM ROAD is a road only BESIDE its road
    (``_beside_road``): the leg of it that runs along a taxiway away from
    any road is that taxiway's shoulder (#1900, owner 2026-11-10T23:12Z)."""
    return evid.get("kind") == "strip" or ref.startswith("route")


def _beside_road(evid: _t.Mapping, roads, narrow: float):
    """The ground a 10l arm road is a road on: within one road width
    (``apron.arm_road_max_width_m``) of a road centreline beyond its own
    width — ``neck.road_arms``' own "beside" reach.  ``None`` for any other
    strip, or when no road is mapped."""
    if not evid.get("arm_road") or roads is None:
        return None
    return roads.buffer(narrow + float(evid.get("neck_width_m", narrow)))


def _run_along(edge, axis: LineString) -> float:
    """The STATIONS ``edge`` covers along ``axis``: each segment's projected
    length, summed — a parallel edge runs its length, a crossing one ~0."""
    run = 0.0
    for ln in line_parts(edge):
        cs = list(ln.coords)
        for a, b in zip(cs, cs[1:], strict=False):
            run += abs(axis.project(Point(b)) - axis.project(Point(a)))
    return run


def _parallel_edge(edge, axis: LineString, tol: float):
    """The segments of ``edge`` running along ``axis`` (their projected run
    at least ``1 - tol`` of their own length)."""
    keep = []
    for ln in line_parts(edge):
        cs = list(ln.coords)
        for a, b in zip(cs, cs[1:], strict=False):
            seg = LineString([a, b])
            if seg.length > 0 and abs(axis.project(Point(b)) - axis.project(Point(a))) \
                    >= (1.0 - tol) * seg.length:
                keep.append(seg)
    return unary_union(keep) if keep else None


def join_taxi_shoulders(final: list[list], taxi_family: tuple[str, ...],
                        axes: list[LineString], rules, holds_startup,
                        road_lines: _t.Sequence[LineString] = ()) -> dict:
    """RULINGS 2026-11-10m over the scorer's ``final`` rows
    (``[role, ref, face, letter, evid, kind]``), IN PLACE: each strip's
    shoulder part becomes a row of its taxi cell's role / ref / letter; the
    rest stays a row of its own verdict.  ``axes`` are the taxi centrelines
    the slice cut with; ``holds_startup(face)`` the #262 rung; ``road_lines``
    the mapped road centrelines (a 10l arm road stays road beside them).

    Rounds repeat until one joins nothing: a strip beside a joined shoulder
    runs along the same taxiway (#1900: ``dsf:objpav447`` lies beside the
    ``dsf:objpav99`` neck, which lies beside taxiway G).  Returns the
    counters."""
    stats = {"taxi_shoulders": 0, "taxi_shoulder_m2": 0.0}
    if not rules.corridor.taxi_shoulder or rules.corridor.runway_shoulder_shared_m <= 0.0 \
            or not axes:
        return stats
    roads = unary_union(list(road_lines)) if road_lines else None
    axis_tree = STRtree(axes)
    for _ in range(len(final)):
        if not _join_round(final, taxi_family, axes, axis_tree, rules,
                           holds_startup, roads, stats):
            break
    return stats


def _join_round(final, taxi_family, axes, axis_tree, rules, holds_startup,
                roads, stats) -> int:
    """One pass of the join over ``final``; returns the strips joined."""
    import math
    need = rules.corridor.runway_shoulder_shared_m
    band_m = rules.corridor.runway_shoulder_max_depth_m
    narrow = rules.apron.arm_road_max_width_m
    reach = rules.junction.route_territory_half_width_m
    tol = rules.cells.on_tol_m
    floor = rules.cells.min_area_m2
    taxi = [r for r in final if r[0] in taxi_family]
    if not taxi:
        return 0
    taxi_tree = STRtree([r[2] for r in taxi])
    # the parallel test's angle: the corridor sub-role's own "parallel"
    cos_tol = 1.0 - math.cos(math.radians(rules.taxi_subrole.parallel_max_angle_deg))
    joins = 0
    out: list[list] = []
    for row in final:
        role, ref, face, letter, evid, kind = row
        if role not in SHOULDER_HOSTS or _mapped_road(ref, evid) or holds_startup(face):
            out.append(row)
            continue
        road_here = _beside_road(evid, roads, narrow)
        best = None
        for j in taxi_tree.query(face.buffer(tol)):
            host = taxi[int(j)]
            hp: Polygon = host[2]
            edge = face.boundary.intersection(hp.boundary.buffer(tol))
            if edge.is_empty or edge.length < need:
                continue
            # the cell's own centreline: the taxi axis nearest the shared
            # edge among those within the route territory of the cell
            near = [axes[int(k)] for k in axis_tree.query(hp.buffer(reach))]
            if not near:
                continue
            mid = edge.centroid
            axis = min(near, key=lambda a: a.distance(mid))
            par = _parallel_edge(edge, axis, cos_tol)
            if par is None:
                continue
            run = _run_along(par, axis)
            if run < need:
                continue
            # NARROW: the strip's mean depth off the edge, a 10l road's own
            # ground left out (an L-shaped neck's road leg is not the
            # depth of its taxiway leg); the shoulder is the strip in the
            # edge's flat-capped band, so it stops where the taxi cell stops
            own = face if road_here is None else face.difference(road_here)
            if own.area > narrow * run:
                continue
            part = own.intersection(par.buffer(band_m, cap_style="flat"))
            if best is None or run > best[1]:
                best = (host, run, part, own.area / run)
        joined = [] if best is None else \
            [p for p in polygon_parts(best[2]) if p.area >= floor]
        if not joined:
            out.append(row)
            continue
        host, run, _part, depth = best
        joins += 1
        rest = [p for p in polygon_parts(face.difference(unary_union(joined)))
                if p.area >= floor]
        for p in joined:
            out.append([host[0], host[1], p, host[3],
                        dict(host[4], kind=host[5], taxi_shoulder=1.0,
                             taxi_shoulder_run_m=run,
                             taxi_shoulder_depth_m=depth,
                             taxi_shoulder_source=ref, taxi_shoulder_was=role),
                        host[5]])
            stats["taxi_shoulders"] += 1
            stats["taxi_shoulder_m2"] += p.area
        for p in rest:
            out.append([role, ref, p, letter, dict(evid, taxi_shoulder_rest=1.0), kind])
    final[:] = out
    return joins
