"""The two newly-metered network paths feed the process-wide download
throughput meter (``o4_engine.download_meter``).

Both paths were previously invisible to the build-time estimator:

* Overpass queries in ``O4_OSM_Utils.get_overpass_data`` (the POST runs
  on a helper thread while the caller polls).
* Coastal bathymetry cell fetches in ``O4_Bathymetry_Band`` (shared by
  the foreground fan-out and the background prefetch through
  ``_fetch_cell`` -> ``_record_cell_download``).

Fully headless, no network: the HTTP session / provider fetch is
monkeypatched (or a real temp file is measured directly), so each case
asserts ``throughput_bytes_per_second()`` becomes non-None and plausible.
Runs under ``-n0``.
"""

import time

import pytest

import O4_OSM_Utils as OSM
import O4_Bathymetry_Band as BATHYBAND
from o4_engine import download_meter


@pytest.fixture(autouse=True)
def _clean_meter():
    download_meter._reset_for_tests()
    yield
    download_meter._reset_for_tests()


# --- Overpass query path --------------------------------------------------

_CANNED_OSM = b"<osm>" + b"x" * 200_000 + b"</osm>"
_POST_SLEEP_SECONDS = 0.05


class _FakeResponse:
    """Minimal stand-in for a requests.Response the success path uses."""

    def __init__(self, content):
        self.content = content
        self.status_code = 200
        self.headers = {}


class _FakeSession:
    def post(self, url, data=None, timeout=None):
        # Emulate a transfer of measurable duration so the meter sees a
        # plausible (non-noise) sample.
        time.sleep(_POST_SLEEP_SECONDS)
        return _FakeResponse(_CANNED_OSM)


def test_overpass_query_feeds_the_meter(monkeypatch):
    monkeypatch.setattr(
        OSM, "overpass_servers",
        {"test": "https://overpass.example/api/interpreter"},
    )
    # Pin the single synthetic server so no status endpoint is probed.
    monkeypatch.setattr(OSM, "overpass_server_choice", "test")
    monkeypatch.setattr(OSM, "_get_http_session", lambda: _FakeSession())

    assert download_meter.throughput_bytes_per_second() is None

    result = OSM.get_overpass_data(
        'way["highway"="motorway"]', "(50.0,8.0,51.0,9.0)"
    )
    # Behaviour preserved: the raw XML answer still comes back verbatim.
    assert result == _CANNED_OSM

    rate = download_meter.throughput_bytes_per_second()
    assert rate is not None
    # The meter saw the whole body over roughly the sleep time; the
    # measured duration is at least the sleep, so the rate never exceeds
    # body/sleep and stays well above zero.
    assert 0 < rate <= len(_CANNED_OSM) / _POST_SLEEP_SECONDS * 1.001
    assert rate == pytest.approx(
        len(_CANNED_OSM) / _POST_SLEEP_SECONDS, rel=0.9
    )


# --- Bathymetry cell fetch path -------------------------------------------

def test_bathymetry_cell_fetch_feeds_the_meter(tmp_path):
    # _record_cell_download is the smallest callable unit wrapping the
    # meter feed for the shared _fetch_cell (foreground + prefetch).  A
    # real payload on disk stands in for a completed provider transfer.
    payload = tmp_path / "cell.part.tif"
    payload_bytes = 128 << 10   # 128 KiB
    payload.write_bytes(b"\0" * payload_bytes)
    fetch_seconds = 0.25

    assert download_meter.throughput_bytes_per_second() is None

    BATHYBAND._record_cell_download(str(payload), fetch_seconds)

    rate = download_meter.throughput_bytes_per_second()
    assert rate is not None
    assert rate == pytest.approx(payload_bytes / fetch_seconds, rel=0.001)


def test_bathymetry_meter_hook_never_raises_on_missing_file(tmp_path):
    # Telemetry must be inert, never fatal: a vanished temp file (or any
    # meter hiccup) is swallowed and leaves the estimate untouched.
    BATHYBAND._record_cell_download(str(tmp_path / "gone.tif"), 0.1)
    assert download_meter.throughput_bytes_per_second() is None
