"""#2053 round 3 (spec ``docs/specs/2053-round3-hold-spec.md``): THE HOLD.
The mesh holds a ground object's cut -- the band rule of THE FLOOR, the
1 m bound, the pure hold on a mesh, the weight boxes, the tile glue that
skips a terrain model, and the patch's object ground.  Synthetic only."""
import os
import sys
import types

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

import O4_Mesh_Utils as MESH  # noqa: E402
from auto_patch import terrain_cut_stage as TCS  # noqa: E402
from auto_patch_v2.airport import bridged_ground as BG  # noqa: E402
from auto_patch_v2.airport import object_ground as OG  # noqa: E402
from auto_patch_v2.airport import terrain_cut as TC  # noqa: E402
from auto_patch_v2.airport import terrain_model as TM  # noqa: E402
from auto_patch_v2.geom.terrain_deck import CELL_M, UNDER_M, DeckGrid  # noqa: E402


def _old_cut_top(grid, erode_m):
    """The cut surface before round 3 (floor_m 0), spelled out."""
    from scipy import ndimage
    cov = grid.covered
    k = max(1, int(round(erode_m / CELL_M)))
    disc = np.hypot(*np.mgrid[-k:k + 1, -k:k + 1]) <= k
    eroded = ndimage.minimum_filter(np.where(cov, grid.top, np.inf), footprint=disc,
                                    mode="constant", cval=np.inf)
    rim = cov & ndimage.binary_dilation(~np.pad(cov, 1), np.ones((3, 3), bool))[1:-1, 1:-1]
    edge = ndimage.distance_transform_edt(~rim) * CELL_M
    b = max(1, int(round(TC.BAND_M / CELL_M)))
    band = np.hypot(*np.mgrid[-b:b + 1, -b:b + 1]) <= b
    lowest = ndimage.maximum_filter(np.where(rim, grid.bot, -np.inf), footprint=band,
                                    mode="constant", cval=-np.inf)
    bound = np.where(edge <= TC.BAND_M, np.maximum(eroded, lowest), eroded)
    return np.where(cov, bound, np.nan)


def _dome(n=41):
    h = (n - 1) / 2.0
    i, j = np.mgrid[0:n, 0:n]
    r2 = ((i - h) ** 2 + (j - h) ** 2) / (h * h)
    top = np.where(r2 <= 1.0, 60.0 * (1.0 - r2), np.nan)
    bot = top - np.where(r2 < 0.3, 4.0, 0.0)
    top[8:11, 25:28] = np.nan
    bot[8:11, 25:28] = np.nan
    return DeckGrid(-h * CELL_M, -h * CELL_M, bot, top)


@pytest.mark.parametrize("erode_m", [TC.ERODE_M, BG.ERODE_M])
def test_the_bound_at_the_plan_cell_is_the_old_cut_for_a_terrain_model(erode_m):
    g = _dome()
    np.testing.assert_array_equal(TC._cut_grid(g, erode_m).top, _old_cut_top(g, erode_m))


def test_a_band_cell_beside_a_high_rim_bottom_keeps_its_own_top():
    """THE FLOOR's band (C1): an arm's rim underside standing high over
    low open ground is not the ground's bound there."""
    bot = np.full((30, 30), 2.0)
    top = bot.copy()
    bot[0:2, :] = 8.0                      # the arm along the edge, its
    top[0:2, :] = 9.0                      # underside 8 m over the zero
    g = DeckGrid(0.0, 0.0, bot, top)
    old = TC._cut_grid(g, BG.ERODE_M).top
    new = TC._cut_grid(g, BG.ERODE_M, floor_m=3.0).top
    assert old[2, 15] == 8.0               # the old band: the rim's lowest
    assert new[2, 15] == 2.0               # its own top, eroded


def test_the_hold_bound_is_binned_at_one_metre():
    sq = np.array([[0, 0, 0], [20, 0, 0], [20, 0, 20], [0, 0, 20]], float)
    p = np.stack([sq[[0, 1, 2]], sq[[0, 2, 3]]])
    p[:, :, 1] = 3.0
    x0, z0, b = TC.hold_bound(p, BG.ERODE_M, 3.0)
    assert (x0, z0) == (0.0, 0.0) and b.shape == (21, 21)
    np.testing.assert_allclose(b[np.isfinite(b)], 3.0)


# -- THE HOLD on a mesh -----------------------------------------------------

def _mesh(n=6, step=10.0):
    from scipy.spatial import Delaunay
    i, j = np.mgrid[0:n, 0:n]
    xy = np.c_[i.ravel(), j.ravel()].astype(float) * step
    return xy, Delaunay(xy).simplices


def _samples(lo, hi, f):
    i, j = np.mgrid[lo:hi + 1, lo:hi + 1]
    s = np.c_[i.ravel(), j.ravel()].astype(float)
    return s, f(s)


def _drawn(xy, z, tris, s):
    """The drawn surface at the samples (any triangle holding each)."""
    pairs = TC._hold_pairs(xy, tris, s)
    out = np.full(len(s), -np.inf)
    np.maximum.at(out, pairs[0], (pairs[2] * z[tris[pairs[1]]]).sum(1))
    return out


def test_a_linear_ramp_is_left_as_it_is():
    xy, tris = _mesh()
    z = 0.1 * xy[:, 0] + 2.0
    s, b = _samples(0, 50, lambda s: 0.1 * s[:, 0] + 2.0)
    z2, unresolved = TC.hold_heights(xy, z, tris, np.ones(len(z), bool), s, b)
    np.testing.assert_allclose(z2, z)
    assert unresolved == 0


def test_a_two_level_step_is_held_and_never_dug_under_its_lower_level():
    xy, tris = _mesh()
    z = np.full(len(xy), 5.0)
    s, b = _samples(0, 50, lambda s: np.where(s[:, 0] < 23.0, 3.0, 1.0))
    z2, unresolved = TC.hold_heights(xy, z, tris, np.ones(len(z), bool), s, b)
    assert unresolved == 0
    assert np.all(_drawn(xy, z2, tris, s) <= b + 1e-3)
    assert z2.min() >= 1.0 - 1e-9
    assert np.all(z2 <= z)                 # only lowers


def test_a_fixed_high_corner_is_unresolved_and_its_neighbours_stop_at_the_bound():
    xy, tris = _mesh()
    z = np.full(len(xy), 5.0)
    mid = int(np.flatnonzero((xy[:, 0] == 20.0) & (xy[:, 1] == 20.0))[0])
    z[mid] = 10.0
    free = np.ones(len(z), bool)
    free[mid] = False
    s, b = _samples(0, 50, lambda s: np.zeros(len(s)))
    z2, unresolved = TC.hold_heights(xy, z, tris, free, s, b)
    assert unresolved > 0
    assert z2[mid] == 10.0
    assert z2[free].min() >= 0.0 - 1e-9
    assert np.all(z2 <= z)


def test_a_shore_vertex_is_never_lowered_under_the_water_beside_it():
    """#2053 (owner 2026-11-13): the hold never lowers a land vertex under
    the water datum of a water vertex it shares a triangle with; the
    samples that clamp leaves over the bound are unresolved."""
    xy, tris = _mesh()
    z = np.full(len(xy), 0.5)
    water = np.flatnonzero(xy[:, 0] == 0.0)            # the shore column
    z[water] = 0.0
    free = np.ones(len(z), bool)
    free[water] = False
    verts = np.zeros(6 * len(z))
    verts[2::6] = z
    floor = TCS.water_floor(verts, tris, water)
    s, b = _samples(0, 50, lambda s: np.full(len(s), -1.9))
    z2, unresolved = TC.hold_heights(xy, z, tris, free, s, b, floor)
    shore = np.isfinite(floor) & free
    inland = ~np.isfinite(floor)
    assert shore.any() and inland.any()
    np.testing.assert_allclose(z2[shore], 0.0)         # stays at the water
    assert np.all(z2[inland] < 0.0)                    # inland still lowers
    assert z2[inland].min() >= -1.9 - 1e-9
    assert unresolved > 0
    assert TCS.water_floor(verts, tris, ()) is None


# -- the weight boxes (C3) --------------------------------------------------

def test_the_box_weight_raises_the_inset_cells():
    tile = types.SimpleNamespace(lat=39, lon=-107)
    box = (-106.6, 39.2, -106.55, 39.27)
    w1 = np.ones((1001, 1001), np.float32)
    w2 = np.ones((1001, 1001), np.float32)
    n1 = MESH.apply_inset_box_curv_weights(tile, w1, [(box, 3.0)])
    n2 = MESH._raise_box_curv_weight(tile, w2, box, MESH.inset_box_curv_weight(3.0))
    assert n1 == n2 > 0
    np.testing.assert_array_equal(w1, w2)
    w3 = np.ones((1001, 1001), np.float32)
    w3[round((39 + 1 - 39.27) * 1000):round((39 + 1 - 39.2) * 1000) + 1,
       round((-106.6 + 107) * 1000):round((-106.55 + 107) * 1000) + 1] = 10.0
    np.testing.assert_array_equal(w1, w3)


def test_the_hold_weight_reads_the_raster_posting():
    dem = types.SimpleNamespace(x0=0.0, x1=1.0, y0=0.0, y1=1.0, nxdem=10801, nydem=10801)
    tile = types.SimpleNamespace(lat=-23, lon=-44, curvature_tol=2.0, dem=dem)
    w = MESH.hold_curv_weight(tile)
    assert 39.0 < w < 42.0


# -- the tile glue (C2) -----------------------------------------------------

def _flat_square(size=40.0, y=0.0):
    sq = np.array([[0, y, 0], [size, y, 0], [size, y, size], [0, y, size]], float)
    sq[:, 0] -= size / 2
    sq[:, 2] -= size / 2
    return np.stack([sq[[0, 1, 2]], sq[[0, 2, 3]]])


def _rec(erode=True):
    cut = {"file": "x.obj", "lat": -22.5, "lon": -43.5, "heading": 0.0}
    if erode:
        cut.update(erode_m=BG.ERODE_M, floor_m=3.0)
    return {"id": "dsf:obj9", "resource": "x.obj", "elevation": 0.0, "icao": "TEST",
            "cut": cut}


def _tile_mesh(z=5.0, step=10.0, n=12):
    """A tile-relative mesh round the record's anchor, flat at ``z``."""
    from scipy.spatial import Delaunay
    tile = types.SimpleNamespace(lat=-23, lon=-44)
    to_xy, to_ll = TC.projector(-22.5, -43.5)
    i, j = np.mgrid[0:n, 0:n]
    e = (i.ravel() - (n - 1) / 2.0) * step
    nn = (j.ravel() - (n - 1) / 2.0) * step
    lon, lat = to_ll(e, nn)
    v = np.zeros((len(e), 6))
    v[:, 0], v[:, 1], v[:, 2], v[:, 5] = lon - tile.lon, lat - tile.lat, z, z
    return tile, v.ravel(), Delaunay(np.c_[e, nn]).simplices


@pytest.fixture
def square(monkeypatch):
    p = _flat_square()
    monkeypatch.setattr(TM, "plan_solid", lambda path: p)
    monkeypatch.setattr(TM, "plan_grid", lambda path: DeckGrid(*__import__(
        "auto_patch_v2.airport.terrain_shaped", fromlist=["x"]).bin_triangles(p)))
    return p


def test_the_hold_lowers_the_free_vertices_under_the_object(square, monkeypatch):
    monkeypatch.setattr(TCS, "cut_records", lambda d, icaos=None: [_rec()])
    monkeypatch.setattr(TCS, "_held_records", lambda tile: TCS._held([_rec()]))
    tile, v, tris = _tile_mesh()
    before = v.copy()
    got = TCS.hold(tile, v, tris, set())
    r = got["dsf:obj9"]
    assert r["lowered"] > 0 and r["unresolved"] == 0
    assert abs(r["worst_m"] - (5.0 + UNDER_M)) < 1e-6
    assert np.all(v[2::6] <= before[2::6])
    moved = v[2::6] < before[2::6]
    assert np.all(v[3::6][moved] == 0) and np.all(v[4::6][moved] == 0)


def test_the_hold_never_moves_a_fixed_vertex(square, monkeypatch):
    monkeypatch.setattr(TCS, "_held_records", lambda tile: TCS._held([_rec()]))
    tile, v, tris = _tile_mesh()
    fixed = set(range(0, len(v) // 6, 2))
    before = v.copy()
    TCS.hold(tile, v, tris, fixed)
    for k in fixed:
        assert v[6 * k + 2] == before[6 * k + 2]


def test_the_hold_skips_a_terrain_model(square, monkeypatch):
    monkeypatch.setattr(TCS, "cut_records", lambda d, icaos=None: [_rec(erode=False)])
    import O4_File_Names as FNAMES
    monkeypatch.setattr(FNAMES, "patch_dir", lambda lat, lon: "/nonexistent")
    tile, v, tris = _tile_mesh()
    before = v.copy()
    assert TCS.hold(tile, v, tris, set()) == {}
    assert TCS.held_boxes(tile) == []
    np.testing.assert_array_equal(v, before)


def test_the_hold_never_raises(monkeypatch):
    def boom(tile):
        raise RuntimeError("unreadable")
    monkeypatch.setattr(TCS, "_held_records", boom)
    tile, v, tris = _tile_mesh()
    assert TCS.hold(tile, v, tris, set()) == {}


# -- the patch's object ground (C4) -----------------------------------------

def _model(seat_by=BG.SEAT_BY):
    return TM.TerrainModel("dsf:obj9", "x.obj", (100.0, 50.0), 0.0, 0.0, 0.0, 0.0, 0.0,
                           0.0, 0.0, file="x.obj", seat_by=seat_by, erode_m=BG.ERODE_M,
                           cut_floor_m=3.0)


def test_the_object_ground_lowers_groundside_vertices_only(square):
    m = _model()
    airport = types.SimpleNamespace(terrain_models=(("dsf:obj9", "x.obj", m, 0.0),))
    xs = np.array([100.0, 105.0, 95.0, 300.0, 100.0])
    ys = np.array([50.0, 55.0, 45.0, 50.0, 52.0])
    zs = np.array([5.0, 5.0, -3.0, 5.0, 5.0])
    out, rep = OG.object_ground(airport, xs, ys, zs, airside={1})
    assert out[0] == pytest.approx(-UNDER_M)      # cut
    assert out[1] == 5.0                          # airside: kept
    assert out[2] == -3.0                         # under the cut: never raised
    assert out[3] == 5.0                          # off the plan
    assert rep.vertices_lowered == 2 and rep.airside_inside == 1
    assert "object ground" in rep.line()


def test_the_object_ground_reads_no_terrain_model(square):
    m = _model(seat_by="")
    airport = types.SimpleNamespace(terrain_models=(("dsf:obj9", "x.obj", m, 0.0),))
    zs = np.array([5.0])
    out, rep = OG.object_ground(airport, np.array([100.0]), np.array([50.0]), zs, set())
    assert out[0] == 5.0 and rep.models == []


def test_the_road_profile_sampler_reads_the_cut_ground_under_a_held_object(square):
    """The census row "a patch row reading airport.dem directly" (SBRJ's
    south-west road joined a core ribbon at the uncut DEM)."""
    m = _model()
    airport = types.SimpleNamespace(terrain_models=(("dsf:obj9", "x.obj", m, 0.0),))

    def flat(xs, ys):
        return np.full(len(np.atleast_1d(xs)), 5.0)
    s = OG.object_sampler(flat, airport)
    z = s(np.array([100.0, 300.0]), np.array([50.0, 50.0]))
    assert z[0] == pytest.approx(-UNDER_M) and z[1] == 5.0
    assert s.lowered == 1
    none = types.SimpleNamespace(terrain_models=(("dsf:obj9", "x.obj", _model(""), 0.0),))
    assert OG.object_sampler(flat, none) is flat
