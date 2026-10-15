"""RULINGS 2026-10-14p (3), #709: a building's small pieces (LEAF ground
groups, no part ``chain_min_height_m`` tall) ride its walls
(``placement_leaves.attach_leaves``).

The witness is KASE ``Garage_1`` (39.2169308, -106.8637059): five ground
groups, two walled (4.0 m, 2.5 m) 6.3 m apart, three leaves 0.6-2.3 m from
them — written as five pieces stepping 1.30 m.  One group here.
"""
from __future__ import annotations

import types

from auto_patch_v2.airport import anchor_rule as AR
from auto_patch_v2.airport import placement_leaves as PL

_D = 1.0 / 111_000.0


def _box(x0, x1):            # metres east along one latitude row
    return (39.0, -106.0 + x0 * _D * 1.29, 39.0 + 5 * _D, -106.0 + x1 * _D * 1.29)


def _raw(h, cls=AR.BUILDING, line=False):
    return ([types.SimpleNamespace(height_m=h, line=line)], cls, None, (1, 2, 3), False)


def _garage():
    # g0 wall | 2.3 m | g1 leaf | 1.8 m | g2 wall | 0.6 m | g3 leaf ; g4 leaf
    raw = [_raw(4.0), _raw(2.0), _raw(2.5), _raw(1.56), _raw(1.12)]
    boxes = [[_box(0, 5)], [_box(7.3, 9)], [_box(10.8, 20)], [_box(20.6, 25)],
             [_box(20.63, 22)]]
    return [[0], [1], [2], [3], [4]], raw, boxes


def test_the_garage_is_one_group():
    groups, raw, boxes = _garage()
    counts: dict = {}
    out = PL.attach_leaves(groups, raw, boxes, reach_m=2.5,
                           chain_min_height_m=2.5, counts=counts)
    assert out == [[0, 1, 2, 3, 4]]
    assert counts["leaf_groups_on_walls"] == 3
    assert counts["buildings_joined_by_pieces"] == 1


def test_out_of_reach_pieces_and_bare_walls_stay_apart():
    groups, raw, boxes = _garage()
    out = PL.attach_leaves(groups, raw, boxes, reach_m=0.5,
                           chain_min_height_m=2.5, counts={})
    # the 0.6 m panels are out of a 0.5 m reach; nothing joins
    assert sorted(map(tuple, out)) == [(0,), (1,), (2,), (3,), (4,)]
    # two walls with no piece between them never link directly
    out = PL.attach_leaves([[0], [2]], raw, boxes, reach_m=50.0,
                           chain_min_height_m=2.5, counts={})
    assert sorted(map(tuple, out)) == [(0,), (2,)]


def test_a_leaf_with_no_wall_and_the_own_law_classes_stay():
    groups, raw, boxes = _garage()
    raw[1] = _raw(2.0, cls=AR.LINE_SEGMENT)          # a fence keeps its drape
    out = PL.attach_leaves(groups, raw, boxes, reach_m=2.5,
                           chain_min_height_m=2.5, counts={})
    assert [1] in out and [0] in out                 # the fence broke the chain
    assert [2, 3, 4] in out
    assert PL.attach_leaves(groups, raw, boxes, reach_m=0.0,
                            chain_min_height_m=2.5, counts={}) == groups
