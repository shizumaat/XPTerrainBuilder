"""THE LAW-GRAPH BUDGET ORACLE — route-metric distance and hard-anchor
envelope on the graph PHASE A ACTUALLY PROJECTS ON (seed-fix round §3 +
the RECONCILIATION clause of ``docs/specs/seed-fix-round-spec.md``).

WHY IT EXISTS.  Two rounds price the same thing.  The seed-fix round needs
"how much grade budget lies between this apron feeder and that hard runway
anchor" so a contact seat cannot be projected 12.85 m away from a runway
truth it is 0.19 m of budget from; the route-distance seat-coupling round
needs the same distance for its coupling weights.  Deriving it twice is
exactly what ``single-pass-principle`` forbids, and deriving it
DIFFERENTLY is how a polytope comes to be priced on a metric the
projection does not enforce — the defect family both rounds are fixing.
So the metric is built ONCE, here, and both rounds consume it.

WHICH GRAPH.  ``_solve_spine_profile``'s final exact projection is

    feasibility_project(elev, [{"edges": s_edges}], anchors)

with ``s_edges`` the de-duplicated ``spine_adj`` and ``anchors`` the
``base_hard`` spine nodes.  That is a pure cap-Lipschitz difference system
``|z_i − z_j| ≤ w_ij`` with the anchors pinned, so its feasible set at a
node is the classical two-sided envelope

    U(i) = min over anchors a ( v_a + d(a, i) )
    L(i) = max over anchors a ( v_a − d(a, i) )

where ``d`` is the shortest path under the per-edge BUDGETS ``w``.  This
module computes exactly that, on exactly that graph:

  * ALL spine edges, service ones included.  The reach BAND
    (``building_feasibility.spine_value_fields``) deliberately excludes
    service pairs because reachability is a LAW question about taxi
    routes; this oracle answers a different question — what the phase-A
    projection will enforce — and the projection sweeps every spine edge.
    Two metrics, two questions, and neither may be silently substituted
    for the other.
  * The anchor VALUES are the solve's own ``elev`` at those nodes, in the
    solve's (crowned) space — the space the projection compares in.  The
    band's de-crowned space is a different frame and is not used here.

The envelope is the EXACT intersection of the per-anchor cap constraints
``|L_i − v_a| ≤ d(a, i)``: the anchor values are fixed, so each such
constraint is an interval on ``L_i`` and the intersection over all
in-reach anchors is ``[L(i), U(i)]``.  A consumer that wants "cap
constraints anchor↔feeder for every hard anchor within reach" therefore
gets them, in full, as one box — two Dijkstras for the whole airport
instead of one per (feeder, anchor) pair.
"""
from __future__ import annotations

import heapq
from typing import Dict, Iterable, Optional, Tuple

__all__ = ["AnchorEnvelope", "build_anchor_envelope"]

_INF = float("inf")


class AnchorEnvelope:
    """``[floor, ceiling]`` per spine node from the hard anchors, with the
    WITNESS anchor and its route budget on each side.

    ``box(node)`` returns ``(floor, ceiling)`` or ``None`` for a node the
    anchors do not reach (no constraint — never a silent clamp).
    ``violation(node, value)`` returns ``None`` when ``value`` sits inside
    the envelope, else the signed excess with the witness that binds — the
    attribution a consumer reports instead of adjusting quietly.
    """

    __slots__ = ("floor", "ceiling", "floor_witness", "ceil_witness",
                 "floor_route_m", "ceil_route_m", "anchor_count",
                 "node_count")

    def __init__(self, floor, ceiling, floor_witness, ceil_witness,
                 floor_route_m, ceil_route_m, anchor_count):
        self.floor = floor
        self.ceiling = ceiling
        self.floor_witness = floor_witness
        self.ceil_witness = ceil_witness
        self.floor_route_m = floor_route_m
        self.ceil_route_m = ceil_route_m
        self.anchor_count = int(anchor_count)
        self.node_count = len(ceiling)

    def box(self, node: int) -> Optional[Tuple[float, float]]:
        lo = self.floor.get(node)
        hi = self.ceiling.get(node)
        if lo is None or hi is None:
            return None
        return (lo, hi)

    def violation(self, node: int, value: float,
                  tol: float = 0.0) -> Optional[dict]:
        """``None`` when ``value`` is within the envelope at ``node``;
        otherwise the binding side, its witness anchor, that anchor's
        value, the route budget between them and the excess in metres."""
        box = self.box(node)
        if box is None:
            return None
        lo, hi = box
        if value > hi + tol:
            return {"side": "ceiling", "excess_m": float(value - hi),
                    "bound": float(hi),
                    "witness": self.ceil_witness.get(node),
                    "route_budget_m": float(self.ceil_route_m.get(node, 0.0))}
        if value < lo - tol:
            return {"side": "floor", "excess_m": float(lo - value),
                    "bound": float(lo),
                    "witness": self.floor_witness.get(node),
                    "route_budget_m": float(self.floor_route_m.get(node, 0.0))}
        return None


def build_anchor_envelope(spine_adj: Dict[int, Iterable],
                          anchor_values: Dict[int, float],
                          *, horizon_m: Optional[float] = None,
                          ) -> Optional[AnchorEnvelope]:
    """Two value-seeded multi-source Dijkstras over ``spine_adj`` — ONE
    pass per side, the same commutation ``spine_value_fields`` uses (the
    per-anchor passes were only ever consumed as a min / max over
    anchors).

    ``spine_adj`` — ``{i: [(j, budget), ...]}``, the projection's own
    adjacency.  ``anchor_values`` — ``{node: pinned_elev}``.
    ``horizon_m`` — optional cap on the ROUTE BUDGET travelled; beyond it a
    node simply has no bound from that side (the envelope is a bound, and
    a missing bound is honest).

    Returns ``None`` when there is nothing to build (no anchors on the
    graph), so a caller can branch once instead of guarding every read.
    """
    if not spine_adj or not anchor_values:
        return None
    seeds = {int(k): float(v) for k, v in anchor_values.items()
             if int(k) in spine_adj}
    if not seeds:
        return None

    def _field(sign):
        best: Dict[int, float] = {}
        witness: Dict[int, int] = {}
        route: Dict[int, float] = {}
        pq = [((value if sign > 0 else -value), 0.0, value, node, node)
              for (node, value) in seeds.items()]
        heapq.heapify(pq)
        while pq:
            _key, dist, value, src, u = heapq.heappop(pq)
            if u in best:
                continue
            best[u] = (value + dist) if sign > 0 else (value - dist)
            witness[u] = src
            route[u] = dist
            for (v, budget) in spine_adj.get(u, ()):
                if v in best:
                    continue
                nd = dist + float(budget)
                if horizon_m is not None and nd > horizon_m:
                    continue
                heapq.heappush(
                    pq, (((value + nd) if sign > 0 else -(value - nd)),
                         nd, value, src, v))
        return best, witness, route

    ceiling, ceil_witness, ceil_route = _field(+1)
    floor, floor_witness, floor_route = _field(-1)
    return AnchorEnvelope(floor, ceiling, floor_witness, ceil_witness,
                          floor_route, ceil_route, len(seeds))
