"""Tile-seam cut-back pins are HARD DEM anchors (owner ruling 2026-07-24).

    "The nodes along a tile seam at the cutback must be anchored [to the
    DEM] and the solver then grades to it.  Pavement crosses the seam,
    you can't leave any kind of dip there."

``tile_cut`` opens a 10 m gap at each integer lat/lon line; that strip
renders at raw DEM in X-Plane.  Before the ruling, AIRSIDE seam pins were
lifted to ``seam_anchors.runway_clamp_floor()`` — ``runway_elev −
SEAM_CLAMP_GRADE·d``, a floor that made the pin↔runway chain cap-feasible
by construction but parked the pavement edge above the terrain the gap
shows (SPLP measured +0.82…+1.16 m on both tile halves: the gutter the
owner sees where the taxiway crosses the seam).

These tests pin the post-ruling contract at all three writers plus the
solver, and pin the ``O4_SEAM_PIN_CLAMP=1`` restore path so the old
behaviour stays exactly recoverable:

* ``seam_anchors.apply_seam_dem_anchors`` writes the raw DEM sample;
* ``tile_cut._terrain_pin_slice_nodes`` writes the raw DEM sample;
* the solver's seam block (``solver_primitives._seed_elevations``) pins
  each seam vertex HARD at its own DEM value, does NOT move it with the
  pin↔pin projection, and REPORTS the residual instead;
* the pin value depends only on (position, DEM) — never on the runway
  set / profile, which is what keeps two tile builds agreeing at a seam;
* with the gate on, every one of those writers takes the clamp floor
  again.

Hermetic: hand-built layouts + a synthetic analytic DEM, no fixtures, no
network, no X-Plane install.
"""
from __future__ import annotations

import math
import os
import sys

import pytest
from shapely.geometry import Polygon

_THIS_DIR = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_THIS_DIR)
for _p in (os.path.join(_ROOT, "src"),):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import auto_patch.config as cfg                              # noqa: E402
from auto_patch import seam_anchors as SA                    # noqa: E402
from auto_patch import tile_cut as TC                        # noqa: E402
from auto_patch.canonical_points import (                    # noqa: E402
    CanonicalPointRegistry)
from auto_patch.elevation_per_surface import (                # noqa: E402
    solver_primitives as SP)
from auto_patch.layout import (                              # noqa: E402
    ROLE_JUNCTION, ROLE_RUNWAY, vertex_bucket)


# ── synthetic world ──────────────────────────────────────────────────
# One tile at (0, 0).  ``m_to_ll`` is the identity-ish mapping below, so
# the DEM's (lon, lat) offsets are metres and the terrain law is exact.
TILE_LAT = 0
TILE_LON = 0

# Terrain: a plane falling 0.10 m per metre of +x (10 %) — far steeper
# than any pavement cap, so a clamp floor and the raw DEM can never be
# confused for one another.
DEM_BASE = 60.0
DEM_SLOPE = -0.10


class _FakeDEM:
    """Analytic stand-in for ``O4_DEM_Utils.DEM``: ``alt((dlon, dlat))``."""

    nodata = -32768

    def __init__(self, base: float = DEM_BASE, slope: float = DEM_SLOPE):
        self.base = base
        self.slope = slope
        self.calls: list = []

    def alt(self, node):
        dlon, dlat = node[0], node[1]
        self.calls.append((dlon, dlat))
        return self.base + self.slope * dlon


class _Shape:
    def __init__(self, role, polygon, *, ref=None, altitude=None,
                 altitude_high=None, altitude_low=None,
                 node_altitudes=None):
        self.role = role
        self.polygon = polygon
        self.ref = ref
        self.altitude = altitude
        self.altitude_high = altitude_high
        self.altitude_low = altitude_low
        self.node_altitudes = node_altitudes
        self.is_bridge = False
        self.source_axis = None
        self.from_single_poly = False


class _Layout:
    """Minimal ``PavementLayout`` surface the seam writers touch.

    ``m_to_ll`` maps metres straight onto degrees-of-offset from the
    tile origin, so ``_sample_dem`` hands the DEM the same metres back.
    """

    def __init__(self, shapes):
        self.shapes = list(shapes)
        self.canonical_points = CanonicalPointRegistry()
        self.anchor = (0.0, 0.0)

    def m_to_ll(self, x, y):
        return (float(y), float(x))

    def ll_to_m(self, lat, lon):
        return (float(lon), float(lat))


def _dem_at(x: float) -> float:
    return DEM_BASE + DEM_SLOPE * x


# The pavement: a junction square whose EAST edge is the seam cut-back
# (x = 40), and a runway sitting 60 m further west at a much higher
# CIFP elevation.  The clamp floor at the seam edge is therefore
# ``runway_elev − 0.015·d`` — comfortably above the terrain there, so
# the two candidate pin values are unambiguous.
SEAM_X = 40.0
RUNWAY_ELEV = 72.0


def _junction():
    poly = Polygon([(0.0, 0.0), (SEAM_X, 0.0),
                    (SEAM_X, 30.0), (0.0, 30.0)])
    # Pre-solve placeholder altitudes (what the interp pass leaves).
    na = [70.0, 70.0, 70.0, 70.0]
    return _Shape(ROLE_JUNCTION, poly, node_altitudes=na + [na[0]])


def _runway():
    poly = Polygon([(-80.0, 0.0), (-60.0, 0.0),
                    (-60.0, 30.0), (-80.0, 30.0)])
    return _Shape(ROLE_RUNWAY, poly, ref="09/27", altitude=RUNWAY_ELEV)


def _seam_layout():
    layout = _Layout([_junction(), _runway()])
    layout._seam_anchor_keys = {
        vertex_bucket(SEAM_X, 0.0), vertex_bucket(SEAM_X, 30.0)}
    return layout


def _clamp_floor_at(x: float, y: float) -> float:
    """The pre-ruling floor for the fixture (nearest runway point)."""
    d = math.hypot(x - (-60.0), 0.0)
    return RUNWAY_ELEV - SA.SEAM_CLAMP_GRADE * d


# ── 1. apply_seam_dem_anchors ────────────────────────────────────────
def test_apply_seam_dem_anchors_writes_raw_dem_not_clamp_floor():
    """The pre-solve seam writer takes the DEM at the vertex."""
    layout = _seam_layout()
    dem = _FakeDEM()
    n = SA.apply_seam_dem_anchors(layout, dem, TILE_LAT, TILE_LON)
    assert n == 2, "both seam vertices must be pinned"
    jct = layout.shapes[0]
    want = round(_dem_at(SEAM_X), 2)
    floor = _clamp_floor_at(SEAM_X, 0.0)
    assert floor > want + 1.0, "fixture must separate floor from DEM"
    assert jct.node_altitudes[1] == want
    assert jct.node_altitudes[2] == want


def test_apply_seam_dem_anchors_clamp_restored_by_gate(monkeypatch):
    """``O4_SEAM_PIN_CLAMP=1`` restores the pre-ruling clamp floor."""
    monkeypatch.setattr(cfg, "SEAM_PIN_RUNWAY_CLAMP", True)
    layout = _seam_layout()
    SA.apply_seam_dem_anchors(layout, _FakeDEM(), TILE_LAT, TILE_LON)
    jct = layout.shapes[0]
    assert jct.node_altitudes[1] == round(_clamp_floor_at(SEAM_X, 0.0), 2)


def test_seam_pin_ignores_boundary_roles_unchanged():
    """A non-airside role was never clamped — it must still take DEM."""
    from auto_patch.layout import ROLE_BOUNDARY
    poly = Polygon([(0.0, 0.0), (SEAM_X, 0.0),
                    (SEAM_X, 30.0), (0.0, 30.0)])
    layout = _Layout([_Shape(ROLE_BOUNDARY, poly,
                             node_altitudes=[9.0] * 4 + [9.0]),
                      _runway()])
    layout._seam_anchor_keys = {vertex_bucket(SEAM_X, 0.0)}
    SA.apply_seam_dem_anchors(layout, _FakeDEM(), TILE_LAT, TILE_LON)
    assert layout.shapes[0].node_altitudes[1] == round(_dem_at(SEAM_X), 2)


# ── 2. tile_cut slice-edge pin ───────────────────────────────────────
def test_terrain_pin_slice_nodes_writes_raw_dem():
    """The tile-cut cut-back writer takes the DEM at the slice node."""
    from shapely.geometry import box
    layout = _seam_layout()
    piece = _Shape(ROLE_JUNCTION,
                   Polygon([(0.0, 0.0), (SEAM_X, 0.0),
                            (SEAM_X, 30.0), (0.0, 30.0)]))
    # ``cut_union`` = the removed 10 m seam band; its boundary passes
    # through the piece's east edge, marking those two slice nodes.
    cut_union = box(SEAM_X, -10.0, SEAM_X + 10.0, 40.0)
    TC._terrain_pin_slice_nodes(piece, cut_union, (), layout,
                                _FakeDEM(), TILE_LAT, TILE_LON)
    assert piece.node_altitudes is not None
    want = round(_dem_at(SEAM_X), 2)
    assert piece.node_altitudes[1] == want
    assert piece.node_altitudes[2] == want
    assert vertex_bucket(SEAM_X, 0.0) in layout._seam_anchor_keys


def test_terrain_pin_slice_nodes_clamp_restored_by_gate(monkeypatch):
    monkeypatch.setattr(cfg, "SEAM_PIN_RUNWAY_CLAMP", True)
    from shapely.geometry import box
    layout = _seam_layout()
    piece = _Shape(ROLE_JUNCTION,
                   Polygon([(0.0, 0.0), (SEAM_X, 0.0),
                            (SEAM_X, 30.0), (0.0, 30.0)]))
    cut_union = box(SEAM_X, -10.0, SEAM_X + 10.0, 40.0)
    TC._terrain_pin_slice_nodes(piece, cut_union, (), layout,
                                _FakeDEM(), TILE_LAT, TILE_LON)
    assert piece.node_altitudes[1] == round(
        _clamp_floor_at(SEAM_X, 0.0), 2)


# ── 3. the solver's seam block (the authority) ───────────────────────
def _seed(layout, dem):
    nodes, b2i = SP._build_node_list(layout)
    elev, is_hard, have_initial = SP._seed_elevations(
        layout, nodes, b2i, dem=dem,
        tile_lat=TILE_LAT, tile_lon=TILE_LON)
    return nodes, b2i, elev, is_hard, have_initial


def _idx(layout, b2i, x, y):
    return b2i[layout.canonical_points.get_or_add(x, y)]


def test_solver_seam_pin_is_hard_at_its_own_dem_value():
    """The solve's only elevation authority pins the seam node at DEM."""
    layout = _seam_layout()
    dem = _FakeDEM()
    nodes, b2i, elev, is_hard, _hi = _seed(layout, dem)
    for y in (0.0, 30.0):
        i = _idx(layout, b2i, SEAM_X, y)
        assert is_hard[i], "seam pin must be a HARD anchor"
        assert elev[i] == pytest.approx(_dem_at(SEAM_X), abs=1e-6)
    # And published in the protected pin set, so no downstream re-stamp
    # or yield relaxation can move it back off the terrain.
    assert _idx(layout, b2i, SEAM_X, 0.0) in layout._seam_pin_idx


def test_solver_seam_pin_clamp_restored_by_gate(monkeypatch):
    monkeypatch.setattr(cfg, "SEAM_PIN_RUNWAY_CLAMP", True)
    layout = _seam_layout()
    nodes, b2i, elev, is_hard, _hi = _seed(layout, _FakeDEM())
    i = _idx(layout, b2i, SEAM_X, 0.0)
    assert elev[i] == pytest.approx(_clamp_floor_at(SEAM_X, 0.0),
                                    abs=1e-6)
    assert elev[i] > _dem_at(SEAM_X) + 1.0


def test_seam_pin_value_independent_of_runway_profile():
    """Cross-tile determinism: the pin is a function of (position, DEM).

    Two tile builds see DIFFERENT surviving runway pieces after
    ``cut_layout_at_tile_boundaries``; under the old clamp that made the
    two sides compute different floors for the same seam (the 2026-07-05
    3.3 m step).  With the DEM anchor the runway set cannot influence the
    pin at all — assert that directly by re-solving the same seam
    geometry against a runway 20 m higher and one that is absent.
    """
    values = []
    for rw in ("normal", "high", "absent"):
        layout = _seam_layout()
        if rw == "high":
            layout.shapes[1].altitude = RUNWAY_ELEV + 20.0
        elif rw == "absent":
            layout.shapes = [layout.shapes[0]]
        nodes, b2i, elev, _ih, _hi = _seed(layout, _FakeDEM())
        values.append(elev[_idx(layout, b2i, SEAM_X, 0.0)])
    assert values[0] == pytest.approx(values[1], abs=1e-9)
    assert values[0] == pytest.approx(values[2], abs=1e-9)
    assert values[0] == pytest.approx(_dem_at(SEAM_X), abs=1e-6)


# ── 4. pin↔pin: no midpointing, honest report instead ────────────────
def _steep_seam_layout():
    """Two seam pins on ONE ring whose DEM values are far over the taxi
    cap for their separation — the class the pre-ruling POCS split into
    the pins (the midpointing the ruling forbids)."""
    poly = Polygon([(0.0, 0.0), (SEAM_X, 0.0),
                    (SEAM_X, 10.0), (0.0, 10.0)])
    jct = _Shape(ROLE_JUNCTION, poly)
    layout = _Layout([jct])
    layout._seam_anchor_keys = {
        vertex_bucket(SEAM_X, 0.0), vertex_bucket(SEAM_X, 10.0)}
    return layout


class _RidgeDEM(_FakeDEM):
    """+2 m step between the two seam pins over their 10 m ring edge
    (20 % — 13x the 1.5 % junction cap)."""

    def alt(self, node):
        dlon, dlat = node[0], node[1]
        return DEM_BASE + (2.0 if dlat > 5.0 else 0.0)


def test_seam_pins_are_not_midpointed_and_residual_is_reported():
    layout = _steep_seam_layout()
    nodes, b2i, elev, is_hard, _hi = _seed(layout, _RidgeDEM())
    lo = _idx(layout, b2i, SEAM_X, 0.0)
    hi = _idx(layout, b2i, SEAM_X, 10.0)
    # Neither pin moved toward the other: both hold their own DEM.
    assert elev[lo] == pytest.approx(DEM_BASE, abs=1e-6)
    assert elev[hi] == pytest.approx(DEM_BASE + 2.0, abs=1e-6)
    assert is_hard[lo] and is_hard[hi]
    # …and the un-absorbable part of the law is REPORTED, not hidden.
    residuals = getattr(layout, "_seam_pin_residuals", None)
    assert residuals, "an over-cap seam pin pair must be reported"
    worst = residuals[0]
    assert worst["excess_m"] == pytest.approx(
        2.0 - SA.SEAM_CLAMP_GRADE * 10.0, abs=1e-6)
    assert worst["grade"] == pytest.approx(0.20, abs=1e-6)


def test_seam_pins_are_midpointed_again_under_the_gate(monkeypatch):
    """The pre-ruling POCS split (kept recoverable) moves both pins."""
    monkeypatch.setattr(cfg, "SEAM_PIN_RUNWAY_CLAMP", True)
    layout = _steep_seam_layout()
    nodes, b2i, elev, _ih, _hi = _seed(layout, _RidgeDEM())
    lo = _idx(layout, b2i, SEAM_X, 0.0)
    hi = _idx(layout, b2i, SEAM_X, 10.0)
    # Legacy behaviour: the excess is split equally between the pair, so
    # NEITHER pin sits at its own terrain any more.
    assert elev[hi] - elev[lo] == pytest.approx(
        SA.SEAM_CLAMP_GRADE * 10.0, abs=1e-3)
    assert elev[lo] > DEM_BASE + 0.5
    assert elev[hi] < DEM_BASE + 1.5


def test_no_residual_reported_when_dem_is_cap_legal():
    """The report is silent when terrain already obeys the taxi cap."""
    layout = _steep_seam_layout()
    _seed(layout, _FakeDEM(slope=0.0))
    assert getattr(layout, "_seam_pin_residuals", None) == []


# ── 5. a RUNWAY-owned seam bucket (owner rulings 2026-07-25 / 26) ────
#   "every node along the tile seam cutback MUST be exactly at DEM ...
#    definitely including the runway."   (2026-07-25)
#   "ALL nodes along the seam MUST be at exact DEM and anchored BEFORE the
#    solve, then the solver can grade between them and its other anchors to
#    maintain grade."                                        (2026-07-26)
#
# The solver's seam write-back USED to skip any runway-owned bucket that was
# already HARD ("the redistributed FAA profile is authority there") — which
# silently restored the profile value on top of ``tile_cut``'s per-vertex DEM
# pin whenever a later pass re-hardened the vertex.  Under the gate the
# runway bucket is a DEM anchor like every other.
def _runway_seam_layout(profile_alt: float = 70.0):
    """A runway whose EAST edge sits on the cut-back line, carrying HARD
    per-vertex profile altitudes well above the terrain there."""
    poly = Polygon([(0.0, 0.0), (SEAM_X, 0.0),
                    (SEAM_X, 30.0), (0.0, 30.0)])
    na = [profile_alt] * 4
    rw = _Shape(ROLE_RUNWAY, poly, ref="09/27",
                node_altitudes=na + [na[0]])
    layout = _Layout([rw])
    layout._seam_anchor_keys = {
        vertex_bucket(SEAM_X, 0.0), vertex_bucket(SEAM_X, 30.0)}
    return layout


def test_runway_seam_bucket_takes_the_dem_not_the_profile():
    layout = _runway_seam_layout()
    _nodes, b2i, elev, is_hard, _hi = _seed(layout, _FakeDEM())
    want = _dem_at(SEAM_X)
    assert want < 70.0 - 1.0, "fixture must separate profile from DEM"
    for y in (0.0, 30.0):
        i = _idx(layout, b2i, SEAM_X, y)
        assert is_hard[i]
        assert elev[i] == pytest.approx(want, abs=1e-6)


def test_runway_seam_bucket_keeps_the_profile_under_the_gate(monkeypatch):
    """``O4_RUNWAY_SEAM_VERTEX_DEM_PIN=0`` = the pre-2026-07-25 path: the
    runway's redistributed profile stays the authority at its seam."""
    monkeypatch.setattr(cfg, "RUNWAY_SEAM_VERTEX_DEM_PIN", False)
    layout = _runway_seam_layout()
    _nodes, b2i, elev, _ih, _hi = _seed(layout, _FakeDEM())
    i = _idx(layout, b2i, SEAM_X, 0.0)
    assert elev[i] == pytest.approx(70.0, abs=1e-6)
