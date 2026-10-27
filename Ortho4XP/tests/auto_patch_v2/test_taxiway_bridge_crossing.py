"""Owner RULINGS 2026-10-27c (Q183, #1471; narrows 2026-10-22n class A): a
structure is a TAXIWAY BRIDGE only if the airport's own taxiway or apron
pavement runs ACROSS its deck, not just touching it at one end.

KLAX's elevated people-mover rail (``Misc/People_Mover/Tracks.obj``) met
the apron at ONE stretch of its edge and was read as a taxiway bridge: its
deck top was set on the apron and the track lowered ~16 m.  The witness is
where the pavement meets the deck's edge (``airside_deck_seat.
pavement_runs_across``): two separate contacts facing each other across
the deck.
"""
from __future__ import annotations

import types

from auto_patch_v2.airport import airside_deck_seat as ADS

#: a 22 m (north-south) x 17 m (east-west) deck
RING = ((40.0, -3.0), (40.0, -2.9998), (40.0002, -2.9998), (40.0002, -3.0))
STEP = 2.0
N, S, E, W = 40.0002, 40.0, -2.9998, -3.0


class _Roles:
    """The role one step outside the deck: ``pick(lat, lon)``."""

    def __init__(self, pick):
        self.pick = pick

    def roles_many(self, la, lo):
        return [self.pick(a, b) for a, b in zip(la, lo, strict=True)]


def _surface(pick):
    def surface(la, lo):
        return 100.0
    surface.roles = _Roles(pick)
    return surface


def _north(a, b):
    return a > N + 1e-9


def _south(a, b):
    return a < S - 1e-9


def _west(a, b):
    return b < W - 1e-12


def test_a_taxiway_carried_end_to_end_runs_across():
    """The taxiway drives on at the south edge and off at the north; the
    road under it passes east-west (LFPG's H*.obj)."""
    s = _surface(lambda a, b: "primary_parallel" if _north(a, b) or _south(a, b)
                 else "service_road")
    assert ADS.pavement_runs_across(RING, s, STEP)


def test_pavement_at_one_end_only_is_a_touch():
    """KLAX's rail: the apron meets one end; the rest is landside."""
    s = _surface(lambda a, b: "apron" if _south(a, b) else None)
    assert not ADS.pavement_runs_across(RING, s, STEP)


def test_an_apron_wrapping_one_end_is_one_contact():
    """The apron round the south end and up both sides near it is ONE
    stretch of the edge: still a touch at one end."""
    s = _surface(lambda a, b: "apron" if (_south(a, b) or a < S + 0.5e-4) else None)
    assert not ADS.pavement_runs_across(RING, s, STEP)


def test_two_contacts_on_one_side_do_not_face_each_other():
    """The apron touches the west side twice, a road between: no pavement
    leaves the deck on the far side."""
    s = _surface(lambda a, b: "apron" if _west(a, b) and abs(a - 40.0001) > 0.4e-4
                 else "service_road")
    assert not ADS.pavement_runs_across(RING, s, STEP)


def test_a_deck_ringed_by_pavement_is_not_a_bridge():
    """Pavement on every side: nothing passes under the deck."""
    s = _surface(lambda a, b: "apron")
    assert not ADS.pavement_runs_across(RING, s, STEP)


def test_the_graded_strip_is_airside_but_not_pavement():
    """The strip and pads are airside by side (22n's role test) but are not
    the airport's taxiway or apron pavement."""
    s = _surface(lambda a, b: "graded_strip" if _north(a, b) or _south(a, b)
                 else "service_road")
    assert not ADS.pavement_runs_across(RING, s, STEP)


def test_class_a_refuses_a_touch_and_counts_it():
    """``airside_zero`` — class A's single derivation site — refuses a flag
    deck over airside that the pavement only touches, and counts it."""
    m = types.SimpleNamespace(deck_kind="flag", deck_top_y=19.35, deck_datum_z=36.4,
                              deck_ring=RING, resource="objects/rail.obj")
    # the ring's south corners stand on the apron (22n's airside witness)
    touch = _surface(lambda a, b: "apron" if a <= S + 1e-9 else None)
    counts: dict = {}
    assert ADS.airside_zero(m, (), touch, STEP, None, counts) is None
    assert counts == {"airside_deck_touch_only": 1}
    across = _surface(lambda a, b: "apron" if a <= S + 1e-9 or a >= N - 1e-9 else None)
    got = ADS.airside_zero(m, (), across, STEP, None, counts)
    assert got is not None and abs(got[0] - (100.0 - 19.35)) < 1e-9
    assert counts == {"airside_deck_touch_only": 1}
