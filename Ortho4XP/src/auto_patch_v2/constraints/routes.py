"""THE ROUTE GRAPH (RULINGS 2026-09-04o: "feasible elevations propagate
out from runway thresholds and have to follow taxi routes ... aircraft
can't travel straight across the grass; they have to follow taxi routes,
which is what follows the grade cap").

THE GRAPH IS THE 1202 CENTRELINE NETWORK ONLY (RULINGS 2026-09-05aa, the
owner's verdict on the HECA limiting-chain KML; spec ``relaxation-
without-certificate-spec.md`` §8; v1's model, memory ``reach-follows-
centerlines``).  Its EDGES are

* (i) every TAXI CENTRELINE STRETCH (``constraints.stretches``, the 1202
  network) — every polyline vertex, so every curve and turn is
  followed — at its stretch cap (``edge_cap``: the stretch's letter,
  tightened by a governed non-taxi face it splits, 09-03j; a part noded
  inside a runway slab at the runway cap);
* (ii) every RUNWAY CENTRELINE — the ``runway_profile`` ridge chains
  (consecutive split chains bridged) at the runway longitudinal cap by
  code (``rulesets.<auth>.runway.longitudinal``), the threshold pins on
  it;
* (iii) the 1202 taxi routes CROSSING a runway (05z b) — recovered from
  ``airport.taxi_edges`` clipped to the slab (classify cut them off the
  centrelines), joined to the ridge's bracketing stations where they
  cross it, to the runway ring vertex where they enter, and — RULINGS
  2026-09-06h (a) — from every 1202 node INSIDE the slab by ONE lateral
  hop to the ridge's bracketing stations over its perpendicular distance
  at the runway TRANSVERSE cap (the walk along the ridge from the foot at
  the longitudinal cap) — the node where the route meets the runway's own
  1202 line: a crossing need not cross the ridge to reach it, and the
  interior nodes are route terminals the entry's walk passes through (HECA 05C/23C, measured 2026-09-06: T4 enters the slab
  diagonally at s≈2215 and ENDS at node 257 at s≈2057, 2.4 m off the
  ridge — the entry's reach ran a 32 m perpendicular hop instead of the
  161 m of centreline, a 4.4 m shortcut on the s≈2218 ceiling);

and NOTHING ELSE: no ring edge of any face, no chord of any kind
(stretch, apron, junction), no apron perimeter, no pad frontage hop.
Every one of those was measured at HECA 2026-09-05 as a shortcut across
open pavement or grass that the reach bands then made hard.

THE ATTACHMENT: every pavement ring vertex of a runway / taxi / apron
face that is no station of a centreline of its OWN face attaches by ONE
LATERAL HOP to the nearest station of the nearest centreline INSIDE or
TOUCHING that face — the ridge chains on a runway-family face, the
stretches splitting or touching (through a ring vertex) every other
face — over the PERPENDICULAR distance (the foot on the polyline) at
the face's TRANSVERSE cap: ``runway.transverse_max`` for a runway edge,
the taxi transverse cap for a taxiway edge, the apron cap for an apron
vertex.  A crossing ENTRY whose crossing reaches the ridge IS a station
of a centreline inside its runway face (the crossing, 06h a) and hops
no more on that face: it reaches the ridge along the crossing.  A PAD attaches at its CONTACT (RULINGS 2026-09-05ab, spec §9):
a rim vertex welded to the pavement IS that pavement vertex and attaches
as one; a rim vertex bound by a ``frontage_near_miss`` row (a sub-metre
source gap, ``pads.frontage_contacts``) joins its apron vertex by ONE
CONTACT edge over that gap at the frontage row's own cap — a walk from
the pad passes THROUGH its contact onto the network (the contact is the
pad's doorway, not a leaf it stops at), so ``no_step.pad_pavement_
edges`` finds the pavement from the pad exactly as from a welded rim.
The rest of the pad is rigid and no node.  A vertex with nothing to
attach to is NO NODE: it has no reach band and no no_step route
distance — the shape laws alone govern it.  SERVICE ROADS ARE EXCLUDED from airside reach
(v1 ``config.REACH_NO_SERVICE_SPINES``): the groundside roles never
contribute a node or an edge, and a ``road_centerline`` breakline adds
nothing.

Each edge carries its LENGTH and the CAP the solve grants along it — the
least budget where two edges compete for one pair.  Two readings:

* ROUTE DISTANCE between two vertices = the shortest path by length; the
  path's BUDGET = ``Σ cap_e · len_e`` along that very path (the pair's
  own caps: an apron↔taxiway pair carries the taxiway's cap on the
  taxiway stretch and the apron's on its hop, 04q-1) —
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
import math
import typing as _t

import numpy as np
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import dijkstra

from ..law import Law
from ..law.tables import (is_rigid_role, is_value_role, role_cap, role_family,
                          role_side, runway_transverse_max)
from ..model.airport import Airport
from ..model.planar import PlanarMap
from .geometry import project_to_chain
from .stretches import edge_cap, stretches

__all__ = ["RouteGraph", "route_roles", "build_routes", "routes",
           "route_neighbours", "route_pairs", "reach", "route_path"]

#: Edge provenance codes (``RouteGraph.kind``).  CENTRELINE: a taxi
#: stretch edge or a runway ridge edge (a split ridge's bridge too);
#: CROSSING: a 1202 taxi route across a runway slab (05z b); LATERAL: a
#: pavement ring vertex's ONE hop to the nearest station of its own
#: face's centreline (05aa); CONTACT: a near-miss pad rim vertex's edge to
#: its frontage apron vertex (05ab).
CENTRELINE, CROSSING, LATERAL, CONTACT = 0, 1, 2, 3
RIDGE_KIND = "runway_profile"


@_dc.dataclass(frozen=True)
class RouteGraph:
    """The route graph of one planar map (module docstring).  ``station``
    marks the NETWORK vertices — those on a centreline (a taxi stretch
    or a runway ridge); every other vertex is a LEAF hanging off the
    network by its hop: a path may start or end at a leaf, never pass
    through one (two hops at a shared corner would otherwise chain into
    a route across the pavement the owner withdrew, 05aa) — so the walk
    is DIRECTED over ``2n`` ids: a leaf's OUT id is ``v``, its IN id
    ``v + n``; a station is one id both ways (:meth:`csr`, :meth:`inbound`)."""

    n: int                                  # planar vertex count (ids dense)
    nodes: frozenset[int]                   # attached airside pavement vertices
    a: np.ndarray                           # edge endpoints, a < b
    b: np.ndarray
    length: np.ndarray                      # plan metres
    cap: np.ndarray                         # grade fraction along the edge
    kind: np.ndarray                        # CENTRELINE / CROSSING / LATERAL / CONTACT
    station: np.ndarray                     # bool per planar vertex: on a centreline
    stats: dict[str, int] = _dc.field(default_factory=dict)
    #: near-miss pad rim vertex -> its frontage apron vertex (CONTACT edges)
    contact_of: dict[int, int] = _dc.field(default_factory=dict)
    #: the FACE an edge belongs to: the face whose ring vertex hops (LATERAL),
    #: the pad face (CONTACT); ``-1`` for a centreline or crossing edge (the
    #: network's own, no single face) — the chain rows (``taxi.taxi_chain``,
    #: RULINGS 2026-09-05ac) cite it so the relaxation reads the row's tier
    face: np.ndarray = _dc.field(default_factory=lambda: np.zeros(0, np.int64))

    @property
    def budget(self) -> np.ndarray:
        """``cap · length`` per edge — metres of lawful rise along it."""
        return self.cap * self.length

    def inbound(self, v: int | np.ndarray) -> int | np.ndarray:
        """The id a walk ARRIVES at vertex ``v`` by (``v`` for a station,
        ``v + n`` for a leaf); a walk LEAVES every vertex by ``v``."""
        return np.where(self.station[v], v, v + self.n) if isinstance(v, np.ndarray) \
            else (int(v) if self.station[v] else int(v) + self.n)

    def vertex(self, ident: int | np.ndarray) -> int | np.ndarray:
        """The planar vertex of a walk id."""
        return ident % self.n

    def csr(self, weight: str = "length", max_len: float | None = None) -> csr_matrix:
        """DIRECTED CSR over the ``2n`` walk ids with ``length`` or
        ``budget`` weights: every edge ``(u, v)`` is ``u → inbound(v)``
        and ``v → inbound(u)``; ``max_len`` drops edges longer than it (an
        edge longer than a window can lie on no path inside it)."""
        w = self.length if weight == "length" else self.budget
        keep = np.ones(len(w), bool) if max_len is None else self.length <= max_len
        contact = self.kind == CONTACT
        w_all = w
        a, b, w = self.a[keep & ~contact], self.b[keep & ~contact], w_all[keep & ~contact]
        rows = [a, b]
        cols = [self.inbound(b), self.inbound(a)]
        data = [w, w]
        # THE CONTACT ARCS (05ab): pad p, contact e.  p leaves through e's
        # OUT id (the walk continues onto e's hop), p reaches e itself, e
        # reaches p, and a walk ARRIVING at e continues into p.
        ca, cb, cw = self.a[keep & contact], self.b[keep & contact], w_all[keep & contact]
        if len(ca):
            pad = np.array([x if int(x) in self.contact_of else y for x, y in zip(ca, cb)], np.int64)
            con = np.where(pad == ca, cb, ca).astype(np.int64)
            rows += [pad, pad, con, self.inbound(con)]
            cols += [con, self.inbound(con), self.inbound(pad), self.inbound(pad)]
            data += [cw, cw, cw, cw]
        m = csr_matrix((np.concatenate(data), (np.concatenate(rows), np.concatenate(cols))),
                       shape=(2 * self.n, 2 * self.n))
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
                      ) -> tuple[list[tuple[int, int, float, float]], set[int], int, set[int]]:
    """RULINGS 2026-09-05z (b) + 2026-09-06h (a): the 1202 taxi routes
    CROSSING each runway as graph edges.  Every non-runway ``taxi_edge``
    is clipped to the slab; the clipped parts form a small POINTS GRAPH
    per runway — an end on the slab boundary is an ENTRY (the runway ring
    vertex the cut centreline ended on, within ``tol``), an end at a
    network node inside the slab an INTERIOR point, and where a part
    meets the ridge its meeting point joins the two bracketing stations.
    Every interior point that is a node of the RUNWAY's own 1202
    centreline (where the taxi route meets the runway line) ALSO joins
    the ridge's bracketing stations by one lateral hop: its perpendicular
    distance at the runway TRANSVERSE cap plus the walk along the ridge
    from the foot at the longitudinal cap (06h a — HECA 05C/23C, measured
    2026-09-05/06: T4 is runway-line node 257 (2.4 m off the ridge at
    s≈2057) → node 437 (17 m off) → node 436 outside; no part crosses the
    ridge, so the crossing never reached it and the entry's perpendicular
    hop stood in for 161 m of centreline).  From every entry the least-BUDGET path through interior
    points to each TERMINAL (a station or another entry) is one graph
    edge carrying that path's budget and length (``cap = budget /
    length``, as a lateral hop is priced).  Returns ``(edges, entries,
    unmatched, ridge_entries)``; ``edges`` are ``(a, b, cap, length)``;
    ``ridge_entries`` the entries whose crossing reaches a ridge station."""
    import heapq
    out: list[tuple[int, int, float, float]] = []
    entries: set[int] = set()
    ridge_entries: set[int] = set()
    unmatched = 0
    node_xy = {nid: n.xy for nid, n in airport.taxi_nodes.items()}
    for rw in airport.runways:
        chains = ridge_by_ref.get(rw.id) or []
        ring_v = ring_by_ref.get(rw.id)
        rc = role_cap(law, "runway", rw.code_number, rw.code_letter)
        if rc is None or not ring_v or not chains:
            continue
        cap = rc.longitudinal
        tcap = runway_transverse_max(law, rw.code_letter, rw.code_number)
        if tcap is None:
            tcap = cap
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

        def ridge_foot(X):
            """``(perpendicular distance, [(station, along)] * 2)`` — the
            foot of ``X`` on the nearest chain and the two stations
            bracketing it with their distance along the segment."""
            best = None
            for ci, ch in enumerate(chains):
                if len(ch) < 2:
                    continue
                d, k, t_, _s = project_to_chain(X, chain_xy[ci])
                if best is None or d < best[0]:
                    best = (d, ci, k, t_)
            if best is None:
                return 0.0, []
            d, ci, k, t_ = best
            (px, py), (qx, qy) = chain_xy[ci][k], chain_xy[ci][k + 1]
            seg = math.hypot(qx - px, qy - py)
            return d, [(chains[ci][k], t_ * seg), (chains[ci][k + 1], (1.0 - t_) * seg)]

        # the points graph: ("v", ring vertex) entries / stations, ("n", node)
        # interior network nodes, ("x", i) ridge meeting points; an arc
        # carries (length, budget)
        adj: dict[tuple, list[tuple[tuple, float, float]]] = {}

        def link(p, q, length, budget):
            if p != q:
                adj.setdefault(p, []).append((q, length, budget))
                adj.setdefault(q, []).append((p, length, budget))
        n_x = 0
        local_entries: set[int] = set()
        # the nodes ON the runway's own 1202 centreline: where a taxi route
        # meets the runway line (T4 at node 257), never a bend of the route
        # inside the slab (node 437, 17 m off the ridge: joined too, the
        # entry reaches the ridge in 56 m and the s≈2218 ceiling reads
        # 110.99; joined at the runway line only it reads 114.52, the
        # ruling's 114.5 — measured 2026-09-06 on the HECA planar map)
        rw_nodes = {n for e in airport.taxi_edges if e.is_runway for n in (e.a, e.b)}
        interior: dict[tuple, tuple[float, float]] = {}
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
                    if node in rw_nodes:
                        interior.setdefault(("n", node), p)
            if ta * tb <= 0.0:
                w = ta / (ta - tb) if ta != tb else 0.0
                X = (p0[0] + w * (p1[0] - p0[0]), p0[1] + w * (p1[1] - p0[1]))
                kx = ("x", n_x); n_x += 1
                for S, dS in ridge_foot(X)[1]:
                    link(kx, ("v", S), dS, cap * dS)
                for kp in keys:
                    if kp is not None:
                        dk = math.hypot(kp[1][0] - X[0], kp[1][1] - X[1])
                        link(kp[0], kx, dk, cap * dk)
            elif keys[0] is not None and keys[1] is not None:
                dk = math.hypot(p0[0] - p1[0], p0[1] - p1[1])
                link(keys[0][0], keys[1][0], dk, cap * dk)
        # THE INTERIOR JOIN (06h a): every 1202 node inside the slab hops
        # once to the ridge's bracketing stations — the perpendicular at
        # the transverse cap, the walk along the ridge at the longitudinal
        # cap (as ``_nearest_station`` prices a ring vertex's hop)
        for kn, p in interior.items():
            d, feet = ridge_foot(p)
            for S, along in feet:
                link(kn, ("v", S), d + along, tcap * d + cap * along)
        # from every entry: the least-budget path to each terminal (a
        # station or another entry) through interior points only
        for v in sorted(local_entries):
            src = ("v", v)
            dist = {src: (0.0, 0.0)}
            heap = [(0.0, 0, src)]
            tick = 0
            while heap:
                b, _k, u = heapq.heappop(heap)
                if b > dist.get(u, (math.inf, 0.0))[0]:
                    continue
                if u != src and u[0] == "v":
                    continue                  # a terminal is never expanded
                for w_, dl, db in adj.get(u, ()):
                    nb = b + db
                    if nb < dist.get(w_, (math.inf, 0.0))[0]:
                        dist[w_] = (nb, dist[u][1] + dl)
                        tick += 1
                        heapq.heappush(heap, (nb, tick, w_))
            for u, (b, ln) in dist.items():
                if u != src and u[0] == "v" and ln > 0.0:
                    out.append((v, u[1], b / ln, ln))
                    if u[1] not in local_entries:
                        ridge_entries.add(v)
    return out, entries, unmatched, ridge_entries


def _nearest_station(pts: np.ndarray,
                     lines: _t.Sequence[tuple[list[int], np.ndarray, np.ndarray]]
                     ) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """For every point the nearest STATION of the nearest line: the
    perpendicular distance to the nearest line (the foot clamped to the
    polyline), the nearer of the two stations bracketing that foot, the
    distance ALONG the segment from that station to the foot, and the
    segment's longitudinal cap — ``(d_perp, station, d_along, cap_l)``;
    station ``-1`` where no line has a segment.  Vectorised over the
    points, one pass per segment.  ``lines`` are ``(chain vertex ids,
    chain xy, per-segment longitudinal cap)``."""
    n = len(pts)
    best_d = np.full(n, np.inf)
    best_v = np.full(n, -1, np.int64)
    best_along = np.zeros(n)
    best_cap = np.zeros(n)
    px, py = pts[:, 0], pts[:, 1]
    for chain, cxy, caps in lines:
        for k in range(len(chain) - 1):
            (ax, ay), (bx, by) = cxy[k], cxy[k + 1]
            vx, vy = bx - ax, by - ay
            l2 = vx * vx + vy * vy
            if l2 <= 0.0:
                continue
            seg = math.sqrt(l2)
            t = np.clip(((px - ax) * vx + (py - ay) * vy) / l2, 0.0, 1.0)
            d = np.hypot(px - (ax + t * vx), py - (ay + t * vy))
            hit = d < best_d
            if not hit.any():
                continue
            near_b = np.hypot(px - bx, py - by) < np.hypot(px - ax, py - ay)
            best_d[hit] = d[hit]
            best_v[hit] = np.where(near_b[hit], chain[k + 1], chain[k])
            best_along[hit] = np.where(near_b[hit], (1.0 - t[hit]) * seg, t[hit] * seg)
            best_cap[hit] = caps[k]
    return best_d, best_v, best_along, best_cap


def build_routes(pm: PlanarMap, law: Law, airport: Airport | None = None) -> RouteGraph:
    """The route graph of ``pm`` under ``law`` (module docstring);
    ``airport`` supplies the 1202 network the runway crossings are
    recovered from (without it a runway is followed along its
    centreline only)."""
    roles = route_roles(law)
    rw_fam = frozenset(r for r in law.tables.precedence.roles if role_family(law, r) == "runway")
    weld_m = float(law.tables.emit.identity.weld_spacing_m)
    min_d = float(law.tables.emit.identity.min_distinct_spacing_m)
    st = stretches(pm, law)
    face_caps: dict[int, tuple[float, float] | None] = {}
    for fid, f in pm.faces.items():
        rc = role_cap(law, f.role, f.code_number, f.code_letter)
        face_caps[fid] = None if rc is None else (rc.longitudinal, rc.transverse)
    n_v = len(pm.vertices)
    xy = np.zeros((n_v, 2), float)
    for vid, v in pm.vertices.items():
        xy[vid] = v.xy
    A, B, C, K = [], [], [], []
    LEN: list[np.ndarray] = []        # explicit lengths (crossings, hops); NaN = plan chord
    FACE: list[np.ndarray] = []       # the edge's face (-1: the network's own)

    def add(a: int, b: int, cap: float, kind: int, length: float = np.nan,
            face: int = -1) -> None:
        A.append(np.array([min(a, b)], np.int64)); B.append(np.array([max(a, b)], np.int64))
        C.append(np.full(1, cap)); K.append(np.full(1, kind, np.int8)); LEN.append(np.full(1, length))
        FACE.append(np.full(1, face, np.int64))

    # (ii) THE RUNWAY CENTRELINES: the ridge chains by runway at the runway
    # longitudinal cap by code; the runway ring vertices by runway
    ridge_by_ref: dict[str, list[list[int]]] = {}
    ridge_chain_of_edge: dict[int, tuple[str, int]] = {}
    for bl in pm.breaklines.values():
        if bl.kind == RIDGE_KIND:
            chs = ridge_by_ref.setdefault(bl.ref, [])
            for eid in bl.edges:
                ridge_chain_of_edge[eid] = (bl.ref, len(chs))
            chs.append(list(bl.vertices(pm)))
    ring_by_ref: dict[str, set[int]] = {}
    ref_cap: dict[str, float] = {}
    for f in pm.faces.values():
        if f.role in rw_fam and f.role in roles and face_caps[f.id] is not None:
            for cyc in (f.ring, *f.holes):
                ring_by_ref.setdefault(f.ref, set()).update(pm.ring_vertices(cyc))
                for eid in cyc:
                    hit = ridge_chain_of_edge.get(eid)
                    if hit is not None:
                        ref_cap[hit[0]] = min(face_caps[f.id][0], ref_cap.get(hit[0], face_caps[f.id][0]))
    for ref, chs in ridge_by_ref.items():
        cap = ref_cap.get(ref)
        if cap is None:
            continue
        for ch in chs:
            for u, v in zip(ch, ch[1:]):
                add(u, v, cap, CENTRELINE)
        # consecutive split chains of one runway bridged at the runway cap
        # over the straight distance (as ``runway_profile`` bridges its rows)
        if len(chs) < 2:
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
            if prev[-1] != nxt[0]:
                add(prev[-1], nxt[0], cap, CENTRELINE)
    # (i) THE TAXI CENTRELINES: every stretch edge, every polyline vertex,
    # at its stretch cap (``edge_cap``: tightened by a governed non-taxi
    # face it splits, 09-03j); a part noded inside a runway slab at the
    # runway cap (the crossing's own price)
    n_stretch_edges = 0
    stretch_caps: dict[int, np.ndarray] = {}      # stretch id -> per-segment cap
    for s in st.items:
        caps_s: list[float] = []
        for eid in s.edges:
            e = pm.edges[eid]
            fs = pm.faces_of_edge(eid)
            if fs and all(pm.faces[fid].role in rw_fam for fid in fs):
                caps = [face_caps[fid][0] for fid in fs if face_caps[fid] is not None]
                cap = min(caps) if caps else s.cap_l
            else:
                c = edge_cap(pm, law, st, eid, face_caps)
                cap = s.cap_l if c is None else c[0]
            add(e.a, e.b, cap, CENTRELINE)
            caps_s.append(cap)
            n_stretch_edges += 1
        stretch_caps[s.id] = np.array(caps_s, float)
    # (iii) THE CROSSINGS (05z b).  An ENTRY — the runway ring vertex a
    # 1202 route enters the slab at — is a point ON that route and so a
    # network node even where the planar cut left it off the stub's
    # stretch (HECA 05L/23R, measured 2026-09-05: entry 3702 at junction
    # pav81 / stub pav126 is no stretch station; as a leaf it dead-ended
    # every crossing there and cut the 05L/23R complex — 654 stations —
    # off the rest of the network)
    n_unmatched = 0
    entries: set[int] = set()
    ridge_entries: set[int] = set()
    if airport is not None and ridge_by_ref:
        xing_edges, entries, n_unmatched, ridge_entries = _runway_crossings(
            law, airport, xy, ridge_by_ref, ring_by_ref, weld_m)
        for a, b, cap, ln in xing_edges:
            add(a, b, cap, CROSSING, ln)
    # THE ATTACHMENT (05aa): every ring vertex of a route face that is no
    # station of one of ITS OWN face's centrelines — the ridge chains on a
    # runway-family face, the stretches splitting or touching every other
    # face — hops ONCE to the nearest station of the nearest such line:
    # the perpendicular distance at the face's TRANSVERSE cap, plus the
    # walk along the centreline from that station to the foot at the
    # centreline's own cap (the station is seldom AT the foot: HECA's
    # ridges are stationed every 12 m, a taxi stretch at its 1202 nodes;
    # priced at the perpendicular distance alone the band is TIGHTER
    # than the hard rows by cap × the station offset and cuts a feasible
    # hard set — measured on the shared-edge twins 2026-09-05, IIS 3 rows)
    n_faces = 0
    unattached: set[int] = set()
    for f in pm.faces.values():
        if f.role not in roles or face_caps[f.id] is None:
            continue
        n_faces += 1
        cap_t = face_caps[f.id][1]
        ring_v: list[int] = []
        seen: set[int] = set()
        for cyc in (f.ring, *f.holes):
            for v in pm.ring_vertices(cyc):
                if v not in seen:
                    seen.add(v); ring_v.append(v)
        lines: list[tuple[list[int], np.ndarray, np.ndarray]] = []
        if f.role in rw_fam:
            refs: dict[str, None] = {}
            for cyc in (f.ring, *f.holes):
                for eid in cyc:
                    hit = ridge_chain_of_edge.get(eid)
                    if hit is not None:
                        refs.setdefault(hit[0])
            if not refs and f.ref in ridge_by_ref:
                refs[f.ref] = None
            for ref in refs:
                rcap = ref_cap.get(ref)
                if rcap is None:
                    continue
                for ch in ridge_by_ref[ref]:
                    lines.append((ch, xy[np.array(ch, np.int64)],
                                  np.full(max(len(ch) - 1, 0), rcap)))
        else:
            sids: dict[int, None] = {}
            for sid in st.face_stretches.get(f.id, ()):
                sids.setdefault(sid)
            for v in ring_v:
                for sid in st.on.get(v, ()):
                    sids.setdefault(sid)
            for sid in sids:
                ch = list(st.items[sid].vertices)
                lines.append((ch, xy[np.array(ch, np.int64)], stretch_caps[sid]))
        on_line = {v for ch, _c, _k in lines for v in ch}
        if f.role in rw_fam:
            # an entry whose crossing reaches the ridge is a station of a
            # centreline inside this face (06h a): no hop on this face
            on_line |= ridge_entries
        off = np.array([v for v in ring_v if v not in on_line], np.int64)
        if off.size == 0:
            continue
        if not lines:
            unattached.update(int(v) for v in off)
            continue
        d, station, along, cap_l = _nearest_station(xy[off], lines)
        ok = station >= 0
        unattached.update(int(v) for v in off[~ok])
        if ok.any():
            src, dst = off[ok], station[ok]
            length = np.maximum(d[ok] + along[ok], min_d)
            bud = cap_t * d[ok] + cap_l[ok] * along[ok]
            A.append(np.minimum(src, dst)); B.append(np.maximum(src, dst))
            C.append(bud / length); K.append(np.full(int(ok.sum()), LATERAL, np.int8))
            LEN.append(length); FACE.append(np.full(int(ok.sum()), f.id, np.int64))
    # THE PAD CONTACTS (05ab): every near-miss frontage pair joins the pad
    # rim vertex to its apron vertex over the gap at the frontage row's
    # cap (the row the solve already holds — the walk from the pad prices
    # nothing the frontage law does not); a gap below the identity
    # spacing reads as the spacing (a zero-length edge is no edge)
    from .pads import frontage_contacts
    attached = set(np.concatenate(A + B).tolist()) if A else set()
    contact_of: dict[int, int] = {}
    for e_v, pad_v, pad_fid, dist, cap, _sf in sorted(frontage_contacts(pm, law),
                                                      key=lambda c: (c[3], c[0])):
        if pad_v in contact_of or e_v not in attached or pad_v in attached:
            continue                      # one doorway per rim vertex: the least gap
        contact_of[pad_v] = e_v
        add(pad_v, e_v, cap, CONTACT, max(dist, min_d), pad_fid)
    station = np.zeros(n_v, bool)
    for chs in ridge_by_ref.values():
        for ch in chs:
            station[ch] = True
    for s_ in st.items:
        station[list(s_.vertices)] = True
    if entries:
        station[sorted(entries)] = True
    if not A:
        z = np.zeros(0, np.int64)
        return RouteGraph(n_v, frozenset(), z, z, np.zeros(0), np.zeros(0),
                          np.zeros(0, np.int8), station,
                          {"nodes": 0, "edges": 0, "faces": n_faces,
                           "centreline": 0, "crossing": 0, "lateral": 0, "contact": 0,
                           "unattached": len(unattached),
                           "crossing_unmatched": n_unmatched}, {}, z)
    a = np.concatenate(A); b = np.concatenate(B); cap = np.concatenate(C); kind = np.concatenate(K)
    ln = np.concatenate(LEN); face = np.concatenate(FACE)
    keep = a != b
    a, b, cap, kind, ln, face = a[keep], b[keep], cap[keep], kind[keep], ln[keep], face[keep]
    plan = np.hypot(xy[a, 0] - xy[b, 0], xy[a, 1] - xy[b, 1])
    ln = np.where(np.isnan(ln), plan, ln)
    key = _pack(a, b, n_v)
    # one edge per pair: the least BUDGET (the budget the solve grants
    # along a shared edge); a centreline beats a hop of equal budget
    order = np.lexsort((kind, cap * ln, key))
    key, a, b, cap, kind, ln, face = (key[order], a[order], b[order], cap[order],
                                      kind[order], ln[order], face[order])
    _u, first = np.unique(key, return_index=True)
    a, b, cap, kind, ln, face = a[first], b[first], cap[first], kind[first], ln[first], face[first]
    keep = ln > 0.0
    a, b, cap, kind, length, face = a[keep], b[keep], cap[keep], kind[keep], ln[keep], face[keep]
    nodes = frozenset(int(v) for v in np.unique(np.concatenate([a, b])))
    stats = {"nodes": len(nodes), "edges": int(len(a)), "faces": n_faces,
             "centreline": int(np.sum(kind == CENTRELINE)),
             "stretch_edges": n_stretch_edges,
             "crossing": int(np.sum(kind == CROSSING)),
             "lateral": int(np.sum(kind == LATERAL)),
             "contact": int(np.sum(kind == CONTACT)),
             "unattached": len(unattached - nodes),
             "crossing_unmatched": n_unmatched,
             "crossing_ridge_entries": len(ridge_entries)}
    return RouteGraph(n_v, nodes, a, b, length, cap, kind, station, stats,
                      {p: e for p, e in contact_of.items() if p in nodes}, face)


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
    n = g.n
    seen: set[tuple[int, int]] = set()
    out: list[tuple[int, int, float, float]] = []
    for c0 in range(0, len(srcs), chunk):
        idx = srcs[c0:c0 + chunk]
        D, P = dijkstra(m, directed=True, indices=idx, limit=window_m,
                        return_predecessors=True)
        for i, s in enumerate(idx):
            row = D[i]
            # a vertex is ARRIVED at by its inbound id only
            cols = np.flatnonzero(np.isfinite(row))
            cols = cols[(cols == g.inbound(g.vertex(cols))) & (g.vertex(cols) != s)]
            verts = g.vertex(cols)
            skip = exclude.get(s, ()) if exclude is not None else ()
            if targets is not None or skip:
                ok = np.array([t not in skip and (targets is None or t in targets)
                               for t in verts], dtype=bool)
                cols, verts = cols[ok], verts[ok]
            if cols.size == 0:
                continue
            order = cols[np.argsort(row[cols], kind="stable")][:k]
            bud: dict[int, float] = {s: 0.0}
            pred = P[i]
            for c in order:
                c = int(c)
                # walk the predecessor chain back to a memoised id
                path: list[int] = []
                u = c
                while u not in bud:
                    path.append(u)
                    u = int(pred[u])
                acc = bud[u]
                for v in reversed(path):
                    p, q = int(g.vertex(int(pred[v]))), int(g.vertex(v))
                    acc += wb[(p, q) if p < q else (q, p)]
                    bud[v] = acc
                t = int(g.vertex(c))
                key = (s, t) if s < t else (t, s)
                if key in seen:
                    continue
                seen.add(key)
                out.append((key[0], key[1], float(row[c]), bud[c]))
    return out


def route_pairs(g: RouteGraph, groups: _t.Sequence[_t.Sequence[int]],
                chunk: int = 128) -> dict[tuple[int, int], tuple[float, float]]:
    """THE WITHIN-SHAPE ROUTE PRICING (RULINGS 2026-09-05ab, spec §9):
    for every distinct pair inside each group (a face ring) the ROUTE
    distance — a's hop + the centreline path + b's hop, the shortest by
    length — and the pair's BUDGET: the least ``Σ cap·len`` over EVERY
    route joining them (the reach bands' own metric, :func:`reach`; each
    route bounds the pair, so their least does — and it is the path
    budget where one route exists), as ``(a, b) -> (dist, budget)`` with
    ``a < b``.  A pair no route joins is ABSENT; a vertex that is no node
    pairs with nothing.  Two Dijkstras per source over the whole graph
    (no window: a route may be many times its chord — HECA pav101:
    3,349 m for a 1,463 m chord), chunked so the dense rows stay small;
    measured HECA 2026-09-05: 7,972 sources, 4.4 s (a per-path budget
    walk by pointer jumping cost 24 s and was replaced)."""
    members: dict[int, list[int]] = {}
    grp = [sorted({v for v in gr if v in g.nodes}) for gr in groups]
    for k, gr in enumerate(grp):
        for v in gr:
            members.setdefault(v, []).append(k)
    srcs = sorted(members)
    out: dict[tuple[int, int], tuple[float, float]] = {}
    if not srcs:
        return out
    m = g.csr("length")
    wb = g.csr("budget")
    for c0 in range(0, len(srcs), chunk):
        idx = srcs[c0:c0 + chunk]
        D = dijkstra(m, directed=True, indices=idx)
        B = dijkstra(wb, directed=True, indices=idx)
        for i, s in enumerate(idx):
            for k in members[s]:
                tg = [t for t in grp[k] if t > s]
                if not tg:
                    continue
                cols = g.inbound(np.array(tg, np.int64))
                d, b = D[i, cols], B[i, cols]
                for t, dv, bv in zip(tg, d, b):
                    if np.isfinite(dv) and dv > 0.0:
                        out[(s, t)] = (float(dv), float(bv))
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
    D = dijkstra(m, directed=True, indices=idx)
    z = np.array([pins[v] for v in idx], dtype=float)[:, None]
    verts = np.arange(g.n)
    Din = D[:, g.inbound(verts)]
    hi = np.min(z + Din, axis=0)
    lo = np.max(z - Din, axis=0)
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
    D, P = dijkstra(m, directed=True, indices=[a], return_predecessors=True,
                    limit=np.inf if max_len is None else max_len)
    tgt = g.inbound(b)
    if not np.isfinite(D[0][tgt]):
        return None
    wb = g.edge_budget()
    ids = [tgt]
    while ids[-1] != a:
        ids.append(int(P[0][ids[-1]]))
    ids.reverse()
    path = [int(g.vertex(i)) for i in ids]
    bud = sum(wb[(u, v) if u < v else (v, u)] for u, v in zip(path, path[1:]))
    return float(D[0][tgt]), float(bud), path
