"""Twins for issue #450 — A DECK HOLDS A MAPPED BORE'S CUT ONLY WHERE IT
STANDS OVER THE RAMP (``planar/structure_deck.decks_over_climb``): the
rule an object corridor's climb beyond its walls already had, now read by
an OSM bore too.  Found at OTHH (an object bridge 152-260 m out held 260 m
of trench at the mouth depth, where the owner reads a road at grade)."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

import test_m4b as M4B                                         # noqa: E402
from auto_patch_v2.classify.roles import Cell, Classification  # noqa: E402
from auto_patch_v2.law import Law                              # noqa: E402
from auto_patch_v2.planar.basins import read_objects           # noqa: E402
from auto_patch_v2.planar.structure_deck import decks_over_climb  # noqa: E402
from auto_patch_v2.planar.structures import build_structures   # noqa: E402


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


@pytest.fixture(scope="module")
def pack(tmp_path_factory):
    return M4B.objs.__wrapped__(tmp_path_factory)


def test_the_walk_keeps_the_decks_the_climb_is_still_under():
    """A 60 m free ramp.  A deck at 20-40 is over it; with the climb held
    to 41, the ramp tops at 101, so a deck at 90-95 is over it too; the
    deck at 300 crosses a road at grade — it and everything after it are
    not this corridor's."""
    top = lambda s: s + 60.0                                    # noqa: E731
    d1, d2, d3 = ("w1", 20.0, 40.0, None), ("w2", 300.0, 310.0, None), ("w3", 400.0, 410.0, None)
    o1 = ("o1", 90.0, 95.0, None, 9.0)
    assert decks_over_climb([d1, d2, d3], [o1], 1.0, top) == ([d1], [o1])
    assert decks_over_climb([d2], [], 1.0, top) == ([], [])
    assert decks_over_climb([], [], 1.0, top) == ([], [])
    # the ground is never reached: every deck is kept, as before
    assert decks_over_climb([d1, d2], [o1], 1.0, lambda s: None) == ([d1, d2], [o1])


def _bore_with_bridge(pack, law, x_bridge):
    airport = M4B._airport(pack, law, [("bridge", (x_bridge, -6.0), 90.0, 0.0)],
                           M4B._tunnel_ways()[:3])
    cells = [Cell(0, "runway", "09/27", M4B._rect(-600, 500, 600, 545), (), 3, "D", "airside",
                  "runway", {}),
             Cell(1, "apron", "apron1", M4B._rect(-80, -60, 80, 60), (), None, None, "airside",
                  "apron", {})]
    objects, _rep = read_objects(airport, law)
    _cl, tunnels, st = build_structures(airport, Classification(tuple(cells), (), {}, ()), law,
                                        objects)
    return next(t for t in tunnels if t.axis[0][0] > 0), st


def test_a_bridge_far_beyond_the_ramps_top_holds_no_cut(pack, law):
    """The east mouth is at x = 80 and the free ramp reaches the ground
    ``bore_datum_m / ramp_max_grade`` out.  An object bridge four ramp
    lengths away crosses a road at grade: the climb starts AT the mouth and
    the bridge is no deck of this tunnel.  The same bridge half a ramp
    length out stands over the ramp and still holds the cut under it."""
    tn = law.tables.structures.tunnel
    run = tn.bore_datum_m / tn.ramp_max_grade
    far, _st = _bore_with_bridge(pack, law, 80.0 + 4.0 * run)
    assert far.climb_from_s == 0.0 and not far.decks
    assert far.top_s < 2.0 * run
    near, st = _bore_with_bridge(pack, law, 80.0 + 0.5 * run)
    assert st.object_decks == 1 and len(near.decks) == 1
    assert near.climb_from_s >= near.decks[0].s1
