# seatspec summary — spec §62: the pad SEAT where pavement touches it (Fable `seatspec`, 2026-10-09)

Branch `claude/seatspec` (= `origin/claude/pads67` 9ab7b36e + main f314564d). Docs only: spec §62 in
`Ortho4XP/docs/specs/auto-patch-v2/design-surface-spec.md`, `docs/briefs/seatspec-notes.md`, this file; probe scripts stay
in `<scratch>/seatspec/` (`siteE.py`, `rows_on.py`, `cmp_arm.py`, `armE.py`, `armD.py`). Frames registered under lane
`seatspec` (HECA base / arm E / late pair; KCLT base). No engine code, no airport build. §62 is the next free number
(§61 is `claude/valleyspec`'s; §56–§60 held by the other unmerged branches).

## What was measured (replays of `frames/pads67/HECA.pkl` and `KCLT.pkl`, `--workers 9`; one solve ≈ 6 min)

| arm | result |
|---|---|
| BASE `--from constraints` | reproduces sw8's P classes: AIR-TOUCH 21 = 21, AIR-NEAR 7 = 7, ARMED 1, GS-TOUCH 1, GS-NEAR 15 (16); stage-2 worst hard row 0.126 m = the building75 vertex on a `pavement_road_cap` row |
| late pair (`--gap-free` base + `--late-from`) | = the build: GAP 51 / 339 m, M 255, GS-NEAR 16 / 570; 16 of 53 GAP runs stand beyond the 1.95 m follow reach |
| A1 `--drop-generator pavement_road_cap` | pad conflicts 108 → 20 (building75's 81 gone, 0 rows on v22865); held datums 0 of 47 moved; BUT GS-NEAR 515 → 1,555 m — landside pads drift 3.6 m: the fallback cap is today's de-facto seat of a landside-only pad |
| E `armE.py` (apron chords across the rings of one face, 5,695 rows) | **AIR-TOUCH 21 → 0, AIR-NEAR 7 → 4**; pad conflicts 108 → 88; 32 of 47 datums moved — the objpav402 pads to ONE grade (building100 101.25 → 93.79) 8.5 m under the DEM; runway 113 movers worst 0.14 m (1.7 km away, the §61 class), taxi 2,347 (0.82), apron 2,120 (2.17) |
| RR `--drop-generator road_ramp` (attribution only) | building164's 66 m ARMED run → 0 m; groundside conflicts 175 → 18; datums 0 moved; runway / taxi 0 |
| D `armD.py` (follow reach = the piece's stand-off, 2.81 m) | **GAP 51 / 339 m → 17 / 156 m**; nothing standing moves; the 17 left are the cut's (Voronoi group / floor merge) |

## Attributions (each by the solved row set or an intervention; site numbers in the spec)

* **building75** (81 pad-tier conflicts): NOT `pad_slope_ceiling`. ONE `pavement_road_cap` 29ac row welds the pad rim vertex v22865 to the road vertex v40607 1.04 m away (10 % × 1.04 = 0.10 m) while the road is held by its ramp ceiling; the LP relaxes the pad's hard plane. Arm A1: 0 violated rows on the vertex.
* **Class C** (`building12`): the landside pad is seated by its SENIOR groundside frontage — the service road, through the same fallback weld — and the road by the apron (road_cross_section chain, 14 hops); the lot 0.66 m off is a junior residual with no row back (§28 mints nothing for a non-airside pad).
* **Class E** (#492, objpav402): v11868 (building100's contact, 101.25) and v11597 (apron, 93.56, 6 m away) share NO row — `apron_within_shape` pairs vertices inside ONE ring; a sheet with the pads as holes has no within-shape law across it, each hole ring seats alone (building100 unreached by the pair graph; building101 chained by the 1 % preference to the taxiway). Arm E removes every rim step.
* **Class B** (building164; KCLT building26 / 27): one mechanism — a road law FIXING a road vertex inside the pad's frontage (the `road_ramp` DEM-target equality / ceiling Band; the `coverage_edge join` PIN at building26) against §28's priced joint. Arm RR confirms at building164.
* **Class D**: (a) follow reach 1.95 m < the stand-off (16 runs); (b) the Voronoi cut hands the pad-side region to another level group (declared bounds); (c) the mint floors merge 6 pad stations away. Arm D answers (a).
* **building147**: the six census `airside_no_step` rows (-10218|-10219, 1.63–1.76 % vs 1.54–1.58 % over 94–135 m) are NOT in the engine's violated set (its 6 `no_step` rows are at 30.138,31.408, a different place): the census's route-pair budget is unwidened where the pair's far end is off the widened faces — read, not intervened (owed).
* **M class**: 229 of 254 HECA runs (84 of 101 KCLT) are lawful grade (the meeting pavement inside its cap, the bare side 09d (1)'s bank); 25 / 17 over-cap runs are the E sheets seen from the next ring. No new class.
* `hard_conflict` taxi 63 → 64 and CYXY adjudicated airside 254 → 265: NOT located (no CYXY replay run; not attempted).

## The rules (§62 (2)–(5))

R-C one leader for a landside-only pad (the senior touching face, HARD), every other touching face follows it under §28, the §28 (6) terrace the one exception (09f). R-D the pad station is a FIXED contact of its gap part: reach = the stand-off, the cut anchored on the pad, no merge of a pad station; "terrace otherwise" = the knife inside the piece. R-E `apron_within_shape` body chords across the rings of one face (no new head / key / weight). R-B no road law fixes a road vertex inside a seated pad's frontage (ramp target / ceiling / coverage-join pin start outside it). R-F the 29ac fallback never pairs a pad vertex — landing WITH R-C rule 1 (arm A1 shows R-F alone releases landside pads).

## Unproven: R-C rule 2 (§28 population widening; no knob), R-D rule 2 (the cut), R-E at KCLT / OTHH (counted, not replayed — KCLT arm re-run pending at hand-back), the 08d (2) misfit on a sheet whose relief exceeds 1.5 %.

## Owner questions (yes/no, recommendation)

Q1 R-C seniority: a landside pad between a ROAD and a LOT follows the road, the lot grades to it — YES. Q2 the sheet's LEVEL under R-E: seat an apron sheet on its own DEM plane where the reach band from its taxi contact allows it (HECA's terminal row at grade ~102 instead of 8.5 m in a cutting at 93.8) — YES. Q3 R-D "terrace otherwise" = a part at the pad's level with the knife on the far side, never a step at the building — YES.
