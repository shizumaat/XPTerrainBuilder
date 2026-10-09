# pads67 notes — `claude/pads63` (PR #480) merged up to main `729e140d`, the seven-airport read, and THE EDGE READ for RULINGS 2026-10-09d (1)

Scratch `<scratch>/pads67/` (`.progress`; `build.sh` / `hold.sh` / `inst.sh` = pads66's, retagged `sw8_`, references `sw7_*` and
`surf337b_OTHH`).

## Step 1 — the merge (`4b433195`)

* `tools/harness/lane_worktree.sh up pads67 origin/claude/pads63` → `git switch -c claude/pads67` → `git merge origin/main`.
* ONE conflict: `docs/frames.jsonl` (both sides appended) — both kept, 1,028 rows, every row parses.
* Spec: auto-merged, no heading collides — pads carry §56 / §57, main carries §59 / §60; nothing renumbered.
* Suites on `4b433195`: non-Qt split `9097 passed, 19 skipped, 1 xpassed` (283 s).

## Step 2a — `tools/pad_edge_read.py` (bank.py promoted on its second use; INDEX row; twin `tests/test_pad_edge_read.py`, 6 passed)

Reads one build's `ICAO.graded.json` + the build's DEM off any capture pickle of the airport (`airport.dem`; the patch carries no
DEM). Per pad-rim vertex: non-pad cells touching or within 10 m, and the uncovered DEM on 8 bearings at 2 / 5 / 10 m. Flagged when
anything stands > 1 m off the rim. Classes: `P` pavement itself off (touching, or within the 3 m stand-off): seat candidates; `M`
pavement at the rim's level beside a bare bank; `S` graded strip only; `B` bare. Runs = same-class chains along one pad's rim.

## Step 2b — the builds (`sw8_<ICAO>`, harness through the ledger, tree `88e925bb` / `38f2ba5a` = the merge + tools only)

Progress (references `sw7_*`, OTHH `surf337b_OTHH`; each census under its own tree's tool):
* CYXY rc 0, body cf8e9e89ec62 → b20103c51fd7 (= pads66's `swq`), runway movers 0, structure 0.
* NLWF rc 0, 45ec40e74dcb → 369eabe9dfef (= swq), 0 movers in every frame.
* KASE rc 0, f9b157158a39 → 718538f4d2e2 (= swq), runway 0, structure 0.
* SPJC rc 0, 61f66f149737 → 3ef3e7c7013d (= swq), runway 0, structure 8 ≤ 0.05.
* Edge reads (`<scratch>/pads67/edge_<ICAO>.{txt,json}`): CYXY 16 runs (P 2), NLWF 5 (P 0), KASE 6 (P 0), SPJC 66 (P 6).

## Step 2c — the seven-airport table (merged head `4b433195` + tools-only commits; `sw8_<ICAO>`, all rc 0, status optimal, guard clean)

References: `sw7_*` (main `729e140d`), OTHH `surf337b_OTHH`. Each census under its own tree's tool. Runway movers = runway-role
vertices moved > 0.02 m in ANY frame of `airside_value_delta` (row-side / solve-owned / structure). Wall times are CORRECTNESS
builds run two at a time (HECA beside KCLT; OTHH beside the instruments) — NOT timings.

| | CYXY | NLWF | KASE | SPJC | KCLT | HECA | OTHH |
|---|---|---|---|---|---|---|---|
| body ref → sw8 | cf8e9e89ec62 → b20103c51fd7 | 45ec40e74dcb → 369eabe9dfef | f9b157158a39 → 718538f4d2e2 | 61f66f149737 → 3ef3e7c7013d | 0b1566de77d5 → e52fc9b4c757 | 75c751a9dd95 → a4919cfe331b | 500f5dddce63 → 2d741bc20863 |
| vs pads66's `swq` body | same | same | same | same | same | NEW (main's gap-apron + #337 moved HECA) | NEW (#337) |
| runway movers | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| structure frame movers > 0.02 (worst) | 0 | 0 | 0 | 8 (0.05) | 4 (0.06) | 0 | 1 (0.04) |
| solve-owned movers > 0.02 (worst) | 306 (1.02) | 0 | 107 (0.54) | 303 (0.45) | 1,693 (0.59) | 2,773 (1.01) | 0 |
| `hard_conflict` taxi | 0 = 0 | 0 = 0 | 0 = 0 | 6 = 6 | 51 = 51 | 63 → 64 | 0 = 0 |
| `hard_conflict` pad | 2 → 4 | 0 = 0 | 66 → 0 | 1 = 1 | 4 → 31 | 27 → 101 | 0 = 0 |
| `hard_conflict` groundside | 5 → 4 | 7 = 7 | 0 → 2 | 1 = 1 | 291 → 292 | 204 → 230 | 0 = 0 |
| CRITICAL motion (by class) | 0 = 0 | 0 = 0 | 1 = 1 `strip_arc` | 0 = 0 | 5 → 4 (`frontage_near_miss` 1 → 0; `strip_arc` 4) | 2 = 2 `strip_arc` | 0 = 0 |
| CRITICAL visual | 52 = 52 `hairline_pair` | 23 = 23 | 45 → 44 (`hairline_pair` 44 → 43, `airside_no_step` 1) | 507 → 502 (`hairline_pair` 466 → 461) | 1,974 → 1,997 (`hairline_pair` 1,969 → 1,993, `adjacent_ground_step` 2 → 1) | 1,912 → 1,957 (`hairline_pair` 1,851 → 1,896; `mid_edge_step` 28, `strip_seam_tear` 22, `vertex_to_edge_step` 5, `adjacent_ground_step` 4, `groundside_cutback` 2 unchanged) | 2,062 → 1,933 (`hairline_pair` 2,040 → 1,923, `within_shape` 12 → 0; `ramp_in_strip` 6, `terrace_actual_step` 4 unchanged) |
| adjudicated airside | 254 → 265 | 3 → 2 | 2,654 → 2,525 | 891 → 711 | 3,355 → 3,027 | 12,205 → 12,017 | 493 → 164 |
| platforms / welded contacts (sum) | 9 / 83 → 9 / 83 | 1 / 7 = | 3 / 42 → 2 / 46 | 32 / 688 → 30 / 693 | 64 / 1,512 → 55 / 1,454 | 47 / 1,023 → 47 / 1,053 | 18 / 1,080 → 16 / 1,081 |
| pads with `welded` > 0 | 9 | 1 | 2 | 24 | 54 | 39 | 16 |
| released welds | 0 | 0 | 4 → 0 | 0 | 0 | 27 → 0 | 0 |
| `weld_widened` | – | – | `building1` | – | – | `building138`, `building147`, `building157`, `building165` | – |
| feet < 0.3 m | no feet | 134 → 130 | 1,715 → 1,737 | 1,287 → 1,454 | 4,370 → 6,095 | 17,147 → 19,681 | (in `inst_OTHH.txt`) |
| feet > 3 m | – | 0 = 0 | 5 → 0 | 62 → 4 | 86 → 90 | 2,383 → 932 | |
| build s (not a timing) | 41.2 | 9.6 | 53.1 | 109.8 | 372.2 | 801.7 | 608.5 |

Per-pad `platforms[].welded` (sw8): CYXY building10:21 13:14 6:12 14:8 4:7 8:7 1:6 12:5 2:3 · NLWF building1:7 · KASE building2:33
building1:13 · SPJC building5:354 42:50 24:39 45:28 54:22 31:21 4:21 6:20 58:17 47:16 62:15 38:15 25:13 8:10 19:10 35:8 39:7 50:5
10:5 13:5 26:5 49:3 57:3 34:1 (six second blocks 0) · KCLT building75:319 84:223 81:82 11:40 18:39 9:37 43:31 54:31 79:31 2:29 7:28
39:27 80:26 24:24 10:22 82:22 … building26:0 · HECA building4:486 147:63 140:42 104:35 84:34 83:32 193:31 138:30 105:24 157:19
174:15 … building75:4, five `building4/landing*` 0, building148 / 5 / 59: 0 · OTHH building6:586 14:128 5:82 32:59 15:44 28:33
16:22 29:19 11:18 7:17 18:17 12:14 24:14 31:12 6#2:12 13:4. Full lists: `<scratch>/pads67/inst_<ICAO>.txt`, `row.py`.

Frames registered (`docs/frames.jsonl`): the seven `sw8_<ICAO>.osm` patches, base `4b433195`, lane pads67.

## Step 3a — WIP checkpoint (resumed after an outage)

* `pad_edge_read.py` pins the console (the `test_console_encoding` twins: 2 failed → pass). Qt `-n0`: 311 passed. Named tests +
  twin + archmap: 223 passed. `tools/ratchets.py`: DUPLICATE RATCHET PASS, LAYER RATCHET PASS (size warnings are the branch's
  own files, none touched by this lane).
* `sw8_OTHH` finished clean: rc 0, body 2d741bc20863, guard blocked [].
* Captures on the merged head for all seven (`<scratch>/pads67/cap/<ICAO>.pkl`), `pad_frontage_step` pairs and edge reads done.
* Replay arms so far: CYXY and SPJC `--design-weight frontage_step_max_m=99` (every pad|groundside pair armed);
  HECA `--drop-generator pad_slope_ceiling` (building75).

## Step 3b — THE EDGE READ (`tools/pad_edge_read.py` on `sw8_<ICAO>.v2/<ICAO>.graded.json`, DEM off the merged-head captures)

Flag: anything standing > 1 m off the rim within 10 m. Stand-off 3 m (= `pad_frontage_gs`'s own `pad_frontage_m`).
Cells: runs / vertices / metres of rim / worst height. Data: `docs/briefs/pads67/edge_<ICAO>.json`, `pclass_<ICAO>.json`.

| | P pavement does not meet the pad | M pavement meets the rim, height beside it | W declared structure | S strip | B BARE (accepted, 09d (1)) |
|---|---|---|---|---|---|
| CYXY | 2 / 21 / 157 / 4.8 | 6 / 9 / 9 / 4.0 | 0 | 3 / 6 / 14 / 2.4 | 5 / 11 / 104 / 3.7 |
| NLWF | 0 | 2 / 7 / 15 / 12.7 | 0 | 1 / 3 / 11 / 11.1 | 2 / 13 / 40 / 12.7 |
| KASE | 0 | 2 / 2 / 0 / 1.1 | 0 | 0 | 4 / 15 / 368 / 8.7 |
| SPJC | 6 / 7 / 32 / 4.1 | 26 / 61 / 874 / 7.7 | 0 | 1 / 1 / 0 / 2.1 | 33 / 167 / 3,512 / 7.0 |
| KCLT | 17 / 27 / 99 / 6.4 | 101 / 239 / 1,181 / 6.0 | 0 | 4 / 6 / 18 / 8.2 | 83 / 361 / 3,682 / 14.7 |
| HECA | 97 / 199 / 1,441 / 10.1 | 254 / 1,217 / 9,310 / 13.9 | 0 | 1 / 1 / 0 / 1.8 | 331 / 1,965 / 17,616 / 9.8 |
| OTHH | 0 | 49 / 276 / 560 / 5.3 | 33 / 250 / 385 / 4.8 (basin floors, tunnel ramps, wall-corridor ramps beside `building6`) | 0 | 29 / 205 / 208 / 4.8 |

The P runs by what the ENGINE says of the pad|cell pair (`pclass.py`: `pad_frontage_step.py` pairs off the capture, the sidecar's
`platforms`, `cluster_pads`, `gap_pieces`, `terrace_joints`):

| class | CYXY | SPJC | KCLT | HECA | what it is |
|---|---|---|---|---|---|
| T28 | 2 (157 m; +4.02, +3.60) | 2 (+3.89, +3.22) | 2 (−3.17, −2.27) | 1 (+1.06) | a §28 (6) pair HELD AS A TERRACE: groundside-frontage DEM minus airside-frontage DEM > `frontage_step_max_m` 2.4 (RULINGS 13o / 13p / 18c (1)); unwelded, 0.7–2 m sliver |
| ARMED | 0 | 0 | 2 (−1.60, −1.01) | 1 (66 m, +2.70) | a §28 pair the engine ARMS (DEM step < 2.4) that still stands > 1 m off in the patch |
| GS-NEAR | 0 | 3 | 10 (71 m) | 16 (570 m) | groundside lot / road 0.6–2.6 m off a pad that is NOT in the §28 population — at HECA every one is a pad with NO platform record (no airside frontage), seated by its object cluster's level or its own DEM |
| GAP | 0 | 0 | 0 | 50 (339 m, 23 pads) | a late-stage gap part ~1.5 m off the pad at another level: 30 `lot` parts, 9 `step` parts, 1 `ramp`, 10 un-cut |
| GS-TOUCH | 0 | 0 | 0 | 1 (`building4/landing4` ⟂ `dsf:pol10`, 1.50 m at 5 %) | welded groundside cell leaving the rim |
| AIR-NEAR | 0 | 0 | 0 | 7 (231 m) | apron 1–2.5 m off a pad with no platform record |
| AIR-TOUCH | 0 | 1 (1.08 m, 38 %) | 3 (1.27–1.28 m, 18–24 %) | 21 (232 m; 17 pads; 6–7.9 m, 75–250 %) | the apron welded to the pad leaves it steeply |

### Interventions (replays of the merged-head captures)

* T28, CYXY `--design-weight frontage_step_max_m=99` (both pairs armed): the two P runs go (lots within 0.48 / 0.71 m across the
  0.74 m sliver), pad seats unchanged (694.895 / 695.864), airside movers 0 in every frame, `hard_conflict` unchanged — and the lots
  pay: `pav4` dug down to −3.73 m (36 of 67 vertices > 1 m), 11 ring edges over its 5 % cap (6.1 % over 43.8 m); `dsf:pol129` −3.58 m
  (21 of 23), 10.2 %, 3 edges over 10 %.
* T28, SPJC same arm: `building24`'s two runs go, seat unchanged (24.352), airside movers 0; `dsf:pol36` −3.87 m, 10.3 % over
  41.6 m; `dsf:pol37` −3.62 m, 10.3 %.
  => the airside frontage sets the seat (CYXY reach bands top out at 698.07 / 698.97 against lots at 698.9 / 699.5); the lot
  cannot weld inside its cap; raising the pad means raising the apron it is welded to.
* HECA `--drop-generator pad_slope_ceiling` (aimed at `building75`): NOTHING changed there (rim 99.70…100.86, 63 + 20 conflicts) —
  the rows citing `cluster:unit:41#103` are not that generator's. Mis-aimed; `building75` is NOT attributed by intervention.

### The two open items from pads63

* HECA `building75`, 81 pad-tier conflicts (sw8: 61 `pad_slope_max ceiling` citing `cluster:unit:41#103` + 20 `platform plane`,
  worst 1.47 m, stage 2). By the record: datum 100.859 (4 airside contacts on `junction:pav98`, emitted 100.86 there); six rim
  vertices are SHARED with `service_road:small_roads:-20325` (100.57–100.81); the free rim stands at 100.56 = the cluster's level
  100.557 (main: cluster level 100.861 over 11 rim vertices; branch: 25), and ONE vertex 30.12086521267, 31.41819005825 at 99.70
  — every conflict over 0.5 m has it as an end, against `pavement_max_grade ceiling`, `road_max_grade pavement fallback`,
  `road_cross_section`, `groundside_road ramp ceiling`. On main the collar stood between the flat platform and that road.
* HECA `building147`, six `airside_no_step` rows (sw8: 6 `apron|junction` ways -10218|-10219, 1.63–1.76 % against 1.53–1.58 % over
  94–135 m, over by 0.12–0.19 m; + the `apron|apron` rate row). The pad's reach band is INVERTED: lo 71.805 (east contact, 29 hops
  from 05C/23C) > hi 70.263 (west contact, 5 hops from 05L/23R); misfit 0.771 < 1 m → 08d (2) widening, Δ 0.312 pp on `pav39` /
  `pav39#plateau`, 12,914 rows. Engine and census use the same membership (ALL vertices of a row on a widened face); the six
  pairs end on a junction vertex outside it. Over-budget ÷ Δ = 38–62 m of route. No taxi `hard_conflict` within 300 m. Reading,
  NOT proven by intervention: the published pair budget is the unwidened route budget while the per-edge rows along the route
  inside `pav39` were widened.
