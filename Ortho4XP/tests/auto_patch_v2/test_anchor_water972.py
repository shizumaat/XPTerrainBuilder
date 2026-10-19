"""#972 A BODY STANDING IN WATER KEEPS ITS AUTHORED SEAT
(``anchor_rule._wet_body_anchor``; owner 2026-10-19: the pack's seawall
"should be seated so the top is < 1 m above the solved terrain").

VHHH's ``tunnel/sea.obj`` has its feet at y -23.5 under the sea; the
generic rule read the WATER SURFACE as their ground and stood the crest
20.6 m over the island.  Where every foot stands on water the anchor is
the placement's origin with ``y_zero = -agl``: the pack's own seat."""
from __future__ import annotations

from auto_patch_v2.airport import anchor_rule as AR
from auto_patch_v2.airport.placement_carrier import is_elevated

_ORIGIN = (22.3074, 113.9266)          # on the island
_SEA_LAT = 22.3300                     # north of this is sea


def _surface():
    def surface(la, lo):
        return 0.0 if la >= _SEA_LAT else 7.32

    surface.water = lambda la, lo: la >= _SEA_LAT
    return surface


def _wall(feet_lat=(22.331, 22.332, 22.333)):
    feet = tuple((la, 113.92, -23.5) for la in feet_lat)
    return AR.BodyGeometry(((feet[0][0], feet[0][1], -23.5, feet),), *_ORIGIN)


def test_every_foot_on_water_keeps_the_authored_seat():
    a = AR.anchor_for(AR.DECK, _wall(), _surface(), tol_m=0.3, deck_own_ground_m=0.5,
                      authored_agl_m=-4.4)
    assert (a.lat, a.lon) == _ORIGIN
    assert a.y_zero == 4.4 and a.surface_z == 7.32
    assert a.datum and "on water" in a.reason
    # the authored zero: 7.32 + (-4.4) = 2.92, so a crest authored at y 4
    # renders at 6.92 — 0.40 m under the island, never 20 m over it
    assert a.surface_z - a.y_zero + 4.0 == 7.32 - 4.4 + 4.0
    # an authored height is never read as elevated (§16e's flag)
    assert not is_elevated(-23.5, a, 0.5)


def test_a_foot_on_land_reads_the_generic_rule_as_before():
    feet_lat = (22.329, 22.331, 22.332)
    a = AR.anchor_for(AR.DECK, _wall(feet_lat), _surface(), tol_m=0.3, deck_own_ground_m=0.5,
                      authored_agl_m=-4.4)
    b = AR.anchor_for(AR.DECK, _wall(feet_lat), _surface(), tol_m=0.3, deck_own_ground_m=0.5)
    assert a == b and not a.datum


def test_no_water_bit_or_no_lift_reads_as_before():
    s = _surface()
    plain = lambda la, lo: s(la, lo)                      # noqa: E731
    a = AR.anchor_for(AR.DECK, _wall(), plain, tol_m=0.3, deck_own_ground_m=0.5,
                      authored_agl_m=-4.4)
    b = AR.anchor_for(AR.DECK, _wall(), s, tol_m=0.3, deck_own_ground_m=0.5)
    for x in (a, b):            # the generic rule: a foot on the water line
        assert not x.datum and x.y_zero == -23.5 and x.surface_z == 0.0
