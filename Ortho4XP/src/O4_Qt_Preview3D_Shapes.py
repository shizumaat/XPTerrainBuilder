"""The 3D preview's patch surfaces (spec patch-editor-20261015 §5 and its
"Ruled after L6a" (1); the Mac app's ``PatchShapeAssembly``,
``PatchShapeMesh`` and ``PatchPreviewIndex``).

Pure functions over an ``o4_engine.patch_edit.PatchDoc`` — no widgets — so
every rule here is tested headless.

A SURFACE is a closed way without an ``o4_feature`` tag (runway, taxiway,
apron, building, graded strip …).  Its holes are

1. the ``o4_feature=gap_interior_ring`` rings paired with it: the emit
   writes an uncovered hole of face F as a closed way tagged with F's
   ``shapeID``; the hole goes to the smallest surface that contains it,
   among the surfaces with the hole's ``shapeID`` when it has one, else
   among all surfaces;
2. the surfaces nested directly inside it — the emit writes no hole that
   the faces inside it cover, so the outer face's ring runs round them —
   unless the inner face lies inside one of the parent's gap rings.

Structure rims, crown spines and other ``o4_feature`` ways are not surfaces.

Each surface is triangulated in NODE IDS, so a moved node updates its
vertex without re-triangulating.  The triangulator is the engine's one
face triangulation, ``auto_patch_v2.geom.triangulate.face_triangles``
(GEOS's constrained Delaunay, which covers a concave face or a face with
holes exactly — issue #752); this module keeps no copy of it.
"""
from __future__ import annotations

import dataclasses as _dc
import math
import typing as _t

import numpy as np

from o4_engine import patch_edit as PE

from O4_Qt_Pack_Outlines import METRES_PER_DEG_LAT
from auto_patch_v2.geom.triangulate import face_triangles

__all__ = ["HOLE_FEATURE", "LocalFrame", "PreviewShape", "ShapeMesh", "ShapeIndex", "triangulate",
           "DocChange", "is_surface", "is_gap_ring", "assemble", "mesh_shapes",
           "diff_documents"]

HOLE_FEATURE = "gap_interior_ring"
#: Metres within which a point counts as ON a ring (well under the law's
#: 0.5 m node spacing, well over coordinate round-off) — the Mac's value.
BOUNDARY_EPS_M = 1.0e-4


@_dc.dataclass(frozen=True)
class LocalFrame:
    """The engine emit's linear plane (``emit/osm_adapter._local_metres``)
    at the document origin: the centre of the document's bbox at load
    (spec §2, clarified after L2), fixed for the document's life."""

    origin_lat: float
    origin_lon: float

    @property
    def m_per_deg_lon(self) -> float:
        return METRES_PER_DEG_LAT * max(math.cos(math.radians(self.origin_lat)), 1e-6)

    @classmethod
    def of(cls, doc: PE.PatchDoc) -> "LocalFrame":
        lats = [n[1] for n in doc.nodes.values()] or [0.0]
        lons = [n[2] for n in doc.nodes.values()] or [0.0]
        return cls((min(lats) + max(lats)) / 2, (min(lons) + max(lons)) / 2)

    def metres(self, lat, lon):
        """(east, north) metres from the origin; arrays welcome."""
        return ((np.asarray(lon) - self.origin_lon) * self.m_per_deg_lon,
                (np.asarray(lat) - self.origin_lat) * METRES_PER_DEG_LAT)


@_dc.dataclass(frozen=True)
class PreviewShape:
    """One surface: its way id, outer ring and holes as node ids, rings
    OPEN (the closing id dropped)."""

    way_id: int
    outer: tuple[int, ...]
    holes: tuple[tuple[int, ...], ...] = ()

    @property
    def node_ids(self) -> frozenset:
        return frozenset(self.outer).union(*self.holes) if self.holes else frozenset(self.outer)


def is_surface(way: PE.Way) -> bool:
    return way.closed and "o4_feature" not in way.tags


def is_gap_ring(way: PE.Way) -> bool:
    return way.closed and way.tags.get("o4_feature") == HOLE_FEATURE


class _Ring:
    """A ring in the frame's plane with what containment needs."""

    def __init__(self, ids: tuple[int, ...], xy: np.ndarray):
        self.ids = ids
        self.xy = xy
        self.lo = xy.min(axis=0)
        self.hi = xy.max(axis=0)
        x, y = xy[:, 0], xy[:, 1]
        self.area = abs(float(np.dot(x, np.roll(y, -1)) - np.dot(y, np.roll(x, -1)))) / 2

    def _locate(self, p: np.ndarray) -> np.ndarray:
        """Per probe point: 1 inside, 0 on the boundary (within eps), -1 outside."""
        a, b = self.xy, np.roll(self.xy, -1, axis=0)
        d = b - a
        px, py = p[:, 0:1], p[:, 1:2]
        len2 = (d * d).sum(axis=1)
        with np.errstate(invalid="ignore", divide="ignore"):
            t = np.where(len2 > 0, ((px - a[:, 0]) * d[:, 0] + (py - a[:, 1]) * d[:, 1]) / len2, 0)
        t = np.clip(t, 0, 1)
        dist = np.hypot(px - (a[:, 0] + t * d[:, 0]), py - (a[:, 1] + t * d[:, 1]))
        on = (dist <= BOUNDARY_EPS_M).any(axis=1)
        straddle = (a[:, 1] > py) != (b[:, 1] > py)
        with np.errstate(invalid="ignore", divide="ignore"):
            xcross = d[:, 0] * (py - a[:, 1]) / d[:, 1] + a[:, 0]
        inside = (straddle & (px < xcross)).sum(axis=1) % 2 == 1
        return np.where(on, 0, np.where(inside, 1, -1))

    def _crosses(self, other: "_Ring") -> bool:
        """Some edge of ``other`` properly crosses an edge of this ring."""
        a, b = other.xy[:, None, :], np.roll(other.xy, -1, axis=0)[:, None, :]
        c, d = self.xy[None, :, :], np.roll(self.xy, -1, axis=0)[None, :, :]

        def orient(p, q, r):
            return (q[..., 0] - p[..., 0]) * (r[..., 1] - p[..., 1]) \
                - (q[..., 1] - p[..., 1]) * (r[..., 0] - p[..., 0])
        o1, o2 = orient(a, b, c), orient(a, b, d)
        o3, o4 = orient(c, d, a), orient(c, d, b)
        return bool((((o1 > 0) & (o2 < 0)) | ((o1 < 0) & (o2 > 0))).__and__(
            ((o3 > 0) & (o4 < 0)) | ((o3 < 0) & (o4 > 0))).any())

    def contains(self, other: "_Ring") -> bool:
        """``other`` lies inside this ring (touching allowed) and is not the
        same ring: every vertex and edge midpoint inside or on the boundary,
        one strictly inside, and no edge crossing."""
        e = BOUNDARY_EPS_M
        if (other.lo < self.lo - e).any() or (other.hi > self.hi + e).any() \
                or set(other.ids) == set(self.ids):
            return False
        mid = (other.xy + np.roll(other.xy, -1, axis=0)) / 2
        where = self._locate(np.vstack([other.xy, mid]))
        if (where < 0).any() or not (where > 0).any():
            return False
        return not self._crosses(other)


def _rings(doc: PE.PatchDoc, frame: LocalFrame, ways) -> list[tuple[PE.Way, _Ring]]:
    out = []
    for way in ways:
        ids = list(way.refs[:-1] if way.closed else way.refs)
        if len(ids) < 3 or any(i not in doc.nodes for i in ids):
            continue
        rows = [doc.nodes[i] for i in ids]
        x, y = frame.metres([n[1] for n in rows], [n[2] for n in rows])
        out.append((way, _Ring(tuple(ids), np.column_stack([x, y]))))
    return out


class _Boxes:
    """The surfaces' bounding boxes and areas as arrays: the candidates for
    "contains" come from one vectorised test, not a loop over every pair."""

    def __init__(self, rings: list[_Ring]):
        self.rings = rings
        self.lo = np.array([r.lo for r in rings], dtype=float).reshape(-1, 2)
        self.hi = np.array([r.hi for r in rings], dtype=float).reshape(-1, 2)
        self.area = np.array([r.area for r in rings], dtype=float)

    def smallest_containing(self, inner: _Ring, pool=None,
                            larger_than: float | None = None) -> int | None:
        """The smallest ring (of ``pool``, else all) that contains ``inner``."""
        e = BOUNDARY_EPS_M
        ok = ((self.lo <= inner.lo + e) & (self.hi >= inner.hi - e)).all(axis=1)
        if larger_than is not None:
            ok &= self.area > larger_than
        cand = np.nonzero(ok)[0]
        if pool is not None:
            cand = np.intersect1d(cand, np.asarray(list(pool), dtype=int))
        for i in cand[np.argsort(self.area[cand], kind="stable")]:
            if self.rings[i].contains(inner):
                return int(i)
        return None


def assemble(doc: PE.PatchDoc, frame: LocalFrame | None = None) -> list[PreviewShape]:
    """Every surface of the document with its holes, in way order."""
    frame = frame or LocalFrame.of(doc)
    surfaces = _rings(doc, frame, [w for w in doc.ways if is_surface(w)])
    gaps = _rings(doc, frame, [w for w in doc.ways if is_gap_ring(w)])
    boxes = _Boxes([r for _w, r in surfaces])
    holes: list[list[tuple[int, ...]]] = [[] for _ in surfaces]
    gap_rings: list[list[_Ring]] = [[] for _ in surfaces]

    # 1. gap rings → the smallest containing surface (same shapeID first)
    for way, ring in gaps:
        sid = way.tags.get("shapeID")
        tagged = [] if sid is None else [i for i, (w, _r) in enumerate(surfaces)
                                         if w.tags.get("shapeID") == sid]
        host = boxes.smallest_containing(ring, tagged or None)
        if host is None and tagged:
            host = boxes.smallest_containing(ring)
        if host is not None:
            holes[host].append(ring.ids)
            gap_rings[host].append(ring)

    # 2. a surface nested in another is a hole of its direct parent
    for _w, inner in surfaces:
        parent = boxes.smallest_containing(inner, larger_than=inner.area)
        if parent is None or any(gr.contains(inner) for gr in gap_rings[parent]):
            continue
        holes[parent].append(inner.ids)
    return [PreviewShape(w.id, r.ids, tuple(h)) for (w, r), h in zip(surfaces, holes)]


#: One surface's triangles as node-id triples (the engine's own rule).
triangulate = face_triangles


@_dc.dataclass(frozen=True)
class ShapeMesh:
    """One surface's triangles as indices into its own vertex list (one
    vertex per node).  A node move rebuilds the positions only."""

    shape: PreviewShape
    vertex_ids: tuple[int, ...]
    indices: np.ndarray            # uint32, three per triangle, CCW from above

    @classmethod
    def of(cls, shape: PreviewShape, doc: PE.PatchDoc, frame: LocalFrame) -> "ShapeMesh":
        ids = [i for i in shape.node_ids if i in doc.nodes]
        x, y = frame.metres([doc.nodes[i][1] for i in ids], [doc.nodes[i][2] for i in ids])
        xy = {i: (float(a), float(b)) for i, a, b in zip(ids, x, y)}
        slot: dict[int, int] = {}
        order: list[int] = []
        out: list[int] = []
        for tri in triangulate(xy, shape.outer, shape.holes):
            (ax, ay), (bx, by), (cx, cy) = (xy[v] for v in tri)
            if (bx - ax) * (cy - ay) - (by - ay) * (cx - ax) < 0:
                tri = (tri[0], tri[2], tri[1])
            for v in tri:
                if v not in slot:
                    slot[v] = len(order)
                    order.append(v)
                out.append(slot[v])
        return cls(shape, tuple(order), np.asarray(out, dtype=np.uint32))


def mesh_shapes(shapes: _t.Iterable[PreviewShape], doc: PE.PatchDoc,
                frame: LocalFrame) -> dict[int, ShapeMesh]:
    return {s.way_id: ShapeMesh.of(s, doc, frame) for s in shapes}


class ShapeIndex:
    """Which shapes draw a node: a node edit rebuilds exactly these."""

    def __init__(self, meshes: _t.Mapping[int, ShapeMesh]):
        self.by_node: dict[int, set[int]] = {}
        for way, mesh in meshes.items():
            for nid in mesh.shape.node_ids:
                self.by_node.setdefault(nid, set()).add(way)

    def shapes_using(self, nodes: _t.Iterable[int]) -> set[int]:
        out: set[int] = set()
        for n in nodes:
            out |= self.by_node.get(n, set())
        return out


@_dc.dataclass(frozen=True)
class DocChange:
    """What an edit changed: node ids whose position or elevation moved
    (or that came or went), and whether any way's refs changed."""

    nodes: frozenset
    topology: bool


def diff_documents(before: PE.PatchDoc, after: PE.PatchDoc) -> DocChange:
    """The Qt model announces documents, not changes; the preview diffs the
    two immutable documents (unchanged nodes keep their tuples)."""
    a, b = before.nodes, after.nodes
    changed = {i for i, n in b.items() if a.get(i) is not n and a.get(i) != n}
    changed |= a.keys() - b.keys()
    topology = before.ways is not after.ways and (
        len(before.ways) != len(after.ways)
        or any(w0 is not w1 and (w0.id != w1.id or w0.refs != w1.refs)
               for w0, w1 in zip(before.ways, after.ways)))
    return DocChange(frozenset(changed), topology)
