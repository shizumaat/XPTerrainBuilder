"""THE ROAD FEED JOINS THE ONE GRAPH — cycle 9's twins.

Spec: ``docs/specs/cycle9-road-feed-spec.md``, implementing RULINGS
2026-08-06 "ONE graph: groundside joins the route graph" and
"Service-road mouths seat like apron-edge buildings".

THE MEASURED DEFECT (c8fin's STOP dossier).  ``layout.apt_taxi_centerlines``
carries the apt.dat row-1206 ground-vehicle routes and nothing else — HECA
5, KCLT 15, SPJC 15, HEAZ 0 — so those were the only service edges the ONE
graph ever contained.  The roads that actually CARVE the slice, and that the
emitter ships as ``service_road`` / ``service_junction`` shapes, come from
the per-airport ROAD FEED (HECA 705 lines / 97.9 km after free-road
scoping).  They cut groundside geometry and then never became route edges,
so nothing downstream of them could reach a band: mouths fired, the band
propagated, and the stranded lots still kept their DEM seed.  That is the D′
population.

THE FIX UNDER TEST.  ONE enumeration — ``grade_graph.centerline_specs`` —
is the law's centerline membership, and the service half of it reads the
SLICE's own scoped road set (``layout._slice_service_subsegments``): the
row-1206 routes and the feed ways alike, after free-road scoping (owner
2026-07-27 — a road inside or edge-sharing an apron IS the apron, never
carved, so never its own spine).

THE LOCKSTEP is the point of the shared enumeration.  ``build_context`` is
the SOLVER-and-VALIDATOR context; ``verification.taxi_axes_exact_ll`` is the
SIDECAR mirror the census reads back as ``axes_exact``.  They used to be two
hand-kept copies of the same walk, so a membership change in one was
invisible to the other and the census would judge a patch under a spine the
build never graded to (the half-landed-law defect the RULINGS forbid).  Both
now consume the same list, and the three-way agreement — solver context,
sidecar, census reader — is asserted here directly.

Hand-computed geometry, no build, no network.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest
from shapely.geometry import LineString, Point

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from auto_patch import grade_graph as GG                      # noqa: E402
from auto_patch.config import (                               # noqa: E402
    SERVICE_ROAD_MAX_GRADE, taxi_grade_cap_for_letter)
from auto_patch.verification import taxi_axes_exact_ll        # noqa: E402


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def cg():
    return _load("road_feed_twin_check_grade", ROOT / "tools" / "check_grade.py")


# ══════════════════════════════════════════════════════════════════════
# THE SYNTHETIC AIRPORT (plan metres)
#
#   TAXI centerline T   : x = 0, y = −100 … +100  (an ICAO "C" route)
#   APT service route A : y = 0,  x = 0 … 50      (the row-1206 road)
#   FEED subsegments    : the slice's scoped road set —
#       F1 (the free remains of A, apron portion scoped away)
#       F2 a feed way running out to a lot, 60 m further
#
#   The apt.dat road A is NOT independently registered when the slice ran:
#   F1 IS its scoped remains, and registering both would double-spine the
#   same physical road.
# ══════════════════════════════════════════════════════════════════════
TAXI_PTS = [(0.0, -100.0), (0.0, 100.0)]
APT_SVC_PTS = [(0.0, 0.0), (50.0, 0.0)]
FEED_1_PTS = [(12.0, 0.0), (50.0, 0.0)]
FEED_2_PTS = [(50.0, 0.0), (110.0, 0.0)]


class _FakeCenterline:
    """The ``apt_dat_reader.TaxiCenterline`` surface the law reads."""

    def __init__(self, pts, is_service=False, seg_sizes=None):
        self.line = LineString(pts)
        self.route_line = None
        self.is_service = is_service
        self.name = "svc" if is_service else "T"
        self.seg_sizes = (list(seg_sizes) if seg_sizes is not None
                          else [""] * (len(pts) - 1))


class _FakeLayout:
    """Minimal layout: what both law readers actually touch."""

    def __init__(self, *, sliced=None):
        self.icao = "TEST"
        self.shapes = []
        self.anchor = (0.0, 0.0)
        self.canonical_points = None
        self.apt_taxi_centerlines = [
            _FakeCenterline(TAXI_PTS, seg_sizes=["C"]),
            _FakeCenterline(APT_SVC_PTS, is_service=True),
        ]
        if sliced is not None:
            self._slice_service_subsegments = [LineString(p) for p in sliced]

    # the local-metre → lat/lon map the sidecar export uses
    def m_to_ll(self, x, y):
        return (y / 111320.0, x / 111320.0)


def _specs(**kw):
    return GG.centerline_specs(_FakeLayout(**kw))


def _service(specs):
    return [s for s in specs if s[2]]


def _taxi(specs):
    return [s for s in specs if not s[2]]


# ── 1. the service SOURCE ────────────────────────────────────────────

def test_the_sliced_road_set_is_the_service_source():
    """The feed roads join the graph — the whole point of the cycle."""
    specs = _specs(sliced=[FEED_1_PTS, FEED_2_PTS])
    svc = _service(specs)
    assert len(svc) == 2, "the two sliced road subsegments must both register"
    assert {tuple(s[0]) for s in svc} == {
        tuple((float(x), float(y)) for (x, y) in FEED_1_PTS),
        tuple((float(x), float(y)) for (x, y) in FEED_2_PTS)}


def test_the_apt_route_is_not_double_registered_beside_its_own_remains():
    """``_slice_service_subsegments`` already CONTAINS the row-1206 routes,
    free-road-scoped.  Registering the unscoped original as well would give
    one physical road two spines at two different extents — and would put a
    spine back through the apron portion the free-road ruling scoped away."""
    svc = _service(_specs(sliced=[FEED_1_PTS, FEED_2_PTS]))
    assert all(tuple(s[0]) != tuple((float(x), float(y))
                                    for (x, y) in APT_SVC_PTS)
               for s in svc), "the unscoped apt.dat road was registered too"


def test_without_a_slice_the_apt_service_routes_still_string():
    """Layouts built without the global slice (unit fixtures) keep the
    pre-cycle-9 behaviour — presence of the attribute is the switch, not its
    truthiness, so a slice that legitimately scoped every road away is not
    silently re-fed from apt.dat."""
    svc = _service(_specs())
    assert len(svc) == 1
    assert tuple(svc[0][0]) == tuple((float(x), float(y))
                                     for (x, y) in APT_SVC_PTS)
    assert _service(_specs(sliced=[])) == [], (
        "an empty sliced set means the slice scoped every road away")


def test_the_feed_roads_carry_the_road_cap_and_the_service_flag():
    """Their 8 % budgets via the existing service pricing — never a taxi
    cap, and flagged so airside reachability keeps refusing to ride them."""
    for (pts, seg_caps, is_svc, _rkey, _rpts) in _service(
            _specs(sliced=[FEED_1_PTS, FEED_2_PTS])):
        assert is_svc is True
        assert seg_caps == [SERVICE_ROAD_MAX_GRADE] * (len(pts) - 1)


def test_the_aircraft_spine_is_untouched_by_the_feed():
    """Receiver-only, structurally: the taxi half of the enumeration is
    byte-identical with and without the road feed."""
    without = _taxi(_specs())
    with_feed = _taxi(_specs(sliced=[FEED_1_PTS, FEED_2_PTS]))
    assert [(s[0], s[1], s[2]) for s in without] == \
           [(s[0], s[1], s[2]) for s in with_feed]
    assert without[0][1] == [taxi_grade_cap_for_letter("C")]


# ── 2. THE LOCKSTEP: solver context ↔ sidecar ↔ census reader ────────

def test_the_two_law_readers_enumerate_the_same_centerlines():
    """``build_context`` (solver + validator) and ``taxi_axes_exact_ll``
    (the sidecar mirror) must agree on membership, per-segment caps and
    route ordinals — by construction, not by inspection."""
    layout = _FakeLayout(sliced=[FEED_1_PTS, FEED_2_PTS])
    ctx = GG.build_context(layout)
    axes, routes = taxi_axes_exact_ll(layout)
    assert len(ctx.centerlines) == len(axes) == 3, (
        "one taxi route + two sliced roads reach both readers")
    for cl, (pts_ll, caps, ridx, is_svc) in zip(ctx.centerlines, axes):
        assert list(cl.seg_caps) == list(caps)
        assert cl.route_idx == ridx
        assert len(cl.pts) == len(pts_ll)
        assert cl.is_service == is_svc, (
            "the SERVICE flag must travel with the axis — without it the "
            "census reads a truck route as an aircraft spine")
    assert len(ctx.routes) == len(routes)


def test_the_census_reader_sees_the_feed_axes(cg, tmp_path):
    """The third leg: what the emitted sidecar carries is what the census
    judges under.  A solver-only registration — the graph gaining roads the
    sidecar never exports — is the half-landed law the RULINGS forbid."""
    layout = _FakeLayout(sliced=[FEED_1_PTS, FEED_2_PTS])
    ctx = GG.build_context(layout)
    axes, routes = taxi_axes_exact_ll(layout)
    patch = tmp_path / "p.osm"
    (tmp_path / "p.osm.axes.json").write_text(json.dumps({
        "axes_exact": [[pts, caps, ridx, svc]
                       for (pts, caps, ridx, svc) in axes],
        "routes_exact": routes,
        "anchor": [0.0, 0.0],
        "ruleset": "icao",
    }))
    law = cg.law_context_from_sidecar(patch)
    assert len(law["taxi_axes_ll"]) == len(ctx.centerlines), (
        "the census must judge under the same centerline set the solve "
        "graded to")
    caps_seen = {tuple(e[1]) for e in law["taxi_axes_ll"]}
    assert (SERVICE_ROAD_MAX_GRADE,) in caps_seen, (
        "the road-feed service axes never reached the census")
    # the flag survives the round trip — the census's centerline rebuild
    # keys the "not an aircraft spine" rule off it
    assert sum(1 for e in law["taxi_axes_ll"] if e[4]) == 2
    assert sum(1 for e in law["taxi_axes_ll"] if not e[4]) == 1


def test_a_legacy_sidecar_without_the_flag_still_reads(cg, tmp_path):
    """Sidecars written before the flag existed carry 3-element entries and
    must read as all-taxi — which is exactly how they were graded."""
    patch = tmp_path / "old.osm"
    (tmp_path / "old.osm.axes.json").write_text(json.dumps({
        "axes_exact": [[[[0.0, 0.0], [0.001, 0.0]], [0.015], 0]],
        "routes_exact": [[[0.0, 0.0], [0.001, 0.0]]],
        "anchor": [0.0, 0.0], "ruleset": "icao",
    }))
    law = cg.law_context_from_sidecar(patch)
    assert [e[4] for e in law["taxi_axes_ll"]] == [False]


def test_axes_exact_is_the_wired_sidecar_key(cg):
    """No new sidecar key is minted: the feed rides the existing exact-axes
    contract, so ``SIDECAR_LAW_KEYS`` (the twin-asserted key registry) is
    already complete for it."""
    assert cg.SIDECAR_LAW_KEYS["axes_exact"] == "taxi_axes_ll"


# ── 3. the graph half: the feed becomes route edges ──────────────────

def test_the_feed_roads_become_service_route_edges_in_the_one_graph():
    """The mechanism's purpose: road-family nodes along a FEED road string
    into ``spine_adj`` at the road budget, and the pairs are tagged service
    so airside reachability still refuses to ride them (direction, not
    deletion)."""
    layout = _FakeLayout(sliced=[FEED_1_PTS, FEED_2_PTS])
    ctx = GG.build_context(layout)
    G = GG.UnifiedGraph()
    # the lot's own sliced edge nodes, 3 m off the feed road's centerline —
    # out of reach of the 1.0 m aircraft rule, in reach of the service one
    G.pos = {1: (60.0, 3.0), 2: (60.0, -3.0), 3: (100.0, 3.0),
             4: (100.0, -3.0), 5: (0.0, 2.0), 6: (0.0, 12.0)}
    GG._build_global_spine(G, ctx, icao="TEST", road_nodes={1, 2, 3, 4})
    for i in (1, 2, 3, 4):
        assert i in G.spine_adj, f"lot node {i} never joined the ONE graph"
    assert G.service_spine_pairs, "the feed road minted no service pair"
    assert G.spine_service_centerlines == 2, (
        "both sliced roads must be walked as service centerlines")


def test_a_feed_road_may_not_sweep_an_unrelated_airside_node():
    """Receiver-only at the stringing tolerance: the restricted node set is
    road-family plus the aircraft spine, so a road passing near an apron
    vertex that is neither may not adopt it."""
    layout = _FakeLayout(sliced=[FEED_1_PTS, FEED_2_PTS])
    ctx = GG.build_context(layout)
    G = GG.UnifiedGraph()
    G.pos = {1: (60.0, 3.0), 2: (100.0, 3.0), 9: (80.0, 2.0)}
    GG._build_global_spine(G, ctx, icao="TEST", road_nodes={1, 2})
    assert 9 not in G.spine_adj, (
        "an apron node the road merely passes was swept into the spine")


# ── 4. a truck route is not an aircraft spine (the Q4 gate's law) ────

def _shape(role, ring):
    return GG.GradeShape(role=role, ring=list(ring),
                         keys=list(range(len(ring))))


def _ctx_with_a_road_across_an_apron():
    """An apron 60 m square with a SERVICE road running straight through
    it, plus one taxi centerline along its west edge."""
    layout = _FakeLayout(sliced=[[(0.0, 30.0), (60.0, 30.0)]])
    layout.apt_taxi_centerlines = [
        _FakeCenterline([(0.0, 0.0), (0.0, 60.0)], seg_sizes=["C"])]
    return GG.build_context(layout)


APRON_RING = [(0.0, 0.0), (60.0, 0.0), (60.0, 60.0), (0.0, 60.0)]


def test_a_service_road_is_not_an_airside_shapes_spine():
    """MEASURED (cycle 9, arm 1): with the feed roads in the graph, airside
    rose at 7 of 8 battery cells, carried by ``transverse::apron|apron``
    (HECA 10 000 +176) and ``transverse::junction|junction`` (+132) —
    families that exist only relative to a spine.  A truck route passing
    over airside pavement may not become that pavement's spine."""
    from auto_patch.layout import ROLE_APRON
    ctx = _ctx_with_a_road_across_an_apron()
    assert any(cl.is_service for cl in ctx.centerlines)
    apron = _shape(ROLE_APRON, APRON_RING)
    mem = GG._spine_membership(apron, ctx)
    for hits in mem.values():
        for (ci, _a) in hits:
            assert not ctx.centerlines[ci].is_service, (
                "an apron took a service road as its spine")


def test_the_road_is_still_its_own_spine():
    """The positive control — the restriction is by ROLE, not a deletion:
    the road's own face still reads it (that is the whole cycle)."""
    from auto_patch.layout import ROLE_SERVICE_JUNCTION
    ctx = _ctx_with_a_road_across_an_apron()
    # within SPINE_PERP_TOL_M of the road centerline at y = 30 (the
    # membership tolerance is the taxi one — the SERVICE tolerance is the
    # STRINGING rule, a different reader)
    road = _shape(ROLE_SERVICE_JUNCTION,
                  [(10.0, 29.5), (50.0, 29.5), (50.0, 30.5), (10.0, 30.5)])
    mem = GG._spine_membership(road, ctx)
    assert any(ctx.centerlines[ci].is_service
               for hits in mem.values() for (ci, _a) in hits), (
        "the road's own face lost its spine")


def test_an_apron_chord_is_not_dropped_for_crossing_a_truck_road():
    """The crossing predicate is the other half: a body chord that crosses
    a SPINE is not a real grade path (the climb is carried by the spine).
    A truck road is not that spine, so the chord must still be graded."""
    from auto_patch.layout import ROLE_APRON, ROLE_SERVICE_JUNCTION
    ctx = _ctx_with_a_road_across_an_apron()
    apron = _shape(ROLE_APRON, APRON_RING)
    crosses = GG._spine_crossing_predicate(apron, ctx,
                                           GG._spine_membership(apron, ctx))
    assert crosses is not None
    # a chord straight across the apron, over the road at y = 30
    assert not crosses(30.0, 5.0, 30.0, 55.0), (
        "an apron chord was dropped because a truck road crossed it")
    road = _shape(ROLE_SERVICE_JUNCTION, APRON_RING)
    crosses_gs = GG._spine_crossing_predicate(
        road, ctx, GG._spine_membership(road, ctx))
    assert crosses_gs(30.0, 5.0, 30.0, 55.0), (
        "the road's own law lost the crossing rule")


def test_the_road_zone_geometry_is_not_the_membership_source():
    """Guard against the tempting shortcut: registration reads the SLICE's
    line set, never the emitted road polygons — the two are different
    populations and keying on shapes would resurrect the proximity join."""
    layout = _FakeLayout(sliced=[FEED_1_PTS])
    assert len(_service(GG.centerline_specs(layout))) == 1
    layout.shapes = []           # no road SHAPES at all
    assert len(_service(GG.centerline_specs(layout))) == 1
