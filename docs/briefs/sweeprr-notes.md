# sweeprr — seven-airport sweep of PR #487 head `824680bb` (`claude/roadramp2`), issue #484

MEASUREMENT lane, no engine edits. Branch `claude/sweeprr` from `origin/claude/roadramp2` @ `824680bb`
(code tree `fd3158bac7ba`). Builds through `tools/harness/build_airport.py ICAO --tag sw9_<ICAO>`, one at a
time (lanes `pads67` / `valley2` building concurrently — wall times are NOT evidence). Reference = main
`0b3084f2` code: `/tmp/harness/sw7_<ICAO>` (OTHH `surf337b_OTHH`). Each arm censused by ITS OWN tree's
`harness/census.py` (reference: the main tree `/Users/noah/XPTerrainBuilder/Ortho4XP` @ `3a64a153`, src/tools
identical to `0b3084f2`; branch: this worktree). Movers: `airside_value_delta --tol 0.02 --by-ref`.
Ramps / followable-ground check: the roadramp2 lane's probe (`<frames>/roadramp2/probe.py`, read-only,
`PYTHONDONTWRITEBYTECODE=1`) on a registered capture. Scratch `<scratch>/sweeprr/` (`analyze.py` = the
roadramp2 lane's `analyze.py` re-pointed at the harness patches; build logs `build_<ICAO>.log`).

## CYXY — body UNCHANGED `cf8e9e89ec62` (= sw7)

* `sw9_CYXY`: rc 0, solve optimal, artifact ledger STORED `5fe84cb008e5`.
* Ramps (build log = probe on `gapapron3/CYXY.pkl`): 1 ramp of a lane width or more, 8 m, longest 8 m, max
  reach 14.7 m (main: 13 m, reach 113.5 m); 0 on every run at the cap (1 has a run at the cap: mouth 1946,
  "the road's end at 5 m"). Targets main -> now: 0 raised / 0 lowered > 0.02 m — hence the identical body.
* Followable-ground check (bar 0): mouths 123, forced 2, ramps on followable ground **0** of 1.
* Census (main tree's on sw7 = branch's on sw9): rows 1,367, `road_cross_section` 18 (0.69), CRITICAL motion
  0 / visual 52, adjudicated airside 254. Movers: none (byte-identical).

## SPJC — body UNCHANGED `61f66f149737` (= sw7)

* `sw9_SPJC`: rc 0, optimal, ledger STORED `224ca1090f25`.
* Ramps (build log = probe on a fresh capture at this tree, `<scratch>/sweeprr/cap/SPJC.pkl`): 1 ramp, 8 m,
  longest 8 m, max reach 44.6 m (main 58.8 m); 1 at the cap on every run (mouth 1448, "the next contact at
  4 m" — the cap does not bring it down). Targets main -> now: 0 > 0.02 m.
* Followable-ground check: mouths 372, forced 3, ramps on followable ground **0** of 1.
* Census (identical both trees): rows 3,630, `road_cross_section` 52 (1.73), `pavement_over_road_cap` 4,
  CRITICAL motion 0 / visual 507, adjudicated airside 891. Movers: none.

## KASE — body CHANGED `f9b157158a39` -> `c2200384ee0d` by ONE node, 0.01 m

* `sw9_KASE`: rc 0, optimal, ledger STORED `12d3adcaa8e8`.
* The whole difference (canonical join, 1,813 = 1,813 nodes, none added/removed): node −1813 at
  39.21671160560, −106.86376495647, `small_roads:-673` [service_road], 2377.59 -> 2377.60 m (+0.010).
  Movers > 0.02 m: **0** in every role (runway / taxi / apron 0; row-side 0 of 1,653; solve-owned 0 of 1,287).
* Ramps (build log = probe on `conc333/KASE_main28500ecf.pkl`; same 98 contacts / 47 targets as the build):
  1 ramp, 6 m, longest 6 m, max reach 6.4 m, at the 5 % design grade, 0 at the cap (mouth 1379; main built
  it at 10 %, under a lane width, so main counts 0). Probe targets main -> now: 0 > 0.02 m.
* Followable-ground check: mouths 98, forced 1, ramps on followable ground **0** of 1.
* Census (identical both trees): rows 4,903, `road_cross_section` 14 (0.70), CRITICAL motion 1 / visual 45,
  adjudicated airside 2,654.

## NLWF — body UNCHANGED `45ec40e74dcb` (= sw7)

* `sw9_NLWF`: rc 0, optimal, ledger STORED `847fd3c0e35a`.
* Ramps (build log = probe on a fresh capture `<scratch>/sweeprr/cap/NLWF.pkl`): 1 ramp, 23 m, longest 23 m,
  max reach 23.2 m (main 57.5 m), steepened under the cap (9.84 %, mouth 387, "the next contact at 8 m"), 0
  at the cap. Probe targets main -> now: 1 lowered by 0.02 m (not over the emit quantum: body identical).
* Followable-ground check: mouths 112, forced 1, ramps on followable ground **0** of 1.
* Census (identical both trees): rows 75, `road_cross_section` 24 (0.89), CRITICAL motion 0 / visual 23,
  adjudicated airside 3. Movers: none.
* INSTRUMENT NOTE: the registered capture `conc333/NLWF_main28500ecf.pkl` does NOT reproduce this build
  (probe on it: 5 ramps / 71 m); the fresh capture does (94 targets, 112 contacts, 1 ramp / 23 m).
