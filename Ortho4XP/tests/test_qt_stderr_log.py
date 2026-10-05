"""The Qt window persists engine stderr, one file per build run.

The file rules (run shift, header, size guard, never-raise) are tested
headless in ``tests/test_engine_stderr_log.py``.  This file checks the
window's side: the tee is installed as ``sys.stderr``, and the build
request that opens a run is THE run boundary — a fresh
``engine-stderr.log`` under a run header, the previous file shifted to
``engine-stderr.1.log`` (twin: ``BuildModel.sendProtocolBuild``).
"""

import json
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest  # noqa: E402

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

import O4_File_Names as FNAMES  # noqa: E402
import O4_Engine_Stderr_Log as STDLOG  # noqa: E402
import O4_Qt_GUI as GUI  # noqa: E402

SETTINGS = {
    "provider": "TEST_PROVIDER", "zoomlevel": 16,
    "do_vector": True, "do_imagery": True, "do_overlays": True,
}


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
    monkeypatch.setattr(FNAMES, "_data_root_override", str(tmp_path))
    import O4_UI_Utils as UI
    saved_stdout, saved_stderr = sys.stdout, sys.stderr
    win = GUI.MainWindow()
    # Read HERE: pytest's capture swaps ``sys.stderr`` back between the
    # fixture and the test body, so the tests below write to the tee itself.
    win.installed_stderr = sys.stderr
    monkeypatch.setattr(win._session, "enqueue_build",
                        lambda tiles, **kwargs: True)
    try:
        yield win
    finally:
        win._building = False
        win.close()
        win.deleteLater()
        UI.engine_session = None
        sys.stdout, sys.stderr = saved_stdout, saved_stderr


def _log_text(tmp_path, name="engine-stderr.log"):
    with open(str(tmp_path / "logs" / name), encoding="utf-8",
              newline="") as handle:
        return handle.read()


def test_the_window_installs_the_tee(window, tmp_path):
    assert isinstance(window.installed_stderr, STDLOG.EngineStderrLog)
    assert window.installed_stderr is window._stderr_log
    window._stderr_log.write("RuntimeWarning: from the engine\n")
    assert "RuntimeWarning: from the engine" in _log_text(tmp_path)


def test_the_build_request_is_the_run_boundary(window, tmp_path):
    window._stderr_log.write("idle warning before the run\n")
    window._start_run_now([(38, -9), (25, 51)], dict(SETTINGS))
    window._stderr_log.write("RuntimeWarning: from this run\n")
    lines = _log_text(tmp_path).split("\n")
    assert lines[0].startswith("=== engine run ")
    assert " | engine %s | 2 tiles: +38-009 +25+051" % (
        GUI.O4_Build_Info.build_info().engine) in lines[0]
    assert " === app " in lines[0]
    assert lines[1] == "RuntimeWarning: from this run"
    assert "idle warning before the run" in _log_text(
        tmp_path, "engine-stderr.1.log")


def test_tiles_queued_into_the_run_are_a_line_not_a_new_file(
        window, tmp_path):
    window._start_run_now([(38, -9)], dict(SETTINGS))
    window._queue_into_running_build_now(
        [(39, -9)], "TEST_PROVIDER", 16, True, True, True)
    text = _log_text(tmp_path)
    assert text.startswith("=== engine run ")
    assert "=== queued into this run " in text
    assert text.rstrip("\n").endswith("=== 1 tile: +39-009")
    assert sorted(os.listdir(str(tmp_path / "logs"))) == ["engine-stderr.log"]
