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

## HECA — body CHANGED `75c751a9dd95` -> `189234d8e929`; runway / taxi / apron 0 movers

* `sw9_HECA`: rc 0, optimal, ledger STORED `8e01c7070064`. Rebake plan sha IDENTICAL to main's
  (`1956d7537290`, `T3_road.obj` `deck_datum_z` 98.445 in both).
* Ramps (build log; probe on `surf337/HECA.pkl` gives the same 1,134 contacts / 460 on-ramp vertices / 38 /
  593 m / 57 m — the capture carries 4,108 targets against the build's 3,984, a stale-capture difference
  that does not reach the ramp figures): **38 ramps, 593 m, longest 57 m (mouth 11888, 5 %), max reach
  77.5 m** (main at 10 %: 25 / 201 m / 27 m / reach 858 m; `2676e011`: 44 / 753 m / reach 932 m). 34 at the
  design grade, 1 steepened under the cap, **3 at the cap on every run** (mouths 25585, 12878, 10160 — "the
  road's end at 6–8 m"; the cap does not bring them down), 4 with some run at the cap (adds 11883, 46 m at
  5 % with one run at 10 % to a road's end 8 m away). Probe targets main -> now: 109 raised > 0.02 m (max
  0.74 m, 19 > 0.3 m), 0 lowered.
* Followable-ground check (bar 0): mouths 1,134, forced 93, ramps on followable ground **0** of 38.
* Movers > 0.02 m vs `sw7_HECA` (canonical join, 42,591 = 42,591 nodes): row-side **0** of 28,054,
  solve-owned (runway, taxi, apron) **0** of 17,422. By role: `service_road` 9 refs / 50 nodes, worst
  0.56 m (`small_roads:-4036` 6/10 at 30.13926320, 31.41026154, 64.01 -> 64.57; `dsf:objpav104` 20/141
  0.49 m; `dsf:objpav366` 10/383 0.48 m; `small_roads:-3890#1` 5/22 0.48 m); `groundside_pavement` 3 nodes
  (`gap:8/s0/lot` 2/88: −2.37 m at 30.11510995356, 31.41089017767, 104.17 -> 101.80, and +0.06 m;
  `gap:0/s0/lot` 1/1,945 at 0.03 m, a node shared with `small_roads:-21141`); `tunnel_ramp` 5/108 nodes at
  +0.02 m (154.35 -> 154.37, the ring at 30.0861, 31.4065 welded to `mouth_road:-1744`).
  The `gap:8/s0/lot` node is the SAME node the roadramp484 notes and review R5 name (a lot part whose
  rows are infeasible against its rim relaxes at an arbitrary rim vertex): it reads 101.80 here, 104.17
  on main `sw7`. FOUND, NOT FIXED, not this PR's mechanism (R5 follow-up).
* OWNER GAP SITES: `gap:7/lot` (#430) 90 nodes, `gap:7/ramp0` (#292) 48, `gap:0/s4/lot` (#358) 160 —
  **0 nodes moved** over 0.005 m. T3 LANDING: 0 of 653 nodes within 150 m of the `T3_road.obj` ring centre
  (30.1123889, 31.3962650) moved > 0.02 m; deck datum identical.
* Census, each arm under its own tree (main -> branch): rows 56,316 -> 56,330; `road_cross_section`
  512 -> **515** (worst 2.76 = 2.76); `pavement_over_road_cap` 15 -> 16 (4.77); `hard_conflict` 294 -> 297
  (airside 90 = 90); `transverse` 947 -> 954 (airside 352 = 352); `mid_edge_step` 54 -> 52; `within_shape`
  45,675 -> 45,677 (airside 44,889 = 44,889); CRITICAL motion 2 = 2, visual 1,912 -> 1,910; adjudicated
  airside 12,205 = 12,205; airside rows 53,387 = 53,387.

## OTHH — body UNCHANGED `500f5dddce63` (= `surf337b_OTHH`)

* `sw9_OTHH`: rc 0, optimal, ledger STORED `14692649a9b4`. Node-for-node identical (35,095 nodes, 0 over
  0.0001 m) — so the object-framed ramps (#447 / #448 / #453 / #454 / #455 sites) and every tunnel ramp
  are node-identical to main; nothing moved.
* Ramps (build log): 1,777 groundside-road vertices from 1,602 contacts, all 1,777 targets on the DEM,
  **0 ramps** — the followable-ground check is 0 of 0.
