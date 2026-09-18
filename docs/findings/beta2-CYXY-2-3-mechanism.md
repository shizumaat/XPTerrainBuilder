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
