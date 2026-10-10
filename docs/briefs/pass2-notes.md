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
