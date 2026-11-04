"""The slow-step alert (#1351): the engine's threshold, words, options and
answers, the child-to-parent hop, and the degraded record of "Use coarser
data".  Headless, no network, no build."""

import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, "src")

import O4_Tile_Failures as FAIL  # noqa: E402
import O4_Vector_Map as VMAP  # noqa: E402
from o4_engine import (  # noqa: E402
    download_meter, events, jsonl, parallel, slow_step, task_meter)
from o4_engine.session import EngineSession, build_done  # noqa: E402

TILE = (56, -4)


@pytest.fixture(autouse=True)
def _clean_meter(monkeypatch):
    task_meter._reset_for_tests()
    download_meter._reset_for_tests()
    # Hermetic: no real lock waits, a roomy disk, no transfer hooks.
    monkeypatch.setattr(slow_step.FLOCK, "lock_waits", lambda: [])
    monkeypatch.setattr(slow_step, "_disk_paths", lambda: ())
    monkeypatch.setattr(download_meter, "watch_transfers", lambda: True)
    yield
    task_meter._reset_for_tests()
    download_meter._reset_for_tests()


T0 = 1000.0


def _watch(enabled=True):
    sent = []
    watch = slow_step.SlowStepWatch(sent.append)
    watch.begin(TILE, "vector", "vector data", enabled=enabled, now=T0)
    return watch, sent


def _activity(monkeypatch, **fields):
    """Make the transfer activity read ``fields`` (a mutable dict)."""
    act = {"in_flight": 0, "busy_since": None, "bytes": 0, "requests": 0,
           "last_progress": None, "hosts": {}}
    act.update(fields)
    monkeypatch.setattr(download_meter, "activity", lambda: dict(act))
    return act


def _phase(key="approach-rings", total=80, idle_since=T0, coarser=False):
    task_meter.begin(key, total, what="Downloading areas: {done} of "
                     "{total} done", why="It is remote",
                     reason="remote_fine_elevation", coarser=coarser)
    task_meter._active[key][5] = idle_since


def test_a_long_step_that_progresses_never_alerts(monkeypatch):
    """Owner 2026-11-04: long because tiles are queued or the CPU is
    shared is not stuck -- an hour of steady bytes and units is quiet."""
    act = _activity(monkeypatch, in_flight=2, busy_since=T0)
    watch, sent = _watch()
    for minute in range(60):
        now = T0 + 60.0 * minute
        act.update(bytes=minute * 10 ** 7, last_progress=now,
                   requests=minute * 5)
        _phase(idle_since=now - 30)
        monkeypatch.setattr(task_meter.time, "time", lambda: now)
        assert watch.poll(lambda: 120.0, now=now) is None
    assert sent == []


def test_a_stalled_download_alerts_then_closes_when_data_returns(
        monkeypatch):
    act = _activity(monkeypatch, in_flight=1, busy_since=T0,
                    last_progress=T0)
    watch, sent = _watch()
    assert watch.poll(now=T0 + slow_step.STALL_SECONDS - 1) is None
    event = watch.poll(lambda: 120.0, now=T0 + slow_step.STALL_SECONDS)
    assert isinstance(event, events.SlowStep) and sent == [event]
    assert event.reason == "download_stalled"
    assert event.title == "Tile +56-004: the vector data step is stuck"
    assert event.message.startswith("Downloading has stopped")
    assert "about 2 min" in event.message and event.eta_seconds == 120.0
    assert event.options == ("continue", "cancel")
    assert event.option_labels == ("Continue", "Cancel this tile")
    assert watch.poll(now=T0 + 130) is None                  # not yet
    assert watch.poll(now=T0 + 120 + slow_step.REFRESH_SECONDS)
    act.update(last_progress=T0 + 200, bytes=10 ** 6)
    assert watch.poll(now=T0 + 201) is None
    assert sent[-1].resolved and len(sent) == 3
    watch.end()
    assert len(sent) == 3                                    # closed once


def test_nothing_in_flight_is_never_a_stall(monkeypatch):
    _activity(monkeypatch, in_flight=0, last_progress=T0)
    watch, sent = _watch()
    assert watch.poll(now=T0 + 10 ** 5) is None and sent == []


def test_a_crawling_download_alerts(monkeypatch):
    act = _activity(monkeypatch, in_flight=1, busy_since=T0)
    watch, sent = _watch()
    rate = slow_step.CRAWL_BYTES_PER_SECOND / 2
    event = None
    for second in range(0, 301, 10):
        act.update(bytes=int(rate * second), last_progress=T0 + second)
        event = watch.poll(now=T0 + second) or event
    assert event is not None and event.reason == "download_crawling"
    assert "25.0 KB/s" in event.message


def test_many_small_requests_are_progress_not_a_crawl(monkeypatch):
    """A provider with no byte progress is measured in requests."""
    act = _activity(monkeypatch, in_flight=1, busy_since=T0)
    watch, sent = _watch()
    for second in range(0, 601, 10):
        act.update(bytes=second * 100, requests=second // 10,
                   last_progress=T0 + second)
        assert watch.poll(now=T0 + second) is None
    assert sent == []


def test_a_refusing_server_alerts_but_one_that_also_serves_does_not(
        monkeypatch):
    act = _activity(monkeypatch, hosts={"data.geopf.fr": (3, 0)})
    watch, sent = _watch()
    act["hosts"] = {"data.geopf.fr": (3, slow_step.REFUSAL_COUNT - 1)}
    assert watch.poll(now=T0 + 5) is None
    act["hosts"] = {"data.geopf.fr": (3, 41)}
    event = watch.poll(now=T0 + 6)
    assert event.reason == "provider_refusing"
    assert "data.geopf.fr has refused or failed 41 requests" in event.message
    watch.end()
    watch.begin(TILE, "vector", "vector data", enabled=True, now=T0)
    act["hosts"] = {"data.geopf.fr": (4, 60)}                # served one
    assert watch.poll(now=T0 + 7) is None


def test_a_counted_phase_with_no_unit_for_ten_minutes_is_hung(monkeypatch):
    _activity(monkeypatch)
    _phase(idle_since=T0, coarser=True)
    task_meter.advance("approach-rings", 30)
    task_meter._active["approach-rings"][5] = T0
    watch, sent = _watch()
    monkeypatch.setattr(task_meter.time, "time",
                        lambda: T0 + slow_step.NO_PROGRESS_SECONDS - 1)
    assert watch.poll(now=T0 + slow_step.NO_PROGRESS_SECONDS - 1) is None
    monkeypatch.setattr(task_meter.time, "time",
                        lambda: T0 + slow_step.NO_PROGRESS_SECONDS)
    event = watch.poll(now=T0 + slow_step.NO_PROGRESS_SECONDS)
    assert event.reason == "no_progress"
    assert event.message.startswith("Downloading areas: 30 of 80 done. "
                                    "Nothing has finished for about 10 min")
    assert event.options == ("continue", "coarser", "cancel")
    assert event.option_labels[1] == "Use coarser data"
    assert watch.choose(TILE, "coarser")
    assert task_meter.coarser_requested("approach-rings")
    assert sent[-1].resolved
    assert watch.poll(now=T0 + 10 ** 5) is None              # answered
    watch.end()
    assert len(sent) == 2                                    # no 2nd close


def test_a_lock_held_by_another_process_for_five_minutes(monkeypatch):
    _activity(monkeypatch)
    monkeypatch.setattr(slow_step.FLOCK, "lock_waits",
                        lambda: [("/c/N56W004.hgt.lock", T0 - 900.0)])
    watch, sent = _watch()
    assert watch.poll(now=T0 + slow_step.LOCK_WAIT_SECONDS - 1) is None
    event = watch.poll(now=T0 + slow_step.LOCK_WAIT_SECONDS)
    assert event.reason == "lock_wait"
    assert "finish with N56W004.hgt (about 5 min" in event.message


def test_a_full_disk_alerts(monkeypatch, tmp_path):
    _activity(monkeypatch)
    monkeypatch.setattr(slow_step, "_disk_paths", lambda: (str(tmp_path),))
    free = {"bytes": 10 ** 12}
    monkeypatch.setattr(
        slow_step.shutil, "disk_usage",
        lambda path: SimpleNamespace(free=free["bytes"]))
    watch, sent = _watch()
    assert watch.poll(now=T0 + 1) is None
    free["bytes"] = 100 * 1024 * 1024
    assert watch.poll(now=T0 + 2) is None                    # checked 15 s
    event = watch.poll(now=T0 + 1 + slow_step.DISK_CHECK_SECONDS)
    assert event.reason == "disk_full" and "100 MB free" in event.message


def test_off_never_alerts_and_the_setting_is_on_off(monkeypatch):
    _activity(monkeypatch, in_flight=1, busy_since=T0)
    watch, sent = _watch(enabled=False)
    assert watch.poll(now=T0 + 10 ** 6) is None and sent == []
    assert not slow_step._alert_on(0)
    assert slow_step._alert_on(5) and slow_step._alert_on(60)
    assert slow_step._alert_on("junk")
    import O4_Cfg_Vars as VARS
    assert VARS.legacy_cfg_value("slow_step_alert_minutes", "30") == "5"
    assert not hasattr(slow_step, "EXPECTED_MARGIN")


def test_answers_are_refused_when_not_offered(monkeypatch):
    _activity(monkeypatch, in_flight=1, busy_since=T0)
    watch, sent = _watch()
    assert not watch.choose(TILE, "continue")                # not alerted
    watch.poll(now=T0 + 300)
    assert not watch.choose((1, 2), "continue")              # other tile
    assert not watch.choose(TILE, "coarser")                 # no phase
    assert watch.choose(TILE, "continue")
    assert not watch.choose(TILE, "continue")


def test_the_transfer_hooks_count_bytes_and_verdicts(monkeypatch):
    """``watch_transfers`` feeds ``activity`` from a real requests send
    (a stub adapter: no network)."""
    import requests
    from requests.adapters import BaseAdapter
    monkeypatch.undo()
    download_meter._reset_for_tests()
    from urllib3.response import HTTPResponse
    monkeypatch.setattr(requests.Session, "send", requests.Session.send)
    for name in ("read", "read_chunked"):
        monkeypatch.setattr(HTTPResponse, name, getattr(HTTPResponse, name))
    monkeypatch.setattr(download_meter, "_watching", False)

    class Stub(BaseAdapter):
        def __init__(self, status):
            super().__init__()
            self.status = status

        def send(self, request, **kwargs):
            response = requests.Response()
            response.status_code, response._content = self.status, b"x" * 7
            response.url, response.request = request.url, request
            return response

        def close(self):
            pass

    assert download_meter.watch_transfers()
    assert download_meter.watch_transfers()                  # idempotent
    for status in (200, 400, 400, 404):
        session = requests.Session()
        session.mount("https://", Stub(status))
        session.get("https://wfs.example.org/q")
    act = download_meter.activity()
    assert act["hosts"] == {"wfs.example.org": (1, 2)}
    assert act["in_flight"] == 0 and act["requests"] >= 1
    download_meter.begin("extract:x", 100)
    assert download_meter.activity()["in_flight"] == 1
    download_meter.update("extract:x", 60)
    assert download_meter.activity()["bytes"] == 60
    download_meter.end("extract:x")
    assert download_meter.activity()["busy_since"] is None


def test_lock_waits_are_noted_while_contended(tmp_path, monkeypatch):
    import O4_File_Lock as FLOCK_REAL
    monkeypatch.undo()
    target = str(tmp_path / "cell.hgt")
    with open(target + ".lock", "w", encoding="utf-8",
              newline="\n") as held:
        held.write("%d\n%s\n" % (__import__("os").getpid(), "elsewhere"))
    seen = []
    monkeypatch.setattr(FLOCK_REAL, "_lock_file_is_stale",
                        lambda *a: False)
    monkeypatch.setattr(FLOCK_REAL.time, "sleep",
                        lambda s: seen.append(FLOCK_REAL.lock_waits()))
    with FLOCK_REAL.hold_file_lock(target, timeout_seconds=0.05) as got:
        assert not got
    assert seen and seen[0][0][0] == target + ".lock"
    assert FLOCK_REAL.lock_waits() == []


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


def test_the_session_frames_each_step_and_stamps_the_attempt(monkeypatch):
    _activity(monkeypatch, in_flight=1, busy_since=T0)
    session = EngineSession()
    seen = []
    session.subscribe(seen.append)
    session._tile_attempts[TILE] = 3
    session._start_step(TILE, "mesh", 0.0, 1.0)
    step = session._slow_step._step
    assert (step["tile"], step["key"], step["name"]) == (TILE, "mesh", "mesh")
    step["enabled"], step["t0"] = True, T0
    alert = session._slow_step.poll(now=T0 + 10 ** 5)
    assert alert in seen and alert.attempt == 3
    session._finish_step(TILE, "mesh")
    assert seen[-1].resolved and session._slow_step._step is None
