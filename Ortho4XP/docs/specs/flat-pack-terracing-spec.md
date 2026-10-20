# Flat-pack terracing: read a pack that assumed a flat airport, and terrace groundside for it

Lane lflatpack, 2026-10-20. A spec only: no engine code is in this branch.

**Owner direction** (Noah, 2026-10-20 17:44Z): "With packages like the
TaiModels HECA, we are making compromises to adapt groundside terrain to
objects that were designed for a flat surface, not reality. If we can
identify this when we first read the package and recognize that the author
expected the entire airport to be flat, it could guide us on how best to
terrace groundside areas to create flat areas connected by sloping roads
even though it is not the most accurate rendition of the terrain. A
new/better airport package could allow us to re-grade more faithfully in
the future."

**Law this builds on:**

* RULINGS 2026-10-20d (Q40): compromises are accepted so that likely
  inaccurate objects work on sloping terrain. Where banks cannot reach the
  ground, the drop goes along a road edge. The road is graded to road
  rules and reaches the high side. A vertical drop is allowed on its low
  side.
* The groundside terrace law (2026-07-30): only pavement and roads are
  graded in groundside, and the ground between them may terrace.
* 2026-10-03c: the wall is the step.
* 2026-10-15g (A–C): no banks; a zone's outer edge goes straight to the DEM.
* 2026-10-19ad: at a road wall the safety-area band holds its graded level.
* 2026-10-19ai: the lower level (#809). 2026-10-20l: the upper level (LPHR, #1119).
* 2026-10-19ac: airside may move up to 0.5 m because of groundside changes.
* 2026-10-05e: no airport-specific code.
* 2026-08-30l: the consumer census comes before any consumer is edited.

**Prior work this folds in, not redoes:**

* `road-edge-drop-spec.md` §1–§7: lane l1088, `claude/l1088-road-wall`
  5938c294f, after #1088.
* The access-road round-3 design (§4.4 below) from the reviewer, as the
  master relayed it. A lane is implementing it in parallel.
* #951's band riser: lane m16, `claude/m16-951` 1f784e3b5, PR #1121,
  `band-road-wall-joint-spec.md`.

## 1. Detection: did the pack assume a flat airport?

### 1.1 The witness

X-Plane seats an OBJ by its origin: the object's y = 0 is the terrain at
its placement point. Nothing in the pack reaches the ground under the
object's far parts. A pack that places many structures from ONE shared
anchor therefore states every one of their floors relative to the ground
at that one anchor. This is the LSGG class of `shared-datum` authoring,
`airport/footprint_connector.authored_units` §16g. If those floors agree
while the real ground under them does not, the author modelled a flat
airport.

The engine already reads everything this needs at load:

* the pack partition (`Airport.partition`: units, then members, then
  parts, then feet);
* each member's own ground read (`Member.base_profile['feet_y']`);
* the DEM.

**Definitions.** All of these are read from the load-time partition. No
planar product is used.

* **Family.** A `Unit` of the partition: every placement sharing one
  anchor spelling.
* **Grounded feet of a member.** Its non-scatter, non-line parts' feet
  with authored `y <= feet_y + 1.0 m`. Here `feet_y` is
  `base_profile['feet_y']`, or the lowest foot when absent. The 1.0 m is
  the S4 below-grade magnitude, `flat_site.detector.below_grade_base_y_m`.
* **Seat of a grounded foot `f`.** `seat(f) = DEM(member origin) +
  unit.agl_m + y_f`. This is where X-Plane draws the foot.
* **Ground of `f`.** `ground(f) = DEM(f)`.
* **A family is FLAT-ASSUMED when all three of these hold:**
  1. Its seats agree: `p95 - p5` of `seat(f)` over its grounded feet is at
     most `flat_site.detector.seat_spread_max_m` (3.0 m, the S4 consensus
     spread).
  2. The ground under it is real relief: `p95 - p5` of `ground(f)` exceeds
     the relief floor of the DEM's source class,
     `flat_site.detector.relief_floor_m` (coarse 8.0 m, fine 2.0 m). A
     lidar-class source reads the fine floor.
  3. The seats miss the ground: the median of `|seat(f) - ground(f)|`
     exceeds the collar drop, `structures.building_pad
     platform_collar_max_m` x `emit.design.bank_slope` = 15.0 x 0.33 =
     **4.95 m** (equal to `[placement] connector_step_max_m`). That is the
     depth past which a fill "cannot bank down" (road-edge-drop R2).
* **The pack statistic `F`.** The share of the pack's grounded feet that
  belong to flat-assumed families. Weighting by feet makes a structure
  count by its size, and a lone prop or mast family weighs nothing.
* **Verdict.**
  * `flat_assumed` when `F >= [flat_pack] share_min`. The working value is
    **0.5**, a majority (Q2).
  * `follows_terrain` otherwise.
  * `no_pack` with no partition.

### 1.2 Measured

The table comes from the registered captures, through the production
loader's partition and DEM.

* Captures: `l786/HECA.pkl` (b57fe46d7), `m15/KASE.pkl`, `m2/KCLT.pkl`,
  `m12/OTHH.pkl`, `c971/LEMD.pkl` and `m5/KATL2.pkl`, all under
  `/Users/noah/XPTerrainBuilderData/.harness/frames/`.
* `members` counts the members with grounded feet.
* `seat`, `ground` and `|seat - ground|` are pack-wide, member-weighted:
  * `seat` is the `p95 - p5` of the seats;
  * `ground` is the `p95 - p5` of the ground under the feet;
  * `|seat - ground|` is the median.
* `beta` is the weighted slope of `seat` on `ground`: 1 means the seats
  follow the terrain, 0 means they are flat.

| airport (pack) | DEM class | members / families | top anchor's share of members | seat p95-p5 | ground p95-p5 | median \|seat-ground\| | beta | **F** | verdict |
|---|---|---|---|---|---|---|---|---|---|
| **HECA** (TaiModels) | coarse | 249 / 7 | 379 of 429 (DEM 108.44 m) | **1.43 m** | **34.04 m** | **17.91 m** | **0.02** | **0.9986** | flat_assumed |
| **LEMD** (Aerosoft) | fine | 166 / 11 | 184 of 327 (DEM 596.0 m) | 3.22 m | 50.52 m | 7.12 m | 0.04 | **0.9554** | flat_assumed |
| KASE (Aerosoft) | lidar | 187 / 155 | 13 of 217 | 53.53 m | 54.33 m | 0.41 m | 1.01 | **0.0000** | follows_terrain |
| KCLT (Nimbus) | lidar | 73 / 49 | 22 of 106 | 7.01 m | 9.93 m | 1.51 m | 0.61 | **0.0000** | follows_terrain |
| OTHH (Aeroscape) | coarse | 436 / 103 | 198 of 1,087 | 6.52 m | 0.00 m | 0.07 m | n/a (flat site) | **0.0000** | follows_terrain |
| KATL (Nimbus) | lidar | 60 / 33 | 14 of 88 | 36.89 m | 26.53 m | 1.68 m | 0.92 | **0.0037** | follows_terrain |

The flat-assumed families:

* **HECA:** `unit:43` (138 members, ground 25.5 m, seat 1.26 m, median
  miss 18.4 m), `unit:42` (78; 32.3 m; 0.52 m; 35.5 m), `unit:41` (29;
  35.7 m; 0.33 m; 25.2 m), `unit:38` and `unit:39` (1 each). The three
  large families share one anchor (30.112118, 31.412026), where the DEM is
  108.44 m.
* **LEMD:** `unit:25` (86 members; ground 53.1 m; seat 2.24 m; median miss
  16.8 m) and `unit:27` (70; 26.8 m; 0.80 m; 8.9 m).
* **KATL:** four one-member families, 0.37 % of its feet.
* **KASE, KCLT, OTHH:** none.

**Sensitivity** (`F`, feet-weighted):

* With the miss bar halved to 2.475 m: KCLT rises to 0.319. Its `unit:3`
  (7 members, 17.9 m of ground) has a median miss of 3.64 m, and
  `unit:31` (17 members) 1.72 m. KATL rises to 0.048.
* With the miss bar doubled to 9.9 m: LEMD falls to 0.722 and HECA stays
  at 0.9986.
* The working bar therefore sits inside a window of about 3.7–9.9 m, in
  which every verdict above is unchanged.
* Without the relief gate, OTHH's one-member families reach 0.0085.

**Not every shared anchor means a flat pack.** OTHH also places 198 of its
1,087 members from one anchor, but its ground is flat, so gate 2 fails. A
shared anchor is only half of the witness; the relief under it is the
other half.

### 1.3 Findings for the master

* **LEMD reads flat-assumed.** The brief listed LEMD among the packs that
  follow the terrain. The statistic says otherwise (F = 0.955).
  * This agrees with what is already known about the pack. Aerosoft ships
    LEMD with its own mesh pack (`Aerosoft - LEMD Madrid - 2 - Mesh`). Its
    airport interior is a dead-flat plateau at 594.625 m: 2,474 of 2,774
    nodes (memory `lemd-aerosoft-patch-ground-truth`, measured
    2026-08-26).
  * The author flattened the ground himself.
  * So under this spec LEMD is a second test case, not an
    unchanged-control airport (Q1).
* **The `1302 flatten 1` metadata.** This apt.dat key asks X-Plane to
  flatten the airport, so it is an explicit declaration of a flat
  airport. None of the six packs carries it. 261 airport entries in the
  installed Custom Scenery do. It is offered as a second, declared witness
  (Q7). No measured case exercises it.
* **Flat site and flat pack cannot both be true.** The flat-site detector
  (`airport/flat_site.py`, S2) needs no credible relief. The flat-pack
  verdict needs relief above the same floor. So the two verdicts exclude
  each other by construction. The detector asserts this; it does not
  arbitrate.

### 1.4 Where it lives

* `airport/flat_pack.py` holds `detect(airport, law) -> FlatPackVerdict`.
  It is a new family member beside `airport/flat_site.py`, it imports only
  `law` and `model`, and it is a pure reading of `Airport.partition` plus
  the DEM.
* `model/airport.py` gains `FlatPackVerdict` (verdict, F, per-family rows)
  and the field `Airport.flat_pack` (None before it runs). The pipeline
  sets it after the partition, as it does `flat_site`.
* The law goes in `law/flat_pack.toml` plus `law/flat_pack_schema.py`:
  * `share_min = 0.5`;
  * `grounded_band_m = 1.0`;
  * `terrace = true|false` (§5, phase gate).
* Every other threshold is read by reference from `flat_site.toml` and
  `structures.toml`, never copied.
* It is published in two places. The sidecar's `flat_pack` record has the
  verdict, F and the family rows. One log line has the same shape as
  `flat_site.log_line`.
* A capture written before the field existed re-derives it at replay. It
  is pure, so a replay recomputes it from the pickled partition, and
  `--from` makes no difference.

A better pack later needs nothing from us. The verdict is re-read from the
pack at every build, so a pack that follows the terrain is graded the way
it is today.

## 2. Groundside today, at HECA (what the terraces replace)

From the `l786/HECA.pkl` planar map (main b57fe46d7):

* **Groundside that is not road:** 118.2 ha (groundside pavement 103.9 ha,
  parking lots 14.3 ha), next to 27.3 ha of road-family faces.
* **Cut by the road family,** that groundside falls into **82 cells**.
  * The largest is 73.3 ha. Its DEM runs 64.3–98.7 m (p5–p95, a span of
    34.3 m), centred near 30.1203, 31.3980.
  * Three more span more than 9.9 m: 6.5 ha (10.6 m), 6.4 ha (10.3 m) and
    3.6 ha (10.6 m).
  * The other 78 span 1.6–7.8 m.
* **The l1088 closing build** (`frames/l1088/l1088_HECA`, against
  `l1088main_HECA`):
  * The T3 forecourt fill stands at 101.49–101.53 m.
  * The access road stands up to 17.58 m over its DEM.
  * There is no declared drop on the low side.
  * The census is +569 against main, groundside `hard_conflict` 553 → 776.
* **The reviewer's key finding** (§4.4): the low-side lots and pads rose
  because the late `gap_follow` rows made them follow the raised road.

The pack drew all this at one datum, about 108 m. Today the engine adapts
the ground in three ways:

* it seats each body on its own ground (20s);
* it banks fills that cannot reach the ground;
* it drapes the pack's ground pages over 30 m of relief.

The result is the series of compromises the owner describes.

## 3. The rule: terraces for a flat-assumed pack

Everything in §3 runs only when `Airport.flat_pack.verdict ==
"flat_assumed"` and `[flat_pack] terrace = true`. For any other verdict
the planar build mints no terrace, and the patch is byte-identical to
today's (§5 bars).

### 3.1 The terrace region and its cells

* **T1. What can terrace.** Groundside faces that are not road-family
  faces, and that lie in a cell with PACK content. A cell has pack content
  when it holds one of these:
  * a grounded foot of a flat-assumed family;
  * a pack draped pavement page (`dsf:pol*`) or gap sheet;
  * a detached groundside pad of such a family's body.

  A cell holding only OSM lots keeps today's grading (Q6). Never part of a
  terrace:
  * an airside face;
  * an airside bank (the landing's `base_hard`);
  * a zone face;
  * a pad of an airside-tied unit;
  * a road-family face: `service_road` strips and ribbons, the network-road
    page of road-edge-drop R1 / D1, and `tunnel_ramp`.
* **T2. Cells.** The terrace region is cut by the road-family faces and by
  airside faces. A connected component of what remains is a **cell**. Its
  boundary therefore runs along roads, along airside, and along OSM-only
  ground.

### 3.2 The level of a cell

* **T3. One datum column per terrace.** Each terrace (a cell, or a block
  of a split cell, T4) is a HELD REF `terrace:<k>` with its own datum
  column `D`. Every vertex of its faces, rings and holes, takes a HARD row
  `z_v = z_D`. This is the landing hold, `constraints/platform.landing_rows`.
  Faces keep their roles (`parking_lot`, `groundside_pavement`). No new
  role literal is introduced.
* **The level.**
  1. **A frontage cell** touches a held airside-tied pad, block or fill:
     the T3 forecourt, or a #1088 / D2 fill. Its column is tied to that
     block's column by the `datum_group_rows` equality. The block's level
     is fixed by its own airside holds. The cell adds no row that can move
     it, because the cell's hard rows are its own flatness only. So the
     relation runs airside → groundside, never back.
  2. **Any other cell** takes a soft preference toward the MIDRANGE of its
     DEM, `(p5 + p95) / 2`. That gives the smallest worst cut or fill (Q3).
     The preference is priced in the `flat_datum`-style preference group,
     below law and above seam.
  3. **Several frontage blocks at different levels** in one cell: the cell
     is cut between them (T4), and each block of the cell takes its own
     frontage.

### 3.3 Splitting deep cells and joining terraces

* **T4. The depth bound and the split.** A terrace may stand at most
  `connector_step_max_m` (4.95 m) off its DEM at any vertex, so a cell
  whose DEM span exceeds 9.9 m cannot hold one level. Such a cell is cut
  into blocks by the pad-block bisection of `planar/pad_blocks`:
  * the chord crossing the fewest metres of footed pack parts (the neck);
  * each side keeps at least `frontage_blocks` worth of area;
  * the worst block is bisected until every block holds;
  * the cap is `[building_pad] frontage_blocks_max`.

  At HECA four cells split: the 73.3 ha cell into at least 4 blocks (34.3 m
  over 4.95 m x 2), and the three 10.3–10.6 m cells into 2 each. Of the
  remaining 78 cells, the largest needs at most 3.9 m of cut or fill.
* **T5. Terrace joints.** Two blocks of one cell meet along their cut
  chord.
  * Where their solved levels differ by at most `[cockpit] visual_m`
    (0.5 m) they WELD: the chord is an ordinary shared edge.
  * Where they differ by more, the chord carries a declared wall. Two
    pieces go with it:
    * a **riser face** 1 m wide, built by the #951 construction
      (`planar/band_riser`, generalised as `planar/terrace_riser.py`, a
      new family member);
    * a `road_terrace['wall']`-shaped record with `retains`.

    Through that record the existing wall machinery runs unchanged:
    `wall_release`, `solve/wall_cut`, `_wall_step_rows`,
    `publication.wall_terrace_joints`, and then
    `check_grade.DeclaredWallSteps`. The shape label is `flat_terrace_wall`.

### 3.4 Roads between terraces ("flat areas connected by sloping roads")

**T6.** A road keeps its own law everywhere:

* its longitudinal cap (rulesets `service_road`);
* its 2 % cross-section, which is hard (§37 (8));
* its 5 % design ramp grade (`[road_contact] ramp_grade`).

A terrace never bends a road off that law. Per the round-3 design (§4.4,
D3), the road climbs by §37 (6) alone: a terrace edge on a road is a MOUTH,
and its §37 (6) mouth level is the terrace's level (`datum_pred` of its
column, never the DEM). So the road ramps from each terrace it serves,
toward its own ground or toward the next mouth. Two mouths that cannot be
joined within the cap over their route distance follow 20d: the road
reaches the HIGHER, and the lower terrace takes a drop at its kerb (T7).

**T7. The kerb.** At a road kerb where the road and the terrace beside it
differ by more than `visual_m`:

* **Road above the terrace:** the kerb run is a DROP, published as
  `road_terrace['drop']` (D4).
  * Late stations and `gap_follow` skip drop edges, so the terrace never
    follows the road up.
  * The stand-off of the gap sheet is the riser.
  * One `wall_terrace` joint is published per run.
* **Terrace above the road:** this is the mirror case, a retaining wall on
  the terrace side. It uses the same record, with `retains` on the terrace.
* **Shared kerb with no stand-off:** the T5 riser face is built on the
  terrace side of the kerb. A kerb that cannot carry the step stays counted
  as `road_wall_shared_kerb`, as road-edge-drop §4 says.

**T8. Bodies on a terrace.** The object stage is unchanged. It seats each
body on the solved surface under it:

* split per body (20s);
* the highest foot (20f);
* converted objects by their lowest feet (20m).

On a flat terrace this gives every body of the terrace one level, which is
the author's own relation, without re-seating code. A detached groundside
pad inside a terrace is tied to the terrace's column (`datum_group_rows`)
instead of its DEM.

### 3.5 Airside stays king, and terrain-following packs are untouched

**T9. Airside is king.**

* No terrace holds an airside face, a zone face, or the airside bank.
* No row reads a terrace vertex from an airside vertex.
* The frontage tie (T3 (1)) is to a block whose level its airside holds
  fix.
* The safety-area band keeps its graded level at a terrace wall, as it
  does at a road wall (19ad).
* The runway and zone outer edges still go to the raw DEM (15g (B)); a
  terrace never extends past them.
* **Bar:** at HECA, no airside vertex moves more than 0.05 m against main.
  That is the l1088 bar, stricter than the 0.5 m that 19ac accepts.

**T10. A terrain-following pack.** The verdict gates T1–T9 at their single
derivation site (`planar/flat_terrace.py`, called once from the planar
build). With no terrace minted, no consumer sees a `terrace:` ref.

## 4. Consumer census (RULINGS 2026-08-30l)

This census is written before any consumer is edited. The geometry
affected is the groundside cells (held refs `terrace:<k>`), their joints,
and the road mouths on their edges.

### 4.1 The census

| # | reader | reads | change | ruling |
|---|---|---|---|---|
| 1 | `airport/pack_partition` (load) | units, members, parts, feet | the detector's input | unchanged |
| 2 | `airport/flat_pack.detect` (NEW) | partition + DEM | the verdict | THE derivation site of §1 |
| 3 | `airport/flat_site` S2/S4 | DEM relief, seats | excludes `flat_assumed` by construction (§1.3) | unchanged; detector asserts |
| 4 | `airport/footprint_connector.authored_units` §16g | shared-datum groups | same families, read here as `Unit` | unchanged |
| 5 | `classify` roles, `lot_roads`, `airside_edge` §27, `retaining_wall` | source cells | no role changes; terraces are planar | unchanged |
| 6 | `classify/gap_terrace.terrace_cut` | gap pieces by neighbour levels | its parts inside a cell are all held at `D` | unchanged code; its knife carries no step there |
| 7 | `classify` R1 / D1 network-road page | pages a network road runs through | a road face, so a cell BOUNDARY | unchanged (l1088 / round 3) |
| 8 | `planar/platform.platform_split`, `pad_blocks` | unit pads, blocks | pads are never in a cell; the bisection is REUSED for T4 | unchanged code (called) |
| 9 | `planar/landing` PASS 1a (R2 / D2 lens) and PASS 2 collars | fills, `taken` | D2 runs FIRST; an extended fill is a frontage seed (T3 (1)); collars only where no terrace holds | EDITED: collars skip terrace faces |
| 10 | `planar/pad_terrace.pad_terrace_split` | pad and apron | airside | unchanged |
| 11 | `planar/zones`, `constraints/zones` | bands | a cell never takes a zone face; a band at a terrace wall holds its level (19ad) | unchanged |
| 12 | `planar/ribbons._ribbons_pass_c`, `planar/band_riser` (#951) | ribbons, risers | T5 / T7 riser built by the same construction | EXTENDED: `planar/terrace_riser.py` (new file) |
| 13 | `planar/flat_terrace` (NEW) | groundside faces, road family, airside, verdict | mints cells, blocks, held refs, joints | THE derivation site of §3 |
| 14 | `overlay.merge_slivers`, `dissolve_sliver_zones` | faces by role and ref | a terrace riser has its own ref and is never a host | riser exempt (as #951) |
| 15 | `constraints/platform.datum_vertices`, `hold_sets`, `flat_held_refs` | held refs | `terrace:<k>` joins as a held ref with a column; no §30 (6) relief rows | EXTENDED |
| 16 | `constraints/platform.datum_group_rows` | column ties | frontage cells and detached pads tie to their block | EXTENDED (new group source) |
| 17 | `constraints/flat_terrace` (NEW) | terrace vertices | hard `z_v = z_D` rows; the midrange preference | new generator (landing-rows pattern) |
| 18 | `constraints/pad_frontage_gs` §28, `held_terrace_pairs` §28 (6) | groundside frontages | inside a terrace the hold carries the frontage, so §28 rows there drop; pairs across a T5 wall are released | EDITED |
| 19 | `airport/road_ramp._contacts`, §37 (6) mouths and ceiling | mouth levels | a terrace edge on a road is a mouth at the terrace's `datum_pred` (T6, D3) | EDITED (the D3 lane's change, extended to terrace mouths) |
| 20 | `constraints/ramp_runout` (R3) | run-out records | R3 deleted by D3 | none here |
| 21 | `airport/road_ramp.with_road_ramp`, `road_terrace['wall'/'drop']` | wall and drop records | T5 / T7 records join | EXTENDED |
| 22 | `constraints/road_ramp.wall_release`, `_wall_step_rows`, `terrace_rewrite` | wall records | release, lower side bounded | unchanged code |
| 23 | late stations, `constraints/gap_follow` | fixed rings | skip drop edges (D4) AND never move a terrace-held vertex | EDITED (D4 plus one guard) |
| 24 | `constraints/flat_site` preference rows | flat region | cannot coexist (row 3) | unchanged |
| 25 | `solve/wall_cut` (`wall_cut_edges`, `_riser_edges`, `riser_cut_edges`) | wall and riser records | bending cut across terrace joints | unchanged code |
| 26 | `solve/design_ground.ground_datum_vertices`, `design_roles.datum_roles` | per-body datum by role | terrace faces keep groundside roles; whether these read a held ref by role is a SEAM-PROBE item for phase 2 | probe, then rule |
| 27 | `pipeline/publication`: `wall_terrace_joints`, `terrace_joints_ll`, `platform_records` | joints, held refs | terrace joints declared; sidecar `flat_terraces` + `flat_pack` records | EXTENDED |
| 28 | object stage: rebake plan, `seat_records`, `pad_block_seat`, per-body split | solved surface under bodies | reads one level per terrace | unchanged code (T8) |
| 29 | emit `to_osm`, decimators | faces, walls | flat faces; walls as two vertex lines | unchanged |
| 30 | census `within_shape`, `plane_gradient`, `pad_flat`, `hard_conflict`, `hairline_pair`, `groundside_cutback`, `adjacent_ground_step` | emitted surface, joints | declared joints forgiven; the rest are the bars | the bars (§5) |
| 31 | `check_grade._check_no_wall_in_runway_strip` | wall vertices | terrace walls are groundside by T1 | unchanged |
| 32 | `tools/v2_solve_replay` capture, `capture_state` | Airport fields, registries | `flat_pack` re-derived at replay; terrace held refs registered like `PLATFORMS` | EDITED (one field) |
| 33 | twins: `test_no_airport_specific_code`, stage/step/patch code closures, `windows_text_io` and the other whole-tree twins | new modules | `flat_pack`, `flat_terrace` (planar + constraints) and `terrace_riser` join `pipeline/stage_code.py`, `O4_Step_Code.py` and `provenance_code.py` | the registries |

### 4.2 Readers of the D-series

* The round-3 lane owns rows 7, 9 (D2), 19 (D3), 21 and 23 (D4) for the
  access road.
* This spec's lane extends the same rows to terrace mouths and edges. It
  merges after the round-3 PR, never beside it.

### 4.3 Emittability

* A terrace is one flat face set.
* A step between terraces, or between a terrace and a road, is two vertex
  lines at different levels: the riser face (1 m) or the gap sheet's
  stand-off (D4).
* A heightfield mesh carries both, as it carries #951's band riser and
  #809's lower level today.

### 4.4 The access-road round 3, as relayed (folded in)

* **D1:** the page a network road runs through is that road (R1).
* **D2:** the fill runs to the road as a LENS, never a hull and never
  across the road. Strips are held before the collar pass.
* **D3:** the road climbs by §37 (6) alone. R3 is deleted.
* **D4:** the drop is declared.
  * The high-kerb runs are published as `road_terrace['drop']`.
  * Late stations and `gap_follow` skip drop edges, so the low side never
    follows.
  * One `wall_terrace` joint goes per run, and the riser is the gap
    sheet's own stand-off.
* **D5:** an unheld block datum, only if it still binds.

Under a flat-assumed pack, terracing is D1–D4 generalised:

* every pack-content cell is held flat, not only the fills;
* every terrace edge on a road is a D3 mouth;
* every kerb drop is a D4 drop.

## 5. Phased plan

| phase | what | cost | bars |
|---|---|---|---|
| 1 | Detector + record, REPORT ONLY (`[flat_pack] terrace = false`). | twins + ONE HECA closing build | §1.2 reproduced within 0.01 on the six captures. A twin on three synthetic packs: a shared anchor on a 30 m slope gives `flat_assumed`; per-object anchors on the same slope give `follows_terrain`; a shared anchor on flat ground gives `follows_terrain`. Patch bodies byte-identical to main (sidecar adds a record only). |
| 2 | Cells, levels, holds, terrace mouths and kerb drops (T1–T3, T6–T9), on top of the merged round-3 PR. `terrace = true`. | synthetic twin; HECA replay `--from planar`; ONE HECA build | see below |
| 3 | The deep-cell split and the terrace riser (T4, T5). | HECA replay; ONE HECA build | the 73.3 ha cell and the three 10 m cells split; every block within 4.95 m of its DEM; every step over 0.5 m between blocks is declared |
| 4 | Optional: `1302 flatten 1` as a declared witness (Q7). | twin only (no measured airport) | the pack verdict reads it |

**Phase 2 bars at HECA** (the test case; no code names it):

* **The owner sites first:**
  * #712 at 30.1096365, 31.3889978;
  * #1003 near 30.112939, 31.397394;
  * the access road: graded to road rules up to the high terminals, with
    the drop on its low side (20d). Read it from the city end, kerb by
    kerb up to the T3 forecourt.
* **Terraces:** every terrace face within 0.05 m of its level (the
  pavement bar).
* **Bodies:** every body on a terrace within 0.5 m of it.
* **Low side:** the low-side lots and pads keep main's levels within
  0.5 m (the reviewer's finding stays fixed).
* **Airside:** no airside vertex moves more than 0.05 m against main;
  CRITICAL motion is unchanged.
* **Roads:** `road_cross_section` and `pavement_over_road_cap` no higher
  than the round-3 build's.
* **Census:** groundside adjudicated rows fall against the round-3 build.
  No step over 0.5 m between groundside pieces is left undeclared.

**The other airports:**

* **KASE, KCLT, OTHH, KATL** (verdict `follows_terrain`) and CYXY: patch
  body byte-identical. This is the orchestrator's sweep, never a lane's.
* **LEMD** (`flat_assumed`): it changes. Its numbers are reported and the
  owner reads it in the sim (Q1).

**Two rounds per phase** (2026-10-20b): a phase that misses its bars
after two rounds stops and goes to review.

## 6. Owner questions (each with the recommended default)

1. **LEMD measures flat-assumed** (F = 0.955; Aerosoft's own mesh is a
   flat plateau). The brief listed it as following the terrain. Should
   LEMD terrace too?
   *Default: yes.* The rule is general (05e). LEMD becomes the second test
   case, with its own sim read. No LEMD switch is written.
2. **The share bar.** `F >= 0.5` (a majority of the pack's grounded
   feet).
   *Default: 0.5.* The measured gap is 0.955 against 0.0037.
3. **The level of a cell with no airside-tied block.** The options are
   the midrange of its DEM (smallest worst cut or fill), its median DEM,
   or its bodies' highest foot.
   *Default: midrange.*
4. **The depth bound.** A terrace stands at most 4.95 m (the collar drop)
   off its DEM before the cell splits.
   *Default: yes.* It is the same number that says a fill "cannot bank
   down".
5. **Road against terrace.** The road keeps its law and the terrace takes
   the wall. Where two terraces cannot be joined within the cap, the road
   reaches the higher one (20d).
   *Default: yes.*
6. **Cells with no pack content** (OSM-only lots): today's grading.
   *Default: yes.*
7. **`1302 flatten 1`** as a second, declared witness, on its own.
   *Default: yes, but report-only until a test airport carries it.*
8. **Granularity.** One pack-level verdict gates terracing, and families
   only decide where. The alternative is family-level everywhere, which
   would terrace KCLT's two partial families (median miss 1.7 m and
   3.6 m).
   *Default: pack-level.* "the author expected the entire airport to be
   flat".

## 7. Not in this spec

* No engine code. The detector's statistic was measured by a lane scratch
  reading of the captures; phase 1 replaces it with `airport/flat_pack.py`.
* No terrace build was made. The §2 cell spans are read from the planar
  map's DEM samples, not from a solve.
* The round-3 access-road design is folded in from the master's relay
  (§4.4), not from its spec file, which this lane has not seen.
