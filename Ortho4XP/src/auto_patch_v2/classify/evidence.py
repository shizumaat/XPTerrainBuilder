"""Classification EVIDENCE — the geometry the scorer reads (plan §1 row
2: apt.dat surface + taxi network + OSM/DSF footprints).

Everything here is derived once from the :class:`Airport`; the scorer
(``roles.py``) never touches a source record.  shapely lives in this
package and ``planar/`` only.
"""
from __future__ import annotations

import dataclasses as _dc
import math
import typing as _t

import shapely
from shapely.geometry import LineString, MultiPolygon, Point, Polygon
from shapely.ops import unary_union

from ..model.airport import Airport, Runway
from ..model.frame import XY
from .rules import Rules

__all__ = ["Chain", "Evidence", "build_evidence", "polygon_from",
           "polygon_parts", "chains_from_edges"]

_LETTERS = "ABCDEF"


@_dc.dataclass
class Chain:
    """A maximal connectivity route of network edges (user 2026-06-29:
    grouped by CONNECTIVITY, never by name): ``letters`` per segment,
    ``runway_contact`` per end (the chain ended at a runway node)."""

    id: int
    line: LineString
    letters: tuple[str | None, ...]
    names: frozenset[str]
    runway_contact: tuple[bool, bool]
    service: bool
    end_degree: tuple[int, int] = (0, 0)
    #: An end node lies in the taxi-network component that reaches a
    #: runway (owner 2026-09-04j item 4: pavement a network taxiway runs
    #: onto is airside even when no pavement touch-chain reaches it).
    runway_network: bool = False
    #: An OSM ``service=parking_aisle`` way: LOT evidence, never a road
    #: a strip is read from (owner 2026-09-04j).
    aisle: bool = False

    @property
    def letter(self) -> str | None:
        """The widest class the chain carries."""
        ls = [l for l in self.letters if l]
        return max(ls, key=_LETTERS.find) if ls else None


@_dc.dataclass
class Evidence:
    """The scorer's inputs."""

    runway_polys: list[tuple[Runway, Polygon]]
    runway_union: Polygon | MultiPolygon
    pavement_polys: list[tuple[str, Polygon]]
    pavement_union: Polygon | MultiPolygon
    taxi_chains: list[Chain]
    truck_chains: list[Chain]
    pads: list[tuple[str, Polygon]]
    pad_union: Polygon | MultiPolygon
    boundary: Polygon | MultiPolygon | None
    terminal_present: bool
    dropped_pads: int
    leadin_chains: list[Chain]
    dsf_pavements_kept: int
    dsf_pavements_dropped: int
    #: OSM ``highway=*`` road centrelines on pavement, deduped against the
    #: 1206 routes (owner 2026-09-04j evidence; ``rules.osm_roads``).
    road_chains: list[Chain] = _dc.field(default_factory=list)
    #: OSM ``amenity=parking`` polygons (``rules.lot.parking_cover_fraction``).
    parking_polys: list[tuple[str, Polygon]] = _dc.field(default_factory=list)


# ── polygons ─────────────────────────────────────────────────────────────

def polygon_from(outer: _t.Sequence[XY], holes: _t.Sequence[_t.Sequence[XY]] = ()
                 ) -> Polygon | None:
    """A VALID polygon from rings (``buffer(0)`` repair; the largest part
    of a self-intersecting source — v1 ``_parse_pavement``)."""
    if len(outer) < 3:
        return None
    try:
        p = Polygon(outer, [h for h in holes if len(h) >= 3])
    except (ValueError, TypeError):
        return None
    if not p.is_valid:
        p = p.buffer(0)
    if p.is_empty:
        return None
    if p.geom_type != "Polygon":
        parts = [g for g in getattr(p, "geoms", ()) if g.geom_type == "Polygon"]
        if not parts:
            return None
        p = max(parts, key=lambda g: g.area)
    return p


def polygon_parts(geom) -> list[Polygon]:
    """The Polygon parts of any geometry (empty -> [])."""
    if geom is None or geom.is_empty:
        return []
    if geom.geom_type == "Polygon":
        return [geom]
    return [g for g in getattr(geom, "geoms", ()) if g.geom_type == "Polygon"
            and not g.is_empty]


def runway_rectangle(rw: Runway) -> Polygon:
    """The runway slab: physical end to physical end (the apt.dat ends
    plus each end's blast pad / overrun), full width (v1 trims 3 m each
    side — a legacy margin v2 does not carry)."""
    (ax, ay), (bx, by) = rw.ends[0].xy, rw.ends[1].xy
    L = math.hypot(bx - ax, by - ay)
    ux, uy = (bx - ax) / L, (by - ay) / L
    ax, ay = ax - ux * rw.ends[0].overrun_m, ay - uy * rw.ends[0].overrun_m
    bx, by = bx + ux * rw.ends[1].overrun_m, by + uy * rw.ends[1].overrun_m
    px, py = -uy * rw.width_m / 2, ux * rw.width_m / 2
    return Polygon([(ax + px, ay + py), (bx + px, by + py),
                    (bx - px, by - py), (ax - px, ay - py)])


# ── network chains ───────────────────────────────────────────────────────

def chains_from_edges(nodes: _t.Mapping[int, XY],
                      edges: _t.Sequence[tuple[int, int, str | None, str]],
                      split_nodes: _t.Collection[int], service: bool,
                      first_id: int = 0) -> list[Chain]:
    """Maximal chains through degree-2 nodes; ``edges`` are
    ``(a, b, letter, name)``; a chain also splits at ``split_nodes``
    (runway contacts, network junctions)."""
    adj: dict[int, list[int]] = {}
    for i, (a, b, _l, _n) in enumerate(edges):
        adj.setdefault(a, []).append(i)
        adj.setdefault(b, []).append(i)
    breaks = {n for n, es in adj.items() if len(es) != 2} | set(split_nodes)
    used = [False] * len(edges)
    out: list[Chain] = []

    def walk(start: int, ei: int) -> None:
        nid = start
        seq: list[int] = []
        while True:
            used[ei] = True
            seq.append(ei)
            a, b, _l, _n = edges[ei]
            nid = b if a == nid else a
            if nid in breaks:
                break
            nxt = [e for e in adj[nid] if not used[e]]
            if not nxt:
                break
            ei = nxt[0]
        _emit(seq, start, nid)

    def _emit(seq: list[int], start: int, end: int) -> None:
        pts = [nodes[start]]
        nid = start
        letters: list[str | None] = []
        names: set[str] = set()
        for ei in seq:
            a, b, letter, name = edges[ei]
            nid = b if a == nid else a
            pts.append(nodes[nid])
            letters.append(letter)
            if name:
                names.add(name)
        pts = [p for i, p in enumerate(pts) if i == 0 or p != pts[i - 1]]
        if len(pts) < 2:
            return
        out.append(Chain(first_id + len(out), LineString(pts), tuple(letters),
                         frozenset(names),
                         (start in split_nodes, end in split_nodes), service,
                         (len(adj.get(start, ())), len(adj.get(end, ())))))

    for n in sorted(breaks):
        for ei in adj.get(n, []):
            if not used[ei]:
                walk(n, ei)
    for i in range(len(edges)):          # pure cycles (no break node)
        if not used[i]:
            walk(edges[i][0], i)
    return out


# ── the evidence ─────────────────────────────────────────────────────────

def build_evidence(airport: Airport, rules: Rules,
                   pad_min_area_m2: float) -> Evidence:
    """Derive every geometric input the scorer reads."""
    runway_polys = [(rw, runway_rectangle(rw)) for rw in airport.runways]
    runway_union = unary_union([p for _r, p in runway_polys]) if runway_polys \
        else Polygon()

    boundary = None
    if airport.boundaries:
        bs = [polygon_from(b.outer, b.holes) for b in airport.boundaries]
        bs = [b for b in bs if b is not None]
        boundary = unary_union(bs) if bs else None

    graded = set(rules.surfaces.graded_codes)
    apt_pav: list[tuple[str, Polygon]] = []
    dsf_raw: list[tuple[str, Polygon]] = []
    for p in airport.pavements:
        if int(p.surface) not in graded:
            continue
        poly = polygon_from(p.outer, p.holes)
        if poly is None or poly.area <= 0:
            continue
        (dsf_raw if p.id.startswith("dsf:") else apt_pav).append((p.id, poly))
    apt_union = unary_union([g for _i, g in apt_pav]) if apt_pav else Polygon()
    dsf_pav, dsf_dropped = _dsf_pavements(dsf_raw, apt_union, boundary, rules)
    pav = apt_pav + dsf_pav
    pavement_union = unary_union([g for _i, g in pav]) if pav else Polygon()

    node_xy = {nid: n.xy for nid, n in airport.taxi_nodes.items()}
    runway_nodes = {e.a for e in airport.taxi_edges if e.is_runway} | \
        {e.b for e in airport.taxi_edges if e.is_runway}
    if not runway_union.is_empty:
        prep = shapely.prepared.prep(runway_union)
        runway_nodes |= {nid for nid, xy in node_xy.items()
                         if prep.intersects(Point(xy))}
    taxi_edges = [(e.a, e.b, e.width_class, e.name)
                  for e in airport.taxi_edges if not e.is_runway]
    taxi_chains = chains_from_edges(node_xy, taxi_edges, runway_nodes, False)
    truck_edges = [(r.a, r.b, None, r.name) for r in airport.ground_routes]
    truck_chains = chains_from_edges(node_xy, truck_edges, (), True,
                                     len(taxi_chains))

    taxi_chains, leadins = _trim_leadins(taxi_chains, airport, rules)
    reach = _network_reach(taxi_edges, runway_nodes)
    reach_xy = {node_xy[n] for n in reach if n in node_xy}
    taxi_chains = [_dc.replace(c, runway_network=(
        c.line.coords[0] in reach_xy or c.line.coords[-1] in reach_xy))
        for c in taxi_chains]
    taxi_chains += _osm_taxiways(airport, taxi_chains, pavement_union,
                                 runway_union, rules, len(taxi_chains) + len(truck_chains))
    road_chains = _osm_roads(airport, truck_chains, pavement_union, rules,
                             len(taxi_chains) + len(truck_chains))
    parking = [(f"osm:{w.id}", p) for w in airport.osm_ways
               if w.closed and w.tags.get("amenity") == "parking"
               for p in [polygon_from(w.points[:-1])] if p is not None]

    pads, dropped = _pads(airport, rules, pad_min_area_m2, boundary,
                          pavement_union, runway_union)
    pad_union = unary_union([g for _i, g in pads]) if pads else Polygon()

    terminal = any(s.kind == "gate" for s in airport.startups) or any(
        w.tags.get("aeroway") == "terminal" for w in airport.osm_ways) or any(
        b.source.endswith(":terminal") for b in airport.buildings)
    return Evidence(runway_polys, runway_union, pav, pavement_union,
                    taxi_chains, truck_chains, pads, pad_union, boundary,
                    terminal, dropped, leadins, len(dsf_pav), dsf_dropped,
                    road_chains, parking)


def _network_reach(edges: _t.Sequence[tuple[int, int, str | None, str]],
                   runway_nodes: _t.Collection[int]) -> set[int]:
    """Node ids in a taxi-network component containing a runway node."""
    adj: dict[int, list[int]] = {}
    for a, b, _l, _n in edges:
        adj.setdefault(a, []).append(b)
        adj.setdefault(b, []).append(a)
    seen: set[int] = set(n for n in runway_nodes if n in adj)
    queue = list(seen)
    while queue:
        n = queue.pop()
        for m in adj.get(n, ()):
            if m not in seen:
                seen.add(m)
                queue.append(m)
    return seen


def _osm_roads(airport: Airport, truck_chains: list[Chain], pavement_union,
               rules: Rules, first_id: int) -> list[Chain]:
    """OSM road ways (``rules.osm_roads.highways``) as ground-vehicle
    centrelines ON pavement, deduped against the authored 1206 routes
    (the network stays senior); one chain per surviving way part."""
    orr = rules.osm_roads
    if not orr.enabled or pavement_union.is_empty:
        return []
    cover = unary_union([c.line for c in truck_chains]).buffer(orr.dedup_m) \
        if truck_chains else Polygon()
    out: list[Chain] = []
    for w in airport.osm_ways:
        if w.tags.get("highway") not in orr.highways or len(w.points) < 2:
            continue
        g = LineString(w.points).intersection(pavement_union)
        if not cover.is_empty:
            g = g.difference(cover)
        for part in _line_parts(g):
            if part.length < orr.min_len_m:
                continue
            out.append(Chain(first_id + len(out), part, (None,) * (len(part.coords) - 1),
                             frozenset([f"osm:{w.id}"]), (False, False), True, (1, 1),
                             aisle=w.tags.get("service") == "parking_aisle"))
    return out


def _line_parts(geom) -> list[LineString]:
    if geom is None or geom.is_empty:
        return []
    if geom.geom_type == "LineString":
        return [geom]
    return [g for g in getattr(geom, "geoms", ()) if g.geom_type == "LineString"
            and g.length > 0]


def _dsf_pavements(raw: list[tuple[str, Polygon]], apt_union, boundary,
                   rules: Rules) -> tuple[list[tuple[str, Polygon]], int]:
    """Admit draped DSF pavement pages (v1 ``read_dsf_pavements`` gates):
    inside the boundary + buffer; a page mostly ON apt.dat pavement is an
    overlay and only its remainder counts."""
    dp = rules.dsf_pavement
    gate = boundary.buffer(dp.boundary_buffer_m) if boundary is not None else None
    out: list[tuple[str, Polygon]] = []
    dropped = 0
    for pid, poly in raw:
        if gate is not None:
            parts = polygon_parts(poly.intersection(gate))
            if not parts:
                dropped += 1
                continue
            poly = max(parts, key=lambda g: g.area)
        if poly.area < dp.min_area_m2:
            dropped += 1
            continue
        if not apt_union.is_empty and \
                poly.intersection(apt_union).area / poly.area >= dp.overlay_fraction:
            dropped += 1
            for k, g in enumerate(polygon_parts(poly.difference(apt_union))):
                if g.area >= dp.remainder_min_m2:
                    out.append((f"{pid}#{k}", g))
            continue
        out.append((pid, poly))
    return out, dropped


def _osm_taxiways(airport: Airport, chains: list[Chain], pavement_union,
                  runway_union, rules: Rules, first_id: int) -> list[Chain]:
    """OSM ``aeroway=taxiway`` ways as centrelines where the apt.dat 1202
    network is silent: the parts on pavement, off the runways and not
    within ``dedup_m`` of an authored route (the network stays senior)."""
    ot = rules.osm_taxiways
    if not ot.enabled:
        return []
    cover = unary_union([c.line for c in chains]).buffer(ot.dedup_m) if chains \
        else Polygon()
    out: list[Chain] = []
    for w in airport.osm_ways:
        if w.tags.get("aeroway") != "taxiway" or w.closed or len(w.points) < 2:
            continue
        g = LineString(w.points).intersection(pavement_union)
        if not runway_union.is_empty:
            g = g.difference(runway_union)
        if not cover.is_empty:
            g = g.difference(cover)
        parts = [g] if g.geom_type == "LineString" else \
            [q for q in getattr(g, "geoms", ()) if q.geom_type == "LineString"]
        for part in parts:
            if part.length < ot.min_len_m:
                continue
            out.append(Chain(first_id + len(out), part, (None,) * (len(part.coords) - 1),
                             frozenset([f"osm:{w.id}"]), (False, False), False, (1, 1)))
    return out


def _trim_leadins(chains: list[Chain], airport: Airport, rules: Rules
                  ) -> tuple[list[Chain], list[Chain]]:
    """Drop the little dead-end lead-ins onto stands from the slicing set
    (user 2026-07-04): a LEAF chain (one end degree 1, not a runway
    contact) ending near a 1300 startup and no longer than the cap."""
    li = rules.leadin
    starts = [Point(s.xy) for s in airport.startups]
    if not starts or not chains:
        return chains, []
    kept: list[Chain] = []
    trimmed: list[Chain] = []
    for c in chains:
        ends = (Point(c.line.coords[0]), Point(c.line.coords[-1]))
        leaf = [c.end_degree[k] == 1 and not c.runway_contact[k] for k in (0, 1)]
        near = [any(ends[k].distance(s) <= li.ramp_start_trim_m for s in starts)
                for k in (0, 1)]
        if c.line.length <= li.max_len_m and any(leaf[k] and near[k] for k in (0, 1)):
            trimmed.append(c)
        else:
            kept.append(c)
    return kept, trimmed


def _pads(airport: Airport, rules: Rules, min_area: float, boundary,
          pavement_union, runway_union) -> tuple[list[tuple[str, Polygon]], int]:
    """Building footprints -> pads: union coincident/stacked footprints
    (a terminal is several facade pieces on one outline), keep those
    inside the boundary (else near pavement), fold tiny ones (RULINGS
    2026-08-24 :1687), never over a runway."""
    polys = []
    admitted = tuple(rules.buildings.sources)
    for b in airport.buildings:
        if not b.source.startswith(admitted):
            continue
        p = polygon_from(b.outer, b.holes)
        if p is not None and p.area > 0:
            polys.append(p)
    if not polys:
        return [], 0
    merged = unary_union(polys)
    gate = boundary if boundary is not None else pavement_union.buffer(200.0)
    out: list[tuple[str, Polygon]] = []
    dropped = 0
    for part in sorted(polygon_parts(merged),
                       key=lambda g: (round(g.bounds[1]), round(g.bounds[0]))):
        if not runway_union.is_empty and part.intersects(runway_union):
            part = part.difference(runway_union)
        for piece in polygon_parts(part):
            if piece.area < min_area:
                dropped += 1
                continue
            if not gate.contains(piece.representative_point()):
                dropped += 1
                continue
            out.append((f"building{len(out) + 1}", piece))
    return out, dropped
