# Brief pack — lane `v2staged`

Base: main `a3185dbb` · generated 2026-09-14 by `tools/brief_pack.py`

Read THIS file first and whole. Do not grep the spec, RULINGS or INDEX monoliths for
what is here; use `tools/docq.py` for anything else you need.

## Task

THE STAGED SOLVE: airside first, then everything with airside fixed (RULINGS 13dh/14an) — on top of claude/v2padcluster

## The brief

THE STAGED SOLVE (RULINGS 13dh — "airside solves first, groundside conforms" — now ordered, 14an). Base: branch `claude/v2padcluster` @ a3185dbb (NOT main — the derived pads are the test; `git merge main` into your worktree first so you carry `479cd0dc`+). Site: `Ortho4XP/src/auto_patch_v2/solve/design.py` (`assemble`, `hard_rulings`, the lag rounds, `[design] one_way_rulings`) and `solve/api.py`; read `tools/docq.py spec '§20a'` (lag = convergence condition), `'§32 (4)'` (projection purity), `'§38'` (seam pins), `'§30 (4)'`, and `tools/docq.py ruling 13dh 13y 13ab 14al 14an`. Mechanism: (1) STAGE 1 — assemble and solve the AIRSIDE problem only: the vertices of airside faces (runway family, taxi family, apron; the existing role sets — `airside_no_step.taxiway_family_roles()` + runway + apron) and every row whose EVERY column is airside (hard rulings, seam pins §38, chords, crowns, within-shape, no-step, taxi_box, junction_mesh, transverse, apron tiers, EAT…); (2) STAGE 2 — assemble the full problem and BOUND every airside vertex to its stage-1 value ± `hard_tol_m` (or substitute it as a constant — choose the one that keeps HiGHS warm-startable and say why); rows coupling airside to pads / roads / groundside then have a constant on the airside side (one-way by construction — the `follows=` machinery and the lag are NOT needed for those rows; keep the lag for groundside-internal one-way rows); (3) the report clocks both stages and names the row counts per stage. Consumer census FIRST (30l): every consumer of the solved vertex map that assumes ONE solve (the design report, `--why-at`, `--why-hard`, `v2_solve_replay --capture/--replay`, `verify`, the census frame, `project.py`) — rule each in one table in a new §20b spec block (write the spec section yourself in the MEASURED style; Fable will ratify). Twins: a synthetic apron + pad + road: stage-2 airside values equal stage-1 to 1e-9; the pad meets the apron edge (weld) and the apron did not move; a hard airside row that stage 2 would have violated is impossible by construction. Bars (HECA, ONE build on the padcluster branch + staged, matched against `v2padclusterHECAdisarm` AND against the r5 shipped arm `a602bba1b858`): airside vertices moved vs DISARM = 0 (today 9,573; runway 885 worst 0.390 → 0); the terminal at 30.1279552, 31.403143 still on `building298` at 72.6 ± 0.02 (body within 0.02 of its pad); `pad_airside_weld` before → after (the pad now meets a FIXED airside — expect a drop from 29); `pad_cluster_mismatch` unchanged (14, not yours); the design report's settled/hard/lag lines; solve wall ≤ 1.5× the single solve (name both stages); CYXY (no pads of note) byte-identical or the diff named; suite twice. Then KCLT and SPJC ONE build each on the same tree (the KCLT terminal weld `building80` ↔ `pav14` and the SPJC viaduct 20.07 — read both). Files: `solve/design.py`, `solve/api.py`, `solve/design_report.py`, `pipeline/build.py` (the stage clocks), `tools/v2_solve_replay.py` (both stages replayable). NOT yours: `constraints/`, `airport/`, `planar/`, `classify/`, `emit/`.

## Bars

- HECA: airside vertices moved > 0.02 m vs DISARM = 0 (today 9,573; runway 885, worst 0.390 m) — by construction, and measured.
- The terminal body on `building298` at 72.6 ± 0.02; `pad_airside_weld` before → after; `pad_cluster_mismatch` unchanged at 14.
- Stage-2 airside values = stage-1 to 1e-9 (twin + the HECA build); every hard airside ruling settled (the report's hard line).
- Solve wall ≤ 1.5× the single solve (stage 1 + stage 2 named); constraints unchanged.
- CYXY byte-identical or the diff named; KCLT + SPJC one build each, the weld and the viaduct read.
- Suite twice; the §20b spec block with the consumer table.

## Files

Yours: `Ortho4XP/src/auto_patch_v2/solve/design.py`, `Ortho4XP/src/auto_patch_v2/solve/api.py`, `Ortho4XP/src/auto_patch_v2/solve/design_report.py`, `Ortho4XP/src/auto_patch_v2/pipeline/build.py`, `Ortho4XP/tools/v2_solve_replay.py`
Other lanes' (do not touch): `Ortho4XP/src/auto_patch_v2/constraints/`, `Ortho4XP/src/auto_patch_v2/airport/`, `Ortho4XP/src/auto_patch_v2/planar/`, `Ortho4XP/src/auto_patch_v2/emit/`

## Spec (design-surface) §32 (4)

### §32 (4) PURITY OF A POST-SOLVE PROJECTION; §20a THE LAG IS A CONVERGENCE CONDITION; §30 (3) THE PAD PLANE IS PROJECTED (Fable 2026-09-13; RULINGS 2026-09-13ac) — lane `v2settle`

Scout `v2unsettled2`: LEMD's hard set was never settled on merged main (12ac
read the lane tip); the merge's §28 rows (42 one-way rows in the pad columns)
leave a 2–3 cm shortfall of a coupled fixed point under a lag capped at three
rounds (`LAG NOT SETTLED` on every arm, 0.30–0.68 m leader motion) and a
polish that does not converge; and main's worst row (0.129 m at v8276/v8273,
`building` + `graded_strip`) is minted AFTER the solve by `project_zone_bands`
clamping a pad-rim vertex independently of its pad. Three laws, in order:

**§32 (4) PURITY.** A post-solve projection may clamp only a column that
carries NO hard row it does not own. `project_zone_bands` refuses a zone
vertex that also carries a pad-ceiling, pavement-ceiling or runway row and
leaves it to the solve (measured alone: main 0.1292 → 0.0271 m). The same
test guards every projection that follows.

**§20a THE LAG.** The one-way leader/follower fixed point iterates to
`one_way_tol_m` (0.01 m) or REPORTS the named failure — which rows, which
leader, its last move — BEFORE the augmented-Lagrangian polish;
`one_way_max_rounds` becomes a safety ceiling (≥ 20) whose hit is a named
failure, never a silent stop. Raising `polish_rounds_max` / `hard_weight`
is refuted (12u, 13ac: 8 rounds → 2 rows, still unsettled).

**§30 (3) THE PAD PLANE.** If (4) and §20a leave the pad ceiling unsettled,
each pad's rigid plane takes the runway's and the zone band's treatment: a
post-solve per-body QP on its free columns onto its own 1 % ceiling
(`project_runway` / `project_zone_bands` discipline), run after purity so no
two projections share a column; `HARD SET SETTLED` is then a re-read after
every projection, and the design report states it for MERGED MAIN.

Instrument: `v2_solve_replay.py --why-hard` (promoted from the scout's
`hardrows.py`: every violated hard row with its vertices, coordinates,
demanded vs allowed metres).

BARS: LEMD on a fresh main capture `HARD SET SETTLED` and `LAG SETTLED`
(today 5 rows / 0.129 m; lag 0.678 m), v8276/v8273 and v9295/v9696 at ≤
0.02 m; KCLT's three counters re-read on its capture (13ab: 644 rounds, 21
rows / 0.4144 m, lag 0.332 m) SETTLED or the failure named; solve wall not
worse than +10 % (`--runs 3`); runway and zone projections unchanged on pure
columns; suite twice; ONE LEMD build.

**MEASURED (lane `v2settle`, branch `claude/v2settle` off `6fe94558`).** ONE
fresh LEMD capture on merged main (`v2_solve_replay.py --capture LEMD`,
199 s, 23,191 vertices / 1,149 faces), four arms replayed off it, each law
measured ALONE and then combined. Every run `[guard] shared repo UNCHANGED`;
lane-local `O4_AIRPORT_MOD_CACHE_DIR` / `O4_DSF_CACHE_DIR`.

**THE CAPTURE REFUSED TO BE MADE FIRST — a main regression, fixed here.**
The first capture read `pack partition 95 s bodies 14,256 groups 0 relief 0
infeasible 0` against the scout's `groups 9,820 relief 5,036 infeasible
3,163`: the WHOLE PAD GROUP LAW was off at LEMD on merged main, silently,
exit 0. `airport/pack_partition._member_of` builds every pack member with a
POSITIONAL tail, and `5fc707eb` (§16e (2)) inserted `deck_end_stations` into
`model.rebake.Member` ahead of it, sliding `plate_y` onto the `()` meant for
`plate_stations`. `plate_y is not None` is `planar.group._eligible`'s FIRST
test, so all 14,256 bodies were refused — no groups, no relief bodies, no
pad rows to settle. It is the SECOND time an inserted field has shifted that
call (2026-09-11t's `plate_clearance_m`, whose warning comment sat two lines
above). Fixed by naming every field; `tests/auto_patch_v2/test_v2settle.py`
now asserts on the AST that the call passes no positional argument. Nothing
below could be measured until this landed, and it is not this spec's law:
it wants its own ruling.

| arm | hard rows violated / 127,380 | worst | lag | solve wall |
|---|---|---|---|---|
| A base (main + the fix) | 4 | **0.0985 m** | NOT SETTLED, 0.399 m in 3 rounds | 62.1 s |
| B §32 (4) purity ALONE | **3** | **0.0299 m** | NOT SETTLED, 0.399 m in 3 | 68.0 s |
| C §20a ceiling 20 ALONE | 25 | 0.1225 m | NOT SETTLED, 0.289 m in 20 | 118.2 s |
| D purity + ceiling 20 | 23 | 0.0324 m | NOT SETTLED, 0.289 m in 20 | 124.6 s |

**§32 (4) PURITY — LANDED.** Arm B against arm A: the worst hard row
0.0985 → 0.0299 m and the violated set 4 → 3, for exactly ONE column of
4,850 refused (`hard_columns 1`). The corridor's own reading is unchanged to
the digit — worst zone miss `8.1029 → 1.756762 m (owned 0.000000)` on BOTH
arms, 3,322 → 3,321 columns moved — so purity buys the hard set 0.069 m and
costs the zone law nothing. The row that goes is main's worst, the pad-slope
ceiling between the two rim vertices at 40.48527108321,−3.59323243501 /
40.48527109147,−3.59320294912 that the clamp had moved independently. This
matches the scout's `--design-weight zone_projection=0` control (3 rows /
0.0271 m) while keeping the projection ON, which the control could not.

**§20a — HALF LANDED, HALF REFUTED.** The NAMED FAILURE is landed
(`design_report.read_lag_failure` / `lag_failure_line`): the cap's hit now
reports which rows still move, the worst row's generator and ruling, its
LEADER vertex with the canonical lat/lon and that leader's last move, into
the design line and the sidecar — `LAG NOT SETTLED after 20 of 20 round(s):
1,132 of 13,932 one-way rows still move more than 0.01 m; worst 0.2890 m on
row … (pads: structures.building_pad frontage_level …), leader v… at …`.
THE ≥ 20 SAFETY CEILING IS REFUTED, in both combinations: the
leader/follower iteration does not contract at LEMD. Twenty rounds buy
0.110 m of leader motion (0.399 → 0.289 m, tol 0.01), take the violated hard
set from 4 to 25 rows (worst 0.0985 → 0.1225 m; with purity, 3 → 23 and
0.0299 → 0.0324) and cost +90 % of the solve against a +10 % bar. So
`one_way_max_rounds` stays 3 with the measurement recorded in
`law/emit.toml`, and `tests/auto_patch_v2/test_v2lag.py` pins the
refutation. THIS IS A DEVIATION FROM THE SPEC TEXT and is reported for the
Fable author's ruling, not decided in the lane.

**§30 (3) THE PAD PLANE — NOT BUILT, and it could not have reached the
bar.** Its condition is met (`pads` is still unsettled after (4)) but the
residual is under the convergence guard's materiality floor and the co-equal
residual is outside the pad plane's reach. What arm B leaves is three rows:
`pavement_ceiling` 0.0299 m at 40.45850655257,−3.56962843176 (apron|apron),
`pads` 0.0298 m at 40.49433943943,−3.59364375649 (building|building), and
`pavement_ceiling` 0.0200 m at the runway projection's own held bar. Over
`hard_tol_m` 0.02 that is 0.0099 / 0.0098 / 0.0000 m — the pad row is 0.0098
m over, BELOW the 0.01 m elevation materiality floor, and the pavement
ceiling beside it is the same size and is not a pad ceiling, so a per-body
pad QP would leave `HARD SET SETTLED` unreached anyway. Building a third
projection to move one row by 1 cm, when an equal row it cannot touch stays,
is the kind of mechanism the build economy refuses. Reported, not built.

**THE BARS.**

* `HARD SET SETTLED` at LEMD: **NOT MET** — 3 rows, worst 0.0299 m (from 4 /
  0.0985). The residual over the bar is 0.0099 m, under the materiality
  floor: PASS-with-residual, quoted for the owner's sign-off.
* `LAG SETTLED`: **NOT MET and refuted as reachable by the ceiling** — the
  failure is now NAMED instead of silent, which is the half that landed.
* v8276/v8273 (40.48527108321,−3.59323243501): **MET** — 0.0985 m → off the
  violated set entirely (≤ 0.02 m).
* v9295/v9696 (40.49615941816,−3.59037117965 / 40.49424548294,
  −3.59145556585): **MET on arm B** — neither carries a violated row after
  purity (both DO carry one on the refuted ceiling arms C/D, 0.0324 m).
* KCLT's three counters: **NOT MEASURED.** The capture refuses at load —
  the pack DSF `.anchor_bak` is newer than every cached text dump, and the
  only lawful cure is `build_airport.py --refresh-data airport_mod_cache`,
  which this lane's brief forbids. Same refusal `59a67dac` recorded.
* Solve wall +10 %: **MET.** The added work is one pass over the hard set
  inside the projection, and the projection's OWN instrumented wall reads it
  directly: 0.05 / 0.06 / 0.08 s base → 0.07 / 0.08 / 0.09 s with purity,
  +0.02 s on a ~60 s solve = **+0.03 %**. The whole-replay wall cannot
  resolve that: three runs a side, exclusive and foreground, read base 59.8
  / 63.0 / 82.0 s and purity 57.3 / 78.5 / 72.9 s — a ±37 % spread on
  IDENTICAL code (min 59.8 vs 57.3, median 63.0 vs 72.9).
* Runway and zone projections unchanged on pure columns: **MET.** Zone
  columns clamped 4,850 → 4,849 (the one refused column), moved 3,322 →
  3,321, worst zone miss and `owned` identical to six digits. The runway
  projection line is unchanged (24,642 hard rows, 2,827 free columns,
  0.0493 → 0.020000 m, 0.035 m max move) — purity does not touch it.
* Instrument: `v2_solve_replay.py --why-hard [N]` promoted with its
  `tools/INDEX.md` row and twins in `tests/auto_patch_v2/test_v2padceiling.py`.

**THE CLOSING BUILD** — `build_airport.py LEMD --engine v2 --tag v2settle`,
578.6 s, rc 0, `body_sha ccc706451007`, ledger `9b08303ac583`, `shared repo
UNCHANGED by this build (full-surface before/after snapshot)`, v2-verify
1,441 rows. The design report's three lines, verbatim:

    4/127380 hard rows violated (max violation 0.0299 m in 2 polish
    round(s), HARD SET NOT SETTLED)

    13932 one-way rows in 3 lag round(s) (worst leader move 0.399 m, LAG NOT
    SETTLED after 3 of 3 round(s): 2980 of 13932 one-way rows still move more
    than 0.01 m; worst 0.3988 m on row 910478 (rim_level:
    structures.structure_rim frontage_level (service_road; owner 2026-09-10an:
    the rim is flush with the pavement it sits in), leader v19987 at
    40.48346832042,-3.58072988310, v19988 at 40.48346831636,-3.58075347118,
    v19986 at 40.48343689447,-3.58018145109, v20001 at
    40.48349993554,-3.58016377812)

    zone projection (12ag): 10418 corridor rows over 4850 ground vertices,
    4849 columns clamped (0 impure, 1 carrying a foreign hard row, 0 fixed
    vertices, 3321 moved, 47 empty bands), worst zone miss 8.1029 ->
    1.756762 m (owned 0.000000), max move 8.103 m, 0.23 s (optimal)

The build's worst hard row is the replay's, to the digit: 0.0299 m, down
from main's 0.0985. The named lag failure earns its first keep immediately —
LEMD's worst leader is NOT a pad frontage row at all but a
`structures.structure_rim frontage_level` on a SERVICE ROAD at
40.48346832042,−3.58072988310, which `LAG NOT SETTLED` alone could never
have said. (The report counts 4 violated rows where `--why-hard` counts 3:
the third is the runway projection's row sitting EXACTLY on `hard_tol_m`
0.020000, and the two readers round it opposite ways. Cosmetic, named here
so nobody attributes it twice.)

### §32 (4) PURITY OF A POST-SOLVE PROJECTION; §20a THE LAG IS A CONVERGENCE CONDITION; §30 (3) THE PAD PLANE IS PROJECTED (Fable 2026-09-13; RULINGS 2026-09-13ac) — lane `v2settle`

Scout `v2unsettled2`: LEMD's hard set was never settled on merged main (12ac
read the lane tip); the merge's §28 rows (42 one-way rows in the pad columns)
leave a 2–3 cm shortfall of a coupled fixed point under a lag capped at three
rounds (`LAG NOT SETTLED` on every arm, 0.30–0.68 m leader motion) and a
polish that does not converge; and main's worst row (0.129 m at v8276/v8273,
`building` + `graded_strip`) is minted AFTER the solve by `project_zone_bands`
clamping a pad-rim vertex independently of its pad. Three laws, in order:

**§32 (4) PURITY.** A post-solve projection may clamp only a column that
carries NO hard row it does not own. `project_zone_bands` refuses a zone
vertex that also carries a pad-ceiling, pavement-ceiling or runway row and
leaves it to the solve (measured alone: main 0.1292 → 0.0271 m). The same
test guards every projection that follows.

**§20a THE LAG.** The one-way leader/follower fixed point iterates to
`one_way_tol_m` (0.01 m) or REPORTS the named failure — which rows, which
leader, its last move — BEFORE the augmented-Lagrangian polish;
`one_way_max_rounds` becomes a safety ceiling (≥ 20) whose hit is a named
failure, never a silent stop. Raising `polish_rounds_max` / `hard_weight`
is refuted (12u, 13ac: 8 rounds → 2 rows, still unsettled).

**§30 (3) THE PAD PLANE.** If (4) and §20a leave the pad ceiling unsettled,
each pad's rigid plane takes the runway's and the zone band's treatment: a
post-solve per-body QP on its free columns onto its own 1 % ceiling
(`project_runway` / `project_zone_bands` discipline), run after purity so no
two projections share a column; `HARD SET SETTLED` is then a re-read after
every projection, and the design report states it for MERGED MAIN.

Instrument: `v2_solve_replay.py --why-hard` (promoted from the scout's
`hardrows.py`: every violated hard row with its vertices, coordinates,
demanded vs allowed metres).

BARS: LEMD on a fresh main capture `HARD SET SETTLED` and `LAG SETTLED`
(today 5 rows / 0.129 m; lag 0.678 m), v8276/v8273 and v9295/v9696 at ≤
0.02 m; KCLT's three counters re-read on its capture (13ab: 644 rounds, 21
rows / 0.4144 m, lag 0.332 m) SETTLED or the failure named; solve wall not
worse than +10 % (`--runs 3`); runway and zone projections unchanged on pure
columns; suite twice; ONE LEMD build.

**MEASURED (lane `v2settle`, branch `claude/v2settle` off `6fe94558`).** ONE
fresh LEMD capture on merged main (`v2_solve_replay.py --capture LEMD`,
199 s, 23,191 vertices / 1,149 faces), four arms replayed off it, each law
measured ALONE and then combined. Every run `[guard] shared repo UNCHANGED`;
lane-local `O4_AIRPORT_MOD_CACHE_DIR` / `O4_DSF_CACHE_DIR`.

**THE CAPTURE REFUSED TO BE MADE FIRST — a main regression, fixed here.**
The first capture read `pack partition 95 s bodies 14,256 groups 0 relief 0
infeasible 0` against the scout's `groups 9,820 relief 5,036 infeasible
3,163`: the WHOLE PAD GROUP LAW was off at LEMD on merged main, silently,
exit 0. `airport/pack_partition._member_of` builds every pack member with a
POSITIONAL tail, and `5fc707eb` (§16e (2)) inserted `deck_end_stations` into
`model.rebake.Member` ahead of it, sliding `plate_y` onto the `()` meant for
`plate_stations`. `plate_y is not None` is `planar.group._eligible`'s FIRST
test, so all 14,256 bodies were refused — no groups, no relief bodies, no
pad rows to settle. It is the SECOND time an inserted field has shifted that
call (2026-09-11t's `plate_clearance_m`, whose warning comment sat two lines
above). Fixed by naming every field; `tests/auto_patch_v2/test_v2settle.py`
now asserts on the AST that the call passes no positional argument. Nothing
below could be measured until this landed, and it is not this spec's law:
it wants its own ruling.

| arm | hard rows violated / 127,380 | worst | lag | solve wall |
|---|---|---|---|---|
| A base (main + the fix) | 4 | **0.0985 m** | NOT SETTLED, 0.399 m in 3 rounds | 62.1 s |
| B §32 (4) purity ALONE | **3** | **0.0299 m** | NOT SETTLED, 0.399 m in 3 | 68.0 s |
| C §20a ceiling 20 ALONE | 25 | 0.1225 m | NOT SETTLED, 0.289 m in 20 | 118.2 s |
| D purity + ceiling 20 | 23 | 0.0324 m | NOT SETTLED, 0.289 m in 20 | 124.6 s |

**§32 (4) PURITY — LANDED.** Arm B against arm A: the worst hard row
0.0985 → 0.0299 m and the violated set 4 → 3, for exactly ONE column of
4,850 refused (`hard_columns 1`). The corridor's own reading is unchanged to
the digit — worst zone miss `8.1029 → 1.756762 m (owned 0.000000)` on BOTH
arms, 3,322 → 3,321 columns moved — so purity buys the hard set 0.069 m and
costs the zone law nothing. The row that goes is main's worst, the pad-slope
ceiling between the two rim vertices at 40.48527108321,−3.59323243501 /
40.48527109147,−3.59320294912 that the clamp had moved independently. This
matches the scout's `--design-weight zone_projection=0` control (3 rows /
0.0271 m) while keeping the projection ON, which the control could not.

**§20a — HALF LANDED, HALF REFUTED.** The NAMED FAILURE is landed
(`design_report.read_lag_failure` / `lag_failure_line`): the cap's hit now
reports which rows still move, the worst row's generator and ruling, its
LEADER vertex with the canonical lat/lon and that leader's last move, into
the design line and the sidecar — `LAG NOT SETTLED after 20 of 20 round(s):
1,132 of 13,932 one-way rows still move more than 0.01 m; worst 0.2890 m on
row … (pads: structures.building_pad frontage_level …), leader v… at …`.
THE ≥ 20 SAFETY CEILING IS REFUTED, in both combinations: the
leader/follower iteration does not contract at LEMD. Twenty rounds buy
0.110 m of leader motion (0.399 → 0.289 m, tol 0.01), take the violated hard
set from 4 to 25 rows (worst 0.0985 → 0.1225 m; with purity, 3 → 23 and
0.0299 → 0.0324) and cost +90 % of the solve against a +10 % bar. So
`one_way_max_rounds` stays 3 with the measurement recorded in
`law/emit.toml`, and `tests/auto_patch_v2/test_v2lag.py` pins the
refutation. THIS IS A DEVIATION FROM THE SPEC TEXT and is reported for the
Fable author's ruling, not decided in the lane.

**§30 (3) THE PAD PLANE — NOT BUILT, and it could not have reached the
bar.** Its condition is met (`pads` is still unsettled after (4)) but the
residual is under the convergence guard's materiality floor and the co-equal
residual is outside the pad plane's reach. What arm B leaves is three rows:
`pavement_ceiling` 0.0299 m at 40.45850655257,−3.56962843176 (apron|apron),
`pads` 0.0298 m at 40.49433943943,−3.59364375649 (building|building), and
`pavement_ceiling` 0.0200 m at the runway projection's own held bar. Over
`hard_tol_m` 0.02 that is 0.0099 / 0.0098 / 0.0000 m — the pad row is 0.0098
m over, BELOW the 0.01 m elevation materiality floor, and the pavement
ceiling beside it is the same size and is not a pad ceiling, so a per-body
pad QP would leave `HARD SET SETTLED` unreached anyway. Building a third
projection to move one row by 1 cm, when an equal row it cannot touch stays,
is the kind of mechanism the build economy refuses. Reported, not built.

**THE BARS.**

* `HARD SET SETTLED` at LEMD: **NOT MET** — 3 rows, worst 0.0299 m (from 4 /
  0.0985). The residual over the bar is 0.0099 m, under the materiality
  floor: PASS-with-residual, quoted for the owner's sign-off.
* `LAG SETTLED`: **NOT MET and refuted as reachable by the ceiling** — the
  failure is now NAMED instead of silent, which is the half that landed.
* v8276/v8273 (40.48527108321,−3.59323243501): **MET** — 0.0985 m → off the
  violated set entirely (≤ 0.02 m).
* v9295/v9696 (40.49615941816,−3.59037117965 / 40.49424548294,
  −3.59145556585): **MET on arm B** — neither carries a violated row after
  purity (both DO carry one on the refuted ceiling arms C/D, 0.0324 m).
* KCLT's three counters: **NOT MEASURED.** The capture refuses at load —
  the pack DSF `.anchor_bak` is newer than every cached text dump, and the
  only lawful cure is `build_airport.py --refresh-data airport_mod_cache`,
  which this lane's brief forbids. Same refusal `59a67dac` recorded.
* Solve wall +10 %: **MET.** The added work is one pass over the hard set
  inside the projection, and the projection's OWN instrumented wall reads it
  directly: 0.05 / 0.06 / 0.08 s base → 0.07 / 0.08 / 0.09 s with purity,
  +0.02 s on a ~60 s solve = **+0.03 %**. The whole-replay wall cannot
  resolve that: three runs a side, exclusive and foreground, read base 59.8
  / 63.0 / 82.0 s and purity 57.3 / 78.5 / 72.9 s — a ±37 % spread on
  IDENTICAL code (min 59.8 vs 57.3, median 63.0 vs 72.9).
* Runway and zone projections unchanged on pure columns: **MET.** Zone
  columns clamped 4,850 → 4,849 (the one refused column), moved 3,322 →
  3,321, worst zone miss and `owned` identical to six digits. The runway
  projection line is unchanged (24,642 hard rows, 2,827 free columns,
  0.0493 → 0.020000 m, 0.035 m max move) — purity does not touch it.
* Instrument: `v2_solve_replay.py --why-hard [N]` promoted with its
  `tools/INDEX.md` row and twins in `tests/auto_patch_v2/test_v2padceiling.py`.

**THE CLOSING BUILD** — `build_airport.py LEMD --engine v2 --tag v2settle`,
578.6 s, rc 0, `body_sha ccc706451007`, ledger `9b08303ac583`, `shared repo
UNCHANGED by this build (full-surface before/after snapshot)`, v2-verify
1,441 rows. The design report's three lines, verbatim:

    4/127380 hard rows violated (max violation 0.0299 m in 2 polish
    round(s), HARD SET NOT SETTLED)

    13932 one-way rows in 3 lag round(s) (worst leader move 0.399 m, LAG NOT
    SETTLED after 3 of 3 round(s): 2980 of 13932 one-way rows still move more
    than 0.01 m; worst 0.3988 m on row 910478 (rim_level:
    structures.structure_rim frontage_level (service_road; owner 2026-09-10an:
    the rim is flush with the pavement it sits in), leader v19987 at
    40.48346832042,-3.58072988310, v19988 at 40.48346831636,-3.58075347118,
    v19986 at 40.48343689447,-3.58018145109, v20001 at
    40.48349993554,-3.58016377812)

    zone projection (12ag): 10418 corridor rows over 4850 ground vertices,
    4849 columns clamped (0 impure, 1 carrying a foreign hard row, 0 fixed
    vertices, 3321 moved, 47 empty bands), worst zone miss 8.1029 ->
    1.756762 m (owned 0.000000), max move 8.103 m, 0.23 s (optimal)

The build's worst hard row is the replay's, to the digit: 0.0299 m, down
from main's 0.0985. The named lag failure earns its first keep immediately —
LEMD's worst leader is NOT a pad frontage row at all but a
`structures.structure_rim frontage_level` on a SERVICE ROAD at
40.48346832042,−3.58072988310, which `LAG NOT SETTLED` alone could never
have said. (The report counts 4 violated rows where `--why-hard` counts 3:
the third is the runway projection's row sitting EXACTLY on `hard_tol_m`
0.020000, and the two readers round it opposite ways. Cosmetic, named here
so nobody attributes it twice.)

## Spec (design-surface) §38

## §38 THE TILE SEAM IS A PIN (owner 2026-07-04 / 2026-07-24 / 2026-07-26 / RULINGS 2026-09-13ah; Fable 2026-09-13) — lane `v2seampin`

Owner (13ah): seam boundaries "must be kept at DEM and treated as an anchor
like CIFP thresholds that everything else grades to." `constraints/seams.py`
(M3a) minted the seam as a PREFERENCE (`Linear.soft`) after the SPLP class of
2026-09-04 (runway edge 55.51 m and strip vertex 57.00 m on one seam line);
a deviating vertex was reported as a "seam residual" and not published as a
pin. Overruled.

1. **A SEAM VERTEX IS A `Pin`** — the same object as a CIFP threshold: its
   value is its own tile's baked DEM sample (the value the neighbouring
   tile's mesh meets), its column is eliminated (`solve/rows._reduce`), it
   holds exactly, it is published in the sidecar as `seam_pins` and the
   census prices pin↔free pairs at the body cap. Every seam-band vertex of
   every role, the runway included.
2. **EVERYTHING GRADES TO THE SEAM.** Between two seam pins the pin↔pin
   row is exempt (terrain against terrain, `constraints.seam_exempt`); the
   free vertices between them take the hard family re-fitted between the
   pins — the runway chord between a threshold and a seam pin, or between
   two seam pins, exactly as §21.2 re-fits between thresholds. A family
   that cannot be met between two pins is NAMED in the design report (the
   two pins, the family, demanded vs allowed metres) — never a moved pin,
   never a silent residual, never a preference.
3. **NO BANK ALONG A SEAM.** The coverage edge at a tile seam is a pin line
   already at the DEM; §37 (3)'s bank is not derived there, and a bank
   chain crossing a seam line is a defect the census names
   (`bank_across_seam`).
4. **ONE AIRPORT, ONE SOLVE.** A seam-straddling airport is solved once on
   the whole map and written as per-tile pieces (§9.2 A5/C3); the two pieces
   share every seam vertex by identity (the 11-dp lat/lon join carries the
   node id), so the runway meets itself across the seam at the pin.

BARS (SPLP, both tiles, after scout `v2splpseam`'s attribution): every seam
vertex at its DEM sample (0 seam residuals); runway z on either side of the
seam identical at every shared vertex; no `bank_foot` chain within
`half_width_m` of the meridian; the texture tear at −12.1610968, −77.0000457
attributed (mesh side or patch side) and, if patch side, gone; cockpit block
on both pieces with no CRITICAL row on the seam; LEMD/KCLT/CYXY (single-tile)
byte-identical; the design report's settled lines; suite twice.

### §38 AMENDED after scout `v2splpseam` (Fable 2026-09-13; RULINGS 2026-09-13am) — lane `v2seampin`

Measured on SPLP (864e7577): one solve, per-tile pieces, 0 shared vertices
between the pieces (the west piece ends at −5.0 m, the east begins at +1.8 m;
the 10 m band is the mesh's draped DEM); seam pass oscillates 45 → 28 → 27 →
28 …, `27/150 vertices on the DEM; 123 residual, max 3.430 m` (a 3 m berm
10 m wide along the seam through the runway strip); runway band-edge vertices
+0.51 … +0.63 m above the DEM (the dip and rise the owner reads); the
relax arm names the graded-strip ZONE BAND as what holds the seam off its DEM;
`_Chord.knots` takes only crossing pins; bank chain −10045 has 2 nodes inside
the band; the coverage slit is closed only because `bank_min_width_m` ==
`seam.half_width_m` (5.0 == 5.0).

1. **(1) stands.** `constraints/seams.py` mints `Pin`; the seam pass in
   `pipeline/build.py` (598–660) is DELETED — a pin needs no pass. The
   sidecar publishes ALL seam pins (150 at SPLP, not the 27 honoured).
2. **(2) names its mechanism.** Between two seam pins the graded-strip zone
   band YIELDS (a soft escalation group, the `runway_profile` end-zone
   pattern); the runway chord takes seam pins as KNOTS in `_Chord.knots`
   exactly as `runway_crossing_pins` are taken, so the end-zone preference
   absorbs the curvature between a threshold and a seam pin. A family still
   unmet between two pins is NAMED (pins, family, demanded vs allowed).
3. **(3) at one derivation site.** `emit/bank.py` cuts the banked region by
   the seam bands beside the water and terrain-edge cuts, and unions the
   seam bands into the coverage EXPLICITLY before the collar; the equality
   of the two 5.0 m constants is no longer load-bearing.
4. **(4) REWRITTEN — ONE AIRPORT, ONE SOLVE, PER-TILE PIECES.** The band is
   draped DEM; the pins are the band-edge vertices at ±`half_width_m`, each
   at its own tile's DEM sample, so each piece meets the drape at zero step.
5. **NEW CENSUS FAMILIES** in `check_grade.LAW_FAMILIES` (twins in
   `test_harness.py`): `seam_residual` — every band-edge vertex against its
   own DEM sample (CRITICAL motion on runway/taxi roles, visual elsewhere);
   `bank_across_seam` — any bank foot node within `half_width_m`.

BARS (SPLP, one build, `--base-arm` 864e7577): `seam: 150/150 vertices on the
DEM` (0 residuals); runway band-edge vertices z−DEM ≤ 0.05 m (today +0.51 …
+0.63); vertex 1408 at 54.50 (today 51.07); no bank foot node within
`half_width_m` (today 2); `seam_residual` 0 and `bank_across_seam` 0 (both
> 0 on the base arm, proving the instruments); cockpit CRITICAL: no row on
the seam; solve settled lines quoted both arms; LEMD / KCLT / CYXY dry
replays byte-identical (no seam vertices); suite twice. The mesh-side
cluster (16,298 border nodes in 1.92 m at lat −12.1609306 on tile −13−077)
is scout `v2splpmesh`'s, not this lane's.

### §38 MEASURED (lane `v2seampin`, base b78f8f32, SPLP `--engine v2`)

**THE CONSUMER CENSUS FIRST** (owner 2026-08-30l). Every reader of the
seam region, ruled in one table before any consumer was edited:

| Reader | file:site | what it read | ruling |
|---|---|---|---|
| the band's DERIVATION | `planar/overlay.py:305 seam_bands` | buffers the sampled graticule line by `half_width_m` of FRAME metre | **CHANGED (13an b)**: each edge is its own polyline at the graticule value ± the DEGREES that measure `half_width_m` there; the band is the polygon between them. The single derivation site. |
| the band's faces | `planar/overlay.py:153/171` | faces inside a band are dropped (`dropped_seam_faces 34`) | unchanged |
| the band's VERTICES | `planar/build.py:314 _seam_vertices` | the band boundary's noded vertices → `PlanarMap.seam_vertices` | unchanged (150 → 149 under the symmetric band) |
| the band's GEOMETRY downstream | — | nothing carried it; `emit/bank.py` could not see it | **NEW**: `PlanarMap.seam_band_rings`, written by `planar/build.py` from `arr.seam_bands` — the record, so no consumer re-derives the graticule |
| the seam ROW | `constraints/seams.py seam_pins` | `Linear.soft` preference, one group per vertex | **CHANGED (1)**: `Pin` — column eliminated, held exactly |
| the pair exemption | `constraints/__init__.py seam_exempt` | dropped rows whose every vertex was an honoured seam pin; took a `honoured` set | **CHANGED**: no honoured set; adds the SENIOR-pin withdrawal (a CIFP threshold outranks the seam: 1 vertex at SPLP) and the (2) zone-band yield |
| the seam PASS | `pipeline/build.py:598-660`, `pipeline/why.py:90-101` | re-solved up to 6× to a fixed point of the honoured set | **DELETED** (oscillated 45 → 28 → 27 → 28 …; 12.0 s of a 24.0 s build) |
| `Config.seam_passes_max` | `pipeline/build.py:53` | the pass's cap | **DELETED** |
| the generator plumbing | `constraints.generate`, `pipeline/shapes.shape_constraints` | `seam_honoured` parameter | **DELETED**; replaced by `yielded_out` (the rows the seam made yield, for the report) |
| the SIDECAR | `pipeline/publication.py:160` | `seam_pins` = the HONOURED subset, `[lat, lon]` | **CHANGED (1)**: every pin, `[lat, lon, dem_z]`; new key `seam_half_width_m` |
| the sidecar KEY register | `emit/osm_adapter.py:77 SIDECAR_KEYS` | — | **NEW** `seam_half_width_m` |
| the census's seam read | `check_grade.py:723 _seam_nids_from_pins` | unpacked `(lat, lon)` | **CHANGED**: reads by position, so 2- and 3-element pins both work (a pre-§38 patch is unchanged) |
| the runway CHORD | `constraints/runway_chord.py:393-408 _Chord.knots` | crossing pins only; a seam vertex was never a control point | **CHANGED (2)**: `_with_seam_knots` adds this runway's own ridge seam pins as knots, at both chord sites |
| the graded-strip ZONE BAND | `constraints/zones.py:396 zone_bands` (one-way, `follows=v`) | with `v` pinned it survived as a two-way PULL on the pavement | **CHANGED (2)**: yields (the `water_exempt` clause) — 67 rows at SPLP |
| the design solve's law pricing | `solve/design.py:370-390` | a row footed on a fixed vertex is priced one-sided | unchanged |
| the ZONE PROJECTION | `solve/project.py:683 project_zone_bands` | clamps a governed vertex into its band | unchanged and now a no-op on seam pins: a pinned vertex carries no column, so it is never a "pure" column |
| the RUNWAY PROJECTION | `solve/project.py:412 coupled` | `n_free < n_all` over the REDUCED matrix — a fixed foot carries no column, so a row footed on two seam pins read self-contained | **CHANGED**: the coupling test reads the ROW'S OWN TERMS. Without it the QP and its relaxation LP are both **Infeasible** and the runway rows ship uncertified. |
| the BANK | `emit/bank.py:792` | closed the 10 m slit with `cov.buffer(bank_min_width_m)` — the 5.0 == 5.0 coincidence | **CHANGED (3)**: the derived pieces are cut by the band and the band is unioned into the coverage before the collar (`emit/seam_band.py`) |
| the bank's LAW constants | `emit.toml:445` / `:86` | independently typed, silently equal | **CHANGED (13an e)**: `law/model.py` refuses `bank_min_width_m < seam.half_width_m` by name at law load |
| `write_tile_pieces` | `emit/osm_adapter.py:317-358` | split breaklines by `floor(lon)` with no seam test | **CHANGED (13an c)**: refuses any breakline vertex inside the band |
| the CENSUS | `check_grade.LAW_FAMILIES` | no patch-edge-vs-DEM family; `strip_seam_tear` read 0 over a 3 m berm | **NEW**: `seam_residual` (cockpit `step`) and `bank_across_seam` (cockpit `keepout`) |

**THE ARMS** (each piece measured alone on SPLP before combining; base
served from the artifact ledger, `v2splpseam2` at 864e7577, body_sha
`f2e8a8226b18`).

| arm | seam on DEM | verify rows | hard set | runway projection | bank foot ≤ 5 m of the meridian |
|---|---|---|---|---|---|
| base b78f8f32 | 27/150, max 3.430 m | 239 | SETTLED 0/12498, max 0.0163 | held by the solve (0.0104) | **2** (closest 1.79 m) |
| (1) pins, pass deleted | **150/150, 0** | 320 | NOT SETTLED 2/12312, max 0.0358 | **Infeasible / relaxation LP Infeasible** | 2 |
| (2) + knots + zone yield | 150/150, 0 | 298 | NOT SETTLED 1/12312, max 0.0394 | optimal (elastic), family 0.0200 | 2 |
| (2) + the coupling fix | 150/150, 0 | **230** | NOT SETTLED 1/12312, max 0.0366 | optimal (elastic), family 0.0193 | 2 |
| (3) bank cut + union | 149/149, 0 | 226 | NOT SETTLED 1/12310, max 0.0363 | optimal (elastic), family 0.0154 | **0** (closest 12.09 m) |

Two attributions the arms bought:

* **the seam KNOTS are worth 68 census rows and half the lag.** With them
  off (diagnostic arm, everything else on): verify 298 vs 230,
  `airside_no_step` 81 vs 48, `within_shape` 144 vs 109, worst leader move
  0.190 vs 0.072 m (base 0.082). They cost fit to the CHANGED target:
  `target RMS` 0.304 → 0.366 m, because the target now passes through the
  seam pins and the K law will not follow a kink exactly. `|z − DEM|` mean
  improves 0.541 → 0.471 m.
* **`bank_min_width_m == seam.half_width_m` was load-bearing and is not
  now.** Unioning the WHOLE band into the coverage (the literal reading)
  extended the coverage a kilometre down the meridian and the collar
  followed it: foot distance mean 5.6 → 302.9 m, max 1042 m, 116 → 326
  foot nodes. The band is therefore clipped to the SLIT — intersected
  with the coverage grown by its own `half_width_m` — and the cut lands on
  the derived PIECES, never on the final banked region (differencing the
  band out after the collar re-opens the slit it exists to close).

**BARS.**

| bar | base | lane |
|---|---|---|
| `seam: N/N vertices on the DEM` | 27/150, 123 residual, max 3.430 m | **149/149, 0 residual** |
| runway band-edge vertices z − DEM | +0.51 … +0.63 m (vids 82/357/81/358) | **0.000** (a `Pin` holds exactly; `residual: pin 0.0000`) |
| vertex 1408 (−12.1664934, −76.9999539) | 51.07 vs DEM 54.50 | **at 54.50** (`seam_residual` 0) |
| bank foot within `half_width_m` | 2 (chain −10045/−10172, closest 1.79 m) | **0** (closest 12.09 m) |
| `seam_residual` | **106 rows, max 3.433 m** | **0** |
| `bank_across_seam` | **2 rows** | **0** |
| cockpit CRITICAL motion | **32** (31 of them `seam_residual [runway\|runway]`, worst 0.629 m at −12.1637725,−76.9999539) | **0** |
| cockpit CRITICAL visual | 0 | 0 |
| `HARD SET` | `SETTLED 0/12498 max 0.0163` | `NOT SETTLED 1/12310 max 0.0363` (the runway projection certifies the family at 0.0154 ≤ `hard_tol_m` 0.02) |
| `LAG` | `NOT SETTLED 0.082` | `NOT SETTLED 0.158` |
| runway 02/20 | `target RMS 0.0412 m, max 0.1506 m; bow −1.44 m` | `target RMS 0.367 m, max 0.794 m; bow −2.00 m` |
| build wall | 23.95 s (7 solve passes) | **9.31 s** |

The two arms' cockpit read is measured on the SAME instrument: the base
geometry priced against the published pins (`v2seampin-baseprobe`), since
the base build's own sidecar predates the key and declares no seam.

**§38 (2) NAMED, NOT SILENT.** 67 zone-band rows yield to a seam pin; 46
are still unmet at the solved surface, worst 3.609 m —
`zones.adjacent_ground` at pin 1408 (−12.1664934, −76.9999539): demanded
+2.502 m, allowed −2.183 … −1.107 m. That is §38 (2)'s "a family that
cannot be met between two pins is NAMED": the corridor between the runway
edge and the seam-pinned strip cannot be met with the pin held, so the
BAND yields and the report says by how much, per pin, every build.

**DEVIATIONS AND RESIDUALS, reported not decided.**

1. **§38 (2) says the zone band yields "as a soft escalation group".** The
   design solve has no slack machinery for a non-hard row — `soft` is read
   only for a row whose ruling head is in `[design] hard_rulings`
   (`solve/design.py:382`), and `zones.adjacent_ground` is not one. A
   `soft` group on that row is a NO-OP. What is implemented is the
   WITHDRAWAL the one-way law already implies (a row that governs a fixed
   vertex can only pull the pavement it was written to follow), reported
   per row with demanded-vs-allowed. Needs the spec author's ruling.
2. **13an (b)'s bar `coverage edges at ±5.000 ± 0.01 m` is not reached.**
   The tmerc round trip is REFUTED as the cause: a Newton correction
   against `to_ll(to_xy(·))` changed the emitted patch by nothing at all
   (`v2seampin-p3b` and `-p3c` are identical). What remains is the
   arrangement's own snap: `unary_union(..., grid_size=emit.identity.
   min_distinct_spacing_m = 0.5 m)` quantises every noded coordinate, so
   band-edge placement is quantised at 0.5 m and ±0.01 m is unreachable at
   this grid. Measured: base east edge +1.79 m (that node is the BANK FOOT
   in the crack), lane +5.016 / −4.973 m. The crack the bar exists to
   close is closed by the explicit coverage union instead.
3. **13an (d) — `seam_residual` comparing the two pieces' border
   POLYLINES — is NOT what landed.** A census reads a patch, and in the
   patch the two band edges are 10 m apart with draped DEM between: the
   west-edge-to-east-edge gap is real terrain and can never read zero. The
   family implemented is the spec's own §38 (5) wording — every band-edge
   vertex against its OWN published DEM sample — which is the same defect
   read where a patch can see it, and it zeroes. The polyline-vs-polyline
   read belongs to the mesh/DSF stage.
4. `LAG` worsens 0.082 → 0.158 m and the hard set stops settling (1 row of
   12,310 at 0.0363 m, certified back to 0.0154 m by the runway
   projection). 150 new hard equalities on the map's boundary is the
   cause; the residual is under the census's rounding envelope and mints
   no defect row.

**THE 13an ADDENDUM BARS.**

| bar (13an) | base | lane |
|---|---|---|
| (a) bank chain in the collar crack | chain −10172/−10045, closest node 1.79 m east of the meridian | none — closest bank foot 12.09 m; the band is unioned into the coverage and the pieces are cut by it |
| (b) coverage edges ±5.000 ± 0.01 m | +5.0228 / −4.9754 m | +5.016 / −4.973 m — **BAR MISSED**, attributed: the round trip is refuted (a Newton correction changed nothing), the residue is the arrangement's own 0.5 m snap grid (`emit.identity.min_distinct_spacing_m`) |
| (c) a breakline vertex inside the band in a tile piece | the chain, written verbatim into −13−077 | refused by `write_tile_pieces` |
| (d) the two edges' polylines, interpolated (patch side) | 72 stations, 39 gaps > 0.10 m, max 2.878 m, worst rolled-on 0.727 m | 70 stations, 25 > 0.10 m, **max 0.360 m**, worst rolled-on **0.251 m** — the residue is the DEM's OWN change across the 10 m draped band, which is why this reading is not the census family (see deviation 3) |
| (e) the two constants | silently equal | `law/model.py` refuses `bank_min_width_m < seam.half_width_m` by name; twin `test_v2bank.py::test_the_law_refuses_a_collar_that_cannot_reach_the_band` |
| the MESH, tile −13−077 (interventional) | 18,638 border nodes within 1 m of lon −77; 16,298 of them inside 1.92 m at lat −12.1609306 | **2,282** border nodes (bar ≤ 2,500); densest 1.92 m latitude window **3** |

The tile arm ran `build_airport.py SPLP --tile -13 -77 --engine v2` and the
harness REFUSED to report it: the engine's DEM prep tried to rewrite
`Elevation_data/-20-080/S13W077_airport_insets/index.json` and the
shared-repo guard blocked it (no `--refresh-data` was given and none was
wanted). The mesh it wrote is therefore a DEGRADED-frame reading and is
quoted as one. It is still decisive for this class: the 16,298-node fan
was a Triangle4XP segment-splitting degeneracy against a constrained
segment 2.37 cm from the unsplittable border, and the segment is gone —
no DEM frame puts it back.

## §38 THE TILE SEAM IS A PIN (owner 2026-07-04 / 2026-07-24 / 2026-07-26 / RULINGS 2026-09-13ah; Fable 2026-09-13) — lane `v2seampin`

Owner (13ah): seam boundaries "must be kept at DEM and treated as an anchor
like CIFP thresholds that everything else grades to." `constraints/seams.py`
(M3a) minted the seam as a PREFERENCE (`Linear.soft`) after the SPLP class of
2026-09-04 (runway edge 55.51 m and strip vertex 57.00 m on one seam line);
a deviating vertex was reported as a "seam residual" and not published as a
pin. Overruled.

1. **A SEAM VERTEX IS A `Pin`** — the same object as a CIFP threshold: its
   value is its own tile's baked DEM sample (the value the neighbouring
   tile's mesh meets), its column is eliminated (`solve/rows._reduce`), it
   holds exactly, it is published in the sidecar as `seam_pins` and the
   census prices pin↔free pairs at the body cap. Every seam-band vertex of
   every role, the runway included.
2. **EVERYTHING GRADES TO THE SEAM.** Between two seam pins the pin↔pin
   row is exempt (terrain against terrain, `constraints.seam_exempt`); the
   free vertices between them take the hard family re-fitted between the
   pins — the runway chord between a threshold and a seam pin, or between
   two seam pins, exactly as §21.2 re-fits between thresholds. A family
   that cannot be met between two pins is NAMED in the design report (the
   two pins, the family, demanded vs allowed metres) — never a moved pin,
   never a silent residual, never a preference.
3. **NO BANK ALONG A SEAM.** The coverage edge at a tile seam is a pin line
   already at the DEM; §37 (3)'s bank is not derived there, and a bank
   chain crossing a seam line is a defect the census names
   (`bank_across_seam`).
4. **ONE AIRPORT, ONE SOLVE.** A seam-straddling airport is solved once on
   the whole map and written as per-tile pieces (§9.2 A5/C3); the two pieces
   share every seam vertex by identity (the 11-dp lat/lon join carries the
   node id), so the runway meets itself across the seam at the pin.

BARS (SPLP, both tiles, after scout `v2splpseam`'s attribution): every seam
vertex at its DEM sample (0 seam residuals); runway z on either side of the
seam identical at every shared vertex; no `bank_foot` chain within
`half_width_m` of the meridian; the texture tear at −12.1610968, −77.0000457
attributed (mesh side or patch side) and, if patch side, gone; cockpit block
on both pieces with no CRITICAL row on the seam; LEMD/KCLT/CYXY (single-tile)
byte-identical; the design report's settled lines; suite twice.

### §38 AMENDED after scout `v2splpseam` (Fable 2026-09-13; RULINGS 2026-09-13am) — lane `v2seampin`

Measured on SPLP (864e7577): one solve, per-tile pieces, 0 shared vertices
between the pieces (the west piece ends at −5.0 m, the east begins at +1.8 m;
the 10 m band is the mesh's draped DEM); seam pass oscillates 45 → 28 → 27 →
28 …, `27/150 vertices on the DEM; 123 residual, max 3.430 m` (a 3 m berm
10 m wide along the seam through the runway strip); runway band-edge vertices
+0.51 … +0.63 m above the DEM (the dip and rise the owner reads); the
relax arm names the graded-strip ZONE BAND as what holds the seam off its DEM;
`_Chord.knots` takes only crossing pins; bank chain −10045 has 2 nodes inside
the band; the coverage slit is closed only because `bank_min_width_m` ==
`seam.half_width_m` (5.0 == 5.0).

1. **(1) stands.** `constraints/seams.py` mints `Pin`; the seam pass in
   `pipeline/build.py` (598–660) is DELETED — a pin needs no pass. The
   sidecar publishes ALL seam pins (150 at SPLP, not the 27 honoured).
2. **(2) names its mechanism.** Between two seam pins the graded-strip zone
   band YIELDS (a soft escalation group, the `runway_profile` end-zone
   pattern); the runway chord takes seam pins as KNOTS in `_Chord.knots`
   exactly as `runway_crossing_pins` are taken, so the end-zone preference
   absorbs the curvature between a threshold and a seam pin. A family still
   unmet between two pins is NAMED (pins, family, demanded vs allowed).
3. **(3) at one derivation site.** `emit/bank.py` cuts the banked region by
   the seam bands beside the water and terrain-edge cuts, and unions the
   seam bands into the coverage EXPLICITLY before the collar; the equality
   of the two 5.0 m constants is no longer load-bearing.
4. **(4) REWRITTEN — ONE AIRPORT, ONE SOLVE, PER-TILE PIECES.** The band is
   draped DEM; the pins are the band-edge vertices at ±`half_width_m`, each
   at its own tile's DEM sample, so each piece meets the drape at zero step.
5. **NEW CENSUS FAMILIES** in `check_grade.LAW_FAMILIES` (twins in
   `test_harness.py`): `seam_residual` — every band-edge vertex against its
   own DEM sample (CRITICAL motion on runway/taxi roles, visual elsewhere);
   `bank_across_seam` — any bank foot node within `half_width_m`.

BARS (SPLP, one build, `--base-arm` 864e7577): `seam: 150/150 vertices on the
DEM` (0 residuals); runway band-edge vertices z−DEM ≤ 0.05 m (today +0.51 …
+0.63); vertex 1408 at 54.50 (today 51.07); no bank foot node within
`half_width_m` (today 2); `seam_residual` 0 and `bank_across_seam` 0 (both
> 0 on the base arm, proving the instruments); cockpit CRITICAL: no row on
the seam; solve settled lines quoted both arms; LEMD / KCLT / CYXY dry
replays byte-identical (no seam vertices); suite twice. The mesh-side
cluster (16,298 border nodes in 1.92 m at lat −12.1609306 on tile −13−077)
is scout `v2splpmesh`'s, not this lane's.

### §38 MEASURED (lane `v2seampin`, base b78f8f32, SPLP `--engine v2`)

**THE CONSUMER CENSUS FIRST** (owner 2026-08-30l). Every reader of the
seam region, ruled in one table before any consumer was edited:

| Reader | file:site | what it read | ruling |
|---|---|---|---|
| the band's DERIVATION | `planar/overlay.py:305 seam_bands` | buffers the sampled graticule line by `half_width_m` of FRAME metre | **CHANGED (13an b)**: each edge is its own polyline at the graticule value ± the DEGREES that measure `half_width_m` there; the band is the polygon between them. The single derivation site. |
| the band's faces | `planar/overlay.py:153/171` | faces inside a band are dropped (`dropped_seam_faces 34`) | unchanged |
| the band's VERTICES | `planar/build.py:314 _seam_vertices` | the band boundary's noded vertices → `PlanarMap.seam_vertices` | unchanged (150 → 149 under the symmetric band) |
| the band's GEOMETRY downstream | — | nothing carried it; `emit/bank.py` could not see it | **NEW**: `PlanarMap.seam_band_rings`, written by `planar/build.py` from `arr.seam_bands` — the record, so no consumer re-derives the graticule |
| the seam ROW | `constraints/seams.py seam_pins` | `Linear.soft` preference, one group per vertex | **CHANGED (1)**: `Pin` — column eliminated, held exactly |
| the pair exemption | `constraints/__init__.py seam_exempt` | dropped rows whose every vertex was an honoured seam pin; took a `honoured` set | **CHANGED**: no honoured set; adds the SENIOR-pin withdrawal (a CIFP threshold outranks the seam: 1 vertex at SPLP) and the (2) zone-band yield |
| the seam PASS | `pipeline/build.py:598-660`, `pipeline/why.py:90-101` | re-solved up to 6× to a fixed point of the honoured set | **DELETED** (oscillated 45 → 28 → 27 → 28 …; 12.0 s of a 24.0 s build) |
| `Config.seam_passes_max` | `pipeline/build.py:53` | the pass's cap | **DELETED** |
| the generator plumbing | `constraints.generate`, `pipeline/shapes.shape_constraints` | `seam_honoured` parameter | **DELETED**; replaced by `yielded_out` (the rows the seam made yield, for the report) |
| the SIDECAR | `pipeline/publication.py:160` | `seam_pins` = the HONOURED subset, `[lat, lon]` | **CHANGED (1)**: every pin, `[lat, lon, dem_z]`; new key `seam_half_width_m` |
| the sidecar KEY register | `emit/osm_adapter.py:77 SIDECAR_KEYS` | — | **NEW** `seam_half_width_m` |
| the census's seam read | `check_grade.py:723 _seam_nids_from_pins` | unpacked `(lat, lon)` | **CHANGED**: reads by position, so 2- and 3-element pins both work (a pre-§38 patch is unchanged) |
| the runway CHORD | `constraints/runway_chord.py:393-408 _Chord.knots` | crossing pins only; a seam vertex was never a control point | **CHANGED (2)**: `_with_seam_knots` adds this runway's own ridge seam pins as knots, at both chord sites |
| the graded-strip ZONE BAND | `constraints/zones.py:396 zone_bands` (one-way, `follows=v`) | with `v` pinned it survived as a two-way PULL on the pavement | **CHANGED (2)**: yields (the `water_exempt` clause) — 67 rows at SPLP |
| the design solve's law pricing | `solve/design.py:370-390` | a row footed on a fixed vertex is priced one-sided | unchanged |
| the ZONE PROJECTION | `solve/project.py:683 project_zone_bands` | clamps a governed vertex into its band | unchanged and now a no-op on seam pins: a pinned vertex carries no column, so it is never a "pure" column |
| the RUNWAY PROJECTION | `solve/project.py:412 coupled` | `n_free < n_all` over the REDUCED matrix — a fixed foot carries no column, so a row footed on two seam pins read self-contained | **CHANGED**: the coupling test reads the ROW'S OWN TERMS. Without it the QP and its relaxation LP are both **Infeasible** and the runway rows ship uncertified. |
| the BANK | `emit/bank.py:792` | closed the 10 m slit with `cov.buffer(bank_min_width_m)` — the 5.0 == 5.0 coincidence | **CHANGED (3)**: the derived pieces are cut by the band and the band is unioned into the coverage before the collar (`emit/seam_band.py`) |
| the bank's LAW constants | `emit.toml:445` / `:86` | independently typed, silently equal | **CHANGED (13an e)**: `law/model.py` refuses `bank_min_width_m < seam.half_width_m` by name at law load |
| `write_tile_pieces` | `emit/osm_adapter.py:317-358` | split breaklines by `floor(lon)` with no seam test | **CHANGED (13an c)**: refuses any breakline vertex inside the band |
| the CENSUS | `check_grade.LAW_FAMILIES` | no patch-edge-vs-DEM family; `strip_seam_tear` read 0 over a 3 m berm | **NEW**: `seam_residual` (cockpit `step`) and `bank_across_seam` (cockpit `keepout`) |

**THE ARMS** (each piece measured alone on SPLP before combining; base
served from the artifact ledger, `v2splpseam2` at 864e7577, body_sha
`f2e8a8226b18`).

| arm | seam on DEM | verify rows | hard set | runway projection | bank foot ≤ 5 m of the meridian |
|---|---|---|---|---|---|
| base b78f8f32 | 27/150, max 3.430 m | 239 | SETTLED 0/12498, max 0.0163 | held by the solve (0.0104) | **2** (closest 1.79 m) |
| (1) pins, pass deleted | **150/150, 0** | 320 | NOT SETTLED 2/12312, max 0.0358 | **Infeasible / relaxation LP Infeasible** | 2 |
| (2) + knots + zone yield | 150/150, 0 | 298 | NOT SETTLED 1/12312, max 0.0394 | optimal (elastic), family 0.0200 | 2 |
| (2) + the coupling fix | 150/150, 0 | **230** | NOT SETTLED 1/12312, max 0.0366 | optimal (elastic), family 0.0193 | 2 |
| (3) bank cut + union | 149/149, 0 | 226 | NOT SETTLED 1/12310, max 0.0363 | optimal (elastic), family 0.0154 | **0** (closest 12.09 m) |

Two attributions the arms bought:

* **the seam KNOTS are worth 68 census rows and half the lag.** With them
  off (diagnostic arm, everything else on): verify 298 vs 230,
  `airside_no_step` 81 vs 48, `within_shape` 144 vs 109, worst leader move
  0.190 vs 0.072 m (base 0.082). They cost fit to the CHANGED target:
  `target RMS` 0.304 → 0.366 m, because the target now passes through the
  seam pins and the K law will not follow a kink exactly. `|z − DEM|` mean
  improves 0.541 → 0.471 m.
* **`bank_min_width_m == seam.half_width_m` was load-bearing and is not
  now.** Unioning the WHOLE band into the coverage (the literal reading)
  extended the coverage a kilometre down the meridian and the collar
  followed it: foot distance mean 5.6 → 302.9 m, max 1042 m, 116 → 326
  foot nodes. The band is therefore clipped to the SLIT — intersected
  with the coverage grown by its own `half_width_m` — and the cut lands on
  the derived PIECES, never on the final banked region (differencing the
  band out after the collar re-opens the slit it exists to close).

**BARS.**

| bar | base | lane |
|---|---|---|
| `seam: N/N vertices on the DEM` | 27/150, 123 residual, max 3.430 m | **149/149, 0 residual** |
| runway band-edge vertices z − DEM | +0.51 … +0.63 m (vids 82/357/81/358) | **0.000** (a `Pin` holds exactly; `residual: pin 0.0000`) |
| vertex 1408 (−12.1664934, −76.9999539) | 51.07 vs DEM 54.50 | **at 54.50** (`seam_residual` 0) |
| bank foot within `half_width_m` | 2 (chain −10045/−10172, closest 1.79 m) | **0** (closest 12.09 m) |
| `seam_residual` | **106 rows, max 3.433 m** | **0** |
| `bank_across_seam` | **2 rows** | **0** |
| cockpit CRITICAL motion | **32** (31 of them `seam_residual [runway\|runway]`, worst 0.629 m at −12.1637725,−76.9999539) | **0** |
| cockpit CRITICAL visual | 0 | 0 |
| `HARD SET` | `SETTLED 0/12498 max 0.0163` | `NOT SETTLED 1/12310 max 0.0363` (the runway projection certifies the family at 0.0154 ≤ `hard_tol_m` 0.02) |
| `LAG` | `NOT SETTLED 0.082` | `NOT SETTLED 0.158` |
| runway 02/20 | `target RMS 0.0412 m, max 0.1506 m; bow −1.44 m` | `target RMS 0.367 m, max 0.794 m; bow −2.00 m` |
| build wall | 23.95 s (7 solve passes) | **9.31 s** |

The two arms' cockpit read is measured on the SAME instrument: the base
geometry priced against the published pins (`v2seampin-baseprobe`), since
the base build's own sidecar predates the key and declares no seam.

**§38 (2) NAMED, NOT SILENT.** 67 zone-band rows yield to a seam pin; 46
are still unmet at the solved surface, worst 3.609 m —
`zones.adjacent_ground` at pin 1408 (−12.1664934, −76.9999539): demanded
+2.502 m, allowed −2.183 … −1.107 m. That is §38 (2)'s "a family that
cannot be met between two pins is NAMED": the corridor between the runway
edge and the seam-pinned strip cannot be met with the pin held, so the
BAND yields and the report says by how much, per pin, every build.

**DEVIATIONS AND RESIDUALS, reported not decided.**

1. **§38 (2) says the zone band yields "as a soft escalation group".** The
   design solve has no slack machinery for a non-hard row — `soft` is read
   only for a row whose ruling head is in `[design] hard_rulings`
   (`solve/design.py:382`), and `zones.adjacent_ground` is not one. A
   `soft` group on that row is a NO-OP. What is implemented is the
   WITHDRAWAL the one-way law already implies (a row that governs a fixed
   vertex can only pull the pavement it was written to follow), reported
   per row with demanded-vs-allowed. Needs the spec author's ruling.
2. **13an (b)'s bar `coverage edges at ±5.000 ± 0.01 m` is not reached.**
   The tmerc round trip is REFUTED as the cause: a Newton correction
   against `to_ll(to_xy(·))` changed the emitted patch by nothing at all
   (`v2seampin-p3b` and `-p3c` are identical). What remains is the
   arrangement's own snap: `unary_union(..., grid_size=emit.identity.
   min_distinct_spacing_m = 0.5 m)` quantises every noded coordinate, so
   band-edge placement is quantised at 0.5 m and ±0.01 m is unreachable at
   this grid. Measured: base east edge +1.79 m (that node is the BANK FOOT
   in the crack), lane +5.016 / −4.973 m. The crack the bar exists to
   close is closed by the explicit coverage union instead.
3. **13an (d) — `seam_residual` comparing the two pieces' border
   POLYLINES — is NOT what landed.** A census reads a patch, and in the
   patch the two band edges are 10 m apart with draped DEM between: the
   west-edge-to-east-edge gap is real terrain and can never read zero. The
   family implemented is the spec's own §38 (5) wording — every band-edge
   vertex against its OWN published DEM sample — which is the same defect
   read where a patch can see it, and it zeroes. The polyline-vs-polyline
   read belongs to the mesh/DSF stage.
4. `LAG` worsens 0.082 → 0.158 m and the hard set stops settling (1 row of
   12,310 at 0.0363 m, certified back to 0.0154 m by the runway
   projection). 150 new hard equalities on the map's boundary is the
   cause; the residual is under the census's rounding envelope and mints
   no defect row.

**THE 13an ADDENDUM BARS.**

| bar (13an) | base | lane |
|---|---|---|
| (a) bank chain in the collar crack | chain −10172/−10045, closest node 1.79 m east of the meridian | none — closest bank foot 12.09 m; the band is unioned into the coverage and the pieces are cut by it |
| (b) coverage edges ±5.000 ± 0.01 m | +5.0228 / −4.9754 m | +5.016 / −4.973 m — **BAR MISSED**, attributed: the round trip is refuted (a Newton correction changed nothing), the residue is the arrangement's own 0.5 m snap grid (`emit.identity.min_distinct_spacing_m`) |
| (c) a breakline vertex inside the band in a tile piece | the chain, written verbatim into −13−077 | refused by `write_tile_pieces` |
| (d) the two edges' polylines, interpolated (patch side) | 72 stations, 39 gaps > 0.10 m, max 2.878 m, worst rolled-on 0.727 m | 70 stations, 25 > 0.10 m, **max 0.360 m**, worst rolled-on **0.251 m** — the residue is the DEM's OWN change across the 10 m draped band, which is why this reading is not the census family (see deviation 3) |
| (e) the two constants | silently equal | `law/model.py` refuses `bank_min_width_m < seam.half_width_m` by name; twin `test_v2bank.py::test_the_law_refuses_a_collar_that_cannot_reach_the_band` |
| the MESH, tile −13−077 (interventional) | 18,638 border nodes within 1 m of lon −77; 16,298 of them inside 1.92 m at lat −12.1609306 | **2,282** border nodes (bar ≤ 2,500); densest 1.92 m latitude window **3** |

The tile arm ran `build_airport.py SPLP --tile -13 -77 --engine v2` and the
harness REFUSED to report it: the engine's DEM prep tried to rewrite
`Elevation_data/-20-080/S13W077_airport_insets/index.json` and the
shared-repo guard blocked it (no `--refresh-data` was given and none was
wanted). The mesh it wrote is therefore a DEGRADED-frame reading and is
quoted as one. It is still decisive for this class: the 16,298-node fan
was a Triangle4XP segment-splitting degeneracy against a constrained
segment 2.37 cm from the unsplittable border, and the segment is gone —
no DEM frame puts it back.

## RULINGS

## 2026-09-14an v2padcluster round 5 STOPPED (not merged): the one-way skirt refuted a third time — a pad bound to airside only by LAGGED rows is not stable inside a round; the staged solve (13dh) is the mechanism — lane `v2staged`

Lane `v2padcluster` @ a3185dbb (three HECA arms vs DISARM; shipped
arm `pad_skirt_m = 0`, ledger a602bba1b858; suite 1,476 twice). The
rigid core stops the collapse but a one-way-bound pad still drifts
(§28's own frontage row moved it 0.12 m; CYXY `mid_edge_step` census
77 vs verify 14 — lag residuals the two readers do not share); the 25
m band is WORSE on every airside bar (runway 1,021 → 1,394); what
helps is withdrawing the two-sided ceiling row over a pair of two
airside-shared vertices (4,008 dropped): airside 10,048 → 9,573
moved, runway 1,021 → 885, worst 0.410 → 0.390; the terminal on
`building298` at 72.60 (+0.07); `pad_cluster_mismatch` 14 = ONE
class (the cluster piece and the emitted pad ref cut in different
places — `geom.cluster_outlines` vs `classify/evidence._pads`'s
re-cut and the fallback footprints; fix = mint a cluster piece as ONE
part, absorb a fallback footprint inside it); constraints +31 % (the
pad population, not the skirt); 30 pads wholly in the band.

* RULING: the mechanism "airside is king" needs is the STAGED SOLVE
  (13dh, owed since): stage 1 solves the AIRSIDE families alone
  (runway, taxi, apron and the rows among them, hard rulings, the
  seam pins); stage 2 solves everything with every airside vertex
  BOUNDED to its stage-1 value ± `hard_tol_m`; rows that couple
  airside to pads / roads / groundside become one-way by construction
  (the airside side is a constant). No lag, no one-way skirt: the pad
  meets the airside because the airside is fixed. Lane `v2staged`
  (fresh context) on top of `claude/v2padcluster` (a3185dbb) so the
  derived pads are the test: HECA airside moved vs DISARM's airside
  = 0 by construction (measure it), the terminal on its pad, runway 0;
  cost named (two LPs; stage 1 is a subset — expected < 1.5× solve).
* `v2padcluster` r5 stands as the branch to merge WITH the staged
  solve; KCLT/SPJC re-reads owed at that tree; the 14-row mismatch
  class named for the round after.

## 2026-09-14al v2padcluster round 4 STOPPED (not merged): the terminal is on its pad (72.60, body +0.08), the runway's worst pull 3.14 → 0.41 m, but 14,263 airside vertices still move (worst 4.55) — the skirt is two-sided; ruled: rigid core + one-way skirt band; round 5

Lane `v2padcluster` @ 16da0f22 (HECA `v2padclusterHECA5` ledger
85c18b3071e6; KCLT `v2padclusterKCLT4` ledger dca6d7449633; SPJC
`v2padclusterSPJC4`; suite 1,474 twice). (7): 359,152 m² in 1,518
leaf pads + 175,708 m² walled-under-threshold removed (39 % of the
pad area beside the apron); emitted pad area 1.21 → 1.09 M m². Bars:
terminal SURFACE 72.60 (bar 72.50, DISARM 72.07) — MET; the body
`T3_concrete_white b4` on walled cluster pad `building298` via
`fu:38:96@cluster_pad` (18 members), own ground +0.08; the pad +0.55 m
fill vs the DISARM ground; `T3_38 b1` (building 160) −6.70 → +0.04,
`b3` (147) −2.45 → −0.33, `b4` (170) −0.02 both arms — the other four
of the seven not readable by body index (indices renumber under the
cut). Airside moved 14,263 / 29,783 (worst 4.55; runway 1,021, worst
0.41); `pad_cluster_mismatch` 14; `pad_airside_weld` 16 (worst
1.135); constraints +15.7 % (the pad population, `pad_flats` 10.6 →
2.5 s). (8)'s whole-plate one-way form REFUTED (the plate has no
rigid relation in the first lag round — the §30 twin's pad collapsed
703.56 → 640.89); what shipped is the airside-sharing pair priced at
the pad's slope CEILING (8,967 skirt rows, two-sided) — that alone
took the runway's worst 3.14 → 0.41. Twins re-founded and named; the
weld family re-read at "within the pad's own slope cap". KCLT: the
terminal pad 221.46 → 220.93 IS the weld (743 nodes shared with
`pav14`, step 0 by construction, spread = the apron's fall) — the
owner's KCLT read is the acceptance. SPJC with heights: the viaduct
`xp11_007__b0` on pad `building7` at 20.07 in a 6-member unit (13df:
19.56 in the 24-member unit) — the owner's SPJC read.

* RULING §16g (10) (8) refined — RIGID CORE + ONE-WAY SKIRT: the pad's
  non-airside vertices form a cap-0 rigid core (the plate keeps a
  rigid relation); only the SKIRT BAND — vertices within
  `pad_skirt_m` (25 m) of an airside-sharing edge — follows the
  airside ONE-WAY (airside leads, never pulled) within the pad slope
  ceiling; beyond the band the pad is flat. The two-sided ceiling row
  is withdrawn (it is what still pulls 14,263 airside vertices).
* Round 5: the rigid-core/one-way-skirt form; bars: airside moved 0
  (the runway 0.41 → 0); the terminal stays at its pad; `pad_airside_
  weld` → 0 or named; `pad_cluster_mismatch` 14 attributed; constraints
  ≤ +20 % accepted (the population); KCLT/SPJC re-read on the same
  frames.

## 2026-09-13dh v2roadcontact round 2: no groundside row binds an airside column (met, twinned); the objective residual accepted; closing build ordered before merge

Lane `v2roadcontact` @ 9eaebbf8 (main 38dd98be). Matched replay pair,
both arms at 38dd98be: ADJUDICATED airside 12,052 → 12,088 (+36),
groundside 322 → 280, `road_cross_section` 40 → 30, `transverse` 777 →
744; `route0` end +1.460 → +0.054 m; item-4 pair 1.30 → 0.04 m (1.3 %).
KCLT (pair at a621b491): airside +71 (r1 +132), groundside 1,549 → 1,470,
`road_cross_section` 373 → 304. Disarm arm byte-identical to base (md5
210dfeb0…). The worst airside mover (0.610 m, apron at 30.1014237,
31.3933314) is bound by NO row — the objective holds it; each law key
moves airside alone in different places; +36 vs +1 for the same code on
two bases; KCLT's own lag is unsettled at 0.24–0.32 m (13y (B)/13ab), three
times the bar.

* Mechanism closed: 8 of the 24 newly priced pairs came from the route
  MERGE (not the ribbon rule) and touched airside — `road_route_merged`
  published; a pair on a fused route or across the ribbon that touches a
  mouth is minted one-way on the road vertex (`RIBBON_RULING`,
  `[design] one_way_rulings`, never hard); a cross-ribbon pair with both
  vertices airside is not minted; the §37 (6) target governs road-owned
  vertices only (544 targets / 66 withdrawn, 0 airside).
* RULING: "airside is king" for a road law = no groundside row binds an
  airside column — MET. Surface invariance under a groundside change is
  the STAGED SOLVE ("airside solves first, groundside conforms"), an
  architecture item owed to the campaign, not this lane. +36/+71 accepted
  and quoted.
* ONE closing HECA build ordered on 9eaebbf8 (the one-way change was
  never built); merge after.

## 2026-09-13y — v2roadcap MERGED (eae16d6f, lane b935c72a): §37 with its consumer census §37.1 (17 rows contiguity cap, 3 `airside_edge_flip`, 11 bank — two rows changed the plan: `constraints/taxi.triangle_planes` is isotropic so the contiguity min is DROPPED not moved; `O4_Mesh_Utils._bank_rings_from_patches` reads CLOSED ways only, so open chains are closed into their ribbon and an implausible closure is refused into the harmonic extension). (1) a strict relaxation by construction (`min(transverse, min(long, cap)) == min(transverse, long, cap)`; 62 generator row counts identical line for line); (2) flips by share: LEMD 1,075 role faces 0 changed, CYXY one road back groundside; (3) the bank where load-bearing: LEMD foot nodes 2,594 → 836 (48 rings → 78 chains), 60,986 → 11,544 m, chords > 30 m 820 → 0, duplicates 5 → 0 (the padding-overlap defect the lane introduced, caught and twinned — `material_runs` folds the padding into membership); CYXY bank 649 → 153 nodes, 218 → 0 long chords. CYXY adjudicated 406 → 345 (airside 381 → 306; `taxi_box` 34 → 17, `airside_no_step` 74 → 40). Suite 1,400/0 twice on main (the four v1 bank/road suites included). TWO FINDINGS the merge carries: (A) KCLT's §37 (4) bars are NOT MEASURED — the lane's KCLT build was refused at `airport/load.py:289` (the pack's `.anchor_bak` newer than every cached dump; the shared cache has no `+35-081.dsf.anchor_bak.*.text` — KCLT never had one; the 13q chip); v2zerocrater's `fresh_pack_dump` (13w) cures this — scout `v2roadcapkclt` dispatched to build KCLT once on main and read §37 (4)'s bars (`dsf:pol51` +14.22 m at 35.2074982,−80.9296586; shapeID 791 apron +12.33; bank 1,855 stations 28.4 % load-bearing). (B) LEMD's census went the WRONG WAY: adjudicated 1,143 → 1,379 (airside 1,127 → 1,345; `taxi_box` +122, `airside_no_step` +62) — attributed by elimination (classification byte-identical; the bank arms census identically family for family; (1) a proven relaxation) to the LP landing on a different optimum of an UNSETTLED system: BOTH arms at base ec8723e9 read `HARD SET NOT SETTLED` / `LAG NOT SETTLED` at LEMD. That is a REGRESSION of 12ac (v2padceiling settled LEMD: 725 violated hard rows → 0) by something merged between 81befff0 and ec8723e9 — scout `v2unsettled2` dispatched to bisect by offline replay (the 12u instrument reproduces the shipped solve bit for bit). The owner ranked the unsettled solve first among debts (12s); its return is the top item before app 1.0.327's LEMD read is trusted.

## 2026-09-13ab — SCOUT `v2roadcapkclt` (one KCLT build on main 064e244e, 373.3 s rc 0, ledger 2951cfc994bd, `body_sha d6093e801a96`; 13w's re-dump CONFIRMED — KCLT builds under the harness). §37 (3) LANDED at KCLT: bank 1,855 stations / 34,212 m / 451 chords > 30 m → 1,876 stations of which 401 load-bearing (21.4 %), 732 foot nodes / 11,424 m / 0 chords > 30 m (max 29.94). §37 (1) and (2) DID NOT TOUCH THE OWNER'S SITES: `dsf:pol51` (item 5) +14.22 → +13.28 m at 35.2074982,−80.9296586 (the chain over 179.3 m: DEM relief 12.15 m, emitted relief 3.49 m, FOLLOW RATIO 0.287, highest fill 13.28 m — the DEM grade 6.8 % is UNDER the 8 % road cap, so the cap was never what held it); shapeID 791 → 784 `dsf:pol82` (item 7) STILL `apron`, +11.52 m max at 35.2209280,−80.9275739 — 13q read it flipped by §27 on 2 % of its perimeter and §37 (2)'s 0.2 share should have left it a road, so either the share is not read where the flip happens or the face is apron by the scorer before §27 runs. 13q's item-5 attribution was INCOMPLETE: relaxing the longitudinal cap was a proven strict relaxation and moved the site 0.94 m; a second mechanism holds the road 13 m up. Cockpit block on this build: CRITICAL motion 9 (worst 0.790 m over 57.88 m `strip_arc [stub|stub]` 35.2123806,−80.9513621; three `mid_edge_step apron|apron` 0.52–0.60 m over ~1 m at 35.2082082,−80.9412547 / 35.2137789,−80.9323169 / 35.2088523,−80.9421498; one `cross_shape` cliff 0.31 m at 35.2139545,−80.9297320), CRITICAL visual 2 (the §35 corner — this build predates ddc5b11d); vs 13w's build motion 15 → 9, worst 3.640 → 0.790 m; law-true 12,353 → 11,504; adjudicated 3,959 (airside 3,592). KCLT is UNSETTLED on all three counters (644 active-set rounds, 21/236,084 hard rows violated max 0.4144 m, 11,211 one-way rows worst leader move 0.332 m) — KCLT's own instance of 13y (B); scout `v2unsettled2` is bisecting LEMD's. Owner items at their coordinates on this build: 1 corner z−DEM −1.47, the two 5.02/4.93 m cliffs still there (pre-§35); 3 no bore/mouth within 35 m of either coordinate (13 bores / 26 mouths built, none here — §34 (5), lane `v2rampwalk`); 4 and 6 pads on their ground (+0.24 / +0.55; +1.23 / −1.48 flat pads) — the floating roofs are object-stage (v2unboxed, now merged, not in this build); 9 the terminal's 27 basin refusals are all the `paredes_*/techos_*/suelos_*_charlotte` + `Charlotte_Airport_00{5,8}_ALB` family refused under 09ag rule 5b ("a slab on datum relief, not a sunken solid"), 4.25–9.54 m under local ground and ~0 under their own render datum — the pack's flat datum plane over real relief; NOTHING in the planar or object stage addresses it yet: OWED as an owner item (the terminal complex wants ONE datum for the family — §16c (6) shared-datum unit — seated at the terminal pad's level, its pieces cut to their own ground where they stand apart). Harness notes: `--tag` collides case-insensitively with a dead run's stem (`v2roadcapKCLT`) — correct refusal; `Could not save airport info … Data+35-081.apt` warning in a lane worktree without `Tiles/` (harmless). Lane `v2roadcap2` dispatched: fix the `default_inputs` half of the 13q chip so `explain KCLT` runs, name the rows holding `dsf:pol51` at +13.28 m and the pass that classes `dsf:pol82` apron, fix both, ONE KCLT build.

## Tool: v2_solve_replay

| `Ortho4XP/tools/v2_solve_replay.py` | --why-vertex V [--why-relax FAMILY ...]`; `--why-hard [N]` on either a `--replay` arm or a `--why-from PKL`) | You are iterating on the v2 SOLVE (a law table, a generator, the shape stage, the planar build) and want the runway bows / z − DEM / joints / yielded-rows figures per change WITHOUT paying for the load stage each time — the synthetic-first solve arm (CLAUDE.md BUILD ECONOMY; `docs/specs/auto-patch-v2/heca-sag-ablation/ablate_heca_pin.py` was the scratch pattern, promoted on its second use by lane v2chord, RULINGS 2026-09-08d). `--capture` runs load → **the PACK PARTITION + GROUPS** (`build.py:288-318`, owner RULINGS 2026-09-11j — folded in 2026-09-12u by lane `v2padceiling` after scout `v2unsettled` measured the trap: a capture without them carries an `Airport` with no `partition` and no `groups`, so the replay silently solves a DIFFERENT problem — no `foot_rows`, no `pad_relief` targets, no basin bodies, and the shipped LEMD hard set could not be reproduced at all; a capture predating it is now REFUSED BY NAME at replay, `capture_has_groups`) → classify → planar (which labels the SHAPES, owner RULINGS 2026-09-08k) → flat site → road profile → shape stage exactly as `pipeline/build.py` and pickles the airport, the classification, the planar map and the stage (HECA 56 s; LEMD 232 s, of which 104 s partition); `--replay` resumes from the named stage under the CURRENT tree (constraints + joint filter + yield transform + ONE solve by default — 08k (4), no joint re-solve; `shapes` rebuilds the shapes over the captured map and re-runs the stage — for a change in `planar/shapes.py` or `[terrace]`; `planar` the whole map), and prints per two-threshold runway the crown-ridge BOW, the ridge minimum, z − DEM mean/min/max, the law-tier line, `yielded_rows` per family and the max apron grade PER SHAPE with the steepest rows per family (face, grade, span, lat/lon), the shapes (count, the largest by vertices), the joints (count, gap joints, max built step, the worst with their shape pair), the road steps, and per `--site` the vertices within `--site-radius` (z − DEM, roles, shape ids, the max |dz| over a short edge = a step). `--emit DIR` writes the arm's patch through the build's own emit half so `patch_proximity_diff.py` and `undulation.py` can read a same-frame divergence on a replay arm; `--verify` runs the v2 VERIFY CENSUS on the solved surface and prints the rows per family and the DEFECT families the app's driver gates on (lane v2smooth round 2, RULINGS 2026-09-08v — a weight sweep needs the defect count per arm without a 130 s build); `--design-weight TERM=W` overrides one `emit.toml [design]` weight for the arm (the measurement arm, never a default). `--drop-generator` also accepts the pseudo-generator **`eat_ramp_reach`** (lane `v2eatramp`, spec §36 (5)): the EAT ramp's trend WITHDRAWAL is a channel edit made before the solve, not a row, so it cannot be dropped by the row filter — `eat_anchor_rect` drops the pins and their reach together, `eat_ramp_reach` the withdrawal alone (the §36 (5) before-arm). Lane v2shapes (2026-09-08): HECA capture 56 s; one pass 144–150 s (the 08g three-pass law read 357 s). `--why-from PKL --why-hump RUNWAY S0 S1` (the `solve.why` bindings and chain trace on the highest ridge vertex above the chord, from a duals solve of the SAME LP — kept out of the timed arm) with `--why-relax FAMILY ...` (relax-one-family arms: the hump's dz after a full re-solve without the family — the INTERVENTIONAL holder read). `--why-hard [N]` lists EVERY VIOLATED HARD ROW of the solved surface — generator, ruling, demanded vs allowed metres, and per vertex the id, coefficient, z, DEM, lat/lon and roles — re-assembling the design problem with `solve.design.assemble` and applying design.py's own `2 / Σ|c|` row scaling, so every violation reads in the METRES `hard_tol_m` is stated in (promoted from scout `v2unsettled2`'s `hardrows.py` on its second use, spec §32 (4), RULINGS 2026-09-13ac: `HARD SET NOT SETTLED` names ONE truncated ruling, which cost 12u a scout re-deriving the population by hand and 13ac needed the row's VERTICES to see that main's worst row was a pair the zone projection had clamped independently). **`--emit` IS THE BUILD'S WHOLE EMIT HALF SINCE 2026-09-13** (lane `v2zonebank`, §37 (3)): it ran `graded_surface` -> `write_patch` and SKIPPED `with_bank` / `with_terrain_edges`, so every `bank_foot` question asked of a replay arm read ZERO feet and looked like the defect under attribution — it now runs `pipeline/build.py:780-795` verbatim and prints the `BankReport` line. **`--bank-from SOLVED.pkl`** replays that emit half alone off a `--solved-out` pickle (KCLT 2.5 s against the 160 s `--replay`), with `--emit DIR` and/or **`--bank-walk`**: §37 (3)'s per-station ADJACENT-GROUND ZONE-2 WALK — per `adjacent_ground:*:zone2` face ring, `|z_ring - DEM(foot)|` at every station, the stations at or over `bank_materiality_m`, whether the foot point stands outside the design coverage, whether it falls in the terrain-edge no-bank region or the water cut, and whether a `bank_foot` stands within that station's OWN 1:3 reach (never the airport-wide `bank_max_width_m`, which calls a foot 200 m away near); then, off `emit/bank.with_bank`'s `station_probe` / `region_probe` attribution hooks, the banked-region station the load-bearing verdict was actually taken on and where an unbanked station stands (inside the banked region? inside a coverage HOLE?). It prices no law and counts no defects — defect counts come from `harness/census.py`. Measured basis (KCLT, base `ce203b29`, `cap/KCLT.pkl`): 233 zone2 rings / 5,647 stations, 542 at or over the 1.65 m materiality, 220 with their foot outside the coverage, **110 with no foot at all** — 110 of them inside the banked region and 109 inside a coverage hole, which is how RULINGS 2026-09-13bu item 5 was attributed to `_foot_piece`'s solid exterior disc; after the fix 8. **A CAPTURE PREDATING A TARGET CHANNEL STILL REPLAYS, AND SAYS SO** (2026-09-13, lane `v2roadcontact`): a `PlanarMap` field added since the pickle was written is simply ABSENT on the unpickled instance, so the first `dataclasses.replace` raised `AttributeError` and a REGISTERED FRAME another lane shares became unreplayable for a channel its own stage never produced; `--replay` now backfills each missing field at the dataclass's OWN default and NAMES it on stdout (the publisher derives the channel in the replay anyway). This is NOT a relaxation of the 12u groups refusal, which stands: that one is a capture solving a DIFFERENT problem, this one is a channel the capture never had. Twins: `tests/auto_patch_v2/test_v2padceiling.py` (the capture calls every pre-solve stage `pipeline/build.build` calls, read off both sources; the refusal predicate) — the rest of the replay is an instrument over `pipeline/build.py`'s own stages, which the pipeline twins cover. |

## Tool: build_airport.py

| `Ortho4XP/tools/harness/build_airport.py` | You need to BUILD anything for measurement: one airport patch, a constant-DEM oracle world, or a whole tile. Enforces the build cwd, refuses a cold DEM/inset frame, a drifted config frame, a PRIVATE data corpus and any implicit download into the shared repo; guarantees the axes sidecar; wraps the run in the ledger; audits the shared repo before/after; and records the env, DEM-frame and data-mount snapshots every later claim depends on. It also refuses a DEGRADATION THE ENGINE SWALLOWED (2026-08-07): `auto_patch.elevation._load_airport_dem` runs production's whole DEM prep inside one `except Exception`, so a write the shared-repo guard blocked became a WARN line, `dem_inset_provenance: null` and a build that exited 0 on 18.5 k nodes against production's 34-36 k (measured at HECA, `tmp/sliver_attrib`). Two independent detectors close it — a write the guard blocked during a build that nevertheless returned, and a laylane carrying no DEM provenance at all — and either refuses BEFORE the patch is written, so a DEM-less `.osm` never lands where a census would find it. The guard's one allowance is the lane's cross-process `.lock` file (`is_lock_artifact`): coordination state, never corpus data, and only for the exclusive-create and removal that `O4_File_Lock.hold_file_lock` performs — a `builtins.open` of a `.lock` path, a rename onto one, or any real data write beside it still refuses, and the churn is recorded in `tmp/engine_cache_root`, `O4_LANE_CACHE_ROOT` overrides; one per WORKTREE, reused across runs, still lane-local and still COW-seeded — perf P2 Lane A 2026-08-13: the per-run root threw away everything a build derived, so HECA re-ran `_compute_dsf_object_buildings` (66.6 s) every lane build and OTHH ~455 s, and seeding from the shared corpus could not save it because the pack's own `.obj` files are IN the footprint fingerprint and the Phase-2 y-bake rewrites them AFTER that run's sidecar is written — HECA sidecar 07:03, 376 of 568 `.obj` rewritten 07:14; staleness is safe because every artifact under the root is content-keyed, so a stale clone recomputes rather than answering wrong) (`build_airport.frame.json`. `--dem CONST_M` substitutes a synthetic constant surface (an explicit DEM SOURCE substitution, never a law gate) and takes NEGATIVES — `--dem -500` is the ruled low world; the world is stamped into `<tag>.result.json` / `<tag>.frame.json` under `synthetic_dem`, because a −500 m census row is not comparable with a real-DEM one. The guard and its allowances live in `harness/shared_repo_guard.py` (one implementation, shared with `run_tile_mesh_only.py`). Engine derived-cache writes never touch the corpus at all (2026-08-11): every build re-points the two writable cache roots the engine derives into — the DSFTool dump cache (`O4_DSF_CACHE_DIR`) and the per-pack `Airport_mod_cache` root (`O4_AIRPORT_MOD_CACHE_DIR`, a COPY-ON-WRITE read-through overlay: APFS `clonefile` seeding — warm reads, and a write lands lane-local even when the writer TRUNCATES IN PLACE) — at the LANE-PERSISTENT root `<out>/<tag>.engine_caches/`, the same env-overridden mechanism the pytest suite runs under; the measured hole it closes is the DSFTool SUBPROCESS dump no Python-level guard can intercept (KCLT 2026-08-11, `Airport_mod_cache/zOrtho4XP_+35-081/+35-081.dsf.8828b7db.text`, run flagged CONTAMINATED). The MASKS root joined them 2026-08-12b (owner ruling: lane mask writes land lane-local): `O4_MASKS_DIR` (`O4_File_Names.masks_root`, read at CALL time) points the engine at `<out>/<tag>.engine_caches/Masks`, a copy-on-write overlay seeded from the shared `Masks/` subtree of the TILE(S) IN SCOPE — so the masks step's reads stay warm and its legacy cleanup deletes lane-local clones instead of everyone's rasters (the measured refusal: a HECA `--tile 30 31` arm rc=1 on 16 blocked `os.remove`s of `Masks/+30+030/+30+031/*.png`, every one swallowed by a bare `except: pass` now narrowed to `FileNotFoundError`). A scope the run is AUTHORISED to refresh (`--refresh-data airport_mod_cache` / `dsf_cache` / `masks`) is deliberately NOT redirected — the refresh must land in the shared repo — and the redirect record rides in `<tag>.result.json` / `<tag>.frame.json` under `engine_cache_redirects`. Corollary: a cold derived cache no longer forces `--allow-degraded-dem` (the rewrite lands lane-local instead of being guard-blocked); warming the SHARED cache stays an explicit `--refresh-data` act. `--warm-insets ICAO[,ICAO...]` (2026-08-11, round-13 spec amendment) fetches/refreshes the airport ELEVATION INSETS of exactly the airports named, before the build's DEM prep and inside the lock, snapshot, guard and ledger record (which names them) — valid ONLY with `--refresh-data dem`, re-querying rather than consulting the cache (negatives included — a transient TNM 504 cached a durable `no-coverage` for KMCI on 2026-08-11), and it is the only lawful instrument for a one-airport inset need: an airport build never reaches `ensure_airport_insets` (its DEM prep is pure disk state), a `--tile` build would refresh every void inset on the tile against a one-airport authorisation, and the standalone fetch tool writes the corpus outside the lock and the ledger. It also bypasses the `is_cached` size>0 gate for the named airports, under which a non-empty but INVALID raster makes a tile pass skip the fetch entirely. **The BASE-ARM ARTIFACT LEDGER (2026-08-12, BS2) means a reference arm is built once, ever:** every successful patch build stores its patch + sidecar + frame + env + result in `~/.ortho4xp/artifact_ledger` (outside the shared repo, gitignored, size-capped LRU, `O4_ARTIFACT_LEDGER_DIR` / `_MAX_MB`), content-addressed by (code-tree hash, ICAO, the `O4_*` env the run ledger keys on, CORPUS STAMP, build variant); `--base-arm` (or `--from-ledger`) serves that artifact instead of rebuilding — measured at CYXY: **0.3 s against a 63.3 s build, patch, sidecar and frame byte-identical**, behind a provenance line naming the original build, its timestamp and its duration, with a `<tag>.served.json` record beside it. A miss NAMES the component that moved, and a corpus-stamp mismatch is ALWAYS a miss (a changed corpus is a different measurement — the KCLT road-feed precedent). Refused: `--no-ledger` (a timing run has no time to replay), `--tile`, `--refresh-data`, and `--no-artifact-ledger` (a flag that silently does nothing). A refresh-authorised or CONTAMINATED run is never stored, and the key's tree hash + dirty flag are RE-CHECKED at store time (the key is cut at START; a worker-pool child that outlives its parent can finish after source edits land — the 2026-08-28 LEMD poisoned-key precedent): a mismatch refuses the store loudly, stamps `contaminated_key` into `<tag>.frame.json`, and never re-keys. **LANE INPUTS ARE PROVISIONED, NEVER HAND-SEEDED (owner ruling 2026-08-12b):** a `--tile` build whose build dir lacks `Ortho4XP_+XX+YYY.cfg` gets it as a BYTE COPY from the ritual's own canonical source (`$O4_MAIN_REPO/Ortho4XP/Tiles/zOrtho4XP_+XX+YYY/`, the tree `lane_worktree.sh` clones `Ortho4XP.cfg` and `Patches/` from), recorded with its sha256 in `<tag>.frame.json` under `tile_cfg_provenance`; an EXISTING lane cfg is never overwritten (recorded as `present`, hashed) and a MISSING canonical source REFUSES — synthesized defaults would build a tile at a provider and ZL nobody chose and exit 0. Closes the 'EMPTY default_website' wall two lanes each improvised past with a different cfg source on 2026-08-12. **`--solve-capture DIR` (2026-08-13, P2 instrument item 1)** additionally writes a SOLVE-STAGE CAPTURE into `DIR/<ICAO>/` — the phases 1-4 product at the solve boundary, replayable by `tools/solve_cut.py --replay` without rebuilding phases 1-4. It is armed inside `build_patch`, AFTER `arm_shared_repo_protection` (the env key is the engine module's own constant, and importing the engine before the redirect composition is the ordering that composition exists to prevent), and it is refused with `--tile` rather than silently doing nothing (`build_tile` runs the engine through another entry; arm `O4_SOLVE_CAPTURE` in that build's environment knowingly instead, and every airport the tile builds writes its own capture). Capture is a pure reader at the boundary: measured at CYXY the build's body sha was `61efa43c3aeb`, the frozen 1.0.245 baseline, capture armed.  **`--geometry-only` (2026-08-14, owner request):** plan geometry only (`compute_elevations=False`, the pipeline's own documented mode) for visual inspection — refused with `--tile` and `--solve-capture` (silent no-ops), stamped into `result.json` and the artifact-ledger variant key so a solved arm can never be served from a geometry-only one, and NEVER censused (there is no solved surface to count). **THE WINDOW IS NOT THE AUTHOR (2026-09-01, beta hardening H6 item 6 — flagged independently by three lanes):** the before/after audit diffs the WHOLE shared repo across the build's wall-clock window and used to attribute EVERY delta in it to that build — but builds run concurrently by ruling, an authorised `--refresh-data` in lane B lands inside lane A's window, and the library-index allowance was this same cross-attribution solved once for one file (the nidrepair 2026-08-07 frames each reported `write_guard_blocked: []` and each named the same modified sidecar neither of them wrote). Every delta is still NAMED — nothing is dropped — but one is labelled **EXTERNAL-CANDIDATE** instead of CONTAMINATED when BOTH hold: this build's own `write_guard_blocked` is EMPTY (a guard-blocked write is a whole-run veto — that build's code did reach for the corpus), AND the path is provably OUTSIDE the build's INPUT SET (`BuildInputScope`: the tiles it reads plus their eight neighbours, in BOTH corpus spellings — `+30+031` and `N30E031` — plus the per-airport road feed by ICAO). A path naming neither a tile nor an airport is UNSCOPABLE and therefore IN scope: "not provably external" is the whole predicate, and the instrument downgrades only what it can positively exclude. CONTAMINATED is unchanged for in-scope or guard-blocked deltas, and an entry passing no scope (or an empty one) gets the pre-2026-09-01 behaviour to the letter. The verdict is re-derivable: `build_input_scope`, `unauthorised_writes` (every delta) and `external_candidate_writes` all ride in `<tag>.frame.json`. The ARTIFACT-LEDGER STORE gate is deliberately the stricter of the two and still refuses on ANY delta — contamination is about whether this build's numbers are trustworthy, the store gate about whether its corpus stamp still describes the corpus a later hit would read. `contaminating_writes` is the ONE reading of the label. Twins: `tests/test_harness.py` (external-vs-in-scope, the guard-blocked veto, the unchanged default, the unscopable path, both tile spellings + neighbours, the ICAO rule, the refusal reading the one helper, the frame stamps). **There is no other sanctioned way to build.** **THE V2 ENGINE (2026-09-04, lane v2resid; THE ONLY ENGINE since the owner retired v1, RULINGS 2026-09-13au — there is no `--engine` flag and no `auto_patch_engine` cfg key):** the SAME entry builds the auto-patch-v2 patch (`src/auto_patch_v2/pipeline/build.py`, RULINGS 2026-09-03d) under the same cwd/DEM-frame/corpus refusals, the same shared-repo guard and swallowed-refusal detectors, the same sidecar guarantee, run ledger and artifact ledger; `frame.json` records `engine` and the v2 law-table digest (`law_tables`: sha256 over `src/auto_patch_v2/law/*.toml`) plus a `v2` block (solve status, LP size, stage walls, v2-verify counts, tile pieces), and the artifact-ledger variant key carries both (v1 keys unchanged — a v2 patch is never served for a v1 arm). The v2 products land in `<tag>.v2/` (`<ICAO>.report.json` with the IIS on infeasibility, `<ICAO>.graded.json`, tile pieces); the patch and sidecar are MOVED to `<tag>.osm` / `<tag>.osm.axes.json` so `census.py` reads it like any patch. Refused by name (not wired for v2): `--dem`, `--geometry-only`, `--solve-capture` (not wired; a silently-inert flag is the precedent). A non-optimal solve refuses to report (no patch is written). **`--tile LAT LON` (2026-09-04, lane v2app)** builds the WHOLE TILE with the app's own dispatch: `auto_patch.driver` runs `auto_patch.engine_v2.build_write_verify_one_v2` per airport — `auto_patch_v2.pipeline.build` on the tile's OWN production DEM (`tile.dem` seeded into the v2 loader, never re-composed), the current tile's patch + sidecar placed at `Patches/<block>/<tile>/<ICAO>_auto.patch.osm`, the v2 verify census in `auto_patch_verify_debug.log`, one `[provenance] ICAO patch: engine=v2 sha=… law=<digest> ruleset=… solve=… dem=…` line per airport, and a non-optimal solve / v2 refusal a NAMED per-airport build failure (`AutoPatchFailed` on the JSONL protocol, IIS in the verify log). Every patch carries `o4_ap_engine` in its freshness block (schema `2`), so a patch the retired engine left behind never reads as current. Measured +25+051 2026-09-04: OTBD 13.7 s / OTBH 7.0 s / OTHH 37.8 s, all optimal; oracle census on the placed OTHH patch 0/0. The mod-cache redirect is also handed to v2's own loader (`inputs.mod_cache_root`), which `planar.__main__.default_inputs` cannot do for itself — it reads no environment by design, so before 2026-09-13 the pack-dump FRESHNESS guard (`airport/load.py:289`) judged the SHARED root and refused every KCLT / HECA v2 build and `explain` (RULINGS 2026-09-13q, "chip"); the build now reads and derives its DSF text dumps in the same lane-local overlay every other derived cache lands in. The guard's one allowance is the lane's cross-process `.lock` file (`is_lock_artifact`): coordination state, never corpus data, and only for the exclusive-create and removal that `O4_File_Lock.hold_file_lock` performs — a `builtins.open` of a `.lock` path, a rename onto one, or any real data write beside it still refuses, and the churn is recorded in `tmp/engine_cache_root`, `O4_LANE_CACHE_ROOT` overrides; one per WORKTREE, reused across runs, still lane-local and still COW-seeded — perf P2 Lane A 2026-08-13: the per-run root threw away everything a build derived, so HECA re-ran `_compute_dsf_object_buildings` (66.6 s) every lane build and OTHH ~455 s, and seeding from the shared corpus could not save it because the pack's own `.obj` files are IN the footprint fingerprint and the Phase-2 y-bake rewrites them AFTER that run's sidecar is written — HECA sidecar 07:03, 376 of 568 `.obj` rewritten 07:14; staleness is safe because every artifact under the root is content-keyed, so a stale clone recomputes rather than answering wrong) (`build_airport.frame.json`. `--dem CONST_M` substitutes a synthetic constant surface (an explicit DEM SOURCE substitution, never a law gate) and takes NEGATIVES — `--dem -500` is the ruled low world; the world is stamped into `<tag>.result.json` / `<tag>.frame.json` under `synthetic_dem`, because a −500 m census row is not comparable with a real-DEM one. The guard and its allowances live in `harness/shared_repo_guard.py` (one implementation, shared with `run_tile_mesh_only.py`). Engine derived-cache writes never touch the corpus at all (2026-08-11): every build re-points the two writable cache roots the engine derives into — the DSFTool dump cache (`O4_DSF_CACHE_DIR`) and the per-pack `Airport_mod_cache` root (`O4_AIRPORT_MOD_CACHE_DIR`, a COPY-ON-WRITE read-through overlay: APFS `clonefile` seeding — warm reads, and a write lands lane-local even when the writer TRUNCATES IN PLACE) — at the LANE-PERSISTENT root `<out>/<tag>.engine_caches/`, the same env-overridden mechanism the pytest suite runs under; the measured hole it closes is the DSFTool SUBPROCESS dump no Python-level guard can intercept (KCLT 2026-08-11, `Airport_mod_cache/zOrtho4XP_+35-081/+35-081.dsf.8828b7db.text`, run flagged CONTAMINATED). The MASKS root joined them 2026-08-12b (owner ruling: lane mask writes land lane-local): `O4_MASKS_DIR` (`O4_File_Names.masks_root`, read at CALL time) points the engine at `<out>/<tag>.engine_caches/Masks`, a copy-on-write overlay seeded from the shared `Masks/` subtree of the TILE(S) IN SCOPE — so the masks step's reads stay warm and its legacy cleanup deletes lane-local clones instead of everyone's rasters (the measured refusal: a HECA `--tile 30 31` arm rc=1 on 16 blocked `os.remove`s of `Masks/+30+030/+30+031/*.png`, every one swallowed by a bare `except: pass` now narrowed to `FileNotFoundError`). A scope the run is AUTHORISED to refresh (`--refresh-data airport_mod_cache` / `dsf_cache` / `masks`) is deliberately NOT redirected — the refresh must land in the shared repo — and the redirect record rides in `<tag>.result.json` / `<tag>.frame.json` under `engine_cache_redirects`. Corollary: a cold derived cache no longer forces `--allow-degraded-dem` (the rewrite lands lane-local instead of being guard-blocked); warming the SHARED cache stays an explicit `--refresh-data` act. `--warm-insets ICAO[,ICAO...]` (2026-08-11, round-13 spec amendment) fetches/refreshes the airport ELEVATION INSETS of exactly the airports named, before the build's DEM prep and inside the lock, snapshot, guard and ledger record (which names them) — valid ONLY with `--refresh-data dem`, re-querying rather than consulting the cache (negatives included — a transient TNM 504 cached a durable `no-coverage` for KMCI on 2026-08-11), and it is the only lawful instrument for a one-airport inset need: an airport build never reaches `ensure_airport_insets` (its DEM prep is pure disk state), a `--tile` build would refresh every void inset on the tile against a one-airport authorisation, and the standalone fetch tool writes the corpus outside the lock and the ledger. It also bypasses the `is_cached` size>0 gate for the named airports, under which a non-empty but INVALID raster makes a tile pass skip the fetch entirely. **The BASE-ARM ARTIFACT LEDGER (2026-08-12, BS2) means a reference arm is built once, ever:** every successful patch build stores its patch + sidecar + frame + env + result in `~/.ortho4xp/artifact_ledger` (outside the shared repo, gitignored, size-capped LRU, `O4_ARTIFACT_LEDGER_DIR` / `_MAX_MB`), content-addressed by (code-tree hash, ICAO, the `O4_*` env the run ledger keys on, CORPUS STAMP, build variant); `--base-arm` (or `--from-ledger`) serves that artifact instead of rebuilding — measured at CYXY: **0.3 s against a 63.3 s build, patch, sidecar and frame byte-identical**, behind a provenance line naming the original build, its timestamp and its duration, with a `<tag>.served.json` record beside it. A miss NAMES the component that moved, and a corpus-stamp mismatch is ALWAYS a miss (a changed corpus is a different measurement — the KCLT road-feed precedent). Refused: `--no-ledger` (a timing run has no time to replay), `--tile`, `--refresh-data`, and `--no-artifact-ledger` (a flag that silently does nothing). A refresh-authorised or CONTAMINATED run is never stored, and the key's tree hash + dirty flag are RE-CHECKED at store time (the key is cut at START; a worker-pool child that outlives its parent can finish after source edits land — the 2026-08-28 LEMD poisoned-key precedent): a mismatch refuses the store loudly, stamps `contaminated_key` into `<tag>.frame.json`, and never re-keys. **LANE INPUTS ARE PROVISIONED, NEVER HAND-SEEDED (owner ruling 2026-08-12b):** a `--tile` build whose build dir lacks `Ortho4XP_+XX+YYY.cfg` gets it as a BYTE COPY from the ritual's own canonical source (`$O4_MAIN_REPO/Ortho4XP/Tiles/zOrtho4XP_+XX+YYY/`, the tree `lane_worktree.sh` clones `Ortho4XP.cfg` and `Patches/` from), recorded with its sha256 in `<tag>.frame.json` under `tile_cfg_provenance`; an EXISTING lane cfg is never overwritten (recorded as `present`, hashed) and a MISSING canonical source REFUSES — synthesized defaults would build a tile at a provider and ZL nobody chose and exit 0. Closes the 'EMPTY default_website' wall two lanes each improvised past with a different cfg source on 2026-08-12. **`--solve-capture DIR` (2026-08-13, P2 instrument item 1)** additionally writes a SOLVE-STAGE CAPTURE into `DIR/<ICAO>/` — the phases 1-4 product at the solve boundary, replayable by `tools/solve_cut.py --replay` without rebuilding phases 1-4. It is armed inside `build_patch`, AFTER `arm_shared_repo_protection` (the env key is the engine module's own constant, and importing the engine before the redirect composition is the ordering that composition exists to prevent), and it is refused with `--tile` rather than silently doing nothing (`build_tile` runs the engine through another entry; arm `O4_SOLVE_CAPTURE` in that build's environment knowingly instead, and every airport the tile builds writes its own capture). Capture is a pure reader at the boundary: measured at CYXY the build's body sha was `61efa43c3aeb`, the frozen 1.0.245 baseline, capture armed.  **`--geometry-only` (2026-08-14, owner request):** plan geometry only (`compute_elevations=False`, the pipeline's own documented mode) for visual inspection — refused with `--tile` and `--solve-capture` (silent no-ops), stamped into `result.json` and the artifact-ledger variant key so a solved arm can never be served from a geometry-only one, and NEVER censused (there is no solved surface to count). **THE WINDOW IS NOT THE AUTHOR (2026-09-01, beta hardening H6 item 6 — flagged independently by three lanes):** the before/after audit diffs the WHOLE shared repo across the build's wall-clock window and used to attribute EVERY delta in it to that build — but builds run concurrently by ruling, an authorised `--refresh-data` in lane B lands inside lane A's window, and the library-index allowance was this same cross-attribution solved once for one file (the nidrepair 2026-08-07 frames each reported `write_guard_blocked: []` and each named the same modified sidecar neither of them wrote). Every delta is still NAMED — nothing is dropped — but one is labelled **EXTERNAL-CANDIDATE** instead of CONTAMINATED when BOTH hold: this build's own `write_guard_blocked` is EMPTY (a guard-blocked write is a whole-run veto — that build's code did reach for the corpus), AND the path is provably OUTSIDE the build's INPUT SET (`BuildInputScope`: the tiles it reads plus their eight neighbours, in BOTH corpus spellings — `+30+031` and `N30E031` — plus the per-airport road feed by ICAO). A path naming neither a tile nor an airport is UNSCOPABLE and therefore IN scope: "not provably external" is the whole predicate, and the instrument downgrades only what it can positively exclude. CONTAMINATED is unchanged for in-scope or guard-blocked deltas, and an entry passing no scope (or an empty one) gets the pre-2026-09-01 behaviour to the letter. The verdict is re-derivable: `build_input_scope`, `unauthorised_writes` (every delta) and `external_candidate_writes` all ride in `<tag>.frame.json`. The ARTIFACT-LEDGER STORE gate is deliberately the stricter of the two and still refuses on ANY delta — contamination is about whether this build's numbers are trustworthy, the store gate about whether its corpus stamp still describes the corpus a later hit would read. `contaminating_writes` is the ONE reading of the label. Twins: `tests/test_harness.py` (external-vs-in-scope, the guard-blocked veto, the unchanged default, the unscopable path, both tile spellings + neighbours, the ICAO rule, the refusal reading the one helper, the frame stamps). **There is no other sanctioned way to build.** **THE V2 ENGINE (2026-09-04, lane v2resid; THE ONLY ENGINE since the owner retired v1, RULINGS 2026-09-13au — there is no `--engine` flag and no `auto_patch_engine` cfg key):** the SAME entry builds the auto-patch-v2 patch (`src/auto_patch_v2/pipeline/build.py`, RULINGS 2026-09-03d) under the same cwd/DEM-frame/corpus refusals, the same shared-repo guard and swallowed-refusal detectors, the same sidecar guarantee, run ledger and artifact ledger; `frame.json` records `engine` and the v2 law-table digest (`law_tables`: sha256 over `src/auto_patch_v2/law/*.toml`) plus a `v2` block (solve status, LP size, stage walls, v2-verify counts, tile pieces), and the artifact-ledger variant key carries both (v1 keys unchanged — a v2 patch is never served for a v1 arm). The v2 products land in `<tag>.v2/` (`<ICAO>.report.json` with the IIS on infeasibility, `<ICAO>.graded.json`, tile pieces); the patch and sidecar are MOVED to `<tag>.osm` / `<tag>.osm.axes.json` so `census.py` reads it like any patch. Refused by name (not wired for v2): `--dem`, `--geometry-only`, `--solve-capture` (not wired; a silently-inert flag is the precedent). A non-optimal solve refuses to report (no patch is written). **`--tile LAT LON` (2026-09-04, lane v2app)** builds the WHOLE TILE with the app's own dispatch: `auto_patch.driver` runs `auto_patch.engine_v2.build_write_verify_one_v2` per airport — `auto_patch_v2.pipeline.build` on the tile's OWN production DEM (`tile.dem` seeded into the v2 loader, never re-composed), the current tile's patch + sidecar placed at `Patches/<block>/<tile>/<ICAO>_auto.patch.osm`, the v2 verify census in `auto_patch_verify_debug.log`, one `[provenance] ICAO patch: engine=v2 sha=… law=<digest> ruleset=… solve=… dem=…` line per airport, and a non-optimal solve / v2 refusal a NAMED per-airport build failure (`AutoPatchFailed` on the JSONL protocol, IIS in the verify log). Every patch carries `o4_ap_engine` in its freshness block (schema `2`), so a patch the retired engine left behind never reads as current. Measured +25+051 2026-09-04: OTBD 13.7 s / OTBH 7.0 s / OTHH 37.8 s, all optimal; oracle census on the placed OTHH patch 0/0. |

| `Ortho4XP/tools/harness/build_airport.py` | **Default.** See above. |

## Registered frames: HECA

HECA  patch    base 13431931   lane v2zonehole       2026-09-13T22:35:13  /tmp/harness/v2zonehole_heca3.osm  — closing arm of claude/v2zonehole (rc 0, 410.3 s, body_sha 6cc8952ff963, ledger 3b32f2bd74f7, shared repo UNCHANGED) — §41 (1) absorption: containment census 39 -> 4 contained faces (33 notches absorbed, 65,772 -> 245 m2), cross_connector:pav77 absorbed into primary_parallel:pav73 at the owner's site, law-true 40,067 -> 38,151, rows within 100 m of the site 615 -> 551; residual zone_on_pavement 3 / 52.3 m2
HECA  capture  base 1a7a7158   lane v2roadcontact    2026-09-13T22:42:26  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/roadcontact/cap/HECA.pkl  — the FIRST registered HECA capture (v2_solve_replay --capture, 156 s, 17,408 vertices / 762 faces, 59 shapes) on main 1a7a7158; carries the road_contact_edge channel
HECA  patch    base 1a7a7158   lane v2roadcontact    2026-09-13T22:42:26  /tmp/harness/v2roadcontactHECA2.osm  — closing build of claude/v2roadcontact 9ac0fac2 (rc 0, 337.6 s, body_sha 38465d2dfd2a, ledger 96f569b01af9, shared repo UNCHANGED) — §37 (10): route0 end +0.054 m over pav74 edge, item-4 pair 1.6 % over 3.05 m; census law-true 38,441 adjudicated 12,771
HECA  patch    base 1a7a7158   lane v2roles          2026-09-13T22:45:39  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2roles/build/v2roles_HECA.osm  — closing HECA build of lane v2roles at claude/v2roles f19e2226 (§40): rc 0, 439.8 s, ways 1383, body_sha 8b2ca256f237, artifact ledger 9441f61e86fb, solve feasible, guard UNCHANGED. Shape 44 -> runway shoulder of 05L/23R, shape 93 -> apron, taxi zone strips on shape 44's ground 5 -> 0. RESIDUAL: v2-verify DEFECT runway_transverse 0 -> 2 (1.5287/1.5233 % vs the 1.50 % cap = 3.1/4.8 cm excess at 108.7/204.9 m from the ridge)
HECA  graded   base 1a7a7158   lane v2roles          2026-09-13T22:45:39  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2roles/build/v2roles_HECA.v2/HECA.graded.json  — design surface of the same v2roles_HECA build; HECA.report.json beside it carries verify.rows per family
HECA  patch    base 79d1fc1e   lane v2drapedsrc      2026-09-13T22:48:53  /tmp/harness/v2drapedsrc_heca.osm  — lane v2drapedsrc closing HECA build on claude/v2drapedsrc 588c09fa (base main 79d1fc1e): rc 0, 1941.7 s, body_sha d5643cfde2d4, artifact ledger 302ca060e48e, shared repo UNCHANGED, solve feasible — the FIRST HECA frame carrying §42 object pavement (467 bodies / 5,511,801 m2 from 8 draped resources; the owner's site 30.1235047,31.4160956 now INSIDE apron:pav132 shape 63)
HECA  graded   base 79d1fc1e   lane v2drapedsrc      2026-09-13T22:48:53  /tmp/harness/v2drapedsrc_heca.v2/HECA.graded.json  — lane v2drapedsrc closing HECA build on claude/v2drapedsrc 588c09fa (base main 79d1fc1e): rc 0, 1941.7 s, body_sha d5643cfde2d4, artifact ledger 302ca060e48e, shared repo UNCHANGED, solve feasible — the FIRST HECA frame carrying §42 object pavement (467 bodies / 5,511,801 m2 from 8 draped resources; the owner's site 30.1235047,31.4160956 now INSIDE apron:pav132 shape 63)
HECA  rebake   base 79d1fc1e   lane v2drapedsrc      2026-09-13T22:48:53  /tmp/harness/v2drapedsrc_heca.v2/HECA.rebake.json  — lane v2drapedsrc closing HECA build on claude/v2drapedsrc 588c09fa (base main 79d1fc1e): rc 0, 1941.7 s, body_sha d5643cfde2d4, artifact ledger 302ca060e48e, shared repo UNCHANGED, solve feasible — the FIRST HECA frame carrying §42 object pavement (467 bodies / 5,511,801 m2 from 8 draped resources; the owner's site 30.1235047,31.4160956 now INSIDE apron:pav132 shape 63)
HECA  patch    base a5bb6be3   lane v2roles          2026-09-13T23:17:39  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2roles/build_r2/v2roles_HECA_r2b.osm  — ROUND 2 closing HECA build, claude/v2roles a33197a5 (§40 as amended by RULINGS 2026-09-13dd, main merged at 76108185): rc 0, 352.7 s, ways 1142, nodes 22040, body_sha 907d90dfc271, artifact ledger 09ca36ca6c1a, solve feasible, guard shared repo UNCHANGED. v2-verify runway_transverse 2 -> 0 (the two shoulder rows pass at the 2.5 % shoulder cap); NO DEFECT family. Matched census A/B vs the 1a7a7158 base arm: law-true 38,612 -> 33,265, ADJUDICATED 12,844 -> 14,870 (+2,026; round 1 was +2,511)
HECA  graded   base a5bb6be3   lane v2roles          2026-09-13T23:17:39  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2roles/build_r2/v2roles_HECA_r2b.v2/HECA.graded.json  — design surface of the round-2 v2roles_HECA_r2b build; report.json beside it, and the A/B rows dumps in scratchpad/v2roles/rows_r2.*.json
HECA  patch    base 38dd98be   lane v2roadcontact    2026-09-13T23:36:37  /tmp/harness/v2roadcontactHECA3.osm  — CLOSING build of claude/v2roadcontact 9eaebbf8 (rc 0, 332.5 s, body_sha 8bbae5f33254, artifact ledger 5e3f94ef2db6, shared repo UNCHANGED) on merged main 38dd98be — §37 (10) as ruled 13dh: route0 end +0.023 m over pav74's edge (4.34 m away), item-4 pair 0.05 m over 3.05 m (1.6 %); census law-true 33,242 adjudicated 14,850 (airside 14,506 / gs 300), road_cross_section 27, transverse 1,575, road_coverage_join 0; v2 verify 21,797 rows, verify_defects {}
HECA  patch    base 38dd98be   lane v2drapedsrc      2026-09-13T23:39:26  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/drapedsrc/l2/v2ds_lane38.osm  — lane v2drapedsrc round 2 (§42 (2) amended, RULINGS 13dc) on claude/v2drapedsrc 8994391f; MATCHED PAIR with the base arm cut at main 38dd98be (both carry §40). rc 0, 540.9 s, ways 1783, body_sha c16719e90795, artifact ledger 3eec5bf2bd6a, shared repo UNCHANGED. The owner's site 30.1235047,31.4160956 is INSIDE its OWN apron face apron:dsf:objpav33 (base: 0 rings); census law-true adjudicated 14,870 -> 24,338
HECA  graded   base 38dd98be   lane v2drapedsrc      2026-09-13T23:39:26  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/drapedsrc/l2/v2ds_lane38.v2/HECA.graded.json  — lane v2drapedsrc round 2 (§42 (2) amended, RULINGS 13dc) on claude/v2drapedsrc 8994391f; MATCHED PAIR with the base arm cut at main 38dd98be (both carry §40). rc 0, 540.9 s, ways 1783, body_sha c16719e90795, artifact ledger 3eec5bf2bd6a, shared repo UNCHANGED. The owner's site 30.1235047,31.4160956 is INSIDE its OWN apron face apron:dsf:objpav33 (base: 0 rings); census law-true adjudicated 14,870 -> 24,338
HECA  patch    base 38dd98be   lane v2drapedsrc      2026-09-13T23:39:26  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/drapedsrc/b2/v2ds_base38.osm  — BASE ARM of the v2drapedsrc round-2 pair: main 38dd98be cut with git archive into a ritual worktree (src byte-identical to the archive), rc 0, 342.7 s, ways 1142, body_sha 907d90dfc271, artifact ledger 85edce09e12a, shared repo UNCHANGED
HECA  graded   base 38dd98be   lane v2drapedsrc      2026-09-13T23:39:26  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/drapedsrc/b2/v2ds_base38.v2/HECA.graded.json  — the design surface of the same v2ds_base38 base arm
HECA  capture  base cf87c942   lane v2unionsweep     2026-09-14T07:40:37  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2unionsweep/heca.lane.json  — DRY replay dump (NOT a capture: plan_clusters OFF the registered HECA capture 1a7a7158, via cluster_arm.py). MATCHED PAIR: heca.base.json = main cf87c942 (67.52 s, contended; scout read 28.7 s), heca.lane.json = claude/v2unionsweep 99cf52ba (2.24 s). 2 clusters both arms, both areas bit-identical (unit:42#0 404117.7954653089 / unit:43#8 915741.4253155532).
HECA  patch    base fef82b29   lane v2slivers        2026-09-14T09:05:26  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2slivers/heca/v2sl_heca2.osm  — CLOSING build of claude/v2slivers 88dfed33 (base main fef82b29): rc 0, 549.5 s, ways 1720, nodes 31441, body_sha 1c7f2be7abae, solve feasible, shared repo UNCHANGED (2 EXTERNAL-CANDIDATE VHHH deltas outside this build's input set) - 41(4) zone slivers 57/1647 m2 -> 1/188 m2 (55 dissolved, 0 dropped), owner shape 1035 gone (no vertex within 12 m of 30.1110526,31.4061994; base carried four at 105.86-106.01 against neighbours 104.32-104.71); gap_interior_ring 57 -> 49 (3 covered + 5 hairline gone incl way -10231, 0 minted, all 49 real voids). Census A/B vs v2sl_heca_base: law-true 54018 -> 53806, ADJUDICATED 24305 -> 24375, cockpit CRITICAL motion 14 -> 17, visual 1568 -> 1518
HECA  patch    base fef82b29   lane v2slivers        2026-09-14T09:05:26  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2slivers/heca_base/v2sl_heca_base.osm  — BASE ARM of the v2slivers matched pair: main fef82b29 (src restored clean in the lane worktree), rc 0, 521.5 s, ways 1783, body_sha c07206902a0b, artifact ledger dc1d00dd83ca, shared repo UNCHANGED. Reproduces the owner's 1.0.331 numbers exactly: 338 graded_strip faces, 57 slivers / 1647 m2, 57 gap_interior_ring rings
HECA  patch    base 2a4abb10   lane v2apronneck      2026-09-14T09:05:27  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/apronneck/build/v2apronneck_HECA.osm  — lane v2apronneck CLOSING HECA build on claude/v2apronneck 5340dcd7 (base main 2a4abb10) — §43 the neck cut: rc 0, 544.5 s, ways 1822, nodes 31613, body_sha d47263b02287, artifact ledger d53f79789526, solve feasible, guard shared repo UNCHANGED, v2-verify DEFECTS {}. HECA 10 necks; the owner's shape-344 apron (79,658 m2, z span 21.77 m) is gone — the neck A->B is secondary_parallel carrying -2.18 % where the apron carried -1.51 %, the new apron beyond spans 2.51 m. MATCHED PAIR with v2apronneck_HECAbase.
HECA  graded   base 2a4abb10   lane v2apronneck      2026-09-14T09:05:27  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/apronneck/build/v2apronneck_HECA.v2/HECA.graded.json  — lane v2apronneck CLOSING HECA build on claude/v2apronneck 5340dcd7 (base main 2a4abb10) — §43 the neck cut: rc 0, 544.5 s, ways 1822, nodes 31613, body_sha d47263b02287, artifact ledger d53f79789526, solve feasible, guard shared repo UNCHANGED, v2-verify DEFECTS {}. HECA 10 necks; the owner's shape-344 apron (79,658 m2, z span 21.77 m) is gone — the neck A->B is secondary_parallel carrying -2.18 % where the apron carried -1.51 %, the new apron beyond spans 2.51 m. MATCHED PAIR with v2apronneck_HECAbase.
HECA  patch    base 2a4abb10   lane v2apronneck      2026-09-14T09:05:27  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/apronneck/base_build/v2apronneck_HECAbase.osm  — BASE ARM of the v2apronneck matched pair: main 2a4abb10 in its own ritual worktree (v2apronneckbase), rc 0, 550.6 s, shared repo UNCHANGED (2 external-candidate deltas named, another lane's VHHH mod-cache), NOT ledger-stored. Census law-true 54,018 adjudicated 24,305
HECA  patch    base 22134e4f   lane zonemint         2026-09-14T09:26:56  /tmp/harness/zonemint_heca.osm  — closing build of claude/zonemint f35d3ee9 (rc 0, 664.5 s, ways 1783, nodes 31514, body_sha c07206902a0b, solve feasible, shared repo UNCHANGED; artifact ledger not stored: an external .DS_Store delta in the window) — sidecar face_holes now derived from the EMITTED surface (546 sub-spacing merges this build): zone_on_pavement 0 (the v2zonehole 13431931 frame: 3 / 52.3 m2; that frame REPLAYED with re-derived holes: 0, no other family moved). Base 22134e4f carries §40/§42, so its 54,012 rows / adjudicated 23,523 are NOT comparable with the 13431931 frame's 38,044 / 12,166
HECA  patch    base 22134e4f   lane v2connector      2026-09-14T09:46:10  /tmp/harness/HECA_20260914T083816.osm  — lane v2connector round 3 HECA build on claude/v2connector a191b26e: rc0 507.4s, body_sha c07206902a0b, ledger fd20ddfd334c, solve feasible, guard UNCHANGED — the FIRST HECA frame carrying §16g (7) (1) footprint rings (CONVEX HULL form, Part.ring flat); bodies at 96.20 1,489 -> 0
HECA  graded   base 22134e4f   lane v2connector      2026-09-14T09:46:10  /tmp/harness/HECA_20260914T083816.v2/HECA.graded.json  — lane v2connector round 3 HECA build on claude/v2connector a191b26e: rc0 507.4s, body_sha c07206902a0b, ledger fd20ddfd334c, solve feasible, guard UNCHANGED — the FIRST HECA frame carrying §16g (7) (1) footprint rings (CONVEX HULL form, Part.ring flat); bodies at 96.20 1,489 -> 0
HECA  rebake   base 22134e4f   lane v2connector      2026-09-14T09:46:10  /tmp/harness/HECA_20260914T083816.v2/HECA.rebake.json  — lane v2connector round 3 HECA build on claude/v2connector a191b26e: rc0 507.4s, body_sha c07206902a0b, ledger fd20ddfd334c, solve feasible, guard UNCHANGED — the FIRST HECA frame carrying §16g (7) (1) footprint rings (CONVEX HULL form, Part.ring flat); bodies at 96.20 1,489 -> 0
HECA  patch    base bc6b0641   lane v2connector      2026-09-14T09:46:10  /tmp/harness/HECA_20260914T093118.osm  — lane v2connector round 4 closing HECA build on claude/v2connector 70dc4acf (base main bc6b0641): rc0 597.6s, body_sha see result.json, ledger 9c1ae5a6873e, solve feasible, guard UNCHANGED — the FIRST frame carrying the TRUE OUTLINE (Part.rings, one per blob, simplified OUTWARD): 46,765 of 55,626 parts / 52,724 rings / 264,996 vertices; units 304 -> 324, plan_units_and_connectors 17.2 s, pads-span units 20 -> 17, rail concrete_3 b1 93.45 -> 76.70
HECA  graded   base bc6b0641   lane v2connector      2026-09-14T09:46:10  /tmp/harness/HECA_20260914T093118.v2/HECA.graded.json  — lane v2connector round 4 closing HECA build on claude/v2connector 70dc4acf (base main bc6b0641): rc0 597.6s, body_sha see result.json, ledger 9c1ae5a6873e, solve feasible, guard UNCHANGED — the FIRST frame carrying the TRUE OUTLINE (Part.rings, one per blob, simplified OUTWARD): 46,765 of 55,626 parts / 52,724 rings / 264,996 vertices; units 304 -> 324, plan_units_and_connectors 17.2 s, pads-span units 20 -> 17, rail concrete_3 b1 93.45 -> 76.70
HECA  rebake   base bc6b0641   lane v2connector      2026-09-14T09:46:10  /tmp/harness/HECA_20260914T093118.v2/HECA.rebake.json  — lane v2connector round 4 closing HECA build on claude/v2connector 70dc4acf (base main bc6b0641): rc0 597.6s, body_sha see result.json, ledger 9c1ae5a6873e, solve feasible, guard UNCHANGED — the FIRST frame carrying the TRUE OUTLINE (Part.rings, one per blob, simplified OUTWARD): 46,765 of 55,626 parts / 52,724 rings / 264,996 vertices; units 304 -> 324, plan_units_and_connectors 17.2 s, pads-span units 20 -> 17, rail concrete_3 b1 93.45 -> 76.70
HECA  patch    base e1014ddd   lane v2connector      2026-09-14T11:15:19  /tmp/harness/HECA_20260914T104957.osm  — lane v2connector round 5 HECA build (the §16g (8) NULL ARM) on claude/v2connector 2e97d822: rc0 578.1s, body_sha 4dd84ed258a0, solve feasible, guard UNCHANGED — §16g (8) derived pads implemented but INERT here: pad_flats.cluster_cross_links 0, so cluster_offsets returns {} and no pad moved; pad-span census byte-equal to round 4 (17 units / 845 bodies, fu:38:23 23 pads / 29.99 m)
HECA  graded   base e1014ddd   lane v2connector      2026-09-14T11:15:19  /tmp/harness/HECA_20260914T104957.v2/HECA.graded.json  — lane v2connector round 5 HECA build (the §16g (8) NULL ARM) on claude/v2connector 2e97d822: rc0 578.1s, body_sha 4dd84ed258a0, solve feasible, guard UNCHANGED — §16g (8) derived pads implemented but INERT here: pad_flats.cluster_cross_links 0, so cluster_offsets returns {} and no pad moved; pad-span census byte-equal to round 4 (17 units / 845 bodies, fu:38:23 23 pads / 29.99 m)
HECA  rebake   base e1014ddd   lane v2connector      2026-09-14T11:15:19  /tmp/harness/HECA_20260914T104957.v2/HECA.rebake.json  — lane v2connector round 5 HECA build (the §16g (8) NULL ARM) on claude/v2connector 2e97d822: rc0 578.1s, body_sha 4dd84ed258a0, solve feasible, guard UNCHANGED — §16g (8) derived pads implemented but INERT here: pad_flats.cluster_cross_links 0, so cluster_offsets returns {} and no pad moved; pad-span census byte-equal to round 4 (17 units / 845 bodies, fu:38:23 23 pads / 29.99 m)
HECA  capture  base 22134e4f   lane rwyholes         2026-09-14T09:25:27  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder--claude-worktrees-dreamy-maxwell-b04861/a16ebd19-720d-4bda-a609-9334a87ca57c/scratchpad/rwyholes/cap/HECA.pkl  — the FIRST HECA capture carrying §40 (v2_solve_replay --capture from a ritual-mounted control worktree at main 22134e4f, 151 s, guard blocked [], lane-local DSF dump + mod-cache overlays; 25,358 vertices / 1,307 faces): 43 runway-family faces, 4 with holes, 308 hole vertices — the rwyholes dry pair (crown_drops 3419 -> 3727, runway_crown 2441 -> 2749, runway_transverse 2441 -> 2749 rows) was read off it

## Registered frames: KCLT

KCLT  capture  base ec8723e9   lane v2eat            2026-09-13T12:06:34  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2eat/cap  — captures of KCLT/HECA/OTHH/SPJC by lane v2eat; base predates the 13ak pad-law break — valid
KCLT  rebake   base 864e7577   lane v2family         2026-09-13T12:12:34  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/family/frame/KCLT.rebake.json  — v2familyKCLTframe build (rc 0, 389.3 s, body_sha bb022a77f067) on main 864e7577 — POST 13ak pad-law fix; the build was CONTAMINATED (one Airport_mod_cache dump, chip 13ao) so it carries no ledger key
KCLT  graded   base 864e7577   lane v2family         2026-09-13T12:12:34  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/family/frame/KCLT.graded.json  — the design surface of the same v2familyKCLTframe build
KCLT  capture  base 70646dc8   lane v2roadramp       2026-09-13T12:44:39  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/cap/KCLT.pkl
KCLT  rebake   base 0c86fe2c   lane v2clusterpad     2026-09-13T17:03:58  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/clusterpad/laneKCLT/v2clusterpadKCLT2.v2/KCLT.rebake.json  — v2clusterpadKCLT2 build (rc 0, 477.2 s, body_sha 9f056cce3dc3, shared repo UNCHANGED) on claude/v2clusterpad over main 0c86fe2c — the FIRST KCLT frame carrying the §30 (4) CLUSTER PAD and its apron reach; no ledger key (the tree moved between key and store time)
KCLT  graded   base 0c86fe2c   lane v2clusterpad     2026-09-13T17:03:58  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/clusterpad/laneKCLT/v2clusterpadKCLT2.v2/KCLT.graded.json  — the design surface of the same v2clusterpadKCLT2 build: building80+building91 are ONE plane (union spread 4.43 -> 1.46 m) and 38 of 90 apron vertices within 60 m sit at the pad's level
KCLT  patch    base ce203b29   lane v2zonebank       2026-09-13T17:33:35  /tmp/harness/KCLT_20260913T172152.osm  — closing build of claude/v2zonebank cde84e27 (rc 0, 492.4 s, body_sha 9113da337600, ledger 6486660716cc, shared repo UNCHANGED) — §37 (3) as amended: bank 134 rings / 1,311 foot nodes, bank_foot at both owner sites (38.3 m and 10.2 m) and at the 13ax lip; census law-true 13,416
KCLT  graded   base ce203b29   lane v2zonebank       2026-09-13T17:33:35  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/zonebank/KCLT.solved.pkl  — v2_solve_replay --solved-out off cap/KCLT.pkl on BASE ce203b29 — the fixed upstream for 'v2_solve_replay --bank-from PKL --bank-walk' (2.5 s per bank-stage arm)
KCLT  graded   base 880a9293   lane v2clusterpad     2026-09-13T17:50:28  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/clusterpad/r2/v2cpKCLTr2.v2/KCLT.graded.json  — v2cpKCLTr2 (rc 0, 493.0 s, 5fb560ae50d0) — the CLUSTER arm of the matched pair; its DISARM twin (cluster_pad_min_m2=0, cluster_apron_reach_m=0) is v2cpKCLTdisarm at .../disarmOUT/v2cpKCLTdisarm.v2/
KCLT  rebake   base 880a9293   lane v2clusterpad     2026-09-13T17:50:28  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/clusterpad/r2/v2cpKCLTr2.v2/KCLT.rebake.json  — the rebake plan of the same v2cpKCLTr2 build
KCLT  graded   base 952924e9   lane v2clusterpad     2026-09-13T18:15:42  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/clusterpad/c3/v2cpKCLTc3.v2/KCLT.graded.json  — round-3 CLUSTER arm (13cc reach: population minus no-step-coupled apron, priced at apron_trend); its matched DISARM twin is .../d3/v2cpKCLTd3.v2 and the PAD-ONLY attribution arm .../padonly/ is BYTE-IDENTICAL to the disarm
KCLT  patch    base 8fce79cb   lane v2hairline       2026-09-13T17:43:19  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2hairline/kclt_arm.osm  — §39 ARM patch (harness tag v2hairline_kclt_patch): shore weld dropped 2 bank nodes, worst 0.0198 mm at 35.2031709,-80.9454997 (the 723,015-sliver site)
KCLT  graded   base e88ed84b   lane v2clusterpad     2026-09-13T18:41:09  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/clusterpad/p5/v2cpKCLTp5.v2/KCLT.graded.json  — round-4 PAD-ONLY arm (reach 0, merge EFFECTIVE: building91 221.52, union spread 1.07); its matched DISARM twin is .../d4/v2cpKCLTd4.v2 (bde3f0aff32e). Taxi family 2,406 moved worst 2.07 m between the two — the merge's own, the reach is off in both
KCLT  graded   base 8841c106   lane v2clusterpad     2026-09-13T18:58:24  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/clusterpad/p6/v2cpKCLTp6.v2/KCLT.graded.json  — round-5 PAD-ONLY arm under the §30 (4) (5) GATE — BYTE-IDENTICAL to its DISARM twin .../d4/v2cpKCLTd4.v2 (both bde3f0aff32e): building91 yields (65.81 m from the terminal, a part-box artefact), taxi family 0 moved
KCLT  patch    base 00d8b05c   lane v2hairline       2026-09-13T21:16:09  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2hairline/kclt_r2.osm  — §39 round 2 arm patch: hairline_pair adjudicated 0, emitted sub-spacing segments 799 -> 11 (all the deliberate triangle floor)

## Registered frames: SPJC

SPJC  patch    base 95c78040   lane v2spjc327        2026-09-13T15:52:21  /tmp/harness/SPJC_20260913T154126.osm  — scout v2spjc327 SPJC build 2026-09-13, rc0 121.7s, body_sha e61277b2bbbc, artifact 7857e8587009, solve=feasible, guard UNCHANGED; reproduces owner 1.0.327 tile -13-078 structures line exactly
SPJC  graded   base 95c78040   lane v2spjc327        2026-09-13T15:52:21  /tmp/harness/SPJC_20260913T154126.v2/SPJC.graded.json  — scout v2spjc327 SPJC build 2026-09-13, rc0 121.7s, body_sha e61277b2bbbc, artifact 7857e8587009, solve=feasible, guard UNCHANGED; reproduces owner 1.0.327 tile -13-078 structures line exactly
SPJC  rebake   base 95c78040   lane v2spjc327        2026-09-13T15:52:21  /tmp/harness/SPJC_20260913T154126.v2/SPJC.rebake.json  — scout v2spjc327 SPJC build 2026-09-13, rc0 121.7s, body_sha e61277b2bbbc, artifact 7857e8587009, solve=feasible, guard UNCHANGED; reproduces owner 1.0.327 tile -13-078 structures line exactly
SPJC  patch    base 0c86fe2c   lane v2spjc           2026-09-13T17:03:04  /tmp/harness/v2spjc-r2.osm  — lane v2spjc closing SPJC build on claude/v2spjc 1992e754 (base main 0c86fe2c): rc0 111.2s, body_sha 0c903ea7b254, artifact 60993cdd0302, solve=optimal, guard UNCHANGED; structures bores 10 underpasses 0 tunnels 8 decks 0 refused 6 (scout base 95c78040: 59/19/18/4/31)
SPJC  graded   base 0c86fe2c   lane v2spjc           2026-09-13T17:03:04  /tmp/harness/v2spjc-r2.v2/SPJC.graded.json  — lane v2spjc closing SPJC build on claude/v2spjc 1992e754 (base main 0c86fe2c): rc0 111.2s, body_sha 0c903ea7b254, artifact 60993cdd0302, solve=optimal, guard UNCHANGED; structures bores 10 underpasses 0 tunnels 8 decks 0 refused 6 (scout base 95c78040: 59/19/18/4/31)
SPJC  rebake   base 0c86fe2c   lane v2spjc           2026-09-13T17:03:04  /tmp/harness/v2spjc-r2.v2/SPJC.rebake.json  — lane v2spjc closing SPJC build on claude/v2spjc 1992e754 (base main 0c86fe2c): rc0 111.2s, body_sha 0c903ea7b254, artifact 60993cdd0302, solve=optimal, guard UNCHANGED; structures bores 10 underpasses 0 tunnels 8 decks 0 refused 6 (scout base 95c78040: 59/19/18/4/31)
SPJC  patch    base 6ec68b44   lane v2connector      2026-09-13T21:58:13  /tmp/harness/SPJC_20260913T214930.osm  — lane v2connector closing SPJC build on claude/v2connector 9b67e568 (base main 6ec68b44): rc0 110.9s, body_sha 545886ed769d, artifact ledger 5fe4d215e11d, solve optimal, guard UNCHANGED — §16g (6) connector law: xp11_007__b0 / xp11_010__b0 members of fu:0:0@cluster_pad at 19.56, unit_connectors_cut 0, unit_split_authored 0
SPJC  graded   base 6ec68b44   lane v2connector      2026-09-13T21:58:13  /tmp/harness/SPJC_20260913T214930.v2/SPJC.graded.json  — lane v2connector closing SPJC build on claude/v2connector 9b67e568 (base main 6ec68b44): rc0 110.9s, body_sha 545886ed769d, artifact ledger 5fe4d215e11d, solve optimal, guard UNCHANGED — §16g (6) connector law: xp11_007__b0 / xp11_010__b0 members of fu:0:0@cluster_pad at 19.56, unit_connectors_cut 0, unit_split_authored 0
SPJC  rebake   base 6ec68b44   lane v2connector      2026-09-13T21:58:13  /tmp/harness/SPJC_20260913T214930.v2/SPJC.rebake.json  — lane v2connector closing SPJC build on claude/v2connector 9b67e568 (base main 6ec68b44): rc0 110.9s, body_sha 545886ed769d, artifact ledger 5fe4d215e11d, solve optimal, guard UNCHANGED — §16g (6) connector law: xp11_007__b0 / xp11_010__b0 members of fu:0:0@cluster_pad at 19.56, unit_connectors_cut 0, unit_split_authored 0

## Registered frames: CYXY

CYXY  patch    base 8dac3c6b   lane v1settings       2026-09-13T12:56:32  /tmp/harness/v1settings_base.osm  — base arm: CYXY --engine v2 at main 8dac3c6b, body_sha fc59980475f5 (v1-retirement stage A control)
CYXY  patch    base 9ae9e5a9   lane v1settings       2026-09-13T12:56:32  /tmp/harness/v1settings_lane.osm  — lane arm: CYXY, no --engine flag, body_sha fc59980475f5 — byte-identical to the base arm
CYXY  patch    base dc5517c0   lane solvemodel       2026-09-13T15:55:54  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/base_CYXY/CYXY_20260913T155123.osm  — BASE arm, solve_model retirement closing test; body_sha ca2c7bbaa57e, 314 ways / 4690 nodes / 344 verify rows
CYXY  patch    base dc5517c0   lane solvemodel       2026-09-13T15:55:54  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/lane_CYXY/CYXY_20260913T155153.osm  — LANE arm (claude/solvemodel fdd291e9); body_sha ca2c7bbaa57e — byte-identical to the base arm, patch cmp-clean
CYXY  patch    base ce203b29   lane v2zonebank       2026-09-13T17:33:35  /tmp/harness/CYXY_20260913T173248.osm  — CYXY control on claude/v2zonebank cde84e27 (rc 0, 16.4 s, body_sha b38fbb12b262) — census law-true 1,087, bank_across_seam 0, stacked_nodes 0 (the RULINGS 10g plateau-tearing class clean)
CYXY  patch    base fef82b29   lane v2slivers        2026-09-14T09:05:36  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2slivers/cyxy/v2sl_cyxy2.osm  — CYXY control, lane arm (claude/v2slivers 88dfed33): rc 0, 13.6 s, ways 268, body_sha 018092d831df. NOT byte-identical to the base arm and lawfully so: CYXY carries 12 zone slivers / 339 m2 and 4 hairline hole rings at base, all dissolved/suppressed. Base arm v2sl_cyxy_base (main fef82b29): 284 ways, body_sha 673393ea5af0, 121 graded_strip faces / 12 slivers, 13 rings / 4 hairline
CYXY  patch    base 4c6f467c   lane v2cost2          2026-09-14T10:52:37  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2cost2/lane/CYXY.osm/cyxylane.osm  — CYXY control, LANE arm (claude/v2cost2 12b29e6c): rc 0, 12.9 s, body_sha 018092d831df — cmp-IDENTICAL to the base arm at main 4c6f467c in scratchpad/v2cost2/base/CYXY.osm/cyxybase.osm (13.2 s, same sha)
CYXY  patch    base 55cf0fe3   lane v2cost2          2026-09-14T11:31:42  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2cost2/lane/CYXY_r2.osm/cyxyr2.osm  — CYXY control, round 2 lane arm (claude/v2cost2 7bc09ea7): rc 0, 14.2 s, body_sha 018092d831df, cmp-IDENTICAL to the base arm scratchpad/v2cost2/base/CYXY.osm/cyxybase.osm

## Standing discipline (unchanged for every lane; the long form is `.claude/agents/lane.md`)

- Worktree: `tools/harness/lane_worktree.sh up <lane> <base sha>`; branch `claude/<lane>`.
  `git merge main` FIRST if main has moved past the base sha.
- `Ortho4XP/venv/bin/python tools/blast.py <file>` before editing each source
  file; a file past 1,000 lines is a warning to reconsider its architecture (split by
  responsibility when it no longer fits; past 1,500 split before merging — owner 13bz).
- ONE closing build through the harness (v2 is the only engine, RULINGS
  2026-09-13au — there is no `--engine` flag); base arms cut with
  `git archive <sha> src`, never another live checkout.
- NEVER write `/Users/noah/XPTerrainBuilderData` or `/Users/noah/X-Plane 12/Custom Scenery/`;
  no `--refresh-data`; every run prints `[guard] shared repo UNCHANGED`;
  lane-local `O4_DSF_CACHE_DIR` / `O4_AIRPORT_MOD_CACHE_DIR` under your scratchpad.
- Any wait loop is bounded (`timeout N` or `$SECONDS`); prefer foreground.
- Suite from `Ortho4XP/` twice: `venv/bin/python -m pytest -q --no-header -p no:cacheprovider -rfE tests/auto_patch_v2 tests/test_harness.py tests/test_role_edge_census.py`.
- Attempt cap two per rule; a bar that moves backwards twice → delete the code, report the measurement.
- Consumer census (RULINGS 2026-08-30l) in the spec MEASURED block before any consumer is edited.
- Extend tools, never fork; INDEX row + twin for any new option. Do NOT merge into main; do NOT write RULINGS.
- Read law with `tools/docq.py spec '§N'`, `tools/docq.py ruling 13xx`, `tools/docq.py index <name>`;
  find captures with `tools/harness/frames.py list [ICAO]`; register yours when done.
- REPORT: branch + sha; per-bar before → after with the frame named; what you did NOT do;
  intent questions with their measurement; files touched.

