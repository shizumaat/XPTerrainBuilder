"""Settings > Storage in the Qt window (#1724), offscreen: the section
lists every store from a ``storage_scan`` result, a kept store (built
tiles, patches) has no Clear button, a declined confirmation deletes
nothing, and a busy engine refuses.  No engine, no network, no data folder
walk: the scan is a literal and the clear is stubbed.
"""
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest  # noqa: E402

pytest.importorskip("PySide6")

import O4_Qt_Settings_Storage as QTSTORE  # noqa: E402
from o4_engine import storage as STORAGE  # noqa: E402
from PySide6.QtWidgets import QApplication, QLabel  # noqa: E402


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def _store(kind, policy, size, files=1):
    return {"kind": kind, "label": kind.title(), "policy": policy, "note": "n",
            "path": "/nowhere/" + kind, "bytes": size, "apparent_bytes": size,
            "files": files, "last_used": 1.7e9 if files else None}


SCAN = {"root": "/nowhere", "measured": "private", "auto_clean_days": 0.0,
        "caps": {}, "cache_bytes": 3_000, "kept_bytes": 9_000,
        "stores": [_store("imagery", STORAGE.CACHE, 3_000),
                   _store("masks", STORAGE.CACHE, 0, files=0),
                   _store("tiles", STORAGE.KEPT, 9_000)]}


def test_rows_buttons_and_a_declined_clear(app, monkeypatch):
    section = QTSTORE.StorageSection()
    calls = []
    monkeypatch.setattr(STORAGE, "storage_clear", lambda **kw: calls.append(kw))
    try:
        section.set_scan(SCAN)
        assert set(section.clear_buttons) == {"imagery", "masks"}   # tiles: none
        assert section.clear_buttons["imagery"].isEnabled()
        assert not section.clear_buttons["masks"].isEnabled()      # empty
        asked = []
        section.confirm = lambda title, message: asked.append(message) or False
        section.ask_clear(SCAN["stores"][0])
        assert asked and QTSTORE.fmt_size(3_000) in asked[0] and calls == []
        section.busy = lambda: True
        section.ask_clear(SCAN["stores"][0])
        assert len(asked) == 1 and "build is running" in section.status_label.text()
        assert section.matches("orthophotos") and section.matches("disk")
    finally:
        section.deleteLater()


def test_auto_clean_is_skipped_while_busy(monkeypatch):
    ran = []
    monkeypatch.setattr(STORAGE, "storage_auto_clean", lambda **kw: ran.append(kw))
    QTSTORE.run_auto_clean(lambda: True, print)
    assert ran == []


def test_both_apps_show_the_same_sections(app):
    """Two UIs, one layout (#1244): the Mac pane's sections and the age
    picker's choices are the Qt section's."""
    from pathlib import Path
    swift = (Path(__file__).resolve().parents[2] / "Sources" / "XPTerrainBuilder"
             / "StorageSettingsView.swift").read_text(encoding="utf-8")
    marks = [swift.find('Section("%s")' % title)
             for title in ("Data Folder", "Caches", "Kept")]
    assert -1 not in marks and marks == sorted(marks)
    assert "[30, 60, 90, 180, 365]" in swift and QTSTORE.AGE_CHOICES == (30, 60, 90, 180, 365)
    assert 'Picker("Clear cache files not used for"' in swift
    section = QTSTORE.StorageSection()
    try:
        assert section.title == "Data Folder"
        section.set_scan(SCAN)
        widgets = [section.rows_layout.itemAt(i).widget()
                   for i in range(section.rows_layout.count())]
        headings = [w.text() for w in widgets if isinstance(w, QLabel)]
        assert headings == ["<b>Caches</b>", "<b>Kept</b>"]
    finally:
        section.deleteLater()
