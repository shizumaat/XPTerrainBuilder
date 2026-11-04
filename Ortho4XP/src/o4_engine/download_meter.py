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

And one record for the stuck-step alert (#1351, :mod:`o4_engine.
slow_step`): the ACTIVITY of this process's transfers -- how many are in
flight and since when, the bytes and completed requests moved so far,
when data last arrived, and each server's answers (served / refused).
:func:`watch_transfers` feeds it from every ``requests`` transfer (one
hook on ``Session.send`` and on urllib3's body reads, so no download
helper has to opt in); :func:`record`, :func:`begin`, :func:`update`
and :func:`end` feed it from the helpers that already report here.

Stdlib only (the engine session imports this); every entry point is
safe to call from any thread and never raises.
"""

from __future__ import annotations

import math
import threading
import time
from typing import Optional
from urllib.parse import urlsplit

# Throughput decay constant: how quickly old speed samples stop
# mattering.  20 s follows real congestion changes without thrashing on
# one slow response.
_TAU_SECONDS = 20.0
# Samples shorter than this carry more timer noise than signal.
_MIN_SAMPLE_SECONDS = 0.005

_lock = threading.Lock()
_rate_bytes_per_second: Optional[float] = None
_active: dict = {}   # key -> (received_bytes, total_bytes)
# The transfer activity (#1351): see :func:`activity`.
_in_flight = 0
_busy_since: Optional[float] = None
_bytes_moved = 0
_requests_done = 0
_last_progress: Optional[float] = None
_hosts: dict = {}    # host -> [served, refused]
_watching = False


def record(byte_count: int, seconds: float) -> None:
    """Fold one completed transfer sample into the throughput estimate."""
    global _rate_bytes_per_second
    try:
        _progressed(0, request=True)
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
            fresh = key not in _active
            _active[key] = (0, int(total_bytes))
        if fresh:
            _opened()
    except Exception:
        pass


def update(key: str, received_bytes: int) -> None:
    try:
        with _lock:
            entry = _active.get(key)
            if entry is not None:
                _active[key] = (int(received_bytes), entry[1])
        if entry is not None and int(received_bytes) > entry[0]:
            _progressed(int(received_bytes) - entry[0])
    except Exception:
        pass


def end(key: str) -> None:
    try:
        with _lock:
            entry = _active.pop(key, None)
        if entry is not None:
            _closed("", None)
    except Exception:
        pass


# ---------------------------------------------------------------------
# Transfer activity (#1351): is a download moving, or stuck?
# ---------------------------------------------------------------------
def _progressed(byte_count: int, request: bool = False) -> None:
    """Data arrived: ``byte_count`` bytes, or one completed request."""
    global _bytes_moved, _requests_done, _last_progress
    with _lock:
        _bytes_moved += max(int(byte_count), 0)
        _requests_done += 1 if request else 0
        if byte_count > 0 or request:
            _last_progress = time.time()


def _opened() -> None:
    global _in_flight, _busy_since
    with _lock:
        if _in_flight <= 0:
            _in_flight, _busy_since = 0, time.time()
        _in_flight += 1


def _closed(host: str, served: Optional[bool]) -> None:
    """One transfer ended: ``served`` True (the server sent the data),
    False (it refused or failed), None (no verdict: a 404, a 3xx)."""
    global _in_flight, _busy_since
    with _lock:
        _in_flight = max(_in_flight - 1, 0)
        if not _in_flight:
            _busy_since = None
        if host and served is not None:
            _hosts.setdefault(host, [0, 0])[0 if served else 1] += 1
    if served:
        _progressed(0, request=True)


def _served(status_code) -> Optional[bool]:
    """A status's verdict for :func:`_closed`: 2xx served; 404 / 410
    (the server answered "not here") and 3xx no verdict; any other
    status a refusal or failure."""
    try:
        code = int(status_code)
    except (TypeError, ValueError):
        return None
    if 200 <= code < 300:
        return True
    if code < 400 or code in (404, 410):
        return None
    return False


def activity() -> dict:
    """The transfer activity now: ``{"in_flight", "busy_since", "bytes",
    "requests", "last_progress", "hosts"}`` -- ``busy_since`` when the
    current unbroken stretch of in-flight transfers began (``None`` when
    nothing is in flight), ``hosts`` ``{host: (served, refused)}``."""
    with _lock:
        return {"in_flight": _in_flight, "busy_since": _busy_since,
                "bytes": _bytes_moved, "requests": _requests_done,
                "last_progress": _last_progress,
                "hosts": {h: tuple(c) for (h, c) in _hosts.items()}}


def watch_transfers() -> bool:
    """Feed :func:`activity` from every ``requests`` transfer of this
    process (once; idempotent).  Wraps ``requests.Session.send`` (in
    flight, the server's verdict) and urllib3's body reads (bytes as
    they arrive, streamed or not); a wrapper never changes what the
    transfer returns or raises.  False when ``requests`` is absent."""
    global _watching
    with _lock:
        if _watching:
            return True
        _watching = True
    try:
        import sys

        import requests
        # urllib3's response class: loaded by requests itself (it is
        # requests' transport, not a library of its own here).
        HTTPResponse = sys.modules["urllib3.response"].HTTPResponse
    except Exception:
        return False
    send = requests.Session.send
    read = HTTPResponse.read
    read_chunked = HTTPResponse.read_chunked

    def metered_send(self, request, **kwargs):
        try:
            host = urlsplit(request.url).hostname or ""
        except Exception:
            host = ""
        _opened()
        served = False
        try:
            response = send(self, request, **kwargs)
            served = _served(getattr(response, "status_code", None))
            return response
        finally:
            _closed(host, served)

    def metered_read(self, *args, **kwargs):
        data = read(self, *args, **kwargs)
        if data:
            _progressed(len(data))
        return data

    def metered_read_chunked(self, *args, **kwargs):
        for chunk in read_chunked(self, *args, **kwargs):
            if chunk:
                _progressed(len(chunk))
            yield chunk

    requests.Session.send = metered_send
    HTTPResponse.read = metered_read
    HTTPResponse.read_chunked = metered_read_chunked
    return True


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
    global _rate_bytes_per_second, _in_flight, _busy_since, _bytes_moved
    global _requests_done, _last_progress
    with _lock:
        _rate_bytes_per_second = None
        _active.clear()
        _in_flight, _busy_since, _bytes_moved = 0, None, 0
        _requests_done, _last_progress = 0, None
        _hosts.clear()
