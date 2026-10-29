# EDDF tunnel mouths on the LFPG cuts rules (#1028 part C)

Status: E1 and E2 BUILT, E3 MEASURED AND HELD (see E3) (lane `l1028`, branch `claude/l1028-eddf-mouths`,
PR #1593, stacked on `claude/llfpgcut-cuts-tunnels` 4dd8956cd, PR #1580).
Q-A and Q-B were ruled by the owner on 2026-10-28T14:52:14Z (RULINGS
2026-10-28s (5) and (6): Q255 a, Q256 b). Owner scope for beta 5 (2026-10-28): "For beta 5 I would like
LFLL and EDDF tunnels and the KATL highway cut."

EDDF is the TEST CASE. Nothing here asks which airport it builds (RULINGS
2026-10-05e).

Rulings it reads: 2026-10-19s (#1028's three clauses; 150 m slide cap),
2026-10-20 Q31 (#1028 spec part B: pack objects take priority for a trench's
size, shape, depth and location), 2026-10-20e (Q41: a pack portal sets the
mouth only where the ground does not already carry the cutting), 2026-10-20an
(a pack portal object sets one trench across every bore at that portal,
ending at the object's outline), 2026-10-20ao / 20as, 2026-08-31h (31h duals),
2026-09-11aq A (only `tunnel=yes` seeds a bore), and the LFPG rules of
2026-10-28k (`lfpg-cuts-tunnels-rules-spec.md`, R1, R2, R4, R5, R6).

## 1. What EDDF builds on the 28k base

Dry structure replay (`python -m auto_patch_v2.planar EDDF --stage
structures`) on 4dd8956cd: **5 tunnels** — 2 OSM, 1 pack corridor
(`Frankfurt_Mesh_Tunnels_Walls_1.obj`, a service ramp 870 m west of the runway 25C threshold, at
50.0453, 8.5749) and R6's `viaduct-road:0` a/b (the Terminal 1 forecourt road
under the departure viaducts, 50.0515, 8.5669). 153 distinct tunnel
refusals: 37 "the credible survey carries the road", 33 "the credible survey
shows no cut", 97 lines "no portal" (with repeats).

The HESSE1M survey holds EDDF's real road cuttings. Under R1 the survey now
decides almost every mapped mouth, and 20e says the same of a pack portal:
where the ground carries the cutting, nothing is cut a second time and R2's
`survey_trench` keeps the zones off the trench. So at EDDF the trench's
DEPTH is the survey's. What is still wrong is WHICH ROAD a mouth reads, and
the trench's PLAN.

## 2. What the 28k rules do not give EDDF

**F1. Two feeds carry every tunnel twice.** The big-roads and airport-roads
extracts both map EDDF's tunnels: **118 of 282 tunnel ways are a node-for-node
copy of another**. `structure_approach.chains` joined a way to its copy at
their shared end, so the bore ran out and back. Both of its "ends" stood at
ONE portal, and the real far portal was lost in the chain's middle.
Measured on the base:

- Every R1 reading on such a chain is the same at both "ends". For example
  `-16928+-9515@0/@1` both read cover 111.42 and road 111.06, and
  `-8163+-4404@0/@1` both read 91.29.
- The two "mouths" overlap each other. The service tunnel `-9780` (copy
  `-17626`) under the taxiway bridge about 400 m west-north-west of the runway 18 threshold is one case:
  `@1` was refused as "its corridor overlaps `@0`". Its north portal was
  never read.
- A dual carriageway could not merge (31h), because each carriageway's
  bore had one portal twice and the other one not at all.

**F2. A road under the apron is mapped `covered=yes`, not `tunnel=yes`.** At
the tertiary dual carriageway under the taxiway bridges about 550 m east of the runway 25R threshold (2 + 2 lanes,
50.0439–50.0449, 8.5408–8.5434), the OSM ways are `covered=yes` along their
whole 207 m. The survey shows the real portals at their mapped ends: 104.1 /
103.8 at the ends against 110.6–112.1 over the cover, about 7 m. The pack
places its trench objects there (`Tunnel_4.obj` anchor 50.043834, 8.540985,
at the south-west end). Under 11aq A a `covered` way is not a bore. Only the
40 m under the taxiway bridge `-1219` is bored, by §34 (5). That bore's
ends stand mid-cover at grade, so R1 reads "no cut" (cover 0.43 / 0.07 m over
the road) and the real portals 85 m further out are never mouths. → **Q-A.**

**F3. The pack's notched trench objects.** EDDF's pack models each road
trench at a taxiway bridge as a walled trench object with a separate flat
`ATTR_hard_deck` bridge object:

| object pair | landmark | plan | depth |
|---|---|---|---|
| `Tunnel_1.obj` + `Tunnel_1_Draped_obj.obj`, `Bridge_2_hard*` / `Tunnel_2.obj` | the taxiway bridge about 400 m west-north-west of the runway 18 threshold, over the tertiary `-7909` and the service road `-9780` (50.0327–50.0370, 8.5204–8.5216) | walls 85 × 488 m; floor plate 41 × 383 m | floor 6.0 m under the object's zero |
| `Tunnel_3.obj` + `Bridge_3_hard*` | the motorway underpasses of taxiway `-1218`, 460 m east of the runway 25R threshold (50.0446, 8.5399) | 379 × 81 m | walls to −6.0 m |
| `Tunnel_4.obj` + `Bridge_4_hard*` | the tertiary dual of F2 (50.0438, 8.5410) | 224 × 38 m | walls to −6.0 m |

Every reader refuses these objects:

- `Tunnel_1`: never screened (shallow seat, no admitted bore in its plan).
- `Tunnel_3` / `Tunnel_4`: refused by the corridor reader ("no floor plate",
  "roof, not a crest"), the sunken-road reader ("29 % / 2 % roofed, an open
  ramp") and the basin reader ("datum relief").

#1132 (part B, not landed) measured their floors within 0.4–1.8 m of the
survey. So by 20e they set no mouth. What Q31 and 20an still ask is that the
objects decide the trench's PLAN, "ending at the object's outline". R2's
`survey_trench` is drawn from the carriageway width (+ rim stand-off + 1:1
bank). → **Q-B.**

**F4. Dual widths.** 31h (`merge_duals`) and #807's per-station edges
(`dual_width`) already give a dual one ramp spanning both carriageways. On
the base they could not fire at EDDF because of F1. With E1 they do:

- The tertiary dual of F2 merges into `-16928+-9515+-16927+-9514`.
- The south ends of `-7909` and `-9780` merge into one dual whose width
  spans both carriageways.

No new rule is needed.

## 3. Rule built

**E1 — A SECOND FEED'S COPY IS THE SAME WAY.** A tunnel way whose nodes are
another tunnel way's node for node, in either direction, within
`NODE_TOL` (`structure_approach._copies`), is no way of its own. It rides in
its original's `Bore.ways`, so the tunnel ids, `replaced_ways`,
`Tunnel.ways` and the published ids keep naming both feeds. It never joins a
chain, so the bore runs portal to portal once. This was #1028 part A's named
follow-up ("`chains()` should merge coincident ways from two feeds").

### Consumer census (RULINGS 2026-08-30l): every reader of a `Bore`

| reader | reads | E1 |
|---|---|---|
| `planar/structures.build_structures` (OSM and §34 (5) underpass bores) | `chains(tunnel_ways)` | one bore per tunnel, both real ends |
| `structure_approach.mouths` | `b.points` ends, `max(width over b.ways)` | the far portal is a mouth again; width unchanged (a copy carries the same tags or fewer) |
| `bore_continuation.continues_underground` | `own = b.ways` | the copy is the bore's own way. Before, it was "another tunnel going on" whenever a split chain left it outside. 46 false no-portal lines go at EDDF. |
| `structure_approach.merge_duals` (31h) | two different bores' mouths | can now pair the two carriageways |
| `lidar_road._cover` / `survey_mouth` (R1) | `bore.points` from the portal inward | reads the bore's own half, not an out-and-back line |
| `structures` tid / `replaced_ways` / `Tunnel.ways` | `"+".join(b.ways)` | the same ids. Chain order now puts a copy after its original. |
| `covered_ground._served` (#714) | `chains(ways)` lines under airside pavement | the same footprint (a copy's line is its original's) |
| AK `planar/bridge_span` (`EdgeBridge.bores`, batch AK, not on this base) | served bores as `"+".join(way ids)` | a bore's id string may now hold a copy's id after its original. It joins by geometry, not by id order. To be measured when AK and this branch meet (§4). |
| census `tunnel_mouth_canonical`, publication `tunnel_mouth_depths` | `Tunnel` records | read the records as built |

**E2 — A COVERED ROAD IS A BORE WHERE A CUT OR A TRENCH OBJECT SAYS SO
(RULINGS 2026-10-28s (5), Q255 a; amends 11aq A).** A road or railway
mapped `covered=yes` that carries no `tunnel` value is read as a chain of
covered ways (`planar/covered_bores.covered_bore_ways`). The chain is a bore
when either holds at one of its two mapped ends:

- On a credible survey, R1's own clearance there
  (`lidar_road.end_clearance`: the cover over the chain's first stretch
  inside the end and the surrounding ground, less the surveyed road on the
  straight line out of it) is at least `[channel] object_min_depth_m`.
- A pack trench object (E3) stands within
  `[tunnel.object] bore_end_tolerance_m` of the end.

The chain's ways enter the bore set as copies tagged `tunnel=yes` and
`o4_covered=yes`, so R1, the slide, 31h and the rest of the bore law read
them unchanged. The §34 (5) underpass pieces of the same ways give way to
them. Any `tunnel` value (`building_passage` and its class) stays 11aq A's
alone. A coarse DEM reads no cut (14f), so there only a trench object
admits.

**E3 — THE ZONES KEEP OFF A PACK TRENCH OBJECT AT A BORE END (RULINGS
2026-10-28s (6), Q256 b). MEASURED AND HELD.** The owner: "if it's a tunnel
mouth object, then typically graded terrain should come right up to it on 3
sides with only the road grading down to it's low edge on the 'front'
side."

The trench object (`airport/trench_objects.read_trench_objects`, read once
beside the portals in `tunnel_objects.read_corridors`, and E2's witness) is
a placed pack object that meets all of these:

- It is not a stock library object, and no corridor, shell or portal has
  taken it.
- Its solids hang at least `[tunnel.object] shell_floor_min_m` under its
  zero.
- They stand no more than `[bridge] clearance_minimum_m` above it.
- Its plan holds a mapped tunnel or covered road end within
  `bore_end_tolerance_m`.

Its outline is the union of its solids' plan: the plates and the walls'
plan segments.

Built and measured (commits a67117871 / 7ec4cb374): every trench object at
a bore end added its outline to the structure pass's keepouts (R2's region),
first whole, then less the classification's cells.

- EDDF closing build `l1028r2` against the control `l1028ctl2`:
  ADJUDICATED 5280 → 5375, airside 2273 → 2347. CRITICAL motion 1 → 0
  (the apron | apron step at 50.04414, 8.54181 is gone).
- The census replay on the registered capture splits it:
  - E1+E2 arm: 4824.
  - E1+E2+E3 arm: 4923.
  - With the cells trimmed out: 4922.
- The +73 airside rows are 64 `airside_no_step` and 22 `taxi_box` rows
  inside taxiway `pav76`. That is the cross connector over the `Tunnel_4`
  trench, about 700 m east of the runway 25R threshold (50.0444, 8.5440).

Reading: the keepout leaves the survey's 7 m trench floor as ground right
against the taxiway deck's edges, and the solve pulls the deck toward it.
Nothing declares that edge a wall (20as: "the cut … encompasses the
object"). The fix is a declared wall at the outline's edge against
airside pavement, so the zones stop at the object and the taxiway edge is
the pack's wall. It needs its own spec, and it is over this lane's two
iterations. `Tunnel_3` and `Tunnel_4` are read as trench objects at EDDF.
At KATL `tunel_A/B/C` and at LFPG `C1.obj` and `2A_70.obj` are read too,
the same objects batch AK's `bridge_span` reads at KATL.

### Consumer census for E2 (RULINGS 2026-08-30l)

| reader | reads | E2 / E3 |
|---|---|---|
| `structures.build_structures` bore set | `tunnel_ways` + underpass pieces | E2 adds the covered chains and drops their own underpass pieces (same way ids) |
| `structure_approach.mouths` / R1 `survey_mouth` / slide / 31h | the bore's two ends | read the covered bore as any bore |
| `structure_approach.approach`, `road_index`, `crossing_roads`, `bore_continuation.tunnel_ends` | `airport.osm_ways` (the covered way untagged) | unchanged: the covered way is still a road there, so a ramp's own road and the approach walk read it as before |
| road ribbons (`classify`) | `airport.osm_ways` | unchanged: a covered bore's middle stays the road ribbon under the cover, exactly as a §34 (5) underpass |
| zones (`zone_regions` keepouts), terrain edge | `classification.keepouts` | unchanged (E3 held) |
| `tunnel_objects.read_corridors` / `portal_objects.read_portals` | pack objects | read first. A trench object is never one they took. |
| basin / sunken-road / door readers | pack objects | unchanged: a trench object stays refused there |

## 4. How it composes with AK's `bridge_span` (#1138)

`bridge_span` derives where an EDGE-WALL bridge's cover ends (KATL
`tunel_A/B/C`). It reads `airport/hanging_objects.edge_wall_reading` and the
bores whose cut meets the object. E1 changes the bore set that reaches it in
two ways:

- A copy-chained bore that ran out and back is now one bore with two real
  ends.
- The bore-id strings may now contain the copy's id after its original.

KATL's dry structures are IDENTICAL under E1, so KATL's edge bridges see the
same bores. At EDDF, `edge_wall_reading` needs deck plates flush with the
object's top on hanging walls, and the pack puts its deck in a SEPARATE
`Bridge_N_hard` object. Whether AK's co-placed union (`_co_placed`) joins
them is unmeasured: AK is not on this base. If it does, Q-B is answered by
AK's back line and this spec's Q-B is withdrawn.

## 5. Measured

The base and branch arms run on one capture taken on the base
(`/private/tmp/claude-501/l1028/cap/EDDF.pkl`).

- **Dry structures, EDDF:** tunnels 5 → 5, distinct refusals 153 → 107.
  - Gone: the service tunnel `-9780`'s out-and-back south mouth (50.03496,
    8.52064). The merged dual's south end is now refused: the road reaches
    grade 10 m out, inside the survey's trench (20e).
  - New: `tunnel:-471+-180@1` (50.05184, 8.55153), the far portal the chain
    used to lose. R1 builds it at floor 104.66, 1.59 m under the surveyed
    road (5.0 m owed, 232 a).
- **Dry structures, KATL:** IDENTICAL (7 → 7).
- **Dry structures, LFPG:** tunnels 27 → 30; distinct refusals 300 → 241.
  - Five mouths are the same mouth under a de-doubled id, at the same
    place and floor (for example `-1719+-235+-1719+-235+-383@0` →
    `-1719+-235+-383@0`). `-384@0` becomes `-1721+-237+-384@0`, 2 m away.
  - `-5099+-719@0` → `@3`, at the same bore's other copy-free end.
  - `-1669+-228@0` (49.0116, 2.5615) is refused. Its R1 cover now reads its
    own half of the bore: cover 110.17 over road 105.23, clearing 5.0 m
    (232 a).
  - New far portals: `-10295+-3555@0` (49.0103, 2.5946), `-35258+-13950@0`
    (49.0109, 2.5804; §4.3's `-13950`), `-25663+-9581+-7810+-2365@0`
    (48.9732, 2.5159) and `-33917+-13264@1` (48.9992, 2.5037).
  - `-10256+-3516@0`'s floor moves 0.05 m.
- **Census replay, EDDF** (`v2_solve_replay --replay … --from planar --emit
  --verify` plus `census.py`, both arms on the one capture):
  - ADJUDICATED 4828 → 4827 (airside 2274 → 2275, groundside 2542 → 2540).
  - CRITICAL motion 1 → 1, the same site (an apron | apron step at
    50.04414, 8.54181).
  - `ramp_in_strip` 3 → 3, all on the `Walls_1` corridor at 50.0453,
    8.5749, inherited.
  - `road_cross_section` 167 → 165, `strip_arc` 8 → 9, `hairline_pair`
    1315 → 1312.

### Closing builds (round 2, 2026-10-28)

All were run through the harness after the master's `--refresh-data dem`.
The negatives that refresh recorded carry engine 1.50.1887, the main
tree's. The branch sits on #1580's 1.50.1884, so every arm, the control
included, was built with `O4_Version.py` set to 1.50.1887 in the working
tree only. The version is a cache and provenance key, not geometry.

| arm (tag) | code | ADJUDICATED | airside | groundside | CRITICAL motion |
|---|---|---|---|---|---|
| control `l1028ctl2` | #1580 head 4dd8956cd | 5280 | 2273 | 2998 | 1 |
| `l1028br2` | + E1 | 5279 | 2274 | 2996 | 1 |
| `l1028r2` | + E1 + E2 + E3 | 5375 | 2347 | 3019 | 0 |
| **`l1028r4`** | **+ E1 + E2 (this branch)** | **5277** | **2275** | **2993** | **1** |

The harness flagged `l1028ctl2` and `l1028br2` CONTAMINATED. The flagged
writes were other lanes' concurrent builds: a KCLT-area OSM clip and
Global Airports caches.

## 6. Questions (RULED 2026-10-28: Q-A → Q255 a = E2 built; Q-B → Q256 b = E3 held)

**Q-A (F2).** Is a road mapped `covered=yes` along its whole run a bore when
both of these hold?

- Its mapped ends stand at least `[channel] object_min_depth_m` (3.0) under
  the survey's cover over it (the R1 reading).
- Or a pack trench object stands at an end.

At the tertiary dual east of the runway 25R threshold, the real portals are its
ends at 104 m, 7 m under the 111 m cover. Today only the 40 m under the
taxiway bridge is a bore, and it reads "no cut".

- A. Yes, with that witness (recommended): it lifts 11aq A for this
  witness only.
- B. No: `covered` stays "not a bore" (11aq A).

**Q-B (F3).** Where a pack trench object (walls reaching
`shell_floor_min_m` under its zero around a mapped road) stands at a mouth
that the survey decides (R1/20e: the ground carries the cutting), does R2's
keepout take the object's outline (Q31 / 20an)?

- A. Yes (recommended): the keepout is the object's plan ∪ the survey
  trench. The zones never grade inside the pack's walls. The depth stays
  the survey's.
- B. No: the carriageway trench stands, and the pack's walls may stand in
  graded ground.
