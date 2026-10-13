# kclt608 — notes (issues #608 #609 #610: owner sim read of KCLT on app 1.0.388)

## RESUME HERE
* Branch `claude/kclt608` (worktree `.claude/worktrees/kclt608`) off main 23d87cecf, merged origin/main be1cabda5 (RULINGS 12l/12m).
* Step A DONE (tables below). Scratch `<scratchpad 466e18b3…>/kclt608/`: `a1_bodies.py` (bodies of a unit with zeros),
  `a2_separations.py` (every ε-contact pair written at two zeros), `a3_window.py` (which zero each part in a window is
  written at), `osr_sw17.json` / `osr_sw11.json` (obj8_split_report dry runs of the sw17 / sw11 plans), `sep_*.csv`.
* Reference: `/tmp/harness/sw17_KCLT.v2/` (plan + graded, body 424876ac748d) and the APP's own written placement
  `/Users/noah/XPTerrainBuilderData/Patches/+30-090/+35-081/o4_v2_placement_KCLT.json` (engine 1.50.1835 = 1.0.388,
  written 2026-10-12 16:33) — the two agree at every site below (body numbering differs).
* Base replay of `frames/pads67/KCLT.pkl --from classify --emit --verify --solved-out` running in `<scratch>/base/`.
* HECA dry run `obj8_split_report` of sw17 HECA running → `<scratch>/osr_heca_sw17.{json,txt}`.

## Step A — LOCATE AND COUNT (sw17 plan + app placement, before any change)

### Units cut per pad level (#577 `_split_by_level`) — ONE unit at KCLT
`fu:6:960` (the terminal; 42 members, 116 bodies) → `/p0` pad building81 221.75 (22 bodies), `/p1` pad building75 222.44
(28), `/p2` pad building85 222.87 (6); `pad_level_bodies_welded 237, nearest 269, straddle 1 (-paredes_5)`. No other KCLT
unit is level-cut. (HECA: see the dry run when it lands.)

### Finding 1 — NW terminal (owner sites 35.2224352,-80.9472186 = pad building81; 35.2203395,-80.9466805 = apron
`pav14#plateau:building81` 221.54)
Every WRITTEN part in the window 35.2218..35.2240 / -80.9485..-80.9460 (walls `paredes_4 b0` 232 feet, `paredes_5 b0`,
`paredes_2 b0`, the roofs `techos_1 b2/b8`, `techos_2 b3/b7`, the carried `paredes_9 b10`, `paredes_10 b42`, `paredes_12
b15/b21`, floor `suelos_interiores b5` 11.37 m) is at ONE zero, 221.75 (a3_window, app placement = dry run). So the
PLAN carries no roof/wall split at the owner's site. What is NOT in the plan:
* `Terminals/paredes_11_charlotte.obj` and `paredes_6_charlotte.obj` — SKIPPED from the plan as "basin facility /
  structure member: the terrain adapted to THIS member (08-26; v1 R4; 09q (1)) — never re-seated"; they stay on their
  AUTHORED row at the file anchor 35.2212296,-80.9433723 on pad building75 = 222.44 m. kclt546 measured (notes, Finding
  2): "within 60 m of either site the two skipped files have no ground-contact component at all (only roof parts at
  y >= 12 m)"; paredes_11 has 387 ground-contact components riding 222.44 elsewhere. **MECHANISM (finding 1): the level
  cut moved the concourse walls to 221.75 (their own pad); the concourse ROOF parts that live in the two never-re-seated
  files stay at the anchor's 222.44 → roof planes 0.69 m above the walls.** Before #577 (sw11, kclt546 numbers) walls and
  roofs were BOTH at 222.44 (walls floating 0.69, roofs on them). Attributed to #577 (the cut), exposing the kept-whole
  files.
* The north extension (`-paredes_2 b1/b2`, `-paredes_5 b0/b2`, `-paredes_7 b1`, `-techos_2 b1`) is `/p2` at pad
  building85 222.87 and touches `paredes_4 b0` / `paredes_5 b0` (221.75) at 35.2234356,-80.9467987: **1.12 m** step
  between touching parts of the one unit (3 pairs); `-techos_1 b2` (own ground 222.29) over `-modulos_interiores b0`
  (/p0 221.75): 0.54 m; `-paredes_7 b1` 222.87 over the same: 1.12 m. Also #577 (sw11 had the same pairs at the same
  metres: the pads were already at these levels; the unit's one zero hid it).

### Touching parts of one unit written at two zeros (a2_separations ≥ 0.3 m, app placement): 33 pairs / 49 bodies
Terminal unit (#577 class): `paredes_8 b7` (own ground 217.21, the tunnel-ramp body) ↔ `paredes_4 b3` /p1 222.44: 5.23 m
(34 pairs, 35.2214171,-80.9441306 — the #548 bore site, not this issue); `techos_1 b0` /p1 222.44 ↔ `Paredes_7 b1`
219.36: 3.08 m; `suelos_interiores b2` 222.44 ↔ `Paredes_7 b8/b9/b10/b11` 221.75 at 35.2202619,-80.9473359 (site B,
the 7.84 m floor plate over the concourse: 0.69 m); `paredes_8 b2` /c0 222.44 ↔ `paredes_2 b0` /p0: 0.69 m.
East side (`Terminals/Hangar/Charlotte_Airport_00x_ALB.obj`, lon > -80.94) — UNCHANGED between sw11 and sw17 (older
than #577), every pair has at least one body seated on its OWN ground (no unit) or on a different cluster pad:
| sep m | A | B | at |
|---|---|---|---|
| 1.31 | 003_ALB b1 own 221.99 | 001_ALB b53 `fu:3:506/host` 223.30 | 35.2209695,-80.9294107 |
| 0.77 | 005_ALB b4 own 216.73 | 001_ALB b39 own 217.50 | 35.2109690,-80.9300226 |
| 0.64 | 005_ALB b6 `fu:3:628/host` 217.50 | 001_ALB b62 own 216.85 | 35.2103367,-80.9301051 |
| 0.58 | 005_ALB b22 own 215.74 | 001_ALB b63 own 216.31 | 35.2063650,-80.9314325 |
| 0.56 | 008_ALB b4 `fu:3:855/host` 223.30 | 001_ALB b64 own 222.74 | 35.2147134,-80.9314928 |
| 0.47 | 005_ALB b23 `fu:3:213` 216.78 | 002_ALB b29 own 217.25 | 35.2104971,-80.9299566 |
| 0.44 / 0.36 | 006_ALB b8 / b9 (`fu:3:756/host`, `/759/host`) | 001_ALB b33 `fu:3:702/host/b1` 218.66 | 35.2078141,-80.9379816 / 35.2062306,-80.9383464 |
| 0.38 | 004_ALB b1 `fu:3:432` 219.04 | 001_ALB b33 218.66 | 35.2184358,-80.9324633 |
| 0.38 | 008_ALB b7 `fu:3:882/host` 220.89 | 001_ALB b13 own 221.27 | 35.2140963,-80.9317748 (22 pairs) |
| 0.35 | 005_ALB b10 own 216.50 | 001_ALB b62 own 216.85 | 35.2086501,-80.9313261 |
Whole-structure floats east (app placement `ground_off` ≥ 0.5 m, zero above the ground under the feet): 008_ALB b14
+1.21 (35.2129824,-80.9327807), 003_ALB b21/b22 +1.11 (35.2011746,-80.9308541), 002_ALB b48 +0.89, 002_ALB b5/b6 +0.87
(35.2177862,-80.9296717 "unit on its median ground"), 003_ALB b1 +0.86 (35.2207610,-80.9292341), 002_ALB b16 +0.87,
b23 +0.86, b17 +0.75, 008_ALB b16 +0.69 … (all "low-side foot" or "median ground" seats on sloping ground; none level-cut).
The awning on posts: not yet identified by name — candidates are the carried-body rows (`§15 carried over a body the law
REFUSES as a carrier` 3.44 m 001_ALB b53 at 35.2144152,-80.9309725; `§16a (2) refused carrier` 2.52 m 004_ALB b11 at
35.2181202,-80.9314641).

### Finding 2 — between the garages (pads building86 223.0–223.4 / building88 223.1 / building90 223.0–223.45)
App placement: 8 bodies of unit `fu:31:2809` (the garage cluster, seated "on pad building88 at 223.11") stand on NO pad
(off every graded face) and float over the DEM: `paredes_10 bb12` +5.03 (35.2251208,-80.9446205), `bb3` +4.81
(35.2241697,-80.9458018), `bb10` +4.67 (35.2244046,-80.9445545), `bb11` +4.39, `bb2` +4.30, `bb9` +3.22
(35.2254441,-80.9446671), `paredes_12 bb4` +3.07 (35.2254979,-80.9444970), `bb3` +0.95. (connect549's "every body within
0.48 m" read the graded surface only; off-surface bodies read nothing there.) They are seated to the unit's one zero
because they are welded (ε-contact) to the deck chain; they have their own feet on bare ground 4–5 m lower.
Ramps / roads: the PATCH has NO road face within 240 m of 35.2248,-80.9450 (nearest `service_road` 247 m away); the
OSM feed has 32 `highway=service` ways within 120 m (one `bridge=yes layer=2`). The forecourt roads are NOT admitted
into the airport patch at all, so the ground between the garages is the raw DEM mesh (~218.1–219.6) rising to the
pads' 223.0–223.4 inside the pad stand-off: the "access ramps" are the mesh bank at the pad edge (+4.9 / +4.0 m fill
accepted in 12c) plus the pack's own ramp objects, not engine-graded roads.

## Step B — the design surface: WHERE the connected terminal gets two levels (base replay `<scratch>/base/`, = sw17: 0 movers in all three frames)
* `b1_clusters.py` on the solved pickle: the terminal is ONE design cluster `unit:31#0` in THREE outline pieces —
  `/0` = building75 (26 faces), `/1` = building81 (9 faces), `/2` = building84 (3 faces); building83 is no cluster's
  face (its own plane entry), building85 is cluster `unit:30#0` (the `-paredes_*` north extension, a different load
  unit). Every piece FRONTS AIRSIDE → `cluster_pad._pinned_faces` kept each piece its own plane entry (the 10-10 re-union
  skipped pinned pieces), so three entries: 221.75 / 222.44 / 222.70.
* All five (75, 81, 83, 84, 85) are HELD blocks (`hold_report`): each has its OWN datum column `dv` with hard plane rows
  (own vertices = dv), hard weld holds (contacts = dv) and a SOFT preference `Band(dv, D, D)` at the median of its
  contacts' pass-1a value (building75 D 220.88 → solved 222.44; building81 D 220.55 → 221.75; building84 D 222.99 →
  222.70). Reach bands: building75 [220.42, 227.16], building81 [216.67, 226.13], building84 [222.88, 231.57] —
  the INTERSECTION [222.88, 226.13] is non-empty: one level for the three pieces exists within the reach graph.
* MECHANISM: two (three) held blocks of one connected cluster, each seated by its own frontage; nothing tied them.
* RULE LANDED (f84234382): (a) `cluster_pad._plane_groups` re-unites the pieces of one cluster stem whether or not
  they front airside (`_pinned_faces` deleted; the flat BLOCKS `/b<k>` of a cut unit still split by `_split_blocks`);
  (b) `constraints/platform.datum_groups(planar, law, airport, prefs)` = the held refs of one plane entry,
  `datum_group_rows` = hard two-sided `z[dv_b] − z[dv_a] = 0` under the HOLD_RULING head (stripped in pass 1a with the
  holds, carried in pass 1b); minted in `no_step.hold_interval` (stats `datum_groups`, `datum_group_rows`; each
  block record carries `group`). The per-block soft preferences stay; the welds and the apron caps decide the one level.
  A weld no one level can hold is released and warned exactly as a single block's (never two levels).
* Object side (f84234382): `pad_block_seat.split_off_pad` — a FOOTED body of a pad unit whose every foot is farther
  than `[placement] footprint_touch_m` (0.5 m, the §16g touch — no new key) outside every pad/block ring the unit stands
  in becomes `<id>/g<n>`, seated by `plan_unit_datums`' ground datum (10n (2)/(3)); footless bodies keep their welds.
  `_split_by_level` STAYS: HECA's sw17 dry run cuts 5 units by level (fu:40:120 4 levels / 230 bodies, fu:43:5027,
  fu:43:5241, fu:43:5987, fu:41:348 — 324 bodies), the state the owner approved (12m).
* Arm replay `<scratch>/arm1/` running (KCLT); HECA arm next.

## Step B — ARM (replay `frames/pads67/KCLT.pkl --from classify --emit --verify` on be4317166, `<scratch>/arm1/`)
* ONE LEVEL: building75 222.44 → **222.68**, building81 221.75 → **222.68**, building83 222.44 → 222.68, building84
  222.70 → 222.69/222.70 (flat at 222.68 to 0.02 m); building85 222.87 → 222.88 (0.20 m above the complex — within
  `split_tol_m`, so the object unit `fu:6:960` has ONE level group and is no longer cut); garages unchanged
  (223.05 / 223.11 / 222.99), building92 223.67 unchanged. The `datum_groups` stat: 1 group (building75 ← 81, 84).
* THE APRON GRADES TO IT (`airside_value_delta` sw17 → arm, tol 0.02): RUNWAY 0; solve-owned 995 movers — apron
  721 (worst 0.93 m at 35.22006914808,-80.94808090106, the concourse frontage: `pav14#plateau:building81` 94/94
  +0.93, `pav14#plateau:building75` 520/521 ≤ 0.84, `pav14` 358/662 ≤ 0.93), taxi family 255 (worst 0.91 m, all
  `junction` of `pav14` at 35.21947425094,-80.94753721362 — the apron's own junction by the concourse), strip 19
  (≤ 0.21); row-side 1,567 (strip 304 ≤ 0.46, other 287); structures 11 tunnel-wall rim nodes ≤ 0.24 m at the
  terminal. Vertices added/removed 0/0 in every frame.
* FRONTAGE: `hard_feasibility` relaxed rows frontage_hold 2 (= base 2, worst 0.0598 m = base), pad_slope ceiling 15
  = 15, platform plane 16 = 16 — no NEW released weld, `warnings` none: every frontage of the complex welds to
  222.68 within the caps. `pad_level` family 90 rows / 45 missed (base 94 / 47, same max 6.62 m elsewhere).
* So (ii) is lawful at KCLT without any step: the one level sits inside the three reach bands' intersection
  [222.88, 226.13]? — no: 222.68 is 0.20 m under building84's band floor 222.88 (the bands are the report; the
  welds + caps are the hard set) and the solve held every weld within caps anyway (0 new relaxations).
* Closing builds started 19:20: `kclt608_KCLT`, `kclt608_HECA` (harness, `/tmp/harness/`).

## HECA — the off-pad cut's blast (object dry run `obj8_split_report` on sw17 HECA plan + graded, be4317166 vs main)
`c2_osr_diff.py osr_heca_sw17.json osr_heca_arm.json`: off_pad_units_split 44, off_pad_bodies 979; **74 bodies move
> 0.05 m**, the largest `T3_concrete_Yellow.obj` fu:42:1906 69.58 → `fu:43:5027/p0/g5` 100.57 (+30.99, 30.1288455,
31.4001441), fu:42:1892 70.37 → 100.96 (+30.59), `metal_strip_2.obj` fu:43:5046 69.94 → 95.03 (+25.09,
30.1189660,31.3884155), `T3_14.obj` 72.72 → 91.09 (+18.38, 30.1254677,31.3999493), `door.obj` fu:40:120/p3 101.79 →
91.01 (−10.78, 30.1139691,31.3967509), `T3_14.obj` 101.79 → 91.93 (−9.86) … 23 more between 2.4 and 8.9 m; plus the
re-partition (92 base-only / 361 arm-only body keys: coarsening regroups when units change). The design side moves
NOTHING at HECA in this dry run (same graded surface); the design arm (datum groups) is measured by the HECA BUILD.
These are bodies with feet on ground far from their unit's zero — under 10n (3) they float/bury today by those
metres; but HECA is APPROVED on the current body (12m) → OWNER'S CALL. To drop the object-side rule alone: restore
`Ortho4XP/src/auto_patch_v2/airport/pad_block_seat.py` and `footprint_seats.py` from main and delete the last test of
`tests/auto_patch_v2/test_connect549.py` (`test_a_footed_body_off_every_pad_on_other_ground_leaves_its_unit`).
