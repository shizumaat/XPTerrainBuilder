"""Classification EVIDENCE — the geometry the scorer reads (plan §1 row
2: apt.dat surface + taxi network + OSM/DSF footprints).

Everything here is derived once from the :class:`Airport`; the scorer
(``roles.py``) never touches a source record.  shapely lives in this
package and ``planar/`` only.
"""
from __future__ import annotations

import dataclasses as _dc
import math
import re
import typing as _t

import shapely
from shapely.geometry import LineString, MultiPolygon, Point, Polygon
from shapely.ops import unary_union
from shapely.strtree import STRtree

from ..model.airport import Airport, Runway
from ..model.frame import XY
from .rules import Rules

__all__ = ["Chain", "Evidence", "build_evidence", "polygon_from",
           "polygon_parts", "chains_from_edges", "apron_named", "taxi_name_match"]

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
    #: THE SKIRTED PADS NEVER MINTED (owner RULINGS 2026-09-10ag, spec
    #: §22.2): one line per candidate pad dropped because skirted
    #: placements cover it and the relief is inside their skirt — the
    #: pad's would-be ref, its area, relief and the skirt depth ``s``.
    skirted_pads: list[str] = _dc.field(default_factory=list)


# ── names (the author's own word for a page) ────────────────────────────

def apron_named(description: str, rules: Rules) -> bool:
    """The apt.dat 110 description names an APRON (``lot.apron_name_tokens``)."""
    d = description.lower()
    return any(t in d for t in rules.lot.apron_name_tokens)


def taxi_name_match(description: str, rules: Rules) -> tuple[str, str] | None:
    """THE TAXI-NAME RULE (RULINGS 2026-09-04z(1), ``rules.taxi_name``):
    ``(token, designator)`` when the apt.dat 110 description names a
    taxiway — a whole-word ``tokens`` match ("Taxiway B", "TWY A1") — else
    ``None``.  Names nothing when: the description also names an APRON
    (the apron name is senior — a "Taxiway E apron" is the apron a
    taxiway crosses, RULINGS 2026-09-03j); or it is one of the editor's
    ``unauthored_names`` plus an optional number ("New Taxiway 41" is
    WED's default for every new pavement — CYXY's roads and lots all
    carry it).  The designator is the word after the token when it is
    at most ``designator_max_len`` characters, else empty."""
    tn = rules.taxi_name
    d = " ".join(description.lower().split())
    if not d or apron_named(d, rules):
        return None
    for u in tn.unauthored_names:
        if re.fullmatch(re.escape(u.lower()) + r"\s*\d*", d):
            return None
    for tok in tn.tokens:
        m = re.search(r"\b" + re.escape(tok.lower()) + r"\b[\s:\-]*([a-z0-9]*)", d)
        if m is None:
            continue
        desig = m.group(1)
        if len(desig) > tn.designator_max_len:
            desig = ""
        return tok, desig.upper()
    return None


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
    side — a legacy margin v2 does not carry).  The corners are the
    model's own (``Runway.slab_corners``): ONE derivation, shared with
    the strip footprint (§40 (1))."""
    return Polygon(rw.slab_corners)


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
                   pad_min_area_m2: float, law=None, cache=None) -> Evidence:
    """Derive every geometric input the scorer reads.  ``law`` and
    ``cache`` reach the FOUNDATION-SKIRT reader (spec §22): with a law a
    candidate pad covered by skirted placements is never minted, and the
    ground under the building keeps its design surface (owner RULINGS
    2026-09-10ag).  Without one every pad stands as 09c/10y leave it —
    the classify-only tools (``pipeline/__main__ explain``) pass theirs
    so no tool reads a different pad set from the build."""
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

    pads, dropped, skirted = _pads(airport, rules, pad_min_area_m2, boundary,
                                   pavement_union, runway_union, law, cache)
    pad_union = unary_union([g for _i, g in pads]) if pads else Polygon()

    terminal = any(s.kind == "gate" for s in airport.startups) or any(
        w.tags.get("aeroway") == "terminal" for w in airport.osm_ways) or any(
        b.source.endswith(":terminal") for b in airport.buildings)
    return Evidence(runway_polys, runway_union, pav, pavement_union,
                    taxi_chains, truck_chains, pads, pad_union, boundary,
                    terminal, dropped, leadins, len(dsf_pav), dsf_dropped,
                    road_chains, parking, skirted)


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


#: §16g (10) (2): what :func:`_cluster_pads` last derived, for the
#: build's own say-line and the sidecar (``pipeline/publication``).
CLUSTER_PADS: dict[str, object] = {}


def _cluster_pads(airport: Airport, law) -> list[Polygon]:
    """§16g (10) (2): ONE pad polygon per CLUSTER — the union of its
    member bodies' footprint rings (``PlanCluster.rings``, the §16g (7)
    (1) outlines), in the planar frame's metres.

    A cluster whose plan predates ``Part.rings`` carries none and is
    SKIPPED (counted): a box union is not a footprint and 13ci measured
    what pricing one costs.  Returns the polygons in the clusters' own
    order; the caller sorts and gates them."""
    CLUSTER_PADS.clear()
    cl = getattr(airport, "clusters", None) or ()
    if law is None or not cl:
        return []
    if not bool(law.tables.structures.placement.pad_from_cluster):
        CLUSTER_PADS.update(disarmed=True, clusters=len(cl))
        return []
    to_xy, _to_ll = airport.frame.transformers()
    out: list[Polygon] = []
    no_rings = 0
    for c in cl:
        rings = getattr(c, "rings", ()) or ()
        if not rings:
            no_rings += 1
            continue
        ps = []
        for r in rings:
            if len(r) < 3:
                continue
            g = Polygon([to_xy(lo, la) for la, lo in r])
            if not g.is_valid:
                g = g.buffer(0.0)
            if not g.is_empty and g.area > 0.0:
                ps.append(g)
        if not ps:
            no_rings += 1
            continue
        u = unary_union(ps)
        for piece in polygon_parts(u):
            if piece.area > 0.0:
                out.append(piece)
    CLUSTER_PADS.update(clusters=len(cl), pads=len(out),
                        no_rings=no_rings,
                        area_m2=round(sum(p.area for p in out), 1))
    return out


def _pads(airport: Airport, rules: Rules, min_area: float, boundary,
          pavement_union, runway_union, law=None, cache=None
          ) -> tuple[list[tuple[str, Polygon]], int, list[str]]:
    """Building footprints -> pads: union coincident/stacked footprints
    (a terminal is several facade pieces on one outline), keep those
    inside the boundary (else near pavement), fold tiny ones (RULINGS
    2026-08-24 :1687), never over a runway.

    THE SKIRTED PAD IS NEVER MINTED (owner RULINGS 2026-09-10ag; spec
    §22.2).  This is the ONE derivation site: a pad dropped here is
    dropped before ``pad_union``, so every region that differences
    itself by the pads (``roles.classify`` :168 / :315) simply covers
    the footprint and the ground under the building keeps its design
    surface — no hole, no new shape class, no per-consumer veto.

    §16g (10) (2) THE PAD IS THE CLUSTER (owner RULINGS 2026-09-14x,
    verbatim: *"pads must match building clusters, no building, or
    cluster can span multiple pads ... they should match exactly"*).
    Where the pack has been partitioned into CLUSTERS
    (``Airport.clusters``, ``planar/cluster.py``) each cluster's own
    OUTLINE UNION is ONE pad candidate — one pad per cluster, never
    unioned with a neighbouring cluster's, which is the whole of "match
    exactly": two clusters that touch at different floors are two
    buildings and the ground between their pads terraces by §23.  The
    admitted footprints NO cluster covers keep the pre-14x reading (one
    ``unary_union``, its connected parts) — (10) (2)'s "the
    footprint-cache pads are the fallback where the plan has no
    cluster".  Every gate below — the runway difference, ``min_area``,
    the boundary and §22.2's skirt drop — is unchanged and applies to
    both halves.  ``[placement] pad_from_cluster = false`` restores the
    pre-14x derivation exactly and is this law's matched base arm.

    MEASURED dry on HECA's round-6 frame: 414 emitted pads / 870,563 m2
    become 401 cluster pads / 1,541,286 m2 at the same
    ``[building_pad] min_area_m2`` — the COUNT is unchanged and the
    covered area is the pack's true footprints replacing the footprint
    cache's."""
    polys = []
    admitted = tuple(rules.buildings.sources)
    for b in airport.buildings:
        if not b.source.startswith(admitted):
            continue
        p = polygon_from(b.outer, b.holes)
        if p is not None and p.area > 0:
            polys.append(p)
    cluster_pads = _cluster_pads(airport, law)
    if cluster_pads:
        # the FALLBACK half: only the footprints no cluster covers
        cu = unary_union(cluster_pads)
        polys = [p for p in polys
                 if p.intersection(cu).area < 0.5 * p.area]
    if not polys and not cluster_pads:
        return [], 0, []
    parts = list(cluster_pads)
    if polys:
        parts.extend(polygon_parts(unary_union(polys)))
    gate = boundary if boundary is not None else pavement_union.buffer(200.0)
    out: list[tuple[str, Polygon]] = []
    dropped = 0
    for part in sorted(parts,
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
    # THE BARE-GROUND BODY PAD IS WITHDRAWN (owner RULINGS 2026-09-11q;
    # spec §11b (1)).  Round 5 minted a pad here from each bare-ground
    # body's own plan footprint (LEMD pads 123 -> 503) and MEASURED it
    # worse at the owner's own site: a rigid plane cut into sloping
    # ground STEPS wherever an unpadded neighbour straddles its edge
    # (the three rows' worst body 1.94 -> 3.33 m, ``pad_flat`` verify
    # rows 39 -> 98, HECA's released T3 bodies +1.5 -> +8.7 m).  The
    # colonnade's columns carry 2.63 m of authored relief BECAUSE the
    # real ground slopes there; a flat pad fights the authoring.  A body
    # on bare ground now takes FOOT ROWS priced as ground targets
    # (``constraints/foot_rows.py``, §11b (2)) and NO pad entity, so
    # this derivation mints pads from the OSM alone again.  A body
    # standing INSIDE an OSM pad still gets that pad's relief offsets
    # (``constraints/pad_relief.py``, §11a (2)) — unchanged.
    return _drop_skirted(airport, law, cache, out, dropped)


def _drop_skirted(airport: Airport, law, cache, pads: list[tuple[str, Polygon]],
                  dropped: int) -> tuple[list[tuple[str, Polygon]], int, list[str]]:
    """Owner RULINGS 2026-09-10ag: a pad whose area is covered by SKIRTED
    placements (``airport/skirt.py``) and whose DEM relief stays inside
    the shallowest of their skirt depths is NEVER MINTED — the building
    sits on the sloping ground, its high side buried and its low side
    exposed, so no flat pad and no ramp is needed.  Relief beyond the
    skirt, a skirt-less building, or a pad the skirted footprints do not
    cover: the pad stands exactly as 09c / 10y / 10ah leave it.

    Returns ``(pads kept, ``dropped`` unchanged, the drop lines)``; the
    refs are renumbered so ``buildingN`` stays contiguous."""
    from ..airport import skirt as _skirt
    if law is None or not pads or not law.tables.structures.skirt.drops_pad:
        return pads, dropped, []
    cover = law.tables.structures.skirt.pad_cover_fraction
    depths, cache = _skirt.skirted_placements(airport, law, cache)
    if not depths:
        return pads, dropped, []
    prints: list[tuple[Polygon, float]] = []
    for o in airport.dsf_objects:
        s = depths.get(o.id)
        if s is None or not o.resolved_path:
            continue
        fp = _skirt.placement_footprint(cache, o.resolved_path, law,
                                        o.xy, o.heading_deg)
        if fp is not None and not fp.is_empty and fp.area > 0.0:
            prints.append((fp, s))
    if not prints:
        return pads, dropped, []
    tree = STRtree([g for g, _s in prints])
    kept: list[tuple[str, Polygon]] = []
    lines: list[str] = []
    for ref, poly in pads:
        parts: list = []
        s: float | None = None
        for i in tree.query(poly, predicate="intersects"):
            g = prints[int(i)][0].intersection(poly)
            if g.is_empty or g.area <= 0.0:
                continue
            parts.append(g)
            d = prints[int(i)][1]
            s = d if s is None else min(s, d)
        area = unary_union(parts).area if parts else 0.0
        relief = _skirt.ring_relief_m(airport.dem.z, poly.exterior.coords) \
            if s is not None else math.inf
        if s is None or poly.area <= 0.0 or area < cover * poly.area or relief > s:
            kept.append((ref, poly))              # the refs never renumber:
            continue                              # two arms join on them
        lines.append(f"{ref} dropped (skirted): {poly.area:.0f} m2, "
                     f"{100.0 * area / poly.area:.0f} % covered by skirted "
                     f"placements, relief {relief:.2f} m <= skirt {s:.2f} m")
    return kept, dropped, lines
