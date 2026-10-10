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
