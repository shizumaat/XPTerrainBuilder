"""HOW THE LIBRARY'S COMMANDS RUN BESIDE A BUILD — one scan per command at
a time, in the background band while a build runs (issue #2268).

The app asks for a Library scan and a stale-tile check after every map
scan, and the map rescans as each tile of a run lands in the World pack.
Each request was a new ``o4-library`` thread: during a build they
overlapped, each walking the same folders, and the engine's own process
spent 1.0-1.7 cores for ten minutes beside the build (owner's 1.0.575
profile, 2026-11-24).

* **one run per command at a time** (:data:`COALESCED`): a request made
  while the same command runs waits; when that run ends, ONE more run with
  the newest request's arguments answers every request that waited — so
  each answer is still computed after it was asked, and a burst of N
  requests costs two runs, not N.
* **the background band while a build runs** (``O4_Machine_Slots.
  background_thread``): the run's thread, and the row threads a Library
  scan starts (:func:`row_initializer`), yield their CPU and disk to the
  build.  With no build running a scan runs at the engine's own priority.
"""
from __future__ import annotations

import contextlib
import threading
import typing as _t

import O4_Machine_Slots as SLOTS

__all__ = ["COALESCED", "launch", "row_initializer"]

#: the read-only scans one run at a time answers (module doc)
COALESCED = frozenset({"library_scan", "tile_staleness", "cache_sizes",
                       "storage_scan"})

_LOCK = threading.Lock()
_RUNNING: set = set()
_WAITING: dict = {}
_BAND = threading.local()


def launch(command: str, request: _t.Any, kwargs: dict,
           body: _t.Callable[[list, dict], None],
           busy: _t.Callable[[], bool] = lambda: False) -> None:
    """Run ``body(requests, kwargs)`` on an ``o4-library`` thread — at once,
    or, for a :data:`COALESCED` command already running, after that run,
    together with every other request that waited (module doc)."""
    if command in COALESCED:
        with _LOCK:
            if command in _RUNNING:
                _WAITING.setdefault(command, []).append((request, kwargs))
                return
            _RUNNING.add(command)
        target = lambda: _runs(command, [request], kwargs, body, busy)  # noqa: E731
    else:
        target = lambda: _banded(body, [request], kwargs, busy)  # noqa: E731
    threading.Thread(target=target, daemon=True, name="o4-library").start()


def _runs(command: str, requests: list, kwargs: dict, body, busy) -> None:
    while True:
        try:
            _banded(body, requests, kwargs, busy)
        finally:
            with _LOCK:
                waiting = _WAITING.pop(command, [])
                if not waiting:
                    _RUNNING.discard(command)
        if not waiting:
            return
        requests = [request for request, _kw in waiting]
        kwargs = waiting[-1][1]


def _banded(body, requests: list, kwargs: dict, busy) -> None:
    try:
        low = bool(busy())
    except Exception:
        low = False
    band = SLOTS.background_thread() if low else contextlib.nullcontext()
    _BAND.low = low
    try:
        with band:
            body(requests, kwargs)
    finally:
        _BAND.low = False


def row_initializer():
    """A thread pool's initializer that puts its threads in this thread's
    band (``None`` when this thread runs at its own priority)."""
    if not getattr(_BAND, "low", False):
        return None
    return SLOTS.lower_this_thread
