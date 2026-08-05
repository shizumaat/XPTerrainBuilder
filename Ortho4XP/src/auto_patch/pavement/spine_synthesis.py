"""Pavement-based taxi-spine synthesis — a WELDED graph of straight lanes
and standard arcs, like the centerline network on an airport diagram.

Design rules (user 2026-07-01, refined against the approved
``SPJC_curved_spine.kml`` target):

* **Navigability invariant.** An aircraft starting anywhere on the spine can
  reach every part of it rolling along spine edges — no right-angle turns,
  wheels never leaving the line.  Everything is straights + tangent arcs,
  and every way ends on a node shared with its neighbours (floating ends =
  defects, gated by the QA tool).
* **Lanes take the straight path.**  A taxiway centerline is the maximal
  straight chord down the middle of its pavement; junctions and widenings
  never deflect it.  Holes identify branches (and widths).
* **One STANDARD arc radius per taxiway size** (ICAO code letter; measured
  half-width as fallback).  Turn arcs everywhere use that radius — a sharper
  turn just makes the arc LONGER, not a different size.  Two parallels plus
  a connector form an "H": the connector stays a straight cross-piece and
  the four 90° corners get four EQUAL arcs (arc–straight–arc movements, not
  S-diagonals).
* **Runway contacts**: square-in keeps a single edge node.  A high-speed
  DIAGONAL keeps its straight (shallow) connection and adds one long
  standard-radius arc for the sharp (~135°) turn, welded to the diagonal
  and landing on the runway edge.
* **Buildings**: pads are subtracted before skeletonizing (a spine never
  enters one); small buildings get a lead-in stub welded to the nearest
  lane; larger buildings/terminals get a perimeter ring at a setback,
  pieces welded to the network or dropped (no floaters).

Construction is from the pavement footprint ONLY.  The apt.dat route data
is consulted ONLY to label a lane with its ICAO size letter (an attribute
lookup — geometry never comes from it); without routes the size falls back
to the measured half-width.
"""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass

import numpy as np
import shapely
from shapely.geometry import LineString, Point

# ── standards constants ──────────────────────────────────────────────────────
# Centerline turn radius (m) at a 90° turn by ICAO code letter — the values
# the user verified on Google Earth (taxi_route_fillets.py, 2026-06-30).
# The SAME radius serves every turn angle; only the arc length changes.
R90_BY_SIZE = {"A": 12.0, "B": 16.0, "C": 22.0, "D": 30.0, "E": 36.0,
               "F": 45.0, "": 22.0}
# Measured lane half-width → size letter fallback (no route data).
_SIZE_BY_HALFWIDTH = ((4.0, "A"), (5.5, "B"), (8.0, "C"), (10.5, "D"),
                      (13.5, "E"), (99.0, "F"))

_TURN_MIN_DEG = 25.0      # flatter meetings are through-continuations
_TURN_MAX_DEG = 155.0     # sharper pairs are fold-backs, no direct movement
_THROUGH_MAX_DEG = 40.0   # body-axis pairs this collinear form one through
_MIN_ARC_FIT = 0.25       # arc may shrink to this × standard before we skip
#                           (tight island-tip corners are pavement-limited —
#                            a smaller arc there is correct, not a defect)
_CHORD_CLEAR_M = 2.0      # a straight chord needs this edge clearance
_FAIR_SIMPLIFY_M = 1.2
_NODE_KEY_M = 0.05        # node weld quantum
_DIAG_MIN_DEG = 20.0      # runway diagonal band
_DIAG_MAX_DEG = 65.0

_OPEN_HALFWIDTH_M = 38.0  # lanes with more clearance than this are open-
#                            pavement medial, not taxiway spine — dropped
_SVC_HALFWIDTH_M = 5.5    # ...and lanes NARROWER than this are service roads,
#                            not aircraft taxiways (target keeps none)

SMALL_BUILDING_M2 = 2000.0
TERMINAL_SETBACK_M = 100.0
_STUB_MAX_REACH_M = 80.0
_RING_MIN_ARC_M = 30.0
_RING_LANE_CLEAR_M = 15.0
_RING_WELD_REACH_M = 25.0


@dataclass
class SpineWay:
    line: LineString
    kind: str          # lane | arc | rwy_turn | building_stub | building_ring
    size: str = ""     # ICAO code letter
    halfwidth: float = 0.0


# ── small geometry helpers ───────────────────────────────────────────────────

def _unit(dx: float, dy: float):
    n = math.hypot(dx, dy)
    return (dx / n, dy / n) if n > 1e-9 else (0.0, 0.0)


def _angle_deg(u, v) -> float:
    d = max(-1.0, min(1.0, u[0] * v[0] + u[1] * v[1]))
    return math.degrees(math.acos(d))


def _arc_pts(center, r, a0, a1, ccw: bool, step_m: float = 4.0):
    if ccw:
        while a1 < a0:
            a1 += 2 * math.pi
    else:
        while a1 > a0:
            a1 -= 2 * math.pi
    n = max(3, int(abs(a1 - a0) * r / step_m) + 1)
    ts = np.linspace(a0, a1, n)
    return [(center[0] + r * math.cos(t), center[1] + r * math.sin(t))
            for t in ts]


def _fillet(P, u_in, u_out, r, gamma_max=_TURN_MAX_DEG,
            gamma_min=_TURN_MIN_DEG):
    """Tangent arc at corner ``P``: arrive along ``u_in``, depart along
    ``u_out``.  Returns (arc_coords, tangent_len) or (None, 0)."""
    gamma = math.acos(max(-1.0, min(1.0,
        u_in[0] * u_out[0] + u_in[1] * u_out[1])))
    if gamma < math.radians(gamma_min) \
            or gamma > math.radians(gamma_max):
        return None, 0.0
    t = r * math.tan(gamma / 2.0)
    ta = (P[0] - u_in[0] * t, P[1] - u_in[1] * t)
    tb = (P[0] + u_out[0] * t, P[1] + u_out[1] * t)
    cross = u_in[0] * u_out[1] - u_in[1] * u_out[0]
    sgn = 1.0 if cross > 0 else -1.0
    n_in = (-u_in[1] * sgn, u_in[0] * sgn)
    c = (ta[0] + n_in[0] * r, ta[1] + n_in[1] * r)
    a0 = math.atan2(ta[1] - c[1], ta[0] - c[0])
    a1 = math.atan2(tb[1] - c[1], tb[0] - c[0])
    return _arc_pts(c, r, a0, a1, ccw=(sgn > 0)), t


# ── the welded spine graph ───────────────────────────────────────────────────

class _Graph:
    """Nodes are first-class; every edge's polyline STARTS and ENDS exactly
    at its nodes' positions.  All geometry edits go through node moves and
    edge splits, so the network can never come apart."""

    def __init__(self):
        self.nodes: list[np.ndarray] = []
        self._key2node: dict = {}
        # edge: dict(a, b, cs Nx2, kind, size, w, alive)
        self.edges: list[dict] = []
        # nodes where through-path pairing is forbidden (regime changes)
        self.no_through: set = set()

    def _key(self, xy):
        return (round(xy[0] / _NODE_KEY_M), round(xy[1] / _NODE_KEY_M))

    def add_node(self, xy) -> int:
        k = self._key(xy)
        if k in self._key2node:
            return self._key2node[k]
        self.nodes.append(np.asarray(xy, dtype=float))
        self._key2node[k] = len(self.nodes) - 1
        return len(self.nodes) - 1

    def add_edge(self, cs, kind, size="", w=0.0) -> int:
        cs = np.asarray(cs, dtype=float)
        a = self.add_node(cs[0])
        b = self.add_node(cs[-1])
        cs[0], cs[-1] = self.nodes[a], self.nodes[b]
        self.edges.append(dict(a=a, b=b, cs=cs, kind=kind, size=size,
                               w=w, alive=True))
        return len(self.edges) - 1

    def incident(self) -> dict:
        inc = defaultdict(list)
        for ei, e in enumerate(self.edges):
            if not e["alive"]:
                continue
            inc[e["a"]].append((ei, True))
            inc[e["b"]].append((ei, False))
        return inc

    def move_node(self, ni: int, xy):
        """Relocate a node; every incident edge's end vertex follows.  The
        key map MUST move with it — otherwise a later add_node at the new
        position mints a duplicate node and silently forks the graph."""
        old_k = self._key(self.nodes[ni])
        if self._key2node.get(old_k) == ni:
            del self._key2node[old_k]
        self.nodes[ni] = np.asarray(xy, dtype=float)
        # first owner keeps a contested key (rare exact-coincidence case)
        self._key2node.setdefault(self._key(xy), ni)
        for e in self.edges:
            if not e["alive"]:
                continue
            if e["a"] == ni:
                e["cs"][0] = self.nodes[ni]
            if e["b"] == ni:
                e["cs"][-1] = self.nodes[ni]

    def edge_dir_at(self, ei: int, at_a: bool, back_m: float = 20.0):
        """Unit direction ARRIVING at the given end along the edge."""
        cs = self.edges[ei]["cs"]
        if at_a:
            cs = cs[::-1]
        acc, i = 0.0, len(cs) - 1
        while i > 0 and acc < back_m:
            acc += float(np.hypot(*(cs[i] - cs[i - 1])))
            i -= 1
        v = cs[-1] - cs[i]
        return _unit(float(v[0]), float(v[1]))

    def split_edge(self, ei: int, s: float) -> int:
        """Split edge ``ei`` at arc length ``s``; returns the new mid node.
        The two halves keep the edge's kind/size."""
        e = self.edges[ei]
        ln = LineString(e["cs"])
        if s <= 1.0:
            return e["a"]                 # reuse the end node — no sliver
        if s >= ln.length - 1.0:
            return e["b"]
        p = ln.interpolate(s)
        # build vertex lists
        first, second = [], []
        acc = 0.0
        cs = e["cs"]
        first.append(cs[0])
        done = False
        for k in range(1, len(cs)):
            d = float(np.hypot(*(cs[k] - cs[k - 1])))
            if not done and acc + d >= s:
                first.append([p.x, p.y])
                second.append([p.x, p.y])
                second.extend(cs[k:])
                done = True
                break
            acc += d
            first.append(cs[k])
        if not done:
            return e["b"]
        mid = self.add_node([p.x, p.y])
        e["alive"] = False
        self.add_edge(np.asarray(first), e["kind"], e["size"], e["w"])
        self.add_edge(np.asarray(second), e["kind"], e["size"], e["w"])
        return mid

    def consolidate(self):
        """Merge degree-2 nodes where two same-kind, same-size edges continue
        near-collinearly — undoes split fragmentation so the emitted ways are
        clean long lanes.  Genuine corners (real turns) keep their node."""
        changed = True
        while changed:
            changed = False
            for ni, ends in self.incident().items():
                live = [(ei, aa) for ei, aa in ends if self.edges[ei]["alive"]]
                if len(live) != 2:
                    continue
                (ea, aa), (eb, ab) = live
                if ea == eb:
                    continue
                A, B = self.edges[ea], self.edges[eb]
                if A["kind"] != B["kind"] or A["size"] != B["size"]:
                    continue
                u = self.edge_dir_at(ea, aa)
                v = self.edge_dir_at(eb, ab)
                if _angle_deg(u, (-v[0], -v[1])) > 30.0:
                    continue
                a_cs = A["cs"][::-1] if aa else A["cs"]     # node LAST
                b_cs = B["cs"] if ab else B["cs"][::-1]     # node FIRST
                merged = np.vstack([a_cs, b_cs[1:]])
                A["alive"] = False
                B["alive"] = False
                self.add_edge(merged, A["kind"], A["size"],
                              max(A["w"], B["w"]))
                changed = True
                break

    def ways(self) -> list[SpineWay]:
        out = []
        for e in self.edges:
            if not e["alive"]:
                continue
            ln = LineString(e["cs"])
            if ln.length < 0.5:
                continue
            out.append(SpineWay(ln, e["kind"], e["size"], e["w"]))
        return out


# ── through-path assembly + straightening (graph-preserving) ─────────────────

# ── size attribution ─────────────────────────────────────────────────────────

# ── junction arcs (welded) ───────────────────────────────────────────────────

def _radius_for(size: str) -> float:
    return R90_BY_SIZE.get(size or "", R90_BY_SIZE[""])


def _add_junction_arcs(g: _Graph, pav_ok, runway_union=None,
                       r_start_for=None, gamma_max=None):
    """At every node, STANDARD arcs for every branch pair with a real turn —
    all arcs of one junction share ONE radius (user: where arcs come
    together they are the same size, mirrored), so symmetric pairs land on
    shared tangent nodes.  Tangent points split the branch edges (endpoint
    reuse welds coincident tangents), keeping the graph coherent.  An H
    junction is a straight rung + four EQUAL quarter-circles.

    ``r_start_for(P, r_std)`` (optional) sets the LARGEST radius to try at
    a node — wide-open junction crossings take the biggest mirrored arcs
    that fit (v8 target evidence), corridor junctions stay standard.
    ``gamma_max`` (optional) caps the pair turn angle below the module
    default — the route model uses ~120°: at standard radius a sharper
    pair sweeps a long arc across the junction interior (v13 user
    review, the way-276 bulge), and those movements are runway-turn
    territory, not ordinary junction fillets."""
    rwy_b = runway_union.boundary \
        if runway_union is not None and not runway_union.is_empty else None
    node_ids = list(g.incident().keys())
    for ni in node_ids:
        P = g.nodes[ni]
        if rwy_b is not None and rwy_b.distance(Point(tuple(P))) < 3.0:
            continue        # square runway contact: straight line, no arcs

        def _ends():
            return [(ei, at_a) for (ei, at_a) in g.incident().get(ni, [])
                    if g.edges[ei]["alive"]
                    and g.edges[ei]["kind"] == "lane"]

        ends = _ends()
        if len(ends) < 2:
            continue
        # ── dry-run: per-pair max fitting radius, then the junction's
        #    COMMON radius = the smallest of them (mirrored equal arcs)
        pair_list = []
        r_common = None
        for x in range(len(ends)):
            for y in range(x + 1, len(ends)):
                (ea, aa), (eb, ab) = ends[x], ends[y]
                if ea == eb:
                    continue
                u = g.edge_dir_at(ea, aa)
                v = g.edge_dir_at(eb, ab)
                u_out = (-v[0], -v[1])
                gamma = _angle_deg(u, u_out)
                if gamma < _TURN_MIN_DEG or gamma > (
                        gamma_max if gamma_max is not None
                        else _TURN_MAX_DEG):
                    continue
                size = min(g.edges[ea]["size"] or "C",
                           g.edges[eb]["size"] or "C")
                r_std = _radius_for(size)
                len_a = LineString(g.edges[ea]["cs"]).length
                len_b = LineString(g.edges[eb]["cs"]).length
                r_fit = None
                r = r_std if r_start_for is None \
                    else max(r_std, float(r_start_for(P, r_std)))
                while r >= _MIN_ARC_FIT * r_std:
                    arc, t = _fillet(tuple(P), u, u_out, r)
                    if arc is None:
                        break
                    # half-length budget: a branch may host arcs at BOTH
                    # of its ends (H rung), so each side gets half.  In
                    # walk mode (v8: planarize fragments are short) the
                    # tangent may continue across collinear fragments.
                    if r_start_for is not None:
                        fits = (_walk_locate(g, ea, aa, t) is not None
                                and _walk_locate(g, eb, ab, t) is not None)
                    else:
                        fits = t <= 0.55 * len_a and t <= 0.55 * len_b
                    if fits and pav_ok(LineString(arc)):
                        r_fit = r
                        break
                    r *= 0.85
                if r_fit is None:
                    continue
                pair_list.append((u, u_out, size))
                r_common = r_fit if r_common is None else min(r_common, r_fit)
        if not pair_list or r_common is None:
            continue
        # ── place every pair at the common radius
        for (u, u_out, size) in pair_list:
            ends_now = _ends()
            # re-resolve the two branches by direction match
            best_a = best_b = None
            for (ei, at_a) in ends_now:
                d = g.edge_dir_at(ei, at_a)
                if _angle_deg(d, u) < 10.0 and best_a is None:
                    best_a = (ei, at_a)
                elif _angle_deg(d, (-u_out[0], -u_out[1])) < 10.0 \
                        and best_b is None:
                    best_b = (ei, at_a)
            if best_a is None or best_b is None or best_a[0] == best_b[0]:
                continue
            arc, t = _fillet(tuple(P), u, u_out, r_common)
            if arc is None:
                continue
            ln_arc = LineString(arc)
            if not pav_ok(ln_arc):
                continue
            (ea, aa), (eb, ab) = best_a, best_b
            len_a = LineString(g.edges[ea]["cs"]).length
            len_b = LineString(g.edges[eb]["cs"]).length
            w_pair = g.edges[ea]["w"]
            if r_start_for is not None:
                loc_a = _walk_locate(g, ea, aa, t)
                loc_b = _walk_locate(g, eb, ab, t)
                if loc_a is None or loc_b is None:
                    continue
                na = g.split_edge(loc_a[0], loc_a[1])
                nb = g.split_edge(loc_b[0], loc_b[1])
            else:
                if t > len_a + 1.0 or t > len_b + 1.0:
                    continue
                na = g.split_edge(ea, t if aa else len_a - t)
                nb = g.split_edge(eb, t if ab else len_b - t)
            cs = np.asarray(arc)
            cs[0] = g.nodes[na]
            cs[-1] = g.nodes[nb]
            g.add_edge(cs, "arc", size, w_pair)
    return


def _walk_locate(g: _Graph, ei: int, from_a: bool, t: float, max_hops=6):
    """Locate arc length ``t`` measured from one end of edge ``ei``, walking
    across near-collinear lane continuations when ``t`` overruns the edge —
    a big sharp-turn arc's tangent point often lies beyond the tip fragment
    that junction-arc splits left behind.  Returns (edge, s) or None."""
    for _hop in range(max_hops):
        e = g.edges[ei]
        L = LineString(e["cs"]).length
        if t <= L - 1.0:
            return ei, (t if from_a else L - t)
        far = e["b"] if from_a else e["a"]
        u = g.edge_dir_at(ei, at_a=not from_a)     # arriving at the far end
        nxt = None
        for (ej, aj) in g.incident().get(far, []):
            if ej == ei or not g.edges[ej]["alive"] \
                    or g.edges[ej]["kind"] != "lane":
                continue
            v = g.edge_dir_at(ej, at_a=aj)
            if _angle_deg(u, (-v[0], -v[1])) <= 30.0:
                nxt = (ej, aj)
                break
        if nxt is None:
            return None
        t -= L
        ei, from_a = nxt
    return None


def _add_runway_turns(g: _Graph, runway_union, pav_eff):
    """Runway-contact arcs at DIAGONAL (rapid-exit style) lane tips.

    Sharp side: one long STANDARD-radius arc (the ~135° turn), tangent to
    the diagonal, landing on the runway edge.  Shallow side: the rare
    gentle LARGE-radius blend into the runway (550 m down to 120 m, first
    that fits).  Both weld into the graph; tangent points may lie beyond
    the tip fragment, so they walk across collinear continuations.  The
    live tip edge is re-resolved before every placement because a previous
    split may have retired it."""
    if runway_union is None or runway_union.is_empty:
        return
    allow_rwy = shapely.buffer(pav_eff, 1.0)
    edge_b = runway_union.boundary
    n_edges0 = len(g.edges)
    for ei in range(n_edges0):
        e = g.edges[ei]
        if not e["alive"] or e["kind"] != "lane":
            continue
        for at_a in (True, False):
            tip = e["cs"][0] if at_a else e["cs"][-1]
            P = Point(tuple(tip))
            if edge_b.distance(P) > 1.5:
                continue
            tip_node = e["a"] if at_a else e["b"]
            u_in = g.edge_dir_at(ei, not at_a)
            if at_a:
                u_in = (-u_in[0], -u_in[1])
            s = edge_b.project(P)
            q0 = edge_b.interpolate(max(0.0, s - 10.0))
            q1 = edge_b.interpolate(min(edge_b.length, s + 10.0))
            e_dir = _unit(q1.x - q0.x, q1.y - q0.y)
            if e_dir == (0.0, 0.0):
                continue
            ang = _angle_deg(u_in, e_dir)
            ang = min(ang, 180.0 - ang)
            if not (_DIAG_MIN_DEG <= ang <= _DIAG_MAX_DEG):
                continue
            # a lane that CROSSES the runway (continuation on the opposite
            # side) is a crossing, not a rapid exit — no diagonal arcs
            probe = LineString([tuple(tip),
                                (tip[0] + u_in[0] * 400.0,
                                 tip[1] + u_in[1] * 400.0)])
            exit_pt = None
            inter = probe.intersection(edge_b)
            cand = [q for q in getattr(inter, "geoms", [inter])
                    if q.geom_type == "Point"
                    and q.distance(P) > 5.0]
            if cand:
                exit_pt = min(cand, key=lambda q: q.distance(P))
            if exit_pt is not None:
                near_far = any(
                    o["alive"] and o["kind"] == "lane"
                    and LineString(o["cs"]).distance(exit_pt) < 35.0
                    for o in g.edges)
                if near_far:
                    continue
            r_std = _radius_for(e["size"])

            def _live_tip_edge():
                for (ej, aj) in g.incident().get(tip_node, []):
                    if g.edges[ej]["alive"] \
                            and g.edges[ej]["kind"] == "lane":
                        return ej, aj
                return None, None

            for e_sgn in (1.0, -1.0):
                u_out = (e_dir[0] * e_sgn, e_dir[1] * e_sgn)
                cei, cat_a = _live_tip_edge()
                if cei is None:
                    break
                if _angle_deg(u_in, u_out) < 95.0:
                    # SHALLOW side: the gentle large-radius blend mostly
                    # lives ON the runway (the paint eases from the runway
                    # centerline onto the diagonal), so at our domain edge
                    # the arc is CLIPPED at the runway boundary: keep the
                    # taxi-side piece — a gentle ease-off from the diagonal
                    # ending on the edge.
                    for r_blend in (550.0, 400.0, 275.0, 180.0, 120.0):
                        arc_b, t_b = _fillet(tuple(tip), u_in, u_out,
                                             r_blend, gamma_max=70.0,
                                             gamma_min=10.0)
                        if arc_b is None:
                            break
                        loc_b = _walk_locate(g, cei, cat_a, t_b)
                        if loc_b is None:
                            continue
                        # smooth prefix of the arc while it stays on
                        # pavement (clip artifacts would kink the line)
                        keep = [arc_b[0]]
                        for q in arc_b[1:]:
                            if not allow_rwy.contains(Point(q)):
                                break
                            keep.append(q)
                        if len(keep) < 3:
                            continue
                        piece = LineString(keep)
                        if piece.length < 25.0:
                            continue
                        nb2 = g.split_edge(loc_b[0], loc_b[1])
                        cs_b = np.asarray(piece.coords)
                        cs_b[0] = g.nodes[nb2]
                        g.add_edge(cs_b, "blend", e["size"], e["w"])
                        break
                    continue
                # SHARP side: long standard-radius turn arc.  A hook at a
                # fraction of the standard radius is paint that does not
                # exist — skip rather than shrink below half standard.
                r, arc, t, loc = r_std, None, 0.0, None
                while r >= 0.5 * r_std:
                    arc, t = _fillet(tuple(tip), u_in, u_out, r,
                                     gamma_max=162.0)
                    if arc is not None:
                        loc = _walk_locate(g, cei, cat_a, t)
                        if loc is not None \
                                and allow_rwy.contains(LineString(arc)):
                            break
                    arc = None
                    r *= 0.75
                if arc is None or loc is None:
                    continue
                na = g.split_edge(loc[0], loc[1])
                cs = np.asarray(arc)
                cs[0] = g.nodes[na]
                g.add_edge(cs, "rwy_turn", e["size"], e["w"])
            if not e["alive"]:
                break
    return


# ── buildings ────────────────────────────────────────────────────────────────

# ── main ─────────────────────────────────────────────────────────────────────

