# Interchange levels v2: the stack's ground is closed (spec after the round-1 miss)

Issue: #1971 (KDEN, 39.842347, -104.673859: rail under two crossing road decks).
Status: SPEC ONLY (one-miss review, RULINGS 2026-11-11c). No engine code was
written. A fresh Opus lane implements it; this spec's author never does.
Supersedes: nothing. It AMENDS `interchange-levels-20261113.md` (v1): every
section of v1 this file does not name stands as written.
Round reviewed: claude/l1971impl `c7e2313ae` / `b27b821bb` (replay on base
`0a1a225c0`), closing build `lkdenclose_KDEN` on claude/lkdenclose `0c7c9747b`.
Base for round 2: claude/lkdenclose `6f5445176` or later.
Law: RULINGS 2026-11-13g (drawn gate is the bar; O1 = a: decks at the real
road level, floor at the walls' feet, "not hanging walls"), 2026-11-13e,
2026-11-11b ("ground should grade to their ends like bridges"), 2026-10-29a
Q299 (a) ("the top of a retaining wall, which the hill grades down to, is the
wall object's top edge as it sits ... the back of the wall is buried"),
2026-11-06d (4) (the cut under an object's floor), 2026-09-13j item 5 and
§37 (6) (the road ramp and its ceiling), 2026-10-30a, 2026-10-05e.
Paths are under `Ortho4XP/src/auto_patch_v2/` unless they say otherwise.

## 0. Summary

Round 1 gave the stack POINTS and LINES: the floor, two road vertices at each
deck end, the void band's outer ring, and a ceiling on whatever vertex
happened to lie under a deck. Its replay bars read those same points, so they
passed. The drawn gate reads AREAS: the ground across a deck's whole end
edge, the ground under a deck's whole ring, the ground beside the walls. In
those areas the patch has no face, and X-Plane draws the lidar, which there
is the real road, the real embankment, or a bank metres off the walls' top.

Five mechanisms, each proven in §2:

- **M0** the closing build ran on a newer base than the replay; that base
  cuts every object floor 0.30 m under the object. The stack's walls have no
  floor plate, so they hang 0.30 m over the drawn floor. D2 "passed" at
  -0.29 against a 0.3 bar.
- **M1** the carried road's ribbon is 8-17 m wide; the deck's end edge is
  15-24 m. Off the ribbon the end edge is lidar (D3).
- **M2** only the ribbon's end pair is held at the plate. The next ribbon
  vertex is 12-21 m out on the road's own lidar target, so the road leaves
  the plate at up to 10 %. Two hard ramp-ceiling rows are violated at the
  south-east end (D3, finding P2).
- **M3** 68-77 % of the area under each deck's ring has no patch face. The
  ceiling row has no vertex to bind there. The lidar under the ring's end
  zones is the real approach, which stands over the plate at the three ends
  where the one zero lowered the road (D4).
- **M4** all 233 vertices of the void band's outer ring are the patch's open
  edge; 184 of them stand exactly on the bar's edge (crest - 0.50), and
  nothing covers the walls' cap strips (D5, D6).

The rule v2 adds: **the stack's ground is closed.** Every area the stack
states is a patch face with rows, and the patch meets the lidar only at an
outer edge that stands AT the lidar. It is said in forms the engine has:

1. The stack floor takes no clearance (the walls' feet are on it).
2. The ground under the decks, on the walls' caps and round the deck ends is
   "graded ground of its own": the third member of the family
   `planar/wall_slope` (#1661, Q299 (a)) and `planar/fill_bank` (#1915)
   already are.
3. A deck's end edge is held at the plate's top across the plate's whole
   width, not on two road vertices.
4. The carried road leaves a deck end as it leaves a foot lot (#1952): its
   ramp is seeded there, so the ramp target and its ceiling are measured
   from the deck's end, not from the lidar.

And one instrument rule so a round cannot pass the replay and miss the gate:
the gate's own D1-D6 function runs on the replay's emitted patch (PREDICTED,
§8.2), with a COVERAGE bar: every D sample must lie on a patch face.

## 1. What was read for this review

| artefact | state |
|---|---|
| closing patch + sidecar, `/Users/noah/XPTerrainBuilderData/.harness/frames/lkdenclose/KDEN_auto.patch.osm` (base `0c7c9747b`) | read |
| replay patch + sidecar, `.../frames/l1971impl/KDEN_auto.patch.osm` (base `2205323ab`) | read |
| replay arm and control: `.claude/worktrees/l1971impl/Ortho4XP/tmp/l1971impl/{arm,ctl}/` (`replay.log`, `replay.json`, `KDEN.graded.json`, `ctl/whyhard.log`) | read |
| the lidar inset `Elevation_data/+30-110/N39W105_airport_insets/KDEN_usgs3dep.tif` (shared data repo) | read (bilinear) |
| gate output `lkdenclose/Ortho4XP/tmp/lkdenclose/` (`lkdenclose_KDEN.drawn.json`, `gate.log`, `build.log`) | GONE (the worktree was removed). The D1-D6 numbers below marked "gate" are the master's brief, not re-read |
| the built tile (mesh, DSF) | GONE. Nothing in this review was read on the drawn mesh |
| capture `frames/l1971/KDEN.pkl` | not loaded (1 GB; the patches and sidecars carried what was needed) |

Drawn gate, round 1 (from the brief): D1 0.00 PASS; D2 -0.29 PASS; D3 lower
`obj31311` -0.40 / +0.54, upper `obj31312#0` +0.26 / -0.50, upper `#1`
-0.34 / +0.12 (bar 0.3); D4 -1.41, -0.78, -0.79 (bar: never under 0); D5
[-1.37, +0.03] (bar 0.5); D6 [-2.36, +2.35]; walls drawn bottom 1626.48, top
1630.03.

EMULATION used below: `tools/drawn_check.check_stack`'s own sample points
(`tools/drawn_check.py:457-527`), read on "the closing patch's face where
one covers the point, else the lidar". It is not the drawn mesh: off a face
the tile mesh blends between patch nodes and lidar postings, so the
emulation is exact on faces and only indicative off them.

## 2. The mechanisms, each from the artefacts

### M0. The floor is cut 0.30 m under the walls' feet (D2)

- Replay patch (base `2205323ab`): floor way `-11301`, 519 nodes, 1626.49 to
  1626.50. Closing patch (base `0c7c9747b`): the same way, 530 nodes, 1626.19
  to 1626.20. The sidecar of the closing patch says `floor_m 1626.495`,
  `clearance_m 0.3`.
- `constraints/object_floor.py:49,75` pins every object floor at
  `z - [tunnel.object] floor_clearance_m`. That is commit `0ffdf2764` (EGLL
  trench floors, #1921 / #1936, RULINGS 2026-11-06d (4): "the cut is deep
  enough that it's completely below the floor so the floor is visible"). It
  is NOT an ancestor of `b27b821bb`; it IS in `0c7c9747b`.
- The law is right for an object with a floor plate. A stack's walls have
  none (v1 §3.2 (4) is the witness), so the mesh IS the floor and the walls'
  feet (y -0.05, drawn 1626.48) hang 0.29 m over it. 13g (2) says "not
  hanging walls".
- The replay was never re-run on the base that was built. That is the first
  half of "replay held, drawn missed".

### M1. A deck's end edge is wider than the road's ribbon (D3)

End edges (sidecar `ends[].stations`, 5 m apart) against the ribbon's end
pair in the closing patch (offsets across the end edge from its middle):

| end line | end edge | ribbon's end pair across | stations with a patch face 5 m outside |
|---|---|---|---|
| lower `obj31311` end a (north-west) | 24.0 m | `big_roads:-5740`, -15.5 to -1.4 | 3 of 6 |
| lower end b (south-east) | 24.0 m | `big_roads:-18866`, -8.1 to +9.2 | 4 of 6 |
| upper `obj31312#0` end a (south-west) | 21.0 m | `big_roads:-2149`, -6.1 to +4.5 | 2 of 5 |
| upper `#0` end b (north-east) | 21.0 m | `big_roads:-3314`, -1.5 to +6.7 | 2 of 5 |
| upper `#1` end a (north-east) | 15.0 m | `small_roads:-4127`, -6.5 to +1.7 | 1 of 4 |
| upper `#1` end b (south-west) | 15.0 m | `small_roads:-18111`, -3.6 to +4.5 | 2 of 4 |

`check_stack` takes the MEDIAN over all stations (`drawn_check.py:483-487`),
so D3 mostly reads lidar beside the road. Emulated D3 against the gate:

| end | emulated | gate | per station (r = road face, d = lidar) |
|---|---|---|---|
| lower a | -0.43 | -0.40 | 1631.27d 1631.31d 1631.21d 1630.67r 1630.69r 1630.70r |
| lower b | +0.57 | +0.54 | 1628.95d 1630.16r 1630.00r 1629.97r 1629.94r 1629.07d |
| upper #0 a | +0.35 | +0.26 | 1637.93d 1637.83d 1638.34r 1638.34r 1638.18d |
| upper #0 b | -0.95 | -0.50 | 1639.47d 1638.59r 1638.57r 1639.49d 1639.61d |
| upper #1 a | -0.80 | -0.34 | 1639.24d 1639.53d 1638.80r 1639.40d |
| upper #1 b | +0.09 | +0.12 | 1638.34d 1638.47r 1638.47r 1638.39d |

The signs and the two on-face ends match the gate. v1's bar said "on the
road"; the tool reads the whole edge. Both are real: the instrument is wrong
(§8.3), and the ground beside the road at a deck end really is lidar, up to
1.0 m over the plate (north-east) and 1.5 m under it (south-east).

### M2. The road is held on two vertices and leaves at up to 10 % (D3, P2)

Road nodes of the closing patch, by distance outward from the end line
(plate top lower 1630.53, upper 1638.53):

| end | nodes within 10 m of a station | next ribbon node |
|---|---|---|
| lower a | 3 at 1630.57 (+0.04) | 13.7 m out, 1631.14 (+0.61): 4.5 % |
| lower b | 2 at 1630.49 (-0.04) | 13.3 m out, 1629.10 (-1.43): 10.5 % |
| upper #0 b | 4 at 1638.57 (+0.04), the outer pair 5 m out | 16.7 m out, 1639.53 (+1.00) |
| upper #1 a | 2 at 1638.57 | 11.7-12.8 m out, 1639.75 (+1.22): 10 % |
| upper #0 a / #1 b | 2 + 2 at 1638.49-1638.50 | 15 m out, 1638.41 (-0.12) |

- The same pattern is in the REPLAY patch (same nodes, same heights), so the
  defect was in the replay. The replay bar read "road nodes within 10 m of
  the end line" (the lane's `sites.py`), which is exactly the banded set.
- No vertex was lost on the way out: `KDEN.graded.json` has 1,372 vertices
  within 200 m of the site and the replay patch 1,372 nodes. Emit decimation
  and `to_osm` are NOT a cause.
- `constraints/deck_stack.py:83,95-113` bands a road vertex within
  `2 x abutment_sample_step_m` (10 m) of a station. Ribbon vertices are
  12-21 m apart there, so the band finds the end pair and nothing else.
- Beyond the end pair the road follows §37 (6): with no airside contact its
  target is the lidar and its hard ceiling is target + 0.5 m. At the
  south-east end the plate is 1.46 m over the lidar. `arm/replay.log:340-348`:
  rows 2595446 / 2595447, "roads.groundside_road ramp ceiling", v61309 /
  v61310, demanded 1630.4875 against allowed 1629.6708 / 1629.6778. The
  solve returned with those two HARD rows violated (31 violated hard rows
  against the control's 29, `ctl/whyhard.log`). v1's P2 said to report this
  and stop; it is finding P2.

### M3. No face under the decks; the lidar there is the real approach (D4)

`check_stack` D4 cells (2 m grid in each ring) by what the closing patch has
there:

| ring | cells | floor face | void band | road | NO FACE | no-face cells over the plate's lowest point | emulated least | gate |
|---|---|---|---|---|---|---|---|---|
| lower | 361 | 98 | 16 | 2 | 245 (68 %) | 89 | -0.62 | -1.41 |
| upper #0 | 533 | 101 | 19 | 0 | 413 (77 %) | 126 | -0.97 | -0.78 |
| upper #1 | 349 | 66 | 22 | 0 | 261 (75 %) | 99 | -1.01 | -0.79 |

Lidar along each deck's axis (metres from end a; plate top in brackets):

- lower [1630.53 at the ends, about 1631.6 at the crown]: 1631.0 at 0 m,
  1630.7 at 10 m, 1630.5 at 15 m, the plug 1630.1-1630.4 over the trench,
  1629.2 at 60 m. Over the plate for the first 10-15 m from the north-west
  end only.
- upper #0 [1638.53]: 1637.8-1638.0 for 0-15 m, falling to 1630.0 at 25 m,
  1629.7-1630.2 to 55 m, rising to 1638.0 at 75 m and 1638.9-1639.3 for
  80-100 m. Over the plate for the last 20-25 m at the north-east end.
- upper #1 [1638.53]: 1639.5 for 0-10 m (north-east end), 1629-1631 between,
  1638.5-1638.8 for 75-90 m.

So the ground comes through a deck at the ends where the one zero put the
plate UNDER the real road (v1 §3.6 residuals +0.52, +0.84, +0.96): the pack's
decks overhang the real abutments by 15-25 m, and the lidar there is the
real approach. v1 §3.7 (6) left "no face under a deck" to the lidar on one
measurement (the plug at the trench under the lower deck); it does not hold
for the end zones. The ceiling row (`deck_stack.py:123-139`) is right but
binds map vertices only, and there are none.

Also an instrument error: D4 compares the mesh with `plate_min_y`
(`drawn_check.py:502`, `model/deck_stack.py:134`), the plate's lowest point,
everywhere under the ring. The lower deck is arched (3.98 at the ends, 5.08
at the crown), so D4 overstates by up to 1.1 m at mid-span.

NOT EXPLAINED: the gate's lower-deck -1.41 against the lidar's -0.62. The
drawn mesh is gone; round 2 reads it (§8.4).

### M4. The walls' top is the patch's open edge; nothing is on the caps (D5, D6)

- The void band (way `-14462`): 233 outer-ring nodes; all 233 belong to the
  void band alone, i.e. they are the patch's open edge. 184 stand at 1629.54
  (crest - 0.50, the low edge of v1's band `[crest - visual_m, crest]` and
  the edge of D5's bar), 26 at 1630.04, one at 1630.42 (+0.38 over the
  crest, at the floor's south end, 39.842024, -104.673990: outside the rim
  selection).
- `constraints/object_floor._rim_pins` already records this class: "the
  band's own vertex alone (the patch ends there) ... the mesh draws the
  ground beyond (MEASURED legll1E1: 35 such rim nodes pinned at the top drew
  1-4.3 m under it)".
- D5 samples 1.0 m outside the wall line (`drawn_check.py:517`). The void
  band is 1.0 m wide. The sample is ON the outer ring: one side is the wall's
  slope, the other the lidar.
- D6 samples 3.0 m outside, on the walls' cap strips (5.5 m wide, 3,268 m2).
  No patch face is there (27 of 27 and 25 of 25 samples read lidar). `stack
  _shade` removed the two pads that stood there and nothing took their
  place. Lidar against the walls' top at those samples: east wall -6.8 to
  +3.9, west wall -4.5 to +8.1 (the gate, on the blended mesh: -2.36 to
  +2.35). The caps are buried in the middle and stand proud at the north
  end.

### What held

D1 (one zero, 0.00). The floor's shape and position: under both decks the
drawn floor follows the pinned ring nodes, not the lidar plug (D2's worst and
its under-both-decks value are the clearance and nothing else). The road end
pairs: all within 0.04 of the plate. The object-floor form is drawn as
solved; so is a road ribbon. That is why v2 uses faces, not new point rows.

## 3. The model, as amended

### 3.1 The floor takes no clearance (M0)

`ObjectFloor` gains `clearance_m: float | None = None` (None: the law's
`[tunnel.object] floor_clearance_m`). `airport/deck_stack.stack_floors` sets
`0.0`: a stack's walls state the floor with their feet and have no plate to
keep clear. `constraints/object_floor.object_floor_pins` and
`pipeline/publication.object_floors` read the floor's own value. Every other
object floor is unchanged.

Bar: floor nodes inside the walls = `zero_m + feet_y` within 0.02 m
(KDEN 1626.495; round 1's closing patch 1626.19-1626.20).

### 3.2 The stack's ground is graded ground of its own (M1, M3, M4)

New family member `planar/stack_ground.py`, the form of `planar/fill_bank`
and `planar/wall_slope`: `graded_strip` pieces, zone source, NO zone class
(the zone law binds no foot to them), refs under a new prefix
`STACK_GROUND_PREFIX = "stack_ground:"` beside `FILL_BANK_PREFIX` in
`model/planar.py`. Minted in `planar/overlay.py` straight after the fill
bank (`overlay.py:352-365`), with the same `taken` / `apart` / `cut_m` /
`hairline_m` arguments and `[design] edge_grid_m` (5 m) as the longest ring
edge.

The footprint is derived once, in `airport/deck_stack` (the record gains the
fields of §6.1). Three classes, disjoint, in this order of precedence:

1. **cap** (`stack_ground:<stack>:cap#k`): the plan of the walls' crest
   plates (`StackWalls.crest_tris`, the largest-area bin of v1 §3.2 (2)), off
   the floor. The author's ground beside the trench (Q299 (a)).
2. **shadow** (`...:shadow:<deck>#<piece>#k`): each deck piece's ring, less
   the caps. Where two rings overlap the cell belongs to the lower level's
   piece (both ceilings bind its vertices, §3.3).
3. **bank** (`...:bank#k`): what joins those to the lidar:
   - round the caps and the rings' side edges, a margin
     `B = clamp(max|level - DEM| / [design] bank_slope, bank_min_width_m,
     2 x [structures] platform_collar_max_m)`, where the maximum is taken
     over samples every `edge_grid_m` along the caps' outer edges (level =
     zero + crest): one value per stack (KDEN, from the lidar read of §2 M4:
     about 20 m, 6.8 m at 1:3);
   - beyond each end edge, the plate's width for
     `L_e = clamp(|G_e - (zero + top_e)| / [road_contact] ramp_grade +
     abutment_sample_step_m, bank_min_width_m, 2 x platform_collar_max_m)`
     (KDEN: 15-30 m): the ground beside the road comes off the deck's end as
     the road does.

Every piece is cut less the floor and its void band (the object floor's
knife is senior and cuts them anyway), less `taken` (zone bands), less every
cell, road ribbon and structure keep-out grown by the zones' groundside
stand-off, exactly as a fill-bank piece is. Nothing is minted on or against
airside pavement: a piece that would touch an airside cell is cut back and a
note says so.

No stack: no piece, and the overlay is byte-equal (twin).

### 3.3 The rows (`constraints/deck_stack.deck_stack_rows`, amended)

`top_e = zero + plate top on end line e`, `crest = zero + crest_y`,
`flush = [bridge] deck_flush_m` (0.04), `visual = [cockpit] visual_m` (0.5).

| row | vertices | row | replaces |
|---|---|---|---|
| R1 end edge | every vertex of a stack-ground face ON a deck piece's end edge (within the identity grid of it), and every road vertex v1 selects (`deck_stack.py:95-106`) | `Band(v, top_e - flush, top_e)` | v1's `Band(z - flush, z + flush)`: the ground and the road never stand over the plate's end |
| R2 walls' top and caps | every vertex of a cap piece, and every vertex of the void band's outer ring within `wall_face_max_thickness_m` of a wall line | `Band(v, crest - visual / 2, crest - flush)` | v1's `Band(crest - visual, crest)` (184 nodes on the bar's edge) |
| R3 under a deck | every vertex inside a deck ring, off the floor, not an R1 vertex of that deck | `Band(v, None, zero + plate y there - flush)` (unchanged) | — |
| R4 the toe | every vertex on the patch's open edge that belongs to stack-ground faces alone | `Pin(v, dem_z)` | new; the rule of `constraints/fill_bank.fill_toe_pins`, extended to the second prefix (one loop, each family's own ruling text) — do not fork it |
| R5 the target | every other stack-ground vertex | the weak ground datum at `dem_z` (`solve/design_ground`), as a fill-bank vertex carries | — |

R1-R3 keep the head `edge_deck.RIGID`. R2 on a cap piece may use
`constraints/wall_zone`'s wall-top head if that head is already in `[design]
hard_rulings`; `law/emit.toml` is not edited either way.

A vertex claimed by two end edges at heights more than `flush` apart is
refused by both, as in v1. A vertex where R2's band lies over R3's ceiling
(a cap under a deck's end, plate under crest + flush) keeps R3 and drops R2,
with a note. KDEN: none expected (the lower plate is 3.98 at its ends and
5.08 at its crown against the crest's 3.50, and the caps pass under it near
mid-span); VERIFY the count in the replay.

### 3.4 The road leaves a deck end as it leaves a foot lot (M2, P2)

`airport/road_ramp.road_ramp_targets` already seeds a ramp at "a road vertex
on a foot lot's ring" (`foot`, #1952; `road_ramp.py:918-925`): a descent
where the level stands over the road's floor, a cut where under, at the
design grade, cap-limited, and the vertex's own target and ceiling are
withdrawn. A stack's end-line road vertices are the same case:

- new `deck_end_seeds(pm, law, airport) -> dict[int, float]` (in
  `airport/deck_stack`): the R1 road vertices, each at `top_e`;
- `road_ramp_targets` takes them as a new keyword `deck_ends`; they join
  `seeds` / `cut_from` and `rep["_foot"]` exactly as `feet` do, with ONE
  difference, the HOLD: a descent is seeded at `top_e + g x H` and a cut at
  `top_e - g x H`, `g = [road_contact] ramp_grade`, `H = [bridge]
  abutment_sample_step_m`. R1 holds the vertex itself at `top_e`; the shift
  only moves the ramp's start one sample step out, so the road keeps the
  deck's level over that step (an approach slab) and D3's station is on it;
- the call site is `with_road_ramp` (`road_ramp.py:2000-2001`).

The selection of "end-line road vertices" is ONE function used by R1 and by
the seeds (a numpy predicate in `geom/`, so `airport/` and `constraints/`
may both import it; `tools/ratchets.py layers` decides its home).

Expected at KDEN (next ribbon vertex 11.7-20.6 m out, mesh linear between):
on the road 5 m outside each end line, 0.04-0.16 m off the plate (round 1:
up to 0.59, lower deck south-east). The two ceiling rows at v61309 / v61310 are gone, not relaxed:
their vertices are seeds.

### 3.5 What stays from v1

§3.1-§3.6 (the witness, the floor polygon, members, levels, the carried
stretch as a mapped bridge, the one zero), §3.8's floor and seats, §3.9's
ownership, the pad shade. v1 §3.7 (6) "where the patch has no face under a
deck the tile mesh keeps the DEM" and §3.7 (7) "no bank ... is added for a
stack" are WITHDRAWN by §3.2.

## 4. Can a heightfield mesh carry it?

- Every new piece is one height per point: the decks are objects, the pieces
  are ground under and beside them.
- A face's interior is drawn from its own nodes, not the lidar: the floor
  face is 12 m wide over a 3.6 m lidar plug and the gate read it flat
  (round 1 D2 under both decks = the clearance alone).
- Under a flat plate, any triangulation of vertices that are all under the
  plate is under the plate. The lower deck's plate is arched upward along
  its axis only, so the same holds.
- A shadow piece falls from a deck's end edge (1638.5) to the caps (1630.0)
  in 15-25 m. It is steep (up to about 50 %) and it is under the deck.
- The pieces stand off road ribbons and the void band by the groundside
  stand-off (about 1 m). Both sides of such a gap are held within 0.25 m of
  each other by R1 / R2, so the mesh across it is flat.
- The toe is on the lidar (R4), so the patch's edge is not a step.

## 5. Consumer census for the new region (RULINGS 2026-08-30l)

The region class is not new: it is the fill bank's (`graded_strip`, zone
source, no zone class, a ref prefix). Ruled before any consumer is edited:

| # | pass | interaction | ruled |
|---|---|---|---|
| 1 | `planar/stack_ground` (NEW), `planar/overlay` | DERIVES / EDIT (one block after the fill bank) | §3.2 |
| 2 | `airport/deck_stack`, `model/deck_stack` | EDIT: the footprint fields, `deck_end_seeds`, the floor's `clearance_m` | §3.1, §3.2, §3.4 |
| 3 | the overlay's noding and weld (pass A) | FREE: zone-source regions node with the airside as the fill bank does. VERIFY: no airside vertex moves (v1 §8.2's 0.01 m bar) | — |
| 4 | `planar/zones`, `zone_pass`, `constraints/zones`, `strips`, `groundside` (zone-class readers) | UNCHANGED: no zone class. VERIFY: 0 rows of those generators name a stack-ground vertex alone | §3.2 |
| 5 | `solve/design_ground` | FREE + VERIFY: the pieces' vertices are in `ground_datum_vertices` | R5 |
| 6 | `constraints/fill_bank.fill_toe_pins` | EDIT: the second prefix | R4 |
| 7 | `constraints/deck_stack` | EDIT | §3.3 |
| 8 | `airport/road_ramp` (`road_ramp_targets`, `with_road_ramp`), `airport/road_descent` | EDIT `road_ramp.py` (keyword + call site); `road_descent` UNCHANGED | §3.4 |
| 9 | `constraints/road_ramp` (`wall_release`, `pad_weld_release`, terraces), `planar/low_extent`, `planar/build.slope_sides` | UNCHANGED: they read wall-slope refs, not this prefix | — |
| 10 | `planar/object_floor_cells` (the knife, the keep-outs) | FREE. VERIFY: no stack-ground face overlaps the floor or the void band; the gap between the void band's outer ring and a cap piece is at most the stand-off | §3.2 |
| 11 | `constraints/object_floor` | EDIT: the floor's own clearance. `_rim_pins` UNCHANGED (a stack floor has no `rim_tops`) | §3.1 |
| 12 | `airport/bridge_ground` (the `dem_z` substitution) | FREE + VERIFY: report its runs and lowered vertices; R3 binds whatever it leaves | — |
| 13 | pads, clusters, `stack_shade` | UNCHANGED (v1) | — |
| 14 | `classify`, road ribbons | UNCHANGED: ribbons are `apart` | — |
| 15 | `emit/*` | UNCHANGED. VERIFY: the pieces are written as `graded_strip` ways with their ref | — |
| 16 | `verify/*`, `tools/check_grade.py` families | UNCHANGED by the fill-bank precedent. VERIFY: every verify / census row within 150 m of the site that the control does not have, listed with its family | — |
| 17 | `pipeline/publication.object_floors` | EDIT: the `"stack"` record gains what the gate needs (§6.1) | §8.3 |
| 18 | `tools/drawn_check.py` | EDIT | §8.2, §8.3 |
| 19 | `pipeline/stage_code`, the code-closure twins | EDIT as the twins say | — |
| 20 | the object stage, the seats | UNCHANGED | — |
| 21 | the engine core (mesh) | UNCHANGED. VERIFY on the drawn mesh (§8.4) | — |

## 6. Implementation plan (for the Opus lane)

Edit by shell in the lane's own worktree. `tools/blast.py <file>` before
each edit; `tools/blast.py --find` before adding a function. Never raise the
lane cap; delete scratch builds when reporting.

### 6.1 Files

| file | change |
|---|---|
| `planar/stack_ground.py` (NEW) | `stack_ground_pieces(airport, taken, apart, cut_m, hairline_m, vertex_m) -> list[tuple[str, Polygon]]`; `[]` without a stack |
| `model/planar.py` | `STACK_GROUND_PREFIX`, `is_stack_ground_ref` |
| `model/deck_stack.py` | `DeckStack.caps: tuple[tuple[XY, ...], ...] = ()`, `ground_margin_m: float = 0.0`; `sidecar()` adds `caps` (lat/lon rings), `band_m` (the void band's width), per deck `plate` (its triangles as lat, lon, y) and per end `ground_m` (G_e) |
| `airport/deck_stack.py` | fill those fields; `stack_floors` sets `clearance_m=0.0`; `deck_end_seeds` |
| `airport/object_floor.py` | `ObjectFloor.clearance_m: float | None = None` (one field) |
| `constraints/object_floor.py`, `pipeline/publication.py` | read the floor's own clearance |
| `planar/overlay.py` | the mint block |
| `constraints/deck_stack.py` | §3.3 |
| `constraints/fill_bank.py` | R4's second prefix |
| `airport/road_ramp.py` | `deck_ends` keyword and the call site |
| `geom/` (one small function) | the end-line vertex predicate shared by R1 and the seeds |
| `tools/drawn_check.py`, `tools/INDEX.md` | §8.2, §8.3 |
| `pipeline/stage_code.py` | key the new module |
| `tests/auto_patch_v2/test_deck_stack1971.py`, `tests/test_drawn_check.py` | §7 |

NOT touched: `planar/deck_bridge.py`, `planar/overlay`'s noding passes,
`planar/object_floor_cells.py`, `planar/structures.py`, `airport/road_
descent.py`, `constraints/edge_deck.py`, `constraints/road_ramp.py`,
`law/*.toml`, `emit/*`, the object stage. Needing one of them is a deviation:
stop and report.

### 6.2 Order (each slice closed by its own predicted bar, §8.2)

1. **S0** start from the build base. Write §8.2's PREDICTED check first and
   run it on round 1's closing patch (`frames/lkdenclose/KDEN_auto.patch.osm`):
   it must reproduce §2's tables (D2 -0.30; 245 / 413 / 261 uncovered D4
   cells; D6 52 of 52 uncovered; D3's signs).
2. **S1** the clearance (§3.1). Predicted D2 0.00.
3. **S2** the seeds (§3.4). Predicted D3 on the road.
4. **S3** the ground pieces and rows (§3.2, §3.3). Predicted D3 beside the
   road, D4, D5, D6, coverage.
5. **S4** ONE closing build on the same sha (§8.4).

### 6.3 Build-time impact statement

One more region family at the overlay for an airport with a stack (KDEN:
about 20 pieces, a few hundred vertices) and none elsewhere (the function
returns on an empty `deck_stacks`). Expected under 0.3 s at KDEN, 0 s at
every other airport. The lane prints the step's seconds; 0.6 s or more is a
stop.

## 7. Twins (added to `tests/auto_patch_v2/test_deck_stack1971.py` on v1's 3-level X fixture, unless named)

| twin | asserts |
|---|---|
| T17 | `stack_floors`' floor carries `clearance_m == 0.0`; `object_floor_pins` pins it AT the floor and an ordinary object floor 0.3 m under its own |
| T18 | `stack_ground_pieces`: cap, shadow and bank refs; the caps cover the crest plates; the shadows cover each ring off the floor; pieces are disjoint; none overlaps the floor, the void band, a ribbon or an airside cell; longest ring edge <= `edge_grid_m`; with no stack `[]` and the overlay's regions equal the control's |
| T19 | COVERAGE on the fixture: every `check_stack` sample point (D2-D6) lies in a face or within the stand-off of one |
| T20 | R1: every stack-ground vertex on an end edge and every end-line road vertex has `Band(top - flush, top)`; none has an upper bound over the plate |
| T21 | R2: cap and rim vertices in `[crest - visual / 2, crest - flush]`; R3 present on every shadow vertex; a vertex where R2 would stand over R3 keeps R3 |
| T22 | R4: open-edge vertices of bank pieces alone are pinned at `dem_z`; the fill bank's own toe pins are unchanged on a fill fixture |
| T23 | `deck_end_seeds` = R1's road vertices (one selection); `road_ramp_targets(..., deck_ends=...)`: a deck end 1.5 m OVER the DEM gives targets `top` at the seed, `>= top - g x (s - H)` at distance s, and no ceiling row at the seed; a deck end 0.8 m UNDER the DEM gives the mirrored cut; without `deck_ends` the targets hash equal to today's |
| T24 (`tests/test_drawn_check.py`) | `check_stack` on synthetic samplers: D2 fails at 0.3 m (a hanging wall) and passes at 0.05; D3 reads road stations and ground stations apart; D4 reads the plate at the cell (an arched plate passes ground that is under it at mid-span and over `plate_min_y`); D5 samples off the void band; D6 only where a cap is published; a sample on no face makes the PREDICTED verdict INCOMPLETE; the predicted and drawn paths call the same `check_stack` |

Gates before reporting: these twins; the files covering the edited shared
modules (`test_object_floor1903.py`, the fill-bank and wall-slope files
`blast.py` names, `test_road_ramp*.py` that cover `road_ramp_targets`,
`tests/test_drawn_check.py`, `tests/test_drawn_gate.py`); the registry gates
of v1 §6.4; `tools/ratchets.py`. No full suite.

## 8. Bars

### 8.1 Replay (node bars; necessary, never sufficient)

On the capture `frames/l1971/KDEN.pkl`, `--from classify --verify --emit`,
on the sha that will be built:

- v1 §8.1 unchanged (zero 1626.545, spread 2.37, members, levels, carried).
- floor nodes inside the walls 1626.495 +/- 0.02;
- end edges: every R1 node in [plate - 0.04, plate] (lower 1630.53, upper
  1638.53), at least one node per 5 m of each end edge (round 1: 2-4 nodes
  per edge);
- caps and rim: every node in [1629.79, 1630.00]; 0 outer-ring rim nodes
  outside it (round 1: 184 at 1629.54, one at 1630.42);
- `--why-hard`: no violated hard row names a stack vertex (round 1: two);
  the count of violated hard rows is not above the control's;
- no airside vertex moves more than 0.01 m against the control replay.

### 8.2 PREDICTED drawn (new; the replay-to-drawn check)

`tools/drawn_check.py --predict`: the SAME `check_stack` over a sampler made
of the emitted patch: a point reads the face that covers it (containment as
`tools/osm_site.py --contains` decides it; height by linear interpolation
on that face's own nodes); a point on no face reads the build's DEM and is
marked UNCOVERED. The written rows come from the rebake replay on a pack
copy (`tools/v2_rebake_replay.py plan --write-pack COPY --plan-out PLAN`,
`drawn_check --plan`). Extend `drawn_check`; do not write a second tool.

Bars (the round does not build until all hold):

- **COVERAGE**: every D2-D6 sample is on a face, or within the groundside
  stand-off of one. An uncovered sample makes the verdict INCOMPLETE, which
  is not a pass. (Round 1: lower 245 of 361 D4 cells uncovered, upper 413 /
  261; D6 52 of 52.)
- the D bars of §8.3, each at HALF its tolerance (D2 0.05, D3 road 0.15,
  D3 ground 0.25, D4 >= 0, D5 / D6 within [-0.25, 0]).

### 8.3 The drawn gate's D rows, restated (instrument corrections named)

`venv/bin/python tools/harness/drawn_gate.py KDEN --tag <tag> --site
stack=39.842347,-104.673859,150 --site trench_n=39.84370,-104.67400,150
--site trench_s=39.84090,-104.67390,200` — verdict PASS at the three sites.

| row | measure | bar | change from v1, and why |
|---|---|---|---|
| D1 one zero | the members' written elevations | within 0.01 m | none |
| D2 the floor | drawn mesh on the floor's centreline against the walls' drawn bottom | within 0.10 m | was 0.3: a 0.29 m hanging wall passed |
| D3r the road at each end | drawn mesh one sample step outside the end line, at the stations that lie on a road face of the patch, against the drawn plate top | within 0.3 m | "on the road" as v1 wrote it; the tool read all stations |
| D3g the ground at each end | the same at the stations off the road | within 0.5 m (`visual_m`) | new: the ground beside the road is ground, judged at the ground bar |
| D4 nothing through a deck | 2 m grid under each ring: drawn plate AT THE CELL (the published plate triangles) less drawn mesh | never under -0.05 m | was `plate_min_y` (wrong by up to 1.1 m under an arch) and 0: the road is flush with the plate's end by law (+/- 0.04), so 0 has no margin |
| D5 the walls' top | drawn mesh `band_m + 0.5` m outside each wall line against the walls' drawn top | within 0.5 m under, never more than 0.05 over | was 1.0 m outside = on the void band's outer ring |
| D6 the caps | drawn mesh 3 m outside each wall line where a published cap ring covers the point | within 0.5 m of the walls' drawn top | was every rim point, cap or not |

Layers 1 and 2 of the gate as v1 §8.4 (every stack node on the drawn mesh:
pavement roles within 0.05 m, others within 0.5 m).

### 8.4 Replay to drawn (so replay cannot pass and drawn miss)

1. ONE SHA. The replay that is reported, the predicted check and the build
   run on the same commit. If the base moves, all three are re-run. The
   report names the sha once.
2. The build's emitted patch against the replay's, at the stack's faces
   (floor, void band, stack-ground, the carried roads' end faces): node
   heights equal within 0.02 m at equal positions (`tools/arm_site_read.py`
   or `osm_site.py` on both files). Not equal: STOP, the build did not solve
   what the replay solved (round 1: 0.30 m at 530 floor nodes, unseen).
3. Drawn against predicted, per D row: report both. A row that passes
   predicted and fails drawn, or differs by more than 0.15 m, is reported
   with its samples (position, face, predicted, drawn): that difference is
   the mesh step's and is the finding the next reader needs. It is a FAIL of
   the round all the same.
4. Report the lower deck's D4 at its worst cell with the cell's position
   (round 1's -1.41 is not explained by the lidar, §2 M3).

Closing build: v1 §8.3's command with the round's own tag, `--pack-copy`,
`df -h` 30 GB free, one build, tile dir and pack copy deleted after the read.

## 9. Regression

v1 §9 unchanged (dry A/B on KBNA, LGAV, EGLL, OTHH, KMCI: `0 stacks`, equal
ways and map). Added, on one capture each:

- EGLL (`rc1903-floor/EGLL.pkl`) full replay: every object floor's pins
  unchanged to 0.001 m (the clearance edit must not move a non-stack floor);
- one old-DEM fill capture the fill-bank lane registered (`frames.py list`;
  FHSH if present): `fill_toe_pins` returns the same rows.

## 10. Owner questions (yes / no; each has the spec's default)

- **Q1, the road ramp ceiling at a deck end.** Today a groundside road may
  stand at most 0.5 m over its ramp target, and with no apron contact the
  target is the lidar (2026-09-13j item 5). At a pack deck's end the road
  must meet the deck: 1.5 m over the lidar at the lower deck's south-east
  end, 0.5-1.0 m under it at three others. "On the approach to a pack deck,
  the road ramps from the deck's end to the ground at the road's design
  grade (5 %), and the 0.5 m ceiling is measured from that ramp, as it
  already is from an apron or a foot lot. Yes / no?" DEFAULT yes: it is how
  11b ("ground should grade to their ends like bridges") and 13g (2) read
  together, and the ceiling stays hard everywhere else. A "no" means the
  decks cannot stand at the real road level at KDEN (O1 would have to be
  re-ruled). The spec author's view: no NEW ruling is needed, but the
  ceiling is a registered hard ruling, so the master should record the
  owner's yes before the build.
- **Q2, the ground beside the walls.** The pack's walls are 3.5 m tall on a
  flat floor for 310 m; the real ground beside them is not flat. With the
  ground graded to the walls' top (Q299 (a)), the bank beside the caps falls
  up to about 6.8 m at the north-east end (the walls stand proud of the real
  ground there) and the hill is cut 1-4 m along the middle. "Grade the
  ground to the walls' top along the whole trench, with a bank to the real
  ground beyond the caps. Yes / no?" DEFAULT yes. A "no" leaves the caps
  buried or the walls' backs bare, and D5 / D6 are then judged only where
  the lidar stands within 0.5 m of the top.

For the master, not the owner: §8.3's five bar corrections (D2 tighter; D3
split; D4's plate and -0.05; D5's offset; D6 on caps only). Each corrects
the instrument to what v1's text asked or to the law's own tolerance; none
relaxes a bar the owner set.

## 11. Convergence guards

- Materiality 0.01 m unless a bar states its own.
- Attempt cap: two fix iterations per pre-registered target, then STOP.
- This is the last Opus round under RULINGS 2026-11-11c: a miss goes to the
  owner (park / ship / redesign). So STOP and report rather than improvise
  when: a NOT-touched file must change; the predicted check cannot reproduce
  §2's tables on round 1's patch (S0); a stack-ground piece touches airside;
  an airside vertex moves; the hold shift cannot be given to
  `road_ramp_targets` without editing `road_descent`; the step costs 0.6 s.
- Heartbeat: `.progress` stamps in the lane's scratch dir.
- Report: site numbers first (§8.3 with every number, predicted beside
  drawn), then §8.1, net lines, new public symbols, and a Process line.

## 12. Not verified, and findings for the master

- The drawn mesh and the gate's own JSON were not read (removed with the
  lkdenclose worktree). §2's D numbers marked "gate" are the brief's. The
  emulation matches them in sign and, on faces, in size; off faces it does
  not (D5 / D6 ranges, D4 lower -0.62 against -1.41).
- The "FREE" rows of §5 rest on the fill-bank and wall-slope precedents, not
  on a replay of this region class. Each has a VERIFY number.
- That `descend` / `climb` accept a shifted seed without a side effect on
  the ramp's built grade is read from the `foot` path, not run.
- The gate's patch-to-drawn layer at `trench_n` / `trench_s` (the run-outs
  stand 2-5 m over the lidar inside a 1 m void band) was not available;
  round 2 reports it. The run-outs' outer ring is still an open edge. If the
  gate fails there, that is a finding (the run-outs need the bank too), not
  something to fold into this round.
- F4: `0ffdf2764` changed every object floor after l1971impl's replay and
  before its build. A lane's closing build base and its replay base were
  different commits and nothing compared them. §8.4 (1)-(2) is the rule
  this spec adds for the stack; it is worth a line in the lane brief
  template.
- F5: a mapped bridge with no pack walls has the same M3 defect wherever the
  lidar keeps the real deck or approach and the patch has no face under the
  span (#1935 lowers targets of existing vertices only). Not in this spec.
