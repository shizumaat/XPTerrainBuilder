"""#2238 (owner 2026-11-27T04:06Z, CYYZ FA: "If you can confirm the tunnel
roof/top has a hard deck, then it should be raised to be flush with the
taxiway surface"): past a pack deck's end line -- outside its ring, beyond
the end EDGE prolonged, corners included -- the ground is the route's, at
the roof's level; beside the deck between its end lines it keeps the bank."""
from __future__ import annotations

import types

from auto_patch_v2.constraints.edge_deck import _past_end
from shapely.geometry import Point

RING = ((0.0, 0.0), (20.0, 0.0), (20.0, 10.0), (0.0, 10.0))
DECK = types.SimpleNamespace(ring=RING)
ES = [types.SimpleNamespace(deck=DECK, line=((1.0, 0.0), (19.0, 0.0))),
      types.SimpleNamespace(deck=DECK, line=((1.0, 10.0), (19.0, 10.0)))]


def test_past_either_end_line_corners_included():
    for p in ((10.0, -1.0), (10.0, 11.5), (21.0, -0.8), (-1.5, 10.6)):
        assert _past_end(ES, Point(p)), p


def test_inside_or_beside_between_the_end_lines_is_not():
    for p in ((10.0, 5.0), (21.0, 5.0), (-2.0, 1.0)):
        assert not _past_end(ES, Point(p)), p


def test_the_run_on_squares_the_corner():
    assert not _past_end(ES, Point(21.0, 0.6))
    assert _past_end(ES, Point(21.0, 0.6), slack=1.0)
    assert not _past_end(ES, Point(21.0, 5.0), slack=1.0)
