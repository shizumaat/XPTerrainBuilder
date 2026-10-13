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
