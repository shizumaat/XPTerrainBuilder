"""A provider that is DOWN is not asked again by any build for a while.

Owner 2026-11-27 (#2306): five coastal tiles built in parallel while the
USGS TNM discovery endpoint answered 504, and every tile kept asking it --
the inset ladder rungs, the ladder re-checks and the approach-ring and
coastline-band cells: 45 failed queries in one run.

An OUTAGE is a server error (an HTTP 5xx) or a request that timed out --
a TNM gateway timing out, a service behind a load balancer down.  The
first one heard on this computer is written to
``Elevation_data/provider_outages.json`` (:class:`~elevation_access.
rest_file.RestFile`, shared by every process of every build), and for
:data:`OUTAGE_S` no fetch or discovery of that provider is sent: it
raises :class:`ProviderOutage` at once, without a request.  When the
record lapses the next asking goes out again and decides.

The record is never a coverage answer: :class:`ProviderOutage` IS a
:class:`~elevation_access.base.TransientFetchError`, so every caller
already treats it as "no answer this time" -- never ``no-coverage`` -- and
it is not a server's answer either (``server_answered`` False), so it
never starts the 24 h refusal rest (:mod:`elevation_access.refusal_rest`)
by itself.  A rate limit (429) is not an outage: :mod:`elevation_access.
rate_limit` waits that out over fewer connections.

The record is per provider code: every query path names the provider by
its code, and the queries of one provider share its service.
"""

from __future__ import annotations

import contextlib
import threading
import time

import O4_UI_Utils as UI

from elevation_access.base import TransientFetchError
from elevation_access.rest_file import RestFile

__all__ = [
    "OUTAGE_S",
    "ProviderOutage",
    "asking_provider",
    "is_outage",
]

#: How long no build asks a provider that is down: 20 minutes (a TNM
#: outage measured 2026-11-27 lasted the whole tile build).
OUTAGE_S = 20 * 60

_FILE_NAME = "provider_outages.json"
_LOCK = threading.Lock()
_STORE = RestFile(_FILE_NAME, OUTAGE_S)
_NOTED = {}           # code -> the record this process last logged


class ProviderOutage(TransientFetchError):
    """Provider ``code`` is resting from an outage: nothing was asked."""

    def __init__(self, code, record):
        TransientFetchError.__init__(
            self, "%s is down (%s), not asked until the outage record "
                  "lapses" % (code, record.get("reason") or "an outage"))
        self.code = str(code)
        self.record = record
        self.server_answered = False


def is_outage(error) -> bool:
    """A 5xx answer or a timed-out request (never a 429, never a skip)."""
    if not isinstance(error, TransientFetchError) or isinstance(
            error, ProviderOutage):
        return False
    try:
        status = int(getattr(error, "http_status", None) or 0)
    except (TypeError, ValueError):
        status = 0
    return 500 <= status <= 599 or bool(getattr(error, "timed_out", False))


def _remember_outage(code, error, now=None):
    """Record that provider ``code`` is down: no build asks it for
    :data:`OUTAGE_S`."""
    now = time.time() if now is None else now
    _STORE.put(code, {"reason": str(error)[:300]}, now)


def _note_once(code, record, now):
    """ONE log line per outage record per process -- never one per cell."""
    with _LOCK:
        if _NOTED.get(str(code)) == record.get("at"):
            return
        _NOTED[str(code)] = record.get("at")
    age = max(0.0, now - float(record.get("at", 0)))
    UI.vprint(
        1,
        "    [insets] %s is down (%s, %.0f min ago, heard by this or "
        "another build) - not asked again for %.0f min; its airports and "
        "cells use the next source meanwhile."
        % (code, record.get("reason") or "an outage", age / 60.0,
           max(0.0, OUTAGE_S - age) / 60.0))


@contextlib.contextmanager
def asking_provider(code):
    """Around one fetch or discovery of provider ``code``: raise
    :class:`ProviderOutage` at once while an outage record is live, and
    record one when the asking ends in an outage."""
    if not code:
        yield
        return
    now = time.time()
    record = _STORE.live(code, now)   # the outage it rests from, or None
    if record is not None:
        _note_once(code, record, now)
        raise ProviderOutage(code, record)
    try:
        yield
    except BaseException as error:
        if is_outage(error):
            _remember_outage(code, error)
        raise
