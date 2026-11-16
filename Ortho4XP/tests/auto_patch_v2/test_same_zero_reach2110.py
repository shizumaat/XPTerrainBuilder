"""#2110 (owner sim read LOWS 1.0.539, 47.791519, 12.997848): the §9
same-zero join of a carried body into one of its own placement's groups
obeys §16b (1) — zero agreement is necessary, not sufficient; the group
must be contiguous in plan within the coarsen reach.  LOWS's
Terminal_LOWS_77 put 245 terminal pieces in the file of a 2-part foot
290 m east, which the unit seat and the group zero then sank 1.38 m under
the walls they rest on."""
from __future__ import annotations

import types

from auto_patch_v2.airport.placement_boxes import group_at_zero

M_LAT = 1.0 / 111132.0


def _raw(z: float) -> tuple:
    a = types.SimpleNamespace(surface_z=z, y_zero=0.0)
    return ([], "building", a, (), False, (), None, None)


def _box(north_m: float) -> tuple:
    la = 47.79 + north_m * M_LAT
    return (la, 13.0, la + 2 * M_LAT, 13.0 + 0.00003)


def _senior(_raw, g):
    return g[0]


def test_far_group_at_the_same_zero_does_not_take_the_body() -> None:
    raw = [_raw(432.03), _raw(432.03)]
    groups = [[0], [1]]
    boxes = [_box(0.0), _box(290.0)]
    near = [_box(2.0)]
    # near group 0 joins (contiguous), the far group 1 never does
    assert group_at_zero(groups, raw, 432.03, 0.05, _senior, near=near,
                         boxes=boxes, reach_m=100.0) == 0
    assert group_at_zero([[1]], raw, 432.03, 0.05, _senior, near=near,
                         boxes=boxes, reach_m=100.0) == -1


def test_no_reach_is_the_old_reading() -> None:
    raw = [_raw(432.03)]
    boxes = [_box(290.0)]
    near = [_box(0.0)]
    assert group_at_zero([[0]], raw, 432.03, 0.05, _senior, near=near,
                         boxes=boxes, reach_m=0.0) == 0
    assert group_at_zero([[0]], raw, 432.03, 0.05, _senior) == 0
