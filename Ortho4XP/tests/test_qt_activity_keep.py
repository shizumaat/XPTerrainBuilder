"""Headless tests for #1341, the Qt half: finished Activity rows stay until
the app quits, under the live ones in finish order, their titles dimmed;
a tile built with warnings shows a gold status that reopens its messages
with the "Report this problem" button.  The order itself is
``O4_Activity_Order`` (twin-tested against the mac app in
``test_activity_order.py``).

Offscreen, no network, no engine: runs are driven through
``MainWindow._start_run`` and the engine event handlers with
``EngineSession.enqueue_build`` recorded rather than run (the seam of
``test_qt_stop_resume.py``).  PREFS_FILE is isolated BEFORE construction.
"""

import json
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest  # noqa: E402

pytest.importorskip("PySide6")

import O4_Activity_Order as ACTORDER  # noqa: E402
import O4_Qt_GUI as GUI  # noqa: E402
import O4_Qt_Tile_Failures as QTFAIL  # noqa: E402
import O4_Tile_Failures as FAIL  # noqa: E402
from o4_engine import events as EV  # noqa: E402
from o4_engine import session as SESSION  # noqa: E402
from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtTest import QTest  # noqa: E402
from PySide6.QtWidgets import QApplication, QLabel, QMessageBox  # noqa: E402

WARNED = (47, -123)
PLAIN = (48, -6)
LAST = (49, -6)
NEW = (50, 10)
SETTINGS = {
    "provider": "BI",
    "zoomlevel": 15,
    "do_vector": True,
    "do_imagery": True,
    "do_overlays": False,
}


@pytest.fixture(scope="module")
def qapp():
    yield QApplication.instance() or QApplication([])


@pytest.fixture
def window(qapp, tmp_path, monkeypatch):
    path = str(tmp_path / "prefs.json")
    with open(path, "w", encoding="utf-8", newline="") as handle:
        json.dump({}, handle)
    monkeypatch.setattr(GUI, "PREFS_FILE", path)
    import O4_UI_Utils as UI
    saved_stdout = sys.stdout
    win = GUI.MainWindow()
    win.prefs["output_dir"] = str(tmp_path)
    # Never link a finished tile into the real X-Plane install (the
    # owner's prefs may have auto-install on; conftest refuses the write).
    win.prefs[GUI.AUTO_INSTALL_KEY] = False
    monkeypatch.setattr(win, "_auto_install_tile", lambda tile: None)
    monkeypatch.setattr(win, "refresh_tiles", lambda: None)
    monkeypatch.setattr(win._session, "enqueue_build",
                        lambda tiles, **kwargs: True)
    monkeypatch.setattr(win._session, "cancel_tile", lambda lat, lon: True)
    monkeypatch.setattr(win._session, "boundary_airports",
                        lambda tiles=None: None)
    # The run's own end-of-run box is not under test here.
    monkeypatch.setattr(win, "_show_issues_box", lambda events: None)
    monkeypatch.setattr(QApplication, "beep", lambda: None)
    deferred = []
    monkeypatch.setattr(win, "_after", lambda ms, callback: deferred.append(
        (ms, callback)))
    win.deferred = deferred
    try:
        yield win
    finally:
        win._building = False
        win.close()
        win.deleteLater()
        UI.engine_session = None
        sys.stdout = saved_stdout


def _finish(window, tile, records=()):
    window._on_tile_state(EV.TileState(
        lat=tile[0], lon=tile[1], state="done", percent=100.0))
    window._on_build_done(SESSION.build_done(
        tile[0], tile[1], True, list(records)))


def _three_tile_run_one_warned(window):
    window._start_run([WARNED, PLAIN, LAST], dict(SETTINGS))
    _finish(window, WARNED, [FAIL.record(
        "pack_dump_stale", "(build) [v2] stale", airport="AAAA")])
    _finish(window, PLAIN)
    _finish(window, LAST)
    window._on_run_done(EV.RunDone(done_count=3, error_count=0))
    linger = [fn for ms, fn in window.deferred if ms == 5000][-1]
    linger()


def _layout_order(window, section=ACTORDER.ACTIVITY):
    """The tiles of one section's rows in the run list, top to bottom
    (Activity unless ``section`` names another)."""
    return window.activity_list.section_tiles(section)


def _title(window, tile):
    return window._tile_rows[tile][2].findChild(QLabel, "tile_title")


def test_finished_rows_stay_dimmed_in_finish_order(window):
    _three_tile_run_one_warned(window)
    assert set(window._tile_rows) == {WARNED, PLAIN, LAST}
    # Built tiles sit in Completed (#1556), in finish order.
    assert _layout_order(
        window, ACTORDER.COMPLETED) == [WARNED, PLAIN, LAST]
    for tile in (WARNED, PLAIN, LAST):
        # Built rows: the dimmed gray brightened toward white (#1542).
        assert GUI.COMPLETED_TITLE_COLOR in _title(window, tile).styleSheet()
    # Nothing is left in Activity once the run is over.
    assert window.activity_list.activity_item.isHidden()
    assert not window.activity_list.completed_item.isHidden()
    assert not window.activity_group.isHidden()
    # The map's badges belonged to the run; the rows outlive it.
    assert window._map_progress() == {}


def test_the_warning_status_is_gold_and_reopens_the_dialog(window,
                                                          monkeypatch):
    zoomed = []
    monkeypatch.setattr(window, "_show_tile_on_map", zoomed.append)
    _three_tile_run_one_warned(window)
    status = window._tile_rows[WARNED][1]
    assert status.text() == QTFAIL.BUILT_WITH_WARNINGS
    assert GUI.WARNING_COLOR in status.styleSheet()
    assert status.is_clickable()
    assert not window._tile_rows[PLAIN][1].is_clickable()
    assert window._tile_rows[PLAIN][1].text() == "done ✓"
    before = len(window._pack_art_boxes)
    QTest.mouseClick(status, Qt.LeftButton)
    assert zoomed == [], "the status click is the status's own"
    assert len(window._pack_art_boxes) == before + 1
    box = window._pack_art_boxes[-1]
    assert isinstance(box, QMessageBox)
    labels = [button.text() for button in box.buttons()]
    assert QTFAIL.REPORT_BUTTON in labels
    box.close()
    # A click anywhere else on the row selects it in the list, natively,
    # and frames its tile (#816, #1537).
    window.activity_list.set_completed_expanded(True)
    window.show()
    QApplication.processEvents()
    QTest.mouseClick(_title(window, WARNED), Qt.LeftButton)
    assert zoomed == [WARNED]
    assert window.activity_list.selected_tiles() == {WARNED}


def test_a_newly_queued_tile_goes_on_top(window):
    _three_tile_run_one_warned(window)
    window._start_run([NEW], dict(SETTINGS))
    assert _layout_order(window)[0] == NEW
    assert set(window._tile_rows) == {WARNED, PLAIN, LAST, NEW}
    assert _title(window, NEW).styleSheet() == ""
    # Building a finished tile again puts it back on top, live.
    window._queue_into_running_build_now(
        [PLAIN], "BI", 15, True, True, False)
    assert _layout_order(window) == [PLAIN, NEW]
    assert _title(window, PLAIN).styleSheet() == ""
    assert window._tile_rows[PLAIN][1].text() == "queued"
    # The run report and the retry list describe this run only.
    window._on_tile_state(EV.TileState(
        lat=NEW[0], lon=NEW[1], state="error", percent=0.0))
    retry = sorted(tile for tile, _settings in window._failed_and_unstarted())
    assert retry == sorted([NEW, PLAIN])


def test_a_done_row_is_compact(window):
    """#1542: a built tile's row is its title, brightened 50 % toward
    white, then "done" and its clock -- no bar, no steps.  #1537: the
    list's own selection shows it selected."""
    from PySide6.QtGui import QColor
    _three_tile_run_one_warned(window)
    bar, status, row, _cancel, clock = window._tile_rows[PLAIN]
    assert bar.isHidden()
    assert row.findChild(QLabel, "tile_steps").isHidden()
    assert status.text().startswith("done")
    assert not clock.isHidden()
    assert GUI.COMPLETED_TITLE_COLOR in _title(window, PLAIN).styleSheet()
    gray, mid = QColor(GUI.FINISHED_TITLE_COLOR), QColor(
        GUI.COMPLETED_TITLE_COLOR)
    for a, b in ((gray.red(), mid.red()), (gray.green(), mid.green()),
                 (gray.blue(), mid.blue())):
        assert abs(b - (a + 255) / 2) <= 1
    window.map.set_selection([PLAIN, WARNED])
    assert window.activity_list.selected_tiles() == {PLAIN, WARNED}


def test_a_requeued_done_row_grows_back(window):
    _three_tile_run_one_warned(window)
    window._start_run([PLAIN], dict(SETTINGS))
    bar, _status, row, _cancel, _clock = window._tile_rows[PLAIN]
    assert not bar.isHidden()
    assert not row.findChild(QLabel, "tile_steps").isHidden()
    assert "color" not in _title(window, PLAIN).styleSheet()


# ─── #1556: the Completed section ──────────────────────────────────────────

def _completed(window):
    return _layout_order(window, ACTORDER.COMPLETED)


def test_done_tiles_move_to_a_collapsed_completed_section(window):
    window._start_run([WARNED, PLAIN, LAST], dict(SETTINGS))
    listed = window.activity_list
    section = listed.completed_item
    assert section.isHidden()
    _finish(window, WARNED, [FAIL.record(
        "pack_dump_stale", "(build) [v2] stale", airport="AAAA")])
    window._on_tile_state(EV.TileState(
        lat=PLAIN[0], lon=PLAIN[1], state="error", percent=0.0))
    # Built with warnings is still built: Completed.  Failed stays.
    assert _completed(window) == [WARNED]
    assert set(_layout_order(window)) == {PLAIN, LAST}
    assert not section.isHidden()
    assert not listed.completed_expanded()
    assert section.text(0) == "Completed (1)"
    _finish(window, LAST)
    assert section.text(0) == "Completed (2)"
    assert _layout_order(window) == [PLAIN]


def test_completed_expands_and_collapses_and_keeps_the_choice(window):
    _three_tile_run_one_warned(window)
    listed = window.activity_list
    toggled = []
    listed.completed_expanded_changed.connect(toggled.append)
    listed.expandItem(listed.completed_item)    # the native disclosure
    assert listed.completed_expanded()
    assert toggled == [True]
    assert listed.completed_item.text(0) == "Completed (3)"
    # A new run, its tile built: the section is still open.
    window._start_run([NEW], dict(SETTINGS))
    _finish(window, NEW)
    assert listed.completed_expanded()
    assert listed.completed_item.text(0) == "Completed (4)"
    listed.collapseItem(listed.completed_item)
    assert not listed.completed_expanded()


def test_a_requeued_done_tile_moves_back_to_activity(window):
    _three_tile_run_one_warned(window)
    window._start_run([PLAIN], dict(SETTINGS))
    assert _layout_order(window) == [PLAIN]
    assert _completed(window) == [WARNED, LAST]
    assert window.activity_list.completed_item.text(0) == "Completed (2)"
    assert not window.activity_list.activity_item.isHidden()
    assert not window.activity_group.isHidden()


def test_a_stopped_tile_stays_in_activity(window):
    window._start_run([PLAIN, LAST], dict(SETTINGS))
    window._on_tile_state(EV.TileState(
        lat=PLAIN[0], lon=PLAIN[1], state="stopped", percent=0.0))
    _finish(window, LAST)
    assert PLAIN in _layout_order(window)
    assert _completed(window) == [LAST]
