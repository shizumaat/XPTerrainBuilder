"""THE ROAD TO AN UPPER PAD (spec ``docs/specs/2068-upper-pad-spec-A1.md``
(2), #2068): the terrace climbs to the level at the cap and never over it
(``constraints/road_ramp.terrace_profile``), the level's rim takes no road
target, and the rim's step is a declared riser (``constraints/riser``,
``constraints/pavement_cap``) — not a row holding the arm up the hill."""
from __future__ import annotations

import types

import pytest
from auto_patch_v2.constraints.road_ramp import terrace_profile

CAP = 0.10


def _route(n, step=5.0):
    return {i: (0, i * step) for i in range(n)}


def test_the_arm_climbs_at_the_cap_to_the_level_and_never_over_it():
    """Stations 0-1 at the apron (100), 2-3 a floor pad's frontage (held),
    4-9 bare to the upper pad's level at 104.7 bordered at 8-9."""
    st = _route(10)
    foot = {v: (1000 + v, 1000 + v, 0.0, "apron") for v in (0, 1)}
    lv = {1000: 100.0, 1001: 100.0}
    terr = {"foot": foot, "pad": {2: "b1", 3: "b1"}, "station": st,
            "level": {8: "b1/p1", 9: "b1/p1"}, "own": {7: True}}
    floor = {v: 106.0 for v in st}
    out, rep = terrace_profile(terr, lv, floor, CAP, upper={8: 104.7, 9: 104.7})
    assert out[2] == out[3] == 100.0                     # the floor-pad hold
    for v in range(4, 10):
        assert out[v] == pytest.approx(min(104.7, 100.0 + CAP * (v - 3) * 5.0))
    assert rep["upper_run"] == 6
    assert rep["upper_gap_m"] == pytest.approx(104.7 - 103.0)     # the arrival gap
    # the rim takes no target
    out2, _ = terrace_profile({**terr, "rim": {9: "b1/p1"}}, lv, floor, CAP,
                              upper={8: 104.7, 9: 104.7})
    assert 9 not in out2 and out2[8] == out[8]


def test_no_level_is_byte_identical():
    st = _route(10)
    foot = {v: (1000 + v, 1000 + v, 0.0, "apron") for v in (0, 1)}
    lv = {1000: 100.0, 1001: 100.0}
    terr = {"foot": foot, "pad": {2: "b1"}, "station": st}
    floor = {v: 106.0 for v in st}
    a = terrace_profile(terr, lv, floor, CAP)
    b = terrace_profile({**terr, "level": {}, "rim": {}}, lv, floor, CAP, upper={})
    assert a[0] == b[0]
    assert b[1] == a[1]


def _pm():
    def face(i, ref, role, ring):
        return types.SimpleNamespace(id=i, ref=ref, role=role, ring=ring, holes=())
    faces = {0: face(0, "b", "building", (1, 2)), 1: face(1, "b/p1#strip", "building", (2, 3)),
             2: face(2, "b/p1", "building", (3, 4, 6)),
             3: face(3, "pol#2", "service_road", (4, 5, 6)),        # the arm
             4: face(4, "pol#2#1", "service_road", (5, 7)),         # a planar piece of it
             5: face(5, "other", "service_road", (8, 9))}
    vx = {v: types.SimpleNamespace(xy=(float(v), 0.0)) for v in range(1, 10)}
    return types.SimpleNamespace(
        faces=faces, vertices=vx, ring_vertices=lambda ring: ring,
        registries=types.SimpleNamespace(landings={"b/p1": {
            "block": "b", "kind": "upper_level", "witness": "group_up", "y": 4.7,
            "arms": ("pol#2",)}}))


def test_the_arm_is_the_far_side_of_the_rim():
    from auto_patch_v2.constraints import riser
    from auto_patch_v2.model.constraints import Diff, Linear, Source
    pm = _pm()
    lvl, arm = riser.upper_arm_sets(pm)
    assert lvl == {3, 4, 6} and arm == {5, 7}
    low, high, _road = riser.riser_sets(pm)
    assert {5, 7} <= high and not ({8, 9} & high)
    src = Source("roads", "r")
    land = Source("landing_rows", "r", ("landing:b/p1", "b/p1", "platform:b"))
    rows = [Diff(4, 5, 0.1, 5.0, src),                     # rim -> arm: withdrawn
            Diff(5, 7, 0.1, 5.0, src),                     # inside the arm: kept
            Linear(((4, 1.0), (1, -1.0)), None, 4.7, land)]
    counts: dict = {}
    assert riser.riser_exempt(rows, pm, counts) == rows[1:]
    assert counts["riser_rows_withdrawn"] == 1


def test_no_upper_pad_no_arm_sets():
    from auto_patch_v2.constraints import riser
    pm = _pm()
    pm.registries.landings["b/p1"]["witness"] = None
    assert riser.upper_arm_sets(pm) == (frozenset(), frozenset())
