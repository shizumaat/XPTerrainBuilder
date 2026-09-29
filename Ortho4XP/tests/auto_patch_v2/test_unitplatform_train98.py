"""RULINGS 2026-09-29q (issue #98, lane ``train98``): A CUT CONNECTOR IS A
LINEAR ELEVATED STRUCTURE — it forms no design cluster, emits no pad and
carries no ground; its rail top and floor follow the DECK, never a station
unit; the buildings at each end keep their own platforms.

HECA's precedent: the elevated rail `road_train/concrete_3.obj` (b0 495 m,
b1 1,149 m, both CUT) was its own single-body cluster and minted two flat
pads at the station level — `building13` 87.02-87.49 (cut −12.3 m) and
`building69` 86.65-87.19 (berm +13.45 m) — and its rail top
`metal_strip_2.obj` rode the station unit.
"""
from __future__ import annotations

import dataclasses as _dc
import types

from auto_patch_v2.airport import footprint_connector as FC
from auto_patch_v2.airport.placement_family import plan_clusters
from auto_patch_v2.geom import cluster_outlines

from test_unitplatform_connector import (_Member, _Part, _Plan, _Unit,
                                         _ground, _lat)


def _ringed(p: _Part, base_y: float = 0.0) -> _Part:
    la0, lo0, la1, lo1 = p.box
    p.rings = (((la0, lo0), (la0, lo1), (la1, lo1), (la1, lo0)),)
    p.base_y = base_y
    return p


def _rail_plan() -> _Plan:
    """Terminal A (0-100 m, ground 100) and terminal B (400-500 m, ground
    129) — two pads on different levels — joined by a 300 m deck on piers
    (a plate with a 5 m pier every 60 m)."""
    a = _Member("objects/a.obj", [_ringed(_Part(1, 0, 100, 12.0))])
    b = _Member("objects/b.obj", [_ringed(_Part(2, 400, 500, 12.0))])
    parts = [_ringed(_Part(10, 100, 400, 0.0, -2.99960, -2.99940), 8.2)]
    parts += [_ringed(_Part(11 + i, 100 + 60 * i, 102 + 60 * i, 5.0,
                            -2.99960, -2.99940)) for i in range(6)]
    link = _Member("objects/link.obj", parts)
    contacts = tuple((10, 11 + i) for i in range(6))
    return _Plan((_Unit([a, b, link]),), contacts)


def _stamped():
    plan = _rail_plan()
    v = FC.solid_connectors(plan, _ground(29.0), touch_m=0.5, span_m=200.0,
                            visual_m=0.5, chain_min_height_m=2.5,
                            gap_max_m=20.0, step_max_m=15.0 * 0.33)
    assert [x.solid for x in v] == [False]
    plan.connectors = v
    return plan, FC.cut_pids(v)


def _to_xy(lo: float, la: float) -> tuple[float, float]:
    """``cluster_outlines`` calls the frame as ``to_xy(lon, lat)``."""
    return ((lo + 3.0) * 84_000.0, (la - 41.0) * 111_132.0)


def test_a_cut_connector_forms_no_cluster_and_emits_no_pad():
    """29q at the derivation: no cluster carries the deck, so no pad is
    minted over the span — the ground between the two ends follows the
    ground law — and both end buildings keep their own clusters (their
    own platforms) at their own floors."""
    plan, cut = _stamped()
    counts: dict = {}
    cl = plan_clusters(plan, 0.5, chain_min_height_m=2.5, cut=cut,
                       counts=counts)
    assert counts["cluster_connectors_cut_out"] == 1
    assert counts["cluster_connectors_no_cluster"] == 1
    assert not any("objects/link.obj" in c.members for c in cl)
    assert sorted(m for c in cl for m in c.members) == \
        ["objects/a.obj", "objects/b.obj"]
    pads, _n = cluster_outlines(cl, _to_xy, 0.5)
    assert len(pads) == 2
    from shapely.geometry import Point
    mid = Point(_to_xy(-2.9995, _lat(250)))
    assert not any(poly.buffer(1.0).contains(mid) for _i, _c, poly in pads)
    ends = [Point(_to_xy(-2.9995, _lat(50))),
            Point(_to_xy(-2.9995, _lat(450)))]
    assert all(any(poly.buffer(1.0).contains(e) for _i, _c, poly in pads)
               for e in ends)


def test_a_solid_verdict_still_joins_its_two_ends():
    """The control on the same plan: re-stamped SOLID, the connector is an
    ordinary member and the chain joins A and B through it (§2 unchanged)."""
    plan, _cut = _stamped()
    plan.connectors = (_dc.replace(plan.connectors[0], solid=True),)
    cl = plan_clusters(plan, 0.5, chain_min_height_m=2.5,
                       cut=FC.cut_pids(plan.connectors))
    assert FC.cut_pids(plan.connectors) == frozenset()
    assert any("objects/link.obj" in c.members for c in cl)


def _staged(mi, parts, elevated=True, footless=False):
    raw = [(list(parts),)]
    return types.SimpleNamespace(mi=mi, raw=raw, footless=footless,
                                 elevated=frozenset({0}) if elevated else
                                 frozenset())


def test_the_rail_top_and_the_platform_floor_ride_the_deck():
    """29q at the object stage: an elevated body of the deck's authored
    unit that TOUCHES the deck (ε-contact) or is authored AT the deck's
    level at its edge rides the DECK body; a station roof elsewhere keeps
    the station."""
    plan, cut = _stamped()
    deck_parts = list(plan.units[0].members[2].parts)
    rail = _ringed(_Part(40, 150, 350, 1.0, -2.99958, -2.99942), 8.9)
    floor = _ringed(_Part(41, 400, 420, 0.3, -2.99960, -2.99940), 8.1)
    roof = _ringed(_Part(42, 20, 60, 1.0), 12.0)
    members = list(plan.units[0].members) + [
        _Member("objects/rail_top.obj", [rail]),
        _Member("objects/floor.obj", [floor]),
        _Member("objects/roof.obj", [roof])]
    plan = _dc.replace(plan, units=(_Unit(members),))
    staged = [_staged(2, deck_parts, elevated=False),
              _staged(3, [rail], footless=True),
              _staged(4, [floor], footless=True),
              _staged(5, [roof])]
    station = types.SimpleNamespace(member=0, pids=frozenset({1}))
    deck = types.SimpleNamespace(member=2, pids=frozenset(p.pid for p in deck_parts))
    counts: dict = {}
    got = FC.deck_riders(plan, 0, staged, [station, deck], cut,
                         contacts=((10, 40),), touch_m=0.5, level_tol_m=0.3,
                         counts=counts)
    assert got == {(3, 0): 1, (4, 0): 1}
    assert counts["bodies_ride_cut_connector_deck"] == 2
    # no cut connector, no rider
    assert FC.deck_riders(plan, 0, staged, [station, deck], frozenset(),
                          contacts=((10, 40),), touch_m=0.5) == {}
