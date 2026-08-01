"""FEASIBILITY consumers must refuse ``service_spine_pairs`` edges.

Owner ruling 2026-07-29: *"reachability for all airside should never use
any groundside or service road paths."*  Service centerlines still weave
into ``UnifiedGraph.spine_adj`` — the solve grades roads along their own
spine — but every FEASIBILITY consumer of that one graph must filter the
pairs recorded in ``UnifiedGraph.service_spine_pairs``.  This file is the
guard: it pins the contract per consumer so a future consumer cannot
silently reintroduce service-road feasibility.

Ordered by ``docs/specs/single-space-string-audit-spec.md`` §3:

  1. reach-band VALUE FIELDS      (``spine_value_fields``' Dijkstras)
  2. NEAREST-ATTACHMENT lookup    (the band's route-attachment assignment)
  3. ROUTE-DISTANCE oracle        (``grade_graph._RouteDistanceOracle``)
  4. RASTER reach band            (``build_raster_reach_band``)

SINGLE ENGINE (2026-07-29, spec ``rod-compose-and-band-single-source-
spec.md`` §B): consumers 1, 2 and 4 are now ONE producer —
``reach_band_unified`` is a thin wrapper over ``build_raster_reach_band``,
which reads its VALUE from ``spine_value_fields`` (route metric,
service-excluded) and uses the grid only to find a point's nearest route
attachment and the local off-route leg.  The legacy nearest-visible-
centerline band, the raster→legacy fall-through and ``_build_skeleton_band``
were deleted, and with them the ``O4_RASTER_REACH_BAND`` selector.  Tests
1-3 therefore exercise the same engine as tests 4-5; they still pin the
distinct CONSUMER contracts, which is the point of the file.

THE FIXTURE — a "U" airport, all coordinates in local metres:

    (0,300) ─── 100 m ─── (100,300)
       │                      │
     300 m                  300 m        taxi centerline, cap 1.5 %
       │                      │
    (0,0)A ····· 100 m ····· (100,0)T    SERVICE road, cap 5 %

``A`` is the runway-join anchor at 100.0 m.  ``T`` is reachable two ways:
the 700 m taxi route around the U (a 10.5 m climb at 1.5 %) or the 100 m
service shortcut (5.0 m at 5 %).  A consumer that honours the exclusion
must price ``T`` at the taxi route; one that rides the road prices it at
the shortcut.  The two answers differ by 5.5 m, so every assertion below
is a real discriminator, not a tolerance.
"""
from __future__ import annotations

import math
import types

import pytest
from shapely.geometry import LineString, Polygon

from auto_patch import config as ap_config
from auto_patch import grade_graph as GG
from auto_patch.apt_dat_reader import TaxiCenterline
from auto_patch.elevation_per_surface.building_feasibility import (
    reach_band_unified)
from auto_patch.layout import BuiltShape, ROLE_APRON, ROLE_SERVICE_ROAD


ANCHOR_VALUE = 100.0
TAXI_CAP = 0.015
SVC_CAP = 0.05
# Taxi route A→(0,300)→(100,300)→T = 700 m at 1.5 % = 10.5 m of climb.
TAXI_CLIMB = TAXI_CAP * 700.0
# Service shortcut A→T = 100 m at 5 % = 5.0 m of climb.
SVC_CLIMB = SVC_CAP * 100.0

TAXI_PTS = [(0.0, 0.0), (0.0, 300.0), (100.0, 300.0), (100.0, 0.0)]
SVC_PTS = [(0.0, 0.0), (100.0, 0.0)]


def _u_graph(taxi_end=(100.0, 0.0), service_end=None):
    """The U fixture as a hand-built :class:`UnifiedGraph`.

    Node 0 = A (anchor), 1 = (0,300), 2 = (100,300), 3 = the taxi chain's
    far end T.  By default the service road ends at T too (one shared
    node carrying both a taxi and a service edge — the real topology).
    Passing ``service_end`` splits the road onto its OWN node 4, which is
    then reachable ONLY through a ``service_spine_pairs`` edge — the case
    the nearest-node lookup has to filter.
    """
    G = GG.UnifiedGraph()
    G.pos = {0: (0.0, 0.0), 1: (0.0, 300.0), 2: (100.0, 300.0),
             3: taxi_end}

    def link(a, b, cap):
        d = math.dist(G.pos[a], G.pos[b])
        G.spine_adj.setdefault(a, []).append((b, cap * d))
        G.spine_adj.setdefault(b, []).append((a, cap * d))

    link(0, 1, TAXI_CAP)
    link(1, 2, TAXI_CAP)
    link(2, 3, TAXI_CAP)
    if service_end is None:
        link(0, 3, SVC_CAP)                   # the shortcut, shared node
        G.service_spine_pairs = {(0, 3)}
    else:
        G.pos[4] = service_end
        link(0, 4, SVC_CAP)                   # the shortcut, own node
        G.service_spine_pairs = {(0, 4)}
    G.runway_anchor = {0: ANCHOR_VALUE}
    return G


def _u_layout(shapes=()):
    """A minimal layout carrying the two centerlines (one taxi, one
    service) plus whatever pavement a test needs."""
    taxi = TaxiCenterline(line=LineString(TAXI_PTS),
                          seg_sizes=["C", "C", "C"], is_service=False,
                          name="A1")
    svc = TaxiCenterline(line=LineString(SVC_PTS), seg_sizes=["C"],
                         is_service=True, name="SVC1")
    return types.SimpleNamespace(
        shapes=list(shapes), apt_taxi_centerlines=[taxi, svc],
        canonical_points=None, anchor=(0.0, 0.0))


@pytest.fixture
def band_engine():
    """The band engine needs scipy (the grid lookup); skip without it."""
    pytest.importorskip("scipy")


# ── 1. reach-band VALUE FIELDS ──────────────────────────────────────────

def test_reach_band_value_fields_refuse_the_service_shortcut(band_engine):
    """The ceiling/floor Dijkstras must price T by the 700 m TAXI route.

    T sits ON a valued spine node, so the off-route leg is zero and the
    band reads that node's route value exactly."""
    band = reach_band_unified(_u_layout(_paved_u()), _u_graph())
    got = band(100.0, 0.0)
    assert got is not None, "T must still be reachable — by the taxi route"
    floor, ceil = got
    assert ceil == pytest.approx(ANCHOR_VALUE + TAXI_CLIMB, abs=1e-6)
    assert floor == pytest.approx(ANCHOR_VALUE - TAXI_CLIMB, abs=1e-6)


def test_fixture_actually_exercises_the_gate(band_engine, monkeypatch):
    """A/B proof the fixture discriminates: with the exclusion OFF the very
    same band rides the road and prices T at the 100 m shortcut."""
    monkeypatch.setattr(ap_config, "REACH_NO_SERVICE_SPINES", False)
    band = reach_band_unified(_u_layout(_paved_u()), _u_graph())
    floor, ceil = band(100.0, 0.0)
    assert ceil == pytest.approx(ANCHOR_VALUE + SVC_CLIMB, abs=1e-6)
    assert floor == pytest.approx(ANCHOR_VALUE - SVC_CLIMB, abs=1e-6)


# ── 2. NEAREST-ATTACHMENT lookup ────────────────────────────────────────

def test_nearest_node_lookup_drops_service_only_nodes(band_engine):
    """The attachment lookup must not hand a query a node with no value.

    The service road's far end sits 0.1 m from the query point and the
    taxi chain's own end 1.0 m away.  Under the exclusion the service node
    carries NO field entry, so it is never seeded as an attachment; the
    nearer-but-valueless node must not win the assignment and leave the
    point priced off something else (or off-net).  The taxi node must.
    """
    G = _u_graph(taxi_end=(100.0, 1.0), service_end=(100.0, 0.1))
    band = reach_band_unified(_u_layout(_paved_u()), G)
    got = band(100.0, 0.0)
    assert got is not None
    floor, ceil = got
    # kB = the taxi chain end (node 3): 300 + 100 + 299 m of taxi route.
    taxi_climb = TAXI_CAP * (300.0 + 100.0 + math.dist((100.0, 300.0),
                                                       (100.0, 1.0)))
    assert ceil == pytest.approx(ANCHOR_VALUE + taxi_climb, abs=1e-6)
    # Discriminator: if the service-only node had won the nearest-node
    # query it would have contributed NO field entry, and the ceiling
    # would fall back to the kA candidate priced along the LINE (700 m).
    assert ceil < ANCHOR_VALUE + TAXI_CAP * 700.0 - 1e-9


# ── 3. ROUTE-DISTANCE oracle ────────────────────────────────────────────

def test_route_distance_oracle_ignores_service_centerlines():
    """``_RouteDistanceOracle`` must route A→T the long way round."""
    cls = [GG.Centerline(pts=TAXI_PTS, seg_caps=[TAXI_CAP] * 3,
                         is_service=False),
           GG.Centerline(pts=SVC_PTS, seg_caps=[SVC_CAP], is_service=True)]
    oracle = GG._RouteDistanceOracle(cls)
    legs = oracle.legs((0.0, 0.0), (100.0, 0.0))
    assert legs is not None
    off_a, graph_d, off_b = legs
    assert off_a == pytest.approx(0.0, abs=1e-9)
    assert off_b == pytest.approx(0.0, abs=1e-9)
    assert graph_d == pytest.approx(700.0, abs=1e-6), (
        "the service shortcut must not be in the route graph")
    assert oracle.distance((0.0, 0.0), (100.0, 0.0)) == pytest.approx(
        700.0, abs=1e-6)


# ── 4. RASTER reach band ────────────────────────────────────────────────

def _paved_u(shortcut_role=ROLE_SERVICE_ROAD, width=15.0):
    """Pavement for the U: apron corridors along the taxi route, plus the
    shortcut corridor under the SERVICE centerline.

    ``shortcut_role`` is the whole point of the raster pair below: a
    service route may be drawn over its own ``service_road`` pavement, or
    straight across AIRSIDE pavement (HECA's giant aprons carry service
    routes through them).  The spine pair is a ``service_spine_pairs``
    member either way.
    """
    def strip(a, b):
        return LineString([a, b]).buffer(width / 2.0, cap_style=2)

    apron = (strip((0.0, 0.0), (0.0, 300.0))
             .union(strip((0.0, 300.0), (100.0, 300.0)))
             .union(strip((100.0, 300.0), (100.0, 0.0))))
    shapes = [BuiltShape(polygon=p, role=ROLE_APRON, altitude=100.0)
              for p in (apron.geoms if apron.geom_type == "MultiPolygon"
                        else [apron])]
    shapes.append(BuiltShape(polygon=strip((0.0, 0.0), (100.0, 0.0)),
                             role=shortcut_role, altitude=100.0))
    return shapes


def _raster_ceiling(shortcut_role, monkeypatch):
    pytest.importorskip("scipy")
    from auto_patch.elevation_per_surface.raster_reach_band import (
        build_raster_reach_band)
    layout = _u_layout(_paved_u(shortcut_role))
    raster = build_raster_reach_band(layout, _u_graph())
    if raster is None:                                     # pragma: no cover
        pytest.skip("raster field could not be built for the fixture")
    got = raster(100.0, 0.0)
    assert got is not None, "T is paved and must be answered"
    return got[1]


def test_raster_band_refuses_a_service_road_paved_shortcut(monkeypatch):
    """The band refuses a service route drawn over its own road pavement.

    TWO independent guards now hold this: ``_domain_geom``'s role set omits
    ``ROLE_SERVICE_ROAD`` (the road is not even in the leg's grid), AND the
    route value comes from the service-excluded spine fields.  Pin it, so a
    future widening of the domain roles cannot quietly re-open the road.
    """
    ceil = _raster_ceiling(ROLE_SERVICE_ROAD, monkeypatch)
    assert ceil > ANCHOR_VALUE + SVC_CLIMB + 1.0, (
        f"band ceiling {ceil:.3f} is at/below the SERVICE-shortcut "
        f"price {ANCHOR_VALUE + SVC_CLIMB:.3f} — reach rode the road")
    assert ceil == pytest.approx(ANCHOR_VALUE + TAXI_CLIMB, abs=1.5)


def test_raster_band_refuses_a_service_route_over_airside_pavement(
        monkeypatch):
    """Same graph, same ``service_spine_pairs``; only the pavement role
    under the shortcut changes — the case the ROLE guard cannot see.

    THIS WAS THE VIOLATOR (strict xfail until 2026-07-29): the old raster
    engine propagated VALUE through the paved grid, an AREA metric, so a
    service route over AIRSIDE pavement (HECA's giant aprons carry service
    routes through them) short-circuited the 700 m taxi route and priced T
    at 101.485 — an 8.7 m UNDER-credit that biases building seats LOW.
    The engine is now route-metric: value on the non-service spine graph,
    grid only for the nearest attachment + local leg.  T sits on the
    valued taxi node, so it prices at the taxi route either way."""
    ceil = _raster_ceiling(ROLE_APRON, monkeypatch)
    assert ceil > ANCHOR_VALUE + SVC_CLIMB + 1.0, (
        f"band ceiling {ceil:.3f} is at/below the SERVICE-shortcut "
        f"price {ANCHOR_VALUE + SVC_CLIMB:.3f} — reach rode the road")
    assert ceil == pytest.approx(ANCHOR_VALUE + TAXI_CLIMB, abs=1.5), (
        "the route metric must price T at the 700 m taxi route, not at any "
        "cheaper path across the apron")
