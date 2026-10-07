# gaps7 notes — spec §55 "as changed" (P12) built, replayed, built at HECA (2026-10-07)

Lane `gaps7`, branch `feature/pavement-gaps`. Frames under
`/Users/noah/XPTerrainBuilderData/.harness/frames/gaps7/`: `ARM2/` (the ONE
replay, `gaps3/HECA.pkl --from classify --late-from gaps6/BASE/solved.pkl`;
`solved.pkl` carries `late_cut` + `late_declared`) and `BUILD/` (the closing
harness build `gaps7_HECA`). Scratch `<scratch>/gaps7/` (`arm2.txt`,
`arm2.site.txt`, `census_build.txt`, `rows_class.txt`, `contour_read.txt`).

## Done

| step | state |
|---|---|
| S2′ Q-D | `model.planar.gap_parts_across_knife(ref_a, ref_b)` — two refs of one piece in two different `/s<j>` step parts; read by `constraints/pavement_cap` and `tools/check_grade._check_pavement_over_road_cap`; twins. Selects the probe's 111 rows on `gaps6/ARM1`. |
| S2″ Q-E | `gap_follow_rows(planar, law, fixed, part_stations=)`, `gap_follow.PartStations(stations, own, lot_rows)` built by `late_stage.cut_classification`; refused bounds in `report["declared"]` (64). |
| S2‴ Q-F | `late_constraints(widen_heads=, widen_floor_m=)`: `cap + floor/d` on all-unknown `Diff`s of the two ceiling heads (57,027 rows). |
| S3′ Q-G | lot rows AND `lot_fit` targets only on parts with `PartStations.lot_rows` (214 rows on 5 parts). The probe kept the targets on every lot; narrowing them moved nothing material (offline check: 83 / 66 stepping pairs against 82 / 65). |
| replay | relaxed 89 with P12's by-head line exactly; DECLARED 43 + OWN-GROUP 45 (24 / 6 / 10 / 5, worst 2.05 m); lot rows 214, 9 relaxed; stepping pairs 85 / 68 (P12 82 / 65: +3.7 % / +4.6 %); movers 0 of 34,540; knives 46, worst 7.94 m; ribbons grown 6 (P12 5). Sites = P12. |
| S4′ | `v2_late_read`: DECLARED / OWN-GROUP from the stage's own `late_declared`; lot rows = the stage's; MERGED-SLIVER naming; twin `tests/test_v2_late_read.py`. Deviation: the record is read from the solved pickle, not the sidecar (the reader reads pickles). |
| S5′ | Two reader defects fixed: (1) sidecar key `gap_pieces` was in no register — the emit RAISED (gaps6 never emitted with it); (2) the joint allowance was read for every pair: v2 verify 528 s -> 18.5 s (rows identical), harness census did not finish -> 275 s a patch. Contour joints attributed (below). Census by family below. |
| S6 | CYXY harness build `gaps7_CYXY` body `2a00c361ffc2` = main's. |
| S8 | non-Qt 8,751 passed / 20 skipped / 1 xpassed; Qt 311; four gate files 200; ratchets PASS. |
| S9 | `gaps7_HECA` rc 0, 467.5 s single run (sw1045 366.1 s; `late_stage` 101.1 s, every other phase equal), body `54c274700a00` = replay = `--workers 1` replay. S7 not needed (< 560 s). |

## Found, not fixed (each needs the spec author)

1. A NECK INSIDE ONE GAP PART MINTS A CONTOUR JOINT AND ITS ROWS ARE DROPPED.
   §55 (14) residual 5's hypothesis (joints earned from the DEM) is REFUTED by
   the read: `planar/shapes` is role-based; the 08k narrow-mouth rule
   (`narrow_mouth_max_m` 12 m) splits one part into several bodies at every
   neck, and `pipeline/shapes.apply_joints` drops every row across the
   contour. 132 contours: 112 inside ONE part (51 in `gap:0/s0/lot`), 8 on
   ribbons, 8 part + ribbon, 4 standing. 102 carry only pairs within 8 % x d;
   16 carry a pair beyond cap x d + floor (worst 4.95 m over 3.2 m in
   `gap:0/s10` at 30.1157278, 31.4080159 — the same pair the census prices as
   `pavement_over_road_cap` 4.96 m). The 30bk weld (`one_shape_roles`) is the
   precedent: a mouth with ONE part on both sides is no mouth. Not built.
2. THE DECLARED GAP JOINT DOES NOT RUN THE KNIFE'S LENGTH. 716 census rows
   (`mid_edge_step` 595, `vertex_to_edge_step` 121) + `cross_shape` 30 +
   `terrace_actual_step` 14 are pairs of two parts across a knife; 648 of the
   716 have no declared joint within 1 m. §55 (6) rows 10 / 14 expected 0.
3. THE CENSUS DOES NOT KNOW THE FLOOR. `within_shape` +2,033 and
   `pavement_over_road_cap` +373 rows inside one part are chords over 8 % by
   <= 1.0 m — Q-F's weld, priced by an instrument that was not widened.
4. `hard_conflict` rows are all sided AIRSIDE by the census; the stage's 89
   groundside-tier relaxations read as airside +89.
5. A sheet-free `--solved-out` pickle carries `hard_conflict` 0 while its
   sidecar publishes 264 (`gaps6/BASE`): a replay arm's sidecar lacks the
   base's records (the build carries them: 353).

## Next command

    cd Ortho4XP && F=/Users/noah/XPTerrainBuilderData/.harness/frames
    venv/bin/python tools/v2_solve_replay.py --replay $F/gaps3/HECA.pkl --from classify \
        --late-from $F/gaps6/BASE/solved.pkl --emit OUT --verify --solved-out OUT/solved.pkl   # 3.5 min
    venv/bin/python tools/v2_late_read.py $F/gaps6/BASE/solved.pkl OUT/solved.pkl --top 40
    venv/bin/python tools/harness/census.py $F/gaps6/BASE/HECA_auto.patch.osm OUT/HECA_auto.patch.osm
