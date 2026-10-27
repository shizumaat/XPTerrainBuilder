# #1461 lane lvnlk — handoff (paused 2026-10-27; RESUMED and the next step DONE, see the end)

Branch `claude/lvnlk-steep-junctions` (PR #1460). It is stacked on `claude/ltriang2` (#1493),
which must land first. Spec and every measurement: `Ortho4XP/docs/findings/vnlk-junctions-lvnlk.md`
(§1–§11). Raw dry-run records: `Ortho4XP/docs/findings/vnlk-junctions-lvnlk-dryrun-r5.json`.

## Done (round 5, this WIP commit; nothing pushed to the PR body yet)

1. **RULINGS 2026-10-28a.**
   - Two law keys:
     - `[design] steep_runway_ground_wavelength_m = 200`: on credible lidar (`inset_class.lidar_credible`).
     - `steep_runway_ground_wavelength_coarse_m = 250`: otherwise.
   - `runway_junctions.design(lidar=)` picks between them; `runway_yield._junction_design` passes `lidar_credible(airport, law)`.
2. **RULINGS 2026-10-28b.** `airport/junction_witness.detach_refuted`: a pavement drawn asphalt or concrete, whose runway contact the imagery refutes, is trimmed 3 m (`zones.adjacent_ground.lip_width_m`) back from every runway slab at load. It is not re-roled.
3. **Steep-only witness (new this round, needs the master's eye).**
   - The witness now reads only STEEP runways (`_steep`: verified end pins, else the DEM at the ends, |Δz|/L > the 29ac 10 % ceiling).
   - It runs after `end_pins.verify` in `load.py` (moved there from beside the threshold witness).
   - Why: the dry run below shows that, ungated, the saturation test refutes many real concrete taxiways at flat airports.
4. **Merges.**
   - origin/main merged. Conflict in `O4_Vector_Map.py`: both blocks kept.
   - Because of the stacked branch, `O4_Tile_Build_Log` was added to `O4_Step_Code._SHARED`.
5. **Tests.**
   - `tests/auto_patch_v2/test_steep_junctions.py`: 13 pass, including the new detach and steep-only tests.
   - Closure twins pass.
   - The full suite ran before the steep gate: 4865 passed.
     - 4 teardown errors, from a sibling lane writing `Elevation_data/-40+140/S38E144_airport_insets/index.json` into the shared repo.
     - The full suite was NOT re-run after the steep gate.

## Measurements (VNLK; sources)

- **Closing build `lvnlk5b`** (`/tmp/harness/lvnlk5b.osm`, body `b76e19a30974`, 250 m + 28b). **Built BEFORE the steep gate.** VNLK is steep (11.3 %), so the gate should not change it, but this is not re-measured. Not registered in `docs/frames.jsonl` yet.
  - Census ADJUDICATED 217 (round 4: 223; base 822). CRITICAL motion 1: 1.67 m over 2.79 m, `strip_transverse`. That is the detached Helo Apron's top corner, 1.3–1.7 m under the runway edge across the 3 m lip.
  - Helo Apron (`pav2`) rows against the runway: 13 → 0 (the bar is met). Internal rows: `taxi_box` 7, `airside_no_step` 7.
  - Profile against the video (findings §11 table):
    - three high-confidence bins are 0.1–0.4 pp outside;
    - heights within 1.8 m;
    - peak 16.62 % at 123 m below RWY 24.
- **Capture with the witness and the detach:**
  - `$SCRATCH/lvnlk/cap5/VNLK.pkl`, scratchpad, NOT registered. Re-take it with `v2_solve_replay.py --capture VNLK`.
  - The registered `lvnlk/VNLK.pkl` is round 4 (no detach).
- **Dry run across the 40 registered captures.** Taken BEFORE the steep gate, so it counts raw refutations. Raw records: `vnlk-junctions-lvnlk-dryrun-r5.json`.
  - The ungated witness refutes pavements at most big airports:

    | airport | refuted / joins |
    |---|---|
    | KBUF | 36 / 109 |
    | KDEN | 19 / 147 |
    | LEMD | 19 / 56 |
    | KLAX | 14 / 126 |
    | KLGB | 12 / 59 |
    | KATL | 9 / 67 |
    | EGLL | 8 / 54 |
    | HECA | 8 / 50 |
    | KBJC | 8 / 34 |
    | KEDW | 8 / 148 |
    | KCLT | 7 / 57 |
    | VHHH | 6 / 133 |
    | PAAQ | 5 / 28 |
    | CYXY | 4 / 10 |
    | EDDF | 3 / 31 |
    | KMCI | 3 / 72 |
    | CYCG | 2 / 8 |
    | KBUR | 2 / 11 |
    | KPDX | 2 / 34 |
    | KSUN | 1 / 12 |
    | LPHR | 1 / 4 |
    | TFFJ | 1 / 4 |
    | VNLK | 1 / 3 |

  - Many of these are concrete (KDEN `Concrete_1_New.pol`).
  - No imagery: KGRK, KRDU.
  - **So the 0.05 saturation tolerance (calibrated on VNLK's Arc texture only) does not generalise.** The steep gate keeps it to steep runways.

## Exact next step

1. Re-run the dry run WITH the steep gate:

   ```
   venv/bin/python $SCRATCH/lvnlk/dryrun.py $SCRATCH/lvnlk/caps_all.txt OUT.json
   ```

   - The script is in the scratchpad (it is not durable; it is 40 lines: load each capture's latest pickle and call `witness_paved_joins` with `built_tile_paths(custom_scenery_dir)`).
   - Expected: the rule fires only at VNLK (`pav2`). Every other registered capture is under 10 %.
   - Report the firing set to the master.
2. Re-run the full suite once (`tests/auto_patch_v2` + the CI twins + `test_harness` + `test_imagery_prefetch`, `-n 4`).
3. Run one closing VNLK build, register it, and update the PR body (round-5 text is in findings §11). Use **Refs #1461**: three high-confidence bins sit outside at 250 m.

## Open questions (for the owner, via the master)

- **The saturation witness's reliability off VNLK** (dry run above). It is gated to steep runways, but its calibration rests on one texture.
- **The detached Helo Apron's step under the runway edge** (CRITICAL motion 1, `strip_transverse` +3). The owner describes the runway as elevated above the cut pad. Making that step lawful is the retaining-wall / cut-edge rule, which is out of scope.
- **Grading the Helo Apron as ground** (the wider rule) is not ruled. Not needed for the bar.
- **Still open from earlier rounds:**
  - the reading of "steep";
  - retaining walls;
  - the 29ac ceiling on the runway's own ring.

## Resumed 2026-10-27: the next step is done

1. **Gated dry run:** the rule fires at VNLK only (`pav2`). Record: `vnlk-junctions-lvnlk-dryrun-r5-gated.json`.
2. **Full suite at `-n 4`:** 4866 passed, 0 failed.
3. **Closing build `lvnlk6`:** body `b76e19a30974`, identical to `lvnlk5b`. Registered as `lvnlk/lvnlk6.osm`.
4. **PR #1460 updated:** Refs #1461.

The open questions above stand.
