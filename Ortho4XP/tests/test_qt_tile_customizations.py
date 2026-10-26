"""The Qt badge, tile pane and Settings shortcut for a tile's customized
settings (#1350).  Offscreen (``QT_QPA_PLATFORM=offscreen``), no network,
no engine: the window driven through its own handlers."""
import json
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402

pytest.importorskip("PySide6")

import O4_Settings_Model as SM  # noqa: E402
import O4_Tile_Customizations as TC  # noqa: E402
from test_tile_customizations import _write_tile, make_data  # noqa: E402


@pytest.fixture
def tiles_dir(tmp_path, monkeypatch):
    return make_data(tmp_path, monkeypatch)


@pytest.fixture
def window(tiles_dir, tmp_path, monkeypatch):
    """The Qt window, offscreen, its prefs isolated and its tiles folder
    the fixture's (the seam of ``test_qt_mac_parity``)."""
    import O4_Qt_GUI as GUI
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    prefs_path = str(tmp_path / "prefs.json")
    with open(prefs_path, "w", encoding="utf-8", newline="") as handle:
        json.dump({"output_dir": tiles_dir + "/"}, handle)
    monkeypatch.setattr(GUI, "PREFS_FILE", prefs_path)
    monkeypatch.setattr(
        GUI, "TILE_SCAN_CACHE_FILE", str(tmp_path / "tile-scan.json"))
    saved_stdout = sys.stdout
    win = GUI.MainWindow()
    monkeypatch.setattr(win, "refresh_tiles", lambda: None)
    monkeypatch.setattr(win, "_refresh_scenery_packs", lambda: None)
    try:
        yield win
    finally:
        win._building = False
        win.close()
        sys.stdout = saved_stdout


def _badges_drawn(tile_map, monkeypatch):
    """The tiles a repaint draws the settings badge on."""
    drawn = []
    monkeypatch.setattr(tile_map, "_draw_settings_badge",
                        lambda painter, r, px, scale: drawn.append(r))
    tile_map.grab()
    return len(drawn)


def test_qt_badge_pane_and_clearing(window, tiles_dir, monkeypatch):
    import O4_Tile_Info as TINFO
    tile = (45, 5)
    folder = os.path.dirname(_write_tile(tiles_dir, ["road_level=5",
                                                "approach_rings=off"]))
    window._built = {tile: TINFO.TileInfo(
        lat=45, lon=5, build_dir=folder, dir_name=os.path.basename(folder),
        dsf_present=True, provider="BI", zl=16)}
    window.map.set_built(window._built)
    window.map.resize(600, 600)
    window.map.center_on_tile(45, 5, zoom=7)
    window._refresh_customized_tiles()
    assert window.map.customized() == {tile}
    assert _badges_drawn(window.map, monkeypatch) == 1

    window._refresh_custom_settings(tile)
    texts = [label.text() for label in window._custom_settings_labels]
    rows = TC.tile_customizations(45, 5, tiles_dir)["customizations"]
    assert texts == [TC.row_text(row) for row in rows] and len(texts) == 2
    road = next(row for row in rows if row["key"] == "road_level")
    assert TC.row_text(road) == "%s %s: %s (default %s)" % (
        TC.GROUND_MARK, road["label"].rstrip("?"),
        TC.display_value("road_level", "5"),
        TC.display_value("road_level", "4"))
    assert window._info_layout.isRowVisible(window.custom_settings_row)

    # Clearing the overrides (what Settings' reset writes) drops the badge.
    SM.write_tile(45, 5, tiles_dir + "/", {"road_level": "4",
                                      "approach_rings": "auto"})
    window._refresh_customized_tiles()
    assert window.map.customized() == set()
    assert _badges_drawn(window.map, monkeypatch) == 0
    window._refresh_custom_settings(tile)
    assert window._custom_settings_labels == []
    assert not window._info_layout.isRowVisible(window.custom_settings_row)


def test_edit_settings_opens_the_tile_with_its_customized_rows(
        window, tiles_dir, monkeypatch):
    import O4_Qt_GUI as GUI
    _write_tile(tiles_dir, ["road_level=5"])
    opened = {}

    class Dialog:
        tile_written = False

        def __init__(self, prefs, tiles, custom_build_dir, parent):
            opened["tiles"] = tiles
            self._prefs = prefs

        def show_customized_only(self):
            opened["customized_only"] = True

        def restoreGeometry(self, *_):
            pass

        def exec(self):
            pass

        def result_prefs(self):
            return self._prefs

        def saveGeometry(self):
            from PySide6.QtCore import QByteArray
            return QByteArray()

    monkeypatch.setattr(GUI.QTSET, "SettingsWindow", Dialog)
    monkeypatch.setattr(GUI, "save_prefs", lambda prefs: None)
    window._refresh_custom_settings((45, 5))
    window.edit_tile_settings_btn.click()
    assert opened == {"tiles": [(45, 5)], "customized_only": True}


def test_qt_settings_window_opens_filtered(window, tiles_dir):
    import O4_Qt_Settings as QTSET
    _write_tile(tiles_dir, ["road_level=5"])
    dialog = QTSET.SettingsWindow({}, [(45, 5)], tiles_dir + "/", window)
    dialog.show_customized_only()
    assert dialog.customized_chip.isChecked()
    shown = {name for name, row in dialog.rows.items() if not row.isHidden()}
    assert shown == {"road_level"}


def test_mac_app_names_the_same_section():
    """Two UIs, one layout (#1244): the Mac tile pane carries the same
    section and button words as the Qt one."""
    import O4_Qt_GUI as GUI
    swift = os.path.join(os.path.dirname(__file__), "..", "..", "Sources",
                         "XPTerrainBuilder", "BuildPane.swift")
    with open(swift, encoding="utf-8") as handle:
        text = handle.read()
    assert '"%s"' % GUI.CUSTOM_SETTINGS in text
    assert '"%s"' % GUI.EDIT_TILE_SETTINGS in text
