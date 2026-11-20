"""A neck's road leg beyond its taxi routes' territory is the road
(``classify/neck_road``; owner sim read 2026-11-19, a fuel-farm loop road
read as a taxi junction)."""
from shapely.geometry import Point, box
from shapely.ops import unary_union

from auto_patch_v2.classify import load_rules
from auto_patch_v2.classify.neck_road import road_beyond_routes

RULES = load_rules()
TERRITORY = box(0, 0, 60, 60)


def _no_stand(_p):
    return False


def test_road_wide_leg_beyond_the_territory_is_the_road():
    face = unary_union([TERRITORY, box(60, 20, 260, 31)])
    keep, roads = road_beyond_routes(face, TERRITORY, RULES, _no_stand)
    assert len(roads) == 1
    part, width = roads[0]
    assert abs(part.area - 200 * 11) < 1.0
    assert 9.0 < width < 12.0
    assert abs(keep.area - 60 * 60) < 1.0


def test_wide_remainder_stays_with_the_junction():
    face = unary_union([TERRITORY, box(60, 0, 260, 60)])   # 60 m wide: a plate
    assert road_beyond_routes(face, TERRITORY, RULES, _no_stand) == (None, [])


def test_a_stand_on_the_leg_keeps_it():
    face = unary_union([TERRITORY, box(60, 20, 260, 31)])
    stand = Point(150, 25)
    assert road_beyond_routes(face, TERRITORY, RULES,
                              lambda p: p.contains(stand)) == (None, [])


def test_no_territory_no_reading():
    face = box(0, 20, 200, 31)
    assert road_beyond_routes(face, None, RULES, _no_stand) == (None, [])
