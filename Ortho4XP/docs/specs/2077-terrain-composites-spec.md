# Spec #2077 — terrain composites: rigid frame, fill, unbounded terrain seat, hide offer (Fable, 2026-11-15)

Base `origin/claude/llows` eb306d685. Owner 2026-11-15T05:46Z (verbatim): "Yes to all three shell related rules. Where we have lidar terrain that is high quality enough to be similar or better than a shell, we should offer to simply hide the shell and seat any remaining objects, the results will likely look more realistic". Rules (owner yes): (A) a shared-origin object set that contains a terrain shell is ONE rigid terrain-shaped composite, never split; (B) where our ground stands below such a composite, fill the ground up to it instead of sinking the composite to its lowest rim; (C) a building with nothing carrying it but our terrain stands on our terrain however far its base is from it; (D) hide offer where quality elevation models the shell. Default of D's tick: UNTICKED (13i) unless the master relays the owner's answer otherwise.

## 0. Measurements that shaped the spec
- The town's ground is FABDEM 30 m (built `.alt` `Rebuild_cache/zOrtho4XP_+47+013_2/Data+47+013.alt`, 11017², 6.92 × 10.31 m postings; matches the approach-ring FABDEM cells within 0.1–1 m outside the hill plan), not the 3″ `.hgt`.
- The hill sits in a crater today: ground 15 m outside the rim stands a median 22.7 m above the rim bottom (p5–p95 8.7–33.5 m).
- Hill seat options (FABDEM, 412 rim cells):
| Seat | z0 | Castle zero | Rim floating > 0.5 m | Rim under outside ground |
|---|---|---|---|---|
| Rim minimum (13i, today) | 406.80 (baked 405.844) | 486.8 | 0 % | 99.8 %, median 24.4 m |
| L1 fit (`terrain_shaped.fit`) — CHOSEN | 426.29 | 506.3 | 12.6 %, max 19.5 m | 83 %, median 5.8 m |
| Rim median | 431.22 | 511.2 | 44 %, max 24.4 m | 45 %, median 4.1 m |
| Author's datum | 430.00 | 510.0 | 34 %, max 23.2 m | 58 %, median 3.8 m |
- The floating hill-rim cells are all on the NW cut edge (47.7956–47.7964, 13.0447–13.0493, bottoms +23 to +60 m) and are closed by the cliff object, not by fill (fill there would raise 278 postings by up to 33.9 m against the town) → "no edge floats" needs an exemption where another composite owns the ground (§2.4).
- The cliff cannot be seated by any DEM fit (`terrain_shaped.fit` of city_centr_08 = 413.3; crest cells 405, foot 428). Ground under the set's origin is 429.62 (FABDEM); ground-level wall bottoms of files 01/02 agree (medians 429.7 / 427.6) → seat the cliff set at our ground under the origin.
- Per-wall fill supports are unusable (1,998 contacts, 562 at y ≥ 5, 4,610 conflicting postings). The zero-plane model (§2.5) has none: zero footprint 27.9 ha, 46.5 ha of postings changed, 2,890 raised (max 16.5, mean 4.3), 3,621 lowered (max 43.1, mean 6.9); afterwards 0 cells have ground over the zero plane; 68 of 1,426 wall cells (4.8 %) still float, up to 3.08 m (feet authored 0.5–3 m above the plane).
- Rule C as worded re-opens 14a: `terrain_base_over_ground = true` moves 42 listed pieces at 9 airports (`Ortho4XP/docs/findings/1884-in-air-pieces.md`): street lights, poles, signs, a jetway connector, fences, pier interiors — no whole building. C needs a building witness (§3).
- The hide offer cannot appear at LOWS today: `LOWS_austria1m` covers 12.9874–13.0200 E; the town is at 13.037–13.050 → stage 2 (§4.3).

## 1. Recognition (rule A)
New file `Ortho4XP/src/auto_patch_v2/airport/relief_skin.py`. Candidate test, no DEM, one verdict per file version (cache as `terrain_model._file_shape`). Bin the static solid with `terrain_shaped.grid_of_triangles` (5 m), take the largest 8-connected component of covered cells. All six must hold:
| Gate | Constant | Value | city_centr_08 | Nearest non-terrain measured |
|---|---|---|---|---|
| Component holds the object | `MIN_SHARE` | 0.9 of covered cells | 0.97 | KBWI_City/7 0.33; KCRW landing-light structure 0.70 |
| Component extent | `terrain_model.MIN_PLAN_M` | 500 m | 835 | KCRW landing-light structure 485 |
| Top relief p5–p95 | `MIN_RELIEF_M` | 30 m | 42.0 | city_centr_09 14.5 |
| Single surface (top − bot < 1 m) | `MIN_SKIN` | 0.6 of cells | 0.74 | KOAK Terminal_1 0.00 |
| No floor (terrain_feature floor share) | `MAX_FLOOR_SHARE` | 0.25 | 0.05 | — |
| Steep (top gradient > 0.25) | `MIN_STEEP` | 0.3 of cells | 0.62 | Chesapeake Bay Bridge_33/34/39 0.00 |
Calibration over 12 packs (LOWS, SBRJ, SBGL, LXGB, BIKF, LICJ, KCRW, KEGE, KHAF ×2, KOAK, KBWI): the only new pass is city_centr_08; other passes are already terrain models/features (land_lows, Sugarloaf, lxgb_rock, lxgb_rock_detail, KHAF mesh01).
Single derivation site: `airport/obj8.py:1431–1447`, after `found` and `shells`: `skins = relief_skin.placement_skins(placements, …, skip=found ∪ shells ∪ terrain features ∪ shaped)`, plain OBJECT / OBJECT_AGL rows only (an OBJECT_MSL skin that fails 13i keeps today's reading; the census counts it). `found.update(skins)`, then the existing `terrain_model.set_members` makes the origin set; members flow through the existing `terrain_feature=True, terrain_model=…` branch (`obj8.py:1467–1476`): never read, split, re-anchored or padded. Precedence: 13i model > ground shell > terrain feature (10-20aq) > terrain-shaped deck > relief skin. No second origin-set function, no new seat kind (records stay `terrain_model.SEAT`). `TerrainModel` gains default-off fields `fill: bool = False`, `plane: tuple = ()` (zero-footprint rings, frame metres), `skin: bool = False`. Do not reuse `seat_by` (`planar/build.py:539`, `road_profile.py:618` read it as "bridged ground").

## 2. Seat and ground (rule B)
2.1 Seat of a 13i model (`terrain_model.match`, replacing its `rim_seat` call; `rim_seat` stays for `ground_shell`): `z0 = terrain_shaped.fit(grid, xy, heading, dem_many)`. Water cap: with `water_many` (`ProductionDem.water_many`, handed in like `fine`), if ≥ 5 % of outer-rim cells lie over water, `z0 = min(fit, min over those cells of (ground − bottom))`. Set `fill=True`.
2.2 Seat of a relief-skin composite: `z0 = dem_z(origin)` (the uncut corpus ground under the set's origin = the reader's `anchor_z`). Every member written OBJECT_MSL at `z0 + lift`. Set `fill=True, skin=True`.
2.3 Cut: 13k unchanged under every terrain member's plan (`terrain_cut._bound`, `cut_fit(fill=False)`).
2.4 Rim fill. New file `Ortho4XP/src/auto_patch_v2/airport/terrain_fill.py` (pure numpy/scipy), called from `auto_patch/terrain_cut_stage._cut_one` / `bake` for records whose `cut` carries `"fill": true`. Supports: outer-rim cells whose `z0 + bot` stands above the raster ground, at `z0 + bot − UNDER_M`. Each posting within `FILL_REACH_M = 60` of a support is raised to `max over supports of (z_s − max(0, d − W))`; shoulder `W = 1.25 × posting diagonal` (15.5 m at LOWS); beyond it the talus is 1:1. Inside the plan, never above the 13k bound. Never raised: postings within two postings of the tile edge (`_EDGE_POSTS`), postings inside an airport patch boundary, postings within `W` of another composite's zero footprint or terrain-member plan (that composite owns the ground: floors win). Unserved supports counted in the log line.
2.5 Zero-plane conform (relief-skin composites only, same module): a zero-level cell is a 5 m cell where a non-terrain member has a near-vertical face (|n_y| < 0.5) whose bottom lies within ±3.0 m of the frame zero (`SKIRT_M`). Zero footprint = 30 m morphological closing of those cells, less the terrain members' plans; stored on the model's seat record as `cut["plane"] = {"z": z0 − UNDER_M, "rings": [[lon, lat]…]}`, simplified as `terrain_cut.outline_rings`. Tile stage: postings within 60 m clipped to `[z − r, z + r]`, `r = max(0, d − W)`; inside the footprint the ground is the plane (filled and cut). Footprint edge drawn as a DUMMY constrained ring (as the plan edge, `terrain_cut_stage.apply`).
2.6 Order in `bake`: all cuts, then planes, then rim fills. Record content (z0, fill, plane) inside the vector-step reuse input (`O4_Step_Reuse.py:381`).
2.7 Out of scope: ground shells (#2056), bridged ground (#2053, `erode_m` records), terrain-shaped decks (#1730): unchanged, cut-only.
Consumer census (08-30l). Region: tile `.alt` postings within 60 m of a fill record's rim supports or zero footprint.
| Consumer | Ruling |
|---|---|
| Triangle4XP (reads `.alt`) | Filled and cut: the purpose |
| Tile edge / neighbour raster | Untouched within two postings; unserved supports logged |
| Plan-edge and footprint-edge rings | DUMMY constrained lines, sampled on the conformed raster |
| ProductionDem (seat, match, anchor_z, water_many) | Reads the corpus: unfilled, uncut |
| Airport patch faces and INTERP_ALT nodes | Never changed; no fill inside a patch boundary (airside is king) |
| Roads and unpatched airports (step 1 after the bake, tile.dem) | Follow the conformed ground |
| Water vertices | Keep the water datum (09-09m) |
| Other pack rows, autogen, X-Plane's Landmarks – Salzburg | Stand on the drawn mesh; never written by us |
| Object stage (rebake_after_mesh, mesh_sampler) | Reads the built mesh |
| Masks, DSF elevation raster, coastline vetting | Raw source DEM: unchanged |
| Refinement re-bake (tile.iterate) | Re-applies cut, plane and fill |
| Step reuse | Record content is an input |
| Hide terrain objects | A hidden shell gets no cut, fill or plane; its set dissolves (§4.2) |
| The hold (held_boxes, hold) | Unchanged, erode_m records only |
| ground_shell.airside_capped (rebake_inputs.py:397) | Extend to fill models: z0 lowered until no rim bottom stands over an airside vertex within W |
| placement_write.py:339–363, terrain_shaped.row_seats | Unchanged path |
| tools/terrain_model_census.py | Gains the relief-skin gate, fit seat, water-rim share, old/new z0 columns (extend; INDEX row same commit) |

## 3. Rule C: terrain seat without the 2.0 m bound
Site: `airport/terrain_base.py`, witness (3) (`TerrainLaw.within_m`, `_Witness`), `law/structures.toml:1509–1514`. New witness (5), a building: the body's or unit's walled parts (`is_walled`) have a union plan box ≥ `[placement] terrain_building_min_area_m2 = 25` with shorter side ≥ `terrain_building_min_side_m = 4`. A building passing (1), (2), (4), (5) seats on our terrain at any margin; anything else keeps `terrain_base_within_m = 2.0`; `terrain_base_over_ground` stays false (14a (1) stands for pieces). Split roofs: existing rider rule (`with_hosts`, `seat`'s non-walled branch) unchanged. Twin: a 30 m² walled body 20 m over ground with a roof rider seats on terrain with its roof; a pole at the same margin does not. Census: two-arm `tools/obj8_split_report.py PLAN --graded G --json` vs eb306d685; movers ⊆ the 42 pieces (EDDF 14, ENTC 14, KDEN 3, KDLH 1, LIMC 2, SCEL 4, LPSJ 2, VQPR 1, LOWS 1); expected passes only SCEL Espigon_E/F_Interior and LPSJ lpsj2019_tps_13.

## 4. Rule D: the hide offer
4.1 Quality test (replaces the two-clause test at `terrain_model.py:387`), against the baked frame (`dem_many`): cover ≥ 0.9 of its cells under a source of 10 m pixel or finer (`fine`); resolution: that source's pixel no coarser than the shell's own post (median plan edge of its upward triangles, floor 1 m; land_lows 16.7 m, city_centr_08 2.5 m); agreement at the L1 fit: correlation ≥ 0.9 and p90 |ground − (z0 + top)| ≤ max(3 m, 0.1 × relief) (provisional). A relief skin is re-matched against the quality ground for this test only.
4.2 Hiding dissolves the set: `placement_models` and `placement_skins` take `hidden: frozenset[def path]` (the pack's `TERRAIN_CHOICES` answer `update` ∩ remembered offer `drape_stage._FOUND`), handed in where `fine` is (`basin_witness.py:107`). A hidden shell takes the existing `ground_shell` HIDDEN path (HIDDEN_SEAT, row left out, no cut/fill/plane); its members are read and seated like any object (11d conversion, split, rule C) — the castle on the lidar hill. The answer becomes a patch freshness input (new `provenance.FRESHNESS_KEYS` entry, digest of the hidden def paths, written by `engine_v2._stamp_header`).
4.3 Stage 2 (own PR after stage 1 lands): `O4_Airport_Elevation_Insets._airport_bounding_boxes` (line 6246) unions the airport's box with the plan boxes of its fill records from the last `o4_v2_rebake_<ICAO>.json` + `inset_fetch_margin_m`; only composites within 5 km of the boundary and box area ≤ 4× the boundary box. At LOWS the box grows east 13.0200 → ~13.053. The offer appears on the build after the one that first sees the composite.
4.4 UI, both apps: no new control (the `terrain` row exists). Change the detail copy, identical in both: `Ortho4XP/src/O4_Qt_Pack_Adjust.py:55`, `Sources/SceneryKit/PackAdjust.swift:120` → "{n} objects ({uses} placements) model hills or cliffs that the tile's detailed elevation data already describes. The package's other objects are then placed on that terrain." Parity manifest unchanged. Default unticked (13i) unless relayed otherwise.

## 5. Corpus census (lane runs; movers > 0.1 m listed)
Extended `tools/terrain_model_census.py` over every installed airport pack: new relief-skin passes; old vs new z0 for every 13i model (estimates: SBRJ Sugarloaf rim min −27.49 → fit −3.32, the water cap decides; KHAF mesh01 −11.65 → −10.10; lxgb_rock and KCRW's landing-light structure are MSL rows newly admitted by llows — measure). Rule C: §3 census. Certified airports (KEGE, BIKF, LICJ) zero movers.

## 6. Bars at LOWS (drawn_gate / drawn_site on a --pack-copy build)
Hill: land_lows written OBJECT_MSL within 1.0 m of the L1 fit to the build's DEM (expect 426.3; today 405.844); castle_lows_00..02 at that zero + 80.000; no rim point more than 0.5 m over drawn ground except rim cells within the shoulder of the cliff set's footprint or city_centr_08's plan (listed with the cliff top beside them; expect ~46); reported: ditch depth at the rim (expect median ~6 m, today 22.7).
Cliff: city_centr_00..13 are 14 OBJECT_MSL rows at one zero within 1.0 m of the build DEM at 47.797953, 13.047096 (expect 429.6); no city_centr entry in the plan's splits (today 14 entries, 376 bodies); crest of city_centr_08 within 3 m of the drawn plateau behind it (486.1 vs FABDEM 486.2 at 47.7985, 13.0400); no wall foot authored within ±0.5 m of the frame zero more than 0.5 m over drawn ground; no drawn ground > 0.5 m over the zero plane inside the footprint; listed: feet authored > 0.5 m over the zero plane.
River: wall feet at 47.80060, 13.04186 (was +7.3) within 0.5 m of drawn ground (prototype 424.33 → 429.52); `11__b64` at 47.804969, 13.037201 no longer lifted (420.79 → 429.52); `00__b3` at 47.80126, 13.04196 (19 m outside the footprint, on the talus) reported.
Drawn gate PASS at sites hill, cliff, river, airport; `--against` the llows control with MOVED only at hill, cliff, river. Airport (approved) must not change.

## 7. Closing builds
`build_airport.py LOWS --tile 47 13 --pack-copy` (all three sites); `--tile 47 12` for rule C only (expect no MOVED outside C's listed pieces). Controls: frames `.harness/frames/llows/`, base arm at eb306d685. Stage 2: one `--refresh-data` of the LOWS inset and one rebuild of +47+013 to read the offer.

## 8. Stop rules
A relief-skin pass that is not terrain (bridge, roofscape, terminal): stop, report; never tune a threshold to an airport. Any mover at KEGE, BIKF or LICJ: stop. Rule C moves > 10 pieces outside LOWS, or any piece not a building by witness (5): stop, list. A LOWS bar missed after one fix iteration: stop (the one permitted iteration: add the fill records' boxes to the mesh curvature weights, `terrain_cut_stage.held_boxes`, weights only, never `hold`). A zero-level wall floating > 2 m, or `00__b3` floating: report. Materiality 0.05 m. Edit by shell in your own worktree; `tools/blast.py --find relief skin fill composite` before adding; registry twins (`windows_text_io`, `patch_env_classification`, `test_no_airport_specific_code`); report net lines and new public symbols.

Prototype scripts (scratch): /private/tmp/claude-501/-Users-noah-XPTerrainBuilder--claude-worktrees-vigilant-lederberg-4eb8b5/36801969-f4c8-4829-9e02-0dc8b5704d14/scratchpad/lows/ (gate.py, m6.py, m9.py).
