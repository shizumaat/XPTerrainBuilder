"""Process-wide pacing telemetry for countable long-running phases.

Sibling of :mod:`download_meter` for work that blocks a build step but
cannot be priced in bytes: airport elevation inset fetches (N airports,
opaque GDAL transfers each), Overpass query rounds, and any future
phase built from repeated similar units.  The phase registers its unit
count, advances a counter as units complete, and
``active_remaining_seconds`` prices the unfinished units at the phase's
own measured pace — so the ETA follows "3 of 17 airports in 6 minutes"
instead of a static model guess.

Before the first unit completes there is no pace yet; a caller-supplied
prediction (typically from the step's learned time model) prices the
whole phase until then, decaying like an ordinary overrun rather than
expiring to zero.

A phase may also say, in plain words, WHAT it is doing and WHY it is
slow, and whether it can finish on coarser data (#1351): the slow-step
alert (:mod:`o4_engine.slow_step`) reads :func:`slowest_phase` for its
words and offers "Use coarser data" only when the phase said it can;
:func:`request_coarser` is the user's answer, which the phase polls with
:func:`coarser_requested` before each remaining unit.

Same contract as download_meter: stdlib only, safe from any thread,
never raises.
"""

from __future__ import annotations

import threading
import time
from typing import Optional

# An unfinished phase whose prediction has fully elapsed keeps this
# fraction of its overrun as remaining — mirroring
# tile_time_model.OVERRUN_REMAINING_FRACTION (kept literal here:
# download_meter/task_meter stay import-light and GUI/model-free).
_OVERRUN_REMAINING_FRACTION = 0.5

_lock = threading.Lock()
# key -> [t0, done_units, total_units, predicted_s, words]; ``words`` is
# {"what", "why", "reason", "coarser"} as :func:`begin` was given them.
_active: dict = {}
# Phases whose remaining units the user asked to finish on coarser data.
_coarser: set = set()


def begin(key: str, total_units: int,
          predicted_seconds: Optional[float] = None, *, what: str = "",
          why: str = "", reason: str = "", coarser: bool = False) -> None:
    """Register an active phase of ``total_units`` similar work units.

    ``predicted_seconds`` (optional) prices the whole phase until the
    first unit completes.  Zero/negative unit counts stay out — they
    cannot be paced.  ``what`` / ``why`` are the phase's plain words for
    the slow-step alert (``what`` may name ``{done}`` and ``{total}``),
    ``reason`` its short reason code, and ``coarser`` whether it can
    finish its remaining units on coarser data.
    """
    try:
        if total_units <= 0:
            return
        with _lock:
            _coarser.discard(key)
            _active[key] = [
                time.time(), 0, int(total_units),
                float(predicted_seconds) if predicted_seconds else None,
                {"what": str(what), "why": str(why), "reason": str(reason),
                 "coarser": bool(coarser)},
            ]
    except Exception:
        pass


def advance(key: str, done_units: int) -> None:
    """Record that ``done_units`` of the phase's units are now complete."""
    try:
        with _lock:
            entry = _active.get(key)
            if entry is not None:
                entry[1] = min(int(done_units), entry[2])
    except Exception:
        pass


def end(key: str) -> None:
    try:
        with _lock:
            _active.pop(key, None)
            _coarser.discard(key)
    except Exception:
        pass


def _remaining(entry, now) -> Optional[float]:
    t0, done, total, predicted = entry[:4]
    elapsed = max(now - t0, 0.0)
    if done > 0:
        return (elapsed / done) * (total - done)
    if predicted is None:
        return None
    if elapsed < predicted:
        return predicted - elapsed
    return _OVERRUN_REMAINING_FRACTION * (elapsed - predicted)


def slowest_phase() -> Optional[dict]:
    """The active phase with words that has the most time left (#1351).

    ``{"key", "what", "why", "reason", "coarser", "done", "total",
    "seconds_per_unit", "remaining"}`` — ``what`` with its ``{done}`` /
    ``{total}`` filled, ``seconds_per_unit`` / ``remaining`` ``None``
    before the first unit is done, ``coarser`` false once asked.
    ``None`` when no active phase said what it is.
    """
    try:
        now = time.time()
        best = None
        with _lock:
            for key, entry in _active.items():
                t0, done, total, _predicted, words = entry
                if not words.get("what"):
                    continue
                remaining = _remaining(entry, now)
                row = {
                    "key": key,
                    "what": words["what"].format(done=done, total=total),
                    "why": words["why"],
                    "reason": words["reason"],
                    "coarser": words["coarser"] and key not in _coarser,
                    "done": done,
                    "total": total,
                    "seconds_per_unit": (max(now - t0, 0.0) / done
                                         if done else None),
                    "remaining": remaining,
                }
                if best is None or (remaining or 0.0) > (
                        best["remaining"] or 0.0):
                    best = row
        return best
    except Exception:
        return None


def request_coarser(key: str) -> bool:
    """The user's "Use coarser data" for phase ``key``: True when the
    phase is active and said it can; the phase reads it through
    :func:`coarser_requested` before each remaining unit."""
    try:
        with _lock:
            entry = _active.get(key)
            if entry is None or not entry[4].get("coarser"):
                return False
            _coarser.add(key)
            return True
    except Exception:
        return False


def coarser_requested(key: str) -> bool:
    """Whether the user asked phase ``key`` to finish on coarser data."""
    try:
        with _lock:
            return key in _coarser
    except Exception:
        return False


def active_remaining_seconds() -> Optional[float]:
    """Seconds to finish the slowest active phase at its measured pace.

    Phases run concurrently with each other and with other step work,
    so the estimate is the MAX over phases (contrast download_meter,
    which sums bytes over one shared connection pool).  ``None`` when
    nothing active offers a basis — the caller keeps its own estimate.
    """
    try:
        now = time.time()
        best = None
        with _lock:
            for entry in _active.values():
                remaining = _remaining(entry, now)
                if remaining is None:
                    continue
                if best is None or remaining > best:
                    best = remaining
        return best
    except Exception:
        return None


def _reset_for_tests() -> None:
    with _lock:
        _active.clear()
        _coarser.clear()
