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
started, less the machine headroom (owner rulings 2026-07-30, docs/specs/
apron-string-and-scheduling-spec.md §A.2; #2083: each step projected
from the tile's own recorded peak, and a heavy step also waits while
LIVE free memory is short) — within that, processor
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
re-derives what a step will read.  The OpenStreetMap cache warmer below
takes an osm token like any other fetcher, warms only a queued tile no
worker could take (idle or yet to be spawned), and downloads in a process
of its own (``osm_warm_process``), never on the command process.

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
import itertools
import json
import os
import subprocess
import sys
import threading
import time
from collections import deque
from typing import Optional

import O4_Console_Encoding
import O4_Edit_Cache as EDITCACHE
import O4_File_Names as FNAMES
import O4_Machine_Memory as MEMORY
import O4_Machine_Slots
import O4_Tile_Failures as FAIL
import O4_UI_Utils as UI

from . import boundary_reselect as BOUNDARY
from . import build_order as ORDER
from . import events as EVENTS
from . import osm_warm_process as OSM_WARM
from . import step_memory
from . import step_parking
from . import storage_floor as FLOOR
from .memory_waits import (REASON_MACHINE, REASON_RUN, MemoryWaits,
                           _Wait, wait_message)
from . import tile_time_model
from .plan_estimate import TIME_SPREAD_KNOWN
from .events import (BuildDone, RunDone, RunEta, StepProgress, TileClocks,
                     TileState)
from .session import (
    ETA_EMIT_SECONDS,
    _gateway_line, _offer_gateway_airports, _offer_pack_overlaps, _predict_step_seconds,
    build_done,
    last_outcome_counts,
    plan_steps, prediction_features, reweight_plan_by_seconds, stopped_tile_state,
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
    # A child reports at ~2 Hz; a report much older than that belongs
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

# A dead child's stderr: how long its exit path waits for the drain to
# reach end of file, how many non-blank lines are kept, and how many of
# them a crashed tile's failure record carries.
STDERR_DRAIN_SECONDS = 2.0
STDERR_TAIL_LINES = 20
CRASH_DETAIL_LINES = 3

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

# How many queued tiles, from the head, the dispatcher considers for an
# idle child and the OpenStreetMap warmer downloads ahead (#1225: the
# queue may hold every tile of the planet).
QUEUE_SCAN_WINDOW = 64
#: The rank of a tile whose batch named no class or deadline.
_DEFAULT_RANK = ORDER.rank()
# How often a warmer that has warmed the whole head looks again.
WARM_AHEAD_POLL_SECONDS = 1.0

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

    # ... and never above the session's machine budget (#1225: cores - 2
    # and the memory headroom), which every heavy process shares.
    return max(1, min(PARALLEL_UTILS.machine_core_count(),
                      O4_Machine_Slots.session_capacity()))


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


def mesh_memory_estimate_gigabytes(elevation_level_value):
    """Estimated peak mesh memory for a tile's ``elevation_level``."""
    if elevation_level_value is None:
        return MESH_MEMORY_DEFAULT_GB
    key = str(elevation_level_value).strip().lower()
    return MESH_MEMORY_ESTIMATES_GB.get(key, MESH_MEMORY_DEFAULT_GB)


def mesh_memory_budget_gigabytes():
    """Total gigabytes the run may commit to concurrent mesh steps.

    The pre-2026-07-30 budget, still used when the cache-aware admission
    gate is off (see :func:`step_memory_budget_gigabytes`): physical
    memory less the machine headroom (#2083; was a flat 4 GB).
    """
    import O4_Parallel_Utils as PARALLEL_UTILS

    return max(
        4.0,
        PARALLEL_UTILS.machine_memory_gigabytes()
        - O4_Machine_Slots.headroom_gigabytes(),
    )


# Peak working-set estimates for the steps OTHER than mesh (gigabytes),
# extending the mesh sizing above to "any step with a memory estimate"
# (spec §A.2).  Deliberately coarse: their job is to stop a cores-wide
# compute admission committing more memory than the machine has, not to
# model a step.  A step absent from this table projects nothing and is
# admitted on the core count alone.
#
# Provenance, honestly: a worker with the whole pipeline imported and
# nothing running is 0.12 GB, so these are that baseline plus a
# deliberately generous working-set allowance, NOT measurements.  Since
# #2083 they are only the NO-RECORD fallback: the scheduler samples every
# step's process tree and projects a tile's step from its own recorded
# peak (``step_memory.projected_gigabytes``).  The vector figure is the
# OSM parse alone; a vector step that may solve airports and has no
# record projects ``step_memory.VECTOR_AIRPORT_DEFAULT_GB`` (8 GB — the
# 1.0.519 run measured 6-14 GB per tile; the 3 GB of 2026-07-30 was one
# HECA reading).
STEP_MEMORY_ESTIMATES_GB = {
    "vector": 3.0,     # the OSM parse alone (no airport to solve)
    "masks": 1.0,      # estimate
    "imagery": 1.5,    # estimate: download buffers + the DDS convert pool
    "overlays": 0.5,   # estimate
}


def step_reservation_gigabytes(step_key, elevation_level_value=None):
    """What one step with no record reserves on the machine memory ledger
    when it runs outside a parallel run's scheduler (a single in-process
    tile, the harness): the scheduler's default projection for the step
    (``step_memory.ledger_gigabytes``).  ``elevation_level_value`` sizes
    the mesh step; unknown steps reserve nothing."""
    if step_key == "mesh":
        default = mesh_memory_estimate_gigabytes(elevation_level_value)
    elif step_key == "vector":
        default = step_memory.VECTOR_AIRPORT_DEFAULT_GB
    else:
        default = STEP_MEMORY_ESTIMATES_GB.get(step_key, 0.0)
    return step_memory.ledger_gigabytes(
        step_key, step_memory.charged_gigabytes(step_key, default))


def step_memory_budget_gigabytes():
    """Gigabytes this run's steps may BOOK and not yet use: the memory the
    machine has free now, above the machine headroom
    (``O4_Machine_Slots.headroom_gigabytes``: the larger of 15 % of
    physical memory and 8 GB, kept for the operating system, the app and
    the user's other work — #1225, #2083).  Re-read every sample
    (``ParallelBuildRun._refresh_memory_budget_locked``).

    THE RULE (owner 2026-11-18): a step starts when the free memory, less
    the part of every running step's booking its process tree has not yet
    grown into (``ParallelBuildRun._run_booked_locked``), covers its need
    plus the headroom.  Memory a step already holds is out of the free
    figure, so it is never counted twice.  Until 2026-11-18 the run
    compared the SUM of its steps' whole projections to 80 % of (free +
    the run's resident): app 1.0.558 held a 9 GB masks step with 61 GB
    free ("this run's steps hold 98.5 of its 79.4 GB budget") — booked
    memory its steps had long grown into or would never reach.
    """
    import O4_Parallel_Utils as PARALLEL_UTILS

    return max(0.0, PARALLEL_UTILS.machine_available_memory_gigabytes()
               - O4_Machine_Slots.headroom_gigabytes())


# A re-read budget replaces the current one only when it moved this much
# (gigabytes): free memory jitters by a few hundred megabytes between two
# samples, and a budget that twitched would admit and refuse in turn.
MEMORY_BUDGET_HYSTERESIS_GB = 1.0

# A step projecting at most this much (gigabytes) is never held behind an
# older step's reservation (#2101): it still fits the budget sum, but
# making a 0.5 GB overlays step wait for an 8 GB vector step to fit frees
# nothing the waiter could use (lane lmemwait, 2026-11-17).
TINY_STEP_GB = 1.0

# Seconds between two samples of the running steps' resident memory
# (one ``ps`` for all of them; step_memory.tree_resident_gigabytes).
STEP_MEMORY_SAMPLE_SECONDS = 2.0


def _recorded_step_peaks(tile):
    """The tile's recorded per-step peaks (``{}`` on any problem)."""
    try:
        return tile_time_model.step_peaks(tile[0], tile[1])
    except Exception:
        return {}


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
        # The declared cold neighbour frames step 1 warms (§D.2 of
        # insets-follow-patch-set-spec): ``module:predicate`` names a
        # predicate other than the module's ``is_cached``.
        "O4_Vector_Map:boundary_frames_are_cached",
        "O4_DEM_Utils",
        "O4_Airport_Elevation_Insets",
        "O4_Bathymetry_Band",
        "auto_patch.build_support",   # was .osm_load (v1) until 2026-10-04
    ),
    "imagery": ("O4_Tile_Utils",),
}


# How long a run's FIRST dispatch sweep waits for the predicates to be
# importable.  The import overlaps the worker handshakes (seconds), so
# the wait is normally zero; the bound only keeps a pathological import
# from holding the run.
PREDICATE_PRELOAD_WAIT_SECONDS = 5.0

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
        (import_name, _colon, attribute) = module_name.partition(":")
        attribute = attribute or "is_cached"
        try:
            module = __import__(import_name, fromlist=[attribute])
            predicate = getattr(module, attribute, None)
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
    return not uncached_subsystems(tile_configuration, step_key, first=True)


def uncached_subsystems(tile_configuration, step_key, first=False):
    """The fetch subsystems (``STEP_FETCH_SUBSYSTEMS`` names) whose
    predicate says this step of this tile WOULD download — or cannot
    answer, which reads the same.  ``first`` stops at the first one.
    An installed package (#2014) reports what its tiles still fetch."""
    out = []
    for module_name in STEP_FETCH_SUBSYSTEMS.get(step_key, ()):
        predicate = _subsystem_is_cached(module_name)
        try:
            cached = predicate is not None and bool(predicate(tile_configuration))
        except Exception:
            cached = False
        if not cached:
            out.append(module_name)
            if first:
                break
    return out


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
    # #433: a child's object stage names a pack X-Plane will not load.
    "PackMissingArt",
    # #1360: ... and a pack whose old flat forests have 3D equivalents.
    "PackOldForests",
    # #1351: the running step's slow-step alert (the child owns the clock).
    "SlowStep",
    # #1707: ... and a pack "Optimise pack" can lighten.
    "PackOptimise",
    # #1916: ... and a pack's adjustments (trees, draped photos, flatten).
    "PackAdjust",
    # #1989: ... and the tile's Gateway airports to offer.
    "GatewayAirports",
    # #2145: ... and the large structures two packs both draw.
    "PackOverlaps",
    # #2174: ... and a read-only pack whose writes wait for the answer.
    "PackReadOnly",
    # RULINGS 11m (4): ... and the packages the tile's packs ship.
    "PackPackage",
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
    re-stamps both at re-emission — and so is ``attempt``: a child numbers
    its own per-step commands, the tile's attempt is the parent's (#1326).
    """
    event_name = payload.get("event")
    event_class = _EVENT_CLASSES.get(event_name)
    if event_class is None:
        return None
    field_names = {
        f.name for f in dataclasses.fields(event_class)
    } - {"seq", "ts", "attempt"}
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
        # True while this child's tile holds an imagery token lent to its
        # imagery job (#1002, #2254).
        self.prefetch_token = False
        # True from the vector step until the imagery step adopts the
        # tile's imagery job or it reports: it may still take a token.
        self.imagery_job_open = False
        # True from a mesh step sent ``objects_beside`` until the tile's
        # next step other than masks starts (#1264): between its steps the
        # tile's object stage may still be writing packs in this child.
        self.objects_beside = False
        # While the step only waits (step_class is step_parking's
        # WAITING_CLASS): the class it returns to and its memory booking.
        self.parked_class = None
        self.parked_memory = None
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
        # The running step's peak resident memory (its process tree),
        # sampled by the run's ticker (#2083).
        self.step_peak_gb = 0.0
        # The child's whole process tree as last sampled (GB): what its
        # running step has grown into, or what earlier steps left.
        self.tree_gb = 0.0
        self.step_failed = False       # current tile had a failing step
        self.cancelling = False        # a mid-step cancel is in flight
        # The child's own "stopped" TileState, held until the parent has
        # released the tile (#1326, ``_child_step_done``).
        self.held_stopped = None
        self.retired = False
        self.hello = threading.Event()
        self._stdin_lock = threading.Lock()
        self._command_id = 0
        # The stderr drain thread and the last lines it read: a crashed
        # child's own error text, which its failure record carries.
        self._stderr_thread = None
        self.stderr_tail = deque(maxlen=STDERR_TAIL_LINES)

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
            # This run reserves each step it starts on the machine memory
            # ledger; the child's own step slot reserves nothing more.
            child_environment[MEMORY.ENV_STEP_RESERVED] = "1"
            # A BUILD worker: its tree runs in the background, below the
            # command process that answers the app's commands and dialogs
            # (owner 2026-11-20T18:40Z, ``O4_Machine_Slots.lower_priority``).
            child_environment[O4_Machine_Slots.ENV_BUILD_WORKER] = "1"
            # The child lists its tiles' edit caches in THIS front end's
            # session and never clears it (O4_Edit_Cache, #1323).
            child_environment[EDITCACHE.LIST_ENV] = EDITCACHE.begin_session()
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
                # Normal QoS (RULINGS 2026-10-22k): no utility clamp, so
                # workers reach the performance cores; the worker sets its
                # own nice (``O4_Machine_Slots.NICE``) at start.
                tile_worker_command(),
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                # The worker's console is UTF-8 (its entry pins it); a
                # bare ``text=True`` reads it in the LOCALE encoding —
                # cp1252 on Windows, where ``Ángel`` (C3 81) does not
                # decode at all and ended the stderr drain (issue #125).
                **O4_Console_Encoding.child_console_pipe(),
                bufsize=1,
                env=child_environment,
                close_fds=False,
            )
        except Exception as error:
            print("Could not start a build worker process:", error)
            return False
        threading.Thread(target=self._read_events, daemon=True).start()
        self._stderr_thread = threading.Thread(target=self._drain_stderr,
                                               daemon=True)
        self._stderr_thread.start()
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
        self.step_peak_gb = 0.0
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
                text = line.rstrip("\n")
                prefix = ("[%s] " % _short_latlon(tile)) if tile else (
                    "[worker %d] " % self.index)
                print(prefix + text)
                if text.strip():
                    self.stderr_tail.append(text.strip())
                # The tile's own build log (#1226); the prefix is the
                # console's, the file is the tile's alone.
                log = getattr(self.run, "tile_log_line", None)
                if log is not None:
                    log(tile, text)
        except Exception:
            pass

    def await_stderr_drained(self):
        """Wait (bounded) for the stderr drain to reach end of file.

        stdout and stderr are two pipes read by two threads: stdout's end
        of file can be seen first, while a dying child's last stderr
        lines (its traceback) are still unread.  The exit path waits for
        them so they reach the tile's log and its failure record before
        the tile is let go (Linux CI read the generic "worker died" line
        without the child's own text).
        """
        thread = self._stderr_thread
        if thread is not None and thread is not threading.current_thread():
            thread.join(STDERR_DRAIN_SECONDS)

    def crash_detail(self):
        """The child's last stderr lines, or the generic sentence."""
        if self.stderr_tail:
            return "\n".join(list(self.stderr_tail)[-CRASH_DETAIL_LINES:])
        return "build worker exited unexpectedly"


class ParallelBuildRun:
    """The phase-aware orchestrator for one parallel run (spec §3.1–3.8)."""

    def __init__(self, session, tiles, provider, zoomlevel,
                 custom_build_dir, step_flags, slots,
                 boundary_policy=None, missing_art=None, overrides=None,
                 priority=None):
        self._session = session
        # The session's per-tile build logs (#1226); a stand-in session
        # without them logs nothing.
        self._tile_logs = getattr(session, "tile_logs", None)
        self._queue = deque()
        # tile -> its batch's ORDER.rank (World spec §8.4); the queue is
        # kept sorted by it, a tile with none ranks ORDER.rank().
        self._priority: dict = {}
        self._total = 0
        # THE MACHINE BUDGET (issue #1225): one slot pool for the engine
        # session, published in os.environ so every tile child — and every
        # airport process and work pool under it — shares it.  No more
        # tile children than it has slots: a queued tile is a queue entry,
        # never a process (the whole planet may be queued).
        self._slots = max(1, min(int(slots),
                                 O4_Machine_Slots.session_capacity()))
        slots = self._slots
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
        # #564: warnings of a tile's finished steps, held for its terminal.
        self._tile_warnings: dict = {}
        # tile -> summed dispatched-step seconds, for the per-tile
        # "completed in" console line (a worker child sees one step at a
        # time, so only the parent can total the tile).
        self._tile_step_seconds: dict = {}
        self._class_limits = class_limits(slots)
        self._class_active = {name: 0 for name in self._class_limits}
        # Workers being started past the slot count for parked children.
        self._parked_spawns = 0
        self._next_step_index: dict = {}
        # Children spawn believing `slots` siblings share the machine;
        # broadcasts below shrink that as tiles finish (see
        # _broadcast_sibling_count).
        self._sibling_broadcast = slots
        # Memory-aware admission (spec §3.8, widened by
        # apron-string-and-scheduling §A.2 from the mesh step to every
        # step with an estimate).  Per-tile MESH estimates come from each
        # tile's configured elevation detail level; the other steps take
        # the flat STEP_MEMORY_ESTIMATES_GB sizing.  The budget is sized
        # here and re-sized from the machine on every memory sample
        # (_refresh_memory_budget_locked); at least one step is always
        # admitted, so no single tile can deadlock.
        self._mesh_memory_estimates: dict = {}
        self._memory_budget = (
            step_memory_budget_gigabytes()
            if cache_aware_admission_enabled()
            else mesh_memory_budget_gigabytes())
        self._memory_in_use = 0.0
        self._memory_holders: dict = {}   # (tile, step) -> gigabytes
        # the machine ledger's record of each running step (its child's
        # process tree grows into it): (tile, step) -> Reservation
        self._ledger_holds: dict = {}
        # #2083: each tile's recorded per-step peaks and the airports its
        # history plans, read at admission (step_memory.projected_gigabytes)
        self._recorded_peaks: dict = {}   # tile -> {step: gigabytes}
        self._airports_planned: dict = {}  # tile -> planned airports / None
        # #2101: steps held for memory, oldest first — the oldest is a
        # reservation later steps may not take (memory_waits module doc)
        self._memory_waits = MemoryWaits()
        self._memory_wait_sent: dict = {}   # key -> what the rows show
        # #2103: steps held for the disk's free-space floor, key ->
        # (free, floor) bytes, and the last floor reading (time, result).
        self._disk_waits: dict = {}
        self._disk_checked = (0.0, (True, 0, 0))
        self._memory_sampled_at = 0.0
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
        # Every tile admitted to this run, whichever press queued it
        # (#1641): the boundary check's "a tile this build is building".
        self._run_cells: set = set()
        # #1643: the boundary batch each tile's CURRENT attempt sent with
        # its vector step (where its airports are chosen), and the tiles
        # that must run that step again once their step in flight ends.
        self._vector_batches: dict = {}
        self._reselect: dict = {}
        self._judging = 0          # judgements in flight hold the run open
        self._children: list = []
        self._next_child_index = 0
        self._done = 0
        self._errors = 0
        # #1624: each tile's LAST outcome (True built) — a tile re-queued
        # after a fixable failure that then builds counts as built in
        # ``RunDone``, not also as failed; the attempt counters above
        # still pace the progress line.
        self._last_ok: dict = {}
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
                                     custom_build_dir, step_flags,
                                     boundary_policy=boundary_policy,
                                     missing_art=missing_art,
                                     overrides=overrides, priority=priority)

    def _admit_batch_locked(self, tiles, provider, zoomlevel,
                            custom_build_dir, step_flags,
                            boundary_policy=None, missing_art=None,
                            overrides=None, priority=None):
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
        with tile_time_model.batch_reads():
            admitted = self._admit_tiles_locked(
                tiles, full_plan, program, provider, zoomlevel,
                custom_build_dir, boundary_policy, missing_art, overrides,
                priority)
        self._total += len(admitted)
        return admitted

    def _admit_tiles_locked(self, tiles, full_plan, program, provider,
                            zoomlevel, custom_build_dir, boundary_policy,
                            missing_art, overrides=None, priority=None):
        admitted = []
        queued = set(self._queue)              # a planet queue: O(1) checks
        carried = {child.tile for child in self._children}
        # The session's record of each tile's build folder (#2032: a batch
        # that joined a live run kept the default folder, so the imagery
        # registration and the World publish looked in the wrong place).
        note_dirs = getattr(self._session, "_note_build_dirs", None)
        for tile in tiles:
            if (tile in queued or tile in self._next_step_index
                    or tile in carried):
                continue
            queued.add(tile)
            admitted.append(tile)
            if note_dirs is not None:
                note_dirs([tile], custom_build_dir)
            self._run_cells.add((int(tile[0]), int(tile[1])))
            # A new attempt (#1326), with a clock that starts at zero: a
            # stopped or finished tile queued again must not inherit the
            # previous attempt's wall clock.
            self._start_attempt(tile)
            self._vector_batches.pop(tile, None)
            self._reselect.pop(tile, None)
            self._tile_first_started.pop(tile, None)
            self._tile_final_elapsed.pop(tile, None)
            self._tile_arguments[tile] = {
                "provider": provider,
                "zoomlevel": zoomlevel,
                "custom_build_dir": custom_build_dir,
                # Per-batch, exactly like provider/zoomlevel: the worker
                # child receives it in its build command and lands it on
                # its own tile object (spec §C.3).
                "boundary_policy": boundary_policy,
                # #433: the batch's missing-art answer, per batch likewise
                "missing_art": missing_art,
            }
            if overrides:
                # #818: the batch's per-build switches, likewise — sent
                # only when set, so the child command stays as before.
                self._tile_arguments[tile]["overrides"] = dict(overrides)
            self._programs[tile] = list(program)
            self._static_windows[tile] = {
                key: (base, width) for (key, base, width) in full_plan
            }
            features = {}
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
            # A mesh the build will REUSE (#615) reads a record, not a
            # raster: it must not wait for memory a real mesh would hold.
            self._mesh_memory_estimates[tile] = (
                0.0 if "mesh" in (features.get("reused_steps") or ())
                else self._estimate_mesh_memory(tile, custom_build_dir))
            self._recorded_peaks[tile] = _recorded_step_peaks(tile)
            self._airports_planned[tile] = features.get("airports_planned")
            self._percent_high_water.pop(tile, None)
            self._forget_cache_state_locked(tile)
            self._queue_tile_locked(tile, priority)
        return admitted

    def _rank_of(self, tile):
        return self.__dict__.setdefault("_priority", {}).get(
            tile, _DEFAULT_RANK)

    def _queue_tile_locked(self, tile, priority=None):
        """Queue ``tile`` by its batch's rank (World spec §8.4): behind
        every tile ranked the same or higher, so plain presses stay
        first-in-first-out."""
        ranks = self.__dict__.setdefault("_priority", {})
        if priority is None:
            ranks.pop(tile, None)
        else:
            ranks[tile] = tuple(priority)
        ORDER.place(self._queue, tile, self._rank_of(tile), self._rank_of)

    def _laxity_first_locked(self):
        """The laxity guard (``ORDER.urgent``): a queued tile with a
        deadline whose slack is under one build's length moves to the
        head of the queue."""
        now = time.time()
        entries = []
        for tile, (_klass, deadline) in self._priority.items():
            if deadline == float("inf") or tile not in self._queue:
                continue
            estimate = sum((self._estimates.get(tile) or {}).values())
            entries.append((tile, deadline, estimate * TIME_SPREAD_KNOWN[1]))
        tile = ORDER.urgent(entries, now)
        if tile is not None and self._queue[0] != tile:
            self._queue.remove(tile)
            self._queue.appendleft(tile)

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
        self._make_room()
        # Import the fetch subsystems' cache predicates off the dispatch
        # path (see preload_cache_predicates), and BEFORE the handshakes
        # so the two waits overlap: the first sweep below must be able to
        # ask them (issue #344 — it used to run first, and every warm
        # tile of the first wave took a fetch token).
        preload = None
        if cache_aware_admission_enabled():
            preload = threading.Thread(
                target=self._preload_predicates_then_dispatch, daemon=True)
            preload.start()
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
        if preload is not None:
            # Bounded: a slow import delays the first sweep, never the
            # run — past the bound tiles read as not cached (the old
            # behaviour) and the preload's own sweep admits the rest.
            preload.join(PREDICATE_PRELOAD_WAIT_SECONDS)
        with self._lock:
            self._dispatch_locked()
            self._warmer_running = True
        threading.Thread(target=self._osm_cache_warmer, daemon=True).start()
        threading.Thread(target=self._ticker, daemon=True).start()
        # Children spawned believing `slots` siblings share the machine;
        # tell them the real count right away (a two-tile run on four
        # slots must not throttle itself for two ghosts).
        self._broadcast_sibling_count()
        # A cancel that landed during the handshake window may have
        # drained the queue already; settle immediately in that case.
        self._maybe_finish()
        return True

    def _make_room(self):
        """Room on disk for the run's tiles before any starts (owner
        2026-11-18T13:32Z, ``storage_room``): no storage pass touches a
        tile once its build holds it."""
        from . import storage_room
        with self._lock:
            tiles = list(self._queue)
            if not tiles:
                return
            arguments = self._tile_arguments[tiles[0]]
            program = self._programs[tiles[0]]
        storage_room.before_run(
            tiles, arguments["provider"], arguments["zoomlevel"],
            arguments["custom_build_dir"],
            ("vector" in program, "imagery" in program,
             "overlays" in program))

    def _preload_predicates_then_dispatch(self):
        """Preload thread body: register the predicates, then sweep.

        A "not cached" given while the predicates were unanswerable is
        never memoised, but nothing re-asked it either until some step
        happened to finish — so a warm tile queued behind a full fetch
        class sat there for the length of another tile's fetch phase.
        """
        preload_cache_predicates()
        with self._lock:
            self._dispatch_locked()

    def enqueue(self, tiles, provider, zoomlevel, custom_build_dir,
                step_flags, boundary_policy=None, missing_art=None,
                overrides=None, priority=None):
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
                tiles, provider, zoomlevel, custom_build_dir, step_flags,
                boundary_policy=boundary_policy, missing_art=missing_art,
                overrides=overrides, priority=priority)
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
        with self._lock:
            self._judging += 1
        threading.Thread(target=self._reselect_neighbours, args=(admitted,),
                         daemon=True, name="o4-boundary-reselect").start()
        return len(admitted)

    # -- #1643: a neighbour that joins after a tile chose its airports ---
    def _reselect_neighbours(self, admitted):
        """Judge again every tile whose airports were chosen against a
        batch lacking one of the *admitted* tiles (``boundary_reselect``):
        one that skipped an airport into it runs its vector step again.
        The judgement reads CIFP and apt.dat (seconds on a real tile), so
        it runs on its own thread, never on the command's or under the
        lock, and holds the run open until it lands (``_judging``)."""
        try:
            with self._lock:
                chosen = dict(self._vector_batches)
            skipped = {}
            for (tile, batch) in chosen.items():
                icaos = BOUNDARY.airports_skipped_into(tile, batch, admitted)
                if icaos:
                    skipped[tile] = icaos
            with self._lock:
                for (tile, icaos) in sorted(skipped.items()):
                    self._reselect_tile_locked(tile, icaos)
                if skipped:
                    self._dispatch_locked()
        finally:
            with self._lock:
                self._judging -= 1
            self._maybe_finish()

    def repatch(self, tile, icaos, line):
        """#2169 (3): *tile*'s patch of *icaos* was built against what
        X-Plane no longer draws (a Gateway install this run): its vector
        step runs again (:meth:`_reselect_tile_locked`), saying *line*."""
        with self._lock:
            self._reselect_tile_locked(tile, icaos, line)
            self._dispatch_locked()

    def _reselect_tile_locked(self, tile, icaos, line=None):
        """A tile still on its program re-runs from its vector step when
        its step in flight ends; a FINISHED, built tile is queued again; a
        queued attempt reads the run afresh at its own vector dispatch."""
        if self._vector_batches.get(tile) is None:
            return                          # re-chosen already, or anew
        carried = any(child.tile == tile for child in self._children)
        if tile in self._queue:
            return
        line = line or (
            "Tile %s: %s crosses into a tile queued after its airports "
            "were chosen; building its vector step again to patch it."
            % (_short_latlon(tile), ", ".join(icaos)))
        print(line)
        self.tile_log_line(tile, line)
        if carried or tile in self._next_step_index:
            self._reselect[tile] = icaos
        elif self._last_ok.get(tile):
            self._readmit_locked(tile)

    def _rewind_to_vector_locked(self, tile):
        """Point a carried tile back at its vector step: every step from
        there runs again on the patch it now builds."""
        self._next_step_index[tile] = self._programs[tile].index("vector")
        self._vector_batches.pop(tile, None)
        self._tile_warnings.pop(tile, None)
        self._percent_high_water.pop(tile, None)

    def _readmit_locked(self, tile):
        """Queue a finished tile again with its own batch's arguments."""
        program = list(self._programs[tile])
        windows = self._static_windows[tile]
        full_plan = [(key,) + tuple(windows[key]) for key in program]
        arguments = self._tile_arguments[tile]
        self._total += len(self._admit_tiles_locked(
            [tile], full_plan, program, arguments["provider"],
            arguments["zoomlevel"], arguments["custom_build_dir"],
            arguments.get("boundary_policy"), arguments.get("missing_art"),
            arguments.get("overrides")))

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
                if step_parking.pool_full_locked(self):
                    break
                self._start_new_tile_locked(child)
        self._lend_imagery_tokens_locked()
        step_parking.retire_surplus_locked(self)

    def _grow_past_parked(self):
        """Start one worker for the queue behind parked children."""
        try:
            self._spawn_child()
        finally:
            with self._lock:
                self._parked_spawns -= 1
                self._dispatch_locked()
        self._broadcast_sibling_count()

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

        The tile's own recorded peak for the step when it has one
        (#2083), else the mesh step's elevation-level sizing or the flat
        table (``step_memory.projected_gigabytes``) — the non-mesh steps
        only while the cache-aware admission gate is on; with it off the
        projection is the pre-2026-07-30 mesh-only one.
        """
        if step_key == "mesh":
            default = self._mesh_memory_estimates.get(
                tile, MESH_MEMORY_DEFAULT_GB)
            if default <= 0.0:
                return 0.0          # a reused mesh reads a record
        elif not cache_aware_admission_enabled():
            return 0.0
        else:
            default = STEP_MEMORY_ESTIMATES_GB.get(step_key, 0.0)
            if default <= 0.0:
                return 0.0
        return step_memory.projected_gigabytes(
            step_key, self._recorded_peaks.get(tile),
            default, self._airports_planned.get(tile))

    def _step_memory_charge(self, tile, step_key):
        """What the step holds against the budget once started (and what a
        held one reserves): its projection, capped for a step whose inner
        work gates itself on live memory (``step_memory.charged_gigabytes``).
        """
        return step_memory.charged_gigabytes(
            step_key, self._step_memory_estimate(tile, step_key))

    def _step_memory_booking(self, tile, step_key):
        """What the step BOOKS once started — in the run and on the machine
        ledger alike: its charge, except that a self-gated step books its
        own parse only (``step_memory.ledger_gigabytes``): its airport
        builds and their pools book their memory on the ledger, slot by
        slot, against live memory.  Until 2026-11-18 the run booked a
        vector step at 8 GB besides: app 1.0.558 started eleven vector
        steps on 119 GB free and held the twelfth ("94.7 of its 95.2 GB
        budget") while the ledger held 33 GB of them."""
        return step_memory.ledger_gigabytes(
            step_key, self._step_memory_charge(tile, step_key))

    def _memory_admits_locked(self, tile, step_key):
        """True when the step's memory fits now (owner 2026-11-18, the
        rule at :func:`step_memory_budget_gigabytes`).

        The step NEEDS its booking (:meth:`_step_memory_booking`) less
        what its tile's worker already
        holds (a step's projection is its whole process tree's peak, and
        the worker keeps the memory of the tile's earlier steps).  The run
        has ``_memory_budget`` (free above the headroom, re-read every
        sample) less what its running steps have BOOKED and not yet grown
        into (:meth:`_run_booked_locked`).  One step is always admitted
        (a single tile must never deadlock, however big its raster), and
        a running step is never paused or stopped.

        #2101: every refused step is held in FIFO order, and the oldest
        held step RESERVES its need — no other step that needs more than
        ``TINY_STEP_GB`` starts unless the run's room still holds both.
        When the waiter is the only work the run could start and only
        memory other programs hold stands in its way, it starts: its
        vector step's airport builds take machine slots against live
        memory one worker at a time (``O4_Machine_Slots.try_take``).

        THE MACHINE LEDGER (incident 2026-11-17): the machine's verdict
        (``O4_Machine_Slots.machine_verdict``) is free memory less what
        every build on the machine (other app sessions, the harness,
        command-line runs, this run) has booked and not yet grown into,
        X-Plane's room and, for a lane, the app's.  It holds every step,
        the run's first one too, when other builds, X-Plane or a pressure
        that refuses this role stand in its way (``contended``); free
        memory alone holds only the heavy ones.  An admitted step books
        its memory there (:meth:`_try_start_step_locked`).
        """
        need = self._step_memory_need_locked(tile, step_key)
        if need <= 0.0:
            return True
        key = (tile, step_key)
        reserved = self._memory_waits.oldest(self._memory_wait_pending_locked)
        if (reserved is not None and reserved[0] != key
                and need > TINY_STEP_GB
                and self._memory_wait_startable_locked(reserved[0])
                and not self._run_fits_locked(need + reserved[1].needed_gb)):
            self._hold_for_memory_locked(
                key, need, REASON_RUN,
                behind="%s %s step" % (_short_latlon(reserved[0][0]),
                                       reserved[0][1]))
            return False
        idle = not self._memory_holders
        machine = O4_Machine_Slots.machine_verdict(need, idle=idle)
        held = not machine.ok and (
            machine.contended or step_key in step_memory.LIVE_CHECKED_STEPS)
        if not idle and not self._run_fits_locked(need):
            # The run's own steps stand in the way when they hold (booked
            # or grown) what the need lacks; else memory others hold.
            reason = (REASON_RUN if need <= self._memory_budget
                      + self._run_resident_locked() else REASON_MACHINE)
        elif held:
            reason = REASON_MACHINE
        else:
            return True
        if (reason == REASON_MACHINE and not machine.contended
                and reserved is not None and reserved[0] == key
                and self._only_waiting_work_locked(key)):
            return True
        # Every refused step is held and shown (a tile must never look
        # stalled): the first refusal prints, the row gets a MemoryWait.
        self._hold_for_memory_locked(
            key, need, reason,
            machine=machine if reason == REASON_MACHINE and not machine.ok
            else None)
        return False

    def _step_memory_need_locked(self, tile, step_key):
        """What the step needs free to start: its charge less what its
        tile's idle worker already holds from the tile's earlier steps
        (sampled; nothing for a tile's first step, whose record was
        measured on its own)."""
        charge = self._step_memory_booking(tile, step_key)
        if not self._next_step_index.get(tile, 0):
            return charge
        held = max([getattr(child, "tree_gb", 0.0) for child in self._children
                    if child.tile == tile and child.running_step is None]
                   or [0.0])
        return max(0.0, charge - held)

    def _run_resident_locked(self):
        """What this run's running steps' process trees hold (sampled)."""
        return sum(getattr(child, "tree_gb", 0.0) for child in self._children
                   if child.running_step is not None)

    def _run_booked_locked(self):
        """What this run's running steps have booked and their process
        trees have not yet grown into: each holder's charge less its
        child's sampled tree (a step past its charge books nothing)."""
        grown = {(child.tile, child.running_step):
                 getattr(child, "tree_gb", 0.0) for child in self._children
                 if child.running_step is not None}
        return sum(max(0.0, charge - grown.get(key, 0.0))
                   for key, charge in self._memory_holders.items())

    def _run_fits_locked(self, gigabytes):
        """Would ``gigabytes`` more fit the run's room now — free memory
        above the headroom, less what its steps booked and not yet use?"""
        return self._run_booked_locked() + gigabytes <= self._memory_budget

    #: how long one reading of the disk's free space serves the gate
    DISK_CHECK_SECONDS = 2.0

    def _disk_admits_locked(self, tile, step_key):
        """#2103: True when the data folder's disk has its free-space
        floor (``storage_floor``).  Under it, a relief starts in the
        background (offload to a tier, then trim) and the step is held,
        its row saying why; the ticker's dispatch starts it once the floor
        is met.  Running steps are never paused."""
        now = time.time()
        if now - self._disk_checked[0] >= self.DISK_CHECK_SECONDS:
            self._disk_checked = (now, FLOOR.admits())
        ok, free, floor = self._disk_checked[1]
        key = (tile, step_key)
        if ok:
            self._disk_waits.pop(key, None)
            return True
        FLOOR.relieve_async()
        if key not in self._disk_waits:
            print("Tile %s waits for disk space before its %s step "
                  "(%.0f GB free, keeping %.0f GB free)."
                  % (_short_latlon(tile), step_key, free / 1e9, floor / 1e9))
        self._disk_waits[key] = (free, floor)
        return False

    def _reserve_on_ledger_locked(self, child, step_key, charged):
        """Reserve a started step's memory on the machine ledger, covering
        its child's process tree (the child itself reserves nothing for
        the step: ``O4_Machine_Memory.ENV_STEP_RESERVED``).  Not in an
        ungated session (the suite's scheduling tests)."""
        if os.environ.get(O4_Machine_Slots.ENV_UNGATED):
            return
        process = getattr(child, "process", None)
        # The ledger counts growth from now; the projection is the whole
        # tree's peak, of which the worker already holds what the tile's
        # earlier steps left (``_step_memory_need_locked``'s rule).
        held = (getattr(child, "tree_gb", 0.0)
                if self._next_step_index.get(child.tile, 0) else 0.0)
        self._ledger_holds[(child.tile, step_key)] = MEMORY.reserve(
            max(0.0, step_memory.ledger_gigabytes(step_key, charged) - held),
            "%s %s step" % (_short_latlon(child.tile), step_key),
            pid=getattr(process, "pid", None))

    def _hold_for_memory_locked(self, key, estimate, reason, behind="",
                                machine=None):
        """Record a refused heavy step (FIFO) and log its first refusal
        with what holds it: the reserving step, what the run's steps
        booked and do not yet use, or the machine — then, for the machine, who holds its memory (the
        ledger's ``note_wait``: logged when the holders change; an app
        run's wait also asks the lanes to leave it room)."""
        import O4_Parallel_Utils as PARALLEL_UTILS

        free = PARALLEL_UTILS.machine_available_memory_gigabytes()
        booked = self._run_booked_locked()
        kept = O4_Machine_Slots.headroom_gigabytes()
        if machine is not None:
            # The ledger logs the wait, and again when its holders change.
            MEMORY.note_wait("tile %s's %s step" % (_short_latlon(key[0]),
                                                     key[1]),
                             machine, estimate)
            # The row names the holders when other builds, X-Plane or the
            # pressure are part of it; else it says what frees memory.
            self._memory_waits.note(
                key, estimate, free, reason,
                MEMORY.holders_text(MEMORY.snapshot())
                if machine.contended else "",
                booked, kept)
            return
        if behind:
            cause = "behind %s" % behind
        elif reason == REASON_RUN:
            cause = ("this run's steps have booked %.1f GB not yet in use; "
                     "%.1f GB kept free" % (booked, kept))
        else:
            cause = "%.1f GB kept free" % kept
        if self._memory_waits.note(key, estimate, free, reason, behind,
                                   booked, kept):
            print("Tile %s waits for free memory before its %s step "
                  "(needs about %.1f GB, %.1f GB free; %s)."
                  % (_short_latlon(key[0]), key[1], estimate, free, cause))

    def _refresh_memory_budget_locked(self):
        """Re-read the run's room from the machine NOW (free memory above
        the headroom, :func:`step_memory_budget_gigabytes`).  A move under
        ``MEMORY_BUDGET_HYSTERESIS_GB`` is ignored.  Only the cache-aware
        gate's room follows the machine; the legacy mesh budget is
        physical memory, already fixed."""
        if not cache_aware_admission_enabled():
            return
        budget = step_memory_budget_gigabytes()
        if abs(budget - self._memory_budget) >= MEMORY_BUDGET_HYSTERESIS_GB:
            self._memory_budget = budget

    def _memory_wait_pending_locked(self, key):
        """Is the held step still this run's next work for its tile?"""
        tile, step_key = key
        program = self._programs.get(tile)
        if not program:
            return False
        if tile in self._queue:
            return program[0] == step_key
        for child in self._children:
            if (child.tile == tile and child.running_step is None
                    and not child.retired and not child.cancelling):
                index = self._next_step_index.get(tile, 0)
                return index < len(program) and program[index] == step_key
        return False

    def _memory_wait_startable_locked(self, key):
        """Could the held step start if memory allowed — is it on a child,
        or is a child idle to take it from the queue?  A queued waiter
        with every child busy reserves nothing: holding the busy children's
        steps would keep any of them from ever freeing (a deadlock)."""
        tile = key[0]
        return any(
            not child.retired and not child.cancelling
            and (child.tile == tile or child.tile is None)
            for child in self._children)

    def _only_waiting_work_locked(self, key):
        """True when no other tile of the run waits to start a step: the
        queue holds no other tile and no other child is between steps."""
        tile = key[0]
        if any(queued != tile for queued in self._queue):
            return False
        return not any(
            child.tile is not None and child.tile != tile
            and child.running_step is None and not child.retired
            and not child.cancelling
            for child in self._children)

    def _announce_memory_waits(self):
        """Emit a ``MemoryWait`` for each held step whose row text changed,
        and a resolved one for each step no longer held (outside the
        lock; the ticker calls it)."""
        with self._lock:
            # A held step with no child free to take it waits for a worker,
            # not memory: its row shows the queue, not a memory wait.
            now = {key: wait
                   for key, wait in self._memory_waits.snapshot().items()
                   if self._memory_wait_pending_locked(key)
                   and self._memory_wait_startable_locked(key)}
            # #2103: a step held for the disk floor shows that instead.
            for key, (free, floor) in list(self._disk_waits.items()):
                if not self._memory_wait_pending_locked(key):
                    del self._disk_waits[key]
                    continue
                now[key] = _Wait(floor / 1e9, free / 1e9, FLOOR.REASON_DISK)
            sent = self._memory_wait_sent
            changes = []
            for key, wait in now.items():
                shown = (round(wait.needed_gb, 1), round(wait.free_gb),
                         wait.reason, wait.behind, round(wait.booked_gb))
                if sent.get(key) != shown:
                    sent[key] = shown
                    changes.append((key, wait, False))
            for key in [k for k in sent if k not in now]:
                del sent[key]
                changes.append((key, None, True))
        for (tile, step_key), wait, resolved in changes:
            self._session._emit(EVENTS.MemoryWait(
                lat=tile[0], lon=tile[1], step_key=step_key,
                needed_gb=0.0 if wait is None else round(wait.needed_gb, 1),
                free_gb=0.0 if wait is None else round(wait.free_gb, 1),
                reason="" if wait is None else wait.reason,
                message="" if wait is None else (
                    FLOOR.wait_message(wait.free_gb, wait.needed_gb)
                    if wait.reason == FLOOR.REASON_DISK else wait_message(
                        wait.needed_gb, wait.free_gb, wait.reason,
                        wait.behind, wait.booked_gb, wait.kept_gb)),
                resolved=resolved))

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
            # The batch's boundary answer, as the worker applies it: the
            # §D.2 predicate warms outside neighbours only under it.
            if arguments.get("boundary_policy") in ("neighbour", "skip"):
                configuration.boundary_policy = arguments["boundary_policy"]
            if arguments.get("overrides"):
                configuration.apply_build_overrides(arguments["overrides"])
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
        if self._class_full_locked(step_class):
            return False
        if not self._disk_admits_locked(child.tile, step_key):
            return False
        # One machine-wide admission: the ledger is read and the step's
        # reservation written with no other build admitting in between.
        with MEMORY.admission():
            return self._admit_and_start_locked(child, step_key, step_class)

    def _class_full_locked(self, step_class):
        """Is ``step_class`` closed to a real step?  An imagery token lent
        to a vector step's prefetch does not count: that download is
        speculative, so it must never keep a tile's real imagery step
        waiting.  The servers stay bounded per request by their
        ``net:<host>`` classes, whoever holds a token."""
        active = self._class_active[step_class]
        if step_class == "imagery":
            active -= sum(1 for child in self._children
                          if getattr(child, "prefetch_token", False))
        return active >= self._class_limits[step_class]

    def _admit_and_start_locked(self, child, step_key, step_class):
        """:meth:`_try_start_step_locked` past its class and disk checks."""
        if not self._memory_admits_locked(child.tile, step_key):
            return False
        arguments = dict(self._tile_arguments[child.tile],
                         boundary_batch=self._boundary_batch_locked(
                             child.tile),
                         run_meshes=self._run_meshes_locked(child.tile))
        opens_job = (step_key == "vector"
                     and "imagery" in self._programs.get(child.tile, ()))
        prefetch = (opens_job and not getattr(child, "prefetch_token", False)
                    and self._may_prefetch_locked(child.tile, step_key))
        if opens_job:
            arguments = dict(arguments, prefetch=True, token_lent=prefetch)
        beside = self._objects_beside_locked(child.tile, step_key)
        if beside:
            arguments = dict(arguments, objects_beside=True)
        if child.start_step(step_key, arguments):
            child.objects_beside = beside
            if prefetch:
                self._class_active["imagery"] += 1
                child.prefetch_token = True
            if opens_job:
                child.imagery_job_open = True
            elif step_key == "imagery":        # this step adopts the job
                self._close_imagery_job_locked(child)
            self._step_started_at[(child.tile, step_key)] = time.time()
            if step_key == "vector":
                self._vector_batches[child.tile] = frozenset(
                    tuple(cell) for cell in arguments["boundary_batch"])
            self._tile_first_started.setdefault(child.tile, time.time())
            self._class_active[step_class] += 1
            child.step_class = step_class
            child.autopatch_pending = None
            # Started: held no longer (the gate is asked twice per start,
            # so the hold ends here, not when the gate first says yes).
            if self._memory_waits.clear((child.tile, step_key)):
                print("Tile %s has the memory it waited for; its %s step "
                      "starts." % (_short_latlon(child.tile), step_key))
            estimate = self._step_memory_booking(child.tile, step_key)
            if estimate > 0.0:
                self._memory_holders[(child.tile, step_key)] = estimate
                self._memory_in_use += estimate
                self._reserve_on_ledger_locked(child, step_key, estimate)
            return True
        return False

    def run_cells(self):
        """Every tile admitted to this run so far, as ``(lat, lon)``."""
        with self._lock:
            return frozenset(self._run_cells)

    def live_tiles(self):
        """The tiles queued or on a child now (not those finished), as
        ``(lat, lon)``."""
        with self._lock:
            return frozenset(
                {(int(t[0]), int(t[1])) for t in self._queue}
                | {(int(c.tile[0]), int(c.tile[1])) for c in self._children
                   if c.tile is not None})

    def _run_meshes_locked(self, tile):
        """``[[lat, lon], ...]``: the OTHER tiles of this run in the 3×3
        block around ``tile`` whose program builds a mesh (#2290): a
        re-seat of such a tile's airport while its ground is not built
        yet waits for that tile's own object stage (``guest_stage.
        note_run_meshes``).  The run's cells, as ``boundary_batch`` reads
        them — never its live progress, so a worker is asked the same
        work however the steps interleave."""
        return [cell for cell in self._boundary_batch_locked(tile)
                if tuple(cell) != (int(tile[0]), int(tile[1]))
                and "mesh" in (self._programs.get(tuple(cell)) or ())]

    def _boundary_batch_locked(self, tile):
        """``[[lat, lon], ...]`` the child's boundary check counts as built
        (issue #51, #1641): the tile and every tile of THIS RUN in the 3×3
        block around it, whichever press queued it — two presses into one
        run are one run.  Read at dispatch, so a tile queued after its
        neighbour was admitted still counts; only the neighbourhood is
        sent, since an airport claim crosses into adjacent cells only and
        a planet-sized run must not ride in every step command (#1225)."""
        (lat, lon) = (int(tile[0]), int(tile[1]))
        return [[lat + dlat, lon + dlon]
                for dlat in (-1, 0, 1) for dlon in (-1, 0, 1)
                if (dlat, dlon) == (0, 0)
                or (lat + dlat, lon + dlon) in self._run_cells]

    def _may_prefetch_locked(self, tile, step_key):
        """Whether this tile's vector step may download its likely
        orthophotos in the background (#1002, O4_Imagery_Prefetch).

        Only for a tile whose program builds imagery, and only while the
        imagery class has room: the prefetch takes an imagery token like
        any downloader, so the remote-server cap is the one the imagery
        step obeys.  The token comes back at the prefetch's
        ``ImageryDownloadsDone`` or at the step's end, whichever is first.
        """
        if step_key != "vector":
            return False
        if "imagery" not in self._programs.get(tile, ()):
            return False
        return (self._class_active["imagery"]
                < self._class_limits["imagery"])

    def _lend_imagery_tokens_locked(self):
        """Lend a freed imagery token to a tile whose job still waits for
        one, the tile nearest its imagery step first (#2254).  The token
        is counted here, the one owner; the job returns it when it drains
        or is adopted."""
        waiting = sorted(
            (child for child in self._children
             if getattr(child, "imagery_job_open", False)
             and not getattr(child, "prefetch_token", False)
             and child.tile is not None and not child.retired
             and not child.cancelling),
            key=lambda child: -self._next_step_index.get(child.tile, 0))
        for child in waiting:
            if (self._class_active["imagery"]
                    >= self._class_limits["imagery"]):
                return
            if child.send({"cmd": "imagery_token", "lat": child.tile[0],
                           "lon": child.tile[1]}):
                self._class_active["imagery"] += 1
                child.prefetch_token = True

    def _objects_beside_locked(self, tile, step_key):
        """Whether the tile's ``step_key`` may run beside (mesh) or with
        (masks) the mesh step's object stage: the imagery step, which joins
        it, follows in this child (#1264, ``O4_Object_Stage_Beside``)."""
        if step_key not in ("mesh", "masks"):
            return False
        program = tuple(self._programs.get(tile, ()))
        index = self._next_step_index.get(tile, 0)
        return "imagery" in program[index + 1:]

    def _close_imagery_job_locked(self, child):
        """The tile left this child: its job can take no token, and one it
        holds comes back."""
        child.imagery_job_open = False
        self._release_prefetch_token_locked(child)

    def _release_prefetch_token_locked(self, child):
        """Return the imagery token lent to a tile's imagery job."""
        if not getattr(child, "prefetch_token", False):
            return False
        child.prefetch_token = False
        self._class_active["imagery"] = max(
            0, self._class_active["imagery"] - 1)
        return True

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
        if (old_class == step_parking.WAITING_CLASS
                and child.parked_class is not None):
            child.parked_class = new_class     # applies when it resumes
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
                or step_parking.held_class(child)
                != STEP_CLASSES.get("vector", "osm")
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
                or step_parking.held_class(child) != STEP_CLASSES.get(
                    "imagery", "imagery")):
            return False
        self._swap_class_locked(child, IMAGERY_TAIL_CLASS)
        return True

    def _imagery_job_done_locked(self, child, payload):
        """The tile's imagery job gave up its token.  A report about a tile
        this child no longer carries changes nothing."""
        tile = child.tile
        if tile is None or (payload.get("lat"), payload.get("lon")) != tuple(
                tile[:2]):
            return False
        child.imagery_job_open = False
        return self._release_prefetch_token_locked(child)

    def _release_step_resources_locked(self, child):
        """Return a finished/aborted step's class and memory budget.  An
        imagery token lent to the tile's job outlives the step (#2254)."""
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
        child.parked_class = None
        child.parked_memory = None
        child.autopatch_pending = None
        held = self._memory_holders.pop((child.tile, step_key), None)
        if held is not None:
            self._memory_in_use = max(0.0, self._memory_in_use - held)
        reservation = self._ledger_holds.pop((child.tile, step_key), None)
        if reservation is not None:
            reservation.release()
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
        if self.__dict__.get("_priority"):
            self._laxity_first_locked()
        # Only the head of the queue is considered: a planet-sized queue
        # must cost nothing per queued tile (#1225), and the cache
        # predicates build a tile's configuration on first ask.
        for candidate in itertools.islice(self._queue, QUEUE_SCAN_WINDOW):
            if candidate == self._warming_tile:
                continue
            first_step = self._programs[candidate][0]
            first_class = self._effective_step_class_locked(
                candidate, first_step)
            if self._class_full_locked(first_class):
                continue
            if not self._memory_admits_locked(candidate, first_step):
                continue
            tile = candidate
            break
        if tile is None:
            return False
        self._queue.remove(tile)
        child.tile = tile
        # The tile's build starts here: its own build log opens (#1226).
        if self._tile_logs is not None:
            self._tile_logs.begin(tile, FNAMES.build_dir(
                tile[0], tile[1], (self._tile_arguments.get(tile)
                                   or {}).get("custom_build_dir", "")))
        child.step_failed = False
        self._next_step_index[tile] = 0
        if not self._try_start_step_locked(child):
            # Dead pipe: put the tile back for another child; the exit
            # path cleans the child up.
            child.tile = None
            self._queue.appendleft(tile)
            return False
        return True

    def tile_log_line(self, tile, text):
        """One line of ``tile``'s build into its own log (#1226)."""
        if self._tile_logs is not None:
            self._tile_logs.line(tile, text)

    # -- attempts (#1326) ------------------------------------------------
    def _start_attempt(self, tile):
        """Number the tile's new attempt in the session (a bare test
        session without attempts numbers nothing)."""
        new_attempt = getattr(self._session, "new_tile_attempt", None)
        if new_attempt is not None:
            new_attempt(tile)

    def _attempt(self, tile):
        """The tile's current attempt number, 0 when unknown."""
        current = getattr(self._session, "tile_attempt", None)
        return current(tile) if current is not None else 0

    def _freeze_tile_clock_locked(self, tile):
        """A stopped tile's clock stops with it: TileClocks reports the
        elapsed so far as final instead of counting on (#1326)."""
        started = self._tile_first_started.get(tile)
        if started is not None:
            self._tile_final_elapsed.setdefault(
                tile, max(0.0, time.time() - started))

    # -- cancellation ----------------------------------------------------
    def _stopped_state(self, tile, attempt=0):
        """The stopped ``TileState`` of ``tile``, its scenery packs put
        back first (#598) — for a tile no child is working on any more.
        ``attempt`` is the stopped attempt, taken under the lock where the
        stop was decided: a re-queue may start the next one meanwhile."""
        build_dir = (self._tile_arguments.get(tile)
                     or {}).get("custom_build_dir", "")
        return stopped_tile_state(tile[0], tile[1], build_dir, attempt)

    def cancel_tile(self, tile):
        emit_stopped = False
        cancelling = None
        ending = None
        with self._lock:
            attempt = self._attempt(tile)
            if tile in self._queue:
                self._queue.remove(tile)
                emit_stopped = True
                accepted = True
            else:
                accepted = False
                for child in self._children:
                    if child.tile != tile or child.retired:
                        continue
                    if (child.running_step is None
                            and getattr(child, "objects_beside", False)):
                        # Between steps, but the mesh step's object stage
                        # may still write packs in it (#1264): the child
                        # ends (its exit waits for the stage within the
                        # shutdown grace) and the tile is reported stopped,
                        # its packs put back, once it has exited.
                        child.cancelling = True
                        ending = child
                        accepted = True
                    elif child.running_step is None:
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
                        cancelling = child
                    break
            if accepted:
                self._freeze_tile_clock_locked(tile)
        if ending is not None:
            self._escalate_cancel(ending)
        if cancelling is not None:
            # Same bounded clock as cancel_all: a per-tile Stop on a
            # child wedged in an operation that never polls its red
            # flag must not hang the run.
            self._arm_cancel_escalation(cancelling)
        if emit_stopped:
            self._session._emit(self._stopped_state(tile, attempt))
            self._maybe_finish()
        return accepted

    def slow_step_choice(self, tile, choice):
        """Hand the user's slow-step answer (#1351) to the child running
        the tile's step; False when no child is running one."""
        # No scheduler lock: a dialog answer never waits for a dispatch
        # (owner 2026-11-20T18:40Z); the list is copied whole, and the
        # child's own stdin lock orders its pipe.
        for child in list(self._children):
            if (child.tile == tile and not child.retired
                    and child.running_step is not None):
                return child.send({"cmd": "slow_step_choice",
                                   "lat": tile[0], "lon": tile[1],
                                   "choice": choice})
        return False

    def cancel_all(self):
        with self._lock:
            self._cancel_all = True
            drained = list(self._queue)
            self._queue.clear()
            waiting = []
            cancelling = []
            ending = []
            for child in self._children:
                if child.retired or child.tile is None:
                    continue
                if (child.running_step is None
                        and getattr(child, "objects_beside", False)):
                    child.cancelling = True        # see cancel_tile (#1264)
                    ending.append(child)
                elif child.running_step is None:
                    waiting.append(child.tile)
                    child.tile = None
                else:
                    child.cancelling = True
                    child.send({"cmd": "cancel"})
                    cancelling.append(child)
            attempts = {tile: self._attempt(tile)
                        for tile in drained + waiting}
        for tile in drained + waiting:
            self._session._emit(self._stopped_state(tile, attempts[tile]))
        for child in cancelling:
            self._arm_cancel_escalation(child)
        for child in ending:
            self._escalate_cancel(child)
        self._maybe_finish()

    def _arm_cancel_escalation(self, child):
        """Put a mid-step child's cooperative cancel on a bounded clock.

        The cancel command only raises the child's red_flag — a step
        wedged in an operation that never polls it would keep `busy`
        true forever and the run would never finish.  Escalate on a
        bounded clock: SIGTERM (the child's transport turns it into a
        bounded wind-down and exit), then SIGKILL as the backstop;
        _on_child_exit does the accounting either way and reports the
        tile stopped (the cancel was the user's).  ONE implementation for
        cancel_tile and cancel_all.
        """
        escalate_timer = threading.Timer(
            CANCEL_ESCALATE_SECONDS, self._escalate_cancel, (child,))
        escalate_timer.daemon = True
        escalate_timer.start()

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
        if event_name == "ImageryJobDone":
            # The tile's imagery job has no more use for its token (#2254).
            with self._lock:
                if self._imagery_job_done_locked(child, payload):
                    self._dispatch_locked()
            return
        if event_name == "StepWaiting":
            # The step only waits (another tile's download, a backoff, a
            # cache lock), or works again: its token follows (#2254).
            with self._lock:
                if step_parking.note_waiting_locked(
                        self, child, bool(payload.get("waiting"))):
                    self._dispatch_locked()
                grow = step_parking.extra_worker_wanted_locked(self)
            if grow:
                threading.Thread(target=self._grow_past_parked,
                                 daemon=True).start()
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
            if event.ok:
                # a pack answer this build caught the tile up with
                event = self._session.with_paid_rebuilds(event)
            # #564: the terminal's warnings (the last step's child read
            # them from the tile's unpatched-airports sidecar) close the
            # tile's log below, after "Tile … completed in".
            with self._lock:
                self._tile_warnings[tile] = (list(event.warnings),
                                             list(event.notes))
            with self._lock:
                self._last_ok[tile] = bool(event.ok)
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
            if event.label == "stopped" and child.cancelling:
                # The stop is reported once the tile is RELEASED (#1326):
                # a front end re-queues it on this notice, and a re-queue
                # arriving while the child still carries the tile would be
                # refused as a duplicate.
                child.held_stopped = event
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
        if event_name == "Log" and tile is not None:
            # The child knows no orchestration: its line is the tile it
            # carries (#1226).
            event = dataclasses.replace(event, tile=tuple(tile))
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
        self._record_step_peak(child)
        with self._lock:
            self._release_step_resources_locked(child)
            stopped = None
            if child.cancelling:
                # Spec §3.4: never reuse a red-flagged interpreter.
                last_step = (self._next_step_index.get(child.tile, 0)
                             >= len(self._programs.get(child.tile, ())) - 1)
                if child.tile is not None:
                    stopped = (child.tile, self._attempt(child.tile),
                               getattr(child, "held_stopped", None),
                               last_step)
                child.held_stopped = None
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
                # #1643: a neighbour joined after this tile chose its
                # airports, and one of them crosses into it.
                rerun = self._reselect.pop(child.tile, None)
                finishing = (self._next_step_index[child.tile]
                             >= len(self._programs.get(child.tile, ())))
                if rerun and not finishing:
                    self._rewind_to_vector_locked(child.tile)
                if finishing:
                    # Tile complete (its final BuildDone was forwarded).
                    # The per-tile total the children cannot print (each
                    # sees one step): dispatched-step seconds summed by
                    # _release_step_resources_locked.
                    closing = ["Tile %s completed in %s."
                               % (_short_latlon(child.tile),
                                  UI.nicer_timer(
                                      self._tile_step_seconds.pop(
                                          child.tile, 0.0)))]
                    closing += FAIL.closing_lines(
                        *self._tile_warnings.pop(child.tile, ([], [])))
                    print("")
                    for line in closing:
                        print(line)
                        # Joins the tile's (just closed) build log.
                        self.tile_log_line(child.tile, line)
                    self._next_step_index.pop(child.tile, None)
                    self._percent_high_water.pop(child.tile, None)
                    (finished, child.tile) = (child.tile, None)
                    stale = []
                    if self._last_ok.get(finished):
                        # #1989: the built tile's Gateway airports (the
                        # per-step children each see one step); #2169 (3):
                        # one installed this run after its patch was built
                        _offer_gateway_airports(*finished)
                        _offer_pack_overlaps(*finished)
                        from auto_patch import gateway_stage as _GW
                        stale = _GW.stale_patches(*finished)
                        if stale and not rerun:
                            line = _gateway_line(finished, stale)
                            print(line)
                            self.tile_log_line(finished, line)
                    if (rerun or stale) and self._last_ok.get(finished):
                        self._readmit_locked(finished)
            if child.tile is None:
                self._close_imagery_job_locked(child)
            self._dispatch_locked()
        if stopped is not None:
            self._report_released_stop(*stopped)
        if respawn:
            replacement = self._spawn_child()
            if replacement is not None:
                with self._lock:
                    self._dispatch_locked()
        self._broadcast_sibling_count()
        self._maybe_finish()

    def _record_step_peak(self, child):
        """Write the finished step's sampled peak into the record the step
        just wrote (#2083), before the tile's next step is dispatched."""
        with self._lock:
            tile, step_key = child.tile, child.running_step
            peak = getattr(child, "step_peak_gb", 0.0)
            started = self._step_started_at.get((tile, step_key))
        if tile is None or step_key is None or started is None \
                or peak <= 0.0 or getattr(child, "cancelling", False):
            return
        tile_time_model.record_step_peak(
            tile[0], tile[1], step_key, peak, since=started)

    def _sample_step_memory(self):
        """Sample every running step's process tree and keep each step's
        peak on its child (#2083); then dispatch again, so a step held by
        the live free-memory check starts once memory is back."""
        with self._lock:
            live = {child.process.pid: (child, child.running_step)
                    for child in self._children
                    if getattr(child, "process", None) is not None
                    and not child.retired}
        resident = (step_memory.tree_resident_gigabytes(list(live))
                    if live else {})
        with self._lock:
            for pid, (child, step_key) in live.items():
                gigabytes = resident.get(pid, 0.0)
                # What the worker holds now: grown into its step's booking,
                # or left from its tile's earlier steps (the next step's
                # projection is the whole tree's peak, so it counts).
                child.tree_gb = gigabytes
                if step_key is not None and child.running_step == step_key:
                    child.step_peak_gb = max(child.step_peak_gb, gigabytes)
            self._refresh_memory_budget_locked()
            self._dispatch_locked()

    def _report_released_stop(self, tile, attempt, held, last_step):
        """A cancelled child let go of its tile: report it stopped NOW
        (#1326) — the child's own notice (it carries what the tile is left
        with, #598), else a bare one.  A child that ran its LAST step to
        the end before noticing the cancel already forwarded the tile's
        terminal, and that is the truth: no stop follows it."""
        if held is not None:
            self._session._emit(dataclasses.replace(held, attempt=attempt))
        elif not last_step:
            self._session._emit(TileState(
                lat=tile[0], lon=tile[1], state="queued", label="stopped",
                attempt=attempt))

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
        child.await_stderr_drained()
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
                stopped_attempt = self._attempt(stopped_tile)
                self._freeze_tile_clock_locked(stopped_tile)
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
                self._last_ok[crashed_tile] = False
                respawn = bool(self._queue) and not self._cancel_all
            self._close_imagery_job_locked(child)
            self._dispatch_locked()
        if stopped_tile is not None:
            lat, lon = stopped_tile
            self._session._emit(
                self._stopped_state(stopped_tile, stopped_attempt))
            print("Build worker for", _short_latlon(stopped_tile),
                  "exited while being stopped; its tile is marked stopped.")
        if crashed_tile is not None:
            lat, lon = crashed_tile
            self._session._emit(TileState(lat=lat, lon=lon, state="error",
                                          label="failed"))
            done_event = build_done(
                lat, lon, False,
                [FAIL.record("worker_died", child.crash_detail())],
                getattr(self._session, "app_driven", False))
            self._tile_warnings.pop(crashed_tile, None)
            self._session._emit(done_event)
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
                # Only the head of the queue (#1225): a planet-sized
                # queue must not be downloaded ahead of its builds.
                unwarmed = [t for t in itertools.islice(
                    self._queue, QUEUE_SCAN_WINDOW)
                    if t not in self._warmed_tiles]
                tile = next((t for t in unwarmed
                             if not self._worker_could_take_locked(t)),
                            None)
                behind = len(self._queue) > QUEUE_SCAN_WINDOW
                if tile is not None:
                    self._warming_tile = tile
            if tile is None:
                if not behind and not unwarmed:
                    return
                # The head moves on, or a worker takes the tile itself.
                time.sleep(WARM_AHEAD_POLL_SECONDS)
                continue
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
            if EXTRACTS is not None and EXTRACTS.extract_download_running(
                    (tile[0], tile[1], tile[0] + 1, tile[1] + 1)):
                # Its extract is on its way: warming now would only wait
                # for that transfer holding an osm token (#2254).  The
                # tile's build joins the transfer and filters the extract.
                with self._lock:
                    self._release_warm_token_locked()
                    self._warming_tile = None
                    self._warmed_tiles.add(tile)
                    self._dispatch_locked()
                self._maybe_finish()
                continue
            try:
                warmed_layers = self._warm_tile_layers(
                    tile, tile_build_dir, len(
                        VMAP.osm_layer_warm_specifications(
                            tile_configuration)))
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

    def _warm_tile_layers(self, tile, build_dir, layer_count):
        """Warm ``tile``'s layers in a worker process of their own
        (``osm_warm_process``: never on the command process's
        interpreter), stopping between layers when the run stops or a
        worker took the tile.  Returns the layers warmed."""
        runner = OSM_WARM.open_runner()
        warmed = 0
        try:
            for index in range(layer_count):
                with self._lock:
                    still_queued = tile in self._queue
                    stopping = self._finished or self._cancel_all
                if stopping or not still_queued:
                    break
                runner.layer(tile[0], tile[1], build_dir, index)
                warmed += 1
        finally:
            runner.close()
        return warmed

    def _worker_could_take_locked(self, tile):
        """Whether a worker could start queued ``tile`` now or once the
        pool grows: it is among the first N queued tiles, N = the idle
        children plus the children the slot count still allows.  The
        warmer leaves such a tile alone — warming it held it off an idle
        worker (owner's 1.0.568 run, 2026-11-20: -23-048 claimed by the
        warmer for an hour, a worker idle beside it for 23 minutes)."""
        alive = [child for child in self._children if not child.retired]
        free = sum(1 for child in alive
                   if child.tile is None and not child.cancelling)
        free += max(0, self._slots - len(alive))
        return tile in itertools.islice(self._queue,
                                        min(free, QUEUE_SCAN_WINDOW))

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
                if self._worker_could_take_locked(tile):
                    # A slot freed while the warmer waited: the tile's
                    # own worker downloads it.
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
            if self._queue or busy or self._judging:
                return
            self._finished = True
            children = list(self._children)
            done, errors = last_outcome_counts(self._last_ok)
            cancelled = self._cancel_all
        # The session leaves its "building" state BEFORE the bounded
        # child reaping below: a Build click landing the moment the last
        # tile finishes must start a fresh run immediately, not wait out
        # slow-exiting workers.
        self._session._run_finished()
        self._session._emit(RunDone(done_count=done, error_count=errors,
                                    cancelled=cancelled))
        self._session._announce_rebuild_pending(cancelled)
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
            if now - self._memory_sampled_at >= STEP_MEMORY_SAMPLE_SECONDS:
                self._memory_sampled_at = now
                try:
                    self._sample_step_memory()
                except Exception:
                    pass
            try:
                self._announce_memory_waits()
            except Exception:
                pass
            time.sleep(ETA_EMIT_SECONDS)
