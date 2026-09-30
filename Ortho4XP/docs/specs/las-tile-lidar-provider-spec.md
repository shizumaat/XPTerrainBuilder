# LAS-TILE LIDAR PROVIDER — A POINT-CLOUD TILE INDEX GRIDDED IN-ENGINE TO A 1 m DTM, DELIVERED THROUGH THE EXISTING INSET PIPELINE; FIRST INSTANCE PITKIN1M (KASE); THE LADDER GOES CROSS-PROVIDER AND RE-CHECKS ITS FINER RUNGS AT EVERY BUILD

Fable 2026-09-30. Issue **#130**. Owner law: RULINGS **30av** (`Ortho4XP/docs/RULINGS.md:9456`, Q-130 (a)), **30aw** (`:9454`, amendments: provider ON, no licence switch; watcher DROPPED for a build-time re-check), findings **30au** (`:9458`) + the three scout comments on #130, ladder **30ab** (`:9496`), transport law **30t** (`:9512`), consumer census **30l** (`:1946`), shared repo **e9daef5** (`tools/harness/shared_repo_guard.py:1-22`). Read-only spec; ONE new file. All engine paths are `Ortho4XP/src/O4_Airport_Elevation_Insets.py` unless named (13,260 lines; cite as `INSETS:<line>`).

## §0 THE FACTS THIS SPEC DESIGNS AGAINST (30au, #130 scouts)

| # | fact | number |
|---|---|---|
| 1 | KASE today | 10 m rung (1/3″, 1958 contour-derived), 100 % valid, 532 × 712 px, 9 sources (30ab); census sw1002_KASE 3,279 adjudicated, 0 runway movers (`RULINGS:9464`) |
| 2 | USGS 1 m at KASE | 3 products list, 0.22 % valid; cell x33y435 absent from all 22 CO projects |
| 3 | Pitkin County 2016 lidar | 63 tiles over the KASE inset box, 7.06 GB; airfield = LD26071512 / LD26101509 / LD26131503 ≈ 250 MB; LAS 1.4 pf6 UNCOMPRESSED, 3,000 × 3,000 ft (914.4 m); 3.30–3.74 pts/m² all returns; RMSEz 4.5 cm; EPSG 6428 (NAD83(2011) CO Central ftUS), NAVD88 ft, Geoid12A |
| 4 | Index | `https://maps.pitkincounty.com/arcgis/rest/services/Hosted/Contour_and_LiDAR_Index_(HFV)/FeatureServer/6/query?geometry={west},{south},{east},{north}&geometryType=esriGeometryEnvelope&inSR=4326&spatialRel=esriSpatialRelIntersects&outFields=name&returnGeometry=false&f=json` |
| 5 | Tile | `https://maps.pitkincounty.com/downloads/elevation/2016_LiDAR/Classified_LAS1.4/2016-{name}.las`; metadata `…/2016_LiDAR/metadata/2016-Pitkin_Classified_Lidar.xml` |
| 6 | Licence | county disclaimer only (liability); owner 30aw: no restriction published, no charge, no redistribution → SHIP ON |
| 7 | USGS `CO_CONMGaps_D24` QL1 | footprint includes KASE, Aspen unit unpublished; will appear as a TNM 1 m / OPR product over the box |
| 8 | venv | Python 3.14.3, numpy 2.4.4, scipy 1.17.1, requests 2.33.1, GDAL 3.12.3 (`Ortho4XP/requirements.txt:1-19`); NO laspy / pdal / lazrs |
| 9 | Inset box | airport bbox + `airport_elevation_inset_margin_m` 2000 m (`INSETS:8845`); frame check box = +1000 m (`INSET_FUNCTIONAL_MARGIN_M`, `INSETS:7485-7501`) |
| 10 | Bake rule | `INSET_MIN_VALID_FRAC` 0.05 (`INSETS:9609`); below it the raster is DECLINED (`INSETS:7636-7667`) |

## §1 THE PROVIDER CLASS — `access_strategy=las_tile_index`

One new strategy class `LasTileIndexStrategy` registered `@register_access_strategy("las_tile_index")` beside the others (`INSETS:1313-1322`; registry list `:1883-12673`), `supports_wide_area = False` (a 7 GB point cloud is never a whole-tile overlay; `O4_Elevation_Level.py:245-250` then skips it). Zero orchestration edits for the class itself (module law, `INSETS:10-20`). Declarative keys, `Providers/Elevation/PITKIN1M.elv` (format: `USGS3DEP.elv`; parser `initialize_elevation_providers_dict`, `INSETS:688-780`):

| key | PITKIN1M value | rule |
|---|---|---|
| `role` | `airport_inset` | :1175 |
| `access_strategy` | `las_tile_index` | mandatory (:743) |
| `index_url_template` | §0 #4 | `{west},{south},{east},{north}` EPSG:4326, the tnm_cog idiom (:1900-1907) |
| `index_name_field` | `name` | the attribute that names a tile |
| `tile_url_template` | §0 #5 | `{name}` substituted |
| `source_crs` | `6428` | EPSG of the point coordinates; a tile whose header CRS disagrees is refused (§2) |
| `vertical_unit` | `ftUS` | `ftUS` (0.3048006096 m) / `ft` / `m` |
| `vertical_datum` | `NAVD88` | copied into the sidecar (:2052); one datum per provider (:1790) |
| `ground_classes` | `2` | comma list of ASPRS classes gridded; `withheld`-flagged points dropped |
| `grid_resolution_m` | `1` | the DTM cell in the SOURCE CRS |
| `native_resolution_m` | `1` | what every reader clamps to (:8937-8957, :13079) |
| `min_points_per_cell` | `1` | a cell with fewer ground points is empty before fill |
| `fill_radius_cells` | `3` | nearest-fill reach (§3); beyond it NoData |
| `max_tiles_per_airport` | `64` | KASE = 63; refusal wording §2 |
| `max_bytes_per_airport` | `8000000000` | KASE = 7.06 GB |
| `keep_raw_las` | `true` | raw tiles stay in the cache so a grid-rule change re-grids without a 7 GB download |
| `rmse_z_m` | `0.045` | declared accuracy, recorded |
| `coverage_bbox` | `-107.40,38.95,-106.30,39.55` | Pitkin County hull (lane verifies against the county boundary); outside it a capability-free durable no-coverage with no network call (:7932-7940) |
| `priority` | `90` | BELOW USGS3DEP's 100: PITKIN1M reaches an airport as USGS3DEP's ladder rung (§4), and standalone only when pinned (`airport_elevation_providers=PITKIN1M`) |
| `license` | `Pitkin County GIS open data (disclaimer only)` | |
| `license_note` | `No use restriction published; not charged for, not redistributed as data (owner RULINGS 2026-09-30aw); disclaimer: <URL the lane records from maps.pitkincounty.com>` | copied verbatim into every sidecar |
| `attribution` | `Pitkin County, Colorado — 2016 LiDAR (Merrick & Co. for CWCB)` | sidecar + pack NOTICES (`scripts/make_notices.py`) |
| `enabled` | `True` | 30aw (1) |

No `requires_license_ack` (dropped by 30aw). `provider_required_capabilities` (`INSETS:901-917`) gains `CAPABILITY_LAS` for `access_strategy=las_tile_index`: an engine without laspy raises `ProviderUnavailable("laspy missing")` (:342-360) → `unavailable:` status, never no-coverage, re-probed once laspy is present (13b door, :971-1017).

## §2 THE FETCH

**Discovery** = one GET on `index_url_template` through `discovery_json_payload` / `discovery_listing_items(payload, …, items_key="features")` (`INSETS:512-600`): 5xx/429/non-JSON → `TransientFetchError`; an ArcGIS body `{"error": …}` with HTTP 200 is TRANSIENT (a protocol answer, not a coverage answer, the :447-460 class); a well-formed empty `features` list is durable no-coverage. Names sorted; the list is the `sources` (`source_id` = name). Over `max_tiles_per_airport` or `max_bytes_per_airport` (Content-Length HEAD sum): `ProviderUnavailable` with the wording `PITKIN1M: KASE needs 71 tiles / 7.9 GB, cap 64 / 8.0 GB (max_tiles_per_airport / max_bytes_per_airport in PITKIN1M.elv) — SKIPPED, recorded unavailable, not no-coverage`.

**Per-tile GET**: `requests.get(stream=True)` into a lane-local scratch `destination_path + ".las%d.part"` (the `.tile%d` idiom, :4770-4780) under `_held_provider_fetch_slot(code)` (:257). Resume: an existing `.part` sends `Range: bytes=<size>-`; 206 appends, 200 restarts, anything else per :419-430 / :482-495 (TLS, timeout, 5xx → transient; a listed tile answering 404 is stamped `tiles_missing` in the sidecar and its cells stay NoData; ALL listed tiles 404 → `ProviderUnavailable("index lists N tiles, server has none")`, retried next run). Integrity before caching: magic `LASF`, `point_data_record_format` 6, `point_count × record_length + offset == size`, header CRS WKT/GeoKey EPSG == `source_crs` (a `.laz` or a compressed pf → `ProviderUnavailable("LAZ needs a backend")`, never no-coverage). A passing tile is `os.replace`d into the cache.

**Cache** (shared repo, e9daef5): `Elevation_data/_las_tiles/<CODE>/<name>.las` + `<name>_dtm.tif` + `<name>_dtm.json` (§3, per-tile grid, re-used across airports and re-cuts). NEW SCOPE `("las_tiles", "Elevation_data/_las_tiles", "raw lidar point-cloud tiles and their per-tile gridded DTMs (LAS-tile providers)")` inserted BEFORE `dem` in `REFRESH_SCOPES` (`shared_repo_guard.py:69-90`; `scope_of` takes the first matching prefix, `:137-147`). The airport inset itself stays under `dem`. A build never writes either: the guard refuses at the call site and the harness names `--refresh-data las_tiles,dem` (`build_airport.py:558-613`, `:1253-1269`). Locked per scope (`RefreshLock`, `:398`), hash-stamped in `.harness/refresh_ledger.jsonl` (`:484`). The lane's warm command: `venv/bin/python tools/harness/build_airport.py KASE --refresh-only --refresh-data las_tiles,dem --warm-insets KASE` (`build_airport.py:1273-1376`). Wall: 7.06 GB at ~10 MB/s ≈ 12 min once; gridding ≈ 63 × ~4 s.

## §3 THE GRID — BINNING MEAN + BOUNDED NEAREST FILL, in the source CRS, then the shared warp

Per tile, `laspy.open(path).chunk_iterator(2_000_000)` (bounds memory at ~60 MB per chunk); keep `classification ∈ ground_classes` and not `withheld`; X/Y/Z scaled by the header. Grid in EPSG 6428 at `grid_resolution_m / 0.3048006096` ftUS (3.2808 ft) anchored on the tile's header min X/Y so adjacent tiles share cell edges; `np.bincount(cell_index, weights=z)` / `np.bincount(cell_index)` → mean per cell (O(n), sequential summation → bit-identical across arm64/x86/Windows, the 17b-17d concern), `count < min_points_per_cell` → empty. Z × 0.3048006096 → metres NAVD88. Fill: up to `fill_radius_cells` rounds of 3×3 mean-of-valid dilation (numpy, no scipy); a cell still empty is NoData (−32768 f32) and is left to the bake's valid-fraction rule and to the base DEM under the bake (the KMCI partial-mosaic behaviour, :9598-9612). Written as a deflate GeoTIFF with EPSG 6428 georeferencing plus `<name>_dtm.json` {`points_total`, `points_ground`, `ground_density_per_m2`, `cells_valid`, `cells_filled`, `fill_radius_cells`, `vertical_unit`, `source_crs`, `laspy_version`, `grid_rule_version`}.

Why not TIN/IDW: at ~1.5–2.5 ground pts/m² over an open airfield a 1 m cell holds 1–3 points; a TIN of ~2.7 M points per tile (scipy Delaunay, ~20 s, non-deterministic tie handling) adds facets across voids and nothing over pavement; IDW smears the 4.5 cm noise into neighbours. Mean binning is the estimator with the declared RMSE; the 3-cell fill closes the gaps a low-density swath leaves without manufacturing hydro-flat plateaus that the water-supplement detector reads as lakes (:8640-8675; filled fraction is recorded so a lane can bound it — acceptance §8 caps it at 5 %).

Assembly: every covering `<name>_dtm.tif` (local paths are lawful warp inputs, :4745-4780) → `warp_vsicurl_sources_to_geotiff(inputs, bbox, 1.0, destination, source_srs="EPSG:6428", source_nodata=-32768)` (`INSETS:1620-1660`): EPSG:4326 float32 at 1 m, the same target every raster provider delivers. Vertical: NOT shifted (the `datum_note`, :2053-2056); NAVD88 is what the USGS rungs deliver, so the 10 m → 1 m change at KASE moves no datum.

## §4 DELIVERY — THE SAME CONTRACT AS `tnm_cog`, THE LADDER GOES CROSS-PROVIDER (30aw (2))

Sidecar (`FNAMES.airport_inset_provenance`, written :8110-8114; keys as :2037-2068): `provider`, `access_strategy`, `source_urls` (tile URLs), `source_ids` (tile NAMES — `dem.py:277` joins them), `sources_used` [{title: name, publication_date: "2016-08", source_id: name}], `sources_empty_over_bbox`, `tiles_missing`, `valid_fraction`, `filled_fraction`, `point_density_per_m2` (ground, over valid cells), `rmse_z_m`, `license`, `license_note`, `attribution`, `vertical_datum`, `vertical_unit_source`, `source_crs`, `datum_note`, `native_resolution_m` 1, `resolution_m`, `fetch_date`, `bounding_box_wgs84`, plus the additive `requested_/delivered_bounding_box_wgs84` (:1388-1400).

**Order at an airport** (owner 30aw): USGS3DEP 1 m → PITKIN1M 1 m → USGS 3 m → USGS 10 m. Mechanism: the 30ab ladder generalised so a rung MAY BE ANOTHER PROVIDER. `USGS3DEP.elv` gains one line, `resolution_ladder=1|Pitkin County 2016 lidar|provider:PITKIN1M`, before the 3 m and 10 m lines; `_parse_resolution_ladder` (`INSETS:649-686`) accepts `provider:<CODE>` in the third field (the sort by `native_resolution_m` at :684 is stable, so the file order breaks the 1 m tie); `_ladder_rung_definitions` (:1416-1435) returns the named provider's OWN definition (its keys, strategy, coverage) for such a rung, and `_fetch_through_resolution_ladder` (:1438-1560) resolves the strategy PER RUNG instead of reusing the caller's. A provider rung whose `coverage_bbox` misses the box is outcome `out-of-coverage` with no network call (:1293-1310) — outside Pitkin County the KASE rung costs every US airport nothing. The delivered raster keeps the chain's file name (`KASE_usgs3dep.tif`, :1546) while `provider` reads `PITKIN1M`; the `ladder` block (:1548-1556) gains `delivered_provider` and, per rung, `listing_ids` (the discovery listing at fetch time: source ids / tile names). Selection stays by descending `priority` and first-`ok` break (`INSETS:1195-1206`, `:8126`); nothing else in the loop changes.

**Re-check at every build** (30aw (2)): in the warm-cache branch (`INSETS:7843-7890`, the chain of `stale_reason` predicates) one more predicate, `ladder_recheck(lat, lon, icao, code, bounding_box)` — THE ONE DERIVATION SITE, also called by the harness frame check (`build_airport.py:795`) — runs when the sidecar's `ladder.delivered_rung > 0`: for each finer rung it calls that rung's `discover()` only (tnm_cog: one TNM GET ≈ 1 s, :1900-1913; PITKIN1M: one index GET) and compares the listing to `listing_ids`. A NEW id → `cached_inset_is_stale = True`, reason `"a finer ladder rung now lists new coverage (<ids>)"`, and the existing refetch-beside-and-replace path runs (:7999-8003, :8080-8090, :8110) — the whole ladder re-runs, so a 1 m product that lists but grids below 5 % (KASE's 0.22 %) leaves the delivered rung where it was. Unchanged → no download. Discovery transient → `result: "transient"`, the cached inset stands (30t: an outage is no answer). Result stamped `ladder.recheck = {"rung": <finest rechecked>, "checked": <date>, "result": "unchanged"|"new-listing"|"transient", "new_source_ids": [...]}`, rewritten only when `result`/`new_source_ids` differ from the stored block (a byte-identical sidecar is never rewritten; a date-only change is not a change). Harness: the recheck's DISCOVERY runs (a read); a `new-listing` fetch is a shared-repo write → the pre-build frame check REFUSES naming `--refresh-data dem` (`,las_tiles` when the PITKIN1M rung is among the finer ones), `--allow-degraded-dem` records the stand-pat; `frame.json` carries `ladder_recheck` (`build_airport.py:4088` idiom). Cost per KASE build: 1 TNM query (delivered by rung 1) ≈ 1 s; 2 queries when delivered by 3 m/10 m.

## §5 CONSUMER CENSUS (30l) — every reader of an inset raster / sidecar / provenance

| consumer | reads | ruling |
|---|---|---|
| fetch loop `INSETS:7843-8130` | priority order, coverage pre-filter, `ok`/`no-coverage`/`unavailable` | unchanged; recheck predicate added at :7890 |
| `fetch_inset` :1326 / ladder :1438 | strategy dispatch; rungs | per-rung strategy (§4); no other edit |
| `cached_inset_declined_reason` :7636, `_void_inset_record_reason` :7676 | raster content | unchanged (content, not index) |
| bake :9684 + manifest entry :9790-9815 | `provider`, `source_ids`, `fetch_date`, `native_resolution_m`/`resolution_m` | all stamped (1/1); NoData → base DEM |
| `airport_inset_frame_problem` :10971 | missing/stale/empty; only a `None` status is "never answered" (`unanswered_inset_providers` :10937-10967) | `unavailable:` reads as answered → never a false `missing`; recheck result surfaced |
| `_honest_inset_resolution_m` :11869, `resolve_working_grid_factor` :11792, densify :12350 | `native_resolution_m` | 1 m → densify engages as for USGS 1 m |
| water-supplement trust :8659-8675 | native vs fetched | 1 == 1 → trusted; fill bounded (§3) |
| `O4_Elevation_Level.py:236-258` | `supports_wide_area` | False → excluded |
| `auto_patch_v2/airport/dem.py:255-280` | `provider`, `source_ids`, `vertical_datum` | tile names, NAVD88 |
| `dem_production.py:130-150`, `:440-530` | frame problem; source pixel from `native_resolution_m` | 1 m |
| `auto_patch/provenance.py:240-335` → `pipeline.py:4518` → `flat_site.py:228-240`, `bridges.py:755-772`, `building_feasibility.py:158-172`, `flat_fast_path.py:172-186`, `layout.py:3608-3618` | `insets[].native_resolution_m`, `provider`, label tags into the patch header | finest = 1 m; labels read `PITKIN1M`; census evidence = these tags (no other census reader: `tools/harness/census.py` has no inset key) |
| harness `build_airport.py:795`, `:1364-1376`, `:4088` | frame check, warm summary valid fraction, `frame.json` | + `ladder_recheck` |
| `O4_Bathymetry_Band.py:243`, `_refuse_mixed_vertical_datums` :1790 | role / datum | untouched |
| app `SettingsLayout.swift:105` (`airport_elevation_providers`, free string; schema snapshot :160) | no enumeration | no change; `auto` includes the rung |
| `provider_required_capabilities` :901, `negative_is_unverified` :971, `negative_is_version_stale` :1033 | capability stamps | + `CAPABILITY_LAS` |

## §6 THE DEPENDENCY

`laspy==2.6.1` (or the current 2.x the lane pins) in `requirements.txt` (`reqs-frozen.txt` filter follows, `scripts/make_engine.sh:70-76`): pure Python + numpy, `py3-none-any` wheel — macOS arm64/x86_64, Windows, Linux; NO LAZ backend (lazrs/laszip) because pf6 uncompressed needs none (§2 refuses `.laz` loudly). Imported lazily inside the strategy → the twin `tests/test_freeze_requirements_cover_lazy_imports.py:73-83` requires the pin; hiddenimports `collect_submodules('laspy')` in both `Ortho4XP.spec:107` and `Ortho4XP_Qt.spec:133`. Frozen smoke: `--import-selfcheck laspy` beside `--tls-selfcheck` (`O4_Proj_Runtime.py:262-268`), run by the existing CI freeze job.

## §7 THE 2024 USGS UNIT — the build-time re-check REPLACES the watcher (30aw (2))

No `tools/usgs_3dep_watch.py`, no workflow, no `elevation_watch.toml`. When USGS publishes `CO_CONMGaps_D24`'s Aspen unit, the next build of +39-107 sees a new 1 m product id in TNM's listing (§4 recheck), refetches, measures, and delivers the 1 m USGS rung if ≥ 5 % valid; PITKIN1M stands otherwise. #130 stays open until that build is observed; the recheck line names the new ids.

## §8 ACCEPTANCE

1. KASE after `--refresh-only --refresh-data las_tiles,dem --warm-insets KASE`: `KASE_usgs3dep.json` `ladder.delivered_rung=1`, `delivered_provider=PITKIN1M`, `native_resolution_m=1`, `valid_fraction ≥ 0.95` (bake threshold 0.05), `filled_fraction ≤ 0.05`, `point_density_per_m2` ≥ 1.0, `rmse_z_m=0.045`, `source_ids` ⊇ {LD26071512, LD26101509, LD26131503}; ledger has one `las_tiles` and one `dem` line.
2. `build_airport.py KASE` builds; census vs `frames/reference/sw1002_KASE.osm` (`RULINGS:9464`): runway movers 0 at `--tol 0.02` (CIFP pins are truth); taxi/apron/pad rows re-read against 1 m — quote CRITICAL motion (sw1002: 3,279 adjudicated) before/after with the worst site as lat, lon; no ruling on the numbers by the lane.
3. HECA / KCLT / SPJC / CYXY: sidecars and rasters byte-identical (no coverage-box hit, no network); the recheck runs at none (delivered_rung 0).
4. Twins in `tests/test_inset_resolution_ladder.py` (10 today): provider rung resolution; out-of-coverage rung makes no call; fake finer rung [] → listing between two builds → refetch, `delivered_rung` 1 → 0, `recheck.result=new-listing`; unchanged → `strategy.fetch` not called; transient discovery → `transient`, inset stands. New `tests/test_las_tile_index.py`: a synthetic 50 × 50 m pf6 LAS written with laspy (ground + class 6 + withheld) grids to the analytic plane within 1 cm, empty cells fill to radius 3 and NoData beyond, ftUS → m, a `.laz`/CRS-mismatch/short-file refuse `ProviderUnavailable`, index `{"error":…}` is transient, cap wording exact. `tests/test_inset_transport_refusal.py` (22) green. Freeze twin sees laspy; CI matrix (macOS/Windows/Linux) green.
5. ONE closing build (KASE). No sweep.

## §9 STOP

Any other pavement/runway law; a whole-tile overlay of LAS; filling 1 m holes from the 10 m rung (30ab NOT-handled stands); a private census/download wrapper (`tools/INDEX.md:1-25`); a lane-local `Elevation_data` copy; any sidecar write from a guarded build; a build with `cifp_data_path` empty; scipy/pdal/lazrs; a "newest-only" 1/3″ change; shifting lidar toward the base DEM; the five-airport sweep.

## §10 LANE BRIEF (Opus, cap 2; lane `las130`)

Base main. Files: `INSETS` (strategy class ≈ 350 lines; `_parse_resolution_ladder`, `_ladder_rung_definitions`, `_fetch_through_resolution_ladder`, `provider_required_capabilities`, the :7890 predicate, `ladder_recheck`), `Providers/Elevation/PITKIN1M.elv` + one `USGS3DEP.elv` line, `shared_repo_guard.py:69` scope, `build_airport.py` (frame check + `frame.json`), `requirements.txt`, both `.spec`s, `O4_Proj_Runtime.py`, `tools/INDEX.md` (scope row), twins §8.4. Run `Ortho4XP/venv/bin/python tools/blast.py` on each before editing. Order: laspy pin + twin → grid function + synthetic twin → strategy + index/tile fetch → cross-provider ladder + recheck + twins → scope + harness → warm KASE (`las_tiles,dem`) → ONE KASE build → census vs sw1002_KASE → report numbers first, `RULINGS` entry drafted, `Fixes #130` withheld until the owner's sim read. Deviations from this spec are reported, not decided.
