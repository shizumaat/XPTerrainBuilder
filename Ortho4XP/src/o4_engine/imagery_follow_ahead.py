"""The follow job's page-ahead: X-Plane's DSF window kept from the camera
feed, and the squares of the tiles about to enter it fetched before they
do (#2109, ``O4_Imagery_Page_Ahead``).

:class:`PageAhead` keeps an ``O4_World_Window.WindowTracker``: a flight
load or camera jump (the follow job's spawn witnesses) loads it at the
new place, a session's first position starts it from every plausible
window, and each later position moves it.  :meth:`PageAhead.fetches`
plans, at most every :data:`PLAN_EVERY_S`, the squares of the tiles that
enter along the path ahead -- the active flight plan's route
(``flight_imagery_route.active``) when there is one, else the straight
track -- and keeps the answer between plans, less what has landed since.
:func:`merge` puts them among the step-up planner's fetches by deadline.
"""
from __future__ import annotations

import math

import O4_File_Names as FNAMES
import O4_Imagery_Page_Ahead as PAGE
import O4_Imagery_Tier_Plan as PLAN
import O4_World_Window as WINDOW

__all__ = ["PLAN_EVERY_S", "PageAhead", "merge"]

#: Seconds between two page-ahead plans (the window moves at most once a
#: few minutes; a plan reads a few hundred squares).
PLAN_EVERY_S = 5.0


def _active_route():
    """The running flight's densified route ``[(lat, lon)]``, or ``None``
    (``flight_imagery_route.active``)."""
    from .flight_imagery_route import active
    split = active()
    return split.samples if split is not None else None


class PageAhead:
    """The window and the page-ahead plan of one follow session.
    ``route()`` returns the route to follow, or ``None`` for the track."""

    def __init__(self, route=_active_route) -> None:
        self.window = WINDOW.WindowTracker()
        self.route = route
        self._at = -math.inf
        self._fetches: list[PLAN.Fetch] = []

    def locate(self, kind: str, lat: float, lon: float) -> None:
        """One camera position; ``kind`` the spawn witness it is
        (``"spawn"``: history unknown; ``"flight_load"`` / ``"jump"``:
        X-Plane loaded the scenery here; ``""``: flying on)."""
        if kind == "spawn":
            self.window.forget()
        elif kind in ("flight_load", "jump"):
            self.window.load(lat, lon)
        if kind:
            self._at = -math.inf            # plan again at once
        self.window.update(lat, lon)

    def describe(self) -> str:
        """``"B,R"`` of the window (``?`` while its history is unknown)."""
        if not self.window.known():
            return "?"
        return f"{next(iter(self.window.cols))},{next(iter(self.window.rows))}"

    def _path(self, motion: PLAN.Motion) -> tuple[list, list]:
        """``(timed path, the path a square's tier is judged on)``: the
        route ahead, or the straight track (judged on its two ends: the
        same line, read in two steps instead of 270)."""
        try:
            samples = self.route() if self.route is not None else None
        except Exception:                   # no flight state: the track
            samples = None
        if samples:
            path = PAGE.route_path(samples, motion, math.inf)
            return path, path
        path = PAGE.straight_path(motion, PAGE.PAGE_HORIZON_S + PAGE.PASS_S)
        return path, [path[0], path[-1]]

    def fetches(self, now: float, motion: PLAN.Motion | None, rows: dict,
                tiles: dict, skip, *, fetch_s=None,
                lead_s: float = PLAN.DEFAULT_LEAD_S) -> list[PLAN.Fetch]:
        """The page-ahead fetches now: ``rows`` the index rows by key,
        ``tiles`` their ``Follow_Reach.by_tile`` boxes, ``skip(key)``
        true for a square another plan or a failure owns."""
        if motion is None or motion.groundspeed_ms <= 0.5:
            self._fetches = []
            return []
        if now - self._at >= PLAN_EVERY_S:
            self._at = now
            self._fetches = self._plan(motion, rows, tiles, fetch_s, lead_s)
        return [f for f in self._fetches
                if f.square in rows and not skip(f.square)
                and PLAN.tier_of_width(rows[f.square]["tier_px"]) < f.tier]

    def _plan(self, motion, rows, tiles, fetch_s, lead_s):
        path, judged = self._path(motion)
        entries = PAGE.entries(self.window, [
            p for p in path if p[0] <= PAGE.PAGE_HORIZON_S])
        squares, on_disk = {}, {}
        for tile in entries:
            box = tiles.get(FNAMES.short_latlon(*tile))
            if box is None:
                continue
            for key in box[5]:
                row = rows.get(key)
                if row is None:
                    continue
                squares.setdefault(tile, []).append(PLAN.Square(
                    key, row["centre_lat"], row["centre_lon"],
                    row["load_size_m"]))
                on_disk[key] = PLAN.tier_of_width(row["tier_px"])
        return PAGE.plan_ahead(judged, entries, squares, on_disk,
                               motion.groundspeed_ms, fetch_s=fetch_s,
                               lead_s=lead_s)


def merge(planned: list, ahead: list) -> list:
    """The step-up planner's ``planned`` fetches with ``ahead`` among its
    on-time ones by deadline (a square the planner lists keeps the
    planner's); its late ones last, as it ordered them."""
    listed = {f.square for f in planned}
    ahead = [f for f in ahead if f.square not in listed]
    if not ahead:
        return planned
    on_time = [f for f in planned if not f.late] + ahead
    on_time.sort(key=lambda f: (f.deadline_s, f.tier, f.square))
    return on_time + [f for f in planned if f.late]
