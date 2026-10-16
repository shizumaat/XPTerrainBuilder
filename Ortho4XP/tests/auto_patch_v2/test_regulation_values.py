"""Regulation conformance L2 (spec ``docs/specs/regulation-conformance-
20261015.md`` §1 rows 2, 5, 9, 10, 11, 13, M1, M2; owner RULINGS
2026-10-15k-n): the law values keyed by code, letter and end class, and
the generators that read them, on the synthetic airport of
``test_constraints``."""
from __future__ import annotations

import dataclasses as dc

import pytest

from auto_patch_v2.constraints import no_step, precedence, runway_profile, strips
from auto_patch_v2.constraints.runway_mean_slope import mean_slope_caps, runway_mean_slope
from auto_patch_v2.law import Law
from auto_patch_v2.law import tables as T
from auto_patch_v2.model.constraints import Diff, Linear

from tests.auto_patch_v2.test_constraints import law, synthetic  # noqa: F401  (fixtures)

ICAO, FAA = Law.load(ruleset="icao"), Law.load(ruleset="faa")


def test_row2_taxi_rate_by_letter_and_authority():
    """Annex 14 §3.9.9: 1 % per 25 m at A/B, per 30 m at C-F; AC §4.14.1
    (3)(b): 1 % per 30.5 m; every other airside ring keeps the strip rate."""
    assert T.airside_rate_per_m(ICAO, "junction", "A") == pytest.approx(0.01 / 25)
    assert T.airside_rate_per_m(ICAO, "primary_parallel", "E") == pytest.approx(0.01 / 30)
    assert T.airside_rate_per_m(ICAO, "stub", None) == pytest.approx(0.01 / 30)
    assert T.airside_rate_per_m(FAA, "cross_connector", "B") == pytest.approx(0.01 / 30.5)
    assert T.airside_rate_per_m(ICAO, "apron") == pytest.approx(ICAO.ruleset.strip.arc_rate.per_metre)


def test_row9_faa_taxi_lip_and_row11_shoulder():
    """AC §4.14.2 item 4: the FAA taxiway lip falls 4.5-5.5 % over 3 m;
    the runway lip and the ICAO lip are unchanged.  Table 3-6 S-2: the FAA
    shoulder cap is 5 %."""
    lo, hi = T.zone_bounds(FAA, "junction", 3.0, code_letter="C")
    assert (lo, hi) == (pytest.approx(-0.165), pytest.approx(-0.135))
    lo, hi = T.zone_bounds(ICAO, "junction", 3.0, code_letter="C")
    assert (lo, hi) == (pytest.approx(-0.15), pytest.approx(-0.09))
    assert T.zone_bounds(FAA, "runway", 3.0, 4, "E", half_m=60.0) == \
        (pytest.approx(-0.15), pytest.approx(-0.09))
    assert T.runway_shoulder_cap(FAA, "E", 4) == pytest.approx(0.05)
    assert FAA.ruleset.runway.shoulder_transverse_min == pytest.approx(0.015)
    assert T.runway_shoulder_cap(ICAO, "E", 4) == pytest.approx(0.025)


def test_row5_faa_end_rise_is_the_lower_of_the_approach_surface_and_40_to_1():
    """RULINGS 2026-10-15m (1): beyond the 61 m hold the ground stays under
    the end's approach surface AND the 40:1 departure surface."""
    d = 100.0
    p40 = T.runway_end_profile(FAA, 4, "E", True)
    assert p40.rise_m(d) == pytest.approx(d / 40)
    assert T.runway_end_profile(FAA, 4, "E", True, "visual").rise_m(d) == pytest.approx(d / 40)
    assert T.runway_end_profile(FAA, 4, "E", True, "npa").rise_m(d) == pytest.approx((d - 61) / 20)
    assert T.runway_end_profile(FAA, 4, "E", True, "pa").rise_m(d) == pytest.approx((d - 61) / 34)
    assert T.runway_end_profile(FAA, 4, "E", True, "pa").rise_m(50.0) == 0.0
    # the displaced length counts: the surface is measured from the threshold
    assert T.runway_end_profile(FAA, 4, "E", True, "npa", 300.0).rise_m(d) == pytest.approx(d / 40)
    # ICAO states no approach surface here: the climb surface alone
    assert T.runway_end_profile(ICAO, 4, "E", True, "pa").rise_m(d) == \
        T.runway_end_profile(ICAO, 4, "E", True).rise_m(d)


def test_row13_code3_end_zone_at_cat_ii_iii_ends_and_m2_m1_tables():
    assert T.runway_end_zone_cap(ICAO, 3, "C") is None
    assert T.runway_end_zone_cap(ICAO, 3, "C", cat_ii_iii=True) == pytest.approx(0.008)
    assert T.runway_end_zone_cap(ICAO, 4, "E") == pytest.approx(0.008)
    assert T.runway_end_zone_grade_change(FAA, 4, "C") == 0.0
    assert T.runway_end_zone_grade_change(FAA, 4, "A") is None
    assert T.runway_end_zone_grade_change(ICAO, 4, "E") is None
    assert T.runway_mean_slope_max(ICAO, 4) == pytest.approx(0.01)
    assert T.runway_mean_slope_max(ICAO, 2) == pytest.approx(0.02)
    assert T.runway_mean_slope_max(FAA, 4) is None


def test_row13_end_zone_rows_only_at_the_cat_ii_iii_end(synthetic, law):  # noqa: F811
    airport, pm, _ = synthetic
    rw = airport.runways[0]                       # code 3, ICAO

    def end_rows(c09, c27):
        ends = (dc.replace(rw.ends[0], cat_ii_iii=c09), dc.replace(rw.ends[1], cat_ii_iii=c27))
        ap = dc.replace(airport, runways=(dc.replace(rw, ends=ends),))
        return [r for r in runway_profile.runway_profile(pm, law, ap)
                if isinstance(r, Diff) and r.soft is not None]

    assert end_rows(False, False) == []
    vw = precedence.view(pm, law)
    xs = {round(vw.xy[r.a][0]) for r in end_rows(True, False)}
    assert xs and all(x < 0 for x in xs)          # the 09 end's quarter only


def test_m1_mean_slope_rows_and_their_pin_yield(synthetic, law):  # noqa: F811
    """Annex 14 §3.1.13: |z_i - z_j| <= 1 % x L over the code-3 ridge; the
    pins that already stand further apart govern, and no row is stated."""
    airport, pm, _ = synthetic
    rows = runway_mean_slope(pm, law, airport)
    assert rows and all(isinstance(r, Diff) and r.cap == pytest.approx(0.01)
                        and r.d == pytest.approx(1200.0) for r in rows)
    rw = airport.runways[0]
    steep = dc.replace(rw, ends=(rw.ends[0], dc.replace(rw.ends[1], threshold_elev_m=724.0)))
    assert "09/27" not in mean_slope_caps(pm, law, dc.replace(airport, runways=(steep,)))


def test_row2_rate_rows_read_the_face_letter(synthetic, law):  # noqa: F811
    """The taxi rings of letter D are bound at 1 % per 30 m (the old 2 % per
    30.5 m was the strip's provisional rate)."""
    airport, pm, _ = synthetic
    rows = [r for r in no_step.no_step_rate(pm, law, airport) if isinstance(r, Linear)]
    vw = precedence.view(pm, law)
    taxi = {f.id for f in vw.faces_of_role(("primary_parallel", "stub"))}
    seen = 0
    for r in rows:
        if int(r.source.inputs[0].split(":")[1]) not in taxi:
            continue
        (c, kn), (b, _kb), (a, kp) = r.terms
        dn, dp = 1.0 / kn, 1.0 / kp
        q = law.tables.emit.instrument.coarse_noise_m - law.tables.emit.materiality.elevation_m
        assert r.hi == pytest.approx(0.01 / 30 * 0.5 * (dp + dn) + q * (kn + kp))
        seen += 1
    assert seen


def test_row5_runway_groups_carry_each_ends_displacement(synthetic, law):  # noqa: F811
    airport, pm, _ = synthetic
    rw = airport.runways[0]
    ap = dc.replace(airport, runways=(dc.replace(rw, ends=(
        dc.replace(rw.ends[0], displaced_m=120.0), rw.ends[1])),))
    g = strips.runway_groups(precedence.view(pm, law), ap)[0]
    assert sorted(g.end_displaced_m) == [0.0, 120.0]
