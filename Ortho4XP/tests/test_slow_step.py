"""The slow-step alert (#1351): the engine's threshold, words, options and
answers, the child-to-parent hop, and the degraded record of "Use coarser
data".  Headless, no network, no build."""

import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, "src")

import O4_Tile_Failures as FAIL  # noqa: E402
import O4_Vector_Map as VMAP  # noqa: E402
from o4_engine import events, jsonl, parallel, slow_step, task_meter  # noqa: E402
from o4_engine.session import EngineSession, build_done  # noqa: E402

TILE = (56, -4)


@pytest.fixture(autouse=True)
def _clean_meter():
    task_meter._reset_for_tests()
    yield
    task_meter._reset_for_tests()


def _watch(expected=None, alert_after=300.0):
    sent = []
    watch = slow_step.SlowStepWatch(sent.append)
    watch.begin(TILE, "vector", "vector data", expected,
                alert_after=alert_after, now=1000.0)
    return watch, sent


def test_quiet_before_the_threshold_then_one_alert_and_a_refresh():
    watch, sent = _watch()
    assert watch.poll(lambda: 120.0, now=1000.0 + 299) is None
    event = watch.poll(lambda: 120.0, now=1000.0 + 300)
    assert isinstance(event, events.SlowStep) and sent == [event]
    assert (event.lat, event.lon, event.step_key) == (56, -4, "vector")
    assert event.title == "Tile +56-004: the vector data step is slow"
    assert event.options == ("continue", "cancel")
    assert event.option_labels == ("Continue", "Cancel this tile")
    assert "about 2 min" in event.message and event.eta_seconds == 120.0
    assert event.reason == "no_record"
    assert watch.poll(now=1000.0 + 310) is None             # not yet
    assert watch.poll(now=1000.0 + 300 + slow_step.REFRESH_SECONDS)
    watch.end()
    assert sent[-1].resolved and len(sent) == 3


def test_a_step_is_judged_against_its_recorded_time():
    watch, sent = _watch(expected=1200.0)
    assert watch.poll(now=1000.0 + 1200) is None
    event = watch.poll(now=1000.0 + slow_step.EXPECTED_MARGIN * 1200)
    assert event.reason == "longer_than_recorded"
    assert "took about 20 min" in event.message
    assert "no estimate" in event.message


def test_off_never_alerts_and_the_setting_reads_minutes():
    watch, sent = _watch(alert_after=0)
    assert watch.poll(now=1000.0 + 10 ** 6) is None and sent == []
    assert slow_step._alert_after_seconds(0) is None
    assert slow_step._alert_after_seconds(10) == 600.0
    assert slow_step._alert_after_seconds("junk") == 300.0


def test_a_phase_names_itself_and_offers_coarser_data():
    task_meter.begin("approach-rings", 80, what="Downloading areas: "
                     "{done} of {total} done", why="It is remote",
                     reason="remote_fine_elevation", coarser=True)
    task_meter.advance("approach-rings", 30)
    watch, sent = _watch()
    event = watch.poll(lambda: 3000.0, now=1000.0 + 400)
    assert event.message.startswith("Downloading areas: 30 of 80 done.")
    assert "It is remote; at the current rate each one takes" in event.message
    assert event.reason == "remote_fine_elevation"
    assert event.options == ("continue", "coarser", "cancel")
    assert event.option_labels[1] == "Use coarser data"
    assert watch.choose(TILE, "coarser")
    assert task_meter.coarser_requested("approach-rings")
    assert sent[-1].resolved
    assert watch.poll(now=1000.0 + 10 ** 5) is None          # answered
    watch.end()
    assert not sent[-1].message and len(sent) == 2           # no 2nd close


def test_answers_are_refused_when_not_offered():
    watch, sent = _watch()
    assert not watch.choose(TILE, "continue")                # not alerted
    watch.poll(now=1000.0 + 300)
    assert not watch.choose((1, 2), "continue")              # other tile
    assert not watch.choose(TILE, "coarser")                 # no phase
    assert watch.choose(TILE, "continue")
    assert not watch.choose(TILE, "continue")


def test_spoken_durations():
    assert slow_step._spoken_duration(20) == "less than a minute"
    assert slow_step._spoken_duration(185) == "about 3 min"
    assert slow_step._spoken_duration(3600) == "about 1 h"
    assert slow_step._spoken_duration(4800) == "about 1 h 20 min"


def test_session_routes_the_answers(monkeypatch):
    session = EngineSession()
    calls = []
    monkeypatch.setattr(session, "cancel_tile",
                        lambda lat, lon: calls.append((lat, lon)) or True)
    assert session.slow_step_choice(56, -4, "cancel")
    assert calls == [TILE]
    assert not session.slow_step_choice(56, -4, "continue")  # nothing open
    session._parallel = SimpleNamespace(
        slow_step_choice=lambda tile, choice: calls.append((tile, choice))
        or True)
    assert session.slow_step_choice(56, -4, "coarser")
    assert calls[-1] == (TILE, "coarser")
    assert "slow_step_choice" in jsonl._build_handlers(session)


def test_the_alert_survives_the_child_hop_and_the_answer_reaches_it():
    assert "SlowStep" in parallel._FORWARDED_EVENT_TYPES
    payload = jsonl.serialize_event(events.SlowStep(
        lat=56, lon=-4, step_key="vector", title="t", message="m",
        options=("continue", "cancel"),
        option_labels=("Continue", "Cancel this tile"), eta_seconds=60.0))
    rebuilt = parallel._rebuild_event(payload)
    assert list(rebuilt.options) == ["continue", "cancel"]
    assert (rebuilt.lat, rebuilt.title, rebuilt.eta_seconds) == (56, "t", 60.0)
    sent = []
    child = SimpleNamespace(tile=TILE, retired=False, running_step="vector",
                            send=lambda command: sent.append(command) or True)
    run = SimpleNamespace(_lock=parallel.threading.Lock(), _children=[child])
    assert parallel.ParallelBuildRun.slow_step_choice(run, TILE, "continue")
    assert sent == [{"cmd": "slow_step_choice", "lat": 56, "lon": -4,
                     "choice": "continue"}]
    child.running_step = None
    assert not parallel.ParallelBuildRun.slow_step_choice(run, TILE, "x")


def test_coarser_data_is_a_degraded_output_of_the_tile(tmp_path):
    tile = SimpleNamespace(lat=56, lon=-4, build_dir=str(tmp_path),
                           rings_coarsened_last_build=12)
    VMAP._record_coarsened_rings(tile)
    import O4_Unpatched_Airports as UNPATCHED
    rows = UNPATCHED.read_degraded(tile)
    assert [r["code"] for r in rows] == ["elevation_coarsened"]
    built = build_done(56, -4, True, [], degraded=FAIL.from_degraded(rows))
    (warning,) = built.warnings
    assert warning["severity"] == "degraded"
    assert "12 area(s)" in warning["why"]
    tile.rings_coarsened_last_build = 0
    VMAP._record_coarsened_rings(tile)
    assert UNPATCHED.read_degraded(tile) == []


def test_the_session_frames_each_step_and_stamps_the_attempt():
    session = EngineSession()
    seen = []
    session.subscribe(seen.append)
    session._tile_attempts[TILE] = 3
    session._start_step(TILE, "mesh", 0.0, 1.0)
    step = session._slow_step._step
    assert (step["tile"], step["key"], step["name"]) == (TILE, "mesh", "mesh")
    alert = session._slow_step.poll(now=step["t0"] + 10 ** 5)
    assert alert in seen and alert.attempt == 3
    session._finish_step(TILE, "mesh")
    assert seen[-1].resolved and session._slow_step._step is None
