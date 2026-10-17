# OrthoStudio XP comparison: scout findings (2026-10-17, master session)

External repo (GPL-3, public): radioharris/orthostudio-xp, shallow clone at
`/tmp/claude-0/-home-user-XPTerrainBuilder/dfafed76-f111-5337-af1b-ea9cb70680a1/scratchpad/ext/orthostudio-xp`
(called E). Three Opus scouts read it against our tree, read-only. Nothing was built or timed:
there is no corpus or X-Plane in this container. All E timings are E's own docs, measured against
upstream Ortho4XP on a Mac (nvcompress under Rosetta). Scout claims about our code are unverified
until you check them. Paths without a prefix are under `Ortho4XP/`.

## 0. Scope and size
- E: 62k src lines / 173 files, tests 63k. Ours: Ortho4XP/src 270k / 554 files (auto_patch_v2 135k,
  auto_patch 42k, elevation_access 13k, o4_engine 9k), tests 241k, tools 88k, Swift 19k, md 218k.
- E's airports (airports_vec 3.4k + vectors 6k) are a faithful port of Ortho4XP's O4_Airport_Utils:
  OSM aeroway only, DEM blur + degree-7 centreline fit, "runways are not flat"
  (E docs/benchmarks/p4-airports.md §2.4). No grading law, no solve/verify, no pack-object seating.
  Their only new airport rule is `aerodrome-dry` (water inside an aerodrome becomes land).
  Verdict: most of our 4x is scope, not bulk.
- E's speed thesis (E ADR 0003): ~90 % of the gain is orchestration (graph, cache, pools,
  binary intermediates, in-process encoding), not language.

## 1. Orchestration / caching (largest payoff)
E mechanism:
- Key = blake3 of canonical JSON {format, rule, hand-bumped int version, declared params only
  (frozen pydantic, extra=forbid), content digests of inputs} (E src/orthostudio/graph/keys.py:21-57,
  canon.py, rule.py:97-147, executor.py:210). No timestamps; early cutoff for free (same bytes
  upstream -> same downstream keys). Store `<root>/<rule>/<key[:2]>/<key>` + SQLite WAL index,
  atomic tmp-dir rename, why/explain/gc/fsck (store.py). Asyncio scheduler, ProcessPool cores-2,
  named lanes (overpass 1, relief 1, network 1, disk 2, RAM 60 %), critical-path ordering with
  moving-average costs (sched/). Resume after stop = instant up to first missing node.
- E weaknesses: code identity is only a hand-bumped int (no check); nothing catches a param a rule
  reads but does not declare; it already failed once (tile missing from key: +43+004 served
  +43+005's vectors, E docs/benchmarks/p2-build.md:99-103).
- E numbers: no-op rebuild 0.01 s (0.29 s CLI) vs Ortho4XP 63 s; masks_width change 8.2 s vs 49.9 s.

Ours:
- Tile phases sequential per tile (src/o4_engine/session.py:1228-1256); DSF/imagery threads overlap
  (src/O4_Tile_Utils.py:431-472). Tiles in parallel processes, network classes capped
  (src/o4_engine/parallel.py:1-46); process pool over airports (src/auto_patch/config.py:1290-1298);
  per-stage pool inside an airport (src/auto_patch_v2/airport/pool.py). Parallelism is comparable.
- Step reuse (#615, src/O4_Step_Reuse.py): vector/mesh/masks only, never DSF/imagery (:63); keyed on
  O4_Cfg_Vars subset + engine version + WHOLE-TREE code digest + auto-patch config digest (:211-215),
  the previous step's RECORD digest, not its output content (:269-274), outputs identified by
  path/size/mtime (src/auto_patch/provenance.py:663-678). A stopped build commits nothing.
- Patch freshness gate (src/auto_patch/driver.py:448-516) uses one digest over every .py/.toml under
  src (src/auto_patch/provenance_code.py:10-16): ANY commit stales every patch and reused step, so a
  no-op rebuild never hits during development. Import closure of the patch build already reaches
  402/437 modules (provenance_code.py:12-15).
- Only in-airport cache: pack-partition cache keyed on per-stage CODE_MODULES, law tables, pristine
  inputs, DEM witness checked answer-by-answer on read (src/auto_patch_v2/airport/partition_cache.py:
  15-84); 298 of 841 s at OTHH. Also topology_cache.py, extension_cache.py.
- tools/v2_solve_replay.py --capture/--replay shows the hazard: module-level registries (HELD,
  PLATEAUS, PLATFORMS, TERRACES, PAD_AIRSIDE) read empty on replay -> KCLT 65,212 vs 49,981 rows
  (#224), HECA 822 vs 108 (#208) (:27-36).
- Time split (code-comment figures, src/auto_patch/engine_v2.py:70-84): ~26 min OTHH, 75 % in
  partition+structures+planar. Median over five airports: load 6.4 %, partition 13.5 %,
  classify+structures 17.0 %, planar 9.9 %, constraints 19.6 %, solve 13.0 %, emit+verify 17.1 %.
  v2 stage times live in `<ICAO>.report.json` wall_s (tools/check_build_time.py:24-32);
  ~/.ortho4xp/auto_patch_build_times holds only v1 labels. Budgets: <=60 s/airport, <=300 s/tile
  (Ortho4XP/CLAUDE.md item 6). Related issues: #412, #803, #579, #149.
Ranked adoptions:
1. Content-keyed per-stage cache for auto_patch_v2 (load, partition, classify, planar; key = stage +
   per-stage code digest + law-table rows read + input digests); a law/solve change reruns only
   constraints/solve/emit (~75 % skipped at OTHH, estimate). Prereq: capture_state registries become
   explicit stage outputs. Keep witness-on-read; twin test replay == build byte-identical.
2. Early cutoff in O4_Step_Reuse: key on predecessor OUTPUT content hash (blake3 over mmap, E
   digest.py:271-275), not record digest + stat identity.
3. Per-step code identity (CODE_MODULES-style closure per step, held by a closure test) instead of
   whole tree. Big payoff for DSF/imagery/mesh/masks, small for vector/patch.
4. Reuse the DSF step; DDS per-texture cache keyed on content (E: colour change 13.9 s; neighbours
   share textures). Check whether Ortho4XP already skips existing DDS by name.
5. Resume mid-build (commit each finished step).
6. Store tooling (why/explain, gc, plan()). 7. Critical-path scheduler: low (we have
   tile_time_model, finish-first dispatch, mid-flight class change).
We do better: source digest (no hand bump), witness-on-read, pristine-input rule
(provenance.py:692-703), ledgered data refreshes, three nested parallel levels with memory bounds,
build-time budget tooling.

## 2. Data-heavy kernels
1. Texture conversion. Ours: DDSTool universal binary, native on arm64 (src/O4_Imagery_Utils.py:
   199-202, 2902-2908), cores-2 threads launching subprocesses (src/O4_Parallel_Utils.py:240-252,
   O4_Tile_Utils.py:500-512). Textures with a colour filter / harmonisation / mask are re-saved as a
   full PNG at Pillow's default compression then converted (O4_Imagery_Utils.py:2839-2844, 2886-2893;
   master spot-checked: `big_image.save(file_to_convert)` with no compress_level).
   (a) compress_level=1 on that temp PNG: identical pixels, identical DDS, one line; E measured the
   PNG save at ~0.75 s per texture. (b) In-process ispc_texcomp BC1/BC3, numpy assembly, linear-light
   gamma-2.2 mips, process pool (E textures/assemble.py, mips.py:124, encode.py; 0.33 s/texture,
   6.8x on 12 workers, E docs/benchmarks/dds-encoder.md). Changes DDS bytes: owner sim read needed.
   Gain over DDSTool unknown (their 1.15 s baseline was Rosetta nvcompress).
2. Mesh I/O. Ours: per-line Python text parse at O4_Mesh_Utils.py:917, 985, 1013, 1511, 2128,
   post_process_nodes_altitudes 2242-2278, write_mesh_file `{:.15f}` 2584-2635, O4_Mask_Utils.py:
   1088-1113. Utils/src/Triangle4XP.c has the same base as E's (Feb 21 2024). E: binary -b I/O patch to
   Triangle4XP readers/writers only (E native/triangle4xp/CHANGES.md 5-10, ADR 0004), mesh step
   8.51 -> 2.79 s. Do first: one shared numpy reader/writer (text .mesh kept byte-identical — the
   auto_patch mesh sampler and masks read it); then binary Triangle I/O behind a flag with a
   text==binary byte-identity twin. Needs binaries for mac/win/linux.
3. Imagery download. Ours: requests, 16 threads/orthophoto (O4_Imagery_Utils.py:1571-1577) x 2
   orthophotos (O4_Parallel_Utils.py:255-271) ~ 32 in flight; Bing plain http host
   `http://r{0-3}.ortho.tiles.virtualearth.net ... g=136` (Providers/Global/BI.lay:2); a 429 falls to
   "Unmanaged Server answer" and the piece fails (O4_Imagery_Utils.py ~1245, master spot-checked);
   2 s fixed sleeps, 10 s timeout (:60). E: curl_cffi AsyncSession HTTP/2, AIMD per host group
   (start 64, cap 128, +1 per success round, halve on 429/503/latency spike, x0.75 on timeout,
   Retry-After obeyed), hedge a request after 3 s, https `ecn.t{0-3}` Bing host, no-imagery detected by
   `X-VE-Tile-Info: no-tile` (E net/fetch.py:3-30, 365-370; ADR 0005; docs/benchmarks/network.md):
   1,436 vs 222 req/s. Order: 429/Retry-After, https host, then async HTTP/2 fetcher. Preserve
   per-provider max_threads, authenticated sessions, the 1033-byte placeholder test (:1205-1208).
   Payoff only on a cold image cache (warm 4096² JPEG cache reused, :1978). Related: #622.
4. DSF encoder: already partly vectorised (O4_DSF_Utils.py:34-64, 1965); per-triangle loops remain at
   :868, 1320, 1574; build_dsf runs beside downloads (off critical path when cold). Byte-identical gate.
   Low/unknown payoff; measure first.
5. Masks: we already run 2-12 threads (O4_Mask_Utils.py:69, 438); remaining cost is the mesh read
   (fixed by 2). Exact distance transform for the 3-steps GaussianBlur loop (:1414-1425) changes
   output: low priority.

## 3. Code quality
- Duplicate v1/v2 readers (~6.2k v1 lines, live callers): apt_dat_reader.py 1,976 vs
  auto_patch_v2/airport/apt_dat.py 823; dsf_reader.py 2,485 vs airport/dsf.py 661 (ratchet already
  flags dsf_reader.py:1136 vs airport/dsf.py:603); obj8_reader 587 vs obj8 1,518; cifp_reader 252 vs
  cifp 168; flat_site 892 vs 486. Callers: tools/harness/build_airport.py (apt_dat_reader),
  O4_Airport_Elevation_Insets.py + o4_engine/patch_commands.py (cifp_reader), flat_site_mode.py
  (flat_site), 4 src + 8 tools (dsf_reader). NOT in #740's plan; fold in as a wave.
- v1 post_mesh/object_anchor arms "BELIEVED unreached" (#740 wave A covers), 316 unused exports
  (#740 B), src/Unused 806 + tools/attic 4,108 (#740 C covers Unused; attic not mentioned).
- tools/check_grade.py 14,715 lines (+922 since baseline), run_checks 1,215 lines.
- Long functions: ours 124 over 200 lines vs E 5. Longest: O4_DSF_Utils.py:814 build_dsf 1,349;
  object_anchor.py:2346 structure_deltas 1,240; check_grade.py:13422 run_checks 1,215;
  auto_patch_v2/pipeline/build.py:645 build 1,046.
- CI: ours has no ruff/format step (.github/workflows/ci.yml: pytest + swift only). E runs ruff check
  + ruff format --check + pytest -n auto (E .github/workflows/ci.yml:33-37); E's mypy config is not
  enforced (don't copy that).
- E coded error registry: errors.py 149 ErrorSpec, DOMAIN_SNAKE codes, severity + scheduler action,
  test_errors_registry.py. Ours partial: o4_engine/failure_report.py:30 (code/what/why/remedy) on
  BuildDone.failures (wire protocol: events.py class names are JSONL wire names).
- E ADRs: 13 one-page Context/Decision/Consequences, never rewritten, superseded. Ours: RULINGS.md
  append-only 9,983 lines. Suggest an ADR per owner standing decision, RULINGS links to it.
- E oracle fixtures vs Ortho4XP reference output (node/edge/byte). Ours has census/oracle for airport
  law but no frozen reference for the inherited O4_* vector/mesh/DSF stages.
- Docs: 218k md lines; superseded handover/plan files at Ortho4XP/docs top level beside docs/archive.

## 4. Licence (keep out of public issues; docs only)
Ortho4XP/ is GPL-3 (LICENSE, LICENSING.md:18-19): E code may be copied INTO Ortho4XP/ only, never
Sources/, tools/, scripts/ (MIT). E NOTICE adds GPL s7 attribution terms that travel with copied code.
Triangle4XP changes stay under Triangle's licence (LICENSING.md:51). Recommendation: re-implement
ideas from E's specs rather than copy files. ispc_texcomp / curl_cffi wheel licences unchecked.
