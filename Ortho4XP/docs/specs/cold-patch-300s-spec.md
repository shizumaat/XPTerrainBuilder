# Cold patch creation under 300 s at HECA and OTHH: measurement and architecture (2026-10-20)

Status: PROPOSAL (spec lane m12). No engine code is changed by this spec.

Owner target, ruling Q35 (Noah, 2026-10-20): "Target is HECA and OTHH auto-patch initial creation in < 300s, total tile build may be longer." Read cold: stage cache off (`O4_V2_STAGE_CACHE=0`), one patch-only build per airport through `tools/harness/build_airport.py --no-ledger`.

Laws this spec works under (read each with `tools/docq.py ruling <key>`):
- `src/auto_patch/CLAUDE.md`, HARD LAW — build time: the budgets are COLD; a change costing ≥ 1 % of the budget is judged against the whole pipeline; single runs swing ±25 %.
- 2026-10-04w: < 300 s is the final-release goal. The direction is RELEVANCE: spend the expensive work only on what can matter to the patch.
- 2026-10-04x (4): parallelism wherever it is EXACT, "use every available core".
- Single-pass principle (standing): never do a task twice; prefer reorder or identity preservation over re-derive or transport.
- 2026-10-19am: (a) later solve passes may warm-start or reuse the factorisation, with rounding-level changes judged at the visibility bars; (b) the late stage may reuse the base map's planar layout and constraints outside the gap pieces, after a spec (`late-stage-prefix-reuse-spec.md`).
- 2026-08-30l: a change to the layout's regions starts with a census of every consumer.
- 2026-10-05e: no airport-specific code. HECA and OTHH are the test cases; every rule below is general.
- Visibility bars (owner 2026-10-15): pavement 0.05 m, ground 0.5 m.

## 1. Measured (site numbers first)

**HECA: 1,111 s cold. OTHH: 971 s cold. Target: 300 s.**

Both builds:
- main `7947b7dfc`, lane `m12`, single foreground runs, `--no-ledger`, stage cache off;
- before batch D (#1069, #1072), which landed while they ran (phase 0 below);
- on the shared 18-core Mac, with other lanes building.

| | HECA `m12-heca-cold` | OTHH `m12-othh-cold` |
|---|---|---|
| machine load (1-min average: start / peak / end) | 9.3 / 26 / 11.8 | 10.9 / 30.7 / 15.5 |
| patch body | `547d881c129f` | `6cc75dff538e` |
| load | 8.1 | 26.5 |
| partition (pack; 18 workers) | 60.2 | 155.4 (pool 53.0) |
| classify | 51.6 | **180.3** |
| planar | 48.0 | 76.0 (readers pool 28.9) |
| flat site + road profile + shapes + ramp feet + jetway strips | 3.0 | 2.8 |
| constraints | 42.3 | 44.9 |
| **front, subtotal** | **213.2** | **485.9** |
| **solve** | **492.4** | 152.5 |
| — ribbon-free re-derive (§2.1, derive #2) | ≈ 82.7 | ≈ 97.2 |
| — stage 1 | 308.9 | 30.7 |
| —— pass 1a, twice (first, then the #768 retarget), and the interval | 91.5 (interval 5.0) | 17.6 (interval 2.6) |
| —— pass 1b, twice (the weld re-widen) | ≈ 212.5 (24 welds re-widened) | ≈ 10.5 (once; none re-widened) |
| — stage 2 | 100.8 | 24.6 |
| **late stage** | **358.1** | **292.6** |
| — cuts (gap pieces; pad-road exits) | 35.3 | 12.9 |
| — two full prefix re-derives (derives #3, #4) | **289.7** | **267.4** |
| — two late solves | 24.7 | 8.8 |
| emit | 12.7 | 15.8 |
| verify | 23.5 | 14.4 |
| unclocked | 11.4 | 8.7 |
| **total** | **1,111.3** | **970.9** |

**The load inflates these numbers.** The master's HECA build the same evening (`batchC3`, main c14cfb986) read 913.8 s with the stage cache ON and missing. 42.4 s of that was record encode + write, so its cache-off equivalent is ≈ 871 s, 0.78 of this build. Its last stage-1 pass spent 30.6 s in the solver against this build's 68.1 s: the sparse factorisations suffer most. Below, "quiet" means ×0.78; it is an estimate, not a measurement.

### 1a. Where the front goes (profiled captures)

Both captures ran under cProfile on the same tree. They are registered as `frames/m12/HECA.pkl` and `frames/m12/OTHH.pkl`.

**HECA** (305 s profiled; classify 66.4 s, planar 83.5 s):
- `classify`:
  - `mint_pad_roads` 25.9 s and `mint_osm_ribbons` 17.5 s. Of these, **38.2 s are 291 `unary_union` calls**: after every minted way the whole `occupied` polygon is re-unioned (`classify/ribbon_mint.py:429` and `:497`, `occupied = unary_union([occupied, rib])`).
  - `build_evidence` 10.5 s (`_pads` 9.5 s).
- `planar` on the FULL map (the gap pieces and pad roads are present, as in derives #3 and #4):
  - `build_arrangement` 46.7 s: pass C 12.7, `platform_split` 10.1, shore walls 4.2, zones 3.9, shelf 3.3, weld 2.5;
  - `build_structures` 15.7 s;
  - pack reads 10.9 s (memoised across the build's derives).
- **The road profile on the full map costs 50.9 s**, against 1.7 s on the base map: 14,348 `answer` calls build 3.4 M shapely `LineString`s. The late derives pay it. #1072 (batch D) builds each way's line once; m8 measured `RoadProfiles.answer` 36.9 → 23.7 s per late stage.

**OTHH** (921 s profiled on a machine at load 61; classify 327 s profiled against 180 s in the build, a ratio of 0.55):
- `classify` → `build_evidence` 259.9 s → `_pads` 257.6 s. Of that:
  - **`_with_jetways` → `airport/jetways.declared_jetways`: 193.9 s for 129 jetways.** Each `_obj_extent` builds `MultiPoint(pts)` from a Python list of EVERY authored vertex of the jetway `.obj`, then takes its convex hull: 186.9 s in `MultiPoint.__new__`. **That is ≈ 105 s of OTHH's 180 s classify.**
  - `_drop_skirted` 36.5 s (the skirt readings, which are the first parse of 36,559 placements' resources);
  - `_cluster_pads` 25.8 s (`base_slab.slab_polygons` 21.9 s).
- `mint_pad_roads` 17.1 s and `mint_osm_ribbons` 11.6 s (the same re-union as HECA).
- `planar` 187.1 s profiled: pack reads 92.4 s, `build_arrangement` 76.7 s (`plateau_cut` 13.6, pass C 13.5, shore walls 12.1, shelf 9.0, `platform_split` 8.9).
- Pack stage (outside the build's classify): `clusters` 183.2 s profiled (`connector_verdicts` 115.0, `plan_clusters` 68.2), `partition_pack` 84.9 s, `read_objects` 56.9 s. The DEM load is 51.6 s profiled.

## 2. Where the time goes

### 2.1 Four derives per build

A DERIVE is `pipeline/prefix.run_prefix`: planar → flat site → road profile → target channels → shapes → constraint generators → jetway strips → hold binding. A build runs it four times, on four classifications:

| # | classification | why it exists (law) | clocked in | HECA s | OTHH s |
|---|---|---|---|---|---|
| 1 | the base: no gap pieces, no pad roads | §55 (4): the base is "the build an airport with no gap sheet gets, row for row" | planar + constraints | ≈ 92 | ≈ 122 |
| 2 | #1 without its mapped-road ribbons | #100 option (c) (RULINGS 2026-09-30z): stage 1 is the ribbon-free map's problem by construction | `solve` | ≈ 83 | ≈ 97 |
| 3 | #1 + the gap pieces, cut by the base's solved levels | §55 (4) (iii) | `late_stage` | ≈ 145 | ≈ 134 |
| 4 | #3 + the pad roads, extended from their pads' solved levels | 13a (1): pad roads are junior to every pavement, the gap pieces too | `late_stage` | ≈ 145 | ≈ 134 |

- **Derives are ≈ 465 s of HECA's 1,111 s and ≈ 487 s of OTHH's 971 s.**
- #2 does not depend on any solve.
- #3 needs the base solve. #4 needs #3's solve.

### 2.2 Stage 1 runs four full QP passes at HECA

`solve/design.solve_design` → `solve/flex.stage_one`:
1. pass 1a;
2. pass 1a again, on the taxi trend retargeted from the first answer's apron levels (RULINGS 2026-10-15i (3) (b), #768: "one extra pass");
3. pass 1b, with the hold interval's rows (flat-pad spec v2 §1; 2026-09-30as);
4. pass 1b again, when the feasibility LP relaxed a weld (spec §57 (3) (ii-c); RULINGS 2026-10-08d (2)). 24 welds at HECA, none at OTHH.

One HECA pass (≈ 18,900 unknowns, ≈ 116,000 rows, ≈ 538,000 hard rows), the final one as the report gives it:
- 68.1 s in three QP solves: 244 + 57 + 117 active-set rounds, 428 + 96 + 202 linear solves;
- 25.6 s in the runway projection;
- 8.0 s in the §5a feasibility LP.

**Every active-set round refactorises.** PR #1063 counted 5,539 factorisations in one HECA replay's solve, and 294 thread-s of SuperLU in a 541 s solve (54 %).

OTHH's stage 1 is 31 s: its airside problem settles in 6 rounds. **The solve is HECA's problem. The derives are both airports' problem. The front is OTHH's.**

### 2.3 The front

- OTHH's front alone (486 s) is past the target: partition 155 s cold (36,573 placements, 167,677 parts), classify 180 s (≈ 105 s of it the jetway hulls, §1a), planar 76 s, load 26 s.
- HECA's front is 213 s.

## 3. Candidates, with numbers

Savings are CRITICAL-PATH seconds from §1's loaded numbers. Three kinds:
- **exact**: the output bytes cannot change, by construction;
- **rounding**: the change is at floating-point level, judged at the bars (19am (a));
- **output**: the patch moves; it needs an owner decision.

### 3.1 The brief's five

**C1. One derive instead of three** (gap pieces and pad-road map minted in the first derive's planar pass).
- **Not reachable as stated.** Two geometries do not exist before the solve:
  - the gap pieces' PARTS are cut by knives placed at the base's solved levels (`late_stage.cut_classification` → `classify/gap_terrace.terrace_cut`, reading `late_stations(pm_base, z_base, …)`);
  - the pad roads' extensions and run-outs are minted from their pads' solved levels (`classify/pad_road_exit.extend_pad_roads(…, _pad_levels(pm_base, z_base))`, `classify/ramp_runout.mint_ramp_runouts(…, pm_base, z_base)`).
- **What is reachable is the DORMANT-CELL form:**
  - the first derive carries every late cell UNCUT (pieces whole, pad roads at their source extent);
  - the base solve treats their vertices as foreign, as stage 1 treats groundside (`solve/design_stage.stage_split`);
  - the late stage EDITS the solved map locally (knives inside piece faces; extensions appended) instead of re-deriving it.
- **Law it touches:** §55 (4) (the base is the map WITHOUT the pieces, row for row) and 13a (1) (pad roads solved against a map without them). Present from the start, the late cells' rings re-node their standing neighbours, so the base solve changes. Measured once already (`late_stage.run_last_stages` docstring): with the pad roads' vertices and rows dropped inside ONE derive at OTHH, "12 gap nodes still moved up to 0.20 m — the rings the pad roads re-node". 0.20 m is over the pavement bar. **Owner decision D3.**
- **Saving:** derives #3 and #4 become a local edit (estimated 20–40 s). After phases 0–3 below have shrunk derive #3, the net is ≈ −30 s at either airport. The local planar edit has no implementation today: `planar` re-derives globally and renumbers ids by face walk (`planar/build.py:306-342`). **The largest engineering item for the smallest net prize once the exact phases land.**

**C2. Incremental late stage over the base** (19am (b); spec `late-stage-prefix-reuse-spec.md`).
- Landed in batch D, after these builds:
  - phase 1: `_way_intervals` answers a way that misses the extent with the prepared predicate (≈ 30 s of HECA's cut);
  - phase 2a: the gap stage is served the ribbon-free map's arrangement front (≈ 40 s per served derive, loaded);
  - #1072 (2b): the rim zone once per clip, a road way's line once per profile (`run_last_stages` 299.7 → 281.8 s on m8's replay).
- Phase 3 (reuse the rows) is STOPPED by that spec's §5a census: equality with the base is empirical, `triangle_planes` names followers, reused rows carry the base's face ids into verify's `source.inputs`, and the prize was ≈ 25 s per derive.
- **Left, exact:** the pass-A / pass-B intermediates and the structures/basins result (that spec's §5 item 3, not yet built), and serving derive #1 the front (it misses today only because the main pass holds a different `Airport` object). Estimate ≈ −20 s per derive on the critical path.
- **Risk:** none to output. The bar is that spec's canonical-join identity of every standing vertex.

**C3. Stage-1 pass merging** (fold the #768 retarget and the weld re-widen into fewer passes).
- The retarget reads pass 1a's FIRST answer (`design.solve_design._s1`). The re-widen reads pass 1b's answer (`no_step.HoldPass.rewiden(got[4])`). Each needs the pass before it, so merging changes which levels they read: an **output** change.
- **Fold A (the retarget):**
  - pass 1a solves once; the retarget is computed from it and applied in pass 1b only;
  - pass 1b's runway Bands are then centred on the un-retargeted pass-1a runway (`hold.derive(cs1a, levels, …)`);
  - saving: one pass-1a QP, ≈ 46 s at HECA loaded (≈ 25 s after C7), ≈ 8 s at OTHH;
  - touches 2026-10-15i (3) (b), whose words are "one extra pass". **Owner decision D1.**
- **Fold B (the re-widen):**
  - decide the widened welds from pass 1a's feasibility LP and the interval, both of which run before pass 1b, so pass 1b is solved once;
  - saving: one full pass, ≈ 100 s at HECA loaded (≈ 58 s after C7); 0 at OTHH (no weld re-widened);
  - touches spec §57 (3) (ii-c) and 2026-10-08d (2) (the weld projection reads pass 1b). A weld that pass 1b leaves off but pass 1a's LP did not flag stays off, and the seal (`hold.seal`) reports it. **Owner decision D2.**
- **Already refuted, not re-proposed:** the warm start (#1063: stage 1 344.6 → 331.4 s, noise) and the stage-1 component re-solve (HECA's stage 1 is one connected component).

**C4. Parallelism across independent passes on the work pool** (04x (4)).
- **C4a: derive #2 beside derive #1. EXACT.**
  - The ribbon-free classification is known before the planar stage (`stage_one_map.ribbon_free(cl)`). Derive #2 reads only it, the airport with its flat-site verdict (0.17 s, computed first) and the pack.
  - It runs in a pool worker, under `airport/pool.py`'s rules: the worker reads the DEM frame and the cached partition itself; the planar pack-read memo is shipped, never re-read.
  - Its result comes back pickled: `pm`, `cs`, `strips`, `hold` and the registries record (`capture_state.collect`). The stage cache's own records price that codec at ≈ 4 s per prefix.
  - Saving: HECA ≈ −70 s, OTHH ≈ −80 s. OTHH's worker pays its 26 s load unless the parent's `Airport` is shipped (open item).
- **C4b: derive #4 beside derive #3, SPECULATIVELY. EXACT.**
  - Derive #4's classification needs (i) #3's cut classification and (ii) the pads' levels and the run-out levels from #3's solve.
  - Pads are CONSTANTS of the gap stage (`late_fixed`), so (ii) is read from the main base instead. The roads cut and derive #4 then run beside derive #3.
  - After the gap solve, the real roads classification is computed (cheap) and compared by digest with the speculated one. Equal: the speculated derive is used. Different: derive #4 runs as today. The fallback IS today's path, so the output cannot change.
  - OTHH: no pad-road exit and no run-out (`exits 0`, `runouts 0`), so its roads classification cannot depend on the gap solve: the speculation always holds, ≈ −125 s.
  - HECA: 161 exits read pad levels. Whether the gap stage's pad medians equal the main base's is the phase-1 measurement. If they hold, ≈ −135 s.
- **C4c: the constraint generators on the pool. EXACT.**
  - `constraints.generate` runs ~60 generators in sequence, each a function of `(planar, law, airport)`. The rows are concatenated in `GENERATORS` order, so the set is identical.
  - `junction_mesh` (16–17 s) bounds a pooled run.
  - Saving ≈ −22 s per derive on the critical path (derives #1 and #3).
- **C4d: verify's families on the pool. EXACT.** Verify already pools the apron chords (8 workers, 1.8 s); the rest is serial (≈ 21 s at HECA). ≈ −12 s at HECA, ≈ −6 s at OTHH.
- **Not parallel, by data dependence:** derive #3 needs the base solve; derive #4 needs the gap solve (C4b speculates around it); stage 2 needs stage 1; the two late solves are sequential by 13a (1).

**C5. Fewer relaxation-LP calls.**
- The §5a feasibility LP runs before EVERY solve (`feasibility.demote_conflicts` inside `design._solve_stage`): 8–10 s per stage-1 pass at HECA, 1–2 s at OTHH. The runway projection's LP budget is already paid once per solve (#994).
- The retarget re-solve of pass 1a changes only the taxi-trend TARGETS (soft rows); its hard rows are pass 1a's. The LP reads the hard rows alone, so a memo keyed on the hard set's digest serves it. **EXACT.** ≈ −9 s at HECA, ≈ −2 s at OTHH.
- Pass 1b and its re-widen differ in their hard set (rows widened): no memo. C3 fold B removes that LP with its pass.
- The brief's "~105 s of relax LPs" was measured on an earlier tree. This build's report carries 9.6 s (pass 1a) and 8.0 s (last pass) per pass, plus the late solves'. Small once C3 lands.

### 3.2 Found by this lane

**C6. Classify's ribbon mint re-unions the whole occupied set after every way** (`ribbon_mint.py:429`, `:497`). HECA: 291 calls, 38.2 s of 66.4 s profiled classify; OTHH: ≈ 16 s.
- Fix: keep `occupied` as the base union plus an STRtree of the minted ribbons, and subtract from a new span only the ribbons it meets. It is the same set.
- Whether the bytes are identical depends on GEOS's difference order (rounding; the cells are snapped by `set_precision` to the snap grid). Bar: body identical, else every vertex within 1e-6 m.
- ≈ −30 s at HECA, ≈ −12 s at OTHH.

**C7. The solve's factorisations.** 54 % of a HECA solve is SuperLU (PR #1063).
- CHOLMOD (approved, lane m8 in flight): a supernodal Cholesky of the same SPD normal matrices. Rounding. Estimated 3–4× on the factor: ≈ −150 s at HECA loaded, ≈ −15 s at OTHH.
- Factor reuse inside the active set (19am (a), "reuse the factorisation"): a round changes a few rows of the active set; CHOLMOD's `updown` applies them as a rank-k update instead of a refactor. Rounding. Estimated a further −40 s at HECA, −5 s at OTHH.
- Bar: z within 1e-6 m, QP round counts unchanged, census identical.

**C8. The road profile on late maps.** 50.9 s on the full map against 1.7 s on the base. #1072 removed the line rebuild (`answer` 36.9 → 23.7 s per late stage). What is left is 3.4 M `project` calls; a per-way station table would remove most of it. Rounding (GEOS `project` against numpy). Not costed: re-measure after phase 0.

**C9. Stage-cache record writes on the user's first build.**
- Production defaults the stage cache ON (`auto_patch/engine_v2.py:180`), so a user's first build is a MISS that encodes and writes every record: 42.4 s at HECA (`batchC3`: encode 16.7 s + write 25.7 s).
- The owner's "initial creation" is that build, not the cache-off arm measured here.
- Writing records from a background thread (the encode is pure, the write is I/O) takes them off the clock. **EXACT.** ≈ −35 s at HECA on the product path; nothing on the cache-off measurement.

**C10. Verify after the patch.** Verify (23.5 / 14.4 s) judges a finished patch. Run beside the tile's next step, it leaves "initial creation". **Owner decision D4** (what the clock measures).

**C11. OTHH's jetway hulls** (`airport/jetways._obj_extent`): ≈ 105 s of OTHH's 180 s classify.
- `MultiPoint(pts)` over a Python list of every authored vertex, per placement.
- Fix, EXACT: build the same coordinates as one numpy array (the same IEEE operations in the same order) and hand them to `shapely.multipoints`; GEOS gets the identical point set, so the hull is identical.
- A further step, rounding: the hull of a resource's vertices computed once per RESOURCE and transformed per placement (a rotation and translation preserve the hull).
- General: every pack whose jetways are `.obj` placements without apt.dat jetway rows pays it. HECA's whole `build_evidence` is 10.5 s.
- **Saving ≈ −100 s at OTHH.** The cheapest large item in this spec.

**C12. OTHH's pack front, by relevance** (04w (3)).
- Partition 155 s cold (`clusters` → `connector_verdicts` and `plan_clusters` serial; `partition_pack` pooled), and planar pack reads (pool 28.9 s + at-grade 20.7 s).
- The pack is read whole; the patch can only be touched by the members near it.
- A relevance screen before the partition is its own spec (#362 lineage). Not costed in detail here; the plan carries an estimate of −90 s on partition and −30 s on planar, marked as such.

## 4. The architecture

Derive once where the law allows. Run independent derives side by side. Solve each stage-1 problem in as few passes as the law allows. Never refactorise what has not changed. Read only the pack that can touch the patch.

```
load → partition (pool; C12 relevance) → classify (C6, C11)
   ├─ derive #1 (base; C4c generators pooled)                ─┐  C4a: side by side
   └─ derive #2 (ribbon-free, in a worker)                   ─┘
stage 1 (C3 folds, C5 LP memo, C7 factor) → stage 2 (C7)
   gap cut ─┬─ derive #3 (gap stage; C2, C4c)                    ─┐ C4b: side by side
            └─ roads cut + derive #4 (speculative, in a worker)   ─┘
   gap solve → digest check (use #4, or re-derive) → roads solve
emit → verify (C4d; or off the clock: D4)
```

With D3 (dormant late cells), derives #3 and #4 become a local edit of the solved map, and the late solves read rows minted only for the edited faces.

## 5. Phased plan

Every phase:
- iterates synthetic-first on `frames/m12/HECA.pkl` / `frames/m12/OTHH.pkl` replays;
- closes with ONE build of the airport the phase is for (HECA by default; OTHH for C4b, C11, C12);
- reads the clock with `tools/check_build_time.py --runs 3`, never one run per side;
- holds the bars in its row.

Savings are critical-path seconds, loaded.

| phase | content | kind | bar | HECA s | OTHH s |
|---|---|---|---|---|---|
| 0 | batch D (#1069, #1072), already on main; re-measure both airports; CHOLMOD (m8) | landed / rounding | — | ≈ −88 (m8's figures) | ≈ −35 |
| 1 | C4a derive #2 beside #1; C4b speculative derive #4; C5 LP memo; C11 jetway hulls (numpy form) | exact | body byte-identical at HECA, OTHH, KCLT; the `pool` report names the workers; a forced speculation miss (twin) takes today's path | −214 | −307 |
| 2 | C7 CHOLMOD + factor reuse | rounding | z within 1e-6 m; QP round counts unchanged; census identical | −190 | −20 |
| 3 | C6 ribbon-mint union; C4c generators pooled; C4d verify pooled; C2's remaining intermediates | exact (C6: rounding at worst) | body identical (C6: vertices within 1e-6 m) | −30 −44 −12 −20 = −106 | −12 −44 −6 −20 = −82 |
| 4 | D1, D2: the stage-1 folds | output | movers listed with landmarks; runway ≤ 0.05 m, ground ≤ 0.5 m, else the owner's read | −83 | −8 |
| 5 | D4 verify off the creation clock; C9 record writes off-thread (product path) | clock definition / exact | patch body and sidecar identical | −23 | −14 |
| 6 | C12 pack relevance (own spec) | exact by its own bar | rebake plan and patch identical | — | ≈ −120 (estimate) |
| 7 | D3 dormant late cells + local late edit | output | 2026-08-30l census table first; movers within the bars, else the owner's read | ≈ −30 | ≈ −30 |

Running totals (loaded → quiet ×0.78):

| after phase | HECA | OTHH |
|---|---|---|
| measured | 1,111 → 867 | 971 → 757 |
| 0 | 1,023 → 798 | 936 → 730 |
| 1 | 809 → 631 | 629 → 491 |
| 2 | 619 → 483 | 609 → 475 |
| 3 | 513 → 400 | 527 → 411 |
| 4 | 430 → 335 | 519 → 405 |
| 5 | 407 → 317 | 505 → 394 |
| 6 | 407 → 317 | 385 → 300 |
| 7 | 377 → 294 | 355 → 277 |

**Reading.**
- The EXACT and rounding-level phases (0–3) take HECA to ≈ 400 s and OTHH to ≈ 410 s quiet. Phase 1 alone is the largest step at both airports, and C11 is OTHH's cheapest large item.
- **Under 300 s needs every phase, including the four owner decisions, and it lands at the 300 s line with no margin** against the ±25 % single-run noise. At HECA the remaining time is the main derive (≈ 70 s after C4c), stage 1 and 2 (≈ 150 s after C7 and the folds) and the front (≈ 150 s). At OTHH it is the front.
- A margin needs work this spec does not cost: pooling inside planar (pass C and the shore walls per region) and inside classify (`_pads` per cluster), and stage 2's own passes.

## 6. Owner decisions

| # | question | recommended default | what moves |
|---|---|---|---|
| D1 | Fold the retarget into pass 1b: pass 1a is solved once, and 2026-10-15i (3) (b)'s "one extra pass" becomes "applied in pass 1b"? | YES, if the HECA replay's movers are within the bars | pass 1b's runway Band centres move by what the retarget moved the runway in pass 1a (expected at the cm level: the runway is senior); apron and taxi levels near the retargeted contacts |
| D2 | Decide the weld re-widen before pass 1b, from pass 1a's LP and the interval, so pass 1b is solved once? | YES, with every weld still off after pass 1b reported by the seal | the 24 HECA welds that today get a second pass 1b; nothing at OTHH |
| D3 | The late cells present and dormant from the first derive; the late stage edits the solved map locally (§55 (4) and 13a (1) re-read: the base is the map WITH the late cells' outlines, their rows dropped)? | ASK AFTER phases 0–3 are measured: its net prize is then ≈ 30 s and its engineering is the largest | measured once: OTHH 12 gap nodes up to 0.20 m (pavement bar 0.05 m); every standing ring a late cell touches gains vertices |
| D4 | "Initial creation" ends when the patch and its sidecar are written; verify runs beside the tile's next step? | YES | nothing in the patch; verify's report arrives later |

## 7. Not done here, and open items

- **Builds after batch D were not run.** These numbers are the pre-D base (`7947b7dfc`); phase 0 re-measures. When this spec was written the machine was at load 61.
- **Not profiled:** the solve (the per-pass split is from the report; the factorisation share is PR #1063's) and OTHH's partition beyond the capture's call graph.
- **C4a at OTHH:** shipping the parent's `Airport` to the worker instead of a 26 s re-load must be read against the pool's "never ship a DEM" rule (the DEM is already a `SharedArrays` block).
- **C4b at HECA:** whether the gap stage's pad medians equal the main base's is the phase-1 measurement.
- **C6 and C11's byte identity** is a measurement, not a claim. C11's numpy form is exact by construction; its per-resource form is not.
- **`road_within_shape`** mints 2,345,423 rows on the late map against 157,121 on the base (late-reuse spec §5a). Every late assembly, `late_constraints` and verify carries them. Not costed here; worth its own issue.
- **C11 is unfiled.** It is a general defect (any pack with `.obj` jetways); the master files it.
