"""The cut is the deck's (owner 2026-11-19T23:07Z / 23:09Z; RULINGS
2026-11-19s (2)-(4)): every generated deck owns its cut -- the floor at
``min(lidar road floor, underside - clearance)``, ramps back along the
road (or the cut's own axis) at the grade cap with vertical curves until
they meet the terrain, the abutments' embankments at 1V:1.5H -- and stage
2 levels it without touching an airside vertex.  Headless, synthetic."""
from __future__ import annotations

import types

import numpy as np
import pytest

from auto_patch_v2.geom.carve_profile import PathFrame, floor_profile, lateral, ramp_lengths

CAP, RATE = 0.10, 0.01 / 3.0


def test_floor_is_level_under_the_deck_and_ramps_out_at_the_cap():
    s = np.arange(-200.0, 201.0, 2.0)
    terrain = np.full(len(s), 173.0)
    z = floor_profile(s, terrain, [(-20.0, 20.0, 165.3)], CAP, RATE)
    under = z[(s >= -20.0) & (s <= 20.0)]
    assert np.allclose(under, 165.3, atol=1e-6)            # the rule's floor, level
    g = np.diff(z) / np.diff(s)
    assert np.abs(g).max() <= CAP + 1e-6                   # the grade cap
    assert np.abs(np.diff(g)).max() / 2.0 <= RATE + 1e-6   # the vertical curves
    before, after = ramp_lengths(s, z, terrain, [(-20.0, 20.0, 165.3)])
    # 7.7 m at 10 % is 77 m, plus half of each of the two curves (30 m)
    assert 77.0 <= before <= 120.0 and before == after
    assert z.max() <= 173.0 + 0.3                          # never fills over the ground


def test_two_decks_over_one_road_share_one_cut_straight_through_the_gap():
    s = np.arange(-200.0, 201.0, 2.0)
    terrain = np.full(len(s), 173.0)
    st = [(-50.0, -20.0, 165.3), (0.0, 30.0, 165.6)]
    z = floor_profile(s, terrain, st, CAP, RATE)
    gap = z[(s > -20.0) & (s < 0.0)]
    assert gap.max() <= 165.6 + 0.05                       # no crest between the decks


def test_the_ramp_follows_the_lidar_road_where_it_is_lower():
    s = np.arange(-150.0, 151.0, 2.0)
    terrain = np.maximum(173.0 - 0.05 * np.abs(s), 160.0)  # the road falls away
    z = floor_profile(s, terrain, [(-20.0, 20.0, 165.0)], CAP, RATE)
    far = np.abs(s) > 120.0
    assert np.all(z[far] <= terrain[far] + 0.3)


def test_lateral_bank_and_projection():
    f = PathFrame([(0.0, 0.0), (100.0, 0.0)])
    s, n = f.project([50.0, 10.0], [4.0, -9.0])
    assert s.tolist() == pytest.approx([50.0, 10.0])
    assert n.tolist() == pytest.approx([4.0, 9.0])
    z = lateral([165.0, 165.0], n, 5.0, 1.0 / 1.5)
    assert z[0] == pytest.approx(165.0)                    # on the floor
    assert z[1] == pytest.approx(165.0 + 4.0 / 1.5)        # on the bank


def _deck():
    from auto_patch_v2.model.deck_carve import CarvePath, DeckCarve
    from auto_patch_v2.model.structures import GENERATED_WITNESS, DeckBridge
    # the taxiway runs along y over a road along x; the ring is 40 m along
    # the taxiway (y -20..20) and 25 m across it (x -12.5..12.5)
    ring = ((-12.5, -20.0), (12.5, -20.0), (12.5, 20.0), (-12.5, 20.0))
    sa = ((-12.5, -17.6), (12.5, -17.6))
    sb = ((-12.5, 17.6), (12.5, 17.6))
    terrain = tuple((float(s), 173.0) for s in np.arange(0.0, 401.0, 2.0))
    p = CarvePath("-1", "road", 5.0, 5.0, CAP, RATE,
                  ((-200.0, 0.0), (200.0, 0.0)), ((185.0, 215.0, "o4gen_t"),), terrain)
    dc = DeckCarve(("OSM road -1 highway=primary",), "along OSM road -1 (primary)", (p,))
    return DeckBridge("o4gen_t", "x.obj", (), ring, sa, sb, 0.0, 0.0, -6.0, 173.0,
                      walls=(), floor_min_m=6.0, witness=GENERATED_WITNESS, family="taxi",
                      covered=(("-1", (("highway", "primary"),), ((-100.0, 0.0), (100.0, 0.0))),),
                      carve=dc)


def _Top():
    """A flat top at 173.0 over the ring: end A at y = -20, end B at y = 20."""
    from auto_patch_v2.geom.coons_patch import CoonsPatch
    flat = ((0.0, 173.0), (1.0, 173.0))
    return CoonsPatch((-12.5, -20.0), (0.0, 40.0), (25.0, 0.0), flat, flat, flat, flat)


def _pm():
    xs = np.arange(-120.0, 121.0, 4.0)
    ys = np.arange(-40.0, 41.0, 4.0)
    verts, faces, air = {}, {0: types.SimpleNamespace(ref="deck_carve:o4gen_t:floor")}, set()
    k = 0
    for x in xs:
        for y in ys:
            verts[k] = types.SimpleNamespace(xy=(float(x), float(y)), dem_z=173.0,
                                             incident_faces=(0,))
            if abs(y) >= 20.0 and abs(x) <= 12.5:
                air.add(k)          # the taxiway beyond the deck's ends
            k += 1
    return types.SimpleNamespace(vertices=verts, faces=faces), air


def test_carve_levels_the_cut_and_never_an_airside_vertex():
    from auto_patch_v2.constraints.deck_carve import carve_levels
    from auto_patch_v2.law import Law
    law = Law.load()
    pm, air = _pm()
    values = {v: 173.0 for v in air}
    got, rep = carve_levels(pm, [_deck()], {"o4gen_t": _Top()}, air, values, {}, law)
    assert got and not (set(got) & air)                    # 19s (1)
    path = rep["o4gen_t"]["paths"][0]
    st = path["stretches"][0]
    # the floor is the underside (173 - 1.0 slab) less the 5 m clearance
    assert st["floor"] == pytest.approx(173.0 - 1.0 - 5.0)
    assert st["clearance"] >= 5.0 - 1e-6
    assert path["max_grade"] <= CAP + 1e-6
    assert all(r is not None for r in path["ramp_m"])
    centre = [v for v, vx in pm.vertices.items() if vx.xy == (0.0, 0.0)][0]
    assert got[centre] == pytest.approx(167.0, abs=0.01)   # the floor under the deck
    # the abutment's embankment: 4 m inside the ring from the end line at
    # y = 20 the cut stands no deeper than the bank from the pavement allows
    bank = [v for v, vx in pm.vertices.items() if vx.xy == (0.0, 16.0)][0]
    assert got[bank] == pytest.approx(173.0 - 4.0 / 1.5, abs=0.01)   # on the embankment
    assert rep["o4gen_t"]["evidence"] == ["OSM road -1 highway=primary"]


def test_a_path_follows_its_mapped_road_and_runs_straight_on_past_its_end():
    from shapely.geometry import LineString

    from auto_patch_v2.planar.deck_carve import _extended, _road_lines
    # the covered piece runs east; the mapped road bends north-east past it
    ways = [types.SimpleNamespace(points=((-50.0, 0.0), (50.0, 0.0)), tags={"highway": "primary"}),
            types.SimpleNamespace(points=((50.0, 0.0), (90.0, 30.0)), tags={"highway": "primary"})]
    airport = types.SimpleNamespace(osm_ways=ways)
    lines, tree = _road_lines(airport)
    got = _extended(LineString([(-10.0, 0.0), (10.0, 0.0)]), 100.0, lines, tree)
    from shapely.geometry import Point
    assert got.distance(Point(90.0, 30.0)) < 1e-6        # followed the bend
    assert got.coords[-1][0] > 90.0                       # ... and straight on past it
    assert got.length == pytest.approx(20.0 + 2 * 100.0, abs=0.5)
    assert got.coords[0][0] < -50.0          # straight on past the map's west end


def test_a_deck_with_no_mapped_road_ramps_along_its_own_axis():
    from auto_patch_v2.law import Law
    from auto_patch_v2.planar.deck_carve import _deck_paths
    law = Law.load()
    d = _deck()
    import dataclasses
    d = dataclasses.replace(d, covered=(), replaces=("dsf:obj1",), carve=None)
    airport = types.SimpleNamespace(osm_ways=(), dem=types.SimpleNamespace(z=lambda x, y: 173.0),
                                    aeroways=())
    import auto_patch_v2.planar.structure_underpass as su
    old = su.aeroway_decks
    su.aeroway_decks = lambda a, law: []
    try:
        dc = _deck_paths(d, [d], airport, law, [], None)
    finally:
        su.aeroway_decks = old
    assert dc.direction.startswith("along the cut's own axis")
    assert "hidden pack frame" in dc.evidence
    (p,) = dc.paths
    assert p.kind == "axis" and p.stretches and len(p.terrain) > 10
    # the axis runs along the end lines (x), across the taxiway
    (x0, y0), (x1, y1) = p.coords[0], p.coords[-1]
    assert abs(y1 - y0) < 1e-6 and abs(x1 - x0) > 100.0


def test_two_decks_far_apart_are_two_cuts_close_ones_one():
    from auto_patch_v2.geom.carve_profile import merged
    # 8 m deep each, 10 %: a ramp up and back down needs 160 m
    assert merged(19.0, 165.0, 165.0, 173.0, CAP)
    assert not merged(200.0, 165.0, 165.0, 173.0, CAP)
    s = np.arange(-300.0, 301.0, 2.0)
    terrain = np.full(len(s), 173.0)
    z = floor_profile(s, terrain, [(-150.0, -120.0, 165.0), (120.0, 150.0, 165.0)], CAP, RATE)
    assert z[np.argmin(np.abs(s))] == pytest.approx(173.0, abs=0.31)   # ground between


def test_the_floor_is_the_decks_full_span_less_its_embankments():
    import dataclasses

    from auto_patch_v2.constraints.deck_carve import _floor_half
    from auto_patch_v2.law import Law
    law = Law.load()
    p = dataclasses.replace(_deck().carve.paths[0], span_m=20.0)
    top = types.SimpleNamespace(z_st=lambda s, t: 173.0)
    # 6 m deep at 1V:1.5H: 9 m of embankment off each end
    assert _floor_half(p, top, 167.0, law) == pytest.approx(11.0, abs=0.01)
    # never narrower than the roads under it (a wall where they need it)
    assert _floor_half(p, top, 160.0, law) == pytest.approx(p.half_m)
