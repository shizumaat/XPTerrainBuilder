# chainlag notes — spec author for §62 R-C's order problem (the chain road → pad → lot)

Lane `chainlag` (Fable, SPEC AUTHOR with probes). Worktree `.claude/worktrees/chainlag`, branch `claude/chainlag` off
`origin/claude/seat2` ec43c00a (the deliverable: spec §63 + this file + `chainlag-summary.md`). Probe tree
`.claude/worktrees/chainlagrun`, scratch branch `claude/chainlag-probe` (never merges); replays run from the FROZEN
worktree `.claude/worktrees/chainlagfrz` checked out detached at each arm's sha (`<scratch>/chainlag/pair.sh NAME ICAO
SHA`). Scratch `<scratch>/chainlag/` (`.progress`).

## Frame

* Captures: the registered pads67 captures `frames/pads67/{HECA,KCLT}.pkl` (seat2's frame).
* Arm = the late-stage replay pair of spec §62 (5a) (`--from classify --gap-free --workers 9 --solved-out`, then
  `--late-from` with `--emit`), `tools/pad_edge_read.py`, classes by `<scratch>/seatspec/cmp_arm.py` (pads67 logic),
  `tools/airside_value_delta.py --tol 0.02` against the base.
* BASE = seat2's `m` (HECA) / `km` (KCLT): the merged tree (main 1e524b12 + R-D rule 1) — `Ortho4XP/src` and `tools`
  are byte-identical between 67e7f587 (where `m` ran) and ec43c00a (this tree): `git diff --stat` empty.
* Probe tree commit ef0cae5b = seat2-rc's R-F + R-C rules 1 and 2 + the hard∩one-way solver change + publication +
  twins, applied clean (`git apply --3way`) onto ec43c00a; R-B (`frontage_release`), R-D rule 2 and the gap-mint moves
  LEFT OUT (R-D rule 1 is already on the tree). Twins: 18 of 19 pass; the one red is R-B's own twin
  (`test_no_ramp_row_or_join_pin_stands_on_a_frontage_vertex`), expected without R-B.

## Arms

| arm | sha | what |
|---|---|---|
| p0 | ef0cae5b | the probe tree as found (= seat2's `b2`, on the merged tree): the control |
| p1 | (next) | M2 + M1: the one-way lag in LEADER ORDER (depth), pad-level rows read once |
