# valley2 notes — implementing spec §61 (taxiway edge takes its centreline's level)

Lane `valley2`, branch `claude/valley2`, based on main `3a64a153`. Ruling 2026-10-09e.

## Step 0 — setup
- §61 was FREE on main (last section §60), so no renumbering: appended verbatim from
  `origin/claude/valleyspec` 51313c41 (297 lines).
- Brought `docs/briefs/valleyspec-{notes,summary}.md`, `valleyspec-scratch/`,
  `flatvalley-notes.md`, `flatvalley-scratch/` (design record, probe arms; no engine code).
- NOT brought: that branch's 14 `docs/frames.jsonl` rows (captures taken on older main
  `e2eec15c`; this lane re-takes controls on main).

## Step 1 — the foot (8b859526, 99f6cb38)
- `constraints/taxi_trend.taxi_xsec_feet(pm, law, report)`; `_face_extension`'s candidate walk and foot
  are factored into `_face_candidates` / `_feet` / `_faces_of_chain` and shared (the trend's extension is
  arithmetic-identical: main's KCLT body 0b1566de77d5 reproduces under the control tree, and the step-1/2
  tree's suite is green). Published by `with_taxi_trend` as `PlanarMap.taxi_xsec` `{v: (a, b, t)}`, an end
  that is a runway contact is `("pin", value)`.
- DEVIATION D1 (from §61 (8) step 1's letter "not in taxi_trend_z"): the feet are published for every
  off-centreline owned vertex and the solve skips the ones that carry a trend row AT ASSEMBLY. Reason:
  `constraints/eat.withdraw_trend_over_reach` runs AFTER the publisher, and §61 (7) row 10 says a
  withdrawn-trend EAT face "follows the (withdrawn-trend) centreline" — which is what the probe did (it
  read `taxi_trend_z` at assemble time). Publishing only the trend-less would leave such a vertex on the
  membrane. Report key `xsec_vertices` counts the trend-less ones.
- 1b: `PlanarMap.__setstate__` — a map pickled before a field existed reads the field's default. The
  frame twin `test_shape_parts` (gaps7/ARM2 `solved.pkl`) died in `dataclasses.replace` on the new field.

## Step 2 — law keys (d9d905bc)
- `[design] taxi_xsec = 1.0`, `free_membrane = 1.0` (both in `DESIGN_TERMS`), `qp_rel_tol = 1e-12`
  (checked in (0, 1)); `design_qp.solve_one_sided(rel_tol=...)`; `_REL_TOL` deleted. `_ROUNDS_MAX` 400 kept
  (the probe ran with 4000 — watch `round_cap` at HECA).
- v2 suite with steps 1+2 only (no rows): 2,781 passed, 1 failed (= the frame twin fixed in 1b).

## Step 3 — the rows
- New module `solve/design_edge.py` (`cross_section_rows`, `membrane_rows`); `rows._level_row_columns`
  (the per-column half of `_level_free_columns`, the probe's relative reading); assemble §5c' and §9d;
  `DesignReport.taxi_xsec_rows` / `free_membrane_rows` (summed over the stages, in `as_dict` and the line).
- The membrane is read for TAXI-FAMILY columns only (spec text). The probe read every unlevelled
  column; KCLT's census/avd numbers come out identical to the spec's ruled row either way (below).
- Twin `tests/auto_patch_v2/test_v2valley.py`: the rows exist and no taxi column is held by bending alone;
  a satisfied ceiling moves nothing (stub fixture); the law keys.
- TWO STANDING TWINS MOVED, attributed by intervention (`scratch twin_arms.py`, two-bench fixture, the
  240 m taxiway's climb against the ground's 3.00 m):
    main (no rows, 1e-9) 2.942 | tol only 2.942 | as shipped, fixture as is 2.215 (31 membrane rows) |
    membrane 0: 2.942 | feet only + membrane: 2.205 | feet only, membrane 0: 2.941 |
    pipeline order (with_taxi_trend): 3.077 (10 trend, 10 xsec, 0 membrane) | pipeline order, main rows: 3.078
  So the CROSS-SECTION row is inert on a centreline (2.942 -> 2.941; 3.078 -> 3.077); the MEMBRANE is a
  slope penalty wherever a CENTRELINE itself has no trend row — a fixture that skips the taxi publisher
  (both failing twins), and in a real build a chain with no fit (`chains_without`) or a DEM-degraded
  airport. FOUND, NOT FIXED (F1, for the spec author): §61 (1) names the membrane class as "foot past
  reach, or face no chain owns"; §61 (8) step 3 says "every taxi-family column still carrying no level
  row", which also takes a TREND-LESS CENTRELINE vertex. Built as step 3 says (= the probe).
  - `test_v2cyxy.two_benches` now runs in the pipeline's order (`_solve(..., taxi_trend=True)`), 11 pass.
  - `test_v2ground.test_the_zone_ring_follows_the_pavement_not_the_terrain`: the pinned staged-arm
    reading moved −2.88 -> −1.14 m (still under its DEM); bar `< -2.0` -> `< -1.0`, claim kept, noted in place.

## Step 4 — KCLT replay: THE SPEC'S RULED ROW REPRODUCES
One capture (`valley2/cap/KCLT.pkl`, main 3a64a153, 132 s), `--from classify`, `--workers 9`.
Control = pristine worktree `valley2ctl` @ 3a64a153 (body 0b1566de77d5 = main's sw7_KCLT); arm = this tree.

| | control | arm | spec "KCLT ruled" |
|---|---|---|---|
| rows | 2,727 trend | + 1,519 cross-section + 898 membrane | 1,519 |
| stage-1 movers > 0.02 / > 0.3 / worst | — | 1,827 / 383 / 1.492 | 1,827 / 384 / 1.49 |
| runway (avd) | — | 4 / 0.06 (stage-1 read 3 / 0.054) | 4 / 0.06 |
| avd strip / taxi / apron / other | — | 2,683 / 290 / 178 / 119 | 2,683 / 290 / 178 / 119 |
| adjudicated airside | 3,355 | 3,336 (−19) | 3,355 -> 3,336 |
| families | — | taxi_box +3, strip_transverse +2, road_cross_section +4, airside_no_step −2, transverse −3, strip_longitudinal +1, drainage_minimum −9, groundside_cutback +1, within_shape −431 | same |
| CRITICAL motion / visual | 5 / 1,974 | 5 / 1,973 (groundside_cutback visual 3 -> 2) | same |
| §5a LP pass 1b | 346 relaxed (gs 291, pad 4, taxi 51) | 346 (gs 290, pad 5, taxi 51) | taxi 51 -> 51 |
| stage-1 wall (single run, two other lanes building) | 48.2 s (1a 16.6) | 52.9 s (1a 17.9) | +15 s |
| stage-1 rounds | 305 | 444 | |
Largest cluster 933 at 35.22006, −80.93342 (`pav41`, +1.49); then 454 at 35.22166, −80.95104 (`pav125`, +0.97).

## Steps 5-7 (6ed7e45b, 75662364) + WIP after the outage
- Step 5: `tools/v2_solve_replay.py --null-change [N]` (helper `tools/replay_null.py`, INDEX row, `--json` key
  `null_change`, twin `tests/test_replay_null.py`). The line also says `LP SETS DIFFER a/b` when the §5a
  relaxed sets differ by identity.
- Step 6 code: `project._relax_lp(tie_rank=...)` + `feasibility.canonical_rank`. DEVIATION D2: the second
  LP is held on the first one's optimal face EXACTLY, by complementary slackness against its duals (rows
  with y < cost stay hard, rows with y > 0 become equalities), instead of a budget row
  `Σ cost·s ≤ opt + hard_tol_m`. Reason: §5a runs in DUAL form (n equality rows, m bounded columns), where
  this is the same model with other column bounds re-run from the first basis (KCLT 0.02 s); a budget row
  needs the primal form (HECA 32 s measured by the dual-form lane) and compares 0.02 against an optimum
  of ~1e7 with tier costs to 1e12. An answer costing more than the first LP's is refused and the first kept.
- Step 7 code: `DesignReport.settle_record()` -> `qp_exits` (round_cap first), `lag_settled`, `hard_settled`
  in `as_dict` (= the sidecar `design` block), `stages.stage1a` / `stage1` / `stage2`. Capped loops were
  already named lines + status FEASIBLE, never a failure — nothing to change there.
- KCLT, final config (k_null): `NULL-CHANGE pass1a 0/0/0.000 pass1b 0/0/0.019 stage2 0/0/0.019 (… promoted
  145=145, lp relaxed 0=0)`; adjudicated airside 3,355 -> 3,335; census hard_conflict 346 -> 343 (taxi 51 -> 50);
  the tie-break moved 0 airside nodes against the step-3 arm; avd identical to step 4.
- HECA FINDING: a one-shot `--replay --from classify` is NOT the build at HECA (body 96f3ab15ab08 vs main's
  75c751a9dd95): the build solves the gap-free base, then the late stage. HECA is therefore read as
  `--gap-free` base (+ `--null-change`) and the closing build; the control patch is main's `sw7_HECA.osm`.
- WIP committed here: `v2_why_solve` names a taxi edge "held by its centreline (t = …)" (§61 (7) row 12),
  the stage-1 dump keys `taxi_xsec` / `free_membrane` owners, the DEFERRED_VERIFICATION line.

## Step 6 at HECA — THE DIVERGENCE, ATTRIBUTED (f394c3ff)
HECA is read on the build's own path: `surf337/HECA.pkl --from classify --gap-free` (the base), `--null-change`.
| arm (one capture, base map) | NULL-CHANGE pass1a / pass1b / stage2 | rows |
|---|---|---|
| control, main 3a64a153 (+ the tool only) | 714/44/0.489 · 650/34/0.520 · 1128/74/0.520 (promoted 1440=1439) | — |
| branch, membrane on TAXI-FAMILY columns (§61 (8) step 3's words) | 3/0/0.043 · **65/4/0.391 MISS** · 91/4/0.391 | 1,160 xsec + 5,279 membrane |
| INTERVENTION: membrane on EVERY unlevelled column (the probe's `_membrane`) | 0/0/0.000 · 4/0/0.262 · 4/0/0.262 | 1,160 + 5,394 (all stages) |
| **SHIPPED: every unlevelled column of the AIRSIDE STAGE, the taxi family's elsewhere** | **0/0/0.000 · 4/0/0.262 · 4/0/0.262 MET** (promoted 1438=1438, lp relaxed 242=242, sets equal) | 1,160 + 5,369 = the spec's §61 (3) figures exactly |
The 4 movers are the spec's own spot (`gapapron:1`, 30.10294, 31.39591). DEVIATION D3: the spec's TEXT says
"taxi-family column", its PROBE (and every number the owner was shown) read every unlevelled stage-1 column;
only the probe's reading meets the ruled bar. The ~90 rows between are an apron piece no datum levels
(`gapapron:1`). Built as the probe; the single solve and stage 2 keep the taxi-family reading so the groundside
takes no membrane. For the spec author's review.
- Tie-break LP: HECA pass 1b 547,172 rows, LP 6.4-7.1 s of which the tie-break 0.11-0.13 s ("canonical");
  pad tier 17 -> 14 (the spec's 17 -> 14), taxi 63 / 61 = control's 63 / 61.
- Cost vs control (base, stage-1 roles): 3,718 movers / 377 > 0.3 / worst 0.981 (spec 3,739 / 367 / 0.98);
  junction 1,658, apron 1,614, strip 1,519; runway 2 / 0.053. Largest cluster 3,428 near 30.12136, 31.42359.
- Stage records: pass 1a qp_exits {no_descent 1, optimal 2}; pass 1b {no_descent 2, optimal 1}, hard NOT
  SETTLED (43 rows, worst 0.1007 m — the SAME 43 / 0.1007 as main); stage 2 lag NOT SETTLED (as main). No round_cap.
- THE PLANAR READ (30.10901, 31.40396; `scratch planar_read.py` on the base maps): v18218 is a corner of
  junction face `dsf:objpav112#2` and of strip face `adjacent_ground:taxi:E:zone1#45`; the apron face `route21`
  runs its edge v17607-v17403 0.976 m away and does NOT share the vertex — a ~1 m sliver of graded strip
  lies between them. A REAL unshared boundary, not a missed weld (no bending row can tie them). The junction
  corner moved 104.421 -> 104.345 (−0.08 m); the step to the apron edge was already −0.443 m on main and is
  −0.519 m now, which crosses the census bar. §39's sliver class: exposed, not minted.

## Step 8 — the closing build `valley2_HECA` (c1450faf; registered frame valley2/valley2_HECA.osm)
rc 0, 561.4 s (single background run; partition cache MISS 47.6 s vs 2.8; solve 209.4 -> 255.6 s; late 107.4 -> 121.0).
Body 79abb3762e38 (main sw7 75c751a9dd95). Against `sw7_HECA.osm`, each tree's own census:
- runway 2 / 0.06 m; strip 2,866 / 0.99; taxi 1,234 / 0.77; apron 843 / 0.43; other 875 / 0.24.
- adjudicated airside 12,205 -> 12,176 (−29). Rising: transverse +7, taxi_box +4, road_cross_section +4,
  pavement_over_road_cap +3, groundside_cutback +2, hard_conflict +2 (294 -> 296; taxi tier 63/61 = 63/61).
  Falling: airside_no_step −15, strip_transverse −13, pad_frontage_hold −1, within_shape −252.
- CRITICAL motion 2 -> 3 (`vertex_to_edge_step` +1, the site above); visual 1,912 -> 1,915 (strip_seam_tear +1,
  hairline_pair +2). The spec disclosed +1 / +1; hairline_pair +2 is new. THE "CRITICAL NOT RISING" BAR IS MISSED AT HECA.
- Tests: non-Qt 9,053 passed / 1 failed -> fixed (c1450faf), the failed file + named four re-run green; Qt 311 passed.
- ratchets PASS; `solve/project.py` 1,022 lines (crossed 1,000 with `_tie_break`), `tools/v2_solve_replay.py` 2,940.
