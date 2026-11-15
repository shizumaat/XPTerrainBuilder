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
