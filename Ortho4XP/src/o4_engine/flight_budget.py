"""A flight's disk need against the one disk budget (spec
flight-manager-and-world-20261110 §12; RULINGS 2026-11-10d): the
pre-check ``flight_create`` runs before anything is built.

* :func:`need_bytes` -- ``(lo, hi)`` bytes the flight adds: its open jobs
  by kind (:data:`TILE_BYTES`, the sizes of spec §3), the pre-fetch caches
  of the corridor tiles whose map data and elevation are not on disk yet
  (``plan_estimate.TERRAIN_DATA_BYTES`` each) and the sharp imagery the
  follow job lands along the route (:data:`SHARP_BYTES_PER_HOUR`, loader
  spec §4.3).
* :func:`verdict` -- ``(fits, detail)`` against ``storage_budget.status``'s
  figures and the volume's free space (``plan_estimate.disk_verdict``):
  fits; fits after clearing N GB of older sharp imagery and caches (said,
  not asked: ``storage_budget.hold`` clears it); does not fit, with the
  figures and the two remedies (raise the budget, narrow the corridor).

Pure: no I/O.  No tile or airport is named here.
"""
from __future__ import annotations

from typing import Iterable, Optional, Tuple

from .plan_estimate import GB, TERRAIN_DATA_BYTES, disk_verdict

__all__ = ["TILE_BYTES", "SHARP_BYTES_PER_HOUR", "need_bytes", "verdict"]

#: Bytes one built tile adds, by kind: a 512 px drape 46 MB with no
#: water, 91 MB when every square carries the water copy's DXT5 (lane
#: ldrape2, +53-061, 2026-11-11), scaled by (px / 512)^2 for a sharper
#: ``drape_photo_px``; full ~80 MB plus ~140 MB of rebuild data
#: (memory-note figures, not re-measured: the high end doubled).
TILE_BYTES = {"drape": (45e6, 95e6), "full": (220e6, 440e6)}
#: Sharp imagery along the route, per flight hour at 250 kt (loader spec
#: §4.3 estimate).
SHARP_BYTES_PER_HOUR = (2.2e9, 4.6e9)


def need_bytes(jobs: Iterable, flight_s: float,
               uncached_tiles: int = 0, drape_px: int = 512
               ) -> Tuple[float, float]:
    """``(lo, hi)`` bytes the flight adds (see the module); ``jobs`` are
    ``O4_Flight_Schedule.Job``s (only the open ones count); drapes at
    ``drape_px``."""
    lo = hi = 0.0
    scale = {"drape": (max(512, int(drape_px)) / 512.0) ** 2}
    for job in jobs:
        if job.open and job.kind in TILE_BYTES:
            lo += TILE_BYTES[job.kind][0] * scale.get(job.kind, 1.0)
            hi += TILE_BYTES[job.kind][1] * scale.get(job.kind, 1.0)
    lo += uncached_tiles * TERRAIN_DATA_BYTES[0]
    hi += uncached_tiles * TERRAIN_DATA_BYTES[1]
    hours = max(0.0, float(flight_s)) / 3600.0
    return (lo + hours * SHARP_BYTES_PER_HOUR[0],
            hi + hours * SHARP_BYTES_PER_HOUR[1])


def verdict(need: Tuple[float, float], figures: Optional[dict],
            free_bytes: Optional[float]) -> Tuple[bool, str]:
    """``(fits, detail)``: see the module.  ``figures`` is
    ``storage_budget.status``'s dict (None: not read); ``free_bytes`` the
    data folder's volume (None: unknown)."""
    state, reason = disk_verdict(need, free_bytes, "the data folder's drive")
    if state == "refuse":
        return False, reason + " Or narrow the corridor."
    budget = int((figures or {}).get("budget_bytes") or 0)
    if not budget:
        return True, reason
    used = int(figures.get("used_bytes") or 0)
    floor = int(figures.get("floor_bytes") or 0)
    room = budget - used
    if need[1] <= room:
        return True, ""
    clearable = max(0, used - floor)
    if need[1] <= room + clearable:
        return True, ("Fits after clearing about %.0f GB of older sharp "
                      "imagery and caches." % ((need[1] - max(room, 0)) / GB))
    return False, ("This flight needs up to %.1f GB; the disk budget has "
                   "%.1f GB left beyond what is always kept. Raise the "
                   "budget in Settings ▸ Storage or narrow the corridor."
                   % (need[1] / GB, max(0, room + clearable) / GB))
