"""Engine stderr is persisted by the Qt app, not just printed.

A Python ``RuntimeWarning`` (shapely, numpy) used to reach the terminal
the Qt app happened to be launched from and nowhere else.  The mac app
has persisted stderr since 2026-09-09 (``OrthoEngineClient.swift``,
``EngineStderrLog``: one appended file, session header, rotation at
20 MB by renaming to ``.1.log``); the Qt window now writes the same file
under its own writable data root.

Unit-level: ``_StderrTee`` is driven directly, so no window and no Qt
event loop are needed for the file rules.  One offscreen test checks the
tee is actually installed.
"""

import io
import json
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest  # noqa: E402

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication  # noqa: E402

import O4_File_Names as FNAMES  # noqa: E402
import O4_Qt_GUI as GUI  # noqa: E402


def test_the_original_stream_is_written_first(tmp_path):
    original = io.StringIO()
    tee = GUI._StderrTee(original, str(tmp_path / "logs" / "engine-stderr.log"))
    tee.write("RuntimeWarning: invalid value encountered\n")
    assert original.getvalue() == "RuntimeWarning: invalid value encountered\n"


def test_the_line_lands_in_the_log_under_a_session_header(tmp_path):
    path = str(tmp_path / "logs" / "engine-stderr.log")
    tee = GUI._StderrTee(io.StringIO(), path)
    tee.write("RuntimeWarning: invalid value encountered\n")
    tee.flush()
    with open(path) as handle:
        text = handle.read()
    assert text.startswith("=== engine session ")
    assert "RuntimeWarning: invalid value encountered" in text


def test_the_log_appends_across_sessions(tmp_path):
    path = str(tmp_path / "logs" / "engine-stderr.log")
    GUI._StderrTee(io.StringIO(), path).write("first\n")
    GUI._StderrTee(io.StringIO(), path).write("second\n")
    with open(path) as handle:
        text = handle.read()
    assert "first" in text and "second" in text
    assert text.count("=== engine session ") == 2


def test_it_rotates_at_the_cap_and_keeps_one_old_file(tmp_path):
    path = str(tmp_path / "logs" / "engine-stderr.log")
    tee = GUI._StderrTee(io.StringIO(), path, max_bytes=200)
    for _ in range(20):
        tee.write("x" * 40 + "\n")
    old = str(tmp_path / "logs" / "engine-stderr.1.log")
    assert os.path.exists(old), "the rotated file is the reason for the cap"
    # The live file is recreated lazily, on the next line written.
    tee.write("after the rotation\n")
    assert os.path.getsize(path) <= 4000

    # A SECOND rotation replaces the old file rather than piling up.
    for _ in range(20):
        tee.write("y" * 40 + "\n")
    tee.write("after the second rotation\n")
    assert sorted(os.listdir(str(tmp_path / "logs"))) == [
        "engine-stderr.1.log", "engine-stderr.log"]


def test_the_cap_is_the_mac_apps_cap():
    assert GUI.ENGINE_STDERR_LOG_MAX_BYTES == 20 * 1024 * 1024


def test_an_unwritable_log_never_raises(tmp_path):
    """This object IS ``sys.stderr``: a logging failure must not take out
    the report of whatever was being logged."""
    blocked = tmp_path / "logs"
    blocked.write_text("not a directory")
    original = io.StringIO()
    tee = GUI._StderrTee(original, str(blocked / "engine-stderr.log"))
    tee.write("still reaches the terminal\n")
    tee.flush()
    assert original.getvalue() == "still reaches the terminal\n"


def test_the_path_is_under_the_data_root(tmp_path, monkeypatch):
    monkeypatch.setattr(FNAMES, "_data_root_override", str(tmp_path))
    assert GUI.engine_stderr_log_path() == os.path.join(
        str(tmp_path), "logs", "engine-stderr.log")


@pytest.fixture(scope="module")
def qapp():
    yield QApplication.instance() or QApplication([])


def test_the_window_installs_the_tee(qapp, tmp_path, monkeypatch):
    prefs_path = str(tmp_path / "prefs.json")
    with open(prefs_path, "w") as handle:
        json.dump({"output_dir": str(tmp_path)}, handle)
    monkeypatch.setattr(GUI, "PREFS_FILE", prefs_path)
    monkeypatch.setattr(
        GUI, "TILE_SCAN_CACHE_FILE", str(tmp_path / "tile-scan.json"))
    monkeypatch.setattr(FNAMES, "_data_root_override", str(tmp_path))
    import O4_UI_Utils as UI
    saved_stdout, saved_stderr = sys.stdout, sys.stderr
    win = GUI.MainWindow()
    try:
        assert isinstance(sys.stderr, GUI._StderrTee)
        sys.stderr.write("RuntimeWarning: from the engine\n")
        with open(str(tmp_path / "logs" / "engine-stderr.log")) as handle:
            assert "RuntimeWarning: from the engine" in handle.read()
    finally:
        win._building = False
        win.close()
        win.deleteLater()
        UI.engine_session = None
        sys.stdout, sys.stderr = saved_stdout, saved_stderr
