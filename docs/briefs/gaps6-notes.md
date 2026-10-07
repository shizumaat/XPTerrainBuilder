# gaps6 notes — spec §55 (revised) built through S3 and run; STOPPED on three spec claims the replay refutes (2026-10-06 night)

Lane `gaps6`, branch `feature/pavement-gaps`. Frames (all under
`/Users/noah/XPTerrainBuilderData/.harness/frames/gaps6/`): `BASE/` (the
sheet-free replay of `gaps3/HECA_nosheet.pkl` RE-SOLVED on this tree, body
sha `09847984ac94` = main's HECA) and `ARM1/` (`--late-from BASE/solved.pkl`
through `pipeline/late_stage.run_late_stage`: the cut, the re-tier, the lot
rows). Scratch: `<scratch>/gaps6/` (`resolve.py`, the reads).

## Owner sites (ARM1 = the revised §55 as written, S2 + S3; NOT in a build)

| site | part | level | reading |
|---|---|---|---|
| #430 30.1154841, 31.4105884 | `gap:7/lot` | 97.46 (DEM 102.11; `route3` 97.05–97.16) | lot 0.00 m off `route3` at the rim; worst slope inside the lot 6.2 % (across section, s=+38); 3.5 % along the road's own |
| #292 30.1159784, 31.4106264 | `gap:7/ramp0` | 97.31 (DEM 101.86) | worst slope 8.0 % (s=+35), 5.0 % west–east; lot → ramp 0.06 m between two samples 1 m apart (continuous on the breakline); no knife in `gap:7` |
| #358 30.1193169, 31.4085087 | `gap:0/s4/lot` | 90.20 (DEM 96.94) | `building26` → piece 0.18 m (2 m apart); 5.4–5.5 % inside the part; 3.90 m to `building64` 19 m off across faceless ground (4.74 m at 17 m in gaps4's arm) |

The three sites read as 06d's picture. THE BARS DO NOT (below): the stage as
specified is worse than gaps4's arm on every stage bar but movers.

## Bars (0.02 m)

| bar | gaps4 arm (old rule, one face per piece) | S2 only (cut + re-tier, no lot rows; offline re-solve) | S2 less the fallback rows across knives (intervention) | ARM1 (S2 + S3 lot rows) |
|---|---|---|---|---|
| existing movers | 0 of 34,540 | 0 | 0 | 0 of 34,540 (worst 0.000 m) |
| foreign vertices | 0 | 0 | 0 | 0 |
| standing way groups identical | 1,152 / 1,152 | (not emitted) | (not emitted) | 1,152 of 1,152 (follower ribbons 18 of 76 identical; 96 groups only in the arm) |
| cut | — | 93 parts / 48 knives / 66 merged / 6 m² | same | same |
| LP relaxed rows | 207 | 235 | 186 | 691 |
| follow rows missed | 165 of 1,583 | 121 of 1,665 (merged 42, UNMERGED 79) | 102 (merged 37, UNMERGED 65: 10 over 1 m, 36 in 0.1–1 m, 15 under) | 303 (merged 50, UNMERGED 253) |
| lot rows missed | — | (not in the set) | — | 185 of 5,509 (worst 6.59 m) |
| stepping pairs | 68 of 147; 52 big | 80 of 202; 64 big | 79 of 202; 63 big | 98 of 202; 83 big |
| knives (part pairs within 1.0 m) | — | 46, worst rim-to-rim 5.70 m | 46, 5.72 m | 46, 7.94 m |
| ribbons grown > 0.1 m | 5 of 59 | 5 | 4 | 6 |
| shapes / gap joints (seam probe row 10) | — | 145 shapes; 48 gap joints (= the knives) + 132 contour joints (base: 52 shapes, 0 joints) | | |

(The pair population grew 147 → 202 because a ribbon beside no piece is now
a standing ring, as §55 (13) rules.)

By head, relaxed by the §5a LP (count, worst metre):

| head | S2 only | S2 less knife rows | ARM1 |
|---|---|---|---|
| `gap_piece follows …` | 109 (8.52) | 90 (8.52) | 297 (13.24) |
| `gap lot terrace holds the road's level across` | — | — | 196 (13.18) |
| `pavement_max_grade ceiling, last stage` | 73 (2.63) | 55 (3.47) | 128 (5.43) |
| `road_max_grade pavement fallback, last stage` | 17 (2.78) | 5 (0.12) | 20 (2.78) |
| `roads.groundside_road ramp ceiling` | 16 (9.52) | 16 (9.52) | 19 (9.52) |
| `pavement_max_grade ceiling` (a constant end) | 12 (1.14) | 12 (1.14) | 12 (1.14) |
| `road_cross_section` | 8 (0.14) | 8 (0.14) | 19 (0.20) |

## THE STOP — three claims of §55 the replay refutes

1. THE KNIFE IS A WELDED NEIGHBOUR OF ITSELF (§55 (2) 4, (6) rows 9 / 14).
   `constraints/pavement_cap.py` mints the 8 % fallback on EVERY two vertices
   of two different pavement faces within `WELD_M = 1.0` m, and the census
   copy (`check_grade.PAVCAP_WELD_M`) prices the same pairs. The knife is
   0.75 m: its two rims are welded neighbours — 111 hard rows of 0.06 m
   across the 48 knives. §55 names three inequalities for `knife_m`; this is
   a fourth, and it contradicts the third (a declared gap joint needs
   `< step_contact_tol_m` = 1.0; the fallback needs `>= 1.0`). INTERVENTION
   (offline re-solve of `ARM1/solved.pkl` with those 111 rows dropped,
   `resolve.py nolot+noknife`): relaxed 235 → 186, follow misses 121 → 102,
   the fallback head 17 (2.78 m) → 5 (0.12 m). A knife can carry its step
   only if the fallback (generator AND census copy) exempts a pair across a
   declared knife — "each exclusion a ruling" in that module's own words.
2. A PART'S RIM VERTEX BESIDE A KNIFE IS WITHIN REACH OF BOTH GROUPS
   (§55 (5) "by construction no longer in conflict"; (6) row 7). The follow
   reach is 1.95 m and the knife takes 0.375 m from each side, so the rim
   vertices of a part next to the knife's end are bound to the OTHER group's
   standing ring as well: `gap_follow_rows` binds every ring within reach,
   it does not know the part's stations. READ, not intervened: the arm still
   prints 27 vertices between two disagreeing neighbours (`building7` 100.38
   against `building6` 92.03, short by 8.33 m, is `gap:5/s2`'s 4.26 m miss on
   an UNMERGED station). The generator needs the part's own group.
3. SAME TIER DOES NOT MAKE THE CAP GIVE (§55 (5), ceiling row). The table
   says the two ceiling heads rank BELOW the follow and lot heads and then
   places them in the groundside tier beside them. Tiers price by tier
   (`hard_conflict_tier_ratio`), so inside one tier the LP minimises total
   slack and relaxes ONE follow row rather than several ceiling rows: with
   the knife rows gone, 36 follow misses of 0.1–1 m remain on unmerged
   stations — the floor's welds, taken at the neighbour instead of in the
   cap. "The road is met and the cap gives" needs a tier below groundside
   for the last-stage ceilings (a law-table change, `hard_conflict_tiers`).
4. THE LOT ROW AS WRITTEN FIGHTS THE FOLLOW ROWS (§55 (3) 4, S3). With the
   lot rows: 691 relaxed, 196 of them lot rows (worst 13.18 m), follow
   misses 303 (253 on unmerged stations). A `lot` part is whatever the ramp
   band leaves, including `gap:0/s0/lot` (556,533 m², 881 pad stations in
   the piece): every unknown vertex is held within 2 % × its distance of the
   NEAREST standing road's level, while its follow row holds it at a pad or
   apron the pair test allows to stand `0.08 d + 1.0` m from that road.
   The two are inconsistent wherever a non-road station sits outside the
   road's 2 % window; the pair test does not exclude it. Worst lot misses:
   `gap:8/s0/lot` against `route3` 6.59 m (the open interleave residual),
   `gap:0/s0/lot` against `dsf:objpav366` 6.05 m, `gap:0/s4/lot` against
   `small_roads:-18900` 3.67 m.

Also read: the remaining > 1 m unmerged misses after the knife intervention
are `gap:8/s0/lot | route3` 3.79 / 2.05 m (§55's named open residual, at the
held 3.91 m lead's point 30.1152588, 31.4106360 — the reader calls it
unmerged: no merged station of `route3` within reach + one spacing),
`gap:34 | pav39` 2.34 / 1.79 m (an uncut piece with follower
`small_roads:-18850`), `small_roads:-3927 | building133` 2.04 m (the ribbon
§55 expected the cut to cure).

## Questions for the spec author (yes / no)

* Q-D: exempt a pair across a declared knife from `road_max_grade pavement
  fallback` in the generator and in `check_grade`'s copy (as pad|pad and the
  #264 hillside terrace pairs are)? Recommend yes — it is the only way the
  0.75 m knife stands; it is a law exemption, so it needs its ruling.
* Q-E: should a part's vertex follow only the standing rings of ITS OWN
  level group (the cut hands `gap_follow_rows` the part's stations)?
  Recommend yes.
* Q-F: a sixth conflict tier under groundside for the last-stage ceilings,
  so the neighbour is met and the cap gives by ≤ the floor? Recommend yes;
  the alternative is to accept follow misses ≤ 1 m as the weld.
* Q-G: the lot row — restrict it to lot vertices with NO follow row of a
  non-road ring (or make it soft only, `lot_fit`), or cut the lot away from
  pads / aprons outside the road's window? No recommendation without a
  probe; as written it must not ship.

## State by step

| step | state |
|---|---|
| S1 | DONE `b0dce756`: `consistent(s, t, cap, floor)`, `level_groups(st, cap, floor)`, `Station.cap` = the piece's, `model.planar.gap_part_kind`; twins (i′), (ii′), (vii) (the frame twin pins 93 / 48 / 66 / 6 m² and the three sites; 74 s, skipped without frames). |
| S0 unfinished reads | NOT DONE (the per-row classing of gaps3/ARM's census deltas; `--why-vertex` on the §53 (16) vertices). The by-head table of the NEW arm is above. |
| S2 | DONE and RUN: base re-solved (`09847984ac94`); `--late-from` calls `run_late_stage` (the replay prelude's tail is `_rest(cl)`); a ribbon beside no piece is a ring (`gap_follow_rows`, `late_stations`); `late_constraints(retier_heads=)`; shapes admit gap parts by kind. Seam probe row 10: 48 gap joints = 48 knives; 132 contour joints appear (not attributed). Row 3 (`ribbon_airside_added / removed`, breakline vertex count) NOT read. |
| S3 | BUILT and RUN, REFUTED as written (claim 4): `gap_follow._lot_rows`, `LOT_RULING` in `hard_rulings` + ranks, `lot_fit` through `preferred_z` (the assembly labels it `road_fit`; no separate label). |
| S4 | PARTIAL: `ConflictReport.worst_by_head` + `by_head_line()` on a LAST STAGE line; `publication.gap_pieces` (sidecar key, written only by a build / replay that ran the stage); `tools/v2_late_read.py` part-aware (merged / UNMERGED naming, lot rows, knife column, pieces' area). `v2_late_site` unchanged (the ref names the part). No twin for the reader. |
| S5 | NOT OBTAINED: `tools/harness/census.py BASE ARM1` ran 30 min at 100 % of one core with no output and was stopped (gaps4's census of the one-face arm finished; the cut arm has 145 shapes and 180 joints against 52 and 0 — not attributed). |
| S6 | WRITTEN; NO-OP PROVED, the stage itself NEVER RUN IN A BUILD: `pipeline/build.py` builds the BASE on `gap_free(cl)` and calls `run_late_stage` once under `if cl_gaps is not None` (structural twin in `test_late_stage.py`); harness build `gaps6_CYXY` body `2a00c361ffc2` = main's. The base's pin yields and conflict records are carried; its jetway-strip report is NOT. |
| S7 – S9 | NOT STARTED. No HECA build. `--workers 1` identity not run. |

## Deviations (for review)

* The re-tiered head is spelled `<head>, last stage` (not ` (last stage)`):
  a head ends at the first parenthesis.
* S2 and S3 were run in ONE arm replay and separated afterwards by offline
  re-solves of its pickle (`<scratch>/gaps6/resolve.py`: 20 s each).
* `--solved-out` now carries `pin_yield`, `hard_conflict`, `late_cut`,
  `late_wall_s`; verify and emit of a late arm read the full map's WHOLE row
  set (`cs_full`), the pickle keeps the stage's own.

## Next command (after the rulings)

    cd Ortho4XP && F=/Users/noah/XPTerrainBuilderData/.harness/frames/gaps6
    venv/bin/python <scratch>/gaps6/resolve.py $F/ARM1/solved.pkl OUT.pkl <mode>   # 20 s per variant
    venv/bin/python tools/v2_late_read.py $F/BASE/solved.pkl OUT.pkl --top 60
    venv/bin/python tools/v2_solve_replay.py --replay $F/../gaps3/HECA.pkl --from classify \
        --late-from $F/BASE/solved.pkl --emit $F/ARM2 --verify --solved-out $F/ARM2/solved.pkl

## Handover checks (tip of the branch)

Non-Qt split 8,741 passed, 20 skipped, 1 xpassed, 1 failed (`test_planar::test_import_and_budget`:
`planar/shapes.py` 1,008 lines — fixed by moving `bears_shape` to
`model.planar`; the file is at 1,000, the twin's limit); Qt `-n0` 311 passed;
the four gate files pass; `tools/ratchets.py` duplicate PASS, layers PASS
(size WARN on files touched: `pipeline/build.py` +113, `pipeline/publication.py`
+21, `tools/v2_solve_replay.py` +247 — all three include earlier growth).
Frames registered: `gaps6/BASE` and `gaps6/ARM1` patches (`frames.py list HECA`).
