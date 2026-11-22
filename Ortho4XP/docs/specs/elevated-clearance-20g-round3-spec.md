# 20g/20k round 3 — the road or rail under a pack soffit is an OPEN TRENCH tied to the group's seat witness

Fable TWO-ROUND-CAP-REVIEW of lane lskyclear round 2 (origin/claude/lskyclear 5452e8702), 2026-11-20. Owner decisions O1–O6 in §C are pending until recorded in RULINGS.

## A. Why round 2 missed
1. Ceilings on ROAD-family vertices only; `classify/ribbon_mint` mints no ribbon inside a pad face and a stretch along a lot is the lot, so 23 roads + 8 rails on pads and 9 on lots had no vertex to bind; rails have no face.
2. The seat was a predicted number (DEM median) because a DEM-predicted highest vote overshoots the mesh (27.4+ vs 27.184).
3. Ceilings bind at vertices; the census reads between them (8 road faces).
4. Nothing ties ground under low members to the lifted seat (new floats 0.5–0.88; prior 0.82–1.62 grew to 1.45–2.25).
5. No airside reach guard beyond "vertex shared with an airside face" (OMDB/LGAV service roads would be lowered unexamined).

## B.1 Mechanism
Each short crossing is lowered by the EXISTING open-trench family (R6 sunken road, `planar/viaduct_road.py`: `_route`, `_runs`, `_side`, `_climb`, `_half` → `object_corridor.Group` kind `"sunken_road"`), carved by the structure pass (`planar/structures.py`, `extra_groups`) out of whatever cell lies there (pad, lot, ribbon, ground). The trench floor is tied by relative rows to the SOLVED surface under one named seat anchor of the crossing group (template `constraints/viaduct_floor.py` `_half_rows`: floor = mean solved witness − depth). The patch publishes the seat as the solved surface at that anchor (at emit), and the object stage obeys it. Pads/lots: the trench cuts the cell; road faces: flat floor under the soffit; rails: trench floor at `[tunnel] rail_ramp_grade` 0.0125 / `rail_ramp_max_grade` 0.035 (no ribbon class); apron+pad: refused by the airside guard and listed.

## B.2 Consumer census (08-30l)
| # | Pass | Round-3 ruling |
|---|---|---|
| 1 | `airport/elevated_crossing.read_crossings` | KEEP; the ONE read |
| 2 | `airport/crossing_seat.crossing_records` | CHANGE: no median seat; emit group, per-part DEM votes + feet, crossings with `soffit_y`, stations, class; rails included |
| 3 | NEW `crossing_seat.seat_plan(planar, law, airport)` | anchor, `dz`, low-member ties; read by rows and emit |
| 4 | NEW `planar/soffit_road.soffit_road_groups` | trench groups, called beside `viaduct_road_groups` |
| 5 | `planar/viaduct_road` | `_runs/_side/_climb/_half` take `grade, cap, min_run, ground_fn`, id/label params (defaults = today; R6 byte-identical twin) |
| 6 | `planar/structures` | +1 call; verify carve of `building`/`parking_lot` cells, `airside_cut_roles`, `pad_ends`/`pin_knives` by capture |
| 7 | `planar/level_regions` seed/low_level | not used; a crossing in a seed's passage refused (`_in_passage`), class `level_seed` |
| 8 | `planar/structure_service` passage (§34(12)(5)(e)) | unchanged; twin: never a bore and a trench on one way |
| 9 | `constraints/structures` sunken_road pins | skip `soffit-road:` halves like `viaduct-road:` |
| 10 | NEW `constraints/soffit_floor.soffit_floor_rows` | relative floor + climb rows, hard, in `[design] hard_rulings`/`hard_conflict_ranks` |
| 11 | `constraints/foot_rows` | low-tie bodies take the tie level (§B.7) |
| 12 | `constraints/pads`, `cluster_pad`, `platform.landing_rows` | not edited; rim/top vertices on rigid faces take no trench row (R3) |
| 13 | `constraints/elevated_clearance` (lskyclear) | DELETE |
| 14 | `road_bridge_ceiling`, `road_bridge_gen` | untouched; ways under generated/pack bridges are bridge law |
| 15 | `pipeline/emit_stage.render` | publishes `provenance.elevated_crossings` with `zero` = SOLVED seat |
| 16 | `airport/touch_seat` | KEEP lift; obey rule tightened (§B.4 (5)) |
| 17 | `airport/airside_group_seat`, `Fixed` | a group with an airside-fixed node is never lifted |
| 18 | stacked_deck, connector_warp/deck_profile, split_bar, tilt_float | order unchanged; movers outside group 0 > 0.1 m |
| 19 | `airport/msl_feet` (20l) | Stage 2 only (§B.9) |
| 20 | `placement_read.pads_rims_from_graded`, `rebake_inputs` | read-only check |
| 21 | `tools/drawn_site_crossings.py` | every row carries its 20g class |

## B.3 Population and classes
Passage population: component not bridge-law; least soffit ≥ `[road_gen] witness_share` × `[bridge] clearance_minimum_m` (2.1 m) over frame zero; spans 0.8 of carriageway. Each short passage takes one class: `trench`; `airside_held` (G1: trench footprint ⊕ rim within `[design] pad_frontage_m` of any `airside_cut_roles` cell; G3: inside airside bands' envelope `ribbon_mint.ribbon_extent` zone-2, or a 1206 truck route; a `building` pad is NOT airside for this test); `level_seed`; `depth_cap` (> `[cutout.sunken_road] max_depth_m` 4.0); `no_route`; `no_seat` (spread > `touch_seat.SEAT_MAX_M`); `low_soffit` (< 2.1 m, reported, not in bar). Act at short > 0.05 m. New tunable only `[elevated] clearance_margin_m = 0.10`.

## B.4 The seat (20k)
1. Votes at load per building part: `DEM − y` over feet (keep lskyclear `_vote`); eligibility = touch pass's own.
2. ANCHOR = highest-vote building part; its feet are the WITNESS.
3. `dz ≤ 0` in `seat_plan`: a group with a building part within `airside_group_seat.TOUCH_M` of an airside-role cell takes no lift (anchor := that part, `lift=false`); otherwise `dz = min(0, min over members on UNRAISABLE ground with control float ≤ split_bar_m of (vote_m + split_bar_m) − vote_anchor)` (unraisable = airside-role face, or held / airside-led pad).
4. At EMIT: `zero = mean_i(solved(foot_i) − y_i) + dz` over witness feet (barycentric, `constraints/face_index.FaceIndex`); add `anchor`, `dz`, `lift` to `crossing_seat.PUBLISHED`.
5. Object stage `touch_seat._seat`: `zc = min(published zero, max(votes))`; count `crossing_seat_clamped` when the clamp bites > 0.05 m; no lift when `lift` false or any node `Fixed` by airside contact.

## B.5 Trench planner — NEW `planar/soffit_road.py` (prefix `soffit-road`)
Ways: `elevated_crossing.crossable`; half-width `model/road_clearance.carriageway_width_m`. Route `viaduct_road._route`; parallel carriageways/tracks within `dual_carriageway_max_separation_m` are one trench. Covered run = crossing stations ± max(5 m, one carriageway width), `min_run` 0, floor FLAT over the run. Planned floor = predicted seat + least `soffit_y` − `design_clearance_m` − margin (geometry only; rows hold the real value). Ramps via `_side`: roads `[tunnel] ramp_grade` 0.05 / `ramp_max_grade` 0.10; rails 0.0125 / 0.035; `ground_fn` = DEM. A way END inside the unit's plan stays level at the floor to the end (Law B end-wall precedent; O4). Same-group overlapping runs merge at the lowest floor; different groups: lower floor governs, other listed if < need + margin. Refusals named in `stats.refused` with class.

## B.6 Rows — NEW `constraints/soffit_floor.py` (imports no planar module; half prefix literal + twin)
R1 floor: per level station vertex `z_v − Σ w_k z_k = c`, `w_k` witness barycentric weights averaged over feet, `c = dz + soffit_y − need − margin − mean(y_feet)`; generalise `viaduct_floor._half_rows` `(ws, depth)` to weighted terms (extend, don't fork). R2 climb: `_half_rows` as is. R3 never tied: stage-1 vertices, seam vertices and stations, vertices shared with rigid-role (`pads.rigid_roles`) or airside faces — and drop the generic structures rim/top pins there. R4 staging: row lives in the stage where the floor is solved with the witness fixed; prefer (within 0.05 m vote) an anchor on a held pad (`model/platform.datum_vertices`); read `solve/design_stage.stage_split` first. FALLBACK only if the split can't: absolute `Pin`s at plan value with margin 0.30, counted `soffit_floor_absolute`.

## B.7 Terrain under low members
Each ground-contact member of a lifted group with control float ≤ 0.5 m and feet on raisable ground: soft `foot_rows`-form rows (`[design] foot_row_rulings`) `surface(foot) − Σ w_k z_k = y_foot − mean(y_anchor feet) + dz`, replacing its DEM-fit level in `foot_rows.foot_targets`. Members floating > 0.5 m at control: listed `prior_float`, no row (O3).

## B.8 lskyclear code
KEEP: `airport/elevated_crossing.py`; `tools/drawn_site_crossings.py` + hook; `Airport.elevated_crossings`; `placement_read.crossings_from_graded_doc`; `object_stage._crossings_published`; `touch_seat` lift (`_lifted`, `_crossing_lifts`, class `crossing`, counts); replay plumbing; the three test files; INDEX row. CHANGE: `crossing_seat.py`; `planar/elevated_crossings.attach_crossings` (no densification); `emit_stage` (solved zero); stage_code closures. DELETE: `constraints/elevated_clearance.py`, its GENERATORS entry, its two `emit.toml` rows (replace with soffit-floor head), stage_code entries, the `_densified` call.

## B.9 Stage 2: KDFW OBJECT_MSL frames
Precondition: `claude/lmslframe` merged. An MSL frame (20l) is a crossing unit (faces at `y + (set elev − reference set elev)`); its seat is msl_feet's own function on the solved surface at emit; witness = governing set's lowest feet. `msl_feet` not edited; publish + trenches only. If patch-side `objects` don't carry MSL geometry, report the blocker; no second reader.

## B.10 Guards
G1, G3, no-lift for airside-held groups, R3, `airside_cut_roles`. Airside movers vs control ≤ 0.05 m expected; > 0.5 m or any new airside grade violation (20b) = FAIL.

## B.11 Evidence and bars
Tools: `v2_solve_replay --capture ICAO` then `--replay --from classify --emit`; `v2_rebake_replay plan --write-pack`; `drawn_site --crossings --graded`; `drawn_site --plan`. Control = same capture on base ref (clean worktree; identity mismatch is a STOP).
KMCO (+28-082): (a) owner site 28.42998,-81.30440: station rails -11396/-11399/-11402/-11406 under centro_2 deck ≥ 4.95 (was 3.31–3.34); via_tren over rails ≥ 4.95 (4.34); -4708 ≥ 4.15 under both; -4821 ≥ 4.95 (4.43); centro_1 b12 over -4340 ≥ 4.15 (2.44). (b) of the 53 short, unclassified = 0 and `trench`-class short = 0. (c) fu:6:1786 class `crossing`, Z = published zero ± 0.02, `crossing_seat_clamped` 0; report lift and `dz`. (d) no lifted-group member floats > 0.5 m except named `prior_float` (centro_1 b18/b20/b22/b23); centro_1 b21, centro_2 b18 ≤ 0.5. (e) solve optimal, 0 hard rows violated; per-trench depth, ramp lengths, grades (road ≤ 10 %, rail ≤ 3.5 %). (f) airside movers per §B.10; object movers outside group 0 > 0.1 m.
KDFW (+32-098): Skylink `168` over International Parkway ≥ 4.95 every station (was 1.22–3.60) or `depth_cap` with number; walkway `133` over 14 service roads ≥ 4.15 or `airside_held`; `161`/`162` ≥ 4.15; jetway kits over apron roads: 0 lowered.
Certified: KEGE, BIKF 0 trenches, graded surface identical; OMDB, LGAV one table per planned trench (way, structure, depth, ground class, distance to airside, G1/G3 verdict); airside movers ≤ 0.05; object movers > 0.1 m = 0.
Twins: `test_soffit_road.py` (road 1.7 m short → 34 m ramps; rail → 136 m; terminus level; near airside refused; level seed refused; depth > 4 refused; R6 unchanged); `test_soffit_floor.py` (witness +0.3 → floor +0.3; stage-1/rigid vertices untied); updated `test_crossing_seat.py`, `test_crossing_lift.py`; registry gates (stage_code closures, hard_rulings, no-airport-specific, ratchets dupes --near/unused/layers, CI twins windows_text_io, patch_env_classification, tile_failures, console).

## C. Owner decisions (pending)
- O1: lift capped so no member on airside-held/pavement ground floats > 0.5 m (KMCO lift may land under +0.835; roads go deeper). Rec: yes.
- O2: OMDB/LGAV (certified) get the general rule (predicted 15 roads ≤ 1.71 m, 10 ≤ 0.59 m) unless G3 holds them; integration replays both and bundles one sim re-read each. Rec: apply.
- O3: members already floating > 0.5 m (centro_1 b18/b20/b22/b23) listed, separate issue; don't zero the lift. Rec: yes.
- O4: a rail's graded corridor = the open trench floor at rail grades; a terminus rail stays level at the lowered floor under the station. Rec: accept.
- O5: soffit < 2.1 m over frame zero is not a passage (listed); trenches > 4.0 m refused and listed. Rec: yes.
- O6: KDFW International Parkway trench up to ~3.9 m on ~76 m ramps a side; report the number before integration. Rec: proceed.

## D. Not verified
Captures for KMCO/KDFW/OMDB/LGAV not listed; structure-pass carve inside `building`/`parking_lot` cells not run; `solve/design_stage.stage_split` not read (R4 is the main risk; fallback named); whether KMCO pads building31/34/40/44 are held/airside-led unknown; OMDB obj4228/6677/4226/6675 and LGAV obj470 roads vs airside bands unknown; whether patch-side `objects` carry KDFW MSL rows unknown. All numbers are lskyclear's own.
