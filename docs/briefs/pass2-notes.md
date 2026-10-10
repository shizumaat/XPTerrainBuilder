# pass2 notes — the three reads reverify left unattributed (A HECA pass 2, B KCLT pass 1b, C the census)

Lane `pass2`. Worktree `.claude/worktrees/pass2`, branch `claude/pass2` = `origin/claude/reverify` 236a50108 merged with
`origin/main` 6dfb97854 (RULINGS 10a, docs only). Scratch `<scratch>/pass2/` (`.progress`). `--workers 9`, one heavy
thing at a time (weldverify shares the machine). No airport build.

## Step 0 — setup, frame (done)

* Captures reused: `frames/pads67/{HECA,KCLT}.pkl`. Arms reused: reverify's `c2` / `kc2` / `km0` (`<scratch>/reverify/`).
* Instrument: `prelude.py` (holering's, this tree) pickles the gap-free stage-1 problem once per airport
  (`<scratch>/pass2/{HECA,KCLT}_prob.pkl`); `p1b.py` runs `flex.stage_one` (pass 1a → interval → pass 1b [→ re-widened
  pass]) twice — the arm, then the arm + the 30 §61 (6) ceilings — with interventions on the second run.
* First observation off reverify's own JSON (`c2/base_gf.json`): HECA `promoted` per pass [632, 879, 878] vs
  [633, 879, 878] — pass 1a's surface is identical (worst 0.0001 m) but one more row is promoted on a miss in the twin.

## Step 1 — B, is KCLT's `pav101` instability on main? (NO)

`tools/v2_solve_replay.py --replay frames/pads67/KCLT.pkl --from classify --gap-free --null-change` on a worktree of
`origin/main` 6dfb97854 (`.claude/worktrees/pass2main`, `<scratch>/pass2/B_main_pads67.log`):
`NULL-CHANGE pass1a 0/0/0.000 pass1b 0/0/0.020 stage2 0/0/0.020 (promoted 145=145, lp relaxed 331=331)` — MET.
Same capture as reverify's `km0` (m tree 67e7f587: 10/0/0.040, 18/4/0.538). So it is NOT the capture and NOT on main:
it is in the 44 src commits between main and the m tree (the pads57–pads67 collar-deletion / weld-floor stack + R-D
rule 1). The valley2 capture on main is run as the second control (below).
Second control, `frames/valley2/KCLT.pkl` on main (`B_main_valley2.log`): the same line, `0/0/0.000 · 0/0/0.020 · 0/0/0.020
(promoted 145=145, lp relaxed 331=331)`. Pass-1b QP exits on main: `no_descent ×3`; on the m tree (`km0`) `round_cap 1,
no_descent 2`; on this tree (`kc2`) `round_cap 1, no_descent 1, optimal 1`.

## Step 2 — the pass-1b instrument and the first interventions (KCLT, this tree = R-E + C2)

`p1b.py` (stage 1 alone, twice; `<scratch>/pass2/arms/`) reproduces the full replay exactly: `K_r400` pass 1a 0/0/0.0041,
pass 1b **47/0/0.1846** (= `kc2`).

| arm (KCLT, this tree) | pass 1a | pass 1b | what it shows |
|---|---|---|---|
| base (`K_r400`, exits traced) | 0/0/0.0041 | 47/0/0.1846 | pass 1b's FIRST QP (the warm-up, cold start) ends `round_cap` at 400 rounds with F 260888.4639 (arm) vs 260888.6728 (twin), \|g\| 4.9 / 4.6; pass 1a's two QPs end `optimal`, F equal to 2e-5 |
| `lv1a` — the twin's `hold.derive` reads the ARM's pass-1a levels | 0/0/0.0041 | **47/0/0.1846** | REFUTED: the 1a → interval → 1b derivation. The interval's rows are identical in both runs (5,106 rows, 0 Band differs, fronting set equal, 0 widened) and the movers stand |
| `r4000` — `design_qp._ROUNDS_MAX` 400 → 4000 | 0/0/0.0041 | **41/0/0.2631** | REFUTED as the mechanism: no `round_cap` any more — the warm-up ends `no_descent` at 435 / 445 rounds, F 260888.3263 vs 260888.3497 (\|g\| 4.55) — and the movers stand (other sites: `dsf:pol14` −0.263) |

So at KCLT pass 1b's own QP does not reach ONE optimum: two solves of the same problem (+30 satisfied ceilings) stop
0.02–0.2 apart in objective (1e-7 relative, against `qp_rel_tol` 1e-12) because no damped step of the normal-equations
solve descends any further (`no_descent`, gradient norm ~4.5 — pass 1a stops at 0.17). §61 (0)'s class again: a set of
columns whose curvature is far under the stiff rows'. WHICH columns and rows: step 3.

## Step C-1 — the census, row level (`tools/harness/census.py --rows-json`, both patches censused on THIS tree)

Row key = (family, roles, way ids, the pair's two end points to 0.5 m). `cdiff.py`, airside rows:

| HECA family | m → c2 | NEW (c2 only) / GONE (m only) / kept |
|---|---|---|
| `within_shape` | 44,300 → 44,377 | 934 / 857 / 43,443 |
| `transverse` | 353 → 379 | 39 / 13 / 340 |
| `strip_seam_tear` | 22 → 37 | 15 / 0 / 22 — ALL 15 at one site, 30.1311, 31.3980 (strip ways −10870 \| −11127): one side 62.06 → 62.24, the other 64.00 → 64.76 |
| `pad_frontage_infeasible` | 0 → 4 | 4 / 0 / 0 (0.105 / 0.075 / 0.059 / 0.053 m; pads at 30.13248, 31.41206; 30.12946, 31.41327; 30.13346, 31.41208; 30.13399, 31.41138) |
| `adjacent_ground_step` | 5 → 8 | 3 / 0 / 5 (two at the same 30.1311, 31.3980 site, one at 30.11972, 31.40926) |
| `airside_no_step` | 4,047 → 4,038 | 49 / 83 / 3,989 |
| `taxi_box` | 2,460 → 2,452 | 82 / 90 / 2,370 |
| `terrace_actual_step` (airside) | 0 → 1 | the CRITICAL row, below |

| KCLT family | m → c2 | NEW / GONE / kept |
|---|---|---|
| `within_shape` | 9,413 → 9,600 | 280 / 93 / 9,320 |
| `transverse` | 4 → 8 | 6 / 2 / 2 (five at one junction, 35.22399, −80.93760, way −10177: 224.96 → 224.55 against 225.42 → 225.25) |
| `drainage_minimum` (deferred) | 1,929 → 1,849 | 120 / 200 / 1,729 |

The census's pair population is the PATCH's (pairs inside one emitted way, joints from the sidecar); it never reads a
constraint row, so R-E's cross-ring pairs cannot enter it as rows. KCLT's two patches have the SAME 22,130 nodes and
1,718 ways (HECA: 133 / 179 nodes and 4 ways differ — the late stage's cuts follow the surface). The intervention
(census of c2's geometry + sidecar carrying m's elevations = `hyb`) is queued.

## Step C-2 — the CRITICAL row: `terrace_actual_step` apron|apron 3.62 m at 30.12155524, 31.41995156

* WHAT LAW: owner RULINGS 2026-10-03c (#291) "THE WALL IS THE STEP" — a pack-placed wall between two levels is a DECLARED
  terrace (`airport/road_ramp.wall_terraces`, `pipeline/publication.wall_terrace_joints`). The joint here is sidecar
  `terrace_joints[74]`, `kind wall_terrace`, object `Airport/Hangar/metal_strip_2.obj#comp12`, height 3.102 m, outline
  292.7 m long, passing 2.1 m from the site, in BOTH arms. So yes: a declared terrace, and the two aprons (`objpav402`
  ways −10421 below, `objpav1` −10386 above, across `small_roads:-18656`) stand a wall apart by the pack's own object.
* WHY THE ROW IS NEW: the joint's DECLARED step is `min(wall height, the step the solve put across it) + 0.01`, the
  second read as the largest (upper vertex − nearest lower vertex) over the wall's own `upper` / `lower` sets (1 pair,
  2 lots). m: emitted 6.337 → declared 3.112; the pair at the site steps 3.1–3.2 ≤ 3.112 + 1.5 % · 4.7 + 0.11 → lawful.
  c2: emitted **1.357** → declared **1.367**; the same pair steps **3.62** → over. Two things moved: the wall's lot
  pairing reads 5 m less (the pads of the sheet came down 7–9 m under R-E, the lots follow their pads), and the
  apron|apron step at this site grew 3.15 → 3.57–3.62 (`objpav402` 95.38 → 95.17, `objpav1` 98.5–98.6 → 98.7–98.8).
* Even at the wall's full height the pair would now be over: 3.62 against 3.102 + 0.01 + 0.07 + 0.11 = 3.29 (0.33 m).
  In c2 there are two more rows on the same line (`apron|service_road` mixed, 2.68 and 2.48 m; not airside-adjudicated).

## Step C-3 — instrument population vs surface, BY INTERVENTION (the hybrid census)

`hybrid.py`: c2's patch geometry AND c2's sidecar, carrying m's elevations (joined by the 11-dp lat/lon key), censused by
the harness (`<scratch>/pass2/cen/{KCLT,HECA}_hyb.*`). If R-E changed what the census COUNTS, the hybrid reads c2's
number; if it changed the SURFACE, the hybrid reads m's.

| airside family | KCLT m / c2 / **hyb** | HECA m / c2 / **hyb** | reading |
|---|---|---|---|
| `within_shape` | 9,413 / 9,600 / **9,413** | 44,300 / 44,377 / **44,298** | SURFACE |
| `transverse` | 4 / 8 / **4** | 353 / 379 / **353** | SURFACE |
| `strip_seam_tear` | — | 22 / 37 / **22** | SURFACE |
| `adjacent_ground_step` | 17 / 16 / 17 | 5 / 8 / **5** | SURFACE |
| `airside_no_step` | 479 / 475 / 479 | 4,047 / 4,038 / 4,047 | SURFACE |
| `strip_transverse`, `taxi_box`, `frontage_near_miss`, `mid_edge_step`, `vertex_to_edge_step`, `pad_airside_weld`, `strip_arc` | hyb = m | hyb = m (`taxi_box` 2,461 vs 2,460) | SURFACE |
| `pad_frontage_infeasible` | 0 | 0 / 4 / **4** | SIDECAR RECORD (the build's own: a held block with a frontage weld the §5a LP released) |
| `hard_conflict` | 83 = 83 | 168 / 132 / **132** | SIDECAR RECORD (the §5a LP's relaxed rows) |
| adjudicated airside | 2,971 / 3,067 / **2,971** | 12,022 / 12,041 / 12,011 | |

KCLT's hybrid is exact (the two patches have the same nodes and ways): every airside family reads m's count to the row.
HECA's is exact but for 133 nodes the two late stages cut differently (its artefacts: `runway_crown` 12,
`terrace_actual_step` 4, `road_coverage_join` 2 — c2's declared joints against m's surface).

VERDICT (i) / (ii): NO family rises because the census counts R-E's cross-ring pairs — the census enumerates pairs inside
one emitted way and never reads a constraint row. The whole rise of `within_shape` (+77 / +187), `transverse` (+26 / +4),
`strip_seam_tear` (+15) and `adjacent_ground_step` (+3) is the SURFACE. Two families are the solve's own record in the
sidecar: `hard_conflict` (168 → 132) and `pad_frontage_infeasible` 0 → 4 — four held blocks each with a frontage weld the
§5a LP released under R-E (1 / 1 / 3 / 1 contacts, worst 0.105 / 0.075 / 0.059 / 0.053 m, at 30.13248410, 31.41205718;
30.12945762, 31.41327142; 30.13345834, 31.41207791; 30.13398605, 31.41138257): the nearest thing to "rows that exist
because R-E's pairs exist" — the cross-ring cap rows are hard and in the §5a set — and they are a real 5–10 cm step on a
pad rim, not an instrument artefact.

The `within_shape` churn is a threshold population: HECA 934 new / 857 gone on 43,443 kept; the new rows are long chords
a few cm over cap (the largest by magnitude: `secondary_parallel` 7.63 m over 492 m = 1.551 % vs 1.5 %, 0.25 m over).

### The 10 worst NEW airside rows, by excess over the row's own limit (`worst.py`; m → c2 at the pair's two ends)

HECA:
1. `terrace_actual_step` apron|apron 30.12155524, 31.41995156 — 3.62 m over 4.7 m against the declared 1.37 (C-2):
   98.60 → 98.79 | 95.38 → 95.17.
2. `strip_seam_tear` graded_strip|graded_strip 30.13110296, 31.39802377 — 2.56 m over 4.0 m (15 rows, one seam between
   strip ways −10870 | −11127; no cap, a step family): 64.04 → 64.80 | 62.06 → 62.24 — one strip follows the taxiway
   up 0.76 m, the other 0.18 m; the same two vertices stood 1.98 m apart in m (not a row there) and stand 2.56 m.
3. `airside_no_step` junction|stub 30.13858425, 31.40696635 — 1.35 m over 65 m (3.05 %): 62.52 → 62.58 | 63.82 → 63.93.
4. `airside_no_step` cross_connector|cross_connector 30.12139524, 31.41177461 — 1.09 m over 27 m (2.57 %): 89.43 = |
   90.69 → 90.52.
5. `within_shape` building|building (way −10442, a pad on the sheet) 30.12201985, 31.41904101 — **1.05 m over 21 m =
   4.99 % vs 1.5 %**: 102.97 → 94.89 | 102.91 → 93.84. The pad came down 8–9 m with the sheet (09i) and is no longer
   one level: a second row 0.78 m over 30 m on the same pad. (m: flat within 0.06 m.)
6. `airside_no_step` secondary_parallel 30.11589254, 31.41231429 — 0.97 m over 106 m: 97.73 → 97.24 | 98.93 → 98.21.
7. `adjacent_ground_step` graded_strip 30.13117061, 31.39795631 — 0.91 m over 2.5 m (the seam of row 2): 63.85 → 64.61 |
   63.14 → 63.70.
8. `adjacent_ground_step` graded_strip 30.11972181, 31.40925572 — 0.84 m over 2.5 m: 87.78 → 86.90 | 88.57 → 87.74.
9. `airside_no_step` cross_connector|junction 30.11946028, 31.41511333 — 0.70 m over 59 m: 97.67 → 97.74 | 98.37 → 98.44.
10. `within_shape` cross_connector 30.12112235, 31.41119611 — 2.62 m over 129 m = 2.03 % vs 1.5 % (0.69 m over):
    90.25 = | 88.31 → 87.63.
(Not new: `within_shape` building|building 6.10 / 5.61 m on pad way −11452 at 30.11976005, 31.40700398 — the same pad
reads 5.74 / 5.71 / 5.69 m in m through other pairs.)

KCLT (all but one at ONE junction, `pav`-way −10177 at 35.2240, −80.9376, which sinks 0.3–0.47 m against a runway-side
edge that does not move):
1. `transverse` junction|primary_parallel 35.22399066, −80.93759630 — 0.70 m over 25 m (2.80 %): 224.96 → 224.55 |
   225.42 → 225.25 (four more `transverse` rows beside it, 0.60 / 0.60 / 0.49 m).
2. `airside_no_step` junction|junction 35.22426215, −80.93771709 — 0.68 m over 30 m: 225.60 → 225.30 | 225.04 → 224.62.
3. `within_shape` primary_parallel|runway 35.22462487, −80.93695912 — 2.02 m over 102 m = 1.98 % vs 1.5 % (0.49 m over):
   227.13 = | 225.58 → 225.11 (three more to the same vertex 35.22449522, −80.93749750: 0.35 / 0.34 / 0.38 m over).
4. `within_shape` primary_parallel 35.22442206, −80.93686853 — 1.44 m over 68 m = 2.13 % (0.43 m over): 226.98 = |
   225.94 → 225.54.
5. `strip_arc` graded_strip 35.22118171, −80.93695414 — 0.39 m over 40 m: 225.10 = | 224.65 → 224.71.
6. `airside_no_step` junction|junction 35.22407287, −80.93770888 — 0.36 m over 23 m: 225.21 → 224.91 | 224.96 → 224.55.

## Step 3 — A and B are ONE mechanism: the linear solve's precision floor under the QP (attributed by intervention)

HECA, same instrument (`A_lv1a`): pass 1 0/0/0.0001, pass 2 **164/0/0.1071** (= the full replay's), and with the twin's
interval derived from the ARM's pass-1a levels the 164 stand (interval rows 5,097 = 5,097, 0 Band differs) — the
1a → 1b derivation is REFUTED at HECA too. (Pass 3 read 263/0/0.178 in this pair against the replay's 13/0/0.154: the
same junction cells, the other sign — pass 3 lands them anywhere.)

WHO MOVES (`rows1b.py`, KCLT pass 1b, the 47 movers): 38 of the 47 columns carry NO level row — only relational rows:
`bend` 186, `free_membrane` 59, `taxi_xsec` 35 (and one body-mean datum). The `pav2` junction / graded-strip cells at
35.2087, −80.9500 are one flat block (every vertex 213.082) tied by `taxi_xsec` rows to its chain; every one-sided row on
them is SLACK (1,555 hard and 1,7xx soft rows, 43 active). They are §61's own rows doing what §61 built them to do; in
pass 1a the same columns are stable. So the columns are not unnamed — the SOLVE does not resolve them:

| arm (KCLT pass-1b pair) | warm-up QP exit (arm / twin) | \|g\| at the QP exits | pass 1a | pass 1b |
|---|---|---|---|---|
| base | `round_cap` 400 / 400, F 260888.464 / .673 | 4.9 – 5.5 (pass 1a 0.17) | 0/0/0.004 | 47/0/0.185 |
| rounds 4000 | `no_descent` 435 / 445, F 260888.326 / .350 | 4.6 – 5.5 | 0/0/0.004 | 41/0/0.263 |
| rounds 4000 + backoff ladder 12 → 40 (λ to 1e22) | identical to the row above | same | 0/0/0.004 | 41/0/0.263 |
| **the linear solve REFINED twice against A itself** (corrected semi-normal equations: `x += N⁻¹ Aᵀ(b − A x)` on the same LU) | `round_cap` 400 / `optimal` 380, F 260889.33 / 260887.91 | **4e-5 – 1e-4** (pass 1a 0.002 – 0.007) | 0/0/0.016 | **0/0/0.0007** |

MECHANISM: `solve/linear._linear_solve` (method `normal`) factorises the normal matrix AᵀA, whose condition number is
the SQUARE of A's; with hard rows at 3e5 beside bending / membrane / cross-section rows at ≤ 1.0 the factorised solve
returns each proximal step with stiff-direction error worth a gradient norm of ~5 — far above the gradient the weak
(1.0) relational blocks produce. `design_qp.solve_one_sided` then finds no damped step that descends (`no_descent`, or
`optimal` on a sub-tolerance gain) and stops wherever it stands; the weak blocks keep whatever level the path gave them.
The spec already met this floor (§61 (2): "pass 1b … exits at the linear solve's floor (`no_descent`, |g| 4.6)") and
out-priced it with 1.0; the pads57–67 hold stack (the pass-1b rows main does not have) and R-E put more columns under
it. NOT the round cap, NOT the backoff ladder, NOT the pass-1a derivation, NOT a missing row.

What the refinement costs the SURFACE (KCLT pass 1b, refined arm vs unrefined arm): 688 stage-1 vertices over 0.02 m,
6 over 0.1 m, 4 over 0.3 m, worst 0.558 m (the unrefined answer was that far from its own optimum there; the null twin
noise was 47 ≤ 0.185). HECA and the row probes: step 4.
