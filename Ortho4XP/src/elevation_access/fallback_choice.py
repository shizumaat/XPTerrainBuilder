"""The base download's slow-step phase and its "Use <fallback> instead".

While a configured base source downloads a cell, the download is a
counted phase of :mod:`o4_engine.task_meter` keyed by the source's HOST
(:func:`download_phase`).  It declares the slow-step alert's "coarser"
answer (#1351) with its own button words, ``"Use FABDEM instead"`` --
the first ``fallback_rank`` source that covers the cell (issue #2211).
The user's answer is :func:`o4_engine.task_meter.request_coarser` on
that key; :func:`fallback_requested` is what ``O4_DEM_Utils.
http_request`` asks between chunks and before each attempt, and a true
answer ends the attempt as a transport refusal, which
``elevation_access.base_fallback`` covers with the fallback (and
remembers the host, so the other stuck cells of the run skip it too).

Telemetry never breaks a download: a missing engine (the frozen CLI
without ``o4_engine``) leaves the phase out and every answer false.
"""

import contextlib
import threading
from urllib.parse import urlparse

__all__ = ["PHASE_PREFIX", "download_phase", "fallback_requested",
           "phase_key"]

#: The task-meter key of a host's base download is this plus the host.
PHASE_PREFIX = "base_elevation_download:"

# phase key -> cells of this process downloading from that host now: the
# phase begins with the first and ends with the last, so two cells in
# flight share one answer.
_holders = {}
_lock = threading.Lock()


def _task_meter():
    try:
        from o4_engine import task_meter
    except Exception:
        return None
    return task_meter


def phase_key(host):
    """The task-meter key of ``host``'s base download."""
    return PHASE_PREFIX + str(host or "")


def fallback_requested(url):
    """Whether the user chose the fallback for ``url``'s host."""
    meter = _task_meter()
    if meter is None:
        return False
    try:
        host = urlparse(url).hostname or ""
    except Exception:
        return False
    return bool(meter.coarser_requested(phase_key(host)))


@contextlib.contextmanager
def download_phase(host, source_label, cell, fallback_label=None):
    """The configured source's download of ``cell`` from ``host``, as a
    slow-step phase; ``fallback_label`` (the first covering fallback's
    name, or ``None``) offers "Use <it> instead"."""
    meter = _task_meter()
    key = phase_key(host)
    if meter is not None:
        with _lock:
            _holders[key] = _holders.get(key, 0) + 1
            first = _holders[key] == 1
        if first:
            meter.begin(
                key, 1,
                what="Downloading the base elevation of cell %s from %s"
                     % (cell, source_label),
                why="It is one whole-cell file from %s's server" % (
                    source_label,),
                reason="remote_base_elevation",
                coarser=bool(fallback_label),
                coarser_label=("Use %s instead" % fallback_label
                               if fallback_label else ""))
    try:
        yield
    finally:
        if meter is not None:
            with _lock:
                _holders[key] -= 1
                last = _holders[key] == 0
                if last:
                    del _holders[key]
            if last:
                meter.end(key)
