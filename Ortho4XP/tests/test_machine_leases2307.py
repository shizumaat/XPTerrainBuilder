"""#2307 (owner 2026-11-27T14:58Z: "it's blocking off large chunks for tiles
that haven't even started"): the app first, leases that grow, predictions
keyed by what a job re-runs, and dead records cleaned on read.  A private
ledger, synthetic free memory and a fake process table (the machine
fixture of ``test_machine_memory_ledger``); real OS locks."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import O4_Machine_Jobs as JOBS  # noqa: E402
import O4_Machine_Memory as MEMORY  # noqa: E402
import O4_Machine_Slots as SLOTS  # noqa: E402
import test_machine_memory_ledger as _LEDGER  # noqa: E402

HEADROOM, _as = _LEDGER.HEADROOM, _LEDGER._as
machine = _LEDGER.machine                  # the shared fixture

ME = os.getpid()


def test_the_app_does_not_count_a_lanes_idle_headroom(machine, monkeypatch):
    """THE SNAPSHOT'S SHAPE: a lane booked 20 GB and holds 7 of it; the
    app's step is admitted against free memory less only the app's own
    bookings, while another lane still counts the 13 GB the first has to
    grow into (lanes never collide with each other's predictions)."""
    machine.free = 40.0
    machine.rss = {ME: 1.0, 501: 7.0}
    _as(monkeypatch, "L", "lane")
    held = MEMORY.reserve(20.0, "replay KATL", pid=501)
    machine.rss[501] = 7.0 + 7.0                         # grew 7 of 20
    _as(monkeypatch, "A", "app")
    snap = MEMORY.snapshot()
    assert snap.outstanding_gb == pytest.approx(13.0)
    assert snap.dev_outstanding_gb == pytest.approx(13.0)
    verdict = MEMORY.admits(15.0, HEADROOM)              # 40-15-19.2 = 5.8
    assert verdict.ok and verdict.spare_gb == pytest.approx(5.8)
    _as(monkeypatch, "L2", "lane")
    assert not MEMORY.admits(15.0, HEADROOM).ok          # 5.8 - 13 < 0
    held.release()


def test_an_app_booking_still_counts_for_the_app(machine, monkeypatch):
    """Among the app's own steps the 11-17 guarantee is unchanged."""
    machine.free = 40.0
    _as(monkeypatch, "A", "app")
    held = MEMORY.reserve(10.0, "+45-124 masks step")
    _as(monkeypatch, "A2", "app")
    verdict = MEMORY.admits(15.0, HEADROOM)              # 5.8 - 10 < 0
    assert not verdict.ok
    held.release()


def test_lanes_admit_nothing_while_an_app_step_waits(machine, monkeypatch):
    """An app WANT: a lane is refused though free memory holds its need,
    its pools read "pressed" (they give back idle workers), and the wait
    says why; once the mark lapses the lane admits again."""
    machine.free = 100.0
    _as(monkeypatch, "A", "app")
    MEMORY.note_wait("tile +45-124's vector step",
                     MEMORY.Verdict(ok=False, text="holding: x"), 3.2,
                     emit=lambda line: None)
    _as(monkeypatch, "L", "lane")
    verdict = MEMORY.admits(2.0, HEADROOM)
    assert not verdict.ok and verdict.contended
    assert "the app goes first" in verdict.text
    assert MEMORY.yields_to_app() and SLOTS.memory_pressed()
    assert not MEMORY.admits(2.0, HEADROOM, idle=True).ok   # no idle pass
    monkeypatch.setitem(MEMORY.BUDGET, "want_ttl_s", 0.0)
    time.sleep(0.01)
    assert MEMORY.admits(2.0, HEADROOM).ok and not SLOTS.memory_pressed()
    _as(monkeypatch, "A", "app")
    assert not MEMORY.yields_to_app()                       # the app never


def test_a_lease_tops_up_when_its_tree_reaches_it(machine, monkeypatch):
    """A lease grown into asks for one ``lease_step_gb`` past its tree:
    granted, the record grows in place (readers see it); a lease not yet
    near its tree asks nothing."""
    machine.free = 60.0
    machine.rss = {ME: 1.0, 601: 1.0}
    _as(monkeypatch, "A", "app")
    lease = MEMORY.reserve(4.0, "+44-124 masks step", pid=601)
    assert lease.top_up(HEADROOM) is None                # grown 0 of 4
    machine.rss[601] = 1.0 + 3.8                         # within the margin
    verdict = lease.top_up(HEADROOM)
    assert verdict is not None and verdict.ok
    assert lease.gigabytes == pytest.approx(3.8 + MEMORY.BUDGET["lease_step_gb"])
    body = json.loads(Path(lease.path).read_text(encoding="utf-8"))
    assert body["gb"] == pytest.approx(lease.gigabytes, abs=1e-3)
    assert MEMORY.snapshot().outstanding_gb == pytest.approx(
        MEMORY.BUDGET["lease_step_gb"])
    lease.release()


def test_a_refused_top_up_leaves_the_lease_and_says_why(machine, monkeypatch):
    machine.free = 20.0                                  # under the headroom
    machine.rss = {ME: 1.0, 602: 1.0}
    _as(monkeypatch, "A", "app")
    lease = MEMORY.reserve(4.0, "+44-124 masks step", pid=602)
    machine.rss[602] = 1.0 + 4.0                         # grown into it
    verdict = lease.top_up(HEADROOM)
    assert verdict is not None and not verdict.ok
    assert lease.gigabytes == pytest.approx(4.0)
    assert "GB free" in verdict.text
    lease.release()


def test_a_step_and_its_slots_top_up_as_one_lease(machine, monkeypatch):
    """A vector step's lease and the airport slot its process took beside
    it cover one tree: growth into the slot's 3 GB is no reason for the
    step's lease to grow (it would book that memory twice)."""
    machine.free = 80.0
    machine.rss = {ME: 1.0, 603: 0.5}
    _as(monkeypatch, "A", "app")
    step = MEMORY.reserve(3.0, "+45-124 vector step", pid=603)
    slot = MEMORY.reserve(3.0, "airport OR81", pid=603)
    machine.rss[603] = 0.5 + 4.0                         # 4 of 6 leased
    assert step.top_up(HEADROOM) is None
    assert step.gigabytes == pytest.approx(3.0)
    machine.rss[603] = 0.5 + 5.8                         # near the 6
    assert step.top_up(HEADROOM).ok
    assert step.gigabytes == pytest.approx(3.0 + 5.8 + 2.0 - 6.0)
    slot.release()
    step.release()


def test_a_replay_is_predicted_from_what_it_reruns(tmp_path, monkeypatch):
    """History keyed by kind and what the job re-runs: the stage's own
    peak first, then the airport's last run, then the kind's largest, then
    the default; a run records both the stage and the airport."""
    peaks = tmp_path / "peaks.json"
    monkeypatch.setenv(JOBS.ENV_PEAKS, str(peaks))
    monkeypatch.delenv(SLOTS.ENV_UNGATED, raising=False)
    margin = JOBS._STEP_MEMORY.RECORDED_PEAK_MARGIN
    assert JOBS._estimate_gigabytes("replay", "KATL@planar") == \
        JOBS.DEFAULT_GB["replay"]
    peaks.write_text(json.dumps({"replay KATL": 10.0, "replay RJTT": 17.0}),
                     encoding="utf-8", newline="")
    assert JOBS._estimate_gigabytes("replay", "KATL@planar") == \
        pytest.approx(10.0 * margin)
    assert JOBS._estimate_gigabytes("replay", "KMCI@planar") == \
        pytest.approx(17.0 * margin)                     # the kind's largest
    JOBS._record_peak("replay", "KATL@planar", 6.0)
    data = json.loads(peaks.read_text(encoding="utf-8"))
    assert data["replay KATL@PLANAR"] == 6.0 and data["replay KATL"] == 6.0
    assert JOBS._estimate_gigabytes("replay", "KATL@planar") == \
        pytest.approx(6.0 * margin)


def test_a_jobs_refused_top_up_is_said_once(monkeypatch):
    """A running job cannot wait: its sampler says once that the machine
    has no room for more, and the job goes on."""
    said = []

    class Lease:
        gigabytes = 12.0

        def top_up(self, headroom_gb):
            return MEMORY.Verdict(ok=False, text="needs 2.0 GB")
    monkeypatch.setattr(SLOTS, "headroom_gigabytes", lambda: HEADROOM)
    stop = JOBS._sample_lease(Lease(), "replay KATL", said.append,
                              every_s=0.01)
    deadline = time.monotonic() + 5.0
    while not said and time.monotonic() < deadline:
        time.sleep(0.01)
    time.sleep(0.05)
    stop.set()
    assert len(said) == 1 and "goes on" in said[0]


def test_the_scheduler_says_a_refused_top_up_once(monkeypatch, capsys):
    from types import SimpleNamespace

    from o4_engine import parallel
    monkeypatch.delenv(SLOTS.ENV_UNGATED, raising=False)
    monkeypatch.setattr(SLOTS, "headroom_gigabytes", lambda: HEADROOM)
    run = SimpleNamespace(_lease_refused=set())
    lease = SimpleNamespace(gigabytes=3.0, top_up=lambda h: MEMORY.Verdict(
        ok=False, text="needs 2.0 GB"))
    leases = [(((45, -124), "vector"), lease)]
    parallel.ParallelBuildRun._top_up_leases(run, leases)
    parallel.ParallelBuildRun._top_up_leases(run, leases)
    out = capsys.readouterr().out
    assert out.count("never stopped") == 1 and "+45-124" in out


def test_dead_tile_holds_and_marks_go_on_read(machine, monkeypatch):
    """#2307: four tile holds of exited processes stood for days because
    only a cleanup read them; a reading now sweeps them."""
    monkeypatch.setitem(MEMORY.BUDGET, "fresh_s", 0.0)
    monkeypatch.setitem(MEMORY.BUDGET, "sweep_s", 0.0)
    os.makedirs(MEMORY.ledger_dir(), exist_ok=True)
    dead = Path(MEMORY.ledger_dir()) / "t-99999991-1-abc.json"
    dead.write_text(json.dumps({"tile": [44, -125], "pid": 99999991}),
                    encoding="utf-8", newline="")
    live = MEMORY.hold_tile(45, -124)
    MEMORY.snapshot()
    assert not dead.exists()
    assert MEMORY.held_tiles() == {(45, -124)}
    live.release()


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX pids")
def test_a_record_whose_holder_exited_is_dead_though_locked(machine,
                                                            monkeypatch):
    """A lock a forked child inherited outlives the record's writer: the
    writer's pid gone, the record is dead and removed."""
    monkeypatch.setitem(MEMORY.BUDGET, "fresh_s", 0.0)
    gone = subprocess.run([sys.executable, "-c", "import os; print(os.getpid())"],
                          stdout=subprocess.PIPE, text=True, check=True)
    pid = int(gone.stdout)
    _as(monkeypatch, "L", "lane")
    held = MEMORY.reserve(5.0, "replay KATL")
    os.makedirs(MEMORY.ledger_dir(), exist_ok=True)
    orphan = os.path.join(MEMORY.ledger_dir(), "r-%d-1-abc.json" % pid)
    os.rename(held.path, orphan)                   # still locked by us
    held.path = orphan
    snap = MEMORY.snapshot()
    assert snap.outstanding_gb == 0.0 and not os.path.exists(orphan)
    held.release()
