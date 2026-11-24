"""The download manager's caller transfers, its lock-only flight and its
server slot (#2258, round lrm1): one transfer per key across threads, an
atomic install, Stop within a poll, a raised failure handed back.
Headless; no network."""
from __future__ import annotations

import os
import sys
import threading
import time

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import O4_Download_Manager as DOWNLOADS  # noqa: E402
import O4_Machine_Slots as SLOTS  # noqa: E402


@pytest.fixture
def store(tmp_path, monkeypatch):
    (tmp_path / "slots").mkdir()
    monkeypatch.setenv(SLOTS.ENV_DIR, str(tmp_path / "slots"))
    monkeypatch.setenv(SLOTS.ENV_CAPACITY, "8")
    folder = tmp_path / "store"
    folder.mkdir()
    return folder


def _resource(store, **options):
    return DOWNLOADS.Resource("k", "made:k", str(store / "file.bin"),
                              **options)


def test_a_transfer_runs_once_and_its_joiners_take_the_file(store):
    calls = []
    release = threading.Event()

    def transfer(temporary, _stop):
        calls.append(temporary)
        release.wait(10)
        with open(temporary, "wb") as handle:
            handle.write(b"body")
        return True

    results = []

    def one():
        results.append(DOWNLOADS.fetch(_resource(store), transfer=transfer))

    threads = [threading.Thread(target=one) for _ in range(3)]
    for thread in threads:
        thread.start()
    time.sleep(0.5)
    release.set()
    for thread in threads:
        thread.join(10)
    assert len(calls) == 1
    assert calls[0].startswith(str(store / "file.bin") + ".tmp-")
    assert sorted(r.joined for r in results) == [False, True, True]
    assert all(r.ok for r in results)
    assert (store / "file.bin").read_bytes() == b"body"
    assert [n for n in os.listdir(store) if ".tmp-" in n] == []


def test_a_raised_failure_is_handed_back_and_not_installed(store):
    def transfer(temporary, _stop):
        with open(temporary, "wb") as handle:
            handle.write(b"half")
        raise RuntimeError("refused")

    result = DOWNLOADS.fetch(_resource(store, shares_failure=False),
                             transfer=transfer)
    assert result.status == DOWNLOADS.FAILED
    assert str(result.error) == "refused"
    assert not (store / "file.bin").exists()
    assert [n for n in os.listdir(store) if ".tmp-" in n] == []


def test_without_shared_failure_a_later_caller_flies_itself(store):
    answers = iter([False, True])

    def transfer(temporary, _stop):
        if next(answers):
            with open(temporary, "wb") as handle:
                handle.write(b"x")
            return DOWNLOADS.READY
        return DOWNLOADS.FAILED

    resource = _resource(store, shares_failure=False)
    assert DOWNLOADS.fetch(resource, transfer=transfer).status == \
        DOWNLOADS.FAILED
    assert DOWNLOADS.fetch(resource, transfer=transfer).ok
    assert DOWNLOADS.request_counts(str(store)) == {"k": 2}


def test_state_dir_holds_the_lock_and_count(store, tmp_path):
    state = tmp_path / "state"

    def transfer(temporary, _stop):
        with open(temporary, "wb") as handle:
            handle.write(b"x")
        return True

    assert DOWNLOADS.fetch(_resource(store, state_dir=str(state)),
                           transfer=transfer).ok
    assert not (store / ".download_manager").exists()
    assert any(name.endswith(".lock") for name in os.listdir(state))


def test_hold_flight_waits_for_the_holder_and_ends_at_stop(store):
    lock = str(store / "section.lock")
    stop = threading.Event()
    with DOWNLOADS.hold_flight(lock) as first:
        assert first
        outcome = []

        def second():
            with DOWNLOADS.hold_flight(lock, stop.is_set) as held:
                outcome.append((held, time.monotonic()))

        thread = threading.Thread(target=second)
        thread.start()
        time.sleep(0.3)
        assert outcome == []                  # it waits
        stopped_at = time.monotonic()
        stop.set()
        thread.join(5)
    assert outcome[0][0] is False
    assert outcome[0][1] - stopped_at < 1.0
    assert not os.path.exists(lock)           # it exists only while held
    with DOWNLOADS.hold_flight(lock) as again:   # released on exit
        assert again


def test_server_slot_waits_without_limit_and_gives_up_at_stop(store):
    url = "https://slots.test/x"
    stop = threading.Event()
    with DOWNLOADS.server_slot(url, server_limit=1) as first:
        assert first
        outcome = []

        def second():
            with DOWNLOADS.server_slot(url, stop.is_set,
                                       server_limit=1) as held:
                outcome.append(held)

        thread = threading.Thread(target=second)
        thread.start()
        time.sleep(0.3)
        assert outcome == []
        stop.set()
        thread.join(5)
    assert outcome == [False]


class _Body:
    headers = {"Content-Length": "6"}

    def __init__(self, chunks):
        self.chunks = chunks

    def iter_content(self, _size):
        yield from self.chunks


def test_write_body_stops_between_chunks_and_checks_the_length(tmp_path):
    path = str(tmp_path / "body")
    seen = []

    def stop():
        seen.append(1)
        return len(seen) > 1

    assert DOWNLOADS.write_body(_Body([b"abc", b"def"]), path, stop) == \
        (DOWNLOADS.STOPPED, 3)
    assert DOWNLOADS.write_body(_Body([b"abc", b"def"]), path) == \
        (DOWNLOADS.READY, 6)
    with pytest.raises(OSError):
        DOWNLOADS.write_body(_Body([b"abc"]), path)


def test_hold_flight_stays_exclusive_while_holders_remove_the_file(store):
    """Each holder removes the lock file it held; a waiter that locked the
    removed file locks the new one, so two never hold at once."""
    lock = str(store / "busy.lock")
    inside = [0]
    peak = [0]
    guard = threading.Lock()

    def one():
        for _ in range(5):
            with DOWNLOADS.hold_flight(lock) as held:
                assert held
                with guard:
                    inside[0] += 1
                    peak[0] = max(peak[0], inside[0])
                time.sleep(0.01)
                with guard:
                    inside[0] -= 1

    threads = [threading.Thread(target=one) for _ in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(30)
    assert peak[0] == 1
    assert not os.path.exists(lock)
