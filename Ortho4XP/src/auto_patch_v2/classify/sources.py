"""SOURCE-POLYGON classes (owner 2026-09-04j): every pavement source —
an apt.dat 110 polygon or a draped DSF page — is read ONCE for what it
carries, and the answer names it a road STRIP, a parking LOT or OPEN
pavement.  Strips and lots are cut from their neighbours at their own
boundary (the road-to-lot mouth IS the lot's boundary where the road's
corridor crosses it; the apron never absorbs either); open pavement
keeps the slice model (taxi centrelines, free routes, the proximity
contour).

The verdict per source, with the numbers recorded (``SourceRecord``):

* ``strip`` — carries a road centreline (a 1206 route or an OSM road
  that is not a parking aisle) and touches NO taxi centreline, and
  either is at most ``lot.narrow_road_width_m`` wide (the pavement IS
  the road) or is at most ``service.free_max_width_m`` wide with at
  least ``lot.through_min_fraction`` of its half-perimeter covered by
  road running THROUGH it (each end on its boundary or at a junction
  inside) and at most ``lot.max_road_pieces_per_100m`` merged road
  pieces per 100 m of half-perimeter (one road, not an aisle grid —
  measured CYXY: strips 0.2-1.5, lots 2.9-4.6);
* ``lot`` — not a strip, touches no taxi centreline, holds no startup,
  is not an apron by name (apt.dat description) or by OSM
  ``aeroway=apron`` cover, and carries an OSM road or parking aisle
  (car evidence: a 1206 truck route alone serves aircraft on an apron
  and never makes a lot) or is covered by OSM ``amenity=parking``;
* ``open`` — everything else.
"""
from __future__ import annotations

import dataclasses as _dc
import typing as _t

from shapely.geometry import LineString, Point, Polygon
from shapely.ops import linemerge, unary_union
from shapely.strtree import STRtree

from ..model.airport import Airport
from .evidence import Evidence, polygon_parts
from .rules import Rules

__all__ = ["SourceRecord", "classify_sources"]

_BOUNDARY_TOL_M = 0.5


@_dc.dataclass(frozen=True)
class SourceRecord:
    """One source pavement polygon and the evidence read off it."""

    id: str
    description: str
    area_m2: float
    width_m: float          # area / half-perimeter (robust to L-shapes)
    road_m: float           # 1206 + OSM road centreline length inside
    osm_road_m: float       # ...the OSM part of it
    through_m: float        # road length in pieces entering AND leaving
    dead_ends: int          # road ends inside, on no boundary and no junction
    road_pieces: int        # merged road pieces inside (an aisle grid has many)
    aisle_m: float          # OSM service=parking_aisle length inside
    taxi_m: float           # taxi centreline length on/inside it
    startups: int           # 1300 startups inside
    parking_cover: float    # fraction under OSM amenity=parking
    apron_cover: float      # fraction under OSM aeroway=apron
    cls: str                # strip | lot | open
    reason: str

    def as_evidence(self) -> dict[str, float | str]:
        return {"source": self.id, "source_class": self.cls,
                "source_reason": self.reason, "source_width_m": self.width_m,
                "source_road_m": self.road_m, "source_taxi_m": self.taxi_m}


def classify_sources(airport: Airport, ev: Evidence, rules: Rules
                     ) -> tuple[list[SourceRecord], dict[str, Polygon]]:
    """Every source polygon's record, and the polygons of the strips and
    lots (the ones whose boundary cuts)."""
    roads = [c.line for c in ev.truck_chains] + \
        [c.line for c in ev.road_chains if not c.aisle]
    osm_roads = [c.line for c in ev.road_chains if not c.aisle]
    aisles = [c.line for c in ev.road_chains if c.aisle]
    taxis = [c.line for c in ev.taxi_chains]
    road_tree = STRtree(roads) if roads else None
    osm_tree = STRtree(osm_roads) if osm_roads else None
    aisle_tree = STRtree(aisles) if aisles else None
    taxi_tree = STRtree(taxis) if taxis else None
    starts = [Point(s.xy) for s in airport.startups]
    start_tree = STRtree(starts) if starts else None
    parking = unary_union([p for _i, p in ev.parking_polys]) if ev.parking_polys \
        else Polygon()
    aprons = [_polygon(w.points) for w in airport.osm_ways
              if w.closed and w.tags.get("aeroway") == "apron"]
    apron_u = unary_union([a for a in aprons if a is not None]) if aprons else Polygon()
    desc = {p.id: p.description for p in airport.pavements}
    out: list[SourceRecord] = []
    cut: dict[str, Polygon] = {}
    for sid, poly in ev.pavement_polys:
        rec = _record(sid, desc.get(sid, ""), poly, road_tree, roads, osm_tree,
                      osm_roads, aisle_tree, aisles, taxi_tree, taxis, start_tree,
                      parking, apron_u, rules)
        out.append(rec)
        if rec.cls in ("strip", "lot"):
            cut[sid] = poly
    return out, cut


def _polygon(points: _t.Sequence[tuple[float, float]]) -> Polygon | None:
    if len(points) < 4:
        return None
    p = Polygon(points)
    if not p.is_valid:
        p = p.buffer(0)
    parts = polygon_parts(p)
    return max(parts, key=lambda g: g.area) if parts else None


def _inside_length(poly: Polygon, tree: STRtree | None, lines) -> list[LineString]:
    if tree is None:
        return []
    hits = [lines[int(j)].intersection(poly) for j in tree.query(poly, predicate="intersects")]
    out: list[LineString] = []
    for g in hits:
        if g.is_empty:
            continue
        for part in (g.geoms if hasattr(g, "geoms") else [g]):
            if part.geom_type == "LineString" and part.length > 0:
                out.append(part)
    return out


def _through_length(poly: Polygon, road_parts: list[LineString]
                    ) -> tuple[float, int, int]:
    """``(through_m, dead_ends, pieces)``: road length in pieces whose
    BOTH ends are connected — on the polygon boundary or at a junction
    with another road piece inside (a route branching inside a ring road
    is still through) — the count of ends connected to nothing, and the
    number of merged pieces (an aisle grid is many pieces)."""
    if not road_parts:
        return 0.0, 0, 0
    u = unary_union(road_parts)
    merged = u if u.geom_type == "LineString" else linemerge(u)
    parts = [g for g in (merged.geoms if hasattr(merged, "geoms") else [merged])
             if g.geom_type == "LineString"]
    ends = [(Point(g.coords[0]), Point(g.coords[-1])) for g in parts]
    boundary = poly.boundary
    total = 0.0
    dead = 0
    for k, g in enumerate(parts):
        ok = True
        for pt in ends[k]:
            if boundary.distance(pt) <= _BOUNDARY_TOL_M:
                continue
            if any(j != k and (ends[j][0].distance(pt) <= _BOUNDARY_TOL_M
                               or ends[j][1].distance(pt) <= _BOUNDARY_TOL_M
                               or parts[j].distance(pt) <= _BOUNDARY_TOL_M)
                   for j in range(len(parts))):
                continue
            ok = False
            dead += 1
        if ok:
            total += g.length
    return total, dead, len(parts)


def _record(sid: str, description: str, poly: Polygon, road_tree, roads,
            osm_tree, osm_roads, aisle_tree, aisles, taxi_tree, taxis,
            start_tree, parking, apron_u, rules: Rules) -> SourceRecord:
    half_perim = max(poly.length / 2.0, 1e-6)
    width = poly.area / half_perim
    road_parts = _inside_length(poly, road_tree, roads)
    road_m = sum(p.length for p in road_parts)
    osm_m = sum(p.length for p in _inside_length(poly, osm_tree, osm_roads))
    aisle_m = sum(p.length for p in _inside_length(poly, aisle_tree, aisles))
    taxi_m = sum(p.length for p in _inside_length(
        poly.buffer(rules.cells.on_tol_m), taxi_tree, taxis))
    starts = len(start_tree.query(poly, predicate="contains")) if start_tree else 0
    pcov = poly.intersection(parking).area / poly.area if not parking.is_empty else 0.0
    acov = poly.intersection(apron_u).area / poly.area if not apron_u.is_empty else 0.0
    through, dead_ends, pieces = _through_length(poly, road_parts)
    lot = rules.lot
    no_taxi = taxi_m < rules.cells.min_shared_m
    carries = road_m >= lot.min_road_fraction * half_perim
    carries_osm = (osm_m + aisle_m) >= lot.min_road_fraction * half_perim
    cls, reason = "open", "no road; or taxi/startup/apron evidence"
    if carries and no_taxi:
        if width <= lot.narrow_road_width_m:
            cls, reason = "strip", f"width {width:.1f} m <= narrow {lot.narrow_road_width_m:g}, road {road_m:.0f} m"
        elif width <= rules.service.free_max_width_m and \
                through >= lot.through_min_fraction * half_perim and \
                pieces * 100.0 / half_perim <= lot.max_road_pieces_per_100m:
            cls, reason = "strip", (f"width {width:.1f} m, through {through:.0f} m >= "
                                    f"{lot.through_min_fraction:g} x {half_perim:.0f} m, "
                                    f"{pieces} road piece(s)")
    if cls == "open" and no_taxi and starts == 0 and \
            acov < lot.parking_cover_fraction and "apron" not in description.lower():
        if pcov >= lot.parking_cover_fraction:
            cls, reason = "lot", f"amenity=parking covers {pcov:.0%}"
        elif aisle_m > 0.0 and carries_osm:
            cls, reason = "lot", f"OSM parking aisle {aisle_m:.0f} m inside"
        elif carries_osm:
            cls, reason = "lot", (f"OSM road {osm_m:.0f} m inside ({pieces} pieces), no "
                                  f"taxi centreline, no startup, width {width:.1f} m")
    return SourceRecord(sid, description, poly.area, width, road_m, osm_m, through,
                        dead_ends, pieces, aisle_m, taxi_m, starts, pcov, acov,
                        cls, reason)
