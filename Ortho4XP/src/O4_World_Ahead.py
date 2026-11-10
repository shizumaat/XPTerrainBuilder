"""Which tiles enter X-Plane's DSF window next, and by when they must be in
place: build-ahead's planning without a route (flight manager / World spec
2026-11-10, §8.5 free flight, §7.5 S3, §2.2).

* :func:`_track_entries` runs a copy of the window tracker
  (``O4_World_Window.WindowTracker``) along the straight track from the
  aircraft for ``horizon_s`` seconds and returns, for every tile that
  enters on the way, the seconds until it enters.
* :func:`ahead` adds the turn margin: while the track turns faster than
  :data:`TURN_RATE_DEG_S`, the same run along the track turned
  :data:`TURN_DEG` toward the turn (one row and column toward it).
* :func:`ring` is the parked case (no track to run): the tiles that enter
  on the window's next move in ANY direction, with the km the aircraft
  has to go before each would enter (``O4_World_Window.reach``).
* :func:`held` is rule S3's verdict for one tile now (witnessed, in the
  window, or within the margin of entering it).
* :func:`deadline_s` is an entry time less rule S3's margin
  (:func:`_margin_s`: 0.05° or 60 s of flight, whichever is more) and the
  swap (:data:`SWAP_S`).

Pure: standard library and ``O4_World_Window`` only, no I/O, no clock.
"""
from __future__ import annotations

import math

import O4_World_Window as WINDOW

__all__ = ["MARGIN_DEG", "MARGIN_S", "SWAP_S", "STEP_S", "TURN_DEG",
           "TURN_RATE_DEG_S", "margin_km", "held", "deadline_s", "ahead", "ring"]

#: Rule S3: a tile is swapped only this far outside the window ...
MARGIN_DEG = 0.05
#: ... or this many seconds of flight from entering it, whichever is more.
MARGIN_S = 60.0
#: Seconds a swap takes (0.47 s measured on the CYYR flight, §2.1; the
#: stage step is part of the build's estimate), rounded up.
SWAP_S = 5.0
#: Seconds between the points of a projected track.
STEP_S = 10.0
#: The turn margin: the track turned this far toward the turn ...
TURN_DEG = 30.0
#: ... while it turns faster than this (a standard-rate turn is 3°/s).
TURN_RATE_DEG_S = 0.5
_M_PER_DEG = 111_320.0

Tile = tuple[int, int]


def margin_km(gs_ms: float) -> float:
    """Rule S3's margin in km at ``gs_ms``: 0.05° or 60 s of flight,
    whichever is more."""
    return max(MARGIN_DEG * _M_PER_DEG, max(gs_ms, 0.0) * MARGIN_S) / 1000.0


def held(tracker: WINDOW.WindowTracker, position, gs_ms: float, tile: Tile,
         seen=()) -> bool:
    """Rule S3: may X-Plane hold ``tile`` now -- witnessed (``seen``), in
    the window, or within :func:`margin_km` of entering it?  An unknown
    ``position`` (``None``) answers yes."""
    if tile in seen or position is None:
        return True
    where = WINDOW.reach(*position, *tile, tracker=tracker)
    return where["in_window"] or where["km_to_load"] < margin_km(gs_ms)


def _margin_s(gs_ms: float) -> float:
    """Rule S3's margin in seconds of flight at ``gs_ms`` (> 0)."""
    return margin_km(gs_ms) * 1000.0 / gs_ms


def deadline_s(entry_s: float, gs_ms: float) -> float:
    """Seconds from now by which a tile entering in ``entry_s`` must be
    built and staged: its entry less the S3 margin and the swap."""
    return entry_s - _margin_s(gs_ms) - SWAP_S


def _step(lat: float, lon: float, track_deg: float,
          metres: float) -> tuple[float, float]:
    """``(lat, lon)`` ``metres`` along ``track_deg`` (flat earth; the steps
    are short)."""
    rad = math.radians(track_deg)
    north, east = metres * math.cos(rad), metres * math.sin(rad)
    cos_lat = max(math.cos(math.radians(lat)), 1e-6)
    return lat + north / _M_PER_DEG, lon + east / (_M_PER_DEG * cos_lat)


def _copy(tracker: WINDOW.WindowTracker) -> WINDOW.WindowTracker:
    twin = WINDOW.WindowTracker()
    twin.cols, twin.rows = set(tracker.cols), set(tracker.rows)
    return twin


def _track_entries(tracker: WINDOW.WindowTracker, lat: float, lon: float,
                  track_deg: float, gs_ms: float, horizon_s: float,
                  step_s: float = STEP_S) -> dict[Tile, float]:
    """``{tile: seconds until it enters}`` along the straight track from
    ``(lat, lon)`` at ``gs_ms`` for ``horizon_s``.  ``tracker`` (the live
    window) is copied, never moved; an unknown history starts from the
    union at ``(lat, lon)``."""
    twin = _copy(tracker)
    if not twin.cols or not twin.rows:
        twin.update(lat, lon)
    out: dict[Tile, float] = {}
    if gs_ms <= 0 or horizon_s <= 0:
        return out
    t = 0.0
    while t < horizon_s:
        dt = min(step_s, horizon_s - t)
        t += dt
        lat, lon = _step(lat, lon, track_deg, gs_ms * dt)
        for tile in twin.update(lat, lon):
            out.setdefault(tile, t)
    return out


def ahead(tracker: WINDOW.WindowTracker, lat: float, lon: float,
          track_deg: float, gs_ms: float, horizon_s: float,
          turn_deg_s: float = 0.0) -> dict[Tile, float]:
    """:func:`_track_entries` plus the turn margin (see the module): a tile
    seen on both runs keeps the earlier entry."""
    out = _track_entries(tracker, lat, lon, track_deg, gs_ms, horizon_s)
    if abs(turn_deg_s) > TURN_RATE_DEG_S:
        turned = track_deg + math.copysign(TURN_DEG, turn_deg_s)
        for tile, t in _track_entries(tracker, lat, lon, turned, gs_ms,
                                     horizon_s).items():
            out[tile] = min(t, out.get(tile, t))
    return out


def ring(tracker: WINDOW.WindowTracker, lat: float,
         lon: float) -> dict[Tile, float]:
    """``{tile: km before it would enter}`` for the tiles the window takes
    in on its next move in any direction (the window's columns and rows
    widened by one each side, less the window)."""
    cols = tracker.cols or WINDOW.plausible_columns(lon)
    rows = tracker.rows or WINDOW.plausible_rows(lat)
    held = WINDOW.window_tiles(cols, rows)
    wider = WINDOW.window_tiles({c + d for c in cols for d in (-1, 0, 1)},
                                {r + d for r in rows for d in (-1, 0, 1)})
    return {tile: WINDOW.reach(lat, lon, *tile)["km_to_load"]
            for tile in wider - held}
