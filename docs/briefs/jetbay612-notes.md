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
