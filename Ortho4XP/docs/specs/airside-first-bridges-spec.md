# Airside-first generated bridges (lane lbridge2, 2026-11-19)

Law: `docs/RULINGS.md` 2026-11-19p, 19r, 19s (1)-(4). A deck WE generate
(`planar/deck_generated`, `witness == "generated"`) never moves airside.
Pack decks we keep (authored height) keep today's coupling (19s (4)); a pack
walled multi-bridge frame is still hidden by `planar/deck_takeover` and its
crossings become our decks (19p).

## 1. Pipeline order

| # | stage | what happens to a generated deck |
|---|-------|----------------------------------|
| 1 | planar, FULL map | the deck is derived (`planar/deck_width`): one per taxi route (apt.dat 1202, grouped by name) across the pavement over the cut, a parallelogram whose sides run along the route and whose ends are the cut's crests (parallel to the road), each end run on to meet the pavement (`[deck_gen] end_reach_m`); WIDTH = the route's width class, taxiway + shoulders (`[deck_gen] width_by_class_m`, ICAO Annex 14 §3.9.3 / §3.10.1), never the pack pavement or the cut. The pack pavement over the cut beside the deck is opened with its ring (`approach`); decks of parallel taxiways over one road closer than the road's two ramps at its grade cap are ONE cut (`deck_gen_pairs._pair_gap_m`); the deck's cut is never a survey keep-out (`survey_deck_cut`: the lidar floor is read, the region C is not drawn) |
| 2 | planar, STAGE-1 map (`model/stage_one.from_full`) | the deck is WITHHELD (`planar/deck_airside`): no deck record, no ring cut, no deck ground, no survey keep-out, no bore under it; its ring is FILLED with the carried route's pavement role (the taxiway spans the road on its own grade law) and its covered roads are covered ground (`planar/covered_ground`: the bare-earth trench is masked out of `Vertex.dem_z`) |
| 3 | stage 1 solve | the airside levels: the NO-BRIDGE SOLVE. Stage 1 is derived whenever the full map carries a generated deck, ribbons or not |
| 4 | between the stages (`stage2_rewrite`, `constraints/deck_floor_follow`) | per deck, the DECK SURFACE: a Coons patch (`geom/coons_patch`) of the stage-1 levels along its four ring edges (exact on each edge; a ring stage 1 carried no pavement under reads the full map's stage-1 levels on it, else stage 1's TIN round it). FIXED (`stage2_fixed`): every full-map airside vertex on or in the ring the coordinate join left without a level (the patch), the abutment crest under each end (the patch; never a road's or the cut's own vertex), and every other unmapped airside vertex within the deck's reach -- ring and opened pavement grown by `floor_min_m / [tunnel] ramp_max_grade` -- at stage 1's TIN. FREED (`stage2_free`): every ground vertex on or in the ring the join had fixed. FLOOR: every floor pin drops to `min(planar floor (lidar road), surface min - floor_min_m)` (slab + design clearance) |
| 5 | stage 2 solve | the cut, its banks and the roads in it, with every airside vertex a constant: the carve can never move airside |
| 6 | publication / object stage | the deck record carries the four edge profiles (absolute m) and its axis; `airport/deck_objects` draws the top as the same Coons patch, so each end is flush by construction; the kerb (lip) runs on the edges parallel to the route only |

## 2. Data handed on

* full map -> stage 1: `PlanarMap.decks` (generated ones withheld by
  `deck_airside.withheld`), the full map's anchors (generated ones carry no pin).
* stage 1 -> rewrite: `StageOne.solved` (stage-1 ids -> solved level, set by
  `solve/design_stage.stage_one_on`) and `StageOne.pm`; stage 1's own map
  carries `PlanarMap.withheld_rings` (every trend over it reads them blind).
* rewrite -> stage 2: `stage2_fixed {full vid: z}`; the moved floor pins.
* rewrite -> publication: `DesignReport.reach_seed["generated_tops"]`
  (`{deck id: {"a": [[t, z]...], "b": ..., "s0": ..., "s1": ...}}`).

## 3. Consumer census (every pass that read a generated deck before this lane)

| consumer | before | now |
|----------|--------|-----|
| `constraints/deck_anchor.derive` | pre-solve PIN at the window-blind profile on each end line (stage 1 and 2) | no pin: the anchor is published at its solved level only (sidecar, census) |
| `constraints/edge_deck._deck_rows` station + rigid rows | held the end lines flush to one zero inside the airside solve | none for a generated deck (the stations are stage-1 constants) |
| `constraints/edge_deck._span_rows` | bank/flush rows on ground AND a ceiling on airside vertices under the ring | stage 2 only (the deck is withheld from stage 1); airside vertices are constants there |
| `constraints/deck_floor_follow` | floor pins follow the anchor stations' stage-1 median | floor pins follow the deck surface's minimum (section 1 row 4) |
| `planar/deck_generated.carried_off` | cut airside cells under ring + approaches on BOTH maps | full map only (stage 1 withholds the deck; its ring is filled) |
| `planar/deck_bridge.deck_cut` banks, `deck_ground` | shared airside vertices with the bank (KBNA v13253) in stage 1 | stage 2 only |
| `planar/survey_deck_cut` (#2128 C keep-out) | cut pavement on both maps | full map only |
| `planar/structures` bores (`deck_bores`, §34 (5) underpass) | the road under the deck bored on both maps | full map only; stage 1 drops every bore under a withheld ring |
| `planar/covered_ground` | lifted `dem_z` over the generated deck's covered roads | the same, on stage 1 from the withheld decks (the trench mask) |
| `pipeline/generated_publication._zero` | zero = solved end-line stations less the planar top | zero and the top from the deck surface |
| `airport/deck_objects._top_fn` | one plane from `top_a`/`top_b` | the Coons patch of the published profiles |
| `airport/deck_structure.end_edges` | END = within `end_tol_m` of an end line AND across the route (KBNA: no end matched, lip all round) | END = every ring edge turned more than `end_angle_deg` off the deck's axis |

Pack decks (every `is_generated(d) == False`) are untouched by every row above.

## 4. Deleted

* the generated deck's pre-solve anchor pin (`deck_anchor.derive`'s generated
  branch) and its station/rigid rows;
* `deck_floor_follow._floor_targets`' anchor read (replaced by the surface);
* the pack-pavement width of the ring (`P ∩ C` across the route): the width
  is the class table's.

## 5. Bars (replay evidence)

Airside movers of the final surface against the no-bridge solve (stage 1) ≤
0.05 m at KBNA, KRDU, KORD, KPHX, KIAH, KJFK; every deck end flush by
construction; clearance per deck; lip sides; deck width = class width;
certified airports (no generated deck) identical.

Build-time impact: one stage-1 derive at an airport whose classification has
no ribbon but a generated deck; a Coons evaluation per deck vertex in the
rewrite (milliseconds).

## 6. The measurement arm

`tools/v2_solve_replay.py --no-bridge` (`planar/deck_airside.no_bridge_arm`):
the FULL map withholds its generated decks too (filled rings, no cut, no
deck), its stage 1 identical to the plain replay's.  The 19s bar is
`tools/airside_value_delta.py ARM.osm PLAIN.osm`, solve-owned frame.

## 7. Not done in this round (lbridge2)

* THE CARVE UNDER A ROAD THE PATCH DOES NOT DRAW -- done in lane lcarve,
  section 8.
* No wall-vs-embankment rule beyond today's generated-deck bank
  (`model/deck_bank`, 1V:1.5H via `constraints/edge_deck` span/blend rows).

## 8. The cut is the deck's (lane lcarve, 2026-11-19)

Owner 23:07Z: "When we insert a bridge, we know the size and shape of the
cut needed to provide the clearance under it, whether there's OSM or not
... we have to add the cut to the patch"; 23:09Z: "If we insert a bridge,
we need the cut, and the cut needs to grade smoothly away from the bridge
back to the natural terrain."  Law 19s (2)-(4).

| step | where | what |
|------|-------|------|
| record | `planar/deck_carve._deck_paths` -> `DeckBridge.carve` (`model/deck_carve.DeckCarve`) | per generated deck: its EVIDENCE (OSM road / rail per covered way, hidden pack frame, OSM bridge tag, lidar trench) and its ONE CUT (owner 00:33Z: the full width of the bridge, a single cut regardless of the roads under it) -- along its most senior covered road or rail (rail first, then road class) on its own line, chained on along its mapped OSM path; the trench spans the deck between its end lines (`span`, signed offsets across the line) and its floor carries at least every road under it with its shoulders (`need`) (straight on past the map's end) as far as its ramp can need (`floor_min_m + 2 m` at the cap, both curves, 20 m; at most `[tunnel] max_ramp_length_m`); with none mapped, the cut's own axis (the deck's road line, else along its end lines). Per path: the floor's half width (carriageway + `[deck_gen] shoulder_m`), the road's clearance (`model/road_clearance`), cap (`[tunnel] ramp_max_grade`; rail `rail_ramp_grade` 1.25 %), vertical-curve rate (`[road_profile] vertical_curve_k_m` / rail), the STRETCH under every generated deck it passes (ring + `bank_past_edge_m`), the surveyed ground along it (`airport.dem`, every 2 m) |
| cells | `planar/deck_carve.deck_carve` (full map only, after `deck_ground`) | `graded_strip` faces `deck_carve:<deck>:floor/bank/ground`: the floor strip, the banks out to the estimated daylight line (1V:1.5H), the ring and its opened approaches; cut out of every groundside cell they cross, never airside pavement, a runway, a structure, a building pad or a road ribbon; noded every 4 m. The corridor cells the structure pass cut under a generated deck (a ribbon road's tunnel, its deck ground) are the deck's cut too: split along the roads' floors so the mesh carries vertices on every floor edge |
| levels | `constraints/deck_carve.carve_levels`, called from `deck_floor_follow` once the tops are known | ONE floor per cut: `min(lidar road, least underside - clearance)` over every road under it; two decks closer than a ramp up to the ground and back down at the cap are one cut at full depth between them, ramps only on the outer ends (`geom/carve_profile.merged`, owner 00:33Z); the floor band is the deck's span less each abutment's embankment (`model/deck_carve.floor_band`), never narrower than its roads (a wall there); the floor is level under the deck at its lowest underside over the ring; UNDER THE RING the rule is absolute (owner 00:30Z): floor vertices at the deck's floor, the rest on the embankment from the nearer end line (the lidar road its lowest survey within `[deck_gen] level_probe_m` of the stretch: a bare-earth survey reads the bridge's fill under the deck); along each path `geom/carve_profile.floor_profile` -- level under each deck, straight through the gap to the next deck over the same road, ramping out at the cap with vertical curves until it meets the surveyed ground (an LP, `O4_Road_Grade._smooth_grade_changes`); across, a vertex on a road's floor (its half width + 0.5 m snap) takes that floor, off every floor the deepest bank at 1V:1.5H; `min(ground, cut)`; never under the cone (1V:1.5H) the airside constants throw down -- the abutment embankment from each end line (under the ring and its approaches it may stand over the ground; beyond, never) -- except a road's floor, which is never raised: where the road needs it, the bank is a wall. Decks whose cuts share a road are ONE cut, one floor (the deepest). Ramps are designed at 95 % of the cap (the mesh between 4 m-noded floor edges reads a little steeper over a short run). Every groundside vertex on the cut's cells, under the ring / approaches, in a corridor the structure pass cut under a generated deck, or where the cut stands under the ground is a STAGE-2 CONSTANT (`stage2_fixed`); the pins and flat groups on them leave with them (a pin outranks a constant, `solve/rows._reduce`); airside never. A pack deck's corridor outside the generated deck's own ground keeps its floor |

Bars: `tools/deck_probe.py --carve` (library `tools/deck_carve_bars.py`).


### 8.1 Lane lcarve2 (2026-11-20): the deck spans its crossing; one line per cut; the stage-2 airside held

| item | where | what |
|------|-------|------|
| the deck spans its crossing | `planar/deck_width._spans_cover`, fed by `planar/deck_generated._route_pieces` (`_airside_near`, `_on_past`) | each route deck grows (along its route and across it, in place) over every part of its covered roads' carriageway + `[deck_gen] shoulder_m` that runs under AIRSIDE pavement (`airside_stage_roles`) past the piece and touches the ring -- the road's line read 30 m straight on past its cover's ends (a pack junction's corner over the road's edge counts); never onto the pack's own decks, frames or near decks (growth that reaches further onto them is undone: the pack always wins, B1 (c)). Measured KRDU 1.0.565 `-255`: the apron `gapapron:5` stood at its no-bridge level at the deck's side, clearance -5.0 m; KORD `-3879` / `-5312` under `dsf:pol35`'s corner |
| one line per cut | `planar/deck_carve._cut_groups`, `_shared_mains` | decks that each run under the other's path are ONE line: the most senior road crossing every deck of the group (rail first, then the road class; tie by its length under the rings), else the senior road of the group's covered roads; a deck the shared line never runs under keeps its own. Measured KPHX 1.0.565 `o4gen_ebd29231` / `o4gen_eeb202e3` (merged in stage 2, ramping out along two roads, 14-21 %) |
| the floor along each ring | `planar/deck_carve._ring_dense` (`RING_NODE_M` 2 m) | every non-airside structure cell the cut takes over (a corridor, the deck's ground) is split along each generated deck's ring (`_split_structures`, as along the roads' floors), and every cut cell and such structure cell is noded where its edges cross a ring and every 2 m where they run along one (`planar/chords.densify_within`). Measured KJFK `o4gen_a900c332`: a 35 m triangle from `o4gen_da02fc0d`'s ramp stood 0.15 m over its floor |
| the ramp owns its floor | `constraints/deck_carve.carve_levels` | a vertex on a path's floor reads its ground as the higher of its own (`dem_z`) and the surveyed path ground there: a corridor the deck took over had lowered its vertices' ground to the old floor (KRDU `-239`: 15 m flat at the tunnel ramp's floor, then 14.6 %) |
| the stage-2 airside held | `constraints/deck_floor_follow` (`_StageTwo.shadow`, `_stage_two_airside`) -> `solve/stage_shadow.held_levels` (called by `solve/design.solve_design`) | every vertex of a stage-1-role face that stage 2 solves (a plateau's / lower level's apron, a vertex the full map minted, a stage-1 level a rewrite frees; never a road's) is a stage-2 CONSTANT at its level in ONE extra stage-2 solve of the same map without the cut (the final stage-2 set with the pins and flat groups as they stood before the carve -- every other rewrite's rows, the door pads' blend bands among them, kept -- the deck's own fixes, no cut constants), warm-started from the same seed. It supersedes `_near_cut_pins` (deleted: it pinned airside within 60 m of the cut to stage 1's TIN, which the no-bridge solve never does). Measured KORD `pav252#plateau:building31` 0.80 m, KPHX apron / `building18` plateau 0.31 m. Build-time impact: one stage-2 solve more at an airport with a generated deck (KRDU ~30 s) |


## 9. Lane lbridge3 (2026-11-20): the 1.0.566 sim read (RULINGS 2026-11-19s (8))

| item | where | what |
|------|-------|------|
| (a) width | `planar/deck_width._class_width_m`, `[deck_gen] shoulder_share` (0.5) | the deck is the taxiway as drawn (`width_by_class_m`, C 25 m ... F 44 m -- what 1.0.566 read as "exactly taxiway width") plus a half-width shoulder each side: twice it (C 50 m, E 76 m) |
| (b) axis | `pipeline/build` (late stage), `airport/deck_objects._deck_frame`, `pipeline/generated_publication._axis`, `constraints/deck_floor_follow._deck_frame` / `_across_route` | MEASURED KBNA 1.0.566 `o4gen_c944399b`: the build's late (gap) stage replaced the design report and dropped `generated_tops` (only `agp_level` was carried), so the deck was published with no surface and no axis, and the object frame fell to the longest dropped centreline across the ring -- a centreline at the junction on its east end, heading 17.1 deg against its route's 287.8 (the replay, which runs no late stage, read it right). Now: the late stage carries `generated_tops`; the published record always has an axis (off the ring when no surface); the object frame reads the axis, then the carried route, then a centreline; the ring's frame takes end A among the two edges most nearly square to the route |
| (c) riders | (by (a)) | KPHX `-1811` / `-1818` ride the doubled S / T decks (`riders`); the service pavement west of the east decks lies inside the 76 m deck |
| (d) road decks span the cut | `pipeline/road_deck._to_cut` | a road bridge whose axis crosses a generated deck's cut (`DeckBridge.carve` paths) and runs within 30 deg of that deck's axis runs on straight to the deck's end lines; each end at the solved ground there (`generated_publication._surface_at`). MEASURED KPHX `-301` / `-302`: 30 / 33 m mapped, 49 m now (the taxiway decks' 48-49 m between end lines) |
| (d) the ends land | `constraints/deck_carve._landing` / `_road_ends` / `_road_landing`, `[deck_gen] end_landing_m` (3 m) | past each end line the ground stands at the end's level for `end_landing_m` across the deck's width, then falls at the deck bank's slope (1V:1.5H), its corners as a cone; raised over the survey where the ground is lower (the "beyond, never over the ground" clause of section 8 yields here). Never a road's floor or the trench's floor cells; the trench's banks past an end line do land (they ran out to the daylight line beyond it). Within the deck's width the landing is its own even over a neighbour's bank; its corner cone never stands in a cut (between the end lines of a deck within a deck's width). The ground past each end of a generated ROAD deck spanning the cut lands the same way, at the taxiway deck's end level there (`floor_follow_rewrite(..., roads=Airport.road_bridges)`), so the road deck's ends (read off the mesh) stand at taxiway height |
| the top along every edge | `constraints/deck_floor_follow._patch` / `_edge_tin` | the Coons edge profiles read stage 1's vertices on the ring AND its TIN every 2 m along each edge: the filled ring is no edge chain in stage 1, so at twice the width an end read five vertices over 76 m (KPHX `o4gen_6494eed8`: the top 0.9 m under the pavement past its end) |
| (a) neighbours part | `planar/deck_width.parted` (called by `planar/deck_generated._route_pieces` over every piece's decks), `[deck_gen] parallel_gap_m` (3 m) | two generated decks stand at least `parallel_gap_m` apart: both give up shoulder a metre a side at a time about their own centrelines, never below their taxiway's width (19s (3) (b)); route decks merge only where their TAXIWAYS overlap (`_core`), and an end's reach to the pavement reads the taxiway's width, not its shoulders. MEASURED KRDU at twice the width: two taxiways 64 m apart over one curving road, their 76 m decks overlapping 422 m2 |
| admission reads the taxiway | `planar/deck_generated` (`_route_pieces` hands each deck's `core`; `overhead_decks` / `_blocked` read it), `planar/deck_width.cores` | the pack's refusals (a pack deck standing ON the crossing, a frame over it) read the deck's taxiway plan, never its shoulders: MEASURED KRDU at twice the width, the shoulders reached the pack's `dsf:obj140` and read it as standing OVER the -17013 / -454 crossings it stands ON (refused at the class width), so two decks were admitted that cut a 19.6 % ramp through a tunnel ramp |
| road deck end levels | `pipeline/generated_publication._surface_at` | the mesh's own surface (the map face holding the point, triangulated on its ring), the survey off every face; a road deck runs to the end lines of the NEAREST generated deck whose cut it crosses (KJFK `-833` ran to the farther of two decks over one road) |
| the bar reads the published top | `tools/v2_solve_replay.py` (`generated_tops` in the solved pickle), `tools/deck_carve_bars._top` | the clearance bar reads the deck's published Coons top; read again off the final airside on the ring it missed the shoulders (KPHX `o4gen_6494eed8` read 4.77 m of 5.0 for 5.32 m) |


## 10. Lane lcross20 (2026-11-20): one decision per crossing, width, gaps, piers, markings (RULINGS 2026-11-20a; owner 14:36Z-15:30Z)

Evidence: `tools/v2_solve_replay.py --replay ... --from classify` on the
lbridge2 captures (KRDU KJFK KORD KPHX KBNA KIAH) and a new KMCO capture,
base `2e605bea7` against the lane head; bars `tools/deck_probe.py --carve
--piers` (library `tools/deck_carve_bars.py`: `end_gaps`, `pier_bars`,
`road_deck_bars`), movers `tools/airside_value_delta.py` against the
`--no-bridge` arm. No tile build (17r).

| item | where | what |
|------|-------|------|
| 1 one decision | `planar/deck_takeover.one_decision` (replaces `attach` at `planar/build`) | the walled frames this build hid (19p) are carried as before; then every OTHER pack placement drawing a DECK over a crossing we generated -- its up-facing solid faces a clearance (`[bridge] clearance_minimum_m`) over its own lowest solid and no higher than the deck's depth plus that clearance over its ground, over the deck by `min_area_m2` and over `pack_cover_share` of its covered roads -- is HIDDEN in the pack copy with its co-placed frame mates (`deck_bridge.co_placed`: the `_luz` lights). A pack HARD deck is never one (the deck law seats it: it refused the crossing, or passes over it). What still draws a deck-level top under a generated footprint is recorded on the deck (`DeckBridge.pack_under`), published (`pack_bridge_under_deck`) and counted by the census family `pack_bridge_under_deck` (check_grade + v2 verify). MEASURED KMCO: `puente.obj` (`deck_kind` candidate, no hard deck, 980 m wide) hidden with `puente_luz.obj` |
| 2 width | `planar/deck_width._end_runs` / `_run_at` / `_between` / `_pavement_width` | the taxiway (taxi / runway family) pavement run `[deck_gen] end_width_probe_m` past each end, never past half way to a neighbouring taxi route; the NARROWER end, never under the taxiway twice; a run over `end_width_broad` x that width (an apron) or no run never widens. MEASURED KPHX taxiways S / T: the airport pavement read 207 m (apron), the taxiway pavement 98-137 m (both taxiways): airside moved 3.5 m until the neighbour bound |
| 3 floor nodes | `planar/deck_carve._need_strips` | every cut cell and deck-ground cell split along each path's `need` strip (every road under the deck with its shoulders, the least floor stage 2 lays): KRDU `o4gen_80bc82b9`'s ground face had no vertex within 10 m of `-254` |
| 5 ends land flush | `constraints/deck_carve._flat_landing` / `_road_flat`; `planar/deck_carve._landings` | past each end line within `end_landing_m` and the deck's width plus `edge_margin_m`, every groundside vertex is a stage-2 CONSTANT at the end's level (up or down); the landing strips are noded in the cut, deck-ground and plain ground cells; a road deck's end crest lands too |
| 8 piers | `pipeline/generated_publication.mapped_under`, `_ground_min`; `airport/deck_objects._structure`; `airport/deck_structure._piers` | every column reaches the deepest solved ground within 5 m of the ring (`ground_m`), the rest buried; columns stand clear of every mapped road / railway carriageway under the ring (whole ways, round caps) |
| 9 riders | (by construction) `planar/deck_gen_pairs.riders` | a rider widens the deck on its own side only (union); twin added |
| 10 / 12 markings | `airport/deck_obj8` (`TOP_STEP_M`, `_tris` on a 2 m grid, `_dense`, `_gridded`, `surface_of`), `[deck_gen] film_lift_m` / `paint_lift_m` 0.001, `deck_objects._FILM_STEP_M` 0 | the slab top was two planar triangles on a four-corner ring while the markings were stationed on the Coons patch: buried up to 0.63 m (KIAH, 5 of 11 decks) or floating 0.29 m. Now the slab is gridded at 2 m, every overlay stationed every metre on the DRAWN top (`surface_of`), 1 mm over it; on top by draw order: the slab (group `objects`), the films (`ATTR_layer_group objects 1`), paint / lines / marks (`objects 2`), a line's layers in batch order |
| 11 road decks | `planar/deck_carve._road_spans` / `_road_stretch_decks`; `pipeline/road_deck._surface_from` | a road deck over a generated deck's cut is a stretch of that deck on every path (the floor level under it, the ramps start past it); its top is the taxiway deck's top at the same stations (a published Coons surface) |

Not done here: item 4's KJFK `o4gen_e74205d8` (the road `-6514` runs
obliquely under two decks; its end A sits over `6f1f538c`'s trench), item 6
beyond the road-deck end crest, item 13 (KIAH JFK Blvd: the carriageways'
RB crossings never become covered roads -- the structure pass bores
`-5106` / `-7074` as one tunnel each under the pack's paved area; a split at
the mapped taxiway bridges was tried and deleted: it never fired).


## 11. Lane lcross21 (2026-11-20): the lcross20 misses, LFPO deck level, LFPG (RULINGS 2026-11-20b-20f)

Evidence: replays `--from classify` on the lbridge2 captures (KRDU KJFK KORD
KPHX KIAH), lane captures of KMCO and LFPO, the l1717 LFPG capture; base
`43a0fbf60` against the lane head; bars as in section 10.

| item | where | what |
|------|-------|------|
| 1 KIAH JFK Blvd | `planar/structure_underpass.underpass_bores`; `planar/deck_generated._whole_cover` / `_open_between`; `planar/road_bridge_gen._bridges` | (a) a mapped taxiway bridge bores the road under it along its centreline ribbon wherever its deck CELL's stations were refused (a junction blob over the cap): KIAH `-414` / `-120` read 23 stations north of the carriageways and 0 roads; (b) a covered stretch over `max_cover_m` that two or more MAPPED bridges cross is no tunnel: each bridge's piece is its own deck, the paved stretch between them opened with the decks' rings (`approach`); (c) a mapped road bridge whose lower road runs into a generated deck's cut needs no survey witness (`-1342`: 2.2 m of 5 surveyed). KIAH: 2 taxiway decks + 1 road deck → 4 taxiway decks (RB, RA over each carriageway) + 2 road decks (`-1342`, `-1337`) |
| 2 KJFK ramp | `planar/deck_carve._shared_mains` (one line per cut when decks share one road), `constraints/deck_carve` (`_ROAD_FLARE_M`: a road's own vertex within 5 m past a floor band takes the floor, unless a deck end's landing reaches it) | `o4gen_6f1f538c` / `o4gen_e74205d8` ran along `-6514` on lines 14.8 m apart, each chained from its own clip: two floor profiles where they disagreed, a 12 % step |
| 3 end gaps | `geom/coons_patch._cornered` (the four profiles agree at each corner), `constraints/deck_carve._flat_landing` (the corner lands beside the deck within the ring margin of its end) | KRDU taxiway d: the end and side profiles 0.11 m apart at a corner |
| 4 road-deck ends | `planar/deck_carve._split_structures(..., ground=True)` (road ribbons noded on the landing strips) | KPHX `-301`: no ribbon vertex within 2.5 m of the deck end |
| 5 20f | `planar/deck_width.parted` / `_facing` / `_band` | the gap gives way: each deck narrows only on its facing side, a metre at a time while the gap needs it, never inside its taxiway's paved band (the narrower end run holding the taxiway, never under the class width) |
| 6 LFPO level | `planar/covered_ground` (a mapped tunnel under a generated deck reads its cut to the deck's floor depth; stage 1's covered ground covers a withheld deck's whole ring), `constraints/deck_floor_follow._in_structure` (the deck's top never reads a structure's cut) | LFPO `o4gen_104efd62` over mapped tunnels (trams `-28859` / `-24950`, trunks `-34628` / `-3715`, all `tunnel=yes layer=-1`): stage 1 kept their trench and ramps under the withheld ring; the top's edge profiles read them, 6 m under the 86 m terrain at both ends |
