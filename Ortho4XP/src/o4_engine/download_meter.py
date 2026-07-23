"""Process-wide download telemetry for build-time estimates.

Two signals, both fed by the actual downloaders:

* A time-decayed THROUGHPUT estimate (bytes/second), sampled by every
  network fetch that moves scenery data — imagery textures, regional
  OSM extracts.  The decay constant keeps it current: a connection that
  slows stops being priced at its old speed within about a minute.
* A registry of ACTIVE known-size downloads (foreground extract
  acquisitions register here).  ``active_remaining_seconds`` prices
  their unmoved bytes at the measured throughput, so the ETA can quote
  download time from measurement instead of treating downloads as free.

Stdlib only (the engine session imports this); every entry point is
safe to call from any thread and never raises.
"""

from __future__ import annotations

import math
import threading
from typing import Optional

# Throughput decay constant: how quickly old speed samples stop
# mattering.  20 s follows real congestion changes without thrashing on
# one slow response.
_TAU_SECONDS = 20.0
# Samples shorter than this carry more timer noise than signal.
_MIN_SAMPLE_SECONDS = 0.005

_lock = threading.Lock()
_rate_bytes_per_second: Optional[float] = None
_active: dict = {}   # key -> (received_bytes, total_bytes)


def record(byte_count: int, seconds: float) -> None:
    """Fold one completed transfer sample into the throughput estimate."""
    global _rate_bytes_per_second
    try:
        if byte_count <= 0 or seconds < _MIN_SAMPLE_SECONDS:
            return
        sample = byte_count / seconds
        with _lock:
            if _rate_bytes_per_second is None:
                _rate_bytes_per_second = sample
            else:
                alpha = 1.0 - math.exp(-seconds / _TAU_SECONDS)
                _rate_bytes_per_second += alpha * (
                    sample - _rate_bytes_per_second)
    except Exception:
        pass


def throughput_bytes_per_second() -> Optional[float]:
    """Current measured throughput, or None before any sample."""
    with _lock:
        return _rate_bytes_per_second


def begin(key: str, total_bytes: int) -> None:
    """Register an active known-size download (unknown sizes stay out —
    they cannot be priced)."""
    try:
        if total_bytes <= 0:
            return
        with _lock:
            _active[key] = (0, int(total_bytes))
    except Exception:
        pass


def update(key: str, received_bytes: int) -> None:
    try:
        with _lock:
            entry = _active.get(key)
            if entry is not None:
                _active[key] = (int(received_bytes), entry[1])
    except Exception:
        pass


def end(key: str) -> None:
    try:
        with _lock:
            _active.pop(key, None)
    except Exception:
        pass


def active_remaining_seconds() -> Optional[float]:
    """Seconds to finish every registered download at measured speed.

    None when nothing is registered or no throughput sample exists yet
    — the caller keeps its model-based estimate.
    """
    try:
        with _lock:
            if not _active or not _rate_bytes_per_second:
                return None
            remaining_bytes = sum(
                max(total - received, 0)
                for (received, total) in _active.values()
            )
            return remaining_bytes / _rate_bytes_per_second
    except Exception:
        return None


def _reset_for_tests() -> None:
    global _rate_bytes_per_second
    with _lock:
        _rate_bytes_per_second = None
        _active.clear()
