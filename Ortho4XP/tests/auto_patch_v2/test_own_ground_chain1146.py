"""#1146 (KLAX people-mover rail): ONE CONNECTED STRUCTURE TAKES ONE SEAT.
The own-ground pieces of one member (§16 (3): footless, no carrier) that
touch chain into one structure written at one zero, their authored
heights kept relative to each other; a piece touching none keeps its own
ground (``placement_file.own_ground_zeros``)."""
from __future__ import annotations

import pytest
from auto_patch_v2.airport.placement_file import own_ground_zeros

M = 1.0 / 111_132.0            # one metre of latitude


def _box(m0, m1):
    return (41.0 + m0 * M, -3.0, 41.0 + m1 * M, -2.9995)


def test_touching_pieces_share_one_zero_and_a_lone_piece_keeps_its_ground():
    part_boxes = [[_box(0, 40)], [_box(40, 80)], [_box(80, 120)], [_box(500, 520)]]
    ground = {0: 30.0, 1: 30.4, 2: 31.0, 3: 35.0}

    def surface(la, lo):
        m = (la - 41.0) / M
        return ground[0 if m < 40 else 1 if m < 80 else 2 if m < 200 else 3]

    got = own_ground_zeros([[0], [1], [2], [3]], part_boxes, surface, touch_m=0.5)
    assert got[0] == got[1] == got[2] == pytest.approx(30.4)   # the chain's median
    assert got[3] is None


def test_no_touch_distance_chains_nothing():
    part_boxes = [[_box(0, 40)], [_box(40, 80)]]
    assert own_ground_zeros([[0], [1]], part_boxes, lambda la, lo: 1.0, 0.0) == [None, None]


def test_a_chain_of_a_member_its_units_hold_takes_their_seat():
    part_boxes = [[_box(0, 40)], [_box(40, 80)]]
    got = own_ground_zeros([[0], [1]], part_boxes, lambda la, lo: 30.0, 0.5,
                           held=[32.72, 31.30])
    assert got == [pytest.approx(32.01), pytest.approx(32.01)]
