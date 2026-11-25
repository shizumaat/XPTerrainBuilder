"""#2284 (TNCS public way -12 climbing the hill, 17.644359, -63.224090;
RULINGS 2026-11-25c "Any section of road should still be held to 2 %
laterally, but they still cross steep slopes and get cut or fill"): what
still held a RELEASED road under its target, each released by
``constraints/public_road_release``:

* the pairs from a MOUTH (a vertex the road shares with the lot it
  leaves), read at the mouth's DEM where it carries no target; never a
  pair between two mouths;
* §37 (10) (1)'s CONTACT rows off that lot;
* the LONGITUDINAL part of a cross-section diagonal on one route -- the
  cross-fall part stays (25c);
* a cross-section pair between two ROUTES of one road, capped at the
  steep-ground cap x the pair;
* the released longitudinal rows never under the steep-ground cap.
"""
from __future__ import annotations

import dataclasses as dc

import pytest
from auto_patch_v2.classify.roles import Cell
from auto_patch_v2.law import Law
from auto_patch_v2.law.tables import road_terrain_cap, role_cap
from auto_patch_v2.model.airport import OsmWay
from auto_patch_v2.model.constraints import Diff, Linear, Source
from tests.auto_patch_v2.test_pad_touch import _rect
from tests.auto_patch_v2.test_roads609e import _map

GRADE = 0.16
LON = Source("roads", "common.roles longitudinal (2026-08-03)", ())
CROSS = Source("roads", "road_cross_section (2026-08-25g)", ("face:0",))


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


@pytest.fixture(scope="module")
def built(law):
    """A public road on a 16 % hillside leaving a lot at its west end."""
    from auto_patch_v2.airport.public_road import public_road_faces, public_road_lifts
    cells = [Cell(9, "runway", "09/27", _rect(-800.0, -422.5, 800.0, -377.5), (),
                  3, "D", "airside", "runway", {}),
             Cell(1, "service_road", "small_roads:-1", _rect(0.0, 92.0, 300.0, 100.0), (),
                  None, None, "groundside", "service_road", {"osm_ribbon": 1.0}),
             Cell(2, "parking_lot", "lot", _rect(-40.0, 80.0, 0.0, 112.0), (),
                  None, None, "groundside", "parking_lot", {})]
    airport, pm = _map(law, cells, only=[])
    way = OsmWay(-1, "airport_small_roads", ((0.0, 96.0), (300.0, 96.0)), False,
                 {"highway": "residential"})
    airport = dc.replace(airport, osm_ways=(way,))
    road = next(f for f in pm.faces.values() if f.ref == "small_roads:-1")
    lot = next(f for f in pm.faces.values() if f.ref == "lot")
    ring = set(pm.ring_vertices(road.ring))
    shared = ring & set(pm.ring_vertices(lot.ring))
    target = {v: 700.0 + GRADE * pm.vertices[v].xy[0] for v in ring - shared}
    pm = dc.replace(pm, road_ramp_z=target)
    lifted = public_road_lifts(pm, law, public_road_faces(pm, law, airport), target)
    assert road.id in lifted
    pm = dc.replace(pm, public_road_lifted=lifted)
    return pm, road, sorted(shared)


def _xy(pm, v):
    return pm.vertices[v].xy


def test_a_mouth_pair_yields_two_mouths_do_not(law, built):
    from auto_patch_v2.constraints.public_road_release import (
        RELEASE_SLACK, _release_sets, terrain_release)
    pm, road, shared = built
    rel, mouths = _release_sets(pm, law)
    assert shared and set(shared) <= mouths and not (rel & mouths)
    m = shared[0]
    far = max(rel, key=lambda v: _xy(pm, v)[0])
    d = abs(_xy(pm, far)[0] - _xy(pm, m)[0])
    row = Diff(m, far, 0.10, d, LON)
    both = Diff(shared[0], shared[1], 0.10, 8.0, LON)
    out, n = terrain_release([row, both], pm, law)
    assert n == 1 and out[1] == both
    rise = abs(pm.road_ramp_z[far] - pm.vertices[m].dem_z) * (1 + RELEASE_SLACK)
    assert out[0].cap * d == pytest.approx(max(rise, road_terrain_cap(law) * d))


def test_the_contact_row_off_the_lot_yields_to_the_target(law, built):
    from auto_patch_v2.constraints.public_road_release import (
        CONTACT_HEAD, RELEASE_SLACK, terrain_release)
    pm, road, shared = built
    rel = [v for v in pm.road_ramp_z if _xy(pm, v)[0] > 100.0]
    v = rel[0]
    a, b = shared[0], shared[1]
    s = _xy(pm, v)[0]
    terms = ((v, 1.0), (a, -0.5), (b, -0.5))
    src = Source("road_ramp", CONTACT_HEAD + " (spec §37 (10))", ())
    hi = Linear(terms, None, 0.10 * s, src, follows=(v,))
    lo = Linear(terms, -0.10 * s, None, src, follows=(v,))
    out, n = terrain_release([hi, lo], pm, law)
    need = (pm.road_ramp_z[v] - 0.5 * (pm.vertices[a].dem_z + pm.vertices[b].dem_z)) \
        * (1 + RELEASE_SLACK)
    assert n == 1 and out[0].hi == pytest.approx(need) and out[1] == lo


def test_only_the_longitudinal_part_of_a_diagonal_yields(law, built):
    from auto_patch_v2.constraints.public_road_release import RELEASE_SLACK, terrain_release
    pm, road, _shared = built
    t = pm.road_ramp_z
    south = sorted((v for v in t if _xy(pm, v)[1] < 96.0), key=lambda v: _xy(pm, v)[0])
    north = sorted((v for v in t if _xy(pm, v)[1] > 96.0), key=lambda v: _xy(pm, v)[0])
    a, c = south[0], north[-1]
    ds, dt = abs(_xy(pm, c)[0] - _xy(pm, a)[0]), 8.0
    assert ds > 1.0
    caps = role_cap(law, road.role)
    bound = caps.longitudinal * ds + caps.transverse * dt
    src = dc.replace(CROSS, inputs=(f"face:{road.id}", road.ref))
    row = Diff(a, c, bound / (ds ** 2 + dt ** 2) ** 0.5, (ds ** 2 + dt ** 2) ** 0.5, src)
    frame = {a: (1, _xy(pm, a)[0], -4.0), c: (1, _xy(pm, c)[0], 4.0)}
    one = dc.replace(pm, road_route_frame=frame)
    out, n = terrain_release([row], one, law)
    assert n == 1
    # the cross-fall part is the 2 %; the longitudinal part the target's
    assert out[0].cap * out[0].d == pytest.approx(
        abs(t[a] - t[c]) * (1 + RELEASE_SLACK) + caps.transverse * dt)
    # two routes: the target's difference, capped at the steep cap x the pair
    two = dc.replace(pm, road_route_frame={a: frame[a], c: (2, 0.0, 4.0)})
    out2, _n = terrain_release([row], two, law)
    assert out2[0].cap * out2[0].d == pytest.approx(
        min(abs(t[a] - t[c]) * (1 + RELEASE_SLACK), road_terrain_cap(law) * row.d))
    # the pure cross-section (no run along the road) keeps its 2 %
    flat = Diff(a, c, 0.02, dt, src)
    same = dc.replace(pm, road_route_frame={a: frame[a], c: (1, _xy(pm, a)[0], 4.0)})
    assert terrain_release([flat], dc.replace(
        same, road_ramp_z={**t, c: t[a]}), law) == ([flat], 0)
