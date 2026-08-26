"""THE GAP-BRIDGING SPINE — twins for §1 of
docs/specs/heca-apron-round2-spec.md.

The motivating measurement: HECA's apt.dat taxi-route graph has a FEED
GAP — taxiway J ends at node 462, the next route starts at node 470
254 m north, no 1202 edge between them and no OSM way there.  Both ends
sit on ONE continuous piece of apron pavement, but the global slice cuts
along CENTERLINES, so the emitted apron carries a 215 x 430 m region
with ZERO interior vertices.

Spec §1.4's twin, verbatim: a synthetic two-route apron with a 250 m gap
gives one bridge, slice vertices in the void and priced chords; a gap
over 300 m gives no bridge; non-apron pavement between gives no bridge.

Headless, no network, no X-Plane install.
"""
from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest
from shapely.geometry import LineString, Polygon

_ROOT = Path(__file__).resolve().parents[1]
for _p in (str(_ROOT / "src"), str(_ROOT), str(_ROOT / "tools")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from auto_patch import gap_spine_bridge as GSB          # noqa: E402
from auto_patch.apt_dat_reader import TaxiCenterline    # noqa: E402


def _cl(pts, size="C", service=False):
    return TaxiCenterline(line=LineString(pts),
                          seg_sizes=[size] * (len(pts) - 1),
                          is_service=service, name="route")


def _apron(width=400.0, y0=-200.0, y1=400.0):
    """One continuous rectangle of apron pavement spanning both routes
    and the gap between them."""
    h = width / 2.0
    return Polygon([(-h, y0), (h, y0), (h, y1), (-h, y1), (-h, y0)])


# The HECA geometry, to scale: route A runs up to y=0, route B starts at
# y=250 — a 250 m feed gap on one apron.
_ROUTE_A = [(0.0, -150.0), (0.0, 0.0)]
_ROUTE_B = [(0.0, 250.0), (0.0, 400.0)]


# ═════════════════════════════════════════════════════════════════════
# §1.4 twin 1 — a 250 m gap gives ONE bridge
# ═════════════════════════════════════════════════════════════════════

def test_a_250m_gap_across_one_apron_gives_one_bridge():
    plan = GSB.plan_gap_spine_bridges(
        [_cl(_ROUTE_A), _cl(_ROUTE_B)], _apron(), max_m=300.0)
    assert len(plan) == 1
    a, b = sorted([plan[0]["a"], plan[0]["b"]], key=lambda p: p[1])
    assert a == (0.0, 0.0)
    assert b == (0.0, 250.0)
    assert plan[0]["dist_m"] == pytest.approx(250.0)


def test_a_gap_over_the_reach_gives_no_bridge():
    """``GAP_SPINE_MAX_M`` is a reach, not a hint: 250 m is inside 300,
    350 m is not."""
    far_b = [(0.0, 350.0), (0.0, 500.0)]
    plan = GSB.plan_gap_spine_bridges(
        [_cl(_ROUTE_A), _cl(far_b)], _apron(y1=600.0), max_m=300.0)
    assert plan == []


def test_non_apron_pavement_between_gives_no_bridge():
    """Visibility is APRON-ONLY: with the pavement split into two pieces
    across the gap (the runway/terminal difference the pipeline applies,
    or simply a gap in the pavement), the chord is not walkable and no
    bridge is synthesized."""
    south = Polygon([(-200.0, -200.0), (200.0, -200.0), (200.0, 20.0),
                     (-200.0, 20.0), (-200.0, -200.0)])
    north = Polygon([(-200.0, 230.0), (200.0, 230.0), (200.0, 400.0),
                     (-200.0, 400.0), (-200.0, 230.0)])
    from shapely.geometry import MultiPolygon
    plan = GSB.plan_gap_spine_bridges(
        [_cl(_ROUTE_A), _cl(_ROUTE_B)], MultiPolygon([south, north]),
        max_m=300.0)
    assert plan == []


def test_two_ends_already_connected_are_not_a_feed_gap():
    """The spec's word is UNCONNECTED.  Two ends of a network that
    already joins them through a third route are not a feed gap however
    close they are."""
    joint = [(0.0, 0.0), (60.0, 125.0), (0.0, 250.0)]
    plan = GSB.plan_gap_spine_bridges(
        [_cl(_ROUTE_A), _cl(_ROUTE_B), _cl(joint)], _apron(),
        max_m=300.0)
    assert plan == []


def test_a_routes_own_two_ends_never_bridge_to_each_other():
    plan = GSB.plan_gap_spine_bridges(
        [_cl([(0.0, 0.0), (10.0, 0.0), (0.0, 200.0)])], _apron(),
        max_m=300.0)
    assert plan == []


def test_service_routes_are_not_taxi_route_ends():
    """A truck route is not an aircraft taxi spine (the ``is_service``
    law the rest of the engine already runs on)."""
    plan = GSB.plan_gap_spine_bridges(
        [_cl(_ROUTE_A), _cl(_ROUTE_B, service=True)], _apron(),
        max_m=300.0)
    assert plan == []


# ═════════════════════════════════════════════════════════════════════
# Determinism: the tie rule is the spec's (lower node id)
# ═════════════════════════════════════════════════════════════════════

class _Node:
    def __init__(self, lat, lon):
        self.lat = lat
        self.lon = lon


class _Airport:
    def __init__(self, nodes):
        self.taxi_nodes = nodes


def _to_m(lon, lat):
    """A trivial projection for the twin: lon/lat ARE metres."""
    return (float(lon), float(lat))


def test_the_ends_are_named_by_their_apt_dat_node_ids():
    """The tie rule the spec states ('lower node id') is the rule that
    runs, and the log can name node 462 and node 470."""
    apt = _Airport({462: _Node(0.0, 0.0), 470: _Node(250.0, 0.0)})
    nodes = GSB._apt_node_ids(apt, _to_m)
    plan = GSB.plan_gap_spine_bridges(
        [_cl(_ROUTE_A), _cl(_ROUTE_B)], _apron(), max_m=300.0,
        apt_nodes=nodes)
    assert len(plan) == 1
    assert {plan[0]["node_a"], plan[0]["node_b"]} == {462, 470}
    # ordered: the LOWER node id is the ``a`` end
    assert plan[0]["node_a"] == 462


def test_an_end_with_no_apt_dat_node_still_bridges_deterministically():
    plan_a = GSB.plan_gap_spine_bridges(
        [_cl(_ROUTE_A), _cl(_ROUTE_B)], _apron(), max_m=300.0)
    plan_b = GSB.plan_gap_spine_bridges(
        [_cl(_ROUTE_B), _cl(_ROUTE_A)], _apron(), max_m=300.0)
    assert plan_a[0]["a"] == plan_b[0]["a"]
    assert plan_a[0]["b"] == plan_b[0]["b"]


def test_each_end_carries_at_most_one_bridge():
    """Three routes meeting one void: the greedy nearest-first pass
    consumes each end once, so no end fans out."""
    c = [(0.0, 250.0), (0.0, 400.0)]
    d = [(120.0, 260.0), (200.0, 400.0)]
    plan = GSB.plan_gap_spine_bridges(
        [_cl(_ROUTE_A), _cl(c), _cl(d)], _apron(width=600.0),
        max_m=300.0)
    ends = [p["a"] for p in plan] + [p["b"] for p in plan]
    assert len(ends) == len(set(ends))


# ═════════════════════════════════════════════════════════════════════
# The bridge is a FIRST-CLASS centerline (§1.2), and the flag (§1.3)
# ═════════════════════════════════════════════════════════════════════

class _Layout:
    def __init__(self, centerlines):
        self.apt_taxi_centerlines = list(centerlines)

    def m_to_ll(self, x, y):
        return (30.12 + y / 111_320.0, 31.40 + x / 96_000.0)


def test_the_bridge_is_appended_as_a_first_class_centerline():
    """It enters ``layout.apt_taxi_centerlines`` BEFORE the slice, so it
    cuts interior vertices, ``centerline_specs`` gives it a profile and
    ``spine_nodes_m`` puts its vertices in the chord population."""
    layout = _Layout([_cl(_ROUTE_A), _cl(_ROUTE_B)])
    recs = GSB.synthesize_gap_spine_bridges(layout, _apron())
    assert len(recs) == 1
    assert len(layout.apt_taxi_centerlines) == 3
    bridge = layout.apt_taxi_centerlines[-1]
    assert bridge.name == "gap_spine_bridge"
    assert bridge.is_service is False
    assert bridge.route_line is None          # it IS its own route
    assert len(bridge.seg_sizes) == len(bridge.line.coords) - 1
    assert bridge.seg_sizes == ["C"]          # inherited, never invented
    assert bridge.line.length == pytest.approx(250.0)


def test_the_provenance_is_published_for_the_sidecar():
    layout = _Layout([_cl(_ROUTE_A), _cl(_ROUTE_B)])
    GSB.synthesize_gap_spine_bridges(layout, _apron())
    recs = layout.gap_spine_bridges
    assert recs[0]["dist_m"] == pytest.approx(250.0)
    assert "a_ll" in recs[0] and "b_ll" in recs[0]


def test_the_profile_reader_gives_the_bridge_its_own_route_chain():
    """§1.2's 'gets a profile': ``centerline_specs`` mints one spec per
    centerline, and a bridge with ``route_line=None`` is its own route
    chain (no parent to inherit an arc frame from)."""
    from auto_patch import grade_graph as GG
    layout = _Layout([_cl(_ROUTE_A), _cl(_ROUTE_B)])
    GSB.synthesize_gap_spine_bridges(layout, _apron())
    specs = GG._centerline_specs_uncached(layout)
    assert len(specs) == 3
    pts, caps, is_svc, rkey, rpts = specs[-1]
    assert pts == [(0.0, 0.0), (0.0, 250.0)]
    assert is_svc is False
    assert rkey[0] == "self"
    assert len(caps) == 1 and caps[0] > 0.0


def test_the_flag_defaults_on_and_off_is_byte_identical():
    import auto_patch.config as cfg
    assert cfg.GAP_SPINE_BRIDGE_ENABLED is True
    assert cfg.GAP_SPINE_MAX_M == 300.0
    import os
    os.environ["O4_GAP_SPINE_BRIDGE"] = "0"
    try:
        importlib.reload(cfg)
        assert cfg.GAP_SPINE_BRIDGE_ENABLED is False
        layout = _Layout([_cl(_ROUTE_A), _cl(_ROUTE_B)])
        before = list(layout.apt_taxi_centerlines)
        assert GSB.synthesize_gap_spine_bridges(layout, _apron()) == []
        assert layout.apt_taxi_centerlines == before
        assert not hasattr(layout, "gap_spine_bridges")
    finally:
        os.environ.pop("O4_GAP_SPINE_BRIDGE", None)
        importlib.reload(cfg)


def test_the_visibility_predicate_is_the_shared_one():
    """'One notion, never a third': the reachability test IS
    ``grade_graph._visibility_predicate``."""
    import inspect
    src = inspect.getsource(GSB._visibility_regions)
    assert "_visibility_predicate" in src
    from auto_patch import grade_graph as GG
    assert callable(GG._visibility_predicate)
