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

## Step 1 — HECA c2 pair (running)
