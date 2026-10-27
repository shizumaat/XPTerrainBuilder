"""The Qt tile pane's missing-textures row (O4_Qt_Missing_Textures) on a
synthetic tile folder.  Offscreen, no engine, no network."""
import os
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402

pytest.importorskip("PySide6")

from test_tile_texture_check import _TERRAIN, _tile  # noqa: E402

TILE = (-42, 175)


@pytest.fixture(scope="module")
def qapp():
    from PySide6.QtWidgets import QApplication
    yield QApplication.instance() or QApplication([])


def _settle(qapp, seconds=2.0):
    deadline = time.time() + seconds
    while time.time() < deadline:
        qapp.processEvents()
        time.sleep(0.02)


def _row(qapp):
    import O4_Qt_Missing_Textures as QTMISSING
    row = QTMISSING.MissingTexturesRow()
    row.show()
    return row


def test_a_tile_missing_textures_shows_the_warning_and_rebuilds(
        qapp, tmp_path):
    row = _row(qapp)
    asked = []
    row.rebuild_requested.connect(asked.append)
    row.check(TILE, _tile(tmp_path, _TERRAIN, []))
    _settle(qapp)
    assert row.isVisible()
    assert row.label.text() == ("⚠ 2 textures missing — X-Plane cannot "
                                "load this tile")
    assert "163856_259008_Arc18.dds" in row.label.toolTip()
    row.rebuild_button.click()
    assert asked == [TILE]


def test_a_whole_tile_shows_nothing(qapp, tmp_path):
    row = _row(qapp)
    row.check(TILE, _tile(tmp_path, _TERRAIN, ["163856_259008_Arc18.dds",
                                               "163872_259024_Arc16.dds"]))
    _settle(qapp)
    assert not row.isVisible()


def test_a_late_answer_for_another_tile_is_dropped(qapp, tmp_path):
    row = _row(qapp)
    row.check(TILE, _tile(tmp_path, _TERRAIN, []))
    row.clear()
    _settle(qapp)
    assert not row.isVisible()


def test_the_window_shows_the_row_for_a_symlinked_tile(
        qapp, tmp_path, monkeypatch):
    """#1563 on the Qt side: the WINDOW's path — the active tile's scanned
    folder, a symlink into a scenery library — reaches the row."""
    import json
    import sys

    import O4_Qt_GUI as GUI
    import O4_Qt_Map as QTMAP
    import O4_Tile_Info as TINFO
    import O4_UI_Utils as UI
    from test_tile_texture_check import _linked_tile

    scenery, link = _linked_tile(tmp_path)
    prefs = tmp_path / "prefs.json"
    prefs.write_text(json.dumps({"output_dir": str(tmp_path)}),
                     encoding="utf-8", newline="")
    monkeypatch.setattr(GUI, "PREFS_FILE", str(prefs))
    monkeypatch.setattr(
        GUI, "TILE_SCAN_CACHE_FILE", str(tmp_path / "tile-scan.json"))
    # The settle below would let the map fetch its base tiles (#122).
    monkeypatch.setattr(QTMAP.MapView, "_start_workers", lambda self: None)
    saved_stdout = sys.stdout
    win = GUI.MainWindow()
    monkeypatch.setattr(win, "refresh_tiles", lambda: None)
    monkeypatch.setattr(win, "_refresh_scenery_packs", lambda: None)
    try:
        win._built.update(TINFO.scan_tiles(scenery))
        win._active_changed((47, -113))
        _settle(qapp)
        row = win.missing_textures_row
        assert not row.isHidden()
        assert row.label.text().startswith("⚠ 2 textures missing")
    finally:
        win._building = False
        win.close()
        win.deleteLater()
        UI.engine_session = None
        sys.stdout = saved_stdout
