# TFFJ verify abort — attribution (lane `tffjverify`, 2026-09-18)

App engine 1.50.1796 aborted tile `+17-063` because TFFJ failed VERIFY:
`runway_transverse 5`, `runway_vertical_curve 3`. Report read from
`/Users/noah/XPTerrainBuilderData/tmp/auto_patch_v2/+17-063/TFFJ/TFFJ.report.json`
(copied lane-local). Siblings TKPK / TKPN / TNCE passed.

## Instrument

`tools/v2_solve_replay.py --capture TFFJ` (19 s), registered frame
`/Users/noah/XPTerrainBuilderData/.harness/frames/tffjverify/TFFJ.pkl`,
base `43122f8d`, lane `tffjverify`.

The capture could only be taken after repairing the tree-wide `--capture`
pickling defect recorded in `docs/BETA2-BLOCKERS.md`
(`PicklingError: Can't pickle local object Frame.entry.<locals>.enter`):
`ProductionDem.__getstate__/__setstate__` in
`src/auto_patch_v2/airport/dem_production.py` now drop the `Frame.entry()`
closure and rebuild it from the pickled `frame`. That is an INSTRUMENT
repair on this lane's branch; no TFFJ fix is written here.

The baseline replay reproduces the shipped surface EXACTLY — same 5 + 3
rows, same magnitudes, same sites — so every arm below is a same-frame
reading. No airport build was run.

## The 8 rows (verify frame = plan frame + (42.0, +48.98) m)

Runway 10/28, 647 m of pavement; CIFP threshold pins at plan `x = -276.5`
(s = 12 m, z = 14.630) and `x = +358.5` (s = 647 m, z = 1.219).

| family | site (lat, lon) | s along 10/28 | read | built | cap |
|---|---|---|---|---|---|
| `runway_vertical_curve` | 17.9043225,-62.8464983 (v2, the RWY 10 pin) | 12 m | grade change over 12 m stations v1→v2→v3 | **2.600 m**, −21.83 % | 0.16 % |
| `runway_vertical_curve` | 17.9043270,-62.8463851 (v3) | 24 m | same chain, next station | **1.701 m**, +14.33 % | 0.16 % |
| `runway_vertical_curve` | 17.9044625,-62.8406188 (v54) | 635 m | station into the RWY 28 pin | **1.081 m**, −9.16 % | 0.16 % |
| `runway_transverse` | 17.9044038,-62.8465078 (v82, north junction edge) | 11 m | edge vs crown ridge, 9.05 m | 0.742 m, 8.19 % | 2.5 % |
| `runway_transverse` | 17.9044038,-62.8465266 (v83) | 9 m | edge vs ridge | 0.525 m, 5.80 % | 2.5 % |
| `runway_transverse` | 17.9042411,-62.8466068 (v163, south apron edge) | 0.5 m | edge vs ridge | 0.301 m, −3.32 % | 2.5 % |
| `runway_transverse` | 17.9042411,-62.8465502 (v164) | 6.5 m | edge vs ridge | 0.349 m, 3.86 % | 2.5 % |
| `runway_transverse` | 17.9044625,-62.8406188 area (face 0, x=347) | 635 m | edge vs ridge | 0.391 m, 4.34 % | 2.5 % |

(A sixth `runway_transverse` census row, 0.0745 m at s ≈ 18.5 m, is under the
0.1 m materiality floor and is not a defect.) All eight sit in the first
24 m and the last 12–24 m of the runway — **at the two CIFP threshold pins**.
Family is `runway` throughout; no blast pad, no displaced-threshold face.

## Mechanism: the runway PROJECTION breaks the ridge at the fixed pins

The LP surface is NOT off. Stage 1's own hard read before the projection is
`0.0849 m` worst row (`rulesets.runway.longitudinal`, marginal). The
projection (`solve/project.py:project_runway`, §09y) then reports
`worst hard row 0.0849 -> 3.4837 m`, `260 elastic rows`, `worst slack
3.468 m`, `max move 1.718 m`, `123 free columns / 125 runway vertices`.

The two non-free columns are exactly the two CIFP threshold pins, and they
are exactly the two vertices the projection does not move:

| vertex | s | shipped (projection ON) | projection OFF | DEM |
|---|---|---|---|---|
| v1 | 0 m | 13.929 | 14.812 | 20.513 |
| **v2 (RWY 10 pin)** | 12 m | **14.630** | **14.630** | 18.331 |
| v3 | 24 m | 12.708 | 14.427 | 16.509 |
| v53 | 623 m | 2.719 | 1.657 | 3.531 |
| v54 | 635 m | 2.519 | 1.419 | 2.599 |
| **v55 (RWY 28 pin)** | 647 m | **1.219** | **1.219** | 1.863 |

Built ridge grades, west end / east end:

* shipped: `+5.85 %, −16.02 %, −1.67 %, −1.67 %` / `−1.67 %, −1.67 %, −10.83 %`
* projection OFF: `−1.51, −1.70, −2.10, −2.21 %` / `−2.06, −1.99, −1.66 %`

The projection holds every free column at the longitudinal cap plus its own
held bar (1.5 % + `hard_tol_m` 0.02 m per 12 m edge = 1.667 % — the shipped
interior grade, exactly). Over the 635 m between the pins that line drops
10.6 m, but the pins are 13.411 m apart, so **the 2.8 m that does not fit is
dumped as a step at the two pins** — the V at v2 (2.60 m + 1.70 m) and the
cliff into v55 (1.08 m). The 5 `runway_transverse` rows are the same event
read across the width: the ridge fell up to 1.7 m under edge vertices that
fell by 0.3–1.0 m.

## Interventions (2, both flip the rows)

| arm | stage-1 worst hard row | ridge bow | verify DEFECT families |
|---|---|---|---|
| shipped | 3.4837 m | −1.43 m | **runway_transverse 5, runway_vertical_curve 3** |
| `--design-weight runway_projection=0` (the projection's own diagnostic arm) | 0.0849 m | −0.07 m | **ALL ZERO** |
| `--design-weight hard_tol_m=0.1` (held bar 0.1 m/edge ⇒ 2.33 % allowed) | — | −0.21 m | **ALL ZERO** |

Both arms also improve every other family the replay prints:
`airside_no_step` 956 → 686 / 710, `strip_transverse` 58 → 0,
`taxi_box` 129 → 18, `within_shape` 585 → 615 / 628 (the only regression).

The second arm is the quantitative confirmation of the mechanism: at a
0.1 m held bar per 12 m edge the allowed grade becomes 2.33 %, the real
2.11 % profile fits between the pins, and no step has to be minted.

## Not the cause

* **Emit / crown-lift.** Verify on the solved surface reproduces the shipped
  rows exactly; nothing is minted downstream of the solve.
* **The DEM.** The pins are CIFP, not DEM (DEM is 3.7 m ABOVE the RWY 10 pin
  and 0.6 m above the RWY 28 pin). The projection-OFF surface stands on the
  same GLO30 raster and reads ALL ZERO. 30 m radar on the hillside is what
  makes `z − DEM` reach −6.6 m in the cut, but it does not drive these rows.
* **Verify's span rule / cliff escape** (RULINGS 2026-09-16aa). It is
  `runway_step`-only (`verify/runway.py:_span_rule`) and correctly so: these
  two families price a RATE against the law, not a wall between faces.
  Extending it here would forgive a real 2.6 m bump at a threshold.

## Fix shape (words only — NOTHING written)

Lives in `src/auto_patch_v2/solve/project.py::project_runway` (the free /
fixed split at `free_columns`, the `held` right-hand side, and the elastic
arm at `_relax_lp`).

1. **Price the pin-to-pin deficit BEFORE the QP.** Between two fixed pins
   the longitudinal family's feasible drop is `cap × span`; when the pins
   demand more, the projection must spend the relaxation on the
   LONGITUDINAL rows UNIFORMLY along the profile (deficit / span, a common
   over-grade) instead of on whichever coupled rows the elastic LP finds
   cheapest — the elastic arm today buys its slack locally and therefore
   always pays at a pin.
2. **A projection may never mint a DEFECT-family row.** `project_runway`
   already has the "never a silently worse surface" contract for a
   non-optimal QP; it should extend to the surface it returns — if the
   projected vector breaks `max_grade_change` / `transverse_max` anywhere
   the design vector held them, return the design vector and name the
   refusal. Here the trade was a 0.085 m residual for a 1.718 m move and a
   −21.8 % break.

## OWNER QUESTIONS

**TFFJ-1 (the law).** TFFJ's two CIFP thresholds are **13.411 m apart over
635 m = 2.112 %**. `law/rulesets.toml:83` prices `icao.runway.longitudinal`
at **1.5 % for every code** (owner 2026-07-08, over Annex 14 §3.1.13's 2 %
for code 1/2; TFFJ is code 1 at 647 m). With both thresholds pinned the
runway family is INFEASIBLE by construction — the solve says so itself in
the projection-OFF arm: *"48 rows are an INFEASIBLE SET, min total shortfall
**3.8812 m**"*, against a hand deficit of `13.411 − 0.015×635 = 3.886 m`.
Even at Annex 14's own 2 % the deficit is still `13.411 − 12.700 = 0.711 m`.
This contradicts the standing "feasibility is GUARANTEED for a real airport
with real thresholds" ruling, so one of the two modelled facts must yield:
(a) the longitudinal cap is a SOFT target at a runway whose declared
thresholds exceed it (the surface then rides at the declared 2.11 % and the
census reports, never aborts), or (b) a threshold pin may yield by the
deficit. Which?

**TFFJ-2 (the gate).** With the projection off, TFFJ ships a smooth
2.0–2.3 % runway that exceeds the 1.5 % cap everywhere and still reads
**zero** in every DEFECT family, because no census family prices runway
LONGITUDINAL grade. Today the engine aborts the whole tile for the step it
mints trying to honour a cap it cannot honour. Is the intended behaviour to
ship the over-grade runway and report it?
