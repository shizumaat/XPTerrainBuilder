# prof300 — warm builds under 300 s: ranked plan (HECA, OTHH, KCLT)

Scout `prof300`, worktree `/Users/noah/XPTerrainBuilder/.claude/worktrees/prof300` (branch `claude/prof300` = origin/main `8e42aa0a`, clean, no edits, nothing pushed).

**Verdict.** All three airports reach < 300 s warm on paper without changing output. KCLT gets there on by-construction items alone (~246 s). OTHH needs either R6 or R10 on top of those (~262 s with R6). HECA gets there only with R6, at ~285 s on estimates good to about ±20 s; it is the one airport that may need an owner ruling on the solve.

**How to read the numbers.**
- *Measured, plain*: stage and per-generator walls from the unprofiled warm sweep builds `sw1041_*_warm*` (tree `4821b25c`; main differs by the version bump and 8 lines of `pool.py`).
- *Measured, profiled*: one cProfile run per airport, heartbeat thread not started, pool pinned to 1 via the engine's own `pool.configure(1)` (log line `[pool] workers 1 (bound: pinned)`). Machine LOADED (load average 11–29 throughout).
- *Estimated*: plain seconds saved = plain stage wall × profile share. Every "saves" figure below is an estimate of this kind unless marked otherwise.
- The partition stage was COLD in my profiled runs (see "Not verified"); no partition number from them is used.
- Patch identity of the three profiled builds matches the bar: HECA `09847984ac94`, OTHH `88794a1d264b`, KCLT `795da9629004`.

## 1. Ranked plan

Paths are under `Ortho4XP/src/auto_patch_v2/` unless they start with `src/`. Seconds are HECA / OTHH / KCLT. "Pass 2" is the ribbon-free stage-1 prefix that runs inside the `solve` wall.

| # | Item | Site | Saves (s) | Exactness | Lane-h |
|---|---|---|---|---|---|
| R1 | Hoist `pad_fronts_airside(planar, law)` out of the list comprehension. It re-derives the whole-map `_fronting` once per pad polygon. | `constraints/pad_frontage_gs.py:361-362` → `constraints/pads.py:382`, `:293` | **40 / 56 / 13** (pass 1: 20 / 28 / 6.5; pass 2 assumed equal) | identical by construction | 1 |
| R2 | `_Index._tied` scans every axis segment per query. Restrict it to the grid cells within `d0 + tie_m` of the point, same scalar test, ascending segment index. | `constraints/stretches.py:334` (callers `taxi.py:383`, `verify/within.py:621`) | **40 / 23 / 13.5** (verify share 11 / 6.5 / 4.5) | identical by construction (candidate superset, same floats, same order) | 3 |
| R3 | Verify `within_shape`: one `covered_by` over all O(n²) chords of each shape. Chunk each shape's pair list onto the work pool, ordered merge. Optionally add the existing sound pre-screen `chord_midpoints_hit` first. | `verify/within.py:290`, `constraints/geometry.py:71`, `:86` | **32 / 6 / 5** | identical by construction (per-chord predicate, ordered merge) | 5 |
| R4 | `terrain_edge._outward` and `_segments` do millions of scalar `.coords` reads. Replace with one `shapely.get_coordinates`. | `planar/terrain_edge.py:116`, `:128-139` | **12 / 16 / 9** over both passes (wide error) | identical by construction (coordinate reads, no arithmetic) | 2 |
| R5 | `route_pairs` runs three times per build (pass 1, pass 2, emit). The emit call recomputes pass 1's table: `_PAIR_CACHE` is one slot keyed on `id(planar)`, cleared by pass 2 and missed because `pm` was replaced. Key it by content. | `constraints/taxi.py:149-185`, `constraints/routes.py:859`, `pipeline/publication.py:767`, `pipeline/build.py:1101` | **10 / 12 / 8** (emit) | identical by construction IF `with_pin_yield` leaves the route graph and rings untouched (not checked; a content key misses otherwise) | 4 |
| R6 | Run the ribbon-free prefix beside pass 1 as a `WorkPool.begin` task, started after the once-per-build pack reads, results merged before `solve_design`. | `pipeline/build.py:1061-1083`, `pipeline/stage_one_map.py:185`, `airport/pool.py:439` | **45 / 48 / 27** net (pass 2 left after R1/R2/R4 ≈ 55 / 58 / 37, less ~10 for result pickling and worker start) | NEEDS A BIT-IDENTITY PROOF: another process, the `capture_state` registries, shipping the pack reads | 16–24 |
| R7 | Solve assembly Python: memoise `ruling_head` per ruling string; tighten `_level_free_columns` and `_one_matrix`. | `solve/design_roles.py:185`, `solve/rows.py:329`, `:388`, `solve/design_assemble.py:94` | **8 / 4 / 5** | memo identical by construction; the rest needs a row-order twin | 4 |
| R8 | OTHH classify: `skirted_placements` makes 35,886 serial `reading` calls. Pool per placement, or carry the result in the partition cache. | `airport/skirt.py:275`, `:164`; `classify/evidence.py:904` | **0 / 20 / 0** | pool: identical with ordered merge; cache: needs a key-completeness twin | 6 |
| R9 | Pool `route_pairs` Dijkstra chunks, and `apron_within_shape` per shape. | `constraints/routes.py:883-897`, `constraints/apron.py:161` | **10 / 10 / 8** (pass-1 wall only) | identical with ordered merge (not checked for hidden per-generator state such as `STATS`) | 8 |
| R10 | Lane-local cache of the composed tile DEM. It is rebuilt for every airport build. | `airport/dem_production.py:773` → `src/O4_Vector_Map.py:2076` | **0 / 20 / 27** warm, 0 cold | identical if the key is complete (twin; same class as the partition cache) | 8 |
| S1 | OWNER: let the QP reuse its factorisation across rounds (low-rank update, or PCG preconditioned by the last LU) instead of refactorising every round. | `solve/design_qp.py:168`, `solve/linear.py:54` | **≈ 65 / 2 / 30** | CHANGES OUTPUT at rounding level; at HECA that is a surface change (#149: path-sensitive up to 0.9 m) | 12–16 + sim read |

## 2. Arithmetic (warm, plain, estimated)

| | HECA | OTHH | KCLT |
|---|---|---|---|
| today (`sw1041` warm, measured) | 474.1 | 446.6 | 300.0 |
| R1 | −40 | −56 | −13 |
| R2 | −40 | −23 | −13.5 |
| R3 | −32 | −6 | −5 |
| R4 | −12 | −16 | −9 |
| R5 | −10 | −12 | −8 |
| R7 | −8 | −4 | −5 |
| R8 | 0 | −20 | 0 |
| **after the by-construction items** | **≈ 332** | **≈ 310** | **≈ 246** |
| R6 | −45 | −48 | −27 |
| **after R6** | **≈ 287** | **≈ 262** | **≈ 219** |
| R9 | ≈ 277 | ≈ 252 | ≈ 211 |
| R10 | 277 | ≈ 232 | ≈ 184 |

- **Cold OTHH** (557.7 today): R1–R8 plus R6 remove about 185 s, giving **≈ 373 s cold**. R10 is warm-only.
- **HECA is the one that may not get there exactly.** Without R6 it stops near 332 s. With R6 it has a ~15 s margin on estimates. What remains is the design solve at 143 s (measured), about 96 s of it sparse refactorisations with no exact lever.
- **Recommended order:** R1, R2, R4, R5 first (about 10 lane-hours, all identical by construction, roughly −100 / −107 / −44). Then R3. Then R6 behind the seven-airport sha bar.

**The owner question, if HECA falls short:** may the staged QP's linear algebra change at rounding level (S1), accepting a changed HECA surface and a sim re-read? Recommendation: yes, but only after the exact items land and HECA is re-measured.

## 3. Stage attribution (profiled seconds, pool 1, loaded; plain stage wall in brackets)

**HECA** (profiled total 1,404 s, of which 202 s is the cold partition)
- constraints [68.9 plain; by generator: frontage 20.4, junction_mesh 18.0, taxi_box 9.8, apron_within_shape 9.7]. `generate` ran 2 calls, 549.2 s:
  - `groundside_frontage_level` 181.2 → `pad_fronts_airside` 550 calls → `_fronting` 556 calls 179.5 (2.71 M `Point()` + `distance`, `_pavement_geoms` 556 calls 55.7).
  - `junction_mesh` 105.2: `box_pair_rows` 52.7, `taxi_pair_routes` → `route_pairs` 28.7, `triangle_boxes` 21.9.
  - `taxi_box` 77.7.
  - `apron_within_shape` 64.7 (`project_to_chain` 4.43 M calls 37.6, `chords_covered` 16.0).
  - `zone_bands` 45.6 (`_nearest_edge` 53,400 calls 48.8).
  - `stretches._tied`: 107,362 calls, 245.4 M each of `hypot`/`min`/`max`/`abs`, 144.6 s cumulative. That is 81 % of `box_bound` (178.2 s; 130.1 from the generators, 48.1 from verify).
- verify [69.4 plain: within_shape 48.5, taxi_box 14.3]: `within_shape` 65.5 → `_chords_outside_face` 285 calls 55.0 → `covered_by` (69.3 s self over 1,908 calls build-wide); `taxi_box` 48.8 → `box_bound`.
- planar [42.9 plain], 2 calls 190.0: `build_arrangement` 140.9; `zone_regions` → `_crest_geometry` 690 calls 67.1 → `_outward` 576 calls 66.6, of which `.coords` 4.38 M reads 37.1 and `_segments` 20.9.
- classify [22.0] 25.6: `mint_osm_ribbons` 15.7 (411 `unary_union`).
- emit [17.5] `publication` 21.7: `taxi_route_pairs` 12.8.
- solve: section 4.

**OTHH** (profiled total 1,768 s, of which 830 s is the cold partition at pool 1)
- constraints [72.8; frontage 28.4, junction_mesh 15.7, taxi_box 7.2, apron 7.1], 2 calls 302.6:
  - frontage 120.6 (`_fronting` 460 calls, 454 from `pad_fronts_airside`).
  - taxi_box 49.6; junction_mesh 46.1.
  - `_tied` 66,097 calls 70.0, 76 % of `box_bound` 91.7 (28.9 from verify).
  - `route_pairs` 3 calls 43.8 s self.
- planar [116.4; in production the pool answered 782 reader tasks in 33.3 s with 8 workers, bound "cap"]. Pinned: readers 203 s CPU (door wells 57.5, sunken roads 37.8, wall corridors 100.7). Serial remainder over both passes: `build_arrangement` 96.5 (`_crest_geometry` 852 calls 47.6, `plateau_cut` 15.5, `platform_split` 11.5), `build_basins` 37.9.
- classify [48.8] 53.0: `skirted_placements` 27.7 (35,886 `reading` calls).
- load [24.4] 64.6: tile DEM compose 57.4.
- verify [26.3] 58.4: taxi_box 29.2, within_shape 16.8.
- solve [123.1 = pass 2 103.5 + design 19.6]: `stage_one_problem` 208.0 (constraints 144.0, planar 53.4); `solve_design` 49.4 (assemble 3 calls 28.4; 147 factorisations 2.8 s; HiGHS 1.7 s).

**KCLT** (profiled total 641 s, of which 82 s is the cold partition)
- constraints [34.0], 2 calls 172.0: frontage 34.5 (`_fronting` 406 calls), apron_within_shape 33.4, taxi_box 29.9, junction_mesh 24.8 (`taxi_pair_routes` 20.3), zone_bands 12.6. `_tied` 52,880 calls 43.1 (87 % of `box_bound`). `route_pairs` 3 calls 27.6.
- solve [142.7 = pass 2 54.1 + design 88.6]: `solve_design` 133.8. Five `_solve_stage` calls: two stage-1 passes 59.2, stage 2 25.5, and two pin-yield re-solves of stage 2 45.9. 23 QP solves 73.3; 3,384 SuperLU factorisations 43.0 s; `assemble` 5 calls 34.8; HiGHS 4.9.
- load [33.9] 56.1: tile DEM compose 47.4 (`smooth_raster_over_airports` 26.1, DEM read 10.5).
- planar [29.7], 2 calls: `_crest_geometry` 1,400 calls 36.9.
- verify [18.5] 36.7: taxi_box 16.0, within_shape 13.3.

## 4. The HECA solve

The data here is a plain, single-process, timestamped replay: `v2_solve_replay --replay rebake362/HECA.pkl --from constraints --design-verbose --workers 1` (capture base `54bc53a0`, loaded machine; solve 157.8 s there against 143.0 s in the sweep).

**The "310 rounds" are not LP rounds and the problem is not rebuilt 310 times.**
- They are the proximal active-set rounds of the engine's own QP (`solve/design_qp.py:128`), summed over pass 1b's three QP solves (206 + 52 + 52).
- The rows-to-matrix assembly happens once per `_solve_stage`. HECA runs four of those: pass 1a, pass 1b, stage 2, and a stage-2 pin-yield re-solve.
- What each round does pay: it re-stacks `A0` + the active rows + `√λ·I`, recomputes `AᵀA`, and refactorises from scratch with SuperLU (`solve/linear.py:54`).

**Per QP solve** (rounds / wall / median seconds per round / active rows first → last):

| Stage | QP solves | Total |
|---|---|---|
| pass 1a | 128 / 17.3 s / 0.145 / 175,137 → 94,342; then 35 / 4.8 s; 35 / 4.4 s | 26.5 s |
| pass 1b | 206 / 30.4 s / 0.160 / 178,830 → 96,762; then 52 / 8.0 s; 52 / 7.8 s | 46.2 s |
| stage 2 | 127 / 5.7 s / 0.048 / 167,903 → 138,225; then 52, 26, 10, 14, 8 rounds | 11.8 s |
| stage-2 re-solve | 117, 40, 26, 10, 14, 8 rounds | 11.1 s |

- **Rows changing per round:** the active set moves by a median of 10–12 rows per round out of about 96,000 active. In 73 of pass 1b's 206 first-solve rounds the gain is below 1e-6·F. After the first dozen rounds every round is a full refactorisation for a ±10-row change.
- **Split of the 157.8 s:**
  - QP rounds 95.6 s (61 %).
  - §5a feasibility LP in HiGHS 8.09 + 6.21 + 0.42 + 0.43 = 15.2 s, once per stage, never per round.
  - Runway-projection QP in HiGHS 15.5 s, once.
  - Assembly and reads about 31 s, by subtraction.
- **Cross-check from the profile:** `gstrf` 1,738 calls 71.1 s; HiGHS 11 calls 40.0 s; `assemble` 4 calls 50.2 s (pure Python, inflated).

**Why it does not settle.** The inner QPs all end `optimal`. The outer multiplier polish is capped at two rounds (`law/emit.toml:911 polish_rounds_max = 2`, a measured ruling). Pass 1b's worst hard row goes 0.149 → 0.101 m in those two rounds; pass 1a settles (0.027 → 0.019 < 0.02). The feasibility LP says the law is satisfiable there, so the residual is the cap's, not the law's and not the inner rounds'.

**Warm start and batching.**
- The polish QPs are already warm-started from the previous iterate.
- Warm-starting pass 1b from pass 1a was tried and reverted in #149 (lane flatpad150): 1,032 vertices moved more than 0.01 m, worst 0.895 m.
- Rounds are sequential. The only thing to batch is the factorisation (S1). It solves the same subproblem to `solver_tol` but is not bit-identical.

**What #149 and #241 established.**
- #149: stage 1 is several full solves; only 7.3 % of the 93,369 promoted rows bind; dropping non-binding rows moved 1,290 vertices by up to 0.86 m. The stage-1 surface is path-sensitive while the hard set is unsettled, so no row reduction is solution-identical. roadrows143 later removed pass 1a's pin-yield re-solve.
- #241 (open): a 105-column change moves the stage-1 optimum up to 1,704 m away with no hard row binding. Hypothesis is per-vertex `apron_trend` pricing; untested.
- Together: stage 1 is globally coupled, so any non-bit-identical solver change at HECA changes the surface and is the owner's call.

## 5. Constraints (generated twice) and verify

**Scalar loops that become exact:**
- R1: the same function called once instead of N times. Proof is by reading; a twin asserts the row list is equal.
- R2: the per-segment scalar expression is untouched and only the candidate set shrinks to a provable superset. Proof: a twin asserting the `_tied` list is equal element-for-element against the full scan for every query in the three captures.
- R4: coordinate extraction only. Proof: `np.array_equal` on `ab` in a twin.

**Scalar loops that need a bit-identity proof if vectorised:**
- `pads._fronting`'s `Point()` + `distance` (2.7 M calls at HECA) → `shapely.distance` on arrays. Same GEOS routine per pair, so it should be bit-equal, but prove it with array equality on captures. This is moot after R1.
- `geometry.project_to_chain` (7.4 M calls at HECA) and `zones._nearest_edge` (113,794 calls): numpy would change the `hypot`/division order and the first-minimum tie-break. They need element-wise equality on captures, or leave them scalar and pool per shape instead.

**Poolable with ordered merge** (`WorkPool.try_map`): `junction_mesh` per face, `apron_within_shape` per shape, `route_pairs` per 128-source chunk, verify `_chords_outside_face` per shape or chunk, `_crest_geometry` per region part.

**Reusing pass 1's rows for the ribbon-free map.** Possible in principle. The two maps join by vertex coordinate; at HECA 32,737 of 34,898 vertices are common. The reuse key would be per generator and per face: face role, the face's ring and hole coordinates as bytes, plus everything the generator reads off the neighbourhood (stretch axes, pad set, caps). That last part is the catch: each generator needs its own completeness argument. I recommend R6 instead. It removes the second pass's wall with one proof rather than a dozen keys.

## 6. Not verified, and housekeeping

- **No unprofiled warm run on `8e42aa0a`.** Plain seconds are the `sw1041` sweep's.
- **Partition was cold in my profiled runs.** I cloned the sweep lane's `engine_caches` into my worktree to skip the warm-up build; the partition cache MISSED on all three and each run wrote a fresh one. Only the partition stage is affected.
- **Pass-1 vs pass-2 split of the second pass is estimated.** The build does not clock it, and the profile's pass-2 constraints at HECA read 394.9 s against 159.0 s for pass 1 under shifting load. I treated that ratio as unusable.
- Every "saves" figure is single-run and profile-derived. Nothing was implemented; no bit-identity was demonstrated.
- R5's premise that `with_pin_yield` leaves the route graph unchanged was not checked. R9's per-shape independence was not checked for hidden state.
- R6 and S1 need builds to prove: a closing `tools/harness/build_airport.py HECA` plus the master's seven-airport sha sweep.
- R3's pre-screen gain needs one `v2_solve_replay --replay … --verify` pair.
- Whether the QP could be split per connected component (the stage-1 report shows 61 components) was not examined.
- `check_build_time.py --runs N` was not run.
- **Housekeeping:** one aborted HECA launch left stub artefacts `/tmp/harness/prof300_HECA_p1.{progress,env.json}`; the real run is tag `prof300_HECA_p1b`. Nothing was registered in `frames.py`, and nothing was written to the shared data repo beyond what the harness itself does. The worktree is still up; `tools/harness/lane_worktree.sh down prof300` removes it.

## 7. Files

Scratch folder: `/private/tmp/claude-501/-Users-noah-XPTerrainBuilder/0ec4326d-10bf-4753-bd1b-ca41fda6bcd1/scratchpad/prof300/`
- `HECA_warm_p1.prof`, `OTHH_warm_p1.prof`, `KCLT_warm_p1.prof` — the profiles
- `HECA_replay.log` — per-round QP lines, timestamped
- `prof_run300.py` — the runner (heartbeat off, pool pin)
- `q.py`, `ts.py` — pstats query and timestamper

Harness artefacts: `/tmp/harness/prof300_HECA_p1b.*`, `/tmp/harness/prof300_OTHH_p1.*`, `/tmp/harness/prof300_KCLT_p1.*`

Reference: `/Users/noah/XPTerrainBuilder/docs/perf/prof362-report.md`; pstats tree reader `/Users/noah/XPTerrainBuilderData/.harness/frames/prof362/ps.py`.
