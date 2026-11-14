# #2090 — AGP group datum, joined bridges and the complex's ground (Fable, 2026-11-14)

Base: ONE branch holding origin/claude/l2090 972215367 [A] (AGP lift) and origin/claude/l2090d 00fbff983 [D] (contains l2090c a416fcacb and l2065e 0b6b1bec3). Paths under `Ortho4XP/src/auto_patch_v2/` unless said. Read: RULINGS 2026-09-28a (1) (2) (4), 08-27 (grade law outranks shared datum), 10-19u, 08-30l, 10-05e, 11-13r, 11-13v, 11-14d/e/f, airside is king, groundside terrace law; `docs/specs/2065-bridge-class-A3.md`; owner 2026-11-14 20:29Z / 20:41Z / 20:49Z (#2090). ONE Opus lane, parts in the order A, D, B, C, each part its own commits and its own replay gate; ONE closing KDEN build. A part that misses its gate is not landed and is reported; the parts before it close alone. Never raise the lane cap; delete your scratch builds when you report.

Owner (verbatim): 20:29Z "...the main terminal and it's buildings and parking garages are all seated a few meters too low, so it does not stay connected to the sky bridge that goes over to Concourse A." 20:41Z "...the nearby bridge connects the elevated access road here: 39.849466710, -104.677903024 to the garage's second level, so a road passes under the bridge. Note that currently I think all the parking garages and central terminal are seated too low burying the bottom floor of the garages". 20:49Z "The terminal is connected via the skybridge to concourse A, so must stay with concourse A as part of the object group, which will lift everything on the groundside there higher, probably more like 3m, and grading may need a little adjustment to match that." 21:42Z "Lots 5%".

PRE-LANDING CLEANUP: commit 75f8d4971 (in l2090c and l2090d) added `Ortho4XP/{Flights,Tile_packages,World_build,World_staging}` as symlinks (`Flights` -> `/Users/noah/XPTerrainBuilderData/Flights`). Remove them from the tree (git rm --cached) in this branch's first commit.

## C0. Findings (measured unless marked)
F1 X-Plane ("X-Plane 10 Autogen Scenery File Format"): `GROUND_PT` is the point "used to align the tile with the ground vertically"; `OBJ_DELTA`'s height is "a vertical offset in meters from the height of the terrain at the tile's ground point"; "autogen points do not support an AGL height in a DSF"; `OBJ_DRAPED` stays on the terrain under its own origin.
F2 `Jeppesen_Concourse.agp`: 55 `OBJECT` + 55 `OBJ_DELTA`, every height 0, at 7 points; `TEXTURE_WIDTH` 1000 m, anchor = ground point = tile centre, `HIDE_TILES`. DSF row 39.847647250, -104.673782139. Lowest solid by 50 m cell: garages and terminal flanks -0.4..+0.1, the centre hall +11.9..+15.9, the north block +8..+12. Garage slab tops y 0.15 / 3.45 / 6.75 / 10.05 / 13.85 (`..._All_Jep_Garage_Solid.obj`; 1,152 triangles at 0.15). Pieces reach 750k vertices. (Garage second level = y 3.45 → 1632.95 at datum 1629.50, NOT 1633.90.)
F3 Graded doc `frames/l2090c/KDEN.graded.json`: Concourse A's ground point stands on face 1140 `building24` (role building, side airside, flat 1638.50); the Jeppesen ground point on no face; face 1384 `building22` (62,997 m², z 1632.66-1633.53) lies under the terminal; no building face under either garage (service-road faces `small_roads:-10258` 1627.81-1628.20, `-10281` 1627.74-1627.88); access road `small_roads:-18914` 1631.00-1631.86 (W), `-20087` 1630.58-1631.48 (E).
F4 [A] `airport/agp_ground.py` derives the datum AFTER the mesh (`plan_lifts` :402: governor = a member on a graded face, `_governor` :326; `_graded` :342; pairs of two graded members never read, :412). Nothing before the solve knows the group.
F5 [D] `frames/l2090d/KDEN.ends.txt`: `dsf:obj31305-31308` Garage_Bridge (west) are kept bridges, predicted seat 1631.146-1631.298, end a flush / governing, end b GRADED gap +3.28..+3.83, run 71-82 m. `dsf:obj31302` is read as a deck but 31302-31304 (east) have no kept row. Garage_Bridge.obj: 14.3 x 42.1 m, end a at the row (z 0), deck top y +0.05, underside -1.60, piers to -10.60.
F6 DSF (`+39-105.dsf.anchor_bak.89f24e78.text`): Garage_Bridge rows :33355-33361 (3 east at lon -104.66975, heading 270; 4 west at -104.67792, heading 90); end b = 42.09 m toward the garage (W 39.849465, -104.677426; E 39.849256, -104.670243) and stands 3 m inside the garage's wall line.
F7 The author's patch `<pack>/Patches/KDEN.patch.osm`: 418 closed ways, `altitude` whole metres: 1628 under the terminal, garages and lots, 1637 under Concourse A, 1632 on four access-road strips beside the garages, `altitude_low/high` 1628/1632 ramps. Step 1637 - 1628 = 9 against the join's -9.02. CHECK ONLY (never a level witness).
F8 The stage-2 rewrite is ONE site: `constraints/road_ramp.reach_seed_rewrite` (main :556; bound in `pipeline/build.py` :652-662), which receives stage 1's solved levels. `constraints/group_level.group_level_rewrite` (:127) is the precedent.
F9 Deck-stack rows are numeric `Band`s on `DeckStack.zero_z` ([D] `constraints/deck_stack.py` :87, :193); the object stage seats a kept deck at the published zero only "where every end was graded" ([D] `airport/rebake_plan.with_kept` :425; `pipeline/rebake_inputs._kept_published` :122).
F10 An end line's road vertices are ONE selection ([D] `model/deck_ends.end_road_vertices` :30; crossings `_crossing_vertices` :55; seeds `airport/deck_ends.deck_end_seeds` :32).
F11 The terminal's GROUND_PT stands under the Westin's elevated deck (lowest solid above it y +13.6) on ungraded DEM 1625.97 (rail trench likely just south) — a seat check, not a grading target.

## C1. Review of [A]'s lifted copy — KEEP, amended
Correct in X-Plane (F1): the heights state the datum over whatever ground the point reads; draped pieces stay on the ground. Q-31 is kept (the row is never `OBJECT_MSL`). "Move GROUND_PT only" is refused: no ground at 1629.48 exists in the tile. Later grading does not disturb the seat, because the lift is `need - drawn ground at GROUND_PT` on each build. Amendments:
V1 ONE DERIVATION. The datum a follower is lifted to is the PUBLISHED one (rule A4); `plan_lifts` re-derives it only when the graded doc has no `agp_groups` key.
V2 JOIN CERTAINTY (13r). A join stands when its winning step has two or more votes of distinct level pairs and more than any rival (KDEN: 11.48|20.50 and 15.98|25.00 -> -9.02), or when |step| <= `flat_step_tol_m` (one pair is enough). A single pair with a non-zero step is no join: listed with its step. (KEWR +1.60 expected refused.)
V3 The five constants of [A] `agp_ground.py` :70-78 move to `law/structures.toml [agp]` with the new keys below.
V4 `AgpSeat` records `gp_relief_m` (drawn relief within 2 m of the ground point). Record only; over 0.10 m heads the report.
Left as built and listed: an `.agp` holding `OBJ_GRADED` / `OBJ_SCRAPER` / a facade is not lifted.

New `[agp]` keys: `connector_floor_m` 2.5, `contact_m` 1.5, `lift_tol_m` 0.05, `flat` 0.9, `step_bin_m` 0.05 (moved); `flat_step_tol_m` 0.10, `airside_reach_m` 60, `datum_slack_m` 1.0, `deck_join_reach_m` 3.0, `deck_join_margin_m` 1.0, `ground_band_m` 0.6, `floor_min_area_m2` 100, `plate_max_off_m` 3.0.

## C2. Rules
### Part A — the group datum
A1 THE RECORD, derived once at the pack stage, before the bridge stacks ([D] `planar/free_bridge.attach_free_bridges` :249 calls it first). New `model/agp_group.py` (data only) and `airport/agp_group.py`: `Airport.agp_groups` = per group its id (`agp:<lowest row>`), members (row, resource, ground point, chain step from the governor), joins (step, votes, runner-up votes, contact point), governor, `zero_pred`. Members and joins are [A]'s `candidates` / `joins` with V2. Every file opened goes through the stage's file witness (`airport/file_witness`).
A2 PROVISIONAL GOVERNOR (pack stage): the member whose ground point is nearest the apt.dat airside pavement ([D] `airport/deck_stack._Airside` :216), when that distance is <= `airside_reach_m` and every other member is at least twice as far. None: the group grades nothing this build (listed `agp_group_unpredicted`); its objects are seated by [A]'s rule.
A3 `zero_pred(m)` = DEM at the governor's ground point (`airport.dem`, as `_end_ground` :244) + the chain step. It fixes GEOMETRY only (rules B and C).
A4 THE DATUM, exact, at the ONE stage-2 rewrite. New `constraints/agp_level.py`; `datum_rewrite(planar, law, cs, levels)` is called last in `reach_seed_rewrite`. z_gov = the design surface's triangle under the governor's ground point (`face_index.FaceIndex.terms_at`, as `group_level.witness_terms`) on stage 1's `levels`; `delta = z_gov - DEM`. Every row that names the group (`Source.inputs` holds `agp:<gid>`, or the id of a stack whose `datum_group` is the group) has its bounds moved by `delta`. Where the triangle is not all stage 1's: `delta = 0`, noted `agp_datum_unread`. No second solve.
A5 AFTER THE SOLVE one helper, `agp_level.final_zero(record, report)`, is the only reader of a group datum or a joined stack's zero: `pipeline/publication` (new sidecar key `agp_groups`: governor, z_gov, delta, per member datum and ground point, joins, deck joins, plates; and `bridge_rows` [D] :1501), `pipeline/rebake_inputs._kept_published`.
A6 OBJECT STAGE. `plan_lifts(..., published=)`: a follower's `need_z` is the published datum; lift = need - drawn ground at its ground point. The governor's drawn ground less published z_gov is counted `agp_governor_drawn_off_m` (listed over 0.05). Followers and the governor come from the record, never from "stands on a graded face". New reader `airport/placement_read.agp_groups_from_graded_doc` (the form of `decks_from_graded_doc`).
A7 NEVER MOVED: the governor; a member standing on a face stage 1 solved; a row the plan holds as a jetway-strip rider; anything airside.

### Part B — a bridge deck joined to a floor
B1 DECK JOIN (pack stage, [D] `airport/bridge_stack._kept_one` :253, after the predicted seat). For each land end of an all-deck frame's deck: the connector floors (`>= connector_floor_m`) of a FOLLOWER member under the end line's stations (`agp_ground._over`, `contact_m`). The floor nearest in level to the deck's predicted top there joins, `D_k = zero_pred(m) + y_k - (seat.zero + top_e)`, when |D| <= `deck_join_reach_m` and the next floor's |D| is at least `deck_join_margin_m` larger. KDEN west: 1632.95 (y 3.45) against 1631.3, D +1.65; next 1636.25, D +4.95. No predicted seat, no datum, two ends that join, or a lone / governor member: no join, listed with the numbers.
B2 THE JOIN IS A WITNESS: an all-deck hard-deck frame with a joined end is a kept bridge whether or not a mapped way is carried (KDEN east, F5); its other end is read as a stub's (axis ray). Site: [D] `planar/free_bridge._read_free_bridges` :181.
B3 ZERO AND STATES. `zero = zero_pred(m) + y_floor - top_joined`; `DeckStack.datum_group = gid`. The joined end's state is `joined` (new member of `model/deck_stack.END_STATES` :44; governing semantics: no row, no ground). The other end is read by `end_state` on that zero. A joined stack is always minted, graded end or not, so its zero is published.
B4 THE ACCESS ROAD. Where an at-grade road passes the graded end's line within the slab (`end_road_vertices`' own selection or a crossing vertex), the end's corridor is the slab alone: no run-on, no R6. Every vertex of that road between two such ends whose stacks join the SAME floor (same member, same y) is seeded on the line between the two ends' levels, and held as R1 holds an end-line vertex. The road's own ramp runs from the outermost ends. New selection `access_road_vertices` in `model/deck_ends.py`; merged in `deck_end_seeds`; rows in `_bridge_rows` under `edge_deck.RIGID`. Where no road passes the end line, A3's rules stand.
B5 Nothing is built under a joined deck: the road under it keeps its level (owner 20:41Z).
B6 OBJECT STAGE. `_kept_published` adds `"joined": [end midpoint]` and the final zero; `with_kept` flags an end that is graded OR joined, so `approach_seat` returns the published zero (never 22p's road under the span). `PLAN_VERSION` 15 -> 16.

### Part C — the ground at a follower's ground floor
C1 PLATE: per follower member, the plan of its up-facing static floors with |y| <= `ground_band_m`, per connected part, area >= `floor_min_area_m2`; level y_p = the area median; `L = datum(m) + y_p - deck_flush_m`. KDEN: the two garage slabs (y 0.15, about 155 x 365 m each), the Westin's base strip. A plate whose median |L - DEM| > `plate_max_off_m` is not built (listed).
C2 GEOMETRY. New `planar/agp_ground.py`, the form of [D] `planar/stack_ground.stack_ground_pieces` :52: graded pieces `agp_ground:<gid>:<row>:plate#k` and `:bank#k` (new `AGP_GROUND_PREFIX` in `model/planar.py`). Bank width max(`bank_min_width_m`, |L - DEM| / emit `bank_slope`), toe pinned by `constraints/fill_bank`. Every piece yields to airside pavement (cut back `pad_frontage_m`, noted), structures, deck-stack rings, building pads (listed `agp_plate_on_pad` with both levels) and stands off cells and road ribbons as stack ground does.
C3 ROWS (`constraints/agp_level.py`, head `edge_deck.RIGID`, inputs `agp:<gid>`):
 P1 every vertex inside a plate that is no airside, structure, rigid or road-ribbon vertex stands in [L - visual_m / 2, L];
 P2 every at-grade road vertex inside a plate is seeded at L, and the road ramps from the plate's edge at `ramp_grade` (through `deck_end_seeds`); a way at another layer is left as built (listed);
 P3 a `parking_lot` vertex d metres outside a plate, d <= max|L - DEM| / 0.05, stands in [L - visual_m / 2 - 0.05 d, L + 0.05 d] (owner 21:42Z: lots 5 %).
 Seniority: another stack's R1 / R3 over P1; P1 over P3.
C4 `classify/ribbon_mint.road_extent` (:84): the reach gains every plate and bank grown by `boundary_reach_m` (A3 rule 7's one site).
C5 Not in this round: the frontage road beside a plate (owner Q1 default a: road along the garage wall under the bridges stays on today's ground; a bank rises to the garage floor and each entrance ramps at 5 %), a pad under a follower (owner Q2 default b: leave `building22` this round), the terminal's north block, mapped roads on the AGP's elevated floors.

### Part D — the floor cache
D1 `agp_ground._piece_floors` ([A] :149) reads through a per-file record: the up-facing static floor triangles (float32) and the file's plan box, in `<mod cache>/<pack>/o4_agp_floors.cache`, keyed per piece on its pristine file (`pack.authored_source`; size + mtime, content sha256 kept and compared when the stat moved, the discipline of `airport/partition_cache`), the reader's version and `flat`. Temp file + `os.replace`; a miss or a refused write just computes.
D2 A piece is parsed only for a pair [A]'s `joins` admits, a follower's plates, or a deck end within `contact_m` of a follower's tile. Two airside members are never read (A2's distance, before any parse).
D3 Register the file family in `tools/harness/shared_repo_guard.py` beside the pack's other mod-cache files, same commit.
Build time: warm, the AGP read must cost under 0.6 s at KDEN (1 % of the 60 s airport budget), read from the stage clocks of two consecutive runs, never one A/B pair. The cold parse is once per pack version; report its clock.

## C3. Consumer census (08-30l)
| consumer | ruling |
|---|---|
| 1 `airport/load.py` :572-612 (`.agp` rows as `DsfObject`) | unchanged: pieces are never expanded into placements |
| 2 `airport/riders.py` :175-204, `constraints/jetway_strip.py` | unchanged; a strip rider is never a follower (A7). VERIFY the Jeppesen row has no `Rider` |
| 3 [A] `agp_ground.joins` :282 / `_step` :255 | EDIT: V2 |
| 4 [A] `agp_ground._governor` :326, `_graded` :342, `plan_lifts` :402 | EDIT: A6; today's rule is the fallback |
| 5 [A] `placement_write.build_plan` :265, `auto_patch/object_stage._agp_surface` :115 | EDIT: pass the published groups |
| 6 [A] `dsf_write._agp_defs`, `_write_pack`, `missing_body_files` | unchanged |
| 7 [D] `bridge_stack._kept_one` :253, `planar/free_bridge._read_free_bridges` :181 | EDIT: B1-B3 |
| 8 [D] `bridge_end_state.end_state` :358, `_run_on` :297 | EDIT: `joined`; B4's slab-only corridor |
| 9 [D] `model/deck_stack.py` :44, `DeckStack` | EDIT: state, `datum_group`; `rowed_ends` unchanged |
| 10 [D] `geom/deck_ground._free_footprint` :134 | unchanged; VERIFY a joined end mints no apron |
| 11 [D] `constraints/deck_stack._bridge_rows` :193 | EDIT: B4 rows |
| 12 [D] `model/deck_ends.py` :30 / :55, `airport/deck_ends.deck_end_seeds` :32 | EDIT: B4, P2 |
| 13 `airport/road_ramp.road_ramp_targets(deck_ends=)`, `constraints/road_ramp` rows | VERIFY the rows minted from a seed carry its stack / group id; EDIT to carry it if not. Cannot be done: STOP |
| 14 `constraints/road_ramp.reach_seed_rewrite` :556 | EDIT: A4 |
| 15 `solve/design_stage.stage_split` | unchanged; VERIFY no plate, bank or joined-stack vertex is stage 1's |
| 16 `planar/build.py` (where stack ground is minted), `model/planar.py` | EDIT: C2 |
| 17 `constraints/fill_bank`, `solve/design_ground` | EDIT / VERIFY: the new prefix is banked and takes the ground datum as stack ground does |
| 18 `emit/road_join`, `geom/coverage.py` | unchanged; VERIFY a plate island emits |
| 19 `classify/ribbon_mint.road_extent` :84 | EDIT: C4 |
| 20 [D] `pipeline/publication.py` :790, :1501 | EDIT: A5 |
| 21 [D] `pipeline/rebake_inputs._kept_published` :122, `airport/rebake_plan.with_kept` :425 | EDIT: B6 |
| 22 [D] `airport/bridge_approach.approach_seat` :87, `anchor_rule.datum_of` | unchanged; VERIFY the zero is returned when both ends are flagged |
| 23 object rows standing on a plate (ground-following) | unchanged; judged by the gate's object layer |
| 24 `verify/`, `tools/check_grade.py` families | unchanged: no new head. A registration demand from `tests/test_harness.py`: STOP |
| 25 `pipeline/stage_code.py`, `src/O4_Object_Stage_Code.py` :132 | EDIT: key every new module in each stage that imports it |
| 26 `tools/bridge_census.py`, `tools/drawn_agp.py`, `tools/harness/drawn_gate.py` | EDIT: `bridge_census --agp`; drawn deck-to-floor joins and plate edges; INDEX rows |
| 27 `airport/pack_optimise/swap.py`, `pack_health`, the DSF restore path | VERIFY they tolerate a `__g_<hash>.agp` def and file |
| 28 Mac / Qt layout, the wire protocol, `tests/test_v1_retired.py` KEEP | unchanged |

Heightfield: every surface single-valued; a plate is ground under a building, a joined deck is an object over the road.

## C4. Twins
`test_agp_ground2090.py`: V2 both ways (two pairs join; one pair at +1.60 does not; one pair at 0.00 does); the published datum overrides the drawn derivation; a follower standing on a graded plate is still lifted. New `test_agp_level2090.py`: `datum_rewrite` moves every tagged Band by delta and no other row; an unread governor leaves delta 0; stage 1's population holds no plate vertex. `test_kept_bridge_seat2090.py`: a deck end over floors 0.15 / 3.45 / 6.75 joins 3.45; margin under 1.0 refuses; an unmapped all-deck frame with a joined end is kept; a joined stack with a flush other end is minted and published; `with_kept` returns the zero for graded + joined. `test_deck_stack1971.py`: B4 holds the road between two ends of one floor and not between ends of two floors; KDEN's trench stack byte-equal. Floor cache: hit, stat-moved-same-content hit, content change miss, unwritable folder computes.

## C5. Gates
G0 (no code) `tools/bridge_census.py --ends` on `frames/l2090d/KDEN.pkl`: the seven Garage_Bridge rows' states written down (F5 expects four kept, end b graded).
G1 `bridge_census.py --agp` on the KDEN capture (re-captured if the pickle does not load) and on ONE `v2_solve_replay.py --capture KEWR`: per group members, joins with votes, governor, `zero_pred`; per deck join the floor and both D's; per member its plates. KDEN bars: one governed group, Concourse_A governs, Jeppesen follows at -9.02 +/- 0.05 on two pairs; no jetway row follows; all seven Garage_Bridge decks join y 3.45; the report also prints the author's patch altitudes at each ground point (F7; a check, not a bar). KEWR: every join with its votes; a single-pair non-zero join is refused; no build. A KEWR lift is never landed on this census alone (one line in `docs/DEFERRED_VERIFICATION.md`).
G2 `v2_solve_replay.py --replay <capture> --from classify --verify --emit`, KDEN, the predicted table written first. Bars: stage 1's levels equal to the base replay at every vertex; `delta` printed, |delta| <= `datum_slack_m` (over: STOP); each joined stack's graded end and B4 vertices within [-0.09, +0.05] of their level; the access road between sibling ends within 0.30 of the line; (part C) plate vertices in band, road at each plate crossing within 0.09 under L, lots <= 5.5 %; no relaxed or infeasible row the base does not have; the trench stack node-equal.
G3 `v2_rebake_replay.py plan <plan> <mesh or installed dsf> --graded G.json`: the Jeppesen seat's `need_z` = the published datum; every joined deck seats at its published zero.
G4 Closing, at most two tile builds (a control on the merged base unless one exists — l2090d's KDEN frame may serve; the arm last): `build_airport.py KDEN --tile 39 -105 --pack-copy --texture-mode default_xplane`, then `drawn_gate.py KDEN --tag T --against <control>` with
 `skybridge=39.85209,-104.67382,120 gb_w_a=39.849467,-104.677903,120 gb_w_b=39.849465,-104.677426,60 gb_e_a=39.849256,-104.669750,120 gb_e_b=39.849256,-104.670243,60 garage_entry=<the at-grade plate crossing nearest 39.8493,-104.6765 from G1>,60 plaza=39.847647,-104.673782,150 stack=39.842347,-104.673859`.
 Bars (drawn): skybridge join misfit within 0.15; each garage bridge's deck top within 0.15 of the floor it joins at end b and of the road at end a; ramp grade <= 5.5 % between stations; the road under each bridge not MOVED; garage_entry: road within 0.15 of L, ground along the plate's edge in [L - 0.50, L + 0.05], no object newly FAIL; plaza: the Jeppesen row's drawn datum within 0.05 of the published one, nothing MOVED outside published footprints; stack: nothing MOVED, no object changed; airside: no pavement node MOVED anywhere. The 8.24 m step on way -19790 is the control's: not worse.

## C6. Not verified
- `delta` at KDEN (DEM under Concourse A against 1638.50), and that face `building24`'s vertices are in stage 1's `levels`.
- Whether road-ramp rows carry their seed's stack id (census row 13).
- Why 31302-31304 are not kept, and whether `_over` reads their end lines.
- A2 at KDEN (Concourse A's ground-point distance to apt.dat pavement).
- How `fill_bank` and `design_ground` select the stack-ground family (row 17).
- KEWR: no capture, dump cache or tile on disk.
- X-Plane's read of a lifted copy in the sim (the owner's read).

## C7. Owner questions (defaults applied; master asked the owner)
Q1 The road along the garage wall, under the bridges: (a, default) it stays on today's ground, a bank rises to the garage's floor and each entrance ramps at 5 %; (b) weld it to the garage's ground floor as 13v does for a building pad.
Q2 The terminal's own pad (`building22`, 1632.66-1633.53) stands 3.2-4.0 m over the lifted terminal's zero, so about 3.5 m of its base stays in the ground: (a) next round, cut it to the group's zero where no airside rule is broken; (b, default this round) leave it.
Q3 The pack's own patch (F7): (a, default) a printed check only; (b) a witness that sets levels.
