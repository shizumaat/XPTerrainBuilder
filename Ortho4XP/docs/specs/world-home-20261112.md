# The World folder is the tiles' home (RULINGS 2026-11-12g, 2026-11-12h)

Lane `lworldbuild`, branch `claude/lworldbuild`. Owner 2026-11-12T23:09:06Z "Yes to both".

## 1. What changes

* **One home.** When the app's World pack (`<Custom Scenery>/zXPTerrainBuilder World`, made by `world_install`, not foreign) exists, it is the HOME of every tile the app builds:
  * `<World>/XPTerrainBuilder_tiles/zOrtho4XP_<tile>/` — every build folder (Build tab, World job, flight job): the build writes there, and `world_publish` puts the finished tile into the pack's own layout (`Earth nav data`, `terrain/<tile>`, `textures/<tile>` — the textures are hard links, now always on the same volume).
  * `<World>/XPTerrainBuilder_packages/` — the `.xptb` store (`storage_packages.store_dir`, world_adopt's `<tile>_adopted.xptb`, `packaged.json`).
  * `<World>/XPTerrainBuilder_home/` — the migration journal and its backups.
  X-Plane reads only a pack's root `Earth nav data`; a nested folder is never a pack, never scanned, never linked.
* **One derivation site.** `FNAMES.Tile_dir` is served at access time (PEP 562, as `Mask_dir` is) from `FNAMES._tiles_root()`: the World home named by the data folder's pointer `world_home.json` when its tiles folder exists, else `<data>/Tiles`. Every reader of `Tile_dir` / `build_dir(lat, lon, "")` follows without an edit. The pointer is written only after a migration run leaves nothing to move; it lives in the data folder (disposable: the next start writes it again).
* **No custom build folder.** The Mac `OrthoCustomBuildDir` and the Qt `output_dir` preference go; both apps send `custom_build_dir ""`. Their last value is handed to `world_onboard` once (`legacy_build_dir`), backed up (`OrthoCustomBuildDirBeforeWorld` / prefs `output_dir_before_world`), then cleared.
* **Every build is published**, not only on-demand ones (`world_publish._publish_built` drops its on-demand gate; airport cores stay on-demand only). `O4_Scenery_Links.install` never links a build folder inside the World pack.
* **Tiers.** Settings ▸ Storage lists every mounted volume other than the app's own (data and X-Plane volumes) with a size field; a size > 0 makes it a tier (`storage_tiers`, setting `storage_tiers` JSON `{mount: gb}`). A sharp texture the on-demand budget makes low-res again (`imagery_downgrade`) is MOVED to `<tier>/XPTerrainBuilder Tier/DDS_cache/<key>` while a tier is mounted and has room, instead of deleted; `imagery_ondemand._full_entry` finds it there and lands it back (copied into the cache, then served as today). An absent volume is simply not a source: the follow job downloads again, as adopted +51+022 does with ThunderBlade.

## 2. Migration (journaled, resumable; `o4_engine/world_home.py`)

Run by `world_onboard` with `move_home` (both apps' start pass it; a bare call, as in tests, only reports) after the pack exists, never while the tile builds (`busy`: the session's queued/building tiles are skipped and moved next start).

1. Back up the journal (`journal.json.<stamp>-before-<run>`) before the run writes it.
2. Sources, in order: `<data>/Tiles/zOrtho4XP_*`, then the legacy custom build folder's `zOrtho4XP_*` (skipped when it is Custom Scenery itself — those are per-tile packs and Convert existing tiles owns them, 2026-11-12a — or already the World tiles folder), then `<data>/Tile_packages/*` (packages and `packaged.json`).
3. Per item, journal `moving` → `moved`: one `os.rename` on the same volume; across volumes a copy under `<name>.part`, sizes verified, renamed into place, then the source removed. A name already present in the World folder is never overwritten: journal `conflict`, the source stays.
4. After the tile folders move: the on-demand index rows naming a moved folder (or a path inside it) name its new place (`O4_Imagery_OnDemand_Index.repoint_folder`, one SQL update a folder; no tile is rescanned, so 700 tiles move in seconds). A run killed after a cross-volume copy landed and before its source went (journal `moving`, both present, the same bytes) is finished by the next run, not counted as a conflict.
5. After the store moves: `packaged.json` `path` fields under the old store are rewritten to the new one.
6. When nothing is left to move (conflicts and busy tiles count as left), the pointer `world_home.json` is written; until then `Tile_dir` stays `<data>/Tiles`, so no tile is ever read from a half-moved home.

Nothing is deleted: a same-volume move is a rename; a cross-volume move removes the source only after the copy is verified. Empty `<data>/Tiles` and `<data>/Tile_packages` folders are left in place.

## 3. Consumer census (RULINGS 2026-08-30l)

Grep of `Tile_dir`, `build_dir(`, `custom_build_dir`, `customBuildDir`, `tileBaseFolder`, `output_dir`, `store_dir`, `STORE_DIR`, `Tile_packages`, `_adopted.xptb`, `World_build`, `World_staging` over `Ortho4XP/src` and `Sources` (auto_patch* excluded: airport packs only).

| Consumer | Where | Reads / writes | Ruling |
|---|---|---|---|
| `FNAMES.Tile_dir`, `build_dir(lat, lon, "")` | `O4_File_Names` | derivation site | CHANGED: served by `_tiles_root()` (pointer → World home, else `<data>/Tiles`) |
| Session build folder | `session.tile_build_dir`, `enqueue_build` | write | unchanged code: default = `Tile_dir`; apps pass `""` |
| World job full builds, flight jobs | `world_job_run`, `flight_job_run`, `flight_manager` | write via session | unchanged: they already pass `""` → World home |
| Drape scratch `World_build`, staging `World_staging` | `world_job_run:253`, `world_commands.staging_root` | transient | unchanged: scratch removed after staging; disposable (12h) |
| Publish | `world_publish._publish_built`, `_sharpen` | write pack | CHANGED: every build published; cores stay on-demand only |
| Per-tile links | `O4_Scenery_Links.install` | write Custom Scenery | CHANGED: a build folder inside the World pack is never linked |
| Records copy for converted tiles | `world_records.plan` (`build_dir(..., "")`) | write | unchanged code: follows `Tile_dir` |
| Tile info / scanner / staleness / failures / stopped build | `O4_Tile_Info`, `session.scan`, `O4_Imagery_Freshness`, `O4_Tile_Failures`, `O4_Stopped_Build` | read build folder | unchanged: build folder now in the World home |
| Library engine | `library._custom_build_dir`, `library.py:480` | read | unchanged: `working_dir == Tile_dir` → `""` |
| On-demand index | `imagery_ondemand._tile_roots`, `on_demand_tiles`, rows' `build_dir`/`config_dir`/`textures_dir`/`terrain_dir` | read; rows name the folder | unchanged readers; MIGRATION repoints the rows of a moved folder (`INDEX.repoint_folder`) |
| Package store | `storage_packages.store_dir`, `world_adopt._package_path`, `package_first`, `world_tile_remove` | read/write | CHANGED: `store_dir()` = World home's `XPTerrainBuilder_packages` when the pointer is set |
| `packaged.json` `path` | `storage_packages.remember` | absolute paths | MIGRATION rewrites them |
| Rebuild data | `FNAMES.rebuild_root` (`Rebuild_cache`) | cache | unchanged: a cache (10d); the tile rebuilds from its package and caches without it |
| Rebuild pointer in a tile folder | `FNAMES.rebuild_pointer_path` | absolute cache path | unchanged: moves with the folder, still valid |
| Storage rows | `storage.STORES` `tiles`, `tile_packages` | sizes | unchanged code: rows follow `Tile_dir` / `store_dir`; the World row counts DSFs only (`storage_range.world_parts`), no double count |
| Disk budget floor | `storage_budget._floor_parts` (`Tile_dir` glob) | read | unchanged code |
| Patch library | `patch_library.publish/apply/scan` (`Tile_dir` compare) | read | unchanged code |
| Plan estimate | `plan_estimate:345` | read | unchanged: `custom_build_dir ""` → `Tile_dir` |
| Slow-step watch | `slow_step:222` | read | unchanged |
| Cfg migration | `O4_Cfg_Migrations:120` | read | unchanged |
| Rebuild cache migrate | `O4_Rebuild_Cache.rebuild_migrate` default folder | read | unchanged |
| Tile bundle paths | `tile_bundle/paths.py:46` (`getattr(FNAMES, "Tile_dir")`) | read | unchanged: `__getattr__` serves it |
| Tile settings read/write | `O4_Settings_Model.read_tile_raw/write_tile`, `O4_Config_Utils.Tile`, `O4_Tile_Customizations`, `O4_Edit_Cache` | read/write cfg | unchanged code: `custom_build_dir ""` → World home |
| Build Airports card | `build_airports`, Swift `BuildAirportsWire`, Qt `O4_Qt_Build_Airports.request` | write via session | CHANGED callers: apps pass `""` |
| Mac `OrthoCustomBuildDir`, Build pane folder picker | `BuildModel.swift:247,794-811`, `BuildPane.swift:177,604-618` | setting | REMOVED; value handed to `world_onboard` once, backed up, cleared |
| Mac `tileBaseFolder` | `BuildModel.swift:799` and ~20 readers | read | CHANGED: the engine's `world_onboard` `home.tiles_dir`, else `<data>/Tiles` |
| Mac `PlanEstimate`, `BuildModel` build/`plan_estimate`/`tile_settings` calls | `BuildModel.swift:1710,1991,3271` | write | CHANGED: `""` |
| Qt `output_dir` preference, `output_dir()`, `working_dir()`, start-up "missing folder" fallback | `O4_Qt_GUI.py:848,2247-2257` | setting | REMOVED: `output_dir()` → `""`, `working_dir()` → `Tile_dir`; value handed to `world_onboard` once, backed up, cleared |
| Qt wizard "Where should finished tiles go?" | `O4_Qt_Wizard._page_folders` | setting | REMOVED (the first-run wizard is Qt-only) |
| Qt Settings path rows (`output_dir` in `_is_path_setting`) | `O4_Qt_Settings.py:77` | label only | unchanged (harmless name list) |
| Onboarding | `world_commands.world_onboard`, Swift `WorldOnboard`, Qt `O4_Qt_World_Onboard` | — | CHANGED: runs the migration; reply carries `home` |
| World-folder guard | `world_commands._foreign_target` | — | unchanged: a foreign World folder is never a home |
| Convert existing tiles | `world_migrate`, `world_originals`, `world_retire`, `world_adopt` work folder beside Custom Scenery | — | unchanged (its `originals/`, `lean/` are the owner's converted copies; their Undo law is 12a) |
| Sharp imagery downgrade | `imagery_downgrade._free_cache_entry` | delete | CHANGED: moved to a mounted tier with room first |
| Full texture lookup | `imagery_ondemand._full_entry/_serve_full` | read | CHANGED: a mounted tier is a second source |
| Settings ▸ Storage | Mac `LibraryStorage.swift` `StorageSettingsRows` + `StorageTiersSection.swift`, Qt `O4_Qt_Library_Storage.StorageRows` + `O4_Qt_Storage_Tiers.TiersBox` | UI | CHANGED: "Storage tiers" rows in both (parity manifest `STORAGE_ROWS`) |
| Test session | `tests/conftest.py` | — | CHANGED: each test has its own pointer file (`O4_WORLD_HOME_POINTER`), and the move runs only on a data root under pytest's basetemp (the master checkout's `Tiles` holds real tiles; the Qt window's start would otherwise move them into a test's World folder) |

## 4. Not in this round

* The build writer emitting the pack layout directly (spec flight-manager §7.3 W3) — builds still stage + publish.
* Convert's `XPTerrainBuilder_world_migrate/{originals,lean}` stay beside Custom Scenery.
* Cross-volume migration runs inside `world_onboard`'s call (synchronous); a progress event is future work.
