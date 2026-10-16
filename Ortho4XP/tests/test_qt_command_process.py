"""The patch editor's heavy reads in a worker PROCESS (issue #753):
``o4_engine.command_process.CommandProcess`` and the Qt door
``O4_Qt_Patch_Engine.PatchEngine`` that uses it.  Synthetic pack from
``test_pack_objects`` in ``tmp_path``; run ``-n0`` (Qt + spawned workers).
"""
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.insert(0, os.path.dirname(__file__))

import pytest  # noqa: E402

pytest.importorskip("PySide6")

from PySide6.QtCore import QTimer  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

import O4_Config_Utils as CFG  # noqa: E402
from O4_Qt_Patch_Engine import PatchEngine  # noqa: E402
from o4_engine import command_process as CP  # noqa: E402
from o4_engine import pack_objects as PO  # noqa: E402
from test_pack_objects import BBOX, TILE, pack  # noqa: E402,F401  (the fixture)


# ─── functions the worker runs (module level: they cross by name) ─────────

def spin(seconds: float) -> int:
    """Pure-Python work that holds the interpreter lock for ``seconds``."""
    end, n = time.perf_counter() + seconds, 0
    while time.perf_counter() < end:
        n += 1
    return n


def burn(n: int) -> int:
    """A FIXED amount of pure-Python work under the interpreter lock — its
    CPU cost does not depend on how loaded the machine is (``spin`` runs to
    a wall-clock deadline instead)."""
    x = 0
    for i in range(n):
        x ^= i
    return x


#: about 0.7 s of one fast core (more on a CI runner): the ratio is what is judged
BURN_N = 60_000_000


def die() -> None:
    os._exit(3)


def custom_scenery() -> str:
    return CFG.custom_scenery_dir


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except OSError:
        return False
    return True


@pytest.fixture
def qapp():
    yield QApplication.instance() or QApplication([])


@pytest.fixture
def worker_pack(pack, monkeypatch):
    """The synthetic pack, found by the worker the way the app finds it:
    the X-Plane folder from the in-memory config (the CIFP folder beside
    it), the mod cache from the environment the worker inherits."""
    xp = pack.parent.parent.parent / "X-Plane"
    (xp / "Custom Data" / "CIFP").mkdir(parents=True)
    monkeypatch.setattr(CFG, "custom_scenery_dir", str(xp / "Custom Scenery"))
    monkeypatch.setattr(CFG, "cifp_data_path", "")
    monkeypatch.setenv("O4_AIRPORT_MOD_CACHE_DIR", str(pack.parent.parent))
    proc = CP.CommandProcess(out=lambda _line: None)
    yield proc
    proc.close()


def test_the_worker_answers_pack_objects_as_this_process_does(worker_pack):
    here = PO.pack_objects(TILE, "ZZZZ", BBOX)
    there = worker_pack.call("pack_objects", tile=TILE, icao="ZZZZ", bbox=BBOX)
    assert there == here and there["models"] and there["placements"]
    pid = worker_pack.pids()
    assert len(pid) == 1 and pid[0] != os.getpid()
    # the session cache lives in the worker: the same box again, same answer
    assert worker_pack.call("pack_objects", tile=TILE, icao="ZZZZ", bbox=BBOX) == here
    assert worker_pack.pids() == pid


def test_the_worker_reads_the_callers_config_at_each_call(worker_pack, monkeypatch):
    assert worker_pack.run(custom_scenery) == CFG.custom_scenery_dir
    monkeypatch.setattr(CFG, "custom_scenery_dir", "/elsewhere/Custom Scenery")
    assert worker_pack.run(custom_scenery) == "/elsewhere/Custom Scenery"


def test_a_command_error_is_its_sentence(worker_pack):
    with pytest.raises(ValueError, match="bbox"):
        worker_pack.call("pack_objects", tile=TILE, icao="ZZZZ", bbox=[1, 2, 1, 2])


def test_a_dead_worker_is_a_sentence_not_a_hang_and_the_next_call_recovers(worker_pack):
    t0 = time.monotonic()
    with pytest.raises(RuntimeError, match="worker process stopped"):
        worker_pack.run(die)
    assert time.monotonic() - t0 < 60
    assert worker_pack.run(spin, seconds=0.0) >= 0


def test_the_worker_is_gone_after_close(worker_pack):
    worker_pack.run(spin, seconds=0.0)
    pids = worker_pack.pids()
    worker_pack.close()
    assert pids and not any(_alive(p) for p in pids)
    assert worker_pack.pids() == []


def test_the_workers_lock_holding_work_costs_this_process_no_cpu(qapp, worker_pack):
    """Issue #753: what the isolation guarantees is that the worker's
    interpreter-lock work is not THIS process's — so the GUI thread never
    waits behind it.  Measured as CPU time (``process_time``), not timer
    lateness: a shared CI runner makes wall-clock bars flaky (main CI
    78b88ca71, 0.182 s against 0.100), while CPU spent here is a property of
    where the work runs.  Both arms run the same fixed work in one test:
    in a thread here it costs this process its full CPU; through the Qt
    door to the worker it costs a small fraction (the waiting loop)."""
    import threading

    def cpu_while(start, done) -> float:
        t0 = time.process_time()
        start()
        deadline = time.monotonic() + 120
        while not done() and time.monotonic() < deadline:
            qapp.processEvents()
            time.sleep(0.002)
        assert done(), "the work did not finish"
        return time.process_time() - t0

    # in-process arm: a thread of this process does the work
    th = threading.Thread(target=burn, args=(BURN_N,))
    here = cpu_while(th.start, lambda: not th.is_alive())

    # isolated arm: the same work through PatchEngine to the worker process
    engine = PatchEngine(object(), isolate=True)
    engine.process.close()
    engine.process = worker_pack
    worker_pack.run(burn, n=0)                       # spawned before the clock starts
    worker_pack.call = lambda name, **kw: worker_pack.run(burn, n=BURN_N)
    got = []
    there = cpu_while(
        lambda: engine.pack_objects(TILE, "ZZZZ", BBOX, lambda r, e: got.append((r, e))),
        lambda: bool(got))
    engine.close()
    assert got and got[0][1] is None
    assert here > 0.2, here                          # the work is real (60 M steps)
    assert there < 0.25 * here, (there, here)


def test_the_qt_door_answers_pack_objects_through_the_process(qapp, worker_pack):
    engine = PatchEngine(object(), isolate=True)
    engine.process.close()
    engine.process = worker_pack
    got = []
    engine.pack_objects(TILE, "ZZZZ", BBOX, lambda r, e: got.append((r, e)))
    deadline = time.monotonic() + 60
    while not got and time.monotonic() < deadline:
        qapp.processEvents()
        time.sleep(0.005)
    assert got and got[0][1] is None
    assert got[0][0] == PO.pack_objects(TILE, "ZZZZ", BBOX)
    pids = worker_pack.pids()
    engine.close()
    assert pids and not any(_alive(p) for p in pids)


def test_a_synchronous_engine_keeps_its_commands_in_process():
    assert PatchEngine(object(), run_async=False).process is None


def test_a_queued_call_no_longer_wanted_is_skipped(worker_pack):
    import threading
    worker_pack.run(spin, seconds=0.0)
    first = threading.Thread(target=worker_pack.run, args=(spin,), kwargs={"seconds": 1.0})
    first.start()
    deadline = time.monotonic() + 30                 # the first holds the worker
    while not worker_pack._lock.locked() and time.monotonic() < deadline:
        time.sleep(0.001)
    assert worker_pack._lock.locked()
    with pytest.raises(CP.Superseded):
        worker_pack.run(spin, still_wanted=lambda: False, seconds=5.0)
    first.join(30)
    assert worker_pack.run(spin, still_wanted=lambda: True, seconds=0.0) >= 0


def test_only_the_box_the_editor_still_wants_is_read(qapp):
    """Three boxes asked while the first is read: the middle one is skipped
    when its turn comes (the 56 s HECA wait was three reads at once).
    Ordered by events, not sleeps: the first read holds the process until
    the other two have queued behind it."""
    import threading

    class Process:
        def __init__(self):
            self.lock, self.read = threading.Lock(), []
            self.arrived, self.reading = 0, threading.Event()
            self.queued, self.gate = threading.Event(), threading.Event()
            self.count = threading.Lock()

        def call(self, name, still_wanted=None, **kw):
            with self.count:
                self.arrived += 1
                if self.arrived == 3:
                    self.queued.set()
            with self.lock:
                if still_wanted is not None and not still_wanted():
                    raise CP.Superseded("no longer wanted")
                self.reading.set()
                assert self.gate.wait(30)
                self.read.append(kw["bbox"][2])
                return {"box": kw["bbox"][2]}

        def close(self):
            pass

    engine = PatchEngine(object(), isolate=True)
    engine.process.close()
    proc = engine.process = Process()
    got = []

    def ask(top):
        engine.pack_objects(TILE, "ZZZZ", [30.0, 31.0, top, 31.1],
                            lambda r, e, top=top: got.append((top, r, e)))

    ask(30.1)
    assert proc.reading.wait(30)                     # the first box is being read
    ask(30.2)
    ask(30.3)
    assert proc.queued.wait(30)                      # both wait behind it
    proc.gate.set()
    deadline = time.monotonic() + 30
    while not got and time.monotonic() < deadline:
        qapp.processEvents()
        time.sleep(0.005)
    assert proc.read == [30.1, 30.3]
    assert got == [(30.3, {"box": 30.3}, None)]
