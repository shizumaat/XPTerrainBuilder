"""#2195 / #2196: a unit authored on two levels, its pieces on pads at both,
seats its LOW piece by its own walls (``airport/level_base``)."""
from __future__ import annotations

import pytest
from auto_patch_v2.airport.level_base import level_zeros


def test_the_low_piece_takes_its_own_walls_base():
    # a pit pad 15 m under the upper pads; the root base reads between them
    pieces = {"u/p0": ("u", 360.56, -5.83, -15.67),
              "u/p1": ("u", 375.57, -5.83, -23.0),
              "u/p2": ("u", 375.49, -5.83, -2.97)}
    counts: dict = {}
    got = level_zeros(pieces, 3.0, counts)
    assert got == {"u/p0": pytest.approx(376.23)} and counts["unit_level_bases"] == 1


def test_one_level_and_a_piece_its_own_walls_do_not_bring_closer_stay():
    assert level_zeros({"u/p0": ("u", 375.0, -1.0, -1.2), "u/p1": ("u", 376.0, -1.0, -0.8)},
                       3.0, {}) == {}
    # a low piece whose own walls read no nearer the high pieces keeps the root's
    assert level_zeros({"u/p0": ("u", 360.0, -5.0, -6.0), "u/p1": ("u", 375.0, -5.0, -5.0)},
                       3.0, {}) == {}
