"""#2099 R3 Part B twin (spec ``docs/specs/2099-R3.md`` §2 B1, §7 T3): two
decks on one road are one trench only where the corridor AS BUILT between
them is clear of the airside cut roles (``planar/structure_overlap.
deck_partner`` with its corridor width)."""
from __future__ import annotations

from auto_patch_v2.model.structures import DeckBridge
from auto_patch_v2.planar.structure_overlap import deck_partner
from shapely.geometry import LineString, box


def _deck(oid: str, y0: float) -> DeckBridge:
    ring = tuple(box(-15.0, y0, 15.0, y0 + 30.0).exterior.coords[:-1])
    return DeckBridge(oid, "deck.obj", (oid,), ring, ((-15.0, y0), (-15.0, y0 + 30.0)),
                      ((15.0, y0 + 30.0), (15.0, y0)), 0.0, 0.0, -7.5, 100.0)


A, B = _deck("a", -15.0), _deck("b", 185.0)
AXIS = LineString([(0.0, 0.0), (0.0, 400.0)])
HALF = 3.5 + 0.6 + 1.0 + 0.6            # half + rim stand-off + gap


def test_an_apron_beside_the_corridor_but_off_its_centre_line_parts_the_decks():
    apron = box(4.0, 80.0, 60.0, 120.0)            # 4 m off the road's centre line
    assert deck_partner(A, AXIS, (A, B), apron) is B          # the centre line alone: paired
    assert deck_partner(A, AXIS, (A, B), apron, HALF) is None


def test_clear_ground_between_two_decks_pairs_them_as_today():
    far = box(30.0, 80.0, 60.0, 120.0)
    assert deck_partner(A, AXIS, (A, B), far, HALF) is B
    assert deck_partner(A, AXIS, (A, B), None, HALF) is B
