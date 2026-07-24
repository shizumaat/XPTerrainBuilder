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
_active: dict = {}   # key -> [t0, done_units, total_units, predicted_s]


def begin(key: str, total_units: int,
          predicted_seconds: Optional[float] = None) -> None:
    """Register an active phase of ``total_units`` similar work units.

    ``predicted_seconds`` (optional) prices the whole phase until the
    first unit completes.  Zero/negative unit counts stay out — they
    cannot be paced.
    """
    try:
        if total_units <= 0:
            return
        with _lock:
            _active[key] = [
                time.time(), 0, int(total_units),
                float(predicted_seconds) if predicted_seconds else None,
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
    except Exception:
        pass


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
            for t0, done, total, predicted in _active.values():
                elapsed = max(now - t0, 0.0)
                if done > 0:
                    remaining = (elapsed / done) * (total - done)
                elif predicted is not None:
                    if elapsed < predicted:
                        remaining = predicted - elapsed
                    else:
                        remaining = (
                            _OVERRUN_REMAINING_FRACTION
                            * (elapsed - predicted))
                else:
                    continue
                if best is None or remaining > best:
                    best = remaining
        return best
    except Exception:
        return None


def _reset_for_tests() -> None:
    with _lock:
        _active.clear()
