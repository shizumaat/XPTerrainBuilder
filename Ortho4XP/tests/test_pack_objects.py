"""``pack_objects`` (protocol 1.12, patch-editor spec §2, §5) and the
terrain-source choice behind ``terrain_sample`` (§5 ruling 3): a synthetic
X-Plane folder, pack, cached dump, OBJ8 and ``.alt`` in ``tmp_path`` —
never the shared data repo, never an install.
"""
import base64
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import numpy as np  # noqa: E402
import pytest  # noqa: E402

import O4_File_Names as FNAMES  # noqa: E402
from o4_engine import pack_objects as PO  # noqa: E402
from o4_engine import terrain_commands as TC  # noqa: E402
from o4_engine import terrain_source as TS  # noqa: E402

TILE = "+45-123"
BBOX = [45.19, -122.96, 45.21, -122.92]

# one static triangle and one animated triangle; vertex 6 unused
OBJ8 = """I
800
OBJ

POINT_COUNTS 7 0 0 6
VT 0 0 0 0 1 0 0 0
VT 10 0 0 0 1 0 0 0
VT 0 6 0 0 1 0 0 0
VT 0 0 0 0 1 0 0 0
VT 2 0 0 0 1 0 0 0
VT 0 2 0 0 1 0 0 0
VT 99 99 99 0 1 0 0 0
IDX 0
IDX 1
IDX 2
IDX 3
IDX 4
IDX 5
TRIS 0 3
ANIM_begin
TRIS 3 3
ANIM_end
"""

DUMP = """OBJECT_DEF objects/box.obj
OBJECT_DEF objects/missing.obj
OBJECT 0 -122.95 45.2 90
OBJECT 0 -122.94 45.2 0
OBJECT_AGL 0 -122.93 45.2 3.5 180
OBJECT 1 -122.95 45.2 0
OBJECT 0 -100.0 10.0 0
OBJECT_MSL 0 -122.95 45.2 812.0 0
"""


@pytest.fixture
def pack(tmp_path, monkeypatch):
    xp = tmp_path / "X-Plane"
    root = xp / "Custom Scenery" / "ZZ Pack"
    (root / "Earth nav data" / "+40-130").mkdir(parents=True)
    (root / "Earth nav data" / "apt.dat").write_text(
        "I\n1100 Version\n\n1 200 0 0 ZZZZ Synthetic\n99\n")
    dsf = root / "Earth nav data" / "+40-130" / "+45-123.dsf"
    dsf.write_bytes(b"XPLNEDSF")
    (root / "objects").mkdir()
    (root / "objects" / "box.obj").write_text(OBJ8)
    cache = tmp_path / "Airport_mod_cache"
    (cache / "ZZ Pack").mkdir(parents=True)
    dump = cache / "ZZ Pack" / "+45-123.dsf.text"
    dump.write_text(DUMP)
    os.utime(dump, (dsf.stat().st_mtime + 10,) * 2)
    monkeypatch.setattr(PO, "xplane_root_for", lambda lat, lon: str(xp))
    monkeypatch.setattr(FNAMES, "airport_mod_cache_root", lambda: str(cache))
    return dump


def _arr(b64, dtype, width):
    return np.frombuffer(base64.b64decode(b64), dtype=dtype).reshape(-1, width)


def test_each_model_once_static_triangles_only(pack):
    r = PO.pack_objects(TILE, "ZZZZ", BBOX)
    assert [m["key"] for m in r["models"]] == ["objects/box.obj"]      # dedup
    m = r["models"][0]
    tris = _arr(m["triangles_u32_b64"], "<u4", 3)
    verts = _arr(m["vertices_f32_b64"], "<f4", 3)
    assert tris.tolist() == [[0, 1, 2]]          # the animated triangle is dropped
    assert verts.tolist() == [[0, 0, 0], [10, 0, 0], [0, 6, 0]]   # compacted
    pl = r["placements"]
    assert [(p["lon"], p["heading_deg"], p["agl_m"]) for p in pl] == [
        (-122.95, 90.0, 0.0), (-122.94, 0.0, 0.0), (-122.93, 180.0, 3.5)]
    assert all(p["model"] == "objects/box.obj" for p in pl)
    text = " ".join(r["missing"])
    assert "objects/missing.obj" in text and "sea-level" in text
    assert "library index" in text                 # none cached: said, not built
    json.dumps(r)                                  # wire-safe


def test_no_cached_dump_is_a_sentence_never_a_regeneration(pack):
    os.remove(pack)
    r = PO.pack_objects(TILE, "ZZZZ", BBOX)
    assert r["models"] == [] and r["placements"] == []
    assert len(r["missing"]) == 1 and "cannot be shown" in r["missing"][0]
    assert not os.listdir(os.path.dirname(pack))   # nothing written


def test_unknown_airport_and_no_install(pack, monkeypatch):
    r = PO.pack_objects(TILE, "QQQQ", BBOX)
    assert "No scenery pack serves QQQQ" in r["missing"][0]
    monkeypatch.setattr(PO, "xplane_root_for", lambda lat, lon: None)
    assert "No X-Plane folder" in PO.pack_objects(TILE, "ZZZZ", BBOX)["missing"][0]


# ── terrain source (§5 ruling 3) ────────────────────────────────────────

N = 121


@pytest.fixture
def dem_roots(tmp_path, monkeypatch):
    elev = tmp_path / "Elevation_data" / "+40-130"
    elev.mkdir(parents=True)
    i = np.arange(N)[:, None]
    j = np.arange(N)[None, :]
    (100 + (N - 1 - i) + 0 * j).astype(">i2").tofile(elev / "N45W123.hgt")   # 100 + 120 (lat-45)
    tiles = tmp_path / "Tiles"
    monkeypatch.setattr(FNAMES, "Elevation_dir", str(tmp_path / "Elevation_data"))
    monkeypatch.setattr(FNAMES, "Tile_dir", str(tiles))
    return tiles / "zOrtho4XP_+45-123"


def _write_alt(build_dir, side=101):
    """A built raster as ``DEM.write_to_file`` writes it: row 0 = NORTH,
    float32, with its frame sidecar; elevation 500 + 1000 (lat - 45)."""
    build_dir.mkdir(parents=True)
    y = 1 - np.arange(side)[:, None] / (side - 1)          # tile-relative lat
    alt = (500 + 1000 * y + 0 * np.arange(side)[None, :]).astype(np.float32)
    path = build_dir / "Data+45-123.alt"
    alt.tofile(path)
    (build_dir / "Data+45-123.alt.frame.json").write_text(json.dumps({
        "schema": "o4.alt.frame/1", "x0": 0.0, "y0": 0.0, "x1": 1.0, "y1": 1.0,
        "nxdem": side, "nydem": side, "epsg": 4326}))
    return path


def _z(reply):
    return np.frombuffer(base64.b64decode(reply["elev_f32_b64"]), "<f4").reshape(
        reply["rows"], reply["cols"])


def test_the_built_raster_wins_when_it_is_readable(dem_roots):
    path = _write_alt(dem_roots)
    r = TC.terrain_sample(TILE, "ZZZZ", [45.2, -122.8, 45.21, -122.79], 50.0)
    assert r["sources"] == {"base": str(path), "inset": None, "frame": "production"}
    lats = 45.2 + np.arange(r["rows"]) * r["dlat"]
    assert np.allclose(_z(r)[:, 0], 500 + 1000 * (lats - 45), atol=1e-2)


def test_overhang_past_the_built_tile_reads_the_authored_dem(dem_roots):
    _write_alt(dem_roots)
    r = TC.terrain_sample(TILE, "ZZZZ", [45.99, -122.01, 46.0, -121.99], 100.0)
    z = _z(r)
    lons = -122.01 + np.arange(r["cols"]) * r["dlon"]
    east = lons > -122.0 + 1e-9                                 # past the tile edge
    assert np.isfinite(z[:, ~east]).all() and np.allclose(z[:, ~east], 500 + 1000 * 0.99, atol=11)
    assert r["sources"]["frame"] == "production"


def test_no_built_raster_falls_back_to_authored_with_the_cfg_feather(dem_roots, monkeypatch):
    seen = {}
    real = TS._tile_config

    def cfg(lat, lon):
        t = real(lat, lon)
        t.airport_elevation_inset_feather_m = 17.0
        return t

    from auto_patch_v2.airport import dem as _dem
    load = _dem.load_dem

    def spy(frame, root, icao, feather_m=60.0):
        seen["feather"] = feather_m
        return load(frame, root, icao, feather_m)

    monkeypatch.setattr(TS, "_tile_config", cfg)
    monkeypatch.setattr(_dem, "load_dem", spy)
    r = TC.terrain_sample(TILE, "ZZZZ", [45.2, -122.8, 45.21, -122.79], 50.0)
    assert r["sources"]["frame"] == "authored" and r["sources"]["base"].endswith("N45W123.hgt")
    assert seen["feather"] == 17.0


def test_a_raster_without_its_frame_is_not_read(dem_roots):
    path = _write_alt(dem_roots)
    os.remove(str(path) + ".frame.json")          # 101-square: not the viewfinder grid
    r = TC.terrain_sample(TILE, "ZZZZ", [45.2, -122.8, 45.21, -122.79], 50.0)
    assert r["sources"]["frame"] == "authored"
