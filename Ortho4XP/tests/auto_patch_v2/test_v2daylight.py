"""THE DAYLIGHT LINE and the LEVEL RINGS VALID BY CONSTRUCTION — lane
``v2daylight``'s twins (owner RULINGS 2026-09-09g and 2026-09-09h; spec
``docs/specs/auto-patch-v2/design-surface-spec.md`` §11).

09g: "the bank foot is the DAYLIGHT (catch) POINT — walking outward from
the boundary ring along its normal, the FIRST station where the 1:3 design
slope line meets the existing DEM within ``bank_daylight_tol_m``, never
nearer than ``bank_min_width_m`` and never farther than
``bank_max_width_m``".  The consequences the owner names are the twins: a
real EMBANKMENT under the pavement edge survives, a PLATEAU EDGE or CLIFF
beyond the daylight point is untouched, a TERRACE is met where it stands.

09h: a level ring is ``cover.buffer(t) ∩ banked_region`` — valid by
construction — never a per-vertex offset, whose self-intersections made
``include_patches`` drop 9 of 39 rings whole at HECA.
"""
from __future__ import annotations

import math

import numpy as np
import pytest

from auto_patch_v2.emit.bank import (BANK_KIND, BankReport, FOOT_KINDS,
                                     daylight_feet, smooth_along, smooth_runs,
                                     with_bank)
from auto_patch_v2.emit.graded import graded_surface
from tests.auto_patch_v2.test_v2smooth import law  # noqa: F401

_K_MIN, _K_DAY, _K_MAX = 0, 1, 2


class _Dem:
    """A synthetic DEM that is a function of the OUTWARD distance ``x``
    only: every twin below walks one ray along +x from the origin."""

    provenance = {"synthetic": "one profile"}

    def __init__(self, profile):
        self._f = profile

    def z(self, x: float, y: float) -> float:
        return float(self._f(float(x)))

    def z_many(self, xs, ys):
        return np.asarray([self._f(float(x)) for x in np.asarray(xs)], float)

    def bounds(self):
        return (-1.0e4, -1.0e4, 1.0e4, 1.0e4)


def _walk(law, z_ring: float, profile):                     # noqa: F811
    """One ray from the origin along +x: its foot distance and its
    classification."""
    d = law.tables.emit.design
    got, kind = daylight_feet(np.array([float(z_ring)]),
                              np.array([[0.0, 0.0]]), np.array([[1.0, 0.0]]),
                              _Dem(profile), d.bank_slope, d.bank_min_width_m,
                              d.bank_max_width_m, d.bank_sample_m,
                              d.bank_daylight_tol_m)
    return float(got[0]), int(kind[0])


# ── (1) THE FIVE DAYLIGHT TWINS, the ruling's own list ─────────────────

def test_a_ring_on_a_real_embankment_daylights_at_the_minimum(law):  # noqa: F811
    """09g: "where the DEM within the first ``bank_min_width_m`` already
    slopes at or steeper than the bank slope in the fill/cut direction (an
    authored earthwork), the foot is at the minimum and the ground is the
    DEM's own bank".  The pavement edge sits on an embankment falling 1:2 —
    steeper than the bank's 1:3 — so the patch banks 5 m and the
    earthwork's own face carries every metre beyond it."""
    d = law.tables.emit.design
    got, kind = _walk(law, 700.0, lambda x: 700.0 - 0.50 * x)
    assert got == pytest.approx(d.bank_min_width_m, abs=1e-9)
    assert FOOT_KINDS[kind] == "min"
    # ... and the embankment beyond the foot is untouched: the bank ends at
    # 5 m, where the DEM still has 100 m of its own fall to give
    assert got < 0.5 * (700.0 - (700.0 - 0.50 * 100.0)) / d.bank_slope


def test_a_ring_six_metres_above_flat_ground_daylights_at_eighteen(law):  # noqa: F811
    """09g's second twin: 6 m of fill over level ground, the 1:3 line
    reaching the DEM 18 m out (6 / 0.33 = 18.2).  The realised bank is the
    law's 1:3 EXACTLY — the walk detects the meeting at a 2 m station and
    the foot is placed at the crossing (§11.6 deviation 1)."""
    d = law.tables.emit.design
    got, kind = _walk(law, 706.0, lambda x: 700.0)
    assert got == pytest.approx(6.0 / d.bank_slope, abs=0.25)   # 18.2 m
    assert FOOT_KINDS[kind] == "daylight"
    assert 6.0 / got == pytest.approx(d.bank_slope, abs=1e-3)


def test_a_plateau_edge_forty_metres_out_is_untouched(law):  # noqa: F811
    """09g: "a PLATEAU EDGE or CLIFF beyond the ring is outside the
    daylight point and untouched".  The ring stands AT the DEM's level on a
    plateau whose edge falls away 40 m out: the slope line meets the ground
    immediately, the foot takes the minimum, and the 40 m of plateau and
    the cliff past it are outside the bank entirely."""
    d = law.tables.emit.design

    def plateau(x):
        return 700.0 if x < 40.0 else 700.0 - 30.0 * (x - 40.0)

    got, kind = _walk(law, 700.0, plateau)
    assert got == pytest.approx(d.bank_min_width_m, abs=1e-9)
    assert FOOT_KINDS[kind] == "min"
    assert got < 40.0                       # the edge is beyond the bank


def test_a_cliff_at_twelve_metres_is_met_at_its_top(law):   # noqa: F811
    """09g's fourth twin: "a cliff at 12 m is met at the cliff top".  The
    ring stands 12 × 0.33 = 3.96 m above level ground, so the 1:3 line
    daylights exactly at 12 m — where a cliff falls 10 m in 2 m.  The foot
    lands on the cliff TOP and the 10 m drop below is the DEM's own."""
    d = law.tables.emit.design
    lift = 12.0 * d.bank_slope

    def cliff(x):
        if x < 12.0:
            return 700.0
        if x < 14.0:
            return 700.0 - 10.0 * (x - 12.0) / 2.0
        return 690.0

    got, kind = _walk(law, 700.0 + lift, cliff)
    assert got == pytest.approx(12.0, abs=0.3)
    assert FOOT_KINDS[kind] == "daylight"
    # the foot is ON the cliff top, not part way down its face
    assert _Dem(cliff).z(got, 0.0) == pytest.approx(700.0, abs=0.2)


def test_ground_rising_to_meet_the_line_daylights_where_it_meets(law):  # noqa: F811
    """09g's fifth twin: "a ring 6 m above ground rising to meet it at 8 m
    daylights at 8 m".  The ground climbs 0.42 m/m, the line falls 0.33
    m/m, and 6 / 0.75 = 8: the terrace's own rise takes the fill away."""
    got, kind = _walk(law, 706.0, lambda x: 700.0 + 0.42 * x)
    assert got == pytest.approx(8.0, abs=0.2)
    assert FOOT_KINDS[kind] == "daylight"


def test_a_cut_ring_walks_the_line_upward(law):             # noqa: F811
    """09g: "down for fill, UP for cut".  A ring 6 m BELOW level ground
    daylights at the same 18 m — the line rises to meet the terrain."""
    d = law.tables.emit.design
    got, kind = _walk(law, 694.0, lambda x: 700.0)
    assert got == pytest.approx(6.0 / d.bank_slope, abs=0.25)
    assert FOOT_KINDS[kind] == "daylight"


def test_a_ray_that_never_daylights_takes_the_maximum(law):  # noqa: F811
    """09g: "a foot that never daylights is placed at the maximum and
    REPORTED by name".  Ground falling at 0.20 m/m under a ring 60 m up:
    the 1:3 line closes on it at 0.13 m/m and would need 460 m."""
    d = law.tables.emit.design
    got, kind = _walk(law, 760.0, lambda x: 700.0 - 0.20 * x)
    assert 60.0 / (d.bank_slope - 0.20) > d.bank_max_width_m
    assert got == pytest.approx(d.bank_max_width_m, abs=1e-9)
    assert FOOT_KINDS[kind] == "max"


def test_the_foot_never_goes_past_the_maximum_width(law):   # noqa: F811
    """The clamp is two-sided and law-valued: no foot of any profile lies
    outside ``[bank_min_width_m, bank_max_width_m]``."""
    d = law.tables.emit.design
    for lift, rate in ((40.0, 0.0), (0.5, 0.0), (-40.0, 0.0), (12.0, -0.30)):
        got, _k = _walk(law, 700.0 + lift, lambda x, r=rate: 700.0 + r * x)
        assert d.bank_min_width_m - 1e-9 <= got <= d.bank_max_width_m + 1e-9


# ── (2) THE TOE IS NEVER SMOOTHED ACROSS A DISCONTINUITY ───────────────

def test_the_toe_smoothing_is_cut_at_a_daylight_jump(law):  # noqa: F811
    """09g (4): "the toe is smoothed in plan along the ring but never
    across a daylight discontinuity — smooth runs are broken where the raw
    daylight distance jumps by more than ``bank_toe_break_m`` between
    neighbours (the toe may jump where the ground does)".  Half a ring
    daylights at 8 m, the other half at 60 m: the step survives, while each
    half's own saw-tooth is smoothed away."""
    d = law.tables.emit.design
    n = 64
    base = np.array([8.0 if k < n // 2 else 60.0 for k in range(n)])
    raw = base + np.array([0.6 if k % 2 else -0.6 for k in range(n)])
    s = np.full(n, 6.0)
    out, runs = smooth_runs(raw.copy(), raw, s, d.bank_foot_smooth,
                            d.bank_toe_break_m)
    assert runs == 2                                # two jumps, two runs
    # THE STEP SURVIVES: the two plateaux are still ~52 m apart
    assert out[n // 4] == pytest.approx(8.0, abs=0.6)
    assert out[3 * n // 4] == pytest.approx(60.0, abs=0.6)
    # ... and the zigzag inside each run is gone
    inner = out[2:n // 2 - 2]
    assert float(np.abs(np.diff(inner)).max()) < 0.2
    # with no jump at all the chain is smoothed CLOSED, exactly as 09f
    flat = np.array([20.0 + (4.0 if k % 2 else -4.0) for k in range(n)])
    closed, runs0 = smooth_runs(flat.copy(), flat, s, d.bank_foot_smooth,
                                d.bank_toe_break_m)
    assert runs0 == 1
    assert np.allclose(closed, smooth_along(flat, s, d.bank_foot_smooth))


def test_an_open_run_never_reaches_around_the_ring(law):     # noqa: F811
    """``smooth_along(closed=False)`` is the RUN operator: its second
    difference runs over the interior stations only, so nothing is carried
    from the run's last station to its first.  A run whose LAST station
    stands 50 m farther out drags station 0 under the CLOSED operator (they
    are ring neighbours) and leaves it alone under the open one — which is
    exactly what 09g (4) forbids across a daylight discontinuity."""
    w = law.tables.emit.design.bank_foot_smooth
    n = 24
    s = np.full(n, 5.0)
    raw = np.full(n, 20.0)
    raw[-1] = 70.0
    closed = smooth_along(raw, s, w, closed=True)
    opened = smooth_along(raw, s, w, closed=False)
    assert float(closed[0]) - 20.0 > 3.0                # dragged around
    assert float(opened[0]) == pytest.approx(20.0, abs=0.05)
    # and a saw-tooth inside the run still loses its curvature
    saw = np.array([20.0 + (3.0 if k % 2 else -3.0) for k in range(n)])
    out = smooth_along(saw, s, w, closed=False)

    def curvature(v):
        return float(np.abs(v[2:] - 2.0 * v[1:-1] + v[:-2]).sum())

    assert curvature(out) < 0.2 * curvature(saw)


# ── (3) THE LEVEL RINGS ARE VALID BY CONSTRUCTION (09h) ────────────────

def test_the_bank_emits_one_closed_foot_ring_and_nothing_between(law):  # noqa: F811
    """The whole pass, end to end, on the §9 apron fixture, RE-SCOPED for
    RULINGS 2026-09-09t: the bank emits ONE CLOSED ``bank_foot`` way per
    boundary and NO level ring, and the daylight classification still
    accounts for every ray."""
    from tests.auto_patch_v2.test_v2bank import _bank, _FlatDem, _built
    from auto_patch_v2.classify.roles import Cell, Classification
    from tests.auto_patch_v2.test_crown import _rect, _rot
    cells = (
        Cell(0, "apron", "apron1", _rect(_rot(90.0), -200.0, 120.0, 200.0, 320.0),
             (), None, "D", "airside", "apron", {}),
    )
    airport, pm, _r = _built(law, _FlatDem(), cells)
    banked, _surf, rep = _bank(airport, pm, law, 6.0)
    zof = {v.id: v.z for v in banked.vertices}
    feet = [b for b in banked.breaklines if b.kind == BANK_KIND]
    assert feet and not [b for b in feet if "@" in b.ref]
    for b in feet:
        assert b.vertices[0] == b.vertices[-1]      # CLOSED (spec §10.5)
        assert all(700.0 - 1e-6 <= zof[v] <= 706.0 + 1e-6 for v in b.vertices)
    # the daylight classification is reported, and it accounts for every ray
    assert rep.at_min + rep.daylighted + rep.at_max == rep.ring_vertices
    assert rep.daylighted > 0 and rep.at_max == 0 and not rep.never_daylight
    assert "DAYLIGHT" in rep.line("TEST")


def test_the_report_names_a_ray_that_never_daylights(law):  # noqa: F811
    """09g: a foot that never daylights is placed at the maximum and
    REPORTED BY NAME.  The apron stands 60 m up over ground that falls
    0.20 m/m away from it, so no ray on the far side ever catches."""
    from tests.auto_patch_v2.test_v2bank import _bank, _built
    from auto_patch_v2.classify.roles import Cell, Classification
    from tests.auto_patch_v2.test_crown import _rect, _rot

    class _Falling:
        provenance = {"synthetic": "0.20 fall"}

        def z(self, x, y):
            return 700.0 - 0.20 * float(x)

        def z_many(self, xs, ys):
            return 700.0 - 0.20 * np.asarray(xs, float)

        def bounds(self):
            return (-9000.0, -9000.0, 9000.0, 9000.0)

    cells = (
        Cell(0, "apron", "apron1", _rect(_rot(90.0), -200.0, 120.0, 200.0, 320.0),
             (), None, "D", "airside", "apron", {}),
    )
    airport, pm, _r = _built(law, _Falling(), cells)
    _banked, _surf, rep = _bank(airport, pm, law, 60.0)
    assert rep.at_max > 0, rep
    assert rep.never_daylight, rep
    assert "@" in rep.never_daylight[0] and "chain" in rep.never_daylight[0]
    # the statistic is the foot NODE's plan distance to the coverage, so a
    # mitred right-angle corner reads its offset parameter times sqrt(2)
    # (the same convention §9's twins record); the parameter itself is
    # clamped at ``bank_max_width_m``
    assert rep.max_m <= law.tables.emit.design.bank_max_width_m \
        * math.sqrt(2.0) + 1e-6, rep
