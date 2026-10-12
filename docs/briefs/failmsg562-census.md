# failmsg562 — census of tile-ending failures (issue #562)

Lane `failmsg562`, base `aed288725`. PHASE 1 deliverable: the master rules the copy.

## How a tile ends without a tile today (four exits, all in `o4_engine`)

| Exit | Where | Wire | 
|---|---|---|
| E1 a step function **returns 0** | `session._build_worker` L1096 (stops at the first failed step) | `TileState(error,"failed")` + `BuildDone(ok=False, error="the <noun> step failed (see the console log)")`; if the driver named airports first: one `AutoPatchFailed(airport, stage, error)` each and `BuildDone.error = "auto-patch failed for KPDX (build): [v2] <exception text>; …"` |
| E2 a step function **raises** | `session._build_worker` L1170 | traceback to stderr and `Ortho4XP.log`; `BuildDone(ok=False, error="crashed with an exception (see the console log): <Class>: <text>")` |
| E3 the **worker child dies** (parallel runs) | `parallel._on_child_exit` L1804 | `BuildDone(ok=False, error="build worker exited unexpectedly")` |
| E4 **cancel** (`UI.red_flag`) | `session._build_worker` L1106 | `TileState(queued,"stopped")`, no `BuildDone`; `RunDone(cancelled=True)` |

What the apps show, for every row below (neither app has a failure surface other than the console):

* **mac** (`Sources/XPTerrainBuilder/BuildModel.swift`): console line `*** Tile +45-123: airport KPDX failed at the build stage — <error>` per `AutoPatchFailed`, then `*** Tile +45-123 failed: <BuildDone.error>`; the activity row reads `failed`. The traceback is only in `~/Library/Logs/XPTerrainBuilder/engine-stderr.log`.
* **Qt** (`Ortho4XP/src/O4_Qt_GUI.py`): the same `AutoPatchFailed` line printed to the console pane; `BuildDone.error` is repeated in the end-of-run report (`_compose_run_report`); the row reads `failed`. The engine runs in-process, so tracebacks print straight into the console pane.

So today the headline the user reads IS the exception text (rows 1–12), a developer refusal (rows 3, 13, 14), or "the X step failed (see the console log)" with the cause only in scroll-back (rows 15–33).

## What the code does today when ONE airport fails (not a proposal — owner question)

`auto_patch/driver.py` `_run_build_tasks`: every airport of the tile is still attempted and every result collected; then **any** failure record raises `AutoPatchBuildFailure`, `O4_Vector_Map.build_poly_file` (L1313) catches it and returns 0, and the session stops the tile at step 1 (H1, POSTMORTEM-20260831: a lost patch must never mesh the stale patch on disk). One airport's failure therefore aborts the whole tile; the other airports' patches were written but no mesh is built. The stale-road-data abort fires before any worker starts. This lane changes none of that.

## Remedy set (fixed; `{log}` is the log path the front end shows)

| Key | Text |
|---|---|
| R-RETRY | Build the tile again. If it fails again, report it and attach the log. |
| R-NET | Check the internet connection, then build the tile again. |
| R-LATER | Try again later. |
| R-DISK | Free some disk space, then build the tile again. |
| R-PACK | Update, repair or disable that scenery pack, then build the tile again. |
| R-REPORT | Report it and attach the log. |
| R-SETTINGS **(not in the brief's set — needs a ruling)** | Check the X-Plane folder / the source chosen in Settings, then build the tile again. |

"Build without that airport if the app offers it" is NOT used in any row: neither app offers it today (the only switch is auto-patch All/None for the whole tile), and whether it should exist is the open owner question of #555/#556.

## The table

`{tile}` = `+45-123`; `{airports}` = folded list (`KBFI, KGRF, KPAE and 3 more`). "What" always starts "Tile {tile} was not built:" — only the tail is listed. Confidence: **A** cause class known from the raise site; **B** class known, remedy is my guess; **C** could not determine the cause class → "report it".

### Per-airport (auto-patch) — reach the wire as `AutoPatchFailed` + folded into `BuildDone`

| # | Path | Raised at | Today's text (headline) | Code | What · Why · Remedy | Conf |
|---|---|---|---|---|---|---|
| 1 | airport geometry exception (#559 KPDX) | any `shapely` `GEOSException` / `TopologicalError`, `GeomSafeError`, `PlanarError` inside `auto_patch_v2` build, caught at `auto_patch/engine_v2.py` L421 / `driver.py` L926, stage `build` | `[v2] TopologyException: Ring edge missing at -185.72 80.68` | `airport_geometry` | the airport {airports} could not be processed. · Its pavement outlines produced a shape the app could not work with. · R-REPORT | A |
| 2 | any other exception in an airport build | same catch, stage `build` | `[v2] <str(exc)>` | `airport_failed` | the airport {airports} could not be processed. · The app hit a problem it does not recognise in this airport's data. · R-REPORT | C |
| 3 | pack DSF newer than every cached dump (#560) | `auto_patch_v2/airport/load.py` L441 `RuntimeError` (lane `dump560` is rewording; may split into missing / empty / DSFTool failed) | 600-char refusal with RULINGS keys and `build_airport.py --refresh-data` ×6 airports | `pack_dump_stale` (+ `pack_dump_failed` reserved for dump560's split) | scenery for {airports} could not be read. · The app could not make a readable copy of the scenery pack {pack}'s file for this tile. · R-PACK | B (the pack name needs dump560 to attach it; without it the text says "a scenery pack on this tile") |
| 4 | stale OSM road feed, refresh failed (issue #24) | `driver.py` L1784, before workers; one notice + `STALE_ROAD_FEED_AIRPORT_ERROR` per airport | "not built — the OSM road data for this area is out of date (see the notice above)" per airport | `road_data_stale` | the road data for this area is out of date. · It could not be refreshed, which needs an internet connection. · R-NET | A |
| 5 | solve not optimal / infeasible | `engine_v2.py` L431, stage `solve` | `[v2] the solve for X ended 'infeasible' — …; the IIS is in <path>` | `airport_solve` | the ground at {airports} could not be shaped. · The app found no surface that meets its slope limits for this airport. · R-REPORT | A |
| 6 | law ladder demoted a governed family | `engine_v2.py` L447, stage `solve` | `[v2] the law ladder DEMOTED a governed family at X (scope …): tier 3 (…) …` | `airport_solve` | as row 5 | A |
| 7 | verify DEFECT (#555, #556) | `engine_v2.py` L470, stage `verify` | `[v2] verify found a structural DEFECT in X: pad_flat 3 (…), …` (law-family names) | `airport_verify` | the ground at {airports} failed its final check. · The shaped surface broke one of the app's own rules, so it was not used. · R-REPORT | A |
| 8 | patch placement failed | `engine_v2.py` L509, stage `write` (`os.replace`, `makedirs`, "no face on this tile") | `[v2] [Errno 28] No space left…` or the RuntimeError text | by exception class: `disk_full` / `no_permission` (rows 30–31), else `airport_write` | the result for {airports} could not be saved. · The app could not write its working files. · R-RETRY | B |
| 9 | airport worker process died (segfault / OOM kill) | `driver.py` L1229, stage `worker` | `A process in the process pool was terminated abruptly…` | `airport_worker_died` | work on {airports} stopped unexpectedly. · A background process ended early, most often because the computer ran out of memory. · R-RETRY | B |
| 10 | no result for an airport | `driver.py` L1271, stage `missing` | `no result` | `airport_no_result` | the airport {airports} produced no result. · A background process ended without reporting why. · R-RETRY | C |
| 11 | "success" but no patch / stale patch on disk | `driver.py` L1380/L1390, stage `manifest` | `build reported success but wrote no <file>` | `airport_no_result` | as row 10 | C |
| 12 | no CIFP folder resolves (whole tile, `icao="*"`) | `O4_Vector_Map.py` L2150, stage `config` | `auto-patch failed for * (config): <refusal>` | `airport_data_missing` | X-Plane's airport data was not found. · The app could not find the navigation data in the X-Plane folder it was given. · R-SETTINGS | A |
| 13 | base DEM missing / cold frame inside an airport build | `auto_patch_v2/airport/dem.py` L265 `FileNotFoundError`, `dem_production.py` `ColdDemFrame`, `dem_shared.py` `ColdTile` | `[v2] base DEM missing: … (warm it with …)` / harness wording | `airport_elevation_missing` | elevation data for {airports} was not available. · The detailed elevation for this airport could not be prepared. · R-NET | B (in the app the driver warms these first; reaching here means the warm failed — may really be a bug → master may prefer R-REPORT) |
| 14 | pack write stand-down / backup unproven / stale object plan | `dsf_write.py` `BackupUnproven`, `PermissionError`, `rebake_screen.py` `StaleScreen` / `ColdPartition` — object stage after the mesh | harness wording | `pack_write_failed` | objects for {airports} could not be updated. · The app could not safely rewrite the scenery pack's file. · R-PACK | C — I did not establish that these END the tile (the object stage reports and continues in the paths I read); catalogued so they never show raw if they do |

### Whole-tile exceptions (E2)

| # | Path | Raised at | Today's text | Code | What · Why · Remedy | Conf |
|---|---|---|---|---|---|---|
| 15 | base elevation download failed on the transport (#561) | `O4_DEM_Utils.py` L967/L1354/L1418/L1447 `ElevationDownloadRefused` | traceback + `crashed with an exception (see the console log): ElevationDownloadRefused: elevation cell … REFUSING to build this tile on an all-zero elevation raster; check the network / TLS …` | `elevation_download_failed` | its elevation data could not be downloaded. · The elevation server did not answer, or the connection to it was blocked. · R-NET (+ R-LATER) | A (`demfall561` adds a fallback; this stays for all-sources-failed) |
| 16 | cached elevation frame unreadable | `O4_DEM_Utils.py` L293–L347 `AltFrameRefused` | `crashed with an exception …: AltFrameRefused: …` | `elevation_cache_bad` | saved elevation data for this tile could not be read. · A file left by an earlier build is damaged or out of date. · R-RETRY | B — some callers catch it and rebuild the frame; not every site traced |
| 17 | elevation provider says no / network error not wrapped | `elevation_access` `ProviderUnavailable`, `TransientFetchError` escaping (most are caught in `O4_Airport_Elevation_Insets`) | `crashed …: ProviderUnavailable: …` | `elevation_download_failed` | as row 15 | B |
| 18 | OSM extract filter failure | `O4_OSM_Extract_Filter.py` `ExtractFilterError` ×14 | `crashed …: ExtractFilterError: …` | `map_data_failed` | the map data for this area could not be prepared. · The downloaded OpenStreetMap extract could not be read or filtered. · R-RETRY | B |
| 19 | mesh refusals | `O4_Mesh_Utils.py` `BankAnnulusCollapse` L1488, `InterpAltLeak` L2232; `O4_Vector_Map.py` `UnsealedInterpAltSeed` L3869 | `crashed …: BankAnnulusCollapse: <developer text>` | `mesh_refused` | the terrain mesh could not be built. · The tile's shapes failed one of the app's own safety checks. · R-REPORT | A |
| 20 | no network (generic) | `ConnectionError`, `TimeoutError`, `requests` / `urllib` errors reaching the worker | `crashed …: ConnectionError: …` | `network_unavailable` | something it needs could not be downloaded. · The internet connection failed or the server did not answer. · R-NET | A |
| 21 | disk full | any `OSError` with `ENOSPC` (also `EDQUOT`) | `crashed …: OSError: [Errno 28] No space left on device` | `disk_full` | the disk is full. · There was no room left to write the tile's files. · R-DISK | A |
| 22 | not allowed to write | `PermissionError` / `EACCES` / `EROFS` (incl. `O4_Scenery_Links`, `dsf_write`) | `crashed …: PermissionError: …` | `no_permission` | the app was not allowed to write a file. · A folder it needs is read-only or protected. · R-SETTINGS (**unsure**: "check the folder's permissions" is not in the brief's remedy set) | B |
| 23 | out of memory | `MemoryError` | `crashed …: MemoryError` | `out_of_memory` | the computer ran out of memory. · This tile needed more memory than was free. · R-LATER (**unsure**: honest advice is "close other apps", not in the set) | B |
| 24 | a file the build needs is missing | `FileNotFoundError` (e.g. `load.py` L249 "no apt.dat under <root>", `O4_Default_Terrain_Map` L158, `dsf_write` L1185) | `crashed …: FileNotFoundError: …` | `file_missing` | a file it needs was not found. · It is missing from the X-Plane install, a scenery pack or the app's working folder. · R-SETTINGS | C |
| 25 | shared-repo guard (harness only) | `O4_External_Writes.ExternalWriteRefused` | harness wording | `unexpected_error` (never fires in the app) | — | A |
| 26 | **any other exception** | anything else reaching `_build_worker` L1170 | `crashed with an exception (see the console log): <Class>: <text>` | `unexpected_error` | the app ran into an unexpected problem. · This is a fault in the app, not in your setup. · R-REPORT | C by definition |

### Step returned 0 (E1) — the cause is printed to the console and LOST to the wire

| # | Path | Site | Today's headline | Code | What · Why · Remedy | Conf |
|---|---|---|---|---|---|---|
| 27 | PROJ runtime broken | `_refuse_on_broken_proj` in `O4_Vector_Map` L1255, `O4_Mesh_Utils` L2750, `O4_Mask_Utils` L149, `O4_Tile_Utils` L328 | "the vector data step failed (see the console log)" | `app_component_broken` | a part of the app is not working. · Its map-projection component failed its start-up check. · Reinstall or update the app; if it still fails, R-REPORT | A |
| 28 | previous step's files missing | `O4_Mesh_Utils` L2782/2785/2789 (node/poly/alt), L3080 (mesh), `O4_Mask_Utils` L188, `O4_Tile_Utils` L356 | "the mesh step failed (see the console log)" | `earlier_step_missing` | files from an earlier step are missing. · The step before this one did not finish, or its files were deleted. · Build the tile again with every step selected | A |
| 29 | elevation source undetermined / cached raster mismatch | `O4_Mesh_Utils` L2824/L2832/L2886, `O4_Mask_Utils` L293 | as above | `elevation_source_unset` | no usable elevation source is set for it. · The elevation source in the tile's settings is missing or does not match the saved data. · R-SETTINGS | B |
| 30 | Triangle4XP failed after retries / crashed | `O4_Mesh_Utils` L3011, L3131 | as above ("file a bug including the .node and .poly files" in the console) | `mesh_failed` | the terrain mesh could not be built. · The mesh program stopped, most often because the computer ran out of memory. · R-RETRY | B |
| 31 | assembled .poly unmeshable (hairline preflight) | `O4_Mesh_Utils` L454 | as above (console: RULINGS keys + sliver counts) | `mesh_refused` | as row 19 | A |
| 32 | imagery source unknown / combined provider init failed | `O4_Tile_Utils` L367, L377 | "the imagery/DSF step failed (see the console log)" | `imagery_source_unknown` | no usable imagery source is set for it. · The imagery source named in the tile's settings is not one the app knows. · R-SETTINGS | A |
| 33 | cannot create tile folders | `O4_Tile_Utils` L413 | as above | `output_folder_unwritable` | its output folder could not be created. · The disk is full or the folder is protected. · R-DISK | B |
| 34 | **DSF construction raised** (e.g. default-X-Plane texture mode with no Global Scenery DSF, `O4_DSF_Utils` L834) | `O4_Tile_Utils._build_dsf_guarded` L438 sets `UI.red_flag = True` | **DEFECT FOUND**: the session reads the red flag as a user cancel — the tile is reported **"stopped"**, no `BuildDone`, and the whole run ends as cancelled | `scenery_file_failed` | its scenery file could not be written. · The app hit a problem while assembling the tile's DSF file. · R-REPORT | C (cause class varies: missing Global Scenery → row 24's copy would be better; keyed by exception class when the raise carries one) |
| 35 | every texture download failed | `O4_Tile_Utils` L543 | "the imagery/DSF step failed (see the console log)" | `imagery_download_failed` | its aerial images could not be downloaded. · None of the downloads from the imagery source succeeded. · R-NET (+ R-LATER) | A |
| 36 | DSF rename failed | `O4_Tile_Utils` L557 — prints "tile is not active" and **continues; the step returns success** | (tile reported built) | — | **DEFECT FOUND, not fixed**: a failed activation is reported as a built tile | — |
| 37 | overlay source DSF missing | `O4_Overlay_Utils` L93 | "the overlay step failed (see the console log)" | `overlay_source_missing` | X-Plane's default scenery for this tile was not found. · The overlay is copied from X-Plane's Global Scenery, which is missing for this tile. · R-SETTINGS | A |
| 38 | overlay copy / destination folder failed | `O4_Overlay_Utils` L107, L257 | as above | `output_folder_unwritable` | as row 33 | B |
| 39 | 7-Zip missing / DSFTool crashed (overlay) | `O4_Overlay_Utils` L121, L145 | as above | `overlay_tool_failed` | its overlay could not be converted. · A helper program the app ships did not run. · Reinstall or update the app; if it still fails, R-REPORT | B |
| 40 | any other `return 0` (≈25 unannotated sites in `O4_Vector_Map` 2510–3844, `O4_Mesh_Utils` 614–2210, `O4_DSF_Utils` 1326–2103, `O4_Mask_Utils` 1117/1248) | — | "the <noun> step failed (see the console log)" | `step_failed` | the {step} step failed. · The app did not record a specific cause. · R-REPORT | C by definition |

### Process-level and non-failures

| # | Path | Site | Today | Code | What · Why · Remedy | Conf |
|---|---|---|---|---|---|---|
| 41 | tile worker child died (parallel run) | `parallel.py` L1804 | "build worker exited unexpectedly" | `worker_died` | the build stopped unexpectedly. · A background process ended early, most often because the computer ran out of memory. · R-RETRY | B |
| 42 | user cancel | `session.cancel` / `cancel_tile` | row "stopped" | — | no message (the user's own action) | A |
| 43 | build command refused before any tile starts | `session.build` returns False (a run is already active) → reply `ok=false`; mac prints `*** Build refused: <reply.error>` | reply text | not on the event path — **not changed by this lane** | — | — |
| 44 | engine process missing / cannot start / dies mid-run | app side only (`BuildModel.swift` L410, L502, legacy runner L2166) — the engine cannot speak for itself | "The bundled Ortho4XP engine is missing from this copy of the app." / "*** Build process exited unexpectedly (status N)." | app-owned strings — **not changed by this lane** | — | — |
| 45 | malformed command line | `jsonl.py` L439 `Error(fatal=False)` | "Engine: malformed JSON line …" in the console | not tile-scoped | — | — |

## Rows where I was unsure (for the master's ruling)

* **R-SETTINGS** (rows 12, 22, 24, 29, 32, 37) is a seventh remedy, outside the brief's set. Without it those rows have no honest remedy except "report it".
* Rows 22, 23: the honest advice ("check the folder's permissions", "close other apps") is outside the set.
* Row 3: the pack's name is only inside the exception text today. The catalogue takes it from an explicit `failure_params` attribute on the exception; until `dump560` attaches it the message says "a scenery pack on this tile".
* Row 13: R-NET vs R-REPORT.
* Row 14: tile-ending status not established.
* Rows 9, 30, 41: "ran out of memory" is the most common cause, not a measured one.
* Rows 2, 10, 11, 26, 34, 40: cause class unknown → "report it".
