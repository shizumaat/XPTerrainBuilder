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
