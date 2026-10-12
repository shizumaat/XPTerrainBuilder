# tilecont564 — lane notes (issue #564, RULINGS 2026-10-12a)

## RESUME HERE

* Branch `claude/tilecont564` (PR #573). Round 1 (12a) done at `fafbd9695`.
* ROUND 2 (RULINGS 2026-10-12d, "restore the original pack"): merged origin/main `012ac5899`;
  took `origin/claude/failmsg562`'s `O4_Unpatched_Airports.py` + its twin (file checkout, not a
  branch merge — PR #573 stays this lane's diff). Census below ("Round 2"). NEXT: implement
  `dsf_write.write_pack(drop=)`, `auto_patch_v2/airport/unpatched_pack.py`, the hook at the top of
  `engine_v2.rebake_after_mesh`, `O4_Unpatched_Airports.note_pack`, twins, full non-Qt suite.

## What fails today, and where

* `auto_patch/driver.py` `_fail_build_tasks` is the ONE path every per-airport failure takes
  (`_run_build_tasks`: result not ok at stage build / solve / verify / write / worker / missing,
  and the on-disk manifest check; plus the stale-road-feed pre-check, which fails every airport
  still needing a rebuild at stage `build`). It logs, emits one `AutoPatchFailed` each, and raises
  `AutoPatchBuildFailure`.
* `O4_Vector_Map.run_auto_patch_generation` raises the same exception itself for the WHOLE-TILE
  `config` stage (`icao == "*"`: auto-patch on, no CIFP directory).
* `O4_Vector_Map.build_poly_file` catches it and returns 0. Every caller reads that 0:
  `o4_engine/session.py` (`BuildDone(ok=False)`), `tools/harness/build_airport.py`
  `run_tile_steps` (SystemExit), `tools/run_tile_mesh_only.py`, `tools/profile_tile_build.py`,
  `tools/airport_inset_acceptance.py`, `scripts/check_frozen_tile.py` (through `BuildDone.ok`
  and, in two passes, the `AutoPatchFailed` events themselves).
* Writes are atomic (`engine_v2`: `os.replace` of patch then sidecar, AFTER the verify gate), so a
  failed airport leaves on disk either its PREVIOUS build's family (stale) or, for a `write`
  failure after the replace, a half-placed NEW family. Both are "a patch this build did not
  finish".

## Consumer census — who reads a failed airport's files after step 1's auto-patch pass

Per-airport family in `Patches/<block>/<tile>/` (one placer: `engine_v2`):
`<ICAO>_auto.patch.osm`, `<ICAO>_auto.patch.osm.axes.json`, `<ICAO>.graded.json`,
`o4_v2_rebake_<ICAO>.json`, `o4_v2_rebake_<ICAO>.screen.json`, `o4_v2_rebake_<ICAO>.screen.refused`.

| # | Consumer | Step / process | Reads | How it selects | With the file set aside |
|---|----------|----------------|-------|----------------|-------------------------|
| 1 | `O4_Vector_Map.include_patches` | 1 vector | `*.patch.osm` | `listdir`, suffix `.patch.osm` | not loaded; airport not in `patches_list` |
| 2 | `O4_Airport_Utils.encode_runways_taxiways_and_aprons` / `encode_hangars` | 1 vector | `patches_list`, `patches_area` from (1) | membership | airport takes the ORDINARY (non-auto-patch) treatment |
| 3 | `O4_Vector_Map.road_bridge_deck_pins` | 1 vector (roads) | `*.patch.osm.axes.json` → `road_bridge_decks` | `listdir`, suffix | no deck pin from that airport |
| 4 | `O4_Vector_Map.road_join_yield_pins` | 1 vector (roads) | `*.patch.osm.axes.json` → `road_join_yield` | `listdir`, suffix | no join pin from that airport |
| 5 | `O4_Mesh_Utils` bank rings (l.1197) | 2 mesh | `*.patch.osm` | `listdir`, suffix + own copy of mode/manual filter | not read |
| 6 | `O4_Mesh_Utils` road linework (l.1311) | 2 mesh | `*.patch.osm` | same | not read |
| 7 | `O4_Vector_Map.auto_patch_not_applied` | 1 + post-mesh | `<ICAO>_auto.patch.osm` exists | `isfile` | "no …_auto.patch.osm" → not applied |
| 8 | `engine_v2.rebake_after_mesh` (object stage, pack DSF rewrite) | 2 mesh, end | `o4_v2_rebake_*.json`, `*.screen.json` | `glob` + name regex, then (7) per plan | no plan found; were one found, (7) skips it |
| 9 | `object_plan.from_screen` / `placement_read` | post-mesh | `<ICAO>.graded.json`, patch for staleness | exact path, only for a plan from (8) | never reached |
| 10 | `driver._auto_patch_is_current` (NEXT build's freshness gate) | 1 vector, next build | `<ICAO>_auto.patch.osm` header | exact path | absent → airport is rebuilt (retried) |
| 11 | patch-set manifest check (`driver._run_build_tasks`) | 1 vector | patch + sidecar on disk | exact path | the check is what NAMES the failure; unchanged |
| 12 | tile-wide `o4_object_anchor_worklist.json`, `o4_object_foot_pads.json`, `auto_patch_verify_debug.log` | — | not per-airport geometry; (8) uses the worklist only for its directory | — | untouched |

Steps 3 (masks) and 4 (imagery/DSF) read no patch file: they read the mesh.

Every geometry consumer selects BY FILE NAME; consumers 5–9 run in the mesh step, which the app
runs in a SEPARATE worker process from step 1 (`o4_engine/parallel.py`, one child per step), so an
in-memory "do not load" list on the tile object would not reach them, and two of them (5, 6) do
not use the shared admission test (7).

## Design

* EXCLUSION = MOVING ASIDE, at the single derivation site (root CLAUDE.md: "prefer trimming a
  region at its single derivation site over per-consumer vetoes"). `_fail_build_tasks` renames
  every file of a failed airport's family to `<name>.stale` (overwriting an older `.stale`). No
  consumer pattern matches the suffix, so rows 1–9 need no edit, and it holds across processes
  and across a later mesh-only rerun. Not deleted: the last good patch stays for diagnosis.
  A later successful build writes the family fresh (row 10 retries the airport by itself); the
  `.stale` files are inert and are overwritten by the next failure. No manual cleanup.
* If a file CANNOT be moved (OS error), the stale patch is still loadable: that failure stays
  FATAL to the tile (H1 outranks continuing).
* STRICT MODE: env `O4_AUTO_PATCH_STRICT=1` keeps today's behaviour (step 1 returns 0). Set by
  the harness build environment (same place as `O4_PACK_WRITES`), the other tile tools and
  `scripts/check_frozen_tile.py`; the app sets nothing.
* TILE-LEVEL stays fatal: the `config` stage (`icao == "*"`), everything outside auto-patch.
* DEFAULT TREATMENT of the unpatched airport: exactly what the engine does for an airport with
  auto-patch off — it is absent from `patches_list`, so `encode_runways_taxiways_and_aprons`,
  `encode_hangars` and `flatten_helipads` give it the ordinary Ortho4XP airport handling over the
  airport-smoothed tile DEM; the object stage does not touch its pack.
* UNPATCHED LIST for the session: `tile.auto_patch_unpatched` (list of
  `{"icao","stage","error"}`) and, because the final `BuildDone` of an app build is emitted by a
  DIFFERENT process than step 1, a sidecar `<build_dir>/o4_unpatched_airports.json`.

## Field request for lane failmsg562 (not stubbed here)

`BuildDone.unpatched_airports: list = []` — one `{"airport": str, "stage": str, "error": str}`
per airport the tile was built without. Empty = clean success; non-empty with `ok=True` =
success with warnings.

Source for the session: `O4_Unpatched_Airports.read(tile)` (keys `icao` / `stage` / `error`).
It returns this process's own record when it ran the vector step and otherwise reads
`<tile.build_dir>/o4_unpatched_airports.json`. That matters: under `o4_engine/parallel.py` each
step runs in its own child, the vector child's `BuildDone(ok=True)` is SWALLOWED as an
intermediate (`_on_child_event`, "event.ok and not last_step"), and the tile's final `BuildDone`
comes from the last step's child, whose session never saw the `AutoPatchFailed` events.

## Round 2 — RULINGS 2026-10-12d: the unpatched airport gets its original pack back

### Census: what the engine writes into a pack for an airport, and what undoes it today

| Pack file | Writer | Scope of one write | Backup / record | Existing undo |
|---|---|---|---|---|
| pack DSF `<tile>.dsf` | `dsf_write.write_pack` | ONE DSF; edits of EVERY recorded airport composed over the pristine dump (#25) | `<dsf>.anchor_bak` (pristine, kept once) + `o4_placement_provenance.json` → `dsfs[<dsf>].airports[<ICAO>]` = that airport's edit rows, bodies, dump sha | per PACK: `object_rebake.restore_detail` (UI "restore originals"): classify, copy backup over, remove bodies, drop entry. Per AIRPORT: none — the next write of a sibling RE-APPLIES the recorded row |
| split bodies `__b<k>.obj` | `placement_write.write_files` | one airport (`airports[<ICAO>].body_files`) | `CUT_MARK` in the file | `dsf_write.remove_cut_files(written_body_files(pack, dsf, icao))`; orphan removal inside `write_pack` |
| pack `.obj` (y rewritten) | v1 seat only, retired 2026-09-12 | pack | `<obj>.anchor_bak` + v1 sidecar | `placement_write.restore_pack_objects` at every v2 write; the UI restore |
| art omission (#433) | `write_pack(omit=)` | DSF entry `omitted_art` | the same backup | a later write without `omit` |
| DSF text dump (mod cache) | `dsf_reader.ensure_dsf_text_path` | DSF, keyed on its mtime | — | refuses itself when the DSF changes |

Who reads the record / backup and must agree after a per-airport restore:
`backup_state.classify_dsf` (OURS by `written_sha256`/stat), `dsf_write.pristine_dsf_path` (every
reader's frame), `written_body_files`, `_sibling_plans` (re-applies recorded airports),
`object_rebake.modified_packs` / `_v2_status` (the apps' "modified packs" list),
`pack_art` (`omitted_art`).

### What a rebake pass does to an unpatched airport's seating TODAY

* Its plan files are set aside (round 1), so the pass has no plan for it and never visits its pack.
* If ANOTHER airport on the tile is served by the same pack DSF and is written this pass,
  `_sibling_plans` re-applies the unpatched airport's recorded edits — its old seating is
  actively kept. So "restore then let the others re-apply" must REMOVE the recorded row.

### Design

* `dsf_write.write_pack(..., drop=())`: recorded airports NOT re-applied. Their rows fall out of
  the record and their bodies take the existing orphan path. No second composer.
* `auto_patch_v2/airport/unpatched_pack.py` `restore_airport(pack_root, dsf_path, icao, tool)`:
  - airport not recorded for this DSF → no-op (never re-seated);
  - no other recorded airport → the DSF's backup goes back over it, the bodies go, the entry is
    dropped: the UI restore's own rule (`classify_dsf`: only an OURS file is overwritten), for
    one DSF. No DSFTool needed;
  - other airports recorded → one `write_pack` with an empty-ICAO plan and `drop=(icao,)`: the
    DSF is rebuilt from the pristine dump with the others' recorded edits only (their seating
    kept whether or not they are rewritten later in the pass);
  - UNPROVEN / ORIGINAL_LOST, or the rewrite fails → nothing is written, the reason is returned.
* Hook: the first thing `engine_v2.rebake_after_mesh` does after the user's stand-down gate,
  BEFORE the plan glob (a tile whose every airport failed has no plan and returned early).
  Packs are found from the engine's own records (`object_rebake.modified_packs(scenery, tile)`),
  not from the set-aside plan. A disabled pack is not touched. The lane stand-down
  (`O4_PACK_WRITES=measure_only`) and `DSF_OBJECT_REANCHOR` off write nothing and are NAMED.
* Unprovable → `O4_Unpatched_Airports.note_pack(tile, icao, text)` adds `pack_restore` to that
  airport's record (sidecar rewritten) and a `loud_warning` line.
