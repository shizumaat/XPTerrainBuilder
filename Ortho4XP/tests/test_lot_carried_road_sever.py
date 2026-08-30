"""THE SCOPED SEVER — owner ruling 2026-08-30, HECA round 6 item 3.

"Sever ONLY where an OSM service road shares vertices with the
groundside ring at 11-dp identity (the road is carried by the lot); the
severed corridor becomes a road under the free-road ramp law.  No global
evidence sweep."  §H3 ``ROAD_EVIDENCE_SEVER`` stays REFUTED (measured
+61 HECA / +37 SPJC / +435 LEMD, IoU 0.8221 against 0.90) and this pass
must never become it: the trigger here is a decidable IDENTITY, and a
lot that merely has roads near it is untouched.

Site: HECA way -13192 shares 30.114178800,31.404126000 with ring -12831
(groundside 2836), which is why 30.1118886,31.4064793 emitted as lot 7 m
below apron 585 instead of as a road ramping to 30.1123727,31.4059687.

The twins are a single-variable pair on the TRIGGER: the same lot, the
same road, differing only in whether the road's node is a vertex of the
lot's ring.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

# ``pipeline`` first: junction_repair <-> elevation is an import cycle.
import auto_patch.pipeline as _PIPELINE  # noqa: E402,F401
from auto_patch import groundside as G  # noqa: E402
from auto_patch.constant_dem import ConstantDEM  # noqa: E402
from auto_patch.layout import (  # noqa: E402
    BuiltShape,
    PavementLayout,
    ROLE_GROUNDSIDE_PAVEMENT,
    ROLE_SERVICE_ROAD,
)

LAT, LON = 30.0, 31.0


class _Network:
    """The published ``layout.airport_road_network`` surface this pass
    reads: ``nodes`` id -> (lat, lon), ``ways`` (id, node ids, tags)."""

    def __init__(self, nodes, ways, widths=None):
        self.nodes = nodes
        self.ways = ways
        self.widths = widths or {}


def _layout(shared: bool):
    """A square lot with a service road running through it.

    ``shared=True`` puts the road's first node ON the lot ring at
    identity (the ruling's trigger); ``shared=False`` moves the ring
    corner a few metres so no vertex is shared — the road is otherwise
    the SAME road, in the same place, over the same lot."""
    layout = PavementLayout(icao="TEST", anchor=(LAT, LON), shapes=[])
    # A 120 m square lot, corner at the local origin.
    corners_m = [(0.0, 0.0), (120.0, 0.0), (120.0, 120.0), (0.0, 120.0)]
    road_ll = [layout.m_to_ll(10.0, 60.0), layout.m_to_ll(110.0, 60.0)]
    if shared:
        # The lot ring carries the road's first node verbatim — the way
        # a lot built AROUND a road does.
        corners_m.insert(1, layout.ll_to_m(*road_ll[0]))
    from shapely.geometry import Polygon
    lot = BuiltShape(polygon=Polygon(corners_m),
                     role=ROLE_GROUNDSIDE_PAVEMENT, ref="groundside",
                     node_altitudes=[97.0] * (len(corners_m) + 1))
    layout.shapes = [lot]
    layout.airport_road_network = _Network(
        nodes={1: road_ll[0], 2: road_ll[1]},
        ways=[(-13192, [1, 2], {"highway": "service"})],
    )
    return layout


def _dem():
    return ConstantDEM(97.0, lat=int(LAT), lon=int(LON))


def test_a_shared_ring_vertex_severs_the_corridor():
    """THE TRIGGER FIRES: the corridor leaves the lot as a
    ``service_road`` and the lot is cut back behind it."""
    layout = _layout(shared=True)
    lot_area_before = layout.shapes[0].polygon.area
    n = G.sever_lot_carried_service_roads(layout, _dem(), int(LAT), int(LON))
    assert n >= 1
    roads = [s for s in layout.shapes if s.role == ROLE_SERVICE_ROAD]
    assert roads, "the severed corridor must be a service_road"
    assert all(s.ref == "lot_carried_road" for s in roads)
    lots = [s for s in layout.shapes
            if s.role == ROLE_GROUNDSIDE_PAVEMENT]
    assert lots, "the lot BODY survives — the sever takes the corridor"
    assert lots[0].polygon.area < lot_area_before - 100.0, (
        "the lot did not yield the ground the road now owns")


def test_no_shared_vertex_is_a_no_op_even_with_the_road_right_there():
    """THE SINGLE VARIABLE.  Same lot, same road, same overlap — only
    the shared vertex is gone, and nothing is severed.  This is what
    keeps the pass off §H3's refuted ground: proximity is not the
    trigger, identity is."""
    layout = _layout(shared=False)
    before = [(s.role, s.polygon.area) for s in layout.shapes]
    n = G.sever_lot_carried_service_roads(layout, _dem(), int(LAT), int(LON))
    assert n == 0
    assert [(s.role, s.polygon.area) for s in layout.shapes] == before


def test_a_tunnelled_way_severs_nothing():
    """The corridor law's own tunnel rule, not a second copy of it: a
    bore under a lot is not surface road pavement."""
    layout = _layout(shared=True)
    way_id, refs, tags = layout.airport_road_network.ways[0]
    layout.airport_road_network.ways = [
        (way_id, refs, {**tags, "tunnel": "yes"})]
    assert G.sever_lot_carried_service_roads(
        layout, _dem(), int(LAT), int(LON)) == 0


def test_a_non_service_highway_is_not_this_ruling():
    """The ruling names SERVICE roads.  A trunk road sharing a vertex is
    a different question and this pass does not answer it."""
    layout = _layout(shared=True)
    way_id, refs, _tags = layout.airport_road_network.ways[0]
    layout.airport_road_network.ways = [
        (way_id, refs, {"highway": "trunk"})]
    assert G.sever_lot_carried_service_roads(
        layout, _dem(), int(LAT), int(LON)) == 0
