"""Twins for #622: the imagery download gets its real share of the bar,
priced from the measured download rate, and the imagery step says
whether it is downloading or reusing cached imagery.

Headless: the time-model store and every folder live in ``tmp_path``.
"""

import os
import sys
import types

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest  # noqa: E402

import O4_Imagery_Progress as IMGPROGRESS  # noqa: E402
from o4_engine import session as SESSION  # noqa: E402
from o4_engine import tile_time_model as model  # noqa: E402


@pytest.fixture
def store(tmp_path, monkeypatch):
    directory = tmp_path / "tile_build_times"
    monkeypatch.setattr(model, "STORE_DIRECTORY", str(directory))
    return directory


def _record(lat, lon, step_seconds, **features):
    base = dict(zoomlevel=16, provider="BI", textures_total=0,
                textures_missing=0)
    base.update(features)
    model.record_build(lat, lon, base, step_seconds)


def _folder(tmp_path, name, files):
    folder = tmp_path / name
    folder.mkdir()
    for file_name in files:
        (folder / file_name).touch()
    return str(folder)


def test_warm_history_does_not_price_a_cold_build_as_warm(store, tmp_path):
    """THE MECHANISM: three cached rebuilds of the tile (30 s imagery)
    used to be the imagery estimate of a build whose textures are all
    gone — the bar gave imagery ~10 % and read ~90 % when the downloads
    began.  Priced from the download count it takes the bulk."""
    for _ in range(3):
        _record(25, 51, {"imagery": 30.0}, textures_total=184)
        _record(25, 51, {"vector": 60.0, "mesh": 250.0, "masks": 30.0})
    features = {"zoomlevel": 16, "provider": "BI"}
    features.update(model.estimate_texture_features(
        25, 51, 16, "BI", _folder(tmp_path, "textures", []),
        jpeg_directory=_folder(tmp_path, "jpegs", [])))
    assert features["textures_to_download"] == 184
    steps = ["vector", "mesh", "masks", "imagery"]
    estimates = model.predict_step_seconds(25, 51, features, steps)
    assert estimates["imagery"] == pytest.approx(
        30.0 + 184 * model.DEFAULT_SECONDS_PER_DOWNLOADED_TEXTURE)
    assert features["textures_missing"] == 184
    plan = SESSION.reweight_plan_by_seconds(
        SESSION.plan_steps(True, True, False), estimates)
    imagery = [p for p in plan if p[0] == "imagery"][0]
    assert imagery[1] < 0.35            # the bar is a third done at most
    # ...where the old same-tile median priced it at 30 s:
    old = dict(features)
    old.pop("textures_to_download")
    assert model.predict_step_seconds(25, 51, old, ["imagery"])[
        "imagery"] == pytest.approx(30.0)


def test_cached_imagery_is_not_priced_as_a_download(store, tmp_path):
    _record(25, 51, {"imagery": 30.0}, textures_total=184)
    jpegs = ["%d_1_BI16.jpg" % index for index in range(184)]
    features = {"zoomlevel": 16, "provider": "BI"}
    features.update(model.estimate_texture_features(
        25, 51, 16, "BI", _folder(tmp_path, "textures", []),
        jpeg_directory=_folder(tmp_path, "jpegs", jpegs)))
    assert features == {"zoomlevel": 16, "provider": "BI",
                        "textures_total": 184, "textures_missing": 184,
                        "textures_to_download": 0}
    assert model.predict_step_seconds(25, 51, features, ["imagery"])[
        "imagery"] == pytest.approx(
            30.0 + 184 * model.DEFAULT_SECONDS_PER_CONVERTED_TEXTURE)


def test_the_measured_download_rate_prices_the_download(store):
    # Another tile measured 2 s per downloaded texture with this source.
    _record(10, 10, {"imagery": 500.0}, textures_total=200,
            textures_missing=200, textures_downloaded=200,
            download_seconds=400.0)
    features = {"zoomlevel": 16, "provider": "BI", "textures_total": 100,
                "textures_missing": 100, "textures_to_download": 100}
    seconds = model.predict_step_seconds(25, 51, features, ["imagery"])
    # Nothing isolates the local work (the one record downloaded), so it
    # is the constant; the download is 100 textures x the measured 2 s.
    assert seconds["imagery"] == pytest.approx(
        model.DEFAULT_IMAGERY_LOCAL_SECONDS + 100 * 2.0)


def test_a_tile_never_built_at_this_zoom_borrows_a_texture_count(store,
                                                                tmp_path):
    """Another source at the same zoom, then every tile at that zoom:
    never zero (zero priced the step as free)."""
    _record(25, 51, {"imagery": 900.0}, provider="GO2", textures_total=150)
    estimate = model.estimate_texture_features(
        25, 51, 16, "BI", _folder(tmp_path, "t1", []))
    assert estimate["textures_total"] == 150
    _record(1, 1, {"imagery": 900.0}, textures_total=300)
    _record(2, 2, {"imagery": 900.0}, textures_total=100)
    _record(3, 3, {"imagery": 900.0}, textures_total=200)
    estimate = model.estimate_texture_features(
        40, 40, 16, "BI", _folder(tmp_path, "t2", []))
    assert estimate["textures_total"] == 175     # median of 100..300


def test_no_texture_count_at_all_is_not_free(store):
    _record(1, 1, {"imagery": 700.0}, textures_total=100, textures_missing=100)
    _record(2, 2, {"imagery": 70.0}, textures_total=100)
    features = {"zoomlevel": 18, "provider": "BI", "textures_total": 0,
                "textures_missing": 0}
    assert model.predict_step_seconds(40, 40, features, ["imagery"])[
        "imagery"] == model.DEFAULT_STEP_SECONDS["imagery"]


def test_default_textures_predict_no_download(store, monkeypatch, tmp_path):
    config = types.ModuleType("O4_Config_Utils")

    class _Tile:
        def __init__(self, lat, lon, build_dir):
            self.lat, self.lon, self.build_dir = lat, lon, str(tmp_path)
            self.texture_mode = "default_xplane"

        def read_from_config(self):
            return True

    config.Tile = _Tile
    monkeypatch.setitem(sys.modules, "O4_Config_Utils", config)
    features = SESSION.prediction_features(25, 51, "BI", 16, str(tmp_path))
    assert features["textures_to_download"] == 0


def test_the_label_says_downloading_or_reusing():
    tile = types.SimpleNamespace()
    IMGPROGRESS.begin(tile)
    assert IMGPROGRESS.label(tile, 3, 184) == (
        "reusing cached imagery · 3 of 184 textures")
    tile.imagery_downloads = 12
    tile.imagery_first_download_at = 100.0
    assert IMGPROGRESS.label(tile, 20, 184, now=160.0) == (
        "downloading imagery · 20 of 184 textures, 12 downloaded "
        "(12.0/min)")
    assert IMGPROGRESS.finish(tile).startswith("converting textures · 12")
    assert tile.imagery_download_seconds > 0


def test_a_download_is_counted_on_its_tile():
    import O4_Imagery_Utils as IMG
    tile = types.SimpleNamespace()
    IMGPROGRESS.begin(tile)
    IMG.note_orthophoto_download(tile)
    IMG.note_orthophoto_download(tile)
    assert tile.imagery_downloads == 2
    assert tile.imagery_first_download_at is not None
