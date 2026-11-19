# Airside-first generated bridges (lane lbridge2, 2026-11-19)

Law: `docs/RULINGS.md` 2026-11-19p, 19r, 19s (1)-(4). A deck WE generate
(`planar/deck_generated`, `witness == "generated"`) never moves airside.
Pack decks we keep (authored height) keep today's coupling (19s (4)); a pack
walled multi-bridge frame is still hidden by `planar/deck_takeover` and its
crossings become our decks (19p).

## 1. Pipeline order

| # | stage | what happens to a generated deck |
|---|-------|----------------------------------|
| 1 | planar, FULL map | the deck is derived: one per carried taxi/runway route, a parallelogram whose sides run along the route and whose ends are the cut's crests (parallel to the road); WIDTH = the route's width class, taxiway + shoulders (`[deck_gen] width_by_class_m`, ICAO Annex 14 §3.9.3 / §3.10.1), never the pack pavement or the cut |
| 2 | planar, STAGE-1 map (`model/stage_one.from_full`) | the deck is WITHHELD (`planar/deck_airside`): no deck record, no ring cut, no deck ground, no survey keep-out, no bore under it; its ring is FILLED with the carried route's pavement role (the taxiway spans the road on its own grade law) and its covered roads are covered ground (`planar/covered_ground`: the bare-earth trench is masked out of `Vertex.dem_z`) |
| 3 | stage 1 solve | the airside levels: the NO-BRIDGE SOLVE. Stage 1 is derived whenever the full map carries a generated deck, ribbons or not |
| 4 | between the stages (`stage2_rewrite`) | per deck, the DECK SURFACE (`constraints/deck_surface`): a Coons patch of the stage-1 levels along its four ring edges (exact on each edge). Every full-map airside vertex on or inside a generated ring that has no stage-1 twin is FIXED at that surface (`stage2_fixed`); every floor pin under the deck drops to `min(planar floor (lidar road), surface min - thickness - clearance)` |
| 5 | stage 2 solve | the cut, its banks and the roads in it, with every airside vertex a constant: the carve can never move airside |
| 6 | publication / object stage | the deck record carries the four edge profiles (absolute m) and its axis; `airport/deck_objects` draws the top as the same Coons patch, so each end is flush by construction; the kerb (lip) runs on the edges parallel to the route only |

## 2. Data handed on

* full map -> stage 1: `PlanarMap.decks` (generated ones withheld by
  `deck_airside.withheld`), the full map's anchors (generated ones carry no pin).
* stage 1 -> rewrite: `StageOne.levels1` (stage-1 ids -> solved level) and
  `StageOne.pm` (its vertices on each ring).
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
