# #2064 round 2 — terrain models (LOWS, LXGB, TFFJ) (Fable one-miss review of lterrain2064 b009db9be, 2026-11-13)

Verdict: keep round 1 (MSL rows recognised, kept at authored height, cut; riders/lift sound). It missed for three reasons outside `terrain_model.py`'s seat: (1) LOWS's production DEM is wrong; (2) the peak gate is too strict for MSL rows; (3) 13k's "no triangle pokes" isn't held by the mesh on small pieces (the #2053 r3 defect; terrain models were left out of the hold). The bar "no model floats > 0.5 m at a visible edge" can't be met by seat or cut for an MSL model at authored height (owner Q1).

## 1. LOWS mechanism (reproduced offline to the lane's numbers)
Building-footprint mask on the Copernicus GLO-30 approach-ring cell filled by nearest-value distance transform. The rock (`OBJECT_MSL 39 13.047865167 47.794984073 430`, line 544 of `/Users/noah/XPTerrainBuilderData/Airport_mod_cache/c_AUT - 100_airport - LOWS Salzburg (Digital Designs)/+47+013.dsf.anchor_bak.df10cb14.text`) lies outside the LOWS 1 m inset (lon 12.987–13.020), inside ring cell `/Users/noah/XPTerrainBuilderData/Elevation_data/+40+010/N47E013_approach_rings/cell_00_07_copernicusglo30_30-m_30.92m.tif` (sidecar: `surface_model_building_masking` 26,753 footprints, 35 m buffer, masked_fraction 0.3583, `fill_method: distance_transform`). Ring 476.59 at the castle origin / 486.97 at the rock origin vs raw .hgt 503.74 / 520.85; E–W at lat 47.79498 ring plateau 488.4/489.0/489.0/488.1 at lon 13.048–13.051 where raw falls 519 → 435 (ring − raw −35..+53). Match on `land_lows.obj`: raw r 0.92 / peak 0.11; masked ring r 0.18 / peak 0.41. Code: `mask_building_footprints_in_surface_model` (`O4_Airport_Elevation_Insets.py:3700`), fill `_fill_masked_by_distance_transform` (:3097), premise "ground under an airport terminal is nearly planar" (:3107). The fill RAISES ground 32–53 m on the east flank — impossible for a building removal.

## 2. Changes (base: main after batch 17 with `claude/lisland3b`; rebase b009db9be — both edit `terrain_model.py`, `terrain_cut*.py`)
C1 DEM fill clamp: in `mask_building_footprints_in_surface_model` only, `filled = minimum(filled, values)` on `pixels_to_fill` after smoothing, both fill methods; record `"fill_clamp": 1`; no global invalidation (13o); LOWS cell re-derived by explicit `--refresh-data dem`. Twin: synthetic hill with masked summit + flank → no filled pixel above source; flat-apron case byte-identical. (Proxy: r 0.83, peak 0.39, east flank restored, summit ~30 m low, hidden under the model. Relief-aware fill for masked hilltops = separate issue.)
C2 Rule A, `OBJECT_MSL` candidates keep the author's row (`placement_models`/`match`): A1 corr ≥ `MIN_CORR` → model at authored height, cut; `MAX_PEAK_ERR` NOT applied to MSL rows (reported) — expected Cliffs3 (0.28), TheRock (0.38), Gustavia (0.54), LOWS after C1 (0.39). A2 corr < `MIN_CORR` or no DEM → kept as authored via the `terrain_feature` path (never converted, never cut, no `cut` record), log "unmatched, kept as authored" — expected TFFJ Hilltop1 and KCRW `KCRW_Landinglight_Structure_1`. A3 small-tier floor for MSL: census with "≥ 100 covered cells" instead of 150 m; adopt only if every new admission is a terrain piece (expected TFFJ Homesite, CliffHotel); else keep 150 m and list them. 13r: report every corpus row whose treatment changes under A1–A3.
C3 mesh hold for terrain-model cuts: `auto_patch/terrain_cut_stage.py` (lisland3b) `_held` takes only records whose `cut` names `erode_m`; extend the vertex hold (`hold_heights`) to every cut record; for records without `erode_m`: bound on the model's `CELL_M` (5 m) grid, top eroded by one cell less `UNDER_M`, band rule unchanged; NO curvature-weight raise and NO patch substitution; lisland3b's shore rule applies; 30 m raster erosion stays; SBRJ Sugarloaf's 12,626 cut postings unchanged (only vertices move).
C4 Rule B, measure first: don't re-land 5fd0016e1. By replay report three seats (rim cell, all-edge, lowest-edge = open edge `outer_edge` over points in the lowest part of the edge's height range; closed sides rim cell) for SBRJ Sugarloaf, KHAF shell, KOAK embankment. Adopt lowest-edge only if SBRJ within 0.5 m of 0.00, KHAF within 2 m of −11.65, KOAK moves < 0.5 m; else leave `rim_seat` and hand the table over. Plain/AGL rows only; MSL rows keep authored height.
C5 riders of a hidden model: `riders()` skips a model the pack answer hides (riders go to the object stage, stand on our ground, 13y (2)); only if < ~30 lines, else one line in `docs/DEFERRED_VERIFICATION.md`.
C6 (owner yes, RULINGS 13z (1): under COARSE elevation only; under trusted national/lidar elevation seat the model to the terrain instead): rim fill — inside the plan within `BAND_M` of the edge, raise raster postings below the edge bottom up to it less `UNDER_M` (never over water, nothing outside the plan).

## 3. Consumer census additions
| Consumer | Reads | Ruling |
|---|---|---|
| ring/inset composite, bake, probes | masked DSM cell | C1 clamp at the one write site |
| `terrain_model.match` | production DEM | MSL: corr only (C2); plain rows unchanged |
| `terrain_feature` (`obj8.py:1463`, `pack_partition.py:676`, `placement_write.py:293`) | feature ids | gains A2 rows |
| object stage (11d conversion) | non-model rows | loses A1/A2 rows; gains hidden-model riders (C5) |
| `basin_witness.read_objects` | row height | round 1 stands |
| free mesh vertices / plan-edge ring vertices | bilinear `.alt` | held (C3) |
| water, INTERP_ALT, pinned vertices | datum / col 5 | fixed |
| Triangle4XP refinement | curvature × weight | no raise for terrain models |
| patch groundside under a plan | `dem_z` | unchanged |
| seat, match | corpus DEM | uncut |
| step reuse / provenance | cut ids | unchanged unless C6 |
| hidden models | — | not cut/held; riders released (C5) |

## 4. Bars (`tools/drawn_cover.py ICAO --tag T --object SUBSTR` + terrain-model log line)
Recognition (replay/census): LOWS `land_lows` model at 430 with 3 castle riders at 510 (lift +80), none converted; LXGB Rock + 10-row set at MSL 0, cut; TFFJ all 16: 0 converted to `OBJECT`. Drawn (closing build): off-patch land samples > 0.05 m over the top with a free corner: 0; land samples > 0.5 m over ≤ 1 % of land plan, each attributed to a fixed corner. Floating edge reported per model (gate only if C6 built). No regression: SBRJ 12,626 postings; KHAF/KOAK seats unchanged unless C4 condition met.

## 5. Closing build
ONE: LOWS tile +47+013 via `tools/harness/build_airport.py` after explicit `--refresh-data dem` for that tile. TFFJ/LXGB by census/replay (their drawn bars go to the master's merged-batch build — a stated gap).

## 6. Tests
`test_terrain_model.py`: MSL corr 0.8 / peak 0.5 → model; same shape plain → not; corr 0.2 MSL → kept feature, no `cut`; A3 floor. `test_terrain_cut_hold.py`: no-`erode_m` record held at `CELL_M`; no weight box; ramp unchanged; shore rule. Inset masking twin (C1). C4 twin only if adopted. Registry twins, `test_v1_retired`, `ratchets.py dupes --near`, `unused`.

## 7. Risks
C1 changes every newly fetched masked DSM cell (filled pixels upper-bounded by the surface; flat aprons unaffected). A2 keeps KCRW's landing-light structure at authored MSL (recent owner reads; census list). C3 cost on LXGB's 4 km plan unmeasured (build-time statement). Rebase first. KSEZ 10 buttes: on-ground → authored MSL + cut (Q2).

## 8. Owner questions
Q1 MSL model at authored height whose edge stands over our ground (TFFJ RocksNW 12.7 m, LOWS up to 20.6 m): (a) raise our ground under the edge in the 10 m rim band (amends 13k "never filled") — recommended; (b) lower the model (13i seat; KSEZ up to 90 m); (c) accept and report. Q2 KSEZ: list the ten buttes with `floats_m` before landing. Q3 KCRW `KCRW_Landinglight_Structure_1` kept at authored MSL (A2) — default keep + sim read. Q4 SBRJ Sugarloaf −26.9 (current) or 0.00 if C4 supports lowest-edge.
