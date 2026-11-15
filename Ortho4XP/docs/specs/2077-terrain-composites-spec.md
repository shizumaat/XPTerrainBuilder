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

## 9. Round 2 (Fable review of round 1, 2026-11-15; base `claude/lcomp` e330ec754)

Round 1 (code 5875a15a1) missed two LOWS bars. The review replayed the round's `bake` on the control raster (log lines reproduced: cut 43 / 2,196 vs 43 / 2,192; plane 6,972 vs 6,977; fills 839/493/227 and 271/108/47 vs 839/493/229 and 270/105/47) and read it through a mesh proxy calibrated on `bars_t3.json` (47 wet feet: exact; hill rim: the lane's 5 points, 0.4–0.74 m against 0.57–1.15 m drawn). The lane's tile and worktree were already deleted: every "drawn" number below is that proxy unless it quotes `bars_t3.json`.

### 9.0 What the misses are
| Miss (drawn, round 1) | Mechanism (measured) | Ruling |
|---|---|---|
| Hill: 5 rim cells 0.57–1.15 m over the mesh | Not the fill. At 3 of the 5 the uncut ground stands OVER the rim (429.22 / 430.66 / 435.91 vs rim 426.34 / 425.30 / 435.72); the other two are supports the fill served (raster 0.10 / 0.08 under the rim). 13k's cut holds rim level for `BAND_M` = 10 m inside the plan, then drops to the 30 m-eroded top: a 3.2–5.6 m step one posting (6.9 × 10.3 m, diagonal 12.4 m) behind the rim (bounds 422.6 / 430.2 / 422.3 / 421.5 / 422.1). The rim-centre's triangle reaches it. | R1 |
| Cliff: 47 zero-level feet "over the Salzach" | All 47 stand on the set's own decks (a near-horizontal face of `city_centr_11` within −1.5…+0.3 m of the foot, same or adjacent 5 m cell): the railings of four bridges (47.8051 13.0381; 47.8007 13.0445; 47.7998 13.0490; 47.7981 13.0538). 09-09m (4): decks keep their height over water. | Not a defect. Instrument (9.4) |
| 13 feet on land beside the river, 0.5–4.5 m | The shore vertex is a water-datum vertex; the first land vertex stands a triangle inland; the bank triangle runs under the quay walls. | R3 |
| 2 feet "over the hill's plan" (47.796497 13.049707; 47.796581 13.046158; raster 5.0–5.2 m under the plane) | Just outside the hill's plan, inside the footprint: across the footprint edge the hill's cut bound holds the ground 5–8 m under the plane (the hill's skirt is authored under the town) and the bilinear raster reads mid-step. | R4 |
| `00__b3` talus foot +1.50 | 17.7 m outside the footprint; its cell's walls reach y = −3.93 (the author's river terrace). Not a zero-level foot. | Listed, not judged |
| NOT MEASURED BY ROUND 1: the river is lifted | The plane and its reach raised 428 raster postings over mapped water (median +11.6 m, max +16.5 m). The engine's own levelling (10 passes, `O4_Mesh_Utils.py:2198`) run on the control mesh's 505 water triangles with the round's raster lifts 209 of 446 water vertices (168 by > 2 m): Müllner Steg +11.0 m (415.6 → 426.5), Staatsbrücke +2.8, Mozartsteg +2.3, east bridge +3.4; water triangles tilted > 0.5 m: 17 → 68. Same simulation on the control raster matches the control mesh (p5/p50/p95 −0.14 / 0.00 / +0.26 m). Corroborated by `bars_t3`: the wet feet would float 8.9–15.9 m over the control's water; the round drew at most 9.17. Violates 09-09m (1) and the census row "Water vertices keep the water datum". | R2 |

Mesh levers, from the code (`Utils/src/Triangle4XP.c`): refinement is `maxedge · maxcurv · weight > curv_tol` (7341–7366), never below one posting (`maxedge² > pix_x·pix_y`), curvature clipped at 8 / posting (17116); a vertex is the bilinear raster (3599–3622). There is no max-error criterion. The tile is Steiner-bound (2,053,340 / 2,053,450 / 2,053,346 vertices in llows, t1, t3): weight only moves the budget. t2 → t3 (weights added): 7 → 5 hill cells at other places, 77 → 63 feet: the weights are spent. A DUMMY ring pins where a kink is, not its height. So: a drawn point is supported by one triangle edge (≤ the larger posting step `s` at the floor) plus one posting diagonal; a step must stand `W + s` from anything that must not sag, or be a constrained line whose vertices read one level on both sides. Keep the round-1 weights (`held_boxes`); add none.

### 9.1 Deviations
(a) APPROVED, generalised as the OWNED ZONE: within a zero footprint grown by `W` the plane is the ground. No rim fill raises it (round 1: its own skin's included), and no other composite's cut bound holds it down (R4). The skin's 229 unserved supports are listed by class (over its own floor / beside another composite), not judged.
(b) APPROVED: the building witness reads the smallest rectangle at any heading; a compass-aligned box is a law that depends on the placement's heading. Movers are exactly the three the spec named. Known limit, recorded not tuned: the hull of an L- or U-shaped thin wall reads as a box; if a census ever lists such a mover, stop and report.

### 9.2 Mechanism (four changes, one site each)
`W` = `terrain_fill.Raster.shoulder_m()` (15.5 m at LOWS); `s` = the raster's larger posting step in metres (10.3); `d` = one posting diagonal = `W / SHOULDER_POSTS` (12.4).

R1 — THE CUT'S EDGE BAND OF A FILL RECORD REACHES `W + s`. `airport/terrain_cut.py:_bound` (158–188) gains `band_m` (default `BAND_M`: every other caller byte-identical; `hold_bound` unchanged) and `clip_m`. For `floor_m == 0`, cells with `BAND_M < edge ≤ band_m`: `max(eroded, min(L, T))`, `T` = the lowest top within `clip_m` of the cell, `L` = today's edge-lowest term (186) read at the cell's NEAREST edge cell (`distance_transform_edt(~rim, return_indices=True)`). `cut_fit` passes them through. `auto_patch/terrain_cut_stage._fit` (91) hands `band_m = W + s`, `clip_m = d` from the tile raster for records whose `cut` carries `fill`, at every call (cut, cap, composite). Proxy: hill rim cells over the mesh by > 0.5 m outside the exemption 0–4 (max 0.74) → 0 (max 0.20); ground over the object's top unchanged (hill 297 → 312 of 6,634 cells, all within 10 m of the rim where natural ground stands over the edge; skin 171 → 179 of 1,085).

R2 — THE BAKE'S PLANE AND FILL NEVER MOVE WATER. `terrain_cut_stage.bake` (138): snapshot the raster after the cuts, before `_fill_all`; `delta = after − snapshot` at the changed postings, kept on `tile.dem` and written beside the `.alt` wherever the `.alt` is written (`apply` :295; the iterate re-bake `O4_Mesh_Utils.py:2776–2777`) as a sparse sidecar (rows, cols, delta, nx, ny; name from `O4_File_Names`; removed when nothing changed). New `terrain_cut_stage.unfill_water(tile, vertices, water_valued)`, called in `post_process_nodes_altitudes` after `water_valued` is known (2178–2179) and before the smoothing (2198): each water-valued vertex inside the sidecar's box has the bilinear `delta` at its position (Triangle4XP's `altitude()` indexing) taken off its altitude. One log line (vertices, worst metres). Never raises. The raster itself stays as round 1 conforms it, over the shore and the water: land vertices, ring vertices and the levelled roads (2,583 of the control box's 6,961 triangles are INTERP_ALT) read the plane. The sidecar is a vector-step output and a mesh-step input (`O4_Step_Reuse.py:459–464`, `_output_files`, `bundle_absent_outputs` 539–542). Scope: planes and fills only; the cut's own effect on inland water is unmeasured and stays as 13k left it.

R3 — THE QUAY. `terrain_cut_stage.apply` (281–306): the footprint's constrained ring is the boundary of `footprint − buffer(mapped water, QUAY_M)`, `QUAY_M = 1.0` (twice `SEAWALL_OFFSET_M`: clear of the 0.5 m hairline pre-flight); mapped water = `O4_Vector_Map.cached_tile_water(tile)` (3046; sea ∪ inland, the mesh's own derivation); pieces under four posting cells are not drawn. No cached water: the ring as today, one counted log line. The raster conform keeps the untrimmed footprint. Round 1 drew 871 m of the 9,677 m ring inside the river (harmless to the flood: a DUMMY mark never fences water, Triangle4XP.c:13643–13645; useless). Result: land at the plane to 1 m from the water, the drop in that metre, the water untouched.

R4 — FLOORS WIN IN THE OWNED ZONE. `airport/terrain_fill.conform_plane` (189–213) takes two bounds: `own` (this record's terrain members) holds everywhere; `others` holds only at postings farther than `W` from the footprint. `_fill_all` (233–247) builds them. At LOWS: 54 postings inside the hill's plan rise to the plane (max 6.7 m); 82 of the hill's 6,634 cells (0.2 ha, tops 0.5–10.2 m under the plane, uncut ground a median 13.1 m over them) go under the town's ground, as authored.

Proxy of R1–R4 together: hill rim 0 (max 0.19); judged feet 0 of about 1,080 (one more, 0.5 m from the shore on the Staatsbrücke abutment, is in the quay metre); land footprint 0 of 30,475 samples off the plane by > 0.5 m either way (round 1: 669 of 31,029 under it, up to 9.1 m — most of them the 0.48 ha of footprint over water; none over); water datum = control.

### 9.3 Consumer census (08-30l), rows added or changed
| Consumer | Ruling |
|---|---|
| Water and sea vertices | Levelled from the raster as it stood before planes and fills (R2). Was: "keep the water datum" — false in round 1 |
| Raster over mapped water | Still conformed (land, rings and roads read it); never read by a water vertex |
| Footprint-edge ring | Trimmed 1 m off mapped water (R3); elsewhere unchanged |
| Another composite's cut bound | Yields within the footprint ⊕ W (R4); holds beyond |
| Own skin's bound, tile edge, airport patch | Unchanged |
| Cut bound of a non-fill record (ground shell #2056, bridged ground #2053, THE HOLD) | Unchanged (default `band_m`) |
| Fill models elsewhere (SBRJ Sugarloaf, KHAF mesh01, LXGB rock) | R1 changes their cut 10–(W + s) m inside the rim: read at the batch sweep; twin T1 |
| Step reuse | The sidecar joins the vector step's outputs and the mesh step's inputs |
| Levelled roads, object stage, masks, ProductionDem | Unchanged |

### 9.4 Instrument
`bars.py` has run twice: promote it (a `--composite` mode of `tools/drawn_cover.py` if its frame fits, else `tools/composite_bars.py`; one INDEX row, one twin; no third scratch copy). Definitions:
- ZERO-LEVEL CELL: a 5 m cell whose lowest wall vertex over ALL non-skin members lies within ±0.5 m of the frame zero (round 1 took it per member: 23 of its 1,164 share a cell with a lower wall).
- JUDGED: zero-level cells inside the footprint, outside mapped water grown by `QUAY_M + 0.5`, not standing on the set's own near-horizontal face (−1.5…+0.3 m, same or 4-adjacent cell), not under a terrain member's top. Bar: drawn ground no more than 0.5 m under the zero plane (`z0 − UNDER_M`) at the foot. (Round 1 judged foot − ground, so a foot authored at +0.50 failed by 0.60 on a perfect plane.)
- LISTED, not judged: feet on decks over water (expect 47); feet in the quay metre (expect ≤ 3); zero-level feet outside the footprint (42); feet authored ≤ −3 m (19 on land, buried 3.1–7.7 m: the author's river terrace); the lowest structure over water at each bridge against the drawn water (piers end 1.4 / 4.0 / 2.8 m over the control's water at Staatsbrücke / Mozartsteg / east bridge).
- WATER: drawn water at 47.80525 13.03835; 47.80085 13.04455; 47.79985 13.04905; 47.79815 13.05385.
- The frames carry, besides the plans: the built mesh clipped to 13.025–13.065 E, 47.785–47.810 N (vertices, triangles, attributes) and the conformed `.alt` window with the sidecar, so a review measures instead of replaying.

### 9.5 Bars at LOWS (drawn, `--pack-copy`)
1. Hill: 0 rim cells more than 0.5 m over drawn ground outside the exemption (round 1: 5, 0.57–1.15).
2. Cliff feet: 0 judged cells fail (round 1 by this definition: at most 15 = 13 + 2).
3. Land footprint (footprint less mapped water ⊕ 1.5 m), 3 m samples: none more than 0.5 m over or under the plane.
4. Water: the four points within 0.5 m of the control (415.57 / 420.11 / 419.92 / 418.54); `unfill_water`'s line quoted.
5. Still hold: land_lows 426.28 and castle 506.28 OBJECT_MSL; 14 city_centr rows at one zero, no split; crest gap; river walls at 47.80060 13.04186 and `11__b64` within 0.5; rule C movers exactly SCEL ×2, LPSJ ×1; KEGE / BIKF / LICJ 0.
6. Airport: patch node diff against the llows frame over the common nodes; round 1 moved 2 by > 0.05 m (0.12 at 47.797646 13.000123; 0.07 at 47.789408 13.000064, both at the 13° E edge) and 127 by > 0.01. Build +47+012 too and name the roles; any AIRSIDE node moved > 0.05 m is a stop.
7. Drawn gate `--against` the control: MOVED only at hill, cliff, river. (Roads FAIL at the airport, 3.87 m at 47.796903 13.003848, stands in the control at 3.86: not this round's.)
8. Reported: triangles inside the fill boxes against the tile's total and its Steiner limit; the hairline pre-flight line (round 1: 33 / 392 / 94 / 1,199, 4 unmeshable).

### 9.6 Twins, builds, stops
Twins (synthetic, one each): T1 a hill whose rim climbs 35 % along its length on a 6.9 × 10.3 m raster — inside the plan within `W + s` of the rim no posting stands more than 0.5 m under its nearest rim cell's bottom unless the top within `d` is lower, none stands over that top, and without `fill` the bound equals today's; T2 a water vertex's altitude after `unfill_water` equals the bilinear unfilled raster to 1e-4, a land vertex is untouched, no sidecar is a no-op; T3 the ring keeps 1 m off a water rectangle, small pieces are dropped, no water leaves the ring as it was; T4 another model's bound yields within `W` of a footprint and holds beyond, the own skin's holds throughout; T5 the judged set (deck, terrace, quay metre, +0.50 foot).
Builds: `build_airport.py LOWS --tile 47 13 --pack-copy` and `--tile 47 12 --pack-copy`, once each as the closing test; iterate on the twins and a `bake` replay. Control: llows frames, base arm eb306d685.
Stops: a bar of 9.5 missed after ONE fix iteration (an implementation defect only; `QUAY_M`, `W`, `s`, `d` and the ±0.5 bars are never tuned) → stop, frames kept as 9.4 says. A water point more than 0.5 m off the control → stop. A new unmeshable hairline inside the town box → stop. Any mover at KEGE, BIKF, LICJ → stop. Materiality 0.05 m. Build time (estimated, not measured): R1–R4 add under 0.5 s to the tile's vector step and nothing to the airport patch; the lane quotes the measured step times. Never raise the lane cap; delete scratch builds when you report (after the frames are written). Registry twins as §8; report net lines and new public symbols.

### 9.7 For the owner (one question; recommendation first)
The town stands 9.4–13.9 m over our river (zero 429.6 from the ground under the set's origin; water 415.6–420.1); the author's piers reach only 5.6–8.3 m under the zero, so they end 1.4–4.0 m over the water, and the quay is a 1 m band of our terrain under the author's walls. RECOMMENDED: keep the seat (the cliff's crest meets the plateau within 0.9 m and the hill and castle hang on the same ground) and judge it in the sim. The alternative — lower the set until its lowest wet structure meets the water, about 1.4–4 m — opens the crest by the same amount and cuts 27.9 ha deeper. No code this round either way.

### 9.8 Not in this round
The hide offer's stage 2 (§4.3); the cut's own effect on inland water; a second plane for the author's river terrace; rule C.
