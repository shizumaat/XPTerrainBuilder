# roadramp2 — lane notes (issue #484, PR #487 follow-up; RULINGS 2026-10-09d (2))

Branch `claude/roadramp2`, from `claude/roadramp484` @ `2676e011` + `origin/main` @ `729e140d`
+ `claude/rampreview` @ `baf03e31` (docs only). Scratch `<scratch>/roadramp2/`.

## Step 1 — setup, spec to one copy (F3b)

* Merged main (one conflict, `docs/frames.jsonl`, append-only: union of both sides) and the
  review branch (spec + `docs/briefs/rampreview-summary.md`).
* F3b: the stale second copy of §38–§41 (with §37 (6)–(9)), 1,634 lines from the review's
  HTML marker to before `## §42`, DELETED. `grep -c '^## §38 THE TILE SEAM'` = 1; the surviving
  copy carries "AIRSIDE IS KING — ROUND 2". The deleted copy was the round-1 snapshot (its
  "AIRSIDE MOTION — REPORTED" block and `v2roadcontactHECA2` closing build are superseded by
  round 2 in the canonical copy). No other file referenced the second copy by line.

## Step 2 — F1 / F2 / F3 + the 09d (2) gate, twinned (no solve yet)

Code (`airport/road_descent.py`, `constraints/road_ramp.py`, `solve/design_report.py`):

* F1 `envelope(…, floors=)`: a label at or under its floor propagates nothing (seeds excepted).
  The per-contact walk (`_run`) ends the same way; the report counts a vertex as on a ramp
  from `STAND_M` = 0.02 m over its floor (was 1e-9).
* F2 `_run`: one shortest-path tree per contact, walked at the design grade to first meet; an
  END the cone arrives over (road's own end / next contact, >= a lane width) steepens ONLY the
  hops of the walk to it (`steep`), the contact's other runs keep the design grade.
  DEVIATION from the review's wording ("the envelope is the max" of the design cone and the
  branch): a branch at a steeper grade is UNDER the contact's own design cone everywhere, so a
  max would be a no-op; the run's hops REPLACE the design grade on that path. Ramp record:
  `grade` = its gentlest run, `steepest` = its steepest.
* 09d (2) `_forced`: a contact the road can leave ON ITS FLOOR inside its cap (its descent at
  the cap, ended at first meet, stands < 0.02 m over every floor) builds NO ramp. This is the
  owner's answer to the review's Q1 (reading B); the review left the mechanism to the
  implementer.
* 09d (2) `_hop`: past the contact's first hop a ramp never stands HIGHER over its floor than
  at the previous vertex — where the floor falls faster than the grade the ramp follows the
  fall (at the cap at most) instead of opening a growing embankment. ADDED BY THIS LANE (not in
  the review's list): without it KCLT mouth 20948 (5 cm of need) built a 51 m ramp 1.17 m high.
* F3 `terrace_profile`: the coverage-join clip is `clip(target, z_a ± cap·d)` again; the
  per-anchor `reach` grade and the `max_join_grade` report key are gone; the design-report line
  reads "reaching a coverage join at the cap" as on main.

Twins (each fails on `2676e011`'s module, passes now — checked by swapping the module in):
`test_road_descent.py`: `test_a_cone_that_met_its_floor_does_not_re_emerge_over_a_later_fall`
(F1), `test_a_stub_end_steepens_its_own_run_only` (F2),
`test_a_road_that_can_follow_its_floor_from_the_contact_has_no_ramp` and
`test_a_ramp_never_stands_higher_over_its_floor_than_where_it_left` (09d (2));
`test_roadterrace100.py`: `test_the_coverage_join_clip_is_the_cap_s_envelope_never_a_design_grade_cut` (F3);
`test_v2roadramp.py`: `test_a_fall_beyond_the_first_meet_is_the_floor_s_not_a_ramp`.

DEVIATION — the `_Shelf` fixture. The review says first meet leaves `_Shelf` unchanged ("its
cone meets once, at 12 / design"). It does not: the fixture's road runs 20 m on the plateau
before the 30 % fall, so the cone meets the floor at the mouth and under F1 the fall is the
floor's own (the clamp, at the cap) — no ramp at all. The fixture is re-founded on what its
docstring always said ("an apron on fill"): the ground drops at the apron's edge. The old
shape is kept as `_LateShelf` with the twin above. FOUND, NOT FIXED (owner intent): a fall
steeper than the cap BEYOND the first meet is descended by the core clamp at the CAP (10 %),
not at the 5 % design grade — review R3 (b) rules the clamp correct as is.

KCLT, registered capture `roadramp484/KCLT.pkl`, no solve (`<frames>/roadramp2/probe.py`,
`probe_KCLT.txt`):

| | ramps >= lane | length | longest | max reach | every run at the cap |
|---|---|---|---|---|---|
| main (10 %) | 24 | 231 m | 24 m | 540 m | 24 |
| `2676e011` | 55 | 1,264 m | 148 m | 594 m | 14 |
| now | 38 | 598 m | 103 m | 103 m | 2 |

Targets `2676e011` -> now: lowered 103 (worst 1.04 m), raised 55 (worst 0.67 m — F2: runs that
were at the cap for a stub are at 5 % again). Main -> now: raised 170 (max 1.22 m), lowered 2
(0.02 m). The review's F1-only figures (49 / 755 m / 109 m) are not reproduced separately:
this tree carries F2 and the gate as well (the 109 m ramp, mouth 13154, is 103 m now).
THE FOLLOWABLE-GROUND CHECK: one descent per mouth at the CAP ended at first meet; a contact is
FORCED when it still stands >= 0.02 m over a road floor. Mouths 858, forced 114; ramps whose
contact is not forced: **0** of 38. 14 ramps have a run steeper than design, 9 a run at the cap
(stub ends 4–8 m away), 2 are at the cap on every run.

## Step 3 — KCLT replay pair, closing build, suites

Replay pair on the registered capture `roadramp484/KCLT.pkl` (`--from constraints --emit
--verify --workers 3`): arm A = the main-tree replay (body `0b1566de77d5` = main `sw7_KCLT`),
arm B = this tree @ `ca6b2e54`, body `c558693ad8bd`, solve optimal, verify DEFECT families all
zero. `airside_value_delta --tol 0.02` + each tree's own `census.py` (`<frames>/roadramp2/
analyze_KCLT.txt`, `avd_KCLT.txt`):

| | main (A) | `2676e011` | now (B) |
|---|---|---|---|
| ramps >= a lane width / length / longest | 24 / 231 m / 24 m | 55 / 1,264 m / 148 m | 38 / 598 m / 103 m |
| max reach | 540 m | 594 m | 103 m |
| `road_cross_section` (worst) | 767 (2.23) | 800 (2.29) | **765 (2.23)** |
| CRITICAL motion / visual | 5 / 1,974 | 5 / — | 5 / 1,974 |
| adjudicated airside | 3,355 | — | 3,355 |
| `pavement_over_road_cap` (worst) | 18 (4.47) | 17 (3.18) | 17 (3.18) |
| solve-owned (runway, taxi, apron) movers > 0.02 m | — | 0 | **0** |
| service_road refs / nodes moved, worst | — | 55 / 306, 1.04 m | 45 / 255, 0.91 m |
| `dsf:pol48` | — | kerb down 0.6–0.8 m | 15 / 74 nodes, worst 0.08 m |
| tunnel_ramp nodes > 0.02 m, worst | — | 7, 0.13 m | 5, 0.13 m |

Row-side receivers: 68 nodes, worst 0.45 m (`adjacent_ground:taxi:F:zone2#156`, a graded strip
welded to a moved road), buildings 52 nodes <= 0.06 m, groundside pavement 71 nodes <= 0.18 m.
`small_roads:-7031#7/#8` no longer move; `-7031#1` moves 0.84 m (3 of 7 nodes, a 5 % ramp).
NOT RE-READ: that the 0.13 m tunnel_ramp node is the review's −16259 (same ring count and worst
value as the review's accepted band non-uniqueness; the node id was not re-joined here).

Closing build `roadramp2_KCLT` (harness, @ `ca6b2e54`): rc 0, optimal, 370.5 s single run, body
`c558693ad8bd` — byte-equal to replay arm B. Frame registered (`frames.py list KCLT`, lane
roadramp2, copied to `<frames>/roadramp2/`). The ARTIFACT LEDGER REFUSED the store (key
`8d0e1ad5865e`): I edited the spec while the build ran, so the dirty flag moved. Code tree
unchanged; the body equals the replay's. No second build was run.

Suites @ this tree: non-Qt `-n 4` 9,059 passed / 20 skipped / 1 xpassed
(`test_v2othhdet::test_read_wall_corridors_is_input_order_free`, not this lane's); Qt `-n0`
311 passed; console_encoding + windows_text_io + v1_retired + no_airport_specific_code 202
passed. `tools/ratchets.py`: DUPLICATE RATCHET PASS, LAYER RATCHET PASS; size warning on a
touched-package file: `airport/road_ramp.py` 1,434 -> 1,527 (+93, all from `2676e011`; this
lane did not edit it). Net lines this lane (src + tests, since the merges): +330 / −106; spec
−1,343 net (the stale copy). New public symbol: `road_descent.STAND_M`; `envelope` gained
`floors=`; ramp records gained `steepest`; report key `max_join_grade` removed.

NOT DONE: HECA / the other five airports not replayed or built (the brief's closing test is
KCLT; the review asked for HECA after F1–F3 — the master's sweep); the F1-only figures
(49 / 755 m) not reproduced in isolation; the lot-step follow-up R5 (`gap:8/s0/lot`) and the
strip follow-up F5 untouched; the probe (`<frames>/roadramp2/probe.py`) is a third use of the
`ramp_probe` pattern and is NOT promoted into `tools/` (owed: a `v2_solve_replay --ramp-probe`
or an INDEX row).
