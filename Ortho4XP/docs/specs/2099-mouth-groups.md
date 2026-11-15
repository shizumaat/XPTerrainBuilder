# #2099: a tunnel mouth made of touching pieces is one object group

Lane lmouth2099 (Opus), 2026-11-15. Spec author and implementer (master brief).
Law: owner ruling 2026-11-15T16:07Z "Like other areas, tunnel mouths made of multiple
touching pieces need to be treated as an object group"; RULINGS 2026-10-22o (connected
objects move as one group), 2026-10-30a (1)/(2) (a hard deck's ONE zero, its frame's
bottom is the road), 2026-11-03T23:21Z (one zero per unit: a deck's frame takes its plate),
2026-08-30l (consumer census), 2026-10-05e (no airport-specific code), 2026-11-13g (drawn gate).
Paths under `Ortho4XP/src/auto_patch_v2/`; lines are claude/test-534 149313605.

Owner symptom (GlobalArt CYYZ): "the tunnel mouths came apart because we didn't recognize
the wing walls were part of the mouth and they ended up sitting on top of the cut instead of
down in it and defining the mouth".

## 0. Measured (capture lmouth/CYYZ.pkl at c5cdd0c8c, corpus refreshed this round)

Pack geometry (authored y over each object's zero; plan half-width = largest inscribed
half-width of the genuine solids' plan):

| mouth | box | box y | wings (placement, y, half-width, runs out of the box, anchor offset) |
|---|---|---|---|
| T 43.669811,-79.626206 | obj10880 `Bridge_Taxiway_T` | -7.51..+1.36, hard deck flush at 0 | obj10877 `_T_c` -1.40..+7.23, 0.91, 25.7 m, 8.8 m / obj10878 `_T_b` -0.53..+7.20, 0.69, 195.7 m, 8.8 m / obj10879 `_T` -1.10..+7.25, 0.68, 131.4 m, 2.4 m |
| M 43.666723,-79.624935 | obj10884 `Bridge_Taxiway_M` | -0.05..+9.24, hard deck 6.99..7.98 | obj10886 `_M_b` -1.69..+6.21, 0.75, 23.3 m, 94.2 m / obj10888 `_M_d` +0.01..+7.22, 0.75, 14.6 m, 88.2 m |
| FA 43.678684,-79.638869 | obj10883 `Ponte_FA` | -0.04..+6.54, hard deck | obj10881 `Bridge_Infield_b` -9.39..+5.49, 0.84, 177.7 m, 0.2 m / obj10882 `Bridge_Infield` -0.56..+5.29, 0.42, 80.2 m, 0.2 m |

* CONTACT (step 1 of the brief): on the real DEM and OSM, with each placement at its own
  per-anchor zero (`contact.partition`, `DEM(anchor) + agl + y`), every wing above is in
  direct ε-contact with its box in the LOAD partition (`PackPartition.contacts`, 1-2 part
  edges each). The real zeros KEEP the contacts. No fence post reaches a group: the two
  `Postinho_Cerca` strays the scout saw at zero anchor are not in the real components.
* READERS: all three boxes are HARD-DECK BRIDGES (`planar/deck_bridge`, `PlanarMap.decks`,
  family `taxi`), none a portal (a hard deck is never one) and none an entrance.
  `DeckBridge.bottom_y`: T -7.51 (its own walls), M -0.05, FA -9.39 (the co-placed
  `Bridge_Infield_b`'s footing near the box). The deck's seat is its PLATE
  (`pipeline/rebake_inputs._deck_plate`: zero = the solved surface at its end-line stations
  less its top).
* FA's wings stand 0.2 m from the box's anchor at its heading: CO-PLACED, so they are
  already `DeckBridge.members` and `_unit_members` gives them the deck's own plate (offset 0:
  one authored frame). FA is the control of this round, not a change.
* T's and M's wings are at foreign anchors (2.4-94 m, 0.5-6.3 deg). Nothing groups them
  (`hanging_objects._co_placed`, `walled_pit._in_pit`, `deck_bridge.co_placed` all need one
  anchor). Each stands on its own ground: T wings' zero = DEM at their anchors
  166.87-166.96 against the mouth's floor 158.97 (deck zero 166.48 + bottom -7.51) -- the
  walls stand 8 m over the cut, their tops 7 m over the cover. M wings 157.61 / 156.95
  against the floor 155.50: 1.4-2.1 m over.
* Height cannot come from contact: at T the wings slide 8 m down a vertical face and stay in
  contact. The seat comes from the mouth's own floor.

## 1. The group (one reading: `airport/mouth_group.py`, new module)

REUSE: the group is the LOAD partition's ε-contact graph (`PackPartition.contacts` over
`member_object`), read across anchor families, as `adapted_riders.touching_adapted` reads it
inside one (#1726). No second contact test, no second grouping.

M1-M3 THE MOUTHS (`mouths_of(pm)`): the placements a planar reader took as a mouth, each
with its FLOOR y (the road under it, in its own frame):
* M1 a hard-deck bridge (`PlanarMap.decks`): floor y = `DeckBridge.bottom_y` (the frame's
  bottom, the level the cut is made to; 30a (2)).
* M2 a roofed portal seated at its pinned floor (`Tunnel.portal_seat` of two): floor y 0
  (its zero IS the floor).
* M3 an entrance face (`Tunnel.portal_seat` of four): floor y = `Tunnel.mouth_z` less the
  zero the seat states (= the face's bottom y).
* NOT a mouth this round (§5): a hanging cover or shell (`object_cut.ObjectCut`) that no deck
  reader also takes, an object floor's frame (`object_floor`), a deck stack.

THE CANDIDATES: the placements in the mouth's ε-contact component (union-find over the
contacts between placements; a LINE part -- a fence, a kerb, `Part.line` -- joins nothing),
not a mouth, and seated by no other rule (`taken`: a plate entry, a whole-row record, the
excluded / storey-shell / terrain-model rows: one authority per row).

W1-W3 THE WING WITNESS (`wing_refusal`, every number a law value):
* W1 A WALL: no `ATTR_hard_deck`, and no part of its genuine solids' plan as thick as
  `[tunnel.object] wall_face_max_thickness_m` (2.0; `plan.buffer(-1.0)` is empty). Measured
  0.42-0.91 for the seven wings, 7.6-13.2 for the three boxes.
* W2 A WALL'S HEIGHT, NO TALLER THAN THE MOUTH: its top y >= `shell_floor_min_m` (2.0) and
  <= the mouth's top over its floor + `plate_bin_m` (0.5). (The scout's draft "within
  plate_bin_m of the mouth's depth" is REFUTED by M: deck 7.98 over its floor, wings 6.21 /
  7.22.)
* W3 IT RUNS OUT OF THE MOUTH: its plan reaches `entrance_skirt_m` (3.0) or more beyond the
  mouth's plan, and nowhere farther than the NEW key `[tunnel.object] wing_reach_max_m`
  (250.0; CYYZ's longest wing 195.7 m) -- the plan-size cap.

ONE HOP: a candidate passing W1-W3 is a wing when its plan comes within `[rebake]
contact_epsilon_m` of the mouth's plan or of a wing already joined; a chain runs only
through wings. A wing joins one mouth (the first by id). Every refused toucher is one log
line (`[ICAO] mouth groups (#2099): ...`).

## 2. The seat: the mouth's own, at its floor

A wing's zero = the mouth's zero + the mouth's floor y. It is carried by the seat the mouth
ITSELF has, so the group cannot come apart (one authority, the mouth's):
* S1 a PLATE-seated mouth (a hard-deck bridge, M1: `tunnel_objects[mouth] = (y, stations,
  clearance, kind[, anchor zero])`, zero = surface at stations - y): the wing takes the same
  plate with `y - floor_y` and an anchor zero `+ floor_y` (`wing_plates`). The object stage
  reads it like FA's co-placed members' (class A: `airside_deck_seat._plate_zero`, every
  body of the wing's unit at that zero; CYYZ's wing units hold wings only).
* S2 a ROW-seated mouth (M2/M3: a `PORTAL_SEAT` / `ENTRANCE_SEAT` record): the wing gets a
  whole-row `PORTAL_SEAT` record, `datum "mouth group"`, `elevation` = the mouth's (lowest)
  record elevation + floor y, `led_by` the mouth (`wing_records`); excluded from the plan
  and written as `OBJECT_MSL` by `terrain_shaped.row_seats`, like `portal_frame_records`'.
  `portal_frame_records` runs FIRST: its co-placed footprint-led pieces are `taken`.
Predicted CYYZ: T wings zero 158.97 (8 m down), M wings 155.50 (1.4-2.1 m down), FA none.

## 3. Consumer census (RULINGS 2026-08-30l) -- every pass that reads these placements

| # | consumer | reads | ruling this round |
|---|---|---|---|
| 1 | `pipeline/rebake_inputs._plate_seats` / `_unit_members` | plate entries | CHANGED: S1 adds a wing's plate after the co-placed members' (they stay `taken`) |
| 2 | `terrain_shaped.portal_seat_records` / `portal_frame_records` | portal records | UNCHANGED; S2 adds wing records after them |
| 3 | `rebake_inputs` `excluded` (PORTAL_SEAT rows) | records | UNCHANGED code: S2 rows are PORTAL_SEAT, excluded with them |
| 4 | `airport/rebake_screen.take` / object step plan | plates, records | UNCHANGED code, carries the new entries |
| 5 | `airport/rebake_plan._with_deck` | plate -> `Member.plate_y/plate_stations/plate_kind/anchor_zero` | UNCHANGED |
| 6 | `airport/placement_plan` -> `airside_deck_seat.airside_frame` / `_plate_zero` / `_is_the_bridge` / `airside_deck` | the wing unit's plate | UNCHANGED code; a wing unit holding a body on a building pad is refused as today (counted `airside_deck_in_a_building_frame`) |
| 7 | `terrain_shaped.row_seats` | S2 records | UNCHANGED (one authority per row: a split row drops its record, as today) |
| 8 | `open_frame_seat.group_zero` (22o) / `footprint_unit.plan_unit_datums` | connected units | UNCHANGED: class A's frame seat is the wing body's datum; measured in the closing build |
| 9 | `planar/deck_bridge` members / `bottom_y` / `wall_faces` / the cut | the deck frame | UNCHANGED: wings do NOT join `DeckBridge.members` (a foreign-anchor wing's y frame is not the deck's; `wall_faces` reads co-placed y). The cut stays the deck's and the road's (§5 residual) |
| 10 | `planar/entrance_skirt`, `portal_objects._wing_plan` (R4) face_plan | a pin's own object | UNCHANGED: no pin at CYYZ; a portal's foreign wings in its top are §5 |
| 11 | `trench_objects.mouth_portals` | trench objects at bore ends | UNCHANGED (a wing is no trench object) |
| 12 | `pack_partition.partition_pack` / `contact.partition` | contacts | READ only (plus the NaN-anchor refusal, §4) |
| 13 | `planar/free_bridge` hard set, `structure_approach.deck_objects` | `DeckBridge.members` | UNCHANGED (members unchanged) |
| 14 | `tools/drawn_site.py` / `drawn_gate.py` | the written pack | READ: the bars |

## 4. Two general bugs (same round)
* `pack_partition.partition_pack`: a placement whose anchor reads no ground (`anchor_z`
  NaN, a cold DEM) made every ε-test false: 0 contacts, silently. Now skipped with a named
  reason and counted (`counts["no_ground"]`), said on stderr; the partition REFUSES
  (`ValueError`) when no resolved placement has ground.
* `geom/foot_planes.floor_plane` / `ground_plane`: a NaN candidate emptied the band
  (`IndexError` at :63); NaN candidates are left out, none left -> `None`.

* `airport/deck_signature._raster` (found on the closing tile): every face edge was sampled
  with the LONGEST edge's sample count, all faces at once -- CYSN's 827k-face
  `YSN_Fence_1.obj` held 13.2 GB in one pack worker, the #1980 memory guard stopped the
  airport and with it the whole N43W080 tile. Now a chunk of faces at a time (the same
  points, the same grid: 39 rasters byte-equal): 0.70 GB.
* Registry gaps the closure twins named on test-534 (`airport/floor_rim`, `object_floor`,
  `walled_pit`, `geom/shape_class` missing from the classify / road_profile / channels /
  shapes / jetway_strip / constraints.assembly stage keys, the partition key and the object
  stage key), keyed with `airport/mouth_group` (emit).

## 5. Not this round (listed residuals)
* The cut along a wing: the ramp beyond the deck stays the road corridor's; the wing's foot
  profile (T: -1.1 at the box rising to +6.2 at 160 m out) is not a ramp witness yet.
* Mouth classes M4+ (hanging cover / shell not taken as a deck, object-floor frames, deck
  stacks): no witness at this round's airports.
* A portal's foreign-anchor wings in its stated top (R4 `_wing_plan` reads its own object).

## 6. Bars
* Replays (`--replay --from planar --emit`): CYYZ wing plates as §2 predicts; the patch
  unchanged against the base replay (the seat is object-stage only). KBNA
  `frames/lkbna2/KBNA.pkl`: no mouth group; P1/P2/TL patch equal to
  `frames/lkbna4/KBNA_auto.patch.arm.osm` up to test-533's XB additions. ENTC
  `frames/splitlvl3/ENTC.pkl`: no group, unchanged. Protected KEGE, KBTV, KSUN, KDEN
  captures: no group (BIKF, LICJ, EGNS: no capture; listed).
* Closing (drawn, `build_airport.py CYYZ --tile 43 -80 --pack-copy`, `drawn_gate.py
  --site T/M/FA --against` the control lmouth_c0 at c5cdd0c8c): each T / M wing's drawn zero
  = its box's drawn zero + floor y within 0.05 m; no wing drawn floating over the ground at
  its foot by more than 0.5 m where the ground is the road floor; FA equal to the control;
  objects no new FAIL, mesh no MOVED.
* Stop rules: a group forming at KBNA / ENTC / a protected capture -> STOP and list; a bar
  missed after one fix iteration -> STOP and report (ONE-MISS).

## 7. Result (lane lmouth2099, closing tile builds lmouth_c3 control at a2952b1d3 / lmouth_a2 arm at 2f2b35f4f)

Drawn (`tools/drawn_site.py` on the pack copy and the tile DSF; a placement's drawn zero =
its highest drawn top less its authored top y):

| mouth | box drawn zero / floor | wing | control: zero - floor | arm: zero - floor |
|---|---|---|---|---|
| T | 165.77 / 158.26 | `_T_b` | +5.36 | -0.01 |
| T | | `_T_c` | +2.46 | -0.01 |
| T | | `_T` | +2.18 | -0.02 |
| M | 151.46 / 151.41 | `_M_b` | +9.42 | -0.01 |
| M | | `_M_d` | +8.04 | -0.01 |
| FA | 159.76 / 159.76 | `Bridge_Infield_b` | -0.00 | -0.00 (co-placed, unchanged) |
| FA | | `Bridge_Infield` | +0.01 | +0.01 (unchanged) |

Boxes unchanged (zeros equal in both builds); the patch is byte-identical (replay arm =
base: patch, graded surface and authored seats). `drawn_gate.py --site T/M/FA --against`
the control: `moved []`; the site verdict FAIL is the control's own, row for row (the deck
mouths' "deck under the floor" and the T / FA road steps 6.58 / 7.84 m: the cut, §5).
Residual (§5): beside the wings the drawn ground is not the authored ramp -- T's walls are
buried 2-6.5 m at their foot within 20 m of the box (tops 1.6 m under the cover's parapet,
2-6 m over the ground), farther out up to 2 m of foot shows (p50 per body +1.5 / +2.0);
M's wings, at the box's own zero, stand 1-2.4 m into the road beside the box exactly as the
box does (its floor 2 m under the drawn road).
