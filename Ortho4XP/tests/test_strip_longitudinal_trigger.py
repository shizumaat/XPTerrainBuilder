"""§A3(a) — the march's emission trigger must carry its LONGITUDINAL term.

THE GAP (closed 2026-08-05).  The adjacent-ground march emits a band where
the ground leaves the corridor LATERALLY; that is the only question its
per-station ray scan asks.  Ground that sits inside the corridor at every
depth but breaches the strip's own along-axis slope / arc law against its
neighbours was therefore never emitted at all — no band, so no vertex, so
``runway_strip_longitudinal_clamp`` never saw it and ``check_grade`` read
raw DEM.  ``grade_law.strip_longitudinal_breaches`` was written for this
trigger and, until this change, had NO production caller (grep: tests
only).

Measured stakes at the time of wiring (composed patches, reader-frame
fixed): KCLT strip_abeam 433 + strip_arc 483, HECA 374 + 415, HEAZ 15 + 16
— every row airside, every row on ``graded_strip``.
"""
from __future__ import annotations

import sys
from pathlib import Path

from shapely.geometry import LineString

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from auto_patch import adjacent_ground as AG          # noqa: E402
from auto_patch import grade_law as GL                # noqa: E402

AXIS = LineString([(0.0, 0.0), (100.0, 0.0)])         # runway along +x
LAW = (0.015, 0.02 / 30.5)                            # slope, arc rate


def _stations(n=11, step=10.0):
    return [(i * step, 0.0) for i in range(n)]


def _dem(profile):
    """sample_dem over the station chain, keyed on x."""
    lut = {round(i * 10.0, 3): z for i, z in enumerate(profile)}

    def sample(x, y):
        return lut.get(round(x, 3))
    return sample


# ── the predicate ─────────────────────────────────────────────────────

def test_lawful_ground_demands_nothing():
    st = _stations()
    flat = [100.0 + 0.01 * i * 10.0 for i in range(len(st))]   # 1 % ramp
    out = AG._strip_longitudinal_demand(
        st, [True] * len(st), AXIS, _dem(flat), LAW)
    assert out is None, (
        "a 1 % along-axis ramp is inside the 1.5 % cap and has zero "
        "curvature — the trigger must stay silent (byte-identical path)")


def test_a_longitudinal_step_is_demanded_even_though_it_is_laterally_fine():
    st = _stations()
    prof = [100.0] * len(st)
    prof[5] = 101.2            # 1.2 m over 10 m = 12 %, cap 1.5 %
    out = AG._strip_longitudinal_demand(
        st, [True] * len(st), AXIS, _dem(prof), LAW)
    assert out is not None
    assert out[5], "the breaching station itself is not demanded"
    assert out[4] and out[6], (
        "the law is read on PAIRS and TRIPLES — shaping one end of an "
        "unlawful pair without the other just moves the step")
    assert not any(out[:3]), "the demand must stay local to the breach"


def test_only_strip_masked_stations_are_read():
    st = _stations()
    prof = [100.0] * len(st)
    prof[5] = 101.2
    mask = [False] * len(st)          # nothing inside the lateral strip
    assert AG._strip_longitudinal_demand(
        st, mask, AXIS, _dem(prof), LAW) is None


def test_no_law_no_demand():
    st = _stations()
    prof = [100.0] * len(st)
    prof[5] = 101.2
    assert AG._strip_longitudinal_demand(
        st, [True] * len(st), AXIS, _dem(prof), None) is None
    assert AG._strip_longitudinal_demand(
        st, [True] * len(st), None, _dem(prof), LAW) is None


def test_the_predicate_is_grade_laws_own():
    """ONE derivation: the trigger must agree with the clamp and the
    validator about which stations the law governs."""
    st = _stations()
    prof = [100.0] * len(st)
    prof[5] = 101.2
    s = [p[0] for p in st]
    direct = GL.strip_longitudinal_breaches(s, prof, LAW[0], LAW[1])
    assert direct, "fixture no longer breaches grade_law's own predicate"
    out = AG._strip_longitudinal_demand(
        st, [True] * len(st), AXIS, _dem(prof), LAW)
    for k in direct:
        assert out[k], f"grade_law flags station {k}; the trigger does not"


# ── the builders honour the demand ────────────────────────────────────

def _flat_dem(z=100.0):
    return lambda x, y: z


# The builders bridge consecutive stations only within 2.5 * step, so a
# builder fixture stations at 2 m with step 1 m (the march's own ratio).
def _close_stations(n=7, gap=2.0):
    return [(i * gap, 0.0) for i in range(n)]


def test_cut_builder_emits_a_band_only_where_demanded():
    st = _close_stations()
    outs = [(0.0, 1.0)] * len(st)
    refs = [100.0] * len(st)
    caps = [30.0] * len(st)

    def ceil_off(d):
        return 5.0          # terrain never breaches laterally

    none_demanded = AG._build_cut_bands(
        st, refs, outs, caps, ceil_off, {3.0}, 0.15, 1.0, _flat_dem())
    assert none_demanded == [], (
        "lateral scan alone must emit nothing here — otherwise this test "
        "cannot show the new term is what emits the band")

    demand = [False, True, True, True, True, True, False]
    with_term = AG._build_cut_bands(
        st, refs, outs, caps, ceil_off, {3.0}, 0.15, 1.0, _flat_dem(),
        longitudinal_demand=demand)
    assert with_term, "the §A3(a) demand did not produce a band"


def test_fill_builder_emits_a_band_only_where_demanded():
    st = _close_stations()
    outs = [(0.0, 1.0)] * len(st)
    refs = [100.0] * len(st)
    caps = [30.0] * len(st)

    def floor_depth(d):
        return 5.0          # terrain never breaches laterally

    assert AG._build_fill_bands(
        st, refs, outs, caps, floor_depth, {3.0}, 0.15, 1.0,
        _flat_dem()) == []
    demand = [False, True, True, True, True, True, False]
    assert AG._build_fill_bands(
        st, refs, outs, caps, floor_depth, {3.0}, 0.15, 1.0, _flat_dem(),
        longitudinal_demand=demand), (
        "the §A3(a) demand did not produce a fill band")


def test_demand_none_is_byte_identical_to_the_old_call():
    st = _close_stations()
    outs = [(0.0, 1.0)] * len(st)
    refs = [100.0] * len(st)
    caps = [30.0] * len(st)

    def ceil_off(d):
        return -1.0         # terrain DOES breach laterally

    a = AG._build_cut_bands(st, refs, outs, caps, ceil_off, {3.0}, 0.15,
                            1.0, _flat_dem())
    b = AG._build_cut_bands(st, refs, outs, caps, ceil_off, {3.0}, 0.15,
                            1.0, _flat_dem(), longitudinal_demand=None)
    assert a == b
