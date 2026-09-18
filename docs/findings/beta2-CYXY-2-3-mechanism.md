# BETA2 CYXY-2 / CYXY-3 — interventional mechanism (lane b2cyxyhill)

Rows CYXY-2 / CYXY-3 of `docs/BETA2-BLOCKERS.md`. Sites
60.7141907,-135.0766528 (`pav4 <- building9`) and
60.7155636,-135.0792452 (`dsf:pol129 <- building10`).

## Instrument

`tools/v2_solve_replay.py --capture` CANNOT WRITE A PICKLE AT MAIN 23556c2a:

    _pickle.PicklingError: Can't pickle local object
    <function Frame.entry.<locals>.enter at 0x...>
    when serializing dict item '_enter'
    ... auto_patch_v2.airport.dem_production.ProductionDem ...

(`ProductionDem` holds a `Frame.entry()` closure — the §46 `Frame.entry()`
work, lane `xplatquantum`.) Every registered CYXY capture is `[MISSING]`, so
this lane could not reuse one either. The reading below therefore runs the
capture's OWN stages in process with `pickle.dump` stubbed
(`scratchpad/probe28.py`), then calls `constraints/pad_frontage_gs`'s own
`_pad_polys` / `_groundside_geoms` / `pair_dem_step_m` — no re-derivation of
the law quantity. CYXY capture 8-12 s. **The capture-pickle break is a
separate defect and is NOT fixed here.**

## Measured — §28 (6) DISARMED because THE PAD FOOTPRINT SHRANK

Same corpus, same probe, one tree moved. Control at `37dac595` ("§28 (6)
MEASURED: CYXY's two hillside lots back on the DEM") reproduces the law
file's own numbers exactly (`law/emit.toml:530-547`, `frontage_step_max_m
= 3.2`):

| pair | tree | pad rim verts | pad area m2 | front DEM med | pad DEM med | step m | §28 (6) |
|---|---|---|---|---|---|---|---|
| `pav4 <- building9` | 37dac595 | 40 | 4477.8 | 698.353 | 694.633 | **+3.757** | DISARM |
| `pav4 <- building9` | HEAD 23556c2a | 26 | 4338.1 | 698.353 | 697.558 | **+0.861** | armed |
| `dsf:pol129 <- building10` | 37dac595 | 22 | 750.8 | 699.692 | 696.250 | **+3.430** | DISARM |
| `dsf:pol129 <- building10` | HEAD | 14 | 442.9 | 699.692 | 699.076 | **+0.915** | armed |
| `pav29 <- building1` (control pair) | both | 21 / 23 | 1144.8 | — | 705.065 | +0.018 / +0.053 | armed both |

`groundside_frontage_level.pairs_held_as_terrace`: **2 at 37dac595, 0 at
HEAD**. The GROUNDSIDE side did not move at all — the frontage vertex count
(16 / 8) and its median DEM (698.353 / 699.692) are IDENTICAL on both trees.
Only the PAD side moved: `building10`'s pad lost 41 % of its area
(750.8 -> 442.9 m2) and 8 of 22 rim vertices, `building9` 14 of 40. The lost
vertices are the DOWNHILL ones: both pads still span the hill
(`building9` rim DEM 693.943..698.403 at HEAD) but the rim MEDIAN — the
quantity `pair_dem_step_m` subtracts — rose +2.93 m / +2.83 m, which is the
whole of the step's collapse. The bound never changed; the number measured
against it did.

## Suspicion in the blocker row is REFUTED

CYXY reports `clusters 0` on both trees, so §16g (10)'s cluster pad
(`f71fca86` / `ad8b5120` / `dba32406`) is INERT here and cannot be the
cause. An explicit HEAD arm with `--placement pad_airside_clip=false`
reproduces the HEAD numbers EXACTLY (0.861 / 0.915, areas 4338.1 / 442.9),
so the pad/airside clip is not the cause either.

STATUS: bisecting 37dac595..HEAD (1,204 commits) for the pad-face change.

## BISECTED — `dba32406` is the first bad commit

`git bisect run` over 37dac595..HEAD (1,204 commits, 10 probe arms, one
shared corpus, criterion `building10` pad area > 600 m2):

    dba32406cf5e49f69cb85d6e1e1ee666fbea4278 is the first bad commit
    §16g (10) (12) (1) (c): the airside REGION is no longer differenced by
    the pad union — one cutter, and it is the arrangement's
    (RULINGS 2026-09-16r)
    Ortho4XP/src/auto_patch_v2/classify/roles.py | 15 +++++++---

It DELETES `region = region.difference(ev.pad_union)` in
`classify/roles.classify`. Per-arm readings for `dsf:pol129 <- building10`:

| tested commit | pad area m2 | step m | §28 (6) |
|---|---|---|---|
| 37dac595 (control) | 750.8 | 3.430 | DISARM |
| 1f54da44, b62be9d7, 25e5e197, 782a50d6 | 750.8 | 3.430 | DISARM |
| 53e91d54 (`merge main into claude/v2padclip`) | 733.6 | **3.157** | armed |
| `dba32406` and every later arm incl. HEAD | 442.9 | 0.915 | armed |

Note the SECOND, smaller contributor: by `53e91d54` the pair had ALREADY
crossed the bound (3.430 -> 3.157 against 3.2) on a 17 m2 pad change — the
0.23 m-wide gap the law comment warns about (`emit.toml:541-549`) is that
narrow. `dba32406` is what makes the collapse unambiguous.

## Mechanism (one paragraph)

§28 (6)'s quantity `pair_dem_step_m` is the frontage vertices' median
`dem_z` minus **the pad face's RIM-VERTEX median `dem_z`** — a median over
the arranged planar face's ring, not over the building's ground. Until
`dba32406` the airside region was differenced by the pad union in
`classify/roles.classify`, so a hillside pad kept its whole outline and its
rim carried its downhill vertices; `dba32406` removed that subtraction
(deliberately, RULINGS 2026-09-16r: one cutter, the arrangement's, after
double-cutting raised the HECA census 4.2 % and LEMD 23 %), and the
arrangement's own clip now trims these two pads — `building9` 40 -> 26 rim
vertices / 4477.8 -> 4338.1 m2, `building10` 22 -> 14 / 750.8 -> 442.9 m2,
in both cases losing DOWNHILL rim vertices. The frontage side is untouched
(same 16 / 8 vertices, same 698.353 / 699.692 medians), so the pad rim
median alone rises 694.633 -> 697.558 and 696.250 -> 699.076 (+2.93 / +2.83)
and the step falls 3.757 -> 0.861 and 3.430 -> 0.915, under
`frontage_step_max_m = 3.2`. Both pairs therefore ARM, §20 pulls each lot to
its pad's edge level and the pad to the apron, and the owner sees the two
hillside lots flat with the apron with the DEM ~2 m above — exactly what
§28 (6) was ruled to prevent. `pairs_held_as_terrace` 2 -> 0.

## Minimal fix shape — NOT IMPLEMENTED (needs an owner ruling)

The bound is not the defect and `dba32406` must not be reverted (its own
measured census gain, and it is a ruling). The defect is that §28 (6)'s
quantity is read off a face rim the ARRANGEMENT is now free to trim, so a
hillside pad's ground is measured only where the arrangement left it. The
minimal shape is to make `pair_dem_step_m`'s pad side the PAD'S OWN GROUND
independently of the arranged rim — either the pad body's pre-arrangement
outline, or an AREA-weighted DEM median over the pad polygon (sampling the
planar map's own DEM, never a second reader) instead of a rim-vertex median.
That is a law-quantity change: it re-prices LEMD `building4 -> pav124`
(+3.00, the pair 13o ordered ARMED) as well, so it is a §28 (6) amendment
for the owner, not a lane edit. Per project law (mechanism before fix) the
mechanism above is the deliverable; no code was changed.

## What this lane did NOT do

- No fix implemented, so no tests and NO CYXY build / census were run.
- The `v2_solve_replay --capture` pickle break at main 23556c2a is
  diagnosed but NOT fixed.
- The smaller pre-`dba32406` drift (3.430 -> 3.157 by `53e91d54`) is
  measured but not attributed to a commit.
