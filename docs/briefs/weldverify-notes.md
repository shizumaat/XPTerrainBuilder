# weldverify notes — measuring PR #504 (`claude/cloudweldfix` b8c8e988) on the corpus; §63 acceptance

Lane `weldverify` (Opus). Worktree `.claude/worktrees/weldverify`, branch `claude/weldverify` = `origin/claude/cloudweldfix`
b8c8e988 + `origin/main` 469d18ea0 (merge b57214e32; main since the base adds two log/sidecar-sum commits, no patch change).
Scratch `<scratch>/weldverify/` (`.progress`, `pair.sh` / `acc.sh` / `cmp.py` / `cencmp.py` copied from `<scratch>/weld63/`,
bases `b0` / `kb0` and weld63's `w1` / `kw1` symlinked — controls shared, not rebuilt). Frozen replay tree `weld63frz`.

## RESUME HERE

* Step 1 running: `chain1.sh` = `v1` (HECA, head b57214e32, `--null-change`, census), `kv1` (KCLT, head, `--null-change`,
  census), `x1` (HECA 44f9955b = W + B′ + P before the cloud commits), `kx1` (KCLT 44f9955b), `s1` (HECA 23ad159e = S + T).
* Then `acc.sh <arm> <ICAO> <base>` and `cencmp.py`, the table below, sites, SPJC / CYXY / OTHH, the closing build.
