"""THE APRON FOLLOWS THE GROUND'S 2-D TREND (owner RULINGS 2026-09-10ar;
spec ``docs/specs/auto-patch-v2/design-surface-spec.md`` §8.7; lane
``v2aprontrend``).

§8.6 (2) gave an apron body THREE AFFINE rows, so its least-squares PLANE
follows the ground's — level and tilt.  10ar measured what that still
leaves open: LEMD's T4S apron is ONE 439 x 1,242 m body whose plane was
satisfied while its pit CORNER sat 1.2 m under its own DEM, and the sheet
fell 0.79 m over the last 23.8 m into the basin rim.  A plane has no LOCAL
REACH.

The ruling: an apron body LARGER THAN THE FIT WINDOW targets the ground's
2-D LONG-WAVE TREND at every vertex — a moving quadratic SURFACE fit of
the production DEM, tricube-weighted over
``[design] runway_profile_window_m`` — at the weak ``[design]
apron_trend``, INSTEAD of its three affine rows; a body at or under the
window keeps them.

Three readings, all synthetic, plus the guards:

* A 1.2 km apron over a ground that rises toward one corner with CURVATURE
  the plane cannot state: the corner comes within 0.3 m of its trend, and
  the built body is no longer a single plane.  The CONTROL is the same
  fixture with the trend channel withheld — the affine arm, i.e. main.
* A 100 m apron: nothing changes at all.  No target is published, the three
  affine rows stand, and the built surface is IDENTICAL to the control to
  0.01 m.
* A ground carrying 1 m of noise at a 20 m wavelength: the published target
  is UNMOVED to 0.05 m.  The window is the guard (08t (1)) — the apron
  follows the ground's trend, never the ground.

THE FIXTURE'S RISE IS WHAT THE APRON'S OWN CAP ADMITS.  The brief's shape
is a 20 m rise at one corner of a 1.2 km body; ``common.roles.apron`` caps
an apron at 1.5 % in both directions, and 20 m of rise over 1.2 km of
QUADRATIC ramp reaches 3.3 %, so no lawful apron can sit on it and the
reading would be of the grade law, not of the datum.  The mechanism is
therefore read at ``CORNER_RISE`` (the same SHAPE at the cap), and the
last arm below asserts what the 20 m ground actually gives: the target
still follows the ground, and the built surface is held by the LAW — which
is the ordering the ruling asks for (every law row is senior to the trend).
"""
from __future__ import annotations

import dataclasses as _dc
import math

import numpy as np
import pytest

from auto_patch_v2.classify.roles import Cell, Classification
from auto_patch_v2.constraints import generate
from auto_patch_v2.constraints.apron_trend import (apron_trend_block,
                                                   apron_trend_targets,
                                                   with_apron_trend)
from auto_patch_v2.constraints.runway_chord import with_runway_chord
from auto_patch_v2.constraints.surface_trend import surface_trend_of
from auto_patch_v2.constraints.taxi_trend import with_taxi_trend
from auto_patch_v2.law import Law
from auto_patch_v2.model.airport import Airport, Runway, RunwayEnd, SceneryPack
from auto_patch_v2.model.frame import Frame
from auto_patch_v2.planar.build import build
from auto_patch_v2.solve import Status, solve_design
from tests.auto_patch_v2.test_crown import HALF_WIDTH, _rect, _rot

RUN_LEN = 1600.0
APRON_LEN = 1200.0          # the site's own scale (LEMD T4S: 1,242 m)
APRON_WIDTH = 400.0
#: The corner rise the apron's 1.5 % cap admits over a quadratic ramp of
#: ``APRON_LEN``: a quadratic reaches twice its mean gradient at the far
#: end, so 7 m over 1.2 km peaks at 1.17 %.  Its least-squares PLANE leaves
#: the corner a sixth of the rise out — 1.17 m, the LEMD reading.
CORNER_RISE = 7.0
#: The brief's literal ground, kept as the LAW-BINDS arm (module docstring).
CORNER_RISE_STEEP = 20.0
NOISE_M = 1.0               # the noise the window must ignore ...
NOISE_WAVE_M = 20.0         # ... at this wavelength (08t (1))


class _CornerDem:
    """A ground that rises toward ONE CORNER with CURVATURE — a quadratic
    ramp along the apron's length.  A plane cannot state it: the body's
    least-squares plane leaves the far corner ``rise / 6`` out, which is
    exactly the shape 10ar attributed at LEMD.  ``noise`` adds the 20 m
    ripple the window must ignore."""

    provenance = {"synthetic": "quadratic corner rise"}

    def __init__(self, rise: float = CORNER_RISE, noise: float = 0.0) -> None:
        self.rise = rise
        self.noise = noise

    def z(self, x: float, y: float) -> float:
        t = min(1.0, max(0.0, (x + APRON_LEN / 2.0) / APRON_LEN))
        v = 700.0 + self.rise * t * t
        if self.noise:
            # OFF-AXIS AND OUT OF PHASE: the body's vertices sit on a grid
            # the apron's own edges make, and a ripple along one axis in
            # phase with it samples to exactly zero at every one of them
            s = 0.8 * x + 0.6 * y
            v += self.noise * math.sin(2.0 * math.pi * s / NOISE_WAVE_M + 1.0)
        return v

    def bounds(self):
        return (-9000.0, -9000.0, 9000.0, 9000.0)


def _airport(law, dem):
    r = _rot(90.0)
    frame = Frame("ZZZZ", origin=(60.5, -135.5), identity_dp=11)
    ends = (RunwayEnd("09", r((-RUN_LEN / 2, 0.0)), (60.5, -135.5), 0.0, 0.0,
                      700.0, "fixture"),
            RunwayEnd("27", r((RUN_LEN / 2, 0.0)), (60.5, -135.5), 0.0, 0.0,
                      700.0, "fixture"))
    rw = Runway("09/27", 45.0, 1, ends, 3, "D")
    pack = SceneryPack("fixture", "apt.dat", "0", (), ())
    return Airport("ZZZZ", "Synthetic", frame, 700.0, (rw,), (), (), {}, (),
                   (), (), (), (), (), (), pack, dem, law.ruleset_key), r


def _cells(r, length: float, width: float = APRON_WIDTH):
    """The runway, and ONE apron body of ``length`` x ``width`` beside it."""
    return (
        Cell(0, "runway", "09/27", _rect(r, -RUN_LEN / 2, -HALF_WIDTH,
                                         RUN_LEN / 2, HALF_WIDTH), (), 3, "D",
             "airside", "runway", {}),
        Cell(1, "apron", "apronA",
             _rect(r, -length / 2, 300.0, length / 2, 300.0 + width), (),
             None, "D", "airside", "apron", {}),
    )


def _solve(law, airport, cells, *, trend: bool = True):
    """The pipeline's own order: the runway profile, the taxi chains'
    trend, then the apron bodies' 2-D trend, then the solve.  ``trend=False``
    is THE CONTROL — the affine arm, i.e. main before this round."""
    pm, _st = build(airport, Classification(tuple(cells), (), {}, ()), law)
    pm = with_runway_chord(pm, law, airport)
    pm = with_taxi_trend(pm, law, airport)
    rep_fit: dict = {}
    if trend:
        pm = with_apron_trend(pm, law, airport, rep_fit)
    cs, _c, _w = generate(pm, law, airport)
    sol, rep = solve_design(pm, cs, law)
    assert sol.status in (Status.OPTIMAL, Status.FEASIBLE), sol.message
    z = np.asarray(sol.z, float)
    rep.apron_trend = apron_trend_block(pm, law, z)
    return pm, z, rep, rep_fit


def _apron_vertices(pm):
    out: set[int] = set()
    for f in pm.faces.values():
        if f.role != "apron":
            continue
        for ring in (f.ring, *f.holes):
            out.update(pm.ring_vertices(ring))
    return sorted(out)


def _plane_residual(pm, z, vs) -> float:
    """The worst distance from the BUILT surface to its own least-squares
    PLANE: zero for a body an affine datum can state, and the metres the
    plane cannot reach otherwise."""
    A = np.array([[*pm.vertices[v].xy, 1.0] for v in vs], float)
    y = np.array([float(z[v]) for v in vs], float)
    coef, *_ = np.linalg.lstsq(A, y, rcond=None)
    return float(np.max(np.abs(A @ coef - y)))


@pytest.fixture(scope="module")
def law():
    return Law.for_airport("ZZZZ")


@pytest.fixture(scope="module")
def big(law):
    """The 1.2 km apron on the curved ground — the trend arm and its
    affine CONTROL, one fixture."""
    airport, r = _airport(law, _CornerDem())
    cells = _cells(r, APRON_LEN)
    return (_solve(law, airport, cells, trend=True),
            _solve(law, airport, cells, trend=False))


# ── (1) THE 1.2 km APRON FOLLOWS ITS GROUND'S TREND ─────────────────────

def test_a_body_larger_than_the_window_takes_the_trend_and_no_plane(big, law):
    """The gate (§8.7 (2)): a body whose plan DIAMETER exceeds the window
    carries ONE row per vertex and NO affine rows."""
    (pm, _z, rep, fit), _control = big
    window = float(law.tables.emit.design.runway_profile_window_m)
    assert fit["max_diameter_m"] > window, fit
    assert fit["bodies"] == 1 and fit["bodies_plane"] == 0, fit
    assert fit["vertices"] == len(pm.apron_trend_z) > 0
    assert rep.apron_trend_rows == len(pm.apron_trend_z)
    # the affine rows are GONE for this body — one gate, both decisions
    assert rep.body_datum_bodies == 0 and rep.body_datum_rows == 0
    # the fit's own wall is reported (the round owes it)
    assert fit["fit_wall_s"] >= 0.0 and fit["samples"] > 0
    assert rep.apron_trend["bodies"] == 1 and rep.apron_trend["by_body"]


def test_the_corner_reaches_its_trend_where_the_plane_could_not(big, law):
    """THE SITE, at fixture scale.  The far corner of a 1.2 km apron over a
    ground with CURVATURE: the plane leaves it a sixth of the rise out (the
    LEMD 1.2 m), the trend brings it home."""
    (pm, z, _rep, _fit), (pm_c, z_c, _rep_c, _fc) = big
    vs = _apron_vertices(pm)
    tt = pm.apron_trend_z
    far = max(vs, key=lambda v: pm.vertices[v].xy[0])
    assert far in tt, "the corner carries a trend row"
    off = abs(float(z[far]) - float(tt[far]))
    assert off <= 0.3, f"the corner stands {off:.3f} m off its trend"
    # THE CONTROL: the affine arm leaves the same corner far under its own
    # ground — the defect this round exists to close
    dem_far = float(pm.vertices[far].dem_z)
    ctrl = min((v for v in _apron_vertices(pm_c)),
               key=lambda v: -pm_c.vertices[v].xy[0])
    off_c = abs(float(z_c[ctrl]) - float(pm_c.vertices[ctrl].dem_z))
    off_t = abs(float(z[far]) - dem_far)
    assert off_t < off_c - 0.3, \
        (f"the trend arm sits {off_t:.3f} m off its ground where the affine "
         f"control sits {off_c:.3f} m off — no improvement")
    # and the whole body follows: every vertex within 0.3 m of its target
    worst = max(abs(float(z[v]) - float(t)) for v, t in tt.items())
    assert worst <= 0.3, f"a body vertex stands {worst:.3f} m off its trend"


def test_the_body_is_no_longer_a_single_plane(big):
    """The affine arm can only be a plane; the trend arm bends with the
    ground's own curvature."""
    (pm, z, _rep, _fit), (pm_c, z_c, _rep_c, _fc) = big
    bent = _plane_residual(pm, z, _apron_vertices(pm))
    flat = _plane_residual(pm_c, z_c, _apron_vertices(pm_c))
    assert bent > 0.3, f"the built body is still a plane ({bent:.3f} m)"
    assert bent > 3.0 * flat, (bent, flat)


# ── (2) A SMALL BODY IS UNTOUCHED ───────────────────────────────────────

def test_a_body_inside_the_window_keeps_its_affine_rows_exactly(law):
    """§8.7 (2): inside one window the trend IS the plane, so a small body
    keeps its three ``body_datum`` rows and its built surface is IDENTICAL
    to the control to 0.01 m."""
    airport, r = _airport(law, _CornerDem())
    cells = _cells(r, 100.0, width=80.0)
    pm, z, rep, fit = _solve(law, airport, cells, trend=True)
    pm_c, z_c, rep_c, _fc = _solve(law, airport, cells, trend=False)
    assert not pm.apron_trend_z and fit["bodies"] == 0, fit
    assert fit["bodies_plane"] == 1 and fit["max_diameter_m"] <= fit["window_m"]
    assert rep.apron_trend_rows == 0
    assert rep.body_datum_bodies == rep_c.body_datum_bodies == 1
    assert rep.body_datum_rows == rep_c.body_datum_rows == 3
    d = float(np.max(np.abs(z - z_c)))
    assert d <= 0.01, f"a small body moved {d:.4f} m"


# ── (3) THE WINDOW IS THE GUARD (08t (1)) ───────────────────────────────

def test_noise_at_twenty_metres_does_not_move_the_target(law):
    """1 m of ground noise at a 20 m wavelength moves the published target
    by no more than 0.05 m: the apron follows the ground's TREND, never the
    ground (08t (1), the per-vertex pull this round must not reintroduce)."""
    airport, r = _airport(law, _CornerDem())
    noisy, _r2 = _airport(law, _CornerDem(noise=NOISE_M))
    cells = _cells(r, APRON_LEN)
    pm, _st = build(airport, Classification(cells, (), {}, ()), law)
    pmn, _st2 = build(noisy, Classification(cells, (), {}, ()), law)
    a = apron_trend_targets(pm, law, airport)
    b = apron_trend_targets(pmn, law, noisy)
    assert a and set(a) == set(b)
    # the DEM the two fits saw really does differ by the noise
    spread = max(abs(float(pmn.vertices[v].dem_z) - float(pm.vertices[v].dem_z))
                 for v in a)
    assert spread > 0.5 * NOISE_M, f"the fixture's noise never landed ({spread:.3f} m)"
    moved = max(abs(a[v] - b[v]) for v in a)
    assert moved <= 0.05, f"the noise moved the target {moved:.3f} m"


# ── (4) THE GUARDS ──────────────────────────────────────────────────────

def test_a_runway_vertex_takes_no_apron_trend_row(big, law):
    """The runway owns its own vertices: its contact is hard and flush, and
    two authorities on one vertex is the ``emit consensus`` class."""
    (pm, _z, _rep, _fit), _c = big
    rwy = frozenset(law.tables.precedence.runway_family.members)
    for v in pm.apron_trend_z:
        assert not (set(pm.roles_at(v)) & rwy), v
    # nor does a vertex the taxi chain's trend already holds
    assert not (set(pm.apron_trend_z) & set(pm.taxi_trend_z))


def test_a_degraded_frame_keeps_the_affine_rows(law):
    """Never an invented value (plan §2): where the production DEM frame is
    degraded nothing is fitted and every body keeps its plane."""
    dem = _CornerDem()
    dem.provenance = {"degraded": "fixture"}
    airport, r = _airport(law, dem)
    pm, _st = build(airport, Classification(_cells(r, APRON_LEN), (), {}, ()), law)
    rep: dict = {}
    pm2 = with_apron_trend(pm, law, airport, rep)
    assert pm2 is pm and not pm.apron_trend_z
    assert rep["fallback"] and rep["bodies_plane"] >= 1


def test_the_fit_falls_back_by_degree_never_to_a_value():
    """``surface_trend_of`` over too few samples answers with the degree its
    samples carry — a plane, then their weighted mean — and an empty sample
    set answers ``None``."""
    assert surface_trend_of([], 500.0) is None
    one = surface_trend_of([(0.0, 0.0, 12.0)], 500.0)
    assert one is not None and one.at([10.0], [0.0])[0] == pytest.approx(12.0)
    tri = surface_trend_of([(0.0, 0.0, 0.0), (400.0, 0.0, 4.0),
                            (0.0, 400.0, 2.0)], 500.0)
    # three samples carry a PLANE exactly, not a quadratic
    assert tri.at([200.0], [200.0])[0] == pytest.approx(3.0, abs=1e-6)
    # a query with nothing in its window gets nan, never an invented value
    assert math.isnan(float(tri.at([9000.0], [9000.0])[0]))


# ── (5) THE BRIEF'S LITERAL GROUND: the LAW is senior ───────────────────

def test_a_twenty_metre_corner_is_held_by_the_grade_law_not_the_trend(law):
    """The module docstring's deviation, measured.  20 m of rise over a
    1.2 km quadratic ramp reaches 3.3 % where the apron's cap is 1.5 %: the
    TARGET still follows the ground (it is the same fit), and the built
    surface stops at what the law admits.  Every law row is senior to the
    trend — the ordering the ruling asks for."""
    airport, r = _airport(law, _CornerDem(rise=CORNER_RISE_STEEP))
    pm, z, _rep, fit = _solve(law, airport, _cells(r, APRON_LEN), trend=True)
    assert fit["bodies"] == 1
    tt = pm.apron_trend_z
    # the target is the ground's trend: it spans most of the 20 m rise
    span = max(tt.values()) - min(tt.values())
    assert span > 0.7 * CORNER_RISE_STEEP, f"the target only spans {span:.2f} m"
    # the BUILT surface does not reach it, and the cap is why
    worst = max(abs(float(z[v]) - float(t)) for v, t in tt.items())
    assert worst > 0.3, "the fixture no longer exercises the cap"
    xs = np.array([pm.vertices[v].xy[0] for v in tt], float)
    zs = np.array([float(z[v]) for v in tt], float)
    rise = float(zs.max() - zs.min())
    run = float(xs.max() - xs.min())
    assert rise / run <= 0.016, f"the built body runs at {100 * rise / run:.2f} %"
