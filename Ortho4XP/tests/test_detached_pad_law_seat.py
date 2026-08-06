"""DETACHED BUILDING PADS SEAT BY LAW — item 3(b), 2026-08-05.

OWNER LAW (RULINGS 2026-08-05, "DEM's role, and the constant-DEM
invariant"): *"DEM chooses WHERE in the lawful band a thing seats.  It
never shapes the band, never constrains, never blocks."*

A pad that touches no qualifying airside pavement used to be HARD-PINNED
at its raw-DEM footprint median for the whole solve
(``build_detached_pad_dem_pins`` + ``config.DETACHED_PAD_DEM_PIN``), and
excluded from every movable-pad relaxation.  Both are DELETED.  These
twins pin the replacement:

* the pad is a GROUNDSIDE object, so its datum is the SOLVED groundside
  pavement it abuts, resolved by the adjacent-ground foot rule
  (interpolate two solved host ring variables);
* buildings are FLAT, so the lawful levels are the INTERSECTION over the
  pad's contacts of ``[datum − cap·d, datum + cap·d]``;
* the DEM seed picks the point INSIDE that box and nothing else — which
  is the constant-DEM oracle in unit form: the same solved hosts give the
  SAME box in the plateau and canyon worlds, while the seat saturates at
  the FLOOR and the CEILING respectively;
* NO HOST ⇒ NO BOX and no write.  A missing datum never falls back to
  the DEM sample; that fallback is the defect this replaced.

No network, no DEM, no fixtures: a stub layout and arithmetic.
"""
from __future__ import annotations

import os
import sys

import pytest
from shapely.geometry import Polygon

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from auto_patch.elevation_per_surface.route_profile import (  # noqa: E402
    anchors as A)
from auto_patch.layout import (                               # noqa: E402
    ROLE_BUILDING, ROLE_GROUNDSIDE_PAVEMENT, ROLE_SERVICE_ROAD)

CAP = 0.05                      # GROUNDSIDE_MAX_GRADE, the lot's own cap


class _CPS:
    """Exact-coordinate registry (the real one interns within 0.5 m;
    these twins place every point far enough apart that the two agree)."""

    def get_or_add(self, x, y):
        return (round(float(x), 6), round(float(y), 6))


class _Shape:
    def __init__(self, role, ring):
        self.role = role
        self.polygon = Polygon(ring + [ring[0]])


class _Layout:
    def __init__(self, shapes):
        self.canonical_points = _CPS()
        self.shapes = list(shapes)


# ── the fixture geometry ─────────────────────────────────────────────
# A groundside LOT (y ≤ 10) solved at 100 m, and a building pad hovering
# 1 m clear of its edge.  The pad's two near vertices foot onto the lot's
# top edge at d = 1 m; its far vertices are 5 m away, past the contact
# radius, so they contribute nothing.
_LOT = [(0.0, 0.0), (20.0, 0.0), (20.0, 10.0), (0.0, 10.0)]
_PAD = [(5.0, 11.0), (9.0, 11.0), (9.0, 15.0), (5.0, 15.0)]
_ROAD = [(0.0, 15.0), (20.0, 15.0), (20.0, 20.0), (0.0, 20.0)]

_B2I = {(0.0, 0.0): 0, (20.0, 0.0): 1, (20.0, 10.0): 2, (0.0, 10.0): 3,
        (5.0, 11.0): 4, (9.0, 11.0): 5, (9.0, 15.0): 6, (5.0, 15.0): 7,
        (0.0, 15.0): 8, (20.0, 15.0): 9, (20.0, 20.0): 10,
        (0.0, 20.0): 11}
_PAD_IDX = [4, 5, 6, 7]


def _elev(pad_seed, lot=100.0, road=110.0):
    return [lot, lot, lot, lot,
            pad_seed, pad_seed, pad_seed, pad_seed,
            road, road, road, road]


def _layout(with_road=False):
    shapes = [_Shape(ROLE_GROUNDSIDE_PAVEMENT, _LOT),
              _Shape(ROLE_BUILDING, _PAD)]
    if with_road:
        shapes.append(_Shape(ROLE_SERVICE_ROAD, _ROAD))
    return _Layout(shapes)


def _pad_shape(layout):
    return [s for s in layout.shapes if s.role == ROLE_BUILDING][0]


# ══════════════════════════════════════════════════════════════════════
# THE DEM PIN IS GONE
# ══════════════════════════════════════════════════════════════════════

class TestThePinIsDeleted:
    def test_the_dem_pin_builder_no_longer_exists(self):
        assert not hasattr(A, "build_detached_pad_dem_pins"), (
            "the raw-DEM hard pin is DEM as a constraint (RULINGS "
            "2026-08-05); it was replaced by a groundside law seat")

    def test_the_gate_no_longer_exists(self):
        from auto_patch import config
        assert not hasattr(config, "DETACHED_PAD_DEM_PIN")

    def test_no_pass_publishes_the_detached_exclusion_set(self):
        """``layout._detached_pad_node_idx`` kept detached pads out of
        every movable-pad relaxation because they carried a DEM value to
        protect.  With the value chosen by law and bounded by a
        ``seat_boxes`` box, the exclusion is retired — a detached pad is
        an ordinary movable FLAT pad group."""
        import inspect
        from auto_patch.elevation_per_surface.route_profile import solve
        src = inspect.getsource(solve)
        assert "layout._detached_pad_node_idx = " not in src
        assert "seat_detached_pads_by_law" in src


# ══════════════════════════════════════════════════════════════════════
# MEMBERSHIP + THE BAND WITHHOLDING (the attributed writer)
# ══════════════════════════════════════════════════════════════════════

class TestMembership:
    def test_a_pad_with_no_seated_ring_node_is_detached(self):
        lay = _layout()
        pads = A.detached_pad_nodes(lay, _B2I, {})
        assert [idx for (_s, idx) in pads] == [_PAD_IDX]

    def test_a_seated_ring_node_disqualifies_the_pad(self):
        """The SEAT producer owns the airside-service verdict; this reads
        it rather than re-deriving it (one instrument, one population —
        the exact failure that let the airside band reach a pad the seat
        had refused)."""
        lay = _layout()
        assert A.detached_pad_nodes(lay, _B2I, {5: 100.0}) == []


class TestBandWithholding:
    def test_the_airside_band_is_withheld_from_exactly_the_pad_nodes(self):
        """THE SOURCE FIX.  ``raster_reach_band._domain_geom`` admits every
        ROLE_BUILDING polygon to the airside propagation domain with no
        service test, so a detached pad inherits an airside route FLOOR
        (``spine_value_fields``) that ``one_profile_solve`` clamps it up
        to at warm start and holds every sweep — the measured KBNA
        plateau.  Withholding the band is what removes that writer."""
        lay = _layout()
        pads = A.detached_pad_nodes(lay, _B2I, {})
        band = [(170.0, 175.0)] * 12
        withheld = A.withhold_airside_band_from_detached_pads(band, pads)
        assert withheld == set(_PAD_IDX)
        assert all(band[i] is None for i in _PAD_IDX)
        assert all(band[i] == (170.0, 175.0)
                   for i in range(12) if i not in _PAD_IDX)

    def test_withholding_never_adds_a_bound(self):
        """Constant-DEM safety by construction: the pass only ever writes
        ``None``, so it cannot manufacture a bound in either world."""
        import inspect
        src = inspect.getsource(A.withhold_airside_band_from_detached_pads)
        assigns = [ln for ln in src.splitlines()
                   if "node_band[i]" in ln and "=" in ln]
        assert assigns and all("None" in ln for ln in assigns)


# ══════════════════════════════════════════════════════════════════════
# THE LAW BOX — solved host variables only
# ══════════════════════════════════════════════════════════════════════

class TestLawBox:
    def test_the_box_is_the_host_datum_plus_or_minus_cap_times_reach(self):
        lay = _layout()
        lo, hi, n_c, n_x = A.detached_pad_law_box(
            lay, _B2I, _elev(1.0), _pad_shape(lay), _PAD_IDX, CAP)
        assert n_c == 2 and n_x == 0        # the two near vertices only
        assert lo == pytest.approx(100.0 - CAP * 1.0)
        assert hi == pytest.approx(100.0 + CAP * 1.0)

    def test_the_datum_is_the_foot_lerp_of_two_solved_host_variables(self):
        """A SLOPED host (2 %, inside the lot's own cap): the pad's near
        vertices foot at x = 5 and x = 9 on the lot's top edge, whose ends
        are solved 100.0 and 100.4.  The datum is the INTERPOLATION of two
        solved variables — the adjacent-ground foot rule — and the box is
        the intersection of the two contacts' intervals.  No DEM term
        appears anywhere in it."""
        lay = _layout()
        elev = _elev(1.0)
        elev[3] = 100.0                     # (0, 10)
        elev[2] = 100.4                     # (20, 10)
        lo, hi, n_c, n_x = A.detached_pad_law_box(
            lay, _B2I, elev, _pad_shape(lay), _PAD_IDX, CAP)
        # foot at x=5 → 100.10, at x=9 → 100.18, both at d = 1 m
        assert n_c == 2 and n_x == 0
        assert lo == pytest.approx(100.18 - CAP)
        assert hi == pytest.approx(100.10 + CAP)

    def test_no_host_means_no_box_never_a_dem_fallback(self):
        lay = _Layout([_Shape(ROLE_BUILDING, _PAD)])   # nothing to abut
        assert A.detached_pad_law_box(
            lay, _B2I, _elev(1.0), _pad_shape(lay), _PAD_IDX,
            CAP) == (None, None, 0, 0)

    def test_an_empty_intersection_is_a_DECLARED_conflict(self):
        """Two hosts a flat pad cannot both meet is the split-level-seat
        law's trigger (RULINGS 2026-08-04) — counted and reported, never
        silently resolved; the first claimant's box is kept, exactly as
        the adjacent-ground foot rule does."""
        lay = _layout(with_road=True)
        lo, hi, n_c, n_x = A.detached_pad_law_box(
            lay, _B2I, _elev(1.0), _pad_shape(lay), _PAD_IDX, CAP)
        assert n_c == 4 and n_x == 2
        assert lo == pytest.approx(100.0 - CAP)        # first claimant
        assert hi == pytest.approx(100.0 + CAP)


# ══════════════════════════════════════════════════════════════════════
# THE SEAT — and the constant-DEM oracle in unit form
# ══════════════════════════════════════════════════════════════════════

class TestSeat:
    def _seat(self, pad_seed):
        lay = _layout()
        elev = _elev(pad_seed)
        pads = A.detached_pad_nodes(lay, _B2I, {})
        seats, stats = A.seat_detached_pads_by_law(
            lay, _B2I, elev, pads, CAP)
        return lay, elev, seats, stats

    def test_the_pad_seats_flat_inside_its_box(self):
        _lay, elev, seats, stats = self._seat(100.02)
        assert stats == (1, 0, 0)
        assert len({round(v, 9) for v in seats.values()}) == 1
        assert seats[4] == pytest.approx(100.02)
        assert all(elev[i] == pytest.approx(100.02) for i in _PAD_IDX)

    def test_the_box_is_registered_on_the_seat_boxes_channel(self):
        """The ratified bounded-yield channel: fp#8 and the final
        projection both resolve ``seat_boxes`` by canonical key, so the
        pad rides the existing group-bounds machinery."""
        lay, _elev, _seats, _stats = self._seat(100.0)
        from auto_patch.elevation_per_surface.node_space import store_of
        boxes = store_of(lay).raw("seat_boxes")
        for (x, y) in _PAD:
            assert boxes[(x, y)] == pytest.approx(
                (100.0 - CAP, 100.0 + CAP))

    # ── THE ORACLE ────────────────────────────────────────────────────
    def test_the_box_is_identical_in_both_constant_dem_worlds(self):
        """ASSERTION: the DEM never shapes the band.  Same solved hosts,
        two seeds 10 km apart, one box."""
        from auto_patch.constant_dem import (
            CANYON_ELEVATION_M, PLATEAU_ELEVATION_M)
        lay = _layout()
        box_lo = A.detached_pad_law_box(
            lay, _B2I, _elev(PLATEAU_ELEVATION_M), _pad_shape(lay),
            _PAD_IDX, CAP)
        box_hi = A.detached_pad_law_box(
            lay, _B2I, _elev(CANYON_ELEVATION_M), _pad_shape(lay),
            _PAD_IDX, CAP)
        assert box_lo == box_hi

    def test_the_plateau_world_seats_at_the_floor_the_canyon_at_the_ceiling(
            self):
        """ADDENDUM assertion 2 (extreme-seating saturation) and 3 (the
        band-width field): the two worlds differ by exactly the box
        width, which is what the emitted difference field must show."""
        from auto_patch.constant_dem import (
            CANYON_ELEVATION_M, PLATEAU_ELEVATION_M)
        _l, _e, lo_seats, _s = self._seat(PLATEAU_ELEVATION_M)
        _l2, _e2, hi_seats, _s2 = self._seat(CANYON_ELEVATION_M)
        assert lo_seats[4] == pytest.approx(100.0 - CAP)   # FLOOR
        assert hi_seats[4] == pytest.approx(100.0 + CAP)   # CEILING
        assert hi_seats[4] - lo_seats[4] == pytest.approx(2 * CAP)

    def test_a_hostless_pad_keeps_its_seed_and_is_reported(self):
        lay = _Layout([_Shape(ROLE_BUILDING, _PAD)])
        elev = _elev(158.0)
        before = list(elev)
        pads = A.detached_pad_nodes(lay, _B2I, {})
        seats, stats = A.seat_detached_pads_by_law(
            lay, _B2I, elev, pads, CAP)
        assert seats == {} and stats == (0, 1, 0)
        assert elev == before
