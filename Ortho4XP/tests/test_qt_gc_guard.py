"""The Qt app survives Python 3.14's incremental GC under worker threads (#2059).

The crash class: a worker's automatic collection (``mark_stacks``, CPython
3.14.0-3.14.4) reads the GUI thread's stack while a PySide6 dealloc there
has freed the wrapper and dropped the GIL (see ``O4_Qt_GC_Guard``).  The
stress run below is that shape stripped to its parts -- the GUI thread
calling ``painter.setPen(QColor(...))`` (``CALL_BUILTIN_O`` with a
temporary shiboken argument, as the map's paint helpers do) while four
worker threads churn cyclic garbage -- and it runs in a subprocess,
because the failure is a segfault.

* guarded: ``O4_Qt_GC_Guard.install`` (forced, so the twin runs on every
  interpreter) plus explicit young/full ``gc.collect`` pressure from the
  workers: every run exits clean, and the guard's own GUI-thread
  collector has run (a collector freed at install would leave the app
  with no collection at all) -- checked after the stress, in a bounded
  quiet window, so a timer starved by load or by the inert path on an
  unaffected interpreter (forced install) is not read as a dead collector;
* base (affected interpreters only): the same run without the guard
  crashes -- the proof the stress reaches the defect (6/6 runs crashed
  within 1.5 s on 3.14.3 when it was written);
* the version gate and the collector's policy, without Qt.
"""

import os
import subprocess
import sys

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

SRC = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src")
sys.path.insert(0, SRC)

import O4_Qt_GC_Guard as GUARD  # noqa: E402

STRESS_S = 2.0


def _stress(seconds, guarded):
    """The stress run (subprocess body): prints CLEAN when it survives."""
    import gc
    import threading
    import time

    from PySide6.QtGui import QColor, QGuiApplication, QImage, QPainter

    app = QGuiApplication([])
    if guarded:
        GUARD.install(app, force=True, tick_ms=5)
    # Dense collections: many more chances per second to collect inside
    # the GUI thread's dealloc window.
    gc.set_threshold(50)
    image = QImage(8, 8, QImage.Format_ARGB32)
    painter = QPainter(image)
    stop = threading.Event()

    def worker(k):
        n = 0
        while not stop.is_set():
            junk = []
            for _ in range(100):
                cycle = []
                cycle.append(cycle)
                junk.append(cycle)
            del junk
            n += 1
            if guarded and n % 2000 == 0:
                gc.collect(0 if (n + k) % 3 else 2)

    threads = [threading.Thread(target=worker, args=(k,), daemon=True) for k in range(4)]
    for thread in threads:
        thread.start()

    def paint(n):
        for i in range(n):
            painter.setPen(QColor(i & 255, 0, 0))

    start = time.monotonic()
    while time.monotonic() - start < seconds:
        paint(2000)
        app.processEvents()
    stop.set()
    for thread in threads:
        thread.join()
    painter.end()
    ticked = True
    if guarded:
        # The stress loop may starve the timer (one long paint() under GIL
        # contention, CI load) or catch counts just reset by a worker's
        # collect: give the collector a quiet, bounded window with garbage
        # over its threshold, so "never ran" means it really cannot run.
        deadline = time.monotonic() + 10.0
        while (not all(c.collections > 0 for c in GUARD._INSTALLED)
               and time.monotonic() < deadline):
            junk = [[] for _ in range(200)]
            for cycle in junk:
                cycle.append(cycle)
            del junk
            app.processEvents()
            time.sleep(0.01)
        ticked = all(c.collections > 0 for c in GUARD._INSTALLED)
    print("CLEAN" if ticked else "COLLECTOR NEVER RAN")


def _run(guarded):
    mode = "guarded" if guarded else "base"
    return subprocess.run(
        [sys.executable, os.path.abspath(__file__), "--stress", str(STRESS_S), mode],
        capture_output=True, text=True, timeout=120,
        env={**os.environ, "QT_QPA_PLATFORM": "offscreen"},
    )


def test_guarded_stress_survives():
    for _ in range(3):
        proc = _run(guarded=True)
        assert proc.returncode == 0 and "CLEAN" in proc.stdout, (
            proc.returncode, proc.stderr[-2000:])


@pytest.mark.skipif(not GUARD.affected(), reason="interpreter never walks other threads' stacks")
def test_base_stress_crashes_on_an_affected_interpreter():
    """Without the guard the stress segfaults: the twin bites."""
    for _ in range(3):
        if _run(guarded=False).returncode != 0:
            return
    pytest.fail("unguarded stress survived 3 runs: the twin no longer reaches the defect")


@pytest.mark.parametrize("version, expected", [
    ((3, 13, 9), False), ((3, 14, 0), True), ((3, 14, 3), True),
    ((3, 14, 4), True), ((3, 14, 5), False), ((3, 15, 1), False),
])
def test_affected_versions(version, expected):
    assert GUARD.affected(version) is expected


class _FakeGC:
    def __init__(self):
        self.count, self.calls = 0, []

    def get_count(self):
        return (self.count, 0, 0)

    def get_threshold(self):
        return (2000, 10, 0)

    def collect(self, generation=2):
        self.calls.append(generation)
        self.count = 0


def test_collector_policy():
    fake, now = _FakeGC(), [0.0]
    collector = GUARD._SafeCollector(fake, clock=lambda: now[0])
    assert collector.tick() == "" and fake.calls == []
    fake.count = 2500
    assert collector.tick() == "young" and fake.calls == [0]
    now[0] = GUARD.FULL_EVERY_S
    fake.count = 2500
    assert collector.tick() == "full" and fake.calls == [0, 2]
    fake.count = 2500
    assert collector.tick() == "young"


def test_install_is_inert_on_an_unaffected_interpreter(monkeypatch):
    import gc

    monkeypatch.setattr(GUARD, "affected", lambda version=None: False)
    was = gc.isenabled()
    assert GUARD.install(object()) is None
    assert gc.isenabled() == was


if __name__ == "__main__" and sys.argv[1:2] == ["--stress"]:
    _stress(float(sys.argv[2]), sys.argv[3] == "guarded")
