"""The Library view's engine commands (#824, ``o4_engine.library``) on a
synthetic data folder in ``tmp_path`` — never the shared data repo, never
an install: sizes summed, a tile built by another tool flagged read-only
and never deleted, nothing freed or deleted without ``confirm``.
"""
import io
import json
import os
import sys
import threading
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import O4_File_Names as FNAMES  # noqa: E402
import O4_Scenery_Links as LINKS  # noqa: E402
import pytest  # noqa: E402
from o4_engine import library as LIB  # noqa: E402

OURS = (45, -123)
OTHER = (46, -123)


def _write(path, size):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as handle:
        handle.write(b"x" * size)


def _tile(tiles, lat, lon, ours, provider="BI", zl=17):
    short = FNAMES.short_latlon(lat, lon)
    build = os.path.join(tiles, "zOrtho4XP_" + short)
    _write(os.path.join(build, "Earth nav data",
                        FNAMES.long_latlon(lat, lon) + ".dsf"), 1000)
    _write(os.path.join(build, "textures", "1000_2000_%s%d.dds" % (provider, zl)), 500)
    if ours:
        with open(os.path.join(build, "XPTerrainBuilder_" + short + ".cfg"), "w",
                  encoding="utf-8", newline="\n") as handle:
            handle.write("cfg_written_by=test\ndefault_website=%s\n"
                         "default_zl=%d\n" % (provider, zl))
    return build


@pytest.fixture
def data(tmp_path, monkeypatch):
    for name, sub in (("Imagery_dir", "Orthophotos"), ("Elevation_dir", "Elevation_data"),
                      ("OSM_dir", "OSM_data"), ("Patch_dir", "Patches")):
        monkeypatch.setattr(FNAMES, name, str(tmp_path / sub))
    _write(str(tmp_path / "Orthophotos" / "+40-130" / "a.jpg"), 300)
    _write(str(tmp_path / "Orthophotos" / "b.jpg"), 200)
    _write(str(tmp_path / "Elevation_data" / "dem.tif"), 50)
    tiles = str(tmp_path / "Tiles")
    _tile(tiles, *OURS, ours=True)
    _tile(tiles, *OTHER, ours=False, provider="GO2", zl=16)
    patch_dir = FNAMES.patch_dir(*OURS)
    _write(os.path.join(patch_dir, "KPDX_auto.patch.osm"), 10)
    _write(os.path.join(patch_dir, "KHIO_edited.patch.osm"), 10)
    scenery = str(tmp_path / "Custom Scenery")
    os.makedirs(scenery)
    return {"root": tmp_path, "tiles": tiles, "scenery": scenery}


def test_scan_sums_sizes_and_reads_each_tile(data):
    LINKS.install(*OURS, os.path.join(data["tiles"], "zOrtho4XP_+45-123"), data["scenery"])
    out = LIB.library_scan(data["tiles"], data["scenery"])
    rows = {(r["lat"], r["lon"]): r for r in out["tiles"]}
    ours, other = rows[OURS], rows[OTHER]
    assert ours["size_bytes"] == 1000 + 500 + len(
        "cfg_written_by=test\ndefault_website=BI\ndefault_zl=17\n")
    assert other["size_bytes"] == 1500
    assert out["tiles_bytes"] == ours["size_bytes"] + other["size_bytes"]
    assert (ours["provider"], ours["zl"]) == ("BI", 17)
    assert (other["provider"], other["zl"]) == ("GO2", 16)    # from the textures
    assert ours["airports"] == ["KHIO", "KPDX"] and other["airports"] == []
    assert ours["in_xplane"] and not other["in_xplane"]
    assert ours["built"] is not None
    caches = {c["kind"]: c["bytes"] for c in out["caches"]}
    assert caches == {"imagery": 500, "elevation": 50, "osm": 0}


def test_a_tile_built_by_another_tool_is_read_only(data):
    rows = {(r["lat"], r["lon"]): r for r in LIB.library_scan(data["tiles"])["tiles"]}
    assert rows[OURS]["built_by"] == LIB.BUILT_HERE and not rows[OURS]["read_only"]
    assert rows[OTHER]["built_by"] == LIB.BUILT_ELSEWHERE and rows[OTHER]["read_only"]


def test_a_step_record_alone_marks_the_tile_ours(data):
    build = os.path.join(data["tiles"], "zOrtho4XP_+46-123")
    _write(os.path.join(build, "Ortho4XP_+46-123_steps.json"), 2)
    rows = {(r["lat"], r["lon"]): r for r in LIB.library_scan(data["tiles"])["tiles"]}
    assert not rows[OTHER]["read_only"]


def test_free_cache_refuses_without_confirm_and_says_what_comes_back(data):
    with pytest.raises(ValueError, match="downloaded again"):
        LIB.free_cache("imagery")
    assert os.path.isfile(str(data["root"] / "Orthophotos" / "b.jpg"))
    with pytest.raises(ValueError, match="not a cache"):
        LIB.free_cache("tiles", confirm=True)


def test_free_cache_empties_the_folder_and_keeps_it(data):
    out = LIB.free_cache("imagery", confirm=True)
    assert out["freed_bytes"] == 500
    assert os.listdir(str(data["root"] / "Orthophotos")) == []
    assert os.path.isfile(str(data["root"] / "Elevation_data" / "dem.tif"))


def test_delete_refuses_without_confirm_and_never_deletes_another_tools_tile(data):
    with pytest.raises(ValueError, match="confirm"):
        LIB.library_delete([list(OURS)], data["tiles"])
    with pytest.raises(ValueError, match="another tool"):
        LIB.library_delete([list(OURS), list(OTHER)], data["tiles"], confirm=True)
    assert sorted(os.listdir(data["tiles"])) == ["zOrtho4XP_+45-123", "zOrtho4XP_+46-123"]


def test_delete_removes_the_folder_and_its_link_and_keeps_patches(data):
    build = os.path.join(data["tiles"], "zOrtho4XP_+45-123")
    LINKS.install(*OURS, build, data["scenery"])
    out = LIB.library_delete([list(OURS)], data["tiles"], data["scenery"], confirm=True)
    assert out["deleted"] == [list(OURS)] and out["freed_bytes"] > 1500
    assert not os.path.exists(build)
    assert os.listdir(data["scenery"]) == []
    assert os.path.isdir(FNAMES.patch_dir(*OURS))


def test_start_refuses_on_the_read_loop_and_completes_with_one_event(data):
    events = []
    with pytest.raises(ValueError, match="confirm"):
        LIB.start(events.append, "free_cache", request=1, kind="osm")
    with pytest.raises(ValueError, match="build is running"):
        LIB.start(events.append, "free_cache", request=2, busy=lambda: True,
                  kind="osm", confirm=True)
    assert LIB.start(events.append, "cache_sizes", request=3) == {"status": "started"}
    deadline = time.time() + 10
    while not events and time.time() < deadline:
        time.sleep(0.02)
    assert len(events) == 1 and events[0].request == 3
    assert events[0].command == "cache_sizes" and events[0].error == ""


def test_the_transport_replies_started_then_library_ready(data):
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
    writer.write(json.dumps({"cmd": "library_scan", "id": 7, "working_dir": data["tiles"],
                             "scenery_dir": data["scenery"]}) + "\n")
    writer.write(json.dumps({"cmd": "free_cache", "id": 8, "kind": "osm"}) + "\n")
    writer.flush()
    deadline = time.time() + 30
    ready = []
    while time.time() < deadline and not ready:
        ready = [o for o in out.objects() if o.get("event") == "LibraryReady"]
        time.sleep(0.05)
    writer.write(json.dumps({"cmd": "shutdown", "id": 9}) + "\n")
    writer.flush()
    server.join(30)
    replies = {o["reply"]: o for o in out.objects() if "reply" in o}
    assert replies[7]["result"] == {"status": "started"}
    assert replies[8]["ok"] is False and "downloaded again" in replies[8]["error"]
    assert len(ready) == 1 and ready[0]["request"] == 7
    assert ready[0]["command"] == "library_scan"
    assert len(ready[0]["result"]["tiles"]) == 2
