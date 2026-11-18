"""Twins for #2116 item 4: a mapped bore whose end goes on as a mapped
BRIDGE way is no portal there (``planar/bore_continuation.continues_on_deck``;
the road passes through a building at deck level, KDEN's arrivals and
commercial lanes).  Synthetic ways; law values read from the tables."""
from __future__ import annotations

import pytest
from auto_patch_v2.law import Law
from auto_patch_v2.model.airport import OsmWay
from auto_patch_v2.planar.bore_continuation import bridge_ends, continues_on_deck
from auto_patch_v2.planar.structure_approach import chains

_T = {"highway": "secondary", "tunnel": "yes", "layer": "-2"}
_B = {"highway": "secondary", "bridge": "yes", "layer": "1"}
_R = {"highway": "secondary"}


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


def test_a_bore_end_onto_a_bridge_is_no_portal(law):
    tn = law.tables.structures.tunnel
    bore_way = OsmWay(-1, "big_roads", ((0.0, 0.0), (0.0, 120.0)), False, _T)
    deck = OsmWay(-2, "big_roads", ((0.0, 120.0), (0.0, 160.0)), False, _B)
    road = OsmWay(-3, "big_roads", ((0.0, 0.0), (0.0, -200.0)), False, _R)
    (bore,) = chains([bore_way])
    ends = bridge_ends([bore_way, deck, road], tn.admitted_values)
    why = continues_on_deck(bore, (0.0, 120.0), ends)
    assert why is not None and "bridge way -2" in why and "#2116" in why
    # the other end runs on at grade: a portal as before
    assert continues_on_deck(bore, (0.0, 0.0), ends) is None


def test_a_bridge_crossing_over_the_portal_is_no_continuation(law):
    """Only a bridge way whose END is the bore's end node continues it; a
    bridge passing over elsewhere names nothing."""
    tn = law.tables.structures.tunnel
    bore_way = OsmWay(-1, "big_roads", ((0.0, 0.0), (0.0, 120.0)), False, _T)
    over = OsmWay(-2, "big_roads", ((-50.0, 60.0), (50.0, 60.0)), False, _B)
    (bore,) = chains([bore_way])
    ends = bridge_ends([bore_way, over], tn.admitted_values)
    assert continues_on_deck(bore, (0.0, 120.0), ends) is None
    assert continues_on_deck(bore, (0.0, 0.0), ends) is None
