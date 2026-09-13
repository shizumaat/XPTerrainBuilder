# Brief pack — lane `dsfaudit`

Base: main `ed0177bf` · generated 2026-09-13 by `tools/brief_pack.py`

Read THIS file first and whole. Do not grep the spec, RULINGS or INDEX monoliths for
what is here; use `tools/docq.py` for anything else you need.

## Task

Promote the DSF resource resolver: tools/dsf_resource_audit.py + INDEX row + twin (RULINGS 13bl/13bq)

## The brief

Promote the scout's one-off DSF resource resolver (RULINGS 2026-09-13bl / 13bq, both in this pack) into a standing tool: `Ortho4XP/tools/dsf_resource_audit.py`, a `tools/INDEX.md` row, and a twin `Ortho4XP/tests/test_dsf_resource_audit.py`. It is a REGRESSION GUARD for every object-stage DSF rewrite: a def that resolves in the pristine `.anchor_bak` and not in the live DSF is OUR defect.

The scout's script (copy it before it vanishes; reimplement from 13bq if gone):
`/private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/audit.py` (+ `packs.json`, `report.json` beside it). It is ~100 lines: a library index over every pack-root `library.txt`, a case-insensitive listdir cache, `resolve()`, and a per-pack loop over the two dumps. Its two KNOWN traps are in 13bq: (1) `os.path.exists` is case-INSENSITIVE on APFS — exact-case is proven segment-by-segment against `os.listdir`; (2) `EXPORT_SEASON` / `EXPORT_EXCLUDE_SEASON` (and `EXPORT_RATIO`) carry ONE extra token before the virtual path — omitting them stranded 678 defs.

INPUTS. `dsf_resource_audit.py PACK_DIR [PACK_DIR ...]` or `--custom-scenery ROOT` (every pack under ROOT whose `Earth nav data/**/*.dsf.anchor_bak` exists — grouped and flat layouts, see `dsf_reader.ensure_dsf_text_path` for the two shapes); `--xplane XP_ROOT` (default: the parent of the Custom Scenery root) supplies `Resources/default scenery/*/library.txt` too. Each pack yields (live DSF, pristine `.anchor_bak`) pairs per tile.

DUMPS, READ-ONLY. For each DSF, first look for the data repo's content-keyed dump `Airport_mod_cache/<pack basename>/<tile>.dsf.<sha8>.text` (and `<tile>.dsf.anchor_bak.<sha8>.text`) — reuse `auto_patch.dsf_reader.dsf_content_tag` + `_default_pack_text_cache_path` + `airport_mod_cache_dir` (importable with `PYTHONPATH=src`; the tool runs from `Ortho4XP/`), NEVER writing there. On a miss run `DSFTool --dsf2text` (`dsf_reader._dsftool_path()`) into `--scratch DIR` (default: a `tempfile.mkdtemp`). Do NOT call `ensure_dsf_text_path` — it writes the cache. The tool must never write the data repo or the X-Plane install; a `--dry` is not needed because it never writes anything but its scratch dir and stdout / `--json OUT`.

RESOLUTION, as X-Plane does it: (a) pack-relative, TRUE exact case (segment-by-segment `os.listdir`; report a case-only match as CASE-MISS with the on-disk spelling); (b) then the library index: every `<root>/*/library.txt` under Custom Scenery AND `Resources/default scenery`, parsing ALL SEVEN forms `EXPORT`, `EXPORT_BACKUP`, `EXPORT_EXCLUDE`, `EXPORT_EXTEND`, `EXPORT_RATIO <ratio> vpath rpath`, `EXPORT_SEASON <seasons> vpath rpath`, `EXPORT_EXCLUDE_SEASON <seasons> vpath rpath`; a virtual path resolves when ANY exporting library's real file exists (case-insensitive vpath match is what X-Plane does; count LIB-DANGLING when every export's file is missing). Record which library resolved it.

CLASSES per def (OBJECT_DEF / POLYGON_DEF / NETWORK_DEF, with placement counts from `OBJECT`/`OBJECT_MSL`/`OBJECT_AGL` index, `BEGIN_POLYGON` index, `BEGIN_SEGMENT`/`BEGIN_SEGMENT_CURVED` network index):
- PRISTINE-BROKEN: unresolved in BOTH dumps, same path (the pack shipped it broken — OTHH's 34 `Jetway/`+`Misc/`, 185 placements).
- OURS: resolves in the pristine dump, unresolved in the live one (a path we garbled) — ALSO any pristine def path absent from the live def list (a def we dropped), and any def whose live placement count < pristine count (dropped placements — 13bq "dropped placements").
- OURS-NEW: a def present only in the live dump that does not resolve (a body we referenced but did not write).
- OK-NEW: a def present only in the live dump that resolves (our `…__b<n>.obj` bodies) — counted, not listed unless `--verbose`.
Plus two file checks per pack: every live def matching `__b\d+\.obj$` exists at its exact-case pack-relative path (a body must be pack-local, never a library hit); every `*.obj.anchor_bak` under the pack has its `X.obj` beside it (ORPHAN otherwise).

OUTPUT: one table per pack (kind, index, path, class, placements live/pristine, resolved-by), a per-pack summary line, and ONE verdict line at the end: `VERDICT: CLEAN` when OURS = OURS-NEW = CASE-MISS = ORPHAN = BODY-MISSING = 0 in every pack (exit 0), else `VERDICT: DEFECT (<n> …)` exit 1; PRISTINE-BROKEN never fails the verdict. `--json OUT` writes the full rows.

TWIN `Ortho4XP/tests/test_dsf_resource_audit.py` (no network, no X-Plane install, no DSFTool — pass the dumps in directly or monkeypatch the dump lookup; build everything in `tmp_path`): a fake Custom Scenery root with a pack dir holding `Earth nav data/+40-004/+40-004.dsf` and `.dsf.anchor_bak` (empty placeholders), a pristine text dump (OBJECT_DEFs: `Objects/a.obj` on disk; `lib/airport/x.obj` exported by a `library.txt`; `Misc/broken.obj` nowhere; `Objects/Case.obj` written on disk as `objects/case.obj`; a POLYGON_DEF `lib/pol.pol` exported via an `EXPORT_EXCLUDE_SEASON win,spr lib/pol.pol pol/p.pol` line), a live dump = pristine + `Objects/a__b0.obj` (on disk) + `Objects/a__b1.obj` (missing) + one pristine path altered to `Objects/A.obj` (garbled) + one dropped placement, and an `Objects/z.obj.anchor_bak` with no `z.obj`. Assert: PRISTINE-BROKEN = {Misc/broken.obj}, OURS = {the garbled path, the dropped placement}, OURS-NEW = {a__b1}, OK-NEW = {a__b0}, CASE-MISS = {Objects/Case.obj}, ORPHAN = {z.obj.anchor_bak}, the season-form export resolves `lib/pol.pol`, verdict exit 1 here and exit 0 on a clean variant. Twin the seven export forms by parsing a library.txt fixture with all of them and asserting every vpath lands.

REAL-PACK CLOSING TEST (read-only, no build): run the tool once with `--custom-scenery "/Users/noah/X-Plane 12/Custom Scenery"` and confirm it reproduces 13bq's numbers — eight packs, OURS 0 / OURS-NEW 0 everywhere, OTHH PRISTINE-BROKEN 34 defs / 185 placements, new bodies LEMD 2,365 / KCLT 481 / OTHH 1,792 / SPJC 91 / HECA 3,461 / NZQN 4 / NZVL 1 / VHHH 538, 323 library.txt files. Any divergence is a finding to report, not to paper over. Verify with `ls -lt` on `Airport_mod_cache/<pack>/` before and after that no `.text` file was written or touched by the tool (the cached dumps for the eight packs exist, so a cache-miss DSFTool run should not even be needed).

DELIVERY: commit on `claude/dsfaudit` in the lane worktree `/Users/noah/XPTerrainBuilder/.claude/worktrees/dsfaudit` (already mounted by the ritual; `Ortho4XP/venv` is the shared symlink). Add files by explicit path — never `git add -A` (the mounted symlinks would be committed). Do NOT merge. Suite from `Ortho4XP/`: `venv/bin/python -m pytest tests/test_dsf_resource_audit.py tests/test_harness.py -q` once. Run `venv/bin/python ../tools/blast.py tools/dsf_resource_audit.py` is not required (new file), but if you touch `dsf_reader.py` run blast first — prefer NOT touching it. Report: the sha, the INDEX row text verbatim, the twin test names, the real-pack verdict output.

## Bars

- `Ortho4XP/tools/dsf_resource_audit.py` exists, runs from `Ortho4XP/` with `venv/bin/python`, writes nothing outside its scratch dir / `--json` target; the data repo's `Airport_mod_cache` is read-only to it (verified by mtime listing before/after the real-pack run).
- Exact-case resolution proven against `os.listdir`, never `os.path.exists`; all SEVEN `EXPORT*` forms parsed with the season/ratio token skipped.
- Classes PRISTINE-BROKEN / OURS / OURS-NEW / OK-NEW + CASE-MISS / ORPHAN / BODY-MISSING, with placement counts; one table per pack; one verdict line; exit 1 on any OURS-class finding.
- Real-pack run reproduces RULINGS 13bq: 8 packs, OURS 0, OURS-NEW 0, OTHH PRISTINE-BROKEN 34/185, bodies 8,740 total.
- `tools/INDEX.md` row lands in the same commit; twin `Ortho4XP/tests/test_dsf_resource_audit.py` passes; `tests/test_harness.py` passes once.
- Branch `claude/dsfaudit`, NOT merged; sha reported.

## Files

Yours: `Ortho4XP/tools/dsf_resource_audit.py`, `Ortho4XP/tests/test_dsf_resource_audit.py`, `tools/INDEX.md`
Other lanes' (do not touch): `Ortho4XP/src/auto_patch/dsf_reader.py`, `Ortho4XP/src/auto_patch/dsf_write.py`

## RULINGS

## 2026-09-13bl — OWNER (verbatim): "I'm seeing errors in the sim when loading at multiple test airports, I'm wondering if our modification to objects or the DSF may have garbled a path or changed a file name. You can review the log, here's an example at OTHH: 0:16:09.571 E/SCN: Failed to find resource 'Jetway/OTHH_Jetway_Type8.obj', referenced from scenery package 'Custom Scenery/OTHH Doha (Aeroscape)/'." — CHECKED (read-only): NOT OURS at OTHH. `Log.txt` (the owner's current session) carries 136 `Failed to find resource` lines, ALL from the OTHH pack, 34 distinct resources under `Jetway/` and `Misc/` (the jetway types, the 34R/16L ILS docks, the `ini_Lib_*` DME/ILS objects). The PRISTINE DSF — `+25+051.dsf.anchor_bak`, sha 84ffe846, our untouched backup — carries the SAME 34 `OBJECT_DEF`s with the SAME 185 placements (10 for `Jetway_Type8`) as the rewritten DSF (d4ab5e36, 3,039 defs); no file named like any of them exists anywhere in the pack (no `Jetway/` or `Misc/` directory; `Objects/` holds `.str`, `GSE`, `tunnels`), no `library.txt` in Custom Scenery exports them, the pack's `OTHH.zip` holds 3 unrelated files. The Aeroscape pack SHIPPED these references broken (a companion library the owner does not have, or authoring debris); X-Plane logs each and skips the object. Our writer keeps every original `OBJECT_DEF` path verbatim (the split bodies are ADDED defs `…__b*.obj` beside them) and renames nothing but the `.obj.anchor_bak` copies it makes of the files it cuts. Scout `v2objpaths` sweeps every pack the owner tested (LEMD, KCLT, SPJC, CYXY, SPLP, OTHH): every `OBJECT_DEF` in the rewritten DSF resolves on disk or through a library export, and every one that does not ALSO fails in the pristine dump — a def that resolves in the pristine and not in ours would be OUR defect.

## 2026-09-13bq — SWEPT (scout `v2objpaths`, every `Custom Scenery/` pack holding our `*.dsf.anchor_bak` — EIGHT: LEMD, KCLT, OTHH, SPJC, HECA (Tai Models), NZQN, NZVL, VHHH (rewritten 16:05 today); CYXY and SPLP were never touched by the object stage): OUR WRITER IS CLEAN. Live vs pristine `OBJECT_DEF` + `POLYGON_DEF` (no `NETWORK_DEF` anywhere), every path resolved as X-Plane does — pack-relative with TRUE exact-case checking (segment-by-segment against `os.listdir`; `os.path.exists` lies on APFS) then through 323 pack-root `library.txt`s / 93,519 virtual paths with ALL SEVEN `EXPORT*` forms (`EXPORT_BACKUP` 339,071, `EXPORT` 99,545, `EXPORT_EXCLUDE` 87,889, `EXPORT_SEASON` 9,117, `EXPORT_EXCLUDE_SEASON` 6,103, `EXPORT_EXTEND` 1,961, `EXPORT_RATIO` 574 — the two `*_SEASON` forms carry a season token before the path; omitting them stranded 678 defs on a first pass, 635 of them LEMD's own `AS_LEMD/…` exports): OURS 0 and OURS-NEW 0 in every pack; pristine defs lost 0 (every original path kept verbatim); every new def is a `…__b<n>.obj` body (LEMD 2,365, KCLT 481, OTHH 1,792, SPJC 91, HECA 3,461, NZQN 4, NZVL 1, VHHH 538 = 8,740, each on disk at its exact-case path); `*.obj.anchor_bak` orphans 0 (every backup has its original beside it); exact-case misses 0 on either axis. PRISTINE-BROKEN: OTHH only — the 34 `Jetway/` + `Misc/` defs, 185 placements, byte-identical before and after (13bl confirmed on independent instrumentation). `Log.txt` (15:59): 136 `Failed to find resource` = those 34 × 4, 100 % pristine-broken; 0 `Failed to load`; 80 `OBJ read failed` all `GMTT Tanger` (untouched); 1 x86 plugin `dlerror`; KCLT's DSF loaded with zero resource errors; the other six packs were not loaded in that session (unverified from the sim side — the static audit is the evidence). ONE FINDING, cosmetic: 30 `E/OBJ: bad light name: full_custom_halo_night` on three of our bodies (`ini_OTHH_Qatar_HangarD_base_000__b0/b1`, `OTHH_RadioBuilding_000__b0`) — the pack's own `LIGHT_NAMED full_custom_halo_night` lines (28 + 10 in the untouched originals; exported by no library), copied verbatim into the split bodies; loud only because the originals now sit at 0 placements and the bodies at 1. RULED: the writer copies what it cuts — pack content stays the pack's; an unresolvable `LIGHT_NAMED` is not remapped (X-Plane drops the light, keeps the object). PROMOTION: the resolver becomes `Ortho4XP/tools/dsf_resource_audit.py` (live vs `.anchor_bak`, PRISTINE-BROKEN / OURS / OURS-NEW, dropped placements; twin carrying the two traps) — a regression guard for every object-stage rewrite; chip filed.

## Tool: dsf_placement_diff

| `Ortho4XP/tools/dsf_placement_diff.py` | THE DRY RUN of the DSF placement edit (spec `object-placement-spec.md` §3/§5, RULINGS 2026-09-11b): per placement, old line -> new line, writing NOTHING. `--dsf PACK.dsf --pack-root PACK` derives the §5 conversions (every `OBJECT_MSL`/`OBJECT_AGL` of a PACK resource becomes an on-ground `OBJECT`; a stock `lib/…` resource is KEPT — 09z (2)) and prints them per resource; `--plan PLAN.json` applies a `PlacementPlan` the split half wrote instead; `--verify` encodes into a TEMP dir and runs `dsf_write.verify_roundtrip`. It calls the writer's own pure `edit_dump` — never a second implementation. Measured 2026-09-11: KMCI 862 conversions / 870 stock kept, KBNA 196 / 958, LEMD 0 (already all on-ground), every round trip ok. |

## Standing discipline (unchanged for every lane; the long form is `.claude/agents/lane.md`)

- Worktree: `tools/harness/lane_worktree.sh up <lane> <base sha>`; branch `claude/<lane>`.
  `git merge main` FIRST if main has moved past the base sha.
- `Ortho4XP/venv/bin/python tools/blast.py <file>` before editing each source
  file; files under 1,000 lines.
- ONE closing build through the harness (v2 is the only engine, RULINGS
  2026-09-13au — there is no `--engine` flag); base arms cut with
  `git archive <sha> src`, never another live checkout.
- NEVER write `/Users/noah/XPTerrainBuilderData` or `/Users/noah/X-Plane 12/Custom Scenery/`;
  no `--refresh-data`; every run prints `[guard] shared repo UNCHANGED`;
  lane-local `O4_DSF_CACHE_DIR` / `O4_AIRPORT_MOD_CACHE_DIR` under your scratchpad.
- Any wait loop is bounded (`timeout N` or `$SECONDS`); prefer foreground.
- Suite from `Ortho4XP/` twice: `venv/bin/python -m pytest -q --no-header -p no:cacheprovider -rfE tests/auto_patch_v2 tests/test_harness.py tests/test_role_edge_census.py`.
- Attempt cap two per rule; a bar that moves backwards twice → delete the code, report the measurement.
- Consumer census (RULINGS 2026-08-30l) in the spec MEASURED block before any consumer is edited.
- Extend tools, never fork; INDEX row + twin for any new option. Do NOT merge into main; do NOT write RULINGS.
- Read law with `tools/docq.py spec '§N'`, `tools/docq.py ruling 13xx`, `tools/docq.py index <name>`;
  find captures with `tools/harness/frames.py list [ICAO]`; register yours when done.
- REPORT: branch + sha; per-bar before → after with the frame named; what you did NOT do;
  intent questions with their measurement; files touched.

