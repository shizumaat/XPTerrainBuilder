"""How often a streamed scan's partial results reach the screen (#2055).

The engine streams ``ScanBatch`` / ``ScanProgress`` at ~10 Hz so a long
scan fills the map as it goes.  Each one the window published repainted
the whole map (the airport layer alone is ~100 ms of Python on a large
install), so a ~25 s launch scan kept the GUI thread busy for most of it.
The scan still accumulates every batch; this says when the accumulated
tiles are published: the first batch at once (the map fills immediately),
then at most once per ``interval``; ``ScanDone`` always publishes the
final truth.

One rule in both apps (Mac: ``ScanStreamThrottle``), twinned on
``tests/fixtures/scan_stream_throttle_cases.json``.
"""
from __future__ import annotations

__all__ = ["DEFAULT_INTERVAL", "ScanStreamThrottle"]

#: Seconds between two publications of a streaming scan.
DEFAULT_INTERVAL = 1.0


class ScanStreamThrottle:
    """Says, per streamed batch, whether to publish what accumulated."""

    def __init__(self, interval: float = DEFAULT_INTERVAL) -> None:
        self.interval = float(interval)
        self._published_at = None

    def reset(self) -> None:
        """A new scan starts: its first batch publishes at once."""
        self._published_at = None

    def should_publish(self, now: float) -> bool:
        """True when the batch arriving at ``now`` (seconds, any monotonic
        clock) should publish; records the publication."""
        last = self._published_at
        if last is not None and now - last < self.interval:
            return False
        self._published_at = now
        return True
