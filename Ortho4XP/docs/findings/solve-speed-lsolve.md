# Solve speed: why the re-solves cost a full solve, and the seeded first QP (#1270, #803; lane lsolve, 2026-10-26)

## 1. Measured (HECA, synthetic-first)

Capture `frames/lsolve/HECA.pkl` at main `59fa7241d`, replayed `--from constraints`
with every `design_qp.solve_one_sided` call recorded (scratch wrapper; per-call
inputs pickled). Machine loaded (load 13–27, sibling lanes building), so the
seconds below are attribution, not A/B timings.

The base solve makes 25 QP calls. The first QP of every `_solve_stage` starts
COLD (`x0 = None`: the unconstrained least-squares point); the AL / one-way
rounds after it are warm.

| call | pass | columns | first QP? | rounds | linear solves | QP wall s |
|---|---|---|---|---|---|---|
| 0 | pass 1a | 18,793 | cold | 112 | 194 | 9.5 |
| 1–2 | pass 1a AL rounds | | warm | 55, 61 | | 10.6 |
| 3 | pass 1a again (#768 retarget, 15i (3) (b)) | 18,793 | **cold** | 92 | 158 | 11.1 |
| 4–5 | | | warm | 39, 53 | | 8.6 |
| 6 | pass 1b (hold rows) | 18,833 | **cold** | 280 | 492 | 36.3 |
| 7–8 | | | warm | 81, 106 | | 27.8 |
| 9 | pass 1b again (weld re-widen, §57 (3) (ii-c)) | 18,833 | **cold** | 296 | 520 | 31.4 |
| 10–11 | | | warm | 65, 105 | | 17.5 |
| 12 | stage 2 | 38,820 | cold | 333 | 589 | 59.2 |
| 13–17 | | | warm | | | 59.7 |
| 18 | stage 2, pin-yield trial (#778/#781) | 39,058 | **cold** | 301 | 539 | 51.0 |
| 19–23 | | | warm | | | 64.4 |
| 24 | stage 2, final pin set | 38,993 | **cold** | 280 | 503 | 46.4 |
| … | | | | | | |

Of 5,500-odd factorisations, ~70 % of linear-algebra thread-time is SuperLU's
factorisation; the rest is the normal-matrix product, the bordered assembly,
F and the active-set read (stage 2's A1 has 10.8 M one-sided rows).

**What makes the second solves necessary.** They are law, not waste: the
retarget pass (RULINGS 2026-10-15i (3) (b)), the weld re-widen (spec §57 (3)
(ii-c), 2026-10-08d (2)), and the stage-2 pin-yield trials (#778). D1 and D2
(fold them away) were measured out of the bars by lane l412d (cold-patch spec
§6a). What IS waste is that each re-solve's first QP starts cold and pays as
many rounds as the first solve did (92–301 rounds), although its problem
differs from the previous pass's by a few rows.

## 2. Levers measured, and refuted

- **Warm start from the previous pass's FINAL surface** (#1063, deleted as
  noise): attributed here. The final surface solves the AL-SHIFTED problem
  (the multipliers converged, the one-way leaders lagged); the next pass's
  first QP solves the UN-shifted problem (μ = 0, one-way rows off). Started
  there, call 9 still takes 189 rounds (296 cold) — the start is far from the
  optimum it needs.
- **Split by connected components** (parallel): stage 1 is ONE component
  (calls 0, 6). Stage 2 has 292, but the largest holds 70 % of the columns:
  ≤ 1.4× on stage 2's QP, and per-block convergence moves the answer at the
  solver tolerance, not at rounding.
- **Factor reuse by PCG** (the previous factorisation as preconditioner):
  median 33 CG iterations, 0.086 s per solve against 0.05 s to refactor (λ
  changes every round, a full-rank diagonal change). Refuted.
- **Semismooth Newton with exact line search** in place of the λ backoff:
  same optimum (max |Δx| 2.6e-5 m) but 127 rounds against 112; no gain.
- **Ordering reuse** (SuperLU `perm_c` once, NATURAL after): −32 % per
  factorisation at identical fill, rounding-level (5e-14). Not taken in this
  round (§4).
- **HiGHS threads** (#1270's guess): the design QP is not HiGHS (it is
  `design_qp`'s own LM active set, §20c deviation); HiGHS runs only the
  runway projection and the §5a LP, both serial algorithms.

## 3. The rule: seed a re-solve's first QP with the previous pass's FIRST QP

Owner RULINGS 2026-10-19am (a): passes after the first may warm-start from the
previous pass; rounding-level changes are accepted at the visibility bars.

Within one stage (stage 1's passes; stage 2's trials), the first QP of every
`_solve_stage` after the first starts from the per-vertex surface of the
PREVIOUS `_solve_stage`'s first QP, mapped to this solve's columns through the
reduction (a column takes the seed value of its vertices; every column has
one). Both first QPs solve the same kind of problem (μ = 0, one-way rows off),
so the seed sits next to the optimum. The QP is convex with a unique minimum
and runs to the same `qp_rel_tol`, so it ends at the same surface within its
own convergence spread.

Measured on the dumped problems (seed from the previous first QP):

| call | cold rounds | seeded rounds | max |Δx| vs cold answer |
|---|---|---|---|
| 3 (retarget) | 92 | 29 | 1.4e-5 m |
| 9 (re-widen) | 296 | 39 | 1.5e-5 m |

The 1.4e-5 m is the QP's own convergence spread (the cold Newton arm differs
from the cold LM answer by 2.6e-5 m).

Not seeded: the first pass of each stage (no previous pass), stage 2's first
solve (its groundside columns have no stage-1 value), the late stage (other
maps), and the `fixed_point` diagnostic arm.

### 3a. Measured on the whole replay (same capture, both arms, `--from constraints --emit`)

| first QP | main rounds | seeded rounds |
|---|---|---|
| pass 1a again (retarget) | 92 | 29 |
| pass 1b | 280 | 169 |
| pass 1b again (re-widen) | 296 | 49 |
| stage 2 pin-yield trial | 301 | 103 |
| stage 2 final pin set | 280 | 4 |
| **all 30 QPs** | **3,223 rounds, 5,661 solves, 7,233 factorisations** | **2,329 / 4,073 / 5,270 (−28 %)** |

Every AL / one-way round after a first QP keeps its round count (±3), so
the path after the seed is the same path.

The patch: 57,161 nodes, 6 differ, each by one 0.01 m quantum of the
emitted `alt_abs` (a value on a rounding boundary): one cluster of building /
service-road vertices around 30.13527, 31.41133 (groundside). Solve-owned
airside: 0 movers over 0.001 m; runway 0; structures 0
(`tools/airside_value_delta.py`). The graded surface differs at the same 6
vertices only. Census (`tools/harness/census.py`, both replay patches): every
family +0 — total 53,770, adjudicated 12,201 in both arms.

## 4. Acceptance bar

- Replay HECA `--from constraints`, seeded vs main on the same capture, the
  emitted patch joined by canonical node identity: runway movers 0 over
  0.05 m, pavement 0 over 0.05 m, ground 0 over 0.5 m (the visibility bars);
  every mover listed with the max; QP round counts reported per pass.
- Closing build: ONE HECA build through the harness, foreground; census
  against the main control.
- Timing: rounds and linear solves are the machine-independent measure; the
  wall clock only through `check_build_time.py --runs N` on a quiet machine.

## 5. What is left (not this lane)

- CHOLMOD (RULINGS 2026-10-20t): the factorisation is 70 % of the linear
  algebra; a supernodal Cholesky would also thread it. It needs a compiled
  dependency in the frozen engine on three platforms (scikit-sparse is not in
  the venv) — that is #412's architecture, not a lane change.
- Ordering reuse (§2): rounding-level, −32 % per factorisation, after the
  seed lands.
