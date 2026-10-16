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
    assert T.runway_shoulder_cap(FAA, "E", 4) == pytest.approx(0.025)
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
        rate = T.airside_rate_per_m(law, "stub", "D", no_step.turn_cos(vw.xy[a], vw.xy[b], vw.xy[c]))
        assert r.hi == pytest.approx(rate * 0.5 * (dp + dn) + q * (kn + kp))
        seen += rate == pytest.approx(0.01 / 30)
    assert seen


def test_row5_runway_groups_carry_each_ends_displacement(synthetic, law):  # noqa: F811
    airport, pm, _ = synthetic
    rw = airport.runways[0]
    ap = dc.replace(airport, runways=(dc.replace(rw, ends=(
        dc.replace(rw.ends[0], displaced_m=120.0), rw.ends[1])),))
    g = strips.runway_groups(precedence.view(pm, law), ap)[0]
    assert sorted(g.end_displaced_m) == [0.0, 120.0]


def test_row5_datum_term_lifts_the_surface_by_the_threshold_height():
    """The approach surface starts at the THRESHOLD's elevation: a datum of
    z_thr - z_end shifts every approach surface, never the 40:1."""
    p0 = T.runway_end_profile(FAA, 4, "E", True, "pa", 0.0, 0.0)
    p1 = T.runway_end_profile(FAA, 4, "E", True, "pa", 0.0, 0.5)
    assert p1.rise_m(100.0) == pytest.approx(p0.rise_m(100.0) + 0.5)
    assert T.runway_end_profile(FAA, 4, "E", True, None, 0.0, 1.5).rise_m(100.0) == \
        pytest.approx(100.0 / 40)


def test_row5_threshold_datums_follow_the_cifp_line(synthetic):  # noqa: F811
    from auto_patch_v2.model.threshold_datum import threshold_datums
    airport, _pm, _ = synthetic
    rw = airport.runways[0]                       # 700 -> 706 over 1200 m
    assert threshold_datums(rw) == (0.0, 0.0)
    disp = dc.replace(rw, ends=(dc.replace(rw.ends[0], displaced_m=200.0), rw.ends[1]))
    da, db = threshold_datums(disp)
    assert da == pytest.approx(6.0 / 1000.0 * 200.0) and db == 0.0


def test_row2_rate_reads_the_profile_not_the_ring_corner():
    """A ring triple turning more than ``emit.no_step.rate_profile_turn_max_deg``
    is the instrument's walk round a corner: it keeps the strip rate."""
    import math
    from auto_patch_v2.constraints.no_step import turn_cos
    assert turn_cos((0, 0), (1, 0), (2, 0)) == pytest.approx(1.0)
    corner = turn_cos((0, 0), (1, 0), (1, 1))
    assert corner == pytest.approx(0.0, abs=1e-12)
    strip = ICAO.ruleset.strip.arc_rate.per_metre
    assert T.airside_rate_per_m(ICAO, "stub", "D", corner) == pytest.approx(strip)
    assert T.airside_rate_per_m(ICAO, "stub", "D", math.cos(math.radians(20))) == \
        pytest.approx(0.01 / 30)


def test_16a_i_a_taxi_route_crossing_the_shoulder_takes_the_taxi_cap(synthetic, law):  # noqa: F811
    """RULINGS 2026-10-16a (i): the shoulder vertices the stub's corridor
    crosses are priced at the taxiway's longitudinal cap beyond the half
    width, every other shoulder vertex at the shoulder's own."""
    from auto_patch_v2.constraints.shoulder_crossing import crossed_shoulder_caps
    airport, pm, _ = synthetic
    from auto_patch_v2.model.airport import TaxiEdge, TaxiNode
    narrow = dc.replace(airport, runways=(dc.replace(airport.runways[0], width_m=30.0),),
                        taxi_nodes={1: TaxiNode(1, (0.0, 91.5), "both"),
                                    2: TaxiNode(2, (0.0, 0.0), "both")},
                        taxi_edges=(TaxiEdge(1, 2, "B", False, False, "D"),))
    got = crossed_shoulder_caps(pm, law, narrow)
    vw = precedence.view(pm, law)
    assert got and all(abs(vw.xy[v][0]) <= 9.0 + 1e-6 for v in got)
    assert all(c == pytest.approx(0.015) for c in got.values())
    assert T.runway_transverse_bound(law, 20.0, 15.0, "D", 3, 0.015) == \
        pytest.approx(0.015 * 15.0 + 0.015 * 5.0)
    assert T.runway_transverse_bound(law, 20.0, 15.0, "D", 3) == \
        pytest.approx(0.015 * 15.0 + 0.025 * 5.0)


def test_16b_a_declared_jetway_joins_the_pad_it_serves(tmp_path, synthetic, law):  # noqa: F811
    """RULINGS 2026-10-16b (1): an apt.dat 1500 jetway rooted at the pad's
    facade grows the pad by its own footprint."""
    from shapely.geometry import Polygon as P
    from auto_patch_v2.classify import evidence as E
    airport, _pm, _ = synthetic
    pad = P([(-60, 200), (60, 200), (60, 250), (-60, 250)])
    lat, lon = airport.frame.transformers()[1](0.0, 200.0)
    apt = tmp_path / "apt.dat"
    apt.write_text(f"I\n1200\n1 700 0 0 ZZZZ Synthetic\n1500 {lat:.9f} {lon:.9f} 180.0 1 1 180.0 15.0 180.0\n",
                   encoding="utf-8", newline="\n")
    ap = dc.replace(airport, pack=dc.replace(airport.pack, apt_dat_path=str(apt)))
    out = E._with_jetways([pad], ap, law, None, P())
    assert E.JETWAY_PADS["found"] == 1 and E.JETWAY_PADS["attached"] == 1
    grown = E.JETWAY_PADS["grown_m2"][0]
    assert grown == pytest.approx(19.0 * 4.0, rel=0.05) and out[0].area > pad.area
