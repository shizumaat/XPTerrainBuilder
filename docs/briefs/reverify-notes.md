# reverify notes — PR #503 (`origin/claude/cloudholering` a4c2b6d9: R-E + C2 `foreign1a`) measured on the corpus

Lane `reverify`. Worktree `.claude/worktrees/reverify`, branch `claude/reverify` = a4c2b6d9 merged with `origin/main`
469d18ea0 (merge d4330deaa). Scratch `<scratch>/reverify/` (`.progress`, `pair.sh`, arm dirs). No engine code changed.

## Frame

* Captures reused: `frames/pads67/{HECA,KCLT,SPJC,OTHH}.pkl` (registered). No new capture, no airport build.
* Arms: `m` = seat2's `<scratch>/seat2/m` (HECA) / `km` (KCLT), tree 67e7f587 (main 1e524b12 + §61 + R-D rule 1, NO R-E);
  `e` = seat2's `e` / `ke`, tree f3596b84 (R-E); `c2` / `kc2` = THIS tree (R-E + C2 + main 469d18ea0).
  REUSED, not re-run: main 1e524b12..469d18ea0 touches `src/` only in `airport/road_descent.py` (a log line) and
  `pipeline/build.py` (sidecar sum) — "no emitted patch changes" (469d18ea0). A control on this tree's own parents is
  the `noC2` arm below (R-E alone = `_unheld_datums` stubbed to the empty set by a scratch driver).
* Pair form: seat2's `pair.sh` (gap-free base `--null-change` + `--solved-out`, late pair `--late-from`, `pad_edge_read`),
  `--workers 9` (weldverify shares the machine), one heavy thing at a time.

## Step 0 — setup (done)

## Mid-task ruling: RULINGS 2026-10-10a (1) (on main 6dfb9785, docs only — not merged into this tree)

The runway bar is no longer 0.1 m: up to 0.5 m where the shift is a gentle dip or rise, no notch / cliff, the runway's
own grade and curvature law still met. Read by `<scratch>/reverify/rw.py` (per runway: movers, worst, dz = arm − base
along the runway axis by cross-section; largest change over any 30 m and 60 m as a grade change in percentage points;
every run of 30 m windows over 0.1 pp listed by site as a KINK; largest dz change across one runway face edge).
graded.json z is cm-rounded: dz quantum 0.01 m = 0.033 pp / 30 m.

## Step 1 — HECA (`<scratch>/reverify/c2`, pair 17:42–18:02; m / e = seat2's, census each on its own tree)

| HECA | m (no R-E) | e (R-E) | c2 (R-E + C2, this tree) |
|---|---|---|---|
| `--null-change` pass1 / pass2 / pass3 / stage2 | 7/0, 9/0, 9/0 (sheetlevel's read) | 13/1/0.914, 164/0/0.107, 13/0/0.159, 15/0/0.159 MISSED | **0/0/0.000**, **164/0/0.107**, 13/0/0.154, 16/0/0.154 **MISSED (pass 2)** |
| P:AIR-TOUCH runs / m | 21 / 232 | 0 / 0 | **0 / 0** |
| P:AIR-NEAR | 7 / 231 | 4 / 46 | 4 / 46 (building5\|pav1 +1.59; building138\|objpav402 +1.49 over 45 m; building148\|objpav36#1 +1.30; building59\|pav131 −1.01) |
| held datums vs apron on the rim (39 held, 38 with an airside rim) | equal by the kinked rim | 0 off | 0 off; 32 of 39 moved vs m (building98 103.50 → 94.43, 100 101.25 → 93.79, 117 101.74 → 95.12, 68 92.11 → 85.34 …) |
| runway movers > 0.02 / > 0.1 / worst vs m | — | 115 / 16 / +0.14 (05L/23R) | **115 / 16 / +0.14 — identical to e (e → c2: 0 movers)** |
| `hard_conflict` gs / pad / taxi | 254 / 104 / 64 | 259 / 68 / 64 | 259 / 68 / 64 |
| movers vs m: taxi / apron ≤ 60 m of a rim / apron > 60 m / pad | — | = c2 | 3,022 (worst −0.83) / 1,522 (−9.48) / 1,576 (−6.88) / 1,347 (−9.07) |
| apron non-pad movers by distance to a rim (n: movers / > 0.3 / worst) | — | = c2 | < 2 m 59: 46 / 32 / −9.08; 2–10 237: 194 / 103 / −9.08; 10–30 641: 484 / 223 / −8.61; 30–60 694: 350 / 113 / −7.53; 60–200 1,776: 810 / 172 / −6.88; > 200 5,326: 1,723 / 398 / −2.58 |
| adjudicated airside | 12,022 | 12,041 | 12,041 |
| CRITICAL motion / visual | 3 / 1,962 | 4 / 1,982 | **4 / 1,982** |

c2's FINAL surface = e's: 0 vertices differ by > 0.02 m in any family, 0 datums (patch sha differs: sub-cm). C2 closes
pass 1 exactly as holering's pass-1a instrument said (13/1/0.914 → 0/0/0.000) and changes nothing else at HECA.

NOT CLOSED BY C2: pass 2's 164 movers (worst −0.107 m; junction / graded-strip cells of `dsf:objpav402` | `dsf:objpav99`
at 30.12206504, 31.41551287, two on taxiway E at 30.11494310, 31.41399265). sheetlevel read them as following pass 1's
instability; with pass 1 at 0 movers they stand unchanged, so they are their own mechanism (R-E's: m reads 9). Bar
≤ 20 at 0.02 m missed; 0 over 0.3 m met. Pass 3 / stage 2 13–16 movers worst 0.154 on `gapapron:1` (met).

CENSUS by family, m → c2 (= m → e row for row): airside rising — `within_shape` 44,300 → 44,377, `transverse` 353 → 379,
`strip_seam_tear` 22 → 37, `pad_frontage_infeasible` 0 → 4 (worst 0.105), `adjacent_ground_step` 5 → 8,
`pad_airside_weld` 5 → 6, `terrace_actual_step` 0 → 1; falling — `hard_conflict` 168 → 132, `airside_no_step` 4,047 →
4,038, `strip_transverse` 261 → 251, `taxi_box` 2,460 → 2,452, `frontage_near_miss` 18 → 16, `mid_edge_step` 1 → 0,
`vertex_to_edge_step` 3 → 2. CRITICAL motion 3 → 4: **`terrace_actual_step` apron|apron "cliff" 3.62 m at
30.12155524, 31.41995156** (the terminal row of objpav402; new under R-E). CRITICAL visual 1,962 → 1,982:
`strip_seam_tear` +15, `hairline_pair` +7, `adjacent_ground_step` +2, `mid_edge_step` −4.
Runway families m → c2: `strip_longitudinal` 7 = 7 (worst 1.3 =), `runway_crown` 0, `runway_step` 0,
`runway_end_skirt` 0, `strip_arc` CRITICAL 2 = 2 (1.37 / 0.37 unchanged): the runway's own law rows are all as in m.

## Step 2 — the runway (HECA, m → c2; c2 = e at the runway to the cm)

C2 does not change the runway number: e → c2 0 movers on 2,581 runway vertices. The m → c2 shift is R-E's.
* 05C/23C: 4 movers, worst +0.030 (30.11697255, 31.42185793); 30 m 0.098 pp, 60 m 0.049 pp; no kink.
* 05R/23L: 0 movers (worst −0.010).
* 05L/23R: 111 movers, 16 > 0.1, 0 > 0.5, worst **+0.140** at 30.13273109, 31.39698312. NOT a rigid shift: of 3,429 m
  about 570 m moves, as separate local rises of 0.05–0.13 m (section means), each at a taxiway junction; the rest is 0.
  Largest change of dz over 30 m **+0.087 m = 0.290 pp** (s 1724–1754, 30.12941097, 31.39369915); over 60 m −0.090 m =
  0.150 pp (s 2249–2309). Largest dz change across one face edge: transverse 0.050 m over 29.8 m (0.168 pp) at
  30.13949308, 31.40670163; longitudinal 0.130 m over 54.7 m (0.238 pp) at 30.12519288, 31.38877602. No cliff (no
  step: every change is spread over ≥ 30 m of edge).
  KINKS by the 0.1 pp / 30 m line — 7 sites: s 1045–1148 peak +0.283 pp (30.12559418, 31.38811696; dz 0 → +0.085);
  s 1668–1786 +0.290 (30.12941097, 31.39369915; +0.02 → +0.107); s 2115–2214 +0.176 (30.13195983, 31.39710778);
  s 2224–2325 −0.166 (30.13264998, 31.39754873); s 2644–2703 +0.121 (30.13504987, 31.40076040); s 3278–3330 −0.131
  (30.13878941, 31.40575722); s 3353–3428 +0.207 (30.13942542, 31.40660823).
* 10 largest (lat, lon, m → c2), all 05L/23R: 30.13273109259, 31.39698311689 59.71 → 59.85 (+0.14);
  30.13243795243, 31.39726856117 60.48 → 60.61; 30.13223500946, 31.39747096527 60.93 → 61.06;
  30.13264540548, 31.39706615547 60.03 → 60.16; 30.13237028443, 31.39717517079 60.49 → 60.62 (+0.13 each);
  30.13251013076, 31.39736195092 60.47 → 60.59; 30.13229810529, 31.39707659232 60.51 → 60.63;
  30.12941096667, 31.39369915363 59.01 → 59.13; 30.13230718766, 31.39756435498 60.92 → 61.04 (+0.12 each);
  30.13258230904, 31.39745534081 60.46 → 60.57 (+0.11).

## Step 1 — KCLT (`kc2` = this tree; `ke0` = this tree with C2 stubbed off = R-E alone; `km0` = m tree null-change)

BASE CHECK: seat2's `ke` (f3596b84) vs this tree's `ke0` — 0 movers > 0.02 m in every family, 0 datums: seat2's m / e
arms are valid bases for this tree (the merge of main adds no geometry).

| KCLT | m (`km`, null-change `km0` on 67e7f587) | e (`ke0`, R-E alone) | c2 (`kc2`) |
|---|---|---|---|
| `--null-change` pass1a / pass1b / stage2 | 10/0/0.040, **18/4/0.538**, 18/4/0.538 MISSED | 17/0/0.143, 24/0/0.121, 41/0/0.121 MISSED | **0/0/0.004**, **47/0/0.185**, **90/0/0.185 MISSED** |
| P:AIR-TOUCH / AIR-NEAR | 3 / 28 m; 0 | 0; 0 | **0; 0** |
| held datums (53) vs apron on the rim | — | 0 off | 0 off; 13 moved vs m (building75 / 83 221.03 → 222.44, building81 220.70 → 221.75, ten others ≤ 0.08 m) |
| runway movers vs m | — | 0 (worst −0.02) | **0 (worst −0.020; 30 m 0.065 pp; no kink)** |
| `hard_conflict` gs / pad / taxi | 277 / 33 / 50 | 288 / 34 / 49 | 288 / 34 / 49 |
| movers vs m: taxi / apron ≤ 60 m / apron > 60 m / pad | — | ≈ c2 | 808 (worst +1.34) / 2,286 (+1.89) / 578 (−2.06) / 296 (+1.41) |
| apron non-pad by distance to a rim (n: movers / > 0.3 / worst) | — | ≈ c2 | < 2 m 70: 38 / 20 / +1.41; 2–10 375: 188 / 49 / +1.89; 10–30 915: 426 / 77 / +1.40; 30–60 947: 477 / 215 / +1.36; 60–200 1,246: 480 / 186 / −2.06; > 200 747: 445 / 190 / −1.78 |
| adjudicated airside | 2,971 | 3,069 | 3,067 |
| CRITICAL motion / visual | 4 / 1,996 | 4 / 1,996 | 4 / 1,996 |

* e0 → c2 (what C2 changes in the final surface): runway 0, pads 0, datums 0; taxi 39 (worst +0.18 at 35.20907717,
  −80.95015120), apron 9 (worst +0.30 at 35.20812142, −80.95781677), other 46. Those sites are the two arms' own pass-1b
  null-change movers (kc2: junction `pav2` cells at 35.2087, −80.9500 −0.18, apron `dsf:pol19` 35.20825, −80.95925 −0.185;
  ke0: `dsf:pol14` 35.20812, −80.95782 +0.121, `dsf:pol19` −0.113, `pav61`): the e0 ↔ c2 difference is pass 1b's
  path dependence, not a C2 effect on a pad.
* C2 closes pass 1a at KCLT too (17 → 0). Pass 1b is unstable in ALL THREE trees — m itself misses the bar at KCLT
  (4 vertices +0.538 m on apron `pav101` at 35.21590029, −80.94392379), so the pass-1b miss is not R-E's and not C2's;
  under R-E + C2 its count is the highest (47 / stage 2 90) and its worst the lowest but one (0.185; none over 0.3).
* Census m → c2 by family (verify code is identical in the three trees — `git diff 67e7f587 HEAD -- src` touches only
  constraints/apron, platform, design_stage, road_descent, build): airside rising `within_shape` 9,413 → 9,600,
  `transverse` 4 → 8, `strip_arc` 11 → 12; falling `drainage_minimum` 1,929 → 1,849, `airside_no_step` 479 → 475,
  `frontage_near_miss` 10 → 8, `adjacent_ground_step` 17 → 16, `strip_transverse` 18 → 17; `hard_conflict` airside
  83 = 83. Runway families: `strip_longitudinal` 10 = 10 (worst 1.02 → 1.08), `strip_arc` 11 → 12 (worst 1.0 =),
  crown / step / skirt 0.

HECA addendum — the new CRITICAL motion row: `dsf:objpav402` (95.38 → 95.17) against `dsf:objpav1` (98.50–98.60 →
98.69–98.79) across `service_road small_roads:-18656` at 30.12155524, 31.41995156: an apron|apron step that was 3.1–3.2 m
in m and is 3.5–3.6 m under R-E (the sheet sinks 0.21, the neighbour rises 0.19); it crosses into `terrace_actual_step`
"cliff". An existing step grown, not a new one.

## Step 3 — SPJC (`sm` = m tree 67e7f587, `sc2` = this tree; pairs with `--null-change`, 18:22–18:27)

| SPJC | m | c2 (R-E + C2) |
|---|---|---|
| `--null-change` pass1a / pass1b / stage2 | 10/0/0.114, 6/0/0.096, 9/0/0.096 MET | **3/0/0.035, 6/0/0.073, 9/0/0.073 MET** |
| P:AIR-TOUCH / AIR-NEAR | 1 / 0 m; 0 | **0; 0** |
| held datums (24; 21 on 6 shared sheets) | — | 4 moved: `pav35` building4 36.37 → 35.94, building6 35.30 → 35.77; `pav40` building13 29.38 → 29.51; building8 32.85 → 32.87; the other 17 on shared sheets unmoved; 0 off their rim |
| runway vs m | — | **0 movers, worst 0.000** (1,029 vertices) |
| `hard_conflict` gs / pad / taxi | 3 / 1 / 7 | 1 / 1 / 7 |
| movers vs m: taxi / apron ≤ 60 m / apron > 60 m / pad | — | 60 (worst −0.07) / 244 (−1.43 at −12.03021614, −77.10670351) / 70 (+0.21) / 11 (+0.16) |
| adjudicated airside | 714 | 723 (`pad_airside_weld` 4 → 5, `within_shape` 2,243 → 2,245) |
| CRITICAL motion / visual | 0 / 502 | 0 / 502 |

Taxi movers vs m by distance to a pad rim (n: movers > 0.02 / > 0.1 / > 0.3 / worst) — HECA c2: < 30 m 139: 87 / 87 / 2 /
+0.39; 30–60 247: 112 / 96 / 15 / +0.60; 60–200 2,194: 918 / 719 / 172 / −0.83; 200–500 4,549: 1,804 / 999 / 309 / −0.82;
> 500 2,342: 101 / 20 / 2 / +0.32. KCLT kc2: < 30 m 195: 27 / 3 / 1 / +0.74; 30–60 185: 52 / 10 / 4 / +1.30; 60–200
1,666: 343 / 186 / 127 / +1.34; 200–500 2,023: 352 / 118 / 62 / +1.06; > 500 1,120: 34 / 6 / 0 / −0.14.

## Step 3 — OTHH (`om` = m tree, `oc2` = this tree; 18:27–18:59)

The emitted patch is BYTE-IDENTICAL (sha 9cb768342ff3… both arms; R-E adds 16,941 diffs, 494,890 → 511,831, none binding:
every held pad already stands at 3.96 on its sheet). `--null-change` 0/0/0.000 every pass in both. `airside_value_delta`
frames: row-side 22,407 nodes 0 moved; solve-owned 10,466 0 moved; STRUCTURE 2,546 nodes (rims, walls, ramps, trenches,
basins) 0 moved. 15 held datums 0 moved (11 on 3 shared sheets `pav10` / `pav29` / `pav32`, all 3.96). Runway 0 of 1,867.
Census 164 = 164, CRITICAL 0 / 1,932 = 0 / 1,932. `hard_conflict` {} = {}.

## Verdict against the bars (R-E + C2, this tree d4330dea = a4c2b6d9 + main 469d18ea)

| bar | HECA | KCLT | SPJC | OTHH |
|---|---|---|---|---|
| null-change ≤ 20 at 0.02, 0 over 0.3, every pass | **MISSED** pass 2: 164 / 0 / 0.107 (pass 1 0/0 — C2 works) | **MISSED** pass 1b 47 / 0 / 0.185, stage 2 90 (m misses too: 18 / 4 / 0.538) | met | met |
| rim steps AIR-TOUCH 0 | 0 (from 21) | 0 (from 3) | 0 (from 1) | 0 |
| datum = apron on its rim | 0 off | 0 off | 0 off | 0 off |
| runway (10a: ≤ 0.5 m and gentle) | worst +0.14; 7 sites over 0.1 pp / 30 m (peak 0.29 pp), no step | 0 | 0 | 0 |
| taxi tier ± 3 | 64 = 64 | 50 → 49 | 7 = 7 | — |
| pad `hard_conflict` | 104 → 68 | 33 → 34 | 1 = 1 | — |
| adjudicated airside not rising | 12,022 → 12,041 | 2,971 → 3,067 | 714 → 723 | = |
| CRITICAL not rising | **motion 3 → 4, visual 1,962 → 1,982** | = | = | = |

C2 as landed is NOT broken on the real path: it does exactly what the PR says (pass 1a 0 movers at HECA and KCLT, was
13/1/0.914 and 17/0/0.143) and moves no pad, datum or runway. No engine code changed by this lane.

Instruments: `docs/briefs/reverify-scratch/` (`pair.sh`, `noC2.py` control driver, `rw.py` runway shape read, `datum.py`,
`taxi_hist.py`, `cen.sh`, `chain2.sh`, `cmp_air.py` = seatspec's `cmp_arm.py` + the AIR rows). Frames registered (lane
reverify): the four c2 patches.
