"""Headless tests for the Qt UI's restored tile selection and its
immediate per-tile stop / resume (docs/specs/qt-parity-selection-stop-
resume-spec.md — the Qt half of the two shipped mac-app specs).

Offscreen (``QT_QPA_PLATFORM=offscreen``), no network, no engine: runs
are driven through ``MainWindow._start_run`` and the engine event
handlers with ``EngineSession.enqueue_build`` recorded rather than run,
which is the same seam the other Qt tests use.

The PREFS_FILE monkeypatch BEFORE construction is mandatory (see
``test_qt_tile_cancel``): the window loads prefs in ``__init__`` and
SAVES them on selection changes and on close, so without isolation a
test window clobbers the user's real ``.qt_prefs.json`` — and this file
is precisely about what gets written there.
"""

import json
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest  # noqa: E402

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

import O4_Qt_GUI as GUI  # noqa: E402
import O4_Qt_Map as QTMAP  # noqa: E402
from o4_engine import events as EV  # noqa: E402


TILE = (48, -6)
OTHER = (49, -6)
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
def prefs_file(tmp_path):
    """An isolated prefs file that EXISTS but says nothing.

    Its existence is what tells the window this is not a first run: an
    absent file arms the onboarding wizard, whose modal exec would sit
    there forever in a headless run.  An empty object still means "no
    stored selection", which is the state most of these tests want.
    """
    path = str(tmp_path / "prefs.json")
    with open(path, "w") as handle:
        json.dump({}, handle)
    return path


@pytest.fixture
def make_window(qapp, tmp_path, prefs_file, monkeypatch):
    """Build a MainWindow against an isolated prefs file, with the engine
    session's build entry recorded instead of run."""
    monkeypatch.setattr(GUI, "PREFS_FILE", prefs_file)
    import O4_UI_Utils as UI
    saved_stdout = sys.stdout
    windows = []
    enqueued = []

    def _make():
        win = GUI.MainWindow()
        win.prefs["output_dir"] = str(tmp_path)
        monkeypatch.setattr(win, "refresh_tiles", lambda: None)
        monkeypatch.setattr(
            win._session, "enqueue_build",
            lambda tiles, **kwargs: enqueued.append(
                (sorted(tiles), kwargs)) or True)
        monkeypatch.setattr(
            win._session, "cancel_tile", lambda lat, lon: True)
        monkeypatch.setattr(win._session, "cancel", lambda: True)
        windows.append(win)
        return win

    _make.enqueued = enqueued
    try:
        yield _make
    finally:
        for win in windows:
            # Closing mid-run would raise the "stop it and quit?" prompt,
            # a modal exec with nobody to answer it.
            win._building = False
            win.close()
            win.deleteLater()
        UI.engine_session = None
        sys.stdout = saved_stdout


@pytest.fixture
def window(make_window):
    return make_window()


def _read_prefs(path):
    with open(path, "r") as handle:
        return json.load(handle)


def _stop_button(window, tile):
    return window._tile_rows[tile][3]


def _status_label(window, tile):
    return window._tile_rows[tile][1]


# ---------------------------------------------------------------------------
# Q1 — the tile key is one spelling, with one reader
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "tile", [(0, 0), (48, -6), (-35, -81), (89, -180), (-1, 179)])
def test_tile_key_round_trip(tile):
    assert QTMAP.parse_tile_key(QTMAP.tile_key(*tile)) == tile


@pytest.mark.parametrize(
    "key",
    ["", "35,-81", "+91-000", "+00-181", "48-006", "+48-6", "+48-006 ",
     None, 42])
def test_parse_refuses_malformed_keys(key):
    assert QTMAP.parse_tile_key(key) is None


def test_selection_is_written_to_the_prefs_file(window, prefs_file):
    window.map.set_selection({TILE, OTHER})
    window.map.set_active(TILE[0], TILE[1], select=False)
    stored = _read_prefs(prefs_file)
    assert stored[GUI.SELECTED_TILES_KEY] == ["+48-006", "+49-006"]
    assert stored[GUI.ACTIVE_TILE_KEY] == "+48-006"


def test_selection_comes_back_on_the_next_launch(make_window):
    first = make_window()
    first.map.set_selection({TILE, OTHER})
    first.map.set_active(OTHER[0], OTHER[1], select=False)
    first.close()

    second = make_window()
    assert second.map.selection() == {TILE, OTHER}
    assert second.map.active_tile() == OTHER


def test_deselecting_everything_launches_empty(make_window, prefs_file):
    first = make_window()
    first.map.set_selection({TILE})
    first.map.clear_selection()
    first.close()
    assert _read_prefs(prefs_file)[GUI.SELECTED_TILES_KEY] == []

    second = make_window()
    # Empty state is today's launch: the remembered last tile, active.
    assert second.map.selection() == {second.map.active_tile()}


def test_malformed_stored_keys_are_dropped_silently(make_window, prefs_file):
    with open(prefs_file, "w") as handle:
        json.dump({GUI.SELECTED_TILES_KEY: ["+48-006", "nonsense",
                                            "+91-000", "+49-006"],
                   GUI.ACTIVE_TILE_KEY: "+49-006"}, handle)
    window = make_window()
    assert window.map.selection() == {TILE, OTHER}
    assert window.map.active_tile() == OTHER


def test_active_outside_the_set_falls_back_to_the_first_tile(make_window,
                                                             prefs_file):
    with open(prefs_file, "w") as handle:
        json.dump({GUI.SELECTED_TILES_KEY: ["+49-006", "+48-006"],
                   GUI.ACTIVE_TILE_KEY: "+10-010"}, handle)
    window = make_window()
    assert window.map.selection() == {TILE, OTHER}
    assert window.map.active_tile() == TILE


def test_restored_selection_syncs_the_toolbar_like_a_click(make_window,
                                                           prefs_file):
    """The restore must let the per-tile config adoption fire exactly as
    it does on a user click — the combos are synced to the restored set,
    not left at the raw prefs defaults."""
    with open(prefs_file, "w") as handle:
        json.dump({GUI.SELECTED_TILES_KEY: ["+48-006"],
                   GUI.ACTIVE_TILE_KEY: "+48-006"}, handle)
    window = make_window()
    assert window._combos_synced_to is not None
    assert window._combos_synced_to[1] == frozenset({TILE})


# ---------------------------------------------------------------------------
# Q2 — the rules, with no widgets in the way
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("state,wins", [
    ("done", True), ("error", True),
    ("queued", False), ("active", False),
    ("indeterminate", False), ("stopped", False),
])
def test_only_a_terminal_outcome_overwrites_a_stopped_row(state, wins):
    assert GUI.may_overwrite_stopped(state) is wins


def test_resolve_drops_stale_events_over_a_stopped_row():
    stopped = ("stopped", "stopped", 42.0)
    assert GUI.resolve_tile_state(("active", "mesh", 61.0), stopped) is None
    # The engine's own late "stopped" notice is stale news too.
    assert GUI.resolve_tile_state(("queued", "stopped", 0), stopped) is None


def test_resolve_lets_terminal_outcomes_through():
    stopped = ("stopped", "stopped", 42.0)
    done = ("done", "", 100.0)
    assert GUI.resolve_tile_state(done, stopped) == done
    assert GUI.resolve_tile_state(("error", "failed", 0), stopped) == (
        "error", "failed", 0)


def test_resolve_passes_everything_through_for_a_live_row():
    incoming = ("active", "imagery", 12.0)
    assert GUI.resolve_tile_state(incoming, None) == incoming
    assert GUI.resolve_tile_state(
        incoming, ("queued", "queued", 0)) == incoming


def test_enqueue_resume_is_ordered_and_deduped():
    queue = GUI.enqueue_resume(TILE, [])
    queue = GUI.enqueue_resume(OTHER, queue)
    assert queue == [TILE, OTHER]
    assert GUI.enqueue_resume(TILE, queue) == [TILE, OTHER]
    assert GUI.enqueue_resume(TILE, []) == [TILE], "the input is not mutated"


# ---------------------------------------------------------------------------
# Q2 — painted glyphs
# ---------------------------------------------------------------------------
def test_glyphs_are_painted_and_distinct(qapp):
    stop = GUI.stop_sign_icon()
    resume = GUI.resume_icon()
    assert not stop.isNull() and not resume.isNull()
    stop_image = stop.pixmap(GUI.STOP_ICON_PT, GUI.STOP_ICON_PT).toImage()
    resume_image = resume.pixmap(GUI.STOP_ICON_PT, GUI.STOP_ICON_PT).toImage()
    assert stop_image != resume_image


def test_glyph_pixmaps_carry_the_screen_pixel_ratio(qapp):
    pixmap = GUI._glyph_pixmap(GUI.STOP_ICON_PT)
    ratio = float(qapp.devicePixelRatio())
    assert pixmap.devicePixelRatio() == ratio
    # The backing store is denser than the logical size — that is what
    # keeps the octagon crisp on a HiDPI display.
    assert pixmap.width() == round(GUI.STOP_ICON_PT * ratio)


def test_the_stop_sign_is_red_with_a_white_centre(qapp):
    image = GUI.stop_sign_icon(32).pixmap(32, 32).toImage()
    centre = image.pixelColor(16, 16)
    edge = image.pixelColor(16, 3)   # inside the octagon's flat top
    assert (centre.red(), centre.green(), centre.blue()) == (255, 255, 255)
    assert edge.red() > 200 and edge.green() < 100 and edge.blue() < 100


# ---------------------------------------------------------------------------
# Q2 §S1 — stopping is a local state change, immediately
# ---------------------------------------------------------------------------
def test_stop_freezes_the_row_where_it_stood(window):
    window._start_run([TILE], dict(SETTINGS))
    window._on_step_progress(EV.StepProgress(
        lat=TILE[0], lon=TILE[1], label="imagery", percent=42.0))
    _stop_button(window, TILE).click()

    state, label, percent = window._progress_states[TILE]
    assert (state, label) == ("stopped", "stopped")
    assert percent == 42.0, "the percent freezes where the stop caught it"
    assert _status_label(window, TILE).text() == "stopped"
    assert GUI.STOPPED_COLOR in _status_label(window, TILE).styleSheet()


def test_later_engine_events_for_a_stopped_tile_are_dropped(window):
    window._start_run([TILE], dict(SETTINGS))
    window._on_step_progress(EV.StepProgress(
        lat=TILE[0], lon=TILE[1], label="imagery", percent=42.0))
    window._cancel_tile_clicked(TILE)

    # Progress the engine emits before it reaches its cancel flag …
    window._on_step_progress(EV.StepProgress(
        lat=TILE[0], lon=TILE[1], label="mesh", percent=61.0))
    # … and its own late "stopped" notice.
    window._on_tile_state(EV.TileState(
        lat=TILE[0], lon=TILE[1], state="queued", label="stopped"))

    assert window._progress_states[TILE] == ("stopped", "stopped", 42.0)
    assert _stop_button(window, TILE).toolTip() == "Resume this tile"


def test_a_tile_that_finished_before_its_cancel_shows_done(window):
    window._start_run([TILE], dict(SETTINGS))
    window._cancel_tile_clicked(TILE)
    window._on_tile_state(EV.TileState(
        lat=TILE[0], lon=TILE[1], state="done", percent=100.0))
    assert window._progress_states[TILE][0] == "done"
    assert _status_label(window, TILE).text() == "done ✓"


def test_an_error_also_wins_over_a_stopped_row(window):
    window._start_run([TILE], dict(SETTINGS))
    window._cancel_tile_clicked(TILE)
    window._on_tile_state(EV.TileState(
        lat=TILE[0], lon=TILE[1], state="error", label="failed"))
    assert window._progress_states[TILE][0] == "error"


def test_the_map_badge_learns_the_stopped_state(window):
    window._start_run([TILE], dict(SETTINGS))
    window._cancel_tile_clicked(TILE)
    assert window.map._progress[TILE][0] == "stopped"


def test_a_stopped_tiles_clock_freezes(window):
    window._start_run([TILE], dict(SETTINGS))
    window._on_tile_clocks(EV.TileClocks(
        rows=[[TILE[0], TILE[1], 30.0, 90.0, False]]))
    window._cancel_tile_clicked(TILE)
    assert window._tile_clocks[TILE] == (30.0, None, True)

    # The engine keeps counting; the row does not.
    window._on_tile_clocks(EV.TileClocks(
        rows=[[TILE[0], TILE[1], 45.0, 75.0, False]]))
    assert window._tile_clocks[TILE] == (30.0, None, True)


# ---------------------------------------------------------------------------
# Q2 §S2/§S3 — the resume control and its queue
# ---------------------------------------------------------------------------
def test_resume_while_idle_rebuilds_with_the_runs_own_settings(make_window):
    window = make_window()
    window._start_run([TILE], dict(SETTINGS))
    window._cancel_tile_clicked(TILE)
    window._building = False
    # The toolbar has moved on since the run started — resume must not
    # adopt it.
    window.imagery_combo.setCurrentText("OSM")
    window.zl_combo.setCurrentText("17")
    make_window.enqueued.clear()

    _stop_button(window, TILE).click()

    assert len(make_window.enqueued) == 1
    tiles, kwargs = make_window.enqueued[0]
    assert tiles == [TILE]
    assert kwargs["provider"] == "BI" and kwargs["zoomlevel"] == 15


def test_resume_while_busy_queues_the_tile(window):
    window._start_run([TILE, OTHER], dict(SETTINGS))
    window._cancel_tile_clicked(TILE)
    _stop_button(window, TILE).click()

    assert window._resume_queue == [TILE]
    assert window._progress_states[TILE][1] == "resumes after current run"
    assert _status_label(window, TILE).text() == "resumes after current run"
    # A queued-for-resume row offers stop again — that is how it comes back.
    assert _stop_button(window, TILE).toolTip() == "Stop this tile"


def test_the_resume_queue_keeps_press_order_without_duplicates(window):
    window._start_run([TILE, OTHER], dict(SETTINGS))
    for tile in (TILE, OTHER):
        window._cancel_tile_clicked(tile)
        window._resume_tile_clicked(tile)
    # Resuming a tile that is already waiting adds nothing.
    window._resume_tile_clicked(TILE)
    assert window._resume_queue == [TILE, OTHER]


def test_stopping_a_queued_resume_returns_it_to_stopped(window):
    window._start_run([TILE], dict(SETTINGS))
    window._cancel_tile_clicked(TILE)
    window._resume_tile_clicked(TILE)
    assert window._resume_queue == [TILE]

    _stop_button(window, TILE).click()
    assert window._resume_queue == []
    assert window._progress_states[TILE][0] == "stopped"


def test_run_end_starts_one_follow_up_run(make_window):
    window = make_window()
    window._start_run([TILE, OTHER], dict(SETTINGS))
    window._cancel_tile_clicked(TILE)
    window._resume_tile_clicked(TILE)
    make_window.enqueued.clear()

    window._on_run_done(EV.RunDone(done_count=1, error_count=0))

    assert len(make_window.enqueued) == 1, "exactly one follow-up run"
    tiles, kwargs = make_window.enqueued[0]
    assert tiles == [TILE]
    assert kwargs["provider"] == "BI" and kwargs["zoomlevel"] == 15
    assert window._resume_queue == []
    assert window._building is True


def test_a_wholesale_stop_drops_the_resume_queue(make_window):
    window = make_window()
    window._start_run([TILE, OTHER], dict(SETTINGS))
    window._cancel_tile_clicked(TILE)
    window._resume_tile_clicked(TILE)
    make_window.enqueued.clear()

    window.request_stop()
    window._on_run_done(EV.RunDone(done_count=0, cancelled=True))

    assert window._resume_queue == []
    assert make_window.enqueued == [], "a stopped run starts nothing"


def test_stopped_rows_and_their_buttons_survive_the_run_end(window,
                                                            monkeypatch):
    """The 5 s linger clears the Activity box — except the rows the user
    stopped, which are the handle on a tile they still mean to build."""
    deferred = []

    class _CapturedTimer:
        """Only the linger's singleShot is of interest here; the window's
        own timers were built during construction."""

        @staticmethod
        def singleShot(milliseconds, callback):
            deferred.append((milliseconds, callback))

    monkeypatch.setattr(GUI, "QTimer", _CapturedTimer)
    window._start_run([TILE, OTHER], dict(SETTINGS))
    window._cancel_tile_clicked(TILE)
    window._on_tile_state(EV.TileState(
        lat=OTHER[0], lon=OTHER[1], state="done", percent=100.0))
    window._on_run_done(EV.RunDone(done_count=1, error_count=0))

    revert = [fn for ms, fn in deferred if ms == 5000][-1]
    revert()

    assert set(window._tile_rows) == {TILE}
    assert window._progress_states == {TILE: ("stopped", "stopped", 0)}
    assert window.activity_group.isHidden() is False
    assert _stop_button(window, TILE).toolTip() == "Resume this tile"
    # The settings a resume needs outlive the run too.
    assert window._run_settings[TILE]["zoomlevel"] == 15


def test_a_finished_row_keeps_no_button(window):
    window._start_run([TILE], dict(SETTINGS))
    window._on_tile_state(EV.TileState(
        lat=TILE[0], lon=TILE[1], state="done", percent=100.0))
    button = _stop_button(window, TILE)
    assert button.isEnabled() is False
    assert button.isHidden() is True
