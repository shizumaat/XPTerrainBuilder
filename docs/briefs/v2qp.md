# Brief pack — lane `v2qp`

Base: main `d0d8af83` · generated 2026-09-14 by `tools/brief_pack.py`

Read THIS file first and whole. Do not grep the spec, RULINGS or INDEX monoliths for
what is here; use `tools/docq.py` for anything else you need.

## Task

§20c: the one-sided design problem solved as a HiGHS QP — replaces the non-converging damped fixed point (RULINGS 14bw)

## The brief

THE QP SOLVE (RULINGS 14bw; §20c). Site: `Ortho4XP/src/auto_patch_v2/solve/design.py` (`assemble`, `_solve_stage`, the damped active-set loop, the lag rounds, `hard_rulings`/`one_way_rulings`, `shift`), `solve/api.py` (`Solution`, `Status`), `solve/rows.py` (`_reduce`, `_Rows`), `solve/design_report.py` (`read_hard_failure`, `set_exits`, the settled line), `solve/project.py` (how the projections already call HiGHS — reuse that binding; `highspy` is a frozen-engine lazy-import hazard: memory `frozen-engine-lazy-imports` — import at module top). Read `tools/docq.py spec '§20c'`, `'§32 (4)'` (§20a inside), `'§20b'`, and `tools/docq.py ruling 14bw 14br 14au 14as 13y 13ab 13ac 13db`. BUILD: (1) `[design] solver = "qp"` (default `fixed_point` until the bars hold, then flip): assemble the SAME rows (`_Rows` after `_reduce`), hand HiGHS a QP: objective = the assembled quadratic (the curvature/smoothness Hessian the normal equations already form — extract Q, c), constraints = hard rows as equalities (`hard_weight` gone — they are constraints), one-way rows as inequalities (the `follows` side ≤/≥), caps as inequalities, DEM/bounds as column bounds; `Status` from HiGHS (optimal / infeasible → the certificate's infeasible set via HiGHS's IIS or the existing min-Σ-slack read); warm start from the fixed point's iterate if cheap. (2) §20b staged: both stages through the QP (stage 2's fixed airside columns are constants — as today). (3) `design_report`: the QP's status, iteration count, wall; `set_exits` retired for `qp`. (4) Twins: a synthetic one-sided problem where the fixed point stalls and the QP converges; a perturbation twin (one row moved 0.3 m → only nearby vertices move); an infeasible pair → named, not traded; both solvers give the same answer on a problem with no one-way rows (identity to 1e-6). MEASURE on the registered captures (v2settle's HECA/KCLT/CYXY at base 12400580 — `frames.py list`; the HECA stability-probe frame): the one-vertex probe (`…/scratchpad/v2settle/probe3.py`/`probe4.py` — reuse) 959 → within 250 m only; hard rows settled (0 over tol+0.01 or named); census by family (`harness/census.py` on the emitted patch of each arm — `v2_solve_replay --emit`) at HECA/KCLT/CYXY + SPJC/OTHH captures if registered (else say); solve wall both solvers (HiGHS QP on ~160 k rows / 32 k cols — if > 2× the fixed point, name where: the Hessian assembly? the QP itself? try HiGHS's `qp` options / crossover off); then ONE HECA build with `solver = qp` for the sim read. Flip the default only if every bar holds; otherwise ship `fixed_point` with the QP measured. NOT yours: `constraints/`, `classify/`, `planar/`, `airport/`, `emit/`.

## Bars

- The one-vertex probe at HECA: 959 moved (953 beyond 500 m) → moved only within 250 m of the perturbation (count named); the same capture solved twice → identical.
- Every hard row settled (0 over `hard_tol_m` + 0.01) or the infeasible set named by the certificate — HECA, KCLT, CYXY.
- Census ADJUDICATED by family before → after at HECA/KCLT/CYXY (+ SPJC/OTHH if captures exist): no family worse by > 5 % without a named reason; the shipped patch diff named.
- Solve wall ≤ 2× the fixed point at HECA (both named); §20b both stages through the QP.
- Suite twice by FAILED lines; ONE HECA build with `solver = qp`.

## Files

Yours: `Ortho4XP/src/auto_patch_v2/solve/design.py`, `Ortho4XP/src/auto_patch_v2/solve/api.py`, `Ortho4XP/src/auto_patch_v2/solve/rows.py`, `Ortho4XP/src/auto_patch_v2/solve/design_report.py`, `Ortho4XP/src/auto_patch_v2/solve/project.py`, `Ortho4XP/src/auto_patch_v2/law/emit.toml`, `Ortho4XP/src/auto_patch_v2/law/design_schema.py`
Other lanes' (do not touch): `Ortho4XP/src/auto_patch_v2/constraints/`, `Ortho4XP/src/auto_patch_v2/classify/`, `Ortho4XP/src/auto_patch_v2/planar/`, `Ortho4XP/src/auto_patch_v2/airport/`

## Spec (design-surface) §20c

## §20c THE ONE-SIDED PROBLEM IS SOLVED AS A QP (Fable 2026-09-14; RULINGS 2026-09-14bw) — lane `v2qp`

MEASURED (lane v2settle r2, HECA): one 0.30 m ceiling row at one apron vertex
moves 959 vertices, 953 of them more than 500 m away — the damped active-set
fixed-point iteration (`splu` on the normal equations, lag rounds for the
one-way rows) exits `objective_stalled` on every solve and never reaches a
fixed point, so any perturbation lands on a different far field; a DEM-anchor
tie-break prices instead of choosing (weight-proportional) and is refuted.
1. The design problem — min Σ curvature (the smoothness objective as
   assembled) subject to hard EQUALITY rows, one-way INEQUALITY rows (§20a's
   `follows`), caps and DEM bounds — is a convex QP.  It is solved as one by
   HiGHS QP (`highspy`), the same solver §30 (3)/§32 (4)'s projections use.
   No lag rounds, no `follows` machinery, no damping: the optimum is unique
   (strictly convex objective) and locally stable.
2. `[design] solver = "fixed_point" | "qp"`: the old solver is kept behind
   the key for the matched pair and deleted when `qp` ships.
3. The certificate (§20a, `read_hard_failure`) reads the QP's own status:
   infeasible → the named infeasible set, never a traded row.
BARS: the one-vertex probe: moved vertices only within 250 m of the
perturbation (count named; today 959 with 953 beyond 500 m); every hard row
settled or named; the census by family at HECA/KCLT/CYXY/SPJC/OTHH before →
after with no family worse by > 5 % unexplained; solve wall ≤ 2× (named);
stage 1 / stage 2 of §20b both through the QP; the shipped patch diff named
(a converged solve differs by construction).

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

## RULINGS

## 2026-09-14bw v2settle round 2 MERGED (a7e88329, instrument only): the far-field instability is the SOLVER — the damped active-set fixed point never converges (`objective_stalled` on all six HECA solves); the tie-break REFUTED (weight-proportional, it prices); ruled: §20c THE ONE-SIDED PROBLEM IS SOLVED AS A QP — lane `v2qp`

Lane `v2settle` @ 16725245 (suite 1,534 twice; 1,549 on main;
shipped patches byte-identical at HECA/KCLT/CYXY). One extra ceiling
row at ONE HECA apron vertex (0.30 m) moves 959 vertices > 0.02 m —
953 beyond 500 m, ZERO within 100 m, worst 0.52 m, over a 6.2 × 4.7 km
box and every role: 14br's collar signature with no collar. The
tie-break (a DEM anchor per free column): at 1e-9 identical to main
to 13 digits; at 1e-6/1e-3 WORSE and weight-proportional — it prices,
it does not choose among equal optima; deleted. `DesignReport.set_
exits` (new): all six damped active-set solves exit `objective_
stalled`, none at `same_set` — the iteration never reaches its fixed
point on either arm; with `set_stall_tol = 0` they exit `line_search_
stalled` and the far field still moves. The default design solver is
`splu` on the normal equations (HiGHS options do not apply). Item
(2): 35 surviving stage-1 rows, worst 0.083 m, FEASIBLE; 25 sit on
vertices carrying another family's hard row — a per-family projection
would trade rows (§32 (4)); a full residual projection on an
unconverged solve is sand.

* RULING §20c: the design's ONE-SIDED problem (the min-curvature
  objective with hard equality rows, one-way ≤ rows, caps and bounds)
  is a CONVEX QP and is solved AS ONE — HiGHS QP (`highspy`, the
  projections already use it) replaces the hand-rolled damped
  active-set fixed point; no lag rounds, no `follows` machinery; the
  optimum is unique for a strictly convex objective and locally
  stable under perturbation by construction. The old solver stays
  behind `[design] solver = "fixed_point" | "qp"` for the measured
  pair, ships `qp` when the bars hold. Lane `v2qp` (fresh).
* Bars: the one-vertex probe 959 → moved vertices only within 250 m
  (name the count); the census ADJUDICATED before → after at HECA,
  KCLT, CYXY, SPJC, OTHH (a converged solve WILL differ — the diff is
  named by family, and no family may worsen by > 5 % without a
  reason); every hard row settled (0 over `hard_tol_m` + 0.01, or the
  infeasible pairs named by the certificate); solve wall ≤ 2× the
  fixed point at HECA (name it; HiGHS QP on ~160 k rows / 32 k
  columns); the owner's sim read of the next app is the acceptance.

## 2026-09-14br v2padjoin round 3 MERGED (2808b6ac, flags OFF): the skirt WITHDRAWN — stage-2 infeasible 151 → 92, `pad_airside_weld` 42 → 18 with nothing armed; the low-side datum in; the collar's residual is the UNSETTLED STAGE-1 OPTIMUM, not the collar — ruled: settle first

Lane `v2padjoin` @ dde728a8 (suite 1,531 twice; 1,538 on main).
`_pad_rows`: the band, rigid core, skirt row and both-ends
withdrawal deleted with their two law keys and the head; five twins
re-founded and named (the §20b two-pavement twin: the pad now holds
its own 1 % under the staged solve — tilt 0.030 → 0.010). §16g (10)
(9)(2): `pad_between_aprons = true` — `plan_unit_datums` takes the
pad's LOW side (the shared-edge subset is not published — a deviation
named). HECA pair (pads+clip+staged ON): base 151 / 178.7 m → 92 /
138.7 m infeasible, weld 42 → 18, adjudicated 26,708 → 24,770; the
collar arm 1,511 / 3,148 m and the terminal 72.92 → 75.90 — of the
11,363 vertices that move, 2,211 stand > 500 m from any pad: a
FIELD-WIDE shift of an unsettled stage-1 optimum (14as (ii), 13y
(B)/13ab), which no row added to stage 1 can hold to "the collar
only"; the collar plane's own LEVEL is picked by stage 1 (the low-side
datum cannot fix a lifted collar). KCLT pads ON (one build): 5
cluster pads, the terminal cluster 55,695 m² over `building80` +
`building89` at 220.859 — NOT inert; the collar there is 5 vertices
(the terminal apron is struck by the taxi-band/no-step/other-pad
rules); `building{N}` renumbered — the 13bo site's pad median 220.34.

* RULING (the lane's decision): 13y (B)/13ab goes FIRST — the stage-1
  optimum must be UNIQUE and STABLE: a perturbation local to one
  terminal must not move vertices 500 m away. Lane `v2settle` r2: the
  remaining 6 rows (the un-built per-family post-solve projection for
  `pavement_ceiling`, §30 (3)'s pattern) AND the uniqueness — a
  regularising tie-break in the objective (the DEM/the previous
  iterate as the least-change anchor among equal-cost optima, at a
  weight below every law) so the same problem ± a collar yields the
  same far field; bar: the HECA collar pair's moved-vertex set within
  the reach + 100 m only. The collar stays disarmed until then.
* Owed: the collar m² (extend `pad_airside_arm.py`), KCLT members'
  seats on the new build, the HECA terminal body seat with the
  low-side datum.

## 2026-09-14au v2settle MERGED: the "unsettled hard set" was mostly CONSTANT rows (footed on pins, no column) and the projection's own 0.02 bar; the real residual is 6 rows / 0.0445 m, NAMED and certified FEASIBLE; shipped patches byte-identical; the stage-2 certificate PROVES the conforming side infeasible by law — ruled: the pad's skirt yields

Lane `v2settle` @ b129f97d (fresh HECA + KCLT captures registered;
suite 1,515 twice). HECA stage 1's 33 unsettled rows: 9 `road_ramp`
ceilings footed on a `Pin` with NO column (constants — `assemble`
tested only `dem_fixed`; 142 such rows; phase C pinned `best_worst`
on a constant it could never beat and RETURNED ROUND 1's ITERATE), 6
`runway_profile` at 0.0200000 (the projection's own held bar), 18
real (`pavement_ceiling` 11, `pads` 7, worst 0.1025). Fixed:
`_carries_a_column` on the REDUCED row; one settle derivation
(`hard_exceeds`/`HARD_READ_EPS`); §20a's named hard failure with a
min-Σ-slack FEASIBILITY CERTIFICATE (`read_hard_failure`); `v2_solve_
replay --why-hard-stage`. After: HECA stage 1 6 rows / 0.0445 m, all
named, certificate FEASIBLE (a solve residual, not the law); shipped
single-solve patches BYTE-IDENTICAL at HECA and KCLT; KCLT's 406
survivors: 143 PROVED an infeasible set (26.4 m over 179 columns, all
`building_pad airside skirt` at 35.2097, −80.9327); §20b stage 2 at
HECA: 1,428 of 2,548 survivors proved infeasible, 1,015.6 m. 13db's
shared `shift` REFUTED as the limit (0 rows both hard and one-way).
Not met: the last 6 rows (both levers refuted, 12u/13ac; the
un-built candidate is a per-family post-solve projection for
`pavement_ceiling`, §30 (3)'s pattern); KCLT's lag 0.317 m.

* RULING (the intent question "which row yields when a welded pad's
  1 % ceiling and a fixed apron rim cannot both hold"): the AIRSIDE
  never yields; the PAD's flatness yields — its skirt band's slope
  ceiling relaxes from 1 % up to `pad_skirt_max_slope` (5 %) as the
  weld requires (a slope, never a step: the owner's "weld smoothly");
  only beyond 5 % is it `pad_airside_weld` CRITICAL. §16g (10) (8)
  amended accordingly; lane `v2padvert`'s successor (or the same
  lane) applies it in `constraints/pads.py` with the KCLT 143-row set
  as the bar (→ 0 infeasible, each pad's skirt slope named).

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

| `Ortho4XP/tools/v2_solve_replay.py` | --why-vertex V [--why-relax FAMILY ...]`; `--why-hard [N] [--why-hard-stage 1]` on either a `--replay` arm or a `--why-from PKL`) | You are iterating on the v2 SOLVE (a law table, a generator, the shape stage, the planar build) and want the runway bows / z − DEM / joints / yielded-rows figures per change WITHOUT paying for the load stage each time — the synthetic-first solve arm (CLAUDE.md BUILD ECONOMY; `docs/specs/auto-patch-v2/heca-sag-ablation/ablate_heca_pin.py` was the scratch pattern, promoted on its second use by lane v2chord, RULINGS 2026-09-08d). `--capture` runs load → **the PACK PARTITION + GROUPS** (`build.py:288-318`, owner RULINGS 2026-09-11j — folded in 2026-09-12u by lane `v2padceiling` after scout `v2unsettled` measured the trap: a capture without them carries an `Airport` with no `partition` and no `groups`, so the replay silently solves a DIFFERENT problem — no `foot_rows`, no `pad_relief` targets, no basin bodies, and the shipped LEMD hard set could not be reproduced at all; a capture predating it is now REFUSED BY NAME at replay, `capture_has_groups`) → classify → planar (which labels the SHAPES, owner RULINGS 2026-09-08k) → flat site → road profile → shape stage exactly as `pipeline/build.py` and pickles the airport, the classification, the planar map and the stage (**and THE CLUSTERS beside the partition and the groups** — lane ``v2padjoin`` 2026-09-14: a capture without ``Airport.clusters`` leaves §30 (4)'s cluster pad, its apron reach and §16g (10)'s derived pads INERT in every replay of it, so a pads-ON arm silently measures the pads-OFF law; a capture predating them has them DERIVED at replay off its own partition, named on stdout) (HECA 56 s; LEMD 232 s, of which 104 s partition); `--replay` resumes from the named stage under the CURRENT tree (constraints + joint filter + yield transform + ONE solve by default — 08k (4), no joint re-solve; `shapes` rebuilds the shapes over the captured map and re-runs the stage — for a change in `planar/shapes.py` or `[terrace]`; `planar` the whole map), and prints per two-threshold runway the crown-ridge BOW, the ridge minimum, z − DEM mean/min/max, the law-tier line, `yielded_rows` per family and the max apron grade PER SHAPE with the steepest rows per family (face, grade, span, lat/lon), the shapes (count, the largest by vertices), the joints (count, gap joints, max built step, the worst with their shape pair), the road steps, and per `--site` the vertices within `--site-radius` (z − DEM, roles, shape ids, the max |dz| over a short edge = a step). `--emit DIR` writes the arm's patch through the build's own emit half so `patch_proximity_diff.py` and `undulation.py` can read a same-frame divergence on a replay arm; `--verify` runs the v2 VERIFY CENSUS on the solved surface and prints the rows per family and the DEFECT families the app's driver gates on (lane v2smooth round 2, RULINGS 2026-09-08v — a weight sweep needs the defect count per arm without a 130 s build); `--design-weight TERM=W` overrides one `emit.toml [design]` weight for the arm (the measurement arm, never a default). `--drop-generator` also accepts the pseudo-generator **`eat_ramp_reach`** (lane `v2eatramp`, spec §36 (5)): the EAT ramp's trend WITHDRAWAL is a channel edit made before the solve, not a row, so it cannot be dropped by the row filter — `eat_anchor_rect` drops the pins and their reach together, `eat_ramp_reach` the withdrawal alone (the §36 (5) before-arm). Lane v2shapes (2026-09-08): HECA capture 56 s; one pass 144–150 s (the 08g three-pass law read 357 s). `--why-from PKL --why-hump RUNWAY S0 S1` (the `solve.why` bindings and chain trace on the highest ridge vertex above the chord, from a duals solve of the SAME LP — kept out of the timed arm) with `--why-relax FAMILY ...` (relax-one-family arms: the hump's dz after a full re-solve without the family — the INTERVENTIONAL holder read). `--why-hard [N]` lists EVERY VIOLATED HARD ROW of the solved surface — generator, ruling, demanded vs allowed metres, and per vertex the id, coefficient, z, DEM, lat/lon and roles — re-assembling the design problem with `solve.design.assemble` and applying design.py's own `2 / Σ|c|` row scaling, so every violation reads in the METRES `hard_tol_m` is stated in (promoted from scout `v2unsettled2`'s `hardrows.py` on its second use, spec §32 (4), RULINGS 2026-09-13ac: `HARD SET NOT SETTLED` names ONE truncated ruling, which cost 12u a scout re-deriving the population by hand and 13ac needed the row's VERTICES to see that main's worst row was a pair the zone projection had clamped independently).  **`--why-hard-stage 1`** reads §20b STAGE 1's OWN ASSEMBLY instead of the full problem's (`solve.design.stage_split`'s drop + fixed): the AIRSIDE hard set, in the rows and the metre scaling stage 1 enforced them under. The full read cannot answer "does the AIRSIDE solve settle" — the airside rows are a subset of 325k whose population and scaling the stage's own drop changes — and that is exactly the claim RULINGS 13y (B) / 13ab / 14as make (lane `v2settle`, which used it to split HECA's "42 unsettled rows" into 9 CONSTANT rows the solve can never move, 6 HELD runway rows at the projection's own bar, and 18 real ones).  The shipped surface is read either way: an airside vertex's z IS stage 1's, so the stage-1 read at the shipped z equals the read at stage 1's own surface (measured identical at HECA). **`--emit` IS THE BUILD'S WHOLE EMIT HALF SINCE 2026-09-13** (lane `v2zonebank`, §37 (3)): it ran `graded_surface` -> `write_patch` and SKIPPED `with_bank` / `with_terrain_edges`, so every `bank_foot` question asked of a replay arm read ZERO feet and looked like the defect under attribution — it now runs `pipeline/build.py:780-795` verbatim and prints the `BankReport` line. **`--bank-from SOLVED.pkl`** replays that emit half alone off a `--solved-out` pickle (KCLT 2.5 s against the 160 s `--replay`), with `--emit DIR` and/or **`--bank-walk`**: §37 (3)'s per-station ADJACENT-GROUND ZONE-2 WALK — per `adjacent_ground:*:zone2` face ring, `|z_ring - DEM(foot)|` at every station, the stations at or over `bank_materiality_m`, whether the foot point stands outside the design coverage, whether it falls in the terrain-edge no-bank region or the water cut, and whether a `bank_foot` stands within that station's OWN 1:3 reach (never the airport-wide `bank_max_width_m`, which calls a foot 200 m away near); then, off `emit/bank.with_bank`'s `station_probe` / `region_probe` attribution hooks, the banked-region station the load-bearing verdict was actually taken on and where an unbanked station stands (inside the banked region? inside a coverage HOLE?). It prices no law and counts no defects — defect counts come from `harness/census.py`. Measured basis (KCLT, base `ce203b29`, `cap/KCLT.pkl`): 233 zone2 rings / 5,647 stations, 542 at or over the 1.65 m materiality, 220 with their foot outside the coverage, **110 with no foot at all** — 110 of them inside the banked region and 109 inside a coverage hole, which is how RULINGS 2026-09-13bu item 5 was attributed to `_foot_piece`'s solid exterior disc; after the fix 8. **A CAPTURE PREDATING A TARGET CHANNEL STILL REPLAYS, AND SAYS SO** (2026-09-13, lane `v2roadcontact`): a `PlanarMap` field added since the pickle was written is simply ABSENT on the unpickled instance, so the first `dataclasses.replace` raised `AttributeError` and a REGISTERED FRAME another lane shares became unreplayable for a channel its own stage never produced; `--replay` now backfills each missing field at the dataclass's OWN default and NAMES it on stdout (the publisher derives the channel in the replay anyway). This is NOT a relaxation of the 12u groups refusal, which stands: that one is a capture solving a DIFFERENT problem, this one is a channel the capture never had. Twins: `tests/auto_patch_v2/test_v2padceiling.py` (the capture calls every pre-solve stage `pipeline/build.build` calls, read off both sources; the refusal predicate) — the rest of the replay is an instrument over `pipeline/build.py`'s own stages, which the pipeline twins cover. |

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
HECA  capture  base b1b7704c   lane v2settle         2026-09-14T17:38:04  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2settle/cap/HECA.pkl  — v2_solve_replay --capture on main b1b7704c (158 s, 31,820 vertices / 1,684 faces, pack partition 101 s: bodies 24,655 groups 22,049 relief 3,938 infeasible 2,546, 63 shapes); guard shared repo UNCHANGED, lane-local DSF + mod-cache overlays. The first HECA capture carrying the merged §20b staged solve (flag OFF by default; arm with --design-weight staged_solve=1). Stage-1 airside hard set read off it with the new --why-hard-stage 1.
HECA  graded   base b1b7704c   lane v2settle         2026-09-14T17:38:04  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2settle/emit_laneB/HECA.graded.json  — LANE arm of the v2settle matched pair (single solve = the shipped configuration), claude/v2settle b1a93a9a off main b1b7704c: dry --emit replay off cap/HECA.pkl. BYTE-IDENTICAL to the base arm /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2settle/base/emit_baseA/ (main b1b7704c) — the constant hard rows never reached the matrix. Hard set READ 281 -> 263 violated, worst 1.2595 m unchanged. Census law-true 64,716 ADJUDICATED 27,695.
HECA  capture  base b1b7704c   lane v2padvert        2026-09-14T18:19:02  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2settle/cap/HECA.pkl  — RE-READ by lane v2padvert (claude/v2padvert 4ec750f9): v2settle's HECA capture replayed under §20b (--design-weight staged_solve=1) with 14au's relaxed skirt ceiling (5 %). Stage 1 AIRSIDE 6/161,638 hard over 0.02 m, worst 0.0445 m — UNCHANGED from v2settle's post-fix reading (the airside did not move). Stage 2 770/163,847 violated, worst 4.4241 m, of which 124 a PROVED INFEASIBLE SET (90.4386 m over 544 free columns) against v2settle's 1,428 of 2,548 / 1,015.6 m: -91 % rows, -91 % shortfall. Pads-ON was NOT measurable off this capture — v2_solve_replay.capture sets no airport.clusters, so pad_from_cluster is inert in any replay of it; a pads-ON HECA reading needs a fresh capture or a build. guard shared repo UNCHANGED.
HECA  patch    base 092b3983   lane v2padjoin        2026-09-14T20:06:08  /tmp/harness/v2padjoinHECAbase.osm  — BASE ARM of the v2padjoin matched HECA pair (branch claude/v2padjoin, base main 092b3983 + the re-landed v2padvert clip): pad_from_cluster=true, pad_airside_clip=true, staged_solve=true, cluster_apron_reach_m=0. rc 0, 457.9 s, ways 1904, nodes 31924, body_sha 3a2d1507c31a, v2-verify 31042, solve feasible, guard shared repo UNCHANGED (1 external-candidate OTHH mod-cache delta named, another lane's; no artifact ledger key for that reason). REPRODUCES v2padvert's registered pads-ON frame EXACTLY: stage 2 1,201/189,405 hard violated, 151 an INFEASIBLE SET (178.7207 m over 705 free columns); stage 1 4/148,256 worst 0.0329 m
HECA  patch    base 092b3983   lane v2padjoin        2026-09-14T20:06:08  /tmp/harness/v2padjoinHECAjoin.osm  — JOIN ARM of the same pair, the ONLY variable cluster_apron_reach_m 0 -> 40 with the §30 (4) apron reach minted as RULINGS 2026-09-14bf's PLANE JOIN (each collar vertex bound into the pad's plate: cap-0 pad_flat + the hard 1 % ceiling). rc 0, 449.9 s, body_sha c76d6b9759f7, guard shared repo UNCHANGED. THE JOIN IS REFUTED: 24,202 join rows take stage 2 from 1,201 to 3,322/204,943 violated and the INFEASIBLE SET from 151/178.7207 m to 1,114/2,312.4274 m over 1,009 columns; stage 1 (the AIRSIDE) 4 -> 8 rows, worst 0.0329 -> 0.1080 m. Mechanism: under §20b the collar is airside, stage 1 fixes it without the pad and substitutes it as a constant, so the plate must equal an already-solved collar (worst join ceiling rows 5.89 m); the all-airside collar pairs leak into stage 1 and move the airside. The join code is DELETED on the branch
HECA  patch    base 0c72919a   lane v2padjoin        2026-09-14T20:49:33  /tmp/harness/v2padjoinHECAr2base.osm  — ROUND 2 BASE ARM (branch claude/v2padjoin 747eaf91, base main 0c72919a): pad_from_cluster + pad_airside_clip + staged_solve ON, cluster_apron_reach_m 0. rc 0, 473.5 s, body_sha 3a2d1507c31a — BYTE-IDENTICAL to round 1's base arm, which proves everything merged into main since 092b3983 changes nothing at HECA in this configuration. Stage 2 1,201/189,405 hard violated, 151 an INFEASIBLE SET (178.7207 m over 705 columns); stage 1 4/148,256 worst 0.0329 m; census pad_airside_weld 42, pad_cluster_mismatch 12, ADJUDICATED 26,708; terminal 30.1279552,31.403143 at 72.62
HECA  patch    base 0c72919a   lane v2padjoin        2026-09-14T20:49:33  /tmp/harness/v2padjoinHECAr2collar2.osm  — ROUND 2 COLLAR ARM, RULINGS 2026-09-14bk's form: the apron within cluster_apron_reach_m (40 m) of a cluster outline is ONE PLANE among itself in §20b STAGE 1 (apron-law heads zones.apron cluster_collar_plane[ ceiling], in no conforming register, no pad vertex in any row) and the pad's plate equals that fixed collar in stage 2; other building pads' welded vertices struck from the collar. rc 0, 368.3 s, body_sha 77e8a3aa20cb, guard shared repo UNCHANGED. STAGE 1 IS FEASIBLE (min shortfall 0.0000 m) — the collar plane is lawful — but THE ACCEPTANCE IS MISSED: airside moved vs the base 11,847 vertices worst 9.45 m (RUNWAY 837, worst 1.23) against a collar of 266 vertices / 12 at the plane, the terminal 72.62 -> 75.92 (bar 72.50), stage-2 infeasible 151 rows / 178.72 m -> 1,318 / 3,074.92 m. The worst stage-2 rows are structures.building_pad airside skirt (7.07 -> 8.58 m) — the skirt law 14ay withdraws and this round did not. Its unstruck twin is v2padjoinHECAr2collar (b6443b925086: 1,626 / 3,644.17 m, stage 1 44 unsettled). Ships DISARMED
HECA  patch    base 7fe1ee9e   lane v2padjoin        2026-09-14T21:30:17  /tmp/harness/v2padjoinHECAr3base.osm  — ROUND 3 BASE ARM (claude/v2padjoin, the SKIRT WITHDRAWN + the low-side datum; pads + clip + staged ON, cluster_apron_reach_m 0): rc 0, 446.1 s, body_sha 43b8ad21d290, v2-verify 28,801, guard shared repo UNCHANGED. THE SKIRT WITHDRAWAL ALONE, against round 2's base 3a2d1507c31a in the same configuration: stage-2 infeasible 151 rows / 178.7207 m -> 92 / 138.7410 m, violated 1,201 -> 555, worst 7.0692 -> 6.4143 m, pad_airside_weld 42 -> 18, pad_cluster_mismatch 12, ADJUDICATED 26,708 -> 24,770; stage 1 5/153,340 worst 0.0329. Terminal surface at 30.1279552,31.403143 72.92, the terminal cluster's plane 72.478
HECA  patch    base 7fe1ee9e   lane v2padjoin        2026-09-14T21:30:17  /tmp/harness/v2padjoinHECAr3collar.osm  — ROUND 3 COLLAR ARM (the only variable cluster_apron_reach_m 0 -> 40): rc 0, 512.4 s, body_sha 8cb776c1d044, guard shared repo UNCHANGED. MISSES: stage-2 infeasible 92 -> 1,511 rows / 138.74 -> 3,148.2532 m, airside moved 11,001 worst 9.27 m (runway 849 worst 1.62), terminal cluster plane 72.478 -> 75.497, surface 72.92 -> 75.90, pad_airside_weld 18 -> 19, ADJUDICATED 24,770 -> 25,983. Stage 1 stays FEASIBLE (11 unsettled rows, min shortfall 0.0000 m) — the collar plane is lawful law. THE RESIDUAL IS NOT LOCAL: of 11,363 moved vertices only 3,202 are within 40 m of a cluster pad, 3,776 within 100 m, 2,211 beyond 500 m — a field-wide shift of an unsettled stage-1 optimum (14as (ii), 13y (B)/13ab). Collar 266 vertices, 8 at the plane. Ships DISARMED
HECA  capture  base 12400580   lane v2settle         2026-09-14T23:01:33  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2settle/cap/HECA.pkl  — RE-READ at main 12400580 (round 2): the same b1b7704c capture replays under the merged tree. THE STABILITY PROBE FRAME — scratchpad/v2settle/probe3.py + probe4.py perturb ONE apron vertex (v9968 at 30.12795521596,31.4031429808) with a ceiling 0.30 m under the base surface and bin the moved set by distance: main moves 959 vertices > 0.02 m, 953 BEYOND 500 m, 0 within 100 m, worst 0.5206 m. Reproduces RULINGS 14br's collar signature with the pad law inert. Stage 1 here: 35/174,500 hard over 0.02 m, worst 0.0828 m, certificate FEASIBLE.
HECA  graded   base 12400580   lane v2settle         2026-09-14T23:01:33  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2settle/r2/emit_final/HECA.graded.json  — lane v2settle ROUND 2 arm (claude/v2settle 16725245) off the b1b7704c HECA capture at main 12400580: BYTE-IDENTICAL to the base arm /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2settle/base2/ equivalents and to the pre-change arm /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2settle/r2/emit_off/. 39/329,775 hard rows violated, worst 1.2595 m, active-set exits objective_stalled x6 (NONE at same_set).

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
KCLT  capture  base b1b7704c   lane v2settle         2026-09-14T17:38:04  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2settle/cap/KCLT.pkl  — v2_solve_replay --capture on main b1b7704c (79 s, 21,683 vertices / 1,007 faces, pack partition 45 s: bodies 7,163 groups 7,007 relief 1,261 infeasible 1,032); guard shared repo UNCHANGED. KCLT captures and replays under the harness (13w's fresh_pack_dump). Base arm 408/227,135 hard violated max 0.5040 m, lag NOT SETTLED 0.3174 m.
KCLT  graded   base b1b7704c   lane v2settle         2026-09-14T17:38:04  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2settle/emit_kcltB/KCLT.graded.json  — LANE arm of the v2settle KCLT matched pair (single solve), claude/v2settle b1a93a9a. BYTE-IDENTICAL to the base arm /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2settle/base/emit_kcltA/. Hard set 408 -> 406 violated, worst 0.5040 m unchanged, and 143 of the 406 NAMED as a proven INFEASIBLE SET (26.3994 m over 179 free columns), all structures.building_pad airside skirt at 35.2096,-80.9327. Census law-true 18,193 ADJUDICATED 6,874.
KCLT  capture  base b1b7704c   lane v2padvert        2026-09-14T18:18:51  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2settle/cap/KCLT.pkl  — RE-READ by lane v2padvert (branch claude/v2padvert 4ec750f9) — v2settle's own KCLT capture replayed as a MATCHED PAIR under §20b (--design-weight staged_solve=1), the ONLY variable emit.within_shape.pad_skirt_max_slope (14au). BASE 1 %: stage 1 airside 1/121,520 hard violated worst 0.0241 m; stage 2 4,431/105,498 violated worst 3.3606 m, of which 2,410 a PROVED INFEASIBLE SET (1,389.70 m over 697 free columns). LANE 5 %: stage 1 IDENTICAL (1/121,520, 0.0241 — the airside did not move); stage 2 937 violated worst 2.3622, INFEASIBLE SET 313 rows / 128.20 m over 392 columns (-87 % rows, -91 % shortfall). The 14au bar (143 -> 0) is MISSED: 313 remain and they are the pads that cannot reach even bending at 5 % — pad_airside_weld CRITICAL by 14au's own clause. Single-solve arm (relaxation ungated) read 406 -> 74 violated and 143 -> 19 infeasible, but cost CYXY 2 runway_transverse rows and is NOT the shipped form. guard shared repo UNCHANGED.
KCLT  patch    base 7fe1ee9e   lane v2padjoin        2026-09-14T21:30:17  /tmp/harness/v2padjoinKCLTr3.osm  — KCLT with pads ON and the collar armed (claude/v2padjoin round 3): rc 0, 218.0 s, body_sha f953d1f4658b, v2-verify 2,774, guard shared repo UNCHANGED. ANSWERS 'is the cluster pad still inert at KCLT': NO, not with pads ON — 5 cluster pads, the terminal cluster unit:31#2377 (55,695 m2) over building80 + building89 at 220.859, plus unit:31#2385 over building91 and unit:30#528/3 over building80 + building97. The COLLAR is 5 vertices (1 at the plane): KCLT's terminal apron is struck almost entirely by the taxi-band, no-step-coupling and other-pad-weld rules. The pad at 13bo's coordinate 35.2191877,-80.9426007 is building80, 63 vertices, median 220.34, spread 1.54 (NOT comparable with round 4's 850-vertex 220.93 reading: the derived pads renumber every building{N} and the nearest vertex is 148.6 m from the site). Certificate 151 infeasible / 70.6075 m over 249 columns

## Registered frames: CYXY

CYXY  patch    base 8dac3c6b   lane v1settings       2026-09-13T12:56:32  /tmp/harness/v1settings_base.osm  — base arm: CYXY --engine v2 at main 8dac3c6b, body_sha fc59980475f5 (v1-retirement stage A control)
CYXY  patch    base 9ae9e5a9   lane v1settings       2026-09-13T12:56:32  /tmp/harness/v1settings_lane.osm  — lane arm: CYXY, no --engine flag, body_sha fc59980475f5 — byte-identical to the base arm
CYXY  patch    base dc5517c0   lane solvemodel       2026-09-13T15:55:54  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/base_CYXY/CYXY_20260913T155123.osm  — BASE arm, solve_model retirement closing test; body_sha ca2c7bbaa57e, 314 ways / 4690 nodes / 344 verify rows
CYXY  patch    base dc5517c0   lane solvemodel       2026-09-13T15:55:54  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/lane_CYXY/CYXY_20260913T155153.osm  — LANE arm (claude/solvemodel fdd291e9); body_sha ca2c7bbaa57e — byte-identical to the base arm, patch cmp-clean
CYXY  patch    base ce203b29   lane v2zonebank       2026-09-13T17:33:35  /tmp/harness/CYXY_20260913T173248.osm  — CYXY control on claude/v2zonebank cde84e27 (rc 0, 16.4 s, body_sha b38fbb12b262) — census law-true 1,087, bank_across_seam 0, stacked_nodes 0 (the RULINGS 10g plateau-tearing class clean)
CYXY  patch    base fef82b29   lane v2slivers        2026-09-14T09:05:36  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2slivers/cyxy/v2sl_cyxy2.osm  — CYXY control, lane arm (claude/v2slivers 88dfed33): rc 0, 13.6 s, ways 268, body_sha 018092d831df. NOT byte-identical to the base arm and lawfully so: CYXY carries 12 zone slivers / 339 m2 and 4 hairline hole rings at base, all dissolved/suppressed. Base arm v2sl_cyxy_base (main fef82b29): 284 ways, body_sha 673393ea5af0, 121 graded_strip faces / 12 slivers, 13 rings / 4 hairline
CYXY  patch    base 4c6f467c   lane v2cost2          2026-09-14T10:52:37  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2cost2/lane/CYXY.osm/cyxylane.osm  — CYXY control, LANE arm (claude/v2cost2 12b29e6c): rc 0, 12.9 s, body_sha 018092d831df — cmp-IDENTICAL to the base arm at main 4c6f467c in scratchpad/v2cost2/base/CYXY.osm/cyxybase.osm (13.2 s, same sha)
CYXY  patch    base 55cf0fe3   lane v2cost2          2026-09-14T11:31:42  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2cost2/lane/CYXY_r2.osm/cyxyr2.osm  — CYXY control, round 2 lane arm (claude/v2cost2 7bc09ea7): rc 0, 14.2 s, body_sha 018092d831df, cmp-IDENTICAL to the base arm scratchpad/v2cost2/base/CYXY.osm/cyxybase.osm
CYXY  capture  base 12400580   lane v2settle         2026-09-14T23:01:33  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2settle/cap/CYXY.pkl  — v2_solve_replay --capture CYXY on main 12400580 (8 s, 4,503 vertices / 261 faces); guard shared repo UNCHANGED. The cheap control: single solve 17/32,327 hard rows violated, active-set exits line_search_stalled x1 (never the set's own fixed point). Lane v2settle r2's byte-identity arm.

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
SPJC  patch    base a1d0edfa   lane v2padcluster     2026-09-14T14:21:30  /tmp/harness/v2padclusterSPJC4.osm  — v2padcluster ROUND 4 SPJC build — the FIRST SPJC frame carrying Part.height_m (claude/v2padcluster 9a4bd0e3): rc 0, 82.1 s, ways 431, body_sha 7f9b9659d13c, solve optimal, guard shared repo UNCHANGED (23 EXTERNAL-CANDIDATE deltas in the window, another lane's — NO ledger key). The viaduct xp11_007__b0 is on pad building7 at 20.07 in unit fu:0:3@cluster_pad of 6 members; 13df read 19.5604 in fu:0:0@cluster_pad of 24 — the leaf rule split the unit and the derived pad stands 0.51 m above the bar. pad_airside_weld 7, worst building7 -> pav46 0.970 m over 20.0 m
SPJC  graded   base a1d0edfa   lane v2padcluster     2026-09-14T14:21:30  /tmp/harness/v2padclusterSPJC4.v2/SPJC.graded.json  — v2padcluster ROUND 4 SPJC build — the FIRST SPJC frame carrying Part.height_m (claude/v2padcluster 9a4bd0e3): rc 0, 82.1 s, ways 431, body_sha 7f9b9659d13c, solve optimal, guard shared repo UNCHANGED (23 EXTERNAL-CANDIDATE deltas in the window, another lane's — NO ledger key). The viaduct xp11_007__b0 is on pad building7 at 20.07 in unit fu:0:3@cluster_pad of 6 members; 13df read 19.5604 in fu:0:0@cluster_pad of 24 — the leaf rule split the unit and the derived pad stands 0.51 m above the bar. pad_airside_weld 7, worst building7 -> pav46 0.970 m over 20.0 m
SPJC  rebake   base a1d0edfa   lane v2padcluster     2026-09-14T14:21:30  /tmp/harness/v2padclusterSPJC4.v2/SPJC.rebake.json  — v2padcluster ROUND 4 SPJC build — the FIRST SPJC frame carrying Part.height_m (claude/v2padcluster 9a4bd0e3): rc 0, 82.1 s, ways 431, body_sha 7f9b9659d13c, solve optimal, guard shared repo UNCHANGED (23 EXTERNAL-CANDIDATE deltas in the window, another lane's — NO ledger key). The viaduct xp11_007__b0 is on pad building7 at 20.07 in unit fu:0:3@cluster_pad of 6 members; 13df read 19.5604 in fu:0:0@cluster_pad of 24 — the leaf rule split the unit and the derived pad stands 0.51 m above the bar. pad_airside_weld 7, worst building7 -> pav46 0.970 m over 20.0 m

## Registered frames: OTHH

OTHH  rebake   base 05050624   lane v2unboxed        2026-09-13T12:06:34  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/unboxed  — KCLT 1.0.324 / LEMD 1.0.325 / OTHH 1.0.326 rebake frames + dry arms
OTHH  capture  base 7949757a   lane v2othh327        2026-09-13T16:30:07  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2othh327/OTHH.pkl  — v2_solve_replay --capture OTHH on main 7949757a (402 s); solved arms beside it: OTHH.solved.pkl (base) and OTHH.nofeet.pkl (--drop-generator foot_rows)
OTHH  patch    base a0f65165   lane v2cutfeet        2026-09-13T17:37:22  /tmp/harness/OTHH_20260913T171324.osm  — closing build of lane v2cutfeet (§11b (7) cut foot verdicts), rc 0, 968.0 s, ways 1097, body_sha 0ff85d1a7bff, artifact ledger 86493fdab68b; matched replay arms on the v2othh327 capture live in /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2cutfeet/out (OTHH.base.pkl / OTHH.cut.pkl / othh.base.json / othh.cut.json / *.log), KCLT arms beside them
OTHH  patch    base f4e9b436   lane v2gradecache     2026-09-13T18:08:32  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/fin_OTHH/structures.json  — OTHH planar --stage structures on claude/v2gradecache vs the 0c86fe2c base arm in scratchpad/base_OTHH: basins array BYTE-IDENTICAL; only one sunken_refused message rounds 50%->49% roofed, same verdict
OTHH  capture  base cf87c942   lane v2unionsweep     2026-09-14T07:40:37  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2unionsweep/othh.lane.json  — DRY replay dump (NOT a capture: the plan_clusters reading OFF the registered OTHH capture 7949757a, via scratchpad/v2unionsweep/cluster_arm.py). MATCHED PAIR: othh.base.json = main cf87c942 (666.07 s, machine contended; scout v2partcost read 299.8 s uncontended at 628cca80), othh.lane.json = claude/v2unionsweep 99cf52ba (16.60 s). 44 clusters both arms, all 44 area_m2 BIT-IDENTICAL (struct.pack '<d' hex).
OTHH  patch    base 4c6f467c   lane v2cost2          2026-09-14T10:52:28  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2cost2/base/OTHH_base.osm/v2cost2base.osm  — BASE ARM of the v2cost2 matched triple (own ritual worktree v2cost2base at main 4c6f467c): rc 0, harness wall 631.7 s, staged total 592.86, body_sha 72d4ec0e08f2, ways 1000 nodes 25387, guard UNCHANGED. wall_s load 7.63 / partition 313.57 / classify 7.87 / planar 67.13 / constraints 94.43 / solve 23.34 / emit 9.00 / rebake_plan 5.49 / verify 63.50 (the second Patch.of + road_law_caps + apron_over_preference ran OUTSIDE this clock). obj8_split_report on its own products: plan stage 223.13 s
OTHH  patch    base 4c6f467c   lane v2cost2          2026-09-14T10:52:28  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2cost2/lane/OTHH_cold.osm/v2cost2cold.osm  — LANE COLD arm (claude/v2cost2 3eeccf13, partition cache EMPTY -> WROTE 1.05 GB): rc 0, wall 615.1 s, body_sha 72d4ec0e08f2 — BYTE-IDENTICAL to the base arm (patch, OTHH.rebake.json and OTHH.graded.json all sha-equal). wall_s partition 288.87 (313.57 base: the per-axis contact screens), constraints 85.32 (94.43), verify 121.85 (63.50 + the 45.6 s that used to run unclocked), total 612.71, unclocked 1.24
OTHH  patch    base 4c6f467c   lane v2cost2          2026-09-14T10:52:28  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2cost2/lane/OTHH_warm.osm/v2cost2warm.osm  — LANE WARM arm (claude/v2cost2 12b29e6c, partition cache HIT): rc 0, harness wall 328.1 s vs the base arm's 631.7; body_sha 72d4ec0e08f2 BYTE-IDENTICAL, guard shared repo UNCHANGED. wall_s partition 313.57 -> 8.40, classify 7.87 -> 75.79 (the ResourceCache is cold on a hit, so the pack parse moves here: partition+classify 321.5 -> 84.2), constraints 94.43 -> 73.48, verify 63.50+45.6-unclocked -> 62.43, total 592.86 -> 325.17. verify.wall_s per family published (within_shape 50.94, taxi_box 8.72)
OTHH  patch    base 55cf0fe3   lane v2cost2          2026-09-14T11:31:42  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2cost2/lane/OTHH_r2c2.osm/v2c2r2c2.osm  — ROUND 2 COLD arm (claude/v2cost2 7bc09ea7, RULINGS 14v; cache EMPTY -> WROTE 31.3 MB, was 1,047 MB): rc 0, body_sha 72d4ec0e08f2, patch/rebake/graded sha-equal to the 4c6f467c base arm, guard UNCHANGED. wall_s partition 283.70 classify 8.90 planar 63.17 constraints 80.17 verify 67.25 total 547.67 unclocked 1.28
OTHH  patch    base 55cf0fe3   lane v2cost2          2026-09-14T11:31:42  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2cost2/lane/OTHH_r2w2.osm/v2c2r2w2.osm  — ROUND 2 WARM arm (claude/v2cost2 7bc09ea7): cache HIT, 2,259 resource readings restored; rc 0 harness wall 298.6 s (base arm 631.7), body_sha 72d4ec0e08f2 BYTE-IDENTICAL (patch, rebake plan and graded surface), guard UNCHANGED. wall_s partition 8.07 classify 10.21 (partition+classify 321.5 -> 18.3 on the base arm's frame; bar <= 40 MET) planar 84.43 (55 cold: the pack parse the cache no longer pre-pays lands here) constraints 78.67 verify 69.06 total 296.22 unclocked 1.28
OTHH  patch    base 8e92e26a   lane v2othhfix        2026-09-14T11:37:09  /tmp/harness/v2othhfix2.osm  — closing OTHH patch build of lane v2othhfix on claude/v2othhfix (§24 (7)/(8), §34 (7)/(8) as amended by 14u): rc 0, 614.3 s, ways 1012, nodes 23724, body_sha 44208e4fdd65, artifact ledger 20d817adcf38, shared repo UNCHANGED; report /tmp/harness/v2othhfix2.v2/OTHH.report.json; census A/B vs the owner's 1.0.332 patch ADJUDICATED 1764 -> 1766 (+2)
OTHH  rebake   base 908895cd   lane v2othhfix        2026-09-14T11:37:09  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2othhfix  — dry planar --stage structures arms on the lane-local overlay: base_OTHH (main 908895cd), a5_OTHH (the branch, final law); bars.py / inner.py / prof.py read floor-per-region, floor vs rim-minus-standoff and the §34 (7) profile identity; dry.sh / dry2.sh are the arm runners
OTHH  patch    base ed971ccd   lane v2othhfix        2026-09-14T14:56:25  /tmp/harness/v2othhfix_r2.osm  — ROUND 2 closing OTHH build (§34 (9) the pinched ramp, RULINGS 2026-09-14ak) on claude/v2othhfix: rc 0, 511.5 s, ways 1010, nodes 23607, body_sha ba3354ce693f, artifact ledger 3060701734b4, shared repo UNCHANGED; verify DEFECT families EMPTY (rows 2190 -> 2214, the +24 all within_shape on the two pinched ramps); census vs the owner's 1.0.333 patch ADJUDICATED 3206 -> 3223, road_cross_section 6 -> 6, transverse/airside_no_step/zone_on_pavement unchanged; shared AIRSIDE vertices moved > 0.1 m = 0 of 16,810
OTHH  rebake   base ed971ccd   lane v2othhfix        2026-09-14T14:56:25  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2othhfix  — ROUND 2 dry --stage structures matched pair: r2_base (main 9a8b253b = the 1.0.333 code) vs r2_fix (§34 (9)); corridors 40 -> 40, refusals 50 -> 50, 2 pinched_ramps (Terminal_Base_2_1@2 vs route9 12.6 m at 11.05 %; Terminal_Base_2_5@0/a vs route7 5.1 m at 36.98 %)
OTHH  patch    base 298b6ac8   lane v2liftedcap      2026-09-14T15:43:25  /tmp/harness/v2liftedcap.osm  — §34 (9) the census takes the LIFTED pinched-ramp cap (RULINGS 14am): rc 0, 494.9 s, ways 1010, nodes 23607, body_sha bdd053b93bbf, artifact ledger 5c0c2ded14c5, shared repo UNCHANGED. MATCHED PAIR: the same patch with the two o4_grade_law_cap_lifted tags stripped is /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2liftedcap/arms/nolift.osm (ADJUDICATED 3223 / law-true 4526 = the v2othhfix_r2 numbers exactly); as built 3204 / 4507. census_rows_diff EXACT 4507 MOVED 0 NEW 0 GONE 19 (all within_shape tunnel_ramp|tunnel_ramp on shapes 828/831). Census json/rows arms in /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2liftedcap
OTHH  patch    base a4b7801d   lane v2othhfix        2026-09-14T17:31:46  /tmp/harness/v2othhfix_r3b.osm  — ROUND 3 closing OTHH build (§34 (9) (4)-(5), RULINGS 2026-09-14aq) on claude/v2othhfix: rc 0, 262.3 s (warm), ways 1010, nodes 23615, body_sha a3c64e4a261c, artifact ledger 4afb62b3f6a1, shared repo UNCHANGED; verify DEFECT families EMPTY, rows 2189 -> 2146; census vs the owner's 1.0.334 patch ADJUDICATED 3204 -> 3174 (within_shape -35, road_cross_section +8 away from both pinched roads); route7 road levels byte-identical, route9 within 0.02 m, 0 of 118 service-road vertices moved > 0.1 m, 2 of 16,810 airside (0.10/0.12 m, apron|building corners)
OTHH  rebake   base a4b7801d   lane v2othhfix        2026-09-14T17:31:46  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2othhfix/r3_base2/structures.json  — ROUND 3 dry --stage structures (§34 (9) (4)-(5)) vs the lane's round-2 arm r2_fix: corridors 40 -> 40, refusals 50 -> 50; Terminal_Base_2_5@0/a climb_from 38.89 -> 36.50 (+2.4 m), pinched grade 36.98 % -> 25.18 %; Terminal_Base_2_1@2 6.30 -> 6.00, 11.05 % -> 10.80 %; mouth_z unchanged both; both pinched ramps report 'the road face edge (the pack paints no line here)' — OTHH carries NO road-edge marking (marks.py/marks2.py/marks3.py/pol.py beside it)
OTHH  rebake   base 9a49f136   lane v2splitname      2026-09-14T18:03:01  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2splitname/out/othh.lane.json  — 14at THE SPLIT FILE IS KEYED ON THE OFFSET IT BAKES — MATCHED PAIR of v2_rebake_replay plan --sampler mesh --runs 3 on the 1.0.334 OTHH products (o4_v2_rebake_OTHH.json + OTHH.graded.json + the installed Data+25+051.mesh, --dsf-dump the shared mod cache's +25+051.dsf.55d38455.text). othh.base.json = main 9a49f136 cut with git archive (145.99 s mean); othh.lane.json = claude/v2splitname 4b13e977 (140.26 s mean). Collisions (one file written by >1 placement with distinct offsets) 1 -> 0; distinct body files 1856 -> 1857; splits 705 bodies 1857 both arms; every row byte-identical bar the name (and the 531 anchor_reason/merged_into strings that quote a carrier's file name) — 0 differences beyond the tag. tunnel1 b0: idx 14052 -> __b0_8b16464a baking its own [9.0486,9.5497,-50.1039], idx 14051 -> __b0_c057eb1e baking [-8.8848,9.5497,-84.4220]. guard shared repo UNCHANGED both arms.
OTHH  rebake   base fe0a5b33   lane v2othhfix        2026-09-14T19:34:56  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2othhfix/r4b/structures.json  — ROUND 4 dry --stage structures (§34 (9) (6) the half-width margin) vs r3_base2: corridors 40 -> 40, none lost; Terminal_Base_2_5@0/a top_s 44.0 -> 40.0 (IN 4.00 m) grade 25.18 -> 53.95 %; Terminal_Base_2_1@2 top_s 18.9 -> 14.0 (IN 4.89 m) grade 10.80 -> 17.39 %; route7 half-width 3.32 m / route9 3.00 m; mouth_z unchanged. NO BUILD — the 54 % east ramp needs 14be's plate-edge full-depth point (not landed) to give the run back; ramp_in_road measured 0 in BOTH the owner's 1.0.335 patch and the lane's r3b build
OTHH  patch    base 88de7fec   lane v2othhramp       2026-09-14T20:43:50  /tmp/harness/v2othhramp.osm  — CLOSING OTHH build of lane v2othhramp (claude/v2othhramp caf7b9cc; the three coupled items of RULINGS 14bi): rc 0, 649.9 s, ways 1015, nodes 23714, body_sha 87ba777c8a94, shared repo UNCHANGED, verify defects {} (rows 7877). MATCHED CONTROL at the same tree = /tmp/harness/v2othhrampBASE.osm (worktree v2othhrampbase at bdd28759 = main 88de7fec + the v2othhfix half-width merge, rc 0, 511.9 s, body_sha b60c2dd4502b, artifact ledger cc0ead55f1f2 — a later --base-arm at that tree is served from it). A/B: law-true 8939 -> 8957, airside 8854 -> 8851, ADJUDICATED 7623 -> 7620; ramp_in_road 0 -> 0; hairline_pair 1316 -> 1337; airside vertices 22 of 20,001 moved > 0.02 m worst 0.060 m and 0 over 0.1 m; service-road vertices 0 of 116 moved > 0.02 m worst 0.010 m. Pinched grades east route7 53.95 -> 17.17 %, west route9 17.39 -> 18.06 %
OTHH  patch    base bdd28759   lane v2othhramp       2026-09-14T20:44:05  /tmp/harness/v2othhrampBASE.osm  — MATCHED CONTROL for lane v2othhramp: main 88de7fec + the claude/v2othhfix half-width merge, NONE of the three 14bi items. rc 0, 511.9 s, ways 1010, nodes 23605, body_sha b60c2dd4502b, artifact ledger cc0ead55f1f2, shared repo UNCHANGED, verify defects {} (rows 7881). Built in ritual worktree v2othhrampbase
OTHH  rebake   base bdd28759   lane v2othhramp       2026-09-14T20:44:06  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2othhramp  — MATCHED dry --stage structures TRIPLE for RULINGS 14bi: r0_base (bdd28759 = the half-width margin alone), r1_plate (the plate edge alone), r2_all (all three). tunnels 40 -> 42, wall corridors 25 -> 27, refusals 26 -> 26. EAST MOUTH Terminal_Base_2_5@0/a along the axis: wall-band end 38.89, PAD edge 36.50 (14at's reading), COVERING-PLATE edge 29.00, ramp top 40.00 with the half-width margin (44.00 without) — 9.9 m of uncovered corridor is ramp, grade 53.95 -> 17.17 %. WEST Terminal_Base_2_1@2: the plate covers the whole corridor so climb_from stands at the wall end 6.30 (the pad read 6.00), 17.39 -> 18.06 %. r1 and r2 are BYTE-IDENTICAL: §34 (10)'s generalisation changes nothing at OTHH beyond the §34 (9) pinch. dry.sh is the arm runner; basetree/ is the git-archive base tree

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

