# The two-level model: lower-level REGIONS (spec, round 1 — picture before code)

Status: the owner accepted the recommendations for the choices §11 raised
(Noah, 2026-11-03T06:05:23Z, verbatim: "Accept recommendations for the "four
choices it raised"."). §13 records what that changes. It OVERRIDES §2, §3
and §10 where they differ.

Law: RULINGS 2026-11-03b (Q340–Q347, owner 2026-11-03T05:00:50Z), the review
doc "Bridges, tunnels and cuts: the two-level model"
(https://claude.ai/artifact/8V2c3TZ2fX2cAZ5j6s91ZW), and the rulings it puts
in one order: 14f, 27g (Q187), 28k (Q226–Q233, R1/R6), 29a (Q271, Q287,
Q297, Q298, Q299), 30a, 30b, 30f, 30g.
Issues: #1717 (the reference case), #1638 (dual roadway; draft PR #1652 is
the road-trench version this replaces), #1715 (deck end lines), #1639
(T1, a tunnel mouth, two bridges).
Replaces: 28k R6 as built (`planar/viaduct_road`), the deck's own trench
(`planar/deck_bores` lanes and `planar/deck_bridge.deck_cut`'s bank), and
PR #1652's `planar/dual_trench` (never lands).
Builds on: `docs/specs/low-level-pad-spec.md` (the stepped unit's lower
level), `docs/specs/lfpg-cuts-tunnels-rules-spec.md` (R1–R7 and its §6
census), `docs/specs/below-grade-cutouts-and-deck-flush-plan.md`.

## 0. Summary

The engine builds lower ground as **road trenches**, one per road, mouth or
deck. The owner builds **levels**: an airside level A and one lower level B,
joined by vertical steps. This spec makes the unit of lower ground a
**region**: one connected area per lower level. Each region has one outline,
one depth from one ladder, and vertical steps at its edges. It is computed
once, at one derivation site, before the structures pass, and every pass reads
that one record.

On LFPG, a 4 m prototype of the rule (§9, run on the 1.0.454 readings and not
yet engine code) puts the T2 central corridor in one 38.9 ha region, 7.0 m
under level A, set by the T2 buildings' lower storeys. It runs from the T2
west loop (2.5586) to the 2E/2F forecourt (2.5996). At S2 it steps vertically
at the same two places as the owner's patch. At S4 it cuts the A1 under
runway 09R/27L 7.5 m down; the owner's patch is 7 m.

It does not reproduce three things in the owner's patch:
- Roissypole and the block north of 2E/2F, about 56 ha, which the owner
  lowered whole and which no object witnesses (D1).
- The owner's flat 103 m datum: the plan keeps the solved airside level, so
  absolute heights differ by up to 3 m (D2).
- The A1 trench width: the plan cuts 72 m (the deck footprint), the owner
  44–46 m (the carriageways) (D3).

§10 lists every disagreement.

## 1. What a region is (Q340 a)

A **level-B region** is a connected area of the airport that its objects put
below level A. It runs through under every bridge and deck in it, and out
along its roads and rails until they climb back to natural ground.

The record is published once, on the planar map:

```
LevelRegion(id, outline: Polygon (frame xy, holes allowed), depth_m: float,
            rung: str, seeds: tuple[Seed], floors: tuple[ObjectFloor],
            runouts: tuple[RunOut], steps: tuple[Step])
PlanarMap.level_regions: tuple[LevelRegion, ...]
```

- `Seed(kind, source_id, polygon, stated_depth_m | None)`: one witness. Its
  kinds are listed in §2.1.
- `ObjectFloor(source_id, polygon, depth_m)`: where an object states its own
  bottom. The floor there is the object's, and Q271 grades it bottom to bottom
  between two such objects.
- `RunOut(way_id, s0, s1, grade)`: a road or rail leaving the region, from
  its edge to where it meets natural ground.
- `Step(line, kind: object|open, object_id | None)`: each piece of the
  outline that is not a run-out.

The region record replaces these: the per-road trench records (R6's
`sunken_road` halves, deck-bore corridors, `survey_trench` /
`survey_road_trenches` trenches inside a region), the per-deck walled trench,
and the `low_extent` extension of a stepped unit's level. A lone bore with no
region around it (a mapped tunnel whose mouths stand in open ground) stays a
`Tunnel` exactly as today.

## 2. How a region is derived (one site)

### 2.1 Seeds: what witnesses lower ground

Every seed is an existing reading. The region adds no new reader.

| seed kind | witness (existing reader) | stated depth |
|---|---|---|
| two-level building, lower storey (Q188) | `airport/airside_group_seat.airside_zeros` + `geom/foot_planes` (the feet planes a storey under the group zero), as `planar/low_level` / `group_low` read them today; footprint = the unit's lower parts | the feet plane (`y_feet`) |
| retaining wall, low side (Q299) | `airport/wall_sides.WallSides.lower_face`, `airport/wall_top.foot_profile` | the wall's foot profile |
| bridge-edge object (27r, Q271) | `planar/bridge_span.edge_bridges` (back, span, walls' bottom) | walls' bottom |
| trench object (Q255/Q256) | `airport/trench_objects.read_trench_objects` | its outline's floor (the object's, not "the survey's or the bore law's" as its docstring says today) |
| tunnel-mouth object, floor in front (Q256 b) | `airport/tunnel_objects.read_corridors`, `airport/portal_objects.read_portals`, `airport/hanging_objects.hanging_bottom` | floor slab / roof-top depth |
| covered rail cut liner (Q287) | `planar/covered_cut._cut_floor` | the liner's walkable top |
| hard-deck bridge (30a/30f) | `planar/deck_bridge.deck_bridges` (ring, top, `bottom_y`, walls) | the frame's bottom only where it reaches `[tunnel] clearance_m` under the top (30g (2)); a slab states none |
| stacked viaducts (28k Q228) | OSM `bridge=yes`, `layer >= viaduct_min_layer` over a `layer <= 0` road inside the aerodrome boundary, as `planar/viaduct_road` reads it today | none |
| covered road (28s (5)) | `planar/covered_bores.covered_bore_ways` | none |
| lot or pad mostly under covers | an arrangement face (lot, apron lot, pad) at least `cover_min` (0.25) of whose area lies under the seeds above | none |

Not seeds:
- A mapped deep tunnel with no portal object and no open-cut witness (Q345 a).
- A door well (07e). It stays its own narrow structure unless it lies inside
  a region.
- Basins (closed pits with their own floor-to-rim law). Their status is an
  owner question, O4.

### 2.2 The outline: from seeds to a region

The outline is built in this order, once:

1. **Level A, the walls.** These are:
   - runway- and taxi-family pavement;
   - aprons an aircraft can still reach (step 2);
   - the graded strips;
   - pads that front reachable airside pavement. These are the airside
     terminals, flat at level A (#1717 item 2).
2. **Aircraft reachability, re-read with the covers standing.** This is the
   existing `planar/reach_after_pads` reading (`BEYOND`), with viaducts, lower
   storeys and mouth floors added as obstacles. Decks are not obstacles,
   because aircraft cross them.
   - A region is found by flooding from taxi pavement through apron opened by
     an `aircraft_passage_m` (24 m) disk. Any apron the flood does not reach
     is not level A.
   - This is what un-flips the §27 apron lot under the T2 viaducts
     (`dsf:pol459`, 13.1 ha, half of it under the owner's lower level). It
     extends 28p (3): a lot's contact with airside under a viaduct does not
     count.
3. **The ground between.** A groundside surface becomes eligible when it lies
   between level-A walls, that is, when level A stands within
   `between_reach_m` (150 m) on both sides along one of four axes. Groundside
   surfaces are lots, roads, unreachable apron, and pads that do not front
   airside.
   - Bare ground with no surface is not eligible. Between taxiways it is the
     graded strips' ground, and level A keeps it.
   - The region is every connected component of seeds ∪ eligible ground that
     holds a seed.
4. **Enclosed faces.** A lot, pad or road at least `enclose_min` (0.5) of
   whose rim lies on the region joins it. This is iterated to a fixpoint.
   Pads that front reachable airside never join.
5. **Through covers (Q340 a, Q297).** Where a region road passes under a cover
   between two parts of one region, the region runs through at the region's
   width, and the two parts are one region. A cover here is a deck, a pad (a
   building the road runs under), or a deck-ground strip.
   - The rule is the road's stretch under the cover. No distance key is
     needed.
   - The prototype approximated it with a 220 m search, which is what the
     2E/2F terminal (`building9`, 197 m across the corridor) needed. The
     engine rule must not carry that number.
6. **Holes.** Ground the region encloses becomes part of the region (the T1
   courtyard).
7. **One region per connected area** (8-connected).
8. **Run-outs.** Every mapped road or rail leaving the region climbs at its
   grade law from the region's edge until it meets natural ground:
   - roads: `[tunnel] ramp_grade`, capped at `ramp_max_grade`;
   - rail: `rail_ramp_grade`, at most 3.5 % (Q233).

   The run-out starts at the edge of the region, or at a mouth object's
   bottom where an object stands, and runs its full standard length along the
   mapped way (#1747).

The law keys are new, in `law/structures.toml [level_b]`:

| key | value | source |
|---|---|---|
| `aircraft_passage_m` | 24.0 | ICAO code B wingspan upper bound; an apron narrower than that between covers is not a stand |
| `between_reach_m` | 150.0 | half the widest forecourt between two level-A walls in the owner's reference patch (LFPG B1, ~260 m); must be checked on the registered KPHX / KATL / EGLL captures before landing (§8) |
| `cover_min` | 0.25 | a face a quarter under covers is a covered lot |
| `enclose_min` | 0.5 | half the rim on the region |

`between_reach_m` and `aircraft_passage_m` were read on one airport. The
no-airport-specific-code gate forbids tuning them so that LFPG passes. §8's
dry A/B on five registered captures is where they are judged, and any value
that only LFPG needs is reported to the owner rather than kept.

### 2.3 The single derivation site

`planar/level_regions.py` (new module, one responsibility: the region record)
holds `level_regions(airport, classification, law, *, decks, edge_bridges,
pack_reads, objects) -> tuple[LevelRegion, ...]`. It is called ONCE in
`planar/build.build`:
- after `deck_bridges` / `edge_bridges` / the pack reads (`build.py:289-293`);
- before `build_structures` (`:295`).

This is the slot `deck_bridges`, `edge_bridges` and `covered_cuts` already
use. The depth comes from §3's one function, `planar/level_depth.region_depth`.

Reuse, not a second implementation:
- **`planar/low_extent.extend_levels`** is today the only code that grows a
  lower level's outline from objects, but it keeps off structures, needs a held
  pad, and runs inside the arrangement. Its growth logic (walled lower parts,
  mapped roads over them, a retaining wall's lower side) MOVES into
  `level_regions`. `low_extent` then reads the region: a stepped unit's level
  inside a region is the region's.
- **`planar/viaduct_road`'s route walk** (heading-keeping route through short
  ways, dual carriageways) moves into the seed reader for viaduct-covered
  roads. Its floor (`_apron_level − mouth_depth_m`) and its climb are deleted.
- **`planar/deck_bridge`** keeps the deck reading (ring, end seats, top,
  frame bottom, walls). `_road_floor`'s clearance logic moves into
  `level_depth`. `deck_cut`'s bank survives only for a lone road under a lone
  deck (§5).

Seam probe P1, required BEFORE any code: confirm that the lower-storey
witness can be read before the arrangement. The witness is the unit lower
parts plus the feet planes `low_level.walled_feet` and
`group_low.group_floor` use, and today those read `Registries.held` from the
arrangement's pad pass (`low_extent.py:85-99`, `low_level.py:521-531`).

Run one `v2_solve_replay --replay <LFPG capture> --from planar` with a probe
that calls them on `objects` + `airport.groups` before `build_structures`.
- If that is impossible, the fallback is the order PR #1652 used: the region
  is derived after the pad pass, and the bores and decks inside it yield to
  it (`absorb_mouths`-style). That is two passes reading one record, never two
  derivations.
- The fallback costs one extra arrangement pass on airports with regions, so
  the owner should know before it is chosen.

## 3. One depth per region: the ladder (Q342 a, Q344 a)

`planar/level_depth.region_depth(region, law, dem) -> (depth_m, rung,
floors)`. It is the only place a lower-level depth is computed. In order:

1. **Objects.** These are objects that state their own bottom: lower-storey
   feet planes, retaining-wall feet, bridge-edge walls' bottoms, trench-object
   floors, tunnel-mouth floor slabs, covered-cut liners, and deck frames
   reaching `[tunnel] clearance_m` (5.0).
   - Each such object is an `ObjectFloor`: the floor there is its own.
   - The region's `depth_m` is the area-weighted median of the stated depths.
     LFPG T2 corridor: 7.03 m, from `building34/35/51/64`'s lower storeys at
     7.03–7.44 m.
2. **Clearance under a deck (30g).** Under a flat deck whose frame states no
   floor (a slab), the floor is at least 5.0 m under the deck top.
3. **Credible lidar, if it clears 5 m.** Only where no object states a depth,
   only on a credible inset (`law/inset_class.lidar_credible`, the one gate;
   `planar/channel._lidar_credible` is a second copy to retire), and never
   under a deck or viaduct. The reading is the survey's floor against the
   adjacent level A (`planar/lidar_road`'s cover/road reading, moved here).
4. **Default 7.5 m** (`[tunnel] mouth_depth_m`).
5. **Under a runway or taxiway with no object, always 7.5 m** (231 b, Q344 a).
   This reading is applied to a SLAB deck carrying a runway or taxiway: the
   slab states no floor, so the 7.5 m rung applies, which also satisfies 30g's
   "at least 5 m".
   - LFPG A1 under runway 09R/27L (H18r, H19): 7.5 m. The owner's patch has
     7 m.
   - H17 (taxiway), whose frame reaches 5.46–5.82 m, keeps its own bottom by
     rung 1.
   - See O2.

**Constant depth under the level A beside it (Q342 a).** Level B is not a
flat height. Every B vertex stands `depth_m` (or its `ObjectFloor`'s depth)
under the solved level A beside it:
- at a step, the A vertex across the step;
- under a deck, the deck's solved top;
- in the interior, interpolated from the rim pairs.

So B is solved with A, not precomputed. One 5 m constant is named:
`tunnel.clearance_m` (5.0). `bridge.clearance_m` (5.1, the §45 channel's)
is NOT a level-B depth source. It is a second constant for the same idea, and
the master decides whether the channel keeps it (O5).

## 4. The vertical step (Q341 a)

- **At an object** (building wall, retaining wall, bridge edge, trench wall,
  tunnel mouth, deck walls): the step stands at the object's face. Level A
  meets the object's top, level B its bottom, and the face is fully exposed on
  the low side (30f (3), 27r, Q299).
- **At an open edge** (no object): the step is vertical, with no bank. At S2
  the owner's patch drops 7 m in under 2 m, and the plan drops at the same two
  stations (§9).
- **Emitted form.** It is the existing declared wall terrace, not a new
  mechanism. This is census form 1:
  1. One `road_terrace['wall']` record per step piece, with `height_m` = the
     local depth, `retains=True`, and `mouth=False` (or `True` at a mouth).
  2. `constraints/road_ramp`'s one-way row `z[lower] − z[upper] ≥ −h` plus
     its release across the wall.
  3. `solve/wall_cut.wall_cut_edges` takes the step's edges out of the bending
     stencil, otherwise the bending lifts B toward A, as the 3.5 m KATL road
     at an 8 m wall did.
  4. `pipeline/publication.wall_terrace_joints` publishes it as kind
     `wall_terrace`, `declared_step_m` = h + 0.01.
  5. The census forgives it through `DeclaredWallSteps`, `_declared_joint_step`
     and `verify/steps.WallSteps`.

  The rows that hold B under A are a generalisation of
  `constraints/platform.landing_rows` (today: rigid at `D_block + y_lo`) to
  "B rim vertex = paired A vertex − d". The withdrawal across the step is
  `constraints/riser.py`'s, generalised from the `#strip` riser to every
  region step. The `#strip` riser itself is a 2-cell bank, so it is replaced
  by the wall step inside regions.
- **No bank, ramp, graded strip or blended zone fills a step.** Zones 1/2
  (`planar/zones.zone_regions`) subtract the region outline as a keepout, as
  they do for corridors today. The same applies to `apron_shelf`, `landing`
  1:3 collars, `fill_road` lenses and `covered_ground`'s DEM lift.

## 5. What is deleted or replaced

| today | under the model | ruling |
|---|---|---|
| `planar/viaduct_road` (R6): a 35 m trench on the mapped road at `apron − 7.5`, with its own climb | DELETED; its route walk moves into the viaduct-cover seed; the ground under the viaducts is a region (T2: inside the 38.9 ha corridor) | 28k R6 widened to the region (Q340 a) |
| `planar/deck_bores` (deck bores, `deck_lanes`, `lane_band`) and `deck_bridge.deck_cut`'s 30b bank and `_walled_trench` | REPLACED by the region running under the deck at full width; the walls are steps. The 30b bank survives for a deck that is the ONLY seed of its region and has one road under it | Q343 a |
| `planar/lidar_road.survey_trench` / `survey_road_trenches` (R2 trench, 1:1 bank, Q245 zone yield) inside a region | REPLACED by the region (the survey sets no outline; it is depth rung 3 only) | Q342/Q344 |
| per-mouth depth: `structures.py:590` (`mouth_dem − mouth_depth_m`), `structure_mouth`'s under-pavement hold, `lidar_road.survey_mouth`'s owed depth, `constraints/structures.py:594` | for a mouth INSIDE a region: the region's floor (the mouth's ramp starts at the region edge). A lone bore keeps R1 unchanged | Q344 a |
| `constraints/edge_floor` (floor linear between edge bridges) | its Q271 bottom-to-bottom grading becomes the region's `ObjectFloor` interpolation | Q271 kept |
| `planar/low_extent.extend_levels` growth | MOVED into `level_regions` | — |
| `#strip` riser bank inside a region | REPLACED by the declared wall step | Q341 a |
| `planar/cut_runout` (covered-cut ends at rail grade) | REPLACED by the region's run-outs (same law, `geom/ramp_profile.runout_profile`) | Q233 |
| `pipeline/publication.tunnel_mouth_depths` / `object_cuts` / `portal_cuts` for mouths inside a region | REPLACED by a `level_regions` sidecar record; `portal_cuts` is kept as the strip exemption | — |
| PR #1652 `planar/dual_trench` | never lands; #1638 is a case of the region rule | Q340 a |

## 6. Consumer census (RULINGS 2026-08-30l): every pass that reads bore, trench, deck or cut geometry

Interaction values:
- **DERIVES**: feeds the region's seeds, outline or depth.
- **REPLACED**: its output becomes the region.
- **DELETED**.
- **READS-REGION**: must read the region's outline or level instead of its own.
- **MUST-YIELD**: stays off the outline; no bank or blend.
- **MUST-EXEMPT**: the step is a declared step, not a violation.
- **UNCHANGED**.

All paths are under `src/auto_patch_v2/` unless they say otherwise.

| pass (module) | reads today | interaction | ruled |
|---|---|---|---|
| `planar/level_regions` (new) | seeds §2.1 | THE derivation | §2 |
| `planar/low_extent.extend_levels` | walled lower parts, roads over them, wall low side; level = objects' bottom (27h) | DERIVES → its growth MOVES into level_regions; reads the region | §2.3 |
| `planar/low_level.low_level_split`, `plan_low`, `level_cut` | stepped block's lower storey, `#strip` riser | DERIVES (lower-storey seed); riser → wall step inside a region | §4 |
| `planar/group_low.plan_group_low` | pad a storey under the group's floor | DERIVES | §2.1 |
| `planar/covered_cut` (`_cut_floor`, `trim_uncut`) | covered rail cut liner (Q287) | DERIVES; `trim_uncut` READS-REGION | §2.1 |
| `planar/low_fill.cut_fill_bands` | a lower level's fill along a lot | READS-REGION | — |
| `planar/cut_runout` | covered-cut ends at rail grade | REPLACED by run-outs | §2.2 (8) |
| `planar/viaduct_road` | R6 per-road trench | DELETED (route walk moves to the seed) | §5 |
| `planar/deck_bores` | deck bores, lanes, bank split | REPLACED / DELETED | §5 |
| `planar/deck_bridge` (`deck_bridges`, `_bottom_y`, `_road_floor`, `deck_cut`, `_walled_trench`, `deck_ground`) | the hard-deck reading; 30a/30b/30f/30g | reading DERIVES; `_road_floor` → `level_depth`; `deck_cut`/`_walled_trench` REPLACED (lone-deck bank kept); `deck_ground` READS-REGION | §3, §5 |
| `planar/deck_walls` | the deck's walls | DERIVES (object steps) | §4 |
| `planar/bridge_span` (`edge_bridges`, `edge_cut`) | edge bridge back, walls' bottom | DERIVES; `edge_cut` REPLACED | §2.1 |
| `planar/overpass_deck.road_overpasses` | a road deck's zero on the road beneath (30f (5)) | READS-REGION where that road is on B | — |
| `planar/covered_bores` | covered road = bore with a witness | DERIVES | §2.1 |
| `planar/covered_ground` | lifts DEM over covered roads | MUST-YIELD (lifts level A over B, never B's floor) | §4 |
| `planar/lidar_road` (`survey_mouth`, `survey_trench`, `survey_road_trenches`, `under_airside_pavement`) | R1/R2/R4/R5 | DERIVES (rung 3 reading, rung 5 test); trenches REPLACED inside regions; lone bores UNCHANGED | §3, §5 |
| `planar/structures.build_structures` | mouth datum, decks, refusals; crest cap §33 (3) | READS-REGION (a mouth inside B: floor = B; ramp starts at B's edge) | §5 |
| `planar/structure_mouth` | slide out of pavement; under-pavement hold | READS-REGION (the hold IS rung 5) | §3 |
| `planar/structure_approach`, `unframed_ramp`, `bore_continuation`, `structure_geometry` | bore chains, approach climb, grade law | UNCHANGED for lone bores; run-outs reuse the grade law | §2.2 (8) |
| `planar/structure_underpass` | §34 (5) aeroway-bridge underpass bores | DERIVES (deck witness); its per-road trench REPLACED | §5 |
| `planar/structure_service` | protected airside set | READS-REGION (B underlies pavement only under decks) | — |
| `planar/structure_deck`, `structure_pair`, `structure_road`, `structure_overlap`, `structure_fence`, `structure_stats` | corridor machinery | UNCHANGED (lone bores) | — |
| `planar/object_corridor`, `door_ramps`, `wall_corridor_ramps`, `plate_bays` | object-framed trenches, floor = slab / sill / wall bottom | DERIVES (object floors, object steps) | §2.1 |
| `planar/channel*` (§45 open channel) | channel floor: plates / lidar / deck − 5.1 with a bank | OPEN (O5): inside a region the region governs; the channel's bank is a step filler | §3 |
| `planar/basins*` | closed pits, floor + rim band | UNCHANGED unless O4 rules a basin is B | — |
| `planar/landing`, `landing_runout`, `fill_road`, `fill_riser`, `pad_fill`, `apron_shelf` | 1:3 collars, fills, lenses | MUST-YIELD | §4 |
| `planar/pad_cut`, `pad_terrace`, `platform`, `pad_blocks`, `pad_sliver`, `cluster` | pads vs airside | READS-REGION (a pad inside B sits on B) | §1 |
| `planar/zones.zone_regions`, `terrain_edge`, `road_yield`, `road_shadow` | adjacent ground bands, keepouts | MUST-YIELD (subtract the outline; no zone bank at a step) | §4 |
| `planar/strip_keepout` | no walls in the runway strip (06n) | CONFLICT → O3 | §10 |
| `planar/reach_after_pads` | unreachable apron → groundside | DERIVES (re-read with the covers) | §2.2 (2) |
| `planar/overlay.build_arrangement`, `shapes`, `shape_*` | the subdivision, shapes, joints | READS-REGION (the outline is a declared step between shapes) | §4 |
| `planar/wall_slope` | the hill above a retaining wall (Q299) | UNCHANGED (upper side) | — |
| `airport/airside_group_seat`, `geom/foot_planes`, `airport/unit_storey` | group zero, feet planes, upper storey | DERIVES | §2.1 |
| `airport/wall_sides`, `wall_top`, `wall_class` | wall low side, foot profile, retains | DERIVES | §2.1 |
| `airport/object_cut`, `tunnel_objects`, `tunnel_walls`, `trench_objects`, `portal_objects`, `hanging_objects`, `sunken_roads` | authored floors, footprints, walls | DERIVES (rung 1); their per-mouth/per-road depths REPLACED inside regions | §3 |
| `airport/deck_signature`, `bridge_family` | deck footprint, underside, piers, OSM bridge/tunnel classes | DERIVES | §2.1 |
| `airport/airside_deck_seat`, `cut_deck_seat`, `placement_deck`, `airport/rebake_plan.deck_datum_z`, `emit/rebake.deck_datum_from_surface` | the deck's level-A seat (30a flush, 22n) | UNCHANGED (B never alters a deck's A datum; #1715's end lines are level A's) | §7 |
| `airport/bridge_approach`, `ramp_feet`, `walled_plate` | approach ground, ramp foot, the road at a plate's foot | READS-REGION | — |
| `airport/road_ramp` (`wall_pieces`, `wall_terraces`) | `road_terrace['wall']` records | READS-REGION + MUST-EXEMPT (the step's record) | §4 |
| `airport/terrain_shaped` + `constraints/terrain_shaped` | rigid terrain skin under a terrain-shaped deck | MUST-EXEMPT (no region inside its footprint) | — |
| `airport/basin_witness`, `door_wells`, `thin_plates`, `slab_plates`, `below_zero`, `pad_level_group`, `one_building`, `open_frame_seat`, `riser_wall`, `sunken_ramp` | — | UNCHANGED (door wells and basins per O4) | — |
| `airport/lidar_breaks`, `airport/portal_witness` | DEM cut votes (not wired into the build) | UNCHANGED (rung 3 uses `inset_class`) | §3 |
| `constraints/structures` | RAMP/RIM/DECK/BASIN rows, mouth pin `DEM − mouth_depth_m` / `tn.depth_m` | REPLACED for mouths inside a region (rows at the region floor); lone bores UNCHANGED | §5 |
| `constraints/platform.landing_rows`, `group_level` | B held at `D_block + y` | READS-REGION → generalised to "B = paired A − d" | §4 |
| `constraints/riser` | withdraws rows across a `#strip` | MUST-EXEMPT, generalised to every region step | §4 |
| `constraints/road_ramp` (`_wall_step_rows`, `wall_release`), `constraints/wall_zone` | the one-way wall rows; zone release beyond a wall | MUST-EXEMPT (open steps use the same rows, h = depth) | §4 |
| `constraints/edge_floor`, `edge_deck` | edge trench floor (Q271), road deck over it | edge_floor → ObjectFloor interpolation; edge_deck UNCHANGED (level A) | §5 |
| `constraints/channel` | §45 floor rows | OPEN (O5) | — |
| `constraints/foot_road` | run-out from an object ramp foot | READS-REGION | — |
| `constraints/roads`, `no_step`, `ceiling`, `pads`, `cluster_pad`, `pad_frontage_gs`, `apron_shelf`, `walled_plate`, `slab_weld` | — | UNCHANGED (rows across a step are withdrawn by the generalised riser/wall release); `no_step` pairs across an open step narrower than `straddle_perp_m` need the P2 probe | §8 |
| `solve/wall_cut.wall_cut_edges` | edges across a retaining wall leave the bending | MUST-EXEMPT (region steps join the set) | §4 |
| `solve/design_ground.riser_outer_vertices` | riser outer vertices | READS-REGION | — |
| `solve/feasibility`, `solve/design_assemble` (basin tie) | — | UNCHANGED | — |
| `emit/osm_adapter` | void rings, sidecar keys (`tunnel_mouth_depths`, `terrace_joints`, …) | READS-REGION (add the `level_regions` key; retire keys that die) | §7 |
| `emit/terrain_edge` | edge breaklines | UNCHANGED | — |
| `pipeline/publication` (`wall_terrace_joints`, `tunnel_mouth_depths`, `object_cuts`, `portal_cuts`, `tunnel_objects`) | the published records | `wall_terrace_joints` READS-REGION (the declaration site); the per-mouth records REPLACED inside regions; `portal_cuts` kept | §4, §5 |
| `verify/structures` (`tunnel_mouth_canonical`, `tunnel_deck_clearance`, `structure_rim_gap`, `wall_in_runway_strip`) | mouth depth law, deck clearance | `tunnel_mouth_canonical` READS-REGION (region floor); clearance READS-REGION; `wall_in_runway_strip` MUST-EXEMPT per O3 | §8 |
| `verify/keepout` (`ramp_in_strip`, `ramp_in_road`, `object_cut_*`, `portal_cut_regions`) | strip and cut checks | `ramp_in_strip` MUST-EXEMPT for a region under a runway (as 19c/26k); `object_cut_*` REPLACED by a region-depth check | §8 |
| `verify/steps` (`WallSteps`, `JointIndex`) | `wall_terrace` joints | MUST-EXEMPT (reads the region's step joints) | §4 |
| `verify/channel`, `verify/cutback`, `verify/no_step` | — | UNCHANGED | — |
| `tools/check_grade.py` (`DeclaredWallSteps`, `_declared_joint_step`, `_terrace_joint_strip_exempt`, `ramp_in_strip` 19c/26k, `_check_no_wall_in_runway_strip`, `tunnel_trench` role) | joint kinds, step forgiveness, strip exemptions | MUST-EXEMPT (no new joint kind: the region's steps publish as `wall_terrace`); add the region to the strip exemptions per O3; one new family `level_b_depth` (B vertex depth under its paired A within 0.1 m of the record) registered in `LAW_FAMILIES` | §8 |

What the census settles:
- The region is published once (`PlanarMap.level_regions`). Its steps use the
  ONE existing declared-step path (`wall_terrace`). It is cut out of the zones
  at the zones' own single derivation site.
- No consumer needs a per-consumer veto: each one either reads the region or
  is already a keepout reader.

Three interactions need a probe or a ruling: P1 (§2.3), P2 (`no_step` across
an open step, §8), and O3 (walls in a runway strip).

## 7. Emittability in a heightfield mesh

- The patch is a heightfield: one coordinate, one node
  (`emit/osm_adapter.py:38`). A "vertical" step is two rings
  `identity.min_distinct_spacing_m` (0.5 m) apart, so a 7 m step is an 86°
  band. Ortho4XP triangulates the constrained rings, as it already does for
  every declared `wall_terrace` (KATL 27R's retaining wall, KBNA's deck
  walls).
- Under a deck or viaduct the mesh IS level B. The deck is an object and
  carries level A over it: 30a seats its top flush with the A vertices at its
  end lines (`airside_deck_seat`), and nothing in the mesh is two-valued. The
  apt.dat pavement over a deck drapes on B, under the deck object, where it
  cannot be seen. This is already true of every trench under a deck today
  (`deck_bores`).
- A region under a runway between decks is open sky. The runway's own
  pavement is cut at the region's outline, the same way the strip keepout's
  portal cuts are (26k). The runway stays level A on the decks. This is O3's
  question.
- The B interior is solved with A: rim pairs plus bending, with no DEM pull.
  It is therefore smooth and single-valued, and the step pairs keep
  `z_B = z_A − d` exactly at the rim.

## 8. Acceptance and the closing test (for the code round, after the owner's yes)

1. Synthetic twins (`tests/auto_patch_v2/test_level_regions.py`):
   - a two-level building with a forecourt between two facades → one region;
   - a viaduct over a road → the region runs under it;
   - a deck carrying a taxiway over a road → the region runs through at full
     width, with no bank;
   - a lone road under a lone wall-less deck → the 30b bank (Q343);
   - an open edge → a declared `wall_terrace` of the region's height;
   - a slab deck over a runway with no object → 7.5 m;
   - a frame reaching 5.5 m → its own bottom;
   - lidar 6 m with no object → 6 m;
   - lidar 4 m → 7.5 m.
2. Dry A/B on the registered captures. The LFPG capture
   (`/Users/noah/XPTerrainBuilderData/.harness/frames/lfpg6/LFPG.pkl`), plus
   KPHX (#1638), KATL (I-285 edge bridges), EGLL and KBNA, each
   `--from planar`. Report regions, their areas and depths, and every mouth
   or deck that changes. This is where `between_reach_m` and
   `aircraft_passage_m` are judged on airports other than LFPG.
3. Probe P2: `v2_solve_replay --why-at` at one open step on LFPG (S2's south
   step, 49.00437, 2.59200) to confirm that `no_step` / `cross_shape` do not
   pair an A vertex with a B vertex across it.
4. Closing build: ONE `tools/harness/build_airport.py LFPG`. Site numbers by
   landmark at S2, S3 and S4. Census through `tools/harness/census.py`, with
   no new `adjacent_ground_step` / `strip_seam_tear` / `ramp_in_strip` rows
   outside the declared steps. #1715's three decks (obj13039, obj13030,
   obj13038) end lines within 4 cm (30a).
5. Gates: the lane-rules gates, `test_no_airport_specific_code`, and the
   model purity twins.

## 9. The picture (Q347): planned levels on the real LFPG data

Method (prototype; not engine code):
- Both patches were rasterised on a 4 m grid. The owner's `LFPG.patch.osm`
  (2025-01-30, Dropbox) was read as Ortho4XP applies it. For the
  `Patches/+40+000/+49+002/LFPG_auto.patch.osm` 1.0.454 patch (engine
  1.50.1900, 2026-10-31T04:17Z, from the shared data repo's `Patches`), its
  node heights were interpolated inside its own shapes.
- The planar stage of the registered capture
  `.harness/frames/lfpg6/LFPG.pkl` was re-run under this tree (main
  5544d9568) to read the decks (25), tunnels (56) and lower-storey landings
  (10).
- §2's seeds, outline steps and run-outs, and §3's ladder, were applied on
  the raster.
- Level A is the 1.0.454 airside surface, filled outward and smoothed over
  100 m. Level B = A − the region's depth, or an object's own floor where one
  stands.
- In the sections, each auto line is moved onto the hand patch's datum by its
  median offset to the hand patch outside the regions. The 2026 survey sits
  2–3 m above the 2025 patch.

What the pictures show:

| site | owner's hand patch | 1.0.454 | PLANNED |
|---|---|---|---|
| S2, 2E/2F forecourt, lon 2.5920 | steps 103 → 96 → 103 inside a ~110 m corridor (49.0044–49.0053), walls vertical | ragged dip of 2–3 m | vertical steps at the same two stations; floor 94.7–95.3 (7.0 m under its level A, which is 1–1.5 m under the owner's 103 there) |
| S3, T2 central corridor, lat 49.0040 | 96 m for ~1.65 km (440–2090 m along the line) | apron height for most of it; one 400 m piece at ~99 | in region 1 from 1030–1760 m at 98.4–99.6 (7.0 m under level A; that level A is 106–107 m west of T2 against the owner's flat 103). Along this exact latitude 440–1030 m it misses (the region there runs 49.0030–49.0039, south of the line), and 1760–2090 m is bare ground the owner lowered |
| S4, A1 under 09R/27L (H18r) | 44–46 m trench, 106 under 113 (7 m) | the runway carried straight across at 115 | a 72 m trench (the deck's footprint), 7.5 m under level A (107.6 under 115.1 in its own datum) |
| T2 area (lon 2.540–2.605, lat 48.997–49.016) | 35 % lower level (60 % airside, 3 % slope) | 3 % lower, 7 % slope, 86 % airside | 10 % lower, 5 % slope, 81 % airside |

Corridor widths, owner against planned:

| lon | owner | planned |
|---|---|---|
| 2.562 | 152 m | 76 m |
| 2.568 | 136 m | 68 m |
| 2.572 | 112 m | 144 m |
| 2.576 | 184 m | 236 m |
| 2.580 | 224 m | 148 m |
| 2.585 | 108 m | 96 m |
| 2.590 | 92 m | 104 m |
| 2.592 | 112 m | 120 m |
| 2.596 | 104 m | 112 m |

Where the plan is lower level, 79 % of it is the owner's lower level too
(41.6 of 52.6 ha).

## 10. Where the rule and the owner's patch disagree

- **D0. Natural ground is not a region.** 107 ha of the owner's "lower
  level" south of T1 (lon 2.5325–2.5535, lat 49.0007–49.0154) stands at 97 m,
  where the survey stands at 96.5 m. That is low natural ground, flattened,
  not a cut.
  - The plan leaves it to the mesh (no patch shape), so the two agree in
    height.
  - Because it counts in the 35 %, the honest comparison is against the
    owner's CUT lower level, where the survey stands more than 1.5 m above his
    level: 118 ha in the T2 window.
- **D1. Landside zones with no object witness.** These are Roissypole (lon
  2.553–2.571, lat 49.0078–49.0115, 38 ha at 97 m) and the block north of
  2E/2F (lon 2.585–2.598, lat 49.0105–49.0128, 18 ha at 96 m). The survey
  reads 102 and 99 m there in the owner's datum.
  - The owner lowered both whole. 28k (229 b) says their level is set by "the
    tunnel-mouth objects, the buildings and the road grading requirements".
  - No object in the pack states a lower floor there: they are groundside
    lots (`dsf:pol178`, `pol250`, `pol559`, …) whose objects follow the mesh.
  - The rule does not lower them. A candidate witness (not measured) is the
    road graph: a landside zone whose every road link to the rest of the
    airport leaves through a level-B region or a tunnel mouth is itself
    level B. → O1.
  - At S2 the north block reads 96 m in the survey too (1260–1400 m along
    S2), so the mesh already shows a cut there with no patch.
- **D2. The level A datum.** The owner's T2 is one flat 103 m apron. The plan
  keeps the solved level A, which follows the survey's 7 m of relief across
  T2, and puts B a constant 7 m under it (Q342 a, 226 a: judged by depth).
  - The depth matches: 7.0 m against his 7.0.
  - The absolute level does not: 98.4–99.6 against 96 on the west of S3, and
    94.7–95.3 against 96 at S2.
- **D3. Trench width under a deck carrying a runway (S4).** The owner cuts
  the A1's carriageways (44–46 m). The rule runs the region under the deck at
  full width (Q343 a: the A1 under H17/H18r/H19 is not a lone road under a
  lone deck), which gives 72 m. → O2.
- **D4. Depth under the A1 decks.**

  | deck | owner | plan |
  |---|---|---|
  | H18r, H19 (runway 09R/27L) | 7 m | 7.5 m (slab over a runway, rung 5) |
  | H17 (taxiway, frame reaching 5.46–5.82 m) | 7 m | its own bottom, 5.5–5.8 m (rung 1) |
  | H7 (east, slabs) | 7 m | 5.0 m (30g) |
  | H15 / H16 | 9 m | 7.3 / 10.5 m (own bottoms) |

  The owner holds ~7 m almost everywhere. → O2.
- **D5. Corridor west of 2.570 is half width.** The planned region there is
  the tunnel ramp and the viaduct cover (68–76 m). The owner's corridor runs
  facade to facade (136–152 m). The part of the §27 apron lot `dsf:pol459`
  north of the ramp stays reachable by a 24 m aircraft passage, and so stays
  level A. A wider passage or a different witness (the terminals 2A/2C
  themselves; the engine reads no lower storey for them) would close it.
- **D6. Bare ground the owner lowered.** On the corridor's south fringe at
  lon 2.578–2.584 (S3 1760–2090 m) and inside the T2 west loops
  (2.557–2.562, 49.006) there is no patch surface today. The rule only takes
  groundside surfaces as "ground between".
- **D7. Pier lower storeys.** The engine's existing lower-level landings
  extend north into the 2E/2F pier footprints (lon 2.574–2.580, lat
  49.0055–49.007, "fern" shapes). The owner keeps those at level A. This is
  today's `low_extent` reading, not new, but the region inherits it.
- **D8. Bores the owner did not cut.** Short N–S bores under the taxiway
  decks (lon 2.580–2.582, lat 49.009–49.0145, and lon 2.551, 49.0095–49.011)
  are engine tunnels today, so the plan keeps them as small regions. The
  owner's patch leaves the ground there natural.

## 11. Owner questions this round raises (for the master to number)

- **O1 (D1).** Should a landside zone whose road links all pass through a
  level-B region or a tunnel mouth sit at level B? (a) Yes, the road-graph
  witness: Roissypole and the north 2E/2F block become regions. (b) No: only
  object-witnessed areas are regions, and these zones keep their own ground.
- **O2 (D3/D4).** Under a pack deck carrying a runway or taxiway inside a
  region: (a) as ruled, the region at the deck's full width; depth = object
  bottom, else 7.5 m under a runway or taxiway, else 5 m. (b) As the owner's
  LFPG patch: the carriageways' width and one ~7 m depth for the whole
  region.
- **O3.** A region's open edge inside a runway strip (the A1 trench where it
  leaves runway 09R/27L): is the vertical step exempt from 06n's "no walls in
  the strip", as portal cuts are (26k)? The owner's patch has the walls.
- **O4.** Are basins (closed pack pits) and §45 open channels level B, or do
  they keep their own laws?
- **O5 (internal, master).** One 5 m constant: `tunnel.clearance_m` (5.0) is
  the level-B one. Does the §45 channel keep `bridge.clearance_m` (5.1)?

## 12. Not done in this round

- No engine code. No capture taken; the lfpg6 capture was replayed through
  the planar stage only, under this tree. No build.
- P1 and P2 were not run.
- The §2.2 rule was measured on LFPG only; the dry A/B on five captures
  (§8 (2)) is the code round's first step.
- No installed pack ships a base mesh for +49+002. All three LFPG DSFs are
  overlays (`sim/overlay`):
  - `c_FRA - 100_airport - 2_LFPG_PARIS_TAIMODELS_XP12`;
  - `c_FRA - 100_airport - 1_LFPG_PARIS_T1_2_3_XP12`;
  - `LFPG ROBER` (Disabled Test).

  So there is no developer mesh to compare against.
- Q271's bottom-to-bottom grading between object floors and the run-out
  ramps' tops are not drawn in the pictures (steps only).

## 13. Owner answers (2026-11-03T06:05:23Z) and what they change

These were relayed by the master, who also answered O5 and set O3's
provisional handling.

- **O1 (a): landside zones by the road graph.** Step 9 is added to §2.2. A
  landside zone joins a region when all three hold:
  - it is a connected groundside area of lots and roads inside the aerodrome
    boundary;
  - level A, the boundary or regions bound it;
  - every mapped road that links it to the rest of the road network passes
    through a level-B region or a tunnel mouth before it reaches natural
    ground.

  The zone takes that region's level. This is what lowers Roissypole and the
  block north of 2E/2F (D1). A zone with any road link that leaves at grade
  stays at its own ground (Q184).
- **O2 (width): a deck carrying a runway or taxiway is a cover, not a seed.**
  Under it the region is the roads that pass under it, at carriageway width
  plus verges (`[level_b] verge_m`, each side), not the deck's footprint. The
  owner's A1 under runway 09R/27L measures 44 m: the two carriageways plus
  their verges. The step at the road's edge is vertical, and there is no 30b
  bank, because the road runs under more than one deck. §2.1's hard-deck row
  and Q343 (a)'s "full width" are read accordingly. Full width applies only
  where the region ALREADY spans the deck from other seeds (the T2 corridor
  under its taxiway decks).
- **O2 (depth): one constant depth per region; decks do not set it.** §3's
  per-object floors are withdrawn for decks. A deck inside a region never
  sets the region's depth. Its frame bottom is a check: the floor stands at
  least `[tunnel] clearance_m` (5.0, O5) under the deck top, and never above
  the frame's bottom where the frame reaches that clearance. The ladder,
  amended:
  1. the region's own objects (lower storeys, retaining-wall feet, bridge
     edges, trench and tunnel-mouth floors, covered-cut liners), as their
     area-weighted median;
  2. **the airport's level B**: for a region with no object of its own, the
     area-weighted median depth of every object-stated region at the airport
     ("one lower level (B)", RULINGS 11-03b). This rung is the master's
     reading and gives LFPG's A1 7.03 m against the owner's 7 m;
  3. 7.5 m under a runway or taxiway;
  4. 5.0 m under a flat deck (30g);
  5. credible lidar if it clears 5 m (never under a deck or viaduct);
  6. 7.5 m.
- **O3 (open; provisional).** A region's vertical edge inside a runway strip
  is exempt from 06n's no-wall rule, as portal cuts are (26k).
  `wall_in_runway_strip` and `_check_no_wall_in_runway_strip` add the
  region's step joints to the `portal_cuts` exemption. It is FLAGGED to the
  owner in every report until ruled.
- **O4 (a): basins and §45 open channels are NOT level B.** They keep their
  own laws and are never seeds. A region keeps off a basin's rim band and a
  channel's corridor, as it keeps off level A.
- **O5 (master): level B's 5 m constant is `[tunnel] clearance_m` (5.0,
  30g).** `bridge.clearance_m` (5.1) stays the channel's.

Order of work, as the master set it:
1. Probes P1 and P2, and the dry A/B on KPHX, KATL, EGLL and KBNA.
2. The implementation.
3. Section views and the level map from the REAL engine (replay), sent to
   the master.
4. ONE closing LFPG build, reporting the T2-area agreement with the owner's
   patch.

P1 by static read (2026-11-03):
- The lower-storey footprint is decided on the pad polygon.
  `low_level.plan_low` needs P, airport and the airside around it;
  `group_low.plan_group_low` the same, plus `group_floor`, which needs only
  airport and the airside cells.
- Both are classification cells, available before the arrangement.
- The held-block selection (`Registries.held`) and the block datum D are the
  arrangement's and the solve's. So the outline can be derived before
  `build_structures`, and the level is tied at solve time (B = paired A − d).

## 14. As built, round 2 (lane b2lvl, 2026-11-03): S2 only

**Landed on the branch: S2, the deck floor at level B.**

- `planar/level_depth.airport_level_b` is the airport's level B, read once
  in `planar/build` before `deck_bridges` (P1 holds).
  - It is the feet-weighted median of the units whose walled feet
    (`low_level.feet_levels`) read a lower storey at least
    `[building_pad] low_level_min_step_m` under the stand-side floor.
  - Readings: LFPG 7.42 m (one unit); KATL 13.0 m (one unit, terminal_F);
    KPHX, KBNA and EGLL none.
- `planar/deck_bridge._road_floor` floors a slab deck (a frame stopping
  short of `[tunnel] clearance_m`) by the §13 ladder:
  - the airport's level B; else
  - `mouth_depth_m` under a deck whose seats stand on runway- or
    taxi-family cells; else
  - the clearance.

  It is never shallower than the clearance. The survey is no longer read
  under a deck (Q344 a), and `_surveyed_road` is deleted. A frame reaching
  the clearance keeps its own bottom (30g (2)).
- H7 east, mechanism and fix. The deeper floor lengthened the design-grade
  ramp of `tunnel:-48960+-19919+-5099+-719@3` (49.01248, 2.58196, the road
  under the H7 taxiway deck north of 2E/2F) and of
  `tunnel:-20675+-6877+-4530+-4529@0` (49.00467, 2.58726, under H2 in the
  2E/2F forecourt) past a bend tighter than their corridors. Both were
  refused with "the approach bends tighter than the corridor", and the cut
  vanished: H7 east's floor rose from 98.0 to 102.2. The fix is
  2026-10-14j extended. A ramp the bend refuses re-plans AT THE CAP
  (`ramp_max_grade`, a shorter ramp; `unframed_ramp.BEND_CAP` / `bend_note`)
  before its bore is refused, through the existing overlap re-plan. Both
  mouths build at 10 %, with floors 93.77 and 93.12.

**Dry A/B (planar re-run on each registered capture, main 5544d9568 against
the branch):**
- KATL, KBNA, EGLL and KPHX: no deck and no tunnel changed.
- LFPG:
  - 24 deck floors deepen to 7.42 m.
  - 38 mouths' floors deepen by 1.6–2.4 m.
  - one mouth refused on main now builds (`tunnel:-1719+-235+-383@0`).
  - none newly refused.

**Not built here; the master runs each as its own lane:**
- **S1, the corridor region.** The first attempt is withdrawn. It grew the
  existing lower-level landings over the viaduct cover, unreachable apron and
  enclosed lots. It grew only ~0.1 ha, and it lifted `building34/p1` and
  `p2` from 7.4/5.8 m to 1.9/0.8 m.
  - Why it grew so little: the corridor floor is mostly the apron page
    `dsf:pol459`, which classify's passage test keeps reachable. Only ~1.2 ha
    of it lies under the OSM viaducts.
  - Two findings block any landing-based region:
    - **landing depth is not held in the solve**, on main and in 1.0.454
      alike: `building64/p3` 1.3 m against 7.0, `building64/p6` 1.4 m,
      `building51/p1` 2.9 m;
    - the region needs the reach read with the covers as obstacles, not as
      bridges.
- **S4, the A1 under runway 09R/27L.** The bore under H18r
  (`tunnel:-21305+-13766+-21304+-160+-13765`, both halves) is refused by
  `structure_overlap.resolve_overlaps`: its corridor overlaps the H19 and
  H17 bores, because OSM maps the A1 as separate tunnels under each deck.
  Nothing is cut there on main either. The fix is the region rule's run
  through: bores on one road chain whose corridors overlap merge into one cut.
- **S3, the road-graph landside zones (O1).**

## 15. Round 3 (lane t2corr, 2026-11-03): S1, the corridor by the covered reach read

Owner (Noah, 2026-11-03T16:44:51Z, verbatim): "I would like to see LFPG built
with the most accurate terrain, bridges all correct, and the central corridor
for T2 cut. Keep the object group together and let the east end float, since
this is a limitation of the scenery package and we can't shape the terrain to
match without violating the tile boundary or grade law. I will review
in-sim."

**Attribution (capture lfpg6, planar re-run on main 110d03e3e).**
- `planar/reach_after_pads` judges each connected PIECE of an apron page
  after the pad cut. The pads cut `dsf:pol459` into 30 pieces. One of them,
  191,899 m2, runs from the stands around 2A–2D through the gaps between the
  terminal blocks into the corridor. Its room reaches the taxiways, so the
  whole piece stays apron (level A).
- The room reaches the corridor through four openings, each wider than a
  taxiway: the west end between the 2A and 2B tips, the gap between the
  north blocks, the gap south of 2D, and the 2E west end.
- The covers already close those openings. The corridor is laced with
  mapped road bridges: the layer-1 loops around 2A/2C and 2B/2D, and the
  layer-2 viaducts along the axis. With them standing as obstacles, no room
  aircraft reach is left inside the corridor, at the 7.5 m default
  half-width or at 11.5 m (code E).
- So the read must change in two ways. The covers must be obstacles. And
  the unit judged must be the pavement the reachable room sweeps, not the
  page piece. The whole-piece verdict is what kept the corridor at level A
  even where the room was cut.

**The rule (one new pass, `planar/reach_under_covers`, run at the end of
`unreachable_after_pads`).**
1. The covers are every mapped `highway` or `railway` way with `bridge`, at
   `layer >= [tunnel] cover_min_layer` (1), inside the aerodrome boundary,
   at its carriageway width. An aircraft cannot pass under a road deck, and
   it does not taxi on one. Aeroway bridges are not covers: aircraft cross
   them (§2.2 step 2).
2. The room is the airside pavement less the covers, eroded by the default
   taxiway half-width (`taxi_half_width_m(law, None)`, no new number).
   Each room piece reaches when its sweep meets a taxi-family face or a
   runway (the 19ag read).
3. On every apron face the covers touch, each connected part of the face
   that the reachable sweep leaves is BEYOND (groundside, `<ref>#beyond<k>`,
   role from `open_default.unclassified_groundside_role`) when:
   - it holds unreachable room;
   - it carries no apt.dat startup;
   - at least `[tunnel] cover_min_share` (0.25, the spec's `cover_min`) of
     it lies under the covers, which makes it a covered lot.
4. The read runs only where the airport's objects state a level B
   (`level_depth.airport_level_b`, handed from `planar/build` through
   `build_arrangement` to `unreachable_after_pads`). EGLL (2 parts,
   13,813 m2) and KPHX (1 part, 2,653 m2) read covered parts but state no
   level B. Ungated, they became groundside lots, and KPHX's census rose
   by 68 adjudicated with 487 airside movers (worst 1.47 m at T4). Those
   covered lots wait for the region round's depth ladder (§3).
5. `low_extent.extend_levels` already takes every beyond piece that meets
   a group's lower footprint into that group's lower level, at the
   objects' bottom (27h). So the corridor becomes level B at the T2
   group's own depth, tied to the group's zero. There is one zero. Its
   value moves with the airside the solve reads it on (see below).

The two keys go in `[tunnel]`, next to the R6 viaduct keys, rather than in a
new `[level_b]` table. One reader each.

**A second finding on the way: the fill band read the level's own lot.**
`low_fill.cut_fill_bands` (28s (3), Q251 a) cuts off the part of a lower
level that stands on fill along a lot. Its lots included the beyond pieces,
which are the pavement the level takes in as its own ground. So the level
read its own area as "a lot beside it" and lost its low half.
- Control: `building34/p2` lost 29,242 of 67,693 m2; `building34/p1`,
  `building51/p1` and `building64/p1` lost 4,705, 2,093 and 1,426 m2.
- With the corridor taken: 50,214 of 143,371 m2, including the whole block
  east of the 2C/2D loop (lon 2.569–2.573).

The fix is at the one call site (`planar/platform.py`): a beyond piece is
never a fill-band lot. A real lot beside a level (KMCI `building26/b1/p1`,
the case the rule was made for) is unchanged.

**Three more findings, from the solve (replays of lfpg6 on main 110d03e3e).**
With the corridor taken, the 143,000 m2 level `building35/p2` solved at
103.94–104.14 m, which is level A, against its pin of 97.59 m.
- **Mechanism.** A group level was held by ONE pin, on its first vertex,
  and a rigid chain to every other vertex.
  - The hard set at the level's open edges was infeasible: pieces of the
    unreachable page the extension did not take were left as lots between
    the level and the apron, and a lot cannot step 7 m.
  - The feasibility LP relaxes the cheapest rows. That was the lone pin
    (one row, 6.4 m), not the hundreds of lot and road rows. So the whole
    rigid level floated to level A.
  - This is the "landing depth is not held" finding of §14, and the
    `building34/p1`/`p2` lift of the withdrawn S1.
- **Fixes, each general.**
  1. `constraints/group_level.group_level_rewrite`: the rigid rows become
     per-vertex pins at the level. A conflict then costs only its own
     vertices.
  2. `planar/low_extent`: a level over unreachable pavement steps at EVERY
     open edge (Q341 a). Its `#strip` riser runs along the airside keep-off
     and the lots it did not take, not only along its pads. Small
     unreachable pieces beside it go into the riser.
  3. A piece of the taken pavement that a structure's keep-off cut off
     from the lower bodies, with no lower body of its own, stands at its
     host level's feet: one lower level.
  4. `planar/reach_under_covers`: a beyond part's open fringe stays with
     the stands. That fringe is pavement outside the unreachable room's
     sweep, not covered, and touching the reachable sweep.

**Not in this round:** the landside zones (S3/O1), the A1 under 09R/27L
(S4), the bare ground the owner lowered (D6), and §2.2 steps 3–8 (ground
between, enclosed faces, run-outs).

## 16. Round 4 (lane lowregion4, 2026-11-04): object-witnessed seeds, one depth per region

Built from the Fable round-4 review (owner yes 2026-11-04T16:03Z: "the changes
are mostly around identifying more cases with more accuracy"). One new module,
`planar/level_regions` (the region record's derivation, one responsibility).

**What is built.**
1. **W1, walls below the zero (`level_seeds`)**, read ONCE in `planar/build`
   beside `airport_level_b`: per partition unit, the walled parts
   (`[placement] chain_min_height_m`) that are no supports
   (`geom/foot_planes.is_support`) whose densest `PLANE_BAND_M` foot plane
   stands at least `[building_pad] low_level_min_step_m` under the unit's
   zero (its stand-side floor where the stands read one, else its authored
   zero) are a seed; footprint = their rings, depth = zero - feet plane. No
   held block, STEPPED base or stand is needed. MEASURED KIAH (capture
   kiahstation): `KIAH_Trainstation2.obj` (unit 60) on the §20 conforming
   pad `building88`, two walled parts with feet at y -3.93; KATL 13 seeds,
   LFPG 6, EGLL 9, KPHX 2.
2. **Step (b), the unreachable pieces a seed touches (`seed_levels`)**, run
   inside `low_level.low_level_split` after `low_extent.extend_levels`:
   each `#beyond` piece within `pad_frontage_m` of a seed footprint, less
   the pads + a riser and the airside + `pad_frontage_m`, is minted
   `<block>/p<k>` (kind `low_level`, witness `walls`) of the held block it
   FRONTS (the predicted-datum block sharing most of its rim), at `y_lo =
   -depth` under that block's datum, with its riser strip along the pads
   and every open edge (`low_extent._riser`). The ground confirms it
   (#1115, in world terms): the piece's DEM median must stand under
   `datum_pred - depth / 2`; EGLL's 9 seeds mint nothing on it (a storey
   over level ground).
3. **Steps (f) + §3, one region, one depth (`region_depths`)**: lower
   levels held at one zero (one group's witnesses and top, or one block's
   datum) that touch and whose floors lie within one `PLANE_BAND_M` are one
   region at the area-weighted median floor. Floors a band or more apart
   keep their object step (KATL `building46` p5-p7, 27h). The riser strips
   between members keep their refs and stand flat (re-reffing them into
   the level moved 4 riser-top vertices 6.3-7.6 m at the strips'
   junctions, MEASURED LFPG replay, refuted and removed).

**Refuted and removed in the round.**
- A seed arming the covered reach read (`reach_under_covers`): it turned
  EGLL (2 parts, 13,813 m2) and KPHX (1 part, 2,653 m2) covered apron
  groundside with no ladder depth to take them (dry A/B; S1's measured
  KPHX cost of the same was +68 adjudicated and 487 airside movers). It
  stays gated on an object-stated level B until the ladder (§3) mints
  covered regions.
- Opening the riser across the at-grade roads leaving a level (the road's
  own law as its run-out): KIAH replay within_shape 112 -> 321,
  road_cross_section 28 -> 52. Step 8's run-outs need the climbing
  run-out record (below).

**Not built this round** (spec §1 W2/W3, §2 steps (c) (d) (e) (g), §4):
W2 as a seed on its own; W3 decks over mapped roads (KLAX) and the
viaduct_road replacement; (c) region roads/rails; (d) through covers;
(e) enclosed faces; (g) run-outs -- a lowered region's roads CLIMB out,
and `cut_runout` / `constraints/ramp_runout.landing_runout_rows` are
written for a run-out that descends (a sign on the record and the mirrored
rows); the region record `PlanarMap.level_regions`; `region_depth`'s
ladder rungs 2-5.

### 16.1 Round 4b (owner 2026-11-04T18:31Z / 18:42Z / 19:09Z)

**Built.**
- **A building the roads run through is one flat lower level.** A W1 seed
  now carries its PASSAGE: the at-grade mapped carriageways across its
  footprint. Its pad is cut by `low_level.level_cut` (whole, frontage band
  kept as the block) into ONE flat level at the walls' depth, tied to the
  pad's own block. The unreachable pieces it touches join it (step (b)),
  each with a riser that fills the airside keep-off up to a riser short of
  the apron rim. A seed with no passage (a basement, a storey over level
  ground) mints nothing. This replaces round 4's step (b) on its own.
- **Clearance (owner 18:42Z).** The object's underside over the passage is
  read from its own OBJ geometry (`planar/level_underside`: the lowest
  horizontal static solid per 2 m cell above the floor; the lowest sloped
  solid reported apart) against `[tunnel] clearance_m` (5.0, "the road's
  vertical clearance under the roof"; no new key). Where the soffit stands
  less than that over the walls' feet, no level is minted and the note says
  so: the walls and the clearance disagreeing is the owner's to rule.
  - KIAH station: soffit y +1.36 over feet at -3.93, so 5.29 m clear.
  - LFPG T1 (`T1_16-18`): soffit -2.99 over -5.19, so 2.20 m (SHORT, no level).
  - LFPG 2A (`2A_50/51`): soffit -0.10 over -5.51, so 5.41 m.
- **Step 8 run-outs, the road half.** `cut_runout.cut_runouts(roads=True)`:
  - The roads' ROUTES are walked through junctions (`viaduct_road._route`).
  - There is one end per route.
  - The run is laid off the level furthest from the ground (one plane band).
  - The record's `sign` is -1 where the road climbs.
  - `constraints/ramp_runout.landing_runout_rows` mirrors its rows by that
    sign, anchored on a level vertex (`from_level`).
  - A riser opens only where a minted run-out leaves through it.

**Refuted and removed.**
- **W3 deck levels at KLAX** (one covered World Way stretch, 9,810 m2 at
  T2's depth, the skybridge pads cut through as covers). Adjudicated rose
  205 -> 291, from 4.4 m terrace steps against the T5 / walkway pads, the
  level bent 4.07 m by relaxed landing rows, and road-exit steps.
  - The KLAX case needs the riser exemption and the terrace declaration
    extended to the OTHER pads a region meets (`constraints/riser.
    riser_sets` reads only the level's own block, and the census reads an
    undeclared pad-to-level step as `terrace_actual_step`).
  - Attempt kept in the lane scratch, not in the tree.
- **Run-outs for the levels the other passes mint** (`region_runouts`,
  KATL `building46`, LFPG T2). KATL road_cross_section 53 -> 208 with
  crossings grouped (strips up to 111 m wide), then 53 -> 225 with one end
  per route. Two attempts; withdrawn. LFPG's T2 corridor therefore has no
  run-outs to the D1/A1 roads this round.
- **Releasing the run-out ground from the pads by the riser exemption**
  (`ground_refs`): the station level was pulled to 27.9 m. Withdrawn.

## 17. Round 5 (lane lowregion5, 2026-11-04): run-outs per road, stage-1 gate, T1 at its walls

Built from the Fable review's spec (TWO-ROUND-CAP-REVIEW #1852/#1717, E1/E2/E4,
F1/F2) and the owner's rulings of 2026-11-04T20:47Z (airside movement under
0.5 m that mints no violation is allowed while grading is refined; KLAX back
in scope as a flat region up to the terminal walls; LFPG T1 at the walls'
depth). Captures: `kiahstation/KIAH.pkl`, `katl1306/KATL.pkl` (registered
this round), `lfpg6/LFPG.pkl`, `lowregion4/KLAX.pkl`.

**Built.**
- **E1, a region's own strips take none of its ends** (`level_regions._run_out`):
  the riser strips of the levels whose run-outs are read are left out of
  `taken`; every other pad and the airside still take an end, now NAMED
  (`level_runout_ends["taken_by"]`: `lat,lon` and the takers' refs).
- **E2, one end per crossing, its strip its own road** (`cut_runout._road_runouts`):
  `_routes` returns each route with its crossing way's carriageway
  half-width (ribbon classes only); an end is one route's crossing of the
  rim (never grouped across `END_M`; two routes over one crossing are one
  end), its strip that half-width either side, clipped to that route's own
  carriageway (never the union of every carriageway).
- **E4**: run-outs are read only for the levels `seed_levels` mints (the
  passage level and its pieces); no other pass's level asks for them.
- **T1 at its walls (owner 20:47Z)**: a seed whose object's soffit stands
  short of `[tunnel] clearance_m` over its wall feet is minted at the walls'
  depth anyway; the note and the record report the clearance.

**Measured and not built.**
- **F1/F2 (the passage level off stage 1's map; its vertices freed from
  stage 1's carried levels).** Built and replayed at KIAH: verify 629, the
  same 629 rows as the round-4b head, the stage-1 map's 25,113 vertices the
  control's, `building88` still 27.97-28.01 against the control's
  28.00-28.08 and the same 3 apron movers (0.11 / 0.08 / 0.01 m at
  29.98711, -95.33286). The stage-1 map is not re-derived through
  `low_level_split`, so the premise (the level re-seats D_88 on stage 1's
  map) is refuted; the movers are the station pad's remnant band and its
  apron sliver in stage 2. They carry two small airside rows the control
  has not (`pad_frontage_infeasible` 0.047 m at the mover, `frontage_near_miss`
  0.05 m on `pav62#plateau:building56`). Withdrawn.
- **KIAH run-outs.** The spec's mechanism (§1.2 of the review: the region's
  own strips take every end) is not the one at work: the probe on the
  round-4b head reads all 4 ends refused `no_datum` -- `building88` is a §20
  conforming pad, whose `datum_pred` is `None`. With a datum injected
  (probe), the head minted 1 and refused 3 (taker `building94`); with E1/E2,
  4 minted, 1 refused (`building94`). Laid off the fronted block's predicted
  datum (`building56`, 26.96; the pad solves at 28.08) the replay read verify
  632 -> 704 (`road_cross_section` 28 -> 63, `within_shape` 112 -> 140),
  census adjudicated 585 -> 612, tunnel walls east of the station moved up to
  1.85 m; with the solved datum injected (oracle arm, 28.08) 632 -> 710,
  adjudicated 585 -> 619 (`within_shape` +12, `pavement_over_road_cap` +13,
  `cross_shape` +5). So the run-outs themselves, not the prediction, cost the
  rows at KIAH; the conforming-pad datum is not supplied and KIAH's exits stay
  refused `no_datum` (counted).
- **KLAX, three attempts, all withdrawn** (control replay: verify 477,
  census adjudicated 205):
  1. *A storey beside its roads*: a W1 seed whose at-grade carriageways run
     within `pad_frontage_m` of its walls (T2, `building84`, unit 129, y -4.40)
     minted the pad as one level at 32.13 m plus the curb carriageway as a
     piece, with two run-outs: verify 477 -> 748 (`road_cross_section` 9 ->
     175), census 205 -> 930 (`hard_conflict` +418): the World Way ribbons
     span the level and the walkway pads (36.5 m) beside it.
  2. *Covered road out of the pads*: the carriageway under pack geometry
     standing `clearance_m` up leaves the pad (the walkway pads
     `building49/53/68/75/80`): verify 477 -> 750 (`road_cross_section` 9 ->
     179): the road stands between the two pad halves at 36 m.
  3. *Elevated objects stand on no pad*: dropping every pad most of whose
     ground lies under parts based `clearance_m` up separates the five KLAX
     walkway pads (92-96 %) but also takes KATL's terminal pads
     (`building33/35/39/50`: split roof objects, `Techos_Terminales` at base
     y 9.6, 86-100 %) and KLAX's Delta hangar (82 %). No witness read off the
     parts separates a walkway over a road from a terminal authored as a
     separate roof object: an owner/spec question, not a threshold.
  The KLAX finding for the next round: the World Way ribbons at T2 rise
  32.6 -> 36.2 m to the T2 pad's edge and 32.5 -> 36.5 m under the walkway
  pads (control `lowregion4b_KLAX`); a flat region up to the walls needs the
  walkway pads gone (a witness for "elevated over a road") AND the step at
  the T2 wall declared (the wall-terrace release of `airport/road_ramp.
  wall_terraces`, a storey wall that retains its height) -- a consumer census
  of its own (riser, pad_terrace, road terrace, publication, census reader).

**Site numbers, round 5 as built** (replays `--from planar` on the
registered captures; controls: KIAH and KATL the branch with the seeds
patched off, LFPG the round-4b head 5829e7731):
- KIAH: `building88/p1..p3` one level at 24.09 m (wall feet -3.93 under the
  zero; station remnant 27.97-28.01, Terminal D 28.08); verify 629 (control
  632; the round-4b head's own 629 rows); census adjudicated 584 (control
  585); run-out ends 4, all refused `no_datum` (conforming pad); airside
  movers 3 (0.11 / 0.08 / 0.01 m, the apron sliver at 29.98711, -95.33286,
  inherited from round 4b); the 13 structure movers are groundside
  `tunnel_ramp` / `tunnel_wall` rim vertices at 29.98736, -95.33087, 0.10-0.13
  m, no road contact (the ramp follows the lowered lot: §2.3 outcome (b)).
  Closing build `lowregion5_KIAH` rc 0, 547 s, census adjudicated 751 (the
  round-4b build `lowregion4_KIAH`, at f888dcd8f before 4b's last commits, 732:
  the +19 are the classes the 4b commits brought, `cross_shape` 5,
  `frontage_near_miss` 2, `within_shape` +9 on `pav62#beyond1`; the replay
  reads round 5 equal to the 4b head).
- KATL: verify 2200 -> 2199 (`road_cross_section` 53 -> 52), `level_runouts` 0.
- LFPG: T1 `building82/p1` minted at -5.19 (13,744 m2) under `T1_16-18`,
  soffit -2.99 -- **2.20 m clear**; `building67/p1` -5.51 (5.41 m clear);
  the T2 region `building34/35/51/64/p1 + building35/p2` at -6.97 unchanged;
  run-out ends 0; verify 3164 -> 3166 (`pad_flat` 83 -> 85, the T1 level);
  census adjudicated 2403 -> 2403, 0 new rows; solve-owned airside movers
  1 x 0.01 m.
