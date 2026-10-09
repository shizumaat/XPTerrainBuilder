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
