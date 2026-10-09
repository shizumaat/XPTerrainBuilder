# pads64 notes — resumes pads63 (killed by an outage mid-J3), 2026-10-08

Branch `claude/pads63`, worktree `.claude/worktrees/pads63`. Scratch `<scratch>/pads64/` (`.progress`, arms `b1/` = J1 + main,
`j3b/` …), the dead lane's `<scratch>/pads63/`. Probes `docs/briefs/padspec-scratch/pads63/` (`widened.py`, `scrapprobe.py`,
`cj.py`). Captures: `gaps3/HECA.pkl` (two passes: the second `--late-from` the first's `solved.pkl`), `perfB362/OTHH.pkl`,
`<scratch>/sweepwalls/base/{KCLT,KASE}.pkl`; all `--from classify --emit --verify --workers 6` (`<scratch>/pads63/arms.sh`).

## 1. What the WIP commit `62272499` is — KEPT (decision)

A complete first draft of J3 as amended by 08d (2), by the dead lane, replayed once as arm `j3a` (pre-merge-of-main):

* `constraints/no_step.hold_interval(airport=)`: reach bands read from `reach_band_values` (their one derivation) before the
  08k withdrawal; per block `seat_misfit(pair interval ∩ reach intersection)`; misfit in (tol, floor) → datum prefers the
  gap's middle, its frontage contacts join `HoldInterval.widen`; non-empty finite reach intersection → hard Band on the datum.
* `constraints/weld_floor.py` (new): `seat_misfit`, `pavement_heads` (taxi + apron tiers of `hard_conflict_ranks`),
  `widen_weld_rows` (Diff `cap + floor/d`, Linear by `floor·|coef|`; never a row naming a runway-family vertex; idempotent).
* `HoldPass.widened` applied in `derive` / `apply`, and by the ribbon-free join in `stage_one_map`.
* sidecar `platforms[].misfit_m` / `weld_widened {floor_m, contacts, rows, runway_rows_kept}`;
  `check_grade.weld_widened_nodes` → `within_shape`, `cross_shape`, `pavement_over_road_cap` take `+floor` on a pair naming a contact.
* twins `tests/auto_patch_v2/test_weld_floor.py` (8), `tests/test_weld_floor_census.py` (3): GREEN on the merged tree.

Arm `j3a` vs `j1` (pre-merge frames, `<scratch>/pads63/{j1,j3a}`; `<scratch>/pads64/pads.py` on the sidecars):

| airport | j1 released (pads / welds) | j3a | notes |
|---|---|---|---|
| KASE | 1 / 6 (`building1` max 0.652) | **0 / 0** — misfit 0.543, widened, 13 contacts, 258 rows, datum 2368.092 → 2368.337 | body 71ac54b9cbf1 → eabb13f08808 |
| HECA | 6 / 27 (`building147` 11 @ 0.47; `building105` 8 @ 0.234; 138 / 157 / 165 / 193 at 0.02–0.04) | 5 / 9 — `building147` **0** (misfit 0.775, 63 contacts, 3,779 rows); `building105` 8 → 1 @ 0.023; the four small ones unchanged (0.020–0.042 m, misfit 0) | body d1157073da5a → 934a8459ff3a (first pass only; no `--late-from` pass ran) |
| KCLT | 0 / 0 | 0 / 0 | body 2c3e4c83f0db → 24fb0823c9ae |
| OTHH | — | not run | `scrapprobe OTHH rc=1` = BrokenPipeError in the pool spawn at 18:58 = the outage, not a logic error |

OPEN after j3a: (a) HECA's 9 residual welds at 0.020–0.042 m on five pads with misfit 0 (solver residual class, just over
the 0.02 m release tolerance) — to attribute; (b) 3,779 rows at `building147` is every pavement row naming a contact, the
brief wants only the rows that close the set; (c) OTHH never replayed; (d) the scrap rule (J1 leftover) not started.

## 2. Merge of main `d0b2f0f4` (walls) — done `79c2bc9d`

Conflicts: `docs/frames.jsonl` (both kept), `test_gap_terrace.py` frame tuple. The tuple is read by the test itself from
`gaps3/HECA.pkl` + `gaps3/BASE/solved.pkl` under this tree's classify + `cut_classification`: **(84, 34, 66, 9)** measured
(= main's; the S1 arm's (93, 48, 66, 6) was the 8 % cap), sites `gap:7/lot`, `gap:7/lot`, `gap:0/s4/lot` hold. 24 passed.

J1 + main base tree: worktree `pads63j1`, LOCAL branch `claude/pads64-j1base` `33bbf20a` (= `0adb422b` + main; differs from
this branch by the J3 WIP only). Not pushed; scaffolding for the base arm.

## 3. Next

1. base arm `b1` (J1 + main) on the four captures; 2. `j3b` = this tree; 3. attribute the residual releases; 4. scrap rule.
