# seat610 — notes (issues #610 KCLT east side, #625 KASE Atlantic FBO: bodies of one building at two zeros)

## RESUME HERE
* Branch `claude/seat610` (worktree `.claude/worktrees/seat610`) off origin/main 89693e99d (app 1.0.389).
* Scratch `<scratchpad 466e18b3…>/seat610/`: `build_KASE_main.log` / `build_KCLT_main.log` (the two REFUSED
  tile builds), `osr_kase_graded.{json,txt}` (dry run of the app's KASE plan on the graded surface, `--units-with FBO`).
* Step 1 (reproduce on mesh ground): the harness tile builds REFUSE on the corpus (below). The owner's app meshes
  exist read-only in the X-Plane install (`/Users/noah/X-Plane 12/Custom Scenery/zOrtho4XP_+39-107/Data+39-107.mesh`
  18:55 and `zOrtho4XP_+35-081/Data+35-081.mesh` 16:32, 2026-10-12 — the meshes the app's placement records
  `o4_v2_placement_{KASE,KCLT}.json` (engine 1.50.1835 = app 1.0.388, 18:55 / 16:33) were seated on), so the
  placement stage is REPLAYED against them offline (`tools/obj8_split_report.py --mesh`, the near-fit extended).

## Step 1 — the two harness tile builds REFUSE on the corpus (master's refresh, verbatim)
`build_airport.py KASE --tile 39 -107 --steps "1 vector,2 mesh"` (rc 1, 8.7 s):
```
REFUSING: 1 artifact(s) are MISSING from the shared data repo, and building would fetch or regenerate them as a SIDE EFFECT:
  [dem] /Users/noah/XPTerrainBuilder/.claude/worktrees/seat610/Ortho4XP/Elevation_data/+30-110/N39W107_bathymetry_band
      the coastal bathymetry band under the MASKS gating (masks_use_DEM_too=auto) — the step-1 prefetch / step-3 masks would fetch cells, record negatives or rebuild the mosaic mid-build
    --refresh-data dem
```
`build_airport.py KCLT --tile 35 -81 --steps "1 vector,2 mesh"` (rc 1):
```
REFUSING: 1 artifact(s) are MISSING from the shared data repo, and building would fetch or regenerate them as a SIDE EFFECT:
  [dem] Elevation_data/**/N35W081_airport_insets/KVUJ_*.tif [stale]
      STALE airport elevation inset .../Elevation_data/+30-090/N35W081_airport_insets/KVUJ_usgs3dep.tif — it was cut for -80.178694,35.390689,-80.121899,35.440769 but KVUJ now requires -80.178649,35.390706,-80.121932,35.440780, so the build would RE-CUT it (--refresh-data dem)
```
Not refreshed here (owner e9daef5: refreshes are explicit, the master's). The closing tile builds of this lane
need `--refresh-data dem` on both tiles first.

## Step 1 — KASE Atlantic FBO as the APP wrote it (mesh ground, `o4_v2_placement_KASE.json`, engine 1.50.1835)
Unit `unit:121` (rebake plan): FBO_1 … FBO_8, one anchor 39.223149,-106.866661. Zero = surface_z − y_zero.
| body | feet | zero | written reason | ground under its own feet (zero − ground_off) |
|---|---|---|---|---|
| FBO_3 b0 | 30 | **2362.62** | §16g unit fu:121:909@ground of 2 members on its median ground at 2362.62 (own ground −0.08) | 2362.25 |
| FBO_3 b3 | 16 | 2362.62 | same unit (own ground −0.01) | 2362.55 |
| FBO_6 b0 | 3 | 2362.62 | same unit (own ground −0.50) | 2362.12 |
| FBO_6 b3 | 28 | 2362.62 | same unit (own ground −0.01) | 2362.59 |
| FBO_3 b2 | 4 | **2362.11** | §16c (7) bound to FBO_3__b0 (own ground −0.22 m) | 2361.89 |
| FBO_3 b4 | 4 | 2362.11 | §16c (7) bound to FBO_3__b0 (own ground +0.15 m) | 2361.96 |
| FBO_6 b1 | 15 | 2362.11 | §16c (7) bound to FBO_3__b0 (own ground +0.20 m) | 2362.11 |
| FBO_6 b2 | 4 | 2362.11 | §16c (7) bound to FBO_3__b0 (own ground +0.28 m) | 2361.83 |
| FBO_3 b1 | 8 | **2361.33** | surface at the body's zero (no unit, not bound) | 2361.12 |
| FBO_1/2/5/7/8 b0, FBO_6 b4 (roofs, footless) | 0 | 2362.62 | carried by FBO_3__b0 (§16c (7) bound by contact / rests on it) | — |
| FBO_4 b0 (line) | 4 | 2362.54 | surface at the body's zero | — |
Separations inside ONE building: roofs/hosts 2362.62 vs the four bound bodies 2362.11 = **0.51 m**; vs FBO_3 b1
2361.33 = **1.29 m**. All anchors of the four bound bodies sit at ONE lat/lon (39.223199,-106.866690) that is NOT
FBO_3 b0's written anchor (39.223076,-106.866821): they carry a COPY of the senior's anchor taken BEFORE the §16g
unit seat moved the senior.
Dry run on the graded surface (`osr_kase_graded.txt`): every FBO body at one zero (§14 spread 0.02 m), the senior
is FBO_6__b1 there — on flat graded ground the pre-seat and post-seat zeros coincide, so the instrument is blind.

## Step 1 — KCLT east side as the APP wrote it (`o4_v2_placement_KCLT.json`, 16:33; numbering ≠ kclt608's sw17)
| owner-site (kclt608 sep) | bodies within 25 m: zero / reason |
|---|---|
| 35.2209695,-80.9294107 (1.31) | `003_ALB b0` 48 ft **223.17** "surface at the body's zero" (NO unit) ↔ roof `001_ALB b0` footless **223.47** "footless_carried_by_unit fu:3:506/host … the carrier 003_ALB__b0 stands −0.30 m off" ↔ roof `001_ALB b23` 223.17 carried by 003_ALB__b0; `003_ALB b1` 4 ft 222.40 low-side foot (spread 0.86) 20 m off |
| 35.2109690,-80.9300226 (0.77) | `005_ALB b3` 4 ft **216.71** low-side foot (spread 5.83) on pad building41 ↔ roof `001_ALB b37` **217.50** carried by 005_ALB__b5 (§16c (7)); `005_ALB b4` 32 ft 217.58 unit fu:3:624/host@pad building40 |
| 35.2103367,-80.9301051 (0.64) | `005_ALB b5` 28 ft 217.50 unit fu:3:628/host@pad building36; `002_ALB b27` 2 ft 217.25 bound to 005_ALB__b5 (own −0.01); roof `005_ALB b23` 216.78 footless_carried_by_unit fu:3:213 "carrier 005_ALB__b5 stands +0.72 off" |
| 35.2063650,-80.9314325 (0.58) | `005_ALB b16` 128 ft 216.32 unit fu:3:253@cluster_pad building17 + roof `001_ALB b8` 216.32 — ONE zero in the app record |
| 35.2147134,-80.9314928 (0.56) | `008_ALB b4` 8 ft 223.30 unit fu:3:855/host@pad building62; roof `001_ALB b51` 223.30 (fu:3:506/host contents); roof `001_ALB b61` **222.76** carried by 008_ALB__b2 |
| 35.2129824,-80.9327807 (008 b14 +1.21) | `008_ALB b14` 4 ft **219.81** low-side foot (spread 1.95), ground_off +1.21 ↔ roof `001_ALB b36` **222.13** carried by 008_ALB__b9 (unit fu:3:58@pad building55 222.13) |
| 35.2011746,-80.9308541 (003 b21/22 +1.11) | `003_ALB b21` 205.50 / `b22` 205.83, both low-side foot ground_off +1.11; roof `001_ALB b53` 203.43 carried by 003_ALB__b20 20 m off |
| 35.2177862,-80.9296717 (002 b5/b6 +0.87) | `002_ALB b5` 3 ft 213.62 unit fu:3:162@ground (ground_off +0.87) + `007_ALB b1` 213.62; `002_ALB b6` 214.01 fu:3:163@ground (+0.87) + `007_ALB b3`; `007_ALB b2` 84 ft 214.37 fu:3:25@pad building74 |
| 35.2144152,-80.9309725 (awning? 3.44) | `001_ALB b51` roof 223.30 (fu:3:506/host contents), `004_ALB b36` footless 223.47 (fu:3:506/host contents, "carrier 008_ALB__b2 stands −0.71 off"), `002_ALB b12` 1 ft 223.47 fu:3:506/host@ground, `005_ALB b1` 4 ft 219.86 fu:3:613/host@pad building57 |
| 35.2181202,-80.9314641 (awning? 2.52) | `004_ALB b9` 8 ft **213.77** low-side foot (spread 0.50) ↔ roof `001_ALB b55` **214.26** carried by 004_ALB__b5 (fu:3:440/host@ground 214.26); `004_ALB b10` 12 ft 213.38 fu:3:451/host@ground |
Class: in every pair one body is a LEAF (short, in no `fu:` unit: "surface at the body's zero" / "low-side foot" /
"§16c (7) bound to …") beside a HOST seated by §16g, and the roof over both rides one of them.

## MECHANISM (hypothesis from the records + code; to be confirmed by the mesh replay)
`placement_plan.build_splits` per unit: (1) `placement_atom.bind_unit` (§16c (7)) hands every body the plan's
ε-contact graph links a BY-VALUE COPY of its senior's anchor (`_dc0.replace(sc.anchor, …)`), refusing a FOOTED body
whose own zero is > `[cockpit] visual_m` 0.5 off the senior's (12ap); (2) THEN `footprint_unit.bind_footprint_units`
(§16g) re-anchors every candidate whose pids are in a plan-wide `fu:` unit onto the unit's datum — the units are
chained over WALLED bodies only (`chain_min_height_m`), so a short body (plate, low wall, posts, awning) is a LEAF in
no unit and `_bind_plan_wide` skips it (`if not hit: continue`). The bound leaf keeps the senior's PRE-SEAT zero; the
senior moves to the unit datum. On the graded surface the two coincide (flat); on the mesh they differ by the slope
between the senior's low-side foot and the unit's median — KASE 0.51 m. A leaf the bind REFUSED (own ground > 0.5 m
off the senior: FBO_3 b1 at 0.78) stays on its own ground, 1.29 m under the building's datum. KCLT east side: the
same two outcomes (bound-then-stranded, and refused-then-own-ground) around hosts seated by §16g on pads/ground.

## Step 1/2 — MECHANISM CONFIRMED BY INTERVENTION (the app's own meshes, replayed)
Instrument: `tools/obj8_split_report.py --mesh Data+XX-YYY.mesh` (near-fit extended, INDEX row; the app's own
adapter `engine_v2.mesh_placement_sampler` factored out of `rebake_after_mesh` and shared). On
`Custom Scenery/zOrtho4XP_+39-107/Data+39-107.mesh` the replay of the app's KASE plan reproduces
`o4_v2_placement_KASE.json` ANCHOR FOR ANCHOR (same lat/lon, y0, reasons: `osr_kase_mesh.txt`); KCLT likewise
(`osr_kclt_mesh.json`, 551 bodies). `<scratch>/run_base.py` runs the same tool file over MAIN's engine
(roads609base worktree = 89693e99d) for the base arm — proven equal to the main-code run on KASE.
* KASE FBO, main: FBO_3 b0/b3 + FBO_6 b0/b3 = unit `fu:…@ground` 2362.62; FBO_3 b2/b4 + FBO_6 b1/b2 "§16c (7) bound
  to FBO_3__b0" at **2362.11** — their anchor (39.2231989,-106.8666896, y0 +0.01) is the senior's anchor BEFORE the
  §16g unit seat moved it to (39.2230757,-106.8668214, y0 −0.08); FBO_3 b1 (the 4 POSTS, comps 3/8/9/21: 0.6 m
  square, 1.90 m tall, 4 feet each; 2 ε-contacts, both with the canopy FBO_5 b0) "surface at the body's zero"
  2361.33 — refused by 12ap (0.78 > visual_m 0.5). The canopy FBO_5 b0 (comp 22, base_y 3.15, 39.223003..39.223264)
  stands over EVERY footed FBO body (fraction 1.0), the posts included.
* Intervention A (`follow_seniors`): the bound bodies take the senior's FINAL anchor → b2/b4, FBO_6 b1/b2 at 2362.62.
* Intervention B (the roof witness in `unit_rigid`): a refused footed body under an elevated body of the cluster that
  also stands over a kept body is one building → FBO_3 b1 bound → 2362.62. Result: EVERY FBO body at ONE zero
  2362.62 (`osr_kase_mesh_arm5.txt`); the posts' feet then stand 1.29–1.50 m under the canopy's building level
  (ground 2361.1 under the NE corner): the float the terrain is to adapt (no pad at the FBO — design-stage).
* The graded dry run (`osr_kase_graded.txt`) shows the pre-seat and post-seat zero equal (flat) — blind by construction.

## THE RULE (general; `airport/placement_atom.py`, `placement_plan.py` one call)
1. **A BOUND BODY FOLLOWS ITS SENIOR** (`follow_seniors`, after the §16g unit seat and the viaduct seat): every
   candidate the §16c (7) bind put on a senior (`cluster_out`, published by the bind) re-takes the senior's anchor
   when its zero differs. THE UNIT SEAT LEADS the cluster: the lead is the senior when it carries `unit_seat`, else
   the unit-seated member with the most feet, else the senior (KCLT `003_ALB` b10, a unit HOST at 210.14 bound by
   feet to a 4-foot leaf at 209.69: the leaf follows UP). Two unit seats at two zeros in one cluster are two units
   touching (or one unit cut by level, 10n (3)) and each keeps its own (`bound_unit_seats_kept_apart`).
   `_take_senior` is the ONE write both the bind and the follow make.
2. **THE ROOF WITNESS** (in `unit_rigid`, after 12ap's ground test): "one building" vs "two buildings that touch"
   is read from the ROOF — an ELEVATED body of the rigid cluster that stands over the refused body AND over a body
   the cluster kept is one roof over one building, and the body under it is bound (`bind_kept_under_one_roof`)
   while its step to the senior is under `[terrace] pad_terrace_floor_m` (1.0 m, RULINGS 2026-09-30i: under it a
   level difference WELDS; at terrace size it is the terrain's to adapt and the body keeps its own ground —
   HECA T3's doors on the ground 10 m under the pad's roof, KCLT `003_ALB` b17/`002_ALB` b48 1.38 m). A roof that
   stands over REFUSED bodies only is that body's own roof — two buildings that touch — and rides the body it
   stands on, never the senior (`roof_rides_its_own_walls`), so no roof is written above its own walls (KCLT
   35.2109690,-80.9300226: roof `001_ALB` b57 217.50 → 216.71 onto `005_ALB` b3).
   Witnesses measured and rejected: contact COUNT/length (the posts touch only the canopy: 2 contacts; a GSE box
   row touches box to box), same member/row (10n (2) forbids it), plan proximity alone (the 12ap boxes touch).
3. **REFUTED, deleted:** releasing an elevated body whose union with a touching host the 300 m span bound refused
   to the carrier search — it released 1,798 of KCLT's elevated bodies (every roof chain has such a contact) and
   the 0.38 / 0.30 sites did not move.

## KCLT east side — owner sites on the app mesh, main → branch (`r4_site.py`; app-record numbering)
| site | main | branch |
|---|---|---|
| 35.2209695,-80.9294107 | wall `003_ALB b0` 48 ft 223.17 own; roof `001_ALB b0` 223.47 (contents of fu:3:506/host, "carrier 003_ALB b0 −0.30"); roof b23 223.17 on b0 | UNCHANGED 0.30 — see residual (c)/(e) |
| 35.2109690,-80.9300226 | `005_ALB b3` 4 ft 216.71 (low-side foot, spread 5.83, pad building41); roof `001_ALB b37` **217.50** over it (rides host b5) | roof on its walls: **216.71**; b3 ↔ host b5 (pad building36, 217.50) 0.78 = two pads, two buildings |
| 35.2103367,-80.9301051 | `002_ALB b27` 2 ft 217.25 bound to b5; roof `005_ALB b23` 216.78 (contents of fu:3:213) | b27 follows b5 to **217.50**; roof b23 still 216.78 — residual (b) |
| 35.2063650,-80.9314325 | one zero 216.32 | one zero |
| 35.2147134,-80.9314928 | host `008_ALB b4` 223.30; roof b61 **222.76** | roof b59 223.47 (on 002 b12 host) ↔ b4 223.30: 0.54 → **0.17** |
| 35.2129824,-80.9327807 | posts `008_ALB b14` 4 ft 219.81 (spread 1.95, ground_off +1.21); roof `001_ALB b36` 222.13 (rides b9 on pad building55) | UNCHANGED: posts have NO ε-contact with the roof or b9 (0 pairs; boxes overlap 46/96 m) — not in any cluster; the roof witness cannot see a body the contact graph never links. THE AWNING CANDIDATE: 35.2129379,-80.9327134 |
| 35.2011746,-80.9308541 | `003_ALB b21/b22` 205.50/205.83 low-side foot, ground_off +1.11 (no roof in reach) | unchanged |
| 35.2177862,-80.9296717 | `002/007_ALB` units fu:3:161/162/163@ground 213.17/213.62/214.01, ground_off +0.87 (3-ft bodies) | unchanged (unit seats; §9 median) |
| 35.2144152,-80.9309725 | roof `001_ALB b51` 223.30 (contents of fu:3:506/host), `004_ALB b36` footless 223.47 | both at 223.47 now (b36 bound by contact) |
| 35.2181202,-80.9314641 | `004_ALB b9` 8 ft 213.77 (spread 0.50); roof `001_ALB b55` 214.26 on `004_ALB b5` (fu:3:440/host 214.26) | UNCHANGED 0.49: b9 has 0 contacts with the roof (b51 arm numbering) and with b5; second awning candidate 35.218182,-80.931399 |
| 35.2040107,-80.9315651 | `003_ALB b17` 207.64 own; `002_ALB b48` 206.26 low-side foot (+0.89); one roof over both | capped (1.38 > 1.0): unchanged; uncapped it bound b17 to 206.26 = buried 1.51 m at its feet |
Touching pairs ≥ 0.3 m airport-wide (`rebake_plan_diff separations`): 37 → **31** (east side 11 → 8); bodies moved > 0.05 m: **6** (all ≤ 0.45 m, every one a leaf following its building's unit seat); `pad_level_units_split` 1 = 1.

## RESIDUAL CLASSES at KCLT (not this rule's; numbers for the master)
(b)/(d) **contents lift across two pads**: a footless roof whose parts are unit U's CONTENTS (#10 S6) is seated at U's
datum though it rests on a host of ANOTHER unit — `005_ALB b23` 216.78 (fu:3:213, pad building37) over host
`005_ALB b5` 217.50 (fu:3:628/host, pad building36) = 0.72 at 35.2104971,-80.9299566; `001_ALB b50` 210.45
(fu:3:23) over host `003_ALB b10` 210.14 = 0.31 at 35.2176929,-80.9270489. §16a (1) says a roof over two
buildings is cut per carrier; `contents_seat` seats the whole piece on one unit.
(c)/(e) **the coarsened chain and the 300 m span bound**: §9 coarsens bodies at one zero within `coarsen_reach_m`
(100 m) into ONE body, so a hangar row on one pad is one 92-foot body ~450 m wide (`008_ALB b7`); the roof
`001_ALB b11` touching it (22 contacts) cannot union (483 m > `UNIT_CLUSTER_SPAN_MAX_M` 300) and rides the chain's
senior `002_ALB b10` 0.38 m up (35.2140963,-80.9317748); `003_ALB b0` (48 ft, 138 m) ↔ roof `001_ALB b59`
(162 m, 1 contact) union 860 m → the roof rides a 1-foot host `002_ALB b12` 0.30 m up (35.2209695,-80.9294107).
(f) **no contact at all**: the two awning candidates (posts with 0 ε-contacts to their roof: the pack authors the
posts and the canopy with a gap) — the contact graph is the only witness the bind has; a plan-overlap witness
(§14 (3) `bind_plan_overlaps` is per member) would be a second rule.
(g) **one building on > 1 m of slope with no pad** (b17/b48): no single zero within the visual bar; design-stage.

## Step 4 — APPROVED AIRPORTS on the app's own meshes (sw20 plans + graded, main engine vs branch cd248a93d; `rebake_plan_diff zeros`, tol 0.05)
HECA (`Data+30+031.mesh` 16:36 2026-10-12; 3,166 bodies): **40 bodies move > 0.05 m, worst +10.59** (`zeros_heca2.json`);
bands > 2 m: 6, 1–2: 7, 0.5–1: 7, 0.3–0.5: 3, 0.05–0.3: 17. Classes: 20 were ALREADY bound and now FOLLOW their
senior's unit seat (`door.obj` b6 91.20 → 101.79 at 30.1139630,31.3968298 — bound to `T3_14` b0 whose unit seat is
the T3 pad 101.79 (#627's +9.75 fill): the door was left on the ground 10 m under the wall it is cut from;
`concrete_3`/`building_texture_4` 66.99 → 68.57 at 30.1286009,31.3996681; four `building_texture*`/`T3_39` 90.73 →
89.63 at 30.1196650,31.4057788; `concrete_1` b1 71.69 → 70.76; `T3_17` b2 83.46 → 82.81); 12 own-ground → bound by
the roof witness ≤ 1.0 m (`concrete_1` b2 82.37 → 80.87 at 30.1195588,31.3966684; `Plastic` b38/b37 79.99/79.68 →
79.03 at 30.1245823,31.4048085; `concrete_1` b0 68.10 → 67.29; `T3_48` b3 71.94 → 71.21; `T3_9` b1 95.88 → 96.53
at 30.1092715,31.3878175); 7 carried bodies whose cluster senior changed (`T3_37` b3 90.20 → 86.08 at
30.1188537,31.4072591; `building_texture` b75 90.22 → 94.31 at 30.1157820,31.4095375; `building` b36 82.81 → 80.56;
`BLUE` b0 75.36 → 77.40); 1 `metal_strip_1_yellow` b69 89.75 → 92.21. Counts: roof witness kept 96, roofs riding
their own walls 745, followed 41, unit seats kept apart 143, 12ap refusals 441 → 345. UNCAPPED (first arm,
`zeros_heca.json`): 60 movers, 31 own-ground → bound, the same +10.59 worst.
OTHH (`Data+25+051.mesh` 17:35; 2,737 bodies): **18 bodies move, worst −2.47**: the five `Bridge_01` clutter/LOD
pieces carried by `OTHH_Bridge_01_LOD0_000` b0 1.95 → −0.53 at 25.2561479,51.6167982 (their senior's cluster changed
— a bus-bridge deck, 12m-approved: OWNER); `Bridge_01_LOD0_003` b0/b2 1.15/2.67 → 1.95 (bound to b1); five
`Terminal_Parking_002/004` pieces 4.48 → 3.96 at 25.2596441,51.6152845 (follow the `Parking-Right_006` b1 unit seat);
`FuelFarm_03` b3 3.50 → 3.96; ATC tower b1 3.59 → 3.86; `Fuel_02_006_2` −0.18 ×2. Counts: kept 42, own-walls 96,
followed 23, apart 27, refusals 100 → 58.
THE BAR ("only bodies visibly separated from their own building move"): every HECA/OTHH mover is a body the
contact graph binds to its building (a follow of its own senior's seat, or a refused body under the building's
roof within 1.0 m); whether the T3 door at +10.59 (its wall is on the 101.79 pad) and the OTHH bridge clutter at
−2.47 are "visibly separated from their own building" or the owner-approved state is the OWNER'S CALL — listed,
not merged by this lane.

## CLOSING — what ran and what did not
* Tile builds through the mesh step: BOTH REFUSE on the corpus (KASE `N39W107_bathymetry_band` missing; KCLT
  `N35W081_bathymetry_band` missing after the master's 21:03 KVUJ inset refresh) — the master's `--refresh-data dem`
  on +39-107 and +35-081, then `build_airport.py KASE --tile 39 -107 --steps "1 vector,2 mesh"` / `KCLT --tile 35 -81`
  on this branch is the closing test still owed. In its place: the app's own meshes replayed (above) — the same
  object stage on the same ground the owner read.
* Airside untouched: patch-only harness builds on this branch — KASE body **9aceb887dd67 = sw20/owner**; KCLT body **9731f0b70610 = sw20** (941 s, 4915 verify rows)
  — the object stage moves no terrain.
* Suite: full non-Qt `-n 4` **9639 passed / 19 skipped / 1 xfailed / 1 xpassed** (844 s); touched files re-run after
  the last edit: 231 passed. `tools/ratchets.py`: DUPLICATE PASS, LAYER PASS; size WARN engine_v2.py 1108 → 1629
  (+5 here, +516 others' baseline drift), placement_plan.py 1022 (+11), obj8_split_report.py 1818 (+33).
* Frames registered (`frames.py register`): KASE/KCLT app meshes (kind mesh) and app rebake plans (kind rebake).
* NOT DONE: the two mesh-step tile builds (refused); the residual KCLT classes (b)–(g) above; the awning's exact
  identity (two candidates, both posts with 0 ε-contacts to their roof — owner to confirm at 35.2129379,-80.9327134
  and 35.218182,-80.931399); `split_off_pad` / roads609's files untouched (`pad_block_seat.py`, `footprint_seats.py`,
  `footprint_unit.py` not edited; `placement_plan.py` +11 lines: one call after the viaduct seat).
