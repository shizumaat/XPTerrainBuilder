"""THE UPPER FORECOURT OF A SPLIT-LEVEL BUILDING (#1934 R6; owner RULINGS
2026-11-17h (5), KLAX: the paved area beside Terminal 8 "is at the floor of
the upper story of the split level building"): a surface car park fronting
the building's upper-footed walls, clear of its lower walls, is held at
the upper floor with the ground between it and the wall
(``airport/split_level_forecourt``, ``planar/split_level_pit._forecourt``,
``constraints/structures._court_rim``).  Synthetic: no pack, no airport."""
from __future__ import annotations

from auto_patch_v2.airport.split_level_forecourt import upper_forecourt
from shapely.geometry import LineString, Point, box

#: a building x 0..20: its east wall y -60..0 upper-footed, y 0..40 lower
_UPPER = [LineString([(20, -60), (20, 0)])]
_LOWER = [LineString([(20, 0), (20, 40)])]
#: a car park 10 m east of the upper wall, one touching it to the south,
#: one against the lower wall (the lower lot), one far away
_SOUTH_LOT = box(30, -50, 50, -10)
_TAIL = box(30, -70, 45, -50)
_LOW_LOT = box(22, 5, 50, 35)
_FAR = box(200, -50, 220, -10)


def test_a_car_park_fronting_the_upper_walls_is_the_upper_floor_with_the_strip_to_the_wall():
    court = upper_forecourt(_UPPER, _LOWER, [_SOUTH_LOT, _TAIL, _LOW_LOT, _FAR], 20.0, 5.0)
    assert court is not None
    # the lot, the ground between it and the wall, and the lot touching it
    assert court.contains(Point(40, -30)) and court.contains(Point(25, -30))
    assert court.contains(Point(40, -60))
    # never the lot the lower walls stand on, nor one no wall fronts
    assert not court.intersects(box(22, 6, 50, 34))
    assert not court.intersects(_FAR)


def test_the_forecourt_stays_on_bare_ground_and_needs_a_witness():
    road = box(25, -40, 50, -35)
    court = upper_forecourt(_UPPER, _LOWER, [_SOUTH_LOT], 20.0, 5.0, clear=road)
    assert court is not None and not court.intersects(box(26, -39, 49, -36))
    # no car park within reach of an upper wall: nothing
    assert upper_forecourt(_UPPER, _LOWER, [_FAR], 20.0, 5.0) is None
    # a car park the lower walls stand on, though an upper wall fronts it too
    both = box(25, -20, 50, 20)
    assert upper_forecourt(_UPPER, _LOWER, [both], 20.0, 5.0) is None
    assert upper_forecourt([], _LOWER, [_SOUTH_LOT], 20.0, 5.0) is None
