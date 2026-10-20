# Flat-pack terracing: read a pack that assumed a flat airport, and terrace groundside for it

Lane lflatpack, 2026-10-20. Revision 2 (same day): the owner's answers
59-66 (RULINGS 2026-10-20w-ad) are folded in. Phase 1, the report-only
detector, is implemented on this branch (§1.4); terracing (phases 2-4) is
spec only.

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

* RULINGS 2026-10-20w-ad (answers 59-66 to this spec's first questions):
  * w: terracing needs evidence beyond a flat pack (buildings that cannot
    be seated, steep paved-grade violations); pads seated on real terrain
    are preferred when feasible; LEMD is not a terrace test case;
  * x: a pack is flat-designed when MORE THAN 90 % of its objects sit at
    one level;
  * y: an area with no terminal to match takes the midrange of its ground;
  * z: no fixed 4.95 m split; where to split follows the object, road and
    lot layout, and walls or terraces taller than that are allowed;
  * aa: airside stays fixed; groundside terraces adjust as far as their
    service roads allow within the roads' max grade;
  * ab: areas with no pack objects keep today's grading;
  * ac: the `1302 flatten 1` flag is a second witness (report-only until a
    test airport uses it) and is removed when the airport is modified;
  * ad: flatness is decided for the whole pack, not per object family.

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
planar product is used. The decision is for the WHOLE PACK (20ad).

* **Object.** A member of the partition (one pack resource placement) with
  grounded feet; scatter members and line parts are not objects.
* **Grounded feet of an object.** Its non-scatter, non-line parts' feet
  with authored `y <= feet_y + grounded_band_m` (1.0 m, the S4 below-grade
  magnitude). `feet_y` is `base_profile['feet_y']`, or the lowest foot when
  absent.
* **Drawn height of a grounded foot `f`.** `DEM(object origin) +
  unit.agl_m + y_f`: where X-Plane draws it.
* **The object's level.** The median drawn height of its grounded feet.
* **The level share `L`.** The largest share of the pack's objects whose
  levels lie in ONE window `flat_site.detector.seat_spread_max_m` (3.0 m)
  wide. The window's median level is THE PACK LEVEL.
* **The relief `R`.** `p95 - p5` of the DEM under the grounded feet of the
  objects at that level.
* **Witness 1, seats (20x).** `L > [flat_pack] level_share_min` (0.9,
  "Greater than 90% of objects would all be at the same level") AND `R`
  exceeds the relief floor of the DEM's source class,
  `flat_site.detector.relief_floor_m` (coarse 8.0 m, fine 2.0 m; a lidar
  or unknown class reads the fine floor). Without the relief gate a pack on
  a genuinely flat site reads flat-designed, and nothing about it would be
  wrong.
* **Witness 2, flatten flag (20ac).** The airport block carries
  `1302 flatten 1` (`SceneryPack.flatten_declared`).
* **Verdict.**
  * `flat_assumed` when either witness holds; the record names which
    (`seats`, `flatten_flag`, or both).
  * `no_data` with fewer than `[flat_pack] min_members` (3) objects and no
    flag.
  * `follows_terrain` otherwise.

The verdict is necessary for terracing, never sufficient: a flat-assumed
pack terraces only where today's grading FAILS (§3.0, 20w).

### 1.2 Measured

Measured by the implemented detector (`airport/flat_pack.detect`, this
branch) on the registered captures, through the production loader's
partition and DEM:

* `l786/HECA.pkl` (b57fe46d7), `c971/LEMD.pkl`, `m15/KASE.pkl`,
  `m2/KCLT.pkl`, `m12/OTHH.pkl` and `m5/KATL2.pkl`, all under
  `/Users/noah/XPTerrainBuilderData/.harness/frames/`.

| airport (pack) | DEM class | objects | at one level | **L** | pack level | **R** (floor) | median miss at that level | flatten flag | verdict |
|---|---|---|---|---|---|---|---|---|---|
| **HECA** (TaiModels) | coarse | 249 | 240 | **0.964** | 107.97 m | **33.31 m** (8.0) | 18.07 m | no | **flat_assumed** (seats) |
| **LEMD** (Aerosoft) | fine | 166 | 153 | **0.922** | 595.38 m | **54.81 m** (2.0) | 7.68 m | no | **flat_assumed** (seats) |
| OTHH (Aeroscape) | coarse | 436 | 375 | 0.860 | 3.96 m | 0.00 m (8.0) | 0.03 m | no | follows_terrain |
| KCLT (Nimbus) | lidar | 73 | 38 | 0.521 | 220.06 m | 13.38 m (2.0) | 1.20 m | no | follows_terrain |
| KATL (Nimbus) | lidar | 60 | 16 | 0.267 | 288.94 m | 6.18 m (2.0) | 0.73 m | no | follows_terrain |
| KASE (Aerosoft) | lidar | 187 | 43 | 0.230 | 2,368.91 m | 2.59 m (2.0) | 0.42 m | no | follows_terrain |

* HECA's level is the pack's shared anchor: 379 of its 429 members are
  placed from one anchor (30.112118, 31.412026), where the DEM is 108.44 m.
* OTHH is the case the relief gate exists for. It also places 198 of its
  1,087 members from one anchor and stands 86 % at one level, but its ground
  is flat. Its share is also under the bar.
* The nearest terrain-following pack to the bar is OTHH at 0.860; the
  nearest with real relief is KCLT at 0.521. LEMD clears it at 0.922, a
  margin of 0.022 (13 of its 166 objects off the level).

**The first revision's statistic** (the feet-weighted share of
flat-assumed anchor FAMILIES, with a 4.95 m median-miss gate) read HECA
0.9986, LEMD 0.9554, KATL 0.0037 and KASE, KCLT, OTHH 0. It is replaced by
the object level share, because the owner ruled the bar in objects (20x)
and for the whole pack (20ad); both statistics give the same verdicts.

### 1.3 Findings

* **LEMD reads flat-assumed, and does not terrace (20w).** Its pack
  stands 92 % at one level over 55 m of ground, and Aerosoft ships its own
  mesh that flattens the airport (a plateau at 594.625 m: 2,474 of 2,774
  nodes, memory `lemd-aerosoft-patch-ground-truth`). The owner: "I think
  LEMD does not need terraces". The verdict is not the trigger; §3.0's
  failure evidence is. LEMD's expected evidence is none, and the phase-2
  bar is "LEMD mints no terrace".
* **The `1302 flatten 1` flag.** None of the six packs carries it; 261
  airport entries in the installed Custom Scenery do. It is a strong
  witness (20ac: "a strong clue the author was not planning for terrain
  so we may have to do more terrain adapting to objects than we would
  like"), read and reported now.
* **Flat site and flat pack cannot both hold through the seats witness.**
  The flat-site detector (S2) needs no credible relief; the seats witness
  needs relief above the same floor. A flatten flag can still stand on a
  flat site; there it changes nothing, because a flat site has no failure
  evidence to terrace.

### 1.4 Where it lives (IMPLEMENTED, phase 1)

* `airport/flat_pack.py`: `detect(airport, law) -> FlatPackVerdict`,
  `record`, `log_line`. A pure reading of `Airport.partition`, the DEM and
  `Airport.pack.flatten_declared`; it imports `law` and `model` only.
* `model/airport.py`: `FlatPackVerdict` (verdict, witness, level_share,
  level_m, relief_m, signals) and `Airport.flat_pack` (None before it
  runs); `SceneryPack.flatten_declared`, read by
  `airport/pack.flatten_declared(block)` from the airport's apt.dat block.
* `law/flat_pack.toml` + `law/flat_pack_schema.py`:
  `[detector] level_share_min = 0.9`, `grounded_band_m = 1.0`,
  `min_members = 3`, and the phase gate `terrace = false`. The level
  window and the relief floor are read from `flat_site.toml`, never
  restated. The freeze specs' law-table count guard is 9.
* `pipeline/build.pack_stage` sets it once the partition is read, writes
  the report's `load.flat_pack` record, and says one `[flat-pack]` line.
  `tools/v2_solve_replay.py --capture` does the same, so a capture carries
  it; an older capture lacks it (`None`), and the detector is pure, so a
  reader can recompute it from the pickled partition.
* Nothing grades by it while `terrace = false`. Bar: the patch bodies are
  byte-identical (§5).

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
  * Three more span more than 10 m: 6.5 ha (10.6 m), 6.4 ha (10.3 m) and
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

### 3.0 Failure evidence first (20w): pads on real terrain are preferred

A flat-assumed pack is graded TODAY'S way first: pads and buildings seated
on the real terrain. A cell (§3.1) terraces only when that grading fails
there, by one of these witnesses, each measured on the today-way surface
with the existing instruments and judged at the visibility bars (pavement
0.05 m, ground 0.5 m):

* **E1, a building that cannot be seated:** a pack body in the cell whose
  seat misses the solved surface under it by more than 0.5 m, or a pad the
  pack groups call infeasible (`groups.counts['infeasible']`, per body);
  or a fill that "cannot bank down" (road-edge-drop R2).
* **E2, a steep paved grade:** a groundside pavement or road face in the
  cell with a census row over its cap (`within_shape`, `plane_gradient`,
  `pavement_over_road_cap`, `road_cross_section`) by more than the
  pavement bar.

A cell with no evidence keeps today's grading. This is a TWO-PASS
decision: the evidence needs the today-way solve, so phase 2 reads it from
the stage-1 solve (or the census of a today-way build) and re-runs the
planar terrace mint for the evidenced cells only. The cost (one extra
planar + solve pass on flat-assumed packs with evidence) is a build-time
item for phase 2's brief. LEMD, per the owner, is expected to carry no
evidence and to mint no terrace.

### 3.1 The terrace region and its cells

* **T1. What can terrace.** Groundside faces that are not road-family
  faces, and that lie in a cell with PACK content and failure evidence
  (§3.0). A cell has pack content
  when it holds one of these:
  * a grounded foot of a pack object (the verdict is the whole pack's, 20ad);
  * a pack draped pavement page (`dsf:pol*`) or gap sheet;
  * a detached groundside pad of a pack body.

  A cell holding only OSM lots keeps today's grading (20ab). Never part of a
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
     DEM, `(p5 + p95) / 2` (20y). The preference is priced in the
     `flat_datum`-style preference group, below law and above seam.
  3. **The service roads bound the level (20aa).** Airside stays fixed.
     A terrace's level may move only as far as its service roads allow
     within their max grade: from each road's fixed end (its airside
     contact or its own ground), the road's longitudinal cap over the
     route distance to the terrace's mouth gives an interval; the level is
     the midrange target CLIPPED to the intersection of its roads'
     intervals. A terrace whose roads give no common interval takes the
     level of its most important road's interval (the one serving an
     airside-tied block, else the longest frontage), and the other kerbs
     carry walls (T7).
  4. **Several frontage blocks at different levels** in one cell: the cell
     is cut between them (T4), and each block of the cell takes its own
     frontage.

### 3.3 Splitting deep cells and joining terraces

* **T4. The split follows the layout (20z).** There is no fixed depth
  bound: walls, cliffs and terraces taller than 4.95 m are allowed where
  the layout needs them ("HECA likely requires some cliff/wall/terraces
  greater than that"). A cell is cut into terrace blocks along its own
  layout lines, in this order:
  1. a lot boundary inside the cell (two lots are two terraces when their
     service roads give them different levels, T3 (3));
  2. the outline of an object cluster (`planar/cluster` / one-building
     groups): a cluster is never cut, and the ground between two clusters
     at different seated levels is where their terraces meet;
  3. a mapped kerb, fence or wall object (10-03c: the wall is the step).

  A cell with none of these and with evidence keeps one level. The
  phase-2 lane reports, per cell, the block count and the tallest joint;
  a joint taller than one storey (`low_level_min_step_m`, 3.0 m) is listed
  for the sim read, not refused. At HECA the 73.3 ha cell (34.3 m of
  ground) is where splits are expected; the three cells spanning
  10.3–10.6 m are the next.
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
toward its own ground or toward the next mouth. The road is never moved to
suit a terrace; the terrace moves to suit its roads (T3 (3), 20aa). Two
mouths that cannot be joined within the cap over their route distance
follow 20d: the road reaches the HIGHER, and the lower terrace takes a
drop at its kerb (T7).

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
* **Bar:** airside stays FIXED (20aa): at HECA no airside vertex moves
  more than 0.05 m against main (the pavement bar; stricter than 19ac's
  0.5 m, which covers groundside-caused movement in general).

**T11. The flatten flag is removed when we grade (20ac).** When the
patch grades an airport whose block carries `1302 flatten 1`, X-Plane must
not flatten our graded mesh, so the scenery we write drops the flag. The
engine has no apt.dat writer today (the pack's apt.dat is read, never
written: "never writing the real X-Plane install"); phase 4 names the site
that carries the override (the output pack's own apt.dat for the airport)
in its own census before it is built. No test airport carries the flag.

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
| 2 | `airport/flat_pack.detect` (BUILT, phase 1) | partition + DEM + `pack.flatten_declared` | the verdict, report `load.flat_pack` | THE derivation site of §1 |
| 2a | `airport/pack.signature` | the airport's apt.dat block | `SceneryPack.flatten_declared` | BUILT (phase 1) |
| 2b | stage-1 solve, census instruments | the today-way surface | §3.0 evidence per cell | READ (phase 2), no edit |
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
| 1 (BUILT) | Detector + record, REPORT ONLY (`[flat_pack] terrace = false`). | synthetic twin + ONE HECA closing build | §1.2 reproduced; the twin (`tests/auto_patch_v2/test_flat_pack.py`): a shared anchor over a 30 m slope gives `flat_assumed`, the same objects on their own ground give `follows_terrain`, a shared anchor on flat ground gives `follows_terrain`, the flag alone gives `flat_assumed`, two objects give `no_data`. Patch bodies byte-identical. |
| 2 | §3.0 evidence + cells, levels bounded by the roads, holds, terrace mouths and kerb drops (T1–T3, T6–T9), on top of the merged round-3 PR. `terrace = true`. | synthetic twin; HECA replay `--from planar`; ONE HECA build | see below |
| 3 | The layout split and the terrace riser (T4, T5). | HECA replay; ONE HECA build | every evidenced cell split only along lot, cluster or wall lines; every step over 0.5 m between blocks declared; joints over one storey listed |
| 4 | The flatten-flag removal (T11), with its own census of the writing site. | twin only (no measured airport) | an airport with the flag graded by us ships without it |

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
* **LEMD** (`flat_assumed`, 20w): no failure evidence expected, so NO
  terrace minted and the body byte-identical. Any LEMD cell that does show
  evidence is reported with its witnesses, for the owner, before it is
  terraced.

**Two rounds per phase** (2026-10-20b): a phase that misses its bars
after two rounds stops and goes to review.

## 6. Owner questions — answered 2026-10-20 18:14Z (RULINGS 2026-10-20w-ad)

| Q | asked | ruled | where in the spec |
|---|---|---|---|
| 1 (59) | LEMD terraces too? | w: terracing needs failure evidence; pads on real terrain preferred; LEMD does not need terraces | §3.0, §5 |
| 2 (60) | share bar 0.5 | x: more than 90 % of objects at one level | §1.1 |
| 3 (61) | cell level | y: midrange | T3 (2) |
| 4 (62) | 4.95 m split | z: no fixed number; the layout decides; taller walls allowed | T4 |
| 5 (63) | road against terrace | aa: airside fixed; terraces move as far as their service roads allow | T3 (3), T6, T9 |
| 6 (64) | OSM-only cells | ab: today's grading | T1 |
| 7 (65) | flatten flag | ac: a witness, report-only until a test airport uses it; removed when we grade | §1.1, T11 |
| 8 (66) | granularity | ad: whole pack | §1.1 |

**New questions (revision 2), each with a default:**

1. **Evidence scope.** Is §3.0 evidence judged per road-bounded cell (a
   cell with one unseatable building terraces, its neighbours do not)?
   *Default: per cell.*
2. **A road interval that cannot hold a flat terrace** (T3 (3) gives no
   common level): the terrace takes its most important road's interval and
   the other kerbs carry walls.
   *Default: yes.*

## 7. Not in this spec

* Phases 2-4 are spec only; phase 1 (the report) is the only code.
* No terrace build was made. The §2 cell spans are read from the planar
  map's DEM samples, not from a solve.
* The round-3 access-road design is folded in from the master's relay
  (§4.4), not from its spec file, which this lane has not seen.
