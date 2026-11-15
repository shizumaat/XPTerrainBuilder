# #2062 / RULINGS 2026-11-13w — split-level buildings join the terrain-shaped family (Fable spec, 2026-11-13)

Design only. Base main 22d554dd7 (`claude/beta8-batch16` has no `src` diff here; `claude/lisland3` adds only the #2053 hold).

## 0. Verified / not verified

Verified by read-only replay (`tools/v2_solve_replay.py --replay-cache LPHR --solved-out` at 22d554dd7):
- The "unidentified winning row" is a WITHDRAWN row: `constraints/structures.basins` makes the tie `floor = mean(open rim) − 6.00` (64 terms, `_split_floor_rows`, `structures.py:983`); `constraints/road_ramp.wall_release` (`road_ramp.py:314`, RULINGS 10-03c "the wall is the step") withdraws it because its vertices straddle the one declared pack wall (`walls 1, released 1`).
- With the tie gone nothing names the floor level: the 45 floor vertices tie only to each other (`--why-at` v696: "no terminal reached — the objective holds it"); floor 35.42, bare open-rim v1065–1067 at floor + 6 = 41.42.
- The tie would have been wrong anyway: `_open_rim` has 63 shared vertices — ~25 on the apron (28.0–28.9), ~38 on lot/road (28.75–32.6); mean 29.54 → floor ≈ 23.5, ~5 m under the apron. `split_level._open_edges` (`airport/split_level.py:191`) reads every set-back facade edge as open, apron-facing ones included.
- The 62 "flat on airside" rows (`structures.py:1008-1017`) tie apron and lot vertices to one level, violated by up to 4.45 m, pulling the lot to 28.75–31.4 along the building.
- Pit-off arm (`read_split_levels`/`read_deck_roofs` stubbed empty): held pad `building4` flat at 28.624, all 25 apron vertices on its edge at 28.624; `building4/p1` (`upper_level`, y 6.0, 302.8 m²) at 34.62–34.64, riser 28.62→34.62; lot `pav2` along the landside edge (x 4…82) 34.28–34.72, rising to 35.3–35.9 behind. The pad is only 1,662 m² of the 3,740 m² pit rim; the rest of the plan lies over apron `dsf:objpav0` (913 m²), lot `pav2` (656 m²) and roads; there the lot ends at 29.4 (W) / 34.05 (E).
- So the pit REGRESSED the 10-20l upper level at LPHR, and it re-implements the level pad (`planar/low_level`): rim = frontage weld, floor = `<block>/p<k>`, wall band = `#strip`, `SPLIT_PLATE` = the 19y block anchor.
- Objects (installed pack): frame a7a7 (unit:8, obj6–12) lower floor y 0.0, upper parts 6.0–6.6. Frame 2b0e (unit:9): `tps_06` y −0.01…18.9, `people1` 6.18…12.83, `extra_00` 11.0…13.68; anchors 12 m apart; only a7a7 is in the pit's `member_ids`.

Not verified: the lane's drawn figures (zero 35.41, bottom 28.44, walls −6.97; people +11–12 m; `tps_06__b5` +2.65…5.0); that a7a7 and 2b0e are joined by 23e today; any KLAX/SBSP/LFPG/LFSB number (needs the lane's replay); `placement_plan` treatment of excluded rows beyond `terrain_shaped.row_seats`; the sidewalk objects; LPHR captures are only from 10-20 (`.harness/frames/llphr/`).

## 1. Contract

Family: geometry reader → one rigid frame → zero where no visible edge floats, airside king → terrain made to the object's lower surface → rows `OBJECT_MSL` at zero + own lift. A split-level adds one reader and one terrain expression. Inside an airport the patch draws the ground, so "the cut" is the owner's 23b model: one rigid pad per foot level.

**Read** (`airport/split_level.read_split_levels` stays the one recogniser; `deck_roof` its sub-reader; verdict unchanged). Record gains:
- `runs`: plan outline cut at its vertices, each run carrying the foot y of the wall faces facing out of it (`_side_feet` per run instead of per box side), or None.
- `levels`: run feet clustered at `BAND_M`, sorted.
- `level_plans`: level k = plan of every solid face under `levels[k+1] − BAND_M` (walls as lines buffered by the grid), closed by `split_level_probe_m`, less lower levels; top level takes the remainder.
- `air_level`: the level holding most run length whose stations `_GROUND_OUT_M` out lie on airside pavement, else None.
- Frame coordinates = authored y + the row's own AGL lift.

**Zero.** Block = `level_plans[air_level]`; no airside contact → lowest level (13i, 23c (2)). `z0 = D_block − levels[block]`, `D_block` the solved datum of the block pad (19y; apron welds flat to the block, 19ak).

**Storeys → patch rows.** One held, non-conforming `building` pad covers the plan. Block face at D; every other level is `<pad>/p<k>` in `Registries.landings` with `y = levels[k] − levels[block]` (`LOW_KIND`/`UP_KIND`), hard at `z = D + y` (`constraints/platform.landing_rows`, `platform.py:599`); `<pad>/p<k>#strip` is the riser. No new row type or role. Back cut (#1909) = the lower level reaching `split_level_back_cut_m` outside groundside runs whose foot is the lower level. Lots/roads meet a level by existing welds (20l (a), 19ai).

**Bar form.** At every run drawn ground = `z0 + foot(run)`: no lower (no open side), no higher (no face buried).

**Frame.** Rigid set = every row of the frame + every row of another frame with ≥ half its solid plan inside the shell plan widened by `open_frame_seat.TOUCH_M`; all written whole at `z0 + lift`. Rows of those frames outside the test keep today's path (22o).

## 2. Consumer census (2026-08-30l)

Region: shell pad faces (`<pad>`, `<pad>/p<k>`, `#strip`) over the shell plan, replacing `basin_floor:<k>` / `basin_wall:<k>`; emittable (existing single-valued faces).

| Consumer | file | Ruling |
|---|---|---|
| `read_split_levels`, `_side_feet`, `wall_box`, `_covered_plan` | `airport/split_level.py` | KEEP, extend (R1); `_open_edges`/`open_sides` DELETE in R3 |
| `read_deck_roofs` | `airport/deck_roof.py` | KEEP; same record, block = roof level |
| `unit_storey.upper_storeys`, `storey_edge` | `airport/`, `classify/` | KEEP unchanged |
| `_split_pits` → `split_level_pits`, `_cut_region`, `_record` | `planar/basins.py:899`, `planar/split_level_pit.py` | MERGE into new `planar/storey_pad.py` (called in `planar/build.build` before `build_arrangement`; R1 airside-low class, R3 all), then DELETE |
| `_apply_pits._cut` knife | `planar/basins.py:926` | REUSE via a shared helper, never copy |
| Held verdict | `planar/platform.py` (~:300) | shell pad held, non-conforming |
| `low_level_split` (`plan_low`, `feet_levels`, `plan_group_low`, `_upper_split`/`plan_up`, `seed_levels`, `extend_levels`) | `planar/low_level.py:534`, `group_low.py`, `level_regions.py`, `low_extent.py` | KEEP byte-identical for other pads; shell pad skips them and mints through the same `level_cut`/strip/`reg.landings` grammar via new `shells=` kw; shell levels not extended |
| `level_seeds` W1, `airport_level_b` | `planar/level_regions.py:101`, `level_depth.py` | KEEP; shell unit mints no seed |
| `landing_rows`, strip rows, `riser_exempt`, pad frontage/ceiling | `constraints/platform.py`, `riser.py`, `pads.py` | unchanged |
| `group_level_rewrite` (23f) | `constraints/group_level.py` | not for shell levels |
| `basins` split branch, `_split_floor_rows`, `_open_rim` | `constraints/structures.py:915-926, 983-1028` | DELETE (R3) |
| `wall_release` | `constraints/road_ramp.py:314` | twin: shell landing rows survive it |
| `pad_relief` | `constraints/pad_relief.py:70` | keep |
| `SPLIT_PLATE` seat | `pipeline/rebake_inputs.py:99-123` | DELETE (R3); storey seat records (R2) |
| `datum_of` split branch; plate-kind guards | `airport/anchor_rule.py:613-620`, `placement_file.py:454`, `placement_body.py:201` | DELETE (R3) |
| `plan_unit_datums`, `airside_zeros`, `unchained_links`, `frame_riders`, `footprint_seats`, `auto_patch/object_frame` | `airport/…` | unchanged for other rows; shell rows excluded and seated whole |
| `/p<k>` fold | `airport/placement_read.py:133` | unchanged |
| `sunken_roads` | `airport/sunken_roads.py` | KEEP, not this family |
| `Basin.open_sides*`, `kind`; sidecar `basin_facilities` | `model/structures.py:748-757`, `pipeline/publication.py:1478` | drop split fields (R3); new sidecar key `storey_shells` from R1 |
| verify split branch | `verify/structures.py:197-224` | DELETE (R3) |
| split rows; open-edge census | `tools/drawn_check.py:44, 661-830, 979`, `tools/harness/census_open_edge.py` | read `storey_shells` |
| terrain cut stage, `.alt` | `auto_patch/terrain_cut_stage.py` | untouched |
| registries | `pipeline/stage_code.py:458, 663`, `O4_Step_Code.py:455, 799`, `auto_patch/provenance_code.py:555, 900` | rename entries |
| v1 Feature C | `auto_patch/object_terrain_features.py` | no change |
| UIs, wire protocol | — | none |

## 3. Rounds

**R1 — storey pads for a shell whose block is its lowest level (LPHR; high).**
1. `airport/split_level.py`: add §1 fields; `open_sides` untouched until R3.
2. New `planar/storey_pad.py` `storey_pads(airport, cells, polys, law, shells, taken)`: pad ref = building cell with most plan area, else minted by classify's cluster-pad helper; polygon = shell plan less runway family, structures, other pads; other cells cut by the shared knife; refusals as today.
3. `planar/build.build`: run before `build_arrangement`; those shells leave `split_level_pits`.
4. `planar/platform.py`, `low_level.low_level_split(shells=)`: held verdict, levels from `level_plans`.
5. `pipeline/publication`: publish `storey_shells`; `tools/drawn_check.py` one row per shell, per-run `drawn − (zero + foot)`.

**R2 — one frame seat (medium; same branch, shares the LPHR build).**
1. `pipeline/rebake_inputs.py` beside `airside_capped` (:350): `split_level.seat_records(shells, pm, surf)` → one record per rigid-set row, `seat = "storey shell"` (register in `terrain_shaped._WHY`), `elevation = z0 + lift`; ids into `excluded`.
2. Census over every pack in the frames corpus of each row whose seat changes (13r precedent); master reads it before landing.
3. Attribute the sidewalks with `tools/drawn_site.py`.
Close: `build_airport.py LPHR --tile 38 -29 --pack-copy` + `drawn_gate.py`.

**R3 — every shell on storey pads; delete the pit (high).** Upper-level-block shells (SBSP, KLAX, LFSB deck roof): lower level + back cut minted in `storey_pad`; keep `split_level_back_cut_m`, `split_level_road_reach_m`; delete `split_level_rim_step_m`; delete everything the census marks. Close: one SBSP build; KLAX, LFSB replay + drawn_check vs 1.0.512; LFPG, KMCI, KATL, KIAH planar replays byte-identical.

Not built: shells whose pad is refused or off the patch (named refusal in the log).

## 4. Bars

LPHR (replay then drawn): B1 lot vertices within 1 m of the upper level's outer edge within 0.5 m of `z0 + 6.00`; B2 lower-storey region within 0.3 m of `z0`; B3 apron vertices on the block edge within 0.05 m of `z0`, stage-1 movers listed (`--stage1-diff`); B4 both frames at one zero (spread 0.000), `people1`/`extra_00` ≤ 0.3 m over the shell surface under them; B5 every run `|drawn − (z0 + foot)|` ≤ 0.05 airside, ≤ 0.5 groundside, 0 runs with ground under the foot; `drawn_gate` PASS.
SBSP (−23.620923, −46.655973), R3: upper-floor runs on the apron within 0.05 m; groundside lower-foot runs within 0.5 m except within `split_level_road_reach_m` of a base road (Q1); no lower storey buried.
KLAX Terminal_8 (#1934 item 1): all four sides within 0.5 m (were −4.73/−5.26/+1.01/+4.51).
LFPG #1717: unchanged.

## 5. Tests
`test_split_level.py`: per-run feet on an L plan with a set-back facade; `level_plans` for a floorless lower storey; `air_level` both classes. New `test_storey_pad.py`: pad = plan, knife cuts apron and lot; levels/strips registered; landing rows survive `wall_release`; non-shell `low_level_split` identical. New `test_storey_seat.py`: joined frames one zero, lift added, outside rows untouched. `test_drawn_check.py` storey row. Plus `tests/test_harness.py`, `test_no_airport_specific_code.py`, registry twins, `ratchets.py dupes --near` / `unused`.

## 6. Risks
Pad cuts apron under the building (913 m² at LPHR) → airside vertex set changes (19al): report movers. Whole-row seats drop per-body handling for those rows (jetways, 19aq leavers): R2 census guards. R3 touches sites read as improved (KLAX 1.0.476): a miss → one-miss cap; R1/R2 stand without it. `level_plans` from thin shells may put a level edge a few m off (hidden inside the plan; B2 near it). Until R3 the remaining pits keep the wall-withdrawal hazard.
Separate finding: `wall_release` withdraws any multi-term `Linear` straddling a wall, structure rows included — ordinary basin floor rows near a pack wall may share this (unmeasured).

## 7. Owner question
Q1 (R3 only). A mapped road along the base of a split-level building above its lower floor (SBSP hangar row): 11-06T02:40Z says the road keeps its slope and the ground meets the wall at the road; 13w (2) says no storey face is buried. (a) road keeps its profile, wall covered up to the road, or (b) road cut to the wall foot? Spec assumes (a).

## Amendment A1 (Fable, 2026-11-13; rules on lane lshell1 bc8aaa171's deviation)

The "top level takes the remainder" rule assumed every storey has a floor (LPHR's lower storey has none: levels 0/6/10, plans 419/1,331/1,971 m², 1,767 m² of ground floor sent to level 10). Replace §1's `level_plans` rule with this order:

**(1) Which level a piece takes.** (a) Wall feet first: each run owns the strip `pad_frontage_m` deep inside it at that run's level. (b) Floors second: the plan of up-facing solid faces within `BAND_M` of a level belongs to that level. (c) Unwitnessed remainder last: a piece with no floor at any level is open downward; it takes the LOWEST level it shares ≥ `split_level_probe_m` of boundary with; if none, the level it shares the most boundary with. (Ground under an absent floor may be too low — hidden in the walls — but never too high.)

**(2) Minimum for a level.** A level counts only when its runs hold ≥ `PLANE_SHARE` of the walled outline length (the constant `low_level.feet_levels` / `airside_group_seat.floor_plane` use; lane confirms its value) and stands `low_level_min_step_m` from its neighbours. Runs of a dropped level take the level of their neighbouring run along the outline (longer neighbour wins a tie) and are published in `storey_shells` as `minor` with their true foot; `drawn_check` lists them, does not judge them.

**(3) R1 scope.** Only shells with `air_level == 0`. Shells with no airside contact or an upper-level block stay on the pit until R3.

**(4) Plumbing.** Pad polygon = plan + the rest of the building cell it takes its ref from (leftover pieces take a level by (1)(c)). Read the shells once in `planar/build.build` next to `level_seeds` (`planar/build.py:312`); pass them to `build_basins` as ids to skip (it runs twice, `:187` and `:370`) and to `storey_pad`; `BasinStats.split_levels` keeps notes only.

**Tests (`test_split_level.py`):** floorless lower storey with one wall at the upper level → interior level 0; a level under `PLANE_SHARE` dropped, runs `minor`; a remainder touching no level by `split_level_probe_m` falls back to most-shared boundary. Bars B1–B5 unchanged.

## Amendment A2 (Fable, 2026-11-13; reviews lshell1 9befd292b; LAST Opus round)

Read-only arm (A1 (b) dropped + riser exemption for shell upper levels) on the same capture: `building4/p1` at D + 6.00 (35.02–35.05, 370 m²), block `building4` 29.030 spread 0.000 (75 v), all 41 apron edge vertices 29.03, lot/road outside foot-6 runs +6.00 (road run 60 +5.81); `hard_conflict` 520 → 145 (none on landing/pad rows; the rest at three lot junctions where the lot ring steps 6 m between neighbours — removed by (3)). Block datum 29.03 vs 28.51/28.624; 57 apron vertices move > 0.05 m, worst +0.536 at frame (68.5, 149.0) (spec §6 risk; listed under B3).

Mechanism: (1) 68 hard `pavement_max_grade ceiling` rows span the riser (51 `pav2#1`, 12 `small_roads:-298`, 4 `pav2`, 1 `building4/p1#strip`; bounds 0.05–0.30 vs 6 m) + 177 soft `roads` longitudinal + 1 proximity; `constraints/riser.py:42-52` `riser_sets` reads only `kind == "low_level"`; pavement ceilings (taxi tier) outrank landing rows (pad tier) (`law/emit.toml:948-966`). (2) A1 (b) floors made level 6 sprawl over the west wing interior (N and S walls foot 0). (3) `cluster:unit:8#0/1` is the level's own plane group (`constraints/cluster_pad.py:468-496`) — wanted; only cross row is one `rim_strip` tie (`constraints/pads.py:467`). (4) 10-20l held because its level was a 3 m strip on a pad never sharing a block vertex with the lot. (5) DEM on the landside is +5.5…+6.9 (wing NW), +1.5…+3.5 (notch), +2.1 (main N wall) over 28.51 — the lot sat at +1 because it was welded to block vertices.

Rulings: lot/road meeting two storeys a few m apart → a declared vertical riser at the back cut's outer edge (`planar/foot_kerb` / `airport/riser_wall`, RULINGS 2026-11-10a (2)); the lot never shares a vertex with a block-level face on a groundside lower-foot run. Upper floor over lower ground IS a deck: A1 (1)(b) deleted. Cluster `pad_slope_max` was misattributed; no change.

Ordered changes:
(1) `airport/split_level._level_plans`: order (a) wall-foot strips, (c) remainder; where strips of two outline-adjacent runs of different levels overlap, cut both by the bisector through their common vertex; other overlaps lower first. Floors are no witness of ground (a run with no wall foot under a slab edge = R3 note).
(2) `constraints/riser.py`: `riser_sets` takes every landing whose record carries `shell` (any kind); low side = level vertices, high side = block faces + strip far edge; `riser_exempt` keeps rows whose first input starts `landing:` or `low_level:`; non-shell `upper_level` unchanged.
(3) Back cut + kerb in `planar/storey_pad.py`: T = band `split_level_back_cut_m` outside each groundside run whose level is the shell's lowest, chained as `split_level_pit._cut_region` (`planar/split_level_pit.py:224`, reuse); T yields to runway family, structures, other pads/pits, airside pavement, mapped road faces (road keeps its profile; 13x (2) is R3) — clipped, never refused; T is block level; pad = plan ∪ rest of cell ∪ T. R = band `fill_riser.riser_width` inside the pad along the pad boundary on T's outer edge (where T clipped to nothing, along the run), only where it borders a groundside value face, never within airside pavement width, never over an upper level; carve R before the level strips. Mint `kerb_ref(pad)` faces + `Registries.held[pad]["kerbs"]` records in `foot_kerb.py:96-100` shape (`ring`, `upper` = R's outer line (lot side high), `height_m` = top level − block level + `[cockpit] visual_m`) in `low_level._shell_split`; shell record carries T, R, per-run `back_cut_m`, `clipped_by`; `shell_levels` keeps levels the riser width off other pads (as `plan_up`, `low_level.py:493`).
(4) Scope (extends A1 (3)): ≥ 2 counted levels and (i) `air_level == 0` (LPHR; ELLX class) or (ii) `air_level is None` and ≥ half the lowest level's run length faces a structure floor (tunnel ramp, entrance bank, channel/basin floor) — KLAX class: block = lowest level following that floor one-way; floor rows untouched. Upper-block shells (KLAX Terminal_2/_8 main parts) stay on the pit until R3.
(5) Reader: `_covered_plan` (`split_level.py:200-219`) returns only the largest part — `_storeys` reads every part ≥ `min_area_m2` as its own record `<witness>#<k>`; the pit keeps reading part 0.
(6) KLAX K0 first: on `frames/lfence/KLAX.pkl`, `--why-at` on the lower edge: does a pad vertex shared with `tunnel_ramp`/`entrance_bank:*` follow the floor or pull it; does `storey_pad._refusal` refuse for touching a structure. If the follower needs a new row family → STOP and report.

Census additions: `riser_sets`/`riser_exempt` (`constraints/riser.py:42, 73`) EXTEND (2); `rim_strip_ties` (`constraints/pads.py:467`) unchanged + twin (lot vertex beside R ties to R's outer vertex); `riser_walls` (`airport/riser_wall.py:58`) reads shell kerbs, orientation twin; `wall_release`, `_wall_step_rows` (`constraints/road_ramp.py:314, 263`) unchanged + twin (lot↔block released, step floor inactive at `height_m`); `wall_cut_edges` (`solve/wall_cut.py`) unchanged; `wall_terrace_joints` (`pipeline/publication`) kerb is a declared joint; `lot_level` (`airport/road_ramp.py` ~2104) must keep running before riser walls; `block_strip_rows` (`constraints/platform.py:187`) no bank row on `#kerb#strip` (twin); `_split_blocks` unchanged; `extend_levels`, `region_depths`, `cut_fill_bands` (`planar/low_level.py:689-696`) must skip landings carrying `shell`.

Bars: B1–B4 unchanged (z0 = block's solved datum; stage-1 movers listed). B5 unchanged for judged runs; minor runs and stations where the back cut was clipped by a mapped road (`base_road`) or blocked ground listed, not judged. B6 (new, replay): no `hard_conflict` within 100 m of the shell on landing, pad, pavement-ceiling or cross-section rows; `airside_no_step` and `frontage_near_miss` equal the pit control (0/0); other families reported with attribution. Round pass/fail = LPHR B1–B6. Reported only: ELLX (capture + planar replay; every scope-(i) shell's levels within 0.05 m of D + y; B6 at each); KLAX sibling (replay on `lfence/KLAX.pkl`): the 402 m² part of `Terminal_8_Buildings.obj` (dsf:obj7223; owner points in cell `building32`, frame x 1131–1149) read with levels −5.5 / −0.5; lower runs (27.4 m on `tunnel_ramp`, 11.3 m on `entrance_bank:tunnel:-3485+-1274@1`) within 0.3 m of the solved floor beside them; upper runs (13.4, 9.7, 6.5 m, hill side) ground at z0 + 5.0 ± 0.5; no strip/kerb outside the plan on the hill side; Terminal_2/Terminal_8 basins byte-identical.

Tests: `test_split_level.py` (wing with foot-0 walls + floor at 6 → interior level 0; bisector at a 0/6 corner; two plan parts → two records); `test_storey_pad.py` (T chained and clipped at a road; R carved before strips; kerb record shape); riser twin (lot ring across a shell riser end → rows withdrawn, landing rows kept, non-shell upper_level identical); synthetic solve twin (lot touching foot-6 and foot-0 runs 5 m apart → level D + 6, lot +6, cut at D, no hard conflict); registry twins, `test_no_airport_specific_code`, ratchets.

Risks: (3) and KLAX steps unrun (arm proves (1)(2)); kerb orientation reversed vs `foot_kerb`; KLAX adds reader records everywhere (only scope (i)/(ii) minted); KLAX heights depend on #1934's mouth depth and the object's 5.0 m storey (owner said ~7); 5 m back cut draws a trench up to 6 m deep landside; `small_roads:-298` keeps its profile (upper ~3.5 m of run 64 stays buried, `base_road`); runs 46/47 rely on the off-patch drape; apron movers up to +0.54 m.

Owner questions: Q1 LPHR landside — 5 m trench exposing the wing/forecourt walls to their feet (13w literal), or lot against the walls (back-cut reach 0, same code)? Q2 `small_roads:-298` crossing upper→lower run: keep profile (assumed) or cut per 13x (2)? Q3 KLAX building step is 5.0 m: lower edge at ~25 m → hill side ~30 m not 32 — acceptable?

## Amendment R3b (Fable, 2026-11-15; R3 round spec for lane lshell3)

### SPEC — #1934 / #2062 R3: every shell on storey pads, one datum rule, the face's front floor, a road carried over a ramp (Fable, 2026-11-15)

Design only. Base main b47870d01. Paths relative to `Ortho4XP/src/auto_patch_v2/` unless given. Owner rulings: 13w (one code path), 13x (2) (nothing along a shell's base stands above its wall foot; SBSP base road cut to the wall foot); 2026-11-15T03:05Z "We should not have any airport specific exceptions, or alternate code paths"; 04:05Z: T8's storey step follows the object (5.0 m). Owner questions Q1/Q3/Q4/Q5 (§9) assumed at the recommendation; the master is asking.

#### Findings that changed the brief
1. The pier model for the KLAX north mouth is refuted: `Misc/Underpass_1.obj` (dsf:obj7230) has ONE opening, jamb to jamb x 1151.0–1181.0 (30.0 m), one 0.8 m centre pier (1165.6–1166.4); "piers" at 1150.9–1151.3 / 1180.9–1181.2 are the jambs' 2.5 m reveals; x 1142.0 and 1187.3 are collinear vertices inside solid full-height (y −6.6…+1.4) headwall wings 1136.6–1151.0 and 1181.0–1199.0. Today's ramp already spans the whole opening via `group_opening`.
2. The owner asked (#1934, 2026-11-13T20:36Z) for the mouth "at its full depth from" 33.940279765,−118.396457834 "to" 33.940330430,−118.395949179 = frame (1143.5,−315.1)–(1190.5,−309.5), 47.3 m, both ON the wings → expose the headwall (RULINGS 06c (5) applied to the wings: "the bottom of the ramp meets the bottom of the mouth object that faces the ramp"; no law change).
3. T8 datum from the owner's words: east-run building edge 33.940411615,−118.396398062 (frame (1149.0,−300.5)) "at the bottom of the tunnel mouth, around 25m"; west upper wall (1138.0,−296.5) "at grade more like 32m". Mouth bottom 25.54 + object storey 5.00 → hill side 30.54 (DEM 30.31 there).

#### 0. Verified / not verified
Verified (captures `frames/lfence/KLAX.pkl`, `frames/splitlvl3/SBSP.pkl`, `frames/splitlvl3/LFSB.pkl`; reader at main):
- T8 `dsf:obj7223#1`: plan x 1131.2–1149.2, y −310.1…−282.4; lowest-level runs (foot −5.5): E 27.4 m (x 1149.2), S 11.3 m (y −310.1), N 13.2 m (y −282.7); upper runs (−0.5): 13.4, 9.7, 6.5 m on the west; level plans 309 / 93 m².
- Tunnel `-3485+-1274@1`: mouth 25.54 pinned by obj7230's bottom (−6.6, zero 32.14), design grade 5 %, `top_s` 84, `climb_from_s` 0; note "#1938 S1: the pinned opening's host pad(s) building32 are cut by its footprint". East run stations s ≈ 6–33.5: a 5 % ramp stands 0.3–1.4 m over the building's foot there.
- DEM at y −310: 31.9 (x 1135), 29.65 (1145), 28.5 (1150), 29.8 (1185), 31.9 (1195).
- `Misc/Road_Bridge.obj` dsf:obj18210: all 104 solid triangles hard deck; plan x 1138.6–1200.2, y −986.0…−962.0; deck plate y −0.5…−1.0, a pier to −6.0 at x 1160–1180; DEM 32.78 / 26.54 / 32.61 (west end / mid / east end). `route14` is a `service_road` cell, bounds x 1002.6–1191.2. Tunnel `@0`: mouth 25.14, `top_s` 12.0, `clipped_by` route14. Capture: `free_bridges` = [], `decks` = [], obj18210 not in `overpasses`.
- Datum law: `model/platform.py:291-345` (column = pad's own vertex, never `structure_vertices`); `_fill_datums` `:354-372`; `landing_rows` `constraints/platform.py:599-661`.
Not verified: any solve/replay of this design; ramp top after the level stretch (DEM estimate ~150 m vs 84); obj18210's bridge class/witnesses at main; Underpass_2's faces (foot clusters suggest the same design); pit zeros in 1.0.512; whether SBSP Hangar3's upper floor (+5.96) is a floor or door lintels; KMCI/KATL/KIAH capture paths. K0 log of the previous lane: frames/lklax/KLAX_k0_2062.log (block 30.48, p1 31.30, no datum column; instrument commit 07c30e4db on origin/claude/lklax — cherry-pick it).

#### 1. Rules
**A. One datum rule for every shell** (single derivation site `planar/storey_pad._record`; new field `StoreyShell.leader`).
- `airside`: block = `air_level`; D = the stage-1 weld column (today).
- `floor`: no airside run, and ≥ half the lowest level's run length faces a ramp-class structure floor (a `Tunnel` record's ramp, front floor or bank). Block = lowest level. D = that floor's mouth datum.
- `ground`: neither. Block = lowest level. D = `datum_z` = `levels[0]` + the length-weighted median of (DEM `_GROUND_OUT_M` outside the run − run foot) over the shell's judged groundside runs (reader `split_level._ground`).
- Column: `model/platform._fill_datums` carriers gain every block whose landing record carries `shell`; same choice rule, never a structure vertex — the RAMP-carry law stands unamended (no ramp vertex is a column or enters the flat set).
- Row: new member `constraints/shell_datum.py`. `floor`: hard two-sided `z_dv − z_f = 0`, `f` a vertex of the floor's datum group (expose it from `constraints/structures.py:556-562`, never re-derive). `ground`: hard pin at `datum_z`. Ruling head "structures.building_pad storey shell datum" in `[design] hard_rulings` and `pad_level_rulings`, pad tier. A basin or channel floor facing a shell is refused by name.
**B. The floor is level along a shell that stands on it (13x (2)).** Single site `planar/structures.py:906-955`: `climb_from = max(climb_from, shell_level_s)`, `shell_level_s` = far station of the floor-scope shell's lowest-level runs facing the corridor, when their near station lies within the level zone (`climb_from` + wall reach + one spacing); otherwise that shell is refused by name. Helper in new `planar/storey_floor.py` (also takes `_floor_scope`). Shells are read before the structures (`planar/build.py:325` vs `:364`): pass `shells=`. The same site makes the shell's plan a wall of the trench: cells under it are never pin hosts or knifed (`:1527-1532`), `outer` is differenced by the plan and the floor by `plan.buffer(rim_off)` (beside the deck/shore clips `:1304-1315`). The void strip stays between plan and floor; its rim is on the pad at pad level (09-10an).
**C. The front floor (06c (5) applied to the wings).** Reader in `airport/trench_objects.py` beside `_wall_opening` (`:186`): `Portal.front_xy` = across-bore ends of the face's front wall — near-vertical solid faces crossing the bore (|plan normal · into| ≥ 0.5), full height (lowest vertex within `cover_flush_m` of the face bottom, highest within it of the face top), chained outward from each jamb; `opening_xy` unchanged. Planar: for stations within new `[tunnel.object] face_front_m = 5.0` of the mouth, the ramp's half widths are the front's, beyond it the opening's (one step in `planar/structures.py:1075-1094`, protected station at `face_front_m`). The front band is trimmed ACROSS the bore, per side, at airside pavement, the runway family, other structures and non-host pads (+ `gap`); it never shortens the ramp; at a floor-scope shell it stops by rule B. KLAX north expected: front 1136.6–1199.0 before trims; T8's south run then stands on floor.
**D. Every shell on storey pads; the pit is deleted.** `read_storey_shells` returns every record with ≥ 2 counted levels, every part ≥ `min_area_m2` (A2 (5)). `read_deck_roofs` fills the storey fields through the same helper (open/apron runs foot = roof y, tall runs their wall feet, `roof = True`; a roof-level run owns a strip one `riser_width` deep). `storey_pads`: scope gate, `pit_skip`, `FLOOR_HELD`, `pitted` go. The back cut T joins the LOWEST level's region (today `regions[block]`, `storey_pad.py:327-329`). Kerb: off every level but the lowest, height `levels[-1] − levels[0] + visual_m`, never against a road face. T no longer yields to a mapped road face (13x (2)): the road's vertices on T's edge are welds, its own caps ramp it away. Another building cell with ≥ half its area inside the plan is absorbed. A refused shell is a plain building pad with its refusal in the log; no fallback path. Before deleting, print the parity table: per shell, pit zero (control) vs storey zero.
**E. A road carried along a pack hard deck over a ramp (14f, 14m (1)).** K1 first (read-only): print obj18210's class and each witness at main. `planar/free_bridge._routes` (`:63`): W1's routes gain the airport's own ground routes (`Airport.ground_routes`, chained as `deck_carry.route_chains`); over a `flag` deck the bridge stretch is the part inside the plate; W2–W7 and W4b unchanged → the deck is a free bridge and spec 2065's seat and end grading hold the route at the deck top, flush at both end lines. `planar/structures.py:1076, 1110-1119`: a stop whose part inside the corridor lies within an object deck's footprint (`odecks`, + `gap`) is carried, not a stop; the deck is the object bridge over the ramp (`obj_ivals`, existing rows: floor ≤ deck top − `clearance_m`); the ramp runs on at design grade.

#### 2. Population (reader at main)
| Airport | Witness | Levels | Leader | Today |
|---|---|---|---|---|
| KLAX | obj5978 Terminal_2 | −4.0 / 0.0, plan 14,272 m² | airside (702.5 m) | pit, floor 32.24 |
| KLAX | obj5982 Terminal_8 | −4.0 / 0.0, plan 9,034 m² | airside (263.6 m) | pit, floor 31.56 |
| KLAX | obj7223#1 T8 Buildings | −5.5 / −0.5, plan 402 m² | floor | refused (structure) |
| SBSP | obj683 Hangar1 (owner site, cell building69) | −0.09 / 15.91, plan 2,330 m² | airside (123.2 m) | pit, floor 772.59; `small_roads:-8144#2` within 6 m of the 41.3 m base run |
| SBSP | obj659 Hangar3 | −9.04 / −4.04 / −1.04 / 5.96 | airside | pit −9.04 / +5.96, floor 776.60 |
| LFSB | obj8798 fireSt | −9 / −3 / 0, plan 6,754 m² | ground | pit −9 / −5, floor 259.66 |
| LFSB | obj8770 jet_aviation (deck roof 11,545 m²) | floor −17.42, roof +0.03 | airside | pit, floor 250.76 |

#### 3. Consumer census (08-30l)
| Consumer | file:line | Ruling |
|---|---|---|
| `split_level_pits`, `_cut_region`, `SPLIT_KIND` | `planar/split_level_pit.py` | DELETE; `back_band`, `_largest`, `_road_under`, `_roads` move to `storey_pad` |
| `_split_pits`, `skip_split`, `BasinStats.split_levels` | `planar/basins.py:238-240, 378, 410, 463, 917-933`; `planar/build.py:155, 195, 211-216, 328-332, 417` | DELETE; notes move to a storey stat |
| basins split branch, `_split_floor_rows`, `_open_rim` | `constraints/structures.py:930-938, 998-1045` | DELETE |
| `Basin.open_sides*` | `model/structures.py:796-802`; `pipeline/publication.py:1619-1620` | DELETE |
| `SPLIT_PLATE` seat | `pipeline/rebake_inputs.py:99-116, 149-150` | DELETE; `storey_seat.seat_records` (`:400-412`) seats every shell |
| plate-kind guards | `airport/anchor_rule.py:636-638`, `placement_file.py:483`, `placement_body.py:214` | DELETE |
| `PLATED_KINDS`, `plated` | `airport/free_bridge_seat.py:51`, `planar/free_bridge.py:307`, `tools/bridge_census.py:80-83` | read `storey_shells` member ids |
| verify split branch | `verify/structures.py:197-251` | DELETE |
| split rows; open-edge census | `tools/drawn_check.py:44, 738-900, 1056`; `tools/harness/census.py:2568-2575, 2689, 2835`; `census_open_edge.py` | DELETE the split branch; `tools/drawn_storey.py` is the reader |
| `split_level_rim_step_m`, `split_level_road_reach_m` | `law/structures.toml:688-689`, `law/model.py:621` | DELETE |
| registries | `pipeline/stage_code.py:727, 2314, 2498`; `O4_Step_Code.py:841`; `auto_patch/provenance_code.py:942` | drop `split_level_pit`; add the three new modules |
| `datum_vertices(fills=True)` readers | `constraints/platform.py:514, 616`; `constraints/road_ramp.py:1015` | read the new column; twin for each |
| `datum_vertices()` stage split and others | `solve/design_roles.py:83`, `solve/design_stage.py:107`, `constraints/pads.py:996`, `platform.py:125, 795-867, 1137, 1339`, `foot_road.py:46`, `ramp_runout.py:376`, `group_level.py:64`, `viaduct_floor.py:241` | unchanged |
| `structure_vertices` flat set, pad plates | `constraints/platform.py:690-717`, `constraints/pads.py:205` | unchanged |
| `riser_sets` / `riser_exempt` | `constraints/riser.py:58, 92` | unchanged; twin with an upper-block shell |
| `wall_release` | `constraints/road_ramp.py:314` | twin: the floor tie survives it |
| `climb_from_s` readers | `constraints/structures.py:560`; `planar/structure_geometry.py:384-394`; `structure_approach.ramp_top:1082`; `publication.py:1378`; `planar_report.py:160-170` | unchanged; read the longer level zone |
| `opening_xy` readers | `planar/mouth_opening.py:39, 55`; `structures.py:524-535`; `entrance_skirt.py`; `airport/portal_floor.py:74`; `tools/drawn_site.py:629-726`, `drawn_site_bars.py:213-274` | unchanged; drawn_site gains `front_m` |
| pinned hosts, pad knife | `planar/structure_mouth.py:689`, `structure_geometry.py:794` | a cell under a floor-scope shell is never a host |
| mapped-bore stops | `planar/structures.py:1076, 1110-1119` | a stop on an object deck is carried |
| W1 routes | `planar/free_bridge.py:63`, `airport/bridge_witness.py:207-324` | + ground routes |
| `overpass_deck`, `deck_bridge`, `deck_route` | `planar/` | unchanged |
| UIs, wire protocol | — | none |

#### 4. Order of work (one lane, high)
K0 (read-only, on a fresh KLAX capture and the SBSP/LFSB captures): the parity table; K1; a corpus census over every capture in `frames.py list` of mouths whose `front_xy` exceeds `opening_xy` by more than the grid, and of hard decks carrying a ground route. REPORT these three lists to the master and WAIT for the go (SendMessage) before code lands — then A → B → C (KLAX replay) → D (SBSP, LFSB replays; delete) → E (KLAX replay).

#### 5. Bars
KLAX (replay, then drawn): T8 four sides — E and S runs' drawn ground within 0.5 m of z0 − 5.5 and the floor beside them within 0.3 m of D; D within 0.05 m of 25.54; upper runs z0 − 0.5 ± 0.5 (30.54); N run back cut at D; no strip/kerb outside the plan on the hill side; no `hard_conflict` within 100 m on landing, pad, datum or ramp rows. North mouth: floor within 0.3 m of 25.54 along the front between the trims (reported; must contain x 1143.5–1190.5 unless airside trims the east end, then quoted); opening unchanged at 30.0 m. South mouth: same reading, front reported. South ramp: `clipped_by` empty; ramp tops out at the ground; under obj18210 deck top − floor ≥ 5.1 m at every station. Road_Bridge ends: route14 within 0.05 m of the deck top at the end line meeting airside and 0.3 m at the other; no ground vertex inside the deck plan above its underside. Terminal_2/Terminal_8: upper-floor runs on the apron within 0.05 m; apron movers > 0.05 m listed (`--stage1-diff`); zero within 0.3 m of the pit control or listed.
SBSP (−23.620923, −46.655973): upper-floor runs on the apron within 0.05 m; every groundside lowest-level run within 0.5 m with no base-road exception; the road at T's edge welded, its ramp-out length and worst grade reported; Hangar3 zero vs control.
LFSB: deck roof: apron within 0.05 m of the roof edge on the open side, tall sides exposed to the floor ± 0.5; fire station zero reported vs control.
`drawn_gate` PASS at each built site, no MOVED vs the control.
Replays (planar + solve, `--emit`, patch body hash vs base): LFPG, KMCI, KATL, KIAH, LPHR, ELLX byte-identical; where not, every mover > 0.1 m listed with its cause (only lawful causes: a front band or a carried route named in K0). Also certified LICJ unchanged.

#### 6. Tests
`test_storey_pad.py`: upper-block shell (T on the lowest level, kerb height, no kerb at a road, road welded); cell absorption. `test_split_level.py`: deck roof as a storey record. New `test_shell_datum.py`: column for a no-airside shell; floor tie survives `wall_release`; ground pin; synthetic solve (shell beside a pinned ramp: block = mouth datum, upper = +y, ramp level along the run). `test_trench_objects`: front wall excludes lintel, back plug, parapet band; one-pier opening unchanged. Structures twin: half-width step, lateral trim at airside, shell plan never knifed, stop on a deck carried. `test_free_bridge_read.py`: ground route as W1. Plus `test_harness`, `test_no_airport_specific_code`, `test_v1_retired`, registry twins, `ratchets.py dupes --near` / `unused` / `layers`.

#### 7. Closing builds, stop rules
Closing: `build_airport.py KLAX --tile 33 -119 --pack-copy` with `drawn_gate` sites at the owner's four points and the bridge (~33.93433, −118.39617; compute from the capture), and `build_airport.py SBSP --tile -24 -47 --pack-copy` with the owner site. LFSB: replay, emit and `drawn_storey` only. df ≥ 30 GB; ≤ 4 builds machine-wide; never raise the lane cap; delete scratch builds on report (register frames first).
Stop and report, never iterate: a K0 list that names a certified airport (KEGE, BIKF, LICJ); K1 failing any witness other than W1; the level stretch refusing ramp `@1`, or its top clipped by a pad or airside; a shell refused that is a pit today; a second miss on any bar (floor 0.01 m).

#### 8. Risks
Front bands appear at every entrance face with full-height wings (K0 names them). Ramp `@1` grows by ~66 m. LFSB fire station zero moves ~−4.3 m (estimate). A roof-level block band is coplanar with the roof plate for one riser width. Hangar3's lower levels stand 7–15 m under its block if +5.96 is a lintel (that error exists in the pit today). Terminal_2's pad covers many cells: apron movers.

#### 9. Owner questions (recommendations assumed; master is asking)
Q1 KLAX north mouth: expose the whole headwall the object models to the floor (62.4 m, trimmed at airside pavement) for 5 m in front of it — recommended (alt: only as wide as the lidar cut). Q2 (answered 04:05Z): T8 hill side at 30.54 from the object's 5.0 m storey. Q3 the ramp stays level along the building's 27.4 m wall and climbs from its north end (~66 m longer) — recommended. Q4 LFSB fire station and SBSP Hangar3 change zero leaving the pit — accept the storey reading, read in sim. Q5 a pack hard deck carrying an apt.dat service route is a bridge like one carrying a mapped road — recommended yes.

# Amendment R4 to spec 2062 (Fable one-miss review of lshell3 06f229549, 2026-11-15)

Paths relative to `Ortho4XP/src/auto_patch_v2/`; lines at 06f229549.

## Findings
- C refusal: mouth @1 (1169.2, −314.2), ramp north; opening halves W/E 17.98 / 11.70; front halves 32.47 / 29.71 (front x 1136.7–1198.9). Trim W 17.98 (T8 shell 1.8 m from the jamb), E 19.70 (floor edge x 1188.9); ring outer east edge x 1191.0 (1188.9 + rim 1.6 → snapped out to 0.5 m grid); distance to pav10 0.53 vs gap 0.60. pav10 is AIRSIDE (6,364 m² taxiway, role junction, west edge x ≈ 1191.5 for y −322…−296). Cause: `front_band.trim` (`planar/front_band.py:44-66`) stands a 3-point proxy off the stop by gap + rim_off = 2.2 m (`planar/structures.py:1086-1087`) while the built ring stands rim_off + up to one grid step out → the clip loop (`structures.py:1154-1208`) treats the band hit as a ramp-top stop, pops stations 16 → 2, `:1202-1206` refuses. What-if (stand-off + grid = 2.7 m): E half 19.20 (floor to x 1188.4, front 37.2 m); @1 builds top_s 168.0, climb_from_s 31.79, clipped_by ''; T8 floor-led block 25.54, p1 30.54, 0 hard conflicts within 30 m. West side needs no band (T8's back cut 68 m² at D = 25.54 covers x ≈ 1138–1149.2, y −315…−310.1). Owner's east point x 1190.5 unreachable: needs pavement edge 1191.5 − (1.6 + 0.6 + 0.5) = 1188.4 → 2.1 m short (quote). Second defect: `stepped` (`front_band.py:69-74`) switches at the next station (12 m), not at 5.0 → a 7 m taper.
- South ramp @0: route14 carried by E (212.8 m² in the corridor, 0 outside the deck); ramp then clipped at top_s 24 by two stops that only graze the rim zone: `edgestrip:3:dsf:pol241` (groundside fence strip, 50 m², x 1187.5–1192.5, y −991…−977; 11.5 m² overlaps the ring, none inside the ring shrunk 2.2 m) and `pav15` (apron, 0.6 m² at 1189.1–1189.6, −994.4…−992.0). What-if (ignore stops touching only the outer 2.2 m): top_s 132.0, clipped_by ''.

## C′ + F — one lateral fit
Rule: per side and per station, the ramp's half width is the target cut back to stand clear of whatever stands beside the corridor, never below the mapped road's own half width. Target: the front's halves for s ≤ face_front_m, the opening's beyond. A stop that still hits at the minimum stands across the floor → today's loop (carry, clip, refuse), unchanged. The fit never refuses a mouth and never shortens a ramp.
Single site: `planar/front_band.py` gains `fit_halves`; `trim` deleted. `planar/structures.py:1072-1096` and `:1113-1124` call it. Clip loop `:1154-1208` untouched.
Algorithm: (1) cur = target at every station of ss; add stations face_front_m and face_front_m + grid (square step). (2) Build the ring with the loop's own `_ring` closure and probe it with the loop's own `_pad_hit` (same stops, tree, gap; exclude carried ∪ pin hosts). No hit: done. (3) For the hit ref: its part within gap of the probe, its side, its least across distance d from the axis over its station span (sampled every grid). If d ≤ minimum + rim_off + gap + grid → real stop, return cur. Else cut that side at stations within one spacing of the span to floor_to_grid(d − rim_off − gap − grid), never below the minimum. Repeat (cap 400 iterations; at the cap return the opening's halves with a note — never a refusal). (4) At s = 0 and inside walls_s never below the opening's halves (#1917, #1938 S2). (5) Minimum = the road half 0.5 * width (the value `half` had before `structures.py:548-549` replaced it by the opening). No new law key; face_front_m stays 5.0 (`law/structures.toml:312`).
Census (08-30l): a ramp with per-station halves = today's traced ramp (`structures.py:1127-1143`, `underpass_mouth.sheared_ring:266`, `structure_mouth.py:496-520`). Grep the `half_fn` readers and list each in the report before editing. opening_xy readers unchanged. drawn_site gains front_m.
Tests: no stop in reach → halves = targets; a stop 0.5 m inside the stand-off → side cut, pad_hit None; a stop across the floor → today's clip byte-equal; a mouth that builds with face_front_m = 0 builds with any front; top_s with the fit ≥ without; step within one grid of face_front_m.
Bars (KLAX replay, then drawn gate):
| Site | Bar |
|---|---|
| @1 | not refused; east floor end x ≥ 1188.0; top_s ≥ 156; clipped_by '' |
| North mouth | floor within 0.3 m of 25.54 from x 1143.5 to 1188.0; the 2.1 m airside trim quoted |
| @0 | clipped_by ''; top_s ≥ 120; east side narrowed ≤ 3.0 m only between s 24 and 48, per station; deck top − floor ≥ 5.1 m under obj18210 |
| KLAX solve | relaxed rows ≤ lane 1's figure + 5, each new one listed |
| Corpus (planar-only replays: the 12 front-census airports, LFPG, KMCI, KATL, KIAH, LPHR, ELLX, LICJ) | no tunnel refused that builds at control; no top_s shorter; every changed ramp listed with its band/fit in metres |
| EGLL 10.obj ends (owner site 51.474061486,−0.452935547; ramp end 51.473395908,−0.452951722) | reported |
Closing: `build_airport.py KLAX --tile 33 -119 --pack-copy`; drawn_gate at the owner's four points and the bridge, --against control, no MOVED.
Stop rules: a corpus change at KEGE, BIKF or LICJ; a second miss on any bar; any mouth refused by the fit; > 3.0 m narrowing needed at @0.

## D′ — NOT for a lane yet (K0-D scout first)
Kept by measurement: (a) every level other than the block is an island: one riser width off the pad's whole outer boundary, two off the airside (block keeps a riser-wide band; apron welds to the block everywhere); (b) a pad piece outside the plan touching airside is the block's (`storey_pad.py:321`); (c) the back cut yields to mapped road faces again (A2 (3)); (d) no kerb beside a level below the block; LPHR's welded upper level byte-identical (an island rule for a level above the block needs its own reading: weld only to the highest level a cell borders). Open (K0-D, read-only): name the objective term that puts the outside at the block's level along an island riser's outer edge (candidates `constraints/pad_ramp` "ramp from the pad", `pipeline/lot_follow`, §37 (10) road contact rows); test minting the island's boundary band with the basin wall role as the pit did; pass: with levels flat, T2 base road within 0.5 m of control and LFSB lot dsf:pol80 within 0.5 m of control. Then Fable amends D′.

# Amendment R5 to spec 2062 — KLAX E′ + C′ + F (Fable, 2026-11-15; owner chose "Redesign" 13:12Z)

Base: origin/claude/lshell4 merged with origin/claude/lr6knee (conflicts: `planar/free_bridge.py` 2 hunks — keep both, pass E's `ways` to `_bw.any_route`; `pipeline/stage_code.py` 2 registry hunks; `docs/frames.jsonl`). Paths under `Ortho4XP/src/auto_patch_v2/`; bridge files cited at lr6knee, `planar/structures.py` at lshell4. Rulings 14d/e/f/j, 14m (1), 22d, 22n, 27r, owner Q5 04:08Z, 08-30l, 10-05e. D′ stays out; the old pit path stands. R4 (C′ + F) text: /private/tmp/claude-501/-Users-noah-XPTerrainBuilder--claude-worktrees-vigilant-lederberg-4eb8b5/36801969-f4c8-4829-9e02-0dc8b5704d14/scratchpad/2062-R4.md (its line numbers are lshell3's; here the half-width site is `planar/structures.py:1088-1111`, the loop `:1113-1210`).

## 1. Findings
- Drawn row (`frames/lshell4/KLAX6_drawn_site.json`): row 18814 plain OBJECT, body `Misc/Road_Bridge__b0_66a28d8f.obj`, unshifted; y = 0 on the drawn mesh at its body anchor (33.9343199, −118.3963359) = 27.33 (anchor on route14's ribbon 15.4 m in from the west end); top 27.83, end tops 27.03, pier foot 21.33. Control (`KLAX_ctl_drawn_site.json`): row 18804, anchor ground 27.56, body shifted +6.0, top 34.06, end tops 33.26.
- Object `Misc/Road_Bridge.obj`: all ATTR_hard_deck; pier −6.0, underside −1.0, driven surface −0.3 at both ends, kerbs +0.5; origin 5 m beyond the west end (placement 18210 at 33.934299898, −118.396554321, heading 82.756).
- How kept bridges get their seat (lr6knee): not MSL. `pipeline/rebake_inputs.py:122-175` publishes every kept deck; `zero` only for a stack with a graded or joined end (`:169-172`). `airport/rebake_plan.py:427-480` (`with_kept`) clears `deck_datum_z` (`:455`), flags the rectangle ends, sets `anchor_zero` (`:478`). `airport/bridge_approach.py:149` returns that zero only when every end is flagged. Row stays an on-ground OBJECT.
- Why obj18210 did not: (1) lshell4 predates that publication (its `rebake_inputs.py:122-146` publishes only stacks with a graded end); (2) both ends read flush on the DEM (west +0.02, east −0.43) → no stack minted (lr6knee `airport/bridge_stack.py:352`); capture `airport.deck_stacks` holds obj18211 and obj500 only; (3) member kept `deck_datum_z` = solved surface median inside its ring (`emit/rebake.py:52`; 47 vertices median 28.49, range 25.14–32.24), deck top +0.5 on it: 27.33; (4) predicted 33.127 exists only as a log line (`KLAX_b.log:9`).
- Ends (`KLAX_solved_b.pkl`; a = west, b = east, top −0.3 at both): DEM on the line / 1.5 m out 32.67 / 32.81 (W), 33.21 / 33.27 (E); faces under the line W: route14 (groundside), taxiway F zone-2 strip, gap; E: apron dsf:pol241, taxiway dsf:pol218 at the north corner; solved level (lshell4) W 28.4–29.9, E 32.08–32.28. DEM at the origin 33.127, 26.5 under mid-span (lidar carries the real cut). 117 m² apron + 18 m² taxiway on the plate. Zero from the airside ≈ 32.45 (delta ≈ −0.68); pier foot 26.45 vs lidar floor 26.5.
- Terrain under the deck: ramp @0 top_s 24.0, clipped_by edgestrip:3:dsf:pol241, level 25.14, axis (1170.0, −951.2) → (1170.1, −975.2), ends under the deck; record has `Deck(object_deck:dsf:obj18210, s 14.40–31.03, z 33.627)`; route14's ribbon runs through the plate and dives to the west rim (28.4 at the west end line, 27.2 at the rim); nothing holds either end line.
- Rule C's code is NOT on lshell4 (it lives on lshell3) → port C first.

## 2. Rules
E′1 — carrying a stop over the ramp (one site: `planar/structures.py:1113-1149`, `_carried_by_deck:1722`). A stop is carried only by a deck that has a bridge read (a deck of a free or kept stack in `airport.deck_stacks`, or of new `Airport.kept_candidates`, every end on land) whose top (stack zero + deck_top_y) stands ≥ `[bridge] clearance_m` (5.1) over the level floor at every station under it; otherwise the stop stands (today's clip), noted `deck_without_bridge_read` / `deck_too_low`. When carried: record `Tunnel.carried += ((ref, object id),)`; set that `Deck.z` to the stack's top; add the carried ref's cells inside the whole plate ring to `bank_cuts` (`:1625-1640`, the knife; no cell minted). The route's ribbon then ends on the plate's ring; the floor stays level under the deck (`:908`) and climbs at the design grade beyond.
E′2 — the kept stack over a floor. `planar/free_bridge.read_bridges` (`:363-386`) keeps the kept reads it did not mint (every − stacks, kind kept, not kept-by-crossing) on `Airport.kept_candidates`. `planar_stacks` (`:473-506`, called at `planar/build.py:432`) gains the candidates and the carried deck ids; a kept stack or candidate whose deck is carried is kept with `DeckStack.over_floor` = the structure ids, graded end or not. An end line with ≥ half its stations on rolled-on airside pavement is state `joined` and recorded in `DeckStack.airside_ends` (read through `deck_bridge.CellRoles`, as `admitted` does). `rowed_ends()` (`model/deck_stack.py:190-194`): a kept stack with over_floor rows its flush, graded and unread ends, as a free stack does.
E′3 — the zero (derived at `bridge_stack._kept_one`; read after the solve only through `agp_level.stack_zero`). No airside end: the predicted seat. With an airside end the airside governs: between the stages new `constraints/deck_airside.py` reads the median over that end's stations (triangles all stage 1) of level − e.top; two airside ends: the mean (spread > visual_m listed); fewer than half the stations read: delta 0, noted `deck_airside_unread`. `agp_level.datum_rewrite` (`:60-100`) merges that delta under key `airside:<stack id>`: no early return at `:67` when such a stack exists; `_tagged` (`:50`) also maps `object_deck:<deck id>` so the clearance band (`constraints/structures.py:684-696`) moves with the deck. `stack_zero` (`:164`) and `airport/road_ramp.py:2072` read new `DeckStack.datum_key` (datum_group, else the airside key).
E′4 — rows (`constraints/deck_stack._bridge_rows:209-313`): R1 through `rowed_ends()`; R3 for `kind == FREE or over_floor` (`:277`), for an over-floor stack never on a `hard` vertex (`:227`); R6 unchanged (lr6knee); no new ruling head.
E′5 — publication (`pipeline/rebake_inputs._kept_published:160-174`): for an over-floor stack: both route mids; `graded` = the mids of `rowed_ends()` (`:167`; identical for every other kept stack); `joined` = every other land end; `zero` = `stack_zero`. `with_kept` and `approach_seat` unchanged (both ends flagged → the object stage takes the published zero on any mesh). No plan version bump.
C′ + F — port rule C from origin/claude/lshell3 (C only, never D): new `airport/entrance_front.py` and `planar/front_band.py`; the front_xy hunks in `airport/trench_objects.py` and `portal_objects.py`; `face_front_m = 5.0` in `law/structures.toml` and `tunnel_object_schema.py`; the three `planar/structures.py` hunks (front_stop, front_pins, the front_t block); registry rows in stage_code.py, O4_Step_Code.py, provenance_code.py. Then apply R4's "C′ + F — one lateral fit" as written (`front_band.fit_halves` replaces `trim`; clip loop untouched).

## 3. Consumer census (08-30l)
| Consumer | file:line | Ruling |
|---|---|---|
| Mapped-bore stops, clip loop | planar/structures.py:1113-1210 | E′1; F fits before it |
| Knife | planar/structures.py:1625-1706 | + the carried ribbon inside the plate |
| Object-deck clearance band | constraints/structures.py:684-696 | reads the stack's top; moves with the datum |
| planar_stacks, live_stacks | planar/free_bridge.py:473, model/deck_stack.py:273 | E′2 |
| end_road_vertices, deck_end_seeds | model/deck_ends.py:176-230, airport/deck_ends.py:30 | unchanged; read rowed_ends |
| _rewrite_ways, stack_ground, deck_ground | airport/deck_stack.py:604, planar/stack_ground.py:136, geom/deck_ground.py:175 | unchanged; twin: an over-floor stack with flush ends mints no ground and rewrites no way |
| datum_group readers | planar/free_bridge.py:501, pipeline/publication.py:1572, model/agp_plate.py:32, airport/access_road.py:130 | unchanged (read datum_group, never datum_key) |
| Sidecar rows | pipeline/publication.py:1547-1575 | + over_floor, airside_ends, zero_pred_m, final zero |
| with_kept, approach_seat, airside_zero | rebake_plan.py:427, bridge_approach.py:149, airside_deck_seat.py:372 | unchanged |
| half_fn readers | planar/structures.py:1088-1111, 1238, 1432, underpass_mouth.py:267 | list each before editing (R4) |
| UIs, wire | — | none |

## 4. Order of work
K0 (read-only) → report to the master and WAIT for "go": (1) merged base, `tools/bridge_census.py --ends` on the KLAX, KDEN, KBNA, OTHH, KMCI captures: rows vs lr6knee; (2) KLAX base replay (`v2_solve_replay.py --replay … --from classify --emit --solved-out`): obj18210's plan member and seat; (3) every capture in `frames.py list`: each deck E carries, with its bridge read; (4) whether the west end's strip vertices are stage 1. Then port C → C′ + F → E′1 → E′2–E′5 → replays → one tile build.

## 5. Tests
Structures twin: carried only with a bridge read and 5.1 m; the ribbon cut on the ring; the stop stands at 5.0 m. test_bridge_stack2065.py: a candidate promoted; a flush-ended over-floor stack rows both ends and R3; an airside end is joined, never rowed; every other kept stack byte-equal. New test_deck_airside.py: delta moves R1, R3, the clearance band and the ramp target; unread gives 0; stack_zero. test_free_bridge_seat.py: both ends flagged → the seat is the published zero on a mesh with a trench under the anchor. R4's six fit tests. Plus test_harness, test_no_airport_specific_code, test_v1_retired, registry twins, ratchets dupes --near / unused / layers.

## 6. Bars (replay first, then drawn; flush 0.04)
| Site | Bar |
|---|---|
| obj18210 stack | kept, over_floor [@0], east joined, west rowed; predicted zero 33.127 ± 0.01; delta reported (expected −0.6 to −0.8) |
| East (airside) end | deck end top within 0.05 of the airside median at the end line; per-station spread listed (expected 0.20) |
| West end | route14's end-line vertices and the slab in [P − 0.04, P]; drawn step ≤ 0.30 |
| Under the plate | no non-airside vertex above the plate less 0.04; airside overs listed (expected ≤ 0.15) |
| @0 | carried; clipped_by ''; top_s ≥ 120; floor 25.14 ± 0.01 under the deck, ≤ 5 % beyond; deck top − floor ≥ 5.1 (expected 7.8); east narrowing ≤ 3.0 m between s 24 and 48 |
| Rebake | member: deck_datum_z None, both ends flagged, anchor_zero = final zero; drawn end tops = zero − 0.30 ± 0.05 |
| @1, north mouth, KLAX solve, corpus, EGLL | R4's rows |
| T8 | as lshell4_KLAX6: mesh 25.54 ± 0.05, Terminal_8_Buildings PASS |
| Roads at RBRIDGE | max step ≤ 0.5 m (control 4.43, lshell4 4.34); a step on a way outside the ramp is listed |
Closing: `build_airport.py KLAX --tile 33 -119 --pack-copy` (refresh dem,rings as needed), then `drawn_gate.py` at T8E=33.940411615,−118.396398062,15, T8W=33.94043,−118.39652,15, RBRIDGE=33.93433,−118.39617,40 and the owner's two north-mouth points (33.940279765,−118.396457834 and 33.940330430,−118.395949179), `--against /Users/noah/XPTerrainBuilderData/.harness/frames/lshell4/KLAX_control.drawn.json`. RBRIDGE judged on its bars (the bridge moves ≈ −1.1 m vs control by design). REGISTER the build's rebake plan (o4_v2_rebake_KLAX.json) and pack copy rows with the closing frames.
Protected: KDEN, KBNA, OTHH, KMCI `--ends` rows and kept plan records identical to the merged base; KEGE, BIKF, LICJ replay-emit patch body identical.
Stop and report, never iterate: K0 shows a carried deck or changed bridge row at a protected/certified airport; KLAX datum unread; clearance band infeasible after the datum; a hard conflict within 100 m of the bridge; the west end's vertices are stage 1; any mouth refused by the fit or > 3.0 m narrowing at @0; a second miss on any bar (floor 0.01 m). Build time: report KLAX's planar clock before and after (expected < 0.6 s added).

## 7. Owner questions (defaults applied; master asking)
Q1 east end on the apron: (a, default) the deck follows the solved airside there: top ≈ 32.95 (≈ 1.1 m under the installed 34.06), route14 cut ≈ 0.5–1.0 m at the west end and ramped back at 5 %; (b) keep the predicted 33.127 (a 0.7 m step up from the apron). Q2 with (a) the pier foot floats ≈ 1.3 m over our floor (25.14, pinned by Underpass_2's bottom; lidar floor 26.5); 22d allows it; listed.
