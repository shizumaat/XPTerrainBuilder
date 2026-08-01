# Vector-step class split — stop throttling auto-patch with a
# server-politeness cap

Owner ruling 2026-07-30 (observed 5 tiles building with most of an
18-core machine idle): the auto-patch solve must not be limited by the
OSM class cap.

## 1. Defect (measured 2026-07-30)

Machine: 18 cores, 128 GB (59 GB free), load average 8.3 — ~46 %
utilisation with 5 tiles queued.  Six workers alive (correct:
`effective_build_slots(0)` → `min(6, 18//3, 128//6)` = 6); 2-3 doing
work at any instant, the rest parked in `_textiowrapper_readline`
awaiting a command.  The active set ROTATES between workers — cap
throttling, not a stall.

Cause: `parallel.STEP_CLASSES` maps `"vector" → "osm"` and
`OSM_CLASS_LIMIT = 2` (hardcoded).  But the vector step is a HYBRID: it
fetches OSM/vector data AND runs the auto-patch build
(`session.py:423`, "while auto-patch owns the vector step").
Auto-patch is the heaviest pure-CPU phase in the product —
single-threaded, minutes per airport (HECA ≈ 6 min at 99 % of one
core, measured repeatedly 2026-07-29).  So a cap whose documented
purpose is "guard REMOTE SERVERS" is serialising CPU work to 2 tiles.

The module's own doctrine (2026-07-17 owner ruling, quoted in
`parallel.py`): "Compute steps are UNCAPPED … processor arbitration [is
left] to the operating system — the caps that remain guard REMOTE
SERVERS, plus the mesh memory admission gate."  The vector step simply
never got split.

Note: raising `max_build_slots` does NOT help — the cap is
`min(OSM_CLASS_LIMIT, slots)`.

## 2. Semantics (fixed)

A tile in the vector step holds the **`osm` class token only while it
is fetching remote vector data**.  When the step transitions into the
auto-patch solve (local CPU, no remote traffic), it RELEASES the osm
token and continues under the **`compute`** class (uncapped, exactly as
`mesh` already is).  Concurrency during the solve is then bounded by
slots and by the existing memory admission gate — never by a network
politeness limit.

Invariants:
* The osm token is never held across the solve; a released token is
  immediately available to a queued tile that needs to fetch.
* Release/acquire is crash-safe: a child dying mid-solve must not leak
  a token (the pool already reaps children — reuse that path).
* No change to remote-fetch concurrency: at most `OSM_CLASS_LIMIT`
  tiles may be FETCHING at once, before and after.
* Mesh memory admission gate unchanged.

## 3. Secondary (same pass, small)

1. **Configurable class limits**: `O4_OSM_CLASS_LIMIT` /
   `O4_IMAGERY_CLASS_LIMIT` env overrides (defaults 2, i.e. unchanged),
   so a server-tolerant operator can tune without a code edit.
2. **Auto slot ceiling for compute-dominated queues**: `cores // 3`
   with a hard ceiling of 6 fits neither extreme (auto-patch uses 1
   core; a mesh step was measured at 1007 % = ~10 cores).  Raise the
   ceiling ONLY where it cannot increase remote pressure — the osm and
   imagery caps already bound fetch concurrency independently, so a
   higher slot count adds compute parallelism only.  Proposal: keep the
   politeness ceiling for FETCH classes; let slots scale as
   `min(cores // 2, memory // 6)` with a higher ceiling (e.g. 12).
   If the implementer's measurement contradicts this sizing, report the
   numbers and propose the alternative rather than guessing.

## 4. Acceptance (measure, don't assume)

Orchestrator-only change: no solver, law, `grade_graph`,
`pavement_scoring`, or auto-patch behaviour may change.

* **Unit**: class-token accounting tests — a tile in the solve phase
  does not hold an osm token; at most `OSM_CLASS_LIMIT` tiles fetch
  concurrently; a killed child releases its token.  Existing
  `parallel`/`session` suites stay green.
* **Behavioural (the point)**: a synthetic or real multi-tile run where
  ≥ 4 tiles reach the auto-patch phase shows ≥ 4 workers simultaneously
  CPU-active (sample `ps` during the run and report the observed
  concurrent-active count and load average, before vs after).
* **Output identity**: the emitted artefacts must be unchanged — build
  ONE tile with the change and confirm its patch/DSF output matches the
  pre-change build of the same tile (hash or vertex-wise). Scheduling
  must not alter results.
* Report build-time deltas honestly: wall times are contention-noisy
  (memory `build-time-noise-floor`); prefer the concurrent-active count
  and per-tile step durations over a single total.

## 5. Constraints

Main tree `/Users/noah/XPTerrainBuilder/Ortho4XP`, `venv/bin/python`,
run from that cwd.  `git log --oneline -1 && git status --short` before
AND after every measurement — other sessions commit omnibus sweeps to
this tree.  Never commit/stash/revert.  No KCLT builds (OOM).
One airport build per process; output to files, never pipes;
PID/artifact-verified waits with timeout arms.

**Concurrency with other work**: two investigation agents are running
against this same tree and own the airport builds (one owns HECA, one
owns SPJC/CYXY/SPLP).  Their files are the solver/law/probe set; yours
are `o4_engine/parallel.py`, `o4_engine/session.py`,
`O4_Parallel_Utils.py` and their tests — do not edit outside that set.
Prefer synthetic/unit verification over airport builds; if you need a
real multi-tile run, check `ps aux` first and keep it short.

STATUS/memory documentation stays with the parent session — report,
don't write there.
