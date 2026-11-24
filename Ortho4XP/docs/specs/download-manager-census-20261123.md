# Download manager census

Base sha f91a0119c. Date 2026-11-23. Issue #2258.

Made from the issue's grep over `Ortho4XP/src` (67 files hit) plus an AST pass naming each call's enclosing function; fetch bodies, shared helpers, locks and slots were then read. Line numbers are at the base sha; paths are relative to `Ortho4XP/src`. Strategies are grouped only where the cells agree. `not determined` means the code read did not settle the cell.

Step-slot note: any fetch inside a tile step runs under `SLOTS.step` (`o4_engine/session.py:1327`).

## Call sites (32 rows)

| # | Module:function:line | Resource and key | Cache path | Lock | Server limit | Retry/backoff | Stop / timeout | Migration |
|---|---|---|---|---|---|---|---|---|
| 1 | `O4_OSM_Extracts:_download_extract:701` (via `_acquire_extract:917,927`; foreground `_ensure_extracts_foreground:562`; background `_maintenance_loop:975`) | Geofabrik `.osm.pbf`; key = region id + URL. Yes: every tile in a region asks the same key | Region file in `STORE_DIRECTORY`; `<target>.tmp-<pid>-<thread>` then `os.replace` :804 | Foreground: per-process `threading.Lock` per region :569. Background: none. Cross-process: only fresh-`.tmp` heuristic (30 s) :536. No file lock | none | No transfer retry; a 404 re-reads index and retries once at a new URL :922-927. Foreground waiter sleeps 2 s per poll :587 inside the step slot | `red_flag` between chunks :748, in waiter :571; timeout 60 s :53,:721 | **done this round** |
| 2 | `O4_OSM_Extracts:_refresh_index:190` | Geofabrik `index-v1.json`; one global key; shared by all tiles | Store index; `.tmp` then `os.replace` :197-200 (fixed temp name) | none | none | none (returns False) | no check; timeout 60 s | next: same store as extracts; fixed temp name is shared |
| 3 | `O4_OSM_Utils:_post_overpass_query_reporting_progress` POST :1009, driven by `get_overpass_data:1066`; callers :637, :697 | Overpass QL; key = query + bbox; cached by `FNAMES.osm_cached(lat, lon, suffix)`. Tile-scoped; neighbours do not share | `osm_cached` file written direct by `write_to_file:313` (:321/:323), no temp | Per-process `threading.Lock` per cache file :457, :478 | none (own server selection) | 8 tentatives :20; `2**n` s, 429 Retry-After capped 120 s :1195; 1 s slices :1236; in step slot | `red_flag` per attempt :1124, during wait :1038, backoff :1228. Stop abandons the thread. Connect 30 s, read query timeout + 30 s :28-29 | next: not this round (explicitly); needs single-flight per query |
| 4 | `O4_OSM_Utils:_read_overpass_server_status:310` (GET :817) | Overpass `/api/status`; key = server | none (memory) | none | none | none | no check; 5 s + 5 s | never: small liveness probe |
| 5 | `O4_Imagery_Utils:http_request_to_image:1297` (GET :1324/:1328); callers: texture workers from `build_texture_from_tilbox:1731`, `build_texture_from_bbox_and_size:1819`, Qt map, the first-answer session fallback (`O4_Imagery_Async:113`) | One imagery part; key = URL (provider + z/x/y). Overlapping textures of two tiles can ask the same part | Returned in memory; assembled by `download_jpeg_ortho:1983` (next row) | none per part | `hold_class(net_class(url), host_limit)` :1292, bounded 600 s then proceeds unslotted :462,:593 | `O4_Http_Pushback`: Retry-After/backoff, host pause; 10 connect + 10 bad-data retries :74-75; in step slot when run from a step | `red_flag` before request :1320, after answer :1398, `interruptible_sleep`; timeout provider or 10 s :72 | next: largest volume; explicitly not this round |
| 6 | `O4_Imagery_Utils:download_orthophoto_once:2103` -> `download_jpeg_ortho:1983`; `O4_Imagery_Prefetch:download_orthophoto:208` | Whole orthophoto; key = file path (provider + til + zoom). Yes across tiles sharing textures | Imagery cache. `require_complete`: `.part` + `os.replace` :2073. Otherwise direct save :2063-2071 | Cross-process `hold_file_lock(path)` :2118 (900 s, then proceeds); plus per-path `threading.Lock` in Prefetch :213 | per part (row above) | per part (row above) | Lock wait has no Stop check (`O4_File_Lock` has no `red_flag`); parts stop as above | next: already single-flight; adopt the shared job |
| 7 | `O4_Imagery_Fetch:_transfer:851` via `O4_Imagery_Async:fetch_parts:200` (curl_cffi `AsyncSession`) | Imagery parts when fetcher = async; key = URL | Memory; answers handed to `http_request_to_image` via first-answer session `O4_Imagery_Async:113` | none | `try_take_class(net_class(url), 1, limit)` `O4_Imagery_Async:186` | Own AIMD group pause; `max_attempts` 4 :397; 12 pushbacks :144; Retry-After ≤ 120 s :143 | `should_stop` polled, cancels within ~1 s (`O4_Imagery_Fetch:33`); timeout from provider | next: with imagery |
| 8 | `O4_Imagery_Freshness:get:305` (:310), async branch :300 | ≤ 16 sample requests; key = URL | not determined | none | async branch: `host_limit`; threaded branch: none | none | `should_stop` before request :307; timeout provider or 20 s | never: small interactive sample |
| 9 | `O4_Imagery_Sources:_http_get:455` via `probe` | One liveness sample; key = URL | none | none | none | none | no check; 5 s :51 | never: interactive probe |
| 10 | `O4_Airport_Boundary_Zoom:_probe_tile:84` (:97) | One imagery tile; key = provider, zl, x, y | In-process dict `_ANSWERS` :88-90 | none | none | none | no check; 10 s :45 | next: low value; should share imagery host limit |
| 11 | `O4_DEM_Utils:http_request:1484` -> `http_request_get_following_redirects:1426` (:1451); callers `usgs_seamless:78`, `viewfinder_zip:111` | Base DEM file; key = URL (source + tile). Neighbours may share an archive | `usgs_seamless:85` direct write; `viewfinder_zip:181-183` `.part` + `os.replace` | Cross-process `hold_file_lock` on `.lock_<code>_<tile>` `O4_Airport_Elevation_Insets:10773` | `hold_class(net_class(url), 2)` :1513 | 6 attempts (`HTTP_REQUEST_ATTEMPT_CAP` :1403); plain `time.sleep(2**n)` :1608, in step slot and file lock; no Pushback | `red_flag` before each try :1508, in slot :1517, before sleep :1598, not during it; timeout 10 s :1406 | next: explicitly not this round; sleep needs Stop |
| 12 | `O4_Airport_Elevation_Insets:_ask_once` (:5359) + `retry_transient` (:5394) around `fetch_inset:1184` | One airport inset; key = provider + airport bbox + resolution | Inset cache; final `os.replace` :1996, :2665 | `first_answer_gate` per provider (in-process) :5359 | `held_inset_fetch_slot` -> `net:elevation:<code>:insets`, `fetch_slots` or 2 | `retry_transient` 60/180/300 s ±25 %, host pause `fetch_retry:38,:54`; in step slot | Stop-aware slot and rest; transfer per strategy | next: orchestrator for every strategy below |
| 13 | `O4_Elevation_Level:_one:2548` (:2556) -> `fetch_inset` | Approach-ring cell; key = provider, column, row, class. Yes across neighbouring tiles | `cell["path"]`, strategy-dependent | not determined | `cell_fetch_class(provider)`, `APPROACH_RING_FETCH_WORKERS` | strategy-dependent | `red_flag` before and inside slot :2551,:2561 | next: with DEM |
| 14 | `O4_Bathymetry_Band:_fetch_cell:1656` -> `fetch_inset` | Bathymetry cell; key = cell stem; overhang cells shared with neighbour tile | `.part<pid>.tif` + `os.replace` :1713 | Own cross-process band lock :580, Stop-aware :595 | strategy-dependent | Failure skipped, non-durable | `red_flag` before cell :1664 | next: with DEM |
| 15 | `downloads:download_whole:46` (:78), `download_zip_whole:148`; callers `tnm_cog:470,605`, `cwcb_lidar_api:317`, `las_tile_index:930` | Whole zip/raster/LAS; key = `download_url` | `scratch_path` direct; caller `os.replace` (`cwcb:206`, `las:948`) | none in helper | Callers hold `_held_provider_fetch_slot` (`tnm_cog:604`, `cwcb:359`); `las:930` caller not determined | 2 GETs :74; no sleep; caller `retry_transient` (60/180/300 s ±25 %, Stop-aware) | `red_flag` between 1 MiB blocks :112; connect 30, read 120 s | next: already the shared helper; natural first DEM adopter |
| 16 | `las_tile_index:_download_tile:1001` (:1025), `_check_caps:955` HEAD :978, `discover:633` :663 | LAS tile; key = `download_url` | `scratch` resumed with Range, validated, `os.replace` :1097 | none seen | `_held_provider_fetch_slot` :1166 | 2 attempts :1017; no sleep; caller `retry_transient` (60/180/300 s ±25 %, Stop-aware) | `red_flag` between blocks :1064; connect 30, read 120 s | next: merge resume into `download_whole` |
| 17 | `aoi_zip_download:_download:396` (:405), `_query:302` POST :312, `_aoi_open_gate:200` :216 | AOI zip; key = dataset ids + AOI | `<dest>.aoi.zip` direct :469; `is_zipfile` check :493; no `os.replace` | Gate cookie `threading.Lock` :102 | slot from caller | caller `retry_transient` (60/180/300 s ±25 %, Stop-aware); none local | `red_flag` between blocks :429; connect 30, read 120 s | next: duplicate streaming body |
| 18 | `arcgis_export_image:_get_chunk:274` (:287) | exportImage chunk; key = service + chunk bbox | Scratch `chunk%04d` direct :319, :425 | none | caller-held inset/cell slot (`net:elevation:<code>:insets` or `:cells`); none of its own | 3 attempts :84; plain 5 s `time.sleep` :88, :295-356 | `red_flag` per attempt :283, not between blocks; 300 s | next |
| 19 | `arcgis_feature_tiles:_downloaded_members:571` (:585); metadata :143-176, :239, :291, :420; HEAD :471 | Archive by URL (grouped :580); metadata by service | `.arch<n>` scratch, whole body in memory, direct :602 | none | caller-held inset/cell slot (`net:elevation:<code>:insets` or `:cells`); none of its own | caller `retry_transient` (60/180/300 s ±25 %, Stop-aware); none local | no check; 600 s (metadata 60 s) | next: non-streamed whole archive |
| 20 | `tile_grid_http:_download_inputs:439` (:467), `_names_from_http:146`, `_tile_exists:320`; `wfs_tile_index:fetch:156` (:175), `discover:111`; `wcs_kvp:_download:167` (:172); `static_stac:_decode_lerc_sources:292` (:333), `_fetch_json:88` | Provider tile/coverage; key = URL | Scratch next to destination, direct write of a non-streamed body (`tile_grid:473`, `wfs:181`, `wcs_kvp:177`, `static_stac:341`) | none | caller-held inset/cell slot (`net:elevation:<code>:insets` or `:cells`); none of its own | caller `retry_transient` (60/180/300 s ±25 %, Stop-aware); none local | no check; 300 s (index/probe 60-120 s or constant) | next: non-streamed bodies, no Stop |
| 21 | `arcgis_lerc_tiles:fetch:70` (:157); `xyz_text_tiles:_mosaic_to_geotiff:92` (:129) | XYZ tile; key = template + z/x/y | LERC blobs direct in scratch; XYZ in memory | none | caller-held inset/cell slot (`net:elevation:<code>:insets` or `:cells`); none of its own | Failed tile is skipped, no retry | no `red_flag` inside the x/y loops; 60 s | next: serial loops with no Stop |
| 22 | `geojson_tile_index:_tile_entries:64` (:73); `coordinate_named_url_list:_ensure_entries:171` (:187); `os_grid_bucket:_tile_entries:86` (:128) | Provider catalog; key = provider. Yes, shared by all tiles | geojson: `index_path` direct :97-98; coordinate list: scratch + `os.replace` :164; os_grid: `_tile_entries` result, cache not determined | none | caller-held inset/cell slot (`net:elevation:<code>:insets` or `:cells`); none of its own | none local | no check; 180 / 60 / 120 s | next: shared catalogs want single-flight |
| 23 | `discovery:tnm_listing_items:348` (:371); `acquisition_order:_read_metadata_text:73` (:78); `stac:_first_item:109`, `discover:131`, `_request_next_page:248`; `authenticated_token_search:discover:71`, `_redeem_download_href:143`; `degree_named_cog:_url_exists:129` HEAD :148 | Catalog/metadata query; key = URL/body | not determined | none | stac probe holds `_held_provider_fetch_slot` :103; others not determined | caller `retry_transient` (60/180/300 s ±25 %, Stop-aware); none local | no check; 30 s (metadata 15 s :24) | next: metadata lane after whole-file downloads |
| 24 | GDAL `/vsicurl`, `/vsizip//vsicurl`, WCS (`direct_cog:75`, `degree_zipped_cog:82`, `tnm_cog:431`, `wcs:_read_band`, `coordinate_named_url_list:265`) | Range reads of a remote COG; key = URL + window | Warp output at caller destination | none | `wcs._server_slot` :358-370; others caller slot | GDAL: 2 retries, 5 s `O4_Airport_Elevation_Insets:319-325`; WCS bands `retry_transient` :238 | GDAL read has no `red_flag`; WCS checks :287; connect 30, total 600 s, low-speed 1 KiB/s for 60 s | never as a byte stream (GDAL owns it); manager may own slot and retry |
| 25 | `O4_Coral_Atlas:download_file:418` (:423), `_request:339` (:344) | Atlas package / API call; key = tile package | `<tile>_package.zip` direct :566-569, :433 | none | none | none | no check; 600 s / 120 s | never: user-initiated, credentialed; at most atomic write |
| 26 | `runway_ref_ourairports:refresh:91` (`fetch:98`, :100) | `runways.csv`; global key | `.part` + `os.replace` | none | none | none | no check; 120 s | never: harness refresh only (:93) |
| 27 | `gateway_api:_http_fetch:43` (:46) | Gateway API/pack; key = URL | Memory | none | none | none | no check; 90 s :32 | never: single interactive read |
| 28 | `patch_library.client:fetch:47` (:54); `github:_urllib:49` (:52) | Library file / GitHub API | Memory | none | none | none | no check; 30 s / 60 s | never: interactive library operations |
| 29 | `probe_signed_in:450`, `sign_in_api_key:532`, `keycloak_password_login:730` | Account session probe/login; key = session name | Cookie jar file | none | none | none | no check; 30 s | never: interactive credential flow |
| 30 | `O4_Flight_Plan:fetch_simbrief:369` (:376) | SimBrief plan; key = user | Memory | none | none | none | no check; 20 s | never: interactive |
| 31 | `O4_Proj_Runtime:tls_selfcheck:227` (:239, GDAL :250) | Diagnostic URL | none | none | none | none | no check; 30 s | never: CLI self-check |
| 32 | `O4_Qt_Map` session :357, fetch :1244-1250 via `get_wmts_image` / `http_request_to_image` | Map preview tile; key = code, z, x, y | Preview cache, write not determined | none | none: no `host_limit` passed :1248 | Inherits `http_request_to_image` | Inherits it; provider timeout | never: interactive preview |

## Excluded (22 files)

- `O4_File_Lock.py`: hostname for lock identity
- `O4_Http_Pushback.py`: retry helper; makes no request
- `O4_Machine_Slots.py`: URL parsing in `net_class`
- `O4_Qt_Settings.py`: account-session UI text and fields
- `O4_Step_Reuse.py`: `urllib.parse` only
- `O4_Unmounted_Links.py`: `urllib.parse` only
- `O4_XPlane_WebAPI.py`: loopback X-Plane Web API (`localhost`, :103-117, :275)
- `auto_patch/build_support.py`: `urllib.parse` only
- `auto_patch/engine_v2.py`: `urllib.parse` only
- `auto_patch/object_anchor.py`: variable names containing `requests`
- `auto_patch/object_frame.py`: variable name containing `requests`
- `auto_patch/provenance.py`: `urllib.parse` only
- `elevation_access/base_fallback.py`: `urlparse` only
- `elevation_access/definitions.py`: definition key read
- `elevation_access/failures.py`: error-text classification
- `o4_engine/download_meter.py`: instrumentation on `Session.send`; no request of its own
- `o4_engine/failure_report.py`: `urllib.parse.quote`
- `o4_engine/parallel.py`: comment / `session` attribute matches
- `o4_engine/redaction.py`: hostname redaction
- `o4_engine/session.py`: account definition fields
- `o4_engine/slow_step.py`: message text
- `tile_bundle/paths.py`: `urllib.parse.quote`

## Findings

1. No cross-process single-flight on the extract download: the foreground lock is a per-process `threading.Lock` (`O4_OSM_Extracts.py:525,569`), the background path takes none (`:985,:998`), and the only cross-process signal is a fresh `.tmp` check (`:536`).
2. `_another_downloader_active` deletes any sibling `.tmp` not modified for 30 s (`O4_OSM_Extracts.py:553-556`, constant `:59`), including a live download of another process whose stream stalled that long; that writer's install at `:804` then cannot use its file.
3. `hold_file_lock` waits up to 900 s with no Stop check: `O4_File_Lock.py` contains no `red_flag` (`:204,:283`). It guards orthophotos (`O4_Imagery_Utils.py:2118`) and base DEM (`O4_Airport_Elevation_Insets.py:10773`).
4. A tile step holds its machine slot for its whole body (`o4_engine/session.py:1327`); `lend()` has one caller (`auto_patch/driver.py:1491`), and no network wait lends it. The foreground extract poll (`O4_OSM_Extracts.py:587`), Overpass backoff (`O4_OSM_Utils.py:1236`) and DEM backoff (`O4_DEM_Utils.py:1608`) wait inside it when run from a step.
5. `O4_DEM_Utils.py:1608` is a plain `time.sleep(2 ** tentative)`; Stop is checked before it (`:1598`), not during it. `arcgis_export_image.py:295-356` likewise sleeps 5 s uninterruptibly.
6. `take_class` gives up after 600 s and the caller proceeds with no slot (`O4_Machine_Slots.py:462,593-613`), so server limits are bounded-wait, not strict.
7. Overpass has no server slot class and no cross-process lock; its cache lock is per-process (`O4_OSM_Utils.py:457,478`) and the cache file is written directly (`:321,:323`).
8. Direct writes to a final cache path with no atomic rename: `usgs_seamless.py:85`, `geojson_tile_index.py:97-98`, `O4_Coral_Atlas.py:433`, and non-`require_complete` orthophotos (`O4_Imagery_Utils.py:2063-2071`).
9. No `red_flag` during transfer: `arcgis_export_image.py:320` (block loop), `O4_Coral_Atlas.py:434`, and the serial tile loops `arcgis_lerc_tiles.py:149-157`, `xyz_text_tiles.py:121-129`.
10. Whole bodies held in memory before writing: `arcgis_feature_tiles.py:585,602` (600 s), `tile_grid_http.py:467,473`, `wfs_tile_index.py:175,181`, `wcs_kvp.py:172,177`, `static_stac.py:333,341`.
11. Three streaming bodies do the same job: `downloads.py:78`, `las_tile_index.py:1025`, `aoi_zip_download.py:405`; `downloads.py:60-62` names a second streaming downloader as a defect.
12. `O4_Qt_Map.py:1248` calls `http_request_to_image` without `host_limit`, so the map preview does not count against the `net:<host>` budget (`O4_Imagery_Utils.py:1289`).

## Status after round ldl1

The table above describes the base sha. This round changed only the following.

| Item | State |
|---|---|
| Manager core (`src/O4_Download_Manager.py`): single flight by key, atomic install, stale temporary cleanup, Stop, per-server and total limits, per-resource request count | built |
| Row 1, OSM regional extracts | migrated |
| Row 2, Geofabrik index | not migrated; its temporary is now private to the writer |
| Finding 2 (a live `.tmp` deleted after 30 s) | removed with `_another_downloader_active` |
| Waits on another tile's download, an Overpass backoff or a contended `hold_file_lock` | the step holds no slot (`src/O4_Step_Wait.py`, `src/o4_engine/step_parking.py`) |

## Status after round limg1

Imagery downloads no longer belong to a build step. `O4_Imagery_Prefetch.open_job` starts one job per tile with the vector step; it takes the parent's imagery token when one frees (`imagery_token`, returned by `ImageryJobDone`), runs through solve, mesh and masks, and the imagery step adopts it. A first build names its textures with `O4_Imagery_Plan.predicted_textures`. Transfers still go through row 5's `net:` classes, so a flight hold pre-empts them. Row 5 is not migrated onto `O4_Download_Manager.fetch`: the job is the caller a thin `ensure(resource, needed_by, priority)` would replace.

Next, in order: Overpass layers, base DEM cells, elevation insets, imagery. Each moves onto `O4_Download_Manager.fetch` with its own key; none was migrated this round.

## Status after round lrm1

| Item | State |
|---|---|
| Manager core | `fetch(..., transfer=)` for a caller that makes the bytes itself (single flight, atomic install, Stop, request count kept; the transfer holds its own server's limit); `Resource.shares_failure` and `state_dir`; `hold_flight` (a work section once at a time across processes, Stop-aware, no time limit, its `.lock` file removed by the holder); `server_slot` (one server slot and one total slot, Stop-aware, no time limit); `write_body` (a streamed body to a file, Stop between chunks); a joiner's wait and a slot wait hold no scheduler slot |
| Row 3, Overpass layers | migrated: `O4_OSM_Utils.cache_layer_once`, key `osm-layer:<cache file>`, cache written to a private temporary and installed with one rename, validated by its tag schema; `airport_small_roads` (`O4_Vector_Map`) through the same call; each POST holds `server_slot` of its Overpass server; Stop is looked at every 0.25 s while a server works |
| Row 11, base DEM cells | migrated: `elevation_access.base_tiles.fetch_base_file`; `usgs_seamless` keyed per cell, `viewfinder_zip` keyed per ARCHIVE (the cells of one zip share one download); `DEM.http_request(destination=)` streams the body with Stop; the back-off sleeps in Stop-aware slices; `ensure_base_tile`'s 900 s `hold_file_lock` is now `hold_flight` |
| Row 12, elevation insets | `ensure_airport_insets` runs once per tile at a time across processes (`hold_flight` on `<tile>_airport_insets/.insets.lock`): the second pass reads the first one's index and rasters; install (scratch + land) and limits (`held_inset_fetch_slot`) were already the inset's own |
| Finding 3 | closed for base DEM and the neighbour frame warm (`O4_Vector_Map.ensure_tile_frame`); orthophotos still use `hold_file_lock` |
| Finding 5 | closed: `O4_DEM_Utils` back-off, `arcgis_export_image` retry rests (`O4_Http_Pushback.interruptible_sleep`, now counted slices) |
| Finding 7 | closed (Overpass slot class and cross-process single flight) |
| Finding 8 | closed for `usgs_seamless` and the Overpass caches; `geojson_tile_index`, `O4_Coral_Atlas` and non-`require_complete` orthophotos remain |
| Finding 9 | closed for `arcgis_export_image`'s block loop and the `arcgis_lerc_tiles` / `xyz_text_tiles` tile loops; `O4_Coral_Atlas` remains |
| Not this round | imagery (rows 5-8), approach-ring cells (row 13), bathymetry (row 14, changed by #2265), rows 15-23's own bodies, the Geofabrik index (row 2) |

## Design note: the rest of the resource manager (not built)

The owner's direction on #2258: one manager in charge of making resources available where and when they are needed, including external drives, downloading, offloading to stay within the budget, and anticipating what running builds and active flights will need. The shape is one call, `ensure(resource, needed_by, priority)`, that answers from the local copy, else recalls the file from a tier drive, else downloads it (`O4_Download_Manager.fetch`), making room first when the budget needs it.

What already does part of it (`tools/blast.py --find storage`, `--find offload`, `--find prefetch`):

| Job | Modules today | Gap |
|---|---|---|
| Fetch once, Stop, server limits | `O4_Download_Manager`; `O4_Machine_Slots` `net:` and `download-total` classes | Imagery still outside it |
| External drives | `o4_engine/storage_tiers` (tiers per mount), `o4_engine/storage_tier_data` (rebuild data on a tier, `_recall_tree` per tile), `O4_Unmounted_Links` | Recall is per tile and after the fact; a download does not ask a tier first |
| Offload within the budget | `o4_engine/storage_budget` (one disk budget), `storage_priority` (`offload`, what goes first), `storage_offload` (after each build run), `storage_floor` (free-space floor), `storage_room` (room before a run), `world_drape_evict` | Runs before or after a run, never before one install of known size |
| Anticipation | `O4_Imagery_Plan` (textures named before the mesh), `O4_Imagery_Prefetch` (per-tile imagery job), `O4_Imagery_Page_Ahead` and `o4_engine/imagery_follow` (deadlines along a flight), `O4_Vector_Map.start_background_osm_prefetch`, `O4_Bathymetry_Band.prefetch_bathymetry_band` | Separate queues; no shared order by deadline |
| CPU and memory while waiting | `O4_Machine_Slots`, `O4_Machine_Memory`, `O4_Step_Wait` | Done for waits on the manager |

Order I would migrate them in:

1. Imagery onto `fetch` (rows 5 and 6): one key per orthophoto, the per-tile job of limg1 as the first caller; this also retires the orthophotos' `hold_file_lock` (rest of finding 3) and their direct save (rest of finding 8).
2. Recall before download: `fetch` asks the tier index for the target's path before it transfers, so a tier hit is a copy and no request. `storage_tier_data` needs a lookup by path, not only by tile.
3. Room before install: a flight that knows its length asks `storage_room` / `storage_floor` for those bytes before it installs, with `storage_priority` choosing what moves; the after-build `storage_offload` stays as the sweep.
4. `needed_by` and `priority`: one queue of flights ordered by deadline, an active flight's page-ahead deadlines first, then the running builds by step; `O4_Imagery_Page_Ahead`, `imagery_follow` and the per-tile imagery job become producers of requests. The accuracy of first-build texture prediction (on water especially) is measured before this step, as #2258 asks.
5. The remaining census rows as callers: approach-ring cells (13), bathymetry once #2265 has settled (14), shared catalogs (22, 23), the Geofabrik index (2).
