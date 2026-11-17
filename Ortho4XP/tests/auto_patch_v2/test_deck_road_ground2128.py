"""#2128 twins (KIAH sim read 2026-11-16, 1 m lidar): a road crossing a
wall-less deck on its end bank is not bored by it (``planar/deck_bores``);
a mapped bore that passes under a pack hard deck near its end has that
deck as the end's portal witness (``planar/end_witness``)."""
from __future__ import annotations

import types

from auto_patch_v2.law import Law
from auto_patch_v2.model.airport import OsmWay
from auto_patch_v2.planar import deck_bores as DBO
from auto_patch_v2.planar import deck_bridge as DB
from auto_patch_v2.planar.structure_underpass import UNDERPASS_TAG
from shapely.geometry import box as _sbox

LAW = Law.for_airport("")


def _deck():
    """A 200 m wall-less deck (end lines x = -100 / +100), 5 m deep, 30 m
    across the road under it."""
    ring = tuple(_sbox(-100.0, -15.0, 100.0, 15.0).exterior.coords[:-1])
    a = tuple((-100.0, y) for y in (-10.0, 0.0, 10.0))
    b = tuple((100.0, y) for y in (-10.0, 0.0, 10.0))
    return DB.DeckBridge("dsf:obj1", "objects/deck.obj", ("dsf:obj1",), ring, a, b,
                         1.5, 1.5, -3.5, 30.0)


def _road(wid, x):
    return OsmWay(wid, "airport_small_roads", ((x, -200.0), (x, 200.0)), False,
                  {"highway": "service"})


def test_a_road_on_the_end_bank_is_not_bored_one_on_the_floor_is():
    """KIAH obj24614 (#2128 item 3): the airside service road 6.9 m inside an
    end line -- its carriageway clear of the line, but on the bank the
    ground climbs from the floor to the deck on -- crosses at grade; a road
    past the bank's run passes under."""
    db = _deck()
    bank = db.depth_m / float(LAW.tables.structures.channel.bank_slope)
    on_bank, on_floor = _road(-1, -91.0), _road(-2, -100.0 + bank + 3.0)
    ways, _p, notes = DBO.deck_bores((db,), [on_bank, on_floor], [], LAW, UNDERPASS_TAG)
    assert [w.id for w in ways] == [-2]
    assert any("not bored (#2128)" in n and "-1" in n for n in notes)


def test_a_hard_deck_over_the_bore_near_its_end_witnesses_that_end():
    """KIAH obj24551 (#2128 item 4): the service bore -3337 is mapped 23 m
    past the deck's edge; the deck over it is that end's portal witness.
    A deck beyond the approach's reach witnesses nothing; nor does one the
    bore only grazes."""
    from auto_patch_v2.planar.end_witness import EndWitness
    from shapely.geometry import LineString
    deck = _sbox(23.0, -15.0, 53.0, 15.0)
    on_field = types.SimpleNamespace(deck_polys=[deck], corridor_prints=[], portal_ends=[],
                                     airport=None)
    w = EndWitness(on_field, LAW)
    bore = LineString([(0.0, 0.0), (76.0, 0.0)])
    assert w.at((0.0, 0.0), [(0.0, 0.0), (-50.0, 0.0)]) is None          # end only: too far
    assert w.at((0.0, 0.0), [(0.0, 0.0), (-50.0, 0.0)], bore) == \
        "a pack hard deck over the bore near it"
    assert w.at((76.0, 0.0), [(76.0, 0.0), (126.0, 0.0)], bore) is not None
    long = LineString([(0.0, 0.0), (600.0, 0.0)])
    far = EndWitness(types.SimpleNamespace(deck_polys=[_sbox(400.0, -15.0, 430.0, 15.0)],
                                           corridor_prints=[], portal_ends=[], airport=None),
                     LAW)
    assert far.at((0.0, 0.0), [(0.0, 0.0), (-50.0, 0.0)], long) is None
    graze = EndWitness(types.SimpleNamespace(deck_polys=[_sbox(23.0, 0.0, 53.0, 30.0)],
                                             corridor_prints=[], portal_ends=[], airport=None),
                       LAW)
    assert graze.at((0.0, 0.0), [(0.0, 0.0), (-50.0, 0.0)], bore) is None
