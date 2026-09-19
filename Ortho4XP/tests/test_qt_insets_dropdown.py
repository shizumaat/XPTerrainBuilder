"""The airport-lidar-insets setting renders as the auto-patch dropdown.

``airport_elevation_insets`` became a three-valued enum on 2026-09-18
(RULINGS 2026-09-18c / 18e, spec ``docs/specs/insets-follow-patch-set-spec.md``
§A.5): the Qt settings window must show the same combo as ``auto_patch``,
with the registry's own labels, and a LEGACY ``True``/``False`` in a config
must select the mode the owner ruled it means rather than sitting on item 0.

Headless: QT_QPA_PLATFORM=offscreen, tmp_path cwd, no network.
"""
from __future__ import annotations

import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest
from PySide6.QtWidgets import QApplication, QComboBox

import O4_Settings_Model as SM
from O4_Qt_Settings import SettingsWindow

KEY = "airport_elevation_insets"
LABELS = ["Off", "Airports with ICAO codes", "All airports"]
VALUES = ["None", "ICAO", "All"]


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def _window(tmp_path, monkeypatch, global_values=None):
    monkeypatch.chdir(tmp_path)  # no real global cfg / prefs picked up
    if global_values is not None:
        monkeypatch.setattr(SM, "read_global_raw", lambda *a, **k: dict(global_values))
    return SettingsWindow(prefs={}, tiles=[], custom_build_dir="")


def _options(row):
    combo = row.control
    assert isinstance(combo, QComboBox), type(combo).__name__
    return (
        [combo.itemText(i) for i in range(combo.count())],
        [combo.itemData(i) for i in range(combo.count())],
    )


def test_insets_row_is_the_auto_patch_combo(qapp, tmp_path, monkeypatch):
    win = _window(tmp_path, monkeypatch)
    try:
        (labels, values) = _options(win.rows[KEY])
        assert values == VALUES
        assert labels == LABELS
        # Same control, same options as the row it was ruled to copy.
        assert _options(win.rows["auto_patch"]) == (labels, values)
        assert win.rows[KEY].value() == "ICAO"        # registry default
    finally:
        win.close()


def test_legacy_boolean_selects_the_ruled_mode(qapp, tmp_path, monkeypatch):
    """CHECKED/True -> "ICAO", UNCHECKED/False -> "None" (RULINGS 18e)."""
    for (stored, expected) in (("True", "ICAO"), ("False", "None"),
                               ("All", "All")):
        win = _window(tmp_path, monkeypatch, global_values={KEY: stored})
        try:
            row = win.rows[KEY]
            assert row.value() == expected, stored
            assert row.control.currentText() == LABELS[VALUES.index(expected)]
        finally:
            win.close()
