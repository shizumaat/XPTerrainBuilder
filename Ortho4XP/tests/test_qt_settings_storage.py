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


def test_the_library_budget_asks_before_it_downgrades(app, monkeypatch):
    """#2007: a budget below what is in use asks "downgrade scenery to low
    res to fit?" with the bytes; Cancel keeps the old budget; yes sets it
    and runs the budget hold.  Unset, the default shows and is used."""
    import O4_Qt_Library_Storage as QTLIBSTORE
    import O4_Storage_Text as TEXT
    section = QTSTORE.StorageSection()
    box = QTLIBSTORE.DiskBudgetBox(section)
    caches = QTLIBSTORE.CachesLine(section)
    applied, asked = [], []
    monkeypatch.setattr(section, "apply_budget", applied.append)
    # RULINGS 2026-11-11h (1): unconfirmed, the default holds the install.
    budget = {"budget_bytes": 300e9, "budget_set": False, "default_bytes": 300e9,
              "default_base_bytes": 200e9, "recommended_bytes": 255e9,
              "held_bytes": 300e9, "used_bytes": 300e9, "floor_bytes": 170e9,
              "over_budget": False, "under_floor": False, "low_water": 0.9}
    written = []
    import O4_Settings_Model as SM
    monkeypatch.setattr(SM, "write_global", written.append)
    monkeypatch.setattr(section, "refresh", lambda: None)
    try:
        section.set_scan(dict(SCAN, budget=budget))
        assert box.budget_edit.text() == "300"                 # the default applies
        assert "holds everything installed now (300.00 GB)" in box.held_label.text()
        assert not box.confirm_btn.isHidden() and box.default_btn.isHidden()
        box.confirm_btn.click()                                # Confirm records it
        assert written == [{QTSTORE.BUDGET_SETTING: "300.0"}]
        assert caches.total_label.text() == QTSTORE.fmt_size(3_000)
        box.confirm = lambda title, text: asked.append((title, text)) or False
        box.budget_edit.setText("150")
        box.submit()
        assert asked[0][0] == TEXT.DOWNGRADE_TITLE and "165.00 GB" in asked[0][1]
        assert applied == [] and box.budget_edit.text() == "300"   # Cancel
        box.confirm = lambda title, text: True
        box.budget_edit.setText("150")
        box.submit()
        assert applied == [150.0]
    finally:
        section.deleteLater()


def test_the_budget_slider_spans_the_range_and_previews(app, monkeypatch):
    """#2022: the slider runs from the minimum to the most, its ends say
    so with the figures, it previews what a budget clears while it moves
    and sets it on release (asked first below what is in use)."""
    import O4_Qt_Library_Storage as QTLIBSTORE
    import O4_Storage_Text as TEXT
    section = QTSTORE.StorageSection()
    box = QTLIBSTORE.DiskBudgetBox(section)
    applied, asked = [], []
    monkeypatch.setattr(section, "apply_budget", applied.append)
    budget = {"budget_bytes": 400e9, "budget_set": True, "chosen_bytes": 900e9,
              "clamped": "followed", "used_bytes": 300e9, "floor_bytes": 20e9,
              "recommended_bytes": 70e9, "minimum_bytes": 25e9,
              "maximum_bytes": 400e9, "low_water": 0.9,
              "breakdown": {"tiles": 200e9, "other": 100e9},
              "ladder": {"caches": 40e9, "imagery": 100e9}}
    try:
        section.set_scan(dict(SCAN, budget=budget))
        assert (box.budget_slider.minimum(), box.budget_slider.maximum()) == (25, 400)
        assert box.budget_slider.value() == 400 and box.budget_edit.text() == "400"
        assert box.min_label.text() == TEXT.end_labels(budget)[0]
        assert "follows the disk down to 400.00 GB" in box.budget_warning.text()
        assert "Tiles and mesh 200.00 GB" in box.usage_bar.legend.text()
        box.budget_slider.setSliderPosition(250)
        box._moved(250)
        assert not box.preview_label.isHidden()
        assert box.preview_label.text() == TEXT.preview_text(budget, 250e9)
        box.confirm = lambda title, text: asked.append(title) or True
        box._released()
        assert box.preview_label.isHidden() and asked == [TEXT.DOWNGRADE_TITLE]
        assert applied == [250.0]
    finally:
        section.deleteLater()
