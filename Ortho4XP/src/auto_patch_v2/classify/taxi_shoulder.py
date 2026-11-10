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
a ROAD on mapped evidence (a road strip source, a §43 / 10l arm road, a 1206
route corridor) and pavement holding a 1300 startup (a stand is apron).
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
    (owner 2026-09-04j), a §43 / RULINGS 2026-11-10l arm road, a 1206
    route corridor outside pavement."""
    return (evid.get("kind") == "strip" or bool(evid.get("arm_road"))
            or ref.startswith("route"))


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
                        axes: list[LineString], rules, holds_startup) -> dict:
    """RULINGS 2026-11-10m over the scorer's ``final`` rows
    (``[role, ref, face, letter, evid, kind]``), IN PLACE: each strip's
    shoulder part becomes a row of its taxi cell's role / ref / letter; the
    rest stays a row of its own verdict.  ``axes`` are the taxi centrelines
    the slice cut with; ``holds_startup(face)`` the #262 rung.  Returns the
    counters."""
    need = rules.corridor.runway_shoulder_shared_m
    band_m = rules.corridor.runway_shoulder_max_depth_m
    narrow = rules.apron.arm_road_max_width_m
    reach = rules.junction.route_territory_half_width_m
    tol = rules.cells.on_tol_m
    floor = rules.cells.min_area_m2
    stats = {"taxi_shoulders": 0, "taxi_shoulder_m2": 0.0}
    if not rules.corridor.taxi_shoulder or need <= 0.0 or not axes:
        return stats
    taxi = [r for r in final if r[0] in taxi_family]
    if not taxi:
        return stats
    taxi_tree = STRtree([r[2] for r in taxi])
    axis_tree = STRtree(axes)
    # the parallel test's angle: the corridor sub-role's own "parallel"
    import math
    cos_tol = 1.0 - math.cos(math.radians(rules.taxi_subrole.parallel_max_angle_deg))
    out: list[list] = []
    for row in final:
        role, ref, face, letter, evid, kind = row
        if role not in SHOULDER_HOSTS or _mapped_road(ref, evid) or holds_startup(face):
            out.append(row)
            continue
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
            if run < need or face.area > narrow * run:
                continue
            if best is None or run > best[1]:
                best = (host, run, par)
        if best is None:
            out.append(row)
            continue
        host, run, par = best
        band = par.buffer(band_m, cap_style="flat")
        joined = [p for p in polygon_parts(face.intersection(band)) if p.area >= floor]
        if not joined:
            out.append(row)
            continue
        rest = [p for p in polygon_parts(face.difference(unary_union(joined)))
                if p.area >= floor]
        for p in joined:
            out.append([host[0], host[1], p, host[3],
                        dict(host[4], kind=host[5], taxi_shoulder=1.0,
                             taxi_shoulder_run_m=run,
                             taxi_shoulder_depth_m=face.area / run,
                             taxi_shoulder_source=ref, taxi_shoulder_was=role),
                        host[5]])
            stats["taxi_shoulders"] += 1
            stats["taxi_shoulder_m2"] += p.area
        for p in rest:
            out.append([role, ref, p, letter, dict(evid, taxi_shoulder_rest=1.0), kind])
    final[:] = out
    return stats
