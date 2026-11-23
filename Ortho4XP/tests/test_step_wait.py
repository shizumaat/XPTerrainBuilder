"""Slots follow real work (#2254, #2258): a step that only waits holds no
machine slot and no scheduler token, and a speculative prefetch never keeps
a real imagery step out.  Headless; no network."""
from __future__ import annotations

import os
import subprocess
import sys
import threading
from types import SimpleNamespace

import pytest

SRC = os.path.join(os.path.dirname(__file__), "..", "src")
sys.path.insert(0, SRC)

import O4_File_Lock as FILE_LOCK  # noqa: E402
import O4_Machine_Slots as SLOTS  # noqa: E402
import O4_Step_Wait as STEP_WAIT  # noqa: E402
from o4_engine import parallel, step_parking  # noqa: E402


class _Calls:
    def __init__(self):
        self.log = []

    def park(self):
        self.log.append("park")

    def resume(self):
        self.log.append("resume")


def test_a_lone_wait_parks_and_resumes():
    calls = _Calls()
    with STEP_WAIT.step_scope(calls.park, calls.resume):
        with STEP_WAIT.waiting():
            with STEP_WAIT.waiting():      # nested: one wait
                assert calls.log == ["park"]
        assert calls.log == ["park", "resume"]


def test_outside_a_step_nothing_happens():
    with STEP_WAIT.waiting():
        with STEP_WAIT.working():
            pass


def test_no_park_while_another_member_works():
    calls = _Calls()
    entered, leave = threading.Event(), threading.Event()

    def member_waits():
        with STEP_WAIT.waiting():
            entered.set()
            leave.wait(5)

    with STEP_WAIT.step_scope(calls.park, calls.resume):
        thread = threading.Thread(target=STEP_WAIT.step_thread(member_waits))
        thread.start()
        assert entered.wait(5)
        assert calls.log == []             # this thread is working
        leave.set()
        thread.join()
    assert calls.log == []


def test_joining_a_waiting_member_parks():
    calls = _Calls()
    entered, leave = threading.Event(), threading.Event()

    def member_waits():
        with STEP_WAIT.waiting():
            entered.set()
            leave.wait(5)

    with STEP_WAIT.step_scope(calls.park, calls.resume):
        thread = threading.Thread(target=STEP_WAIT.step_thread(member_waits))
        thread.start()
        assert entered.wait(5)
        with STEP_WAIT.joining():
            assert calls.log == ["park"]
            leave.set()
            thread.join()
    assert calls.log == ["park", "resume"]


def test_joining_a_working_member_does_not_park():
    calls = _Calls()
    leave = threading.Event()
    with STEP_WAIT.step_scope(calls.park, calls.resume):
        thread = threading.Thread(
            target=STEP_WAIT.step_thread(lambda: leave.wait(5)))
        thread.start()
        with STEP_WAIT.joining():
            assert calls.log == []
            leave.set()
            thread.join()
    assert calls.log == []


def test_working_inside_a_wait_holds_the_slots():
    calls = _Calls()
    with STEP_WAIT.step_scope(calls.park, calls.resume):
        with STEP_WAIT.waiting():
            with STEP_WAIT.working():
                assert calls.log == ["park", "resume"]
            assert calls.log == ["park", "resume", "park"]


def test_a_thread_outside_the_step_is_not_counted():
    calls = _Calls()

    def stranger():
        with STEP_WAIT.waiting():
            pass

    with STEP_WAIT.step_scope(calls.park, calls.resume):
        thread = threading.Thread(target=stranger)
        thread.start()
        thread.join()
    assert calls.log == []


def test_contended_cache_lock_parks_the_step(tmp_path):
    calls = _Calls()
    target = str(tmp_path / "cell.tif")
    holder = FILE_LOCK.hold_file_lock(target)
    holder.__enter__()
    released = threading.Timer(0.5, lambda: holder.__exit__(None, None, None))
    released.start()
    with STEP_WAIT.step_scope(calls.park, calls.resume):
        with FILE_LOCK.hold_file_lock(target, timeout_seconds=10) as got:
            assert got is True
    released.join()
    assert calls.log == ["park", "resume"]


def test_free_cache_lock_does_not_park(tmp_path):
    calls = _Calls()
    with STEP_WAIT.step_scope(calls.park, calls.resume):
        with FILE_LOCK.hold_file_lock(str(tmp_path / "cell.tif")):
            pass
    assert calls.log == []


#: a step in its own process: holds the machine slot, waits inside a bracket
WAITER = r"""
import os, sys, time
sys.path.insert(0, sys.argv[1])
import O4_Machine_Slots as SLOTS, O4_Step_Wait as W
from o4_engine import step_parking as P
parking = P.ChildParking(lambda event: None, 1, 2)
with SLOTS.step(gb=0, what="test"):
    print("held", flush=True)
    sys.stdin.readline()
    with W.step_scope(parking.park, parking.resume):
        with W.waiting():
            print("waiting", flush=True)
            sys.stdin.readline()
        print("back", flush=True)
        sys.stdin.readline()
"""


def test_a_waiting_process_gives_its_machine_slot_to_another(
        tmp_path, monkeypatch):
    (tmp_path / "slots").mkdir()
    monkeypatch.setenv(SLOTS.ENV_DIR, str(tmp_path / "slots"))
    monkeypatch.setenv(SLOTS.ENV_CAPACITY, "1")
    monkeypatch.setenv(SLOTS.ENV_UNGATED, "1")
    waiter = subprocess.Popen([sys.executable, "-c", WAITER, SRC],
                              stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                              text=True)
    try:
        assert waiter.stdout.readline().strip() == "held"
        assert SLOTS.try_take(1, gb=0).count == 0     # working: it holds it
        waiter.stdin.write("\n")
        waiter.stdin.flush()
        assert waiter.stdout.readline().strip() == "waiting"
        other = SLOTS.try_take(1, gb=0)
        assert other.count == 1                       # waiting: it is free
        other.release()
        waiter.stdin.write("\n")
        waiter.stdin.flush()
        assert waiter.stdout.readline().strip() == "back"
        assert SLOTS.try_take(1, gb=0).count == 0     # resumed: held again
        waiter.stdin.write("\n")
        waiter.stdin.flush()
        assert waiter.wait(30) == 0
    finally:
        if waiter.poll() is None:
            waiter.kill()


# -- the orchestrator ------------------------------------------------------

class _Child:
    def __init__(self):
        self.tile = None
        self.running_step = None
        self.step_class = None
        self.parked_class = None
        self.parked_memory = None
        self.autopatch_pending = None
        self.step_failed = False
        self.cancelling = False
        self.retired = False
        self.prefetch_token = False
        self.step_peak_gb = 0.0
        self.tree_gb = 0.0

    def start_step(self, step_key, build_arguments):
        self.running_step = step_key
        return True

    def send(self, payload):
        return True

    def retire(self):
        self.retired = True


@pytest.fixture
def run(tmp_path, monkeypatch):
    import O4_Parallel_Utils as PU

    (tmp_path / "slots").mkdir()
    monkeypatch.setenv(SLOTS.ENV_DIR, str(tmp_path / "slots"))
    monkeypatch.setenv(SLOTS.ENV_CAPACITY, "64")
    monkeypatch.setenv(SLOTS.ENV_UNGATED, "1")
    monkeypatch.setenv(parallel.OSM_CLASS_LIMIT_ENVIRONMENT_KEY, "2")
    monkeypatch.setattr(PU, "machine_core_count", lambda: 16)
    tiles = [(10, 10), (11, 11), (12, 12), (13, 13)]
    build = parallel.ParallelBuildRun(
        SimpleNamespace(_emit=lambda e: None, _run_finished=lambda: None),
        tiles, "P", 16, "", (True, False, False), 4)
    monkeypatch.setattr(build, "_fetch_is_cached_locked",
                        lambda tile, step: False)
    return build


def _start(run, count):
    children = [_Child() for _ in range(count)]
    run._children.extend(children)
    with run._lock:
        for child in children:
            run._start_new_tile_locked(child)
    return children


def _event(run, child, waiting):
    run._on_child_event(child, {"event": "StepWaiting", "waiting": waiting})


def test_a_waiting_tile_frees_its_osm_token(run, monkeypatch):
    monkeypatch.setattr(step_parking, "extra_worker_wanted_locked",
                        lambda _run: False)
    first, second, third = _start(run, 3)
    assert third.tile is None              # the class (2) is full
    _event(run, first, True)
    assert first.step_class == step_parking.WAITING_CLASS
    assert third.tile is not None and third.step_class == "osm"
    _event(run, first, False)
    assert first.step_class == "osm"
    assert run._class_active["osm"] == 3   # over, and shut until it drains
    assert run._class_active[step_parking.WAITING_CLASS] == 0


def test_a_step_ending_parked_leaks_no_token(run, monkeypatch):
    monkeypatch.setattr(step_parking, "extra_worker_wanted_locked",
                        lambda _run: False)
    first, _second = _start(run, 2)
    _event(run, first, True)
    with run._lock:
        run._release_step_resources_locked(first)
    assert run._class_active[step_parking.WAITING_CLASS] == 0
    assert first.parked_class is None


def test_parking_hands_back_the_memory_booking(run, monkeypatch):
    monkeypatch.setattr(step_parking, "extra_worker_wanted_locked",
                        lambda _run: False)
    first, _second = _start(run, 2)
    key = (first.tile, "vector")
    booked = run._memory_holders.get(key)
    assert booked
    in_use = run._memory_in_use
    _event(run, first, True)
    assert key not in run._memory_holders
    assert run._memory_in_use == pytest.approx(in_use - booked)
    _event(run, first, False)
    assert run._memory_holders[key] == booked
    assert run._memory_in_use == pytest.approx(in_use)


def test_a_late_class_change_applies_on_resume(run, monkeypatch):
    monkeypatch.setattr(step_parking, "extra_worker_wanted_locked",
                        lambda _run: False)
    first, _second = _start(run, 2)
    _event(run, first, True)
    with run._lock:
        assert run._note_autopatch_begin_locked(first, ["KAAA"])
    assert first.step_class == step_parking.WAITING_CLASS
    _event(run, first, False)
    assert first.step_class == parallel.VECTOR_SOLVE_CLASS


def test_an_extra_worker_serves_the_queue_behind_parked_children(run):
    children = _start(run, 2)
    with run._lock:
        run._class_limits["osm"] = 4
        run._slots = 2
        for child in children:
            step_parking.note_waiting_locked(run, child, True)
        assert step_parking.pool_full_locked(run) is False
        assert step_parking.extra_worker_wanted_locked(run) is True
        assert run._parked_spawns == 1


def test_no_extra_worker_without_a_parked_child(run):
    _start(run, 2)
    with run._lock:
        run._slots = 2
        assert step_parking.extra_worker_wanted_locked(run) is False


def test_surplus_idle_workers_retire_once_nobody_is_parked(run):
    children = [_Child() for _ in range(3)]
    run._children.extend(children)
    with run._lock:
        run._queue.clear()
        run._slots = 2
        step_parking.retire_surplus_locked(run)
    assert sum(child.retired for child in children) == 1


def test_prefetch_tokens_do_not_keep_a_real_imagery_step_out(run):
    """The unmodified scheduler answered False here: four vector steps'
    lent prefetch tokens filled the imagery class."""
    limit = run._class_limits["imagery"]
    prefetchers = [_Child() for _ in range(limit)]
    for child in prefetchers:
        child.prefetch_token = True
    run._children.extend(prefetchers)
    run._class_active["imagery"] = limit
    assert run._class_full_locked("imagery") is False
    run._class_active["imagery"] = limit + limit
    assert run._class_full_locked("imagery") is True


def test_a_prefetch_still_needs_a_free_imagery_token(run):
    run._programs[(10, 10)] = ["vector", "imagery"]
    run._class_active["imagery"] = run._class_limits["imagery"]
    assert run._may_prefetch_locked((10, 10), "vector") is False


# -- the airport's own photos ----------------------------------------------

def test_the_airport_photo_wait_holds_no_step_slot(tmp_path, monkeypatch):
    import O4_Imagery_Prefetch as PREFETCH

    calls = _Calls()
    seen = []
    monkeypatch.setattr(PREFETCH, "_orthophoto_path",
                        lambda tile, texture, imagery: str(tmp_path / "none"))

    def fetch(tile, texture):
        seen.append(list(calls.log))
        return 1
    with STEP_WAIT.step_scope(calls.park, calls.resume):
        PREFETCH.fetch_airport_imagery(
            SimpleNamespace(), {"A": 1}, fetch=fetch,
            find=lambda tile, airports: {"A": [(1, 2, 16, "P")]}, slots=1)
    assert seen == [["park"]]
    assert calls.log == ["park", "resume"]


# -- the backend's switch, before the configuration is loaded --------------

def _maintenance_once(monkeypatch, EXTRACTS):
    class _Done(Exception):
        pass

    def stop_loop(_seconds):
        raise _Done
    monkeypatch.setattr(EXTRACTS.time, "sleep", stop_loop)
    with pytest.raises(_Done):
        EXTRACTS._maintenance_loop()


@pytest.mark.parametrize("enabled, asked", [("False", 0), ("True", 1)])
def test_maintenance_obeys_the_setting_before_config_loads(
        tmp_path, monkeypatch, enabled, asked):
    import O4_OSM_Extracts as EXTRACTS
    import O4_Settings_Model as SETTINGS

    monkeypatch.delitem(sys.modules, "O4_Config_Utils", raising=False)
    monkeypatch.setattr(SETTINGS, "read_global_raw",
                        lambda *a: {"osm_regional_extracts": enabled})
    monkeypatch.setattr(EXTRACTS, "STORE_DIRECTORY", str(tmp_path))
    index_requests = []
    monkeypatch.setattr(EXTRACTS, "_refresh_index",
                        lambda: index_requests.append(1) or False)
    monkeypatch.setattr(EXTRACTS.UI, "red_flag", False)
    assert EXTRACTS.extracts_enabled() is (enabled == "True")
    _maintenance_once(monkeypatch, EXTRACTS)
    assert len(index_requests) == asked


def test_refresh_days_are_read_before_config_loads(monkeypatch):
    import O4_OSM_Extracts as EXTRACTS
    import O4_Settings_Model as SETTINGS

    monkeypatch.delitem(sys.modules, "O4_Config_Utils", raising=False)
    monkeypatch.setattr(SETTINGS, "read_global_raw",
                        lambda *a: {"osm_extract_refresh_days": "14"})
    assert EXTRACTS._extract_refresh_days() == 14.0
