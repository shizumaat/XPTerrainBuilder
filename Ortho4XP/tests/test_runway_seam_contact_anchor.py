"""A tile seam is ANOTHER runway-grading anchor (owner ruling 2026-07-24).

    "This has never worked, trying to do anything other than DEM at the tile
     seam causes visual disaster in X-Plane.  We are not giving up the CIFP
     thresholds, it's just that a tile seam acts like a crossing runway, it's
     ANOTHER anchor that is part of the runway grading.  The tile seam at ALL
     points must be anchored at DEM."

Every non-runway role takes the seam DEM directly at its own vertex.  A
runway cannot: it also carries CIFP threshold elevations and the FAA grade /
vertical-curve law, and it is laterally FLAT — so its seam contact (a whole
LINE across the runway's width, 148 m of it at SPLP's 18-degree oblique
crossing) has to reach the surface through the one degree of freedom a
runway has, its longitudinal profile.  The seam therefore enters
``runway_redistribute`` exactly the way a crossing-runway anchor does.

What these tests pin:

* the contact is walked at ``RUNWAY_SEAM_CONTACT_STEP_M`` on the tile line
  AND on both ``TILE_CUT_HALF_WIDTH_M`` cut-back lines (the ruling's "the
  nodes along a tile seam at the cutback"), with both extremes always in;
* the one-sided "hump" filter is GONE — a contact whose DEM lies BELOW the
  current profile is anchored just like one above it (that filter is what
  left SPLP's north seam contact floating +0.67 m over the terrain);
* where the terrain across the contact is itself steeper than
  ``MAX_RUNWAY_GRADE``, the law wins and the unreachable samples are
  REPORTED with the grade they would have demanded — never midpointed;
* the accepted anchor set depends only on (whole-runway geometry, DEM), so
  BOTH tile builds derive it identically without seeing each other;
* the gate ``O4_RUNWAY_SEAM_CONTACT=0`` restores the pre-ruling behaviour;
* ``TILE_CUT_HALF_WIDTH_M`` is the single source of truth for the cut-back
  offset shared by ``tile_cut`` and the anchor walk.

Hermetic: hand-built layouts + an analytic DEM.  No fixtures, no network,
no X-Plane install.
"""
from __future__ import annotations

import importlib
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

import auto_patch.pipeline  # noqa: F401,E402  (import-cycle order)
from auto_patch import config as CFG                        # noqa: E402
from auto_patch import runway_redistribute as RR            # noqa: E402
from auto_patch import tile_cut as TC                       # noqa: E402
from auto_patch.canonical_points import (                   # noqa: E402
    CanonicalPointRegistry)
from auto_patch.layout import ROLE_RUNWAY                    # noqa: E402


# ── synthetic world ──────────────────────────────────────────────────
# Tile (0, 1); the airport sits at lat 0.5, lon 1.0, i.e. straddling the
# integer LONGITUDE line lon == 1 — the seam.  Local metres are anchored
# there, so the seam is x == 0.
TILE_LAT = 0
TILE_LON = 1
ANCHOR_LAT = 0.5
ANCHOR_LON = 1.0
M_PER_DEG = 111320.0
SEAM_X = 0.0


class _FakeDEM:
    """Analytic ``O4_DEM_Utils.DEM`` stand-in.

    ``alt((dlon, dlat))`` takes DEGREES of offset from the tile origin (as
    ``elevation._sample_dem`` hands them over); the terrain law below is
    written in the layout's local METRES, so convert on the way in.
    """

    nodata = -32768

    def __init__(self, fn):
        self.fn = fn

    def alt(self, node):
        dlon, dlat = float(node[0]), float(node[1])
        x = (dlon + TILE_LON - ANCHOR_LON) * M_PER_DEG
        y = (dlat + TILE_LAT - ANCHOR_LAT) * M_PER_DEG
        return self.fn(x, y)


class _Shape:
    def __init__(self, role, polygon, *, ref=None, node_altitudes=None):
        self.role = role
        self.polygon = polygon
        self.ref = ref
        self.altitude = None
        self.altitude_high = None
        self.altitude_low = None
        self.node_altitudes = node_altitudes
        self.is_bridge = False
        self.source_axis = None
        self.from_single_poly = True


class _Layout:
    def __init__(self, shapes):
        self.shapes = list(shapes)
        self.canonical_points = CanonicalPointRegistry()
        self.anchor = (ANCHOR_LAT, ANCHOR_LON)

    def m_to_ll(self, x, y):
        return (ANCHOR_LAT + float(y) / M_PER_DEG,
                ANCHOR_LON + float(x) / M_PER_DEG)

    def ll_to_m(self, lat, lon):
        return ((float(lon) - ANCHOR_LON) * M_PER_DEG,
                (float(lat) - ANCHOR_LAT) * M_PER_DEG)


# ── the runway ────────────────────────────────────────────────────────
# A 2000 m runway running due EAST (so station == x) with a half-width of
# 20 m, crossing the seam line x = 1.0 square-on.  Square-on keeps the
# contact geometry trivial for the walk tests; the oblique case (where the
# contact spans real station) gets its own layout below.
HALF_W = 20.0


# ── an OBLIQUE crossing, the SPLP shape ──────────────────────────────
# Runway bearing 18 degrees off the seam line: the contact spans
# ``2*HALF_W / sin(18deg)`` ~ 129 m of runway length, so the profile can
# legitimately hold several DEM values at once.
OBLIQUE = math.radians(18.0)


def _oblique_runway(length=2000.0):
    ux, uy = math.sin(OBLIQUE), math.cos(OBLIQUE)
    nx, ny = uy, -ux
    cx, cy = SEAM_X, 0.0
    pts = []
    for s, w in ((-length / 2, -HALF_W), (length / 2, -HALF_W),
                 (length / 2, HALF_W), (-length / 2, HALF_W)):
        pts.append((cx + s * ux + w * nx, cy + s * uy + w * ny))
    return _Shape(ROLE_RUNWAY, Polygon(pts), ref="02/20"), (ux, uy), length


def _m_to_ll(x, y):
    return (ANCHOR_LAT + y / M_PER_DEG, ANCHOR_LON + x / M_PER_DEG)


def _oblique_ends(u, length):
    """Physical-end (lat, lon) of the oblique runway — DEGREES, which is
    what ``_find_edge_boundary_crossings`` expects."""
    ux, uy = u
    return (_m_to_ll(SEAM_X - (length / 2) * ux, -(length / 2) * uy),
            _m_to_ll(SEAM_X + (length / 2) * ux, (length / 2) * uy))


# ═════════════════════════ contact walk ══════════════════════════════

class TestSeamContactWalk:
    """``_find_edge_boundary_crossings`` samples the WHOLE contact."""

    def test_walks_the_contact_at_the_configured_step(self):
        # Flat terrain: every sample is the same value, so the test is
        # purely about HOW MANY / WHERE, not about elevations.
        dem = _FakeDEM(lambda x, y: 50.0)
        shape, u, length = _oblique_runway()
        layout = _Layout([shape])
        a_ll, b_ll = _oblique_ends(u, length)
        two = RR._find_edge_boundary_crossings(
            layout, [shape], a_ll, b_ll, dem, TILE_LAT, TILE_LON)
        walked = RR._find_edge_boundary_crossings(
            layout, [shape], a_ll, b_ll, dem, TILE_LAT, TILE_LON,
            step_m=10.0)
        assert len(two) == 2, "un-stepped call is the historical 2 extremes"
        # 2*HALF_W / sin(18 deg) ~ 129 m of contact -> ~12 interior samples.
        assert len(walked) >= 12
        # The two extremes survive the walk.
        assert min(t for t, _ in walked) == pytest.approx(
            min(t for t, _ in two), abs=1e-9)
        assert max(t for t, _ in walked) == pytest.approx(
            max(t for t, _ in two), abs=1e-9)
        # Sorted by station, as every caller assumes.
        assert walked == sorted(walked)

    def test_cutback_lines_extend_the_contact_span(self):
        """The ruling names the CUT-BACK nodes: the walk must cover the two
        lines where ``tile_cut`` actually ends the pavement, not only the
        tile line.  On an oblique crossing that widens the station span the
        crossing occupies — which is exactly what buys the profile the
        grade headroom to sit on terrain at both ends."""
        dem = _FakeDEM(lambda x, y: 50.0)
        shape, u, length = _oblique_runway()
        layout = _Layout([shape])
        a_ll, b_ll = _oblique_ends(u, length)
        line_only = RR._find_edge_boundary_crossings(
            layout, [shape], a_ll, b_ll, dem, TILE_LAT, TILE_LON,
            step_m=10.0)
        with_cutback = RR._find_edge_boundary_crossings(
            layout, [shape], a_ll, b_ll, dem, TILE_LAT, TILE_LON,
            step_m=10.0, cutback_m=CFG.TILE_CUT_HALF_WIDTH_M)
        span_line = (max(t for t, _ in line_only)
                     - min(t for t, _ in line_only)) * length
        span_cut = (max(t for t, _ in with_cutback)
                    - min(t for t, _ in with_cutback)) * length
        # Each cut-back line moves its contact 5 m / sin(18 deg) ~ 16 m of
        # station further out, on BOTH sides.
        assert span_cut > span_line + 25.0

    def test_tile_cut_half_width_is_the_single_source_of_truth(self):
        # The walk samples the cut-back lines at whatever offset tile_cut
        # actually cuts at; a second copy of "5.0" would silently un-anchor
        # the cut-back the day either moved.
        import inspect
        default = inspect.signature(
            TC.cut_layout_at_tile_boundaries
        ).parameters["half_width_m"].default
        assert default == CFG.TILE_CUT_HALF_WIDTH_M


# ═════════════════ feasibility selection + reporting ═════════════════

class TestFeasibleAnchorSelection:
    """``_select_feasible_seam_anchors`` — DEM everywhere the law allows,
    an honest report everywhere it does not."""

    PHYS = 1000.0

    def test_gentle_terrain_anchors_every_sample(self):
        # 0.5 % across the contact: every candidate is reachable.
        cands = [(0.30 + 0.01 * k, 50.0 + 0.05 * k) for k in range(6)]
        acc, rej = RR._select_feasible_seam_anchors(cands, self.PHYS)
        assert acc == cands
        assert rej == []

    def test_keeps_both_extremes_when_mutually_feasible(self):
        # Convex terrain: flat across most of the contact then a late 4.5 %
        # rise.  The two visible contacts are 1.25 % apart (legal) so BOTH
        # are held; every interior sample would need > cap to reach the far
        # anchor and is reported instead.
        cands = [(0.30, 50.0), (0.31, 50.02), (0.32, 50.03),
                 (0.33, 50.05), (0.34, 50.50)]
        acc, rej = RR._select_feasible_seam_anchors(cands, self.PHYS)
        assert acc[0] == (0.30, 50.0)
        assert acc[-1] == (0.34, 50.50)
        assert rej, "the steep interior must be reported, not silently kept"
        # Every reported conflict names the grade it would have demanded.
        for _t, _v, g in rej:
            assert g > CFG.RUNWAY_MAX_GRADE

    def test_reports_when_even_the_two_extremes_conflict(self):
        # 3 % between the two visible contacts: no profile can hold both.
        cands = [(0.30, 50.0), (0.32, 50.6)]
        acc, rej = RR._select_feasible_seam_anchors(cands, self.PHYS)
        assert acc == [(0.30, 50.0)]
        assert len(rej) == 1
        assert rej[0][0] == 0.32
        assert rej[0][2] == pytest.approx(0.03, rel=1e-6)

    def test_accepted_set_is_never_steeper_than_the_law(self):
        # A 1 % ramp with one spike in it: the spike is dropped, the rest
        # anchored, and every accepted pair stays inside the cap.
        cands = [(0.30, 50.00), (0.305, 50.05), (0.31, 50.40),
                 (0.315, 50.15), (0.32, 50.20)]
        acc, rej = RR._select_feasible_seam_anchors(cands, self.PHYS)
        assert (0.31, 50.40) not in acc
        assert len(acc) == 4
        assert [r[0] for r in rej] == [0.31]
        for (t0, e0), (t1, e1) in zip(acc, acc[1:]):
            d = (t1 - t0) * self.PHYS
            assert abs(e1 - e0) / d <= CFG.RUNWAY_MAX_GRADE + 1e-9

    def test_selection_is_order_independent_of_input_shuffle(self):
        # Cross-tile determinism relies on the SET, not the arrival order.
        cands = [(0.30, 50.0), (0.31, 50.02), (0.32, 50.03),
                 (0.33, 50.05), (0.34, 50.50)]
        acc_a, rej_a = RR._select_feasible_seam_anchors(cands, self.PHYS)
        acc_b, rej_b = RR._select_feasible_seam_anchors(
            list(reversed(cands)), self.PHYS)
        assert acc_a == acc_b
        assert rej_a == rej_b


# ══════════════ the one-sided filter is gone (the defect) ════════════

class TestBelowProfileContactIsAnchored:
    """The pre-ruling code kept only contacts where the DEM poked ABOVE the
    profile.  At SPLP that discarded the runway's north seam contact, so the
    pavement met terrain at one end of the crossing and floated +0.67 m over
    it at the other — one-sided anchoring, exactly what the ruling forbids.
    """

    def _run(self, dem_fn, monkeypatch=None):
        shape, u, length = _oblique_runway()
        layout = _Layout([shape])
        a_ll, b_ll = _oblique_ends(u, length)
        return RR._find_edge_boundary_crossings(
            layout, [shape], a_ll, b_ll, _FakeDEM(dem_fn),
            TILE_LAT, TILE_LON, step_m=10.0,
            cutback_m=CFG.TILE_CUT_HALF_WIDTH_M)

    def test_contact_below_the_profile_is_still_a_candidate(self):
        # Terrain rising gently with y: the low-station end of the contact
        # sits BELOW any flat profile and the high end ABOVE it.  Both must
        # come back as candidates.
        cands = self._run(lambda x, y: 50.0 + 0.008 * y)
        assert len(cands) > 2
        lo = min(v for _t, v in cands)
        hi = max(v for _t, v in cands)
        assert lo < 50.0 < hi, "candidates must straddle, not be hump-only"

    def test_both_extremes_survive_selection_on_gentle_terrain(self):
        cands = self._run(lambda x, y: 50.0 + 0.008 * y)
        acc, _rej = RR._select_feasible_seam_anchors(cands, 2000.0)
        assert acc[0] == min(cands)
        assert acc[-1] == max(cands)
        # ...and they really are on opposite sides of the mean, i.e. the
        # profile is pulled DOWN at one end and UP at the other.
        assert acc[0][1] < acc[-1][1]


# ═══════════════════ cross-tile determinism ══════════════════════════

class TestCrossTileDeterminism:
    """Both tile builds must derive the SAME anchor set without seeing each
    other.  They do because ``redistribute_runway_profile`` runs BEFORE
    ``tile_cut``, so each build measures the contact on the WHOLE runway,
    and the DEM at the tile line is the ``preserve_boundary``-blended value
    both tiles share.
    """

    def test_identical_anchor_set_from_either_side_of_the_seam(self):
        def terrain(x, y):
            return 50.0 + 0.006 * y + 0.4 * math.sin(y / 37.0)

        shape, u, length = _oblique_runway()
        a_ll, b_ll = _oblique_ends(u, length)

        # Tile WEST of the seam and tile EAST of the seam: same whole-runway
        # geometry, same DEM, independently built layouts.
        west = _Layout([_oblique_runway()[0]])
        east = _Layout([_oblique_runway()[0]])
        out = []
        for layout in (west, east):
            cands = RR._find_edge_boundary_crossings(
                layout, layout.shapes, a_ll, b_ll, _FakeDEM(terrain),
                TILE_LAT, TILE_LON, step_m=CFG.RUNWAY_SEAM_CONTACT_STEP_M,
                cutback_m=CFG.TILE_CUT_HALF_WIDTH_M)
            out.append(RR._select_feasible_seam_anchors(cands, length))
        (acc_w, rej_w), (acc_e, rej_e) = out
        assert acc_w == acc_e
        assert rej_w == rej_e
        assert len(acc_w) >= 2

    def test_anchor_values_do_not_depend_on_the_runway_set(self):
        """A seam anchor is (position, DEM) only.  Nothing about which
        shapes survived a tile cut, or where a runway sits relative to the
        pin, may enter — that is what made the pre-2026-07-24 clamp floor
        diverge between the two sides of a seam."""
        def terrain(x, y):
            return 50.0 + 0.006 * y

        shape, u, length = _oblique_runway()
        a_ll, b_ll = _oblique_ends(u, length)
        bare = _Layout([shape])
        # Same runway, but the layout also holds an unrelated second runway
        # far away (what a neighbour-tile build would carry).
        other = _Shape(ROLE_RUNWAY,
                       Polygon([(500.0, 500.0), (900.0, 500.0),
                                (900.0, 540.0), (500.0, 540.0)]),
                       ref="18/36")
        crowded = _Layout([_oblique_runway()[0], other])
        a = RR._find_edge_boundary_crossings(
            bare, [bare.shapes[0]], a_ll, b_ll, _FakeDEM(terrain),
            TILE_LAT, TILE_LON, step_m=10.0,
            cutback_m=CFG.TILE_CUT_HALF_WIDTH_M)
        b = RR._find_edge_boundary_crossings(
            crowded, [crowded.shapes[0]], a_ll, b_ll, _FakeDEM(terrain),
            TILE_LAT, TILE_LON, step_m=10.0,
            cutback_m=CFG.TILE_CUT_HALF_WIDTH_M)
        assert a == b


# ══════════════════════════ the gate ═════════════════════════════════

class TestGate:
    def test_gate_off_restores_the_two_extremes_only_walk(self, monkeypatch):
        monkeypatch.setenv("O4_RUNWAY_SEAM_CONTACT", "0")
        cfg = importlib.reload(CFG)
        try:
            assert cfg.RUNWAY_SEAM_CONTACT_ANCHORS is False
        finally:
            monkeypatch.delenv("O4_RUNWAY_SEAM_CONTACT", raising=False)
            importlib.reload(CFG)
        assert CFG.RUNWAY_SEAM_CONTACT_ANCHORS is True

    def test_no_seam_means_no_work_and_no_change(self):
        """An airport whose runway bbox contains no integer lat/lon line has
        no seam, so the walk must do nothing at all — no DEM reads, no
        candidates.  (Verified end-to-end too: CYXY, which has no integer
        line inside its footprint, emits a byte-identical patch body with
        the gate on and off.)"""
        reads = []

        def terrain(x, y):
            reads.append((x, y))
            return 50.0

        # A runway parked well inside the tile, nowhere near lon == 1.
        poly = Polygon([(-3000.0, -HALF_W), (-1000.0, -HALF_W),
                        (-1000.0, HALF_W), (-3000.0, HALF_W)])
        shape = _Shape(ROLE_RUNWAY, poly, ref="09/27")
        layout = _Layout([shape])
        a_ll = _m_to_ll(-3000.0, 0.0)
        b_ll = _m_to_ll(-1000.0, 0.0)
        out = RR._find_edge_boundary_crossings(
            layout, [shape], a_ll, b_ll, _FakeDEM(terrain),
            TILE_LAT, TILE_LON, step_m=CFG.RUNWAY_SEAM_CONTACT_STEP_M,
            cutback_m=CFG.TILE_CUT_HALF_WIDTH_M)
        assert out == []
        assert reads == [], "no seam must cost zero DEM samples"

    def test_step_zero_is_the_historical_behaviour(self):
        dem = _FakeDEM(lambda x, y: 50.0 + 0.006 * y)
        shape, u, length = _oblique_runway()
        layout = _Layout([shape])
        a_ll, b_ll = _oblique_ends(u, length)
        assert len(RR._find_edge_boundary_crossings(
            layout, [shape], a_ll, b_ll, dem, TILE_LAT, TILE_LON,
            step_m=0.0, cutback_m=0.0)) == 2


# ═════════════ end-to-end: the DEM reaches the pavement ══════════════

def _profile_state(u, length, thresh_a, thresh_b, n=41):
    """The emit-time ``layout._runway_profile_state`` entry a CIFP build
    leaves behind: a straight CIFP line between two anchored thresholds."""
    a_ll, b_ll = _oblique_ends(u, length)
    fr = [i / (n - 1) for i in range(n)]
    return {("RW02", "RW20"): {
        'phys_end_a_ll': a_ll,
        'phys_end_b_ll': b_ll,
        'fractions': fr,
        'elevs': [thresh_a + (thresh_b - thresh_a) * f for f in fr],
        'anchored': [i in (0, n - 1) for i in range(n)],
        'phys_dist_m': length,
        'blast_a_m': 0.0,
        'blast_b_m': 0.0,
    }}


class TestEndToEndSeamAnchoring:
    """``redistribute_runway_profile`` must put the EMITTED runway surface
    on the DEM at the seam — that is the whole point of the ruling."""

    def _build(self, terrain, thresh_a=40.0, thresh_b=70.0):
        shape, u, length = _oblique_runway()
        layout = _Layout([shape])
        layout._runway_profile_state = _profile_state(
            u, length, thresh_a, thresh_b)
        n = RR.redistribute_runway_profile(
            layout, _FakeDEM(terrain), TILE_LAT, TILE_LON)
        return layout, shape, u, length, n

    def test_profile_meets_the_dem_at_the_seam_contact(self):
        # Terrain that rises gently along the runway: reachable within cap,
        # so every accepted contact must come out EXACTLY on the DEM.
        def terrain(x, y):
            return 55.0 + 0.004 * y

        layout, _shape, _u, _length, n = self._build(terrain)
        assert n >= 1, "the runway shape must have been rewritten"
        audit = layout._runway_seam_audit["02/20"]
        assert audit['anchored'], "no seam contact was anchored at all"
        for a in audit['anchored']:
            assert abs(a['residual_m']) < 0.01, (
                f"anchored seam contact off the DEM by "
                f"{a['residual_m']:.3f} m")

    def test_a_below_profile_contact_pulls_the_runway_DOWN(self):
        """The regression the ruling names: a seam whose terrain sits BELOW
        the CIFP-linear profile must still move the runway.  Pre-ruling the
        below-profile side was filtered out and the pavement floated."""
        def terrain(x, y):
            # Flat terrain well BELOW the 40->70 CIFP line at the seam
            # (which passes ~55 m there).
            return 52.0

        layout, shape, u, length, _n = self._build(terrain)
        prof = layout._runway_redistributed_profiles["02/20"]
        # Evaluate the redistributed profile at the seam contact.
        mid = RR.sample_redistributed_profile(layout, "02/20", SEAM_X, 0.0)
        assert mid is not None
        assert mid < 55.0 - 0.5, (
            "the seam DEM below the profile did not pull the runway down "
            f"(profile at the seam = {mid:.2f} m)")
        assert prof['seam_t'], "no seam anchor entered the profile"

    def test_law_conflicts_are_reported_not_midpointed(self):
        # Terrain across the contact steeper than the runway may be.
        def terrain(x, y):
            return 55.0 + 0.05 * y

        layout, _shape, _u, _length, _n = self._build(terrain)
        conflicts = getattr(layout, "_runway_seam_law_conflicts", [])
        assert conflicts, "an impossible seam must be reported"
        for c in conflicts:
            assert c['grade_needed'] > c['grade_cap']
            assert c['ref'] == "02/20"
            assert 'station_m' in c and 'dem_m' in c

    def test_cifp_threshold_shift_is_recorded(self):
        def terrain(x, y):
            return 55.0 + 0.004 * y

        layout, _shape, _u, _length, _n = self._build(terrain)
        shift = layout._runway_seam_audit["02/20"]['cifp_threshold_shift_m']
        assert len(shift) == 2
        # The ruling keeps the CIFP thresholds: whatever the seam demanded,
        # the move must be recorded so it is never silent.
        assert all(isinstance(v, float) for v in shift)

    def test_both_tile_builds_emit_the_same_profile(self):
        """Cross-tile determinism at the level that matters: the two builds
        produce the same elevation at every station, so any shared seam
        position agrees."""
        def terrain(x, y):
            return 55.0 + 0.004 * y

        a, _s, _u, length, _n = self._build(terrain)
        b, _s2, _u2, _l2, _n2 = self._build(terrain)
        pa = a._runway_redistributed_profiles["02/20"]
        pb = b._runway_redistributed_profiles["02/20"]
        assert pa['fractions'] == pb['fractions']
        assert pa['elevs'] == pb['elevs']
        assert pa['seam_t'] == pb['seam_t']
