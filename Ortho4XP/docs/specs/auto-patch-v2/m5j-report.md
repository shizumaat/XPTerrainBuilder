# auto-patch-v2 — M5j report: the closing items after 05f/05g (lane v2hecaclose, 2026-09-05)

Lane `lane/v2hecaclose` off main `8a939da5`. Four items: (1) `[relaxation]
pad_slope_max = 0.01` (owner 05f) as a table value; (2) HECA's 14 airside
rim steps (the round-3 weld class at two sites); (3) the stage 1 + 2 cost
of HECA's relaxed solve; (4) `test_why.py::test_report_renders_every_section`
erroring only in the full `-n0` run. Every law value from the TOML tables
(one new key, cited below); no env reads; no v1 imports; every touched v2
file ≤ 1,000 lines (`solve/relax.py` 868, `planar/weld.py` 246;
`tests/conftest.py` was 1,160 before this lane and is 1,180 — not a v2
file). Synthetic-first: items 1–3 were attributed and fixed on an offline
capture of HECA's pre-solve product (`airport`, `pm`, `cs` pickled after
`generate`, 33 s) and its classified cells; the weld replayed in 0.9 s, the
relaxation in ~110 s per arm; HECA and CYXY built ONCE each at the close
through the harness, concurrently (correctness runs, not timing-grade).

## 0. Site first — the closing table (branch `7ce6bbd8`, tag `…T162647`)

| airport | artifact key | build s | mode | oracle census adj / airside | airside by family | relaxed pad |
|---|---|---|---|---|---|---|
| HECA | `a644050ed6f2` | 125.9 (solve 101.8: hard 1–12 + IIS 4.7 + stage 1 39.8 + stage 2 55.6) | relaxed-optimal, no tier demoted, 1 round | **10 / 3** (05g: 24 / 17) | cross_shape 3 building\|building (m5d's slivers, unchanged); the 14 cross_connector\|junction rim steps are GONE; groundside 7 unchanged (vertex_to_edge 1 + mid_edge 6) | face 1148: **0.998 %** (05g: 1.28 %), certificate `pad_slope_max_seen 0.0099813 ≤ 0.01`, plane residual 0.0 |
| CYXY | `649dc3dfb3a9` | 5.3 | hard feasible | **0 / 0** (unchanged) | — | — |

HECA's relaxed set: 506 rows (05g: 512), Σ relief 28.41 m (28.70), excess
grade mean 0.117 %, max 3.86 % (one 15 m frontage row; was 2.80 %) — the
0.85 m rise the pad no longer takes (0.66 m now over 66 m) went to the
apron chords and the frontage rows, as 04t(1) asks. 108 rows under the
04x-2 heading (was 150). Suite: `tests/auto_patch_v2` **227 passed** in ONE
`-n0` run (225 + 2 twins); `test_harness.py` + `test_census_cache.py` 326
passed.

## 1. `pad_slope_max` — the table value (05f)

* `law/emit.toml [relaxation] pad_slope_max = 0.01`; `law/model.py
  Relaxation.pad_slope_max` (the loader is field-driven — a table without
  the key refuses to load).
* Stage 1 (`solve/relax.py::_model`): every relaxed pad's plane `(u, v)` is
  bounded to the disc of that radius by `SLOPE_DIRECTIONS = 32` half-planes
  `u·cosθ + v·sinθ ≤ s·cos(π/32)` — the polygon lies INSIDE the disc, so the
  true gradient never exceeds the table value in any direction (|u|, |v| ≤ s
  are among them; on-axis the pad may reach 0.995 s). Both backends (QP and
  the PWL) take the rows.
* The certificate carries `pad_slope_max` / `pad_slope_max_seen` and fails
  over the bound (+ grade materiality).
* `verify/pads.py`: `plane_fit` returns residual AND gradient; a relaxed pad
  that is one plane but steeper than the table value by more than the grade
  materiality is a `pad_flat` row, `reading = "plane_slope"` — a DEFECT
  that fails the airport by name (05e's register, unchanged).
* Twins: `test_relax.py::test_relaxed_pad_slope_is_bounded_by_the_table`
  (cap active on the hangar fixture — the unbounded pad sloped 1.02 %; at
  0.5 % the chords take more; both backends; the certificate),
  `test_pad_flat.py::test_a_relaxed_pad_steeper_than_the_table_is_one_row`.
  `test_pwl_approximation_agrees_with_the_qp`'s tolerance now scales with the
  excess (the pads sit on the cap and the chord that takes the rest lands on
  a PWL breakpoint: 1.2e-3 at 6.3e-3, one piece's width there).
* Measured: highspy's QP returns `kSolveError` on the hangar fixture at a
  0.5 % bound; stage 1 falls to the PWL as designed (the twin uses the
  default backend for that arm).

## 2. HECA's 14 rim steps — attribution and the weld fix

* The two census sites (30.13734,31.40582 / 30.13806,31.40528) are ONE cell
  pair: junction `pav81` #48 (5 vertices, rank 6) against cross_connector
  `pav129` #155 (38 vertices, rank 5); in the planar map faces 42 / 345 with
  vertices v10133 0.414 m, v10134 0.905 m off the junction's boundary and
  v3869 0.530 m off the connector's — a 0.4–0.9 m sliver of graded strip
  (346) between two pavements, the 04u class.
* THE CAUSE (replayed on the cells, `_weld_one` spied): the weld is ONE
  pass. pav81's corner (−931.49, 2865.89) lay 0.903 m off pav131 and was
  projected onto it; that bent the 240 m long edge; pav129's vertex
  (−891.91, 2898.66), 1.031 m off the old edge, was inserted into the bent
  one; and the next pav129 vertex (−807.07, 2971.47) — 1.297 m off the old
  edge — then sat **0.880 m** off the twice-bent edge, inside the tolerance,
  un-welded: `_insert` had examined the straight segment, not the pieces its
  own insertions made. Round 3's CYXY case (0.47 m, one vertex) never needed
  a second look.
* THE FIX (`planar/weld.py`): (a) `_insert` is a per-segment WORKLIST — the
  sub-segments an insertion makes are examined again until no ref vertex
  within the tolerance remains (every ref vertex enters at most once:
  termination); (b) `_weld_one` repeats project + insert to a fixed point
  (`MAX_PASSES = 6`, a convergence guard, never a law value; HECA converges
  in ≤ 2 passes, `WeldStats.passes_max`); (c) a vertex the ring already has
  is never inserted twice (the single pass inserted duplicates through
  adjacent parallel segments — an invalid polygon `buffer(0)` then repaired
  or refused: HECA's refused cells 6 → 3, welded 137 → 131, inserted 126 →
  105). The junior's vertex projected onto the senior's edge is the
  T-vertex form the brief names — the grid-snapped noding
  (`overlay.py`, `min_distinct_spacing_m`) splits the senior's edge at it.
* Measured on the cells: same-side pavement vertices strictly within the
  tolerance of another pavement's boundary after the weld 104 → 83 (66
  pairs; 34 ≤ 5 cm, 26 ≤ 35 cm — the snap merges those; 23 in 0.35–1.0 m,
  none of them a census row). The site pair: 0 residual. I1–I7 kept
  (`test_round3.py` green).

## 3. Stage 1 + 2 cost — the warm start is REFUTED (attempt cap reached)

Single runs on the HECA capture, one machine, sequential, nothing else
running (`stage2_exp.py` in the lane scratchpad, not promoted):

| arm | stage 2 wall | simplex it |
|---|---|---|
| E0 scipy cold (as shipped) | 61.8 s | 80,517 |
| E1 scipy cold, relaxed rows + ε (grade 1e-4 / 5 mm) — degeneracy hypothesis | 59.2 s | 79,706 |
| E2a highspy cold, presolve on | 62.3 s | 80,517 |
| E2b highspy `setSolution` from the OPTIMUM (best case) | 29.1 s | 9,376 |
| **attempt 1**: highspy from stage 1's own point (`Stage1.z`, in the pipeline) | **364 s** | — |
| **attempt 2**: E4 cold solve with the 562 relaxed rows DROPPED 57.1 s (79,371 it), then E5 highspy from its optimum | 53.8 s (+57.1) | 14,243 |

E4 is the finding: the plain feasible L1 LP at HECA's size (1.35 M rows,
51.5 k columns) costs ~57 s on its own — the relaxation is not what makes
stage 2 slow, and a crash basis from any non-optimal point costs 3–4 ms an
iteration. The warm-start code is deleted (refuted mechanisms are deleted;
this report is the record). Predictions "solve < 60 s, total < 90 s" NOT
met: HECA solve 101.8 s, total 125.9 s (05g: 101.8 / 124.9). `highspy`
sizing, for the record: the wheel is already a venv dependency used by
`solve/iis.py`'s certificate on this same path; its function-level
`import highspy` is visible to PyInstaller's bytecode scan, but whether the
current freeze carries it was not verified here.

## 4. `test_why.py::test_report_renders_every_section` — the session detector

* Not reproducible here: four full `-n0` runs (two in the lane, two in the
  main tree) all green. What CAN error that test and no other: it is the
  LAST collected test of `tests/auto_patch_v2`, and pytest reports a
  session-scoped autouse fixture's teardown failure as "ERROR at teardown"
  of the last test. The one such teardown that fails by design is
  `conftest._the_shared_data_repo_survives_the_suite` — and its pure half
  `unauthorised_shared_writes` counted a `.lock` file as an unauthorised
  write (verified: `Elevation_data/dem.lock` → scope `dem` → unlawful). A
  guarded build running BESIDE the suite (the owner's LEMD/HECA rebuilds
  the same afternoon, or a lane's closing build) creates and removes its
  lock in the shared repo lawfully; a 25–45 s `-n0` window sees it, a
  one-second single-test run does not. "Passes alone" and "only the full
  run" both follow.
* Fix (`tests/conftest.py`): `is_lock_churn` (the harness's own
  `is_lock_artifact` predicate) excludes lock files from the unlawful set,
  the churn is printed, and the failure message says pytest attributes it to
  the last collected test. Twin in `test_harness.py::
  test_the_shared_repo_detector_flags_a_test_written_cache`.
* If the parent's ERROR was something else, its traceback names it: this
  lane could not obtain one.

## 5. Not done

* The five-airport sweep (orchestrator's). SPJC / OTHH / LEMD / KCLT not
  rebuilt — the weld fix changes their planar maps.
* No timing claim beyond single runs; HECA built concurrently with CYXY.
* Item 3's predictions unmet (above); the structural option left — ONE
  full-size LP instead of two (the variance program folded into the L1
  solve lexicographically) — changes stage 1's semantics and is a spec
  question, not a lane's.
* The 83 residual sub-tolerance proximities after the weld (none a census
  row) are not chased.
* HECA's 3 building|building slivers: m5d's class, not touched.
* Pre-existing census warning: sidecar key `pad_pavement_no_step_edges` in
  neither oracle register.
