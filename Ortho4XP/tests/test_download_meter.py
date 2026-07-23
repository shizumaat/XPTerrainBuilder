"""Download meter: throughput EWMA + active-download pricing, and its
integration into the session ETA (headless, no network)."""

import sys
import time

import pytest

sys.path.insert(0, "src")

from o4_engine import download_meter, session


@pytest.fixture(autouse=True)
def _clean_meter():
    download_meter._reset_for_tests()
    yield
    download_meter._reset_for_tests()


def test_throughput_from_samples():
    assert download_meter.throughput_bytes_per_second() is None
    download_meter.record(10 << 20, 1.0)
    rate = download_meter.throughput_bytes_per_second()
    assert rate == pytest.approx(10 << 20)
    # A slower sample pulls the estimate down, but not all the way
    # (time-decayed blend, not replacement).
    download_meter.record(1 << 20, 1.0)
    blended = download_meter.throughput_bytes_per_second()
    assert (1 << 20) < blended < (10 << 20)


def test_noise_samples_ignored():
    download_meter.record(0, 1.0)
    download_meter.record(1024, 0.0001)   # sub-timer-resolution
    assert download_meter.throughput_bytes_per_second() is None


def test_active_remaining_prices_unmoved_bytes():
    # Nothing registered / no throughput yet -> no estimate.
    assert download_meter.active_remaining_seconds() is None
    download_meter.begin("extract:egypt", 100 << 20)
    assert download_meter.active_remaining_seconds() is None
    download_meter.record(10 << 20, 1.0)   # 10 MB/s
    download_meter.update("extract:egypt", 40 << 20)
    remaining = download_meter.active_remaining_seconds()
    assert remaining == pytest.approx(6.0, rel=0.01)
    download_meter.end("extract:egypt")
    assert download_meter.active_remaining_seconds() is None


def test_unknown_size_downloads_are_not_registered():
    download_meter.begin("extract:mystery", 0)
    download_meter.record(1 << 20, 1.0)
    assert download_meter.active_remaining_seconds() is None


def test_active_download_floors_current_step_remaining():
    tracker = session._EtaTracker(
        [(0, 0)], [("vector", 0.0, 1.0)], {(0, 0): {"vector": 1.0}})
    tracker.step_key = "vector"
    tracker.step_started_at = time.time()
    # Model alone: ~1 s step estimate.
    assert tracker._current_step_remaining() < 5.0
    # A 100 MB extract at 10 MB/s with nothing received floors it at ~10 s.
    download_meter.record(10 << 20, 1.0)
    download_meter.begin("extract:egypt", 100 << 20)
    assert tracker._current_step_remaining() >= 9.0
    download_meter.end("extract:egypt")
    assert tracker._current_step_remaining() < 5.0
