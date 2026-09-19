"""The Qt front end's boundary-airport preflight and its one dialog.

Spec ``docs/specs/insets-follow-patch-set-spec.md`` §C.2-§C.4 / §C.7,
owner RULINGS 2026-09-18h (insets half) and 18i: before it enqueues any
build the Qt window asks the engine which airports' AIRSIDE claims cross
into tiles the user did not select, and — unless the answer is empty, an
error, or already remembered — shows ONE modal sheet for the whole
batch.

Headless: ``QT_QPA_PLATFORM=offscreen``, an isolated prefs file, no
network and no engine.  The preflight command and ``enqueue_build`` are
recorded rather than run, and the completion event is delivered through
``_on_engine_event`` — the same seam the other Qt tests use (the real
bridge marshals it onto the GUI thread; the handler is what runs there).

The PREFS_FILE monkeypatch BEFORE construction is mandatory: the window
loads prefs in ``__init__`` and writes them on close, and an absent file
arms the onboarding wizard, whose modal exec would sit there forever.
"""

import json
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest  # noqa: E402

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

import O4_Qt_Boundary_Dialog as BD  # noqa: E402
import O4_Qt_GUI as GUI  # noqa: E402
from o4_engine import events as EV  # noqa: E402


TILE = (38, -10)
NEIGHBOUR = (38, -9)
SETTINGS = {
    "provider": "BI",
    "zoomlevel": 16,
    "do_vector": True,
    "do_imagery": True,
    "do_overlays": False,
}

AIRPORT = {
    "icao": "LPMT",
    "name": "Montijo",
    "home": [38, -10],
    "neighbours": [[38, -9]],
    "crossing_m": 623.4,
}


@pytest.fixture(scope="module")
def qapp():
    yield QApplication.instance() or QApplication([])


# ---------------------------------------------------------------------
# The dialog itself
# ---------------------------------------------------------------------
def _dialog(airports=(AIRPORT,), add_tiles=(NEIGHBOUR,),
            default_choice="neighbour"):
    return BD.BoundaryAirportsDialog(list(airports), list(add_tiles),
                                     default_choice=default_choice)


def test_dialog_copy_is_the_ruled_copy(qapp):
    dialog = _dialog()
    try:
        assert dialog.windowTitle() == "Airports on a tile edge"
        assert BD.BODY == (
            "These airports extend into tiles you haven't selected. "
            "To grade a whole airport, the adjacent tiles have to be "
            "built too.")
        assert BD.FOOTNOTE == (
            "Skipped airports keep ungraded terrain in this build.")
        assert dialog.neighbour_btn.text() == "Build adjacent tiles too (1)"
        assert dialog.skip_btn.text() == "Skip these airports' patches"
        assert dialog.cancel_btn.text() == "Cancel build"
        assert dialog.remember_check.text() == "Remember my choice"
        assert not dialog.remember_check.isChecked()
    finally:
        dialog.deleteLater()


def test_a_row_names_the_airport_its_distance_and_the_tiles(qapp):
    dialog = _dialog()
    try:
        # Rounded to 10 m; the tile spells as X-Plane spells it.
        assert dialog.rows[0].text() == (
            "LPMT Montijo — extends 620 m into +38-009")
    finally:
        dialog.deleteLater()
    assert BD.tile_label((38, -9)) == "+38-009"
    assert BD.crossing_metres(94.0) == 90
    assert BD.crossing_metres(95.0) == 100
    assert BD.crossing_metres(None) == 0


def test_the_added_tile_count_is_the_engines_add_tiles(qapp):
    dialog = _dialog(add_tiles=[(38, -9), (39, -9), (39, -10)])
    try:
        assert dialog.neighbour_btn.text() == "Build adjacent tiles too (3)"
    finally:
        dialog.deleteLater()


def test_the_default_button_is_the_events_default_choice(qapp):
    """Preselected action is ENGINE-owned, never hardcoded (18i (2))."""
    dialog = _dialog(default_choice="neighbour")
    try:
        assert dialog.default_button is dialog.neighbour_btn
        assert dialog.neighbour_btn.isDefault()
        assert not dialog.skip_btn.isDefault()
    finally:
        dialog.deleteLater()
    dialog = _dialog(default_choice="skip")
    try:
        assert dialog.default_button is dialog.skip_btn
        assert dialog.skip_btn.isDefault()
        assert not dialog.neighbour_btn.isDefault()
    finally:
        dialog.deleteLater()
    # An unknown / missing value falls back to the ruled default.
    dialog = _dialog(default_choice="")
    try:
        assert dialog.default_choice == "neighbour"
    finally:
        dialog.deleteLater()


def test_the_buttons_answer_a_policy_and_escape_cancels(qapp):
    for (button, expected) in (("neighbour_btn", "neighbour"),
                               ("skip_btn", "skip")):
        dialog = _dialog()
        try:
            getattr(dialog, button).click()
            assert dialog.choice == expected
            assert dialog.remember is False
        finally:
            dialog.deleteLater()
    dialog = _dialog()
    try:
        dialog.cancel_btn.click()
        assert dialog.choice is None
    finally:
        dialog.deleteLater()
    dialog = _dialog()
    try:
        dialog.reject()                      # what Escape does
        assert dialog.choice is None
    finally:
        dialog.deleteLater()


def test_remember_my_choice_is_reported_with_the_answer(qapp):
    dialog = _dialog()
    try:
        dialog.remember_check.setChecked(True)
        dialog.skip_btn.click()
        assert (dialog.choice, dialog.remember) == ("skip", True)
    finally:
        dialog.deleteLater()
    assert BD.CFG_VALUE_FOR_POLICY == {"neighbour": "Build adjacent",
                                       "skip": "Skip patch"}


# ---------------------------------------------------------------------
# The flow
# ---------------------------------------------------------------------
@pytest.fixture
def make_window(qapp, tmp_path, monkeypatch):
    prefs_path = str(tmp_path / "prefs.json")
    with open(prefs_path, "w") as handle:
        json.dump({"output_dir": str(tmp_path)}, handle)
    monkeypatch.setattr(GUI, "PREFS_FILE", prefs_path)
    import O4_UI_Utils as UI

    saved_stdout = sys.stdout
    windows = []
    state = {"asked": [], "enqueued": []}

    def _make():
        win = GUI.MainWindow()
        win.prefs["output_dir"] = str(tmp_path)
        monkeypatch.setattr(win, "refresh_tiles", lambda: None)
        monkeypatch.setattr(
            win._session, "enqueue_build",
            lambda tiles, **kwargs: state["enqueued"].append(
                (sorted(tiles), kwargs)) or True)
        monkeypatch.setattr(
            win._session, "boundary_airports",
            lambda tiles=None: state["asked"].append(list(tiles or []))
            or {"status": "started", "request_id": len(state["asked"])})
        windows.append(win)
        return win

    yield _make, state
    for win in windows:
        win._building = False
        win.close()
        win.deleteLater()
    UI.engine_session = None
    sys.stdout = saved_stdout


def _ready(request_id=1, **kwargs):
    return EV.BoundaryAirportsReady(request_id=request_id, **kwargs)


def _no_dialog(monkeypatch):
    def _refuse(*a, **k):
        raise AssertionError("the dialog was shown")
    monkeypatch.setattr(GUI.QTBOUND, "BoundaryAirportsDialog", _refuse)


class _FakeDialog:
    """Stands in for the modal sheet: answers, never runs an event loop."""

    calls = []
    answer = ("neighbour", False)

    def __init__(self, airports, add_tiles, default_choice="neighbour",
                 parent=None):
        type(self).calls.append((list(airports), list(add_tiles),
                                 default_choice))
        self.choice, self.remember = type(self).answer

    def exec(self):
        return 1


@pytest.fixture
def fake_dialog(monkeypatch):
    _FakeDialog.calls = []
    _FakeDialog.answer = ("neighbour", False)
    monkeypatch.setattr(GUI.QTBOUND, "BoundaryAirportsDialog", _FakeDialog)
    return _FakeDialog


def test_the_preflight_runs_before_any_build_is_enqueued(make_window,
                                                         monkeypatch):
    make, state = make_window
    win = make()
    _no_dialog(monkeypatch)
    win._start_run([TILE], dict(SETTINGS))
    # Nothing is enqueued until the preflight answers.
    assert state["asked"] == [[[38, -10]]]
    assert state["enqueued"] == []
    assert win._building is False

    win._on_engine_event(_ready(airports=[]))
    assert win._building is True
    assert state["enqueued"] and state["enqueued"][0][0] == [TILE]
    assert "boundary_policy" not in state["enqueued"][0][1]


def test_a_preflight_error_builds_the_selected_tiles_as_they_are(
        make_window, monkeypatch):
    make, state = make_window
    win = make()
    _no_dialog(monkeypatch)
    win._start_run([TILE], dict(SETTINGS))
    win._on_engine_event(_ready(error="CIFP unreadable",
                                airports=[dict(AIRPORT)],
                                add_tiles=[[38, -9]]))
    assert state["enqueued"][0][0] == [TILE]
    assert "boundary_policy" not in state["enqueued"][0][1]


def test_a_remembered_answer_is_applied_without_asking(make_window,
                                                       monkeypatch):
    make, state = make_window
    win = make()
    _no_dialog(monkeypatch)
    win._start_run([TILE], dict(SETTINGS))
    win._on_engine_event(_ready(airports=[dict(AIRPORT)],
                                add_tiles=[[38, -9]],
                                remembered="skip"))
    (tiles, kwargs) = state["enqueued"][0]
    assert tiles == [TILE]
    assert kwargs["boundary_policy"] == "skip"


def test_a_remembered_neighbour_answer_adds_the_tiles(make_window,
                                                      monkeypatch):
    make, state = make_window
    win = make()
    _no_dialog(monkeypatch)
    win.map.set_selection({TILE})
    win._start_run([TILE], dict(SETTINGS))
    win._on_engine_event(_ready(airports=[dict(AIRPORT)],
                                add_tiles=[[38, -9]],
                                remembered="neighbour"))
    (tiles, kwargs) = state["enqueued"][0]
    assert tiles == sorted([TILE, NEIGHBOUR])
    assert kwargs["boundary_policy"] == "neighbour"
    # The added tile is a tile of this run like any the user picked: same
    # provider and zoom, visible in the selection.
    assert kwargs["provider"] == SETTINGS["provider"]
    assert kwargs["zoomlevel"] == SETTINGS["zoomlevel"]
    assert NEIGHBOUR in win.map.selection()
    assert NEIGHBOUR in win._progress_states
    assert win._run_settings[NEIGHBOUR]["provider"] == SETTINGS["provider"]


def test_the_dialog_is_shown_once_for_the_whole_batch(make_window,
                                                      fake_dialog):
    make, state = make_window
    win = make()
    win._start_run([TILE, (39, -10)], dict(SETTINGS))
    win._on_engine_event(_ready(
        airports=[dict(AIRPORT), dict(AIRPORT, icao="LPPT")],
        add_tiles=[[38, -9]], default_choice="neighbour"))
    assert len(fake_dialog.calls) == 1
    (airports, add_tiles, default_choice) = fake_dialog.calls[0]
    assert [a["icao"] for a in airports] == ["LPMT", "LPPT"]
    assert add_tiles == [NEIGHBOUR]
    assert default_choice == "neighbour"
    (tiles, kwargs) = state["enqueued"][0]
    assert tiles == sorted([TILE, (39, -10), NEIGHBOUR])
    assert kwargs["boundary_policy"] == "neighbour"


def test_skip_enqueues_only_the_selected_tiles(make_window, fake_dialog):
    make, state = make_window
    win = make()
    fake_dialog.answer = ("skip", False)
    win._start_run([TILE], dict(SETTINGS))
    win._on_engine_event(_ready(airports=[dict(AIRPORT)],
                                add_tiles=[[38, -9]]))
    (tiles, kwargs) = state["enqueued"][0]
    assert tiles == [TILE]
    assert kwargs["boundary_policy"] == "skip"
    assert NEIGHBOUR not in win.map.selection()


def test_cancel_build_enqueues_nothing(make_window, fake_dialog):
    make, state = make_window
    win = make()
    fake_dialog.answer = (None, False)
    win._start_run([TILE], dict(SETTINGS))
    win._on_engine_event(_ready(airports=[dict(AIRPORT)],
                                add_tiles=[[38, -9]]))
    assert state["enqueued"] == []
    assert win._building is False


def test_remember_my_choice_writes_the_app_setting(make_window,
                                                   fake_dialog,
                                                   monkeypatch):
    make, state = make_window
    win = make()
    import O4_Settings_Model as SM

    written = []
    applied = []
    monkeypatch.setattr(SM, "write_global",
                        lambda values, *a, **k: written.append(dict(values)))
    monkeypatch.setattr(SM, "apply_runtime",
                        lambda values: applied.append(dict(values)) or [])
    fake_dialog.answer = ("skip", True)
    win._start_run([TILE], dict(SETTINGS))
    win._on_engine_event(_ready(airports=[dict(AIRPORT)],
                                add_tiles=[[38, -9]]))
    # ONE mechanism: the settings model's own global write.
    assert written == [{"auto_patch_boundary": "Skip patch"}]
    assert applied == [{"auto_patch_boundary": "Skip patch"}]
    assert state["enqueued"][0][1]["boundary_policy"] == "skip"


def test_an_unticked_box_writes_nothing(make_window, fake_dialog,
                                        monkeypatch):
    make, _state = make_window
    win = make()
    import O4_Settings_Model as SM

    monkeypatch.setattr(SM, "write_global", lambda *a, **k: pytest.fail(
        "the choice was persisted without the box"))
    fake_dialog.answer = ("neighbour", False)
    win._start_run([TILE], dict(SETTINGS))
    win._on_engine_event(_ready(airports=[dict(AIRPORT)],
                                add_tiles=[[38, -9]]))


def test_a_stale_request_id_is_ignored(make_window, monkeypatch):
    make, state = make_window
    win = make()
    _no_dialog(monkeypatch)
    win._start_run([TILE], dict(SETTINGS))
    win._on_engine_event(_ready(request_id=99, airports=[]))
    assert state["enqueued"] == []
    win._on_engine_event(_ready(request_id=1, airports=[]))
    assert len(state["enqueued"]) == 1
    # The answered request is retired: a repeat of it changes nothing.
    win._on_engine_event(_ready(request_id=1, airports=[]))
    assert len(state["enqueued"]) == 1


def test_a_silent_preflight_times_out_and_builds_anyway(make_window,
                                                        monkeypatch):
    make, state = make_window
    win = make()
    _no_dialog(monkeypatch)
    win._start_run([TILE], dict(SETTINGS))
    assert win._boundary_pending
    win._boundary_preflight_timeout(next(iter(win._boundary_pending)))
    assert state["enqueued"][0][0] == [TILE]
    assert "boundary_policy" not in state["enqueued"][0][1]
    assert not win._boundary_pending


def test_an_engine_without_the_preflight_builds_immediately(make_window,
                                                            monkeypatch):
    """A front end newer than its engine must not stop the build."""
    make, state = make_window
    win = make()
    _no_dialog(monkeypatch)

    def _unsupported(tiles=None):
        raise AttributeError("boundary_airports")
    monkeypatch.setattr(win._session, "boundary_airports", _unsupported)
    win._start_run([TILE], dict(SETTINGS))
    assert state["enqueued"][0][0] == [TILE]
    assert win._building is True


def test_a_batch_queued_into_a_running_build_asks_too(make_window,
                                                      fake_dialog):
    make, state = make_window
    win = make()
    win._start_run([TILE], dict(SETTINGS))
    win._on_engine_event(_ready(request_id=1, airports=[]))
    assert win._building is True
    state["enqueued"].clear()

    win._queue_into_running_build([(39, -10)], **SETTINGS)
    assert state["asked"][-1] == [[39, -10]]
    assert state["enqueued"] == []
    win._on_engine_event(_ready(request_id=2,
                                airports=[dict(AIRPORT, icao="LPPT")],
                                add_tiles=[[39, -9]]))
    (tiles, kwargs) = state["enqueued"][0]
    assert tiles == sorted([(39, -10), (39, -9)])
    assert kwargs["boundary_policy"] == "neighbour"


def test_a_resumed_tile_asks_too(make_window, monkeypatch):
    make, state = make_window
    win = make()
    _no_dialog(monkeypatch)
    win._start_run([TILE], dict(SETTINGS))
    win._on_engine_event(_ready(request_id=1, airports=[]))
    win._progress_states[TILE] = ("stopped", "stopped", 40)
    win._building = False
    state["asked"].clear()
    state["enqueued"].clear()

    win._resume_tile_clicked(TILE)
    assert state["asked"] == [[[38, -10]]]
    assert state["enqueued"] == []
    win._on_engine_event(
        _ready(request_id=next(iter(win._boundary_pending)), airports=[]))
    assert state["enqueued"][0][0] == [TILE]


# ---------------------------------------------------------------------
# The setting the "Remember my choice" tick writes
# ---------------------------------------------------------------------
def test_the_settings_window_offers_the_boundary_choice(qapp, tmp_path,
                                                        monkeypatch):
    """The remembered answer is a normal setting, changeable later."""
    monkeypatch.chdir(tmp_path)          # no real global cfg is read
    from PySide6.QtWidgets import QComboBox
    from O4_Qt_Settings import SettingsWindow

    win = SettingsWindow(prefs={}, tiles=[], custom_build_dir="")
    try:
        row = win.rows["auto_patch_boundary"]
        assert row.setting.label == "Airports on a tile edge"
        assert row.setting.scope == "app"
        combo = row.control
        assert isinstance(combo, QComboBox), type(combo).__name__
        values = [combo.itemData(i) for i in range(combo.count())]
        labels = [combo.itemText(i) for i in range(combo.count())]
        assert values == ["Ask", "Build adjacent", "Skip patch"]
        assert labels == ["Ask me each time",
                          "Build the adjacent tiles too",
                          "Skip those airports' patches"]
        assert row.value() == "Ask"          # registry default
        # The dialog's tick writes exactly these two values.
        assert set(BD.CFG_VALUE_FOR_POLICY.values()) <= set(values)
    finally:
        win.close()


def test_two_asks_in_flight_do_not_strand_each_other(make_window,
                                                     monkeypatch):
    """The resume queue can have several batches waiting to be answered.

    A single-slot pending record made the second ask supersede the first,
    and that batch was never built.
    """
    make, state = make_window
    win = make()
    _no_dialog(monkeypatch)
    win._start_run([TILE], dict(SETTINGS))
    win._building = True                     # the run the first ask starts
    win._queue_into_running_build([(39, -10)], **SETTINGS)
    assert sorted(win._boundary_pending) == [1, 2]
    win._on_engine_event(_ready(request_id=2, airports=[]))
    win._on_engine_event(_ready(request_id=1, airports=[]))
    assert sorted(t for (tiles, _k) in state["enqueued"] for t in tiles) == [
        TILE, (39, -10)]


def test_the_resume_queue_starts_its_batches_in_order(make_window,
                                                      monkeypatch):
    """Batch 2 is queued into the run batch 1 started, never before it."""
    make, state = make_window
    win = make()
    _no_dialog(monkeypatch)
    other = dict(SETTINGS, zoomlevel=17)
    win._progress_states = {TILE: ("stopped", "stopped", 10),
                            (39, -10): ("stopped", "stopped", 10)}
    win._run_settings = {TILE: dict(SETTINGS), (39, -10): other}
    win._resume_queue = [TILE, (39, -10)]
    win._start_resume_queue()
    # Only the FIRST batch has been asked about so far.
    assert state["asked"] == [[[38, -10]]]
    win._on_engine_event(_ready(request_id=1, airports=[]))
    assert win._building is True
    assert state["asked"] == [[[38, -10]], [[39, -10]]]
    win._on_engine_event(_ready(request_id=2, airports=[]))
    assert [tiles for (tiles, _k) in state["enqueued"]] == [
        [TILE], [(39, -10)]]
    assert state["enqueued"][1][1]["zoomlevel"] == 17


def test_a_second_build_press_during_the_ask_starts_no_second_run(
        make_window, monkeypatch):
    make, state = make_window
    win = make()
    _no_dialog(monkeypatch)
    win.imagery_combo.addItems(["TEST_PROVIDER"])
    win.imagery_combo.setCurrentText("TEST_PROVIDER")
    win.zl_combo.setCurrentText("16")
    monkeypatch.setattr(win, "xplane_block_reason", lambda: None)
    said = []
    monkeypatch.setattr(win, "_status", said.append)
    win.map.set_selection({TILE})

    win.start_build()
    assert len(state["asked"]) == 1
    win.start_build()                        # impatient second press
    assert len(state["asked"]) == 1
    assert said and "tile edges" in said[-1]
    win._on_engine_event(_ready(request_id=1, airports=[]))
    assert len(state["enqueued"]) == 1
