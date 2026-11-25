"""#2197: a pack origin set whose outer rim is its author's ground (a PARTIAL
SHELL) is recognised by its ground sheet, and our raster is graded to its
rim stations, raised or lowered, never at a frozen posting.  Synthetic
plans and rasters, no corpus."""
import json
import os
import sys
import types

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))

from auto_patch import terrain_cut_stage as TCS  # noqa: E402
from auto_patch_v2.airport import ground_rim as GR  # noqa: E402
from auto_patch_v2.airport import rim_grade as RG  # noqa: E402
from auto_patch_v2.airport import terrain_fill as TF  # noqa: E402
from auto_patch_v2.airport import terrain_model as TM  # noqa: E402
from auto_patch_v2.geom import shape_class as SC  # noqa: E402
from auto_patch_v2.geom.terrain_deck import UNDER_M  # noqa: E402


def _quad(x0, z0, x1, z1, y):
    """Two upward triangles of a level rectangle, OBJ8 axes (x east, y up,
    z south)."""
    a, b, c, d = (x0, y, z0), (x1, y, z0), (x1, y, z1), (x0, y, z1)
    return np.array([[a, b, c], [a, c, d]], float)


def _box(x0, z0, x1, z1, h):
    """A building: its roof at ``h`` and four walls down to 0."""
    tris = [_quad(x0, z0, x1, z1, h)]
    for (xa, za), (xb, zb) in (((x0, z0), (x1, z0)), ((x1, z0), (x1, z1)),
                               ((x1, z1), (x0, z1)), ((x0, z1), (x0, z0))):
        tris.append(np.array([[(xa, 0, za), (xb, 0, zb), (xb, h, zb)],
                              [(xa, 0, za), (xb, h, zb), (xa, h, za)]], float))
    return np.concatenate(tris)


#: THE MODELLED GROUND of the fixtures: a valley, 8 m deep over 60 m (a
#: plane cannot fit it: its relief is the module's MIN_RELIEF_M and more)
def _v(x):
    return 8.0 * np.abs(np.asarray(x, float)) / 60.0


def _ground(x, y):
    """Our ground, the author's valley (frame metres; north is -z)."""
    return _v(x)


def _plaza(x0, z0, x1, z1, k=12):
    """The valley as a ground sheet: strips of two triangles each."""
    xs = np.linspace(x0, x1, k + 1)
    tris = []
    for a, b in zip(xs[:-1], xs[1:], strict=True):
        p, q, r, s = (a, _v(a), z0), (b, _v(b), z0), (b, _v(b), z1), (a, _v(a), z1)
        tris += [[p, q, r], [p, r, s]]
    return np.array(tris, float)


def test_the_vectorised_plan_matches_the_reference_rasteriser():
    p = np.concatenate([_quad(-40, -30, 40, 30, 0.0), _box(-10, -10, 10, 10, 6.0)])
    pl = np.stack([p[:, :, 0], -p[:, :, 2], p[:, :, 1]], -1)
    fast = GR._raster_of(pl, step=1.0)
    ref = SC.rasterise(pl, max_cells=10 ** 6, min_step=1.0)
    assert fast.top.shape == ref.top.shape
    both = np.isfinite(fast.top) & np.isfinite(ref.top)
    assert both.sum() > 0.95 * np.isfinite(ref.top).sum()
    assert np.allclose(fast.top[both], ref.top[both])
    assert np.allclose(fast.low[both], ref.low[both])


def test_the_sheet_reaches_the_ground_never_a_roof_nor_a_deck_up_a_ramp():
    top = np.zeros((40, 80))
    top[10:20, 10:20] = 4.0                     # a roof behind a wall
    top[25:30, 30:70] = np.linspace(0.0, 12.0, 40)[None, :]   # a ramp to a deck
    sheet = GR._ground_sheet(top, np.zeros_like(top))
    assert sheet[0, 0] and sheet[35, 5]
    assert not sheet[10:20, 10:20].any()        # cut off by its wall
    ramp = top[25:30, 30:70]
    assert sheet[25:30, 30:70][ramp <= 5.0].all()
    assert not sheet[25:30, 30:70][ramp > 5.0].any()


def test_a_ground_plaza_is_a_partial_shell_and_a_building_is_not():
    box = _box(-15, -10, 15, 10, 8.0)
    box[:, :, 1] += 2.0 * (box[:, :, 1] > 0)          # its roof 10 m up
    plaza = np.concatenate([_plaza(-60, -40, 60, 40), box])
    r = GR._set_raster([plaza], 0.0)
    got = GR._recognise(r, (0.0, 0.0), 0.0, _ground)
    assert got is not None
    assert got.rim_share == 1.0 and got.sheet_share > 0.85
    assert got.relief_m >= GR.MIN_RELIEF_M
    assert abs(got.z0) < 1e-6
    assert np.allclose(got.stations[:, 2], _v(got.stations[:, 0]), atol=0.2)
    assert GR._recognise(GR._set_raster([_box(-40, -30, 40, 30, 8.0)], 0.0),
                        (0.0, 0.0), 0.0, _ground) is None


def test_an_apron_plate_on_a_grade_is_no_partial_shell():
    plate = _quad(-60, -40, 60, 40, 0.0)
    plate[:, :, 1] = 0.05 * plate[:, :, 0]             # a 5 % grade, no relief
    got = GR._recognise(GR._set_raster([plate], 0.0), (0.0, 0.0), 0.0,
                       lambda x, y: 0.05 * np.asarray(x, float))
    assert got is None


def test_the_seat_is_the_rigid_fit_of_the_authors_ground_to_ours():
    plaza = _plaza(-60, -40, 60, 40)
    got = GR._recognise(GR._set_raster([plaza], 0.0), (0.0, 0.0), 0.0,
                       lambda x, y: _v(x) + 101.2)
    assert abs(got.z0 - 101.2) < 1e-6


def test_placement_sets_reads_the_origin_set_not_one_file():
    rows = [("a", "lot_a.obj", (0.0, 0.0), 0.0, None, "OBJECT"),
            ("b", "lot_b.obj", (0.0, 0.0), 0.0, None, "OBJECT"),
            ("c", "lib/cars/car.obj", (0.0, 0.0), 0.0, None, "OBJECT")]
    solids = {"lot_a.obj": _plaza(-60, -40, 0, 40, 6), "lot_b.obj": _plaza(0, -40, 60, 40, 6)}
    got = GR.placement_models(rows, solids.get, _ground)
    assert list(got) == ["a"] and got["a"].rim is not None
    # every row of the origin rides the one frame (a library car too)
    assert TM.set_members(rows, got) == {k: got["a"] for k in "abc"}
    # an OBJECT_MSL set is the author's own height: never this module's
    msl = [r[:5] + ("OBJECT_MSL",) for r in rows]
    assert GR.placement_models(msl, solids.get, _ground) == {}


def _raster(n=401, ground=0.0, frozen=None):
    """A 1 m raster, 400 m square, about (0, 0) deg-free metres."""
    a = np.full((n, n), ground, float)
    k = 1.0 / TF._M_PER_DEG
    return TF.Raster(a, -200 * k, 200 * k, k, k, frozen)


def _proj():
    k = TF._M_PER_DEG
    return (lambda lo, la: (np.asarray(lo) * k, np.asarray(la) * k),
            lambda x, y: (np.asarray(x) / k, np.asarray(y) / k))


def _ring_stations(z, half=50.0):
    s = np.arange(-half, half + 1e-9, 1.0)
    pts = np.concatenate([np.c_[s, -half + 0 * s], np.c_[s, half + 0 * s],
                          np.c_[-half + 0 * s, s], np.c_[half + 0 * s, s]])
    ring = np.array([[-half, -half], [half, -half], [half, half], [-half, half], [-half, -half]])
    return np.c_[pts, np.full(len(pts), z)], [ring]


def test_the_grade_raises_and_lowers_to_the_rim_and_feathers_out():
    to_xy, to_ll = _proj()
    for z in (2.0, -2.0):
        r = _raster()
        st, rings = _ring_stations(z)
        rep = RG.rim_grade(r, to_xy, to_ll, st, rings)
        assert rep["unserved"] == 0
        assert (rep["raised"] > 0) == (z > 0) and (rep["lowered"] > 0) == (z < 0)
        at_rim = r.sample(*to_ll(np.array([0.0]), np.array([-50.0 - 0.5])))[0]
        assert abs(at_rim - (z - UNDER_M)) < 0.05
        far = r.sample(*to_ll(np.array([0.0]), np.array([-50.0 - TF.REACH_M - 2])))[0]
        assert far == 0.0
        line = r.sample(*to_ll(np.zeros(60), -50.0 - np.arange(60.0)))
        assert np.all(np.diff(np.abs(line)) <= 1e-9)          # a monotone feather
        # deep inside the plan the object covers the ground: untouched
        assert r.sample(*to_ll(np.array([0.0]), np.array([0.0])))[0] == 0.0


def test_the_grade_never_moves_a_frozen_posting():
    to_xy, to_ll = _proj()
    r = _raster(frozen=lambda rows, cols, lons, lats: lons < 0)
    st, rings = _ring_stations(3.0)
    rep = RG.rim_grade(r, to_xy, to_ll, st, rings)
    assert np.all(r.alt[:, :200] == 0.0)
    assert rep["unserved"] > 0 and rep["moved"] > 0


def test_seat_records_carry_the_rim_on_the_sets_own_row_only():
    rs = GR._RimSet((0.0, 0.0), 0.0, 100.0, 120.0, 1.0, 1.0, 8.0,
                   np.array([[1.0, 2.0, 100.5]]), (np.array([[0, 0], [1, 0], [1, 1], [0, 0]]),))
    m = TM.TerrainModel("a", "lot_a.obj", (0.0, 0.0), 0.0, 100.0, 0, 0, 0, 1.0, 0.0, rim=rs)
    frame = types.SimpleNamespace(transformers=lambda: (None, lambda x, y: (y * 1e-5, x * 1e-5)))
    ap = types.SimpleNamespace(terrain_models=(("a", "lot_a.obj", m, 0.0),
                                               ("b", "lot_b.obj", m, 0.0)), frame=frame)
    recs = {r["id"]: r for r in TM.seat_records(ap)}
    assert recs["a"]["seat"] == recs["b"]["seat"] == TM.SEAT
    assert recs["a"]["elevation"] == recs["b"]["elevation"] == 100.0
    assert "rim" in recs["a"] and "rim" not in recs["b"] and "cut" not in recs["a"]
    assert recs["a"]["rim"]["stations"] == [[2e-5, 1e-5, 100.5]]
    assert TM.model_paths(recs.values()) == ()          # never offered for hiding


def test_the_tile_stage_reads_and_grades_rim_records(tmp_path, monkeypatch):
    lat0, lon0 = -22.5, -43.5
    to_xy, to_ll = __import__("auto_patch_v2.airport.terrain_cut",
                              fromlist=["projector"]).projector(lat0, lon0)
    st, rings = _ring_stations(205.0)
    lo, la = to_ll(st[:, 0], st[:, 1])
    rlo, rla = to_ll(rings[0][:, 0], rings[0][:, 1])
    rec = {"id": "dsf:obj1", "resource": "lot_a.obj", "seat": TM.SEAT, "elevation": 200.0,
           "rim": {"lat": lat0, "lon": lon0, "z0": 200.0,
                   "stations": np.c_[la, lo, st[:, 2]].tolist(),
                   "rings": [np.c_[rla, rlo].tolist()]}}
    (tmp_path / "o4_v2_rebake_TEST.json").write_text(
        json.dumps({"icao": "TEST", "pack_root": "", "authored_seats": [rec]}), encoding="utf-8",
        newline="")
    rims = TCS.rim_records(str(tmp_path))
    assert [r["id"] for r in rims] == ["dsf:obj1"]
    n = 2001
    dem = types.SimpleNamespace(x0=0.0, x1=1.0, y0=0.0, y1=1.0,
                                alt_dem=np.full((n, n), 200.0, np.float32))
    tile = types.SimpleNamespace(lat=-23, lon=-44, dem=dem)
    monkeypatch.setattr(TCS, "_wet", lambda *a: np.zeros(len(a[2]), bool))
    k = TCS.bake(tile, [], None, rims)
    assert k > 0 and float(dem.alt_dem.max()) > 204.0
    assert dem.terrain_fill_delta is not None and np.all(dem.terrain_fill_delta["delta"] >= 0)
    assert len(TCS._rim_lines(tile, rims)) == 1


def test_a_hill_the_author_added_is_not_our_ground():
    """#2197 round 2: the plaza's valley on FLAT ground of ours -- relief we
    do not have (a hill, a rock, a bridge's approach) -- is refused."""
    plaza = _plaza(-60, -40, 60, 40)
    assert GR._recognise(GR._set_raster([plaza], 0.0), (0.0, 0.0), 0.0,
                        lambda x, y: np.zeros(np.shape(x))) is None


def test_a_deck_over_a_void_is_no_skin():
    """#2197 round 2: the valley as a 2 m slab (a deck, a bridge) follows
    our ground yet is no ground skin."""
    plaza = _plaza(-60, -40, 60, 40)
    under = plaza.copy()
    under[:, :, 1] -= 2.0
    assert GR._recognise(GR._set_raster([plaza, under], 0.0), (0.0, 0.0), 0.0,
                        _ground) is None


def test_a_sheet_far_from_our_ground_is_refused_never_dragged_to():
    """RULINGS 2026-11-25f: a terrace whose ground half follows ours and
    half stands 4 m over it is left as authored: no set, no rim stations."""
    def ground(x, y):
        return _v(x) - 4.0 * (np.asarray(x, float) > 0.0)
    plaza = _plaza(-60, -40, 60, 40)
    assert GR._recognise(GR._set_raster([plaza], 0.0), (0.0, 0.0), 0.0, ground) is None
