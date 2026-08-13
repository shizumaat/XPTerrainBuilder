# Perf P2: instruments + candidate #1 (Fable, 2026-08-13)

Charter: perf-phase-charter.md. Baseline: baselines/1.0.245/MANIFEST.txt
(byte-identity gate on EVERYTHING here — an instrument or cache hit that
changes a patch body is a defect). Dev-model v2 applies (pre-delegated
trees below; report caps; STOP only on novel findings).

## Lane A — candidate #1: derived object caches never hit in lane builds

P1 measured: HECA `_compute_dsf_object_buildings` re-runs every lane
build (66.6 s; OTHH ~455 s, KCLT ~18 s) because (a) the mod-cache
overlay is per-RUN (`<out>/<tag>.engine_caches/`) so computed results
are discarded, and (b) the shared cache's fingerprint differs from the
lane's for the SAME 817 rings (fingerprint includes gate_constants +
cache version; shared sidecars rewritten by the owner's app 07:02).

1. Interventional A/B FIRST (same lane, two runs, one persistent cache
   dir): confirm run 2 hits when the overlay root persists. Then
   attribute the fingerprint drift: dump both fingerprints' components
   for one airport — WHICH component differs (gate constants? version?
   corpus path?).
   Decision tree: (a) components differ LEGITIMATELY (lane gates ≠ app
   gates) → the fix is the persistent lane root only; do not touch the
   fingerprint. (b) components differ SPURIOUSLY (e.g. an absolute path
   or timestamp in the fingerprint) → fix the fingerprint to the
   semantic content AND keep the persistent root. (c) anything else →
   STOP.
2. Implement: the harness's engine-cache redirection gains a
   LANE-PERSISTENT derived-cache root (per worktree, reused across
   runs; still lane-local — corpus law untouched; COW-seeded from
   shared on first use per the standing overlay law). `--refresh-data`
   scopes and the guard are unchanged.
3. Acceptance: run-2 cache HIT quoted per airport (HECA ≥60 s saved,
   OTHH ≥400 s); patch bodies byte-identical to the frozen baseline on
   hit AND miss arms; guard clean; twins for the persistent root
   (reuse, seeding, never-shared-write).

## Lane B — P2 instruments

1. SOLVE-STAGE REPRO CUTTER at the verified boundary
   (`finalize.compute_elevations_and_repair_geometry`, finalize.py:214;
   call site pipeline.py ~5786): a capture flag serializes the named
   argument set post-phase-4 (layout with canonical_points registry,
   centerlines, pavement records/unions, Airport block, OSM nodes/ways,
   apron_candidates, cropped tile_dem window + lat/lon, the to_m
   anchor); a replay entry rebuilds to_m and re-runs phases 5+6 alone.
   Acceptance: HECA capture → replay reproduces the frozen baseline
   body byte-identically, replay wall ≈ phases 5+6 (~420 s at HECA
   today), tool + INDEX row + twin (tiny synthetic airport capture/
   replay in tests).
2. CENSUS-BY-BODY-HASH CACHE: census.py caches its full output keyed
   by (body sha, sidecar sha, law knobs); identical re-census serves
   from cache with a CACHED marker. Twin: cache hit == fresh output
   byte-for-byte; knob change misses.
3. PER-ROUND WALL/TOKEN LOGGING: run_with_ledger records wall per
   entry already — add a session/round tag (env `O4_ROUND_TAG`) so
   phase reports can sum cost per round.
4. Port `build_airport.py --tile`'s empty-cifp refusal into
   profile_tile_build.py (P1 caveat — the tile profiler silently
   built an auto_patch-degraded tile).

Acceptance: twins once, ledgered; no timed claims (instruments only);
shared repo unchanged; both lanes commit on their branches, no merge;
reports capped ~600 words.
