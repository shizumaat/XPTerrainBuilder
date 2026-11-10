"""X-Plane 12's DSF window: which tiles it holds open, and when one enters
(flight manager / World spec 2026-11-10, §2.2 and §8.1).

The model, read off the CYYR World pack recording (2026-11-10, 53°N, every
``.dsf`` open joined to the aircraft position) and CYXY flight 2 (60°N):

* X-Plane holds FOUR columns ``B-2 .. B+1`` around a tile boundary ``B``
  (a whole degree of longitude) and THREE rows ``R-1 .. R+1`` around the
  row ``R`` (tile rows are ``[R, R+1)``).
* ``B`` moves one column when the aircraft is more than
  :data:`COLUMN_SHIFT` (0.65°) of longitude from it; ``R`` moves one row
  when the aircraft is more than :data:`ROW_SHIFT` (0.10°) beyond the
  row's edge.  Both have hysteresis: the window does not follow the
  aircraft back until it crosses the opposite line.
* A tile's DSF is opened when its column or row enters the window, so a
  tile enters when the aircraft is 1.35° of longitude or 0.90° of latitude
  from the tile's near edge (:func:`load_box`).
* At a flight load ``B = round(lon)`` and ``R = floor(lat)`` [assumed from
  the CYYR start: lon -60.447 gave columns -62..-59].

:class:`WindowTracker` keeps ``B`` and ``R`` from a position feed.  While
the history is unknown (first position of a session) it keeps every
plausible ``B`` and ``R`` (all those the hysteresis rule allows at that
position) and answers with the union of their windows, so "loaded?" errs
toward yes and deadlines err early; the candidates collapse as the aircraft
moves, or at once when :meth:`WindowTracker.witness` is told which tile
X-Plane loaded (``O4_XPlane_Log``).

Pure: standard library only, no I/O.
"""
from __future__ import annotations

import math
from typing import Iterable

__all__ = [
    "COLUMN_SHIFT", "ROW_SHIFT", "WindowTracker", "plausible_columns",
    "plausible_rows", "window_tiles", "load_box", "reach", "route_entries",
]

#: Degrees of longitude from the boundary ``B`` at which the window moves
#: one column [measured: 0.651-0.657 at 53°N, 0.64-0.65 at 60°N].
COLUMN_SHIFT = 0.65
#: Degrees of latitude past the row's edge at which the window moves one
#: row [measured: 0.100 southbound and northbound at 53°N].
ROW_SHIFT = 0.10
_M_PER_DEG = 111_320.0

Tile = tuple[int, int]


def plausible_columns(lon: float) -> set[int]:
    """Every boundary ``B`` the hysteresis rule allows at ``lon``: the
    whole degrees within :data:`COLUMN_SHIFT` of it (one or two)."""
    return {b for b in (math.floor(lon), math.ceil(lon))
            if abs(lon - b) <= COLUMN_SHIFT}


def plausible_rows(lat: float) -> set[int]:
    """Every row ``R`` the hysteresis rule allows at ``lat``: those whose
    row, widened by :data:`ROW_SHIFT` each side, holds it (one or two)."""
    f = math.floor(lat)
    return {r for r in (f - 1, f, f + 1)
            if r - ROW_SHIFT <= lat <= r + 1 + ROW_SHIFT}


def window_tiles(cols: Iterable[int], rows: Iterable[int]) -> set[Tile]:
    """The tiles ``(lat, lon)`` of the union of the windows of the
    boundaries ``cols`` and rows ``rows``."""
    lons = {c for b in cols for c in range(b - 2, b + 2)}
    lats = {r + d for r in rows for d in (-1, 0, 1)}
    return {(la, lo) for la in lats for lo in lons}


def load_box(tlat: int, tlon: int) -> tuple[float, float, float, float]:
    """``(south, north, west, east)``: the aircraft positions from which tile
    ``(tlat, tlon)`` can be in the window.  It ENTERS when the aircraft
    crosses into this box: 0.90° of latitude and 1.35° of longitude from
    the tile's near edge.  (It leaves only farther out, by the hysteresis.)
    """
    return (tlat - 1 + ROW_SHIFT, tlat + 2 - ROW_SHIFT,
            tlon - 2 + COLUMN_SHIFT, tlon + 3 - COLUMN_SHIFT)


def reach(lat: float, lon: float, tlat: int, tlon: int,
          tracker: "WindowTracker | None" = None) -> dict:
    """Is tile ``(tlat, tlon)`` in the window for an aircraft at
    ``(lat, lon)``, and how far is the aircraft from the line where it
    would enter: ``{"in_window", "km_to_load"}`` (``km_to_load`` 0 inside
    the :func:`load_box`).  ``in_window`` reads ``tracker`` when given,
    else the union of the plausible windows at this position (the history
    is unknown, so it errs toward yes)."""
    if tracker is not None and tracker.known():
        held = (tlat, tlon) in tracker.window()
    else:
        held = (tlat, tlon) in window_tiles(plausible_columns(lon),
                                            plausible_rows(lat))
    south, north, west, east = load_box(tlat, tlon)
    dlat = max(south - lat, 0.0, lat - north)
    dlon = max(west - lon, 0.0, lon - east)
    km = math.hypot(dlat, dlon * math.cos(math.radians(lat))) * _M_PER_DEG / 1000
    return {"in_window": held, "km_to_load": round(km, 1)}


def _shift(b: int, x: float, lo: float, hi: float) -> int:
    """Move ``b`` one step at a time while ``x`` lies outside
    ``[b + lo, b + hi]``."""
    while x > b + hi:
        b += 1
    while x < b + lo:
        b -= 1
    return b


class WindowTracker:
    """Keeps the window's ``B`` and ``R`` from a feed of positions.

    ``cols`` and ``rows`` are the candidate ``B`` and ``R`` (one each once
    the history is known; empty before the first position).  Call
    :meth:`load` at a flight load or jump, :meth:`update` for each position
    and :meth:`witness` for each DSF X-Plane is seen to load."""

    def __init__(self) -> None:
        self.cols: set[int] = set()
        self.rows: set[int] = set()

    def known(self) -> bool:
        """True when one ``B`` and one ``R`` remain."""
        return len(self.cols) == 1 and len(self.rows) == 1

    def window(self) -> set[Tile]:
        """The tiles held now (the union while the history is unknown)."""
        return window_tiles(self.cols, self.rows)

    def forget(self) -> None:
        """History unknown again: the next :meth:`update` starts from every
        plausible window."""
        self.cols, self.rows = set(), set()

    def load(self, lat: float, lon: float) -> set[Tile]:
        """X-Plane (re)loaded the flight at ``(lat, lon)``: ``B = round(lon)``,
        ``R = floor(lat)`` [assumed].  Returns the window."""
        self.cols, self.rows = {math.floor(lon + 0.5)}, {math.floor(lat)}
        return self.window()

    def update(self, lat: float, lon: float) -> set[Tile]:
        """Advance to the position; returns the tiles that ENTER the window
        here (the whole window at the first position of an unknown
        history)."""
        before = self.window()
        if not self.cols or not self.rows:
            self.cols, self.rows = plausible_columns(lon), plausible_rows(lat)
        else:
            self.cols = {_shift(b, lon, -COLUMN_SHIFT, COLUMN_SHIFT)
                         for b in self.cols}
            self.rows = {_shift(r, lat, -ROW_SHIFT, 1 + ROW_SHIFT)
                         for r in self.rows}
        return self.window() - before

    def witness(self, tlat: int, tlon: int) -> set[Tile]:
        """X-Plane loaded tile ``(tlat, tlon)`` just now: keep only the
        candidates whose window holds it, or, when none does, move ``B`` or
        ``R`` the least distance that makes it so.  Returns the tiles this
        adds to the window (a load the tracker had not predicted)."""
        before = self.window()
        self.cols = _agree(self.cols, tlon - 1, tlon + 2)
        self.rows = _agree(self.rows, tlat - 1, tlat + 1)
        return self.window() - before


def _agree(cands: set[int], lo: int, hi: int) -> set[int]:
    """Candidates within ``[lo, hi]``; else the value(s) of that range
    nearest the candidates (the whole range when there are none)."""
    keep = {c for c in cands if lo <= c <= hi}
    if keep:
        return keep
    if not cands:
        return set(range(lo, hi + 1))
    moved = {c: min(max(c, lo), hi) for c in cands}
    least = min(abs(v - c) for c, v in moved.items())
    return {v for c, v in moved.items() if abs(v - c) == least}

def route_entries(points: Iterable[tuple[float, float]]) -> dict[Tile, int]:
    """Run a tracker along ``points`` ``(lat, lon)`` (a densified route) and
    return, for every tile that is ever in the window, the index of the
    first point at which it enters.  Index 0 is the FIRST WINDOW: the
    union of the plausible windows at the start, so a start near a column
    or row line cannot leave a tile out (spec §8.2)."""
    tracker, first = WindowTracker(), {}
    for i, (lat, lon) in enumerate(points):
        for tile in tracker.update(lat, lon):
            first.setdefault(tile, i)
    return first
