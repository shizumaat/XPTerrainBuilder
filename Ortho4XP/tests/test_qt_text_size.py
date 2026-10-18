"""View > Bigger Text / Smaller Text / Actual Size in the Qt window (#827).

Offscreen, no network, no engine: the window is driven through its own
actions.  The prefs file is monkeypatched BEFORE the window is built (it
loads prefs in ``__init__``), and every test ends at Actual Size so the
shared QApplication's font does not leak into other tests.
"""

import json
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest  # noqa: E402

pytest.importorskip("PySide6")

from PySide6.QtGui import QKeySequence  # noqa: E402
from PySide6.QtWidgets import QApplication, QLabel, QMenu  # noqa: E402

import O4_Text_Scale as TS  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    yield QApplication.instance() or QApplication([])


@pytest.fixture
def make_window(qapp, tmp_path, monkeypatch):
    import O4_Qt_GUI as GUI
    import O4_Qt_Text_Scale as QTTEXT
    import O4_UI_Utils as UI
    prefs_path = str(tmp_path / "prefs.json")

    def write_prefs(extra=None):
        prefs = {"output_dir": str(tmp_path)}  # existing: no wizard
        prefs.update(extra or {})
        with open(prefs_path, "w", encoding="utf-8", newline="") as handle:
            json.dump(prefs, handle)

    write_prefs()
    monkeypatch.setattr(GUI, "PREFS_FILE", prefs_path)
    monkeypatch.setattr(
        GUI, "TILE_SCAN_CACHE_FILE", str(tmp_path / "tile-scan.json"))
    saved_stdout = sys.stdout
    windows = []

    def _make(prefs=None):
        if prefs is not None:
            write_prefs(prefs)
        win = GUI.MainWindow()
        monkeypatch.setattr(win, "refresh_tiles", lambda: None)
        monkeypatch.setattr(win, "_refresh_scenery_packs", lambda: None)
        windows.append(win)
        return win

    def _prefs():
        with open(prefs_path, encoding="utf-8") as handle:
            return json.load(handle)

    _make.prefs = _prefs
    try:
        yield _make
    finally:
        for win in windows:
            win._building = False
            win.close()
            win.deleteLater()
        QTTEXT.apply_text_scale(TS.DEFAULT)
        UI.engine_session = None
        sys.stdout = saved_stdout


def _view_actions(win):
    view = next(m for m in win.menuBar().findChildren(QMenu)
                if m.title().replace("&", "") == "View")
    return {a.text(): a for a in view.actions() if a.text()}


def _keys(action):
    return {seq.toString() for seq in action.shortcuts()}


def test_the_view_menu_has_the_three_actions_on_the_zoom_keys(make_window):
    actions = _view_actions(make_window())
    bigger = actions[TS.BIGGER_TITLE]
    smaller = actions[TS.SMALLER_TITLE]
    actual = actions[TS.ACTUAL_TITLE]
    assert QKeySequence(QKeySequence.ZoomIn).toString() in _keys(bigger) or \
        QKeySequence(QKeySequence.ZoomIn).isEmpty()
    assert "Ctrl+=" in _keys(bigger)
    assert "Ctrl+-" in _keys(smaller)
    assert _keys(actual) == {"Ctrl+0"}


def test_bigger_scales_the_app_font_console_rows_and_notes(make_window):
    import O4_Qt_Text_Scale as QTTEXT
    win = make_window()
    base = QTTEXT.base_points()
    console_pt = win.console.font().pointSizeF()
    win._add_progress_rows([(48, -6)])
    row = win._tile_rows[(48, -6)][2]
    status = row.findChild(QLabel, "tile_status")
    status_px = status.font().pixelSize()
    assert (console_pt, status_px) == (11.0, 11)

    actions = _view_actions(win)
    actions[TS.BIGGER_TITLE].trigger()
    actions[TS.BIGGER_TITLE].trigger()
    assert QTTEXT.current_scale() == 1.3
    assert QApplication.font().pointSizeF() == TS.scaled(base, 1.3)
    assert win.console.font().pointSizeF() == TS.scaled(11, 1.3)
    assert status.font().pixelSize() == round(TS.scaled(11, 1.3))
    # A row made AFTER the change starts at the scale in force.
    win._add_progress_rows([(49, -6)])
    late = win._tile_rows[(49, -6)][2].findChild(QLabel, "tile_clock")
    assert late.font().pixelSize() == round(TS.scaled(11, 1.3))
    # A status update must not put a fixed stylesheet size back.
    assert "font-size" not in status.styleSheet()

    actions[TS.ACTUAL_TITLE].trigger()
    assert QApplication.font().pointSizeF() == base
    assert win.console.font().pointSizeF() == 11.0


def test_the_scale_is_remembered_between_launches(make_window):
    import O4_Qt_Text_Scale as QTTEXT
    win = make_window()
    _view_actions(win)[TS.BIGGER_TITLE].trigger()
    assert make_window.prefs()[TS.PREF_KEY] == 1.15
    win.close()
    QTTEXT.apply_text_scale(TS.DEFAULT)
    again = make_window(prefs=make_window.prefs())
    assert QTTEXT.current_scale() == 1.15
    assert again.console.font().pointSizeF() == TS.scaled(11, 1.15)


def test_the_ends_clamp_and_disable_their_action(make_window):
    import O4_Qt_Text_Scale as QTTEXT
    win = make_window(prefs={TS.PREF_KEY: 99})
    actions = _view_actions(win)
    assert QTTEXT.current_scale() == TS.STEPS[-1]
    assert not actions[TS.BIGGER_TITLE].isEnabled()
    for _ in range(len(TS.STEPS) + 2):
        win.set_text_scale(TS.smaller(QTTEXT.current_scale()))
    assert QTTEXT.current_scale() == TS.STEPS[0]
    assert not actions[TS.SMALLER_TITLE].isEnabled()
    assert actions[TS.BIGGER_TITLE].isEnabled()
    assert make_window.prefs()[TS.PREF_KEY] == TS.STEPS[0]


def test_map_labels_grow_with_the_text_scale():
    import O4_Map_Labels as LABELS
    candidates = [LABELS.LabelCandidate("KAAA", 100.0, 100.0, 0, 3000, False)]
    _, small = LABELS.place_airport_labels(candidates, 100.0, 5.0)
    _, big = LABELS.place_airport_labels(candidates, 100.0, 5.0,
                                         text_scale=1.3)
    assert big[0][1].font_size == pytest.approx(small[0][1].font_size * 1.3)
    assert big[0][1].width > small[0][1].width
