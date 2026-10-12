# Lane kbna555 — notes (#555 KBNA, #556 KBWG; tile +36-087, app 1.0.387)

## RESUME HERE (2026-10-12, resumed session)

- Branch `claude/kbna555`: WIP of the ended session committed as 1eaa9115c (both fixes + twins), main
  1ff5a912a merged (fc0a951d9). Twins `test_v2eat.py` + `test_weld_ridge_end.py`: 26 passed.
- Old session's scratch (captures `cap/KBNA.pkl`, `cap/KBWG.pkl`, bisect logs):
  `/private/tmp/claude-501/-Users-noah-XPTerrainBuilder/0ec4326d-10bf-4753-bd1b-ca41fda6bcd1/scratchpad/kbna555`.
  This session's: `…/466e18b3-e03c-471f-b042-c64d8df4e04d/scratchpad/kbna555`.
- BISECT (harness builds, one per arm, same defect row each): KBWG `runway_step 1`, cliff 0.1801 m at
  main b8b0abf4a, 7b2c122af (10-10), 6dfb97854 (10-09 18:50), 11e4746ef (10-09 11:24) AND at
  `v1.0.350-beta.1` (867d90b75, tag KBWG_beta1, body d33cab2743d0). KBNA `runway_vertical_curve 2`
  (0.2333 / 0.2042 m) at main and at 11e4746ef (KBNA_c, body 4d592d9c74c4). => KBWG is NOT a regression
  (it failed on beta 1's engine too). KBNA at beta 1: build running in tree `kbna555c` (now detached
  at the beta-1 tag), log `kbna_beta1.log`.
- KBWG intervention (old session, `kbwg_fix2.log`): capture replayed `--from classify` with the weld
  change -> `verify DEFECT families: ALL ZERO`, rows 584 -> 582 (runway_step 1 -> 0, runway_crown 54 -> 53).
- KBNA intervention: replay of `cap/KBNA.pkl --from classify --verify --emit` with the EAT change
  running (`kbna_fix.log`).
- NEXT: read both; runway movers (`tools/airside_value_delta.py --by-ref`); related suites; ratchets;
  ONE closing harness build each (the fixes are separate) + census.

Branch `claude/kbna555`, base main b8b0abf4a. Scratch: session scratchpad `kbna555/`.

## Step 1 — reproduced through the harness (main b8b0abf4a)

- KBWG `build_airport.py KBWG` (tag KBWG_repro, body 936b265e1a72, 28 s): `runway_step 1`, cliff 0.1801 m
  over 0.25 m, ways 1|2 — the owner's row exactly. Site 36.9741838, -86.4139459 (runway 21 end, on the
  centreline).
- KBNA `build_airport.py KBNA` (tag KBNA_repro, body ab095a4282a6, 484 s): `runway_vertical_curve 2`,
  0.2333 / 0.2042 m, 02R/20L — the owner's rows exactly. Stations 36.1182487, -86.6654430 and
  36.1183523, -86.6654041.
- Captures: `cap/KBWG.pkl`, `cap/KBNA.pkl` (+ `.solved.pkl`); the replay reproduces both.

## Step 2 — mechanism (read on the captures)

### KBNA: the EAT pin family pins RUNWAY vertices 9.12 m under the ground
- The DEM along the 02R/20L ridge is smooth (179.6 → 164.6 m). The BUILT ridge is a V: 179.83 → 166.18 m
  at s = 660 m → 172.46 → 164.59; 9.0 m under the DEM at the apex, grades −2.5 % / +1.8 %. The two
  vertical-curve rows are the apex only.
- `eat_anchor_rect`: 1 rect accepted, 3 pins at 165.829 m (DEM 174.95) for end 31 of runway 13/31 —
  D = 326–329 m beyond the end, q = −19…−22 m. The three vertices (v78, v79, v527) are the whole of a
  3-vertex sliver face `stub:dsf:pol331` and ALL THREE are vertices of a runway 02R/20L face (its west
  edge, 36.1183478, -86.6656762).
- `constraints/eat.py` excludes runway FACES ("the runway profile is senior — an EAT ceiling must never
  bend it") but selects vertices per taxi-family face; a vertex shared with a runway face is pinned.
  `withdraw_against_senior` only yields to another Pin / a Flat group.
- Build log: `EAT ramp reach … LOOP TOO SHORT at 3 foot(feet) — forced grade 476 %`; `37 → 71 RUNWAY
  row(s) in a law conflict, kept hard`; `§7 STOP … 0.128 m over after the projection`; runway 02R/20L
  `bow vs straight chord −9.58 m`.

### KBWG: the runway's ridge end is not a vertex of the rim cell's edge 0.25 m away
- The pack's runway 03/21 is TRANSPARENT in apt.dat; the pack draws it as `dsf:pol1`, 1.1 m wider on
  one side and 0.37 m longer at the 21 end. Classify gives the remainder role runway, ref 03/21
  (cell 6 → face 1).
- The weld (04u, tol 1.0 m) collapsed one end corner (0.996 m) but not the other (1.14 m), so the rim
  survives as a face 1 m wide with a 0–0.5 m wedge across the runway end.
- The CIFP-pinned ridge end (v198, 158.496 m) is the `runway_profile` breakline's last station. It is
  noded into the runway rectangle's end edge, but it is not a ring vertex of the rectangle cell, so
  weld rule (2) (senior vertex within tol of a junior segment is inserted) never sees it. The rim's end
  edge runs corner to corner (158.296 → 158.330) 0.245 m from the crown at 158.496: a 0.18 m fold in
  0.25 m.
