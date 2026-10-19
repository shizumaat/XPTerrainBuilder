# #843 step 9a (B3-11e, part 1 of 3): merge 6+8, back-half record infrastructure, constraints + jetway_strip records

Branch `claude/project-thread-g7d6rw-843-backhalf`, worktree `/home/user/wt-843-backhalf`.
The worktree is MID-MERGE: it is #960's head (step 8, named stages) with #959's
head (step 6, `HARD_CONFLICT`/`RUNWAY_FLEX` become `DesignReport` fields)
merged in; `pipeline/build.py` and `pipeline/late_stage.py` conflict.

First: resolve the merge. Step 6's semantics win (no module globals: the
lists travel on `DesignReport` / `run_late_stage`'s report / publication
kwargs), placed in step 8's new homes (`late_solve`, `emit_stage`, `prefix`,
`verify_stage`). grep the whole tree for `HARD_CONFLICT`, `RUNWAY_FLEX`,
`feasibility.publish` afterwards: none may remain outside comments. Run the
twins both branches touched (`test_nearmiss148`, `test_roads609`,
`test_joinyield128`, `test_facade_mint`, `test_stage_registries`,
`test_stage_code_closure`, late-stage / publication / replay twins) and commit
the merge before any new work. Push.

Then build the shared back-half infrastructure and the first records
(spec `v2-stage-cache-spec.md` §4b intro, §4b.1, §4b.2, §4b.3, §4c, §6
"Back-half additions", §8 T1/T6/T9(a,b,f)/T10/T11, §10 step 9):
- `stage_code.ENTRY_MODULES` gains `constraints.<generator>` (one per
  `constraints.GENERATORS` entry, keyed by closure of `fn.__module__`),
  `constraints.assembly` (`constraints/assembly.py` + `pipeline.shapes` per
  §4b.1), `jetway_strip`; closure twin extended. Also declare (empty records
  for now are NOT wanted — only add entries for stages you implement).
- The environment fingerprint (`pipeline/xplat.environment()` canonical
  digest) in EVERY stage key, front half included (§4c). This changes every
  front-half key once — say so.
- Store additions in `airport/stage_cache.py` (§6 back half): length-prefixed
  JSON header readable without decompressing (stage, key, recipe, witnesses,
  `output_digest`, `payload_sha256`, created, last_used); payload sha checked
  on every read (refused `payload_sha256`); references by output digest; one
  `last_used` per stage run. Keep `peek`/`why_miss`/`first_difference` working
  (#961 adds them on another branch — if absent here, do not add them; keep
  the header compatible so they merge).
- Constraint records with the PR #918 codec (`model/constraint_codec.py`),
  never pickle (RULINGS 18e), KEY chaining for constraint records (18e:
  decode misses 1 s, so the solve names the assembly by key). Per-generator
  records + the assembly record storing only its DELTA (§6), and the
  `ShapeStage` drop fields installed on a hit (§3b row `apply_joints`).
  `constraints.STATS` slice is a record field (§3b).
- `jetway_strip` record.
- Every prefix run (main, ribbon-free, late derives) reads/writes these
  records through `run_prefix`'s cache argument, keyed by its own `pm` (§4b.3).
  Prefix re-runs may now also go through the front-half records — that is the
  spec's ruling (§4b.3), do it.
- Law key: whole-law digest (first landing; the §5 row witness is out of
  scope here — say so in the report).
- `report["cache"]` block per record: hit / miss / refused: reason / bypass,
  key prefix, bytes, encode_s / digest_s / write_s (§4b.8).
- `Config.xplat_dump` → every record `bypass: xplat` (T12 half).
- Twins (synthetic, no corpus): T1 extended (AST over constraints/, solve/,
  emit/, verify/, pipeline/), T6 generator independence, T8 for these records
  (build through every constraints/jetway hit == cold, byte for byte), T9 (a)
  (b) (f), T10 for constraints and jetway, T11 environment.
Leave for parts 9b (solve + late_cut + late_solve, certificate) and 9c (emit +
verify, body witness, header_extra split) — other lanes start from your pushed
head, so keep the record/registration API small and documented
(one function a later stage calls to read-or-run a record).
Gate (master, corpus): HECA + CYXY cold vs full-hit byte-identical; miss-arm
`encode_s+digest_s+write_s` from the cache block.
