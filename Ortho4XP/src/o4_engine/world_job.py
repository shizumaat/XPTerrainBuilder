"""Build-ahead in track mode: tiles about to enter X-Plane's DSF window are
built and swapped into the World pack before they load (flight manager /
World spec 2026-11-10, §8.5 free flight, §7.5, §10; capability
``world_job``).

:class:`WorldJob` is the job's logic, driven by one position record at a
time (:meth:`WorldJob.tick`); it does no I/O of its own.  What it touches
is passed in:

* ``builder`` -- ``start(tile, kind, deadline_in_s, klass)`` starts (or
  queues) a build and says whether it took it; ``poll(now)`` returns
  ``[(tile, ok)]`` for the builds finished since the last call (``ok``
  None: a flight's job took the tile over, ``build_share``)
  (``world_job_run._SessionBuilder``: a ``drape`` is fetched and written
  on the builder's own thread; a ``full`` tile goes through the engine
  session's build queue with its ``deadline`` and ``klass``);
* ``publisher`` -- ``settle(tile, kind, held)`` stages / swaps a finished
  tile and returns its state (``swapped``, ``staged``, ``pending``,
  ``failed``); ``held`` is rule S3's verdict for that tile now;
* ``wanted(tile)`` -- may the job build this tile (in an enabled region,
  a placeholder of ours, not ``external``, spec §7.2);
* ``loads()`` -- the tiles X-Plane has loaded this session (the
  ``Log.txt`` witness, ``O4_XPlane_Log``);
* ``slot_free(slots, running)`` -- how many builds may start now
  (``build_share.BuildShare.free_for``: a flight's job runs beside
  track mode on one budget and its deadlines come first, #2019).

Each tick:

1. The aircraft position moves the window tracker
   (``O4_World_Window.WindowTracker``; a jump forgets it, a witnessed load
   corrects it) and the motion tracker (track and speed from position
   deltas, ``O4_Imagery_Follow_Motion``).
2. Finished builds are settled: a staged tile is swapped when S3 allows
   (not witnessed, outside the window by 0.05° or 60 s of flight);
   swaps are spaced :data:`SWAP_SPACING_S` apart (§10) unless a tile's
   margin would run out before the next slot (then at once: the spacing
   never makes a tile late).
3. Candidates: flying (:data:`MOVING_MS` or faster), the tiles that enter
   along the straight track within the horizon, plus the turn margin
   (``O4_World_Ahead.ahead``), each with its deadline (entry less the S3
   margin and the swap); a tile that cannot be built by its deadline even
   at the low estimate is ``late`` and not started ("Flying faster than
   tiles can be built here").  Parked or slow: the tiles the window takes
   in on its next move in any direction (``O4_World_Ahead.ring``), nearest
   first, with a deadline at :data:`PARKED_ASSUMED_MS`.
4. Dispatch, earliest deadline first, while fewer builds run than the slots
   allow: ``O4_World_Governor.flight_slots`` in flight, ``parked_slots``
   parked, less what the frame-time guard has given back, less what an
   active flight's job runs and waits to start (``slot_free``).

THE PARKED AIRCRAFT (RULINGS 2026-11-12c (3), owner 14:32Z: "We always
need the high res imagery at an airport"; #2019): on the ground (AGL
under :data:`ON_GROUND_AGL_M`, or slower than :data:`PARKED_MS` when the
record has no AGL), the tile under the aircraft is a candidate although
X-Plane holds it (step 3 leaves held tiles out) -- a placeholder, or a
drape not yet given its core this session (``kind_of``: the pack's
kind of a tile this job may build, None for any other).  It is built at
once (deadline now, class P0) as a drape whose squares around the
aircraft are fetched at full resolution (``builder.start(..., core=(lat,
lon))``), and swapped in although X-Plane holds it -- the one exception
to S3, merged file by file so no name X-Plane may open goes (S5,
``publisher.settle(..., merge=True, fresh=True)``), which then OFFERS the user the
reload that shows it; nothing reloads on its own (12c (4)).

A build that fails twice is ``failed`` (two attempts, never a third,
spec §11).  Each finished build rescales the kind's remaining estimates by
measured / predicted, clamped to 0.5-2.5 (§9).
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Callable, Iterable, Optional

import O4_Flight_Schedule as SCHEDULE
import O4_World_Ahead as AHEAD
import O4_World_Governor as GOVERNOR
import O4_World_Pack as WP
import O4_World_Window as WINDOW
from O4_Imagery_Follow_Motion import MotionTracker

__all__ = ["KINDS", "ESTIMATE_S", "SPREAD", "MOVING_MS",
           "PARKED_ASSUMED_MS", "SWAP_SPACING_S", "MAX_ATTEMPTS", "WorldJob",
           "drape_estimate"]

#: The intermediate kind the job builds: D1 decided ``drape`` (spec §17,
#: RULINGS 2026-11-11j); ``light`` is retired.
KINDS = ("drape",)
#: Seconds one tile takes before any is measured on this machine
#: (``O4_Flight_Schedule.PROFILE_SECONDS``: a 512 px drape).
ESTIMATE_S = dict(SCHEDULE.PROFILE_SECONDS)


def drape_estimate(px) -> dict:
    """``estimate_s`` for a job whose drapes are ``px`` wide
    (``O4_Flight_Schedule.drape_seconds``)."""
    return {"drape": SCHEDULE.drape_seconds(px)}
#: An estimate's range (``plan_estimate.TIME_SPREAD_KNOWN``).
SPREAD = (0.75, 1.5)
#: Faster than this the aircraft has a track to run (spec §9: airborne
#: is 25 m/s).
MOVING_MS = 25.0
#: Parked: the ring's deadlines assume this speed (120 kt).
PARKED_ASSUMED_MS = 61.7
#: Seconds between two swaps (spec §10).
SWAP_SPACING_S = 10.0
#: Attempts per tile (spec §11 convergence guard).
MAX_ATTEMPTS = 2
#: On the ground: under this height above it (``flight_manager``'s), or,
#: with no AGL in the record, slower than :data:`PARKED_MS`.
ON_GROUND_AGL_M = 3.0
PARKED_MS = 2.0
#: The horizon runs this many degrees of travel past one build's length.
HORIZON_EXTRA_DEG = 1.0
MAX_HORIZON_S = 3600.0
_M_PER_DEG = 111_320.0

Tile = tuple[int, int]


@dataclass
class _Job:
    """One tile of build-ahead (spec §6.3)."""
    tile: Tile
    kind: str
    deadline: float                    # job clock seconds
    klass: str = "P1"
    state: str = "queued"              # queued building built staged
    #                                    swapped late failed
    attempts: int = 0
    started_at: Optional[float] = None
    finished_at: Optional[float] = None
    swapped_at: Optional[float] = None
    notes: list = field(default_factory=list)
    #: the parked aircraft's own tile: built at once with its core at
    #: ``core`` (lat, lon), swapped in although X-Plane holds it
    core: Optional[tuple] = None


class WorldJob:
    """Build-ahead in track mode (see the module)."""

    def __init__(self, *, builder, publisher, wanted: Callable[[Tile], bool],
                 kind: str = "drape", capacity: int = 4, cores: int = 8,
                 fly_slots: int = 0, sim_priority: str = "balanced",
                 loads: Callable[[], Iterable[Tile]] = lambda: (),
                 estimate_s: Optional[dict] = None,
                 slot_free: Callable[[int, int], int] = lambda s, r: s - r,
                 kind_of: Callable[[Tile], Optional[str]] = lambda t: None,
                 stamp: Callable[[], object] = lambda: "") -> None:
        if kind not in KINDS:
            raise ValueError(f"unknown intermediate kind {kind!r} "
                             f"(known: {list(KINDS)})")
        self.builder, self.publisher = builder, publisher
        self.wanted, self.loads = wanted, loads
        self.slot_free = slot_free
        self.kind_of = kind_of
        self.spawn: Optional[Tile] = None   # the parked aircraft's tile
        self.on_ground = False
        self._cored: set = set()
        self.stamp = stamp                 # last_swap's time (UTC text)
        self.kind = kind
        self.estimate_s = dict(ESTIMATE_S, **(estimate_s or {}))
        self.scale = 1.0
        self.capacity = int(capacity)
        self.flight_cap = GOVERNOR.flight_slots(cores, fly_slots, capacity)
        self.governor = GOVERNOR.FrameGovernor(sim_priority)
        self.tracker = WINDOW.WindowTracker()
        self.motion = MotionTracker()
        self.jobs: dict[Tile, _Job] = {}
        self.swaps: list[tuple[Tile, float]] = []     # (tile, at)
        self.last_swap: tuple = ()
        self.state, self.reason = "idle", ""
        self.position: Optional[tuple[float, float]] = None
        self.gs_ms = 0.0
        self._track: Optional[tuple[float, float]] = None   # (t, deg)
        self.turn_deg_s = 0.0
        self._seen_loads: set = set()
        self._swap_at = -math.inf

    # ------------------------------------------------------------ inputs

    def flight_loaded(self, lat: float, lon: float) -> None:
        """X-Plane (re)loaded the flight here: the window restarts
        (``WindowTracker.load``) and the motion history is forgotten."""
        self.tracker.load(lat, lon)
        self.motion.restart()

    def forget_window(self) -> None:
        """X-Plane loaded a flight somewhere unknown (the feed's reader
        re-resolved): the window's history is unknown again (the union,
        then the witness narrows it) and so is the motion."""
        self.tracker.forget()
        self.motion.restart()

    def estimate(self) -> tuple[float, float]:
        """``(low, high)`` seconds one build of the job's kind takes now."""
        base = self.estimate_s[self.kind] * self.scale
        return base * SPREAD[0], base * SPREAD[1]

    def tick(self, now: float, rec: Optional[dict]) -> None:
        """One cycle at job-clock ``now`` with the position record ``rec``
        (``lat``, ``lon``, ``frame_s``, ``paused``; ``None``: X-Plane does
        not answer)."""
        self._harvest(now)
        if rec is None:
            self.state, self.reason = "idle", "Waiting for X-Plane."
            return
        lat, lon = float(rec["lat"]), float(rec["lon"])
        self._move(now, lat, lon, float(rec.get("elev_m") or 0.0))
        self.spawn = self._spawn_tile(rec)
        self.governor.observe(now, rec.get("frame_s"), self._running() > 0)
        self._settle(now)
        if rec.get("paused"):
            self.state, self.reason = "paused", "X-Plane is paused."
            return
        self._plan(now)
        self._dispatch(now)
        self.state = "building" if self._running() else "following"

    # ---------------------------------------------------------- tracking

    def _move(self, now: float, lat: float, lon: float, alt: float) -> None:
        motion = self.motion.add(now, lat, lon, alt)
        if self.motion.jumped:
            self.tracker.forget()
        self.tracker.update(lat, lon)
        for tile in set(self.loads()) - self._seen_loads:
            self._seen_loads.add(tile)
            self.tracker.witness(*tile)
        self.position = (lat, lon)
        self.gs_ms = motion.groundspeed_ms if motion else 0.0
        if motion is None or self.gs_ms < MOVING_MS:
            self._track, self.turn_deg_s = None, 0.0
            return
        if self._track is not None and now > self._track[0]:
            delta = (motion.track_deg - self._track[1] + 180.0) % 360.0 - 180.0
            self.turn_deg_s = delta / (now - self._track[0])
        self._track = (now, motion.track_deg)

    def _spawn_tile(self, rec: dict) -> Optional[Tile]:
        """The tile under a parked aircraft that needs its core (see the
        module), or None."""
        agl = rec.get("agl_m")
        ground = (float(agl) < ON_GROUND_AGL_M if agl is not None
                  else self.gs_ms < PARKED_MS)
        self.on_ground = ground
        if not ground or self.position is None:
            return None
        tile = (math.floor(self.position[0]), math.floor(self.position[1]))
        if tile in self._cored:
            return None
        return tile if self.kind_of(tile) in ("placeholder", "drape") else None

    def held(self, tile: Tile) -> bool:
        """Rule S3: may X-Plane hold ``tile`` now (witnessed, in the window,
        or within the margin of entering it)?  Unknown position: yes."""
        return AHEAD.held(self.tracker, self.position, self.gs_ms, tile,
                          self._seen_loads)

    def _held_soon(self, tile: Tile) -> bool:
        """Would ``tile`` be held one swap spacing from now?"""
        if self.position is None:
            return True
        where = WINDOW.reach(*self.position, *tile, tracker=self.tracker)
        ahead_km = where["km_to_load"] - self.gs_ms * SWAP_SPACING_S / 1000.0
        return ahead_km < AHEAD.margin_km(self.gs_ms)

    # ---------------------------------------------------------- builds

    def _running(self) -> int:
        return sum(1 for j in self.jobs.values() if j.state == "building")

    def _harvest(self, now: float) -> None:
        for tile, ok in self.builder.poll(now):
            job = self.jobs.get(tuple(tile))
            if job is not None and ok is None:
                del self.jobs[tuple(tile)]  # a flight's job has it now
                continue
            if job is None or job.state != "building":
                continue
            job.finished_at = now
            if ok:
                job.state = "built"
                self._rescale(now - (job.started_at or now))
            elif job.attempts >= MAX_ATTEMPTS:
                job.state = "failed"
            else:
                job.state = "queued"

    def _rescale(self, measured: float) -> None:
        predicted = self.estimate_s[self.kind]
        if measured > 0 and predicted > 0:
            self.scale = min(2.5, max(0.5, measured / predicted))

    def _settle(self, now: float) -> None:
        """Stage and swap finished tiles (see the module, step 2)."""
        done = sorted((j for j in self.jobs.values()
                       if j.state in ("built", "staged")),
                      key=lambda j: j.deadline)
        for job in done:
            if job.core is not None:        # the parked exception to S3
                state = self.publisher.settle(job.tile, job.kind, False,
                                              merge=self.held(job.tile),
                                              fresh=True)
            else:
                held = self.held(job.tile)
                if (not held and now - self._swap_at < SWAP_SPACING_S
                        and not self._held_soon(job.tile)):
                    held = True             # waits for the next slot
                state = self.publisher.settle(job.tile, job.kind, held)
            if state == "swapped":
                job.state, job.swapped_at = "swapped", now
                if job.core is not None:
                    self._cored.add(job.tile)
                self._swap_at = now
                self.swaps.append((job.tile, now))
                self.last_swap = (WP.tile_name(*job.tile), job.kind,
                                  self.stamp())
            elif state in ("staged", "failed"):
                job.state = state

    # ---------------------------------------------------------- planning

    def _horizon_s(self) -> float:
        lat = self.position[0] if self.position else 0.0
        deg_m = _M_PER_DEG * max(math.cos(math.radians(lat)), 0.2)
        extra = HORIZON_EXTRA_DEG * deg_m / max(self.gs_ms, MOVING_MS)
        return min(MAX_HORIZON_S, self.estimate()[1] + extra)

    def candidates(self) -> dict[Tile, float]:
        """``{tile: deadline in seconds from now}`` (see the module, step
        3); every tile the window may take in next, wanted or not."""
        lat, lon = self.position
        if self._track is None:
            return {tile: km * 1000.0 / PARKED_ASSUMED_MS
                    for tile, km in AHEAD.ring(self.tracker, lat, lon).items()}
        entries = AHEAD.ahead(self.tracker, lat, lon, self._track[1],
                              self.gs_ms, self._horizon_s(), self.turn_deg_s)
        return {tile: AHEAD.deadline_s(t, self.gs_ms)
                for tile, t in entries.items()}

    def _plan(self, now: float) -> None:
        low = self.estimate()[0]
        wanted = {tile: d for tile, d in self.candidates().items()
                  if self.wanted(tile) and not self.held(tile)}
        if self.spawn is not None:
            wanted[self.spawn] = 0.0        # at once, although X-Plane holds it
            done = self.jobs.get(self.spawn)
            if done is not None and done.core is None and done.state in (
                    "swapped", "staged"):
                del self.jobs[self.spawn]   # drawn without its core: again
        for tile, job in list(self.jobs.items()):
            if job.state in ("queued", "late") and tile not in wanted:
                del self.jobs[tile]         # off the track now
        for tile, deadline in wanted.items():
            job = self.jobs.get(tile)
            if job is not None and job.state not in ("queued", "late"):
                continue
            if job is None:
                job = self.jobs[tile] = _Job(tile, self.kind, now + deadline)
            job.deadline = now + deadline
            if tile == self.spawn:
                job.core, job.klass = self.position, "P0"
                job.state = "queued"
                continue
            job.core = None
            moving = self._track is not None
            job.state = "late" if moving and deadline < low else "queued"
        late = [j for j in self.jobs.values() if j.state == "late"]
        self.reason = ("Flying faster than tiles can be built here: ahead "
                       "stays X-Plane's own scenery." if late else "")

    def slots(self) -> int:
        """Builds that may run now (spec §10)."""
        cap = (self.flight_cap if self._track is not None
               else GOVERNOR.parked_slots(self.capacity))
        return self.governor.allowed(cap)

    def _dispatch(self, now: float) -> None:
        free = self.slot_free(self.slots(), self._running())
        queued = sorted((j for j in self.jobs.values() if j.state == "queued"),
                        key=lambda j: (j.deadline, j.tile))
        for job in queued[:max(0, free)]:
            core = {} if job.core is None else {"core": job.core}
            if not self.builder.start(job.tile, job.kind, job.deadline - now,
                                      job.klass, **core):
                continue
            job.state, job.started_at = "building", now
            job.attempts += 1

    # ----------------------------------------------------------- status

    def job_rows(self) -> tuple:
        """The map's rows, ``[[lat, lon], "ahead", kind, state]`` per tile
        the job holds (``FlightStatus.jobs``' shape, so the Fly map's
        corridor cells read both); a written drape is staged at once, so
        ``built`` reads ``staged``."""
        return tuple([list(j.tile), "ahead", j.kind,
                      "staged" if j.state == "built" else j.state]
                     for _t, j in sorted(self.jobs.items()))

    def status(self, now: float) -> dict:
        """The job's ``WorldStatus`` fields."""
        building = []
        high = self.estimate()[1]
        for job in self.jobs.values():
            if job.state == "building":
                remaining = max(0.0, high - (now - (job.started_at or now)))
                building.append([WP.tile_name(*job.tile), job.kind,
                                 "building", round(remaining)])
        return {"state": self.state, "reason": self.reason,
                "queue": sum(1 for j in self.jobs.values()
                             if j.state == "queued"),
                "building": tuple(building), "jobs": self.job_rows(),
                "slots": self.slots(),
                "frame_ms": self.governor.frame_ms(),
                "governor": self.governor.state,
                "last_swap": self.last_swap, "here": self.here(now)}

    def here(self, now: float) -> Optional[dict]:
        """The aircraft's own tile as the job sees it (#2020: the Fly
        pane's "Preparing imagery at ..." with no plan): ``tile``,
        ``lat``/``lon`` (the aircraft), ``on_ground``, ``kind`` (the
        pack's: ``placeholder``, ``drape``, ``full``, "" not ours),
        ``job`` (its build-ahead state, "" none), ``elapsed_s`` /
        ``estimate_s`` of a running build, ``core`` (the build carries,
        or the tile has had, the parked aircraft's full-resolution core).
        None before the first position."""
        if self.position is None:
            return None
        tile = (math.floor(self.position[0]), math.floor(self.position[1]))
        job = self.jobs.get(tile)
        building = (job is not None and job.state == "building"
                    and job.started_at is not None)
        elapsed = now - job.started_at if building else 0.0
        return {"tile": WP.tile_name(*tile),
                "lat": round(self.position[0], 6),
                "lon": round(self.position[1], 6),
                "on_ground": bool(self.on_ground),
                "kind": self.kind_of(tile) or "",
                "job": "" if job is None else (
                    "staged" if job.state == "built" else job.state),
                "elapsed_s": round(max(0.0, elapsed)),
                "estimate_s": round(self.estimate()[1]) if building else 0,
                "core": bool(tile in self._cored
                             or (job is not None and job.core is not None))}
