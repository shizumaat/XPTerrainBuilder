"""The Qt Library window (#824), offscreen: the list populates from a
``library_scan`` result, sorts by size, filters by the search field, and
a tile built by another tool cannot be deleted or rebuilt.  No engine, no
network; the one real scan reads a synthetic folder in ``tmp_path``.
"""
import os
import sys
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest  # noqa: E402

pytest.importorskip("PySide6")

import O4_Qt_Library as QTLIB  # noqa: E402
from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def _row(tile, size, read_only=False, airports=(), packs=()):
    lat, lon = int(tile[:3]), int(tile[3:])
    return {"tile": tile, "lat": lat, "lon": lon, "build_dir": "/nowhere/" + tile,
            "size_bytes": size, "zl": 17, "provider": "BI", "built": 1.7e9,
            "airports": list(airports), "packs_modified": list(packs),
            "link_status": "not_installed", "in_xplane": False,
            "built_by": "other" if read_only else "XPTerrainBuilder",
            "read_only": read_only}


RESULT = {
    "tiles": [_row("+45-123", 2_000_000, airports=["KPDX"]),
              _row("+46-123", 9_000_000_000, read_only=True),
              _row("+47-122", 30_000,
                   packs=[{"pack_name": "KSEA Pack", "pack_path": "/p", "objects": 3}])],
    "tiles_bytes": 9_002_030_000,
    "caches": [{"kind": "imagery", "label": "Imagery", "path": "/i", "bytes": 1024,
                "redownload": "again"},
               {"kind": "elevation", "label": "Elevation", "path": "/e", "bytes": 0,
                "redownload": "again"},
               {"kind": "osm", "label": "Map data", "path": "/o", "bytes": 0,
                "redownload": "again"}],
}


def _dialog(**kw):
    dialog = QTLIB.LibraryDialog(None, "/tiles", "", **kw)
    dialog.set_library(RESULT)
    return dialog


def test_the_list_populates_and_sorts_by_size(app):
    dialog = _dialog()
    assert dialog.table.rowCount() == 3
    dialog.table.sortItems(QTLIB.SIZE_COLUMN, Qt.DescendingOrder)
    assert dialog.visible_tiles() == ["+46-123", "+45-123", "+47-122"]
    dialog.table.sortItems(QTLIB.SIZE_COLUMN, Qt.AscendingOrder)
    assert dialog.visible_tiles() == ["+47-122", "+45-123", "+46-123"]
    assert dialog.tiles_total_label.text() == "8.4 GB in 3 tiles"
    assert dialog.cache_labels["imagery"].text() == "1.0 KB"


def test_the_search_field_filters(app):
    dialog = _dialog()
    dialog.search_edit.setText("kpdx")
    assert dialog.visible_tiles() == ["+45-123"]
    dialog.search_edit.setText("")
    assert len(dialog.visible_tiles()) == 3


def test_another_tools_tile_is_never_deleted_or_rebuilt(app):
    dialog = _dialog(on_rebuild=lambda tiles: None)
    for i in range(dialog.table.rowCount()):
        if dialog._row_of(i)["read_only"]:
            dialog.table.selectRow(i)
    assert not dialog.delete_btn.isEnabled() and not dialog.rebuild_btn.isEnabled()
    assert dialog.install_btn.isEnabled()


def test_rebuild_and_restore_follow_the_selection(app):
    rebuilt = []
    dialog = _dialog(on_rebuild=rebuilt.append)
    dialog.table.selectAll()
    assert not dialog.delete_btn.isEnabled()        # one row is read-only
    dialog.table.clearSelection()
    for i in range(dialog.table.rowCount()):
        if dialog._row_of(i)["tile"] == "+47-122":
            dialog.table.selectRow(i)
    assert dialog.delete_btn.isEnabled() and dialog.restore_btn.isEnabled()
    dialog.rebuild_btn.click()
    assert rebuilt == [[(47, -122)]]


def test_delete_asks_first(app):
    dialog = _dialog()
    asked = []
    dialog.confirm = lambda title, text: asked.append(text) or False
    for i in range(dialog.table.rowCount()):
        if dialog._row_of(i)["tile"] == "+47-122":
            dialog.table.selectRow(i)
    dialog.delete_btn.click()
    assert len(asked) == 1 and "KSEA Pack" in asked[0]
    assert dialog.status_label.text() == ""


def test_a_real_scan_fills_the_window(app, tmp_path, monkeypatch):
    import O4_File_Names as FNAMES
    for name in ("Imagery_dir", "Elevation_dir", "OSM_dir", "Patch_dir"):
        monkeypatch.setattr(FNAMES, name, str(tmp_path / name))
    build = tmp_path / "Tiles" / "zOrtho4XP_+45-123" / "Earth nav data" / "+40-130"
    build.mkdir(parents=True)
    (build / "+45-123.dsf").write_bytes(b"x" * 10)
    dialog = QTLIB.LibraryDialog(None, str(tmp_path / "Tiles"), "")
    dialog.refresh()
    deadline = time.time() + 10
    while not dialog.rows and time.time() < deadline:
        app.processEvents()
        time.sleep(0.02)
    assert [r["tile"] for r in dialog.rows] == ["+45-123"]
    assert dialog.rows[0]["read_only"]
