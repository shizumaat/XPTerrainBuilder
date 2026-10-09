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

## 3. J1 re-proof on main = base arm `b1` (tree `claude/pads64-j1base` 33bbf20a; `<scratch>/pads64/b1`, HECA late pass `b1L`)

| airport | body | released pads / welds | hard_conflict taxi / pad / groundside | WARNED |
|---|---|---|---|---|
| KASE | 5e5209666176 | 1 / 6 (`building1` 0.652) | 0 / 56 / 2 | 1 |
| KCLT | d1aea0f26c24 | 0 / 0 | 51 / 28 / 288 | 0 |
| HECA (late pass) | 6fdaa01a95ba (first pass b7972faaf5fa) | 6 / 27: 147 9 @ 0.415, 105 10 @ 0.269, 157 3 @ 0.039, 165 3 @ 0.042, 138 1 @ 0.021, 193 1 @ 0.020 (= sw6 main's six pads) | 71 / 128 / 246 | 1 (147) |
| OTHH | (running) | | | |

## 4. J3 as reworked by pads64 (commit `dd240199`) — DECISIONS

* KEPT from the WIP: the reach-band read before withdrawal, `seat_misfit`, the datum at the gap's middle, the hard Band on the
  datum inside a non-empty reach intersection, `pavement_heads`, `widen_weld_rows`' row statement, the sidecar record, the census read.
* CHANGED (a): ONLY THE CONTACTS THAT CLOSE THE SET GIVE, EACH BY WHAT IT IS SHORT (`weld_floor.contact_gives`: a contact whose
  own pair-graph interval ∩ reach band excludes the level gives `shortfall + hard_tol_m`; ≤ the misfit, so always under the
  floor). The WIP gave the full 1.0 m floor to every row naming any frontage contact. MEASURED at KASE `building1` (misfit 0.543):
  WIP 13 contacts / 258 rows, steepest widened grade 7.59 % (cap 1.5 %) over 14.1 m, one chord used the whole 1.000 m;
  reworked 9 contacts / 167 rows, steepest 4.62 % over 14.1 m at 39.22010294331, -106.86487635609, largest give used 0.572 m;
  released 0 in both. DEVIATION from the brief's letter ("widened by floor/d"): the floor is the GATE (misfit < 1.0 m), the give
  is the contact's own shortfall — less pavement over its cap for the same weld.
* ADDED (b): THE WELD PROJECTION (`weld_floor.seal_welds`, `HoldPass.seal`, called in `solve/flex.stage_one` after pass 1b,
  before stage 2 substitutes the airside). ATTRIBUTION of HECA's four small released pads (157 / 165 / 138 / 193, 0.020–0.042 m,
  the same on main `sw6`): `relprobe.py` on the j3a solved set — NO `hard_conflict` row names them, the law is satisfiable
  ("min total shortfall 0.0000 m — the residual is the solve's"), the hold rows stand 0.02–0.04 m over, i.e. the augmented
  Lagrangian's unsettled residual (31 of 543,689 stage-1 hard rows over 0.02 m), which `[design] polish_rounds_max` documents as
  not certifiable. A weld row governs one contact against a solved datum column: the projection is an assignment (the zone
  projection's argument, 12ag). Every weld the feasibility LP did not relax, off its datum by more than `hard_tol_m` and under the
  floor, takes the datum; a relaxed weld, a runway-family contact and a contact two blocks hold are left. Each sealed contact
  is recorded in `platforms[].weld_widened.contacts` with its move (the pavement gave by that much there).
* census: `check_grade.weld_widened_nodes` → `{node: give}`; a pair naming a contact takes that contact's give (never more than the record's floor).

KASE arm `j3c` vs `b1` (`<scratch>/pads64/inst.sh`): released 6 → **0**, WARNED 1 → 0, runway movers 0, solve-owned movers 93
(taxi 13 / 0.34, apron 74 / 0.50, strip 6 / 0.28; over 0.3 m: 4, 0 far-field), hard_conflict taxi 0 = 0, pad 56 → 0,
groundside 2 → 1; census (b1 under the base tree's tool, j3c under this tree's): adjudicated airside 2,594 → 2,523,
critical_motion 1 = 1, critical_visual 44 = 44, `pad_frontage_infeasible` 1 → 0, `hard_conflict` 56 → 0, `within_shape` 2,610 → 2,598. Body 75fcd0de0f1f.

* ADDED (c) (commit `20c98407`): a closing contact that is itself a FIXED point (a stage-1 pin, a runway column) cannot give —
  such a block is not welded by the pavement (misfit recorded, the solve's release + the warning stand: the diagnostic of (4));
  a pinned contact is never sealed. Twin `test_nearmiss148` (rim pinned 700.5 / near-miss pinned 701.5) holds as before.

KCLT arm `j3d` (20c98407) vs `b1`: body d1aea0f26c24 → 49b7ac1a6e73; released 0 = 0; no misfit, nothing widened, weld_seal 0
contacts, every pad datum within 0.001 m; runway movers 0; hard_conflict taxi 51 = 51, pad 28 = 28, groundside 288 → 287;
CRITICAL motion 5 = 5, visual 1,997 = 1,997; adjudicated airside 3,043 → 3,088 (`within_shape` 9,971 → 10,010).
BUT 580 solve-owned movers at 0.02 m (strip 516 / 0.90, apron 47 / 1.02 at 35.21575607491, -80.9438469184, taxi 17 / 0.51;
over 0.3 m 88, 60 far-field). SUSPECT (to prove by one arm): the new hard Band on each datum column inside its reach
intersection — non-binding everywhere here, but a changed row set → the unsettled solve / the feasibility LP lands on another
optimum (the null-change class of §56 (10) F1). Arm `x_noband` KCLT owed.

## 5. Next

`j3c` arms KCLT / HECA (+ late) / OTHH run from the FROZEN tree `pads63j1` detached at the arm's sha (`chain_j3.sh TAG SHA`), so this
tree stays editable. Then: instruments per airport (`inst.sh`), the scrap rule (read `scraps.py` on `b1/OTHH`), closing builds.
