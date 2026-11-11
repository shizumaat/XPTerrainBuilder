"""The flight manager (spec flight-manager-and-world-20261110 §4.3, §6.2,
§8.2, §8.4, §9; lane F1b; capability ``flight_manager``): one flight's
tiles made ready by their deadlines, its readiness rows and countdown.

* :func:`flight_jobs` -- a plan becomes the flight's jobs: the departure,
  destination and (only with the checkbox, RULINGS 2026-11-10g) alternate
  tiles built ``full`` (the user's settings, never interactive) unless a
  ``full`` tile of ours or another pack's mesh (``external``) is already
  there; the corridor (the tiles the route crosses plus those within
  ``corridor_km``, and the departure's and destination's eight
  neighbours) built as the intermediate kind where the World pack holds
  a placeholder (an enabled region, not ``external``, spec §7.2).  Each
  job's deadline comes from where its tile enters X-Plane's DSF window
  along the route (``O4_World_Window.route_entries`` on the densified
  route, ``O4_Flight_Schedule.tile_deadlines``); the first window is P0.
* :class:`FlightManager` -- driven by one position record at a time
  (:meth:`FlightManager.tick`); no I/O of its own.  What it touches is
  passed in, with the same shapes as build-ahead's (``world_job``):
  ``builder`` (``start(tile, kind, deadline_in_s, klass)``,
  ``poll(now)``), ``publisher`` (``settle(tile, kind, held)``),
  ``facts()`` (the readiness facts the engine gathers: World pack,
  budget, network, pre-fetch, X-Plane, the witness's loads),
  ``ground_reload(tiles)`` (rule S6 (a): merge the staged departure and
  first-window tiles over the loaded ones and reload once, on the
  ground).

Lane F2 adds the diversion (:meth:`FlightManager.divert`, spec §8.6,
``flight_divert``), the one reload in the air (rule S6 (b),
``flight_air_reload``), the flight's notices (``flight_notices``) and the
offline waiver (§11, RULINGS 2026-11-10k Q3: en-route tiles that cannot
be built without the internet may be left to X-Plane's own scenery;
never the departure or the destination).

The flight always waits for readiness (10g): ``ready`` is every row of
§6.2 ``done``; the countdown is the schedule's (``O4_Flight_Schedule``)
from the recorded estimates, a dash (None) while a row is blocked.  Once
ready the flight stays ready (§9).  A job that fails twice is ``failed``
(§11: two attempts, never a third).  No airport is named here.
"""
from __future__ import annotations

import math
from dataclasses import replace
from typing import Any, Callable, Dict, Iterable, List, Optional, Tuple

import O4_Flight_Plan as FP
import O4_Flight_Schedule as SCHEDULE
import O4_World_Ahead as AHEAD
import O4_World_Pack as WP
import O4_World_Window as WINDOW

from . import flight_divert as DIVERT
from .flight_air_reload import LOW_AGL_M, NEAR_KM, AirReload
from .flight_notices import Board
from .flight_record import FlightRecord, TileRow

__all__ = ["BUILT_KINDS", "FULL_ROLES", "MAX_ATTEMPTS", "flight_jobs",
           "FlightManager"]

Tile = Tuple[int, int]

#: World-pack kinds that are a built tile (``O4_World_Pack.KINDS`` less
#: the placeholder).
BUILT_KINDS = frozenset({"full", "drape"})
#: Roles built ``full`` (graded airports, the user's settings).
FULL_ROLES = ("departure", "destination", "alternate")
#: Attempts per job (spec §11 convergence guard).
MAX_ATTEMPTS = 2
#: Phases (§9): on the ground under 3 m AGL (``aircraft_watch``); parked
#: under 2 m/s; airborne above 15 m AGL and 25 m/s for 10 s; approach
#: within 40 km of the destination; arrived after 10 min parked there.
ON_GROUND_AGL_M = 3.0
PARKED_MS = 2.0
AIRBORNE_AGL_M = 15.0
AIRBORNE_MS = 25.0
AIRBORNE_HOLD_S = 10.0
APPROACH_KM = 40.0
ARRIVED_KM = 10.0
ARRIVED_PARKED_S = 600.0
#: Swaps are spaced this far apart (§10 Landings).
SWAP_SPACING_S = SCHEDULE.SWAP_S


def _neighbours(tile: Tile) -> List[Tile]:
    lat, lon = tile
    return [(lat + a, ((lon + b + 180) % 360) - 180)
            for a in (-1, 0, 1) for b in (-1, 0, 1)
            if (a, b) != (0, 0) and -90 <= lat + a <= 89]


def _roles(plan: "FP.FlightPlan", tiles: Iterable[Tile],
           build_alternate: bool) -> Dict[Tile, str]:
    """``{tile: role}``: departure, destination, alternate win over
    en route."""
    roles = {tuple(t): "enroute" for t in tiles}
    if build_alternate and plan.alternate is not None:
        roles[FP.tile_of(plan.alternate.lat, plan.alternate.lon)] = "alternate"
    last, first = plan.waypoints[-1], plan.waypoints[0]
    roles[FP.tile_of(last.lat, last.lon)] = "destination"
    roles[FP.tile_of(first.lat, first.lon)] = "departure"
    return roles


def _job_for(role: str, have: Optional[str], intermediate: str
             ) -> Optional[Tuple[str, str]]:
    """``(kind, state)`` of a tile's job, or None when the flight leaves
    it to X-Plane's own scenery (outside the regions, another pack's).
    ``stale`` (``flight_job_run.STALE``): a built tile a pack's package
    changed for — a departure or destination builds again."""
    if have == "stale":
        return ("full", "queued") if role in FULL_ROLES else ("full", "swapped")
    if role in FULL_ROLES:
        if have == "external":
            return "external", "external"
        return ("full", "swapped") if have == "full" else ("full", "queued")
    if have == "placeholder":
        return intermediate, "queued"
    if have in BUILT_KINDS:
        return have, "swapped"
    return None


def flight_jobs(plan: "FP.FlightPlan", *, corridor_km: float,
                build_alternate: bool, cruise_ms: Optional[float],
                intermediate: str, state_of: Callable[[Tile], Optional[str]],
                estimate: Callable[[Tile, str, str], Tuple[float, float]],
                leg: Optional["DIVERT.Leg"] = None
                ) -> Tuple[List["SCHEDULE.Job"], Tuple[list, list]]:
    """The flight's jobs and its route ``(samples, seconds after
    takeoff)`` (see the module).  ``state_of(tile)`` is the World pack's
    word for a tile: ``placeholder``, a built kind, ``external`` or None
    (no placeholder: outside the enabled regions); ``estimate(tile, kind,
    role)`` a ``(lo, hi)`` seconds range.  ``leg`` (a diversion,
    ``flight_divert``): an airborne leg starts at the aircraft
    ``leg.start_s`` after takeoff, with no departure and no first window;
    the diversion airport is built in class P0 (§8.6)."""
    leg = leg or DIVERT.Leg()
    samples, times = SCHEDULE.route_times(plan, cruise_ms)
    times = [t + leg.start_s for t in times]
    speed = (cruise_ms or plan.cruise_ms
             or SCHEDULE.DEFAULT_CRUISE_KT * SCHEDULE.KT_TO_MS)
    first, last = plan.waypoints[0], plan.waypoints[-1]
    corridor = set(FP.route_tiles(plan.points(), corridor_km))
    for end in ((last,) if leg.airborne else (first, last)):
        corridor.update(_neighbours(FP.tile_of(end.lat, end.lon)))
    entries = WINDOW.route_entries(samples)
    deadlines = SCHEDULE.tile_deadlines(times, entries, speed)
    if leg.airborne:            # already in X-Plane's window: due now
        deadlines.update({t: times[0] for t, i in entries.items() if i <= 0})
    roles = _roles(plan, corridor, build_alternate)
    if leg.airborne:
        start = FP.tile_of(first.lat, first.lon)
        if roles.get(start) == "departure":
            roles[start] = "enroute"
    jobs = []
    for tile, role in sorted(roles.items()):
        decided = _job_for(role, state_of(tile), intermediate)
        if decided is None:
            continue
        kind, state = decided
        if (leg.airborne and role == "enroute" and state == "queued"
                and entries.get(tile) == 0):
            state = "late"          # X-Plane holds it already: its own scenery
        klass = SCHEDULE.klass_for(role, entries.get(tile) == 0
                                   and not leg.airborne)
        if leg.diverted and role == "destination":
            klass = SCHEDULE.P0
        jobs.append(SCHEDULE.Job(
            tile=tile, role=role, kind=kind, klass=klass,
            deadline_s=deadlines.get(tile, times[-1]),
            est_s=(tuple(estimate(tile, kind, role)) if state == "queued"
                   else (0.0, 0.0)),
            state=state, off_route_km=FP.off_route_km(samples, tile)))
    return jobs, (samples, times)


class FlightManager:
    """One flight being prepared and flown (see the module)."""

    def __init__(self, record: FlightRecord, plan: "FP.FlightPlan", *,
                 builder, publisher, facts: Callable[[], dict],
                 state_of: Callable[[Tile], Optional[str]],
                 estimate: Callable[[Tile, str, str], Tuple[float, float]],
                 intermediate: str = "drape", parked_slots: int = 1,
                 flight_slots: int = 1,
                 ground_reload: Callable[[List[Tile]], bool] = lambda t: False,
                 stamp: Callable[[], str] = lambda: "") -> None:
        self.record, self.plan = record, plan
        self.builder, self.publisher, self.facts = builder, publisher, facts
        self.state_of, self.estimate = state_of, estimate
        self.intermediate = intermediate
        self.parked_slots = max(1, int(parked_slots))
        self.flight_slots = max(1, int(flight_slots))
        self.ground_reload, self.stamp = ground_reload, stamp
        self.departure = plan.waypoints[0]
        self.leg = DIVERT.Leg()
        self.air = AirReload()
        self.board = Board()
        self.diverted_to = ""
        self.diversions = 0
        self.waive_offline = False
        self.waivable: Tuple[Tile, ...] = ()
        self.agl_m: Optional[float] = None
        self._km_offset = 0.0
        self.tracker = WINDOW.WindowTracker()
        self.position: Optional[Tuple[float, float]] = None
        self.gs_ms = 0.0
        self.takeoff_at: Optional[float] = None     # manager clock seconds
        self.reload = ""
        self.countdown_s: Optional[float] = None
        self.items: List["SCHEDULE.Item"] = []
        self.reason = ""
        self.jobs: List["SCHEDULE.Job"] = []
        self._runs: Dict[Tile, dict] = {}            # attempts, times, point
        self._finished: set = set()
        self._seen: set = set()
        self._swap_at = -math.inf
        self._airborne_since: Optional[float] = None
        self._parked_since: Optional[float] = None
        self.replan()

    # ------------------------------------------------------------ plan

    def _plan_jobs(self) -> List["SCHEDULE.Job"]:
        jobs, (self.samples, self.times) = flight_jobs(
            self.plan, corridor_km=self.record.corridor_km,
            build_alternate=self.record.build_alternate,
            cruise_ms=self.record.profile.get("cruise_ms"),
            intermediate=self.intermediate, state_of=self.state_of,
            estimate=self.estimate, leg=self.leg)
        self._km = [self._km_offset]
        for a, b in zip(self.samples, self.samples[1:], strict=False):
            self._km.append(self._km[-1] + FP.route_length_km([a, b]))
        return jobs

    def replan(self) -> None:
        """(Re)make the jobs from the record's choices; a tile already
        started, built or failed keeps its state (``flight_update``); a
        build under way or staged that the new plan no longer lists
        stays to be published."""
        old = {j.tile: j for j in self.jobs}
        kept = []
        for job in self._plan_jobs():
            prior = old.pop(job.tile, None)
            if (prior is not None and prior.kind == job.kind
                    and prior.state not in ("queued", "late")):
                job = replace(job, state=prior.state, est_s=prior.est_s)
            kept.append(job)
        kept += [j for _t, j in sorted(old.items())
                 if j.state in ("building", "staged")]
        self.jobs = kept

    def divert(self, now: float, target: "FP.Waypoint",
               is_alternate: bool, cancel: Callable[[Tile], Any] = None
               ) -> str:
        """Spec §8.6 (``flight_divert``): ``target`` replaces the
        destination; its tile is built ``full`` in class P0; the leg is
        planned again from the aircraft (in the air) or the departure;
        the old destination's build stops at its next step boundary
        (``cancel(tile)``) unless the new leg still needs it.  Returns
        the name the status shows (``diverted_to``)."""
        last = self.plan.waypoints[-1]
        old_destination = FP.tile_of(last.lat, last.lon)
        flown = None if self.takeoff_at is None else now - self.takeoff_at
        self._km_offset = self._done_km() if flown is not None else 0.0
        self.plan, self.leg = DIVERT.divert_leg(
            self.plan, target, self.position, flown, is_alternate)
        if is_alternate:
            self.record.build_alternate = False
        self.jobs = DIVERT.merge_after_divert(
            self.jobs, self._plan_jobs(), old_destination,
            cancel or (lambda tile: None))
        name = target.ident or "%.4f, %.4f" % (target.lat, target.lon)
        self.record.notes.append({"diverted_to": name, "from": last.ident,
                                  "at": self.stamp(), "alternate": is_alternate})
        self.record.destination = {"ident": target.ident, "lat": target.lat,
                                   "lon": target.lon}
        if self.air.state != "sent":
            self.air = AirReload()
        self.diverted_to, self.diversions = name, self.diversions + 1
        return name

    def _set(self, tile: Tile, **changes) -> None:
        self.jobs = [replace(j, **changes) if j.tile == tile else j
                     for j in self.jobs]

    def _job(self, tile: Tile) -> Optional["SCHEDULE.Job"]:
        return next((j for j in self.jobs if j.tile == tile), None)

    # ------------------------------------------------------------ tick

    def tick(self, now: float, rec: Optional[dict]) -> None:
        """One cycle at manager-clock ``now`` (seconds) with the position
        record ``rec`` (``lat``, ``lon``, ``agl_m``, ``gs_ms``; ``None``:
        X-Plane does not answer)."""
        facts = dict(self.facts() or {})
        self._move(now, rec, facts)
        self._harvest(now)
        self._settle(now, facts)
        self._air_reload(now)
        if self.record.state in ("preparing", "ready", "flying"):
            self._mark_late(now)
            self._dispatch(now)
        self._offline(facts)
        was = self.record.state
        self._readiness(now, facts)
        self._notices(was)

    def _move(self, now: float, rec: Optional[dict], facts: dict) -> None:
        for tile in set(facts.get("loads") or ()) - self._seen:
            self._seen.add(tile)
            self.tracker.witness(*tile)
        if rec is None:
            self.record.phase = ""
            self.position = None
            return
        lat, lon = float(rec["lat"]), float(rec["lon"])
        self.tracker.update(lat, lon)
        self.position = (lat, lon)
        self.gs_ms = float(rec.get("gs_ms") or 0.0)
        agl = rec.get("agl_m")
        self.agl_m = None if agl is None else float(agl)
        self.record.phase = self._phase(now, rec)

    def _phase(self, now: float, rec: dict) -> str:
        """§9's phases; moves ``state`` at takeoff and arrival."""
        agl = rec.get("agl_m")
        ground = agl is None or float(agl) < ON_GROUND_AGL_M
        dest = self.plan.waypoints[-1]
        to_dest = FP.route_length_km([self.position, (dest.lat, dest.lon)])
        up = (agl is not None and float(agl) > AIRBORNE_AGL_M
              and self.gs_ms > AIRBORNE_MS)
        self._airborne_since = (
            (now if self._airborne_since is None else self._airborne_since)
            if up else None)
        if (self.takeoff_at is None and self._airborne_since is not None
                and now - self._airborne_since >= AIRBORNE_HOLD_S):
            self.takeoff_at = self._airborne_since
            self.record.departed_at = self.stamp()
            if self.record.state in ("preparing", "ready"):
                self.record.state = "flying"
        if not ground:
            self._parked_since = None
            if self.takeoff_at is None:
                return "taxi"
            return "approach" if to_dest <= APPROACH_KM else "airborne"
        parked = self.gs_ms < PARKED_MS
        self._parked_since = (
            (now if self._parked_since is None else self._parked_since)
            if parked else None)
        if self.takeoff_at is None:
            return "parked" if parked else "taxi"
        if (parked and to_dest <= ARRIVED_KM and self.record.state == "flying"
                and now - self._parked_since >= ARRIVED_PARKED_S):
            self.record.state, self.record.arrived_at = "arrived", self.stamp()
        return "landed"

    # ---------------------------------------------------------- builds

    def _harvest(self, now: float) -> None:
        for tile, ok in self.builder.poll(now):
            tile = tuple(tile)
            job, run = self._job(tile), self._runs.get(tile)
            if job is None or job.state != "building" or run is None:
                continue
            run["finished_at"] = now
            if ok:
                self._finished.add(tile)
                self.jobs = SCHEDULE.rescale(self.jobs, job.kind,
                                             now - run["started_at"],
                                             run["point"])
            elif run["attempts"] >= MAX_ATTEMPTS:
                self._set(tile, state="failed")
            else:
                self._set(tile, state="queued")

    def held(self, tile: Tile, facts: dict) -> bool:
        """Rule S3 (``O4_World_Ahead.held``); never while X-Plane does
        not run."""
        if not facts.get("xplane_running"):
            return False
        return AHEAD.held(self.tracker, self.position, self.gs_ms, tile,
                          self._seen)

    def _settle(self, now: float, facts: dict) -> None:
        """Stage and swap finished tiles, one swap per spacing."""
        waiting = [j for j in self.jobs
                   if j.tile in self._finished or j.state == "staged"]
        for job in sorted(waiting, key=lambda j: (j.deadline_s, j.tile)):
            held = (self.held(job.tile, facts)
                    or now - self._swap_at < SWAP_SPACING_S)
            state = self.publisher.settle(job.tile, job.kind, held)
            if state == "pending":
                continue
            self._finished.discard(job.tile)
            if state == "swapped":
                self._swap_at = now
                self._runs.setdefault(job.tile, {})["swapped_at"] = now
            self._set(job.tile, state=state)

    def _takeoff_s(self, now: float) -> float:
        """Takeoff on the manager clock: as flown, else now plus the
        countdown (the wait the pilot is told)."""
        if self.takeoff_at is not None:
            return self.takeoff_at
        wait = self.countdown_s
        if wait is None:            # before the first readiness pass
            wait = SCHEDULE.countdown(self._live_jobs(now), self.parked_slots,
                                      self.flight_slots)
        return now + (wait or 0.0)

    def _mark_late(self, now: float) -> None:
        """In flight, an en-route tile whose deadline passed before it was
        started loads as X-Plane's own scenery: ``late``, never built (the
        destination is never given up, §8.4)."""
        if self.takeoff_at is None:
            return
        for job in self.jobs:
            if (job.state == "queued" and job.role == "enroute"
                    and self.takeoff_at + job.deadline_s < now):
                self._set(job.tile, state="late")

    def slots(self) -> int:
        """Builds that may run now (§10): the flight capacity in the air,
        the parked capacity while preparing."""
        if self.takeoff_at is not None:
            return self.flight_slots
        return self.parked_slots

    def _dispatch(self, now: float) -> None:
        running = sum(1 for j in self.jobs if j.state == "building")
        takeoff = self._takeoff_s(now)
        refused: set = set()
        while running < self.slots():
            job = SCHEDULE.next_job([j for j in self.jobs
                                     if j.tile not in refused], now, takeoff)
            if job is None:
                return
            due = takeoff + job.deadline_s - now
            if not self.builder.start(job.tile, job.kind, due,
                                      "P%d" % job.klass):
                refused.add(job.tile)
                continue
            run = self._runs.setdefault(job.tile, {"attempts": 0})
            run.update(started_at=now,
                       point=math.sqrt(job.est_s[0] * job.est_s[1]))
            run["attempts"] = run.get("attempts", 0) + 1
            self._set(job.tile, state="building")
            running += 1

    def _remaining(self, job, now: float) -> Tuple[float, float]:
        run = self._runs.get(job.tile) or {}
        if job.state != "building" or "started_at" not in run:
            return job.est_s
        gone = now - run["started_at"]
        return (max(0.0, job.est_s[0] - gone), max(0.0, job.est_s[1] - gone))

    # ------------------------------------------------------- readiness

    def _live_jobs(self, now: float) -> List["SCHEDULE.Job"]:
        """The jobs with their remaining estimates (a building job's
        elapsed time taken off: §9 "from the real progress")."""
        return [replace(j, remaining_s=self._remaining(j, now))
                for j in self.jobs]

    def flight_loaded(self) -> bool:
        """Does X-Plane stand with the departure in its window (a flight
        loaded there)?"""
        if self.position is None:
            return False
        first = self.departure
        return WINDOW.reach(*self.position, *FP.tile_of(first.lat, first.lon),
                            tracker=self.tracker)["in_window"]

    def _loaded_real(self) -> bool:
        """Will X-Plane read the real departure and first-window tiles?
        Not while one of them waits staged: X-Plane holds its placeholder
        (rule S3 refused the swap), so only a reload reads it (S6 (a))."""
        return not any(j.klass == SCHEDULE.P0 and j.state == "staged"
                       and j.role in ("departure", "enroute")
                       for j in self.jobs)

    def _readiness(self, now: float, facts: dict) -> None:
        jobs = self._live_jobs(now)
        known = {k: facts[k] for k in (
            "world_installed", "world_seen", "xplane_running", "budget_fits",
            "budget_detail", "network_ok", "all_on_disk", "prefetch_done",
            "network_detail")
            if facts.get(k) is not None}
        self.items = SCHEDULE.readiness_items(SCHEDULE.Facts(
            jobs=tuple(jobs), slots=self.slots(), flight_slots=self.flight_slots,
            build_alternate=self.record.build_alternate,
            flight_loaded=self.flight_loaded(),
            loaded_real=self._loaded_real(),
            **known))
        self._maybe_reload(now)
        if (self.record.state == "preparing"
                and all(item.state == "done" for item in self.items)):
            self.record.state, self.record.ready_at = "ready", self.stamp()
        self.countdown_s = self._countdown(jobs)
        self.reason = next((i.detail for i in self.items
                            if i.state in ("blocked", "failed") and i.detail),
                           "")
        late = sum(1 for j in self.jobs if j.state == "late")
        if late and not self.reason:
            self.reason = ("Building is behind: %d tile(s) ahead will show "
                           "X-Plane's own scenery." % late)

    def _countdown(self, jobs) -> Optional[float]:
        """§9's countdown; 0 once ready; None (a dash) while a row is
        blocked or a job has no estimate."""
        if self.record.state != "preparing":
            return 0.0
        if any(i.state in ("blocked", "failed") for i in self.items):
            return None
        wait = SCHEDULE.countdown(jobs, self.parked_slots, self.flight_slots)
        if wait is None:
            return None
        return max([wait] + [i.eta_s for i in self.items
                             if i.state != "done" and i.eta_s is not None])

    def _maybe_reload(self, now: float) -> None:
        """Rule S6 (a): ``loaded`` is the last row; with every other row
        done and the aircraft on the ground, the staged departure and
        first-window tiles go in (merged, S5) and X-Plane reloads once."""
        loaded = next((i for i in self.items if i.key == "loaded"), None)
        if self.takeoff_at is not None:        # S6 (a) is on the ground only
            self.reload = ""
            return
        if loaded is None or loaded.state == "done":
            if self.reload == "ground_pending":
                self.reload = ""
            return
        self.reload = "ground_pending"
        others = all(i.state == "done" for i in self.items
                     if i.key != "loaded")
        if not others or self.record.phase not in ("parked", ""):
            return
        tiles = [j.tile for j in self.jobs if j.klass == SCHEDULE.P0
                 and j.state == "staged" and j.role in ("departure", "enroute")]
        if not self.ground_reload(tiles):
            return
        self.reload = "sent"
        self.board.post("reloading_on_ground")
        for tile in tiles:
            self._runs.setdefault(tile, {})["swapped_at"] = now
            self._set(tile, state="swapped")
        self.items = [i._replace(state="done", eta_s=0.0, detail="")
                      if i.key == "loaded" else i for i in self.items]

    # ------------------------------------------- S6 (b), offline, notices

    def _destination(self) -> Tuple["FP.Waypoint", Optional["SCHEDULE.Job"]]:
        last = self.plan.waypoints[-1]
        job = self._job(FP.tile_of(last.lat, last.lon))
        return last, (job if job is not None and job.role == "destination"
                      else None)

    def _air_reload(self, now: float) -> None:
        """Rule S6 (b) (``flight_air_reload``): the destination waits
        staged because X-Plane loaded its area; near the ground, the one
        reload of the flight is announced, then sent unless "Not now"."""
        if self.takeoff_at is None:
            return
        last, job = self._destination()
        needed = job is not None and job.state == "staged"
        if needed:
            self.board.post("destination_late", key=self.diversions,
                            destination=last.ident)
        near = (self.position is not None and self.agl_m is not None
                and self.agl_m < LOW_AGL_M
                and FP.route_length_km([self.position, (last.lat, last.lon)])
                <= NEAR_KM)
        action = self.air.step(now, needed, near)
        if action == "announce":
            self.board.post("reload_announced", key=self.diversions,
                            destination=last.ident)
        elif action == "send":
            self._send_air_reload(now, job.tile)

    def _send_air_reload(self, now: float, tile: Tile) -> bool:
        if not self.ground_reload([tile]):
            return False
        self.air.sent()
        self._runs.setdefault(tile, {})["swapped_at"] = now
        self._set(tile, state="swapped")
        return True

    def reload_now(self, now: float) -> bool:
        """``flight_reload``: the pilot asks for the offered reload (in
        the air, rule S6 (b)); False when none is offered."""
        _last, job = self._destination()
        if (self.takeoff_at is None or job is None or job.state != "staged"
                or not self.air.press()):
            return False
        return self._send_air_reload(now, job.tile)

    def not_now(self) -> bool:
        """``flight_reload {not_now: true}``: the announced reload waits
        until the pilot asks for it."""
        return self.air.not_now()

    def _offline(self, facts: dict) -> None:
        """§11 / RULINGS 2026-11-10k Q3: corridor tiles whose map data or
        elevation could not be fetched (``facts["offline_tiles"]``).  With
        the pilot's waiver, en-route ones are left to X-Plane's own
        scenery (shed) and the network row is done; the departure and
        destination are never waived."""
        missing = {tuple(t) for t in facts.get("offline_tiles") or ()}
        roles = {j.tile: j.role for j in self.jobs}
        enroute = tuple(sorted(t for t in missing
                               if roles.get(t) in ("enroute", "alternate")))
        vital = [t for t in missing
                 if roles.get(t) in ("departure", "destination")]
        if not missing:
            self.waivable = ()
            return
        if self.waive_offline and not vital:
            for tile in enroute:
                job = self._job(tile)
                if job is not None and job.state in ("queued", "late"):
                    self._set(tile, state="shed")
            facts.update(network_ok=True, prefetch_done=True)
            self.waivable = ()
            return
        self.waivable = () if vital else enroute
        facts["network_detail"] = (
            "Needs internet for the departure or destination" if vital
            else "Needs internet for %d tile(s) en route" % len(enroute))
        if enroute and not vital:
            self.board.post("offline", key=len(enroute), count=len(enroute))

    def waive(self) -> int:
        """The pilot's "Fly with X-Plane's own scenery there"; the tiles
        it covers."""
        self.waive_offline = True
        self.record.notes.append({"offline_waived": [
            WP.tile_name(*t) for t in self.waivable], "at": self.stamp()})
        return len(self.waivable)

    def _notices(self, was: str) -> None:
        """The one-shot ``FlightNotice`` codes (``flight_notices``)."""
        last, job = self._destination()
        dest = last.ident or self.diverted_to
        if was == "preparing" and self.record.state == "ready":
            self.board.post("ready", origin=self.departure.ident,
                            destination=dest)
        if (job is not None and job.state == "swapped"
                and self.record.state in ("ready", "flying")):
            margin = None
            run = self._runs.get(job.tile, {})
            if "swapped_at" in run and self.takeoff_at is not None:
                margin = self.takeoff_at + job.deadline_s - run["swapped_at"]
            if self.leg.diverted:
                self.board.post("diversion_ready", key=self.diversions,
                                destination=dest)
            elif job.est_s != (0.0, 0.0):       # built for this flight
                self.board.post("destination_ready", destination=dest,
                                margin_s=margin)
        late = sum(1 for j in self.jobs if j.state == "late")
        if late:
            self.board.post("tile_late", key=late, count=late)
        budget = next((i for i in self.items if i.key == "budget"), None)
        if budget is not None and budget.state == "blocked":
            self.board.post("budget", detail=budget.detail)
        if was != "arrived" and self.record.state == "arrived":
            self.board.post("arrived", destination=dest)

    def notices(self) -> List[dict]:
        """The notices posted since the last call (the runner emits each
        as a ``FlightNotice``)."""
        return self.board.drain()

    # ---------------------------------------------------------- status

    def _done_km(self) -> float:
        if self.position is None or self.takeoff_at is None:
            return 0.0
        best = min(range(len(self.samples)), key=lambda i: FP.route_length_km(
            [self.position, self.samples[i]]))
        return self._km[best]

    def _eta_s(self, now: float) -> Optional[float]:
        if not self.times:
            return None
        if self.takeoff_at is None:
            return round(self.times[-1], 1)
        return round(max(0.0, self.takeoff_at + self.times[-1] - now), 1)

    def _job_row(self, job, ends: Dict[Tile, float], now: float) -> list:
        takeoff = self._takeoff_s(now)
        run = self._runs.get(job.tile, {})
        if "swapped_at" in run:
            margin = takeoff + job.deadline_s - run["swapped_at"]
        elif job.tile in ends:
            margin = takeoff + job.deadline_s - (now + ends[job.tile])
        else:
            margin = None
        remaining = (0.0 if job.state in SCHEDULE.DONE_STATES
                     else self._remaining(job, now)[1])
        return [list(job.tile), job.role, job.kind, job.state,
                round(remaining, 1),
                None if margin is None else round(margin, 1)]

    def status(self, now: float) -> dict:
        """The ``FlightStatus`` fields (spec §5.3)."""
        live = self._live_jobs(now)
        ends = {j.tile: end
                for j, end in SCHEDULE.finish_times(live, self.slots())}
        wait = 0.0 if self.takeoff_at is not None else (self.countdown_s or 0.0)
        shed = SCHEDULE.shed_order(live, self.slots(), wait)
        return {
            "flight": self.record.id, "state": self.record.state,
            "phase": self.record.phase,
            "ready": self.record.state in ("ready", "flying", "arrived"),
            "countdown_s": (None if self.countdown_s is None
                            else round(self.countdown_s, 1)),
            "reason": self.reason,
            "items": tuple([i.key, i.state,
                            None if i.eta_s is None else round(i.eta_s, 1),
                            i.detail] for i in self.items),
            "jobs": tuple(self._job_row(j, ends, now) for j in live),
            "route_km": round(self._km[-1], 1),
            "done_km": round(self._done_km(), 1),
            "eta_s": self._eta_s(now),
            "late": tuple(WP.tile_name(*j.tile) for j in self.jobs
                          if j.state == "late"),
            "shed": tuple(WP.tile_name(*j.tile) for j in shed),
            "reload": self.reload if self.takeoff_at is None else self.air.state,
            "diverted_to": self.diverted_to,
            "waivable": tuple(WP.tile_name(*t) for t in self.waivable),
        }

    def record_tiles(self) -> List[TileRow]:
        """The record's ``tiles`` (§6.1), with what each took (manager
        clock seconds after the flight was created)."""
        rows = []
        for job in self.jobs:
            run = self._runs.get(job.tile, {})
            rows.append(TileRow(
                tile=list(job.tile), role=job.role, kind=job.kind,
                state=job.state, deadline_s=round(job.deadline_s, 1),
                est_s=[round(job.est_s[0], 1), round(job.est_s[1], 1)],
                started_at=_clock_text(run.get("started_at")),
                finished_at=_clock_text(run.get("finished_at")),
                swapped_at=_clock_text(run.get("swapped_at")),
                late=job.state == "late"))
        return rows


def _clock_text(value: Optional[float]) -> Optional[str]:
    """A manager-clock second as the record keeps it."""
    return None if value is None else "%+.0fs" % value
