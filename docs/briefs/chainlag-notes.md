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
| p2 | 5a589e4e | (Q2 option a under the OLD seniority: the leader face's frontage follows the pad) — KILLED unrun: moot after 09j |
| q1 / kq1 | cce61d26 | 09j's order in ROW form: `_airside_only` drops every groundside role (no groundside seat), `groundside_frontage` leads from EVERY pad; HECA + KCLT |

## Results (all in spec §63 (9); the per-run lists are `<scratch>/chainlag/<arm>/cmp.txt`, `prow.py` output, `gap_<ICAO>.txt`)

* p0: C 15 / 564 → 17 / 957 m; pad conflicts 104 → 15; airside 0; lag 845 unsettled (1.544 m); stage 2 53.4 s.
* p1: C 18 / 766; lag 764 unsettled; `building12` | `pav57` 5.74 m / 386 m — the order is not the defect (refuted).
* MID-LANE: owner RULINGS 2026-10-09j (main 116152e0) — pads senior to roads; touching (source geometry) welds, a gap
  is free. The brief's Q1/Q2 are withdrawn by it.
* gapread (knife off): HECA 15 of 18 C/B runs OVERLAP the pad (565 of 631 m); KCLT 7 of 13; SPJC 2 of 5. With the
  knife ON the same read gives 0.64–0.70 m everywhere: the gap is `classify/roles._cut_back_groundside`'s.
* q1: C 12 / 1,040 m, apron 7 movers 0.28 m, pads rise to their DEM datum, the roads stay (hard law vs a soft row) —
  the row form is ruled out, the weld is the design. kq1: C 8 / 128, ARMED 4 / 54, pad 33 =, airside 0 (strip 7 at
  0.06 m).
* why-at on p0 at `building12` (30.11544369885,31.40991480491): v26991 binding = 3 `pads` rows only; chain 10 hops /
  +9.45 m to a `route3` ramp-ceiling Band (groundside_frontage_level +1.46, transverse +1.75, apron_preference +4.47):
  the road's level is the apron's through the road law, 10 m under the DEM there — Q-B's road.
