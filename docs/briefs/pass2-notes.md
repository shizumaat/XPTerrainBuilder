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
