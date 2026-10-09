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

OTHH census (each arm under its own tree, identical): rows 2,562, `road_cross_section` 3 (0.15),
`pavement_over_road_cap` 1, CRITICAL motion 0 / visual 2,062, adjudicated airside 493.

## KCLT — the three items the implementer left open (replay / patch reads only; no build)

Instrument: `v2_solve_replay --replay roadramp484/KCLT.pkl --from constraints --emit --solved-out` on this
tree (body `c558693ad8bd` = `roadramp2_KCLT`), then `--why-from … --why-at / --why-vertex` per node
(`<scratch>/sweeprr/kclt/why_*.txt`). Patch node −N is solve vertex v(N−1).

(a) THE 5 `tunnel_ramp` NODES > 0.02 m (`sw7_KCLT` -> `roadramp2_KCLT`, way ref `tunnel_ramp`):

| node | lat, lon | main -> branch | way | the only binding row on it |
|---|---|---|---|---|
| −16259 (v16258) | 35.20105481483, −80.94033935031 | 208.14 -> 208.01 (−0.13) | −10843 | `structures FLAT group 2 tunnel_ramp laterally flat (road_cross_section 0 %)`, dual 0.00 — "no terminal reached, the objective holds it" |
| −16252 (v16251) | 35.20105482035, −80.94041621906 | 208.14 -> 208.01 (−0.13) | −10843 | the same FLAT row (its cross-section partner is −16259), dual 0.00 — the objective holds it |
| −16230 (v16229) | 35.20274485833, −80.94042153054 | 210.03 -> 210.01 (−0.02) | −10841 | FLAT group 2 lateral row, dual 0.00 — the objective holds it |
| −16219 (v16218) | 35.20273583092, −80.94022935566 | 210.03 -> 210.01 (−0.02) | −10841 | FLAT group 2 lateral row (partner −16230), dual 0.00 — the objective holds it |
| −16120 (v16119) | 35.22699148745, −80.94620242601 | 219.74 -> 219.77 (+0.03) | −10835 | `structures OFFSET >= 0.000 -> v16101` (tunnel.ramp monotone profile, spec §34 (3)), dual 0.18; chain v16119 -> v16101 -> v16100 (cap 4.82 % x 11.0 m) -> v16099 (FLAT) -> PIN v16131 `tunnel.crest = dem` (`tunnel:-11194@0`), 4 hops |

So −16259 is confirmed BY JOIN as the review's node (the implementer's "NOT RE-READ"). Four of the five are
two lateral pairs at ramp ends that NO hard row holds in level (one zero-dual lateral-flat row each): their
level is the objective's, and it follows the welded road's new target. The fifth sits on its ramp's
monotone-profile row. None is held by a road-ramp row; all five stay inside the tunnel-ramp law.

(b) THE TWO `[KCLT] road ramps built` LINES (38 / 598 m, then 14 / 344 m) are in the REPLAY log only
(`<scratch>/roadramp2/B/KCLT/log.txt`); the harness build log has one. Both come from ONE print,
`tools/v2_solve_replay.py:2154` inside `replay_problem._targets`, which runs twice: (1) on the FULL map
(the line `pipeline/build.py:1058` also prints — 38 ramps), (2) inside `_ribbon_free`
(`v2_solve_replay.py:~2227`, `shape_stage(_targets(…pm0…))`) on the RIBBON-FREE stage-1 map of #100 (c) —
14 ramps / 344 m, fewer because the map has no ribbon cells. The build makes the same second call at
`pipeline/build.py:1126` (`with_road_ramp(pm0, law, ap0, {}, …)`) with a throw-away report and prints
nothing. Not a double application: two maps, one call each.

(c) ARTIFACT LEDGER. The harness's own words at the refusal (`build_KCLT.log:565`, key `8d0e1ad5865e`):
"The run's artifacts stay on disk; rebuild at a stable tree to earn the ledger entry." So YES, an entry
needs a rebuild — but NOT REBUILT: the PR head moved to `5b1a7ab5` (touches `road_descent.py` /
`road_ramp.py`), so an entry earned at code tree `fd3158bac7ba` would key a superseded tree; the master's
sweep at the merged head earns it. Nothing else depends on the entry (the body is proven twice: build =
replay arm B = this lane's replay, `c558693ad8bd`).

## The seven rows (PR #487 @ `824680bb`; head is now `5b1a7ab5`, not rebuilt)

| airport | body main -> branch | ramps / length / longest / max reach | every run at cap | on followable ground | rwy/taxi/apron movers | `road_cross_section` | CRITICAL motion / visual | adjudicated airside | rc, solve |
|---|---|---|---|---|---|---|---|---|---|
| CYXY | `cf8e9e89ec62` unchanged | 1 / 8 m / 8 m / 14.7 m | 0 | 0 | 0 | 18 = 18 | 0 / 52 | 254 = 254 | 0, optimal |
| SPJC | `61f66f149737` unchanged | 1 / 8 m / 8 m / 44.6 m | 1 | 0 | 0 | 52 = 52 | 0 / 507 | 891 = 891 | 0, optimal |
| KASE | `f9b157158a39` -> `c2200384ee0d` (1 node, 0.01 m) | 1 / 6 m / 6 m / 6.4 m | 0 | 0 | 0 | 14 = 14 | 1 / 45 | 2,654 = 2,654 | 0, optimal |
| NLWF | `45ec40e74dcb` unchanged | 1 / 23 m / 23 m / 23.2 m | 0 | 0 | 0 | 24 = 24 | 0 / 23 | 3 = 3 | 0, optimal |
| HECA | `75c751a9dd95` -> `189234d8e929` | 38 / 593 m / 57 m / 77.5 m | 3 | 0 | 0 | 512 -> 515 | 2 = 2 / 1,912 -> 1,910 | 12,205 = 12,205 | 0, optimal |
| OTHH | `500f5dddce63` unchanged | 0 | 0 | 0 of 0 | 0 | 3 = 3 | 0 / 2,062 | 493 = 493 | 0, optimal |
| KCLT (roadramp2 lane's build) | `0b1566de77d5` -> `c558693ad8bd` | 38 / 598 m / 103 m / 103 m | 2 | 0 | 0 | 767 -> 765 | 5 = 5 / 1,974 | 3,355 = 3,355 | 0, optimal |

FOUND, NOT FIXED: (1) HECA `gap:8/s0/lot` node at 30.11510995356, 31.41089017767 flips 104.17 -> 101.80
(2.37 m) — review R5's lot-rim relaxation defect, present in both arms at different levels; (2) HECA
`road_cross_section` +3, `pavement_over_road_cap` +1, `hard_conflict` +3, `transverse` +7 (all groundside;
airside counts equal) — rows not joined (`census_rows_diff` not run); (3) the registered captures
`conc333/NLWF_main28500ecf.pkl` and `surf337/HECA.pkl` no longer match current builds (NLWF: wrong ramps;
HECA: 4,108 vs 3,984 targets); (4) the ramp probe and `analyze.py` are now on their 4th / 3rd lane use,
unpromoted (no INDEX row); this lane added a scratch `nodediff.py` (canonical-join node lister by
role / ref / radius) that `airside_value_delta` does not offer per node.
