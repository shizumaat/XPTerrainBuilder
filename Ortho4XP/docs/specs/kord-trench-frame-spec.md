# KORD I-190 trench frame: why its decks were "beside a building", and the rule (#2157 family)

Amends `walled-multibridge-frames-spec.md` (W1-W9 stand). Owner 2026-11-19T03:37Z: "There's no
building touching the bridge at KORD. Spend one more round to see if we can understand what's
different here so we can handle it correctly". Spec only: nothing here is implemented or
replayed. Law: RULINGS 10-22n (a deck beside a building), 08-11b / 10-02v (3) (no building, no
pad), 09-14aj (leaves get no pad), 10-30f (3) (walls bound the cut), 11-06 #1903 (a trench
object's floor is the cut), 11-19a, 08-30l, 05e/05g.

Measured on the lwfA capture `/Users/noah/XPTerrainBuilderData/.harness/frames/lwfA/KORD.pkl`
(base 653e21585) by loading it and by reading the three OBJ files; code cited at lwfB
6e0cc2cac under `Ortho4XP/src/auto_patch_v2/`. M = measured here, L = lwfA's report.

## 1. What building46 is (M)

The frame is three placements at one anchor (1178.735, 247.275), heading 50.30, lift 0:

| Placement | File | What it is (authored frame; x along I-190, z across) |
|---|---|---|
| obj14271 | `tunel_solido.obj` | 220 components, y -5.05..+5.96. The WALLS: outer faces at z -33.5 (-36.5 under E) and +46.5, and five 1 m PIERS at z -26.5, -6.5, 4.0, 23.5, 35.5 (twelve wall lines under each deck, six bays); `ATTR_hard_deck`: the two decks W x[-57, -20.8], E x[28.1, 64.3] |
| obj14405 | `tunel_solido_nuevo.obj` | ONE component, 102 triangles, y -5.00..0.00, `ATTR_hard`: the ROAD BED. Flat at y -5.0 between the outer walls (z -33.7 / -36.7..+46.5), terraces and 4,558 m2 of ramp up to y 0 at the ends. No wall, nothing above y 0 |
| obj14272 | `tunel_transparencia.obj` | two zero-thickness sheets at y +0.15, 78,098 m2, `ATTR_layer_group terrain -1`: a texture overlay. Not `genuine` (`airport/obj8.py:683-690`), a leaf, no part in any of this |

**building46 is obj14405 alone: the road bed.** Cluster `unit:21#30`, one member, one body,
floor -5.0, footprint 45,158 m2 (pad 45,157 m2, the same outline). No other placement feeds it;
obj14271's cluster `unit:21#0` is a deck member, not walled, and is dropped as a leaf.

Cause chain:
1. `airport/placement_family.py:659-663`: `walled = tall >= chain_min_height_m and not
   member_is_deck`. `tall` is the part's TOTAL height (2.72 m here, base -5.00), wherever it
   stands. A slab wholly under its own grade reads as a walled body. (KRDU's CTR_TML / NTH_TML
   clusters are deck members, so walled 0 and leaves: that is the whole KORD / KRDU difference.)
2. `geom/cluster_outline.py:572-582` rule 9: tall-base fill 0.86 >= 0.002, passes (total extent
   again).
3. `cluster_outline.py:626-641` rule 10: the VERTICAL test fails, correctly (tallest ABOVE-GRADE
   extent 0.00 < `evidence_min_height_m` 6.0; `geom/pad_evidence.py:155-175` clamps at grade).
   The pad is then VOUCHED by `cluster_building_evidence` (`cluster_outline.py:231-302`), whose
   test is ANY intersection with a v1 footprint-cache ring of role `object`. The rings that
   touch the outline: `dsf:object11`..`18` (the people-mover guideway,
   `kord_metro_highway_paintedmetal.obj`: 316-469 m2 rings 2.9 km round) by 0.7-2.9 m2 each at
   the SE corner, and `dsf:object88`..`93` (the terminal core weld with
   `vias_tren_parqueadero.obj`) by 5.9-52.5 m2 at the NW corner. At most 52.5 m2 of 45,157
   (0.12 %). No OSM building touches it. The road bed's OWN cache ring (`dsf:object2`,
   46,532 m2) is `object_unvouched`: v1 itself read no building there.
4. `classify/evidence.py:941`: the piece is minted `building46`; one cell, 45,157 m2, over
   5,917 of the decks' 6,923 m2 (L).
5. `planar/deck_bridge.py:290-299` `_beside_a_building`: the plan-box centroid of each frame
   member lies outside the piece (the frame is 470 m long, the piece 36 m) and reads role
   `building`: W and E refused, "a building stands beside it in its frame" (L).
6. With the decks refused the basin pass claims the frame (`planar/basins.py:636-637`):
   `floor_z = deepest.solid_min_z` = the DEM AT THE ANCHOR + the object's lowest y. The DEM
   already carries the real trench: 192.80 at the anchor, 192.1-193.8 across the floor under and
   between the decks, 198.3-199.5 on the rims (rim median `R_est` 197.82). So the floor is
   192.88 - 5.05 = 187.83: the object's depth hung under ground that is already the floor.
   That is the 4.94 m (197.82 - 9.99). The right floor, deck zero - 5.05 (about 192.3), is the
   lidar's own floor within 0.5 m.
7. With 22n off (L): two taxi `DeckBridge`s, bottom -5.05, but `_walled_trench`
   (`deck_bridge.py:913-947`) calls `geom/wall_lines.inner_faces`, which takes "the face line
   nearest the deck's middle" on each side (`wall_lines.py:60-64`). The middle is z ~6.5, so
   the pair is the pier faces 4.5 and 23.0: ONE bay, 18.5 x 36.2 = 670 m2 (L: 672 / 368).

## 2. The rules (general; nothing names an airport, pack, file or coordinate)

**K1 — A building rises above its own grade.** A cluster mints a derived pad only when some
component of it rises `[placement] chain_min_height_m` (2.5) or more ABOVE the object's own
grade: `PadEvidence.tallest_extent_m` (the clamped, resource-folded extent the vertical test
already reads) `>= pad_admission(law)`'s walled height. A cluster under it is a road bed, a
trench, a pit floor or a retaining wall: it mints nothing, counted `below_grade` and listed
with rule 9 / 10's refusal row. The test stands in `cluster_outlines` BEFORE rule 10's vouch
(OSM, cache or name): a vouch says a building is near, never that a slab under the ground is
one. One derivation site, so the mint, the census (`constraints/cluster_pad`) and
`planar/apron_shelf` read one verdict. An unmeasured cluster (`evidence is None`) is not
refused, as today. `placement_family`'s `walled` (the CHAINING reading) is NOT changed, and
neither is the vouch's any-intersection test (HECA's measured basis); 22n is not changed.

What this says about the frame kinds: walls below grade and a floor below grade are a CUT
(the trench passes read them); a hard deck at grade is a DECK (already never walled); a
zero-thickness sheet is nothing. Only a body standing above the ground is a building.

**K2 — The trench's walls are the pair at the edge of the frame's floor; piers stand in it.**
Under a span and along an open stretch, the wall pair is read against the FRAME'S FLOOR across
the road: the extent `(f_lo, f_hi)` of the near-horizontal solids of every frame member within
`_REACH_FRAC` of the bottom over the stretch. The wall on each side is the wall line standing
at that edge (the innermost line not inside the floor: `u_a` = the least line `>= f_lo - bin`,
`u_b` = the greatest `<= f_hi + bin`). A wall line with the frame's floor on both sides is a
DIVIDER (a pier): never the trench's wall, never a rim, never an end of a wall-pair span
(`deck_span_cut._wall_spans`). A frame that models no floor across the stretch keeps today's
nearest-the-middle pair, unchanged. One derivation: `inner_faces` takes the floor extent, and
`deck_bridge._walled_trench` (both calls) and `model/deck_bank.banked` pass the same one;
`deck_walls` reads the floor extent beside the faces.

**K3 — The pit pass does not see this frame; its depth law is not changed.** W1's precedence
(a walled bridge frame is `deck_bridges`', its placements `taken` from basins) plus W5 (floor =
the span's zero less its own bottom) remove `basin:0`. The basin floor law itself
(`basins.py:636`) is left alone: of 97 basins in the data repo's debug logs 30 differ by more
than 1 m between "deepest solid" and "plate y" for unrelated reasons, so a general change has
no measured basis. The KORD signature (anchor inside the floor, DEM at the anchor more than
`cover_flush_m` under the rim) is recorded for the next pit that shows it; KDAL `basin:0`
(anchor inside, -5.34 vs plate -3.56) is the only other one in the logs.

## 3. Consumer census (08-30l)

| Pass (`file:line`) | Reads | Effect |
|---|---|---|
| `geom/cluster_outline.cluster_outlines` :371, before :626 | `ev.tallest_extent_m`, admission | K1: the new refusal, counted and listed |
| `law/tables.pad_admission` | `chain_min_height_m` | carries the walled height (no new constant) |
| `classify/evidence._cluster_pads` :640, `_pads` :828-941 | cluster pieces -> `building{N}` | KORD: 2 pads fewer, refs after them renumber; fallback half: `dsf:object2` is `object_unvouched` with no OSM, so no fallback pad replaces it (verify, stop 2) |
| `constraints/cluster_pad.py:156` | same call | census agrees with the mint by construction |
| `planar/apron_shelf.py:102` | same call (small clusters) | a below-grade cluster fronts no shelf |
| `tools/pad_gap_diff.py:51`, `tools/pack_stage_profile.py:284, 364` | same call | inherit; no edit |
| `planar/overlay` airside clip, `constraints/pads`, `pad_relief`, `foot_rows`, slope pads | pad faces | nothing left to read over the trench; its piers seat by the deck / trench path |
| `deck_bridge._beside_a_building` :290, `overpass_deck.py:217`, `free_bridge.py:462`, `airport/bridge_witness` | role `building` at member centroids | unchanged code; no building cell under this frame any more |
| `geom/wall_lines.inner_faces` :38 | faces, reach | K2: floor extent |
| `deck_bridge._walled_trench` :934, :943; `deck_cut` :760, `deck_banks` :826, :846 | the pair | outer pair; floor spans all bays |
| `model/deck_bank.banked` :72 | same test | same pair (a frame with piers and no outer wall on a side is banked there) |
| `planar/deck_walls.wall_faces` :57 | frame triangles | also returns the floor extent |
| `planar/deck_span_cut._wall_spans` :78 | consecutive wall lines | dividers are not span ends |
| `planar/basins`, split-level, sunken-road, wall-corridor | candidate placements | W1 `taken` (unchanged from the parent spec) |

Heightfield: no new face kind. The trench floor becomes one strip between the outer walls per
span and stretch instead of one bay or a 44,748 m2 pit.

## 4. Bars at KORD (replay; drawn once at integration, 17r)

1. No `building` cell under the frame: `building46` gone, K1 lists exactly `unit:21#30`
   (45,157 m2) and `unit:12#1947` (338 m2).
2. Two `DeckBridge` pieces (W 3,619 m2, E 3,304 m2), family taxi, bottom -5.05; `basin:0` absent.
3. Both decks flush with the taxiway: every end line <= 0.04 m (`deck_end_flush`).
4. Floor under each span = that span's zero - 5.05 within 0.05 m, and within 0.5 m of the DEM
   there (192.1-193.8). Floor width = the outer pair: W 80.0 m (z -33.5..46.5), E 83.0 m
   (-36.5..46.5), so about 2,900 / 3,000 m2 against 672 / 368 today; the 48.9 m stretch
   between the decks open sky between the same walls.
5. Clean cut: `walled_span_clean` 0, no pavement, centreline or pad vertex inside either span
   cut; the five piers stand in the floor and raise no rim.
6. Rebake plan (diff the plan, #625): W and E each seated on its own end lines (lwfB's
   `deck_rings`); obj14405 and obj14272 ride the frame; no member seated on a pad.

## 5. Protection (K1 measured here on each capture; K2 predicted)

K1, admitted cluster pads whose tallest above-grade extent is under 2.5 m:

| Capture | Pads | Would stop being a building |
|---|---|---|
| KORD `lwfA` | 74 | 2: `unit:21#30` road bed 45,157 m2 (41.979364, -87.893640); `unit:12#1947` `concreto_parqueadero.obj` 338 m2, floor -3.6, +0.82 above grade (41.980738, -87.895952) |
| KRDU `lkrdu` | 31 | 0 (CTR_TML obj143 and NTH_TML obj137-139 clusters are already leaves: above grade 0.0-2.17 m, no pad today) |
| KBNA `lkbna16` 75, OTHH `lkbna2` 64, LGAV `llgav3` 46, OMDB `lomdb` 123, KDEN `lkden2` 36, HECA `lheca4` 175, KEGE `lkege3` 14, BIKF `lkbna14` 52, EDDF `deckB` 137 | | 0 each |

So every protected pad set is identical and their `building{N}` refs do not move. The lane
re-runs the same read on its tree (`--pad-read`) and replays `--from planar` at KBNA, OMDB,
LGAV, OTHH: no vertex > 0.1 m. K2 changes a pair only where a frame models a floor wider than
its nearest-the-middle pair: print the pair before / after for every walled `DeckBridge` on
the protected captures; KBNA taxiway L (172.0 +- 0.1, its open stretch open sky) must be
identical.

## 6. Replay commands (from `Ortho4XP/`)

    K=/Users/noah/XPTerrainBuilderData/.harness/frames/lwfA/KORD.pkl
    venv/bin/python tools/v2_solve_replay.py --replay $K --from classify --pad-read \
        --site 41.979364,-87.893640                 # K1: pad read, the ref under the trench
    venv/bin/python tools/v2_solve_replay.py --replay $K --from planar \
        --json OUT/kord.json --solved-out OUT/kord.pkl          # ~10 min (planar 274 s)
    venv/bin/python tools/deck_probe.py OUT/kord.pkl --object dsf:obj14271 --json OUT/decks.json
    venv/bin/python tools/v2_rebake_replay.py plan ...           # the object stage, plan diff

Protected captures: section 5's names under the same `frames/` root. Synthetic first: a
one-component slab y -5..0 beside a cache ring that clips its corner (K1); a frame with two
outer walls, three piers and a floor plate, and the same frame without a floor (K2).

## 7. Order, stop conditions, estimate

Order, one variable per replay: K1 -> `--pad-read`; then the parent spec's W1 + W3 + W5 with K2
-> planar replay; W8; protection after K1 and after K2.

Stop and report, no tuning:
1. K1 refuses any pad on a protected capture, or more than the two listed at KORD.
2. After K1 any `building` cell still stands under the frame (a fallback pad took its place),
   or 22n still refuses W or E: report the cell's ref and source; do not touch 22n.
3. After K2 either floor is not the outer pair (width off by more than 1 m), or any protected
   walled deck changes its pair.
4. End lines flush but the floor more than 0.5 m off the DEM floor: report the profile.
5. `_wall_spans` or 18i cuts either KORD deck into bays.
6. A second miss goes to the owner (11-11c). No closing tile build; never raise the lane cap;
   delete scratch builds on report.

Estimate, one Opus lane, effort high: K1 ~25 lines + 2 tests, K2 ~50 lines + 2 tests, on top
of the parent spec's planar half (W1, W3, W5, W8; ~150 lines of its lane A). KORD replays ~10
min x 4, protection in parallel: 3-4 h wall. No new public symbol beyond one `inner_faces`
argument and one counter. Build time: K1 is a scalar test per cluster, K2 one projection per
walled deck; neither is measurable against the 60 s budget.

## 8. Not verified

- That K1 alone lets `deck_bridges` read W and E: inferred from lwfA's 22n-off probe; no replay
  with the pad removed was run.
- The fallback half after K1 (stop 2) and the renumbered refs' downstream readers at KORD.
- K2 on any capture: the wall lines and floor extents above are read from the OBJ files with
  `deck_walls`' thresholds, not through `wall_faces`; the skewed low-side wall along the open
  stretch (z -33.5 to -36.5) relies on `wall_lines`' merged bins.
- The decks' areas, the 5,917 m2 overlap, bottom -5.05 and 672 / 368 m2: lwfA's report.
- `unit:12#1947`'s loss of its 338 m2 pad is not judged here (a half-sunk parking structure).
- The part height 2.72 m against the component's own -5.00..0.00: the partition's reading,
  not traced.
- The KDEN capture is `KDEN_coarse.pkl`; old captures carry cluster evidence stamped at their
  own base.
