"""RULINGS 2026-09-29q as narrowed and completed by 29v (issue #98, lane
``train98``): a NOT-WALLED cut connector is a LINEAR ELEVATED STRUCTURE — it
forms no design cluster, emits no pad and carries no ground; a WALLED cut
connector keeps its cluster; the structure is seated ONCE (its legs share
one datum, where they join); its riders ride the deck by the §16c contact
rule, never by the carrier search; the end buildings keep their platforms.

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
from auto_patch_v2.airport import footprint_unit as FU
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
                       linear=FC.linear_pids(plan.connectors), counts=counts)
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


def test_a_walled_cut_connector_keeps_its_cluster():
    """29v (1): a WALLED cut connector (cut by its end step alone — HECA's
    `Hangar/T3_60` b0) is a building body and keeps its own cluster."""
    plan, _cut = _stamped()
    plan.connectors = (_dc.replace(plan.connectors[0], walled=True),)
    cut = FC.cut_pids(plan.connectors)
    lin = FC.linear_pids(plan.connectors)
    assert cut and not lin
    counts: dict = {}
    cl = plan_clusters(plan, 0.5, chain_min_height_m=2.5, cut=cut,
                       linear=lin, counts=counts)
    assert any("objects/link.obj" in c.members for c in cl)
    assert counts["cluster_connectors_no_cluster"] == 0
    # ...and it still links nothing: A and B stay apart
    assert not any({"objects/a.obj", "objects/b.obj"} <= set(c.members)
                   for c in cl)


def _two_leg_plan():
    """A (0-100 m) and B (400-500 m) joined by ONE member split by a
    station at 250 m into two legs: leg 1 plate 100-240 m on piers at
    100 and 230 m, leg 2 plate 260-400 m on piers at 260 and 398 m.
    Ground: 110 at A's end, 120 around the station, 90 at B's end."""
    a = _Member("objects/a.obj", [_ringed(_Part(1, 0, 100, 12.0))])
    b = _Member("objects/b.obj", [_ringed(_Part(2, 400, 500, 12.0))])
    lo = (-2.99960, -2.99940)
    parts = [_ringed(_Part(10, 100, 240, 0.0, *lo), 8.2),
             _ringed(_Part(11, 100, 102, 5.0, *lo)),
             _ringed(_Part(12, 230, 232, 5.0, *lo)),
             _ringed(_Part(20, 260, 400, 0.0, *lo), 8.2),
             _ringed(_Part(21, 260, 262, 5.0, *lo)),
             _ringed(_Part(22, 398, 400, 5.0, *lo))]
    link = _Member("objects/rail.obj", parts)
    plan = _Plan((_Unit([a, b, link]),), ((10, 11), (10, 12), (20, 21),
                                          (20, 22)))

    def ground(la, _lo):
        m = (la - 41.0) * 111_132.0
        return 110.0 if m < 150 else (120.0 if m < 350 else 90.0)

    def box(m0, m1):
        return ((_lat(m0), lo[0], _lat(m1), lo[1]),)

    def leg(pids, a0, a1, b0, b1):
        return FC.ConnectorVerdict(
            pids=pids, resource="objects/rail.obj", span_m=140.0,
            end_a="fu:0/c0", end_b="fu:0/c1", step_m=10.0,
            walled_gap_m=130.0, walled=False, deck=False, solid=False,
            own_a=box(a0, a1), own_b=box(b0, b1))
    plan.connectors = (leg((10, 11, 12), 99, 103, 229, 233),
                       leg((20, 21, 22), 259, 263, 397, 401))
    return plan, ground


def test_a_two_leg_linear_connector_has_one_seat():
    """29v (2): the legs share ONE datum — the contact where they join
    (the station, 120) — never each leg's own low end (110 and 90)."""
    plan, ground = _two_leg_plan()
    counts: dict = {}
    pw, _s = FU.plan_wide_seats(plan, ground, (), 0.5, 0.0, counts,
                                100.0, 2.5)
    s1, s2 = pw[10][5], pw[20][5]
    assert abs(s1[1] - 120.0) < 1e-6 and abs(s2[1] - 120.0) < 1e-6
    assert s1[0] == s2[0] and s1[0].endswith("~joint")
    assert pw[11][5] == s1 and pw[22][5] == s2
    assert counts["connector_legs_one_seat"] == 2
    # one leg alone keeps its low end (§16g (7) (2))
    plan.connectors = plan.connectors[:1]
    pw, _s = FU.plan_wide_seats(plan, ground, (), 0.5, 0.0, {}, 100.0, 2.5)
    assert abs(pw[10][5][1] - 110.0) < 1e-6


def _staged(mi, parts, elevated=True, footless=False):
    raw = [(list(parts),)]
    return types.SimpleNamespace(mi=mi, raw=raw, footless=footless,
                                 elevated=frozenset({0}) if elevated else
                                 frozenset())


def test_riders_by_the_contact_rule_and_the_station_floor_case():
    """29v (2): the rail top rides the deck by its ε-CONTACT; its own
    member's other body standing over the deck rides with it (one rigid
    member — HECA's `metal_strip_2` b1, which the carrier search had put
    on a station building); a station FLOOR at deck level with no contact
    to the deck stays with the building (the §16c contact rule decides);
    a roof elsewhere is untouched."""
    plan, cut = _stamped()
    deck_parts = list(plan.units[0].members[2].parts)
    rail = _ringed(_Part(40, 150, 350, 1.0, -2.99958, -2.99942), 8.9)
    beam = _ringed(_Part(43, 200, 220, 1.0, -2.99958, -2.99942), 5.4)
    floor = _ringed(_Part(41, 400, 420, 0.3, -2.99960, -2.99940), 8.1)
    roof = _ringed(_Part(42, 20, 60, 1.0), 12.0)
    members = list(plan.units[0].members) + [
        _Member("objects/rail_top.obj", [rail, beam]),
        _Member("objects/floor.obj", [floor]),
        _Member("objects/roof.obj", [roof])]
    plan = _dc.replace(plan, units=(_Unit(members),))
    rail_st = types.SimpleNamespace(mi=3, raw=[([rail],), ([beam],)],
                                    footless=True, elevated=frozenset())
    staged = [_staged(2, deck_parts, elevated=False), rail_st,
              _staged(4, [floor], footless=True), _staged(5, [roof])]
    station = types.SimpleNamespace(member=0, pids=frozenset({1}))
    deck = types.SimpleNamespace(member=2,
                                 pids=frozenset(p.pid for p in deck_parts))
    counts: dict = {}
    got = FC.deck_riders(plan, 0, staged, [station, deck], cut,
                         contacts=((10, 40),), counts=counts)
    assert got == {(3, 0): 1, (3, 1): 1}
    assert counts["bodies_ride_deck_as_member_sibling"] == 1
    # the floor WITH a contact edge to the deck is part of the structure
    got = FC.deck_riders(plan, 0, staged, [station, deck], cut,
                         contacts=((10, 40), (10, 41)))
    assert got[(4, 0)] == 1
    # no linear connector, no rider
    assert FC.deck_riders(plan, 0, staged, [station, deck], frozenset(),
                          contacts=((10, 40),)) == {}
