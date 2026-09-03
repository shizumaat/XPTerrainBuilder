"""Parallel tile builds: the phase-aware subprocess orchestrator
(docs/specs/parallel-tile-builds.md).

One :class:`ParallelBuildRun` drives a run in which up to N tiles build
concurrently, each inside its own worker child process running the
existing JSON-lines engine transport (``Ortho4XP.py --engine-jsonl``).

The parent dispatches ONE STEP AT A TIME (spec §3.8): every ``build``
command a child receives selects a single step key, so the parent knows
and controls each tile's phase.  Steps belong to resource classes; the
two NETWORK classes ("osm" for vector, "imagery") carry concurrency caps
(four each) so a forty-tile queue can never stampede the OpenStreetMap
or imagery servers.  COMPUTE admission is the machine's logical core
count, bounded by a projection of the admitted steps' peak memory
against 80 % of the memory the machine could hand out when the run
started (owner rulings 2026-07-30, docs/specs/
apron-string-and-scheduling-spec.md §A.2) — within that, processor
arbitration is the operating system's job (2026-07-17 owner ruling).

Two things move a tile OUT of a fetch class.  A step may change class
MID-FLIGHT: the vector step holds its network token only while it
fetches, then runs the auto-patch solve under the compute class
(``VECTOR_SOLVE_CLASS``), and the imagery step likewise hands its token
back when its download queue drains and converts to DDS under
``IMAGERY_TAIL_CLASS``.  And a tile whose inputs are ALREADY ON DISK
never takes a fetch token at all: each fetch subsystem answers for
itself through an ``is_cached(tile)`` predicate co-located with its own
fetch code (``STEP_FETCH_SUBSYSTEMS``), so the scheduler never
re-derives what a step will read.  The parent-side OpenStreetMap cache
warmer below takes an osm token like any other fetcher.

A child whose next step's class is full waits idle (a between-steps
child holds almost nothing — the pipeline communicates through files).
When capacity frees, blocked children are dispatched finish-first
(later steps before earlier ones, work in progress drains before new
tiles enter).

Children are reused across steps and tiles (one interpreter start-up
per slot), except after a mid-step cancel, where the child is retired
and a fresh one spawned so a red-flagged interpreter never carries
state forward.  The child's per-step ``BuildDone`` / ``TileState(done)``
/ ``RunDone`` events are consumed as scheduling signals; the parent
forwards tile-level terminals only when a tile's LAST step completes,
and remaps ``StepProgress`` percent from the child's single-step window
into the tile's full-plan window, so views see exactly the stream a
whole-tile build produced.

No GUI-toolkit imports (core-module rule).  The session owns run
lifecycle bookkeeping; this module reports back through
``session._emit`` and ``session._run_finished``.
"""

from __future__ import annotations

import dataclasses
import json
import os
import subprocess
import sys
import threading
import time
from collections import deque
from typing import Optional

import O4_UI_Utils as UI

from . import events as EVENTS
from . import tile_time_model
from .events import (BuildDone, RunDone, RunEta, StepProgress, TileClocks,
                     TileState)
from .session import (
    _predict_step_seconds, plan_steps, prediction_features,
    reweight_plan_by_seconds,
)


def estimate_remaining_wall_seconds(estimates, programs, queued_tiles,
                                    next_step_index, in_flight_steps,
                                    now, slots, live_step_remaining=None):
    """Advisory wall-clock remaining estimate for a parallel run.

    Work model: every queued tile contributes its full predicted plan;
    every active tile contributes its remaining steps.  An in-flight
    step with a LIVE child report (``live_step_remaining``, harvested
    from the worker's own RunEta — bar rates, the auto-patch model and
    meter floors the parent cannot see) is priced at that report, aged
    by its own staleness; otherwise it is credited for its elapsed time
    (degrading into overrun-proportional remaining once it outlives its
    prediction — see :func:`tile_time_model.remaining_step_seconds`).
    The wall clock is a MAKESPAN, not a fluid: a tile is bound to one
    worker, so the run can never end before the longest single tile's
    own remaining chain (owner report 2026-07-28: tiles of 6 min and
    1 min on 2 slots showed "3 min" total — total-work ÷ slots underran
    the longest tile).  Per-tile remainders are packed longest-first
    onto ``slots`` workers (active tiles keep the worker they hold) and
    the estimate is the fullest worker's load — with every tile already
    running this reduces to max(per-tile remaining), exactly the
    per-tile clocks' longest row.  Still coarse (class limits and the
    memory gate are not modelled).  Returns ``None`` when no work
    remains.

    ``estimates``: ``{tile: {step: seconds}}``; ``programs``:
    ``{tile: ordered step keys}`` (batches enqueued into a live run may
    select different steps); ``next_step_index``:
    ``{tile: index of the running-or-next step}``; ``in_flight_steps``:
    ``{(tile, step): started_at}``; ``live_step_remaining``:
    ``{(tile, step): (seconds, received_at)}``.
    """
    live_step_remaining = live_step_remaining or {}
    # A child reports at ~1 Hz; a report much older than that belongs
    # to a wedged or dying child and the model estimate is honester.
    live_report_max_age = 10.0

    def step_estimate(tile, key):
        value = (estimates.get(tile) or {}).get(key)
        if isinstance(value, (int, float)) and value > 0:
            return float(value)
        return None

    active_remaining = []       # tiles holding a worker right now
    queued_remaining = []       # tiles waiting for a slot
    for tile in queued_tiles:
        tile_work = 0.0
        for key in programs.get(tile, ()):
            estimate = step_estimate(tile, key)
            if estimate is not None:
                tile_work += estimate
        queued_remaining.append(tile_work)
    for tile, index in next_step_index.items():
        tile_work = 0.0
        for position, key in enumerate(programs.get(tile, ())):
            if position < index:
                continue
            estimate = step_estimate(tile, key)
            started_at = in_flight_steps.get((tile, key))
            if started_at is not None:
                live = live_step_remaining.get((tile, key))
                if live is not None and now - live[1] <= live_report_max_age:
                    estimate = max(live[0] - (now - live[1]), 0.0)
                else:
                    estimate = tile_time_model.remaining_step_seconds(
                        estimate, now - started_at)
            elif estimate is None:
                continue
            tile_work += estimate
        active_remaining.append(tile_work)
    if not active_remaining and not queued_remaining:
        return None
    # Longest-first packing onto the workers.  Active tiles seed the
    # loads (each already owns its worker); queued tiles land on the
    # least-loaded worker as one becomes free.
    n_workers = max(1, int(slots))
    loads = sorted(active_remaining, reverse=True)[:n_workers]
    loads += [0.0] * (n_workers - len(loads))
    for tile_work in sorted(queued_remaining, reverse=True):
        loads.sort()
        loads[0] += tile_work
    return max(loads)


def per_tile_clock_rows(estimates, programs, queued_tiles, next_step_index,
                        in_flight_steps, now, live_step_remaining,
                        first_started, final_elapsed):
    """The TileClocks rows for a parallel run (protocol 1.3).

    Same inputs and step-pricing rules as
    :func:`estimate_remaining_wall_seconds` — an in-flight step takes the
    child's live report (aged), else the model degraded by elapsed — but
    summed PER TILE and never divided by slots: a tile's remaining figure
    is its OWN outstanding work, while the run-level RunEta stays the
    slot-aware wall clock.  ``first_started``/``final_elapsed`` are the
    parent's wall stamps ({tile: t} / {tile: seconds}); a tile with no
    priced step at all reports None (the dash), never a guess.
    """
    live_step_remaining = live_step_remaining or {}
    live_report_max_age = 10.0
    queued = set(queued_tiles)
    rows = []
    for tile in programs:
        final = final_elapsed.get(tile)
        if final is not None:
            rows.append((int(tile[0]), int(tile[1]),
                         round(max(0.0, final), 1), 0.0, True))
            continue
        started = first_started.get(tile)
        elapsed = (now - started) if started is not None else 0.0
        index = 0 if tile in queued else next_step_index.get(tile, 0)
        total = 0.0
        have_basis = False
        for position, key in enumerate(programs.get(tile, ())):
            if position < index:
                have_basis = True
                continue
            value = (estimates.get(tile) or {}).get(key)
            estimate = (float(value)
                        if isinstance(value, (int, float)) and value > 0
                        else None)
            started_at = in_flight_steps.get((tile, key))
            if started_at is not None:
                live = live_step_remaining.get((tile, key))
                if live is not None and now - live[1] <= live_report_max_age:
                    estimate = max(live[0] - (now - live[1]), 0.0)
                else:
                    estimate = tile_time_model.remaining_step_seconds(
                        estimate, now - started_at)
            elif estimate is None:
                continue
            total += estimate
            have_basis = True
        rows.append((int(tile[0]), int(tile[1]),
                     round(max(0.0, elapsed), 1),
                     total if have_basis else None, False))
    return tuple(rows)

# Seconds to wait for a freshly spawned worker's EngineHello line before
# declaring the spawn failed (interpreter start + light imports only —
# the heavy pipeline imports happen later, inside the build command).
HANDSHAKE_TIMEOUT_SECONDS = 30.0

# Cancel escalation: how long a mid-step child gets to honor its red
# flag before SIGTERM (the pipeline's cancellation checkpoints answer
# within a few seconds; a blocking network request can hold this long),
# and how long SIGTERM's bounded wind-down gets before SIGKILL.
CANCEL_ESCALATE_SECONDS = 12.0
CANCEL_KILL_SECONDS = 15.0

# How often the parent-side cache warmer re-tries for an osm token when
# the class is full (spec §A.3: the warmer is a fetcher and takes a token
# like any other).  It drops its warming claim between tries, so a
# waiting warmer never keeps its tile off the workers.
WARM_TOKEN_POLL_SECONDS = 0.05

# Resource classes (spec §3.8): which shared resource each step leans
# on, and how many tiles may occupy a class at once.  The two network
# classes are SEPARATE because they exhaust separate servers — a tile
# downloading OpenStreetMap data must not steal budget from the imagery
# phase, which dominates total build time (the goal is minimal makespan
# for the whole queue).  Compute steps are UNCAPPED (the class exists
# only for bookkeeping): the 2026-07-17 owner ruling leaves processor
# arbitration to the operating system — the caps that remain guard
# REMOTE SERVERS, plus the mesh memory admission gate below for the
# one machine cliff the operating system handles badly.
STEP_CLASSES = {
    "vector": "osm",
    "imagery": "imagery",
    "mesh": "compute",
    "masks": "compute",
    "overlays": "compute",
}
# The vector step is a HYBRID (owner ruling 2026-07-30,
# docs/specs/vector-step-class-split-spec.md): it FETCHES remote vector
# data and then runs the auto-patch SOLVE, the heaviest pure-processor
# phase in the product (minutes per airport).  The step therefore holds
# its osm token only while fetching; when the child reports
# AutoPatchBegin the token is released — immediately available to a
# queued tile that needs to FETCH — and the tile continues under this
# class for the duration of the solve.  When the last airport reports
# its terminal, the remainder of the vector step (roads/coastline/water
# encoding, which may still touch the network on a cache miss) takes an
# osm token back.  Setting this to "osm" restores the pre-2026-07-30
# behaviour exactly (the swap becomes a no-op) — the before/after arm of
# the acceptance measurement uses that.
VECTOR_SOLVE_CLASS = "compute"

# The imagery step is hybrid for the same reason the vector step is
# (docs/specs/apron-string-and-scheduling-spec.md §A.2): it DOWNLOADS a
# mesh-derived texture set and then converts it to DDS locally, and the
# conversion tail is pure processor work that no remote server cares
# about.  The tile releases its imagery token when the child reports
# ImageryDownloadsDone (O4_Tile_Utils, at the download queue's drain)
# and finishes the step under this class.  Setting it to "imagery"
# restores the pre-2026-07-30 behaviour exactly.
IMAGERY_TAIL_CLASS = "compute"

# The two NETWORK classes.  A tile occupies one of them only while it may
# issue remote requests.
FETCH_CLASSES = ("osm", "imagery")
# Where a tile whose inputs are already on disk is admitted instead: a
# cached tile issues no remote request, so holding a fetch token would
# only keep a genuinely cold tile out of the servers' way (owner ruling
# 2026-07-30 — "I could run as many tiles as I have cores concurrently
# if they have all their data downloaded").
CACHED_STEP_CLASS = "compute"

OSM_CLASS_LIMIT = 4
IMAGERY_CLASS_LIMIT = 4
# The pre-2026-07-30 caps, restored when the admission gate below is off
# — the BEFORE arm of the acceptance measurement, and the gate-off
# byte-identity proof.
LEGACY_OSM_CLASS_LIMIT = 2
LEGACY_IMAGERY_CLASS_LIMIT = 2
# Environment overrides for the two REMOTE-SERVER caps, for operators
# whose Overpass/imagery endpoints tolerate more (spec §3.1).  A
# non-numeric or non-positive value is ignored.
OSM_CLASS_LIMIT_ENVIRONMENT_KEY = "O4_OSM_CLASS_LIMIT"
IMAGERY_CLASS_LIMIT_ENVIRONMENT_KEY = "O4_IMAGERY_CLASS_LIMIT"

# The named gate for the whole of Part A (spec Acceptance: "every part is
# default-ON behind a named env gate ... with gate-off byte-identity").
# Off restores the pre-2026-07-30 scheduler exactly: 2/2 fetch caps,
# compute bounded by the slot count, no cached-tile bypass, an untokened
# cache warmer and no imagery-tail release.
CACHE_AWARE_ADMISSION_ENVIRONMENT_KEY = "O4_CACHE_AWARE_ADMISSION"
_GATE_OFF_VALUES = ("0", "false", "no", "off")


def cache_aware_admission_enabled():
    """Is cache-aware admission (spec Part A) active?  Default yes."""
    value = os.environ.get(CACHE_AWARE_ADMISSION_ENVIRONMENT_KEY)
    if value is None:
        return True
    return str(value).strip().lower() not in _GATE_OFF_VALUES


def _limit_from_environment(key, default):
    try:
        value = int(os.environ.get(key, "").strip())
    except (AttributeError, TypeError, ValueError):
        return default
    return value if value >= 1 else default


def osm_class_limit():
    """How many tiles may FETCH OpenStreetMap data at once."""
    return _limit_from_environment(
        OSM_CLASS_LIMIT_ENVIRONMENT_KEY,
        OSM_CLASS_LIMIT if cache_aware_admission_enabled()
        else LEGACY_OSM_CLASS_LIMIT)


def imagery_class_limit():
    """How many tiles may occupy the imagery servers at once."""
    return _limit_from_environment(
        IMAGERY_CLASS_LIMIT_ENVIRONMENT_KEY,
        IMAGERY_CLASS_LIMIT if cache_aware_admission_enabled()
        else LEGACY_IMAGERY_CLASS_LIMIT)


def compute_class_limit(slots):
    """How many tiles may run a COMPUTE step at once.

    The machine's LOGICAL CORE COUNT (owner ruling 2026-07-30: "I could
    run as many tiles as I have cores concurrently if they have all
    their data downloaded"; "I think we can let the machine manage the
    CPU").  Memory is bounded separately and per step, by the projection
    gate below — the review of revision 1 showed a cores-ONLY rule
    admitting 16 tiles where the old formula admitted 5, which is why
    both bounds exist.  Gate off: the slot count, as before.
    """
    if not cache_aware_admission_enabled():
        return slots
    import O4_Parallel_Utils as PARALLEL_UTILS

    return max(1, PARALLEL_UTILS.machine_core_count())


def class_limits(slots):
    """Per-class concurrency caps for a run of ``slots`` children."""
    return {
        "osm": min(osm_class_limit(), slots),
        "imagery": min(imagery_class_limit(), slots),
        "compute": compute_class_limit(slots),
    }


# Rough peak mesh-step memory per tile (gigabytes) by elevation detail
# level (docs/specs/elevation-level-spec.md sizing: working raster plus
# smoothing/bake copies).  Drives the mesh admission gate below, so one
# 1 m island tile in a forty-tile queue is scheduled around, not
# alongside, other big rasters.
MESH_MEMORY_ESTIMATES_GB = {
    "auto": 2.0,
    "coastline": 3.0,
    # "90" pins the auto base class (dem3 upsampled onto the same
    # 1 arc-second working grid), so its mesh footprint is auto's.
    "90": 2.0,
    "30": 1.5,
    "10": 3.0,
    "5": 8.0,
    "1": 18.0,
}
MESH_MEMORY_DEFAULT_GB = 2.0
# Gigabytes kept free for the operating system, the application, and the
# non-mesh phases of concurrently building tiles.
MESH_MEMORY_HEADROOM_GB = 4.0


def mesh_memory_estimate_gigabytes(elevation_level_value):
    """Estimated peak mesh memory for a tile's ``elevation_level``."""
    if elevation_level_value is None:
        return MESH_MEMORY_DEFAULT_GB
    key = str(elevation_level_value).strip().lower()
    return MESH_MEMORY_ESTIMATES_GB.get(key, MESH_MEMORY_DEFAULT_GB)


def mesh_memory_budget_gigabytes():
    """Total gigabytes the run may commit to concurrent mesh steps.

    The pre-2026-07-30 budget, still used when the cache-aware admission
    gate is off (see :func:`step_memory_budget_gigabytes`).
    """
    import O4_Parallel_Utils as PARALLEL_UTILS

    return max(
        4.0,
        PARALLEL_UTILS.machine_memory_gigabytes() - MESH_MEMORY_HEADROOM_GB,
    )


# Peak working-set estimates for the steps OTHER than mesh (gigabytes),
# extending the mesh sizing above to "any step with a memory estimate"
# (spec §A.2).  Deliberately coarse: their job is to stop a cores-wide
# compute admission committing more memory than the machine has, not to
# model a step.  A step absent from this table projects nothing and is
# admitted on the core count alone.
#
# Provenance, honestly: only the VECTOR figure is measured — a live
# auto-patch build (HECA, 2026-07-30) held 2.55-2.56 GB resident at
# 100 % of one core across a five-sample window, and the vector step
# runs that solve after its own OSM parse, so it is rounded UP to 3.0.
# A worker with the whole pipeline imported and nothing running is
# 0.12 GB, so the others are that baseline plus a deliberately generous
# working-set allowance, NOT measurements; refine them when a
# per-step peak-RSS measurement exists.
STEP_MEMORY_ESTIMATES_GB = {
    "vector": 3.0,     # measured: OSM parse + the auto-patch solve
    "masks": 1.0,      # estimate
    "imagery": 1.5,    # estimate: download buffers + the DDS convert pool
    "overlays": 0.5,   # estimate
}


def step_memory_budget_gigabytes():
    """Gigabytes a run may PROJECT onto its concurrently admitted steps.

    ``MEMORY_CEILING_FRACTION`` (80 %, owner ruling 2026-07-30) of the
    memory the machine can hand out.  Sampled ONCE per run, on purpose:
    re-sampling it live would make the run's own consumption shrink its
    own budget — a feedback loop that starves admission rather than
    gating it — and would make the gate untestable.  Floored at one
    default estimate so a single tile can never deadlock.
    """
    import O4_Parallel_Utils as PARALLEL_UTILS

    return max(
        MESH_MEMORY_DEFAULT_GB,
        PARALLEL_UTILS.machine_available_memory_gigabytes()
        * PARALLEL_UTILS.MEMORY_CEILING_FRACTION,
    )


# ---------------------------------------------------------------------
# Cache determination (spec §A.2): per-subsystem predicates, never a
# scheduler-side re-derivation
# ---------------------------------------------------------------------
# Which fetch subsystems each step's REMOTE traffic comes from.  This
# table is the whole of the scheduler's knowledge: it never re-derives
# "what will this step read" — that duplicated derivation is exactly
# what drifts (scheduler says cached, step fetches anyway, the fetch cap
# is breached silently).  Each name resolves to a module-level
# ``is_cached(tile)`` co-located with that subsystem's fetch code, which
# is cheap, filesystem/manifest-only, never a network probe, and answers
# False for anything it cannot decide.
STEP_FETCH_SUBSYSTEMS = {
    # The vector step downloads OSM layers, prepares the DEM (base tiles
    # plus airport elevation insets), kicks the bathymetry band prefetch
    # and runs the auto-patch airport builds.
    "vector": (
        "O4_Vector_Map",
        "O4_DEM_Utils",
        "O4_Airport_Elevation_Insets",
        "O4_Bathymetry_Band",
        "auto_patch.osm_load",
    ),
    "imagery": ("O4_Tile_Utils",),
}


_PREDICATES: dict = {}
_PREDICATES_LOCK = threading.Lock()


def preload_cache_predicates():
    """Import the fetch subsystems and register their predicates.

    Run OFF the dispatch path (a daemon thread at run start): importing
    these modules pulls the whole pipeline into the FRONT-END process,
    which must never happen while the scheduler lock is held — that is
    the 2026-07-17 "build appears hung" shape all over again.  Until the
    preload finishes, no subsystem can answer and every tile is treated
    as NOT cached, which is simply the pre-2026-07-30 behaviour.
    """
    for module_name in sorted({
        name
        for names in STEP_FETCH_SUBSYSTEMS.values()
        for name in names
    }):
        predicate = None
        try:
            module = __import__(module_name, fromlist=["is_cached"])
            predicate = getattr(module, "is_cached", None)
        except Exception:
            predicate = None
        with _PREDICATES_LOCK:
            _PREDICATES[module_name] = predicate or False


def _subsystem_is_cached(module_name):
    """One subsystem's registered ``is_cached`` predicate, or ``None``.

    ``None`` means "cannot answer" — not yet preloaded, unimportable, or
    a subsystem that publishes no predicate — and every caller reads that
    as NOT cached.
    """
    with _PREDICATES_LOCK:
        predicate = _PREDICATES.get(module_name)
    return predicate or None


def cache_predicates_ready(step_key):
    """Can every subsystem this step fetches from answer for itself?"""
    return all(
        _subsystem_is_cached(module_name) is not None
        for module_name in STEP_FETCH_SUBSYSTEMS.get(step_key, ())
    )


def tile_inputs_are_cached(tile_configuration, step_key):
    """Would this step of this tile issue NO remote request?

    Asks every subsystem the step fetches from, in order, and stops at
    the first that says no.  ``tile_configuration`` is a configured
    ``O4_Config_Utils.Tile``.  A step with no fetch subsystems (mesh,
    masks, overlays) is trivially cached; so is a step whose subsystems
    all answer yes.  Anything else — a subsystem that cannot answer, a
    predicate that raises — is NOT cached.
    """
    for module_name in STEP_FETCH_SUBSYSTEMS.get(step_key, ()):
        predicate = _subsystem_is_cached(module_name)
        if predicate is None:
            return False
        try:
            if not predicate(tile_configuration):
                return False
        except Exception:
            return False
    return True


# Event types forwarded verbatim (modulo remapping/suppression, spec
# §3.8) from a child stream into the parent session.  Everything else is
# child-run-level (hello, run clock, run end) or impossible from a
# worker (scan events) and is suppressed; the parent emits its own.
_FORWARDED_EVENT_TYPES = (
    "TileState",
    "StepProgress",
    "BuildDone",
    "AutoPatchBegin",
    "AutoPatchProgress",
    # H1: the per-airport failure DIAGNOSIS must survive the child→parent
    # hop, or a parallel run degrades back to the silent class this event
    # exists to close (docs/POSTMORTEM-20260831.md Task C).
    "AutoPatchFailed",
    "Log",
)

_EVENT_CLASSES = {
    name: value
    for name, value in vars(EVENTS).items()
    if isinstance(value, type)
    and issubclass(value, EVENTS.EngineEvent)
    and value is not EVENTS.EngineEvent
}


def tile_worker_command():
    """The argv launching one worker child.

    From source: ``[python, <repo>/Ortho4XP.py, --engine-jsonl]``.  In
    the frozen application the executable serves as its own worker via
    the same early argv branch in ``Ortho4XP_Qt.py``.  Module-level so
    tests can substitute a stub worker script.
    """
    # --engine-worker marks a parallel-build CHILD: the entry branches
    # skip application-process work (extract maintenance) for it.
    if getattr(sys, "frozen", False):
        return [sys.executable, "--engine-jsonl", "--engine-worker"]
    repository_root = os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    )
    return [
        sys.executable,
        os.path.join(repository_root, "Ortho4XP.py"),
        "--engine-jsonl",
        "--engine-worker",
    ]


def _short_latlon(tile):
    lat, lon = tile
    return "%+03d%+04d" % (lat, lon)


def _rebuild_event(payload):
    """Parse one child event line back into a typed event, or ``None``.

    Additive-protocol rules: unknown event types and unknown fields are
    dropped silently.  ``seq``/``ts`` are discarded — the parent session
    re-stamps both at re-emission.
    """
    event_name = payload.get("event")
    event_class = _EVENT_CLASSES.get(event_name)
    if event_class is None:
        return None
    field_names = {
        f.name for f in dataclasses.fields(event_class)
    } - {"seq", "ts"}
    kwargs = {k: v for k, v in payload.items() if k in field_names}
    # JSON turns tuples into lists; the tuple-typed forwarded field is
    # normalized back so in-process and merged streams look alike.
    if "airports" in kwargs and isinstance(kwargs["airports"], list):
        kwargs["airports"] = tuple(
            tuple(a) if isinstance(a, list) else a
            for a in kwargs["airports"]
        )
    try:
        return event_class(**kwargs)
    except Exception:
        return None


class _WorkerChild:
    """One worker subprocess: process handle, stream threads, state."""

    def __init__(self, run, index):
        self.run = run
        self.index = index
        self.process: Optional[subprocess.Popen] = None
        self.tile = None               # tile this child is carrying
        self.running_step = None       # step key in flight, None = waiting
        # The resource class this child OCCUPIES right now (None between
        # steps).  Usually STEP_CLASSES[running_step], but the vector
        # step swaps to VECTOR_SOLVE_CLASS for the auto-patch solve, so
        # the release path must read what is held, never re-derive it
        # from the step key — that is also what makes the release
        # crash-safe (the pool's reaping path releases this same field).
        self.step_class = None
        # Airports still solving while this child is in the auto-patch
        # phase of its vector step (None outside that phase).
        self.autopatch_pending = None
        # The child's own live in-step estimate: (step_key, seconds,
        # received_at).  A worker child runs a full EngineSession whose
        # tracker sees the live signals the parent cannot (bar rates,
        # the auto-patch model, download/task meter floors); its RunEta
        # is harvested here instead of being discarded with the other
        # run-level events.
        self.live_remaining = None
        self.step_failed = False       # current tile had a failing step
        self.cancelling = False        # a mid-step cancel is in flight
        self.retired = False
        self.hello = threading.Event()
        self._stdin_lock = threading.Lock()
        self._command_id = 0

    # -- lifecycle -----------------------------------------------------
    def spawn(self):
        """Start the process and its stream threads; await the handshake.

        Returns True when the child produced its EngineHello in time.
        """
        try:
            # Children learn their sibling count so their own Auto slot
            # resolutions (DDS conversion, downloads) share the machine.
            child_environment = dict(os.environ)
            child_environment["O4_PARALLEL_BUILD_SIBLINGS"] = str(
                self.run._slots)
            # The child's parent-death watchdog probes this pid directly
            # (jsonl owns_process mode), so a front end that dies without
            # collapsing the stdin pipe still takes its workers with it.
            child_environment["O4_PARENT_PROCESS_ID"] = str(os.getpid())
            # No ``cwd=`` and ``close_fds=False``: both force CPython off
            # posix_spawn onto fork+exec, and a fork in a pyproj-loaded
            # parent segfaults in the proj.db sqlite atfork handler
            # before exec ever runs (the 2026-07-16 crash class; observed
            # again 2026-07-23 as a crash-report loop when a test process
            # with the full pipeline imported spawned workers).  The
            # from-source child re-anchors its own cwd at entry instead
            # (Ortho4XP.py --engine-jsonl); leaving close_fds off is safe
            # since PEP 446 makes descriptors non-inheritable by default.
            self.process = subprocess.Popen(
                tile_worker_command(),
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                env=child_environment,
                close_fds=False,
            )
        except Exception as error:
            print("Could not start a build worker process:", error)
            return False
        threading.Thread(target=self._read_events, daemon=True).start()
        threading.Thread(target=self._drain_stderr, daemon=True).start()
        if not self.hello.wait(HANDSHAKE_TIMEOUT_SECONDS):
            print("Build worker", self.index,
                  "did not answer in time; giving up on it.")
            self.terminate()
            return False
        return True

    def send(self, command):
        try:
            with self._stdin_lock:
                self._command_id += 1
                command = dict(command, id=self._command_id)
                self.process.stdin.write(json.dumps(command) + "\n")
                self.process.stdin.flush()
            return True
        except Exception:
            return False

    def start_step(self, step_key, build_arguments):
        """Send one single-step build command for this child's tile.

        ``slots=1`` is explicit: a worker child must run its step
        in-process, never orchestrate worker grandchildren of its own,
        whatever its own configuration would resolve to.
        """
        self.running_step = step_key
        self.live_remaining = None
        return self.send(dict(
            build_arguments,
            cmd="build",
            tiles=[[self.tile[0], self.tile[1]]],
            steps=[step_key],
            slots=1,
        ))

    def retire(self):
        """Close the child down gracefully (EOF ends jsonl.serve)."""
        self.retired = True
        try:
            self.process.stdin.close()
        except Exception:
            pass

    def terminate(self):
        self.retired = True
        try:
            self.process.terminate()
        except Exception:
            pass

    # -- stream threads --------------------------------------------------
    def _read_events(self):
        try:
            for line in self.process.stdout:
                line = line.strip()
                if not line:
                    continue
                try:
                    payload = json.loads(line)
                except ValueError:
                    continue
                if payload.get("event") == "EngineHello":
                    self.hello.set()
                    continue
                if "event" in payload:
                    self.run._on_child_event(self, payload)
        except Exception:
            pass
        self.run._on_child_exit(self)

    def _drain_stderr(self):
        """Pipeline prints and crash text, re-printed with attribution so
        the interleaved console stays readable."""
        try:
            for line in self.process.stderr:
                tile = self.tile
                prefix = ("[%s] " % _short_latlon(tile)) if tile else (
                    "[worker %d] " % self.index)
                print(prefix + line.rstrip("\n"))
        except Exception:
            pass


class ParallelBuildRun:
    """The phase-aware orchestrator for one parallel run (spec §3.1–3.8)."""

    def __init__(self, session, tiles, provider, zoomlevel,
                 custom_build_dir, step_flags, slots):
        self._session = session
        self._queue = deque()
        self._total = 0
        self._slots = slots
        # Per-tile build state: a batch enqueued into a LIVE run may
        # carry different build arguments (imagery source, zoom level,
        # output folder, step selection) than the batch that started it,
        # so everything the dispatcher needs is keyed by tile.
        self._tile_arguments: dict = {}   # tile -> child build kwargs
        self._programs: dict = {}         # tile -> ordered step keys
        self._static_windows: dict = {}   # tile -> {step: (base, width)}
        # Learned per-tile step estimates (tile_time_model): drive the
        # run clock (spec §3.3 upgraded from the honest dash) and
        # re-scale each tile's percent windows to predicted seconds.
        # Purely advisory — failure keeps the static windows and the
        # dash.
        self._estimates: dict = {}
        self._tile_step_windows: dict = {}
        self._step_started_at: dict = {}      # (tile, step) -> monotonic t
        # Per-tile wall clocks (TileClocks, protocol 1.3): first step
        # start stamp + frozen final elapsed at the tile's terminal.
        self._tile_first_started: dict = {}   # tile -> wall time
        self._tile_final_elapsed: dict = {}   # tile -> seconds
        # tile -> summed dispatched-step seconds, for the per-tile
        # "completed in" console line (a worker child sees one step at a
        # time, so only the parent can total the tile).
        self._tile_step_seconds: dict = {}
        self._class_limits = class_limits(slots)
        self._class_active = {name: 0 for name in self._class_limits}
        self._next_step_index: dict = {}
        # Children spawn believing `slots` siblings share the machine;
        # broadcasts below shrink that as tiles finish (see
        # _broadcast_sibling_count).
        self._sibling_broadcast = slots
        # Memory-aware admission (spec §3.8, widened by
        # apron-string-and-scheduling §A.2 from the mesh step to every
        # step with an estimate).  Per-tile MESH estimates come from each
        # tile's configured elevation detail level; the other steps take
        # the flat STEP_MEMORY_ESTIMATES_GB sizing.  The budget is
        # sampled ONCE (see step_memory_budget_gigabytes) and at least
        # one step is always admitted, so no single tile can deadlock.
        self._mesh_memory_estimates: dict = {}
        self._memory_budget = (
            step_memory_budget_gigabytes()
            if cache_aware_admission_enabled()
            else mesh_memory_budget_gigabytes())
        self._memory_in_use = 0.0
        self._memory_holders: dict = {}   # (tile, step) -> gigabytes
        # Cache-aware fetch admission (spec §A.2): the per-subsystem
        # predicates' verdict per (tile, step), memoised because a tile's
        # first step is re-evaluated on every dispatch sweep and the
        # predicates, while cheap, are not free.  A tile's configured
        # Tile object is built once and shared by all five predicates
        # (the single-pass principle), never rebuilt per subsystem.
        self._cache_state: dict = {}
        self._tile_configurations: dict = {}
        # The parent-side cache warmer holds an osm token exactly like
        # any other fetcher while it downloads (spec §A.3, binding
        # invariant).
        self._warm_token_held = False
        self._lock = threading.Lock()
        self._children: list = []
        self._next_child_index = 0
        self._done = 0
        self._errors = 0
        self._cancel_all = False
        self._finished = False
        self._t0 = time.time()
        # OpenStreetMap cache warmer state (spec §3.7): the tile whose
        # caches are being downloaded right now (assignment waits for
        # it), the tiles already warmed, and whether the warmer thread
        # is alive (an enqueue may need to revive it).
        self._warming_tile = None
        self._warmed_tiles: set = set()
        self._warmer_running = False
        # Per-tile progress high-water marks: the legacy in-step bars
        # oscillate within a step (they refill per OpenStreetMap layer,
        # per download phase, ...), which the historic single-bar view
        # hid but a per-tile bar shows as jumping.  The forwarder
        # ratchets: a tile's displayed percent only ever advances.
        self._percent_high_water: dict = {}
        with self._lock:
            self._admit_batch_locked(tiles, provider, zoomlevel,
                                     custom_build_dir, step_flags)

    def _admit_batch_locked(self, tiles, provider, zoomlevel,
                            custom_build_dir, step_flags):
        """Register a batch of tiles with the run (caller holds the lock).

        Tiles already part of the run (queued or on a child) are skipped
        — re-queueing a tile that already FINISHED is allowed and treats
        it as new work.  Returns the tiles actually admitted, already
        appended to the queue.
        """
        do_vector, do_imagery, do_overlays = step_flags
        full_plan = plan_steps(do_vector, do_imagery, do_overlays)
        program = [key for (key, _base, _width) in full_plan]
        if not program:
            return []
        admitted = []
        for tile in tiles:
            if (tile in self._queue or tile in self._next_step_index
                    or any(child.tile == tile
                           for child in self._children)):
                continue
            admitted.append(tile)
            self._tile_arguments[tile] = {
                "provider": provider,
                "zoomlevel": zoomlevel,
                "custom_build_dir": custom_build_dir,
            }
            self._programs[tile] = list(program)
            self._static_windows[tile] = {
                key: (base, width) for (key, base, width) in full_plan
            }
            try:
                features = prediction_features(
                    tile[0], tile[1], provider, zoomlevel,
                    custom_build_dir)
                estimates = _predict_step_seconds(
                    tile[0], tile[1], features, program)
                self._estimates[tile] = estimates
                self._tile_step_windows[tile] = {
                    key: (base, width)
                    for (key, base, width) in reweight_plan_by_seconds(
                        full_plan, estimates)
                }
            except Exception:
                self._estimates.pop(tile, None)
                self._tile_step_windows.pop(tile, None)
            self._mesh_memory_estimates[tile] = (
                self._estimate_mesh_memory(tile, custom_build_dir))
            self._percent_high_water.pop(tile, None)
            self._forget_cache_state_locked(tile)
            self._queue.append(tile)
        self._total += len(admitted)
        return admitted

    # -- lifecycle -----------------------------------------------------
    def start(self):
        """Spawn the slot pool and dispatch the first steps.

        The FIRST child is the canary: if it cannot be spawned, the whole
        parallel mode is declared unavailable and the session falls back
        to the in-process worker (spec §3.2).  Later spawn failures just
        shrink the pool.
        """
        # Spawn one child per tile up to the slot cap — never more
        # children than there is work (the cap itself may exceed the
        # starting batch: enqueue grows the pool later).
        with self._lock:
            wanted_children = min(self._slots, len(self._queue))
        if not wanted_children:
            return False
        first = self._spawn_child()
        if first is None:
            return False
        for _ in range(wanted_children - 1):
            if not self._queue:
                # A cancel during the handshake window drained the queue.
                break
            if self._spawn_child() is None:
                print("Fewer build workers than requested could be "
                      "started; continuing with", len(self._children))
                break
        with self._lock:
            self._dispatch_locked()
            self._warmer_running = True
        threading.Thread(target=self._osm_cache_warmer, daemon=True).start()
        threading.Thread(target=self._ticker, daemon=True).start()
        # Import the fetch subsystems' cache predicates off the dispatch
        # path (see preload_cache_predicates): until they land every tile
        # reads as not cached, which is exactly the old behaviour.
        if cache_aware_admission_enabled():
            threading.Thread(
                target=preload_cache_predicates, daemon=True).start()
        # Children spawned believing `slots` siblings share the machine;
        # tell them the real count right away (a two-tile run on four
        # slots must not throttle itself for two ghosts).
        self._broadcast_sibling_count()
        # A cancel that landed during the handshake window may have
        # drained the queue already; settle immediately in that case.
        self._maybe_finish()
        return True

    def enqueue(self, tiles, provider, zoomlevel, custom_build_dir,
                step_flags):
        """Append a batch of tiles to the LIVE run.

        The batch keeps its own build arguments and step selection —
        per-tile state throughout the dispatcher makes mixed batches
        first-class.  Idle children pick the new tiles up immediately;
        if the pool has shrunk (crashed or retired-after-cancel
        children), replacements are spawned off-thread up to the slot
        count.  Returns the number of tiles actually admitted: 0 when
        the run is finishing or cancelled (the caller should start a
        fresh run instead) or when every tile is already part of it.
        """
        with self._lock:
            if self._finished or self._cancel_all:
                return 0
            admitted = self._admit_batch_locked(
                tiles, provider, zoomlevel, custom_build_dir, step_flags)
            if not admitted:
                return 0
            self._dispatch_locked()
            alive = [child for child in self._children
                     if not child.retired]
            missing = max(0, min(self._slots - len(alive),
                                 len(self._queue)))
            revive_warmer = not self._warmer_running
            if revive_warmer:
                self._warmer_running = True

        def _grow_pool_and_dispatch():
            for _ in range(missing):
                if self._spawn_child() is None:
                    break
            with self._lock:
                self._dispatch_locked()
            self._broadcast_sibling_count()

        # Spawning blocks on the worker handshake — never on the
        # caller's (GUI) thread.
        threading.Thread(target=_grow_pool_and_dispatch,
                         daemon=True).start()
        if revive_warmer:
            threading.Thread(target=self._osm_cache_warmer,
                             daemon=True).start()
        self._broadcast_sibling_count()
        return len(admitted)

    def _spawn_child(self):
        """Spawn one worker (blocks on the handshake; never called while
        holding the scheduler lock — a slow spawn must not block
        cancellation or event routing)."""
        with self._lock:
            child = _WorkerChild(self, self._next_child_index)
            self._next_child_index += 1
        if not child.spawn():
            return None
        with self._lock:
            self._children.append(child)
        return child

    # -- the dispatcher (spec §3.8) --------------------------------------
    def _dispatch_locked(self):
        """Start every step that capacity allows (caller holds the lock).

        Blocked children first, finish-first (later steps before earlier
        ones), then idle children pick up new tiles from the queue.
        """
        if self._finished or self._cancel_all:
            return
        blocked = sorted(
            (child for child in self._children
             if child.tile is not None and child.running_step is None
             and not child.retired and not child.cancelling),
            key=lambda child: -self._next_step_index.get(child.tile, 0),
        )
        for child in blocked:
            self._try_start_step_locked(child)
        for child in list(self._children):
            if (child.tile is None and not child.retired
                    and not child.cancelling):
                self._start_new_tile_locked(child)

    @staticmethod
    def _estimate_mesh_memory(tile, custom_build_dir):
        """One tile's mesh memory estimate from its configuration.

        Reads the tile's ``elevation_level`` (per-tile config file, or
        the default when absent); any failure degrades to the default
        estimate — scheduling must never fail on a config hiccup.
        """
        level_value = None
        try:
            import O4_Settings_Model as SETTINGS_MODEL

            raw = SETTINGS_MODEL.read_tile_raw(
                tile[0], tile[1], custom_build_dir)
            level_value = (raw or {}).get("elevation_level")
            if level_value is None:
                # Sparse tile configs (blended model) omit inherited
                # settings: the tile builds with the GLOBAL value.
                level_value = SETTINGS_MODEL.global_effective_value(
                    "elevation_level")
        except Exception:
            level_value = None
        return mesh_memory_estimate_gigabytes(level_value)

    def _forget_cache_state_locked(self, tile):
        """Drop a tile's memoised cache verdicts and its configuration.

        Called whenever something may have changed what is on disk for
        it: a re-queued (previously finished) tile, a completed step, a
        finished warm.  Re-asking is cheap; a stale "not cached" would
        keep a warm tile queueing for a fetch token it does not need.
        """
        for key in [k for k in self._cache_state if k[0] == tile]:
            del self._cache_state[key]
        self._tile_configurations.pop(tile, None)

    def _step_memory_estimate(self, tile, step_key):
        """Projected peak memory (gigabytes) for one step of one tile.

        The mesh step keeps its per-tile elevation-level sizing; the
        other steps take the flat table, but only while the cache-aware
        admission gate is on — with it off the projection is the
        pre-2026-07-30 mesh-only one.
        """
        if step_key == "mesh":
            return self._mesh_memory_estimates.get(
                tile, MESH_MEMORY_DEFAULT_GB)
        if not cache_aware_admission_enabled():
            return 0.0
        return STEP_MEMORY_ESTIMATES_GB.get(step_key, 0.0)

    def _memory_admits_locked(self, tile, step_key):
        """True when the step's projected memory fits the budget now.

        One step is always admitted (a single tile must never deadlock,
        however big its raster); beyond that, the sum of the admitted
        steps' projections stays within the budget — 80 % of the memory
        the machine could hand out when the run started.
        """
        estimate = self._step_memory_estimate(tile, step_key)
        if estimate <= 0.0:
            return True
        if not self._memory_holders:
            return True
        return self._memory_in_use + estimate <= self._memory_budget

    def _tile_configuration(self, tile):
        """This tile's configured ``Tile``, built once and reused.

        The one object every cache predicate is handed (spec §A.2 asks
        each subsystem, not the scheduler, what it needs from it).
        ``None`` when the configuration cannot be read at all — the
        callers treat that as "not cached".
        """
        if tile in self._tile_configurations:
            return self._tile_configurations[tile]
        configuration = None
        try:
            import O4_Config_Utils as CFG

            build_dir = (self._tile_arguments.get(tile)
                         or {}).get("custom_build_dir", "")
            configuration = CFG.Tile(tile[0], tile[1], build_dir)
            configuration.read_from_config()
            arguments = self._tile_arguments.get(tile) or {}
            # The build command's imagery selection is explicit user
            # intent and wins over the recorded config, exactly as the
            # worker's own session applies it before running the step —
            # otherwise the imagery predicate would judge the manifest
            # against the wrong provider.
            if arguments.get("provider"):
                configuration.default_website = arguments["provider"]
            if arguments.get("zoomlevel"):
                configuration.default_zl = arguments["zoomlevel"]
        except Exception:
            configuration = None
        self._tile_configurations[tile] = configuration
        return configuration

    def _fetch_is_cached_locked(self, tile, step_key):
        """Memoised verdict of the per-subsystem cache predicates."""
        key = (tile, step_key)
        if key in self._cache_state:
            return self._cache_state[key]
        if not cache_predicates_ready(step_key):
            # The preload thread has not finished importing the fetch
            # subsystems.  Answer NOT cached and do NOT memoise it —
            # the next dispatch sweep asks again.
            return False
        configuration = self._tile_configuration(tile)
        cached = False
        if configuration is not None:
            started = time.time()
            cached = tile_inputs_are_cached(configuration, step_key)
            elapsed = time.time() - started
            if elapsed > 1.0:
                # The predicates are cheap BY CONTRACT; a slow one is
                # holding the scheduler lock and deserves to be named.
                print("Cache check for %s %s took %.1f s — a fetch cache "
                      "predicate is doing more than filesystem work."
                      % (_short_latlon(tile), step_key, elapsed))
        self._cache_state[key] = cached
        return cached

    def _effective_step_class_locked(self, tile, step_key):
        """The resource class this step of this tile will OCCUPY.

        A fetch-class step whose inputs are all on disk issues no remote
        request, so it is admitted under the compute class instead and
        never waits for a fetch token (spec §A.2, "an already-cached
        queued tile never waits for a fetch token").
        """
        step_class = STEP_CLASSES.get(step_key, "compute")
        if step_class not in FETCH_CLASSES:
            return step_class
        if not cache_aware_admission_enabled():
            return step_class
        if self._fetch_is_cached_locked(tile, step_key):
            return CACHED_STEP_CLASS
        return step_class

    def _try_start_step_locked(self, child):
        """Dispatch the child's tile's next step if its class has room
        and the memory projection admits it."""
        step_index = self._next_step_index.get(child.tile, 0)
        step_key = self._programs[child.tile][step_index]
        step_class = self._effective_step_class_locked(child.tile, step_key)
        if self._class_active[step_class] >= self._class_limits[step_class]:
            return False
        if not self._memory_admits_locked(child.tile, step_key):
            return False
        if child.start_step(step_key, self._tile_arguments[child.tile]):
            self._step_started_at[(child.tile, step_key)] = time.time()
            self._tile_first_started.setdefault(child.tile, time.time())
            self._class_active[step_class] += 1
            child.step_class = step_class
            child.autopatch_pending = None
            estimate = self._step_memory_estimate(child.tile, step_key)
            if estimate > 0.0:
                self._memory_holders[(child.tile, step_key)] = estimate
                self._memory_in_use += estimate
            return True
        return False

    def _swap_class_locked(self, child, new_class):
        """Move a running child from the class it holds to ``new_class``.

        The child is ALREADY running, so an acquire cannot be refused:
        the count may exceed the class limit for as long as the returning
        tiles take to finish their step, and every gate compares ``>=``,
        so the effect is to SHUT the class to new dispatches while they
        drain.  Never re-acquiring at all would be worse: the tails would
        run alongside a full complement of freshly dispatched fetchers.
        """
        old_class = child.step_class
        if old_class == new_class:
            return
        if old_class is not None:
            self._class_active[old_class] = max(
                0, self._class_active[old_class] - 1)
        self._class_active[new_class] = (
            self._class_active.get(new_class, 0) + 1)
        child.step_class = new_class

    def _note_autopatch_begin_locked(self, child, airports):
        """The child's vector step handed off to the auto-patch solve.

        Releases the osm token (a queued tile may start FETCHING at
        once) and continues under ``VECTOR_SOLVE_CLASS``.  Ignored for a
        child that is not in the fetch phase of a vector step, and for an
        empty airport list (nothing to solve).
        """
        if (child.running_step != "vector"
                or child.step_class != STEP_CLASSES.get("vector", "osm")
                or not airports):
            return False
        self._swap_class_locked(child, VECTOR_SOLVE_CLASS)
        child.autopatch_pending = {str(a) for a in airports}
        return True

    def _note_autopatch_terminal_locked(self, child, airport):
        """One airport finished (done/fail); the last one ends the solve.

        The vector step's remainder can still touch the network, so the
        tile takes an osm token back for it.
        """
        pending = child.autopatch_pending
        if pending is None:
            return False
        pending.discard(str(airport))
        if pending:
            return False
        child.autopatch_pending = None
        if child.running_step != "vector":
            return False
        self._swap_class_locked(child, STEP_CLASSES.get("vector", "osm"))
        return True

    def _note_imagery_downloads_done_locked(self, child):
        """The imagery step's download queue drained for this child.

        Releases the imagery token (a queued tile may start downloading
        at once) and lets the local DDS conversion tail finish under
        ``IMAGERY_TAIL_CLASS`` — the same hybrid-step release the vector
        step performs at ``AutoPatchBegin``.  Ignored for a child that is
        not in the fetch phase of an imagery step, so a duplicate or
        late signal cannot double-release.
        """
        if not cache_aware_admission_enabled():
            return False
        if (child.running_step != "imagery"
                or child.step_class != STEP_CLASSES.get(
                    "imagery", "imagery")):
            return False
        self._swap_class_locked(child, IMAGERY_TAIL_CLASS)
        return True

    def _release_step_resources_locked(self, child):
        """Return a finished/aborted step's class and memory budget."""
        step_key = child.running_step
        if step_key is None:
            return
        started = self._step_started_at.pop((child.tile, step_key), None)
        if started is not None and child.tile is not None:
            self._tile_step_seconds[child.tile] = (
                self._tile_step_seconds.get(child.tile, 0.0)
                + (time.time() - started))
        # Release the class the child ACTUALLY holds: a vector step that
        # handed off to the auto-patch solve is occupying
        # VECTOR_SOLVE_CLASS, not "osm".  This one path serves normal
        # step completion AND the reaping of a child that died mid-solve
        # (_on_child_exit), so no token can leak.
        step_class = child.step_class or STEP_CLASSES.get(step_key, "compute")
        self._class_active[step_class] = max(
            0, self._class_active[step_class] - 1)
        child.step_class = None
        child.autopatch_pending = None
        held = self._memory_holders.pop((child.tile, step_key), None)
        if held is not None:
            self._memory_in_use = max(0.0, self._memory_in_use - held)
        child.running_step = None

    def _start_new_tile_locked(self, child):
        """Hand an idle child a queued tile whose first step has room.

        A tile whose OpenStreetMap caches are being warmed RIGHT NOW is
        skipped (never assigned mid-warm — the no-race guarantee of spec
        §3.7); the warmer re-dispatches the moment it finishes a tile.
        A tile whose FIRST step's class is full is also skipped in favour
        of a later queued tile whose first step has room (mixed-batch
        programs may lead with different classes).  That scan uses the
        EFFECTIVE class, so a queued tile whose inputs are already
        cached overtakes cold tiles waiting on a full fetch class rather
        than queueing behind them (spec §A.2).
        """
        tile = None
        for candidate in self._queue:
            if candidate == self._warming_tile:
                continue
            first_step = self._programs[candidate][0]
            first_class = self._effective_step_class_locked(
                candidate, first_step)
            if (self._class_active[first_class]
                    >= self._class_limits[first_class]):
                continue
            if not self._memory_admits_locked(candidate, first_step):
                continue
            tile = candidate
            break
        if tile is None:
            return False
        self._queue.remove(tile)
        child.tile = tile
        child.step_failed = False
        self._next_step_index[tile] = 0
        if not self._try_start_step_locked(child):
            # Dead pipe: put the tile back for another child; the exit
            # path cleans the child up.
            child.tile = None
            self._queue.appendleft(tile)
            return False
        return True

    # -- cancellation ----------------------------------------------------
    def cancel_tile(self, tile):
        emit_stopped = False
        with self._lock:
            if tile in self._queue:
                self._queue.remove(tile)
                emit_stopped = True
                accepted = True
            else:
                accepted = False
                for child in self._children:
                    if child.tile != tile or child.retired:
                        continue
                    if child.running_step is None:
                        # Between steps: no child cancel needed at all —
                        # stop dispatching and report stopped (spec §3.8);
                        # the child stays clean and reusable.
                        child.tile = None
                        self._next_step_index.pop(tile, None)
                        self._percent_high_water.pop(tile, None)
                        emit_stopped = True
                        accepted = True
                        self._dispatch_locked()
                    else:
                        child.cancelling = True
                        accepted = child.send({"cmd": "cancel"})
                    break
        if emit_stopped:
            self._session._emit(TileState(lat=tile[0], lon=tile[1],
                                          state="queued", label="stopped"))
            self._maybe_finish()
        return accepted

    def cancel_all(self):
        with self._lock:
            self._cancel_all = True
            drained = list(self._queue)
            self._queue.clear()
            waiting = []
            cancelling = []
            for child in self._children:
                if child.retired or child.tile is None:
                    continue
                if child.running_step is None:
                    waiting.append(child.tile)
                    child.tile = None
                else:
                    child.cancelling = True
                    child.send({"cmd": "cancel"})
                    cancelling.append(child)
        for tile in drained + waiting:
            self._session._emit(TileState(lat=tile[0], lon=tile[1],
                                          state="queued", label="stopped"))
        # The cancel command only raises the child's red_flag — a step
        # wedged in an operation that never polls it would keep `busy`
        # true forever and the run would never finish.  Escalate per
        # child on a bounded clock: SIGTERM (the child's transport turns
        # it into a bounded wind-down and exit), then SIGKILL as the
        # backstop; _on_child_exit does the accounting either way.
        for child in cancelling:
            escalate_timer = threading.Timer(
                CANCEL_ESCALATE_SECONDS, self._escalate_cancel, (child,))
            escalate_timer.daemon = True
            escalate_timer.start()
        self._maybe_finish()

    def _escalate_cancel(self, child):
        process = child.process
        if child.tile is None or child.retired or process is None:
            return
        if process.poll() is None:
            child.terminate()
            kill_timer = threading.Timer(
                CANCEL_KILL_SECONDS,
                lambda: process.poll() is None and process.kill())
            kill_timer.daemon = True
            kill_timer.start()

    def shutdown_workers(self):
        """Hard-stop every worker child because the front end is exiting.

        ``cancel_all`` is the graceful in-run stop (children finish their
        current step before retiring); this is the application going away
        NOW.  Each child gets its stdin closed (end-of-file) AND a
        terminate signal — its transport turns both into a red-flagged,
        bounded wind-down (jsonl.serve owns_process mode) — so no worker
        can outlive the front end and keep building headless.  Never
        blocks the caller.
        """
        with self._lock:
            self._cancel_all = True
            self._queue.clear()
            children = list(self._children)
        for child in children:
            child.retire()
            child.terminate()

    # -- child callbacks (reader threads) --------------------------------
    def _on_child_event(self, child, payload):
        event_name = payload.get("event")
        if event_name == "SecretRequest":
            # A worker child's brokered secret-store operation
            # (o4_engine.secret_broker): the parent services it — off
            # this reader thread, because the parent's own routing may
            # itself block on the front end brokering THIS process.
            threading.Thread(
                target=self._service_child_secret_request,
                args=(child, payload), daemon=True).start()
            return
        if event_name == "RunDone":
            self._child_step_done(child)
            return
        if event_name == "RunEta":
            # Harvest the child's live in-step estimate for the parent
            # run clock (tagged with the step so a report racing a step
            # transition is discarded rather than misattributed).
            remaining = payload.get("remaining_seconds")
            if (child.running_step is not None
                    and isinstance(remaining, (int, float))):
                child.live_remaining = (
                    child.running_step, float(remaining), time.time())
            return
        if event_name == "AutoPatchBegin":
            # The vector step's fetch phase is over and its auto-patch
            # solve has started: hand the osm token back so a queued tile
            # can fetch, and let the solve run under the uncapped compute
            # class (spec: vector-step-class-split §2).
            with self._lock:
                if self._note_autopatch_begin_locked(
                        child, payload.get("airports") or ()):
                    self._dispatch_locked()
        elif (event_name == "AutoPatchProgress"
                and payload.get("status") in ("done", "fail")):
            with self._lock:
                if self._note_autopatch_terminal_locked(
                        child, payload.get("airport")):
                    self._dispatch_locked()
        elif event_name == "ImageryDownloadsDone":
            # The imagery step's download queue drained: hand the imagery
            # token back so a queued tile can download, and let the DDS
            # conversion tail run under compute (spec §A.2).
            with self._lock:
                if self._note_imagery_downloads_done_locked(child):
                    self._dispatch_locked()
            return
        if event_name == "Error" and payload.get("fatal"):
            # A fatal child error ends that CHILD, never the parent
            # session; the crash path in _on_child_exit accounts for it.
            print("[worker %d] fatal: %s"
                  % (child.index, payload.get("text", "")))
            return
        if event_name not in _FORWARDED_EVENT_TYPES:
            return
        event = _rebuild_event(payload)
        if event is None:
            return
        tile = child.tile
        step_index = self._next_step_index.get(tile, 0)
        program = self._programs.get(tile, ())
        last_step = step_index >= len(program) - 1
        if event_name == "BuildDone":
            if event.ok and not last_step:
                # Intermediate step completion: a scheduling signal, not
                # a tile terminal — swallowed (spec §3.8).
                return
            with self._lock:
                if event.ok:
                    self._done += 1
                else:
                    child.step_failed = True
                    self._errors += 1
                # Freeze the tile's clock at its terminal (TileClocks).
                started = self._tile_first_started.get(tile)
                if started is not None:
                    self._tile_final_elapsed.setdefault(
                        tile, max(0.0, time.time() - started))
        elif event_name == "TileState":
            if event.state == "done" and not last_step:
                return
            if tile is not None and event.state in ("active", "indeterminate"):
                # In-run TileState percents are step-local like
                # StepProgress (a child's run IS one step) and include
                # the dataclass default 0.0 — forwarded raw they yank a
                # ratcheted bar back to zero mid-tile.  Same high-water
                # rule as the StepProgress remap below; terminal and
                # queued states keep their semantic percents.
                event = dataclasses.replace(event, percent=max(
                    event.percent,
                    self._percent_high_water.get(tile, 0.0)))
        elif event_name == "StepProgress" and tile is not None:
            # Remap the child's single-step percent window into the
            # tile's full-plan window so views see whole-tile percent,
            # then ratchet against the tile's high-water mark: the
            # legacy bars oscillate within a step, and a per-tile bar
            # must fill smoothly, never slide back (each tile has one
            # child, so the per-key update is single-writer).
            windows = (self._tile_step_windows.get(tile)
                       or self._static_windows.get(tile) or {})
            base, width = windows.get(event.step_key, (0.0, 1.0))
            remapped = min(
                100.0, (base + width * event.percent / 100.0) * 100.0)
            remapped = max(
                remapped, self._percent_high_water.get(tile, 0.0))
            self._percent_high_water[tile] = remapped
            event = dataclasses.replace(event, percent=remapped)
        if event_name in ("AutoPatchBegin", "AutoPatchProgress"):
            if tile is not None and (event.lat, event.lon) == (0, 0):
                event = dataclasses.replace(event, lat=tile[0], lon=tile[1])
        self._session._emit(event)

    def _service_child_secret_request(self, child, payload):
        """Answer one child's secret-store request with the parent's
        own routing (O4_Authenticated_Sessions.secret_get/set/delete):
        forwarded to the front end when this process is itself brokered
        (the packaged application), keyring directly otherwise — so the
        one process that touches the platform store is always the
        outermost driver, never an ad-hoc worker child."""
        import O4_Authenticated_Sessions as SESSIONS

        operation = str(payload.get("operation", ""))
        session_name = str(payload.get("session_name", ""))
        account = str(payload.get("account", ""))
        response = {"cmd": "secret_response",
                    "request_id": payload.get("request_id", 0)}
        try:
            if operation == "get":
                response["secret"] = SESSIONS.secret_get(
                    session_name, account)
                response["ok"] = True
            elif operation == "set":
                SESSIONS.secret_set(
                    session_name, account,
                    str(payload.get("secret", "")))
                response["ok"] = True
            elif operation == "delete":
                SESSIONS.secret_delete(session_name, account)
                response["ok"] = True
            else:
                response["ok"] = False
                response["error"] = (
                    "unknown secret operation %r" % operation)
        except Exception as error:
            response["ok"] = False
            response["error"] = str(error)
        child.send(response)

    def _child_step_done(self, child):
        """The child finished (or aborted) one single-step build."""
        respawn = False
        with self._lock:
            self._release_step_resources_locked(child)
            if child.cancelling:
                # Spec §3.4: never reuse a red-flagged interpreter.
                self._next_step_index.pop(child.tile, None)
                self._percent_high_water.pop(child.tile, None)
                self._tile_step_seconds.pop(child.tile, None)
                child.tile = None
                child.retire()
                respawn = bool(self._queue) and not self._cancel_all
            elif child.step_failed:
                # The failure was forwarded at BuildDone time; abort the
                # tile's remaining steps.
                self._next_step_index.pop(child.tile, None)
                self._percent_high_water.pop(child.tile, None)
                self._tile_step_seconds.pop(child.tile, None)
                child.tile = None
                child.step_failed = False
            elif child.tile is not None:
                # A finished step may have landed exactly the data the
                # NEXT step would fetch (the vector step's background
                # prefetch is the common case), so the tile's memoised
                # cache verdicts are re-asked rather than carried over.
                self._forget_cache_state_locked(child.tile)
                self._next_step_index[child.tile] = (
                    self._next_step_index.get(child.tile, 0) + 1)
                if (self._next_step_index[child.tile]
                        >= len(self._programs.get(child.tile, ()))):
                    # Tile complete (its final BuildDone was forwarded).
                    # The per-tile total the children cannot print (each
                    # sees one step): dispatched-step seconds summed by
                    # _release_step_resources_locked.
                    print("\nTile %s completed in %s."
                          % (_short_latlon(child.tile),
                             UI.nicer_timer(
                                 self._tile_step_seconds.pop(
                                     child.tile, 0.0))))
                    self._next_step_index.pop(child.tile, None)
                    self._percent_high_water.pop(child.tile, None)
                    child.tile = None
            self._dispatch_locked()
        if respawn:
            replacement = self._spawn_child()
            if replacement is not None:
                with self._lock:
                    self._dispatch_locked()
        self._broadcast_sibling_count()
        self._maybe_finish()

    def _broadcast_sibling_count(self):
        """Tell surviving children how many siblings still hold work.

        Since the 2026-07-17 lean-on-the-operating-system ruling,
        processor-bound pools no longer divide by this count — its one
        remaining consumer is the network fetchers that hit small
        remote hosts (the bathymetry cell fetch), which re-read it from
        the environment (set_parallel_siblings) at their next step.

        The count is the children actively HOLDING tiles (measured
        after dispatch, so a freed slot the queue instantly refills
        never reads as spare capacity).  Queued tiles do not count —
        they consume nothing until a child picks them up; counting them
        (the pre-2026-07-17 formula) told every child in a deep-queue
        run that the whole queue was concurrent.
        """
        with self._lock:
            holders = [child for child in self._children
                       if child.tile is not None and not child.retired]
            count = max(1, len(holders))
            if count == self._sibling_broadcast:
                return
            self._sibling_broadcast = count
        for child in holders:
            child.send({"cmd": "siblings", "count": count})

    def _on_child_exit(self, child):
        """The child's stdout closed: normal retirement or a crash."""
        crashed_tile = None
        stopped_tile = None
        respawn = False
        with self._lock:
            if child in self._children:
                self._children.remove(child)
            self._release_step_resources_locked(child)
            # A child that exits while its cancel is in flight — the
            # cooperative red flag never answered and the escalation's
            # SIGTERM took it out through the transport's bounded exit,
            # or it died on its own after the cancel — was STOPPED by the
            # user, not failed.  ``retired`` is set by the escalation's
            # ``terminate()`` itself, so the cancelling test comes first
            # and does not consult it (2026-09-03: the wedged +40-004
            # child's Stop was reported as "failed").
            if child.tile is not None and child.cancelling:
                stopped_tile = child.tile
                self._next_step_index.pop(child.tile, None)
                self._percent_high_water.pop(child.tile, None)
                self._tile_step_seconds.pop(child.tile, None)
                child.tile = None
                respawn = bool(self._queue) and not self._cancel_all
            elif child.tile is not None and not child.retired:
                crashed_tile = child.tile
                self._next_step_index.pop(child.tile, None)
                self._percent_high_water.pop(child.tile, None)
                self._tile_step_seconds.pop(child.tile, None)
                child.tile = None
                self._errors += 1
                respawn = bool(self._queue) and not self._cancel_all
            self._dispatch_locked()
        if stopped_tile is not None:
            lat, lon = stopped_tile
            self._session._emit(TileState(lat=lat, lon=lon, state="queued",
                                          label="stopped"))
            print("Build worker for", _short_latlon(stopped_tile),
                  "exited while being stopped; its tile is marked stopped.")
        if crashed_tile is not None:
            lat, lon = crashed_tile
            self._session._emit(TileState(lat=lat, lon=lon, state="error",
                                          label="failed"))
            self._session._emit(BuildDone(
                lat=lat, lon=lon, ok=False,
                error="build worker exited unexpectedly"))
            print("Build worker for", _short_latlon(crashed_tile),
                  "exited unexpectedly; its tile is marked failed.")
        if respawn:
            replacement = self._spawn_child()
            if replacement is not None:
                with self._lock:
                    self._dispatch_locked()
        self._broadcast_sibling_count()
        self._maybe_finish()

    # -- OpenStreetMap cache warmer (spec §3.7) ---------------------------
    def _acquire_warm_token_locked(self):
        """Take an osm token for the warmer, or refuse.

        The parent-side warmer is a FETCHER and takes a token like any
        other (spec §A.3, the binding admission invariant: revision 1's
        untokened warmer could push concurrent Overpass conversations to
        cap + 1).  Gate off: no token, exactly as before.
        """
        if not cache_aware_admission_enabled():
            return True
        if self._warm_token_held:
            return True
        if self._class_active["osm"] >= self._class_limits["osm"]:
            return False
        self._class_active["osm"] += 1
        self._warm_token_held = True
        return True

    def _release_warm_token_locked(self):
        """Hand the warmer's osm token back (idempotent)."""
        if not self._warm_token_held:
            return False
        self._class_active["osm"] = max(
            0, self._class_active["osm"] - 1)
        self._warm_token_held = False
        return True

    def _osm_cache_warmer(self):
        """Warmer thread body: run the warm loop, then mark the thread
        dead so a later enqueue knows to revive it (the loop returns
        the moment no unwarmed queued tiles remain)."""
        try:
            self._warm_queued_tiles()
        finally:
            with self._lock:
                # A thread that dies anywhere — including inside a warm —
                # must not leak its token; this is the warmer's half of
                # the crash-safe release the pool's reaping path gives
                # the children.
                self._release_warm_token_locked()
                self._warming_tile = None
                self._warmer_running = False
                self._dispatch_locked()

    def _warm_queued_tiles(self):
        """Pre-download queued tiles' OpenStreetMap layer caches.

        One tile at a time, one Overpass request at a time — combined
        with the network class cap, the server sees a bounded, polite
        request profile however many tiles are queued.  Only UNASSIGNED
        tiles are touched, and assignment skips the tile being warmed
        (_start_new_tile_locked), so the warmer can never race a worker
        child on the same cache files.  Failures are per-tile and
        non-fatal: the child simply downloads for itself, exactly as
        without a warmer.

        ``O4_DISABLE_OSM_WARMER`` in the environment disables the warmer
        entirely (the automated test suite sets it globally so no test
        can reach the network; real runs never set it).
        """
        if os.environ.get("O4_DISABLE_OSM_WARMER"):
            return
        try:
            import O4_Config_Utils as CFG
            import O4_OSM_Utils as OSM
            import O4_Vector_Map as VMAP
        except Exception as error:
            print("OpenStreetMap cache warmer unavailable:", error)
            return
        try:
            import O4_OSM_Extracts as EXTRACTS
        except Exception:
            EXTRACTS = None
        while True:
            with self._lock:
                if self._finished or self._cancel_all:
                    return
                tile = next(
                    (t for t in self._queue if t not in self._warmed_tiles),
                    None,
                )
                if tile is None:
                    return
                self._warming_tile = tile
            # The warmer exists to spare the OVERPASS servers.  A tile
            # fully covered by locally stored regional extracts never
            # touches Overpass — and warming it would run country-sized
            # pbf scans INSIDE the front-end process, starving the
            # interface through the interpreter lock (the 2026-07-17
            # live "build appears hung": the interface sat at 100 %
            # processor parsing great-britain.osm.pbf while the worker
            # children built fine).  Its worker child filters the same
            # extracts in its OWN process instead.
            locally_covered = False
            if EXTRACTS is not None:
                try:
                    locally_covered = EXTRACTS.local_extracts_cover(
                        (tile[0], tile[1], tile[0] + 1, tile[1] + 1))
                except Exception:
                    locally_covered = False
            if locally_covered:
                print("[warm]", _short_latlon(tile),
                      "is covered by local OpenStreetMap extracts;"
                      " its build filters them directly.")
                with self._lock:
                    self._warming_tile = None
                    self._warmed_tiles.add(tile)
                    self._dispatch_locked()
                self._maybe_finish()
                continue
            tile_configuration = None
            try:
                with self._lock:
                    tile_build_dir = self._tile_arguments.get(
                        tile, {}).get("custom_build_dir", "")
                tile_configuration = CFG.Tile(
                    tile[0], tile[1], tile_build_dir)
                tile_configuration.read_from_config()
            except Exception as error:
                print("[warm] OpenStreetMap warm failed for",
                      _short_latlon(tile), ":", error,
                      "- its build will download for itself.")
            # A tile whose layer caches are already current needs no
            # Overpass conversation at all — and must therefore not
            # occupy an osm token to discover that.
            vector_is_cached = getattr(VMAP, "is_cached", None)
            if tile_configuration is None or (
                    vector_is_cached is not None
                    and vector_is_cached(tile_configuration)):
                with self._lock:
                    self._warming_tile = None
                    self._warmed_tiles.add(tile)
                    self._dispatch_locked()
                self._maybe_finish()
                continue
            if not self._await_warm_token(tile):
                continue
            try:
                specifications = VMAP.osm_layer_warm_specifications(
                    tile_configuration)
                warmed_layers = 0
                for (cached_suffix, queries, tags_of_interest,
                        node_tags_of_interest,
                        cache_schema) in specifications:
                    with self._lock:
                        still_queued = tile in self._queue
                        stopping = self._finished or self._cancel_all
                    if stopping or not still_queued:
                        break
                    OSM.OSM_queries_to_OSM_layer(
                        queries,
                        OSM.OSM_layer(),
                        tile[0],
                        tile[1],
                        tags_of_interest,
                        cached_suffix=cached_suffix,
                        node_tags_of_interest=node_tags_of_interest,
                        cache_schema=cache_schema,
                    )
                    warmed_layers += 1
                if warmed_layers:
                    print("[warm] OpenStreetMap cache ready for",
                          _short_latlon(tile),
                          "(%d layer(s))" % warmed_layers)
            except Exception as error:
                print("[warm] OpenStreetMap warm failed for",
                      _short_latlon(tile), ":", error,
                      "- its build will download for itself.")
            with self._lock:
                self._release_warm_token_locked()
                self._warming_tile = None
                self._warmed_tiles.add(tile)
                self._cache_state.pop((tile, "vector"), None)
                self._dispatch_locked()
            self._maybe_finish()

    def _await_warm_token(self, tile):
        """Block until the warmer holds an osm token for ``tile``.

        Returns False (nothing acquired, nothing to do) when the run is
        stopping or a worker child took the tile meanwhile.  The warming
        CLAIM is dropped while waiting: a warmer parked on a full osm
        class must not also keep its tile off the workers, or a queue
        whose whole osm budget is busy would stall behind it.
        """
        while True:
            with self._lock:
                if self._finished or self._cancel_all:
                    self._warming_tile = None
                    return False
                if tile not in self._queue:
                    self._warming_tile = None
                    return False
                self._warming_tile = tile
                if self._acquire_warm_token_locked():
                    return True
                self._warming_tile = None
                self._dispatch_locked()
            time.sleep(WARM_TOKEN_POLL_SECONDS)

    # -- run end ----------------------------------------------------------
    def _maybe_finish(self):
        with self._lock:
            if self._finished:
                return
            busy = any(
                child.tile is not None
                for child in self._children
                if not child.retired
            )
            if self._queue or busy:
                return
            self._finished = True
            children = list(self._children)
            done, errors = self._done, self._errors
            cancelled = self._cancel_all
        # The session leaves its "building" state BEFORE the bounded
        # child reaping below: a Build click landing the moment the last
        # tile finishes must start a fresh run immediately, not wait out
        # slow-exiting workers.
        self._session._run_finished()
        self._session._emit(RunDone(done_count=done, error_count=errors,
                                    cancelled=cancelled))
        for child in children:
            child.retire()
        deadline = time.time() + 5.0
        for child in children:
            try:
                child.process.wait(timeout=max(0.1, deadline - time.time()))
            except Exception:
                child.terminate()

    def _ticker(self):
        """Run-level clock: elapsed + the learned remaining estimate
        (spec §3.3; a dash only when the time model has no basis)."""
        while True:
            with self._lock:
                if self._finished:
                    return
                completed = self._done + self._errors
                queued_tiles = list(self._queue)
                next_step_index = dict(self._next_step_index)
                in_flight_steps = dict(self._step_started_at)
                programs = dict(self._programs)
                total = self._total
                live_step_remaining = {
                    (child.tile, child.live_remaining[0]):
                        (child.live_remaining[1], child.live_remaining[2])
                    for child in self._children
                    if child.tile is not None
                    and child.live_remaining is not None
                    and child.live_remaining[0] == child.running_step
                }
                first_started = dict(self._tile_first_started)
                final_elapsed = dict(self._tile_final_elapsed)
            now = time.time()
            remaining = None
            try:
                remaining = estimate_remaining_wall_seconds(
                    self._estimates, programs, queued_tiles,
                    next_step_index, in_flight_steps, now,
                    self._slots, live_step_remaining)
            except Exception:
                remaining = None
            self._session._emit(RunEta(
                elapsed_seconds=now - self._t0,
                remaining_seconds=remaining,
                done_tiles=completed,
                total_tiles=total))
            try:
                self._session._emit(TileClocks(rows=per_tile_clock_rows(
                    self._estimates, programs, queued_tiles,
                    next_step_index, in_flight_steps, now,
                    live_step_remaining, first_started, final_elapsed)))
            except Exception:
                pass
            time.sleep(1.0)
