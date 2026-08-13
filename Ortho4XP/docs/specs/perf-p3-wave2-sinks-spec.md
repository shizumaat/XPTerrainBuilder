# Perf P3 wave 2: remaining sinks (Fable, 2026-08-13)

Charter: perf-phase-charter.md. Premises are P1's PROFILED measurements
(HECA airport profile 568.3 s; KCLT tile profile 107.4 s), author-
re-verified today: every named function exists on merged main; P1 LINE
numbers are P1-tree — re-locate by function name. THE GATE ON EVERY
ITERATION: byte-identity to baselines/1.0.245/MANIFEST.txt.
Semantics-identical transformations ONLY (spatial/bbox prefilters,
prepared geometries, caching, vectorization, dead-work elimination); a
change that would alter one emitted byte — including float-accumulation
reordering — is out of scope. No new law constants. Dev-model v2.

SAMPLING CAVEAT (P1 gotcha, binding): the sampler over-attributes
inside numpy/GIL-heavy loops. Function-level ranking is trustworthy;
every per-LINE claim and every before/after number quotes
`profile_airport_build.py --count MODULE:ATTR` wrapper timers or
`perf_counter`, never sampled seconds.

## Iteration loop

Solve-side lanes (E, H; F and G where the target proves replay-
reachable): capture ONCE per airport (`build_airport.py HECA
--solve-capture`; CYXY as fast control), iterate `tools/solve_cut.py
--replay` — byte-identity checked every replay; verify the sink shrank
with `--count`. Non-replay targets (phase 4, before-step-1, tile):
`--no-ledger --patch-only` build PAIRS reading the recorded phase
times — never a single-run quote.

WALL ADJUDICATION MOVES TO P4 (this wave's change from wave 1): lanes
quote replay-to-replay and recorded-phase deltas only; the exclusive
`check_build_time.py --runs N` block runs ONCE on the merged tree in
P4, which also re-records the committed baselines (owner approval
2026-08-13, the 2026-08-04 drift artifact). No per-lane exclusive
pairs — five lanes cannot each have the machine.

## Lane E — emit/finalize (lane/perfemit)

P1 HECA phase 6 = 99.4 s sampled; OTHH's is larger (the 98–216 s
docket range). Sites (P1 lines, re-locate): pipeline.py:6123 24.6 s,
:6979 22.6 s, :6256 22.2 s, :6482 6.6 s, :6019 4.3 s, :5850 4.1 s,
:7198 2.3 s; finalize.compute_elevations_and_repair_geometry 16.4 s.
`elevation._drop_overlap_against_fixed_shapes` is ALREADY PAID (lane D,
35.3→3.3 s) — do not re-touch. Phase [6] is inside the replay. An OTHH
capture is lawful if HECA's phase-6 shape proves unrepresentative.
Target: ≥30 s off HECA replay phase [6].

## Lane F — presolve/groundside + global slice (lane/perfpre)

P1 HECA: groundside.py `_svc_contiguous_width` 27.5, `free_road_
subsegments` 24.9, `groundside_route_band` 24.6; adjacent_ground.py
`construct_adjacent_ground_presolve` 22.4, `_build_construct_reach_
band` 17.3; apron_terrace.py `construct_apron_terrace_presolve` 18.9,
`presolve_anchor_envelope` 16.9; pavement/global_slice.py
`build_global_slice_faces` 33.0 incl. `_hole_spur` 20.8 (phase 4 —
NOT in the replay; iterate via build pairs + `--count`). These callers
carry most of the remaining shapely leaf ceiling (intersects/
intersection/buffer/distance/contains ≈226 s machine-wide). Attack:
STRtree/bbox prefilters, prepared predicates, hoisting invariant
unions/buffers out of per-feature loops. Target: ≥40 s off HECA
combined (replay for phase-5 sites + recorded phase 4).

## Lane G — object partitioning (lane/perfobj)

P1 HECA ≈145 s: object_anchor.py `partition_structures` 52.5;
obj8_partition.py `_surfaces_in_contact` 28.9, `_vertex_to_triangle_
proof` 22.7, `contact_graph` 22.7, `split_oversized_components_with_
edges` 21.0, `_point_triangle_minimum_distances` 19.2. Step 1: locate
these in the phase structure with `--count` on a replay — if not
replay-reachable, build pairs. Attack: numpy batch triangle-distance
math, spatial prefilters on the contact graph, memoizing per-object
invariants. The before-step-1 DSF read is already cache-paid
(perfcache/perfsidecar) — out of scope. Target: ≥40 s off HECA.

## Lane H — solve remaining halves (lane/perfsolveH)

P1 HECA: solve.py `final_grade_projection` 44.9, `_apply_runway_flex_
hook` 26.8, `_value_envelope` 23.5 (leaf 14.7+6.1); one_solve.py
`one_profile_solve` self sites (P1 4677/4679/4687/4688, ~25 s self);
solver_primitives.py `_seed_elevations` leaf 9.7. Lane C's
`_project_chromatic` work is merged — build on it, do not rework those
lines. All replay-reachable. Target: ≥30 s off HECA replay.

## Lane T — tile vector step (lane/perftile)

P1 KCLT tile +35-081: vector step 68.7 s of 107.4; O4_Vector_Utils
`insert_way`/`insert_edge` 41.8 incl., rtree `insert` 26.7 LEAF +
`delete` 7.8 + `_intersection_obj` 5.1; `encode_MultiPolygon` 26.8;
`snap_to_grid` 1.3. Attack: rtree bulk/stream loading over per-edge
inserts, cutting index churn on edge splits, batching. Step 1
(author-verified premise boundary): name the vector step's exact
product set (what `build_poly_file` writes) and hash it — THAT
byte-identity is this lane's gate, plus an unchanged downstream mesh
on one +35-081 pair. Distribution via `profile_tile_build.py`
(CIFP-armed per its refusal); walls from recorded step pairs.
Target: ≥15 s off the vector step.

## Acceptance (each lane)

- Byte-identity at every landed commit (E/F/G/H: HECA + CYXY replay
  hashes vs MANIFEST; T: the step-product set + mesh pair).
- `--count` before/after table for each named sink; sampled numbers
  never quoted as claims.
- Twins for any new cache/prefilter layer (disabled-vs-enabled equal
  outputs on a fixture); 0 new constants; shared repo UNCHANGED;
  tests once through the run ledger (PRE-SHIP); DEFERRED lines for
  every skipped check; commit on the lane branch; NO merge (lead
  merges); report ≤600 words.

## Pre-delegated decisions

- Sink already paid by a merged wave-1 lane → skip it, one report
  line, move on.
- The only win at a site requires float-order change → STOP on that
  site, record the measured potential, continue the lane's other
  sites.
- Target not reachable in the replay → build pairs + `--count`;
  quote recorded-phase deltas only.
- Materiality floor 2 s per named sink; attempt cap 2 per site;
  progress heartbeats per convergence-guard law.
