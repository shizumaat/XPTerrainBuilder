"""The default-airport index over the engine protocol
(docs/specs/airport-index-engine-command-spec.md).

``O4_Airport_Index`` is the project's ONE apt.dat parser.  A front end
with no Python of its own (the macOS application) reaches it through the
``airport_index`` command instead of growing a second parser, and gets
back either the cache path to read or a ``building`` status completed by
the :class:`AirportIndexReady` event.

Covered here: the command registration, all three reply shapes, the
worker that keeps the 380 MB parse OFF the transport's read loop, the
single-worker guard for a second command mid-build, and the failure arm.

All headless: synthetic ``apt.dat`` fixtures under ``tmp_path``, the
cache path monkeypatched away from the real data root, no network and no
X-Plane install.
"""

import os
import sys
import threading

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest  # noqa: E402

import O4_Airport_Index as AI  # noqa: E402
import O4_File_Names as FNAMES  # noqa: E402
import O4_UI_Utils as UI  # noqa: E402
from o4_engine import jsonl  # noqa: E402
from o4_engine.session import EngineSession  # noqa: E402


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
_APT_DAT = """I
1000 Generter apt.dat

1    100 0 0 XXXX Alpha Field
1302 icao_code AAAA
1302 datum_lat 48.5
1302 datum_lon -6.25

1    50 0 0 BBBB Bravo Field
100 30.0 1 0 0.25 1 3 0 09 12.5000 77.7000 0 0 0 0 0 0 27 12.5100 77.7100 0 0 0 0 0 0

16   0 0 0 SSSS Seaplane Base
101 60 1 07 59.0000 10.0000 25 58.9000 10.1000
"""

_INDEXED_AIRPORTS = 3


@pytest.fixture(autouse=True)
def reset_ui_routing():
    yield
    UI.engine_session = None
    UI.red_flag = False


@pytest.fixture
def xplane_dir(tmp_path):
    """A fake X-Plane root carrying one Global Airports apt.dat."""
    nav_data = tmp_path / "xplane" / "Global Scenery" / "Global Airports" \
        / "Earth nav data"
    os.makedirs(nav_data)
    with open(nav_data / "apt.dat", "w", encoding="utf-8") as handle:
        handle.write(_APT_DAT)
    return str(tmp_path / "xplane")


@pytest.fixture
def cache_file(tmp_path, monkeypatch):
    """Point the engine's cache path at tmp_path (never the data root)."""
    path = str(tmp_path / "cache" / ".airport_index.tsv")
    monkeypatch.setattr(FNAMES, "airport_index_cache", lambda: path)
    return path


class _EventSink:
    """Collects a session's events; waits for one by type."""

    def __init__(self, session):
        self.events = []
        self._condition = threading.Condition()
        session.subscribe(self._receive)

    def _receive(self, event):
        with self._condition:
            self.events.append(event)
            self._condition.notify_all()

    def wait_for(self, name, timeout=10.0):
        with self._condition:
            if not self._condition.wait_for(
                    lambda: any(e.event == name for e in self.events),
                    timeout):
                raise AssertionError("no %s event arrived" % name)
            return next(e for e in self.events if e.event == name)

    def count_of(self, name):
        with self._condition:
            return sum(1 for e in self.events if e.event == name)


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------
def test_registry_maps_the_airport_index_command():
    """The transport's command table reaches the session method 1:1."""
    session = EngineSession()
    handlers = jsonl._build_handlers(session)
    assert handlers["airport_index"] == session.airport_index


# ---------------------------------------------------------------------------
# Reply shapes
# ---------------------------------------------------------------------------
def test_no_xplane_folder_is_none(cache_file):
    session = EngineSession()
    assert session.airport_index() == {"status": "none"}
    assert session.airport_index(xplane_dir="") == {"status": "none"}
    assert not os.path.exists(cache_file)


def test_folder_without_apt_dat_is_none(tmp_path, cache_file):
    empty_root = str(tmp_path / "no-airports")
    os.makedirs(empty_root)
    session = EngineSession()
    assert session.airport_index(xplane_dir=empty_root) == {"status": "none"}
    assert not os.path.exists(cache_file)


def test_stale_replies_building_then_the_event_carries_the_real_count(
        xplane_dir, cache_file):
    """No cache yet: the command returns at once and the parse — which may
    be hundreds of megabytes — happens on a worker thread."""
    session = EngineSession()
    sink = _EventSink(session)

    assert session.airport_index(xplane_dir=xplane_dir) == {
        "status": "building"}
    ready = sink.wait_for("AirportIndexReady")
    assert (ready.path, ready.count, ready.error) == (
        cache_file, _INDEXED_AIRPORTS, "")
    # The event's path is a cache a front end can actually read, and its
    # count is the one recorded in the header.
    assert os.path.isfile(cache_file)
    assert AI.index_count(cache_file) == _INDEXED_AIRPORTS
    assert {e.code for e in AI.load_index(cache_file)} == {
        "AAAA", "BBBB", "SSSS"}


def test_fresh_cache_replies_ready_with_the_header_count(
        xplane_dir, cache_file):
    session = EngineSession()
    sink = _EventSink(session)
    session.airport_index(xplane_dir=xplane_dir)
    sink.wait_for("AirportIndexReady")

    # Second session, same (now fresh) cache: answered synchronously.
    session = EngineSession()
    sink = _EventSink(session)
    assert session.airport_index(xplane_dir=xplane_dir) == {
        "status": "ready", "path": cache_file, "count": _INDEXED_AIRPORTS}
    assert sink.count_of("AirportIndexReady") == 0   # nothing rebuilt


def test_the_parse_runs_off_the_command_thread(xplane_dir, cache_file,
                                               monkeypatch):
    """THE READ-LOOP HAZARD, asserted: build_index must not be called on
    the thread that issued the command."""
    command_thread = threading.current_thread()
    threads = []
    real_build_index = AI.build_index

    def _record(paths, cache):
        threads.append(threading.current_thread())
        return real_build_index(paths, cache)

    monkeypatch.setattr(AI, "build_index", _record)
    session = EngineSession()
    sink = _EventSink(session)
    session.airport_index(xplane_dir=xplane_dir)
    sink.wait_for("AirportIndexReady")
    assert threads and all(t is not command_thread for t in threads)


def test_second_command_during_a_build_joins_the_one_worker(
        xplane_dir, cache_file, monkeypatch):
    """A second airport_index while a build runs replies building without
    starting a second 380 MB parse."""
    entered = threading.Event()
    release = threading.Event()
    calls = []
    real_build_index = AI.build_index

    def _blocking(paths, cache):
        calls.append(paths)
        entered.set()
        assert release.wait(10), "the test never released the build worker"
        return real_build_index(paths, cache)

    monkeypatch.setattr(AI, "build_index", _blocking)
    session = EngineSession()
    sink = _EventSink(session)

    assert session.airport_index(xplane_dir=xplane_dir) == {
        "status": "building"}
    assert entered.wait(10), "the build worker never started"
    # Mid-build: the same answer, and NO second worker.
    assert session.airport_index(xplane_dir=xplane_dir) == {
        "status": "building"}
    release.set()

    ready = sink.wait_for("AirportIndexReady")
    assert (ready.path, ready.count) == (cache_file, _INDEXED_AIRPORTS)
    assert len(calls) == 1
    assert sink.count_of("AirportIndexReady") == 1
    # And once the flag is cleared the next command answers from the cache.
    assert session.airport_index(xplane_dir=xplane_dir)["status"] == "ready"


def test_worker_failure_reports_an_error_event(xplane_dir, cache_file,
                                               monkeypatch):
    def _explode(paths, cache):
        raise OSError("no space left on device")

    monkeypatch.setattr(AI, "build_index", _explode)
    session = EngineSession()
    sink = _EventSink(session)

    assert session.airport_index(xplane_dir=xplane_dir) == {
        "status": "building"}
    ready = sink.wait_for("AirportIndexReady")
    assert (ready.path, ready.count) == ("", 0)
    assert ready.error == "no space left on device"
    # The failure released the single-worker flag: a retry runs again.
    monkeypatch.setattr(AI, "build_index", _explode)
    assert session.airport_index(xplane_dir=xplane_dir) == {
        "status": "building"}
    for _ in range(200):
        if sink.count_of("AirportIndexReady") == 2:
            break
        threading.Event().wait(0.05)
    assert sink.count_of("AirportIndexReady") == 2
