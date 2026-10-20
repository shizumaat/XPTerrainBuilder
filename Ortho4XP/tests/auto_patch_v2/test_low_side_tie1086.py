"""#1086 THE LOW-SIDE FOOT'S TIE ON EQUAL GROUND
(``anchor_rule._low_side_foot``; owner 2026-10-20: "When feet tie on
equal ground, the building is seated on its highest foot, so nothing
floats").

The low-side branch compared the feet's ground UNROUNDED, so on a flat
pad the "lowest" ground was decided by float noise (~1e-16) and a
re-triangulation could flip OTHH's TerminalRoads_03_003 b0 between its
ramp landing (y -1.419) and its pier footing (y -3.169): 1.75 m of float
at the landing.  Ground is now compared at 1e-6 m (the best-foot key's
own rounding) and a tie goes to the HIGHEST authored foot."""
from __future__ import annotations

import pytest

from auto_patch_v2.airport import anchor_rule as AR

_LANDING, _PIER = (25.0000, 51.0000), (25.0001, 51.0000)
_FAR = (25.0002, 51.0000)                    # a foot on higher ground


def _body():
    """A landing at y -1.419 and a pier footing at y -3.169 on one flat
    pad, and a third foot on ground 4 m up: no foot reads the body's zero
    plane, so the low-side rule decides."""
    feet = ((*_LANDING, -1.419), (*_PIER, -3.169), (*_FAR, 0.0))
    return AR.BodyGeometry(((_LANDING[0], _LANDING[1], -3.169, feet),),
                           *_LANDING)


def _surface(landing_z, pier_z):
    ground = {_LANDING: landing_z, _PIER: pier_z, _FAR: 9.0}
    return lambda la, lo: ground[(round(la, 6), round(lo, 6))]


@pytest.mark.parametrize("noise", [+1e-13, -1e-13, 0.0])
def test_a_tie_on_equal_ground_seats_on_the_highest_foot(noise):
    """Whichever way the noise falls, the landing (the higher foot) is the
    anchor: it does not float, and the pier footing buries 1.75 m."""
    a = AR.anchor_for(AR.SKIRTED, _body(), _surface(5.0, 5.0 + noise),
                      tol_m=0.3)
    assert a.reason.startswith("low-side foot (no point within 0.3 m")
    assert "2 contact heights tie on its ground (#1086)" in a.reason
    assert (a.lat, a.lon) == pytest.approx(_LANDING)
    assert a.y_zero == pytest.approx(-1.419)
    assert a.surface_z - a.y_zero == pytest.approx(6.419)


def test_lower_ground_still_wins_over_a_higher_foot():
    """Ground lower by more than 1e-6 m is not a tie: the low side is the
    ground, and the authored height only breaks a true tie."""
    a = AR.anchor_for(AR.SKIRTED, _body(), _surface(5.0, 5.0 - 1e-3),
                      tol_m=0.3)
    assert (a.lat, a.lon) == pytest.approx(_PIER)
    assert a.y_zero == pytest.approx(-3.169)
    assert "tie" not in a.reason


def test_a_stand_in_never_wins_the_tie_over_a_real_foot():
    """A footless part stands in at its own base; on the same flat pad a
    deck part's base at y +8.248 ties with the real feet.  It is not a
    foot: the highest REAL foot seats the body (OTHH TerminalRoads_03_003
    b0 would otherwise bury 9.7 m)."""
    feet = ((*_LANDING, -1.419), (*_PIER, -3.169), (*_FAR, 0.0))
    deck = (25.00005, 51.0000)
    g = AR.BodyGeometry(((_LANDING[0], _LANDING[1], -3.169, feet),
                         (deck[0], deck[1], 8.248, ())), *_LANDING)
    ground = {_LANDING: 5.0, _PIER: 5.0, _FAR: 9.0, deck: 5.0}
    a = AR.anchor_for(AR.SKIRTED, g,
                      lambda la, lo: ground[(round(la, 6), round(lo, 6))],
                      tol_m=0.3)
    assert (a.lat, a.lon) == pytest.approx(_LANDING)
    assert a.y_zero == pytest.approx(-1.419)


def test_among_stand_ins_alone_the_lowest_base_seats():
    """No real foot on the tied ground: the lowest part base is the seat
    (``_lowest_part``'s reading), never the highest elevated part."""
    lo_part, hi_part, far = (25.0, 51.0), (25.0001, 51.0), (25.0002, 51.0)
    g = AR.BodyGeometry(((*lo_part, 0.0, ()), (*hi_part, 39.9, ()),
                         (*far, 0.0, ())), *lo_part)
    ground = {lo_part: 5.0, hi_part: 5.0, far: 9.0}
    a = AR.anchor_for(AR.SKIRTED, g,
                      lambda la, lo: ground[(round(la, 6), round(lo, 6))],
                      tol_m=0.3)
    assert (a.lat, a.lon) == pytest.approx(lo_part)
    assert a.y_zero == pytest.approx(0.0)
