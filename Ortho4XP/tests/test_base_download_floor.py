"""A base DEM server that keeps the connection alive and trickles (#2211).

Measured on the owner's +28+086: the Viewfinderpanoramas archive ran 80+
minutes and never fell back, because ``O4_DEM_Utils.http_request`` falls
back only after six FAILED attempts and a trickle never fails.  These
twins hold the bar:

* an attempt below the throughput floor fails (``O4_Transfer_Floor``);
* two such attempts give the source up as a TRANSPORT refusal, so the
  configured fallback takes the cell, logged;
* while the configured source downloads, the slow-step alert offers
  "Use <fallback> instead" (the first covering ``fallback_rank``), and
  that answer ends the attempt and takes the fallback at once.

No network, no wall clock: the session is a fake whose body advances an
injected clock per chunk.
"""

import os
import sys

import numpy
import pytest

sys.path.insert(0, "src")

import O4_Airport_Elevation_Insets as INSETS  # noqa: E402
import O4_DEM_Utils as DEM  # noqa: E402
import O4_File_Names as FNAMES  # noqa: E402
import O4_Transfer_Floor as FLOOR  # noqa: E402
import O4_UI_Utils as UI  # noqa: E402
from elevation_access import base_fallback, fallback_choice  # noqa: E402
from elevation_access import registry as ea_registry  # noqa: E402
from o4_engine import slow_step, task_meter  # noqa: E402

URL = "https://slow.invalid/dem3/G45.zip"
CELL = (28, 86)


class _Clock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


# ------------------------------------------------------------ the floor
def _feed(floor, clock, rate, seconds, step=1.0, received=0):
    """``rate`` bytes/s for ``seconds``, one chunk per ``step``."""
    floor.started(0)
    for _ in range(int(seconds / step)):
        clock.now += step
        received += int(rate * step)
        floor.chunk(int(rate * step), received, 0)
    return received


def test_a_transfer_above_the_floor_never_fails():
    clock = _Clock()
    floor = FLOOR.ThroughputFloor(clock=clock)
    _feed(floor, clock, 2 * FLOOR.FLOOR_BYTES_PER_SECOND, 600)


def test_a_trickle_fails_after_one_window_not_before():
    clock = _Clock()
    floor = FLOOR.ThroughputFloor(clock=clock)
    rate = FLOOR.FLOOR_BYTES_PER_SECOND / 10
    _feed(floor, clock, rate, FLOOR.FLOOR_WINDOW_SECONDS - 1)
    with pytest.raises(FLOOR.TransferTooSlow, match="below the 100 KB/s"):
        clock.now += 1.0
        floor.chunk(1, 1, 0)


def test_a_fast_start_that_then_trickles_still_fails():
    clock = _Clock()
    floor = FLOOR.ThroughputFloor(clock=clock)
    received = _feed(floor, clock, 10 * FLOOR.FLOOR_BYTES_PER_SECOND,
                     FLOOR.FLOOR_WINDOW_SECONDS)
    with pytest.raises(FLOOR.TransferTooSlow):
        for _ in range(int(FLOOR.FLOOR_WINDOW_SECONDS) + 1):
            clock.now += 1.0
            received += 10
            floor.chunk(10, received, 0)


def test_abandoned_ends_the_transfer_at_the_next_chunk():
    answer = [False]
    floor = FLOOR.ThroughputFloor(clock=_Clock(), abandoned=lambda: answer[0])
    floor.started(0)
    floor.chunk(1, 1, 0)
    answer[0] = True
    with pytest.raises(FLOOR.TransferAbandoned):
        floor.chunk(1, 2, 0)


# ----------------------------------------------------------- the transport
class _Trickle:
    """A 200 whose body moves ``rate`` bytes/s on the injected clock;
    ``on_chunk`` (optional) runs before each chunk."""

    def __init__(self, clock, rate, chunks, on_chunk=None):
        self.status_code = 200
        self.headers = {}
        self._clock, self._rate, self._chunks = clock, rate, chunks
        self._on_chunk = on_chunk

    def iter_content(self, size):
        assert size == FLOOR.FLOOR_CHUNK_BYTES
        for _ in range(self._chunks):
            if self._on_chunk is not None:
                self._on_chunk()
            self._clock.now += size / self._rate
            yield b"x" * size

    def close(self):
        pass


class _Session:
    def __init__(self, answer):
        self.answer, self.calls = answer, 0

    def get(self, url, timeout=None, allow_redirects=True, stream=False):
        self.calls += 1
        return self.answer()


@pytest.fixture
def transport(monkeypatch):
    clock = _Clock()
    monkeypatch.setattr(DEM, "HTTP_REQUEST_CLOCK", clock)
    monkeypatch.setattr(DEM.PUSHBACK, "interruptible_sleep", lambda s: True)
    monkeypatch.setattr(UI, "red_flag", False)
    task_meter._reset_for_tests()
    yield clock
    task_meter._reset_for_tests()


def _serve(monkeypatch, answer):
    session = _Session(answer)
    monkeypatch.setattr(DEM.requests, "Session", lambda: session)
    return session


def test_two_trickling_attempts_give_the_source_up_on_the_transport(
        transport, monkeypatch, tmp_path):
    session = _serve(monkeypatch, lambda: _Trickle(transport, 1024, 10 ** 6))
    with pytest.raises(DEM.ElevationTransportRefused) as caught:
        DEM.http_request(URL, "View", destination=str(tmp_path / "a.zip"))
    assert session.calls == DEM.HTTP_REQUEST_SLOW_ATTEMPT_CAP == 2
    assert "too slow" in str(caught.value)
    # One window per attempt plus a chunk: minutes, never hours.
    assert transport.now < 2 * (FLOOR.FLOOR_WINDOW_SECONDS
                                + FLOOR.FLOOR_CHUNK_BYTES / 1024)


def test_a_body_above_the_floor_is_kept(transport, monkeypatch, tmp_path):
    rate = 4 * FLOOR.FLOOR_BYTES_PER_SECOND
    _serve(monkeypatch, lambda: _Trickle(transport, rate, 2000))
    path = tmp_path / "a.zip"
    assert DEM.http_request(URL, "View", destination=str(path))
    assert path.stat().st_size == 2000 * FLOOR.FLOOR_CHUNK_BYTES


def test_the_users_choice_ends_the_attempt_at_once(transport, monkeypatch,
                                                   tmp_path):
    key = fallback_choice.phase_key("slow.invalid")
    chunks = []

    def _answer_on_the_third_chunk():
        chunks.append(1)
        if len(chunks) == 3:
            assert task_meter.request_coarser(key)

    session = _serve(monkeypatch, lambda: _Trickle(
        transport, 1024, 10 ** 6, _answer_on_the_third_chunk))
    with fallback_choice.download_phase("slow.invalid", "Viewfinder",
                                        "+28+086", "FABDEM"):
        with pytest.raises(DEM.ElevationTransportRefused,
                           match="chose the fallback source instead"):
            DEM.http_request(URL, "View", destination=str(tmp_path / "a"))
    assert session.calls == 1 and len(chunks) == 3   # that very chunk
    assert not task_meter.coarser_requested(key)       # the phase ended


# ------------------------------------------------- the alert and the cell
class _Configured:
    """A configured base source served by the fake transport."""

    def covers(self, definition, lat, lon):
        return True

    def download_url(self, definition, lat, lon):
        return URL

    def tile_cache_path(self, definition, lat, lon):
        return FNAMES.elevation_data("View", lat, lon)

    def ensure_tile(self, definition, lat, lon, verbose=True):
        path = self.tile_cache_path(definition, lat, lon)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        return int(bool(DEM.http_request(URL, "View", verbose,
                                         destination=path + ".part")))


class _Spare:
    calls = []

    def covers(self, definition, lat, lon):
        return True

    def tile_cache_path(self, definition, lat, lon):
        return "%s_%s.hgt" % (FNAMES.base_file_name(lat, lon),
                              definition["code"])

    def ensure_tile(self, definition, lat, lon, verbose=True):
        path = self.tile_cache_path(definition, lat, lon)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        numpy.full((5, 5), 200, dtype=">i2").tofile(path)
        _Spare.calls.append(definition["code"])
        return 1


CONFIGURED = {"code": "VIEW", "role": "base", "access_strategy": "_slow",
              "display_name": "Viewfinder"}


@pytest.fixture
def world(transport, tmp_path, monkeypatch):
    monkeypatch.setattr(FNAMES, "Elevation_dir", str(tmp_path))
    monkeypatch.setitem(ea_registry.ACCESS_STRATEGIES, "_slow", _Configured)
    monkeypatch.setitem(ea_registry.ACCESS_STRATEGIES, "_spare", _Spare)
    providers = {
        "VIEW": CONFIGURED,
        "FABDEM": {"code": "FABDEM", "role": "base", "fallback_rank": "1",
                   "access_strategy": "_spare", "display_name": "FABDEM"},
    }
    monkeypatch.setattr(INSETS, "elevation_providers_dict", providers)
    _Spare.calls = []
    base_fallback.forget_unreachable_sources()
    yield providers
    base_fallback.forget_unreachable_sources()


def _ensure(providers):
    return base_fallback.ensure_tile_or_fallback(
        _Configured(), CONFIGURED, CELL[0], CELL[1], False, providers)


def test_a_trickling_source_hands_the_cell_to_fabdem_logged(
        world, monkeypatch, capsys):
    _serve(monkeypatch, lambda: _Trickle(DEM.HTTP_REQUEST_CLOCK,
                                         1024, 10 ** 6))
    assert _ensure(world) == 1
    assert _Spare.calls == ["FABDEM"]
    said = capsys.readouterr().out
    assert "elevation cell +28+086 taken from FABDEM instead" in said
    assert "too slow" in said


def test_the_alert_offers_the_fallback_and_its_answer_takes_it(
        world, monkeypatch):
    sent = []
    watch = slow_step.SlowStepWatch(sent.append)
    monkeypatch.setattr(slow_step.FLOCK, "lock_waits", lambda: [])
    monkeypatch.setattr(slow_step, "_disk_paths", lambda: ())
    monkeypatch.setattr(slow_step.download_meter, "watch_transfers",
                        lambda: True)
    # The download crawls (rule 1); the alert names the phase's answer.
    monkeypatch.setattr(slow_step.download_meter, "activity", lambda: {
        "in_flight": 1, "busy_since": 0.0, "bytes": 0, "requests": 0,
        "last_progress": 0.0, "hosts": {}})
    watch.begin(CELL, "mesh", "mesh", enabled=True, now=0.0)
    seen = []

    def _user_answers_once():
        if not seen:
            event = watch.poll(now=slow_step.STALL_SECONDS)
            seen.append(event)
            assert watch.choose(CELL, "coarser")

    _serve(monkeypatch, lambda: _Trickle(DEM.HTTP_REQUEST_CLOCK, 1024,
                                         10 ** 6, _user_answers_once))
    assert _ensure(world) == 1
    event = seen[0]
    assert event.reason == "download_stalled"
    assert event.options == ("continue", "coarser", "cancel")
    assert event.option_labels == ("Continue", "Use FABDEM instead",
                                   "Cancel this tile")
    assert _Spare.calls == ["FABDEM"]
    # Within one attempt: the user's answer, never the floor's verdict.
    assert DEM.HTTP_REQUEST_CLOCK.now < FLOOR.FLOOR_WINDOW_SECONDS
