"""Issue #825, Qt half: an offscreen window fed a build's events shows the
step strip on the tile's row (the mapping itself: ``test_step_strip.py``).

Offscreen, no network, no engine: the session's build entry is recorded
rather than run, the seam ``test_qt_stop_resume.py`` uses.
"""

import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest  # noqa: E402

pytest.importorskip("PySide6")

import O4_Qt_GUI as GUI  # noqa: E402
import O4_Qt_Step_Strip as QTSTRIP  # noqa: E402
import O4_Step_Strip as STRIP  # noqa: E402
import O4_UI_Utils as UI  # noqa: E402
from o4_engine import events as EV  # noqa: E402
from PySide6.QtWidgets import QApplication, QLabel  # noqa: E402

TILE = (47, -123)



def test_qt_row_shows_the_steps(qt_window):
    window, tile = qt_window
    window._start_run([tile], {
        "provider": "BI", "zoomlevel": 15, "do_vector": True,
        "do_imagery": True, "do_overlays": False})
    label = window._tile_rows[tile][2].findChild(QLabel, "tile_steps")
    assert label is not None and not label.isHidden()
    assert "○ Map data" in label.text()

    where = dict(lat=tile[0], lon=tile[1])
    window._on_engine_event(EV.StepProgress(
        step_key="vector", label="vector data", **where))
    window._on_engine_event(EV.AutoPatchBegin(airports=("KSEA",), **where))
    window._on_engine_event(EV.AutoPatchProgress(
        airport="KSEA", done=65.0, total=100.0,
        label="Solving the surface (HiGHS LP)", **where))
    strip = window._step_strips[tile]
    assert [s for s, _t in STRIP.segments(strip)][:3] == [
        "done", "running", "waiting"]
    assert "KSEA — shaping runways (65 %)" in label.text()
    assert label.text() == QTSTRIP.strip_html(strip)

    window._cancel_tile_clicked(tile)
    window._on_engine_event(EV.StepProgress(step_key="mesh", **where))
    assert [s for s, _t in STRIP.segments(strip)][:3] == [
        "done", "stopped", "waiting"]


@pytest.fixture
def qt_window(tmp_path, monkeypatch):
    QApplication.instance() or QApplication([])
    prefs = tmp_path / "prefs.json"
    prefs.write_text("{}", encoding="utf-8", newline="")
    monkeypatch.setattr(GUI, "PREFS_FILE", str(prefs))
    saved_stdout = sys.stdout
    win = GUI.MainWindow()
    win.prefs["output_dir"] = str(tmp_path)
    monkeypatch.setattr(win, "refresh_tiles", lambda: None)
    monkeypatch.setattr(win._session, "enqueue_build",
                        lambda tiles, **kwargs: True)
    monkeypatch.setattr(win._session, "cancel_tile", lambda lat, lon: True)
    monkeypatch.setattr(win._session, "cancel", lambda: True)
    monkeypatch.setattr(win._session, "boundary_airports",
                        lambda tiles=None: None)
    try:
        yield win, TILE
    finally:
        win._building = False
        win.close()
        win.deleteLater()
        UI.engine_session = None
        sys.stdout = saved_stdout
