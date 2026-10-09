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
