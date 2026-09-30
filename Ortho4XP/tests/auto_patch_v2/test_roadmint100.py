"""#100 v3 — THE ROAD-FACE MINT, WIDENED (owner RULINGS 2026-09-30b Q-100b,
spec-author 2026-09-30e (1)-(6); lane roadmint100).

Every mapped at-grade road inside the patch gets its ribbon face from the
one road-face mint (``classify/roles.mint_osm_ribbons``); inside a zone
band the band is cut by the ribbon with NO stand-off (the kerb is shared,
the band leads); the ribbons are noded AFTER the airside is frozen, so
the airside is byte-identical with and without them.
"""
from __future__ import annotations

import dataclasses as _dc

import pytest
from shapely.geometry import Polygon

from auto_patch_v2.classify import classify, load_rules
from auto_patch_v2.classify.roles import bridge_gaps, is_osm_ribbon
from auto_patch_v2.law import Law
from auto_patch_v2.law.tables import rolled_on_roles
from auto_patch_v2.model.airport import Building, OsmWay
from auto_patch_v2.planar.build import build as planar_build

from test_classify import _rect, _synthetic


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("SYNT")


def _way(wid, pts, **tags):
    return OsmWay(wid, "airport_small_roads", tuple(pts), False, dict(tags))


#: a road along the runway's south side at y = -40: inside the runway's
#: zone band (30 m wide along y = 0, code 2: zone 2 to 40 m off the edge), clear of
#: every pavement page and of the 1206 truck route at x = 300
SOUTH = ((600.0, -40.0), (900.0, -40.0))


def _with(*ways, buildings=()):
    a = _synthetic(gate=True, island=False)
    return _dc.replace(a, osm_ways=tuple(ways),
                       buildings=tuple(a.buildings) + tuple(buildings))


def _ribbons(cl):
    return [c for c in cl.cells if is_osm_ribbon(c)]


def test_a_tertiary_way_with_no_1206_route_mints_a_ribbon(law):
    cl = classify(_with(_way(-3, SOUTH, highway="tertiary")), law)
    rib = _ribbons(cl)
    assert [c.ref for c in rib] == ["small_roads:-3"]       # 30e (6) feed ref
    assert rib[0].side == "groundside" and rib[0].role == "service_road"
    area = Polygon(rib[0].ring, rib[0].holes).area
    hw = float(law.tables.emit.road_profile.lane_width_m)
    assert area == pytest.approx(300.0 * 2 * hw, rel=0.02)
    assert cl.stats["osm_ribbons"] == 1


@pytest.mark.parametrize("hw", ["footway", "path", "cycleway", "steps",
                                "pedestrian", "track"])
def test_a_footway_or_track_mints_nothing(law, hw):
    assert _ribbons(classify(_with(_way(-4, SOUTH, highway=hw)), law)) == []


def test_a_way_on_a_1206_route_is_deduped(law):
    # the synthetic truck route runs x = 300 from y = -200 to 200
    on_route = _way(-5, ((302.0, -150.0), (302.0, -40.0)), highway="service")
    assert _ribbons(classify(_with(on_route), law)) == []


def test_the_gap_bridge_joins_219_m_and_not_300_m():
    gap = load_rules().osm_roads.road_gap_bridge_m
    assert gap == 250.0
    assert bridge_gaps([(0.0, 100.0), (319.0, 500.0)], gap) == [(0.0, 500.0)]
    assert bridge_gaps([(0.0, 100.0), (400.0, 500.0)], gap) == \
        [(0.0, 100.0), (400.0, 500.0)]


def test_no_ribbon_inside_a_pad(law):
    pad = Building("shed", _rect(700.0, -52.0, 780.0, -30.0), (), "osm", 6.0, 1)
    base = classify(_with(buildings=(pad,)), law)
    pads = [Polygon(c.ring, c.holes) for c in base.cells if c.role == "building"
            and c.ref.endswith("shed")]
    cl = classify(_with(_way(-3, SOUTH, highway="tertiary"), buildings=(pad,)), law)
    rib = _ribbons(cl)
    assert rib
    for p in pads:
        for c in rib:
            assert Polygon(c.ring, c.holes).intersection(p).area < 1e-6


def _airside_rings(pm, law):
    air = rolled_on_roles(law)
    return sorted((f.role, f.ref, tuple(pm.vertices[v].xy
                                        for v in pm.ring_vertices(f.ring)))
                  for f in pm.faces.values() if f.role in air)


def test_the_airside_is_unchanged_by_a_ribbon_and_the_kerb_is_shared(law):
    a0 = _with()
    a1 = _with(_way(-3, SOUTH, highway="tertiary"))
    pm0, _ = planar_build(a0, classify(a0, law), law)
    pm1, _ = planar_build(a1, classify(a1, law), law)
    assert _airside_rings(pm1, law) == _airside_rings(pm0, law)
    rib = [f for f in pm1.faces.values() if f.role == "service_road"
           and f.ref.startswith("small_roads:")]
    assert rib
    band = set()
    for f in pm1.faces.values():
        if f.role == "graded_strip":            # the ribbon is the band's HOLE
            for cyc in (f.ring, *f.holes):
                band.update(pm1.ring_vertices(cyc))
    kerb = set()
    for f in rib:
        kerb.update(v for v in pm1.ring_vertices(f.ring) if v in band)
    # IN-BAND: the ribbon shares its kerb vertices with the band (30e (4)),
    # and those are exactly the model's band-kerb set
    assert len(kerb) >= 4
    assert kerb <= pm1.band_kerb_vertices()
