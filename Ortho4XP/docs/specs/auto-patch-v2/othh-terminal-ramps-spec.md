# v2 — OTHH terminal: door ramps and the sunken road under the building (spec, 2026-09-08)

Owner (RULINGS 2026-09-08b): "spots where the object extends below
ground, at least one slightly depressed tunnel under the building, and
several basement access doors that need a small ramp going down to
them." Measured by scout `othhterminal` on `OTHH_20260907T125006`
(flat site Z0 3.962, every plate depth = metres under ground). Author:
session (Fable). Implementer: lane `v2doorramp`, AFTER `v2trenchgap`
merges (same files).

## 1. Measured (the scout's read; KML sent to the owner)

* SIX basement access wells whose floor plate reaches the car parks'
  exterior face: sills −1.57 … −1.70 m, wells 3.7 × 1.5 m (Parking-
  Left/Right ×4), 3.8 × 2.4 (VCN_003), 5.2 × 4.8 (Terminal_Parking_006);
  nearest at-grade OSM road 22.8–41.4 m. v2 emits NOTHING: they are
  under `basin.admission_depth_m` 2.5 (obj8.py:648-650) and never a
  witness.
* TWO sunken road ramps (`TerminalRoads_03_000` / `02_000`): floor
  plates 2,368 / 2,288 m², 183 × 22 m, from the mouth at grade down
  3.09 / 3.18 m (1.7 %), then the underground road to −11.5 m; roofed by
  the viaduct decks (`03_002` / `02_002`). Refused by the tunnel-object
  pass as "roofed along its axis" (tunnel_objects.py:305-316) and by the
  basin pass (`through_grade` / `no_floor`, obj8.py:662-673, 742-756);
  no OSM tunnel way runs along them; v2 emits nothing — flat terrain
  3.96 over a floor 0.56–3.65 m under it.
* Two genuine BASEMENTS under Bridge_01 (basins 8/10, own cover 1.00):
  correctly refused (basins.py:337-345) — unchanged.
* The terminal proper's "spots": four −0.17 m slivers of Terminal_Base_2_1
  (6.7 / 2.2 / 2.2 / 1.6 m²) — below every gate; unchanged.

## 2. Law A — DOOR RAMP (`structures.toml [cutout.door]`)

Where a below-grade floor plate of an object REACHES ITS EXTERIOR FACE
(the plate boundary leaves the object's own at-grade geometry,
obj8.py:801-833 — a door, not a basement), cut a trench of the sill's
width from the sill up to grade at the ramp grade, OUTSIDE the building
only, along the outward normal of that face. Keys: `sill_min_depth_m =
0.5` (its own gate, separate from the 2.5 m basin gate), `sill_min_width_m
= 1.0`, `ramp_grade = 0.08` (a 1.70 m sill → 21 m; the pack's own
geometry implies ≥ 7.5 % — the nearest road is 22.8 m away — the
owner's "small ramp"), `max_length_m = 25` (a ramp that would cross an
at-grade road or pavement STOPS at it and steps — report the case).
The trench floor = the sill plate ⊕ `floor_overlap_m`; the rim = 08a's
`rim_inset_m` inside the well's walls; the ramp is a `tunnel_ramp`-class
structure face (precedence.toml) with `seat = "none"` — the door groups
NEVER re-seat the anchor family (basins.py:392-400 `seat =
"floor_plate"` would move all 35 members of unit:22): members standing
> `contact_band_m` under the mesh are facility members and keep their
authored y (structures.toml:169, emit/rebake.py:382-391).

## 3. Law B — SUNKEN ROAD under the building (`[cutout.sunken_road]`)

A floor plate below the seat that is ROOFED (today's refusal) whose
plate reaches within `contact_band_m` of the ground at one end is a
sunken road: the mouth is that end; the trench = the plate ⊕
`floor_overlap_m` along the axis, the floor = the plate's own y per
station (the 1.7 % descent), cut only to `max_depth_m = 4.0` (deeper is
the underground road — the terrain stays); rim inside the wall (08a);
the building/deck above untouched (the roof is the object). A third
signature class in `airport/tunnel_objects.signature` beside full/edge
wall; `planar/object_corridor.object_groups` (:119-162) takes the depth
per station from the plate, `climbs = False` at the deep end;
`basins.py`: a plate whose depth VARIES and reaches grade is a ramp,
never a basement (`basement_cover_min` applies to level, closed plates
only). `seat = "none"` likewise (unit:26's 399 members stay).

## 4. Consumer census (owner 30l) — written by lane `v2doorramp` BEFORE editing

The new geometry: two `Tunnel` records per law (`source = "door"` /
`"sunken_road"`), a door's ramp cells (new role `door_ramp`, ref
`door_ramp`) and a sunken road's ramp cells (role `tunnel_ramp`), each
with the void face (`retaining_wall`, ref `tunnel_wall`) whose exterior
is the rim.  Both enter `build_structures`' ONE group loop (05n's
object-corridor path), so every consumer of a tunnel structure is a
consumer here.  Ruled per pass, in one table:

| Pass | Reads | Interaction | Ruling |
|---|---|---|---|
| `airport/obj8.py` `_witness` / `at_grade_geometry` / `above_grade_footprint` | the components, the ground-contact linework, the cover | reused READ-ONLY by the two new readers; `FloorWitness` gains `plate_y_min` (the plate faces' own deepest y — the sill) | the 2.5 m basin admission is untouched; the door gate (`sill_min_depth_m`) is the reader's own |
| `airport/door_wells.py` (new) | sill witnesses ≥ `sill_min_depth_m` under the local ground, the family's own at-grade polygons | a well = a below-ground region whose boundary is partly INSIDE the family's cover (the sill line, ≥ `sill_min_width_m`) and partly outside; own cover ≥ `basement_cover_min` → basement, nothing; a component reaching the basin gate is the basin pass's | the door is read where the plate leaves the object's at-grade geometry (§2), never by proximity |
| `airport/sunken_roads.py` (new) | every anchor FAMILY's near-horizontal genuine faces at or under the ground | a connected plate ≥ `min_plate_m2` whose station profile reaches within `contact_band_m` of the ground at one end and descends ≥ `min_descent_m` is a sunken road; the trench runs from the top station (`top_depth_m`) to the station where the plate reaches `max_depth_m` | DEVIATION from §3's "third class in `tunnel_objects.signature`": the wall signature is per RESOURCE in the authored frame, the sunken plate is a per-FAMILY reading (03_000's roof is 03_002, the deep continuation another member) — the class lives in its own reader; `signature()` keeps its "roofed" refusal, the line names the reader that owns it |
| `planar/basins.py` | the witnesses (2.5 m gate), the structures already built | a door well never reaches it (no witness); the sunken road is a STRUCTURE before the basin pass runs — an overlapping region is refused by the existing "overlaps a tunnel structure" rule | the basement branch needs NO exemption: the order settles it (30l: trim at the derivation, no per-consumer veto); `shell_thickness_m` gains `exclude` (sill-line samples are not wall samples) |
| `planar/structure_geometry.py` | axis, half / rim functions | reused unchanged: a capped U (the cap at the building face / the deep-end cut) | rim = `rim_standoff` of the measured side thickness (08a); beyond the well the OSM stand-off, as an object corridor beyond its walls |
| `planar/object_corridor.py` `Group` | — | fields added: `kind`, `max_grade`, `max_length_m`, `spacing_m`, `climb_from_s`, `stop_at_pavement`, `profile` | `object_groups` unchanged in behaviour |
| `planar/structures.py` `build_structures` / `_ramp_top` / `_pad_hit` | the groups | the climb grade / length / spacing are the group's; a door ramp's climb starts at the well's outer edge (the well floor is the sill); `_pad_hit` for a door probes EVERY non-structure cell BEYOND the well except the HOST cell(s) holding the well's outer edge (the pavement the well stands in is cut like any structure; a pavement the ramp would ENTER stops it: `clipped_by`, the ramp steps — §2 "report the case"); the well cuts every cell incl. pads (hull knife, 08-26) | runway-family / strip refusals unchanged |
| `planar/structures.ramp_targets` | tunnel records | door faces target the design line (flat in the well, 8 % beyond); sunken faces the plate profile | the objective never pulls the ground |
| `constraints/structures.py` | the ramp / void faces | Diff cap per tunnel: `cutout.door.ramp_grade` for a door, `tunnel.ramp_max_grade` else; the mouth pinned absolute (as an object corridor); a sunken road's EVERY station group pinned at the plate profile (senior); `structure_roles` += `door_ramp` | ids `door:` / `sunken-road:` are outside `[structures] datum_order` — `reconcile_datums` neither withdraws nor ranks them (no shared vertex with a tunnel or basin rim is expected; reported if the build shows one) |
| `precedence.toml` | — | role `door_ramp` (common, groundside, value, structure, `oracle_role = tunnel_ramp`, `oracle_law = service_road`), NOT in `[authority] order` (tier after the named, as an omitted governed role) | DEVIATION from §2's "`tunnel_ramp`-class face": `tunnel_ramp` is capped 4 % in BOTH instruments (rulesets / v1 `ROLE_GRADE_LIMITS`) — an 8 % ramp emitted under it is a violation by construction; the door ramp is its own role, priced 8 % by v2's verify (`role_cap`) and by the oracle through the existing `o4_grade_law` override (`ROLE_GRADE_LIMITS[service_road]` = 0.08) composed with `o4_grade_law_cap` = 0.08 |
| `rulesets.toml [common.roles]` | — | `door_ramp = { longitudinal = 0.080, transverse = 0.020 }`; loader cross-check `cutout.door.ramp_grade ≤ door_ramp.longitudinal` | one number, checked at load |
| `emit/osm_adapter.py` | `RoleSpec.oracle_role` | writes `role=tunnel_ramp class=door_ramp o4_grade_law=service_road o4_grade_law_cap=0.08` (the new `oracle_law` field) | no oracle code change |
| `emit/graded.py` `FLOOR_ROLES` | floor roles | += `door_ramp` (the void's rim chain drops the edges along the ramp) | |
| `emit/rebake.py` facility rule, `pipeline/build._plate_seats`, `airport/rebake_plan.py` | `pm.structures` with `source == "object"`, the basins | a door / sunken family is NOT plate-seated (`_plate_seats` skips every other source), NOT excluded, NOT below-grade deck evidence; its members seat by the cluster law with the facility rule (05p/05q: a part > `contact_band_m` under the mesh keeps its authored y) | `seat = "none"` is the only generated value (loader-checked); the deck-promotion evidence stays the basins' (owed if a foreign deck over a sunken road ever needs it) |
| `verify/structures.py` | ramps by role, rims by feature, `tunnel_objects` axes | `structure_rim_gap` floors += `door_ramp`; `tunnel_mouth_canonical` exempts sites on published object axes — doors and sunken roads are published there with `kind` (their mouth datum is not the 09-03b cap − 5.1) | `tunnel_deck_clearance` unchanged |
| `verify/within.py`, `steps.py`, `no_step.py`, `contiguity.py` | roles / sides | `door_ramp` is groundside + structure: no airside step pairs; not a road-family role (lateral contiguity binds none of it); within-shape at its own cap | `road_cross_section` binds none of it; the ramp is laterally flat by the generator's `Flat` rows |
| the oracle (`tools/check_grade.py`) and the harness census | the emitted tags | as the adapter row; partition groundside under `tunnel_ramp`; the rim is a role-less `structure_rim` feature as today | no code change; `terrace_joint_route` pre-existing row untouched |
| `airport/flat_site.py`, `constraints/flat_site.py` | structure roles | `door_ramp` is `structure = true`: the flat datum skips its vertices (05k-2) | `seat_consensus` unchanged |
| `pipeline/publication.tunnel_objects` | `pm.structures` | publishes every non-OSM structure with `kind` ("wall" / "door" / "sunken_road") and the door fields (sill z, width, ramp length) | sidecar key set unchanged |
| `law/model.py` | `Cutout` | moved to `law/cutout_schema.py` with `Door` / `SunkenRoad` (the 1,000-line law) | |
| `tests/auto_patch_v2/test_law_tables.py` | v1 registers | `groundside partition` RULED drift += `door_ramp` (a v2-only role, aliased for the oracle like `parking_lot`) | `precedence.order` unchanged |

### 4a. What the lane found when it read the pack (v2doorramp, 2026-09-08)

* LAW B HAS NO SITE at OTHH under this tree's reading.  The spec's "floor
  plates 2,368 / 2,288 m², 183 × 22 m, 1.7 %" of `TerminalRoads_03_000` /
  `02_000` do not reproduce: those files are 59- and 84-vertex viaduct
  ramps whose below-ground faces are 139 / 189 m² at 19 % (the ramp feet
  dipping 1.9 m under), `03_002` / `02_002` carry 293 / 340 m² of faces at
  10–45 % between −1.8 and −0.7 m, and the scout's own face selection
  (`n_y ≥ 0.7`, `y_max` in [−3.0, −0.5]) returns NOTHING for the six
  TerminalRoads resources it named.  The only descending plates near the
  site are `Terminal_Parking_002`'s car-park ramps (505 / 324 / 152 /
  140 m² pieces at 12–20 %, 2.4–3.2 m deep).  Under §3 as written (the
  floor along the plate, priced by the 4 % ramp law) nothing qualifies;
  the reader is in place and finds level roofed plates (`LEVEL`), unroofed
  descending plates (the bus bridges' banks, 16–20 % roofed) and the
  drainage bowls' banks (open), each refused by name.  Two keys the lane
  added to make §3 decidable: `roof_min_fraction` (0.5 — "roofed" is not
  quantified in §3) and `min_descent_m` / `min_plate_m2` / `top_depth_m`;
  a plate steeper than `tunnel.ramp_max_grade` is refused (the ramp law
  prices every ring pair at that cap).  OPEN to the spawner: whether the
  car-park ramps (12–20 %) are the owner's "slightly depressed tunnel"
  and, if so, at what cap (its own role, as the door ramp).
* LAW A at OTHH (closing tile builds `OTHH_20260908T114527` /
  `OTHH_20260908T121758`, rc 0): 8 wells read, 7 door ramps emitted —
  the four `Terminal_Parking_Parking-Left/Right_000` wells the scout named
  (sill 2.26 = 1.70 m under 3.96, 2.46 m wide along the face, the well
  2.1 m, the climb 23.9 m at 8 % to the ground at s 26.0) at
  25.257491,51.613901 / 25.257367,51.613397 / 25.258519,51.616490 /
  25.258288,51.616033; `Terminal_Parking_006@0` (sill 2.38, 14.7 m wide,
  well 6.4 m, climb 23.6 m); `TerminalRoads_Parking_000@0/@1` (sill 2.27,
  8.0 / 10.1 m wide, wells 11.5 / 10.7 m, climbs 24.5 / 23.3 m) — sunken
  parking pits the letter of §2 admits.  `VCN_003` is refused (the side
  opposite the face lies under above-band solids); `Parking_006@1`
  overlaps `@0` (31h's overlap rule).  v2 verify: every family 0 but ONE
  `structure_rim_gap` row of 0.0004 m (a rim vertex 0.4996 m off a door
  ramp after the identity snap: under the 0.01 m materiality floor,
  PASS-with-residual); census `--no-cache` on the patch: every family 0
  but the pre-existing `terrace_joint_route` 1.  THE FACE IS THE OPEN
  QUESTION: the wells are closed four-walled boxes hanging from the car
  parks' facade lattice, the door a texture on the building-side wall;
  the at-grade band, the above-band cover and the shell's walls all read
  alike on both long sides.  The lane's rule: the face is the well's
  longer side nearer the centroid of the family's above-band solids
  within `max_length_m` (the building's mass), the exit its opposite
  side, which must lie mostly outside that cover (`exit_max_fraction`); a
  plate that descends at or under `ramp_grade` over its reach is the
  object's own ramp, never a sill.  The owner's sim read decides whether
  the ramps leave the right side.
* THE SEAT (`seat = "none"`): the first build's post-mesh cluster seat
  sank 8 objects of the Parking family (`Parking-Left_000/002/006`,
  `Right_000/005/006`, `VCN_000/001`) by −1.0 … −1.9 m — parts whose
  ground sample fell inside the new trenches.  The lane reads `seat =
  "none"` as: a door's / sunken road's anchor family is EXCLUDED from the
  re-seat (the rebake plan's pre-existing "terrain adapted to it" skip,
  `structure_family_excluded`).  Second build: 75 objects written
  (Bridges Bus 45, Dewatering 18, tunnels 8, Emiri 4; 95 on main) — the
  Parking family 0 AND the 197-member TerminalRoads family 0, the latter
  because `TerminalRoads_Parking_000` carries two wells: the 08d deck
  artefact (−10.87 m, 19 writes) is MASKED at OTHH by this exclusion, not
  fixed — lane `v2othhseat` must know.
* LEMD `--base-arm` (`LEMD_20260908T121038`): 10 door ramps —
  `Terminal4SAT_green-LEMD13` ×8 (sills 596.06–596.09 = 1.9 m under
  598.0, 18 m wide, ramps 26.4 m) and `-VRDCH` ×2 (598.75 = 1.3 m under,
  38 / 32 m wide, ramps 20 / 18 m): the T4S service yards, "doors" by the
  letter of §2; v2 verify 19 vs 18 on main (+1 = a 0.0007 m rim-gap
  residual on a door ramp; taxi_box 2, strip_seam_tear 5, transverse 4,
  vertex_to_edge_step 1, tunnel_mouth_canonical 6 unchanged).  CYXY
  `--base-arm` (`CYXY_20260908T121609`): 0 rows, no door, 7.1 s.
* COST: the door reader is 56 s at OTHH (11,325 placements, 263 screened
  at the 0.5 m sill gate, 517 sill witnesses, 357 regions) after four
  rounds of pruning (254 → 174 → 98 → 56 s: cheap plate gates first, bulk
  triangle clips in `obj8._clip_component` / `_clip_both`, per-region
  `within` windows on the cover reads with a per-resource component-bounds
  pre-select — `within` is a new argument of `obj8.above_grade_footprint`
  / `at_grade_geometry`, `ResourceCache.component_bounds` new); what is
  left is `solid_components` on the ~166 resources the 0.5 m gate admits
  that the 2.5 m basin gate never read (30 s) and the witness reads.  The
  sunken reader is 2 s.  Under the build-time law this is a Fable
  optimisation-review item, reported, not decided.

## 5. Twins and acceptance

Twins: a box with a 1.7 m well reaching its face → one door ramp of the
sill width, 21 m at 8 %, rim inside the well walls, the anchor unmoved;
the same well under the roof → basement, nothing; a roofed descending
plate reaching grade → sunken-road trench to 4 m, floor along the plate,
anchor unmoved; a level roofed plate → basement. ONE build: `OTHH
--engine v2 --tile 25 51` (the seat is post-mesh): the six wells and
the two ramps emitted (quote each: floor z, rim, length), verify 0,
census 0/0, `objects moved: 0` for units 22 and 26 (the owner: no object
modifications), LEMD/CYXY `--base-arm` unchanged.

## §6 Law C — WALL-BOTTOM FLOOR corridors (RULINGS 2026-09-08m)

Measured by scout `othhunderpass` (KML `scratchpad/othhunderpass/OTHH_underpass.kml`; scripts beside it). The pack models the terminal's road underpass and its loading bays as KERB WALLS only — vertical faces 1.35–1.89 m under ground, no floor at any depth, a deck above at 4.3–4.5 m headroom. Law: `[cutout.wall_corridor]` — `min_wall_depth_m 1.0`, `min_width_m 6.0`, `max_width_m 20.0`, `min_wall_length_m 5.0`, `min_headroom_m 3.5`, `ramp_grade 0.08`, `max_ramp_grade 0.10` (when the ramp would enter airside pavement it stops at the pavement edge and steepens to this), `seat "none"`. Mechanism: wall bands from vertical-only genuine components (`obj8` must keep zero-plan-area bands: `_bulk_polys` drops them today), paired per family into corridors, handed to `tunnel_walls.read_wall_lines` (kind "II") and `object_corridor` with `mouth_depth = "wall_bottom"`; closed ends by a crossing family face within `end_cap_open_m`; open ends = mouths with ramps at 8 % (site 1: NE 18.9 m to the apron → 10 %; SW 23.6 m, OSM −9214 yields onto it; site 2: 16.9 m). Basement cover gate replaced by the headroom test for corridors. Twins: two parallel bands 10 m apart 1.9 m deep under a deck → a corridor, floor at the wall bottom, two ramps; one band alone → nothing; bands 25 m apart → nothing; a closed end → one ramp; a ramp meeting airside pavement → stops and steepens to 10 %, refused loudly above it. Acceptance: OTHH tile: both corridors and the three bays emitted (floor z, mouths, ramp lengths and grades quoted), verify 0, no terminal object written; LEMD/CYXY unchanged.

### §6a Consumer census (owner 30l) — written by lane `v2wallcorridor` BEFORE editing (2026-09-08)

Three geometry-law changes land together (RULINGS 08l/08o depth, 08o seat stations, 08m/08n Law C).
Every pass that reads the affected geometry, ruled in ONE table. Key: **D** = depth law, **S** = stations, **C** = wall corridors.

| # | Consumer (file:symbol) | Reads | Ruling |
|---|---|---|---|
| 1 | `airport/tunnel_objects.signature` | floor faces below the seat (`floor_plate_max_m2` refusal) | **D**: a floor slab (`_axis_crossing_area` ≥ `plate_min_area_m2`) is DEPTH EVIDENCE (`WallSignature.floor_y`), never a refusal; `floor_plate_max_m2` DELETED. A floor the basin pass witnessed still routes to basins (`o.witnesses`, unchanged). |
| 2 | `airport/tunnel_objects._corridor` | `depth = sig.plate_y` (crest-to-anchor) | **D**: `depth = plate_y − floor_y` with a slab, else `tunnel.bore_datum_m` for EVERY mouth kind (`mouth_depth = "floor_slab"`); the edge-wall "no bore mouth" refusal is WITHDRAWN (bore_datum is the depth); a `closed`-kind mouth with no mapped road (highway/railway) through the trench is refused by name ("closed-end fallback with no road through it"). `plate_y` unchanged (the seat's crest). |
| 3 | `airport/tunnel_objects._bore_ends_at` / `_bore_near` | `end_cap_open_m` 2.0 as the bore-end tolerance | **D**: `bore_end_tolerance_m` 5.0 (new key) for the END-inside test and the line-crossing test; `end_cap_open_m` keeps its end-wall meaning. `Corridor.bore_ways` records the ways at each mouth. |
| 4 | `planar/structures.build_structures` precedence (`mouth_covered_by`) | footprint ⊕ `end_cap_open_m` | **D**: a mouth whose bore way is in the corridor's `bore_ways` PAIRS with it (replaced), else footprint ⊕ `bore_end_tolerance_m`; the overlap refusal at OTHH −9170/−9169 disappears by construction. |
| 5 | `constraints/structures.structures` (law check + `src_mouth` text) | `ob.mouth_depth == "plate"` | **D**: accepts `"floor_slab"` only; the mouth pin is `tn.mouth_z` as before (absolute). |
| 6 | `planar/structures._reseat_expect`, `pipeline/publication`, `verify/structures.tunnel_mouth_canonical`, `emit/rebake._plate_reading` | `plate_y_m` (crest) | **D**: untouched — the crest stays the seat datum; only `depth_m`/`mouth_z` change. |
| 7 | `pipeline/build.plate_stations` / `_plate_seats` | `Tunnel.footprint` ⊕ grid | **S**: stations = (footprint ∪ the emitted rim ring near it) ⊕ grid, minus the ramp band beyond the wall end (`axis[wall_length_m..top_s]` ⊕ half + rim); never inside the rim ring, never on the ramp. Basin plate stations untouched. |
| 8 | `airport/rebake_plan.plan`, `emit/rebake.seat` | `plate_stations` per member | **S**: read as before (lat/lon list); no change. |
| 9 | `airport/obj8._bulk_polys` | drops zero-plan-area bands | **C**: NOT edited (obj8 is 991 lines; the ≤ 1000-line law). The wall-band reader (`airport/wall_corridors.py`) reads vertical triangles from `Component.tris` directly and builds bands from their plan segments — the zero-area bands never pass through `_bulk_polys`. Deviation recorded (brief said "obj8 must keep zero-plan-area bands"). |
| 10 | `airport/tunnel_walls.read_wall_lines` (kind "II") + `midline` + `stations_along` | a two-part plate | **C**: fed the union of the two band polygons; a zero-thickness sheet is widened to a nominal band so `simplify(0.01)` cannot collapse it (its measured thickness stays 0 → rim stand-off floors at the identity spacing, 08e thin-shell case). |
| 11 | `planar/object_corridor.Group` | group fields | **C**: new fields `stop_side`, `ramp_cuts_pads`, `mouth_strip`, `sibling`, `ramp_role`; defaults keep every existing group byte-identical. |
| 12 | `planar/structures.build_structures` climb block (`fits`) | object corridors climb INSIDE the walls | **C**: a wall corridor never climbs inside its walls (the floor is the wall bottom): `fits = False`, `climb_from = hull_s`, the climb beyond at `ramp_grade`; a descending corridor has no climb (`climbs = False`). |
| 13 | same — decks (`obj_ivals`, `deck_ivals`, `_pavement_deck_intervals`) | decks over the corridor | **C**: object decks and mapped bridges INSIDE the walls are not read (the deck above is the family's own roof — the headroom test replaces `bridge.clearance_m`); beyond the walls they are read as for any ramp; pavement decks as before. |
| 14 | same — `stop_at_pavement` / `_pad_hit` | door: every governed cell beyond the well | **C**: `stop_side = "airside"`: AIRSIDE cells (non-structure, non-runway) + building pads stop the ramp; groundside cells (a service road) are cut by it (08m (b)); host cells (the ones the corridor stands in) never stop it. After a stop the climb STEEPENS: `g' = rise / (s_top − climb_from)` ≤ `max_ramp_grade` → `design_grade = g'`, top pinned at the ground; else refused loudly. |
| 15 | same — the uncapped-mouth strip | `not g.capped` → a grid strip beyond the mouth | **C**: only for kind `object` (a bore continuing underground); a level open/open corridor is TWO capless halves meeting at its midpoint (the `Tunnel` doc's own model), sharing the mouth line's vertices, exempt from the overlap refusal as siblings. |
| 16 | same — `hull_knives` | walls cut pads, the ramp beyond does not | **C**: the whole footprint cuts (walls + ramp), pads included: a pad over a ramp is nonsense; the ramp never crosses a pad it does not host (`_pad_hit` on pads still stops it). **Closed on the tile build (lane instance 2):** the knife guarded the WHOLE beyond-the-walls strip, so a pad the corridor HOSTS kept its `weld_to_touching_pavement` Flat over the ramp's own vertices — five `building5` pad flats gripped seven wall-corridor FLOOR vertices at OTHH and the ladder demoted `wall_corridor_ramp` by 1.392 m (the bays' full depth); the build refused. The knife now guards only the part of the strip lying in a NON-host pad. A pad cannot both host a ramp and hold it flat. Twin `test_a_host_pad_is_cut_by_the_ramp_beyond_the_walls`. |
| 17 | same — `ramp_role` | `door_ramp` / `tunnel_ramp` | **C**: `wall_corridor_ramp` (level corridors, bays, their climbs; cap `max_ramp_grade` 0.10) and `garage_ramp` (authored descending floors; cap `max_authored_grade` 0.25) — two new roles (`precedence.toml`, `rulesets.toml [common.roles]`), groundside, structure, oracle alias `tunnel_ramp` at `service_road`'s law. ORACLE LIMIT: v1's largest role cap is 8 % (`service_road`), and the alias composes as a MINIMUM — a wall-corridor ramp between 8 and 10 % and any authored garage ramp over 8 % is reported by the v1 census as `within_shape` although lawful; v2 verify reads the role's own cap. Reported as an instrument limitation, not hidden. |
| 18 | `constraints/structures.structures` | `source` branches; datum group `Flat` + mouth pin; descent `Diff` rows; top pin | **C**: `source == "wall_corridor"`: stations inside the walls (`s ≤ wall_length_m`) are SENIOR pins at `profile_z` (the wall bottom per station: level or descending, cut as authored); no datum `Flat`; beyond the walls the descent `Diff` rows at `wall_corridor.max_ramp_grade` and the top pin at the ground; the rim rows as for every structure. |
| 19 | `planar/structures.ramp_targets` | `tn.profile` → target everywhere | **C**: the published profile INCLUDES the climb (design line to the top), so the target is the design along the whole ramp; roles tuple gains the two new roles. |
| 20 | `constraints/structures.ramp_faces_of`, `on_floor`, `structure_roles`; `emit/graded.FLOOR_ROLES`; `verify/structures.structure_rim_gap` floors; `tests/auto_patch_v2/test_law_tables.py` groundside partition | role literal tuples | **C**: each gains `wall_corridor_ramp` + `garage_ramp` (the census names them all; a role missed here would leave a floor unread by that pass). |
| 21 | `pipeline/build._plate_seats`, `build()` seat exclusion (`excluded`) | `source == "object"` / door + sunken_road | **C**: wall corridors are never plate-seated (`source != "object"`), and their families are EXCLUDED from the re-seat like doors (`seat = "none"`). |
| 22 | `pipeline/build` report lines; `planar/__main__.structure_records`; `pipeline/publication` (`kind = source`) | per-source lines/records | **C**: a wall-corridor line per site (floor z per mouth, class, ramp length/grade); records + `--kml` inventory in the structures replay; the publication carries `kind = "wall_corridor"` (the mouth-canonical verify exempts every non-osm kind by axis, unchanged). |
| 23 | `planar/basins.build_basins` (tunnel overlap refusal, owner id) | `t.source != "osm"` | **C**: a basin region overlapping a wall corridor is refused as overlapping a structure (by ORDER, unchanged). |
| 24 | `airport/door_wells`, `airport/sunken_roads` | floor plates | **C**: disjoint populations (Law C has no floor plate); unchanged. |
| 25 | `airport/rebake_plan` facility rule (05p/05q) | members deeper than the contact band | **C**: the kerb walls stay facility members / excluded; unchanged. |
| 26 | `law/model.TunnelObject`, `law/cutout_schema`, `law/tables`, `tests/auto_patch_v2/test_law_tables.py`, `test_tunnel_objects.test_law_register` | schema | **D/C**: `floor_plate_max_m2` removed, `bore_end_tolerance_m` added, `mouth_depth` datum `"floor_slab"`; `[cutout.wall_corridor]` schema `WallCorridor` (seat none; `ramp_grade ≤ max_ramp_grade = wall_corridor_ramp` cap; `max_authored_grade = garage_ramp` cap, checked at load). |

Twins re-pointed by the owner's law (not by convenience): `test_tunnel_objects.test_refusals_name_their_reason` (a floored wall is now a wall with a floor-slab depth), `test_v2lemd3.test_edge_wall_without_a_bore_is_refused_by_name` (an edge wall with no bore is no longer refused; the closed-no-road refusal replaces it), `test_law_tables` / `test_tunnel_objects.test_law_register` (the key set).

### §6b Closing measurement — lane `v2wallcorridor` (OTHH tile `+25+051`, engine v2, build tag `v2wc_close2`, rc 0, 739 s)

Head `a6a03ece` (main `188dd728` merged). Suite 743 (lane scope
`tests/auto_patch_v2` + `tests/test_harness.py`); full `tests/` 9,923 passed
with 12 pre-existing v1 reds this lane cannot touch (no v1 source edited)
plus 3 that this lane closed (two line-budget twins, one xdist flake).

**DEPTH (08l/08o) — every mouth kind reads `bore_datum_m` 5.10; no OTHH
wall object carries a floor slab (all skirts). Floor at the mouth −1.14 =
ground 3.962 − 5.10 throughout.**

| object | before (1.0.294) | depth now | floor@mouth | ramp total (inside walls / beyond) | grade | crest (seat handle) |
|---|---|---|---|---|---|---|
| `tunnel south west 2.obj@0` (the owner's deep site) | 10.0 m, floor −6.04, 196 m ramp | **5.10** | **−1.14** | 204.0 (140.2 / **63.8**) | 4.00 % | 10.00 |
| `tunnel_sw.obj@0` (its twin) | 5.0 m, floor −1.04 | **5.10** | **−1.14** | 180.0 (103.3 / 76.7) | 4.00 % | 5.00 |
| `tunnel1.obj@0` / `@1` | 9.55 m | **5.10** | **−1.14** | 248.3 (248.3 / 0.0) | 2.05 % | 9.55 |
| `tunnel middle - east/west.obj@0` | 5.0 m | **5.10** | **−1.14** | 192.0 / 200.3 | 4.00 / 2.55 % | 5.00 |
| `tunnel west 1/2/3.obj@0` | 5.0 m | **5.10** | **−1.14** | 35.6 / 221.3 / 221.3 | 0.00 / 2.30 / 2.30 % | 5.00 |

08o's ≈ 65 m expectation for the deep side is met (63.8 m beyond the
walls). Both bore mouths PAIR with the object (`replaced mouths of
[-9170, -9169]`); no closed-end fallback fired.

**SEAT STATIONS (08o).** `Z0` 3.962. Seat datum vs `Z0 − plate_y`:
`tunnel_sw` (unit:17) −1.0419 vs −1.038, **−0.004 m** (inside the 0.05 m
bar); `tunnel west 2` −0.000; `tunnel west 3` −0.000; `tunnel west 1`
−0.009. **DEVIATION, reported not decided:** the deep object
(`tunnel south west 2`, unit:7) computes a plate seat of **+0.492 m** and
the re-bake's own `below_threshold` rule (|Δ| < 1.0 m ⇒ the structure stays
at its authored y) declines to write it — so its crest keeps a 0.49 m
residual against 08o's 0.05 m bar. This is the two rules disagreeing, not a
depth or station error: on 1.0.294 the same object's datum sat 1.75 m BELOW
its own floor. The owner rules whether the plate seat is exempt from the
1.0 m write threshold.

**LAW C (08m/08n) — the inventory at OTHH (11 anchor families, 276 wall
bands, 73 pairs).**

| class | read | cut into the surface |
|---|---|---|
| `level` (open/open, two capless halves) | 30 corridors (60 halves) | — |
| `bay` (one closed end) | 13 | — |
| `garage_ramp` (descending wall bottom) | **0** | 0 |
| total corridors read | **43** | 23 `wall_corridor` tunnels |

Refused by name, 30: headroom under `min_headroom_m` 3.5 — 12; closed at
both ends (a sunken yard between four kerbs, no mouth) — 11; wall bottom
shallower than `min_wall_depth_m` 1.0 — 4; not two readable bands (a crest
plate 3.33 m thick in plan: a deck, not walls) — 2; **wall bottom at
348.5 % between stations, over `max_authored_grade` 25 % — 1**.

**DEVIATION, reported not decided (08n):** the owner's "a number of garage
ramps with the same pattern" has **no instance at OTHH** under the
wall-bottom reading. The one descending candidate,
`OTHH_Terminal_Parking_VCN_004.obj` at 25.257756, 51.614363, refuses loudly
at 348.5 % — a step in the authored wall bottom, not a ramp. The
`garage_ramp` law, role and twin are all in place and unexercised by a real
site; the owner reads the KML
(`.../v2wallcorridor/OTHH_wall_corridors.kml`, 163 placemarks) to say
whether that object is the ramp he means.

**Solve / verify.** Solve 17.6 s optimal; hard set infeasible, the 04t-1
IIS-scoped relaxation applied — 26 IIS rows, 12 relaxed, excess grade max
**0.0015** (worst over-cap factor 1.019 against the 2.5 bound), **no tier
demoted**. v2 verify **0 rows**. Re-bake: 107 units, **22 objects written**
(6 tunnel objects, 10 Drainage, 6 Dewatering) — **0 terminal-family
objects**, as the seat law requires. Base arms unmoved: LEMD 23 rows
(`body_sha 5476dfef821b`, byte-identical to the pre-fix arm), CYXY 0.

**Census (`census.py --no-cache`) — law-true 182.** One `terrace_joint_route`
(airside, pre-existing — the ONLY acceptance row) + 181 groundside
`within_shape`, every one `tunnel_ramp|tunnel_ramp`, grades **8.16 %–10.14 %**
(min/max over all 181; worst |de| 1.82 m).

Two instruments, one population, and the split is fully accounted:

* **8–10 %** is the limitation §6a row 17 pre-registered — the v1 oracle
  prices `wall_corridor_ramp` through its `tunnel_ramp` alias at
  `service_road`'s **8 %**, while the role's own cap is `max_ramp_grade`
  **10 %**. Lawful, mis-priced by the older instrument.
* **the 0.14 pp above 10 %** is the 04t-1 IIS-scoped relaxation this same
  build reports: 12 rows relaxed, **excess grade max 0.0015** (0.15 pp),
  worst over-cap factor **1.019** — i.e. ≤ 10.19 %, which bounds the
  observed 10.14 %. The v2 verify stamps those rows yielded-with-certificate
  and so reads **0**; the v1 census has no such stamp and re-reports them.

So the 181 rows are 8 %-alias rows plus the ruled last resort, not a Law C
defect — but the arithmetic above is the claim, and it should be re-checked
if the relaxation's excess ever grows.
## §7 Consumer census (owner 30l) — lane `v2seatfix`, written BEFORE editing (2026-09-08)

Two rulings land together (RULINGS 2026-09-08u (1) and (2)). Key: **P** =
the plate seat's own threshold (`rebake.plate_seat_min_delta_m` 0.05 m);
**R** = the oracle's reading of the two ramp roles at `max_ramp_grade`
0.10.

### §7a Readers of the plate-seat threshold (**P**)

| # | Consumer (file:symbol) | Reads | Ruling |
|---|---|---|---|
| 1 | `emit/rebake.seat` (the structure-seat branch) | `min_delta_m` for EVERY structure seat | **P**: the threshold is `plate_seat_min_delta_m` when `datum == DATUM_PLATE` (a tunnel wall's crest plate, a basin's floor plate), `min_delta_m` otherwise. 08f (d) is untouched: a unit under ITS threshold still STAYS at its authored y and is never handed to the cluster law; `structure_seat_threshold_exempt` still short-circuits both. |
| 2 | `emit/rebake.seat` (the flat-site deck branch, 08f (e)) | writes `below_threshold: flat site …` with no number | **P**: unchanged — that branch is a DECK verdict, not a plate reading. |
| 3 | `emit/rebake.seat` (the unit-level cluster roll-up, "every cluster moves less than `min_delta_m`") | `min_delta_m` | **P**: unchanged — a cluster is not a plate seat. |
| 4 | `emit/clusters.py` (`max_delta < rb.min_delta_m`) | `min_delta_m` | **P**: unchanged — the CLUSTER seat keeps the 1.0 m bar (v1's `DSF_OBJECT_BAKE_MIN_DELTA_M`, and the law-table twin still `c.eq`s it). |
| 5 | `model/rebake.counts` (`below_threshold` / `clusters_below_threshold`) | the `skip_reason` PREFIX | **P**: unchanged — the prefix is still `below_threshold: …`; only the number in the text differs. |
| 6 | `auto_patch/engine_v2._decision_from_seats` + the `[v2 rebake]` report line | `skip_reason`, and `min_delta_m` for the CLUSTER count in the line | **P**: unchanged (the line counts clusters). |
| 7 | `auto_patch/object_rebake.apply` | the decision's deltas | **P**: unchanged — the v1 writer applies NO threshold of its own to a v2 decision (`DSF_OBJECT_BAKE_MIN_DELTA_M` is read by v1's `object_anchor` seat pass only, which v2 does not run), so a 0.49 m plate write reaches the pack. |
| 8 | `law/rebake_schema.Rebake`, `law/structures.toml [rebake]`, `tests/auto_patch_v2/test_law_tables` | the key set | **P**: one new key, `0 < plate_seat_min_delta_m < min_delta_m` asserted. v2-only (v1 knows one threshold). |
| 9 | `tests/auto_patch_v2/test_v2othhseat` (d), `test_engine_v2_rebake`, `test_m6a_rebake` | the threshold's behaviour | **P**: the (d) twin's plate at +0.001 still stays (under 0.05); the new twin covers +0.492 written / +0.03 stays / a DECK unit at +0.49 stays. |

### §7b Readers of the ramp-role caps (**R**)

| # | Consumer (file:symbol) | Reads | Ruling |
|---|---|---|---|
| 1 | `emit/osm_adapter` (the oracle alias block) | `oracle_role`, `oracle_law`, and `role_cap` → `o4_grade_law_cap` | **R**: a role may now declare `oracle_cap` — the cap the ORACLE prices its pairs at, written in place of the role's face cap. The composition with a prior tag stays a MINIMUM. |
| 2 | `law/model.RoleSpec` + `load_tables` validation | the role fields | **R**: new optional `oracle_cap` (only with an `oracle_role`, > 0); `law/cutout_schema` asserts at load that both ramp roles' `oracle_cap` IS `cutout.wall_corridor.max_ramp_grade` — one number, checked, never a second spelling. |
| 3 | `law/precedence.toml` roles `door_ramp` / `wall_corridor_ramp` | `oracle_law = "service_road"` (8 %) | **R**: `oracle_law = "structure_ramp"`, `oracle_cap = 0.10`. `garage_ramp` is NOT changed — its authored cap is 25 %, no oracle law carries it and it has no site (08u (3)); its rows stay an instrument limitation, reported. |
| 4 | `auto_patch/config.ROLE_GRADE_LIMITS` | the v1 role→cap table the oracle judges by | **R**: one new entry `structure_ramp = STRUCTURE_RAMP_MAX_GRADE` 0.10 — the LAW NAME v2's ramp faces are priced under. No v1 shape ever carries the role (v1 emits no structure ramp), so every v1 patch reads exactly as before; no ruleset varies it. |
| 5 | `tools/check_grade._role_grade_limit` (`o4_grade_law` branch, then `min` with `o4_grade_law_cap`) | `ROLE_GRADE_LIMITS[<law>]` | **R**: no code change — the law name resolves to 0.10 and the cap tag no longer tightens it. Both readers of the resolver (`_check_within_shape`, `_pair_grade_limit`) are covered by construction. |
| 6 | `tools/check_grade._is_groundside` / `law_role` / `layout.GROUNDSIDE_ROLES` | the emitted `role` tag (`tunnel_ramp`) | **R**: unchanged — the alias keeps the ramps groundside; `structure_ramp` is never an emitted role, only an `o4_grade_law` value. |
| 7 | `tools/harness/census.py`, `tools/harness/oracle.py`, `check_grade.LAW_FAMILIES` | the census entry points | **R**: unchanged (the brief's constraint); the harness twins stay green. |
| 8 | v2 `constraints/structures`, `planar/wall_corridor_ramps`, `planar/door_ramps`, `verify/structures` (`role_cap`) | `rulesets.toml [common.roles]` — `door_ramp` 8 %, `wall_corridor_ramp` 10 % | **R**: unchanged. v2 verify stays the STRICTER instrument on a door ramp (8 % vs the oracle's 10 %); the oracle is the pair-frame cross-check, and the owner's ruling prices both ramp roles at the ramp ceiling there. Stated, not hidden. |
| 9 | `tests/auto_patch_v2/test_v2doorramp`, `test_v2wallcorridor`, `test_law_tables` (the divergence register) | `spec.oracle_law == "service_road"` | **R**: re-pointed to `structure_ramp` + `oracle_cap`. |
| 10 | `tests/test_harness.py` | the census twins | **R**: new twin — a synthetic `door_ramp` pair at 8.2 % reads 0 rows, at 10.5 % reads 1. |

### §7c Closing measurement — lane `v2seatfix` (OTHH tile `+25+051`, engine v2, build tag `v2sf_close`, rc 0, 630.1 s: vector 459.5 / mesh 11.9 / masks 8.7 / tile 149.5)

**The seat (P).** `unit:7` = `Objects/tunnels/tunnel south west 2.obj` — the
deep bore's mouth — is now WRITTEN: ground at the wall band (65 stations,
0 water, 0 off-mesh) 3.957 against the rendered plate (base −6.535 +
plate 10.000 = 3.465), delta **+0.4919 m**, datum `plate`, no skip. The
seated crest stands at **3.9569** against the site's Z0 **3.962** —
**0.005 m**, inside the 08o bar. The two `tunnel1` plate units below the
new bar STAY, and say so at it: `below_threshold: plate seat |+0.026| m <
0.05 m` and `|+0.020| m < 0.05 m`. Objects written **23** (main: 22) —
tunnels **7** (was 6: the one new write is this bore), Dewatering/Drainage
16, **0 terminal-family**, 0 reverted; 107 units, 14 baked, 90 below
threshold, 3 held. Shared repo UNCHANGED (full before/after snapshot).

**The oracle (R).** OTHH v2 verify **0 rows**. Census `--no-cache` on
`OTHH_auto.patch.osm`: **0 rows in all 29 law families** — the 181
groundside `tunnel_ramp|tunnel_ramp` `within_shape` rows at 8.2 % are
gone, and (on this base) the airside `terrace_joint_route` row is 0 too.

**LEMD** (`--base-arm` on the lane tree, tag `v2sf_LEMD`, rc 0, 220.6 s,
`body_sha 7c84e9b98c4a`, v2 verify 14): census **20 adjudicated** (airside
11, groundside 8, mixed 1). THE SAME PATCH replayed with the pre-fix tag
(`o4_grade_law=service_road`, the only difference — the geometry is
byte-identical) censuses **4,933**: **4,913 groundside
`tunnel_ramp|tunnel_ramp` within-shape rows at 8.02–8.04 % against the
8.00 % alias**, every one of them a corridor/door ramp built AT the 8 %
ramp grade and pushed over it by emit quantisation. The OTHH 181 was the
small end of this class; nobody had censused LEMD since Law C began
emitting there (v2wallcorridor's LEMD 23 is a BASE arm, cut before the
corridors existed). Attribution of 23 → 20 against that older base is
NOT claimed: it is a different tree, and no clean-tree LEMD control at
319f8700 was built (controls are shared, never rebuilt).
