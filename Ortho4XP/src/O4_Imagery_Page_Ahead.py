"""Imagery for the tiles X-Plane will page in NEXT: each square at its
tier before its DSF enters X-Plane's window (#2109).

X-Plane opens a tile's DSF, ``.ter`` files and textures when the tile
enters its window (``O4_World_Window``; World spec 2026-11-10 §2.2), 75 to
150 km before the aircraft reaches the tile.  A file that is on disk then
is what X-Plane draws there with no reload; a texture it already holds is
read again only at a scenery reload (#2106) or, on the step-up read model
of the local-imagery-cache spec §2.5, at the next step up in resolution.
So the follow job lands the squares of the tiles about to enter at the
tier they will want, BEFORE they enter, on top of the step-up crossings
``O4_Imagery_Tier_Plan`` schedules inside the window.

* :func:`straight_path` / :func:`route_path`: the timed path ahead,
  ``[(t, lat, lon)]`` -- the straight track (``O4_World_Ahead.
  track_path``), or a flight plan's route flown at the groundspeed from
  the aircraft's nearest point on it.
* :func:`target_tier`: the finest tier a square wants anywhere along the
  path -- the whole route, or the track flown :data:`PASS_S` beyond the
  horizon, since a tile entering at the horizon is crossed after it:
  tier k when the path passes within ``(CROSSING_S[k] +
  LATERAL_MARGIN_S) * S`` of its centre (horizontal: at the window entry
  the aircraft's height there is unknown, and lower is finer).
* :func:`entries`: when each tile enters the window along the path.
* :func:`plan_ahead`: one ``Fetch`` per square of each entering tile
  that wants more than it has, ``crossing`` 0 (the window entry: the
  first read), deadline the entry less rule S3's margin and the swap
  (``O4_World_Ahead.deadline_s``), and a start time from a backward
  schedule: each fetch starts when the fetches due after it, done one at
  a time at the measured landing times, still finish by their deadlines.
  So a column is landed just in time with one slot; more slots are slack.

Pure: standard library and the planner's constants only; no I/O, no clock.
"""
from __future__ import annotations

import dataclasses
import math
from typing import Iterable, Mapping

import O4_Imagery_Tier_Plan as PLAN
import O4_World_Ahead as AHEAD
import O4_World_Window as WINDOW

__all__ = ["PAGE_HORIZON_S", "PASS_S", "PAGE_CROSSING", "straight_path", "route_path",
           "target_tier", "entries", "plan_ahead"]

#: Seconds of flight ahead whose window entries are planned.  One tile
#: column at 37 N (88 km) is ~12,300 requests at the corridor's tiers,
#: 140-225 s at the measured 55-90 requests/s (#2109); a column enters
#: every 380-1,420 s at 450-120 kt, so the next entry is seen at least
#: 900 s ahead -- four to six times the time it takes.
PAGE_HORIZON_S = 900.0
#: Seconds of track past the horizon a square's tier is judged on: a
#: tile entering at the horizon is flown over up to ~1,800 s later
#: (two tiles' width at 120 kt).
PASS_S = 1800.0
#: The ``crossing`` of a page-ahead fetch: the window entry.
PAGE_CROSSING = 0

_M_PER_DEG = 111_320.0

Tile = tuple[int, int]


def straight_path(motion: PLAN.Motion,
                  horizon_s: float = PAGE_HORIZON_S) -> list:
    """The straight track ahead of ``motion``, timed."""
    return AHEAD.track_path(motion.lat, motion.lon, motion.track_deg,
                            motion.groundspeed_ms, horizon_s)


def _en(lat0: float, lat: float, lon: float) -> tuple[float, float]:
    """Equirectangular metres (east, north) of ``(lat, lon)``, scaled at
    ``lat0``."""
    return (lon * _M_PER_DEG * math.cos(math.radians(lat0)),
            lat * _M_PER_DEG)


def _nearest_on_route(pts, lat0: float, here) -> tuple[int, float]:
    """``(leg, fraction)`` of the route point nearest ``here``."""
    best = (math.inf, 0, 0.0)
    for i, (p, q) in enumerate(zip(pts, pts[1:], strict=False)):
        a, b = _en(lat0, *p), _en(lat0, *q)
        u = _fraction(here, a, b)
        d = math.hypot(a[0] + u * (b[0] - a[0]) - here[0],
                       a[1] + u * (b[1] - a[1]) - here[1])
        if d < best[0]:
            best = (d, i, u)
    return best[1], best[2]


def route_path(samples, motion: PLAN.Motion,
               horizon_s: float = PAGE_HORIZON_S,
               step_m: float = 5_000.0) -> list:
    """A route's ``samples`` ``[(lat, lon)]`` ahead of the aircraft,
    timed at its groundspeed: from the route point nearest the aircraft
    to the end or ``horizon_s``, a point every ``step_m``.  The straight
    track when the route has no leg or the aircraft is parked."""
    pts = [(float(a), float(b)) for a, b in samples or ()]
    v = max(0.0, motion.groundspeed_ms)
    if len(pts) < 2 or v <= 0.0:
        return straight_path(motion, horizon_s)
    lat0 = motion.lat
    i, u = _nearest_on_route(pts, lat0, _en(lat0, motion.lat, motion.lon))
    p, q = pts[i], pts[i + 1]
    legs = [(p[0] + u * (q[0] - p[0]), p[1] + u * (q[1] - p[1]))]
    legs += pts[i + 1:]
    out, t, prev = [(0.0, motion.lat, motion.lon)], 0.0, legs[0]
    for nxt in legs[1:]:
        a, b = _en(lat0, *prev), _en(lat0, *nxt)
        length = math.hypot(b[0] - a[0], b[1] - a[1])
        n = max(1, int(math.ceil(length / step_m)))
        for k in range(1, n + 1):
            t += length / n / v
            f = k / n
            out.append((t, prev[0] + f * (nxt[0] - prev[0]),
                        prev[1] + f * (nxt[1] - prev[1])))
            if t >= horizon_s:
                return out
        prev = nxt
    return out


def _fraction(p, a, b) -> float:
    """Where on segment ``a``-``b`` the point nearest ``p`` lies (0..1)."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    seg = dx * dx + dy * dy
    if seg <= 0:
        return 0.0
    return max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / seg))


def _path_distance(c, pts) -> float:
    """Metres from ``c`` to the polyline ``pts`` (east, north)."""
    if len(pts) == 1:
        return math.hypot(pts[0][0] - c[0], pts[0][1] - c[1])
    best = math.inf
    for a, b in zip(pts, pts[1:], strict=False):
        u = _fraction(c, a, b)
        best = min(best, math.hypot(a[0] + u * (b[0] - a[0]) - c[0],
                                    a[1] + u * (b[1] - a[1]) - c[1]))
    return best


def target_tier(path, sq: PLAN.Square, lat0: float | None = None) -> int:
    """The finest tier ``sq`` wants along ``path`` (``[(t, lat, lon)]``):
    k when the path passes within ``(CROSSING_S[k] + LATERAL_MARGIN_S)
    * S`` of its centre, else 0."""
    if not path:
        return 0
    lat0 = path[0][1] if lat0 is None else lat0
    d = _path_distance(_en(lat0, sq.lat, sq.lon),
                       [_en(lat0, la, lo) for _t, la, lo in path])
    for k in range(len(PLAN.CROSSING_S) - 1, 0, -1):
        if d <= (PLAN.CROSSING_S[k] + PLAN.LATERAL_MARGIN_S) * sq.size_m:
            return k
    return 0


def entries(tracker: WINDOW.WindowTracker, path) -> dict[Tile, float]:
    """``{tile: seconds until it enters}`` X-Plane's window along
    ``path`` (``O4_World_Ahead.path_entries``; ``tracker`` is not moved)."""
    return AHEAD.path_entries(tracker, path)


def _schedule(fetches: list, fetch_s: Mapping[int, float],
              lead_s: float) -> list:
    """The fetches by deadline, each ``start_in_s`` its latest start in a
    one-at-a-time schedule run backward from the last deadline, less
    ``lead_s``."""
    out, next_start = [], math.inf
    for f in sorted(fetches, key=lambda f: (f.deadline_s, f.tier, f.square),
                    reverse=True):
        start = min(f.deadline_s, next_start) - float(fetch_s.get(f.tier, 0.0))
        next_start = start
        out.append(dataclasses.replace(f, start_in_s=start - lead_s))
    out.reverse()
    return out


def plan_ahead(path, entries: Mapping[Tile, float],
               tiles: Mapping[Tile, Iterable[PLAN.Square]],
               on_disk: Mapping[str, int], gs_ms: float, *,
               fetch_s: Mapping[int, float] | None = None,
               lead_s: float = PLAN.DEFAULT_LEAD_S) -> list[PLAN.Fetch]:
    """The page-ahead fetches along ``path`` (the route, or the track
    for :data:`PAGE_HORIZON_S` + :data:`PASS_S`), earliest deadline
    first.

    ``entries`` maps each tile that ENTERS X-Plane's window along the
    path to the seconds until it does (:func:`entries`; a tile held now
    is the step-up planner's); ``tiles`` a tile ``(lat, lon)`` to its
    squares (those the index has); ``on_disk`` a square to the tier it
    has (missing = 0).  ``fetch_s``: seconds to land one file per tier
    (default: the planner's model)."""
    if not entries:
        return []
    fetch_s = dict(fetch_s or {1: 0.3, 2: 1.9, 3: 5.0})
    lat0, here = path[0][1], _en(path[0][1], path[0][1], path[0][2])
    out = []
    for tile, entry_s in entries.items():
        deadline = AHEAD.deadline_s(entry_s, max(gs_ms, 1.0))
        for sq in tiles.get(tile) or ():
            tier = target_tier(path, sq, lat0)
            if tier <= int(on_disk.get(sq.name, 0)):
                continue
            c = _en(lat0, sq.lat, sq.lon)
            out.append(PLAN.Fetch(sq.name, tier, PAGE_CROSSING, deadline, 0.0,
                                  math.hypot(c[0] - here[0], c[1] - here[1]),
                                  False))
    return _schedule(out, fetch_s, lead_s)
