"""How many on-demand textures to fetch at once: adaptive like a video
stream's buffer (#1992 local-imagery-cache spec §4.4; owner ruling
2026-11-10T05:18Z, rev 3).

The follow job keeps a BUFFER of tiers landed ahead of the aircraft.  Its
size in seconds is the queue's tightest slack: for the fetches in planner
order, the time to its deadline minus when it would land if the queue
ahead of it ran at the current number of slots (:func:`buffer_s`).
Normally ONE texture is in flight (``O4_Imagery_Prefetch``'s
``TEXTURES_IN_FLIGHT = 1`` precedent: the per-provider load of one
build-step download).  While the buffer DEPLETES (below
:data:`LOW_S`, or shrinking faster than :data:`DRAIN_PER_S` while under
:data:`HIGH_S`) :class:`FetchSlots` adds one slot per
:data:`STEP_S`, up to ``max_slots``; once the buffer has stayed at or
above :data:`HIGH_S` for :data:`RECOVER_S` it drops one slot per
:data:`STEP_S`, back to one.  Each request still goes through the build's
own fetcher (AIMD window, ``Retry-After``, per-host budget), so a second
slot never asks a provider harder than a build does.

Pure: no I/O; the caller passes the clock.
"""
from __future__ import annotations

import math

__all__ = ["DRAIN_PER_S", "FOR_LEAD_S", "HIGH_S", "LOW_S", "MAX_SLOTS",
           "RECOVER_S", "STEP_S", "FetchSlots", "buffer_s", "for_lead"]

#: Buffer (s) below which a deadline is at risk: add a slot.  A fetch
#: becomes due ``T_lead`` (30 s) before its crossing, so a queue that keeps
#: up holds about ``T_lead`` minus one fetch; these two are for that lead
#: (the job scales them with its own, :func:`for_lead`).
LOW_S = 5.0
#: Buffer (s) at or above which the queue is comfortably ahead.
HIGH_S = 15.0
#: The lead LOW_S and HIGH_S are set for (``O4_Imagery_Tier_Plan``).
FOR_LEAD_S = 30.0
#: Buffer loss per second (s/s) that counts as depleting while under HIGH_S.
DRAIN_PER_S = 0.5
#: Seconds the buffer must hold at HIGH_S before a slot is dropped.
RECOVER_S = 20.0
#: At most one slot change per this many seconds (time to see its effect).
STEP_S = 5.0
#: Default ceiling of textures in flight.
MAX_SLOTS = 4


def buffer_s(deadlines, fetch_s, slots: int) -> float:
    """The tightest slack of a queue: ``deadlines`` are the seconds to
    each queued fetch's crossing in planner order, ``fetch_s`` the
    seconds one fetch takes (a number, or one per fetch); with ``slots``
    in flight fetch i lands after ``sum(fetch_s[:i+1]) / slots``.
    ``inf`` for an empty queue."""
    deadlines = list(deadlines)
    if isinstance(fetch_s, (int, float)):
        fetch_s = [float(fetch_s)] * len(deadlines)
    slots = max(1, int(slots))
    worst, work = math.inf, 0.0
    for deadline, cost in zip(deadlines, fetch_s, strict=True):
        work += float(cost)
        worst = min(worst, float(deadline) - work / slots)
    return worst


def for_lead(lead_s: float, max_slots: int = MAX_SLOTS) -> "FetchSlots":
    """A controller whose thresholds scale with the job's ``lead_s``."""
    scale = max(0.1, float(lead_s) / FOR_LEAD_S)
    return FetchSlots(max_slots, low_s=LOW_S * scale, high_s=HIGH_S * scale)


class FetchSlots:
    """The number of textures in flight, from the buffer's level and
    trend.  :meth:`update` takes ``(buffer seconds, now)`` once per job
    tick and returns the slots to run; :attr:`slots` holds it."""

    def __init__(self, max_slots: int = MAX_SLOTS, *, low_s: float = LOW_S,
                 high_s: float = HIGH_S, drain_per_s: float = DRAIN_PER_S,
                 recover_s: float = RECOVER_S, step_s: float = STEP_S):
        self.max_slots = max(1, int(max_slots))
        self.low_s, self.high_s = float(low_s), float(high_s)
        self.drain_per_s = float(drain_per_s)
        self.recover_s, self.step_s = float(recover_s), float(step_s)
        self.slots = 1
        self._last = None             # (now, buffer) of the previous update
        self._changed_at = -math.inf
        self._high_since = None

    def depleting(self, buffer: float, now: float) -> bool:
        """Is the buffer at risk: low, or draining while under HIGH_S?"""
        if buffer < self.low_s:
            return True
        if self._last is None or buffer >= self.high_s:
            return False
        then, before = self._last
        dt = now - then
        if dt <= 0 or math.isinf(before):
            return False
        return (before - buffer) / dt > self.drain_per_s

    def update(self, buffer: float, now: float) -> int:
        """The slots for the next tick."""
        depleting = self.depleting(buffer, now)
        if buffer >= self.high_s:
            if self._high_since is None:
                self._high_since = now
        else:
            self._high_since = None
        can_step = now - self._changed_at >= self.step_s
        if depleting and self.slots < self.max_slots and can_step:
            self.slots += 1
            self._changed_at = now
        elif (not depleting and self.slots > 1 and can_step
              and self._high_since is not None
              and now - self._high_since >= self.recover_s):
            self.slots -= 1
            self._changed_at = now
            self._high_since = now    # each further drop waits again
        self._last = (now, buffer)
        return self.slots
