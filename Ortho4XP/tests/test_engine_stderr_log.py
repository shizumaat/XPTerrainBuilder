"""One ``engine-stderr.log`` per build run, five previous runs kept.

The file used to append across app sessions for weeks, and errors from an
old build were read as current (2026-10-05).  ``EngineStderrLog`` now
starts a fresh file at the build request that opens a run, shifts the
previous runs to ``engine-stderr.1.log`` … ``.5.log``, writes a run header,
and keeps the 20 MB guard inside a run.

Headless: the tee is driven directly, no window and no Qt.  The same cases
run against the mac twin in ``Tests/SceneryKitTests/
EngineStderrLogTests.swift``; ``tests/test_qt_stderr_log.py`` checks the
window installs the tee and calls it at the run boundary.
"""

import io
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import O4_Engine_Stderr_Log as STDLOG  # noqa: E402
import O4_File_Names as FNAMES  # noqa: E402


def _log(tmp_path, **kwargs):
    original = io.StringIO()
    path = str(tmp_path / "logs" / "engine-stderr.log")
    return STDLOG.EngineStderrLog(original, path, **kwargs), original


def _text(tmp_path, name="engine-stderr.log"):
    with open(str(tmp_path / "logs" / name), encoding="utf-8",
              newline="") as handle:
        return handle.read()


def _names(tmp_path):
    return sorted(os.listdir(str(tmp_path / "logs")))


def test_the_original_stream_is_written_first(tmp_path):
    tee, original = _log(tmp_path)
    tee.write("RuntimeWarning: invalid value encountered\n")
    assert original.getvalue() == "RuntimeWarning: invalid value encountered\n"


def test_lines_between_runs_land_under_a_session_header(tmp_path):
    _log(tmp_path)[0].write("first\n")
    _log(tmp_path)[0].write("second\n")
    text = _text(tmp_path)
    assert text.startswith("=== engine session ")
    assert "first\n" in text and "second\n" in text
    assert text.count("=== engine session ") == 2


def test_a_run_starts_a_fresh_file_under_the_run_header(tmp_path):
    tee, original = _log(tmp_path)
    tee.write("start-up warning\n")
    tee.start_run("1.0.378", "1.50.1815", ["+30+031", "+25+051"])
    tee.write("RuntimeWarning: from this run\n")
    lines = _text(tmp_path).split("\n")
    assert lines[0].startswith("=== engine run ")
    assert lines[0].endswith(
        "=== app 1.0.378 | engine 1.50.1815 | 2 tiles: +30+031 +25+051")
    assert lines[1] == "RuntimeWarning: from this run"
    assert "start-up warning" in _text(tmp_path, "engine-stderr.1.log")
    # The header is the LOG's, not the console's.
    assert "engine run" not in original.getvalue()


def test_the_header_text_is_the_mac_twins():
    assert STDLOG.run_header("1.0.378", "", ["+38-009"], stamp="T") == (
        "=== engine run T === app 1.0.378 | engine unknown | 1 tile: +38-009")
    assert STDLOG.queued_line(["+38-009", "+38-010"], stamp="T") == (
        "=== queued into this run T === 2 tiles: +38-009 +38-010")


def test_a_note_reaches_the_log_only(tmp_path):
    tee, original = _log(tmp_path)
    tee.start_run("a", "e", ["+00+000"])
    tee.note(STDLOG.queued_line(["+01+001"], stamp="T"))
    assert "=== queued into this run T === 1 tile: +01+001\n" in _text(tmp_path)
    assert original.getvalue() == ""


def test_five_runs_are_kept_and_the_oldest_is_dropped(tmp_path):
    tee, _ = _log(tmp_path)
    for run in range(1, 9):
        tee.start_run("a", "e", ["+00+000"])
        tee.write("run %d\n" % run)
    assert _names(tmp_path) == [
        "engine-stderr.1.log", "engine-stderr.2.log", "engine-stderr.3.log",
        "engine-stderr.4.log", "engine-stderr.5.log", "engine-stderr.log"]
    assert "run 8\n" in _text(tmp_path)
    for index in range(1, 6):
        assert "run %d\n" % (8 - index) in _text(
            tmp_path, "engine-stderr.%d.log" % index)


def test_the_size_guard_shifts_inside_a_run_and_the_run_continues(tmp_path):
    tee, _ = _log(tmp_path, max_bytes=200)
    tee.start_run("a", "e", ["+00+000"])
    for _ in range(40):
        tee.write("x" * 40 + "\n")
    tee.write("after the guard\n")
    live = _text(tmp_path)
    assert "=== engine run continued " in live
    assert "engine-stderr.1.log" in live
    assert len(live) < 600
    assert len(_names(tmp_path)) == 6, "a runaway run is bounded to the kept files"


def test_the_cap_and_the_count_are_the_mac_twins():
    assert STDLOG.ENGINE_STDERR_LOG_MAX_BYTES == 20 * 1024 * 1024
    assert STDLOG.ENGINE_STDERR_LOG_KEPT_RUNS == 5


def test_an_unwritable_log_never_raises_and_the_next_run_tries_again(tmp_path):
    """This object IS ``sys.stderr``: a logging failure must not take out
    the report of whatever was being logged."""
    blocked = tmp_path / "logs"
    blocked.write_text("not a directory", encoding="utf-8", newline="")
    tee, original = _log(tmp_path)
    tee.write("still reaches the terminal\n")
    tee.start_run("a", "e", [])
    tee.note("dropped")
    tee.flush()
    os.remove(str(blocked))
    tee.write("still disabled for this run\n")
    assert not os.path.exists(str(blocked))
    assert original.getvalue() == (
        "still reaches the terminal\nstill disabled for this run\n")
    tee.start_run("a", "e", ["+00+000"])
    tee.write("persisted again\n")
    assert "persisted again\n" in _text(tmp_path)


def test_a_shift_that_fails_disables_the_run_and_never_raises(
        tmp_path, monkeypatch):
    tee, original = _log(tmp_path)
    tee.write("before\n")

    def refuse(*_args, **_kwargs):
        raise PermissionError("locked by another process")

    monkeypatch.setattr(STDLOG.os, "replace", refuse)
    tee.start_run("a", "e", ["+00+000"])
    tee.write("console only\n")
    assert original.getvalue() == "before\nconsole only\n"
    assert "console only" not in _text(tmp_path)
    assert _names(tmp_path) == ["engine-stderr.log"]


def test_a_header_that_cannot_be_built_never_raises(tmp_path):
    tee, _ = _log(tmp_path)
    tee.start_run("a", "e", None)
    tee.write("line\n")
    assert _text(tmp_path).startswith("=== engine run ===\n")


def test_the_path_is_under_the_data_root(tmp_path, monkeypatch):
    monkeypatch.setattr(FNAMES, "_data_root_override", str(tmp_path))
    assert STDLOG.engine_stderr_log_path() == os.path.join(
        str(tmp_path), "logs", "engine-stderr.log")
