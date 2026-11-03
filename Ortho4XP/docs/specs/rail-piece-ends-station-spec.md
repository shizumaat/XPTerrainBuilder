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

Status: SPEC v2, awaiting the owner's yes on the section views (lane `b1738`).
v2 (owner 2026-11-03T05:42:24Z: "Look at the package provided ENGM mesh, that will
tell you exactly what the developer intended") adds the developer mesh to every
view, compares it per site (§1b) and revises R2's witness, R3's open question
and Q-A/Q-C from it.

## 1. Sites (current build, then planned)

Current = stage replay of main `5544d956` (capture `ENGM.pkl`, `--from
planar --emit`). Its rail ramps are the same as the owner's 2026-11-01 build
(`Patches/+60+010/+60+011/ENGM_auto.patch.osm`). Planned = the same replay
with rules R1, R2 and R4 applied as a scratch arm. R3 (the station) is drawn
from the station object's own levels. Heights are metres MSL at the owner's
point. Landmarks: the station is under the terminal forecourt. The rail
tunnel runs north from it under the central pier, between the two runways.

| Site | Where | DEM | Current | Planned | Developer mesh (as authored / at our datum) | What cuts it now |
|---|---|---|---|---|---|---|
| S1 60.198815, 11.100162 | rail line, 670 m N of the station, N end of the central pier | 204.09 | **197.92** (6.2 m trench) | 204.08 | 207.0 / 204.13 | `tunnel:-3643+-3642@0`: two branch pieces' switch ends, merged as a "dual" |
| S2 60.197995, 11.099484 | rail line, 580 m N of the station | 204.06 | **198.04** | 204.44 | 207.0 / 204.13 | `tunnel:-3640@0`: branch piece's switch end |
| S3 60.195686, 11.098786 | rail line, 325 m N of the station | 204.50 | **199.04** | 204.38 | 207.0 / 204.13 | `tunnel:-3644@0`: branch piece's switch end |
| S4 60.195564, 11.097703 | rail line, 310 m N of the station, 60 m W of S3 | 204.52 | **197.94** | 204.58 (see Q-C) | 207.0 / 204.13 | `tunnel:-3645@0`: branch piece's switch end |
| S5 60.193092, 11.108285 | E end of the terminal front, on the airside service road into the terminal | 204.99 | **201.25** | 204.13 | 207.0 / 204.13 | `tunnel-object:T1_13.obj@0`: a terminal part read as a tunnel wall object |
| Station 60.192763, 11.096594 (#1739) | under the terminal forecourt | 202.45 | **204.13** (pad over the station; its roof deck 203.65 is 0.5 m under it) | **195.11** lower pad | **192.0 / 189.13** | nothing lowers it: the station sits inside held pad `building24` |

Section views (scratch, `…/scratchpad/b1738/`): `sec_S{1..5}_across.png`,
`sec_S{1..5}_along.png`, `sec_ST_along.png`, `sec_ST_across.png`, plus the R2
consequences `sec_C1_north_portal.png` and `sec_C2_rail_underpass.png`. Every view
carries the developer mesh twice: as authored (orange) and moved to our airside
datum (orange dashed). Plan of the developer mesh: `plan_devmesh.png`.

In the arm, the built tunnels go from 22 to 9 (`tunnel_ramp` ways 23 to 10).
No rail ramp remains, and T1_13's corridor is gone. One mouth appears that the base hid:
`tunnel:-766@1`, Q-C.

## 1b. The developer mesh (v2)

**What it is.** `zzz_Aerosoft - ENGM Gardermoen - Mesh/Earth nav data/+60+010/+60+011.dsf`
is read with the existing reader (`auto_patch/dsf_reader.ensure_dsf_text_path`,
dumped into the lane scratch, never into the pack). It is triangulated exactly
(`O4_Default_Terrain_Map._primitive_triangles`), and each vertex takes its own
elevation or, where it carries the sentinel −32768, the DSF's 1201² elevation
raster (rows stored south first). Scratch reader: `scripts/devmesh.py`.

- The airport is a FLAT plane at **207.0 m** (the field elevation; vertex z is
  quantised to 1 m).
- Our graded airside sits at 204.13 (terminal pad), so the views shift the mesh
  by **−2.87 m** to compare depths.
- Inside the airport, it cuts in exactly three places:
  - the **station slot**: floor 192.0, vertical sides, from the station's
    north wall (60.1933) to 60.1885, about 590 m, then a wall back up to 207
    by 60.1875;
  - the **north portal box**: floor 197.0, from 60.2009 to 60.2025 (about
    160 m, the rail and `-742`'s mouth both inside), then a vertical wall back
    up to 207;
  - a 192.0 hole at 60.1988-60.1993, 11.1005-11.1009, beside `Ham1.obj`.
- Every other mapped tunnel mouth is flat in it. That covers the false rail
  ramps, `-766`, `-1216`, T1_13, and the sunken roads `T1_9` / `T1__17`.
- Caveat: the mesh is AEROSOFT's product. The objects are TAIMODELS'
  (`c_NOR - 100_airport - ENGM Oslo (Taimodels)`), a different developer. It
  states one developer's intent for the ground, not necessarily the ground
  these objects were authored over.

**Per site, at the owner's point** (developer at our datum = as authored − 2.87):

| Site | Current | Planned | Developer (our datum) | Planned − developer | Verdict |
|---|---|---|---|---|---|
| S1 | 197.92 | 204.08 | 204.13 | −0.05 | agrees: no cut |
| S2 | 198.04 | 204.44 | 204.13 | +0.31 | agrees: no cut |
| S3 | 199.04 | 204.38 | 204.13 | +0.25 | agrees at the point. The planned `-766` ramp 35 m away is flat in the mesh (Q-C) |
| S4 | 197.94 | 204.58 | 204.13 | +0.45 | agrees at the point. The planned `-766` ramp edge 6 m away is flat in the mesh (Q-C) |
| S5 | 201.25 | 204.13 | 204.13 | 0.00 | agrees: no cut |
| Station | 204.13 | 195.11 | 189.13 | **+5.98** | open in both; the developer is 6 m deeper |
| C1 north portal (floor) | 195.63 at the mouth, ramp 552 m | 194.10 under Ham3, run-out about 610 m | 194.13, box 160 m | −0.03 at the floor | agrees at the floor; the developer has no run-out |
| C2 rail underpass | 201.66 (7.5 m ramp) | 208.97 (DEM) | 208.47 (outside the flat field, no shift) | +0.50 | agrees: no cut |

**Where planned and developer differ by more than 0.5 m, why, and the rule that
would close it:**

1. **Station depth (+5.98 m).** The developer's slot floor is 15.0 m under its
   field. Our level is the station object's feet plane, 8.72 m under its zero.
   No Taimodels object along the reach goes deeper: T1_18 feet y −8.72, the
   T1_18 south bodies y −8.55, `concrete.obj` −10.68. Seated on the
   developer's own field (zero 207), T1_18's walls would stand 6.3 m above
   its slot floor. The slot belongs to Aerosoft's station, not to these
   objects.
   - Rule that closes it: **R6 below** (a companion mesh's below-grade region
     is a depth witness, senior to the objects).
   - Against it: it would hang this pack's station 6 m in the air. The
     objects-first ladder (Q344) keeps 195.11. Owner question Q-B v2.
2. **Station slot length (south of the station).**
   - Developer: constant depth for 590 m, then a near-vertical wall (15 m over
     about 110 m).
   - Planned: a 1.25 % run-out meets the DEM's natural cut (196 to 197 m)
     about 105 m south, and the rail then follows the DEM cut. That cut is
     7 to 8 m deep and reaches 60.186 in the DEM.
   - Q342 (constant depth where no object sets it) would give the
     developer's shape, if the region ran on until the rail "climbs back to
     natural ground". Here natural ground is the DEM cut itself, so the two
     readings meet once the depth matches (item 1).
3. **North portal extent (beyond 60.2025).** The developer box ends in a
   10 m vertical wall back up to the field. The planned run-out climbs at
   1.25 % for about 610 m to the DEM.
   - A rail cannot climb a wall, so the developer's wall is a simplification
     we do not copy.
   - No rule change is proposed; the disagreement is reported. The floor
     itself agrees within 0.03 m.
4. **Planned `-766` west ramp (near S3/S4, up to 7.2 m).** The developer has
   no cut there. This answers Q-C as (b). The general rule that closes it is
   R2 (c) below.

Other mouths where the mesh disagrees with the CURRENT build (not owner sites,
reported for the next round):

| Mouth | Current depth | Developer |
|---|---|---|
| `-1216@0` (60.1949, 11.0937, service) | 12 m ramp, 4.9 m deep | flat |
| `Ham1.obj` corridor (`-742`'s object) | 5.3 m deep along 103 m | flat on our corridor; a 192 hole 30 m west of it |
| sunken roads `T1_9` / `T1__17` | 2.6 / 1.3 m | flat |
| motorway underpass `-165/-163` | 7.5 m | a 2-3 m dip |
| service `-1152` | 7.5 m | about 0.4 m |

R2 (c) closes the service ones inside the fence. The rest need the object
readers' own round.

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

  v2: the north portal HAS witness 1. `Airport/Tunnel/Ham3.obj` is a pack
  hard deck (flag), lowest solid 194.10 m (8.5 m under its anchor). Its
  footprint (60.20079-60.20124, 11.10089-11.10279) contains the merged mouth
  (60.20088, 11.10128). The v1 arm refused every rail end without asking
  for this witness, which is why v1's C1 view showed the portal closed. Under
  this R2 it opens at the deck's bottom:
  - 194.10 against the developer's 197 − 2.87 = 194.13;
  - under the deck and in front of the mouth (Q340 "the floor in front of
    tunnel mouths", "ground under hard-deck bridges");
  - with a vertical step at the tunnel side (Q341);
  - a rail run-out on the open side.

  The rail under a hard deck is not bored today: `deck_bores` takes
  `structure_underpass.bore_roads`, highways only. R2 (b) 1 reads the deck as
  the rail's witness, and `deck_bores` takes railway ways too. This is one
  reading, `bore_roads` gaining rail (census row added in §4).

  With none, the end is not opened: no ramp, no trench, and the rail beyond is
  graded like ground. The refusal is named in `stats.refused`, as #1028's are.
- **(c) v2, a fenced service bore needs a portal witness too.** The developer
  mesh opens only the mouths that a pack object or the station states. Inside
  the airport boundary, a `service` bore end (the airside service tunnels:
  `-766`, `-1216`, `-1152`, `-1360`) takes R2 (b)'s per-END witness list.
  27z's per-BORE witnesses (cover, crossing, rise) admit the bore as a tunnel
  but no longer open its ends. This narrows 27z, so it needs the owner's word:
  **Q-C v2**.
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

**R6 (proposed, Q-D). A companion terrain mesh is a witness.** A scenery pack
other than the airport pack can carry physical terrain patches with explicit
vertex elevations inside the airport boundary, i.e. a developer mesh. Where it
does, its below-grade regions are read before the solve. Their outline and
depth under the mesh's own field level (the mesh's modal airside elevation) are
a witness of where the ground is open and how deep: an open cut where it cuts,
closed where it is flat. It ranks with the pack's objects in Q344's ladder. No
pack name and no airport literal is involved: the reader asks "which installed
DSF covers this tile with explicit elevations inside this boundary", reusing
`dsf_reader.ensure_dsf_text_path` and `_primitive_triangles`.
- At ENGM it matches the planned surface at S1 to S5, C1's floor and C2.
- It disagrees at the station's depth (§1b item 1), because the mesh and the
  objects come from two vendors.

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
| `planar/structure_underpass.bore_roads` → `deck_bores` | mapped ways under a hard deck | highways only | + railway (a deck over rail bores it) | R2 (b) 1 v2 |
| `planar/structure_service.terrain_tunnel_witness` + per-end witness | fenced `service` bores | admitted bore opens both ends | each end needs R2 (b)'s witness | R2 (c), Q-C v2 |
| new companion-mesh reader (`airport/`, one module) | an installed terrain DSF over the tile | — | below-grade regions as witnesses | R6, Q-D |
| `airport/tunnel_objects.signature` → `read_corridors` → `pack_reads` | resources | T1_13 a corridor | refused | R4 |
| re-seat of tunnel-object families (`[tunnel.object] reseat`) | corridors | T1_13 re-seated by crest +23.86 | not a corridor, not re-seated | R4 |
| census `check_grade` families on `tunnel_ramp` / `tunnel_trench` | emitted roles | 23 ramps + 2 trench | 10 ramps + 2 trench | — |

Emittability: R1, R2 and R4 only remove structures. R3 is a flat pad with its
existing riser strip and run-out, the same heightfield shapes as LFLL's.

## 5. Owner questions (asked with the section views)

- **Q-A: ANSWERED BY THE PACK (v2).** Ham3.obj is the north portal's witness. The
  portal opens at the deck's bottom, which matches the developer mesh's floor
  within 0.03 m. What was asked in v1 is kept for the record:
  **Q-A v1 (R2 (b) consequence, `sec_C1_north_portal.png`).** The OSM rail
  surfaces north of the pier at 60.2008, 11.1013. The coarse DEM (Copernicus,
  not lidar) shows a 5 to 6 m open cut there for about 500 m. Read literally,
  Q345 closes it, so the planned ground is graded at 203 to 205 m over the
  cut. (a) Literal: closed. (b) Recommended: a DEM cut at least `mouth_depth_m`
  deep along the approach, on any DEM class, is also a rail witness. The four
  rail underpasses 2 to 6 km out (`-1269/-1268`, `-1166/-1164`,
  `-1163/-1161`, `-790/-221`, layer −1) lose their cuts under both answers.
  Their DEM shows the rail at grade under road embankments
  (`sec_C2_rail_underpass.png`).
- **Q-B v2 (R3 depth).** The developer mesh's slot is 15 m deep (189.13 at our
  datum), 6 m deeper than the objects' feet. (a) Recommended: the objects'
  feet, 195.11. The developer mesh is another vendor's, and matching it would
  hang T1_18 6.3 m above the ground. (b) The developer mesh's depth (R6). v1's
  text follows:
  **Q-B v1.** The planned station level is 195.11 m, the objects'
  feet plane, 9 m under the forecourt. The DEM cut south of the station floors
  at 196 to 198 m. (a) Recommended: the feet plane (Q344: objects first).
  (b) Only open the 0.5 m between the pad and the roof deck (the tracks stay
  buried).
- **Q-C v2.** The developer mesh is flat over `-766`'s planned west ramp, and
  over every airside service mouth. Recommended: R2 (c), where a fenced
  `service` bore end needs a per-end portal witness. This narrows 27z. Yes or
  no? v1's text follows:
  **Q-C v1 (S4, `sec_S4_along.png`).** With the false rail ramp gone, the
  airside service tunnel `-766` (layer −1, 88 m, under the terminal's airside
  face, both ends on service road `-333`) builds its west mouth's 168 m ramp
  6 m from S4. Before, only the overlap with the false rail ramp refused it.
  Is there a road tunnel portal there? (a) Yes, build it. (b) No: the road
  passes under the terminal's overhang at grade (§34 (12) (5) (e)), and the
  part-at-grade test needs reading per part for a pack authored as one-anchor
  monoliths. Without (b) the owner's "no tunnel at S4" is not met.

- **Q-D (R6).** Should an installed companion terrain mesh over the tile be
  read as a witness of cuts (outline and depth under its own field)? It
  matches 7 of 8 views at ENGM. It disagrees only where its vendor's station
  differs from the pack's.

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

## 8. Implementation (owner's yes, 2026-11-03T06:07:15Z)

Answers: (1) the planned levels; (2) the station floor at the objects' own
wall feet; (3) R2 (c); (4) R6, below the objects in the ladder.

- **R1**: `planar/bore_continuation.tunnel_ends` indexes interior nodes; the
  shortest-ramp test reads the rail cap for a rail bore;
  `airport/portal_witness.mapped_mouths` joins on every node.
- **R2**: `planar/end_witness` (`needs_witness`, `EndWitness`), asked in
  `structure_approach.mouths` AFTER the bore's own admission (§34 (12) (5)
  keeps naming a bore that is no tunnel). Deep = `[tunnel] deep_layer_max`
  (−2), only where no mapped way comes out of the end.
  `structure_fence._Portals.at_end` is the per-end form of witness 3.
- **R3**: `planar/station_level.station_split`. A station's pad is not
  itself a held block (MEASURED ENGM: `building19#1`), so its level
  (`plan_covered` in its station form, `covered_cut.station_corridors`) is
  registered as a `low_level` landing of the nearest held block on the same
  pack unit (`building24/p1`, y −8.70 against its top). `level_cut`
  `whole=True` lets the pad become the level entire. The tagged-cutting
  path is unchanged. A held-pad station path was tried and DROPPED: at
  LEMD it minted an 18,292 m² level 2.2 m down under `building52`, which no
  owner site asked for.
- **R4**: `airport/tunnel_objects.signature`, shallow-seat branch.
- **R5**: `structure_underpass.bore_roads(rail=True)` at the two hard-deck
  readers (`deck_bores`, `deck_bridge._roads_under`).
- **R6**: `airport/terrain_mesh_witness`.
  - Candidates come from `airport/companion._candidates`, screened by
    `dsf_commands.header_properties` (no overlay, not this engine's own
    DSF).
  - The pre-build refresh dumps them (`engine_v2._fresh_mesh_dumps`); load
    reads the dump (`pipeline/build.pack_stage`, `Airport.terrain_mesh`).
  - A cut needs a rim the depth higher within 10 m and a mean width of at
    most 150 m.
  - It is a per-end WITNESS only. It does not set a depth yet (objects
    first; no ENGM site needed it).

Deviations from the planned views:
- The station's south end has no run-out. The DEM's cut just south stands
  above the level, and `cut_runout` never climbs. That leaves a step of
  about 1 m at the pad edge.
- A pad remnant stands over the forecourt road that crosses the station.
  The level takes no road (24a).
- The north portal keeps its OSM ramp (mouth 195.5 m, opened by the
  `Ham3.obj` deck witness), not the deck's bottom (194.1 m).
