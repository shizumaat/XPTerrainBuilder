"""#2077 round 2 R2 (twin T2): the terrain composites' planes and fills
never move water.  The bake records its planes' and fills' change beside
the ``.alt``; the mesh step takes it off every water-valued vertex
(Triangle4XP's bilinear ``altitude()``), a land vertex is untouched, and
without a sidecar nothing moves.  Synthetic raster, no corpus."""
from __future__ import annotations

import os
import sys
import types

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

import O4_File_Names as FNAMES  # noqa: E402
from auto_patch import terrain_cut_stage as TCS  # noqa: E402


def _bilinear(a, frame, x, y):
    x0, y0, x1, y1 = frame
    ny, nx = a.shape
    px, py = (x - x0) / (x1 - x0) * (nx - 1), (y1 - y) / (y1 - y0) * (ny - 1)
    i, j = int(np.floor(px)), int(np.floor(py))
    rx, ry = px - i, py - j
    return (a[j, i] * (1 - rx) * (1 - ry) + a[j, i + 1] * rx * (1 - ry)
            + a[j + 1, i] * (1 - rx) * ry + a[j + 1, i + 1] * rx * ry)


@pytest.fixture
def tile(tmp_path, monkeypatch):
    path = str(tmp_path / "Data.alt.unfill.npz")
    monkeypatch.setattr(FNAMES, "alt_unfill_file", lambda t: path)
    rng = np.random.default_rng(7)
    a0 = 400.0 + rng.random((101, 101)).astype(np.float32)
    dem = types.SimpleNamespace(x0=-0.01, y0=-0.01, x1=1.01, y1=1.01, alt_dem=a0.copy())
    return types.SimpleNamespace(lat=47, lon=13, dem=dem, iterate=0, a0=a0, path=path)


def _fill(tile):
    """A plane's change in a window, recorded as ``_fill_all`` does."""
    a = tile.dem.alt_dem
    a[40:60, 30:55] = 429.5
    d = a - tile.a0
    ii, jj = np.nonzero(d)
    tile.dem.terrain_fill_delta = {"rows": ii.astype(np.int32), "cols": jj.astype(np.int32),
                                   "delta": d[ii, jj].astype(np.float32), "nx": 101, "ny": 101,
                                   "frame": np.array([-0.01, -0.01, 1.01, 1.01])}


def test_t2_a_water_vertex_reads_the_unfilled_raster(tile):
    _fill(tile)
    TCS.write_unfill(tile)
    assert os.path.exists(tile.path)
    frame = (-0.01, -0.01, 1.01, 1.01)
    pts = [(0.35, 0.5), (0.452, 0.4137), (0.30001, 0.5899), (0.8, 0.8)]   # in, in, edge, far
    v = np.zeros(6 * (len(pts) + 1))
    for k, (x, y) in enumerate(pts):
        v[6 * k], v[6 * k + 1], v[6 * k + 2] = x, y, _bilinear(tile.dem.alt_dem, frame, x, y)
    land = len(pts)
    v[6 * land], v[6 * land + 1], v[6 * land + 2] = 0.4, 0.5, 429.5
    rep = TCS.unfill_water(tile, v, set(range(len(pts))))
    for k, (x, y) in enumerate(pts):
        assert v[6 * k + 2] == pytest.approx(_bilinear(tile.a0, frame, x, y), abs=1e-4)
    assert v[6 * land + 2] == 429.5                         # land: untouched
    assert rep["vertices"] >= 2 and rep["worst_m"] > 25.0


def test_t2_no_change_no_sidecar_no_move(tile):
    _fill(tile)
    TCS.write_unfill(tile)
    tile.dem.terrain_fill_delta = None
    TCS.write_unfill(tile)                                   # a stale one is removed
    assert not os.path.exists(tile.path)
    v = np.array([0.4, 0.5, 429.5, 0, 0, 0], float)
    assert TCS.unfill_water(tile, v, {0}) == {"vertices": 0, "worst_m": 0.0}
    assert v[2] == 429.5


def test_t2_the_bake_records_its_planes_and_fills_alone(monkeypatch):
    """The recorded change is ``after - (after the cuts)``: taken off, the
    raster is the cut raster, never the uncut one."""
    from auto_patch_v2.airport import terrain_cut as TC
    from auto_patch_v2.airport import terrain_model as TM
    from auto_patch_v2.geom.terrain_deck import CELL_M, DeckGrid
    i, j = np.mgrid[0:9, 0:9]
    top = 30.0 + 10.0 * np.exp(-((i - 4) ** 2 + (j - 4) ** 2) / 8.0)
    top[0, :] = top[-1, :] = top[:, 0] = top[:, -1] = 5.0
    g = DeckGrid(-4.5 * CELL_M, -4.5 * CELL_M, top - 2.0, top)
    monkeypatch.setattr(TM, "plan_grid", lambda p: g)
    lat, lon = 47.5, 13.5
    to_xy, to_ll = TC.projector(lat, lon)
    sq = np.array([[60.0, -40.0], [140.0, -40.0], [140.0, 40.0], [60.0, 40.0], [60.0, -40.0]])
    ring = np.c_[to_ll(sq[:, 0], sq[:, 1])]
    rec = {"id": "dsf:obj1", "resource": "s.obj", "elevation": 400.0,
           "cut": {"file": "s.obj", "lat": lat, "lon": lon, "heading": 0.0, "fill": True,
                   "plane": {"z": 401.0, "rings": [ring.tolist()]}}}
    n = 2001
    ground = 380.0 + np.linspace(0.0, 60.0, n, dtype=np.float32)[None, :].repeat(n, 0)
    mk = lambda: types.SimpleNamespace(lat=47, lon=13, iterate=0, dem=types.SimpleNamespace(  # noqa: E731
        x0=0.0, x1=1.0, y0=0.0, y1=1.0, alt_dem=ground.copy()))
    t, cut_only = mk(), mk()
    TCS.bake(t, [rec])
    TCS.bake(cut_only, [dict(rec, cut={k: v for k, v in rec["cut"].items()
                                       if k not in ("fill", "plane")})])
    d = t.dem.terrain_fill_delta
    assert d is not None and len(d["rows"]) > 0
    un = t.dem.alt_dem.copy()
    un[d["rows"], d["cols"]] -= d["delta"]
    assert np.abs(un - cut_only.dem.alt_dem).max() < 1e-4
    assert not np.array_equal(cut_only.dem.alt_dem, ground)        # the cut is kept


# -- round 3 (master ruling R2'): the dry raster ---------------------------

def _dry(tile):
    """A plane's change, half of it kept off the mesher's raster (``held``)
    as ``_fill_all`` keeps the postings near mapped water."""
    a = tile.dem.alt_dem
    a[40:60, 30:55] = 429.5
    d = a - tile.a0
    ii, jj = np.nonzero(d)
    wet = jj >= 43
    ch = d[ii, jj].astype(np.float32)
    tile.dem.terrain_fill_delta = {"rows": ii.astype(np.int32), "cols": jj.astype(np.int32),
                                   "delta": np.where(wet, 0, ch).astype(np.float32),
                                   "held": np.where(wet, ch, 0).astype(np.float32),
                                   "nx": 101, "ny": 101,
                                   "frame": np.array([-0.01, -0.01, 1.01, 1.01])}


def test_r2p_write_alt_keeps_the_held_postings_at_their_cut_ground(tile, tmp_path, monkeypatch):
    alt = str(tmp_path / "Data.alt")
    monkeypatch.setattr(FNAMES, "alt_file", lambda t: alt)
    _dry(tile)
    full = tile.dem.alt_dem.copy()
    tile.dem.write_to_file = lambda path: tile.dem.alt_dem.astype(np.float32).tofile(path)
    TCS.write_alt(tile)
    written = np.fromfile(alt, np.float32).reshape(101, 101)
    assert np.array_equal(tile.dem.alt_dem, full)                 # memory keeps the plane
    assert np.allclose(written[40:60, 43:55], tile.a0[40:60, 43:55], atol=1e-4)
    assert np.array_equal(written[40:60, 30:43], full[40:60, 30:43])
    assert os.path.exists(tile.path)


def test_r2p_land_reads_the_conformed_raster_water_the_cut_raster(tile):
    """Whatever the ``.alt`` carries, the sidecar gives a land vertex the
    conformed raster and a water vertex the raster before the planes."""
    _dry(tile)
    TCS.write_unfill(tile)
    d = tile.dem.terrain_fill_delta
    full = tile.dem.alt_dem.copy()
    written = full.copy()
    written[d["rows"], d["cols"]] -= d["held"]
    frame = (-0.01, -0.01, 1.01, 1.01)
    pts = [(0.35, 0.5), (0.452, 0.4137), (0.5, 0.45), (0.8, 0.8)]
    v = np.zeros(6 * len(pts))
    for k, (x, y) in enumerate(pts):
        v[6 * k], v[6 * k + 1], v[6 * k + 2] = x, y, _bilinear(written, frame, x, y)
        v[6 * k + 3] = v[6 * k + 4] = 0.25
    water, land = {0, 1}, (2, 3)
    TCS.unfill_water(tile, v, water)
    rep = TCS.refill_land(tile, v, water)
    for k in water:
        assert v[6 * k + 2] == pytest.approx(_bilinear(tile.a0, frame, *pts[k]), abs=1e-3)
    for k in land:
        assert v[6 * k + 2] == pytest.approx(_bilinear(full, frame, *pts[k]), abs=1e-3)
    assert rep["vertices"] == 1 and v[6 * 2 + 3] == 0 and v[6 * 3 + 3] == 0.25


def test_r2p_the_bake_keeps_the_plane_off_the_raster_near_water(monkeypatch):
    """``_fill_all`` holds exactly the changed postings within ``DRY_M`` of
    the tile's mapped water."""
    from auto_patch_v2.airport import terrain_cut as TC
    from auto_patch_v2.airport import terrain_fill as TF
    from auto_patch_v2.airport import terrain_model as TM
    from auto_patch_v2.geom.terrain_deck import CELL_M, DeckGrid
    from shapely.geometry import box
    i, j = np.mgrid[0:9, 0:9]
    top = np.full((9, 9), 5.0)
    g = DeckGrid(-4.5 * CELL_M, -4.5 * CELL_M, top - 2.0, top)
    monkeypatch.setattr(TM, "plan_grid", lambda p: g)
    lat, lon = 47.5, 13.5
    to_xy, to_ll = TC.projector(lat, lon)
    sq = np.array([[60.0, -40.0], [240.0, -40.0], [240.0, 40.0], [60.0, 40.0], [60.0, -40.0]])
    ring = np.c_[to_ll(sq[:, 0], sq[:, 1])]
    rec = {"id": "dsf:obj1", "resource": "s.obj", "elevation": 400.0,
           "cut": {"file": "s.obj", "lat": lat, "lon": lon, "heading": 0.0,
                   "plane": {"z": 420.0, "rings": [ring.tolist()]}}}
    wx = np.array([300.0, 340.0]); wlo, _ = to_ll(wx, np.zeros(2))
    water = box(wlo[0] - 13, 0.4, wlo[1] - 13, 0.6)                 # a river 40 m east
    monkeypatch.setattr(TCS, "_tile_water", lambda t: water)
    n = 2001
    ground = np.full((n, n), 400.0, np.float32)
    t = types.SimpleNamespace(lat=47, lon=13, iterate=0, dem=types.SimpleNamespace(
        x0=0.0, x1=1.0, y0=0.0, y1=1.0, alt_dem=ground.copy()))
    TCS.bake(t, [rec])
    d = t.dem.terrain_fill_delta
    x, _ = to_xy(13 + d["cols"] / (n - 1.0), 47 + 1 - d["rows"] / (n - 1.0))
    dist = np.where(x < 300.0, 300.0 - x, 0.0)
    held = d["held"] != 0
    assert held.any() and (~held).any()
    assert np.all(dist[held] <= TF.DRY_M + 1.0) and np.all(dist[~held] >= TF.DRY_M - 1.0)
    assert np.allclose(d["delta"][held], 0) and np.allclose(d["held"][~held], 0)


def test_r2p_wet_weight_cells_are_the_fill_boxes_cells_over_water(monkeypatch):
    """A fill record's box cells that meet mapped water, none in a held
    box, none without water."""
    from shapely.geometry import box
    recs = [{"cut": {"fill": True}}, {"cut": {"erode_m": 3.0}}]
    boxes = [(False, (13.100, 47.100, 13.120, 47.120)), (True, (13.100, 47.100, 13.105, 47.120))]
    monkeypatch.setattr(TCS, "_weight_boxes", lambda r: boxes)
    t = types.SimpleNamespace(lat=47, lon=13)
    monkeypatch.setattr(TCS, "_tile_water", lambda tt: None)
    assert len(TCS.wet_weight_cells(t, recs)[0]) == 0
    monkeypatch.setattr(TCS, "_tile_water", lambda tt: box(0.1096, 0.1, 0.1114, 0.2))
    rows, cols = TCS.wet_weight_cells(t, recs)
    assert set(cols.tolist()) == {110, 111} and set(rows.tolist()) == set(range(880, 901))
    monkeypatch.setattr(TCS, "_tile_water", lambda tt: box(0.1016, 0.1, 0.1034, 0.2))
    assert len(TCS.wet_weight_cells(t, recs)[0]) == 0            # inside the held box
