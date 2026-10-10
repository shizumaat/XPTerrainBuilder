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
