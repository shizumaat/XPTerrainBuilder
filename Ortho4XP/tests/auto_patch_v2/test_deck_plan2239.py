"""#2239 / #2241 (spec cyyz-decks-r3 §2): one derivation of a deck's plan
(``geom/deck_plan``) -- its bands, floor, square mouth zone and aprons --
and the ring the deck owns (``planar/deck_ring_cut``)."""
from __future__ import annotations

import types

from auto_patch_v2.geom.deck_plan import plan, prolonged, safe_band
from auto_patch_v2.planar.deck_ring_cut import cut_decks
from shapely.geometry import Point, Polygon

#: a 68 x 28 m deck, the road along x under it, the taxiway driving on at y = 0 / 28
RING = [(0.0, 0.0), (68.0, 0.0), (68.0, 28.0), (0.0, 28.0)]
EDGE_A = [(0.0, 0.0), (68.0, 0.0)]
EDGE_B = [(68.0, 28.0), (0.0, 28.0)]


def _law(ring_floor=0.7071):
    cut = types.SimpleNamespace(ring_floor_m=ring_floor)
    return types.SimpleNamespace(tables=types.SimpleNamespace(
        structures=types.SimpleNamespace(cutout=cut)))


def test_the_safe_band_is_two_cells():
    assert abs(safe_band(_law()) - 1.4142) < 1e-9


def test_an_edge_is_prolonged_along_its_own_ends():
    p = prolonged(EDGE_A, 5.0)
    assert p[0] == (-5.0, 0.0) and p[-1] == (73.0, 0.0)


def test_bands_floor_mouth_and_apron():
    dp = plan(RING, EDGE_A, EDGE_B, 1.5)
    a, b = dp.bands()
    # each band stands on the deck's side of its edge, run past the corners
    assert a.contains(Point(-3.0, 0.7)) and not a.contains(Point(10.0, -0.7))
    assert b.contains(Point(80.0, 27.3))
    fl = dp.floor()
    assert fl.contains(Point(34.0, 14.0)) and fl.contains(Point(-10.0, 14.0))
    assert not fl.contains(Point(34.0, 0.7)) and not fl.contains(Point(34.0, 27.3))
    # the mouth zone: beyond the ring between the edges, squared at the footprint
    outer = Polygon([(-12.0, -3.0), (80.0, -3.0), (80.0, 31.0), (-6.0, 31.0)])
    mz = dp.mouth_zone(outer)
    assert mz.contains(Point(-11.0, 14.0)) and mz.contains(Point(79.0, 2.0))
    assert not mz.contains(Point(-13.0, 14.0)) and not mz.contains(Point(34.0, 14.0))
    assert not mz.contains(Point(34.0, -1.0))
    # the apron: outside edge A, corner to corner
    ap = dp.apron(0, 2.0)
    assert ap.contains(Point(1.0, -1.0)) and ap.contains(Point(67.0, -1.9))
    assert not ap.contains(Point(30.0, 1.0)) and not ap.contains(Point(-1.0, -1.0))


def test_the_decks_with_a_cut_under_them():
    def deck(oid, cut="none", members=()):
        return types.SimpleNamespace(object_id=oid, cut=cut, members=members, family="taxi",
                                     resource="x.obj", witness="hard_deck")
    decks = [deck("d1", "walls"), deck("d2"), deck("d3", members=("p3",)), deck("d4")]
    tunnels = [types.SimpleNamespace(deck_bridge="d2", objects=()),
               types.SimpleNamespace(deck_bridge="", objects=("p3",))]
    assert [d.object_id for d in cut_decks(decks, tunnels)] == ["d1", "d2", "d3"]


def test_a_shell_under_its_cover_floors_between_the_bands_and_ends_square():
    from auto_patch_v2.planar.structure_geometry import _under_cover
    cover = Polygon(RING)
    # the footprint cut back to the cover's sides, reaching 12 / 6 m past the mouths
    outer = Polygon([(-12.0, 0.0), (80.0, 0.0), (80.0, 28.0), (-6.0, 28.0)])
    ramp = Polygon([(-10.0, 1.0), (78.0, 1.0), (78.0, 27.0), (-5.0, 27.0)])
    inside = outer.buffer(-2.0, join_style="mitre")
    out2, ins2, ramp2 = _under_cover(outer, inside, ramp, (cover, 1.5, (EDGE_A, EDGE_B)))
    # under the cover the floor stands the band inside each side, never the wall's 2 m
    assert ins2.contains(Point(34.0, 1.7)) and not ins2.contains(Point(34.0, 1.3))
    # and beyond the mouth the cut is square to the trench's farthest reach,
    # never past it into the footprint's wing band
    assert out2.contains(Point(-9.5, 26.0)) and ins2.contains(Point(-9.5, 26.0))
    assert ramp2.contains(Point(-9.5, 14.0)) and not ramp2.contains(Point(-11.0, 14.0))
