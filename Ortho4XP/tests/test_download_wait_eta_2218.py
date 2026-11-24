"""#2218: a build step waiting on a download is priced by bytes and rate,
a joiner hears the flight's progress, and interrupted downloads' files
are swept from the extract store.  Headless: injected clocks, fake pids,
no network."""
from __future__ import annotations

import json
import os
import sys
import time

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import O4_Download_Manager as DOWNLOADS  # noqa: E402
import O4_File_Lock as FILE_LOCK  # noqa: E402
import O4_OSM_Extracts as EXTRACTS  # noqa: E402
import O4_UI_Utils as UI  # noqa: E402
from o4_engine import download_meter, session, task_meter  # noqa: E402

MB = 1 << 20


@pytest.fixture(autouse=True)
def _clean_meters():
    download_meter._reset_for_tests()
    task_meter._reset_for_tests()
    yield
    download_meter._reset_for_tests()
    task_meter._reset_for_tests()


class _Clock:
    def __init__(self, now: float) -> None:
        self.now = now

    def __call__(self) -> float:
        return self.now


def _masks_tracker(clock, estimate=60.0):
    tracker = session._EtaTracker(
        [(13, -61)], [("masks", 0.0, 1.0)], {(13, -61): {"masks": estimate}})
    tracker.clock = clock
    tracker.step_started((13, -61), "masks")
    return tracker


def test_waiting_step_is_priced_by_bytes_and_rate_not_by_the_wait():
    """TLPL +13-061: 256 of 758 MB at ~0.6 MB/s is ~14 min, however long
    the step has waited; the old floor let the model's overrun grow."""
    clock = _Clock(1000.0)
    tracker = _masks_tracker(clock)
    clock.now += 120.0                    # 60 s past the 60 s estimate
    before = tracker._current_step_remaining()
    assert before == pytest.approx(30.0)  # overrun recedes at half rate
    download_meter.begin("extract:central-america", 758 * MB)
    download_meter.record(int(0.6 * MB), 1.0, now=clock.now)
    download_meter.update("extract:central-america", 256 * MB)
    download_seconds = (758 - 256) / 0.6
    first = tracker._current_step_remaining()
    assert first == pytest.approx(before + download_seconds, rel=0.01)
    clock.now += 3600.0                   # an hour of waiting, no bytes
    assert tracker._current_step_remaining() == pytest.approx(first)
    download_meter.update("extract:central-america", 700 * MB)
    assert tracker._current_step_remaining() == pytest.approx(
        before + 58 / 0.6, rel=0.01)
    # The download ends: the step resumes where it was, its waited
    # seconds off its elapsed.
    download_meter.end("extract:central-america")
    assert tracker._current_step_remaining() == pytest.approx(before)
    clock.now += 20.0
    assert tracker._current_step_remaining() == pytest.approx(before + 10.0)


def test_a_download_before_its_first_rate_sample_holds_the_step_still():
    clock = _Clock(50.0)
    tracker = _masks_tracker(clock, estimate=100.0)
    clock.now += 40.0
    download_meter.begin("extract:quebec", 500 * MB)
    assert tracker._current_step_remaining() == pytest.approx(60.0)
    clock.now += 900.0
    assert tracker._current_step_remaining() == pytest.approx(60.0)


def test_the_download_restarts_the_steps_bar_windows():
    """The extract drove bar 1 with its own percentage; once it ends the
    masks bar's rate is measured afresh."""
    clock = _Clock(0.0)
    tracker = _masks_tracker(clock)
    tracker.bar_windows = {1: [(0.0, 10.0), (30.0, 40.0)]}
    download_meter.begin("extract:ontario", 10 * MB)
    tracker._current_step_remaining()
    download_meter.end("extract:ontario")
    clock.now = 50.0
    tracker._current_step_remaining()
    assert tracker.bar_windows == {}


def test_flight_progress_reads_the_leaders_temporary_and_length(tmp_path):
    target = tmp_path / "central-america.osm.pbf"
    resource = DOWNLOADS.Resource("osm-extract:central-america",
                                  "https://example.invalid/ca.pbf",
                                  str(target))
    stem = DOWNLOADS._state_stem(resource)
    os.makedirs(os.path.dirname(stem))
    with open(stem + ".json", "w") as handle:
        json.dump({"outcome": "running", "total_bytes": 1000}, handle)
    (tmp_path / "central-america.osm.pbf.tmp-424242-7").write_bytes(
        b"x" * 400)
    (tmp_path / "quebec.osm.pbf.tmp-424242-8").write_bytes(b"x" * 900)
    heard = []

    class Listener(DOWNLOADS.Watcher):
        def waited(self, received, total_bytes):
            heard.append((received, total_bytes))

    clock = _Clock(10.0)
    poll = DOWNLOADS._flight_progress(resource, stem, Listener(), clock)
    poll()
    poll()                                 # within PROGRESS_SECONDS
    assert heard == [(400, 1000)]
    clock.now += DOWNLOADS.PROGRESS_SECONDS
    poll()
    assert heard == [(400, 1000), (400, 1000)]


def test_the_leader_notes_its_length_in_the_flight_state(tmp_path):
    state = tmp_path / "flight.json"
    state.write_text(json.dumps({"outcome": "running", "requests": 1}))
    started = []

    class Listener(DOWNLOADS.Watcher):
        def started(self, total_bytes):
            started.append(total_bytes)

    DOWNLOADS._FlightWatcher(Listener(), str(state)).started(758 * MB)
    assert started == [758 * MB]
    assert json.loads(state.read_text()) == {
        "outcome": "running", "requests": 1, "total_bytes": 758 * MB}


def test_a_foreground_joiner_prices_the_flight_it_waits_on(monkeypatch):
    clock = _Clock(500.0)
    monkeypatch.setattr(EXTRACTS.time, "time", clock)
    monkeypatch.setattr(UI, "progress_bar", lambda *_a: None)
    watcher = EXTRACTS._ExtractWatcher("central-america", foreground=True)
    watcher.waited(100 * MB, 758 * MB)
    assert download_meter.downloading()
    assert download_meter.active_remaining_seconds() is None   # no rate yet
    clock.now += 10.0
    watcher.waited(106 * MB, 758 * MB)
    assert download_meter.active_remaining_seconds() == pytest.approx(
        652 / 0.6, rel=0.01)
    watcher.finished()
    assert not download_meter.downloading()


def test_a_background_joiner_prices_nothing():
    EXTRACTS._ExtractWatcher("quebec", foreground=False).waited(1, 10)
    assert not download_meter.downloading()


def test_store_sweep_removes_dead_and_abandoned_temporaries_only(
        tmp_path, monkeypatch):
    """Fake pids: 111 is dead, 222 is alive.  A dead writer's file goes
    once past the grace, a live writer's stays until it is abandoned."""
    monkeypatch.setattr(EXTRACTS, "STORE_DIRECTORY", str(tmp_path))
    monkeypatch.setattr(FILE_LOCK, "process_is_running",
                        lambda pid: pid == 222)
    lines = []
    monkeypatch.setattr(UI, "vprint", lambda *a: lines.append(a))
    now = time.time()
    ages = {"dead_old": ("a.osm.pbf.tmp-111-1",
                         DOWNLOADS.SWEEP_GRACE_SECONDS + 60),
            "dead_fresh": ("b.osm.pbf.tmp-111-2", 5),
            "live": ("c.osm.pbf.tmp-222-3", 600),
            "live_abandoned": ("d.osm.pbf.tmp-222-4",
                               DOWNLOADS.ABANDONED_SECONDS + 60),
            "extract": ("e.osm.pbf", DOWNLOADS.ABANDONED_SECONDS + 60)}
    for (name, age) in ages.values():
        path = tmp_path / name
        path.write_bytes(b"x")
        os.utime(path, (now - age, now - age))
    assert EXTRACTS._sweep_interrupted_downloads() == 2
    left = sorted(os.listdir(tmp_path))
    assert left == ["b.osm.pbf.tmp-111-2", "c.osm.pbf.tmp-222-3",
                    "e.osm.pbf"]
    assert any("Removed 2 file(s)" in " ".join(map(str, line))
               for line in lines)
    lines.clear()
    assert EXTRACTS._sweep_interrupted_downloads() == 0
    assert lines == []
