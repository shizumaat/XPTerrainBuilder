"""#2268: the Library's scans run one per command at a time (a burst of
requests is answered by two runs, each answer computed after it was
asked) and in the background band while a build runs.  Threads and
events only; no wall-time assert."""
from __future__ import annotations

import contextlib
import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import O4_Machine_Slots as SLOTS  # noqa: E402
from o4_engine import library as LIB  # noqa: E402
from o4_engine import library_runs as RUNS  # noqa: E402

WAIT_S = 10.0


class Recorder:
    def __init__(self, gate: threading.Event | None = None):
        self.calls, self.gate = [], gate
        self.started = threading.Event()
        self.done = threading.Event()
        self.lock = threading.Lock()

    def body(self, requests, kwargs):
        with self.lock:
            self.calls.append((list(requests), dict(kwargs),
                               getattr(RUNS._BAND, "low", False)))
        self.started.set()
        if self.gate is not None:
            assert self.gate.wait(WAIT_S)
        self.done.set()


def _settle(command):
    for _ in range(1000):                    # bounded: the run loop exits
        with RUNS._LOCK:
            if command not in RUNS._RUNNING:
                return True
        threading.Event().wait(0.01)
    return False


def test_requests_during_a_scan_are_answered_by_one_run_after_it():
    gate = threading.Event()
    rec = Recorder(gate)
    RUNS.launch("tile_staleness", 1, {"tiles": "first"}, rec.body)
    assert rec.started.wait(WAIT_S)
    for request in (2, 3, 4):
        RUNS.launch("tile_staleness", request, {"tiles": request}, rec.body)
    gate.set()
    assert _settle("tile_staleness")
    assert [c[0] for c in rec.calls] == [[1], [2, 3, 4]]
    assert rec.calls[1][1] == {"tiles": 4}             # the newest arguments


def test_a_command_that_is_no_scan_never_waits_for_another():
    gate = threading.Event()
    first, second = Recorder(gate), Recorder()
    RUNS.launch("free_cache", 1, {}, first.body)
    assert first.started.wait(WAIT_S)
    RUNS.launch("free_cache", 2, {}, second.body)
    assert second.done.wait(WAIT_S)                    # ran beside the first
    gate.set()
    assert first.done.wait(WAIT_S)


def test_a_scan_beside_a_build_runs_in_the_background_band(monkeypatch):
    lowered = []

    @contextlib.contextmanager
    def band():
        lowered.append(threading.current_thread().name)
        yield
    monkeypatch.setattr(SLOTS, "background_thread", band)
    building, idle = Recorder(), Recorder()
    RUNS.launch("library_scan", 1, {}, building.body, busy=lambda: True)
    assert building.done.wait(WAIT_S) and _settle("library_scan")
    RUNS.launch("library_scan", 2, {}, idle.body, busy=lambda: False)
    assert idle.done.wait(WAIT_S) and _settle("library_scan")
    assert lowered == ["o4-library"]
    assert building.calls[0][2] is True and idle.calls[0][2] is False


def test_a_scans_row_threads_share_its_band():
    assert RUNS.row_initializer() is None
    RUNS._BAND.low = True
    try:
        assert RUNS.row_initializer() is SLOTS.lower_this_thread
    finally:
        RUNS._BAND.low = False


def test_every_waiting_request_gets_its_own_library_ready(monkeypatch):
    gate = threading.Event()
    calls = []

    def scan(**kw):
        calls.append(kw)
        if len(calls) == 1:
            assert gate.wait(WAIT_S)
        return {"n": len(calls)}
    monkeypatch.setitem(LIB._COMMANDS, "cache_sizes", (scan, None))
    events, got = [], threading.Event()

    def emit(event):
        events.append(event)
        if len(events) == 3:
            got.set()
    LIB.start(emit, "cache_sizes", request="a")
    for _ in range(1000):
        if calls:
            break
        threading.Event().wait(0.01)
    LIB.start(emit, "cache_sizes", request="b")
    LIB.start(emit, "cache_sizes", request="c")
    gate.set()
    assert got.wait(WAIT_S)
    assert [(e.request, e.result) for e in events] == [
        ("a", {"n": 1}), ("b", {"n": 2}), ("c", {"n": 2})]


def test_lowering_a_thread_never_raises_and_restores():
    done = []

    def run():
        undo = SLOTS.lower_this_thread()
        undo()
        with SLOTS.background_thread():
            done.append(True)
    t = threading.Thread(target=run)
    t.start()
    t.join(WAIT_S)
    assert done == [True]
