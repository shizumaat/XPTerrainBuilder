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


def _select(dialog, tile):
    dialog.table.clearSelection()
    for i in range(dialog.table.rowCount()):
        if dialog._row_of(i)["tile"] == tile:
            dialog.table.selectRow(i)


def _settle(app, dialog, before):
    deadline = time.time() + 10
    while dialog.status_label.text() == before and time.time() < deadline:
        app.processEvents()
        time.sleep(0.02)


def test_export_and_import_library_bundle_call_the_engine(app, monkeypatch):
    """#1699 phase 1: the two buttons the Mac app's Library has too —
    export one tile of this app's into a chosen folder, import a chosen
    bundle into the tiles folder."""
    calls = []
    monkeypatch.setattr(QTLIB.LIB, "library_export_bundle", lambda lat, lon, wd, out: (
        calls.append(("export", lat, lon, wd, out)) or {"bytes": 2048}))
    monkeypatch.setattr(QTLIB.LIB, "library_import_bundle", lambda path, wd: (
        calls.append(("import", path, wd)) or {"tile": "+45-123"}))
    dialog = _dialog()
    dialog.refresh = lambda: None                     # no real scan after
    _select(dialog, "+46-123")
    assert not dialog.export_btn.isEnabled()          # another tool's tile
    dialog.table.selectAll()
    assert not dialog.export_btn.isEnabled()          # one tile at a time
    _select(dialog, "+45-123")
    assert dialog.export_btn.isEnabled() and dialog.import_btn.isEnabled()
    dialog.choose_folder = lambda title: "/out"
    dialog.export_btn.click()
    _settle(app, dialog, "Exporting +45-123…")
    assert calls[-1] == ("export", 45, -123, "/tiles", "/out")
    assert "Exported +45-123 (2.0 KB)" in dialog.status_label.text()
    dialog.choose_bundle = lambda title: "/b/XPTerrainBuilder_+45-123.xptbundle"
    dialog.import_btn.click()
    _settle(app, dialog, "Importing…")
    assert calls[-1] == ("import", "/b/XPTerrainBuilder_+45-123.xptbundle", "/tiles")
    dialog.choose_bundle = lambda title: ""             # cancelled: nothing runs
    dialog.import_btn.click()
    assert len(calls) == 2


def test_no_bundle_while_a_build_runs(app):
    dialog = _dialog(building=lambda: True)
    _select(dialog, "+45-123")
    assert not dialog.export_btn.isEnabled() and not dialog.import_btn.isEnabled()


CHECK = {"configured": True, "checked": "", "regions": ["+40-130"], "rows": [
    {"icao": "KPDX", "tile": "+45-123", "state": "newer", "pack": "KPDX Pack",
     "entry_pack": "KPDX Pack", "version": 2, "local_version": 1,
     "entry": "entries/KPDX/KPDX Pack/0123456789ab/v2", "signature": "a" * 32,
     "verified": True, "publisher": "dev", "solved_usable": True, "reason": "",
     "warning": ""},
    {"icao": "KHIO", "tile": "+45-123", "state": "pack_changed", "pack": "P",
     "entry_pack": "P", "version": 1, "local_version": 1, "entry": "entries/KHIO/P/0123456789ab/v1",
     "signature": "b" * 32, "verified": False, "publisher": "pilot",
     "solved_usable": False, "reason": "x", "warning": ""}]}


def test_the_patch_library_box_lists_the_check_and_applies(app, monkeypatch):
    """#1699 phase 2: the Library's "Patch library" box (the Mac app's
    ``PatchLibrarySection``): one row per airport, Update lays the entry
    down through ``library_apply``."""
    import O4_Qt_Patch_Library as PATCHLIB
    calls = []

    def fake(name):
        def run(**kw):
            calls.append((name, kw))
            if name == "library_apply":
                return {"icao": "KPDX", "tile": "+45-123", "version": 2, "mode": "solved",
                        "reason": "", "edits": "none", "files": 6, "warning": ""}
            return {"configured": False, "rows": []}
        return run
    monkeypatch.setattr(PATCHLIB, "command", fake)
    dialog = _dialog()
    dialog.patch_box.set_check(CHECK)
    first, second = dialog.patch_box.row_widgets
    assert set(first.buttons) == {"Update", "Ignore"}
    assert set(second.buttons) == {"Ignore"}            # the next build re-solves
    first.buttons["Update"].click()
    deadline = time.time() + 10
    while [n for n, _kw in calls][-1:] != ["library_check"] and time.time() < deadline:
        app.processEvents()
        time.sleep(0.02)
    assert [n for n, _kw in calls] == ["library_apply", "library_check"]
    assert calls[0][1] == {"entry": CHECK["rows"][0]["entry"], "working_dir": "/tiles"}
    assert PATCHLIB.applied_text({"icao": "KPDX", "tile": "+45-123", "version": 2,
                                  "mode": "solved"}) == (
        "KPDX v2 laid down: the next build of +45-123 skips its solve.")
    assert PATCHLIB._notice(CHECK["rows"]) == (
        "Patch library: airports 1 with a newer patch, 1 whose pack changed — see Library.")


def test_publish_patch_needs_one_built_tile_with_airports(app):
    dialog = _dialog()
    dialog.refresh = lambda: None
    _select(dialog, "+47-122")                          # no airport graded
    assert not dialog.publish_btn.isEnabled()
    _select(dialog, "+45-123")
    assert dialog.publish_btn.isEnabled()
    publish = dialog.publish_dialog(RESULT["tiles"][0])
    assert publish.airport_combo.currentText() == "KPDX"
    assert not publish.publish_btn.isEnabled()          # no preview, no licence yet
    publish._on_preview({"icao": "KPDX", "version": 1, "pack": "KPDX Pack",
                         "kind": "payware", "bytes": 1_600_000, "verified": True,
                         "problems": [], "signed_in": "dev", "licence_accepted": False})
    assert not publish.publish_btn.isEnabled()
    publish.licence_chk.setChecked(True)
    assert publish.publish_btn.isEnabled() and not publish.signin_btn.isVisible()
