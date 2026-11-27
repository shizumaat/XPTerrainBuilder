"""#2239 / #2241: a deck's end edge runs corner to corner past the pavement
contact (``geom/deck_end_edge``; owner 2026-11-26 "the weld must span the
deck's full width including shoulders"), and the bank under a banked deck
hangs from that edge (``constraints/edge_deck._bank_drop``)."""
from __future__ import annotations

import types

from auto_patch_v2.constraints.edge_deck import _bank_drop
from auto_patch_v2.geom.deck_end_edge import end_edge, on_edge
from shapely.geometry import LineString, Point

#: a 68 x 28 m deck, the road along x under it, the taxiway driving on at y = 0 / 28
RING = [(0.0, 0.0), (30.0, 0.0), (68.0, 0.0), (68.0, 28.0), (40.0, 28.4), (0.0, 28.0)]
#: the pavement meets the south side over 10-60 m only (shoulders past it)
LINE_A = [(float(x), 0.0) for x in range(10, 61, 5)]
LINE_B = [(float(x), 28.0) for x in range(12, 59, 5)]


def test_the_edge_runs_corner_to_corner_along_the_side():
    e = end_edge(RING, LINE_A)
    assert abs(LineString(e).length - 68.0) < 1e-9
    assert e[0] == (0.0, 0.0) and e[-1] == (68.0, 0.0)
    b = end_edge(RING, LINE_B)             # a slight kink in the side is still the side
    assert {b[0], b[-1]} == {(68.0, 28.0), (0.0, 28.0)}
    assert on_edge((2.0, 0.1), e, 0.35) and not on_edge((2.0, 1.0), e, 0.35)


def test_the_edge_wraps_past_the_first_vertex():
    ring = RING[1:] + RING[:1]
    e = end_edge(ring, LINE_A)
    assert abs(LineString(e).length - 68.0) < 1e-9


def test_the_bank_hangs_from_the_full_edge():
    deck = types.SimpleNamespace(ring=RING)
    es = [types.SimpleNamespace(deck=deck, line=LINE_A, depth=7.5)]
    # on the shoulder at the deck's edge the bank is flush (it was 5 m x slope)
    assert _bank_drop(es, Point(5.0, 0.0), 0.5) == 0.0
    assert abs(_bank_drop(es, Point(5.0, 2.0), 0.5) - 1.0) < 1e-9
    assert _bank_drop(es, Point(30.0, 20.0), 0.5) == 7.5
