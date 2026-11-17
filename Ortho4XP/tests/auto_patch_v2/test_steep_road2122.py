"""OWNER RULINGS 2026-11-17 (#2122, NZWN hill road): "Looks like there are
real roads that go up to 20%, so when terrain demands it, we should allow
it. Raise our road grade limit to 20%."

* ``law.tables.road_terrain_cap``: the ONE constant (``[common]
  road_terrain_max_grade``), never under the road cap;
* the core clamp's in-band cap (``O4_Vector_Utils.road_inside_cap``): a
  non-public ROAD follows its terrain up to it; a railway, an untagged way
  and every road without it keep the cap;
* ``airport/public_road.steep_road_lifts``: a non-public mapped road whose
  own target runs over the road cap takes the steep-ground cap; on gentle
  ground nothing is named;
* ``constraints/public_road_release.steep_release``: its longitudinal rows
  rise to that cap; the cross-section keeps its 2 %; nothing is tightened;
* ``constraints/road_ramp.terrace_profile``: a bare exit on such a route
  steepens toward that cap only where its run demands it (the design grade
  stands where it reaches).
"""
from __future__ import annotations

import dataclasses as dc

import O4_Cfg_Vars as CFGVARS
import O4_Vector_Utils as VECT
import pytest
from auto_patch_v2.law import Law
from auto_patch_v2.model.constraints import Diff, Source
from tests.auto_patch_v2.test_public_road_release import GRADE, _built


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


def test_the_steep_ground_cap_is_one_constant_over_the_road_cap(law):
    from auto_patch_v2.law.tables import road_terrain_cap
    c = law.tables.common
    assert road_terrain_cap(law) == pytest.approx(0.20)
    assert road_terrain_cap(law) >= c.road_max_grade
    assert CFGVARS.road_neighbourhood_law()["terrain_cap"] == road_terrain_cap(law)
    # the design grade stands
    assert law.tables.emit.road_contact.ramp_grade == pytest.approx(0.05)


def test_the_core_clamp_lets_a_road_follow_steep_ground_to_the_cap():
    nl = CFGVARS.road_neighbourhood_law()
    cap, ceil, pub, top = 0.10, nl["cap_ceiling"], nl["public_classes"], nl["terrain_cap"]
    assert VECT.road_inside_cap("service", cap, ceil, pub, top) == top
    assert VECT.road_inside_cap("track", cap, ceil, pub, top) == ceil     # public (22h)
    assert VECT.road_inside_cap("residential", cap, ceil, pub, top) == ceil
    assert VECT.road_inside_cap("railway:rail", cap, ceil, pub, top) == cap
    assert VECT.road_inside_cap(None, cap, ceil, pub, top) == cap
    assert VECT.road_inside_cap("service", cap, ceil, pub) == cap         # not given
    # the clamp itself: on a 16 % hill the service road follows the ground,
    # on 30 % it is held at the steep-ground cap
    import numpy as np
    s = np.arange(0.0, 101.0, 5.0)
    for g, want in ((0.16, 0.16), (0.30, top)):
        dem = 100.0 + g * s
        prof = VECT.cap_lipschitz_profile(s, dem, top)
        assert np.abs(np.diff(prof) / np.diff(s)).max() == pytest.approx(want, rel=1e-6)


def test_a_service_road_on_steep_ground_takes_the_steep_cap(law):
    from auto_patch_v2.airport.public_road import (
        public_road_faces,
        steep_road_faces,
        steep_road_lifts,
    )
    from auto_patch_v2.law.tables import road_terrain_cap
    airport, pm, road = _built(law, "service")
    faces = steep_road_faces(pm, law, airport)
    assert road.id in faces and road.id not in public_road_faces(pm, law, airport)
    lifted = steep_road_lifts(pm, law, faces, pm.road_ramp_z)
    assert GRADE > 0.10 and lifted == {road.id: road_terrain_cap(law)}
    # gentle ground: nothing named, nothing changes
    gentle = {v: 700.0 + 0.04 * pm.vertices[v].xy[0] for v in pm.road_ramp_z}
    assert steep_road_lifts(pm, law, faces, gentle) == {}
    # a ramp built AT the old cap reads a hair over it: not steep ground
    at_cap = {v: 700.0 + 0.1004 * pm.vertices[v].xy[0] for v in pm.road_ramp_z}
    assert steep_road_lifts(pm, law, faces, at_cap) == {}
    # a public road is 22h's, never this ruling's
    airport, pm, road = _built(law, "residential")
    assert road.id not in steep_road_faces(pm, law, airport)


def test_the_longitudinal_rows_rise_to_the_steep_cap_the_cross_section_does_not(law):
    from auto_patch_v2.airport.public_road import steep_road_faces, steep_road_lifts
    from auto_patch_v2.constraints.public_road_release import (
        steep_release,
        steep_vertex_caps,
        terrain_release,
    )
    from auto_patch_v2.pipeline.publication import lifted_caps
    airport, pm, road = _built(law, "service")
    lifted = steep_road_lifts(pm, law, steep_road_faces(pm, law, airport), pm.road_ramp_z)
    pm = dc.replace(pm, steep_road_lifted=lifted)
    caps = steep_vertex_caps(pm, law)
    assert caps and set(caps.values()) == {0.20}
    south = sorted((v for v in caps if pm.vertices[v].xy[1] < 96.0),
                   key=lambda v: pm.vertices[v].xy[0])
    north = [v for v in caps if pm.vertices[v].xy[1] > 96.0]
    a, b = south[0], south[-1]
    c = min(north, key=lambda v: abs(pm.vertices[v].xy[0] - pm.vertices[a].xy[0]))
    d_ab = abs(pm.vertices[a].xy[0] - pm.vertices[b].xy[0])
    lon = Diff(a, b, 0.10, d_ab, Source("roads", "common.roles longitudinal (2026-08-03)", ()))
    cross = Diff(a, c, 0.02, 8.0, Source("roads", "road_cross_section (2026-08-25g)", ()))
    out, n = steep_release([lon, cross], pm, law)
    assert n == 1 and out[0].cap == pytest.approx(0.20) and out[1] == cross
    loose = dc.replace(lon, cap=0.5)
    assert steep_release([loose], pm, law)[0] == [loose]
    # the public road's release reads its own map only
    assert terrain_release([lon], pm, law) == ([lon], 0)
    # the census lifts the same face
    assert lifted_caps(pm)[road.id] == pytest.approx(0.20)


def test_a_bare_exit_steepens_toward_the_route_cap_only_where_its_run_demands():
    """Station 0 bordered at 100; 1-10 bare, 5 m apart, the floor climbing
    16 %: the run's end (110 + 8 m at 50 m) needs 16 %.  At the old cap the
    exit is held at 10 %; on a steep route it climbs at the 16 % its run
    needs — never the 20 % cap — and on a route whose end the design grade
    reaches it stays at 5 %."""
    from auto_patch_v2.constraints.road_ramp import terrace_profile
    st = {i: (0, i * 5.0) for i in range(11)}
    foot = {0: (1000, 1000, 0.0, "apron")}
    lv = {1000: 100.0}
    floor = {v: 100.0 + 0.16 * 5.0 * v for v in st}
    terr = {"foot": foot, "pad": {}, "station": st}
    kw = dict(design=0.05, lane=4.0)
    held, _r = terrace_profile(terr, lv, floor, 0.10, **kw)
    assert held[10] == pytest.approx(105.0)
    steep, rep = terrace_profile(terr, lv, floor, 0.10, route_caps={0: 0.20}, **kw)
    assert steep[10] == pytest.approx(108.0)
    assert rep["max_bare_grade"] == pytest.approx(0.16)
    gentle = {v: 100.0 + 0.04 * 5.0 * v for v in st}
    flat, rep = terrace_profile(terr, lv, gentle, 0.10, route_caps={0: 0.20}, **kw)
    assert rep["max_bare_grade"] == pytest.approx(0.05)
