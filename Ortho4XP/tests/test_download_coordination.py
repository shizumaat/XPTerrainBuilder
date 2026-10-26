"""Machine-wide download coordination (issue #1236): one request budget per
server for the whole build session (``O4_Machine_Slots`` named classes), and
one in-flight download per file across processes (``O4_File_Lock``) for base
elevation cells and orthophotos.

Real ``multiprocessing`` workers on ``tmp_path``; the network is a local
stub that counts its calls.  No network.
"""
from __future__ import annotations

import asyncio
import multiprocessing
import os
import subprocess
import sys
import time
import types
from pathlib import Path

import pytest

SRC = str(Path(__file__).resolve().parents[1] / "src")
sys.path.insert(0, SRC)

import O4_File_Lock as LOCK  # noqa: E402
import O4_Machine_Slots as SLOTS  # noqa: E402


@pytest.fixture
def slot_session(tmp_path, monkeypatch):
    """A slot session every spawned worker inherits through the environment."""
    path = tmp_path / "slots"
    path.mkdir()
    monkeypatch.setenv(SLOTS.ENV_DIR, str(path))
    monkeypatch.setenv(SLOTS.ENV_CAPACITY, "4")
    monkeypatch.setenv(SLOTS.ENV_UNGATED, "1")
    return path


def _append(path, text):
    with open(path, "a", encoding="utf-8", newline="") as handle:
        handle.write(text)


def _lines(path):
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as handle:
        return [line.strip() for line in handle if line.strip()]


def _run_workers(target, args_list, timeout=120):
    context = multiprocessing.get_context("spawn")
    processes = [context.Process(target=target, args=args) for args in args_list]
    for process in processes:
        process.start()
    for process in processes:
        process.join(timeout=timeout)
        assert process.exitcode == 0


# =====================================================================
# One base elevation cell, two tile processes: fetched once
# =====================================================================
class _CountingBaseStrategy:
    """Downloads (counts) only when the cell file is not cached yet."""

    calls_file = ""
    cell_file = ""

    def ensure_tile(self, definition, lat, lon, verbose=True):
        if os.path.exists(self.cell_file):
            return 1
        _append(self.calls_file, "fetch\n")
        time.sleep(0.4)                        # long enough to collide
        _append(self.cell_file, "cell\n")
        return 1


def _dem_worker(src, elevation_dir, calls_file, cell_file):
    sys.path.insert(0, src)
    sys.path.insert(0, os.path.dirname(src))
    import O4_Airport_Elevation_Insets as INSETS
    import O4_File_Names as FNAMES
    from elevation_access import base_fallback

    FNAMES.Elevation_dir = elevation_dir
    _CountingBaseStrategy.calls_file = calls_file
    _CountingBaseStrategy.cell_file = cell_file
    INSETS.resolve_base_definition = (
        lambda lat, lon, selector="auto", prefer_coarse=False:
        {"code": "TESTBASE", "access_strategy": "counting"})
    INSETS.ACCESS_STRATEGIES = {"counting": _CountingBaseStrategy}
    base_fallback.ensure_tile_or_fallback = (
        lambda strategy, definition, lat, lon, verbose, *a, **k:
        strategy.ensure_tile(definition, lat, lon, verbose))
    assert INSETS.ensure_base_tile("auto", 36, -87) == 1


def test_the_same_base_cell_is_fetched_once_by_two_processes(tmp_path):
    calls = str(tmp_path / "calls.txt")
    cell = str(tmp_path / "cell.hgt")
    _run_workers(_dem_worker,
                 [(SRC, str(tmp_path / "Elevation"), calls, cell)] * 2)
    assert _lines(calls) == ["fetch"]
    assert _lines(cell) == ["cell"]


# =====================================================================
# One orthophoto, two processes: downloaded once, reused by the other
# =====================================================================
def _ortho_worker(src, file_dir, calls_file):
    sys.path.insert(0, src)
    import O4_Imagery_Utils as IMG

    def stub_download(file_dir, file_name, *attrs, **options):
        _append(calls_file, "download\n")
        time.sleep(0.4)
        _append(os.path.join(file_dir, file_name), "jpeg")
        return 1

    IMG.download_jpeg_ortho = stub_download
    noted = []
    assert IMG.download_orthophoto_once(
        file_dir, "1_2_TEST16.jpg", 2, 1, 16, "TEST",
        on_download=lambda: noted.append(1)) == 1


def test_the_same_orthophoto_is_downloaded_once_by_two_processes(tmp_path):
    calls = str(tmp_path / "calls.txt")
    file_dir = str(tmp_path / "Orthophotos" / "TEST_16")
    _run_workers(_ortho_worker, [(SRC, file_dir, calls)] * 2)
    assert _lines(calls) == ["download"]
    assert not any(name.endswith(".lock") for name in os.listdir(file_dir))


# =====================================================================
# A server budget of 2, four tile processes: never more than 2 at once
# =====================================================================
def _imagery_request_worker(src, active_dir, log_file, requests_each):
    sys.path.insert(0, src)
    import O4_Imagery_Utils as IMG

    class Answer(types.SimpleNamespace):
        def __str__(self):
            return "<Response [404]>"

    class Session:
        def get(self, url, timeout=None, headers=None):
            marker = os.path.join(active_dir, "%d-%d" % (os.getpid(), time.monotonic_ns()))
            _append(marker, "x")
            _append(log_file, "%d\n" % len(os.listdir(active_dir)))
            time.sleep(0.05)
            os.remove(marker)
            return Answer(headers={}, content=b"")

    session = Session()
    for n in range(requests_each):
        IMG.http_request_to_image(
            256, 256, "https://tiles.example.test/%d.jpg" % n, None, session,
            host_limit=2)


def test_a_server_budget_of_two_holds_across_four_processes(tmp_path, slot_session):
    active = tmp_path / "active"
    active.mkdir()
    log = str(tmp_path / "in_flight.txt")
    _run_workers(_imagery_request_worker,
                 [(SRC, str(active), log, 6)] * 4)
    seen = [int(n) for n in _lines(log)]
    assert len(seen) == 24
    assert max(seen) <= 2
    assert max(seen) == 2                      # and the budget is used


def test_a_class_takes_at_most_its_limit_and_gives_back(slot_session):
    held = SLOTS.try_take_class("net:a.example", 5, limit=3)
    assert held.count == 3
    assert SLOTS.try_take_class("net:a.example", 1, limit=3).count == 0
    # another server's budget is its own
    with SLOTS.try_take_class("net:b.example", 1, limit=3) as other:
        assert other.count == 1
    held.release()
    with SLOTS.try_take_class("net:a.example", 3, limit=3) as again:
        assert again.count == 3


def test_a_class_wait_is_bounded_and_ends_on_give_up(slot_session):
    with SLOTS.try_take_class("net:busy.example", 1, limit=1):
        t0 = time.monotonic()
        late = SLOTS.take_class("net:busy.example", 1, 1, timeout_s=0.3, poll_s=0.02)
        assert late.count == 0 and 0.25 <= time.monotonic() - t0 < 5
        stopped = SLOTS.take_class("net:busy.example", 1, 1, give_up=lambda: True)
        assert stopped.count == 0


def test_net_class_is_the_host():
    assert SLOTS.net_class("https://Tiles.Example.com:8443/a/b?c=1") == "net:tiles.example.com:8443"
    assert SLOTS.net_class("https://user:pw@h.example/x") == "net:h.example"
    assert SLOTS.net_class("h.example") == "net:h.example"


# =====================================================================
# Crashed holders are reaped
# =====================================================================
_HOLDER = (
    "import sys, time; sys.path.insert(0, sys.argv[1]); import {module} as M;"
    "{hold}; print('held', flush=True); time.sleep(60)")


def _start_holder(module, hold, *args):
    return subprocess.Popen(
        [sys.executable, "-c", _HOLDER.format(module=module, hold=hold), SRC, *args],
        stdout=subprocess.PIPE, text=True, encoding="utf-8", env=dict(os.environ))


def _kill(child):
    child.kill()
    child.wait(10)
    child.stdout.close()


def test_a_killed_holders_file_lock_is_reaped_at_once(tmp_path):
    target = str(tmp_path / "cell.hgt")
    child = _start_holder(
        "O4_File_Lock", "c = M.hold_file_lock(sys.argv[2]); c.__enter__()", target)
    try:
        assert child.stdout.readline().strip() == "held"
        with LOCK.hold_file_lock(target, timeout_seconds=0.5) as acquired:
            assert acquired is False           # a LIVE holder is waited for
    finally:
        _kill(child)
    assert os.path.exists(target + ".lock")     # the killed holder left it
    t0 = time.monotonic()
    with LOCK.hold_file_lock(target, timeout_seconds=30.0) as acquired:
        assert acquired is True
    assert time.monotonic() - t0 < 5           # not the hour rule: its pid is gone
    assert not os.path.exists(target + ".lock")


def test_a_lock_from_another_host_is_left_to_the_hour_rule(tmp_path):
    target = str(tmp_path / "cell.hgt")
    _append(target + ".lock", "999999 2026-10-26T00:00:00 some-other-machine\n")
    with LOCK.hold_file_lock(target, timeout_seconds=0.3) as acquired:
        assert acquired is False
    assert os.path.exists(target + ".lock")


def test_a_killed_holders_class_slot_comes_back(slot_session):
    child = _start_holder(
        "O4_Machine_Slots", "h = M.try_take_class('net:k.example', 2, 2); assert h.count == 2")
    try:
        assert child.stdout.readline().strip() == "held"
        assert SLOTS.try_take_class("net:k.example", 1, 2).count == 0
    finally:
        _kill(child)
    with SLOTS.try_take_class("net:k.example", 2, 2) as after:
        assert after.count == 2


# =====================================================================
# The async imagery fetcher draws on the same budget
# =====================================================================
def test_the_async_fetcher_never_exceeds_its_shared_budget():
    pytest.importorskip("curl_cffi")
    import O4_Imagery_Fetch as FETCH

    granted = {"now": 0, "peak": 0}

    class Slot:
        def release(self):
            granted["now"] -= 1

    def budget(request):
        if granted["now"] >= 2:
            return None
        granted["now"] += 1
        granted["peak"] = max(granted["peak"], granted["now"])
        return Slot()

    class Probe(FETCH.Fetcher):
        active = 0
        peak = 0

        def _ensure_session(self):
            return None

        async def _transfer(self, session, req, group):
            Probe.active += 1
            Probe.peak = max(Probe.peak, Probe.active)
            await asyncio.sleep(0.02)
            Probe.active -= 1
            return FETCH._Outcome("ok", 200, b"x", {}, 0.02)

    fetcher = Probe(max_in_flight=16, start_in_flight=16, budget=budget)
    requests = [FETCH.FetchRequest(n, "http://t.example/%d" % n) for n in range(20)]
    results = asyncio.run(fetcher.fetch_many(requests))
    assert [r.status for r in results] == [200] * 20
    assert Probe.peak <= 2 and granted["peak"] == 2
    assert granted["now"] == 0                 # every slot given back
