# Beta hardening plan — Mon 09-01 → Thu sim read → Fri beta
# (owner mandate + rulings 2026-09-01a; 31f strict gates hold all week:
# below-bar = STOP-AND-WAIT, attribution before fix, thresholds
# measured never fitted, artifacts verified before measuring.)

## Day 1 (Mon) — safety, red-zero, instruments, decisions applied

- H1 SILENT TILE DEATH (P0): a tile build that dies between the
  phase-time write and the patch write must FAIL LOUDLY — engine
  surfaces the error, tile build exits nonzero, stale patch never
  ships silently (the flown-Aug-29-HECA class). Root cause the worker
  death path in driver/tile entries; regression twin.
- H2 RED-ZERO: every standing test red attributed and fixed or
  formally retired with its law: round16 ×4 (§T5 O4_RAMP_WALL_FOOT),
  gap_fill_spine ×3 (gate-state), classification ×1 (lateral
  contiguity emitter), obj8 partition signature ×1, KCLT bake pool ×1
  (span-skip bar 5 vs 6). Beta gate: full suite green.
- H3 INSTRUMENTS + CACHE SURFACING: mouth inventory stops mischarging
  the lawful arm-end opening; the R10-2 clip joins the named-removal
  log; cold airport_small_roads caches REFUSE with a --refresh-data
  osm_layers message instead of writing the shared repo.
- A3 (on lane/ltbatch3): ruling A — pinch wall stands down; expect
  10/10 mouths canonical under the corrected bar; batch goes
  MERGE-READY.
- B1 (on lane/bldround): ruling B — FILL_R ~15 m, measured at
  building79's cluster first (11.1 m gap open, facade gaps closed);
  pack-wide arm at LEMD (the fallout-prone pack); batch MERGE-READY.

## Day 2 (Tue) — merges, C, Batch-4 cleanup, residual attributions

- MERGE (spawner): ltbatch3, bldround, ltbatch4a as each is green.
- C1: the merge-and-weld rule for adjacent strips on freed ground
  (ruling C) — lands with/after the 4a merge; closes the 2
  strip_seam_tear rows and re-checks the +44 airside_no_step.
- H4 BATCH-4 CLEANUP: dormant road-ownership passes measured
  zero-fire then DELETED; retired env flags removed; the inert
  node-book exclusion and dead frontage-cutback code deleted; the
  45 residual far rings attributed (fix if the producer is one of
  the deleted class).
- H5 BATCH-3 LEFTOVERS: deck pin + OSM crossing classifier exercised
  on a real LEMD tile build (they have only twins today).

## Day 3 (Wed) — full verification + release prep

- FULL SUITE (paying the suspended debt) green on final main.
- Five-airport sweep + censuses on final main; site reads at every
  owner site in the sim guide.
- Exclusive perf profile; record the LEMD committed baseline on the
  final tree; CYXY/SPLP/HEAZ measured; budget status quoted (beta
  may ship over the 60 s budget — the final-design profiling round
  remains post-beta, per the standing suspension).
- Worktree cleanup (~90); ledger hygiene.
- Beta candidate app build (1.0.274) + updated sim guide + release
  checklist per the alpha-1 recipe (tag → auto-publish,
  make_notices); RELEASE WAITS for the Thursday sim read.

## Standing rules for every lane this week

Attribution before fix; one closing arm per round; controls via
ledger; per-change tests once but the FULL SUITE runs Day 3; nothing
merges below bar; every deviation stops for Fable review; heartbeats;
verify artifacts before measuring; no branch switches in trees with
running builds; sweeps in worktrees.
