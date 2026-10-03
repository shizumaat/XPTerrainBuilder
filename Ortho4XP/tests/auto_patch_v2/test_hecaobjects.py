"""Lane ``hecaobjects`` (issues #289 / #290, HECA app 1.0.371 sim reads).

#289: ``footprint_unit.contents_seat``'s railway carve-out (owner 09-18s)
is read on the piece's own PARTS and only where the plan-wide map calls
the piece a connector — a scatter of terminal panes chained 240-331 m by
§16c (7), or one 331 m roof slab of the terminal's own unit, is contents,
not a railway.

#290: a piece carried by a DECK whose lowest part stands on the deck's
authored surface keeps its deck (§16e (3)): the deck and its furniture
are one rigid assembly.  ``bridge_family.DeckPrint.top_at`` reads that
surface where the part stands (a ramp is not one height), with the
``[deck] edge_m`` reach for a parapet on the deck's edge.  Hermetic.
"""
from __future__ import annotations

import types

from auto_patch_v2.airport import anchor_rule as AR
from auto_patch_v2.airport import bridge_family as BF
from auto_patch_v2.airport import footprint_unit as FU
from auto_patch_v2.airport import placement_plan as PP

U_ZERO = 102.56
TOL = 0.3
BOX = (40.0, -3.0, 40.0001, -2.9999)
LONG = (40.0, -3.0, 40.003, -2.997)                 # ~420 m diagonal
PW = {1: ("fu:0:0/b1", U_ZERO, "building4/b1", "cluster_pad"),
      2: ("fu:0:0/b1", U_ZERO, "building4/b1", "cluster_pad"),
      # a CUT connector's row: two ends and the plan's verdict
      7: ("fu:0:0/b1", U_ZERO, "building4/b1", "cluster_pad",
          ("fu:0:0/b1", "fu:0:9"), ("fu:0:9", 95.0, "", "ground"), "cut")}
INDEX = {"fu:0:0/b1": (BOX, (BOX,), U_ZERO, "building4/b1", "cluster_pad")}


def _cand(name: str, zero: float, cls: str = "building",
          surface_z: float = 100.0):
    a = AR.Anchor(cls, 40.0, -3.0, surface_z - zero, "test", surface_z)
    return types.SimpleNamespace(anchor=a, resource=name, body_class=cls)


def test_a_scattered_piece_of_short_parts_is_contents_not_a_railway():
    """HECA T3 b1: ``360_room``/``T2_glass`` panes whose PIECE hull reads
    240 m rode ``green_glass__b5`` on block b0, 2.64 m under their own
    block; no one part is connector-length, so they take their unit."""
    on_b0 = _cand("green_glass__b5.obj", 99.92)
    over = [(on_b0, "§16c (7) bound by contact")]
    out, uc = FU.contents_seat(over, frozenset({1, 2}), LONG, PW, INDEX,
                               tol_m=TOL, span_max_m=200.0,
                               piece_boxes=[BOX, BOX])
    assert out == [] and uc is not None and uc.unit == "fu:0:0/b1"
    # the pre-fix reading (the piece hull) kept the carrier on b0
    out0, uc0 = FU.contents_seat(over, frozenset({1, 2}), LONG, PW, INDEX,
                                 tol_m=TOL, span_max_m=200.0)
    assert uc0 is None and out0 == over


def test_a_long_part_of_the_units_own_is_not_the_carve_out():
    """T3's 331 m roof slab (13,148 m2) is a member of the terminal's unit:
    the plan names no connector, so its piece rides the unit."""
    on_b4 = _cand("metal_titles__b4.obj", 99.29)
    out, uc = FU.contents_seat([(on_b4, "rests on it")], frozenset({1}),
                               LONG, PW, INDEX, tol_m=TOL, span_max_m=200.0,
                               piece_boxes=[LONG])
    assert out == [] and uc is not None


def test_a_long_part_the_plan_calls_a_connector_keeps_the_carve_out():
    rail = _cand("concrete_3__b1.obj", 90.0)
    over = [(rail, "x")]
    out, uc = FU.contents_seat(over, frozenset({7}), LONG, PW, INDEX,
                               tol_m=TOL, span_max_m=200.0,
                               piece_boxes=[LONG])
    assert uc is None and out == over


def _ramp() -> BF.DeckPrint:
    """A 2-triangle deck 100 m long: y 0 at lat 40.0, y 10 at lat 40.0009."""
    a, b = (40.0, -3.0), (40.0, -2.9998)
    c, d = (40.0009, -2.9998), (40.0009, -3.0)
    p = BF.DeckPrint(key="T3_road.obj", unit=0, member=5, under_y=0.0,
                     box=(40.0, -3.0, 40.0009, -2.9998),
                     tris=((a, b, c), (a, c, d)),
                     ys=((0.0, 0.0, 10.0), (0.0, 10.0, 10.0)))
    p.index()
    return p


def test_the_deck_surface_is_read_where_the_part_stands():
    p = _ramp()
    assert abs(p.top_at(40.00045, -2.9999) - 5.0) < 1e-6
    assert p.top_at(40.0005, -2.9990) is None              # 77 m off
    # a parapet 3 m off the deck's east edge, with the 6 m edge reach
    y = p.top_at(40.00045, -2.9998 + 3.0 / 85_000.0, reach_m=6.0)
    assert y is not None and abs(y - 5.0) < 0.05


def _part(lat, lon, base_y):
    return types.SimpleNamespace(lat=lat, lon=lon, base_y=base_y)


def test_a_railing_on_the_deck_is_a_rider_and_facade_glass_is_not():
    p = _ramp()
    rail = [_part(40.00045, -2.9999, 5.1), _part(40.0005, -2.9999, 6.6)]
    assert PP._deck_rider(p, rail, 1.0, 6.0)
    # facade glass beside the viaduct reaching 4 m BELOW the surface
    glass = [_part(40.00045, -2.9999, 1.0), _part(40.0005, -2.9999, 6.0)]
    assert not PP._deck_rider(p, glass, 1.0, 6.0)
    # a floor slab 40 m from the deck is not over it at all
    slab = [_part(40.00045, -2.9994, 5.0)]
    assert not PP._deck_rider(p, slab, 1.0, 6.0)
    assert not PP._deck_rider(None, rail, 1.0, 6.0)


def test_a_deck_rider_keeps_its_deck_whatever_its_zero():
    """#290: T3_road's lamp posts were moved by #10 onto the terminal's
    datum 6.17 m above the road they stand on."""
    deck = _cand("T3_road__b1.obj", 93.12, cls="deck")
    over = [(deck, "rests on it")]
    counts: dict = {}
    out, uc = FU.contents_seat(over, frozenset({1}), BOX, PW, INDEX,
                               tol_m=TOL, span_max_m=200.0, counts=counts,
                               deck_rider=lambda c: True)
    assert uc is None and out == over
    assert counts[FU.CONTENTS_SEAT + "_kept_deck_rider"] == 1
    # not a rider (facade glass over the deck in plan): #10 still reroutes
    out2, uc2 = FU.contents_seat(over, frozenset({1}), BOX, PW, INDEX,
                                 tol_m=TOL, span_max_m=200.0,
                                 deck_rider=lambda c: False)
    assert out2 == [] and uc2 is not None
    # a non-deck carrier is never asked
    side = _cand("side_walk__b2.obj", 93.12)
    out3, uc3 = FU.contents_seat([(side, "x")], frozenset({1}), BOX, PW,
                                 INDEX, tol_m=TOL, span_max_m=200.0,
                                 deck_rider=lambda c: True)
    assert out3 == [] and uc3 is not None
