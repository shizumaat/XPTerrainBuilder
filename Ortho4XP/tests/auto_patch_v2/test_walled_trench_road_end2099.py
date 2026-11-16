"""#2099 F2 (lcyyzP5): a walled trench's floor meets a road entering it at
its ring -- a mapped road end standing in a wall's opening (outside the
floor, within a wall's plan thickness) is on the floor; one past the wall,
or already inside, leaves the floor as it was."""
from __future__ import annotations

from shapely.geometry import Point, box

from auto_patch_v2.airport.walled_trench import _reach_road_ends

FLOOR = box(0.0, 0.0, 20.0, 40.0)
TK = 2.0


def test_end_in_the_wall_opening_stands_on_the_floor():
    end = (10.0, 40.1)                      # 0.1 m past the ring, in the headwall
    got = _reach_road_ends(FLOOR, [(end, -1335)], TK)
    assert got.contains(Point(end))
    assert got.area > FLOOR.area
    # the floor grew only at the opening: a strip 0.25 * tk either side
    assert got.difference(FLOOR).bounds[0] >= 10.0 - 0.25 * TK - 1e-6
    assert got.difference(FLOOR).bounds[2] <= 10.0 + 0.25 * TK + 1e-6


def test_end_past_the_wall_or_inside_is_unchanged():
    for end in ((10.0, 40.0 + TK + 0.5), (10.0, 20.0)):
        assert _reach_road_ends(FLOOR, [(end, 1)], TK).equals(FLOOR)
    assert _reach_road_ends(FLOOR, (), TK).equals(FLOOR)
