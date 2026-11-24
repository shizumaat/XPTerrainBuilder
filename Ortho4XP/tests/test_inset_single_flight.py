"""Elevation insets and the download manager (#2258, round lrm1): one
inset pass per tile across processes, and a Stop heard during that wait,
an exportImage retry rest and the per-tile loops of the LERC and XYZ
strategies (census findings 3, 5, 9).  Headless; no network."""
from __future__ import annotations

import json
import os
import sys
import threading
import time

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import O4_Airport_Elevation_Insets as INSETS  # noqa: E402
import O4_Download_Manager as DOWNLOADS  # noqa: E402
import O4_File_Names as FNAMES  # noqa: E402
import O4_Machine_Slots as SLOTS  # noqa: E402
import O4_UI_Utils as UI  # noqa: E402
from elevation_access.base import TransientFetchError  # noqa: E402
from elevation_access.strategies import arcgis_export_image  # noqa: E402
from elevation_access.strategies import xyz_text_tiles  # noqa: E402


@pytest.fixture(autouse=True)
def _session(tmp_path, monkeypatch):
    (tmp_path / "slots").mkdir()
    monkeypatch.setenv(SLOTS.ENV_DIR, str(tmp_path / "slots"))
    monkeypatch.setenv(SLOTS.ENV_CAPACITY, "8")
    monkeypatch.setattr(FNAMES, "Elevation_dir", str(tmp_path / "elev"))
    UI.red_flag = False
    yield
    UI.red_flag = False


def _stop_in(seconds):
    timer = threading.Timer(seconds, lambda: setattr(UI, "red_flag", True))
    timer.start()
    return timer


def test_a_second_pass_waits_for_the_tile_s_flight_and_stops(monkeypatch):
    os.makedirs(FNAMES.airport_inset_directory(36, -87))
    with open(FNAMES.airport_inset_index(36, -87), "w", encoding="utf-8",
              newline="\n") as handle:
        json.dump({"KBNA": {"usgs3dep": "ok"}}, handle)
    monkeypatch.setattr(INSETS, "_ensure_airport_insets_held",
                        lambda *a, **k: pytest.fail("fetched"))
    with DOWNLOADS.hold_flight(INSETS._inset_pass_lock(36, -87)):
        _stop_in(0.3)
        started = time.monotonic()
        index = INSETS.ensure_airport_insets(
            36, -87, {"KBNA": (-86.7, 36.1, -86.6, 36.2)}, [], None)
    assert time.monotonic() - started < 2.0
    assert index == {"KBNA": {"usgs3dep": "ok"}}


def test_the_tile_s_pass_runs_under_its_flight(monkeypatch):
    seen = []

    def held(lat, lon, *_a, **_k):
        flight = SLOTS.try_os_lock(INSETS._inset_pass_lock(lat, lon))
        seen.append(flight is None)          # someone (we) holds it
        if flight is not None:
            SLOTS.release_os_lock(flight)
        return {}

    monkeypatch.setattr(INSETS, "_ensure_airport_insets_held", held)
    assert INSETS.ensure_airport_insets(
        36, -87, {"KBNA": (-86.7, 36.1, -86.6, 36.2)}, [], None) == {}
    assert not os.path.exists(INSETS._inset_pass_lock(36, -87))
    assert seen == [True]


def test_an_export_image_retry_rest_ends_at_stop(monkeypatch):
    monkeypatch.setattr(arcgis_export_image, "EXPORT_IMAGE_RETRY_DELAY_S",
                        30.0)
    _stop_in(0.3)
    started = time.monotonic()
    with pytest.raises(TransientFetchError):
        arcgis_export_image._rest_before_retry("TEST")
    assert time.monotonic() - started < 2.0


def test_the_xyz_tile_loop_ends_at_stop():
    class _Session:
        def get(self, *_a, **_k):
            pytest.fail("a tile was asked for after Stop")

    UI.red_flag = True
    strategy = xyz_text_tiles.XyzTextTileStrategy()
    with pytest.raises(TransientFetchError):
        strategy._mosaic_to_geotiff(_Session(), "https://t/{zoom}/{x}/{y}",
                                    12, (139.7, 35.6, 139.71, 35.61),
                                    "unused.tif")
