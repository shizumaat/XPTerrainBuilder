# holering notes — the apron HOLE RING in pass 1a (Fable: attribution, design, fix only if the probe holds)

Lane `holering`. Worktree `.claude/worktrees/holering`, branch `claude/holering` off `origin/claude/seat2-re`
f3596b84 (= main 1e524b12 + §61 + R-D rule 1 + §62 R-E) merged with `origin/main` (6e6f4849: RULINGS 09i/09j/09k,
docs only). Scratch `<scratch>/holering/` (`.progress`, `prelude.py`, `p1a.py`, `arms/`).

## Frame

* The defect (sheetlevel d9b0cb1c, by intervention): under R-E at HECA the runway 05L/23R moves 115 nodes, worst
  +0.14 m, 1.7 km from the sheet; `--null-change` reads pass1 13/1/0.914 (building88's vertex at
  30.12101407579,31.41755189267 = v12285 on the full map), pass2 164/0/0.107, pass3 13/0/0.159 (base m: 7/0, 9/0, 9/0).
  Pinning the runway (arm P) leaves pass 1 at 6/1/0.510 and zeroes pass 2 / stage 2.
* Law: 09i (a pad takes the apron's level), 09k (an apron prefers flat; the 1 % preference STANDS over the trend —
  not touched here), 09e/09h (§61: the edge takes its centreline's level; a vertex no chain reaches takes the
  membrane; null-change ≤ 20 at 0.02 m and 0 over 0.3 m), 09b (runway ≤ 0.1 m).
* Frames reused: seat2's late pairs on `frames/pads67/HECA.pkl` / `KCLT.pkl` (`<scratch>/seat2/{m,e,km,ke}`),
  sheetlevel's arms P / N / W (`<scratch>/sheetlevel/`). No new capture.

## Instrument (scratch, never lands)

`prelude.py ICAO OUT.pkl` runs `v2_solve_replay.replay_problem(--from classify --gap-free)` ONCE and pickles
`{pm, cs, law, airport, stage1}`; `p1a.py PROB.pkl ARM` solves PASS 1a alone (the ribbon-free stage-1 problem with
the hold rows stripped, `flex.yield_stage_one` as the build runs it) twice — the arm, then the arm plus the 30 §61 (6)
ceilings (`replay_null.ceilings` on the arm's own pass-1a levels) — and reports movers over the levelled set by vertex
class: apron HOLE RIM (a vertex of a hole ring of an apron face), PAD-ONLY (building faces only), RUNWAY, other.
Arms: `base` (R-E as on the branch), `noRE` (the cross-ring rows dropped = m's pass 1a), `pinrim` (rim + pad-only
columns pinned at the arm's own pass-1a values: the intervention), candidates by name. `--rows V…` prints every
assembled pass-1a row at a vertex. A pass-1a pair is ~3 min at HECA against ~20 min for the full late pair.

## Step 0 — reproduce (pending)
