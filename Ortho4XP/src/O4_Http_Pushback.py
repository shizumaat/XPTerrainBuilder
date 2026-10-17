"""Server pushback for imagery fetches: Retry-After, backoff, per-host pause.

`http_request_to_image` (O4_Imagery_Utils) asks this module how long to
wait after a 429 / 503 / 5xx / connection failure, and waits through it
in short slices so `UI.red_flag` stays responsive
(imagery-fetch-spec §3.1, #834).

- A `Retry-After` (seconds or HTTP-date) is obeyed, clamped to
  [1, PUSHBACK_MAX_WAIT] s, and counted against a per-call budget of
  PUSHBACK_MAX_PAUSES pauses / PUSHBACK_MAX_TOTAL s.
- Without the header the wait is `0.5 * 2**k` s with +-25 % jitter,
  capped at BACKOFF_CAP s, for k <= BACKOFF_MAX_STEPS.
- A 429 / 503 pauses the whole host: every download thread checks
  `host_pause_remaining(url)` before its next request.
"""

import email.utils
from typing import Mapping, Optional
import random
import threading
import time
from urllib.parse import urlsplit

import O4_UI_Utils as UI

__all__ = [
    "Pushback",
    "host_pause_remaining",
    "interruptible_sleep",
    "pause_host",
    "retry_after_seconds",
    "wait_for_host",
]

PUSHBACK_MAX_WAIT = 60.0
PUSHBACK_MAX_PAUSES = 6
PUSHBACK_MAX_TOTAL = 120.0
BACKOFF_BASE = 0.5
BACKOFF_CAP = 8.0
BACKOFF_MAX_STEPS = 5
SLEEP_SLICE = 0.25

_HOST_PAUSE_LOCK = threading.Lock()
_HOST_PAUSED_UNTIL = {}


def retry_after_seconds(headers: Optional[Mapping]) -> Optional[float]:
    """Seconds asked for by a Retry-After header, or None when absent/unreadable."""
    value = (headers or {}).get("Retry-After")
    if value is None:
        return None
    value = str(value).strip()
    try:
        return max(0.0, float(value))
    except ValueError:
        pass
    try:
        when = email.utils.parsedate_to_datetime(value)
    except (TypeError, ValueError, IndexError):
        return None
    if when is None:
        return None
    return max(0.0, when.timestamp() - time.time())


def backoff_delay(step: int) -> float:
    """Exponential backoff with +-25 % jitter for retry number `step` (0-based)."""
    delay = min(BACKOFF_BASE * (2 ** step), BACKOFF_CAP)
    return delay * random.uniform(0.75, 1.25)


def _host(url: str) -> str:
    return urlsplit(url).netloc


def pause_host(url: str, seconds: float) -> None:
    """Hold every request to url's host for `seconds` (never shortens a pause)."""
    host = _host(url)
    until = time.monotonic() + seconds
    with _HOST_PAUSE_LOCK:
        if _HOST_PAUSED_UNTIL.get(host, 0.0) < until:
            _HOST_PAUSED_UNTIL[host] = until


def host_pause_remaining(url: str) -> float:
    """Seconds left on url's host pause (0 when the host is not paused)."""
    with _HOST_PAUSE_LOCK:
        until = _HOST_PAUSED_UNTIL.get(_host(url), 0.0)
    return max(0.0, until - time.monotonic())


def interruptible_sleep(seconds: float) -> bool:
    """Sleep in short slices; False as soon as UI.red_flag is raised."""
    deadline = time.monotonic() + seconds
    while True:
        if UI.red_flag:
            return False
        left = deadline - time.monotonic()
        if left <= 0:
            return True
        time.sleep(min(SLEEP_SLICE, left))


def wait_for_host(url: str) -> bool:
    """Wait out url's host pause, if any; False when stopped by UI.red_flag."""
    remaining = host_pause_remaining(url)
    return interruptible_sleep(remaining) if remaining > 0 else not UI.red_flag


class Pushback:
    """One call's retry state: Retry-After budget and backoff step."""

    def __init__(self) -> None:
        self.pauses = 0
        self.paused_total = 0.0
        self.step = 0

    def next_wait(
        self, headers: Optional[Mapping] = None, pause_url: Optional[str] = None
    ) -> Optional[float]:
        """Seconds to wait before the next try, or None when the budget is spent.

        A Retry-After in `headers` spends the pushback budget; otherwise the
        backoff step advances. `pause_url` (a 429 / 503) shares the wait
        with every thread fetching from that host.
        """
        retry_after = retry_after_seconds(headers) if headers else None
        if retry_after is not None:
            wait = min(max(retry_after, 1.0), PUSHBACK_MAX_WAIT)
            if (
                self.pauses >= PUSHBACK_MAX_PAUSES
                or self.paused_total + wait > PUSHBACK_MAX_TOTAL
            ):
                return None
            self.pauses += 1
            self.paused_total += wait
        else:
            if self.step > BACKOFF_MAX_STEPS:
                return None
            wait = backoff_delay(self.step)
            self.step += 1
        if pause_url:
            pause_host(pause_url, wait)
        return wait
