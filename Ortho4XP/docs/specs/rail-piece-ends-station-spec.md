# Rail piece ends, deep tunnels and the buried station (#1738, #1739)

Law: RULINGS 2026-11-03b (6), Q345 a: "a deep mapped tunnel is never opened;
rail is open only where a pack trench or station object, or the lidar, shows
an open cut; the buried station (ENGM #1739) gets its own cut or lower pad".
Also 2026-10-27z (a fenced tunnel needs a witness), 2026-10-29a Q287/Q298,
2026-10-30f (structures are read before the solve), 11-03b (1)-(5) (the
two-level model). Per 11-03b (8) this round stops before code: the section
views below are for the owner's yes.

ENGM is where the defects were seen and is the closing test. Every rule below
reads geometry, tags and objects only; none names an airport (RULINGS 05e).

Status: SPEC, awaiting the owner's yes on the section views (lane `b1738`).

## 1. Sites (current build, then planned)

Current = stage replay of main `5544d956` (capture `ENGM.pkl`, `--from
planar --emit`). Its rail ramps are the same as the owner's 2026-11-01 build
(`Patches/+60+010/+60+011/ENGM_auto.patch.osm`). Planned = the same replay
with rules R1, R2 and R4 applied as a scratch arm. R3 (the station) is drawn
from the station object's own levels. Heights are metres MSL at the owner's
point. Landmarks: the station is under the terminal forecourt. The rail
tunnel runs north from it under the central pier, between the two runways.

| Site | Where | DEM | Current | Planned | What cuts it now |
|---|---|---|---|---|---|
| S1 60.198815, 11.100162 | rail line, 670 m N of the station, N end of the central pier | 204.09 | **197.92** (6.2 m trench) | 204.08 | `tunnel:-3643+-3642@0`: two branch pieces' switch ends, merged as a "dual" |
| S2 60.197995, 11.099484 | rail line, 580 m N of the station | 204.06 | **198.04** | 204.44 | `tunnel:-3640@0`: branch piece's switch end |
| S3 60.195686, 11.098786 | rail line, 325 m N of the station | 204.50 | **199.04** | 204.38 | `tunnel:-3644@0`: branch piece's switch end |
| S4 60.195564, 11.097703 | rail line, 310 m N of the station, 60 m W of S3 | 204.52 | **197.94** | 204.58 (see Q-C) | `tunnel:-3645@0`: branch piece's switch end |
| S5 60.193092, 11.108285 | E end of the terminal front, on the airside service road into the terminal | 204.99 | **201.25** | 204.13 | `tunnel-object:T1_13.obj@0`: a terminal part read as a tunnel wall object |
| Station 60.192763, 11.096594 (#1739) | under the terminal forecourt | 202.45 | **204.13** (pad over the station; its roof deck 203.65 is 0.5 m under it) | **195.11** lower pad | nothing lowers it: the station sits inside held pad `building24` |

Section views (scratch, `…/scratchpad/b1738/`): `sec_S{1..5}_across.png`,
`sec_S{1..5}_along.png`, `sec_ST_along.png`, `sec_ST_across.png`, plus the R2
consequences `sec_C1_north_portal.png` and `sec_C2_rail_underpass.png`.

In the arm, the built tunnels go from 22 to 9 (`tunnel_ramp` ways 23 to 10).
No rail ramp remains, and T1_13's corridor is gone. One mouth appears that the base hid:
`tunnel:-766@1`, Q-C.

## 2. Mechanisms (file:line on `5544d956`)

**M1, S1 to S4: a switch reads as a portal.** OSM maps the station's four
tracks as 25 `railway=rail tunnel=yes layer=-2` pieces, split at every switch.
At a switch the branch piece ENDS on an INTERIOR node of the through piece.
There are six such ends: `-3645`@-59649 on `-784`, `-3644`@-59648 on `-3637`,
`-3643`@-59641 on `-784`, `-3642`@-59640 on `-2134`, `-3641`@-59642 on `-1717`
and `-3640`@-59643 on `-786`.

- `structure_approach.chains` (`planar/structure_approach.py:183-222`) joins
  pieces only where exactly two ENDS meet.
- `bore_continuation.tunnel_ends` (`planar/bore_continuation.py:34-43`)
  indexes only way END nodes.
- `structure_approach.approach` (`:225-300`) walks only non-tunnel ways, so at
  a switch it finds nothing and makes a straight extension (walked 0 m).
- So `continues_underground` (`bore_continuation.py:67-89`) sees no tunnel at
  the end. The end becomes a `Mouth` at `structure_approach.py:814-822`.
- The bore is admitted by `terrain_tunnel_witness`
  (`planar/structure_service.py:231`: layer -2; also taxiways crossing over
  it). A full rail ramp (7.5 m mouth, 1.25 %) is then built out along the
  straight extension, over the tunnel itself.
- Ends that share an END node (the other 18 switch ends) are already refused
  by #1028's test. The T-ends are the only gap.
- `-3641@0` was refused only because its corridor overlaps `-3640@0`.

**M2, S5: a terminal part read as a tunnel wall.** `Airport/Main_Terminal/
T1_13.obj` has no solid below its seat. `tunnel_objects.signature`
(`airport/tunnel_objects.py:368-402`) takes the shallow-seat branch:

- no full skirt, so the crest is the topmost bin of at least 100 m², which is
  its roof band at +23.86 m;
- `edge_skirt` = 23.86 ≥ 1.5, so it is an EDGE WALL.

Bore `-1360`'s end (an airside `service` road, layer -1) lies within
`bore_end_tolerance_m` of the "plate". So the object becomes that bore's mouth
(object precedence, `planar/structures.py:292`), and a corridor 132 × 29.7 m
is cut to `mouth_depth_m` (7.5 m) inside the terminal. The OSM bore alone is
refused by §34 (12) (5) (a) ("ENTERS A PACK BUILDING … T1_13 stands 23.9 m
over its zero", `structure_service.py:184-202`), but the object path runs
first. The same reading re-seats T1_13 by its "crest" (`[ENGM] re-seated crest
+23.86`): it is an object-stage consequence, listed in §6.

**M3, the station: no reading lowers it.** The station is pack object
`T1_18.obj` (unit 7, every terminal part on one anchor):

- a roof deck at y −0.18 (5,284 m² up-facing at 201.50 authored);
- platform canopies at y +0.6;
- walls and columns standing on a FEET plane at y −8.72 (969 vertices;
  base-profile verdict `feet`, `feet_y` −8.7228);
- no floor plate: the pack expects the terrain to be the track bed.

Seated with its group (owner build: body `b10`, zero 203.83 m), that puts the
roof deck at 203.65 and the feet at **195.11**. The DEM south of the station
already shows the open rail cut at 196 to 198 m.

The station lies inside held pad `building24` (204.13 m, flat), so the whole
station volume is under the pad. This is the owner's "buried". South of the
pad the current surface drops 6.5 m as a cliff to the DEM cut.

Three readings could have lowered it, and none fires:

- `planar/covered_cut.plan_covered` (the LFLL station's lower pad, #1333 R2)
  is asked only where `covered_corridors` (`covered_cut.py:87-93`, reading
  `classify/pad_cut_corridor.cutting_corridors`) finds a cutting mapped
  `covered=yes` / `tunnel=building_passage`. ENGM maps the station tracks as
  plain `railway=rail` (south half) and `tunnel=yes layer=-2` (north half).
- `plan_low` refuses: the unit is not read STEPPED over this pad.
- The four rail mouths at the station's north end are refused "against
  building pad building19". That is correct under Q345, since this is a deep
  tunnel.

## 3. Rules

**R1. A tunnel end on another tunnel way is no portal.** A mapped tunnel way's
end continues underground when its node lies on ANY other admitted tunnel way,
at that way's end (today) or at an INTERIOR node (a switch drawn on the
through piece).

- `tunnel_ends` indexes every interior node of a tunnel way as two directed
  continuations, `(w, p_i, p_{i+1})` and `(w, p_i, p_{i-1})`. The turn cap
  (`approach_turn_max_deg`) and the shortest-ramp test stay as they are.
- `airport/portal_witness.mapped_mouths` (`:47-59`, its own end-to-end join at
  `_JOIN_M` = 2 m) reads the same index instead, so the witness tool and the
  build agree on what a mouth is.
- One derivation site, no new law key.

**R2. A rail end, or a deep end, needs a portal witness (Q345).**

- **(a) Deep.** An end of a bore whose lowest `layer` is at or under `[tunnel]
  deep_layer_max` (new key, −2: OSM's statement that it runs under something
  already below grade) is never opened where its approach walks no mapped way
  (`walked_m` = 0: no road or rail comes out there). Ends whose way surfaces
  keep today's tests.
- **(b) Rail.** An end of a bore any of whose ways carries `railway` is a mouth
  only where a portal witness stands AT THAT END:
  1. a pack tunnel or trench object takes the mouth (object precedence, or
     `airport/trench_objects`), or a pack part stands below grade there
     (`structure_fence._Portals.near`, 27z witness 3, read per end);
  2. a station level (R3) holds the end;
  3. a credible lidar inset reads an open cut there (`structure_fence.
     _LidarCut`, 27z witness 5; `channel_geometry._lidar_cut`).

  With none, the end is not opened: no ramp, no trench, and the rail beyond is
  graded like ground. The refusal is named in `stats.refused`, as #1028's are.
- One site: a sibling of `continues_underground` in `planar/
  bore_continuation.py`, called where it is (`structure_approach.py:820`).
- Rail ramp grades stay 28k R5's. The shortest-ramp test in
  `continues_underground` today divides by the ROAD cap (75 m) for rail as
  well. It reads `rail_ramp_max_grade` for a rail bore (214 m). This is the
  same law at its rail value.

**R3. The station's own lower pad.** A mapped railway (any way: open,
`tunnel`, `covered`) running under a HELD pad is offered to `plan_covered` as
a covered corridor, beside the tagged covered cuttings
(`covered_cut.covered_corridors` gains `rail_under_pads`, the one reading).
The objects then decide, by `plan_covered`'s existing tests: the unit's parts
along the reach must stand at least two plane bands (a storey, 23c) under the
block's top level `t`. At ENGM, T1_18's feet plane is y −8.72 against `t` ≈ 0.

- The level is the lower parts' footprint inside the reach. It is minted
  `<block>/p1` (`witness = station_floor`) at D + plane (27h: the densest 1 m
  plane of the lower parts' walled feet) = **195.11 m**.
- Its rim is a vertical riser at the object's walls (Q341, the existing
  `#strip`).
- It ends at the object's wall where the rail goes on as a deep tunnel (R2 (a):
  never opened). It runs out (#1333 R3, `planar/cut_runout`) where the rail
  leaves the pad open: at 1.25 %, it meets the DEM's cut about 105 m south of
  the station's south wall.
- A rail-under-pad corridor that `plan_covered` refuses is NOT trimmed
  (`covered_cut.trim_uncut` keeps to tagged covered cuttings). A deep tunnel
  under a pad with no station stays buried.

**R4. A building's wall is not a tunnel edge wall.** In `tunnel_objects.
signature`'s shallow-seat branch, an edge wall whose walls stand more than
`[tunnel] mouth_depth_m` (7.5 m, a tunnel's own depth) from crest to lowest
solid is refused by name ("a building's wall, not a tunnel edge wall"). LEMD
`Bridge4.obj` (2.02 m) and OTHH's edge walls are well under it. The bore it
would have taken then meets §34 (12) (5) (a) on its own: `-1360` enters
T1_13, so it is not built.

## 4. Consumer census (RULINGS 2026-08-30l)

| Pass (module) | Reads | Before | After | Rule |
|---|---|---|---|---|
| `planar/bore_continuation.tunnel_ends` → `continues_underground` (`structure_approach.mouths`) | tunnel way nodes | ends only | ends + interior nodes | R1 |
| `airport/portal_witness.mapped_mouths` (`--witness` dry read) | tunnel way ends | own 2 m end join | the shared index | R1 |
| `structure_approach.mouths` admission | bore ends | rail ends open by default | rail ends need witness; deep ends need a surfacing way | R2 |
| `structure_fence._Portals` / `_LidarCut` | pack below-grade parts, lidar | per BORE (27z) | also asked per END for rail | R2 (b) |
| `structures.py:292` object precedence, `apply_plates` | mouths | unchanged | unchanged (an object-taken mouth is a witness) | R2 (b) 1 |
| `structure_service.terrain_tunnel_witness` | bores | unchanged | unchanged (admission stays per bore; R2 is per end) | — |
| `merge_duals`, overlap tie-breaks (`unframed_ramp.overlap_*`) | mouths | a false rail ramp masked `-766@1` | fewer mouths; `-766@1` unmasked | Q-C |
| `classify/pad_cut_corridor.trim_cut_corridors` | cutting corridors | open + covered tags | unchanged (rail-under-pad is not a cutting) | R3 |
| `planar/covered_cut.covered_corridors` / `plan_covered` | covered corridors under held pads | tagged cuttings only | + rail ways under held pads | R3 |
| `planar/covered_cut.trim_uncut` | covered corridors | trims uncut tagged cuttings | unchanged: never trims a rail-under-pad corridor | R3 |
| `planar/low_level.low_level_split` order | held pads | `plan_covered` → `plan_low` → `group_low` | unchanged order | R3 |
| `planar/low_extent.extend_levels` | `low_level` records | skips `covered_cut` | also skips `station_floor` | R3 |
| `planar/cut_runout`, `landing.landing_cut`, `constraints/ramp_runout` | the level's ring, rail ways | LFLL only | the station's south end | R3 |
| `constraints/platform.landing_rows` | `low_level` records | rigid at D + y | unchanged consumer | R3 |
| `airport/placement_read` (object stage) | level under the block's plane | — | the station stays seated with its group (zero 203.83) | R3 |
| `airport/tunnel_objects.signature` → `read_corridors` → `pack_reads` | resources | T1_13 a corridor | refused | R4 |
| re-seat of tunnel-object families (`[tunnel.object] reseat`) | corridors | T1_13 re-seated by crest +23.86 | not a corridor, not re-seated | R4 |
| census `check_grade` families on `tunnel_ramp` / `tunnel_trench` | emitted roles | 23 ramps + 2 trench | 10 ramps + 2 trench | — |

Emittability: R1, R2 and R4 only remove structures. R3 is a flat pad with its
existing riser strip and run-out, the same heightfield shapes as LFLL's.

## 5. Owner questions (asked with the section views)

- **Q-A (R2 (b) consequence, `sec_C1_north_portal.png`).** The OSM rail
  surfaces north of the pier at 60.2008, 11.1013. The coarse DEM (Copernicus,
  not lidar) shows a 5 to 6 m open cut there for about 500 m. Read literally,
  Q345 closes it, so the planned ground is graded at 203 to 205 m over the
  cut. (a) Literal: closed. (b) Recommended: a DEM cut at least `mouth_depth_m`
  deep along the approach, on any DEM class, is also a rail witness. The four
  rail underpasses 2 to 6 km out (`-1269/-1268`, `-1166/-1164`,
  `-1163/-1161`, `-790/-221`, layer −1) lose their cuts under both answers.
  Their DEM shows the rail at grade under road embankments
  (`sec_C2_rail_underpass.png`).
- **Q-B (R3 depth).** The planned station level is 195.11 m, the objects'
  feet plane, 9 m under the forecourt. The DEM cut south of the station floors
  at 196 to 198 m. (a) Recommended: the feet plane (Q344: objects first).
  (b) Only open the 0.5 m between the pad and the roof deck (the tracks stay
  buried).
- **Q-C (S4, `sec_S4_along.png`).** With the false rail ramp gone, the
  airside service tunnel `-766` (layer −1, 88 m, under the terminal's airside
  face, both ends on service road `-333`) builds its west mouth's 168 m ramp
  6 m from S4. Before, only the overlap with the false rail ramp refused it.
  Is there a road tunnel portal there? (a) Yes, build it. (b) No: the road
  passes under the terminal's overhang at grade (§34 (12) (5) (e)), and the
  part-at-grade test needs reading per part for a pack authored as one-anchor
  monoliths. Without (b) the owner's "no tunnel at S4" is not met.

## 6. Not in this round

- The object stage's re-seat of T1_13 by +23.86 m (M2) goes away with R4. No
  other object is checked here.
- The 18 other `#1028` switch-end refusals are unchanged.
- No five-airport census is run in a lane. Before landing, R2 (b) is
  censused over the registered captures with rail bores (LFPG, LFLL, EDDF,
  LEMD, KCLT if present): every rail mouth that loses its ramp, by witness.

## 7. Closing test

One ENGM build (`tools/harness/build_airport.py ENGM`). Pass when:

- S1 to S5 show no cut (S4 as Q-C rules);
- the station's lower pad is at the Q-B level, with the cut running in from
  the south;
- no new `tunnel_ramp` / `tunnel_trench` rows appear elsewhere;
- the census is not worse than base except for the lawful station level.
