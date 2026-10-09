# roadramp3 — five review fixes on PR #487 (no geometry change)

Worktree `.claude/worktrees/roadramp2`, branch `claude/roadramp2`, base `824680bb`.

## Fixes

* (a) `airport/road_descent.descend`: a ramp record's `fits` is the contact's own
  `runs[m].fits` (was `runs[m].fits or least[m] < cap`): a contact with one run that needs more
  than the cap is NOT "fits", whatever its other runs are built at. Twin
  `test_a_stub_end_steepens_its_own_run_only` flipped to `not r["fits"]` (the 62.5 % stub).
* (b) `airport/road_ramp._ramp_figures`: steepened / at-cap are classed by `steepest` (was
  `grade`, the gentlest run); the `ramps_steepest` list sorts by and prints `steepest` too, so
  a ramp listed as at the cap is not printed at 5 %.
* (c) `test_the_design_grade_at_the_cap_is_the_ramp_of_old` runs on `_Shelf` and asserts a ramp
  exists. IT FAILS THERE — FINDING, assertion kept verbatim, marked `xfail(strict=True)`:
  2 of 12 targets (the two road vertices 20 m from the mouth, y = 0) are published at 710.667
  against the bound `max(700, 712 − cap·s) + 0.6` = 710.6, i.e. 0.067 m over. `descend`'s own
  label there is 710.0 (the cap descent); the per-route cap-Lipschitz lift of §37 (8) (`_lift`)
  publishes 710.667. main @ `3a64a153` (the ramp of old), run on the same `_Shelf` fixture,
  publishes the SAME 12 targets (710.667, 706, 700 × 4 per side): the control holds against
  main; the hand-written bound does not. Not attributed further (why the lift's station
  spacing gives 13.3 m where the graph hop is 20 m).
* (d) spec §37 (6a) (iii): the "`_Shelf` … is unchanged" sentence struck; it points at (iv).
* (e) `road_ramp.py` `on_ramp`: reads `STAND_M` (`ramp >= floor + STAND_M`, the same test
  `descend` uses for a ramp's length) instead of `1e-9`. Report-only counter (`on_ramp`,
  `on_dem`, `max_above_dem_m`, `max_reach_m`; read by `pipeline/build.py`'s log line only).
