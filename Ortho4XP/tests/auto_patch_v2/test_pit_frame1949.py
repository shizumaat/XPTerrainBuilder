"""#1949 (owner RULINGS 2026-11-11f, OMDB ``duong_ray``): a rail group meeting
a station in a walled pit stays grouped with it; the more airside-visible of
the two sets the shared frame (``airport/pit_frame``)."""
from __future__ import annotations

import types

from auto_patch_v2.airport import pit_frame as PF
from shapely.geometry import box

ORIGIN = (25.0, 55.0)
#: the pit's footprint, a little east of the shared origin
RING = box(25.0, 55.001, 25.001, 55.002)


def _record(**kw):
    """The pit floor's record: authored at -0.219, the rail row (co-placed)
    at 13.469 -- OMDB's ``hamnen`` and ``duong_ray``."""
    rec = {"id": "dsf:obj1", "elevation": -12.4, "seat": "object floor",
           PF.PIT_OF: "object_floor:pit@pit0", "rim_proud_m": 0.0,
           PF.PIT_AUTHORED: {"dsf:obj1": -0.219, "dsf:obj9": 13.469},
           PF.PIT_RING: [list(q) for q in RING.exterior.coords]}
    rec.update(kw)
    return rec


def _frame(feet, member="dsf:obj9"):
    part = types.SimpleNamespace(pid=7, feet=tuple(feet), line=False)
    return types.SimpleNamespace(id="unit:4", anchor=ORIGIN, agl_m=13.7,
                                 members=(types.SimpleNamespace(id=member, parts=(part,)),))


IN_PIT = [(25.0005, 55.0015, -15.7)]
KEY = "fu:4:574|unit:4"


def _join(u, zeros, airside=None, recs=None, crest=3.0):
    pits = PF.pits_of(recs or [_record()])
    shifts, counts = {}, {}
    PF.join_frame(u, {7: ("fu:0:18/c3", 1.0)}, {"fu:0:18": "fu:4:574"}, zeros,
                  airside or {}, pits, crest, shifts, counts)
    return shifts, counts


def test_a_share_on_no_airside_rides_the_pit_rigidly():
    zeros = {KEY: (2.2, 13.7)}
    shifts, counts = _join(_frame(IN_PIT), zeros)
    assert shifts == {} and counts == {"pit_frame_shares": 1}
    assert abs(zeros[KEY][0] - (-12.4 + 13.469 + 0.219)) < 1e-9


def test_an_airside_share_raises_the_pit_frame_to_it_within_the_crest_band():
    """OMDB: the rail's share is seated on Concourse D's apron floor (2.215);
    the pit frame (-12.418, its rim on the ground) rises 0.945 to it."""
    zeros = {KEY: (2.215, 13.7)}
    shifts, counts = _join(_frame(IN_PIT), zeros, {KEY: (2.215, 68)},
                           [_record(elevation=-12.418)])
    assert zeros[KEY] == (2.215, 13.7)
    assert abs(shifts["object_floor:pit@pit0"] - 0.945) < 1e-9
    assert counts == {"pit_frame_moved": 1}
    recs = PF.shifted([_record(elevation=-12.418), {"id": "x", "elevation": 5.0}], shifts)
    assert [r["elevation"] for r in recs] == [-11.473, 5.0]


def test_the_two_stay_apart_where_the_pit_would_sink_or_its_rim_leave_the_band():
    zeros = {KEY: (0.0, 13.7)}                      # the pit would sink 1.27 m
    assert _join(_frame(IN_PIT), zeros, {KEY: (0.0, 9)})[1] == {"pit_frame_apart": 1}
    zeros = {KEY: (6.0, 13.7)}                      # the rim 4.7 m proud > 3.0
    assert _join(_frame(IN_PIT), zeros, {KEY: (6.0, 9)})[1] == {"pit_frame_apart": 1}


def test_no_foot_in_the_pit_or_a_placement_not_co_placed_is_no_witness():
    zeros = {KEY: (2.2, 13.7)}
    assert _join(_frame([(25.0005, 55.003, 0.0)]), zeros) == ({}, {})
    assert _join(_frame(IN_PIT, member="dsf:obj77"), zeros) == ({}, {})
    assert zeros[KEY] == (2.2, 13.7)


def test_the_floor_record_carries_the_pit_and_the_frame_rows_its_name():
    f = types.SimpleNamespace(id="object_floor:pit@pit0", authored=(("a", -0.2), ("b", 13.5)),
                              rim_proud_m=0.25, footprint=box(0.0, 0.0, 10.0, 10.0))
    floor, row = {"id": "a"}, {"id": "b"}
    PF.stamp(floor, f, lambda x, y: (25.0 + y * 1e-5, 55.0 + x * 1e-5))
    PF.stamp(row, f, None)
    assert row == {"id": "b", PF.PIT_OF: f.id}
    assert floor[PF.PIT_AUTHORED] == {"a": -0.2, "b": 13.5} and floor["rim_proud_m"] == 0.25
    assert len(floor[PF.PIT_RING]) == 5
    [p] = PF.pits_of([{**floor, "elevation": -1.0}])
    assert p.id == f.id and p.zero == -1.0 and p.authored_zero == -0.2
