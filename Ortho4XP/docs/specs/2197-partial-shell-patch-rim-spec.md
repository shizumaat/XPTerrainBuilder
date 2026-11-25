# Spec #2197 round 2 — partial shells: the narrowed population, and the patch half (lane lpartshell2, 2026-11-25)

Base `claude/lpartshell` 34c5814d2 (round 1, not merged) on `claude/project-thread-ddpu46` 302511b0c.
Owner 2026-11-20T14:20Z (ELLX, verbatim): "the terrain should meet it's outer edges flush all the way around so you can't see under it." Owner 2026-11-22T16:25Z (LDSP): "we need to recognize that and seat and grade things so it blends into the natural terrain correctly."

Round 1 recognises a PARTIAL SHELL (`airport/ground_rim`: an origin set whose ground sheet holds ≥ 0.5 of its plan and of its outer rim and models ≥ 5 m of relief beyond a plane), seats it rigid and grades the FREE tile raster to its rim stations (`airport/rim_grade`). Two defects keep it from merging: the population is too broad (§1), and the rim stays open where it lies inside the airport patch, whose postings the tile never moves (§2).

## 1. Narrowing (recognition)

MEASURED — see §4 table.

## 2. The patch half: a groundside face touching a rim takes the rim

### 2.1 The rule
Per recognised set (`constraints/rim_pins.rim_sets`: every `TerrainModel.rim` of `airport.terrain_models`, once per set), every vertex of a GROUNDSIDE VALUE face (`constraints/groundside.groundside_face_roles`: `groundside_pavement`, `service_road`, `service_junction`, `parking_lot` — car lots included) that

* no face of any other role carries (an airside face, a strip band, a structure ramp: airside is king; a structure's rim is its own law), and
* stands on no open edge of the patch (the seam's `seam_pins` and the coverage edge's `roads.coverage_edge join` own those),

is pinned (`Pin`, generator `rim_pins`, ruling head `#2197 a groundside face meets a partial shell's ground rim`) at

1. UNDER THE SHEET — its plan point on a sheet cell: the author's ground there (`_RimSet.sheet_at`, the sheet's `z0 + top` kept on the record) less `geom/terrain_deck.UNDER_M` (0.1 m): the lot stands just under the shell's ground, never through it;
2. OUTSIDE THE PLAN within the stand-off reach (`constraints/gap_follow.reach_m`, the distance a groundside face welds to a standing ring across) of a rim station: the stations' inverse-distance-squared mean (the 8 nearest, `rim_grade`'s own target) less `UNDER_M`;
3. anywhere else (under the shell's buildings or decks, i.e. inside the plan off the sheet; beyond the reach): no pin. The face follows its own law from its pinned vertices (lot / road caps, 25e's ground-follow within the 5 % cap).

The rim is the AUTHORITY, ONE-WAY: the object never moves (round 1's rigid seat), our groundside conforms.

### 2.2 Airside never moves
The head is registered in `[design] groundside_pin_rulings` (`law/emit.toml`): §20b stage 1 treats every rim-pinned vertex (and its rigid class) as FOREIGN (`solve/design_stage._groundside_pinned`), so no lot / road / frontage row footed on it enters the airside problem — the airside solves free and the lot conforms in stage 2 (10-02v (1), #143). A pin whose rigid class contains an airside vertex is not groundside (design_stage's own rule) — `_candidates` never mints one on a vertex an airside face carries.

### 2.3 Conflicts yield
The head is registered in `[design] yielding_pin_rulings`: a rim pin its own hard rows cannot hold (a lot or road ceiling from a senior level, a seam reach) is released to a design target at its own value and REPORTED (`DesignReport.pin_yield`), as the coverage-edge join is (`solve/pin_yield`, 27a (10)). Never infeasible.

### 2.4 Coordination with RULINGS 2026-11-25e (lots follow their ground within 5 %; lane llot)
A lot touching a rim TAKES THE RIM: its rim-pinned vertices are constants; 25e's ground-follow applies to the lot's other vertices, which grade from the pinned ones within the lot's 5 % cap. Where the rim and the lot's DEM disagree by more than the cap allows, the pin wins at the rim (it is a constant) and the cap row carries the residual (one-sided penalty) — the visible edge is flush, the lot's body grades away.

### 2.5 Consumer census (RULINGS 2026-08-30l): region = groundside vertices under a recognised sheet or within the stand-off reach of its rim

| # | Consumer | Reads | Ruling here |
|---|---|---|---|
| 1 | `airport/ground_rim` (load, `obj8.read_placed_objects`) | the origin set | DERIVATION SITE: recognition + `sheet` surface on `_RimSet` |
| 2 | `terrain_model.seat_records` / object stage | the set's rows | rigid `OBJECT_MSL` at `z0 + lift`; unchanged |
| 3 | `auto_patch/terrain_cut_stage._grade_rims` → `rim_grade` (tile raster) | free postings | unchanged: never a patch posting (frozen) — the patch half is this spec |
| 4 | tile DUMMY constrained lines (`_rim_lines`) | rim rings | unchanged |
| 5 | NEW `constraints/rim_pins` | groundside value-face vertices | THE PINS (§2.1) |
| 6 | `solve/design_stage.stage_split` (`_groundside_pinned`) | pin ruling heads | rim pins FOREIGN to stage 1 (§2.2) |
| 7 | `solve/pin_yield` | yielding heads | rim pins yield on own conflict, reported (§2.3) |
| 8 | `constraints/groundside.groundside_ramps` (apron edge → groundside 5 %) | groundside ring vertices | row stays; footed on a pin it is a stage-2 row only (foreign) — the apron is never pulled |
| 9 | `constraints/pad_frontage_gs`, `roads`, `road_ramp`, `road_cross_section`, `pavement_cap`, `public_road_release` | road / lot vertices | rows stay; a pinned vertex is a constant they grade from |
| 10 | `constraints/car_lot_follow`, `pipeline/lot_follow` (late / follower stages) | lot vertices | a pinned car-lot / lot vertex is a constant (a pin outranks a stage substitution, `solve/rows._reduce`) |
| 11 | `solve/design_ground` ground datum | strip vertices (no pavement) | untouched: rim pins are never on a strip vertex |
| 12 | planar `Vertex.dem_z` substitutions (`object_ground`, `bridge_ground`, ...) | `dem_z` | untouched; the pin overrides only the solved value |
| 13 | seam pins, coverage-edge join pins | open-edge vertices | senior: rim pins never mint on an open edge |
| 14 | emit / heightfield | solved z | emittable: a pin is a vertex value, no new geometry |

### 2.6 Out of scope (named, not done)
* No rim breakline is inserted into the planar map: where a groundside face's ring crosses the rim far from any vertex, the face's own triangulation interpolates between pinned and free vertices (measured residual in §4).
* Ground strips (zone bands: `graded_strip`, clearances) are airside-side roles and are never pinned.

## 3. Build-time impact
`rim_pins`: one KD-tree query per set over the groundside vertices; none without a recognised set (every airport but the hits in §4). Recognition adds two shares to `ground_rim._recognise` (vectorised over the plan raster already built).

## 4. Measurements
FILLED IN BELOW.
