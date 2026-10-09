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
