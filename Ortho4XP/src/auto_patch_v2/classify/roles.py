"""ONE scorer, ONE output: a ``Role`` per pavement cell (plan §1 row 2).

The pavement union (less runways and pads) is cut by the taxi
centrelines, the ground-vehicle routes and the apron route-proximity
contour into CELLS; each cell is scored from what touches it:

* touches taxi centrelines, narrow (area / shared edge <= corridor width)
  -> a CORRIDOR, named by its axis' geometry against the runways
  (``primary_parallel`` / ``secondary_parallel`` / ``stub`` /
  ``cross_connector``);
* touches taxi centrelines, small or route territory -> ``junction``;
* touches ground routes only -> ``service_junction`` (user 2026-07-02);
* touches nothing, or open pavement beyond route reach -> ``apron``,
  unless it lies within the route-proximity contour of a taxi centreline
  or runway, where it is ``junction`` (user 2026-07-06: "less than 50 m
  from a centreline or runway is NOT apron");
* an apron/taxi cell with no touch-chain to a runway is
  ``groundside_pavement`` when the airport has a terminal (user
  2026-06-09 / 2026-06-11).

Owner 2026-09-04j (``sources.py``): a source polygon read as a road
STRIP is its own face and a road (``service_road``); one read as a
parking LOT is its own face and ``parking_lot``; both are cut from
their neighbours at their own boundary (the mouth), so an apron never
absorbs groundside pavement.  A demoted (landside) cell with road
evidence is a ``parking_lot``; one with none stays
``groundside_pavement``.  Pavement a network taxiway runs onto is
airside even without a pavement touch-chain (item 4).

Runway slabs are ``runway``; their pairwise overlaps ``runway_crossing``;
ground-route corridors outside pavement ``service_road``; building
footprints ``building`` (pads yield to their apron — RULINGS
2026-09-03h — a constraint the M2 pad generator writes, not a role).
Every role is the ``precedence.toml`` register; thresholds are
``rules.toml``.
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
from ..law.tables import is_value_role, role_side
from ..model.airport import Airport
from ..model.frame import XY
from .evidence import Chain, Evidence, build_evidence, polygon_parts
from .rules import Rules, load_rules
from .sources import SourceRecord, classify_sources

__all__ = ["Cell", "CutLine", "Classification", "classify"]

_LETTERS = "ABCDEF"
TAXI_FAMILY = ("primary_parallel", "secondary_parallel", "stub",
               "cross_connector", "junction")


@_dc.dataclass(frozen=True)
class Cell:
    """One scored region: ``ring``/``holes`` in the frame (unclosed),
    ``kind`` the slice kind the role came from, ``evidence`` the numbers
    the verdict used (for the report, never re-read downstream)."""

    id: int
    role: str
    ref: str
    ring: tuple[XY, ...]
    holes: tuple[tuple[XY, ...], ...]
    code_number: int | None
    code_letter: str | None
    side: str
    kind: str
    evidence: _t.Mapping[str, float | str]


@_dc.dataclass(frozen=True)
class CutLine:
    """A centreline the slice cut with — the planar map's breakline
    source (``taxi_centerline`` / ``road_centerline``)."""

    kind: str
    ref: str
    points: tuple[XY, ...]


@_dc.dataclass(frozen=True)
class Classification:
    """The scorer's output."""

    cells: tuple[Cell, ...]
    cut_lines: tuple[CutLine, ...]
    stats: _t.Mapping[str, int | float]
    notes: tuple[str, ...]
    #: Rings NO region may claim (M4): the unowned gap round a tunnel ramp
    #: and the structure footprints — the zone regions stop at the wall
    #: (RULINGS 2026-09-01c: the triangulated gap IS the face).
    keepouts: tuple[tuple[XY, ...], ...] = ()
    #: Every source pavement polygon's evidence record (``sources.py``).
    sources: tuple[SourceRecord, ...] = ()


def classify(airport: Airport, law: Law, rules: Rules | None = None
             ) -> Classification:
    """Score every pavement cell of ``airport`` under ``law``'s register."""
    rules = rules or load_rules()
    pad_min = law.tables.structures.building_pad.min_area_m2
    ev = build_evidence(airport, rules, pad_min)
    sources, cut_polys = classify_sources(airport, ev, rules)
    src_of = {r.id: r for r in sources}
    cut_ids = list(cut_polys)
    cut_tree = STRtree([cut_polys[i] for i in cut_ids]) if cut_ids else None
    cells: list[Cell] = []
    notes: list[str] = []
    stats: dict[str, int | float] = {}

    def add(role: str, ref: str, poly: Polygon, kind: str,
            code_number: int | None = None, code_letter: str | None = None,
            evidence: _t.Mapping[str, float | str] | None = None) -> None:
        ring = tuple(poly.exterior.coords)[:-1]
        holes = tuple(tuple(h.coords)[:-1] for h in poly.interiors)
        cells.append(Cell(len(cells), role, ref, ring, holes, code_number,
                          code_letter, role_side(law, role), kind,
                          dict(evidence or {})))

    # ── runways and crossings ───────────────────────────────────────
    crossings: list[tuple[str, Polygon, int, str]] = []
    rp = ev.runway_polys
    for i in range(len(rp)):
        for j in range(i + 1, len(rp)):
            x = rp[i][1].intersection(rp[j][1])
            for part in polygon_parts(x):
                code = max(rp[i][0].code_number or 0, rp[j][0].code_number or 0)
                letter = max((rp[i][0].code_letter or "A", rp[j][0].code_letter or "A"),
                             key=_LETTERS.find)
                crossings.append(("+".join(sorted((rp[i][0].id, rp[j][0].id))),
                                  part, code, letter))
    xing_union = unary_union([c[1] for c in crossings]) if crossings else Polygon()
    for rw, poly in rp:
        body = poly.difference(xing_union) if not xing_union.is_empty else poly
        for part in polygon_parts(body):
            add("runway", rw.id, part, "runway", rw.code_number, rw.code_letter)
    for ref, part, code, letter in crossings:
        add("runway_crossing", ref, part, "runway_crossing", code, letter)

    # ── the slice ───────────────────────────────────────────────────
    region = ev.pavement_union
    if not ev.runway_union.is_empty:
        region = region.difference(ev.runway_union)
    if not ev.pad_union.is_empty:
        region = region.difference(ev.pad_union)
    taxi_parts, truck_parts, prox, spurs, src_cuts = _cut_lines(
        ev, region, rules, cut_polys)
    faces = _slice(region, taxi_parts, truck_parts, spurs + src_cuts, rules)
    stats["slice_faces"] = len(faces)
    stats["keyhole_spurs"] = len(spurs)
    stats["source_strips"] = sum(1 for r in sources if r.cls == "strip")
    stats["source_lots"] = sum(1 for r in sources if r.cls == "lot")

    taxi_tree = STRtree([ln for ln, _c in taxi_parts]) if taxi_parts else None
    truck_tree = STRtree([ln for ln, _c in truck_parts]) if truck_parts else None
    pav_tree = STRtree([g for _i, g in ev.pavement_polys])
    starts = [Point(st.xy) for st in airport.startups]
    start_tree = STRtree(starts) if starts else None
    scored: list[tuple[Polygon, str, str, str | None, dict, bool]] = []
    for face in faces:
        src = _source_for(face, cut_tree, cut_ids, cut_polys, src_of)
        if src is not None:
            # A STRIP is the road, a LOT the lot (owner 2026-09-04j): its
            # own face, cut at its boundary, no chain question to ask.
            evid = {"area_m2": face.area, "n_taxi": 0, "kind": src.cls}
            evid.update(src.as_evidence())
            role = "service_road" if src.cls == "strip" else "parking_lot"
            scored.append((face, role, src.id, None, evid, False))
            continue
        taxi = _touching(face, taxi_tree, taxi_parts, rules)
        truck = _touching(face, truck_tree, truck_parts, rules)
        net = any(c.runway_network for c in taxi)
        ref = _ref_for(face, pav_tree, ev)
        kind, axis, evid = _kind(face, taxi, rules, _apron_named(src_of.get(ref), rules))
        if kind == "apron" and not taxi and truck and not _holds_startup(face, start_tree):
            kind = "service"           # a stand (1300) makes it apron, not service territory
        if kind == "service":
            role = "service_junction"
        elif kind == "corridor" and axis is not None:
            role = _subrole(axis, ev, rules)
        elif kind == "junction":
            role = "junction"
        else:
            role = "apron"
        letter = None
        if role in TAXI_FAMILY:
            ls = [c.letter for c in taxi if c.letter]
            letter = max(ls, key=_LETTERS.find) if ls else None
        if role == "apron" and prox is not None:
            # THE ROUTE-PROXIMITY CUT (user 2026-07-06), after scoring as
            # v1 applies it: the part of an apron within the contour is
            # maneuvering surface (junction); only the rest keeps the
            # apron law.
            for part in polygon_parts(face.intersection(prox)):
                if part.area >= rules.cells.min_area_m2:
                    scored.append((part, "junction", ref, None,
                                   dict(evid, near_route=1.0), net))
            for part in polygon_parts(face.difference(prox)):
                if part.area >= rules.cells.min_area_m2:
                    scored.append((part, "apron", ref, None,
                                   dict(evid, near_route=0.0), net))
            continue
        scored.append((face, role, ref, letter, evid, net))

    # ── groundside: the runway touch-chain ─────────────────────────
    demoted = _groundside(scored, ev, rules)
    stats["groundside_demoted"] = len(demoted)
    if demoted and not ev.terminal_present:
        notes.append("no terminal: landside demotion skipped (user 2026-06-11)")
    road_ev = _road_evidence(scored, ev, rules)
    stats["demoted_lots"] = 0
    for i, (face, role, ref, letter, evid, _net) in enumerate(scored):
        if i in demoted and ev.terminal_present and role in ("apron", *TAXI_FAMILY):
            # landside: a lot when a road reaches it or a road/lot face
            # touches it (the roads-and-lots complex, owner 2026-09-04j),
            # else the paved island it always was
            role = "parking_lot" if i in road_ev else "groundside_pavement"
            evid = dict(evid, demoted=1.0, road_evidence=float(i in road_ev))
            stats["demoted_lots"] += int(role == "parking_lot")
            letter = None
        add(role, ref, face, str(evid.get("kind", "")), None, letter, evid)

    # ── service roads outside pavement, pads ───────────────────────
    corridors = []
    for c in ev.truck_chains:
        corridors.append(c.line.buffer(rules.service.road_width_m / 2,
                                       cap_style="flat", join_style="mitre"))
    if corridors:
        road = unary_union(corridors)
        road = road.difference(ev.pavement_union)
        if not ev.pad_union.is_empty:
            road = road.difference(ev.pad_union)
        if not ev.runway_union.is_empty:
            road = road.difference(ev.runway_union)
        for i, part in enumerate(polygon_parts(road)):
            if part.area >= rules.cells.min_area_m2:
                add("service_road", f"route{i}", part, "service_road")
    for ref, poly in ev.pads:
        add("building", ref, poly, "building")
    stats["pads_dropped"] = ev.dropped_pads
    cells, n_cut = _cut_back_groundside(cells, law, rules)
    stats["mixed_pad_cutbacks"] = n_cut
    stats["taxi_chains"] = len(ev.taxi_chains)
    stats["truck_chains"] = len(ev.truck_chains)
    stats["terminal_present"] = float(ev.terminal_present)

    cut: list[CutLine] = []
    for ln, c in taxi_parts:
        cut.append(CutLine("taxi_centerline", f"taxi{c.id}", tuple(ln.coords)))
    for ln, c in truck_parts:
        cut.append(CutLine("road_centerline", f"route{c.id}", tuple(ln.coords)))
    strips = [cut_polys[i] for i in cut_ids if src_of[i].cls == "strip"]
    if strips:                                     # the road axis inside each strip
        strip_u = unary_union(strips)
        for c in ev.truck_chains + ev.road_chains:
            for ln in _line_parts(c.line.intersection(strip_u)):
                cut.append(CutLine("road_centerline", f"route{c.id}", tuple(ln.coords)))
    for c in ev.truck_chains:                      # the corridor spine outside pavement
        outside = c.line.difference(ev.pavement_union)
        for ln in _line_parts(outside):
            cut.append(CutLine("road_centerline", f"route{c.id}", tuple(ln.coords)))
    return Classification(tuple(cells), tuple(cut), stats, tuple(notes),
                          sources=tuple(sources))


def _source_for(face: Polygon, tree: STRtree | None, ids: list[str],
                polys: _t.Mapping[str, Polygon], src_of) -> SourceRecord | None:
    """The strip/lot source polygon this face lies in (>= half its area)."""
    if tree is None:
        return None
    best, best_a = None, 0.0
    for j in tree.query(face, predicate="intersects"):
        sid = ids[int(j)]
        a = polys[sid].intersection(face).area
        if a > best_a:
            best, best_a = src_of[sid], a
    return best if best is not None and best_a >= 0.5 * face.area else None


def _road_evidence(scored, ev: Evidence, rules: Rules) -> set[int]:
    """Indices of scored faces a road reaches: a road/route centreline
    within ``on_tol_m``, or a strip/lot face touching within touch_tol."""
    tol = rules.cells.on_tol_m
    roads = [c.line for c in ev.truck_chains + ev.road_chains]
    road_tree = STRtree(roads) if roads else None
    rl = [(i, s[0]) for i, s in enumerate(scored) if s[1] in ("service_road", "parking_lot")]
    rl_tree = STRtree([p for _i, p in rl]) if rl else None
    out: set[int] = set()
    for i, s in enumerate(scored):
        face = s[0]
        if road_tree is not None and any(
                roads[int(j)].distance(face) <= tol
                for j in road_tree.query(face.buffer(tol), predicate="intersects")):
            out.add(i)
            continue
        if rl_tree is not None and any(
                rl[int(j)][1].distance(face) <= rules.groundside.touch_tol_m
                for j in rl_tree.query(face.buffer(rules.groundside.touch_tol_m),
                                       predicate="intersects")):
            out.add(i)
    return out


# ── mixed pads ───────────────────────────────────────────────────────────

def _cut_back_groundside(cells: list[Cell], law: Law, rules: Rules
                         ) -> tuple[list[Cell], int]:
    """THE MIXED-PAD RULE (RULINGS 2026-09-01g/i; ``structures.building_pad
    .groundside_cutback_m``): a pad that touches BOTH an airside governed
    surface and groundside pavement welds AIRSIDE — its one flat value is
    its airside contact (03h) — and the groundside pavement is CUT BACK
    from it so the two never share a vertex: the groundside lot keeps its
    own law and follows the DEM, and the terrace in the stand-off is the
    lawful airside/groundside boundary (memory ``groundside-terrace-law``).
    Measured SPJC (M3b): a terminal pad at 24.55 m dragged a groundside
    DSF page 4.8 m below the DEM and minted 14 groundside step rows against
    its DEM-following neighbour.  Returns the cells and the number cut."""
    back = law.tables.structures.building_pad.groundside_cutback_m
    if back <= 0.0:
        return cells, 0
    tol = rules.groundside.touch_tol_m
    pads = [c for c in cells if c.role == "building"]
    if not pads:
        return cells, 0
    airside = [Polygon(c.ring, c.holes) for c in cells
               if c.role != "building" and c.side == "airside"
               and is_value_role(law, c.role)]
    ground_idx = [i for i, c in enumerate(cells)
                  if c.side == "groundside" and is_value_role(law, c.role)]
    if not airside or not ground_idx:
        return cells, 0
    air_tree = STRtree(airside)
    gpolys = [Polygon(cells[i].ring, cells[i].holes) for i in ground_idx]
    g_tree = STRtree(gpolys)
    knives: list[Polygon] = []
    for c in pads:
        poly = Polygon(c.ring, c.holes)
        probe = poly.buffer(tol)
        touches_air = any(airside[int(k)].distance(poly) <= tol
                          for k in air_tree.query(probe, predicate="intersects"))
        touches_ground = any(gpolys[int(k)].distance(poly) <= tol
                             for k in g_tree.query(probe, predicate="intersects"))
        if touches_air and touches_ground:
            knives.append(poly.buffer(back, join_style="mitre", mitre_limit=2.0))
    if not knives:
        return cells, 0
    knife = unary_union(knives)
    out: list[Cell] = []
    n_cut = 0
    for i, c in enumerate(cells):
        if i not in ground_idx:
            out.append(c)
            continue
        poly = Polygon(c.ring, c.holes)
        if not poly.intersects(knife):
            out.append(c)
            continue
        n_cut += 1
        for k, part in enumerate(polygon_parts(poly.difference(knife))):
            if part.area < rules.cells.min_area_m2:
                continue
            ring = tuple(part.exterior.coords)[:-1]
            holes = tuple(tuple(h.coords)[:-1] for h in part.interiors)
            out.append(Cell(len(out), c.role, c.ref if k == 0 else f"{c.ref}#{k}",
                            ring, holes, c.code_number, c.code_letter, c.side,
                            c.kind, dict(c.evidence, mixed_pad_cutback=1.0)))
    # ids are positional
    return [_dc.replace(c, id=i) for i, c in enumerate(out)], n_cut


# ── slice helpers ────────────────────────────────────────────────────────

def _line_parts(geom) -> list[LineString]:
    if geom is None or geom.is_empty:
        return []
    if geom.geom_type == "LineString":
        return [geom]
    return [g for g in getattr(geom, "geoms", ()) if g.geom_type == "LineString"
            and g.length > 0]


def _cut_lines(ev: Evidence, region, rules: Rules,
               cut_polys: _t.Mapping[str, Polygon]):
    """Centreline parts inside the region, the proximity contour, the
    keyhole spurs for interior dead-ends, and the strip/lot source
    boundaries (owner 2026-09-04j: the mouth cut).  A free route part
    inside a strip does not cut again (the strip is one face)."""
    taxi_parts = [(ln, c) for c in ev.taxi_chains
                  for ln in _line_parts(c.line.intersection(region))]
    src_u = unary_union(list(cut_polys.values())) if cut_polys else Polygon()
    src_cuts: list[LineString] = []
    for poly in cut_polys.values():
        for ring in [poly.exterior, *poly.interiors]:
            src_cuts += _line_parts(LineString(ring.coords).intersection(region.buffer(0.01)))
    truck_parts = []
    for c in ev.truck_chains:
        for ln in _free_road_parts(c.line, ev.pavement_union, rules):
            g = ln.intersection(region)
            if not src_u.is_empty:
                g = g.difference(src_u)
            truck_parts += [(q, c) for q in _line_parts(g)]
    src = [c.line.buffer(rules.apron.route_proximity_m, join_style="mitre",
                         mitre_limit=2.0) for c in _through_routes(ev, rules)]
    if not ev.runway_union.is_empty:
        src.append(ev.runway_union.buffer(rules.apron.route_proximity_m,
                                          join_style="mitre", mitre_limit=2.0))
    prox = unary_union(src) if src else None
    spurs = _keyholes([ln for ln, _c in taxi_parts + truck_parts], region, rules)
    return taxi_parts, truck_parts, prox, spurs, src_cuts


def _free_road_parts(line: LineString, pavement_union, rules: Rules
                     ) -> list[LineString]:
    """The sub-segments of a ground route that are COMPLETELY FREE
    (owner ruling 2026-07-27): stations where the pavement cross-section
    is at most ``free_max_width_m`` wide (the pavement IS the road) or
    absent.  A station inside wider pavement is the apron's road and
    never cuts (v1 ``free_road_subsegments``, width-only fallback)."""
    sv = rules.service
    if line.length < sv.sample_step_m:
        return [line]
    half = sv.free_max_width_m
    n = max(2, int(line.length // sv.sample_step_m) + 1)
    ds = [line.length * k / (n - 1) for k in range(n)]
    free: list[bool] = []
    for d in ds:
        p = line.interpolate(d)
        q = line.interpolate(min(line.length, d + 0.5))
        r = line.interpolate(max(0.0, d - 0.5))
        dx, dy = q.x - r.x, q.y - r.y
        L = math.hypot(dx, dy) or 1.0
        nx, ny = -dy / L * half, dx / L * half
        xs = LineString([(p.x - nx, p.y - ny), (p.x + nx, p.y + ny)]
                        ).intersection(pavement_union)
        if xs.is_empty:
            free.append(True)
            continue
        piece = 0.0
        for g in (xs.geoms if hasattr(xs, "geoms") else [xs]):
            if g.geom_type == "LineString" and g.distance(p) < 0.6:
                piece = max(piece, g.length)
        free.append(piece < 2 * half - 1e-6 and piece <= sv.free_max_width_m)
    out: list[LineString] = []
    k = 0
    while k < n:
        if not free[k]:
            k += 1
            continue
        j = k
        while j + 1 < n and free[j + 1]:
            j += 1
        a, b = ds[k], ds[j]
        if b - a >= sv.min_run_m:
            out.append(shapely.ops.substring(line, a, b))
        k = j + 1
    return out


def _through_routes(ev: Evidence, rules: Rules) -> list[Chain]:
    """Routes that count for the proximity cut: each end joins another
    route or the runway within ``through_join_tol_m``, or the route is
    at least ``through_min_len_m`` long (gate lead-ins never qualify)."""
    ap = rules.apron
    lines = [c.line for c in ev.taxi_chains]
    tree = STRtree(lines) if lines else None
    out: list[Chain] = []
    for i, c in enumerate(ev.taxi_chains):
        if c.line.length >= ap.through_min_len_m:
            out.append(c)
            continue
        through = True
        for pt in (Point(c.line.coords[0]), Point(c.line.coords[-1])):
            joined = (not ev.runway_union.is_empty
                      and ev.runway_union.distance(pt) <= ap.through_join_tol_m)
            if not joined and tree is not None:
                joined = any(lines[int(j)].distance(pt) <= ap.through_join_tol_m
                             for j in tree.query(pt.buffer(ap.through_join_tol_m))
                             if int(j) != i)
            if not joined:
                through = False
                break
        if through:
            out.append(c)
    return out


def _keyholes(lines: list[LineString], region, rules: Rules) -> list[LineString]:
    """A centreline that ends INSIDE the pavement is a dangling cut that
    polygonize drops; spur it to the nearest boundary (v1 keyhole)."""
    if not lines:
        return []
    tree = STRtree(lines)
    boundary = region.boundary
    kh = rules.keyhole
    out: list[LineString] = []
    for i, ln in enumerate(lines):
        for pt in (Point(ln.coords[0]), Point(ln.coords[-1])):
            near = [int(j) for j in tree.query(pt.buffer(kh.join_tol_m))
                    if int(j) != i]
            if any(lines[j].distance(pt) <= kh.join_tol_m for j in near):
                continue
            d = boundary.distance(pt)
            if d <= kh.deadend_boundary_tol_m or d > kh.max_spur_m:
                continue
            q = shapely.ops.nearest_points(pt, boundary)[1]
            out.append(LineString([pt, q]))
    return out


def _slice(region, taxi_parts, truck_parts, spurs, rules: Rules
           ) -> list[Polygon]:
    """Polygonize the region boundary + cuts; keep the pieces on pavement."""
    lines = _line_parts(region.boundary) if region.geom_type != "MultiPolygon" \
        else [ln for g in region.geoms for ln in _line_parts(g.boundary)]
    lines += [ln for ln, _c in taxi_parts] + [ln for ln, _c in truck_parts] + spurs
    # Node in FULL precision first (a contour endpoint lies on a boundary
    # segment's interior; snapping the lines separately opens a gap the
    # hot-pixel snap-round cannot close), then snap the ONE noded
    # geometry to the grid.
    grid = rules.cells.snap_grid_m
    noded = shapely.unary_union(unary_union(lines), grid_size=grid)
    prep = shapely.prepared.prep(shapely.set_precision(region, grid))
    out = []
    for poly in polygon_parts(shapely.polygonize([noded])):
        if poly.area < rules.cells.min_area_m2:
            continue
        if prep.contains(poly.representative_point()):
            out.append(poly)
    return out


def _touching(face: Polygon, tree: STRtree | None, parts, rules: Rules
              ) -> list[Chain]:
    """Chains whose line runs along the face boundary (>= min_shared_m
    within on_tol_m); one entry per chain."""
    if tree is None:
        return []
    ext = face.exterior
    seen: dict[int, Chain] = {}
    for j in tree.query(face.buffer(rules.cells.on_tol_m)):
        ln, chain = parts[j]
        if chain.id in seen:
            continue
        if ext.intersection(ln.buffer(rules.cells.on_tol_m, cap_style="flat")
                            ).length >= rules.cells.min_shared_m:
            seen[chain.id] = chain
    return list(seen.values())


def _holds_startup(face: Polygon, tree: STRtree | None) -> bool:
    return tree is not None and len(tree.query(face, predicate="contains")) > 0


def _apron_named(src: SourceRecord | None, rules: Rules) -> bool:
    """The face's source is an APRON by the author's own word (apt.dat
    110 description, ``lot.apron_name_tokens``) or by OSM
    ``aeroway=apron`` cover: its stand lanes are apron, never corridors
    (RULINGS 2026-09-03j; owner 2026-09-04j item 3, CYXY pav17)."""
    if src is None:
        return False
    d = src.description.lower()
    return any(t in d for t in rules.lot.apron_name_tokens) or \
        src.apron_cover >= rules.lot.parking_cover_fraction


def _kind(face: Polygon, taxi: list[Chain], rules: Rules, apron_named: bool = False
          ) -> tuple[str, Chain | None, dict]:
    """v1 ``classify_faces``: corridor / junction / apron from spine
    topology, with the numbers recorded."""
    evid: dict[str, float | str] = {"area_m2": face.area, "n_taxi": len(taxi)}
    if not taxi:
        evid["kind"] = "apron"
        return "apron", None, evid
    if apron_named:
        evid["kind"] = "apron"
        evid["apron_named"] = 1.0
        return "apron", None, evid
    buf = unary_union([c.line.buffer(rules.cells.on_tol_m, cap_style="flat")
                       for c in taxi])
    shared = face.exterior.intersection(buf).length
    width = face.area / shared if shared > 1.0 else float("inf")
    evid["shared_m"] = shared
    evid["width_m"] = width
    if width <= rules.corridor.max_width_m:
        evid["kind"] = "corridor"
        return "corridor", max(taxi, key=lambda c: c.line.length), evid
    if face.area <= rules.junction.max_area_m2:
        evid["kind"] = "junction"
        return "junction", None, evid
    reach = unary_union([c.line.buffer(rules.junction.route_territory_half_width_m)
                         for c in taxi])
    frac = face.intersection(reach).area / face.area
    evid["route_territory_frac"] = frac
    if frac >= rules.junction.route_territory_min_fraction:
        evid["kind"] = "junction"
        return "junction", None, evid
    evid["kind"] = "apron"
    return "apron", None, evid


def _subrole(axis: Chain, ev: Evidence, rules: Rules) -> str:
    """Corridor sub-role from the axis' geometry against the runways."""
    ts = rules.taxi_subrole
    (ax, ay), (bx, by) = axis.line.coords[0], axis.line.coords[-1]
    L = math.hypot(bx - ax, by - ay)
    if L < 1e-6:
        return "cross_connector"
    bearing = math.degrees(math.atan2(by - ay, bx - ax)) % 180.0
    best_offset = None
    for rw, _poly in ev.runway_polys:
        (rx, ry), (sx, sy) = rw.ends[0].xy, rw.ends[1].xy
        rl = math.hypot(sx - rx, sy - ry)
        if rl < 1e-6:
            continue
        rb = math.degrees(math.atan2(sy - ry, sx - rx)) % 180.0
        diff = min(abs(bearing - rb), 180.0 - abs(bearing - rb))
        if diff > ts.parallel_max_angle_deg:
            continue
        ux, uy = (sx - rx) / rl, (sy - ry) / rl
        ta = (ax - rx) * ux + (ay - ry) * uy
        tb = (bx - rx) * ux + (by - ry) * uy
        lo, hi = max(min(ta, tb), 0.0), min(max(ta, tb), rl)
        if hi - lo < ts.parallel_min_overlap_frac * L:
            continue
        mid = Point((ax + bx) / 2, (ay + by) / 2)
        off = LineString([(rx, ry), (sx, sy)]).distance(mid)
        best_offset = off if best_offset is None else min(best_offset, off)
    if best_offset is not None:
        return "primary_parallel" if best_offset <= ts.primary_max_offset_m \
            else "secondary_parallel"
    touch = any(axis.runway_contact) or (
        not ev.runway_union.is_empty and (
            ev.runway_union.distance(Point(ax, ay)) <= ts.runway_touch_m
            or ev.runway_union.distance(Point(bx, by)) <= ts.runway_touch_m))
    return "stub" if touch else "cross_connector"


def _ref_for(face: Polygon, pav_tree: STRtree, ev: Evidence) -> str:
    """The source pavement with the largest overlap."""
    best, best_a = "", 0.0
    for j in pav_tree.query(face, predicate="intersects"):
        a = ev.pavement_polys[j][1].intersection(face).area
        if a > best_a:
            best, best_a = ev.pavement_polys[j][0], a
    return best


def _groundside(scored, ev: Evidence, rules: Rules) -> set[int]:
    """Indices of apron/taxi cells with NO touch-chain to a runway."""
    idx = [i for i, s in enumerate(scored) if s[1] in ("apron", *TAXI_FAMILY)]
    if not idx:
        return set()
    polys = [scored[i][0] for i in idx]
    tree = STRtree(polys)
    tol = rules.groundside.touch_tol_m
    reached: set[int] = set()
    queue: list[int] = []
    for k, p in enumerate(polys):
        # seeds: touches a runway, or a NETWORK taxiway runs onto it
        # (owner 2026-09-04j item 4: CYXY pol19)
        if scored[idx[k]][5] or (not ev.runway_union.is_empty
                                 and p.distance(ev.runway_union) <= tol):
            reached.add(k)
            queue.append(k)
    while queue:
        k = queue.pop()
        for j in tree.query(polys[k].buffer(tol), predicate="intersects"):
            j = int(j)
            if j in reached:
                continue
            if polys[k].distance(polys[j]) <= tol:
                reached.add(j)
                queue.append(j)
    return {idx[k] for k in range(len(polys)) if k not in reached}
