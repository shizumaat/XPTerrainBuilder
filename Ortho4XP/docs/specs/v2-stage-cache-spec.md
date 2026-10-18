# v2 per-stage content-keyed cache — spec (2026-10-17, Beta 3 W4)

Status: PROPOSAL. Plan: `beta3-build-speed-plan-20261017.md` W4. Issues: manifest
B3-08 … B3-12. Prior art: E `docs/specs/graph-keys.md` (content-keyed artefact
store); our own `auto_patch_v2/airport/partition_cache.py` (issue #362, #382),
`topology_cache.py`, `extension_cache.py`, `dem_witness.py`,
`pipeline/capture_state.py`.

AMENDED 2026-10-18 (owner RULINGS 2026-10-18b, issue #843): the cache covers the
WHOLE airport build — constraints (per generator), jetway_strip, solve,
late_stage, emit and verify as well as the front half. The amendment is §1
"The back half", §3b, §4b, §4c, the §5 memo rule, §6 sizes, §7 #880 and the
prefix re-runs, §8 T6–T13, §9 (7)–(9), §10 steps 6–9, §11, §12–§14. Cache root
and cap are ruled (RULINGS 2026-10-17a Q1/Q2), so §6 and §7 now state them.

## 1. Problem

`auto_patch_v2.pipeline.build.build` (`pipeline/build.py:645`, 1,046 lines) runs
load → partition → classify → ramp_feet → planar → flat_site → road_profile →
shapes → constraints → jetway_strip → solve → late_stage → emit → verify, each
stage clocked into `wall_s` of `<ICAO>.report.json` (`build.py:1646`). Only the
pack partition is cached (`partition_cache.py`, 298 of 841 s at OTHH per its
module doc). Everything before the constraint stage is recomputed on every
build, although a change to a law table, a constraint generator, the solve or
the emitter changes none of it. Median stage shares over five airports
(`engine_v2.py:70-84`, re-measured 2026-09-30): load 6.4, partition 13.5,
classify+structures 17.0, planar 9.9 — about 47 % of the airport wall that a
law/solve/emit change does not need; the OTHH comment puts partition +
structures + planar at 75 % there.

Two facts make a stage cache possible today and one makes it hazardous:

- the stage products are already data: `Airport`, `Classification`,
  `PlanarMap`, `ShapeStage` are pickled by `tools/v2_solve_replay.py --capture`;
- the code-identity mechanism exists: `partition_code.CODE_MODULES` is the
  static import closure of the reading's entry modules, held by
  `tests/auto_patch_v2/test_partition_code_closure.py`, and the freeze writes
  the same digest beside the module (`partition_code.sha256`);
- seven stage products are NOT data but module globals the planar stage fills
  and later stages read (`pipeline/capture_state.py` REGISTRIES: `HELD`,
  `PLATEAUS`, `LANDINGS`, `LANDING_RUNOUTS`, `PLATFORMS`, `TERRACES`,
  `PAD_AIRSIDE`). The replay tool carries them since 2026-10-02 (#208, #224);
  the BUILD still hands them through the module. A cache that serves a
  `PlanarMap` without them would re-create #224 (KCLT 65,212 rows vs 49,981) in
  production.

(#888 and #893 have since made the registries a record: `model/registries.py`
`Registries` rides the map as `PlanarMap.registries`, and the seven module
globals are gone once #893 merges.)

### The back half (amendment 2026-10-18)

The shares above are from 2026-09-30 and no longer describe the build. The
stage clocks of the last orchestrator sweep (`wall_s` of
`<data repo>/tmp/auto_patch_v2/<tile>/<ICAO>/<ICAO>.report.json`, written
2026-10-16/17, one build each, read 2026-10-18) put most of the wall AFTER
the shape stage:

| Airport | total s | front (load…shapes) | constraints + jetway | solve | late_stage | emit + rebake | verify |
|---|---|---|---|---|---|---|---|
| HECA | 806.8 | 12.7 % | 4.3 % | 46.6 % | 31.9 % | 1.3 % | 2.2 % |
| CYXY | 42.4 | 31.7 % | 6.0 % | 52.0 % | — | 4.1 % | 4.3 % |
| OTHH | 955.3 | 51.7 % | 7.1 % | 16.5 % | 21.0 % | 1.4 % | 1.4 % |
| KCLT | 551.0 | 27.4 % | 6.0 % | 39.0 % | 23.4 % | 1.4 % | 1.8 % |
| SPJC | 215.9 | 28.3 % | 6.0 % | 35.4 % | 24.8 % | 1.4 % | 3.3 % |
| **median** | | **28.3 %** | **6.0 %** | **39.0 %** | **23.4 %** | **1.4 %** | **2.2 %** |

Single runs (±25 %); shares, not times, are what this spec uses. Two facts
in these numbers shape the back half:

- the solve and late_stage clocks CONTAIN FRONT-HALF WORK. `solve` includes
  `stage_one_problem`, which re-runs planar → flat_site → road_profile →
  shapes → constraints → jetway_strip → hold_pass on the ribbon-free
  classification (`build.py` `_ribbon_free`, #100 (c)); `late_stage` runs the
  same prefix once per derive (`late_stage.run_last_stages`: the gap pieces,
  then the pad roads — two derives where both exist). HECA's late stage is
  `{"cut": 22.1, "derive": 213.5, "solve": 16.8}` s — 83 % of it is the
  prefix. A build runs the prefix up to FOUR times (base, ribbon-free, gap
  derive, pad-road derive);
- the constraint set is LARGE: HECA (regL3 capture, constraints re-run on main
  603c44e05, 45.6 s) is 4,337,588 rows (`road_within_shape` alone 3,411,888),
  423 MB as pickled Python objects, 50 MB zlib-1; pickling it takes 3.3 s and
  unpickling 3.0 s. A cache that pickles constraint sets as objects pays
  ~16 s per HECA build on the miss arm (four sets). §4c answers this.

## 2. Design in one paragraph

Each cacheable stage becomes a function of named inputs to a named output
record; its key is `stage | stage code digest | law witness | input digests`;
the output is stored content-addressed beside the partition cache; a read is
served only when its witnesses (DEM samples, law rows) answer the same today.
The module registries become fields of the planar stage's output record
(`capture_state.collect()` is already that record) and are INSTALLED by the
build explicitly, so a hit and a miss enter the constraint stage with the same
state by construction. The freshness gate above (`driver._auto_patch_is_current`,
whole-tree `o4_code`) is untouched: it decides whether a patch is rebuilt; this
cache decides how much of the rebuild is recomputed.

The back half (§4b) is the same design with three additions. (1) The
cross-stage module globals the back half still has (`solve.feasibility.
HARD_CONFLICT`, `constraints.no_step.RUNWAY_FLEX`, the hold report the solve
writes into `registries.held`) become fields of the solve's output record, the
#841 move repeated. (2) The prefix re-runs inside the solve and the late stage
go THROUGH the cache, keyed by their own classification, so a change after the
shape stage stops re-paying them. (3) The solve is never served on its key
alone: its residual certificate is re-evaluated on the cached `z` against the
constraint set it is served with, and verify is served only for the bytes on
disk it judged. Every stage's key is chained on its inputs' OUTPUT digests,
so a stage that re-runs and produces the same record leaves every later stage
a hit (early cutoff).

## 3. Consumer census (RULINGS 2026-08-30l)

The affected state is the set of module-level mutable globals in
`auto_patch_v2`. The census is `capture_state.py`'s table, re-read 2026-10-17
(`grep -rn 'capture_state' src/auto_patch_v2` — the only production reader is
`pipeline/stage_one_map.py:426,490`, which already treats the registries as a
record it collects, installs and restores around the ribbon-free stage-1 pass).

| Registry | Filled by (stage) | Read by | Ruling here |
|---|---|---|---|
| `model.platform.HELD` | planar (`planar/platform`, `planar/pad_cut`) | `constraints/{platform,no_step,jetway_strip}`, `model/platform` | STAGE OUTPUT, field `held`; readers take it from the record |
| `model.platform.PLATEAUS` | planar (`pad_cut`) | `constraints/platform` | STAGE OUTPUT `plateaus` |
| `model.platform.LANDINGS` | planar (`landing` via `platform`) | `constraints/{platform,pads}` | STAGE OUTPUT `landings` |
| `model.platform.LANDING_RUNOUTS` | planar (`landing_runout`) | `constraints/{ramp_runout,platform}`, `planar/landing` | STAGE OUTPUT `landing_runouts`; the in-stage reader (`planar/landing`) keeps the module path until the planar stage is done |
| `model.platform.PLATFORMS` | planar (`platform`) | `constraints/platform`, `pipeline/publication` | STAGE OUTPUT `platforms` |
| `model.pad_terrace.TERRACES` | planar (`pad_terrace`, `overlay`) | `constraints/pad_fronting`, `pipeline/publication` | STAGE OUTPUT `terraces` |
| `planar.overlay.PAD_AIRSIDE` | planar (`overlay`) | `pipeline/publication` | STAGE OUTPUT `pad_airside` |
| `planar.pad_blocks.BLOCK_PLANS`, `classify.evidence.CLUSTER_PADS`, `planar.platform.MERGE_READ` | their stage | tools / same stage | NOT CACHED, NOT CARRIED (same ruling as capture_state) |
| `planar.cluster.WHY`, `structure_deck.LAST_DECK_WITNESS`, `constraints/*.STATS` | their stage | diagnostics | NOT CARRIED; a hit prints "served" in their place |
| `anchor_rule._PAD_BOXES`, `constraints/*._CACHE`, `_MEMO`, `routes._CACHE` | on demand | on demand | MEMOS keyed on input — unaffected |
| `solve.feasibility.HARD_CONFLICT`, `constraints.cluster_pad.{YIELDED,…}`, `no_step.RUNWAY_FLEX` | after the front-half stages | `pipeline/publication`, `pipeline/late_stage` | produced by the back half: RULED in §3b (`HARD_CONFLICT`, `RUNWAY_FLEX` become solve-record fields; `cluster_pad.*` are emit-internal scratch) |
| `partition_cache._TAKEN/_HELD/_STAMPS/_DEMS` | partition | companions | the partition cache's own bookkeeping; the stage cache's companions use `partition_cache.companion` the same way |

A new module global in `auto_patch_v2` that a later stage reads is a defect
this spec's twin (§8 T1) catches: the census is executable.

## 3b. Consumer census of the back half (amendment 2026-10-18; RULINGS 2026-08-30l)

Every reader of each back-half stage's output, in ONE table, before any key is
proposed. Read 2026-10-18 on main 603c44e05 and #893's branch
(`origin/claude/cloudregplumb` 78e2ca4c9): `pipeline/build.py` 1,095–1,690,
`pipeline/shapes.py`, `constraints/__init__.py`, `pipeline/late_stage.py`,
`pipeline/publication.py`, `pipeline/stage_one_map.py`, and a grep of every
module-level mutable in `constraints/`, `solve/`, `emit/`, `verify/` for
readers outside its own module.

| Product (writer) | Read by | Carried how today | Ruling |
|---|---|---|---|
| per-generator rows (`constraints.GENERATORS`, each `fn(pm, law, airport)`) | `generate()` concatenation only; no generator reads another's rows | return value | RECORD per generator (§4b.1) |
| `constraints/*.STATS[fn]` (incl. `pads.AIRSIDE_LED`, folded into `STATS["pad_flats"]`) | `generate()` → `counts` → `report["constraints"]` | module global read right after the call | FIELD `stats` of the generator's record; the module global stays a diagnostic written by a run, never read across a cache boundary |
| `eat.RECTS`, `eat.REACH`, `foot_rows.VERDICTS`, `cluster_pad.NO_OUTLINE` | own module only (no outside reader found) | diagnostics | NOT CARRIED; a hit prints "served" for them |
| memos: `routes._CACHE/_PAIRS_MEMO`, `stretches._CACHE`, `precedence._CACHE`, `contiguity._CACHE`, `taxi._PAIR_CACHE`, `cluster_pad._POLY_MEMO/_AIRSIDE_MEMO`, `no_step._EDGES_MEMO`, `pad_fronting._CACHE`, `pad_frontage_gs.HELD_PAIRS` (read-or-compute, `per_map`), `jetway_strip._BASE_MEMO`, `shoulder_crossing._LAST`, `runway_mean_slope._LAST` | several generators and post-passes | keyed on the map / its inputs; a reader recomputes on a miss | NOT CARRIED (pure). LAW-WITNESS HAZARD: a memo filled in one stage hides its law reads from the next — §5 memo rule |
| post-pass products: `water_exempt`, `seam_exempt` (+ `yielded_out` → `seam_yielded`), `structures.reconcile_datums`, `eat.withdraw_against_senior`, `ramp_runout.runout_exempt`, `ceiling.pavement_ceiling`, `pavement_cap.pavement_road_cap` | the assembled `ConstraintSet` → jetway_strip, solve, late_stage, publication (`eat_rects` reads the final pins), `joint_steps` | return values | RECORD `constraints.assembly` (§4b.1) |
| `apply_joints` mutation of the `ShapeStage` (`dropped`, `flats_straddling`, `bands_withdrawn`) | build's report lines, `report["shapes"]` | IN-PLACE mutation of the shape stage's record | FIELD of the assembly record, installed on a hit (a hit that skipped it would print zeros) |
| `jetway_strips(...)` → `strips` | solve (`strips=`), late_stage, `publication(strips=)`, `jetway_strips_ll` | return value | RECORD `jetway_strip` |
| `cluster_pad.{YIELDED, REFERENCE, DERIVED, OFFSET_SPREAD, TOUCHING_STEPS}` | `pipeline/publication` (lines 326–388), after it calls `cluster_pad_faces` / `cluster_offsets` itself; `constraints/jetway_strip` also calls `cluster_pad_faces` | written and read INSIDE one stage (emit; jetway_strip) | NOT CARRIED: intra-stage scratch. Twin T1 fails if a reader in another stage appears |
| `solve.feasibility.HARD_CONFLICT` (written by `feasibility.publish` inside the solve) | `pipeline/publication._hard_conflict`, `pipeline/late_stage` (lines 379–441: base conflicts merged with the late solve's), `tools/v2_solve_replay` | MODULE GLOBAL across solve → late_stage → emit | DELETED as a global; FIELD `hard_conflict` of the solve record and of the late record; publication and late_stage take it as an argument (the #841 move) |
| `constraints.no_step.RUNWAY_FLEX` (reset by `hold_pass`, written by `HoldPass` flex inside the solve) | `pipeline/publication._runway_flex` | MODULE GLOBAL across solve → emit | DELETED as a global; FIELD `runway_flex` of the solve record |
| hold report keys (`model.platform.HOLD_REPORT_KEYS`) written into `pm.registries.held` by `no_step.HoldInterval` during the solve | `constraints/platform` (`rec["reach_band"]`), publication (`platforms` key), build's late-stage carry (`hold_report` / `install_hold_report`) | mutation of the map's record (no global since #893) | FIELD `hold_report` of the solve record, installed into the map's `registries.held` on a hit — the same carry the late stage already does |
| `Solution` (`z`, status, residual, message), `DesignReport` (stages, targets, pin_yield, jetway_strip), `size` (LP dims), `tt2_rep` → `lrep.taxi_trend["second_pass"]`, `_s1.report` | late_stage (base `z`, `pin_yield`), `with_pin_yield`, `displacement_by_role`, `ground_envelope`, runway report, emit (`graded_surface`, `publication`, `pub["design"]`, `design_target`), report | return values + ONE mutation of the load report (`lrep.taxi_trend`) | RECORD `solve`; `second_pass` is a field the build writes into `lrep` on hit and miss alike |
| `run_last_stages` → final `pm`, `sol`, `_late` (`cl`, `cs_full`, `strips`, `design`, `pin_yield`, `cut`, `followers`, `stage`, `join`, `dropped`, `follow`, `wall_s`), `_prefix_stage["stage"]` (the last derive's `ShapeStage`) | `with_pin_yield`, emit, `joint_steps`, report, `gap_pieces`, `late_stage()` publication | return values + a build-local closure variable | RECORD `late_solve` (§4b.4); `cs_full` and the derive's `ShapeStage` are REFERENCES to the derive's own entries, not copies |
| post-solve glue in `build.py` (`with_pin_yield` → `pm.road_join_yield`, `displacement_by_role`, ground envelope, runway profile block, road agreement, shore weld, natural shore) | emit, report | in-function locals | part of the EMIT stage (it is what emit reads); moved into `pipeline/emit_stage.py` (§10 step 8) |
| emit products: `surf` (graded surface), `pub` (publication), `paths` (patch `.osm`, `.axes.json`), tile pieces, `<ICAO>.graded.json`, `rebake.screen.json`, `report["emit"/"warnings"/"shore_weld"/…]` | verify (`census_frame(surf, law, pub, caps)`), the tile build (files), the harness census (files) | files + locals | RECORD `emit`: the FILE BYTES and the in-memory `surf`/`pub` verify reads |
| `report["verify"]`, the DEFECT / under-floor lines, `verify.census.WALL_S`, `_vpool` | `report.json` → `auto_patch/engine_v2.py` defect labels → UI warnings | report + printed lines | RECORD `verify` (lines re-printed on a hit); `WALL_S`/pool are clocks, served as "served" |
| `pipeline/xplat` `_PROJ_*` globals | the xplat dump only (`Config.xplat_dump`) | armed per build | the dump BYPASSES the cache (§7) |

Nothing else in `constraints/`, `solve/`, `emit/`, `verify/` or the back half of
`pipeline/` is a module-level mutable read outside its stage. The table is the
extended twin T1 (§8): an AST walk that fails on a cross-stage global read not
listed here.

## 4. The stages and their keys

Cached stages, in order, with the inputs each is a function of:

| Stage | Output record | Inputs (digested) | Witnesses (checked on read) |
|---|---|---|---|
| partition | (exists) | pack content, dump, law, frame, code | DEM samples (`dem_witness`) |
| classify | `Classification` | `Airport` digest (post-partition), rules digest (`classify.load_rules()`), `classify` code digest | law rows read (§5) |
| planar | `PlanarMap`, `pstats` (minus diagnostics), registries record (`capture_state.collect()`), `objects_out` | `Classification` digest, `Airport` digest, pack objects digest (`pack_report`), `planar` code digest | DEM samples; law rows read |
| flat_site, road_profile, shapes | their records (`ShapeStage`, …) | `PlanarMap` digest + each one's code digest | law rows read |

Not cached: load (reads apt.dat, CIFP, DSF dump, OSM, DEM; its `Airport` is
~450 MB pickled at HECA and CYXY because it carries the DEM rasters, so it is
never stored — a build that misses anywhere runs load; a build that hits
everywhere is skipped before load by §7's walk) and ramp_feet (reads the
resource cache, 1 s class). The back half — constraints, jetway_strip, solve,
late_stage, emit, verify — was "not cached" until RULINGS 2026-10-18b; it is
§4b.

Key = sha256 over the canonical form of
`{"stage", "version": CACHE_VERSION, "code": <stage code digest>, "law": <law
witness digest>, "inputs": {name: digest}}`. Canonical form: `json.dumps(…,
sort_keys=True, separators=(",", ":"))` with floats repr'd; no timestamps, no
paths, no process state. (E's `graph/canon.py` rules; ours is the stdlib form.)

**Input digests** are taken from the objects in hand, not from files: a
`digest_of(product)` per stage product — `pickle.dumps(product, protocol=5)`
hashed, with a twin that the digest is stable across two processes for the
same product (dict order and set order are the hazard: the digest walks
dataclasses field by field and sorts sets; `pickle` alone is NOT stable for
sets). The partition's own fingerprint (`partition_cache.fingerprint`) is the
`Airport` digest's partition component.

**Stage code identity** generalises `partition_code.py` into
`auto_patch_v2/pipeline/stage_code.py`: one `ENTRY_MODULES` tuple per stage,
the closure computed and held by a twin (`test_stage_code_closure.py`, the
`test_partition_code_closure.py` pattern), the freeze writing one
`stage_code.sha256` with all stages' digests (both `.spec` files already run
`partition_code.write_freeze_digest` with `runpy`; this adds one call). A
shared helper module in two closures is fine — an edit re-reads both stages,
which is the truth.

(Landed as #889: `pipeline/stage_code.py` with `ENTRY_MODULES` for classify,
planar, flat_site, road_profile, shapes; §4b extends the same table.)

## 4b. The back half (amendment 2026-10-18)

Every back-half stage below is stated the same way: its OUTPUT RECORD (what is
stored; no module global), its DIGESTED INPUTS, its CODE IDENTITY (a
`stage_code.ENTRY_MODULES` entry, closure held by `test_stage_code_closure.py`),
the WITNESSES checked on read, and what a HIT skips. Every key also carries the
environment fingerprint (§4c) and `CACHE_VERSION`. "Digest" is §4's
`digest_of`, or §4c's columnar digest for constraint rows.

### 4b.1 constraints — one record PER GENERATOR, plus one assembly record

**Are the generators independent? Yes, by signature and by census.** Each of
the 57 entries of `constraints.GENERATORS` is `fn(pm, law, airport) -> rows`;
`generate()` calls them in order and concatenates. No generator reads another
generator's rows. Their only couplings are (a) PURE memos keyed on the map
(§3b), whose answer does not depend on which generator fills them first, and
(b) per-module diagnostics. Everything that reads ALL rows — `water_exempt`,
`seam_exempt`, `structures.reconcile_datums`, `eat.withdraw_against_senior`,
`ramp_runout.runout_exempt`, `ceiling.pavement_ceiling`,
`pavement_cap.pavement_road_cap` and the shape stage's `apply_joints` — runs
AFTER the generators, as a post-pass. So: one record per generator for its raw
rows, and one ASSEMBLY record for the post-passes. Twin T6 makes the
independence executable (each generator alone, in a fresh process, in a
shuffled order, produces the same rows).

| Record | Output | Inputs (digested) | Code identity | Witnesses on read | A hit skips |
|---|---|---|---|---|---|
| `constraints.gen.<name>` (one per `GENERATORS` entry) | `rows` (columnar, §4c), `stats` (its `STATS[fn.__name__]` slice), `count` | shape-stage `pm` (incl. `pm.registries`), `Airport` | `stage_code` entry `constraints.<name>`: closure of `fn.__module__` (generators in one module — `taxi` has four — share the code digest, never the record) | law rows the call read (§5); DEM samples when `airport` DEM is read (the front half's `dem_witness`) | that generator (HECA: `junction_mesh` 15.3 s, `apron_within_shape` 6.0 s, `road_within_shape` 5.6 s; most < 0.5 s) |
| `constraints.assembly` | the assembled `ConstraintSet` (columnar), `counts` (incl. every post-pass count and `joint_dropped.*`), `seam_yielded`, the `ShapeStage` drop fields (`dropped`, `flats_straddling`, `bands_withdrawn`) | the ORDERED list of generator output digests, `ShapeStage` digest (`withdraw`, `edges`, `bands`), `pm` | entry `constraints.assembly`: `pipeline.shapes` + the post-pass modules (`water_exempt`/`seam_exempt` move from `constraints/__init__` to `constraints/assembly.py` so the closure is the post-passes, not every generator) | law rows read | the post-passes and the joint filter (HECA ≈ 5 s: `joint_filter` 2.1, `pavement_ceiling` 1.2, `pavement_road_cap` 1.0, exempt passes) |

A FULL hit reads the assembly record alone (the generator records are read
only when the assembly misses). A ONE-GENERATOR change re-runs that generator,
reads the other 56 records and re-runs the assembly. The generators also run in
every prefix re-run (§4b.3); each run has its own records, keyed by its own
`pm`.

The per-generator split pays on a generator CODE change. On a LAW change it
pays only once the row witness of §5 lands: under the first landing's
whole-law digest every generator re-runs on any law edit.

### 4b.2 jetway_strip — one record

| Output | Inputs | Code | Witnesses | A hit skips |
|---|---|---|---|---|
| `strips` (the region record `jetway_strips()` returns) | `pm`, assembly output digest, `Airport` (riders are `rider_candidates(airport, law)`, derived inside) | entry `jetway_strip`: `constraints.jetway_strip`, `airport.riders` | law rows read | 0.3–1.2 s; kept as its own record because the solve, the late stage and emit all read `strips`, and #880's walk needs every stage keyed |

### 4b.3 the prefix re-runs go THROUGH the cache

`stage_one_problem(cl, _ribbon_free, …)` and each late-stage derive call the
build's own prefix — `build_planar` → `flat_site.detect` → `preferred_road_z` →
the runway-chord / trend / road-ramp passes → `shape_stage` →
`shape_constraints` → `jetway_strips` → `hold_pass` — on another
classification (ribbon-free; the cut one). Today `_ribbon_free` is a closure
inside `build()`, so its code has no closure of its own and the replay tool
re-states it.

Ruled here: the prefix becomes a named function, `pipeline/prefix.py`
`run_prefix(airport, cl, law, inputs, pack, cache) -> PrefixRecord`, used by the
main build, `stage_one_problem`, the late stage's derives and
`tools/v2_solve_replay.py`. Each of its steps reads and writes the SAME stage
entries as the main build (planar, flat_site, road_profile, shapes,
`constraints.gen.*`, `constraints.assembly`, `jetway_strip`), keyed by the
classification it was handed. The prefix itself has no record: it is the
sequence of its steps' records. A change confined to the solve, the late stage,
emit or verify then re-pays none of the four prefix runs (HECA: the late
stage's 213 s `derive` is prefix work).

`hold_pass(pm, law, airport)` is a constructor (`HoldPass`); its state lives
until the solve mutates it, so it is part of the SOLVE's inputs (its arguments
are already digested), never a record.

### 4b.4 solve — one record, never served without its certificate

| | |
|---|---|
| **Output record** | `Solution` (`z` as a float64 array, exact bits; `status`, `residual`, `iterations`, `message`), the `DesignReport` (whole object), `size` (LP dims), `pin_yield`, `second_pass` (the `tt2_rep` keys the build writes into `lrep.taxi_trend`), `stage_one_report` (`_s1.report`), and the three former side channels: `hard_conflict` (was `feasibility.HARD_CONFLICT`), `runway_flex` (was `no_step.RUNWAY_FLEX`), `hold_report` (`model.platform.hold_report(pm.registries.held)` after the solve). NOT stored: the LP matrix, the stage-one map (its products are the prefix's own entries), `wall_s` (served as "served"). |
| **Inputs** | `pm` (shape stage, incl. registries), assembly output digest, `jetway_strip` output digest, the ribbon-free prefix's record digests (its `pm`, assembly, strips — `None` when no ribbon was minted), `cfg.options` (`Options` fields). |
| **Code** | entry `solve`: `solve.design`, `solve.api`, AND the callback modules the build binds into it because `solve` may not import `constraints` — `constraints.road_ramp` (`reach_seed_rewrite`), `constraints.no_step` (`hold_pass`), `constraints.taxi_trend` (`stage_one_retarget`) — and `pipeline.stage_one_map`. A closure from `solve.design` alone would miss the callbacks; the closure twin holds the declared list. |
| **Witnesses on read** | (1) the key's law rows (§5); (2) THE CERTIFICATE: `solve.design_report.residual(cs, z, objective)` re-evaluated on the cached `z` against the constraint set the build holds NOW must equal the stored `Residual` field for field, bit for bit (the same code on the same numbers is deterministic); (3) `len(z) == len(pm.vertices)` and every `z` finite; (4) the hard rows (`[design] hard_generators`) hold at the cached `z` to `hard_tol_m`, as the solve's own polish guarantees. Any failure REFUSES the entry (§6: refused, never repaired) and the solve runs. WHAT IT CATCHES: a `z` served for a different constraint set than the one in hand — a constraint digest that omits a field (a codec bug), a header/payload mix-up, a reference resolved to the wrong record. WHAT IT DOES NOT: an input outside the constraint set that the key missed (an `Options` field, an undeclared global) — that is T1's census and T10's propagation twin. COST: one pass over the rows at the cached `z`; on §4c's columns, vectorised, hypothesis ≤ 1 s at HECA's 4.3 M rows, reported in the `cache` block. It runs whenever the solve record is SERVED to a stage that reads `z`; #880's full skip serves nothing and so runs none. |
| **Not cached when** | `cfg.options.time_limit_s` is set (a time-limited answer is a function of the wall clock, not of the inputs); `Config.xplat_dump` is set (§7). |
| **A hit skips** | the solve proper: stage 1, 1a, 2, the projections, the HiGHS feasibility LPs (HECA: 376 s less the prefix it no longer contains). |

**Is the solve deterministic?** On ONE machine it is expected to be, and twin T7
measures it rather than assuming it:

- the design surface is scipy sparse (`splu`, `cg`, `lsqr`) plus HiGHS
  (`solve/project.py`, `solve/design_report.py`: QP/LP through `highspy`, no
  `threads` / `random_seed` / `parallel` option set — HiGHS's defaults run the
  serial dual simplex for an LP and the active-set QP, both deterministic for
  one model and one library build);
- `solve/design_qp.py` speculates the λ backoff on `ThreadPoolExecutor(2)` but
  READS THE RESULTS IN SUBMISSION ORDER (`_round`), so the answer is the
  sequential loop's;
- the residual hazard is multithreaded BLAS inside `splu`/`numpy`: its
  reductions are deterministic for a fixed thread count on one machine, which is
  what T7 checks (two cold builds, cache off, byte-identical patch). If T7 fails,
  the cache cannot promise "hit == cold" for the solve — that is a STOP and a
  finding for the owner (§14 Q3), not a tolerance.

ACROSS mac / Windows / Linux it is NOT deterministic and need not be: #813
showed GEOS last-bit arithmetic moving a classify cut before HiGHS is entered
(fixed by the §46 1 mm opening grid, but the class remains), and the
cross-platform gate compares stage digests on a rounding ladder
(`pipeline/xplat.py`), not bits. A cache entry is therefore PER MACHINE: it
lives in the user's data folder (17a Q1) and its key carries the environment
fingerprint (§4c), so a copied cache folder or a wheel upgrade misses.

### 4b.5 late_stage — cut, prefix, solve

`run_last_stages` becomes its documented three steps per pass (its module
docstring (i)–(iii)); with both gap pieces and pad roads there are two passes.

| Record | Output | Inputs | Code | Witnesses | A hit skips |
|---|---|---|---|---|---|
| `late.cut.<pass>` | the cut classification (`cut_classification`), stations, followers, `cut` report | `cl_gaps` (the classification `gap_free` split off), base `pm`, base `z` (the solve record's output digest), `Airport`, `load_rules()` digest; pass 2 adds pass 1's `late.solve` output digest | entry `late_cut`: `pipeline.late_stage` (cut half), `classify.gap_terrace`, `classify.gap_mint` | law rows | the cut (HECA 22 s) |
| derive | — | §4b.3: the prefix on the cut classification, through the cache | — | — | the derive (HECA 213 s) |
| `late.solve.<pass>` | final `pm` (the derive's `pm` + the follow rows' effects), `Solution`, `design`, `pin_yield`, `join`, `dropped`, `follow`, `followers`, `hard_conflict` (base merged with the late solve's), `hold_report` (the base solve's carried over the re-minted held registry, as `build.py` does today); `cs_full` and the derive's `ShapeStage` as REFERENCES (keys) to the derive's assembly and shapes records | the derive's record digests, base `z`, base `hard_conflict`, the `late.cut` output digest, `cfg.options` | entry `late_solve`: `pipeline.late_stage`, `constraints.gap_follow`, `solve.design` (+ the solve's callback modules) | law rows; THE CERTIFICATE as §4b.4 against `cs_full` | the late solve (HECA 17 s) |

`run_late_stage` is used by `tools/v2_solve_replay.py --late-from` too; the
split keeps one implementation for both.

### 4b.6 emit — the file bytes and what verify reads

| | |
|---|---|
| **Output record** | the BODIES of every file emit writes — patch `.osm`, sidecar `.axes.json`, tile pieces, `<ICAO>.graded.json`, `<ICAO>.rebake.screen.json` — each with its sha256; `surf` and `pub` (what verify reads; `pub` is the sidecar's content before serialisation); the emit-side report keys (`report["emit"]`, `["warnings"]`, `["shore_weld"]`, `["joint_steps"]`, `["off_dem_by_role"]`, the runway profile block, `road_profile_agreement`, `rebake_screen`). |
| **Inputs** | the final `pm` (late record, else shapes), final `z` and `design` (late record, else solve record), final constraint set (reference), `strips`, `hard_conflict`, `runway_flex`, `hold_report`, `Airport` (frame origin / CRS, pack name, cells — digested as a whole), `cfg.feather_m`. NOT `cfg.header_extra`: the hosting tile build's freshness stamps change on every commit, so emit renders the patch BODY and applies the header on every write, hit or miss (`write_patch` takes the rendered body and the header; T8 asserts the bytes on disk equal a cold build's). If that split is not clean, `header_extra` joins the key and emit misses whenever a stamp changes — measured and reported, not assumed. |
| **Code** | entry `emit`: `pipeline.emit_stage` (the post-solve glue moved out of `build.py`, §10 step 8), `pipeline.publication`, `emit.graded`, `emit.osm_adapter`, `emit.road_join`, `emit.terrain_edge`, `airport.rebake_screen`. |
| **Witnesses on read** | law rows read; each stored body re-hashes to its recorded sha256 before it is written (integrity of the payload). |
| **A hit** | writes the stored bodies to `out_dir` (temp + `os.replace`, the header applied to the patch), installs the report keys, and hands `surf`/`pub` to verify (loaded lazily — only a verify MISS unpickles them). Skips graded_surface, publication, the shore weld, `write_patch`, `write_tile_pieces`, the rebake screen (HECA ≈ 10 s; median 1.4 %). |

### 4b.7 verify — cached for the bytes it judged

**Should verify ever be served from cache?** Yes, under RULINGS 18b, with one
witness the other stages do not have. Verify is a READ of the emitted surface
(`census_frame(surf, law, pub, caps)` and `apron_over_preference`); it changes
nothing that ships. Served for exactly the inputs it judged — the same emitted
bytes, the same law rows, the same verify code — its verdict is the same
function of the same arguments. The risk a cached verdict carries is a key
that omits an input; T1's census closes that, and the record is refused
whenever the bytes on disk are not the bytes it judged.

| | |
|---|---|
| **Output record** | `report["verify"]` (by family, summary, defects, under-floor, `apron_over_preference`), the DEFECT and under-floor lines (re-printed verbatim on a hit, so `auto_patch/engine_v2.py`'s warnings and the UI read the same), the sha256 of the patch and sidecar BODIES it judged. |
| **Inputs** | the emit record's output digest (`surf`, `pub`), `caps` (`road_law_caps(pm, law)` + `lifted_caps`, i.e. `pm` digest), `cfg.verify`. |
| **Code** | entry `verify`: the `verify` package, `constraints.roads` (`road_law_caps`), `pipeline.publication` (`lifted_caps`). |
| **Witnesses on read** | law rows read; the patch and sidecar bodies NOW ON DISK re-hash to the bodies the record judged — a patch edited or rewritten by anything else since refuses the verdict. |
| **A hit skips** | the in-build census (HECA 18 s, OTHH 13 s, CYXY 1.8 s; median 2.2 %). |

The harness census (`tools/harness/census.py`, `check_grade.py`) is a
different instrument on the patch FILE and never reads this cache: every lane
and sweep measurement keeps its independent check. Making in-build verify
always run instead costs the 2.2 % median and buys nothing the witness above
does not; the owner may still prefer it (§14 Q2).

### 4b.8 report.json

`report.json` is assembled from the records; it is NOT byte-identical between a
cold and a hit build because `wall_s` and `pool` are clocks. It gains a `cache`
block: per record `hit` / `miss` / `refused: <reason>` / `bypass: <reason>`,
the key prefix, bytes read and written, and the miss arm's own cost
(`encode_s`, `digest_s`, `write_s`) — the figure RULINGS 17a Q2 judges.

## 4c. Chaining, digests and the environment

**Output-digest chaining (early cutoff).** A stage's key names its inputs by
the OUTPUT digest recorded in the producing stage's entry header, never by the
producer's key. A stage that re-runs (its code changed) and produces the same
record leaves every later key unchanged: comment-only edits, refactors and
no-op law edits stop at the stage they touched. The price is that every output
must be digested on the miss arm, which is why constraint rows need §4c's
codec.

**Columnar constraint rows.** Rows are frozen dataclasses (`Pin`, `Diff`,
`Flat`, `Band`, `Offset`, `Linear`, each with a `Source`). The record stores
them as columns: per kind, int32 vertex columns, float64 value columns (`None`
as NaN plus a mask), small-int indices into per-record string and `Source`
tables, and offset arrays for the ragged fields (`Flat.group`, `Linear.terms`,
tuple `follows`). Pickled at protocol 5 with out-of-band buffers; the digest is
sha256 over the buffers in a fixed order. Round trip is exact (float64 bits;
rows compare equal by value — no reader keys a row by `id()`, which T6 checks).
Hypothesis: HECA's 4.34 M rows encode + digest in ≤ 1 s and decode in ≤ 1 s
(objects: 3.3 + 3.0 s); measured by the codec landing (§10 step 7) before any
cache uses it. If the codec misses that, the constraint records fall back to
KEY chaining (the solve names the assembly by its key, not its output digest;
early cutoff then stops at the constraints); the records are still stored
with the codec, not pickle (RULINGS 2026-10-18e: measured at HECA, exact round
trip, 2.2 s write vs 3.2 s pickle, 36 MB vs 422 MB; decode 1.6–2.1 s misses
the 1 s target, so key chaining applies) — written by a writer thread (zlib
and file I/O release the GIL), the encode on the build thread. This fallback
is the codec lane's to report.

**Environment fingerprint.** `pipeline/xplat.environment()` already reports the
interpreter, platform and the bundled numerics (numpy, scipy, highspy, shapely,
GEOS, PROJ, BLAS). Its canonical digest is a component of EVERY stage key,
front half included: the code closure covers `auto_patch_v2` only (#842's
rule), and GEOS's last bit has moved a cut before (#813).

**The `Airport` digest** is taken once per build and shared by every record
that reads it. Pickling the whole `Airport` is 451 MB at HECA (0.31 s + 0.15 s
sha256); its DEM rasters should enter the digest by their file hashes and
witness samples instead (`airport/file_hash`, `dem_witness`), which is the
front-half lane's to settle (B3-11).

## 5. The law witness

E's weakness: a rule may read a parameter it did not declare. Our law is one
typed object (`law.tables`, `auto_patch_v2/law/model.py`; the TOML files hashed
by `law.tables.law_tables_digest`). Keying on the WHOLE law digest is safe and
simple, and is the FIRST landing. The witness refines it: during a cached stage
the `Law` object is wrapped in a recording proxy (`law/witness.py`) that records
every attribute path resolved (`tables.common.roles.apron.longitudinal`, …) and
every `ruleset.X` lookup; the record is stored in the entry's header and a read
holds only when every recorded path resolves to the same value today
(`dem_witness.holds` pattern). The witness never widens a hit: a path not
recorded is one the stage did not read. Rows added to a table the stage never
read do not invalidate it; a row it read, edited, does. Twin: a synthetic law
edit on a read row misses; on an unread row hits.

**The memo rule (amendment 2026-10-18).** The back half shares memos across
stages and generators (`routes._CACHE`, `stretches._CACHE`,
`precedence._CACHE`, `taxi._PAIR_CACHE`, … §3b). A memo filled while
generator A's recorder was active and then read by generator B (or by the
solve's callbacks) hands B a value computed from law rows B's witness never
saw: B's record would hit on a law edit that changes its rows. So a memo that
holds law-derived values stores, beside its value, the law paths recorded
while it was filled, and a memo HIT replays those paths into the active
recorder. One helper in `law/witness.py` (`memo_record` / `memo_replay`), used
by every such memo; T4 gains the case "generator B reads a memo A filled; a law
edit on a row only the memo read misses B". Until the witness lands, the
whole-law digest (above) is the back half's law key as well, and the memo rule
is moot.

## 6. Store

`auto_patch_v2/airport/stage_cache.py` beside `partition_cache.py`, same folder
(the pack's mod-cache folder under `O4_AIRPORT_MOD_CACHE_DIR` for lanes; for
the app, RULED by 17a Q1: under the user's data folder beside today's caches,
2 GB starting cap, oldest-first eviction, shown in the Library's cache cleanup
#824 — revisable by measurement), same discipline:

- `<mod-cache>/o4_stage_<ICAO>_<stage>_<key[:16]>.cache` — zlib-compressed
  pickle with a JSON header carrying the recipe (so `peek` can say why a key
  missed, field by field, as `partition_cache.peek` does), the witnesses and
  `CACHE_VERSION`;
- write = temp file + `os.replace`; a stale payload is refused, never repaired;
- a LAST-USED index file per airport for an LRU sweep with a size cap
  (default 2 GB per mod-cache root; owner Q1);
- `write_cache=False` paths (replays, tools) write nothing (the
  `topology_cache` rule); a build that HIT only reads;
- `O4_V2_STAGE_CACHE=0` turns it off (every stage runs); the default is on
  once the twins and the closing build are green. The variable is read in
  `auto_patch/engine_v2.py` and handed to the build as a `Config` field
  (`stage_cache: bool`), the `xplat_dump` pattern — `auto_patch_v2` reads no
  environment (`tests/auto_patch_v2/test_model.py`).

**Back-half additions (amendment 2026-10-18).**

- The JSON header is a length-prefixed first block, readable WITHOUT
  decompressing the payload. It carries `stage`, `key`, the recipe (`inputs`
  `{name: digest}`, `code`, `law_witness`, `env`, `version`), the witnesses,
  `output_digest`, `payload_sha256`, `created`, `last_used`. §7's walk (#880)
  reads headers only.
- A record may REFERENCE another by output digest instead of copying it (the
  late solve's `cs_full`, the assembly's generator rows). The assembly record
  stores only its DELTA over the concatenated generator rows: a kept-row bitmask
  over `concat(generator rows) ++ appended`, the appended rows (ceiling,
  pavement cap) and any row a post-pass replaced, by index. A referenced record
  that was evicted is a MISS of that record alone: it is recomputed, and the
  reference holds if the recomputed output digest equals the recorded one;
  otherwise the referencing record is refused.
- Payload integrity: `payload_sha256` is checked on every read; a mismatch is
  refused (and counted in the report's `cache` block).
- Eviction is oldest-`last_used` first over the whole root; a set of records
  written by one stage run carries one `last_used`.

Sizes per airport, zlib-1, measured 2026-10-18 where stated (HECA regL3 capture
and a constraints run on main 603c44e05; CYXY regL1 capture; emit bodies from
the shared data repo's `Patches/`):

| Record (per build) | HECA | CYXY | Basis |
|---|---|---|---|
| constraint rows, per prefix run (generators + assembly delta) | ≈ 55 MB (50 MB rows + ≈ 5 MB delta) | ≈ 1.5 MB | measured: 4,337,588 rows (50 MB) / 90,358 rows (1.4 MB) as pickled objects; delta estimated |
| prefix runs per build | up to 4 (base, ribbon-free, gap derive, pad-road derive) | 2 (no late stage) | `build.py`, `late_stage.run_last_stages` |
| front-half records of the extra prefix runs (planar `pm`, classification, shape stage) | ≈ 5.5 MB each | ≈ 0.6 MB each | measured: `pm` 2.4 MB, `stage` 2.6 MB, `cl` 0.45 MB at HECA |
| solve (+ late solve) | ≤ 5 MB each (`z` 45,258 × 8 B = 0.36 MB; `DesignReport` estimated) | ≤ 0.5 MB | estimate |
| late cut | ≤ 2 MB per pass | — | estimate |
| emit (bodies + `surf` + `pub`) | ≈ 12 MB (patch 1.1 + sidecar 5.2 + graded ≈ 0.4 + `surf`/`pub` ≈ 5) | ≈ 1.5 MB | measured bodies; `surf`/`pub` estimated |
| verify | < 1 MB | < 0.1 MB | estimate |
| **back half, one build** | **≈ 250 MB** | **≈ 7 MB** | |

OTHH, KCLT and SPJC are not measured here; their constraint sets set their
size (HECA's is 79 % one generator, `road_within_shape`). The landing reports
all five from the sweep's `cache` blocks. At ≈ 250 MB a HECA-class back half,
the 2 GB cap holds the front and back halves of roughly six such builds — §14
Q1.

## 7. Interactions

- **Freshness gate** (`driver._auto_patch_is_current`, `provenance_code`
  whole-tree `o4_code`): unchanged. Any commit still rebuilds every patch; the
  rebuild now hits on every stage whose code closure did not change.
- **Partition cache**: unchanged; the stage cache keys on its fingerprint and
  reuses `partition_cache.companion` / `hold_companion` for the classify
  entry (same lifetime rule: written with the partition, never alone).
- **`tools/v2_solve_replay.py`**: `--capture` pickles the same records the
  cache stores; once B3-11 lands, `--capture` MAY write the stage entries and
  `--replay --from constraints` MAY read them (B3-12, small). The refusal
  logic (`capture_state.missing/refusal`) stays; a cache entry without the
  registries record is a `missing()` refusal, by field name.
- **`stage_one_map`**: already collects/installs the record around the
  ribbon-free pass; it reads the record from the planar output instead of the
  live modules once B3-09 lands.
- **`O4_Step_Reuse`**: the vector step records the patch inputs; a patch
  rebuilt faster is still a rebuilt patch. No change.
- **Hard law**: the miss arm adds the digests (pickle + sha256 of a `PlanarMap`,
  hypothesis ≤ 0.5 s at OTHH) and one cache write per stage. Measured by
  `check_build_time.py --run HECA --runs 3` with the cache OFF vs the miss arm
  ON before landing; ≥ 0.6 s triggers the whole-pipeline review. (RULINGS
  17a Q2: judged on this COLD miss arm; warm/hit times are information.)

Back-half interactions (amendment 2026-10-18):

- **#880, per-airport freshness.** #880 replaces the whole-tree gate with a
  WALK over this cache's headers: from a LOAD MANIFEST (the load inputs' file
  digests — apt.dat stamp, pack, DSF dump, OSM extracts, DEM witness — and the
  load code digest, recording the `Airport` digest; #880's record, not this
  cache's, because the `Airport` itself is never stored) through every stage
  key in build order, each computed from the previous header's
  `output_digest`, each header's witnesses re-checked (law rows against today's
  law, DEM samples against today's DEM, the environment fingerprint). The
  airport is FRESH — skipped entirely, load included — when every key in the
  walk names a present entry whose witnesses hold AND the patch body on disk
  hashes to the emit record's patch digest AND verify's record judged that
  body. No payload is decompressed. The first key that misses is where the
  rebuild starts: load runs (its `Airport` is needed), every record before the
  miss is SERVED (decoded lazily, only where a later stage reads it), the miss
  and everything after it whose inputs change re-run. This spec supplies the
  header fields #880 needs (§6); #880 owns the manifest, the walk and the
  owner's confirmation of the trade (its issue body).
- **Partition cache.** Unchanged. The back half never reads it directly; the
  prefix re-runs call `build_planar(..., cache=ocache)` exactly as today and
  the planar entry keys on the partition fingerprint as in §4.
- **Stop and resume (17a Q3, #838).** The stage cache IS the commit point:
  each record is written when its stage ends, so a Stop during the solve
  resumes with every record up to the assembly served. A pack put back on Stop
  changes the partition fingerprint and so every key after it.
- **`Config.xplat_dump`** (the release cross-platform gate) BYPASSES the cache:
  the gate measures the programme, and a served record would compare caches.
  CI runners start empty anyway.
- **`cfg.verify = False`**: verify neither runs nor is served nor written.
  The walk asks for a verify record only when the caller builds with verify
  (the app always does).
- **`tools/v2_solve_replay.py`** (B3-12): `--replay --from emit|verify` against
  served solve/late records is the development loop an emit-only change wants
  (seconds instead of a solve). `--why-miss` prints the first differing recipe
  field per record (`peek`).

## 8. Tests and twins

- T1 `tests/auto_patch_v2/test_stage_registries.py`: the set of module-level
  mutable globals in `auto_patch_v2` read outside their defining stage equals
  the declared `REGISTRIES` fields plus the allow-list of memos/diagnostics
  (AST walk over `src/auto_patch_v2`; the census of §3 as a test).
- T2 `test_v2_capture_state.py` extended: the build's installed record equals
  `capture_state.collect()` taken at the stage boundary (hit arm == miss arm).
- T3 `test_stage_code_closure.py`: each stage's `ENTRY_MODULES` closure equals
  the declared list (both directions), the freeze digest reproduces.
- T4 `test_stage_cache.py` (synthetic airport, no corpus): miss → write →
  hit serves an equal record (`digest_of` equal); a code-digest change misses;
  a DEM sample change refuses by witness; a law row read changes → miss, a row
  not read changes → hit; `O4_V2_STAGE_CACHE=0` runs every stage; a newer
  `CACHE_VERSION` refuses.
- T5 digest stability: `digest_of(product)` equal across two subprocesses for
  the same synthetic product (sets, dict order).
- Replay twin: `tests/test_structure_replay_diff.py` pattern — a registered
  HECA capture (`tools/harness/frames.py list HECA`) replayed `--from
  constraints` with and without the cache produces identical rows/columns.

Back half (amendment 2026-10-18). Synthetic airport, no corpus, unless named:

- T1 EXTENDED: the AST walk covers `constraints/`, `solve/`, `emit/`,
  `verify/` and `pipeline/`; its allow-list is §3b's table. It fails on any
  cross-stage read of a module global not listed — `HARD_CONFLICT` and
  `RUNWAY_FLEX` leave the allow-list when they become record fields.
- T6 `test_generator_independence.py`: every generator's rows (columnar
  digest) are equal when it runs (a) in `GENERATORS` order, (b) alone in a fresh
  subprocess with every memo cold, (c) in a shuffled order; and the assembly of
  the per-generator records equals `generate()`'s set. No reader keys a row by
  `id()` (AST check over `solve/` and `constraints/`).
- T7 cold == cold: two cache-OFF builds of the synthetic airport in two
  processes, and the closing HECA build's control (a served `--base-arm`
  control is NOT a second cold run: the lane runs the second one with
  `--no-ledger`), are byte-identical (patch, sidecar, tile pieces, rebake
  screen). The precondition of every "hit == cold" claim; on failure, STOP
  (§14 Q3).
- T8 hit == cold: a build through EVERY hit equals a cold build byte for byte
  (patch, sidecar, tile pieces, graded, rebake screen; `report.json` minus
  `wall_s`, `pool`, `cache`). Then the same with ONE stage forced to miss, for
  each back-half stage in turn (emit-only, verify-only, solve-only,
  one-generator, assembly-only, late-only).
- T9 planted stale entries, one per back-half record type, each REFUSED on
  read with its named reason: (a) a header whose recipe differs from the
  requested key in one field (older code digest; other law witness) → refused
  `recipe:<field>`; (b) a payload altered under an intact header →
  `payload_sha256`; (c) a solve record whose `z` moved 0.01 m at one vertex
  with header and payload hash rewritten to match → refused by the
  CERTIFICATE; (d) an emit record whose stored body no longer hashes to its
  recorded sha → refused; (e) a verify record while the patch on disk was
  edited after it → refused by the body witness; (f) an evicted generator record
  referenced by an assembly → that generator re-runs and the assembly holds iff
  its digest matches.
- T10 code-change propagation: for each stage S (front and back half),
  monkeypatch S's code digest. (a) A change that leaves S's output identical:
  S re-runs, every stage before S and after S hits. (b) A change that alters
  S's output: S and every stage after S whose inputs changed re-run, every stage
  before S hits. Counted from the report's `cache` block.
- T11 environment: a changed `environment()` digest misses every record.
- T12 bypasses: `Options(time_limit_s=…)` → solve `bypass: time_limit`;
  `Config.xplat_dump` → every record `bypass: xplat`.
- T13 resume (#838): a build stopped after the assembly record is written
  restarts with every record up to the assembly served and the solve run.
- T4 gains the memo case of §5 and the per-generator law-row case (an edit on a
  row read by generator A only misses A's record and hits the rest).

## 9. Acceptance and rollback

Acceptance: (1) patch `.osm` and `.axes.json` sha256-identical between the
miss arm and the hit arm on the closing airport (HECA) and on CYXY; (2) hit-arm
`wall_s` for classify+planar+shapes near zero, `total` reduced by the stages'
share (reported, hypothesis 40–70 %); (3) miss-arm `total` within 0.6 s of the
cache-OFF arm (median of 3) or reviewed; (4) `tools/ratchets.py` green; (5)
T1–T5 green; (6) `tools/INDEX.md` row for `stage_cache.peek` if exposed as a
tool subcommand (extend `v2_solve_replay --why-miss` rather than a new tool).

Back half: (7) T1 (extended), T6–T13 green; (8) on HECA (closing) and CYXY:
cold, full-hit and the six single-miss arms of T8 byte-identical (patch,
sidecar, tile pieces, graded, rebake screen); the full-hit and emit-only-miss
`wall_s` reported as information (17a Q2); (9) the miss arm's cost from the
`cache` block (`encode_s + digest_s + write_s`, all records) reported per
airport, ≥ 0.6 s triggering the whole-pipeline review, judged on the cold
miss arm against cache-OFF (`--runs 3`, `--no-ledger`).

Rollback: `O4_V2_STAGE_CACHE=0`, then `git revert` of the landing; cache files
are derived data and may be deleted at any time.

## 10. Landings (one lane each)

1. B3-08 — registries become the planar stage's output record: `build_planar`
   returns `(pm, pstats, state)`, `build` installs `state` explicitly before
   the shape stage, T1 + T2. No cache yet; replay == build by construction.
2. B3-09 — readers take the record: `constraints/{platform,no_step,
   jetway_strip,pads,ramp_runout,pad_fronting}` and `pipeline/publication`
   receive a `Registries` argument; the module globals are deleted; `stage_one_map`
   and `capture_state` read the record. Split per registry group if the diff
   passes ~600 lines.
3. B3-10 — `stage_code.py` + closure twin + freeze digest.
4. B3-11 — `stage_cache.py`, the law witness, digests, T4/T5, the closing build.
5. B3-12 — `v2_solve_replay` reads/writes the stage cache (optional, small).

Back half (amendment 2026-10-18; all under #843 unless the master files them
apart; steps 6–8 are byte-identical refactors that can run in parallel with
step 4, step 9 needs 4 and 6–8):

6. B3-11b — the solve's side channels become record fields:
   `feasibility.HARD_CONFLICT` and `no_step.RUNWAY_FLEX` are deleted as module
   globals; `solve_design` returns them (on `DesignReport`), `run_late_stage`
   takes and returns `hard_conflict`, `publication` takes both as arguments; the
   hold report is returned, not only written into `registries.held`;
   `capture_state`'s census row and T1's allow-list updated. Gate: patch +
   sidecar byte-identical on HECA and CYXY (one shared solve/emit-path change:
   the OFF-arm byte identity is required here, BUILD ECONOMY).
7. B3-11c — the columnar `ConstraintSet` codec (`model/constraint_codec.py`):
   encode/decode/digest, round-trip twin over every row kind, the HECA timing of
   §4c reported. Decides output-digest vs key chaining for constraint records.
8. B3-11d — named stage functions: `pipeline/prefix.py` (`run_prefix`, replacing
   `build()`'s `_ribbon_free` closure and the replay tool's copy),
   `pipeline/emit_stage.py` (the post-solve glue and emit), `pipeline/
   verify_stage.py`; `late_stage.run_last_stages` split into cut / derive /
   solve; `water_exempt`/`seam_exempt` to `constraints/assembly.py`. `build.py`
   shrinks to the sequence. Byte-identical; replay twins green.
9. B3-11e — the back-half records: `stage_code.ENTRY_MODULES` gains
   `constraints.<generator>` (57), `constraints.assembly`, `jetway_strip`,
   `solve`, `late_cut`, `late_solve`, `emit`, `verify` (closure twin extended);
   the records of §4b, the certificate and body witnesses, the environment
   fingerprint, the memo rule (if the witness has landed), T1/T6–T13, the
   closing HECA build and CYXY. Split constraints+jetway / solve+late /
   emit+verify if the diff passes ~600 lines.

#880 (per-airport freshness) follows step 9 and consumes §6's headers and §7's
walk.

## 11. Out of scope

Caching the load stage (its `Airport` carries the DEM rasters; #880's manifest
records its digest instead); storing the LP matrix or any solver-internal
state (the solve record is its answer and its certificate); sharing cache
entries across machines or platforms (per-machine by construction, §4b.4); a
tolerance in "hit == cold" (a solve that is not deterministic on one machine is
a finding, not a tolerance); a scheduler or critical-path ordering (we have
`tile_time_model` and finish-first dispatch); E's SQLite index (a per-airport
JSON index suffices at our entry counts); any change to law, solve or emitted
geometry; the freshness gate's keying (#880 owns it); the size of
`road_within_shape`'s row population (3.4 M of HECA's 4.3 M rows — a solve-cost
question, not a cache one).

## 12. Expected effect (hypothesis)

From the median shares of §1's table (front 28.3, constraints + jetway 6.0,
solve 39.0, late_stage 23.4, emit 1.4, verify 2.2 %) and HECA's seconds. A
rebuild after a change of the named kind; "load" (≈ 1–4 % of the wall, inside
"front") runs on every rebuild that misses anywhere. Hypotheses until T8's arms
and the closing build measure them; reported as information beside the cold
miss arm (17a Q2).

| Change confined to | What re-runs | Rebuild, median airport | HECA (806.8 s cold) |
|---|---|---|---|
| nothing (re-run; #880 walk) | nothing | ≈ 0 % (header walk) | < 1 s |
| verify code | load, verify (+ decode `surf`/`pub`, `pm`) | ≈ 4–6 % | ≈ 25 s |
| emit code | load, emit, verify (+ decode `cs`, `pm`, `z`) | ≈ 6–9 % | ≈ 40–45 s |
| the late stage (cut or late solve) | load, late cut + late solve (derives SERVED from the prefix records), emit, verify | ≈ 10–15 % | ≈ 75 s |
| the solve | load, solve (its stage-one prefix SERVED), late stage (its derives re-run only if the base `z` changed — they read it through the cut), emit, verify | ≈ 55–70 % | ≈ 450–620 s |
| one generator, rows unchanged | load, that generator ×(1–4 prefix runs); everything after hits by early cutoff | ≈ 3–8 % | ≈ 10–65 s (`junction_mesh` × 4 is the worst) |
| one generator, rows changed | that generator ×4, the assembly ×4, solve, late (cut + derive constraints + late solve), emit, verify | ≈ 67–70 % (front 28 % and the other generators' share saved) | ≈ 700 s |
| a law row, first landing (whole-law digest) | everything | 100 % | 806 s |
| a law row, with the §5 witness | the stages and generators that read it, then everything whose inputs changed | between "one generator" and "the solve" | — |

The ruling's "~33 %" was constraints + solve on the 09-30 shares (19.6 +
13.0). On the 10-16/17 shares the back half is ≈ 70 % of the median wall, so a
change confined to emit or verify saves ≈ 90 % of a rebuild, not a third. The first landing's law key makes every law edit a full rebuild; the
witness is where law-iteration speed comes from.

## 13. Files and blast radius (amendment 2026-10-18)

`tools/blast.py` on main 603c44e05, 2026-10-18 (importers / tests / hazards):

| File | Change | Importers | Hazards blast names |
|---|---|---|---|
| `src/auto_patch_v2/pipeline/build.py` | shrinks to the stage sequence; reads/writes records | 29 (4 src, 22 tests, 3 tools) | role literal `runway`; co-changes `v2_why.py`, `api.py`, `road_join.py`, `terrain_edge.py` |
| `src/auto_patch_v2/constraints/__init__.py` | `generate` per-generator records; post-passes to `constraints/assembly.py` | 100 (2 src, 95 tests, 3 tools) | `GENERATORS` (14 users), `generate` (69) — signature kept |
| `src/auto_patch_v2/pipeline/shapes.py` | `shape_constraints` takes the records | 9 | — |
| `src/auto_patch_v2/solve/design.py` | returns `hard_conflict`, `runway_flex`, `hold_report` | 56 (20 src, 34 tests, 2 tools) | `DesignReport` (9), `solve_design` (4) |
| `src/auto_patch_v2/solve/feasibility.py` | `HARD_CONFLICT` global deleted | 11 | `HARD_CONFLICT` (3 users: `late_stage`, `publication`, `v2_solve_replay`) |
| `src/auto_patch_v2/constraints/no_step.py` | `RUNWAY_FLEX` global deleted | 20 | role literal `runway`; `hold_pass` (9) |
| `src/auto_patch_v2/pipeline/late_stage.py` | cut / derive / solve split; `hard_conflict` explicit | 9 | role literal `apron` |
| `src/auto_patch_v2/pipeline/publication.py` | takes `hard_conflict`, `runway_flex` | 49 (1 src, 47 tests, 1 tool) | role literals `apron`, `tunnel_ramp`; `publication` (27) |
| `src/auto_patch_v2/emit/osm_adapter.py` | `write_patch` takes a rendered body + header | 35 (3 src incl. `O4_Qt_Patch_Geometry.py`, `patch_file.py`) | `write_patch` (13), `SIDECAR_KEYS` (7); role literals `apron`, `runway` |
| `src/auto_patch_v2/verify/census.py` | unchanged API; called from `pipeline/verify_stage.py` | 32 | `DEFECT_KEYS` (12) |
| `src/auto_patch_v2/pipeline/stage_code.py` | back-half `ENTRY_MODULES` | 1 (its twin) | runpy-loaded by both `.spec` files (stdlib only, no relative import) |
| `src/auto_patch_v2/pipeline/stage_one_map.py` | calls `run_prefix` | 15 | `stage_one_problem` (4) |
| `src/auto_patch_v2/model/constraints.py` | unchanged; the codec is a new module beside it | 142 | — |
| `src/auto_patch/engine_v2.py` | reads `O4_V2_STAGE_CACHE` → `Config.stage_cache` | — | engine ↔ app wire names are untouched (no event renamed) |
| `tools/v2_solve_replay.py` | `run_prefix`; reads `hard_conflict` from the record; B3-12 cache read/write | — | its `tools/INDEX.md` row |
| NEW `pipeline/prefix.py`, `pipeline/emit_stage.py`, `pipeline/verify_stage.py`, `constraints/assembly.py`, `model/constraint_codec.py`, `law/witness.py` (front half) | — | — | each a new module with one responsibility (RULINGS 2026-10-04 a/b/c) |

## 14. Open questions for the owner

1. **Cap.** A HECA-class back half is ≈ 250 MB (§6), so the 2 GB cap (17a Q1)
   holds about six such airport builds, front and back. Keep 2 GB and let
   eviction work (recommended; Q1 already says "revisable by measurement" —
   revisit with the sweep's measured sizes), or raise it now?
2. **Verify.** Cached for the bytes it judged (§4b.7, recommended under 18b), or
   always run (+2.2 % median, 18 s at HECA)?
3. **Only if T7 fails** (two cold builds on one machine differ): pin solver and
   BLAS threads to one (slower solve, deterministic) or restate the twin as
   "a hit equals the cold build that wrote it". Not asked unless measured.

## Licence

Design re-implemented from E's `graph-keys.md` ideas and our own caches; no E
code copied. Lives under `Ortho4XP/` (GPL-3).
