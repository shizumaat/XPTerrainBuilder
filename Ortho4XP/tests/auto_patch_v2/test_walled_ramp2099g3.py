"""#2099 G3 Part A twin (spec ``docs/specs/2099-G3.md``): a hard-deck
corridor whose mouth group's walls line its approach and witness a climb is
a RAMP to its walls' end, never paired with a further deck
(``planar/structure_overlap.walled_ramp``, read by both callers of the
pairing: ``planar/structures`` and ``planar/deck_bores._runs_through``).
Two decks with level-footed walls between them pair as before."""
from __future__ import annotations

from auto_patch_v2.law import Law
from auto_patch_v2.model.structures import DeckBridge
from auto_patch_v2.planar import deck_bores as DBO
from auto_patch_v2.planar.structure_overlap import deck_partner, walled_ramp
from shapely.geometry import LineString, box

LAW = Law.for_airport("ZZZZ")
MOUTH = (0.0, 15.0)
APPROACH = (MOUTH, (0.0, 400.0))


def _deck(oid: str, y0: float, feet=()) -> DeckBridge:
    ring = tuple(box(-15.0, y0, 15.0, y0 + 30.0).exterior.coords[:-1])
    return DeckBridge(oid, "deck.obj", (oid,), ring, ((-15.0, y0), (-15.0, y0 + 30.0)),
                      ((15.0, y0 + 30.0), (15.0, y0)), 0.0, 0.0, -7.5, 100.0,
                      group_feet=tuple(feet))


def _walls(grade: float) -> tuple:
    """A wall line 6 m off the road, stations every 2 m over 100 m out of
    the mouth, its foot rising at ``grade`` over the floor."""
    return tuple((6.0, 15.0 + s, grade * s) for s in range(0, 101, 2))


def test_walls_with_a_rising_foot_make_a_ramp_that_is_never_paired():
    a, b = _deck("a", -15.0, _walls(0.04)), _deck("b", 140.0)
    assert walled_ramp(a, MOUTH, LAW)
    # the pairing itself still sees the further deck; its callers part them
    assert deck_partner(a, LineString([(0.0, 0.0), (0.0, 400.0)]), (a, b)) is b
    z = DBO.road_level(APPROACH, a, lambda x, y: 20.0, 0.6, 150.0, 12.0, (a, b), None, LAW)
    assert z == 20.0                     # the ramp's own road is read: no run-through


def test_level_feet_witness_no_climb_and_the_decks_pair_as_before():
    a, b = _deck("a", -15.0, _walls(0.0)), _deck("b", 140.0)
    assert not walled_ramp(a, MOUTH, LAW)
    assert DBO.road_level(APPROACH, a, lambda x, y: 20.0, 0.6, 150.0, 12.0, (a, b),
                          None, LAW) is None


def test_no_walls_and_no_law_pair_as_before():
    a, b = _deck("a", -15.0), _deck("b", 140.0)
    assert not walled_ramp(a, MOUTH, LAW)
    assert not walled_ramp(_deck("c", -15.0, _walls(0.04)), MOUTH, None)
    assert DBO.road_level(APPROACH, a, lambda x, y: 20.0, 0.6, 150.0, 12.0, (a, b)) is None
