"""``Runway.declared_width_m`` must survive shoulder widening.

The row-100 shoulder pass and the extent-measured shoulder pass both
widen through ``pavement.runways._widen_runway_rect``, which overwrites
``width_m`` in place.  Historically it never saved the published width,
so every ``declared_width_m`` reader (the runway-end corridor
half-width, the EAT ceiling's code letter) silently got
runway+shoulders (KCLT: 46.0 m read back as 62/73 m).  The pre-DSF
whole-polygon shoulder pass in the pipeline preserves the width at its
own call site; these tests pin the shared helper.
"""

import math

import pytest

from auto_patch.apt_dat_reader import Runway
from auto_patch.layout import R_EARTH, _projection
from auto_patch.pavement.runways import _widen_runway_rect

ANCHOR = (0.0, 0.0)


def _make_runway(width_m=45.0, length_m=3000.0):
    lon_b = math.degrees(length_m / R_EARTH)
    return Runway(
        desig_a="09", desig_b="27",
        lat_a=0.0, lon_a=0.0, lat_b=0.0, lon_b=lon_b,
        width_m=width_m, surface_code=1,
        displaced_a_m=0.0, displaced_b_m=0.0)


def test_widening_preserves_declared_width():
    r = _make_runway(width_m=45.0)
    rect = _widen_runway_rect(r, ANCHOR, -30.5, 30.5, _projection(ANCHOR))
    assert rect is not None and not rect.is_empty
    assert r.width_m == pytest.approx(61.0)
    assert r.declared_width_m == pytest.approx(45.0)


def test_second_widening_keeps_the_first_save():
    r = _make_runway(width_m=45.0)
    to_m = _projection(ANCHOR)
    assert _widen_runway_rect(r, ANCHOR, -30.5, 30.5, to_m) is not None
    assert _widen_runway_rect(r, ANCHOR, -36.5, 36.5, to_m) is not None
    assert r.width_m == pytest.approx(73.0)
    assert r.declared_width_m == pytest.approx(45.0)


def test_asymmetric_widening_preserves_declared_width():
    r = _make_runway(width_m=45.0)
    rect = _widen_runway_rect(r, ANCHOR, -22.5, 36.5, _projection(ANCHOR))
    assert rect is not None and not rect.is_empty
    assert r.width_m == pytest.approx(59.0)
    assert r.declared_width_m == pytest.approx(45.0)


def test_degenerate_rollback_leaves_record_untouched():
    # Endpoints < 1 m apart: the helper bails before mutating anything.
    r = _make_runway(width_m=45.0, length_m=0.5)
    assert _widen_runway_rect(
        r, ANCHOR, -30.5, 30.5, _projection(ANCHOR)) is None
    assert r.width_m == pytest.approx(45.0)
    assert r.published_width_m is None
    assert r.declared_width_m == pytest.approx(45.0)


def test_pipeline_whole_polygon_pass_guard_is_mirrored():
    # The pre-DSF pass sets ``published_width_m`` only when still None;
    # the helper must honor that save rather than clobber it, so a
    # whole-polygon-widened runway later re-widened by the extent pass
    # still declares the ORIGINAL published width.
    r = _make_runway(width_m=45.0)
    r.published_width_m = 45.0   # as the pre-DSF pipeline pass leaves it
    r.width_m = 61.0             # widened by that pass
    assert _widen_runway_rect(
        r, ANCHOR, -36.5, 36.5, _projection(ANCHOR)) is not None
    assert r.width_m == pytest.approx(73.0)
    assert r.declared_width_m == pytest.approx(45.0)
