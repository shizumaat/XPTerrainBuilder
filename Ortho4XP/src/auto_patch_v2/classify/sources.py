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
  ``aeroway=apron`` cover, and carries an OSM road or parking aisle,
  or is covered by OSM ``amenity=parking``, or is REACHED by a road —
  a 1206 route or an OSM road entering it or ending at its boundary
  (RULINGS 2026-09-04u: a route reaching a page is road evidence for
  it; CYXY dsf:pol17 read "road 0 m" while route 50 ended at its
  boundary — supersedes 04j's "a 1206 route alone never makes a lot");
* ``open`` — everything else, including a source whose description
  NAMES A TAXIWAY (RULINGS 2026-09-04z(1), ``evidence.taxi_name_match``):
  taxi evidence stands in for the centreline it lacks, so the page is
  never a strip or a lot (the scorer reads it taxi family).
"""
from __future__ import annotations

import dataclasses as _dc
import typing as _t

from shapely.geometry import LineString, Point, Polygon
from shapely.ops import linemerge, unary_union
from shapely.strtree import STRtree

from ..model.airport import Airport
from .evidence import Evidence, apron_named, polygon_parts, taxi_name_match
from .rules import Rules

__all__ = ["SourceRecord", "classify_sources", "apron_union",
           "object_body_cuts", "OBJECT_PAVEMENT_PREFIX", "ENCLOSED_MIN_FRAC"]

#: the source-id prefix ``airport/load.py`` gives a §42 object-pavement body
OBJECT_PAVEMENT_PREFIX = "dsf:objpav"

#: §41 (1) (owner RULINGS 2026-09-13co item 2): the fraction of its OWN
#: area a pavement region must have inside another's EXTERIOR RING to be
#: that one's rather than its own.  ONE definition, read by both halves of
#: the rule — ``planar/overlay.absorb_enclosed_pavement`` applies it to
#: FACES, ``object_body_cuts`` below to a §42 object body before the slice
#: (RULINGS 2026-09-13dc).  It lives at the earlier stage because ``planar``
#: may import ``classify`` and never the other way (the layering twin,
#: ``tests/auto_patch_v2/test_model.py::test_dependency_direction``).
ENCLOSED_MIN_FRAC = 0.95

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
    road_reach: int         # road centrelines REACHING it: entering, or an end within on_tol_m of the boundary (04u)
    aisle_m: float          # OSM service=parking_aisle length inside
    taxi_m: float           # taxi centreline length on/inside it
    startups: int           # 1300 startups inside
    parking_cover: float    # fraction under OSM amenity=parking
    apron_cover: float      # fraction under OSM aeroway=apron
    cls: str                # strip | lot | open
    reason: str
    taxi_name: str = ""     # the description's taxiway token (04z-1), "" when it names none
    taxi_designator: str = ""  # ...and the designator after it ("Taxiway B" -> "B")

    def as_evidence(self) -> dict[str, float | str]:
        out: dict[str, float | str] = {
            "source": self.id, "source_class": self.cls,
            "source_reason": self.reason, "source_width_m": self.width_m,
            "source_road_m": self.road_m, "source_taxi_m": self.taxi_m,
            "source_road_reach": float(self.road_reach)}
        if self.taxi_name:
            out["source_taxi_name"] = self.taxi_name
        return out


def apron_union(airport: Airport):
    """The OSM ``aeroway=apron`` polygons of the airport, as one geometry.

    THE ONE READING of mapped apron (RULINGS 2026-09-04u / 09-11ac item 6,
    §40 (2)): the LOT rung reads its cover over a SOURCE POLYGON, §40 (2)
    over a CELL, and both must mean the same thing by "apron is drawn
    here" — a second spelling of the selection is a second answer.
    Unclosed ways are not areas and never count."""
    aprons = [_polygon(w.points) for w in airport.osm_ways
              if w.closed and w.tags.get("aeroway") == "apron"]
    aprons = [a for a in aprons if a is not None]
    return unary_union(aprons) if aprons else Polygon()


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
    apron_u = apron_union(airport)
    desc = {p.id: p.description for p in airport.pavements}
    out: list[SourceRecord] = []
    cut: dict[str, Polygon] = {}
    for sid, poly in ev.pavement_polys:
        # A REMAINDER KEEPS ITS PAGE'S DESCRIPTION.  A source overlapping
        # apt.dat pavement is admitted as its remainder pieces (``<id>#k``,
        # ``evidence._dsf_pavements``); the description is the PAGE's, so
        # the lookup strips the ``#k`` here — the ONE site.  Ruled for
        # ``dsf:objpav`` remainders by §42 (3) (RULINGS 2026-09-13cv: the
        # draped OBJ8 a cell was born of); the same gap on ``.pol``
        # remainders (RULINGS 2026-09-13dc chip) classified every piece
        # with an EMPTY description — no ``[lot] apron_name_tokens`` match,
        # no taxi name — and is repaired by lane polremainder, its
        # KCLT/LEMD evidence shift measured dry in that lane's report.
        base = sid.split("#", 1)[0]
        rec = _record(sid, desc.get(sid) or desc.get(base, ""),
                      poly, road_tree, roads, osm_tree,
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
    reach = _road_reach(poly, road_tree, roads, rules.cells.on_tol_m)
    lot = rules.lot
    named = taxi_name_match(description, rules)
    tok, desig = named if named else ("", "")
    no_taxi = taxi_m < rules.cells.min_shared_m and named is None
    carries = road_m >= lot.min_road_fraction * half_perim
    carries_osm = (osm_m + aisle_m) >= lot.min_road_fraction * half_perim
    # §37 (5) A PAGE TOO NARROW TO PARK ON IS NOT A CAR PARK (owner
    # RULINGS 2026-09-13j item 7 / 13ab; ``lot.min_lot_width_m``).  A
    # 90-degree car park's minimum module is one 5.0 m stall row plus one
    # 6.0 m one-way aisle; a page narrower than that holds no parking at
    # all, so the two WEAKEST rungs of the lot ladder below — which read
    # only that roads reach or touch the page — must not mint one.
    # ...and the floor: BELOW one service-road corridor the page is an
    # EMIT SLIVER, not a narrow surface (LEMD's ``dsf:pol255#2`` family,
    # 0.1-0.3 m across on a 200-800 m perimeter).  Measured before it
    # shipped: without the floor 26 LEMD slivers stopped being minted
    # ``parking_lot`` and LEMD's cell count moved 597 -> 578 for no
    # reason connected to §37 (5).  §27 already owns the sliver class
    # (``_LOT_SLIVER_RADIUS_M``); this rule leaves it alone.  KCLT's
    # twelve are 6.7-10.3 m and unaffected by the floor.
    too_narrow_for_lot = (rules.service.road_width_m <= width
                          <= lot.min_lot_width_m)
    cls, reason = "open", "no road; or taxi/startup/apron evidence"
    if named is not None and taxi_m < rules.cells.min_shared_m:
        reason = (f"taxi by name {tok!r}" + (f" ({desig})" if desig else "")
                  + " (04z-1), no taxi centreline")
    if carries and no_taxi:
        if width <= lot.narrow_road_width_m:
            cls, reason = "strip", f"width {width:.1f} m <= narrow {lot.narrow_road_width_m:g}, road {road_m:.0f} m"
        elif width <= rules.service.free_max_width_m and \
                through >= lot.through_min_fraction * half_perim and \
                pieces * 100.0 / half_perim <= lot.max_road_pieces_per_100m:
            cls, reason = "strip", (f"width {width:.1f} m, through {through:.0f} m >= "
                                    f"{lot.through_min_fraction:g} x {half_perim:.0f} m, "
                                    f"{pieces} road piece(s)")
    elif no_taxi and too_narrow_for_lot and starts == 0 and \
            road_m >= rules.osm_roads.min_len_m and \
            acov < lot.apron_cover_fraction and not apron_named(description, rules):
        # §37 (5), the other half: the narrow-road rule's own words are
        # "a page at most ``narrow_road_width_m`` wide that carries ANY
        # road centreline IS the road", but the branch above is gated on
        # ``carries`` — ``min_road_fraction`` × HALF-PERIMETER, which on a
        # long ribbon is a length, not a fraction of its width: KCLT's
        # ``dsf:pol82`` needed 120 m of mapped centreline inside its 601 m
        # to qualify and OSM maps 71 m of it (the centreline wanders in
        # and out of an 8.4 m page).  Below the parking floor the gate is
        # the rule's own: a road centreline inside that is not NOISE
        # (``osm_roads.min_len_m``, the feed's own floor), on a page at
        # least one service-road corridor wide (``service.road_width_m``)
        # — LEMD's emit slivers are 0.1-0.3 m across and clip a metre of
        # road each; 34 of them would otherwise have become roads.
        # It carries the LOT
        # ladder's own evidence vetoes — a mapped ``aeroway=apron`` over
        # the page, an apron NAME, a 1300 startup on it — because a
        # surveyed fact outranks a width heuristic in both directions
        # (KCLT ``pav127`` 8.2 m, 100 % apron cover, stays ``open``).
        cls, reason = "strip", (f"width {width:.1f} m <= lot minimum "
                                f"{lot.min_lot_width_m:g} (too narrow to park on, "
                                f"§37 (5)), road {road_m:.0f} m, {reach} road(s) reach it")
    # THE APRON VETO (owner RULINGS 2026-09-11ac item 6): a page with a
    # MAPPED APRON on it is not a car park.  It reads
    # ``lot.apron_cover_fraction`` — the same key ``open_default``'s
    # evidence ladder reads, one physical fact and one threshold — and
    # that threshold is a NOISE FLOOR, not a majority: OSM never draws
    # ``aeroway=apron`` over a car park, and a pack's own pavement page is
    # routinely far larger than any one mapped apron polygon.  Until
    # 2026-09-11 this read ``parking_cover_fraction`` at 0.5 and LEMD's
    # ``pav126`` (the owner's shapeID 83, 25 % apron) shipped a lot.
    if cls == "open" and no_taxi and starts == 0 and \
            acov < lot.apron_cover_fraction and not apron_named(description, rules):
        if pcov >= lot.parking_cover_fraction:
            cls, reason = "lot", f"amenity=parking covers {pcov:.0%}"
        elif aisle_m > 0.0 and carries_osm:
            cls, reason = "lot", f"OSM parking aisle {aisle_m:.0f} m inside"
        elif too_narrow_for_lot:
            # §37 (5): MAPPED parking evidence (the two rungs above — an
            # ``amenity=parking`` polygon, an OSM parking aisle) is a
            # surveyed fact and still wins; the two rungs BELOW read only
            # that roads reach the page, which on a sub-module width is
            # evidence of a ROAD.  A narrow page with no road inside
            # stays ``open``.
            pass
        elif carries_osm:
            cls, reason = "lot", (f"OSM road {osm_m:.0f} m inside ({pieces} pieces), no "
                                  f"taxi centreline, no startup, width {width:.1f} m")
        elif reach > 0:
            cls, reason = "lot", (f"{reach} road(s) reach it (04u), no taxi centreline, "
                                  f"no startup, width {width:.1f} m")
    return SourceRecord(sid, description, poly.area, width, road_m, osm_m, through,
                        dead_ends, pieces, reach, aisle_m, taxi_m, starts, pcov, acov,
                        cls, reason, tok, desig)


def _road_reach(poly: Polygon, tree: STRtree | None, lines, tol: float) -> int:
    """How many road centrelines REACH ``poly`` (RULINGS 2026-09-04u): the
    line enters it (a positive length inside) or one of its ends lies
    within ``tol`` of its boundary."""
    if tree is None:
        return 0
    n = 0
    for j in tree.query(poly.buffer(tol), predicate="intersects"):
        ln = lines[int(j)]
        if ln.intersection(poly).length > 0.0:
            n += 1
        elif any(poly.boundary.distance(Point(c)) <= tol
                 for c in (ln.coords[0], ln.coords[-1])):
            n += 1
    return n


def object_body_cuts(ev: Evidence, region) -> list[LineString]:
    """§42 (2) AS AMENDED (owner RULINGS 2026-09-13dc; Fable's §42
    amendment) — AN ADJACENT OBJECT BODY IS ITS OWN FACE.

    THE DEFECT this repairs is round 1's own measurement.  The slice runs
    over ``ev.pavement_union`` and cuts it only along centrelines and the
    strip/lot boundaries, so a §42 body merely TOUCHING a mapped page
    dissolved into it: at HECA ``apron:pav132`` came out as ONE face of
    2,687 nodes spanning 63.85-154.79 m of DEM (HECA has ~85 m of real
    relief), off-DEM to 11.73 m and joint steps to 5.38 m — a surface no
    apron cap can hold, and classification lost rather than gained.

    So an object-pavement body CUTS AT ITS OWN BOUNDARY, exactly as a
    strip or a lot does (owner 2026-09-04j, the mouth cut) — but it is NOT
    a strip or a lot: it enters ``_source_for``'s dictionary nowhere, so
    the face it bounds is kinded by the ordinary evidence ladder
    (apron / lot / corridor) and welded to its neighbour at the seam under
    the ordinary shape-joint and no-step laws, each face inside its own
    cap.

    THE ONE EXCEPTION IS §41 (1), and it is the SAME TEST the planar pass
    applies to faces (``planar/overlay.absorb_enclosed_pavement``, which
    re-exports ``ENCLOSED_MIN_FRAC`` from here): a body at least that
    fraction of whose area lies inside a mapped page's EXTERIOR RING is
    that page's — it is not cut here, it unions into the page, and there
    is no boundary between them for a step to stand on.  One constant, so
    the two halves of §41 (1) cannot drift apart.
    """
    bodies = [(sid, g) for sid, g in ev.pavement_polys
              if sid.startswith(OBJECT_PAVEMENT_PREFIX)]
    if not bodies:
        return []
    # the MAPPED pages' exterior rings (apt.dat 110 polygons and `.pol`
    # pages), holes filled: §41 (1) reads the ring, never the solid
    frames = [Polygon(g.exterior) for sid, g in ev.pavement_polys
              if not sid.startswith(OBJECT_PAVEMENT_PREFIX) and g.area > 0.0]
    tree = STRtree(frames) if frames else None
    gate = region.buffer(0.01)
    out: list[LineString] = []
    for _sid, body in bodies:
        if tree is not None and body.area > 0.0 and any(
                frames[int(j)].intersection(body).area
                >= ENCLOSED_MIN_FRAC * body.area
                for j in tree.query(body, predicate="intersects")):
            continue                       # §41 (1): the page's, not its own
        for ring in [body.exterior, *body.interiors]:
            g = LineString(ring.coords).intersection(gate)
            out += [q for q in ([g] if g.geom_type == "LineString"
                                else list(getattr(g, "geoms", ())))
                    if q.geom_type == "LineString" and q.length > 0.0]
    return out
