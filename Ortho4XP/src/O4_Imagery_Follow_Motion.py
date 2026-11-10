"""The camera's ground track and speed, from its positions over time
(#1992 local-imagery-cache spec §4.2-4.5, phase P3b).

The follow job never reads ``sim/flightmodel/position/groundspeed``:
flight 2 was flown with X-Plane's ground-speed multiplier and moved up to
8x faster than that dataref says.  :class:`MotionTracker` takes the
camera's ``(t, lat, lon, alt)`` samples (``t`` = this machine's clock, so
a sim-time multiplier is measured, not trusted) and derives track and
speed from the displacement across the last :data:`WINDOW_S` seconds.

A JUMP (map jump, replay, "move to"; spec §4.5) is a displacement of more
than :data:`JUMP_S` square sizes in under :data:`JUMP_WITHIN_S` seconds
at a speed no aircraft flies (:data:`JUMP_MIN_MS`): the history restarts
at the new place (speed 0 until two samples there) and
:attr:`MotionTracker.jumps` counts it.

Pure: no I/O, no clock.
"""
from __future__ import annotations

import math
from collections import deque

from O4_Imagery_Tier_Plan import Motion

__all__ = ["JUMP_MIN_MS", "JUMP_S", "JUMP_WITHIN_S", "WINDOW_S",
           "MotionTracker"]

#: Seconds of history track and speed are measured over.
WINDOW_S = 6.0
#: A camera move of more than this many S in under JUMP_WITHIN_S is a jump.
JUMP_S = 5.0
JUMP_WITHIN_S = 5.0
#: ... and only above this speed (m/s; Mach 3 at sea level), so an
#: 8x-accelerated jet is still flying, not jumping.
JUMP_MIN_MS = 1000.0

_M_PER_DEG = 111_320.0


def _east_north_m(lat0, lon0, lat1, lon1) -> tuple[float, float]:
    mid = math.radians((lat0 + lat1) / 2.0)
    return ((lon1 - lon0) * _M_PER_DEG * math.cos(mid),
            (lat1 - lat0) * _M_PER_DEG)


class MotionTracker:
    """Track and speed from position deltas; :meth:`add` returns the
    :class:`O4_Imagery_Tier_Plan.Motion` after each sample."""

    def __init__(self, square_m: float = 4000.0, window_s: float = WINDOW_S):
        self.square_m = float(square_m)
        self.window_s = float(window_s)
        self.samples: deque = deque()
        self.jumps = 0
        self.jumped = False          # the last add() was a jump
        self._track = 0.0

    def add(self, t: float, lat: float, lon: float,
            alt_m: float = 0.0) -> Motion:
        """One camera sample; the motion it implies."""
        self.jumped = False
        if self.samples:
            t0, lat0, lon0, _ = self.samples[-1]
            dt = t - t0
            if dt <= 0:
                return self.motion()
            dist = math.hypot(*_east_north_m(lat0, lon0, lat, lon))
            if (dt < JUMP_WITHIN_S and dist > JUMP_S * self.square_m
                    and dist / dt > JUMP_MIN_MS):
                self.samples.clear()
                self.jumps += 1
                self.jumped = True
        self.samples.append((t, lat, lon, alt_m))
        while len(self.samples) > 2 and t - self.samples[1][0] >= self.window_s:
            self.samples.popleft()
        return self.motion()

    def motion(self) -> Motion | None:
        """The current motion, or ``None`` before the first sample."""
        if not self.samples:
            return None
        t1, lat1, lon1, alt1 = self.samples[-1]
        t0, lat0, lon0, _ = self.samples[0]
        speed = 0.0
        if t1 > t0:
            east, north = _east_north_m(lat0, lon0, lat1, lon1)
            speed = math.hypot(east, north) / (t1 - t0)
            if speed > 0.5:          # a parked camera keeps its last track
                self._track = math.degrees(math.atan2(east, north)) % 360.0
        return Motion(lat1, lon1, alt1, self._track, speed)
