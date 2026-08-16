"""Twins for THE WHOLE-RUN CORRIDOR PROFILE (staged-solve round, S2).

Four properties the round spec names, each asserted on the solver
itself so a regression fails here and not three airports later:

1. ENDPOINT FIDELITY — mouth welds and free-end DEM ties are exact
   pass-through values (stage-A values are read-only boundary data).
2. CAP COMPLIANCE — every emitted segment obeys the road cap, and the
   profile is NOT a cap-riding bang-bang trace.
3. FLATNESS IS LAWFUL — equal pegs come out FLAT; no minimum slope is
   minted (owner 2026-08-14, "DRAINAGE RULING SCOPE CLARIFIED":
   corridors/roads get no added drainage curvature).
4. INTEGRAL INFEASIBILITY IS REPORTED WITH NUMBERS — a rise the run
   cannot absorb at the cap yields a conflict carrying rise/run/cap,
   never an exception, never a quarantine, never a bare step.
"""

from __future__ import annotations

import math
import os
import sys

import pytest

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from auto_patch.elevation_per_surface.route_profile.corridor_profile import (  # noqa: E402
    CAP_RIDE_MIN_SEGMENTS, audit_run, solve_run_profile)

CAP = 0.08          # config.SERVICE_ROAD_MAX_GRADE — the existing constant


def _uniform(n: int, step: float = 10.0) -> list[float]:
    return [i * step for i in range(n)]


def _wide_band(n: int, lo: float = -1e6, hi: float = 1e6):
    return [lo] * n, [hi] * n


# ── 1. endpoint fidelity ────────────────────────────────────────────
def test_pegs_are_exact_pass_through():
    s = _uniform(21)
    f, c = _wide_band(21)
    pegs = {0: 100.0, 10: 104.0, 20: 101.5}
    out = solve_run_profile(s, f, c, pegs, CAP)
    assert out is not None
    for i, v in pegs.items():
        assert out.z[i] == pytest.approx(v, abs=1e-9), (
            f"peg {i} moved: {out.z[i]} != {v}")


def test_mouth_weld_is_not_rewritten_by_a_wide_band():
    """A stage-A mouth value is boundary DATA — the band never pulls it."""
    s = _uniform(11)
    f = [90.0] * 11
    c = [110.0] * 11
    out = solve_run_profile(s, f, c, {0: 90.0, 10: 110.0}, 0.25)
    assert out is not None
    assert out.z[0] == pytest.approx(90.0)
    assert out.z[-1] == pytest.approx(110.0)


# ── 2. cap compliance and no bang-bang ──────────────────────────────
def test_band_grown_at_cap_yields_no_over_cap_segment():
    """The tube is the cap-Lipschitz reach from the pegs; the string
    inside it is cap-lawful, and the audit VERIFIES that."""
    n, step = 31, 10.0
    s = _uniform(n, step)
    v0, v1 = 100.0, 103.0
    f = [max(v0 - CAP * s[i], v1 - CAP * (s[-1] - s[i])) for i in range(n)]
    c = [min(v0 + CAP * s[i], v1 + CAP * (s[-1] - s[i])) for i in range(n)]
    out = solve_run_profile(s, f, c, {0: v0, n - 1: v1}, CAP)
    assert out is not None
    assert out.audit.over_cap_segments == 0
    assert out.audit.worst_grade <= CAP + 1e-9
    assert not [x for x in out.conflicts if x.kind == "over_cap_segment"]


def test_dem_hump_inside_the_band_is_not_traced():
    """The named HECA defect: a 6.18 m DEM hump with no anchor within
    60 m.  A POINTWISE clamp traces it at the cap; the whole-run profile
    does not — band-lawful displacement trumps DEM in the interior."""
    n, step = 41, 5.0                      # 200 m run
    s = _uniform(n, step)
    v0 = v1 = 100.0
    f = [max(v0 - CAP * s[i], v1 - CAP * (s[-1] - s[i])) for i in range(n)]
    c = [min(v0 + CAP * s[i], v1 + CAP * (s[-1] - s[i])) for i in range(n)]
    mid = n // 2
    dem = [v0 + 6.18 * math.exp(-((i - mid) / 6.0) ** 2) for i in range(n)]

    # What the pointwise rule did: clamp DEM into the band, station by
    # station.  It traces the hump and rides the cap on the flanks.
    ptwise = [min(max(dem[i], f[i]), c[i]) for i in range(n)]
    ptwise_audit = audit_run(s, ptwise, CAP)
    assert max(ptwise) - v0 > 5.0, "control: the pointwise rule humps"
    assert ptwise_audit.cap_ride_runs >= 1, "control: it rides the cap"

    out = solve_run_profile(s, f, c, {0: v0, n - 1: v1}, CAP, dem=dem)
    assert out is not None
    assert max(out.z) - v0 <= 0.01, (
        f"hump survived the whole-run profile: {max(out.z) - v0:.3f} m")
    assert out.audit.cap_ride_runs == 0
    assert out.audit.over_cap_segments == 0


def test_cap_ride_run_detector_sees_a_bang_bang_trace():
    s = _uniform(12)
    z = [i * CAP * 10.0 for i in range(12)]     # every segment at cap
    a = audit_run(s, z, CAP)
    assert a.cap_ride_segments == 11
    assert a.cap_ride_runs == 1
    assert a.cap_ride_length_m == pytest.approx(110.0)
    short = audit_run(_uniform(CAP_RIDE_MIN_SEGMENTS),
                      [i * CAP * 10.0 for i in range(CAP_RIDE_MIN_SEGMENTS)],
                      CAP)
    assert short.cap_ride_runs == 0, "a bend onto a wall is not a RUN"


# ── 3. flat is lawful ───────────────────────────────────────────────
def test_equal_pegs_come_out_flat_no_minimum_slope_minted():
    s = _uniform(25)
    f, c = _wide_band(25)
    out = solve_run_profile(s, f, c, {0: 42.0, 24: 42.0}, CAP)
    assert out is not None
    assert out.audit.worst_grade == pytest.approx(0.0, abs=1e-12)
    assert all(v == pytest.approx(42.0, abs=1e-12) for v in out.z)
    assert not out.conflicts


def test_a_flat_run_between_flat_walls_is_not_a_conflict():
    n = 15
    s = _uniform(n)
    f = [10.0] * n
    c = [10.0] * n
    out = solve_run_profile(s, f, c, {0: 10.0, n - 1: 10.0}, CAP)
    assert out is not None
    assert out.conflicts == []
    assert out.audit.cap_ride_runs == 0


# ── 4. integral infeasibility is REPORTED, with numbers ─────────────
def test_rise_the_run_cannot_absorb_is_reported_not_raised():
    """A refused wall's step enters as an interior peg.  20 m of run
    cannot carry 6 m at 8 % — that is a law conflict with numbers."""
    s = _uniform(21, 10.0)
    f, c = _wide_band(21)
    pegs = {0: 100.0, 2: 106.0, 20: 100.0}     # 6 m over 20 m of run
    out = solve_run_profile(s, f, c, pegs, CAP)
    assert out is not None, "an infeasible run still emits a profile"
    pair = [x for x in out.conflicts if x.kind == "peg_pair"]
    assert len(pair) >= 1
    hit = pair[0]
    assert hit.rise_m == pytest.approx(6.0)
    assert hit.run_m == pytest.approx(20.0)
    assert hit.cap == pytest.approx(CAP)
    assert hit.required_grade == pytest.approx(0.30)
    assert "cap" in hit.describe() and "rise" in hit.describe()


def test_inverted_tube_is_relaxed_and_recorded_never_blended():
    """``floor > ceiling`` was a distance-weighted blend + a quarantine
    export (the discharge-pocket residue).  Here it is the minimal
    relaxation plus a conflict carrying the deficit."""
    n = 11
    s = _uniform(n)
    f = [0.0] * n
    c = [5.0] * n
    f[5], c[5] = 9.0, 4.0                       # 5 m of contradiction
    out = solve_run_profile(s, f, c, {0: 0.0, n - 1: 0.0}, CAP)
    assert out is not None
    inv = [x for x in out.conflicts if x.kind == "inverted_tube"]
    assert len(inv) == 1
    assert inv[0].station_index == 5
    assert inv[0].deficit_m == pytest.approx(5.0)
    # the run still emits ONE continuous profile through the conflict
    assert len(out.z) == n
    assert all(math.isfinite(v) for v in out.z)


def test_under_pegged_run_synthesises_dem_end_ties():
    n = 9
    s = _uniform(n)
    f, c = _wide_band(n)
    dem = [50.0 + 0.1 * i for i in range(n)]
    out = solve_run_profile(s, f, c, {}, CAP, dem=dem)
    assert out is not None
    assert out.synthetic_end_ties == 2
    assert out.z[0] == pytest.approx(dem[0])
    assert out.z[-1] == pytest.approx(dem[-1])


def test_no_pegs_and_no_dem_returns_none_for_the_callers_fallback():
    n = 6
    assert solve_run_profile(_uniform(n), *_wide_band(n), {}, CAP) is None


def test_dem_deviation_is_neither_measured_nor_reported():
    """Owner 2026-08-14: DEM deviation is not an error and is not
    reported.  The audit carries no deviation field and a DEM the
    profile lawfully leaves behind mints no conflict."""
    n = 21
    s = _uniform(n)
    f, c = _wide_band(n)
    dem = [100.0] * n
    dem[10] = 105.0
    out = solve_run_profile(s, f, c, {0: 100.0, n - 1: 100.0}, CAP, dem=dem)
    assert out is not None
    assert not hasattr(out.audit, "max_dem_displacement_m")
    assert not out.conflicts, "deviation from DEM is never a defect"
    assert max(out.z) == pytest.approx(100.0)


def test_float_noise_inversion_is_levelled_but_not_reported():
    """Measured at HECA: a 5e-14 m tube inversion at a weld.  Levelled
    (the string needs a well-formed tube) and NOT reported (below the
    0.01 m materiality floor it is the reach fields' own noise)."""
    n = 7
    s = _uniform(n)
    f = [95.18790636814693] + [90.0] * (n - 1)
    c = [95.18790636814688] + [99.0] * (n - 1)
    out = solve_run_profile(s, f, c, {0: 95.1879063681469, n - 1: 95.0}, CAP)
    assert out is not None
    assert out.conflicts == []


# ── RUN / YARD SCOPING (Fable ruling 2026-08-14, S2's STOP 1) ───────
# "The 1-D profile HOLDS on the corridor's LINEAR RUNS only; a 2-D
# service surface is never held to a line."  The discriminator is the
# shape's own geometry — mean width ``2*area/perimeter`` against
# ``config.ROAD_CARVE_MAX_WIDTH_M`` — never the role literal, because a
# service_junction is a narrow connector in one place and a 40 m yard in
# another, and it was the YARDS that made within-shape pairs
# unsatisfiable (KCLT +157 rows, measured).

def _mean_width(poly):
    return 2.0 * poly.area / poly.length


def test_mean_width_separates_a_road_run_from_a_yard():
    from shapely.geometry import Polygon
    from auto_patch.config import ROAD_CARVE_MAX_WIDTH_M as W
    road = Polygon([(0, 0), (120, 0), (120, 6), (0, 6)])       # 6 m x 120 m
    yard = Polygon([(0, 0), (40, 0), (40, 40), (0, 40)])       # 40 m square
    assert _mean_width(road) <= W, _mean_width(road)
    assert _mean_width(yard) > W, _mean_width(yard)


def test_the_widest_thing_the_carve_calls_a_road_is_still_linear():
    """The threshold is the existing carve constant, so a road at the
    carve's own maximum width is on the LINEAR side of it."""
    from shapely.geometry import Polygon
    from auto_patch.config import ROAD_CARVE_MAX_WIDTH_M as W
    wide_road = Polygon([(0, 0), (2000, 0), (2000, W), (0, W)])
    assert _mean_width(wide_road) <= W


# ═══════════════════════════════════════════════════════════════════════
# R1 — A HELD PROFILE MUST BE LAWFUL OR IT IS NOT HELD (service-road law
# spec 2026-08-15).  The run's OWN audit names every over-cap segment and
# every relaxed inverted tube; exactly those stations are RELEASED from
# the ``svc_profile`` hold (values stay as seeds).  Clean stations stay
# held — the smooth majority must not loosen.
# ═══════════════════════════════════════════════════════════════════════

def _release_of(prof, run_sid):
    import auto_patch.pipeline  # noqa: F401 — import-order guard
    from auto_patch.elevation_per_surface.route_profile.anchors import (
        _profile_law_release)
    return _profile_law_release(prof.conflicts, run_sid)


def test_over_cap_strung_run_releases_exactly_its_over_cap_stations():
    """A tube that FORCES a 40 % segment between stations 1 and 2 (the
    walls pinch to two levels the cap cannot join) releases BOTH stations
    of that segment — and nothing else.  The run's peg_pair conflict (an
    end-tie tension, not a held-station value) releases nothing."""
    s = [0.0, 10.0, 20.0, 30.0, 40.0]
    f = [100.0, 100.0, 104.0, 104.0, 104.0]
    c = [100.0, 100.0, 104.0, 104.0, 104.0]
    out = solve_run_profile(s, f, c, {0: 100.0, 4: 104.0}, CAP)
    assert out is not None
    kinds = {cf.kind for cf in out.conflicts}
    assert "over_cap_segment" in kinds
    assert "inverted_tube" not in kinds
    run_sid = ["s0", "s1", "s2", "s3", "s4"]
    rel = _release_of(out, run_sid)
    assert rel == {"s1", "s2"}, (
        f"released {sorted(rel)}; the over-cap segment is 1→2 and its "
        f"two stations are the whole release")


def test_relaxed_inverted_tube_station_is_released():
    """An inverted tube (two anchor regimes contradicting at station 2)
    is levelled by ``_relax_tube`` and RECORDED — that station leaves the
    hold even when the string through the relaxed tube is lawful."""
    s = [0.0, 10.0, 20.0, 30.0, 40.0]
    f = [90.0, 90.0, 110.0, 90.0, 90.0]
    c = [110.0, 110.0, 90.0, 110.0, 110.0]      # inverted at station 2
    out = solve_run_profile(s, f, c, {0: 100.0, 4: 100.0}, CAP)
    assert out is not None
    assert {cf.kind for cf in out.conflicts} == {"inverted_tube"}
    rel = _release_of(out, ["s0", "s1", "s2", "s3", "s4"])
    assert rel == {"s2"}


def test_clean_run_releases_no_station():
    """Stations whose audit is clean stay HELD."""
    s = [0.0, 10.0, 20.0, 30.0, 40.0]
    f, c = _wide_band(5)
    out = solve_run_profile(s, f, c, {0: 100.0, 4: 102.0}, CAP)
    assert out is not None
    assert not out.conflicts
    assert _release_of(out, ["s0", "s1", "s2", "s3", "s4"]) == set()


# ── R4: THE STRING HOLDS ON THE PEGGED SPAN ONLY (service-road law
# spec amendment, 2026-08-15 — the run-(46,0) eruption class) ────────

def _span_of():
    from auto_patch.elevation_per_surface.route_profile.anchors import (
        _r4_pegged_span)
    return _r4_pegged_span


def test_r4_one_sided_pegs_string_only_their_span():
    """HECA run (46,0): 265 stations, pegs at indices 0/1/2 only.  The
    string holds on [0..2]; every station beyond keeps the pointwise
    DEM-follow rule (NOT a 2.36 km flat at the mouth value, NOT a
    synthetic far-end chord)."""
    span = _span_of()({0: 127.21, 1: 127.21, 2: 127.21})
    assert span == (0, 2)


def test_r4_zero_or_one_peg_runs_are_not_strung():
    """Zero law targets → nothing to string between: the whole run is
    pointwise.  One peg likewise (the weld's own reach band shapes the
    departure; the string has no second target)."""
    span = _span_of()
    assert span({}) is None
    assert span({7: 101.5}) is None


def test_r4_degenerate_single_station_span_is_not_strung():
    span = _span_of()
    assert span({3: 100.0}) is None


def test_r4_both_end_pegged_run_is_unchanged():
    """A run pegged at both termini strings end to end — R4 changes
    nothing for the healthy case."""
    span = _span_of()({0: 100.0, 9: 102.0})
    assert span == (0, 9)


def test_r4_interior_pegs_bound_the_span():
    span = _span_of()({2: 100.0, 5: 101.0, 11: 100.5})
    assert span == (2, 11)


# ══ R5 — ROAD RUNS TRACK TERRAIN ════════════════════════════════════
# The taut string draws the STRAIGHTEST lawful profile — correct for an
# airside spine, wrong for a road (owner in-sim on 1.0.252: CYXY road
# 349 as a 5.2 m causeway over a 2.7 % dip, the junction-190 complex as
# a 12-16 m canyon under 718-722 m terrain, HECA as a plateau).  A
# service-road run's profile is the CAP-CONSTRAINED LEAST-DEVIATION
# TRACKER of its low-passed station DEM.

from auto_patch.elevation_per_surface.route_profile.corridor_profile import (  # noqa: E402
    MATERIALITY_M, track_dem_profile)


def _v_dip(n: int, depth: float, base: float = 100.0) -> list[float]:
    """A symmetric V dip of ``depth`` m at the middle station."""
    mid = (n - 1) / 2.0
    return [base - depth * (1.0 - abs(i - mid) / mid) for i in range(n)]


# ── (a) LONGITUDINAL CAP — the owner's condition 1, hard ────────────
def test_r5_longitudinal_cap_holds_at_every_adjacent_pair():
    """Terrain far steeper than the cap, in both directions, with pegs:
    every emitted adjacent-station grade still obeys the cap."""
    n = 41
    s = _uniform(n)
    f, c = _wide_band(n)
    dem = [100.0 + 7.0 * math.sin(i * 1.1) + 0.9 * i * (i % 3 - 1)
           for i in range(n)]
    out = track_dem_profile(s, f, c, {0: 100.0, 25: 103.0, 40: 99.0},
                            CAP, dem=dem)
    assert out is not None
    for i in range(1, n):
        g = abs(out.z[i] - out.z[i - 1]) / (s[i] - s[i - 1])
        assert g <= CAP + 1e-9, f"segment {i} rides {g * 100:.3f} % > cap"
    assert out.audit.over_cap_segments == 0


# ── (b) A WITHIN-CAP DIP IS TRACKED, NOT BRIDGED ────────────────────
def test_r5_within_cap_dip_is_tracked():
    """CYXY road 349's class: a road between two equal mouth welds over
    a dip the cap can follow.  The tracker follows it (<= 0.5 m); the
    taut string bridges it as a causeway — the measured defect."""
    n = 21
    s = _uniform(n)                     # 200 m of run
    f, c = _wide_band(n)
    dem = _v_dip(n, 2.5)                # 2.5 % flanks, well inside 8 %
    pegs = {0: 100.0, 20: 100.0}

    tracked = track_dem_profile(s, f, c, pegs, CAP, dem=dem)
    assert tracked is not None
    dev = max(abs(tracked.z[i] - dem[i]) for i in range(n))
    assert dev <= 0.5, f"tracker deviates {dev:.3f} m from a within-cap dip"

    strung = solve_run_profile(s, f, c, pegs, CAP, dem=dem)
    assert strung is not None
    causeway = max(strung.z[i] - dem[i] for i in range(n))
    assert causeway > 2.0, (
        "control: the taut string must still bridge the dip (if this "
        "fails the contrast the twin measures no longer exists)")


def test_r5_a_rise_within_cap_is_tracked_exactly():
    """No cap pressure anywhere ⇒ the profile IS the terrain."""
    n = 15
    s = _uniform(n)
    f, c = _wide_band(n)
    dem = [700.0 + 0.5 * i for i in range(n)]      # 5 % < 8 %
    out = track_dem_profile(s, f, c, {}, CAP, dem=dem)
    assert out is not None
    for i in range(n):
        assert out.z[i] == pytest.approx(dem[i], abs=1e-9)
    assert out.audit.dem_departure_stations == 0
    assert out.audit.dem_departure_spans == ()


# ── (c) AN OVER-CAP RISE DEPARTS MINIMALLY, AND THE AUDIT SAYS SO ───
def test_r5_over_cap_rise_departs_minimally_and_is_audited():
    """A 5 m riser across one 10 m station pair is 50 % — five times the
    cap.  The minimum possible sup deviation of ANY cap-Lipschitz
    profile from this terrain is (rise - cap*run)/2 = 2.1 m; the
    tracker attains it, and the audit carries the departure span."""
    n = 21
    s = _uniform(n)
    f, c = _wide_band(n)
    dem = [100.0] * 10 + [105.0] * 11
    out = track_dem_profile(s, f, c, {}, CAP, dem=dem)
    assert out is not None
    dev = max(abs(out.z[i] - dem[i]) for i in range(n))
    optimal = (5.0 - CAP * 10.0) / 2.0
    assert dev == pytest.approx(optimal, abs=1e-6), (
        f"deviation {dev:.4f} m is not the minimal {optimal:.4f} m")
    a = out.audit
    assert a.dem_departure_stations > 0
    assert a.dem_departure_max_m == pytest.approx(optimal, abs=1e-6)
    assert len(a.dem_departure_spans) == 1
    lo_s, hi_s = a.dem_departure_spans[0]
    assert lo_s < s[10] < hi_s or lo_s <= s[9]      # spans the riser
    assert a.dem_departure_max_m > MATERIALITY_M


# ── (d) PEGS ARE EXACT LAW TARGETS ──────────────────────────────────
def test_r5_pegs_are_exact():
    n = 31
    s = _uniform(n)
    f, c = _wide_band(n)
    dem = [100.0 + 3.0 * math.cos(i * 0.7) for i in range(n)]
    pegs = {0: 101.25, 12: 99.5, 30: 100.75}
    out = track_dem_profile(s, f, c, pegs, CAP, dem=dem)
    assert out is not None
    for i, v in pegs.items():
        assert out.z[i] == pytest.approx(v, abs=1e-9), (
            f"peg {i} moved: {out.z[i]} != {v}")


def test_r5_pegs_stay_exact_under_a_tight_band():
    """The tube clamps everywhere, but a peg is a LAW target, not a
    band value."""
    n = 11
    s = _uniform(n)
    f = [99.0] * n
    c = [101.0] * n
    dem = [90.0] * n                    # far below the tube
    out = track_dem_profile(s, f, c, {0: 100.0, 10: 100.4}, CAP, dem=dem)
    assert out is not None
    assert out.z[0] == pytest.approx(100.0, abs=1e-9)
    assert out.z[10] == pytest.approx(100.4, abs=1e-9)
    for v in out.z:
        assert 99.0 - 1e-9 <= v <= 101.0 + 1e-9


# ── (e) NO PEGS AT ALL — the R4-unstrung stretch still tracks ───────
def test_r5_empty_pegs_still_returns_a_profile_that_tracks_dem():
    """R5 SCOPE: outside the pegged span the same tracker applies with
    NO pegs — the stretch R4 left to the pointwise rule."""
    n = 25
    s = _uniform(n)
    f, c = _wide_band(n)
    dem = [89.7 + 0.3 * math.sin(i * 0.4) for i in range(n)]
    out = track_dem_profile(s, f, c, {}, CAP, dem=dem)
    assert out is not None
    assert out.pegs == {}
    assert out.synthetic_end_ties == 0
    for i in range(n):
        assert out.z[i] == pytest.approx(dem[i], abs=1e-9)


def test_r5_no_dem_at_all_returns_none():
    """Nothing to track ⇒ the caller keeps its own fallback."""
    n = 5
    s = _uniform(n)
    f, c = _wide_band(n)
    assert track_dem_profile(s, f, c, {0: 100.0}, CAP,
                             dem=[None] * n) is None


def test_r5_missing_interior_samples_are_bridged():
    n = 9
    s = _uniform(n)
    f, c = _wide_band(n)
    dem = [100.0, None, 100.2, None, None, 100.5, 100.6, None, 100.8]
    out = track_dem_profile(s, f, c, {}, CAP, dem=dem)
    assert out is not None
    assert len(out.z) == n
    for i in range(1, n):
        assert abs(out.z[i] - out.z[i - 1]) / (s[i] - s[i - 1]) <= CAP + 1e-9
    # only really-sampled stations are audited for departure
    assert out.audit.dem_stations == 5      # indices 0, 2, 5, 6, 8


# ── (f) DEM DEVIATION MINTS NO CONFLICT ─────────────────────────────
def test_r5_dem_deviation_mints_zero_conflicts():
    """Owner 2026-08-14: DEM deviation is not an error and is not
    reported.  A terrain the cap cannot follow departs into the AUDIT,
    never into the conflict list."""
    n = 31
    s = _uniform(n)
    f, c = _wide_band(n)
    dem = [100.0 + 20.0 * (i % 2) for i in range(n)]   # 200 % zig-zag
    out = track_dem_profile(s, f, c, {}, CAP, dem=dem)
    assert out is not None
    assert out.conflicts == [], (
        f"DEM deviation minted conflicts: "
        f"{[x.kind for x in out.conflicts]}")
    assert out.audit.dem_departure_stations > 0
    assert out.audit.over_cap_segments == 0


def test_r5_tube_and_peg_conflicts_are_still_reported():
    """The tracker keeps the SAME conflict vocabulary: an inverted tube
    and an unabsorbable peg pair are still named with their numbers."""
    n = 11
    s = _uniform(n)
    f = [100.0] * n
    c = [100.0] * n
    f[5] = 105.0                        # inverted tube at station 5
    dem = [100.0] * n
    out = track_dem_profile(s, f, c, {0: 100.0, 1: 108.0}, CAP, dem=dem)
    assert out is not None
    kinds = {x.kind for x in out.conflicts}
    assert "inverted_tube" in kinds
    assert "peg_pair" in kinds


# ── the airside form is untouched ───────────────────────────────────
def test_r5_taut_string_is_still_the_airside_form():
    """``solve_run_profile`` keeps taut-string semantics (the airside
    spine's law); R5 adds a second objective, it does not replace one."""
    n = 11
    s = _uniform(n)
    f, c = _wide_band(n)
    dem = _v_dip(n, 2.0)
    out = solve_run_profile(s, f, c, {0: 100.0, 10: 100.0}, CAP, dem=dem)
    assert out is not None
    for v in out.z:
        assert v == pytest.approx(100.0, abs=1e-9)
