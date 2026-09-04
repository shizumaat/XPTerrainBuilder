"""THE ROUTE GRAPH (RULINGS 2026-09-04o: "feasible elevations propagate
out from runway thresholds and have to follow taxi routes ... aircraft
can't travel straight across the grass; they have to follow taxi routes,
which is what follows the grade cap").

The graph an aircraft travels: NODES are the planar vertices on airside
pavement; EDGES are the travel paths the law itself prices inside and
along that pavement — every ring edge of an airside pavement face (a
taxi centreline chord is a ring edge of the faces it splits, so the
centrelines are first-class), every chord of a taxi-family face (the
face is a PLANE shape: any two of its vertices are a travel path,
``rulesets.taxi.longitudinal within_shape``), and on an apron the
movement surfaces the apron law names (ring edges, chords to a spine or
pad vertex, body chords inside ``emit.within_shape.apron_body_chord_max_m``;
RULINGS 2026-08-21c / 08-24) — chords span ALL the rings of a face, the
outer and its holes: a face is one surface and a pad's rim reaches the
pad beside it across the apron between them.  SERVICE ROADS ARE EXCLUDED from airside
reach (v1 ``config.REACH_NO_SERVICE_SPINES``; memory
``reach-follows-centerlines``): the groundside roles never contribute a
node or an edge, and a ``road_centerline`` breakline adds nothing.

Each edge carries its PLAN LENGTH and the CAP of the face it lies in —
the strictest where two faces share it, which is the budget the solve
actually grants along it.  Two readings:

* ROUTE DISTANCE between two vertices = the shortest path by length; the
  path's BUDGET = ``Σ cap_e · len_e`` along that very path (the pair's
  own caps: an apron↔taxiway pair carries the taxiway's cap on the
  taxiway stretch and the apron's on the apron stretch, 04q-1) —
  :func:`route_neighbours` (the no-step population).
* REACH from the runway thresholds = the threshold values propagated
  along every route at the path caps, multi-source Dijkstra over the
  budget weights — :func:`reach` (v1's reach band as a floor / ceiling
  per vertex).  Budgets are non-negative by construction (memory
  ``reach-envelope-sign-discipline``).

``scipy.sparse.csgraph`` does the walking; nothing here is O(n²) over
the map.  Pure over the planar map and the law; no shapely, no v1.  It
lives beside the generators (not under ``planar/``) because the
constraints read it and the dependency law lets a generator import law
and model only (M0 §1, ``test_dependency_direction``).
"""
from __future__ import annotations

import dataclasses as _dc
import typing as _t

import numpy as np
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import dijkstra

from ..law import Law
from ..law.tables import is_rigid_role, is_value_role, role_cap, role_side
from ..model.planar import EdgeKind, PlanarMap

__all__ = ["RouteGraph", "route_roles", "build_routes", "routes",
           "route_neighbours", "reach", "route_path"]

#: Edge provenance codes (``RouteGraph.kind``).
RING, CHORD, CENTRELINE = 0, 1, 2


@_dc.dataclass(frozen=True)
class RouteGraph:
    """The route graph of one planar map (module docstring)."""

    n: int                                  # planar vertex count (ids dense)
    nodes: frozenset[int]                   # airside pavement vertices
    a: np.ndarray                           # edge endpoints, a < b
    b: np.ndarray
    length: np.ndarray                      # plan metres
    cap: np.ndarray                         # grade fraction along the edge
    kind: np.ndarray                        # RING / CHORD / CENTRELINE
    stats: dict[str, int] = _dc.field(default_factory=dict)

    @property
    def budget(self) -> np.ndarray:
        """``cap · length`` per edge — metres of lawful rise along it."""
        return self.cap * self.length

    def csr(self, weight: str = "length", max_len: float | None = None) -> csr_matrix:
        """Symmetric CSR over the planar vertex ids with ``length`` or
        ``budget`` weights; ``max_len`` drops edges longer than it (an edge
        longer than a window can lie on no path inside it)."""
        w = self.length if weight == "length" else self.budget
        keep = np.ones(len(w), bool) if max_len is None else self.length <= max_len
        a, b, w = self.a[keep], self.b[keep], w[keep]
        m = csr_matrix((np.concatenate([w, w]),
                        (np.concatenate([a, b]), np.concatenate([b, a]))),
                       shape=(self.n, self.n))
        m.sum_duplicates()
        return m

    def edge_budget(self) -> dict[tuple[int, int], float]:
        """``(a, b) -> cap · length`` with ``a < b``."""
        bud = self.budget
        return {(int(x), int(y)): float(w) for x, y, w in zip(self.a, self.b, bud)}


def route_roles(law: Law) -> frozenset[str]:
    """The roles whose faces carry the route graph: airside, value-
    carrying, governed, not rigid — the airside no-step population
    (RULINGS 2026-09-03i); the groundside roles (service roads and
    junctions, lots, ramps) are excluded by the table's own partition."""
    reg = law.tables.precedence.roles
    return frozenset(r for r in reg
                     if role_side(law, r) == "airside" and is_value_role(law, r)
                     and role_cap(law, r) is not None and not is_rigid_role(law, r))


def _pack(a: np.ndarray, b: np.ndarray, n: int) -> np.ndarray:
    """One int64 key per unordered pair (``a < b``)."""
    return a.astype(np.int64) * n + b.astype(np.int64)


def _face_pairs(P: np.ndarray, strict: np.ndarray, all_pairs: bool, gate: float,
                chunk: int = 512) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """The chords of one face over ALL its rings (outer and holes — the
    face is one surface; a pad hole's rim reaches the rim beside it across
    the apron, measured CYXY building6/7: 3.6 m apart, 1.59 m step when
    only same-ring chords were routes): ``(i, j, d)`` with ``i < j``;
    every pair for a plane shape, else a pair with a strict endpoint at
    any distance or any pair inside ``gate``."""
    n = len(P)
    ii, jj, dd = [], [], []
    for i0 in range(0, n, chunk):
        i1 = min(n, i0 + chunk)
        d = np.hypot(P[i0:i1, None, 0] - P[None, :, 0], P[i0:i1, None, 1] - P[None, :, 1])
        rows = np.arange(i0, i1)[:, None]
        cols = np.arange(n)[None, :]
        m = (cols > rows) & (d > 0.0)
        if not all_pairs:
            m &= strict[i0:i1, None] | strict[None, :] | (d <= gate)
        r, c = np.nonzero(m)
        ii.append(r + i0)
        jj.append(c)
        dd.append(d[r, c])
    if not ii:
        z = np.zeros(0, np.int64)
        return z, z, np.zeros(0, float)
    return np.concatenate(ii), np.concatenate(jj), np.concatenate(dd)


def build_routes(pm: PlanarMap, law: Law) -> RouteGraph:
    """The route graph of ``pm`` under ``law`` (module docstring)."""
    roles = route_roles(law)
    taxi = set(law.tables.precedence.taxi_family.members)
    rigid = {r for r in law.tables.precedence.roles if is_rigid_role(law, r)}
    gate = law.tables.emit.within_shape.apron_body_chord_max_m
    n_v = len(pm.vertices)
    xy = np.zeros((n_v, 2), float)
    for vid, v in pm.vertices.items():
        xy[vid] = v.xy
    # spine vertices (taxi centrelines) and pad-shared vertices: an apron
    # chord to either is a movement surface (RULINGS 2026-08-21c)
    strict_v = np.zeros(n_v, bool)
    for bl in pm.breaklines.values():
        if bl.kind == "taxi_centerline":
            strict_v[list(bl.vertices(pm))] = True
    for f in pm.faces.values():
        if f.role in rigid:
            for cyc in (f.ring, *f.holes):
                strict_v[list(pm.ring_vertices(cyc))] = True
    centre = np.array(sorted({e.a * n_v + e.b if e.a < e.b else e.b * n_v + e.a
                              for e in pm.edges.values() if e.kind is EdgeKind.CENTERLINE}),
                      dtype=np.int64)
    A, B, C, K = [], [], [], []
    nodes: set[int] = set()
    n_faces = 0
    for f in pm.faces.values():
        if f.role not in roles:
            continue
        rc = role_cap(law, f.role, f.code_number, f.code_letter)
        if rc is None:
            continue
        cap = rc.longitudinal
        n_faces += 1
        verts: list[int] = []
        seen: set[int] = set()
        for cyc in (f.ring, *f.holes):
            ring = list(pm.ring_vertices(cyc))
            m = len(ring)
            ra = np.array(ring, np.int64)
            rb = np.roll(ra, -1)
            A.append(np.minimum(ra, rb)); B.append(np.maximum(ra, rb))
            C.append(np.full(m, cap)); K.append(np.full(m, RING, np.int8))
            for v in ring:
                if v not in seen:
                    seen.add(v)
                    verts.append(v)
        nodes.update(verts)
        if f.role in taxi or f.role == "apron":
            va = np.array(verts, np.int64)
            i, j, _d = _face_pairs(xy[va], strict_v[va], f.role in taxi, gate)
            if len(i):
                pa, pb = va[i], va[j]
                A.append(np.minimum(pa, pb)); B.append(np.maximum(pa, pb))
                C.append(np.full(len(i), cap)); K.append(np.full(len(i), CHORD, np.int8))
    if not A:
        z = np.zeros(0, np.int64)
        return RouteGraph(n_v, frozenset(), z, z, np.zeros(0), np.zeros(0),
                          np.zeros(0, np.int8), {"nodes": 0, "edges": 0, "faces": 0,
                                                  "ring": 0, "chord": 0, "centreline": 0})
    a = np.concatenate(A); b = np.concatenate(B); cap = np.concatenate(C); kind = np.concatenate(K)
    keep = a != b
    a, b, cap, kind = a[keep], b[keep], cap[keep], kind[keep]
    key = _pack(a, b, n_v)
    # one edge per pair: the STRICTEST cap (the budget the solve grants
    # along a shared edge); a ring edge beats a chord of equal cap
    order = np.lexsort((kind, cap, key))
    key, a, b, cap, kind = key[order], a[order], b[order], cap[order], kind[order]
    _u, first = np.unique(key, return_index=True)
    a, b, cap, kind, key = a[first], b[first], cap[first], kind[first], key[first]
    kind = kind.copy()
    kind[np.isin(key, centre)] = CENTRELINE
    length = np.hypot(xy[a, 0] - xy[b, 0], xy[a, 1] - xy[b, 1])
    keep = length > 0.0
    a, b, cap, kind, length = a[keep], b[keep], cap[keep], kind[keep], length[keep]
    stats = {"nodes": len(nodes), "edges": int(len(a)), "faces": n_faces,
             "ring": int(np.sum(kind == RING)), "chord": int(np.sum(kind == CHORD)),
             "centreline": int(np.sum(kind == CENTRELINE))}
    return RouteGraph(n_v, frozenset(nodes), a, b, length, cap, kind, stats)


_CACHE: dict[int, tuple[PlanarMap, Law, RouteGraph]] = {}


def routes(pm: PlanarMap, law: Law) -> RouteGraph:
    """The (cached) route graph of ``pm`` under ``law``."""
    hit = _CACHE.get(id(pm))
    if hit is not None and hit[0] is pm and hit[1] is law:
        return hit[2]
    g = build_routes(pm, law)
    _CACHE.clear()
    _CACHE[id(pm)] = (pm, law, g)
    return g


def route_neighbours(g: RouteGraph, sources: _t.Iterable[int], window_m: float,
                     k: int, targets: _t.Container[int] | None = None,
                     chunk: int = 256) -> list[tuple[int, int, float, float]]:
    """For every source vertex its ``k`` nearest graph vertices BY ROUTE
    DISTANCE within ``window_m`` (route metres): ``(a, b, dist, budget)``
    with ``a < b``, deduplicated; ``dist`` is the shortest path's plan
    length, ``budget`` the sum of ``cap · len`` along THAT path.  A
    vertex with no pavement path inside the window pairs with nothing —
    the pair does not exist (04o).  ``targets`` restricts the partners."""
    srcs = sorted(v for v in sources if v in g.nodes)
    if not srcs or k <= 0:
        return []
    m = g.csr("length", max_len=window_m)
    wb = g.edge_budget()
    seen: set[tuple[int, int]] = set()
    out: list[tuple[int, int, float, float]] = []
    for c0 in range(0, len(srcs), chunk):
        idx = srcs[c0:c0 + chunk]
        D, P = dijkstra(m, directed=False, indices=idx, limit=window_m,
                        return_predecessors=True)
        for i, s in enumerate(idx):
            row = D[i]
            reached = np.flatnonzero(np.isfinite(row))
            reached = reached[reached != s]
            if targets is not None:
                reached = np.array([t for t in reached if t in targets], dtype=np.int64)
            if reached.size == 0:
                continue
            order = reached[np.argsort(row[reached], kind="stable")][:k]
            bud: dict[int, float] = {s: 0.0}
            pred = P[i]
            for t in order:
                t = int(t)
                # walk the predecessor chain back to a memoised vertex
                path: list[int] = []
                u = t
                while u not in bud:
                    path.append(u)
                    u = int(pred[u])
                acc = bud[u]
                for v in reversed(path):
                    p = int(pred[v])
                    acc += wb[(p, v) if p < v else (v, p)]
                    bud[v] = acc
                key = (s, t) if s < t else (t, s)
                if key in seen:
                    continue
                seen.add(key)
                out.append((key[0], key[1], float(row[t]), bud[t]))
    return out


def reach(g: RouteGraph, pins: _t.Mapping[int, float]
          ) -> dict[int, tuple[float, float]]:
    """THE REACH BAND: for every graph vertex a route joins to a pin,
    ``(floor, ceiling)`` = ``(max_p z_p − B(p, v), min_p z_p + B(p, v))``
    where ``B`` is the least ``Σ cap·len`` over every route from pin
    ``p`` — the envelope every hard path row from the thresholds implies
    (v1 ``spine_value_fields``: a route metric).  A vertex no route
    reaches is absent; a vertex whose floor exceeds its ceiling is
    present as such (the pins contradict along the routes)."""
    idx = sorted(v for v in pins if v in g.nodes)
    if not idx:
        return {}
    m = g.csr("budget")
    D = dijkstra(m, directed=False, indices=idx)
    z = np.array([pins[v] for v in idx], dtype=float)[:, None]
    hi = np.min(z + D, axis=0)
    lo = np.max(z - D, axis=0)
    ok = np.isfinite(hi)
    return {int(v): (float(lo[v]), float(hi[v])) for v in np.flatnonzero(ok)
            if int(v) in g.nodes}


def route_path(g: RouteGraph, a: int, b: int, max_len: float | None = None
               ) -> tuple[float, float, list[int]] | None:
    """The shortest route from ``a`` to ``b``: ``(dist, budget,
    vertices)``, or ``None`` when no pavement path joins them (inside
    ``max_len`` when given).  One pair — an instrument, not the
    population's engine."""
    if a not in g.nodes or b not in g.nodes:
        return None
    m = g.csr("length", max_len=max_len)
    D, P = dijkstra(m, directed=False, indices=[a], return_predecessors=True,
                    limit=np.inf if max_len is None else max_len)
    if not np.isfinite(D[0][b]):
        return None
    wb = g.edge_budget()
    path = [b]
    while path[-1] != a:
        path.append(int(P[0][path[-1]]))
    path.reverse()
    bud = sum(wb[(u, v) if u < v else (v, u)] for u, v in zip(path, path[1:]))
    return float(D[0][b]), float(bud), path
