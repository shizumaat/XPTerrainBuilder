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

from auto_patch import terrain_cut_stage as TCS  # noqa: E402
from auto_patch_v2.airport import pack_choice as PC  # noqa: E402
from auto_patch_v2.airport import terrain_cut as TC  # noqa: E402
from auto_patch_v2.airport import terrain_model as TM  # noqa: E402
from auto_patch_v2.geom.terrain_deck import (  # noqa: E402
    CELL_M,
    UNDER_M,
    DeckGrid,
    TerrainFit,
    target_at,
)


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
    c = TC._cut_grid(g)
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
    # the cut reads the file's plan grid (a ground object on its bridges,
    # #2053, is no terrain-model candidate and is cut too)
    monkeypatch.setattr(TM, "plan_grid", lambda p: g)
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
    path.write_text(json.dumps(plan), encoding="utf-8", newline="")
    assert [r["id"] for r in TCS.cut_records(str(tmp_path), ["TEST"])] == ["dsf:obj7"]
    assert TCS.cut_records(str(tmp_path), ["OTHER"]) == []
    PC.Store(PC.TERRAIN_CHOICES).remember(root, "update")
    assert TCS.cut_records(str(tmp_path), ["TEST"]) == []
    # the answer reaches only the models offered for hiding
    plan["authored_seats"][0]["hideable"] = False
    path.write_text(json.dumps(plan), encoding="utf-8", newline="")
    assert [r["id"] for r in TCS.cut_records(str(tmp_path), ["TEST"])] == ["dsf:obj7"]


def test_the_plan_edge_is_a_closed_ring_per_boundary():
    fit = TC.cut_fit(_skin(), 0.0, 0.0)
    rings = TC.outline_rings(fit, TC.projector(-22.5, -43.5)[1])
    assert len(rings) == 2                            # the rim and the hole
    for r in rings:
        assert np.allclose(r[0], r[-1])


def _climbing_hill(nx=60, nz=30, climb=0.35):
    """A skin hill (top == bot) whose rim climbs ``climb`` along x."""
    i, j = np.mgrid[0:nx, 0:nz]
    x = (i + 0.5) * CELL_M
    u, v = (i - (nx - 1) / 2) / (nx / 2), (j - (nz - 1) / 2) / (nz / 2)
    top = climb * x + 25.0 * np.clip(1.0 - u * u - v * v, 0.0, None)
    return DeckGrid(0.0, -nz * CELL_M / 2, top.copy(), top)


def test_t1_a_fill_record_holds_its_rim_level_a_triangle_and_a_diagonal_inside():
    """#2077 round 2 R1 (twin T1): on a 6.9 x 10.3 m raster a fill
    record's cut, within ``W + s`` of the rim, never stands more than
    0.5 m under its nearest rim cell's bottom unless the top within ``d``
    is lower, never over that top; without ``fill`` the bound is today's."""
    from auto_patch_v2.airport import terrain_fill as TF
    from scipy import ndimage
    g = _climbing_hill()
    lat = 47.8
    r = TF.Raster(np.zeros((3, 3)), 13.0, lat, 6.9 / (111_320.0 * np.cos(np.radians(lat))),
                  10.3 / 111_320.0)
    band, diag = TCS._fill_band(r)
    assert band == pytest.approx(TF._shoulder_m(6.9, 10.3) + 10.3, abs=0.02)
    assert diag == pytest.approx(np.hypot(6.9, 10.3), abs=0.02)
    cov = g.covered
    rim = cov & ndimage.binary_dilation(~np.pad(cov, 1), np.ones((3, 3), bool))[1:-1, 1:-1]
    edge, (ni, nj) = ndimage.distance_transform_edt(~rim, return_indices=True)
    edge = edge * CELL_M
    reach = cov & (edge > TC.BAND_M) & (edge <= band)
    k = int(round(diag / CELL_M))
    near_top = ndimage.minimum_filter(np.where(cov, g.top, np.inf),
                                      footprint=np.hypot(*np.mgrid[-k:k + 1, -k:k + 1]) <= k,
                                      mode="constant", cval=np.inf)
    want = np.minimum(g.bot[ni, nj], near_top)
    old = TC._bound(g.bot, g.top, CELL_M, TC.ERODE_M, 0.0)
    new = TC._bound(g.bot, g.top, CELL_M, TC.ERODE_M, 0.0, band, diag)
    assert np.any(want[reach] - old[reach] > 0.5)            # today's step behind the rim
    assert np.all(new[reach] >= want[reach] - 0.5)
    assert np.all(new[reach] <= near_top[reach] + 1e-9)
    assert np.array_equal(new[~reach & cov], old[~reach & cov])
    # the stage: a fill record reaches the band, any other record is today's
    TM_plan = TM.plan_grid
    try:
        TM.plan_grid = lambda p: g
        rec = {"elevation": 0.0, "cut": {"file": "h.obj", "heading": 0.0}}
        plain = TCS._fit(rec, (band, diag)).grid.top
        assert np.array_equal(plain[cov], TCS._fit(rec).grid.top[cov])
        assert np.array_equal(plain[cov], old[cov])
        filled = TCS._fit(dict(rec, cut=dict(rec["cut"], fill=True)), (band, diag)).grid.top
        assert np.array_equal(filled[cov], new[cov])
    finally:
        TM.plan_grid = TM_plan


# -- THE SHELL (#2272 round 2): the body is cut, the edge band is not ---------

def _skirted(n=41, peak=40.0, skirt=10.0):
    """A small shell (top == bot): a dome over a SKIRT -- its outer 5 m
    rises ``skirt`` metres from the rim (0 m) inward."""
    h = (n - 1) / 2.0
    i, j = np.mgrid[0:n, 0:n]
    r = np.hypot(i - h, j - h) * CELL_M
    big = h * CELL_M
    top = np.where(r <= big, peak * (1.0 - (r / big) ** 2)
                   + skirt * np.clip((big - r) / 5.0, 0.0, 1.0), np.nan)
    return DeckGrid(-h * CELL_M, -h * CELL_M, top.copy(), top)


def _shell_rec(lat, lon, elevation=0.0):
    return {"id": "dsf:obj3", "resource": "s.obj", "seat": TM.SEAT, "elevation": elevation,
            "cut": {"file": "s.obj", "lat": lat, "lon": lon, "heading": 0.0, "shell": True}}


def _fine_tile(ground, n=801, half=0.003):
    """A raster window of ``n`` x ``n`` postings (about 0.8 m) round the
    tile's middle, where the records sit."""
    dem = types.SimpleNamespace(x0=0.5 - half, x1=0.5 + half, y0=0.5 - half, y1=0.5 + half,
                                alt_dem=np.full((n, n), ground, np.float32))
    return types.SimpleNamespace(lat=-23, lon=-44, dem=dem)


def _cut_postings(tile, g, rec):
    """``(changed, band, body)`` postings of a bake: band / body by the
    plan cell each posting falls in."""
    before = tile.dem.alt_dem.copy()
    TCS.bake(tile, [rec])
    a, d = tile.dem.alt_dem, tile.dem
    n = a.shape[0]
    r, c = np.mgrid[0:n, 0:n]
    lons = -44 + d.x0 + c.ravel() * (d.x1 - d.x0) / (n - 1)
    lats = -23 + d.y1 - r.ravel() * (d.y1 - d.y0) / (n - 1)
    fit = TCS._fit(rec)
    lx, lz = fit.local(*TC.projector(rec["cut"]["lat"], rec["cut"]["lon"])[0](lons, lats))
    i, j, inside = g.cell_of(lx, lz)
    body = np.zeros(len(lons), bool)
    body[inside] = TC.body_mask(g.covered)[i[inside], j[inside]]
    changed = (a != before).ravel()
    return changed, inside & ~body, body, a.ravel(), before.ravel(), fit, i, j


def test_a_skirted_shell_keeps_its_band_uncut_and_its_body_under_the_top(monkeypatch):
    """S2/S3: under a 100 m ground a skirted dome's body is cut under its
    top (eroded over the body alone: never down to the skirt's foot) and
    its edge band -- the skirt -- is never cut, so the ground at its rim
    stays where it was."""
    g = _skirted()
    monkeypatch.setattr(TM, "plan_grid", lambda p: g)
    tile = _fine_tile(100.0)
    changed, band, body, a, before, fit, i, j = _cut_postings(
        tile, g, _shell_rec(-22.5, -43.5))
    assert band.any() and body.any()
    assert not changed[band].any()                                   # S3
    assert changed[body].all()
    assert np.all(a[body] <= fit.grid.top[i[body], j[body]] - UNDER_M + 1e-3)
    assert np.all(a[body] <= g.top[i[body], j[body]] - UNDER_M + 1e-3)
    # the body's erosion never reads the skirt: its bound stays over the
    # skirt's foot (0 m) by the body's own lowest top within ERODE_M
    assert np.all(a[body] > 5.0)


def test_a_flat_shell_is_cut_only_beyond_its_band(monkeypatch):
    """A flat margin (a shell 5 m high everywhere, 20 m ground): the band
    keeps the ground, the body is cut to the top less UNDER_M."""
    g = _skin()
    flat = DeckGrid(g.x0, g.z0, np.where(g.covered, 5.0, np.nan), np.where(g.covered, 5.0, np.nan))
    monkeypatch.setattr(TM, "plan_grid", lambda p: flat)
    tile = _fine_tile(20.0)
    changed, band, body, a, before, *_ = _cut_postings(tile, flat, _shell_rec(-22.5, -43.5))
    assert np.all(a[band] == 20.0)
    assert np.allclose(a[body], 5.0 - UNDER_M, atol=1e-3)


def test_skirt_off_is_todays_bound():
    """``skirt=False`` (every record but a shell's) is byte-identical to
    the bound before round 2: the terrain model's and the ground object's."""
    g = _skin()
    for erode_m, floor_m in ((TC.ERODE_M, 0.0), (5.0, 3.0)):
        np.testing.assert_array_equal(
            TC._bound(g.bot, g.top, CELL_M, erode_m, floor_m, skirt=False),
            TC._bound(g.bot, g.top, CELL_M, erode_m, floor_m))
    band = TC._bound(g.bot, g.top, CELL_M, TC.ERODE_M, 0.0, 28.0, 14.0, skirt=True)
    assert np.all(np.isinf(band[g.covered & ~TC.body_mask(g.covered)]))
