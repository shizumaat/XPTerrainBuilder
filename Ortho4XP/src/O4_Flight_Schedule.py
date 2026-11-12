"""The flight manager's schedule (spec flight-manager-and-world-20261110
§6.2, §6.3, §8.2, §8.4, §9): pure arithmetic, no files, no clock.

* :func:`route_times` -- the route densified, with the planned seconds
  after takeoff at every sample (waypoint times when the plan has them,
  else the cruise speed with a 250 kt climb and descent leg).
* :func:`tile_deadlines` -- a tile's deadline from the sample at which it
  enters X-Plane's DSF window.  WHERE a tile enters is the window model's
  answer (``O4_World_Window``, lane W0); this module takes it as a
  ``{tile: sample index}`` mapping, index 0 being the first window.
* :class:`Job`, :func:`job_estimate`, :func:`rescale` -- what is to be
  built, with a ``[lo, hi]`` seconds range from the recorded times.
* :func:`finish_times`, :func:`departure_countdown`,
  :func:`projected_late`, :func:`feasible`, :func:`shed_order`,
  :func:`next_job` -- list scheduling on ``slots`` build slots, the
  countdown to the departure area (RULINGS 2026-11-12c (2)), the route
  tiles projected late, the shedding order and the dispatch pick with
  the laxity guard.
* :func:`readiness_items` -- the readiness rows of §6.2 from facts the
  flight manager gathers; :func:`countdown_text` -- the one line.

All times are seconds.  A job's ``deadline_s`` is counted from TAKEOFF;
0 means "before the flight loads" (class P0).  Finish times are counted
from NOW.  The countdown T is the wait until the departure area (every P0
job) is built; a later job that does not finish by ``T + deadline_s`` is
projected late and warned of, not waited for.

No airport is named here (owner standing 2026-10-05).
"""

import heapq
import math
from dataclasses import dataclass, replace
from typing import Dict, Iterable, List, NamedTuple, Optional, Sequence, Tuple

import O4_Flight_Plan as FP

__all__ = [
    "P0", "P1", "P2", "P3", "P4", "Job", "Facts", "Item", "route_times",
    "margin_s", "tile_deadlines", "klass_for", "job_estimate", "rescale",
    "DRAPE_SECONDS", "drape_seconds",
    "finish_times", "feasible", "shed_order", "next_job",
    "readiness_items", "countdown_text", "DONE_STATES", "READY_KEYS",
    "DEPARTURE_MARGIN_S", "departure_countdown", "projected_late",
]

Tile = Tuple[int, int]

#: Dispatch classes, highest first (§8.4).  P3 is the follow job's
#: sharpening, which is not a build job; it is named for completeness.
P0, P1, P2, P3, P4 = 0, 1, 2, 3, 4

KT_TO_MS = FP.KT_TO_MS
#: No speed in the plan and none from the aircraft (§4.3 step 3).
DEFAULT_CRUISE_KT = 250.0
#: The climb and descent legs are flown at this speed (§8.2).
CLIMB_KT = 250.0
#: Climb/descent leg length per 1000 ft of cruise level (the 3-to-1
#: descent rule), and the level assumed when the plan has none [estimate].
CLIMB_NM_PER_1000_FT = 3.0
DEFAULT_CRUISE_ALT_FT = 10000.0
#: Swap rule S3: a tile is swapped at least this far outside the window,
#: 0.05 degree (of latitude, 5.56 km) or 60 s of flight, whichever is more.
MARGIN_KM = 0.05 * math.pi * FP.EARTH_RADIUS_KM / 180.0
MARGIN_MIN_S = 60.0
#: Swaps are spaced at least this far apart (§10 Landings).
SWAP_S = 10.0
#: Seconds one drape with its water copy takes cold, by photo width
#: (``drape_photo_px``; lane ldrape2, 2026-11-11, cold caches, Labrador):
#: 512 px 82-109 s (photos 29-70 s, the water read 47-102 s beside them,
#: held to ``world_job_run.WATER_WAIT_S``), 1024 px 109 s, 4096 px 730 s
#: (photos 445 s, masks 213 s; the masks now run beside the photos).
DRAPE_SECONDS = {512: 80.0, 1024: 110.0, 4096: 730.0}
#: Seconds per tile before any build of the kind is recorded: the drape,
#: the one intermediate kind (spec §17, RULINGS 2026-11-11j).
PROFILE_SECONDS = {"drape": DRAPE_SECONDS[512]}
#: plan_estimate's spreads (TIME_SPREAD_KNOWN / _UNKNOWN), repeated so
#: this module stays pure; tests/test_flight_schedule.py pins them equal.
SPREAD_KNOWN = (0.75, 1.5)
SPREAD_UNKNOWN = (0.5, 2.5)
#: Rescaling by measured / predicted is clamped to this range (§9).
RESCALE_RANGE = (0.5, 2.5)

#: Job states (§6.3) after which a job needs no slot.
DONE_STATES = frozenset({"staged", "swapped", "external"})
_DROPPED_STATES = frozenset({"shed", "failed"})


# ===========================================================================
# Route -> times -> deadlines
# ===========================================================================
def _leg_samples(points: Sequence[Tuple[float, float]]):
    """The route densified leg by leg: ``(samples, leg of each sample)``;
    the first sample is leg 0, a sample of leg i lies between waypoints
    i-1 and i."""
    samples: List[Tuple[float, float]] = list(FP.densify(points[:1]))
    legs: List[int] = [0] * len(samples)
    for i in range(1, len(points)):
        part = FP.densify([points[i - 1], points[i]])[1:]
        samples += part
        legs += [i] * len(part)
    return samples, legs


def _cumulative_km(samples) -> List[float]:
    out = [0.0]
    for a, b in zip(samples, samples[1:], strict=False):
        out.append(out[-1] + FP.route_length_km([a, b]))
    return out


def route_times(plan: "FP.FlightPlan", cruise_ms: Optional[float] = None
                ) -> Tuple[List[Tuple[float, float]], List[float]]:
    """``(samples, seconds after takeoff)`` along the plan's route.

    When every waypoint carries a time (``t_s``) and they do not run
    backwards, times are interpolated by distance within each leg.
    Otherwise the route is flown at ``cruise_ms`` (else the plan's, else
    :data:`DEFAULT_CRUISE_KT`), with a climb leg and a descent leg at
    :data:`CLIMB_KT` sized by the cruise level."""
    samples, legs = _leg_samples(plan.points())
    km = _cumulative_km(samples)
    stamps = [w.t_s for w in plan.waypoints]
    if all(t is not None for t in stamps) and all(
            b >= a for a, b in zip(stamps, stamps[1:], strict=False)):
        return samples, _interpolated(km, legs, stamps)
    speed = cruise_ms or plan.cruise_ms or DEFAULT_CRUISE_KT * KT_TO_MS
    level = plan.cruise_alt_ft or DEFAULT_CRUISE_ALT_FT
    total = km[-1]
    leg = min(total / 2.0, CLIMB_NM_PER_1000_FT * level / 1000.0 * FP.KM_PER_NM)
    climb = min(speed, CLIMB_KT * KT_TO_MS)
    times = [0.0]
    for a, b in zip(km, km[1:], strict=False):
        middle = (a + b) / 2.0
        v = climb if middle < leg or middle > total - leg else speed
        times.append(times[-1] + (b - a) * 1000.0 / v)
    return samples, times


def _interpolated(km, legs, stamps) -> List[float]:
    """Seconds at each sample from the waypoint times, by distance."""
    ends = {0: km[0]}                 # leg -> km at its closing waypoint
    for i, leg in enumerate(legs):
        ends[leg] = km[i]
    out = []
    for i, leg in enumerate(legs):
        if leg == 0:
            out.append(float(stamps[0]))
            continue
        t0, t1 = float(stamps[leg - 1]), float(stamps[leg])
        k0 = ends.get(leg - 1, km[0])
        span = ends[leg] - k0
        frac = 1.0 if span <= 0 else (km[i] - k0) / span
        out.append(t0 + frac * (t1 - t0))
    return out


def margin_s(speed_ms: float) -> float:
    """Swap rule S3's margin in seconds of flight at ``speed_ms``."""
    if speed_ms <= 0:
        return MARGIN_MIN_S
    return max(MARGIN_MIN_S, MARGIN_KM * 1000.0 / speed_ms)


def tile_deadlines(times: Sequence[float], entries: Dict[Tile, int],
                   speed_ms: float) -> Dict[Tile, float]:
    """Each tile's deadline after takeoff: the time it enters the window
    (``entries``: tile -> sample index, from the window model), less the
    S3 margin and one swap.  Index 0 (the first window) and any deadline
    that would fall before takeoff are 0: "before the flight loads"."""
    lead = margin_s(speed_ms) + SWAP_S
    return {tile: (0.0 if index <= 0 else max(0.0, times[index] - lead))
            for tile, index in entries.items()}


# ===========================================================================
# Jobs and their estimates
# ===========================================================================
@dataclass(frozen=True)
class Job:
    """One tile to make ready (§6.3)."""
    tile: Tile
    role: str                      # departure | enroute | destination | alternate
    kind: str                      # light | drape | full
    klass: int
    deadline_s: float              # after takeoff; 0 = before the flight loads
    est_s: Tuple[float, float]     # whole build, [lo, hi]
    needs_network: bool = False
    state: str = "queued"
    #: Seconds still to run ``[lo, hi]`` while building; None = ``est_s``.
    remaining_s: Optional[Tuple[float, float]] = None
    #: Distance of the tile from the route itself (0 = the route crosses it).
    off_route_km: float = 0.0

    @property
    def left_hi(self) -> float:
        return float((self.remaining_s or self.est_s)[1])

    @property
    def open(self) -> bool:
        """Still needs a slot (not built, shed or failed)."""
        return self.state not in DONE_STATES and self.state not in _DROPPED_STATES


def klass_for(role: str, first_window: bool = False) -> int:
    """The dispatch class of §8.4."""
    if role == "departure" or first_window:
        return P0
    return {"enroute": P1, "destination": P2, "alternate": P4}.get(role, P1)


def drape_seconds(px) -> float:
    """:data:`DRAPE_SECONDS` of a ``drape_photo_px`` value (512 px for a
    width the table does not know)."""
    try:
        return DRAPE_SECONDS.get(int(px), DRAPE_SECONDS[512])
    except (TypeError, ValueError):
        return DRAPE_SECONDS[512]


def job_estimate(kind: str, recorded_s: Optional[float] = None,
                 known: bool = False) -> Tuple[float, float]:
    """``[lo, hi]`` seconds: the recorded point estimate (``known`` = from
    the tile's own history, else a cross-tile fit), or the profile's
    constant before any build of the kind is recorded."""
    point = recorded_s if recorded_s is not None else PROFILE_SECONDS.get(kind)
    if point is None:
        raise ValueError("no estimate for a %r build" % kind)
    lo, hi = SPREAD_KNOWN if known and recorded_s is not None else SPREAD_UNKNOWN
    return (point * lo, point * hi)


def rescale(jobs: Iterable[Job], kind: str, measured_s: float,
            predicted_s: float) -> List[Job]:
    """After a finished ``kind`` job: scale the queued jobs of that kind by
    measured / predicted, clamped to :data:`RESCALE_RANGE`."""
    jobs = list(jobs)
    if predicted_s <= 0 or measured_s <= 0:
        return jobs
    f = min(max(measured_s / predicted_s, RESCALE_RANGE[0]), RESCALE_RANGE[1])
    return [replace(j, est_s=(j.est_s[0] * f, j.est_s[1] * f))
            if j.kind == kind and j.state == "queued" else j for j in jobs]


# ===========================================================================
# Scheduling
# ===========================================================================
def _first(job: Job) -> bool:
    """The departure tile: first of its class (#2023, the pilot waits
    for it; the full build fetches its airport's imagery first)."""
    return job.role == "departure" and job.klass == P0


def _plan_order(jobs: Iterable[Job]) -> List[Job]:
    """Running jobs first (they hold their slots), then class, deadline.
    The laxity guard is a dispatch rule (:func:`next_job`); the plan
    order is the class order, so the countdown errs late, never early."""
    return sorted((j for j in jobs if j.open),
                  key=lambda j: (j.state != "building", j.klass,
                                 not _first(j), j.deadline_s, j.tile))


def finish_times(jobs: Iterable[Job], slots: int) -> List[Tuple[Job, float]]:
    """``(job, seconds from now)`` for every open job, list-scheduled on
    ``slots`` slots in plan order with the high-end estimates."""
    free = [0.0] * max(1, int(slots))
    out = []
    for job in _plan_order(jobs):
        end = heapq.heappop(free) + job.left_hi
        heapq.heappush(free, end)
        out.append((job, end))
    return out


def _estimated(job: Job) -> bool:
    values = job.remaining_s or job.est_s
    return values is not None and all(
        v is not None and math.isfinite(v) for v in values)


#: The readiness rows a flight waits for (RULINGS 2026-11-12c (2), owner
#: 14:32Z: "be conservative with the ready to start timer, but it should
#: definitely let the user leave as soon as the departure area is ready"):
#: the facts and the departure area.  The route, destination, alternate
#: and reload rows are shown, never waited for: they build in flight by
#: their deadlines, a tile projected late is warned of
#: (:func:`projected_late`).  Replaces the 2026-11-10 "every row" rule.
READY_KEYS = ("world", "budget", "network", "prefetch", "departure",
              "first_window")
#: Added to the departure area's high-estimate finish (conservative).
DEPARTURE_MARGIN_S = 60.0


def departure_countdown(jobs: Iterable[Job], slots: int) -> Optional[float]:
    """Seconds until the departure area (every open P0 job: the
    departure and the first window) is built, list-scheduled on ``slots``
    with the high estimates, plus :data:`DEPARTURE_MARGIN_S`; 0 when none
    is open; None when one has no estimate."""
    jobs = list(jobs)
    area = [j for j in jobs if j.open and j.klass == P0]
    if not area:
        return 0.0
    if not all(_estimated(j) for j in area):
        return None
    ends = [end for job, end in finish_times(jobs, slots) if job.klass == P0]
    return max(ends) + DEPARTURE_MARGIN_S


def projected_late(jobs: Iterable[Job], slots: int, takeoff_s: float
                   ) -> List[Job]:
    """The open en-route, destination and alternate jobs that, built on
    ``slots`` in plan order with the high estimates, finish after their
    tile loads with takeoff ``takeoff_s`` seconds from now."""
    return [job for job, end in finish_times(jobs, slots)
            if job.klass != P0 and end > takeoff_s + job.deadline_s]


def feasible(jobs: Iterable[Job], slots: int, takeoff_s: float) -> bool:
    """Does every open job finish by ``takeoff_s + deadline_s``?"""
    return all(end <= takeoff_s + job.deadline_s
               for job, end in finish_times(jobs, slots))


def _shed_candidates(jobs: Sequence[Job]) -> List[Job]:
    """What may be given up, in order (§8.4): the alternate; corridor
    tiles off the route, farthest first; corridor tiles on the route,
    earliest deadline first.  Never P0, never the destination."""
    open_ = [j for j in jobs if j.open and j.klass != P0]
    alt = [j for j in open_ if j.role == "alternate"]
    off = sorted((j for j in open_ if j.role == "enroute" and j.off_route_km > 0),
                 key=lambda j: (-j.off_route_km, j.tile))
    on = sorted((j for j in open_ if j.role == "enroute" and j.off_route_km <= 0),
                key=lambda j: (j.deadline_s, j.tile))
    return alt + off + on


def shed_order(jobs: Iterable[Job], slots: int, takeoff_s: float) -> List[Job]:
    """The jobs to give up, in order, until the rest is feasible with
    takeoff at ``takeoff_s`` (0 in flight).  Empty when it already is;
    when nothing more may be shed and it still is not, the destination
    will be late and the pilot is told (§4.3 step 7)."""
    kept = list(jobs)
    shed: List[Job] = []
    for victim in _shed_candidates(kept):
        if feasible(kept, slots, takeoff_s):
            break
        kept.remove(victim)
        shed.append(victim)
    return shed


def next_job(jobs: Iterable[Job], now_s: float, takeoff_s: float
             ) -> Optional[Job]:
    """The queued job to start next (§8.4).  Laxity guard: a job whose
    slack (takeoff + deadline - now - high estimate) is under one build's
    length (the longest queued high estimate) goes first, the tightest
    first; otherwise class, then the earliest deadline.  The departure
    tile goes before any other job (#2023: the pilot waits for it)."""
    queued = [j for j in jobs if j.state == "queued"]
    if not queued:
        return None
    guard = max(j.left_hi for j in queued)

    def slack(j: Job) -> float:
        return takeoff_s + j.deadline_s - now_s - j.left_hi

    tight = [j for j in queued if slack(j) < guard]
    if tight:
        return min(tight, key=lambda j: (not _first(j), slack(j), j.klass,
                                         j.tile))
    return min(queued, key=lambda j: (j.klass, not _first(j), j.deadline_s,
                                      j.tile))


# ===========================================================================
# Readiness (§6.2)
# ===========================================================================
@dataclass(frozen=True)
class Facts:
    """What the flight manager knows when it asks for the readiness rows.
    ``None`` = not known yet (the row is ``working``)."""
    jobs: Tuple[Job, ...]
    slots: int = 1
    #: Build slots in the air (§10); None: the same as ``slots``.
    flight_slots: Optional[int] = None
    world_installed: bool = False
    world_seen: Optional[bool] = None       # a World-pack line in Log.txt
    xplane_running: bool = False
    budget_fits: Optional[bool] = None
    budget_detail: str = ""
    network_ok: Optional[bool] = None
    network_detail: str = ""                # what the network row is blocked on
    all_on_disk: bool = False               # nothing this flight needs is remote
    prefetch_done: Optional[bool] = None
    build_alternate: bool = False
    flight_loaded: bool = False             # X-Plane has a flight loaded
    loaded_real: Optional[bool] = None      # the witness read our real tiles


class Item(NamedTuple):
    """One readiness row: ``[key, state, eta_s, detail]`` on the wire."""
    key: str
    state: str          # done | working | waiting | blocked | failed
    eta_s: Optional[float]
    detail: str


def _flag_item(key: str, flag: Optional[bool], blocked: str) -> Item:
    if flag is None:
        return Item(key, "working", None, "")
    return Item(key, "done", 0.0, "") if flag else Item(key, "blocked", None, blocked)


def _jobs_item(key: str, jobs: List[Job], ends: Dict[int, float]) -> Item:
    """Done when every job is built; failed when one failed; else the
    time until the last of them is built.  A job given up (``shed``: the
    offline waiver, a diversion) is not waited for."""
    jobs = [j for j in jobs if j.state != "shed"]
    if all(j.state in DONE_STATES for j in jobs):
        return Item(key, "done", 0.0, "")
    if any(j.state == "failed" for j in jobs):
        return Item(key, "failed", None, "The build failed twice")
    pending = [ends[id(j)] for j in jobs if id(j) in ends]
    working = any(j.state not in ("queued", "shed") for j in jobs if j.open)
    return Item(key, "working" if working else "waiting",
                max(pending) if pending else None, "")


def _deadline_item(key: str, jobs: List[Job], ends: Dict[int, float]) -> Item:
    """Done when built, or when its build finishes before its tile loads
    with takeoff now (the margin is the detail); else the wait until it
    would."""
    item = _jobs_item(key, jobs, ends)
    if item.state in ("done", "failed"):
        return item
    late = max((ends[id(j)] - j.deadline_s for j in jobs if id(j) in ends),
               default=0.0)
    if late <= 0:
        return Item(key, "done", 0.0, "Ready %d min before it loads"
                    % math.floor(-late / 60.0))
    return item._replace(eta_s=late)


def readiness_items(facts: Facts) -> List[Item]:
    """The rows of §6.2, in order.  The flight is ready when every row
    of :data:`READY_KEYS` is ``done`` (the departure area); the others
    say how the rest of the route stands."""
    jobs = list(facts.jobs)
    ends = {id(j): end for j, end in finish_times(jobs, facts.slots)}

    def role(name: str) -> List[Job]:
        return [j for j in jobs if j.role == name]

    if not facts.world_installed:
        world = Item("world", "blocked", None, "Install the World pack")
    elif facts.xplane_running and facts.world_seen is False:
        world = Item("world", "blocked", None, "Restart X-Plane once")
    else:
        world = Item("world", "done", 0.0, "")
    rows = [world,
            _flag_item("budget", facts.budget_fits, facts.budget_detail),
            _flag_item("network", True if facts.all_on_disk else facts.network_ok,
                       facts.network_detail or "Needs internet"),
            Item("prefetch", "done", 0.0, "") if facts.prefetch_done
            else Item("prefetch", "working", None, ""),
            _jobs_item("departure", role("departure"), ends),
            _jobs_item("first_window", [j for j in role("enroute") if j.klass == P0],
                       ends)]
    flying = facts.flight_slots or facts.slots
    in_air = ({id(j): end for j, end in finish_times(jobs, flying)}
              if flying != facts.slots else ends)
    route = [j for j in role("enroute") if j.klass != P0 and id(j) in in_air]
    late = [j for j in route if in_air[id(j)] > j.deadline_s]
    if not late:
        rows.append(Item("route", "done", 0.0, ""))
    else:
        rows.append(Item("route", "working", None,
                         "Builds in flight; %d tile(s) may show X-Plane's "
                         "own scenery at this speed" % len(late)))
    rows.append(_deadline_item("destination", role("destination"), ends))
    if facts.build_alternate:
        rows.append(_deadline_item("alternate", role("alternate"), ends))
    if not facts.flight_loaded or facts.loaded_real:
        rows.append(Item("loaded", "done", 0.0, ""))
    else:
        rows.append(Item("loaded", "waiting", None,
                         "Reload scenery when you choose"))
    return rows


def countdown_text(seconds: Optional[float]) -> str:
    """"Ready in about 12 min"; a dash when there is no defensible figure."""
    if seconds is None:
        return "Ready in —"
    if seconds <= 0:
        return "Ready"
    if seconds < 60:
        return "Ready in under a minute"
    return "Ready in about %d min" % math.ceil(seconds / 60.0)
