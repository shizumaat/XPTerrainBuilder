"""Owner RULINGS 2026-11-25b (2), #2274: a runway whose pins force its cap to
yield follows its ground's long wave between the pins, WITHIN the law's
vertical curve, instead of one uniform grade (``runway_junctions.
_within_curve`` over ``smoothest_grades``)."""
from __future__ import annotations

import pytest
from auto_patch_v2.constraints.runway_junctions import _rate, _within_curve, smoothest_grades


def _ground(d, grades):
    out, h = [0.0], 0.0
    for dk, gk in zip(d, grades, strict=True):
        h += dk * gk
        out.append(h)
    return out


def test_the_profile_follows_a_steeper_then_gentler_ground_and_meets_both_pins():
    # 640 m: -2.8 % for 440 m then -0.5 % (TFFJ's shape), pins 13.4 m apart
    d = [20.0] * 32
    ground = _ground(d, [-0.028] * 22 + [-0.005] * 10)
    dz = -13.4
    k_law, unit = 1000.0, 0.01            # K 1000 m per 1 % of grade change
    g0 = smoothest_grades(d, dz, [None] * len(d), ground, 200.0)
    g = _within_curve(d, dz, [None] * len(d), ground, 200.0, g0, k_law, unit)
    assert sum(a * b for a, b in zip(g, d, strict=True)) == pytest.approx(dz, abs=1e-6)
    assert g[2] < g[-2]                    # steeper near the high end
    assert _rate(g, d) <= unit / k_law + 1e-12


def test_a_curve_the_law_cannot_hold_falls_back_to_the_straight_line():
    d = [20.0] * 10
    ground = _ground(d, [-0.10] * 5 + [0.10] * 5)
    g0 = smoothest_grades(d, -1.0, [None] * 10, ground, 50.0)
    g = _within_curve(d, -1.0, [None] * 10, ground, 50.0, g0, 1e9, 0.01)
    assert g == pytest.approx([-1.0 / 200.0] * 10)
