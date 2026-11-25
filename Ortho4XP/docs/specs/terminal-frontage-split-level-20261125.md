# Terminal frontages are split-level by default — spec for RULINGS 2026-11-25g

Fable scout `lfrontage`, 2026-11-25, design only. Base: `claude/wonderful-neumann-e0d113` 5635077b2.
Issues: #2279 (PHLI), #2288 and #2287 (LDSP), #2197 (ELLX, LDSP), #2062 (LPHR).
Law read: RULINGS 2026-11-25g, 25f, 25e, 25c, 25b (5), 2026-11-20r, 2026-11-13v/13w/13x, 2026-10-19ai, owner answer 47 (2026-10-20), 2026-09-12r (§28), 2026-09-13aj (§37 (6)), 2026-10-09j, 2026-08-30l.
Specs read: `low-level-pad-spec.md` (§5 the upper level), `2062-storey-shell-spec.md`, `unit-platform-spec.md`, lane specs `2279-kerb-frontage-spec.md` (branch `claude/lphli2`) and `2197-partial-shell-patch-rim-spec.md` (worktree `lpartshell2`, uncommitted).

Owner questions Q1-Q4 (§6) are open; answers are recorded in RULINGS when given.

## 0. Verified / not verified

Verified by reading code, sidecars and branches:

- **Today's default is one level.** §28 (`constraints/pad_frontage_gs.py:470` `groundside_frontage_level`) ties every groundside face that fronts a pad to the pad's edge level, which is the airside level. A pair is released only where its DEM step exceeds `[design] frontage_step_max_m` = 2.4 m (`law/emit.toml:845`, `pad_frontage_gs.py:108`). A released pair gets no level and no flat frontage.
- **A second level exists only on a positive witness, read in eight separate places** (§1.1 table). Each has its own gate and its own geometry.
- **Recognised population today.** Across 1,177 airports with a built sidecar in `/Users/noah/XPTerrainBuilderData/Patches`, 426 have a pad ≥ 5,000 m² (`[placement] cluster_pad_min_m2`). Of all 1,177, 28 carry any pad level `<pad>/p<k>`, 2 a `storey_shells` record (KLAX, LPHR) and 1 an `upper_pads` record (LPPI). That is roughly 7 % of terminal-sized pads read as two-level, against the owner's "more common than not".
- **PHLI** (lphli2's own spec §4, replay of `frames/lphli/PHLI.pkl`): terminal pads at 47.14 m; upper storey rise +4.1 m; kerb at 51.22 m and forecourt lot at 51.21 m after lphli2 step 2 (control 46.81, lphli step 1 47.44–47.6); ground there 49.5–50.0 m; 203 kerb vertices, median miss 0.02 m; misses > 1 m at the plan's two ends; 0 airside vertices move > 0.01 m when the generator is dropped.
- **LDSP** (sidecar and rebake plan of 2026-11-22, engine 1.50.1902): `storey_shells`, `upper_pads` and `landings` are all empty. The terminal is one origin set, `unit:5`, with 44 members. Its pack unit `unit:5#4` (21 members) stands on pad `building1`: 31,816.5 m², level 18.77 m, `datum_pred` 15.093, `block_verdict` "residual". Member feet stand on two planes: y ≈ +3.0 (`PTerminal-5`, `PMain_1`, `PStairs*`, `PZellt001`, `PGarage`, …) and y −2.74 to −2.89 (`LDSP_NewTerminal_4/5/6`); the authored storey is 5.7–5.9 m. The drawn patch has the apron at 17.69–21.17 m and the frontage roads 97–158 m south-east of the terminal at 11.82–13.67 m (`big_roads:-2970*`, `-3032`, `-3034`). 24 road faces touching the pad climb from 10.6–14.8 m to 18.77 m (`small_roads:-504#1` 10.60..18.24, `-505#1` 14.51..18.77, `big_roads:-3033` 12.51..18.77). `lifted_caps` has 30 rows naming `pad:building1`, with caps 0.2599 and 0.2688 (26–27 %); `hard_conflict` has 133 rows. Reading: the groundside roads are pulled a storey up to the airside pad — the 25g defect.
- **ELLX** (sidecar 2026-11-19): terminal pad `building42` is 113,317 m² at 375.94 m, with upper level `building42/p1` at y +4.8 (380.735 m, 3,256.5 m²); `building52/p1` and `building53/p1` are also +4.8; cluster `unit:138#0` reads floor −5.821; `hard_conflict` 1,285; `lifted_caps` 153 rows, max 2.747.
- **LPHR** (sidecar 2026-11-15): storey pad `building4` at 29.371 m, `building4/p1` at y +6.0 = 35.371 m (377.5 m²), one `storey_shells` record.
- **Direction of the step.** Three of the four cases have landside a storey up (PHLI +4.1, ELLX +4.8, LPHR +6.0). LDSP has landside a storey down (−5.7 to −5.9). KATL (`building32/p2` y −15.0) and KMCI are the existing "down" precedents.

Not verified (needs the named entry):

- **Why LDSP minted no lower level.** No LDSP capture is registered. Run `tools/v2_solve_replay.py --capture LDSP` and read `plan_low`'s `refused` list (`planar/low_level.py:296`). Candidates: the `unit_base` STEPPED gate, the ground-drop gate (`g_hi − g_lo < 3.0`), or `unit_floor` reading the wrong plane on a 44-member origin set.
- **Which LDSP plane the pad's 18.77 m is.** That it is y +3.0 (the airside floor) is inferred, not measured.
- **PHLI numbers** are lphli2's, quoted from its spec, not replayed here.
- **ELLX partial-shell measurements.** `lpartshell2`'s spec §4 is still "FILLED IN BELOW".
- **LPHR on current code.** The lshoulder capture (2026-10-20) predates the storey pad; later captures are MISSING in `docs/frames.jsonl`.
- Sidecar population counts come from sidecars built 10-10 to 11-25 on different engine versions (order of magnitude). Line numbers are at 5635077b2.

## 1. The recognition model

### 1.1 What exists (one row per reader; none is deleted by this spec)

| # | Reader (derivation site) | Witness | Direction | Fires at |
|---|---|---|---|---|
| R1 | `airport/unit_storey.upper_storeys` (`:142`) | unit parts ≥ `low_level_min_step_m` (3.0 m) over the airside floor `t` | landside up | LPHR, PHLI, ELLX |
| R2 | `airport/unit_storey.upper_pads` (`:267`) | a pad wholly under the upper storey | up | LPPI, KMCI tower |
| R3 | `planar/low_level.plan_low` (`:296`) | held block, unit base STEPPED, parts ≤ `t − 3.0`, ground drop ≥ 3.0 | down | KATL F, KMCI |
| R4 | `planar/group_low.plan_group_low` | a held pad the group stands a storey above | down | LFPG T2 |
| R5 | `planar/level_regions.level_seeds` | walls below the unit zero with roads through | down | KIAH station |
| R6 | `airport/airside_floor.floor_lifts` | frame feet on apt.dat airside against the others | re-zero | KATL F |
| R7 | `airport/split_level.read_split_levels` (`:738`) | one frame's wall feet per side | both | KLAX T2/T8, SBSP, LFSB, LPHR |
| R8 | `classify/floor_yard`, `classify/fence_yard` | unit fences on a floor | terrace edge | KMCI |
| R9 | `airport/split_level_forecourt.upper_forecourt` | OSM car park at upper-footed walls | up | KLAX |
| R10 | `classify/frontage_road.mint_frontage_roads` (`:138`) | mapped road within 15 m of a pad | same level | KASE |
| R11 | `airport/wall_corridors` (Law C), `airport/road_ramp.deck_refs` (`:132`) | kerb-wall corridors, decks over roads | kerb decks | OTHH, LEMD, HECA, KCLT |
| R12 | lane lphli2 `constraints/kerb_frontage` (not merged) | R1's storey plan and rise | up | PHLI |
| R13 | lane lpartshell `airport/ground_rim` (not merged) | origin-set ground sheet and rim | skirt | ELLX, LDSP |

The gap: no object says "this unit's airside floor is A, its groundside floor is G, its landside face is F". Each consumer re-derives a piece, and the default consumer (§28) assumes G = A.

### 1.2 The one record: `UnitLevels` (new, in `airport/unit_storey.py`)

`airport/unit_storey.py` is the derivation site: it already owns the unit's airside floor (`unit_floor`, `:128`) and upper storey, and it sits in `airport`, below `classify`, `planar` and `constraints`.

New public function `unit_levels(airport, law, air) -> list[UnitLevels]`, one record per pack unit that stands at airside pavement and whose plan is ≥ `cluster_pad_min_m2` (the "commercial terminal" test: no name, no ICAO). A smaller unit keeps today's readers unchanged.

| Field | Meaning | Derived from |
|---|---|---|
| `unit` | index in `airport.partition` | — |
| `air_y` | the airside floor, authored (today's `t`) | `unit_floor` (unchanged) |
| `land_y` | the groundside floor, authored; `None` means one level | the ladder in §1.3 |
| `rise` | `land_y − air_y`; signed; 0.0 when `land_y` is `None` | — |
| `face` | the landside face: polyline(s) of the unit's solid plan outline that do not face airside pavement | §1.4 |
| `witness` | which rung of the ladder gave `land_y` | §1.3 |
| `ground` | `(g_air, g_land)`: DEM medians along the airside contact and `_GROUND_OUT_M` outside `face` | `unit_storey.dem_samples` (`:88`) |
| `verdict` | `held`, `single`, `unconfirmed` or `far` | §1.5 |

Frame levels follow from the pad datum as today: A = D (the held block's datum, stage 1), G = D + `rise` — the `landing_rows` form `z = D + y` (`constraints/platform.py:599`). No new level arithmetic.

### 1.3 The witness ladder for `land_y`

First rung that holds wins. Each rung is an existing reader, called, not copied.

- **L1, storey parts** (R1 and R3 merged). The unit's grounded solid parts whose footprint does NOT meet the airside-near band are binned into foot planes with `geom/foot_planes.floor_plane`. The densest plane at least `low_level_min_step_m` off `air_y`, on either side, is `land_y`. This removes R3's `unit_base` STEPPED pre-gate from recognition only; the pad cut keeps its own gates. Elevated parts (canopies, roofs, parapets) never set a plane, as in `unit_floor`. Line/scatter-flagged parts are excluded (`_solid`, `:137`); LDSP's vehicle atlases (`PAtlasVehicles*`, `PVehiclesA1`) must not vote — confirm they carry the flag, or exclude parts with no walled component (`[placement] chain_min_height_m`).
- **L2, wall feet of one frame** (R7). `SplitLevel.y_lo` / `y_up` with `air_level` give `air_y` and `land_y` when the unit is one split-level frame.
- **L3, kerb deck.** The unit carries an elevated deck (a `landing` record with a `deck`, or a `deck_refs` member) along its landside face with a road under it: the road level under the deck is the arrivals kerb, `land_y` = the deck's pier feet plane; the deck top is an object, not ground (HECA, LEMD, KCLT, OTHH). The upper kerb road is a viaduct (existing `viaduct_road` and Law C). No change to Law C admission.
- **L4, skirt** (R13, once merged). The unit's origin set has a ground sheet (`ground_rim`); `land_y` is the median sheet top within `pad_frontage_m` outside the terminal body's landside wall (ELLX).
- **L5, linked building.** A connector member (`footprint_unit.plan_units_and_connectors`, `:598`) or a free bridge (`airport/bridge_class`) joins the unit to another unit whose floor plane stands ≥ a storey off; `land_y` is the far unit's floor in the shared frame (LDSP sky bridge, #2287).
- **L6, the ground alone.** No pack witness, but `g_land` differs from `g_air` by ≥ `low_level_min_step_m` on credible ground (the 25c "credible lidar" predicate): `land_y = air_y + (g_land − g_air)`. Witness `ground`. (Owner Q2.)
- **None.** `land_y = None`: one level; §28 and 13v apply as today.

apt.dat and OSM give no level; they give geometry only (§1.4).

### 1.4 The frontage line `face`

`face` is the part of the unit's solid plan outline (union of `part_footprint`s, `:114`) with all three of: (1) no airside pavement within `pad_frontage_m` (3.0 m); (2) groundside pavement or a mapped road ribbon within `[road_contact] contact_reach_m` (15 m) (13v's reach); (3) length ≥ `[edge_lines] min_run_m` after simplification. An OSM `aeroway=terminal` or `building` polygon over the unit is a tie-break only where the pack outline is ragged (snap within 3 m). An OSM `highway` with `bridge=yes` or `layer` ≥ 1 along `face` is L3's upper kerb road, not the ground frontage.

The **frontage band**: every groundside value-face vertex (`constraints/groundside.groundside_face_roles`, `:23`) within `pad_frontage_m` of `face`, plus the 13v kerbside faces minted along it. The band ends where `face` ends.

### 1.5 The verdict (ground confirms; 25f bounds)

Let `Δpack = rise`, `Δdem = g_land − g_air`.

- `single`: `land_y` is `None`.
- `held`: same sign and `|Δdem| ≥ ½ |Δpack|` (`storey_edge.ground_confirms`, `:124`, lphli's half-rise rule). Replaces `plan_low`'s full-step ground gate for recognition (KATL 11.7 m vs 13 m passes either way; EDDF T1 0.1 m vs ≥ 6 m still refuses).
- `unconfirmed`: ground does not show half the rise. Published, consumed by nothing (doubt refuses, 13r). §28 as today.
- `far` (25f): `|G − g_land| > low_level_min_step_m`. Our ground does not go to it; the frontage takes the L6 ground level, the pack stays as authored, and §3.5's connector rule applies. First check the best elevation source (25f (1)). (Owner Q1.)

## 2. Consumer census (RULINGS 2026-08-30l)

Region: the frontage band of a `held` unit, and levels A and G. Ruled before any consumer is edited.

| # | Consumer | file:line | Reads today | Ruling |
|---|---|---|---|---|
| C1 | `unit_storey.unit_floor`, `upper_storeys`, `upper_pads` | `airport/unit_storey.py:128, 142, 267` | parts | DERIVATION SITE. `unit_levels` beside them; `upper_storeys` becomes a view (rise > 0). |
| C2 | `storey_edge.storey_band`, `storey_height`, `ground_confirms`, `knife_storeys`, `arm_storeys` | `classify/storey_edge.py:86, 106, 124, 142, 192` | R1 | Read `UnitLevels`. Band and knife for rise > 0 only (unchanged). For rise < 0 nothing fires here; measure at LDSP before editing. |
| C3 | §27 `airside_edge_flip`, `_keep_across`, lphli `_landside_of_storey` | `classify/airside_edge.py:352-367` | storey band | Unchanged logic; band from C2. |
| C4 | `roles.classify` storey block, `_cut_back_groundside` | `classify/roles.py:906-920, 1376` | `STOREY_Y_KEY` | Unchanged. |
| C5 | `frontage_road.mint_frontage_roads` (13v) | `classify/roles.py:995`, `classify/frontage_road.py:138` | pad edge | EDIT. Along a `held` unit's `face`, minted as today with evidence `frontage_unit`, `frontage_rise`; level from C12. |
| C6 | `overlay._storey_lots` → `low_level._upper_split` | `planar/overlay.py:266-268, 529`; `planar/low_level.py:865` | `STOREY_Y_KEY` | Unchanged for rise > 0. |
| C7 | `low_level.plan_low`, `low_level_split` | `planar/low_level.py:296, 588` | own parts read | EDIT. Pre-gates (`unit_base` STEPPED, ground drop ≥ 3.0) replaced by `verdict == held` with rise < 0. Cut (`level_cut`, `:382`) and refusals stand. The LDSP change. |
| C8 | `group_low`, `group_up`, `level_regions` | `planar/group_low.py:117`, `group_up.py:74`, `level_regions.py:117` | own witnesses | Unchanged; never contradict a `held` record of the same unit (twin). |
| C9 | `split_level` → `storey_pad`, `storey_floor`, `split_level_pit`, `split_level_forecourt` | `planar/build.py:230, 375`; `planar/basins.py:929`; `planar/split_level_pit.py:344` | R7 | Unchanged; R7 feeds L2. |
| C10 | `platform.landing_rows` | `constraints/platform.py:599` | landings | Unchanged (`z = D + y`). |
| C11 | `riser.riser_exempt`, `upper_arm_sets` | `constraints/riser.py:92, 126`; `constraints/assembly.py:58` | landings | Unchanged. |
| C12 | lphli2 `kerb_frontage_rows`, `kerb_wall_exempt`, `planar/kerb_frontage.publish_kerbs` | branch `claude/lphli2` | storey plan and rise | BECOMES THE FRONTAGE LAW (§3.1): both signs, from `UnitLevels`, band from §1.4. No second generator. |
| C13 | §28 `groundside_frontage`, `groundside_frontage_level`, `held_terrace_pairs` | `constraints/pad_frontage_gs.py:331, 470, 448` | pad edge level; DEM step > 2.4 m releases | EDIT. A pair whose pad is a `held` unit's block and whose face lies in the band is not a §28 pair (C12 owns it); it joins `held_terrace_pairs` so `pavement_cap` does not weld it back (`constraints/pavement_cap.py:109`). |
| C14 | `groundside.groundside_ramps` | `constraints/groundside.py:42` | apron/groundside pairs | Rows across `face` withdrawn by C12's wall exempt. |
| C15 | `ceiling.pavement_ceiling`, `pavement_cap.pavement_road_cap` | `constraints/` | difference rows | As C14. |
| C16 | §37 road ramp: `reach_contacts`, `road_ramp_targets`, `between_levels`, `road_terrace` | `airport/road_ramp.py:239, 890, 1348, 1433` | airside contact level | EDIT (§3.2): a contact with a band is at G. |
| C17 | `road_ramp_rows`, `wall_release`, `terrace_profile`, `pad_weld_release` | `constraints/road_ramp.py:130, 325, 757, 688` | `road_ramp_z` | Read the new targets; band vertex rows withdrawn. |
| C18 | `pad_ramp.pad_ramp_rewrite`, `pad_road_reach` | `constraints/pad_ramp.py:222` | nearest pad rim | EDIT: a pad road ending on a band ramps from the band's level. |
| C19 | `public_road_release` | `constraints/public_road_release.py:92, 166` | `public_road_lifted` | Unchanged; a band vertex is never released. |
| C20 | `road_cross_section` rows | `constraints/` | ring pairs | Unchanged: 2 % lateral holds on the band (25c). |
| C21 | llot `lot_ground`, `lot_neck` (25e) | `model/lot_ground.py`, `constraints/lot_neck.py` | lot DEM | Band vertices are constants for the lot; the rest follows ground within 5 % (§3.3). |
| C22 | `car_lot_follow_rows` | `constraints/car_lot_follow.py:78` | standing ring | Unchanged: the band is a standing ring at G. |
| C23 | lpartshell2 `rim_pins` | `constraints/rim_pins.py` | rim stations | Rim pin wins under a sheet (L4 made G from the same sheet; twin: agree within 0.1 m). |
| C24 | `fence_yard`, `floor_yard` | `classify/fence_yard.py:118`, `classify/floor_yard.py:111` | `UPPER_Y_KEY` | Unchanged. |
| C25 | Law C, `deck_refs`, `edge_deck` | `airport/wall_corridors.py`, `airport/road_ramp.py:132`, `constraints/edge_deck.py:90` | decks | Unchanged; L3 reads them. |
| C26 | Object stage: `storey_seat.seat_records`, `footprint_unit.plan_unit_datums`, `airside_floor` | `pipeline/rebake_inputs.py:666`; `airport/footprint_unit.py:866`; `airport/obj8.py:1487` | unit zero | Unchanged: the unit seats on airside (20r). Twin: no seat moves at identity airports. |
| C27 | Publication | `pipeline/publication.py:793`; lphli2 `pipeline/kerb_publication.py` | — | NEW sidecar key `terminal_frontages`; the wall along `face` on `terrace_joints` as `wall_terrace`. |
| C28 | Census and drawn gate | `tools/check_grade.py`; `tools/drawn_check.py` | declared joints | `LAW_FAMILIES` entry `frontage_level` (band vertex off G > 0.05 m); drawn check reads `terminal_frontages`. |
| C29 | Code keys | `pipeline/stage_code.py`, `O4_Step_Code.py`, `auto_patch/provenance_code.py` | — | Key any new module. |
| C30 | Emit / heightfield | — | solved z | Emittable: ordinary vertices; wall is the existing knifed stand-off (`groundside_cutback_m` 0.6 m). |
| C31 | UIs, wire protocol | — | — | None. |

## 3. The laws

### 3.1 The frontage is flat along the building, at the groundside floor (25g (2))

For a `held` unit, every frontage-band vertex `v` that is not a stage-1 vertex and not a pad vertex takes one one-way equality `z_v − z_D = rise` (`D` = the held block's datum column; lphli2's K1 with `rise` signed).

- Flat along: `rise` is constant per block; across two blocks the band steps where the blocks do.
- Near-zero lateral: beyond the band, within `contact_reach_m` (15 m) of `face`, a frontage road or kerbside vertex departs from the band no faster than the tighter of the road's and the pad's transverse caps (2 % / 1.5 %) — 13v's rule. (Owner Q3.)
- One-way: stage 2 against stage-1 constants; airside never pulled (§3.4).
- Single-level units: rise = 0 — 13v's and §28's existing row.
- The step is at the wall (25b (5)): rows spanning a band vertex and an airside-floor-side vertex are withdrawn (lphli2 K2); the wall is declared (K3).
- Ground confirms per vertex (lphli2): a band vertex is taken only where its own DEM shows half the rise.

### 3.2 Roads ramp to the frontage (25g (3), under the 25c road law)

- A road whose ribbon enters a band has a CONTACT at G; `road_ramp_targets` treats it as an airside contact (`max(floor, z_contact − grade·s)` or the cut mirror, at `[road_contact] ramp_grade` 5 %).
- Caps: lateral 2 % everywhere (25c). Longitudinal: the class cap (`[road_profile.class_caps]`), yielding per 2026-09-18o; public classes follow terrain to `road_terrain_max_grade` 20 % with K = 3 m/% (2026-11-18e).
- The frontage never yields to a road: a road that cannot reach G within its cap over its run is released at the far end, never at the band (`pad_shift_max_m` precedent, shift 0).
- A road between A and G is `between_levels` (`airport/road_ramp.py:1348`); with no length (pavements touching) the step is a wall (25b (5)).
- An elevated kerb road (L3) gets no rows here.

### 3.3 Groundside is terraced; lots follow their ground (25g (4), 25e)

- Outside the band a lot follows its DEM within its 5 % cap (25e); band vertices are its constants; disagreement beyond the cap is carried by the cap row.
- The frontage terrace is the one exception to 25e's ground-follow.
- Two bands at different G never share a vertex; the stand-off is a declared terrace (bank over unpaved land, wall where pavements touch, 25b (5)).
- A lot between the band and a lower road grades ≤ 5 %; residual is a declared terrace at the lot's far edge (`car_lot_terraces`), never at the kerb.

### 3.4 Airside is never pulled

- Every frontage row head is in `[design] one_way_rulings` and `pad_flat_rulings`; its vertices are foreign to stage 1.
- The unit seats on airside (20r, 16u); G never feeds back into D.
- Acceptance every step: dropping the frontage generator moves 0 airside vertices by > 0.01 m.
- Classification changes that move stage-1 population are reported as rule changes (integration crossing census).

### 3.5 Far-off pack ground is left as authored (25f)

- Verdict `far`: the band takes the L6 ground level; the pack's terrace floats where it must.
- A connector between the two levels (LDSP walkway, #2287 sky bridge) has two end levels and is skewed where its class allows (free-bridge class B seat, `airport/free_bridge_seat.py`; HECA rails in `footprint_unit`), else left as authored. The skew is #2287's own lane; this spec gives it the two levels.

## 4. Population plan

### 4.1 Captures expected to change

| Airport | Capture | Expected |
|---|---|---|
| PHLI | `frames/lphli/PHLI.pkl` | rise +4.1; band at 51.2 |
| ELLX | `frames/lellx3/ELLX.pkl` | `building42` rise +4.8 (already `/p1`); band rows new |
| LPHR | none live — re-capture | rise +6.0; band = today's `/p1` |
| LDSP | none — capture | rise ≈ −5.8; lower level new |
| KATL, KMCI | latest registered | rise −13/−15; C7's gate change must not move them |
| KLAX, SBSP, LFSB | latest registered | L2; band rows new along upper forecourts |
| LFPG, KIAH, EDDF, LEMD, HECA, KCLT, OTHH | latest registered | `single`/`unconfirmed`/L3 with no ground change — the risk population |

### 4.2 The census (step 1 delivers it; no solve)

New tool `tools/unit_levels_census.py` (+ `tools/INDEX.md` row): per latest live capture, unpickle, call `unit_levels`, print per unit plan m², `air_y`, `land_y`, rise, rung, `g_air`, `g_land`, verdict, face length, band vertex count. Light; one capture at a time under the lane memory gate. Report before any consumer edit: (1) `held` counts by sign and rung; (2) every unit whose verdict differs from today's readers, by airport; (3) the seven identity airports' rows (all `single`, `unconfirmed`, or `held` equal to today's minted level).

## 5. Implementation plan (three lane steps, Opus, synthetic-first, stop at replay evidence per 17r)

Prerequisite: lphli2, lpartshell2 and llot land or are rebased onto.

### Step 1 — the record and its census (medium; no behaviour change)

`UnitLevels`, `unit_levels` (L1, L2, L6; verdicts) in `airport/unit_storey.py`; `upper_storeys` reads it; sidecar key `terminal_frontages`; `tools/unit_levels_census.py`; captures LDSP and LPHR registered. Acceptance: PHLI one `held`, rise 4.1 ± 0.1, L1; LDSP terminal rise −5.6..−6.0 with `g_air`, `g_land`, and `plan_low`'s refusal named; ELLX `building42` `held` 4.8 ± 0.1; LPHR 6.0 ± 0.1; identity replay emit byte-identical at HECA, KATL, KBUF, KEGE, BIKF, OMDB, LGAV (sidecar gains one key; patch body hash unchanged); §4.2's three reports.

### Step 2 — the frontage law, both signs (high)

Generalise `constraints/kerb_frontage` to `UnitLevels` (C12); C5, C13, C14, C15, C17, C19, C27, C28; C7 verdict gate; L3, L4 (if lpartshell2 merged), L5. Acceptance (replay): PHLI band 203 ± 20 at datum + 4.1, median miss ≤ 0.05 m, forecourt 51.2 ± 0.3, generator-drop arm moves 0 airside > 0.01 m; LDSP lower level at D − 5.8 ± 0.2, `lifted_caps` rows naming `pad:building1` with cap > 0.20 from 30 to 0, `hard_conflict` falls from 133, apron moves ≤ 0.01 m; ELLX `building42/p1` 380.74 ± 0.05, band miss ≤ 0.05 m, `hard_conflict` ≤ 1,285; LPHR `building4/p1` 35.37 ± 0.05; identity byte-identical at HECA, KBUF, KEGE, BIKF, OMDB, LGAV; KATL `building32/p2` at −15.0 / 286.285 ± 0.01 with movers > 0.1 m listed.

### Step 3 — roads ramp to the band; lots terrace; the 25f bound (high)

C16, C18, C21, C22, C23; `far`'s L6 level; `frontage_level` census family. Acceptance (replay): PHLI access road reaches the band with no step > `neck_step_m` (0.2 m), grades within class cap, cross-slope ≤ 2 %, plan-end residuals (`small_roads:-544`/`-568`, NE pocket) ≤ 0.5 m or declared; LDSP road faces touching the band ≤ class cap (no 26–27 % rows), `-504#1`, `-505#1`, `-3033` no longer reach 18.77, terrace reported `far`, no ground vertex rises to it; ELLX `lifted_caps` max 2.747 → ≤ 0.30 on roads at `building42`'s band; identity byte-identical. Integration then builds PHLI, LDSP, ELLX once each with the drawn gate at 21.97850,−159.34935; 43.5366,16.2990; 49.6345,6.2144, and censuses every crossing.

Build-time impact: one pass over units ≥ 5,000 m² with ≤ 400 DEM samples each; one KD-tree query per held unit; expected < 1 % of the 60 s airport budget (not measured).

## 6. Owner questions (each changes behaviour)

- **Q1. How far is "far" (25f)?** One storey (3.0 m): a pack groundside floor more than 3 m off credible ground is left floating and the frontage takes the ground's level (PHLI 1.7 m off is held; LDSP 6–23 m is left). Or should our ground always go to the pack's kerb when a road can still reach it within its grade cap?
- **Q2. No pack witness, but the ground shows a storey (L6).** Flatten the frontage at the ground's median along the building, or leave it following the ground as today? (Largest population change.)
- **Q3. How deep is the flat stretch?** 3 m dead level, then 2 % / 1.5 % cross-fall to 15 m (the KASE rule), then lots follow ground at ≤ 5 %. Is 15 m right?
- **Q4. Two kerbs on the ground** (departures ramp on fill, arrivals at grade, no deck object): one groundside level per block (the one the pack's landside feet stand on), other road a ramp — or two flat stretches?
