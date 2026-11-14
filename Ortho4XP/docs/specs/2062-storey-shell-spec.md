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
