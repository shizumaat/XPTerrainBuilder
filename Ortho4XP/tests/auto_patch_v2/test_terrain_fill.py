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


def _feather(r, sxy, e, f=TF.FEATHER_M):
    to_xy, to_ll = TC.projector(LAT, LON)
    return TF.edge_feather(r, to_xy, to_ll, np.asarray(sxy, float), np.asarray(e, float), f)


def _apply(r, got):
    rows, cols, d = got
    r.alt[rows, cols] += d
    return r


def test_the_feather_only_lowers_and_fades_to_zero_at_its_reach():
    """#2272 round 2 S4: a body edge 6 m under our ground -- the ground at
    the edge takes all of it, half of it at half the reach, nothing at
    the reach; a residual over the ground (``e > 0``) moves nothing."""
    sxy = [[0.0, 0.0]]
    r = _raster()
    rows, cols, d = _feather(r, sxy, [-6.0])
    assert len(d) and (d < 0.0).all() and d.min() >= -6.0 - 1e-9
    _apply(r, (rows, cols, d))
    assert _at(r, 0.0, 0.0) == pytest.approx(394.0, abs=1e-6)
    assert _at(r, 0.0, 30.0) == pytest.approx(397.0, abs=0.02)
    assert _at(r, 0.0, 60.0) == pytest.approx(400.0, abs=0.02)
    assert _at(r, 0.0, 80.0) == pytest.approx(400.0)
    assert not len(_feather(_raster(), sxy, [3.0])[2])


def test_the_feather_is_continuous():
    """Neighbouring postings differ by no more than the feather's slope
    (the edge's residuals blended, the weight linear in distance)."""
    sxy = np.c_[np.linspace(-50.0, 50.0, 21), np.zeros(21)]
    e = -6.0 - 4.0 * np.sin(np.linspace(0.0, 3.0, 21))
    r = _raster()
    _apply(r, _feather(r, sxy, e))
    d = r.alt - 400.0
    step = max(np.abs(np.diff(d, axis=0)).max(), np.abs(np.diff(d, axis=1)).max())
    assert step <= 10.0 * 5.0 / TF.FEATHER_M + 0.5


def test_the_feather_is_zero_at_a_frozen_posting_and_never_under_the_sea():
    """The weight fades to zero at frozen ground (``Raster.frozen_dist``):
    a frozen posting never moves, one a quarter reach from it takes a
    quarter of the weight; the ground is never lowered under min(ground, 0)."""
    sxy = [[0.0, 0.0]]
    frozen = lambda rows, cols, lons, lats: lats > LAT + 20.0 / 111_320.0   # noqa: E731
    r = _raster(frozen=frozen)
    r.frozen_dist = lambda rows, cols, lons, lats: np.maximum(   # noqa: E731
        (LAT + 20.0 / 111_320.0 - lats) * 111_320.0, 0.0)
    _apply(r, _feather(r, sxy, [-8.0]))
    assert _at(r, 0.0, 25.0) == pytest.approx(400.0)               # frozen
    assert _at(r, 0.0, 5.0) == pytest.approx(400.0 - 8.0 * (55.0 / 60.0) * (15.0 / 60.0), abs=0.02)
    r = _raster(3.0)
    _apply(r, _feather(r, sxy, [-20.0]))
    assert r.alt.min() == pytest.approx(0.0)


def test_two_abutting_shells_take_one_correction():
    """Two shells' feathers over the same postings: the stage keeps the
    most negative, never their sum (``terrain_cut_stage._feather``)."""
    import types

    from auto_patch import terrain_cut_stage as TCS
    to_xy, to_ll = TC.projector(LAT, LON)

    class _Fit:          # no body: every posting is outside it
        pass
    r = _raster()
    comps = []
    for _side in (-10.0, 10.0):
        comps.append(types.SimpleNamespace(
            rec={"cut": {"shell": True}}, fit=_Fit(), to_xy=to_xy, to_ll=to_ll, owned=TF.Owned()))
    res = {id(comps[0].rec): (np.array([[-10.0, 0.0]]), np.array([-4.0])),
           id(comps[1].rec): (np.array([[10.0, 0.0]]), np.array([-6.0]))}
    orig = TC.cut_heights
    TC.cut_heights = lambda fit, to_xy, lons, lats, g: (np.asarray(g, float),
                                                        np.zeros(len(lons), bool))
    try:
        k, worst = TCS._feather(r, comps, res)
    finally:
        TC.cut_heights = orig
    assert k > 0 and worst == pytest.approx(6.0, abs=0.05)
    single = _raster()
    _apply(single, _feather(single, [[10.0, 0.0]], [-6.0]))
    assert r.alt.min() >= single.alt.min() - 1e-6
    assert (r.alt <= single.alt + 1e-6).all()




def test_a_shell_rim_under_the_water_is_never_filled_nor_feathered(monkeypatch):
    """RULINGS 2026-11-25a (3): a coastal shell runs under the water.  Its
    rim and body edge seated under the sea datum are no supports: the rim
    fill lifts no water posting from them and the feather never lowers a
    posting under the sea datum (nor moves one at or under it)."""
    import types

    from auto_patch import terrain_cut_stage as TCS
    from auto_patch_v2.airport import terrain_model as TM
    from auto_patch_v2.geom.terrain_deck import DeckGrid
    n = 41
    h = (n - 1) / 2.0
    i, _j = np.mgrid[0:n, 0:n]
    top = np.where(i < 10, -6.0, 8.0) + 0.0 * i      # the west quarter under the sea
    g = DeckGrid(-h * 5.0, -h * 5.0, top.copy(), top.astype(float))
    monkeypatch.setattr(TM, "plan_grid", lambda p: g)
    rec = {"id": "s", "resource": "s.obj", "elevation": 0.0, "icao": "T",
           "cut": {"file": "s.obj", "lat": LAT, "lon": LON, "heading": 0.0,
                   "fill": True, "shell": True}}
    nn = 401
    dlon = POST / math.cos(math.radians(LAT))
    hh = (nn - 1) // 2
    alt = np.full((nn, nn), -2.0, np.float32)             # the sea, 2 m deep
    cols = np.arange(nn)
    alt[:, cols > hh - 40] = 20.0                         # land from 50 m west of the anchor
    dem = types.SimpleNamespace(x0=0.0, x1=(nn - 1) * dlon, y0=0.0, y1=(nn - 1) * POST,
                                alt_dem=alt.copy())
    tile = types.SimpleNamespace(lat=LAT + hh * POST - (nn - 1) * POST,
                                 lon=LON - hh * dlon, dem=dem)
    monkeypatch.setattr(TCS, "_wet", lambda tile, dem, rows, cols: np.zeros(len(rows), bool))
    res = TCS._residuals(dem, tile, [rec])
    sxy, e = res[id(rec)]
    assert len(sxy) and np.all(e <= 0.0)
    TCS.bake(tile, [rec])
    sea = alt <= 0.0
    assert np.all(dem.alt_dem[sea] <= alt[sea] + 1e-6)          # no water lifted
    assert dem.alt_dem[~sea].min() >= -1e-6                     # never under the datum
