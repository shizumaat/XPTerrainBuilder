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

OTHH base `b1` body d3389a1c5a16; arm `j3d` body d3389a1c5a16 — IDENTICAL (J3 changes nothing at the flat airport: released 0 = 0).

HECA arm `j3d` (first pass e230d9ff6466, late pass `j3dL` 065c4ad78805) vs `b1` / `b1L`: released pads 6 → **0**, welds 27 → **0**,
WARNED 1 → 0; runway movers 0; hard_conflict taxi 71 = 71 (new rows 0, gone 0), pad 128 → 112, groundside 246 = 246; welded
1,020 → 1,047. `building147` (39,184 m², 30.12759888, 31.40301330): misfit 0.775 m, datum 70.909 → 71.113, 28 of 63 contacts give
(max 0.795 m), 1,444 rows widened (apron frontage chord 985, no_step route pairs 164, pavement ceiling 93 + 16 Linear, apron ring
edge 34), 0 runway rows met, 189 rows USE the widening; steepest 11.58 % vs cap 1.50 % over 7.8 m (+0.789 m), apron ring edge
30.1281718027, 31.40426373051 → 30.12820337024, 31.40419108472. Sealed: 8 contacts on 4 blocks (138: 1 @ 0.021; 157: 3 @ 0.039;
165: 3 @ 0.042; 193: 1 @ 0.020). `building105` (b1: 9 pad-tier hold rows RELAXED by the LP, s 0.03–0.08 m, 10 released @ 0.269,
datum 82.509): in the arm datum 83.124, no relaxation, released 0 — nothing acted on it directly (the feasibility LP is global);
because that is not a mechanism, the seal was GENERALISED (`27f60b89`): every weld under the floor is sealed, an LP-relaxed one
included (counted `weld_seal.relaxed`); at the floor or over nothing moves and the warning stands.
Solve-owned movers vs b1L at 0.02 m: 2,843 (taxi 1,216 / 0.72, apron 832 / 0.85 at building105, strip 795 / 0.80; over 0.3 m 1,079, 128 far-field).
Census (late pass; the replay's late sidecar LOST the hold report, so the welded contacts were priced with no allowance —
fixed in `27f60b89`, `v2_solve_replay` now carries `hold_report` over the late pass as `pipeline/build` does): adjudicated airside
12,022 → 12,139; critical_motion 3 → 2; critical_visual 1,943 → 1,945 (hairline_pair 1,879 → 1,883 all groundside, strip_seam_tear 22 → 20);
`pad_frontage_infeasible` 6 → 0; `within_shape` 44,647 → 44,559. To be re-read on `j3e`.

KCLT ATTRIBUTION (arm `x_noband` = J3 with the datum's reach Band not stated; `csdiff.py` on the stage-1 sets): `b1` itself carries
ONE reach Band on a datum (35.207295527, -80.93018574: [203.068, 237.673]); removing that one non-binding row moves 268
solve-owned vertices (strip 241 / 0.25, apron 18 / 0.09, taxi 9 / 0.05), and J3's Bands on every datum move 580 (apron 1.02) with
no datum changing by more than 0.001 m. So the KCLT motion is the unsettled solve's response to a changed hard-row set (stage 1:
297 / 361 / 499 rounds in b1 / x_noband / j3d), not a seat. KEPT: the Band is the spec's §57 (3) (ii) and the brief's (1); reported.

## 4b. THE SCRAP RULE (J1's leftover) — the brief's premise is REFUTED by the arrangement read; NO code change

`scrapprobe.py` (pads63's run died rc=1 because the script had NO `__main__` guard: the work pool SPAWNS and every worker re-ran
the probe — 5 h of recursion, then a broken pipe; guard added) on `perfB362/OTHH.pkl` at the re-role, `<scratch>/pads64/scrapprobe_OTHH.txt`,
surplus `building6` pieces AFTER the existing rule: 28 pieces / 1,313 m² border the OPEN apron only (+ 6 apron + structure),
1 borders the plateau only (2.1 m², 97 % covered), 2 plateau + structure (`building6#12` 93.2 m² w 3.50, one 111.2 m² w 3.24:
enclosed but NOT thin), 3 own + structure (58–63 m², ≤ 51 % covered), 5 own (≤ 50 % covered).
At the owner's site (25.259994, 51.6104872, r 150; `scraps.py` on `b1/OTHH`): 56 faces, 1,742 ring vertices, collar 0, building 17
= the pad (183,354 m²) + 16 pieces: seven of 89–96 m² (the jetway-root pads, islands in the apron), 29.6, 7.5, and seven of 0.6–2.6 m².
14 of the 16 border the OPEN APRON, not the pad's own faces and not its plateau; 2 border the plateau (`#12` not thin; the 2.1 m²
one 3 % uncovered). "Bordered by the pad's own faces or its plateau" therefore reaches 0 pieces under the existing floor (thin
< 2.0 m, whole boundary). What would take them: (i) J2's bay plateau makes the apron round them plateau — then the existing rule
takes the thin ones with no change; (ii) an AREA floor for a non-thin enclosed piece (93 / 111 m²) needs a number the law does not
have — an owner / master decision; (iii) re-roling an apron-bordered sliver to open apron drops its hold: NOT a zero level change.

## 4c. Arm `j3e` (commit `27f60b89`; the final code is `b168ff48` + a test-only commit `8179f4c2`: KASE body unchanged)

KASE 75fcd0de0f1f, KCLT 49b7ac1a6e73, HECA first pass e230d9ff6466 / late 065c4ad78805 — all == `j3d` (no LP-relaxed weld was
left to seal: `weld_seal.relaxed` 0). HECA late pass WITH the hold report carried: adjudicated airside 12,022 → 12,062 (+117
without the record: 77 rows were the welded contacts' pairs), critical_motion 3 → 2, critical_visual 1,943 → 1,945
(hairline_pair +4, all groundside; strip_seam_tear −2).

## 4d. CLOSING HARNESS BUILDS (tree `8179f4c2`, tags `p64_*`, references `sw6_*` under MAIN's tool; `<scratch>/pads64/close.sh`)

| airport | body (== replay?) | build s (sw6) | released pads / welds sw6 → p64 | WARNED | taxi-tier sw6 / J1 arm / p64 | runway movers | CRITICAL motion sw6 → p64 | CRITICAL visual sw6 → p64 |
|---|---|---|---|---|---|---|---|---|
| KASE | 75fcd0de0f1f (== j3e) | 35.9 (35.8) | 1 / 4 → **0 / 0** | 0 | 0 / 0 / 0 | 0 | 1 = 1 | 45 → 44 |
| KCLT | 49b7ac1a6e73 (== j3e) | 261.8 (248.2) | 0 / 0 → 0 / 0 | 0 | 51 / 51 / 51 | 0 | 5 = 5 | 1,974 → 1,997 (hairline_pair +24 = the J1 arm's 1,997: collar deletion, J3 adds 0) |
| HECA | b59b39641f50 (build frame; replay late pass 065c4ad78805) | 517.8 (489.5) | 6 / 27 → **0 / 0** | 0 | 67 / 71 (replay frame) / 68 | 0 | 3 → 2 | 1,910 → 1,967 (hairline_pair +59, strip_seam_tear −2; vs the J1 control build: owed below) |
| OTHH | d3389a1c5a16 (== j3d == b1) | 569.5 (435.3, single runs under load, not a timing) | 0 / 0 → 0 / 0 | 0 | 0 / 8 / 8 | 0 (0 movers at all vs sw6) | 0 = 0 | 1,846 → 1,717 |

HECA per pad (p64): `building147` 39,184 m² at 30.12759888, 31.40301330 — datum 71.113, misfit 0.775, 28 contacts give (max 0.795),
1,444 rows, runway rows met 0; sealed `building138` 1 @ 0.021, `building157` 3 @ 0.039, `building165` 3 @ 0.042, `building193` 1 @ 0.020.
KASE `building1` 5,417 m² at 39.21979668, -106.86460425: datum 2367.947, misfit 0.543, 9 contacts (max 0.563), 167 rows, 0 runway rows.
No pad at or over the 1.0 m floor on the four airports; no pad split.

OTHH owner site (25.259994, 51.6104872, r 150): sw6 57 faces / 2,330 ring vertices / collar 12 / building 18 → p64 56 / 1,742 / 0 / 17.
FOUND (J0 / J1's, not J3's): at OTHH the J1 arm and p64 carry hard_conflict taxi 8 / pad 23 where sw6 carries none, with ZERO
solve-owned movers against sw6.

HECA feet (`feet.sh`, `feetcmp.py`; ten sites, r 60; within 0.3 m / feet) sw6 → p64: building147@30.1279552 33/120 → 99/103;
@30.1265141 0/38 → 30/38; building4@30.1141299 5/141 → 63/134; @30.1123068 21/108 → 48/108; @30.1110593 26/90 → 23/87;
@30.1110619 41/107 → 36/102; building64 69/74 =; building29 44/60 → 45/60; building7 / building6 11/164 =; building4@30.1080544 204/272 =.
Whole pad: building4 3,827/11,416 → 4,883/11,492; building147 398/957 → 887/941. The J1 control build (`p64j1_HECA`) is the bar: running.

## 4e. THE MATCHED PAIR AT HECA — J1 control build `p64j1_HECA` (tree `claude/pads64-j1base` 33bbf20a) vs `p64_HECA`

| | J1 control `p64j1` | J3 `p64` |
|---|---|---|
| body | c98496b72d61 | b59b39641f50 |
| released pads / welds | 6 / 27 (147: 9 @ 0.415; 105: 10 @ 0.269; 157: 3 @ 0.039; 165: 3 @ 0.042; 138: 1 @ 0.021; 193: 1 @ 0.020) | **0 / 0** |
| WARNED | 1 (`building147`) | 0 |
| hard_conflict taxi / pad / groundside | 68 / 124 / 252 | 68 (new rows 0, gone 0) / 100 / 252 |
| runway movers | — | 0 (solve-owned movers 2,843: taxi 1,216 / 0.72, apron 832 / 0.85, strip 795 / 0.80) |
| adjudicated airside (each tree's tool) | 12,013 | 12,045 |
| CRITICAL motion | 3 | 2 (`vertex_to_edge_step` −1) |
| CRITICAL visual | 1,954 | **1,967 (+13)**: `hairline_pair` 1,891 → 1,906, `strip_seam_tear` 22 → 20 |

THE +13 IS NAMED (`census_rows_diff.py --family hairline_pair`: EXACT 1,891, MOVED 0, GONE 0, NEW 15): all 15 are
`hairline_pair groundside_pavement|groundside_pavement [groundside]`, |de| 0.053–0.184 m, between two late-stage gap pieces
(30.116143, 31.406766 0.184; 30.124567, 31.394510 0.123; 30.122245, 31.398578 0.123; 30.113345, 31.396436 0.122; …) — the §55
pieces re-cut against a base whose apron moved; 0 are airside (airside hairline 1,192 = 1,192). BAR "CRITICAL rows not rising":
MISSED by these 13 at HECA, met at KASE (44 = 44), KCLT (1,997 = 1,997), OTHH (identical body).

HECA feet, three arms (within 0.3 m / feet in r 60): identical to the J1 control at 8 of 11 rows; building147@30.1279552 108/112 →
99/103 (4 unfitted feet in both; the foot population in the radius changed), building29 44/60 → 45/60, building64 worst −4.39 → −4.28;
whole pad building147 806/859 → 887/941, building4 4,883/11,492 =. Not worse.

## 4f. Handover

Tests at the final code (`8179f4c2`; later commits are notes / frames only): full non-Qt split 8,842 passed, 19 skipped, 1 xpassed
(`-n 8`, 259 s); `-n0 tests/test_qt_*.py` 311 passed; the four gate files 200 passed; `tools/ratchets.py` DUPLICATE PASS, LAYER PASS;
size warnings on files this lane touched: `constraints/no_step.py` 1,128 lines (was 974: crossed 1,000 — the weld law itself is
the new `constraints/weld_floor.py`, 204 lines; what grew in `no_step` is `HoldPass.widened` / `.seal` and the record),
`tools/check_grade.py` 14,062, `tools/v2_solve_replay.py` 2,873, `constraints/platform.py` 1,204 (+1 here).
Frames registered (lane `pads64`, 9 rows): the four closing builds, the J1 control build, the J1 + main base arm (4).
NOT DONE: the scrap rule (4b: premise refuted, no code); a synthetic end-to-end twin of a misfit block through `solve_design`
(the unit twins + `HoldPass` twins + the KASE / HECA replays stand for it); the `--stage1-dump` read (superseded by `closers_*.txt`).

## 5. Next (for the master / the next lane)

The sweep; J2 (the bay plateau) — after it, re-read `scraps.py` at the OTHH site: the existing scrap rule should then take the
thin apron-bordered pieces. Arms run from the FROZEN tree `pads63j1` (`<scratch>/pads64/chain_j3.sh TAG SHA`); never replay in
an edited tree, and every probe script needs a `__main__` guard (the pool spawns).
