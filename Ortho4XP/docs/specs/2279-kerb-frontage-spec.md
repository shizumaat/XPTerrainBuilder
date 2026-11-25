# #2279 step 2 — the kerb-level frontage (a unit's landside meets the building at its kerb)

Owner, #2279 (PHLI, terminal 21.97786, -159.34878): "the terminal's landside
is one level higher; the front access road and parking must be graded to
meet the bottom of the building and its kerbs, grading down to the retaining
wall (the level change is at the wall)". With RULINGS 2026-11-25b (5)
(pavements touching: the step is a wall) and 2026-11-25e (a groundside lot
follows its ground within its 5 % cap).

Step 1 (lane lphli, `56bca13af`/`31926d69f`): §27 keeps a lot that meets the
apron mostly across a unit's upper storey groundside as the unit's LANDSIDE
(`storey_edge.STOREY_LANDSIDE_KEY`), the storey's PLAN = the convex hull of
its upper parts; the lot is cut back from the plan and what it drew under the
plan became apron (the building's airside floor).

## 1 What step 1 left (measured, PHLI replay of the lphli capture)

- The kerb drive along the terminal's landside face lies INSIDE the hull but
  under no part: 2.9 k m² in two strips 67-72 m from any airside (hull
  34,586 m², upper parts 22,758 m²). Step 1 made it apron at the floor
  (47.17), a storey under its kerb.
- The lot beside the plan stood at 47.4-47.5 (ground 49.4-49.6): the road
  stub `small_roads:-386#1` shares vertices with the under-plan apron and the
  lot; its within-shape pair, the apron-edge ramp and their hard 5 % ceiling /
  10 % fallback-cap twins welded the lot edge to the floor; the §37 ramp
  ceiling (DEM + 0.5) held the road-shared lot vertices.

## 2 The rule

C1 (classify, `storey_edge._floor`). The building's airside floor inside a
landside lot is the storeys' BODY — their upper parts' footprints closed
across `[design] pad_frontage_m` — plus each piece of the lot inside the hull
but off the body that touches the airside (a bay of the airside face). A
piece inside the hull that fronts no airside stays the landside's. The lot is
cut back from the floor (not the hull); the floor rings ride on the lot as its
KERB LINE (`STOREY_PLAN_KEY`, with `STOREY_UNIT_KEY`).

P1 (planar, `planar/kerb_frontage.publish_kerbs`). After the pads and levels
are minted, each landside lot's record `{lot, plan, y}` (y = the storey's
rise, `STOREY_Y_KEY`) goes on the held block of the storey's unit the plan
covers (an upper level's block first, else the most covered) under
`model.registries.LANDSIDE_KERB` — no new registry field.

K1 (constraints, `constraints/kerb_frontage.kerb_frontage_rows`, family
`kerb_frontage`). Every groundside-pavement vertex (`groundside_face_roles`:
lot and front access road alike) outside the plan and within
`pad_frontage_m` of it, no stage-1 vertex and no pad's, takes ONE one-way
equality `z_v − z_D = y`, D the block's datum column (the landing rows'
column). A stage-2 row with D stage 1's constant: never pulls the pad.
Head `structures.building_pad landside_kerb` in `pad_flat_rulings` (§28's
senior price) and `one_way_rulings`. The lot grades away under its own law.

K2 (assembly post-pass `kerb_wall_exempt`, after the 5 % ceiling and the
fallback cap). Withdrawn: every row spanning a kerb vertex and a WALL vertex
(inside the plan or within `groundside_cutback_m` of it) — the wall at the
plan edge, 25b (5); and every §37 road-ramp row all of whose vertices are
kerb vertices (the run-out precedent `ramp_runout.runout_exempt`).

No new law key, no tuned threshold, no ICAO literal.

## 3 Consumer census of the storey plan / landside record

| Reader | Reads | Effect of step 2 |
|---|---|---|
| `classify/airside_edge._landside_of_storey` | `StoreyBand.plan` (hull), `storey_height(plan=True)` | unchanged (detection) |
| `classify/storey_edge.storey_height` | hull, parts | unchanged |
| `classify/storey_edge.knife_storeys` | `_storeys_met` + `_floor` | cut-back and airside-floor pieces now from the floor (body + airside bays), not the hull |
| `classify/roles` hold test (`STOREY_Y_KEY`) | lot evidence | unchanged |
| `planar/overlay._storey_lots` → `low_level._upper_split` | `STOREY_Y_KEY` | unchanged (upper level minted where the lot meets a held pad) |
| `planar/kerb_frontage.publish_kerbs` | `STOREY_PLAN_KEY`/`UNIT_KEY`/`Y_KEY` | NEW: block record |
| `constraints/kerb_frontage` rows + wall exempt | `held[*][LANDSIDE_KERB]` | NEW |
| §28 `groundside_frontage_level` | pad relation | its rows from a kerb vertex to a pad under the plan are withdrawn by K2 |
| `groundside.groundside_ramps` (apron-edge ramp) | apron ↔ groundside pairs | withdrawn across the wall by K2 |
| `ceiling.pavement_ceiling`, `pavement_cap.pavement_road_cap` | difference rows | twins across the wall withdrawn by K2 (it runs after both) |
| `road_ramp` §37 target / ceiling | road vertices | withdrawn on kerb vertices (K2) |
| census (`check_grade`) | patch | sees the wall as a step between the kerb and the floor (reported below) |

## 4 Measured

See the lane report (#2279, lane lphli2): PHLI transect, census, population.
