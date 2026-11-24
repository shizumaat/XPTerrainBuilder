"""#2271: the runway target falls back to the straight chord where the
DEM trend leaves the slope law (``constraints/runway_chord.py``)."""
from auto_patch_v2.constraints.runway_chord import (
    _admitted_off_chord,
    _Chord,
    _within_slope_law,
)
from auto_patch_v2.geom.trend import trend_of


def _chord(dip_m, length=600.0, z=3.658):
    """A level 600 m runway whose DEM dips ``dip_m`` mid-length."""
    samples = [(s, z - dip_m * (1.0 - abs(2.0 * s / length - 1.0)))
               for s in range(0, int(length) + 1, 10)]
    return _Chord((0.0, 0.0), 1.0, 0.0, 0.0, length, z, z,
                  trend=trend_of(samples, 200.0), span=(0.0, length))


def test_admitted_is_the_deepest_v_at_the_cap():
    assert abs(_admitted_off_chord(_chord(0.0), 0.02) - 6.0) < 1e-9


def test_a_pit_beyond_the_law_takes_the_straight_chord():
    c = _within_slope_law(_chord(16.0), 0.02, 10.0)
    assert c.trend is None and c.kind == "chord"
    amplitude, admitted = c.slope_refused
    assert amplitude > admitted == 6.0
    assert c.z(300.0) == c.straight_z(300.0) == 3.658


def test_a_lawful_trend_is_kept_byte_for_byte():
    original = _chord(2.0)
    assert _within_slope_law(original, 0.02, 10.0) is original


def test_no_trend_or_no_cap_is_not_judged():
    flat = _Chord((0.0, 0.0), 1.0, 0.0, 0.0, 600.0, 3.0, 3.0)
    assert _within_slope_law(flat, 0.02, 10.0) is flat
    pit = _chord(16.0)
    assert _within_slope_law(pit, None, 10.0) is pit
