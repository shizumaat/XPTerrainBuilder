"""D1 (owner RULINGS 2026-10-14n, #709): a scatter member one of whose
parts has a ground foot and stands at least ``chain_min_height_m`` tall is
a structure, not scatter (``scatter.standing_members``).

KASE ``Garage_1`` (39.2169308, -106.8637059): 83 wall panels of 10 m or
less read SCATTER, never clustered, and were cut into five pieces seated
1.30 m apart.  A bush (short) or a leaf clump (no ground foot) stays scatter.
"""
from __future__ import annotations

import numpy as np

from auto_patch_v2.airport import scatter as SC

_FOOT = np.array([[39.0, -106.0, 0.0]])
_NONE = np.zeros((0, 3))


def _rows(*parts):
    """``(feet, rings, solid_h)`` per part — ``contact.part_attrs``'s shape."""
    return [(feet, (), h) for feet, h in parts]


def test_a_walled_scatter_member_is_a_structure():
    attrs = [_rows((_FOOT, 4.8), (_FOOT, 0.3)),      # the garage: a 4.8 m wall
             _rows((_FOOT, 1.2), (_FOOT, 0.8)),      # bushes: all short
             _rows((_NONE, 6.0))]                    # a leaf clump: no foot
    got = SC.standing_members([None] * 3, {0, 1, 2}, attrs, 2.5, ())
    assert got == {0}


def test_only_scatter_members_are_asked_and_zero_disarms():
    attrs = [_rows((_FOOT, 4.8)), _rows((_FOOT, 4.8))]
    assert SC.standing_members([None] * 2, {1}, attrs, 2.5, ()) == {1}
    assert SC.standing_members([None] * 2, {0, 1}, attrs, 0.0, ()) == set()


def test_the_threshold_is_the_chain_height_inclusive():
    attrs = [_rows((_FOOT, 2.5)), _rows((_FOOT, 2.49))]
    assert SC.standing_members([None] * 2, {0, 1}, attrs, 2.5, ()) == {0}
