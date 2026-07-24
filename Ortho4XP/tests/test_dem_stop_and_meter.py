"""O4_DEM_Utils download telemetry + cancellation (headless, no network).

Two behaviours the module gained:

* Every successful ``http_request`` fetch folds one sample into the
  process-wide throughput meter (``o4_engine.download_meter``) so the
  build-time ETA can price elevation downloads from measurement.
* ``UI.red_flag`` (the polled Stop flag) aborts the multi-attempt retry
  loop and the multi-tile base raster assembly promptly, using each
  path's existing failure convention (``http_request`` returns a falsy
  0; ``build_combined_raster`` returns its partial 9-tuple).

The requests session is monkeypatched so nothing touches the network.
"""

import sys

import numpy
import pytest

sys.path.insert(0, "src")

import O4_DEM_Utils as DEM
import O4_UI_Utils as UI
from o4_engine import download_meter


class _FakeResponse:
    """Enough of a requests.Response for http_request's ``str(r)`` status
    sniffing and ``r.content`` body read."""

    def __init__(self, status, content=b""):
        self._status = status
        self.content = content

    def __repr__(self):
        return "<Response [%d]>" % self._status


class _FakeSession:
    """Stand-in for ``requests.Session`` whose ``get`` is fully scripted."""

    def __init__(self, get_impl):
        self._get_impl = get_impl
        self.calls = 0

    def get(self, url, timeout=None):
        self.calls += 1
        return self._get_impl(url)


@pytest.fixture(autouse=True)
def _clean_state():
    UI.red_flag = False
    download_meter._reset_for_tests()
    yield
    UI.red_flag = False
    download_meter._reset_for_tests()


def _install_session(monkeypatch, get_impl):
    session = _FakeSession(get_impl)
    monkeypatch.setattr(DEM.requests, "Session", lambda: session)
    return session


def test_successful_fetch_feeds_the_throughput_meter(monkeypatch):
    # Pin the elapsed measurement so the recorded sample is deterministic:
    # http_request reads time.time() once before and once after get().
    times = iter([1000.0, 1000.5])
    monkeypatch.setattr(DEM.time, "time", lambda: next(times, 1000.5))
    body = b"x" * (5 * 1024 * 1024)  # 5 MiB in 0.5 s -> 10 MiB/s
    session = _install_session(
        monkeypatch, lambda url: _FakeResponse(200, body)
    )

    assert download_meter.throughput_bytes_per_second() is None
    result = DEM.http_request("http://example.test/tile.zip", "View")

    assert isinstance(result, _FakeResponse)
    assert session.calls == 1
    rate = download_meter.throughput_bytes_per_second()
    assert rate == pytest.approx((5 * 1024 * 1024) / 0.5)  # 10 MiB/s
    assert rate > 0


def test_redflag_aborts_before_first_request(monkeypatch):
    UI.red_flag = True

    def _boom(url):
        raise AssertionError("no network request may fire once Stop is set")

    session = _install_session(monkeypatch, _boom)
    result = DEM.http_request("http://example.test/tile.zip", "View")

    assert result == 0
    assert session.calls == 0
    # Nothing fetched -> no telemetry sample.
    assert download_meter.throughput_bytes_per_second() is None


def test_redflag_aborts_retry_loop_before_backoff_sleep(monkeypatch):
    # A 5xx would normally retry with an exponential back-off sleep.  If
    # Stop is pressed mid-flight, the loop must bail before sleeping.
    slept = []
    monkeypatch.setattr(DEM.time, "sleep", lambda s: slept.append(s))

    def _server_error_then_stop(url):
        UI.red_flag = True  # user hits Stop while this attempt is in flight
        return _FakeResponse(503)

    session = _install_session(monkeypatch, _server_error_then_stop)
    result = DEM.http_request("http://example.test/tile.zip", "View")

    assert result == 0
    assert session.calls == 1        # only the first attempt ran
    assert slept == []               # never entered the back-off sleep


def test_redflag_aborts_base_tile_assembly(monkeypatch):
    # build_combined_raster loops over 9 neighbour tiles, each of which
    # may download via ensure_elevation.  With Stop set it must break at
    # the first iteration and return its (all-zero) partial raster.
    calls = []
    monkeypatch.setattr(
        DEM, "ensure_elevation",
        lambda *a, **k: calls.append(a) or 1,
    )
    UI.red_flag = True

    (epsg, x0, y0, x1, y1, nodata, nxdem, nydem, alt_dem) = (
        DEM.build_combined_raster("View", 46, 6, False)
    )

    assert calls == []                       # no download attempted
    assert alt_dem.shape == (nydem, nxdem)
    assert isinstance(alt_dem, numpy.ndarray)
    assert (alt_dem == 0).all()              # nothing was filled in
