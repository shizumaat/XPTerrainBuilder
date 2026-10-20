# The drop goes along a road edge (RULINGS 2026-10-20d; issues #712, #1003; follows #1088)

Lane l1088, 2026-10-20. Owner law: RULINGS 2026-10-20d ("Where banks cannot
reach the ground, the drop is placed along a road edge: the road is graded to
road rules and reaches the high side, and a vertical drop is allowed on its
low side so the buildings there seat on the ground"). It follows the pad fill
of #1088 (`pad-fill-region-spec.md`, RULINGS 2026-10-19ap). The consumer
census (RULINGS 2026-08-30l) was written before any consumer was edited.

## 1. What was measured

Capture `frames/l1088/HECA.pkl` (branch base 8e4b38045 = #1088 + main
7ea290492); patch `frames/m13/m13_HECA.osm` (the #1088 closing build).

* **The fills cannot bank down.** The plate fill under the #712 slab
  (`building6/landing1`, 7,284 m2) stands at its block's datum, predicted
  96.17 m. The ground under its collar is 89.4-93.2 m. The 15 m collar at 1:3
  drops at most 5 m. In m13 the collar ring reaches 87.18 m. The #1003 pier
  fill (`building5/landing10`, 31,147 m2) stands at 100.1 - 0.3 m over ground
  of 92.0-103.4 m, and has the same fault on its north and west sides.
* **The road the drop belongs on.** The roads that carry the city's traffic
  to the terminals run over one pack page, `dsf:pol10` (`Asphast_red.pol`,
  70,036 m2, 18.5 m wide). It carries 3,444 m of mapped `secondary` road:
  33 pieces, all running through, 0.87 pieces per 100 m, 91 % of its
  half-perimeter. Today it is a LOT. The source classifier reads only
  `highway=service` as road evidence: 28 m of it lies inside the page, so the
  04j strip rule never sees the network road. It is the only HECA page with
  network road through it.
* **Distances.** The #712 fill is 68.6 m from the page (its collar 52.5 m),
  with the lot `gap:3` between. The #1003 fill touches only the landing
  run-out strips (`runout:building5/landing2/3`). It is 67 m from the page.
* **A step can be built at the page's kerb.** Gap pieces stand off the page.
  They share none of its vertices (nearest 0.50 m, median 2.1 m). Ribbons
  share 617 vertices with gap pieces, so a step at a ribbon's kerb needs a
  riser (#951's band riser, draft PR #1041). That is out of this round.
* **A pad has no pre-solve level.** No pad or landing vertex has a
  `preferred_z`, `apron_trend_z` or `taxi_trend_z`. A road vertex shared with
  a pad is therefore a §37 (6) mouth at its own DEM, and the hard ramp
  ceiling holds the road beside it within `visual_m` of that DEM.

## 2. The rule

**R1. A page a network road runs through is that road.** The 04j strip rule
also reads the mapped NETWORK roads: the `[osm_roads] ribbon_highways`
classes less `service`, which the road evidence already reads. A page is a
road strip (`service_road`) when all of these hold:

* it is at most `[service] free_max_width_m` wide;
* it touches no taxi centreline;
* network road runs through it for at least `[lot] through_min_fraction` of
  its half-perimeter;
* the network road in it is in at most `[lot] max_road_pieces_per_100m`
  pieces.

These are the strip rule's own thresholds. A lot carrying lanes keeps its
verdict (14a (2)), because its lanes are service roads.

**R2. The fill runs to the road.** A pad fill is a landing of kind `plate`
or `piers`. It *cannot bank down* when its predicted level (`datum_pred` +
`y`) stands more than its collar's drop (`platform_collar_max_m` x
`bank_slope`) above the lowest DEM on its collar's outer line. Such a fill
takes the ground between it and every road strip within `[building_pad]
fill_road_reach_m`. A road strip here is a road-family source cell that
touches no airside region. The ground taken is:

* the convex hull of the fill and the strip's parts within reach,
* less the strip itself,
* less what is already held (pads, the airside and its bank, earlier
  landings),
* keeping only the pieces that touch the fill.

The strip is never cut. Its kerb is the fill's edge there, so the two share
vertices. The collar is minted only over ground the extended fill does not
hold.

**R3. The road reaches the high side.** The road vertices on the fill's ring
are landing vertices, held at the block's datum + `y` by the landing's own
rows. Every other vertex `v` of a road face sharing that frontage takes one
hard row against the block's datum column `D`. Here `d` is `v`'s distance
from the frontage along the road's own edges:

    y + max(-cap * d, -g * d)  <=  z_v - z_D  <=  y

This is the run-out law (`constraints/ramp_runout.landing_runout_rows`),
keyed by route distance instead of by a straight axis. `g` is `[road_contact]
ramp_grade` and `cap` is the road's longitudinal cap. The row stops at the
station where the design ramp off the fill's highest predicted level has met
`v`'s DEM. Beyond that station the road is on its own ground.

The same predicted level is the §37 (6) MOUTH level of a fill vertex. It is
the run-out's `z_hi`: `datum_pred` + the block's widest reach band + `y`,
and never the DEM. As a result, the ramp ceiling cannot hold the road down on
ground the fill covers. The cross-section (2 %, hard) and the cap are
unchanged.

**R4. The vertical drop on the low side.** On a road face R3 governs, a kerb
vertex is an UPPER vertex of a declared wall when all of these hold:

* it lies on road faces only;
* it is not on the frontage;
* its §37 target stands more than `[cockpit] visual_m` over its own DEM.

The LOWER vertices are those of the groundside non-rigid, non-road faces
within `[service] retaining_wall_reach_m` that stand across the kerb.

Each run is one `road_terrace['wall']` record with `retains` set. The
existing machinery then:

* withdraws the stage-2 pair rows across it (`wall_release`);
* cuts the bending across it (`solve/wall_cut`);
* bounds the lower side at the wall's height (`_wall_step_rows`);
* declares the joint to the census (`publication.wall_terrace_joints`).

The record's line is the kerb run offset outward into the stand-off, so no
row along the road crosses it. Its height is the highest upper target less
the lowest lower DEM. A gap piece does not follow a road ring edge whose two
ends are wall-upper vertices (`constraints/gap_follow`). The lower side keeps
its own ground.

## 3. Consumer census (RULINGS 2026-08-30l)

| # | reader | reads | change | ruling |
|---|---|---|---|---|
| 1 | `classify/sources._record` | source pages, road chains | R1's network-road rung | THE derivation site of R1 |
| 2 | `classify/roles` strip -> `service_road` | `src.cls` | the page becomes `service_road` | unchanged code |
| 3 | `classify/airside_edge` §27 | strips | a strip flips by share (0.2), not by edge | unchanged; the page has no airside contact |
| 4 | `classify/lot_roads` | `LOT_ROLES` lots | the page is no lot; a ribbon along it stays a ribbon | unchanged |
| 5 | `planar/landing.landing_cut` | `LOT_ROLES` | today the page is cut under the deck landings and run-outs as a lot | EDITED: a road strip touching no airside is cut there too, never under a plate / piers fill (R2 stops at the road) |
| 6 | `planar/landing._runout_regions` | standing base regions | the run-out yields to what stands | unchanged; the page is cut first (row 5) |
| 7 | `planar/landing` PASS 1a | `f.extent`, `taken` | R2's extension | THE derivation site of R2 |
| 8 | `planar/landing` PASS 2 collars | `held_c` | the collar takes what the extended fill does not | unchanged code |
| 9 | `planar/ribbons._ribbons_pass_c` | rigid faces | a ribbon or gap piece inside the extension is clipped | unchanged; #1088 residual 2 stands |
| 10 | `airport/road_ramp._contacts` | `_airside_level` | a mouth on a fill takes the fill's `z_hi` | EDITED (R3) |
| 11 | `constraints/platform.landing_rows` | landing ring | holds the frontage at datum + `y` | unchanged |
| 12 | `constraints/ramp_runout` | run-out records | R3's rows beside them | EDITED: one generator |
| 13 | §37 rows and ceiling | `road_ramp_z` | the ceiling reads row 10's level | unchanged code |
| 14 | `airport/road_ramp.with_road_ramp` | `road_terrace['wall']` | R4's records join the pack walls | EDITED (R4) |
| 15 | `wall_release`, `_wall_step_rows` | wall records | release; lower side bounded | unchanged code |
| 16 | `solve/wall_cut` | wall records (`retains`) | bending cut | unchanged code |
| 17 | `publication.wall_terrace_joints` | wall records | census joint `wall_terrace` | unchanged code |
| 18 | `check_grade.DeclaredWallSteps` | sidecar joints | forgives the declared step across the line | unchanged code |
| 19 | `constraints/gap_follow` | fixed rings | a gap piece never follows a wall-upper road edge | EDITED (R4) |
| 20 | `airport/placement_read`, `slab_drape` | fill faces | a body over the extension reads the fill | unchanged (#1088 rows 12-13) |
| 21 | census road laws | `service_road` faces | the page is judged as a road | the bar |

Airside: R2 never takes the airside or a bank's width of it (the landing's
`base_hard`). R1's page touches no airside region (row 5). Stage 1 cannot
see any of it.

## 4. Emittability

A vertical drop in a heightfield needs two lines of vertices at different
levels. At the page's kerb the gap pieces stand 0.5-4 m off, so the mesh
builds the wall across the stand-off. A kerb whose low-side face shares its
vertices cannot carry the step. It needs a riser (#951), so it is counted as
`road_wall_shared_kerb` and never declared.

## 5. Bars (HECA, one build against main)

* The owner sites, read first:
  * #712 at 30.1096365, 31.3889978;
  * #1003 near 30.112939, 31.397394.
* Buildings on the low side are within 0.5 m of their ground.
* The access road is within the road caps.
* No airside vertex moves more than 0.05 m.
* The census does not rise against main beyond the declared walls.

## 6. Not in this round

* The riser for a shared kerb (#951).
* A fill that reaches a road only through a mapped ribbon. Ribbons are late
  cells and are absent at the platform stage.
* `fill_road_reach_m` = 100 m is a WORKING VALUE awaiting the owner's
  confirmation. It is the depth of a terminal forecourt: kerb, drop-off
  lanes, one parking row. No airport is tuned to it.
