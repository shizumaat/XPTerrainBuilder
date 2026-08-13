"""SERVICE STRINGING — the D′ finisher's twins (cycle 8).

Spec: ``docs/specs/cycle8-one-graph-spec.md`` ADDENDUM ("SERVICE
STRINGING"), implementing RULINGS 2026-08-06 "ONE graph" (service roads
ARE route edges) and "Service-road mouths seat like apron-edge
buildings".

THE MEASURED DEFECT.  ``_build_global_spine`` strings a centerline from
geometry nodes within ``SPINE_PERP_TOL_M`` (1.0 m).  That tolerance
assumes TAXI-style placement — the global slice cuts pavement ALONG a
taxi centerline, so its nodes land ON the line.  A service road is
sliced as a CORRIDOR: its nodes sit at the road's two EDGES, half a road
width away.  Measured at the cycle-8 baseline: SPJC 4 service
centerlines strung of 389 apt.dat segments, HECA 0, KCLT 10 — and ZERO
MOUTHS at all four battery airports, so the groundside band was fed by
the airside-valued nodes alone and every lot beyond the off-net radius
kept its DEM seed (the D′ class).

THE FIX UNDER TEST: service centerlines string at their OWN tolerance
(half the service corridor width plus the base tolerance), and only over
nodes that are ROAD-FAMILY/groundside or already on the aircraft spine.
The second clause is what makes this receiver-only: the aircraft spine's
own stringing is untouched, and the only airside node a service string
may adopt is the ATTACHMENT — which is exactly the mouth the owner's
ruling seats from the airside side.

Hand-computed geometry, no build, no network.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from auto_patch.grade_graph import (                          # noqa: E402
    Centerline, GradeContext, SERVICE_SPINE_PERP_TOL_M, SPINE_PERP_TOL_M,
    UnifiedGraph, _build_global_spine,
)
from auto_patch.config import SERVICE_ROAD_WIDTH_M            # noqa: E402


# ══════════════════════════════════════════════════════════════════════
# THE SYNTHETIC AIRPORT (plan metres)
#
#   TAXI centerline T : x = 0, from y = −100 to y = +100
#   SERVICE centerline S : y = 0, from x = 0 to x = 50
#
#   node 20 (0, 2)     — ON T (perp 0) → aircraft spine; 2.0 m from S,
#                        so it is the ATTACHMENT the service string may
#                        adopt (and only because it is already spine).
#   node 22 (0, 12)    — ON T as well: a centerline needs TWO on-line
#                        nodes to string at all, and 12 m from S keeps it
#                        out of the road's reach.
#   nodes 10..13       — the ROAD's own sliced edge nodes at y = ±3.0,
#                        i.e. half the 6 m corridor off S: MISSED by the
#                        1.0 m rule, caught by the service tolerance.
#   node 30 (40, 2)    — an APRON node 2.0 m from S: not road-family and
#                        not on the spine ⇒ never strung by a road.
#   node 21 (2.5, 50)  — 2.5 m from T: the AIRCRAFT tolerance is
#                        unchanged, so this stays off the spine.
# ══════════════════════════════════════════════════════════════════════
ROAD_NODES = {10, 11, 12, 13}
POS = {
    10: (5.0, 3.0), 11: (5.0, -3.0), 12: (25.0, 3.0), 13: (25.0, -3.0),
    20: (0.0, 2.0), 21: (2.5, 50.0), 22: (0.0, 12.0), 30: (40.0, 2.0),
}


def _graph_and_ctx():
    G = UnifiedGraph()
    G.pos = dict(POS)
    taxi = Centerline(pts=[(0.0, -100.0), (0.0, 100.0)], seg_caps=[0.015])
    svc = Centerline(pts=[(0.0, 0.0), (50.0, 0.0)], seg_caps=[0.08],
                     is_service=True)
    return G, GradeContext(centerlines=[taxi, svc])


def _run():
    G, ctx = _graph_and_ctx()
    _build_global_spine(G, ctx, icao="TEST", road_nodes=ROAD_NODES)
    return G


def test_the_service_tolerance_is_derived_from_the_corridor_width():
    """No fresh magic number: half the width the road rects are built at,
    plus the base tolerance for float/round noise."""
    assert SERVICE_SPINE_PERP_TOL_M == (
        SERVICE_ROAD_WIDTH_M / 2.0 + SPINE_PERP_TOL_M)
    # and it must actually clear a sliced road's edge nodes (3.0 m).
    assert SERVICE_SPINE_PERP_TOL_M > SERVICE_ROAD_WIDTH_M / 2.0


def test_a_sliced_road_now_strings_its_own_edge_nodes():
    """The defect, directly: at 1.0 m the four road nodes (3.0 m off the
    line) string NOTHING — fewer than two on-line nodes means no chain at
    all.  At the service tolerance they are one chain."""
    G = _run()
    for i in ROAD_NODES:
        assert i in G.spine_adj, f"road node {i} never joined the spine"
    assert G.service_spine_pairs, "no service spine pair was recorded"


def test_the_attachment_is_the_only_airside_node_a_road_may_adopt():
    """RULINGS 2026-08-06: the MOUTH is where the road meets the airside
    route network, and airside seats it.  Node 20 is on the aircraft
    spine and within the service tolerance ⇒ attachment.  Node 30 is the
    same distance from the road but is neither road-family nor spine ⇒
    the road may not touch it."""
    G = _run()
    assert 20 in G.spine_adj
    assert 30 not in G.spine_adj
    # and the attachment is recorded as a SERVICE pair, so airside reach
    # (REACH_NO_SERVICE_SPINES) still refuses to ride it: direction, not
    # deletion.
    assert any(20 in pair for pair in G.service_spine_pairs)


def test_the_aircraft_stringing_is_untouched():
    """The airside half of the walk keeps the 1.0 m rule: a node 2.5 m
    from the taxi centerline is NOT on the spine, and the road's own
    nodes are not reachable from the taxi pass either."""
    G = _run()
    assert 21 not in G.spine_adj
    # node 20's taxi-side membership comes from T, not from the road:
    # with NO road_nodes at all the aircraft chain must be unchanged.
    G2, ctx2 = _graph_and_ctx()
    _build_global_spine(G2, ctx2, icao="TEST", road_nodes=set())
    assert 21 not in G2.spine_adj
    assert not (ROAD_NODES & set(G2.spine_adj))


def test_no_road_nodes_means_no_service_string_at_all():
    """Byte-inertness of the clause: an airport whose roads carry no
    road-family geometry strings exactly what it strung before."""
    G2, ctx2 = _graph_and_ctx()
    _build_global_spine(G2, ctx2, icao="TEST", road_nodes=set())
    assert not G2.service_spine_pairs
    assert not G2.centerline_service


# ── THE APRON-EDGE MOUTH ─────────────────────────────────────────────
# The value field covers only nodes a TAXI centerline strung, so a road
# that meets airside pavement away from a centerline has no field value
# anywhere on it — measured at the cycle-8 baseline: KCLT 117 service
# spine pairs, ZERO field-covered endpoints, ZERO mouths.  The ruling
# says the mouth is seated "where it's feasible for the airside apron to
# meet it", and THE AIRSIDE BAND is that interval.

class _StubG:
    """Only what the two call sites read: positions, the service pair set
    and (for the profile solve's corridor coupling) an empty edge list."""

    def __init__(self, pos, pairs):
        self.pos = pos
        self.service_spine_pairs = pairs
        self.edges = []
        self.runway_anchor = {}


def _mouths(field_ceiling, field_floor, band):
    from auto_patch.elevation_per_surface.building_feasibility import (
        service_mouths)
    G = _StubG({1: (0.0, 0.0), 2: (100.0, 0.0)}, {(1, 2)})
    return service_mouths(object(), G, field_ceiling, field_floor,
                          airside_band=band)


def test_an_endpoint_the_field_cannot_answer_takes_the_airside_band():
    # node 1 sits on airside pavement (the band answers 5..7); node 2 is
    # 100 m out on the road, past the band's domain (None).
    band = lambda x, y: (5.0, 7.0) if x == 0.0 else None   # noqa: E731
    assert _mouths({}, {}, band) == {1: (5.0, 7.0)}


def test_no_band_means_the_pre_clause_behaviour():
    assert _mouths({}, {}, None) == {}


def test_the_value_field_still_wins_where_it_covers_the_endpoint():
    """The band is the FALLBACK, never a second authority: an endpoint the
    route metric answers keeps the route metric's interval verbatim."""
    band = lambda x, y: (5.0, 7.0)                          # noqa: E731
    out = _mouths({1: 102.0}, {1: 98.0}, band)
    assert out[1] == (98.0, 102.0)          # the field, not the band
    assert out[2] == (5.0, 7.0)             # the other end still falls back


# ── THE AIRSIDE PROFILE DOES NOT RIDE SERVICE EDGES ──────────────────

def test_the_spine_profile_solve_drops_service_edges():
    """``_solve_spine_profile`` WRITES values by a neighbour blend, so a
    strung road in its graph is groundside pulling airside.  With the
    graph's ``service_spine_pairs`` in hand it drops those edges; the
    positive control (no graph ⇒ no exclusion) shows the pull it
    prevents."""
    from auto_patch.elevation_per_surface.route_profile.solve import (
        _solve_spine_profile)

    def run(graph):
        elev = [10.0, 10.0, -500.0]
        spine_adj = {0: [(1, 1.0)], 1: [(0, 1.0), (2, 100.0)],
                     2: [(1, 100.0)]}
        frozen, _ = _solve_spine_profile(
            elev, [True, False, False], spine_adj, {},
            nodes_xy=[(0.0, 0.0), (10.0, 0.0), (20.0, 0.0)], graph=graph)
        return elev, frozen

    elev_excl, frozen_excl = run(_StubG({}, {(1, 2)}))
    assert elev_excl[2] == -500.0          # the road never moved
    assert 2 not in frozen_excl            # ... and was not frozen as spine
    elev_ctrl, _ = run(None)               # POSITIVE CONTROL
    assert elev_ctrl[2] != -500.0


def test_the_service_half_of_the_spine_census_is_reported():
    """Instrument truth (RULINGS 2026-08-06 clause 2): the walk reports
    the numbers a reader needs to tell "no roads here" from "the roads
    did not string" — walked, strung, pairs, attachments."""
    G = _run()
    assert G.spine_service_centerlines == 1        # walked
    assert len(G.centerline_service) == 1          # strung
    assert G.spine_service_attachments >= 1        # mouth candidates


# ══════════════════════════════════════════════════════════════════════
# AMENDMENT 2 (Fable lead 2026-08-12b) — THE AIRSIDE EXCLUSION AT THE
# POPULATION SOURCE.
#
# THE MEASURED DEFECT.  Once a corridor is registered END-TO-END (the
# 2026-08-12b "one corridor = ONE continuous law object" ruling) its walk
# crosses APRON pavement, so it strings MANY airside nodes rather than the
# one mouth this module's docstring admits — and it linked consecutive
# PAIRS OF THEM into ``spine_adj`` at the road cap.  Every consumer of the
# one graph then saw a groundside object in an airside input: the reach
# band as pairs to exclude (HECA, measured: −65 airside adjudicated rows
# when the exclusion was lifted) and the profile solve as an 8 % law edge
# between two apron nodes.
#
# THE FIX UNDER TEST.  A service centerline links only pairs with at least
# one ROAD-FAMILY endpoint.  The MOUTH survives by construction (one end of
# a mouth pair IS a road node); an airside-to-airside pair is never woven.
# One place, one law — every consumer inherits it.
#
# THE CROSSING FIXTURE: a second taxi centerline T2 at x = 40 puts a
# SECOND airside node (40) within the service tolerance of the corridor,
# with node 20 the first.  With no road geometry between them the two are
# CONSECUTIVE on the corridor's walk — the apron crossing, in miniature.
# ══════════════════════════════════════════════════════════════════════

import pytest                                                 # noqa: E402

from auto_patch.grade_graph import (                          # noqa: E402
    Centerline as _CL, GradeContext as _Ctx, UnifiedGraph as _UG,
)

CROSS_POS = {
    20: (0.0, 2.0),        # on T,  2.0 m from the corridor  → airside
    22: (0.0, 12.0),       # on T   (a chain needs two nodes)
    40: (40.0, 2.0),       # on T2, 2.0 m from the corridor  → airside
    42: (40.0, 12.0),      # on T2
    10: (20.0, 3.0),       # the corridor's OWN sliced edge node
}


def _crossing(road_nodes):
    G = _UG()
    G.pos = dict(CROSS_POS)
    t1 = _CL(pts=[(0.0, -100.0), (0.0, 100.0)], seg_caps=[0.015])
    t2 = _CL(pts=[(40.0, -100.0), (40.0, 100.0)], seg_caps=[0.015])
    svc = _CL(pts=[(0.0, 0.0), (60.0, 0.0)], seg_caps=[0.08], is_service=True)
    ctx = _Ctx(centerlines=[t1, t2, svc])
    _build_global_spine(G, ctx, icao="TEST", road_nodes=road_nodes)
    return G


def _linked(G, a, b):
    return any(j == b for (j, _bud) in G.spine_adj.get(a, ()))


class TestAirsideExclusionAtThePopulationSource:

    def test_a_corridor_never_links_two_airside_nodes(self, monkeypatch):
        """The apron crossing: nodes 20 and 40 are both airside and both
        within the corridor's tolerance, and NOTHING may weave them."""
        G = _crossing(road_nodes=set())
        assert not _linked(G, 20, 40) and not _linked(G, 40, 20)
        assert not any({20, 40} == set(p) for p in G.service_spine_pairs)

    def test_the_gate_off_reproduces_the_defect(self, monkeypatch):
        """The knife's other arm — proof this twin measures the clause and
        not an accident of the fixture."""
        import auto_patch.config as cfg
        monkeypatch.setattr(cfg, "SERVICE_BAND_AIRSIDE_EXCLUSION", False)
        G = _crossing(road_nodes=set())
        assert _linked(G, 20, 40), (
            "with the exclusion off the corridor must weave the airside "
            "pair — otherwise this fixture proves nothing")

    def test_the_mouth_still_links(self):
        """One end of a mouth pair is a ROAD node, so the mouth is kept by
        construction — the 2026-08-06 ruling is untouched."""
        G = _crossing(road_nodes={10})
        assert _linked(G, 10, 20) or _linked(G, 20, 10)
        assert _linked(G, 10, 40) or _linked(G, 40, 10)
        assert any(set(p) == {10, 20} for p in G.service_spine_pairs)

    def test_the_airside_pair_is_still_refused_with_road_nodes_present(self):
        """Even when the corridor has its own geometry, the two airside
        nodes are never linked TO EACH OTHER."""
        G = _crossing(road_nodes={10})
        assert not _linked(G, 20, 40) and not _linked(G, 40, 20)

    def test_no_airside_node_gains_a_band_input_from_a_corridor(self):
        """The ruling stated as the band's own question: for every airside
        node, the set of spine neighbours a CORRIDOR contributed is either
        empty or a road-family node (the mouth).  A groundside corridor may
        not alter airside feasibility inputs."""
        road = {10}
        G = _crossing(road_nodes=road)
        airside = {20, 22, 40, 42}
        for pair in G.service_spine_pairs:
            a, b = pair
            assert not (a in airside and b in airside), (
                f"corridor pair {pair} is airside-to-airside")
        for i in airside:
            for (j, _b) in G.spine_adj.get(i, ()):
                if any(set(p) == {i, j} for p in G.service_spine_pairs):
                    assert j in road, (
                        f"airside node {i} took a corridor edge to {j}, "
                        f"which is not a road-family node")

    def test_the_aircraft_spine_is_byte_untouched_by_the_clause(self):
        """The aircraft pass runs first and the clause only reads
        ``cl.is_service`` — the taxi chains are identical either way."""
        import auto_patch.config as cfg
        on = _crossing(road_nodes={10})
        setattr(cfg, "SERVICE_BAND_AIRSIDE_EXCLUSION", False)
        try:
            off = _crossing(road_nodes={10})
        finally:
            setattr(cfg, "SERVICE_BAND_AIRSIDE_EXCLUSION", True)
        for i in (20, 22, 40, 42):
            taxi_on = {j for (j, _b) in on.spine_adj.get(i, ())
                       if not any(set(p) == {i, j}
                                  for p in on.service_spine_pairs)}
            taxi_off = {j for (j, _b) in off.spine_adj.get(i, ())
                        if not any(set(p) == {i, j}
                                   for p in off.service_spine_pairs)}
            assert taxi_on == taxi_off
