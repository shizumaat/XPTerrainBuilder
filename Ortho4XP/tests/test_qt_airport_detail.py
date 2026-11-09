"""The Qt Settings window's Detail choice and Imagery zoom (#1985).

Detail sits under the preset cards; choosing one writes its keys (and,
for ICAO or All, the zoom) like a preset; a row edit afterwards shows
Custom; with a tile selected it applies to the tile.  The build zoom's
combo lives in the Imagery category.

Offscreen (QT_QPA_PLATFORM=offscreen), tmp_path cwd, no network.
"""

from __future__ import annotations

import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest  # noqa: E402

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

import O4_Airport_Detail as DETAIL  # noqa: E402
import O4_Qt_Airport_Detail as QTDETAIL  # noqa: E402
import O4_Settings_Model as SM  # noqa: E402
from O4_Qt_Settings import SettingsWindow  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    yield QApplication.instance() or QApplication([])


@pytest.fixture
def window(qapp, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    win = SettingsWindow(prefs={}, tiles=[], custom_build_dir="")
    yield win
    win.close()


def _choose(window, key):
    combo = window.airport_detail_row.combo
    combo.activated.emit(combo.findData(key))


def test_engine_defaults_show_custom(window):
    assert window.airport_detail_row.current_key() == QTDETAIL.CUSTOM_KEY


def test_choosing_all_writes_every_airport_key_and_the_zoom(window):
    _choose(window, "all")
    raw = SM.read_global_raw()
    for name, value in DETAIL.values("all").items():
        assert SM.values_equivalent(name, raw[name], value), name
        assert SM.values_equivalent(name, window.rows[name].value(), value)
    assert window.result_prefs()["zl"] == 16
    assert window.airport_detail_row.current_key() == "all"
    assert window.airport_detail_row.combo.findData(QTDETAIL.CUSTOM_KEY) < 0


def test_sharper_airports_is_detail_icao_and_a_row_edit_is_custom(window):
    window.preset_cards.buttons["sharper_airports"].click()
    assert window.airport_detail_row.current_key() == "icao"
    row = window.rows["bathymetry_near_other_airports"]
    row.set_value("True")
    window._row_committed(row)
    assert window.airport_detail_row.current_key() == QTDETAIL.CUSTOM_KEY
    window.preset_cards.buttons["balanced"].click()
    assert window.airport_detail_row.current_key() == "none"


def test_none_keeps_the_zoom(window):
    window.prefs["zl"] = 17
    _choose(window, "none")
    assert window.result_prefs()["zl"] == 17
    assert SM.read_global_raw()["auto_patch"] == "None"


def test_detail_with_a_tile_selected_applies_to_the_tile(
        qapp, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    build_dir = str(tmp_path) + "/"
    win = SettingsWindow(prefs={}, tiles=[(48, -6)],
                         custom_build_dir=build_dir)
    try:
        _choose(win, "all")
        raw = SM.read_tile_raw(48, -6, build_dir)
        assert raw["auto_patch"] == "All"
        assert raw["cover_airports_with_highres"] == "True"
        assert "auto_patch" not in SM.read_global_raw()
        assert (win.zoom_target, win.selection_zl) == ("tiles", 16)
        assert win.airport_detail_row.current_key() == "all"
    finally:
        win.close()


def test_the_zoom_lives_in_imagery(window):
    assert window.detail_combo is window.imagery_zoom_row.combo
    window.category_list.setCurrentRow(
        [key for key, _t in SM.CATEGORIES].index("imagery"))
    assert window.imagery_zoom_row.isVisibleTo(window)
    window.category_list.setCurrentRow(
        [key for key, _t in SM.CATEGORIES].index("network"))
    assert not window.imagery_zoom_row.isVisibleTo(window)
