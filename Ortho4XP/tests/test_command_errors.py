"""1.0.553: a tile build refused with "Error -3 while decompressing data:
incorrect header check", and the next press sat "queued" forever.

Cause: the engine's executable was re-signed on disk after the engine
started; a frozen engine reads each late import from its executable by
offset, so the first late import inside ``EngineSession.build`` raised
``zlib.error``.  ``build`` had already set ``_building``, so every later
press joined a queue no worker read.

Twins: (1) a run that fails to start leaves the session idle and the
next press starts a run; (2) a refused build names the exception type,
the file:line, the engine step, and the changed executable; other
commands keep their own sentence.  Headless, ``tmp_path``, no network.
"""
from __future__ import annotations

import os
import sys
import zlib

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))), "src"))

from o4_engine import command_errors as CE  # noqa: E402
from o4_engine import session as S  # noqa: E402


def _raise_in_engine_step():
    raise zlib.error("Error -3 while decompressing data: incorrect header check")


def _caught():
    try:
        _raise_in_engine_step()
    except zlib.error as exc:
        return exc


def test_refused_build_names_type_place_and_step():
    text = CE.command_error_text("enqueue_build", _caught(), changed=False)
    assert text.startswith("enqueue_build failed: error: Error -3")
    assert "test_command_errors.py:" in text
    assert "in _raise_in_engine_step" in text
    assert "program file changed" not in text


def test_changed_executable_is_named_for_every_command():
    text = CE.command_error_text("enqueue_build", _caught(), changed=True)
    assert "quit the app and open it again" in text
    plain = CE.command_error_text("read_flight_plan", ValueError(
        "This plan could not be read."), changed=False)
    assert plain == "This plan could not be read."
    hinted = CE.command_error_text("read_flight_plan", ValueError("x"),
                                   changed=True)
    assert hinted.startswith("x -- the engine's program file changed")


def test_engine_step_is_the_deepest_engine_frame():
    def engine_side():
        _raise_in_engine_step()
    engine_side.__code__ = engine_side.__code__.replace(
        co_filename="/x/src/o4_engine/session.py")
    try:
        engine_side()
    except zlib.error as exc:
        text = CE.command_error_text("build", exc, changed=False)
    assert "; step session.engine_side)" in text


def test_executable_changed_reads_inode_size_and_time(tmp_path):
    exe = tmp_path / "Ortho4XP"
    exe.write_bytes(b"a" * 10)
    start = CE._executable_stamp(str(exe))
    assert not CE._executable_changed(start, CE._executable_stamp(str(exe)))
    exe.write_bytes(b"b" * 12)              # re-signed: new size
    assert CE._executable_changed(start, CE._executable_stamp(str(exe)))
    assert not CE._executable_changed(None, None)     # not frozen


def test_failed_start_leaves_the_session_idle(monkeypatch):
    session = S.EngineSession()
    calls = []

    def start_run(self, *args):
        calls.append(args)
        if len(calls) == 1:
            _raise_in_engine_step()
        return True

    monkeypatch.setattr(S.EngineSession, "_start_run", start_run)
    try:
        session.enqueue_build([(37, -26)], "BI", 16, "")
    except zlib.error:
        pass
    else:
        raise AssertionError("the first start should raise")
    assert session._building is False
    assert session._parallel is None
    # The second press starts a run instead of joining a dead queue.
    assert session.enqueue_build([(37, -26)], "BI", 16, "") is True
    assert len(calls) == 2
