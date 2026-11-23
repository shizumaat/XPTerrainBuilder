"""The download manager across REAL processes (#2258), against a local
server: one transfer per resource, joiners woken, Stop and kills leave no
temporaries, limits hold.  Headless; loopback only."""
from __future__ import annotations

import http.server
import json
import os
import subprocess
import sys
import threading
import time

import pytest

SRC = os.path.join(os.path.dirname(__file__), "..", "src")
sys.path.insert(0, SRC)

import O4_Download_Manager as DOWNLOADS  # noqa: E402
import O4_Machine_Slots as SLOTS  # noqa: E402

BODY = b"HEADER" + b"x" * (1 << 20)

#: one client process: fetch, print the result as JSON
CLIENT = r"""
import json, os, sys, time
sys.path.insert(0, sys.argv[1])
import O4_Download_Manager as D
key, url, target, stop_file, server_limit, total_limit = sys.argv[2:8]
result = D.fetch(
    D.Resource(key, url, target),
    should_stop=lambda: bool(stop_file) and os.path.exists(stop_file),
    server_limit=int(server_limit), total_limit=int(total_limit))
print(json.dumps({"status": result.status, "joined": result.joined,
                  "transferred": result.transferred}))
"""


class _Server(http.server.ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, delay=0.02, status=200, truncate=False, hold=False):
        super().__init__(("127.0.0.1", 0), _Handler)
        #: ``hold``: the FIRST GET stops after one chunk until released
        self.release = threading.Event()
        if not hold:
            self.release.set()
        self.delay = delay
        self.status = status
        self.truncate = truncate
        self.gets: dict = {}
        self.active = 0
        self.peak = 0
        self.guard = threading.Lock()

    @property
    def base(self):
        return "http://127.0.0.1:%d/" % self.server_address[1]


class _Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        server = self.server
        counted = True
        with server.guard:
            server.gets[self.path] = server.gets.get(self.path, 0) + 1
            first = sum(server.gets.values()) == 1
            server.active += 1
            server.peak = max(server.peak, server.active)
        try:
            if server.status != 200:
                time.sleep(server.delay * 20)
                self.send_error(server.status)
                return
            self.send_response(200)
            self.send_header("Content-Length", str(len(BODY)))
            self.end_headers()
            sent = len(BODY) // 2 if server.truncate else len(BODY)
            for start in range(0, sent, 1 << 17):
                if start + (1 << 17) >= sent:
                    # Counted out BEFORE the last bytes: the client holds
                    # its slot until it has them, so two requests counted
                    # at once were really two slots held at once.
                    counted = _leave(server, counted)
                self.wfile.write(BODY[start:min(start + (1 << 17), sent)])
                self.wfile.flush()
                if first:
                    server.release.wait(60)
                time.sleep(server.delay)
        except OSError:
            pass
        finally:
            _leave(server, counted)


def _leave(server, counted):
    """Count a request out once; False from then on."""
    if counted:
        with server.guard:
            server.active -= 1
    return False


@pytest.fixture
def serve():
    servers = []

    def start(**options):
        server = _Server(**options)
        threading.Thread(target=server.serve_forever, daemon=True).start()
        servers.append(server)
        return server
    yield start
    for server in servers:
        server.shutdown()
        server.server_close()


@pytest.fixture
def session(tmp_path, monkeypatch):
    """One slot session every client process inherits."""
    (tmp_path / "slots").mkdir()
    monkeypatch.setenv(SLOTS.ENV_DIR, str(tmp_path / "slots"))
    monkeypatch.setenv(SLOTS.ENV_CAPACITY, "8")
    store = tmp_path / "store"
    store.mkdir()
    return store


def _client(key, url, target, stop_file="", server_limit=4, total_limit=8):
    return subprocess.Popen(
        [sys.executable, "-c", CLIENT, SRC, key, url, str(target), stop_file,
         str(server_limit), str(total_limit)],
        stdout=subprocess.PIPE, text=True)


def _results(clients):
    out = []
    for client in clients:
        stdout, _ = client.communicate(timeout=120)
        out.append(json.loads(stdout))
    return out


def _temporaries(store):
    return [name for name in os.listdir(store) if ".tmp-" in name]


def _wait_for(predicate, seconds=30.0):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return False


def test_n_processes_make_one_transfer(serve, session):
    server = serve()
    target = session / "region.pbf"
    url = server.base + "region.pbf"
    results = _results([_client("r", url, target) for _ in range(8)])
    assert server.gets == {"/region.pbf": 1}
    assert all(result["status"] == DOWNLOADS.READY for result in results)
    assert sum(result["transferred"] for result in results) == 1
    assert target.read_bytes() == BODY
    assert _temporaries(session) == []
    assert DOWNLOADS.request_counts(str(session)) == {"r": 1}


def test_stop_ends_leader_and_joiners_with_no_temporaries(serve, session):
    server = serve(hold=True)
    target = session / "region.pbf"
    stop = str(session / "stop")
    url = server.base + "region.pbf"
    clients = [_client("r", url, target, stop) for _ in range(4)]
    assert _wait_for(lambda: _temporaries(session))
    with open(stop, "w", encoding="utf-8", newline="\n"):
        pass
    server.release.set()
    results = _results(clients)
    assert all(result["status"] == DOWNLOADS.STOPPED for result in results)
    assert not target.exists()
    assert _temporaries(session) == []
    assert server.gets == {"/region.pbf": 1}


def test_killed_leader_is_taken_over_and_its_temporary_removed(serve, session):
    server = serve(hold=True)
    target = session / "region.pbf"
    url = server.base + "region.pbf"
    leader = _client("r", url, target)
    assert _wait_for(lambda: _temporaries(session))
    joiner = _client("r", url, target)
    leader.kill()
    leader.communicate()
    server.release.set()
    result = _results([joiner])[0]
    assert result["status"] == DOWNLOADS.READY and result["transferred"]
    assert target.read_bytes() == BODY
    assert _temporaries(session) == []
    assert server.gets == {"/region.pbf": 2}


def test_joiners_share_the_failure_they_waited_for(serve, session):
    server = serve(delay=0.1, status=404)
    url = server.base + "gone.pbf"
    results = _results([_client("g", url, session / "gone.pbf")
                        for _ in range(4)])
    assert all(result["status"] == DOWNLOADS.FAILED for result in results)
    assert server.gets == {"/gone.pbf": 1}
    assert _temporaries(session) == []


def test_server_limit_holds_across_processes(serve, session):
    server = serve()
    clients = [_client("r%d" % i, server.base + "r%d" % i,
                       session / ("r%d" % i), server_limit=2)
               for i in range(6)]
    assert all(r["status"] == DOWNLOADS.READY for r in _results(clients))
    assert len(server.gets) == 6 and server.peak <= 2


def test_total_limit_holds_across_servers(serve, session):
    first, second = serve(), serve()
    clients = [_client("r%d" % i, (first if i % 2 else second).base + "f",
                       session / ("r%d" % i), total_limit=3)
               for i in range(8)]
    peaks = []
    watching = threading.Event()

    def watch():
        while not watching.is_set():
            peaks.append(first.active + second.active)
            time.sleep(0.002)
    watcher = threading.Thread(target=watch)
    watcher.start()
    try:
        assert all(r["status"] == DOWNLOADS.READY for r in _results(clients))
    finally:
        watching.set()
        watcher.join()
    assert max(peaks) <= 3


def test_truncated_transfer_is_not_installed(serve, session):
    server = serve(truncate=True)
    target = session / "region.pbf"
    result = DOWNLOADS.fetch(
        DOWNLOADS.Resource("r", server.base + "region.pbf", str(target)))
    assert result.status == DOWNLOADS.FAILED
    assert not target.exists() and _temporaries(session) == []


def test_invalid_payload_is_not_installed(serve, session):
    server = serve()
    target = session / "region.pbf"
    result = DOWNLOADS.fetch(DOWNLOADS.Resource(
        "r", server.base + "region.pbf", str(target),
        is_valid=lambda path: False))
    assert result.status == DOWNLOADS.INVALID
    assert not target.exists() and _temporaries(session) == []


def test_refresh_replaces_a_valid_target(serve, session):
    server = serve()
    target = session / "region.pbf"
    target.write_bytes(b"old")
    resource = DOWNLOADS.Resource("r", server.base + "region.pbf", str(target))
    assert DOWNLOADS.fetch(resource).transferred is False
    assert DOWNLOADS.fetch(resource, refresh=True).transferred is True
    assert target.read_bytes() == BODY


def test_sweep_keeps_a_live_transfer_and_removes_a_dead_one(session):
    done = subprocess.run([sys.executable, "-c",
                           "import os; print(os.getpid())"],
                          capture_output=True, text=True, check=True)
    dead = session / ("a.pbf.tmp-%d-1" % int(done.stdout))
    live = session / ("b.pbf.tmp-%d-1" % os.getppid())
    other = session / "index-v1.json"
    for path in (dead, live, other):
        path.write_bytes(b"x")
    old = time.time() - DOWNLOADS.SWEEP_GRACE_SECONDS - 1
    os.utime(dead, (old, old))
    os.utime(live, (old, old))
    assert DOWNLOADS.sweep_stale_temporaries(str(session)) == 1
    assert not dead.exists() and live.exists() and other.exists()


def test_in_flight_sees_another_holder(session):
    resource = DOWNLOADS.Resource("r", "http://127.0.0.1:1/r",
                                  str(session / "r"))
    assert DOWNLOADS.in_flight(resource) is False
    stem = DOWNLOADS._state_stem(resource)
    os.makedirs(os.path.dirname(stem), exist_ok=True)
    flight = SLOTS.try_os_lock(stem + ".lock")
    try:
        assert DOWNLOADS.in_flight(resource) is True
    finally:
        SLOTS.release_os_lock(flight)
    assert DOWNLOADS.in_flight(resource) is False


def test_unusable_folder_fails_at_once(tmp_path):
    blocker = tmp_path / "file"
    blocker.write_bytes(b"x")
    result = DOWNLOADS.fetch(DOWNLOADS.Resource(
        "r", "http://127.0.0.1:1/r", str(blocker / "r")))
    assert result.status == DOWNLOADS.FAILED
