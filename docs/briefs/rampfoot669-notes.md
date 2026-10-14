# rampfoot669 — issue #669, the ramp foot runs out at road grade (RULINGS 2026-10-14c (5))

Branch `claude/rampfoot669` off main 83927e7ef. Captures (this lane, at 83927e7ef):
scratchpad `rampfoot669/{KCLT,HECA,SPJC,OTHH}.pkl`.

## The site (KCLT, sw27 = main before 14c)
* The departures roadway's object ramp is `Terminals/techos_1_charlotte.obj` (unit:31,
  deck_kind `candidate`, elevated): it descends NORTH ~7 % from y 6.0 to its zero; the
  foot's lip at 35.2223764, −80.9423153, 14 m wide (`airport/ramp_feet`). (The OSM
  `bridge=yes` secondary −1571/−10515 along 35.2213 is the same roadway's map.)
* Profile north from 35.22234, −80.94236 (5 m steps): the pack pavement under the ramp
  `gap:0` (groundside_pavement, a §53 gap piece) carries the ground at 222.2–222.5 to
  ≈ s = 8 m; beyond it NO face — raw DEM 218.1 (s = 10) → 217.5 (s = 60), big_roads −1570
  at 217.99 from s = 75. THE CLIFF: 222.24 → 218.14 = **4.1 m inside ~5 m** at the patch
  edge. Beside it (−80.94225) gap:0 222.08 → DEM 219.15: 2.9 m.
* What graded the ground up there: the gap piece `gap:0` (pack pavement page) following
  the terminal unit's pad `building75` (222.68). Not a 10-03e landing (KCLT has 0 landings:
  no deck member of a unit), not a pad face, not a road.

## Consumer census — every pass that grades ground to an object ramp's foot
| pass | grades the foot how | in the travel direction before | ruled here |
|---|---|---|---|
| `planar/landing` (10-03e) | landing platform at the unit datum + y_land, 1:3 collar all round | the 1:3 collar | NOT CHANGED this round (the mint counts such a foot `landing` and skips it). TRIED and withdrawn: the collar and the lot cleared AHEAD of the foot (width = the foot's, run = offset / 5 %) — at HECA T3_road landing3 (30.1140697, 31.3975845, 101.78 m over DEM 94.87) the mapped pad road small_roads:-3963 then took the ground ahead and ended at 99.42 m over raw DEM 93.4 (a 6 m step, worse than the collar's 3 m toe step at sw28). Needs a ruling: does a mapped road ahead of a landing carry the run-out (pad-road exit walk), or does the run-out take it? |
| cluster pad (`classify/evidence._cluster_pads`) | the unit pad covers the deck footprint | pad edge: whatever borders it | the run-out leaves the patch edge (any face) |
| §53 gap pieces (`gap_mint` / `gap_terrace`) | pack pavement under the ramp, follows its neighbours | patch edge → raw DEM (KCLT) | idem |
| pad roads (`ribbon_mint.mint_pad_roads`, `pad_road_exit`, `pad_ramp`) | a MAPPED road off a pad ramps at 5 % from the rim | only where a mapped way continues | untouched; the run-out is the same law where no way continues; run-out faces are excluded from `pad_ramp`'s rim seeding (they carry their own row) |
| `airport/sunken_ramp` (#516) | the other direction: a foot UNDER the ground leaves the pad | n/a | untouched |
| road ramps §37 (`constraints/road_ramp`) | mapped roads to an object contact | n/a | untouched |
| zones 1–2 (adjacent ground) | airside only | n/a | untouched |

Single derivation: the FOOT is read once (`airport/ramp_feet`, memoised per partition) by
`classify/ramp_runout`. The STRIP is minted once,
in the pad roads' last stage (`classify/ramp_runout.mint_ramp_runouts`), as a
`service_road` pad-road cell `runout:<k>` (census reads road law); its rows are
`constraints/ramp_runout.runout_rows` (one design row per free vertex, the
`pad_ramp.ramp_delta` profile shared with the pad-road ramp).

## Build cost (master 2026-10-14) — one parse per resource
`ramp_feet` now runs once per build, after the planar stage, on the run's `ResourceCache`
(`attach_ramp_feet` → `Airport.ramp_feet`); `sunken_ramp` also reads through that cache.
Recorded `[ramp feet]` phase: OTHH 0.78 s (389/389 resources already parsed), HECA 0.24 s
(125/125), KCLT 0.63 s (36/36); it was 29–36 s / ~10 s / ~6 s. Run-out faces byte-identical
(KCLT runout:1, HECA runout:0); OTHH still 0 run-outs.

## RULINGS 2026-10-14i (road carries the run-out at a landing) — tried, withdrawn
Build `rampfoot669d_HECA`: the collar was cleared ahead of the foot (lot not cut), and every
ribbon touching a landing was made a pad road of it. Result vs sw28: the lot `dsf:pol10`
welded up to the landing (worst +5.70 m at 30.1113059, 31.3922606; lot 3–5 m over the DEM for
65 m ahead of landing4, then a 2.9 m step). Road `small_roads:-3963` ahead of landing3 stayed
at 100.4 → 99.8 m and ended over raw DEM 93.67 (a 6 m step): the mapped way dead-ends there,
so the exit walk prunes it. Gap pieces gap:26 / gap:2 / gap:6 moved 1.7–3.1 m. Withdrawn; the
landing case stays as on main (the collar banks it).
