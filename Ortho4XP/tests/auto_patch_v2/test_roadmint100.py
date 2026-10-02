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


# ── THE ROAD-EXIT LAW (owner RULINGS 2026-09-29y / 30z (1) / 10-02v (1);
# lane roadmint100b, issue #100): a ribbon leaving the patch runs on until
# the road cap's profile from the patch's level meets the terrain ─────────
from shapely.geometry import LineString as _LS

from auto_patch_v2.classify.roles import exit_reach


class _ShelfDem:
    """Flat at 100 m inside |x| <= 950 (the patch), a +5 m shelf beyond."""
    provenance = {"base": "synthetic"}

    def __init__(self, step=5.0, edge=950.0):
        self.step, self.edge = step, edge

    def z(self, x: float, y: float) -> float:
        return 100.0 + (self.step if x > self.edge else 0.0)

    def bounds(self):
        return (-5000.0, -5000.0, 5000.0, 5000.0)


def test_exit_reach_runs_to_where_the_cap_profile_meets_a_shelf():
    line = _LS([(600.0, -40.0), (1400.0, -40.0)])
    airside = Polygon(_rect(0.0, -15.0, 900.0, 15.0))
    cap = 0.08
    a, b = exit_reach(line, 0.0, 350.0, _ShelfDem(5.0), airside, cap, 2.0, 8.0)
    assert a == 0.0                                  # the way starts in the patch
    # beyond x = 950 the DEM is 5 m up: the 8 % profile from the mouth's
    # level (100 m) needs 62.5 m past the shelf edge; the mouth was at
    # s = 350 (x = 950), so the reach is 62.5 m + one station
    assert b == pytest.approx(350.0 + 62.5 + 2.0, abs=2.0)
    # a flat terrain beyond the patch edge: the first station meets the
    # profile, plus the one station that puts the last vertex on the DEM
    _a, b_flat = exit_reach(line, 0.0, 350.0, _ShelfDem(0.0), airside, cap, 2.0, 8.0)
    assert b_flat == pytest.approx(354.0, abs=1e-6)
    # no DEM: the span is what it was
    assert exit_reach(line, 0.0, 350.0, None, airside, cap, 2.0, 8.0) == (0.0, 350.0)


def test_a_ribbon_leaving_the_patch_onto_a_shelf_reaches_the_terrain(law):
    """The minted ribbon's far end stands past the shelf's reach (so its
    last ring vertex is ON the terrain); a way far from the patch mints
    nothing (the brief's 'a road far from the patch is untouched')."""
    far = ((600.0, -40.0), (1400.0, -40.0))
    # the synthetic's zone-2 envelopes reach x = 1100 and its airside
    # x = 1060: the shelf starts past both, inside the hold window, so the mouth reads 100 m
    shelf = _ShelfDem(5.0, edge=1105.0)
    a = _dc.replace(_with(_way(-3, far, highway="tertiary")), dem=shelf)
    cl = classify(a, law)
    rib = _ribbons(cl)
    assert [c.ref for c in rib] == ["small_roads:-3"]
    xmax = max(x for x, _y in rib[0].ring)
    cap = float(law.tables.common.road_max_grade)
    assert xmax >= 1105.0 + 5.0 / cap
    assert xmax <= 1105.0 + 5.0 / cap + 12.0
    off = _dc.replace(_with(_way(-9, ((600.0, -3000.0), (1400.0, -3000.0)),
                                highway="tertiary")), dem=shelf)
    assert _ribbons(classify(off, law)) == []


def test_a_band_is_not_cut_back_from_a_ribbon(law):
    """13ar / 30e (4): the zone band shares the ribbon's kerb (no 0.6 m
    stand-off strip), while a 1206 route corridor keeps its cut-back."""
    from auto_patch_v2.planar.zones import zone_regions
    a1 = _with(_way(-3, SOUTH, highway="tertiary"))
    cl = classify(a1, law)
    rib = _ribbons(cl)[0]
    zones = zone_regions(tuple(cl.cells), law)
    ribbon = Polygon(rib.ring, rib.holes)
    touching = [z for z in zones if z.zone == 2 and
                z.polygon.distance(ribbon) < 1e-6]
    assert touching, "the zone-2 band abuts the ribbon with no stand-off"
    routes = [c for c in cl.cells if c.role == "service_road" and not is_osm_ribbon(c)]
    assert routes
    corridor = Polygon(routes[0].ring, routes[0].holes)
    cut = float(law.tables.zones.adjacent_ground.groundside_cutback_m)
    assert all(z.polygon.distance(corridor) >= cut - 1e-6 for z in zones)
