# Lane kbna555 — notes (#555 KBNA, #556 KBWG; tile +36-087, app 1.0.387)

## RESUME HERE (2026-10-12) — DONE, awaiting the master's merge

Code = 1eaa9115c (the recovered WIP, unchanged after verification). Nothing left to do in this lane.

- BISECT: neither is a regression. Same DEFECT at main b8b0abf4a, 7b2c122af, 6dfb97854, 11e4746ef and
  at `v1.0.350-beta.1` (867d90b75): KBWG_beta1 body d33cab2743d0 `runway_step 1` cliff 0.1801 m;
  KBNA_beta1 body a0376bbcd7e4 `runway_vertical_curve 1` (2.24 m) + `runway_transverse 4`, same EAT
  rect (3 pins, drop 9.12 m). The code read: `constraints/eat.py` 0d9954749 (09-13), `planar/weld.py`
  b5662afe5 (09-04), `runway_step` DEFECT family 9738638f4 (09-15).
- KBNA intervention (replay `cap/KBNA.pkl --from classify --verify`, EAT rule): DEFECT families ALL
  ZERO; 02R/20L z-DEM min -9.05 -> +0.05 m, bow -9.58 -> -2.74 m; §7 STOP lines gone; verify rows
  5061 -> 3480 (airside_no_step 1688 -> 698).
- KBWG intervention (replay, weld rule): DEFECT families ALL ZERO, rows 584 -> 582.
- CLOSING BUILDS (harness): KBWG_fix body bd850a637e3e, no DEFECT, census LAW-TRUE 940 -> 936
  (runway_step 2 -> 0); runway movers 3 nodes on 03/21, worst 0.06 m, at the 21 end. KBNA_fix body
  86c078601e62, no DEFECT, EAT rects 0 / pins 0 / runway_vertices_excluded 4, census LAW-TRUE
  20392 -> 18769; runway movers 02R/20L 261/579 nodes worst 9.38 m (the V removed), 13/31 13/876
  worst 0.05 m; structure frame 0 moved.
- Suites: `tests/auto_patch_v2` 2919 passed, 3 skipped, 1 xfailed, 1 xpassed; ratchets PASS.
- NOT fixed: (1) a rect that keeps OWN vertices beside excluded runway vertices is still pinned at the
  ceiling next to a runway edge (no witness at KBNA after the fix); (2) KBNA census CRITICAL motion 5,
  worst strip_arc stub|stub 3.63 m at 36.1354576, -86.6887073 — same in control and fix.

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
