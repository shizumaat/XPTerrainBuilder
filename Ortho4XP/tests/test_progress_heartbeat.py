"""Issue #136 (RULINGS 2026-09-30ai): the v2 progress table and heartbeat.

OTHH's ``[40/100] Classifying & building the planar map`` ran ~26 min with
no line at all.  These twins pin the three halves of the fix:

* the phase table — seven steps, weights summing to 100, one weight per
  label, the stage-done map advancing in build order;
* the heartbeat — ONE time-gated emitter: on a fake three-stage run it
  beats at the cadence, never faster, and a new step restarts its clock;
* the channel — a beat goes out as the SAME ``(percent, label)`` event and
  console line a step banner uses (``UI.lvprint`` -> console drawer +
  ``Ortho4XP.log``; ``UI.auto_patch_progress`` -> ``AutoPatchProgress``;
  the pool worker's queue tuple), so the JSONL event set is unchanged.
"""
from __future__ import annotations

import time

import pytest

import O4_UI_Utils as UI
from auto_patch import engine_v2, progress
from auto_patch_v2.model import pulse


# ── the table ─────────────────────────────────────────────────────────────
def test_phase_weights_sum_to_100_and_match_the_labels():
    assert len(engine_v2.V2_PHASE_WEIGHTS) == len(engine_v2.V2_PHASE_LABELS) == 7
    assert sum(engine_v2.V2_PHASE_WEIGHTS) == 100
    assert all(w > 0 for w in engine_v2.V2_PHASE_WEIGHTS)
    # pack partition, structures and planar are SEPARATE reported steps
    labels = engine_v2.V2_PHASE_LABELS
    assert any("Partitioning the pack" in s for s in labels)
    assert any("door wells" in s and "wall corridors" in s for s in labels)
    assert any("planar map" in s for s in labels)


def test_stage_done_map_advances_in_build_order():
    order = ["load", "pack", "structures", "planar", "constraints", "solve"]
    phases = [engine_v2._STAGE_DONE_TO_PHASE[k] for k in order]
    assert phases == list(range(2, 2 + len(order)))
    assert phases[-1] == len(engine_v2.V2_PHASE_LABELS)


# ── the heartbeat, on a fake clock ────────────────────────────────────────
def _fake_run(stages, period, dt=0.25):
    """Drive ``Heartbeat.poll`` over ``stages`` = [(name, seconds), ...]
    on a fake clock; return (beats, step_starts) as (time, text) lists."""
    now = [0.0]
    cur = [0, None]
    beats, starts = [], []
    hb = progress.Heartbeat(lambda text: beats.append((now[0], text)),
                            lambda: tuple(cur), lambda: "doing x 3/9 things",
                            period_s=period, clock=lambda: now[0])
    for k, (name, secs) in enumerate(stages, start=1):
        cur[:] = [k, name]
        starts.append((now[0], name))
        end = now[0] + secs
        while now[0] < end:
            hb.poll()
            now[0] = round(now[0] + dt, 6)
    return beats, starts


def test_heartbeat_fires_at_the_cadence_and_never_faster():
    period = 60.0
    stages = [("load", 20.0), ("structures", 330.0), ("planar", 125.0)]
    beats, starts = _fake_run(stages, period)
    # every emitted line (step banners AND beats) in time order
    events = sorted([(t, "step") for t, _ in starts] + [(t, "beat") for t, _ in beats])
    gaps = [b[0] - a[0] for a, b in zip(events, events[1:])]
    # never faster: a beat is at least one period after the previous line
    for (ta, _ka), (tb, kb) in zip(events, events[1:]):
        if kb == "beat":
            assert tb - ta >= period - 1e-9
    # at the cadence: no silence longer than a period (+ one poll tick)
    assert max(gaps) <= period + 0.25 + 1e-9
    # counts: the 20 s step is silent, 330 s beats 5x, 125 s beats 2x
    per_step = [sum(1 for t, _ in beats if s0 <= t < s0 + secs)
                for (s0, _), (_n, secs) in zip(starts, stages)]
    assert per_step == [0, 5, 2]
    # the line names the step, its elapsed time, and the activity count
    t1, text = beats[0]
    assert text.startswith("structures — still working: 1m00s in this step")
    assert text.endswith("— doing x 3/9 things")


def test_heartbeat_thread_beats_and_stops():
    got = []
    hb = progress.Heartbeat(lambda text: got.append(time.monotonic()),
                            lambda: (1, "step"), period_s=0.2)
    hb.start(poll_s=0.01)
    time.sleep(1.05)
    hb.stop()
    n = len(got)
    assert 3 <= n <= 5, got
    assert all(b - a >= 0.2 - 1e-3 for a, b in zip(got, got[1:]))
    time.sleep(0.3)
    assert len(got) == n                    # stopped means stopped


# ── the pulse ─────────────────────────────────────────────────────────────
def test_pulse_each_is_transparent_and_restores_the_outer_activity():
    pulse.tick("outer")
    seen = []
    for x in pulse.each(range(4), "inner", "things"):
        seen.append((x, pulse.describe()))
    assert [x for x, _ in seen] == [0, 1, 2, 3]
    assert seen[1][1] == "inner 2/4 things"
    assert pulse.describe() == "outer"
    pulse.clear()
    assert pulse.describe() == ""
    assert pulse.describe(("door wells", 411, 1318, "objects")) == \
        "door wells 412/1,318 objects"


# ── the channel: a fake v2 build through V2Progress ───────────────────────
@pytest.fixture
def ui_capture(monkeypatch):
    printed, events = [], []
    monkeypatch.setattr(UI, "lvprint", lambda lvl, *a: printed.append(" ".join(map(str, a))))
    monkeypatch.setattr(UI, "auto_patch_progress",
                        lambda icao, done, total, label, status="run", eta_total_s=None:
                        events.append((icao, done, total, label, status)))
    monkeypatch.setattr(progress.config, "BUILD_PROGRESS", True)
    monkeypatch.setattr(progress, "_worker_queue", None)
    return printed, events


def test_v2_progress_reports_seven_steps_and_beats_through_the_same_channel(ui_capture):
    printed, events = ui_capture
    with engine_v2.V2Progress("ZZZZ", period_s=0.1) as vp:
        vp.hb.stop()                        # drive the beat by hand below
        vp.line("[ZZZZ] load 1.00 s  runways 1")
        vp.line("  [partition] cache MISS x")          # not a stage line
        vp.line("[ZZZZ] pack partition 2.00 s  members 3")
        assert vp.bp.running_step()[0] == 3
        vp.hb.poll()                        # the new step arms the clock
        for _o in pulse.each(list(range(10)), "door wells: sill witnesses", "objects"):
            if _o == 2:
                vp.hb.poll(now=time.monotonic() + 1.0)
        pulse.mark("structures")
        assert vp.bp.running_step()[0] == 4
        vp.line("[ZZZZ] planar 3.00 s  faces 9")
        vp.line("[ZZZZ] constraints 1.00 s")
        vp.line("[ZZZZ] solve 1.00 s")
        assert vp.bp.running_step() == (7, engine_v2.V2_PHASE_LABELS[-1])
    banners = [p for p in printed if "still working" not in p]
    assert [b.split("] ", 1)[0].rsplit("[", 1)[1] for b in banners] == \
        [f"{k}/7" for k in range(1, 8)]
    beats = [p for p in printed if "still working" in p]
    assert len(beats) == 1
    assert beats[0].startswith("   Auto-patch: ZZZZ [3/7] Classifying & reading structures")
    assert beats[0].endswith("door wells: sill witnesses 3/10 objects")
    # the GUI event: the same call a banner makes, status "run", the beat's
    # text as the label, the percent unchanged from the step's
    beat_ev = [e for e in events if "still working" in e[3]]
    assert len(beat_ev) == 1 and beat_ev[0][4] == "run" and beat_ev[0][2] == 100
    step3 = [e for e in events if e[3] == engine_v2.V2_PHASE_LABELS[2]][0]
    assert beat_ev[0][1] == step3[1] == 7 + 14
    # the percent moves at every step boundary (no flat [40/100] span)
    pcts = [e[1] for e in events if "still working" not in e[3]]
    assert pcts == sorted(pcts) and len(set(pcts)) == 7
    assert not pulse._listeners and pulse.current() is None


def test_a_beat_in_a_pool_worker_is_the_step_events_tuple(monkeypatch):
    class Q(list):
        def put(self, item):
            self.append(item)
    q = Q()
    monkeypatch.setattr(progress, "_worker_queue", q)
    monkeypatch.setattr(progress.config, "BUILD_PROGRESS", True)
    bp = progress.BuildProgress("ZZZZ", engine_v2.V2_PHASE_LABELS,
                                engine_v2.V2_PHASE_WEIGHTS)
    bp.step()
    bp.heartbeat("Loading — still working: 1m00s in this step, 1m00s total")
    assert len(q) == 2
    assert [len(x) for x in q] == [5, 5]          # (icao, pct, 100, label, eta)
    assert q[1][0] == "ZZZZ" and q[1][2] == 100 and "still working" in q[1][3]
