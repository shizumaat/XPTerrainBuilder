# Performance phase report (P1–P4, closed 2026-08-13)

Charter: docs/specs/perf-phase-charter.md. Baseline frozen at
baselines/1.0.245/MANIFEST.txt; EVERY landed optimization reproduced
all five airport bodies byte-for-byte (consolidated-5: HECA
f562cbfeb8f9, KCLT 7bf9038e93f7, OTHH 75594bc8773a, CYXY 61efa43c3aeb,
KSTJ 65844a63b397; zero contamination). The phase changed time and
nothing else.

## Committed baselines, re-recorded (owner approval; P4 exclusive block)

2-run exclusive medians at merge d787464, nice 0, machine quiet. The
old committed numbers were 2026-08-04 machine-drift artifacts that
read 13–32% fast, so raw old→new deltas UNDERSTATE the real wins.

| airport | old (stale-fast) | new | note |
|---|---|---|---|
| CYXY | 35.56 | 34.88 | |
| OTHH | 339.52 | 262.91 | −23% vs a fast baseline; first block's 519.67 was the one-time pack re-key (227 s assembling), re-recorded clean |
| SPJC | 174.99 | 210.33 | drift-dominated; untouched by wave lanes |
| HECA | 351.93 | 347.19 | real win under drift (recorded 562–581 s at phase open) |
| SPLP | 12.25 | 8.43 | |
| HEAZ | 54.73 | 41.00 | |
| KCLT | 307.26 | 334.20 | +9% < drift ⇒ net win; solve phase −10 s vs first block |

Budget adjudication: OTHH/SPJC/HECA/KCLT remain over the 60 s airport
budget; approval ceilings refreshed to the measured medians
(build_time_approvals.json, dated 2026-08-13). The staged-solve round
is the chartered path down.

## What the phase paid (all byte-identical; replay/--count attributed)

Wave 1 (merged before this session): lane-persistent derived caches
(OTHH −423.5 s, HECA −63.2 s per lane rebuild); PRISTINE-key
fingerprints (production per-bake recompute eliminated: ~455 s OTHH /
~66 s HECA); solve sinks −58 s (graph constraints) −25 s (chromatic
projection); solve-stage repro cutter.

Wave 2 (this session): lane H −52 s (flex-hook dominated-push
suppression, sweep plan, numpy-bounded seed backfill); lane F −34.7 s
(global-slice buffer memo, route-band graph skip); lane G ~32 CPU-s
(partition prefilters; ≥40 s floor honestly refuted — whole sink
52.2 s); lane E conformance family (~3 s; 71 s of its charter was
other lanes' functions — spec boundary error, acknowledged); lane T
tile vector 127.4→103.4 s (edge-index bulk queries; P1's tile
premises corrected: non-production cfg, sampler-inflated rtree);
perfgraph −5.9 s (run-scoped shape_constraints memo; cross-build
redundancy measured 10.6%, not the 6× the sink table implied);
perfcenter −4.1 s (centerline_specs memo, 11-item walked read-set).

## The duplicate-work census (owner question: "are we doing anything twice?")

Instrument: profile_airport_build --count-inputs (input-fingerprint
counters; id-reuse and import-alias traps closed and twinned;
observation-only proved by byte-identity). Verdict over 51 armed
callables: ONE material duplicate row existed (centerline_specs,
~4 s — paid by perfcenter); the six graph builds and both
final_grade_projection calls are REAL work on genuinely different
inputs (zero duplicate fingerprints), because the pipeline MUTATES
layout between builds; 7 memos have scope shorter than their inputs'
invariance (inventory in the census, lane/dupcensus c57b84d).

The architectural answer is chartered, not asserted: the staged-solve
round's GEOMETRY FREEZE (owner direction) completes all solve-consumed
geometry before solving — one node list, one graph, additive-only
emission, value-preserving refinement — which collapses the six
builds and the double projection by construction.

## Findings routed out of the phase

- TILE BUILDS ARE NOT IDEMPOTENT: o4_object_foot_pads.json is a
  post_mesh product consumed as next-build input (object_pad
  689→723→736 across three tile builds). Owner RULED the redesign:
  pads decided in the ONE solve, convergence retired (RULINGS
  2026-08-13; staged-solve S5).
- Bake-invariance of the PRISTINE-key caches PROVED end-to-end (warm
  2.15/3.16 s across 171/77 baked .obj rewrites).
- Route-metric baked budgets differ in the last ULP across graph
  builds (perfgraph counterexample) — dissolves under the one-graph
  freeze.
- profile_tile_build did not arm the shared-repo guard (hole closed,
  lane T); one shared-corpus sidecar write remains ATTRIBUTION OPEN
  (likely the production app's lawful re-key; DEFERRED ledger).
- 2026-07-18 owner ruling keeps the mid projection (~64 s at OTHH);
  expected to collapse by construction in the staged-solve round.

## Instruments now standing

solve_cut capture/replay (solve iteration in ~7 min not ~10);
--count / --count-inputs wrapper timers (sampler GIL caveat
documented); census-by-body-hash cache; per-round wall/token ledger
tags; base-arm artifact ledger; guard-armed profilers.
