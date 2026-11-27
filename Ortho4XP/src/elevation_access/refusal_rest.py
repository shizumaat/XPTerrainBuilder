"""A provider that refused a query rests for 24 hours.

Owner 2026-11-04: IGN's WFS answered HTTP 400 to every FRANCE50CM query
(the LiDAR HD tile-index layer is gone: "Unknown namespace"), and the
refusal was never remembered, so every build asked it again -- 41
refused queries over +48+002 / +45+005 / +49+002 in one run.

A REFUSAL is the server ANSWERING that it will not serve the query: a
:class:`~elevation_access.base.ProviderQueryError` (a 4xx that is not
404 / 410), or a :class:`~elevation_access.base.TransientFetchError` the
discovery classifier raised for a server answer (a 5xx, a 429, a 200
error envelope -- ``error.server_answered``).  A timeout or a dead
connection is NOT one: that may be this machine's network, and a day
without the provider would follow it.

After a refusal the provider is not asked again, for any airport, until
:data:`REST_S` has passed.  The rest is per PROVIDER (it covers every
query): the queries a provider refuses share their shape, and the owner's
measure is one request per provider per day.  It is never a coverage
answer -- the index keeps whatever it said, and the next asking after the
rest decides.  The memory lives in ``Elevation_data/provider_refusals.json``
(skipped under an armed shared-repo guard, where it stays in this process).
"""

from __future__ import annotations

import contextlib
import threading
import time

import O4_UI_Utils as UI

from elevation_access.base import ProviderQueryError, TransientFetchError
from elevation_access.rest_file import RestFile

__all__ = [
    "REST_S",
    "first_answer_gate",
    "is_refusal",
    "note_resting_once",
    "remember_refusal",
    "resting_refusal",
]

#: How long a refusing provider rests: one day.
REST_S = 24 * 3600

_FILE_NAME = "provider_refusals.json"
_LOCK = threading.Lock()
#: code -> {"at": epoch s, "reason": str, "query": str}, shared by file.
_STORE = RestFile(_FILE_NAME, REST_S)
_NOTED = set()        # codes whose rest this process has already logged
_ANSWERED = set()     # codes that answered (not refused) in this process
_GATES = {}           # code -> the lock its first asking holds


def is_refusal(error) -> bool:
    """Is ``error`` a server's refusal (not a network failure)?"""
    if isinstance(error, ProviderQueryError):
        return True
    return isinstance(error, TransientFetchError) and bool(
        getattr(error, "server_answered", False))


def remember_refusal(code, error, query=None, now=None):
    """Record that provider ``code`` refused ``query`` (an airport, a
    rung) with ``error``: it rests for :data:`REST_S`."""
    now = time.time() if now is None else now
    _STORE.put(code, {"reason": str(error)[:300], "query": str(query or "")},
               now)
    with _LOCK:
        _NOTED.discard(str(code))


def resting_refusal(code, now=None):
    """The refusal provider ``code`` is resting from, or ``None``."""
    return _STORE.live(code, time.time() if now is None else now)


def note_resting_once(code, record, now=None):
    """ONE log line per resting provider per process -- never one per
    airport or query."""
    with _LOCK:
        if str(code) in _NOTED:
            return
        _NOTED.add(str(code))
    now = time.time() if now is None else now
    hours = max(0.0, (REST_S - (now - float(record.get("at", 0)))) / 3600.0)
    UI.vprint(
        1,
        "    [insets] %s refused a query %.0f h ago (%s) - not asked again "
        "for %.0f h; its airports use the next provider (else the base DEM)."
        % (code, (now - float(record.get("at", 0))) / 3600.0,
           record.get("reason") or "refused", hours),
    )


@contextlib.contextmanager
def first_answer_gate(code, query=None):
    """Hold the provider's FIRST asking in this process alone.

    The airports of a tile fetch on worker threads; without this, every
    worker that starts before the first refusal comes back asks too (4 of
    11 airports at +49+002).  Until ``code`` has answered once, one
    asking at a time passes; the others wait and then see the rest the
    refusal left.  Yields the rest record (``None``: go ahead and ask).
    A refusal raised inside is remembered on the way out; any other end
    opens the gate for good (later askings run in parallel again)."""
    code = str(code)
    if code in _ANSWERED:
        yield resting_refusal(code)
        return
    with _LOCK:
        gate = _GATES.setdefault(code, threading.Lock())
    with gate:
        resting = resting_refusal(code)
        try:
            yield resting
        except BaseException as error:
            if is_refusal(error):
                remember_refusal(code, error, query)
            elif resting is None:
                _ANSWERED.add(code)
            raise
        if resting is None and resting_refusal(code) is None:
            _ANSWERED.add(code)
