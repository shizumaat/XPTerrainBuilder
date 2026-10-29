# Lane `llfpgcut` handoff — LFPG cuts and tunnels (RULINGS 2026-10-28k; spec PR #1559)

Paused 2026-10-27T17:43Z on the owner's shutdown order. Branch
`claude/llfpgcut-cuts-tunnels` (code commit a9baa6d30 + this WIP commit).
Step 1 is done: the spec branch `claude/llfpgspec-cuts-tunnels` was pushed at
5ce3bb561 with R1–R7 and §7 revised to the rulings. The spec's new §10 "As
built" (on this branch) lists what was built and the deviation the master
must rule on.

## State

- DONE (code, twins green). R1: the cover reading; 231 b applied under
  airside pavement or a hard-deck object; 232 a's no-sign refusal and its
  5 m keep elsewhere; the kept "survey carries" refusal.
  `Tunnel.depth_m` = DEM(cap) − floor, which stops the constraint
  overriding the 27g blend with cap − 7.5. R4: the design grade follows the
  surveyed road. R5: rail law keys `rail_ramp_grade` 0.0125 and
  `rail_ramp_max_grade` 0.035 (EU TSI INF). R2: the kept-mouth trench
  keepout.
  Files: `planar/lidar_road.py` (rewritten), `planar/structures.py`,
  `planar/unframed_ramp.py` (design/cap kwargs), `planar/structure_stats.py`,
  `law/structures.toml`, `law/model.py`,
  `tests/auto_patch_v2/test_tunnel_ramps_ltramp.py` (13 twins).
- GATES. `tests/auto_patch_v2` and the registry/closure twins ran once at
  an earlier state: 4342 passed, 1 failed
  (`test_constraints::test_cyxy_verify_matches_v1_census`). At CYXY,
  `tunnel:-725` is now kept, and the strip zone took its approach. The
  trench keepout fixes it: that test and the ltramp twins pass again. THE
  FULL SUITE HAS NOT BEEN RE-RUN ON a9baa6d30, and `tools/ratchets.py`
  passed only at an earlier state (re-run it).
- NO PR OPENED, because the gates have not been re-run.
- NOT BUILT: R3 (227 a, which is #1138's trench under a hard deck), R6
  (228 a), R7 (229 b). The reasons are in spec §10.

## Measured

Lane instrument: the emitted patch rasterised on a 2 m grid. Depth = the
75th percentile of the ground 25–60 m out, minus the lowest point within
12 m. 224 portals lie in the hand patch's cover. Script:
`/private/tmp/claude-501/llfpgcut/score.py` (scratch, not promoted).

| arm (replay `--from planar --emit` of the capture below) | match | too deep | too shallow | missing (filled) | missing | extra (on survey cut) | extra | none |
|---|---|---|---|---|---|---|---|---|
| base origin/main 6f90dd6a8 (= the owner's 1.0.436 patch, same counts) | 55 | 41 | 46 | 5 | 8 | 12 | 16 | 41 |
| arm5 (R1 + deck objects as pavement + trench keepout, before the final trench bound) | 75 | 11 | 53 | 6 | 10 | 12 | 7 | 50 |

"Too shallow" means the owner's cut is deeper than ours. In at least 41 of
these, our depth matches the survey and the owner's is deeper (the T1
roads: owner 9 m, survey 6.4–7.1 under groundside cover; the LGV). That is
the residual 231 b leaves wherever no pavement or deck stands over the
bore.

Closing build on the branch (a9baa6d30): `build_airport.py LFPG`, rc 0,
24 min. Its patch is saved at
`/private/tmp/claude-501/llfpgcut/build/LFPG_20261027T102505_2.osm`
(harness copy `/tmp/harness/LFPG_20261027T102505_2.osm`). The harness
flagged the run CONTAMINATED: 4 unauthorised shared-repo paths. The
external deltas it names are ELLX caches, which points to the owner's
concurrent app builds, not this lane. The run was not stored in the
artifact ledger. It is NOT YET SCORED and NO CENSUS HAS BEEN RUN. The
matched control (`build_airport.py LFPG --base-arm` in worktree
`llfpgcutbase`) was STOPPED by the pause before it finished.

Dry structure A/B (planar re-run per capture, base vs branch; detail in
`/private/tmp/claude-501/llfpgcut/ab/summary.txt`), tunnels built:

- LFPG 55 → 25.
- KATL 9 → 5.
- KCLT 8 → 2. The #807 site `tunnel:-31625` is now KEPT: the survey reads
  its road 11 m under its cover.
- EGGW 17 → 2.
- EGLL 15 → 11, with 11 floors raised.
- KBUF 11 → 9.
- NZWN 10 → 5. `tunnel:-2743@0` is new, at -41.33027, 174.81290, about
  120 m from the owner's #1337 sites.
- CYXY 2 → 0 (kept).

These are large changes. The master should read them before landing.

## Exact next step

1. Run the gate suites from
   `/Users/noah/XPTerrainBuilder/.claude/worktrees/llfpgcut/Ortho4XP`:
   `tests/auto_patch_v2`, `tests/test_console_encoding.py`,
   `tests/test_no_airport_specific_code.py`, `tests/test_patch_code_closure.py`,
   `tests/test_patch_env_classification.py`, `tests/test_tile_failures.py`,
   `tests/test_step_code_closure.py`, `tests/test_v1_retired.py`,
   `tests/test_windows_text_io.py` (`-n 8`). Then run `tools/ratchets.py`
   from the repo root.
2. Build the control in `llfpgcutbase` (origin/main 6f90dd6a8):
   `tools/harness/build_airport.py LFPG --base-arm`.
3. Score the control patch against the branch build's patch (above) with
   `score.py --auto base=... --auto arm=...` run with `-I`. Rebuild the arm
   if the contamination matters. Then run `tools/harness/census.py` on
   both.
4. Once green, open the PR with the body lines the brief gives, and report.

## Captures and frames

- LFPG capture at origin/main 6f90dd6a8:
  `/private/tmp/claude-501/llfpgcut/base/LFPG.pkl`. It is NOT registered.
  It sits in /private/tmp and may not survive the shutdown; a re-capture
  takes 9 min.
- Base solved pickle for `--why-from`:
  `/private/tmp/claude-501/llfpgcut/base/solved.pkl` (also in /private/tmp).
- A/B captures used (all registered): lpackcut KATL_r3, EGGW, EGLL, KBUF;
  lramp2 KCLT; lramp NZWN; m1 CYXY.

## Cloud container?

Step 1 (code and twins only): yes. Steps 2–3: NO. They need this Mac's
corpus and the owner's hand patch in Dropbox.
