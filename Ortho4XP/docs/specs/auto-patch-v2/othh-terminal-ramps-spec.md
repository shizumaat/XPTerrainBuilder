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
authored y (structures.toml:169, emit/rebake.py:382-391). **AMENDED by owner RULINGS 2026-10-07e (`design-surface-spec.md` §47 (7) AMENDED 2): an object-framed ramp takes its length and depth from the object and has no grade cap; `[cutout.door] ramp_grade` and `[cutout.wall_corridor] max_ramp_grade` are deleted.**

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
| `constraints/structures.py` | the ramp / void faces | Diff cap per tunnel: `cutout.door.ramp_grade` for a door, `tunnel.ramp_max_grade` else; the mouth pinned absolute (as an object corridor); a sunken road's EVERY station group pinned at the plate profile (senior); `structure_roles` += `door_ramp` | ids `door:` / `sunken-road:` are outside `[structures] datum_order` — `reconcile_datums` neither withdraws nor ranks them (no shared vertex with a tunnel or basin rim is expected; reported if the build shows one) **AMENDED by owner RULINGS 2026-10-07e (`design-surface-spec.md` §47 (7) AMENDED 2): an object-framed ramp takes its length and depth from the object and has no grade cap; `[cutout.door] ramp_grade` and `[cutout.wall_corridor] max_ramp_grade` are deleted.** |
| `precedence.toml` | — | role `door_ramp` (common, groundside, value, structure, `oracle_role = tunnel_ramp`, `oracle_law = service_road`), NOT in `[authority] order` (tier after the named, as an omitted governed role) | DEVIATION from §2's "`tunnel_ramp`-class face": `tunnel_ramp` is capped 4 % in BOTH instruments (rulesets / v1 `ROLE_GRADE_LIMITS`) — an 8 % ramp emitted under it is a violation by construction; the door ramp is its own role, priced 8 % by v2's verify (`role_cap`) and by the oracle through the existing `o4_grade_law` override (`ROLE_GRADE_LIMITS[service_road]` = 0.08) composed with `o4_grade_law_cap` = 0.08 |
| `rulesets.toml [common.roles]` | — | `door_ramp = { longitudinal = 0.080, transverse = 0.020 }`; loader cross-check `cutout.door.ramp_grade ≤ door_ramp.longitudinal` | one number, checked at load **AMENDED by owner RULINGS 2026-10-07e (`design-surface-spec.md` §47 (7) AMENDED 2): an object-framed ramp takes its length and depth from the object and has no grade cap; `[cutout.door] ramp_grade` and `[cutout.wall_corridor] max_ramp_grade` are deleted.** |
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
  the ramps leave the right side. **AMENDED by owner RULINGS 2026-10-07e (`design-surface-spec.md` §47 (7) AMENDED 2): an object-framed ramp takes its length and depth from the object and has no grade cap; `[cutout.door] ramp_grade` and `[cutout.wall_corridor] max_ramp_grade` are deleted.**
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

Measured by scout `othhunderpass` (KML `scratchpad/othhunderpass/OTHH_underpass.kml`; scripts beside it). The pack models the terminal's road underpass and its loading bays as KERB WALLS only — vertical faces 1.35–1.89 m under ground, no floor at any depth, a deck above at 4.3–4.5 m headroom. Law: `[cutout.wall_corridor]` — `min_wall_depth_m 1.0`, `min_width_m 6.0`, `max_width_m 20.0`, `min_wall_length_m 5.0`, `min_headroom_m 3.5`, `ramp_grade 0.08`, `max_ramp_grade 0.10` (when the ramp would enter airside pavement it stops at the pavement edge and steepens to this), `seat "none"`. **[AMENDED by RULINGS 2026-10-07b (2) / 07c (1): the ramp runs the full wall length and stops nowhere beyond it — `design-surface-spec.md` §47 (7) AMENDED.]** Mechanism: wall bands from vertical-only genuine components (`obj8` must keep zero-plan-area bands: `_bulk_polys` drops them today), paired per family into corridors, handed to `tunnel_walls.read_wall_lines` (kind "II") and `object_corridor` with `mouth_depth = "wall_bottom"`; closed ends by a crossing family face within `end_cap_open_m`; open ends = mouths with ramps at 8 % (site 1: NE 18.9 m to the apron → 10 %; SW 23.6 m, OSM −9214 yields onto it; site 2: 16.9 m). Basement cover gate replaced by the headroom test for corridors. Twins: two parallel bands 10 m apart 1.9 m deep under a deck → a corridor, floor at the wall bottom, two ramps; one band alone → nothing; bands 25 m apart → nothing; a closed end → one ramp; a ramp meeting airside pavement → stops and steepens to 10 %, refused loudly above it. Acceptance: OTHH tile: both corridors and the three bays emitted (floor z, mouths, ramp lengths and grades quoted), verify 0, no terminal object written; LEMD/CYXY unchanged.

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
| 12 | `planar/structures.build_structures` climb block (`fits`) | object corridors climb INSIDE the walls | **C**: a wall corridor never climbs inside its walls (the floor is the wall bottom): `fits = False`, `climb_from = hull_s`, the climb beyond at `ramp_grade`; a descending corridor has no climb (`climbs = False`). **[AMENDED by RULINGS 2026-10-07b (2) / 07c (1): the ramp runs the full wall length and stops nowhere beyond it — `design-surface-spec.md` §47 (7) AMENDED.]** **AMENDED by owner RULINGS 2026-10-07e (`design-surface-spec.md` §47 (7) AMENDED 2): an object-framed ramp takes its length and depth from the object and has no grade cap; `[cutout.door] ramp_grade` and `[cutout.wall_corridor] max_ramp_grade` are deleted.** |
| 13 | same — decks (`obj_ivals`, `deck_ivals`, `_pavement_deck_intervals`) | decks over the corridor | **C**: object decks and mapped bridges INSIDE the walls are not read (the deck above is the family's own roof — the headroom test replaces `bridge.clearance_m`); beyond the walls they are read as for any ramp; pavement decks as before. |
| 14 | same — `stop_at_pavement` / `_pad_hit` | door: every governed cell beyond the well | **C**: `stop_side = "airside"`: AIRSIDE cells (non-structure, non-runway) + building pads stop the ramp; groundside cells (a service road) are cut by it (08m (b)); host cells (the ones the corridor stands in) never stop it. After a stop the climb STEEPENS: `g' = rise / (s_top − climb_from)` ≤ `max_ramp_grade` → `design_grade = g'`, top pinned at the ground; else refused loudly. **[AMENDED by RULINGS 2026-10-07b (2) / 07c (1): the ramp runs the full wall length and stops nowhere beyond it — `design-surface-spec.md` §47 (7) AMENDED.]** |
| 15 | same — the uncapped-mouth strip | `not g.capped` → a grid strip beyond the mouth | **C**: only for kind `object` (a bore continuing underground); a level open/open corridor is TWO capless halves meeting at its midpoint (the `Tunnel` doc's own model), sharing the mouth line's vertices, exempt from the overlap refusal as siblings. |
| 16 | same — `hull_knives` | walls cut pads, the ramp beyond does not | **C**: the whole footprint cuts (walls + ramp), pads included: a pad over a ramp is nonsense; the ramp never crosses a pad it does not host (`_pad_hit` on pads still stops it). **Closed on the tile build (lane instance 2):** the knife guarded the WHOLE beyond-the-walls strip, so a pad the corridor HOSTS kept its `weld_to_touching_pavement` Flat over the ramp's own vertices — five `building5` pad flats gripped seven wall-corridor FLOOR vertices at OTHH and the ladder demoted `wall_corridor_ramp` by 1.392 m (the bays' full depth); the build refused. The knife now guards only the part of the strip lying in a NON-host pad. A pad cannot both host a ramp and hold it flat. Twin `test_a_host_pad_is_cut_by_the_ramp_beyond_the_walls`. |
| 17 | same — `ramp_role` | `door_ramp` / `tunnel_ramp` | **C**: `wall_corridor_ramp` (level corridors, bays, their climbs; cap `max_ramp_grade` 0.10) and `garage_ramp` (authored descending floors; cap `max_authored_grade` 0.25) — two new roles (`precedence.toml`, `rulesets.toml [common.roles]`), groundside, structure, oracle alias `tunnel_ramp` at `service_road`'s law. ORACLE LIMIT: v1's largest role cap is 8 % (`service_road`), and the alias composes as a MINIMUM — a wall-corridor ramp between 8 and 10 % and any authored garage ramp over 8 % is reported by the v1 census as `within_shape` although lawful; v2 verify reads the role's own cap. Reported as an instrument limitation, not hidden. |
| 18 | `constraints/structures.structures` | `source` branches; datum group `Flat` + mouth pin; descent `Diff` rows; top pin | **C**: `source == "wall_corridor"`: stations inside the walls (`s ≤ wall_length_m`) are SENIOR pins at `profile_z` (the wall bottom per station: level or descending, cut as authored); no datum `Flat`; beyond the walls the descent `Diff` rows at `wall_corridor.max_ramp_grade` and the top pin at the ground; the rim rows as for every structure. **[AMENDED by RULINGS 2026-10-07b (2) / 07c (1): the ramp runs the full wall length and stops nowhere beyond it — `design-surface-spec.md` §47 (7) AMENDED.]** **AMENDED by owner RULINGS 2026-10-07e (`design-surface-spec.md` §47 (7) AMENDED 2): an object-framed ramp takes its length and depth from the object and has no grade cap; `[cutout.door] ramp_grade` and `[cutout.wall_corridor] max_ramp_grade` are deleted.** |
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
0.10. **AMENDED by owner RULINGS 2026-10-07e (`design-surface-spec.md` §47 (7) AMENDED 2): an object-framed ramp takes its length and depth from the object and has no grade cap; `[cutout.door] ramp_grade` and `[cutout.wall_corridor] max_ramp_grade` are deleted.**

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
| 2 | `law/model.RoleSpec` + `load_tables` validation | the role fields | **R**: new optional `oracle_cap` (only with an `oracle_role`, > 0); `law/cutout_schema` asserts at load that both ramp roles' `oracle_cap` IS `cutout.wall_corridor.max_ramp_grade` — one number, checked, never a second spelling. **AMENDED by owner RULINGS 2026-10-07e (`design-surface-spec.md` §47 (7) AMENDED 2): an object-framed ramp takes its length and depth from the object and has no grade cap; `[cutout.door] ramp_grade` and `[cutout.wall_corridor] max_ramp_grade` are deleted.** |
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

## §12 Law C admission on AUTHORED depth (RULINGS 2026-09-10u) — lane `v2corridor`, 2026-09-10

**The clause.** A wall band is admitted only when its lowest vertex stands at least
`cutout.wall_corridor.min_wall_depth_m` (1.0 m) below the OBJECT'S OWN local zero —
`comp.min_y < −min_wall_depth_m` in the OBJ8's authored frame — never on rendered depth
(`dem_z(centroid) − (anchor_z + agl)`), which reads a pack's flat anchor plane as ground.
Two sites: `airport/wall_corridors.py:_bands_of` (the band) and the pair's floor gate
(`max(authored_depths) < min_wall_depth_m`, the wall bottom per station in the object's
frame — `_floor_profile` now returns `(floors, floors_y)`, the samples carrying their
authored `y` as a fourth column so a merged band spanning two placements still states it).
Rendered depth survives ONLY as a MEASUREMENT of an admitted corridor (`depth_m`, the
notes, the garage ramp's mouth-at-grade check, the ramp's floor = slab else 5.1 m, 08l/08o)
and as the ground-CONTACT clause (`basin.contact_band_m`): a band rendered wholly under the
terrain is buried and still refused — a terrain relation, kept as one.

**Consumer census (owner 30l).** Key: **A** = the admission.

| # | Consumer (file:symbol) | Reads | Ruling |
|---|---|---|---|
| 1 | `airport/wall_corridors._bands_of` (band admission) | `comp.min_y` vs the DEM | **A**: authored frame. THE single derivation site — no consumer vetoes. |
| 2 | `airport/wall_corridors.read_wall_corridors` (placement pre-screen) | `cache.y_range()[0] > −min_wall_depth_m` | unchanged — ALREADY the authored frame; the two now agree. |
| 3 | the pair floor gate (`depths` vs `min_wall_depth_m`) | the wall bottom vs the DEM | **A**: authored (`floors_y`); `grounds`/`depths` stay for the notes and `depth_m`. |
| 4 | the `descending` / garage branch (`shallow_depth > contact_band_m`) | the DEM at the shallow end | unchanged — a mouth AT GRADE is a terrain relation, not an admission. |
| 5 | `planar/wall_corridor_ramps.wall_corridor_groups` (ramp planner) + `airside_stops` | the records, `Group.profile`, `climb_from_s` | unchanged — fewer/more records only. |
| 6 | `planar/structures.build_structures` → `constraints/structures` (`WALL_CORRIDOR_ROLES`, `WALL_CORRIDOR_SOURCE`) | the emitted ramp rows | unchanged. |
| 7 | `pipeline/build` (`tn.source == "wall_corridor"`, the seat exclusion at `:620`) | the source tag | unchanged — `seat = "none"` still. |
| 8 | `verify/structures` (`wall_corridor_ramp` / `garage_ramp`) | the emitted roles | unchanged. |
| 9 | `emit/osm_adapter` + `law/precedence.toml:68` (`oracle_role = tunnel_ramp`) and the census families (`check_grade.LAW_FAMILIES`, `harness/census.py`) | the emitted role | unchanged — a count effect only, no law change. |
| 10 | door wells / sunken roads / basins (`planar/basins`, `airport/tunnel_objects`) | the same components, their own laws | unchanged — Law C's admission is not theirs. |
| 11 | `planar/__main__ --stage structures` (+ `--kml`) | `wall_corridors`, `wall_corridor_refused` | unchanged shape; the refusal now names the authored frame. |

**MEASURED, AND THE RULING'S PREMISE IS REFUTED AT LEMD** (structure replays, lane tree,
production DEM; `--stage structures`). LEMD wall corridors **17 → 38** (records 28 → 85):
the fix does NOT remove them, it adds. Why: the reader resolves each placement to the
PRISTINE pack (`*.obj.anchor_bak`), and there the witnesses ARE authored well below their
own zero — `CGVRW −1.435`, `GAVIA −2.617`, `NEWCO −1.757`, `EAT −1.642`, `EATzwei −1.499`,
`TAPSL −1.230`, `FLEDI −1.198`, `LEMDgrass −1.841` (m). 10u's figures (`CGVRW +0.945`,
`TAPSL +6.714`, `EAT −0.140`) are the LIVE `.obj` files — already REBAKED by our own anchor
seat (+2.38 m at CGVRW) — not the pack's authoring. Every LEMD placement also reads
`anchor_z = dem(xy) = 596.00`, `agl = 0`: the anchor plane is NOT under the terrain at the
object; the drift is per-COMPONENT (a shared-datum pack, LSGG class — components up to 4 km
from the anchor, where `dem_z(centroid) − base` reaches +9 m), which is what the authored
clause correctly removes. The count RISES because fewer bands mean fewer third-band vetoes
and fewer merges, so more pairs survive. OTHH: **73 records (43 corridors: 30 level ×2 +
13 bays), identical before and after** in class, axis, stations, floors and trench; four
records' notes move one point of end-cover (9 % → 8 %) because the discarded bands no longer
contribute vertical faces — no class or gate changes. **The discriminator LEMD-vs-OTHH is
therefore still open**: on authored depth both packs dig 1.2–2.6 m below their zero. What
separates them (measured, for the ruling): LEMD's pairs are foundations of two SEPARATE
buildings 3–12 m apart with no roof over 10 of 17 and a floor at one constant plane; OTHH's
carry a deck at +2.61 over 74 % of their length. Ruling requested before this lands.

## §12a Law C's THREE-PART admission (RULINGS 2026-09-10w) — lane `v2corridor` round 2, 2026-09-10 — SUPERSEDED by §12b: 10z DELETED the heading test and the deck clause (c); this section is kept for its measurement only

**The clause.** A Law C corridor is admitted only when ALL THREE hold: **(a)** its walls are
authored ≥ `min_wall_depth_m` below the object's own zero (§12, kept as NECESSARY); **(b)** a
ROAD ENTERS A MOUTH — an OSM `highway=*` way (`airport_small_roads` / `big_roads`) or a patch
road ribbon (`service_road` / `service_junction` / `groundside_pavement` cell) whose plan
geometry lies within `[cutout.wall_corridor] corridor_mouth_road_m` (15.0) of a mouth point AND
whose direction there agrees with the corridor axis within `corridor_mouth_road_deg` (45°);
**(c)** a DECK COVERS IT — the headroom reader's lowest near-horizontal plate over the trench,
inside Law C's bounds; **OPEN AIR IS NOW A REFUSAL** (it used to pass). One site:
`airport/wall_corridors.read_wall_corridors`'s pair loop, after the ends are read (the mouths
are the open ends; a garage ramp's mouth is its shallow end; both ends closed = no mouth).
`read_wall_corridors(..., classification=None)` takes the classification for the ribbons;
`_headroom` now returns `(headroom, witness)`; `stats.admission` states (a)/(b)/(c) with the
witness (way id / plate component) per CANDIDATE and a `nearest:` witness search on a (b)
refusal; `--stage structures` prints them.

**Consumer table — the rows §12's table touches.** 1 (`_bands_of`) unchanged. 2 (pre-screen)
unchanged. 3 (pair floor gate) unchanged — (a). NEW rows: 3b the pair loop's mouth/road test
(the single derivation site of (b)); 3c the headroom gate (the (c) refusal replaces the old
"open air passes"). 4 (garage `shallow_depth`) unchanged. 5–10 unchanged: fewer records only.
11 (`--stage structures` / `--kml`) gains `wall_corridor_admission`. `airport/osm.py`,
`classify/roles.py`, `airport/road_profile.py` are READ-ONLY consumers here (the mouth test
re-reads `airport.osm_ways` and the classification cells; it never touches `RoadProfiles`,
which does not exist yet at structure time).

**MEASURED — the OTHH bar FAILS; STOP (structure replays, lane tree, production DEM,
`--stage structures`; arms neutralise one clause at a time in ONE tree).**

| arm | LEMD corridors | OTHH corridors (records) |
|---|---|---|
| (a) only — main's law | 51 | **43** (73: 30 level ×2 + 13 bays) |
| (a) + (c) | 7 (all bays) | 36 |
| (a) + (b) + (c) — 10w as ruled | **0** | **25** (47) |

LEMD reaches 0 (bar met) but OTHH loses 18 corridors to (b) and 7 to (c) — the bar "OTHH's 43
identical" FAILS, so nothing is merged and the test is NOT weakened. WHY (b) fails at OTHH:
the road that enters those mouths is UNMAPPED (it runs under the terminal deck); what IS
mapped is the frontage kerb road CROSSING the mouth — witness search at each refused mouth
(4× the law window): `Terminal_Base_2_5` 432/433 (the 08u 77.8 m underpass) `patch service_road
cell 378 (route7)` 6.4 m **89° off**, `osm -9214` 11.7 m 90° off; `Terminal_Base_2_1` (the 08u
loading bays) ×5 at 10–21 m, 85–90° off; `Terminal_Parking_VCN_004/006` ×5 at 5–38 m, 83–89°
off; `Bridge_03_LOD0_003` ×5 with `osm -490` 50–57 m or nothing within 60 m; `Qatar_DutyFree`
×2 at 5–12 m, 89° off. The corridors (b) KEEPS are exactly the mapped-road ones
(`TerminalRoads_02/03/Parking_004`, `Bridge_02/06`: roads 1–15 m, 0–15° off). (c) costs OTHH
`Bridge_06_LOD0_002` ×5 and `Qatar_DutyFree_003` (no plate over those pairs' trenches).
Owner/spawner ruling needed before this lands: a loading bay IS entered from a road that runs
past its mouth, and an underpass's own road is not in OSM.

## §12b Law C's TWO-PART admission (RULINGS 2026-09-10z) — lane `v2corridor` round 3, 2026-09-10

**The clause as ruled.** A Law C corridor is admitted only when BOTH hold: **(a)** its
walls are authored ≥ `min_wall_depth_m` below the object's own zero (§12, kept), AND
**(b″)** THE MOUTH OPENS ONTO GROUNDSIDE — within `[cutout.wall_corridor]
corridor_mouth_road_m` (15.0) of a mouth there is a road in ANY HEADING (an OSM
`highway=*` way of `airport_small_roads`/`big_roads`, or a patch road ribbon:
`service_road` / `service_junction` / `groundside_pavement`), and the pavement face the
mouth opens onto — the NEAREST of those roads and of the classification's AIRSIDE
apron/taxiway faces (`AIRSIDE_FACE_ROLES` = apron, runway, the taxi family, `side ==
"airside"`) — is not airside. 10w's heading test (`corridor_mouth_road_deg`) and deck
clause (c) are DELETED, key and all; open air over the trench passes again, and the
headroom gate is back to its pre-10w form (`min_headroom_m` on a deck that IS there).
One derivation site: `read_wall_corridors`'s pair loop; `stats.admission` prints (a) and
(b″) with the witness per candidate and a nearest-road / nearest-face search on a refusal.

**Consumer table.** §12's rows 1, 2, 3, 4, 5–10 unchanged. Row 3b (the pair loop's mouth
test) is now the single derivation site of (b″); §12a's row 3c (the deck gate) is DELETED.
Row 11 (`--stage structures` / `--kml`) keeps `wall_corridor_admission`.

**MEASURED — BOTH BARS FAIL; STOP** (structure replays, one lane tree, production DEM,
`--stage structures`; the (a)-only arm neutralises (b″) in the SAME tree).

| arm | LEMD corridors (records) | OTHH corridors (records) |
|---|---|---|
| (a) only — main's law (arm in THIS tree) | **51 (85)** | **43** (73: 30 level ×2 + 13 bays) |
| (a) + (b″) — 10z as ruled | **26 (49)** — the bar is 0 | **39 (69)**: 30 level ×2 + 9 bays |

*LEMD keeps 26.* Its survivors are `LEMDgrass` 23 records, `NEWCO` 16, `LEMD79` 4,
`CGVRW` 2, `FLEDI` 2, `LEMD36` 2 — the 10u witness families themselves. Every one has a
REAL OSM service way 0.3–14.4 m from its mouth (`osm -5904/-5905/-5882` at NEWCO's cargo
kerbs, `-18749/-18750` and the `-5828` track along the grass fences, `-14060` at FLEDI,
`-18218` at CGVRW) and, at 24 of 26, NO airside apron/taxiway face within 15 m at all: by
the ruling's own test these mouths open onto groundside. The airside half fires exactly
once (`LEMD70`, both mouths INSIDE `apron cell 134`). Widening the face probe does not
save it: of 68 LEMD mouth probes only 30 have an airside face within 60 m (7 at 0 m, 4 at
~10, 3 at ~20, 9 at ~30, 3 at ~40, 1 at ~50, 3 at ~60) — 38 mouths have apron nowhere near.
The owner's "it's just apron up to the building" does not describe the LEMD cargo/grass
kerbs geometrically; what separates them from OTHH is still not stated by any clause tried.

*OTHH loses 4* (net; 10 candidates refused by (b″)): the `Terminal_Base_2_1` loading bays
`@3`/`@4` (nearest road `osm -9191` 21.2 m, `-9189` 19.7 m, 88–89° off — the road is there,
just BEYOND the 15 m window), `Terminal_Parking_VCN_004@2/a`+`@2/b` and `@1`/`@3` bays
(`osm -11187` 15.7 m, `-11198` 31.4 m, `-11193` 38.4 m), `Terminal_Parking_VCN_006`; two
`VCN_004@1/a,b` levels appear in their place. `Bridge_03_LOD0_003`'s five (nothing within
60 m) were already refused downstream at (a)-alone and cost nothing. NO OTHH mouth is
refused for reading AIRSIDE (`refused_airside_mouth` 0): the whole OTHH loss is the
15 m window against roads at 15.7–21.2 m, not the airside face.

**What a round 4 would need from the spawner**: either the window is a law value to be set
by measurement (25 m keeps `Base_2_1` and `VCN_004@2`; it does nothing for LEMD, which is
already road-adjacent), or the LEMD/OTHH discriminator is NOT the mouth's surroundings at
all — every clause tried (rendered depth, authored depth, road heading, deck cover, the
groundside mouth) has now been measured, and only the deck cover ever separated the two
packs (round 2: LEMD 7 vs OTHH 36) while costing OTHH seven real corridors.

## §12c Round 4 — the two PHYSICAL discriminators MEASURED (RULINGS 2026-09-10ab) — lane `v2corridor`, 2026-09-10: NEITHER SEPARATES THEM; STOP, nothing implemented

**The instrument** (`airport/wall_corridors.py`, `--stage structures` only —
`read_wall_corridors(..., measure=True)`, `stats.floor_probe`, printed as the `PROBE`
table; never a gate and never a build cost). Per CANDIDATE that reaches the mouth test
(the (a)-alone set, (b″) neutralised in this tree):

* **(i) FLOOR-vs-ROAD** — the nearest road within `corridor_road_level_m` (40 m) of a
  MOUTH (OSM `highway=*`, or a patch `service_road` / `service_junction` /
  `groundside_pavement` ribbon), its LEVEL at the point nearest that mouth — Ortho4XP's
  own longitudinal clamp (`airport/road_profile.clamp_way`, the profile every v2
  road-family vertex is fitted to) over the way's centreline (a ribbon: its own
  `face_axis`), the DEM where the core levels nothing (an asserted `bridge` / `tunnel`
  way) — minus the corridor's floor at that mouth; plus `ramp_reachable`
  (|Δ| ≤ `max_ramp_grade` × the corridor's length).
* **(ii) FLOOR SLAB** — a horizontal plate of the family thinner than
  `corridor_floor_slab_max_thickness_m` (0.5) lying within `corridor_floor_slab_tol_m`
  (0.5) of the floor inside the trench over `corridor_floor_slab_cover_min` (0.5) of the
  length.

**THE TABLE** (structure replays, ONE lane tree, production DEM; (a)-alone arm — LEMD 51
corridors / 52 candidates, OTHH 43 / 44, reproducing §12b's arm exactly).

| airport | placement | cand. | floor z | road level z | Δ (road − floor) | ≤1.5 m | ramp | slab | (b″) |
|---|---|---|---|---|---|---|---|---|---|
| OTHH | `Bridge_02_LOD0_002` | 3 | 1.84 | 3.96 | +2.03..+2.13 | 0 | 0 | **0** | 3 |
| OTHH | `Bridge_06_LOD0_002` | 16 | 1.84..2.22 | 3.96 | +1.72..+2.13 | 0 | 3 | **0** | 16 |
| OTHH | `Qatar_DutyFree_003` | 3 | −8.24..2.60 | 3.96 | +1.37..+12.21 | 2 | 1 | **0** | 3 |
| OTHH | `TerminalRoads_02_004` | 4 | 1.87 | 3.96 | +2.10 | 0 | 0 | **0** | 4 |
| OTHH | `TerminalRoads_03_004` | 4 | 2.07 | 3.96 | +1.89 | 0 | 0 | **0** | 4 |
| OTHH | `TerminalRoads_Parking_004` | 4 | 2.07 | 3.96 | +1.89 | 0 | 0 | **0** | 4 |
| OTHH | `Terminal_Base_2_1` (bays) | 5 | 2.57..2.61 | 3.96 | +1.35..+1.39 | 5 | 0 | **0** | 3 |
| OTHH | `Terminal_Base_2_5` (the underpass) | 1 | 2.07 | 3.96 | +1.89 | 0 | 1 | **0** | 1 |
| OTHH | `Terminal_Parking_VCN_004` | 4 | 2.24..2.25 | 3.96 | +1.71..+1.73 | 0 | 2 | **0** | 2 |
| LEMD | `Cargo-CGVRW` | 1 | 594.59 | 605.00 | +10.41 | 0 | 0 | **0** | 1 |
| LEMD | `Cargo-EAT` | 1 | 594.36 | 599.00 | +4.62 | 0 | 0 | **0** | 0 |
| LEMD | `Cargo-EATzwei` | 1 | 594.50 | 600.01 | +5.52 | 0 | 1 | **0** | 0 |
| LEMD | `Cargo-FLEDI` | 2 | 594.80..594.83 | 602.75..602.88 | +7.92..+8.07 | 0 | 0 | **0** | 2 |
| LEMD | `Cargo-GAVIA` | 1 | 594.68 | 602.00 | +7.32 | 0 | 0 | **0** | 0 |
| LEMD | `Cargo-NEWCO` | 9 | 594.38..594.68 | 594.00..597.06 | **−0.38..+2.41** | 5 | 4 | **0** | 8 |
| LEMD | `Munoza-LEMD70` | 2 | 594.28..594.63 | 563.00..565.08 | −31.28..−29.56 | 0 | 0 | **0** | 0 |
| LEMD | `Munoza-LEMD73` | 1 | 594.39 | — (no road ≤ 40 m) | — | 0 | 0 | **0** | 0 |
| LEMD | `Munoza-LEMD79` | 5 | 594.28..594.51 | 565.00 | −29.51 (+3 no road) | 0 | 0 | **0** | 2 |
| LEMD | `Ground-FSX-LEMD36` | 1 | 588.97 | 594.63 | +5.66 | 0 | 0 | **0** | 1 |
| LEMD | `Sim-wings-LEMDzaun` | 2 | 589.01..592.78 | 597.52..597.74 | +1.61..+8.50 | 0 | 1 | **0** | 1 |
| LEMD | `Sim-wings-SWbaume` | 1 | 589.01 | 597.12 | +8.11 | 0 | 0 | **0** | 0 |
| LEMD | `grass_FSX-LEMDgrass` | 25 | 594.45..594.98 | 586.00..594.64 | **−8.85..−0.16** (+12 no road) | 2 | 2 | **0** | 12 |

**(ii) THE FLOOR SLAB IS ZERO ON BOTH PACKS** — 0 of OTHH's 44 and 0 of LEMD's 52 (max
cover 0.00 at both): OTHH's kerb walls carry no floor at any depth (that IS Law C's
premise, module doc / 08u `bore_datum_m` 5.10) and neither does Aerosoft's. As a clause it
would refuse OTHH's 43 outright — the OTHH bar fails at once. **Refuted.**

**(i) NO TOLERANCE SEPARATES THEM.** OTHH's 43 real corridors sit in a tight band
Δ +1.35..+2.13 (the 44th, `Qatar_DutyFree_003@8/7`, is an 8.24 m pit at +12.21); LEMD's
spread runs −31.3..+10.4 with 16 candidates having no road within 40 m at all — but 15
land INSIDE OTHH's band:

| tolerance | OTHH kept (of 44) | LEMD kept (of 52) |
|---|---|---|
| 1.35 m | 2 | 5 |
| **1.5 m** (the proposed value) | **7** | **7** |
| 1.75 m | 13 | 12 |
| 2.0 m | 29 | 13 |
| **2.13 m** (the loosest that keeps all 43) | **43** | **15** |
| 2.5–5.0 m | 43 | 17–18 |

The bar is OTHH 43 / LEMD 0. Every value fails one side: 1.5 m costs OTHH 36 of its 43;
2.13 m keeps OTHH's 43 and LEMD's 15 (`NEWCO` 5, `LEMDgrass` 2, `LEMDzaun` 1 and the rest
of the cargo kerbs). Adding `ramp_reachable` as an OR only loosens it (OTHH 7 / LEMD 8
extra). **Refuted.** The pair (i) AND (ii) is 0 / 0 — refuted with it.

**WHY the reading cannot separate them (the instrument's own limit, stated for the next
round).** OTHH's production DEM is CONSTANT 3.96 m over the whole airport (73 of 73
mouths; Doha at sea level on a flat inset), so at OTHH "the road's level" IS the ground
everywhere and Δ degenerates to the corridor's depth under grade — a quantity
`min_wall_depth_m` already gates. At LEMD the DEM runs 563..605 while the Aerosoft pack's
floors sit on one anchor plane at 594.3..595.0, so Δ measures the pack's anchor offset
against the terrain: huge where the terrain is high (`CGVRW` +10.4, `LEMD70` −31.3), and
accidentally small (±2 m) wherever the terrain happens to pass through 594–597 — which is
exactly the cargo kerb / grass-fence belt. The difference between the two packs is not a
level relation at the mouth.

**WHAT LANDS FROM ROUND 4**: the instrument and its law values only (`corridor_road_level_m`,
`corridor_floor_road_tol_m`, `corridor_floor_slab_max_thickness_m`,
`corridor_floor_slab_tol_m`, `corridor_floor_slab_cover_min` in `structures.toml` +
`cutout_schema`), the `PROBE` table in `--stage structures`, and two twins holding the
reading honest (`test_v2corridor.py`: the probe states the road level minus the floor at
+2.0 / +6.0 and names the levelled profile; the slab reader finds a plate only where one
is authored). **The admission is UNCHANGED** — (a) authored depth + (b″) the groundside
mouth, exactly as §12b measured it (verified after: LEMD 26 corridors / 49 records). No
clause (b‴) is proposed; the next discriminator is the owner's.

## §12d Law C reads the SEATED frame (RULINGS 2026-09-10ad) — lane `v2corridor` round 5, 2026-09-10

**The clause.** Law C measures depth in the object's SEATED frame: the rebake puts the
object's zero on the LOCAL GROUND (09af-1), so a component's rendered z is
`dem(the component's own plan centroid) + agl + authored y` — never `anchor_z + agl + y`,
the pack's anchor plane (Aerosoft LEMD anchors components up to 4 km away, where the
terrain stands 9 m higher: a wall authored 2.6 m under its zero read 8–10 m "below ground"
and its ramp came out 160–200 m at 5 % instead of ≤ 52 m). This frame carries BOTH the
admission ((a) authored depth, §12, unchanged in value) and the corridor FLOOR, so the ramp
length — `rise / ramp_grade` with `rise = ground − mouth floor` — is the authored depth's.
The rendered-under-DEM reading is DELETED from Law C. **(b″) (the groundside mouth, §12b)
is DELETED, key `corridor_mouth_road_m` and all** — refuted in 10z/10ab. The round-4
measurement probe (§12c) stays, measurement only.

**The sites changed** (`airport/wall_corridors.py`): `_seat_base(o, xy, dem_z)` — the new
single derivation of the frame; `_bands_of` (the band's `pts` z column, and the ground-
CONTACT clause, which becomes `comp.max_y < −basin.contact_band_m`: in the seated frame the
object's zero IS the local ground); `_headroom` and `_floor_slab` (the same per-component
seat, so a plate and the floor under it stay in ONE frame — headroom is unchanged by a
frame shift); the pair loop's rule-6 block, deleted with `airside_faces`, `_nearest_face`,
`_nearest_roads`, `_road_at_mouth`, `_road_bearing_at`, `AIRSIDE_FACE_ROLES` and
`stats.roads` / `refused_no_road` / `refused_airside_mouth`. `mouth_roads` stays: the probe
reads it.

**Consumer rows touched** (§12's table). 1 `_bands_of` — the seated frame, the single site.
2 pre-screen (`y_range`) — unchanged, already authored. 3 the pair floor gate — unchanged
(authored y). 3b (b″) — DELETED. 4 the garage `shallow_depth` mouth-at-grade gate — now
seated (a garage's shallow end meets its own local ground, not the pack's plane).
5 `planar/wall_corridor_ramps` (the ramp planner) — unchanged code, SHORTER ramps: the
climb's rise is the authored depth. 6 `constraints/structures` (the ramp emitter) —
unchanged rows, shorter geometry. 7 `pipeline/build` seat exclusion, 8 `verify/structures`,
9 `emit/osm_adapter` + `precedence.toml:68` (`tunnel_ramp`) and the census families
(`check_grade.LAW_FAMILIES`, `harness/census.py`) — unchanged: a count/length effect, no
law change. 10 door wells / sunken roads / basins — unchanged (their own frames).
11 `--stage structures` — `wall_corridor_admission` keeps (a) alone.

**MEASURED** (four patch builds, one shared corpus: LEMD/OTHH at main `23a10aaf` —
`--base-arm`, tags `lemdmain5` / `othhmain5` — and at this branch, tags `lemda5` / `r5`;
DEFECTs 0 in all four).

*LEMD — the owner's 17 shapes (main emits EXACTLY 17 `wall_corridor_ramp`s), before → after
as `length m / rise m`* (the rise is the climb the ramp makes; at `ramp_grade` 8 % the run is
`rise / 0.08`): 213.3/10.52 → 101.9/1.62 · 173.5/11.41 → 58.2/1.57 · 167.6/11.38 → 79.8/5.73 ·
141.8/8.71 → 55.7/1.28 · 115.6/8.45 → 26.1/1.45 · 107.9/4.66 → 69.9/1.60 · 94.5/7.95 → GONE ·
69.8/2.23 → 60.0/1.51 · 60.3/1.70 → 50.1/0.89 · 55.8/1.37 → 45.9/0.57 · 51.9/2.97 → 36.0/1.89 ·
38.3/2.09 → 32.3/1.75 · 33.9/1.25 → 33.9/1.25 · 25.8/1.45 → 21.9/1.12 · 24.0/1.29 → 24.0/1.29 ·
22.2/1.09 → 22.2/1.09 · 9.5/0.32 → GONE.  Every rise now stands inside the ADMITTED authored
depths the same tree reads (`--stage structures`: 77 admitted, 1.01..6.99 m, median 1.37) —
the 5.73 m one is `LEMDzaun`'s 6.99 m authored wall — so every ramp is ≤ authored depth /
`ramp_grade`; the 10.5-11.4 m rises (a 130-140 m run) are gone.  The 20 OSM road bores are
unchanged (20 → 20), `basin_floor` 0 → 0, census adjudicated 268 → 208.
**The COUNT rises: 17 → 55 emitted shapes (corridors 17 → 76, bands 836 → 7,174).**  The
old frame refused most LEMD bands as BURIED (`comp.max_y < dem - anchor_z - contact_band`,
+8..+9 m under a shared-datum pack); in the seated frame that clause reads the object's own
zero and admits them.  They are SHORT (median authored depth 1.37 m) but numerous — the
owner's re-read (10ad) now decides whether 1.2-2.6 m cargo-door corridors are tunnels at
all, i.e. whether 10ac-1 (A) terminals-only follows.

*OTHH — 43 corridors, `by_class` 13 bay + 60 level, 24 emitted shapes: identical in count and
class; 18 of 24 shapes identical to 0.0 m.*  SIX shapes moved — the `Bridge_06` group
(25.2504..25.2517, 51.6163..51.6175): 60.5/2.07 → 52.4/1.43, 60.1/2.07 → 52.0/1.43,
46.3/2.21 → 38.4/1.58, 34.7/1.94 → 26.7/1.29, 34.4/1.92 → 26.7/1.26, 30.2/1.92 → 28.3/1.56.
Attribution: those placements' anchor plane stands ~0.64 m UNDER the local ground (OTHH's DEM
is not the constant 3.96 m at the bridge), so the rendered frame read 0.6 m of depth the pack
never authored — the walls there are authored 1.08..1.46 m down and the ramps now climb
exactly that.  One consequence downstream: `Bridge_06_LOD0_000`'s `deck_datum_z` 3.615 → 3.96
(the shorter ramp no longer covers the deck ring, so the datum falls back to the mesh) — the
rebake plan is otherwise identical (111 units, 948 members, ids and member counts equal).
Refusal population unchanged (10 ↔ 10, same sites, restated in the authored frame).
Census adjudicated 4 → 4.

## §12e Round 6 — the NARROW-CUT TEST MEASURED (RULINGS 2026-09-10af) — lane `v2corridor`, 2026-09-10: NO CLAUSE READS OTHH 43 / LEMD CARGO 0; STOP, nothing implemented in law

**The instrument** (`airport/below_zero.py` + `stats.narrow_cut`, printed as the `NARROW`
table; `--stage structures` only, never a gate and never a build cost). Per CANDIDATE
corridor, in the SEATED frame (§12d):

* **the WALL-PAIR SPACING** — the inner faces' distance (the corridor's width), and the
  stationed `width_m` beside it;
* **the BELOW-ZERO PERIMETER FRACTION** — the placement's plan geometry (every genuine
  component's triangles projected; a vertical face widened to
  `tunnel.object.wall_face_max_thickness_m`), the polygon of it holding the site, and the
  share of that polygon's exterior lined by geometry authored `min_wall_depth_m` or more
  under the object's OWN zero (`fsite`); `fobj` is the same share over EVERY polygon of the
  placement. *Authored plan BOUNDING BOXES were tried first and refused: a pack's component
  boxes overlap, so the union collapses a whole cargo area into one polygon and every
  candidate in it reads the same fraction (CGVRW 0.073 for all 17).*
* **the CUT WIDTH across the axis** against the footprint's own (`wr`), and — the fourth
  reading, added when the first three did not separate — the BELOW-ZERO END COVER (`ec`:
  does the below-zero geometry itself close an end, as a foundation ring would?).

**THE TABLE** (structure replays, ONE lane tree, production DEM, the §12d admission — OTHH
43 corridors / 62 candidates, LEMD 77 / 118, byte-identical before and after the module
split).

| airport | placement | cand. | spacing m | `fsite` | `fobj` | `wr` | `ec` max |
|---|---|---|---|---|---|---|---|
| OTHH | `Bridge_06_LOD0_002` | 15 | 11.88..15.14 | 0.87..0.95 | 0.91..0.94 | 0.98..1.00 | 1.00 |
| OTHH | `Terminal_Base_2_1` (bays) | 5 | 9.86 | 0.02 | 0.01 | 0.23..0.24 | 1.00 |
| OTHH | `TerminalRoads_Parking_004` | 4 | 10.00..10.07 | 1.00 | 1.00 | 1.00 | 0.04 |
| OTHH | `TerminalRoads_03_004` | 4 | 12.30..12.35 | 0.92 | 0.92 | 1.00 | 0.02 |
| OTHH | `TerminalRoads_02_004` | 4 | 11.45..12.06 | 0.99 | 0.99 | 1.00 | 1.00 |
| OTHH | `Terminal_Parking_VCN_004` | 4 | 6.13..11.37 | 0.11..0.37 | 0.11..0.26 | 0.31..1.00 | 0.15 |
| OTHH | `Qatar_DutyFree_003` | 3 | 12.17..12.61 | 0.66 | 0.83 | 1.00 | 1.00 |
| OTHH | `Bridge_02_LOD0_002` | 3 | 14.21..14.48 | 1.00 | 1.00 | 1.00 | 0.07 |
| OTHH | `Terminal_Base_2_5` (the underpass) | 1 | 9.85 | 0.99 | 0.02 | 1.00 | 0.00 |
| LEMD | `grass_FSX-LEMDgrass` | 31 | 6.12..19.03 | 0.60..1.00 | 0.20 | 0.98..1.00 | 0.96 |
| LEMD | `Airport_Cargo-CGVRW` | 17 | 6.47..15.89 | 1.00 | 1.00 | 1.00 | 1.00 |
| LEMD | `Airport_Cargo-NEWCO` | 9 | 9.53..19.38 | 1.00 | 0.97 | 1.00 | 1.00 |
| LEMD | `Airport_Munoza-LEMD79` | 5 | 8.54..17.62 | 1.00 | 0.80 | 1.00 | 1.00 |
| LEMD | `Airport_Cargo-GAVIA` | 4 | 8.03..12.99 | 0.65 | 0.68 | 0.96..1.00 | 1.00 |
| LEMD | `Airport_Cargo-FLEDI` | 2 | 6.73..6.99 | 1.00 | 0.94 | 1.00 | 1.00 |
| LEMD | `Airport_Munoza-LEMD70` | 2 | 7.38..14.02 | 1.00 | 0.49 | 1.00 | 1.00 |
| LEMD | `Sim-wings-LEMDzaun` | 2 | 9.76..10.78 | 0.05..0.37 | 0.05..0.52 | 0.00..0.90 | 0.41 |
| LEMD | `Airport_Cargo-LEMD64` | 1 | 19.04 | 1.00 | 0.79 | 1.00 | 0.00 |
| LEMD | `Airport_Cargo-EATzwei` | 1 | 17.18 | 0.97 | 0.60 | 1.00 | 1.00 |
| LEMD | `Airport_Cargo-EAT` | 1 | 17.22 | 1.00 | 0.60 | 1.00 | 1.00 |
| LEMD | `Airport_Munoza-LEMD73` | 1 | 8.04 | 0.79 | 0.31 | 1.00 | 0.00 |
| LEMD | `Sim-wings-SWbaume` | 1 | 8.06 | 1.00 | 1.00 | 1.00 | 0.12 |

**(i) THE SPACING DOES NOT SEPARATE THEM.** OTHH's 43 span 6.13..15.14 m; LEMD's 77 span
6.12..19.38 m. `corridor_max_width_m` at OTHH's own maximum (15.14 m, no margin) still keeps
57 of LEMD's 77 (54 of the 74 on the owner's witness families) — the cargo docks the owner
named sit INSIDE OTHH's band (FLEDI 6.73..6.99, CGVRW 6.47..15.89, GAVIA 8.03..12.99,
NEWCO 9.53, LEMD79 8.54). With a margin it is worse. **Refuted as a clause.**

**(ii) THE PERIMETER FRACTION DOES NOT SEPARATE THEM EITHER — and it is the OWNER'S
picture that fails, not the reading.** LEMD's cargo docks DO read as foundation skirts
(CGVRW/NEWCO/FLEDI/EAT/LEMD64/LEMD70 `fsite` 1.00 — the whole bottom below zero, exactly
10af). But so do OTHH's own kerb corridors: `TerminalRoads_Parking_004` 1.00,
`Bridge_02_LOD0_002` 1.00, `TerminalRoads_02_004` 0.99, `Terminal_Base_2_5` (the
underpass!) 0.987 — because a FREE-STANDING kerb wall's footprint IS the wall, so every
metre of its perimeter is authored below zero. `corridor_skirt_fraction` 0.5 keeps 9 of
OTHH's 43. The whole-placement denominator (`fobj`) only trades the error: it reads OTHH's
underpass 0.02 (right) but LEMD's `grass` 0.20 and `LEMD70` 0.49 (wrong). **Refuted.**

**(iii) THE CUT WIDTH across the axis is 1.00 at 17 of 22 families on BOTH packs** (the
below-zero geometry spans its own footprint by construction: the pair's two walls ARE the
footprint's two sides). Only OTHH's `Terminal_Base_2_1` bays (0.23) and
`Terminal_Parking_VCN_004` (0.31) read as notches in a larger building. **Refuted.**

**(iv) THE BELOW-ZERO END COVER does not separate them.** A foundation ring should close
its own ends; 11 of OTHH's 43 have an end closed below zero and 33 of LEMD's 77 do; NEITHER
pack has a candidate closed below zero at BOTH ends. **Refuted.**

**Every other geometric quantity overlaps too** (measured on the same arms): corridor
length OTHH 2.58..38.89 m vs LEMD 2.48..80.30 (71 of 76 inside OTHH's range); depth
1.07..12.21 vs 0.66..7.02 (69 inside); length/width aspect 0.18..3.95 vs 0.18..4.67 (74
inside); the thinner band's plan thickness OTHH 0.00..0.66 m vs LEMD 0.00..1.39 — 16 of
OTHH's own 43 corridors are ZERO-THICKNESS SHEETS (`TerminalRoads_02/03/Parking`), the same
sheet authoring as LEMD's cargo skirts.

**What round 6 DID attribute.** An IDEAL foundation skirt — four walls carried 2 m under the
object's zero with a roof over them — is ALREADY refused by 08n's own rule: its ring closes
both ends and Law C calls it "a sunken yard between four kerbs, not a corridor" (twin
`test_a_foundation_skirt_reads_the_same_fraction_as_a_kerb_corridor`). LEMD's cargo docks
survive because their skirts are single SHEETS whose bands RUN PAST the shed: `Cargo-CGVRW`
pairs bands of 21.8 m and 58.8 m 7.02 m apart into a 7.2 m corridor whose ends cover
0 %/1 %. The next clause to measure is therefore about the PAIR, not the placement: two
bands of one closed skirt ring are not a corridor however their overlap window falls.

**Nothing landed in law.** The instrument (`below_zero.py`, `stats.narrow_cut`) and its
twins landed; `wall_corridors.py` was 1,401 lines with them and is split under the
1,000-line law into `wall_geometry.py` (the band plan geometry, `WallBand`, the merge, the
seated frame) and `wall_corridor_probe.py` (the §12c probes) — OTHH's and LEMD's structure
records are byte-identical across the split.

## §12f Round 7 — THE WALL'S HEIGHT ABOVE THE OBJECT'S ZERO, and the TERMINALS-ONLY fallback (RULINGS 2026-09-10ao) — lane `v2corridor`, 2026-09-10

**The question (10ao, the owner's physical picture).** A KERB WALL is a low free-standing
wall: it rises from its floor to the deck it carries and no further (OTHH's terminal kerb,
+2.61 m). A cargo shed's foundation sheet is the bottom of a BUILDING WALL that rises 6–12 m
to a roof. So: per band, the wall's height ABOVE THE OBJECT'S OWN ZERO — its component's
`max_y`, and the top of the wall connected above it in the same placement (plan contact
within `emit.identity.min_distinct_spacing_m`, starting at or below the band's top).

**Instrument.** `airport/below_zero.read_wall_height` → `own_m` (the band's own component),
`step_m` (one step of the connected stack) and `connected_m` (the transitive climb); a
corridor's row carries the MAX over its two bands (a corridor with one building wall is a
building's corridor) and `conn_min`. `--stage structures` prints the HEIGHT table beside
the §12e NARROW table. Read at measure time only — a build pays nothing.

**MEASURED (one tree, the same replay as §12e; OTHH 43 admitted / LEMD 77, of which 73 at
the owner's cargo witnesses).**

| quantity | OTHH 43 (min / p50 / max) | LEMD cargo 73 | OTHH max + 0.5 keeps |
| --- | --- | --- | --- |
| `own_m` | 0.40 / 9.48 / **9.82** | −0.60 / 5.51 / 31.65 | OTHH 43/43, **LEMD cargo 64/73** |
| `step_m` | 0.40 / 9.48 / 14.15 | −0.59 / 6.65 / 37.10 | OTHH 43/43, LEMD cargo 69/73 |
| `connected_m` | 0.40 / 9.48 / 43.71 | −0.59 / 6.65 / 37.10 | OTHH 43/43, LEMD cargo 73/73 |
| `connected_m` (min of the two bands) | 0.40 / 8.10 / 15.70 | −0.59 / 6.49 / 18.54 | OTHH 43/43, LEMD cargo 71/73 |

**REFUTED.** The premise is false at OTHH itself: only 9 of its 43 accepted corridors are
LOW kerbs (`Terminal_Base_2_1/2_5` 0.59–0.63, `Qatar_DutyFree_003` 0.40–1.40). The other 34
stand at walls 5.91–9.82 m high — `Bridge_06_LOD0_002` 8.10–9.48, `TerminalRoads_02_004`
9.59, `TerminalRoads_03_004` 9.78, `Terminal_Parking_VCN_004` 9.60–9.82,
`TerminalRoads_Parking_004` 5.91 — i.e. exactly the range of LEMD's cargo walls
(`NEWCO` 6.63–10.45, `GAVIA` 2.29–10.83, `LEMD79` 4.55–10.30, `LEMD64` 10.46). No threshold
reads OTHH 43 / LEMD cargo 0; the best (9.82, OTHH's own maximum, no margin) keeps 63 of 73.
**Nothing landed in law.** The reading stays a measurement.

**THE FALLBACK, 10ac-1 (A) TERMINALS-ONLY — implemented, and it ships OFF.** A corridor is
admitted only where an `aeroway=terminal` way of the tile's `airports` feed lies within
`[cutout.wall_corridor] corridor_terminal_m` of a mouth (`wall_corridor_probe.terminal_polygons` /
`terminal_witness`; X-Plane's apt.dat carries NO terminal geometry — its rows are pavement,
lights and startup locations — so OSM is the only source, and an Overpass export flattens a
multipolygon relation into its member ways).

OTHH's terminals are MAPPED — ten `aeroway=terminal` ways (Main Terminal Building,
Concourses A–E, Emiri/Premium Terminal, …). The owner's 43 stand, from the nearest of them:

| family | n | nearest terminal |
| --- | --- | --- |
| `Terminal_Base_2_1` / `2_5` | 6 | **0.0 m** (Concourse C) |
| `Terminal_Parking_VCN_004` | 4 | 37.9 – 232.2 m |
| `TerminalRoads_02_004` / `03_004` | 8 | 179.7 – 219.2 m |
| `TerminalRoads_Parking_004` | 4 | 303.1 – 331.7 m |
| `Bridge_02` / `Bridge_06` | 18 | 422.0 – 589.5 m |
| `Qatar_DutyFree_003` | 3 | 1465.1 – 1485.4 m |

At the proposed 60 m the clause keeps **7 of OTHH's 43** and refuses 36 of the owner's own
accepted set; at LEMD it keeps 2 of 77. Any radius large enough to keep OTHH's 43 (1,486 m)
keeps every LEMD candidate inside 1,486 m of Terminal 1 too — 57 of 77, including
`CGVRW` (429–485 m), `FLEDI` (79 m), `GAVIA` (139–166 m), `NEWCO` (709–1,013 m). The
clause therefore lands with `corridor_terminal_only = false`: the witness and its distance
are REPORTED per candidate in `stats.admission` either way, and turning the key on is an
owner act. This is the one permitted gate (10ao): the alternative is deleting the owner's
accepted OTHH set.

## §12g LAW C IS A PER-AIRPORT AFFORDANCE (RULINGS 2026-09-10ap) — lane `v2corridor` round 8, 2026-09-10

**SUPERSEDED by §12h (owner RULINGS 2026-10-05g, 2026-10-05): Law C is unconditional under a four-clause general rule; the table, the key and the gate below are DELETED. Kept for its measurement.**

**The ruling.** After seven rounds no witness in the geometry or the map separates OTHH's
terminal kerb corridors from LEMD's cargo-dock foundations (§12–§12f). Law C — **kerb-wall
corridors AND garage ramps**, the two classes of `airport/wall_corridors.py` — therefore
becomes an AIRPORT-LEVEL AFFORDANCE a pack EARNS by the owner's sim read. Law A (door
wells, `airport/door_wells.py`) and Law B (sunken roads, basins) stay ON EVERYWHERE and
take no key; nothing else in the pipeline is gated.

**The table.** `law/airports.toml`, one table per ICAO, `[OTHH] kerb_wall_corridors = true`;
every airport the table does not name (and a law bound to none) takes every key false.
The schema is `law/airports_schema.py` (`Affordances`, `NO_AFFORDANCES`, `load_airports`,
plus `Resolution` / `resolve_ruleset` moved beside it under the 1,000-line file law);
`Law` gains an `icao` field that `Law.for_airport` fills, and `law.affordances` reads the
table. `law_tables_digest` globs `*.toml`, so a patch's provenance already changes with the
table; the freeze glob picks it up and `Ortho4XP.spec`'s count guard rises 8 → 9 (twinned
against the actual table count in `test_auto_patch_engine_dispatch.py`).

**The gate.** ONE site: in `read_wall_corridors`, on each CANDIDATE PAIR, **before clause
(a)** and before any wall line is read — `if not law.affordances.kerb_wall_corridors:` →
`stats.admission` gets `candidate … : law off for <ICAO>` and the pair is skipped. The
class (level / bay / garage_ramp) is decided later in the same loop, so no Law C class can
escape it. `stats.refused` stays geometry-only.

**DELETED with this section**: the 10ao terminals-only clause and its keys
(`corridor_terminal_only`, `corridor_terminal_m`, `terminal_polygons`, `terminal_witness`,
`TerminalWitness`) — 10ap closes 10ac-1 as (B), so the (A) mechanism is a refuted branch,
deleted rather than gated. Its measurement stays above in §12f.

**Closing builds (counts, materiality = counts).** LEMD `r8_lemd` vs main `2fb83ce3`
(control served from the artifact ledger, `v2pit2_base`): Law C shapes **17 → 0** — the
sidecar's `tunnel_objects` 17 → 1, the one survivor `tunnel-object:Bridge4.obj@0` (Law B);
`tunnel_ramp` shapes 38 → **21**, exactly the OSM road bores, unchanged; `basin_facilities`
0 → 0; v2-verify DEFECTs **0**; census adjudicated **555 → 394** (total 3,318 → 3,131).
OTHH `r8_othh` vs round 7 `1d3c0d78` (ledger `v2corr_r7_othh`): **43 corridors** (bay 13,
level 60 halves) from 69 pairs of 268 bands in 10 families, refused 26 — the patch body is
**byte-identical** (`e921644fe5cd5806…`, body sha `58b3045f42fe570b`), the rebake plan is
byte-identical (`493af639e41a5f25…`), the sidecar differs only in two wall-clock fields,
and v2-verify reads the same 4 rows with **DEFECTs 0**.

## §12h LAW C IS UNCONDITIONAL UNDER A FOUR-CLAUSE GENERAL RULE — THE OPEN MOUTH (owner RULINGS 2026-10-05e/05f/05g; findings `docs/mouthwitness-lawc-findings.md`; issue #396) — Fable (lane `lawcspec`), 2026-10-05

**Supersedes §12g.** The per-airport switch `law/airports.toml [OTHH] kerb_wall_corridors`,
`Affordances.kerb_wall_corridors` and the gate at the admission site are DELETED, and the
RECORDED set of `tests/test_no_airport_specific_code.py` falls to empty (05e: an airport is a
test case, never the scope of a fix). Law C — kerb-wall corridors AND garage ramps, the two
classes of `airport/wall_corridors.py` / `airport/wall_family.py` — is read at EVERY airport
under the rule below. Law A (door wells) and Law B (sunken roads, basins) are unchanged.
`Affordances.group_span_max_m` and its per-airport reading go with the table (05g (2)); the
pack-wide `[placement] group_span_max_m` stays, byte-identical ((8) below).

**The owner's picture (05f).** OTHH's terminal has thin walls running OUT from the building
below grade whose two ARMS enclose an OPEN mouth — a spot that needs a ramp. A loading dock is
a CLOSED extension: an object stands across the mouth between the arms, so no ramp is needed.
The scout measured that picture against the whole registered corpus (16 captures, the law
forced on everywhere, `scratchpad/mouthwitness/mw.py`): taken literally it does NOT separate
the cases (Aerosoft's LEMD cargo docks are two open-ended foundation sheets, 39 of 43 with
NOTHING across a mouth); what separates them is the composition below — every clause of which
is either already law or is the owner's witness read against the whole pack. Measured: OTHH
9 kept of 9; false corridors elsewhere 0 of 61 (LEMD 33, KASE 26, TFFJ 2); VHHH in (10).

**File references.** The implementation lands AFTER `feature/parallel-v2`, whose reader is
split into `airport/wall_family.py` (lane `pardoors` 5, `7377cc8c`). That file is on
`claude/parfinal` (`d41e65db`, the merge-ready head) and on `claude/pardoors`; it is NOT yet on
the `origin/feature/parallel-v2` ref itself (`1e30cbcf`, the parcluster head, predates the
split). Every `file:line` in this section is on **`claude/parfinal d41e65db`** unless it says
`main`; the implementing lane re-greps once on the branch it is actually handed.

### §12h (1) THE RULE, AS GEOMETRY

Every reading below happens in `read_family` (`wall_family.py:108-519`) on a CANDIDATE PAIR,
in the object's SEATED frame (§12d, RULINGS 10ad: `_seat_base`, `wall_geometry.py`), from
objects the reader already holds. Nothing is re-derived downstream (RULINGS 2026-08-30l).

* **ARM** = one `WallBand` of the pair (`wall_geometry.py:41-60`): a genuine component of
  vertical faces authored ≥ `[cutout.wall_corridor] min_wall_depth_m` (1.0) under the
  object's zero, plan length ≥ `min_wall_length_m` (5.0). The pair's inner faces are
  `tunnel_walls.read_wall_lines` kind `"II"`; stations by `stations_along`
  (`wall_family.py:215-216`). Arms of unequal length: the corridor is their OVERLAP window along
  the axis (`_overlap_along`, `:160`); the longer arm's run-on is not part of the corridor.
* **MOUTH SEGMENT** M_k = `end_line(k)` (`wall_family.py:354-362`): the segment across the
  trench at the last station of end k, from the left inner face to the right inner face; its
  length W = `half_l + half_r` (6.1–19.4 m on the corpus). Its WINDOW is the flat buffer of M_k
  by `[tunnel.object] end_cap_open_m` (2.0) — the same window rule 4's `_end_cover`
  (`wall_corridors.py:351-386`) reads.
* **ACROSS THE MOUTH** = ANY triangle of ANY placement of the pack — every family, the pair's
  own included; stock-library resources excluded exactly as rule 1 excludes them
  (`wall_family.py:98`, `obj8.is_stock_library_resource`) — whose plan (a vertical face → its
  plan segment, `wall_geometry._plan_segments`; any other face → its plan polygon) intersects
  the window, intersected with the window and projected onto M_k. The union of the projections
  over W is the COVER FRACTION of that end in that band; an end is CLOSED in a band when the
  fraction ≥ `[cutout.wall_corridor] end_cap_cover_min` (0.5). The rendered z of a triangle is
  `_seat_base(placement, component centroid, dem) + authored y`, as `_headroom`
  (`wall_corridors.py:475-562`) renders a plate.
* **TWO HEIGHT BANDS** at end k, with `floor_z(k)` the seated floor at that end's station and
  `ground_z(k)` the DEM at M_k's midpoint, or that end's station ground where the DEM is
  NaN there (the station grounds are already non-NaN or the pair was refused):
  * BELOW-GRADE: `floor_z(k) + ε .. ground_z(k) − ε` — the trench opening a vehicle would
    drive through;
  * AT-GRADE: `ground_z(k) + ε .. ground_z(k) + min_headroom_m` (`[cutout.wall_corridor]`,
    3.5) — a wall, door, fence, kerb, ground slab OR DECK standing across the mouth window
    under that ceiling closes it: a roof under `min_headroom_m` over the ground at the mouth
    is a dock's cover, not a canopy. A face whose lowest rendered point stands at or above
    `ground_z(k) + min_headroom_m` is a canopy or deck overhead: it closes nothing. A
    corridor's own deck (rule 5, measured from the FLOOR) closes its mouth only if it reaches
    the mouth window under that ceiling — the arms of a corridor run OUT beyond the deck
    (05f); a pit roofed to its mouth is a dock.
  * **ε = `[rebake] plate_seat_min_delta_m` (0.05 m)**, the smallest step the engine treats
    as visible (08u (1)). No alias key: an alias is a second value that can drift, and the
    meaning here IS that one. MEASURED DEPENDENCE (not ε): LEMD GAVIA 0/0's closer is
    `Cargo-LEMD63` comp 14, a 3 cm plate authored +2.26 m over its zero — rule 5's own plate
    (headroom 3.73) — 2.15 m over the mouth's DEM ground, 3.52 m over the floor, 0.82 of W:
    CLOSED under any at-grade ceiling above 2.15 m, OPEN under a floor-measured bar (floor +
    3.5 misses it by 0.02 m; measured, withdrawn). OTHH `Terminal_Base_2_5` 432/433's deck is
    2.42 m over ground (inside the band) and the mouth is open because the plate stops ≥
    `end_cap_open_m` short of the window (0.00 of W). These two sites are separated by whether
    the deck reaches the mouth — §12h (11). The
    scout's arm used 0.10 and an at-grade ceiling of 4.0; 0.05 / 3.5 are the law values and
    the implementing lane's `--stage structures` must reproduce the (2) table under them.
    `[emit.identity] min_distinct_spacing_m` (0.5) is NOT ε.
* **W1s — THE OPEN MOUTH (the owner's witness).** An end is an OPEN MOUTH iff it is open
  under rule 4 (no FAMILY face across it, as today) AND its BELOW-GRADE cover < 0.5 AND its
  AT-GRADE cover < 0.5 over ALL placements. W1s holds iff the candidate has ≥ 1 open mouth.
* **W3 — THE ARMS RUN OUT FROM A BUILT STRUCTURE.** Holds iff rule 5's headroom witness
  returned a plate (`_headroom` → `plate_plan is not None`: a deck over the trench) OR some
  end k is closed by an ABOVE-GRADE WALL: the AT-GRADE-band cover at end k, counting only
  faces whose rendered z_max ≥ `ground_z(k) + [basin] contact_band_m` (1.0) — a face reaching
  a full contact band over the ground is a wall, not a kerb cap — is ≥ 0.5, any placement.
  Exact computable form: `W3 = (plate_plan is not None) or any(wall_cover[k] >= end_cap_cover_min
  for k in (0, 1))` where `wall_cover[k]` is the projection union over the AT-GRADE-band hits
  at end k restricted to `z_max >= ground_z(k) + contact_band_m`. (The scout's equivalent
  "trench ⊕ end_cap_open_m meets `obj8.above_grade_footprint`" was NOT measured; it is not the
  form.)
* **FIELD — THE OPEN MOUTH STANDS ON THE FIELD.** The midpoint of an open mouth (W1s) lies
  within `[tunnel] mouth_standoff_m` (150) of the CLASSIFIED COVER — the cover half of §29
  (1)'s mapped-tunnel test, the predicate of `structure_approach.FieldRegion.on_cover`
  (`dwithin standoff_m` over the cells' polygons), carried into the `airport` layer as
  `wall_mouth.FieldCover` — the layer order forbids `airport` importing `planar` — and held
  equal to it by a twin. The cover is the classification's cells
  alone (`[Polygon(c.ring, c.holes) for c in classification.cells]`, the expression
  `planar/structures.py:165-166` builds — factor it into ONE helper
  `structure_approach.cover_polygons(classification)` and call it from both sites); the
  roofed tunnel corridors' footprints §29 (1) adds are not known when the walls are read and
  are not needed (measured: OTHH's 9 stand 0.0–9.6 m from the cells). The approach corridor
  and the runway band of `FieldRegion.holds` are NOT part of FIELD (not measured; a kerb
  corridor is not a portal seen on approach).
* **R — ADMISSION.** A candidate is ADMITTED iff (a) authored depth [existing, 10u] ∧
  (d) `h_own ≤ max_wall_height_m` [existing, 27a (3)] ∧ rule 3 [existing] ∧ rule 4 has ≥ 1
  open end [existing] ∧ rule 5 headroom [existing] ∧ FIELD ∧ W1s ∧ W3. R only REFUSES; an
  admitted record's every field is built by unchanged code.

**Values — every one an EXISTING key (verified on `claude/parfinal`):**

| value | key | where |
| --- | --- | --- |
| window along the axis, 2.0 m | `[tunnel.object] end_cap_open_m` | `law/structures.toml:134`; read `wall_family.py:363-366` |
| cover fraction, 0.5 | `[cutout.wall_corridor] end_cap_cover_min` | `structures.toml:325`; `wall_family.py:368` |
| at-grade ceiling, 3.5 m | `[cutout.wall_corridor] min_headroom_m` | `structures.toml:360`; `wall_family.py:432` |
| ε, 0.05 m | `[rebake] plate_seat_min_delta_m` | `structures.toml:673`; `law/rebake_schema.py` |
| field standoff, 150 m | `[tunnel] mouth_standoff_m` | `structures.toml:13`; `structure_approach.py:325` |
| kerb bar (d), 3.0 m | `[cutout.wall_corridor] max_wall_height_m` | `structures.toml:359`; `wall_family.py:343` |
| wall-at-end bar, 1.0 m | `[basin] contact_band_m` | `structures.toml:588`; `wall_family.py:467` |
| horizontal / vertical face | `[tunnel.object] plate_normal_y_min` 0.7 | `structures.toml:76`; `wall_family.py:431` |

No new law value. No new toml key.

**The class, on the COMPOSED openness (an extension of the findings — no corpus instance
changes).** Today `closed[k]` is rule 4's family cover alone (`wall_family.py:368, 385,
487-517`). Under R an end is OPEN iff it is open under rule 4 AND under W1s (both bands < 0.5
over all placements). The class reads that composed openness: two open ends → `level` (two
halves); one → `bay` at the open end; none → REFUSED by W1s ("no open mouth"). A level pair
whose one end a FOREIGN placement closes is a bay — a half climbing out of a closed end would
ramp into that object. At OTHH every rule-4-open end of the 9 is W1s-open (table (2)), so the
9 records are identical; nowhere else on the corpus does a composed-closed end survive the
other clauses. For the DESCENDING class the mouth is the SHALLOW end alone (`:381-383`); its
deep end is closed by the garage whatever crosses it, and W3 reads the deep end as the
closed end (plate = the garage deck, or a wall ≥ 0.5 of W there).

### §12h (2) WHAT THE CLAUSES READ ON THE CORPUS (the scout's tables, the law values' basis)

Population A — today's law with the key forced on everywhere; positives = OTHH's 9, negatives =
the 61 live candidates at LEMD / KASE / TFFJ (every other registered capture: 0 live).

| clause | OTHH kept / 9 | LEMD / 33 | KASE / 26 | TFFJ / 2 | TP / FN / FP / TN |
| --- | --- | --- | --- | --- | --- |
| W1 (below-grade band only, the literal witness) | 9 | 32 | 23 | 2 | 9 / 0 / 57 / 4 |
| W1s (both bands) | 9 | 31 | 5 | 0 | 9 / 0 / 36 / 25 |
| W3 | 9 | 2 | 24 | 2 | 9 / 0 / 28 / 33 |
| FIELD | 9 (0.0–9.6 m) | 33 (0–135.5 m) | 0 (3,900–4,370 m) | 0 (560–594 m) | 9 / 0 / 33 / 28 |
| W1s ∧ W3 | 9 | 0 | 3 | 0 | 9 / 0 / 3 / 58 |
| **R = (d) ∧ W1s ∧ W3 ∧ FIELD** | **9** | **0** | **0** | **0** | **9 / 0 / 0 / 61** |

Population B (kerb test (d) neutralised, the 10ap framing: OTHH 44 / LEMD 76): no mouth clause
reads 43/0 — the cargo docks are open-mouthed sheets; (d) is what reads them and 27a (3) made
it law. The mouth witness alone would ADMIT the corridors the owner's #12 read rejected
(`TerminalRoads_03_004` 11–14 at 25.2575296, 51.6120308: 0.02/0.02 both ends, walls 9.78 m),
so W1s composes with (d), never replaces it. The 61 false corridors: LEMD 31
`grass_FSX-LEMDgrass` buried grass-billboard lattices (W3 refuses: no deck, no wall), 1
`Cargo-GAVIA` 0/0 bay 24 (W1s: its own roof `Cargo-LEMD63` comp 14, a 3 cm plate authored +2.26 m, 2.15 m over the mouth's ground, reaches its mouth), 1 `Sim-wings-SWbaume` 117
(W1s: the ground slab fills it); KASE 26 — one UUID-named city-block object 3.9–4.4 km from
the field (FIELD refuses all 26; W1s ∧ W3 alone keeps 3); TFFJ 2 `industrial_1_1` 560–594 m
off (W1s and FIELD both refuse). OTHH's 9 admitted today: `Qatar_DutyFree_003` ×3 (own
0.40–1.40 m), `Terminal_Base_2_5` 432/433 (the 08u underpass, headroom 4.31), `Terminal_Base_
2_1` ×5 bays (own 0.59–0.63) — W1 ✓ W1s ✓ W3 ✓ FIELD ✓ at every one; void occupancy between
the arms 0.00–0.10.

### §12h (3) DEGENERATE CASES

| case | reading under R |
| --- | --- |
| one arm only | no pair (rule 2 unchanged): nothing. |
| arms of unequal length | the records end at the terminal STATION (where the shorter wall ends); rule 4's `end_line` and the mouth segment M_k stand at the MIDLINE's end, half the run-on beyond that station (unchanged: OTHH's identity bar; owner question E 1 — on the corpus one OTHH record's class depends on it). |
| roll-up door mesh / fence / kerb / step across the mouth | a face in the AT-GRADE or BELOW band covering ≥ 0.5 of W → that end CLOSED. A 0.15 m kerb at grade crosses `ground + ε` → CLOSED (owner question (12) Q1). |
| jet bridge across the mouth | underside above `min_headroom_m` → not in the band; its legs cover < 0.5 → OPEN. |
| canopy / deck overhead | underside ≥ ground + min_headroom_m, or the plate stops short of the window: OPEN; a deck reaching the window under that: CLOSED (LEMD GAVIA 0/0) |
| ground slab object at grade across the mouth | CLOSED — the pack says ground is there. LEMD SWbaume 117 (`Ground-FSX-LEMD85` 1.00, both mouths). |
| open at both ends | `level`, two halves, as today — PROVIDED W3 (a deck over it: OTHH's underpass). Two bare walls under open sky with open ends are a ditch or a fence line → REFUSED by W3 (LEMDgrass, 31 of 31). |
| closed at both ends (family faces) | REFUSED by rule 4 as today ("sunken yard": NLWF's 14 foundations, KASE 2,073 pairs). |
| closed at both ends (one by a foreign placement) | REFUSED by W1s ("no open mouth"). |
| garage ramp (descending) | the ONE-MOUTH form: W1s at the shallow end; W3 at the deep end (garage deck plate or wall); FIELD at the shallow end. No admitted garage ramp exists on the corpus (08u (3) stands): GEML `GEHM_01` 180/236, 35.301954, −2.943986 (shallow end 3.18 m under ground, refused as today). |
| a candidate with no classification handed | FIELD NOT READ — see (4): the line says so, `stats.field_read` is False, and the build path can never take it. |

### §12h (4) THE SINGLE ADMISSION SITE, THE ORDER OF CLAUSES, THE LINE

ONE site: the pair loop of `read_family` (`wall_family.py`); the three clauses are
`airport/wall_mouth.admit` (the pack-wide index `MouthIndex`, `FieldCover`, `WallField`,
re-exported from `wall_family`), called from that loop alone. The gate at `:180-204`
("law off for …") is deleted; no clause is evaluated anywhere else and no consumer vetoes.
The EXISTING clauses keep their order and their refusal texts (today's `stats.refused` lines
are unchanged for every candidate they refuse); the three NEW clauses follow rule 5, cheapest
refusal first:

0. STEP 0, the family FIELD gate: with a field handed, the CONVEX HULL of the members'
   `plan_bbox`es (every mouth midpoint lies within `max_width_m/2` of it) is tested once — no
   cover polygon within `mouth_standoff_m + max_width_m/2` of the hull → the family is refused
   WHOLE by one line naming the distance, no band read, `stats.off_field_families += 1`; a
   family on the field is read as before. Exact by construction, a function of the family's
   members and the field alone (pooled = serial). (Review `docs/lawcreview-12h.md` (B) and
   `docs/lawcreview-12h-reruling.md` 2, HARD LAW §6. The line, in `stats.refused`:
   `family {fam_name} ({n} members, {resource}): off the field — nearest cover {d:.1f} m (> mouth_standoff_m {standoff:g} + max_width_m/2 {margin:g}); no band read`
   — polygon distance to the hull, never centroids; `{resource}` is the first member's. A
   gated family counts in none of `stats.families / bands / pairs`. No field → not applied
   (FIELD not read). Measure mode is NOT exempt. The on-field clause order below is unchanged,
   so every on-field refusal text is as before.)
1. rule 1 bands, rule 2 pair, (a) authored depth, (d) kerb height, rule 3 grade / descending,
   rule 4 family end covers (`covers`, `mouth_ks`), rule 5 headroom (`plate_plan`), and for a
   DESCENDING pair the shallow-end-at-grade test (`shallow_depth ≤ contact_band_m`, existing:
   `no mouth at grade`, its `@k` spent) — as today, BEFORE any mouth query;
2. **FIELD-pre**: for each rule-4-open end, `field.on_cover(Point(midpoint of M_k))`; none on
   the field → `REFUSED by FIELD`. One `dwithin` query per end on the cells' STRtree; the
   KASE city block (3,695 pairs, 3.9 km off) and TFFJ's two never reach a mouth query.
3. **THE MOUTH QUERY**, once per end (BOTH ends — W3's wall test reads the closed end too):
   the pack-wide index (5) returns every component meeting the window whose seated z-range
   meets `floor_z(k) + ε .. ground_z(k) + min_headroom_m`; its triangles are split into the
   two bands and projected; the result per end is `below_cover`, `at_grade_cover`,
   `wall_cover` (the at-grade hits with `z_max ≥ ground + contact_band_m`) and the CLOSER per
   band — the placement and resource with the largest projected span, its span fraction and
   its rendered z range.
4. **W1s**: the composed-open ends = rule-4-open ∧ below < 0.5 ∧ at-grade < 0.5. None →
   `REFUSED by W1s`. Then FIELD on the composed mouths: none of them on the field →
   `REFUSED by FIELD` (the FIELD-pre set is a superset, so this is reached only when a
   FIELD-pre-open end was W1s-closed). FIELD is a location clause of the candidate; it never
   closes an end — a level pair stays level however far its second mouth stands from the
   cover.
5. **W3**: `plate_plan is not None` (free) else `wall_cover[k] ≥ 0.5` at some end. Neither →
   `REFUSED by W3`.
6. The class on the composed openness ((1) last paragraph); the records as today.

**THE LINE** (`stats.admission`, one per candidate reaching rule 2, stopping at the first
refusal; `python -m auto_patch_v2.planar ICAO --stage structures` prints it under
`wall_corridor_admission`, and `v2_solve_replay --from planar` reaches it through
`planar.build`):

    candidate {name} bands {A}/{B} at {site}: (a) admitted — wall bottom authored {d:.2f} m under the object's zero; (d) kerb {h_own:.2f} m; ends family {c0:.0%}/{c1:.0%}; headroom {open air | {h:.2f} m ({plate witness})}; FIELD end {k} {dist:.1f} m of cover; MOUTH end 0 below {b0:.2f} / at-grade {a0:.2f} (closer {resource}@{placement} {frac:.2f} of W, z {zmin:.2f}..{zmax:.2f} — the larger of the two bands' closers, `none` when no face met the window; both bands' closers are in the `narrow_cut` row `mouth_closers`), end 1 below {b1:.2f} / at-grade {a1:.2f} (closer …); W1s open end {k}; W3 {plate ({witness}) | wall at end {k} {frac:.2f} of W, z_max {h:+.2f} m over ground} -> ADMITTED {level | bay | garage_ramp}
    candidate … ; FIELD REFUSED — nearest cover {dist:.1f} m from end {k} (> mouth_standoff_m 150)
    candidate … ; W1s REFUSED — no open mouth: end 0 below {b0:.2f} / at-grade {a0:.2f} (closer …), end 1 …
    candidate … ; W3 REFUSED — open air, no wall at either end (at-grade wall cover {w0:.2f} / {w1:.2f})
    candidate … ; FIELD not read (no cover handed) — W1s …; W3 … -> ADMITTED {class}
    candidate … ; headroom … -> REFUSED — a descending pair whose shallow end lies {d:.2f} m under the ground: no mouth at grade

(the `narrow_cut` row of such a pair is not `admitted`)

Every clause names its witness and its closer, so a sim read of a wrong corridor can be
attributed from the line alone. `stats.narrow_cut` rows gain the same numbers (`field_m`,
`mouth_below`, `mouth_at_grade`, `mouth_wall`, `mouth_closers`, `w1s`, `w3`, `field`) for
`--json`; `WallCorridorStats` gains `field_read: bool` and `field_cells: int`.

**FIELD needs the classification at structure time.** `read_wall_corridors(airport, objects,
cache, law, classification=None, measure=False)` (`wall_family.py:551`) already takes it (the
`measure` probe's road ribbons); `planar/build.py:223` calls `wall_corridor_reads(airport,
objects, cache, law)` WITHOUT it and `pack_reads(…, walls=True)` (`:215`) hands the pool
nothing of it. The rule: the wall corridors are read ONCE per build under the cover of the
classification handed to the FIRST `planar.build` (`pipeline/build.py:665`); the ribbon-free
second pass (`:1061-1064`, #100 (c)) reuses that reading through the existing memo
(`pack_reads._store`, `:134-146`), exactly as today. `planar/build.py` derives ONE
`WallField(polys, standoff_m)` (a frozen two-field record in `wall_family.py`: the cells'
polygons by `cover_polygons(classification)`, `[tunnel] mouth_standoff_m`) and hands it to
`pack_reads(…, walls=True, field=…)` → `_read` → `reader_work.begin(…, field=…)` → the
pool's `setup` args → `ReadWorker.field` → `wall_reader(a, cache, law, field=…)`, and to
`wall_corridor_reads(…, field=…)` for the one-core read; `wall_reader` builds
`FieldRegion(field.polys, field.standoff_m)` once per process (an STRtree does not cross a
pool; the polygons do). `field=None` is lawful only for a caller that has no classification
(synthetic twins without one, `tools/planar_read_arm.py --no-field`): FIELD is then NOT READ,
every line says so and `stats.field_read` is False; `planar_read_arm` hands the capture's own
cover by default and hashes `wall_records` (the records alone) beside `wall_corridors`
(records + stats). The BUILD path always hands one; the structures
replay (`planar/__main__.py:371`) hands `cl`; a twin asserts `planar.build` reads the walls
with `field_read is True`.

### §12h (5) THE PACK-WIDE MOUTH INDEX AND THE BUILD-TIME IMPACT (HARD LAW §6)

**The index.** One STRtree over `PlacedObject.plan_bbox` (`obj8.py:599`) of every placed,
non-stock object of the pack, built LAZILY on the first mouth query and held on the
`WallReader` (`wall_family.py:46-62`) — one per process, never per family, like `to_ll`. A
query returns the placements whose bbox meets the window; for each, `cache.component_bounds`
(`obj8.py:495`) is rotated into the frame and only the components meeting the window AND the
band in seated z (`_seat_base(o, comp centroid, dem) + min_y/max_y`) have their triangles
read — the walk `_headroom` (`wall_corridors.py:505-556`) already makes, over the hits instead
of the family's members. Vertical triangles → `wall_geometry._plan_segments`; others →
`shapely.polygons`. Nothing is cached across queries but the tree.

**Cost (MEASURED — lane `lawc396`; HARD LAW §6 review `docs/lawcreview-12h.md` (B)).** 0.69 s
one-core for OTHH's 9 candidates (the index built once per process); KASE 6.1 → 15.7 s before
the gate, the gate's bar ≤ base. With the gate landed (lane `lawc396b`, one core, the
registered captures): KASE 0.16 s, TFFJ 1.6–1.9 s (4.8 before), VHHH 18.0 s (22.9 before),
OTHH 86.6 s (90.5–91.0 before; base 92.5), LEMD unchanged (no family off the field).

**The family FIELD gate ((4) step 0) in a pool.** It is a pure function of the family's own
members and the field, so pooled = serial holds and the intake is unchanged; a gated family
costs one `dwithin` query and reads no band. Counter: `WallCorridorStats.off_field_families`,
summed in `assemble`.

**In a pool worker (the parallel branch).** A wall task is one FAMILY (`reader_work.py:
11-15, 444-446`); the worker already holds EVERY placed object (`begin`, `:472-473`,
`list(objects)` crosses) and the parsed resources it needs (`ReadWorker.cache`), so the mouth
index is built from what the worker has — one tree per worker, on its first mouth query, and
NOTHING new crosses but the `WallField` (the cells' polygons: a few MB; `pickle.dumps(args)`
at `:475` is the existing refusal if it cannot). The purity invariant of `read_family`
CHANGES and the docstring (`:110-115`, "it reads nothing of another family") is rewritten: a
family's reading is a pure function of (its members, THE WHOLE PACK's placements and
geometry, the DEM, the law, the field) and of NO OTHER FAMILY'S READING — so `assemble`
(`:522-548`) still orders it and the result is identical at any worker count and in any
completion order. The twins `test_parplanar.py:119 test_pooled_readers_equal_serial`,
`:171 …its_own_and_the_ids_come_from_the_assembly`, `test_pardoors.py:166 any_completion_
order` are the bar; `tools/planar_read_arm.py:138` hashes `wall_corridor_reads` for the two
arms (`test_parplanar.py:308`) and must hash equal serial vs pooled WITH the field handed.

### §12h (6) CONSUMER CENSUS (owner RULINGS 2026-08-30l) — ruled per row BEFORE any consumer is edited; verified on `claude/parfinal d41e65db`

R only REFUSES; an admitted record's fields are built by unchanged code, so every consumer
sees the same records at OTHH and none elsewhere. Rows 1–10 are the scout's, re-verified;
11–18 are readers the scout's census did not list.

| # | consumer (parfinal) | reads | under R |
| --- | --- | --- | --- |
| 1 | `planar/pack_reads.py:51, 167-180 wall_corridor_reads` | the records + stats memo | gains `field`; same shape; 9 records at OTHH, 0 elsewhere |
| 2 | `planar/build.py:215-227` → `wall_corridor_ramps.wall_corridor_groups` (`:77`) | records → `Group` | derives the `WallField`, hands it; same 9 groups |
| 3 | `planar/structures.py:95-98, 270-271, 744, 812-814`, `structure_geometry.py:55-57, 327, 405`, `structure_deck.py:186` | groups, `plate_plan`, the law's caps | unchanged (plate_plan is read, not re-derived) |
| 4 | `constraints/structures.py:113-115, 163, 242, 256, 277-278, 303-313` (`WALL_CORRIDOR_SOURCE/ROLES`) | emitted ramp rows | unchanged |
| 5 | `pipeline/build.py:294` (seat exclusion), `:715-721` (report), `:798` (per-site line) | `tn.source`, `ws` | unchanged; prints `field read` |
| 6 | `airport/rebake_plan` facility members | the kerb walls as members | unchanged |
| 7 | `pipeline/publication.py:168 RAMP_ROLES`, `verify/structures.py:265`, `verify/keepout.py:104`, `verify/channel.py:178`, `emit/graded.py:28 FLOOR_ROLES`, `constraints/foot_rows.py:77`, `constraints/channel.py:113`, `classify/airside_edge.py:58`, `planar/object_corridor.py:97-102`, `model/structures.py:299`, `law/units.py:19`, `law/cutout_schema.py:81-155`, `law/model.py:727, 1009-1031`, `families.toml:368-446`, `precedence.toml:60-71`, `rulesets.toml:31` | role literals / the ramp law | unchanged (count effect only) |
| 8 | `tools/check_grade.py:6710, 7496-7556 LAW_FAMILIES`, `harness/census.py`, `precedence.toml oracle_role = tunnel_ramp` | the role | unchanged |
| 9 | `planar/__main__.py:360-374, 535-558, 630-645` (`--stage structures`, `--kml`) | `read_wall_corridors(…, cl, measure=True)`, `wall_corridor_admission` | hands `cl` → `field`; the line gains the three clauses' witnesses |
| 10 | door wells / sunken roads / basins / tunnel objects | their own laws | untouched |
| 11 | `airport/reader_work.py:79, 166, 175-181, 222-236, 428-490` (the pool: `wall_families` intake, `read_family` per task, `wall_reader` built in the worker) | one task per family | `begin`/`setup`/`ReadWorker` carry `field`; the index per worker (5) |
| 12 | `airport/wall_family.py:46-74 WallReader / wall_reader`, `:522-548 assemble`, `:551-571 read_wall_corridors` | the reader's inputs | gains `field`, the lazy index; `assemble` unchanged |
| 13 | `tools/planar_read_arm.py:48, 138, 145` | hashes the readings | serial = pooled with the field handed |
| 14 | `airport/object_cut.py:12-13, 605-623` | docstring + the VHHH refutation note | rewritten as history ((7) and (10)) |
| 15 | `law/model.py:44, 56, 61-64, 797-798, 1108-1109, 1143-1147`, `law/__init__.py:7-12`, `law/tables.py:16, 35, 74-91` | `Affordances`, `LawTables.airports`, `Law.affordances`, `TABLE_FILES` | deleted ((7)); `Law.for_airport` keeps `icao` for the ruleset resolution and `tables.flat_declared(law, icao)` |
| 16 | `Ortho4XP.spec:80-86`, `Ortho4XP_Qt.spec:95-101`, `tests/test_auto_patch_engine_dispatch.py:418-434` | the law-table count | 9 → 8 datas (7 tables + `classify/rules.toml`); the twin's `n` is computed |
| 17 | `tests/test_no_airport_specific_code.py:18-22, 42-46` | `RECORDED` | `set()` |
| 18 | `tests/auto_patch_v2/test_v2corridor.py:46-52, 472-547`, `test_v2wallcorridor.py:108`, `test_v2canopy.py:36, 153-154, 198-208`, `test_parpack.py:33`, `test_v2packcache.py:31`, `test_once362.py`, `test_pardoors.py`, `test_parplanar.py` | the law fixtures and the affordance twins | the affordance twins deleted; the `Law.for_airport("OTHH")` fixtures stay valid (it resolves a ruleset); every synthetic corridor twin re-read under R ((9)) |

Readers of `group_span_max_m` (05g (2)): `law/tables.py:82-91` (THE derivation site, kept),
`pipeline/build.py:406, 504`, `tools/v2_solve_replay.py:425`, `tools/pack_stage_profile.py:
304, 331`, `tools/pad_airside_arm.py:194`, `planar/group.py:26, 58-59, 130, 138, 379`
(docstrings), `law/rebake_schema.py:103-105` (the schema of the pack-wide key and its
comment), `structures.toml:707-720`, `tests/auto_patch_v2/test_v2canopy.py:36, 153-154,
198-208`.

### §12h (7) THE DELETION LIST (file:line on `claude/parfinal d41e65db`)

| what | where | action |
| --- | --- | --- |
| the table | `law/airports.toml` (18 lines) | DELETE the file |
| `TABLE_FILES` | `law/model.py:61-64` | drop `"airports.toml"` (8 → 7) and the 10ap comment |
| `LawTables.airports` | `law/model.py:797-798` | delete the field |
| the load | `law/model.py:1108-1109` | delete |
| `Law.affordances` | `law/model.py:1143-1147` | delete the property |
| `Affordances`, `NO_AFFORDANCES`, `load_airports` | `law/airports_schema.py:41-72`, docstring `:1-19` | delete; the module keeps `Resolution` / `resolve_ruleset` (`:29-35, 75-85`) and a docstring saying so |
| re-exports | `law/model.py:44, 56`, `law/__init__.py:7-8, 12` | drop the three names |
| `tables.affordances()` | `law/tables.py:74-79`, `__all__ :35` | delete |
| `tables.group_span_max_m()` | `law/tables.py:82-91` | KEEP the function (one derivation site, five readers); body becomes `return float(law.tables.structures.placement.group_span_max_m)`; docstring loses "overridden by this airport's own value" |
| `Affordances.group_span_max_m` prose | `law/rebake_schema.py:103-104`, `structures.toml:718`, `planar/group.py:58-59, 379` | delete the per-airport sentence |
| the gate | `airport/wall_family.py:180-204` | delete; the (1) clauses take its place after rule 5 |
| the reader's docstring | `airport/wall_corridors.py:1-14` (`§6, §12g`, `airports.toml`, "PER-AIRPORT AFFORDANCE") | rewrite to §12h |
| the VHHH note | `airport/object_cut.py:12-13, 605-623` | rewrite as history: signature A refuted (15x stands); the affordance replaced by §12h; VHHH measured under R ((10)) |
| RECORDED | `tests/test_no_airport_specific_code.py:42-46` (+ docstring `:18-22`) | `RECORDED = set()`; `test_the_recorded_set_is_not_stale` stays (vacuously true, and it re-arms the day a row is added) |
| the affordance twins | `tests/auto_patch_v2/test_v2corridor.py:472-547` (`…names_othh_and_nobody_else`, `…with_the_key_on_and_refused_with_it_off`, `…every_law_c_class_passes_the_one_gate`, `…the_law_digest_changes_when_the_affordance_table_changes`) and the fixture docstring `:46-52` | delete; `…terminals_only_clause_and_its_keys_are_deleted` (`:519`) stays |
| the span twin | `tests/auto_patch_v2/test_v2canopy.py:198-208 test_the_airport_may_state_its_own_span` | replace by one asserting `group_span_max_m(law) == law.tables.structures.placement.group_span_max_m` and that `Law` has no `affordances` |
| the freeze guards | `Ortho4XP.spec:80-86`, `Ortho4XP_Qt.spec:95-101` | `< 9` → `< 8`; "eight … (incl. airports.toml, RULINGS 2026-09-10ap)" → "seven"; `tests/test_auto_patch_engine_dispatch.py:429` comment |
| INDEX / docs prose naming `airports.toml` | `tools/INDEX.md`, `CLAUDE.md`, `.claude/agents/*.md` (grep) | one-line edits in the same commit |

**What `Law.for_airport` keeps afterwards.** `Law.icao` (`model.py:1176`) — used by
`resolve_ruleset` (FAA for K…/PA…-class identifiers, a rule by identifier class, not by
airport), by `tables.flat_declared(law, icao)` (`:648`, the owner's option-(c) declaration —
`flat_site.toml` names no airport today, the 05e twin proves it) and by report lines. NO
per-airport TABLE remains: `LawTables` loses `airports`, the law directory has 7 files, and
`test_no_airport_specific_code.law_affordances` finds nothing. `law_tables_digest`
(`tables.py:55`) globs the directory, so every patch's provenance changes once — expected,
and the byte-identity bars are on the BODY and the rebake plan, never the sidecar's digest.

### §12h (8) `group_span_max_m` — THE EXACT REMOVAL THAT LEAVES THE PACK-WIDE VALUE BYTE-IDENTICAL

Its per-airport reading: `Affordances.group_span_max_m: float | None = None`
(`law/airports_schema.py:49-55`) → `tables.group_span_max_m(law)` (`law/tables.py:82-91`:
`own = law.affordances.group_span_max_m; return own if not None else
law.tables.structures.placement.group_span_max_m`) → `pipeline/build.py:406` imports it as
`_span_max` and `:504` hands `_span_max(law)` to `planar/group.derive` (`:379`
`span_max_m`). `airports.toml` names NO `group_span_max_m` for any airport (the file's one
key is `kerb_wall_corridors`), so `own` is `None` on every build today and the function
returns `[placement] group_span_max_m` = 150.0 (`structures.toml:720`, schema
`rebake_schema.py:105`). The removal: delete the dataclass field with the class; reduce the
function body to the one `return`; delete the four prose mentions ((7)). Every reader keeps
the same call and the same value → the derived groups, the pads and the patch are
byte-identical by construction; the proof is the OTHH replay body sha in (9) (the partition
and the groups are captured, so a `--from planar` replay does not re-derive them — the lane
ALSO runs `--from classify` once on the OTHH capture, which re-derives the clusters off the
partition, and the one OTHH build, which derives everything).

### §12h (9) ACCEPTANCE BARS FOR THE IMPLEMENTING LANE

Synthetic-first, one airport at the close (CLAUDE.md BUILD ECONOMY):

1. **The OTHH replay** (registered capture `frames/perfB362/OTHH.pkl` or the parallel branch's
   `pardoors` frame; `frames.py list OTHH`): `--from planar --emit DIR` → 9 corridors with
   RECORDS IDENTICAL to the base arm (ids, class, axis, stations, floors, plate_plan — diff the
   `--stage structures` JSON), patch BODY sha
   `88794a1d264baaa696d7248c08c0f39a3fd8aa7027f369d5f45e827d7438ae8d`, rebake plan
   `eecf0d4d6ba1…` (the full sha is on the pardoors frame row); then ONE OTHH build through
   `tools/harness/build_airport.py OTHH` with the same body sha. With the family FIELD gate
   ((4) step 0) the bar on the LINES is: records sha + patch body `88794a1d264b…` + rebake
   `eecf0d4d6ba1…` + the 30 ON-FIELD refusal texts identical + the 5 family lines naming
   distances ≥ 150 (30 of OTHH's 60 refusal texts belonged to its 5 off-field families and
   are those 5 lines).
2. **The other six sweep airports byte-identical** — CYXY `2a00c361ffc2`, SPJC `9d611f11e04b`,
   KCLT `795da9629004`, KASE `738c2a8ceb64`, HECA `09847984ac94`, NLWF `84be89f8b7bc` — proven
   by the MASTER's sweep at merge (never a lane's five-airport sweep); the lane proves KASE on
   its registered capture by replay (`--from planar --emit`, body sha) because KASE is the one
   whose candidate population R touches (26 live → 0).
3. **Replays admitting 0**: LEMD (`frames/sheetchain/LEMD.pkl`), KASE (`conc333`), TFFJ
   (`surfacesettle2`), VHHH (`frames/lawcspec/VHHH.pkl`, (10)) — `--stage structures` on each:
   `corridors 0`, every refused candidate's line naming its clause, and the (2) table
   reproduced from the lines for the on-field airports (LEMD); for KASE / TFFJ / VHHH the
   family lines name the distance and the per-clause columns are the lane's recorded
   measurement — under the law values (ε 0.05, ceiling 3.5): W1s / W3 / FIELD
   counts per airport equal to the table, or the difference named per candidate.
4. **Build time**: `read_s` delta on the OTHH replay and the OTHH build's wall-corridor line,
   both arms, under `ab-time`; the bar is < 0.6 s added and the index built once per process.
5. **Twins, from synthetic packs** (`test_v2corridor.py`'s `_corridor_obj` family, extended
   with a CLOSER placement of another resource and a cells list for the field): one per clause
   — W1s open (admitted) / closed below by a foreign slab / closed at grade by a wall, a door
   mesh, a fence, a 0.15 m kerb (each REFUSED by W1s with the closer named); W3 by plate /
   by an above-grade wall at the closed end / neither (REFUSED by W3); FIELD on / off (cells
   moved 200 m away → REFUSED by FIELD) / not read (no classification: the line says so,
   `field_read` False) — and one per degenerate case of (3): canopy overhead (the mouth open;
   the canopy is a plate, so W3 ✓ through `plate_plan`), jet bridge
   (legs < 0.5 → open), ground slab (closed), open both ends with a deck (level, two halves),
   open both ends under open sky (REFUSED by W3), one end closed by a foreign placement (bay
   at the other), garage ramp (one mouth; W3 at the deep end), unequal arms (mouth at the
   overlap). Plus: the composed class (level → bay) twin; the line-format twin (every clause
   present, the closer's resource and placement in it); the pooled = serial twins with the
   field handed (`test_parplanar`, `test_pardoors`, `planar_read_arm`); `test_no_airport_
   specific_code` green with `RECORDED = set()`; the law-table count twins at 7.
6. **The existing twins re-read under R** ((6) row 18): every synthetic corridor they admit
   today has a deck (`deck_y=2.6`) — W3 ✓ — and open mouths with nothing else in the pack —
   W1s ✓ — and most hand no classification → FIELD not read. A twin that admits an `open_air`
   corridor (`test_v2corridor.py:66`, `test_v2wallcorridor.py:127-128` garage/steep with
   `deck_y=None`) is now REFUSED by W3 unless the pack carries a wall at the closed end: those
   twins assert the refusal by name, not a changed law.
7. `tools/ratchets.py` passes; the report carries net lines and new public symbols
   (`WallField`, `cover_polygons`, the `field` parameters, the stats fields).

### §12h (10) VHHH — MEASURED (the condition RULINGS 2026-10-05g set before the key is deleted)

**Capture.** No VHHH capture existed (every registered one was MISSING after the reboot
of issue #37), so this lane took ONE: `tools/v2_solve_replay.py --capture VHHH` on main
`b229ab54` from the `lawcspec` lane worktree on the shared corpus — 248 s, peak RSS **2.7 GB**
(the 25–35 GB structures-stage warning did not recur at capture; the mouth read peaked at
1.9 GB), 33,947 vertices / 2,118 faces, pack partition 106 s (2,998 bodies, 2,730 groups),
`[guard] shared repo UNCHANGED`. Registered: `frames/lawcspec/VHHH.pkl`
(`docs/frames.jsonl`, kind `capture`, base `b229ab54`, lane `lawcspec`).

**Read** with the scout's instrument unchanged (`scratchpad/mouthwitness/mw.py`: the
affordance forced ON in-process, (d) neutralised in-process so every candidate reaches rule
4 while its own-wall height still states (d)'s verdict; `read_wall_corridors` 284 s over
5,078 placed objects, 145 families, 1,326 bands, 224 pairs; then the FIELD read against
the capture's classified cells). Numbers first:

| population | n | (d) refuses | W1s | W3 | FIELD | R |
| --- | --- | --- | --- | --- | --- | --- |
| today's law, key forced on (live) | **0** | — | 0 | 0 | 0 | **0** |
| (d) neutralised (the 10ap population) | 181 (bay 100, level 81 pairs) | **181** (own wall 16.66–153.25 m) | 180 | 175 | **0** (nearest cover 1,316–2,042 m) | **0** |

Every one of the 181 is inside `CITY1.obj` 64 / `CITY2.obj` 72 / `CITY3.obj` 41 /
`CITY4.obj` 4 — the city-block objects whose foundation walls descend 1.35–10.22 m under
their ground, at 22.27605–22.29683, 113.93130–113.95404 (the town east of the field; the
nearest classified cells are `building` 280 / `service_road` 82 ends, 1.3–2.0 km away).
The other 43 of 224 pairs are refused by the existing rules (closed at both ends 31, not
two readable bands 2, wall bottom at 894 % 1, …). The `object_cut.py:612-623` record —
`CITY2.obj` 0 → 116 corridors with the key on, 2026-09-15, BEFORE (d) existed — is this
class: signature A's predicate (a crest plate) admitted them; today's (d) refuses every one
on its own, and FIELD refuses every one on its own. **R admits nothing at VHHH; two
independent clauses each read the whole set as refused.** No finding, no special case.

Lane `lawcspec`, 2026-10-05; the per-candidate JSON (`VHHH.json`, `field_vhhh*.log`) is in
the lane's scratchpad beside the scout's; the implementing lane's `--stage structures` on
the registered capture is the durable form of this read (bar (9) 3).

### §12h (11) RESIDUE FOR THE OWNER'S SIM LOOK (nothing misclassified on the corpus; five refusals rest on ONE clause each)

| site | what | the one clause |
| --- | --- | --- |
| KASE 39.191344, −106.819583 | `b56dfde4-…-359f7b320fda_1` 3105: 19.5 × 10.3 m, 9.9 m deep, one end wholly open, the other closed by `_2` (z 2395–2405) | (d) and FIELD (3,900–4,370 m from the cover) — see the 3131 row |
| KASE 39.189304, −106.819453 | 3131: 10.3 × 8.9 m, 3.1 m deep, bay under a 7.2 m deck | KASE 3131 and 3105's kerb reads 3.00x m at the engine's precision (the scout compared a rounded 3.0): (d) refuses them; FIELD refuses them too. Only 3161 (kerb −0.0, W1s ✓ W3 ✓) rests on FIELD alone |
| KASE 39.190352, −106.819609 | 3161: 22.2 × 10.7 m, 7.0 m deep, bay | FIELD |
| LEMD 40.458445, −3.577556 | `Airport_Cargo-GAVIA` 0/0 bay 24: a 1.2–1.4 m cargo kerb pit under a 3.7 m deck — `Cargo-LEMD63` comp 14, a 3 cm plate authored +2.26 m, 2.15 m over the mouth's ground, 3.52 m over the floor — that reaches its mouth window (0.82 of W) | W1s — its roof reaches the mouth under `min_headroom_m` over the ground |
| OTHH 25.266210, 51.611335 | `Terminal_Base_2_5` 432/433 (the 08u underpass): admitted; its deck (2.42 m over ground) would close the mouth if it reached the window | the one admitted record whose W1s rests on the plate's edge |
| LEMD 40.491095, −3.568335 | `Sim-wings-SWbaume` 135/163 (117): a 7 m pit at the T4S tower filled by the pack's ground slab `Ground-FSX-LEMD85` (1.00) | W1s |

Downtown Aspen is 3.9 km from the field; the two LEMD sites are paved over by the pack itself.
If the owner wants pictures, these five. The next witness if R were refused — the crest test,
the band's own top ≥ 0.2 m over the object's zero — is weaker (a 0.36 m margin against a
presence test) and is recorded in the findings only.

### §12h (12) OWNER QUESTIONS (each a yes/no with the spec author's recommendation)

1. A kerb or step < 0.3 m across the mouth at grade CLOSES it (the pack says a vehicle does not
   drive there)? — **Recommend YES** (no corpus instance either way; the rule stays one value,
   ε; a kerb-height floor to the at-grade band would be a new value nobody has measured).
2. A level corridor whose one end a FOREIGN placement closes builds as a BAY at the other end
   (rather than being refused or built as two halves)? — **Recommend YES** ((1) last
   paragraph; no corpus instance; the half that would climb into the closer is the defect
   avoided).
3. FIELD reads the classified cover ALONE (not §29 (1)'s approach corridor and runway band)?
   — **Recommend YES** (the measured form; a kerb corridor is not a portal seen on approach).
