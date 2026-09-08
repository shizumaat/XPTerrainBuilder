"""THE REACH TERRITORIES — SERVING CONTACTS AND LABEL-BOUNDARY JOINTS
(RULINGS 2026-09-07c, 07e, 07f, 07g; spec ``docs/specs/auto-patch-v2/
apron-reach-territory-spec.md`` §2b; ``emit.toml [terrace]``
``min_step_m`` / ``simplify_factor`` / ``complex_roles``).

THE LAW (owner 07c, reframed 07g): "the only time an apron can be counted
as part of a centerline route is when there is no other way for the
route to connect between runways.  Nodes not on the route must take the
shortest visible path to a centerline route without leaving the apron,
then follow the main route."  No shortcuts across aprons; two aprons no
route joins are separate and step (07e: the HECA pack "incorrectly
connects the two aprons" at 30.127729, 31.412022 — the joint is inferred
from the routes serving each side).

CONTACTS are RUNWAY-CONNECTED stations only (07f (1)): a vertex of a
``taxi_centerline`` breakline the route graph reaches from a threshold
pin (``constraints.routes.reach``); a dead-end lane's stations are
neither contacts nor joins.  Each contact carries its route band.

THE COMPLEX.  The owner's "apron shape" is the WELDED PAVEMENT — HECA
pav132 is one 110 polygon the classification cuts into 28 faces — so the
labelling runs over each connected component of the union of the
``complex_roles`` faces (apron, junction, the road family inside
pavement) and the DEAD-END taxi faces (a taxi-family face with no reached
station on its ring: a lane inside the apron that serves no runway — its
stations are labelled like any other node, so its centreline never
bridges two territories), never per face.  Runway-connected taxi faces
are the routes themselves and stay out (07g (1): with them the union is
the whole airside, measured 2.88 km² at HECA).

THE LABELS (07g (2)).  Every vertex of a complex's faces is SERVED by the
contact it reaches by the shortest visible in-shape path: the shortest
path in the complex's visibility graph (visible chords among the
boundary vertices simplified to ``simplify_factor`` × the identity
spacing, plus the contacts, plus the boundary arcs), each vertex joined
to the graph through its ``LABEL_CANDIDATES`` nearest visible graph
nodes.  Contacts are their own label.  A rigid pad's vertices take one
label — the majority of its labelled vertices (07c (3): a pad belongs to
one territory).  THE REACH BAND of a labelled node (07g (2): the
contact's band ± the apron cap × the path) is NOT a solver row: agreement
is pairwise and not transitive, so a chain of agreeing labels can join a
node to a contact its own label disagrees with, and the band rows were
measured INFEASIBLE against the kept rows (HECA replay 2026-09-07: 1,765
bands, HiGHS infeasible).  The pipeline WITHDRAWS the hop-derived ``reach``
band of every labelled non-station node instead (an envelope the kept
rows imply, never a law row) — the kept rows carry the reach.

THE PREDICATE (07f, pairwise, never transitive) on two labels ``c₁``,
``c₂``: they DISAGREE — a JOINT — when ``|ceil₁ − ceil₂| > cap_max ·
d_inshape(c₁, c₂) + min_step_m``; the floor-only variant is REPORTED
where it fires and the ceiling one does not, never decided.

THE JOINT (07g (3)) is the LABEL BOUNDARY, no polygon cut, no split
copy, no seam geometry: every vertex pair (a planar edge, any row's
endpoints) whose labels disagree is a joint pair — the pipeline drops
every row across it ONCE at assembly (``pipeline/territory.py``) and the
mesh builds the step from the two node elevations (owner 07d).  The
DECLARATION (sidecar ``terrace_joints``, 06n's path) is the boundary
CONTOUR through each face: the face's constrained Delaunay triangulation
over its own vertices, marched — a triangle with two joint edges carries
the segment between their midpoints, any other mixed triangle joins its
joint-edge midpoints at its centroid — so the contour SEPARATES the
face's disagreeing vertex sets and every priced chord across the joint
crosses it (the census's allowance test), the contours merged into
polylines airport-wide, each with the step its joint edges carry.

THE FEASIBILITY FALLBACK (07g (1)).  A runway whose threshold pins reach
no other runway's pins through the network: the shortest in-shape path
across one complex joining the two route SYSTEMS (contact sets reached
from either) becomes a route link at the apron cap
(``PlanarMap.route_links``; ``constraints.routes`` walks it, the chain
row ``route_links`` prices it) — reported wherever it fires.

The dependency law lets ``planar`` import law / model / airport /
classify only, so the pipeline hands the route bands in as data.
"""
from __future__ import annotations

import dataclasses as _dc
import math
import time
import typing as _t

import numpy as np
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import dijkstra
from scipy.spatial import cKDTree
import shapely
from shapely.geometry import LineString, Point, Polygon
from shapely.ops import linemerge, unary_union
from shapely.strtree import STRtree

from ..classify.evidence import polygon_parts
from ..classify.roles import Classification
from ..law import Law
from ..law.tables import is_rigid_role, role_cap, role_family, snap_margin_m
from ..model.frame import XY
from ..model.planar import LabelJoint, PlanarMap
from .terraces import STATION_KIND

__all__ = ["Territories", "TerritoryStats", "reached_stations", "label_territories",
           "joint_planar_edges", "label_joints", "fallback_links", "row_vertices", "row_test_pairs"]

Band = tuple[float, float]
#: The slice kind of a service-road cell built OUTSIDE pavement
#: (``classify``: the truck corridors): never part of a pavement complex.
OUTSIDE_ROAD_KIND = "service_road"
#: How many nearest graph nodes a vertex is joined to the visibility graph
#: through (×4 once while none is visible, then the notch fallback), and
#: the longest chord the graph carries (a longer visible line relays
#: through a boundary node) — wall bounds, never law values (HECA
#: 2026-09-07: all-pairs over 837 nodes and the full escalation cost
#: 23 s + 48 s; the graph's crossing query is the cost).
LABEL_CANDIDATES = 24
LABEL_CANDIDATE_ROUNDS = 2
MAX_CHORD_M = 400.0
#: Label of a vertex no complex serves.
NO_LABEL = -1


@_dc.dataclass
class TerritoryStats:
    """What the labelling found (one line in the build log)."""

    complexes: int = 0              # pavement complexes (connected pavement unions)
    complexes_split: int = 0        # unions still in parts after the closure (the largest kept)
    complexes_labelled: int = 0     # with two or more runway-connected contacts
    contacts: int = 0               # runway-connected stations on those complexes
    labelled: int = 0               # vertices served by a contact
    unlabelled: int = 0             # complex vertices no visible chord joins to the graph
    notch_fallback: int = 0         # vertices labelled through their nearest connected graph node (no visible chord)
    isolated_fallback: int = 0      # of those, whose Euclidean-nearest node was ISOLATED (no path to a contact)
    pads_relabelled: int = 0        # rigid faces whose vertices took the majority label
    road_vertices_labelled: int = 0  # outside-road corridor vertices labelled along the corridor (07g (4))
    labels: int = 0                 # distinct serving contacts
    adjacent_pairs: int = 0         # label pairs met on a planar edge
    joint_pairs: int = 0            # of those, disagreeing under the ceiling predicate
    over_max_pairs: int = 0         # disagreeing pairs whose predicted step exceeds terrace.max_step_m: NOT a joint (RULINGS 2026-09-08d (3)), the rows stay
    floor_only_pairs: int = 0       # pairs the FLOOR variant separates and the ceiling one does not (report)
    joint_edges: int = 0            # planar edges across a joint
    joint_edges_by_roles: dict[str, int] = _dc.field(default_factory=dict)
    joint_edges_in_strip: int = 0   # joint edges inside the runway strip keep-out (report)
    contours: int = 0               # declared polylines
    contour_length_m: float = 0.0
    dangling_faces: int = 0         # faces whose contour needed a centroid join (non-transitive labels)
    links: list[list] = _dc.field(default_factory=list)   # the fallback links [a, b, d_m, complex]
    welded_route_pairs: int = 0     # disagreeing label pairs on a route edge (two contacts): welded, never a joint
    welded_strip_pairs: int = 0     # disagreeing label pairs whose joint edge lies in the runway strip: welded (06n keep-out)
    graph_nodes: int = 0            # visibility-graph nodes over the labelled complexes
    wall_graph_s: float = 0.0
    wall_label_s: float = 0.0
    wall_s: float = 0.0
    pairs: list[list] = _dc.field(default_factory=list)   # [c1, c2, gap, d, hold, floor gap, joint]


@_dc.dataclass
class Territories:
    """The labelling of one map: ``label[v]`` = the serving contact (a
    planar vertex id) or ``NO_LABEL``; ``path_m[v]`` the in-shape path to
    it; ``joint(a, b)`` the predicate on two labels; ``weld(a, b)`` overrides
    it (the pair is one terrace: a route edge, the strip keep-out)."""

    label: dict[int, int]
    path_m: dict[int, float]
    contacts: frozenset[int]
    stats: TerritoryStats
    #: (c₁, c₂) with c₁ < c₂ -> disagreeing (True) / agreeing (False)
    verdict: dict[tuple[int, int], bool] = _dc.field(default_factory=dict)
    #: contact -> (complex index, column in that complex's distance matrix)
    _where: dict[int, tuple[int, int]] = _dc.field(default_factory=dict)
    _dcc: list[np.ndarray] = _dc.field(default_factory=list)
    _bands: dict[int, Band] = _dc.field(default_factory=dict)
    _cap: float = 0.0
    _min_step: float = 0.0
    #: RULINGS 2026-09-08d (3): the largest step a joint may carry (v1
    #: APRON_TERRACE_MAX_STEP_M, ``terrace.max_step_m``); a boundary whose
    #: predicted step exceeds it is NOT a joint — the cell grades through
    _max_step: float = float("inf")

    def joint(self, la: int, lb: int) -> bool:
        """Whether two labels disagree (a joint between their nodes)."""
        if la == lb or la == NO_LABEL or lb == NO_LABEL:
            return False
        key = (la, lb) if la < lb else (lb, la)
        v = self.verdict.get(key)
        if v is None:
            v = self._decide(key)
            self.verdict[key] = v
        return v

    def _decide(self, key: tuple[int, int]) -> bool:
        wa, wb = self._where.get(key[0]), self._where.get(key[1])
        if wa is None or wb is None or wa[0] != wb[0]:
            return False                    # two complexes: no adjacency (report)
        d = float(self._dcc[wa[0]][wa[1], wb[1]])
        if not math.isfinite(d):
            return False
        gap = abs(self._bands[key[0]][1] - self._bands[key[1]][1])
        return self._min_step < gap - self._cap * d <= self._max_step

    def weld(self, la: int, lb: int) -> None:
        """Two labels ruled one terrace whatever the predicate says."""
        if la != lb and la != NO_LABEL and lb != NO_LABEL:
            self.verdict[(la, lb) if la < lb else (lb, la)] = False

    def straddles_pairs(self, pairs: _t.Iterable[tuple[int, int]]) -> bool:
        """Whether any of the vertex ``pairs`` carries disagreeing labels."""
        return any(self.joint(self.label.get(a, NO_LABEL), self.label.get(b, NO_LABEL))
                   for a, b in pairs)

    def straddles(self, ids: _t.Iterable[int]) -> bool:
        """Whether any two of ``ids`` carry disagreeing labels."""
        seen: list[int] = []
        for v in ids:
            lv = self.label.get(v, NO_LABEL)
            if lv == NO_LABEL:
                continue
            for u in seen:
                if u != lv and self.joint(u, lv):
                    return True
            if lv not in seen:
                seen.append(lv)
        return False


def reached_stations(pm: PlanarMap, bands: _t.Mapping[int, Band]) -> frozenset[int]:
    """The RUNWAY-CONNECTED stations: taxi-centreline breakline vertices
    the route graph reaches from a threshold pin (07f (1))."""
    out: set[int] = set()
    for b in pm.breaklines.values():
        if b.kind == STATION_KIND:
            out.update(v for v in b.vertices(pm) if v in bands)
    return frozenset(out)


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


def _complex_faces(pm: PlanarMap, law: Law, stations: frozenset[int],
                   outside_refs: _t.Container[str]) -> list[int]:
    """The faces whose union is the pavement complexes (module docstring)."""
    roles = set(law.tables.emit.terrace.complex_roles)
    out: list[int] = []
    for fid, f in pm.faces.items():
        if f.role in roles:
            if f.ref in outside_refs:
                continue
            out.append(fid)
        elif role_family(law, f.role) == "taxi":
            if not any(v in stations for cyc in (f.ring, *f.holes) for v in pm.ring_vertices(cyc)):
                out.append(fid)
    return out


def _complexes(pm: PlanarMap, fids: list[int], close_m: float,
               stats: TerritoryStats | None = None) -> list[tuple[Polygon, list[int]]]:
    """The welded pavement complexes: the faces grouped by SHARED VERTICES
    (v2's weld is one node per coordinate — a 06n retreat leaves two cells
    touching at a vertex, and a polygon union reads a point contact as two
    parts), each group's union closed by ``close_m`` (a hair gap or a
    point contact; under half the 06n joint gap, which stays open); a
    group whose closed union is still several parts keeps its largest
    (counted)."""
    parent = {fid: fid for fid in fids}

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    owner: dict[int, int] = {}
    for fid in fids:
        f = pm.faces[fid]
        for cyc in (f.ring, *f.holes):
            for v in pm.ring_vertices(cyc):
                o = owner.get(v)
                if o is None:
                    owner[v] = fid
                else:
                    ra, rb = find(o), find(fid)
                    if ra != rb:
                        parent[max(ra, rb)] = min(ra, rb)
    groups: dict[int, list[int]] = {}
    for fid in fids:
        groups.setdefault(find(fid), []).append(fid)
    out: list[tuple[Polygon, list[int]]] = []
    for members in groups.values():
        polys = [p for p in (_face_polygon(pm, fid) for fid in members) if p is not None]
        if not polys:
            continue
        u = unary_union(polys)
        if u.geom_type != "Polygon":
            u = u.buffer(close_m).buffer(-close_m)
        parts = [p for p in polygon_parts(u) if p.area > 0.0]
        if not parts:
            continue
        if len(parts) > 1 and stats is not None:
            stats.complexes_split += 1
        out.append((max(parts, key=lambda p: p.area), members))
    return out


def _boundary_nodes(poly: Polygon, spacing: float) -> tuple[np.ndarray, list[tuple[int, int]]]:
    """The simplified boundary vertices of ``poly`` as ``(P, (cycle, pos))``."""
    simp = poly.simplify(spacing, preserve_topology=True)
    if simp.is_empty or simp.geom_type != "Polygon":
        simp = poly
    pts: list[XY] = []
    tags: list[tuple[int, int]] = []
    for ci, ring in enumerate((simp.exterior, *simp.interiors)):
        coords = list(ring.coords)[:-1]
        for k, (x, y) in enumerate(coords):
            pts.append((float(x), float(y)))
            tags.append((ci, k))
    return np.array(pts, float), tags


def _boundary_tree(poly: Polygon) -> STRtree:
    segs = []
    for ring in (poly.exterior, *poly.interiors):
        c = np.asarray(ring.coords, float)
        segs.append(np.stack([c[:-1], c[1:]], axis=1))
    return STRtree(shapely.linestrings(np.concatenate(segs)))


def _visible(cover, btree: STRtree, PA: np.ndarray, PB: np.ndarray) -> np.ndarray:
    """Which chords ``PA[k]–PB[k]`` the face covers: a chord CROSSING a
    boundary segment never (the tree prefilter); a chord crossing none is
    wholly inside or wholly outside, decided by its MIDPOINT (a chord
    touching a hole corner without crossing and clipping it is the one
    miss — accepted; one GEOS ``covered_by`` per surviving chord over the
    13-hole HECA complex was measured at 39 s + 44 s for the graph and the
    labels, 2026-09-07, the midpoint test under 2 s)."""
    n = len(PA)
    if n == 0:
        return np.zeros(0, bool)
    chords = shapely.linestrings(np.stack([PA, PB], axis=1))
    hit = btree.query(chords, predicate="crosses")
    ok = np.ones(n, bool)
    ok[np.unique(hit[0])] = False
    idx = np.flatnonzero(ok)
    if len(idx):
        M = 0.5 * (PA[idx] + PB[idx])
        ok[idx] = np.asarray(shapely.contains_xy(cover, M[:, 0], M[:, 1]), bool)
    return ok


@_dc.dataclass
class _Graph:
    """The in-shape visibility graph of one complex: boundary nodes then
    contacts; ``D[k, node]`` the in-shape distance from contact ``k``."""

    P: np.ndarray
    n_boundary: int
    contacts: list[int]
    D: np.ndarray
    cover: object
    btree: STRtree
    tree: cKDTree
    #: the CONNECTED nodes (a finite in-shape distance to some contact) and
    #: their tree — the fallback's targets (module docstring)
    connected: np.ndarray
    ctree: cKDTree


def _graph(poly: Polygon, contacts: dict[int, XY], spacing: float, tol: float) -> _Graph | None:
    P0, tags = _boundary_nodes(poly, spacing)
    cids = sorted(contacts)
    if len(P0) < 3 or len(cids) < 2:
        return None
    P = np.vstack([P0, np.array([contacts[c] for c in cids], float)])
    n = len(P)
    cover = poly.buffer(tol)
    shapely.prepare(cover)
    btree = _boundary_tree(poly)
    tree = cKDTree(P)
    pairs = tree.query_pairs(MAX_CHORD_M, output_type="ndarray")
    if len(pairs):
        I, J = pairs[:, 0].astype(np.int64), pairs[:, 1].astype(np.int64)
        ok = _visible(cover, btree, P[I], P[J])
        I, J = I[ok], J[ok]
    else:
        I = J = np.zeros(0, np.int64)
    A: list[int] = []
    B: list[int] = []
    by_cycle: dict[int, list[int]] = {}
    for k, (ci, _pos) in enumerate(tags):
        by_cycle.setdefault(ci, []).append(k)
    for ks in by_cycle.values():
        for a, b in zip(ks, ks[1:] + ks[:1]):
            A.append(a); B.append(b)
    Aa, Ba = np.array(A, np.int64), np.array(B, np.int64)
    if len(Aa):
        ok = _visible(cover, btree, P[Aa], P[Ba])
        Aa, Ba = Aa[ok], Ba[ok]
    EA, EB = np.concatenate([I, Aa]), np.concatenate([J, Ba])
    W = np.hypot(P[EA, 0] - P[EB, 0], P[EA, 1] - P[EB, 1])
    m = csr_matrix((np.concatenate([W, W]), (np.concatenate([EA, EB]), np.concatenate([EB, EA]))),
                   shape=(n, n))
    m.sum_duplicates()
    D = dijkstra(m, directed=False, indices=np.arange(len(P0), n))
    connected = np.flatnonzero(np.isfinite(D).any(axis=0))
    return _Graph(P, len(P0), cids, D, cover, btree, tree, connected, cKDTree(P[connected]))


def _vertex_distances(g: _Graph, Q: np.ndarray, fallback: list[int]) -> np.ndarray:
    """``(len(Q), n_contacts)`` in-shape distances from each query point to
    every contact through its nearest visible graph nodes; ``inf`` where
    no graph node is visible."""
    nq = len(Q)
    out = np.full((nq, len(g.contacts)), np.inf)
    if nq == 0:
        return out
    pending = np.arange(nq)
    k = LABEL_CANDIDATES
    n = len(g.P)
    for _round in range(LABEL_CANDIDATE_ROUNDS):
        if not len(pending):
            break
        kk = min(k, n)
        d, idx = g.tree.query(Q[pending], k=kk)
        d = np.atleast_2d(d); idx = np.atleast_2d(idx)
        rows = np.repeat(pending, kk)
        cols = idx.ravel()
        dd = d.ravel()
        same = dd < 1e-9                        # the vertex IS a graph node
        vis = np.zeros(len(rows), bool)
        vis[same] = True
        rest = np.flatnonzero(~same)
        if len(rest):
            vis[rest] = _visible(g.cover, g.btree, Q[rows[rest]], g.P[cols[rest]])
        rows, cols, dd = rows[vis], cols[vis], dd[vis]
        if len(rows):
            cand = g.D[:, cols].T + dd[:, None]      # (hits, contacts)
            np.minimum.at(out, rows, cand)
        pending = pending[~np.isfinite(out[pending]).any(axis=1)]
        if kk >= n:
            break
        k *= 4
    if len(pending):
        # THE NOTCH FALLBACK (labelling is TOTAL over a labelled complex):
        # a vertex whose every chord to the graph leaves the polygon (a
        # reflex corner the simplification moved past — HECA 2026-09-07:
        # 458 vertices, among them v10228, the node the binding chain
        # entered #364 through) takes the distances of its Euclidean-
        # nearest CONNECTED graph node plus the gap (an over-estimate by at
        # most the detour round the notch).  Connected, because a
        # simplified boundary node can be ISOLATED — its ring arcs cut a
        # notch of the true boundary and every chord failed — and the
        # nearest node's ``inf`` left 74 HECA vertices unlabelled.
        d, idx = g.ctree.query(Q[pending], k=1)
        idx = g.connected[np.atleast_1d(idx)]
        out[pending] = g.D[:, idx].T + np.atleast_1d(d)[:, None]
        fallback[0] += len(pending)
        _d0, idx0 = g.tree.query(Q[pending], k=1)
        fallback[1] += int((np.atleast_1d(idx0) != idx).sum())
    return out


def label_territories(pm: PlanarMap, law: Law, bands: _t.Mapping[int, Band],
                      cl: Classification | None = None) -> Territories:
    """The serving-contact labels, bands and joint predicate of ``pm``
    (module docstring); ``bands`` is the route graph's ``(floor,
    ceiling)`` per reached vertex (``constraints.no_step.reach_band_values``)."""
    t0 = time.perf_counter()
    stats = TerritoryStats()
    tt = law.tables.emit.terrace
    caps = [role_cap(law, r) for r in tt.cell_roles]
    cap = max((max(rc.longitudinal, rc.transverse) for rc in caps if rc is not None), default=0.0)
    terr = Territories({}, {}, frozenset(), stats, _bands=dict(bands), _cap=cap,
                       _min_step=tt.min_step_m, _max_step=tt.max_step_m)
    stations = reached_stations(pm, bands)
    terr.contacts = stations
    if len(stations) < 2:
        stats.wall_s = time.perf_counter() - t0
        return terr
    outside = {c.ref for c in cl.cells if c.kind == OUTSIDE_ROAD_KIND} if cl is not None else set()
    fids = _complex_faces(pm, law, stations, outside)
    tol = snap_margin_m(law)
    min_d = law.tables.emit.identity.min_distinct_spacing_m
    complexes = _complexes(pm, fids, min_d / 2.0, stats)
    stats.complexes = len(complexes)
    spacing = tt.simplify_factor * min_d
    contacts_xy = {v: pm.vertices[v].xy for v in stations}
    ctree = STRtree([Point(p) for p in contacts_xy.values()])
    cids = list(contacts_xy)
    for ci, (comp, members) in enumerate(complexes):
        cover = comp.buffer(tol)
        shapely.prepare(cover)
        near = [cids[int(k)] for k in ctree.query(cover, predicate="intersects")]
        here = {v: contacts_xy[v] for v in near if cover.covers(Point(contacts_xy[v]))}
        if len(here) < 2:
            continue
        t_c = time.perf_counter()
        g = _graph(comp, here, spacing, tol)
        stats.wall_graph_s += time.perf_counter() - t_c
        t_c = time.perf_counter()
        if g is None:
            continue
        stats.complexes_labelled += 1
        stats.graph_nodes += len(g.P)
        stats.contacts += len(here)
        col = {c: k for k, c in enumerate(g.contacts)}
        dcc = g.D[:, g.n_boundary:]                  # contact × contact in-shape distances
        terr._dcc.append(np.minimum(dcc, dcc.T))
        for c, k in col.items():
            terr._where[c] = (len(terr._dcc) - 1, k)
        verts = sorted({v for fid in members for cyc in (pm.faces[fid].ring, *pm.faces[fid].holes)
                        for v in pm.ring_vertices(cyc)})
        Q = np.array([pm.vertices[v].xy for v in verts], float)
        fb = [0, 0]
        Dv = _vertex_distances(g, Q, fb)
        stats.notch_fallback += fb[0]
        stats.isolated_fallback += fb[1]
        cvec = np.array(g.contacts)
        for r, v in enumerate(verts):
            if v in col:
                terr.label[v] = v
                terr.path_m[v] = 0.0
                continue
            row = Dv[r]
            if not np.isfinite(row).any():       # unreachable: a contact exists, so never
                terr.label[v] = NO_LABEL
                stats.unlabelled += 1
                continue
            k = int(np.argmin(row))
            terr.label[v] = int(cvec[k])
            terr.path_m[v] = float(row[k])
        # THE PADS (07c (3)): one label per rigid face — the majority
        for fid, f in pm.faces.items():
            if not is_rigid_role(law, f.role):
                continue
            vs = [v for cyc in (f.ring, *f.holes) for v in pm.ring_vertices(cyc)]
            ls = [terr.label[v] for v in vs if terr.label.get(v, NO_LABEL) != NO_LABEL]
            if not ls or len(set(ls)) == 1:
                continue
            top = max(set(ls), key=lambda l: (ls.count(l), -l))
            for v in vs:
                if v in terr.label and terr.label[v] != NO_LABEL and v not in col:
                    terr.label[v] = top
            stats.pads_relabelled += 1
        stats.wall_label_s += time.perf_counter() - t_c
    _label_outside_roads(pm, law, terr, outside, spacing, tol)
    stats.labelled = sum(1 for l in terr.label.values() if l != NO_LABEL)
    stats.labels = len({l for l in terr.label.values() if l != NO_LABEL})
    # THE ROUTE IS NEVER CUT: two contacts on one planar edge (a centreline
    # chord, a crossing) are one terrace whatever their ceilings say (a
    # 3 % letter-A/B stretch outruns the apron cap; HECA 2026-09-07: two
    # runway-side stations 4.5 m apart, 4.5 m apart by ceiling)
    for e in pm.edges.values():
        if e.a in stations and e.b in stations and terr.joint(e.a, e.b):
            terr.weld(e.a, e.b)
            stats.welded_route_pairs += 1
    _adjacency_report(pm, terr, bands, cap, tt.min_step_m)
    stats.wall_s = time.perf_counter() - t0
    return terr


def _label_outside_roads(pm: PlanarMap, law: Law, terr: Territories, outside: _t.Container[str],
                         spacing: float, tol: float) -> None:
    """THE ROADS ACROSS A JOINT (07g (4)): a road corridor OUTSIDE pavement
    is no apron shape — its vertices are never served through it — but a
    corridor welded to pavement at both ends bridges two territories with
    its own profile rows (HECA 2026-09-07: route15, 600 m at 1.5 %, made
    the K + route chain INFEASIBLE once the apron shortcut was cut).  Each
    corridor group's unlabelled vertices take the label of the nearest
    labelled vertex on it by the in-shape path ALONG the corridor, so the
    boundary falls mid-corridor and the road's rows across it are dropped
    (the step reported)."""
    st = terr.stats
    fids = [fid for fid, f in pm.faces.items() if f.ref in outside]
    if not fids:
        return
    for poly, members in _complexes(pm, fids, tol):
        verts = sorted({v for fid in members for cyc in (pm.faces[fid].ring, *pm.faces[fid].holes)
                        for v in pm.ring_vertices(cyc)})
        seeds = {v: pm.vertices[v].xy for v in verts if terr.label.get(v, NO_LABEL) != NO_LABEL}
        todo = [v for v in verts if v not in seeds]
        if len(seeds) < 2 or not todo:
            continue
        g = _graph(poly, seeds, spacing, tol)
        if g is None:
            continue
        Q = np.array([pm.vertices[v].xy for v in todo], float)
        fb = [0, 0]
        Dv = _vertex_distances(g, Q, fb)
        svec = np.array(g.contacts)
        for r, v in enumerate(todo):
            row = Dv[r]
            if not np.isfinite(row).any():
                continue
            k = int(np.argmin(row))
            terr.label[v] = terr.label[int(svec[k])]
            terr.path_m[v] = float(row[k]) + terr.path_m.get(int(svec[k]), 0.0)
            st.road_vertices_labelled += 1


def _adjacency_report(pm: PlanarMap, terr: Territories, bands, cap: float, min_step: float) -> None:
    """The label pairs met on planar edges and the predicate's verdicts."""
    st = terr.stats
    st.pairs = []
    st.joint_pairs = st.floor_only_pairs = 0
    pairs: set[tuple[int, int]] = set()
    for e in pm.edges.values():
        la, lb = terr.label.get(e.a, NO_LABEL), terr.label.get(e.b, NO_LABEL)
        if la != lb and la != NO_LABEL and lb != NO_LABEL:
            pairs.add((la, lb) if la < lb else (lb, la))
    st.adjacent_pairs = len(pairs)
    for a, b in sorted(pairs):
        j = terr.joint(a, b)
        wa, wb = terr._where.get(a), terr._where.get(b)
        d = float("nan")
        if wa is not None and wb is not None and wa[0] == wb[0]:
            d = float(terr._dcc[wa[0]][wa[1], wb[1]])
        gap = abs(bands[a][1] - bands[b][1])
        fgap = abs(bands[a][0] - bands[b][0])
        hold = cap * d + min_step
        st.pairs.append([a, b, round(gap, 2), round(d, 1), round(hold, 2), round(fgap, 2), j])
        if j:
            st.joint_pairs += 1
        elif math.isfinite(d) and gap - cap * d > terr._max_step:
            st.over_max_pairs += 1
        elif math.isfinite(d) and fgap > hold:
            st.floor_only_pairs += 1


def row_vertices(row) -> tuple[int, ...]:
    """The vertex ids a constraint row touches (no import of the row types:
    duck-typed on the record's fields)."""
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
    its ends: labels agree pairwise and not transitively, so a triple
    whose ENDS disagree while both segments agree crosses no declared
    contour, and dropping it leaves the surface free where the census
    still prices the rate (CYXY 2026-09-07: junction #126 ring
    2658-2659-2660, 348 no_step rows dropped, one 3.0 % rate read)."""
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


def joint_planar_edges(pm: PlanarMap, terr: Territories, keepout=None
                       ) -> list[tuple[int, int, str, str]]:
    """Every planar edge whose endpoints' labels disagree, with the roles
    on its two sides (``keepout``: the runway strip polygon — an edge
    inside it is counted in the stats, never declared)."""
    st = terr.stats
    if keepout is not None and not keepout.is_empty:
        # THE STRIP KEEP-OUT (06n; spec §3): a joint edge inside the runway
        # strip is no joint — the two territories MERGE there (welded)
        for e in pm.edges.values():
            la, lb = terr.label.get(e.a, NO_LABEL), terr.label.get(e.b, NO_LABEL)
            if terr.joint(la, lb) and keepout.intersects(
                    LineString([pm.vertices[e.a].xy, pm.vertices[e.b].xy])):
                st.joint_edges_in_strip += 1
                terr.weld(la, lb)
                st.welded_strip_pairs += 1
    out: list[tuple[int, int, str, str]] = []
    by_roles: dict[str, int] = {}
    for e in pm.edges.values():
        la, lb = terr.label.get(e.a, NO_LABEL), terr.label.get(e.b, NO_LABEL)
        if not terr.joint(la, lb):
            continue
        roles = sorted(pm.faces[f].role for f in (e.left_face, e.right_face) if f is not None)
        key = "|".join(roles)
        by_roles[key] = by_roles.get(key, 0) + 1
        out.append((e.a, e.b, roles[0], roles[-1]))
    st.joint_edges = len(out)
    st.joint_edges_by_roles = by_roles
    return out


def _face_contour(pm: PlanarMap, fid: int, terr: Territories,
                  ) -> tuple[list[LineString], list[tuple[int, int]], bool]:
    """The label-boundary contour of one face (module docstring): the
    segments, the joint vertex pairs of its triangulation, and whether a
    centroid join was needed."""
    poly = _face_polygon(pm, fid)
    if poly is None:
        return [], [], False
    f = pm.faces[fid]
    ids: dict[tuple[float, float], int] = {}
    for cyc in (f.ring, *f.holes):
        for v in pm.ring_vertices(cyc):
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
            if terr.joint(terr.label.get(a, NO_LABEL), terr.label.get(b, NO_LABEL)):
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
    """``pts`` with both ends pushed ``eps`` outward along their end
    segments: a contour ends at the MIDPOINT of a boundary edge, and the
    census's crossing test between that edge (a priced chord) and a point
    a coordinate-rounding away from it is a coin toss (measured on the
    twin: 15 m ring-edge steps read as rows); past the edge the crossing
    is proper."""
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


def label_joints(pm: PlanarMap, terr: Territories, faces: _t.Iterable[int],
                 to_ll: _t.Callable[[float, float], tuple[float, float]],
                 extend_m: float = 0.0) -> tuple[LabelJoint, ...]:
    """The declared joints: the faces' contours merged into polylines,
    each carrying the joint vertex pairs whose midpoints lie on it, the
    ends pushed ``extend_m`` past the boundary edges they stop on."""
    st = terr.stats
    segs: list[LineString] = []
    pairs: list[tuple[int, int]] = []
    for fid in faces:
        s, p, dangling = _face_contour(pm, fid, terr)
        segs.extend(s)
        pairs.extend(p)
        if dangling:
            st.dangling_faces += 1
    if not segs:
        return ()
    merged = linemerge(unary_union(segs))
    lines = list(getattr(merged, "geoms", [merged]))
    pairs = sorted(set(pairs))
    mids = np.array([[0.5 * (pm.vertices[a].xy[0] + pm.vertices[b].xy[0]),
                      0.5 * (pm.vertices[a].xy[1] + pm.vertices[b].xy[1])] for a, b in pairs])
    tree = STRtree(shapely.points(mids)) if len(mids) else None
    out: list[LabelJoint] = []
    for line in lines:
        pts = [(float(x), float(y)) for x, y in line.coords]
        if len(pts) < 2:
            continue
        on = [pairs[int(k)] for k in tree.query(line, predicate="dwithin", distance=1e-6)] \
            if tree is not None else []
        pts = _extended(pts, extend_m)
        roles = sorted({pm.faces[f].role for a, b in on for f in
                        (set(pm.vertices[a].incident_faces) & set(pm.vertices[b].incident_faces))})
        out.append(LabelJoint(len(out), tuple(pts), tuple(tuple(to_ll(x, y)) for x, y in pts),
                              tuple(on), float(line.length), tuple(roles)))
    st.contours = len(out)
    st.contour_length_m = sum(j.length_m for j in out)
    return tuple(out)


def fallback_links(pm: PlanarMap, law: Law, terr: Territories, systems: _t.Sequence[frozenset[int]],
                   ) -> list[tuple[int, int, float, float]]:
    """THE FEASIBILITY FALLBACK (07g (1)): for route systems (contact sets
    reached from different runways) that no route joins, the shortest in-
    shape path across one complex between a contact of the one and a
    contact of the other, as ``(a, b, apron cap, path metres)`` — one
    link per system pair, greedily until every system is joined."""
    if len(systems) < 2 or not terr._dcc:
        return []
    cap = terr._cap
    parent = list(range(len(systems)))

    def find(x: int) -> int:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    out: list[tuple[int, int, float, float]] = []
    cands: list[tuple[float, int, int, int, int]] = []
    for i in range(len(systems)):
        for j in range(i + 1, len(systems)):
            best = None
            for a in systems[i]:
                wa = terr._where.get(a)
                if wa is None:
                    continue
                for b in systems[j]:
                    wb = terr._where.get(b)
                    if wb is None or wb[0] != wa[0]:
                        continue
                    d = float(terr._dcc[wa[0]][wa[1], wb[1]])
                    if math.isfinite(d) and (best is None or d < best[0]):
                        best = (d, a, b, wa[0])
            if best is not None:
                cands.append((best[0], i, j, best[1], best[2]))
    for d, i, j, a, b in sorted(cands):
        ri, rj = find(i), find(j)
        if ri == rj:
            continue
        parent[max(ri, rj)] = min(ri, rj)
        out.append((a, b, cap, d))
        terr.stats.links.append([a, b, round(d, 1), int(terr._where[a][0])])
    return out
