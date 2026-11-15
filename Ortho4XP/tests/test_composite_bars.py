"""``tools/composite_bars.py`` (#2077 round 2, spec 9.4; twin T5): the
judged set of a relief skin's feet.  A zero-level cell is the lowest wall
vertex over all non-skin members per 5 m cell; a foot on the set's own
deck, in the quay metre, outside the footprint, over water or authored on
the author's terrace is listed, never judged; a foot authored at +0.50 m
on a perfect plane passes.  Synthetic solids, no corpus."""
from __future__ import annotations

import os
import sys

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "tools"))

import composite_bars as CB  # noqa: E402


def _wall(x, z, y0, y1):
    """A 1 m wall (two vertical triangles) at (x, z) from y0 to y1."""
    a, b = np.array([x, y0, z]), np.array([x + 1.0, y0, z])
    c, d = np.array([x + 1.0, y1, z]), np.array([x, y1, z])
    return [np.array([a, b, c]), np.array([a, c, d])]


def _deck(x, z, y):
    a, b, c, d = (np.array(p, float) for p in ((x, y, z), (x + 4, y, z), (x + 4, y, z + 4),
                                                (x, y, z + 4)))
    return [np.array([a, b, c]), np.array([a, c, d])]


def test_t5_the_lowest_wall_vertex_over_all_members_per_cell():
    m1 = np.array(_wall(1.0, 1.0, 0.2, 5.0))
    m2 = np.array(_wall(2.0, 2.0, -0.3, 4.0) + _deck(0.0, 0.0, 9.0))   # same cell, lower
    m3 = np.array(_wall(11.0, 1.0, 2.0, 6.0))
    cells = CB.foot_cells([m1, m2, None, m3])
    by = {(int(i), int(j)): (float(y), int(m)) for i, j, y, m in
          zip(cells["i"], cells["j"], cells["y"], cells["member"], strict=True)}
    assert by[(0, 0)] == (-0.3, 1)
    assert by[(2, 0)] == (2.0, 3)
    assert len(by) == 2                    # the deck is no wall


def test_t5_the_judged_set():
    decks = CB.deck_index([np.array(_deck(0.0, 0.0, -0.4))])
    # feet: on a deck (over water), on land plain, in the quay metre, a
    # terrace foot, outside the footprint, +0.50 on a perfect plane
    i = np.array([0, 5, 6, 7, 8, 9])
    j = np.zeros(6, int)
    y = np.array([0.1, 0.0, 0.2, -4.0, 0.0, 0.5])
    deck = CB.on_deck(i, j, y, decks)
    assert deck.tolist() == [True, False, False, False, False, False]
    infp = np.array([True, True, True, True, False, True])
    water_d = np.array([0.0, 30.0, 1.2, 50.0, 40.0, 25.0])
    under = np.zeros(6, bool)
    lab = CB.classify_feet(y, deck, infp, water_d, under, 1.0)
    assert lab.tolist() == ["deck_water", "judged", "quay", "terrace", "outside", "judged"]
    plane = 429.5
    ground = np.array([415.0, plane - 0.4, plane - 3.0, plane - 9.0, plane - 5.0, plane])
    fail = CB.judge_feet(lab, ground, plane)
    assert not fail.any()                  # +0.50 on the plane passes; listed never judged
    ground[1] = plane - 0.6
    assert CB.judge_feet(lab, ground, plane).tolist() == [False, True, False, False, False, False]
    # a deck on land is listed too, and a foot under a terrain member's top
    lab2 = CB.classify_feet(np.zeros(2), np.array([True, False]), np.ones(2, bool),
                            np.full(2, 30.0), np.array([False, True]), 1.0)
    assert lab2.tolist() == ["deck_land", "under_terrain"]
