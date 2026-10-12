# tilecont564 — lane notes (issue #564, RULINGS 2026-10-12a)

## RESUME HERE

* Branch `claude/tilecont564`, worktree `.claude/worktrees/tilecont564`, base `1ff5a912a`.
* STEP 1 DONE: consumer census (below), design decided.
* STEP 2 DONE: `Ortho4XP/src/O4_Unpatched_Airports.py` (new), `auto_patch/driver.py`
  (`_fail_build_tasks` sets aside, exception carries `stale_left`), `O4_Vector_Map.py`
  (`include_airports` continues; `build_poly_file` still returns 0 for what is re-raised),
  strict env in `tools/harness/build_airport.py` `redirect_engine_caches` and
  `scripts/check_frozen_tile.py`, twin `tests/test_unpatched_airports.py` (12 tests).
* STEP 3 DONE: ratchets pass; full non-Qt suite run once (3 reds in
  `test_auto_patch_engine_dispatch.py` — the set-aside imported `auto_patch_v2`, which those twins
  stub out; fixed by spelling the family in `O4_Unpatched_Airports.PATCH_FAMILY`, held against the
  writers' constants by a twin); affected files rerun green. Nothing left but the master's merge.

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
