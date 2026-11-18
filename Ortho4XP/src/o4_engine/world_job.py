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
3. Candidates (#2142 part 3), always both: the RING -- the tiles the
   window takes in on its next move in any direction
   (``O4_World_Ahead.ring``), each with the deadline of turning straight
   at it (``O4_World_Ahead.ring_deadline_s``, at :data:`PARKED_ASSUMED_MS`
   or faster) -- and, flying (:data:`MOVING_MS` or faster), the tiles that
   enter along the straight track within the horizon plus the turn margin
   (``O4_World_Ahead.ahead``), each with its deadline (entry less the S3
   margin and the swap); a tile in both keeps the earlier.  Only an AHEAD
   tile that cannot be built by its deadline even at the low estimate is
   ``late`` and not started ("Flying faster than tiles can be built
   here").  A placeholder is left out only while it is in the window or
   within S3's margin of it NOW (:meth:`WorldJob.in_window_now`): the
   ``Log.txt`` witness keeps no placeholder out for the session (a tile
   X-Plane loaded empty and then left is draped before it comes back).
   Ring and held tiles are drawn at :data:`QUICK_PX`; an ahead tile at the
   user's width when that fits its deadline (:meth:`WorldJob.px_for`).
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

HELD PLACEHOLDERS (#2142 part 2): every placeholder of the window
X-Plane holds now is a candidate as well -- on the ground at once
(class P0, after the aircraft's own tile, nearest first), in the air
LAST (after every ring and ahead tile).  A placeholder X-Plane holds
goes in although it holds it (``O4_World_Pack.nothing_held``, #2032)
but shows only after a reload: when the last of them (and the parked
aircraft's own tile) is swapped or has failed, and the aircraft is on
the ground, the job calls ``offer()`` ONCE for the episode (a flight
load starts a new one); in the air nothing is offered until it is next
on the ground (owner Q2, 2026-11-17).

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
           "PARKED_ASSUMED_MS", "SWAP_SPACING_S", "MAX_ATTEMPTS", "QUICK_PX",
           "WorldJob", "drape_estimate"]

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
#: A window move takes in this many tiles at most per column (the 5-row
#: ring's side); the horizon covers building them on the slots.
RING_SIDE = 5
#: The photo width of every ring and held tile (owner Q1, 2026-11-17:
#: Quick for every speculative tile; the follow job sharpens it live).
QUICK_PX = 512
#: A ring or ahead tile due within this many builds (high estimate) goes
#: before the ground's held placeholders (CYYR replay: the held ones
#: took the parked slots the first ring needed).
URGENT_BUILDS = 2.0
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
    #: photo width this build is asked for (None: the builder's default)
    px: Optional[int] = None
    #: a placeholder X-Plane holds in its window now (part 2)
    held: bool = False
    #: started on the ground as a held placeholder
    ground_start: bool = False
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
                 stamp: Callable[[], object] = lambda: "",
                 drape_px: Optional[int] = None,
                 offer: Callable[[], object] = lambda: None) -> None:
        """``drape_px``: the user's drape width (None: builds are started
        without ``px``); ``offer()``: the episode's one reload offer."""
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
        self.drape_px = drape_px
        self.offer = offer
        self.offers: list = []              # job-clock times offered
        self._ahead: set = set()
        self._new_episode()

    def _new_episode(self) -> None:
        """A flight (re)load: the reload offer may be made again."""
        self._shown_on_reload: set = set()  # swapped while X-Plane held it
        self._offered = False

    # ------------------------------------------------------------ inputs

    def flight_loaded(self, lat: float, lon: float) -> None:
        """X-Plane (re)loaded the flight here: the window restarts
        (``WindowTracker.load``) and the motion history is forgotten."""
        self.tracker.load(lat, lon)
        self.motion.restart()
        self._new_episode()

    def forget_window(self) -> None:
        """X-Plane loaded a flight somewhere unknown (the feed's reader
        re-resolved): the window's history is unknown again (the union,
        then the witness narrows it) and so is the motion."""
        self.tracker.forget()
        self.motion.restart()
        self._new_episode()

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
        self._maybe_offer(now)
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

    def in_window_now(self, tile: Tile) -> bool:
        """In the window or within S3's margin of it now -- the witness
        left out (a placeholder X-Plane loaded and then left is wanted
        again; tiles holding real files keep S4 at the publisher)."""
        return AHEAD.held(self.tracker, self.position, self.gs_ms, tile)

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

    def _counted(self) -> int:
        """Running builds that hold a slot: flying, a held placeholder
        started on the ground does not (it was dispatched on the parked
        slots; counting it on the 1-3 flight slots kept the first tiles
        on the track from starting for one build, CYYR replay)."""
        return sum(1 for j in self.jobs.values() if j.state == "building"
                   and not (self._track is not None and j.ground_start))

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
            shown = job.held
            if job.core is not None:        # the parked exception to S3
                shown = self.held(job.tile)
                state = self.publisher.settle(job.tile, job.kind, False,
                                              merge=shown, fresh=True)
            else:
                held = self.held(job.tile)
                if (not held and now - self._swap_at < SWAP_SPACING_S
                        and not self._held_soon(job.tile)):
                    held = True             # waits for the next slot
                state = self.publisher.settle(job.tile, job.kind, held)
            if state == "swapped":
                if shown:                   # X-Plane shows it on a reload
                    self._shown_on_reload.add(job.tile)
                job.state, job.swapped_at = "swapped", now
                if job.core is not None:
                    self._cored.add(job.tile)
                self._swap_at = now
                self.swaps.append((job.tile, now))
                self.last_swap = (WP.tile_name(*job.tile), job.kind,
                                  self.stamp())
            elif state in ("staged", "failed"):
                job.state = state

    def _maybe_offer(self, now: float) -> None:
        """The episode's ONE reload offer (see the module): every held
        placeholder and the parked aircraft's own tile settled, at least
        one of them swapped while X-Plane held it, on the ground."""
        if (self._offered or not self._shown_on_reload or not self.on_ground
                or self.spawn is not None):     # its own tile comes first
            return
        if any((j.held or j.core is not None)
               and j.state not in ("swapped", "failed")
               for j in self.jobs.values()):
            return
        self._offered = True
        self.offers.append(now)
        self.offer()

    # ---------------------------------------------------------- planning

    def _horizon_s(self) -> float:
        lat = self.position[0] if self.position else 0.0
        deg_m = _M_PER_DEG * max(math.cos(math.radians(lat)), 0.2)
        extra = HORIZON_EXTRA_DEG * deg_m / max(self.gs_ms, MOVING_MS)
        rounds = math.ceil(RING_SIDE / max(1, self.slots()))
        return min(MAX_HORIZON_S, self.estimate()[1] * rounds + extra)

    def candidates(self) -> dict[Tile, float]:
        """``{tile: deadline in seconds from now}`` (see the module, step
        3): the ring and, flying, the tiles ahead; every tile the window
        may take in next, wanted or not.  The ahead ones are kept in
        ``_ahead`` (only they can be late)."""
        lat, lon = self.position
        out = {tile: AHEAD.ring_deadline_s(km, self.gs_ms)
               for tile, km in AHEAD.ring(self.tracker, lat, lon).items()}
        self._ahead = set()
        if self._track is None:
            return out
        entries = AHEAD.ahead(self.tracker, lat, lon, self._track[1],
                              self.gs_ms, self._horizon_s(), self.turn_deg_s)
        for tile, t in entries.items():
            deadline = AHEAD.deadline_s(t, self.gs_ms)
            self._ahead.add(tile)
            out[tile] = min(deadline, out.get(tile, deadline))
        return out

    def held_placeholders(self) -> dict[Tile, float]:
        """``{tile: deadline}`` of the placeholders X-Plane holds in its
        window now (see the module): on the ground at once, nearest
        first; in the air after every other candidate."""
        lat, lon = self.position
        base = 0.0 if self.on_ground else MAX_HORIZON_S
        out = {}
        for tile in self.tracker.window():
            if tile == self.spawn or not self.wanted(tile):
                continue
            km = math.hypot(tile[0] + 0.5 - lat, (tile[1] + 0.5 - lon)
                            * math.cos(math.radians(lat))) * _M_PER_DEG / 1e3
            out[tile] = base + km / 1000.0
        return out

    def px_for(self, deadline_s: float) -> Optional[int]:
        """An ahead tile's width: the user's when its high estimate fits
        ``deadline_s``, else :data:`QUICK_PX` (None: no user width)."""
        if self.drape_px is None:
            return None
        high = (SCHEDULE.drape_seconds(self.drape_px) * self.scale
                * SPREAD[1])
        return int(self.drape_px) if high <= deadline_s else QUICK_PX

    def _plan(self, now: float) -> None:
        low = self.estimate()[0]
        wanted = {tile: d for tile, d in self.candidates().items()
                  if self.wanted(tile) and not self.in_window_now(tile)}
        held = self.held_placeholders()
        wanted.update(held)
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
            job.held = tile in held
            ahead = self._track is not None and tile in self._ahead
            quick = None if self.drape_px is None else QUICK_PX
            job.px = (self.px_for(deadline) if ahead and not job.held
                      else quick)
            job.state = ("late" if ahead and not job.held and deadline < low
                         else "queued")
        late = [j for j in self.jobs.values() if j.state == "late"]
        self.reason = ("Flying faster than tiles can be built here: ahead "
                       "stays X-Plane's own scenery." if late else "")

    def slots(self) -> int:
        """Builds that may run now (spec §10)."""
        cap = (self.flight_cap if self._track is not None
               else GOVERNOR.parked_slots(self.capacity))
        return self.governor.allowed(cap)

    def _rank(self, job: _Job, now: float) -> int:
        """Dispatch order: the parked aircraft's tile; a ring or ahead
        tile due within one build (high estimate); the ground's held
        placeholders; the track; the ring; the air's held placeholders."""
        if job.core is not None:
            return 0
        if job.held:
            return 2 if self.on_ground else 5
        if job.deadline - now <= self.estimate()[1] * URGENT_BUILDS:
            return 1
        return 3 if job.tile in self._ahead else 4

    def _order(self, now: float) -> list:
        """The queued jobs in dispatch order (:meth:`_rank`, then
        deadline); on the ground the held placeholders alternate with
        the ring after the urgent ones, so neither takes every parked
        slot (CYYR replay: the ring the first minutes of flight need)."""
        queued = sorted((j for j in self.jobs.values() if j.state == "queued"),
                        key=lambda j: (self._rank(j, now), j.deadline, j.tile))
        if not self.on_ground:
            return queued
        head = [j for j in queued if self._rank(j, now) < 2]
        held = [j for j in queued if self._rank(j, now) == 2]
        rest = [j for j in queued if self._rank(j, now) > 2]
        mixed = [j for pair in zip(held, rest, strict=False) for j in pair]
        n = min(len(held), len(rest))
        return head + mixed + held[n:] + rest[n:]

    def _gated(self, job: _Job) -> bool:
        """Flying, a build off the track (ring, held) waits for a spare
        slot (:meth:`_spare_off_track`)."""
        return (self._track is not None and job.core is None
                and job.tile not in self._ahead)

    def _spare_off_track(self, queued: list) -> int:
        """Builds off the track that may start now while flying: none
        while a track tile waits, and never the last slot (a build is not
        pre-empted: the track's next tile must find one free)."""
        if self._track is None:
            return len(queued)
        if any(not self._gated(j) for j in queued):
            return 0
        running = sum(1 for j in self.jobs.values() if j.state == "building"
                      and self._gated(j) and not j.ground_start)
        return self.slots() - 1 - running

    def _dispatch(self, now: float) -> None:
        free = self.slot_free(self.slots(), self._counted())
        queued = self._order(now)
        spare = self._spare_off_track(queued)
        for job in queued[:max(0, free)]:
            if self._gated(job):
                if spare <= 0:
                    break
                spare -= 1
            core = {} if job.core is None else {"core": job.core}
            if job.px is not None:
                core["px"] = job.px
            if not self.builder.start(job.tile, job.kind, job.deadline - now,
                                      job.klass, **core):
                continue
            job.state, job.started_at = "building", now
            job.ground_start = job.held and self.on_ground
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
