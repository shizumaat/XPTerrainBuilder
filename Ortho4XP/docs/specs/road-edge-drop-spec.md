# The drop goes along a road edge (RULINGS 2026-10-20d; issues #712, #1003; follows #1088)


> **Superseded in part (round 5, lane lheca5, 2026-10-27).** §2 R1 and R4 and §4 are
> replaced by `fill-step-at-road-kerb-spec.md` (RULINGS 2026-10-27i/j): R1 re-kinds a page
> only where it is welded to a pad, and the drop is the fill's riser at the far kerb
> (`planar/fill_riser`, `airport/riser_wall`); `airport/road_edge_wall` is deleted. §1 and
> §7-8 stay as the measured record.

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

## 7. Measured (lane l1088, two iterations, replays of `frames/l1088/HECA_it1.pkl`)

All iterations are compared against the base replay (`frames/l1088/HECA.pkl`,
replayed at the branch base 8e4b38045).

* **R1.** `dsf:pol10` is now a `strip` (network road 3,444 m through it,
  0.6 x 3,789 m needed, 33 pieces, width 18.5 m). It is graded as a
  `service_road`.
* **R2.** Two fills run to the road. The #712 plate (`building6/landing0`)
  grows to 46,071 m2. The #1003 piers fill (`building5/landing11`) grows to
  77,626 m2: it is the whole T3 forecourt up to the road's NE branch. Two
  forecourt pads ride the fill:
  * `building21`: 92.41 m becomes 101.49 m (DEM 93.1);
  * `building14`: 96.12 m becomes 101.53 m.
* **R3.**
  * Iteration 1 published no channel. The walk ran over road-owned vertices
    only and stopped at the first kerb vertex shared with a collar or a
    ribbon, so only 5 vertices were reached. The walk now covers every road
    ring vertex: 238 vertices.
  * Iteration 2 (`it2`): the rows and the §37 route-lifted ceiling
    contested each other. 129 of 260 rows relaxed, by up to 6.05 m. The §37
    target now leaves the vertices R3 governs (`it2b`), and 44 of 460 rows
    relaxed.
  * Those 44 relaxed rows lie beside the run-out strips. The run-out strips
    now keep their own law (no replay since).
* **R4.** No wall is declared at HECA. Along the raised access road, no
  groundside face stands within 8 m of the high kerb runs (8 runs, all
  `shared_kerb`). The low side is OUTSIDE the patch coverage, so the drop
  there is the terrain mesh's own transition from the kerb to the DEM.
* **Sites** (`it2b` against the base):
  * #712 is 96.37-96.56 m (base 96.54-96.63);
  * #1003 is 101.49-101.53 m (base 101.52-101.63).
* **Airside.** 16,676 vertices joined, 0 movers over 0.05 m.
* **The access road** stands up to 17.58 m over its DEM (base: 5.39 m). This
  is the 5 % ramp off the T3 fill (z_hi 102.5 m) down to ground at 84-89 m.
* **Census** (`it1` against the base): adjudicated 12,195 becomes 12,020.
  * Groundside 1,758 becomes 1,528. Airside 10,419 becomes 10,475, all of it
    pad / collar rows at the fills.
  * Rises: `road_cross_section` 142 to 159, `pavement_over_road_cap` 23 to
    27, `plane_gradient` 2 to 5 (worst 5.8 m at `building5/landing9#collar`),
    `hard_conflict` 620 to 676.
  * Critical motion 4, unchanged.

### 7.1 Closing build

The closing build is `l1088_HECA`: the branch merged with main 09f87265a.
The control is `l1088main_HECA` (main 09f87265a, built because the
artifact-ledger lookup missed). Both are in `frames/l1088/`.

* **The owner sites.**
  * #712: `gap:3` at 88.84-96.52 m becomes the fill `building6/landing0`
    at **96.37-96.56 m**. The slab is at 96.62 m.
  * #1003: `gap:5/s0` at 94.09-101.82 m becomes `building5/landing11` at
    **101.49-101.53 m**.
* **Airside.** 16,676 rolled-on vertices joined; **0** moved more than
  0.05 m (worst 0.01 m).
* **Pads (281 compared).**
  * No pad outside the fills moved more than 0.24 m. The low-side pads keep
    main's levels (`building22` +0.57, `68` -0.80, `63` -0.46 m against
    their DEM, unchanged).
  * Fill-borne pads rose: `building14` +11.75 m, `building21` +8.53 m,
    `building7` +4.27 m.
  * The seasonal block piece `building6` fell 0.97 m. The T3 block fell
    0.30 m.
* **The access road** stands up to 17.58 m over its DEM.
* **Census** against main: adjudicated 12,182 becomes **12,751** (+569). No
  wall is declared: R4 found no low-side face (§7).
  * `hard_conflict` 569 to 1,016 (airside-labelled pad rows 16 to 240,
    groundside 553 to 776).
  * `pavement_over_road_cap` 36 to 57.
  * `hairline_pair` 2,604 to 2,703.
  * `road_cross_section` 270 to 283.
  * `plane_gradient` 4 to 7 (worst 5.76 m, collar).
  * `road_coverage_join` 17 to 4.
  * Critical motion 4, unchanged.
  The #1088 build alone measured +410 against its main.

**Bars.** Met:
* the sites;
* the low-side pads;
* airside motion.

Not met:
* the census (+569, no declared wall carries it);
* the road caps (`road_cross_section` +13, `pavement_over_road_cap` +21);
* the two block moves.

## 8. Round 3 (lane l1088c; the reviewer's D1-D5, owner Q58: the 17 m ramp)

Capture `frames/l1088c/HECA.pkl` (branch + main 43ab28518); base solve
`base_it2.pkl` (`--gap-free`), last stage `late_it2.pkl`; closing build
`frames/l1088c/l1088c_HECA.osm` at f4a0e3d93 against `l1088main_HECA`.

**What changed.**

* **D2, the lens.** `planar/fill_road.extend_to_roads` returns the fill and
  the ground within reach of BOTH the fill and a strip (the mitred buffers'
  intersection), kept BETWEEN the two (the closing of fill and strip at half
  the reach: without it the lens wraps a strip's end and takes the far side,
  5,720 m2 on the twin), less every strip, less what is held, the pieces
  touching the fill.  At HECA the fills grow by 3,413 m2 in all (the hull
  took 46,071 + 77,626 m2).  Road strips join `held_c` before PASS 2.  A
  fill is cut back `bank_min_width_m` from every earlier landing of its
  block at another level AND from the block itself (deviation: the block is
  the `y = 0` level of its own; without it 159 of `building5`'s rim
  vertices stood at the fill's `y = -0.30`, the block mean 101.774).
* **D3.** `airport/fill_ramp`, `constraints/fill_road`, their three
  `emit.toml` rulings and the targets withdrawal are deleted.  The mouth
  line in `road_ramp_targets` stays.
* **D4.** `airport/road_edge_wall.drop_runs` (base) publishes
  `road_terrace['drop']`: 16 runs over 139 kerb vertices at HECA.
  `late_stations` and `gap_follow` skip drop edges; a lot vertex or a follow
  ring whose NEAREST edge is a drop takes nothing from that road (never the
  next edge along: with the edge alone removed, lot vertices 1.6 m off the
  drop were held 1.5 m over their DEM by the road beyond it).
  `road_edge_walls` (late derive) declares one retaining wall per run with
  a low side: **6** at HECA.  The last stage now applies `wall_release`.
* **D5.** `--why-at` on `building6`'s low corner (94.43 m, DEM 90.04):
  bound by `pavement_road_cap` to `service_road` v34952, itself on its §37
  ramp ceiling.  `datum_vertices(fills=True)` gives a held block that welds
  nothing and carries a fill a stage-2 column (read by
  `platform_plane_rows` and `landing_rows` only; the stage split never
  reads it): `building6` is flat (tilt: control 0.218 %, iteration 1 0.617 %, now 0.000 %).

**Measured (build `l1088c_HECA` against `l1088main_HECA`).**

* #712 (30.1096365, 31.3889978): `gap:3` 92.04 -> `building6/landing1`
  **96.71** (slab 96.62).  #1003 (30.112939, 31.397394): inside
  `building5/landing10` at **101.53** (101.66).
* Airside (solve-owned, 16,676 joined): 0 moved > 0.01 m.
* Blocks: `building5` 101.828 -> 101.829, its deck landings 0-4 unchanged;
  `building6` 96.456 (tilt 0.218 %) -> 96.560 flat (+0.10 m).
* Low side: `building22` 86.51, `68` 80.88, `63` 81.72, `14` 89.78, all
  unchanged.  `building7` (inside the #712 plate's own extent, not the lens)
  92.20 -> 96.56.
* Gap faces within 4 m of the six drops: 28 of 37 nodes stand more than
  0.5 m over their DEM (worst +2.42 m).  Named residuals: a mapped ribbon
  that joins the raised road at its kerb ramps down into the piece
  (`big_roads:-6586`, `small_roads:-3964`); `gap:2/s0` follows the T3
  fill's collar on its far side; `gap:27/lot` beside a kerb whose §37
  TARGET is under `visual_m` while its solved level is 1.2 m over the DEM
  (the run is read on targets).
* Census adjudicated 12,182 -> **12,358**; `hard_conflict` 569 -> 739;
  `hairline_pair` 2,604 -> 2,846; `road_cross_section` 270 -> 293;
  `pavement_over_road_cap` 36 -> 63; `plane_gradient` 4 -> 6; CRITICAL
  motion 4 -> 4.  Wall-terrace joints 11 -> 16: the six road-edge walls in,
  `Airport/T23/door.obj#comp870` out (its lower lot `dsf:pol10` is a road
  since R1).
