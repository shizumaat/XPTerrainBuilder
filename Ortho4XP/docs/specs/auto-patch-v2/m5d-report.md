# auto-patch-v2 — M5d report: THE LAST RESORT (RULINGS 2026-09-04t(1))

Lane `lane/v2relax` off main `ede79b2e`. Ruling implemented: **04t(1)** —
"where the hard set is infeasible at a site, the solver may relax ALL
THREE populations together … choosing the combination that minimises the
TOTAL variance from law (a quadratic spread across the IIS rows, not L1's
concentration on one row), and only for the rows an IIS names. No terrace
minting." Every law value from `law/emit.toml [relaxation]`; no env reads;
no v1 imports; every file ≤ 1,000 lines (largest: `law/model.py` 903,
`solve/relax.py` 740); attempt cap two respected (one attempt per target).

## 1. The design — `solve/relax.py`, `solve/iis.py`, `solve/tiers.py`

Order of the law-ordered solve is now HARD → **RELAX** → tiers (04i):

1. **The IIS**, on the build path, inside `iis_time_budget_s` (120 s).
   Fast path (`iis.ray_candidates`): the whole set as ONE HiGHS LP with
   presolve OFF (a reduced model carries no ray), zero objective; the
   DUAL RAY (Farkas certificate) names the rows in its support and, by
   `Aᵀy`, the columns whose `Band` bounds it leans on — 23 rows + 2 bands
   out of 1.8 M at HECA — and QuickXplain reduces that with tiny scipy
   probes. Measured HECA: the seeded deletion filter alone 73–126 s; the
   certificate 22–32 s. The seeded filter remains the path without
   `highspy` / without a ray; both raise `IISBudgetExceeded` at the
   deadline → the tier machinery answers and the report says so.
2. **The site, not the one IIS.** The IIS's vertices name the junior faces
   (`relaxable_from_role = "apron"`'s tier or below, plus the rigid pads);
   the candidates are every hard `Diff`/`Linear` OWNED by a junior tier
   (`tiers.row_tier`) with a vertex on the site and every rigid pad's
   `Flat` on it; the IIS's own rows always. Pins, reach bands, runway and
   taxi-family rows are never relaxed (an IIS naming only those → tiers,
   reason recorded). Why the site: an apron is a membrane — the parallel
   chords beside one IIS path are IISs of their own (the hangar-row twin
   spent three one-IIS-per-round rounds without closing), and the variance
   program gives a row in NO IIS exactly zero slack (relaxing it buys
   nothing and costs), so its SUPPORT is "the rows an IIS names".
3. **Stage 1 — the variance program.** A candidate `Diff` gets a GRADE
   excess `g ≥ 0` (`|Δz| ≤ (cap + g)·d`); a `Linear` a metre slack; a pad
   becomes ONE PLANE `z = z_c + u·dx + v·dy` (its contact may slope, its
   interior stays one plane; its rim vertices ARE the apron's, so no step
   can form). Objective `min Σ d·g² + Σ D·(u²+v²) + Σ s²` — the squared
   excess INTEGRATED along the pavement, whose optimum is a UNIFORM
   over-cap along a chain (plain `Σ g²` loads the long chords, `Σ m²` the
   short edges). Pure variance, no DEM term. **Backend verdict:**
   `highspy` 1.15.1 installed into the venv (wheel
   `highspy-1.15.1-cp314-macosx_11_0_arm64.whl`, **4.5 MB**, one extension
   module — the freeze can carry it via the existing
   `collect_submodules('auto_patch_v2')` import scan; NOT frozen/verified
   in this lane). Its QP is exact at twin scale (0.3 s) and **did not
   finish in 5 min on HECA's 1.8 M-row model** (killed), so the QP runs
   under `qp_time_budget_s` (20 s) and past it a CONVEX PIECEWISE-LINEAR
   approximation of the square answers (`max_pieces = 8` chords from the
   grade / elevation materiality doubling; scipy HiGHS LP, presolve on,
   14 s at HECA) — stated as `approximation: true` in every report. The
   twin proves the two agree within the finest pieces.
4. **Stage 2** fixes the relief into the rows (`cap + g`; a pad's plane as
   equalities at the solved slope, source ruling suffixed `relaxed by
   04t(1)`) and runs the normal `highs.solve` with the L1 DEM preference —
   so `why` reads the relaxed set's duals like any feasible airport's.
5. **Certificate:** plane residual per relaxed pad and the step between
   adjacent relaxed elements ≤ `materiality_m` (0.01): HECA 0.0 / 0.0.

Publication: sidecar key `relaxed_rows` (kind, family, ruling, face,
slack_m, excess/slope, vertex lat/lon); `verify/census.mark_relaxed` tags
every row on a relaxed vertex `relaxed_by = "04t(1)"` and the build log /
`report.json` count them apart (`verify.relaxed_by_04t1`). `why` on an
infeasible hard set runs the last resort and appends a `relaxed by
04t(1)` block (IIS, rows, spread, certificate) — `pipeline/why.py`.

## 2. HECA closing build (`build_airport.py HECA --engine v2`, ledgered)

Tag `HECA_20260904T125846`, artifact-ledger key **726a0e49cdce**, body
`24aae0f161e3`, tree 819d3f8a. Status **optimal, mode relaxed, no tier
demoted** (m5c: k_min 3, apron 175 rows ≤ 0.443 m, 241 s).

| stage | s |
|---|---|
| hard solve (infeasible) | 11.8 |
| IIS (certificate LP + 22-row QuickXplain) | 22.4 |
| stage 1 (QP 20.6 s time-limit → PWL 14.3 s) | 34.9 |
| stage 2 (normal solve, relaxed set) | 41.6 |
| **solve** | **111.3** (m5c 241; prediction < 60 s **MISSED**) |
| total build | 133.7 |

**The IIS (22 rows, one site — pav132):** 8 `Flat` pads (building 359,
350, 339, 328, 323, 311, 300, 343), apron chords of faces 340/356, 3
`frontage_near_miss`, no-step pairs; HELD (not relaxable): 2 taxi
within-shape rows, 1 runway crown transverse, 2 reach bands. Prediction
"24 rows at pav132 only" — 22 (the certificate's minimal set differs from
the seeded filter's by exactly the envelope: taxi rows + crown in place of
the reach bands, same site). Site: 15,283 candidates → **117 relaxed**.

| row | family | excess (grade) | relief |
|---|---|---|---|
| pad building359 (face 338, 145 m) | pads | slope 0.318 % | rise 0.462 m |
| pad building311 (354, 170 m) | pads | 0.194 % | 0.330 m |
| pad building323 (353, 184 m) | pads | 0.166 % | 0.304 m |
| pad building328 (352, 119 m) | pads | 0.166 % | 0.197 m |
| pad building300 (387, 86 m) | pads | 0.153 % | 0.132 m |
| pad building343 (1121, 66 m) | pads | 0.166 % | 0.110 m |
| pad building339 (350, 67 m) | pads | 0.153 % | 0.103 m |
| pad building359 sliver (339, 4 m) | pads | 0.070 % | 0.003 m |
| 42 apron chords, face 340 | apron | +0.01 … +0.15 % (cap 1.01–1.15 %) | ≤ 0.028 m |
| 7 apron chords, face 356 | apron | ≤ +0.10 % (one 83 m chord at 1.10 %) | ≤ 0.086 m |
| 5 apron chords, face 337 | apron | +0.01 … +0.03 % | ≤ 0.012 m |
| 4 frontage_near_miss, faces 340/356 | pads | +0.31 % (1.31 %) | ≤ 0.047 m |
| 51 no-step pairs (apron-owned) | no_step | +0.01 … +0.33 % | ≤ 0.013 m |

Spread: excess grade mean 0.049 %, max 0.318 %, sd 0.067 %, max/mean 6.5;
relief Σ 2.95 m over 117 rows, max 0.462 m (a 145 m pad's rise; m5c's
single-row yield 0.443 m, the L1 stub 25.6 m under M5). Prediction "≤ 0.5
m over-cap across the row set, max slack ≪ the yield's max": the max
relief is a pad's rise across its whole length (0.46 m at 0.32 %), the
largest chord relief 0.086 m — the concentration is gone, the ≪ claim
only holds per chord.

**Oracle census** (`census.py`, `heca_census_rows.json`): **52 / 52**
adjudicated (m5c 84 / 84; the 12 apron|apron within_shape yield rows and
14 no_step rows at pav132 are gone). Of the 52, **2 are relaxed rows**
(airside_no_step apron|apron 0.92 m / 1.10 % over 83.3 m = the face-356
chord relaxed to 1.104 %; frontage_near_miss apron|building 0.19 m / 1.26 %
over 15.05 m = the pads row relaxed to 1.31 %). The other 50 are not this
lane's class: 14 within_shape junction|junction ≤ 1.11 m (the 07-06 vs
04q-2 cap disagreement, `v2caps`), 26 mid/vertex-to-edge steps
cross_connector|junction / stub|stub ≤ 1.59 m (near-coincident rims, m5c
§6.2, planar class), 7 strip_seam_tear ≤ 4.06 m, 3 building cross_shape
slivers. v2 verify: 47 rows + **3 under "relaxed by 04t(1)"** (within_shape
1, airside_no_step 1, frontage_near_miss 1) — the v1 oracle reader does
not read `relaxed_rows` yet (`check_grade.py` is `v2caps`'s file): open
item 2.

## 3. Feasible airports untouched

| | body sha (this lane) | main ede79b2e (ledger, m5c; no `src/auto_patch_v2` commit since) | identical |
|---|---|---|---|
| SPJC `SPJC_20260904T130204` key 2f44ffbbcd20 | 1d639eebaa8e | 1d639eebaa8e (`91700133c773`) | **yes** |
| KCLT `KCLT_20260904T130210` key 8cd40d756304 (77.8 s, hard set feasible, no yield, v2 verify 57) | 518490118a31 | 518490118a31 (`3bfaace6a7e6`) | **yes** |

The last resort runs only after an INFEASIBLE hard solve; the hard path
is the unchanged scipy `linprog` (the twin asserts `sol.z == hard.z`).

## 4. Twins — `tests/auto_patch_v2/test_relax.py` (8) + `test_m5.py` amended

Hangar row: a runway climbing the lawful 1.5 % over 1,200 m, two stubs at
x = ±150 into a 40 m apron strip whose north edge three flat pads front
with 10 m gaps, DEM 10 % across the apron → hard INFEASIBLE, IIS 8 rows
naming the apron face and its pads; the relaxation applies (QP, exact,
1 round, site 1,032 candidates, 150 rows above the grade materiality);
pads become planes (the middle pad follows the apron's own 1 %: slope
1.02 %, the west pad 0.56 %; the certificate holds; consecutive rim
vertices differ by the plane's slope alone); runway pins and taxi rows
exact; no single carrier (max relief share 14 %; L1 ≈ 100 %); the PWL
approximation agrees with the QP within 8 grade-materiality units; a
feasible airport returns the hard solution byte for byte; an IIS naming
tier-0 rows only declines ("no relaxable row") and the tiers answer as
before; `why` runs in relaxed mode; the census tags rows on relaxed
vertices. **The brief's "no slack ≥ 2× mean" is REFUTED on a membrane**
(max/mean ≈ 11 over the material support: a pad's excess counts from
flat, a chord's from its 1 %, the transverse chords join at small
excess) and recorded as such in the twin. `test_m5::test_iis_names_tier_
zero_only` now admits `Linear` rows (the certificate's minimal set
includes a rate row on the runway). `tests/auto_patch_v2`: **183 passed**.

## 5. Not done

* The v1 oracle reader does not yet honour `relaxed_rows` (`check_grade.py`
  belongs to `v2caps`); the 2 relaxed rows are identified here by chord.
* The freeze was not rebuilt; `highspy` in the PyInstaller bundle is asserted
  by the import scan only.
* No timing claim: single runs (HECA solve 111 s, contended by nothing; the
  offline replay measured 88 s for IIS+stage1+stage2).
* `constraints/pads.py` untouched (the plane lives in `relax.py`); one
  SIDECAR_KEYS line added in `emit/osm_adapter.py` (outside the brief's
  file list — the register is closed by design and had to admit the key).

## 6. Open questions (≤ 3)

1. The 20 s QP budget is pure waste at HECA scale (the QP never finishes
   past ~10⁵ rows): keep the exact QP for small sites (a size gate in the
   table) or drop `highspy` and ship the approximation alone?
2. Should the oracle reader read `relaxed_rows` and price those chords at
   their relaxed cap (the 2 remaining rows become 0), i.e. is a relaxed
   row lawful for acceptance, or reported forever under its heading?
3. The spread statistic the owner wants adjudicated: excess GRADE (uniform
   over-cap, what the census reads) or relief METRES per row (what the
   L1 yield concentrated) — the twin asserts the former plus "no single
   carrier".
