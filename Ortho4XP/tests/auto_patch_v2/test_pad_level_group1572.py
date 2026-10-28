"""Twin of RULINGS 2026-10-28p (2) (Q241 a; #1572, #1288): within one frame
a unit on the same flat pad as the pad's largest unit, drawn higher, sinks
to that group's level at any depth; a unit drawn lower never floats."""
from __future__ import annotations

import types

from auto_patch_v2.airport.open_frame_seat import group_key
from auto_patch_v2.airport.pad_level_group import pad_level_links

F = "unit:1"


def _frame(seats):
    """``seats``: pid -> (unit id, zero, pad, source) -> (frame, plan_wide)."""
    parts = [types.SimpleNamespace(pid=pid, rings=()) for pid in seats]
    u = types.SimpleNamespace(id=F, anchor=(0.0, 0.0),
                              members=[types.SimpleNamespace(parts=parts)])
    pw = {pid: (s[0], s[1], s[2], s[3], ("", ""), None) for pid, s in seats.items()}
    return u, pw


def _zeros(**z):
    return {group_key(r.replace("_", ":"), F): (v, 0.0) for r, v in z.items()}


def _add(u, pw, pid, seat):
    pw[pid] = (*seat, ("", ""), None)
    u.members[0].parts.append(types.SimpleNamespace(pid=pid, rings=()))


def _garage_and_island(island_zero, island_pad="b12", island_src="pad"):
    seats = {i: ("fu:1:1/p1", 306.61, "b12", "pad") for i in range(10)}
    seats[20] = ("fu:1:2", island_zero, island_pad, island_src)
    seats[21] = ("fu:1:2", island_zero, island_pad, island_src)
    return _frame(seats)


def test_a_unit_drawn_higher_on_the_pad_sinks_to_the_largest_units_group():
    u, pw = _garage_and_island(307.25)
    counts, movers = {}, []
    got = pad_level_links(u, pw, {}, _zeros(fu_1_1=306.61, fu_1_2=307.25),
                          counts=counts, movers=movers)
    assert got == {"fu:1:2": "fu:1:1"}
    assert counts == {"pad_level_sunk": 1, "pad_level_sunk_cm_max": 64}
    assert movers[0][:3] == ("fu:1:2", "fu:1:1", "b12")


def test_at_any_depth():
    u, pw = _garage_and_island(312.0)
    got = pad_level_links(u, pw, {}, _zeros(fu_1_1=306.61, fu_1_2=312.0))
    assert got == {"fu:1:2": "fu:1:1"}


def test_a_unit_drawn_lower_never_floats():
    u, pw = _garage_and_island(306.40)
    assert pad_level_links(u, pw, {}, _zeros(fu_1_1=306.61, fu_1_2=306.40)) == {}


def test_within_tolerance_nothing_moves():
    u, pw = _garage_and_island(306.64)
    assert pad_level_links(u, pw, {}, _zeros(fu_1_1=306.61, fu_1_2=306.64)) == {}


def test_a_ground_seated_unit_chained_in_rides_along():
    u, pw = _garage_and_island(307.25)
    _add(u, pw, 30, ("fu:1:3/host", 307.95, "", "ground"))
    got = pad_level_links(u, pw, {"fu:1:3": "fu:1:2"},
                          _zeros(fu_1_1=306.61, fu_1_2=307.25))
    assert got == {"fu:1:2": "fu:1:1", "fu:1:3": "fu:1:1"}


def test_a_group_whose_level_is_a_ground_seat_stays():
    u, pw = _garage_and_island(307.25)
    _add(u, pw, 30, ("fu:1:3/host", 307.95, "", "ground"))
    got = pad_level_links(u, pw, {"fu:1:2": "fu:1:3"},
                          _zeros(fu_1_1=306.61, fu_1_3=307.95))
    assert got == {"fu:1:2": "fu:1:3"}


def test_another_pad_or_a_ground_seat_is_not_read():
    for pad, src in (("b13", "pad"), ("b12", "ground")):
        u, pw = _garage_and_island(307.25, pad, src)
        assert pad_level_links(u, pw, {}, _zeros(fu_1_1=306.61, fu_1_2=307.25)) == {}


def test_a_group_with_a_unit_off_the_pad_stays():
    u, pw = _garage_and_island(307.25)
    _add(u, pw, 30, ("fu:1:3", 309.0, "b40", "pad"))
    got = pad_level_links(u, pw, {"fu:1:3": "fu:1:2"},
                          _zeros(fu_1_1=306.61, fu_1_2=307.25))
    assert got == {"fu:1:3": "fu:1:2"}


def test_the_whole_merged_group_moves_with_the_target():
    u, pw = _garage_and_island(307.25)
    _add(u, pw, 30, ("fu:1:3", 307.0, "b12", "pad"))
    got = pad_level_links(u, pw, {"fu:1:3": "fu:1:2"},
                          _zeros(fu_1_1=306.61, fu_1_2=307.25))
    assert got == {"fu:1:2": "fu:1:1", "fu:1:3": "fu:1:1"}


def test_the_target_is_the_group_the_largest_unit_already_moves_with():
    u, pw = _garage_and_island(307.25)
    got = pad_level_links(u, pw, {"fu:1:1": "fu:1:9"},
                          _zeros(fu_1_9=306.0, fu_1_2=307.25))
    assert got == {"fu:1:1": "fu:1:9", "fu:1:2": "fu:1:9"}


def test_airside_wins():
    u, pw = _garage_and_island(307.25)
    z = _zeros(fu_1_1=306.61, fu_1_2=307.25)
    assert pad_level_links(u, pw, {}, z, airside={group_key("fu:1:2", F)}) == {}
