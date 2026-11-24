"""The departure core of a planned flight, as the flight's readiness reads
it (#2256): which squares a camera standing at the departure wants finer
than the file on disk, recounted from the index rows on every follow tick.

The count is taken from the rows, never from the spawn episode: X-Plane's
flight load opens an episode of its own, and a readiness that followed the
episode would lose the squares with it.

Pure: no I/O, no clock; the follow job passes the time and its rows.
"""
from __future__ import annotations

import O4_Imagery_Spawn as SPAWN
import O4_Imagery_Tier_Plan as PLAN

__all__ = ["HOLD_MAX_S", "STALL_S", "DepartureCore", "waiting_status"]

#: Seconds without a landing after which the core reads ``stalled``.
STALL_S = 60.0
#: The longest one departure core keeps background downloads waiting.
HOLD_MAX_S = 180.0


def waiting_status(lat: float, lon: float) -> dict:
    """The status before the follow job has counted the core."""
    return {"lat": lat, "lon": lon, "state": "working", "left": 0, "total": 0,
            "failed": 0, "eta_s": None}


class DepartureCore:
    """The core around ``(lat, lon)``, focused at ``at``."""

    def __init__(self, lat: float, lon: float, at: float):
        self.lat, self.lon, self.at = float(lat), float(lon), float(at)
        self.total = 0
        self._left: int | None = None
        self._progress_at = float(at)
        self.status = waiting_status(self.lat, self.lon)

    def is_at(self, lat: float, lon: float) -> bool:
        """Is this the core of the departure ``(lat, lon)``?"""
        return (abs(self.lat - float(lat)) < 1e-6
                and abs(self.lon - float(lon)) < 1e-6)

    def update(self, rows, tiles, failed, now: float, fetch_s: dict,
               slots: int, *, offline: bool = False,
               held: bool = False) -> dict:
        """Recount the core; returns (and keeps) its status."""
        wants = SPAWN.core_wants(rows, self.lat, self.lon, 0.0, tiles)
        lost = sum(1 for key in wants if key in failed)
        left = {key: tier for key, tier in wants.items() if key not in failed}
        count = len(left)
        if self._left is None or count < self._left:
            self._progress_at = now
        self._left = count
        self.total = max(self.total, count + lost)
        state = "done" if not count else (
            "offline" if offline else "held" if held else
            "stalled" if now - self._progress_at >= STALL_S else "working")
        eta = None
        if state == "working":
            work = sum(fetch_s.get(tier, fetch_s[len(PLAN.TIER_WIDTH) - 1])
                       for tier in left.values())
            eta = round(work / max(1, int(slots)), 1)
        self.status = {"lat": self.lat, "lon": self.lon, "state": state,
                       "left": count, "total": self.total, "failed": lost,
                       "eta_s": eta}
        return self.status

    def holds_network(self, now: float) -> bool:
        """Should background downloads wait for this core now?"""
        return (self.status["state"] in ("working", "stalled")
                and now - self.at < HOLD_MAX_S)
