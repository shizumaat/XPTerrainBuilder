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
| record | `planar/deck_carve.deck_paths` -> `DeckBridge.carve` (`model/deck_carve.DeckCarve`) | per generated deck: its EVIDENCE (OSM road / rail per covered way, hidden pack frame, OSM bridge tag, lidar trench) and its PATHS -- each covered road or rail chained on along its own mapped OSM path (straight on past the map's end) as far as its ramp can need (`floor_min_m + 2 m` at the cap, both curves, 20 m; at most `[tunnel] max_ramp_length_m`); with none mapped, the cut's own axis (the deck's road line, else along its end lines). Per path: the floor's half width (carriageway + `[deck_gen] shoulder_m`), the road's clearance (`model/road_clearance`), cap (`[tunnel] ramp_max_grade`; rail `rail_ramp_grade` 1.25 %), vertical-curve rate (`[road_profile] vertical_curve_k_m` / rail), the STRETCH under every generated deck it passes (ring + `bank_past_edge_m`), the surveyed ground along it (`airport.dem`, every 2 m) |
| cells | `planar/deck_carve.deck_carve` (full map only, after `deck_ground`) | `graded_strip` faces `deck_carve:<deck>:floor/bank/ground`: the floor strip, the banks out to the estimated daylight line (1V:1.5H), the ring and its opened approaches; cut out of every groundside cell they cross, never airside pavement, a runway, a structure, a building pad or a road ribbon; noded every 4 m |
| levels | `constraints/deck_carve.carve_levels`, called from `deck_floor_follow` once the tops are known | ONE floor per deck: `min(lidar road, least underside - clearance)` over every road under it (the lidar road its lowest survey within `[deck_gen] level_probe_m` of the stretch: a bare-earth survey reads the bridge's fill under the deck); along each path `geom/carve_profile.floor_profile` -- level under each deck, straight through the gap to the next deck over the same road, ramping out at the cap with vertical curves until it meets the surveyed ground (an LP, `O4_Road_Grade._smooth_grade_changes`); across, a vertex on a road's floor (its half width + 0.5 m snap) takes that floor, off every floor the deepest bank at 1V:1.5H; `min(ground, cut)`; never under the cone (1V:1.5H) the airside constants throw down -- the abutment embankment from each end line. Every groundside vertex on the cut's cells, under the ring / approaches, or where the cut stands under the ground is a STAGE-2 CONSTANT (`stage2_fixed`); airside never |

Bars: `tools/deck_probe.py --carve` (library `tools/deck_carve_bars.py`).

