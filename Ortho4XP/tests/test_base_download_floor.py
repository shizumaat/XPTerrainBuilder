"""A base DEM server that keeps the connection alive and trickles (#2211).

Measured on the owner's +28+086: the Viewfinderpanoramas archive ran 80+
minutes and never fell back, because ``O4_DEM_Utils.http_request`` falls
back only after six FAILED attempts and a trickle never fails.  The
owner's ruling (2026-11-24): "The floor seems fine, but ask the user if
they want to wait or fallback."  These twins hold that bar:

* the throughput floor (``O4_Transfer_Floor``) DETECTS a body below
  100 KB/s over 60 s and never fails the transfer;
* below the floor the base download's phase is flagged, so the
  slow-step alert asks AT ONCE (before its own thresholds) with
  Continue / "Use <fallback> instead" / Cancel this tile, while the
  body keeps streaming;
* "Use FABDEM instead" ends the attempt and takes the fallback;
  "Continue" waits for the configured source;
* with nobody to answer, the download waits as before, logged once.

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


def _floor(clock, **kw):
    verdicts = []
    floor = FLOOR.ThroughputFloor(
        clock=clock, report=lambda below, detail: verdicts.append(
            (below, detail)), **kw)
    return floor, verdicts


def test_a_transfer_above_the_floor_is_never_reported_below():
    clock = _Clock()
    floor, verdicts = _floor(clock)
    _feed(floor, clock, 2 * FLOOR.FLOOR_BYTES_PER_SECOND, 600)
    assert verdicts and not any(below for below, _ in verdicts)


def test_a_trickle_is_reported_after_one_window_and_never_raises():
    clock = _Clock()
    floor, verdicts = _floor(clock)
    rate = FLOOR.FLOOR_BYTES_PER_SECOND / 10
    _feed(floor, clock, rate, FLOOR.FLOOR_WINDOW_SECONDS - 1)
    assert verdicts == []
    clock.now += 1.0
    floor.chunk(1, 1, 0)
    assert verdicts[0][0] and "the floor is 100 KB/s" in verdicts[0][1]
    # The floor only detects: the transfer goes on, window after window.
    _feed(floor, clock, rate, 10 * FLOOR.FLOOR_WINDOW_SECONDS)
    assert len(verdicts) > 5 and all(below for below, _ in verdicts)


def test_a_fast_start_that_then_trickles_is_reported():
    clock = _Clock()
    floor, verdicts = _floor(clock)
    received = _feed(floor, clock, 10 * FLOOR.FLOOR_BYTES_PER_SECOND,
                     FLOOR.FLOOR_WINDOW_SECONDS)
    for _ in range(int(FLOOR.FLOOR_WINDOW_SECONDS) + 1):
        clock.now += 1.0
        received += 10
        floor.chunk(10, received, 0)
    assert [below for below, _ in verdicts] == [False, True]


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


def test_a_trickle_is_never_refused_it_downloads_to_the_end_logged_once(
        transport, monkeypatch, tmp_path, capsys):
    chunks = 40      # 16 s each at 1 KB/s: ten windows below the floor
    session = _serve(monkeypatch, lambda: _Trickle(transport, 1024, chunks))
    path = tmp_path / "a.zip"
    assert DEM.http_request(URL, "View", destination=str(path))
    assert session.calls == 1
    assert path.stat().st_size == chunks * FLOOR.FLOOR_CHUNK_BYTES
    said = capsys.readouterr().out
    assert said.count("below the speed floor") == 1
    assert "still downloading" in said


def test_below_the_floor_flags_the_phase_and_the_flag_comes_down(
        transport, monkeypatch, tmp_path):
    seen = []
    session = _serve(monkeypatch, lambda: _Trickle(
        transport, 1024, 12,
        lambda: seen.append(task_meter.flagged_phase())))
    with fallback_choice.download_phase("slow.invalid", "Viewfinder",
                                        "+28+086", "FABDEM"):
        assert DEM.http_request(URL, "View", destination=str(tmp_path / "a"))
        assert task_meter.flagged_phase() is None   # the attempt ended
    assert session.calls == 1
    flagged = [f for f in seen if f]
    assert seen[0] is None and flagged     # after one window, not before
    assert flagged[0]["key"] == fallback_choice.phase_key("slow.invalid")
    assert "below the speed floor" in flagged[0]["what"]
    assert flagged[0]["coarser_label"] == "Use FABDEM instead"


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


def test_headless_a_trickling_source_keeps_the_cell_and_waits(
        world, monkeypatch, capsys):
    """Nobody to answer: the configured source keeps the cell."""
    _serve(monkeypatch, lambda: _Trickle(DEM.HTTP_REQUEST_CLOCK, 1024, 40))
    assert _ensure(world) == 1
    assert _Spare.calls == []
    said = capsys.readouterr().out
    assert said.count("below the speed floor") == 1
    assert "FABDEM" not in said


def _watch(monkeypatch):
    """A slow-step watch whose own thresholds never fire: only the
    phase's flag can raise the alert."""
    sent = []
    watch = slow_step.SlowStepWatch(sent.append)
    monkeypatch.setattr(slow_step.FLOCK, "lock_waits", lambda: [])
    monkeypatch.setattr(slow_step, "_disk_paths", lambda: ())
    monkeypatch.setattr(slow_step.download_meter, "watch_transfers",
                        lambda: True)
    monkeypatch.setattr(slow_step.download_meter, "activity", lambda: {
        "in_flight": 0, "busy_since": None, "bytes": 0, "requests": 0,
        "last_progress": None, "hosts": {}})
    watch.begin(CELL, "mesh", "mesh", enabled=True, now=0.0)
    return watch, sent


def _user_answers(watch, choice, polls):
    """Poll the watch before every chunk (1 s apart on the watch's own
    clock, far below every threshold); answer ``choice`` on the first
    alert."""
    def on_chunk():
        event = watch.poll(now=float(len(polls) + 1))
        polls.append(event)
        if event is not None and not event.resolved and choice:
            assert watch.choose(CELL, choice)
    return on_chunk


def test_below_the_floor_raises_the_alert_at_once_and_fabdem_takes_it(
        world, monkeypatch):
    (watch, sent) = _watch(monkeypatch)
    polls = []
    _serve(monkeypatch, lambda: _Trickle(DEM.HTTP_REQUEST_CLOCK, 1024,
                                         10 ** 6,
                                         _user_answers(watch, "coarser",
                                                       polls)))
    assert _ensure(world) == 1
    alerts = [e for e in polls if e is not None]
    event = alerts[0]
    assert event.reason == "phase_flagged"
    assert "below the speed floor" in event.message
    assert event.options == ("continue", "coarser", "cancel")
    assert event.option_labels == ("Continue", "Use FABDEM instead",
                                   "Cancel this tile")
    assert _Spare.calls == ["FABDEM"]
    # Right after the first window, on the user's answer -- no refusal.
    assert len(polls) <= FLOOR.FLOOR_WINDOW_SECONDS / 16 + 2


def test_continue_waits_and_the_configured_source_finishes(world,
                                                           monkeypatch):
    (watch, sent) = _watch(monkeypatch)
    polls = []
    _serve(monkeypatch, lambda: _Trickle(DEM.HTTP_REQUEST_CLOCK, 1024, 40,
                                         _user_answers(watch, "continue",
                                                       polls)))
    assert _ensure(world) == 1
    alerts = [e for e in polls if e is not None]
    assert len(alerts) == 1 and alerts[0].reason == "phase_flagged"
    assert _Spare.calls == []
    assert len(polls) == 40             # every chunk arrived


def test_the_alert_closes_when_the_download_recovers(transport,
                                                    monkeypatch):
    (watch, sent) = _watch(monkeypatch)
    with fallback_choice.download_phase("slow.invalid", "Viewfinder",
                                        "+28+086", "FABDEM"):
        fallback_choice.report_floor(URL, "View", True, "1.0 KB/s")
        assert watch.poll(now=1.0).reason == "phase_flagged"
        fallback_choice.report_floor(URL, "View", False)
        assert watch.poll(now=2.0) is None
    assert sent[-1].resolved
