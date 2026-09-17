"""The Qt window reports a per-airport auto-patch death, like the mac app.

``AutoPatchFailed`` is the DIAGNOSIS event (H1, protocol 1.7): it names
the airport, the stage it died at and the cause.  The mac app prints it
on its console the moment it arrives (``BuildModel.swift``, ``case
.autoPatchFailed``); the Qt handler table did not carry the event at
all, so the Qt window showed a red row and nothing else.

Offscreen, no engine: the event is handed to the window through
``_on_engine_event``, the seam the other Qt tests drive.
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
from o4_engine import events as EV  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    yield QApplication.instance() or QApplication([])


@pytest.fixture
def window(qapp, tmp_path, monkeypatch):
    prefs_path = str(tmp_path / "prefs.json")
    with open(prefs_path, "w") as handle:
        # An EXISTING prefs file: an absent one arms the onboarding
        # wizard, whose modal exec would sit there forever headless.
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
        win._building = False
        win.close()
        win.deleteLater()
        UI.engine_session = None
        sys.stdout = saved_stdout


def test_the_event_is_in_the_handler_table(window):
    """An unhandled event is dropped silently — the defect itself."""
    assert EV.AutoPatchFailed in window._event_handlers


def test_a_dead_airport_is_named_on_the_console(window, capsys):
    """The line is a pipeline ``print``: the window's stdout tee is what
    puts it on the console drawer, so stdout is the seam under test."""
    capsys.readouterr()
    window._on_engine_event(EV.AutoPatchFailed(
        airport="HECA", stage="build", error="no runway data",
        lat=30, lon=31))
    text = capsys.readouterr().out
    assert (
        "*** Tile +30+031: airport HECA failed at the build stage "
        "— no runway data" in text
    )


def test_the_wording_matches_the_mac_app(window):
    """Same sentence, same tile key, in both UIs.

    The mac source is the reference: a rewording on one side only is
    exactly the parity gap this handler closed.
    """
    swift = os.path.join(
        os.path.dirname(__file__), "..", "..",
        "Sources", "XPTerrainBuilder", "BuildModel.swift")
    if not os.path.exists(swift):
        pytest.skip("Swift sources not present in this tree")
    with open(swift) as handle:
        source = handle.read()
    assert '"*** Tile \\(coord.key): airport \\(airport) failed at the "' \
        in source
    assert '+ "\\(stage) stage — \\(error)")' in source
