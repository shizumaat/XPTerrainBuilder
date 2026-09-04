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
from .overlay import Arrangement, build_arrangement

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


def build(airport: Airport, classification: Classification, law: Law,
          grid_m: float | None = None) -> tuple[PlanarMap, BuildStats]:
    """The planar map for ``airport`` under ``law``, validated."""
    arr = build_arrangement(airport, classification, law, grid_m)
    stats = BuildStats(grid_m=arr.grid_m, dropped_faces=arr.dropped_faces)
    frame = airport.frame
    to_ll = _vector_to_ll(frame)

    vid_of: dict[XY, int] = {}
    vertices_xy: list[XY] = []
    edges: dict[tuple[int, int], Edge] = {}
    edge_list: list[Edge] = []
    faces: dict[int, Face] = {}
    incident: dict[int, set[int]] = {}

    def vertex(p: XY) -> int:
        v = vid_of.get(p)
        if v is None:
            v = len(vertices_xy)
            vid_of[p] = v
            vertices_xy.append(p)
            incident[v] = set()
        return v

    def walk(coords: _t.Sequence[XY], fid: int) -> tuple[int, ...]:
        """Ring edges in walking order; the face is on the LEFT."""
        ids: list[int] = []
        pts = [(float(x), float(y)) for x, y in coords]
        if pts[0] == pts[-1]:
            pts.pop()
        vs = [vertex(p) for p in pts]
        for a, b in zip(vs, vs[1:] + vs[:1]):
            if a == b:
                continue
            key = (a, b) if a < b else (b, a)
            e = edges.get(key)
            if e is None:
                e = Edge(len(edge_list), key[0], key[1], None, None,
                         EdgeKind.BOUNDARY)
                edges[key] = e
                edge_list.append(e)
            if (a, b) == key:
                e = _dc.replace(e, left_face=fid)
            else:
                e = _dc.replace(e, right_face=fid)
            edges[key] = e
            edge_list[e.id] = e
            ids.append(e.id)
            incident[a].add(fid)
            incident[b].add(fid)
        return tuple(ids)

    for fid, (poly, region) in enumerate(arr.faces):
        poly = orient(poly, sign=1.0)
        ring = walk(poly.exterior.coords, fid)
        holes = tuple(walk(h.coords, fid) for h in poly.interiors)
        faces[fid] = Face(fid, region.role, region.ref, ring, holes,
                          region.code_number, region.code_letter, region.side)
        stats.faces_by_role[region.role] = stats.faces_by_role.get(region.role, 0) + 1
        stats.area_by_role_m2[region.role] = \
            stats.area_by_role_m2.get(region.role, 0.0) + poly.area

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
    dp = frame.identity_dp
    vertices: dict[int, Vertex] = {}
    for v, p in enumerate(vertices_xy):
        key: Key = (round(float(lat[v]), dp), round(float(lon[v]), dp))
        z = float(zs[v])
        vertices[v] = Vertex(v, p, key, None if math.isnan(z) else z,
                             tuple(sorted(incident[v])))

    pm = PlanarMap(airport.icao, vertices, {e.id: e for e in edge_list},
                   faces, {b.id: b for b in breaklines})
    validate(pm)
    stats.faces, stats.edges = len(faces), len(edge_list)
    stats.vertices, stats.breaklines = len(vertices), len(breaklines)
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


def _breaklines(arr: Arrangement, edge_list: list[Edge], vxy: list[XY]
                ) -> tuple[list[Breakline], dict[int, EdgeKind], int, int]:
    """Match each source line to the noded edges lying on it (both
    endpoints within ``0.6 * grid`` of the snapped source), order them
    along the source and split where the chain breaks."""
    tol = 0.6 * arr.grid_m
    segs = [LineString([vxy[e.a], vxy[e.b]]) for e in edge_list]
    tree = STRtree(segs) if segs else None
    out: list[Breakline] = []
    kinds: dict[int, EdgeKind] = {}
    dropped = split = 0
    for src in arr.sources:
        line = shapely.set_precision(src.line, arr.grid_m)
        if line.is_empty or line.length <= 0 or tree is None:
            continue
        cand = []
        for j in tree.query(line.buffer(tol), predicate="intersects"):
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
            out.append(Breakline(len(out), src.kind, src.ref, tuple(ch)))
    return out, kinds, dropped, split


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
