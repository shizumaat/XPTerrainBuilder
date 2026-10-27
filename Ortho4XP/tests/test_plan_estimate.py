"""The build-cost estimate before a build (#820): ``o4_engine.plan_estimate``.

Offline: the time store, the tile folder and the image cache are
``tmp_path`` folders; the free space is a stub.  The figures are ranges,
so the tests assert on relations (lo <= hi, half cached halves the
download, a need over the free space refuses), never on exact bytes.
"""

import io
import json
import os
import sys
import threading
import time

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from o4_engine import events as EV  # noqa: E402
from o4_engine import plan_estimate as PE  # noqa: E402
from o4_engine import session as SESSION  # noqa: E402
from o4_engine import tile_time_model as TTM  # noqa: E402

LAT, LON = 45, -123
TEXTURES = 40


@pytest.fixture
def world(tmp_path, monkeypatch):
    """A tile with history (TEXTURES textures at BI 16), an empty tile
    folder and an empty image cache, its terrain data already cached."""
    monkeypatch.setattr(TTM, "STORE_DIRECTORY", str(tmp_path / "times"))
    TTM.record_build(LAT, LON, TTM.features_for_record(
        zoomlevel=16, provider="BI", textures_total=TEXTURES,
        textures_missing=TEXTURES), {"vector": 60.0, "mesh": 90.0,
                                     "masks": 30.0, "imagery": 400.0})
    tile_dir = tmp_path / "tile"
    (tile_dir / "textures").mkdir(parents=True)
    cache = tmp_path / "cache"
    cache.mkdir()
    monkeypatch.setattr(PE, "_tile_settings",
                        lambda lat, lon, p, z, d: (None, "BI", 16))
    monkeypatch.setattr(SESSION, "_imagery_cache_directory",
                        lambda lat, lon, z, p: str(cache))
    monkeypatch.setattr(PE, "_terrain_data_cached", lambda lat, lon: True)
    monkeypatch.setattr(PE, "_throughput", lambda: None)
    monkeypatch.setattr(PE, "_free_bytes", lambda path: 500 * PE.GB)
    return {"tile": str(tile_dir), "cache": cache}


def _estimate(world, **kw):
    return PE.plan_estimate([(LAT, LON)], "BI", 16, world["tile"], **kw)


def _cache(world, count, size=6 * 1024 * 1024):
    for i in range(count):
        path = world["cache"] / ("%d_%d_BI16.jpg" % (i, i))
        path.write_bytes(b"\0" * 16)
        os.truncate(path, size)


def _ordered(pair):
    return len(pair) == 2 and pair[0] <= pair[1]


def test_every_figure_is_a_range_with_lo_at_most_hi(world):
    result = _estimate(world)
    row = result["tiles"][0]
    for key in ("download_gb", "disk_gb", "time_s"):
        assert _ordered(row[key]), (key, row[key])
        assert _ordered(result["total"][key]), (key, result["total"][key])
    assert row["time_s"][0] < row["time_s"][1], "a time is never a single number"
    assert row["textures"]["count"] == [TEXTURES, TEXTURES]
    assert result["verdict"] == "ok" and result["reason"] == ""
    assert result["free_gb"] == 500.0


def test_half_the_textures_cached_halves_the_download(world):
    cold = _estimate(world)["tiles"][0]
    _cache(world, TEXTURES // 2)
    warm = _estimate(world)["tiles"][0]
    assert warm["textures"]["to_download"] == [TEXTURES // 2, TEXTURES // 2]
    # The cold side prices from the constant, the warm from the measured
    # files: compare texture counts times the same per-texture bytes.
    per_texture = PE._bytes_per_texture([6 * 1024 * 1024], None)
    assert warm["download_gb"][0] == pytest.approx(
        round(TEXTURES // 2 * per_texture[0] / PE.GB, 2))
    assert cold["textures"]["to_download"][0] == 2 * warm["textures"]["to_download"][0]


def test_half_cached_halves_download_lo_at_one_price(world, monkeypatch):
    monkeypatch.setattr(PE, "_bytes_per_texture", lambda sizes, fallback: fallback)
    cold = _estimate(world)["tiles"][0]["download_gb"][0]
    _cache(world, TEXTURES // 2)
    warm = _estimate(world)["tiles"][0]["download_gb"][0]
    assert warm == pytest.approx(cold / 2, abs=0.01)


def test_converted_textures_are_neither_downloaded_nor_rewritten(world):
    textures = os.path.join(world["tile"], "textures")
    for i in range(TEXTURES):
        with open(os.path.join(textures, "%d_%d_BI16.dds" % (i, i)), "wb") as f:
            f.write(b"\0")
    row = _estimate(world)["tiles"][0]
    assert row["textures"]["to_download"] == [0, 0]
    assert row["download_gb"] == [0.0, 0.0]


def test_a_tile_with_no_history_counts_the_texture_grid(world, monkeypatch):
    monkeypatch.setattr(TTM, "STORE_DIRECTORY", str(world["cache"] / "none"))
    row = _estimate(world)["tiles"][0]
    grid = PE.texture_grid_count(LAT, LON, 16)
    assert row["textures"]["count"] == [int(round(PE.UNKNOWN_COVERAGE_FLOOR * grid)), grid]
    assert row["has_history"] is False


def test_the_grid_grows_four_times_a_zoom_level():
    for zl in (15, 16, 17):
        ratio = PE.texture_grid_count(LAT, LON, zl + 1) / PE.texture_grid_count(LAT, LON, zl)
        assert 3.0 < ratio < 4.5


def test_uncached_terrain_data_adds_a_download(world, monkeypatch):
    base = _estimate(world)["tiles"][0]["download_gb"]
    monkeypatch.setattr(PE, "_terrain_data_cached", lambda lat, lon: False)
    more = _estimate(world)["tiles"][0]["download_gb"]
    assert more[0] > base[0] and more[1] > base[1]
    only_imagery = _estimate(world, do_vector=False)["tiles"][0]["download_gb"]
    assert only_imagery == base


def test_disk_need_over_free_space_refuses_with_the_reason(world, monkeypatch):
    need = _estimate(world)["total"]["disk_gb"]
    monkeypatch.setattr(PE, "_free_bytes", lambda path: need[0] * PE.GB / 2)
    result = _estimate(world)
    assert result["verdict"] == "refuse"
    assert "needs at least" in result["reason"] and "GB free" in result["reason"]


def test_free_space_between_lo_and_hi_warns(world, monkeypatch):
    need = _estimate(world)["total"]["disk_gb"]
    monkeypatch.setattr(PE, "_free_bytes",
                        lambda path: (need[0] + need[1]) / 2 * PE.GB)
    result = _estimate(world)
    assert result["verdict"] == "warn" and "may need up to" in result["reason"]


def test_totals_sum_the_tiles(world):
    result = PE.plan_estimate([(LAT, LON), (LAT, LON + 1)], "BI", 16,
                              world["tile"] + "/")
    assert len(result["tiles"]) == 2
    for key in ("download_gb", "disk_gb"):
        for side in (0, 1):
            assert result["total"][key][side] == pytest.approx(
                sum(r[key][side] for r in result["tiles"]), abs=0.02)


def test_no_steps_costs_nothing(world):
    row = _estimate(world, do_vector=False, do_imagery=False)["tiles"][0]
    assert row["download_gb"] == [0.0, 0.0] and row["time_s"] == [0, 0]


def test_the_command_round_trips_through_the_jsonl_transport(world):
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
    stdin, writer = os.fdopen(r_fd, "r", encoding="utf-8"), os.fdopen(w_fd, "w", encoding="utf-8")
    out = Capture()
    server = threading.Thread(target=jsonl.serve, args=(stdin, out), daemon=True)
    server.start()
    writer.write(json.dumps({
        "cmd": "plan_estimate", "id": 7, "tiles": [[LAT, LON]], "provider": "BI",
        "zoomlevel": 16, "custom_build_dir": world["tile"],
        "do_vector": True, "do_imagery": True, "do_overlays": False}) + "\n")
    writer.flush()
    deadline = time.time() + 30
    ready = []
    while time.time() < deadline and not ready:
        ready = [o for o in out.objects() if o.get("event") == "PlanEstimateReady"]
        time.sleep(0.05)
    writer.write(json.dumps({"cmd": "shutdown", "id": 8}) + "\n")
    writer.flush()
    server.join(30)
    objects = out.objects()
    assert objects[0]["protocol"] == EV.PROTOCOL_VERSION
    assert tuple(int(p) for p in EV.PROTOCOL_VERSION.split(".")) >= (1, 15)
    replies = {o["reply"]: o for o in objects if "reply" in o}
    assert replies[7] == {"reply": 7, "ok": True, "result": {"status": "started"}}
    assert len(ready) == 1 and ready[0]["request"] == 7 and ready[0]["error"] == ""
    result = ready[0]["result"]
    assert set(result) == {"tiles", "total", "free_gb", "cache_free_gb", "verdict", "reason"}
    assert set(result["tiles"][0]) >= {"lat", "lon", "download_gb", "disk_gb", "time_s"}
    assert [result["tiles"][0]["lat"], result["tiles"][0]["lon"]] == [LAT, LON]


def test_a_failure_completes_with_the_error(monkeypatch):
    events = []
    monkeypatch.setattr(PE, "plan_estimate",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    assert PE.start_plan_estimate(events.append, [(LAT, LON)], request=3) == {
        "status": "started"}
    deadline = time.time() + 10
    while not events and time.time() < deadline:
        time.sleep(0.01)
    assert events[0].request == 3 and events[0].error == "boom" and events[0].result is None


def test_answers_within_a_second(world):
    start = time.perf_counter()
    PE.plan_estimate([(LAT, LON + i) for i in range(4)], "BI", 16, world["tile"] + "/")
    assert time.perf_counter() - start < 1.0

