"""A streamed transfer's throughput floor (issue #2211).

A server that keeps the connection alive and trickles bytes never makes
a transfer FAIL: every read returns before the socket's timeout, so a
retry loop that counts failed attempts never gets to its fallback
(measured: a Viewfinderpanoramas base archive ran 80+ min this way).
:class:`ThroughputFloor` is the download manager's
:class:`~O4_Download_Manager.Watcher` that makes such an attempt fail:
over each window of :data:`FLOOR_WINDOW_SECONDS` the body must move at
least :data:`FLOOR_BYTES_PER_SECOND`, or the next chunk raises
:class:`TransferTooSlow`.  ``abandoned`` (optional) is asked at every
chunk too: true raises :class:`TransferAbandoned` -- the user chose
another source for this transfer.

The clock is injected, so a twin proves the floor without waiting it
out.  The verdict lands at a chunk boundary, so a caller that wants it
on time streams in small chunks (:data:`FLOOR_CHUNK_BYTES`).  No
GUI-toolkit imports (core-module rule).
"""
from __future__ import annotations

import time
from typing import Callable, Optional

import O4_Download_Manager as DOWNLOADS

__all__ = ["FLOOR_BYTES_PER_SECOND", "FLOOR_CHUNK_BYTES",
           "FLOOR_WINDOW_SECONDS", "ThroughputFloor", "TransferAbandoned",
           "TransferTooSlow"]

#: The slowest a body may move, averaged over one window (owner bar on
#: #2211: "< 100 KB/s over 60 s" fails the attempt).
FLOOR_BYTES_PER_SECOND = 100 * 1024
FLOOR_WINDOW_SECONDS = 60.0

#: The chunk a floored stream reads: the verdict waits for a chunk to
#: land, so at a 1 KB/s trickle this is a check every 16 s instead of
#: the manager's 256 KiB (four minutes).
FLOOR_CHUNK_BYTES = 16 * 1024


class TransferTooSlow(OSError):
    """The body moved below the floor for a whole window."""


class TransferAbandoned(OSError):
    """The caller's ``abandoned`` came true while the body streamed."""


class ThroughputFloor(DOWNLOADS.Watcher):
    """Fails a streamed transfer that moves below the floor.

    Windows are back to back: each starts where the last passed, so a
    server that stalls after a fast start is still caught one window
    later."""

    def __init__(self, floor_bytes_per_second: float = FLOOR_BYTES_PER_SECOND,
                 window_seconds: float = FLOOR_WINDOW_SECONDS,
                 clock: Callable[[], float] = time.monotonic,
                 abandoned: Optional[Callable[[], bool]] = None):
        self._floor = float(floor_bytes_per_second)
        self._window = float(window_seconds)
        self._clock = clock
        self._abandoned = abandoned
        self._window_t0: Optional[float] = None
        self._window_bytes = 0

    def started(self, total_bytes: int) -> None:
        self._window_t0 = self._clock()
        self._window_bytes = 0

    def chunk(self, size: int, received: int, total_bytes: int) -> None:
        if self._abandoned is not None and self._abandoned():
            raise TransferAbandoned(
                "abandoned at %d bytes: another source was chosen" % received)
        now = self._clock()
        if self._window_t0 is None:
            (self._window_t0, self._window_bytes) = (now, received)
            return
        elapsed = now - self._window_t0
        if elapsed < self._window:
            return
        rate = (received - self._window_bytes) / elapsed
        if rate < self._floor:
            raise TransferTooSlow(
                "the body moved %.1f KB/s over %.0f s, below the %.0f KB/s "
                "floor (%d bytes received)"
                % (rate / 1024.0, elapsed, self._floor / 1024.0, received))
        (self._window_t0, self._window_bytes) = (now, received)
