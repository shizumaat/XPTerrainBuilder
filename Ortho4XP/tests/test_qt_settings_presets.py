"""Settings preset cards in the Qt app (issue #822), offscreen.

The Settings window shows the three cards; one click writes exactly the
preset's config keys to the global config and its zoom to the preferences,
and the rows show the new values at once; changing a key afterwards shows
Custom.  The first-run wizard shows the same cards on its Imagery page and
hands the picked preset's config keys to its caller.

Headless: QT_QPA_PLATFORM=offscreen, tmp_path cwd, no network.
"""

from __future__ import annotations

import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest  # noqa: E402

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

import O4_Qt_Wizard as WIZ  # noqa: E402
import O4_Settings_Model as SM  # noqa: E402
import O4_Settings_Presets as PRESETS  # noqa: E402
from O4_Qt_Settings import SettingsWindow  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    yield QApplication.instance() or QApplication([])


@pytest.fixture
def window(qapp, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)  # no real global cfg / prefs picked up
    win = SettingsWindow(prefs={}, tiles=[], custom_build_dir="")
    yield win
    win.close()


def _titles(cards):
    return [PRESETS.preset(key).title for key in cards.cards]


def test_settings_shows_the_three_cards_and_balanced(window):
    # An untouched global config is the registry defaults: Balanced.
    cards = window.preset_cards
    assert _titles(cards) == ["Light on disk", "Balanced",
                              "Sharper airports"]
    assert cards.current_key == "balanced"
    assert cards.status_label.text() == "Current: Balanced"
    assert not cards.buttons["balanced"].isEnabled()


def test_applying_a_preset_sets_exactly_its_keys(window):
    before = SM.read_global_raw()
    window.preset_cards.buttons["light_on_disk"].click()
    after = SM.read_global_raw()
    changed = {name for name in set(before) | set(after)
               if before.get(name) != after.get(name)}
    entry = PRESETS.preset("light_on_disk")
    assert changed <= set(PRESETS.cfg_values(entry))
    for name, value in PRESETS.cfg_values(entry).items():
        assert SM.values_equivalent(name, after[name], value)
        # The row shows it at once (the Expert rows included).
        assert SM.values_equivalent(name, window.rows[name].value(), value)
    assert window.result_prefs()["zl"] == 15
    assert window.preset_cards.status_label.text() == "Current: Light on disk"


def test_a_row_edit_after_a_preset_shows_custom(window):
    window.preset_cards.buttons["sharper_airports"].click()
    assert window.preset_cards.current_key == "sharper_airports"
    row = window.rows["cover_extent"]
    row.set_value("2.5")
    window._row_committed(row)
    assert window.preset_cards.current_key is None
    assert window.preset_cards.status_label.text() == "Current: Custom"
    assert all(button.isEnabled()
               for button in window.preset_cards.buttons.values())


def test_a_preset_with_a_tile_selected_applies_to_the_tile(
        qapp, tmp_path, monkeypatch):
    """#1549: with a tile selected, Use applies the preset to that tile
    (its config keys as tile values, its zoom as the tile's next build);
    the global defaults are untouched."""
    monkeypatch.chdir(tmp_path)
    build_dir = str(tmp_path) + "/"
    SM.write_tile(48, -6, build_dir, {"cover_extent": "3.0"})
    win = SettingsWindow(prefs={}, tiles=[(48, -6)],
                         custom_build_dir=build_dir)
    try:
        assert win.preset_cards.current_key is None    # 3.0 is no preset
        win.preset_cards.buttons["sharper_airports"].click()
        assert "cover_airports_with_highres" not in SM.read_global_raw()
        raw = SM.read_tile_raw(48, -6, build_dir)
        assert raw["cover_airports_with_highres"] == "ICAO"
        assert "cover_extent" not in raw   # 1.0 is the global: no override
        assert SM.values_equivalent(
            "cover_extent", win.rows["cover_extent"].value(), "1.0")
        assert (win.zoom_target, win.selection_zl) == ("tiles", 16)
        assert win.preset_cards.current_key == "sharper_airports"
        assert not win.preset_cards.buttons["sharper_airports"].isEnabled()
    finally:
        win.close()


def test_first_run_shows_the_cards_and_hands_back_the_pick(
        qapp, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(WIZ, "detect_xplane_installs", lambda: [])
    wizard = WIZ.OnboardingWizard({}, ["BI"])
    try:
        wizard._set_step(WIZ.STEPS.index("Imagery"))
        cards = wizard.preset_cards
        assert _titles(cards) == ["Light on disk", "Balanced",
                                  "Sharper airports"]
        # A new user starts from the default preset (#937).
        assert cards.status_label.text() == "Current: Sharper airports"
        cards.buttons["light_on_disk"].click()
        assert wizard.zl_combo.currentText() == "15"
        assert cards.current_key == "light_on_disk"
        wizard._finish()
        assert wizard.prefs["zl"] == 15
        assert wizard.preset_values == PRESETS.cfg_values(
            PRESETS.preset("light_on_disk"))
    finally:
        wizard.close()


def test_first_run_finish_writes_the_default_preset(
        qapp, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(WIZ, "detect_xplane_installs", lambda: [])
    wizard = WIZ.OnboardingWizard({}, ["BI"])
    try:
        wizard._finish()
        assert wizard.preset_values == PRESETS.cfg_values(
            PRESETS.default_preset())
    finally:
        wizard.close()


def test_first_run_keeps_a_config_that_sets_a_preset_key(
        qapp, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(WIZ, "detect_xplane_installs", lambda: [])
    SM.write_global({"cover_extent": "2.5"})
    wizard = WIZ.OnboardingWizard({}, ["BI"])
    try:
        assert wizard.preset_cards.status_label.text() == "Current: Custom"
        wizard._finish()
        assert wizard.preset_values == {}
    finally:
        wizard.close()


def test_first_run_zoom_change_after_a_pick_is_custom(
        qapp, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(WIZ, "detect_xplane_installs", lambda: [])
    wizard = WIZ.OnboardingWizard({}, ["BI"])
    try:
        wizard.preset_cards.buttons["sharper_airports"].click()
        wizard.zl_combo.setCurrentText("17")
        assert wizard.preset_cards.status_label.text() == "Current: Custom"
        wizard._finish()
        assert wizard.prefs["zl"] == 17
        assert wizard.preset_values == {}
    finally:
        wizard.close()


def test_choosing_a_zoom_in_the_dialog_is_recorded(window):
    """#1539: the main window makes the dialog's zoom the default only
    when the user chose one there (Detail or a preset card)."""
    assert window.zoom_chosen is False
    window.detail_combo.setCurrentText("18")
    assert window.zoom_chosen is True
