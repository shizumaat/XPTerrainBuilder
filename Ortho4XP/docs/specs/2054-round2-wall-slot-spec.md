# #2054 round 2 — thin-wall step slot, foot growth, roads under runway-end bodies (Fable review, 2026-11-13)

Review of `claude/lfence` 28f576eac (round 1: KSFO PASS). Read-only review; nothing implemented. Line numbers are on 28f576eac.

## 1. Attribution (measured)

### KLAX (33.946707, -118.399851), Fence_Terminal_1.obj piece 0, station s≈117
- The wall is 0.5 m thick (105.2 m² / 421.6 m perimeter); apron `pav5` stands on its upper face.
- The lower band's inner ring is the APRON RIM, not the wall's low face: face 432 (`adjacent_ground:wall:Misc/Fence_Terminal_1.obj#1`, 348 m², airside) shares v6644, v6643, v8389, v1572 with `pav5`, all within 0.09 m of the upper face — its only inner-ring vertices over s 43–134.
- Mechanism: `planar/zone_pass.py:57-84` (`_off_rim_runs`) drops any zone line inside the airside rim band (`weld_spacing_m` 1.0, line 100); the low face is 0.5 m from the rim, so the face closes on the rim. `model/wall_reach.py:15-23` already names this for fills (hence `FILL_SLOT_M` 1.5).
- Solved: rim 35.08/35.47; band outer ring (2.06 m past the low face) 35.02–35.08; road kerb `big_roads:-1143` (3.03 m out) 33.39. The 1.67 m step sits 2.06–3.03 m out.
- No foot held at the site: `foot_profile` piece 0 is None at s 0–18, 56–210; `wall_sides.py:289-318` `_foot_retaining` withdraws a station when top − foot < `retaining_wall_clear_step_m` 2.0; foot raised to DEM 4.5 m out (`_foot_on_ground` :274, `FOOT_GROUND_SMEARS` 1.5): 33.52 vs top 35.345 = 1.82 m. Pieces 1–4 likewise (DEM smears the step ±8 m). Lawful; no bar.
- Inferred, unchecked: `PlanarMap.road_terrace['wall']` carries a `retains` record for this wall at solve time.

### KCRW case 4 — road ridge (38.368910, -81.603493)
- The body IS a recognised walled plate: `Airport.walled_plates` `dsf:obj3228`, runway 05 (#1977 paved-end reading), footprint 9,040 m², height 45.8, step 29.5, plate 288.37.
- That footprint includes the embankment slopes (`pavement_end_plate.py:96-103` takes every |n_y| ≥ 0.7 face, no level bin; 27t bins at plate level, `walled_plate.py:163-178`). Whole plan 13,802 m², flat top 6,947 m².
- The road passes under the object: face 271 (`small_roads:-1488`, 1,887 m²) has 838 m² inside; v5403–5406, v5426–5428 in `plate_under`, each targeted/capped 288.371 (`constraints/walled_plate.py:61,65`); they solve 282.06–288.08 over DEM 261.6–270.8 (v5426 11.94 m above the embankment it should be under).
- Road welded to the runway at v286 (overrun face 1), solves 288.08 over DEM 266.54; from there the road can only fall at 10 % (`roads` longitudinal, `pavement_ceiling`, `pavement_road_cap`, `road_within_shape`); `road_ramp` seeded at v286 (log `steepest (286, 0.1, 258.8, "the road's end at 47 m")`), v5412 target 278.976 / ceiling 279.476. End pin v5416 (252.707, `roads.coverage_edge join`) solves 271.156; v5417 yields +19.1.
- At the owner's road site 18 vertices within 60 m stand 14.71–20.43 m over the DEM (mean 18.3). Why-chain v5412 → 5413 → 5414 → 5415 → 5416.
- `Diff(5406→5407, pavement_road_cap)` survives the #1201 release (generated `assembly.py:90` after `release_across`, `constraints/__init__.py:240`).
- Round 1's claims refuted: `road_ramp` rows DO name it (`('vertex:5412', 'small_roads:-1488')`); the RSA bands are not the lift (+0.9/+0.3 m mean over DEM); sliver `zone2#0` is lifted BY the road.
- Wall (owner 38.368733, -81.602572): south face x −872…−766, y −787…−797, top edge 272.5–289.9, panels to 245.5; DEM 3 m outside 258.5–263.5; nearest ground today 282–288 (the lifted road) buries the face. Owner coordinates lie 11.5 m / 8.4 m outside our placement plan (click vs placement offset — the drawn read settles it).
- Case 3 (fence 38.363304, -81.588474): `edgestrip:15:small_roads:-1476` (789 m²) at 300.08–300.80, −2.41…+0.23 vs DEM; replay only, never built.

Found, not this round: six runway vertices in `plate_under` with cap 0.17–0.29 m over solved (`plate_ground.py:54` excludes only `graded_strip`); RSA `zone2#1` 13.2–18.2 m over DEM east of the deck; DEM pokes 5–13 m through the west embankment.

## 2. Rules (general)

**R1 step slot** (`airport/wall_sides.wall_sides`, single derivation site): a retaining piece thinner than `FILL_SLOT_M` is read as `FILL_SLOT_M` thick, grown past its lower face. The effective footprint/lower face/bands/core are what `WallSides` publishes and what `road_terrace['wall']`'s `line`/`lower_face` carry. The real outline stays only for `wall_clip`, top/foot profile sampling (`wall_top`, re-stationed onto the effective face) and the object seat. No per-consumer veto. Walls ≥ 1.5 m thick byte-identical.

**R2 foot growth**: a road-family or lot cell, `side == "groundside"`, on the lower side, within `[edge_lines] host_reach_m` of the effective lower face, grows to that face (less the effective footprint with snap margin, the upper band, every other cell). Witness = the wall record; no DEM test. Airside never grows. In `classify/roles.py` after `cut_roads_at_walls` (~892), before `mint_edge_strips`. Reuse `_runs`, `_strip`, `_grow_hosts` (`classify/edge_line_mint.py:134-261`); generalise `_marking`'s predicate, don't copy. Confirm `road_terrace['wall']` holds `retains` so `wall_release`/`wall_cut` apply across the slot.

**R3 no road under a runway-end body**: every road-family cell loses the plan of a walled plate's static solid (all faces of the origin set). Derive once in `airport/walled_plate.py` from `plates_of` + partition members' triangles, memoised; NO `WalledPlate` field (rides the partition cache). Apply at the `cut_roads_at_walls` site with the snap margin. Remainders end at the body edge on their own profile via the coverage-edge pin.

**R4**: `edge_line_mint` uses `max(el.half_width_m, min_distinct_spacing_m)` (v800 fences read 0.0).

Not this round: OBJ fence/barrier chains; retaining-wall facades (KCRW: 2 `retaining_wall` + 6 `solid_wall` edge lines inert); foot threshold change; the three "found" items.

## 3. Consumer census (lane confirms by grep of `.lower`, `.lower_face`, `.poly`, `.core`, `retaining_walls`, `walled_plates` before editing)

| Consumer | Reads | Ruling |
|---|---|---|
| `classify/wall_clip` (via evidence) | wall_class pieces | real outline; unchanged |
| `classify/wall_cutback.cut_roads_at_walls`, `cut_lines_at_walls` | `WallSides.poly`, bands | effective (R1); + R3 plate plan for roads |
| `classify/retaining_wall.road_extension` (§47) | `far_side_cut` | effective |
| `classify/edge_line_mint` | cells | R2 runs before; R4 |
| `planar/overlay` → `wall_slopes`, `band_setbacks` | upper, lower, poly | effective; lower band starts 1.5 m from rim so `zone_pass` keeps it; not minted where R2 took the ground |
| `planar/zone_pass` | rim band | unchanged (the reason for R1) |
| `planar/low_extent`, `planar/shore` | wall-slope strips, walls | effective; check no thin-wall assumption |
| `constraints/wall_zone` | record faces/profiles | effective lower face; `face_top` unchanged |
| `constraints/road_ramp.wall_release`, `solve/wall_cut` | record `line`, sides | effective |
| `airport/road_ramp.wall_terraces`, `wall_pieces` | wall_class pieces | publish effective `line`; verify join to `WallSides` |
| `airport/road_profile` | poly, core, bands | effective |
| `airport/foot_lot`, `pipeline/terrace_witness`, `pipeline/late_stage` | walls | effective; no change at thick walls |
| `airport/wall_top` | real piece/face | real, re-stationed |
| `constraints/walled_plate`, `plate_ground`, road ramp `on_plate` (`road_ramp.py:2053`) | `plate_under`, footprint | unchanged; under set shrinks by road vertices |
| `model/end_area`, `rebake_plan` | plate record | unchanged |
| `pipeline/stage_code`, `O4_Step_Code`, `provenance_code` | module lists | key any new module |

## 4. Bars
- KLAX (`--replay lfence/KLAX.pkl --from classify --emit --verify`, piece 0 s 60–135): zero airside vertices move vs the lfence arm; kerb within 0.05 m of profile; ground within 0.3 m of kerb level ≤ 1.5 m past the REAL low face; no face shares a vertex with both `pav5` and the low side; no new verify family.
- KCRW road: every `small_roads:-1488` vertex within 60 m within 0.3 m of `preferred_z`, z − DEM in ≈ −1.5…+3.0 (today +14.71…+20.43); no JOIN YIELD > 0.5 m (today +18.4, +19.1); no road vertex inside the body plan.
- KCRW wall (south face x −872…−766): drawn ground within 10 m outside ≤ 0.5 m over DEM (today 282–288 vs 254–264); ≥ 10 m of face exposed near the owner's point.
- KCRW fence: drawn ground host edge → fence within 0.3 m of host level over 50 m; rise outside the line; fence base span ≤ 0.3 m.
- Controls (replay only): KSEA `l1201c` `--from classify` zero airside moves, inner-edge RSA levels within 0.05 m; KATL `katl1306` wall-slope faces and holds identical; KSFO `lfence` strips identical apart from R4, barrier span ≤ 0.18 m.
- `tools/drawn_check.py` PASS at all three KCRW sites.

## 5. Closing build
One: `build_airport.py KCRW --tile 38 -82` (cases 3 + 4, never built). KLAX judged on the replay-emitted patch; its drawn read belongs to the master's merged-batch verification.

## 6. Tests (synthetic, `tests/auto_patch_v2/`)
1. 0.5 m wall, apron on upper face, road 3 m off low face → effective footprint 1.5 m, no shared rim/low-side face, road grows to the slot, step complete within 1.5 m. 2. 1.5 m and 3.5 m walls → `WallSides` identical. 3. Airside host at the foot → no growth. 4. Road crossing a walled-plate body → cut at plan, zero road vertices in `plate_under`, remainders pinned on own profile; plate-only fixture unchanged. 5. Zero-width edge line → strip ≥ 0.5 m past it. 6. Twins: no_airport_specific_code, layers, stage-code digests, unused and dupes ratchets.

## 7. Risks
R1 reaches every thin retaining wall (census `2·area/perimeter < 1.5` over registered captures first, report the count). R2 can grow a road across a real verge within 8 m (same reach as §47). R3 changes KSEA (roads on plates lose under-plate vertices; read the drawn mesh vs the object surface in the KCRW build for sloped bodies). A missing `road_terrace` record would let the terrace verify family flag the slot step. KCRW 11 m owner-coordinate offset may be a placement error.

## 8. Owner choices
1. Thin wall: the ~1 m bank goes on the LOW side (≈1.1 m of a 1.7 m step's base hidden; airside untouched) — alternative: cut the apron back ~1 m, ditch on the airside, low face fully visible.
2. KCRW "cut down to the wall's bottom" (245.5, 13–18 m under the DEM): remove the fill against the wall, leave natural ground; do not dig below the DEM.
3. R3 (no road drawn under a runway-end object) and R2 (road at a wall's foot takes the ground to the wall within 8 m).
4. RSA lateral end at the deck body — separate issue.
5. OBJ chains and retaining facades deferred.

## 9. Not verified
`drawn_check.py` site syntax; `road_terrace['wall']` content for KLAX at solve; `road_terrace` ↔ `WallSides` join; §47/§52 text read via docstrings; KSEA/KATL/KCLT predicted not replayed; KCRW case 3 replay only.
