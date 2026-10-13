# jetbay612 — a terminal's pad takes in its jetways (#612, RULINGS 2026-10-12l (2))

Lane `jetbay612`, branch `claude/jetbay612` from main a11299a48. Worktree
`/Users/noah/XPTerrainBuilder/.claude/worktrees/jetbay612`. Scratch
`<scratchpad>/jetbay/`. RESUME HERE.

Master course-correction (received mid STEP 0): HECA (12m, body 53a84604b6ce,
`/tmp/harness/sw17_HECA.*`) and OTHH (12j, e8770bd28b9a, `sw17_OTHH.*`) are
APPROVED references; the design must report, per airport, which pads grow, the
area, the level, frontage rows relaxed, airside movers by family (runway 0),
OTHH's 10 pits + 15 authored seats byte-identical — and how their jetways sit
TODAY under the STEP 0 instrument.

## STEP 0 — the defect measured (in progress)

KSEA build: `build_airport.py KSEA` started 2026-10-12T17:33 on this tree
(`/tmp/harness/KSEA_20261012T173313.*`). Pre-flight passed (no refusal).

KSEA pack `c_USA - 100_airport - KSEA Seattle Airports XP (DD)`: 81 jetway-named
placements in the airport box (68 `MisterX_Library/Airport/Jetways-SAM/Jetway_Steel_Old_4m.obj`,
13 `Jetway_Steel_Modern_4m.obj`; SAM library objects), apt.dat 1300 startups:
gate 120, tie_down 10, misc 2.

### The instrument (extension of a near-fit, `tools/seat_feet_census.py --dsf-dump`)

Jetways are NEVER plan rows: at HECA, OTHH and KSEA every jetway resource is
"placed at N anchors" (a multi-anchor resource the partition drops) → the
rebake plan skips it, `provenance.jetway_strips` is EMPTY on both approved
builds (the strip is disarmed on a held block, v2 §3 P12), so `riders_for_dump`
returns () and the jetway stays a plain `OBJECT` row the sim DRAPES AT ITS
ANCHOR. Its float/burial is therefore the design surface between its anchor
and the ground its parts reach. `obj8_split_report --filter Jetway` measures
nothing (0 rows in plan); `jetway_rider_census` has no strip to read.

Added (same tool, new mode, no new file): `seat_feet_census.py --dsf-dump TEXT
--pack ROOT --graded G [--names jetway] [--host-m 12] [--reach-m 25] --json`:
every pristine `OBJECT` row whose resource matches, feet read about y=0
(`base_ref`; the authored rooms reach −4.5 m at OTHH/HECA and SAM's animated
struts −11 m, so the file base is not the ground), library resources resolved
through the read-only `library.txt` index (KSEA's jetways are
`MisterX_Library/Airport/Jetways-SAM/*`), `.agp` feet = footprint corners; per
row: role under anchor/feet, host pad (nearest `building` face within 12 m) and
its median level, and `reach_profile` — the design surface RELATIVE TO THE
ANCHOR along the object's −z axis at 5/10/15/20/25 m and the min/max over a
25 m disc (positive = ground above the anchor = parts buried; negative =
floating). The rest-pose feet residual is kept but is meaningless for a SAM
jetway (animated wheel strut); the terrain reach is the reading.

### HECA (sw17, approved 12m) and OTHH (sw17, approved 12j) — jetways TODAY

| airport | jetway rows | host pad (level) | anchor − pad level | 25 m disc spread: max / rows > 0.3 | forward 25 m: max / > 0.3 |
|---|---|---|---|---|---|
| HECA | 51 (48 `.agp`, 3 `EGCC_Jetway_metal_03.obj`) | building4 = T3, 101.79 m, all 51 | max 0.03, median 0.00 | 0.57 m / 14 | 0.41 m / 6 |
| OTHH | 129 `.obj` (Type4–10) | building6 (+#1–#4) and building5, 3.96 m, 112; 17 no pad within 12 m | 0.00 | 2.12 m / 5 (the five are the approved pits/trenches beside the anchor; every forward station 0.00) | 0.00 / 0 |

So at both approved airports every jetway anchor stands ON its terminal's
level and the apron under its reach is within 0.41 m (HECA, ~1.5 % forward
grade over 25 m) or dead flat (OTHH). They sit right today; nothing there is
owed a change. At HECA T3 the plateau (`building4`, 165,020 m², source
riders+startups, datum 101.791) already holds the apron under all 51.

### KSEA — the STEP 0 build (`KSEA_20261012T173313`, main a11299a48, rc 0, 1,825.9 s wall under load 100–170; frames registered under lane jetbay612: patch, graded, rebake)

Held blocks 11; warned 5: building13 (119.016 m, 3/151 released, max 0.673),
building7 (116.579, 9/64, 1.863), building8 (114.385, 3/79, 0.744), building9
(115.129, 5/28, 0.627), building16 (121.999, 1/64, 0.111 — under the margin, not
warned by the app). The app's four (building13/7/8/9) are the same blocks; the
levels differ from the owner's log by 0.9–1.3 m (this build: 119.02 / 116.58 /
114.39 / 115.13 vs 118.10 / 115.38 / 113.49 / 113.86 — the owner's app 1.0.388 is
an older tree; same blocks, same release pattern). Plateaus 7 (building13 61,882
m²; building7 51,831; building8 35,163; building16 36,330; …), all
`riders+startups` — so the stand-zone plateau DOES exist under the KSEA
terminals, as at HECA.

Jetway rows: 81 (`MisterX_Library/Airport/Jetways-SAM/Jetway_Steel_Old_4m.obj`
68, `Jetway_Steel_Modern_4m.obj` 13; library resources, animated SAM objects,
plain `OBJECT` rows, no plan row). Full table `<scratch>/jetbay/ksea_table.md`
(81 rows: lat, lon, anchor role, host pad + level, anchor − level, disc min/max,
forward 10/20/25 m, nearest released contact).

| reading (81 jetways) | KSEA | HECA | OTHH |
|---|---|---|---|
| anchor stands on | **door_ramp 35, NO FACE 44** (a hole: nearest face junction 17 / building 15 / apron 7 / door_ramp 5 at 0 m), apron 2 | apron 50, building 1 | apron 100, building 28 |
| host pad within 12 m | building7 26, building16 16, building13 15, building8 10, none 14 | building4 51 | building6/5 112 |
| anchor − host level | max 2.15 m, > 0.3 m: 45 of 67 (building7 −2.15…+0.49; building13 −0.78…+1.48; building16 −1.12…−0.20; building8 ±0.25) | max 0.03 | 0.00 |
| 25 m disc spread | max 3.92; > 0.3: 67; > 1 m: 35 | 0.57; 14; 0 | 2.12; 5 (pits); 0 |
| ground BELOW the anchor (float) | worst −3.07 m, rows < −0.3: 32 | −0.55, 6 | −2.12 (pits), 5 |
| ground ABOVE the anchor (burial) | worst +2.16 m, rows > 0.3: 63 | +0.43, 6 | 0 |
| jetway anchors within 5 m of a `door_ramp` face | **81 of 81** | — | — |

### THE MECHANISM (attributed by reading; the intervention follows)

KSEA's graded surface carries **83 `door_ramp` faces; 79 of them are witnessed
by the SAM jetway objects themselves** (sidecar `tunnel_objects`, kind `door`:
66 × `Jetway_Steel_Old_4m.obj`, 13 × `Jetway_Steel_Modern_4m.obj`; the other 4
by `KSEA_AR_03/04.obj`). Each is a 3.5 × 2.8 m well 1.6–2.4 m deep (median 1.72)
cut into the apron at the jetway's own anchor: the SAM jetway's AUTHORED
geometry reaches −11 m (the animated wheel strut and rotunda column, `ANIM_trans
sam/jetway/extent`, 84 ANIM blocks), with base plates at −4.4 m; the door-well
reader (`airport/door_wells.py` rule 1, `screened` → `witnesses_of`) finds a
near-horizontal plate between `sill_min_depth_m` and the basin gate, outside the
object's at-grade geometry, and mints a DOOR RAMP (`planar/door_ramps.py` LAW A,
exempt from the cap, 07c (1)). The apron is then cut 1.7 m down under every
jetway; the sim drapes the jetway `OBJECT` at the anchor — into the ramp (sinks,
"partly underground") — and the apron 5–25 m away stands up to 2.2 m above /
3.1 m below that anchor, so the cabin end and the neighbours' reach float or
bury. This is the owner's picture exactly, and it is NOT a pad-outline
question: the stand-zone plateau is there (building7's 51,831 m² at 116.58) and
the apron would be at the pad's level under the jetways but for the ramps.

It is the same defect class lane wells551 closed today for the BASIN reader
(#551: a jetway's roofed service room read as a pit — OTHH 45 → 10 basins):
the #551 "standing on the ground" witness (`obj8.read_placement`: deepest plate
roofed by the object's own solids ≥ `basement_cover_min` AND solid top above
ground > plate depth, `rep.standing`) was built into the basin pass only; the
door-well reader has no such witness and reads the same objects one law family
over. HECA's `.agp` jetways cannot witness (no OBJ geometry) and its 3 `EGCC`
jetways were refused as basements; OTHH's were refused by #551 today — which is
why those two airports sit right and KSEA does not.

### The witness (probed in isolation, `<scratch>/jetbay/door_probe.py`: one object on a flat DEM through `read_objects` + `read_door_wells`)

The SAM plinth reproduces alone: `Jetway_Steel_Old_4m.obj` → sill witness =
component 0 (−1.70…+1.70 m, 3.4 × 2.8 m, plate 6.7 m²), one well, `plate_cover`
73 % (< `basement_cover_min` 90 %: the plinth's lid is cut where the rotunda
column passes), so every gate of spec §5 passes. The basin reader does not mark
it `standing` (#551 needs a basin-gate plate; the strut's −11 m block is not
roofed ≥ 0.9). What separates it from every legitimate door well, read on the
WELL REGION (not the plate):

| object | region m² | building at-grade solids INSIDE the well (region eroded by `floor_overlap_m` 0.3) | verdict today | verdict under the rule |
|---|---|---|---|---|
| SAM `Jetway_Steel_Old_4m` | 23.1 | **76 %** (the rotunda column + pillars stand on the plinth) | door | FOUNDATION, refused |
| SAM `Jetway_Steel_Modern_4m` | 14.9 | **70 %** | door | FOUNDATION, refused |
| OTHH `Terminal_Parking_Parking-Left_000` (approved, 2 ramps) | 6.2 | 0 % | door | door (unchanged) |
| OTHH `Terminal_Parking_Parking-Right_000` (approved, 2 ramps) | 6.8 | 0 % | door | door (unchanged) |
| twin `door.obj` (building + well at its face) | 7.4 | 0 % | door | door |

RULE (general, name-free; `airport/door_wells.read_family`, after the basement
cover test): a door well is dug OUTSIDE the face it serves — the building's
at-grade solids touch it only along the sill strip. A well whose interior the
building's own at-grade solids occupy (area > the identity grid²) is the ground
the building stands in: a FOUNDATION, refused and named "(#612)". No new law
number (`cutout.floor_overlap_m` and `emit.identity.min_distinct_spacing_m` are
the two it reads). Twin
`test_v2doorramp.test_a_foundation_under_a_standing_object_is_not_a_door`
(an open plinth with a column standing in it → refused FOUNDATION; the fixture
door beside it still a door). Door twins 10/10 pass.

HECA carries 0 door ramps (unchanged by construction); OTHH's 4 are the two
garages at 0 % — unchanged. KSEA arm: replay of `jetbay/KSEA.pkl --from planar`
(re-reads the pack's door wells under this tree) vs the same-tree base.

Committed 8a626b3d5 on `claude/jetbay612`: the refusal, the twin, the tool
mode (+ INDEX row), notes, frames. `tests/test_no_airport_specific_code.py::
test_the_readers_see_an_offence` ERRORS on this tree AND on main c379d3784
(the per-session shared-repo snapshot detector: a subprocess write by a
concurrent lane; the 6 code gates pass) — pre-existing, not this lane's.

## STEP 1 — the design, against the live code (numbers from the arm below)

The owner's sentence names a fix ("expand terminal pads to include jetways so
that area remains flat, and the apron grades to it") for a picture ("jetways
floating and partly underground") whose measured cause at KSEA is a door ramp
minted under each jetway by the jetway's own plinth. Two different questions,
kept apart:

(a) THE CUT UNDER THE JETWAY — the foundation rule above. No pad outline, no
law key, no consumer touched: the door reader refuses one more class of well
by the geometry it already reads. After it, what stands under a KSEA jetway is
what stood there before the ramp: the stand-zone PLATEAU (riders + startups,
held at the block datum) where the jetway is within 40 m of a rider edge or
30 m of a gate, else plain apron graded within its cap.

(b) THE FLAT AREA — 12l (2) as law: "the flat pad extends over the jetways,
and the apron grades to that edge". What exists already IS this for the
jetway's own reach: `planar/pad_cut.plateau_cut` region (a) = the apron
within `jetway_strip_m` (40 m) of every RIDER EDGE of the block (a rider = a
placement within 12 m of the outline the plan holds no geometry for — every
jetway at HECA / OTHH / KSEA is one) and (b) = `stand_zone_radius_m` (30 m)
round every `gate`/`tie_down` startup within 60 m of the held contacts, swept
to the outline; one region, hard at the datum, ref `<apron>#plateau:<block>`,
taxi / runway vertices `foreign`. So "the pad takes in its jetways" is built
today as a PLATEAU, not as a re-roled building pad (08e (A) Q1 YES), and it
already reaches ≥ 40 m past the jetway's root — further than a SAM cabin's
17 m extent. What §57 (2) adds on top is the WHOLE BAY (hull pocket holding a
gate) — the owner's 08b "whole piers as well"; 09g (1) set it aside and 12l
reopens it "to be returned with numbers". The numbers that decide whether the
bay matters FOR THE JETWAYS are the arm's: with the ramps gone, is the ground
under every jetway's 25 m reach within 0.3 m of its anchor and of the pad's
level? If yes, (a) alone closes #612's sim picture and the bay is a separate,
sloping-ground question (12l's "how large a flat pad sloping ground allows")
with its own owner numbers; if no, the bay (or a deeper strip) is owed.

Consumer census of the plateau region (what a bay extension would touch) —
ONE derivation site, `pad_cut._stand_zone` (the union of parts (a)+(b),
closed by Rz/2, clipped to the held span and the apron bodies the outline
touches); every reader below reads the SET it produces, never the region
rule, so a region change at that site needs no consumer edit:

| reader | what it reads | effect of a larger region |
|---|---|---|
| `constraints/platform.hold_sets` → `frontage_hold_rows` | `plateau_vertices` (ref mark) less `foreign` (taxi/runway/rigid faces) | more hard rows on the datum column; taxiway-edge vertices stay the taxiway's |
| `constraints/no_step` (606, 733, 926) | `HELD[b]["plateau_vertices"]` for the interval / pair graph | the interval reads more contacts (§57 (3) J3 is NOT built: bands withdrawn, `reach_isect` None) |
| `planar/overlay` 827–835 | `PLATEAU_MARK` in ref: never absorbs a plateau face | more faces kept apart |
| `planar/pad_sliver` (`_dissolve_rest_slivers`, `_enclosed_rests_to_plateau`) | rest parts vs pieces | same rule on more rests |
| `pipeline/publication._plateau_rings` → sidecar `plateau_rings`; `emit/osm_adapter` key list | the vertex set | larger key |
| `tools/check_grade` / `harness/law_support/grade_law.py` (`pad_airside_renode` outside `plateau_rings`) | the sidecar key | same census |
| `constraints/platform.platform_records` → sidecar `platforms[].plateau_*`, `stand_zone_source` | counts | `stand_zone_source` would carry a new token |
| object stage (`pad_block_seat`, `footprint_seats`, `placement_*`) — lane kclt608's files | the `building` faces and the graded z under feet; NOT the plateau mark | none (a plateau is role `apron`) |
| `airport/riders.riders_for_dump` | `provenance.jetway_strips` (EMPTY on a held block: the strip is disarmed, P12) | none |

Emittable in a heightfield: a plateau is apron faces at one z meeting their
neighbours over the apron's own cap rows — the same class as today's
plateaus (KSEA 7 at 3.6k–62k m²), nothing new in kind.

## STEP 1/2 — the arms (same-tree replay pairs of `jetbay/KSEA.pkl`, `--from planar --emit --verify`)

ARM 1 (foundation rule only): door ramps 83 → 1, released contacts 21 → 0 —
but the SAME jetways then read as 12 m PITS (68 `basin_floor` faces as
`tunnel_trench`, anchors 11.8 m under the apron): the SAM wheel strut (animated,
authored to −11 m) became the basin reader's floor plate; #551's standing
witness does not hold it (the deepest plate is a 0.1 m column, roofed 0). The
parser knows nothing of animation → RULE A: `obj8` marks solid triangles inside
`ANIM_begin/ANIM_end`, `Component.animated`, `ResourceCache.genuine` and the
basin loop skip them (a moving part never witnesses terrain). SAM jetway: 271
of 276 components animated; the probe then reads 0 basin witnesses, 0 wells.
Commits 8a626b3d5 (rule F + tool) and 793c1dd39 (rule A); twins: door 11
(+2 new), wells551 / m4b / v2basinfix / pardoors, objsplit / leafframe /
objcut / partextend / witnessvalid / tunnel_objects / doorwellperf — 59 + 253
pass; ratchets PASS (duplicate + layer).

ARM 2 (both rules) vs base — spec §65 (3) carries the full numbers: door
ramps 83 → 1, pits 0, released contacts 21 → 0, the four warnings GONE, the
complex at one level 117.68 (building8 +3.3 m, building9 +2.6, building7 +1.1,
building13 −1.3, building2 +2.6), adjudicated airside census 1,232 → 895
(hard_conflict 247 → 0, pad_frontage_* 8 → 0, pavement_over_road_cap 26 → 0,
ramp_in_strip 37 → 0), runway movers 13 / worst 0.060 m, taxi 417 / 2.70 m
and strip 285 / 2.35 m at the complex. Jetways: anchors apron 46 / building
34 / off-face 1; forward 25 m within −0.48…+0.06 m on all 81; anchor − level
> 0.3 on 13 (all building16: it went from a HELD flat block at 122.00 to a
TILTED platform 1.27 % at 120.83, residual 0.485 — a seat question for
kclt608's domain); disc > 0.3 above: 17 (worst +1.61), below: 19 (−0.48).
Residual points are `junction` cells (KSEA's one-polygon pavement `pav1`
classified taxi family under the stands; `plateau_cut` cuts apron only).
§57's bay would fill NOTHING there. Options O1/O2/O3 in §65 (3) — STOP for
the owner on the bay; rules F and A ship as the #612 fix.

Shared-file note for kclt608: this lane touched `airport/obj8.py` (parser +
Component + genuine), `airport/door_wells.py` (one refusal), `tools/
seat_feet_census.py`, `tests/auto_patch_v2/test_v2doorramp.py`, spec §65 —
NOT cluster_pad / pad_block_seat / footprint_seats / platform.

## CLOSING (RESUME HERE: done; the bay decision is the owner's)

Closing KSEA harness build `KSEA_20261012T183132` on 1b3ac42b5: rc 0, 314.5 s;
IDENTICAL to arm2 (door ramps 1, pits 0, released 0, warnings 0, census
adjudicated airside 895, runway 13 / 0.060 m, jetways: anchors apron 46 /
building 34, forward −0.48…+0.06 m on all 81, 13 anchors off level all on
building16's tilted platform). Frames registered: STEP 0 patch/graded/rebake
(a11299a48), capture `frames/jetbay612/KSEA.pkl`, closing patch/graded
(1b3ac42b5). OTHH same-tree pair (pads67 capture, --from planar): 10 basins
identical, 4 door ramps, 0 movers at 0.01 m in all three frames (21,698 /
10,190 / 1,060 common nodes). HECA: 0 door ramps on sw17 — unchanged by
construction (no replay run).
