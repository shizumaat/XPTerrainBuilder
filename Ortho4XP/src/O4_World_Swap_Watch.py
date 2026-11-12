"""When a World or flight job puts a tile into the World pack, the Build
map rescans: the tile's World state changed and its build (records,
patches) is now ours to show -- the patch view and editor included (owner
2026-11-12T22:19Z: a tile a flight had just built showed no patch view or
editor when zoomed in).  The build itself refreshes through its
BuildDone / TileState; the swap comes after them.

One rule in both apps (Mac: ``WorldSwapWatch``), twinned on
``tests/fixtures/world_swap_watch_cases.json``.  No tile or airport is
named here.
"""
from __future__ import annotations

__all__ = ["SWAPPED", "SwapWatch"]

#: The flight job state of a tile the World pack now holds.
SWAPPED = "swapped"


class SwapWatch:
    """Remembers the last statuses; each method says whether to rescan."""

    def __init__(self) -> None:
        self._swapped: frozenset = frozenset()
        self._last_swap: tuple = ()

    def flight_status(self, jobs) -> bool:
        """``FlightStatus.jobs`` rows ``[[lat, lon], role, kind, state,
        ...]``: True when a job reached ``swapped`` since the last status."""
        now = frozenset(
            (int(row[0][0]), int(row[0][1])) for row in (jobs or ())
            if len(row) >= 4 and row[3] == SWAPPED)
        fresh = bool(now - self._swapped)
        self._swapped = now
        return fresh

    def world_status(self, last_swap) -> bool:
        """``WorldStatus.last_swap`` ``[tile, kind, utc]``: True when it
        names a swap the last status did not."""
        swap = tuple(str(part) for part in (last_swap or ()))
        fresh = bool(swap) and swap != self._last_swap
        self._last_swap = swap
        return fresh
