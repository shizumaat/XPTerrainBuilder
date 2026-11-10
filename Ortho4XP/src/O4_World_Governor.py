"""Sharing the CPU with X-Plane while it flies (flight manager / World
spec 2026-11-10, §10).

* :func:`flight_slots` -- build slots while X-Plane answers and the
  aircraft is beyond ``parked``: the ``fly_build_slots`` setting, or
  automatically ``clamp((cores - 6) // 3, 1, 3)`` [estimate; the 6 is
  X-Plane's share, to be set from the F1 flight], never more than memory
  admits.
* :func:`parked_slots` -- while parked and preparing: the normal capacity
  less two more cores (the pilot waits; frame rate matters little).
* :class:`FrameGovernor` -- the frame-time guard.  Baseline: the p90 frame
  time over the last :data:`BASELINE_S` with no build running.  When the
  p90 over the last :data:`WINDOW_S` rises more than the mode's share
  above it (``balanced`` 25 %, ``smooth`` 10 %, ``fast`` never), one slot
  is given back (the caller starts no new build until it is under the
  cap; a running build ends at its step boundary), down to ``floor``;
  after :data:`RECOVER_S` back under, one is returned.

Every build child already runs at nice 10 (``O4_Machine_Slots.
lower_priority``); this module only says how many may run.

Pure: no I/O, no clock (times are passed in).
"""
from __future__ import annotations

from collections import deque

__all__ = ["MODES", "XPLANE_CORES", "MAX_FLIGHT_SLOTS", "BASELINE_S",
           "WINDOW_S", "RECOVER_S", "flight_slots", "parked_slots",
           "FrameGovernor"]

#: ``fly_sim_priority`` -> how far the recent p90 may rise above the
#: baseline before a slot is given back (``None``: never).
MODES = {"smooth": 0.10, "balanced": 0.25, "fast": None}
#: Cores left to X-Plane in the automatic rule [estimate, U9].
XPLANE_CORES = 6
#: The automatic rule's ceiling in flight.
MAX_FLIGHT_SLOTS = 3
#: Seconds of no-build frames the baseline is the p90 of.
BASELINE_S = 60.0
#: Seconds of frames the recent p90 is taken over.
WINDOW_S = 30.0
#: Seconds back under the line before a slot is returned.
RECOVER_S = 60.0
#: Fewer no-build frames than this keep the previous baseline.
_MIN_SAMPLES = 10


def flight_slots(cores: int, setting: int = 0,
                 memory_slots: int | None = None) -> int:
    """Build slots in flight (see the module); ``setting`` > 0 is the
    user's ``fly_build_slots``."""
    slots = (int(setting) if int(setting or 0) > 0
             else min(max((int(cores) - XPLANE_CORES) // 3, 1),
                      MAX_FLIGHT_SLOTS))
    if memory_slots is not None:
        slots = min(slots, max(1, int(memory_slots)))
    return max(1, slots)


def parked_slots(capacity: int) -> int:
    """Build slots while parked and preparing: the session's capacity
    less two more cores."""
    return max(1, int(capacity) - 2)


def _p90(values: list) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(0.9 * len(ordered)))]


class FrameGovernor:
    """The frame-time guard (see the module).  :meth:`observe` each
    position's ``frame_s``; :meth:`allowed` the slots now."""

    def __init__(self, mode: str = "balanced", floor: int = 1) -> None:
        if mode not in MODES:
            raise ValueError(f"unknown sim priority {mode!r} "
                             f"(known: {sorted(MODES)})")
        self.share = MODES[mode]
        self.floor = int(floor)
        self.samples: deque = deque()        # (t, frame_s, building)
        self.baseline: float | None = None
        self.reduced = 0
        self._most = None                    # cap - floor at the last allowed()
        self._changed_at: float | None = None
        self._under_since: float | None = None

    @property
    def state(self) -> str:
        """``ok`` or ``reduced`` (``WorldStatus.governor``)."""
        return "reduced" if self.reduced else "ok"

    def frame_ms(self) -> float:
        """The recent p90 frame time in ms (0 before any frame)."""
        recent = [f for _, f, _ in self.samples]
        return round(_p90(recent) * 1000.0, 1) if recent else 0.0

    def observe(self, now: float, frame_s, building: bool) -> None:
        """One frame-time sample at ``now`` (``building``: a build of ours
        is running)."""
        if not frame_s or frame_s <= 0:
            return
        self.samples.append((now, float(frame_s), bool(building)))
        while self.samples and now - self.samples[0][0] > BASELINE_S:
            self.samples.popleft()
        quiet = [f for _, f, b in self.samples if not b]
        if len(quiet) >= _MIN_SAMPLES:
            self.baseline = _p90(quiet)
        if self.share is None or self.baseline is None:
            return
        recent = [f for t, f, _ in self.samples if now - t <= WINDOW_S]
        line = self.baseline * (1.0 + self.share)
        if _p90(recent) > line:
            self._under_since = None
            if self._changed_at is None or now - self._changed_at >= WINDOW_S:
                self.reduced += 1
                if self._most is not None:
                    self.reduced = min(self.reduced, self._most)
                self._changed_at = now
            return
        if self._under_since is None:
            self._under_since = now
        if self.reduced and now - self._under_since >= RECOVER_S:
            self.reduced -= 1
            self._changed_at = self._under_since = now

    def allowed(self, cap: int) -> int:
        """Slots under ``cap`` now: one fewer per slot given back, never
        under ``floor``."""
        self._most = max(0, int(cap) - self.floor)
        self.reduced = min(self.reduced, self._most)
        return max(self.floor, int(cap) - self.reduced)
