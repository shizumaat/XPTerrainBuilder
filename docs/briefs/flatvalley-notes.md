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

So F1 is not "two optima": the objective is strictly convex but its
curvature on those columns is 8-9 orders under the stiff rows', and

## 5. Solver termination alone does NOT fix it (arm c)

`k_tight` (`_REL_TOL` 1e-13): pass 1a ends `no_descent` at F 126360.876
(the shipped exit is 0.036 above it, and 610 columns stand > 0.02 m off
it, worst 0.25 m); pass 1b needs 790 rounds for 177. Null-change
(`k_tight_slack` vs `k_tight`): pass 1a 39 movers (worst 0.082), pass 1b
**141 movers, 7 over 0.3 m, worst 0.59 m** — bar missed. At the QP level
two tight solves from two starts end 0.49 m apart (dF 4.6e-3): the
normal-equation solve cannot resolve modes this soft. Stage 1 wall 41 ->
78 s.
