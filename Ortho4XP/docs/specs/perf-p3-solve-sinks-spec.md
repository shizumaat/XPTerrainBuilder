# Perf P3: solve-sink optimization lanes (Fable, 2026-08-13)

Charter: perf-phase-charter.md. Premises are P1's PROFILED measurements
(not summaries). THE GATE ON EVERY ITERATION: byte-identity to
baselines/1.0.245/MANIFEST.txt. Semantics-identical transformations
ONLY (spatial indexes, prepared geometries, caching, vectorization,
dead-work elimination); any change that would alter a single emitted
byte is out of scope for this phase — that includes "harmless"
reorderings that reorder floating-point accumulation. No new law
constants. Dev-model v2; report caps.

## Iteration loop (both lanes)

Capture ONCE per airport with `build_airport.py HECA --solve-capture`
(and CYXY as the fast control); iterate with `tools/solve_cut.py`
replays — byte-identity checked EVERY replay (the cutter refuses drift
anyway); profile the replay (py-spy) to verify the sink actually
shrank. Wall claims at close only: recorded-phase comparison plus ONE
exclusive `check_build_time.py --run --runs 2` pair per changed
airport class (`unsetopt bg_nice`).

## Lane C — `one_solve.feasibility_project` / `_project_chromatic`

P1: 88.3 s of HECA's 192 s solve concentrated on ~6 lines
(one_solve.py 1968-2032). Understand the algorithm first (blast.py,
read the module header + the chromatic partition design); then attack:
per-line vectorization (the lines suggest per-node Python loops over
partition colors), memoization of invariant lookups, numpy
batch-projection where the math is already array-shaped. STOP if the
only wins require changing iteration order in a way that moves floats.
Target: ≥40 s off HECA's solve replay, byte-identical.

## Lane D — `grade_graph.shape_constraints(_cached)` + `build_unified_graph`

P1: 85.6 + 69.2 s at HECA; leaves `classify_pair` 57.5,
`_crosses`/`_crosses_one` 63.5 combined, `_vis` 23.5 — pairwise
shapely predicates with no visible spatial index. Attack: STRtree
prefilter before pairwise classification, `shapely.prepared` for the
repeated `intersects`/`contains` sites, cache `classify_pair` by the
pair's canonical ids where inputs are immutable across the pass. The
`_cached` variant exists and still costs 85.6 s — measure WHY (cache
misses? cache key cost?) before adding another layer. Also in this
lane's file scope from candidate #4: `_drop_overlap_against_fixed_
shapes` (42.9 s, two call sites — check idempotence: if call 2 is
provably a no-op on call 1's output, gate it out; that is candidate #5's
cheap half). Target: ≥60 s off HECA phases 5+6, byte-identical.

## Acceptance (each lane)

- HECA + CYXY replays byte-identical at every landed commit (quote the
  final hashes vs MANIFEST).
- Replay-profile before/after showing the named sink shrinking (quote
  the top-10 both sides).
- ONE exclusive wall pair at close per airport (HECA, CYXY): quote
  --runs 2 numbers; expected HECA total −40 s (C) / −60 s (D) floors.
- Twins for any new caching layer (cache hit == fresh output on a
  fixture); 0 new constants; shared repo UNCHANGED; commit on
  lane/perfsolveC / lane/perfsolveD; no merge; reports ≤600 words.
