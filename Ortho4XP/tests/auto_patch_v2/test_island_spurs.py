"""A centreline that is a hole's only tie is a bridge polygonize drops;
``classify/island_spurs`` gives the hole a second tie so the centreline
bounds two faces (follow-up of #2244: EKVG's taxiway C into a runway
painted inside one field-wide pavement polygon)."""
from __future__ import annotations

import shapely
from auto_patch_v2.classify.island_spurs import island_spurs
from auto_patch_v2.classify.rules import load_rules
from shapely.geometry import LineString, Polygon, box

RULES = load_rules()
#: a field-wide pavement 20 m round a 1,000 x 30 m runway, which the
#: region excludes (a hole)
FIELD = box(-20.0, -20.0, 1020.0, 50.0)
RUNWAY = box(0.0, 0.0, 1000.0, 30.0)
REGION = FIELD.difference(RUNWAY)


def _bounds_a_face(line: LineString, cuts: list[LineString]) -> bool:
    lines = [LineString(REGION.exterior.coords)] + \
        [LineString(h.coords) for h in REGION.interiors] + [line, *cuts]
    noded = shapely.unary_union(lines)
    faces = shapely.get_parts(shapely.polygonize([noded]))
    edges = shapely.union_all([f.boundary for f in faces])
    return edges.buffer(0.01).contains(line.interpolate(0.5, normalized=True))


def test_a_hole_tied_once_is_spurred_and_the_tie_bounds_faces():
    taxi = LineString([(500.0, 50.0), (500.0, 30.0)])   # outer edge -> runway edge
    assert not _bounds_a_face(taxi, [])                  # the bridge: dropped
    spurs = island_spurs([taxi], REGION, RULES)
    assert len(spurs) == 1
    assert 0.0 < spurs[0].length <= RULES.keyhole.max_spur_m
    assert REGION.buffer(0.01).contains(spurs[0])
    assert _bounds_a_face(taxi, spurs)


def test_a_hole_tied_twice_or_never_is_left_alone():
    a = LineString([(300.0, 50.0), (300.0, 30.0)])
    b = LineString([(700.0, 50.0), (700.0, 30.0)])
    assert island_spurs([a, b], REGION, RULES) == []
    assert _bounds_a_face(a, [b])
    far = LineString([(300.0, 50.0), (300.0, 45.0)])    # touches no hole
    assert island_spurs([far], REGION, RULES) == []


def test_no_spur_beyond_the_keyhole_reach():
    wide = box(-100.0, -100.0, 1100.0, 130.0).difference(RUNWAY)   # 70+ m all round
    taxi = LineString([(500.0, 130.0), (500.0, 30.0)])
    assert island_spurs([taxi], wide, RULES) == []


def test_a_polygon_without_holes_is_untouched():
    taxi = LineString([(500.0, 50.0), (500.0, -20.0)])
    assert island_spurs([taxi], Polygon(FIELD.exterior.coords), RULES) == []
