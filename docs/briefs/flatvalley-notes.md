# lane flatvalley — notes (finding F1: "the airside optimum is not unique")

Branch `claude/flatvalley` off main `9baa9e82`. Scratch:
`<scratch>/flatvalley/` (`nullarm.py` = `v2_solve_replay` under
monkeypatched null arms + a per-stage-call instrument; `cmp.py` = the
per-stage diff). Captures REUSED (registered): KCLT
`<scratch>/sweepwalls/base/KCLT.pkl`, HECA
`frames/gaps3/HECA.pkl`; every arm is `--replay … --from classify` on this
tree, so control and arm are one tree, one capture, one variable.

Scheduling deviation (reported): the brief's strict hold ("while another
engine build/replay runs") starved 25 min — three lanes overlap
continuously — so the hold was relaxed to "at most ONE foreign engine
process burning CPU", my replays pinned `--workers 6`. FREEZE/TIMING
windows are still honoured.

## 1. Solver exit facts (read off `solve/design_qp.py`, `design.py`, the log)

- Backend: the module's own proximal semismooth Newton (`solver = "qp"`),
  sparse LU on the normal equations (`method normal`, bordered low-rank
  datum term, Tikhonov floor 1e-12 x max diag). HiGHS only in §5a's elastic
  LP and the two projections.
- "optimal" is a TOLERANCE EXIT, not a certificate: one accepted step
  gained <= `_REL_TOL` 1e-9 x F. KCLT control, |grad| at exit:
  pass 1a 0.18 / 2.19; pass 1b 96.4 / 8.89 / 64.8; stage 2 14.1 … 626.
- Outer loops are capped, not converged: lag `one_way_max_rounds` 3
  (KCLT stage 2: LAG NOT SETTLED), multiplier polish `polish_rounds_max` 2
  with best-iterate return.
- Discrete decisions fed by those iterates: §5a `check_hard_set` (LP,
  demote where s > 0.02), `promote_missed` (> 0.02 on the lagged iterate:
  KCLT 24 in pass 1a, 121 in pass 1b), the hold's interval between the
  passes, pin yield.

## 2. TRUE null changes at KCLT (one tree, one capture) — AIRSIDE DOES NOT MOVE

| arm | what changed | stage 1 (airside) | stage 2 |
|---|---|---|---|
| `k_lsperm` | rows of every linear solve permuted (roundoff-level null) | 0 movers, max < 1e-6 m, same rounds | 0 movers, max < 1e-6 m |
| `k_lpperm` | §5a LP handed its rows in another order | 0 movers (LP relaxes 0 rows in both passes) | demote set 336/336 but 6 rows DIFFER; 147 vertices > 0.02 m, worst 0.216 m, 0 over 0.3 |
| `k_nullband` | VACUOUS (the band never reached stage 1's own set — the ribbon-free map carries its own `cs`); superseded by the slack arm |

So: the QP path is deterministic and roundoff-stable; the §5a LP has a
DEGENERATE optimum (a face of optima, simplex returns a vertex chosen by
row order) — proven at stage 2, where it moves groundside only.

## 3. THE REPRODUCTION — a constraint the control ALREADY SATISFIES moves airside (KCLT)

Arm `k_slack`: 30 `Band` ceilings on apron / taxi vertices, each 0.05 m
ABOVE the higher of the control's own pass-1a and pass-1b level at that
vertex. The control's surface satisfies all 30, so if the control were the
optimum of its (convex) objective the arm's optimum is the SAME point.

| stage call | movers > 0.02 m | > 0.3 m | worst | F control | F arm |
|---|---|---|---|---|---|
| pass 1a (airside) | 506 | 1 | 0.335 m | 126360.912 | 126360.982 |
| pass 1b (airside, shipped) | 615 | 31 | 0.810 m | 216341.329 | 216339.188 |
| stage 2 (whole map) | 1,332 | 56 | 0.810 m | | |

The arm's pass-1a exit is 0.07 ABOVE a point it could have had (the
control's, feasible for it): neither exit is the minimum; they are two
points of one valley, 5.5e-7 apart in relative objective and 0.3 m apart
in level. Objective difference = a tie to solver tolerance.

## 4. THE FLAT DIRECTION, NAMED (pass 1a's first QP, dumped; `flat.py`, `who.py`)

- Hessian (12,135 columns, dense eigen-decomposition at the tight
  optimum's active set): 1 eigenvalue at 0 (-1.6e-15), 3 < 1e-3,
  **269 < 1e-2, 654 < 0.1**, max 7.2e6.
- 83 % of the `k_slack` mover vector's energy lies in the modes < 0.1.
- The columns inside the flat subspace (192 with share > 0.5, 517 with
  > 0.1) carry ONE always-on term: **bending** (median diagonal 0.166).
  No `taxi_trend`, no `apron_trend`, no chord, no `detached`, no body
  datum (1 of 192), and NO ACTIVE one-sided row (1 of 192).
- Who they are: TAXI-FAMILY vertices shared with the graded strip —
  `cross_connector+graded_strip` 190, `stub+graded_strip` 214,
  `primary_parallel+graded_strip` 84, `junction+graded_strip` 18 — in 27
  clusters (largest: 124 columns near 35.22819482, -80.95006358 on
  `pav11` / `pav125`; 75 near 35.21722086, -80.95141990; 70 near
  35.22235766, -80.93415301).
- Airport-wide 2,578 of 12,135 stage-1 columns are bend-only (1,797 of
  them in no body-datum row): the taxi edges beyond the trend's face
  reach, and whole short stubs / cross connectors whose chain is not
  "long" (`taxi_trend_face_reach_m`, §8.6.1) — plus their strip edges.
  The laws that bound them (transverse cap, grade caps, no_step) are
  INEQUALITIES and slack: inside the lawful band the level costs only
  bending, ~1e-2 per m² and less.

So F1 is not "two optima": the objective is strictly convex, but on those
columns its curvature is 8-9 orders under the stiff rows', and the solve
exits on objective gain — it stops wherever its path enters the valley.

## 5. Solver termination alone does NOT fix it (arm c)

`k_tight` (`_REL_TOL` 1e-13): pass 1a ends `no_descent` at F 126360.876
(the shipped exit is 0.036 above it, and 610 columns stand > 0.02 m off
it, worst 0.25 m); pass 1b needs 790 rounds for 177. Null-change
(`k_tight_slack` vs `k_tight`): pass 1a 39 movers (worst 0.082), pass 1b
**141 movers, 7 over 0.3 m, worst 0.59 m** — bar missed. At the QP level
two tight solves from two starts end 0.49 m apart (dF 4.6e-3): the
normal-equation solve cannot resolve modes this soft. Stage 1 wall 41 ->
78 s.

## 6. HECA reproduces it (`h_ctl` / `h_slack`, capture gaps3, main 9baa9e82)

30 satisfied ceilings: pass 1a 157 movers (worst 0.148 m; the
`promote_missed` set also flips by ONE row, 575 -> 574), pass 1b **535
movers, 42 over 0.3 m, worst 0.62 m**, whole map 909 / 86. HECA exits:
pass 1b |grad| 46 / 95 / 956, hard set 0.10 m (NOT settled), §5a LP
relaxes 17 pad rows in pass 1b.

## 7. ARMS (KCLT; replay only, monkeypatched in `nullarm.py`; nothing landed)

"Free column" = a stage-1 column no always-on LEVEL row names (no row
whose coefficients over the free columns sum non-zero — `_level_free_columns`'
own reading, applied per column — and no body-datum row): 1,832 of 12,135.

QP level first (`tie_test.py`, pass 1a's dumped QP, two starts of one
problem): no tie is unstable at any tolerance (1e-12: 499 columns > 0.02
m apart); a DEM tie is stable from eps 0.03 at 1e-12; a membrane (first
difference to mesh neighbours) from 0.3. ANY tie moves ~1,300-1,800
columns off today's exit, worst 0.8-2.9 m, whatever its weight: a mode
with no stiffness goes wherever the tie says. The tie is therefore not a
tolerance detail, it is the LEVEL LAW those columns lack.

| arm | null-change movers, solve-owned airside (bar <= 20 / 0 over 0.3) | cost on the control (solve-owned airside) | runway | LP taxi tier | adjudicated airside (census.py) | stage 1 wall (single runs) |
|---|---|---|---|---|---|---|
| control | **458, 21 over 0.3, worst 0.73** (strip 425, taxi 14, apron 19) | - | 0 | 51 | 3,355 | 13.5 + 27.4 s |
| (c) `_REL_TOL` 1e-13 | pass 1b 141 / 7 / 0.59 — MISS | 858 stage-1 vertices, worst 0.90 | 0 | 51 | not run (verify rows +48) | 18.3 + 59.6 s |
| (a) DEM tie 0.1 both passes, 1e-12 (attempt 1) | pass 1b 70 / 0 / 0.119 — MISS on count | 824, worst 2.20 | 0 | 51 | not run (verify +142) | 13.9 + 71.6 s |
| (a) DEM tie 0.1 in pass 1a, pass 1b tied to PASS 1a's level at 1.0, 1e-12 (attempt 2) | **0** (whole map 16, worst 0.057: the stage-2 LP) — MET | 901, 241 over 0.3, worst 2.16 (strip 729, taxi 86, apron 86) | 0 | 51 | 3,425 (**+70** — MISS) | 14.1 + 35.4 s |
| (a2) MEMBRANE 0.3 in pass 1a, pass 1b tied to pass 1a's level at 1.0, 1e-12 | **0** (whole map 0, worst 0.0004) — MET | 1,149, 245 over 0.3, worst 1.62 (strip 998, taxi 73, apron 78) | 0 | 51 | 3,374 (**+19**, 0.6 % — MISS by the letter; within_shape 11,700 -> 11,651) | 13.9 + 32.1 s |
| (b) lexicographic tie-break | NOT RUN: 07b refuted an objective ORDER (apron preference over DEM fit, census 6 -> 14); and the airside non-uniqueness is not in an LP at all | | | | | |

The stage-2 §5a LP IS a degenerate LP (section 2) and wants its own
deterministic tie-break; it moves groundside only, <= 0.22 m.

## 8. STOP — the question for the spec author

No arm meets every bar: the two that make the surface reproducible
(null-change movers 0) change it ONCE by up to 1.6-2.2 m on ~900-1,150
airside vertices and raise the adjudicated airside census (+19 membrane,
+70 DEM). And WHICH tie is an intent choice, not a solver setting.

Q (yes/no): shall every stage-1 column that no level term names take a
weak MEMBRANE row to its mesh neighbours in pass 1a ("level with what is
beside it": a taxi edge level with its centreline, a short connector a
straight ramp between its contacts), and in pass 1b a tie to its pass-1a
level, with the QP's exit tightened to 1e-12 — accepting a one-time
change of the reference surfaces (KCLT: 1,149 airside vertices, worst
1.62 m, runway 0, adjudicated airside +19)?
Recommendation: YES to the membrane form (no DEM enters pavement, 08t (1);
within_shape falls); NO to the DEM tie (it follows terrain at the
cross-section scale: census +70).  Alternative the author may prefer: give
those columns the taxi trend itself (§8.6.1's reach gate widened) — not
measured here.

## 9. HECA under the membrane arm (`h_mem` / `h_mem_slack`, capture gaps3, main 9baa9e82)

| | control | membrane arm |
|---|---|---|
| null-change movers, solve-owned airside | 379, 9 over 0.3, worst 0.62 (strip 218, taxi 161) | **0** (worst 0.0019 m in any stage call) |
| cost on the control | - | 968, 209 over 0.3, worst 1.01 (strip 621, taxi 340, apron 7); runway 0 |
| §5a LP tiers | pad 17 / taxi 67, 66 | identical |
| adjudicated airside (census.py) | 12,196 | 12,168 (-28); hard_conflict 245 = 245 |
| stage 1 wall (single runs, foreign load) | 38.9 + 75.0 s | 40.2 + 91.7 s |

HECA meets every bar; KCLT misses one (adjudicated airside +19 of 3,355).
These are on main 9baa9e82: main moved to e2eec15c (gap-piece apron
cells, HECA +154 stage-1 unknowns) during the lane — per the master, a
like-for-like study; any landing re-takes the HECA capture on current
main first.

## 10. Not done

- Nothing landed in the engine: the arms live in
  `docs/briefs/flatvalley-scratch/nullarm.py` (monkeypatches, copied from
  the scratch dir for the next lane; NOT a tool, not indexed).
- No closing build, no suites (no engine file changed).
- The stage-2 §5a LP tie-break (groundside, <= 0.22 m) is named, not fixed.
- `promote_missed` flips a row under a null change at HECA (575 -> 574):
  a threshold on an unconverged iterate; gone under the arm, not
  separately attributed.
- The DEM-tie arm was not run at HECA; the taxi-trend-reach alternative
  was not measured anywhere.
- The instrument (`nullarm.py` slack arm + `cmp.py`) is on its first use;
  promotion to `tools/` with an INDEX row is owed on its second.
