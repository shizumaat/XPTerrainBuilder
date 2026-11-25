"""The lane job gate (``O4_Machine_Jobs``, owner 2026-11-25): a heavy lane
job waits until the machine memory ledger admits its estimate, says so once
a minute, holds the memory while it runs and gives it back after; a pool is
sized by the headroom.  A stubbed verdict, clock and ledger: no machine
reading decides any assert."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import O4_Machine_Jobs as JOBS  # noqa: E402
import O4_Machine_Memory as MEM  # noqa: E402
import O4_Machine_Slots as SLOTS  # noqa: E402
from o4_engine import step_memory  # noqa: E402


@pytest.fixture
def gated(tmp_path, monkeypatch):
    """A gated process on a private ledger and peaks file; ``answers`` is
    the stubbed verdict sequence (the last repeats), ``asked`` the needs.
    The environment is a copy: the lane claim never leaks into the suite."""
    monkeypatch.setattr(os, "environ", os.environ.copy())
    monkeypatch.delenv(SLOTS.ENV_UNGATED, raising=False)
    monkeypatch.setenv(MEM.ENV_DIR, str(tmp_path / "ledger"))
    monkeypatch.setenv(JOBS.ENV_PEAKS, str(tmp_path / "peaks.json"))
    state = {"answers": [MEM.Verdict(ok=True, spare_gb=50.0)], "asked": [],
             "reserved": [], "released": []}

    def verdict(need_gb=None, *, idle=False, budget=None):
        state["asked"].append((need_gb, idle))
        answers = state["answers"]
        return answers.pop(0) if len(answers) > 1 else answers[0]

    class Held:
        def __init__(self, gb):
            self.gb = gb

        def release(self):
            state["released"].append(self.gb)

    def reserve(gb, what):
        state["reserved"].append((gb, what))
        return Held(gb)
    monkeypatch.setattr(SLOTS, "machine_verdict", verdict)
    monkeypatch.setattr(MEM, "reserve", reserve)
    monkeypatch.setattr(JOBS, "_peak_gigabytes", lambda: 7.0)
    return state


class Clock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t

    def sleep(self, s):
        self.t += s


REFUSED = MEM.Verdict(ok=False, spare_gb=-4.0,
                      text="needs 10 GB, 12 GB free, 19 GB kept free; holding: lane x 30 GB")


def test_an_idle_machine_admits_at_once_and_says_nothing(gated):
    lines = []
    with JOBS.admit("capture", "heca", emit=lines.append) as need:
        assert gated["reserved"] == [(10.0, "capture heca")]
        assert gated["released"] == []
    assert need == JOBS.DEFAULT_GB["capture"]
    assert gated["asked"] == [(10.0, True)]          # the ledger's progress rule
    assert gated["released"] == [10.0]
    assert lines == []


def test_a_job_waits_one_line_a_minute_then_starts(gated):
    gated["answers"] = [REFUSED] * 30 + [MEM.Verdict(ok=True)]
    clock, lines = Clock(), []
    with JOBS.admit("replay", "KCLT", emit=lines.append, clock=clock,
                    sleep=clock.sleep):
        pass
    waits = [ln for ln in lines if "waits" in ln]
    assert len(waits) == 3                           # 0 s, 60 s, 120 s of 150 s
    assert "needs 10 GB" in waits[0] and "holding: lane x" in waits[0]
    assert "starts after 150 s" in lines[-1]
    assert gated["reserved"] == [(10.0, "replay KCLT")]


def test_give_up_ends_a_wait_holding_nothing(gated):
    gated["answers"] = [REFUSED]
    clock = Clock()
    with pytest.raises(SystemExit):
        with JOBS.admit("capture", "HECA", emit=lambda _l: None,
                        give_up=lambda: True, clock=clock, sleep=clock.sleep):
            pass
    assert gated["reserved"] == []


def test_a_crashing_job_gives_its_memory_back(gated):
    with pytest.raises(RuntimeError):
        with JOBS.admit("census"):
            raise RuntimeError("boom")
    assert gated["released"] == [JOBS.DEFAULT_GB["census"]]


def test_the_measured_peak_becomes_the_next_estimate(gated, tmp_path):
    with JOBS.admit("capture", "HECA"):
        pass
    peaks = (tmp_path / "peaks.json").read_text(encoding="utf-8")
    assert json.loads(peaks) == {"capture HECA": 7.0}
    margin = step_memory.RECORDED_PEAK_MARGIN
    assert JOBS.estimate_gigabytes("capture", "heca") == round(7.0 * margin, 2)
    # another airport of the kind: the kind's largest measured peak
    assert JOBS.estimate_gigabytes("capture", "KCLT") == round(7.0 * margin, 2)
    assert JOBS.estimate_gigabytes("replay", "HECA") == JOBS.DEFAULT_GB["replay"]


def test_an_ungated_process_records_no_peak(gated, tmp_path, monkeypatch):
    monkeypatch.setenv(SLOTS.ENV_UNGATED, "1")
    with JOBS.admit("capture", "HECA"):
        pass
    assert not (tmp_path / "peaks.json").exists()


def test_pools_are_sized_by_headroom_not_cores(gated):
    gated["answers"] = [MEM.Verdict(ok=True, spare_gb=25.0)]
    assert JOBS.admissible_workers(10.0, 16) == 3    # itself + 2 more fit
    gated["answers"] = [MEM.Verdict(ok=True, spare_gb=500.0)]
    assert JOBS.admissible_workers(10.0, 16) == 16   # an idle machine: every core
    gated["answers"] = [REFUSED]
    assert JOBS.admissible_workers(10.0, 16) == 1    # pressed: the caller alone


def test_the_lane_is_named_by_its_worktree(monkeypatch, tmp_path):
    monkeypatch.setattr(os, "environ", os.environ.copy())
    monkeypatch.delenv(MEM.ENV_ROLE, raising=False)
    monkeypatch.delenv(MEM.ENV_LABEL, raising=False)
    root = tmp_path / ".claude" / "worktrees" / "lmemx" / "Ortho4XP"
    root.mkdir(parents=True)
    JOBS.claim_lane(root)
    assert MEM.role() == "lane"
    assert os.environ[MEM.ENV_LABEL] == "lane lmemx"
