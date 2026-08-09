"""R-a — LATERAL NODES ARE ROUTE-TRANSPARENT (lead ruling 2026-08-08).

THE KNOWN-ANSWER TWIN the ruling asks for: *a lateral row across a
corridor does NOT change any route length between anchors.*

The owner's 2026-07-30 law is that feasibility/reach follows TAXI
CENTERLINES only.  A cross-section foot is a sample of the TRANSVERSE
law, not a route, so it may bind a within-shape pair and it may never
appear in ``UnifiedGraph.spine_adj`` — the route metric the reach band
prices its budgets on.

WHY THE FIXTURE LOOKS LIKE THIS.  ``grade_graph.SPINE_PERP_TOL_M`` is
1.0 m, so the feet that get strung are exactly the ones on an edge the
axis runs ALONG — which is the wide-corridor class the lateral pass
exists to serve (CYXY apron ``shapeID 115``).  Put a second pavement's
near edge on the other side of that axis and the arc-ordered walk
interleaves left and right feet into CROSS EDGES: at HECA that shortened
routes until the reach band inverted and the build refused (1,655 of
10,220 band-covered nodes, 49.400 m of anchor spread over a 47.723 m
route budget).  The fixture below is that corridor, minimally.

Every test asserts against the SAME layout before the row is inserted —
a known answer measured, never a constant typed in.
"""
from __future__ import annotations

import heapq
import os
import sys

import pytest
from shapely.geometry import LineString, Polygon

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from auto_patch import grade_graph as GG                     # noqa: E402
from auto_patch import lateral_spine_nodes as lsn            # noqa: E402
from auto_patch.config import TAXI_MAX_GRADE                 # noqa: E402
from auto_patch.layout import ROLE_APRON                     # noqa: E402

_LEN = 480.0            # corridor length (the CYXY extent, near enough)
_STEP = 12.0            # config.SPINE_STEP_M — the station step R-c arms
_GAP = 0.6              # the second pavement's near edge, INSIDE the 1.0 m
#                         spine tolerance: that is what makes a cross edge


class _Shape:
    def __init__(self, polygon, role=ROLE_APRON):
        self.polygon = polygon
        self.role = role
        self.node_altitudes = None
        self.ref = "T"


class _CL:
    def __init__(self, line, is_service=False):
        self.line = line
        self.is_service = is_service


class _Layout:
    def __init__(self, shapes, centerlines):
        self.shapes = shapes
        self.apt_taxi_centerlines = centerlines


def _corridor_layout():
    """Two pavements flanking ONE axis at x=0.

    ``right`` runs x in [0, 20] — its near edge IS the axis (distance 0).
    ``left`` runs x in [-20, -0.6] — its near edge is 0.6 m off, still
    inside ``SPINE_PERP_TOL_M``.  Both are the CYXY shape: a long thin
    pavement whose far edge is a single segment.

    ``left`` is deliberately SHORTER (y in [5, 475]) so no two corners
    share an arc position.  ``_build_global_spine`` sorts its on-line
    nodes by arc alone, so an exact tie is resolved by candidate order —
    which node interning shifts when a ring gains vertices.  That is a
    pre-existing property of the walk, not an R-a effect, and a fixture
    that trips it would measure the tie-break instead of the ruling.
    """
    right = _Shape(Polygon([(0.0, 0.0), (20.0, 0.0),
                            (20.0, _LEN), (0.0, _LEN)]))
    left = _Shape(Polygon([(-20.0, 5.0), (-_GAP, 5.0),
                           (-_GAP, _LEN - 5.0), (-20.0, _LEN - 5.0)]))
    axis = _CL(LineString([(0.0, 0.0), (0.0, _LEN)]))
    return _Layout([right, left], [axis])


def _ctx(layout):
    cl = layout.apt_taxi_centerlines[0]
    return GG.GradeContext(centerlines=[
        GG.Centerline(pts=list(cl.line.coords),
                      seg_caps=[TAXI_MAX_GRADE] * (len(cl.line.coords) - 1),
                      is_service=cl.is_service)])


def _nodes_of(layout):
    """``{(x, y) rounded: idx}`` over every ring vertex — the hermetic
    stand-in for ``solver_primitives._build_node_list``'s interning."""
    idx: dict = {}
    for s in layout.shapes:
        for (x, y) in list(s.polygon.exterior.coords)[:-1]:
            key = (round(float(x), 6), round(float(y), 6))
            if key not in idx:
                idx[key] = len(idx)
    return idx


def _spine(layout):
    """Build the global spine for ``layout``; return ``(G, key->idx)``."""
    keys = _nodes_of(layout)
    G = GG.UnifiedGraph()
    for (k, i) in keys.items():
        G.pos[i] = k
    GG._build_global_spine(G, _ctx(layout), icao="TEST", layout=layout)
    return G, keys


def _route_len(G, a, b):
    """Cheapest ``spine_adj`` budget from ``a`` to ``b`` (``None`` if
    disconnected) — the same metric ``spine_value_fields`` walks."""
    best = {a: 0.0}
    pq = [(0.0, a)]
    seen = set()
    while pq:
        d, u = heapq.heappop(pq)
        if u in seen:
            continue
        seen.add(u)
        if u == b:
            return d
        for (v, budget) in G.spine_adj.get(u, ()):
            nd = d + budget
            if nd < best.get(v, float("inf")):
                best[v] = nd
                heapq.heappush(pq, (nd, v))
    return None


def _anchor_pair(keys):
    """The two ends of the axis — the anchors the route is priced between."""
    return keys[(0.0, 0.0)], keys[(0.0, _LEN)]


def _insert_row(layout):
    """Plant the lateral row at the 12 m station step (R-c's arming)."""
    return lsn.insert_lateral_spine_nodes(layout, "TEST",
                                          station_step_m=_STEP)


# ── the ruling ────────────────────────────────────────────────────────

def test_a_lateral_row_does_not_change_any_route_length():
    """THE TWIN.  Route lengths between the anchors are IDENTICAL — bit
    for bit — before and after a lateral row crosses the corridor."""
    base = _corridor_layout()
    Gb, kb = _spine(base)
    a, b = _anchor_pair(kb)
    before = _route_len(Gb, a, b)
    assert before is not None and before > 0.0

    after_layout = _corridor_layout()
    assert _insert_row(after_layout) > 0, "the fixture must plant a row"
    Ga, ka = _spine(after_layout)
    a2, b2 = _anchor_pair(ka)
    after = _route_len(Ga, a2, b2)

    assert after == before, (
        f"a lateral row moved the route budget {before} -> {after}; the "
        f"transverse law and the route metric are sharing one graph again")


def test_every_route_length_between_pre_existing_nodes_is_preserved():
    """Not just the anchor pair: EVERY pair of nodes that existed before
    the row prices the same route after it."""
    base = _corridor_layout()
    Gb, kb = _spine(base)
    after_layout = _corridor_layout()
    _insert_row(after_layout)
    Ga, ka = _spine(after_layout)

    shared = [k for k in kb if k in ka]
    assert len(shared) >= 4
    for i, ki in enumerate(shared):
        for kj in shared[i + 1:]:
            assert (_route_len(Ga, ka[ki], ka[kj])
                    == _route_len(Gb, kb[ki], kb[kj])), (ki, kj)


def test_the_twin_is_not_vacuous_the_off_arm_moves_the_budget(monkeypatch):
    """With R-a OFF the SAME row changes the route budget — so the test
    above is measuring the mechanism, not an inert fixture."""
    base = _corridor_layout()
    Gb, kb = _spine(base)
    before = _route_len(Gb, *_anchor_pair(kb))

    monkeypatch.setenv("O4_FABRIC_RA_ROUTE_TRANSPARENT_LATERALS", "0")
    off_layout = _corridor_layout()
    _insert_row(off_layout)
    Go, ko = _spine(off_layout)
    after = _route_len(Go, *_anchor_pair(ko))
    assert after != before, (
        "the OFF arm must reproduce the pre-R-a world, where the feet are "
        "strung and the corridor grows cross edges")


def test_no_route_edge_ever_touches_a_cross_section_foot():
    """The structural half of the ruling: a foot is not an endpoint of any
    ``spine_adj`` budget, and the graph SAYS which nodes those were."""
    layout = _corridor_layout()
    _insert_row(layout)
    G, keys = _spine(layout)
    feet = G.route_transparent_nodes
    assert feet, "the row must be recorded as route-transparent"
    for u, lst in G.spine_adj.items():
        assert u not in feet, u
        for (v, _budget) in lst:
            assert v not in feet, (u, v)


def test_the_recorded_feet_are_exactly_the_planted_ones():
    """The record is the emitter's own truth — no re-derivation, and no
    genuine spine node swept in beside a foot."""
    layout = _corridor_layout()
    n = _insert_row(layout)
    pts = lsn.lateral_feet(layout)
    assert len(pts) == n
    pred = lsn.lateral_foot_predicate(layout)
    assert pred is not None
    for (x, y) in pts:
        assert pred(x, y)
    # The axis ends are REAL geometry nodes, not feet: the corner
    # tolerance keeps every foot clear of them.
    assert not pred(0.0, 0.0)
    assert not pred(0.0, _LEN)


def test_a_layout_with_no_laterals_has_no_predicate_and_no_exclusions():
    """The inert path: nothing recorded ⇒ no predicate, empty exclusion
    set, and a graph byte-identical to the pre-R-a one."""
    layout = _corridor_layout()
    assert lsn.lateral_foot_predicate(layout) is None
    G, _keys = _spine(layout)
    assert G.route_transparent_nodes == set()


@pytest.mark.parametrize("flag", ["0"])
def test_off_arm_restores_the_pre_ra_graph_exactly(flag, monkeypatch):
    """OFF is the pre-commit tree: the same layout, built with the flag
    off, reproduces the graph the pre-R-a code produced — which here is
    the graph that strings the feet (asserted by inclusion, so the test
    cannot pass by producing an empty graph)."""
    monkeypatch.setenv("O4_FABRIC_RA_ROUTE_TRANSPARENT_LATERALS", flag)
    layout = _corridor_layout()
    _insert_row(layout)
    G, keys = _spine(layout)
    assert G.route_transparent_nodes == set()
    strung = set(G.spine_adj)
    foot_keys = {(round(x, 6), round(y, 6)) for (x, y) in lsn.lateral_feet(layout)}
    assert any(keys[k] in strung for k in foot_keys if k in keys), (
        "with R-a off the feet must be strung — otherwise the ON arm is "
        "proving nothing")
