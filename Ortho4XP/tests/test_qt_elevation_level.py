"""Headless tests for the build-area elevation detail level selectors.

Verifies the Qt surface of ``docs/specs/elevation-level-spec.md``:
- a ``Tile elevation:`` label + combo box live in the build area directly
  after the texture-mode row, with an ``Airport elevation:`` combo right
  after it;
- the tile combo shows the seven levels in order and defaults to ``Auto``;
- selecting ``10 m`` round-trips ``elevation_level="10"`` into the
  active tile's config file and reads back on reload;
- the airport combo shows the six options in order, defaults to ``Auto``,
  and selecting ``5 m`` round-trips ``airport_elevation_level=5``;
- both config values also render as combos in the settings model
  (enumerated values + labels).

All offscreen (``QT_QPA_PLATFORM=offscreen``), no network, no X-Plane
install.  Mirrors ``tests/test_qt_texture_mode.py``.
"""

import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

import O4_Qt_GUI as GUI  # noqa: E402
import O4_Settings_Model as SM  # noqa: E402


def test_modules_resolve_to_this_worktree():
    """Guard against sys.path/conftest leakage from another checkout."""
    here = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    for module in (GUI, SM):
        assert os.path.abspath(module.__file__).startswith(here), (
            "%s resolved to %s, not this worktree" % (module, module.__file__)
        )


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def window(qapp, tmp_path, monkeypatch):
    # Isolate the prefs file BEFORE construction: MainWindow loads the
    # prefs in __init__ and closeEvent SAVES them — without this patch,
    # closing a test window clobbers the user's real .qt_prefs.json with
    # the pytest temp output_dir (which is exactly what once broke the
    # tile scan of a real install).
    monkeypatch.setattr(GUI, "PREFS_FILE", str(tmp_path / "prefs.json"))
    saved_stdout = sys.stdout
    win = GUI.MainWindow()
    win.prefs["output_dir"] = str(tmp_path)
    try:
        yield win
    finally:
        win.close()
        win.deleteLater()
        sys.stdout = saved_stdout


def test_elevation_row_sits_after_texture_row(window):
    layout = window.chk_skip_built.parentWidget().layout()
    texture_index = layout.indexOf(window.texture_row)
    elevation_index = layout.indexOf(window.elevation_row)
    airport_index = layout.indexOf(window.airport_elevation_row)
    button_index = layout.indexOf(window.build_btn)
    # The airport-elevation row sits directly after the tile-elevation row.
    assert texture_index < elevation_index < airport_index < button_index
    assert airport_index == elevation_index + 1
    assert window.elevation_label.text() == "Tile elevation:"
    assert window.elevation_combo.toolTip()


def test_combo_shows_seven_levels_in_order(window):
    combo = window.elevation_combo
    assert combo.count() == 7
    assert [combo.itemText(i) for i in range(7)] == [
        "Auto", "Auto + coastline", "90 m", "30 m", "10 m", "5 m", "1 m",
    ]
    assert [combo.itemData(i) for i in range(7)] == [
        "auto", "coastline", "90", "30", "10", "5", "1",
    ]


def test_airport_combo_shows_six_options_in_order(window):
    combo = window.airport_elevation_combo
    assert combo.count() == 6
    assert [combo.itemText(i) for i in range(6)] == [
        "Auto", "0.5 m", "1 m", "5 m", "10 m", "30 m",
    ]
    assert [combo.itemData(i) for i in range(6)] == [
        "auto", "0.5", "1", "5", "10", "30",
    ]


def test_defaults_to_auto(window):
    window.map.set_active(48, -6)
    assert window.elevation_combo.currentData() == "auto"


def test_airport_defaults_to_auto(window):
    window.map.set_active(48, -6)
    assert window.airport_elevation_combo.currentData() == "auto"


def test_selecting_ten_metres_round_trips(window, tmp_path):
    lat, lon = 48, -6
    window.map.set_active(lat, lon)

    index = window.elevation_combo.findData("10")
    assert index >= 0
    window.elevation_combo.setCurrentIndex(index)

    raw = SM.read_tile_raw(lat, lon, window.output_dir())
    assert raw is not None, "selecting a level must create the tile config"
    assert raw.get("elevation_level") == "10"

    # Reload: knock the combo off, then re-read from disk.
    window.elevation_combo.blockSignals(True)
    window.elevation_combo.setCurrentIndex(0)
    window.elevation_combo.blockSignals(False)
    window._refresh_elevation_level((lat, lon))
    assert window.elevation_combo.currentData() == "10"


def test_selecting_five_metres_airport_round_trips(window, tmp_path):
    lat, lon = 48, -6
    window.map.set_active(lat, lon)

    index = window.airport_elevation_combo.findData("5")
    assert index >= 0
    window.airport_elevation_combo.setCurrentIndex(index)

    raw = SM.read_tile_raw(lat, lon, window.output_dir())
    assert raw is not None, "selecting a level must create the tile config"
    assert raw.get("airport_elevation_level") == "5"

    # Reload: knock the combo off, then re-read from disk.
    window.airport_elevation_combo.blockSignals(True)
    window.airport_elevation_combo.setCurrentIndex(0)
    window.airport_elevation_combo.blockSignals(False)
    window._refresh_airport_elevation_level((lat, lon))
    assert window.airport_elevation_combo.currentData() == "5"


def test_no_active_tile_write_is_noop(window):
    original = window.map.active_tile
    window.map.active_tile = lambda: None
    try:
        window._elevation_level_changed(2)  # must not raise
    finally:
        window.map.active_tile = original


def test_no_active_tile_airport_write_is_noop(window):
    original = window.map.active_tile
    window.map.active_tile = lambda: None
    try:
        window._airport_elevation_level_changed(2)  # must not raise
    finally:
        window.map.active_tile = original


def test_settings_model_renders_enumerated_combo():
    setting = SM.get_setting("elevation_level")
    assert setting is not None
    assert setting.scope == "tile"
    assert setting.category == "elevation"
    assert setting.values == (
        "auto", "coastline", "90", "30", "10", "5", "1",
    )
    assert setting.label_for("auto").startswith("Auto")
    assert setting.label_for("90").startswith("90 m")
    assert setting.label_for("1").startswith("1 m")


def test_settings_model_renders_airport_enumerated_combo():
    setting = SM.get_setting("airport_elevation_level")
    assert setting is not None
    assert setting.scope == "tile"
    assert setting.category == "elevation"
    assert setting.values == ("auto", "0.5", "1", "5", "10", "30")
    assert setting.label_for("auto").startswith("Auto")
    assert setting.label_for("0.5").startswith("0.5 m")
