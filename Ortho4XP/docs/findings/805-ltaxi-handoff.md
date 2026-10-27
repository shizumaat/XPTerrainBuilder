# Lane ltaxi handoff: #805 / #883 / #517 (paused 2026-10-27, owner order)

Branch `claude/ltaxi-805` (PR #1499, still titled for round 1; its body does not yet say "Fixes #805").

## Done
- **#805 round 1** (16d (1)): wrap recognition by shape, beyond the RSA. The RSA bound is now law under RULINGS 2026-10-27x and is cited in `eat.py`.
- **#805 round 2** (RULINGS 2026-10-27w): on credible lidar a recognised rect is pinned when the survey along the crossing route breaks the taxiway longitudinal cap.
  - Code: `eat._route_grade`, `eat._lidar_overruled`.
  - Twin: `test_lidar_breaking_the_taxiway_law_along_the_route_is_no_witness`.
  - KCLT taxiway T has a route grade of 2.42 %, so it is pinned at 217.31.
- **#883** (RULINGS 2026-10-27y): `check_grade.DeclaredWallSteps` now reads `gap: true` joints the same way it reads walls. Twin: `test_a_declared_gap_step_is_forgiven_like_a_wall`.
  - The KBOI census is unchanged at 105, because the kept-step strip pairs do not cross the declared joint. Details are in `taxiways-ltaxi.md`, "Round 2 results".
- **#517 round 2**: measured and not shipped. Every variant that removes the climb adds 111–140 `within_shape` rows. The diff is in the scratchpad (path in `taxiways-ltaxi.md`). Two-round cap reached.
- Tests run on commit ca9f11843: `test_v2eat`, `test_mouth_census`, the strip-seam tests, `test_harness`, the census tests, the registry twins and the closure twins all pass (1143 passed). `ratchets.py` passes.

## Exact next step
1. Run the census on the closing build, then diff it against the replay control:
   - closing build: `/Users/noah/XPTerrainBuilderData/.harness/frames/ltaxi/ltaxi805b_KCLT.osm` (body be9828f5b1dc, solve optimal, built from ca9f11843);
   - command: `venv/bin/python tools/harness/census.py <that>.osm --rows-json …`;
   - control: the round-1 build, adjudicated 4,929 (frame `ltaxi/ltaxi805_KCLT.osm`).

   Expected from the replay: `eat_ceiling` 4 → 0, and +123 `within_shape` airside rows at 35.2294, −80.953.
2. The master decides the within-shape collision (next section). Only then should the PR body be set to "Fixes #805". Bars met: T ≤ 217.31, road level unchanged, nothing new at T's edge. Bar not met: +123 new adjudicated rows on the EAT's approach connector.
3. Update the PR #1499 body with the round-2 numbers.

## Open questions (for the master)
- **The EAT depth against the one-shape direct-pair cap.** The 123 rows pair `pav11` cross_connector / stub with the 18C runway-end region 430–450 m away, at 1.9–2.0 % against 1.5 % (8.66 m drop). An EAT nearer than depth / 0.015 (about 590 m here) cannot satisfy the direct-pair reading inside one source polygon. Should those pairs be exempted, or read along the route?
- **#883:** should the gap joint's declaration run along the pad corner, where the strip carries the step (`planar.shapes._gap_joints`)? Without that, the 4 ground rows stay.

## Measurement sources (all scratchpad unless noted)
- KCLT replays:
  - control: `kclt_ctl_z.npy`, `kcltctl_emit/`;
  - arm: `kclt_27w_z.npy`, `kclt27w_emit/`, `kclt27w_solved.pkl`;
  - census json: `c_kcltctl_emit.json`, `c_kclt27w_emit.json`.
- Captures (registered): `/Users/noah/XPTerrainBuilderData/.harness/frames/ltaxi/{SPJC,KBOI,KCLT}.pkl`.
- Scratchpad: `/private/tmp/claude-501/-Users-noah-XPTerrainBuilder--claude-worktrees-elegant-wilson-8530db/06e49073-fa34-4d4e-b09b-e8641564046f/scratchpad/ltaxi/`
