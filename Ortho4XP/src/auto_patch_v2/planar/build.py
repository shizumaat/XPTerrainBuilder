"""``build(airport, classification, law) -> PlanarMap`` — faces, edges
once with both faces, vertices with 11-dp identity and every incident
face, breaklines as edge chains, a DEM sample per vertex, then
``validate()`` (invariants I1-I7, ``model/planar.py``).

The topology is read off the polygonised arrangement: each face ring is
oriented (exterior counter-clockwise, holes clockwise) so the face lies
to the LEFT of every directed ring edge; an undirected edge is created
once and gets ``left_face`` from the face walking it forward and
``right_face`` from the face walking it backward.  A vertex on a face
boundary is an endpoint of that face's ring edges by construction, so a
T-vertex cannot be represented — ``stats.t_vertices`` measures it
anyway (an STRtree query of every vertex against non-incident edges).
"""
from __future__ import annotations

import dataclasses as _dc
import math
import typing as _t

import numpy as np
import shapely
from shapely.geometry import LineString, Point
from shapely.geometry.polygon import orient
from shapely.strtree import STRtree

from ..classify.roles import Classification
from ..law import Law
from ..model.airport import Airport
from ..model.frame import XY, Key
from ..model.planar import (Breakline, Edge, EdgeKind, Face, PlanarMap,
                            Vertex, validate)
from .edges import EdgeTable
from .terrain_edge import EdgeReport
from .overlay import Arrangement, build_arrangement
from .shapes import ShapeStats, build_shapes
from .weld import WeldStats
from .basins import BasinStats, build_basins, read_objects
from .channel import ChannelStats, identify_channels
from .structures import StructureStats, build_structures, ramp_targets
from ..airport.tunnel_objects import TunnelObjectStats, read_corridors
from ..airport.thin_plates import read_plates
from ..airport.door_wells import DoorStats, read_door_wells
from ..airport.sunken_roads import SunkenRoadStats, read_sunken_roads
from ..airport.wall_corridors import WallCorridorStats, read_wall_corridors
from .door_ramps import door_groups, sunken_groups
from .wall_corridor_ramps import wall_corridor_groups

__all__ = ["BuildStats", "build"]

_LINE_KIND = {"runway_profile": EdgeKind.BREAKLINE,
              "taxi_centerline": EdgeKind.CENTERLINE,
              "road_centerline": EdgeKind.CENTERLINE}


@_dc.dataclass
class BuildStats:
    """What the build produced and what it dropped."""

    faces: int = 0
    edges: int = 0
    vertices: int = 0
    breaklines: int = 0
    t_vertices: int = 0
    dropped_faces: int = 0
    dropped_source_edges: int = 0
    breakline_chains_split: int = 0
    min_vertex_spacing_m: float = 0.0
    max_chord_m: float = 0.0
    faces_by_role: dict[str, int] = _dc.field(default_factory=dict)
    area_by_role_m2: dict[str, float] = _dc.field(default_factory=dict)
    grid_m: float = 0.0
    seam_bands: int = 0
    seam_vertices: int = 0
    dropped_seam_faces: int = 0
    structures: StructureStats = _dc.field(default_factory=StructureStats)
    basins: BasinStats = _dc.field(default_factory=BasinStats)
    weld: WeldStats = _dc.field(default_factory=WeldStats)
    tunnel_objects: TunnelObjectStats = _dc.field(default_factory=TunnelObjectStats)
    #: RULINGS 2026-09-08b/c: the door wells and sunken roads read
    door_wells: DoorStats = _dc.field(default_factory=DoorStats)
    sunken_roads: SunkenRoadStats = _dc.field(default_factory=SunkenRoadStats)
    shapes: ShapeStats = _dc.field(default_factory=ShapeStats)   # owner RULINGS 2026-09-08k (``planar/shapes.py``)
    slivers_merged: int = 0      # RULINGS 2026-09-08d (4a): same-region sliver faces merged (``overlay.merge_slivers``)
    holes_dissolved: int = 0     # RULINGS 2026-09-10h (1): degenerate hole rings dissolved (``overlay.dissolve_degenerate_holes``)
    #: §41 (1): pavement faces enclosed by another pavement face's ring and
    #: absorbed into it, and the enclosed-but-detached ones left alone
    #: (``overlay.absorb_enclosed_pavement``)
    enclosed_absorbed: int = 0
    enclosed_detached: int = 0
    #: §41 (4) (owner RULINGS 2026-09-14c item 4): sliver ZONE faces
    #: dissolved into the face they border, the host-less ones dropped,
    #: their total area and one row each (``overlay.dissolve_sliver_zones``)
    zone_slivers_dissolved: int = 0
    zone_slivers_dropped: int = 0
    zone_sliver_area_m2: float = 0.0
    zone_sliver_rows: tuple = ()
    #: RULINGS 2026-09-08m/08n Law C: the kerb-wall corridors read
    wall_corridors: WallCorridorStats = _dc.field(default_factory=WallCorridorStats)
    #: owner RULINGS 2026-09-10b/10c (spec §19): the terrain edge's trim
    terrain_edge: EdgeReport = _dc.field(default_factory=EdgeReport)
    #: spec §45 (owner RULINGS 2026-09-15i): the OPEN CHANNELS identified
    channels: ChannelStats = _dc.field(default_factory=ChannelStats)


def build(airport: Airport, classification: Classification, law: Law,
          grid_m: float | None = None, objects_out: list | None = None,
          cache=None, objects=None, object_report=None) -> tuple[PlanarMap, BuildStats]:
    """The planar map for ``airport`` under ``law``, validated.
    ``objects_out``, when given, receives ``[objects, cache]`` — the
    placed objects read here and their parsed geometry — so the emit
    stage's re-bake plan (``emit/rebake.py``) reads the pack ONCE.

    ``objects`` / ``object_report``, when given, are the pack ALREADY READ
    at load (owner RULINGS 2026-09-11j; spec §11a (3): the pack partition
    is a load-stage input, so the objects are read before ``classify``) —
    passing them keeps "the pack is read ONCE" true now that the first
    reader is upstream of this stage."""
    import time as _time
    t0 = _time.perf_counter()
    from ..airport.obj8 import ResourceCache
    cache = cache or ResourceCache(law.tables.structures.basin.min_solid_thickness_m)
    if objects is None:
        objects, orep = read_objects(airport, law, cache)
    else:
        orep = object_report
    if objects_out is not None:
        objects_out[:] = [objects, cache]
    read_s = _time.perf_counter() - t0
    # THE TUNNEL WALL OBJECTS (RULINGS 2026-09-05k-1): read over the
    # geometry the cache already holds, they replace the OSM bores they cover
    corridors, tstats = read_corridors(airport, objects, cache, law)
    # THE THIN-PLATE WALL OBJECTS (spec §33 (2)): the pack's bridge / tunnel
    # PLATES, which the wall reader's skirt pre-screen refuses — they govern
    # the MOUTH of the bore they span (owner RULINGS 2026-09-13d item 5)
    plates, pstats = read_plates(airport, objects, cache, law,
                                 {c.resource for c in corridors})
    tstats.plates = pstats.plates
    tstats.refused.extend(pstats.refused)
    # THE DOOR WELLS AND SUNKEN ROADS (RULINGS 2026-09-08b/c): read over the
    # same geometry, built through the same structure machinery
    wells, dstats = read_door_wells(airport, objects, cache, law)
    roads, rstats = read_sunken_roads(airport, objects, cache, law)
    walls_c, wstats = read_wall_corridors(airport, objects, cache, law, classification)
    extra = door_groups(wells, law) + sunken_groups(roads, law, rstats.refused) \
        + wall_corridor_groups(walls_c, law)
    # ── THE OPEN CHANNELS (spec §45; owner RULINGS 2026-09-15i) ──────
    # DERIVED FIRST (§45.1 C1): the structure pass reads them to keep a
    # crossing inside a channel from ever becoming a bore with mouths
    # (§45 (1)/(6)), and the basin pass to keep a wall/floor object along
    # the axis from being read a second time as a pit (§45 (7)).
    channels, chstats = identify_channels(airport, classification, law, objects)
    classification, tunnels, sstats = build_structures(airport, classification, law, objects,
                                                       corridors, extra, plates, channels)
    classification, basins, bstats = build_basins(airport, classification, law, tunnels,
                                                  objects, cache, report=orep,
                                                  channels=channels,
                                                  claimed=frozenset(tstats.shell_claimed))
    bstats.objects = orep
    bstats.object_read_s = read_s
    arr = build_arrangement(airport, classification, law, grid_m)
    stats = BuildStats(grid_m=arr.grid_m, dropped_faces=arr.dropped_faces,
                       structures=sstats, basins=bstats, weld=arr.weld, tunnel_objects=tstats,
                       slivers_merged=arr.slivers_merged,
                       holes_dissolved=arr.holes_dissolved,
                       enclosed_absorbed=arr.enclosed_absorbed,
                       enclosed_detached=arr.enclosed_detached,
                       zone_slivers_dissolved=arr.zone_slivers_dissolved,
                       zone_slivers_dropped=arr.zone_slivers_dropped,
                       zone_sliver_area_m2=arr.zone_sliver_area_m2,
                       zone_sliver_rows=arr.zone_sliver_rows,
                       door_wells=dstats, sunken_roads=rstats, wall_corridors=wstats,
                       channels=chstats,
                       terrain_edge=arr.edge_report)
    frame = airport.frame
    to_ll = _vector_to_ll(frame)

    vid_of: dict[XY, int] = {}
    vertices_xy: list[XY] = []
    table = EdgeTable()
    faces: dict[int, Face] = {}

    def vertex(p: XY) -> int:
        v = vid_of.get(p)
        if v is None:
            v = len(vertices_xy)
            vid_of[p] = v
            vertices_xy.append(p)
            table.incident.setdefault(v, set())
        return v

    def walk(coords: _t.Sequence[XY], fid: int) -> tuple[int, ...]:
        """Ring edges in walking order; the face is on the LEFT."""
        pts = [(float(x), float(y)) for x, y in coords]
        if pts[0] == pts[-1]:
            pts.pop()
        return table.walk([vertex(p) for p in pts], fid)

    for fid, (poly, region) in enumerate(arr.faces):
        poly = orient(poly, sign=1.0)
        ring = walk(poly.exterior.coords, fid)
        holes = tuple(walk(h.coords, fid) for h in poly.interiors)
        faces[fid] = Face(fid, region.role, region.ref, ring, holes,
                          region.code_number, region.code_letter, region.side)
        stats.faces_by_role[region.role] = stats.faces_by_role.get(region.role, 0) + 1
        stats.area_by_role_m2[region.role] = \
            stats.area_by_role_m2.get(region.role, 0.0) + poly.area

    edge_list = table.edges
    incident = table.incident
    # ── breaklines: chains of existing edges along each source ─────
    breaklines, kinds, dropped, split = _breaklines(arr, edge_list, vertices_xy)
    stats.dropped_source_edges = dropped
    stats.breakline_chains_split = split
    for eid, kind in kinds.items():
        edge_list[eid] = _dc.replace(edge_list[eid], kind=kind)
    for e in edge_list:
        if e.kind == EdgeKind.BOUNDARY:
            roles = {faces[f].role for f in (e.left_face, e.right_face)
                     if f is not None}
            if roles and roles <= {"graded_strip"}:
                edge_list[e.id] = _dc.replace(e, kind=EdgeKind.ZONE)

    # ── vertices: identity + DEM ───────────────────────────────────
    xs = np.array([p[0] for p in vertices_xy])
    ys = np.array([p[1] for p in vertices_xy])
    lat, lon = to_ll(xs, ys)
    zs = _sample(airport, xs, ys)
    # a tunnel ramp's target is its designed profile (``ramp_targets``)
    targets = ramp_targets(tunnels, law, faces, edge_list, vertices_xy, zs)
    dp = frame.identity_dp
    vertices: dict[int, Vertex] = {}
    for v, p in enumerate(vertices_xy):
        key: Key = (round(float(lat[v]), dp), round(float(lon[v]), dp))
        z = targets.get(v, float(zs[v]))
        vertices[v] = Vertex(v, p, key, None if math.isnan(z) else z,
                             tuple(sorted(incident[v])))

    seam = _seam_vertices(arr, vertices_xy)
    pm = PlanarMap(airport.icao, vertices, {e.id: e for e in edge_list},
                   faces, {b.id: b for b in breaklines}, seam, tunnels, basins,
                   channels=tuple(channels),
                   terrain_edges=tuple(tuple(ln.coords) for ln in arr.terrain_edges),
                   seam_band_rings=tuple(tuple(b.exterior.coords)
                                         for b in arr.seam_bands),
                   edge_kind_of_ref={r.ref: r.edge_kind for r in arr.regions
                                     if r.edge_kind != "none"})
    validate(pm)
    # THE SHAPES (owner RULINGS 2026-09-08k): the connected components of
    # touching pavement, their joints declared — the only lawful steps
    pm, stats.shapes = build_shapes(pm, law, airport, classification)
    stats.seam_bands = len(arr.seam_bands)
    stats.seam_vertices = len(seam)
    stats.dropped_seam_faces = arr.dropped_seam_faces
    stats.faces, stats.edges = len(pm.faces), len(pm.edges)
    stats.vertices, stats.breaklines = len(pm.vertices), len(pm.breaklines)
    stats.t_vertices = _t_vertices(pm)
    stats.min_vertex_spacing_m, stats.max_chord_m = _spacing(pm)
    return pm, stats


# ── helpers ──────────────────────────────────────────────────────────────

def _vector_to_ll(frame):
    from pyproj import Transformer  # local: geodesy stays in the producers
    inv = Transformer.from_crs(frame.crs, "EPSG:4326", always_xy=True)

    def to_ll(xs: np.ndarray, ys: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
        lon, lat = inv.transform(xs, ys)
        return np.asarray(lat), np.asarray(lon)
    return to_ll


def _sample(airport: Airport, xs: np.ndarray, ys: np.ndarray) -> np.ndarray:
    dem = airport.dem
    many = getattr(dem, "z_many", None)
    if callable(many):
        return np.asarray(many(xs, ys), dtype=float)
    return np.array([dem.z(float(x), float(y)) for x, y in zip(xs, ys)])


def _snapped(geom, grid_m: float):
    """``geom`` with its coordinates on the grid and NO precision model
    left on the result.  ``set_precision`` stamps the grid onto the
    geometry, and every later operation on it is rounded to that grid
    too: a ``0.3 m`` buffer of a 0.5 m-precision line is snapped to the
    0.5 m lattice and, for any line off the axes, collapses to an EMPTY
    polygon (measured at LEMD 2026-09-04: the 142° runways 14R/32L and
    14L/32R lost their whole ``runway_profile`` breakline — no CIFP pins,
    no profile law, no crown, 2,185 oracle ``runway_crown`` rows priced
    against the 18/36 ridges 0.3–4.8 km away — while the 180° pair
    survived because an axis-aligned ribbon rounds to one cell wide)."""
    return shapely.set_precision(shapely.set_precision(geom, grid_m), 0.0)


def _breaklines(arr: Arrangement, edge_list: list[Edge], vxy: list[XY]
                ) -> tuple[list[Breakline], dict[int, EdgeKind], int, int]:
    """Match each source line to the noded edges lying on it (both
    endpoints within ``0.6 * grid`` of the snapped source — or within
    the sliver weld's spacing where the weld moved vertices, RULINGS
    2026-09-04u), order them along the source and split where the chain
    breaks.  Measured HECA 2026-09-05 (lane v2relaxfull5): four 1202
    chains meet at node (6.3, 579.3); the welded planar vertex sits at
    (6, 580), 0.323 m off the snapped source, so at 0.3 m the last edge
    of ``taxi136`` went unmatched, the chain ended one edge short and
    the route network split into two components (the 05L/23R complex
    cut off from every other threshold)."""
    tol = max(0.6 * arr.grid_m, arr.weld.tolerance_m)
    segs = [LineString([vxy[e.a], vxy[e.b]]) for e in edge_list]
    tree = STRtree(segs) if segs else None
    out: list[Breakline] = []
    kinds: dict[int, EdgeKind] = {}
    dropped = split = 0
    for src in arr.sources:
        line = _snapped(src.line, arr.grid_m)
        if line.is_empty or line.length <= 0 or tree is None:
            continue
        cand = []
        for j in tree.query(line, predicate="dwithin", distance=tol):
            e = edge_list[int(j)]
            if line.distance(Point(vxy[e.a])) <= tol and \
                    line.distance(Point(vxy[e.b])) <= tol and \
                    line.distance(segs[int(j)].centroid) <= tol:
                cand.append((line.project(segs[int(j)].centroid), e.id))
        if not cand:
            dropped += max(0, len(src.line.coords) - 1)
            continue
        cand.sort()
        chains: list[list[int]] = [[cand[0][1]]]
        for _s, eid in cand[1:]:
            prev = edge_list[chains[-1][-1]]
            cur = edge_list[eid]
            if {prev.a, prev.b} & {cur.a, cur.b}:
                chains[-1].append(eid)
            else:
                chains.append([eid])
        if len(chains) > 1:
            split += len(chains) - 1
        for ch in chains:
            for eid in ch:
                kinds[eid] = _LINE_KIND.get(src.kind, EdgeKind.BREAKLINE)
            out.append(Breakline(len(out), src.kind, src.ref, tuple(ch),
                                 src.code_letter))
    return out, kinds, dropped, split


def _seam_vertices(arr: Arrangement, vxy: list[XY]) -> frozenset[int]:
    """Vertices on a seam band's edge (the band boundary was noded and
    snapped with everything else, so the test is exact up to the grid)."""
    if not arr.seam_bands:
        return frozenset()
    tol = 0.6 * arr.grid_m
    edges = [_snapped(b.boundary, arr.grid_m) for b in arr.seam_bands]
    out = set()
    for v, p in enumerate(vxy):
        pt = Point(p)
        if any(e.distance(pt) <= tol for e in edges):
            out.add(v)
    return frozenset(out)


def _t_vertices(pm: PlanarMap) -> int:
    """Vertices lying on the interior of a non-incident edge."""
    segs = [LineString([pm.vertices[e.a].xy, pm.vertices[e.b].xy])
            for e in pm.edges.values()]
    if not segs:
        return 0
    tree = STRtree(segs)
    eov = pm.edges_of_vertex()
    n = 0
    for v in pm.vertices.values():
        p = Point(v.xy)
        for j in tree.query(p.buffer(1e-6), predicate="intersects"):
            if int(j) not in eov[v.id] and segs[int(j)].distance(p) < 1e-6:
                n += 1
                break
    return n


def _spacing(pm: PlanarMap) -> tuple[float, float]:
    """``(nearest distinct-vertex distance, longest edge)``."""
    pts = [Point(v.xy) for v in pm.vertices.values()]
    if len(pts) < 2:
        return 0.0, 0.0
    tree = STRtree(pts)
    best = float("inf")
    for i, p in enumerate(pts):
        for j in tree.query(p.buffer(2.0)):
            if int(j) != i:
                best = min(best, p.distance(pts[int(j)]))
    longest = max(LineString([pm.vertices[e.a].xy, pm.vertices[e.b].xy]).length
                  for e in pm.edges.values())
    return (best if best < float("inf") else 0.0), longest
