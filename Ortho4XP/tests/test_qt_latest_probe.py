"""#1546: a window's reanchor probe is bounded — one worker in flight,
superseded requests never run, nothing delivered after close, and the
worker is gone once the window closes.

A thread per request had piled up ~200 probes in one Qt suite process
(each a full Custom Scenery scan outliving its window) and Python 3.14's
collector crashed inside one.  Offscreen; the scan is a slow stub.
"""

import json
import os
import sys
import threading
import time

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest  # noqa: E402

import O4_Qt_Latest_Probe as QTPROBE  # noqa: E402

PROBE_NAME = "o4-reanchor-probe"


def _probe_threads(name=PROBE_NAME):
    return [t for t in threading.enumerate() if t.name == name]


def _wait_until(predicate, seconds=5.0):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return predicate()


def test_runner_single_flight_latest_wins_and_close_joins():
    ran, delivered = [], []
    gate = threading.Event()

    def work(value, should_stop):
        ran.append(value)
        gate.wait(5)
        return value

    probe = QTPROBE.LatestProbe(work, delivered.append, name="t-probe")
    probe.submit(0)
    assert _wait_until(lambda: ran == [0])
    for value in range(1, 50):
        probe.submit(value)
        assert len(_probe_threads("t-probe")) <= 1
    gate.set()
    assert _wait_until(lambda: not probe.in_flight())
    # the first request, then only the newest of the 49 queued behind it
    assert ran == [0, 49]
    assert delivered == [49]
    probe.close()
    probe.submit(7)
    assert not probe.in_flight() and _probe_threads("t-probe") == []


def test_runner_close_stops_delivery_and_ends_the_scan():
    delivered, started = [], threading.Event()

    def work(should_stop):
        started.set()
        while not should_stop():
            time.sleep(0.005)
        return "late"

    probe = QTPROBE.LatestProbe(work, delivered.append, name="t-probe2")
    probe.submit()
    assert started.wait(5)
    probe.close()
    assert _probe_threads("t-probe2") == []
    assert delivered == []


pytest.importorskip("PySide6")

import O4_Qt_GUI as GUI  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402


@pytest.fixture(scope="module")
def qapp():
    yield QApplication.instance() or QApplication([])


def _open_window(tmp_path, monkeypatch, index):
    prefs_path = str(tmp_path / ("prefs%d.json" % index))
    with open(prefs_path, "w", encoding="utf-8", newline="") as handle:
        # an EXISTING prefs file: an absent one arms the modal wizard
        json.dump({"output_dir": str(tmp_path)}, handle)
    monkeypatch.setattr(GUI, "PREFS_FILE", prefs_path)
    win = GUI.MainWindow()
    monkeypatch.setattr(win, "refresh_tiles", lambda: None)
    monkeypatch.setattr(win, "_refresh_scenery_packs", lambda: None)
    monkeypatch.setattr(win.map, "active_tile", lambda: (25, 51))
    return win


def test_windows_bound_probe_threads_and_reach_zero_after_close(
        qapp, tmp_path, monkeypatch):
    import O4_Config_Utils as CFG
    import O4_UI_Utils as UI
    from auto_patch import object_rebake

    scans = []

    def slow_scan(scenery_dir, tile=None, should_stop=None):
        scans.append(tile)
        while not should_stop():
            time.sleep(0.005)
        return []

    monkeypatch.setattr(object_rebake, "modified_packs", slow_scan)
    monkeypatch.setattr(CFG, "custom_scenery_dir", str(tmp_path),
                        raising=False)
    monkeypatch.setattr(GUI, "TILE_SCAN_CACHE_FILE",
                        str(tmp_path / "tile-scan.json"))
    saved_stdout = sys.stdout
    windows = []
    try:
        for index in range(4):
            win = _open_window(tmp_path, monkeypatch, index)
            windows.append(win)
            for _ in range(25):
                win._refresh_modified_airports()
            assert len(_probe_threads()) <= len(windows)
        assert _wait_until(lambda: len(_probe_threads()) == len(windows))
        for win in windows:
            win._building = False
            win.close()
            win.deleteLater()
        assert _wait_until(lambda: _probe_threads() == [])
        # 100 requests, at most one scan per window plus its one queued
        # successor — never one per request
        assert len(scans) <= 2 * len(windows)
    finally:
        for win in windows:
            win._reanchor_probe.close()
        UI.engine_session = None
        sys.stdout = saved_stdout
