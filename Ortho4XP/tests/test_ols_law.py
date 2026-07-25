"""OLS law unit tests (slice 1) — pure, headless, no DEM / X-Plane needed.

The law lives in ``grade_law.ols_*``; the rule VALUES live in ``config``.
Design + citations: ``docs/specs/obstacle-limitation-surfaces-spec.md``.

The property these tests exist for is CONTINUITY: the composed lateral
ceiling runs ``zones 1-2 -> zone-3 +5 % -> OLS transitional``, and a step
anywhere along it would mint a wall between two active cut bands — the
exact class the 2026-07-09 weld ruling exists to prevent.  So the join at
the handover distance is asserted EXACTLY (not to a tolerance): both sides
read the same ``_adjacent_strip_envelope`` helper, so they must agree to
the bit.
"""
import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_SRC = os.path.normpath(os.path.join(_HERE, "..", "src"))
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from auto_patch.config import (                              # noqa: E402
    OLS_APPROACH_DIVERGENCE, OLS_APPROACH_EMIT_REACH_M,
    OLS_APPROACH_FIRST_SECTION_SLOPE,
    OLS_APPROACH_INNER_EDGE_HALF_WIDTH_M, OLS_APPROACH_SETBACK_M,
    OLS_APPROACH_SETBACK_VISUAL_CODE1_M, OLS_MAX_CUT_DEPTH_M,
    OLS_STRIP_HALF_WIDTH_INSTRUMENT_BY_CODE,
    OLS_TRANSITIONAL_EMIT_REACH_M, OLS_TRANSITIONAL_SLOPE,
    OLS_TRANSITIONAL_SLOPE_STEEP, RUNWAY_STRIP_HALF_WIDTH_BY_CODE)
from auto_patch.grade_law import (                           # noqa: E402
    adjacent_ground_envelope, ols_approach_ceiling,
    ols_island_refused, ols_lateral_handover_distance_m,
    ols_strip_half_width_m, ols_transitional_ceiling,
    ols_transitional_slope)

CLASSES = ("visual", "non_precision", "precision")
CODES = (1, 2, 3, 4)
# A representative pavement half-width: SPJC 16R/34L is shoulder-widened
# from 45 m to 81 m, so its edge sits 40.5 m off the axis.
EDGE_OFF_AXIS_M = 40.5


# ── The continuity ruling ────────────────────────────────────────────
@pytest.mark.parametrize("approach_class", CLASSES)
@pytest.mark.parametrize("code", CODES)
def test_transitional_joins_lateral_zone3_exactly(code, approach_class):
    """At the handover S the OLS transitional ceiling EQUALS the
    adjacent-ground ceiling — bit-exact, not merely close."""
    s = ols_lateral_handover_distance_m(code, approach_class,
                                        EDGE_OFF_AXIS_M)
    lateral = adjacent_ground_envelope("runway", code, None, s)[1]
    transitional = ols_transitional_ceiling(code, approach_class, s,
                                            EDGE_OFF_AXIS_M)
    assert lateral is not None
    assert transitional is not None
    assert transitional == lateral


@pytest.mark.parametrize("approach_class", CLASSES)
@pytest.mark.parametrize("code", CODES)
def test_transitional_is_continuous_and_rising(code, approach_class):
    """Just past the handover the ceiling rises at the transitional
    slope, continuously from the join value."""
    s = ols_lateral_handover_distance_m(code, approach_class,
                                        EDGE_OFF_AXIS_M)
    at_s = ols_transitional_ceiling(code, approach_class, s,
                                    EDGE_OFF_AXIS_M)
    slope = ols_transitional_slope(code, approach_class)
    for step in (0.001, 1.0, 25.0, 100.0):
        got = ols_transitional_ceiling(code, approach_class, s + step,
                                       EDGE_OFF_AXIS_M)
        assert got == pytest.approx(at_s + slope * step, abs=1e-9)


@pytest.mark.parametrize("approach_class", CLASSES)
@pytest.mark.parametrize("code", CODES)
def test_transitional_none_inside_handover(code, approach_class):
    """Inside S the adjacent-ground corridor owns the ground — the OLS
    law must decline it, so a band emitter skips those stations."""
    s = ols_lateral_handover_distance_m(code, approach_class,
                                        EDGE_OFF_AXIS_M)
    for d in (0.0, 1.0, 0.5 * s, s - 0.001):
        assert ols_transitional_ceiling(
            code, approach_class, d, EDGE_OFF_AXIS_M) is None


@pytest.mark.parametrize("approach_class", CLASSES)
@pytest.mark.parametrize("code", CODES)
def test_transitional_none_beyond_emit_reach(code, approach_class):
    s = ols_lateral_handover_distance_m(code, approach_class,
                                        EDGE_OFF_AXIS_M)
    assert ols_transitional_ceiling(
        code, approach_class, s + OLS_TRANSITIONAL_EMIT_REACH_M,
        EDGE_OFF_AXIS_M) is None
    assert ols_transitional_ceiling(
        code, approach_class, s + OLS_TRANSITIONAL_EMIT_REACH_M - 0.001,
        EDGE_OFF_AXIS_M) is not None


# ── Strip width + slope keying ───────────────────────────────────────
@pytest.mark.parametrize("code", CODES)
def test_instrument_strip_is_wider_than_non_instrument(code):
    """Annex 14 §3.4.3-3.4.4: the instrument OLS strip is the wide one;
    a non-instrument runway reuses the graded-strip width (no second
    constant to drift)."""
    visual = ols_strip_half_width_m(code, "visual")
    assert visual == RUNWAY_STRIP_HALF_WIDTH_BY_CODE[code]
    for cls in ("non_precision", "precision"):
        assert (ols_strip_half_width_m(code, cls)
                == OLS_STRIP_HALF_WIDTH_INSTRUMENT_BY_CODE[code])
        assert ols_strip_half_width_m(code, cls) >= visual


def test_steep_transitional_only_for_small_visual_and_npa():
    """1:5 applies to non-instrument / non-precision code 1-2 only;
    everything else is 1:7 (Table 4-1)."""
    for code in (1, 2):
        for cls in ("visual", "non_precision"):
            assert (ols_transitional_slope(code, cls)
                    == OLS_TRANSITIONAL_SLOPE_STEEP)
        assert (ols_transitional_slope(code, "precision")
                == OLS_TRANSITIONAL_SLOPE)
    for code in (3, 4):
        for cls in CLASSES:
            assert ols_transitional_slope(code, cls) == OLS_TRANSITIONAL_SLOPE


def test_handover_never_starts_inside_the_graded_band():
    """The floor at the graded width keeps the transitional out of a
    still-graded zone 1-2 while the lateral march still spends the
    graded half-width as a from-EDGE reach (pre-arc-A4)."""
    for code in CODES:
        for cls in CLASSES:
            s = ols_lateral_handover_distance_m(code, cls, EDGE_OFF_AXIS_M)
            assert s >= RUNWAY_STRIP_HALF_WIDTH_BY_CODE[code]


# ── Approach surface ─────────────────────────────────────────────────
@pytest.mark.parametrize("approach_class", CLASSES)
@pytest.mark.parametrize("code", CODES)
def test_approach_none_inside_setback(code, approach_class):
    setback = (OLS_APPROACH_SETBACK_VISUAL_CODE1_M
               if (approach_class == "visual" and code == 1)
               else OLS_APPROACH_SETBACK_M)
    for s in (0.0, 1.0, setback - 0.001, setback):
        assert ols_approach_ceiling(code, approach_class, s, 0.0) is None
    assert ols_approach_ceiling(
        code, approach_class, setback + 0.001, 0.0) is not None


@pytest.mark.parametrize("approach_class", CLASSES)
@pytest.mark.parametrize("code", CODES)
def test_approach_zero_at_inner_edge_then_rises(code, approach_class):
    """The inner edge sits AT the anchor elevation (offset 0) and the
    surface rises from there at the first-section slope."""
    setback = (OLS_APPROACH_SETBACK_VISUAL_CODE1_M
               if (approach_class == "visual" and code == 1)
               else OLS_APPROACH_SETBACK_M)
    slope = OLS_APPROACH_FIRST_SECTION_SLOPE[approach_class][code]
    for run in (0.001, 50.0, 300.0):
        got = ols_approach_ceiling(code, approach_class, setback + run, 0.0)
        assert got == pytest.approx(slope * run, abs=1e-9)


@pytest.mark.parametrize("approach_class", CLASSES)
@pytest.mark.parametrize("code", CODES)
def test_approach_splay_boundary_is_exact(code, approach_class):
    """Inside the fan the law answers; one millimetre outside it declines
    — the emitter relies on that ``None`` to confine the fan instead of
    building bespoke clipping geometry."""
    setback = (OLS_APPROACH_SETBACK_VISUAL_CODE1_M
               if (approach_class == "visual" and code == 1)
               else OLS_APPROACH_SETBACK_M)
    run = 200.0
    half = (OLS_APPROACH_INNER_EDGE_HALF_WIDTH_M[approach_class][code]
            + OLS_APPROACH_DIVERGENCE[approach_class] * run)
    s = setback + run
    for off in (0.0, half - 0.001, -(half - 0.001)):
        assert ols_approach_ceiling(code, approach_class, s, off) is not None
    for off in (half + 0.001, -(half + 0.001), half * 3.0):
        assert ols_approach_ceiling(code, approach_class, s, off) is None


@pytest.mark.parametrize("approach_class", CLASSES)
@pytest.mark.parametrize("code", CODES)
def test_approach_flat_transversely(code, approach_class):
    """Annex 14 measures approach slopes in the vertical plane through
    the centreline, so inside the fan the ceiling is independent of the
    lateral offset."""
    s = OLS_APPROACH_SETBACK_M + 300.0
    on_axis = ols_approach_ceiling(code, approach_class, s, 0.0)
    off_axis = ols_approach_ceiling(code, approach_class, s, 20.0)
    assert on_axis is not None and off_axis is not None
    assert on_axis == off_axis


@pytest.mark.parametrize("approach_class", CLASSES)
@pytest.mark.parametrize("code", CODES)
def test_approach_none_beyond_emit_reach(code, approach_class):
    setback = (OLS_APPROACH_SETBACK_VISUAL_CODE1_M
               if (approach_class == "visual" and code == 1)
               else OLS_APPROACH_SETBACK_M)
    assert ols_approach_ceiling(
        code, approach_class,
        setback + OLS_APPROACH_EMIT_REACH_M, 0.0) is not None
    assert ols_approach_ceiling(
        code, approach_class,
        setback + OLS_APPROACH_EMIT_REACH_M + 0.001, 0.0) is None


def test_npa_code_34_first_section_is_two_percent():
    """Regression pin for the gap-audit correction (2026-07-24): NPA code
    3/4 is 2 %, the SAME as precision 3/4 — 3.33 % is NPA code 1/2.  The
    audit carried the wrong keying until this arc re-verified Table 4-1."""
    assert OLS_APPROACH_FIRST_SECTION_SLOPE["non_precision"][3] == 0.02
    assert OLS_APPROACH_FIRST_SECTION_SLOPE["non_precision"][4] == 0.02
    assert OLS_APPROACH_FIRST_SECTION_SLOPE["non_precision"][1] == 0.0333
    assert OLS_APPROACH_FIRST_SECTION_SLOPE["non_precision"][2] == 0.0333
    assert (OLS_APPROACH_FIRST_SECTION_SLOPE["precision"][4]
            == OLS_APPROACH_FIRST_SECTION_SLOPE["non_precision"][4])


# ── Mountain refusal ─────────────────────────────────────────────────
def test_island_refusal_threshold():
    assert not ols_island_refused(0.0)
    assert not ols_island_refused(OLS_MAX_CUT_DEPTH_M)
    assert ols_island_refused(OLS_MAX_CUT_DEPTH_M + 0.001)
    assert ols_island_refused(120.0)          # a real mountain flank


# ── There is no floor anywhere in this law ───────────────────────────
def test_ols_is_cut_only():
    """An OLS bounds how HIGH terrain may stand, never how low it may
    fall — every OLS law function returns a ceiling or ``None``, and no
    OLS function returns a floor at all.  Guards against someone later
    adding a fill direction to a surface that has none."""
    import auto_patch.grade_law as gl
    ols_callables = [n for n in dir(gl)
                     if n.startswith("ols_") and callable(getattr(gl, n))]
    # The law's public surface, pinned so a new function must be
    # considered here deliberately rather than slipping in.
    assert set(ols_callables) == {
        "ols_approach_ceiling", "ols_island_refused",
        "ols_lateral_handover_distance_m", "ols_strip_half_width_m",
        "ols_transitional_ceiling", "ols_transitional_slope",
    }
    for code in CODES:
        for cls in CLASSES:
            s = ols_lateral_handover_distance_m(code, cls, EDGE_OFF_AXIS_M)
            for d in (s, s + 10.0, s + 100.0):
                got = ols_transitional_ceiling(code, cls, d, EDGE_OFF_AXIS_M)
                assert got is None or isinstance(got, float)
