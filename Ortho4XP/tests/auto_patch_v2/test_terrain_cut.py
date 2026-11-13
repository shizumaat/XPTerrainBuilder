"""Owner RULINGS 2026-11-13k (#2036 (c), #2040): "Yes to cutting terrain
under a terrain object if it's not being hidden".  The tile raster under a
terrain model's plan is cut to its surface (never raised), its edge band
never under the object's lowest surface, nothing outside the plan or at
the tile's edge changes, and a model the user hides is not cut.
Synthetic grids and rasters, no corpus."""
import json
import os
import sys
import types

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

from auto_patch import pack_choice as PC  # noqa: E402
from auto_patch import terrain_cut_stage as TCS  # noqa: E402
from auto_patch_v2.airport import terrain_cut as TC  # noqa: E402
from auto_patch_v2.airport import terrain_model as TM  # noqa: E402
from auto_patch_v2.geom.terrain_deck import CELL_M, UNDER_M, DeckGrid, TerrainFit, target_at  # noqa: E402


def _skin(n=81, peak=120.0):
    """A dome SKIN (top == bot) over an ``n`` x ``n`` cell plan centred
    on the anchor, its rim at y = 0, a 3 x 3 cell hole off centre."""
    h = (n - 1) / 2.0
    i, j = np.mgrid[0:n, 0:n]
    r2 = ((i - h) ** 2 + (j - h) ** 2) / (h * h)
    top = np.where(r2 <= 1.0, peak * (1.0 - r2), np.nan)
    top[20:23, 50:53] = np.nan
    return DeckGrid(-h * CELL_M, -h * CELL_M, top.copy(), top)


def test_the_cut_never_fills():
    """``fill`` off: ground under the deck's underside stays where it is."""
    g = DeckGrid(0.0, 0.0, np.full((3, 3), 5.0), np.full((3, 3), 10.0))
    fill = TerrainFit("d", "", (0.0, 0.0), 0.0, 0.0, 1.0, 0.0, 0.0, g)
    cut = TerrainFit("d", "", (0.0, 0.0), 0.0, 0.0, 1.0, 0.0, 0.0, g, fill=False)
    x, y, dem = np.array([5.0, 5.0]), np.array([-5.0, -5.0]), np.array([0.0, 50.0])
    assert target_at(fill, x, y, dem)[0].tolist() == [5.0 - UNDER_M, 10.0 - UNDER_M]
    assert target_at(cut, x, y, dem)[0].tolist() == [0.0, 10.0 - UNDER_M]


def test_the_cut_surface_stays_under_the_top_and_meets_the_edge():
    g = _skin()
    c = TC.cut_grid(g)
    cov = g.covered
    assert np.array_equal(np.isfinite(c.top), cov)
    from scipy import ndimage
    rim = cov & ndimage.binary_dilation(~np.pad(cov, 1), np.ones((3, 3), bool))[1:-1, 1:-1]
    edge = ndimage.distance_transform_edt(~rim) * CELL_M
    inner = cov & (edge > TC.BAND_M)
    # inside, the bound is the lowest top within ERODE_M: never over the top
    assert np.all(c.top[inner] <= g.top[inner] + 1e-9)
    high = inner & (g.top > 60.0)
    assert np.all(c.top[high] < g.top[high])
    # the edge band never sinks under the object's lowest surface there
    assert np.all(c.top[rim] >= g.bot[rim] - 1e-9)


def _tile(n=2001, ground=200.0):
    dem = types.SimpleNamespace(x0=0.0, x1=1.0, y0=0.0, y1=1.0,
                                alt_dem=np.full((n, n), ground, np.float32))
    return types.SimpleNamespace(lat=-23, lon=-44, dem=dem)


def _rec(lat, lon, hideable=False):
    return {"id": "dsf:obj7", "resource": "m.obj", "seat": TM.SEAT, "elevation": 10.0,
            "hideable": hideable, "cut": {"file": "m.obj", "lat": lat, "lon": lon,
                                          "heading": 30.0}}


@pytest.fixture
def shaped(monkeypatch):
    g = _skin()
    monkeypatch.setattr(TM, "shape_of", lambda p, geometry=None: types.SimpleNamespace(grid=g))
    return g


def test_the_raster_is_cut_inside_the_plan_only(shaped):
    tile = _tile()
    before = tile.dem.alt_dem.copy()
    k = TCS.bake(tile, [_rec(-22.5, -43.5)])
    a = tile.dem.alt_dem
    changed = a != before
    assert k == int(changed.sum()) > 0
    assert np.all(a <= before)                       # only ever lowered
    # every changed posting lies in the plan, at the cut surface
    fit = TC.cut_fit(shaped, 10.0, 30.0)
    to_xy, _ll = TC.projector(-22.5, -43.5)
    r, c = np.nonzero(changed)
    n = a.shape[0]
    lons, lats = -44 + c / (n - 1), -23 + 1 - r / (n - 1)
    lx, lz = fit.local(*to_xy(lons, lats))
    i, j, inside = shaped.cell_of(lx, lz)
    assert inside.all()
    assert np.all(a[r, c] <= 10.0 + fit.grid.top[i, j] - UNDER_M + 1e-3)
    assert np.all(a[r, c] < 200.0 - 1.0)
    # the dome's foot (y = 0 at the rim, zero 10 m) is under the 200 m
    # ground: the edge band is cut to the object's lowest surface, no lower
    assert np.all(a[r, c] >= 10.0 - UNDER_M - 1e-3)


def test_the_tile_edge_is_never_cut(shaped):
    tile = _tile()
    before = tile.dem.alt_dem.copy()
    TCS.bake(tile, [_rec(-22.0005, -43.5)])      # the plan crosses the north edge
    a = tile.dem.alt_dem
    assert (a != before).any()
    assert np.array_equal(a[:3], before[:3])


def test_a_hidden_model_is_not_cut(tmp_path, monkeypatch, shaped):
    monkeypatch.setattr(PC, "store_path", lambda name: str(tmp_path / name))
    root = str(tmp_path / "pack")
    plan = {"icao": "TEST", "pack_root": root,
            "authored_seats": [_rec(-22.5, -43.5, hideable=True),
                               dict(_rec(-22.5, -43.5), id="dsf:obj8", cut=None)]}
    path = tmp_path / "o4_v2_rebake_TEST.json"
    path.write_text(json.dumps(plan), encoding="utf-8")
    assert [r["id"] for r in TCS.cut_records(str(tmp_path), ["TEST"])] == ["dsf:obj7"]
    assert TCS.cut_records(str(tmp_path), ["OTHER"]) == []
    PC.Store(PC.TERRAIN_CHOICES).remember(root, "update")
    assert TCS.cut_records(str(tmp_path), ["TEST"]) == []
    # the answer reaches only the models offered for hiding
    plan["authored_seats"][0]["hideable"] = False
    path.write_text(json.dumps(plan), encoding="utf-8")
    assert [r["id"] for r in TCS.cut_records(str(tmp_path), ["TEST"])] == ["dsf:obj7"]


def test_the_plan_edge_is_a_closed_ring_per_boundary():
    fit = TC.cut_fit(_skin(), 0.0, 0.0)
    rings = TC.outline_rings(fit, TC.projector(-22.5, -43.5)[1])
    assert len(rings) == 2                            # the rim and the hole
    for r in rings:
        assert np.allclose(r[0], r[-1])
