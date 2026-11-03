"""#1351: the Qt slow-step alert — non-modal, the engine's words verbatim,
refreshed in place, closed on ``resolved``, and its answers routed like
the mac app's (``BuildModel.answerSlowStep``).

Offscreen, no engine: events are handed to the window through
``_on_engine_event``, the seam the other Qt tests drive.
"""

import json
import os
import sys
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest  # noqa: E402

pytest.importorskip("PySide6")

import O4_Qt_GUI as GUI  # noqa: E402
from o4_engine import events as EV  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

SWIFT = Path(__file__).resolve().parents[2] / "Sources"


def _event(**kw):
    base = dict(lat=56, lon=-4, step_key="vector",
                title="Tile +56-004: the vector data step is slow",
                message="Downloading…\n\nRemote.\n\nAbout 3 min.",
                options=("continue", "coarser", "cancel"),
                option_labels=("Continue", "Use coarser data",
                               "Cancel this tile"))
    base.update(kw)
    return EV.SlowStep(**base)


@pytest.fixture(scope="module")
def qapp():
    yield QApplication.instance() or QApplication([])


@pytest.fixture
def window(qapp, tmp_path, monkeypatch):
    prefs_path = str(tmp_path / "prefs.json")
    with open(prefs_path, "w", encoding="utf-8", newline="") as handle:
        json.dump({"output_dir": str(tmp_path)}, handle)
    monkeypatch.setattr(GUI, "PREFS_FILE", prefs_path)
    monkeypatch.setattr(
        GUI, "TILE_SCAN_CACHE_FILE", str(tmp_path / "tile-scan.json"))
    import O4_UI_Utils as UI
    saved_stdout = sys.stdout
    win = GUI.MainWindow()
    monkeypatch.setattr(win, "refresh_tiles", lambda: None)
    monkeypatch.setattr(win, "_refresh_scenery_packs", lambda: None)
    try:
        yield win
    finally:
        for box in list(win._slow_step_boxes.values()):
            box.close()
        win._building = False
        win.close()
        win.deleteLater()
        UI.engine_session = None
        sys.stdout = saved_stdout


def _button(box, text):
    return [b for b in box.buttons() if b.text() == text][0]


def test_the_event_is_in_the_handler_table(window):
    assert EV.SlowStep in window._event_handlers


def test_one_box_per_step_refreshed_in_place_and_closed(window):
    window._on_engine_event(_event())
    [box] = window._slow_step_boxes.values()
    assert not box.isModal()
    # the platform orders the buttons by role; the words are the engine's
    assert sorted(b.text() for b in box.buttons()) == sorted(
        ["Continue", "Use coarser data", "Cancel this tile"])
    window._on_engine_event(_event(message="Later words."))
    assert list(window._slow_step_boxes.values()) == [box]
    assert box.informativeText() == "Later words."
    window._on_engine_event(EV.SlowStep(lat=56, lon=-4, step_key="vector",
                                        resolved=True))
    assert window._slow_step_boxes == {}


@pytest.mark.parametrize("label,choice", [("Continue", "continue"),
                                          ("Use coarser data", "coarser")])
def test_the_answers_go_to_the_engine(window, monkeypatch, label, choice):
    sent = []
    monkeypatch.setattr(window._session, "slow_step_choice",
                        lambda *a: sent.append(a) or True)
    window._on_engine_event(_event())
    [box] = window._slow_step_boxes.values()
    _button(box, label).click()
    assert sent == [(56, -4, choice)] and window._slow_step_boxes == {}


def test_cancel_is_the_rows_own_stop(window, monkeypatch):
    stopped, sent = [], []
    monkeypatch.setattr(window, "_cancel_tile_clicked", stopped.append)
    monkeypatch.setattr(window._session, "slow_step_choice",
                        lambda *a: sent.append(a))
    window._on_engine_event(_event())
    [box] = window._slow_step_boxes.values()
    _button(box, "Cancel this tile").click()
    assert stopped == [(56, -4)] and sent == []


def test_the_mac_app_shows_the_same_event_the_same_way():
    """Neither app holds copy: both show the engine's title, message and
    button words, and route "cancel" to the row's own stop."""
    model = (SWIFT / "XPTerrainBuilder" / "BuildModel.swift").read_text(
        encoding="utf-8")
    banner = (SWIFT / "XPTerrainBuilder" / "SlowStepBanner.swift").read_text(
        encoding="utf-8")
    assert "case .slowStep(let step)" in model
    assert 'if choice == "cancel" {' in model and "cancelTile(" in model
    assert "client?.slowStepChoice(" in model
    for shown in ("step.title", "step.message", "button.label"):
        assert shown in banner, shown
