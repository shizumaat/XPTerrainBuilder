# #1918 — hidden objects and the terrain solve (consumer census)

Lane l1918, base `5efc824e7` (test-536). Rule under test (brief; RULINGS
2026-11-06d (1)/(6), 2026-11-13q, 2026-11-15e/h): an object the pack hides
leaves the terrain solve — it owns no ground and pins nothing.

## Two hides, one rule

| hide | where decided | what the readers see |
|---|---|---|
| A7 concave cut shell, rim at the ground (`hide_concave_shells`) | `airport/object_floor._concave` | `ObjectFloor.hidden` → `owns_ground()` false |
| ground shell no seat lays flat (#2056), or a terrain object the user hid ("Hide terrain objects", ticked by default since 15h) | `airport/obj8.place` → `TerrainModel.ground == "hidden"` | a `terrain_feature`: never read for below-grade witnesses; row written `HIDDEN_SEAT` |

At LGAV both fire on one object: `Trench_06` (dsf:obj618, 520,625 m²) is a
hidden ground shell AND an A7 hidden concave shell.

## Census (every reader of shells / pack terrain objects)

| # | reader | consults the hide? | terrain/road effect at base | verdict |
|---|---|---|---|---|
| 1 | `planar/object_floor_cells.add_object_floor_cells` (cut cells, knives, keep-outs) | yes (`owns_ground`) | none | lawful |
| 2 | `planar/structures` owners (structure cells trimmed to floors) | yes | none | lawful |
| 3 | `object_floor_cells.floor_mouths` (bore mouths at a floor) | yes | none | lawful |
| 4 | `object_floor.floor_portals` (portal pins) | yes | none | lawful |
| 5 | `constraints/object_floor.object_floor_pins` | implicit (no cells → no faces) | none | lawful |
| 6 | `object_floor.read_object_floors` (floor / shell / walled pit, raw geometry) | A7 only — NOT the terrain-model hide | latent: a user-hidden or ground-shell-hidden object read as a drawn floor would own ground | FIXED: `ground_shell.hidden_by_pack` marks it hidden |
| 7 | `object_floor_cells.object_floor_stage` object-cut corridors (`object_cut.read_shells`, raw geometry) | dropped only when read as a floor | latent: a hidden object's cut not read as a floor would cut the terrain | FIXED: a corridor stated by a `hidden_by_pack` placement is dropped |
| 8 | `airport/visible_cut` + `planar/channel_depth` (channel floor, sides, reach) | yes — reads the hidden shell on purpose | the shell classifies members (cover / on the cut / buried by its surface); its floor plates set the floor LEVEL and a side's floor edge; its footprint bounds the axis run-on | ruled witness use (06d (1) "at most a witness of the cut's extent and depth"; spec object-gate-member-floors §4; 13q (2)). The brief's rule "no witness to any reader" would reverse it: owner Q1 |
| 9 | `planar/floor_decks` (`has_footprint`) → `constraints/deck_lines` end lines | yes — witness | deck pieces over the hidden shell seated flush with the pavement at both end lines (06d (5)) | ruled witness use (06d (1)); the decks are visible objects |
| 10 | `object_floor._deepest` (A4) | no | a hidden deeper shell withdraws the shallower liners (Trench_01/02 own none; drawn) | ruled (06d (1) names A4). Skipping hidden shells in A4 makes the liners A7-hidden too (rim at the ground 100 %) and drops them from the DSF: 13q (1)'s object-side round, not this one |
| 11 | `object_floor.seat_records` cut ring; `rebake_inputs._keep_cut_rings` | witness | object stage only (frame decks seated over the cut) | no terrain reader |
| 12 | `terrain_model.seat_records` (terrain cut under a model, 13k) | yes (hidden → no `cut`) | none | lawful |
| 13 | `object_ground`, `road_profile.object_sampler`, `planar/build` (`seat_by` models) | n/a — bridged ground is never hideable | none | lawful |
| 14 | `ground_shell.off_the_shell` (riders of a hidden ground shell) | yes | riders read on our ground, no pit | lawful |
| 15 | basins / pits / tunnels reading `below_grade` / `witnesses` | yes (a hidden model is a `terrain_feature`, never read) | none | lawful |

Measured on the LGAV capture at base (`v2_solve_replay --capture LGAV`):
no planar face carries the hidden shell's id; the channel's region and crest
ring follow the shell's outline for 10 m / 60 m of 6.2 km (0.2 % / 1.0 %);
inside the channel (crest ring + 20 m) the groundside census is 25
`within_shape` (≤ 10.06 % on a 9.5 % cap) and 8 `road_cross_section`
(≤ 0.69 m) rows; `tunnel_trench` 0. SBGL (`Objeto Terreno`, a hidden ground
shell): no structure, face or floor carries it. With rows 6 and 7 fixed the
LGAV replay patch body is identical (045f85bd84a6 both arms).

## The drawn issue site (owner's installed tile, built 2026-11-14 19:36, engine 1.50.1902)

`drawn_gate.py LGAV --tile +37+023 --patches <data>/Patches --site issue=37.927,23.935,200 --site sw=37.9235,23.932,200`:
mesh PASS, patch→drawn PASS (0 of 27,472). Two FAILs, neither the hidden
shell's:

* objects: channel:0 floor/ledge feet float, 20 feet > 0.3 m, worst +1.76 at
  37.927254, 23.936271 — 2.7 m outside the crest ring on the right side
  (the per-side channel width class lgavtrench left open; 13q (1)'s member
  seat path, not implemented).
* roads: way -886 (`small_roads:-886`, service) steps 0.62 m at 37.927345,
  23.934221 against the `building24` pad — 43 m outside the hidden shell,
  66 m from the channel: a pad/road joint.

## Owner questions

* Q1. 06d (1) keeps a hidden shell as a witness of the cut's extent and
  depth (row 8). The brief's rule says a hidden object is no witness to any
  reader. Dropping the shell's floor plates and footprint makes the floor
  level the lowest member foot (a buried pile then sets the floor: the
  ratified spec twin `_trench` fails) and the axis run-on must be bounded by
  the members alone. Keep the ruled witness use, or remove it?
* Q2. The two drawn FAILs above are other mechanisms (per-side widths / 13q
  (1); a pad/road joint), each its own round.
