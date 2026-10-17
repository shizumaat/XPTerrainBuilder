# v2 per-stage content-keyed cache — spec (2026-10-17, Beta 3 W4)

Status: PROPOSAL. Plan: `beta3-build-speed-plan-20261017.md` W4. Issues: manifest
B3-08 … B3-12. Prior art: E `docs/specs/graph-keys.md` (content-keyed artefact
store); our own `auto_patch_v2/airport/partition_cache.py` (issue #362, #382),
`topology_cache.py`, `extension_cache.py`, `dem_witness.py`,
`pipeline/capture_state.py`.

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
| `solve.feasibility.HARD_CONFLICT`, `constraints.cluster_pad.{YIELDED,…}`, `no_step.RUNWAY_FLEX` | after the cached stages | `pipeline/publication` | produced by the uncached half — unaffected |
| `partition_cache._TAKEN/_HELD/_STAMPS/_DEMS` | partition | companions | the partition cache's own bookkeeping; the stage cache's companions use `partition_cache.companion` the same way |

A new module global in `auto_patch_v2` that a later stage reads is a defect
this spec's twin (§8 T1) catches: the census is executable.

## 4. The stages and their keys

Cached stages, in order, with the inputs each is a function of:

| Stage | Output record | Inputs (digested) | Witnesses (checked on read) |
|---|---|---|---|
| partition | (exists) | pack content, dump, law, frame, code | DEM samples (`dem_witness`) |
| classify | `Classification` | `Airport` digest (post-partition), rules digest (`classify.load_rules()`), `classify` code digest | law rows read (§5) |
| planar | `PlanarMap`, `pstats` (minus diagnostics), registries record (`capture_state.collect()`), `objects_out` | `Classification` digest, `Airport` digest, pack objects digest (`pack_report`), `planar` code digest | DEM samples; law rows read |
| flat_site, road_profile, shapes | their records (`ShapeStage`, …) | `PlanarMap` digest + each one's code digest | law rows read |

Not cached: load (reads apt.dat, CIFP, DSF dump, OSM, DEM — the freshness gate
already prices it; 6.4 % median), ramp_feet (reads the resource cache, 1 s
class), constraints, solve, late_stage, emit, verify (the half that a law or
solve change invalidates by definition).

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

## 6. Store

`auto_patch_v2/airport/stage_cache.py` beside `partition_cache.py`, same folder
(the pack's mod-cache folder under `O4_AIRPORT_MOD_CACHE_DIR` for lanes;
owner Q1 on the app's root), same discipline:

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
  once the twins and the closing build are green.

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
  ON before landing; ≥ 0.6 s triggers the whole-pipeline review.

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

## 9. Acceptance and rollback

Acceptance: (1) patch `.osm` and `.axes.json` sha256-identical between the
miss arm and the hit arm on the closing airport (HECA) and on CYXY; (2) hit-arm
`wall_s` for classify+planar+shapes near zero, `total` reduced by the stages'
share (reported, hypothesis 40–70 %); (3) miss-arm `total` within 0.6 s of the
cache-OFF arm (median of 3) or reviewed; (4) `tools/ratchets.py` green; (5)
T1–T5 green; (6) `tools/INDEX.md` row for `stage_cache.peek` if exposed as a
tool subcommand (extend `v2_solve_replay --why-miss` rather than a new tool).

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

## 11. Out of scope

Caching the load stage or the constraint/solve/emit half; a scheduler or
critical-path ordering (we have `tile_time_model` and finish-first dispatch);
E's SQLite index (a per-airport JSON index suffices at our entry counts); any
change to law, solve or emitted geometry; the freshness gate's keying.

## Licence

Design re-implemented from E's `graph-keys.md` ideas and our own caches; no E
code copied. Lives under `Ortho4XP/` (GPL-3).
