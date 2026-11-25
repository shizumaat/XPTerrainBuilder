"""#2077 rule B: the ground is FILLED up to a terrain composite's outer rim
(a shoulder, then a 1:1 talus, only raised, never at the tile's edge, in an
airport patch or against another composite's ground), and a relief skin's
zero footprint is conformed to its frame zero.  A synthetic raster, no
corpus."""
from __future__ import annotations

import math
import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

from auto_patch_v2.airport import terrain_cut as TC  # noqa: E402
from auto_patch_v2.airport import terrain_fill as TF  # noqa: E402
from auto_patch_v2.geom.terrain_deck import UNDER_M  # noqa: E402

LAT, LON = 47.8, 13.04
POST = 5.0 / 111_320.0                 # a 5 m north posting


def _raster(z=400.0, n=161, frozen=None):
    """``n`` x ``n`` postings of ``z`` centred on (LAT, LON), square in
    metres (5 m)."""
    dlon = POST / math.cos(math.radians(LAT))
    h = (n - 1) // 2
    return TF.Raster(np.full((n, n), z, float), LON - h * dlon, LAT + h * POST,
                     dlon, POST, frozen)


def _at(r, x, y):
    to_xy, to_ll = TC.projector(LAT, LON)
    return float(r.sample(*to_ll(np.array([x]), np.array([y])))[0])


def _no_cap(lons, lats):
    return np.full(len(lons), np.inf)


def test_the_shoulder_is_posting_diagonals():
    assert TF._shoulder_m(6.92, 10.31) == pytest.approx(15.52, abs=0.01)   # LOWS
    assert TF.posting_shoulder_m(6.92, 47.8) == pytest.approx(15.52, abs=0.05)
    assert TF.posting_shoulder_m(None, 47.8) == 0.0


def test_a_rim_over_the_ground_is_filled_shoulder_then_talus():
    r = _raster()
    to_xy, to_ll = TC.projector(LAT, LON)
    sxy = np.array([[0.0, 0.0]])
    rep = TF.rim_fill(r, to_xy, to_ll, sxy, np.array([420.0]), _no_cap)
    assert rep == {"supports": 1, "raised": rep["raised"], "unserved": 0}
    w = r.shoulder_m()
    assert _at(r, 0.0, 0.0) == pytest.approx(420.0, abs=1e-6)
    assert w == pytest.approx(8.84, abs=0.01)
    assert _at(r, 0.0, 5.0) == pytest.approx(420.0, abs=0.05)         # in the shoulder
    assert _at(r, 0.0, 15.0) == pytest.approx(420.0 - (15.0 - w), abs=0.2)
    assert _at(r, 0.0, 70.0) == pytest.approx(400.0)                  # beyond the reach
    # only raised: a support under the ground is no support
    r2 = _raster(430.0)
    assert TF.rim_fill(r2, to_xy, to_ll, sxy, np.array([420.0]), _no_cap)["supports"] == 0
    assert (r2.alt == 430.0).all()


def test_the_fill_stays_under_the_cut_bound_and_off_frozen_postings():
    to_xy, to_ll = TC.projector(LAT, LON)
    sxy = np.array([[0.0, 0.0]])
    r = _raster()
    TF.rim_fill(r, to_xy, to_ll, sxy, np.array([420.0]),
                lambda lons, lats: np.full(len(lons), 410.0))
    assert r.alt.max() == pytest.approx(410.0)
    # the tile's edge / an airport patch: a frozen posting never moves
    r = _raster(frozen=lambda rows, cols, lons, lats: lats > LAT - 1e-12)
    rep = TF.rim_fill(r, to_xy, to_ll, sxy, np.array([420.0]), _no_cap)
    assert _at(r, 0.0, 5.0) == pytest.approx(400.0)
    assert _at(r, 0.0, -5.0) == pytest.approx(420.0, abs=0.5)
    assert rep["unserved"] == 1 or _at(r, 0.0, 0.0) >= 419.5


def test_another_composites_ground_is_never_raised_and_unserved_is_counted():
    """Floors win: a posting within W of another composite's plan or zero
    footprint is left to it; the support it leaves floating is counted."""
    to_xy, to_ll = TC.projector(LAT, LON)
    sq = np.array([[-50.0, -50.0], [50.0, -50.0], [50.0, 50.0], [-50.0, 50.0], [-50.0, -50.0]])
    lo, la = to_ll(sq[:, 0], sq[:, 1])
    owned = [TF.Owned((np.c_[lo, la],))]
    r = _raster()
    rep = TF.rim_fill(r, to_xy, to_ll, np.array([[0.0, 0.0], [0.0, 150.0]]),
                      np.array([420.0, 420.0]), _no_cap, owned)
    assert _at(r, 0.0, 0.0) == pytest.approx(400.0)
    assert _at(r, 0.0, 150.0) == pytest.approx(420.0, abs=1e-6)
    assert rep["supports"] == 2 and rep["unserved"] == 1


def test_the_zero_footprint_is_conformed_to_its_plane():
    """2.5: inside the footprint and its shoulder the ground is the plane;
    beyond, clipped to the plane +/- (d - W); never above a terrain
    member's cut bound."""
    to_xy, to_ll = TC.projector(LAT, LON)
    sq = np.array([[-40.0, -40.0], [40.0, -40.0], [40.0, 40.0], [-40.0, 40.0], [-40.0, -40.0]])
    lo, la = to_ll(sq[:, 0], sq[:, 1])
    rings = [np.c_[lo, la]]
    pad = 0.002
    box = (lo.min() - pad, la.min() - pad, lo.max() + pad, la.max() + pad)
    r = _raster(400.0)
    r.alt[:80, :] = 450.0               # the north half: high ground
    k = TF.conform_plane(r, to_xy, rings, 428.4, _no_cap, box)
    w = r.shoulder_m()
    assert k > 0
    assert _at(r, 0.0, 0.0) == pytest.approx(428.4, abs=1e-6)
    assert _at(r, 0.0, -45.0) == pytest.approx(428.4, abs=0.05)       # in the shoulder
    assert _at(r, 0.0, -55.0) == pytest.approx(428.4 - (15.0 - w), abs=0.3)
    assert _at(r, 0.0, 55.0) == pytest.approx(428.4 + (15.0 - w), abs=0.3)
    assert _at(r, 0.0, -120.0) == pytest.approx(400.0)
    # a terrain member's plan over the footprint: raised no higher than it
    r = _raster(400.0)
    TF.conform_plane(r, to_xy, rings, 428.4,
                     lambda lons, lats: np.full(len(lons), 420.0), box)
    assert _at(r, 0.0, 0.0) == pytest.approx(420.0, abs=1e-6)


def test_the_supports_carry_under_m():
    """The fill reaches ``z0 + bot - UNDER_M``: a rim cell is served when its
    ground stands within ``SERVED_M`` of its bottom."""
    r = _raster()
    to_xy, to_ll = TC.projector(LAT, LON)
    rep = TF.rim_fill(r, to_xy, to_ll, np.array([[0.0, 0.0]]),
                      np.array([420.0 - UNDER_M]), _no_cap)
    assert rep["unserved"] == 0


def test_t3_the_quay_keeps_the_ring_a_metre_off_the_water():
    """#2077 round 2 R3 / round 3 R3' (twin T3): the zero footprint's drawn
    ring keeps ``QUAY_M`` off mapped water, EVERY piece is drawn whatever
    its area, and without water the rings are as given."""
    import shapely
    from shapely.geometry import box
    to_xy, to_ll = TC.projector(LAT, LON)
    sq = np.array([[-50.0, -50.0], [50.0, -50.0], [50.0, 50.0], [-50.0, 50.0], [-50.0, -50.0]])
    rings = [np.c_[to_ll(sq[:, 0], sq[:, 1])]]
    # a river across the east part leaves a 2 x 100 m strip beyond it
    water = box(20.0, -80.0, 47.0, 80.0)
    rep = {}
    out = TF.quay_rings(rings, to_xy, to_ll, water, **_GAPS, report=rep)
    assert len(out) == 2 and rep == {"pieces": 2, "merged": 0, "cleaned": 0, "dropped": 0}
    for ring in out:
        xy = np.c_[to_xy(ring[:, 0], ring[:, 1])]
        assert shapely.distance(water, shapely.points(xy)).min() >= TF.QUAY_M - 1e-6
    assert min(np.c_[to_xy(r[:, 0], r[:, 1])][:, 0].max() for r in out) == \
        pytest.approx(20.0 - TF.QUAY_M, abs=1e-6)
    none = TF.quay_rings(rings, to_xy, to_ll, None, **_GAPS)
    assert np.array_equal(none[0], rings[0])


_GAPS = {"degenerate_m": 0.010, "spacing_m": 0.5}


def test_t3p_a_hairline_piece_is_merged_or_cleaned_never_dropped():
    """R3': a piece whose ring carries a vertex under the degenerate gap of
    its neighbour is merged into the pieces within the spacing; alone, its
    ring is cleaned of the degenerate vertex."""
    import shapely
    from shapely.geometry import Polygon
    to_xy, to_ll = TC.projector(LAT, LON)
    alone = Polygon([(0, 0), (5, 0), (5.00001, 0.00001), (5, 5), (0, 5)])   # 14 um segment
    rep = {"pieces": 0, "merged": 0, "cleaned": 0, "dropped": 0}
    out = TF._meshable([alone, Polygon([(20, 0), (25, 0), (25, 5), (20, 5)])], 0.010, 0.5, rep)
    assert rep == {"pieces": 2, "merged": 0, "cleaned": 1, "dropped": 0}
    assert all(shapely.minimum_clearance(p) >= 0.010 for p in out)
    rep = {"pieces": 0, "merged": 0, "cleaned": 0, "dropped": 0}
    beside = Polygon([(5.2, 0), (10, 0), (10, 5), (5.2, 5)])
    out = TF._meshable([alone, beside], 0.010, 0.5, rep)
    assert rep == {"pieces": 1, "merged": 1, "cleaned": 0, "dropped": 0}
    assert out[0].area == pytest.approx(50.0, rel=0.01)


def test_t4_floors_win_in_the_owned_zone():
    """#2077 round 2 R4 (twin T4): another composite's cut bound yields
    within ``W`` of the zero footprint and holds beyond; the composite's
    own members' bound holds throughout."""
    to_xy, to_ll = TC.projector(LAT, LON)
    sq = np.array([[-40.0, -40.0], [40.0, -40.0], [40.0, 40.0], [-40.0, 40.0], [-40.0, -40.0]])
    lo, la = to_ll(sq[:, 0], sq[:, 1])
    rings = [np.c_[lo, la]]
    pad = 0.002
    box_ = (lo.min() - pad, la.min() - pad, lo.max() + pad, la.max() + pad)
    other = lambda lons, lats: np.full(len(lons), 405.0)      # noqa: E731
    r = _raster(400.0)
    TF.conform_plane(r, to_xy, rings, 428.4, _no_cap, box_, other)
    w = r.shoulder_m()
    assert _at(r, 0.0, 0.0) == pytest.approx(428.4, abs=1e-6)            # inside: the plane
    assert _at(r, 0.0, -40.0 - 0.5 * w) == pytest.approx(428.4, abs=0.05)  # in the shoulder
    assert _at(r, 0.0, -40.0 - w - 10.0) == pytest.approx(405.0, abs=1e-6)  # beyond: it holds
    r = _raster(400.0)
    TF.conform_plane(r, to_xy, rings, 428.4, other, box_, _no_cap)        # its own: holds
    assert _at(r, 0.0, 0.0) == pytest.approx(405.0, abs=1e-6)
    assert _at(r, 0.0, -40.0 - 0.5 * w) == pytest.approx(405.0, abs=1e-6)
