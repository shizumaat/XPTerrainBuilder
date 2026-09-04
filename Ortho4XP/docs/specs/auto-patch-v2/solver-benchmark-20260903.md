# v2 solver benchmark — HiGHS (scipy) vs OSQP vs hand-rolled ADMM (2026-09-03)

Synthetic airport-like instances (jittered triangulated grid over a ±40 m
DEM with a ridge; runway/taxi breakline chains with caps 0.015 / 0.01 /
0.08; pins along two sloped runway profiles; flat pad groups; DEM bands
outside pavement); feasible (f) and deliberately infeasible (i) variants at
n = 5k / 15k / 50k / 150k vertices; 3 runs each, median wall seconds, peak
RSS. Scripts: `tests/auto_patch_v2/bench/{bench,solvers,report}.py`; raw
rows: `solver-benchmark-20260903.results.jsonl`. Accuracy bar 1e-3 m.

| n | HiGHS LP, real (L1) objective | HiGHS LP, zero objective (phase-1) | OSQP default | OSQP 1e-4 + polish | OSQP 1e-6 + polish | ADMM (own) |
|---|---|---|---|---|---|---|
| 5k | 0.07 s | 0.07 s | 0.07 s (viol > bar) | 0.09 s | 0.20 s | 0.52 s |
| 15k | 0.23 s | 0.48 s | 0.18 s (viol > bar) | 0.63 s | 1.95 s (meets bar) | 3.9 s |
| 50k | 1.14 s, 671 MB | 4.26 s | 1.12 s (viol 8 mm) | 11.9 s (8 mm) | 34.9 s (0.1 mm) | 51 s (8 mm) |
| 150k | **5.29 s, 2.0 GB** | 45.4 s | 3.7 s (**112 mm**) | 42.7 s ("solved inaccurate", 61 mm) | **680 s, FALSE "primal infeasible"** | 211 s, max_iter (48 mm) |

Infeasible instances: HiGHS reports infeasible in 0.01–0.22 s at every
size; OSQP in 0.06–6 s. Diagnosis (WHICH pins contradict): seeded
deletion-filter IIS over HiGHS 0.11 / 0.84 / 10.3 / **109 s** (5k…150k);
raw HiGHS phase-1 via `highspy` 0.2 / 1.7 / 20 / 220 s (no dual-ray API
exposed through scipy's bundled build).

## Findings
1. The LP with the REAL objective is the fastest lawful path at every
   size and the only one under 10 s at 150k. A zero-objective "phase 1"
   makes the simplex wander (45 s at 150k): feasibility-first means
   "solve the real problem; infeasibility is reported by the same call".
2. OSQP is unusable as configured: default tolerance leaves 112 mm
   violations; the tight arm takes 680 s and declares a feasible instance
   infeasible. Not added to the freeze (RULINGS 2026-09-03d: "if it
   measurably beats HiGHS" — it does not).
3. The quadratic objective (Σ w (z − dem)²) was not directly benchmarked
   under HiGHS (scipy exposes HiGHS as LP only). Options for M2: (a) the
   L1 objective (|z − dem| with roughness as L1 of second differences) —
   a pure LP, measured above; (b) piecewise-linear approximation of the
   quadratic; (c) `highspy` QP (HiGHS has a QP solver; needs the wheel).
   M2 starts with (a); (c) is the follow-up benchmark.
4. IIS at 150k (109 s) is too slow for every build; run it only when the
   LP reports infeasible, and seed the deletion filter from the
   structure (pins/flat groups first) to cut the search. At the M2 sizes
   (≤ 15k) it is under a second.
