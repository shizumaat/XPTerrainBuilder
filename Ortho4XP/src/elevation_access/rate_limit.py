"""A provider's rate limit on ONE transfer: wait it out, fewer connections.

HTTP 429 (and a 503 carrying ``Retry-After``) is the server saying "too
many of you, come back later" -- never "this tile does not exist" and
never "give this rung up" (#2295: TIST's USGS lidar point-cloud rung
started 12 LAS tiles over 4 connections, one GET answered 429, and the
whole rung was dropped for 1/3 arc-second (10 m) fill).

:func:`rate_limit_wait` is the answer a transfer gives a 429: the
``Retry-After`` the server asked for (else the next wait of
:data:`RATE_LIMIT_WAITS_S`), the PROVIDER paused for every connection
meanwhile (``O4_Http_Pushback.pause_host``, keyed on the provider like
``fetch_retry``), a progress line at least every
:data:`RATE_LIMIT_PROGRESS_S` while it waits (the app's stuck detector
reads silence as a hang), and the provider THROTTLED: from then on
:func:`throttled_connection` lets one transfer at a time reach it.
``False`` when the waits are spent or Stop was pressed -- the caller then
raises its transient error, as before.
"""

import contextlib
import threading

import O4_Http_Pushback as PUSHBACK
import O4_UI_Utils as UI

__all__ = [
    "RATE_LIMIT_PROGRESS_S",
    "RATE_LIMIT_WAITS_S",
    "is_rate_limited",
    "rate_limit_wait",
    "throttled_connection",
    "wait_for_provider",
]

#: Seconds to wait after each rate-limit answer without a ``Retry-After``;
#: then the transfer gives up (about 7.5 minutes in all).
RATE_LIMIT_WAITS_S = (30.0, 60.0, 120.0, 240.0)
#: The longest a ``Retry-After`` is obeyed for one wait.
RATE_LIMIT_MAX_WAIT_S = 300.0
#: At most this long between two "still waiting" lines.
RATE_LIMIT_PROGRESS_S = 10.0

_LOCK = threading.Lock()
_THROTTLED = {}


def _key(code) -> str:
    """The ``O4_Http_Pushback`` host key of one provider (``fetch_retry``'s)."""
    return "https://elevation-provider-%s/" % str(code).lower()


def is_rate_limited(status, headers=None) -> bool:
    """A 429, or a 503 that names when to come back."""
    status = int(status)
    return status == 429 or (
        status == 503 and PUSHBACK.retry_after_seconds(headers) is not None)


def throttled_connection(code):
    """A context: one transfer at a time to ``code`` once it has rate
    limited us (a no-op before)."""
    with _LOCK:
        lock = _THROTTLED.get(str(code))
    return lock if lock is not None else contextlib.nullcontext()


def wait_for_provider(code, label) -> bool:
    """Wait out ``code``'s pause, a line at least every
    :data:`RATE_LIMIT_PROGRESS_S`; False on Stop."""
    remaining = PUSHBACK.host_pause_remaining(_key(code))
    while remaining > 0:
        UI.vprint(1, "    [inset] %s: waiting %.0f s more for %s's rate limit"
                  % (label, remaining, code))
        if not PUSHBACK.interruptible_sleep(
                min(remaining, RATE_LIMIT_PROGRESS_S)):
            return False
        remaining = PUSHBACK.host_pause_remaining(_key(code))
    return not UI.red_flag


def rate_limit_wait(code, headers, attempt, label) -> bool:
    """Wait after rate-limit answer number ``attempt`` (0-based); True to
    ask again, False when the waits are spent or on Stop."""
    if attempt >= len(RATE_LIMIT_WAITS_S):
        return False
    asked = PUSHBACK.retry_after_seconds(headers)
    wait = (RATE_LIMIT_WAITS_S[attempt] if asked is None
            else min(max(asked, 1.0), RATE_LIMIT_MAX_WAIT_S))
    with _LOCK:
        _THROTTLED.setdefault(str(code), threading.Lock())
    PUSHBACK.pause_host(_key(code), wait)
    UI.vprint(1, "    [inset] %s: %s is rate limiting us -- waiting %.0f s%s,"
              " then asking again over one connection (retry %d of %d)"
              % (label, code, wait, " as it asked" if asked is not None
                 else "", attempt + 1, len(RATE_LIMIT_WAITS_S)))
    return wait_for_provider(code, label)
