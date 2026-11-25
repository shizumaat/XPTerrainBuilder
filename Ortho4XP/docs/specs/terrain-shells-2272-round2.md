# Terrain shells (#2272), round 2: the shell's body shows, its edge band is buried, the ground is feathered to it

Status: SPEC (Fable scout, 2026-11-24, one-miss review of lane lshell
93967787b..891891c36, reverted at 9cc935ab6). Law: `docs/RULINGS.md` 2026-11-24k,
2026-11-13g / 17r (drawn gate at integration), 2026-08-30l (consumer census),
2026-09-09m (water is a datum), 05e (no airport-specific code).
Line numbers are at 7232cde28. Site: TFFJ, tile +17-063.
Owner decisions D1-D3 (section 6) are pending at commit time.

## 1. What round 1 did, and what was measured

Round 1 recognised the 16 `OBJECT_MSL` shells, kept all 16, seated each at the
author's datum (-1.0 to 3.0 m), cut the ground under them with the terrain-model
cut, and added `terrain_fill.rim_tuck`. Integration: `drawn_cover` RocksE 4,007
and HillTopHarbour 2,867 open off-patch samples over 0.05 m (worst +13.18 and
+16.52 m); `drawn_gate` roads Cliffs 0.31 -> 0.58 m (new FAIL), HillTopHarbour
1.37 -> 1.58 m.

No merged tile build exists any more. Drawn numbers below are from the saved
lverify JSON for RocksE and HillTopHarbour; raster numbers are a replay of the
lshell bake on the control `.alt` (`Rebuild_cache/zOrtho4XP_+17-063`, 11-24 06:37).

| measured | RocksE | HillTopHarbour |
|---|---|---|
| drawn mesh - replayed lshell raster at the over samples, median (p10 / p90) | +0.06 (-0.92 / +0.90) m | -0.05 (-2.36 / +0.91) m |
| replayed raster - shell top there, median / max | 3.70 / 12.36 m | 4.91 / 14.95 m |
| the cut's own bound - shell top there, median / max | 3.83 / 14.67 m | 5.17 / 16.83 m |
| over samples deeper than 10 m from the edge | 4 (worst 1.44 m) | 8 (worst 0.75 m) |

## 2. Mechanism

1. THE MESH FOLLOWED THE RASTER. The path works: `O4_Vector_Map.py:2388`
   `TERRAIN_CUT.apply` -> `terrain_cut_stage.bake` (:168) -> `_cut_one` (:136,
   lowers only, :163) -> `_fill_all` (:283) -> `write_alt` (:462). Triangle4XP
   samples the `.alt` per vertex. `O4_Mesh_Utils.post_process_nodes_altitudes`
   gives land vertices the water-side changes back (`refill_land`, :2208). The
   refinement re-bake repeats it (`O4_Mesh_Utils.py:2823-2826`). The tuck
   reached the mesh within 0.1 m (median).
2. THE RASTER ITSELF STOOD OVER THE SHELL, BY RULE. `terrain_cut._bound`
   (`terrain_cut.py:199-203`): within `BAND_M` = 10 m of the plan edge the ground
   is never cut under the highest rim BOTTOM within 10 m. A fill record extends
   that level `W + s` (about 28 m) inside (:204-212). `rim_tuck` added a floor at
   the highest rim bottom within one posting. Round 1's own replay log showed it:
   2,742 of 3,627 rim cells still buried over 0.05 m. Its bar read only the mean.
3. THE EDGE BAND IS A SKIRT. Median over each rim: on HillTopHarbour, Homesite,
   HillS and RocksE the sheet rises 9.0-10.0 m in its outer 5 m (2 m per metre);
   RocksNW 6.4 m; Rocks, TheRock and Hilltop1 4.1-4.9 m in 5 m and 7.7-8.7 m in
   10 m. Cliffs, Cliffs2 and Cliffs4 have none (-0.2 to +0.8 m). DEM - shell,
   median:

   | class | at the rim | 10 m inside |
   |---|---|---|
   | inland rocks (9 shells, 6,972 m of rim) | +4.2 to +11.5 m | -1.9 to +3.8 m (RocksNW -4.5) |
   | coastal cliffs (Cliffs 1-4, Gustavia) | +7.8 to +12.6 m | +1.6 to +9.6 m |
   | CliffHotel, LesGrosIslets, BirdIslets | rim under the sea datum | - |

   Over all 16 shells 8,516 m of rim stand above the sea datum; our ground is over
   the rim on 8,332 m (97.8 %) and under it by more than 0.5 m on 135 m (1.6 %).
   So the author's height is the right seat. The "2-40 m off" was the skirt's
   depth, plus a 30 m DEM that is 7-12 m high on the sea cliffs.
4. THE MOAT. Cutting the band to the rim's bottom lowers the ground AT the rim:
   on 55 % of the rim with the 13k band alone (median 3.1 m, max 19.4 m), on
   69 % with the tuck (median 5.4 m, max 21.1 m). The mesh then runs from our
   ground outside down into the moat, across the skirt. Those are the band over
   samples.
5. THE ROADS. The new FAIL points are 6.9 m (Cliffs) and 7.0 m (HillTopHarbour)
   OUTSIDE the rim, on the tuck's 1:1 talus and the ramp into the moat. 1,606 m
   of road lie inside kept plans (29 rim crossings), 2,141 m within 10 m outside.
   Road-ribbon proxy, worst 1 m step outside kept plans, Cliffs / HillTopHarbour
   / RocksE: control 0.25 / 0.44 / 0.14; 13k band + rim fill 0.79 / 0.76 / 0.14;
   round 1 as merged 0.93 / 0.89 / 0.34 (drawn 0.58 / 1.58 / 0.35).
6. NOT HELD. `terrain_cut_stage._held` (:621) holds only records naming
   `erode_m`. Nothing guaranteed the drawn triangles under a shell.

## 3. The law (general; no name, no coordinate, no per-airport number)

A kept shell has a BODY (deeper than `BAND_M` from its plan edge) and an EDGE
BAND (the outer `BAND_M`, where a shell carries its skirt).

- S1 SEAT, unchanged from round 1: recognition and admission
  (`terrain_shell.small_shape` / `small_match`), the frame zero at the author's
  `OBJECT_MSL` datum with the wet-rim cap, one rigid frame, never split, the hide
  offer by `terrain_model.quality()`, the per-object override in both apps.
- S2 THE BODY SHOWS. Under the body the ground is cut to the shell
  (`erode(top, ERODE_M) - UNDER_M`, as 13k). In the fill band's inner part
  (`BAND_M` < edge <= `W + s`) the bound is the lowest top within one posting
  diagonal (the existing `near_top`), so the cut does not bleed to the rim.
- S3 THE EDGE BAND IS NOT CUT. Within `BAND_M` of the edge the cut has no
  bound: the ground there is our ground, lowered only by S4. It may stand over
  the shell there (the skirt is buried). `rim_tuck` and `_skirt_floor` are deleted.
- S4 THE GROUND IS FEATHERED TO THE BODY'S EDGE. At each body-edge cell
  (`terrain_model.outer_rim` of the body mask) the residual is
  `e = min(0, z0 + top - UNDER_M - ground)`, read on the raster BEFORE any cut.
  Every free posting outside every kept body and within `FEATHER_M` of a
  body-edge cell takes `ground + w * E`. `E` is the inverse-distance-squared
  mean of `e` over the 16 nearest body-edge cells (distance floored at half a
  plan cell). `w = clip(1 - d / FEATHER_M, 0, 1) * clip(d_frozen / FEATHER_M, 0, 1)`,
  `d` to the nearest body-edge cell, `d_frozen` to the nearest frozen ground
  (patch boundary, tile edge). One correction over ALL kept shells: the most
  negative `w * E` wins. Only lowers; never under `min(ground, 0 m)`; never a
  frozen posting. The change joins the planes' and fills' delta, so the dry
  raster and `refill_land` / `unfill_water` carry it.
- S5 NO EDGE FLOATS. After S2-S4 the existing rim fill (`terrain_fill.rim_fill`)
  raises the ground to every rim cell still standing over it. In the edge band
  it has no cap; under the body the cap is the S2 bound.
- S6 THE BODY IS HELD BY THE MESH. A BODY RING is drawn as a second DUMMY
  constrained ring beside the plan outline, so no drawn triangle spans from
  the rim to the body. It encloses every 1 m sample deeper than `BAND_M - 1 m`.
  After the altitudes are post-processed, the existing hold
  (`terrain_cut.hold_heights`) lowers the free vertices inside the body ring
  until every drawn triangle stands under `z0 + top - UNDER_M` at every 1 m
  body sample. For a shell record: the plan-outline ring's vertices are FIXED
  (the rim never floats by the hold); water-valued vertices, patch pins and
  INTERP_ALT vertices inside the patch coverage are FIXED; a road-ribbon vertex
  under the body is FREE (the shell covers the road there); the water floor
  (`water_floor`) stands.

Constants, all existing: `BAND_M` 10 m, `ERODE_M` 30 m, `HOLD_CELL_M` 1 m,
`UNDER_M` 0.1 m, `FEATHER_M = terrain_fill.REACH_M` (60 m, also the insets'
default feather), `DRY_M` 60 m. No new tuned number.

## 4. Replay of the proposed raster (control `.alt`; 3 m samples, 16 shells)

| arm | body over 0.05 m (of 36,522) | band over | ground at the rim lowered > 0.5 m | rim floating > 0.5 m (of 8,516 m) | road proxy Cliffs / HTH / RocksE |
|---|---|---|---|---|---|
| control (no cut) | 16,753 (45.9 %), worst 22.4 m | 75 % | 0 % | 135 m | 0.25 / 0.44 / 0.14 |
| 13k band + rim fill | 288 (0.8 %), worst 4.8 | 59 % | 55 %, median 3.1, max 19.4 m | 191 m | 0.79 / 0.76 / 0.14 |
| round 1 as merged | 256 (0.7 %), worst 4.6 | 54 % | 69 %, median 5.4, max 21.1 m | 276 m | 0.93 / 0.89 / 0.34 |
| S2-S4, body eroded 30 m, feather 60 m | 1,231 (3.4 %), worst 8.7 | 70 % | 52 %, median 2.5, max 13.6 m | 419 m | 0.41 / 0.44 / 0.14 |
| S2-S4, body eroded 15 m, feather 60 m | 1,666 (4.6 %), worst 8.7 | 72 % | 48 %, median 2.4, max 13.6 m | 155 m | 0.41 / 0.44 / 0.14 |

The S rows are before the rim fill (S5) and the hold (S6). The spec'd bound
(S2: one posting diagonal near the band, 30 m beyond) lies between the two.
The body remainder is the hold's work. The floats are the rim fill's work.
The feather lowers 3,337 postings outside the plans (34.4 ha), median 1.4 m,
p95 6.8 m, max 12.2 m, almost all at the sea cliffs; the body-edge residual
is median -1.2 m, p5 -13.1 m. With `FEATHER_M` 100 m the Cliffs proxy is 0.37
and 74.1 ha are lowered. Road centreline samples under shell bodies: 935;
with ribbons fixed, 40-69 stand over the shell (worst 3.0-4.0 m; Cliffs2,
Cliffs4, Rocks, Hilltop1, CliffHotel). That is why S6 frees them.

## 5. Consumer census (RULINGS 2026-08-30l)

Region: the tile raster and mesh inside a kept shell's plan, and within
`FEATHER_M` of its body edge.

| consumer | reads | ruling |
|---|---|---|
| Triangle4XP (`.alt`) | cut, feather, rim fill | as written; within `DRY_M` of mapped water the dry raster (`write_alt` :462) |
| curvature weights (`_weight_boxes` :641, `O4_Mesh_Utils._apply_hold_curv_weights` :590) | plan box grown by the reach | shells ride the fill records' boxes; water cells keep their weight |
| plan-outline ring, body ring (`_edge_lines` :429) | DUMMY constrained lines on the cut raster | both drawn; outline vertices fixed in the hold |
| `unfill_water` / `refill_land` (`O4_Mesh_Utils.py:2207-2208`) | the delta sidecar | the feather's change is in it; water vertices never move |
| THE HOLD (`terrain_cut_stage.hold` :766, called `O4_Mesh_Utils.py:2478`) | drawn triangles under the body | S6 |
| road banks (`O4_Road_Bank`, before the hold) | free vertices beside ribbons | unchanged; the hold runs last and may lower a banked vertex under a body |
| roads (step 1, after the cut; `o4_levelled_roads.json`) | `tile.dem` in memory | follow the feathered ground outside and the cut ground inside; under a body the hold may lower the ribbon |
| apt.dat pavement of an unpatched airport | `tile.dem` | follows; its INTERP_ALT vertices are not road ribbons and stay fixed |
| airport patch | frozen postings, `alt_abs` nodes, pins | never changed; the feather fades to zero at the patch boundary; on-patch samples reported (B2) |
| `ProductionDem` (seat, match, quality, the solve) | corpus DEM | uncut, unfeathered |
| masks, DSF elevation raster, coastline vetting | raw source DEM | unchanged |
| refinement re-bake (`O4_Mesh_Utils.py:2823-2826`) | `bake` + `write_alt` | re-applies S2-S5; the hold runs after every mesh |
| step reuse and code keys (`O4_Step_Reuse.py:384`, `O4_Step_Code.py`, `O4_Object_Stage_Code.py`, `provenance_code.py`, `partition_code.py`, `stage_code.py`) | the cut records | `terrain_shell` beside `terrain_model`, as round 1's twins |
| hide answer (`_hidden` :77, `pack_choice`, `pack_terrain`, `tile_rebuild_pending`) | the per-pack and per-object answers | a hidden shell: no cut, no feather, no rings, no hold; its row left out |
| object stage, 11d conversion, the OBJ8 split | the model's origin set | never split, never converted; the shell's row `OBJECT_MSL` at `z0` |
| riders (pack `OBJECT` / `AGL` rows and autogen on the plan) | the drawn mesh | follow the cut ground under the shell; REPORTED (see 8) |
| another kept shell (RocksNW / RocksE share 435 m of rim, 4,229 m2) | each other's plan | both bodies cut; one feather; a rim inside another kept plan is not judged for float |
| other composites (terrain models, relief skins, ground shells, bridged ground) | `owned` | unchanged; a rim fill stays `W` clear of their ground |
| neighbour tile | edge postings | frozen (two postings) |
| `tools/drawn_cover.py`, `tools/harness/drawn_gate.py` | the built tile | bars in 6 |

## 6. Acceptance

Owner decisions the master needs before the integration judges. Without D1
the round cannot pass: 24k (3) read as "0 over in the rim band" requires the moat.

- D1 THE EDGE BAND. Within 10 m of a kept shell's edge our ground may stand
  over the shell (its skirt is buried); deeper than 10 m nothing over 0.05 m;
  the edge never floats more than 0.5 m over land. Samples on water-valued
  triangles are not judged (2026-09-09m).
- D2 THE FEATHER. Our ground within 60 m of a kept shell is lowered toward
  it where the DEM stands over the body's edge (TFFJ: 34.4 ha, median 1.4 m,
  max 12.2 m; nothing at the patch boundary).
- D3 (only if the gate trips there) a road sample under a kept shell's body
  is hidden and not judged by the roads gate.

Drawn bars (integration, one TFFJ tile build with `--pack-copy`, 17r):

- B-BODY: `drawn_cover.py TFFJ --tag T --object <each of the 16> --judge inner`
  -> 0 open off-patch samples over 0.05 m deeper than `BAND_M`, water-valued
  triangles excepted. Round 1: 4 and 8 at the two shells read.
- B-EDGE: every RIM run over land and outside another kept plan has
  `min_m >= -0.5`.
- B-ROADS: `drawn_gate.py TFFJ --tag T --site Cliffs=17.906316,-62.854916,150
  --site HillTopHarbour=17.901217,-62.85174,150 --site RocksE=17.90642,-62.848157,150
  --against <control JSON>`: no new road FAIL, no MOVED; mesh PASS;
  patch->drawn 0 of 1,567.
- Reported, not judged: band over share and worst per shell, SINK, RIDERS.

## 7. Evidence order (synthetic first; the lane stops before the tile build)

1. Twins, headless:
   - `_bound(..., skirt=True)`: a skirted dome keeps its band uncut and the
     ground at the rim unchanged; a flat margin is cut only beyond the band;
     `skirt=False` is byte-identical to today on the terrain-model and
     bridged-ground fixtures.
   - `edge_feather`: only lowers; continuous; zero at a frozen posting and at
     `FEATHER_M`; never under the sea datum; one correction for two abutting shells.
   - the body ring encloses every 1 m sample deeper than `BAND_M - 1 m`.
   - the shell hold on a synthetic mesh: body samples under; outline vertices
     unmoved; a ribbon vertex lowered; a patch vertex fixed and its sample
     counted unresolved.
2. `tools/terrain_shell_replay.py TFFJ` (new, promoted from the scout's probes;
   INDEX row; test): the section 4 table on the control `.alt` with the lane's
   code. Lane bar: rim floating over land outside other kept plans 0 m after
   the rim fill; ground at the rim lowered on no more of the rim, and no
   deeper, than the S rows; road proxy under 0.5 m at Cliffs and unchanged
   (within 0.02 m) at HillTopHarbour and RocksE. If Cliffs is over 0.45,
   `FEATHER_M` is the lever, as one general constant, and the lane says so.
3. `tools/terrain_model_census.py` on the TFFJ pack: 16 shells, `z0` = datum.
   Plan diff at SBRJ, KHAF, LOWS and TNCS: their records unchanged, no `shell` key.
4. STOP. The lane reports the three `--site`s and the 16 `--object` names. It
   deletes its scratch builds and never raises the lane cap.
5. Integration (master): `venv/bin/python tools/harness/build_airport.py TFFJ
   --tile 17 -63 --pack-copy DIR --tag T`, then the bars of 6. Keep the failing
   arm's tile DSF and pack copy until the review closes.

## 8. Files, API, limits

Re-land round 1 (`git revert 9cc935ab6`), then:

- `src/auto_patch_v2/airport/terrain_cut.py`: `_bound`, `_cut_grid`, `cut_fit`,
  `hold_bound` take `skirt: bool = False`; new `body_rings(fit, to_ll)`; the
  module doc gains the law and the census rows.
- `src/auto_patch_v2/airport/terrain_fill.py`: delete `rim_tuck`,
  `_skirt_floor`; new `edge_feather(raster, to_xy, supports_xy, residual,
  feather_m) -> (rows, cols, delta)`; `Raster` gains an optional `frozen_dist`.
- `src/auto_patch_v2/airport/terrain_model.py`: `seat_records` writes
  `cut["shell"] = True` in place of `"tuck"`.
- `src/auto_patch/terrain_cut_stage.py` (in `KEEP`; no new module there):
  `_fit` passes `skirt`; residuals read before the cut loop in `bake`; the
  feather pass in `_fill_all` before the rim fills; `_outline` adds the body
  ring; `_held` and `_hold_one` take shell records; `hold(..., ribbons=())`.
- `src/O4_Mesh_Utils.py:2475-2480`: pass the road-ribbon vertices to `hold`
  (identified from the levelled-roads sidecar, `O4_Road_Bank`'s reader).
- `tools/drawn_cover.py`: `--judge {all,inner}`, `verdict.open_off_over_inner`,
  a `where` label (land / water / shell) per RIM run; INDEX rows; tests.
- Tests: `tests/auto_patch_v2/test_terrain_cut.py`, `test_terrain_cut_hold.py`,
  `test_terrain_fill.py`, `test_terrain_shell.py`, `tests/test_drawn_cover.py`,
  the replay tool's test.

Frozen: `o4_engine/events.py` wire names; `terrain_model.SEAT`; the seat
record's keys other than `cut.shell`; `terrain_cut.hold_heights`;
`pack_terrain` / `pack_choice` as round 1 left them. CI registry gates as
round 1 (`windows_text_io`, `patch_env_classification`, closure twins,
`test_v1_retired`, ratchets). `tools/blast.py` before each edit.

Build time: no cost on a tile without shell records (early return). With
them: one feather over the shells' windows and one hold over the body samples
(TFFJ about 0.37 km2 of body); expected under 5 s of the 300 s tile budget.
The lane states the measured step-1 and mesh-step deltas from its replay.

Out of scope, reported for the master:

- RIDERS. In round 1's build four pack rows on HillTopHarbour (three houses, a
  lighthouse) stood 5.0-14.7 m under the shell and two on RocksE 16.3 m. This
  spec does not change that. The fix is a seat rule (an `OBJECT` / `AGL` row over
  a kept body is written `OBJECT_MSL` on the shell), its own small spec.
- DATA. TFFJ's inset is Copernicus GLO-30 at 30 m with 47.8 % of its pixels
  building-masked and refilled. Finer elevation would move TFFJ onto 24k (1).

Probes (promote into `tools/terrain_shell_replay.py`):
`/private/tmp/claude-501/-Users-noah-XPTerrainBuilder--claude-worktrees-confident-kilby-fb0990/b0ea8518-a5e5-4c54-9cdb-a897b332f27c/scratchpad/scout2272/`
(`probe10.py`, `probe11.py`; `lshell_src/`, `polys.pkl`, `rims.pkl`).
