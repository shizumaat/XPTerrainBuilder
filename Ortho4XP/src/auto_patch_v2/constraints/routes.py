"""THE ROUTE GRAPH (RULINGS 2026-09-04o: "feasible elevations propagate
out from runway thresholds and have to follow taxi routes ... aircraft
can't travel straight across the grass; they have to follow taxi routes,
which is what follows the grade cap").

The graph an aircraft travels (RULINGS 2026-09-05v, 04o applied): NODES
are the planar vertices on airside pavement; EDGES are the MOVEMENT-
SURFACE ROUTE NETWORK — every ring edge of an airside pavement face
(runway-family and taxi-family rings, apron PERIMETERS), the taxi
centrelines (a centreline is a cut line through every pavement region,
so a 1202 taxilane crossing an apron is a ring edge of the apron faces
it splits, priced at the apron cap through ``edge_cap``) and the
per-stretch chords of a taxi-family face (the face is a PLANE shape:
any two of its vertices on one stretch are a travel path,
``rulesets.taxi.longitudinal within_shape``, 04t-3).  NO APRON PLAN
CHORD: a chord across an apron's body is the apron law's own hard-but-
relaxable row (``constraints.apron``), never a route — measured HECA
2026-09-05: a path cutting pav132 on a 700 m chord at 1 % granted 7 m
where the taxi route around it grants 43 m, and the reach bands are
hard, so relaxing the apron rows could never free them (the §4 reading
of ``relaxation-without-certificate-spec.md`` is withdrawn).  The twin:
the graph carries no CHORD edge whose two endpoints lie on one apron
face — a taxi chord along a run shared with an apron is dropped too
(its ring edges are the route).  A pad hole's rim inside an apron is
therefore an island unless a centreline reaches it: it takes no reach
band and no perimeter no-step pair (the pad law and the apron frontage
rows bind it).  SERVICE ROADS ARE EXCLUDED from airside reach (v1
``config.REACH_NO_SERVICE_SPINES``; memory ``reach-follows-centerlines``):
the groundside roles never contribute a node or an edge, and a
``road_centerline`` breakline adds nothing.

Each edge carries its PLAN LENGTH and the CAP of the face it lies in —
the strictest where two faces share it, which is the budget the solve
actually grants along it; a taxi CENTRELINE edge carries its STRETCH's
cap and a taxi-family chord its per-stretch price (RULINGS 2026-09-04t-3,
``constraints.stretches`` — the same rows ``taxi`` generates), a chord to
a pad vertex the pad's cap (frontage).  Two readings:

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

THE RUNWAY IS LIKE AN APRON IN THE GRAPH (RULINGS 2026-09-05z, spec
``relaxation-without-certificate-spec.md`` §7 amended): crossable and
followed along its CENTRELINE, its EDGES never graph edges.  A runway-
family face contributes (a) its centreline — the ``runway_profile``
breakline chain (consecutive split chains bridged) at the runway
longitudinal cap by code (``rulesets.<auth>.runway.longitudinal``), the
threshold pins on it; (b) the 1202 taxi routes CROSSING the runway at
the runway cap — recovered from ``airport.taxi_edges`` clipped to the
runway slab (classify cut them off the centrelines), joined to the
ridge's bracketing stations where they cross it and to the runway edge
vertex where they enter (the planar vertex the cut centreline ended
on, within the weld spacing); (c) an edge vertex on no crossing hops
to the NEAREST crossing / centreline vertex of its own face ring at
the runway cap over the RING distance — as an apron perimeter reaches
its taxilane — never a runway ring edge as a route.  Measured HECA
2026-09-05 (certificate, 9 rows): runway 05C/23C's two edges at stubs
pav91 / pav101, 60 m apart and tied within ±0.455 m by the transverse
law, were 3,206 m vs 6,417 m from the low pin because the graph
routed a crossing around the runway end.

``scipy.sparse.csgraph`` does the walking; nothing here is O(n²) over
the map.  Pure over the planar map and the law; no shapely, no v1.  It
lives beside the generators (not under ``planar/``) because the
constraints read it and the dependency law lets a generator import law
and model only (M0 §1, ``test_dependency_direction``).
"""
from __future__ import annotations

import dataclasses as _dc
import math
import typing as _t

import numpy as np
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import dijkstra

from ..law import Law
from ..law.tables import (is_rigid_role, is_value_role, role_cap, role_family,
                          role_side)
from ..model.airport import Airport
from ..model.planar import EdgeKind, PlanarMap
from .geometry import project_to_chain
from .stretches import edge_cap, pair_caps, stretches

__all__ = ["RouteGraph", "route_roles", "build_routes", "routes",
           "route_neighbours", "reach", "route_path"]

#: Edge provenance codes (``RouteGraph.kind``).  FRONTAGE: a hole rim's
#: hop to the nearest vertex of another ring of its face (CANDIDATE
#: amendment to 2026-09-05v, measured, NOT ruled — see build_routes).
#: CROSSING: a 1202 taxi route across a runway (05z b); EDGE_HOP: a
#: runway edge vertex's hop to its ring's nearest crossing / centreline
#: vertex over the ring distance (05z c).
RING, CHORD, CENTRELINE, FRONTAGE, CROSSING, EDGE_HOP = 0, 1, 2, 3, 4, 5
RIDGE_KIND = "runway_profile"


@_dc.dataclass(frozen=True)
class RouteGraph:
    """The route graph of one planar map (module docstring)."""

    n: int                                  # planar vertex count (ids dense)
    nodes: frozenset[int]                   # airside pavement vertices
    a: np.ndarray                           # edge endpoints, a < b
    b: np.ndarray
    length: np.ndarray                      # plan metres
    cap: np.ndarray                         # grade fraction along the edge
    kind: np.ndarray                        # RING / CHORD / CENTRELINE / ...
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


def _runway_frame(rw) -> tuple[float, float, float, float, float, float, float]:
    """``(ax, ay, ux, uy, L, h, L0)``: the runway slab's axis frame —
    physical end to physical end (overruns included, the classify
    ``runway_rectangle``), half width ``h``."""
    (ax, ay), (bx, by) = rw.ends[0].xy, rw.ends[1].xy
    L0 = math.hypot(bx - ax, by - ay)
    if L0 <= 0.0:
        return ax, ay, 0.0, 0.0, 0.0, rw.width_m / 2.0, 0.0
    ux, uy = (bx - ax) / L0, (by - ay) / L0
    ax, ay = ax - ux * rw.ends[0].overrun_m, ay - uy * rw.ends[0].overrun_m
    L = L0 + rw.ends[0].overrun_m + rw.ends[1].overrun_m
    return ax, ay, ux, uy, L, rw.width_m / 2.0, L0


def _runway_crossings(law: Law, airport: Airport, xy: np.ndarray,
                      ridge_by_ref: _t.Mapping[str, list[list[int]]],
                      ring_by_ref: _t.Mapping[str, set[int]], tol: float
                      ) -> tuple[list[tuple[int, int, float, float]], set[int], int]:
    """RULINGS 2026-09-05z (b): the 1202 taxi routes CROSSING each runway
    as graph edges at the runway longitudinal cap.  Every non-runway
    ``taxi_edge`` is clipped to the slab; the clipped parts form a small
    POINTS GRAPH per runway — an end on the slab boundary is an ENTRY
    (the runway ring vertex the cut centreline ended on, within
    ``tol``), an end at a network node inside the slab an interior
    point (HECA 05C/23C, measured 2026-09-05: the crossing at stubs
    pav91 / pav101 is centreline node 257 → node 437, 14.6 m off the
    ridge inside the slab → node 436 outside — no single part both
    enters and meets the ridge), and where a part meets the ridge its
    meeting point joins the two bracketing stations.  From every entry
    the shortest path through interior points to each TERMINAL (a
    station or another entry) is one graph edge of that length.
    Returns ``(edges, entries, unmatched)``; ``edges`` are ``(a, b, cap,
    length)``."""
    import heapq
    out: list[tuple[int, int, float, float]] = []
    entries: set[int] = set()
    unmatched = 0
    node_xy = {nid: n.xy for nid, n in airport.taxi_nodes.items()}
    for rw in airport.runways:
        chains = ridge_by_ref.get(rw.id) or []
        ring_v = ring_by_ref.get(rw.id)
        rc = role_cap(law, "runway", rw.code_number, rw.code_letter)
        if rc is None or not ring_v or not chains:
            continue
        cap = rc.longitudinal
        ax, ay, ux, uy, L, h, L0 = _runway_frame(rw)
        if L <= 0.0:
            continue
        rv = np.fromiter(sorted(ring_v), np.int64)
        rxy = xy[rv]
        chain_xy = [[(float(xy[v, 0]), float(xy[v, 1])) for v in ch] for ch in chains]

        def st(p):
            dx, dy = p[0] - ax, p[1] - ay
            return dx * ux + dy * uy, -dx * uy + dy * ux

        def match(p):
            d = np.hypot(rxy[:, 0] - p[0], rxy[:, 1] - p[1])
            j = int(np.argmin(d))
            return int(rv[j]) if d[j] <= tol else None

        def ridge_join(X):
            best = None
            for ci, ch in enumerate(chains):
                if len(ch) < 2:
                    continue
                d, k, _t_, _s = project_to_chain(X, chain_xy[ci])
                if best is None or d < best[0]:
                    best = (d, ci, k)
            if best is None:
                return []
            _d, ci, k = best
            return [(chains[ci][k], math.hypot(X[0] - chain_xy[ci][k][0], X[1] - chain_xy[ci][k][1])),
                    (chains[ci][k + 1], math.hypot(X[0] - chain_xy[ci][k + 1][0],
                                                   X[1] - chain_xy[ci][k + 1][1]))]

        # the points graph: ("v", ring vertex) entries / stations, ("n", node)
        # interior network nodes, ("x", i) ridge meeting points
        adj: dict[tuple, list[tuple[tuple, float]]] = {}

        def link(p, q, d):
            if p != q:
                adj.setdefault(p, []).append((q, d))
                adj.setdefault(q, []).append((p, d))
        n_x = 0
        local_entries: set[int] = set()
        for e in airport.taxi_edges:
            if e.is_runway or e.a not in node_xy or e.b not in node_xy:
                continue
            P, Q = node_xy[e.a], node_xy[e.b]
            (s0, t0), (s1, t1) = st(P), st(Q)
            lo, hi = 0.0, 1.0
            ok = True
            for pk, qk in ((-(s1 - s0), s0), (s1 - s0, L - s0),
                           (-(t1 - t0), t0 + h), (t1 - t0, h - t0)):
                if pk == 0.0:
                    if qk < 0.0:
                        ok = False
                        break
                    continue
                r = qk / pk
                if pk < 0.0:
                    lo = max(lo, r)
                else:
                    hi = min(hi, r)
            if not ok or hi <= lo:
                continue
            ends = []
            for u_, nid in ((lo, e.a), (hi, e.b)):
                p = (P[0] + u_ * (Q[0] - P[0]), P[1] + u_ * (Q[1] - P[1]))
                node = nid if u_ in (0.0, 1.0) else None
                s_, t_ = st(p)
                on_boundary = node is None or min(abs(abs(t_) - h), abs(s_), abs(L - s_)) <= tol
                ends.append((p, t_, node, on_boundary))
            (p0, ta, n0, b0), (p1, tb, n1, b1) = ends
            if abs(ta) <= tol and abs(tb) <= tol:
                continue                      # runs ALONG the centreline: (a) carries it
            keys = []
            for p, _t_, node, onb in ends:
                if onb:
                    v = match(p)
                    if v is None:
                        unmatched += 1
                        keys.append(None)
                        continue
                    entries.add(v); local_entries.add(v)
                    keys.append((("v", v), p))
                else:
                    keys.append((("n", node), p))
            if ta * tb <= 0.0:
                w = ta / (ta - tb) if ta != tb else 0.0
                X = (p0[0] + w * (p1[0] - p0[0]), p0[1] + w * (p1[1] - p0[1]))
                kx = ("x", n_x); n_x += 1
                for S, dS in ridge_join(X):
                    link(kx, ("v", S), dS)
                for kp in keys:
                    if kp is not None:
                        link(kp[0], kx, math.hypot(kp[1][0] - X[0], kp[1][1] - X[1]))
            elif keys[0] is not None and keys[1] is not None:
                link(keys[0][0], keys[1][0], math.hypot(p0[0] - p1[0], p0[1] - p1[1]))
        # from every entry: the shortest path to each terminal (a station
        # or another entry) through interior points only
        for v in sorted(local_entries):
            src = ("v", v)
            dist = {src: 0.0}
            heap = [(0.0, 0, src)]
            tick = 0
            while heap:
                d, _k, u = heapq.heappop(heap)
                if d > dist.get(u, math.inf):
                    continue
                if u != src and u[0] == "v":
                    continue                  # a terminal is never expanded
                for w_, dw in adj.get(u, ()):
                    nd = d + dw
                    if nd < dist.get(w_, math.inf):
                        dist[w_] = nd
                        tick += 1
                        heapq.heappush(heap, (nd, tick, w_))
            for u, d in dist.items():
                if u != src and u[0] == "v" and d > 0.0:
                    out.append((v, u[1], cap, d))
    return out, entries, unmatched


def _ring_hops(ring: list[int], xy: np.ndarray, anchors: _t.Container[int]
               ) -> list[tuple[int, int, float]]:
    """RULINGS 2026-09-05z (c): ``(v, anchor, ring distance)`` for every
    ring vertex that is no anchor — the nearest anchor along the ring
    (cyclic), never across the face."""
    idx = [i for i, v in enumerate(ring) if v in anchors]
    if not idx or len(idx) == len(ring):
        return []
    r = np.array(ring, np.int64)
    seg = np.hypot(xy[np.roll(r, -1), 0] - xy[r, 0], xy[np.roll(r, -1), 1] - xy[r, 1])
    pos = np.concatenate([[0.0], np.cumsum(seg)[:-1]])
    total = float(seg.sum())
    if total <= 0.0:
        return []
    ai = np.array(idx, np.int64)
    out: list[tuple[int, int, float]] = []
    for i, v in enumerate(ring):
        if v in anchors:
            continue
        d = np.abs(pos[ai] - pos[i])
        d = np.minimum(d, total - d)
        j = int(np.argmin(d))
        out.append((v, ring[idx[j]], float(d[j])))
    return out


def build_routes(pm: PlanarMap, law: Law, airport: Airport | None = None) -> RouteGraph:
    """The route graph of ``pm`` under ``law`` (module docstring);
    ``airport`` supplies the 1202 network the runway crossings are
    recovered from (without it a runway is followed along its
    centreline only)."""
    roles = route_roles(law)
    taxi = set(law.tables.precedence.taxi_family.members)
    rw_fam = frozenset(r for r in law.tables.precedence.roles if role_family(law, r) == "runway")
    weld_m = float(law.tables.emit.identity.weld_spacing_m)
    rigid = {r for r in law.tables.precedence.roles if is_rigid_role(law, r)}
    min_d = law.tables.emit.identity.min_distinct_spacing_m
    mesh_roles = frozenset(law.tables.emit.within_shape.junction_mesh_roles)
    hop_m = float(law.tables.emit.no_step.window_m)
    pad_cap = law.tables.common.roles["building"].longitudinal
    st = stretches(pm, law)
    face_caps: dict[int, tuple[float, float] | None] = {}
    for fid, f in pm.faces.items():
        rc = role_cap(law, f.role, f.code_number, f.code_letter)
        face_caps[fid] = None if rc is None else (rc.longitudinal, rc.transverse)
    n_v = len(pm.vertices)
    xy = np.zeros((n_v, 2), float)
    for vid, v in pm.vertices.items():
        xy[vid] = v.xy
    # spine vertices (taxi centrelines) and pad-shared vertices: a taxi
    # chord to a pad vertex carries the pad's cap (frontage)
    strict_v = np.zeros(n_v, bool)
    f_rigid = np.zeros(n_v, bool)
    for bl in pm.breaklines.values():
        if bl.kind == "taxi_centerline":
            strict_v[list(bl.vertices(pm))] = True
    for f in pm.faces.values():
        if f.role in rigid:
            for cyc in (f.ring, *f.holes):
                strict_v[list(pm.ring_vertices(cyc))] = True
                f_rigid[list(pm.ring_vertices(cyc))] = True
    centre = np.array(sorted({e.a * n_v + e.b if e.a < e.b else e.b * n_v + e.a
                              for e in pm.edges.values() if e.kind is EdgeKind.CENTERLINE}),
                      dtype=np.int64)
    # THE RUNWAY FAMILY (RULINGS 2026-09-05z): the ridge chains by runway,
    # the runway ring vertices by runway, the crossings from the network
    ridge_edges: set[int] = set()
    ridge_by_ref: dict[str, list[list[int]]] = {}
    for bl in pm.breaklines.values():
        if bl.kind == RIDGE_KIND:
            ridge_edges.update(bl.edges)
            ridge_by_ref.setdefault(bl.ref, []).append(list(bl.vertices(pm)))
    ring_by_ref: dict[str, set[int]] = {}
    for f in pm.faces.values():
        if f.role in rw_fam and f.role in roles:
            for cyc in (f.ring, *f.holes):
                ring_by_ref.setdefault(f.ref, set()).update(pm.ring_vertices(cyc))
    xing_edges: list[tuple[int, int, float, float]] = []
    entries: set[int] = set()
    n_unmatched = 0
    if airport is not None and ridge_by_ref:
        xing_edges, entries, n_unmatched = _runway_crossings(
            law, airport, xy, ridge_by_ref, ring_by_ref, weld_m)
    A, B, C, K = [], [], [], []
    LEN: list[np.ndarray] = []        # explicit lengths (crossings, hops); NaN = plan chord
    nodes: set[int] = set()
    n_faces = 0
    ref_cap: dict[str, float] = {}
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
        if f.role in rw_fam:
            # (a) the centreline (ridge) edges and any taxi centreline part
            # noded inside the slab, at the runway cap; (c) every other ring
            # vertex hops to its ring's nearest anchor over the ring distance;
            # the runway's EDGES are no route
            ref_cap[f.ref] = min(cap, ref_cap.get(f.ref, cap))
            for cyc in (f.ring, *f.holes):
                ring = list(pm.ring_vertices(cyc))
                anchors: set[int] = set()
                for eid in cyc:
                    e = pm.edges[eid]
                    if eid in ridge_edges or e.kind is EdgeKind.CENTERLINE:
                        anchors.add(e.a); anchors.add(e.b)
                        A.append(np.array([min(e.a, e.b)], np.int64))
                        B.append(np.array([max(e.a, e.b)], np.int64))
                        C.append(np.full(1, cap))
                        K.append(np.full(1, CENTRELINE, np.int8))
                        LEN.append(np.full(1, np.nan))
                anchors |= entries & set(ring)
                hops = _ring_hops(ring, xy, anchors)
                if hops:
                    ha = np.array([h[0] for h in hops], np.int64)
                    hb = np.array([h[1] for h in hops], np.int64)
                    A.append(np.minimum(ha, hb)); B.append(np.maximum(ha, hb))
                    C.append(np.full(len(hops), cap)); K.append(np.full(len(hops), EDGE_HOP, np.int8))
                    LEN.append(np.array([h[2] for h in hops], float))
                for v in ring:
                    if v not in seen:
                        seen.add(v)
                        verts.append(v)
            nodes.update(verts)
            continue
        for cyc in (f.ring, *f.holes):
            ring = list(pm.ring_vertices(cyc))
            m = len(ring)
            ra = np.array(ring, np.int64)
            rb = np.roll(ra, -1)
            A.append(np.minimum(ra, rb)); B.append(np.maximum(ra, rb))
            C.append(np.full(m, cap)); K.append(np.full(m, RING, np.int8))
            LEN.append(np.full(m, np.nan))
            for v in ring:
                if v not in seen:
                    seen.add(v)
                    verts.append(v)
        nodes.update(verts)
        if f.role in taxi:
            # per-stretch chords (04t-3), a pad endpoint at the pad's cap;
            # a JUNCTION BODY's pairs are its common-stretch pairs ONLY
            # (04y, the rows ``taxi`` generates) — measured HECA
            # 2026-09-05: junction pav132's every-pair chords (1300 m and
            # 1175 m from a hangar-pad rim at the pad cap) were the
            # min-budget route from 05L/23R to runway 05C/23C's edge
            pc = pair_caps(pm, law, st, f.id, verts, cap, min_d,
                           common_only=f.role in mesh_roles)
            if pc:
                pa = np.array([p[0] for p in pc], np.int64)
                pb = np.array([p[1] for p in pc], np.int64)
                cc = np.array([min(p[2], pad_cap) if (strict_v[p[0]] and f_rigid[p[0]])
                               or (strict_v[p[1]] and f_rigid[p[1]]) else p[2]
                               for p in pc], float)
                A.append(np.minimum(pa, pb)); B.append(np.maximum(pa, pb))
                C.append(cc); K.append(np.full(len(pc), CHORD, np.int8))
                LEN.append(np.full(len(pc), np.nan))
        # PAD FRONTAGE HOPS — CANDIDATE amendment to 2026-09-05v, measured
        # on CYXY, NOT RULED: with no apron plan chord a hole rim (a pad
        # inside an apron / junction face) is a route ISLAND — no reach
        # band, no no_step pair to the pavement 0.5 m away (CYXY
        # building6/7: building|building 1.95 m, 5 pad twins red).  Each
        # hole vertex hops to the NEAREST vertex of every other ring of
        # its face inside the no-step window — the shortest link there is,
        # never a plan chord across the body — at the pad cap.
        if hop_m > 0.0 and f.holes:
            rings = [np.array(list(pm.ring_vertices(c)), np.int64) for c in (f.ring, *f.holes)]
            for hi in range(1, len(rings)):
                src = rings[hi]
                for oj, other in enumerate(rings):
                    if oj == hi or len(other) == 0:
                        continue
                    dd = np.hypot(xy[src, None, 0] - xy[None, other, 0],
                                  xy[src, None, 1] - xy[None, other, 1])
                    j = np.argmin(dd, axis=1)
                    ok = dd[np.arange(len(src)), j] <= hop_m
                    if ok.any():
                        pa, pb = src[ok], other[j[ok]]
                        A.append(np.minimum(pa, pb)); B.append(np.maximum(pa, pb))
                        C.append(np.full(int(ok.sum()), min(cap, pad_cap)))
                        K.append(np.full(int(ok.sum()), FRONTAGE, np.int8))
                        LEN.append(np.full(int(ok.sum()), np.nan))
    # (b) the crossings; (a) consecutive split ridge chains of one runway
    # bridged at the runway cap over the straight distance (as
    # ``runway_profile`` bridges its Diff rows)
    if xing_edges:
        xa = np.array([x[0] for x in xing_edges], np.int64)
        xb = np.array([x[1] for x in xing_edges], np.int64)
        A.append(np.minimum(xa, xb)); B.append(np.maximum(xa, xb))
        C.append(np.array([x[2] for x in xing_edges], float))
        K.append(np.full(len(xing_edges), CROSSING, np.int8))
        LEN.append(np.array([x[3] for x in xing_edges], float))
    for ref, chs in ridge_by_ref.items():
        if len(chs) < 2 or ref not in ref_cap:
            continue
        longest = max(chs, key=len)
        p0, p1 = xy[longest[0]], xy[longest[-1]]
        ux, uy = p1[0] - p0[0], p1[1] - p0[1]
        nrm = math.hypot(ux, uy)
        if nrm <= 0.0:
            continue
        ux, uy = ux / nrm, uy / nrm

        def along(v):
            return (xy[v, 0] - p0[0]) * ux + (xy[v, 1] - p0[1]) * uy
        ordered = sorted(chs, key=lambda c: min(along(c[0]), along(c[-1])))
        ordered = [c if along(c[0]) <= along(c[-1]) else list(reversed(c)) for c in ordered]
        for prev, nxt in zip(ordered, ordered[1:]):
            u, v = prev[-1], nxt[0]
            if u != v:
                A.append(np.array([min(u, v)], np.int64)); B.append(np.array([max(u, v)], np.int64))
                C.append(np.full(1, ref_cap[ref])); K.append(np.full(1, CENTRELINE, np.int8))
                LEN.append(np.full(1, np.nan))
    if not A:
        z = np.zeros(0, np.int64)
        return RouteGraph(n_v, frozenset(), z, z, np.zeros(0), np.zeros(0),
                          np.zeros(0, np.int8), {"nodes": 0, "edges": 0, "faces": 0,
                                                  "ring": 0, "chord": 0, "centreline": 0,
                                                  "frontage": 0, "crossing": 0, "edge_hop": 0,
                                                  "crossing_unmatched": n_unmatched})
    a = np.concatenate(A); b = np.concatenate(B); cap = np.concatenate(C); kind = np.concatenate(K)
    ln = np.concatenate(LEN)
    keep = a != b
    a, b, cap, kind, ln = a[keep], b[keep], cap[keep], kind[keep], ln[keep]
    plan = np.hypot(xy[a, 0] - xy[b, 0], xy[a, 1] - xy[b, 1])
    ln = np.where(np.isnan(ln), plan, ln)
    key = _pack(a, b, n_v)
    # one edge per pair: the STRICTEST cap (the budget the solve grants
    # along a shared edge); a ring edge beats a chord of equal cap; the
    # least BUDGET where two explicit lengths compete
    order = np.lexsort((kind, cap * ln, key))
    key, a, b, cap, kind, ln = key[order], a[order], b[order], cap[order], kind[order], ln[order]
    _u, first = np.unique(key, return_index=True)
    a, b, cap, kind, key, ln = a[first], b[first], cap[first], kind[first], key[first], ln[first]
    kind = kind.copy()
    kind[np.isin(key, centre)] = CENTRELINE
    # a taxi centreline edge holds ITS STRETCH's cap (04t-3), which may be
    # looser than the faces it splits (G at 3 % through a letter-D junction)
    cl_cap: dict[int, float] = {}
    for eid, e in pm.edges.items():
        if eid in st.by_edge:
            fs = pm.faces_of_edge(eid)
            if fs and all(pm.faces[fid].role in rw_fam for fid in fs):
                continue                      # a crossing part inside the slab: runway cap
            c = edge_cap(pm, law, st, eid, face_caps)
            if c is not None:
                cl_cap[int(min(e.a, e.b)) * n_v + int(max(e.a, e.b))] = c[0]
    if cl_cap:
        cap = cap.copy()
        for idx in np.flatnonzero(np.isin(key, np.array(list(cl_cap), np.int64))):
            cap[idx] = cl_cap[int(key[idx])]
    # NO APRON PLAN CHORD (2026-09-05v): a CHORD with both endpoints on one
    # apron face (a taxi chord along a run the face shares with an apron)
    # is not a route — the ring edges along that run are
    drop = np.zeros(len(a), bool)
    is_chord = kind == CHORD
    for f in pm.faces.values():
        if f.role != "apron" or not is_chord.any():
            continue
        fv = np.fromiter({v for cyc in (f.ring, *f.holes) for v in pm.ring_vertices(cyc)},
                         np.int64)
        drop |= is_chord & np.isin(a, fv) & np.isin(b, fv)
    keep = ~drop
    a, b, cap, kind, ln = a[keep], b[keep], cap[keep], kind[keep], ln[keep]
    keep = ln > 0.0
    a, b, cap, kind, length = a[keep], b[keep], cap[keep], kind[keep], ln[keep]
    stats = {"nodes": len(nodes), "edges": int(len(a)), "faces": n_faces,
             "ring": int(np.sum(kind == RING)), "chord": int(np.sum(kind == CHORD)),
             "centreline": int(np.sum(kind == CENTRELINE)),
             "frontage": int(np.sum(kind == FRONTAGE)),
             "crossing": int(np.sum(kind == CROSSING)),
             "edge_hop": int(np.sum(kind == EDGE_HOP)),
             "crossing_unmatched": n_unmatched}
    return RouteGraph(n_v, frozenset(nodes), a, b, length, cap, kind, stats)


_CACHE: dict[int, tuple[PlanarMap, Law, Airport | None, RouteGraph]] = {}


def routes(pm: PlanarMap, law: Law, airport: Airport | None = None) -> RouteGraph:
    """The (cached) route graph of ``pm`` under ``law`` (``airport`` as
    :func:`build_routes`)."""
    hit = _CACHE.get(id(pm))
    if hit is not None and hit[0] is pm and hit[1] is law and hit[2] is airport:
        return hit[3]
    g = build_routes(pm, law, airport)
    _CACHE.clear()
    _CACHE[id(pm)] = (pm, law, airport, g)
    return g


def route_neighbours(g: RouteGraph, sources: _t.Iterable[int], window_m: float,
                     k: int, targets: _t.Container[int] | None = None,
                     chunk: int = 256,
                     exclude: _t.Mapping[int, _t.Container[int]] | None = None
                     ) -> list[tuple[int, int, float, float]]:
    """For every source vertex its ``k`` nearest graph vertices BY ROUTE
    DISTANCE within ``window_m`` (route metres): ``(a, b, dist, budget)``
    with ``a < b``, deduplicated; ``dist`` is the shortest path's plan
    length, ``budget`` the sum of ``cap · len`` along THAT path.  A
    vertex with no pavement path inside the window pairs with nothing —
    the pair does not exist (04o).  ``targets`` restricts the partners;
    ``exclude[s]`` names partners source ``s`` never pairs with (a pad's
    contact vertex and its own flat group, 04r) — they do not spend its
    ``k``."""
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
            skip = exclude.get(s, ()) if exclude is not None else ()
            if targets is not None or skip:
                reached = np.array([t for t in reached if t not in skip
                                    and (targets is None or t in targets)], dtype=np.int64)
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
