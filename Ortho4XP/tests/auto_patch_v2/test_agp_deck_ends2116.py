"""Twins for #2116 (items 1, 3, 6): the ends of an AGP follower's driven
decks (``airport/agp_deck_ends``).  Synthetic floors in the frame (x, y,
authored height); the stacked-storey separation is passed as the law's
``[agp] connector_floor_m`` would be."""
from __future__ import annotations

import numpy as np
import pytest
from auto_patch_v2.airport.agp_deck_ends import _deck_ends, _end_line, _Floors, _vote
from shapely.geometry import LineString

STOREY = 2.5


def _slab(x0, x1, y0, y1, z0, z1=None):
    """Two triangles over [x0, x1] x [y0, y1], height z0 at x0 rising to z1 at x1."""
    z1 = z0 if z1 is None else z1
    a, b, c, d = (x0, y0, z0), (x1, y0, z1), (x1, y1, z1), (x0, y1, z0)
    return [(a, b, c), (a, c, d)]


def _floors(*slabs) -> _Floors:
    return _Floors(np.array([t for s in slabs for t in s], float))


def test_a_flat_deck_ends_where_its_floor_stops():
    fl = _floors(_slab(0.0, 40.0, -6.0, 6.0, 10.0))
    own = LineString([(5.0, 0.0), (60.0, 0.0)])
    got, why = _deck_ends(own, own, fl, STOREY)
    assert why == "" and len(got) == 1
    (p, u, top), = got
    assert p[0] == pytest.approx(40.0, abs=0.6) and u == pytest.approx((1.0, 0.0))
    assert top == pytest.approx(10.0, abs=0.01)
    line = _end_line(p, u, fl, top)
    assert line[0][1] == pytest.approx(-6.0, abs=0.6) and line[-1][1] == pytest.approx(6.0, abs=0.6)


def test_a_ramp_is_followed_to_its_end_and_its_top_read_there():
    """The deck descends past the bridge way's own end along its route; the
    end is where the RAMP stops, its top the ramp's height there."""
    fl = _floors(_slab(0.0, 30.0, -6.0, 6.0, 14.0), _slab(30.0, 90.0, -6.0, 6.0, 14.0, 10.0))
    own = LineString([(5.0, 0.0), (30.0, 0.0)])
    line = LineString([(5.0, 0.0), (150.0, 0.0)])
    (p, _u, top), = _deck_ends(line, own, fl, STOREY)[0]
    assert p[0] == pytest.approx(90.0, abs=0.6)
    assert top == pytest.approx(10.0, abs=0.1)


def test_a_deck_drawn_twice_reads_its_lower_copy():
    fl = _floors(_slab(0.0, 40.0, -6.0, 6.0, 10.0), _slab(0.0, 40.0, -6.0, 6.0, 11.0))
    own = LineString([(5.0, 0.0), (60.0, 0.0)])
    (_p, _u, top), = _deck_ends(own, own, fl, STOREY)[0]
    assert top == pytest.approx(10.0, abs=0.01)


def test_stacked_storeys_are_no_one_deck():
    best, why = _vote([[3.45, 6.75, 10.05]] * 6, STOREY)
    assert best is None and "stacked storeys" in why


def test_an_open_stretch_under_the_building_is_no_end():
    """The road leaves the deck and runs 5 m in the open before it comes
    back under a canopy of the same member: no end."""
    fl = _floors(_slab(0.0, 40.0, -6.0, 6.0, 10.0), _slab(45.0, 80.0, -6.0, 6.0, 18.0))
    own = LineString([(5.0, 0.0), (80.0, 0.0)])
    got, _why = _deck_ends(own, own, fl, STOREY)
    assert got == []


def test_a_slab_drawn_as_two_faces_is_one_level_its_top_the_upper():
    """A slab's two up faces 0.25 m apart, and a far copy 1 m over: the
    near pair is the deck (tie to the lower level), its top the upper face."""
    fl = _floors(_slab(0.0, 40.0, -6.0, 6.0, 9.0), _slab(0.0, 40.0, -6.0, 6.0, 9.25),
                 _slab(0.0, 40.0, -6.0, 6.0, 10.25))
    own = LineString([(5.0, 0.0), (60.0, 0.0)])
    (_p, _u, top), = _deck_ends(own, own, fl, STOREY)[0]
    assert top == pytest.approx(9.25, abs=0.01)


def test_past_an_agp_deck_end_the_whole_run_is_at_grade():
    """A mapped bridge running on 60 m past an AGP deck's graded end (run
    45 m): the whole run is at grade (no pack deck carries it); past a
    kept DSF deck's end only ``[bridge] free_end_run_on_max_m`` is."""
    from auto_patch_v2.airport import deck_stack as DS
    from auto_patch_v2.airport.agp_deck_ends import AGP_END_PREFIX
    from auto_patch_v2.law import Law
    from auto_patch_v2.model.airport import OsmWay
    from auto_patch_v2.model.deck_stack import KEPT, DeckStack, StackDeck, StackEnd
    law = Law.for_airport("")
    end = StackEnd("E", "a", ((0.0, -4.0), (0.0, 4.0)), 2.0, (1.0, 0.0), 8.0, 2.0, "graded", "",
                   ((0.0, 0.0), (60.0, 0.0)), 45.0, 0.05)
    deck = StackDeck("E", "", 0, ((-30.0, -6.0), (0.0, -6.0), (0.0, 6.0), (-30.0, 6.0)), 1,
                     (-1,), (), end.stations, (), 2.0, 0.0)

    def stack(bridge):
        return DeckStack(id="stack:" + bridge, walls_id="", walls_resource="",
                         members=(("E", ""),), zero_z=8.0, zero_spread_m=0.0, end_zeros=(),
                         feet_y=0.0, crest_y=0.0, floor=(), rim=(), runouts=(), under_ways=(),
                         decks=(deck,), kind=KEPT, ends=(end,), bridge=bridge)
    ways = [OsmWay(-1, "big_roads", ((-30.0, 0.0), (60.0, 0.0)), False,
                   {"highway": "primary", "bridge": "yes", "layer": "2"})]

    def at_grade(got):
        return sum(LineString(w.points).length for w in got if "bridge" not in w.tags)
    run_on = float(law.tables.structures.bridge.free_end_run_on_max_m)
    assert at_grade(DS._rewrite_ways(ways, [stack(AGP_END_PREFIX + "x")], law)) == \
        pytest.approx(45.0, abs=0.1)
    assert at_grade(DS._rewrite_ways(ways, [stack("kept:x")], law)) == \
        pytest.approx(run_on, abs=0.1)
