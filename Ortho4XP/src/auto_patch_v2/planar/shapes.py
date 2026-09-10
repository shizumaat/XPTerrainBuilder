"""THE SHAPES (owner RULINGS 2026-09-08k; spec ``heca-v1-parity-spec.md``
§8; ``emit.toml [terrace]``): "if pavement is touching, or overlapping,
then it should be treated as a single shape, only separated by narrow
mouths / service roads; pavement separated by more than 0.5 m is a
separate apron or lot and could then have a wall / step between them; no
other steps are allowed in aprons — they must be solved by what their
connecting taxiways can serve."

THE NETWORK (owner RULINGS 2026-09-08p, amending 08k: "there are
multiple different aprons connected by taxiways, not a single apron").  A
face is NETWORK iff its role is of the runway family, or a taxi-centreline
breakline edge (``STATION_KIND``, the 1202 network) whose endpoints are
RUNWAY-CONNECTED lies on it (:func:`network_faces`): runway-connected =
in a connected component of the centreline breakline graph that holds a
vertex incident to a runway-family face or on a runway ridge — the planar
reading of ``constraints.routes.reach`` from the thresholds (this layer
may not import ``constraints``).  The network is never part of a shape:
it is hard at its route law and connects shapes by ROUTE only.  Every
vertex incident to a network face (the set ``N``) carries ``NO_SHAPE``:
an apron body's ring along the network is WELDED flush (its rows to the
body's interior are never dropped, no contour is drawn there, no gap
joint faces the network).  A centreline no runway reaches (an apron
taxilane, the 05w "junction" hangar aprons no route crosses) is part of
the body it lies in.

THE SHAPES.  A shape is a connected component of touching / overlapping
APRON-BODY pavement: the union of the ``shape_roles`` faces that are not
network (the apron-like roles, a taxi-family face no route reaches —
never a road, which SEPARATES), CLOSED
by ``separation_m`` (pavement closer than the owner's 0.5 m is one shape)
and OPENED by ``narrow_mouth_max_m``: the bodies of one component are the
connected parts of its erosion by half the mouth width, so a neck
narrower than the mouth, a point contact and a contact edge shorter than
the mouth all separate two bodies, while a wide neck (HECA pav132's 126 m)
joins them.  Every vertex of a shape-role face takes the body nearest to
it (the boundary falls across a neck's middle); A ROAD BETWEEN TWO SHAPES
BELONGS TO NEITHER (owner RULINGS 2026-09-08r-2, :func:`_label_roads`):
along a boundary it takes the level of the shape it is welded to (more
shared vertices) and the step stands at its far edge; crossing from one
shape to the other it is unlabelled and RAMPS along its length at its own
row law, no joint across it (``PlanarMap.road_ramps``);
a rigid pad's vertices take the pad's majority label (07c (3)); any other
vertex shared with pavement carries the pavement's label, the rest none.
A boundary edge inside the RUNWAY STRIP keep-out (06n: walls at runway
edges are never lawful, owner 2026-08-01) WELDS its two bodies — a shape
is an equivalence class, so the weld is transitive.

THE JOINTS.  A joint exists only between two shapes: (a) the label-
boundary CONTOUR through every face whose vertices carry two labels (the
face's constrained Delaunay triangulation marched: a triangle with two
boundary edges carries the segment between their midpoints, any other
mixed triangle joins its midpoints at its centroid — the contour
separates the disagreeing vertex sets and every priced chord across the
boundary crosses it, the census's allowance test); (b) a GAP joint — the
Voronoi midline between two shapes whose rings come within the step
readers' own contact horizon (``instrument.step_contact_tol_m``; a wider
gap is priced by no reader).  Both are declared in the sidecar
``terrace_joints`` (v1's record shape, ``pipeline/publication.py``) with
the BUILT step over their vertex pairs — no cap, no re-solve: joints are
geometric, known before the solve.  Inside a shape no joint exists and no
step is lawful.

The dependency law lets ``planar`` import law / model / airport / classify
only; the reach bands the pipeline reads beside the shapes stay there.
"""
from __future__ import annotations

from ..model.frame import rotated_rectangle

import dataclasses as _dc
import math
import typing as _t

import numpy as np
import shapely
from scipy.spatial import cKDTree
from shapely.geometry import LineString, Point, Polygon
from shapely.ops import linemerge, unary_union
from shapely.strtree import STRtree

from ..classify.evidence import polygon_parts
from ..classify.roles import Classification
from ..law import Law
from ..law.tables import family, is_rigid_role, snap_margin_m, zone2_half_width_m
from ..model.airport import Airport
from ..model.frame import XY
from ..model.planar import NO_SHAPE, PlanarMap, RoadRamp, ShapeJoint

__all__ = ["NO_SHAPE", "STATION_KIND", "RIDGE_KIND", "ShapeStats", "build_shapes", "network_faces", "network_vertices", "strip_keepout",
           "straddles", "straddles_pairs", "row_vertices", "row_test_pairs",
           "joint_planar_edges"]

#: Which breakline kind is the 1202 network (the route graph's stations).
STATION_KIND = "taxi_centerline"
#: The runway ridge breakline kind (``constraints.routes.RIDGE_KIND``): a root of the network.
RIDGE_KIND = "runway_profile"
#: A shape is a surface: fewer vertices than a polygon has is no shape (a
#: structural bound, never a law value).
MIN_SHAPE_VERTICES = 3


@_dc.dataclass
class ShapeStats:
    """What the labelling found (one line in the build log)."""

    faces: int = 0                  # shape-role faces (network included)
    network_faces: int = 0          # 08p: faces carrying a runway-connected centreline, or of the runway family
    network_by_role: dict[str, int] = _dc.field(default_factory=dict)
    network_vertices: int = 0       # the set N: every vertex incident to a network face
    body_faces: int = 0             # shape-role faces that are not network (the apron bodies)
    faces_unlabelled: int = 0       # body faces whose every vertex lies in N (welded whole)
    connected_stations: int = 0     # centreline vertices a runway reaches
    unconnected_station_edges: int = 0   # centreline edges no runway reaches (part of a body)
    components: int = 0             # connected pavement components (after the closing)
    bodies: int = 0                 # bodies after the opening (components with one body count one)
    shapes: int = 0                 # distinct shape ids after the strip welds
    vertices_labelled: int = 0
    road_vertices_labelled: int = 0
    road_vertices_relabelled: int = 0   # 08r-2: a body's vertex on an along road taking the road's shape
    road_vertices_unlabelled: int = 0   # 08r-2: a crossing road's contact vertices freed
    roads_along: int = 0                # road faces running along one shape (its level)
    roads_crossing: int = 0             # road faces crossing from one shape to another (a ramp)
    road_ramps: int = 0                 # the ramps declared (crossings whose two shapes stayed distinct)
    pads_relabelled: int = 0
    welded_strip_pairs: int = 0     # body pairs welded by a boundary edge inside the runway strip
    welded_route_pairs: int = 0     # body pairs welded by a boundary edge on a taxi centreline (a mouth a route passes through)
    joint_edges: int = 0            # planar edges whose endpoints carry two shapes
    joint_edges_by_roles: dict[str, int] = _dc.field(default_factory=dict)
    contours: int = 0               # declared label-boundary polylines
    contour_length_m: float = 0.0
    dangling_faces: int = 0
    gap_joints: int = 0             # declared gap midlines
    gap_length_m: float = 0.0
    by_shape: list[list] = _dc.field(default_factory=list)   # [id, faces, area m2, vertices, roles]
    wall_s: float = 0.0


def strip_keepout(classification: Classification, law: Law):
    """The RUNWAY STRIP keep-out: every runway-family cell's long axis,
    extended by the end-skirt corridor at both ends, buffered to the
    zone-2 (strip) half width — a joint touching it is never declared."""
    polys = []
    rw_roles = set(law.tables.precedence.runway_family.members)
    cl = law.ruleset.end_skirt.corridor_length_m
    for c in classification.cells:
        if c.role not in rw_roles or len(c.ring) < 3:
            continue
        poly = Polygon(c.ring)
        if poly.is_empty or poly.area <= 0.0:
            continue
        half = zone2_half_width_m(law, "runway", c.code_number, c.code_letter) or 0.0
        end = (cl.value(c.code_number, c.code_letter) if cl is not None else 0.0) or 0.0
        rect = rotated_rectangle(poly)
        pts = list(rect.exterior.coords)[:4]
        if len(pts) < 4:
            polys.append(poly.buffer(half))
            continue
        sides = [(math.hypot(pts[k + 1][0] - pts[k][0], pts[k + 1][1] - pts[k][1]), k)
                 for k in range(3)] + [(math.hypot(pts[0][0] - pts[3][0], pts[0][1] - pts[3][1]), 3)]
        _l, k = max(sides)
        p, q = pts[k], pts[(k + 1) % 4]
        r, s = pts[(k + 3) % 4], pts[(k + 2) % 4]
        a = ((p[0] + r[0]) / 2.0, (p[1] + r[1]) / 2.0)
        b = ((q[0] + s[0]) / 2.0, (q[1] + s[1]) / 2.0)
        L = math.hypot(b[0] - a[0], b[1] - a[1])
        if L <= 0.0:
            polys.append(poly.buffer(half))
            continue
        ux, uy = (b[0] - a[0]) / L, (b[1] - a[1]) / L
        axis = LineString([(a[0] - ux * end, a[1] - uy * end), (b[0] + ux * end, b[1] + uy * end)])
        width = max(half, poly.area / max(L, 1.0) / 2.0)
        polys.append(axis.buffer(width, cap_style="flat").union(poly.buffer(half)))
    return unary_union(polys) if polys else None


def _face_polygon(pm: PlanarMap, fid: int) -> Polygon | None:
    f = pm.faces[fid]
    ring = [pm.vertices[v].xy for v in pm.ring_vertices(f.ring)]
    if len(ring) < 3:
        return None
    holes = [[pm.vertices[v].xy for v in pm.ring_vertices(h)] for h in f.holes]
    p = Polygon(ring, [h for h in holes if len(h) >= 3])
    if not p.is_valid:
        p = p.buffer(0)
    return None if p.is_empty or p.area <= 0.0 else p


def _face_vertices(pm: PlanarMap, fid: int) -> list[int]:
    f = pm.faces[fid]
    return [v for cyc in (f.ring, *f.holes) for v in pm.ring_vertices(cyc)]


class _Union:
    """Union-find over shape ids (the strip weld is transitive)."""

    def __init__(self) -> None:
        self.parent: dict[int, int] = {}

    def find(self, x: int) -> int:
        p = self.parent.setdefault(x, x)
        while p != x:
            self.parent[x] = self.parent.setdefault(p, p)
            x = p
            p = self.parent[x]
        return x

    def union(self, a: int, b: int) -> bool:
        ra, rb = self.find(a), self.find(b)
        if ra == rb:
            return False
        self.parent[max(ra, rb)] = min(ra, rb)
        return True


def network_faces(pm: PlanarMap, law: Law, stats: ShapeStats | None = None
                  ) -> tuple[frozenset[int], frozenset[int]]:
    """THE NETWORK PREDICATE (module docstring; owner RULINGS 2026-09-08p):
    ``(network face ids, N)`` — the faces of the runway family and the
    faces a runway-connected taxi-centreline breakline edge lies on, and
    every vertex incident to one of them."""
    st = stats if stats is not None else ShapeStats()
    rw_fam = set(law.tables.precedence.runway_family.members)
    roots: set[int] = set()
    for fid, f in pm.faces.items():
        if f.role in rw_fam:
            roots.update(_face_vertices(pm, fid))
    uf = _Union()
    station_edges: list[int] = []
    for b in pm.breaklines.values():
        if b.kind == RIDGE_KIND:
            roots.update(b.vertices(pm))
        if b.kind != STATION_KIND:
            continue
        for eid in b.edges:
            e = pm.edges[eid]
            uf.union(e.a, e.b)
            station_edges.append(eid)
    connected_roots = {uf.find(v) for v in roots if v in uf.parent}
    # the network is the TAXI FAMILY (08p (2): "taxi-family faces that carry
    # a runway-connected route — taxiways, real junctions, stubs, connectors")
    # and the runway's; an apron a route runs onto (a 1202 taxilane ending
    # inside it) stays a BODY — the route's chain rows are hard through it
    # and the body conforms (08k (3)); a zone face a dangling end crosses
    # is nobody's
    pav = set(law.tables.precedence.taxi_family.members) | rw_fam
    net: set[int] = {fid for fid, f in pm.faces.items() if f.role in rw_fam}
    n_conn_v: set[int] = set()
    for eid in station_edges:
        e = pm.edges[eid]
        if uf.find(e.a) in connected_roots and uf.find(e.b) in connected_roots:
            n_conn_v.update((e.a, e.b))
            net.update(f for f in (e.left_face, e.right_face)
                       if f is not None and pm.faces[f].role in pav)
        else:
            st.unconnected_station_edges += 1
    N: set[int] = set()
    for fid in net:
        N.update(_face_vertices(pm, fid))
        st.network_by_role[pm.faces[fid].role] = st.network_by_role.get(pm.faces[fid].role, 0) + 1
    st.network_faces = len(net)
    st.network_vertices = len(N)
    st.connected_stations = len(n_conn_v)
    return frozenset(net), frozenset(N)


def network_vertices(pm: PlanarMap, law: Law) -> frozenset[int]:
    """The set ``N`` alone (the yield transform's reader)."""
    return network_faces(pm, law)[1]


def _label_pavement(pm: PlanarMap, law: Law, stats: ShapeStats, net: frozenset[int], N: frozenset[int]
                    ) -> tuple[dict[int, int], dict[int, Polygon]]:
    """The shape label of every shape-role face vertex (module docstring)
    and each body's polygon.  The connectivity union carries the rigid
    pads too (a hangar floor is level with the apron it stands on, RULINGS
    2026-09-03h: pavement is not parted by a building), so a passage
    between two pads never reads as a mouth.  Faces are labelled
    COHERENTLY: a face inside one body's reach (the body dilated back by
    half the mouth width) takes that body; a face spanning two bodies — a
    neck — splits its vertices by the nearest body; a face beyond every
    body's reach (a spur thinner than the mouth) inherits the label of the
    faces it shares vertices with, never a body across a gap."""
    tt = law.tables.emit.terrace
    roles = set(tt.shape_roles)
    all_fids = [fid for fid, f in pm.faces.items() if f.role in roles]
    stats.faces = len(all_fids)
    fids = [fid for fid in all_fids if fid not in net]           # 08p: the apron bodies only
    stats.body_faces = len(fids)
    polys = {fid: p for fid in fids if (p := _face_polygon(pm, fid)) is not None}
    if not polys:
        return {}, {}
    rigid = [p for fid, f in pm.faces.items() if is_rigid_role(law, f.role) and fid not in polys
             and fid not in net if (p := _face_polygon(pm, fid)) is not None]
    U = unary_union(list(polys.values()) + rigid)
    s = tt.separation_m
    if s > 0.0:
        U = U.buffer(s / 2.0).buffer(-s / 2.0)          # closing: pavement under the separation is one
    comps = [c for c in polygon_parts(U) if c.area > 0.0]
    stats.components = len(comps)
    half = tt.narrow_mouth_max_m / 2.0
    bodies: dict[int, Polygon] = {}
    reach: dict[int, Polygon] = {}
    for comp in comps:
        parts = [b for b in polygon_parts(comp.buffer(-half)) if b.area > 0.0]
        # a BODY is wider than a mouth on its own account: a part that does
        # not survive a second erosion by the same half-width is the remnant
        # of a spur a hair wider than the mouth, not a body (measured HECA
        # 2026-09-08: 85 / 51 / 42 m2 remnants beside the 3.7 km2 airside)
        parts = [b for b in parts if not b.buffer(-half).is_empty]
        if len(parts) >= 2:
            for b in parts:
                bodies[len(bodies)] = b
                reach[len(bodies) - 1] = b.buffer(half + s).intersection(comp)
        else:
            bodies[len(bodies)] = comp
            reach[len(bodies) - 1] = comp
    stats.bodies = len(bodies)
    rtree = STRtree([reach[i] for i in sorted(reach)])
    rids = sorted(reach)
    label: dict[int, int] = {}
    pending: list[int] = []
    necks: list[tuple[int, list[int]]] = []
    hits_of: dict[int, list[int]] = {}
    for fid, poly in polys.items():
        hits = [rids[int(k)] for k in rtree.query(poly, predicate="intersects")]
        hits_of[fid] = [i for i in hits if reach[i].intersection(poly).area > 0.0]
    # single-body faces first: a vertex shared with a face wholly inside one
    # body belongs to that body whatever a neck face beside it would say
    for fid, hits in hits_of.items():
        if len(hits) == 1:
            for v in _face_vertices(pm, fid):
                if v not in N:
                    label[v] = hits[0]
        elif len(hits) >= 2:
            necks.append((fid, hits))
        else:
            pending.append(fid)
    for fid, hits in necks:
        vs = [v for v in _face_vertices(pm, fid) if v not in label and v not in N]
        if not vs:
            continue
        btree = STRtree([bodies[i] for i in hits])
        near = np.asarray(btree.nearest(shapely.points([pm.vertices[v].xy for v in vs]))).reshape(-1)
        for v, k in zip(vs, near):
            label[v] = hits[int(k)]
    # spurs: inherit through shared vertices, to a fixed point
    stats.faces_unlabelled = sum(1 for fid in polys if all(v in N for v in _face_vertices(pm, fid)))
    pending = [fid for fid in pending if not all(v in N for v in _face_vertices(pm, fid))]
    while pending:
        progressed = False
        rest: list[int] = []
        for fid in pending:
            vs = _face_vertices(pm, fid)
            ls = [label[v] for v in vs if v in label]
            if not ls:
                rest.append(fid)
                continue
            top = max(set(ls), key=lambda l: (ls.count(l), -l))
            for v in vs:
                if v not in N:
                    label.setdefault(v, top)
            progressed = True
        pending = rest
        if not progressed:
            break
    if pending:                                     # nothing shared: the nearest body
        btree = STRtree([bodies[i] for i in sorted(bodies)])
        bids = sorted(bodies)
        for fid in pending:
            vs = [v for v in _face_vertices(pm, fid) if v not in N]
            if not vs:
                continue
            near = np.asarray(btree.nearest(shapely.points([pm.vertices[v].xy for v in vs]))).reshape(-1)
            for v, k in zip(vs, near):
                label.setdefault(v, bids[int(k)])
    # a label with fewer vertices than a polygon has is no surface: its
    # vertices join the label of their nearest other labelled vertex
    count: dict[int, int] = {}
    for l in label.values():
        count[l] = count.get(l, 0) + 1
    small = {l for l, n in count.items() if n < MIN_SHAPE_VERTICES}
    if small and len(count) > len(small):
        keep = [v for v, l in label.items() if l not in small]
        tree = cKDTree([pm.vertices[v].xy for v in keep])
        for v, l in list(label.items()):
            if l in small:
                _d, j = tree.query(pm.vertices[v].xy)
                label[v] = label[keep[int(j)]]
    return label, bodies


def _road_axis(pm: PlanarMap, fid: int) -> tuple[float, float] | None:
    """The road's own direction (``constraints.geometry.long_axis``'s
    minimum-area rectangle, re-derived here: the planar layer may not import
    ``constraints``)."""
    pts = [pm.vertices[v].xy for v in pm.ring_vertices(pm.faces[fid].ring)]
    if len(pts) < 3:
        return None
    best: tuple[float, tuple[float, float]] | None = None
    for i in range(len(pts)):
        (ax, ay), (bx, by) = pts[i], pts[(i + 1) % len(pts)]
        L = math.hypot(bx - ax, by - ay)
        if L < 1e-9:
            continue
        ux, uy = (bx - ax) / L, (by - ay) / L
        us = [x * ux + y * uy for x, y in pts]
        vs = [-x * uy + y * ux for x, y in pts]
        w, h = max(us) - min(us), max(vs) - min(vs)
        if best is None or w * h < best[0]:
            best = (w * h, (ux, uy) if w >= h else (-uy, ux))
    return None if best is None else best[1]


def _label_roads(pm: PlanarMap, law: Law, label: dict[int, int], N: frozenset[int],
                 stats: ShapeStats) -> list[RoadRamp]:
    """A ROAD BETWEEN TWO SHAPES BELONGS TO NEITHER (owner RULINGS
    2026-09-08r-2).  Per road-family face, its CONTACTS are the vertices
    the pavement labelling already labelled (shared with a body's face).
    One contact shape — or none: the nearest labelled vertex's shape, by
    majority — and the road runs ALONG it: every vertex takes that shape.
    Two or more: the two most-shared shapes A and B, their contacts
    projected on the road's long axis.  Overlapping intervals → the road
    runs ALONG the boundary: every vertex takes A (the more shared), the
    ones shared with B included, so the step stands at the road's FAR edge
    (B's faces along it carry two labels and the contour hugs their edge
    inside B).  Disjoint intervals → the road CROSSES from A to B: every
    vertex is UNLABELLED — its rows all survive the filter and it RAMPS
    along its length at its own row law (the ``roads`` yield ceiling = the
    core clamp), no contour crosses it, the two shapes step elsewhere; a
    :class:`RoadRamp` records it for the report (a road too short to ramp
    the difference is named).  A vertex in ``N`` is never labelled."""
    roads = set(family(law, "road_cross_section").roles)
    ids = sorted(label)
    tree = cKDTree([pm.vertices[v].xy for v in ids]) if ids else None
    tol = law.tables.emit.identity.min_distinct_spacing_m
    face_vs: dict[int, list[int]] = {}         # road face -> its vertices off the network
    contacts_of: dict[int, dict[int, list[int]]] = {}   # road face -> shape -> contact vertices
    choice: dict[int, int] = {}                # road face -> the shape it runs along
    crossing_faces: set[int] = set()
    ramps: list[RoadRamp] = []

    def centroid(vs: _t.Sequence[int]) -> XY:
        xs = [pm.vertices[v].xy for v in vs]
        return (sum(x for x, _y in xs) / len(xs), sum(y for _x, y in xs) / len(xs))

    for fid, f in pm.faces.items():
        if f.role not in roads:
            continue
        vs = [v for v in _face_vertices(pm, fid) if v not in N]
        if not vs:
            continue
        face_vs[fid] = vs
        contacts: dict[int, list[int]] = {}
        for v in vs:
            if v in label:
                contacts.setdefault(label[v], []).append(v)
        contacts_of[fid] = contacts
        if not contacts:
            if tree is None:
                continue
            near = [label[ids[int(tree.query(pm.vertices[v].xy)[1])]] for v in vs]
            choice[fid] = max(set(near), key=lambda l: (near.count(l), -l))
            continue
        ranked = sorted(contacts, key=lambda l: (-len(contacts[l]), l))
        a = ranked[0]
        if len(ranked) >= 2:
            b = ranked[1]
            axis = _road_axis(pm, fid)
            if axis is not None:
                ux, uy = axis
                pa = [pm.vertices[v].xy[0] * ux + pm.vertices[v].xy[1] * uy for v in contacts[a]]
                pb = [pm.vertices[v].xy[0] * ux + pm.vertices[v].xy[1] * uy for v in contacts[b]]
                overlap = min(max(pa), max(pb)) - max(min(pa), min(pb))
                if overlap < tol:                       # disjoint along the axis: a crossing
                    crossing_faces.add(fid)
                    ramps.append(RoadRamp(fid, f.ref, (a, b), tuple(sorted(contacts[a])),
                                          tuple(sorted(contacts[b])),
                                          abs(sum(pa) / len(pa) - sum(pb) / len(pb))))
                    continue
        choice[fid] = a
    # A ROAD NEVER CARRIES A JOINT (08r-2): two road faces sharing an edge
    # or a vertex while running along DIFFERENT shapes would put the step
    # between them — a wall across the road (HECA route8 in six pieces,
    # 2026-09-08) — so the pair is a crossing: both unlabelled, the ramp
    # from the one's contacts to the other's
    face_of_v: dict[int, list[int]] = {}
    for fid, vs in face_vs.items():
        for v in vs:
            face_of_v.setdefault(v, []).append(fid)
    pairs: set[tuple[int, int]] = set()
    for v, fids in face_of_v.items():
        for fa in fids:
            for fb in fids:
                if fa < fb and fa in choice and fb in choice and choice[fa] != choice[fb]:
                    pairs.add((fa, fb))
    for fa, fb in sorted(pairs):
        la, lb = choice[fa], choice[fb]
        ca = contacts_of[fa].get(la, [])
        cb = contacts_of[fb].get(lb, [])
        if fa not in crossing_faces or fb not in crossing_faces:
            if ca and cb:
                ga, gb = centroid(ca), centroid(cb)
                ramps.append(RoadRamp(fa, pm.faces[fa].ref, (la, lb), tuple(sorted(ca)), tuple(sorted(cb)),
                                      math.hypot(ga[0] - gb[0], ga[1] - gb[1])))
        crossing_faces.update((fa, fb))
    crossing: set[int] = {v for fid in crossing_faces for v in face_vs[fid]}
    stats.roads_crossing += len(crossing_faces)
    stats.roads_along += sum(1 for fid in choice if fid not in crossing_faces)
    for fid, l in choice.items():
        if fid in crossing_faces:
            continue
        for v in face_vs[fid]:
            if v in crossing:
                continue
            if v not in label:
                stats.road_vertices_labelled += 1
            elif label[v] != l:
                stats.road_vertices_relabelled += 1
            label[v] = l
    for v in crossing:
        if v in label:
            del label[v]
            stats.road_vertices_unlabelled += 1
    return ramps


def _label_others(pm: PlanarMap, law: Law, label: dict[int, int], N: frozenset[int],
                  stats: ShapeStats) -> list[RoadRamp]:
    """Roads (:func:`_label_roads`); rigid pads by their majority (module
    docstring); a vertex in ``N`` never."""
    if not label:
        return []
    ramps = _label_roads(pm, law, label, N, stats)
    for fid, f in pm.faces.items():
        if not is_rigid_role(law, f.role):
            continue
        vs = _face_vertices(pm, fid)
        ls = [label[v] for v in vs if v in label]
        if not ls or len(set(ls)) == 1:
            continue
        top = max(set(ls), key=lambda l: (ls.count(l), -l))
        for v in vs:
            if v in label:
                label[v] = top
        stats.pads_relabelled += 1
    return ramps


def _weld_strip(pm: PlanarMap, label: dict[int, int], keep, stats: ShapeStats) -> _Union:
    """THE STRIP KEEP-OUT: a boundary edge inside it welds its two bodies.
    THE ROUTE IS NEVER CUT (RULINGS 2026-09-07g, kept): a boundary edge
    lying on a taxi centreline — a mouth a route passes through — welds
    its two bodies too: the route's chain rows are hard on both sides, so
    the connecting taxiway serves both (08k: "solved by what their
    connecting taxiways can serve"), and a declared step across a route
    is the oracle's ``terrace_joint_route`` violation."""
    uf = _Union()
    for b in pm.breaklines.values():
        if b.kind != STATION_KIND:
            continue
        for eid in b.edges:
            e = pm.edges[eid]
            la, lb = label.get(e.a, NO_SHAPE), label.get(e.b, NO_SHAPE)
            if la != lb and la != NO_SHAPE and lb != NO_SHAPE and uf.union(la, lb):
                stats.welded_route_pairs += 1
    if keep is not None and not keep.is_empty:
        shapely.prepare(keep)
        for e in pm.edges.values():
            la, lb = label.get(e.a, NO_SHAPE), label.get(e.b, NO_SHAPE)
            if la == lb or la == NO_SHAPE or lb == NO_SHAPE or uf.find(la) == uf.find(lb):
                continue
            if keep.intersects(LineString([pm.vertices[e.a].xy, pm.vertices[e.b].xy])):
                uf.union(la, lb)
                stats.welded_strip_pairs += 1
    for v in label:
        label[v] = uf.find(label[v])
    return uf


def straddles(pm: PlanarMap, ids: _t.Iterable[int]) -> bool:
    """Whether the vertices ``ids`` carry two different shapes."""
    seen = NO_SHAPE
    for v in ids:
        lv = pm.shape_of_vertex.get(v, NO_SHAPE)
        if lv == NO_SHAPE:
            continue
        if seen == NO_SHAPE:
            seen = lv
        elif lv != seen:
            return True
    return False


def straddles_pairs(pm: PlanarMap, pairs: _t.Iterable[tuple[int, int]]) -> bool:
    """Whether any of the vertex ``pairs`` carries two shapes."""
    return any(straddles(pm, p) for p in pairs)


def row_vertices(row) -> tuple[int, ...]:
    """The vertex ids a constraint row touches (duck-typed on the record)."""
    if hasattr(row, "terms"):
        return tuple(v for v, _c in row.terms)
    if hasattr(row, "group"):
        return tuple(row.group)
    if hasattr(row, "a"):
        return (row.a, row.b)
    return (row.v,)


def row_test_pairs(row) -> list[tuple[int, int]] | None:
    """The vertex pairs the census READS a row by (``None``: every pair of
    its vertices).  A second-difference CHAIN row — three terms, one
    negative coefficient equal to the sum of the other two: the §1.2 rate,
    the strip arc rate — is read by its two consecutive segments, never by
    its ends (CYXY 2026-09-07: junction #126 ring 2658-2659-2660, 348
    no_step rows dropped, one 3.0 % rate read)."""
    terms = getattr(row, "terms", None)
    if terms is None or len(terms) != 3:
        return None
    neg = [i for i, (_v, c) in enumerate(terms) if c < 0.0]
    if len(neg) != 1:
        return None
    pos = [i for i in range(3) if i != neg[0]]
    scale = max(abs(c) for _v, c in terms)
    if abs(terms[neg[0]][1] + terms[pos[0]][1] + terms[pos[1]][1]) > 1e-9 * scale:
        return None
    b = terms[neg[0]][0]
    return [(terms[pos[0]][0], b), (b, terms[pos[1]][0])]


def joint_planar_edges(pm: PlanarMap) -> list[tuple[int, int, str, str]]:
    """Every planar edge whose endpoints carry two shapes, with the roles
    on its two sides."""
    out: list[tuple[int, int, str, str]] = []
    for e in pm.edges.values():
        if not straddles(pm, (e.a, e.b)):
            continue
        roles = sorted(pm.faces[f].role for f in (e.left_face, e.right_face) if f is not None)
        out.append((e.a, e.b, roles[0], roles[-1]))
    return out


def _face_contour(pm: PlanarMap, fid: int, label: _t.Mapping[int, int]
                  ) -> tuple[list[LineString], list[tuple[int, int]], bool]:
    """The label-boundary contour of one face (module docstring)."""
    poly = _face_polygon(pm, fid)
    if poly is None:
        return [], [], False
    ids: dict[tuple[float, float], int] = {}
    for v in _face_vertices(pm, fid):
        x, y = pm.vertices[v].xy
        ids[(round(x, 6), round(y, 6))] = v
    try:
        tris = shapely.constrained_delaunay_triangles(poly)
    except Exception:
        return [], [], False
    segs: list[LineString] = []
    pairs: set[tuple[int, int]] = set()
    dangling = False
    for tri in getattr(tris, "geoms", ()):
        c = list(tri.exterior.coords)[:3]
        vs = [ids.get((round(x, 6), round(y, 6))) for x, y in c]
        if any(v is None for v in vs):
            continue
        mids = []
        for i in range(3):
            a, b = vs[i], vs[(i + 1) % 3]
            la, lb = label.get(a, NO_SHAPE), label.get(b, NO_SHAPE)
            if la != lb and la != NO_SHAPE and lb != NO_SHAPE:
                (xa, ya), (xb, yb) = c[i], c[(i + 1) % 3]
                mids.append((0.5 * (xa + xb), 0.5 * (ya + yb)))
                pairs.add((min(a, b), max(a, b)))
        if len(mids) == 2:
            segs.append(LineString(mids))
        elif mids:
            dangling = True
            cx = sum(x for x, _y in c) / 3.0
            cy = sum(y for _x, y in c) / 3.0
            for m in mids:
                segs.append(LineString([m, (cx, cy)]))
    return segs, sorted(pairs), dangling


def _extended(pts: list[XY], eps: float) -> list[XY]:
    """``pts`` with both ends pushed ``eps`` outward: a contour ends at the
    midpoint of a boundary edge and the census's crossing test against a
    point a rounding away from that edge is a coin toss; past it the
    crossing is proper."""
    if eps <= 0.0 or len(pts) < 2:
        return pts
    (x0, y0), (x1, y1) = pts[0], pts[1]
    L = math.hypot(x1 - x0, y1 - y0)
    if L > 0.0:
        pts = [(x0 - (x1 - x0) / L * eps, y0 - (y1 - y0) / L * eps)] + pts[1:]
    (x0, y0), (x1, y1) = pts[-2], pts[-1]
    L = math.hypot(x1 - x0, y1 - y0)
    if L > 0.0:
        pts = pts[:-1] + [(x1 + (x1 - x0) / L * eps, y1 + (y1 - y0) / L * eps)]
    return pts


def _joints_from(pm: PlanarMap, segs: list[LineString], pairs: list[tuple[int, int]],
                 to_ll, extend_m: float, start: int, gap: bool) -> list[ShapeJoint]:
    """Merge contour segments into polylines, each carrying the vertex
    pairs whose midpoints lie on it."""
    if not segs:
        return []
    merged = linemerge(unary_union(segs))
    lines = list(getattr(merged, "geoms", [merged]))
    pairs = sorted(set(pairs))
    mids = np.array([[0.5 * (pm.vertices[a].xy[0] + pm.vertices[b].xy[0]),
                      0.5 * (pm.vertices[a].xy[1] + pm.vertices[b].xy[1])] for a, b in pairs]) \
        if pairs else np.zeros((0, 2))
    tree = STRtree(shapely.points(mids)) if len(mids) else None
    label = pm.shape_of_vertex
    out: list[ShapeJoint] = []
    for line in lines:
        pts = [(float(x), float(y)) for x, y in line.coords]
        if len(pts) < 2:
            continue
        near = 1e-6 if not gap else max(extend_m, 1e-6)
        on = [pairs[int(k)] for k in tree.query(line, predicate="dwithin", distance=near)] \
            if tree is not None else []
        roles = sorted({pm.faces[f].role for a, b in on for f in
                        (set(pm.vertices[a].incident_faces) | set(pm.vertices[b].incident_faces))})
        labs = sorted({label.get(v, NO_SHAPE) for a, b in on for v in (a, b)} - {NO_SHAPE})
        shapes = (labs[0], labs[-1]) if labs else (NO_SHAPE, NO_SHAPE)
        pts = _extended(pts, extend_m)
        out.append(ShapeJoint(start + len(out), tuple(pts),
                              tuple(tuple(map(float, to_ll(x, y))) for x, y in pts),
                              tuple(on), float(line.length), tuple(roles), shapes, gap))
    return out


def _contour_joints(pm: PlanarMap, label: _t.Mapping[int, int], to_ll, extend_m: float,
                    stats: ShapeStats) -> list[ShapeJoint]:
    segs: list[LineString] = []
    pairs: list[tuple[int, int]] = []
    for fid in pm.faces:
        labs = {label.get(v, NO_SHAPE) for v in _face_vertices(pm, fid)} - {NO_SHAPE}
        if len(labs) < 2:
            continue
        s, p, dangling = _face_contour(pm, fid, label)
        segs.extend(s)
        pairs.extend(p)
        if dangling:
            stats.dangling_faces += 1
    out = _joints_from(pm, segs, pairs, to_ll, extend_m, 0, False)
    stats.contours = len(out)
    stats.contour_length_m = sum(j.length_m for j in out)
    return out


def _gap_joints(pm: PlanarMap, law: Law, label: _t.Mapping[int, int], to_ll, extend_m: float,
                start: int, stats: ShapeStats, net: frozenset[int] = frozenset()) -> list[ShapeJoint]:
    """THE GAP JOINTS (module docstring): for two shapes whose ring edges
    come within the readers' contact horizon of each other without
    sharing a face, the Voronoi midline between the facing edges
    (densified at the horizon so a long edge is represented along its
    length), clipped to the corridor between them."""
    tol = law.tables.emit.instrument.step_contact_tol_m
    roles = set(law.tables.emit.terrace.shape_roles)
    ring_edges: list[LineString] = []
    edge_label: list[int] = []
    edge_ends: list[tuple[int, int]] = []
    for fid, f in pm.faces.items():
        if f.role not in roles or fid in net:               # 08p: never between a shape and the network
            continue
        for cyc in (f.ring, *f.holes):
            vs = pm.ring_vertices(cyc)
            for a, b in zip(vs, vs[1:] + vs[:1]):
                la, lb = label.get(a, NO_SHAPE), label.get(b, NO_SHAPE)
                if la == NO_SHAPE or la != lb:
                    continue
                ring_edges.append(LineString([pm.vertices[a].xy, pm.vertices[b].xy]))
                edge_label.append(la)
                edge_ends.append((a, b))
    if len(set(edge_label)) < 2:
        return []
    tree = STRtree(ring_edges)
    hit = tree.query(ring_edges, predicate="dwithin", distance=tol)
    near: dict[tuple[int, int], set[int]] = {}      # (shape a, shape b) -> facing edges of both
    for i, j in zip(hit[0], hit[1]):
        i, j = int(i), int(j)
        la, lb = edge_label[i], edge_label[j]
        if la == lb:
            continue
        (a, b), (c, d) = edge_ends[i], edge_ends[j]
        fi = set(pm.vertices[a].incident_faces) | set(pm.vertices[b].incident_faces)
        if fi & (set(pm.vertices[c].incident_faces) | set(pm.vertices[d].incident_faces)):
            continue                                # a shared face: the contour's case
        near.setdefault((min(la, lb), max(la, lb)), set()).update((i, j))
    out: list[ShapeJoint] = []
    for (la, lb), eids in sorted(near.items()):
        side = {la: [ring_edges[e] for e in eids if edge_label[e] == la],
                lb: [ring_edges[e] for e in eids if edge_label[e] == lb]}
        if not side[la] or not side[lb]:
            continue
        P: list[XY] = []
        labs: list[int] = []
        for lab, lines in side.items():
            for ln in lines:
                for x, y in shapely.segmentize(ln, tol).coords:
                    P.append((float(x), float(y)))
                    labs.append(lab)
        if len(P) < 3:
            continue
        try:
            cells = list(getattr(shapely.voronoi_polygons(shapely.multipoints(P)), "geoms", []))
        except Exception:
            continue
        if not cells:
            continue
        ptree = STRtree(shapely.points(P))
        cell_lab = []
        for c in cells:
            inside = ptree.query(c, predicate="covers")
            cell_lab.append(labs[int(inside[0])] if len(inside) else NO_SHAPE)
        lens = unary_union(side[la]).buffer(tol).intersection(unary_union(side[lb]).buffer(tol))
        segs: list[LineString] = []
        ctree = STRtree(cells)
        for i, c in enumerate(cells):
            for j in ctree.query(c, predicate="touches"):
                j = int(j)
                if j <= i or cell_lab[i] == cell_lab[j] or NO_SHAPE in (cell_lab[i], cell_lab[j]):
                    continue
                shared = c.intersection(cells[j]).intersection(lens)
                for g in getattr(shared, "geoms", [shared]):
                    if g.geom_type == "LineString" and g.length > 0.0:
                        segs.append(g)
        # the pairs across the gap: each facing vertex against its nearest
        # vertex of the other shape within the horizon
        va = sorted({v for e in eids if edge_label[e] == la for v in edge_ends[e]})
        vb = sorted({v for e in eids if edge_label[e] == lb for v in edge_ends[e]})
        tb = cKDTree([pm.vertices[v].xy for v in vb])
        pairs: list[tuple[int, int]] = []
        for v in va:
            d, k = tb.query(pm.vertices[v].xy)
            if d <= 2.0 * tol:
                u = vb[int(k)]
                pairs.append((min(v, u), max(v, u)))
        out.extend(_joints_from(pm, segs, pairs, to_ll, extend_m, start + len(out), True))
    stats.gap_joints = len(out)
    stats.gap_length_m = sum(j.length_m for j in out)
    return out


def build_shapes(pm: PlanarMap, law: Law, airport: Airport,
                 classification: Classification | None = None
                 ) -> tuple[PlanarMap, ShapeStats]:
    """``pm`` with ``shape_of_vertex`` / ``shape_of_face`` / ``shape_joints``
    filled (module docstring)."""
    import time
    t0 = time.perf_counter()
    stats = ShapeStats()
    net, N = network_faces(pm, law, stats)
    label, _bodies = _label_pavement(pm, law, stats, net, N)
    if not label:
        stats.wall_s = time.perf_counter() - t0
        return pm, stats
    ramps = _label_others(pm, law, label, N, stats)
    keep = strip_keepout(classification, law) if classification is not None else None
    uf = _weld_strip(pm, label, keep, stats)
    # the record: dense shape ids in order of first appearance by area rank
    of_face: dict[int, int] = {}
    area: dict[int, float] = {}
    nfaces: dict[int, int] = {}
    roles_of: dict[int, set[str]] = {}
    for fid, f in pm.faces.items():
        ls = [label[v] for v in _face_vertices(pm, fid) if v in label]
        if not ls:
            continue
        top = max(set(ls), key=lambda l: (ls.count(l), -l))
        of_face[fid] = top
        if f.role in set(law.tables.emit.terrace.shape_roles):
            poly = _face_polygon(pm, fid)
            area[top] = area.get(top, 0.0) + (poly.area if poly is not None else 0.0)
            nfaces[top] = nfaces.get(top, 0) + 1
            roles_of.setdefault(top, set()).add(f.role)
    order = sorted(set(label.values()), key=lambda l: (-area.get(l, 0.0), l))
    dense = {l: k for k, l in enumerate(order)}
    label = {v: dense[l] for v, l in label.items()}
    of_face = {fid: dense[l] for fid, l in of_face.items()}
    # the ramps' shapes through the welds and the dense ids (a ramp whose
    # two shapes welded into one is no ramp: the road runs inside it)
    ramps = [_dc.replace(r, shapes=(dense[uf.find(r.shapes[0])], dense[uf.find(r.shapes[1])]))
             for r in ramps if uf.find(r.shapes[0]) in dense and uf.find(r.shapes[1]) in dense]
    ramps = [r for r in ramps if r.shapes[0] != r.shapes[1]]
    stats.shapes = len(order)
    stats.vertices_labelled = len(label)
    nverts: dict[int, int] = {}
    for l in label.values():
        nverts[l] = nverts.get(l, 0) + 1
    stats.by_shape = [[dense[l], nfaces.get(l, 0), round(area.get(l, 0.0)), nverts.get(dense[l], 0),
                       sorted(roles_of.get(l, ()))] for l in order]
    pm = _dc.replace(pm, shape_of_vertex=label, shape_of_face=of_face)
    edges = joint_planar_edges(pm)
    stats.joint_edges = len(edges)
    for _a, _b, ra, rb in edges:
        key = f"{ra}|{rb}"
        stats.joint_edges_by_roles[key] = stats.joint_edges_by_roles.get(key, 0) + 1
    _to_xy, to_ll = airport.frame.transformers()
    ll = lambda x, y: tuple(map(float, to_ll(x, y)))  # noqa: E731
    ext = snap_margin_m(law)
    joints = _contour_joints(pm, label, ll, ext, stats)
    joints += _gap_joints(pm, law, label, ll, ext, len(joints), stats, net)
    pm = _dc.replace(pm, shape_joints=tuple(joints), road_ramps=tuple(ramps))
    stats.road_ramps = len(ramps)
    stats.wall_s = time.perf_counter() - t0
    return pm, stats
