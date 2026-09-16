# Brief pack — lane `v2stagepop`

Base: main `3ed236fd` · generated 2026-09-16 by `tools/brief_pack.py`

Read THIS file first and whole. Do not grep the spec, RULINGS or INDEX monoliths for
what is here; use `tools/docq.py` for anything else you need.

## Task

Stage 1's population invariant to groundside geometry (§20b (3)) — the pad line's last lever; measurement first

## The brief

The pad line's last lever (RULINGS 16t/16v; §16g (10) (11)–(12), §20b, §20c). Sites: `solve/design.py` (`_solve_stage`, the §20b dispatch, the stage-1 population — the rows/columns handed to stage 1), `solve/api.py`, `solve/rows.py` (which generators feed stage 1), `constraints/zones.py` / `constraints/strips.py` (the zone/strip rows a pad's presence removes from the ground under it — the likely mechanism), `constraints/cluster_pad.py` / `constraints/pads.py` (what a pad adds), `planar/overlay.py` (faces beside the airside). Reuse v2padclip r2's registered captures (HECA off/clip/on staged; LEMD off/on) and `v2_solve_replay --placement KEY=V` / `--why-at`; `pad_airside_arm --arm-a/--arm-b`. This lane MAY edit solve/design.py (the stage population only) — name every function; do not touch the qp solver (`design_qp.py`) or the projections. The peer's v2channel is merged (planar/channel*.py — do not touch). Never write the shared data repo or the X-Plane install; never --refresh-data; no --tile; matched pairs one tree/one capture/one variable; never compare across a corpus refresh.

## Bars

- MEASUREMENT FIRST (§20b (3) (4)): on the registered HECA staged captures (v2padclip r2: OFF / clip / ON arms, `staged_solve=1`, `solver = qp`), ONE table decomposing the 1,544 airside movers that survive dropping every pad row, by what the pad's presence changes in the STAGE-1 problem: rows removed (zone/strip rows under the pad), rows added, columns added/removed, face adjacency changed — counts, m² and the worst mover per class, with the stage-1 problem's row/column counts and sorted row keys on both arms diffed. Committed to the MEASURED block before any edit.
- The fix at the stage-1 population site: the stage-1 problem (rows, columns, sorted keys) byte-identical between the pads-OFF and pads-ON arms at HECA and LEMD — a twin asserts it.
- Solve-owned airside moved > 0.02 m OFF → ON: HECA 2,230 → 0, LEMD 485 → 0 (survivors named); runway 0; the one-vertex probe (HECA stability frame) ≤ 0.02 m beyond 250 m, max ≤ 0.0167 m (r2's number holds).
- A stage-2 row references an airside vertex only as a constant (a twin: no stage-2 column is an airside vertex).
- If every bar holds: `pad_from_cluster`, `pad_airside_clip`, `staged_solve` TRUE in law; ONE LEMD airport-path build — the T4 garage 40.4892214,−3.5944287 on `building45` at one level, fill named; census pairs HECA + LEMD by family, no family worse by > 5 % unnamed; else ship FALSE with the numbers.
- Suite by FAILED lines (zero); `shared repo UNCHANGED`.

## Files

Yours: `Ortho4XP/src/auto_patch_v2/solve/design.py`, `Ortho4XP/src/auto_patch_v2/solve/rows.py`, `Ortho4XP/src/auto_patch_v2/constraints/zones.py`, `Ortho4XP/src/auto_patch_v2/constraints/cluster_pad.py`
Other lanes' (do not touch): `Ortho4XP/src/auto_patch_v2/solve/design_qp.py`, `Ortho4XP/src/auto_patch_v2/planar/channel.py`

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

## §20b (3) STAGE 1'S POPULATION IS INVARIANT TO GROUNDSIDE GEOMETRY — AIRSIDE IS KING MEANS THE AIRSIDE SHEET DOES NOT KNOW THE PADS EXIST (Fable 2026-09-16; RULINGS 2026-09-16v; founded on v2padclip r2) — lane `v2stagepop`, measurement first

**The measurement (v2padclip r2, 16t).**  With the airside vertex set
invariant, the airside REGION pad-independent, `solver = "qp"` and
`staged_solve = true`, the pads-OFF → pads-ON pair still moves solve-
owned airside values at HECA by 2,230 vertices (worst 2.68 m; runway 2
at 0.020 m) and at LEMD by 485 (0.36 m; runway 0); with EVERY pad
generator dropped 1,544 / 2.00 m survive at the same coordinates.  The
`--why-at` chain at the worst mover is 15 hops of `apron_preference`,
`apron_edge_portion`, `no_step_pairs`, `apron_within_shape` — the
airside's own rows — against `pads` +0.04.  So the difference between
the arms is the SHEET the airside rows are priced on: with pads present
the ground under a pad no longer carries zone/strip rows, extra faces
and columns exist beside the airside, and the airside rows' neighbours
have changed.  §20b (1) made stage 1 solve the airside alone; it did
not make stage 1's POPULATION independent of what stands beside it.

**RULED.**  (1) Stage 1's sheet is derived from the airside cells and
their own strips/zones EXACTLY as if no pad, unit, cluster or
structure existed: the same faces, the same columns, the same rows on
the pads-OFF and pads-ON arms — a twin asserts the stage-1 problem
(row count, column count, the sorted row keys) is byte-identical
between the arms at HECA and LEMD.  (2) Stage 2 takes the stage-1
surface as constants on every airside vertex and solves the rest
(pads, units, ground); a stage-2 row may reference an airside vertex
only as a constant (the weld), never as a column.  (3) Bars: solve-
owned airside moved > 0.02 m between the pads-OFF and pads-ON arms → 0
at HECA and LEMD (survivors named); runway 0; the one-vertex probe
≤ 0.02 m beyond 250 m (r2's 0 of 32,575 must hold); then `pad_from_
cluster`, `pad_airside_clip`, `staged_solve` ship TRUE together and
the T4 garage seats on `building45` at one level in a real build.
(4) MEASUREMENT FIRST (mechanism before fix): r1 of the lane
decomposes the 1,544 survivors by what the pad's presence changes in
the stage-1 problem — rows removed (zone/strip rows under the pad),
rows added, columns added, face adjacency changed — one table with
counts and the worst mover per class, on the registered HECA staged
captures, before any edit; the fix then lands at the stage-1 population
site in `solve/design.py` / `solve/api.py` (the §20b dispatch) and at
whichever generator builds the ground rows the pad removes.

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

### §20c MEASURED (lane `v2qp`, branch `claude/v2qp` off main `63258868`)

**THE DIAGNOSIS IS CONFIRMED INTERVENTIONALLY, AND IT IS WORSE THAN
"UNSETTLED": THE SHIPPED SURFACE IS NOT THE MINIMUM OF ITS OWN
OBJECTIVE.**  F is convex, C¹ and piecewise quadratic, so accelerated
proximal gradient (FISTA with function restart) converges to its global
minimum from anywhere.  Run FROM the fixed point's own returned iterate on
the registered CYXY capture, with the one-way lag and the hard multipliers
FROZEN at what that solve returned — i.e. on exactly the problem it claims
to have solved — it drops F from **193 499.2357 to 190 618.15 in 9 s** and
moves **703 of 4 437 columns more than 0.02 m, worst 0.52 m**.  §20c's own
solver reaches **190 617.9104** (below FISTA's, from the other side), so
the two independent methods agree on the minimum and the fixed point stands
**1.489 % above it**.  A point that is not the minimum has no reason to be
stable, and that is 14bw's far field.

**§20c's SOLVER, AND THE DEVIATION (reported, not decided).**  The spec
names `highspy`'s QP.  MEASURED, in both textbook forms of this QP — the
epigraph form (a residual variable per row, diagonal Hessian) and the
normal-equation form (Hessian `A₀ᵀA₀` over the columns, L2 slacks for the
one-sided rows, L1-elastic slacks for the hard rows): HiGHS's QP is a
DENSE-NULLSPACE active-set solver.  It refuses at once — `ERROR: QP solver
has exceeded nullspace limit of 4000`, model status `Large nullspace`,
`Solve error` — because this problem's nullspace dimension IS its free
column count (4 437 at CYXY, 31 558 at HECA) and the limit's cost is
quadratic in it.  Raised to 200 000 it ran **630 s at CYXY without
terminating** (objective flat from ~230 s, nullspace dimension still
climbing) against the **3.2 s** solve it replaces.  The projections stay on
HiGHS because their QPs are small by construction (`project_runway`: 993
free columns at CYXY, nearly every row active); the whole-airport design
problem is not that shape.  What ships behind `solver = "qp"` is the SAME
convex QP solved exactly by the module's own linear algebra: the active
set's own subproblem PROXIMALLY damped (`min ‖A₀x−b₀‖² + Σ_active w(a·x−b̃)²
+ λ‖x−x_k‖²`, one extra diagonal block on the same stack, through the same
`_linear_solve`), λ ÷ 4 on an accepted step and × 6 on a rejected one.
`highspy` is imported at MODULE TOP in `solve/design_qp.py` and a twin
asserts it on the AST (memory `frozen-engine-lazy-imports`).

**WHY THE SHIPPED STEP FAILS, in one number.**  The fixed point takes the
UNDAMPED minimiser of the active set's subproblem and line-searches along
the ray from the previous iterate.  At CYXY that subproblem minimiser sits
at **F = 7.6e8** against F = 1.9e5 at the iterate it was taken from: the
ray is useless, the backtracking collapses to `_ALPHA_FLOOR`, and the
iteration exits `line_search_stalled` / `objective_stalled` — never
`same_set`, on every solve, exactly as 14bw measured.  Damping the
SUBPROBLEM instead of searching a ray out of it converges in **52
iterations / 94 linear solves / 1.2 s** at CYXY — LESS than the 3.2 s the
stalling iteration costs.

**THE ONE-VERTEX PROBE — THE BAR, MET.**  Matched pair on lane `v2settle`
r2's registered HECA stability frame (`scratchpad/v2settle/r2/heca.solved.pkl`,
base main `12400580`), the ONLY variable `[design] solver`; one extra 0.30 m
ceiling row at v9968 (30.12795521596, 31.4031429808), through
`v2_solve_replay --probe-site` (promoted there from `probe3.py`/`probe4.py`):

| arm | moved > 0.02 m | ≥ 100 m | ≥ 250 m | ≥ 500 m | worst | hard set under the probe |
|---|---|---|---|---|---|---|
| `fixed_point` | **959** / 31 820 | 959 | 959 | **953** | 0.5206 m | 39 → 25 rows |
| `qp` | **0** | 0 | 0 | 0 | **0.0043 m** (whole field) | 18 → **18** |

The bar was "moved only within 250 m"; the QP moves nothing anywhere by
more than 4.3 mm — under the elevation materiality — and its hard set does
not change under the perturbation either.  The same capture solved twice is
BITWISE identical on both arms (sha `cef4f5c8a773` / `01c2f08e40b1`).

**THE AIRSIDE SOLVE SETTLES — the campaign's first-ranked standing debt
(13y (B) / 13ab / 14as, owner-ranked first at 12s) closes.**  §20b staged,
HECA, one tree, the only variable `solver`:

| arm | stage 1 (AIRSIDE) hard | worst | SETTLED | stage 1 wall | stage 2 hard | worst | total |
|---|---|---|---|---|---|---|---|
| `fixed_point` | 35 / 174 500 | 0.0961 m | **no** | 87.6 s | 586 / 155 275 | 4.4203 m | 97.7 s |
| `qp` | **0** / 174 500 | **0.0200 m** | **YES** | 110.5 s | 572 / 155 275 | 4.4244 m | 119.8 s |

Stage 2 is the conforming side's own infeasibility (the pads) and is
unchanged; §20b (2)'s stage-2 substitution and both projections run on the
QP arm exactly as on the fixed point — ONE dispatch inside `_solve_stage`,
so the lag, the multiplier polish, both projections and every counter are
the same code on either arm.

**THE SINGLE SOLVE, three captures, matched replay pairs (`--emit` = the
build's own emit half; census by `harness/census.py`):**

| capture | wall | hard rows over 0.02 m | worst | lag worst leader | ADJUDICATED | law-true |
|---|---|---|---|---|---|---|
| CYXY (`12400580`) | 3.2 → 4.2 s (**1.31×**) | 17 → **12** (6 an infeasible set, both arms) | 0.5627 → 0.5627 | 0.319 → **0.162 m** | 427 → **379** (−11.2 %) | 1 396 → 1 350 |
| HECA (`b1b7704c`) | 127.4 → 131.0 s (**1.03×**) | 39 → **18** (4 → 3 infeasible) | 1.2595 → 1.2595 | 0.709 → 0.708 m | 26 634 → **26 607** | 63 824 → 63 816 |
| KCLT (`b1b7704c`) | 67.8 → 82.1 s (**1.21×**) | 29 → **19** (certificate FEASIBLE both) | 0.1100 → 0.1099 | 0.300 → 0.302 m | 6 607 → **6 515** | 17 975 → 17 675 |

NO FAMILY IS WORSE BY MORE THAN 5 % anywhere.  The largest backward moves
are HECA `airside_no_step` 7 735 → 7 745 (+0.13 %) and `taxi_box` 3 397 →
3 404 (+0.21 %), KCLT `transverse` 327 → 331 (+1.2 %) and
`drainage_minimum` 1 461 → 1 465 (+0.27 %, version-deferred).  Forward:
CYXY `airside_no_step` 46 → 31, `taxi_box` 24 → 17, `road_cross_section`
18 → 13; KCLT `within_shape` 11 448 → 11 179, `airside_no_step` 874 → 850,
`strip_arc` 6 → 2; HECA `strip_transverse` 357 → 348, `transverse` 1 320 →
1 314, `strip_arc` 28 → 26, `pad_airside_weld` 3 → 2.  The runway
projection's own read improves at CYXY (worst hard row 0.0044 → 0.0002 m).
The shipped patch DIFFERS by construction — a converged solve is a
different surface — and the diff above is the naming §20c asks for.
SPJC and OTHH have NO registered capture, so their censuses are NOT
measured (the frames registry carries patches, not captures, for both).

**THE CLOSING BUILD** — `build_airport.py HECA --tag v2qpHECA` with
`[design] solver = "qp"`: rc 0, **449.1 s**, `body_sha 73b5bdecfd98`,
artifact ledger `2f4e1c4f8717`, status `optimal`, v2-verify 30 592 rows,
`shared repo UNCHANGED by this build (full-surface before/after snapshot)`.
Its design line reads `QP (§20c): 6 exact solve(s), optimal x6, 197
round(s) / 358 linear solves, 50.09 s, worst |grad| 537.7` and
`18/329337 hard rows violated (max violation 1.2595 m ... 3 of them are an
INFEASIBLE SET ... min total shortfall 3.1661 m)`; census law-true 61 845,
ADJUDICATED 26 348.

**WHAT DOES NOT CHANGE, AND IS OWED.**  (a) The LAG: §20c says "no lag
rounds, no `follows` machinery", and this lane kept both — the one-way
split is a bilevel relation, not a term of one convex QP, and removing it
means either pulling the pavement toward the ground it shapes (a two-way
penalty) or making ~15 700 soft rows hard (the §20a/13ac refutation).  The
lag is measurably better under an exact inner solve at CYXY (worst leader
move 0.319 → 0.162 m) and unmoved at HECA (0.709 → 0.708), still NOT
SETTLED on both.  (b) The HARD ROWS stay `hard_weight` penalties under a
2-round augmented-Lagrangian polish, not QP CONSTRAINTS: made constraints,
the QP is INFEASIBLE at CYXY on the first try (HiGHS presolve, 0.0 s) —
which is the certificate's own reading (6 CYXY rows are a proven infeasible
set, min total shortfall 1.5889 m), so the elastic treatment is the law's,
not a solver convenience.  What is left is NAMED on all three captures.
(c) `hard_worst` / `read_hard_failure` / both projections / `set_exits`
are untouched; `set_exits` is simply EMPTY on the QP arm and `qp_solves`
(status, rounds, linear solves, objective, |grad|, wall) is what replaces
it in `line()` and `as_dict()` — a nested value under the existing `design`
sidecar key, no `SIDECAR_KEYS` edit.

**SHIPPED OFF: `[design] solver = "fixed_point"`.**  Every bar in the
brief holds, and the lane does not flip the default for two reasons, both
for the spec author's ruling: the SOLVER IS A DEVIATION from §20c's text
(HiGHS, measured and refuted at this scale — above), and with the key
flipped the suite reads **2 failed, 1 563 passed** where the two failures
are this lane's own `test_the_shipped_default_is_the_fixed_point` and
`test_v2taxidatum::test_a_chain_touching_a_runway_keeps_the_contact`, whose
runway contact stands **0.24564 m** under its ridge against a bar of
`crown × |off| + hard_tol` = **0.245 m** — 0.6 mm over, an order under the
0.01 m elevation materiality, and the QP's surface is the one that
MINIMISES the objective those rows are priced into.  With the key at
`fixed_point` the suite is **1 565 passed / 1 skipped twice**, and the
flip is one `sed` on `law/emit.toml`.

### §20c RULED (Fable 2026-09-15; RULINGS 2026-09-15b) — the deviation is accepted; the damped proximal step IS the §20c solver; the key flips ON

(1) **The tool was the deviation, not the law.**  §20c's substance is
that the one-sided problem is solved TO ITS MINIMUM by a globally
convergent convex method with a certificate.  HiGHS's QP was named as
the instrument; it is REFUTED for this problem class by measurement (a
dense-nullspace active-set solver whose cost is quadratic in the free-
column count, `nullspace limit` at 4 000, 630 s without terminating at
200 000 on CYXY's 4 437 columns).  The proximally damped active-set
subproblem — `min ‖A₀x−b₀‖² + Σ_active w(a·x−b̃)² + λ‖x−x_k‖²` on the
same stack through the same `_linear_solve`, λ ÷ 4 accepted / × 6
rejected — solves the SAME convex problem and agrees with FISTA at its
minimum (190 617.91 vs 190 618.15 at CYXY).  It IS the §20c solver.
HiGHS stays on the projections, whose QPs are small by construction;
the module-top `highspy` import and its AST twin stay.

(2) **The lag stays; the hard rows stay penalties with the certificate.**
A one-way row is a bilevel relation, not a term of one convex objective;
folding it in means pulling the pavement or hardening ~15 700 soft rows
(refuted 13ac / 14au).  The hard rows as CONSTRAINTS make the QP
infeasible at CYXY — the certificate's own reading (6 rows, 1.5889 m);
the certificate names them, the penalty solves around them.

(3) **The key flips ON.**  `[design] solver = "qp"` ships.  The bars
held on every measured count: the one-vertex probe moves NOTHING by
more than 4.3 mm (fixed point: 959 vertices, 953 of them beyond 500 m);
stage 1 SETTLES at HECA (0 / 174 500 hard, worst 0.0200 m — the
campaign's first-ranked debt closes); hard rows CYXY 17 → 12, HECA 39 →
18, KCLT 29 → 19, every survivor named; adjudicated census CYXY −11.2 %,
HECA −0.1 %, KCLT −1.4 %, no family worse by > 5 %; wall 1.03× HECA /
1.21× KCLT / 1.31× CYXY against the 2× bar.  The two twins that read red
under the flip are re-founded, not weakened: the solver-default twin
asserts `"qp"`; `test_v2taxidatum::test_a_chain_touching_a_runway_keeps_
the_contact` reads 0.24564 m against a 0.245 m bar — 0.6 mm, under the
0.01 m elevation materiality (CLAUDE.md convergence guard (a)), so the
bar becomes 0.25 m with the residual quoted in the twin's docstring.

(4) **Release sequencing (owner's OTHH priority).**  App 1.0.340 carries
the merge OFF: its surfaces are those of 1.0.339 bar the DEFECT floor —
the LEMD tile closes on it.  The flip lands in 1.0.341 for the HECA pad
read; the certified OTHH customer build stays on the fixed-point
surface until the owner rebuilds it on a flipped app and reads it.

(5) **Residual, named.**  KCLT `transverse` +1.2 % and `drainage_minimum`
+0.27 %, HECA `taxi_box` +0.21 % — under the 5 % bar, carried into the
owner's read.  SPJC / OTHH unmeasured (no registered capture) — the
sweep at 1.0.341's build time is the measurement.  The stage-2 hard set
(586 → 572, worst 4.42 m) is the pads' own infeasibility (§16g (10) /
§30 (4)), untouched by the solver and the HECA pad line's next item.

## Spec (object-placement) §16g (10)

### §16g (10) (4)–(5) WHAT CHAINS, AND A DERIVED PAD NEVER TAKES AIRSIDE GROUND (Fable 2026-09-14; RULINGS 2026-09-14ah) — lane `v2padcluster`

MEASURED (lane r2, HECA): with pads derived from clusters as hard flat
regions, 502,561 m² of new pad (94,795 m² from apron) moved 13,637 of
21,534 airside vertices (runway 1,110, worst 4.38 m) and put the terminal at
+10.83 m; the T3 district stayed ONE cluster of 9,334 bodies / 541,200 m²
because its footed bodies genuinely touch through the authored ground
slabs.

4. WHAT CHAINS.  Only WALLED bodies link a cluster.  A thin body — floor
   slab, plate, deck, canopy, road, apron object; solid height <
   `chain_min_height_m` (2.5 m), or classed deck/plate/pavement by the
   object stage — is a LEAF: seated on its own ground or carrier, never a
   link between two walled bodies.
5. A DERIVED PAD NEVER TAKES AIRSIDE GROUND.  The pad polygon is the
   cluster's outline clipped by every airside face; a cluster wholly on
   airside pavement gets no pad.  A cluster whose outline is in more than
   one piece is SPLIT at the pieces (each a cluster with its own pad).

BARS: HECA airside vertices moved > 0.02 m = 0; the terminal at 30.1279552,
31.403143 at its pad 72.50; `pad_cluster_mismatch` 0; the T3 district
resolved into its buildings (count, largest cluster's area named);
constraints ≤ +10 %; KCLT BUILD with outlines — `building80` 221.44 ± 0.02
and the terminal's members' seats unchanged; SPJC 19.56 dry.

### §16g (10) (6) A PAD SHARING AN EDGE WITH AIRSIDE WELDS TO IT (owner RULINGS 2026-09-14ai) — lane `v2padcluster`

A `building` pad that shares an edge with an airside face takes the airside
face's solved level along that edge — no step — and its plane meets it
within the pad's own slope cap; the airside is the datum (airside is king),
the pad never pulls it.  A pad that cannot meet its airside edge within cap
is `pad_airside_weld` (CRITICAL), never a terrace step.  The cluster seated
on such a pad follows the welded level.  BAR: every airside-sharing pad at
HECA and KCLT welded (step along the shared edge ≤ `hard_tol_m`), named with
its airside face.

### §16g (10) (7)–(8) LEAVES GET NO PAD; A PAD BENDS TO THE AIRSIDE AT ITS RIM (Fable 2026-09-14; RULINGS 2026-09-14aj) — lane `v2padcluster`

MEASURED (r3): (4)/(5) hold, yet 345,016 m² of new hard-flat pad beside the
apron moved 17,482 airside vertices — a shared vertex is one unknown.  A
derived pad cannot be (a) one hard plane, (b) welded to the apron along its
rim and (c) forbidden to move the apron all at once.
7. A derived pad is minted for a WALLED cluster only; a leaf (slab, plate,
   deck, canopy, road; §16g (10) (4)) seats on its own ground and mints no
   pad.
8. (a) is dropped AT THE RIM: a pad is flat (cap 0) across its interior and
   non-airside rim; along an airside-sharing edge its rim vertices are
   one-way followers of the airside (airside leads), and the plate meets
   them within the pad's slope ceiling (1 %) — a bent skirt, never a step.
   Twins asserting a two-sided cap-0 plate at an airside edge are re-founded.
BARS: HECA airside moved 0; the terminal body on its walled cluster's pad
within 0.02 m, the pad within 1 % of the airside it touches, its cut/fill vs
the disarmed ground named; `pad_cluster_mismatch` 0; `pad_airside_weld` 0;
constraints ≤ +10 %; KCLT build at the final tree (the terminal pad's weld
named); SPJC build carrying heights (19.56 ± 0.02).

### §16g (10) (8) REFINED — RIGID CORE, ONE-WAY SKIRT (Fable 2026-09-14; RULINGS 2026-09-14al) — lane `v2padcluster`

MEASURED (r4): a whole-plate one-way form leaves the plate no rigid
relation and it collapses; a two-sided ceiling row on the airside-sharing
pairs holds the plate but still pulls 14,263 airside vertices (worst 4.55
m).  So: the pad's vertices farther than `pad_skirt_m` (25 m) from any
airside-sharing edge form a cap-0 RIGID CORE; the SKIRT BAND within
`pad_skirt_m` follows the airside ONE-WAY within the pad slope ceiling —
the airside leads and is never pulled; the core stays a plate.  BARS: HECA
airside moved > 0.02 m = 0; the terminal at its pad (72.60); `pad_airside_
weld` 0 or each named; KCLT `building80` weld re-read; SPJC viaduct re-read.

### §16g (10) (4)–(6) MEASURED, ROUND 3 (lane `v2padcluster`, 2026-09-14; branch `claude/v2padcluster`)

**WHAT CARRIES THE T3 CHAIN, MEASURED FIRST (the round's first order).**
Per body of the largest cluster (`unit:43`, 9,334 bodies / 9,333 touch
edges), how many cluster edges pass through it:

| resource | edges | parts | solid extent | `base_y` | area |
|---|---|---|---|---|---|
| `T3_4.obj` | **1,822** | 1 | **0.00 m** | 15.73 | 1,161 m² |
| `T3_4.obj` | **1,772** | 1 | **0.00 m** | 15.73 | 1,161 m² |
| `metal_titles.obj` | 1,531 | 58 | 23.51 m | 3.73 | 25,477 m² |
| `Plastic.obj` | 1,165 | 238 | 22.07 m | 6.09 | 18,553 m² |
| `floor.obj` | 996 | 12 | 6.53 m | −0.63 | 14,415 m² |
| `door.obj` | 468 | 1 | 0.00 m | −0.46 | 589 m² |
| `concrete_3.obj` | 219 | 1 | 0.00 m | −1.84 | 17,383 m² |
| `strip_concrete.obj` | 41 | 1 | 0.00 m | −0.17 | 1,289 m² |

Two single-component CEILING PLATES carry **3,594 of the district's
9,333 edges** between them; six `T3_4.obj` bodies carry 3,598 endpoints,
`black_glass.obj` contributes 366 bodies all at extent 0.00, and
`concrete_3.obj` is 13cs's 17,383 m² ground slab.  **The district is held
together by its floor and its ceiling**, exactly as 14ah read it.

**THE ARMS.**  DISARM `v2padclusterHECAdisarm` (`97a2267cfc28`, 462.1 s)
against LANE `v2padclusterHECA4` (`cbefb8edcacb`, 384.4 s, ledger
`72fb36419b42`), both `[guard] shared repo UNCHANGED`.  `v2padclusterHECA3`
is byte-identical in its design surface (same `body_sha`) — the object-
stage half of (4) moves no vertex, which is itself the proof that the
unit rule and the cluster rule are separable.

| bar | DISARM | round 2 | round 3 | verdict |
|---|---|---|---|---|
| clusters | — | 1,954 | **4,278** | — |
| largest cluster over the pad threshold | — | 541,200 m² / 9,334 bodies | **171,086 m² / 1 body** | **(4) MET — the T3 district is resolved** |
| `pad_cluster_mismatch` (bar 0) | 33 | 44 | **27** | MISSED |
| `pad_airside_weld` (bar 0, new) | 16 | — | **24** | MISSED, and WORSE |
| **airside vertices moved > 0.02 m (bar 0)** | — | 13,637 of 21,534 | **17,482 of 29,465, worst 12.15 m; the runway 856 of 3,426, worst 3.14 m** | **MISSED** |
| `building` pad area | 867,173 m² | 1,369,935 | **1,212,189** | the clip gave 157,746 m² back |
| apron area | 2,935,484 m² | 2,841,363 | **3,012,902** | **(5) MET — the pads no longer eat the apron** |
| the terminal 30.1279552 31.403143, SURFACE (bar 72.50) | 72.07 | 82.90 | **80.94** | MISSED |
| the terminal's BODY off its own ground | — | `T3_49 b4` +7.66 m | **`T3_49 b3` +0.15 m, WITHIN 0.3** | **MET — it left the 52-member unit** |
| constraints stage (bar ≤ +10 %) | 83.46 s | +57 % | **129.67 s, +55 %** | MISSED |
| law-true census total | 62,116 | — | **77,288** | reported |
| suite | | | 1,475 passed, twice | MET |

**(5) WORKS ON THE MAP AND NOT ON THE SOLVE, AND THAT IS THE ROUND'S
FINDING.**  Clipping the pads out of airside did what it says: the apron
GAINS 77,418 m² instead of losing 94,795, and no pad overlaps a runway or
a taxiway.  The airside still moves 17,482 vertices.  The mechanism is
not overlap — it is the WELD: 345,016 m² of new hard-flat pad now sits
BESIDE the apron along its whole perimeter, and a shared vertex is ONE
unknown (09-01g, contact = value), so the pad's flat rows and the apron's
own rows are peers at every boundary node.  Clipping moved the conflict
from the interior to the edge; it did not remove it.

**(6) AS A CONSTRAINT WAS ATTEMPTED TWICE AND BOTH FORMS ARE REFUTED BY
MEASUREMENT.**  14ai's sentence — "the airside is the datum, the pad
never pulls it" — has two implementations and this lane measured both:

1. WITHDRAW the shared vertices from the pad's flat plate.  The pad then
   has no plate at its rim and loses its own law: the §30 twin's pad
   tilted to **2.6 % against a 1 % HARD ceiling**, and a pad between two
   pavements half a percent apart stopped being flat.  Narrowing the
   withdrawal to the cap-0 target and leaving the 1 % ceiling the whole
   rim did not save it (4 ruled twins still red).
2. Make those rows ONE-WAY with the airside vertex as LEADER (09-10l's
   own shape, a new head in `one_way_rulings` + `pad_flat_rulings`).
   **13 ruled twins go red**, including the plate's own two-sidedness
   (§30 "every rim pair priced, contacts included") and §28's frontage
   direction.

Both are rewrites of laws this lane does not own, so NEITHER SHIPPED.
What shipped is (6)'s CENSUS — `pad_airside_weld`, CRITICAL, computed
from the patch by node identity — and it reads **16 pads at DISARM and 24
with the derived pads**.  The step ACROSS a welded edge is 0 by
construction and is not what it measures; what it measures is the pad
pulled out of plane at the edge, which is the thing the owner's sentence
forbids and which is now visible for the first time.

**THE CONFLICT, STATED ONCE.**  A derived pad is (a) one hard plane, (b)
welded to the apron along its whole rim, and (c) forbidden to move the
apron.  Any two of the three can hold; all three cannot, and the three
are §30's pad law, 09-01g's weld and 14ai's airside datum respectively.
**STOP-and-report: nothing further is armed.**  The lever the owner must
choose among: drop (a) for pads that share an airside edge (the pad
becomes a level, not a plane, at that edge — and its 1 % ceiling with
it); drop (b) (a derived pad stands OFF the apron by a declared joint,
§23, and shares no vertex); or drop (c) and accept a bounded airside
movement with a stated cap.

**KCLT, AND THE REF IS NOT A HANDLE.**  `v2padclusterKCLT3` (rc 0,
274.2 s, `d19ae4797bc4`, guard UNCHANGED; no ledger key — the tree moved
during the run).  Read BY COORDINATE at 13bo's own site (35.2191877,
−80.9426007), because `building{N}` is an ORDINAL and the derived pads
renumber every later one: the terminal pad is **221.46 → 220.56 m**
(−0.90), 865 → 483 vertices, spread 1.07 → 0.51.  The bar was unchanged
within `hard_tol_m`: **MISSED by 0.90 m**, and the members' seats follow
it.  `building80` as a REF now names a 16-vertex pad elsewhere — quoting
it across these arms would have reported 3.77 m of pure renumbering.

**SPJC IS INERT AND SAYS SO.**  The registered frame
(`SPJC_20260913T214930`) carries no `Part.height_m`, so (4) stands down
by its own clause and the units are byte-identical — 4 units, `fu:0:0`
with 484 bodies / 24 members including `xp11_007` and `xp11_010`.  The
19.56 viaduct is untouched BY CONSTRUCTION, not by measurement; an SPJC
build carrying heights is OWED, as is a KCLT one at the final tree.

### §16g (10) (7)–(8) MEASURED, ROUND 4 (lane `v2padcluster`, 2026-09-14; branch `claude/v2padcluster`)

**THE ARMS.**  DISARM `v2padclusterHECAdisarm` (`97a2267cfc28`) against
LANE `v2padclusterHECA5` (rc 0, 420.6 s, `1112755a1db9`, ledger
`85c18b3071e6`); KCLT `v2padclusterKCLT4` (rc 0, 259.0 s, `2fa924a012cc`,
ledger `dca6d7449633`); SPJC `v2padclusterSPJC4` (rc 0, 82.1 s,
`7f9b9659d13c`, no ledger — 23 external-candidate deltas in the window,
another lane's).  All four `[guard] shared repo UNCHANGED`.  Suite
**1,474 passed / 1 skipped, twice**.

**(7) LEAVES GET NO PAD, MEASURED.**  Of HECA's 1,380,739 m² of cluster
outline, **359,152 m² in 1,518 pads are LEAVES** (no walled body) and
**175,708 m² in 821 more are walled but under `cluster_pad_min_m2`** —
together **39 %** of the pad area that sat beside the apron.  The emitted
pad area falls 1,212,189 → **1,091,467 m²** (DISARM 867,173).  The same
population is used by `classify` (which mints) and by the census (which
judges), so the mismatch family can never report a cluster that was never
given a pad.

| bar | DISARM | round 3 | **round 4** | verdict |
|---|---|---|---|---|
| **airside moved > 0.02 m (bar 0)** | — | 17,482 of 29,465, worst 12.15 m | **14,263 of 29,783, worst 4.55 m** | MISSED, worst −63 % |
| the RUNWAY alone | — | 856 of 3,426, worst 3.14 m | **1,021 of 3,426, worst 0.41 m** | worst −87 % |
| terminal 30.1279552 31.403143, SURFACE (bar 72.50) | 72.07 | 80.94 | **72.60** | **MET (+0.10)** |
| the terminal BODY | — | on `building11`, own ground +7.50 m | **`T3_concrete_white b4` on WALLED cluster pad `building298` at 72.62 via `fu:38:96@cluster_pad` (18 members), own ground +0.08 m; `metal b8` +0.05, worst foot +0.21 WITHIN 0.3** | ~MET (0.08 vs the 0.02 bar) |
| the terminal pad's CUT/FILL vs the DISARM ground | 72.07 | +8.87 | **+0.55 m of FILL**, cluster `fu:38:96@cluster_pad`, pad `building298` | named |
| `pad_cluster_mismatch` (bar 0) | 33 | 27 | **14** | MISSED |
| `pad_airside_weld` (bar 0) | **3** (worst 0.085 m) | — | **16** (worst 1.135 m, `building4 → pav1` over 51.5 m) | MISSED |
| constraints (bar ≤ +10 %) | 83.46 s | +55 % | **96.57 s, +15.7 %** | MISSED |
| law-true census total | 62,103 | 77,288 (+24 %) | **63,904 (+2.9 %)** | reported |

**WHERE THE CONSTRAINT COST GOES.**  `pad_flats` itself is 10.6 → **2.5
s** (the skirt prices fewer cap-0 pairs), and the LP is SMALLER than
round 3's (245,680 → 212,368 rows, 34,448 → 32,872 columns).  What
remains is the pad population: 823,018 → **838,816** `diffs`, i.e. 15,798
more difference rows over 1,091,467 m² of pad against 867,173.  The
residual +15.7 % is the price of the pads themselves, not of (8).

**(8)'s ONE-WAY CLAUSE IS REFUTED BY MEASUREMENT, AND ONLY THAT CLAUSE.**
14aj asks for the airside-sharing rim vertices to be ONE-WAY FOLLOWERS.
Built that way, a plate whose every binding is one-way has no rigid
relation to anything in the first lag round and does not chase back: the
§30 twin's pad collapsed from **703.56 to 640.89 m**.  09-10l's one-way
precedent is a LEVEL row — a mean against a leader band — which leaves
the PLATE holding the pad rigid; a whole plate one-way leaves nothing.
What shipped is the rest of (8): a pair with an end the pad shares with
airside is priced at the pad's own **slope ceiling** instead of the cap-0
flat target, so the pad is flat across its interior and its non-airside
rim and BENDS to meet the pavement it touches.  HECA: **8,967 skirt
rows**, 0 pairs dropped, **30 pads wholly inside pavement** kept their
two-sided plate (the OSM pad-in-an-apron class, which the skirt would
leave with no law at all).  That alone took the airside's worst move from
12.15 m to 4.55 m and the runway's from 3.14 to 0.41.

**THE TWINS, RE-FOUNDED AND NAMED (14aj's own instruction).**

| twin | asserted | now asserts |
|---|---|---|
| `test_constraints::test_strip_families_and_pads` | a cap-0 `Diff` over EVERY rim pair at `pad_flat` | the cap set is `{0, pad_slope_max}`; every ceiling-capped FLAT row has an airside end and every cap-0 row has none; the ceiling pass is still one row per pair over the whole rim (the ROW SET is unchanged) |
| `test_v2padlevel::test_a_pad_between_two_pavements_..._tiers_neither` | the pad's MEAN lies between its two frontages | the pad MEETS each frontage (a shared vertex IS that pavement's vertex, 09-01g) and its tilt stays inside the 1 % ceiling.  The bracket only ever held because a flat plate pinned at both edges must sit between them |
| `test_v2frontage::test_the_only_channel_left_is_the_two_way_apron_edge_ramp_law` | the two-way apron-edge ramp moves the pad < 0.05 m | the same claim, re-measured at **0.172 m**: a looser pad, the same channel, still downward, still the ramp's |
| `test_v2clusterpad` / `test_v2padcluster` fixtures | a cluster with no `walled` count | `_Cl` / `_Cluster` carry `walled`, because (7) drops a leaf |
| `verify.census.NOT_IMPLEMENTED` | — | gains `pad_cluster_mismatch` / `pad_airside_weld`: both are the CENSUS's and `verify` has no reader, so the lockstep twin must not expect one (CYXY v1 read 7 weld rows against v2's 0) |
| `test_v2padcluster::…pad_airside_weld…` | a least-squares plane residual against `hard_tol_m` | the SHARED vertex against its own pad's other vertices at `pad_slope_max·d`.  The first reading measured the bend (8) ALLOWS — HECA read 16 rows at DISARM and 36 with the skirt, the instrument counting the law working.  At the cap: DISARM **3**, LANE **16** |

**KCLT, AND THE −0.53 m IS THE WELD, NAMED.**  The terminal pad at
13bo's own coordinate (35.2191877, −80.9426007) is `building80`, 850
vertices, median **221.46 → 220.93** (round 3: 220.56), spread 1.07 →
**3.77**.  It shares **743 nodes with the apron `pav14`** (z 220.04 …
223.81) and 51 more with `pav118` — so the step across the weld is 0 by
construction and the pad's 3.77 m spread IS the apron's own fall across
the edge it is welded to.  The bar (unchanged within `hard_tol_m`) is
MISSED by 0.53 m and the movement is the weld's, which is what 14aj said
would make it lawful — **the owner's read is the acceptance.**  `pad_
airside_weld` 25 rows, worst `building80 → pav14` **1.384 m over 11.6 m**:
the pad could not reach that edge even bending at 1 %.

**SPJC, BUILT WITH HEIGHTS, AND THE VIADUCT MOVES.**  `xp11_007__b0` is
on pad `building7` at **20.07** in unit `fu:0:3@cluster_pad` of **6
members** — 13df's reading was **19.5604** in `fu:0:0@cluster_pad` of 24.
The leaf rule split the 24-member unit into 6 and the derived pad stands
0.51 m above it: **MISSED by 0.51 m**, and `building7` is also SPJC's
worst weld row (0.970 m over 20.0 m against `pav46`).

**THE SEVEN HECA BUILDINGS, AS FAR AS THE IDENTITIES REACH.**  A body
INDEX is as unstable as a pad ref — the cut renumbers bodies exactly as
the derived pads renumber `building{N}` — so only the bodies whose index
survived both arms can be quoted: `T3_38 b1` (14g's 160) `fu:43:7386@
cluster_pad` of 20 members on `building53` at 98.02, own ground **−6.70 →
+0.04 m** on `building160` in a 2-member unit; `T3_38 b4` (170) own
ground −0.02 → **−0.02**, WITHIN 0.3 both arms; `T3_38 b3` (147) median
ground 93.18 worst −2.45 → `building168` at 90.62, own ground −0.01,
worst **−0.33**.  `building_texture_4 b7/b8` and `building_texture_3
b29/b31` do not exist under those indices in either arm and were NOT
read.

**STOP-and-report.**  Three bars moved a long way (the terminal is MET,
the runway's worst move is 0.41 m, the cost is +15.7 %) and three are
still missed — airside 14,263, `pad_cluster_mismatch` 14,
`pad_airside_weld` 16.  The remaining airside movement is no longer the
pad pulling its own edge: it is the pad's SKIRT, bending at up to 1 %
over hundreds of metres, plus the 30 pads that keep a two-sided plate.
The lever the owner must choose among is now narrow: (i) a skirt WIDTH —
the bend is allowed only within N metres of the shared edge and the pad
is flat beyond it; (ii) the one-way form with a RIGID SEED (the plate
keeps a cap-0 core over its non-airside vertices and only the skirt band
follows), which is the form that did not collapse in the twin; or (iii)
accept a bounded airside movement with the 0.41 m runway figure as the
stated cap.

### §16g (10) (8) REFINED — MEASURED, ROUND 5 (lane `v2padcluster`, 2026-09-14; branch `claude/v2padcluster`)

**THREE ARMS, ONE TREE, LAW VALUES ONLY**, all against DISARM
`v2padclusterHECAdisarm`, all `[guard] shared repo UNCHANGED`:

| arm | `pad_skirt_m` | wall | `body_sha` | ledger |
|---|---|---|---|---|
| round 4's scope (the shared vertices) | — | 420.6 s | `1112755a1db9` | `85c18b3071e6` |
| **the 25 m BAND** | 25.0 | 433.5 s | `ee7d0f56911c` | `b63e49fd65b0` |
| **SHIPPED** (band 0 = the shared vertices, + 14al's withdrawal) | 0.0 | 451.5 s | `18e51b7d084e` | `a602bba1b858` |

| bar | DISARM | r4 scope | 25 m BAND | **SHIPPED** |
|---|---|---|---|---|
| airside moved > 0.02 m, of 21,523 (bar 0) | — | 10,048 | 10,683 | **9,573** |
| worst airside move | — | 4.55 m | 4.52 m | 4.55 m |
| **the RUNWAY** | — | 1,021, worst 0.410 | 1,394, worst 0.570 | **885, worst 0.390** |
| `pad_airside_weld` (bar 0) | 3 (worst 0.085) | 16 (worst 1.135) | 21 (worst 2.42) | **29 (worst 1.135)** |
| `pad_cluster_mismatch` (bar 0) | 33 | 14 | 14 | **14** |
| law-true census | 62,103 | 63,904 | 66,771 | **64,844** |
| the terminal body on `building298` | — | 72.62, +0.08 m | 72.62, +0.00 m | **72.60, +0.07 m** |
| constraints (bar ≤ +20 %) | 83.46 s | 96.57 (+15.7 %) | 102.43 (+22.7 %) | **109.69 (+31.4 %)** |

**14al's ONE-WAY CLAUSE IS REFUTED FOR THE THIRD TIME, ON A THIRD
SCOPE.**  14al adds the cap-0 rigid core precisely so round 4's collapse
cannot recur, and it does not recur — with a core the pad holds.  It is
still not STABLE: built with the band following the airside one-way,
§28's own frontage row — which its twin proves moves NOTHING — moved the
pad **0.12 m**, and at CYXY the census and the engine's verify came apart
on `mid_edge_step` (**77 against 14**), i.e. the lag leaves residuals the
two readers do not share.  A one-way row is LAGGED; a pad bound to the
airside only by lagged rows has nothing holding it inside a round.
09-10l's precedent is ONE level row per pad against a leader band, with
the plate still rigid underneath — a whole band of them is a different
thing.  The band therefore ships TWO-SIDED at the pad's slope ceiling.

**AND THE 25 m WIDTH IS REFUTED BY MEASUREMENT TOO.**  It is WORSE on
every airside bar — airside 10,048 → 10,683, the runway 1,021 → 1,394 and
its worst 0.410 → 0.570 m, `pad_airside_weld` 16 → 21 and its worst 1.135
→ 2.42 m, law-true 63,904 → 66,771 — and buys only the terminal body
+0.08 → +0.00 m.  A wider band softens more of the pad, and a softer pad
moves more of the apron inside the same ceiling.  `pad_skirt_m` keeps
25.0 as its documented design value and **ships at 0**, which is NOT "no
skirt" but the airside-SHARED vertices alone.

**WHAT 14al DID BUY, AND IT IS THE BEST ARM.**  Its other half — WITHDRAW
the two-sided ceiling row over a pair of two airside-shared vertices —
is what the shipped arm adds to round 4, and it is worth **4,008 dropped
pairs**: airside 10,048 → **9,573**, the runway 1,021 → **885** and its
worst 0.410 → **0.390 m**, law-true 66,771 → 64,844.  The pad no longer
has any two-sided row between two vertices the airside already owns.
Counters published per build: `pad_flats.airside_skirt_rows` 4,959,
`both_skirt_dropped` 4,008, `pads_core_only` 74, `pads_wholly_in_the_band`
**30** — those 30 are the pads with no plate left (the OSM
pad-in-an-apron class), which keep their two-sided plate; at the 25 m
band that count is 55 and is the answer to "how many pads are skirt
only".

**THE 14 `pad_cluster_mismatch` ROWS, ATTRIBUTED — ONE CLASS.**  12
`cluster_spans_pads` + 2 `pad_spans_clusters`, and every one is the SAME
defect: **the cluster piece and the emitted pad ref are cut in different
places.**  The cluster is cut by `geom.cluster_outlines` (the closed
outline's connected components, then the airside clip — which is why the
ids carry `/k`: `unit:43#16/0`, `/1`, `/3`), and the pad ref is cut again
downstream by `classify/evidence._pads` (the runway difference, the
boundary gate, `min_area`, §22.2's skirt drop, and the separately-unioned
FALLBACK footprints, one of which landing inside a cluster piece splits
it).  `building19` is claimed by `unit:43#16/0` AND `/1` — two pieces of
ONE cluster over one pad, the two cutters disagreeing about where the cut
is.  TO REACH 0: a cluster piece must be minted as ONE part and never
re-cut — `_pads` must not subdivide it, and a fallback footprint landing
inside one must be absorbed rather than mint its own ref.  NOT ARMED
(the round's attempts are spent).

**THE COST, NAMED.**  Constraints 83.46 → **109.69 s (+31.4 %)**, over
the +20 % the round accepted.  It is not the skirt: `pad_flats` runs in
2.6 s and the LP is SMALLER than round 3's (222,546 rows against
245,680).  It is the PAD POPULATION — 823,018 → **830,023** `diffs` over
1,091,467 m² of derived pad against DISARM's 867,173 — plus the per-pad
band walk, which is O(rim × shared) per pad and is the one piece of this
round's own work in the number.

**KCLT AND SPJC STAND ON THEIR ROUND-4 FRAMES.**  The one-way skirt is
not in the shipped law, so nothing it would have changed there was built;
the two-sided withdrawal changes the design surface, so the KCLT weld
(the terminal pad 221.46 → 220.93, 743 nodes shared with apron `pav14`)
and the SPJC viaduct (20.07 on `building7` in a 6-member unit against
13df's 19.56) are as round 4 measured them and were NOT re-built this
round — **owed**.

### §16g (10) (8) AMENDED — THE SKIRT YIELDS, NEVER THE AIRSIDE (Fable 2026-09-14; RULINGS 2026-09-14au)

MEASURED (lane v2settle): with the airside fixed, 143 `building_pad airside
skirt` rows at KCLT (26.4 m of shortfall) and 1,428 conforming rows at HECA
under §20b are INFEASIBLE BY LAW — a welded pad's 1 % ceiling and a fixed
apron rim cannot both hold.  RULING: the pad's skirt band takes whatever
slope the weld requires up to `pad_skirt_max_slope` (5 %) — a slope, never a
step; the core stays a cap-0 plate; the airside never moves.  Beyond 5 % the
pad is `pad_airside_weld` (CRITICAL).  BAR: KCLT's 143 infeasible skirt rows
→ 0 with each pad's skirt slope named; HECA's certificate re-read.

### §16g (10) (9) A PAD BETWEEN APRONS SLOPES WITH THEM; THE BUILDING SEATS AT THE LOW SIDE (owner RULINGS 2026-09-14ay/az; supersedes (8))

1. A pad touching an apron takes the apron's level along the shared edge;
   the apron within `cluster_apron_reach_m` (40 m, re-armed, bounded to the
   touching component, never across a taxi-family face) joins the pad's
   plane (§30 (4)); no skirt.
2. A pad sharing edges with apron on more than one side is a plane sloping
   up to 1 % between them (the apron law's own cap — always feasible, since
   the aprons across that span hold it); the cluster's datum is the pad's
   LOWEST shared-edge level: nothing floats, the high side is buried by at
   most 1 % × the span.
3. `pad_airside_weld` (CRITICAL) fires only for a shared edge with a
   non-apron airside face that cannot be met.
BARS: KCLT 143 / HECA 124 infeasible skirt rows → 0 (each pad named: the
apron area flattened within the reach, or its slope and low-side seat);
the reach never crosses a taxiway; airside moved vs pads-OFF = the
flattened apron area only.

### §16g (10) (11) THE PAD COVERS EVERY SEATED MEMBER — RE-ARMED UNDER THE CONVERGED SOLVER (Fable 2026-09-15; RULINGS 2026-09-15h) — lane `v2padqp`

**The reading (LEMD 1.0.340, owner 15e item 2).**  The T4 garage
`LEMD_OBJ-Airport_Terminal4_green-PKT4.obj` b0 (H 12.5 m, bbox 667 × 118 m)
is seated by unit membership (`fu:25:983@cluster_pad`, 8 members) on pad
`building12` at 616.10, but that pad's POLYGON (way −10157) ends 55.28 m
short of the garage; its own ground is 612.47 → **3.63 m of air over raw
DEM** (no graded face within 45 m).  Both other pad-minting paths refuse
on the pack's flat render datum (no crest plate; basin depth 0.58 m <
2.5).  This is exactly the mismatch (10) forbids — "no building or
cluster can span multiple pads … they should match exactly" (14x) — and
the mechanism that closes it, `pad_from_cluster`, ships OFF because its
far field moved under the non-converging fixed point (14bk).  §20c now
converges (the one-vertex probe: nothing beyond 4.3 mm).

**RULED.**  (a) A unit member seated on a pad whose polygon does not
contain the member's footprint is the `pad_cluster_mismatch` defect at
that member — never a silent seat over air.  (b) `pad_from_cluster =
true` and `pad_airside_clip = true` are RE-MEASURED under `solver =
"qp"` on ONE tree: the owner's site (the garage) and HECA's 14 mismatch
residual, with (4)–(9) unchanged (leaves get no pad; the skirt yields,
never the airside; between aprons ≤ 1 %, low side).  (c) The pad under
the garage is the cluster outline through PKT4 b0/b1 at the terminal's
datum (616.10, one plane per (9) unless an apron on the far side says
otherwise); the terrain rises to it through the one-way skirt, and
`cluster_apron_reach_m` stays 0 (14bk).  (d) If the far field still
moves with the converged solver, the probe names WHERE and the flag
stays OFF with that number — the mechanism is not re-litigated by
narrative.

### §16g (10) (11) MEASURED (lane `v2padqp`, 2026-09-15; branch `claude/v2padqp`)

**THE OWNER'S SITE IS FIXED, AND IT IS THE FIRST NUMBER.**  The T4
garage `LEMD_OBJ-Airport_Terminal4_green-PKT4.obj` at 40.4892214,
−3.5944287 stands, pads OFF (the shipped law, = 1.0.340), 55.3 m OUTSIDE
the nearest `building` pad — `building12`, 581 nodes, median 616.35 —
which reproduces 15h's "the pad polygon ends 55.28 m short" exactly.
With `pad_from_cluster` + `pad_airside_clip` armed the garage point is
INSIDE its pad: in the closing build `building45`, a 93-node face of a
ref whose EVERY face reads median **615.35** (spread 0.05 within the
containing face), i.e. ONE level over the terminal and the garage
together.  PKT4 is a member of the walled cluster `unit:25#843` (421,940
m², 761 walled bodies, 23 resources incl. `Airport_Terminal4-LEMD01`) —
so the chain rule of (6)–(8) already reaches the terminal and **was not
widened**; the pad is that cluster's own outline.  The terrain under the
garage is now the pad, not raw DEM: z − DEM at the site **+5.14 → +4.33
m of FILL** (replay arms), no step over a short edge (0.0 m) either arm.
The `float` bar (body zero vs its own ground) is the OBJECT stage's
reading and is NOT measured here — a harness patch build emits the
design surface only; it is owed to an app build.  What is measured is
the thing 15h attributed: the seat's pad now CONTAINS the member.

**THE ONE-VERTEX PROBE — AND (11) (d) FIRES.**  Registered HECA
stability frame, `v2_solve_replay --why-from … --probe-site
30.1279552,31.403143 --probe-arm solver=qp`, one 0.30 m ceiling row:

| pads-ON arm | moved > 0.02 m | ≥ 250 m | ≥ 500 m | worst | hard under the probe |
|---|---|---|---|---|---|
| clip at MINT (14ah's pre-split) | **0** / 32,262 | 0 | 0 | 0.0192 m (whole field) | 27 → 27 |
| clip at the ARRANGEMENT (this lane's (a)) | **16** / 32,182 | 16 | **16** | **0.1031 m** | 27 → 27 |

14bk's far-field mover is GONE under the converged solver with the pads
armed as `v2padcluster` r5 left them — nothing moves anywhere by more
than 4.3 cm, under the elevation materiality.  It COMES BACK, 16
vertices ALL beyond 500 m and worst 0.1031 m, when the mint stops
pre-splitting the outline and the arrangement's clip alone shapes the
pad — an interventional attribution of the residual far field to the
PAD/AIRSIDE RIM GEOMETRY, not to the solver.  Per (11) (d) the flag
stays OFF with that number.

**`pad_cluster_mismatch`, ATTRIBUTED AND PART-CLOSED.**  r5 left 14 and
named the cause ("the cluster piece and the emitted pad ref are cut in
different places").  Matched replay arms on ONE tree (census by
`harness/census.py`): HECA **16 → 10**, LEMD **1 → 1** (direct read of
`constraints.cluster_pad.pad_cluster_mismatch`: HECA 12 → 10, LEMD 3 →
2), and the owner's own T4 cluster LEFT the list — it was
`cluster_spans_pads unit:25#843/0 → building34/35/36`.  Three causes,
all at their single derivation site:

1. `_pads` cut the cluster polygon a SECOND time (the runway difference,
   `polygon_parts`) and gave each piece its own `building{N}`.  A part
   now takes ONE ref, its surplus pieces the tree's own `ref#k`.
2. `_face_map` joined on the RAW ref, so `building38` and `building38#1`
   — one pad to `publication` :597/:672 and `constraints/structures` —
   counted as two (LEMD `unit:25#1581`).  It joins on the base ref now.
3. The MINT pre-split the outline at the apt.dat airside union while the
   CENSUS split it at the PLANAR role faces — two cutters, and LEMD's T4
   cluster read as ONE 94,301 m² census piece against three minted refs.
   RULINGS 14ax already ruled the clip is `planar/overlay.airside_clip`'s;
   with that clip armed neither side pre-cuts now (with it disarmed both
   still do — 14ah's guard stands).  A piece under `[building_pad]
   min_area_m2` is also no longer judged: the mint drops it, so LEMD's 7
   m² and 3 m² slivers cannot make their building's ref a row.

**THE 10 HECA SURVIVORS ARE ONE CLASS, NAMED.**  Every one is
`cluster_spans_pads` over a NEIGHBOURING pad, and the instrument's own
per-FACE test is why: `_OWN_FACE_SHARE` asks whether a FACE is mostly
inside the cluster, so one sliver face of a big neighbouring pad puts
that whole ref on the list.  Measured: `unit:43#204` holds 94 % of
`building254`'s area and **2 %** of `building253`'s (8 faces, 4,373 m²);
`unit:43#612/0` 96 % of `building110` and **8 %** of `building107`;
`unit:43#844` 100 % of `building75` and 48 % of `building73`.  The
un-tried lever, named (the round's attempts are spent): weigh the REF's
own area inside the cluster, not one face's.  Survivors:
`unit:42#515/0`, `/2`, `unit:43#204`, `#267/0`, `#447/0`, `#612/0`,
`#687/1`, `#784/3`, `#844` and `pad_spans_clusters building281`; LEMD:
`unit:27#341/8` and `building25`.

**THE CENSUS PAIRS (matched replay arms, ONE tree, the only variable the
two `[placement]` keys).**

| | HECA OFF → ON | LEMD OFF → ON |
|---|---|---|
| ADJUDICATED | 26,608 → **26,285** (−1.2 %) | 1,371 → **1,376** (+0.4 %) |
| law-true total | 63,829 → 63,456 | 6,187 → 5,683 |
| `airside_no_step` | 7,747 → **7,487** | 455 → **445** |
| `within_shape` | 47,927 → **47,836** | 3,441 → 3,443 |
| `taxi_box` | 3,411 → **3,358** | 182 → 183 |
| `hairline_pair` | 2,749 → 2,795 (+1.7 %) | 1,882 → **1,388** |
| `pad_cluster_mismatch` | 16 → **10** | 1 → 1 |
| `pad_airside_weld` | 2 → **7** | 1 → **2** |
| `zone_on_pavement` | 0 → **0** | 0 → **0** |

WORSE BY MORE THAN 5 %, each named: HECA `pad_airside_weld` 2 → 7 and
`plane_gradient` 8 → 13 and `strip_seam_tear` 28 → 30; LEMD
`pad_airside_weld` 1 → 2, `strip_longitudinal` 4 → 5 and
`strip_transverse` 83 → 87.  `pad_airside_weld` is the bar's own
"0 new" clause and it is MISSED on both airports.

**THE AIRSIDE STILL MOVES, AND BY HOW MUCH.**  `airside_value_delta`
(canonical identity join, solve-owned frame, roles ∩
`law.tables.rolled_on_roles`) between the two HECA arms: **5,915**
airside vertices moved > 0.02 m, worst **3.61 m**; the RUNWAY **231**,
worst **0.140 m** (r5's shipped arm, a different frame: 9,573 and 885 /
0.390 m).  §16g (10) (5)'s bar is 0 and is MISSED; the runway is within
a tenth of a metre of quiet.

**THE CLOSING BUILD** — `build_airport.py LEMD --tag v2padqpLEMD2` with
both keys armed, on merged main: rc 0, **346.3 s**, ways 1,048, nodes
20,304, status `optimal`, `body_sha e5d30cf207a8`, artifact ledger
`50546224d866`, v2-verify 1,633 rows, and verbatim `[harness] shared
repo UNCHANGED by this build (full-surface before/after snapshot) — no
side-effect mutation`.  Its object stage reports the pad law defeating a
spurious pit at the garage: `refused basin:1 … 96 % under its own
objects' solids … a BASEMENT, not a pit: the terrain there is the
building's pad (building45) under the pad law`.  Suite **1,579 passed /
1 skipped** by FAILED lines.

**SHIPS OFF: `pad_from_cluster = false`, `pad_airside_clip = false`.**
Bar 6 is "flipped only if EVERY bar holds".  Three do not: the airside
moves (5,915 / 3.61 m), `pad_airside_weld` gains 5 rows at HECA and 1 at
LEMD, and `pad_cluster_mismatch` is 10 / 1 rather than 0.  The probe —
the reason 14bk shipped it OFF — is the bar that MOVED: under the
converged solver the pads-ON far field is nothing at all, or 16 vertices
at 0.10 m once the clip moves to the arrangement.  The owner's site is
fixed on the armed arm and the numbers above are the read it is
adjudicated on.

### §16g (10) (11) RULED ON THE MEASUREMENT (lane v2padqp r1 2039b3c0; Fable 2026-09-15; RULINGS 2026-09-15z) — the garage seats on its cluster's pad; the keys stay OFF until the AIRSIDE MOVEMENT is attributed

The garage (40.4892214, −3.5944287) with the keys armed: INSIDE
`building45` (the walled cluster `unit:25#843`'s own outline — 421,940
m², 761 walled bodies; the chain rule was never widened), one level
615.35 over the terminal and garage together, z − DEM +4.33 m of fill,
no short-edge step; the spurious basement pit refused as "a BASEMENT,
not a pit".  Three defects fixed at their derivation sites: `_pads`
re-cutting one cluster piece into separate `building{N}` refs (one ref
+ `ref#k` now); `_face_map` joining on the raw ref (`building38` vs
`building38#1`); the mint (apt.dat union) and the census (planar role
faces) cutting the airside differently.  `pad_cluster_mismatch` HECA
16 → 10, LEMD 1 → 1; the ten survivors are ONE class — `_OWN_FACE_SHARE`
is a per-FACE test, one sliver face of a neighbour lists the whole ref
(2 % / 8 % shares) — the untried lever: weigh the REF's area.  The one-
vertex probe with the pads as r5 left them: 0 of 32,262 moved > 0.02 m
— 14bk's far-field mover is GONE under §20c; with the clip moved to the
arrangement 16 vertices beyond 500 m, worst 0.103 m — the residual far
field is the pad/airside rim geometry, not the solver.

**MISSED, and why the keys stay OFF:** the AIRSIDE moved between the
OFF and ON arms — 5,915 vertices > 0.02 m, worst 3.61 m; runway 231,
worst 0.140 m (§16g (10) (5): a derived pad never takes airside ground;
airside is king) — r5's arm read 9,573 / 885 at 0.390 m, so this lane
halved it and did not close it; `pad_airside_weld` 2 → 7 HECA, 1 → 2
LEMD; HECA `plane_gradient` 8 → 13, `strip_seam_tear` 28 → 30; LEMD
`strip_transverse` 83 → 87.  RULED (r2): (a) ATTRIBUTE the airside
movement interventionally — `--why-at` on the worst airside mover
(3.61 m) and on the worst runway mover (0.140 m): which row set on the
ON arm reaches the airside (a pad weld row with the wrong direction? a
zone re-cut? the arrangement clip changing airside cells?) — the pad's
rows must be ONE-WAY toward the pad; an airside vertex that moves
because a pad exists is a defect at the row that moved it; (b) the
ref-area lever for the ten survivors; (c) the seven welds named.  The
keys flip ON only when airside movement is 0 (> 0.02 m) and the welds
are 0 new; the object-stage FLOAT at the garage (body zero vs its own
ground) is read on the next app build, not in the harness.

### §16g (10) (11) MEASURED, ROUND 2 (lane `v2padqp` r2, 2026-09-15; branch `claude/v2padqp`)

**(1) THE AIRSIDE MOVEMENT IS ATTRIBUTED, AND IT IS NOT A ROW OF THE PAD
LAW.**  `--why-at` on HECA's worst airside mover between the pads-OFF and
pads-ON arms (+3.610 m at 30.11038632205, 31.39574702991, roles `apron` +
`building`) named exactly ONE binding row on it: **the pad's own cap-0
plate**, `pads cap 0.00 % × 8.7 m`, dual **3.61**, over a vertex the
apron owns.  So the plate was pointed the one lawful way (below) and the
site re-read: the new worst mover (+3.28 m) carries **no binding pad row
at all** — its chain ends on an apron vertex `FREE: no binding row blocks
it … held by bending alone`.  The decisive count, by node identity
between the two emitted patches: of the **5,868** airside vertices that
moved, only **268** are SHARED with a pad at all; **5,600 touch no pad**
and still move up to 2.77 m.

**THE CHANNEL IS THE ARRANGEMENT CLIP, MEASURED INTERVENTIONALLY.**  A
third arm with `pad_airside_clip = true` and `pad_from_cluster = FALSE` —
the clip alone, no derived pad anywhere — against the same OFF arm:

| arm (vs pads-OFF) | airside moved > 0.02 m | worst | runway | runway worst |
|---|---|---|---|---|
| **clip ALONE** | **4,474** | **1.39 m** | 17 | 0.100 m |
| clip + derived pads | 5,973 | 3.28 m | 189 | 0.200 m |

Three quarters of the moved vertices and nearly half the worst move are
bought by the CLIP, which re-cuts the airside faces around every pad
(1,082 solve-owned airside vertices gone, 235 new) — a different
arrangement, a different triangulation, a different smoothness optimum
over the whole field.  14as (i) armed the clip to make the airside
REGION independent of the pads (area-null, and it is); the airside
VERTEX SET is not, and that is what moves the surface.  §16g (10) (5)'s
bar of 0 cannot be reached at the pad's rows: it is a question about
whether the airside may be re-noded by a pad at all, and that is the
spec's to rule, not this lane's.

**WHAT THE ROW-LEVEL FIX DID BUY, ON THE SHIPPED SURFACE.**  A plate pair
with ONE end on airside is now priced ONE-WAY toward the pad (new head
`structures.building_pad flat airside-led`, in `one_way_rulings` and
`pad_flat_rulings` — same plate, same price, one lawful direction); a
pair the airside owns at BOTH ends is withdrawn; a pad with fewer than
three vertices of its OWN keeps its two-sided plate (three points make a
plane — the pad-in-an-apron class, measured on the §30 (4) twin at 0.86 m
when the pairs were withdrawn anyway), and a cluster's cross-links are
built from own vertices.  Measured on the PADS-OFF arm, the same capture,
the only variable this code: ADJUDICATED **26,608 → 25,521 (−4.1 %)**,
`airside_no_step` 7,747 → **7,344**, `taxi_box` 3,411 → **3,169**,
`within_shape` 47,927 → **47,201**, `transverse` −5 — the shipped
fallback pads stop dragging the apron too.  The price is
`pad_airside_weld` **2 → 8**: where the pad now yields instead of pulling,
the census says so, which is the family's whole job (14ai).

**(2) `pad_airside_weld`: NO NEW ROW.**  HECA OFF → ON **8 → 7**
(r1: 2 → 7); LEMD **2 → 3**.  The bar's "0 new" holds at HECA; LEMD's one
row is `building7`-class (a pad that cannot reach its non-apron airside
edge) and is named in the census rows.

**(3) THE REF-AREA LEVER CLOSES THE MISMATCH.**  `_OWN_FACE_SHARE` now
asks the share of the REF's whole area, not one face's — a pad IS a ref,
and asked per face one sliver face of a neighbour listed the whole ref.
**HECA `pad_cluster_mismatch` 10 → 0** (pads OFF, the shipped fallback
derivation: **15**), LEMD 2 → **1** (`unit:27#341/8` over `building25` /
`building26`, the OldTerminal chain).  (10)'s own bar — "pads must match
building clusters … exactly" — is MET at HECA with the pads derived and
MISSED by the shipped derivation.

**(4) THE CENSUS PAIRS (matched replay arms, one tree, final code).**

| | HECA OFF → ON | LEMD OFF → ON |
|---|---|---|
| ADJUDICATED | 25,521 → 25,612 (+0.4 %) | 2,118 → **1,377** (−35 %) |
| law-true | 62,456 → 62,592 | 6,911 → **5,606** |
| `pad_cluster_mismatch` | 15 → **0** | 0 → 1 |
| `pad_airside_weld` | 8 → **7** | 2 → 3 |
| `airside_no_step` | 7,344 → **7,280** | 444 → **440** |
| `transverse` | 1,315 → **1,277** | 117 → **109** |
| `frontage_near_miss` | 28 → **20** | 8 → **2** |
| `plane_gradient` | 8 → 12 | 0 → 0 |
| `strip_seam_tear` | 28 → **28** | 0 → 0 |
| `hairline_pair` | 2,749 → 2,795 | 1,882 → **1,388** |

`strip_seam_tear` is CLOSED (r1's 28 → 30 is gone: +0).  `plane_gradient`
8 → 12 is the residual, named: four more rows on the derived pads'
own planes, the class r1 also carried.  LEMD `strip_longitudinal` 4 → 5,
`strip_arc` 7 → 8 and `strip_transverse` 84 → 87 are the same order.

**(5) THE KEYS STAY FALSE.**  Deliverable (1)'s bar — airside movement 0
— is MISSED (HECA 5,973 / 3.28 m, runway 189 / 0.200 m; LEMD 1,651 /
2.36 m, runway 43 / 0.070 m) and the attribution says why it cannot be
met by a pad row: three quarters of it is the arrangement clip's own
re-noding.  Deliverable (2) is MET at HECA and +1 at LEMD; (3) is MET at
HECA.  Suite **1,613 passed / 1 skipped**, 0 FAILED.  No closing build:
the keys did not flip.  The owner's garage still seats on `building45`
(93-node face, median **615.09**, z − DEM **+4.06 m** of fill) on the
armed arm.

### §16g (10) (12) THE ARRANGEMENT CLIP PRESERVES THE AIRSIDE VERTEX SET — A PAD IS CLIPPED BY THE AIRSIDE CELLS, THE AIRSIDE CELLS ARE NEVER RE-CUT BY A PAD (Fable 2026-09-16; RULINGS 2026-09-16b) — lane `v2padclip`

**The measurement (v2padqp r2, RULINGS 15ah).**  With `pad_airside_clip`
alone (no derived pads) the airside moved 4,474 vertices (worst 1.39 m,
runway 17 / 0.100 m) against the pads-OFF arm — three quarters of the
movement the pad line was held for: the arrangement clip DELETES 1,082
solve-owned airside vertices and MINTS 235, i.e. it re-nodes the
airside faces.  14as (i) made the airside REGION pad-independent; its
VERTEX SET is not.  The one binding pad row found (the cap-0 plate over
an apron vertex) was pointed one-way in r2 and is not the cause.

**RULED.**  (1) The airside cells' geometry and vertex set are computed
BEFORE any pad exists and are NEVER modified by the pad stage: a pad
polygon is the cluster outline MINUS the airside union, clipped BY the
airside cells (their existing edges become the pad's boundary where
they touch), and the pad's own vertices are new vertices on the
pad's side of that boundary; where a pad edge meets an airside edge
the pad takes the airside's existing boundary vertices (shared by
identity, §16g (10) (6) the weld) and adds none to the airside cell.
(2) An airside vertex present in the pads-OFF arm is present, with the
same id/position, in the pads-ON arm; the census family
`pad_airside_renode` counts airside vertices deleted or minted by the
pad stage (bar 0).  (3) With (1)–(2) in force the flag is re-measured
(the v2padqp bars): airside moved > 0.02 m between the OFF and ON arms
→ 0 at HECA and LEMD (named survivors), `pad_airside_weld` 0 new,
mismatch HECA 0 (ref-area share), LEMD 1 named, the far-field probe ≤
0.02 m; then `pad_from_cluster` + `pad_airside_clip` ship TRUE and the
T4 garage (40.4892214, −3.5944287) seats on `building45` at one level
with the fill under it (r2: 615.09, +4.06 m).  Consumer census first
(every reader of the arrangement / the airside cells / the pad polygon
/ `_face_map` / the census cutters — the two cutters r1 aligned).

### §16g (10) (12) MEASURED (lane `v2padclip`, 2026-09-16; branch `claude/v2padclip`, base main `7f80dc71`)

**THE CONSUMER CENSUS (RULINGS 2026-08-30l), BEFORE ANY CONSUMER IS
EDITED.**  The affected geometry is THE ARRANGEMENT'S NODED VERTEX SET —
not a new region, an exemption or a claim, which is why the table below
is short and its rows are all one seam: `planar/overlay.build_arrangement`
is the ONLY producer of it (`grep build_arrangement src` = one call site,
`planar/build.build`:161) and every other pass in the engine reads it
THROUGH `PlanarMap`.  So the census asks, per reader: *what does this
pass read that a change to WHICH VERTICES EXIST can move?*

| # | reader | what it reads of the arrangement | ruled interaction |
|---|---|---|---|
| 1 | `planar/build.build` :198-240 | `arr.faces` → `Face.ring/holes`, `vertex()` (exact-XY dedupe → the WELD: one coordinate = one unknown), `arr.regions` → `edge_kind_of_ref` / `quay_refs`, `arr.sources` → `_breaklines`, `arr.seam_bands` → `_seam_vertices` | THE one consumer. The airside faces it is handed must be the pad-free ones; the pad faces are additional faces that SHARE the airside's own coordinates and mint none of their own inside the airside union. Nothing else in the file changes. |
| 2 | `solve/design_roles.airside_stage_vertices` (§20b stage 1) | every vertex of an `airside_stage_roles` face | the stage-1 column set. A minted airside vertex is a NEW UNKNOWN in the airside problem and a deleted one removes a row — this is the channel 15ah attributed the 4,474-vertex far field to. Bar `pad_airside_renode` = 0 closes it BY CONSTRUCTION, not by a veto here. |
| 3 | `constraints/pads._pad_polys` / `_pad_groups` / `pad_flats` / `pad_shared` / `frontage_contacts` | pad FACE rings out of `PlanarMap` (`vw.rings`, `vw.holes`) | reads the pad's own face, never the airside's. The one-way plate at airside pairs (r2) is priced on SHARED vertices — preserved: the pad still takes the airside's own boundary vertices by identity (12) (1). UNCHANGED. |
| 4 | `constraints/pads._pavement_geoms` / `_pavement_faces` | airside pavement face rings | reads airside face geometry. It gets FEWER vertices (the pad-minted ones stop existing) and the same polygon: the clip is area-null (14as (i)), so every proximity read it does is unchanged in kind. |
| 5 | `constraints/cluster_pad._face_map` :227 / `plane_groups` / `pad_cluster_mismatch` | pad faces by `_base_ref` (r2's join) + `rolled_on_roles` faces for the cluster/apron reach | the CENSUS CUTTER. r1 aligned it with the mint (one ref per cluster piece, `ref#k` for the surplus); r2 made its share test the REF's own area. (12) does not move either cutter — it moves WHICH VERTICES the faces carry. UNCHANGED. |
| 6 | `constraints/pad_relief` / `pad_frontage_gs` | `_pad_polys` + `_pavement_geoms` | as 3 / 4. UNCHANGED. |
| 7 | `classify/roles.classify` :244-251 | subtracts the pad union from the airside REGION when `pad_airside_clip` is OFF | region-level, pre-arrangement. (12) changes nothing here; the key still selects the region-level behaviour. |
| 8 | `classify/evidence._pads` / `_cluster_pads` :499-518 | mints the pad polygons; pre-splits the outline at the apt.dat airside union only when the arrangement clip is DISARMED | THE MINT. (12) does not re-cut it. The guard at `_mint_airside` stands. |
| 9 | `planar/shapes.build_shapes`, `planar/zones.zone_regions`, `emit/*`, `verify/*` | `PlanarMap` faces/vertices | all downstream of 1; they read whatever the arrangement produced. None of them can distinguish a pad-minted airside vertex from a real one, which is exactly why the trim belongs at the single derivation site (CLAUDE.md's own preference) and not in any of them. |
| 10 | `tools/check_grade.py` / `harness/census.py` | the EMITTED patch | the instrument. `pad_airside_renode` is a SIDECAR-DECLARED family (the `eat_ceiling` / `seam_pins` pattern): the arrangement publishes what the pad stage did to the airside vertex set and the census reads it. A patch with no key reads exactly as before. |

NO consumer is vetoed and no consumer is edited: the whole change is at
`planar/overlay.build_arrangement`, the single derivation site.

**THE DEFECT REPRODUCED AND ATTRIBUTED (`tools/pad_airside_arm.py`, HECA,
one tree, ONE variable `[placement] pad_airside_clip`, `pad_from_cluster`
FALSE on both arms — the clip-alone arm of 15ah).**  `[guard] shared repo
UNCHANGED`.  Airside vertices (`solve/design_roles.airside_stage_vertices`,
never a hand list): OFF **19,435** → clip ON **18,710**, **GONE 1,008,
NEW 283** (15ah's build-frame reading: 1,082 / 235).

*THE 1,008 GONE ARE NOT DELETIONS — THEY ARE MINTS THE OFF ARM MAKES.*
Every one of the leading classes is a vertex incident to an APRON AND A
BUILDING PAD at once on the OFF arm — `apron:pav1 + building:building1`
116, `apron:pav132 + building:building289` 83, `apron:pav1 +
building:building7` 67, `…building4` 67, `…building6` 63 — i.e. the
UNCLIPPED pad ring crossing the apron, which splits the apron's own
edges.  With the clip armed the pad is differenced out of the apron and
those nodes have no reason to exist.  So §16g (10) (12) (2)'s frame as
written ("an airside vertex present in the pads-OFF arm is present in the
pads-ON arm") would score the pad stage's own pollution as the defect: the
OFF arm is the POLLUTED one.  **The frame that survives measurement is the
invariance frame: the airside vertex set must be the SAME on every pad
arm, because it is a function of the airside alone** — which is (12) (1)'s
own sentence, and (2) read as a bar on either direction.  `pad_airside_
renode` is therefore counted as DELETED ∪ MINTED against the pad-free
airside, on each arm, and its bar 0 subsumes (2).

*THE 283 MINTS ARE TWO CLASSES, BOTH THE NODING'S.*  `PAD_AIRSIDE` on the
clip arm: `pads 384, clipped 59, snapped_pads 58, snapped_vertices 419,
snap_max_m 4.8, snap_too_far 75 (max 70.76 m), snap_refused_overlap 2,
snap_refused_invalid 1, kept_wholly_on_airside 8`.
(a) THE UNSNAPPED CROSSING POINT — 75 of the clip's own crossing points
stand further from a rim NODE than `pad_airside_snap_max_m`, so they split
a rim edge and mint an airside vertex that exists only because the pad
does.  The rim they snap to is `AirsideRim(air, …)`, built from the airside
REGION rings — NOT from the arrangement's own node set, which also carries
every crossing the runway sources, the zone edges and the seam bands mint
INSIDE the airside.  A pad vertex near one of those can never snap.
(b) THE GLOBAL SNAP-ROUND — the whole line set is noded in ONE
`shapely.unary_union(…, grid_size=min_distinct_spacing_m)`, and
snap-rounding is a GLOBAL operation: adding or removing ANY line can move
an unrelated vertex by up to half a cell.  Measured directly in the pair:
`NEW vertex → nearest OFF-arm airside vertex` has **min 0.500 m**, p50
2.55 m, and the matching GONE/NEW couples read as one vertex MOVED — e.g.
`apron:pav1 + service_road:route0` at (30.10639358515, 31.38950704486) on
the OFF arm and (30.10639809557, 31.38950704376) on the ON arm, the same
node 0.5 m apart.  228 of the 283 stand over 1 m from any OFF-arm airside
vertex and 106 over 5 m; only **4 of 283** lie on the OFF arm's airside
boundary at all.  **No amount of rim snapping can fix (b): while the pads
are noded in the same pass as the airside, the airside vertex set is a
function of the pad set.**  That is the mechanism (12) (1) names, and the
fix is structural — the airside is noded BEFORE the pads exist and the pad
stage may only ADD vertices outside the airside union.

**WHAT SHIPPED (12) (1), AT THE ONE DERIVATION SITE.**
`planar/overlay.build_arrangement` is now TWO PASSES over one line set,
and that split IS the rule:

* PASS A nodes everything the airside is made of — every non-pad region
  ring, the runway-profile stations, the taxi/road cut lines, the zone
  rings and the seam bands — in the same single `unary_union(...,
  grid_size=min_distinct_spacing_m)` as before.  Its node set IS the
  airside cells' vertex set, and it is a function of the airside alone.
* PASS B adds the PADS to that result.  Each pad is differenced by pass
  A's own grid-snapped airside union (`airside_union`, ONE derivation,
  read by the clip and by the re-node census alike), and the rim its
  crossing points quantise to is built over PASS A'S OWN NODES
  (`AirsideRim(..., nodes=)`), not the region ring's — measured at HECA,
  6,272 ring nodes against **8,775** arrangement ones, which is why 75
  crossing points had nothing to reach (`snap_too_far_max_m` 70.76 m).
* THE DENSIFIER MAY NOT NODE THE RIM EITHER (`_drop_rim_midpoints`):
  `ring_lines` densifies every ring at its OWN role's chord cap, so the
  `building` cap's midpoints landed on airside edges the airside cap had
  spaced differently and split them.  A pad coordinate on the rim that is
  neither one of pass A's nodes nor a vertex of the pad's own polygon is
  dropped — 24…37 per HECA arm.  The `own` test is load-bearing: dropping
  pad CORNERS collapsed the three `test_v2padlevel` fixtures whose pad
  merely touches its apron along a straight edge.
* A PAD WHOLLY ON AIRSIDE IS DROPPED, not kept.  (12) (1)'s own sentence
  is "a pad polygon is the cluster outline MINUS the airside union" and
  §16g (10) (5) already said a cluster wholly on airside pavement gets no
  pad.  It was KEPT as the §30 / 14ai pad-in-an-apron class, and MEASURED
  it was the ONLY re-node class left once the airside was noded first:
  HECA **548 of 553** minted nodes, every one STRICTLY INSIDE the airside
  union.  The four ruled twins that encoded the class are RE-FOUNDED, not
  weakened — a building that really does stand in an apron IS A HOLE in
  that apron, so `test_v2bank`'s `pad_map` and `test_constraints`'s
  `synthetic` now carry the pad as the apron cell's own hole and every
  claim they make (the weld by identity, the flat target, the 1 % hard
  ceiling, the pure-hole pad minting no level row) reads exactly as
  before.  `test_v2bank`'s pad is 40 m on a side rather than 60 because
  the HOLE ring is densified at the APRON's chord cap and a 60 m edge came
  back split at its midpoint, which cost the pin twin its own premise.

(12) (2) SHIPS AS A CENSUS FAMILY, `pad_airside_renode`, sidecar-declared
in the `eat_ceiling` / `seam_pins` shape: the arrangement publishes
`[lat, lon, "minted"|"deleted"]` per node (`pipeline/publication.
_renode_rows` off `planar/overlay.PAD_AIRSIDE`) and `check_grade` emits
one row each.  An ABSENT key means NOT MEASURED and an EMPTY list means
MEASURED ZERO — publishing `[]` either way made all four of this lane's
matched REPLAY arms read a perfect family, because a replay resumes from
a captured planar map and never builds an arrangement; `v2_solve_replay
--capture` therefore carries the arrangement's own reading in the pickle
and `--replay` restores and prints it.

### §16g (10) (12) THE NUMBERS

**(a) THE RE-NODE IS CLOSED — `renode_deleted` 0 ON EVERY ARM.**
`tools/pad_airside_arm.py` (ONE load, classify+planar twice, the airside
population read from `solve/design_roles.airside_stage_vertices`), one
tree, `[guard] shared repo UNCHANGED`:

| airport / arm | deleted | minted | on the rim | inside airside |
|---|---|---|---|---|
| HECA, shipped law (both keys false) | **0** | 40 | 5 | 35 |
| HECA, clip alone | **0** | 40 | 5 | 35 |
| HECA, clip + derived pads | **0** | 43 | 4 | 39 |
| LEMD, shipped law | **0** | 150 | 85 | 65 |
| LEMD, clip + derived pads | **0** | **32** | 9 | 23 |

Before the rule, the clip alone at HECA read **1,008 deleted / 283
minted** against the shipped arm (15ah's build frame: 1,082 / 235), and
the pad-in-an-apron class alone accounted for 553 → 40 of the minted.
THE RESIDUAL IS ONE CLASS AND IT IS NAMED: an unsnappable CROSSING POINT
(`snap_too_far`, 68 at HECA) standing on a rim segment, plus the 2–3
`snap_refused_overlap` pads whose snap is withdrawn and whose clip
polygon keeps a sliver inside the union.  The second attempt on it —
making such a crossing RETREAT off the rim by the hot-pixel band instead
of standing on it — IS REFUTED: it takes the WELD with it (09-01g /
§16g (10) (6)), and `test_v2padlevel::test_a_pad_between_two_pavements_
half_a_percent_apart_stays_flat_and_tiers_neither` read **ZERO shared
vertices** on both its frontages.  The attempts are spent.  The un-tried
lever, named: the law value `pad_airside_snap_max_m` (5.0 m), which
trades pad distortion along the rim for these nodes.

**(b) AND THE AIRSIDE STILL MOVES, WHICH IS THE ROUND'S FINDING.**
`tools/airside_value_delta.py`, HECA, solve-owned frame, the `building`
(pad) vertices excluded so the number is airside and not the pad:

| pair | moved > 0.02 m | worst | runway | runway worst |
|---|---|---|---|---|
| pads OFF → pads ON (the bar) | **6,031** | 3.09 m | 180 | 0.130 m |
| OFF → the CLIP ALONE | 4,787 | 2.06 m | 19 | 0.070 m |
| clip → clip + derived pads | 3,875 | 3.14 m | 157 | 0.110 m |
| the same pair under §20b `staged_solve` | **2,018** | 2.69 m | **3** | **0.020 m** |

15ah read OFF → ON 5,973 / 3.28 m and the clip alone 4,474 / 1.39 m on
its own tree.  **So the airside vertex set is now invariant and the
airside VALUE moves as much as it ever did** — which REFUTES 15ah's
attribution as a complete explanation.  A re-noded arrangement was real
and is now gone; it was not what moved the surface.  The interventional
arm above names what does: with the vertex set held fixed and the ONLY
variable §20b's `staged_solve`, the runway's moved set falls from **157
vertices / 0.110 m to 3 / 0.020 m** — at the elevation materiality.  The
pads' own rows reach the airside because the design problem is solved
JOINTLY; §20b stage 1 solving the airside alone and substituting it is
what freezes it.  §16g (10) (5)'s bar of 0 is therefore a question for
§20b, not for the pad law, and this lane does not re-litigate it by
narrative.

**(c) THE OWNER'S SITE IS FIXED AND READS AS r2 LEFT IT.**  The LEMD T4
garage `LEMD_OBJ-Airport_Terminal4_green-PKT4.obj` at 40.4892214,
−3.5944287, pads ON: INSIDE **`building45`**, a **93-node** face, way
−10991, altitudes **615.05 … 615.11** — ONE LEVEL, spread 0.06 m — with
no step over a short edge.  Pads OFF, the shipped law: **0 ring groups
cover the point** (15h's "the pad polygon ends 55.28 m short").

**(d) THE CENSUS PAIRS (matched replay arms, ONE tree, the only variable
the two `[placement]` keys; `harness/census.py`).**

| | HECA OFF → ON | LEMD OFF → ON |
|---|---|---|
| ADJUDICATED | 19,456 → **18,686** (−4.0 %) | 2,121 → **1,004** (−53 %) |
| law-true | 61,185 → 59,755 | 6,479 → 4,865 |
| `pad_cluster_mismatch` | 15 → **0** | 0 → 1 |
| `pad_airside_weld` | 9 → **8** | 2 → 3 |
| `airside_no_step` | 5,457 → **5,172** | 335 → **320** |
| `within_shape` | 48,707 → **47,901** | 4,253 → **3,025** |
| `taxi_box` | 2,679 → **2,481** | 135 → **131** |
| `mid_edge_step` | 21 → **2** | — |
| `vertex_to_edge_step` | 7 → **0** | — |
| `frontage_near_miss` | 47 → **21** | 14 → **3** |
| `hairline_pair` | 2,836 → **2,792** | 1,642 → **1,287** |
| `transverse` | 1,002 → **978** | 39 → **34** |

WORSE BY MORE THAN 5 %, each named: HECA `plane_gradient` 9 → 14 and
`strip_seam_tear` 28 → 33 and `strip_longitudinal` 3 → 4; LEMD
`pad_cluster_mismatch` 0 → 1 (`unit:27#341/8`-class, r2's own named
survivor), `pad_airside_weld` 2 → 3, `strip_longitudinal` 1 → 2 and
`raoa` 0 → 1.  `pad_airside_weld` HECA 9 → 8 MEETS the "0 new" clause;
LEMD's +1 is the `building7` class r2 named.

**SHIPS OFF: `pad_from_cluster = false`, `pad_airside_clip = false`.**
Bar 6 is "flipped only if EVERY bar holds".  The re-node bar HOLDS on
`deleted` and is missed on `minted` by one named class (HECA 40/43, LEMD
32); the AIRSIDE MOVEMENT bar is missed by 6,031 vertices and is now
attributed, interventionally, to §20b rather than to the pad law.  No
closing airport build: the keys did not flip.
### §16g (10) (12) MEASURED AND AMENDED (lane v2padclip r1 104c7b43; Fable 2026-09-16; RULINGS 2026-09-16r) — the vertex set is invariant now; the VALUE still moves because the problem is solved jointly → §20b staged solve ON under §20c; (2) reworded to the invariance reading

**Measured.**  `build_arrangement` in two passes (A: every non-pad line;
B: pads on that result), `airside_clip` un-gated and dropping a pad
wholly on airside, `AirsideRim` noded on the arrangement (HECA 6,272
ring nodes → 8,775): `pad_airside_renode` deleted **0** on every arm
(was 1,008 at HECA with the clip alone), minted 40–43 HECA / 32 LEMD
(one class: an unsnappable crossing, `snap_too_far` 68 — the untried
lever is `pad_airside_snap_max_m` 5.0; RETREATING the point took the
weld with it and is refuted).  The owner's garage: inside `building45`,
615.05…615.11, one level.  `pad_cluster_mismatch` HECA 15 → 0;
`pad_airside_weld` HECA 9 → 8.  AND the airside VALUE still moves OFF →
ON: HECA 6,031 vertices, worst 3.09 m, runway 180 / 0.130 m — as much
as 15ah read.  The interventional arm (clip+pads, the ONLY variable
`staged_solve`): runway 157 / 0.110 m → **3 / 0.020 m**, airside 3,875
→ 2,018.  The pads' rows reach the airside because the design problem
is solved JOINTLY; the re-noding of 15ah was real, is closed, and was
not what moved the surface.

**RULED.**  (a) (12) (2) is reworded to the invariance reading the
lane implemented: airside vertices deleted ∪ minted by the pad stage,
measured against the pad-free airside per arm, = 0 — the OFF arm was
the polluted one and cannot be the reference.  (b) §16g (10) (5)'s
bar (a derived pad never takes airside ground) is met by §20b, not by a
pad row: `staged_solve = true` ships with `solver = "qp"` — stage 1
(AIRSIDE) SETTLES under §20c (15b: 0 / 174,500 hard, worst 0.0200 m),
stage 2 conforms with the airside FIXED.  r2 measures the remaining
2,018 movers under the staged solve interventionally (`--why-at`: which
stage, which rows — a stage-2 substitution touching a shared weld
vertex is a §20b (2) defect) with the bar 0 > 0.02 m on solve-owned
airside, HECA and LEMD; then `pad_from_cluster`, `pad_airside_clip` and
`staged_solve` ship TRUE together if every bar holds.  (c) The last
piece of (12) (1): `classify/roles.classify` (:244–251) still subtracts
the pad union from the airside REGION when the clip is off — the `if`
goes (v2shoulderband r2 is merged; the file is free).  (d) Before the
merge of r1, the SHIPPED arm's identity: the two-pass arrangement and
the un-gated clip run on the OFF arm too — HECA and LEMD OFF-arm replay
pairs main-before vs branch must be byte-identical or each difference
named (the lane reported OFF → ON pairs only).

### §16g (10) (12) MEASURED, ROUND 2 (lane `v2padclip` r2, 2026-09-16; branch `claude/v2padclip`, base main `1bc93833` then `782a50d6`)

**(1) THE SHIPPED ARM IS NOT BYTE-IDENTICAL, AND r1 ALONE MADE IT WORSE —
WHICH IS WHY (12) (1) (c) IS NOT OPTIONAL.**  OFF-arm (both keys false)
matched replay pairs, base main `1bc93833` cut into its own ritual
worktree against the branch, one variable (the lane's code):

| | HECA base → r1 | HECA base → r1+(c) | LEMD base → r1 | LEMD base → r1+(c) |
|---|---|---|---|---|
| ADJUDICATED | 19,032 → **19,826** (+4.2 %) | 19,032 → **19,076** (+0.2 %) | 1,749 → **2,159** (+23 %) | 1,749 → **986** (−44 %) |
| law-true | 59,215 → 60,506 | 59,215 → **59,114** | 6,257 → 6,630 | 6,257 → **4,850** |
| `airside_no_step` | 5,171 → 5,421 | 5,171 → **5,138** | 322 → 334 | 322 → **321** |
| `hairline_pair` | 2,767 → 2,808 | 2,767 → **2,230** | 1,819 → 1,670 | 1,819 → **1,272** |
| `taxi_box` | 2,511 → 2,654 | 2,511 → **2,511** | 119 → 127 | 119 → 122 |
| `frontage_near_miss` | 29 → 47 | 29 → **27** | 8 → 14 | 8 → **0** |
| `pad_airside_weld` | 8 → 9 | 8 → **8** | 2 → 2 | 2 → **1** |

THE MECHANISM, NAMED: with the arrangement clip un-gated (r1) and
`classify/roles`'s `if` still standing, the pad was CUT TWICE on the
shipped arm — once out of the airside REGION at classify, then again at
the arrangement, where the rim snap moved **1,700 pad vertices** (HECA,
`snapped_vertices`).  Neither cut is wrong; making both is.  With (12)
(1) (c) landed there is ONE cutter and it is the arrangement's, and the
shipped arm comes back to parity at HECA and materially better at LEMD.
The surface still CHANGES — the airside value moves 5,961 (HECA, worst
2.42 m, runway 60 / 0.090 m) and 1,286 (LEMD, worst 2.22 m, runway 1 /
0.020 m) — because the airside region is no longer a function of the
pads, which is a DEFECT FIXED and not a free change: it is the last
clause of (12) (1).  `pad_cluster_mismatch` and `strip_seam_tear` are
unmoved; the named regressions are HECA `within_shape` +479,
`mid_edge_step` 13 → 21, `road_cross_section` +11, `vertex_to_edge_step`
2 → 4 and LEMD `taxi_box` +3, `strip_longitudinal` 1 → 2.

**(2) (12) (1) (c) CLOSES THE AIRSIDE REGION.**  `classify/roles.classify`
no longer differences the airside region by `ev.pad_union` at all (the
key kept its other job, the mint's pre-split guard).  MEASURED at LEMD
(`tools/pad_airside_arm.py`, OFF vs ON): **apron faces 106 on BOTH arms**
(before: 180 vs 106); the OFF arm's `renode_minted` **150 → 12**; the
cross-arm airside vertex set GONE/NEW **1,484 / 254 → 23 / 43**.

**(3) §20b UNDER §20c — THE STAGED ARMS, AND THE BAR IS STILL MISSED.**
`solver = "qp"` (the shipped default since 15b) with `--design-weight
staged_solve=1`, OFF → ON, solve-owned frame, pad vertices excluded:

| | moved > 0.02 m | worst | runway | runway worst |
|---|---|---|---|---|
| HECA unstaged | 2,230 … (r1 frame 3,875) | — | — | — |
| **HECA staged** | **2,230** | 2.68 m | **2** | **0.020 m** |
| **LEMD staged** | **485** | 0.36 m | **0** | — |

The RUNWAY bar is MET (LEMD 0; HECA 2 vertices AT the 0.02 m elevation
materiality — PASS-with-residual, CLAUDE.md convergence guard (a)).  The
solve-owned bar of 0 is MISSED on both.

**AND IT IS NOT A §20b (2) DEFECT — THE INTERVENTIONAL ARM SAYS SO.**
`--why-at` on HECA's worst staged mover (+2.68 m at 30.12612886558,
31.41825773893, `v13336[apron#511,building#547]`) names `pads` (7 rows,
Σ|dual| 112.54) and `pad_frontage_level` (1 row) as its binding rows and
a 15-hop chain to the 23R threshold pin whose dz is dominated by
`apron_preference +17.81`, `apron_edge_portion +3.85`, `no_step_pairs
+3.46` and `apron_within_shape +2.18` — the airside's OWN families —
against `pads +0.04` and `pad_frontage_level +0.84`.  So the third arm:
the SAME staged pair with EVERY pad generator dropped (`--drop-generator
pads --drop-generator pad_level --drop-generator pad_frontage_level`),
which is a problem with no pad row anywhere:

| HECA staged, OFF → ON | moved | worst | runway |
|---|---|---|---|
| all rows | 2,230 | 2.68 m | 2 / 0.020 m |
| **every pad generator dropped** | **1,544** | **2.00 m** | **0** |

**69 % of the movement survives the deletion of every pad row**, at the
same coordinate.  The pads' ROWS are 31 % of it; the rest is the pads'
PRESENCE — extra faces in the sheet, extra columns in one problem, and
the ground the pad occupies no longer carrying the zone/strip rows it
would otherwise carry.  §20b (1b) is doing its job (`conforming_rulings`
already refuses every pad ruling in stage 1 even where every column is
airside), stage 2 substitutes the airside as constants, and NO stage-2
substitution touches a shared weld vertex it should not.  There is no
defect at the substitution site, `solve/design*.py` is untouched, and
the remaining movement is not reachable by a row-level fix.

**(4) THE STAGED SOLVE ALONE CHANGES THE SHIPPED SURFACE, NAMED.**
OFF arm, the only variable `staged_solve`: HECA ADJUDICATED 19,076 →
**18,346** (−3.8 %), law-true −1,081, `pad_airside_weld` 8 → **18**;
LEMD ADJUDICATED 986 → **1,005** (+1.9 %), law-true +266,
`airside_no_step` 321 → **292**.

**(5) THE REMAINING BARS.**  Staged OFF → ON census: HECA ADJUDICATED
18,346 → 19,026 (+3.7 %), `pad_cluster_mismatch` **15 → 0** (MET),
`pad_airside_weld` 18 → 19 (+1, MISSED), `hairline_pair` 2,230 → 2,781;
LEMD 1,005 → 1,053 (+4.8 %), mismatch 0 → 1 (`unit:27#341/8`, r2's own
named survivor), weld 2 → 2 (MET).  THE ONE-VERTEX PROBE IS MET AND IS
THE ROUND'S BEST NUMBER: on the pads-ON staged arm, one 0.30 m ceiling at
30.1279552,31.403143 moves **0 of 32,575 vertices by more than 0.02 m**,
max 0.0167 m over the whole field, **nothing beyond 250 m**, the hard set
27 → 27 under the perturbation.

**SHIPS OFF: `pad_from_cluster = false`, `pad_airside_clip = false`,
`staged_solve = false`.**  16r (b) flips the three together only if every
bar holds; the solve-owned airside bar is missed at both airports and the
weld gains one row at HECA.  No LEMD airport-path build.  Suite **1,787
passed / 1 skipped / 1 xpassed**, 0 FAILED, after merging the peer's
§45 channel work (`782a50d6`; both census families kept, additively).

## RULINGS

## 2026-09-16v APP 1.0.343 BUILT (26721f38, engine 1.50.1790, main a5e6a968; bundled: `[channel]` present, `terrain_cover_min_m` present, solver qp, staged_solve false, bank OFF, pads OFF; engine binary Sep 16 11:02) — §45 the open channel ON (peer 16i), no building bores + LEMD's seven decks, the shoulder end cap, the pad clip's airside-region fix; §20b (3) WRITTEN (stage 1's population invariant to groundside geometry — the pad line's last lever; measurement first) → lane v2stagepop

WHAT THE OWNER READS IN 1.0.343 (beyond 1.0.342): LEMD decks 981/988
back (7 of 7); VMMC no tunnels near the field (two real hill tunnels
1.8 km+ out remain — 16d-1 open); OTHH one terminal car-park ramp gone
(a wall corridor returns); LGAV/KPHX/KDFW open channels (the peer's
read items); the shoulder band's end cap at every airport; the pad
clip's shipped-surface changes (LEMD ADJUDICATED −44 %, HECA +0.2 %,
HECA `within_shape` +479 / `mid_edge_step` 13 → 21 named). SPJC still
unbuildable until the owner's road-layer refresh.

## 2026-09-16t v2padclip r1+r2 MERGED (4be40fb4, fast-forward; suite ON MAIN 1780 passed, 0 FAILED): the arrangement clip no longer re-nodes airside and the airside REGION is pad-independent (the `classify/roles` `if` gone; LEMD apron faces 106 on both arms); the shipped OFF arm CHANGED as a defect fixed (r1 alone double-cut every pad: HECA ADJUDICATED 19,032 → 19,076 (+0.2 %), LEMD 1,749 → 986 (−44 %); named regressions HECA `within_shape` +479, `mid_edge_step` 13 → 21, `road_cross_section` +11; LEMD `taxi_box` +3); KEYS SHIP FALSE (`pad_from_cluster`, `pad_airside_clip`, `staged_solve`): under the staged solve + qp the runway bar is MET (LEMD 0, HECA 2 at 0.020 m) and the one-vertex probe is the campaign's best (0 of 32,575 moved, max 0.0167 m), but solve-owned airside VALUES still move (HECA 2,230 / 2.68 m, LEMD 485 / 0.36 m) and 69 % of that survives deleting EVERY pad row — the pads' PRESENCE in the sheet (faces, columns, ground no longer carrying zone/strip rows), not a row and not a §20b (2) substitution defect → §20b (3) to write: stage 1's population must be invariant to groundside geometry (airside is king) — measured first (r3: decompose the 1,544 by what the pad's presence removes); app 1.0.343 = v2channel (§45, peer 16i) + this, building now

Also measured: the staged solve ALONE changes the shipped surface (HECA
ADJUDICATED 19,076 → 18,346 −3.8 % but `pad_airside_weld` 8 → 18; LEMD
986 → 1,005) — named. `pad_cluster_mismatch` HECA 15 → 0; the untried
lever for the residual `renode_minted` (HECA 40/43, LEMD 12/32) is
`pad_airside_snap_max_m` 5.0. Refuted: retreating an unsnappable
crossing off the rim (takes the weld). Functions in 16r; plus
`classify/roles.classify` (the pad-union subtraction removed).

## 2026-09-16r v2padclip r1 (104c7b43) MEASURED, merge held for the shipped-arm identity check: the arrangement clip no longer re-nodes airside (`pad_airside_renode` deleted 0; the garage on `building45` at one level; HECA mismatch 15 → 0) — but the airside VALUE still moves with pads (HECA 6,031 / 3.09 m) because the design problem is solved JOINTLY; the interventional arm names §20b: with `staged_solve = true` the runway's movement is 3 / 0.020 m → RULED (§16g (10) (12) MEASURED AND AMENDED): staged solve ships ON under §20c, pads ON with it if the bars hold; r2

Lane @ 104c7b43 (base 7f80dc71); suite 1,711 / 0 FAILED; keys ship
FALSE. Functions: `planar/overlay.build_arrangement` (two passes),
`airside_union`, `build_rim`, `_node_coords`, `_drop_rim_midpoints`,
`_renode_counts`, `airside_clip(regions, law, air=, nodes=, rim=)`
un-gated + drops a pad wholly on airside; `geom/cluster_outline.
AirsideRim(nodes=, node_tol_m=)`; `pipeline/publication._renode_rows`
(absent key = NOT MEASURED, empty = MEASURED ZERO); `check_grade
_check_pad_airside_renode`; `pad_airside_arm --arm-a/--arm-b`;
`v2_solve_replay` captures carry the re-node reading. Refuted:
retreating an unsnappable crossing off the rim (takes the weld). Twins
re-founded: a building standing in an apron IS a hole in that apron
(`test_v2bank` pad 40 m; `test_constraints`; `test_v2padvert`). Census
OFF → ON: HECA ADJUDICATED 19,456 → 18,686, LEMD 2,121 → 1,004; worse
by > 5 % named (HECA `plane_gradient` 9 → 14, `strip_seam_tear` 28 →
33). NOT done: the `classify/roles.classify` `if` (the OFF arm's
airside region still pad-dependent: LEMD apron faces 180 vs 106); the
OFF-arm identity vs main (r2's first deliverable, before the merge).

## 2026-09-15ah v2padqp r2 MERGED OFF (b2294797 → 348f80a4): the airside movement ATTRIBUTED — ¾ of it is the ARRANGEMENT CLIP re-noding the airside vertex set (clip alone 4,474 / 1.39 m), not a pad row; the pad plate row pointed one-way improves the SHIPPED surface (HECA ADJUDICATED −4.1 %, LEMD −35 %); mismatch HECA 10 → 0 by the ref-area share; keys stay OFF — the clip is a spec question. OWNER (away): "no need to rebuild that app yet … complete the open lanes first"; the app killed and the road-layer refreshes run by the session on the owner's word

Lane @ b2294797; suite 1,639 passed, 0 FAILED. `--why-at` on HECA's
worst mover (+3.610 m at 30.11038632205,31.39574702991, apron+building):
ONE binding row — the pad's cap-0 plate (`pads cap 0.00 % × 8.7 m`,
dual 3.61), two-sided over an apron-owned vertex → pointed one-way
(§16g (10) (11) (a)); the next worst mover carries NO pad row; 5,600 of
5,868 moved airside vertices touch no pad. Third arm (clip alone, no
derived pads): 4,474 moved / 1.39 m, runway 17 / 0.100 m — the
arrangement clip deletes 1,082 solve-owned airside vertices and mints
235; 14as (i) made the airside REGION pad-independent, not its VERTEX
SET. Bar 1 MISSED (HECA 5,973 / 3.28 m; LEMD 1,651 / 2.36 m) and cannot
be met at a pad row. The direction fix ships (pads OFF): HECA
ADJUDICATED 26,608 → 25,521, `airside_no_step` 7,747 → 7,344, `taxi_box`
3,411 → 3,169, `within_shape` −726; `pad_airside_weld` 2 → 8 on that arm
(the pad now yields — the family's job). Welds OFF → ON 8 → 7 HECA
(MET), LEMD 2 → 3. Ref-area share: HECA mismatch 10 → 0 (shipped
fallback reads 15), LEMD 2 → 1. Census final: HECA 25,521 → 25,612,
LEMD 2,118 → 1,377; `strip_seam_tear` closed; `plane_gradient` 8 → 12
(derived pads' own planes). NEXT (spec, Fable): whether a pad may
re-node the airside at all — §16g (10) (12): the arrangement clip must
preserve the airside vertex set (the pad polygon is clipped BY the
airside cells, the airside cells are never re-cut by a pad). Owner
away: the app quit by the session (engine idle: 0 % CPU, no children,
workers exited), NO 1.0.341 build per the owner; `--refresh-data
osm_layers` per tile started on the owner's explicit word (VMMC/+22+113
first, then LEMD, HECA, KCLT, OTHH, CYXY), one task per tile.
15ah addendum: suite ON MAIN after the v2padqp r2 merge (348f80a4): 1639 passed, 1 skipped, 42 warnings in 75.63s (0:01:15). The first refresh chain (six tiles in one 600 s task) was stopped before it wrote anything; it left its own `osm_layers.lock` (pid 49618, dead) which the session removed — one refresh task per tile from here.

## 2026-09-15b v2qp MERGED OFF (d3864680): the design solver converges — HiGHS's QP refuted for the whole-airport problem, the damped proximal step ruled AS the §20c solver; the key flips ON in a follow-up (app 1.0.341)

Lane `v2qp` @ 682d1810, merged d3864680 (frames 7692adb3); suite on
the lane 1,565 passed twice as shipped (`solver = "fixed_point"`); the
suite ON MAIN reported below by FAILED lines. MEASURED (§20c MEASURED):
the shipped fixed point is NOT the minimum of its own objective — FISTA
from its own iterate with the lag and multipliers frozen drops F
193,499.24 → 190,618.15 (1.489 % above the minimum) and moves 703 / 4,437
CYXY columns (worst 0.52 m); the cause is the UNDAMPED active-set
subproblem minimiser (F = 7.6e8 against 1.9e5) whose ray line-search
collapses to the floor — `objective_stalled` on every solve, exactly
14bw. HiGHS's QP (both textbook forms) refuses on the nullspace limit
and runs 630 s untermininated at CYXY when raised; a proximally damped
subproblem on the same `_linear_solve` converges in 52 iterations /
1.2 s (the stall cost 3.2 s). The one-vertex HECA probe: fixed point
959 moved (953 beyond 500 m, worst 0.52 m); QP 0 moved, worst 4.3 mm,
hard set 18 → 18. §20b stage 1 SETTLES at HECA (0 / 174,500 hard, worst
0.0200 m). Hard rows CYXY 17→12 HECA 39→18 KCLT 29→19; census CYXY
427→379, HECA 26,634→26,607, KCLT 6,607→6,515; wall ≤ 1.31×; closing
HECA build rc 0 449 s, shared repo UNCHANGED. RULED (§20c RULED (1)–(5)):
the deviation is ACCEPTED — the tool, not the law, was wrong; the lag
and the hard-row penalties stay; the key FLIPS ON with the two twins
re-founded (the 0.6 mm taxidatum residual is under the 0.01 m
materiality; bar 0.25 m); 1.0.340 ships OFF for the LEMD tile, the flip
lands in 1.0.341 for the HECA read; the OTHH customer surface stays
fixed-point until the owner rebuilds and reads it. Lane resumed for the
flip.

## Tool: v2_solve_replay

| `Ortho4XP/tools/v2_solve_replay.py` | --why-vertex V [--why-relax FAMILY ...]`; `--why-hard [N] [--why-hard-stage 1]` on either a `--replay` arm or a `--why-from PKL`; `--why-from PKL --probe-site LAT,LON [--probe-drop M] [--probe-arm TERM=V ...]`) | You are iterating on the v2 SOLVE (a law table, a generator, the shape stage, the planar build) and want the runway bows / z − DEM / joints / yielded-rows figures per change WITHOUT paying for the load stage each time — the synthetic-first solve arm (CLAUDE.md BUILD ECONOMY; `docs/specs/auto-patch-v2/heca-sag-ablation/ablate_heca_pin.py` was the scratch pattern, promoted on its second use by lane v2chord, RULINGS 2026-09-08d). `--capture` runs load → **the PACK PARTITION + GROUPS** (`build.py:288-318`, owner RULINGS 2026-09-11j — folded in 2026-09-12u by lane `v2padceiling` after scout `v2unsettled` measured the trap: a capture without them carries an `Airport` with no `partition` and no `groups`, so the replay silently solves a DIFFERENT problem — no `foot_rows`, no `pad_relief` targets, no basin bodies, and the shipped LEMD hard set could not be reproduced at all; a capture predating it is now REFUSED BY NAME at replay, `capture_has_groups`) → classify → planar (which labels the SHAPES, owner RULINGS 2026-09-08k) → flat site → road profile → shape stage exactly as `pipeline/build.py` and pickles the airport, the classification, the planar map and the stage (**and THE CLUSTERS beside the partition and the groups** — lane ``v2padjoin`` 2026-09-14: a capture without ``Airport.clusters`` leaves §30 (4)'s cluster pad, its apron reach and §16g (10)'s derived pads INERT in every replay of it, so a pads-ON arm silently measures the pads-OFF law; a capture predating them has them DERIVED at replay off its own partition, named on stdout) (HECA 56 s; LEMD 232 s, of which 104 s partition); `--replay` resumes from the named stage under the CURRENT tree (constraints + joint filter + yield transform + ONE solve by default — 08k (4), no joint re-solve; `shapes` rebuilds the shapes over the captured map and re-runs the stage — for a change in `planar/shapes.py` or `[terrace]`; `planar` the whole map), and prints per two-threshold runway the crown-ridge BOW, the ridge minimum, z − DEM mean/min/max, the law-tier line, `yielded_rows` per family and the max apron grade PER SHAPE with the steepest rows per family (face, grade, span, lat/lon), the shapes (count, the largest by vertices), the joints (count, gap joints, max built step, the worst with their shape pair), the road steps, and per `--site` the vertices within `--site-radius` (z − DEM, roles, shape ids, the max |dz| over a short edge = a step). `--emit DIR` writes the arm's patch through the build's own emit half so `patch_proximity_diff.py` and `undulation.py` can read a same-frame divergence on a replay arm; `--verify` runs the v2 VERIFY CENSUS on the solved surface and prints the rows per family and the DEFECT families the app's driver gates on (lane v2smooth round 2, RULINGS 2026-09-08v — a weight sweep needs the defect count per arm without a 130 s build); `--design-weight TERM=W` overrides one `emit.toml [design]` weight for the arm (the measurement arm, never a default). `--drop-generator` also accepts the pseudo-generator **`eat_ramp_reach`** (lane `v2eatramp`, spec §36 (5)): the EAT ramp's trend WITHDRAWAL is a channel edit made before the solve, not a row, so it cannot be dropped by the row filter — `eat_anchor_rect` drops the pins and their reach together, `eat_ramp_reach` the withdrawal alone (the §36 (5) before-arm). Lane v2shapes (2026-09-08): HECA capture 56 s; one pass 144–150 s (the 08g three-pass law read 357 s). `--why-from PKL --why-hump RUNWAY S0 S1` (the `solve.why` bindings and chain trace on the highest ridge vertex above the chord, from a duals solve of the SAME LP — kept out of the timed arm) with `--why-relax FAMILY ...` (relax-one-family arms: the hump's dz after a full re-solve without the family — the INTERVENTIONAL holder read). `--why-hard [N]` lists EVERY VIOLATED HARD ROW of the solved surface — generator, ruling, demanded vs allowed metres, and per vertex the id, coefficient, z, DEM, lat/lon and roles — re-assembling the design problem with `solve.design.assemble` and applying design.py's own `2 / Σ|c|` row scaling, so every violation reads in the METRES `hard_tol_m` is stated in (promoted from scout `v2unsettled2`'s `hardrows.py` on its second use, spec §32 (4), RULINGS 2026-09-13ac: `HARD SET NOT SETTLED` names ONE truncated ruling, which cost 12u a scout re-deriving the population by hand and 13ac needed the row's VERTICES to see that main's worst row was a pair the zone projection had clamped independently).  **`--why-hard-stage 1`** reads §20b STAGE 1's OWN ASSEMBLY instead of the full problem's (`solve.design.stage_split`'s drop + fixed): the AIRSIDE hard set, in the rows and the metre scaling stage 1 enforced them under. The full read cannot answer "does the AIRSIDE solve settle" — the airside rows are a subset of 325k whose population and scaling the stage's own drop changes — and that is exactly the claim RULINGS 13y (B) / 13ab / 14as make (lane `v2settle`, which used it to split HECA's "42 unsettled rows" into 9 CONSTANT rows the solve can never move, 6 HELD runway rows at the projection's own bar, and 18 real ones).  The shipped surface is read either way: an airside vertex's z IS stage 1's, so the stage-1 read at the shipped z equals the read at stage 1's own surface (measured identical at HECA). **`--emit` IS THE BUILD'S WHOLE EMIT HALF SINCE 2026-09-13** (lane `v2zonebank`, §37 (3)): it ran `graded_surface` -> `write_patch` and SKIPPED `with_bank` / `with_terrain_edges`, so every `bank_foot` question asked of a replay arm read ZERO feet and looked like the defect under attribution — it now runs `pipeline/build.py:780-795` verbatim and prints the `BankReport` line. **`--bank-from SOLVED.pkl`** replays that emit half alone off a `--solved-out` pickle (KCLT 2.5 s against the 160 s `--replay`), with `--emit DIR` and/or **`--bank-walk`**: §37 (3)'s per-station ADJACENT-GROUND ZONE-2 WALK — per `adjacent_ground:*:zone2` face ring, `|z_ring - DEM(foot)|` at every station, the stations at or over `bank_materiality_m`, whether the foot point stands outside the design coverage, whether it falls in the terrain-edge no-bank region or the water cut, and whether a `bank_foot` stands within that station's OWN 1:3 reach (never the airport-wide `bank_max_width_m`, which calls a foot 200 m away near); then, off `emit/bank.with_bank`'s `station_probe` / `region_probe` attribution hooks, the banked-region station the load-bearing verdict was actually taken on and where an unbanked station stands (inside the banked region? inside a coverage HOLE?). It prices no law and counts no defects — defect counts come from `harness/census.py`. Measured basis (KCLT, base `ce203b29`, `cap/KCLT.pkl`): 233 zone2 rings / 5,647 stations, 542 at or over the 1.65 m materiality, 220 with their foot outside the coverage, **110 with no foot at all** — 110 of them inside the banked region and 109 inside a coverage hole, which is how RULINGS 2026-09-13bu item 5 was attributed to `_foot_piece`'s solid exterior disc; after the fix 8. **A CAPTURE PREDATING A TARGET CHANNEL STILL REPLAYS, AND SAYS SO** (2026-09-13, lane `v2roadcontact`): a `PlanarMap` field added since the pickle was written is simply ABSENT on the unpickled instance, so the first `dataclasses.replace` raised `AttributeError` and a REGISTERED FRAME another lane shares became unreplayable for a channel its own stage never produced; `--replay` now backfills each missing field at the dataclass's OWN default and NAMES it on stdout (the publisher derives the channel in the replay anyway). This is NOT a relaxation of the 12u groups refusal, which stands: that one is a capture solving a DIFFERENT problem, this one is a channel the capture never had. Twins: `tests/auto_patch_v2/test_v2padceiling.py` (the capture calls every pre-solve stage `pipeline/build.build` calls, read off both sources; the refusal predicate).  **`--probe-site LAT,LON` IS THE STABILITY PROBE** (lane `v2qp`, spec §20c, promoted from lane `v2settle` r2's `scratchpad/v2settle/probe3.py`/`probe4.py` on its second use): off a `--solved-out` pickle, one extra `Band` ceiling `--probe-drop` (default 0.30) metres under the ARM's OWN base surface at the vertex nearest the point, re-solved, and the moved set (> 0.02 m) binned by distance from it — 0-40 / 40-100 / 100-250 / 250-500 / beyond, with the worst beyond 250 m, each arm's hard set and its exit line.  `--probe-arm TERM=V` repeated makes it a MATCHED PAIR of `[design]` arms on ONE problem (`--probe-arm solver=fixed_point --probe-arm solver=qp` is §20c's own bar); with none it probes the shipped law alone.  This is the instrument RULINGS 2026-09-14bw's headline was taken on (HECA: 959 vertices moved by one 0.30 m row, 953 beyond 500 m, ZERO within 100 m).  `--design-weight TERM=V` also takes a NON-NUMERIC value now (§20c's `solver=qp`); a value that does not parse as a float is passed through as the string.    **`--placement KEY=V` IS THE CAPTURE-TIME LAW ARM** (lane `v2padqp`, spec §16g (10) (11)): the §16g (10) pad keys (`pad_from_cluster`, `pad_airside_clip`) are read in `classify/evidence._pads` and `planar/overlay` — UPSTREAM of the capture — so `--design-weight` (a `[design]` override applied at REPLAY) cannot arm them and a pads-ON replay of a pads-OFF capture silently measures the pads-OFF law; a matched OFF/ON pair is therefore TWO CAPTURES of one tree, never two edits of the shipped toml (the value is coerced to the key's own type, an unknown key refuses by name, and the arm is recorded in the pickle).  `--capture` also arms `harness/build_airport.arm_shared_repo_protection` — the ONE arming composition — and prints `[guard] shared repo UNCHANGED`.  **`--rule SECTION.KEY=V` IS THE CAPTURE-TIME CLASSIFY ARM** (lane `v2shoulderband`, spec §40 (5)): the same thing for `classify/rules.toml` that `--placement` is for `[placement]` — a CLASSIFY key is read upstream of the capture (the capture HOLDS the classification, so `--from planar` cannot see a classify change at all), which makes a matched pair on one TWO CAPTURES; doing that by editing the shipped toml between the arms is the defect RULINGS 2026-09-15az records (disarming a head by prefix also deleted `foot_row_rulings` and silently re-priced every foot row), so the arm is ONE COMMAND-LINE VARIABLE on one unedited tree instead. `SECTION.KEY=VALUE`, coerced to the key's own type, an unknown section or key refuses BY NAME, and the arm is printed on stdout — e.g. `--rule corridor.runway_shoulder_band=false`.  **`--reclassify PKL` IS THE DRY §40 BAND READ** (lane `v2shoulderband` r2, promoted on its SECOND use per RULINGS `7e90032` — r1 hand-rolled it in a scratchpad for the HECA control and r2 needed it at five airports): a CLASSIFY key cannot be armed at replay, but the capture also carries the `Airport` the classifier ran on, so the CLASSIFY STAGE ALONE is re-run over it on the CURRENT tree with `--rule` as the only variable — seconds against a capture's minutes (LEMD 74-79 s). It prints §40 (5)'s own table: the `runway_shoulder` population (cells, m², each named with its host runway and its worst lateral offset), the runway BODY beside it, what the remainder earned BY ROLE, the worst lateral offset of a shoulder vertex off its own runway's apt.dat axis and how many stand beyond the band (§40 (5) (1)'s own bar, "→ 0"), and the classifier's own `shoulder_band_*` stats; `--json` dumps it with the arm recorded, so no reading is frame-less. It is a DRY read and says so — no planar build, no solve, no emit — so it PRICES NO LAW AND COUNTS NO DEFECTS (defect counts come from `harness/census.py` and nowhere else) and it cannot answer anything downstream of classify: a `runway_step` row or a census family needs a built patch. The axis and the half width are the derivation's own (`classify/roles.shoulder_band`), imported and never re-spelled. Control: re-read on the registered `LEMD capture base e856ce64` it reproduces r1's ON arm EXACTLY (271,086 m² / 19 cells / remainder 273,949 m² in 28 faces). Twin: `tests/auto_patch_v2/test_runway_shoulder.py` (the table IS the classifier's verdict on both arms, band + remainder PARTITION the cell, the arm is recorded).  **A CAPTURE CARRIES THE ARRANGEMENT'S RE-NODE READING** (lane `v2padclip`, spec §16g (10) (12) (2)): `pipeline/publication` publishes the sidecar's `pad_airside_renode` out of a module global `planar/overlay.PAD_AIRSIDE` that only a BUILD fills, so every replay arm published an EMPTY list and read a perfect family — the silent-degradation class. `--capture` now pickles that dict and `--replay` restores it and prints `pad/airside re-node from the capture: deleted N minted M`; a capture written before 2026-09-16 carries none and the sidecar key is then OMITTED, which every reader reads as NOT MEASURED rather than zero.   Twin: `tests/auto_patch_v2/test_v2qp.py` (the probe as a fixture pair) — the rest of the replay is an instrument over `pipeline/build.py`'s own stages, which the pipeline twins cover. |

## Tool: pad_airside_arm

| `Ortho4XP/tools/pad_airside_arm.py` | **THE PAD/AIRSIDE INVARIANCE ARM** (RULINGS 2026-09-14as (i), lane `v2padvert`; promoted from that lane's scratchpad on its eighth use per RULINGS `7e90032`). `V2PADVERT_ENGINE=<engine tree> venv/bin/python tools/pad_airside_arm.py ICAO OUT.json` — ONE load, then classify+planar TWICE (`[placement] pad_from_cluster` OFF then ON) and a diff of §20b stage 1's OWN airside vertex population (`solve/design_roles.airside_stage_vertices`, never a hand list) and the apron face list between the arms. It answers "does deriving the pads change the AIRSIDE PROBLEM" — 14as (i)'s prerequisite — in ~3 min at HECA against a ~450 s build, and it is a READER: no solve, no emit, nothing written but its own JSON. The shared-repo write guard and the lane-local cache redirects come from `harness/build_airport.arm_shared_repo_protection` (the ONE arming composition) and every run prints `[guard] shared repo UNCHANGED`. It also prints `classify/evidence.PAD_AIRSIDE` (what the airside clip and the rim snap did, with every refusal by reason) and, per NEW airside vertex, its distance to the other arm's nearest airside VERTEX and to its airside BOUNDARY — the two readings that separate a clip crossing point from an identity-grid artefact. MEASURED at HECA, gone/new: main 280/88; the clip alone 59/79; clip + vertex snap 28/35; clip + snap + the never-delete exemption 41/151. Twin: `tests/auto_patch_v2/test_v2padvert.py`. **`--arm-a KEY=V[,KEY=V]` / `--arm-b`** (lane `v2padclip`, spec §16g (10) (12)) name each arm's `[placement]` keys explicitly instead of the historical `pad_from_cluster` OFF/ON pair — the same arm form `v2_solve_replay --placement` speaks, coerced to the key's own type, an unknown key refused BY NAME, and the arm printed per side; it is what lets the CLIP be armed alone (`--arm-a pad_from_cluster=false,pad_airside_clip=false --arm-b pad_from_cluster=false,pad_airside_clip=true`), which is the attribution RULINGS 2026-09-15ah rests on. The report now also carries the arrangement's own `renode_deleted` / `renode_minted` counters (§16g (10) (12) (2)) beside the gone/new diff. MEASURED at HECA with the clip alone: 1,008 gone / 283 new before §16g (10) (12), **0 deleted / 40 minted** after it. |

## Tool: pad_span_census

| `Ortho4XP/tools/pad_span_census.py` | The question is DOES THIS UNIT'S OWN DATUM FIT ITS BODIES' PADS — *how far apart do the emitted `building` pads one FOOTPRINT UNIT stands on actually stand?* — the single number owner RULINGS 2026-09-14c item 1 is accepted or refused on (spec `object-placement-spec.md` §16g (1)/(7)). No other instrument asks it: `harness/census.py` prices PAIRS OF VALUES, so an object seated 23.70 m above its own pad breaks no grade law and reports ZERO rows; `obj8_split_report.py` prints a body's anchor and its own ground but never asks whether the bodies sharing ONE unit's datum stand on pads that disagree; `role_overlap_read.py` is an AREA sweep and `role_edge_census.py` a boundary-length one. This is the unit-vs-pad reading: per unit, the `building` pads its bodies' FEET fall inside, how many bodies it holds, and the SPAN of those pads' planes, largest first. **It measures no law and counts no defects** — the pads are the emitted design surface's own `building` faces at `median(z)` over the ring, which is the plane `footprint_unit` reads through `anchor_rule.pad_plurality`, and the body→part join is the PART ID, never a proximity match (memory `canonical-identity-join`). `--over` (default 1.0 m) is the listing floor 14g stated its bar in, not a threshold with any standing. It takes either `o4_v2_placement_<ICAO>.json` or an `obj8_split_report --json` dump — both carry the same `splits` body records. Measured basis (scout `v2heca331` on the owner's 1.0.331 HECA): 17 units whose pads span > 1 m over 1,363 bodies, `fu:38:20` alone 978 bodies on 136 pads spanning 34.8 m — the unit chained on PART BOXES, and its DECK member then gave 96.20 to 1,509 bodies. Promoted 2026-09-14 from that scout's scratchpad `padspan.py` on its SECOND use (RULINGS `7e90032`, promote-on-reuse) — the 14g attribution, then lane `v2connector` round 3's before/after. Several patches are reported separately; quote it on identical options. Twin: `tests/test_pad_span_census.py` (the span IS the unit's own pads, a non-`building` face is not a pad, a unit on one pad is not a row, a body with no `unit_of` is not counted, the floor both ways, the CLI's JSON IS the library result, and this index row). |

## Tool: check_grade

| `Ortho4XP/tools/check_grade.py` | You want the grade validator's CLI on one patch, or its library from code. The CLI is a thin front end over the same law reader the census uses. A run with no sidecar is CONTEXT-FREE and overcounts — it is not a defect count. It also prints **THE COCKPIT BLOCK FIRST** (owner RULINGS 2026-09-12x/12y; §31 (6)) — the same `cockpit_block` / `cockpit_block_lines` the harness census and the pytest fixtures call, over the SAME run's `family_out` (the checks' own output is buffered and replayed under the block, never run twice). A `strip_seam_tear` row carries the PAIR MIDPOINT as its lat/lon (spec §32 (3), RULINGS 2026-09-12ag): it used to carry none, and `run_checks` filled it with the offending way's RING CENTROID — at LEMD that sent the cockpit block's first CRITICAL VISUAL find 220 m from the 8.25 m tear. Twinned both sides (`tests/auto_patch_v2/test_v2zoneclamp.py`), the engine's own `verify/strips.strip_seam_tear` alongside. The block's "in view by approach" test is the ONE approach corridor of `auto_patch_v2.law.approach_corridor` (RULINGS 2026-09-12al; twins `tests/auto_patch_v2/test_v2approachcorridor.py`), never a radius around a runway vertex. **`pad_airside_renode`** (spec §16g (10) (12) (2), Fable 2026-09-16 / RULINGS 2026-09-16b, lane `v2padclip`) is the PRESENCE family the airside vertex set had none of: one row per airside CELL vertex the PAD STAGE minted or deleted, read from the sidecar's `pad_airside_renode` (`[lat, lon, "minted"|"deleted"]`, published by `planar/overlay.build_arrangement` comparing its own pass A — the airside noded before any pad exists — with its pass B). Sidecar-declared like `eat_ceiling` / `seam_pins`, because the only place both node sets exist is inside the build's own arrangement; an ABSENT key is NOT MEASURED and an EMPTY list is MEASURED ZERO. No other family sees it: an emitted surface carrying an extra airside vertex breaks no grade law, which is why the clip alone deleting 1,082 solve-owned airside vertices and minting 235 at HECA (RULINGS 2026-09-15ah) had to be attributed with a lane arm. Class `keepout` — one node is the whole defect and there is no magnitude to threshold. Twins: `tests/auto_patch_v2/test_v2padvert.py` (both directions, the densifier filter, the publication's absent-vs-empty contract). **`adjacent_ground_step`** (spec §34 (4), lane `v2rampwalk` 2026-09-13) is the WITHIN-FACE welded step on a v2 `adjacent_ground:*` face — the reading no family had: `graded_strip` carries no within-shape cap, `adjacent_ground_tear` fires only under a 1 m edge and `strip_seam_tear` is the CROSS-shape twin, so a band holding its designed level over a mapped road's own ground (LEMD `zone2#2`, 1.73 m over 1.5 m at road −6289) was priced by nothing. Its floor is the cockpit's own `visual_m` AND `cliff_grade` in one step: without the cliff term it counts the lawful hillside drape (measured CYXY 296 rows). Lockstep both sides — `auto_patch_v2.verify.strips.adjacent_ground_step` reads it in the engine; twins `tests/auto_patch_v2/test_v2rampwalk.py` and the v1/v2 census parity test. **`ramp_in_road`** (spec §34 (10), owner RULINGS 2026-09-14bb/14bc/14bd, lane `v2othhramp`) is the CRITICAL presence family the road margin needed: every ramp arriving at a road ends at the road's TRUE edge — the centreline offset by the road's own half-width toward the ramp, ONE derivation `planar/wall_corridor_ramps.road_true_edge` read by every ramp emitter — so a RAMP vertex standing INSIDE a road ribbon is a lane of carriageway cut away, whatever its elevation. No other family sees it: a ramp welded flat into the road it ate breaks no grade law and prices zero rows. A vertex within the census's own weld tolerance of the ribbon's edge is ON the edge, which is what the law asks for. It reads 0 at OTHH before and after — the family is the GUARD on that derivation and never a defect count. Twins: `tests/test_harness.py` §34 (10) (both directions, the weld line both ways, the register and the cockpit class, and the ramp-role set read from the law's own structure roles). **`ramp_in_strip`** (spec §34 (5) (b), Fable 2026-09-15 / RULINGS 2026-09-15h, owner 15e item 7, lane `v2lemdstruct2`) is its AIRSIDE sibling: the covered extent of an underpass beneath a taxiway or runway spans the pavement AND its graded strip, so a RAMP vertex standing inside that strip is a trench in the ground an aircraft leaving the pavement runs out onto — LEMD 40.4611623,-3.5444804, where a code-E strip is 19.0 m and the trench face stood at 15.5 m under a 5.42 m unbanked drop, the airport's worst CRITICAL VISUAL row. The strip region is ONE derivation with `planar/zones.zone_regions` and `planar/structure_underpass.strip_half_width_m` (the zone-2 half width for the cell's class, the zone-1 LIP where the class declares none), read from the LAW with a literal no-engine fallback the twin asserts against. TWO READINGS MEASURED, NOT CHOSEN: the face's sidecar HOLES are applied and the pavement SOLID is subtracted, so the region is the BAND — read ring-blind and disc-shaped the first arm reported 52 LEMD rows, every one inside `cross_connector:pav61`'s own 144,429 m2 void and up to 220 m from any kerb, and `de_m` can now never exceed the class's own half width. Twins: `tests/test_harness.py` §34 (5) (b) (both directions, the class's own half width against the zone law and the planar derivation, the taxiway-loop void, the weld line both ways, the register and the cockpit class). **THE RUNWAY SHOULDER'S OWN CAP** (spec §40 (2) as amended, owner RULINGS 2026-09-13dd, lane `v2roles`): a within-shape pair BOTH of whose nodes lie beyond their runway's own half width is priced at `shoulder_transverse_max` (2.5 %, ICAO Annex 14 §3.2.4), not the runway's 1.5 % — a §40 (1) SHOULDER keeps the runway's DATUM, not its cross-fall. The line is the SOLVE's and is read, never re-derived: the sidecar's `runway_axes` (`[ref, lat_a, lon_a, lat_b, lon_b, half_m]` off the apt.dat ends and width) and `shoulder_transverse_max`, through `shoulder_nids` / `_shoulder_cap`. Fitting the width to the runway RINGS instead would read a shoulder as part of the runway and never find its own line. A patch with no key reads exactly as before. One reading with the generator and the v2 verify (`auto_patch_v2.law.tables.runway_transverse_cap`); twins `tests/auto_patch_v2/test_runway_shoulder.py`. |

## Tool: census

| `Ortho4XP/tools/harness/census.py` | You need DEFECT COUNTS from an emitted patch. Every law family always (the register, never a hand list), law-true frame from the patch's own sidecar, airside/groundside/mixed split, worst-N rows, class table, sidecar evidence, JSON + table, A/B across patches. **The only numbers that may be quoted as defect counts.** `--zone-split` additionally buckets the within-shape rows by FAN-RAMP ZONE membership (on a declared ramp piece / inside a zone / crossing one / unrelated, plus the rows already steeper than the zone cap) — reach for it when a grade law grants relief on declared ground and you need to know whether the relief is where the defects are. It is a flag and not its own tool because it needs the census's law-true frame; a private copy of that frame is the census-wrapper defect above. `--magnitude-bands [EDGES]` buckets EVERY law-true row by severity (|de| / step height; default edges `0.01,0.1,1,10` m, or your own ascending list) with the airside/groundside/mixed and adjudicated/version-deferred splits per band — reach for it when the question is which KIND of population a total is, not how big it is (the frame of record is stated in these terms: "0.1-1 m 13,711 = 45.1 %, 1-10 m 11,143 = 36.7 %, 82 % is in-band airside solver residual"). The bands PARTITION the census's own rows and the band below the first edge is the materiality floor's own. Promoted 2026-08-06 from the two lane copies that hand-rolled it (c6attr, c6tip). `--frame own\|base` selects the AXIS FRAME: `own` (default) is the patch's own sidecar and the only frame whose numbers are defect counts; `base` re-reads the SAME patch bytes with the SERVICE axes removed from its sidecar — the axis population a pre-road-feed sidecar carried — which is what splits "the class moved because the surface moved" from "…because the axis frame moved" (cycle 9/10: HECA 10 000 m read airside 4,610 own-frame and 4,474 base-frame, and the whole gap was ONE instrument defect). A base-frame number is a FRAME claim, never a defect count; the frame is stamped into every report either way (`axis_frame`). Added 2026-08-07 (cycle 10) in place of the hand-built filtered sidecars the cycle-10 probe made and threw away. `--rows-json OUT.json` additionally ITEMISES every law-true row — family, role pair, side, magnitude, grade/cap, site in layout-local metres, lat/lon, way ids — which is what turns a class table into an attribution: a net class delta hides equal churn by construction (a class that gains 200 rows at one site and loses 18 at another reads as "+182"), and only the rows say WHICH rows and WHERE. It is the census's own `all_rows`, the same population every count in the report is taken from, so the dump and the counts beside it can never disagree — `tests/test_harness.py` asserts the dump's class tally IS the report's class table, its side split IS the report's, and the worst-N table is its prefix. With several patches you get one dump per patch (a single file would silently keep the last). Added 2026-08-07 (cycle 10) for the road-pair receiver-only round's +182 decomposition. `--sites` clusters those same rows into DEFECT SITES and reports the other headline: how many DISTINCT defects a patch carries (law-true and adjudicated), ROWS PER SITE — the AMPLIFICATION FACTOR — per-site worst |de| / step and worst grade excess, the families, role pairs and shape ids each site spans, its bbox + centroid lat/lon, and a SIM-VISIBILITY flag. Reach for it whenever a row total is about to be quoted as a defect count to a human: row counts AMPLIFY and site counts do not — one over-cap region on one apron mints hundreds of edge-granularity rows (HECA's way -12407 alone carries ~800; the road-feed round's 180 threshold-flip sites live on 19 shapes, 72 % of them on four aprons), so "thousands of defects" is a count of PAIRS THE LAW PRICED and differs from the number of things wrong with the surface by whatever the amplification happens to be on that patch. THE CLUSTERING RULE, printed with every table so a site count is never read without it: two rows join one site iff SAME LAW FAMILY and (shared way id OR shared canonical node), where a canonical node is the census's own weld tolerance (`LAW_TRUE_KNOBS['proximity_m']` = `check_grade.SHARED_VERTEX_TOL_M`, 0.5 m) applied to the rows' endpoints in layout-local metres — the law's own "these two vertices are one node" predicate, never a proximity semantic invented for a report; sites are the connected components (union-find), and no magnitude, role or geometry test takes part. `--site-visibility M` moves the visibility threshold (default 0.05 m of relief = silhouette-visible candidate); it is a REPORTING threshold and an assumption — nothing has measured it in the sim — never a law, and the law still adjudicates every row regardless. `--sites-json OUT.json` dumps every site with its full membership as row indices into the census's own magnitude-sorted order, so it joins a `--rows-json` dump by position. The sites PARTITION the census's own population — `census_one` REFUSES if they do not, and `tests/test_harness.py` §9 carries the known-answer twin (two hand-built sites, one joined by way id and one by weld, asserting count, membership, amplification and both visibility flags) plus the union-equals-`all_rows` lockstep. Added 2026-08-07 (cycle 10) for the owner's "why does the battery still read thousands of defects" question. **THE HEADLINE the section reports is ACTIONABLE SITES** — the MATERIALITY FLOOR (owner RULINGS 2026-08-07, "we don't need to be grading to less than 0.5m") adjudicated per site, since a site is the unit that sentence is about: 40 one-centimetre rows on one apron are one place owing 0.4 m of grading, not 40 defects. A site is actionable when its ADJUDICATED rows accumulate ≥ **0.5 m** of unlawful excess, OR one of them is a single step ≥ **0.15 m** or sits at ≥ **2× its own cap** (the SHARP GUARD — "we don't want any sharp bumps", the half a bare accumulation floor throws away), OR it touches the **RUNWAY FAMILY** (`runway` / `runway_crossing`), which is never floored because reg-derived precision governs there. Every constant is a named knob in `check_grade` (`MATERIALITY_FLOOR_M`, `MATERIALITY_SHARP_STEP_M`, `MATERIALITY_SHARP_GRADE_CAP_MULTIPLE`, `MATERIALITY_RUNWAY_FAMILY_ROLES`) citing the ruling, and all of them ride in every report beside the counts — the floor is PROVISIONAL and two site tables taken at two floors are not comparable. ACCUMULATION is `check_grade.row_excess_m` summed over the site's adjudicated rows only (a version-deferred or out-of-scope row is not a defect and may not fund one): the EXCESS, not the magnitude — a 3.2 m rise over 200 m of 1.5 %-capped taxiway is a 3.2 m magnitude and a 0.2 m excess. A family that prices a CAP rather than metres (`MATERIALITY_UNMEASURED_FAMILIES`, today `lateral_contiguity`, whose `de_m` is a bare grade difference over no span) funds nothing AND keeps its site actionable — a floor may only relax what it can measure. A site the floor takes out is REPORTED under the **`sub_floor`** label with its rows and worst |de| (counted-never-dropped, the `VERSION_DEFERRED_FAMILIES` / `disconnected_ring` convention), and actionable + sub-floor PARTITIONS the adjudicated sites — `census_one` REFUSES if it does not. Twins: `tests/test_harness.py` §10 (both sides of every constant, each guard half proven to fire ALONE, the runway exemption, the label locked to its register, the production refusal). Alongside it, ROLE-LESS FEATURE WAYS SIDE WITH THEIR HOST (lead ruling 2026-08-07): an `o4_feature` way with no `role` tag — `shape_interior_ring` / `gap_interior_ring` / `gap_drainage_spine` / `crown_spine`, 232 of them at HECA — used to fall through to the caller's default 1.5 % cap and to AIRSIDE whatever its host was; `check_grade.resolve_feature_hosts` (shared-node majority, ties on `layout.AUTHORITY_RANK`) and the drainage law's own parent selection now supply the role and side for REPORTING ONLY — the `role` tag is law input and is never written — and a row whose host's vertex set COVERS it is adjudicated `role_less_host_duplicate` (one geometry, one row set), reported under its own heading and never dropped. §10b twins. `--no-cache` / `--clear-cache` govern the CENSUS CACHE: the full report is memoised under `Ortho4XP/tmp/census_cache` (lane-local, gitignored, `$O4_CENSUS_CACHE_DIR`, REFUSED inside the shared data repo, and off inside pytest unless the root is named) keyed by the patch BODY sha (`build_airport.body_sha256`, the `tail -n +3` the frozen MANIFESTs speak) AND the whole-file sha (the census PRINTS the provenance stamp the body hash excludes), the sidecar BYTES (never an enumeration of its law keys — that is the wrapper defect), the run ledger's own code-tree hash (`run_with_ledger.code_tree_hash`, so a `check_grade.py` edit misses), `LAW_TRUE_KNOBS`, the `O4_*` environment and the option frame. A hit re-prints the stored report and re-writes the stored `--json` / `--rows-json` / `--sites-json` bytes, so it is the fresh output plus exactly ONE line — the `[CENSUS CACHE HIT] …` marker, first, immediately before the `=== CENSUS …` header, printed even under `--quiet`; a miss prints nothing. No number, family or law changes: memoisation, not measurement. Twin: `tests/test_census_cache.py`. The census also prints THE BUILD'S OWN AIRSIDE-SCOPED CERTIFICATE beside its counts (air7, RULINGS 2026-09-01l/r): the solve's law-graph verdict on the zero-airside beta bar, read verbatim from the sidecar's `airside_certificate` EVIDENCE key (readings per certificate site + the last-exit verdict; row-side partition, check_grade's quantization allowance imported) — a DIFFERENT instrument over a DIFFERENT population (law edges at exit vs emitted node pairs): agreement is corroboration, disagreement is a finding, and neither replaces the other. Twins: `tests/test_solve_certificate_instrument.py` TASK 6. **THE COCKPIT BLOCK IS PRINTED FIRST** (owner RULINGS 2026-09-12x/12y; `design-surface-spec.md` §31 (6), lane `v2cockpit`): before any other line the census classifies its OWN rows into CRITICAL MOTION (a `step`-class family over `[cockpit] motion_step_m` 0.05 m BETWEEN WELDED NEIGHBOURS — ends no farther apart than `emit.instrument.step_contact_tol_m`, the law's own weld spacing — where BOTH roles are ROLLED-ON — the runway family, the taxi family and the apron, derived from `precedence.toml`, never a literal list — plus the `grade_break` families the runway/taxi rate laws forbid, which carry no span test because a curve is long by definition), CRITICAL VISUAL (a WELDED `step`-class row over `visual_m` 0.5 m inside the airport boundary or within `approach_km` 5 km of a runway axis) and REPORT (everything else: every slope excess, every keep-out row, everything under a threshold, and everything beyond the view — §31 (4), "centimetres are not a goal"), each with its count, worst magnitude and worst COORDINATE. It is a CLASSIFICATION and never a measurement: no row is created, dropped or re-priced, and `cockpit_block` REFUSES if its three buckets do not add up to the population handed in. **THE SPAN RULE** (owner RULINGS 2026-09-12ad, round 2): a step-family row read SPANNED — ends farther apart than the weld spacing — is a SLOPE, not a discontinuity: it is grade, judged by its own cap, and is REPORT.  Round 1 classed a 2.69 m rise over 81 m of LEMD taxiway as critical motion and the block read 452; every one of those rows was spanned and LEMD now reads 0.  The REPORT line names what the rule moved — how many spanned rows would be over the motion threshold and how many over the visual one if they were welded — so the count is never folded into an anonymous total.  **THE CLIFF ESCAPE** (owner RULINGS 2026-09-12af, round 3) bounds it: a spanned row whose implied grade `|dz| / span` exceeds `[cockpit] cliff_grade` is a CUT or a RISE, not ground, and is judged as though it were welded, under its own reason `cliff` (on rolled-on pavement CRITICAL MOTION — no aircraft rolls a 1:3).  LEMD's `strip_seam_tear`, 8.27 m over 3.01 m = 275 %, is the row that made the rule.  The escape restores the BUCKET, never the threshold: a 0.4 m cliff is still under `visual_m` and still invisible.  `cliff_grade` holds a DOTTED LAW PATH (`emit.design.bank_slope`), never a number: the design surface's own 1:3 bank is already the line between "ground a pilot reads" and a wall, and `tables.cliff_grade` resolves it — change the bank and the cliff line follows, with no second copy to drift.  The loader refuses a path that does not name a grade in (0, 1] over the motion threshold.  **ROUND 4** (owner RULINGS 2026-09-12aj) repaired three READER defects the block's own output exposed, all in `check_grade.py`: the three RATE/ARC readers (`strip_arc`, `raoa`, `airside_no_step`'s §1.2 half) built rows with NO lat/lon, so `run_checks`'s fallback stamped each with the CENTROID OF ITS RING — 36 rows of LEMD apron `pav12` printed one coordinate 560 m from the wall they had found, and a whole round of attribution went to the wrong place; every rate row now carries its own pair midpoint (`_rate_row_site`, off a projection that gained an `inverse`). A rate row's `distance_m` published the HALF span `0.5*(dp+dn)` while its `de_m` spans `dp+dn`, so every implied grade read 2x (LEMD's five apron rows printed 0.37-0.46 and are really 0.20-0.23); it is now the full separation, and the allowance keeps the half span because that is the rate law's own averaging term. And the CLIFF ESCAPE now reaches EVERY family, not only `step` ones — LEMD's two sharpest readings of the same wall, a `within_shape` 81 % and a `cross_shape` 240 %, are class `grade` and could not be cliffs at all — while `row_roles` returns THE FACES ON EACH SIDE of the pair rather than the ring it was walked on: a within-shape pair has one ring for both ways, so the pad rim standing over the apron read `building|building` and the rolled-on test called it landside. `run_checks` indexes every node to the SENIOR face carrying it (`precedence.toml` authority order, an identity join on emitted coordinates at millimetre quantisation — never a proximity match) and stamps `role_a`/`role_b`; `row_roles` prefers them. A patch with no `boundary` role way (v2 emits none today) says so and the approach corridor alone decides view. IN VIEW BY APPROACH IS **THE APPROACH CORRIDOR** (owner RULINGS 2026-09-12al, §31 (2)): per runway END, `[cockpit] approach_km` beyond the threshold along the extended centreline and `approach_half_width_m` to each side, derived ONCE in `src/auto_patch_v2/law/approach_corridor.py` and read by the engine's mouth gate (`planar/structure_approach.FieldRegion`, §29 (1)) through the same class — the harness takes its axes from the emitted runway rings, the engine from the apt.dat thresholds. The first reading, "within `approach_km` of a runway axis", admitted the whole airport (at LEMD 4,318 of 4,408 rows, at HECA 8,122 of 37,364 — the corridor leaves 90 and 29,242 of them respectively behind) and is DELETED, not gated. Every family's class lives in `law/families.toml` (`cockpit = step|grade_break|grade|keepout`, REQUIRED — a new family without one does not load) and the four numbers in `law/emit.toml [cockpit]`. Twins: `tests/test_harness.py` §7. **§38 THE TILE SEAM (owner RULINGS 2026-09-13ah / 13am / 13an; lane `v2seampin`)** adds the two families the census had no instrument for. `seam_residual` prices every tile-seam band-edge vertex against ITS OWN tile's baked DEM sample — the value the solve PINNED, published per pin in the sidecar as `seam_pins` = `[lat, lon, dem_z]` (all of them since 13ah; the M3a sidecar published only the subset a soft preference happened to honour). Class `step`, so the cockpit rule gives it CRITICAL MOTION on the rolled-on roles and VISUAL elsewhere with no second threshold. It is the reader the SPLP berm needed: 106 rows, max 3.433 m, 31 of them CRITICAL MOTION on `runway|runway` (worst 0.629 m) — while `strip_seam_tear` read 0 over the same 3 m ridge. `bank_across_seam` prices any `bank_foot` node inside the band (`seam_half_width_m`, also published), class `keepout`: one node is the whole defect, because 13an measured a chain 0.0237 m off the meridian that Triangle4XP split 16,298 times against the unsplittable tile border. The bank foot is ROLE-LESS, so this family reads the `feature_out` channel of `_parse_osm`, not `ways` — a reader that walked `ways` prices nothing. Both are sidecar-declared like `eat_ceiling`: a patch with no key (v1's output, or a v2 patch predating §38) reports nothing and reads exactly as before. This is where the lane's seam-vertex/DEM probe was PROMOTED to (RULINGS `7e90032` second-use rule) — there is no separate script. Twins: `tests/test_harness.py` §38 (both directions of both families, at SPLP's own worst numbers, plus the cockpit classes read out of `families.toml`). |

| `Ortho4XP/tools/census_matrix.py` | You have MANY census JSONs — a multi-airport, multi-world round's arms — and the question is "did any cell's AIRSIDE count RISE against the arm we promised not to regress" (the Q4 gate) and "where did the change land". Lays the arms out as one table (lawtrue / adjudicated / airside / groundside per cell), applies a stated per-cell airside CEILING (`--gate ARM`, default the first census listed, or `--gate-json FILE` for a recorded frame of record), prints the arm-vs-arm delta and, with `--bands`, the census's magnitude bands. **It measures nothing and derives no number** — every value is read verbatim from a `harness/census.py --json` artifact; a reporter that recomputes a defect count is the census-wrapper defect. Equality PASSES the gate ("may not rise"); a cell with no ceiling is reported as ungated, never as a pass. Promoted 2026-08-06 from `tmp/c8fin/mx.py` on its second use (c9feed) — promote-on-reuse; the lane copy hard-coded one round's frame as a module constant. Twin: `tests/test_census_matrix.py`. |

| `Ortho4XP/tools/census_rows_diff.py` | You have TWO `harness/census.py --rows-json` dumps (a control arm and an arm under test) and the question is WHICH rows moved, not how many. A class delta hides equal churn by construction — 200 new and 182 gone read as "+18" — and the zero-new-adjudicated-airside bar is a claim about ROWS, so it needs a row-level reader. Joins the two dumps in three labelled tiers: EXACT (same family / role pair / side, both endpoints identical to the millimetre in the patch's own layout-local metre frame), MOVED (same class, nearest surviving partner within `--tol`, default 0.50 m, each partner used once — an INFERENCE, labelled one everywhere, and quoting two tolerances is how you show the join is not doing the work), and NEW / GONE (no partner — the rows an attribution owes a mechanism for). **It derives no law and measures nothing**: every row is read verbatim out of a census dump, the census staying the only instrument that produces defect counts. REFUSES a join across different `law_true_knobs` or a different axis frame (two dumps read under different law are not one population), a class-level census JSON, and a truncated dump. `--side` / `--family` filter the REPORT, never the join. Twin: `tests/test_census_rows_diff.py` (the four tiers on a hand-built scene, the tolerance knob both ways, class isolation, endpoint-order invariance, partner-used-once, nearest-wins, exact-beats-near, every refusal). |

| `Ortho4XP/tools/pad_span_census.py` | The question is DOES THIS UNIT'S OWN DATUM FIT ITS BODIES' PADS — *how far apart do the emitted `building` pads one FOOTPRINT UNIT stands on actually stand?* — the single number owner RULINGS 2026-09-14c item 1 is accepted or refused on (spec `object-placement-spec.md` §16g (1)/(7)). No other instrument asks it: `harness/census.py` prices PAIRS OF VALUES, so an object seated 23.70 m above its own pad breaks no grade law and reports ZERO rows; `obj8_split_report.py` prints a body's anchor and its own ground but never asks whether the bodies sharing ONE unit's datum stand on pads that disagree; `role_overlap_read.py` is an AREA sweep and `role_edge_census.py` a boundary-length one. This is the unit-vs-pad reading: per unit, the `building` pads its bodies' FEET fall inside, how many bodies it holds, and the SPAN of those pads' planes, largest first. **It measures no law and counts no defects** — the pads are the emitted design surface's own `building` faces at `median(z)` over the ring, which is the plane `footprint_unit` reads through `anchor_rule.pad_plurality`, and the body→part join is the PART ID, never a proximity match (memory `canonical-identity-join`). `--over` (default 1.0 m) is the listing floor 14g stated its bar in, not a threshold with any standing. It takes either `o4_v2_placement_<ICAO>.json` or an `obj8_split_report --json` dump — both carry the same `splits` body records. Measured basis (scout `v2heca331` on the owner's 1.0.331 HECA): 17 units whose pads span > 1 m over 1,363 bodies, `fu:38:20` alone 978 bodies on 136 pads spanning 34.8 m — the unit chained on PART BOXES, and its DECK member then gave 96.20 to 1,509 bodies. Promoted 2026-09-14 from that scout's scratchpad `padspan.py` on its SECOND use (RULINGS `7e90032`, promote-on-reuse) — the 14g attribution, then lane `v2connector` round 3's before/after. Several patches are reported separately; quote it on identical options. Twin: `tests/test_pad_span_census.py` (the span IS the unit's own pads, a non-`building` face is not a pad, a unit on one pad is not a row, a body with no `unit_of` is not counted, the floor both ways, the CLI's JSON IS the library result, and this index row). |

| `Ortho4XP/tools/role_edge_census.py` | The question is WHAT SHARES AN EDGE WITH WHAT — *how many metres of a groundside shape's boundary run along AIRSIDE PAVEMENT in an emitted patch* — the single number owner RULINGS 2026-09-12c is accepted or refused on ("shapeID 81 ... cannot be groundside because it shares a long edge with an apron. Something can only be groundside if it has no connection to airside other than a service road"). No other instrument answers it: `harness/census.py` prices PAIRS OF VALUES, so a lot welded flat along 828 m of apron breaks no grade law and reports ZERO rows; `role_overlap_read.py` asks AREA overlap (what STANDS on what), which is 0 for two faces that merely share a boundary; `osm_site.py` answers one coordinate. This is the BOUNDARY-LENGTH sweep: per groundside shape its area, perimeter, inscribed radius (area / perimeter) and the metres shared with airside pavement / with `service_road`+`service_junction` / with `building`, largest first; `--min-m` (§27's `[lot] airside_edge_min_m`, default 10) and `--min-radius` (its sliver floor, default 1.0 m) split the population into SUBSTANTIVE, SLIVER and LOT-class. **It measures no law and counts no defects** — geometry, roles and the groundside partition come from the harness library (`check_grade._parse_osm`, `effective_role`, `_GROUNDSIDE_ROLES`), imported and never re-spelled (the census-wrapper precedent); defect counts come from `harness/census.py` and nowhere else. Edges are joined on NODE IDENTITY — a shared edge is two shapes listing the same node pair, exactly what the planar weld produces — never a proximity match (memory `canonical-identity-join`). Measured basis (shipped 1.0.320 LEMD): 175 groundside shapes, 105 sharing >= 10 m with airside pavement, 71 substantive (182,604 m², 34 slivers excluded), of which 13 LOT-class / 145,262 m² — the owner's shapeID 81 (`pav137`) 140.2 m of its 270.9 m perimeter, `pav125` 828.4 m. Promoted 2026-09-12 from the `v2lemd320t` scout's `census_gs.py` on its second use (RULINGS `7e90032`). Several patches are reported separately — the arm-to-arm read; quote it on identical options. **`--pad-frontage`** is the SECOND question on the same geometry and the same joins (added 2026-09-12, lane `v2frontage`, spec §28): *pad -> neighbour -> shared edge m -> STEP m*, the read owner RULINGS 2026-09-11ai-1 -> 2026-09-12r ("grade frontages only") is accepted on. No other instrument answers it either: the harness census FORGIVES a declared terrace across a shape joint (`terrace_joints_ll`), so a car park standing 3 m above the terminal it fronts prices ZERO rows — and at LEMD the owner's +3.03 m is not even a declared joint (the patch carries 4, none of them `building4`'s). Per `building` shape: each groundside neighbour (`groundside_pavement` / `service_road` / `service_junction`, `parking_lot` by its class tag), the metres of edge they SHARE by node identity, the facing-vertex pairs within `--near` (default 2.0 m) and the largest and mean SIGNED step, neighbour minus pad. The proximity read is not a shortcut: the pad-frontage relation is a proximity relation in the engine too (`[design] pad_frontage_m` 3.0, owner RULINGS 2026-09-10ax (1)) and `building4` / `pav124` share not one node while standing 0.71-1.50 m apart. `--min-step` (default 0.05 m) is the listing floor. Measured basis (shipped 1.0.321 LEMD): ONE pad with a groundside step >= 0.10 m — `building4`, `pav124` +3.03 / +2.67 and `route6` +0.38. Twin: `tests/test_role_edge_census.py` (the shared edge IS the node-identity join, the airside-pavement set excludes `building`, service-road metres are reported apart, the sliver split, prices-no-law, the pad-frontage step across a proximity gap and across a welded edge, and this index row). |

| `Ortho4XP/tools/void_census.py` | The question is about ENCLAVE TOPOLOGY on a shipped patch: which regions does airside pavement completely surround, which of them have a tunnel/bridge ESCAPE, and what is sitting inside them. Reads back exactly the geometry the enclave region law computes (`auto_patch/enclaves.py`). `--union` selects WHICH union, because the law has two and they answer different questions: `surround` (default) is airside ∪ BUILDINGS, the set published as `layout.airside_enclaves` and the CLASSIFIER's question ("is this ground airside-interior?"); `pavement` is airside pavement only, which is the GAP LAW's own detection union and therefore the scope of the adjacent-ground BAND KEEP-OUT (`enclaves.enclave_band_keepout_union`). The distinction is load-bearing and was measured: buildings standing in HECA's 3.4 km² infield subdivide it into pocket-width components in the `surround` union while the gap law holds it as ONE wide region and declines it on width, so scoping the keep-out by the wrong union deleted 152,734 m² of Annex 14 §3.4.11-13 graded strip. The union is stamped into every report — two unions are two populations. Reports per void its area, perimeter, minimum-rotated-rect SHORT SIDE and POCKET flag (short side ≤ the gap law's own `GAP_FILL_MAX_WIDTH_M`, the class the ruled gap ring + spine treatment covers; under `--union pavement` that flag IS the band keep-out's membership test), the escapes, whether the gap treatment emitted a face there, the per-role/ref contents, the retaining-wall inventory with way ids, and the BARE GROUND remainder carrying no shape at all — the 87.6 % that made the shape-scoped G-ENCLAVE predicate structurally blind. `--bands` adds the ADJACENT-GROUND inventory beside the topology: band and `adjacent_ground_wall` way counts and areas, split by where each way SITS — inside a POCKET no-escape void (the keep-out's own territory), inside another no-escape void, or outside every void — each way in exactly one column, the columns summing to the total. Reach for it whenever a band-area delta is about to be quoted: the total alone cannot tell a keep-out that removed band inside pocket voids from one that also took ground nothing owns, and that is precisely the failure the ratified scoping fixes. **It measures no law and derives no defect count**: grade defects come from `harness/census.py` and nowhere else, and the role vocabulary plus the escape set are IMPORTED from `auto_patch.enclaves` rather than re-typed (the census-wrapper precedent). Parses with the harness library's own reader (`check_grade._parse_osm`) in the builder's anchor frame from the axes sidecar, so this tool and the census read one geometry; without a sidecar the topology is unchanged and lat/lon are simply not reported. FRAME: emitted geometry is post-decimation and post `_separate_groundside_from_airside`, so a void reads slightly larger than the in-build region and a groundside shape inside it reads pulled back from the rim; a real-DEM patch is never comparable with a constant-DEM one. The in-build predicate also honours the `is_bridge` SHAPE FLAG, which `to_osm` does not emit — so this reader sees the four escape ROLES and no more (stated by the tool itself). Promoted 2026-08-07 from `tmp/enclave_attrib/void_census.py` on its second use (promote-on-reuse); the lane copy carried its own patch reader and a hand-typed role list. Twin: `tests/test_void_census.py`. |

| `Ortho4XP/tools/seat_feet_census.py` | THE DRAPE RESIDUAL AT EVERY PLACEMENT'S FEET (RULINGS 2026-09-09ac (3); the placement reading 11e (3), spec §7/§9) — `--placement-plan o4_v2_placement_<ICAO>.json` with `--mesh` (a built mesh) or `--graded` (the emitted design surface, for a dry run with no tile built): per placement of the plan's own rows, `surface(foot) − (surface(anchor) + y_foot)`, the |Δ| histogram (<0.3 / 0.3-1 / 1-3 / >3 m), the same by class, the worst N with lat/lon, and §13's elevated-body / footless-carrier bars. Feet are read from the AUTHORED pack (`.anchor_bak` when one exists). THE SEAT-RESULT MODE IS DELETED (owner RULINGS 2026-09-12s, spec §8) — the name is kept because the INDEX row, `obj8_split_report` and the twins address it by it. Writes nothing to the pack. §17 THE COCKPIT BLOCK (owner RULINGS 2026-09-12x/12y, lane `v2cockpit`) is printed FIRST, before the §14 bars: the §15 floats, the §16a (2) refusal set's `ground_off`, the §16b own-ground floats and the §16c torn seams classified CRITICAL VISUAL at `[cockpit] visual_m` 0.5 m (with the worst named by resource AND coordinate) or REPORT under it, from `placement_census.cockpit_block` — the SAME `[cockpit]` law keys the terrain census reads, one frame for both stages. `split_tol_m` 0.3 stays a PARTITION choice and its `body wider than its terrain group` count is REPORT whatever its size. CRITICAL MOTION is named as an instrument limit rather than printed as a zero HERE: §17's motion reading needs the graded face ROLE under each foot, and this tool hands the block none — `obj8_split_report.py` is the entry that takes it (owner RULINGS 2026-09-12am (2), lane `v2objmotion`). §16e (owner RULINGS 2026-09-13k, lane `v2othhdatums`): `--placement-plan --mesh` WAS BROKEN — it passed its bbox as `(lat, lon)` to `MeshElevationSampler`, which takes `(min_lon, min_lat, max_lon, max_lat)`, so at OTHH it asked for a box at lon 25.2 / lat 51.6 and the sampler raised `no mesh triangles inside ... — wrong tile?`; the one place the two orders meet is now `plan_bounds()` and a twin holds it end to end over the sampler's own mesh fixture. The report also prints `§16e bodies on a DATUM` (a crest plate / a deck top) as its own class and EXCLUDES them from §13's `elevated bodies as own files` bar: a datum body's `y_zero` is +5 … +10 m by construction, and counting it there reported the law as the defect (OTHH 0 -> 10 -> 0 with the class printed apart). §16e (3) (Fable 2026-09-13, RULINGS 2026-09-13v, lane `v2bridgecontact`): the report also prints THE BRIDGE FAMILY block (`airport/bridge_family.census_bridges` / `census_bridges_lines`, re-exported through `placement_census`, the same call `obj8_split_report` makes over the same plan shape) — per `Bridge_NN` the deck's own body's world DECK TOP against the land under that bridge's own written geometry (`|deck top - highest land|`, bar `[cockpit] visual_m` 0.5 m), the PER-PLACEMENT zero spread (`max - min` of `surface_z - y_zero` over one placement's bodies; `Bridge_02_CLUTTER_007` is six piers of ONE solid), the CROSS-BRIDGE carriers (a body whose `merged_into` names a file of another bridge, bar 0) and how many bodies publish `bridge_of` and agree with the resource's own tag. The `Bridge_NN` axis is the CENSUS's, never the law's — §16e (3) exists because the name does not name a bridge — so the agreement count is the instrument's own check on the derived relation. Measured on the app's 1.0.326 OTHH frame: `Bridge_01` deck top 3.23 -> 3.96 and `Bridge_04`/`Bridge_05` KEPT -> 3.96 (all three |deck top - land| 0.00, PASS), cross-bridge carriers 2 (unchanged — the bind and the filter are refuted and deleted, see `bridge_family`'s module doc). |

| `census_lockstep.py` | `harness/census.py` (law-true + bare frames, class table) |

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
HECA  patch    base 63258868   lane v2qp             2026-09-15T00:29:54  /tmp/harness/v2qpHECA.osm  — CLOSING build of claude/v2qp 682d1810 with [design] solver="qp" (§20c; the branch SHIPS fixed_point — this is the QP ARM): rc 0, 449.1 s, ways 1741, nodes 31261, body_sha 73b5bdecfd98, artifact ledger 2f4e1c4f8717, status optimal, shared repo UNCHANGED, v2-verify 30592 rows. design line: QP (§20c) 6 exact solves optimal x6, 197 rounds / 358 linear solves, 50.09 s, worst |grad| 537.7; 18/329337 hard rows over 0.02 m (3 a proved INFEASIBLE SET, 3.1661 m) vs the fixed point's 39. Census law-true 61845 ADJUDICATED 26348
HECA  graded   base 63258868   lane v2qp             2026-09-15T00:29:54  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2qp/emit_heca_qp/HECA.graded.json  — QP ARM of the v2qp matched HECA replay pair off the registered v2settle capture (cap/HECA.pkl, base b1b7704c), --design-weight solver=qp: solve 131.0 s (fixed point 127.4 s = 1.03x), hard rows over 0.02 m 39 -> 18, worst 1.2595 unchanged, infeasible set 4 -> 3. Its BASE ARM (fixed_point, same tree) is /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2qp/emit_heca_fp/HECA.graded.json, which reproduces v2settle r2's registered reading exactly (39/329775, objective_stalled x6). Census A/B ADJUDICATED 26634 -> 26607, no family worse by > 5 %
HECA  capture  base 12400580   lane v2qp             2026-09-15T00:29:54  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2settle/r2/heca.solved.pkl  — RE-READ by lane v2qp as the §20c STABILITY PROBE frame, through the promoted instrument 'v2_solve_replay --why-from PKL --probe-site 30.1279552,31.403143 --probe-arm solver=fixed_point --probe-arm solver=qp'. fixed_point reproduces 14bw exactly: 959 of 31820 moved > 0.02 m, 959 beyond 250 m, 953 beyond 500 m, ZERO within 100 m, worst 0.5206 m, hard 39 -> 25 under the probe. qp: 0 moved anywhere, max |dz| 0.0043 m field-wide, hard 18 -> 18. Same capture solved twice is BITWISE identical on both arms (sha cef4f5c8a773 / 01c2f08e40b1)
HECA  capture  base 2117c48c   lane v2padqp          2026-09-15T09:52:26  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2padqp/cap/HECA.on3.pkl  — HECA PADS-ON capture (--placement pad_from_cluster=true pad_airside_clip=true), 170 s, 32,182 vertices / 1,811 faces, guard UNCHANGED. Its solved pickle h2.on.pkl is the §16g (10) (11) probe frame: one 0.30 m ceiling at 30.1279552,31.403143 moves 16 of 32,182 vertices, ALL beyond 500 m, worst 0.1031 m (the same capture with the clip left at the MINT moved 0, max 0.0192 m). Matched OFF arm cap/HECA.off3.pkl
HECA  capture  base 2117c48c   lane v2padqp          2026-09-15T09:52:26  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2padqp/cap/HECA.off3.pkl  — HECA PADS-OFF capture (the shipped law), 186 s, 31,820 vertices / 1,684 faces, guard UNCHANGED - BASE ARM of the v2padqp HECA pair (census ADJUDICATED 26,608; pad_cluster_mismatch 16)
HECA  patch    base f32fb08c   lane v2channel        2026-09-15T10:23:51  /tmp/v2channel/r3/br_HECA/structures.json  — v2channel round-3 DRY structure replay (branch), paired with base HECA at main 46b219d8 in /tmp/v2channel/r3/base_HECA
HECA  capture  base 5144df7d   lane v2padqp          2026-09-15T10:51:20  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2padqp/cap/HECA.clip.pkl  — THE CLIP-ONLY ARM (--placement pad_airside_clip=true pad_from_cluster=false), 209 s, 30,980 vertices / 1,665 faces, guard shared repo UNCHANGED. §16g (10) (11) r2's interventional attribution: against the pads-OFF arm this arm ALONE moves 4,474 airside vertices worst 1.39 m (runway 17 / 0.100) of the full pads-ON arm's 5,973 / 3.28 m -- three quarters of the airside movement is the ARRANGEMENT CLIP re-noding the airside faces, not any pad row
HECA  capture  base 848bf35e   lane v2lemdstruct2    2026-09-15T11:36:11  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/ls2/heca_on.pkl  — r4 CONTROL, flip ON arm (solved pickle off the registered v2padqp HECA.off3 capture): verify 30,500 rows. Its matched OFF arm is heca_off2.pkl beside it - ONE variable, the emit.toml one_way_rulings entry for structures.placement foot_row. Delta: verify 30,459 -> 30,500 (+41), airside_no_step 7,794 -> 7,823, 8 of 3,753 runway-family vertices moved > 0.02 m (worst 0.064 m), whole surface max 0.822 m. Only 3 of HECA's 4 foot targets touch airside pavement - the flip is nearly inert here, so LEMD's 5 m is a SITE property
HECA  patch    base 395bd09a   lane v2channel        2026-09-15T10:52:05  /tmp/v2channel/r4/br_HECA/structures.json  — v2channel round-4 DRY structure replay (branch, §45 (13)); base arm at main in /tmp/v2channel/r4/base_HECA
HECA  capture  base 7f80dc71   lane v2padclip        2026-09-16T09:49:01  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2padclip/cap/HECA.off.pkl  — HECA PADS-OFF capture (--placement pad_from_cluster=false pad_airside_clip=false = the shipped law) on claude/v2padclip, 186 s, 32,589 vertices / 1,738 faces, guard shared repo UNCHANGED. The FIRST HECA capture carrying §16g (10) (12) (the two-pass arrangement: the airside is noded before any pad exists) AND the arrangement's own re-node reading (deleted 0 / minted 40). BASE ARM of the v2padclip HECA triple; census ADJUDICATED 19,456, pad_cluster_mismatch 15, pad_airside_weld 9.
HECA  capture  base 7f80dc71   lane v2padclip        2026-09-16T09:49:01  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2padclip/cap/HECA.clip.pkl  — HECA CLIP-ONLY capture (--placement pad_from_cluster=false pad_airside_clip=true), 162 s, 31,576 vertices / 1,708 faces, guard UNCHANGED. The 15ah attribution arm re-cut under §16g (10) (12): re-node deleted 0 / minted 40 (before the rule the same arm read 1,008 deleted / 283 minted). Against the OFF arm the airside VALUE still moves 4,787 non-pad solve-owned vertices, worst 2.06 m, runway 19 / 0.070 m.
HECA  capture  base 7f80dc71   lane v2padclip        2026-09-16T09:49:01  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2padclip/cap/HECA.on.pkl  — HECA PADS-ON capture (--placement pad_from_cluster=true pad_airside_clip=true), 187 s, 32,769 vertices / 1,850 faces, guard UNCHANGED. re-node deleted 0 / minted 43. Census vs the OFF arm: ADJUDICATED 19,456 -> 18,686, pad_cluster_mismatch 15 -> 0, pad_airside_weld 9 -> 8. Airside moved (non-pad, solve-owned) 6,031 worst 3.09 m, runway 180 / 0.130 m -- attributed to the JOINT solve: the same pair under --design-weight staged_solve=1 reads runway 3 / 0.020 m.
HECA  patch    base 7f80dc71   lane v2padclip        2026-09-16T09:49:15  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2padclip/emit_heca_clip/HECA_auto.patch.osm  — HECA clip-only replay EMIT - the FIRST patch whose sidecar carries pad_airside_renode (40 rows, all 'minted'); census law-true 59,808 ADJUDICATED 18,759, pad_airside_renode 40.
HECA  capture  base 782a50d6   lane v2padclip        2026-09-16T10:59:14  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2padclip/r2/cap/HECA.lane2.pkl  — r2 HECA PADS-OFF (shipped law) capture with §16g (10) (12) (1) (c) landed: 164 s, 31,383 vertices / 1,695 faces, guard UNCHANGED. Its matched BASE ARM is cap/HECA.base.pkl (main 1bc93833, own ritual worktree). OFF-arm identity: census ADJUDICATED 19,032 -> 19,076 (+0.2%), law-true 59,215 -> 59,114; hairline_pair -537, taxi_box +0, pad_airside_weld +0. Its staged emit is emit_heca_off_st.
HECA  capture  base 782a50d6   lane v2padclip        2026-09-16T10:59:14  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2padclip/r2/cap/HECA.on2.pkl  — r2 HECA PADS-ON capture (pad_from_cluster+pad_airside_clip true). Staged OFF->ON (solve-owned, non-pad): 2,230 moved worst 2.68 m, RUNWAY 2 at 0.020 m. THE PROBE on its staged solve (heca_on_st.pkl): one 0.30 m ceiling moves 0 of 32,575 > 0.02 m, max 0.0167 m, nothing beyond 250 m. Third arm with every pad generator dropped still moves 1,544 / 2.00 m -- the movement is NOT a pad row.

## Registered frames: LEMD

LEMD  capture  base ec8723e9   lane v2roadcap        2026-09-13T12:06:34  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/rw/cap/LEMD.pkl  — the v2roadcap-era LEMD capture used by scout v2unsettled2
LEMD  capture  base 864e7577   lane v2settle         2026-09-13T12:06:34  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2settle  — fresh main capture + per-law arms + logs (13ak)
LEMD  patch    base f4e9b436   lane v2gradecache     2026-09-13T18:08:32  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/fin_LEMD/structures.json  — LEMD planar --stage structures on claude/v2gradecache vs the 0c86fe2c base arm in scratchpad/base_LEMD: every basin rim_ll/region_ll/floor_z/ramp_rings_ll/area/notes and every basin refusal BYTE-IDENTICAL; only covered_fraction moves 0.22750697->0.22750614 at the 1 cm plane quantum
LEMD  mesh     base 8fce79cb   lane v2hairline       2026-09-13T17:43:19  /tmp/harness/tile_v2hairline_arm3/Data+40-004.mesh  — §39 ARM: shore weld ON, metric split ON, vector weld OFF — sub-0.1 m2 in bbox 1,641, aspect p50 1.61, 2,734,780 tris
LEMD  patch    base df67b414   lane v2hairline       2026-09-13T17:43:19  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2hairline/control.osm  — §39 CONTROL patch (harness tag v2hairline_control) with shore_edges injected from the same TileWater witness — hairline_pair 29 adjudicated
LEMD  capture  base 32c78eaf   lane v2lemd329        2026-09-13T20:49:45  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/cap/LEMD.pkl  — fresh LEMD v2_solve_replay capture on main 32c78eaf (22158 vertices, 1119 faces, 353 s) — for the sunken-road round
LEMD  mesh     base 00d8b05c   lane v2hairline       2026-09-13T21:16:09  /tmp/harness/tile_v2hairline_r2cp/Data+40-004.mesh  — §39 round 2 FINAL arm: one witness + project + merge + crossing dedupe + 13cp z carry — 1,617 sub-0.1 m2 in bbox, aspect p50 1.65, 2,745,864 tris, pre-flight 7 UNMESHABLE (all non-patch markers)
LEMD  mesh     base 6b3a57cb   lane v2bankfoot       2026-09-13T21:59:14  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2bankfoot/fix/Data+40-004.mesh  — FIX ARM (13cp): bank rings CLOSED again, open runs wear PATCH_RING_MARKER, ribbon belt — annulus 39,105 of 58,555 valued, harmonic moved 491, isolated components 0, 111 closed bank_foot ways / 0 open; owner site 40.465414,-3.5531888 median 589.00 (1.0.329: 568.3); attr-8 nodes over 2 m = 3 of 275,861
LEMD  mesh     base 6b3a57cb   lane v2bankfoot       2026-09-13T21:59:14  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2bankfoot/omit/Data+40-004.mesh  — OMIT ARM (owner request): [design] bank_omit=true, NO bank_foot emitted — ribbons restored too (attr-8 over 2 m = 4), but patch edge step median 0.740 / p95 5.680 / >3 m 2,584 vs the fix arm's 0.415 / 4.944 / 1,924
LEMD  patch    base 05cf9282   lane v2leafframe      2026-09-14T21:43:48  /tmp/harness/v2leafframeLEMD.osm  — lane v2leafframe CLOSING LEMD patch build (claude/v2leafframe 443b5c0f, base main 05cf9282): rc 0, 786.0 s, body_sha c917d457d4c6, solve feasible, guard shared repo UNCHANGED (38 external-candidate Masks/OTHH deltas named, another lane's; no artifact-ledger key stored for that reason). THE FIRST frame carrying Part.height_m in ONE frame (RULINGS 2026-09-14bo): 29,684 parts 580-646 m -> 0.000-50.001 m, walled 29,684 -> 12,325. Unit census 22 units / 536 bodies-in-a-unit / largest 236 members spanning 2,855 m -> 20 / 206 / 84 members spanning 1,670 m. Items 2/4/6/9 all OUT of the giant units and on their own ground. Sec17 FLOATING 1305 -> 185, BURIED 2054 -> 1725, feet > 1 m 2427 -> 918. NEW: Sec15 carried float 0 -> 2.
LEMD  rebake   base 05cf9282   lane v2leafframe      2026-09-14T21:43:48  /tmp/harness/v2leafframeLEMD.v2/LEMD.rebake.json  — lane v2leafframe CLOSING LEMD patch build (claude/v2leafframe 443b5c0f, base main 05cf9282): rc 0, 786.0 s, body_sha c917d457d4c6, solve feasible, guard shared repo UNCHANGED (38 external-candidate Masks/OTHH deltas named, another lane's; no artifact-ledger key stored for that reason). THE FIRST frame carrying Part.height_m in ONE frame (RULINGS 2026-09-14bo): 29,684 parts 580-646 m -> 0.000-50.001 m, walled 29,684 -> 12,325. Unit census 22 units / 536 bodies-in-a-unit / largest 236 members spanning 2,855 m -> 20 / 206 / 84 members spanning 1,670 m. Items 2/4/6/9 all OUT of the giant units and on their own ground. Sec17 FLOATING 1305 -> 185, BURIED 2054 -> 1725, feet > 1 m 2427 -> 918. NEW: Sec15 carried float 0 -> 2.
LEMD  graded   base 05cf9282   lane v2leafframe      2026-09-14T21:43:48  /tmp/harness/v2leafframeLEMD.v2/LEMD.graded.json  — lane v2leafframe CLOSING LEMD patch build (claude/v2leafframe 443b5c0f, base main 05cf9282): rc 0, 786.0 s, body_sha c917d457d4c6, solve feasible, guard shared repo UNCHANGED (38 external-candidate Masks/OTHH deltas named, another lane's; no artifact-ledger key stored for that reason). THE FIRST frame carrying Part.height_m in ONE frame (RULINGS 2026-09-14bo): 29,684 parts 580-646 m -> 0.000-50.001 m, walled 29,684 -> 12,325. Unit census 22 units / 536 bodies-in-a-unit / largest 236 members spanning 2,855 m -> 20 / 206 / 84 members spanning 1,670 m. Items 2/4/6/9 all OUT of the giant units and on their own ground. Sec17 FLOATING 1305 -> 185, BURIED 2054 -> 1725, feet > 1 m 2427 -> 918. NEW: Sec15 carried float 0 -> 2.
LEMD  capture  base 05cf9282   lane v2leafframe      2026-09-14T21:43:49  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/leafframe  — DRY one-frame counterfactual arms for LEMD/HECA/KCLT/OTHH/SPJC: oneframe.py rewrites a registered rebake plan's Part.height_m to the authored component extent (the fix's own output, VERIFIED byte-equal to the built LEMD plan), obj8_split_report --json before/after beside each, unitcensus.py + sites.py readers, and the pristine-dump OBJECT_MSL censuses (mslp_b336.txt / mslp_built.txt: LEMD MSL rows 1,481 -> 0).
LEMD  patch    base 87bb9f38   lane v2lemdstruct     2026-09-14T21:49:27  /tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/ls/base/structures.json  — BASE dry 'planar --stage structures' at main 87bb9f38: bores 70 / mouths 90 / tunnels 50 / decks 11 / cells cut 3 / plate mouths 2 / basins 1; underpass -1230 clip 5.6 m centreline ribbon, 2 roads bored; basin:0 rim stations beyond 2.0 m = 58 of 69
LEMD  patch    base e5078016   lane v2lemdstruct     2026-09-14T21:49:27  /tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/ls/r3/structures.json  — AFTER dry 'planar --stage structures' on claude/v2lemdstruct e5078016 (RULINGS 14bp derivations 1/2/3/4): every count identical to the base bar decks 11 -> 7 (parallel carriageways grouped); underpass clip = the deck CELL across the axis, 772 m2, 2 roads bored; plate mouths CLAMPED (moved 0.9 / 0.1 m, -5931 mouths back at 40.4980351,-3.5850028 and 40.4960205,-3.5849927); basin rim-snap REFUTED (median 19.24 m to the at-grade contour, 11 of 68 within 2 m)
LEMD  patch    base e5078016   lane v2lemdstruct     2026-09-14T22:11:40  /Users/noah/XPTerrainBuilder/.claude/worktrees/v2lemdstruct/Ortho4XP/Patches/+40-010/+40-004/LEMD_auto.patch.osm  [MISSING]  — CLOSING BUILD v2lemdstruct1 (build_airport.py LEMD --tile 40 -4), rc 0, 946.7 s (vector 874.3 + mesh 71.7), shared repo UNCHANGED, verify defects {}, solve feasible 146 rounds 395.5 s. Census vs the 1.0.336 tile patch: ADJUDICATED 2094 -> 1924, road_cross_section 14 -> 8, within_shape 3963 -> 3918, taxi_box 241 -> 178; COCKPIT motion 6 -> 4, visual 1184 -> 1181. Mesh at /tmp/harness/tile_v2lemdstruct1/Data+40-004.mesh
LEMD  mesh     base e5078016   lane v2lemdstruct     2026-09-14T22:11:40  /tmp/harness/tile_v2lemdstruct1/Data+40-004.mesh  — v2lemdstruct1 tile mesh: the bridge transect at lat 40.4835412 over lon -3.5812..-3.5788 reads 610.88 -> 606.15 -> 607.13 with NO station-to-station step over 0.5 m; the residual dip past the owner's east end 40.4835412,-3.5799114 is 0.73 m peak-to-trough (the 1.0.336 read was a 2.2 m notch)
LEMD  capture  base da8e5d7f   lane v2lemdstruct2    2026-09-15T08:29:03  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/ls2/cap/LEMD.pkl  — fresh LEMD v2_solve_replay capture on claude/v2lemdstruct2, base main da8e5d7f (20,608 vertices, 1,024 faces, 286 s; clusters 7776, pack partition 115 s) — the 15e items 5/7 round (33 (5), 34 (11), 34 (5) (b))
LEMD  patch    base da8e5d7f   lane v2lemdstruct2    2026-09-15T09:14:50  /Users/noah/XPTerrainBuilder/.claude/worktrees/v2lemdstruct2/Ortho4XP/Patches/+40-010/+40-004/LEMD_auto.patch.osm  [MISSING]  — lane v2lemdstruct2 CLOSING LEMD tile build (tag v2lemdstruct2, branch claude/v2lemdstruct2 @ 5ed9b083, base main da8e5d7f): rc 0, 551.8 s (vector 491.5 + mesh 59.5), solve optimal 40.4 s, ledger tree 3e3e13880a2a. WARNING: the harness flagged the run CONTAMINATED — it rewrote OSM_data/+40-010/+40-004/+40-004_big_roads.osm.bz2 (2,197,226 -> 2,199,670 bytes), the v2roadtags ROAD_CACHE_TAG_SCHEMA bump merged into main the same morning; the matched REPLAY pair off the registered capture is unaffected. 33 (5): item-5 mouth floor 599.25 -> 597.09 under a rim at 602.16 = 5.07 m vs bore_datum_m 5.10. 34 (5) (b): item-7 trench mouth 12.77/15.46 m -> 31.06/33.43 m from the owner node, beyond the 19.0 m code-E strip; zone1 intact at 18.15 m. Census: ramp_in_strip 11 -> 8 (all runway-strip), wall_in_runway_strip 10 -> 6, tunnel_mouth_canonical 32 -> 28
LEMD  mesh     base da8e5d7f   lane v2lemdstruct2    2026-09-15T09:14:50  /tmp/harness/tile_v2lemdstruct2/Data+40-004.mesh  — lane v2lemdstruct2 CLOSING LEMD tile build (tag v2lemdstruct2, branch claude/v2lemdstruct2 @ 5ed9b083, base main da8e5d7f): rc 0, 551.8 s (vector 491.5 + mesh 59.5), solve optimal 40.4 s, ledger tree 3e3e13880a2a. WARNING: the harness flagged the run CONTAMINATED — it rewrote OSM_data/+40-010/+40-004/+40-004_big_roads.osm.bz2 (2,197,226 -> 2,199,670 bytes), the v2roadtags ROAD_CACHE_TAG_SCHEMA bump merged into main the same morning; the matched REPLAY pair off the registered capture is unaffected. 33 (5): item-5 mouth floor 599.25 -> 597.09 under a rim at 602.16 = 5.07 m vs bore_datum_m 5.10. 34 (5) (b): item-7 trench mouth 12.77/15.46 m -> 31.06/33.43 m from the owner node, beyond the 19.0 m code-E strip; zone1 intact at 18.15 m. Census: ramp_in_strip 11 -> 8 (all runway-strip), wall_in_runway_strip 10 -> 6, tunnel_mouth_canonical 32 -> 28
LEMD  patch    base da8e5d7f   lane v2lemdstruct2    2026-09-15T09:14:50  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/ls2/base_emit/LEMD_auto.patch.osm  — BASE ARM of the matched replay pair (v2_solve_replay --replay on the registered da8e5d7f capture, base tree, --emit): LAW-TRUE 5688 / ADJUDICATED 1341, ramp_in_strip 11, strip_transverse worst 5.589 m, within_shape 3397, tunnel_mouth_canonical 32; item-5 floor 599.25 under rim 602.16 (2.91 m); item-7 ramp at 15.46 m, 572.02-572.42 under a 577.84 kerb
LEMD  patch    base da8e5d7f   lane v2lemdstruct2    2026-09-15T09:14:50  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/ls2/a4_emit/LEMD_auto.patch.osm  — ARM of the matched replay pair (--from planar, 33 (5) + 34 (5) (b)): LAW-TRUE 5756 / ADJUDICATED 1404, ramp_in_strip 8, strip_transverse worst 13.872 m, within_shape 3464, tunnel_mouth_canonical 28
LEMD  capture  base 2117c48c   lane v2padqp          2026-09-15T09:52:26  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2padqp/cap/LEMD.on3.pkl  — LEMD PADS-ON capture (v2_solve_replay --capture --placement pad_from_cluster=true --placement pad_airside_clip=true, 219 s, 20,473 vertices / 1,011 faces, guard shared repo UNCHANGED) - the FIRST LEMD capture carrying the derived cluster pads; the T4 cluster unit:25#843 (421,940 m2, 761 walled, PKT4 a member) mints ONE pad containing the owner's garage at 40.4892214,-3.5944287. Its matched OFF arm is cap/LEMD.off3.pkl
LEMD  capture  base 2117c48c   lane v2padqp          2026-09-15T09:52:26  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2padqp/cap/LEMD.off3.pkl  — LEMD PADS-OFF capture (--placement pad_from_cluster=false pad_airside_clip=false = the shipped law), 226 s, 21,348 vertices / 1,058 faces, guard UNCHANGED - the BASE ARM of the v2padqp LEMD pair; reproduces 15h's garage reading (nearest pad building12 55.3 m away, median 616.35)
LEMD  patch    base 2117c48c   lane v2padqp          2026-09-15T09:52:26  /tmp/harness/v2padqpLEMD2.osm  — CLOSING BUILD v2padqpLEMD2 with BOTH §16g (10) pad keys ARMED (the measurement arm; the branch SHIPS them false): rc 0, 346.3 s, ways 1048, nodes 20304, status optimal, body_sha e5d30cf207a8, artifact ledger 50546224d866, v2-verify 1,633 rows, '[harness] shared repo UNCHANGED by this build (full-surface before/after snapshot)'. The owner's T4 garage at 40.4892214,-3.5944287 is INSIDE pad building45 (93-node face, every face of the ref at median 615.35) and the pad law defeats the spurious basin:1 there
LEMD  patch    base 9c313551   lane v2lemdstruct2    2026-09-15T09:47:19  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/ls2/b2_emit/LEMD_auto.patch.osm  — r2 SHIPPING ARM (v2_solve_replay --from planar on the registered da8e5d7f capture, tree = claude/v2lemdstruct2 r2): solve optimal 54.5 s; v2 verify 1,576 rows (within_shape 466 -> 422 under 34 (13) (1)'s axis reading, tunnel_mouth_canonical 28, wall_in_runway_strip 6); census LAW-TRUE 5,712 / ADJUDICATED 1,360, within_shape 3,420, ramp_in_strip 8, strip_transverse worst 13.872 m. Surface byte-equal to r1 at both owner sites (item 5 floor 597.09 under rim 602.16; item 7 mouth 31.06/33.43 m). NO BUILD: the osm_layers refresh RULINGS 15u calls for has not been run
LEMD  patch    base 9c313551   lane v2lemdstruct2    2026-09-15T09:47:19  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/ls2/b1_emit/LEMD_auto.patch.osm  — 34 (13) (2) REFUTED ARM (outermost airside strip; the code is DELETED): every bar moved backwards - ramp_in_strip 8 -> 19 (bar was 0), strip_transverse 83/13.872 m -> 90/19.070 m, verify wall_in_runway_strip 6 -> 20, cockpit CRITICAL visual cliffs 10 -> 24, ADJUDICATED 1,360 -> 1,372; the trench mouth 31.06/33.43 -> 41.67/43.25 m, still inside 14R/32L's 75 m strip. Kept as the refutation record
LEMD  patch    base 106459fa   lane v2objcut         2026-09-15T09:44:01  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2objcut/r4_LEMD/structures.json/structures.json  — §33 (6) LEMD matched pair (base /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2objcut/b4_LEMD/...): the same six arrays BYTE-IDENTICAL (1/50/0/1/3/0), plate_mouths 2->2, crest_from_approach 2->2, underpasses 1->1; +25 named §33 (6) refusals only.
LEMD  patch    base f32fb08c   lane v2channel        2026-09-15T10:23:51  /tmp/v2channel/r3/br_LEMD/structures.json  — v2channel round-3 DRY structure replay (branch), paired with base LEMD at main 46b219d8 in /tmp/v2channel/r3/base_LEMD
LEMD  patch    base 539e524e   lane v2lemdstruct2    2026-09-15T10:24:50  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/ls2/c6_emit/LEMD_auto.patch.osm  — r3 CLOSING ARM (v2_solve_replay --from planar on the registered da8e5d7f capture, tree = claude/v2lemdstruct2 r3): solve optimal 45.9 s, v2 verify 1,564 rows. 34 (13) (3) junction_raw_transverse ON as a one-way TARGET (1,591 rows, 62 contacts) - the owner's pair at 40.4611623,-3.5444804 still 4.296 % over 18.2 m; hard refuted twice (all 1,591: 10,006/109,240 violated worst 60.48 m; the 62 contacts alone: 8,548/106,182 worst 105.29 m). 34 (13) (4) mouth_pair_roads ON: 4 faces / 3,775 m2 at LEMD incl. mouth_road:-5944 (way -10867, 605.09-611.00 m, worst edge 8.00 % at the road cap), KCLT 3 / 3,564 m2, OTHH 0. Census ADJUDICATED 1,360 -> 1,344, LAW-TRUE 5,712 -> 5,692, transverse 107 -> 98, airside_no_step 475 -> 460. Hole ring -10670 cover 0.011 -> 0.023, rings > 10,000 m2 13 -> 13. NO BUILD: the ledger's last osm_layers refresh is 2026-09-08 (SPJC)
LEMD  patch    base 539e524e   lane v2lemdstruct2    2026-09-15T10:24:50  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/ls2/c1_emit/LEMD_auto.patch.osm  — r3 arm c1 (constraints-stage): junction_raw_transverse as a SOFT one-way target only, no mouth roads - solve optimal, verify 1,549, transverse 115 -> 97, airside_no_step 457 -> 451, the owner's crossfall pair UNCHANGED at 5.01 %. The measurement that says the raw-pair row is correct and does not bind
LEMD  patch    base 848bf35e   lane v2lemdstruct2    2026-09-15T11:36:11  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/ls2/d5_emit/LEMD_auto.patch.osm  — r4 CLOSING ARM (v2_solve_replay --from planar on the registered da8e5d7f capture, tree = claude/v2lemdstruct2 r4): solve optimal 226.1 s, v2 verify 1,547 rows, DEFECT families ALL ZERO. 34 (13) (3) (a) the foot-row flip ON (LEMD 184 one-way of 524 targets). THE OWNER'S CROSSFALL, by coordinate: contact 582.586 / far edge 582.309 over 18.12 m = 1.529 %, under the 1.985 % junction cap (r3 read 4.313 %); 0 census rows within 20 m. PRICE: 354 of 4,031 runway-family vertices moved > 0.02 m, worst 5.687 m; ramp_in_strip 8 -> 18, strip_transverse worst 13.864 -> 17.700 m, cliffs 10 -> 20, a NEW mid_edge_step 0.950 m between two runway faces at 40.4613609,-3.5446852. Census LAW-TRUE 5,791 ADJUDICATED 1,357 (airside 1,251 -> 1,215). NO BUILD: the ledger's last osm_layers refresh is 2026-09-08
LEMD  patch    base 106459fa   lane v2objcut         2026-09-15T10:44:12  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2objcut/c6_LEMD/structures.json/structures.json  — r2 §33 (6) C lane arm at claude/v2objcut 3b3259dd (base arm /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2objcut/b4_LEMD/...)
LEMD  patch    base 395bd09a   lane v2channel        2026-09-15T10:52:05  /tmp/v2channel/r4/br_LEMD/structures.json  — v2channel round-4 DRY structure replay (branch, §45 (13)); base arm at main in /tmp/v2channel/r4/base_LEMD
LEMD  patch    base e78c9728   lane v2channel        2026-09-15T11:14:01  /tmp/v2channel/r5/br_LEMD/structures.json  — v2channel round-5 §45 (13)(d): LEMD channel:5's three pack witnesses (dsf:obj7/obj8/obj10 = LEMD37/LEMD85/LEMD36) ARE built basin:0's members, floor 588.952 both — channel:5 refused as ruled; channels 3 (channel:1/:2/:4, all neck+clearance); tunnels 51->51 IDENTICAL, basins 1->1 IDENTICAL vs /tmp/v2channel/r5/base_LEMD.
LEMD  patch    base d803147a   lane v2lemdstruct2    2026-09-15T12:24:50  /Users/noah/XPTerrainBuilder/.claude/worktrees/v2lemdstruct2/Ortho4XP/Patches/+40-010/+40-004/LEMD_auto.patch.osm  [MISSING]  — r5 CLOSING BUILD (build_airport.py LEMD --tag v2lemdstruct2r5 --tile 40 -4), rc 0, 980.1 s, ledger tree fddb2fc4a8c6, [harness] shared repo UNCHANGED (full-surface before/after snapshot). THE ACCEPTANCE NUMBER: the owner's raw pair at 40.4611623,-3.5444804 reads 0.280 m over 18.16 m = 1.542 %, under the 1.985 percent junction cap (r3 read 4.313). Item 5 rim 602.16 / ramp floor 597.09 = 5.07 m; item 7 trench rim at 31.06 m; 3 mouth roads. Census LAW-TRUE 6,024 ADJUDICATED 1,934, ramp_in_strip 18, mid_edge_step 2 (0.950 m), strip_transverse 89/17.700, transverse 92, airside_no_step 362, cliffs 20
LEMD  patch    base d803147a   lane v2lemdstruct2    2026-09-15T12:24:50  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/ls2/e_off_emit/LEMD_auto.patch.osm  — r5 MATCHED PAIR, flip OFF arm (the r4 foot-row one-way registration OUT; one tree, one capture, registers asserted before the arm). Verify 1,711 rows; census LAW-TRUE 5,782 ADJUDICATED 1,505 (airside 1,370); CRITICAL motion 7, cliffs 20; mid_edge_step 2 worst 0.950 m; ramp_in_strip 18; the owner's raw pair 4.313 percent. Its ON twin is e_on_emit. THIS PAIR CORRECTS r4, whose runway figures compared arms across a main merge
LEMD  patch    base d803147a   lane v2lemdstruct2    2026-09-15T12:24:50  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/ls2/e_on_emit/LEMD_auto.patch.osm  — r5 MATCHED PAIR, flip ON arm. Verify 1,554 rows; census LAW-TRUE 5,712 ADJUDICATED 1,393 (airside 1,258); CRITICAL motion 5, cliffs 20; mid_edge_step 2 worst 0.950 m (SAME as the OFF arm - it is NOT the flip's doing); ramp_in_strip 18 (same); airside_no_step 452 -> 357, taxi_box 152 -> 130, transverse 98 -> 90, strip_arc 9 -> 4; within_shape +62 and strip_transverse worst 13.864 -> 17.700 m are the flip's real price; the owner's raw pair 4.313 -> 1.529 percent. Runway movement 319 of 4,042 vertices > 0.02 m, worst 5.687 m - attributed to a 111,648 m2 40 (1) runway SHOULDER (cell 15 / face 5) reaching 914 m off the centreline, on which no level row exists
LEMD  patch    base f912ba81   lane v2objcut         2026-09-15T12:02:00  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2objcut/e1_LEMD/structures.json/structures.json  — r3 lane dry --stage structures at claude/v2objcut edf1e3c0; matched base arm at main f912ba81 in /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2objcut/e0_LEMD (LEMD) / /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2objcut/e2_LEMD (OTHH, run 2 - run 1 e0_OTHH read 7 corridors against run 2's 9 at the SAME sha: main's object-corridor reader is NONDETERMINISTIC at OTHH, reported).
LEMD  patch    base f912ba81   lane v2objcut         2026-09-15T12:02:00  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2objcut/f1_LEMD/structures.json/structures.json  — r3 C3' arm with deck_rings_ll published (base arm /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2objcut/f0_LEMD): bridge_deck:-6288 lateral -11.81..+2.29 m -> -10.23..+10.24 m against the Bridge2 pair's inner faces at +-10.185 m (worst |offset|-half 1.62 -> 0.06 m); every other LEMD deck ring BYTE-IDENTICAL.
LEMD  patch    base 9306c56d   lane v2othhdet        2026-09-15T13:10:37  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2othhdet/runs/lemd_lane/structures.json  — v2othhdet LEMD dry --stage structures PAIR: lane arm (claude/v2othhdet 9306c56d) vs base arm scratchpad/v2othhdet/runs/lemd_base (git archive 118d2c40 in basesrc). corridors 1 / tunnels 51 / basins 1 / wall_corridors / plates / door_wells ALL byte-identical; the only difference is corridor_refused 209, the same SET now in sorted order.
LEMD  patch    base 1d6bc71a   lane v2channel        2026-09-15T13:27:32  /tmp/v2channel/r7/br_LEMD/structures.json  — v2channel round-5/6 dry replay (branch): tunnels 52->52 IDENTICAL, basins 1->1 IDENTICAL vs /tmp/v2channel/r7/base_LEMD; channels 3 (channel:1/:2/:4, neck+clearance, 2 decks each); channel:5 refused — its 3 pack witnesses dsf:obj7/obj8/obj10 ARE built basin:0's members (LEMD36/37/85, floor 588.952), exactly §45 (13)(d).
LEMD  capture  base e856ce64   lane v2shoulderband   2026-09-15T13:25:05  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/sb/cap_off/LEMD.pkl  — §40 (5) MATCHED PAIR, band OFF arm (--rule corridor.runway_shoulder_band=false, the §40 (1) law). v2_solve_replay --capture on claude/v2shoulderband, 236 s, 21,376 vertices / 1,059 faces, guard shared repo UNCHANGED. runway_shoulder 545,036 m2 in 17 cells, worst lateral 914.3 m; solve optimal 169.9 s; the 09y runway projection FAILS (Solve error rc kError); runway_step 3 rows at 40.4613609,-3.5446852 (0.950/0.633/0.317 m); census LAW-TRUE 6,807 ADJUDICATED 2,011.
LEMD  capture  base e856ce64   lane v2shoulderband   2026-09-15T13:25:05  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/sb/cap_on/LEMD.pkl  — §40 (5) MATCHED PAIR, band ON arm (--rule corridor.runway_shoulder_band=true, the RULED law). Same tree, same airport, ONE variable, arm line printed per capture. 351 s, 21,883 vertices / 1,099 faces, guard UNCHANGED. runway_shoulder 271,086 m2 in 19 band pieces, worst lateral 75.5 m, remainder 273,949 m2 in 28 faces; solve optimal 70.9 s; runway projection 'held by the solve (nothing to settle)', worst hard row 2.3 mm; runway_step 0; census LAW-TRUE 6,185 ADJUDICATED 1,709.
LEMD  patch    base e856ce64   lane v2shoulderband   2026-09-15T13:25:05  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/sb/emit_off/LEMD_auto.patch.osm  — §40 (5) band OFF arm EMIT (v2_solve_replay --replay --emit --verify off cap_off). The BASE of the matched pair.
LEMD  patch    base e856ce64   lane v2shoulderband   2026-09-15T13:25:05  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/sb/emit_on/LEMD_auto.patch.osm  — §40 (5) band ON arm EMIT. ramp_in_strip 18 -> 9, strip_transverse 93 -> 34, transverse 92 -> 34, CRITICAL motion 12 -> 6, cliffs 20 -> 10; the ONE riser adjacent_ground_step 0 -> 2 (0.580 m).
LEMD  patch    base e856ce64   lane v2shoulderband   2026-09-15T13:25:05  /tmp/harness/v2shoulderband.osm  — CLOSING LEMD AIRPORT-PATH build of claude/v2shoulderband a8138464 (build_airport.py LEMD --tag v2shoulderband, NO --tile per RULINGS 2026-09-15av): rc 0, 351.4 s, status optimal, ways 1123, nodes 21660, body_sha 42241995fdaf, artifact ledger 874c7aee6b0d, v2-verify 1797 rows with every DEFECT family ZERO (runway_transverse / runway_vertical_curve / runway_step), shared repo UNCHANGED (18 lock-churn ops, the allowed class).
LEMD  capture  base 7f80dc71   lane v2padclip        2026-09-16T09:49:15  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2padclip/cap/LEMD.off.pkl  — LEMD PADS-OFF capture (the shipped law) on claude/v2padclip, 219 s, 21,841 vertices / 1,099 faces, guard shared repo UNCHANGED - BASE ARM of the v2padclip LEMD pair; census ADJUDICATED 2,121, law-true 6,479, pad_airside_weld 2. The owner's T4 garage 40.4892214,-3.5944287 is covered by NO ring group on this arm (15h's 'the pad polygon ends 55.28 m short').
LEMD  capture  base 7f80dc71   lane v2padclip        2026-09-16T09:49:15  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2padclip/cap/LEMD.on.pkl  — LEMD PADS-ON capture (--placement pad_from_cluster=true pad_airside_clip=true), 216 s, 20,953 vertices / 1,042 faces, guard UNCHANGED. Under §16g (10) (12): re-node deleted 0 / minted 32 (the shipped-law arm reads 150). The owner's T4 garage is INSIDE building45, a 93-node face (way -10991) at 615.05..615.11 - ONE LEVEL, spread 0.06 m, no short-edge step. Census vs the OFF arm: ADJUDICATED 2,121 -> 1,004 (-53%), within_shape 4,253 -> 3,025, hairline_pair 1,642 -> 1,287; worse: pad_cluster_mismatch 0 -> 1, pad_airside_weld 2 -> 3.
LEMD  capture  base 782a50d6   lane v2padclip        2026-09-16T10:59:14  /private/tmp/claude-501/-Users-noah-XPTerrainBuilder/3fc455a9-745d-4126-a4c3-38d52975e33b/scratchpad/v2padclip/r2/cap/LEMD.lane2.pkl  — r2 LEMD PADS-OFF (shipped law) capture with (12) (1) (c): 200 s, 20,403 vertices / 985 faces. Against main 1bc93833 (cap/LEMD.base.pkl) the shipped arm IMPROVES: ADJUDICATED 1,749 -> 986 (-44%), law-true 6,257 -> 4,850, frontage_near_miss 8 -> 0, pad_airside_weld 2 -> 1. apron faces 106 on BOTH pad arms (was 180 vs 106); OFF-arm renode_minted 150 -> 12.

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

