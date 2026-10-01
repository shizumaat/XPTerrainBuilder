# US HOLDER PROVIDERS — 59 HOLDER AIRPORTS SERVED THROUGH A GLOBAL, COVERAGE-BOXED, BEST-AVAILABLE LADDER; ONE VERTICAL-UNIT SITE; FOUR STRATEGY EXTENSIONS, THREE NEW

Fable 2026-09-30. Issues **#154** (holders), **#153** (the USGS OPR/LPC rung — lane `opr153` owns it; this spec only places it), **#151** (census). Owner order **RULINGS 2026-09-30bl** (`Ortho4XP/docs/RULINGS.md:9454`); law 30t (`:9542` transport classes), 30ab (`:9526` ladder), 30aw (`:9484` cross-provider + re-check), 30az/30bg (`:9478`/`:9464` two-layer, `airport_valid_fraction`, `las_tiles` scope), 30l (`:9442` consumer census). Inputs: the three verified scout reports on #154 (hold154a/b/c), `docs/elevation/usa_airport_elevation_gaps_20261003.{csv,md}` (2,959 airports, 164 gaps, 59 HOLDER, 51 USGS-LPC/OPR), `docs/specs/las-tile-lidar-provider-spec.md`. Engine paths are `Ortho4XP/src/O4_Airport_Elevation_Insets.py` (14,870 lines; cited `INSETS:<line>`). Read-only spec; ONE file; no engine edit, no build.

## §0 THE FACTS

| # | fact | number / site |
|---|---|---|
| 1 | HOLDER airports | 59: NC 17, OR 13, TX 12, AK 6, FL 4, CO 4 (KASE already served by PITKIN1M), WA 2, E78 1 |
| 2 | Vertical FEET at the source | NC Phase 3 (ftUS, Float32, nodata −999999), all DOGAMI/OLC Oregon, CWCB CO (3-ft IMG, ftUS), WA DNR (EPSG 2927 ftUS), FL native 2.5 ft service. The shared warp never rescales Z (`INSETS:2076-2244`, `-novshift` :2143); `vertical_unit` exists only in the LAS gridder (`LAS_UNIT_TO_M` :6679, `grid_las_tile` :6982). A feet raster bakes **3.28×** today — and the sanitizer (:2215-2240) silently voids every cell above 12,000 (= 3,658 m real) |
| 3 | The ladder enters ONLY for a definition with `resolution_ladder_rungs` (`fetch_inset` :1434) — USGS3DEP alone; the fetch loop ranks standalone providers by `priority` and stops at the first `ok` (:1237, break :9661). A standalone NCPHASE3 at priority 90 is NEVER reached at KRDU: USGS3DEP's own 3 m rung (1/9″ 100 % there) delivers first |
| 4 | Ladder mechanics in place | rung strategy resolved per rung :1647; out-of-coverage without a call :1641; `ProviderUnavailable` → `unavailable` + climb :1670 (rung 0 re-raises :1672); transient raises out :1628 docstring; `airport_valid_fraction` gate for a `core` block :1683-1691; surround assembly :1769-1820; `ladder` block :1829-1841; `ladder_recheck` :8831 (finer covering rungs only, discovery only) |
| 5 | Caps that today END in the wrong class | `arcgis_lerc_tiles` > 1,024 tiles → `return None` = durable NO-COVERAGE (:4594-4601); `arcgis_feature_tiles` silently truncates to 8 archives (`archives[:8]` :5660); `wcs_kvp` clamps one request to 8,000 px (:4862) and DOGAMI refuses > ~8 Mpx (an inset box needs ~76 Mpx) |
| 6 | Three shipped exportImage definitions send `noData=` EMPTY (CURITIBA50CM, CZECHIA2M, LITHUANIA1M `.elv`) — scout c measured that an empty noData returns 0.0 = false sea level. Out of scope here; filed as a follow-up (§8) |
| 7 | Target pixel floor `AIRPORT_INSET_MIN_TARGET_RESOLUTION_M` = 0.5 (:10493); a 0.457 m (WA) source warps at 0.5, NC 0.9525 at 0.9525 |
| 8 | KTPA at LERC level 17 ≈ 924 tiles — 90 % of the 1,024 cap; KMCF's longer box (3,489 m runway) likely exceeds it |

## §1 THE LADDER — "BEST AVAILABLE" MADE EXPLICIT

**Definition.** For one airport, the ladder is the ordered list of RUNGS `[r0, r1, …]`, each a provider definition (or the chain's own coarser discovery), ordered by `native_resolution_m` ascending, ties by `priority` descending then code; `r0` is always the chain's own finest rung (USGS 1 m). Every rung is **coverage-boxed**: a rung whose `coverage_bbox(es)` (:1207, :1355) miss the airport box is NOT a rung for that airport (no row, no call) — stronger than today's `out-of-coverage` row (:1641), which stays for the explicit `provider:` lines only. Discovery is authoritative inside the box.

**Outcome classes per rung — all fall through, none blocks a build:**

| class | cause | record | next |
|---|---|---|---|
| `delivered` | ≥ `INSET_MIN_VALID_FRAC` box-wide (:11215), or ≥ `INSET_MIN_AIRPORT_COVER_FRAC` 0.80 (:11224) over the aerodrome box when the rung answers a `core` block | the rung's provenance | stop; surround = next covering rung (30az) |
| `below-threshold` | valid share under the gate | fraction kept; finest sub-threshold raster retained as fallback (:1741) | next rung |
| `no-coverage` | a well-formed empty listing / all-nodata window | `listing_ids: []` | next rung |
| `unavailable` | `ProviderUnavailable` :357 — missing reader/decoder (`las`/`lerc`/the #153 LAZ backend), a cap exceeded (`max_tiles_per_airport`, `max_bytes_per_airport`, `max_archives_per_airport`, `max_request_px` × chunks), a vertical-unit contradiction (§2), a gate not opened (§3.6) | `unavailable_reason` | next rung; re-asked next build (13b door) |
| transient | 30t classes (`_TRANSIENT_NETWORK_ERROR_FRAGMENTS` :383, 5xx/429/non-JSON/truncated listing) | NOTHING durable; the fetch loop logs `loud_warning` and retries next run (:9640) | the ladder STOPS this run (an unfinished ladder is no durable answer — unchanged from 30ab); a lower-ranked standalone provider may still answer |

Rule kept from 30ab: all rungs below threshold → the finest sub-threshold raster is kept and the bake declines it loudly; `None` only when no rung listed anything. A build NEVER fails on a holder rung: the only raising class is transient, and the loop already survives it.

**Recorded per rung**: `rung`, `label`, `provider`, `native_resolution_m`, `resolution_m`, `outcome`, `valid_fraction`, `airport_valid_fraction` (when a core), `listing_ids`, `unavailable_reason`, `sources_used` (:1628-1696); plus NEW `vertical_unit_source` / `vertical_unit_applied` (§2) and `bytes_fetched`. `ladder.delivered_rung/label/provider` as today (:1829). `ladder_recheck` (:8831) runs on every lower-rung delivery (`delivered_rung > 0`) and asks ONLY the finer covering rungs' `discover()` — for an NC airport delivered by NCPHASE3 that is one TNM GET.

**ONE derivation site**: `_fetch_through_resolution_ladder` (:1554). Rung assembly is `_ladder_rung_definitions` (:1480); no strategy and no other caller orders rungs.

**How holder providers enter — RULED: GLOBAL ASSEMBLY, not hand lines.** 15+ holder `.elv` files as `resolution_ladder=1|…|provider:X` lines in `USGS3DEP.elv` is a second registry that drifts from the first (a file added without its line is silently a standalone provider that never runs — fact 3). Instead `_ladder_rung_definitions` becomes: `[r0] + explicit provider: lines (file order kept, PITKIN1M stays) + every enabled role=airport_inset definition with ladder_member=True (new key) whose coverage box intersects the airport box and which is not already named + the chain's own coarser rungs`, then a STABLE sort by `native_resolution_m`, `-priority`, code, with `r0` pinned first. `ladder_member` defaults **False** — the 70 non-US providers never join, so HECA/SPJC/CYXY/KASE/KCLT stay byte-identical (none of them has a holder box; KCLT delivers at r0; KASE's explicit PITKIN line precedes the global members). USGS3DEP's own rungs (#153's OPR/LPC rung at its native resolution, 1/9″ 3 m, 1/3″ 10 m) are the TAIL by resolution — the OPR rung (0.5–1 m native) sorts by its declared `native_resolution_m` like any member; where a holder and OPR tie at 1 m, `priority` decides (holders 90 < OPR's USGS3DEP 100 → OPR first, which is the owner's "USGS when USGS has it"). Holder `.elv` files carry `priority=90` so the standalone loop keeps USGS3DEP (100) as the one root; a pinned `airport_elevation_providers=NCPHASE3` still fetches it standalone as PITKIN1M does today. The sidecar `ladder.rungs_tried` lists only rungs that were rungs (covering), so an NC build shows ≤ 4 rows, not 20.

## §2 THE VERTICAL-UNIT KEY (cross-cutting; FIRST lane)

**Key**: `vertical_unit=m|ft|ftUS` on any RASTER provider; absent = `m`. Table `LAS_UNIT_TO_M` (:6679) is renamed/shared as `VERTICAL_UNIT_TO_M` (ftUS = 1200/3937 exactly).

**ONE site**: `warp_vsicurl_sources_to_geotiff` (:2076) gains `vertical_unit="m"`; in the existing post-warp array pass (:2215-2240, the sanitizer, which already reads and rewrites the band) valid cells are multiplied by the factor BEFORE the garbage test, so the floor/ceiling (−600/+12,000) is judged in metres and nodata (−32768) is untouched. Bilinear resampling is linear, so scale-after-warp equals scale-before. Every strategy passes `definition.get("vertical_unit")` through — 18 call sites (:2452 2927 3146 3483 3498 3915 4242 4468 4700 4782 4902 5295 5452 5720 6076 6441 6626 7438); the LAS site :7438 passes `"m"` (its DTMs are already metres, points converted at :6987).

**Refusal**: before the warp, each input's SRS is read (`osr.SpatialReference.IsCompound()`, vertical linear unit via `GetTargetLinearUnits("VERT_CS")`); when a compound CRS declares a unit and it contradicts the `.elv`, raise `ProviderUnavailable("<CODE>: .elv vertical_unit=ftUS but <source> declares metre")` → `unavailable:` record (:9628), ladder climbs; never a silent scale, never a durable no-coverage. Sources with no vertical CRS trust the `.elv`. Mixed declared units across one mosaic refuse exactly as `_refuse_mixed_vertical_datums` (:2246) does for datums.

**Provenance**: `vertical_unit_source` = `"elv"` | `"crs"` | `"elv=crs"`; `vertical_unit_applied` = `"m"`. A cached raster whose sidecar says `vertical_unit_source ∉ {m, null}` and lacks `vertical_unit_applied` was written by a pre-key engine → `_void_inset_record_reason` (:9179) names it and the raster is refetched; a lane's early feet raster cannot survive into the corpus.

**30l consumer census — every reader of a raster inset's Z** (all read metres; the one site above makes them all correct; NO consumer edit):

| consumer | reads | after §2 |
|---|---|---|
| sanitizer :2215 | floor/ceiling | judged in metres (order fixed above) |
| `inset_valid_fraction` :11237, `inset_is_effectively_empty` :11291 | nodata share | unit-agnostic |
| `_bake_one_inset` :11432 → ring offset → `_warn_if_provider_offsets_systematic` :10979 (3 m, ≥ 3 insets) and `INSET_DATUM_WARNING_THRESHOLD_M` 10 :10973 | inset − base | would only WARN at 3.28× — not a guard; now moot |
| `assemble_two_layer_inset` :1900 | core − surround seam median | the KASE class: a feet core beside a metre surround. Gate: assembler REFUSES (`ProviderUnavailable`) unless both provenances carry `vertical_unit_applied == "m"` — the one new assertion |
| `derive_acceptance_probes` :13048, `ideal_bake_errors_per_probe` :13251 (`PROBE_TERRAIN_SCALE_M` 30) | heights | metres |
| water detection :9834-9852 (flatness 0.05 m, range 0.15 m, rim 0.3 m), `ensure_inset_water_supplement` :10252 | metre thresholds | metres |
| `densify_tile_dem_for_insets` :13960, `resolve_working_grid_factor` :13402 | `native_resolution_m` | unchanged |
| `airport_inset_frame_problem` :12581, `cached_inset_declined_reason` :9146, `_void_inset_record_reason` :9179 | sidecar/raster | + the pre-key sidecar rule |
| `auto_patch_v2/airport/dem.py:164-204` (DemSample), `:276-278` (`provider`, `source_ids`, `vertical_datum`) | Z, sidecar | metres; sidecar keys additive |
| `dem_production.py:443-525` | `native_resolution_m` | unchanged |
| harness `build_airport.py:795/811/3947` | frame problem, recheck | + `vertical_unit_applied` in `frame.json` per inset |

**Twin** (`tests/test_airport_elevation_insets.py` + new `tests/test_vertical_unit.py`): a synthetic 40 × 40 GeoTIFF of a plane in ftUS with nodata holes, warped with `vertical_unit=ftUS` → every valid cell within 1 mm of plane/3.2808; holes stay −32768; a compound-CRS source declaring metre + `.elv ftUS` → `ProviderUnavailable` with the exact wording; the two-layer assembler refuses a core/surround unit mismatch; a pre-key sidecar is reported void.

## §3 STRATEGIES

Common contract: caps checked BEFORE any byte moves, raising `ProviderUnavailable` in the LAS wording (:7247-7256 "needs N tiles / X MB, cap … — SKIPPED, recorded unavailable, not no-coverage"); a `#136` progress line at most every 30 s (`LAS_PROGRESS_INTERVAL_S` :6700, `_las_progress_line` :6772 generalised); transient = 30t fragments + 5xx/429/non-JSON/truncated listing (:527, :571); durable no-coverage ONLY for a well-formed empty answer; scratch beside `destination_path`, removed in `finally`. Refresh scopes: rasters and the per-airport inset stay under `dem` (`shared_repo_guard.py:94`); point clouds under `las_tiles` (`:91`). **Archives (zips) RULED: no new scope** — a quarter-quad zip or a tile zip is read through `/vsizip/` and deleted after the warp (as `arcgis_feature_tiles` does :5706); nothing persists but the inset, which is `dem`. Only a `keep_raw`-style cache would need a scope, and none is specified here.

### 3.1 `direct_cog` — EXTEND (`:4741`)
Works today for a dataset VRT in `cog_urls` (`.vrt` already in the allowed extensions :2057). Add: `vertical_unit` pass-through; `vertical_datum` as today. Note for the lane: NC Phase 3's VRT indexes 44,813 tiles — measure the VRT fetch once (expected tens of MB, cached by `/vsicurl`); if > 60 s cold, split `cog_urls` per NOAA `EPSG-named` VRT (there are two) and record it. No cap needed (windowed reads).

### 3.2 `arcgis_feature_tiles` — EXTEND (`:5488`)
Today: folder enumeration of "Coverage" services (:5509), one `url_field` per feature, 8-archive slice. Add keys: `index_layer_url` (a single query layer, bypassing the folder walk), `where` (e.g. `bestavail=1`), `archive_resolver=tnris_resources` (per-collection `{prefix}` from the TxGIO resources API, memoised in `Elevation_data/texas1m_resources.json`), `archive_url_template` with `{collid}`, `{prefix}`, `{tileid7}` (`tileid[0:7]`), `member_filter_template` = `-1m_{tileid}` evaluated PER FEATURE (today's single substring :5635 stays the default), `max_archives_per_airport` (default 8; TEXAS1M 16) — over it → `ProviderUnavailable`, replacing the silent slice (:5660). Transport: the S3 origin (`s3.amazonaws.com/data.tnris.org/...`), never the CloudFront host (403 on non-browser agents — scout b); `.img` members warp like `.tif` (the `_tif_members` walk :5641 gains `.img`). Nodata sniff (:5675) unchanged.

### 3.3 `las_tile_index` — EXTEND (`:7119`)
Add `index_format=ogr` (default `arcgis`): the index is a GeoPackage opened over `/vsicurl/` with OGR, filtered by the surgical footprint (`las_core_geometry` :6729) exactly as the ArcGIS branch; keys `index_url`, `index_url_field` (`url`), `index_name_field` (`filename`). LAZ: lifted by the #153 backend capability (lane opr153 registers `CAPABILITY_LAZ`; this strategy consults it; without it `ProviderUnavailable("laz backend missing")`, never the current flat refusal :6694). `archive_member=las` (CWCB 7V2's LAS-in-zip): download the zip to the `las_tiles` cache, extract the one member, delete the zip — the raw LAS stays under `las_tiles` as today. Caps and progress as shipped.

### 3.4 NEW `arcgis_export_image` (sibling of `wcs_kvp` :4818)
Contract: `service_url` (ImageServer root), `source_epsg` METRIC or feet-projected (the request grid is laid in it), `native_resolution_m`, `max_request_px` (default 6,000,000 — DOGAMI's measured limit is ~8 Mpx), optional `rendering_rule` (JSON, e.g. DOGAMI's `×0.3048` — when used, `vertical_unit=m` and `vertical_unit_source="rendering_rule"`), `nodata` MANDATORY (a definition without it is refused at parse: fact 6), `format=tiff|lerc` (`lerc` needs `CAPABILITY_LERC` → `unavailable` without it), `max_bytes_per_airport` (default 400 MB; DOGAMI ≈ 110 MB LERC / 300 MB TIFF per airport). Fetch: pad 60 m, tile the padded box into chunks of ≤ `max_request_px` at the request pixel (the `wcs_kvp` rule :4848: never finer than the inset target), one GET per chunk with retry per 30t, chunk count × bytes checked against the cap BEFORE the first GET (a HEAD is not available; estimate = px × 4 B), build a VRT over the chunk files, shared warp with `vertical_unit`. Progress: one line per chunk. **`wcs_kvp` RULED: NOT folded.** HESSE1M is a true WCS 2.0.1 KVP; the three exportImage users (fact 6) migrate to the new strategy in a follow-up lane that also sets their `nodata` — one change, not this spec's.

### 3.5 NEW `cwcb_lidar_api`
Contract: `api_url` (`https://coloradohazardmapping.com/api`), `dataset_id` (per `.elv`), `format_key` (the 3-ft IMG DEM), `source_epsg` (CO North ftUS 6428-family — the lane pins the exact code from the IMG header), `vertical_unit=ftUS`, `max_tiles_per_airport` (24; KHDN 20, KCAG 14), `max_bytes_per_airport` (120 MB; 2.2 MB zipped per tile). Discovery: `POST tiles` with the surgical footprint's WKT → tile keys; `POST tileSummaries [dataset]` → WKTs + sizes, memoised per dataset in `Elevation_data/cwcb1m_<dataset>_summaries.json`; footprint ∩ polygon selects (the §2 LAS rule). Fetch: `GET files/{tileKey}/{formatKey}` → `{tileId}.zip` into scratch; the `.img` member is read through `/vsizip/`; VRT of members → shared warp. Transient/durable per the module law; an API `{"error":…}` in a 200 is transient. 7V2 is NOT this strategy (LAS-only, §5).

### 3.6 NEW `aoi_zip_download` (WA DNR + Alaska portals, same software)
Contract: `portal_url`, `query_path=/query`, `download_path=/download`, `dataset_filter` (name/id of the one dataset), `source_epsg`, `vertical_unit`, `max_bytes_per_airport` (300 MB), `max_tiles_per_airport` (64), `gate_cookie_from` (optional; a GET on this path first, its cookies replayed) and `user_agent` (a browser string) — BOTH keys are honoured ONLY when the owner answers **Q-154 (a)**; until then a definition carrying them is parsed `enabled=False` with one line naming Q-154, and WADNR ships disabled. AK's portal has no gate: no keys. Discovery: `POST query` with the surgical footprint GeoJSON → datasets/files/bytes (the bytes answer IS the cap check); fetch: `GET download?geojson=&ids=` streamed to scratch with progress lines, members warped through `/vsizip/`, zip deleted. Zip64 > 4 GB is refused as `unavailable` (PAWG, §5).

## §4 THE PROVIDER FILES (`Ortho4XP/Providers/Elevation/`), keys ready to commit

Common keys on every file: `role=airport_inset`, `ladder_member=True`, `priority=90`, `enabled=True`, `vertical_datum=NAVD88`, `license`, `license_note` (30aw pattern: the published terms or "no restriction published; not charged for, not redistributed as data (owner RULINGS 2026-09-30aw)"), `attribution`, `coverage_bbox` (tight to the dataset's index extent, measured by the lane), `publication_date`, `native_resolution_m`.

| file | airports | strategy / keys | unit |
|---|---|---|---|
| `NCPHASE3.elv` | 17 NC (KGSO KRDU KFAY KPOB KTTA KSOP KBUY KTDF KHBI KSIF KRCZ KHRJ KSCR KHFF KFBG W77 43A) | `direct_cog`; `cog_urls=` the two NOAA EPSG-named VRTs under `noaa-nos-coastal-lidar-pds/dem/NC_phase3_2024_15636/`; `source_nodata=-999999`; `native_resolution_m=0.9525`; `coverage_bbox=-80.19,34.62,-78.25,36.56`; `license=CC0 1.0` | `vertical_unit=ftUS` |
| `NOAATXJLC1M.elv` | KBMT | `direct_cog` on the 2017 TNRIS Jefferson/Liberty/Chambers VRT (ID 9040); works today | m |
| `NOAAKETCHIKAN.elv` | PAKT | `direct_cog`, 2014 FEMA Ketchikan VRT (ID 8521); 84 % holder share → may land as `below-threshold` on the airport box and still deliver box-wide ≥ 0.05; the lane quotes both fractions | m |
| `NOAAAKCOASTAL.elv` | PADL | `direct_cog`, 2023 AK Coastal Communities VRT (ID 10424) | m |
| `NOAACOLUMBIARIVER.elv` | KAST (if DOGAMI does not cover it, see below) | `direct_cog`, 2010 USACE Columbia River VRT (ID 1122) | m (lane verifies the VRT's compound CRS) |
| `NOAAVALDEZLAZ.elv` | PAVD | `las_tile_index`, `index_format=ogr`, the dataset's `tileindex_*.gpkg`, COPC LAZ (UTM m, NAVD88) — needs §3.3 + #153's LAZ backend; until then `unavailable` | m |
| `TEXAS1M.elv` | 11 TX (KGRK KACT KTPL KGLE KBWD KILE KTRL KGTU KHLR T31 KLUD) | `arcgis_feature_tiles` + §3.2: `index_layer_url=…/Status_Maps/Lidar_Index_Public/FeatureServer/0`, `where=bestavail=1`, `archive_resolver=tnris_resources`, `archive_url_template=https://s3.amazonaws.com/data.tnris.org/{collid}/resources/{prefix}_{tileid7}_dem.zip`, `member_filter_template=-1m_{tileid}`, `max_archives_per_airport=16`, `license=CC0` | m |
| `CWCB1M.elv` | KHDN, KCAG | `cwcb_lidar_api`, `dataset_id=` 2016 Routt County, `format_key=` the IMG DEM, `max_tiles_per_airport=24`, `coverage_bbox=` Routt County; `license_note` as PITKIN1M's (same Merrick/CWCB flight family; no restriction published) | ftUS |
| `HILLSBOROUGH1M.elv` | KTPA KMCF KVDF KPCM | `arcgis_lerc_tiles`, `ESRITest/n767demmosaic_WGS84_m/ImageServer`, `tile_level=17` (1.06 m), `native_resolution_m=1.06`; `license_note` records the "ESRITest" folder and the "bilinear-resampled, not for modelling" caveat; the :4594 cap path becomes `ProviderUnavailable` (fact 8) | m |
| `HILLSBOROUGHNATIVE.elv` | same 4, ranked finer (0.762 m) | `arcgis_export_image` on the native 2.5 ft FL West service, `nodata=-9999`, `source_epsg=` FL West ftUS; ships in the export_image lane; HILLSBOROUGH1M becomes its next rung by resolution | ftUS |
| `OREGONDOGAMI.elv` | KEUG KSLE KOTH KMMV KCVO KAST S21 KONP KUAO 3S8 (+ KRBG 64S KBDN if the statewide mosaic covers them — the lane probes one exportImage per airport and records the answer) | `arcgis_export_image`, `service_url=…/lidar/DIGITAL_TERRAIN_MODEL_MOSAIC/ImageServer`, `source_epsg=6557`, `native_resolution_m=0.914`, `rendering_rule=` the verified ×0.3048 rule (→ `vertical_unit=m`), `nodata=-9999`, `max_request_px=6000000`, `format=lerc`, `coverage_bbox=` Oregon | m via rule |
| the six Oregon OLC NOAA copies | — | **RULED: NOT WRITTEN.** DOGAMI's statewide mosaic is the same data with the newest survey on top (KEUG = 2023 South), one provider instead of six feet-unit files. They return only for an airport the DOGAMI probe does not cover (then as `direct_cog`, `vertical_unit=ft`, one file per dataset, the lane names it) | — |
| `AKHOMER.elv` | PAHO | `aoi_zip_download` on elevation.alaska.gov, dataset 2019 DGGS Homer (NCMP 1 m); no gate keys | m |
| `WADNR.elv` | KNUW KNRA | `aoi_zip_download`, `source_epsg=2927`, `native_resolution_m=0.457`, `gate_cookie_from=/`, `user_agent=` browser — **enabled=False until Q-154 (a)** | ftUS |
| `AKHAINES.elv` | PAHN | **RULED**: the one 322 MB file is served from the same portal; if it is a GeoTIFF with range support, `direct_cog` with that URL as `cog_urls` (a windowed read never fetches 322 MB; `coordinate_named_url_list` is the NCEI filename grammar :4054 and does not apply); if it is zipped, `tile_grid_http` with a `/vsizip//vsicurl/` template (the BREMEN1M idiom). The lane's first act is a HEAD + `gdalinfo` and the file's answer picks the line | lane verifies |

## §5 GAPS — declared, not provided

| airport | why | action |
|---|---|---|
| E78 Sells | no 1 m anywhere: the Pima County 2021 lidar has a hole over the Tohono O'odham Nation (scout c) | census verdict → `NOBODY`; the USIEI row is a false holder; `elevation_gap_census.py` gains an `--override` CSV (icao, verdict, reason) read at classify (`tools/elevation_gap_census.py:261`) |
| PAWG Wrangell | 9.2 GB Zip64 from DGGS | `unavailable` by cap; stays HOLDER with note; the OPR/LPC rung (55 % AK_SouthEastLandslides QL1) may serve part |
| 7V2 North Fork Valley | 2015 Western CO point cloud, LAS 1.2 in zips | §3.3 `archive_member=las` + an `.elv` in the las_tile_index lane; until then unavailable |
| PAVD | COPC LAZ only | after #153's LAZ backend (§4) |

## §6 ACCEPTANCE

1. **Census re-run**: `tools/elevation_gap_census.py --providers` (new mode; reads `initialize_elevation_providers_dict()` :726 and `_ladder_rung_definitions` :1480 for the USGS3DEP root; per HOLDER row prints the rung LIST the ladder would assemble and the rung it WOULD deliver from the recorded discovery only — no download) → every HOLDER airport except E78/PAWG/7V2/PAVD names a holder rung; the 51 USGS-LPC/OPR rows name #153's rung (that lane's own acceptance). Output `docs/elevation/usa_airport_elevation_gaps_<date>_providers.csv`.
2. **Witness builds** — one per strategy class, lane-local insets, `build_airport.py ICAO` after a lane-local `--refresh-data dem` (never the shared corpus; the session seeds it after merge): KRDU (NCPHASE3), KBMT (NOAATXJLC1M), KGRK (TEXAS1M), KHDN (CWCB1M), KTPA (HILLSBOROUGH1M; then HILLSBOROUGHNATIVE), KEUG (OREGONDOGAMI), PAHO (AKHOMER), PAKT (NOAAKETCHIKAN). Each quotes: `ladder.delivered_provider`, `delivered_rung`, `valid_fraction`, `airport_valid_fraction ≥ 0.80`, `vertical_unit_applied=m`, bytes fetched vs cap, wall time; replay census vs the shared-corpus control (the same airport built on the 10 m/base rung) — runway PINS unchanged (`--tol 0.02`), movers explained by the DEM delta per 30az (3) (≥ 95 %, quoted not ruled).
3. **VERTICAL sanity at every witness** (the feet trap's twin): the inset's median over a 60 m disc at the ARP vs the apt.dat field elevation — |Δ| ≤ 3 m. A feet raster reads +630 m at KRDU (ARP 132 m): impossible to miss. RULED: in the harness (`build_airport.py` beside :795) as `inset_arp_sanity` — a `frame.json` key + WARN; a refusal only under `--strict-inset-datum` (a geoid difference at a coastal AK field is lawful and must not block the owner's build); the engine never refuses on it.
4. **Controls byte-identical**: HECA, KCLT, SPJC, CYXY, KASE — sidecars and rasters unchanged (no holder box contains them; KCLT delivers at r0; KASE's ladder rows unchanged: PITKIN explicit line first).
5. Twins: §2's; per strategy a synthetic server (the `tests/test_inset_transport_refusal.py` pattern, 22 twins today) proving cap wording, transient vs durable, `unavailable` on a missing capability, chunk tiling (export_image: a 76 Mpx box → 13 chunks at 6 Mpx), the Q-154 gate parse; `test_inset_resolution_ladder.py` (10 today) + global-assembly rows: a `ladder_member=True` provider outside its box is NOT a rung; inside, it sorts between USGS 1 m and 3 m; controls' rung lists unchanged.

## §7 STOP

A feet inset baked as metres (any raster with `vertical_unit ≠ m` reaching the bake without `vertical_unit_applied`); a holder rung that raises anything but a 30t transient out of the ladder; a cap exceeded that returns `None` (no-coverage) instead of `ProviderUnavailable`; a truncated listing or slice delivered as the whole; the WA gate bypassed (`gate_cookie_from` honoured) without Q-154 (a); a CloudFront/browser-agent trick on any host that refuses bots; hand `provider:` lines for holders in `USGS3DEP.elv`; a lane-local `Elevation_data` copy or a shared-corpus write (the ritual, `lane_worktree.sh`); the three exportImage `noData=` fixes (follow-up issue); any pavement/runway law; the five-airport sweep; a private census wrapper (`tools/INDEX.md`).

## §8 LANE PLAN (Opus, cap 2 attempts each; one witness build per lane; report numbers first)

| # | lane | scope | witnesses | pre-registered targets |
|---|---|---|---|---|
| 1 | `vunit154` | §2 warp key + refusal + provenance + assembler assertion + pre-key sidecar void + global ladder assembly (§1, `ladder_member`) + lerc/feature cap → `ProviderUnavailable` (fact 5) + census `--providers` + `--override` + `inset_arp_sanity` | KASE control (byte-identical), synthetic feet twin | 5 controls identical; twins green; `--providers` prints 59 rows |
| 2 | `ncnoaa154` | the `direct_cog` files: NCPHASE3, NOAATXJLC1M, NOAAKETCHIKAN, NOAAAKCOASTAL, (NOAACOLUMBIARIVER if needed) — 21 airports | KRDU, KBMT | KRDU `delivered_provider=NCPHASE3`, ARP |Δ| ≤ 3 m, `airport_valid_fraction ≥ 0.95`; VRT cold open ≤ 60 s |
| 3 | `tx154` | §3.2 + TEXAS1M — 11 airports | KGRK | 9 tiles ≤ 16 cap; delivered TEXAS1M |
| 4 | `export154` | §3.4 + OREGONDOGAMI + HILLSBOROUGHNATIVE (+ the DOGAMI coverage probe for KRBG/64S/KBDN) — 14–17 airports | KEUG, KTPA | KEUG ≤ 13 chunks, ≤ 120 MB LERC, median 110.6 m at the runway reproduced ± 0.5 m |
| 5 | `fl154` | HILLSBOROUGH1M on the shipped lerc strategy (can run parallel to 4) | KTPA | ≤ 1,024 tiles or `unavailable`; delivered |
| 6 | `cwcb154` | §3.5 + CWCB1M | KHDN | 20 tiles, ARP 2007.3 m ± 3 |
| 7 | `aoi154` | §3.6 + AKHOMER + AKHAINES (+ WADNR disabled; enabled only on Q-154 (a)) | PAHO | delivered; PAHN line picked by the HEAD |
| 8 | `lasidx154` | §3.3 (ogr index, LAZ via #153, zip-LAS) + NOAAVALDEZLAZ + a 7V2 file | PAVD (after #153 merges) | delivered or `unavailable:laz backend` named |

Order: 1 merges FIRST (nothing with `vertical_unit ≠ m` may land before it); 2 and 3 after 1; 4/5/6/7 parallel after 1; 8 after #153. Each lane: `blast.py` on `INSETS`, `tools/INDEX.md` entries for the census mode, a `RULINGS` entry drafted, `Fixes #154` withheld until the census re-run (step 6.1) is quoted on the merged engine. Deviations reported, not decided. Owner questions pending: **Q-154** (WA DNR bot gate: (a) replay the cookie with a browser agent, (b) leave WA to the OPR/LPC rung).
