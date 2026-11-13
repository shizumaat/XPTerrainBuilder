# Interchange levels: the bridge model for N stacked levels (spec, ready for an Opus lane)

Issue: #1971 (KDEN, 39.842347, -104.673859: rail under two crossing road decks).
Status: SPEC ONLY. No engine code was written in this round (owner
2026-11-13T02:12Z, relayed by the master: "with a fable spec, it's probably
more efficient to use Opus to implement"). The owner asked for "a natural
extension of the existing bridge model" (2026-11-13).
Author: lane l1971 (Fable). Read on base 79a3a386d; the implementing lane
starts from the batch-15 tip or later (it must hold `0a1a225c0`, #1903's
drawn gate).
Law it builds on: RULINGS 2026-10-30a (one zero, flush at both end lines),
30f (road overpasses, decks read before the solve), 2026-10-26d (a deck over
the pack's own cut), 2026-11-03b / 03c (two levels, the depth ladder: objects
first), 2026-11-06 (#1903: a trench object's own floor is the cut),
2026-11-07b (1) (the author's ground), 2026-11-11b (decks grade like bridges),
2026-10-28k Q233 (rail run-outs), 2026-10-05e (no airport-specific code).
Builds on: `two-level-regions-20261103.md`, `deck-end-anchors-20261103.md`,
`lgav-corridor-cut-and-deck-ends-20261106.md`.

Everything under "MEASURED" was read on the capture
`/Users/noah/XPTerrainBuilderData/.harness/frames/l1971/KDEN.pkl`
(`v2_solve_replay --capture KDEN`, base 79a3a386d, usgs3dep 1 m inset,
registered in `docs/frames.jsonl`). Paths are under
`Ortho4XP/src/auto_patch_v2/` unless they say otherwise.

## 0. Summary

A pack may build an interchange from several objects that stand over one
another: a trench with walls at the bottom, a road deck over it, and another
road deck over that. The engine reads each object alone today. At KDEN that
gives four wrong readings at one place:

1. The trench walls are refused by every trench reader and become two
   building pads.
2. The lower deck is read as an overpass over the road it carries, so its
   zero is put on that road.
3. The road the lower deck carries is mapped at grade, so it is graded as a
   terrain road straight across the rail trench.
4. The upper deck's zero is read off the lower road and off its own approach
   roads.

The rule this spec adds is one record, the **deck stack**:

- **Level 0** is a floor the pack states with walls that stand on their own
  zero (the trench).
- **Levels 1..N** are the hard decks that span it, in the order of their
  authored height.
- **One zero.** Every member stands on the level-0 floor, so the whole stack
  has one zero. It is read from the decks' end lines, as a bridge's is.
- **The terrain** is the lowest level only: the floor between the walls, the
  ground at the walls' top beside them, and the roads' own ground up to each
  deck's end lines. Decks are objects. A road a deck carries has no terrain
  under the deck.
- **One owner per thing.** Each placement, and each piece of ground, is
  claimed once (§3.9).

The stack is expressed in records the engine already has: the floor is an
`ObjectFloor` (#1903), a carried road stretch is a mapped bridge
(`bridge=yes`), the members' seats are object-floor seat records, and their
pads leave through a pad shade. So most passes need no change (§5: 9 passes
are edited, the rest read an existing record).

MEASURED KDEN, what the rule gives (pre-registered, §8):
- stack zero 1626.56 m (from five deck end lines);
- rail floor 1626.51 m between the walls, through under both decks (today:
  the lidar's plug at 1630.1 m and a road ribbon across it);
- lower deck ends at 1630.56 m, upper deck ends at 1638.54 m, the roads
  graded to them (the roads move -0.5 to +1.5 m at the five ends);
- the four objects written at one elevation.

One thing the owner should know before the build: the pack's model is
vertically compressed. Its rail floor is 4.0 m under the lower deck's ends;
the real one is about 7.5 m under. With the decks at the real road level, the
trench floor stands 2.0 to 5.4 m above the lidar's floor (§10, O1).

## 1. The case, as measured

### 1.1 The pack's objects

Pack `c_USA - 100_airport - KDEN - Denver International Airport`, tile
+39-105. Four placements, all `OBJECT` (AGL 0), anchors within 4 m of each
other:

| id | resource (`Objects/Landside/Bridges/`) | anchor (lat, lon) | heading | what it is (authored y over its zero) |
|---|---|---|---|---|
| `dsf:obj31298` | `Train_Walls.obj` | 39.842252, -104.673825 | 0.0 | two retaining walls 310 m long, feet y -0.05, vertical faces 0 → 3.5, cap strips at y 3.50 (3,268 m2, 5.5 m wide), NO floor face; piers to y 6 and y 12 |
| `dsf:obj31299` | `Over_Train_Bridge.obj` | 39.842262, -104.673858 | 0.0 | a small bridge 100 m north, y 3.0..5.1, no hard deck |
| `dsf:obj31311` | `Mix_Master_Lower.obj` | 39.842265, -104.673840 | 6.17 | `ATTR_hard_deck` plate, 60.0 x 24.0 m, arched: y 4.00 at both ends, 5.08 at the crown; lowest solid 2.48 |
| `dsf:obj31312` | `Mix_Master_Upper.obj` | 39.842286, -104.673846 | 354.32 | `ATTR_hard_deck` plate, two pieces (100 x 21 m and 90 x 15 m), flat at y 11.98; lowest solid 8.98 |

They are four partition units (`unit:140/142/143/147`). They are not
co-placed (`deck_bridge.co_placed` needs one anchor and one heading), so no
frame rule links them today.

The author's own Ortho4XP patch ships in the pack (`Patches/KDEN.patch.osm`,
not read by the engine): flatten 1628 in the trench, 1632 on the lower road's
approaches, 1640 on the upper road's. So the author's three levels are 0 m,
+4 m and +12 m over the trench floor, which is what the objects state
(0, 4.0, 11.98).

### 1.2 The map (OSM feeds of the tile)

| way | tags | role in the interchange |
|---|---|---|
| `big_roads:-4171`, `-4166` | `railway=rail tunnel=yes layer=-1`, 67 m | the rail under both decks |
| `big_roads:-17142`, `-17141`, `-5731`, `-5547` | `railway=rail` | the rail in the open trench north and south |
| `big_roads:-18866`, `-5740` | `highway=primary`, no bridge tag | the lower road; it runs ALONG the lower deck (skew 2.4 and 14.6 degrees to the deck's long axis) |
| `big_roads:-2141` | `highway=primary bridge=yes layer=1`, 61 m | the upper road on the upper deck's 100 m piece |
| `big_roads:-2149`, `-3314` | `highway=primary`, no bridge tag | the upper road's approaches; the deck's ring overhangs the mapped bridge by 18.0 m and 20.8 m of them |
| `small_roads:-3638` | `highway=unclassified bridge=yes layer=1` | the second carriageway, along the upper deck's 90 m piece |

So OSM states three levels too (-1, 0, 1), but it puts the lower road at
grade and the rail in a tunnel, where the pack builds a deck over an open
trench.

### 1.3 The ground (usgs3dep 1 m inset)

- Rail floor in the open trench: 1621.1-1621.5 m south of the decks,
  1622.6-1624.5 m north.
- Under the decks the lidar keeps the lower bridge as ground: a plug at
  1629.5-1630.3 m across the trench for about 50 m (frame y -2175..-2125).
- Lower road, 5 m outside the lower deck's ends: 1631.08 m (north-west end),
  1629.03 m (south-east end).
- Upper road, 5 m outside the upper deck's ends: 1639.38 m (north-east),
  1637.74 m (south-west), 1639.50 m (north-east end of the second piece).
- Banks beside the trench: 1629-1634 m west, 1626-1639 m east.

### 1.4 What the engine reads today (planar stage re-run on the capture)

| object / way | today's reading (the engine's own note) |
|---|---|
| `Train_Walls.obj` | `tunnel_objects`: "a building's wall, not a tunnel edge wall: 12.00 m from the crest at +11.95 m to its lowest solid (> mouth_depth_m 7.5)". The crest read is a pier cap, not the walls' 3.5 m top. `basins`: "a slab sitting on datum relief". Result: two building pads, `building19` (422 m2) and `building21` (1,237 m2), under its west cap strip. |
| `Mix_Master_Lower.obj` | `deck_bridges`: "no pavement runs across it (27c)". `road_overpasses`: "a road overpass over way(s) [-18866, -5740], deck y +5.08 over its zero; the zero sits on the road beneath". The "road beneath" is the road it carries. |
| `Mix_Master_Upper.obj` | `road_overpasses`: over `[-18866, -3314, -2149]` and `[-5740]`: the lower road (which is on the lower deck there) and its own two approaches. |
| `Over_Train_Bridge.obj` | no reading; a plain object |
| rail `-4171+-4166` | refused at both ends: "the credible survey carries the road ... rail follows the survey; nothing is cut a second time (28k (226 a))". True at the ends (1620.9 / 1622.4 m); false between them, where the survey is the plug. |
| lower road | one terrain face `big_roads:-18866` (2,071 m2) runs across the trench at the site. |
| map at the site | `decks 0, structures 0, object_floors 0, overpasses 4` |

The owner's 1.0.478 build (2026-11-08) shows the result: pads at 1624.8 m
under the wall strips, the lower road dipping from 1629 to 1625 m across
them under its own deck, the lower deck's zero on that dipped road
(1625.39), the upper deck's at 1625.80.

### 1.5 The gaps, named

- **G1.** A trench the author built UP from its zero (walls rising from the
  floor to the ground level) is read by no trench reader: every one of them
  measures a wall DOWN from the zero.
- **G2.** `overpass_deck._road_under` takes any mapped non-bridge road whose
  centreline crosses the deck piece. It cannot tell the road a deck carries
  from a road under it.
- **G3.** A road a pack deck carries, which OSM maps at grade, is a terrain
  ribbon under its own deck.
- **G4.** Each deck is seated alone. Nothing says the members stand on one
  ground.
- **G5.** Under a deck the lidar's "ground" is the deck. Nothing removes the
  plug from the trench (`airport/bridge_ground` reads mapped bridges on
  highways only, and lowers targets, not the trench).

## 2. What the bridge model already has (and what the stack reuses)

| piece of the bridge model | where | reused for the stack as |
|---|---|---|
| a hard deck is read before the solve; its END LINES are where the carried route drives onto it; ONE zero, flush at both end lines | `planar/deck_bridge`, `constraints/edge_deck` (30a) | the same reading for each stack deck, with a ROAD as the carried route (§3.4, §3.5) |
| the deck's zero is the mean over its end lines of (ground there less the deck top there); the ground under a deck is never read | `constraints/deck_anchor.derive` (11-03c, Q344 a) | the stack's zero (§3.6) |
| a trench object's own floor is the cut over its whole footprint; its frame is written whole at the zero the floor was read at | `airport/object_floor`, `planar/object_floor_cells`, `constraints/object_floor` (#1903) | the level-0 floor IS an `ObjectFloor`; the members are its frame (§3.7, §3.8) |
| the depth ladder: an object that states its own bottom comes first (retaining-wall feet), the survey only where no object does | two-level spec §3 / §13 | the floor stands at the walls' feet (§3.7; O1) |
| a mapped bridge way is no terrain road | `airport/deck_signature.is_bridge_way` and its 16 readers | a carried stretch becomes a mapped bridge at ONE site (§3.5) |
| a deck over the pack's own cut is no road overpass | `overpass_deck.road_overpasses(cut_objects=...)` (26d) | the members are passed as `cut_objects` by the existing line (§5 row 17) |
| a mouth's walls are no pad | `airport/entrance_shade`, `geom/cluster_outline.pad_shade_extra` | the members' pad shade (§3.9) |
| rail ends grade at the rail law, never step | `geom/ramp_profile.runout_profile` (28k Q233) | the floor's run-outs (§3.7) |
| the #1903 gate: what X-Plane draws (mesh, patch → drawn, objects), run by every `--tile` build with `--pack-copy` | `tools/harness/drawn_gate.py`, `tools/drawn_check.py` (on batch 15, `0a1a225c0`) | the closing bar (§8.4) |

Nothing in the stack needs a new solver row family, a new face role, a new
sidecar key or a new law number.

## 3. The model

All geometry is in the airport frame. "y" is an authored height over a
placement's zero. Every number is an existing law-table key; none is new.

### 3.1 The record

New file `model/deck_stack.py` (the model holds no shapely; the model
package may be imported by `constraints`):

```
StackDeck(object_id, resource, piece: int, ring: tuple[XY, ...],
          level: int,                       # 1..N
          carried: tuple[int, ...],         # way ids of the carried route
          under: tuple[int, ...],           # way ids crossing beneath
          end_a: tuple[XY, ...], end_b: tuple[XY, ...],   # stations, () if none
          top_a: float, top_b: float,       # plate y ON each end line
          plate: tuple[tuple[XY3, XY3, XY3], ...])  # frame x, y, authored y
DeckStack(id: str,                          # "stack:<walls object id>"
          walls_id: str, walls_resource: str,
          members: tuple[tuple[str, str], ...],      # (placement id, resource), walls first
          zero_z: float, zero_spread_m: float,
          end_zeros: tuple[tuple[str, int, str, float, float], ...],  # deck, piece, end, ground, top
          feet_y: float, crest_y: float,
          floor: tuple[XY, ...],            # the corridor polygon between the walls
          rim: tuple[tuple[XY, ...], ...],  # the wall lines (outer side of the floor)
          runouts: tuple[tuple[tuple[XY, ...], float, float], ...],  # strip ring, z at the walls, z at the lip
          under_ways: tuple[int, ...],
          decks: tuple[StackDeck, ...],
          notes: tuple[str, ...])
Airport.deck_stacks: tuple[DeckStack, ...] = ()
Airport.stack_shade: object | None = None      # shapely, like entrance_shade
Airport.osm_ways_mapped: tuple[OsmWay, ...] | None = None   # the ways before §3.5's rewrite
```

### 3.2 Level 0: floor-datum walls (the witness)

A placement W states a level-0 floor when ALL of these hold. Each is
geometry; none is a name.

1. **Walls rising from its feet.** W has genuine vertical faces
   (`|n_y| < [tunnel.object] plate_normal_y_min`) that start within
   `plate_bin_m` of its lowest genuine solid `feet_y` and rise at least
   `edge_wall_min_skirt_m` (1.5).
2. **A crest that is the walls' top.** `crest_y` is the top of the
   LARGEST-AREA `plate_bin_m` bin of W's near-horizontal faces above
   `feet_y`, holding at least `plate_min_area_m2` (100). It is never the
   topmost bin: a pier that rises through the crest to carry a deck is not
   the wall. MEASURED: bins {3.0-3.5: 3,275 m2, 11.5-12.0: 346 m2} → crest
   3.50.
3. **A trench's depth.** `crest_y - feet_y >= [tunnel.object]
   floor_sunken_min_m` (2.0). The crest plates beside the walls are the
   author's ground (07b (1)); the floor stands that far under it. MEASURED
   3.55.
4. **No floor of its own.** W's near-horizontal faces within `plate_bin_m` of
   `feet_y` hold less than `plate_min_area_m2`. An object with a floor plate
   is the floor readers' (`airport/object_floor`), not this one's.
5. **A corridor.** The walls stand on both sides of a strip at least
   `hull_min_length_m` (10) long: the FLOOR polygon of §3.3 is not empty.
6. **Something runs in it.** A mapped `highway` or `railway` route runs along
   the corridor inside the floor (the UNDER-WAY; MEASURED: the six rail ways
   of §1.2, 54-169 m each inside the floor).
7. **A deck spans it.** A hard-deck piece of the population
   `deck_bridge._frames` reads (`deck_kind` flag or signature), of W's own
   placement or another, crosses the corridor from one wall to the other, and
   that deck is a MEMBER (§3.3).

A wall object with no deck over it, or with a deck that is not a member, is
not a stack and keeps today's reading. That keeps the rule off plain
retaining walls, fences, garages and buildings (#1961, #1966, #1950).

### 3.3 The floor polygon, and who is a member

**The under-way.** Of the mapped `highway` / `railway` routes (§3.4), the
one with the greatest length inside the hull of W's wall faces, with at
least `hull_min_length_m` of it between two facing wall faces. None: no
floor, no stack.

**The floor.** Stations every `[tunnel.object] wall_sample_m` (2.0) along the
under-way's route (the `tunnel_walls.Station` idiom): at each, the
perpendicular is cast both ways to the nearest wall face of §3.2 (1); the
floor is the polygon through the left and right hits. A station with a wall
on one side only takes the previous station's half-width on the other. The
floor ends at the last station that has a wall on either side. Do NOT use the
walls' convex hull: MEASURED it flares to 69 m at the south end, where the
trench is 12-15 m wide. `tunnel_walls.read_wall_lines` does not read this
object either (MEASURED: "the crest plate is a slab 5.54 m thick in plan"
on the caps; "piece 0 has 3 free ends" on the wall band), so the cast is new
code; look at `airport/wall_geometry` and `airport/wall_family` for a
pairing to reuse before writing it.
MEASURED (hull construction, upper bound): 7,514 m2; 11.7-12.6 m wide under
the decks, 20-27 m north.

**Members.** W itself, and every placement of kind `OBJECT` whose anchor
stands on the floor (inside it, or within `[tunnel.object]
cover_placement_tol_m` (1.0) of it) at W's own AGL. The author stood them on
the floor, so their zero is the floor's zero. MEASURED: all four anchors are
inside (0.21, 3.08, 1.54 and 2.09 m from the edge).

A deck piece that spans the corridor but whose placement is not a member
(its anchor is elsewhere, or it is `OBJECT_MSL`) is NOT read by the stack. A
note says so and it keeps today's reading. If no member carries a spanning
deck, there is no stack.

One placement belongs to at most one stack, and to no stack if an earlier
reader already claimed it (a floor, a corridor, a basin: the `taken` set, as
`read_portal_floors(taken=...)` takes it).

### 3.4 Levels 1..N: the decks, what each carries, what runs under

For each member's hard-deck PIECE (`deck_bridge._frames`, `_plate`):

- **Axis.** The piece's minimum rotated rectangle. The END edges are its two
  short sides; the SIDE edges its two long sides. The long side must exceed
  the short by more than `2 x [bridge] abutment_sample_step_m`; a squarer
  piece is not read (note).
- **Routes.** Mapped `highway` / `railway` ways are chained into routes
  through shared end nodes (`viaduct_road._route`, the heading-keeping walk).
- **Carried.** A highway route that crosses the ring through BOTH end edges.
  MEASURED: lower ← `-18866` + `-5740`; upper piece 0 ← `-2149` + `-2141` +
  `-3314`; upper piece 1 ← `-3638` (it ends 5 m inside the south-west end:
  a route that crosses one end edge and ends within `abutment_sample_step_m`
  of the other is carried too).
- **Under / over.** A route that crosses both SIDE edges runs under the piece
  or over it. It is `under` when it runs in the floor (the under-way) or is
  the carried route of a lower level; otherwise it is ignored here.
- **Unclassified.** A route through one end and one side: a note, nothing
  else.
- **Level.** Pieces are ordered by their plate's mean y. Two pieces whose
  mean y differ by less than `[bridge] clearance_minimum_m` (4.2) are one
  level (the upper deck's two carriageways). MEASURED: level 1 = lower
  (4.00-5.08), level 2 = both upper pieces (11.98).
- **The tag check.** The mapped `layer` of the carried routes must not
  contradict the levels (default 0; `bridge` with no layer 1; `tunnel` with
  no layer -1): a higher level's carried route never has a lower layer than
  a lower level's, and the under-way never a higher one than level 1's. A
  contradiction refuses the stack with a note; it is a finding for the
  master, not something to resolve in code.

### 3.5 A carried stretch is a mapped bridge (ONE site)

For every way of a carried route, the stretch between the piece's two end
edges is replaced in `Airport.osm_ways` by a piece with the same id and
kind, its tags plus `bridge=yes` and `o4_deck=<deck placement id>`
(`structure_underpass.UNDERPASS_TAG` is the precedent for a synthesized
tag). The rest of the way keeps its tags. A stretch already tagged `bridge`
only gains `o4_deck`. The `layer` tag is NOT invented: R6
(`viaduct_min_layer` 2) and the cover read (`cover_min_layer` 1) must not
see a new viaduct.

The ways as mapped are kept in `Airport.osm_ways_mapped`, and the derivation
always starts from them, so running it twice gives the same airport.

Every reader of `is_bridge_way` then reads the stretch as a bridge without
an edit. The ones that matter:

- `airport/road_ways.road_ways`, `classify/sources`: no road ribbon between
  the end lines. The ribbons end AT the end lines.
- `overpass_deck._road_under`: a carried stretch is never "the road
  beneath".
- `airport/bridge_ground`: the stretch joins its bridge runs (§5 row 8).

MEASURED: the lower road loses its 60 m across the trench; the upper road's
approaches lose 18.0 m and 20.8 m under the deck's overhang.

### 3.6 One zero

- **Top at an end line.** `top_e` is the PLATE's own height on the end edge:
  the mean, over stations every `abutment_sample_step_m` along it, of the
  plate triangle under each station (`geom/lowest_face.floor_z_at` on the
  plate's triangles). Never the maximum within a reach
  (`deck_bridge._top_at`): MEASURED on the arched lower deck `_top_at` gives
  4.83 and 4.48 where the plate stands at 4.00 at both ends.
- **Ground at an end line.** `G_e` is the median DEM at the end line's
  stations moved one `abutment_sample_step_m` outward, off the deck, onto the
  approach. The DEM under a deck is never read (Q344 a).
- **Zero.** `Z0 = mean over every end line of every deck of (G_e - top_e)`,
  each end line once (`deck_anchor.derive`'s rule, over the whole stack).
- **Sanity.** If `max - min` of `(G_e - top_e)` exceeds `[tunnel]
  clearance_m` (5.0), the members do not stand in one frame on this ground:
  no stack, with a note carrying the values.

MEASURED KDEN:

| end line | at (lat, lon) | G_e | top_e | G_e - top_e | residual to Z0 |
|---|---|---|---|---|---|
| lower, north-west | 39.842527, -104.674077 | 1631.08 | 4.00 | 1627.08 | +0.52 |
| lower, south-east | 39.842145, -104.673573 | 1629.03 | 4.00 | 1625.04 | -1.52 |
| upper piece 0, north-east | 39.842706, -104.673399 | 1639.38 | 11.98 | 1627.40 | +0.84 |
| upper piece 0, south-west | 39.842063, -104.674217 | 1637.74 | 11.98 | 1625.76 | -0.80 |
| upper piece 1, north-east | 39.842732, -104.673596 | 1639.50 | 11.98 | 1627.52 | +0.96 |
| upper piece 1, south-west | not read in the spec round | | 11.98 | | |

`Z0 = 1626.56` over the five (spread 2.48 m). The sixth end line is the
implementer's to read; the pre-registered zero is 1626.56 +/- 0.25.
The residual is how far the road's end moves to meet the deck (sign
reversed): the ground grades to the deck ends (11b), the deck never tilts
(30a).

### 3.7 What the terrain does (the lowest level only)

1. **The floor.** Inside the floor polygon the surface is `Z0 + feet_y(s)`,
   the walls' feet at each station (MEASURED flat, 1626.51). It runs through
   under every deck at the corridor's full width. This is the depth ladder's
   first rung: an object that states its own bottom (two-level spec §3).
   The lidar is not read there, so the plug goes.
2. **The run-outs.** Beyond each open end of the walls the floor goes on
   along the under-way at the corridor's end width, from `Z0 + feet_y` to the
   ground, by `geom/ramp_profile.runout_profile` at the under-way's law
   (rail: `rail_ramp_grade` 1.25 %, never over `rail_ramp_max_grade` 3.5 %;
   road: `ramp_grade`, `ramp_max_grade`), bounded by `max_ramp_length_m`. It
   stops at airside pavement and at a pad, with a note. MEASURED: the floor
   stands 5.3 m over the lidar at the south end (a run of 87-139 m) and 2.0 m
   at the north end (57-160 m).
3. **The walls.** The step between the floor and the ground beside it is the
   object floor's existing form: a void band (role `retaining_wall`) half a
   `wall_face_max_thickness_m` wide around the floor's ring, the mesh making
   the wall between the two rings.
4. **The walls' top.** A map vertex on the rim, where a wall face stands,
   lies in `[Z0 + crest_y - [cockpit] visual_m, Z0 + crest_y]`: never over
   the wall's top (the wall would be buried), at most 0.5 m under it.
   MEASURED band 1629.56..1630.06; the ground beside the trench under the
   decks is 1629.4-1632.1 today.
5. **A deck's end lines.** The carried road's ribbon ends at the end line.
   Its end vertices stand at `Z0 + top_e` within `[bridge] deck_flush_m`
   (0.04), hard (§3.8). The road grades to them by its own law.
6. **Under a deck.** No face is minted for a deck. A map vertex inside a
   deck piece's ring that is not on the floor takes a ceiling: `z <= Z0 +
   plate y there - deck_flush_m`. Where the patch has no face under a deck
   the tile mesh keeps the DEM. MEASURED: the plug outside the walls
   (1629.5-1630.3) is under the lower plate (1630.56-1631.64) and beside the
   caps' level (1630.06); it is the real abutment ground and stays.
7. **Nothing else.** No bank, no zone band, no pad, no ramp is added for a
   stack. A deck in a stack never cuts anything: the only cut is the floor.

### 3.8 What the solve and the object stage are given

- **The floor's pins.** The stack's floor is an `ObjectFloor`:
  `id = "stack:<walls id>"`, `object_id` = the walls, `covers` = the other
  members, `zero_z = Z0`, `floor_z = Z0 + feet_y`, `footprint` = floor ∪
  run-outs, `faces` = the floor's triangles at `Z0 + feet_y(s)` and the
  run-outs' at their profile, `kind = "floor"`, `decks = ()`,
  `seats = ((placement id, resource, Z0) for every member)`.
  `planar/object_floor_cells.add_object_floor_cells` cuts it into the map and
  `constraints/object_floor.object_floor_pins` pins it, unchanged.
- **The end lines, the rim, the ceilings.** One new generator,
  `constraints/deck_stack.deck_stack_rows(planar, law, airport)`, reading
  `airport.deck_stacks`:
  - per end line: every map vertex of a road-role face (`ROAD_ROLES`) within
    `2 x abutment_sample_step_m` of a station, on no structure face
    (`deck_lines.floor_end_lines`' selection): `Band(v, Z0 + top_e -
    deck_flush_m, Z0 + top_e + deck_flush_m)`;
  - per rim vertex (§3.7 (4)): `Band(v, Z0 + crest_y - visual_m, Z0 +
    crest_y)`;
  - per vertex inside a deck ring off the floor (§3.7 (6)): a one-sided
    `Band` (or the generator's own ceiling form) at `Z0 + plate y -
    deck_flush_m`.
  All under the existing head `edge_deck.RIGID` ("structures.hard-deck
  bridge: one zero, flush at both end lines", already in `[design]
  hard_rulings`): the stack's rows are the same ruling, so `law/emit.toml`
  is not edited. `Source("deck_stack", RIGID, (stack id, deck id, part))`.
  With no stack the generator returns `[]`.
- **The seats.** `airport/object_floor.seat_records` writes every member
  WHOLE as `OBJECT_MSL` at `Z0` (datum `object_floor`), each placement once.
  No plate, no end-line re-seat, no split.

### 3.9 Who owns what (nothing is claimed twice)

| thing | its one owner | how the others are kept off (existing mechanism) |
|---|---|---|
| a member placement's seat | the stack floor's seat record | `seat_records`: one record per placement, the first frame naming it |
| a member as a hard-deck bridge | nobody | `planar/build`: `deck_bridges([o for o in objects if o.id not in floor_frame])` |
| a member as a road overpass | nobody | `road_overpasses(cut_objects=... + sorted(floor_frame))` |
| a member as a basin / split-level / corridor | nobody | `object_floor_stage`: `tstats.shell_claimed |= floor ids`; corridors over floor ids dropped |
| a member's footprint as a pad | nobody | `Airport.stack_shade` through `geom/cluster_outline.pad_shade_extra` and the fallback mint in `classify/evidence` |
| the ground in the floor and run-outs | the object floor's cut face | senior to every structure cell; the knife (never the runway family) |
| the ground between a deck's end lines on the carried road | nobody (the deck is an object) | the stretch is a mapped bridge: no ribbon |
| the ground under a deck elsewhere | whatever owned it before | a ceiling only |
| the under-way's mapped tunnel | nobody | a bore inside an object floor's footprint is trimmed to its rim; MEASURED the rail bore is refused already |

## 4. Can a heightfield mesh carry it? (checked before ratification)

The patch is one height per point. The stack asks for nothing else:

- The mesh holds the lowest level only. Level 0 is terrain; every higher
  level is an object.
- Under a deck the mesh is single-valued: the floor between the walls, the
  ground beside them. The carried road has no mesh between its end lines, so
  no point needs two heights.
- A wall is two rings a void band apart, as every object floor's wall is
  (LGAV, EGLL) and every declared wall terrace (KATL, KBNA). MEASURED: a
  3.55 m step over 1.0 m of plan.
- A deck's end is a ring of road vertices at the deck's top. Just inside the
  ring the ground falls to the level below. Where the pack models an
  abutment (KDEN's lower deck: its lowest solid 2.48 over the caps at 3.50)
  the object hides the fall; where it does not, the mesh makes a bank under
  the deck. Either is one height per point.
- Two decks crossing in an X need nothing at the crossing: neither is in the
  mesh.
- A run-out is a ramp of pinned faces. It can stand ABOVE the lidar (a fill)
  as well as below it; pins do both.

What a heightfield cannot do, and the model does not ask: ground on a deck
(a road ribbon on the lower deck), or ground under an overhanging wall.

One limit to state: where two stack decks' end lines stand closer than a
ribbon's width at different heights, two road ends meet in plan. At KDEN the
nearest two end lines of different levels are 47 m apart (the lower deck's
north-west end and the upper deck's second piece's north-east end). The
generator refuses a
vertex claimed by two end lines at heights more than `deck_flush_m` apart
and says so.

## 5. Consumer census (RULINGS 2026-08-30l): every pass that reads deck, claim or tunnel geometry

Ruled BEFORE any consumer is edited. Interaction values:

- **DERIVES**: new, or feeds the stack record.
- **EDIT**: must read the record; the edit is named.
- **FREE**: reads a record the stack writes in an existing form (a bridge
  tag, an `ObjectFloor`, `floor_frame`, a seat record, a pad shade). No edit.
- **UNCHANGED**: does not see a stack; why.
- **VERIFY**: no edit; a number to read in the replay and report.

| # | pass (module) | reads today | interaction | ruled |
|---|---|---|---|---|
| 1 | `airport/deck_stack` (NEW) | — | DERIVES: the one derivation site (`attach_deck_stacks`), at the pack stage | §3, §6 |
| 2 | `airport/stack_walls` (NEW) | — | DERIVES: floor-datum walls, crest, feet, wall faces, the floor cast | §3.2, §3.3 |
| 3 | `airport/deck_carry` (NEW) | — | DERIVES: carried / under routes, end lines, plate tops, the way rewrite | §3.4-§3.6 |
| 4 | `model/deck_stack` (NEW), `model/airport.Airport` | — | EDIT `model/airport.py`: three fields with defaults (§3.1) | §3.1 |
| 5 | `airport/deck_signature` (`is_bridge_way`, `is_tunnel_way`, `bridge_lines`, the deck kinds) | tags; plates | FREE. It runs inside the pack read, BEFORE the rewrite, so the deck kinds are as today | §3.5 |
| 6 | `airport/tunnel_objects.read_corridors`, `tunnel_walls`, `trench_objects`, `hanging_objects`, `portal_objects`, `portal_floor`, `object_cut`, `sunken_roads`, `door_wells`, `wall_corridors` / `wall_family` / `wall_mouth` / `wall_geometry`, `thin_plates`, `walled_pit`, `pit_frame` | walls and floors measured DOWN from the zero | UNCHANGED: none admits a floor-datum wall (MEASURED: the §1.4 refusals stay). A placement one of them claims is in the stack's `taken` set and is never a member | §3.3 |
| 7 | `airport/object_floor` (`read_object_floors`, `seat_records`, `owns_ground`, `floor_portals`), `geom/lowest_face` | floor objects, shells | FREE: the stack floor is one more `ObjectFloor` (built by `airport/deck_stack`, not by `read_object_floors`) | §3.8 |
| 8 | `airport/bridge_ground` (#1935: `bridge_runs`, `bridge_sampler`, the `dem_z` substitution in `planar/build`) | mapped highway bridges | FREE + VERIFY: a carried stretch joins its runs. It lowers the TARGET of non-airside vertices only; every stack vertex is pinned or banded. Report its run and vertex counts before and after (today: 5 runs, 4 vertices, max 7.40 m) | §3.5 |
| 9 | `airport/road_ways.road_ways` / `road_lines`, `classify/sources` (road sources, `_rail_lines`), `classify/pad_cut_corridor` | at-grade ways | FREE: no ribbon on a carried stretch | §3.5 |
| 10 | `airport/road_profile` (`core_profiles`, `preferred_road_z`), `constraints/roads`, `road_ramp`, `foot_road` | the road's own profile and caps | VERIFY (probe P2, §8.2): the ribbon's end is banded at `Z0 + top_e`; the road must grade to it without a relaxed row | §3.7 (5) |
| 11 | `geom/cluster_outline.pad_shade_extra`; `classify/evidence` (the fallback mint, `entrance_shade` gate) | `sunken_ramps`, `wall_shade`, `entrance_shade` | EDIT, one line each: `Airport.stack_shade` joins the union and the fallback gate | §3.9 |
| 12 | the partition, groups, connectors, `planar/cluster.clusters` / `deck_shades` | units | UNCHANGED: members stay their own units; their pads leave through the shade | §3.9 |
| 13 | `airport/below_grade_witness`, `geom/author_ground` | the pack's plates | UNCHANGED: the stack's own depth witness is §3.2 (3). W's caps stay author's ground for its neighbours | §3.2 |
| 14 | `airport/wall_shade`, `wall_sides`, `wall_class`, `retaining_walls`, `entrance_shade`, `sunken_ramp`, `flat_pack`, `walled_plate`, `terrain_shaped`, `terrain_mesh_witness`, `pack_ground` | — | UNCHANGED (MEASURED KDEN: `wall_shade` none, `retaining_walls` 0, `entrance_shade` none) | — |
| 15 | `planar/object_floor_cells.object_floor_stage` | the floors, read once | EDIT: append the stacks' floors after `read_portal_floors` (`floors += stack_floors(airport.deck_stacks, taken=...)`), so `planar/build` and the `--stage structures` replay share it | §3.8 |
| 16 | `planar/object_floor_cells.add_object_floor_cells`, `floor_mouths`, `not_floors`; `planar/structures.build_structures` (owners, knife, keep-outs) | object floors | FREE: the cut face, the void band, the seniority and the keep-outs | §3.7 |
| 17 | `planar/deck_bridge.deck_bridges`; `planar/overpass_deck.road_overpasses` | hard decks | FREE: members are in `floor_frame`, which `planar/build` already filters out of `deck_bridges` and passes as `cut_objects`. VERIFY: the two member overpass notes become "its frame holds a pack object cut"; `Train_Bridge_1.obj`'s overpass is unchanged | §3.9 |
| 18 | `planar/floor_decks` | shells' pavement decks | UNCHANGED: it reads `kind == SHELL` only; the stack floor is `kind == "floor"` with `decks = ()` | §3.8 |
| 19 | `planar/structure_approach`, `structure_service` (the terrain-tunnel witness, the pack-passage rule), `structure_fence`, `end_witness`, `structure_mouth`, `structure_overlap`, `structure_pair`, `structure_road`, `structure_underpass`, `structure_deck`, `structure_geometry`, `unframed_ramp`, `bore_continuation`, `lidar_road` | mapped bores | UNCHANGED. VERIFY: `tunnel:-4171+-4166` stays refused (or is trimmed to the floor's rim) and mints no ramp; no `bridge_deck:` face is minted at the site | §3.9 |
| 20 | `planar/viaduct_road` (R6), `planar/reach_under_covers` | bridges at `layer >= 2` / `>= 1` | UNCHANGED: the rewrite invents no `layer` (§3.5). VERIFY: no new R6 group, no new beyond piece | §3.5 |
| 21 | `planar/bridge_span`, `covered_ground`, `covered_cut`, `covered_bores`, `cut_frame`, `cut_runout`, `deck_bores`, `deck_walls`, `deck_route`, `channel*`, `basins*`, `split_level_pit`, `station_level` | their own witnesses | UNCHANGED: members are claimed (`shell_claimed`), no `Tunnel` of source `object` exists for them. VERIFY: the `split_levels` refusal of `Mix_Master_Upper.obj` and the basin refusals go (claimed) or stay; none mints anything | §3.9 |
| 22 | `planar/level_regions`, `level_depth`, `level_underside`, `low_level`, `low_extent`, `low_fill`, `landing*`, `fill_*`, `pad_*`, `platform`, `zones`, `terrain_edge`, `road_yield`, `road_shadow`, `strip_keepout`, `reach_after_pads`, `overlay`, `shapes` | lower levels, bands, pads | FREE through the object floor's keep-outs. MEASURED: `level_seeds` reads no seed from W (feet at its zero) | — |
| 23 | `constraints/object_floor.object_floor_pins` | object floors | FREE | §3.8 |
| 24 | `constraints/deck_stack` (NEW), `constraints/__init__.GENERATORS` | — | DERIVES rows; EDIT: one registry line after `("object_floor", ...)` | §3.8 |
| 25 | `constraints/edge_deck` (`_deck_rows`, `_floor_deck_rows`, `_span_rows`), `deck_lines`, `deck_anchor` | `PlanarMap.decks`, `ObjectFloor.decks` | UNCHANGED: a stack mints no `DeckBridge` and no `FloorDeck`. `_span_rows` must NOT be used for a stack deck: it pairs the ground under a ring to the deck's seats, which would lift the ground under an elevated deck by its clearance | §3.7 (6) |
| 26 | `constraints/structures`, `edge_floor`, `channel`, `ramp_runout`, `wall_zone`, `riser`, `platform`, `group_level`, `no_step`, `ceiling`, `pads`, `terrain_shaped`, `walled_plate`; `solve/wall_cut`, `design_ground`, `feasibility` | — | UNCHANGED / FREE (the void band's role) | — |
| 27 | `pipeline/build.pack_stage`; `tools/v2_solve_replay.py` (the capture, and the replay's `resume in ("classify", "planar")` block) | the `attach_*` steps | EDIT: call `attach_deck_stacks` after `attach_entrance_shade`, at all three sites. The replay re-derives every time (from `osm_ways_mapped`), so `--from classify` iterates without a new capture | §6 |
| 28 | `pipeline/publication.object_floors` | per floor: id, objects, floor, zero, area | EDIT: a stack floor's record gains `"stack"` (zero, spread, levels, per deck: object, piece, level, carried ways, each end line's stations as lat/lon and its top; the walls' crest and feet). The sidecar key exists; the register is not touched | §8.4 |
| 29 | `pipeline/publication` (the other records), `emit/osm_adapter`, `emit/terrain_edge` | — | UNCHANGED | — |
| 30 | `pipeline/rebake_inputs` (`_edge_seat_plates`, the authored and floor seats), `pipeline/authored_seats` | plates, seat records | FREE: no overpass plate for a member; `_of.seat_records` writes the members | §3.8 |
| 31 | `airport/rebake_plan`, `placement_plan`, `anchor_rule`, `airside_deck_seat`, `cut_deck_seat`, `bridge_approach`, `placement_family`, `bridge_family`, `placement_deck`, `open_frame_seat`, `deck_family_contact`; `auto_patch/object_stage`, `post_mesh`, `object_rebake`, `object_anchor` | the seats | VERIFY (probe P3, §8.2): a FLAG deck with an object-floor seat record must be written at the record's elevation, not re-seated by class A, `refused_bridge` or `approach_seat`. If it is re-seated, the fix is at the one site that honours `authored_seat.kept_ids`, and it is reported as a deviation | §3.8 |
| 32 | `verify/structures`, `keepout`, `steps`, `no_step`, `channel`, `cutback`; `tools/check_grade.py` and its families (`DeclaredWallSteps`, the `tunnel_trench` role, `deck_end_flush`) | the object floor's forms; `deck_anchors` | UNCHANGED. No new census family in this round: the end lines are judged on the drawn mesh (§8.4). A census family for stack end lines is a follow-up (§12) | — |
| 33 | `tools/drawn_check.py` (the OBJECTS layer of `tools/harness/drawn_gate.py`, on batch 15) | the sidecar's claims; every `object_floors` object is a CUT site | EDIT `drawn_check.py` only: a record with `"stack"` gives its deck members the DECK bar, and a STACK section measures one zero, the floor, the end lines and the ceilings on the drawn mesh (§8.4). `drawn_gate.py` is not edited: it carries the rows as object sites. The `tools/INDEX.md` row is updated in the same commit | §8.4 |
| 34 | `tools/deck_probe.py`, `osm_site.py --deck-witness`, `drawn_site.py`, `site_read.py` | `PlanarMap.decks`, patches | UNCHANGED | — |
| 35 | `pipeline/stage_code.CODE_MODULES`, `pipeline/front_cache`, `capture_state`, `auto_patch/provenance_code` | the stage keys, the code closure | EDIT `stage_code.py`: key the new modules in the stage lists (`tests/auto_patch_v2/test_stage_code_closure.py` names what is missing). VERIFY `tests/test_v2_replay_stage_cache.py` | §6 |
| 36 | the engine core (`O4_Vector_Map` road levelling, `include_patches`, the mesh) | the raw road feed, the patch | UNCHANGED. VERIFY on the drawn mesh (§8.4): the core still sees the lower road at grade in the raw feed; inside the patch's faces the patch governs | §8.4 |

What the census settles:

- The stack is derived once, at the pack stage, and published in forms the
  passes already read. Nine files are edited (rows 4, 11 x2, 15, 24, 27 x2,
  28, 33, 35); everything else is new modules.
- No consumer needs a veto. Three interactions need a probe before the
  closing build: P1 (the floor cast on the real walls), P2 (the road ends
  against the bands), P3 (the seat precedence of a flag deck).

## 6. Implementation plan (for the Opus lane)

Run `tools/blast.py <file>` before each edit and `tools/blast.py --find
<keyword>` before adding a function. A new family member is a new file.

### 6.1 New modules

| file | one responsibility | public symbols |
|---|---|---|
| `model/deck_stack.py` | the records (§3.1) | `DeckStack`, `StackDeck` |
| `airport/stack_walls.py` | floor-datum walls: §3.2 (1)-(5) and the floor cast of §3.3 | `StackWalls` (feet_y, crest_y, faces, crest plates), `read_stack_walls(o, cache, law) -> StackWalls | str`, `floor_between(walls, route, law) -> Polygon | str` |
| `airport/deck_carry.py` | per deck piece: axis, routes, carried / under, end lines, plate tops; the way rewrite | `carry_of(piece, plate, routes, law) -> Carry | str`, `plate_top(plate, stations) -> float`, `bridge_stretches(ways, carries) -> tuple[OsmWay, ...]`, `DECK_TAG = "o4_deck"` |
| `airport/deck_stack.py` | THE derivation: candidates, members, levels, zero, run-outs, the `ObjectFloor`, the shade, the attach | `deck_stacks(airport, objects, cache, law, taken=()) -> tuple[tuple[DeckStack, ...], list[str]]`, `stack_floors(stacks, taken) -> list[ObjectFloor]`, `attach_deck_stacks(airport, objects, cache, law) -> Airport`, `log_line(icao, stacks)` |
| `constraints/deck_stack.py` | the rows (§3.8) | `GEN = "deck_stack"`, `deck_stack_rows(planar, law, airport) -> list[Row]` |
| `tests/auto_patch_v2/test_deck_stack1971.py` | the twins (§7) | — |

Reuse, by import, with no edit to the source: `planar/deck_bridge._frames`,
`_plate`, `CellRoles`; `planar/viaduct_road._route` (if importing a planar
module from `airport/` breaks `tools/ratchets.py layers`, move the three
readers' CALLS into a thin `planar/` caller and keep the geometry in
`airport/`; do not copy them); `airport/object_floor.ObjectFloor`;
`geom/lowest_face.floor_z_at`; `geom/ramp_profile.runout_profile`;
`airport/obj8._to_frame`; `constraints/edge_deck.RIGID`;
`constraints/deck_lines.floor_end_lines`' vertex selection (copy the 6-line
selection only if it cannot be called; the duplicate ratchet counts it).

### 6.2 Shared files touched (every one; the EGLL lane is in trench / deck code)

| file | edit | size |
|---|---|---|
| `model/airport.py` | three fields with defaults (§3.1) | ~12 lines |
| `pipeline/build.py` | `attach_deck_stacks` after `attach_entrance_shade`, one `_say` line | ~4 |
| `tools/v2_solve_replay.py` | the same call in the capture and in the replay block | ~6 |
| `geom/cluster_outline.py` | `pad_shade_extra`: add `stack_shade` | 1-2 |
| `classify/evidence.py` | the fallback gate: `entrance_shade` ∪ `stack_shade` | 1-2 |
| `planar/object_floor_cells.py` | `object_floor_stage`: append the stack floors, their notes | ~6 |
| `constraints/__init__.py` | import and one `GENERATORS` line | 2 |
| `pipeline/publication.py` | `object_floors`: the `"stack"` sub-record | ~15 |
| `pipeline/stage_code.py` | key the new modules | as the twin says |
| `tools/drawn_check.py`, `tools/INDEX.md` | the STACK section; its index row | ~80 |

NOT touched: `planar/deck_bridge.py`, `planar/overpass_deck.py`,
`planar/structures.py`, `planar/build.py`, `constraints/edge_deck.py`,
`airport/tunnel_objects.py`, `airport/object_floor.py`, `law/*.toml`,
`emit/*`, the object stage. If the round finds it must touch one of these,
that is a deviation from this spec: stop and report it.

### 6.3 Order of work (each slice has its own bar)

1. **S1, the readers** (`stack_walls`, `deck_carry`, records; twins T1-T8).
   Bar: the twins; probe P1.
2. **S2, the derivation and the attach** (`deck_stack`, the pack-stage and
   replay calls, the shade, the way rewrite; twins T9-T12). Bar: dry replay
   `--from classify --pad-read` on the KDEN capture gives §8.1's readings,
   and on the regression captures gives `0 stacks` and an identical map
   (§9).
3. **S3, the floor and the rows** (`stack_floors`, `object_floor_stage`,
   `constraints/deck_stack`; twins T13-T15). Bar: full KDEN replay, §8.2;
   probes P2, P3.
4. **S4, publication and the drawn check** (twin T16).
5. **S5, ONE closing build**, closed by the drawn gate (§8.3, §8.4).

### 6.4 Gates before reporting

- The twins of §7 and the test files covering the edited shared files:
  `tests/auto_patch_v2/test_object_floor1903.py`, `test_overpass_deck1692.py`,
  `test_deck_bridge1671.py`, `test_deck_anchor.py`, `test_bridge_ground1935.py`,
  `test_below_grade_witness1966.py`, `tests/test_drawn_check.py`,
  `tests/test_drawn_gate.py`, `tests/test_v2_replay_stage_cache.py`.
- The registry gates (tree-walking twins `blast.py` never lists):
  `tests/auto_patch_v2/test_stage_code_closure.py`,
  `tests/test_patch_code_closure.py`, `tests/test_step_code_closure.py`,
  `tests/test_v1_retired.py`, `tests/test_no_airport_specific_code.py`,
  `tests/test_windows_text_io.py`, `tests/test_patch_env_classification.py`,
  `tests/test_console_encoding.py`, `tests/test_tile_failures.py`.
- `tools/ratchets.py` (duplicates, near-duplicates, unused, layers); report
  its size warnings for the files touched.
- No full suite (owner 2026-11-11, short test-app cycle).

### 6.5 Build-time impact statement

The new work runs once per airport at the pack stage. It first screens the
objects for a floor-datum wall (§3.2 (1)-(4), on geometry the pack read
already parsed); with none it returns at once. With one it reads a few
decks' plates and casts one floor. Expected under 0.2 s at KDEN (3,965
bodies) and under 0.05 s where no wall is found. The lane prints the
step's seconds in its `[deck-stack]` line and reports them. At 0.6 s or more
(1 % of the 60 s airport budget) the build-time law applies: stop and
report.

## 7. Twins (synthetic fixtures; `tests/auto_patch_v2/test_deck_stack1971.py`)

Build the objects as `tests/auto_patch_v2/test_overpass_deck1692.py` does
(`_box`, an OBJ written to `tmp_path`, `types.SimpleNamespace` placements,
`Frame("ZZZZ", ...)`), with a synthetic DEM function. The base fixture, the
**3-level X**:

- walls W: two 1 m thick walls 200 m long, 12 m apart, y 0..3.5, a 5 m cap
  strip at y 3.5 outside each, two piers to y 12, no floor face;
- lower deck L: a hard-deck plate 60 x 24 m, y 4.0 at its ends and 5.0 at
  the crown, crossing the corridor at 50 degrees;
- upper deck U: a flat hard-deck plate 100 x 21 m at y 12.0, crossing L at
  about 85 degrees;
- anchors: all three on the floor, AGL 0, different headings;
- ways: a rail `tunnel=yes layer=-1` along the corridor under the decks and
  at-grade rails beyond; an at-grade `highway=primary` along L; a
  `bridge=yes layer=1` way along U that stops 18 m short of each end of U's
  ring, continued by at-grade ways;
- DEM: trench floor 95.0 outside the decks, a plug at 104.0 under them,
  ground 104.0 beside, the road ends at chosen heights.

| twin | asserts |
|---|---|
| T1 | 3-level X: one stack; members W, L, U; levels 1 and 2; `carried` / `under` as built; `feet_y`, `crest_y` 3.5 (the piers' 12.0 is not the crest) |
| T2 | 2-level: W and L only → one stack, one level |
| T3 | two decks crossing in an X on flat ground, no walls → no stack; `road_overpasses` returns the same records with and without the attach |
| T4 | nothing below grade never mints a cut (#1961, #1966, #1950), one case each → no stack: (a) walls 1.0 m high (under `floor_sunken_min_m`); (b) walls and a deck but no route in the corridor; (c) walls with a floor plate at their feet; (d) a deck beside the walls, not spanning them; (e) walls standing on zero with a roof over the whole corridor and no hard deck (a garage) |
| T5 | a spanning deck whose anchor is 30 m off the floor is not a member: no stack, and the note names it |
| T6 | the arched deck's end top is the plate on the end edge (4.0), not the crown and not the maximum within a reach |
| T7 | a route through both side edges is under; through one end and one side is unclassified (note) and makes no end line |
| T8 | the mapped layers contradicting the levels refuse the stack (note) |
| T9 | the zero is the mean of `(G_e - top_e)` to 1e-6; a spread over `clearance_m` refuses the stack |
| T10 | the rewrite: the at-grade way under L becomes three pieces with one id, the middle one `bridge=yes` + `o4_deck`, no `layer` added; U's approach stubs inside its ring too; `road_ways` yields no line between L's end lines |
| T11 | the attach is idempotent (twice = once) and leaves an airport with no stack byte-equal in its ways |
| T12 | `stack_shade` covers W's caps; `pad_shade_extra` returns it; the members are in the floor's `covers` |
| T13 | the `ObjectFloor`: footprint between the walls (not the hull), z = zero + feet through the plug, seats = every member at the zero, `decks == ()`, `kind == "floor"`; a run-out reaches the ground at the rail law; a run-out that meets airside stops with a note |
| T14 | `deck_stack_rows` on a small map: the end-line bands at `zero + top` within `deck_flush_m` on road vertices; the rim band; the ceiling under a ring; a vertex two end lines claim at different heights is refused |
| T15 | with no stack, `deck_stack_rows` is `[]` and the constraint set of a control map hashes equal |
| T16 | `publication.object_floors` carries `"stack"`; `tools/drawn_check` (in `tests/test_drawn_check.py`, its synthetic DSFTool text) gives a stack's deck the DECK bar, fails a deck given the CUT bar's reading, and passes / fails D1, D3 and D4; `tests/test_drawn_gate.py` still passes |

## 8. KDEN measurement plan (synthetic first, then one build, closed by the drawn gate)

Capture: `/Users/noah/XPTerrainBuilderData/.harness/frames/l1971/KDEN.pkl`
(base 79a3a386d; `tools/harness/frames.py list KDEN`). The DEM and the
airports OSM layer of N39W105 were refreshed for it through the harness on
2026-11-12 (`--refresh-data dem,osm_layers`, ledgered).

### 8.1 Dry replay (S2): `tools/v2_solve_replay.py --replay KDEN.pkl --from classify --pad-read`

Pre-registered readings (materiality 0.01 m unless stated):

| reading | expected |
|---|---|
| stacks | 1: `stack:dsf:obj31298` |
| members | `dsf:obj31298`, `dsf:obj31299`, `dsf:obj31311`, `dsf:obj31312` |
| walls | feet y -0.05, crest y 3.50 |
| levels | 1: `Mix_Master_Lower.obj` (plate 4.00 at both ends); 2: `Mix_Master_Upper.obj`, two pieces (11.98) |
| carried | lower: `-18866`, `-5740`; upper piece 0: `-2149`, `-2141`, `-3314`; upper piece 1: `-3638` |
| under | `-4171`, `-4166` (and the at-grade rails in the floor) |
| zero | 1626.56 +/- 0.25 (five end lines read in §3.6; the sixth is new) |
| floor | 1626.51 +/- 0.25; 11.7-12.6 m wide under the decks; area under the hull's 7,514 m2 |
| pads | `building19` and `building21` are gone |
| overpasses | none for `dsf:obj31311` / `dsf:obj31312`; `Train_Bridge_1.obj`'s unchanged |
| road faces | no `big_roads:-18866` / `-5740` face between the lower deck's end lines (today the site lies in face `big_roads:-18866`, 2,071 m2) |
| elsewhere | every deck, overpass, structure and object floor NOT at the site is as in the control replay |

### 8.2 Full replay (S3): `--from classify --verify --emit DIR --solved-out PKL`, against a control replay of the same capture on the base

Site numbers first, by landmark:

| where | today (base) | bar |
|---|---|---|
| the rail under both decks (39.842347, -104.673859) | DEM 1630.09, a road face | solved = zero + feet (about 1626.51) within 0.05 |
| the open trench 70 m north (39.84300, -104.67387) and 55 m south (39.84185, -104.67387) of the site | 1623.68 / 1621.08 (no face) | on the floor or its run-out: within 0.05 of the stack's own profile; no step over 0.5 m along the rail |
| lower deck's ends (39.842527, -104.674077 and 39.842145, -104.673573) | road at 1630.93 / 1629.18 | road end = zero + 4.00 (about 1630.56) within 0.04 |
| upper deck's ends (39.842706, -104.673399; 39.842063, -104.674217; 39.842732, -104.673596; and the sixth) | 1639.30 / 1637.83 / 1639.43 | road end = zero + 11.98 (about 1638.54) within 0.04 |
| the walls' top, both sides, under the decks | — | in [zero + 3.00, zero + 3.50] |
| under each deck's ring | — | every map vertex at or under zero + plate y |

Then:

- **P2** (`--why-at` at each end line): no relaxed `RIGID` row, no relaxed
  road row, in `--why-hard`. If a road cannot reach its band, report the
  rows; do not loosen the band.
- **P3** (the emitted rebake plan, `tools/v2_rebake_replay.py`): the four
  members carry the object-floor seat at the zero; none is split, plated or
  re-seated.
- Census (`tools/harness/census.py` on the emitted patch, both arms):
  adjudicated airside rows not above the control; every new groundside row
  within 150 m of the site listed with its family.
- `airside_value_delta` / `--z-out`: no airside vertex moves more than
  0.01 m (the stack is groundside, 2.4 km south of the terminal).

### 8.3 ONE closing build, closed by the drawn gate

The implementing lane's base is the batch-15 tip or later (it must hold
`0a1a225c0`, the merge of #1903's drawn gate). `df -h /` must show 30 GB
free. From the lane's `Ortho4XP/`:

    venv/bin/python tools/harness/build_airport.py KDEN --tile 39 -105 \
        --pack-copy <scratch dir> --tag l1971impl_KDEN

`--pack-copy` is required. Without it the gate's OBJECTS layer reads the
owner's old pack, says NOT MEASURED, and the verdict is INCOMPLETE, which is
not a pass. The tile build runs the gate itself and writes
`<out>/l1971impl_KDEN.drawn.json`. Delete the tile dir and the pack copy
after the read.

### 8.4 The closing bar, in the drawn gate's terms

Judge the round where it worked:

    venv/bin/python tools/harness/drawn_gate.py KDEN --tag l1971impl_KDEN \
        --site stack=39.842347,-104.673859,150 \
        --site trench_n=39.84370,-104.67400,150 \
        --site trench_s=39.84090,-104.67390,200 \
        [--against BASE.json] --json <scratch>/l1971impl_KDEN.sites.json

The three sites cover the decks, the walls' north half with its run-out, and
the south end with its run-out (the walls run 231 m north and 79 m south of
the anchors; the run-outs up to 160 m beyond).

`BASE.json` is the control. Do NOT build one. Use, in this order: the
gate's JSON of a base build in the artifact ledger, if one exists for the
lane's base; else the owner's installed tile read in place
(`drawn_gate.py KDEN --tile +39-105 --json BASE.json`, read-only), if its
mesh layer is measured (on 2026-11-12 that tile folder held no `Earth nav
data`, so it may not be); else no `--against`, and the sites are judged on
their own bars. Say which was used.

**The bar is the gate's verdict PASS at the three sites.** Layer by layer:

| layer | what the gate reads | PASS at the sites means |
|---|---|---|
| 1. MESH | which base mesh X-Plane draws on the tile; the DSF not older than the patch | our own tile DSF is the drawn one |
| 2. PATCH → DRAWN | every `alt_abs` node of the patch on the drawn mesh, 0.15 m of horizontal slack; a pavement-role node within 0.05 m, any other within 0.5 m | no node over its bar inside the sites. For the stack that is: every node of the floor face and its run-outs (role `tunnel_trench`), of the void band's two rings, and of the road ends at the five (six) end lines. This is what proves the trench is cut through under the decks in the mesh the sim draws, the plug gone |
| 3. OBJECTS | `tools/drawn_check.py`'s claims, each written row placed as X-Plane places it on the drawn mesh | MEASURED (not vacuous), and every stack row passes: see below |

Layer 3 for a stack. The stack's floor is an `object_floors` claim, so
today every object of the record gets the CUT bar (`|drawn bottom - cut
floor| <= 0.3 m`). That is right for the walls and wrong for the decks, so
this round extends `drawn_check` (census row 33): a record carrying
`"stack"` is read as follows.

| row | measure on the drawn products | bar |
|---|---|---|
| the walls (CUT) | the walls' drawn bottom against the cut floor (the lowest node of the floor's `tunnel_trench` way) and against the drawn mesh under it | within 0.3 m (the tool's `--tol`) |
| each deck member (DECK) | its drawn bottom against the cut floor | bottom at or over the floor less 0.3 m: the `deck_anchors` rule, never the CUT bar |
| D1, one zero | the members' written elevations | equal within 0.01 m |
| D2, the floor under the decks | the drawn mesh on the floor's centreline every 10 m against the walls' drawn bottom, the stretch under both decks named apart | within 0.3 m |
| D3, the end lines | per end line: the drawn plate top (written elevation + `top`) against the drawn mesh one sample step outside it, on the road | within 0.3 m |
| D4, nothing through a deck | under each deck's ring on a 2 m grid: drawn plate top less drawn mesh | never under 0 |
| D5, the walls' top | the drawn mesh 1 m outside each wall against the wall's drawn top | within 0.5 m, never above it |
| D6, no pad | the drawn mesh under the west cap strip (39.84300, -104.67410) | within 0.5 m of the wall's drawn top, not a flat pad at the floor's level |

With `--against`: no site in the three is new or worse than the control by
more than the gate's 0.05 m, EXCEPT the nodes the stack itself adds or
moves (the floor, the rings, the road ends); list those apart with their
own deltas.

Patch → drawn sites the gate reports elsewhere at KDEN are counted as
`elsewhere` and are not this round's (every airport read so far has some).

Report, site numbers first: the gate's verdict and each layer's; D1-D6 with
every number; the control used; then §8.2's replay numbers. A bar missed
twice is a STOP (§11). A PASS on the replay with a FAIL or INCOMPLETE on
the gate is a FAIL of the round.

## 9. Regression read (one existing bridge airport must be unchanged or better)

Dry A/B on registered captures, `--from classify --pad-read`, base against
the branch. Use the newest capture the replay accepts for each
(`tools/harness/frames.py list ICAO`):

- KBNA (`kbnafix/KBNA.pkl`): the taxiway-L hard-deck bridge and the crossing
  road overpass;
- LGAV (`hiddenshell/LGAV.pkl`) and EGLL (`rc1903-floor/EGLL.pkl`): the
  object floors and the decks over the pack's cuts, the nearest neighbours
  of the stack floor;
- OTHH (`m12/OTHH.pkl`; if the replay refuses its age, say so and skip it:
  do not take a new capture for a dry read);
- KMCI (`lkmci/KMCI.pkl`): decks and a garage on flat ground.

Bar for each: `0 stacks`; `Airport.osm_ways` equal to the control's
(hash); the same decks, overpasses, structures, object floors and pads.

Then ONE full replay on KBNA (`--from classify --verify`, both arms): the
same verify rows and no vertex moved more than 0.01 m.

If a regression capture DOES read a stack, that is a finding, not a failure:
stop, report the stack's readings (§8.1's table for it) to the master, and
do not build until the master answers.

## 10. Owner questions (none blocks the round; each has the spec's default)

- **O1, the floor under a compressed model.** The pack's rail floor is
  4.0 m under the lower deck's ends; the real one is about 7.5 m. With the
  decks at the real road level the floor stands at 1626.5 m: 2.0 m (north)
  to 5.4 m (south) above the lidar's floor, with run-outs of 60-160 m along
  the rail. (a) DEFAULT: as specified, the floor at the walls' feet (the
  depth ladder: objects first; #1903: the object's bottom meets the cut).
  (b) Sink the whole stack to the lidar's floor: the five road ends then
  drop 2.9-5.5 m into a bowl. (c) Keep the lidar's floor and let the walls'
  feet stand 2-5.4 m over it on a mesh face. The spec builds (a).
- **O2, the issue's two interview points.** "What is visible at each level":
  the rail floor and its walls; the lower road on its deck; the upper road
  on its deck; the natural ground beside the trench under the decks. "Cut
  all the way through": the floor runs under both decks at the walls' feet,
  at the corridor's full width, with the walls on both sides and no plug.
- **O3, a member with no hard deck.** `Over_Train_Bridge.obj` is seated at
  the stack's zero, but nothing grades the ground to its ends. Its top then
  stands at about 1630.6-1631.6 m against banks of 1631-1639 m, so its east
  end may be buried. The closing build measures it. A rule for it (a plain
  deck over a stack's floor) is a follow-up.
- **O4, road over road with no level-0 object.** Two pack decks crossing
  with no walls under them are not a stack here (twin T3): each keeps
  today's reading. No case is in hand.

## 11. Convergence guards (mandatory)

- Materiality: 0.01 m for an elevation, unless a bar states its own
  (0.04 m end lines, 0.3 m and 0.5 m on the drawn mesh). A residual under
  its floor is PASS-with-residual.
- Attempt cap: at most 2 fix iterations per pre-registered target. A second
  miss is a STOP and a report, not a third attempt.
- STOP and report, do not improvise, when: a file of §6.2's NOT-touched list
  must change; the floor cast cannot be built from the real walls (P1); the
  zero differs from 1626.56 by more than 0.25 m; a regression capture reads
  a stack; a seat is not honoured (P3); the pack-stage step costs 0.6 s or
  more.
- Heartbeat: `.progress` stamps (START / slice / EXIT) in the lane's scratch
  dir.
- A deviation from this spec is reviewed by the spec's author before it
  lands (Ortho4XP/CLAUDE.md, item 1a).

## 12. Not done in this round, and findings for the master

- **No engine code, no build.** The readings of §1 and §3 were made with
  scratch probes on the capture; the floor polygon was built from the walls'
  convex hull (an upper bound), not by the cast of §3.3.
- **F1, a general defect in the overpass reading (not fixed here).**
  `overpass_deck._road_under` takes a deck's own approach as "the road
  beneath" whenever the deck's plate overhangs its mapped bridge's ends, at
  any airport (KDEN's upper deck: 18.0 m and 20.8 m of its approaches). The
  stack fixes it for its members only, through the rewrite. A fix for every
  overpass (the end-edge test of §3.4) changes seats at other airports and
  needs its own dry A/B; it should be its own issue.
- **F2, the lidar's plug under a mapped rail.** 28k (226 a) refuses a rail
  bore where "the survey carries the road" at its ends. At KDEN the survey
  carries a bridge deck between them (a 8.6 m dam across the trench). The
  stack removes it here; a rail under a mapped bridge with no pack walls is
  not covered.
- **F3, the pack ships the author's own patch** (`Patches/KDEN.patch.osm`,
  three flatten levels at the site). The engine does not read a pack's own
  patch. It is a direct statement of the author's ground and could feed
  `geom/author_ground` (#1950); not part of this spec.
- **Not specified:** a census family for stack end lines (§5 row 32); a
  stack whose decks carry airside pavement (a taxiway deck over a stack
  floor is `deck_bridge`'s and `floor_decks`' today, and a mixed stack
  refuses with a note); a member placed `OBJECT_MSL`.
- 2026-11-11b ("authored decks grade like bridges") is applied to a stack's
  decks only. Its general form for every road deck is the KMCI lane's.
