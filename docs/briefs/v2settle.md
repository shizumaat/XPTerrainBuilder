# Brief pack — lane `v2settle`

Base: main `e0eb6d41` · generated 2026-09-14 by `tools/brief_pack.py`

Read THIS file first and whole. Do not grep the spec, RULINGS or INDEX monoliths for
what is here; use `tools/docq.py` for anything else you need.

## Task

THE AIRSIDE SOLVE MUST SETTLE: the hard set at HECA/KCLT settles or names its infeasible pairs (RULINGS 13y/13ab/14as)

## The brief

THE AIRSIDE SOLVE MUST SETTLE (RULINGS 13y (B)/13ab — the first-ranked standing debt; 14as: stage 1 alone leaves 42 of 161,690 hard rows unsettled at HECA, max 0.1794 m; KCLT `LAG NOT SETTLED after 3 of 3 rounds`, ~4,000 one-way rows moving, worst leader move 0.317 m — 13dh). Read `tools/docq.py spec '§20a'` via `tools/docq.py spec '§32 (4)'` (the §20a block: lag = convergence condition, 3 rounds + named failure), `tools/docq.py spec '§20b'` (the staged solve, ships OFF), `tools/docq.py ruling 13y 13ab 13ac 14as 14an`. Site: `Ortho4XP/src/auto_patch_v2/solve/design.py` (the augmented-Lagrangian hard set: `hard_weight` 300000, `shift[hard_i] = mu/rho`, the one `shift` vector shared with the one-way lag — 13db's finding; `_solve_stage`; the settle test), `solve/api.py`, `solve/design_report.py`. MEASURE FIRST on the registered HECA capture (`frames.py list HECA` — the v2staged OFF/FINAL frames; `v2_solve_replay --capture` if a fresh one is needed, registered) with `staged_solve = true` and stage 1 ALONE: the 42 unsettled hard rows — which families, where, demanded vs allowed, and WHY they do not settle (infeasible pairs: two hard rows that cannot both hold — 13de's apron ceiling vs the 5 % pavement ceiling class? a residual that the multiplier update cannot close in 3 rounds? the shared `shift` vector overwritten by the lag?). Then FIX at the cause: (a) if the multiplier update is the limit — separate the hard multipliers from the one-way lag (a second shift vector; 13db named it), raise the round cap where the residual is still falling (§20a: lag = convergence condition, not a fixed count — stop when max residual < `hard_tol_m` or when the decrease stalls, name the failure otherwise); (b) if two hard rows are infeasible together — name the pair as a CRITICAL in the design report (`hard_infeasible_pair`) and do NOT trade them silently; (c) if the airside problem is perturbed by non-airside inputs — that is lane v2padvert's, not yours. Bars: HECA stage-1 hard set SETTLED (0 rows over `hard_tol_m` + 0.01, or every survivor named as an infeasible pair); KCLT the same on its registered capture (the `LAG NOT SETTLED` line gone or named); the solve wall ≤ 1.5× today's; byte-identity NOT expected (a settled solve moves) — instead the design report's settled/hard/lag lines before → after and the census ADJUDICATED before → after on HECA and KCLT (dry replay, matched arms, one tree); CYXY/SPJC settled already? (say). Twins: a synthetic hard set that the 3-round lag leaves at 0.05 m settles under the new rule; an infeasible pair is named, not traded. Files: `solve/design.py`, `solve/api.py`, `solve/design_report.py`, `law/emit.toml` (`[design]` keys). NOT yours: `constraints/`, `classify/`, `airport/`, `planar/`, `emit/`. No build unless the replay cannot answer (then ONE HECA).

## Bars

- HECA stage-1 (airside) hard set: 42 unsettled rows → 0 over `hard_tol_m` + 0.01, or every survivor named as an infeasible pair with both rows.
- KCLT: `LAG NOT SETTLED after 3 of 3 rounds` → settled or named; worst leader move 0.317 → ≤ 0.02.
- Design report settled/hard/lag lines and census ADJUDICATED before → after on HECA and KCLT (matched dry replays, one tree).
- Solve wall ≤ 1.5× today (HECA 117.9 s single / 95.8 staged).
- Suite twice.

## Files

Yours: `Ortho4XP/src/auto_patch_v2/solve/design.py`, `Ortho4XP/src/auto_patch_v2/solve/api.py`, `Ortho4XP/src/auto_patch_v2/solve/design_report.py`, `Ortho4XP/src/auto_patch_v2/law/emit.toml`
Other lanes' (do not touch): `Ortho4XP/src/auto_patch_v2/constraints/`, `Ortho4XP/src/auto_patch_v2/classify/`, `Ortho4XP/src/auto_patch_v2/planar/`

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

## Spec (design-surface) §20b

## §20b THE STAGED SOLVE — AIRSIDE SOLVES FIRST, EVERYTHING ELSE CONFORMS (owner RULINGS 2026-09-13dh, ordered 2026-09-14an) — lane `v2staged`

"Airside is king" has been a POSTURE priced into rows (a one-way ruling, a
lagged leader, a withdrawn ceiling pair) and measured as a residual every
round since 13dh: `v2roadcontact` r2 met "no groundside row binds an airside
column" and still moved 36 airside vertices; `v2padcluster` r4/r5 refuted the
one-way skirt three times and still shipped 9,573 moved airside vertices,
the runway 885 of them (worst 0.390 m).  A LAGGED row is not a fixed value:
a pad bound to airside only by lagged rows has nothing holding it inside a
round.  The mechanism the posture needs is ARCHITECTURAL, not a price:

1. **STAGE 1 — THE AIRSIDE PROBLEM ALONE.**  The columns are the vertices of
   AIRSIDE PAVEMENT faces — every role that is `pavement_roles` (a value role
   that is not a structure), whose `role_side` is `airside`, and that is not
   RIGID: the runway family, the taxi family and the apron, and nothing else.
   One derivation site, `solve/design_roles.airside_stage_roles`, read from
   the law tables; the strip / clearance / boundary family (airside by
   `role_side` but not pavement) and the pad (`building`, rigid) are stage 2.
   Every row whose every COLUMN is airside is assembled — the hard rulings,
   the seam pins (§38), the chords and crowns, within-shape, no-step,
   taxi_box, junction_mesh, transverse, the apron tiers, EAT — and every row
   carrying a free column that is not airside is DROPPED.  A row footed on a
   `Pin` keeps it: a pin is a constant, not a column.  The stage runs the
   whole solve, its polish and BOTH projections, so what stage 1 returns is
   the CERTIFIED airside surface.
2. **STAGE 2 — THE WHOLE PROBLEM WITH AIRSIDE FIXED.**  Every airside column
   stage 1 gave a LEVEL is SUBSTITUTED as a constant at its stage-1 value —
   eliminated from the unknowns by the reduction, exactly as a `Pin` is.  A
   row coupling airside to a pad, a road or the ground then has a CONSTANT on
   its airside side: it is one-way BY CONSTRUCTION, and neither the `follows=`
   machinery nor the lag is needed for it (the lag stays for the rows whose
   leader is itself groundside).  Airside moved between the two stages is
   zero by construction — not a bound, not a tolerance, not a residual.
3. **SUBSTITUTION, NOT A ±`hard_tol_m` BOUND, AND WHY.**  The design surface
   is a least-squares problem with a one-sided ACTIVE SET (`solve/design.py`),
   not a bounded LP: there is no bound machinery to warm-start, and a
   ±`hard_tol_m` box would have to be minted as two one-sided rows per airside
   vertex at `hard_weight` — ~40,000 new hard rows at HECA, added to the very
   set that already does not settle (13y (B), 13ab), buying a surface that may
   move every airside vertex by 2 cm.  Elimination costs nothing, removes the
   columns from the factorisation (stage 2 is SMALLER than today's single
   solve), and holds exactly.  `hard_tol_m` then bounds nothing here; it is
   quoted only as the bar the measurement is read against.
4. **A COLUMN STAGE 1 DID NOT LEVEL IS NOT FIXED** (§23.4's principle).  An
   airside column reached by no always-on row in stage 1 — no bending, no
   chord, no trend, no datum, no level belt — has no level there; its
   least-squares value is the sentinel, and fixing it would pin the crater.
   Such columns stay FREE in stage 2 and the report counts them
   (`stage1_unlevelled`).

**THE CONSUMER CENSUS** (owner RULINGS 2026-08-30l), every consumer of the
solved vertex map and of the assembled design problem, ruled before any was
edited:

| Consumer | file:site | what it assumes of ONE solve | ruling |
|---|---|---|---|
| the pipeline's solve call | `pipeline/build.py:740` | one `solve_design` → one `Solution`, one `DesignReport`, one `wall["solve"]` | **CHANGED**: the call is unchanged (the staging lives inside `solve_design`); `wall["solve"]` stays the WHOLE solve and the two stage clocks are printed from the report (`stage1_wall_s` / `stage2_wall_s`) |
| the returned `Solution` | `solve/api.py` | `z`, `status`, `iterations`, `wall_s`, `residual` | **CHANGED**: `z` IS stage 2's (airside values are stage 1's, by identity); `status` is the WORSE of the two stages; `iterations` the sum; `residual` is computed once, on the final z over the whole `ConstraintSet` — unchanged |
| the design REPORT | `solve/design_report.py` | every counter describes one problem | **CHANGED**: the returned report is STAGE 2's, plus a `stages` block carrying stage 1's counters and both clocks; `line()` gains one `staged (§20b)` clause; `as_dict()` gains `stages` (a nested value under the existing `design` sidecar key — no new sidecar key, no `SIDECAR_KEYS` edit) |
| the HARD SET read | `design.read_hard_set` / `line()` | every hard row carries a column and is scaled to metres (`2/Σ|c|` over the REDUCED row) | **CHANGED**: in stage 2 an airside hard row carries NO column, so its reduced row sum is 0 and the metre scaling would silently read it in raw units. Stage 2's hard read is over the rows that still carry a column; the airside hard rows are read in STAGE 1, where they are enforced; the report's `hard_rows` / `hard_active` / `hard_max_violation_m` are the COMBINATION, and `HARD SET SETTLED` is the conjunction |
| the LAG | `design.py` phase B, `read_lag_failure` | a one-way row's leader is a free column to be lagged | unchanged in code, narrower in fact: a row whose leader is airside has a CONSTANT leader in stage 2 and never enters the lag (`one_way_rows` falls); §20a's named failure still reports the rows that remain |
| the RUNWAY projection | `solve/project.py:300 project_runway` | free runway columns exist | unchanged — it runs in stage 1 (where the runway is free) and is a no-op in stage 2 (`if not rep.columns: return x`), which is the certified surface being carried, not a skipped law |
| the ZONE projection (§32) | `solve/project.py:700 project_zone_bands` | ground columns and §32 (4) purity | unchanged — the ground is stage 2's; a fixed airside vertex carries no column, so it is never "pure" and can never be clamped (§32 (4) holds a fortiori) |
| `--why-hard` | `tools/v2_solve_replay.py:305` | re-assembles the FULL problem and reads every hard row at the shipped z | unchanged and still correct: the population is the full problem's hard set, read at the final surface; an airside row reads its stage-1 value |
| `--why-at` / the pressure read | `solve/why.py:82 solve_with_pressure` | re-solves and prices every law row at the final z | unchanged: the re-solve is staged like the pipeline's, and the pressure of a row is read on the FULL row set at the final z |
| `v2_solve_replay --capture` | `tools/v2_solve_replay.py` | captures load → partition → classify → planar → shape stage | unchanged (nothing captured is solve state) |
| `v2_solve_replay --replay` | `tools/v2_solve_replay.py:788` | one `solve_design`, one wall, one `rep.line()` | **CHANGED (reporting only)**: both stages replay through the one call and the report line names both; the DISARM arm is `--design-weight staged_solve=0` |
| the census FRAME | `tools/check_grade.py`, `harness/census.py` | reads the emitted patch and its sidecar | unchanged — no key added, no key changed |
| `verify` | `verify/frame.py` | reads the shipped surface | unchanged (lane `v2liftedcap` is in that file; nothing here touches it) |
| the sidecar publication | `pipeline/publication.py` | `pub["design"] = design_rep.as_dict()` | unchanged code (lane `v2liftedcap`'s file); the nested `stages` value rides the existing key |
| `displacement_by_role`, `joint_steps`, `runway_profile_block`, `taxi_trend_block`, `apron_trend_block`, `road_profile_agreement`, the seam residual read, the flat-site read | `pipeline/build.py:757-830` | read the FINAL z | unchanged — all read stage 2's z, which is the shipped surface |
| the `size_out` LP size | `pipeline/build.py:739` | one problem's columns/rows | **CHANGED**: it reports stage 2's size with `stage1_columns` / `stage1_rows` beside it |
| the twins that call `solve_design` | `tests/auto_patch_v2/*` | one solve of a synthetic map | unchanged where the map is all-airside (stage 2 fixes what stage 1 solved: the same surface); a twin whose map mixes a pad or a road with airside is a §20b case and reads the new law |
| `law/emit.toml [design]` | `law/design_schema.py` | the weights and limits | **CHANGED**: one new value `staged_solve` (bool, default true) — the arm switch a measurement needs, never an env gate |

BARS (HECA, ONE build on `claude/v2padcluster` + the staged solve, against
`v2padclusterHECAdisarm` AND the r5 shipped arm `a602bba1b858`): airside
vertices moved vs DISARM 0 by construction and measured (today 9,573; the
runway 885, worst 0.390 m); the terminal body on `building298` at 72.6 ±
0.02; `pad_airside_weld` before → after; `pad_cluster_mismatch` unchanged at
14; stage-2 airside values equal stage 1's to 1e-9 (twin and build); every
hard airside ruling settled; solve wall ≤ 1.5× the single solve, both stages
named; CYXY byte-identical or the diff named; suite twice.

### §20b MEASURED (lane `v2staged`, branch `claude/v2staged` off `claude/v2padcluster` a3185dbb + main; HECA)

**THE ARCHITECTURE IS BUILT AND IT HOLDS BY CONSTRUCTION.**  Stage 2's
reduction gives an airside-pavement vertex NO COLUMN (`test_v2staged.py::
test_stage_two_carries_no_airside_column`), the shipped z on every airside
vertex IS stage 1's (`…is_stage_ones`, 1e-9), and a row coupling airside to
a pad or a road keeps only its groundside columns — one-way with no
`follows=`, no lag, no skirt (`…has_a_constant_on_its_airside_side`).  The
single solve on the SAME map lands airside elsewhere, so the instrument is
not vacuous.  It is also CHEAPER: the offline HECA replay pair reads
**95.8 s staged (stage 1 90.3 + stage 2 5.5) against 117.9 s single** — 0.81×
against a 1.5× bar — and the closing builds read **416.0 s against 476.3 s**.

**THE MATCHED PAIR IS EXACT.**  The OFF arm built on this tree
(`v2stagedHECAoff`, 476.3 s) has `body_sha 18e51b7d084e` — byte for byte
`v2padcluster` r5's own shipped arm (ledger `a602bba1b858`).  Everything
merged since changed nothing at HECA, so the r5 and DISARM frames are
lawful controls for this lane's numbers.

| arm (HECA, one tree) | `body_sha` | build | airside moved vs DISARM (> 0.02 m, of 19,521) | worst | runway | hard rows violated | worst |
|---|---|---|---|---|---|---|---|
| OFF = r5 shipped | `18e51b7d084e` | 476.3 s | **8,976** | 7.71 m | 885 / 0.390 m | 1,021 / 365,395 | 2.984 m |
| staged, first form | `943df8b90952` | 454.5 s | 9,936 | 7.40 | 477 / 1.570 | ~3,300 | 4.652 |
| staged + (1b) only | `9a873f30aea4` | 557.0 s | 11,144 | 7.41 | 990 / 1.540 | — | — |
| **staged FINAL** (1b + 1c) | `266b56b5a358` | **416.0 s** | **10,371** | 7.38 | 477 / 1.560 | 3,260 / 365,395 | 5.314 |

**14an's BAR IS NOT MET, AND THE MOVER IS NOT THE COUPLING.**  With (1b) no
pad, road, zone, foot or reach row is in stage 1 at all, yet airside still
moves against DISARM — and it moves EVERYWHERE: 2,495 of the moved vertices
lie within 25 m of a pad, 3,774 lie 300–1,000 m away and **405 lie more
than a kilometre from the nearest pad** (worst 0.91 m there).  Two causes,
neither of them a row from the conforming side:

1. **THE PAD DERIVATION CHANGES THE AIRSIDE PROBLEM ITSELF.**  Between
   DISARM and the pad arm the airside vertex set differs by 268 gone / 93
   new and the airside faces by 844 → 841 (the holes are 82 in both): the
   apron's own rings, its body datum plane and its 2-D trend are fitted
   over a different vertex set, so stage 1 is not the same problem.
2. **THE AIRSIDE SOLVE IS UNSETTLED** (13y (B), 13ab; the owner ranked it
   first among debts, 12s).  Stage 1 alone reads `42/161,690 hard rows
   violated, max 0.1794 m, NOT SETTLED` and its active set does not settle
   either.  A perturbed unsettled system lands on a different optimum, and
   that is what a moved vertex a kilometre from any pad is.

**WHAT THE CONFORMING SIDE PAYS.**  Hard rows violated 1,021 → 3,260, worst
2.984 → 5.314 m, and `--why-hard` on the replay names the classes: `pads`
4 → 199, `pavement_ceiling` 23 → 81, `road_ramp` 15 → 48, `roads` 16 → 36,
`runway_profile` 13 → **6** (the runway's own hard set IMPROVES).  The
mechanism is honest: a pad welded to a fixed apron rim cannot also hold its
own 1 % ceiling, and a service road pinched between a fixed airside contact
and its ramp ceiling cannot hold both — worst `roads.groundside_road ramp
ceiling` +2.33 m at 30.10445522994,31.39662999264.  Under the single solve
the airside yielded the centimetres that made those rows feasible; that
yielding IS what §20b forbids.

**THE CENSUS AND THE SITE** (`v2stagedHECAoff` → `v2stagedHECA3`):
adjudicated 28,413 → 29,018, law-true total 64,738 → 64,065;
`airside_no_step` 7,919 → **6,801**, `taxi_box` 3,429 → **2,854**,
`frontage_near_miss` 39 → 30; `within_shape` 49,704 → 50,678,
`transverse` 1,330 → 1,353, `pad_airside_weld` 29 → 33,
`pad_cluster_mismatch` **14 → 14** (bar met, not this lane's).  The terminal
at 30.1279552,31.403143: `building298` 72.60 → **73.05** (DISARM 72.06) —
over the owner's own 72.50 bar, 0.45 m over the brief's restatement of it.
The runway projection is stage 1's and reads BETTER: worst hard row
0.2702 → 0.020000 m with **0 elastic rows** (the single solve needed one).

**THREE DEVIATIONS, REPORTED NOT DECIDED.**

1. **§20b (1b) — A CONFORMING ROW IS NEVER STAGE 1's, even where every
   column is airside.**  The brief's rule ("every row whose every column is
   airside") admits a welded pad's skirt and flatness rows, because those
   sit between two vertices the apron already owns: the pad moving the
   apron through the back door (9,936 airside vertices with the rule as
   written).  Stage 1 therefore refuses any row that declares a `follows`
   or whose ruling head is in the law's own conformance registers
   (`solve/design_roles.conforming_rulings`).
2. **§20b (1c) — A STAGE TRIANGULATES ONLY THE FACES IT OWNS.**  The
   bending operator is assembled over every sheet face, so a pavement
   vertex on the airside boundary carries a stencil reaching into the strip
   and the stage drop refused the row entirely, leaving the airside sheet
   with no bending at its own edge (`test_crown`'s built crown drop 0.146 →
   0.558 m).  With the sheet restricted to the stage's own faces the crown
   is back at 0.146 m.  What does NOT come back is the LEVEL the airside
   sheet used to borrow from the ground's datum across that boundary:
   §23.3's "a level or tilt the datum gives a strip transmits exactly zero"
   is true for an interior stencil and FALSE at the sheet's edge, and on
   `test_v2ground`'s valley fixture the taxiway that used to sit +2.68 m
   over the valley floor now sits −3.92 m under it, the strip following to
   −5.03 m.  At HECA the same reading is inert (`off-DEM by role` identical
   to two decimals on every role), because a real taxi family carries its
   own trend.  Whether an airside sheet may take a level from the ground it
   stands on is exactly the question §20b exists to answer, and it is the
   spec author's to answer.
3. **A WELDED PAD'S CEILING IS UNREACHABLE.**  A pad whose opposite rims
   are welded to two pavements 3 % apart takes the AIRSIDE'S OWN 3 % (the
   twin measures 0.030 staged against 0.0079 single) and nothing holds its
   1 % ceiling, because 14al withdrew the two-sided ceiling row over a pair
   of two airside-shared vertices — a withdrawal whose whole purpose was to
   stop that row PULLING the airside, which under §20b it cannot do.
   Reversing it is the cheapest candidate fix for the 199 `pads` rows
   above, and it is in `constraints/pads.py`, not this lane's files.

**SHIPPED OFF.**  `[design] staged_solve = false`.  The architecture, its
twins and both arms' numbers are on the branch; the suite is 1,502 green
twice with the flag off, and every §20b twin sets the flag explicitly, so
both arms stay pinned.  Turning it on is the owner's ruling: it buys the
airside its own solve (the runway's hard set and `airside_no_step` /
`taxi_box` all improve, 60 s of build), and it costs the conforming side
2,239 more violated hard rows and the terminal 0.45 m — while NOT buying
14an's "airside moved = 0", which the unsettled airside solve and the pad
derivation's own change to the airside vertex set put out of reach of any
staging.

**NOT MEASURED** (owed): a pads-OFF staged control (the DISARM law values
with `staged_solve = true`), which would separate cause 1 from cause 2
outright; KCLT and SPJC on this tree; the terminal BODY's own-ground delta
(the object stage is not in a patch build).

## RULINGS

## 2026-09-14as v2staged + v2padcluster MERGED with BOTH mechanisms OFF (`pad_from_cluster = false`, `staged_solve = false`): main's surface is byte-unchanged; the airside is not yet invariant under pads — two prerequisites named

Lane `v2staged` @ 65351424 (on `claude/v2padcluster` a3185dbb; HECA
arms `v2stagedHECAoff` = r5's shipped `18e51b7d084e` and the staged
FINAL `266b56b5a358`; suite 1,502 twice on the branch, 1,495 on main
with the three padcluster twins arming the flag themselves). §20b
built: stage 1 = the airside pavement problem alone (runway/taxi/apron
from the law, its own polish and projections), stage 2 = everything
with every airside column SUBSTITUTED as a constant (a ±tol box would
mint ~40 k hard rows); (1b) a row with a `follows` or a conformance
head is never stage 1's even when all-airside (a welded pad's skirt
rows between two apron vertices — 9,936 moved with the rule as
written); (1c) a stage triangulates only its own faces (the bending
stencil never leaves the stage). Measured: airside moved vs DISARM
8,976 (OFF) → 10,371 (staged) — NOT the coupling: 405 moved vertices
over a kilometre from any pad; (a) the pad derivation CHANGES THE
AIRSIDE PROBLEM (268 airside vertices gone, 93 new, 844 → 841 apron
faces; the body datum and 2-D trend refit) and (b) the airside solve
is UNSETTLED (stage 1 alone: 42 of 161,690 hard rows, max 0.18 m — 13y
(B)/13ab), so a perturbed problem lands on a different optimum. The
conforming side pays (`pads` 4 → 199, `road_ramp` 15 → 48) because
airside cannot yield a centimetre — which §20b forbids. Stage clocks
90.3 + 5.5 = 95.8 s vs 117.9 single (0.81×). Terminal 72.60 → 73.05.

* RULING: both ship OFF. The airside becomes invariant under pads
  only when (i) THE PAD DERIVATION LEAVES THE AIRSIDE VERTEX SET ALONE
  — a pad clipped by airside shares the airside's EXISTING vertices
  and adds none; the body datum / 2-D trend are fitted on airside
  alone (the pads never enter the fit) — and (ii) the airside solve
  SETTLES (13y (B)/13ab — the standing first-ranked debt: 42 unsettled
  hard rows at HECA). Then staged ON gives identity by construction.
  Two lanes, in that order, before 1.0.335 arms pads at HECA.
* Deviations recorded for the spec author: §23.3 (the airside sheet
  borrowing the ground's datum across the stencil) is false under §20b
  at the sheet's edge (valley fixture +2.68 → −3.92; HECA inert); a
  welded pad's 1 % ceiling is unreachable under §20b (the two-sided
  row 14al withdrew can return, since under §20b it cannot pull).
* The OTHH customer line is untouched: OTHH on main = 1.0.334's
  surface (both flags off).

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

## 2026-09-13y — v2roadcap MERGED (eae16d6f, lane b935c72a): §37 with its consumer census §37.1 (17 rows contiguity cap, 3 `airside_edge_flip`, 11 bank — two rows changed the plan: `constraints/taxi.triangle_planes` is isotropic so the contiguity min is DROPPED not moved; `O4_Mesh_Utils._bank_rings_from_patches` reads CLOSED ways only, so open chains are closed into their ribbon and an implausible closure is refused into the harmonic extension). (1) a strict relaxation by construction (`min(transverse, min(long, cap)) == min(transverse, long, cap)`; 62 generator row counts identical line for line); (2) flips by share: LEMD 1,075 role faces 0 changed, CYXY one road back groundside; (3) the bank where load-bearing: LEMD foot nodes 2,594 → 836 (48 rings → 78 chains), 60,986 → 11,544 m, chords > 30 m 820 → 0, duplicates 5 → 0 (the padding-overlap defect the lane introduced, caught and twinned — `material_runs` folds the padding into membership); CYXY bank 649 → 153 nodes, 218 → 0 long chords. CYXY adjudicated 406 → 345 (airside 381 → 306; `taxi_box` 34 → 17, `airside_no_step` 74 → 40). Suite 1,400/0 twice on main (the four v1 bank/road suites included). TWO FINDINGS the merge carries: (A) KCLT's §37 (4) bars are NOT MEASURED — the lane's KCLT build was refused at `airport/load.py:289` (the pack's `.anchor_bak` newer than every cached dump; the shared cache has no `+35-081.dsf.anchor_bak.*.text` — KCLT never had one; the 13q chip); v2zerocrater's `fresh_pack_dump` (13w) cures this — scout `v2roadcapkclt` dispatched to build KCLT once on main and read §37 (4)'s bars (`dsf:pol51` +14.22 m at 35.2074982,−80.9296586; shapeID 791 apron +12.33; bank 1,855 stations 28.4 % load-bearing). (B) LEMD's census went the WRONG WAY: adjudicated 1,143 → 1,379 (airside 1,127 → 1,345; `taxi_box` +122, `airside_no_step` +62) — attributed by elimination (classification byte-identical; the bank arms census identically family for family; (1) a proven relaxation) to the LP landing on a different optimum of an UNSETTLED system: BOTH arms at base ec8723e9 read `HARD SET NOT SETTLED` / `LAG NOT SETTLED` at LEMD. That is a REGRESSION of 12ac (v2padceiling settled LEMD: 725 violated hard rows → 0) by something merged between 81befff0 and ec8723e9 — scout `v2unsettled2` dispatched to bisect by offline replay (the 12u instrument reproduces the shipped solve bit for bit). The owner ranked the unsettled solve first among debts (12s); its return is the top item before app 1.0.327's LEMD read is trusted.

## 2026-09-13ab — SCOUT `v2roadcapkclt` (one KCLT build on main 064e244e, 373.3 s rc 0, ledger 2951cfc994bd, `body_sha d6093e801a96`; 13w's re-dump CONFIRMED — KCLT builds under the harness). §37 (3) LANDED at KCLT: bank 1,855 stations / 34,212 m / 451 chords > 30 m → 1,876 stations of which 401 load-bearing (21.4 %), 732 foot nodes / 11,424 m / 0 chords > 30 m (max 29.94). §37 (1) and (2) DID NOT TOUCH THE OWNER'S SITES: `dsf:pol51` (item 5) +14.22 → +13.28 m at 35.2074982,−80.9296586 (the chain over 179.3 m: DEM relief 12.15 m, emitted relief 3.49 m, FOLLOW RATIO 0.287, highest fill 13.28 m — the DEM grade 6.8 % is UNDER the 8 % road cap, so the cap was never what held it); shapeID 791 → 784 `dsf:pol82` (item 7) STILL `apron`, +11.52 m max at 35.2209280,−80.9275739 — 13q read it flipped by §27 on 2 % of its perimeter and §37 (2)'s 0.2 share should have left it a road, so either the share is not read where the flip happens or the face is apron by the scorer before §27 runs. 13q's item-5 attribution was INCOMPLETE: relaxing the longitudinal cap was a proven strict relaxation and moved the site 0.94 m; a second mechanism holds the road 13 m up. Cockpit block on this build: CRITICAL motion 9 (worst 0.790 m over 57.88 m `strip_arc [stub|stub]` 35.2123806,−80.9513621; three `mid_edge_step apron|apron` 0.52–0.60 m over ~1 m at 35.2082082,−80.9412547 / 35.2137789,−80.9323169 / 35.2088523,−80.9421498; one `cross_shape` cliff 0.31 m at 35.2139545,−80.9297320), CRITICAL visual 2 (the §35 corner — this build predates ddc5b11d); vs 13w's build motion 15 → 9, worst 3.640 → 0.790 m; law-true 12,353 → 11,504; adjudicated 3,959 (airside 3,592). KCLT is UNSETTLED on all three counters (644 active-set rounds, 21/236,084 hard rows violated max 0.4144 m, 11,211 one-way rows worst leader move 0.332 m) — KCLT's own instance of 13y (B); scout `v2unsettled2` is bisecting LEMD's. Owner items at their coordinates on this build: 1 corner z−DEM −1.47, the two 5.02/4.93 m cliffs still there (pre-§35); 3 no bore/mouth within 35 m of either coordinate (13 bores / 26 mouths built, none here — §34 (5), lane `v2rampwalk`); 4 and 6 pads on their ground (+0.24 / +0.55; +1.23 / −1.48 flat pads) — the floating roofs are object-stage (v2unboxed, now merged, not in this build); 9 the terminal's 27 basin refusals are all the `paredes_*/techos_*/suelos_*_charlotte` + `Charlotte_Airport_00{5,8}_ALB` family refused under 09ag rule 5b ("a slab on datum relief, not a sunken solid"), 4.25–9.54 m under local ground and ~0 under their own render datum — the pack's flat datum plane over real relief; NOTHING in the planar or object stage addresses it yet: OWED as an owner item (the terminal complex wants ONE datum for the family — §16c (6) shared-datum unit — seated at the terminal pad's level, its pieces cut to their own ground where they stand apart). Harness notes: `--tag` collides case-insensitively with a dead run's stem (`v2roadcapKCLT`) — correct refusal; `Could not save airport info … Data+35-081.apt` warning in a lane worktree without `Tiles/` (harmless). Lane `v2roadcap2` dispatched: fix the `default_inputs` half of the 13q chip so `explain KCLT` runs, name the rows holding `dsf:pol51` at +13.28 m and the pass that classes `dsf:pol82` apron, fix both, ONE KCLT build.

## 2026-09-13ac — ATTRIBUTED (scout `v2unsettled2`, one capture at 81befff0 replayed under four trees — the 12u instrument) and RULED (Fable, spec §30 (3), §32 (4), §20a): NO merge in 81befff0..ec8723e9 re-unsettled LEMD — 12ac's "HARD SET SETTLED 0/125,572, worst 0.0130 m" was a reading of the LANE TIP af50e0bd, never of merged main. The merge's other parent 7587c7f8 carries v2frontage (§28, `constraints/pad_frontage_gs.py`, generator `groundside_frontage`, 42 rows at LEMD); replayed at 81befff0 the same capture reads 19 / 125,572 violated, worst 0.0324 m; `--drop-generator groundside_frontage` → 0 (interventional). Neither lane measured the combination; RULINGS discipline amended below. The 19 rows are all `structures.building_pad pad_slope_max ceiling` at TWO pad corners — v9295 (40.49615941816, −3.59037117965; demanded 0.0751 vs allowed 0.0427) and v9696 (40.49424548294, −3.59145556585; 0.0296 vs 0.0050) — plus one `pavement_ceiling` row at 40.46100467355, −3.54393810062 (0.9180 vs 0.8930): a 2–3 cm shortfall of a COUPLED FIXED POINT, not 12u's 2.2 m mutual infeasibility. `--why-vertex 9295`: binding families `pads` (21 rows, Σ|dual| 261) and ONE 742-term `frontage_level` Linear holding the pad 0.22 m above apron v8344, whose chain terminal is FREE. The one-way lag runs `one_way_max_rounds = 3` (`law/emit.toml:602`) and reads LAG NOT SETTLED on EVERY arm (leader move 0.302 m at 81befff0, 0.678 m on main, tol 0.01); the hard multiplier polish (`polish_rounds_max = 2`, `emit.toml:561`, whose own comment says it does not converge at any weight) runs INSIDE a lag that has not converged; §28's 42 one-way rows land in the pad columns and the wobble crosses `hard_tol_m` 0.02. `polish_rounds_max = 8` → 2 rows, still unsettled: refuted again (12u). SHIPPING ON MAIN (v2roadcap-era capture replayed at 064e244e): 5 / 126,458 violated, worst 0.129163 m at v8276 / v8273 (40.48527108321, −3.59323243501 / 40.48527109147, −3.59320294912; `building` + `graded_strip`; demanded 0.1542 vs allowed 0.0250; the pair also breaks `pavement_max_grade` 0.1542 vs 0.1250) — MINTED AFTER THE SOLVE by v2zoneclamp: `solve/project.py:623 project_zone_bands` clamps every zone-governed ground vertex into its own band (3,310 columns moved, max 8.10 m, 47 empty bands) and `solve/design.py:903-909` runs it BEFORE the hard re-read; the two vertices are clamped independently and the pad-ceiling difference opens. `--design-weight zone_projection=0` → 3 rows, worst 0.0271 m; the pre-zoneclamp tree 8d6e0475 reads 3 / 0.0393. Corpus constant (LEMD ledger corpus sha e512b4ea8c… 09-10 → 09-13); no shared-repo write (stamp-audited).

* RULINGS DISCIPLINE (Fable): a "SETTLED" claim is a claim about MERGED MAIN. From now on the merge entry quotes the three settled lines from a replay (or build) on the merge commit itself — the suite does not read them, and a lane tip is not main. The 12ac entry stands as a lane-tip reading.
* FABLE'S RULING, three laws in order (lane `v2settle`, attempt cap two each; measure each alone on the 81befff0 capture and on a fresh main capture before combining): (1) §32 (4) PURITY — a post-solve projection may clamp only a column carrying NO hard row it does not own: `project_zone_bands` refuses a zone vertex that also carries a pad-ceiling / pavement-ceiling / runway row (a `building` + `graded_strip` rim vertex) and leaves it to the solve; alone this takes main 0.1292 → 0.0271 m (measured by the scout). (2) §20a THE LAG IS A CONVERGENCE CONDITION, NOT A ROUND BUDGET — the leader/follower fixed point iterates to `one_way_tol_m` (0.01 m) or REPORTS the named failure (which rows, which leader, its last move) BEFORE the augmented-Lagrangian polish; `one_way_max_rounds` becomes a safety ceiling (≥ 20) whose hit is a named failure, never a silent stop. (3) §30 (3) THE PAD PLANE IS PROJECTED — if (1)+(2) leave the pad ceiling unsettled, each pad's rigid plane gets the runway's and the zone band's treatment: a post-solve per-body QP on its free columns onto its own 1 % ceiling (`project_runway` / `project_zone_bands` discipline), certifying `pads` the way §21.2 / §32 certify theirs, run AFTER (1)'s purity so the two projections never fight over one column; the design report then states `HARD SET SETTLED` from a re-read after every projection. The scout's row lister (`scratchpad/u2/hardrows.py`, `solve.design.assemble` + design.py's own 2/Σ|c| metre scaling) is promoted by the lane as `v2_solve_replay.py --why-hard` (INDEX row + twin) — the design report names only the worst row's ruling, never a row's vertices. Bars: LEMD `HARD SET SETTLED` / `LAG SETTLED` on a main capture (today 5 rows / 0.129 m; lag 0.678 m), the two v8276/v8273 and v9295/v9696 sites named at ≤ 0.02 m; KCLT's three counters (13ab: 644 rounds, 21 rows / 0.4144 m, lag 0.332 m) re-read on its capture — SETTLED or the failure NAMED; solve wall not worse than +10 % (`--runs 3` on the replay); runway projection and zone projection unchanged where pure; suite twice; ONE LEMD build.

## 2026-09-13db v2roadcontact round 1 reported, NOT merged: items 4/5 met, item 3's mechanism refuted, airside moved — round 2 ordered

Lane `v2roadcontact` @ bb7a0b03 (HECA build `v2roadcontactHECA2`, ledger
96f569b01af9). Item 5: `route0`'s end 108.09 → 106.66 vs the taxiway edge
106.606 (+1.474 → +0.054, step 33 % → 1.2 %). Item 4: 1.30 m → 0.05 m over
3.05 m (42.6 % → 1.6 %). HECA `road_cross_section` 21 → 28 priced,
`not_a_pair` 9,092 → 9,065; KCLT dry `road_cross_section` 373 → 280.

* REFUTED, item 3: `route7` has 8 airside mouths among its 15 vertices
  (on `pav115`/`pav131`, all at 0.00) and its 6 owned vertices sit 0.6–1.0
  m over them inside its 8 % cap — no contact law moves it. The "hill" at
  30.1116052, 31.4066985 is `apron:pav131`'s own datum (108.43) against
  ground cut to 107.85 and the road on the DEM at 109.14: an AIRSIDE datum
  question (§23), not a road one. Owner intent: "we just need this area
  lowered" — a separate read of what holds pav131 at 108.43.
* NOT MERGED: airside moved — HECA 115 airside vertices > 0.1 m (worst
  0.770 m, an apron), KCLT airside rows 3,524 → 3,656. Mechanism: the LP
  re-solve after 66 mouth targets are withdrawn + ribbon pairs priced on
  road rings that include mouth vertices. Round 2: every row involving a
  mouth/airside vertex is one-way on that vertex; withdrawing a target
  releases no airside vertex; bar = 0 airside moves > 0.1 m, KCLT airside
  ≤ 3,524.
* FINDING for a ruling: hard + one-way is not expressible in
  `solve/design` (one `shift` vector — the augmented Lagrangian's
  `shift[hard_i]` overwrites the one-way lag); the contact row is priced at
  `[design] law`, not hard. Accepted for now; owed a second shift vector
  if a hard one-way row is ever needed.
* §37 (10) (3)'s "4 rows → every ribbon" conflated violation rows with
  priced rows (15 of 18 refs were already priced) — spec text to correct
  at merge.

## Tool: v2_solve_replay

| `Ortho4XP/tools/v2_solve_replay.py` | --why-vertex V [--why-relax FAMILY ...]`; `--why-hard [N]` on either a `--replay` arm or a `--why-from PKL`) | You are iterating on the v2 SOLVE (a law table, a generator, the shape stage, the planar build) and want the runway bows / z − DEM / joints / yielded-rows figures per change WITHOUT paying for the load stage each time — the synthetic-first solve arm (CLAUDE.md BUILD ECONOMY; `docs/specs/auto-patch-v2/heca-sag-ablation/ablate_heca_pin.py` was the scratch pattern, promoted on its second use by lane v2chord, RULINGS 2026-09-08d). `--capture` runs load → **the PACK PARTITION + GROUPS** (`build.py:288-318`, owner RULINGS 2026-09-11j — folded in 2026-09-12u by lane `v2padceiling` after scout `v2unsettled` measured the trap: a capture without them carries an `Airport` with no `partition` and no `groups`, so the replay silently solves a DIFFERENT problem — no `foot_rows`, no `pad_relief` targets, no basin bodies, and the shipped LEMD hard set could not be reproduced at all; a capture predating it is now REFUSED BY NAME at replay, `capture_has_groups`) → classify → planar (which labels the SHAPES, owner RULINGS 2026-09-08k) → flat site → road profile → shape stage exactly as `pipeline/build.py` and pickles the airport, the classification, the planar map and the stage (HECA 56 s; LEMD 232 s, of which 104 s partition); `--replay` resumes from the named stage under the CURRENT tree (constraints + joint filter + yield transform + ONE solve by default — 08k (4), no joint re-solve; `shapes` rebuilds the shapes over the captured map and re-runs the stage — for a change in `planar/shapes.py` or `[terrace]`; `planar` the whole map), and prints per two-threshold runway the crown-ridge BOW, the ridge minimum, z − DEM mean/min/max, the law-tier line, `yielded_rows` per family and the max apron grade PER SHAPE with the steepest rows per family (face, grade, span, lat/lon), the shapes (count, the largest by vertices), the joints (count, gap joints, max built step, the worst with their shape pair), the road steps, and per `--site` the vertices within `--site-radius` (z − DEM, roles, shape ids, the max |dz| over a short edge = a step). `--emit DIR` writes the arm's patch through the build's own emit half so `patch_proximity_diff.py` and `undulation.py` can read a same-frame divergence on a replay arm; `--verify` runs the v2 VERIFY CENSUS on the solved surface and prints the rows per family and the DEFECT families the app's driver gates on (lane v2smooth round 2, RULINGS 2026-09-08v — a weight sweep needs the defect count per arm without a 130 s build); `--design-weight TERM=W` overrides one `emit.toml [design]` weight for the arm (the measurement arm, never a default). `--drop-generator` also accepts the pseudo-generator **`eat_ramp_reach`** (lane `v2eatramp`, spec §36 (5)): the EAT ramp's trend WITHDRAWAL is a channel edit made before the solve, not a row, so it cannot be dropped by the row filter — `eat_anchor_rect` drops the pins and their reach together, `eat_ramp_reach` the withdrawal alone (the §36 (5) before-arm). Lane v2shapes (2026-09-08): HECA capture 56 s; one pass 144–150 s (the 08g three-pass law read 357 s). `--why-from PKL --why-hump RUNWAY S0 S1` (the `solve.why` bindings and chain trace on the highest ridge vertex above the chord, from a duals solve of the SAME LP — kept out of the timed arm) with `--why-relax FAMILY ...` (relax-one-family arms: the hump's dz after a full re-solve without the family — the INTERVENTIONAL holder read). `--why-hard [N]` lists EVERY VIOLATED HARD ROW of the solved surface — generator, ruling, demanded vs allowed metres, and per vertex the id, coefficient, z, DEM, lat/lon and roles — re-assembling the design problem with `solve.design.assemble` and applying design.py's own `2 / Σ|c|` row scaling, so every violation reads in the METRES `hard_tol_m` is stated in (promoted from scout `v2unsettled2`'s `hardrows.py` on its second use, spec §32 (4), RULINGS 2026-09-13ac: `HARD SET NOT SETTLED` names ONE truncated ruling, which cost 12u a scout re-deriving the population by hand and 13ac needed the row's VERTICES to see that main's worst row was a pair the zone projection had clamped independently). **`--emit` IS THE BUILD'S WHOLE EMIT HALF SINCE 2026-09-13** (lane `v2zonebank`, §37 (3)): it ran `graded_surface` -> `write_patch` and SKIPPED `with_bank` / `with_terrain_edges`, so every `bank_foot` question asked of a replay arm read ZERO feet and looked like the defect under attribution — it now runs `pipeline/build.py:780-795` verbatim and prints the `BankReport` line. **`--bank-from SOLVED.pkl`** replays that emit half alone off a `--solved-out` pickle (KCLT 2.5 s against the 160 s `--replay`), with `--emit DIR` and/or **`--bank-walk`**: §37 (3)'s per-station ADJACENT-GROUND ZONE-2 WALK — per `adjacent_ground:*:zone2` face ring, `|z_ring - DEM(foot)|` at every station, the stations at or over `bank_materiality_m`, whether the foot point stands outside the design coverage, whether it falls in the terrain-edge no-bank region or the water cut, and whether a `bank_foot` stands within that station's OWN 1:3 reach (never the airport-wide `bank_max_width_m`, which calls a foot 200 m away near); then, off `emit/bank.with_bank`'s `station_probe` / `region_probe` attribution hooks, the banked-region station the load-bearing verdict was actually taken on and where an unbanked station stands (inside the banked region? inside a coverage HOLE?). It prices no law and counts no defects — defect counts come from `harness/census.py`. Measured basis (KCLT, base `ce203b29`, `cap/KCLT.pkl`): 233 zone2 rings / 5,647 stations, 542 at or over the 1.65 m materiality, 220 with their foot outside the coverage, **110 with no foot at all** — 110 of them inside the banked region and 109 inside a coverage hole, which is how RULINGS 2026-09-13bu item 5 was attributed to `_foot_piece`'s solid exterior disc; after the fix 8. **A CAPTURE PREDATING A TARGET CHANNEL STILL REPLAYS, AND SAYS SO** (2026-09-13, lane `v2roadcontact`): a `PlanarMap` field added since the pickle was written is simply ABSENT on the unpickled instance, so the first `dataclasses.replace` raised `AttributeError` and a REGISTERED FRAME another lane shares became unreplayable for a channel its own stage never produced; `--replay` now backfills each missing field at the dataclass's OWN default and NAMES it on stdout (the publisher derives the channel in the replay anyway). This is NOT a relaxation of the 12u groups refusal, which stands: that one is a capture solving a DIFFERENT problem, this one is a channel the capture never had. Twins: `tests/auto_patch_v2/test_v2padceiling.py` (the capture calls every pre-solve stage `pipeline/build.build` calls, read off both sources; the refusal predicate) — the rest of the replay is an instrument over `pipeline/build.py`'s own stages, which the pipeline twins cover. |

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
HECA  patch    base 0bc96357   lane v2padcluster     2026-09-14T12:30:17  /tmp/harness/v2padclusterHECA2.osm  — LANE arm of the v2padcluster matched pair (§16g (9)-(10) THE PAD IS THE CLUSTER, branch claude/v2padcluster 1a230c8f, base main 0bc96357): rc 0, 394.8 s, ways 2079, body_sha c83dfe27b38d, artifact ledger beb3e32ab119, solve feasible, guard shared repo UNCHANGED. The FIRST HECA frame whose building pads are DERIVED from the pack's clusters (1,954 clusters; pad area 867,374 -> 1,369,935 m2, 414 -> 652 faces). pad_cluster_mismatch 44; AIRSIDE 13,637 of 21,534 taxi/runway vertices moved > 0.02 m, worst 10.14 m -- the airside bar is MISSED and the branch should not merge on it
HECA  patch    base 0bc96357   lane v2padcluster     2026-09-14T12:30:17  /tmp/harness/v2padclusterHECAdisarm.osm  — BASE ARM of the v2padcluster matched pair: the SAME branch with [placement] pad_from_cluster=false, floor_split_m=0, cluster_pad_min_m2=0 (the keys' own disarm clauses), rc 0, 462.1 s, ways 1741, body_sha 97a2267cfc28, guard shared repo UNCHANGED. Reproduces the pre-14x pad derivation: 414 building faces / 867,374 m2
HECA  graded   base 0bc96357   lane v2padcluster     2026-09-14T12:30:17  /tmp/harness/v2padclusterHECA2.v2/HECA.graded.json  — LANE arm of the v2padcluster matched pair (§16g (9)-(10) THE PAD IS THE CLUSTER, branch claude/v2padcluster 1a230c8f, base main 0bc96357): rc 0, 394.8 s, ways 2079, body_sha c83dfe27b38d, artifact ledger beb3e32ab119, solve feasible, guard shared repo UNCHANGED. The FIRST HECA frame whose building pads are DERIVED from the pack's clusters (1,954 clusters; pad area 867,374 -> 1,369,935 m2, 414 -> 652 faces). pad_cluster_mismatch 44; AIRSIDE 13,637 of 21,534 taxi/runway vertices moved > 0.02 m, worst 10.14 m -- the airside bar is MISSED and the branch should not merge on it
HECA  graded   base 0bc96357   lane v2padcluster     2026-09-14T12:30:17  /tmp/harness/v2padclusterHECAdisarm.v2/HECA.graded.json  — BASE ARM of the v2padcluster matched pair: the SAME branch with [placement] pad_from_cluster=false, floor_split_m=0, cluster_pad_min_m2=0 (the keys' own disarm clauses), rc 0, 462.1 s, ways 1741, body_sha 97a2267cfc28, guard shared repo UNCHANGED. Reproduces the pre-14x pad derivation: 414 building faces / 867,374 m2
HECA  rebake   base 0bc96357   lane v2padcluster     2026-09-14T12:30:17  /tmp/harness/v2padclusterHECA2.v2/HECA.rebake.json  — LANE arm of the v2padcluster matched pair (§16g (9)-(10) THE PAD IS THE CLUSTER, branch claude/v2padcluster 1a230c8f, base main 0bc96357): rc 0, 394.8 s, ways 2079, body_sha c83dfe27b38d, artifact ledger beb3e32ab119, solve feasible, guard shared repo UNCHANGED. The FIRST HECA frame whose building pads are DERIVED from the pack's clusters (1,954 clusters; pad area 867,374 -> 1,369,935 m2, 414 -> 652 faces). pad_cluster_mismatch 44; AIRSIDE 13,637 of 21,534 taxi/runway vertices moved > 0.02 m, worst 10.14 m -- the airside bar is MISSED and the branch should not merge on it
HECA  rebake   base 0bc96357   lane v2padcluster     2026-09-14T12:30:17  /tmp/harness/v2padclusterHECAdisarm.v2/HECA.rebake.json  — BASE ARM of the v2padcluster matched pair: the SAME branch with [placement] pad_from_cluster=false, floor_split_m=0, cluster_pad_min_m2=0 (the keys' own disarm clauses), rc 0, 462.1 s, ways 1741, body_sha 97a2267cfc28, guard shared repo UNCHANGED. Reproduces the pre-14x pad derivation: 414 building faces / 867,374 m2
HECA  patch    base a1d0edfa   lane v2padcluster     2026-09-14T13:25:46  /tmp/harness/v2padclusterHECA4.osm  — LANE arm of the v2padcluster ROUND 3 pair (§16g (10) (4)-(6), branch claude/v2padcluster e75f97b1, base main a1d0edfa): rc 0, 384.4 s, ways 2088, body_sha cbefb8edcacb, artifact ledger 72fb36419b42, solve feasible, guard shared repo UNCHANGED. (4) only a WALLED body chains (Part.height_m + chain_min_height_m 2.5) on BOTH the design cluster and the object unit; (5) the pad is clipped by airside and split at its pieces; (6) pad_airside_weld census. T3 RESOLVED: largest cluster over the pad threshold 541,200 m2 / 9,334 bodies -> 171,086 m2 / 1 body; the terminal body at 30.1279552,31.403143 is +0.15 m off its own ground (was +7.50). MISSED: airside 17,482 of 29,465 vertices moved > 0.02 m (worst 12.15, runway 856/3,426 worst 3.14); pad_cluster_mismatch 27; pad_airside_weld 24 (disarm 16); terminal SURFACE 80.94 vs bar 72.50; constraints +55 %. Design surface byte-identical to v2padclusterHECA3
HECA  graded   base a1d0edfa   lane v2padcluster     2026-09-14T13:25:46  /tmp/harness/v2padclusterHECA4.v2/HECA.graded.json  — LANE arm of the v2padcluster ROUND 3 pair (§16g (10) (4)-(6), branch claude/v2padcluster e75f97b1, base main a1d0edfa): rc 0, 384.4 s, ways 2088, body_sha cbefb8edcacb, artifact ledger 72fb36419b42, solve feasible, guard shared repo UNCHANGED. (4) only a WALLED body chains (Part.height_m + chain_min_height_m 2.5) on BOTH the design cluster and the object unit; (5) the pad is clipped by airside and split at its pieces; (6) pad_airside_weld census. T3 RESOLVED: largest cluster over the pad threshold 541,200 m2 / 9,334 bodies -> 171,086 m2 / 1 body; the terminal body at 30.1279552,31.403143 is +0.15 m off its own ground (was +7.50). MISSED: airside 17,482 of 29,465 vertices moved > 0.02 m (worst 12.15, runway 856/3,426 worst 3.14); pad_cluster_mismatch 27; pad_airside_weld 24 (disarm 16); terminal SURFACE 80.94 vs bar 72.50; constraints +55 %. Design surface byte-identical to v2padclusterHECA3
HECA  rebake   base a1d0edfa   lane v2padcluster     2026-09-14T13:25:46  /tmp/harness/v2padclusterHECA4.v2/HECA.rebake.json  — LANE arm of the v2padcluster ROUND 3 pair (§16g (10) (4)-(6), branch claude/v2padcluster e75f97b1, base main a1d0edfa): rc 0, 384.4 s, ways 2088, body_sha cbefb8edcacb, artifact ledger 72fb36419b42, solve feasible, guard shared repo UNCHANGED. (4) only a WALLED body chains (Part.height_m + chain_min_height_m 2.5) on BOTH the design cluster and the object unit; (5) the pad is clipped by airside and split at its pieces; (6) pad_airside_weld census. T3 RESOLVED: largest cluster over the pad threshold 541,200 m2 / 9,334 bodies -> 171,086 m2 / 1 body; the terminal body at 30.1279552,31.403143 is +0.15 m off its own ground (was +7.50). MISSED: airside 17,482 of 29,465 vertices moved > 0.02 m (worst 12.15, runway 856/3,426 worst 3.14); pad_cluster_mismatch 27; pad_airside_weld 24 (disarm 16); terminal SURFACE 80.94 vs bar 72.50; constraints +55 %. Design surface byte-identical to v2padclusterHECA3
HECA  patch    base a1d0edfa   lane v2padcluster     2026-09-14T14:21:29  /tmp/harness/v2padclusterHECA5.osm  — LANE arm of the v2padcluster ROUND 4 pair (§16g (10) (7)-(8), branch claude/v2padcluster 9a4bd0e3, base main a1d0edfa): rc 0, 420.6 s, ways 1916, body_sha 1112755a1db9, artifact ledger 85c18b3071e6, solve feasible, guard shared repo UNCHANGED. (7) LEAVES GET NO PAD (39 % of the outline area dropped: 359,152 m2 in 1,518 leaf pads + 175,708 m2 under the threshold); (8) the plate is DROPPED AT AN AIRSIDE RIM (8,967 skirt rows at the pad slope ceiling, 30 pads wholly inside pavement keep a two-sided plate). MET: the terminal at 30.1279552,31.403143 SURFACE 72.60 (bar 72.50, DISARM 72.07) with its body on the WALLED cluster pad building298 at 72.62, own ground +0.08 m (+0.55 m of fill, cluster fu:38:96@cluster_pad). MISSED: airside 14,263 of 29,783 moved > 0.02 m worst 4.55 m (the RUNWAY 1,021 of 3,426 worst 0.41 m, down from 3.14); pad_cluster_mismatch 14 (disarm 33); pad_airside_weld 16 (disarm 3, worst 1.135 m); constraints +15.7 %
HECA  graded   base a1d0edfa   lane v2padcluster     2026-09-14T14:21:29  /tmp/harness/v2padclusterHECA5.v2/HECA.graded.json  — LANE arm of the v2padcluster ROUND 4 pair (§16g (10) (7)-(8), branch claude/v2padcluster 9a4bd0e3, base main a1d0edfa): rc 0, 420.6 s, ways 1916, body_sha 1112755a1db9, artifact ledger 85c18b3071e6, solve feasible, guard shared repo UNCHANGED. (7) LEAVES GET NO PAD (39 % of the outline area dropped: 359,152 m2 in 1,518 leaf pads + 175,708 m2 under the threshold); (8) the plate is DROPPED AT AN AIRSIDE RIM (8,967 skirt rows at the pad slope ceiling, 30 pads wholly inside pavement keep a two-sided plate). MET: the terminal at 30.1279552,31.403143 SURFACE 72.60 (bar 72.50, DISARM 72.07) with its body on the WALLED cluster pad building298 at 72.62, own ground +0.08 m (+0.55 m of fill, cluster fu:38:96@cluster_pad). MISSED: airside 14,263 of 29,783 moved > 0.02 m worst 4.55 m (the RUNWAY 1,021 of 3,426 worst 0.41 m, down from 3.14); pad_cluster_mismatch 14 (disarm 33); pad_airside_weld 16 (disarm 3, worst 1.135 m); constraints +15.7 %
HECA  rebake   base a1d0edfa   lane v2padcluster     2026-09-14T14:21:29  /tmp/harness/v2padclusterHECA5.v2/HECA.rebake.json  — LANE arm of the v2padcluster ROUND 4 pair (§16g (10) (7)-(8), branch claude/v2padcluster 9a4bd0e3, base main a1d0edfa): rc 0, 420.6 s, ways 1916, body_sha 1112755a1db9, artifact ledger 85c18b3071e6, solve feasible, guard shared repo UNCHANGED. (7) LEAVES GET NO PAD (39 % of the outline area dropped: 359,152 m2 in 1,518 leaf pads + 175,708 m2 under the threshold); (8) the plate is DROPPED AT AN AIRSIDE RIM (8,967 skirt rows at the pad slope ceiling, 30 pads wholly inside pavement keep a two-sided plate). MET: the terminal at 30.1279552,31.403143 SURFACE 72.60 (bar 72.50, DISARM 72.07) with its body on the WALLED cluster pad building298 at 72.62, own ground +0.08 m (+0.55 m of fill, cluster fu:38:96@cluster_pad). MISSED: airside 14,263 of 29,783 moved > 0.02 m worst 4.55 m (the RUNWAY 1,021 of 3,426 worst 0.41 m, down from 3.14); pad_cluster_mismatch 14 (disarm 33); pad_airside_weld 16 (disarm 3, worst 1.135 m); constraints +15.7 %
HECA  patch    base 9a8b253b   lane v2padcluster     2026-09-14T15:11:08  /tmp/harness/v2padclusterHECA7.osm  — SHIPPED arm of v2padcluster ROUND 5 (§16g (10) (8) refined, branch claude/v2padcluster 95c48df7, base main 9a8b253b): rc 0, 451.5 s, ways 1916, body_sha 18e51b7d084e, artifact ledger a602bba1b858, solve feasible, guard shared repo UNCHANGED. [placement] pad_skirt_m ships at 0 = the airside-SHARED vertices alone (round 4's scope) PLUS 14al's withdrawal of the two-sided ceiling row over a pair of two shared vertices (4,008 pairs dropped). THE BEST ARM: airside 9,573 of 21,523 moved > 0.02 m (r4 10,048, the 25 m band 10,683), the RUNWAY 885 worst 0.390 m (r4 1,021/0.410, band 1,394/0.570); pad_cluster_mismatch 14; pad_airside_weld 29 worst 1.135; law-true 64,844; the terminal body on building298 at 72.60, own ground +0.07 m. Constraints 109.69 s = +31.4 % (bar +20 %, MISSED — the pad population, not the skirt)
HECA  patch    base 9a8b253b   lane v2padcluster     2026-09-14T15:11:08  /tmp/harness/v2padclusterHECA6.osm  — the 25 m BAND arm of v2padcluster ROUND 5 — MEASURED AND REFUTED (branch claude/v2padcluster b5e29894): rc 0, 433.5 s, body_sha ee7d0f56911c, artifact ledger b63e49fd65b0, guard shared repo UNCHANGED. Worse than round 4's scope on EVERY airside bar: airside 10,048 -> 10,683, the runway 1,021 -> 1,394 and its worst 0.410 -> 0.570 m, pad_airside_weld 16 -> 21 (worst 1.135 -> 2.42), law-true 63,904 -> 66,771 — for the terminal body +0.08 -> +0.00 m. A wider band softens more of the pad and a softer pad moves more of the apron inside the same ceiling. pad_skirt_m keeps 25.0 as its design value and ships at 0
HECA  graded   base 9a8b253b   lane v2padcluster     2026-09-14T15:11:08  /tmp/harness/v2padclusterHECA7.v2/HECA.graded.json  — SHIPPED arm of v2padcluster ROUND 5 (§16g (10) (8) refined, branch claude/v2padcluster 95c48df7, base main 9a8b253b): rc 0, 451.5 s, ways 1916, body_sha 18e51b7d084e, artifact ledger a602bba1b858, solve feasible, guard shared repo UNCHANGED. [placement] pad_skirt_m ships at 0 = the airside-SHARED vertices alone (round 4's scope) PLUS 14al's withdrawal of the two-sided ceiling row over a pair of two shared vertices (4,008 pairs dropped). THE BEST ARM: airside 9,573 of 21,523 moved > 0.02 m (r4 10,048, the 25 m band 10,683), the RUNWAY 885 worst 0.390 m (r4 1,021/0.410, band 1,394/0.570); pad_cluster_mismatch 14; pad_airside_weld 29 worst 1.135; law-true 64,844; the terminal body on building298 at 72.60, own ground +0.07 m. Constraints 109.69 s = +31.4 % (bar +20 %, MISSED — the pad population, not the skirt)
HECA  graded   base 9a8b253b   lane v2padcluster     2026-09-14T15:11:08  /tmp/harness/v2padclusterHECA6.v2/HECA.graded.json  — the 25 m BAND arm of v2padcluster ROUND 5 — MEASURED AND REFUTED (branch claude/v2padcluster b5e29894): rc 0, 433.5 s, body_sha ee7d0f56911c, artifact ledger b63e49fd65b0, guard shared repo UNCHANGED. Worse than round 4's scope on EVERY airside bar: airside 10,048 -> 10,683, the runway 1,021 -> 1,394 and its worst 0.410 -> 0.570 m, pad_airside_weld 16 -> 21 (worst 1.135 -> 2.42), law-true 63,904 -> 66,771 — for the terminal body +0.08 -> +0.00 m. A wider band softens more of the pad and a softer pad moves more of the apron inside the same ceiling. pad_skirt_m keeps 25.0 as its design value and ships at 0
HECA  rebake   base 9a8b253b   lane v2padcluster     2026-09-14T15:11:08  /tmp/harness/v2padclusterHECA7.v2/HECA.rebake.json  — SHIPPED arm of v2padcluster ROUND 5 (§16g (10) (8) refined, branch claude/v2padcluster 95c48df7, base main 9a8b253b): rc 0, 451.5 s, ways 1916, body_sha 18e51b7d084e, artifact ledger a602bba1b858, solve feasible, guard shared repo UNCHANGED. [placement] pad_skirt_m ships at 0 = the airside-SHARED vertices alone (round 4's scope) PLUS 14al's withdrawal of the two-sided ceiling row over a pair of two shared vertices (4,008 pairs dropped). THE BEST ARM: airside 9,573 of 21,523 moved > 0.02 m (r4 10,048, the 25 m band 10,683), the RUNWAY 885 worst 0.390 m (r4 1,021/0.410, band 1,394/0.570); pad_cluster_mismatch 14; pad_airside_weld 29 worst 1.135; law-true 64,844; the terminal body on building298 at 72.60, own ground +0.07 m. Constraints 109.69 s = +31.4 % (bar +20 %, MISSED — the pad population, not the skirt)
HECA  rebake   base 9a8b253b   lane v2padcluster     2026-09-14T15:11:08  /tmp/harness/v2padclusterHECA6.v2/HECA.rebake.json  — the 25 m BAND arm of v2padcluster ROUND 5 — MEASURED AND REFUTED (branch claude/v2padcluster b5e29894): rc 0, 433.5 s, body_sha ee7d0f56911c, artifact ledger b63e49fd65b0, guard shared repo UNCHANGED. Worse than round 4's scope on EVERY airside bar: airside 10,048 -> 10,683, the runway 1,021 -> 1,394 and its worst 0.410 -> 0.570 m, pad_airside_weld 16 -> 21 (worst 1.135 -> 2.42), law-true 63,904 -> 66,771 — for the terminal body +0.08 -> +0.00 m. A wider band softens more of the pad and a softer pad moves more of the apron inside the same ceiling. pad_skirt_m keeps 25.0 as its design value and ships at 0
HECA  patch    base 18cc0ecb   lane v2staged         2026-09-14T16:41:01  /tmp/harness/v2stagedHECA3.osm  — §20b THE STAGED SOLVE, FINAL FORM, staged_solve=true arm (branch claude/v2staged): rc 0, 416.0 s, ways 1916, body_sha 266b56b5a358, v2-verify 33955, shared repo UNCHANGED. Stage 1 AIRSIDE 19,034 unknowns / 128,949 rows, 42/161,690 hard violated max 0.1794 NOT SETTLED, 0 one-way rows, runway projection 0.1155 -> 0.020000 m with 0 elastic; stage 2 13,838 unknowns / 180,591 rows in 11.2 s. vs its OFF twin v2stagedHECAoff (= r5 shipped body 18e51b7d084e): airside moved vs DISARM 8,976 -> 10,371 (BAR 0 MISSED; runway 885/0.390 -> 477/1.560), adjudicated 28,413 -> 29,018, airside_no_step 7,919 -> 6,801, taxi_box 3,429 -> 2,854, pad_airside_weld 29 -> 33, pad_cluster_mismatch 14 -> 14, terminal building298 72.60 -> 73.05. SHIPS OFF
HECA  patch    base 18cc0ecb   lane v2staged         2026-09-14T16:41:01  /tmp/harness/v2stagedHECAoff.osm  — §20b's DISARM twin (staged_solve=false) on claude/v2staged: rc 0, 476.3 s, body_sha 18e51b7d084e — BYTE-IDENTICAL to v2padcluster r5's shipped arm (ledger a602bba1b858), which proves everything merged since a3185dbb changes nothing at HECA and makes the r5/DISARM frames lawful controls for this lane. v2-verify 33,397; 1,021/365,395 hard rows violated max 2.984 m

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
KCLT  patch    base a1d0edfa   lane v2padcluster     2026-09-14T13:25:46  /tmp/harness/v2padclusterKCLT3.osm  — lane v2padcluster ROUND 3 KCLT build (claude/v2padcluster at 01724ef4 — carries (4) on the DESIGN cluster, (5) and (6); the object-stage half of (4) landed after and moves no vertex, proven by HECA3/HECA4 sharing body_sha cbefb8edcacb): rc 0, 274.2 s, ways 1189, body_sha d19ae4797bc4, solve feasible, guard shared repo UNCHANGED; NO ledger key (the tree moved during the run). THE CONTROL, read BY COORDINATE at 13bo's site 35.2191877,-80.9426007 because the derived pads RENUMBER every building{N}: the terminal pad 221.46 -> 220.56 m (-0.90), 865 -> 483 vertices, spread 1.07 -> 0.51 — the bar (unchanged within hard_tol_m) is MISSED
KCLT  graded   base a1d0edfa   lane v2padcluster     2026-09-14T13:25:46  /tmp/harness/v2padclusterKCLT3.v2/KCLT.graded.json  — lane v2padcluster ROUND 3 KCLT build (claude/v2padcluster at 01724ef4 — carries (4) on the DESIGN cluster, (5) and (6); the object-stage half of (4) landed after and moves no vertex, proven by HECA3/HECA4 sharing body_sha cbefb8edcacb): rc 0, 274.2 s, ways 1189, body_sha d19ae4797bc4, solve feasible, guard shared repo UNCHANGED; NO ledger key (the tree moved during the run). THE CONTROL, read BY COORDINATE at 13bo's site 35.2191877,-80.9426007 because the derived pads RENUMBER every building{N}: the terminal pad 221.46 -> 220.56 m (-0.90), 865 -> 483 vertices, spread 1.07 -> 0.51 — the bar (unchanged within hard_tol_m) is MISSED
KCLT  rebake   base a1d0edfa   lane v2padcluster     2026-09-14T13:25:46  /tmp/harness/v2padclusterKCLT3.v2/KCLT.rebake.json  — lane v2padcluster ROUND 3 KCLT build (claude/v2padcluster at 01724ef4 — carries (4) on the DESIGN cluster, (5) and (6); the object-stage half of (4) landed after and moves no vertex, proven by HECA3/HECA4 sharing body_sha cbefb8edcacb): rc 0, 274.2 s, ways 1189, body_sha d19ae4797bc4, solve feasible, guard shared repo UNCHANGED; NO ledger key (the tree moved during the run). THE CONTROL, read BY COORDINATE at 13bo's site 35.2191877,-80.9426007 because the derived pads RENUMBER every building{N}: the terminal pad 221.46 -> 220.56 m (-0.90), 865 -> 483 vertices, spread 1.07 -> 0.51 — the bar (unchanged within hard_tol_m) is MISSED
KCLT  patch    base a1d0edfa   lane v2padcluster     2026-09-14T14:21:29  /tmp/harness/v2padclusterKCLT4.osm  — v2padcluster ROUND 4 KCLT build at the final tree (claude/v2padcluster 9a4bd0e3): rc 0, 259.0 s, ways 1070, body_sha 2fa924a012cc, artifact ledger dca6d7449633, solve feasible, guard shared repo UNCHANGED. THE CONTROL at 13bo's coordinate 35.2191877,-80.9426007: the terminal pad building80 (850 verts) median 221.46 -> 220.93 (-0.53), spread 1.07 -> 3.77 — and the movement IS THE WELD: the pad shares 743 nodes with the apron pav14 (z 220.04..223.81) and 51 with pav118, so the step across the weld is 0 by construction. pad_airside_weld 25, worst building80 -> pav14 1.384 m over 11.6 m (the pad cannot reach that edge even bending at 1 %)
KCLT  graded   base a1d0edfa   lane v2padcluster     2026-09-14T14:21:29  /tmp/harness/v2padclusterKCLT4.v2/KCLT.graded.json  — v2padcluster ROUND 4 KCLT build at the final tree (claude/v2padcluster 9a4bd0e3): rc 0, 259.0 s, ways 1070, body_sha 2fa924a012cc, artifact ledger dca6d7449633, solve feasible, guard shared repo UNCHANGED. THE CONTROL at 13bo's coordinate 35.2191877,-80.9426007: the terminal pad building80 (850 verts) median 221.46 -> 220.93 (-0.53), spread 1.07 -> 3.77 — and the movement IS THE WELD: the pad shares 743 nodes with the apron pav14 (z 220.04..223.81) and 51 with pav118, so the step across the weld is 0 by construction. pad_airside_weld 25, worst building80 -> pav14 1.384 m over 11.6 m (the pad cannot reach that edge even bending at 1 %)
KCLT  rebake   base a1d0edfa   lane v2padcluster     2026-09-14T14:21:30  /tmp/harness/v2padclusterKCLT4.v2/KCLT.rebake.json  — v2padcluster ROUND 4 KCLT build at the final tree (claude/v2padcluster 9a4bd0e3): rc 0, 259.0 s, ways 1070, body_sha 2fa924a012cc, artifact ledger dca6d7449633, solve feasible, guard shared repo UNCHANGED. THE CONTROL at 13bo's coordinate 35.2191877,-80.9426007: the terminal pad building80 (850 verts) median 221.46 -> 220.93 (-0.53), spread 1.07 -> 3.77 — and the movement IS THE WELD: the pad shares 743 nodes with the apron pav14 (z 220.04..223.81) and 51 with pav118, so the step across the weld is 0 by construction. pad_airside_weld 25, worst building80 -> pav14 1.384 m over 11.6 m (the pad cannot reach that edge even bending at 1 %)

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

