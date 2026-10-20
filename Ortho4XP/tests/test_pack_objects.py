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

# a 10 x 6 x 4 m tetrahedron (static), a 1 m one (static clutter) and the
# large one again, animated; vertex 12 unused
_TET = [(0, 0, 0), (10, 0, 0), (0, 6, 0), (0, 0, 4)]
_SMALL = [(20, 0, 0), (21, 0, 0), (20, 1, 0), (20, 0, 1)]
_FACES = [(0, 2, 1), (0, 1, 3), (0, 3, 2), (1, 2, 3)]


def _obj8():
    moved = [(x + 50, y, z) for x, y, z in _TET]       # apart, or the weld joins them
    vt = [f"VT {x} {y} {z} 0 1 0 0 0" for x, y, z in _TET + _SMALL + moved + [(99, 99, 99)]]
    idx = [f"IDX {base + i}" for base in (0, 4, 8) for f in _FACES for i in f]
    return "\n".join(["I", "800", "OBJ", "", f"POINT_COUNTS {len(vt)} 0 0 {len(idx)}"]
                      + vt + idx + ["TRIS 0 24", "ANIM_begin", "TRIS 24 12",
                                    "ANIM_end", ""])


OBJ8 = _obj8()

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
        "I\n1100 Version\n\n1 200 0 0 ZZZZ Synthetic\n99\n", encoding="utf-8", newline="\n")
    dsf = root / "Earth nav data" / "+40-130" / "+45-123.dsf"
    dsf.write_bytes(b"XPLNEDSF")
    (root / "objects").mkdir()
    (root / "objects" / "box.obj").write_text(OBJ8, encoding="utf-8", newline="\n")
    cache = tmp_path / "Airport_mod_cache"
    (cache / "ZZ Pack").mkdir(parents=True)
    dump = cache / "ZZ Pack" / "+45-123.dsf.text"
    dump.write_text(DUMP, encoding="utf-8", newline="\n")
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
    # grey massing: the hull of the one static >= 2 m component only
    assert sorted(map(tuple, verts.tolist())) == sorted(map(tuple, map(lambda p: map(float, p), _TET)))
    assert len(tris) == 4
    centre = verts.mean(axis=0)
    for a, b, c in verts[tris]:
        assert np.dot(np.cross(b - a, c - a), a - centre) > 0     # wound outward
    pl = r["placements"]
    assert [(p["lon"], p["heading_deg"], p["agl_m"]) for p in pl] == [
        (-122.95, 90.0, 0.0), (-122.94, 0.0, 0.0), (-122.93, 180.0, 3.5)]
    assert all(p["model"] == "objects/box.obj" for p in pl)
    text = " ".join(r["missing"])
    assert "objects/missing.obj" in text and "sea-level" in text
    assert "1 object part(s) smaller than 2 m" in text
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
        "nxdem": side, "nydem": side, "epsg": 4326}), encoding="utf-8", newline="\n")
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
    real = TS.tile_config

    def cfg(lat, lon, build_dir=None):
        t = real(lat, lon, build_dir)
        t.airport_elevation_inset_feather_m = 17.0
        return t

    from auto_patch_v2.airport import dem as _dem
    load = _dem.load_dem

    def spy(frame, root, icao, feather_m=60.0):
        seen["feather"] = feather_m
        return load(frame, root, icao, feather_m)

    monkeypatch.setattr(TS, "tile_config", cfg)
    monkeypatch.setattr(_dem, "load_dem", spy)
    r = TC.terrain_sample(TILE, "ZZZZ", [45.2, -122.8, 45.21, -122.79], 50.0)
    assert r["sources"]["frame"] == "authored" and r["sources"]["base"].endswith("N45W123.hgt")
    assert seen["feather"] == 17.0


def test_a_raster_without_its_frame_is_not_read(dem_roots):
    path = _write_alt(dem_roots)
    os.remove(str(path) + ".frame.json")          # 101-square: not the viewfinder grid
    r = TC.terrain_sample(TILE, "ZZZZ", [45.2, -122.8, 45.21, -122.79], 50.0)
    assert r["sources"]["frame"] == "authored"


# ── asynchronous command, session cache, reply cap ──────────────────────

def test_the_command_replies_started_and_one_event_completes_it(pack):
    import io
    import threading
    import time
    from o4_engine import jsonl

    class Capture(io.StringIO):
        def __init__(self):
            super().__init__()
            self.lock = threading.Lock()

        def write(self, text):
            with self.lock:
                return super().write(text)

        def objects(self):
            with self.lock:
                return [json.loads(x) for x in self.getvalue().splitlines() if x.strip()]

    r_fd, w_fd = os.pipe()
    stdin, writer = os.fdopen(r_fd, "r"), os.fdopen(w_fd, "w")
    out = Capture()
    server = threading.Thread(target=jsonl.serve, args=(stdin, out), daemon=True)
    server.start()
    writer.write(json.dumps({"cmd": "pack_objects", "id": 41, "tile": TILE, "icao": "ZZZZ",
                             "bbox": BBOX}) + "\n")
    writer.flush()
    deadline = time.time() + 30
    ready = []
    while time.time() < deadline and not ready:
        ready = [o for o in out.objects() if o.get("event") == "PackObjectsReady"]
        time.sleep(0.05)
    writer.write(json.dumps({"cmd": "shutdown", "id": 42}) + "\n")
    writer.flush()
    server.join(30)
    replies = {o["reply"]: o for o in out.objects() if "reply" in o}
    assert replies[41] == {"reply": 41, "ok": True, "result": {"status": "started"}}
    assert len(ready) == 1 and ready[0]["request"] == 41 and ready[0]["error"] == ""
    assert [m["key"] for m in ready[0]["result"]["models"]] == ["objects/box.obj"]


def test_a_bad_argument_is_refused_before_any_thread(pack):
    events = []
    with pytest.raises(ValueError, match="tile key"):
        PO.start_pack_objects(events.append, "45-123", "ZZZZ", BBOX, request=1)
    assert events == []


def test_a_second_request_is_answered_from_the_session_cache(pack, monkeypatch):
    from o4_engine import pack_massing as PM
    first = PO.pack_objects(TILE, "ZZZZ", BBOX)
    monkeypatch.setattr(PM, "model_hulls", lambda *a: pytest.fail("pack re-read"))
    assert PO.pack_objects(TILE, "ZZZZ", BBOX) is first
    # a changed pack DSF is a new key: read again
    dsf = [p for p in PO._CACHE][-1][0]
    os.utime(dsf, (os.path.getmtime(dsf) + 5,) * 2)
    os.utime(pack, (os.path.getmtime(dsf) + 10,) * 2)
    with pytest.raises(pytest.fail.Exception):
        PO.pack_objects(TILE, "ZZZZ", BBOX)


def test_over_the_cap_the_smallest_parts_go_first():
    from o4_engine import pack_massing as PM

    def hull(size):
        return PM.Hull(np.zeros((8, 3)), np.zeros((12, 3), dtype=int), size)

    models = {"a": [hull(5.0), hull(30.0)], "b": [hull(2.5), hull(9.0)]}
    each = hull(1).wire_bytes
    assert PM.fit_to_cap(models, 0, cap=4 * each) == 0
    dropped = PM.fit_to_cap(models, 0, cap=2 * each)
    assert dropped == 2
    assert [h.size_m for h in models["a"]] == [30.0] and [h.size_m for h in models["b"]] == [9.0]


def test_footprints_only_sends_the_plan_outline_not_the_massing(pack):
    """#797: the 2-D map's answer carries each model's plan hull as (x, z)
    pairs and no vertices or triangles; the placements are the same."""
    full = PO.pack_objects(TILE, "ZZZZ", BBOX)
    flat = PO.pack_objects(TILE, "ZZZZ", BBOX, footprints_only=True)
    assert flat is not full                      # its own cache entry
    (m,) = flat["models"]
    assert set(m) == {"key", "plan_hull_f32_b64"}
    ring = _arr(m["plan_hull_f32_b64"], "<f4", 2)
    verts = _arr(full["models"][0]["vertices_f32_b64"], "<f4", 3)
    want = {(float(x), float(z)) for x, _y, z in verts}
    assert {tuple(map(float, p)) for p in ring} <= want and len(ring) >= 3
    assert flat["placements"] == full["placements"]
    json.dumps(flat)


def test_plan_hull_drops_interior_points():
    from o4_engine import pack_massing as PM
    v = np.array([[0, 0, 0], [10, 5, 0], [10, 0, 10], [0, 9, 10], [5, 3, 5]], float)
    ring = PM.plan_hull([PM.Hull(v, np.zeros((0, 3), int), 10.0)])
    assert sorted(map(tuple, ring.tolist())) == [(0.0, 0.0), (0.0, 10.0), (10.0, 0.0), (10.0, 10.0)]
