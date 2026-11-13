"""ONE reader of X-Plane's position, shared (flight manager / World spec
§5.1): the follow job, the World pack's swap rule (S3), and later the
World job, the flight manager and the map read the same Web API
connection instead of each opening its own ``PositionReader``.

A :class:`PositionFeed` wraps one ``O4_XPlane_WebAPI.PositionReader`` and
is read like one (:meth:`PositionFeed.read`, ``resets``, ``error``), so
the follow job takes it as its ``reader`` unchanged.  It is PULL-driven:
a read younger than ``max_age_s`` is served from the last record, an
older one reads the Web API once and hands the record to every
subscriber (:meth:`PositionFeed.subscribe`).  No thread of its own: the
feed reads only while someone reads it (the follow job ticks at 1 Hz).

:func:`shared` returns the one feed of a Web API base;
:func:`latest_record` the freshest record any feed holds and
:func:`latest_position` its camera position (``None`` when no feed has
read lately).  The Web API read runs outside the record's lock, so
:meth:`PositionFeed.latest` never waits on X-Plane; :func:`start_pump`
keeps a feed read on a thread of its own for a reader that must never
wait (the flight's tick: 5-6 s per tick with X-Plane not running, owner
log 2026-11-12T20:22Z).
"""
from __future__ import annotations

import threading
import time
from typing import Any, Callable, Dict, List, Optional

__all__ = ["MAX_AGE_S", "FRESH_S", "PUMP_EVERY_S", "shared",
           "latest_record", "latest_position", "start_pump"]

#: A record younger than this is served again instead of a new read.
MAX_AGE_S = 0.5
#: :func:`latest_position` trusts a record this young.
FRESH_S = 5.0
#: :func:`start_pump` reads its feed this often.
PUMP_EVERY_S = 1.0


class _PositionFeed:
    """One Web API position reader, fanned out (see the module)."""

    def __init__(self, reader: Any, max_age_s: float = MAX_AGE_S,
                 clock: Callable[[], float] = time.monotonic) -> None:
        self.reader = reader
        self.max_age_s = float(max_age_s)
        self.clock = clock
        self._lock = threading.Lock()          # the record: never held on I/O
        self._reading = threading.Lock()       # one Web API read at a time
        self._rec: Optional[dict] = None
        self._at: Optional[float] = None
        self._subscribers: List[Callable[[Optional[dict]], None]] = []

    @property
    def resets(self) -> int:
        """The reader's id re-resolves after a failure (flight loads)."""
        return int(getattr(self.reader, "resets", 0))

    @property
    def error(self) -> str:
        return str(getattr(self.reader, "error", ""))

    @property
    def loading(self) -> bool:
        """The reader's last record came while X-Plane loads a flight."""
        return bool(getattr(self.reader, "loading", False))

    def read(self) -> Optional[dict]:
        """The position record (``None`` when X-Plane does not answer);
        from the last read when it is younger than ``max_age_s``."""
        with self._reading:
            with self._lock:
                now = self.clock()
                if self._at is not None and now - self._at < self.max_age_s:
                    return self._rec
            rec = self.reader.read()
            with self._lock:
                self._rec, self._at = rec, self.clock()
                subscribers = list(self._subscribers)
        for callback in subscribers:
            try:
                callback(rec)
            except Exception:           # one bad subscriber never stops the feed
                pass
        return rec

    def latest(self, max_age_s: float = FRESH_S) -> Optional[dict]:
        """The last record when it is younger than ``max_age_s``; no
        read."""
        with self._lock:
            if self._at is None or self.clock() - self._at > max_age_s:
                return None
            return self._rec

    def subscribe(self, callback: Callable[[Optional[dict]], None]
                  ) -> Callable[[], None]:
        """Call ``callback(record)`` after every Web API read; returns the
        unsubscribe."""
        with self._lock:
            self._subscribers.append(callback)

        def unsubscribe() -> None:
            with self._lock:
                if callback in self._subscribers:
                    self._subscribers.remove(callback)
        return unsubscribe


_FEEDS: Dict[str, _PositionFeed] = {}
_FEEDS_GUARD = threading.Lock()


def shared(base: Optional[str] = None) -> _PositionFeed:
    """THE feed of the Web API at ``base`` (default: the app's)."""
    import O4_XPlane_WebAPI as WEBAPI
    base = base or WEBAPI.base_url()
    with _FEEDS_GUARD:
        feed = _FEEDS.get(base)
        if feed is None:
            feed = _FEEDS[base] = _PositionFeed(WEBAPI.PositionReader(base))
        return feed


def latest_record(max_age_s: float = FRESH_S) -> Optional[dict]:
    """The freshest position record any feed holds, or ``None``."""
    with _FEEDS_GUARD:
        feeds = list(_FEEDS.values())
    for feed in feeds:
        rec = feed.latest(max_age_s)
        if rec is not None:
            return rec
    return None


def latest_position(max_age_s: float = FRESH_S) -> Optional[tuple]:
    """``(lat, lon)`` of X-Plane's camera from the freshest record any
    feed holds, or ``None``."""
    import O4_XPlane_WebAPI as WEBAPI
    rec = latest_record(max_age_s)
    return None if rec is None else WEBAPI.camera_position(rec)


def start_pump(feed: _PositionFeed, stop: threading.Event,
               every_s: float = PUMP_EVERY_S,
               name: str = "o4-position-pump") -> threading.Thread:
    """Read ``feed`` every ``every_s`` on a daemon thread until ``stop``
    is set, so its readers take :meth:`_PositionFeed.latest` and never
    wait on the Web API."""
    def run() -> None:
        while not stop.is_set():
            try:
                feed.read()
            except Exception:           # the reader logs; the pump goes on
                pass
            stop.wait(every_s)
    thread = threading.Thread(target=run, daemon=True, name=name)
    thread.start()
    return thread
