"""OWNER RULINGS 2026-10-22h (Q111, #1254; lane lroads): A PUBLIC ROAD
FOLLOWS ITS TERRAIN where it is steeper than the road cap; airside and
service roads keep the cap.

* ``airport/public_road``: which ribbon faces are public (the way's own
  ``highway`` class against ``[road_profile] public_classes``), and which of
  them run over the cap on their own target;
* ``constraints/public_road_release``: on those faces every LONGITUDINAL
  grade row between two released vertices yields to the target's own
  difference; the cross-section, airside vertices and every other pavement's
  vertices keep their law;
* ``pipeline/publication.lifted_caps``: the census reads the same faces as
  lifted.
"""
from __future__ import annotations

import dataclasses as dc

import pytest
from auto_patch_v2.classify.roles import Cell
from auto_patch_v2.law import Law
from auto_patch_v2.model.airport import OsmWay
from auto_patch_v2.model.constraints import Diff, Source
from tests.auto_patch_v2.test_pad_touch import _rect
from tests.auto_patch_v2.test_roads609e import _map

GRADE = 0.16          # the hillside, steeper than the 10 % road cap


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


def _cells(hw_ref: str = "small_roads:-1"):
    return [Cell(9, "runway", "09/27", _rect(-800.0, -422.5, 800.0, -377.5), (),
                 3, "D", "airside", "runway", {}),
            Cell(1, "service_road", hw_ref, _rect(0.0, 92.0, 300.0, 100.0), (),
                 None, None, "groundside", "service_road", {"osm_ribbon": 1.0})]


def _built(law, highway: str):
    airport, pm = _map(law, _cells(), only=[])
    way = OsmWay(-1, "airport_small_roads", ((0.0, 96.0), (300.0, 96.0)), False,
                 {"highway": highway})
    airport = dc.replace(airport, osm_ways=(way,))
    road = next(f for f in pm.faces.values() if f.ref == "small_roads:-1")
    ring = set(pm.ring_vertices(road.ring))
    target = {v: 700.0 + GRADE * pm.vertices[v].xy[0] for v in ring}
    return airport, dc.replace(pm, road_ramp_z=target), road


def test_a_public_road_on_steep_terrain_is_lifted_a_service_road_is_not(law):
    from auto_patch_v2.airport.public_road import public_road_faces, public_road_lifts
    for highway, public in (("residential", True), ("service", False)):
        airport, pm, road = _built(law, highway)
        faces = public_road_faces(pm, law, airport)
        assert (road.id in faces) is public, highway
        lifted = public_road_lifts(pm, law, faces, pm.road_ramp_z)
        assert (road.id in lifted) is public, highway
        if public:
            assert lifted[road.id] == pytest.approx(GRADE, rel=1e-3)
    # on gentle terrain nothing is lifted
    airport, pm, road = _built(law, "residential")
    gentle = {v: 700.0 + 0.04 * pm.vertices[v].xy[0] for v in pm.road_ramp_z}
    assert public_road_lifts(pm, law, public_road_faces(pm, law, airport), gentle) == {}


def test_the_longitudinal_rows_yield_the_cross_section_does_not(law):
    from auto_patch_v2.airport.public_road import public_road_faces, public_road_lifts
    from auto_patch_v2.constraints.public_road_release import (
        RELEASE_SLACK,
        released_vertices,
        terrain_release,
    )
    from auto_patch_v2.pipeline.publication import lifted_caps
    airport, pm, road = _built(law, "residential")
    lifted = public_road_lifts(pm, law, public_road_faces(pm, law, airport), pm.road_ramp_z)
    pm = dc.replace(pm, public_road_lifted=lifted)
    rel = released_vertices(pm, law)
    assert rel
    south = sorted((v for v in rel if pm.vertices[v].xy[1] < 96.0),
                   key=lambda v: pm.vertices[v].xy[0])
    north = sorted((v for v in rel if pm.vertices[v].xy[1] > 96.0),
                   key=lambda v: pm.vertices[v].xy[0])
    a, b = south[0], south[-1]
    c = min(north, key=lambda v: abs(pm.vertices[v].xy[0] - pm.vertices[a].xy[0]))
    d_ab = abs(pm.vertices[a].xy[0] - pm.vertices[b].xy[0])
    d_ac = 8.0
    lon = Diff(a, b, 0.10, d_ab, Source("roads", "common.roles longitudinal (2026-08-03)", ()))
    cross = Diff(a, c, 0.02, d_ac, Source("roads", "road_cross_section (2026-08-25g)", ()))
    out, n = terrain_release([lon, cross], pm, law)
    assert n == 1
    t = pm.road_ramp_z
    assert out[0].cap * out[0].d == pytest.approx(abs(t[a] - t[b]) * (1 + RELEASE_SLACK))
    assert out[1] == cross
    # a row is never tightened
    loose = dc.replace(lon, cap=0.5)
    assert terrain_release([loose], pm, law)[0] == [loose]
    # the census lifts the same face
    assert road.id in lifted_caps(pm)


def test_a_service_road_releases_nothing(law):
    from auto_patch_v2.constraints.public_road_release import terrain_release
    _airport, pm, road = _built(law, "service")
    ring = list(pm.ring_vertices(road.ring))
    row = Diff(ring[0], ring[1], 0.10, 1.0, Source("roads", "x", ()))
    assert terrain_release([row], pm, law) == ([row], 0)


# ── RULINGS 2026-10-27f / 27s: the junction joint ────────────────────────

def test_a_junction_mouth_between_two_public_roads_is_the_streets_grade(law):
    """27f: two routes within one ribbon's width of two DIFFERENT public
    roads (a sized joint's frames carry the road as a fourth field) are the
    side street's longitudinal grade; one carriageway keeps 2 %."""
    from auto_patch_v2.constraints.roads import road_pair_reading
    fa, fb = (1, 10.0, 0.0, "osm:-1"), (2, 50.0, 0.0, "osm:-2")
    assert road_pair_reading(0.10, 0.02, 45.0, fa, fb, 4.0, 6.0) == (pytest.approx(0.40), False)
    same = (2, 50.0, 0.0, "osm:-1")
    assert road_pair_reading(0.10, 0.02, 45.0, fa, same, 4.0, 6.0) == (pytest.approx(0.08), True)
    bare = (2, 50.0, 0.0)
    assert road_pair_reading(0.10, 0.02, 45.0, fa, bare, 4.0, 6.0) == (pytest.approx(0.08), True)


@pytest.mark.parametrize("z0,g0,line0,g1", [
    (153.0, 0.11, 155.3, 0.15),       # LGAV -1276 into -1190
    (153.0, 0.0, 155.3, 0.18),        # a side street climbing off a level kerb
    (155.3, 0.0, 153.0, -0.18),       # ... and descending
    (100.0, 0.0, 100.5, 0.02),        # within the free change: an offset only
])
def test_the_joint_transition_keeps_the_town_street_law(law, z0, g0, line0, g1):
    """27s: the street leaves the kerb within the free change, then changes
    grade at no more than 1 % per 3 m, and lands on its own line in value
    and grade, never steeper than the ceiling."""
    import numpy as np
    from auto_patch_v2.airport.road_joint import transition
    c = law.tables.common
    free = c.road_joint_free_grade_change
    rate = c.vertical_curve_k_grade_unit / c.road_joint_k_m_per_pct
    assert (free, c.road_joint_k_m_per_pct) == (0.08, 3.0)
    ceiling = law.tables.emit.road_profile.cap_ceiling
    u_end, prof = transition(z0, g0, line0, g1, free, rate, ceiling)
    h = 0.05
    u = np.arange(0.0, u_end + h / 2, h)
    z = np.array([prof(x) for x in u])
    g = np.diff(z) / h
    assert z[0] == pytest.approx(z0)
    assert prof(u_end) == pytest.approx(line0 + g1 * u_end, abs=1e-6)
    assert abs(g[0] - g0) <= free + rate * h + 1e-9
    assert np.abs(np.diff(g)).max() / h <= rate * (1 + 1e-6)
    assert abs(g[-1] - g1) <= rate * h + 1e-9
    assert np.abs(g).max() <= ceiling + 1e-9
