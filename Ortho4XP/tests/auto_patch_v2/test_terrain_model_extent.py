"""Issue #2272: the airport inset box grows over the terrain objects a pack
places near its aerodrome (``terrain_model_extent``; the fetch side
``O4_Inset_Terrain_Objects``) -- the union, the cap, and the identity
when nothing is admitted.  Synthetic OBJ8s and boxes, no corpus."""
import math
import os
import sys
import types

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))
sys.path.insert(0, os.path.dirname(__file__))

import test_terrain_shell as TTS  # noqa: E402
from auto_patch_v2.airport import terrain_model as TM  # noqa: E402
from auto_patch_v2.airport import terrain_model_extent as TX  # noqa: E402

M_LAT = 111_320.0
TILE = (-63.0, 17.0, -62.0, 18.0)
AERODROME = (-62.85, 17.90, -62.84, 17.91)
BOX = (-62.854, 17.896, -62.836, 17.914)


def _m_lon(lat):
    return M_LAT * math.cos(math.radians(lat))


def _model(lon, lat, half_m, name="rock.obj"):
    """A square plan box ``2 * half_m`` across centred on ``(lon, lat)``."""
    dl, dp = half_m / _m_lon(lat), half_m / M_LAT
    return TX.ModelBox(name, lon, lat, (lon - dl, lat - dp, lon + dl, lat + dp),
                       (2 * half_m) ** 2)


def test_the_outline_turns_as_the_seat_turns(tmp_path):
    """The plan box of a placement holds every covered cell exactly where
    ``terrain_model._world`` puts it, at any heading."""
    path = TTS._write(tmp_path)
    shape = TM.shape_of(path)
    pts = TX.outline(path)
    assert shape is not None and pts and len(pts) >= 3
    ii, jj = np.nonzero(shape.grid.covered)
    lon, lat = -62.85, 17.9
    for heading in (0.0, 37.0, 90.0, 211.0):
        (w, s, e, n), area = TX._plan_box(pts, lon, lat, heading)
        xs, ys = TM._world(shape.grid, ii, jj, (0.0, 0.0), heading)
        lo, la = lon + xs / _m_lon(lat), lat + ys / M_LAT
        assert lo.min() >= w and lo.max() <= e and la.min() >= s and la.max() <= n
        assert 200.0 ** 2 <= area <= 320.0 ** 2


def test_a_building_has_no_outline(tmp_path):
    flat = TTS._write(tmp_path, "kerb.obj", lambda x, z: 0.5)
    assert TX.outline(flat) is None
    rows = [("kerb.obj", -62.86, 17.9, 0.0), ("lib/stock.obj", -62.86, 17.9, 0.0)]
    assert TX.plan_boxes(rows, lambda d: flat if d == "kerb.obj" else None) == []


def test_plan_boxes_ask_each_file_once(tmp_path):
    path = TTS._write(tmp_path)
    asked = []

    def outline_of(p):
        asked.append(p)
        return TX.outline(p)
    rows = [("rock.obj", -62.86, 17.9, 0.0), ("rock.obj", -62.87, 17.9, 45.0)]
    got = TX.plan_boxes(rows, lambda d: path, outline_of)
    assert len(got) == 2 and asked == [path]


def test_near_rows_stand_off_the_aerodrome_and_within_reach():
    rows = [("on.obj", -62.845, 17.905, 0.0),                    # on the aerodrome
            ("near.obj", -62.86, 17.905, 0.0),                   # ~1 km west
            ("far.obj", -62.70, 17.905, 0.0)]                    # ~15 km east
    assert [r[0] for r in TX.nearby(rows, [AERODROME])] == ["near.obj"]
    assert TX.nearby(rows, []) == []


def test_the_union_grows_the_box_over_an_admitted_object():
    m = _model(-62.86, 17.905, 150.0)
    box, admitted, left = TX.admit([m], AERODROME, BOX, TILE, 160.0)
    assert admitted == [m] and left == []
    pad = 160.0 / _m_lon(17.905)
    assert math.isclose(box[0], m.box[0] - pad)
    assert box[1:] == BOX[1:]                    # the object sits inside on the other sides


def test_the_cap_names_what_it_leaves_out():
    huge = _model(-62.86, 17.905, 2000.0, "island.obj")      # 16 km2
    far = _model(-62.70, 17.905, 100.0, "far.obj")           # ~15 km away
    off = TX.ModelBox("off.obj", -63.2, 17.9, (-63.3, 17.89, -63.1, 17.91), 1.0e6)
    box, admitted, left = TX.admit([huge, far, off], AERODROME, BOX, TILE, 160.0)
    assert box is BOX and admitted == []
    why = {m.resource: w for m, w in left}
    assert "km2" in why["island.obj"] and "from the aerodrome" in why["far.obj"]
    assert why["off.obj"] in ("off the tile",) or "from the aerodrome" in why["off.obj"]


def test_an_admitted_box_is_clipped_to_the_tile():
    edge = (-62.99, 17.90, -62.98, 17.91)
    m = _model(-63.0, 17.905, 300.0)
    box, admitted, _left = TX.admit([m], edge, edge, TILE, 160.0)
    assert admitted == [m] and box[0] == TILE[0]


def test_nearest_takes_the_closest_aerodrome():
    m = _model(-62.86, 17.905, 50.0)
    assert TX.nearest(m, {"A": AERODROME, "B": (-62.5, 17.5, -62.49, 17.51)}) == "A"
    assert TX.nearest(m, {}) is None


def test_the_gates_key_follows_the_gates(monkeypatch):
    k = TX.gates_key()
    monkeypatch.setattr(TM, "MIN_PLAN_M", TM.MIN_PLAN_M + 1.0)
    assert TX.gates_key() != k


# ---- the fetch side (O4_Inset_Terrain_Objects) -------------------------

def _tile():
    return types.SimpleNamespace(lat=17, lon=-63, airport_elevation_inset_feather_m=60.0)


def test_no_model_leaves_the_request_identical(monkeypatch):
    import O4_Airport_Elevation_Insets as INSETS
    import O4_Inset_Terrain_Objects as TO
    boxes = {"TFFJ": BOX}
    monkeypatch.setattr(INSETS, "_xplane_root_for_package_footprints", lambda: None)
    assert TO.grow_boxes(_tile(), {}, boxes) is boxes
    monkeypatch.setattr(INSETS, "_xplane_root_for_package_footprints", lambda: "/xp")
    monkeypatch.setattr(INSETS, "_airport_bounding_boxes",
                        lambda *a, **k: {"TFFJ": AERODROME})
    monkeypatch.setattr(TO, "_pack_models", lambda *a: [])
    assert TO.grow_boxes(_tile(), {}, boxes) is boxes

    def boom(*a):
        raise OSError("unreadable")
    monkeypatch.setattr(TO, "_pack_models", boom)
    assert TO.grow_boxes(_tile(), {}, boxes) is boxes


def test_a_model_grows_only_its_airports_box(monkeypatch):
    import O4_Airport_Elevation_Insets as INSETS
    import O4_Inset_Terrain_Objects as TO
    other = (-62.5, 17.5, -62.49, 17.51)
    boxes = {"TFFJ": BOX, "TXXX": other}
    monkeypatch.setattr(INSETS, "_xplane_root_for_package_footprints", lambda: "/xp")
    monkeypatch.setattr(INSETS, "_airport_bounding_boxes",
                        lambda *a, **k: {"TFFJ": AERODROME, "TXXX": other})
    monkeypatch.setattr(TO, "_pack_models", lambda *a: [_model(-62.86, 17.905, 150.0)])
    got = TO.grow_boxes(_tile(), {}, boxes)
    assert got["TXXX"] == other and got["TFFJ"][0] < BOX[0]
    assert boxes == {"TFFJ": BOX, "TXXX": other}            # the request is a new dict


def test_kept_outlines_are_asked_once_per_file_version(tmp_path, monkeypatch):
    import O4_Inset_Terrain_Objects as TO
    from auto_patch import dsf_reader
    path = TTS._write(tmp_path)
    monkeypatch.setattr(dsf_reader, "airport_mod_cache_dir",
                        lambda root: str(tmp_path / "cache"))
    kept = TO._Kept(str(tmp_path), TX.gates_key())
    first = kept(path)
    kept.save()
    calls = []
    monkeypatch.setattr(TX, "outline", lambda p: calls.append(p))
    again = TO._Kept(str(tmp_path), TX.gates_key())
    assert again(path) == first and calls == []
    stale = TO._Kept(str(tmp_path), "another-gates-key")
    stale(path)
    assert calls == [path]


def test_an_armed_guard_keeps_the_outlines_in_memory(tmp_path, monkeypatch):
    import O4_Inset_Terrain_Objects as TO
    from auto_patch import dsf_reader
    from elevation_access import downloads
    path = TTS._write(tmp_path)
    monkeypatch.setattr(dsf_reader, "airport_mod_cache_dir",
                        lambda root: str(tmp_path / "cache"))
    monkeypatch.setattr(downloads, "_write_refused_by_armed_guard", lambda p: True)
    kept = TO._Kept(str(tmp_path), TX.gates_key())
    assert kept(path)
    kept.save()
    assert not (tmp_path / "cache").exists()


def test_the_kept_outlines_are_guarded_python_only():
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "tools", "harness"))
    import O4_Inset_Terrain_Objects as TO
    import shared_repo_guard as G
    assert G.is_guarded_python_only_artifact("Airport_mod_cache/Some Pack/" + TO.KEPT_NAME)
    assert not G.is_guarded_python_only_artifact("Airport_mod_cache/" + TO.KEPT_NAME)
    assert not G.is_guarded_python_only_artifact("Airport_mod_cache/a/b/" + TO.KEPT_NAME)
