"""The Qt Settings window follows the map selection (#1549), offscreen.

Owner RULINGS 2026-10-28i and 28j: no tile selected shows (and edits)
the defaults for new tiles; one tile shows its own settings; several
that agree look like one; several that disagree show "Conflicting
values" and every change asks first; the preset cards compare the
selection; app-wide settings stay global; a never-built tile counts as
the defaults.  The rule is ``O4_Settings_Selection``
(``tests/test_settings_selection.py``); the Mac app's twin is
``Tests/SceneryKitTests/SettingsSelectionTests.swift``.

Headless: QT_QPA_PLATFORM=offscreen, tmp_path cwd, no network.
"""

from __future__ import annotations

import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest  # noqa: E402

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QMessageBox  # noqa: E402

import O4_Settings_Model as SM  # noqa: E402
import O4_Settings_Selection as SEL  # noqa: E402
from O4_Qt_Settings import SettingsWindow  # noqa: E402

A, B = (48, -6), (49, -6)
SHARPER = {"cover_airports_with_highres": "ICAO", "cover_zl": "18",
           "cover_extent": "1.0"}


@pytest.fixture(scope="module")
def qapp():
    yield QApplication.instance() or QApplication([])


@pytest.fixture
def env(qapp, tmp_path, monkeypatch):
    """A global config (road_level=3), the build dir, and a recorded
    answer for the confirmation (``env.answer``; ``env.asked``)."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "XPTerrainBuilder.cfg").write_text(
        "road_level=3\n", encoding="utf-8", newline="")

    class Env:
        build_dir = str(tmp_path) + "/"
        answer = QMessageBox.Yes
        asked = []
        windows = []

        def window(self, tiles, **kwargs):
            win = SettingsWindow(prefs={"zl": 16}, tiles=tiles,
                                 custom_build_dir=self.build_dir, **kwargs)
            self.windows.append(win)
            return win

        def raw(self, tile):
            return SM.read_tile_raw(tile[0], tile[1], self.build_dir) or {}

    env = Env()
    env.asked = []
    monkeypatch.setattr(
        QMessageBox, "question",
        lambda *a, **k: env.asked.append(a) or env.answer)
    yield env
    for win in env.windows:
        win.close()


def _commit(win, name, value):
    row = win.rows[name]
    row.set_value(value)
    win._row_committed(row)
    return row


def test_no_selection_shows_and_edits_the_defaults(env):
    SM.write_tile(*A, env.build_dir, {"road_level": "5"})   # a built tile
    win = env.window([])
    assert win.context_label.text() == "Editing the global defaults for new tiles"
    assert win.rows["road_level"].value() == "3"
    assert win.detail_combo.currentText() == "16"
    _commit(win, "road_level", "4")
    assert SM.read_global_raw()["road_level"] == "4"
    assert env.raw(A)["road_level"] == "5", "built tiles keep their own"
    win.detail_combo.setCurrentText("17")
    assert win.zoom_target == "defaults" and win.result_prefs()["zl"] == 17
    assert env.asked == []


def test_one_tile_shows_and_edits_its_own_settings(env):
    SM.write_tile(*A, env.build_dir, {"road_level": "5"})
    win = env.window([A], tile_zooms={A: 17})
    assert win.context_label.text() == "Editing tile +48-006"
    assert win.rows["road_level"].value() == "5"
    assert win.detail_combo.currentText() == "17"
    _commit(win, "road_level", "1")
    assert env.raw(A)["road_level"] == "1"
    assert SM.read_global_raw()["road_level"] == "3"
    win.detail_combo.setCurrentText("18")
    assert (win.zoom_target, win.selection_zl) == ("tiles", 18)
    assert win.result_prefs()["zl"] == 16, "the default is untouched"
    assert env.asked == []


def test_matching_tiles_look_like_one_and_edit_together(env):
    for tile in (A, B):
        SM.write_tile(*tile, env.build_dir, {"road_level": "5"})
    win = env.window([A, B], tile_zooms={A: 17, B: 17})
    row = win.rows["road_level"]
    assert row.value() == "5" and not row.is_mixed()
    assert row.conflict_tag.isHidden()
    assert win.context_label.text() == "Editing 2 tiles"
    assert win.detail_combo.currentText() == "17"
    _commit(win, "road_level", "1")
    assert env.asked == [], "agreeing tiles: no question"
    assert env.raw(A)["road_level"] == env.raw(B)["road_level"] == "1"


def test_conflicting_tiles_show_it_and_confirm_every_change(env):
    SM.write_tile(*A, env.build_dir, {"road_level": "5"})
    win = env.window([A, B])
    row = win.rows["road_level"]
    assert row.is_mixed() and not row.conflict_tag.isHidden()
    assert row.conflict_tag.text() == SEL.CONFLICT_TEXT
    assert win.context_label.text() == "Editing 2 tiles · conflicting values"

    env.answer = QMessageBox.No                       # declined: nothing
    _commit(win, "road_level", "4")
    assert len(env.asked) == 1
    assert env.asked[0][1] == SEL.CONFIRM_TITLE
    assert env.raw(A)["road_level"] == "5" and "road_level" not in env.raw(B)
    assert row.is_mixed(), "the conflict still shows"

    env.answer = QMessageBox.Yes                      # confirmed: all
    _commit(win, "road_level", "4")
    assert len(env.asked) == 2
    assert env.raw(A)["road_level"] == env.raw(B)["road_level"] == "4"
    assert not row.is_mixed()
    assert win.context_label.text() == "Editing 2 tiles"


def test_conflicting_detail_levels_show_it_and_confirm(env):
    win = env.window([A, B], tile_zooms={A: 16, B: 17})
    assert win.detail_combo.currentIndex() == -1
    assert win.detail_combo.placeholderText() == SEL.CONFLICT_TEXT
    env.answer = QMessageBox.No
    win.detail_combo.setCurrentText("18")
    assert win.zoom_target is None and win.detail_combo.currentIndex() == -1
    env.answer = QMessageBox.Yes
    win.detail_combo.setCurrentText("18")
    assert (win.zoom_target, win.selection_zl) == ("tiles", 18)


def test_a_matching_preset_is_highlighted_and_its_use_disabled(env):
    for tile in (A, B):
        SM.write_tile(*tile, env.build_dir, SHARPER)
    win = env.window([A, B], tile_zooms={A: 16, B: 16})
    cards = win.preset_cards
    assert cards.current_key == "sharper_airports"
    assert not cards.buttons["sharper_airports"].isEnabled()
    assert cards.buttons["balanced"].isEnabled()
    assert cards.note_label.text() == SEL.TILES_NOTE


def test_preset_use_applies_to_every_selected_tile(env):
    SM.write_tile(*A, env.build_dir, {"cover_extent": "3.0"})
    win = env.window([A, B], tile_zooms={A: 17, B: None})
    assert win.preset_cards.current_key is None
    assert all(b.isEnabled() for b in win.preset_cards.buttons.values())
    win.preset_cards.buttons["sharper_airports"].click()
    assert len(env.asked) == 1, "the tiles disagreed: confirmed once"
    for tile in (A, B):
        raw = env.raw(tile)
        assert raw["cover_airports_with_highres"] == "ICAO"
        assert "cover_extent" not in raw
    assert "cover_airports_with_highres" not in SM.read_global_raw()
    assert (win.zoom_target, win.selection_zl) == ("tiles", 16)
    assert win.preset_cards.current_key == "sharper_airports"


def test_app_wide_settings_stay_global_with_tiles_selected(env):
    win = env.window([A, B])
    setting = SM.get_setting("max_build_slots")
    assert setting.scope == "app"
    _commit(win, setting.name, "3")
    assert SM.read_global_raw()[setting.name] == "3"
    assert setting.name not in env.raw(A) and setting.name not in env.raw(B)
    assert env.asked == []


def test_a_never_built_tile_counts_as_the_defaults(env):
    SM.write_tile(*A, env.build_dir, {"road_level": "3"})  # = the global
    win = env.window([A, B], tile_zooms={A: 16, B: None})
    assert not win.rows["road_level"].is_mixed()
    assert win.detail_combo.currentText() == "16"
    assert win.context_label.text() == "Editing 2 tiles"
    built_17 = env.window([A, B], tile_zooms={A: 17, B: None})
    assert built_17.detail_combo.currentIndex() == -1, "17 vs the default 16"
