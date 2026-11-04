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
import json
import os
import threading
import time

import O4_File_Names as FNAMES
import O4_UI_Utils as UI

from elevation_access.base import ProviderQueryError, TransientFetchError
from elevation_access.downloads import _write_refused_by_armed_guard

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
_MEMORY = {}          # code -> {"at": epoch s, "reason": str, "query": str}
_LOADED_FROM = [None]
_NOTED = set()        # codes whose rest this process has already logged
_ANSWERED = set()     # codes that answered (not refused) in this process
_GATES = {}           # code -> the lock its first asking holds


def is_refusal(error) -> bool:
    """Is ``error`` a server's refusal (not a network failure)?"""
    if isinstance(error, ProviderQueryError):
        return True
    return isinstance(error, TransientFetchError) and bool(
        getattr(error, "server_answered", False))


def _path():
    root = getattr(FNAMES, "Elevation_dir", "") or ""
    return os.path.join(root, _FILE_NAME) if root else None


def _load_locked():
    """Merge the file into memory when it is new or changed since read:
    the tiles of a build are separate processes, and one's refusal is
    every other's rest."""
    path = _path()
    if path is None:
        return
    try:
        stamp = (path, os.stat(path).st_mtime_ns)
    except OSError:
        stamp = (path, None)
    if _LOADED_FROM[0] == stamp:
        return
    _LOADED_FROM[0] = stamp
    try:
        with open(path, "r", encoding="utf-8") as handle:
            stored = json.load(handle)
    except (OSError, ValueError):
        return
    if isinstance(stored, dict):
        for (code, record) in stored.items():
            mine = _MEMORY.get(str(code))
            if isinstance(record, dict) and (
                    mine is None
                    or float(record.get("at", 0)) > float(mine.get("at", 0))):
                _MEMORY[str(code)] = record


def _save_locked(now):
    path = _path()
    if path is None or not os.path.isdir(os.path.dirname(path)):
        return
    if _write_refused_by_armed_guard(path):
        return                        # a build is not a refresh event
    live = {code: record for (code, record) in _MEMORY.items()
            if now - float(record.get("at", 0)) < REST_S}
    scratch = "%s.%d.tmp" % (path, os.getpid())
    try:
        with open(scratch, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(live, handle, indent=2, sort_keys=True)
        os.replace(scratch, path)
    except OSError:
        try:
            os.remove(scratch)
        except OSError:
            pass


def remember_refusal(code, error, query=None, now=None):
    """Record that provider ``code`` refused ``query`` (an airport, a
    rung) with ``error``: it rests for :data:`REST_S`."""
    now = time.time() if now is None else now
    with _LOCK:
        _load_locked()
        _MEMORY[str(code)] = {"at": now, "reason": str(error)[:300],
                              "query": str(query or "")}
        _NOTED.discard(str(code))
        _save_locked(now)


def resting_refusal(code, now=None):
    """The refusal provider ``code`` is resting from, or ``None``."""
    now = time.time() if now is None else now
    with _LOCK:
        _load_locked()
        record = _MEMORY.get(str(code))
    if record is None or now - float(record.get("at", 0)) >= REST_S:
        return None
    return record


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
