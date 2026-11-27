"""RULINGS 2026-11-25j/l: a ROCK OUTCROP or an ADDED HILL a pack lays on the
ground (a plain or ``OBJECT_AGL`` row, often hard, often tiled-textured) is
a terrain shell (``terrain_rock``): recognised by THE WITNESS
(``rock_witness``: one top sheet standing on its own ground zero, no storey
walls, no right-angle creases, not axis-aligned), matched at its row's
datum, seated by the shells' skirt seat; where the skirt runs out our
ground is raised to its rim (``fill_z0``, the run-out fill).  Built
look-alikes -- a terrace of storeys, a building on a flat plate, an arched
roof on its walls, a fence -- are refused.  Synthetic OBJ8s, no corpus."""
import json
import math
import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
sys.path.insert(0, os.path.dirname(__file__))

import test_terrain_model as TTM  # noqa: E402
from auto_patch import terrain_cut_stage as TCS  # noqa: E402
from auto_patch_v2.airport import rock_witness as RW  # noqa: E402
from auto_patch_v2.airport import terrain_cut as TC  # noqa: E402
from auto_patch_v2.airport import terrain_fill as TF  # noqa: E402
from auto_patch_v2.airport import terrain_model as TM  # noqa: E402
from auto_patch_v2.airport import terrain_rock as TR  # noqa: E402
from auto_patch_v2.airport.obj8 import parse_obj8  # noqa: E402

HALF = 50.0


def _outcrop(x, z):
    """A 20 m outcrop over a 100 m square, its rim at y = 0."""
    r = math.hypot(x, z) / HALF
    return max(0.0, 20.0 * (1.0 - r))


def _write(tmp_path, name="rock.obj", height=_outcrop, **kw):
    kw.setdefault("hard", True)
    kw.setdefault("uv", "atlas")
    return TTM._write(tmp_path, name, height, half=HALF, step=5.0, **kw)


def _soup(tmp_path, name, tris):
    """An OBJ8 of the triangles ``tris`` (``(n, 3, 3)`` x y z corners),
    each with its face normal (up-turned for the upward faces)."""
    vt = []
    for t in tris:
        a = np.asarray(t, float)
        n = np.cross(a[1] - a[0], a[2] - a[0])
        n = n / max(np.linalg.norm(n), 1e-12) * (1.0 if n[1] >= 0.0 else -1.0)
        vt += [f"VT {x} {y} {z} {n[0]} {n[1]} {n[2]} 0 0" for x, y, z in t]
    idx = list(range(len(vt)))
    body = ["I", "800", "OBJ", f"POINT_COUNTS {len(vt)} 0 0 {len(idx)}", *vt]
    body += [f"IDX {i}" for i in idx] + [f"TRIS 0 {len(idx)}"]
    path = tmp_path / name
    path.write_text("\n".join(body) + "\n", encoding="utf-8", newline="\n")
    return str(path)


def _quad(a, b, c, d):
    return [[a, b, c], [a, c, d]]


def _box(x0, x1, z0, z1, h, y0=0.0):
    """A roofed box: four walls and the roof that caps them."""
    p = [(x0, z0), (x1, z0), (x1, z1), (x0, z1)]
    out = _quad(*[(x, h, z) for x, z in reversed(p)])
    for (xa, za), (xb, zb) in zip(p, p[1:] + p[:1], strict=True):
        out += _quad((xa, y0, za), (xb, y0, zb), (xb, h, zb), (xa, h, za))
    return out


def _flat(z):
    return lambda xs, ys: np.full(len(xs), float(z))


def _verdict(path):
    return TR.rock_verdict(path, parse_obj8(path))


def test_a_hard_atlas_textured_outcrop_is_a_rock(tmp_path):
    s = TM.shape_of(_write(tmp_path))
    assert s is not None and s.small and s.rock and s.rock_only
    assert s.relief_m >= TR.ROCK_MIN_RELIEF_M
    w = dict(s.witness)
    assert w["sheet"] == pytest.approx(1.0) and w["wall"] == 0.0 and w["right"] == 0.0
    assert w["axis"] <= RW.ROCK_MAX_AXIS and abs(w["base_m"]) < 0.01


def test_a_berm_with_a_few_free_standing_tree_cards_is_a_rock(tmp_path):
    g = parse_obj8(_write(tmp_path, "berm.obj"))
    ground = g.vertices[g.solid].tolist()
    cards = []
    for k in (-20, 20):                      # two 4 m cards on the slope
        y = _outcrop(float(k), 0.0)
        cards += _quad((k - 1.0, y, 0.0), (k + 1.0, y, 0.0), (k + 1.0, y + 4.0, 0.0),
                       (k - 1.0, y + 4.0, 0.0))
    s = TM.shape_of(_soup(tmp_path, "berm_trees.obj", ground + cards))
    assert s is not None and s.rock
    assert 0.0 < dict(s.witness)["wall"] <= RW.ROCK_MAX_WALL


def test_a_terrace_of_storeys_is_not(tmp_path):
    # six roofed blocks rising 4 m each: steep enough, one body, but every
    # wall a storey, every roof flat and square to its walls
    tris = []
    for k in range(6):
        tris += _box(-30.0 + 10.0 * k, -20.0 + 10.0 * k, -30.0, 30.0, 4.0 * (k + 1))
    path = _soup(tmp_path, "terrace.obj", tris)
    assert TM.shape_of(path) is None
    f, failed = _verdict(path)
    assert {"one_sheet", "no_storey_walls", "no_right_creases"} <= set(failed)


def test_a_hipped_building_on_a_flat_plate_is_not(tmp_path):
    # an 80 m plate at y = 0 and, on it, a 60 m block with a hipped roof
    # rising from 6 m to 16 m: axis-aligned slopes, storey walls, creases
    tris = _quad((-40.0, 0.0, -40.0), (-40.0, 0.0, 40.0), (40.0, 0.0, 40.0), (40.0, 0.0, -40.0))
    p = [(-30.0, -30.0), (30.0, -30.0), (30.0, 30.0), (-30.0, 30.0)]
    for (xa, za), (xb, zb) in zip(p, p[1:] + p[:1], strict=True):
        tris += _quad((xa, 0.0, za), (xb, 0.0, zb), (xb, 6.0, zb), (xa, 6.0, za))
        tris += [[(xa, 6.0, za), (0.0, 16.0, 0.0), (xb, 6.0, zb)]]
    path = _soup(tmp_path, "hipped.obj", tris)
    assert TM.shape_of(path) is None
    got = _verdict(path)
    assert got is None or {"not_axis_aligned", "no_storey_walls"} <= set(got[1])


def test_an_arched_roof_on_its_walls_is_not(tmp_path):
    # a 100 m barrel vault of 20 m radius springing from 6 m walls
    tris, k = [], 16
    for i in range(k):
        a0, a1 = math.pi * i / k, math.pi * (i + 1) / k
        x0, y0 = 20.0 * math.cos(a0), 6.0 + 20.0 * math.sin(a0)
        x1, y1 = 20.0 * math.cos(a1), 6.0 + 20.0 * math.sin(a1)
        tris += _quad((x0, y0, -50.0), (x0, y0, 50.0), (x1, y1, 50.0), (x1, y1, -50.0))
    for x in (-20.0, 20.0):
        tris += _quad((x, 0.0, -50.0), (x, 0.0, 50.0), (x, 6.0, 50.0), (x, 6.0, -50.0))
    path = _soup(tmp_path, "vault.obj", tris)
    assert TM.shape_of(path) is None
    f, failed = _verdict(path)
    assert "on_ground" in failed and "not_axis_aligned" in failed


def test_a_fence_and_a_gentle_mound_are_not(tmp_path):
    fence = _quad((-100.0, 0.0, 0.0), (100.0, 0.0, 0.0), (100.0, 6.0, 0.0), (-100.0, 6.0, 0.0))
    assert TM.shape_of(_soup(tmp_path, "fence.obj", fence)) is None
    mound = TTM._write(tmp_path, "mound.obj",
                       lambda x, z: 6.0 * (1 - abs(x) / 200) * (1 - abs(z) / 200),
                       half=200.0, step=10.0, hard=True, uv="atlas")
    assert TM.shape_of(mound) is None


def test_the_gates_and_their_constants():
    f = {"sheet": 0.95, "base_m": 0.5, "top_m": 6.0, "wall": 0.01, "right": 0.02,
         "axis": 0.3, "smooth": 0.2}
    assert RW.failed(f) == []
    assert RW.failed(f, lift=1.0) == ["on_ground"]
    assert RW.failed(dict(f, sheet=0.85, axis=0.6)) == ["one_sheet", "not_axis_aligned"]
    assert RW.failed(dict(f, top_m=4.0)) == ["on_ground"]
    assert RW.failed(dict(f, smooth=0.6)) == ["natural_surface"]


def _dome(x, z):
    """A smooth spherical cap: 40 m radius, 20 m over its 69 m rim."""
    return max(0.0, math.sqrt(max(1600.0 - x * x - z * z, 0.0)) - 20.0)


def _rough_berm(x, z):
    """A 14 m berm across a 100 m square with undulations at several
    scales (RULINGS 2026-11-26b: natural relief changes its curvature)."""
    body = 14.0 * math.exp(-(z / 18.0) ** 2) * (1.0 - (x / 50.0) ** 2)
    rough = (1.2 * math.sin(0.9 * x + 1.3 * z) * math.cos(1.7 * x - 0.6 * z)
             + 0.8 * math.sin(0.23 * x * z + 0.5) + 0.6 * math.cos(2.1 * z - 0.4 * x))
    return max(0.0, body + rough * body / 14.0)


def test_a_smooth_dome_on_the_ground_is_not_natural(tmp_path):
    # RULINGS 2026-11-26b (1): one sheet on its ground, no walls, no
    # creases, not axis-aligned -- but one large continuous curve
    path = TTM._write(tmp_path, "dome.obj", _dome, half=36.0, step=2.0, hard=True, uv="atlas")
    assert TM.shape_of(path) is None
    f, failed = _verdict(path)
    assert failed == ["natural_surface"]
    assert f["smooth"] > RW.ROCK_MAX_SMOOTH


def test_a_rough_berm_is_natural_and_a_rock(tmp_path):
    path = TTM._write(tmp_path, "rough_berm.obj", _rough_berm, half=50.0, step=2.5, hard=True,
                      uv="atlas")
    f, failed = _verdict(path)
    assert failed == [] and f["smooth"] < RW.ROCK_MAX_SMOOTH / 4
    s = TM.shape_of(path)
    assert s is not None and s.rock


def test_row_datum_is_the_ground_plus_the_lift_and_msl_rows_are_never_rocks(tmp_path):
    dem = _flat(12.0)
    assert TR.row_datum("OBJECT_MSL", 40.0, (0.0, 0.0), dem) is None
    assert TR.row_datum("OBJECT", None, (0.0, 0.0), dem) == 12.0
    assert TR.row_datum("OBJECT_AGL", 0.5, (0.0, 0.0), dem) == 12.5
    assert TR.row_datum("OBJECT", None, (0.0, 0.0), _flat(math.nan)) is None
    s = TM.shape_of(_write(tmp_path))
    # ON THE GROUND with the row's lift: 2 m up, its base is off its zero
    assert TR.row_datum("OBJECT_AGL", 2.0, (0.0, 0.0), dem, s) is None


def test_a_plain_row_matches_where_its_rim_does_not_float_and_msl_is_a_shell(tmp_path):
    path = _write(tmp_path)
    rows = [("dsf:obj1", "m.obj", (0.0, 0.0), 0.0, None, "OBJECT"),
            ("dsf:obj2", "m.obj", (900.0, 0.0), 0.0, None, "OBJECT"),
            ("dsf:obj3", "m.obj", (0.0, 900.0), 0.0, 10.0, "OBJECT_MSL")]

    def dem(xs, ys):
        # flat at 10 m but a 20 m spike under the second rock's anchor: its
        # datum there leaves its rim 20 m over our ground
        xs, ys = np.asarray(xs, float), np.asarray(ys, float)
        return 10.0 + np.where((np.abs(xs - 900.0) < 5.0) & (np.abs(ys) < 5.0), 20.0, 0.0)
    found = TM.placement_models(rows, lambda d: path, lambda d: parse_obj8(path), dem)
    # #2285 (TNCS's hard tide-pool shell): the OBJECT_MSL row of a rock is
    # a small shell at its author's datum, never left to the 11d conversion
    assert set(found) == {"dsf:obj1", "dsf:obj3"}
    m = found["dsf:obj1"]
    assert m.small and m.datum is None and m.z0 == pytest.approx(10.0) and m.fill_z0 is None
    s = found["dsf:obj3"]
    assert s.small and s.datum == pytest.approx(10.0) and s.z0 == pytest.approx(10.0)
    assert s.fill_z0 is None and not s.hideable
    rec = TR.rock_match(TM.shape_of(path), (0.0, 0.0), 0.0, _flat(10.0), 10.0)
    assert rec["level_m"] == pytest.approx(0.0, abs=0.01) and not rec["hideable"]
    # a buried rim is the skirt's business: our ground 3 m over it matches
    assert TR.rock_match(TM.shape_of(path), (0.0, 0.0), 0.0, _flat(13.0), 10.0) is not None


def test_an_msl_rock_row_off_our_ground_is_not_a_shell(tmp_path):
    """#2285: the shell law's level test still holds on a rock's
    OBJECT_MSL row -- authored 30 m over our ground, it is not read."""
    s = TM.shape_of(_write(tmp_path))
    assert TM.match(s, (0.0, 0.0), 0.0, _flat(10.0), datum=10.0) is not None
    assert TM.match(s, (0.0, 0.0), 0.0, _flat(10.0), datum=40.0) is None


def _slope(xs, ys):
    """Ground falling 0.2 m per metre to the east."""
    return 50.0 - 0.2 * np.asarray(xs, float)


def test_a_rock_whose_skirt_runs_out_carries_its_fill_seat(tmp_path):
    path = _write(tmp_path)
    assert TR.fill_seat(path, (0.0, 0.0), 0.0, 10.0, _flat(10.0)) is None
    # on the slope its east rim floats ~10 m: deeper than its skirt
    z = TR.fill_seat(path, (0.0, 0.0), 0.0, 50.0, _slope)
    assert z is not None and 40.0 < z < 50.0
    rows = [("dsf:obj1", "m.obj", (0.0, 0.0), 0.0, None, "OBJECT")]
    found = TM.placement_models(rows, lambda d: path, lambda d: parse_obj8(path), _slope)
    assert found["dsf:obj1"].fill_z0 == pytest.approx(z)


def _shell_rec(path, fill_z0=None):
    to_xy, to_ll = TC.projector(47.8, 13.04)
    rec = {"id": "dsf:obj1", "model": "dsf:obj1", "resource": "o/rock.obj",
           "seat": TM.SEAT, "elevation": 50.0, "hideable": False,
           "shell": {"file": path, "lat": 47.8, "lon": 13.04, "heading": 0.0}}
    if fill_z0 is not None:
        rec["fill_z0"] = fill_z0
    return rec


def test_the_run_out_fill_is_a_rim_only_fill_record(tmp_path):
    path = _write(tmp_path)
    plan = {"icao": "TEST", "pack_root": str(tmp_path / "pack"),
            "authored_seats": [_shell_rec(path), dict(_shell_rec(path, 44.0), id="dsf:obj2")]}
    (tmp_path / "o4_v2_rebake_TEST.json").write_text(json.dumps(plan), encoding="utf-8",
                                                       newline="")
    recs = TCS.cut_records(str(tmp_path), ["TEST"])
    assert [r["id"] for r in recs] == ["dsf:obj2"]
    assert recs[0]["elevation"] == 44.0
    assert recs[0]["cut"]["fill"] and recs[0]["cut"]["rim_only"]


def test_the_run_out_fill_raises_our_ground_to_the_rim_never_in_the_patch(tmp_path):
    path = _write(tmp_path)
    lat, lon = 47.8, 13.04
    post = 5.0 / 111_320.0
    dlon = post / math.cos(math.radians(lat))
    n = 81

    def raster(frozen=None):
        alt = np.full((n, n), 40.0)
        return TF.Raster(alt, lon - 40 * dlon, lat + 40 * post, dlon, post, frozen)
    rec = _shell_rec(path, 45.0)
    r = raster()
    rep = TCS.run_out_fill(r, rec)
    assert rep["supports"] > 0 and rep["raised"] > 0 and rep["unserved"] == 0
    # the rim stands at 45 m (its seat): our ground raised to it there,
    # shoulder then talus away from it, never lowered
    to_xy, to_ll = TC.projector(lat, lon)
    edge = r.sample(*to_ll(np.array([HALF + 1.5]), np.array([0.0])))[0]
    far = r.sample(*to_ll(np.array([HALF + 40.0]), np.array([0.0])))[0]
    assert edge >= 45.0 and 40.0 <= far < edge and r.alt.min() == 40.0
    frozen = TCS.run_out_fill(raster(lambda rows, cols, lons, lats: np.ones(len(rows), bool)),
                              rec)
    assert frozen["raised"] == 0 and frozen["unserved"] == frozen["supports"] > 0


def test_a_rock_reads_only_in_a_frame_of_its_own(tmp_path):
    # RULINGS 2026-11-25l (1): rows sharing the rock's origin must be its
    # content (over its plan, LICR's lights on its hillside); a scene
    # exported at one zero around it (LPLA, EGKK) is a composite
    path = _write(tmp_path)
    on = _soup(tmp_path, "light.obj", _quad((0.0, 15.0, 0.0), (1.0, 15.0, 0.0),
                                            (1.0, 16.0, 0.0), (0.0, 16.0, 0.0)))
    off = _soup(tmp_path, "hangar.obj", _box(300.0, 340.0, 0.0, 40.0, 10.0))
    s = TM.shape_of(path)
    assert TR.own_frame(s, [parse_obj8(on)]) and not TR.own_frame(s, [parse_obj8(off)])
    assert not TR.own_frame(s, [None])
    paths = {"m.obj": path, "on.obj": on, "off.obj": off}

    def found(*others):
        rows = [("dsf:obj1", "m.obj", (0.0, 0.0), 0.0, None, "OBJECT")]
        rows += [(f"dsf:obj{k + 2}", d, (0.0, 0.0), 0.0, None, "OBJECT")
                 for k, d in enumerate(others)]
        return TM.placement_models(rows, paths.get, lambda d: parse_obj8(paths[d]), _flat(10.0))
    assert "dsf:obj1" in found("on.obj") and "dsf:obj1" not in found("on.obj", "off.obj")
