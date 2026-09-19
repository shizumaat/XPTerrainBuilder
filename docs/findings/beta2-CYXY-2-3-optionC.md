# BETA2 CYXY-2 / CYXY-3 — §28 (6) OPTION C: the pad's AIRSIDE-FRONTAGE datum

Owner RULINGS 2026-09-18c (1), verbatim model: "Building pads are seated
based on their airside frontage, then we leave a gap" — so §28 (6)'s
`pair_dem_step_m` becomes

    median dem_z over the groundside face's FRONTAGE vertices
  − median dem_z over the PAD'S AIRSIDE-FRONTAGE vertices

replacing the pad-RIM median that the arrangement has been free to trim
since `dba32406` (mechanism: `docs/findings/beta2-CYXY-2-3-mechanism.md`).
Fallback for a pad with no airside frontage: an AREA-WEIGHTED DEM over the
pad's own outline, sampling the planar map's own `Vertex.dem_z`.

## Instrument

`tools/pad_frontage_step.py CAP.pkl` (promoted this lane from the previous
lane's `scratchpad/probe28.py` on its second use, RULINGS `7e90032`). It
re-uses the engine's own derivations and re-spells nothing: the pair
population is `pad_frontage_gs._groundside_geoms` + `pads._pad_polys` +
`pads.pad_fronts_airside` + `pad_frontage_gs._airside_pavement_vertices`,
and the PAD'S AIRSIDE FRONTAGE is `pads.pad_frontage()`'s own contacts
restricted to `role_side(law, role) == "airside"` — the same `_fronting`
relation §20 seats the pad on, so the two directions cannot disagree.

Captures taken on this branch off `main 0bac9241` (the `--capture` pickling
repair `2dff85c2` is what makes this readable at all — the previous lane
had to stub `pickle.dump`): CYXY 7 s / 4,412 vertices, LEMD 220 s / 21,533,
HECA 16 pairs. `[guard] shared repo UNCHANGED` on every capture. All four
frames are registered in `docs/frames.jsonl` under lane `b2frontagedatum`.

## The population, both quantities (production DEM, the engine's own frame)

`frontage_radius_m` 3.0. OLD = frontage median − pad RIM median (the
shipped quantity); NEW = frontage median − pad AIRSIDE-FRONTAGE median
(option C); FB = the fallback, frontage median − area-weighted DEM over the
pad outline.

| airport | groundside face (role) | pad | OLD m | **NEW m** | FB m | airside-frontage verts |
|---|---|---|---|---|---|---|
| CYXY | `pav4` (parking_lot) | `building9` | 0.861 | **+4.192** | 2.249 | 7 |
| CYXY | `dsf:pol129` (groundside_pavement) | `building10` | 0.915 | **+3.283** | 1.532 | 3 |
| CYXY | `pav29` (service_road) | `building1` | 0.018 | **+0.047** | 0.031 | 5 |
| CYXY | `pav29#2` (service_road) | `building1` | 0.053 | **+0.082** | 0.066 | 5 |
| LEMD | `route2` (service_road) | `building26` | −0.753 | **−0.049** | −0.593 | 1 |
| HECA | `dsf:pol10` (parking_lot) | `building9` | −4.441 | **−4.006** | −3.018 | 22 |
| HECA | `dsf:objpav445` (groundside_pavement) | `building305` | 0.685 | **+1.599** | 1.426 | 7 |
| HECA | `dsf:objpav121` (groundside_pavement) | `building273` | 0.041 | **+1.237** | 0.445 | 21 |
| HECA | `dsf:objpav352` (service_road) | `building69` | 0.890 | **+0.991** | 0.378 | 4 |
| HECA | `dsf:objpav446#0` (service_road) | `building305` | −1.695 | **−0.781** | −0.953 | 7 |
| HECA | 11 more pairs | — | — | **+0.755 … +0.007** | — | — |

HECA's `dsf:pol10 <- building9` is held as a terrace on BOTH frames (its rim
reading is −4.441), so it is not a behaviour change anywhere.

CYXY `building9`: frontage median 698.300, rim median 697.439, AIRSIDE
frontage median **694.108** — the pad is seated 4.19 m under the lot that
fronts it, which is exactly the owner's 13l item 1 reading ("cut into the
hillside, the lot a storey up"). `building10`: 699.533 / 698.618 /
**696.250**.

## THE 13o-ERA LEMD PAIRS NO LONGER EXIST IN THE RELATION

The law comment's population (`emit.toml:527-538`) lists LEMD `building4 →
pav124` twice, `building4 → route3/6` and `building12 → pav70`. **None of
them is a §28 pair on this tree.** `pav124` is now `role = apron`, i.e.
AIRSIDE (`role_side` airside) — it is `building4`'s §20 frontage, not a
groundside neighbour — and `pav70` / `route3` / `route6` carry no face at
all. Measured directly: over LEMD's 34 airside-fronting pads and 56
groundside faces, only FOUR pad/groundside polygon distances fall under
30 m, all of them `building25`/`building26` against `route2` and a bridge
deck; `building4`'s nearest groundside face is beyond 30 m. So the LEMD
arming the brief required could not be read as such — and the option-C
frame is what dissolves it: a pad's own airside frontage IS its datum, so
the `pav124` pair 13o/12r ordered graded is now stated by §20 and not by
§28 at all.

## Arming under option C

Sorted by |step|: **4.192, 4.006, 3.283 | 1.599, 1.237, 0.991, 0.781,
0.755 … 0.007**. The population separates cleanly and IN THE RIGHT ORDER —
the three hillside lots at the top, every graded pair at the bottom — with
a gap of **1.68 m** (1.599 → 3.283), against the 0.23 m gap the shipped
rim-median frame left (3.00 → 3.43). Centre of the gap:
(1.599 + 3.283) / 2 = 2.441 → **`frontage_step_max_m = 2.4`**.

Arming under 2.4, the whole population: CYXY `building9` and `building10`
DISARM (the two BETA2 rows), HECA `building9` stays held (it was held
before too), and every other pair at all three airports stays ARMED. So the
ONLY behaviour change in the measured population is CYXY-2 / CYXY-3.

Noted, not decided: under the NEW quantity the shipped 3.2 would already
disarm `building10` — by 0.083 m. 2.4 is the gap centre and gives the
decision 0.88 m of margin on either side.

## Closing build — CYXY, the only build this lane ran

`CYXY_20260918T171219` on `claude/b2frontagedatum`: rc 0, 12.9 s, ways 273,
nodes 4,340, status optimal, `body_sha 74a61fd896b3`, artifact ledger
`ffa50922f000`, `[harness] shared repo UNCHANGED`.

**`groundside_frontage_level.pairs_held_as_terrace` = 2** (0 before).

The two sites, emitted patch vs the production DEM:

| site | row | emitted z | DEM | z − DEM | the pad it fronts |
|---|---|---|---|---|---|
| 60.7141907,−135.0766528 | CYXY-2 | 698.42 | 698.35 | **+0.07** | `building9` 695.43 |
| 60.7155636,−135.0792452 | CYXY-3 | 698.73 | 699.99 | −1.26 | `building10` 696.03 |

By FACE (median over the ring, which is the fairer read — the CYXY-3 probe
point is that face's lowest corner): `pav4` z 698.41–702.05, median 699.53
against DEM median 699.37 (**+0.16**); `dsf:pol129` z 698.73–701.13, median
700.19 against DEM median 700.47 (**−0.28**). Each lot now stands ~3 m
ABOVE the pad it fronts (`pav4` − `building9` = +2.99 m, `dsf:pol129` −
`building10` = +2.70 m) instead of being pulled down to it, and the apron
those pads are seated on is `pav9` at 693.5–695.5. The blocker's own words
were "pulled nearly flat with the apron; DEM ~2 m higher": the lots are on
their DEM and the pads are on their apron.

Census (`harness/census.py`): law-true **1,378**, ADJUDICATED **373**
(airside 295 / groundside 78), `groundside_frontage` design-target misses
**4**, max miss 0.014 m. This is a FRAME value, not an A/B: no base arm was
built this round (one airport, one build), so it may not be differenced
against the registered CYXY controls, which sit on other trees and dates.

## What this lane did NOT do

- **No LEMD build** (one airport per round). The LEMD arming is the probe's
  only: one pair, `route2 <- building26` at −0.049, ARMED — and the 13o
  `building4 -> pav124` pair the brief asked to confirm ARMED **is not in
  the §28 relation any more**, for the reason above.
- **No base arm / no matched census A/B** at CYXY. The interventional
  evidence for the change is the probe (same tree, same capture, the
  quantity as the only variable) plus `pairs_held_as_terrace` 0 → 2 and the
  site numbers.
- The area-weighted FALLBACK is implemented and twinned but is **unreached
  in production**: §28 (2) keeps a pad with no airside frontage out of the
  relation entirely, so it can only fire for a pad whose airside contacts
  carry no DEM sample (planar invariant I7 says they do).
- No other airport was built or censused; HECA and LEMD were read DRY, off
  captures.
